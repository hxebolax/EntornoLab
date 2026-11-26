"""«Conectar con mi profesor»: buscar salas en la red, escribir la dirección o usar este mismo ordenador.

Siempre se ofrece escribir la dirección a mano: muchas redes de centros
bloquean la búsqueda automática, y una lista vacía no significa que no haya
sala. El código de emparejamiento lo dicta el profesor; se escribe con el
teclado o con la rueda de letras del mando.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.core.i18n import _
from app.reproductor.menus import SONIDO_ERROR, EntradaTexto, Espera, Menu, Opcion
from app.supervision import descubrimiento

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)

HOST_LOCAL = "127.0.0.1"


def pedir_codigo(app: Aplicacion, host: str, puerto: int, al_conectar: Callable[[], None] | None = None) -> None:
	"""Pide el código de emparejamiento y conecta con la sala."""

	def aceptado(codigo: str) -> None:
		if not codigo.strip():
			app.sonar(SONIDO_ERROR)
			app.decir(_("No has escrito el código."), True)
			return
		app.conectar_sala(host, puerto, codigo.strip())
		# Primero se cierra el menú de conexión: lo que diga al volver no debe tapar este aviso.
		if al_conectar is not None:
			al_conectar()
		app.decir(_("Conectando con la sala. Puedes seguir usando el juego mientras tanto."), True)

	app.abrir(
		EntradaTexto(
			app,
			_("Escribe el código que te ha dicho tu profesor"),
			aceptado,
			maximo=32,
			ayuda=_("Suelen ser seis cifras. Con el mando, cambia a números con el botón de cambiar de grupo."),
		)
	)


def abrir_conexion(app: Aplicacion) -> Menu:
	"""Abre el menú de conexión con la sala del profesor."""

	def buscar() -> None:
		def encontrado(salas: Any) -> None:
			salas = list(salas or [])
			if not salas:
				app.sonar(SONIDO_ERROR)
				app.decir(
					_("No se ha encontrado ninguna sala. Puede que la red no deje buscarlas: pide la dirección a tu profesor y escríbela."),
					True,
				)
				return
			abrir_salas(app, salas, al_conectar=lambda: app.cerrar(menu))

		app.abrir(
			Espera(app, _("Buscando salas en la red."), lambda: descubrimiento.buscar_salas(espera=1.5), encontrado, _("Sigo buscando."))
		)

	def escribir() -> None:
		def aceptada(texto: str) -> None:
			try:
				host, puerto = descubrimiento.analizar_direccion(texto, int(app.config.obtener("supervision.puerto", 47900)))
			except ValueError as error:
				app.sonar(SONIDO_ERROR)
				app.decir(str(error), True)
				return
			app.establecer("supervision.ultima_sala", texto.strip()[:255])
			pedir_codigo(app, host, puerto, al_conectar=lambda: app.cerrar(menu))

		app.abrir(
			EntradaTexto(
				app,
				_("Escribe la dirección de la sala"),
				aceptada,
				inicial=str(app.config.obtener("supervision.ultima_sala", "") or ""),
				maximo=80,
				ayuda=_("Es la que ve tu profesor en su pantalla, por ejemplo 192.168.1.20. Los puntos están en el grupo de signos."),
			)
		)

	def local() -> None:
		pedir_codigo(app, HOST_LOCAL, int(app.config.obtener("supervision.puerto", 47900)), al_conectar=lambda: app.cerrar(menu))

	def desconectar() -> None:
		app.desconectar_sala()
		app.decir(_("Desconectado de la sala."), True)
		menu.refrescar(False)

	def lista() -> list[Opcion]:
		opciones: list[Opcion] = []
		if app.enlace is not None:
			opciones.append(
				Opcion(
					lambda: app.enlace.descripcion() if app.enlace is not None else _("Sin conexión."), ayuda=_("El estado de la conexión.")
				)
			)
			opciones.append(Opcion(_("Desconectar"), desconectar, ayuda=_("Deja la sala. Puedes seguir jugando por tu cuenta.")))
		opciones += [
			Opcion(_("Buscar salas en la red"), buscar, ayuda=_("Busca el ordenador de tu profesor en la red del centro o de casa.")),
			Opcion(
				_("Escribir la dirección de la sala"),
				escribir,
				ayuda=_("Si la búsqueda no la encuentra, tu profesor te puede dictar la dirección."),
			),
			Opcion(_("El profesor está en este mismo ordenador"), local, ayuda=_("Cuando el Estudio está abierto en este ordenador.")),
		]
		return opciones

	menu = Menu(app, _("Conectar con mi profesor"), lista, intro=_("Necesitas el código que te diga tu profesor"))
	app.abrir(menu)
	return menu


def abrir_salas(app: Aplicacion, salas: list[Any], al_conectar: Callable[[], None] | None = None) -> Menu:
	"""Lista de salas encontradas; al elegir una se pide el código."""

	def elegir(sala: Any) -> Callable[[], None]:
		def hacer() -> None:
			app.cerrar(menu)
			pedir_codigo(app, str(sala.host), int(sala.puerto), al_conectar)

		return hacer

	opciones = [
		Opcion(
			sala.nombre or _("Sala sin nombre"),
			elegir(sala),
			ayuda=_("Está en la dirección {host}, puerto {puerto}.").format(host=sala.host, puerto=sala.puerto),
		)
		for sala in salas
	]
	menu = Menu(app, _("Salas encontradas"), opciones)
	app.abrir(menu)
	return menu
