"""«Aprender los sonidos» y «Practicar los controles».

Las dos pantallas sirven para lo mismo: que el alumno llegue a la primera
actividad sabiendo qué significa lo que oye y qué hace cada tecla o botón, sin
la presión de estar jugando.

- **Aprender los sonidos**: los grupos y los sonidos salen de
  ``catalogo_sonidos()`` (común a todos los paquetes de sonidos), cada uno con
  su nombre y su explicación. Se oyen con el paquete que esté elegido.
- **Practicar los controles**: se pulsa cualquier cosa y se dice qué es y para
  qué sirve, sin ejecutar nada. Usa el mapa de juego real, con lo que el
  alumno haya reasignado, y los nombres de botón del mando conectado.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

import pygame

from app.audio.banco import catalogo_sonidos
from app.core.i18n import _
from app.entrada import acciones, teclado
from app.entrada.mando import BOTONES_SDL
from app.reproductor.menus import SONIDO_ATRAS, Menu, Opcion, Pantalla

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)

# Un bucle (un ambiente, el frigorífico) se deja sonar este tiempo y se apaga solo.
SEGUNDOS_DE_BUCLE = 4.0


# ── Aprender los sonidos ─────────────────────────────────────────────────────


class MenuSonidos(Menu):
	"""Menú de los sonidos de un grupo: aceptar hace sonar el elegido; los bucles se apagan solos."""

	def __init__(self, app: Aplicacion, titulo: str, sonidos: list[tuple[str, dict[str, Any]]]) -> None:
		self._canal = 0
		self._queda = 0.0
		self._sonidos = sonidos
		super().__init__(app, titulo, self._lista, intro=_("Elige un sonido para oírlo. Con la ayuda oyes su explicación"))

	def _lista(self) -> list[Opcion]:
		return [
			Opcion(
				str(ficha.get("nombre") or clave),
				self._sonar(clave, ficha),
				ayuda=str(ficha.get("explicacion") or _("Sin explicación.")),
				callado=True,
			)
			for clave, ficha in self._sonidos
		]

	def _sonar(self, clave: str, ficha: dict[str, Any]) -> Callable[[], None]:
		def hacer() -> None:
			self.parar()
			self.app.callar()
			bucle = bool(ficha.get("bucle"))
			try:
				self._canal = int(self.app.motor.reproducir(clave, bus="interfaz", bucle=bucle, eco=False))
			except OSError, ValueError, KeyError, RuntimeError:
				log.warning("No se pudo reproducir el sonido %s.", clave, exc_info=True)
				self._canal = 0
			self._queda = SEGUNDOS_DE_BUCLE if bucle else 0.0

		return hacer

	def parar(self) -> None:
		"""Calla el sonido que se estuviera escuchando."""
		if self._canal:
			self.app.motor.parar(self._canal, 0.15)
			self._canal = 0
		self._queda = 0.0

	def actualizar(self, dt: float) -> None:
		"""Apaga un bucle cuando ha sonado lo suficiente."""
		if self._queda > 0.0:
			self._queda -= dt
			if self._queda <= 0.0:
				self.parar()

	def mover(self, nuevo: int) -> None:
		"""Al pasar a otro sonido, el anterior se calla."""
		self.parar()
		super().mover(nuevo)

	def al_salir(self) -> None:
		"""Al cerrar el menú no queda nada sonando."""
		self.parar()
		super().al_salir()


def abrir_sonidos(app: Aplicacion) -> Menu:
	"""Abre los grupos de sonidos del catálogo."""
	catalogo = catalogo_sonidos()
	sonidos: dict[str, dict[str, Any]] = catalogo.get("sonidos", {})

	def abrir_grupo(grupo: dict[str, Any]) -> Callable[[], None]:
		def hacer() -> None:
			del_grupo = [(clave, ficha) for clave, ficha in sonidos.items() if ficha.get("grupo") == grupo.get("id")]
			app.abrir(MenuSonidos(app, str(grupo.get("nombre") or ""), del_grupo))

		return hacer

	opciones: list[Opcion] = []
	for grupo in catalogo.get("grupos", []):
		cuantos = sum(1 for ficha in sonidos.values() if ficha.get("grupo") == grupo.get("id"))
		if cuantos:
			opciones.append(Opcion(str(grupo.get("nombre") or ""), abrir_grupo(grupo), ayuda=_("{n} sonidos.").format(n=cuantos)))
	if not opciones:
		opciones.append(Opcion(_("No se ha encontrado el catálogo de sonidos.")))
	menu = Menu(app, _("Aprender los sonidos"), opciones, intro=_("Elige un grupo"))
	app.abrir(menu)
	return menu


# ── Practicar los controles ──────────────────────────────────────────────────


class PracticaControles(Pantalla):
	"""Dice qué hace cada tecla o botón que se pulsa, sin ejecutarlo. Para salir, la pausa dos veces seguidas."""

	contexto = acciones.JUEGO

	def __init__(self, app: Aplicacion) -> None:
		super().__init__(app)
		self._pausa_previa = False
		self.ultimo = ""

	def al_entrar(self) -> None:
		"""Explica cómo funciona y cómo se sale."""
		salida = self.app.entrada.control_de("pausa", acciones.JUEGO)
		self.app.decir_menu(
			_(
				"Practicar los controles. Pulsa cualquier tecla o botón y te digo para qué sirve; no pasa nada. Para salir, pulsa {salida} dos veces seguidas."
			).format(salida=salida)
		)

	def _decir(self, control: str, accion: str | None) -> None:
		if accion is None:
			texto = _("{control}: no hace nada mientras juegas.").format(control=control) if control else ""
		else:
			nombre = acciones.nombre_accion(accion)
			ayuda = acciones.ayuda_accion(accion)
			texto = f"{control}: {nombre}. {ayuda}" if control else f"{nombre}. {ayuda}"
		if texto:
			self.ultimo = texto
			self.app.decir_menu(texto[:1].upper() + texto[1:])

	def _salir_o_avisar(self) -> None:
		if self._pausa_previa:
			self.app.sonar(SONIDO_ATRAS)
			self.app.cerrar(self)
			return
		self._pausa_previa = True

	def tecla(self, evento: pygame.event.Event) -> bool:
		"""Se queda con todas las teclas y botones: los traduce para decirlos, no para jugar."""
		entrada = self.app.entrada
		if evento.type == pygame.KEYDOWN:
			traducidas = [accion for accion, pulsada in entrada.teclado.traducir(evento, acciones.JUEGO) if pulsada]
			nombre = teclado.nombre_combinacion(teclado.combinacion(evento.key, int(getattr(evento, "mod", 0)))) or teclado.nombre_tecla(
				teclado.id_tecla(evento.key)
			)
			self._atender(nombre, traducidas)
			return True
		if evento.type == pygame.KEYUP:
			entrada.teclado.traducir(evento, acciones.JUEGO)
			return True
		if evento.type == pygame.CONTROLLERBUTTONDOWN:
			boton = BOTONES_SDL.get(int(evento.button), "")
			traducidas = [accion for accion, pulsada in entrada.mandos.evento(evento, acciones.JUEGO) if pulsada]
			nombre = entrada.mandos.nombre_boton(boton) if boton else _("Botón desconocido")
			if entrada.mandos.modificador_pulsado and boton and boton != entrada.mandos.mapa.modificador:
				nombre = _("{modificador} más {boton}").format(
					modificador=entrada.mandos.nombre_boton(entrada.mandos.mapa.modificador), boton=nombre
				)
			elif boton and boton == entrada.mandos.mapa.modificador:
				self._pausa_previa = False
				self.app.decir_menu(_("{boton}: segunda función. Mantenlo pulsado y pulsa otro botón.").format(boton=nombre))
				return True
			self._atender(nombre, traducidas)
			return True
		if evento.type == pygame.CONTROLLERBUTTONUP:
			entrada.mandos.evento(evento, acciones.JUEGO)
			return True
		return False

	def _atender(self, nombre: str, traducidas: list[str]) -> None:
		accion = traducidas[0] if traducidas else None
		if accion == "pausa":
			if self._pausa_previa:
				self._salir_o_avisar()
				return
			self._decir(nombre, accion)
			self._pausa_previa = True
			return
		self._pausa_previa = False
		self._decir(nombre, accion)

	def accion(self, accion: str, pulsada: bool) -> bool:
		"""Lo que llega ya como acción (palancas y gatillos): se dice igual, sin ejecutarlo."""
		if not pulsada:
			return True
		control = self.app.entrada.control_de(accion, acciones.JUEGO)
		if accion == "pausa":
			if self._pausa_previa:
				self._salir_o_avisar()
				return True
			self._decir(control, accion)
			self._pausa_previa = True
			return True
		self._pausa_previa = False
		self._decir(control, accion)
		return True

	def titulo_visible(self) -> str:
		"""El nombre de la pantalla."""
		return _("Practicar los controles")

	def lineas(self) -> tuple[list[str], int]:
		"""Lo último que se ha dicho."""
		return self.app.partir(self.ultimo, 24, 900), -1


def abrir_practica(app: Aplicacion) -> PracticaControles:
	"""Abre la pantalla de práctica de controles."""
	pantalla = PracticaControles(app)
	app.abrir(pantalla)
	return pantalla
