"""Vocabulario de vibración del mando: pocos patrones, siempre los mismos, con nombre.

El alumno aprende qué significa cada vibración igual que aprende los sonidos, así que el vocabulario es
pequeño y constante (apartado 12.4 del informe): golpe seco = choque; pulso suave = premio cerca; lado
izquierdo o derecho = pared a ese lado; doble pulso = objetivo alcanzado.

Convención de lados: en los mandos de Xbox y PlayStation el motor **grave** (el grande, baja frecuencia)
está en la empuñadura **izquierda** y el **agudo** (el pequeño) en la **derecha**. Por eso «pared a la
izquierda» usa solo el grave y «pared a la derecha» solo el agudo. No es un lado perfecto (el agudo se
nota menos), y por eso el patrón derecho es algo más fuerte y más largo.

Este módulo no conoce pygame: recibe un ``emisor(grave, agudo, ms)`` (normalmente ``Mando.vibrar``) y
traduce nombres a pulsos. Las secuencias (doble pulso) avanzan con ``tic``.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass

from app.core.i18n import N_, _

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Pulso:
	"""Un pulso de vibración: motores grave y agudo (0 a 1), duración y silencio posterior, en milisegundos."""

	grave: float
	agudo: float
	ms: int
	pausa_ms: int = 0


# nombre → secuencia de pulsos. Un solo pulso es lo normal; el doble pulso lleva pausa entre los dos.
PATRONES: dict[str, tuple[Pulso, ...]] = {
	"choque": (Pulso(1.0, 0.8, 90),),
	"premio_cerca": (Pulso(0.0, 0.3, 160),),
	"pared_izquierda": (Pulso(0.7, 0.0, 120),),
	"pared_derecha": (Pulso(0.0, 0.85, 150),),
	"objetivo": (Pulso(0.6, 0.6, 110, 90), Pulso(0.6, 0.6, 110)),
	"peldano": (Pulso(0.35, 0.0, 50),),
	"aviso": (Pulso(0.3, 0.5, 80, 70), Pulso(0.3, 0.5, 80, 70), Pulso(0.3, 0.5, 80)),
}

_NOMBRES: dict[str, str] = {
	"choque": N_("Choque: golpe seco"),
	"premio_cerca": N_("Premio cerca: pulso suave"),
	"pared_izquierda": N_("Pared a la izquierda: vibra el lado izquierdo"),
	"pared_derecha": N_("Pared a la derecha: vibra el lado derecho"),
	"objetivo": N_("Objetivo alcanzado: doble pulso"),
	"peldano": N_("Peldaño: toque corto"),
	"aviso": N_("Aviso: tres toques"),
}

FUERZA_MINIMA = 0.2  # por debajo, muchos mandos no llegan a moverse y parecería que no vibra


def nombres_patrones() -> dict[str, str]:
	"""Nombre visible (traducido) de cada patrón, para el menú «Aprender las vibraciones» y las preferencias."""
	return {nombre: _(texto) for nombre, texto in _NOMBRES.items()}


def _recortar(valor: float) -> float:
	return max(0.0, min(1.0, float(valor)))


class Haptica:
	"""Traduce patrones con nombre a llamadas ``emisor(grave, agudo, ms)`` y lleva las secuencias pendientes."""

	def __init__(self, emisor: Callable[[float, float, int], None] | None = None, opciones: dict | None = None) -> None:
		"""``opciones``: ``activa`` (bool) y ``fuerza`` (0.2 a 1). Sin emisor, lo emitido se apunta en ``registro``."""
		self.emisor = emisor
		self.activa = True
		self.fuerza = 1.0
		self.registro: list[tuple[float, float, int]] = []
		self._reloj: Callable[[], float] = time.monotonic
		self._ahora = 0.0  # tiempo interno, que solo avanza con tic()
		self._t_real: float | None = None
		self._cola: list[tuple[float, float, float, int]] = []  # (instante, grave, agudo, ms)
		self.configurar(opciones or {})

	def configurar(self, opciones: dict) -> None:
		"""Aplica ``activa`` y ``fuerza`` en caliente."""
		if "activa" in opciones:
			self.activa = bool(opciones["activa"])
			if not self.activa:
				self._cola.clear()
		if "fuerza" in opciones:
			try:
				self.fuerza = max(FUERZA_MINIMA, min(1.0, float(opciones["fuerza"])))
			except TypeError, ValueError:
				log.warning("Fuerza de vibración no válida: %s", opciones["fuerza"])

	def vibrar(self, grave: float, agudo: float, ms: int) -> None:
		"""Vibración directa (la de ``EvVibrar``): recortada a 0..1 y multiplicada por la fuerza elegida."""
		if not self.activa or ms <= 0:
			return
		g = _recortar(grave) * self.fuerza
		a = _recortar(agudo) * self.fuerza
		if self.emisor is None:
			self.registro.append((g, a, int(ms)))
			return
		try:
			self.emisor(g, a, int(ms))
		except Exception:  # noqa: BLE001 - un mando que no vibra o desconectado a medias no debe parar el juego
			log.debug("El mando no pudo vibrar.", exc_info=True)

	def patron(self, nombre: str, intensidad: float = 1.0) -> bool:
		"""Lanza un patrón del vocabulario. Sustituye a la secuencia que estuviera pendiente. Falso si no existe."""
		pulsos = PATRONES.get(nombre)
		if pulsos is None:
			log.warning("Patrón de vibración desconocido: %s", nombre)
			return False
		if not self.activa:
			return True
		k = _recortar(intensidad)
		self._cola.clear()
		instante = self._ahora
		for pulso in pulsos:
			self._cola.append((instante, pulso.grave * k, pulso.agudo * k, pulso.ms))
			instante += (pulso.ms + pulso.pausa_ms) / 1000.0
		self._despachar()
		return True

	def _despachar(self) -> None:
		while self._cola and self._cola[0][0] <= self._ahora + 1e-9:
			_instante, grave, agudo, ms = self._cola.pop(0)
			self.vibrar(grave, agudo, ms)

	def tic(self, dt: float | None = None) -> None:
		"""Avanza las secuencias pendientes. Con ``dt`` (segundos) avanza eso; sin él, lo que diga el reloj."""
		if dt is None:
			real = self._reloj()
			dt = 0.0 if self._t_real is None else real - self._t_real
			self._t_real = real
		self._ahora += max(0.0, dt)
		self._despachar()

	@property
	def pendiente(self) -> bool:
		"""Si queda algún pulso de una secuencia por emitir."""
		return bool(self._cola)

	def parar(self) -> None:
		"""Olvida lo pendiente y detiene los motores."""
		self._cola.clear()
		if self.emisor is None:
			return
		try:
			self.emisor(0.0, 0.0, 0)
		except Exception:  # noqa: BLE001 - igual que al vibrar
			log.debug("No se pudo parar la vibración.", exc_info=True)
