"""Único punto de enganche del seguimiento con el resto del Estudio.

La ventana principal importa este módulo (de forma tolerante) y solo usa lo
que hay aquí:

- ``MENUS_SEGUIMIENTO``: los menús «Alumnos» y «Supervisión», con el formato
  de ``app/ui/menus.py`` (ver ``docs/estudio.md``): cada entrada es
  ``(nombre_de_funcion, etiqueta, ayuda)`` o ``None`` para un separador, y la
  función es una de este módulo, a la que se llama con el contexto.
- ``crear_panel_actividades(padre, contexto)``: la pestaña «Actividades».
- ``mostrar_alumnos``, ``mostrar_supervision``, ``mostrar_sesiones``,
  ``mostrar_informes`` y ``mostrar_cuaderno``: abren (o traen al frente) cada
  ventana. Las que enseñan datos de alumnos piden antes la contraseña.
- ``al_cerrar(contexto)``: cierra la sala, los reproductores lanzados, las
  ventanas y la base.

No importa ``app.ui.contexto``: el contexto se usa por su forma
(``app.ui.seguimiento.contexto.ContextoSeguimiento``).
"""

from __future__ import annotations

import logging
from typing import Any

import wx

from app.core.i18n import N_
from app.ui.seguimiento import dialogos_acceso
from app.ui.seguimiento.comun import abrir_ventana
from app.ui.seguimiento.servicio import cerrar_servicio, obtener_servicio

log = logging.getLogger(__name__)

# Letras de los menús de la barra ya usadas por la ventana principal: A, E, I, V, H y U.
MENUS_SEGUIMIENTO: list = [
	(
		N_("A&lumnos"),
		[
			(
				"mostrar_alumnos",
				N_("&Fichas de alumnos...\tCtrl+L"),
				N_("Abre la lista de alumnos: fichas, ajustes de juego, recompensas, exportar y borrar."),
			),
			(
				"mostrar_sesiones",
				N_("&Sesiones...\tCtrl+T"),
				N_("Lista las sesiones guardadas, con su detalle y la repetición del recorrido."),
			),
			(
				"mostrar_informes",
				N_("&Informes...\tCtrl+I"),
				N_("Informes de una sesión, comparación, evolución, examen y evaluación real frente a virtual."),
			),
			(
				"mostrar_cuaderno",
				N_("&Cuaderno de evaluación real...\tCtrl+U"),
				N_("Anota y consulta las pruebas hechas en el lugar físico."),
			),
			None,
			(
				"cambiar_contrasena",
				N_("Cambiar la c&ontraseña..."),
				N_("Cambia la contraseña con la que se cifran los datos personales de los alumnos."),
			),
			(
				"bloquear_datos",
				N_("&Bloquear los datos de alumnos"),
				N_("Cierra los datos de alumnos: la próxima vez se pedirá la contraseña."),
			),
		],
	),
	(
		N_("&Supervisión"),
		[
			(
				"mostrar_supervision",
				N_("&Sala de supervisión...\tF7"),
				N_("Abre la ventana de supervisión en vivo: sala, alumnos conectados y órdenes."),
			),
			(
				"empezar_sesion_local",
				N_("&Empezar sesión en este ordenador..."),
				N_("Elige alumno, entorno y actividad y abre el reproductor conectado a la sala."),
			),
			(
				"anuncios_supervision",
				N_("&Anuncios por voz..."),
				N_("Elige qué sucesos del alumno se dicen por voz durante la supervisión."),
			),
		],
	),
]


def crear_panel_actividades(padre: wx.Window, contexto: Any) -> wx.Window:
	"""Crea la pestaña «Actividades» del entorno abierto."""
	from app.ui.seguimiento.panel_actividades import PanelActividades

	return PanelActividades(padre, contexto, obtener_servicio(contexto))


def mostrar_alumnos(contexto: Any) -> Any:
	"""Abre la ventana de alumnos (pide antes la contraseña). Devuelve la ventana, o ``None`` si se cancela."""
	from app.ui.seguimiento.alumnos import VentanaAlumnos

	servicio = obtener_servicio(contexto)
	if dialogos_acceso.asegurar_base(contexto, servicio) is None:
		return None
	return abrir_ventana(servicio, VentanaAlumnos.CLAVE, lambda: VentanaAlumnos(contexto, servicio))


def mostrar_supervision(contexto: Any) -> Any:
	"""Abre la ventana de supervisión en vivo. No necesita la contraseña: por la sala solo viaja el alias."""
	from app.ui.seguimiento.supervision import VentanaSupervision

	servicio = obtener_servicio(contexto)
	return abrir_ventana(servicio, VentanaSupervision.CLAVE, lambda: VentanaSupervision(contexto, servicio))


def mostrar_sesiones(contexto: Any, alumno_id: int | None = None) -> Any:
	"""Abre la ventana de sesiones, filtrada por un alumno si se indica."""
	from app.ui.seguimiento.sesiones import VentanaSesiones

	servicio = obtener_servicio(contexto)
	if dialogos_acceso.asegurar_base(contexto, servicio) is None:
		return None
	existente = servicio.ventanas.get(VentanaSesiones.CLAVE)
	if existente and alumno_id is not None:
		existente.elegir_alumno(alumno_id)
	return abrir_ventana(servicio, VentanaSesiones.CLAVE, lambda: VentanaSesiones(contexto, servicio, alumno_id))


def mostrar_informes(contexto: Any, alumno_id: int | None = None, sesion_id: str | None = None) -> Any:
	"""Abre la ventana de informes, con un alumno y una sesión ya elegidos si se indican."""
	from app.ui.seguimiento.informes import VentanaInformes

	servicio = obtener_servicio(contexto)
	if dialogos_acceso.asegurar_base(contexto, servicio) is None:
		return None
	existente = servicio.ventanas.get(VentanaInformes.CLAVE)
	if existente and alumno_id is not None:
		existente.cargar_alumnos(alumno_id, sesion_id)
	return abrir_ventana(servicio, VentanaInformes.CLAVE, lambda: VentanaInformes(contexto, servicio, alumno_id, sesion_id))


def mostrar_cuaderno(contexto: Any, alumno_id: int | None = None) -> Any:
	"""Abre el cuaderno de evaluación real, con un alumno ya elegido si se indica."""
	from app.ui.seguimiento.cuaderno import VentanaCuaderno

	servicio = obtener_servicio(contexto)
	if dialogos_acceso.asegurar_base(contexto, servicio) is None:
		return None
	existente = servicio.ventanas.get(VentanaCuaderno.CLAVE)
	if existente and alumno_id is not None:
		existente.cargar_alumnos(alumno_id)
	return abrir_ventana(servicio, VentanaCuaderno.CLAVE, lambda: VentanaCuaderno(contexto, servicio, alumno_id))


def cambiar_contrasena(contexto: Any) -> bool:
	"""Abre el cambio de contraseña de los datos de alumnos."""
	return dialogos_acceso.cambiar_contrasena(contexto, obtener_servicio(contexto), getattr(contexto, "ventana", None))


def bloquear_datos(contexto: Any) -> None:
	"""Cierra las ventanas con datos de alumnos y bloquea la base."""
	dialogos_acceso.bloquear(contexto, obtener_servicio(contexto))


def empezar_sesion_local(contexto: Any) -> Any:
	"""Abre la supervisión y, en ella, el diálogo para empezar una sesión en este ordenador."""
	ventana = mostrar_supervision(contexto)
	if ventana is not None:
		ventana.empezar_sesion()
	return ventana


def anuncios_supervision(contexto: Any) -> Any:
	"""Abre la supervisión y, en ella, las preferencias de los anuncios por voz."""
	ventana = mostrar_supervision(contexto)
	if ventana is not None:
		ventana.anuncios()
	return ventana


def al_cerrar(contexto: Any) -> None:
	"""Cierra todo lo del seguimiento: ventanas, sala, reproductores lanzados y base. Nunca lanza."""
	try:
		cerrar_servicio(contexto)
	except Exception:  # noqa: BLE001 - se está cerrando el Estudio: un fallo aquí no debe impedir que se cierre
		log.exception("Ha fallado el cierre del seguimiento")
