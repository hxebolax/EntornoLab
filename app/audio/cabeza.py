"""Seguimiento de cabeza con OpenTrack, para que los sonidos se queden en su sitio al girarla.

OpenTrack (libre; con una webcam o un sensor) manda por UDP, con su salida «UDP over network», paquetes
de seis números de coma flotante de 64 bits en orden little-endian: posición x, y, z y giro (yaw),
cabeceo (pitch) y alabeo (roll), en grados. Aquí se escucha en ``127.0.0.1`` (puerto 4242, el de fábrica
de OpenTrack). El giro de la cabeza se suma al rumbo del oyente: al girar la cabeza a la derecha, lo
que sonaba delante pasa a oírse a la izquierda, como en la realidad.

Es opcional: sin OpenTrack en marcha no llega nada, ``giro()`` vale 0 y todo suena como siempre.
``centrar()`` toma la postura actual como «mirando al frente» (la webcam casi nunca está justo delante).
"""

from __future__ import annotations

import logging
import socket
import struct
import threading
import time

log = logging.getLogger(__name__)

PUERTO = 4242
CADUCA = 1.0  # segundos sin paquetes: se da la cabeza por quieta y al frente


def leer_paquete(datos: bytes) -> tuple[float, float, float, float, float, float] | None:
	"""(x, y, z, giro, cabeceo, alabeo) de un paquete de OpenTrack, o None si no lo es."""
	if len(datos) < 48:
		return None
	return struct.unpack("<6d", datos[:48])


def _normalizar(grados: float) -> float:
	"""Lleva un ángulo a -180..180."""
	return (grados + 180.0) % 360.0 - 180.0


class Cabeza:
	"""Escucha a OpenTrack en un hilo y ofrece el giro y el cabeceo de la cabeza respecto del centro."""

	def __init__(self, puerto: int = PUERTO, invertir: bool = False, direccion: str = "127.0.0.1", suavizado: float = 0.0) -> None:
		"""``invertir``: para cámaras que dan el giro al revés. ``suavizado`` (0 a 0.95): cuánto pesa el valor
		anterior en cada paquete; quita el temblor de una webcam a cambio de algo de retraso."""
		self.puerto = puerto
		self.invertir = invertir
		self.direccion = direccion
		self.suavizado = max(0.0, min(0.95, float(suavizado)))
		self._giro = 0.0
		self._cabeceo = 0.0
		self._centro_giro = 0.0
		self._centro_cabeceo = 0.0
		self._cuando = -1e9
		self._cerrojo = threading.Lock()
		self._parar = threading.Event()
		self._hilo: threading.Thread | None = None
		self._socket: socket.socket | None = None

	# ── Valores ──────────────────────────────────────────────────────────────

	def poner(self, giro: float, cabeceo: float = 0.0) -> None:
		"""Apunta una medida (grados). La llama el hilo que escucha; las pruebas, directamente."""
		if self.invertir:
			giro = -giro
		with self._cerrojo:
			reciente = time.monotonic() - self._cuando < CADUCA
			if self.suavizado > 0.0 and reciente:
				# Por el camino corto: de 179 a -179 hay dos grados, no 358.
				self._giro = _normalizar(self._giro + (1.0 - self.suavizado) * _normalizar(giro - self._giro))
				self._cabeceo += (1.0 - self.suavizado) * (cabeceo - self._cabeceo)
			else:
				self._giro = _normalizar(giro)
				self._cabeceo = float(cabeceo)
			self._cuando = time.monotonic()

	@property
	def recibiendo(self) -> bool:
		"""Si han llegado medidas en el último segundo."""
		return time.monotonic() - self._cuando < CADUCA

	def giro(self) -> float:
		"""Grados que la cabeza está girada a la derecha respecto del centro (-180 a 180); 0 si no llega nada."""
		with self._cerrojo:
			if not self.recibiendo:
				return 0.0
			return _normalizar(self._giro - self._centro_giro)

	def cabeceo(self) -> float:
		"""Grados de cabeceo respecto del centro (el signo es el de OpenTrack); 0 si no llega nada."""
		with self._cerrojo:
			if not self.recibiendo:
				return 0.0
			return self._cabeceo - self._centro_cabeceo

	def centrar(self) -> None:
		"""Toma la postura actual como «mirando al frente». Sin medidas recientes, vuelve al centro de fábrica."""
		with self._cerrojo:
			if self.recibiendo:
				self._centro_giro = self._giro
				self._centro_cabeceo = self._cabeceo
			else:
				self._centro_giro = 0.0
				self._centro_cabeceo = 0.0

	# ── Escucha ──────────────────────────────────────────────────────────────

	def iniciar(self) -> bool:
		"""Empieza a escuchar. Falso si no se puede abrir el puerto (otro programa lo usa); se registra."""
		if self._hilo is not None:
			return True
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			s.bind((self.direccion, self.puerto))
			s.settimeout(0.25)
		except OSError:
			log.warning("No se pudo escuchar a OpenTrack en %s:%s.", self.direccion, self.puerto, exc_info=True)
			return False
		self.puerto = s.getsockname()[1]  # con puerto 0, el que haya dado el sistema
		self._socket = s
		self._parar.clear()
		self._hilo = threading.Thread(target=self._escuchar, args=(s,), name="opentrack", daemon=True)
		self._hilo.start()
		log.info("Seguimiento de cabeza: escuchando a OpenTrack en %s:%s.", self.direccion, self.puerto)
		return True

	def parar(self) -> None:
		"""Deja de escuchar y libera el puerto."""
		hilo, self._hilo = self._hilo, None
		if hilo is None:
			return
		self._parar.set()
		hilo.join(timeout=2.0)
		self._socket = None

	def _escuchar(self, s: socket.socket) -> None:
		with s:
			while not self._parar.is_set():
				try:
					datos, _origen = s.recvfrom(1024)
				except TimeoutError:
					continue
				except OSError:
					log.debug("OpenTrack: fallo al recibir.", exc_info=True)
					continue
				paquete = leer_paquete(datos)
				if paquete is not None:
					self.poner(paquete[3], paquete[4])
