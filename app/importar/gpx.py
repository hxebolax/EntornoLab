"""Importación de puntos y rutas reales (GPX y GeoJSON) sobre un exterior georreferenciado.

Sirve para marcar en un entorno importado de un mapa la ruta que el alumno
hará de verdad: el profesional la graba andando con el móvil (GPX) o la
dibuja en un mapa (GeoJSON) y aquí se coloca sobre la planta de calle.

El modelo no tiene un elemento «línea», así que una ruta se guarda de dos
maneras a la vez:

- entera, como lista de puntos, en ``entorno.procedencia["rutas"]``, para
  que el Estudio la pinte y el motor pueda usarla;
- como referencias en sus vértices principales («Ruta al colegio: punto 3
  de 8»), que es lo que el alumno encuentra y oye al recorrer el entorno.

Los puntos sueltos (waypoints) pasan a ser referencias permanentes.

Hace falta que el entorno esté georreferenciado (``entorno.georef``): sin
eso no se sabe dónde cae una latitud. Los ficheros se leen del disco y no
salen del equipo; el XML se analiza sin entidades externas.
"""

from __future__ import annotations

import json
import logging
import math
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.i18n import _
from app.dominio import edicion as ed
from app.dominio import geometria as geo
from app.dominio.modelo import Entorno, Planta
from app.importar import formas
from app.importar.comun import ErrorImportacion, Informe, analizar_xml_seguro, frase_cuenta, leer_fichero
from app.importar.georef import proyeccion_de

log = logging.getLogger(__name__)

MAX_BYTES = 20 * 1024 * 1024
MAX_ELEMENTOS = 300_000
CLAVE_RUTAS = "rutas"
# Una ruta se reduce a sus vértices principales: los que se apartan más de esto de la recta.
TOLERANCIA_RUTA_M = 2.0
MAX_REFERENCIAS_POR_RUTA = 40
# Un punto a más de esta distancia de la planta no pertenece a este entorno.
MARGEN_FUERA_M = 50.0


@dataclass
class PuntoGeo:
	"""Un punto con nombre en coordenadas reales."""

	nombre: str
	lat: float
	lon: float
	descripcion: str = ""


@dataclass
class RutaGeo:
	"""Una línea con nombre en coordenadas reales: lista de (latitud, longitud)."""

	nombre: str
	puntos: list[tuple[float, float]] = field(default_factory=list)
	descripcion: str = ""


@dataclass
class Trazado:
	"""Lo leído de un GPX o un GeoJSON: puntos sueltos y rutas."""

	puntos: list[PuntoGeo] = field(default_factory=list)
	rutas: list[RutaGeo] = field(default_factory=list)
	origen: str = ""


def _coordenada(lat: Any, lon: Any) -> tuple[float, float] | None:
	try:
		latitud, longitud = float(lat), float(lon)
	except TypeError, ValueError:
		return None
	if not (math.isfinite(latitud) and math.isfinite(longitud)) or abs(latitud) > 90.0 or abs(longitud) > 180.0:
		return None
	return latitud, longitud


def _bytes_de(origen: str | os.PathLike[str] | bytes) -> tuple[bytes, str]:
	if isinstance(origen, (bytes, bytearray)):
		if len(origen) > MAX_BYTES:
			raise ErrorImportacion(_("El fichero es demasiado grande para importarlo."))
		return bytes(origen), ""
	return leer_fichero(origen, MAX_BYTES), Path(origen).stem


def leer_gpx(origen: str | os.PathLike[str] | bytes) -> Trazado:
	"""Lee un GPX: sus puntos (``wpt``), sus rutas (``rte``) y sus recorridos grabados (``trk``)."""
	datos, nombre = _bytes_de(origen)
	raiz = analizar_xml_seguro(datos, MAX_BYTES, MAX_ELEMENTOS)
	if raiz.tag != "gpx":
		raise ErrorImportacion(_("El fichero no es un GPX: su elemento principal no es «gpx»."))
	trazado = Trazado(origen=nombre or "GPX")
	for punto in raiz.findall("wpt"):
		coordenada = _coordenada(punto.get("lat"), punto.get("lon"))
		if coordenada is not None:
			trazado.puntos.append(
				PuntoGeo(
					(punto.findtext("name") or "").strip() or _("Punto"),
					coordenada[0],
					coordenada[1],
					(punto.findtext("desc") or punto.findtext("cmt") or "").strip(),
				)
			)
	for ruta in raiz.findall("rte"):
		puntos = [c for c in (_coordenada(p.get("lat"), p.get("lon")) for p in ruta.findall("rtept")) if c is not None]
		if len(puntos) >= 2:
			trazado.rutas.append(RutaGeo((ruta.findtext("name") or "").strip() or _("Ruta"), puntos, (ruta.findtext("desc") or "").strip()))
	for recorrido in raiz.findall("trk"):
		puntos = [c for c in (_coordenada(p.get("lat"), p.get("lon")) for p in recorrido.iter("trkpt")) if c is not None]
		if len(puntos) >= 2:
			trazado.rutas.append(
				RutaGeo((recorrido.findtext("name") or "").strip() or _("Recorrido"), puntos, (recorrido.findtext("desc") or "").strip())
			)
	if not trazado.puntos and not trazado.rutas:
		raise ErrorImportacion(_("El GPX no tiene puntos ni rutas."))
	return trazado


def _linea_geojson(coordenadas: Any) -> list[tuple[float, float]]:
	"""Lista de (latitud, longitud) de un ``coordinates`` de línea (GeoJSON da longitud primero)."""
	if not isinstance(coordenadas, list):
		return []
	puntos = []
	for par in coordenadas:
		if isinstance(par, list) and len(par) >= 2:
			coordenada = _coordenada(par[1], par[0])
			if coordenada is not None:
				puntos.append(coordenada)
	return puntos


def _geometria_geojson(geometria: Any, nombre: str, descripcion: str, trazado: Trazado) -> None:
	if not isinstance(geometria, dict):
		return
	tipo = geometria.get("type")
	coordenadas = geometria.get("coordinates")
	if tipo == "Point" and isinstance(coordenadas, list) and len(coordenadas) >= 2:
		coordenada = _coordenada(coordenadas[1], coordenadas[0])
		if coordenada is not None:
			trazado.puntos.append(PuntoGeo(nombre or _("Punto"), coordenada[0], coordenada[1], descripcion))
	elif tipo == "MultiPoint" and isinstance(coordenadas, list):
		for par in coordenadas:
			_geometria_geojson({"type": "Point", "coordinates": par}, nombre, descripcion, trazado)
	elif tipo == "LineString":
		puntos = _linea_geojson(coordenadas)
		if len(puntos) >= 2:
			trazado.rutas.append(RutaGeo(nombre or _("Ruta"), puntos, descripcion))
	elif tipo in ("MultiLineString", "Polygon") and isinstance(coordenadas, list):
		for linea in coordenadas[: 1 if tipo == "Polygon" else None]:
			_geometria_geojson({"type": "LineString", "coordinates": linea}, nombre, descripcion, trazado)
	elif tipo == "GeometryCollection":
		for parte in geometria.get("geometries") or []:
			_geometria_geojson(parte, nombre, descripcion, trazado)


def leer_geojson(origen: str | os.PathLike[str] | bytes) -> Trazado:
	"""Lee un GeoJSON: los puntos pasan a ser puntos y las líneas (y el borde de los polígonos), rutas."""
	datos, nombre = _bytes_de(origen)
	try:
		contenido = json.loads(datos.decode("utf-8-sig"))
	except (UnicodeDecodeError, ValueError) as error:
		raise ErrorImportacion(_("El fichero no es un GeoJSON válido.")) from error
	if not isinstance(contenido, dict):
		raise ErrorImportacion(_("El fichero no es un GeoJSON válido."))
	trazado = Trazado(origen=nombre or "GeoJSON")
	if contenido.get("type") == "FeatureCollection":
		elementos = [e for e in contenido.get("features") or [] if isinstance(e, dict)]
	elif contenido.get("type") == "Feature":
		elementos = [contenido]
	else:
		elementos = [{"geometry": contenido, "properties": {}}]
	for elemento in elementos:
		propiedades = elemento.get("properties") if isinstance(elemento.get("properties"), dict) else {}
		nombre_elemento = str(propiedades.get("name") or propiedades.get("nombre") or propiedades.get("title") or "").strip()
		descripcion = str(propiedades.get("description") or propiedades.get("descripcion") or propiedades.get("desc") or "").strip()
		_geometria_geojson(elemento.get("geometry"), nombre_elemento, descripcion, trazado)
	if not trazado.puntos and not trazado.rutas:
		raise ErrorImportacion(_("El GeoJSON no tiene puntos ni líneas."))
	return trazado


def rutas_de(entorno: Entorno, planta_id: str | None = None) -> list[dict[str, Any]]:
	"""Rutas guardadas en el entorno (las de una planta, o todas): ``{"nombre", "planta", "puntos", "origen"}``."""
	rutas = entorno.procedencia.get(CLAVE_RUTAS)
	if not isinstance(rutas, list):
		return []
	return [ruta for ruta in rutas if isinstance(ruta, dict) and (planta_id is None or ruta.get("planta") == planta_id)]


def anadir_trazado(entorno: Entorno, planta: Planta, trazado: Trazado, referencias_de_ruta: bool = True) -> Informe:
	"""Coloca sobre una planta georreferenciada los puntos y las rutas leídos, y devuelve el informe.

	Los puntos pasan a ser referencias; cada ruta se guarda entera en
	``procedencia["rutas"]`` y, si se pide, deja referencias en sus vértices
	principales. Lo que cae lejos de la planta se deja fuera y se anota.
	"""
	proyeccion = proyeccion_de(entorno)
	if proyeccion is None:
		raise ErrorImportacion(
			_(
				"Este entorno no está georreferenciado: no se sabe dónde colocar una ruta real. Solo se puede hacer sobre un entorno importado de un mapa."
			)
		)
	informe = Informe(titulo=_("Importación de «{origen}»").format(origen=trazado.origen))
	caja = planta.caja()
	fuera = 0
	creados = 0
	for punto in trazado.puntos:
		x, y = proyeccion.a_xy(punto.lat, punto.lon)
		if not formas.dentro_de_caja((x, y), caja, MARGEN_FUERA_M):
			fuera += 1
			continue
		ed.anadir_referencia(entorno, planta, punto.nombre, round(x, 2), round(y, 2), tipo="punto", descripcion=punto.descripcion)
		creados += 1
	rutas_guardadas = 0
	for ruta in trazado.rutas:
		puntos = formas.sin_puntos_repetidos([proyeccion.a_xy(lat, lon) for lat, lon in ruta.puntos], 0.3)
		dentro = [p for p in puntos if formas.dentro_de_caja(p, caja, MARGEN_FUERA_M)]
		if len(dentro) < 2:
			fuera += 1
			continue
		if len(dentro) < len(puntos):
			informe.anotar_aviso(
				_("Parte de la ruta «{ruta}» cae fuera de la zona del entorno y se ha recortado.").format(ruta=ruta.nombre)
			)
		linea = formas.simplificar_linea(dentro, 0.5)
		entorno.procedencia.setdefault(CLAVE_RUTAS, []).append(
			{
				"nombre": ruta.nombre,
				"descripcion": ruta.descripcion,
				"planta": planta.id,
				"puntos": [[round(x, 2), round(y, 2)] for x, y in linea],
				"longitud_m": round(geo.longitud_linea(linea), 1),
				"origen": trazado.origen,
			}
		)
		rutas_guardadas += 1
		if referencias_de_ruta:
			tolerancia = TOLERANCIA_RUTA_M
			principales = formas.simplificar_linea(linea, tolerancia)
			while len(principales) > MAX_REFERENCIAS_POR_RUTA:
				tolerancia *= 1.5
				principales = formas.simplificar_linea(linea, tolerancia)
			for numero, (x, y) in enumerate(principales, start=1):
				if numero == 1:
					nombre = _("{ruta}: salida").format(ruta=ruta.nombre)
				elif numero == len(principales):
					nombre = _("{ruta}: llegada").format(ruta=ruta.nombre)
				else:
					nombre = _("{ruta}: punto {n} de {total}").format(ruta=ruta.nombre, n=numero, total=len(principales))
				ed.anadir_referencia(
					entorno,
					planta,
					nombre,
					round(x, 2),
					round(y, 2),
					tipo="punto",
					descripcion=_("Marca de una ruta importada."),
					permanente=False,
				)
	informe.contar("puntos", creados)
	informe.contar("rutas", rutas_guardadas)
	if creados:
		informe.anotar_importado(_("{puntos}, como referencias.").format(puntos=frase_cuenta(creados, "{n} punto", "{n} puntos")))
	if rutas_guardadas:
		informe.anotar_importado(
			_("{rutas}, guardadas enteras y marcadas con referencias en sus giros.").format(
				rutas=frase_cuenta(rutas_guardadas, "{n} ruta", "{n} rutas")
			)
		)
		informe.anotar_revisar(
			_(
				"Una ruta grabada con el móvil se desvía varios metros de la realidad: compruebe que sus puntos caen en la acera y no en la calzada o dentro de un edificio."
			)
		)
	if fuera:
		informe.anotar_aviso(
			_("{elementos} fuera de la zona del entorno; no se han importado.").format(
				elementos=frase_cuenta(fuera, "{n} elemento cae", "{n} elementos caen")
			)
		)
	if not creados and not rutas_guardadas:
		raise ErrorImportacion(_("Nada de «{origen}» cae dentro de la zona de este entorno.").format(origen=trazado.origen))
	log.info("Trazado «%s»: %s puntos y %s rutas añadidos a la planta %s", trazado.origen, creados, rutas_guardadas, planta.id)
	return informe


def importar_gpx(entorno: Entorno, planta: Planta, origen: str | os.PathLike[str] | bytes, referencias_de_ruta: bool = True) -> Informe:
	"""Lee un GPX y lo coloca sobre la planta de una vez."""
	return anadir_trazado(entorno, planta, leer_gpx(origen), referencias_de_ruta)


def importar_geojson(entorno: Entorno, planta: Planta, origen: str | os.PathLike[str] | bytes, referencias_de_ruta: bool = True) -> Informe:
	"""Lee un GeoJSON y lo coloca sobre la planta de una vez."""
	return anadir_trazado(entorno, planta, leer_geojson(origen), referencias_de_ruta)
