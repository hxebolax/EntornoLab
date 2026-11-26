"""«Archivo, Exportar»: paquete para el alumno, descripción en texto, planos SVG, GeoJSON y DXF.

Cada exportación pregunta dónde guardar con el cuadro de Windows, hace el
trabajo sin bloquear la interfaz, anuncia cuántos ficheros ha escrito y
dónde, y ofrece abrir la carpeta.

El «paquete para el alumno» no es una copia del fichero del disco (puede
haber cambios sin guardar): se escribe de nuevo con ``guardar_paquete`` a
partir de lo que hay abierto, después de comprobarlo. Si la comprobación
encuentra errores se enseñan y se pregunta, con botones que dicen la
acción, si se exporta de todos modos.

Nada de lo exportado sale del equipo. Los entornos que vienen de
OpenStreetMap llevan su atribución dentro de cada fichero (lo hacen los
módulos de ``app/exportar``).
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

import wx

from app.core import tareas
from app.core.i18n import N_, _, _n
from app.dominio import validacion
from app.dominio.formato import guardar_paquete, identificador_seguro
from app.dominio.modelo import Entorno
from app.exportar import dxf as exportar_dxf
from app.exportar import geojson as exportar_geojson
from app.exportar import svg as exportar_svg
from app.exportar import texto as exportar_texto
from app.ui import espera
from app.ui.accesibilidad.dialogos import DialogoMensaje, mostrar_error, mostrar_mensaje
from app.ui.dialogo_progreso import ejecutar_tarea
from app.ui.esquemas import c
from app.ui.formulario import mostrar_dialogo, pedir_formulario

log = logging.getLogger(__name__)

FORMATOS = ("paquete", "texto", "svg", "tactil", "geojson", "dxf")

TITULOS: dict[str, str] = {
	"paquete": N_("Exportar el paquete para el alumno"),
	"texto": N_("Exportar la descripción en texto"),
	"svg": N_("Exportar el plano SVG visual"),
	"tactil": N_("Exportar el plano táctil"),
	"geojson": N_("Exportar a GeoJSON"),
	"dxf": N_("Exportar a DXF"),
}


def abrir_carpeta(carpeta: Path) -> bool:
	"""Abre una carpeta en el Explorador. False si no se pudo (queda en el registro)."""
	if not hasattr(os, "startfile"):
		return False
	try:
		os.startfile(carpeta)  # noqa: S606 - carpeta elegida por la persona para su exportación
	except OSError:
		log.exception("No se pudo abrir la carpeta %s", carpeta)
		return False
	return True


# ── Comprobación previa del paquete ──────────────────────────────────────────


def avisos_de_paquete(
	entorno: Entorno, actividades: list[dict[str, Any]], catalogo: Any, paso_libre: float, recursos: Any = None
) -> list[Any]:
	"""Avisos del entorno y, si el módulo de actividades existe, de cada actividad del paquete.

	Con ``recursos`` (los del paquete abierto) se comprueba también que el
	audio grabado de cada premio viaja en el paquete.
	"""
	avisos = list(validacion.validar(entorno, catalogo, paso_libre))
	try:
		from app import actividades as modulo_actividades
	except ImportError:
		log.debug("No hay módulo de actividades: el paquete se comprueba solo como entorno.")
		return avisos
	validar_actividad = getattr(modulo_actividades, "validar_actividad", None)
	if not callable(validar_actividad):
		return avisos
	for actividad in actividades:
		try:
			if recursos is None:
				avisos.extend(validar_actividad(actividad, entorno, catalogo))
			else:
				avisos.extend(validar_actividad(actividad, entorno, catalogo, recursos=recursos))
		except Exception:  # noqa: BLE001 - una actividad que no se puede comprobar no impide exportar; se deja constancia
			log.exception("No se pudo comprobar la actividad %s", actividad.get("id"))
	return avisos


def texto_de_avisos(avisos: list[Any]) -> str:
	"""Los avisos en frases, con los errores primero, para leerlos en el diálogo de decisión."""
	errores = [aviso for aviso in avisos if aviso.es_error]
	lineas = [
		_n("La comprobación ha encontrado {n} error.", "La comprobación ha encontrado {n} errores.", len(errores)).format(n=len(errores)),
		_(
			"Un paquete con errores puede dejar al alumno encerrado o sin poder terminar. Lo recomendable es corregirlos antes (Herramientas, Comprobar el entorno)."
		),
		"",
	]
	for aviso in errores:
		lineas.append(_("Error: {mensaje} {sugerencia}").format(mensaje=aviso.mensaje, sugerencia=aviso.sugerencia).strip())
	return "\n".join(lineas)


def crear_pregunta_de_errores(padre: wx.Window | None, avisos: list[Any]) -> DialogoMensaje:
	"""Diálogo que enseña los errores y pregunta qué hacer; ``ids_opciones[0]`` es «Exportar de todos modos»."""
	return DialogoMensaje(
		padre,
		texto_de_avisos(avisos),
		_("El entorno tiene errores"),
		opciones=[_("&Exportar de todos modos"), _("&No exportar")],
		icono=wx.ICON_WARNING,
	)


# ── Trabajo de cada formato (sin wx: se ejecuta en segundo plano) ────────────


def escribir_paquete(entorno: Entorno, actividades: list[dict[str, Any]], recursos: dict[str, bytes], destino: Path) -> list[Path]:
	"""Escribe el ``.elab`` para el alumno con su entorno, sus actividades y sus recursos."""
	guardar_paquete(destino, entorno, actividades, recursos or None)
	return [destino]


def escribir(formato: str, entorno: Entorno, destino: Path, catalogo: Any = None, pagina: str = "A4") -> list[Path]:
	"""Escribe la exportación de ``formato`` en ``destino`` (fichero para «texto», carpeta para los demás)."""
	if formato == "texto":
		return [exportar_texto.guardar_descripcion(entorno, destino, catalogo=catalogo)]
	destino.mkdir(parents=True, exist_ok=True)
	if formato == "svg":
		return list(exportar_svg.guardar_planos(entorno, destino, "visual", pagina, catalogo))
	if formato == "tactil":
		return list(exportar_svg.guardar_planos(entorno, destino, "tactil", pagina, catalogo))
	if formato == "geojson":
		return list(exportar_geojson.guardar_geojson(entorno, destino, catalogo))
	if formato == "dxf":
		return list(exportar_dxf.guardar_dxf(entorno, destino, catalogo))
	raise ValueError(f"Formato de exportación desconocido: {formato}")


# ── Preguntar el destino ─────────────────────────────────────────────────────


def _carpeta_inicial(contexto: Any) -> str:
	return str(contexto.ruta_paquete.parent) if contexto.ruta_paquete is not None else ""


def _nombre_base(contexto: Any) -> str:
	return identificador_seguro(contexto.entorno.nombre or "entorno", "entorno")


def pedir_fichero(contexto: Any, titulo: str, comodin: str, nombre: str) -> Path | None:
	"""Cuadro «Guardar como» de Windows. ``None`` si se cancela."""
	estilo = wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT
	with wx.FileDialog(contexto.ventana, titulo, _carpeta_inicial(contexto), nombre, comodin, estilo) as dialogo:
		if dialogo.ShowModal() != wx.ID_OK:
			return None
		return Path(dialogo.GetPath())


def pedir_carpeta(contexto: Any, titulo: str) -> Path | None:
	"""Cuadro de elegir carpeta de Windows. ``None`` si se cancela."""
	with wx.DirDialog(contexto.ventana, titulo, _carpeta_inicial(contexto), style=wx.DD_DEFAULT_STYLE) as dialogo:
		if dialogo.ShowModal() != wx.ID_OK:
			return None
		return Path(dialogo.GetPath())


def campos_plano() -> list[Any]:
	"""Formulario de exportar planos: carpeta y tamaño de la hoja."""
	return [
		c(
			"carpeta",
			N_("Carpeta de destino"),
			"ruta_carpeta",
			N_("Carpeta donde se guarda un plano por cada planta, con su leyenda."),
			obligatorio=True,
		),
		c(
			"pagina",
			N_("Tamaño de la hoja"),
			"opcion",
			N_("Tamaño del papel. El plano se dibuja a la mayor escala normalizada que quepa; imprímalo al 100 %."),
			opciones=[("A4", "A4"), ("A3", "A3")],
			defecto="A4",
		),
	]


# ── Final común ──────────────────────────────────────────────────────────────


def crear_aviso_final(padre: wx.Window | None, mensaje: str, titulo: str) -> DialogoMensaje:
	"""Diálogo de fin de exportación; ``ids_opciones[0]`` es «Abrir la carpeta»."""
	return DialogoMensaje(padre, mensaje, titulo, opciones=[_("&Abrir la carpeta"), _("&Cerrar")], icono=wx.ICON_INFORMATION)


def _terminar(contexto: Any, titulo: str, ficheros: list[Path], carpeta: Path) -> bool:
	"""Anuncia el resultado y ofrece abrir la carpeta. False si no se escribió nada."""
	if not ficheros:
		mostrar_mensaje(contexto.ventana, _("No se ha exportado nada: el entorno no tiene ninguna planta con contenido."), titulo)
		return False
	mensaje = _n("Exportado {n} fichero en {carpeta}.", "Exportados {n} ficheros en {carpeta}.", len(ficheros)).format(
		n=len(ficheros), carpeta=carpeta
	)
	contexto.anunciar(mensaje)
	dialogo = crear_aviso_final(contexto.ventana, mensaje, titulo)
	abrir = dialogo.ids_opciones[0]
	if mostrar_dialogo(dialogo) == abrir:
		abrir_carpeta(carpeta)
	return True


def _hacer(contexto: Any, titulo: str, trabajo: Callable[[], list[Path]]) -> list[Path] | None:
	"""Ejecuta el trabajo de exportar sin bloquear la interfaz. ``None`` si falla o se cancela (ya explicado)."""
	try:
		return ejecutar_tarea(
			contexto.ventana, titulo, lambda _tarea: trabajo(), contexto.tareas, contexto.configuracion, _("Exportando...")
		)
	except tareas.TareaCancelada:
		contexto.anunciar(_("Exportación cancelada."))
	except (OSError, ValueError) as error:
		log.exception("No se pudo exportar")
		mostrar_error(contexto.ventana, _("No se pudo exportar: {error}").format(error=error), titulo)
	except Exception as error:  # noqa: BLE001 - un fallo del exportador se explica; no debe tirar el Estudio
		log.exception("Fallo inesperado al exportar")
		mostrar_error(contexto.ventana, _("No se pudo exportar: {error}. Los detalles están en el registro.").format(error=error), titulo)
	return None


def exportar(contexto: Any, formato: str) -> bool:
	"""Exporta el entorno abierto en ``formato``. True si se escribió algún fichero."""
	if formato not in FORMATOS:
		raise ValueError(f"Formato de exportación desconocido: {formato}")
	titulo = _(TITULOS[formato])
	if contexto.entorno is None:
		mostrar_mensaje(contexto.ventana, _("No hay ningún entorno abierto que exportar."), titulo)
		return False
	# El trabajo en segundo plano usa una COPIA: el entorno abierto solo se toca en el hilo de la interfaz.
	copia = Entorno.de_dict(contexto.entorno.a_dict())
	catalogo = contexto.catalogo
	if formato == "paquete":
		try:
			# Comprobar un barrio importado tarda segundos: con un entorno grande va a segundo plano con progreso.
			avisos = espera.hacer(
				contexto,
				titulo,
				lambda _tarea: avisos_de_paquete(
					copia, list(contexto.actividades), catalogo, contexto.paso_libre(), recursos=getattr(contexto, "recursos", None)
				),
				_("Comprobando el entorno antes de exportarlo"),
			)
		except tareas.TareaCancelada:
			contexto.anunciar(_("Exportación cancelada."))
			return False
		if any(aviso.es_error for aviso in avisos):
			pregunta = crear_pregunta_de_errores(contexto.ventana, avisos)
			seguir = pregunta.ids_opciones[0]
			if mostrar_dialogo(pregunta) != seguir:
				return False
		destino = pedir_fichero(contexto, titulo, _("Entornos de EntornoLab (*.elab)|*.elab"), f"{_nombre_base(contexto)}-alumno.elab")
		if destino is None:
			return False
		if destino.suffix.lower() != ".elab":
			destino = destino.with_name(destino.name + ".elab")
		if contexto.ruta_paquete is not None and destino.resolve() == Path(contexto.ruta_paquete).resolve():
			mostrar_error(
				contexto.ventana,
				_("Elija otro nombre: ese es el fichero del entorno que tiene abierto. Para guardarlo use Archivo, Guardar."),
				titulo,
			)
			return False
		actividades = [dict(actividad) for actividad in contexto.actividades]
		recursos = dict(contexto.recursos)
		ficheros = _hacer(contexto, titulo, lambda: escribir_paquete(copia, actividades, recursos, destino))
		return ficheros is not None and _terminar(contexto, titulo, ficheros, destino.parent)
	if formato == "texto":
		comodin = _("Texto (*.txt)|*.txt|Markdown (*.md)|*.md|Página web accesible (*.html)|*.html")
		destino = pedir_fichero(contexto, titulo, comodin, f"{_nombre_base(contexto)}.txt")
		if destino is None:
			return False
		if destino.suffix.lower() not in (".txt", ".md", ".html"):
			destino = destino.with_name(destino.name + ".txt")
		ficheros = _hacer(contexto, titulo, lambda: escribir("texto", copia, destino, catalogo))
		return ficheros is not None and _terminar(contexto, titulo, ficheros, destino.parent)
	pagina = "A4"
	if formato in ("svg", "tactil"):
		valores = pedir_formulario(contexto.ventana, titulo, campos_plano(), {"carpeta": _carpeta_inicial(contexto)})
		if valores is None:
			return False
		carpeta, pagina = Path(valores["carpeta"]), valores["pagina"]
	else:
		elegida = pedir_carpeta(contexto, titulo)
		if elegida is None:
			return False
		carpeta = elegida
	ficheros = _hacer(contexto, titulo, lambda: escribir(formato, copia, carpeta, catalogo, pagina))
	return ficheros is not None and _terminar(contexto, titulo, ficheros, carpeta)
