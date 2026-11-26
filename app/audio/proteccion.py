"""Protección auditiva: que ningún fallo ni ningún ajuste pueda hacer daño por los auriculares.

El alumno lleva auriculares y no ve la pantalla; un sonido inesperadamente fuerte no solo molesta,
asusta y desorienta. Cuatro defensas, todas ajustables y ninguna desactivable del todo:

- **Techo por fuente**: ningún sonido suelto supera esa ganancia, pida lo que pida el entorno
  (un ``volumen`` de 5 en un complemento mal hecho se queda en el techo).
- **Techo de mezcla**: tope de la ganancia maestra y limitador de la suma (rodilla suave).
- **Subidas graduales**: el volumen maestro sube despacio (al arrancar, al volver de un silencio o al
  mover un deslizador) y cada fuente continua entra desde el silencio. Las bajadas son inmediatas.
- **Silencio si el motor se queda sin actualizar**: si el juego se cuelga, las fuentes en bucle
  seguirían sonando sin control; el :class:`Vigilante` calla la salida y, cuando el juego vuelve,
  el volumen sube otra vez poco a poco.
"""

from __future__ import annotations

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

import numpy as np

log = logging.getLogger(__name__)


def _acotar(valor: object, minimo: float, maximo: float, defecto: float) -> float:
	try:
		numero = float(valor)  # type: ignore[arg-type]
	except TypeError, ValueError:
		log.warning("Valor de protección auditiva no numérico: %r; se usa %s.", valor, defecto)
		return defecto
	if numero != numero:
		return defecto
	return max(minimo, min(maximo, numero))


@dataclass
class Proteccion:
	"""Límites de volumen. Los valores de serie son prudentes para auriculares."""

	techo_fuente: float = 1.0  # ganancia máxima de una fuente (tras su bus)
	techo_mezcla: float = 0.9  # ganancia maestra máxima y nivel máximo de la suma
	subida_maestro: float = 0.8  # cuánto puede subir la ganancia maestra por segundo
	subida_fuente: float = 5.0  # cuánto puede subir la ganancia de una fuente por segundo
	silencio_sin_tic: float = 0.75  # segundos sin actualizar tras los que se calla la salida

	@classmethod
	def de_dict(cls, datos: dict | None) -> Proteccion:
		"""Lee los límites de la configuración, sin dejar que nadie los quite (rangos acotados)."""
		d = dict(datos or {})
		base = cls()
		return cls(
			techo_fuente=_acotar(d.get("techo_fuente", base.techo_fuente), 0.1, 1.5, base.techo_fuente),
			techo_mezcla=_acotar(d.get("techo_mezcla", base.techo_mezcla), 0.1, 1.0, base.techo_mezcla),
			subida_maestro=_acotar(d.get("subida_maestro", base.subida_maestro), 0.1, 4.0, base.subida_maestro),
			subida_fuente=_acotar(d.get("subida_fuente", base.subida_fuente), 0.5, 50.0, base.subida_fuente),
			silencio_sin_tic=_acotar(d.get("silencio_sin_tic", base.silencio_sin_tic), 0.2, 5.0, base.silencio_sin_tic),
		)

	def a_dict(self) -> dict:
		"""Para guardar en la configuración."""
		return asdict(self)

	def limitar_fuente(self, ganancia: float) -> float:
		"""Ganancia de una fuente, entre 0 y el techo."""
		if ganancia != ganancia:
			return 0.0
		return max(0.0, min(self.techo_fuente, ganancia))

	def limitar_maestro(self, ganancia: float) -> float:
		"""Ganancia maestra, entre 0 y el techo de mezcla."""
		if ganancia != ganancia:
			return 0.0
		return max(0.0, min(self.techo_mezcla, ganancia))

	def subir(self, actual: float, objetivo: float, dt: float) -> float:
		"""Acerca la ganancia maestra a su objetivo: baja al momento, sube como mucho ``subida_maestro`` por segundo."""
		if objetivo <= actual:
			return objetivo
		return min(objetivo, actual + self.subida_maestro * max(0.0, dt))

	def subir_fuente(self, actual: float, objetivo: float, dt: float) -> float:
		"""Lo mismo para una fuente, con su propio ritmo (más rápido: son unas décimas de segundo)."""
		if objetivo <= actual:
			return objetivo
		return min(objetivo, actual + self.subida_fuente * max(0.0, dt))

	def limitar_mezcla(self, mezcla: np.ndarray) -> np.ndarray:
		"""Limitador de la suma para los motores que mezclan en Python (modifica y devuelve ``mezcla``).

		Por debajo de la rodilla (el 70 % del techo) no toca nada; por encima comprime con una tangente
		hiperbólica que nunca pasa del techo. Así muchos sonidos a la vez no recortan ni dan un golpe.
		"""
		techo = self.techo_mezcla
		rodilla = 0.7 * techo
		margen = techo - rodilla
		valor = np.abs(mezcla)
		alto = valor > rodilla
		if alto.any():
			mezcla[alto] = np.sign(mezcla[alto]) * (rodilla + margen * np.tanh((valor[alto] - rodilla) / margen))
		return mezcla


class Vigilante:
	"""Calla la salida si el juego deja de llamar a ``tic`` (se ha colgado o está bloqueado).

	El motor llama a :meth:`latido` en cada ``tic``. Un hilo comprueba cada décima de segundo cuánto
	hace del último; si pasa del límite llama a ``al_callar`` una vez, y al volver los latidos, a
	``al_volver``. En las pruebas no se arranca el hilo: se llama a :meth:`comprobar` con la hora.
	"""

	def __init__(self, limite: float, al_callar: Callable[[], None], al_volver: Callable[[], None] | None = None) -> None:
		self.limite = float(limite)
		self.al_callar = al_callar
		self.al_volver = al_volver
		self.callado = False
		self._ultimo = time.monotonic()
		self._parar = threading.Event()
		self._hilo: threading.Thread | None = None
		self._candado = threading.Lock()

	def latido(self, ahora: float | None = None) -> None:
		"""El juego sigue vivo. Si se había callado la salida, se avisa para que vuelva."""
		volver = False
		with self._candado:
			self._ultimo = time.monotonic() if ahora is None else ahora
			if self.callado:
				self.callado = False
				volver = True
		if volver:
			log.info("El juego vuelve a actualizar el sonido: se reanuda la salida.")
			if self.al_volver is not None:
				self.al_volver()

	def comprobar(self, ahora: float | None = None) -> bool:
		"""Calla la salida si toca. Devuelve si está callada."""
		ahora = time.monotonic() if ahora is None else ahora
		callar = False
		with self._candado:
			if not self.callado and ahora - self._ultimo > self.limite:
				self.callado = True
				callar = True
		if callar:
			log.warning("El sonido lleva más de %.2f s sin actualizarse: se calla la salida por seguridad.", self.limite)
			self.al_callar()
		return self.callado

	def iniciar(self) -> None:
		"""Arranca el hilo de vigilancia (una sola vez)."""
		if self._hilo is not None:
			return
		self._parar.clear()
		self._ultimo = time.monotonic()
		self._hilo = threading.Thread(target=self._vigilar, name="vigilante-sonido", daemon=True)
		self._hilo.start()

	def parar(self) -> None:
		"""Detiene el hilo."""
		self._parar.set()
		hilo, self._hilo = self._hilo, None
		if hilo is not None and hilo is not threading.current_thread():
			hilo.join(timeout=1.0)

	def _vigilar(self) -> None:
		while not self._parar.wait(0.1):
			try:
				self.comprobar()
			except Exception:  # noqa: BLE001 - el vigilante no puede morir: es la última defensa
				log.exception("Fallo en el vigilante del sonido.")
