"""Capa ctypes sobre OpenAL Soft (``data/bin/openal/soft_oal.dll``).

La DLL es un fichero suelto que el usuario puede sustituir por otra compilación de OpenAL Soft: es
lo que pide su licencia (LGPL) y por eso no se enlaza ni se empaqueta dentro del ejecutable. Aquí
solo están las funciones y constantes que usa el motor; no es la API completa.

Antes de cargarla se fijan, solo para este proceso, dos variables de entorno:

- ``ALSOFT_LOCAL_PATH``: la carpeta ``hrtf`` con los perfiles de cabeza (``.mhr``). OpenAL Soft busca
  ahí además de en la propia DLL (perfil «Built-In HRTF»).
- ``ALSOFT_CONF``: ``alsoft.ini`` de la misma carpeta.

No se escribe nada fuera de la carpeta del programa.

Adaptado de la capa ``openal_soft`` de Reconocedor de Ciudades y de ``audio_al.py`` de Puerto Bravo.
"""

from __future__ import annotations

import ctypes
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)

NOMBRE_DLL = "soft_oal.dll"
INTEGRADA = "Built-In HRTF"

# ── AL/al.h ──
AL_NONE = 0
AL_SOURCE_RELATIVE = 0x202
AL_PITCH = 0x1003
AL_POSITION = 0x1004
AL_LOOPING = 0x1007
AL_BUFFER = 0x1009
AL_GAIN = 0x100A
AL_ORIENTATION = 0x100F
AL_SOURCE_STATE = 0x1010
AL_INITIAL = 0x1011
AL_PLAYING = 0x1012
AL_PAUSED = 0x1013
AL_STOPPED = 0x1014
AL_REFERENCE_DISTANCE = 0x1020
AL_ROLLOFF_FACTOR = 0x1021
AL_MAX_DISTANCE = 0x1023
AL_FORMAT_MONO16 = 0x1101
AL_FORMAT_STEREO16 = 0x1103
AL_VERSION = 0xB002
AL_INVERSE_DISTANCE_CLAMPED = 0xD002
AL_DIRECT_CHANNELS_SOFT = 0x1033
# ── AL/efx.h ──
AL_DIRECT_FILTER = 0x20005
AL_AUXILIARY_SEND_FILTER = 0x20006
AL_ROOM_ROLLOFF_FACTOR = 0x20009
AL_FILTER_TYPE = 0x8001
AL_FILTER_NULL = 0x0000
AL_FILTER_LOWPASS = 0x0001
AL_LOWPASS_GAIN = 0x0001
AL_LOWPASS_GAINHF = 0x0002
AL_EFFECT_TYPE = 0x8001
AL_EFFECT_REVERB = 0x0001
AL_EFFECTSLOT_NULL = 0x0000
AL_EFFECTSLOT_EFFECT = 0x0001
AL_EFFECTSLOT_GAIN = 0x0002
AL_REVERB_DENSITY = 0x0001
AL_REVERB_DIFFUSION = 0x0002
AL_REVERB_GAIN = 0x0003
AL_REVERB_GAINHF = 0x0004
AL_REVERB_DECAY_TIME = 0x0005
AL_REVERB_DECAY_HFRATIO = 0x0006
AL_REVERB_REFLECTIONS_GAIN = 0x0007
AL_REVERB_REFLECTIONS_DELAY = 0x0008
AL_REVERB_LATE_REVERB_GAIN = 0x0009
AL_REVERB_LATE_REVERB_DELAY = 0x000A
# ── AL/alc.h y extensiones de OpenAL Soft ──
ALC_FREQUENCY = 0x1007
ALC_CONNECTED = 0x313
ALC_DEFAULT_ALL_DEVICES_SPECIFIER = 0x1012
ALC_ALL_DEVICES_SPECIFIER = 0x1013
ALC_MAX_AUXILIARY_SENDS = 0x20003
ALC_FORMAT_CHANNELS_SOFT = 0x1990
ALC_FORMAT_TYPE_SOFT = 0x1991
ALC_STEREO_SOFT = 0x1501
ALC_FLOAT_SOFT = 0x1406
ALC_HRTF_SOFT = 0x1992
ALC_HRTF_STATUS_SOFT = 0x1993
ALC_NUM_HRTF_SPECIFIERS_SOFT = 0x1994
ALC_HRTF_SPECIFIER_SOFT = 0x1995
ALC_HRTF_ID_SOFT = 0x1996
ALC_OUTPUT_LIMITER_SOFT = 0x199A
ALC_OUTPUT_MODE_SOFT = 0x19AC
ALC_STEREO_BASIC_SOFT = 0x19AE
ALC_STEREO_HRTF_SOFT = 0x19B2

# Códigos de ALC_HRTF_STATUS_SOFT. Activo de verdad: 1, 3 y 4.
ESTADOS_HRTF: dict[int, str] = {
	0: "desactivado",
	1: "activado",
	2: "denegado",
	3: "obligatorio",
	4: "activado por los auriculares",
	5: "formato de salida no admitido",
}
ESTADOS_HRTF_ACTIVOS = (1, 3, 4)

_c = ctypes
_p_int = _c.POINTER(_c.c_int)
_p_uint = _c.POINTER(_c.c_uint)
_FIRMAS: dict[str, tuple[object, tuple]] = {
	"alcOpenDevice": (_c.c_void_p, (_c.c_char_p,)),
	"alcCloseDevice": (_c.c_char, (_c.c_void_p,)),
	"alcCreateContext": (_c.c_void_p, (_c.c_void_p, _p_int)),
	"alcMakeContextCurrent": (_c.c_char, (_c.c_void_p,)),
	"alcDestroyContext": (None, (_c.c_void_p,)),
	"alcGetError": (_c.c_int, (_c.c_void_p,)),
	# Devuelve un puntero y no una cadena: las listas de dispositivos llevan varios nombres seguidos.
	"alcGetString": (_c.c_void_p, (_c.c_void_p, _c.c_int)),
	"alcGetIntegerv": (None, (_c.c_void_p, _c.c_int, _c.c_int, _p_int)),
	"alcIsExtensionPresent": (_c.c_char, (_c.c_void_p, _c.c_char_p)),
	"alcGetProcAddress": (_c.c_void_p, (_c.c_void_p, _c.c_char_p)),
	"alGetError": (_c.c_int, ()),
	"alGetString": (_c.c_char_p, (_c.c_int,)),
	"alDistanceModel": (None, (_c.c_int,)),
	"alListenerf": (None, (_c.c_int, _c.c_float)),
	"alListener3f": (None, (_c.c_int, _c.c_float, _c.c_float, _c.c_float)),
	"alListenerfv": (None, (_c.c_int, _c.POINTER(_c.c_float))),
	"alGenBuffers": (None, (_c.c_int, _p_uint)),
	"alDeleteBuffers": (None, (_c.c_int, _p_uint)),
	"alBufferData": (None, (_c.c_uint, _c.c_int, _c.c_void_p, _c.c_int, _c.c_int)),
	"alGenSources": (None, (_c.c_int, _p_uint)),
	"alDeleteSources": (None, (_c.c_int, _p_uint)),
	"alSourcei": (None, (_c.c_uint, _c.c_int, _c.c_int)),
	"alSourcef": (None, (_c.c_uint, _c.c_int, _c.c_float)),
	"alSource3f": (None, (_c.c_uint, _c.c_int, _c.c_float, _c.c_float, _c.c_float)),
	"alGetSourcei": (None, (_c.c_uint, _c.c_int, _p_int)),
	"alSourcePlay": (None, (_c.c_uint,)),
	"alSourceStop": (None, (_c.c_uint,)),
	"alSourcePause": (None, (_c.c_uint,)),
}
# EFX: filtros y reverberación. Una DLL sin ellos sirve igual, sin eco ni paso bajo.
_FIRMAS_EFX: dict[str, tuple[object, tuple]] = {
	"alSource3i": (None, (_c.c_uint, _c.c_int, _c.c_int, _c.c_int, _c.c_int)),
	"alGenFilters": (None, (_c.c_int, _p_uint)),
	"alDeleteFilters": (None, (_c.c_int, _p_uint)),
	"alFilteri": (None, (_c.c_uint, _c.c_int, _c.c_int)),
	"alFilterf": (None, (_c.c_uint, _c.c_int, _c.c_float)),
	"alGenEffects": (None, (_c.c_int, _p_uint)),
	"alDeleteEffects": (None, (_c.c_int, _p_uint)),
	"alEffecti": (None, (_c.c_uint, _c.c_int, _c.c_int)),
	"alEffectf": (None, (_c.c_uint, _c.c_int, _c.c_float)),
	"alGenAuxiliaryEffectSlots": (None, (_c.c_int, _p_uint)),
	"alDeleteAuxiliaryEffectSlots": (None, (_c.c_int, _p_uint)),
	"alAuxiliaryEffectSloti": (None, (_c.c_uint, _c.c_int, _c.c_int)),
	"alAuxiliaryEffectSlotf": (None, (_c.c_uint, _c.c_int, _c.c_float)),
}
# Extensiones ALC de OpenAL Soft, que se piden con alcGetProcAddress (None si la DLL no las trae).
_EXTENSIONES: dict[str, object] = {
	"alcGetStringiSOFT": _c.CFUNCTYPE(_c.c_char_p, _c.c_void_p, _c.c_int, _c.c_int),
	"alcResetDeviceSOFT": _c.CFUNCTYPE(_c.c_char, _c.c_void_p, _p_int),
	"alcReopenDeviceSOFT": _c.CFUNCTYPE(_c.c_char, _c.c_void_p, _c.c_char_p, _p_int),
	"alcLoopbackOpenDeviceSOFT": _c.CFUNCTYPE(_c.c_void_p, _c.c_char_p),
	"alcRenderSamplesSOFT": _c.CFUNCTYPE(None, _c.c_void_p, _c.c_void_p, _c.c_int),
}

_al: ctypes.CDLL | None = None
_carpeta: Path | None = None


def carpeta() -> Path | None:
	"""La carpeta ``bin/openal`` que contiene la DLL, o None si no está en ningún sitio."""
	from app.audio.base import carpetas_de_serie

	for candidata in carpetas_de_serie("bin", "openal"):
		if (candidata / NOMBRE_DLL).is_file():
			return candidata
	return None


def disponible() -> tuple[bool, str]:
	"""(se puede cargar, motivo si no). No carga nada."""
	from app.core.i18n import _

	if os.name != "nt":
		return False, _("El motor OpenAL de EntornoLab solo está preparado para Windows.")
	if ctypes.sizeof(ctypes.c_void_p) != 8:
		return False, _("La biblioteca OpenAL Soft incluida es de 64 bits y este Python no lo es.")
	if carpeta() is None:
		return False, _("Falta la biblioteca soft_oal.dll en la carpeta data/bin/openal.")
	return True, ""


def _ruta_para_openal(ruta: Path) -> str:
	"""La ruta escrita de forma que OpenAL Soft la encuentre.

	OpenAL Soft no lee las carpetas en red escritas como ``\\\\servidor\\carpeta``: solo vería la cabeza
	integrada. En ese caso se le da relativa a la carpeta del programa, que se pone como carpeta de
	trabajo (lección aprendida en Reconocedor de Ciudades).
	"""
	texto = os.path.abspath(str(ruta))  # sin resolver: conserva la letra de unidad
	if not texto.startswith("\\\\"):
		return texto
	from app.core import paths

	base = paths.ruta_base()
	try:
		os.chdir(base)
		return os.path.relpath(texto, os.path.abspath(str(base)))
	except OSError, ValueError:
		log.warning("No se pudo preparar la carpeta de perfiles de cabeza %s.", texto, exc_info=True)
		return texto


def cargar() -> ctypes.CDLL:
	"""Carga la DLL una sola vez, con las firmas puestas y las extensiones como atributos.

	Lanza ``OSError`` si no está o no se puede cargar.
	"""
	global _al, _carpeta
	if _al is not None:
		return _al
	donde = carpeta()
	if donde is None:
		raise OSError("no se encuentra soft_oal.dll en data/bin/openal")
	os.environ["ALSOFT_LOCAL_PATH"] = _ruta_para_openal(donde / "hrtf")
	configuracion = donde / "alsoft.ini"
	if configuracion.is_file():
		os.environ["ALSOFT_CONF"] = os.path.abspath(str(configuracion))
	al = ctypes.CDLL(os.path.abspath(str(donde / NOMBRE_DLL)))
	for nombre, (devuelve, argumentos) in _FIRMAS.items():
		funcion = getattr(al, nombre)
		funcion.restype = devuelve
		funcion.argtypes = argumentos
	al.con_efx = True
	for nombre, (devuelve, argumentos) in _FIRMAS_EFX.items():
		funcion = getattr(al, nombre, None)
		if funcion is None:
			al.con_efx = False
			log.warning("La biblioteca OpenAL no trae %s: no habrá reverberación ni filtros.", nombre)
			continue
		funcion.restype = devuelve
		funcion.argtypes = argumentos
	for nombre, tipo in _EXTENSIONES.items():
		direccion = al.alcGetProcAddress(None, nombre.encode("ascii"))
		setattr(al, nombre, tipo(direccion) if direccion else None)
	_al = al
	_carpeta = donde
	log.info("OpenAL Soft cargada desde %s.", donde)
	return al


def cabezas_en_disco() -> list[str]:
	"""Los perfiles de cabeza ``.mhr`` que hay en la carpeta (sin el integrado), por nombre de fichero."""
	donde = carpeta()
	if donde is None:
		return []
	return sorted(p.stem for p in (donde / "hrtf").glob("*.mhr"))


def cadena(al: ctypes.CDLL, dispositivo: int | None, parametro: int) -> str:
	"""Una cadena de ``alcGetString``."""
	puntero = al.alcGetString(dispositivo, parametro)
	return ctypes.string_at(puntero).decode("utf-8", "replace") if puntero else ""


def lista_cadenas(al: ctypes.CDLL, dispositivo: int | None, parametro: int) -> list[str]:
	"""Una lista de ``alcGetString``: cadenas seguidas, terminada con una vacía."""
	puntero = al.alcGetString(dispositivo, parametro)
	nombres: list[str] = []
	while puntero:
		trozo = ctypes.string_at(puntero)
		if not trozo:
			break
		nombres.append(trozo.decode("utf-8", "replace"))
		puntero += len(trozo) + 1
	return nombres


def entero(al: ctypes.CDLL, dispositivo: int | None, parametro: int) -> int:
	"""Un entero de ``alcGetIntegerv``."""
	valor = ctypes.c_int(0)
	al.alcGetIntegerv(dispositivo, parametro, 1, ctypes.byref(valor))
	return valor.value


def perfiles(al: ctypes.CDLL, dispositivo: int) -> list[str]:
	"""Los perfiles HRTF que ve el dispositivo abierto, en el orden de ``ALC_HRTF_ID_SOFT``."""
	if al.alcGetStringiSOFT is None:
		return []
	cuantos = entero(al, dispositivo, ALC_NUM_HRTF_SPECIFIERS_SOFT)
	return [(al.alcGetStringiSOFT(dispositivo, ALC_HRTF_SPECIFIER_SOFT, i) or b"").decode("utf-8", "replace") for i in range(cuantos)]


def estado_hrtf(al: ctypes.CDLL, dispositivo: int) -> tuple[int, str]:
	"""(código de ``ALC_HRTF_STATUS_SOFT``, perfil en uso): el estado REAL, no el pedido."""
	return entero(al, dispositivo, ALC_HRTF_STATUS_SOFT), cadena(al, dispositivo, ALC_HRTF_SPECIFIER_SOFT)


def atributos(pares: list[tuple[int, int]]) -> ctypes.Array:
	"""Lista de atributos de contexto terminada en 0."""
	plano = [valor for par in pares for valor in par] + [0]
	return (ctypes.c_int * len(plano))(*plano)
