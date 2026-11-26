"""Interiores de edificios cartografiados en OpenStreetMap (Simple Indoor Tagging).

Algunos edificios públicos (estaciones, centros comerciales, universidades)
tienen sus salas dibujadas en el mapa con ``indoor=room``, ``indoor=corridor``
o ``indoor=area`` y su planta en ``level``. Con la opción de interiores,
``convertir`` las trae como habitaciones editables:

- las de la planta 0 van en la propia planta de calle (se entra andando
  desde la acera) y su edificio deja de ser un bloque macizo;
- las demás van cada una en su planta, que se crea si hace falta;
- las puertas (``door=*`` o ``entrance=*`` en el contorno de una sala) se
  abren en su pared;
- los ascensores (``highway=elevator``) se convierten en conectores cuando
  sus paradas caen dentro de una sala, y las escaleras con peldaños
  conocidos también; lo que no se puede conectar con seguridad se deja como
  referencia y se anota para revisarlo.

Es una opción, y está apagada de serie, porque los interiores del mapa
suelen estar incompletos: es mejor pedirlos a propósito.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from app.core.i18n import _
from app.dominio import edicion as ed
from app.dominio import geometria as geo
from app.dominio.geometria import Punto
from app.dominio.modelo import Abertura, Planta
from app.importar import formas
from app.importar.comun import frase_cuenta
from app.importar.osm_conversion import numero

if TYPE_CHECKING:
	from app.importar.osm_conversion import Area, Conversor

log = logging.getLogger(__name__)

TIPOS_INTERIORES = {"room": "habitacion", "corridor": "pasillo", "area": "vestibulo"}
ANCHO_PUERTA = 0.82


def niveles_de(texto: str | None) -> list[int]:
	"""Plantas de una etiqueta ``level``: «0», «1;2», «0-2», «-1», «0.5» (se redondea)."""
	if not texto:
		return []
	niveles: list[int] = []
	for parte in texto.replace(",", ";").split(";"):
		parte = parte.strip()
		if not parte:
			continue
		try:
			if "-" in parte[1:]:
				corte = parte.index("-", 1)
				inicio, fin = round(float(parte[:corte])), round(float(parte[corte + 1 :]))
				niveles.extend(range(min(inicio, fin), max(inicio, fin) + 1))
			else:
				niveles.append(round(float(parte)))
		except ValueError:
			log.debug("Etiqueta level no numérica: %r", texto)
	return sorted(set(niveles))


def _interiores(conversor: Conversor) -> list[Area]:
	return [area for area in conversor.areas if area.etiquetas.get("indoor") in TIPOS_INTERIORES]


def preparar(conversor: Conversor) -> None:
	"""Marca los edificios que tienen salas en la planta 0: esos no se importan como bloque macizo."""
	salas = [
		formas.punto_interior(area.puntos)
		for area in _interiores(conversor)
		if 0 in (niveles_de(area.etiquetas.get("level")) or [0]) and len(area.puntos) >= 3
	]
	if not salas:
		return
	for area in conversor.areas:
		if area.etiquetas.get("building", "no") == "no" or "indoor" in area.etiquetas:
			continue
		contorno = formas.limpiar_poligono(area.puntos)
		if len(contorno) >= 3 and any(geo.punto_en_poligono(punto, contorno) for punto in salas):
			conversor.edificios_con_interior.append(area)


def _planta(conversor: Conversor, nivel: int) -> Planta:
	"""Planta de ese nivel: la de calle para el 0, y las demás se crean según hacen falta."""
	if nivel == 0:
		return conversor.planta
	existente = conversor.entorno.planta_de_nivel(nivel)
	if existente is not None:
		return existente
	return ed.crear_planta(conversor.entorno, nivel=nivel)


def _puerta(conversor: Conversor, planta: Planta, contorno: list[Punto], nodo: int) -> bool:
	"""Abre en la sala la puerta que el mapa pone en ese nodo de su contorno."""
	etiquetas = conversor.etiquetas_nodo[nodo]
	punto = conversor.xy[nodo]
	indice, distancia = formas.lado_mas_cercano(contorno, punto)
	if distancia > 0.5:
		return False
	a, b = geo.lados(contorno)[indice]
	ancho = min(max(numero(etiquetas.get("width")) or ANCHO_PUERTA, 0.6), 3.0)
	tramo = formas.tramo_centrado(a, b, punto, ancho)
	if tramo is None or conversor.pisa_abertura(planta, tramo):
		return False
	hueco = etiquetas.get("door") == "no"
	entrada = etiquetas.get("entrance", "no") != "no"
	hoja = "ninguna" if hueco else "batiente"
	if not hueco and etiquetas.get("automatic_door", "no") != "no":
		hoja = "automatica"
	elif not hueco and etiquetas.get("door") == "sliding":
		hoja = "corredera"
	abertura = Abertura(
		nombre=etiquetas.get("name", ""),
		descripcion="" if hueco else _("El mapa no dice si suele estar abierta."),
		tipo="hueco" if hueco else ("portal" if entrada and planta.exterior else "puerta"),
		a=tramo[0],
		b=tramo[1],
		estado="abierta" if hueco else "cerrada",
		hoja=hoja,
		material="madera",
		es_salida=entrada,
	)
	if not abertura.nombre:
		unidos = ed.espacios_de_abertura(planta, abertura)
		nombres = [e.nombre for e in unidos if not e.datos.get("terreno_base")]
		base = _("Hueco") if hueco else (_("Portal") if abertura.tipo == "portal" else _("Puerta"))
		abertura.nombre = (
			_("{tipo} entre {a} y {b}").format(tipo=base, a=nombres[0], b=nombres[1])
			if len(nombres) >= 2
			else (_("{tipo} de {a}").format(tipo=base, a=nombres[0]) if nombres else base)
		)
	abertura.id = conversor.entorno.id_para(abertura)
	planta.aberturas.append(abertura)
	conversor.nodos_usados.add(nodo)
	return True


def importar(conversor: Conversor) -> None:
	"""Crea las salas, sus puertas y los ascensores y escaleras que se puedan conectar con seguridad."""
	informe = conversor.informe
	salas = 0
	puertas = 0
	plantas_tocadas: set[int] = set()
	pendientes_de_puerta: list[tuple[Planta, list[Punto], list[int]]] = []
	for area in _interiores(conversor):
		etiquetas = area.etiquetas
		contorno = formas.limpiar_poligono(area.puntos)
		if not formas.poligono_valido(contorno, 0.5) or not conversor.dentro(geo.centroide(contorno)):
			continue
		clase = etiquetas["indoor"]
		tipo = "escalera" if etiquetas.get("stairs") == "yes" or etiquetas.get("room") == "stairs" else TIPOS_INTERIORES[clase]
		nombre_base = etiquetas.get("name") or etiquetas.get("ref") or ""
		for nivel in niveles_de(etiquetas.get("level") or etiquetas.get("repeat_on")) or [0]:
			planta = _planta(conversor, nivel)
			nombre = nombre_base or conversor.nombre_unico(
				{"habitacion": _("Sala"), "pasillo": _("Pasillo"), "vestibulo": _("Zona interior"), "escalera": _("Hueco de escalera")}[
					tipo
				]
			)
			espacio = conversor.espacio(
				nombre,
				contorno,
				planta,
				tipo=tipo,
				cerrado=clase != "area",
				descripcion="" if nombre_base else _("Nombre: el mapa no lo dice."),
				datos={"osm": area.osm, "nivel_osm": etiquetas.get("level", "")},
			)
			if espacio is None:
				continue
			salas += 1
			plantas_tocadas.add(nivel)
			pendientes_de_puerta.append((planta, list(espacio.contorno), area.ids))
	for planta, contorno, ids in pendientes_de_puerta:
		for nodo in ids:
			etiquetas_nodo = conversor.etiquetas_nodo.get(nodo, {})
			if nodo in conversor.xy and ("door" in etiquetas_nodo or etiquetas_nodo.get("entrance", "no") != "no"):
				niveles_puerta = niveles_de(etiquetas_nodo.get("level"))
				if niveles_puerta and planta.nivel not in niveles_puerta:
					continue
				if _puerta(conversor, planta, contorno, nodo):
					puertas += 1
	if not salas:
		informe.anotar_falta(_("El mapa no tiene interiores de edificios en esta zona."))
		return
	ascensores = _ascensores(conversor)
	informe.contar("salas", salas)
	informe.contar("puertas_interiores", puertas)
	informe.anotar_importado(
		_("{salas} interiores en {plantas}, con {puertas}.").format(
			salas=frase_cuenta(salas, "{n} sala", "{n} salas"),
			plantas=frase_cuenta(len(plantas_tocadas), "{n} planta", "{n} plantas"),
			puertas=frase_cuenta(puertas, "{n} puerta", "{n} puertas"),
		)
	)
	if ascensores:
		informe.anotar_importado(
			_("{ascensores} entre plantas.").format(ascensores=frase_cuenta(ascensores, "{n} ascensor", "{n} ascensores"))
		)
	if conversor.edificios_con_interior:
		informe.anotar_deducido(
			_(
				"Los edificios con salas en la planta baja no se han puesto como bloques macizos: sus paredes son las de sus salas. Revise que el contorno queda cerrado."
			)
		)
	informe.anotar_revisar(
		_(
			"Los interiores del mapa suelen estar incompletos: compruebe las puertas, añada las que falten y conecte las plantas con sus escaleras."
		)
	)


def _ascensores(conversor: Conversor) -> int:
	"""Convierte en conector cada ascensor cuyas paradas caen dentro de una sala; el resto, referencia."""
	creados = 0
	for nodo, etiquetas in conversor.etiquetas_nodo.items():
		if etiquetas.get("highway") != "elevator" or nodo in conversor.nodos_usados:
			continue
		punto = conversor.xy[nodo]
		if not conversor.dentro(punto):
			continue
		plantas: list[Planta] = []
		for nivel in niveles_de(etiquetas.get("level") or etiquetas.get("repeat_on")):
			planta = conversor.planta if nivel == 0 else conversor.entorno.planta_de_nivel(nivel)
			if planta is not None and planta.espacio_en(punto[0], punto[1], incluir_macizos=False) is not None:
				plantas.append(planta)
		conversor.nodos_usados.add(nodo)
		nombre = etiquetas.get("name") or conversor.nombre_unico(_("Ascensor"))
		if len(plantas) >= 2:
			ed.crear_ascensor(
				conversor.entorno,
				plantas,
				punto,
				0.0,
				nombre=nombre,
				descripcion=_("El mapa no dice hacia dónde abre la puerta ni si avisa de la planta con voz."),
			)
			creados += 1
			conversor.informe.anotar_revisar(
				_("En los ascensores: coloque el punto delante de la puerta y el rumbo de entrada, que el mapa no dice.")
			)
		else:
			ed.anadir_referencia(
				conversor.entorno,
				conversor.planta,
				nombre,
				punto[0],
				punto[1],
				tipo="punto",
				descripcion=_("Ascensor del mapa que no se ha podido conectar entre plantas."),
			)
			conversor.informe.anotar_aviso(_("Un ascensor del mapa no se ha podido conectar entre plantas y se ha dejado como referencia."))
	return creados
