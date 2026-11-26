"""Puente entre la configuración compartida y las piezas del reproductor.

Los motores de sonido, la voz, la vibración y la sesión del motor no leen la
configuración global: reciben diccionarios. Aquí está, en un solo sitio, la
traducción de las claves de ``app/core/configuracion.py`` (las mismas que usa
el Estudio) a esos diccionarios. Así un cambio de nombre de una clave se
arregla aquí y no en diez pantallas.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from app.motor.sesion import AjustesJuego

log = logging.getLogger(__name__)

# Buses del motor de sonido que tienen volumen propio en la configuración (sonido.volumen_<bus>).
BUSES: tuple[str, ...] = ("maestro", "efectos", "pasos", "ambiente", "ayudas", "interfaz", "musica", "voz")

# Con la protección auditiva «desactivada» los límites se relajan, pero no desaparecen:
# el motor de sonido nunca deja quitarlos del todo (ver docs/sonido.md).
_PROTECCION_RELAJADA: dict[str, float] = {"techo_fuente": 1.5, "techo_mezcla": 1.0, "subida_maestro": 4.0, "subida_fuente": 50.0}

# Claves que son preferencias del ALUMNO: con un alias elegido se guardan en su perfil y nunca en la
# configuración compartida con el Estudio (ver ``Aplicacion.preferencia``); sin alias, en la configuración.
PREFERENCIAS_JUEGO: tuple[str, ...] = (
	"juego.modo_movimiento",
	"juego.paso_m",
	"juego.giro_grados",
	"juego.velocidad_ms",
	"juego.formato_direccion",
	"juego.unidad",
	"juego.estilo",
	"voz.detalle",
)

# Campo de ``AjustesJuego`` (y de los ajustes de la ficha del Estudio) → clave de la configuración.
CLAVE_DE_CAMPO: dict[str, str] = {
	"modo_movimiento": "juego.modo_movimiento",
	"paso_m": "juego.paso_m",
	"giro_grados": "juego.giro_grados",
	"velocidad_ms": "juego.velocidad_ms",
	"formato_direccion": "juego.formato_direccion",
	"unidad": "juego.unidad",
	"estilo": "juego.estilo",
	"detalle": "voz.detalle",
}
CAMPO_DE_CLAVE: dict[str, str] = {clave: campo for campo, clave in CLAVE_DE_CAMPO.items()}


def opciones_sonido(config: Any, memoria: bool = False) -> dict[str, Any]:
	"""Diccionario para ``crear_motor`` y ``MotorAudio.iniciar`` a partir de la sección ``sonido``.

	``memoria`` abre los motores sin tarjeta de sonido (pruebas automáticas).
	"""
	sonido = config.obtener("sonido", {}) or {}
	opciones: dict[str, Any] = {
		"motor": str(sonido.get("motor") or "openal"),
		"dispositivo": str(sonido.get("dispositivo") or ""),
		"salida": str(sonido.get("modo_salida") or "auriculares"),
		"cabeza": str(sonido.get("perfil_hrtf") or ""),
		"refuerzo_detras": 1.0 if sonido.get("refuerzo_detras", True) else 0.0,
		"volumenes": {bus: float(sonido.get(f"volumen_{bus}", 1.0)) for bus in BUSES},
		"proteccion": {} if sonido.get("proteccion_auditiva", True) else dict(_PROTECCION_RELAJADA),
	}
	if config.obtener("supervision.segunda_salida", False):
		opciones["segunda_salida"] = str(sonido.get("segunda_salida") or "")
	if memoria:
		opciones["memoria"] = True
	return opciones


def opciones_voz(config: Any) -> dict[str, Any]:
	"""Diccionario para ``Voz`` a partir de la sección ``voz`` (la velocidad pasa de 0–100 a −10–10 de SAPI)."""
	voz = config.obtener("voz", {}) or {}
	try:
		velocidad = round((float(voz.get("velocidad", 50)) - 50.0) / 5.0)
	except TypeError, ValueError:
		velocidad = 0
	canales = voz.get("canales")
	return {
		"salida": str(voz.get("salida") or "automatica"),
		"sapi_voz": str(voz.get("voz_sapi") or ""),
		"sapi_velocidad": int(velocidad),
		"sapi_volumen": voz.get("volumen", 100),
		"braille": "temporal" if voz.get("braille", True) else "nada",
		"nunca_interrumpir": not bool(voz.get("interrumpir", True)),
		"canales": dict(canales) if isinstance(canales, dict) else {},
		"historial_max": max(10, int(voz.get("historial", 50) or 50)),
	}


def opciones_mando(config: Any) -> dict[str, Any]:
	"""Opciones del mando que tienen clave en la configuración (lo demás queda de serie)."""
	return {
		"zona_muerta": float(config.obtener("mando.zona_muerta", 0.2)),
		"vibracion": bool(config.obtener("mando.vibracion", True)),
		"fuerza_vibracion": float(config.obtener("mando.fuerza_vibracion", 1.0)),
	}


def opciones_haptica(config: Any) -> dict[str, Any]:
	"""Opciones del vocabulario de vibración (``app.audio.haptica``)."""
	return {"activa": bool(config.obtener("mando.vibracion", True)), "fuerza": float(config.obtener("mando.fuerza_vibracion", 1.0))}


def mapa_o_nada(valor: Any) -> dict | None:
	"""Un mapa de teclas o de botones guardado, o None si está vacío (se usa entonces el de serie)."""
	return dict(valor) if isinstance(valor, dict) and valor else None


def ajustes_juego(config: Any, preferencia: Callable[[str], Any] | None = None) -> AjustesJuego:
	"""Los ajustes de juego del alumno (sección ``juego`` y ``voz.detalle``), saneados por el motor.

	``preferencia(clave)`` da el valor que vale para el alumno (ficha del
	Estudio, perfil o configuración, ver ``Aplicacion.preferencia``); sin ella
	se lee la configuración tal cual.
	"""
	leer = preferencia if preferencia is not None else config.obtener
	datos: dict[str, Any] = {}
	for campo, clave in CLAVE_DE_CAMPO.items():
		valor = leer(clave)
		if valor is not None:
			datos[campo] = valor
	return AjustesJuego.de_dict(datos)
