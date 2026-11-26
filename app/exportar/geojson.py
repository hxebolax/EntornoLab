"""Exportación de un entorno a GeoJSON, planta por planta.

GeoJSON es el formato de intercambio que entienden los sistemas de
información geográfica, los editores de mapas y muchas aplicaciones de
navegación. Cada elemento del entorno sale como una «feature» con:

- sus propiedades de EntornoLab (prefijo ``elab:``), para no perder nada;
- las etiquetas equivalentes de **Simple Indoor Tagging** de OpenStreetMap
  cuando existen (``indoor=room``, ``door=*``, ``level``, ``highway=steps``…);
- las de **IMDF** (el formato de mapas de interiores) cuando hay
  equivalencia: ``feature_type`` (unit, opening, fixture, amenity, footprint),
  ``category`` y ``level_id``.

Coordenadas: si el entorno está georreferenciado salen en longitud y latitud
reales (WGS84), como pide la norma. Si no, salen en metros locales (x al
este, y al norte) y el fichero lo avisa con la clave ``crs_local``: sirve
para intercambiar el plano, pero no para ponerlo sobre un mapa.

Si el entorno viene de OpenStreetMap, el fichero lleva la atribución y la
licencia ODbL, que hay que conservar.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any

from app.dominio.catalogo import Catalogo
from app.dominio.formato import identificador_seguro
from app.dominio.geometria import Punto
from app.dominio.modelo import Abertura, Entorno, Espacio, Planta
from app.exportar.fichas import NO, SI, estado_de
from app.importar.georef import Proyeccion, proyeccion_de, texto_atribucion

log = logging.getLogger(__name__)

# Suelo del modelo → valor de ``surface`` de OpenStreetMap.
_SUPERFICIES: dict[str, str] = {
	"baldosa": "paving_stones",
	"madera": "wood",
	"moqueta": "carpet",
	"alfombra": "carpet",
	"hormigon": "concrete",
	"asfalto": "asphalt",
	"acera": "paving_stones",
	"adoquin": "sett",
	"tierra": "ground",
	"hierba": "grass",
	"grava": "gravel",
	"metal": "metal",
	"arena": "sand",
}
# Tipo de espacio → (etiquetas de OpenStreetMap, categoría de «unit» de IMDF o cadena vacía).
_ESPACIOS: dict[str, tuple[dict[str, str], str]] = {
	"habitacion": ({"indoor": "room"}, "room"),
	"pasillo": ({"indoor": "corridor"}, "walkway"),
	"vestibulo": ({"indoor": "area"}, "lobby"),
	"escalera": ({"indoor": "room", "stairs": "yes"}, "stairs"),
	"cabina": ({"indoor": "room", "highway": "elevator"}, "elevator"),
	"exterior": ({}, ""),
	"acera": ({"highway": "footway", "footway": "sidewalk", "area": "yes"}, ""),
	"calzada": ({"area:highway": "residential"}, ""),
	"paso_peatones": ({"highway": "footway", "footway": "crossing", "area": "yes"}, ""),
	"plaza": ({"highway": "pedestrian", "area": "yes"}, ""),
	"parque": ({"leisure": "park"}, ""),
	"sendero": ({"highway": "path", "area": "yes"}, ""),
	"edificio": ({"building": "yes"}, ""),
}
_BARRERAS = {"valla": "fence", "seto": "hedge"}
_PUERTAS = {"batiente": "hinged", "corredera": "sliding", "automatica": "yes", "ninguna": "no"}
_REFERENCIAS: dict[str, dict[str, str]] = {
	"parada": {"public_transport": "platform"},
	"semaforo": {"highway": "traffic_signals"},
	"portal": {"entrance": "yes"},
	"comercio": {"shop": "yes"},
	"mobiliario": {"amenity": "bench"},
}


class _Coordenadas:
	"""Convierte puntos del entorno a las coordenadas del fichero: reales si hay georreferencia."""

	def __init__(self, proyeccion: Proyeccion | None) -> None:
		self.proyeccion = proyeccion
		self.minimos = [float("inf"), float("inf")]
		self.maximos = [float("-inf"), float("-inf")]

	def punto(self, p: Punto) -> list[float]:
		"""Un punto como [longitud, latitud] (o [x, y] locales); de paso ensancha la caja del documento."""
		if self.proyeccion is not None:
			lat, lon = self.proyeccion.a_latlon(p[0], p[1])
			par = [round(lon, 7), round(lat, 7)]
		else:
			par = [round(p[0], 3), round(p[1], 3)]
		for i in (0, 1):
			self.minimos[i] = min(self.minimos[i], par[i])
			self.maximos[i] = max(self.maximos[i], par[i])
		return par

	def linea(self, puntos: Any) -> list[list[float]]:
		"""Una lista de puntos convertida."""
		return [self.punto(p) for p in puntos]

	def anillo(self, contorno: Any) -> list[list[list[float]]]:
		"""Un contorno como anillo de polígono GeoJSON: cerrado, repitiendo el primer punto."""
		anillo = self.linea(contorno)
		if anillo and anillo[0] != anillo[-1]:
			anillo.append(list(anillo[0]))
		return [anillo]


def _propiedades(elemento: Any, clase: str, planta: Planta, extra: dict[str, Any] | None = None) -> dict[str, Any]:
	propiedades: dict[str, Any] = {
		"id": elemento.id,
		"name": getattr(elemento, "nombre", "") or "",
		"level": str(planta.nivel),
		"level_id": planta.id,
		"elab:clase": clase,
	}
	descripcion = getattr(elemento, "descripcion", "")
	if descripcion:
		propiedades["description"] = descripcion
	if extra:
		propiedades.update({clave: valor for clave, valor in extra.items() if valor not in ("", None)})
	return propiedades


def _feature(tipo: str, coordenadas: Any, propiedades: dict[str, Any]) -> dict[str, Any]:
	return {
		"type": "Feature",
		"id": propiedades.get("id"),
		"geometry": {"type": tipo, "coordinates": coordenadas},
		"properties": propiedades,
	}


def _etiquetas_paso(paso: Espacio) -> dict[str, str]:
	"""Etiquetas de OpenStreetMap de un paso; lo que no se sabe no se escribe (que es como OSM dice «no lo sé»)."""
	etiquetas: dict[str, str] = {}
	datos = paso.datos
	semaforo = estado_de(datos, "semaforo")
	if semaforo == SI:
		etiquetas["crossing"] = "traffic_signals"
	elif semaforo == NO:
		etiquetas["crossing"] = "uncontrolled"
	for clave, etiqueta in (
		("sonoro", "traffic_signals:sound"),
		("vibracion", "traffic_signals:vibration"),
		("pulsador", "button_operated"),
		("isleta", "crossing:island"),
		("tactil", "tactile_paving"),
	):
		estado = estado_de(datos, clave)
		if estado in (SI, NO) and (semaforo == SI or clave in ("isleta", "tactil")):
			etiquetas[etiqueta] = "yes" if estado == SI else "no"
	if datos.get("bordillo"):
		etiquetas["kerb"] = str(datos["bordillo"])
	return etiquetas


def _espacio(espacio: Espacio, planta: Planta, coordenadas: _Coordenadas) -> dict[str, Any]:
	etiquetas, categoria = _ESPACIOS.get(espacio.tipo, ({}, ""))
	extra: dict[str, Any] = dict(etiquetas)
	extra["elab:tipo"] = espacio.tipo
	extra["elab:suelo"] = espacio.suelo
	extra["elab:acustica"] = espacio.acustica
	extra["surface"] = _SUPERFICIES.get(espacio.suelo, "")
	if espacio.suelo == "agua":
		extra["natural"] = "water"
	if espacio.tipo == "paso_peatones":
		extra.update(_etiquetas_paso(espacio))
	if espacio.tipo == "escalera" and planta.exterior:
		extra = {clave: valor for clave, valor in extra.items() if clave not in ("indoor", "stairs")}
		extra["highway"] = "steps"
		extra["area"] = "yes"
		if espacio.datos.get("peldanos"):
			extra["step_count"] = str(espacio.datos["peldanos"])
	if espacio.macizo:
		extra["feature_type"] = "footprint"
		extra["category"] = "ground"
		extra["elab:macizo"] = True
	elif categoria and (not planta.exterior or espacio.cerrado):
		extra["feature_type"] = "unit"
		extra["category"] = categoria
	if not espacio.cerrado and not espacio.macizo and espacio.tipo in ("habitacion", "pasillo"):
		extra["indoor"] = "area"
	for clave in ("origen", "via", "lado", "ancho", "forma", "segun_mapa", "osm", "uso"):
		if clave in espacio.datos:
			extra[f"elab:{clave}"] = espacio.datos[clave]
	return _feature("Polygon", coordenadas.anillo(espacio.contorno), _propiedades(espacio, "espacio", planta, extra))


def _abertura(abertura: Abertura, planta: Planta, coordenadas: _Coordenadas) -> dict[str, Any]:
	extra: dict[str, Any] = {
		"elab:tipo": abertura.tipo,
		"elab:estado": abertura.estado,
		"elab:hoja": abertura.hoja,
		"width": str(round(abertura.ancho, 2)),
	}
	if abertura.tipo == "ventana":
		extra["window"] = "yes"
	else:
		extra["door"] = "no" if abertura.tipo == "hueco" else _PUERTAS.get(abertura.hoja, "yes")
		if abertura.hoja == "automatica":
			extra["door"] = "yes"
			extra["automatic_door"] = "yes"
		if abertura.estado == "con_llave":
			extra["locked"] = "yes"
		if abertura.tipo == "portal" or abertura.es_salida:
			extra["entrance"] = "main" if abertura.es_salida else "yes"
		extra["feature_type"] = "opening"
		extra["category"] = "pedestrian.principal" if abertura.es_salida else "pedestrian"
	return _feature("LineString", coordenadas.linea((abertura.a, abertura.b)), _propiedades(abertura, "abertura", planta, extra))


def features_de_planta(
	entorno: Entorno, planta: Planta, coordenadas: _Coordenadas, catalogo: Catalogo | None = None
) -> list[dict[str, Any]]:
	"""Todas las «features» de una planta, con las coordenadas ya convertidas."""
	features: list[dict[str, Any]] = []
	for espacio in planta.espacios:
		if len(espacio.contorno) >= 3:
			features.append(_espacio(espacio, planta, coordenadas))
	for zona in planta.zonas:
		if len(zona.contorno) >= 3:
			extra = {
				"elab:suelo": zona.suelo,
				"surface": _SUPERFICIES.get(zona.suelo, ""),
				"tactile_paving": "yes" if zona.suelo.startswith("tactil") else "",
			}
			features.append(_feature("Polygon", coordenadas.anillo(zona.contorno), _propiedades(zona, "zona", planta, extra)))
	for pared in planta.paredes:
		extra = {
			"barrier": _BARRERAS.get(pared.material, "wall"),
			"indoor": "" if planta.exterior else "wall",
			"height": str(round(pared.altura, 2)),
			"elab:material": pared.material,
			"elab:bloquea_paso": pared.bloquea_paso,
			"elab:bloquea_sonido": pared.bloquea_sonido,
		}
		features.append(_feature("LineString", coordenadas.linea((pared.a, pared.b)), _propiedades(pared, "pared", planta, extra)))
	for abertura in planta.aberturas:
		features.append(_abertura(abertura, planta, coordenadas))
	for objeto in planta.objetos:
		huella = catalogo.huella(objeto) if catalogo is not None else objeto.huella_caja()
		extra = {
			"feature_type": "fixture",
			"category": "furniture",
			"elab:tipo": objeto.tipo,
			"elab:ancho": round(objeto.ancho, 3),
			"elab:fondo": round(objeto.fondo, 3),
			"elab:alto": round(objeto.alto, 3),
			"elab:rumbo": round(objeto.rumbo, 1),
			"height": str(round(objeto.alto, 2)),
		}
		features.append(_feature("Polygon", coordenadas.anillo(huella), _propiedades(objeto, "objeto", planta, extra)))
	for fuente in planta.fuentes:
		extra = {"elab:sonido": fuente.sonido, "elab:radio": fuente.radio, "elab:volumen": fuente.volumen}
		features.append(_feature("Point", coordenadas.punto((fuente.x, fuente.y)), _propiedades(fuente, "fuente", planta, extra)))
	for referencia in planta.referencias:
		extra = dict(_REFERENCIAS.get(referencia.tipo, {}))
		extra.update(
			{"feature_type": "amenity", "category": "unspecified", "elab:tipo": referencia.tipo, "elab:permanente": referencia.permanente}
		)
		features.append(
			_feature("Point", coordenadas.punto((referencia.x, referencia.y)), _propiedades(referencia, "referencia", planta, extra))
		)
	for via in planta.vias:
		if len(via.eje) < 2:
			continue
		extra = {
			"highway": "residential",
			"lanes": str(via.carriles),
			"oneway": {"ida": "yes", "vuelta": "-1"}.get(via.sentido, "no"),
			"maxspeed": str(round(via.velocidad_kmh)),
			"width": str(round(via.ancho, 2)),
			"elab:trafico": via.trafico,
		}
		features.append(_feature("LineString", coordenadas.linea(via.eje), _propiedades(via, "via", planta, extra)))
	for conector in entorno.conectores:
		niveles = ";".join(str(p.nivel) for p in (entorno.planta(i) for i in conector.plantas()) if p is not None)
		for numero, posicion in enumerate(conector.posiciones()):
			if posicion.planta != planta.id:
				continue
			extra = {
				"highway": "elevator" if conector.tipo == "ascensor" else ("steps" if conector.tipo.startswith("escalera") else "footway"),
				"conveying": "yes" if conector.tipo == "escalera_mecanica" else "",
				"ramp": "yes" if conector.tipo == "rampa" else "",
				"level": niveles,
				"elab:tipo": conector.tipo,
				"elab:conector": conector.id,
				"elab:rumbo": round(posicion.rumbo, 1),
			}
			propiedades = _propiedades(conector, "conector", planta, extra)
			propiedades["id"] = f"{conector.id}#{numero}"
			features.append(_feature("Point", coordenadas.punto(posicion.punto), propiedades))
	return features


def a_geojson(entorno: Entorno, planta: Planta | None = None, catalogo: Catalogo | None = None) -> dict[str, Any]:
	"""El entorno (o una sola planta) como diccionario GeoJSON, listo para ``json.dumps``."""
	proyeccion = proyeccion_de(entorno)
	coordenadas = _Coordenadas(proyeccion)
	plantas = [planta] if planta is not None else list(entorno.plantas)
	features: list[dict[str, Any]] = []
	for una in plantas:
		features.extend(features_de_planta(entorno, una, coordenadas, catalogo))
	documento: dict[str, Any] = {
		"type": "FeatureCollection",
		"name": entorno.nombre if planta is None else f"{entorno.nombre} - {planta.nombre}",
		"elab:entorno": entorno.id,
		"elab:niveles": [
			{"level_id": una.id, "level": una.nivel, "name": una.nombre, "outdoor": una.exterior, "elevation_m": una.altura_m}
			for una in plantas
		],
		"features": features,
	}
	if features:
		documento["bbox"] = [coordenadas.minimos[0], coordenadas.minimos[1], coordenadas.maximos[0], coordenadas.maximos[1]]
	if proyeccion is None:
		documento["crs_local"] = {
			"unidades": "metros",
			"eje_x": "este",
			"eje_y": "norte",
			"nota": "Coordenadas locales del plano, no geográficas.",
		}
	atribucion = texto_atribucion(entorno.procedencia)
	if atribucion:
		documento["attribution"] = atribucion
		documento["license"] = str(entorno.procedencia.get("licencia") or "")
	return documento


def texto_geojson(entorno: Entorno, planta: Planta | None = None, catalogo: Catalogo | None = None) -> str:
	"""El GeoJSON como texto, con sangría para poder revisarlo."""
	return json.dumps(a_geojson(entorno, planta, catalogo), ensure_ascii=False, indent="\t") + "\n"


def guardar_geojson(entorno: Entorno, carpeta: str | os.PathLike[str], catalogo: Catalogo | None = None) -> list[Path]:
	"""Escribe un fichero ``.geojson`` por planta en ``carpeta`` y devuelve sus rutas."""
	destino = Path(carpeta)
	destino.mkdir(parents=True, exist_ok=True)
	base = identificador_seguro(entorno.nombre or entorno.id, "entorno")
	escritos: list[Path] = []
	for planta in entorno.plantas:
		ruta = destino / f"{base}_{identificador_seguro(planta.nombre or planta.id, 'planta')}.geojson"
		ruta.write_text(texto_geojson(entorno, planta, catalogo), encoding="utf-8", newline="\n")
		escritos.append(ruta)
	log.info("GeoJSON de «%s»: %s ficheros", entorno.nombre, len(escritos))
	return escritos
