"""Motor 3D con BASS (Un4seen Developments), a través del paquete ``basskit`` que viaja con EntornoLab.

BASS viene incluida: la rueda recortada de ``__pip__`` (solo ``bass.dll`` y la API nativa) se instala
con ``entorno.bat instalar`` y se empaqueta con cx_Freeze. Es una alternativa al motor OpenAL, no su
sustituto: **no es binaural** (BASS no trae HRTF). Lo que hace:

- **Oyente y fuentes en 3D de BASS.** El oyente se mueve y gira por el mundo; cada fuente con posición
  es un flujo ``BASS_SAMPLE_3D``. BASS reparte entre los dos oídos con un panorama de potencia
  constante (a 90 grados el oído lejano queda mudo) y atenúa con la misma ley inversa recortada que
  el resto de motores (distancia mínima = referencia, máxima = tope, ``rolloff`` = caída).
- **Oclusión y «detrás»** con tres bandas del ecualizador paramétrico de BASS (4, 9 y 15 kHz): juntas
  hacen de paso bajo de hasta unos −36 dB por encima de 4 kHz. Se recalcula en cada fotograma, porque
  al girar el oyente cambia lo que queda detrás.
- **Protección**: volumen general de los flujos con subida gradual, vigilante que calla la salida si
  el juego deja de actualizar, y un compresor en la mezcla final (suaviza la suma de muchos sonidos;
  no es un limitador exacto).
- **Salidas**: se puede elegir por nombre, cambiar en caliente sin cortar lo que suena
  (``BASS_ChannelSetDevice``) y, sin nombre, se sigue a la salida por defecto de Windows.
- **Modo en memoria** (``{"memoria": True}``) para las pruebas: abre el dispositivo «sin sonido» de
  BASS (el 0) y captura la mezcla final con un DSP; :meth:`MotorBass.renderizar` la devuelve. BASS
  mezcla en tiempo real, así que renderizar un segundo tarda un segundo.

Sin reverberación: la acústica se recuerda, pero no se oye.

Convenio de BASS (mano izquierda): x derecha, y arriba, z adelante. Del proyecto (x este, y norte,
z arriba) se pasa con (x, z, y); mirar con rumbo ``r`` es (sen r, 0, cos r).

Licencia: BASS no es software libre y es gratuita solo para uso no comercial (ver
``data/docs/licencias/BASS.txt`` y el permiso adicional de ``LICENSE``). Quien quiera un uso comercial
sin pagar la licencia de Un4seen solo tiene que elegir otro motor y retirar ``bass.dll``: este motor
se declara entonces no disponible y la fábrica pasa al siguiente.

Parte de ``_MotorBass`` de Reconocedor de Ciudades (mismo autor).
"""

from __future__ import annotations

import ctypes
import io
import logging
import math
import os
import threading
import time
import wave
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from app.audio import salidas
from app.audio.base import (
	FRECUENCIA,
	Canal,
	ErrorMotor,
	MotorBase,
	MotorNoDisponible,
	a_mono,
	carpetas_de_serie,
	factor_detras,
	ganancias_filtro,
	mundo_a_relativo,
)
from app.audio.proteccion import Vigilante
from app.core.i18n import _

log = logging.getLogger(__name__)

# Bandas del ecualizador que apaga los agudos: (centro en Hz, ancho en semitonos). Medido con ruido
# blanco: con las tres a −15 dB, la banda de 4 a 8 kHz baja unos 36 dB y por debajo de 500 Hz, 1 dB.
BANDAS_FILTRO: tuple[tuple[float, float], ...] = ((4000.0, 30.0), (9000.0, 30.0), (15000.0, 30.0))
DECIBELIOS_BANDA = -15.0  # lo máximo que baja una banda (límite del ecualizador)
# Decibelios que bajan los agudos por cada decibelio de las tres bandas a la vez (medido).
EFECTO_BANDAS = 2.4
# Cada cuánto se mira si la salida elegida se ha ido o ha vuelto.
VIGILAR_CADA = 1.5
# Dispositivos fijos de BASS: el 0 no suena; el 1 es «la salida por defecto de Windows», y la sigue.
DISPOSITIVO_SIN_SONIDO = 0
DISPOSITIVO_DE_WINDOWS = 1
# Segundos de mezcla que se guardan como mucho en el modo en memoria si nadie los recoge.
SEGUNDOS_CAPTURA = 4.0
# El compresor de la mezcla empieza a actuar estos decibelios por debajo del techo de mezcla.
MARGEN_COMPRESOR = 6.0
CARPETA_DLL_DE_RESERVA = ("bin", "bass")
VARIABLE_DLL = "BASSKIT_DLL_PATH"


@dataclass
class _Flujo:
	"""El flujo de BASS de un canal y lo último que se le ha puesto (para no repetir llamadas)."""

	id: int
	posicionada: bool
	bandas: list[int] = field(default_factory=list)  # efectos del ecualizador; vacío si no hace falta
	decibelios: float = 0.0
	volumen: float = -1.0
	tono: float = -1.0
	posicion: tuple[float, float, float] | None = None
	atributos: tuple[int, float, float] | None = None  # modo 3D, distancia mínima y máxima
	# El WAV en memoria del que lee BASS: se retiene aquí para que siga vivo si el sonido se sustituye mientras suena.
	memoria: Any = None


@dataclass
class _Biblioteca:
	"""Lo que se usa de basskit: la API nativa, las constantes, las estructuras y el tipo del DSP."""

	bass: Any
	c: Any
	e: Any
	tipo_dsp: Any


_biblioteca_cargada: _Biblioteca | None = None

# BASS abre cada dispositivo UNA vez por proceso: un segundo ``BASS_Init`` del mismo da
# ``BASS_ERROR_ALREADY`` y comparte el abierto. Si cada motor hiciera ``BASS_Free`` al cerrar, el
# primero que cerrase dejaría al otro sin dispositivo (y sin sus flujos) mientras sigue en marcha. Se
# cuenta cuántos motores usan cada uno y solo el último lo libera.
_usos_dispositivo: dict[int, int] = {}
# Las retrollamadas DSP que BASS puede llamar todavía, por dispositivo. Una CFUNCTYPE que el
# recolector libera mientras el hilo de mezcla de BASS la sigue llamando ejecuta memoria liberada
# (cierre nativo del proceso). Se guardan aquí hasta que ``BASS_Free`` cierra ese dispositivo, aunque
# el motor que las creó ya no exista.
_retrollamadas_vivas: dict[int, list[Any]] = {}
_candado_dispositivos = threading.Lock()


def _usar_dispositivo(indice: int) -> None:
	"""Un motor más usa ese dispositivo de BASS."""
	with _candado_dispositivos:
		_usos_dispositivo[indice] = _usos_dispositivo.get(indice, 0) + 1


def _dejar_dispositivo(bass: Any, indice: int) -> bool:
	"""Un motor deja el dispositivo; si era el último, se libera de verdad. Devuelve si se liberó."""
	if indice < 0:
		return False
	with _candado_dispositivos:
		usos = _usos_dispositivo.get(indice, 0) - 1
		if usos > 0:
			_usos_dispositivo[indice] = usos
			return False
		if usos < 0:
			# No debería pasar: se registra en vez de liberar dos veces lo que otro motor usa.
			log.warning("BASS: se dejó el dispositivo %s más veces de las que se abrió; no se libera de nuevo.", indice)
			return False
		_usos_dispositivo.pop(indice, None)
		liberado = False
		if bass.BASS_SetDevice(indice):
			# BASS_Free para el hilo de mezcla de ese dispositivo: después ya nadie llama a sus DSP.
			liberado = bool(bass.BASS_Free())
		_retrollamadas_vivas.pop(indice, None)
		return liberado


def _asegurar_dll() -> None:
	"""Si a basskit le falta su ``bass.dll``, le indica la de ``data/bin/bass`` (si alguien la puso allí).

	basskit busca la DLL dentro de su propio paquete (``basskit/data/dlls/x64``), que es donde viaja
	tanto desde el código como compilado (el paquete va fuera del zip de bibliotecas). La carpeta de
	reserva permite reponer o sustituir la DLL sin tocar las bibliotecas del programa.
	"""
	if os.environ.get(VARIABLE_DLL):
		return
	from basskit import rutas

	try:
		propia: Path | None = rutas.obtener_directorio_dlls()
	except FileNotFoundError:
		propia = None
	if propia is not None and (propia / "bass.dll").is_file():
		return
	for carpeta in carpetas_de_serie(*CARPETA_DLL_DE_RESERVA):
		if (carpeta / "bass.dll").is_file():
			os.environ[VARIABLE_DLL] = str(carpeta)
			log.info("bass.dll no está en el paquete basskit; se usa la de %s.", carpeta)
			return


def _biblioteca() -> _Biblioteca:
	"""Carga basskit y ``bass.dll`` (sin abrir ningún dispositivo). Lanza :class:`MotorNoDisponible`."""
	global _biblioteca_cargada
	if _biblioteca_cargada is not None:
		return _biblioteca_cargada
	try:
		import basskit
		from basskit import constantes
		from basskit.callbacks.bass import DSPPROC
		from basskit.dlls.bass import bass
		from basskit.estructuras import bass as estructuras
	except ImportError as error:
		raise MotorNoDisponible(
			_(
				"Falta el paquete basskit, que viene con EntornoLab. Desde el código fuente se instala con "
				"«entorno.bat instalar»; en la versión compilada, vuelva a descomprimir el programa."
			)
		) from error
	try:
		_asegurar_dll()
		version = int(bass.BASS_GetVersion())
		# Nombres de dispositivo en UTF-8 y una entrada «Default» (la 1) que sigue a la salida de Windows.
		bass.BASS_SetConfig(constantes.BASS_CONFIG_UNICODE, 1)
		bass.BASS_SetConfig(constantes.BASS_CONFIG_DEV_DEFAULT, 1)
	except (OSError, AttributeError, basskit.BassKitError) as error:
		raise MotorNoDisponible(
			_("No se pudo cargar bass.dll ({error}). Si la ha retirado, elija otro motor de sonido.").format(error=error)
		) from error
	log.debug("bass.dll cargada: versión %s.", _texto_version(version))
	_biblioteca_cargada = _Biblioteca(bass, constantes, estructuras, DSPPROC)
	return _biblioteca_cargada


def _texto_version(version: int) -> str:
	"""La versión de BASS como «2.4.18.23»."""
	return f"{version >> 24 & 255}.{version >> 16 & 255}.{version >> 8 & 255}.{version & 255}"


def _wav(datos: np.ndarray) -> bytes:
	"""Las muestras como un fichero WAV de 16 bits en memoria, que es lo que BASS sabe abrir."""
	pcm = np.ascontiguousarray(np.clip(datos, -1.0, 1.0) * 32767.0, dtype=np.int16)
	memoria = io.BytesIO()
	with wave.open(memoria, "wb") as w:
		w.setnchannels(1 if pcm.ndim == 1 else 2)
		w.setsampwidth(2)
		w.setframerate(FRECUENCIA)
		w.writeframes(pcm.tobytes())
	return memoria.getvalue()


def decibelios_de_banda(agudos: float) -> float:
	"""Ganancia de cada banda del ecualizador para que los agudos queden en ``agudos`` (de 0 a 1).

	Las tres bandas se solapan y suman: por eso a cada una le toca solo una parte de la bajada.
	"""
	objetivo = 20.0 * math.log10(max(float(agudos), 1e-3))
	return max(DECIBELIOS_BANDA, min(0.0, objetivo / EFECTO_BANDAS))


class MotorBass(MotorBase):
	"""BASS en 3D (sin HRTF), incluido con EntornoLab. Elegible en las preferencias."""

	nombre = "bass"
	FUENTES_MAXIMAS = 48

	def __init__(self) -> None:
		super().__init__()
		self._b: _Biblioteca | None = None
		self._bass: Any = None
		self._c: Any = None
		self.memoria = False
		self.version = ""
		self.dispositivo_pedido = ""
		self.nombre_salida = ""
		self._indice = -1  # dispositivo de BASS abierto; -1 si ninguno
		self._memoria: dict[tuple[str, bool], Any] = {}
		self._con_ecualizador = True
		self._flujo_salida = 0  # flujo «de dispositivo»: la mezcla final, para el compresor y la captura
		self._compresor = 0
		self._dsp: Any = None  # la retrollamada de captura; hay que conservarla mientras BASS la use
		self._dsp_puesto = 0  # el HDSP que devolvió BASS, para quitarlo si el dispositivo sigue abierto
		self._captura: deque[bytes] = deque()
		self._bytes_captura = 0
		self._canales_salida = 2
		self._candado = threading.Lock()
		self._sucio_3d = False
		self._t_vigila = 0.0
		self.vigilante: Vigilante | None = None

	@classmethod
	def disponible(cls) -> tuple[bool, str]:
		"""Si están basskit y ``bass.dll``. Carga la DLL, pero no abre ningún dispositivo."""
		try:
			_biblioteca()
		except MotorNoDisponible as error:
			return False, str(error)
		return True, ""

	# ── Dispositivos ──

	def _vector(self, x: float, y: float, z: float) -> Any:
		"""Un ``BASS_3DVECTOR`` con esas coordenadas (ya en el convenio de BASS)."""
		vector = self._b.e.BASS_3DVECTOR()  # type: ignore[union-attr]
		vector.x = float(x)
		vector.y = float(y)
		vector.z = float(z)
		return vector

	@staticmethod
	def _enumerar(b: _Biblioteca) -> list[tuple[int, str, int]]:
		"""(índice, nombre, banderas) de las salidas reales que BASS ve, estén conectadas o no."""
		lista: list[tuple[int, str, int]] = []
		info = b.e.BASS_DEVICEINFO()
		indice = DISPOSITIVO_DE_WINDOWS + 1
		while b.bass.BASS_GetDeviceInfo(indice, ctypes.byref(info)):
			nombre = (info.name or b"").decode("utf-8", errors="replace").strip()
			if nombre:
				lista.append((indice, nombre, int(info.flags)))
			indice += 1
		return lista

	def dispositivos(self) -> list[str]:
		"""Nombres de las salidas conectadas que BASS puede abrir (sin «sin sonido» ni «por defecto»)."""
		try:
			b = _biblioteca()
		except MotorNoDisponible:
			log.warning("No se pudo cargar BASS para listar las salidas.", exc_info=True)
			return []
		return [nombre for _i, nombre, banderas in self._enumerar(b) if banderas & b.c.BASS_DEVICE_ENABLED]

	def _indice_de(self, nombre: str) -> int | None:
		"""El dispositivo de BASS de una salida guardada; el de Windows si va vacío; None si no está conectada.

		El nombre puede venir de otro motor (el corto de Windows, o con «OpenAL Soft on »): se compara
		por el principio.
		"""
		if not nombre:
			return DISPOSITIVO_DE_WINDOWS
		b = self._b or _biblioteca()
		conectadas = [(i, n) for i, n, banderas in self._enumerar(b) if banderas & b.c.BASS_DEVICE_ENABLED]
		for indice, candidato in conectadas:
			if candidato == nombre:
				return indice
		for indice, candidato in conectadas:
			if salidas.coincide(nombre, candidato):
				return indice
		return None

	def _nombre_de(self, indice: int) -> str:
		"""Nombre de la salida real que hay detrás de un dispositivo de BASS («» si no suena)."""
		if indice == DISPOSITIVO_SIN_SONIDO or self._b is None:
			return ""
		for i, nombre, banderas in self._enumerar(self._b):
			if i == indice or (indice == DISPOSITIVO_DE_WINDOWS and banderas & self._b.c.BASS_DEVICE_DEFAULT):
				return nombre
		return ""

	def _abrir(self, indice: int) -> bool:
		"""``BASS_Init`` de ese dispositivo y lo deja como el del hilo. False si BASS no puede abrirlo."""
		bass, c = self._bass, self._c
		# Estéreo aunque la salida tenga más altavoces: el reparto entre los dos oídos es la pista.
		banderas = c.BASS_DEVICE_3D | c.BASS_DEVICE_STEREO
		if not bass.BASS_Init(indice, FRECUENCIA, banderas, 0, None):
			codigo = bass.BASS_ErrorGetCode()
			if codigo != c.BASS_ERROR_ALREADY:
				log.warning("BASS no pudo abrir el dispositivo %s (error %s).", indice, codigo)
				return False
		_usar_dispositivo(indice)
		if not bass.BASS_SetDevice(indice):
			log.warning("BASS no pudo seleccionar el dispositivo %s (error %s).", indice, bass.BASS_ErrorGetCode())
			_dejar_dispositivo(bass, indice)
			return False
		self._indice = indice
		self.nombre_salida = self._nombre_de(indice)
		return True

	def _preparar_dispositivo(self) -> None:
		"""Lo que hay que poner en cada dispositivo recién abierto: factores 3D, oyente, compresor y captura."""
		bass, c = self._bass, self._c
		self._poner_factores()
		self._dsp_puesto = 0
		self._flujo_salida = bass.BASS_StreamCreate(0, 0, 0, c.STREAMPROC_DEVICE, None)
		self._compresor = 0
		if not self._flujo_salida:
			log.info("BASS no da acceso a la mezcla final (error %s): sin compresor.", bass.BASS_ErrorGetCode())
		else:
			self._compresor = bass.BASS_ChannelSetFX(self._flujo_salida, c.BASS_FX_DX8_COMPRESSOR, 0)
			if not self._compresor:
				log.info("Sin compresor en la mezcla de BASS (error %s).", bass.BASS_ErrorGetCode())
			self._poner_compresor()
		if self.memoria:
			self._preparar_captura()
		self._sucio_3d = True
		self._oyente_cambiado()

	def _poner_factores(self) -> None:
		"""Metros, la caída de la distancia configurada y sin efecto Doppler (confundiría más que ayudaría)."""
		if not self._bass.BASS_Set3DFactors(1.0, float(min(self.caida, 10.0)), 0.0):
			log.warning("BASS no aceptó los factores 3D (error %s).", self._bass.BASS_ErrorGetCode())
		self._sucio_3d = True

	def _poner_compresor(self) -> None:
		"""Compresor de la mezcla final: actúa cuando la suma se acerca al techo de mezcla."""
		if not self._compresor:
			return
		parametros = self._b.e.BASS_DX8_COMPRESSOR()  # type: ignore[union-attr]
		parametros.fGain = 0.0
		parametros.fAttack = 0.01
		parametros.fRelease = 200.0
		parametros.fThreshold = max(-60.0, 20.0 * math.log10(max(self.proteccion.techo_mezcla, 0.01)) - MARGEN_COMPRESOR)
		parametros.fRatio = 20.0
		parametros.fPredelay = 4.0
		if not self._bass.BASS_FXSetParameters(self._compresor, ctypes.byref(parametros)):
			log.warning("BASS no aceptó los parámetros del compresor (error %s).", self._bass.BASS_ErrorGetCode())

	def _preparar_captura(self) -> None:
		"""Modo en memoria: un DSP al final de la mezcla copia lo que llegaría a la tarjeta."""
		bass = self._bass
		if not self._flujo_salida:
			raise ErrorMotor("esta BASS no da acceso a la mezcla final: no hay modo en memoria")
		info = self._b.e.BASS_CHANNELINFO()  # type: ignore[union-attr]
		if not bass.BASS_ChannelGetInfo(self._flujo_salida, ctypes.byref(info)):
			raise ErrorMotor(f"BASS no informa del formato de la mezcla (error {bass.BASS_ErrorGetCode()})")
		if not int(info.flags) & self._c.BASS_SAMPLE_FLOAT:
			raise ErrorMotor("la mezcla de BASS no es de coma flotante: no hay modo en memoria")
		self._canales_salida = max(1, int(info.chans))
		self._dsp = self._b.tipo_dsp(self._capturar)  # type: ignore[union-attr]
		# Viva hasta que se libere el dispositivo, no solo lo que viva este motor (ver _retrollamadas_vivas).
		with _candado_dispositivos:
			_retrollamadas_vivas.setdefault(self._indice, []).append(self._dsp)
		# Prioridad mínima: después del compresor, para medir lo mismo que se oiría.
		self._dsp_puesto = int(bass.BASS_ChannelSetDSP(self._flujo_salida, self._dsp, None, -1000) or 0)
		if not self._dsp_puesto:
			raise ErrorMotor(f"BASS no pudo poner el DSP de captura (error {bass.BASS_ErrorGetCode()})")

	def _capturar(self, _dsp: int, _canal: int, bufer: int, cuantos: int, _usuario: int) -> None:
		"""Lo llama BASS desde su hilo de mezcla con cada bloque de la mezcla final."""
		bloque = ctypes.string_at(bufer, cuantos)
		limite = int(SEGUNDOS_CAPTURA * FRECUENCIA) * 4 * self._canales_salida
		with self._candado:
			self._captura.append(bloque)
			self._bytes_captura += len(bloque)
			while self._bytes_captura > limite and len(self._captura) > 1:
				self._bytes_captura -= len(self._captura.popleft())

	def iniciar(self, dispositivo: str | None, opciones: dict) -> None:
		"""Abre la salida pedida (o la de Windows, o ninguna en memoria) en 3D y estéreo."""
		if self._iniciado:
			self.cerrar()
		self._leer_opciones(opciones)
		self._b = _biblioteca()
		self._bass, self._c = self._b.bass, self._b.c
		self.memoria = bool(self.opciones.get("memoria", False))
		self.dispositivo_pedido = "" if self.memoria else str(dispositivo or "")
		if self.memoria:
			indice: int | None = DISPOSITIVO_SIN_SONIDO
		else:
			indice = self._indice_de(self.dispositivo_pedido)
			if indice is None:
				log.warning("La salida de sonido «%s» no está conectada; BASS usa la de Windows.", self.dispositivo_pedido)
				indice = DISPOSITIVO_DE_WINDOWS
		if not self._abrir(indice):
			codigo = self._bass.BASS_ErrorGetCode()
			if indice in (DISPOSITIVO_SIN_SONIDO, DISPOSITIVO_DE_WINDOWS) or not self._abrir(DISPOSITIVO_DE_WINDOWS):
				raise ErrorMotor(f"BASS_Init falló con el error {codigo}")
		self.version = _texto_version(int(self._bass.BASS_GetVersion()))
		# El volumen general arranca en silencio y lo sube ``tic`` poco a poco.
		self._bass.BASS_SetConfig(self._c.BASS_CONFIG_GVOL_STREAM, 0)
		self._con_ecualizador = True
		self._iniciado = True
		try:
			self._preparar_dispositivo()
		except ErrorMotor:
			self.cerrar()
			raise
		self.vigilante = Vigilante(self.proteccion.silencio_sin_tic, self._callar_por_seguridad, self._volver_de_silencio)
		if not self.memoria:
			self.vigilante.iniciar()
		self._t_vigila = time.monotonic()
		log.info("BASS %s iniciado en 3D. Salida: %s.", self.version, self.nombre_salida or "en memoria (sin sonido)")

	def cambiar_dispositivo(self, dispositivo: str | None) -> bool:
		"""Lleva lo que suena a otra salida sin cortarlo (vacío: la de Windows). False si no está conectada."""
		self.dispositivo_pedido = str(dispositivo or "")
		if not self._iniciado or self.memoria:
			return False
		destino = self._indice_de(self.dispositivo_pedido)
		if destino is None:
			log.warning("La salida de sonido «%s» no está conectada; BASS sigue en «%s».", self.dispositivo_pedido, self.nombre_salida)
			return False
		return self._mudar(destino, "cambiada en las preferencias")

	def _mudar(self, destino: int, motivo: str) -> bool:
		"""Abre ``destino``, pasa a él todos los flujos y cierra el dispositivo anterior."""
		if destino == self._indice:
			return True
		bass = self._bass
		anterior, antes = self._indice, self.nombre_salida
		mezcla_anterior = (self._flujo_salida, self._compresor, self._dsp_puesto)
		if not self._abrir(destino):
			bass.BASS_SetDevice(anterior)
			return False
		self._preparar_dispositivo()
		for canal in self._canales.values():
			flujo: _Flujo | None = canal.interno
			if flujo is not None and not bass.BASS_ChannelSetDevice(flujo.id, destino):
				log.warning("BASS no pudo pasar %s a la nueva salida (error %s).", canal.nombre, bass.BASS_ErrorGetCode())
		# Al cerrar el anterior se liberan su flujo de mezcla y lo que no se haya podido pasar; si otro
		# motor lo sigue usando, solo se quita lo de este (su compresor y su captura).
		self._soltar_mezcla(anterior, mezcla_anterior)
		bass.BASS_SetDevice(destino)
		bass.BASS_Apply3D()
		log.info("Salida de sonido de BASS cambiada (%s): antes «%s», ahora «%s».", motivo, antes, self.nombre_salida)
		return True

	def _vigilar_salida(self) -> None:
		"""Cada poco: si la salida elegida se ha desconectado se pasa a la de Windows, y si ha vuelto, a ella.

		La salida «de Windows» no necesita vigilancia: BASS la sigue sola cuando el usuario la cambia.
		"""
		ahora = time.monotonic()
		if self.memoria or ahora - self._t_vigila < VIGILAR_CADA:
			return
		self._t_vigila = ahora
		if not self.dispositivo_pedido:
			return
		elegida = self._indice_de(self.dispositivo_pedido)
		if elegida is None and self._indice != DISPOSITIVO_DE_WINDOWS:
			self._mudar(DISPOSITIVO_DE_WINDOWS, "se ha desconectado la elegida")
		elif elegida is not None and elegida != self._indice:
			self._mudar(elegida, "ha vuelto la elegida")

	def configurar(self, opciones: dict) -> None:
		"""Lo común y, además, la caída de la distancia y el umbral del compresor."""
		super().configurar(opciones)
		if self._iniciado:
			self._poner_factores()
			self._poner_compresor()

	# ── Oyente y sonidos ──

	def _oyente_cambiado(self) -> None:
		if not self._iniciado:
			return
		x, y, z, rumbo = self._oyente
		r = math.radians(rumbo)
		hecho = self._bass.BASS_Set3DPosition(
			ctypes.byref(self._vector(x, z, y)),
			None,
			ctypes.byref(self._vector(math.sin(r), 0.0, math.cos(r))),
			ctypes.byref(self._vector(0.0, 1.0, 0.0)),
		)
		if not hecho:
			log.debug("BASS no aceptó la posición del oyente (error %s).", self._bass.BASS_ErrorGetCode())
		self._sucio_3d = True

	def _sonido_cambiado(self, nombre: str) -> None:
		for clave in [c for c in self._memoria if c[0] == nombre]:
			self._memoria.pop(clave, None)

	def _empezar(self, canal: Canal) -> bool:
		datos = self._datos(canal.nombre)
		if datos is None:
			return False
		bass, c = self._bass, self._c
		posicionada = canal.pos is not None or canal.relativo is not None
		# BASS solo sitúa en 3D sonidos de un canal; y con «mono» los dos oídos oyen lo mismo.
		un_canal = posicionada or self.mono
		clave = (canal.nombre, un_canal)
		memoria = self._memoria.get(clave)
		if memoria is None:
			contenido = _wav(a_mono(datos) if un_canal else datos)
			memoria = self._memoria[clave] = ctypes.create_string_buffer(contenido, len(contenido))
		banderas = (c.BASS_SAMPLE_3D if posicionada else 0) | (c.BASS_SAMPLE_LOOP if canal.bucle else 0)
		flujo = bass.BASS_StreamCreateFile(1, memoria, 0, len(memoria), banderas)
		if not flujo:
			log.warning("BASS no pudo crear el flujo de %s (error %s).", canal.nombre, bass.BASS_ErrorGetCode())
			return False
		# Sin búfer propio: los cambios de filtro y de tono se oyen al momento, no medio segundo después.
		bass.BASS_ChannelSetAttribute(flujo, c.BASS_ATTRIB_BUFFER, 0.0)
		canal.interno = _Flujo(flujo, posicionada, memoria=memoria)
		self._aplicar(canal)
		if posicionada:
			bass.BASS_Apply3D()
			self._sucio_3d = False
		if not canal.pausado and not bass.BASS_ChannelPlay(flujo, 0):
			log.warning("BASS no pudo hacer sonar %s (error %s).", canal.nombre, bass.BASS_ErrorGetCode())
			self._detener(canal)
			return False
		return True

	def _situar(self, canal: Canal, flujo: _Flujo) -> float | None:
		"""Pone el flujo en su sitio del espacio de BASS y devuelve el ángulo respecto del oyente."""
		bass, c = self._bass, self._c
		angulo: float | None
		if canal.pos is not None:
			angulo, distancia, altura = mundo_a_relativo(self._oyente, canal.pos)
			if self.mono:
				# Delante del oyente, a su distancia: se conserva el volumen y se pierde el lado.
				modo, posicion = c.BASS_3DMODE_RELATIVE, (0.0, 0.0, math.hypot(distancia, altura))
			else:
				modo, posicion = c.BASS_3DMODE_NORMAL, (canal.pos[0], canal.pos[2], canal.pos[1])
		else:
			angulo, distancia = canal.relativo  # type: ignore[misc]
			r = math.radians(0.0 if self.mono else angulo)
			modo, posicion = c.BASS_3DMODE_RELATIVE, (math.sin(r) * distancia, 0.0, math.cos(r) * distancia)
		atributos = (int(modo), float(self.referencia), float(self.maxima))
		if atributos != flujo.atributos:
			# Sin conos ni volumen exterior (-1 = como estén); más allá de la máxima deja de bajar, no se corta.
			if bass.BASS_ChannelSet3DAttributes(flujo.id, atributos[0], atributos[1], atributos[2], -1, -1, -1.0):
				flujo.atributos = atributos
				self._sucio_3d = True
			else:
				log.debug("BASS no aceptó los atributos 3D de %s (error %s).", canal.nombre, bass.BASS_ErrorGetCode())
		if posicion != flujo.posicion:
			if bass.BASS_ChannelSet3DPosition(flujo.id, ctypes.byref(self._vector(*posicion)), None, None):
				flujo.posicion = posicion
				self._sucio_3d = True
			else:
				log.debug("BASS no aceptó la posición de %s (error %s).", canal.nombre, bass.BASS_ErrorGetCode())
		return angulo

	def _aplicar(self, canal: Canal) -> None:
		flujo: _Flujo | None = canal.interno
		if flujo is None:
			return
		bass, c = self._bass, self._c
		angulo = self._situar(canal, flujo) if flujo.posicionada else None
		general, agudos = ganancias_filtro(canal.filtro, factor_detras(angulo), self.refuerzo_detras)
		volumen = max(0.0, canal.ganancia * general)
		if volumen != flujo.volumen:
			bass.BASS_ChannelSetAttribute(flujo.id, c.BASS_ATTRIB_VOL, volumen)
			flujo.volumen = volumen
		if canal.tono != flujo.tono:
			bass.BASS_ChannelSetAttribute(flujo.id, c.BASS_ATTRIB_FREQ, FRECUENCIA * canal.tono)
			flujo.tono = canal.tono
		self._poner_ecualizador(flujo, agudos)

	def _poner_ecualizador(self, flujo: _Flujo, agudos: float) -> None:
		"""Tres bandas del ecualizador de BASS que bajan los agudos según la oclusión y lo de detrás."""
		if not self._con_ecualizador:
			return
		decibelios = decibelios_de_banda(agudos)
		if abs(decibelios - flujo.decibelios) < 0.2:
			return
		bass, c = self._bass, self._c
		if not flujo.bandas:
			for _banda in BANDAS_FILTRO:
				efecto = bass.BASS_ChannelSetFX(flujo.id, c.BASS_FX_DX8_PARAMEQ, 0)
				if not efecto:
					self._con_ecualizador = False
					log.warning("Sin filtro de agudos en BASS (BASS_ChannelSetFX: error %s).", bass.BASS_ErrorGetCode())
					for puesto in flujo.bandas:
						bass.BASS_ChannelRemoveFX(flujo.id, puesto)
					flujo.bandas = []
					return
				flujo.bandas.append(efecto)
		flujo.decibelios = decibelios
		for efecto, (centro, ancho) in zip(flujo.bandas, BANDAS_FILTRO, strict=True):
			parametros = self._b.e.BASS_DX8_PARAMEQ()  # type: ignore[union-attr]
			parametros.fCenter = centro
			parametros.fBandwidth = ancho
			parametros.fGain = decibelios
			if not bass.BASS_FXSetParameters(efecto, ctypes.byref(parametros)):
				log.debug("BASS no aceptó una banda del ecualizador (error %s).", bass.BASS_ErrorGetCode())

	def _detener(self, canal: Canal) -> None:
		flujo: _Flujo | None = canal.interno
		canal.interno = None
		if flujo is not None and self._bass is not None:
			# Liberar el flujo lo para y suelta también sus efectos.
			self._bass.BASS_StreamFree(flujo.id)

	def _sigue(self, canal: Canal) -> bool:
		flujo: _Flujo | None = canal.interno
		if flujo is None:
			return False
		return canal.pausado or self._bass.BASS_ChannelIsActive(flujo.id) != self._c.BASS_ACTIVE_STOPPED

	def _pausar_canal(self, canal: Canal, si: bool) -> None:
		flujo: _Flujo | None = canal.interno
		if flujo is None:
			return
		if si:
			self._bass.BASS_ChannelPause(flujo.id)
		else:
			self._bass.BASS_ChannelPlay(flujo.id, 0)

	# ── Por fotograma ──

	def tic(self, dt: float) -> None:
		"""Además de lo común: vigilante, salida, 3D de una vez y volumen general (de 0 a 10000 en BASS)."""
		if not self._iniciado:
			return
		if self.vigilante is not None:
			self.vigilante.latido()
		self._vigilar_salida()
		super().tic(dt)
		if self._sucio_3d:
			# BASS guarda los cambios de posición y los aplica todos juntos aquí.
			self._bass.BASS_Apply3D()
			self._sucio_3d = False
		self._bass.BASS_SetConfig(self._c.BASS_CONFIG_GVOL_STREAM, int(10000 * min(1.0, self._maestro)))

	def _callar_por_seguridad(self) -> None:
		"""Lo llama el vigilante (desde su hilo) si el juego deja de actualizar el sonido."""
		if self._bass is not None:
			self._bass.BASS_SetConfig(self._c.BASS_CONFIG_GVOL_STREAM, 0)

	def _volver_de_silencio(self) -> None:
		self._maestro = 0.0

	def renderizar(self, muestras: int) -> np.ndarray:
		"""Solo en memoria: las siguientes ``muestras`` de la mezcla, forma (muestras, 2), izquierda y derecha.

		BASS mezcla en tiempo real también en el dispositivo sin sonido: esta llamada espera lo que
		duren esas muestras. Lo anterior a la llamada se descarta.
		"""
		if not self.memoria or not self._iniciado:
			raise ErrorMotor("renderizar solo funciona con el motor en memoria")
		muestras = max(1, int(muestras))
		necesarios = muestras * 4 * self._canales_salida
		with self._candado:
			self._captura.clear()
			self._bytes_captura = 0
		limite = time.monotonic() + muestras / FRECUENCIA * 4.0 + 2.0
		while True:
			with self._candado:
				if self._bytes_captura >= necesarios:
					contenido = b"".join(self._captura)
					break
			if time.monotonic() > limite:
				raise ErrorMotor("BASS no entrega la mezcla en memoria (el dispositivo sin sonido no avanza)")
			time.sleep(0.004)
		mezcla = np.frombuffer(contenido, dtype=np.float32).reshape(-1, self._canales_salida)[:muestras]
		if self._canales_salida == 1:
			mezcla = np.repeat(mezcla, 2, axis=1)
		return np.array(mezcla[:, :2], dtype=np.float32)

	def _soltar_mezcla(self, indice: int, mezcla: tuple[int, int, int]) -> None:
		"""Deja el dispositivo ``indice``: lo libera si nadie más lo usa; si no, quita solo el compresor y la captura de este motor.

		El flujo de la mezcla final (``STREAMPROC_DEVICE``) es uno por dispositivo y lo comparten
		todos los motores que lo tengan abierto; por eso no se libera aquí.
		"""
		bass = self._bass
		if _dejar_dispositivo(bass, indice):
			return
		flujo_salida, compresor, dsp = mezcla
		if flujo_salida and bass.BASS_SetDevice(indice):
			if dsp and not bass.BASS_ChannelRemoveDSP(flujo_salida, dsp):
				log.debug("BASS no quitó el DSP de captura (error %s).", bass.BASS_ErrorGetCode())
			if compresor and not bass.BASS_ChannelRemoveFX(flujo_salida, compresor):
				log.debug("BASS no quitó el compresor (error %s).", bass.BASS_ErrorGetCode())

	def cerrar(self) -> None:
		"""Para todo y deja el dispositivo de BASS (lo libera si era el último motor). Se puede llamar más de una vez.

		Orden: primero los flujos (que leen de ``_memoria``), después el dispositivo (que para el hilo
		de mezcla y con él las llamadas al DSP) y por último la memoria de Python. La retrollamada DSP
		no se suelta aquí: queda en ``_retrollamadas_vivas`` hasta que se libere el dispositivo.
		"""
		if self.vigilante is not None:
			self.vigilante.parar()
			self.vigilante = None
		if self._iniciado:
			self.parar_todo()
			self._soltar_mezcla(self._indice, (self._flujo_salida, self._compresor, self._dsp_puesto))
			log.info("Motor BASS cerrado.")
		self._iniciado = False
		self._indice = -1
		self._flujo_salida = 0
		self._compresor = 0
		self._dsp_puesto = 0
		self._dsp = None
		self.nombre_salida = ""
		self._memoria.clear()
		with self._candado:
			self._captura.clear()
			self._bytes_captura = 0

	def estado(self) -> dict:
		"""Lo común más la versión, la salida y lo que BASS ha aceptado; no hay HRTF ni reverberación."""
		datos = super().estado()
		datos.update(
			{
				"version": self.version,
				"frecuencia": FRECUENCIA,
				"hrtf_activo": False,
				"reverberacion": False,
				"dispositivo": self.nombre_salida,
				"filtro": self._con_ecualizador,
				"compresor": bool(self._compresor),
				"memoria": self.memoria,
			}
		)
		return datos
