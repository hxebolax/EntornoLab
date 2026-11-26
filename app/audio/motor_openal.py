"""Motor principal: OpenAL Soft por ctypes, con sonido binaural (HRTF) para auriculares.

Cada sonido pasa por la respuesta de una cabeza medida (HRTF): llega a cada oído con su retardo, su
diferencia de nivel y el timbre que da la oreja según venga de delante, de detrás, de arriba o de
abajo. Con auriculares se distingue de verdad delante de detrás. La mezcla la hace la biblioteca en
código nativo, fuera de Python.

Lo que hace este motor (y de dónde sale, de los dos proyectos del autor):

- **HRTF pedido y verificado** (Reconocedor de Ciudades): se pide por atributos ALC y después se
  consulta ``ALC_HRTF_STATUS_SOFT``; el estado real queda en ``hrtf_activo`` y en el registro.
- **Perfiles de cabeza** elegibles en caliente (``cabeza``), con ``alcResetDeviceSOFT``.
- **Oyente que se mueve y gira** y fuentes ancladas al mundo, actualizadas cada fotograma (Puerto
  Bravo). Conversión de coordenadas: proyecto (x este, y norte, z arriba) → OpenAL (x, z, −y); mirar
  con rumbo ``r`` es el vector (sen r, 0, −cos r).
- **Reserva de fuentes** con prioridades: si no quedan, se roba la menos importante.
- **Filtro paso bajo EFX por fuente**: oclusión (``filtro``) combinada con el refuerzo «detrás».
- **Reverberación EFX** con un preset por acústica y fundido entre dos ranuras al cambiar de lugar.
- **Distancia**: ``AL_INVERSE_DISTANCE_CLAMPED`` con los mismos parámetros que
  :func:`app.audio.base.ganancia_distancia`.
- **Cambio de salida en caliente** (``alcReopenDeviceSOFT``) y seguimiento de la salida de Windows.
- **Modo en memoria** (loopback) para las pruebas: no abre la tarjeta y :meth:`renderizar` devuelve
  lo que llegaría a cada oído.
- **Altavoces**: modo estéreo sin HRTF (``salida = "altavoces"``).
"""

from __future__ import annotations

import ctypes
import logging
import math
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.audio import _openal as o
from app.audio import salidas
from app.audio.base import (
	ACUSTICAS,
	FRECUENCIA,
	Canal,
	ErrorMotor,
	MotorBase,
	MotorNoDisponible,
	a_mono,
	factor_detras,
	ganancias_filtro,
	mundo_a_relativo,
	recortar,
)
from app.audio.proteccion import Vigilante
from app.core.i18n import N_, _

log = logging.getLogger(__name__)

# Perfiles de cabeza: «» es el que trae OpenAL Soft dentro; los demás, ficheros .mhr de data/bin/openal/hrtf.
CABEZAS: dict[str, str] = {
	"": N_("la integrada"),
	"kemar_oreja_normal": N_("maniquí con oreja normal"),
	"kemar_oreja_grande": N_("maniquí con oreja grande"),
	"ku100": N_("cabeza artificial de estudio"),
	"persona_1": N_("persona 1"),
	"persona_2": N_("persona 2"),
	"persona_3": N_("persona 3"),
	"persona_4": N_("persona 4"),
}

SALIDAS = ("auriculares", "altavoces")
VIGILAR_CADA = 1.5  # segundos entre dos miradas a la salida de sonido
TRANSICION_ECO = 0.6  # segundos del fundido entre dos reverberaciones


@dataclass(frozen=True)
class Reverberacion:
	"""Parámetros EFX de una acústica. ``envio`` es cuánto eco se oye (ganancia de la ranura)."""

	envio: float
	cola: float  # segundos que tarda en apagarse
	brillo: float  # agudos del eco (0 a 1)
	cola_agudos: float  # cuánto duran los agudos respecto de la cola
	primeras: float  # nivel de las primeras reflexiones
	retardo_primeras: float  # segundos: más grande, paredes más lejos
	tardias: float  # nivel de la cola
	retardo_tardias: float
	densidad: float = 1.0
	difusion: float = 1.0


# Un preset por acústica de docs/arquitectura.md. Valores suaves: el eco informa del lugar, no adorna.
PRESETS: dict[str, Reverberacion] = {
	"seca": Reverberacion(0.0, 0.3, 0.5, 0.5, 0.05, 0.005, 0.3, 0.01),
	"habitacion": Reverberacion(0.32, 0.5, 0.6, 0.6, 0.35, 0.004, 0.9, 0.008),
	"sala_grande": Reverberacion(0.40, 1.4, 0.7, 0.75, 0.25, 0.012, 1.1, 0.02),
	"pasillo": Reverberacion(0.40, 0.9, 0.75, 0.6, 0.45, 0.006, 1.0, 0.012, difusion=0.6),
	"bano": Reverberacion(0.45, 1.1, 0.9, 0.9, 0.6, 0.003, 1.2, 0.007),
	"escalera": Reverberacion(0.45, 2.0, 0.7, 0.7, 0.4, 0.01, 1.2, 0.02),
	"nave": Reverberacion(0.50, 3.0, 0.6, 0.6, 0.2, 0.02, 1.3, 0.03),
	"exterior": Reverberacion(0.05, 0.7, 0.4, 0.5, 0.02, 0.02, 0.5, 0.03, densidad=0.5),
	"calle": Reverberacion(0.18, 1.1, 0.6, 0.6, 0.08, 0.02, 0.9, 0.03, densidad=0.7),
	"parque": Reverberacion(0.08, 0.9, 0.4, 0.5, 0.03, 0.025, 0.7, 0.04, densidad=0.5),
}

# El contexto de OpenAL es global al proceso: se recuerda cuál está puesto para no repetir la llamada.
_contexto_actual: int | None = None


def cabezas_disponibles() -> list[str]:
	"""«» (la integrada) y los perfiles que hay en ``data/bin/openal/hrtf``, los conocidos primero."""
	orden = list(CABEZAS)
	return ["", *sorted(o.cabezas_en_disco(), key=lambda c: (orden.index(c) if c in orden else 99, c))]


def nombre_cabeza(cabeza: str) -> str:
	"""Nombre para mostrar de un perfil de cabeza; el del fichero si es uno añadido por el usuario."""
	texto = CABEZAS.get(cabeza)
	return _(texto) if texto is not None else cabeza


@dataclass
class _Fuente:
	"""Lo que el motor recuerda de la fuente de OpenAL de un canal, para no repetir llamadas."""

	id: int
	posicionada: bool
	filtro_directo: tuple[float, float] | None = None
	filtro_envio: float | None = None


@dataclass
class _Ranura:
	"""Una ranura de efecto con su reverberación."""

	ranura: int
	efecto: int
	ganancia: float = 0.0
	objetivo: float = 0.0
	preset: str = ""


class MotorOpenAL(MotorBase):
	"""OpenAL Soft con HRTF. Ver el docstring del módulo."""

	nombre = "openal"
	FUENTES_MAXIMAS = 48

	def __init__(self) -> None:
		super().__init__()
		self.al: Any = None
		self._dispositivo: int | None = None
		self._contexto: int | None = None
		self.memoria = False
		self.frecuencia = FRECUENCIA
		self.hrtf_activo = False
		self.estado_hrtf = ""
		self.perfil_hrtf = ""
		self.cabeza = ""
		self.salida = "auriculares"
		self.dispositivo_pedido = ""
		self.nombre_salida = ""
		self.version = ""
		self.reverberacion = True
		self.nivel_reverberacion = 1.0
		self.vigilante: Vigilante | None = None
		self._libres: list[int] = []
		self._todas: list[int] = []
		self._buferes: dict[tuple[str, bool], int] = {}
		self._retirados: list[int] = []  # búferes sustituidos que una fuente aún usaba al sustituirlos
		self._filtro = 0
		self._ranuras: list[_Ranura] = []
		self._ranura_activa = 0
		self._preset_pendiente: str | None = None
		self._t_vigila = 0.0
		self._defecto_visto = ""

	# ── Disponibilidad y arranque ──

	@classmethod
	def disponible(cls) -> tuple[bool, str]:
		"""Hace falta Windows de 64 bits y ``soft_oal.dll`` en ``data/bin/openal``."""
		return o.disponible()

	def _leer_opciones(self, opciones: dict) -> None:
		super()._leer_opciones(opciones)
		op = self.opciones
		self.cabeza = str(op.get("cabeza") or "")
		if self.cabeza == "integrada":
			self.cabeza = ""
		salida = str(op.get("salida") or "auriculares")
		self.salida = salida if salida in SALIDAS else "auriculares"
		self.reverberacion = bool(op.get("reverberacion", True))
		self.nivel_reverberacion = recortar(float(op.get("nivel_reverberacion", 1.0) or 0.0), 0.0, 1.5)

	def iniciar(self, dispositivo: str | None, opciones: dict) -> None:
		"""Abre la salida (o el dispositivo en memoria), crea el contexto con HRTF y comprueba que quedó activo."""
		if self._iniciado:
			self.cerrar()
		self._leer_opciones(opciones)
		hay, motivo = o.disponible()
		if not hay:
			raise MotorNoDisponible(motivo)
		try:
			al = self.al = o.cargar()
		except OSError as error:
			raise MotorNoDisponible(f"no se pudo cargar OpenAL Soft: {error}") from error
		self.memoria = bool(self.opciones.get("memoria", False))
		self.dispositivo_pedido = str(dispositivo or "")
		if self.memoria:
			if al.alcLoopbackOpenDeviceSOFT is None:
				raise ErrorMotor("esta OpenAL no tiene dispositivo en memoria (ALC_SOFT_loopback)")
			self._dispositivo = al.alcLoopbackOpenDeviceSOFT(None)
		else:
			elegido = self._nombre_al(self.dispositivo_pedido) if self.dispositivo_pedido else None
			if self.dispositivo_pedido and elegido is None:
				log.warning("No está la salida de sonido «%s»: se usa la de Windows.", self.dispositivo_pedido)
			self._dispositivo = al.alcOpenDevice(elegido) or (al.alcOpenDevice(None) if elegido else None)
		if not self._dispositivo:
			self._dispositivo = None
			raise ErrorMotor("OpenAL no pudo abrir el dispositivo de sonido")
		self._contexto = al.alcCreateContext(self._dispositivo, self._atributos())
		if not self._contexto:
			codigo = al.alcGetError(self._dispositivo)
			al.alcCloseDevice(self._dispositivo)
			self._dispositivo = self._contexto = None
			raise ErrorMotor(f"OpenAL no pudo crear el contexto (error {codigo:#x})")
		self._poner_contexto(forzar=True)
		self.version = (al.alGetString(o.AL_VERSION) or b"").decode("utf-8", "replace")
		self.frecuencia = o.entero(al, self._dispositivo, o.ALC_FREQUENCY)
		self._verificar_hrtf()
		al.alDistanceModel(o.AL_INVERSE_DISTANCE_CLAMPED)
		al.alListenerf(o.AL_GAIN, 0.0)  # la ganancia maestra sube poco a poco desde el silencio
		try:
			self._crear_fuentes()
		except ErrorMotor:
			self.cerrar()  # no dejar abierto un dispositivo que no sirve
			raise
		self._crear_filtro()
		self._crear_eco()
		self.nombre_salida = "" if self.memoria else o.cadena(al, self._dispositivo, o.ALC_ALL_DEVICES_SPECIFIER)
		self._defecto_visto = "" if self.memoria else salidas.por_defecto()
		self._t_vigila = time.monotonic()
		self.vigilante = Vigilante(self.proteccion.silencio_sin_tic, self._callar_por_seguridad, self._volver_de_silencio)
		if not self.memoria:
			self.vigilante.iniciar()
		self._iniciado = True
		self._oyente_cambiado()
		self._acustica_cambiada()
		log.info(
			"Motor OpenAL iniciado: OpenAL Soft %s, %s Hz, %s fuentes, salida «%s»%s.",
			self.version,
			self.frecuencia,
			len(self._todas),
			self.nombre_salida or "en memoria",
			"" if self._ranuras else ", sin reverberación",
		)

	def _atributos(self) -> ctypes.Array:
		"""Atributos del contexto: formato (en memoria), envíos, limitador y HRTF o estéreo simple."""
		al = self.al
		pares: list[tuple[int, int]] = []
		if self.memoria:
			pares += [
				(o.ALC_FORMAT_CHANNELS_SOFT, o.ALC_STEREO_SOFT),
				(o.ALC_FORMAT_TYPE_SOFT, o.ALC_FLOAT_SOFT),
				(o.ALC_FREQUENCY, FRECUENCIA),
			]
		pares += [(o.ALC_MAX_AUXILIARY_SENDS, 2), (o.ALC_OUTPUT_LIMITER_SOFT, 1)]
		if self.salida == "auriculares" and not self.mono:
			# HRTF siempre que se pida auriculares, sin esperar a que Windows diga que lo son.
			pares += [(o.ALC_HRTF_SOFT, 1), (o.ALC_OUTPUT_MODE_SOFT, o.ALC_STEREO_HRTF_SOFT)]
			vistos = o.perfiles(al, self._dispositivo)
			pedida = self.cabeza or o.INTEGRADA  # sin pedirla, OpenAL elegiría el primer fichero
			if pedida not in vistos and self.cabeza:
				log.warning("No está el perfil de cabeza «%s»; se usa el integrado. Hay: %s.", self.cabeza, ", ".join(vistos))
				pedida = o.INTEGRADA
			if pedida in vistos:
				pares.append((o.ALC_HRTF_ID_SOFT, vistos.index(pedida)))
		else:
			pares += [(o.ALC_HRTF_SOFT, 0), (o.ALC_OUTPUT_MODE_SOFT, o.ALC_STEREO_BASIC_SOFT)]
		return o.atributos(pares)

	def _verificar_hrtf(self) -> None:
		"""Consulta el estado REAL del HRTF (no lo que se pidió) y lo deja en el registro."""
		codigo, perfil = o.estado_hrtf(self.al, self._dispositivo)
		self.hrtf_activo = codigo in o.ESTADOS_HRTF_ACTIVOS
		self.estado_hrtf = o.ESTADOS_HRTF.get(codigo, str(codigo))
		self.perfil_hrtf = perfil if self.hrtf_activo else ""
		quiere = self.salida == "auriculares" and not self.mono
		if self.hrtf_activo:
			log.info("HRTF %s con el perfil «%s».", self.estado_hrtf, perfil or "?")
		elif quiere:
			log.warning("OpenAL no activó el HRTF (%s): los sonidos se sitúan solo con panorama.", self.estado_hrtf)
		else:
			log.info("HRTF %s: salida en estéreo para altavoces.", self.estado_hrtf)

	def _crear_fuentes(self) -> None:
		"""Reserva las fuentes de una vez; si la biblioteca da menos, se trabaja con las que haya."""
		al = self.al
		pedidas = int(recortar(float(self.opciones.get("fuentes", 48) or 48), 8, 128))
		self._todas = []
		al.alGetError()
		for _i in range(pedidas):
			fuente = ctypes.c_uint(0)
			al.alGenSources(1, ctypes.byref(fuente))
			if al.alGetError() or not fuente.value:
				break
			self._todas.append(fuente.value)
		if not self._todas:
			raise ErrorMotor("OpenAL no dio ninguna fuente de sonido")
		self._libres = list(reversed(self._todas))
		self.FUENTES_MAXIMAS = len(self._todas)

	def _crear_filtro(self) -> None:
		"""Un paso bajo de trabajo: OpenAL copia sus valores en la fuente al asignárselo."""
		al = self.al
		self._filtro = 0
		if not al.con_efx:
			return
		al.alGetError()
		filtro = ctypes.c_uint(0)
		al.alGenFilters(1, ctypes.byref(filtro))
		al.alFilteri(filtro.value, o.AL_FILTER_TYPE, o.AL_FILTER_LOWPASS)
		if al.alGetError() or not filtro.value:
			log.warning("OpenAL no admite el filtro paso bajo: no habrá oclusión ni refuerzo detrás.")
			return
		self._filtro = filtro.value

	def _crear_eco(self) -> None:
		"""Dos ranuras de reverberación (para fundir de una acústica a otra); una si solo hay un envío."""
		al = self.al
		self._ranuras = []
		self._ranura_activa = 0
		self._preset_pendiente = None
		if not al.con_efx or not self.reverberacion:
			return
		envios = o.entero(al, self._dispositivo, o.ALC_MAX_AUXILIARY_SENDS)
		for _i in range(min(2, envios)):
			al.alGetError()
			efecto = ctypes.c_uint(0)
			ranura = ctypes.c_uint(0)
			al.alGenEffects(1, ctypes.byref(efecto))
			al.alEffecti(efecto.value, o.AL_EFFECT_TYPE, o.AL_EFFECT_REVERB)
			al.alGenAuxiliaryEffectSlots(1, ctypes.byref(ranura))
			if al.alGetError() or not efecto.value or not ranura.value:
				log.warning("OpenAL no pudo crear la reverberación.")
				break
			al.alAuxiliaryEffectSlotf(ranura.value, o.AL_EFFECTSLOT_GAIN, 0.0)
			self._ranuras.append(_Ranura(ranura.value, efecto.value))

	def _poner_contexto(self, forzar: bool = False) -> None:
		"""Deja este contexto como el actual del proceso (puede haber otro motor abierto, en las pruebas)."""
		global _contexto_actual
		if forzar or _contexto_actual != self._contexto:
			self.al.alcMakeContextCurrent(self._contexto)
			_contexto_actual = self._contexto

	# ── Salidas ──

	def dispositivos(self) -> list[str]:
		"""Las salidas que ve OpenAL ahora mismo."""
		try:
			al = o.cargar()
		except OSError:
			log.warning("No se pudo cargar OpenAL para listar las salidas.", exc_info=True)
			return []
		return o.lista_cadenas(al, None, o.ALC_ALL_DEVICES_SPECIFIER)

	def _nombre_al(self, nombre: str) -> bytes | None:
		"""El nombre exacto de OpenAL para una salida guardada (quizá con el nombre corto de Windows)."""
		for candidato in self.dispositivos():
			if candidato == nombre or salidas.coincide(nombre, candidato):
				return candidato.encode("utf-8")
		return None

	def cambiar_dispositivo(self, dispositivo: str | None) -> bool:
		"""Lleva la mezcla a otra salida sin cortar lo que suena (vacío: la de Windows)."""
		self.dispositivo_pedido = str(dispositivo or "")
		return self._reabrir("cambiada en las preferencias")

	def _reabrir(self, motivo: str) -> bool:
		"""``alcReopenDeviceSOFT``: OpenAL Soft mueve la mezcla al dispositivo indicado."""
		if not self._iniciado or self.memoria:
			return False
		al = self.al
		if al.alcReopenDeviceSOFT is None:
			log.warning("Esta OpenAL no sabe cambiar de salida en caliente.")
			return False
		self._poner_contexto()
		antes = self.nombre_salida
		destino = self._nombre_al(self.dispositivo_pedido) if self.dispositivo_pedido else None
		hecho = al.alcReopenDeviceSOFT(self._dispositivo, destino, self._atributos()) != b"\x00"
		if not hecho and destino is not None:
			hecho = al.alcReopenDeviceSOFT(self._dispositivo, None, self._atributos()) != b"\x00"
		self.nombre_salida = o.cadena(al, self._dispositivo, o.ALC_ALL_DEVICES_SPECIFIER)
		self._verificar_hrtf()
		log.info("Salida de sonido abierta de nuevo (%s): antes «%s», ahora «%s».", motivo, antes, self.nombre_salida)
		return hecho

	def _vigilar_salida(self) -> None:
		"""Cada poco: si la salida se ha cortado, si Windows ha cambiado la suya o si ha vuelto la elegida, se reabre."""
		ahora = time.monotonic()
		if self.memoria or ahora - self._t_vigila < VIGILAR_CADA:
			return
		self._t_vigila = ahora
		defecto = salidas.por_defecto()
		motivo = ""
		if not o.entero(self.al, self._dispositivo, o.ALC_CONNECTED):
			motivo = "se ha cortado"
		elif not self.dispositivo_pedido and defecto and self._defecto_visto and defecto != self._defecto_visto:
			motivo = "ha cambiado la de Windows"
		elif (
			self.dispositivo_pedido
			and not salidas.coincide(self.dispositivo_pedido, self.nombre_salida)
			and self.dispositivo_pedido != self.nombre_salida
			and salidas.presente(self.dispositivo_pedido)
		):
			motivo = "ha vuelto la elegida"
		if defecto:
			self._defecto_visto = defecto
		if motivo:
			self._reabrir(motivo)

	def _reiniciar_dispositivo(self, motivo: str) -> bool:
		"""``alcResetDeviceSOFT``: cambia HRTF, cabeza o modo de salida sin cerrar nada."""
		if not self._iniciado:
			return False
		al = self.al
		if al.alcResetDeviceSOFT is None:
			log.warning("Esta OpenAL no sabe cambiar el HRTF en caliente.")
			return False
		self._poner_contexto()
		hecho = al.alcResetDeviceSOFT(self._dispositivo, self._atributos()) != b"\x00"
		if not hecho:
			log.warning("OpenAL no aceptó el cambio (%s): error %#x.", motivo, al.alcGetError(self._dispositivo))
		self._verificar_hrtf()
		return hecho

	def poner_cabeza(self, cabeza: str) -> bool:
		"""Cambia en caliente el perfil de cabeza («» = el integrado). Devuelve si quedó activo ese perfil."""
		self.opciones["cabeza"] = cabeza
		self.cabeza = "" if cabeza == "integrada" else str(cabeza or "")
		self._reiniciar_dispositivo("perfil de cabeza")
		return self.hrtf_activo and self.perfil_hrtf == (self.cabeza or o.INTEGRADA)

	def poner_salida(self, salida: str) -> bool:
		"""«auriculares» (binaural) o «altavoces» (estéreo sin HRTF), en caliente."""
		if salida not in SALIDAS:
			log.warning("Tipo de salida desconocido: %s.", salida)
			return False
		self.opciones["salida"] = salida
		self.salida = salida
		return self._reiniciar_dispositivo("tipo de salida")

	def configurar(self, opciones: dict) -> None:
		"""Aplica en caliente cabeza, tipo de salida, sonido mono, distancia y nivel de reverberación."""
		antes = (self.cabeza, self.salida, self.mono)
		super().configurar(opciones)
		if not self._iniciado:
			return
		if (self.cabeza, self.salida, self.mono) != antes:
			self._reiniciar_dispositivo("preferencias")
		self._poner_contexto()
		for canal in self._canales.values():
			self._poner_distancia(canal)
		self._acustica_cambiada()

	# ── Oyente ──

	def _oyente_cambiado(self) -> None:
		if not self._iniciado:
			return
		self._poner_contexto()
		x, y, z, rumbo = self._oyente
		r = math.radians(rumbo)
		self.al.alListener3f(o.AL_POSITION, x, z, -y)
		self.al.alListenerfv(o.AL_ORIENTATION, (ctypes.c_float * 6)(math.sin(r), 0.0, -math.cos(r), 0.0, 1.0, 0.0))

	# ── Búferes ──

	def _bufer(self, nombre: str, mono: bool) -> int:
		"""El búfer de OpenAL de un sonido; ``mono`` pide la mezcla a un canal (lo que se posiciona)."""
		clave = (nombre, mono)
		hecho = self._buferes.get(clave)
		if hecho:
			return hecho
		datos = self._datos(nombre)
		if datos is None:
			return 0
		if mono:
			datos = a_mono(datos)
		pcm = np.ascontiguousarray(np.clip(datos, -1.0, 1.0) * 32767.0, dtype=np.int16)
		formato = o.AL_FORMAT_STEREO16 if pcm.ndim == 2 else o.AL_FORMAT_MONO16
		al = self.al
		al.alGetError()
		bufer = ctypes.c_uint(0)
		al.alGenBuffers(1, ctypes.byref(bufer))
		al.alBufferData(bufer.value, formato, pcm.ctypes.data_as(ctypes.c_void_p), pcm.nbytes, FRECUENCIA)
		error = al.alGetError()
		if error or not bufer.value:
			log.warning("OpenAL no pudo cargar el sonido %s (error %#x).", nombre, error)
			if bufer.value:
				al.alDeleteBuffers(1, ctypes.byref(bufer))
				al.alGetError()
			return 0
		self._buferes[clave] = bufer.value
		return bufer.value

	def _sonido_cambiado(self, nombre: str) -> None:
		"""Un sonido sustituido: sus búferes viejos sobran (si alguna fuente aún los usa, OpenAL no los borra)."""
		if self.al is None or not self._iniciado:
			return
		self._poner_contexto()
		self._borrar_retirados()
		for clave in [c for c in self._buferes if c[0] == nombre]:
			viejo = self._buferes.pop(clave)
			self.al.alGetError()
			self.al.alDeleteBuffers(1, ctypes.byref(ctypes.c_uint(viejo)))
			if self.al.alGetError():
				# Una fuente lo está usando (un bucle que se funde): OpenAL no lo borra. Se apunta para
				# borrarlo en cuanto quede libre, o al cerrar, DESPUÉS de soltar las fuentes.
				self._retirados.append(viejo)
				log.debug("El búfer antiguo de %s sigue en uso; se borrará cuando quede libre.", nombre)

	def _borrar_retirados(self) -> None:
		"""Intenta borrar los búferes sustituidos que seguían en uso; los que aún suenan esperan."""
		if not self._retirados:
			return
		al = self.al
		quedan: list[int] = []
		for bufer in self._retirados:
			al.alGetError()
			al.alDeleteBuffers(1, ctypes.byref(ctypes.c_uint(bufer)))
			if al.alGetError():
				quedan.append(bufer)
		self._retirados = quedan

	# ── Canales ──

	def _empezar(self, canal: Canal) -> bool:
		self._poner_contexto()
		al = self.al
		datos = self._datos(canal.nombre)
		if datos is None or not self._libres:
			return False
		posicionada = canal.pos is not None or canal.relativo is not None
		bufer = self._bufer(canal.nombre, mono=posicionada and datos.ndim == 2)
		if not bufer:
			return False
		fuente = _Fuente(self._libres.pop(), posicionada)
		canal.interno = fuente
		al.alGetError()
		al.alSourceStop(fuente.id)
		al.alSourcei(fuente.id, o.AL_BUFFER, bufer)
		al.alSourcei(fuente.id, o.AL_LOOPING, 1 if canal.bucle else 0)
		# Un ambiente estéreo sin posición va derecho a cada oído, sin pasar por la cabeza.
		al.alSourcei(fuente.id, o.AL_DIRECT_CHANNELS_SOFT, 1 if datos.ndim == 2 and not posicionada else 0)
		self._poner_distancia(canal)
		self._aplicar(canal)
		if not canal.pausado:
			al.alSourcePlay(fuente.id)
		error = al.alGetError()
		if error:
			log.warning("OpenAL no pudo hacer sonar %s (error %#x).", canal.nombre, error)
			self._detener(canal)
			return False
		return True

	def _poner_distancia(self, canal: Canal) -> None:
		"""Parámetros del modelo de distancia de la fuente (los mismos para todas las posicionadas)."""
		fuente: _Fuente = canal.interno
		al = self.al
		al.alSourcef(fuente.id, o.AL_REFERENCE_DISTANCE, self.referencia)
		al.alSourcef(fuente.id, o.AL_MAX_DISTANCE, self.maxima)
		al.alSourcef(fuente.id, o.AL_ROLLOFF_FACTOR, self.caida if fuente.posicionada else 0.0)
		if al.con_efx:
			# El eco de una fuente lejana también llega más flojo, aunque cae más despacio que el sonido directo.
			al.alSourcef(fuente.id, o.AL_ROOM_ROLLOFF_FACTOR, 0.5 * self.caida if fuente.posicionada else 0.0)

	def _aplicar(self, canal: Canal) -> None:
		fuente: _Fuente = canal.interno
		al = self.al
		angulo: float | None = None
		if canal.pos is not None:
			angulo, distancia, altura = mundo_a_relativo(self._oyente, canal.pos)
			if self.mono:
				# Para quien oye por un solo oído: todo delante, a su distancia real; los dos oídos oyen lo mismo.
				al.alSourcei(fuente.id, o.AL_SOURCE_RELATIVE, 1)
				al.alSource3f(fuente.id, o.AL_POSITION, 0.0, 0.0, -math.hypot(distancia, altura))
			else:
				al.alSourcei(fuente.id, o.AL_SOURCE_RELATIVE, 0)
				al.alSource3f(fuente.id, o.AL_POSITION, canal.pos[0], canal.pos[2], -canal.pos[1])
		elif canal.relativo is not None:
			angulo, distancia = canal.relativo
			r = math.radians(0.0 if self.mono else angulo)
			al.alSourcei(fuente.id, o.AL_SOURCE_RELATIVE, 1)
			al.alSource3f(fuente.id, o.AL_POSITION, math.sin(r) * distancia, 0.0, -math.cos(r) * distancia)
		else:
			# Sin posición (interfaz): en el centro de la cabeza, igual por los dos oídos.
			al.alSourcei(fuente.id, o.AL_SOURCE_RELATIVE, 1)
			al.alSource3f(fuente.id, o.AL_POSITION, 0.0, 0.0, 0.0)
		al.alSourcef(fuente.id, o.AL_GAIN, canal.ganancia)
		al.alSourcef(fuente.id, o.AL_PITCH, canal.tono)
		self._poner_filtros(canal, fuente, factor_detras(angulo))

	def _poner_filtros(self, canal: Canal, fuente: _Fuente, detras: float) -> None:
		"""Paso bajo del camino directo (oclusión y detrás) y del envío al eco (solo oclusión)."""
		al = self.al
		if not self._filtro:
			return
		general, agudos = ganancias_filtro(canal.filtro, detras, self.refuerzo_detras)
		directo = (round(general, 3), round(agudos, 3))
		if directo != fuente.filtro_directo:
			fuente.filtro_directo = directo
			if directo == (1.0, 1.0):
				al.alSourcei(fuente.id, o.AL_DIRECT_FILTER, o.AL_FILTER_NULL)
			else:
				al.alFilterf(self._filtro, o.AL_LOWPASS_GAIN, directo[0])
				al.alFilterf(self._filtro, o.AL_LOWPASS_GAINHF, directo[1])
				al.alSourcei(fuente.id, o.AL_DIRECT_FILTER, self._filtro)
		envio = round(canal.filtro, 3) if (canal.eco and self._ranuras) else -1.0
		if envio != fuente.filtro_envio:
			fuente.filtro_envio = envio
			if envio < 0.0:
				for indice in range(2):
					al.alSource3i(fuente.id, o.AL_AUXILIARY_SEND_FILTER, o.AL_EFFECTSLOT_NULL, indice, o.AL_FILTER_NULL)
			else:
				# Lo que suena tras una pared excita menos el eco de esta sala, y sin sus agudos.
				general_eco, agudos_eco = ganancias_filtro(envio)
				al.alFilterf(self._filtro, o.AL_LOWPASS_GAIN, general_eco * (1.0 - 0.5 * envio))
				al.alFilterf(self._filtro, o.AL_LOWPASS_GAINHF, agudos_eco)
				for indice, ranura in enumerate(self._ranuras):
					al.alSource3i(fuente.id, o.AL_AUXILIARY_SEND_FILTER, ranura.ranura, indice, self._filtro)
			al.alGetError()  # con un solo envío, pedir el segundo da un error que no importa

	def _detener(self, canal: Canal) -> None:
		fuente: _Fuente | None = canal.interno
		if fuente is None or self.al is None or self._contexto is None:
			return
		self._poner_contexto()
		al = self.al
		al.alSourceStop(fuente.id)
		al.alSourcei(fuente.id, o.AL_BUFFER, 0)
		al.alSourcei(fuente.id, o.AL_DIRECT_FILTER, o.AL_FILTER_NULL)
		if al.con_efx:
			for indice in range(2):
				al.alSource3i(fuente.id, o.AL_AUXILIARY_SEND_FILTER, o.AL_EFFECTSLOT_NULL, indice, o.AL_FILTER_NULL)
		al.alGetError()
		self._libres.append(fuente.id)
		canal.interno = None

	def _sigue(self, canal: Canal) -> bool:
		fuente: _Fuente | None = canal.interno
		if fuente is None:
			return False
		# Con otro motor abierto (pruebas, muestras de las preferencias) su contexto podría ser el actual.
		self._poner_contexto()
		estado = ctypes.c_int(0)
		self.al.alGetSourcei(fuente.id, o.AL_SOURCE_STATE, ctypes.byref(estado))
		if estado.value in (o.AL_PLAYING, o.AL_PAUSED):
			return True
		return canal.pausado and estado.value == o.AL_INITIAL

	def _pausar_canal(self, canal: Canal, si: bool) -> None:
		fuente: _Fuente | None = canal.interno
		if fuente is None:
			return
		self._poner_contexto()
		if si:
			self.al.alSourcePause(fuente.id)
		else:
			self.al.alSourcePlay(fuente.id)

	# ── Reverberación ──

	def _cargar_preset(self, ranura: _Ranura, preset: str) -> None:
		"""Pone los parámetros de una acústica en el efecto y lo vuelve a cargar en la ranura (si no, no cambia)."""
		al = self.al
		p = PRESETS[preset]
		for parametro, valor in (
			(o.AL_REVERB_DENSITY, p.densidad),
			(o.AL_REVERB_DIFFUSION, p.difusion),
			(o.AL_REVERB_GAIN, 0.5),
			(o.AL_REVERB_GAINHF, p.brillo),
			(o.AL_REVERB_DECAY_TIME, p.cola),
			(o.AL_REVERB_DECAY_HFRATIO, p.cola_agudos),
			(o.AL_REVERB_REFLECTIONS_GAIN, p.primeras),
			(o.AL_REVERB_REFLECTIONS_DELAY, p.retardo_primeras),
			(o.AL_REVERB_LATE_REVERB_GAIN, p.tardias),
			(o.AL_REVERB_LATE_REVERB_DELAY, p.retardo_tardias),
		):
			al.alEffectf(ranura.efecto, parametro, float(valor))
		al.alAuxiliaryEffectSloti(ranura.ranura, o.AL_EFFECTSLOT_EFFECT, ranura.efecto)
		error = al.alGetError()
		if error:
			log.warning("OpenAL rechazó la reverberación «%s» (error %#x).", preset, error)
		ranura.preset = preset

	def _acustica_cambiada(self) -> None:
		"""Con dos ranuras: la nueva acústica entra por la libre mientras la otra se apaga. Con una: baja, cambia y sube."""
		if not self._iniciado or not self._ranuras:
			return
		self._poner_contexto()
		preset = self.preset if self.preset in PRESETS else "seca"
		objetivo = PRESETS[preset].envio * self.nivel_reverberacion
		activa = self._ranuras[self._ranura_activa]
		if activa.preset == preset:
			activa.objetivo = objetivo
			return
		if len(self._ranuras) == 1:
			self._preset_pendiente = preset
			activa.objetivo = 0.0
			return
		otra = 1 - self._ranura_activa
		nueva = self._ranuras[otra]
		nueva.ganancia = 0.0
		self.al.alAuxiliaryEffectSlotf(nueva.ranura, o.AL_EFFECTSLOT_GAIN, 0.0)
		self._cargar_preset(nueva, preset)
		nueva.objetivo = objetivo
		activa.objetivo = 0.0
		self._ranura_activa = otra

	def _avanzar_eco(self, dt: float) -> None:
		al = self.al
		paso = dt / TRANSICION_ECO
		for ranura in self._ranuras:
			if ranura.ganancia != ranura.objetivo:
				if ranura.ganancia < ranura.objetivo:
					ranura.ganancia = min(ranura.objetivo, ranura.ganancia + paso)
				else:
					ranura.ganancia = max(ranura.objetivo, ranura.ganancia - paso)
				al.alAuxiliaryEffectSlotf(ranura.ranura, o.AL_EFFECTSLOT_GAIN, recortar(ranura.ganancia))
		if self._preset_pendiente is not None and self._ranuras[0].ganancia <= 0.0:
			preset, self._preset_pendiente = self._preset_pendiente, None
			self._cargar_preset(self._ranuras[0], preset)
			self._ranuras[0].objetivo = PRESETS[preset].envio * self.nivel_reverberacion

	# ── Por fotograma ──

	def tic(self, dt: float) -> None:
		"""Además de lo común: vigila la salida, avanza el fundido del eco y pone la ganancia maestra."""
		if not self._iniciado:
			return
		self._poner_contexto()
		if self.vigilante is not None:
			self.vigilante.latido()
		self._vigilar_salida()
		super().tic(dt)
		self._borrar_retirados()
		self._avanzar_eco(recortar(dt, 0.0, 0.25))
		self.al.alListenerf(o.AL_GAIN, self._maestro)

	def _callar_por_seguridad(self) -> None:
		"""Lo llama el vigilante (desde su hilo) si el juego deja de actualizar el sonido."""
		if self.al is not None and self._contexto is not None:
			self.al.alListenerf(o.AL_GAIN, 0.0)

	def _volver_de_silencio(self) -> None:
		"""El juego ha vuelto: la ganancia maestra arranca de cero y sube poco a poco."""
		self._maestro = 0.0

	def renderizar(self, muestras: int) -> np.ndarray:
		"""Solo en memoria: las siguientes ``muestras`` de la mezcla, forma (muestras, 2), izquierda y derecha."""
		if not self.memoria or not self._iniciado:
			raise ErrorMotor("renderizar solo funciona con el motor en memoria")
		self._poner_contexto()
		salida = (ctypes.c_float * (muestras * 2))()
		self.al.alcRenderSamplesSOFT(self._dispositivo, salida, muestras)
		return np.frombuffer(salida, dtype=np.float32).reshape(muestras, 2).copy()

	# ── Cierre y diagnóstico ──

	def cerrar(self) -> None:
		"""Para todo y libera fuentes, filtros, efectos, búferes, contexto y dispositivo."""
		global _contexto_actual
		if self.vigilante is not None:
			self.vigilante.parar()
			self.vigilante = None
		if self.al is None or self._contexto is None:
			self._iniciado = False
			return
		al = self.al
		self._poner_contexto(forzar=True)
		self.parar_todo()
		self._iniciado = False
		if self._todas:
			al.alDeleteSources(len(self._todas), (ctypes.c_uint * len(self._todas))(*self._todas))
		if self._filtro:
			al.alDeleteFilters(1, ctypes.byref(ctypes.c_uint(self._filtro)))
		for ranura in self._ranuras:
			al.alDeleteAuxiliaryEffectSlots(1, ctypes.byref(ctypes.c_uint(ranura.ranura)))
			al.alDeleteEffects(1, ctypes.byref(ctypes.c_uint(ranura.efecto)))
		# Después de borrar las fuentes: ningún búfer queda en uso, así que se borran todos (OpenAL no
		# borra ninguno de la lista si uno solo sigue puesto en una fuente).
		buferes = list(self._buferes.values()) + self._retirados
		if buferes:
			al.alGetError()
			al.alDeleteBuffers(len(buferes), (ctypes.c_uint * len(buferes))(*buferes))
			error = al.alGetError()
			if error:
				log.warning("OpenAL no borró %s búferes al cerrar (error %#x).", len(buferes), error)
		self._todas, self._libres, self._ranuras, self._filtro = [], [], [], 0
		self._buferes.clear()
		self._retirados = []
		al.alcMakeContextCurrent(None)
		_contexto_actual = None
		al.alcDestroyContext(self._contexto)
		al.alcCloseDevice(self._dispositivo)
		self._contexto = self._dispositivo = None
		log.info("Motor OpenAL cerrado.")

	def estado(self) -> dict:
		"""Lo común más el estado real del HRTF, la salida y la reverberación."""
		datos = super().estado()
		datos.update(
			{
				"version": self.version,
				"frecuencia": self.frecuencia,
				"hrtf_activo": self.hrtf_activo,
				"estado_hrtf": self.estado_hrtf,
				"perfil_hrtf": self.perfil_hrtf,
				"cabeza": self.cabeza,
				"salida": self.salida,
				"dispositivo": self.nombre_salida,
				"fuentes": len(self._todas),
				"fuentes_libres": len(self._libres),
				"reverberacion": bool(self._ranuras),
				"ranuras_eco": len(self._ranuras),
				"filtro": bool(self._filtro),
				"memoria": self.memoria,
			}
		)
		return datos


assert set(PRESETS) == set(ACUSTICAS), "falta el preset de reverberación de alguna acústica"
