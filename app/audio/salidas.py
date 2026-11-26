"""Las salidas de sonido de Windows: cuáles hay conectadas y cuál es ahora la de por defecto.

Los motores abren su salida al arrancar y se quedan con ella: si se desconectan los auriculares el
programa se quedaría mudo, y si se conectan después seguiría en los altavoces mientras el lector de
pantalla, que sí sigue a Windows, se va a los auriculares. PortAudio (motor clásico) no se entera de
que los dispositivos cambian, y OpenAL se queda en el que abrió.

Aquí se pregunta a Windows, sin abrir nada y sin cortar el sonido, qué salidas hay y cuál es la de
por defecto (la API clásica ``winmm``, que siempre está al día). Los motores lo miran cada poco y, si
su salida se ha ido o la de Windows ha cambiado, la vuelven a abrir donde toca. Los nombres de winmm
llegan cortados a 31 letras: se comparan por el principio con los de cada motor.

Adaptado de ``salidas.py`` de Puerto Bravo (mismo autor).
"""

from __future__ import annotations

import ctypes
import logging
import os

log = logging.getLogger(__name__)

_winmm: object | None = None
_intentado = False

_WAVE_MAPPER = ctypes.c_size_t(-1).value
_DRVM_MAPPER_PREFERRED_GET = 0x2015


def _biblioteca() -> object | None:
	"""``winmm`` con las firmas puestas, o None fuera de Windows o si no se puede cargar."""
	global _winmm, _intentado
	if _intentado:
		return _winmm
	_intentado = True
	if os.name != "nt":
		return None
	try:
		from ctypes import wintypes

		w = ctypes.WinDLL("winmm")
		w.waveOutGetNumDevs.restype = wintypes.UINT
		w.waveOutGetDevCapsW.restype = wintypes.UINT
		w.waveOutMessage.argtypes = [ctypes.c_void_p, wintypes.UINT, ctypes.c_void_p, ctypes.c_void_p]
		w.waveOutMessage.restype = wintypes.UINT
		_winmm = w
	except OSError, AttributeError:
		log.warning("No se pudo cargar winmm: no se seguirán los cambios de salida de sonido.", exc_info=True)
		_winmm = None
	return _winmm


def _estructura_caps() -> type[ctypes.Structure]:
	from ctypes import wintypes

	class Caps(ctypes.Structure):
		_fields_ = [
			("wMid", wintypes.WORD),
			("wPid", wintypes.WORD),
			("vDriverVersion", wintypes.UINT),
			("szPname", wintypes.WCHAR * 32),
			("dwFormats", wintypes.DWORD),
			("wChannels", wintypes.WORD),
			("wReserved1", wintypes.WORD),
			("dwSupport", wintypes.DWORD),
		]

	return Caps


def disponibles() -> list[str]:
	"""Nombres (cortos) de las salidas de sonido conectadas ahora. Lista vacía si no se puede saber."""
	w = _biblioteca()
	if w is None:
		return []
	caps = _estructura_caps()
	nombres: list[str] = []
	try:
		for i in range(int(w.waveOutGetNumDevs())):
			c = caps()
			if w.waveOutGetDevCapsW(i, ctypes.byref(c), ctypes.sizeof(c)) == 0 and c.szPname.strip():
				nombres.append(c.szPname.strip())
	except OSError:
		log.debug("No se pudieron enumerar las salidas de sonido.", exc_info=True)
		return []
	return nombres


def por_defecto() -> str:
	"""Nombre (corto) de la salida que Windows tiene ahora por defecto. Cadena vacía si no se sabe."""
	w = _biblioteca()
	if w is None:
		return ""
	from ctypes import wintypes

	dispositivo = wintypes.DWORD(0)
	banderas = wintypes.DWORD(0)
	try:
		resultado = w.waveOutMessage(
			ctypes.c_void_p(_WAVE_MAPPER),
			_DRVM_MAPPER_PREFERRED_GET,
			ctypes.cast(ctypes.byref(dispositivo), ctypes.c_void_p),
			ctypes.cast(ctypes.byref(banderas), ctypes.c_void_p),
		)
	except OSError:
		log.debug("No se pudo preguntar la salida de sonido por defecto.", exc_info=True)
		return ""
	if resultado != 0:
		return ""
	nombres = disponibles()
	return nombres[dispositivo.value] if 0 <= dispositivo.value < len(nombres) else ""


def coincide(corto: str, largo: str) -> bool:
	"""Si el nombre corto de Windows es esa salida del motor.

	«Headphones (HyperX Cloud Alpha » coincide con «Headphones (HyperX Cloud Alpha Wireless)» y con
	«OpenAL Soft on Headphones (HyperX Cloud Alpha Wireless)».
	"""
	c = (corto or "").strip().lower()
	n = (largo or "").strip().lower()
	if not c or not n:
		return False
	if n.startswith("openal soft on "):
		n = n[len("openal soft on ") :]
	if c.startswith("openal soft on "):
		c = c[len("openal soft on ") :]
	return n.startswith(c) or c.startswith(n)


def presente(nombre: str) -> bool:
	"""Si esa salida (guardada con su nombre) está conectada ahora."""
	return any(coincide(n, nombre) for n in disponibles())
