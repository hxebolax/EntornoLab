"""Elegir entorno y actividad, y «Continuar la última actividad».

Dos pasos cortos: primero el lugar (los paquetes ``.elab`` del profesional y
los de ejemplo, cada uno con su descripción en la ayuda) y después qué hacer
en él: una de sus actividades o la exploración libre. Un paquete dañado no
rompe nada: se dice qué pasa, con palabras claras, y se sigue en el menú.

Lista de trabajo: lo que el profesional ha asignado al alumno en su ficha
llega por la sala y queda en su perfil. Sale lo primero en «Elegir entorno»
(«Lo que te ha puesto tu profesor») y, dentro de un entorno, sus actividades
asignadas van antes que las demás. «Continuar», si el alumno aún no ha jugado
nada, empieza la primera asignada.
"""

from __future__ import annotations

import logging
import zipfile
from collections.abc import Callable
from pathlib import Path
from typing import TYPE_CHECKING, Any

from app.core.i18n import _, _n
from app.dominio.formato import ErrorFormato, leer_manifiesto
from app.reproductor import entornos, puente_actividades
from app.reproductor.menus import SONIDO_ERROR, Menu, Opcion

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)


def _decir_error(app: Aplicacion, mensaje: str) -> None:
	app.sonar(SONIDO_ERROR)
	app.decir(mensaje, True, "aviso")


def abrir_entornos(app: Aplicacion) -> Menu | None:
	"""Abre la lista de entornos disponibles."""
	extra: Path | None = getattr(app.opciones, "paquete", None)
	descripciones: dict[Path, str] = {}

	def descripcion(ficha: entornos.FichaEntorno) -> Callable[[], str]:
		def texto() -> str:
			# Se abre el paquete solo cuando se pide su descripción, y una vez.
			if ficha.ruta not in descripciones:
				try:
					descripciones[ficha.ruta] = entornos.describir(entornos.abrir(ficha.ruta))
				except entornos.ErrorEntorno as error:
					descripciones[ficha.ruta] = str(error)
			return descripciones[ficha.ruta]

		return texto

	def abrir(ficha: entornos.FichaEntorno) -> Callable[[], None]:
		def hacer() -> None:
			try:
				paquete = entornos.abrir(ficha.ruta)
			except entornos.ErrorEntorno as error:
				_decir_error(app, str(error))
				return
			abrir_actividades(app, paquete)

		return hacer

	def lista() -> list[Opcion]:
		opciones: list[Opcion] = []
		asignadas = app.perfil.lista_trabajo if app.perfil is not None else []
		if asignadas:
			opciones.append(
				Opcion(
					_("Lo que te ha puesto tu profesor"),
					lambda: abrir_trabajo(app),
					ayuda=_n("Tu profesor te ha puesto {n} actividad.", "Tu profesor te ha puesto {n} actividades.", len(asignadas)).format(
						n=len(asignadas)
					),
				)
			)
		for ficha in entornos.listar(app.config, extra):
			texto = ficha.nombre
			if ficha.origen == entornos.ORIGEN_EJEMPLO:
				texto = _("{nombre}, de ejemplo").format(nombre=ficha.nombre)
			if not ficha.valido:
				texto = _("{nombre}, no se puede abrir").format(nombre=ficha.nombre)
			opciones.append(Opcion(texto, abrir(ficha), ayuda=descripcion(ficha)))
		if not opciones:
			opciones.append(
				Opcion(
					_("No hay ningún entorno. Pide a tu profesor que te dé uno."),
					ayuda=_("Los entornos se guardan en la carpeta data, entornos."),
				)
			)
		return opciones

	menu = Menu(app, _("Elegir entorno"), lista, intro=_("Con la ayuda oyes la descripción de cada uno"))
	app.abrir(menu)
	return menu


def nombre_actividad(datos: dict[str, Any]) -> str:
	"""Nombre visible de una actividad, con su modo si no es un juego."""
	nombre = str(datos.get("nombre") or datos.get("id") or _("Actividad sin nombre"))
	modo = str(datos.get("modo") or "juego")
	if modo == "examen":
		return _("{nombre}, examen").format(nombre=nombre)
	if modo == "practica":
		return _("{nombre}, práctica").format(nombre=nombre)
	return nombre


def abrir_actividades(app: Aplicacion, paquete: Any) -> Menu:
	"""Abre las actividades de un entorno ya cargado, con la exploración libre al final."""

	def jugar(datos: dict[str, Any] | None) -> Callable[[], None]:
		def hacer() -> None:
			app.empezar_partida(paquete, datos)

		return hacer

	def lista() -> list[Opcion]:
		asignadas = _asignadas_en(app, str(paquete.entorno.id))
		actividades = [datos for datos in paquete.actividades if isinstance(datos, dict)]
		# Las que ha puesto el profesor, primero (en el orden del entorno); después las demás.
		actividades.sort(key=lambda datos: str(datos.get("id") or "") not in asignadas)
		opciones = [
			Opcion(
				_("{nombre}, te la ha puesto tu profesor").format(nombre=nombre_actividad(datos))
				if str(datos.get("id") or "") in asignadas
				else nombre_actividad(datos),
				jugar(datos),
				ayuda=(lambda d=datos: puente_actividades.describir(d, paquete.entorno)),
			)
			for datos in actividades
		]
		opciones.append(
			Opcion(
				_("Exploración libre"),
				jugar(None),
				ayuda=_("Recorre el lugar a tu aire, sin objetivos ni tiempo, para conocerlo."),
			)
		)
		return opciones

	menu = Menu(app, paquete.entorno.nombre or _("Entorno"), lista, intro=entornos.describir(paquete))
	app.abrir(menu)
	return menu


def _asignadas_en(app: Aplicacion, entorno_id: str) -> set[str]:
	"""Ids de las actividades de ese entorno que el profesional ha puesto al alumno."""
	if app.perfil is None:
		return set()
	return {
		str(entrada.get("actividad_id") or "") for entrada in app.perfil.lista_trabajo if str(entrada.get("entorno_id") or "") == entorno_id
	}


def buscar_paquete(app: Aplicacion, entrada: dict[str, Any]) -> Path | None:
	"""El ``.elab`` de este equipo con el entorno de una actividad asignada: por su id y, si no, por el nombre del fichero."""
	entorno_id = str(entrada.get("entorno_id") or "")
	nombre = str(entrada.get("paquete") or "")
	por_nombre: Path | None = None
	for ficha in entornos.listar(app.config, getattr(app.opciones, "paquete", None)):
		if not ficha.valido:
			continue
		if entorno_id:
			try:
				if str(leer_manifiesto(ficha.ruta).get("id") or "") == entorno_id:
					return ficha.ruta
			except ErrorFormato, OSError, ValueError, zipfile.BadZipFile:
				log.warning("No se pudo leer el manifiesto de %s al buscar una actividad asignada", ficha.ruta.name)
		if nombre and ficha.ruta.name == nombre and por_nombre is None:
			por_nombre = ficha.ruta
	return por_nombre


def jugar_asignada(app: Aplicacion, entrada: dict[str, Any]) -> bool:
	"""Empieza una actividad de la lista de trabajo. Devuelve si se pudo empezar."""
	ruta = buscar_paquete(app, entrada)
	if ruta is None:
		_decir_error(
			app,
			_("En este ordenador no está el entorno «{entorno}». Pide a tu profesor que te lo copie.").format(
				entorno=entrada.get("entorno_nombre") or entrada.get("paquete") or _("de la actividad")
			),
		)
		return False
	try:
		paquete = entornos.abrir(ruta)
	except entornos.ErrorEntorno as error:
		_decir_error(app, str(error))
		return False
	datos = paquete.actividad(str(entrada.get("actividad_id") or ""))
	if datos is None:
		app.decir(_("Esa actividad ya no está en el entorno. Elige otra."), True, "aviso")
		abrir_actividades(app, paquete)
		return False
	return app.empezar_partida(paquete, datos)


def abrir_trabajo(app: Aplicacion) -> Menu:
	"""Las actividades que el profesional ha puesto al alumno (la lista de trabajo de su ficha)."""

	def jugar(entrada: dict[str, Any]) -> Callable[[], None]:
		return lambda: jugar_asignada(app, entrada)

	def lista() -> list[Opcion]:
		entradas = app.perfil.lista_trabajo if app.perfil is not None else []
		if not entradas:
			return [Opcion(_("Tu profesor no te ha puesto ninguna actividad."))]
		return [
			Opcion(
				_("{actividad}, en {entorno}").format(
					actividad=entrada.get("actividad_nombre") or entrada.get("actividad_id"),
					entorno=entrada.get("entorno_nombre") or entrada.get("paquete"),
				),
				jugar(entrada),
				ayuda=_("Aceptar la empieza."),
			)
			for entrada in entradas
		]

	menu = Menu(app, _("Lo que te ha puesto tu profesor"), lista)
	app.abrir(menu)
	return menu


def continuar(app: Aplicacion) -> bool:
	"""Vuelve a lo último que jugó el alumno; si nunca ha jugado, a lo primero que le ha puesto su profesor."""
	ultima = app.perfil.ultima if app.perfil is not None else {}
	ruta = str(ultima.get("ruta") or "")
	if not ruta:
		asignadas = app.perfil.lista_trabajo if app.perfil is not None else []
		if asignadas:
			return jugar_asignada(app, asignadas[0])
		app.decir(_("Todavía no has jugado nada. Elige un entorno."), True)
		return False
	try:
		paquete = entornos.abrir(ruta)
	except entornos.ErrorEntorno as error:
		_decir_error(app, str(error))
		return False
	identificador = str(ultima.get("actividad") or "")
	datos = paquete.actividad(identificador) if identificador else None
	if identificador and datos is None:
		app.decir(_("La actividad que jugaste ya no está en el entorno. Elige otra."), True, "aviso")
		abrir_actividades(app, paquete)
		return False
	return app.empezar_partida(paquete, datos)
