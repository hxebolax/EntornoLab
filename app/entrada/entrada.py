"""Punto único de entrada: teclado y mando traducidos a acciones del motor.

El reproductor no distingue de dónde viene una orden: pasa cada evento de
pygame a ``Entrada.traducir`` y recibe pares ``(acción, pulsada)``; una vez
por fotograma llama a ``actualizar`` (palancas convertidas en acciones) y a
``ejes`` (movimiento analógico para ``Sesion.analogico``). Teclado y mando
valen a la vez.

No depende de la configuración global: los mapas y las opciones entran y
salen como diccionarios (``a_dict``), y quien los guarda es otro módulo.
"""

from __future__ import annotations

import logging
from typing import Any

import pygame

from app.entrada import acciones
from app.entrada.mando import Mandos, MapaMando, sanear_opciones, textos_mando
from app.entrada.teclado import MapaTeclado, Teclado

log = logging.getLogger(__name__)

_EVENTOS_TECLADO = (pygame.KEYDOWN, pygame.KEYUP)
_EVENTOS_MANDO = (
	pygame.CONTROLLERDEVICEADDED,
	pygame.CONTROLLERDEVICEREMOVED,
	pygame.CONTROLLERBUTTONDOWN,
	pygame.CONTROLLERBUTTONUP,
	pygame.CONTROLLERAXISMOTION,
)


class Entrada:
	"""Teclado y mandos del alumno, con sus mapas reasignables.

	``opciones`` son las del mando (zona muerta, gatillos, vibración...: ver
	``app.entrada.mando.OPCIONES_POR_DEFECTO``). ``iniciar_mandos=False`` no
	toca SDL: para las pruebas, que conectan un mando falso con
	``entrada.mandos.conectar``.
	"""

	def __init__(
		self,
		mapa_teclado: dict | None = None,
		mapa_mando: dict | None = None,
		opciones: dict | None = None,
		iniciar_mandos: bool = True,
	) -> None:
		self.teclado = Teclado(mapa_teclado)
		self.mandos = Mandos(mapa_mando, opciones, iniciar=iniciar_mandos)
		self._contexto = acciones.JUEGO

	# ── Eventos y ejes ──

	def traducir(self, evento: pygame.event.Event, contexto: str = acciones.JUEGO) -> list[tuple[str, bool]]:
		"""(acción, pulsada) de un evento de pygame; lista vacía si no produce ninguna.

		Si el contexto cambia (se abre o se cierra un menú), lo que quedara
		pulsado se suelta primero: una flecha mantenida al abrir la pausa no
		debe seguir andando al volver.
		"""
		salida = self._cambiar_contexto(contexto)
		if evento.type in _EVENTOS_TECLADO:
			salida += self.teclado.traducir(evento, contexto)
		elif evento.type in _EVENTOS_MANDO:
			salida += self.mandos.evento(evento, contexto)
		elif evento.type == pygame.WINDOWFOCUSLOST:
			# Sin el foco no llegan las teclas soltadas: se sueltan aquí para que el alumno no siga andando solo.
			salida += self.soltar_todo()
		return salida

	def actualizar(self, dt: float, contexto: str = acciones.JUEGO) -> list[tuple[str, bool]]:
		"""Acciones que salen de las palancas en este fotograma (repetición en menús, mirar con la derecha)."""
		return self._cambiar_contexto(contexto) + self.mandos.actualizar(dt, contexto)

	def ejes(self, contexto: str = acciones.JUEGO) -> tuple[float, float, float, tuple[float, float] | None]:
		"""(avance, lateral, giro, mirada) del mando, de −1 a 1; todo a cero sin mando o en un menú."""
		return self.mandos.ejes(contexto)

	def soltar_todo(self) -> list[tuple[str, bool]]:
		"""Suelta todo lo que esté pulsado en el teclado y en los mandos."""
		return self.teclado.soltar_todo() + self.mandos.soltar_todo()

	def _cambiar_contexto(self, contexto: str) -> list[tuple[str, bool]]:
		if contexto == self._contexto:
			return []
		self._contexto = contexto
		return self.soltar_todo()

	# ── Vibración y avisos ──

	def vibrar(self, grave: float, agudo: float, ms: int) -> bool:
		"""Hace vibrar los mandos conectados; devuelve si alguno vibró."""
		return self.mandos.vibrar(grave, agudo, ms)

	def avisos(self) -> list[str]:
		"""Frases pendientes de decir (mando conectado o desconectado); se vacían al leerlas."""
		return self.mandos.tomar_avisos()

	# ── Textos ──

	@property
	def con_mando(self) -> bool:
		"""Si hay un mando conectado y las frases deben nombrar sus botones."""
		return self.mandos.conectado and bool(self.mandos.opciones["decir_botones"])

	def control_de(self, accion: str, contexto: str = acciones.JUEGO) -> str:
		"""Con qué se hace ahora una acción, dicho en una frase: el botón si se juega con mando, o la tecla."""
		if self.con_mando:
			frase = self.mandos.frase_de(accion, contexto)
			if frase:
				return frase
		return self.teclado.mapa.nombre_de(contexto, accion)

	def textos(self, texto: str, contexto: str = acciones.JUEGO) -> str:
		"""Con un mando conectado, las teclas que nombra una frase se dicen como botones de ese mando."""
		if not self.con_mando:
			return texto
		return textos_mando(texto, self.teclado.mapa, self.mandos.mapa, self.mandos.familia, contexto)

	def ayuda(self, contexto: str = acciones.JUEGO) -> list[str]:
		"""Una frase por acción del contexto con su tecla o su botón, para la pantalla de ayuda."""
		frases: list[str] = []
		for accion in acciones.acciones_de(contexto):
			control = self.control_de(accion.id, contexto)
			if control:
				frases.append(f"{control[0].upper()}{control[1:]}: {accion.nombre.lower()}.")
		return frases

	# ── Cargar y guardar ──

	def a_dict(self) -> dict[str, Any]:
		"""Mapas y opciones, para que la configuración los guarde."""
		return {
			"teclado": self.teclado.mapa.a_dict(),
			"mando": self.mandos.mapa.a_dict(),
			"opciones": dict(self.mandos.opciones),
		}

	def cargar(self, datos: dict | None) -> None:
		"""Sustituye mapas y opciones por los de ``datos`` (lo que devuelve ``a_dict``); lo que falte queda de serie."""
		datos = datos if isinstance(datos, dict) else {}
		self.soltar_todo()
		self.teclado.mapa = MapaTeclado(datos.get("teclado"))
		self.mandos.mapa = MapaMando(datos.get("mando"))
		self.mandos.opciones = sanear_opciones(datos.get("opciones"))

	def cerrar(self) -> None:
		"""Suelta los mandos (al salir del reproductor)."""
		self.mandos.cerrar()
