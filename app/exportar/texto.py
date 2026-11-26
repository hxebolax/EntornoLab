"""Descripción completa de un entorno en texto, Markdown y HTML accesible.

Es la manera de «tener el plano» sin verlo: un documento ordenado por
plantas que se puede leer con el lector de pantalla saltando de encabezado en
encabezado, pasar a una línea braille o imprimir en braille.

Amplía ``edicion.describir_entorno``. En los interiores va espacio por
espacio (medidas, vecinos, puertas, objetos y referencias). En los
exteriores agrupa por lo que importa al andar por la calle: calles con sus
aceras, cruces con su forma, pasos de peatones con su ficha, paradas,
edificios con sus portales, zonas, obstáculos y referencias.

Reglas del documento:

- cada línea es una frase completa, que se entiende sola;
- lo que el mapa no dice figura como «el mapa no lo dice»;
- si el entorno viene de OpenStreetMap, lleva siempre la atribución y la
  licencia, que la ODbL obliga a conservar.
"""

from __future__ import annotations

import html
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path

from app.core.i18n import N_, _, _n, idioma_actual, separador_decimal
from app.dominio import edicion as ed
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import TIPOS_REFERENCIA, Entorno, Espacio, Planta, nombre_visible
from app.exportar.fichas import ficha_escalera, ficha_paso
from app.importar.georef import texto_atribucion

log = logging.getLogger(__name__)

FORMATOS = ("txt", "md", "html")
# Paredes sueltas que se detallan una a una; si hay más, solo se cuentan.
MAX_PAREDES_DETALLADAS = 40

_FORMAS_CRUCE = {
	"t": N_("en T"),
	"y": N_("en Y"),
	"cruz": N_("en cruz"),
	"aspa": N_("en aspa"),
	"desalineado": N_("de cuatro calles desalineado"),
	"complejo": N_("complejo"),
	"rotonda": N_("rotonda"),
}


@dataclass
class Bloque:
	"""Un apartado del documento: encabezado, párrafos y una lista de frases."""

	titulo: str
	nivel: int = 2
	parrafos: list[str] = field(default_factory=list)
	lista: list[str] = field(default_factory=list)


def _m(valor: float) -> str:
	texto = f"{valor:.2f}".rstrip("0").rstrip(".")
	return (texto or "0").replace(".", separador_decimal())


def _bloque_procedencia(entorno: Entorno) -> Bloque | None:
	procedencia = entorno.procedencia if isinstance(entorno.procedencia, dict) else {}
	lineas: list[str] = []
	for clave, plantilla in (
		("fuente", _("Fuente: {valor}.")),
		("fecha", _("Fecha de la importación o del dibujo: {valor}.")),
		("fecha_datos", _("Fecha de los datos del mapa: {valor}.")),
		("escala", _("Escala: {valor}.")),
		("licencia", _("Licencia: {valor}.")),
		("atribucion", _("Atribución obligatoria: {valor}.")),
		("notas", _("Notas: {valor}")),
	):
		valor = str(procedencia.get(clave) or "").strip()
		if valor:
			lineas.append(plantilla.format(valor=valor))
	if isinstance(entorno.georef, dict) and "lat0" in entorno.georef and "lon0" in entorno.georef:
		lineas.append(
			_("Georreferencia: el punto (0; 0) del entorno está en la latitud {lat} y la longitud {lon}.").format(
				lat=str(entorno.georef["lat0"]).replace(".", separador_decimal()), lon=str(entorno.georef["lon0"]).replace(".", separador_decimal())
			)
		)
	if not lineas:
		return None
	return Bloque(_("Procedencia"), 2, lista=lineas)


def _contenido_de(entorno: Entorno, planta: Planta, espacio: Espacio, catalogo: Catalogo | None) -> list[str]:
	"""Frases de lo que hay en un espacio: vecinos, puertas, objetos, sonidos y referencias."""
	lineas: list[str] = []
	if not espacio.macizo:
		cercanos = [(otro, lado) for otro, lado in ed.vecinos(planta, espacio) if not otro.datos.get("terreno_base")]
		if cercanos:
			lineas.append(
				_("Vecinos: {lista}.").format(
					lista=", ".join(_("{nombre} al {lado}").format(nombre=o.nombre, lado=_(lado)) for o, lado in cercanos)
				)
			)
	if espacio.cerrado or espacio.macizo:
		for abertura in ed.aberturas_de(planta, espacio):
			lineas.append(ed.describir_elemento(entorno, abertura))
	if espacio.macizo:
		return lineas
	for nombre_lista in ("objetos", "fuentes", "referencias"):
		for hijo in getattr(planta, nombre_lista):
			if planta.espacio_en(hijo.x, hijo.y) is espacio:
				lineas.append(ed.describir_elemento(entorno, hijo, catalogo))
	return lineas


def _bloque_espacio(entorno: Entorno, planta: Planta, espacio: Espacio, catalogo: Catalogo | None, nivel: int) -> Bloque:
	return Bloque(
		espacio.nombre or espacio.id,
		nivel,
		[ed.describir_elemento(entorno, espacio, catalogo)],
		_contenido_de(entorno, planta, espacio, catalogo),
	)


def _frase_acera(acera: Espacio) -> str:
	partes = [acera.nombre]
	ancho = acera.datos.get("ancho")
	if isinstance(ancho, (int, float)):
		partes.append(_("de {metros} metros de ancho").format(metros=_m(float(ancho))))
	origen = acera.datos.get("origen")
	if origen == "deducida":
		partes.append(_("DEDUCIDA: el mapa no dice si existe"))
	elif origen == "mapa":
		partes.append(_("figura en el mapa") if acera.datos.get("ancho_segun_mapa") else _("figura en el mapa, pero su anchura no"))
	return ", ".join(partes) + "."


def _bloques_exterior(entorno: Entorno, planta: Planta, catalogo: Catalogo | None) -> list[Bloque]:
	"""Los apartados de una planta de calle, por lo que importa al andar por ella."""
	bloques: list[Bloque] = []
	usados: set[str] = set()
	# Calles con sus aceras.
	calles = Bloque(_("Calles"), 3)
	for via in planta.vias:
		frase = ed.describir_elemento(entorno, via)
		if via.descripcion:
			frase += " " + via.descripcion
		calles.lista.append(frase)
		aceras = [e for e in planta.espacios if e.tipo == "acera" and e.datos.get("via") == via.id]
		if aceras:
			for acera in aceras:
				calles.lista.append("    " + _frase_acera(acera))
				usados.add(acera.id)
		else:
			calles.lista.append("    " + _("Sin aceras en el entorno."))
	for espacio in planta.espacios:
		if espacio.tipo == "calzada" and not espacio.datos.get("cruce"):
			usados.add(espacio.id)
	if calles.lista:
		bloques.append(calles)
	# Cruces.
	cruces = Bloque(_("Cruces"), 3)
	for espacio in planta.espacios:
		if espacio.tipo == "calzada" and espacio.datos.get("cruce"):
			usados.add(espacio.id)
			forma = str(espacio.datos.get("forma") or "")
			frase = espacio.nombre + "."
			if forma in _FORMAS_CRUCE and forma != "rotonda":
				frase = _("{nombre}: cruce {forma}.").format(nombre=espacio.nombre, forma=_(_FORMAS_CRUCE[forma]))
			if espacio.descripcion:
				frase += " " + espacio.descripcion
			cruces.lista.append(frase)
	if cruces.lista:
		bloques.append(cruces)
	# Pasos de peatones, cada uno con su ficha.
	pasos = [e for e in planta.espacios if e.tipo == "paso_peatones"]
	if pasos:
		bloques.append(
			Bloque(
				_("Pasos de peatones"), 3, [_n("Hay {n} paso de peatones.", "Hay {n} pasos de peatones.", len(pasos)).format(n=len(pasos))]
			)
		)
	for paso in pasos:
		usados.add(paso.id)
		lineas = ficha_paso(paso)
		if paso.descripcion and not paso.datos.get("descripcion_automatica"):
			lineas.append(paso.descripcion)
		bloques.append(Bloque(paso.nombre, 4, lista=lineas))
	# Paradas.
	paradas = [r for r in planta.referencias if r.tipo == "parada"]
	if paradas:
		bloques.append(Bloque(_("Paradas de transporte"), 3, lista=[ed.describir_elemento(entorno, r) for r in paradas]))
	# Edificios y portales.
	edificios = Bloque(_("Edificios y portales"), 3)
	for espacio in planta.espacios:
		if espacio.macizo:
			usados.add(espacio.id)
			edificios.lista.append(ed.describir_elemento(entorno, espacio, catalogo))
			edificios.lista.extend("    " + linea for linea in _contenido_de(entorno, planta, espacio, catalogo))
	if edificios.lista:
		bloques.append(edificios)
	# Interiores a pie de calle (un vestíbulo al que se entra andando).
	interiores = [e for e in planta.espacios if e.cerrado and not e.macizo]
	if interiores:
		bloques.append(Bloque(_("Interiores a pie de calle"), 3))
		for espacio in interiores:
			usados.add(espacio.id)
			bloques.append(_bloque_espacio(entorno, planta, espacio, catalogo, 4))
	# El resto de zonas: plazas, parques, senderos, escaleras.
	zonas = Bloque(_("Plazas, parques, caminos y escaleras"), 3)
	for espacio in planta.espacios:
		if espacio.id in usados or espacio.datos.get("terreno_base"):
			continue
		frase = ed.describir_elemento(entorno, espacio, catalogo)
		if espacio.datos.get("descripcion_automatica") and espacio.descripcion:
			# La descripción automática repite la ficha, que va justo debajo.
			frase = frase.replace(" " + espacio.descripcion, "")
		zonas.lista.append(frase)
		if espacio.tipo == "escalera" or espacio.datos.get("rampa"):
			zonas.lista.extend("    " + linea for linea in ficha_escalera(espacio))
	if zonas.lista:
		bloques.append(zonas)
	if planta.objetos:
		bloques.append(Bloque(_("Obstáculos y mobiliario"), 3, lista=[ed.describir_elemento(entorno, o, catalogo) for o in planta.objetos]))
	otras = [r for r in planta.referencias if r.tipo != "parada"]
	if otras:
		otras.sort(key=lambda r: (nombre_visible(TIPOS_REFERENCIA, r.tipo), r.nombre))
		bloques.append(Bloque(_("Referencias, semáforos y comercios"), 3, lista=[ed.describir_elemento(entorno, r) for r in otras]))
	if planta.fuentes:
		bloques.append(Bloque(_("Fuentes de sonido"), 3, lista=[ed.describir_elemento(entorno, f) for f in planta.fuentes]))
	return bloques


def _bloque_paredes(entorno: Entorno, planta: Planta) -> Bloque | None:
	if not planta.paredes:
		return None
	bloque = Bloque(_("Muros, vallas y paredes sueltas"), 3)
	total = sum(geo.distancia(p.a, p.b) for p in planta.paredes)
	bloque.parrafos.append(
		_n("Hay {n} tramo, que suma {metros} metros.", "Hay {n} tramos, que suman {metros} metros.", len(planta.paredes)).format(
			n=len(planta.paredes), metros=_m(round(total, 1))
		)
	)
	if len(planta.paredes) <= MAX_PAREDES_DETALLADAS:
		bloque.lista = [ed.describir_elemento(entorno, pared) for pared in planta.paredes]
	return bloque


def estructura(entorno: Entorno, catalogo: Catalogo | None = None) -> list[Bloque]:
	"""El documento como lista de apartados, antes de darle formato.

	Es la base común de los tres formatos; quien quiera otro (un DOCX, una
	página de la ayuda) puede partir de aquí.
	"""
	bloques: list[Bloque] = []
	portada = Bloque(entorno.nombre or _("Entorno sin nombre"), 1)
	if entorno.descripcion:
		portada.parrafos.append(entorno.descripcion)
	if entorno.autor:
		portada.parrafos.append(_("Autor: {autor}.").format(autor=entorno.autor))
	portada.parrafos.append(
		_n("Tiene {n} planta", "Tiene {n} plantas", len(entorno.plantas)).format(n=len(entorno.plantas))
		+ _n(" y {n} conector entre plantas.", " y {n} conectores entre plantas.", len(entorno.conectores)).format(
			n=len(entorno.conectores)
		)
	)
	planta_inicio = entorno.planta(entorno.inicio.planta)
	if planta_inicio is not None:
		espacio_inicio = planta_inicio.espacio_en(entorno.inicio.x, entorno.inicio.y)
		portada.parrafos.append(
			_("Inicio: en {donde}, planta {planta}, mirando al {punto}.").format(
				donde=espacio_inicio.nombre if espacio_inicio else _("un punto fuera de todo espacio"),
				planta=planta_inicio.nombre,
				punto=geo.punto_cardinal(entorno.inicio.rumbo),
			)
		)
	portada.parrafos.append(_("Las medidas van en metros. El norte es la parte de arriba del plano."))
	bloques.append(portada)
	procedencia = _bloque_procedencia(entorno)
	if procedencia is not None:
		bloques.append(procedencia)
	for planta in entorno.plantas:
		bloques.append(Bloque(_("Planta: {nombre}").format(nombre=planta.nombre or planta.id), 2, [ed.describir_elemento(entorno, planta)]))
		if planta.exterior:
			bloques.extend(_bloques_exterior(entorno, planta, catalogo))
		else:
			for espacio in planta.espacios:
				bloques.append(_bloque_espacio(entorno, planta, espacio, catalogo, 3))
			sueltos = [
				h for lista in (planta.objetos, planta.fuentes, planta.referencias) for h in lista if planta.espacio_en(h.x, h.y) is None
			]
			if sueltos:
				bloques.append(Bloque(_("Fuera de todo espacio"), 3, lista=[ed.describir_elemento(entorno, h, catalogo) for h in sueltos]))
		paredes = _bloque_paredes(entorno, planta)
		if paredes is not None:
			bloques.append(paredes)
	if entorno.conectores:
		bloques.append(
			Bloque(
				_("Escaleras, rampas y ascensores entre plantas"), 2, lista=[ed.describir_elemento(entorno, c) for c in entorno.conectores]
			)
		)
	atribucion = texto_atribucion(entorno.procedencia)
	if atribucion:
		bloques.append(
			Bloque(
				_("Datos del mapa"),
				2,
				[_("Datos del mapa: {atribucion}. Esta atribución debe conservarse en cualquier copia.").format(atribucion=atribucion)],
			)
		)
	return bloques


def a_texto(entorno: Entorno, catalogo: Catalogo | None = None) -> str:
	"""Descripción en texto llano: encabezados en su línea, una frase por línea."""
	lineas: list[str] = []
	for bloque in estructura(entorno, catalogo):
		if lineas:
			lineas.append("")
		lineas.append(bloque.titulo.upper() if bloque.nivel <= 2 else bloque.titulo)
		lineas.extend(bloque.parrafos)
		lineas.extend(("  " + frase) if not frase.startswith("    ") else frase for frase in bloque.lista)
	return "\n".join(lineas) + "\n"


def a_markdown(entorno: Entorno, catalogo: Catalogo | None = None) -> str:
	"""Descripción en Markdown, con encabezados por los que se puede saltar."""
	lineas: list[str] = []
	for bloque in estructura(entorno, catalogo):
		if lineas:
			lineas.append("")
		lineas.append("#" * bloque.nivel + " " + bloque.titulo)
		for parrafo in bloque.parrafos:
			lineas.append("")
			lineas.append(parrafo)
		if bloque.lista:
			lineas.append("")
		for frase in bloque.lista:
			sangrada = frase.startswith("    ")
			lineas.append(("  - " if sangrada else "- ") + frase.strip())
	return "\n".join(lineas) + "\n"


def a_html(entorno: Entorno, catalogo: Catalogo | None = None) -> str:
	"""Descripción en HTML accesible: idioma declarado, encabezados en orden y listas de verdad.

	No lleva estilos ni código: se lee igual en cualquier navegador con
	cualquier lector de pantalla y se imprime bien.
	"""
	titulo = html.escape(entorno.nombre or _("Entorno sin nombre"))
	partes = [
		"<!DOCTYPE html>",
		f'<html lang="{html.escape(idioma_actual() or "es")}">',
		"<head>",
		'<meta charset="utf-8">',
		'<meta name="viewport" content="width=device-width, initial-scale=1">',
		f"<title>{titulo}</title>",
		"</head>",
		"<body>",
		"<main>",
	]
	for bloque in estructura(entorno, catalogo):
		nivel = max(1, min(6, bloque.nivel))
		partes.append(f"<h{nivel}>{html.escape(bloque.titulo)}</h{nivel}>")
		partes.extend(f"<p>{html.escape(parrafo)}</p>" for parrafo in bloque.parrafos)
		if bloque.lista:
			partes.append("<ul>")
			abierta = False
			for frase in bloque.lista:
				sangrada = frase.startswith("    ")
				if sangrada and not abierta and partes[-1].endswith("</li>"):
					# Sublista dentro del elemento anterior: se reabre su <li>.
					partes[-1] = partes[-1].removesuffix("</li>")
					partes.append("<ul>")
					abierta = True
				elif not sangrada and abierta:
					partes.append("</ul></li>")
					abierta = False
				partes.append(f"<li>{html.escape(frase.strip())}</li>")
			if abierta:
				partes.append("</ul></li>")
			partes.append("</ul>")
	partes.extend(["</main>", "</body>", "</html>"])
	return "\n".join(partes) + "\n"


def describir(entorno: Entorno, formato: str = "txt", catalogo: Catalogo | None = None) -> str:
	"""La descripción en el formato pedido: ``txt``, ``md`` o ``html``."""
	if formato == "txt":
		return a_texto(entorno, catalogo)
	if formato == "md":
		return a_markdown(entorno, catalogo)
	if formato == "html":
		return a_html(entorno, catalogo)
	raise ValueError(_("Formato de descripción desconocido: «{formato}». Formatos: txt, md, html.").format(formato=formato))


def guardar_descripcion(
	entorno: Entorno, ruta: str | os.PathLike[str], formato: str | None = None, catalogo: Catalogo | None = None
) -> Path:
	"""Escribe la descripción en un fichero; el formato sale de la extensión si no se indica."""
	destino = Path(ruta)
	if formato is None:
		formato = {".md": "md", ".markdown": "md", ".html": "html", ".htm": "html"}.get(destino.suffix.lower(), "txt")
	destino.write_text(describir(entorno, formato, catalogo), encoding="utf-8", newline="\n")
	log.info("Descripción del entorno «%s» guardada en %s", entorno.nombre, destino.name)
	return destino
