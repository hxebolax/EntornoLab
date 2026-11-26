"""Estrés de las operaciones nativas de sonido sospechosas de corromper memoria al cerrar.

Origen: una vez se vio «Windows fatal exception: code 0xc0000374» (corrupción del montículo) al
cerrar una prueba de interfaz. Lo que se repite aquí son las operaciones de los motores que
hablan con DLL por ctypes y que, hechas en mal orden, escriben o ejecutan memoria liberada:

- BASS: dos motores comparten el mismo dispositivo (BASS lo abre una vez por proceso). Antes, el
  primero que cerraba hacía ``BASS_Free`` y dejaba al otro sin dispositivo; y la retrollamada DSP
  de captura (una CFUNCTYPE) podía recogerla el recolector mientras el hilo de mezcla la llamaba.
- OpenAL: sustituir un sonido mientras un bucle lo usa deja un búfer que OpenAL no puede borrar;
  antes se olvidaba (fuga hasta cerrar el dispositivo); ahora se borra cuando queda libre.

Ninguna suena: OpenAL en memoria (loopback) y BASS en su dispositivo «sin sonido».
"""

from __future__ import annotations

import gc
import logging

import numpy as np
import pytest

from app.audio.base import FRECUENCIA
from app.audio.motor_openal import MotorOpenAL

OPCIONES = {"memoria": True, "proteccion": {"subida_maestro": 4.0, "techo_mezcla": 1.0}, "volumenes": {"maestro": 1.0}}
CICLOS = 15


def _ruido(segundos: float = 0.5, semilla: int = 1) -> np.ndarray:
	return (np.random.default_rng(semilla).standard_normal(int(FRECUENCIA * segundos)) * 0.2).astype(np.float32)


def _nivel(mezcla: np.ndarray) -> float:
	return float(np.sqrt((mezcla.astype(np.float64) ** 2).mean()))


# ── BASS ─────────────────────────────────────────────────────────────────────


def _bass():
	pytest.importorskip("basskit", reason="basskit no está instalado")
	from app.audio import motor_bass

	hay, motivo = motor_bass.MotorBass.disponible()
	if not hay:
		pytest.skip(f"el motor BASS no está disponible: {motivo}")
	return motor_bass


def _motor_bass(modulo):
	motor = modulo.MotorBass()
	motor.iniciar(None, OPCIONES)
	motor.cargar("ruido", datos=_ruido())
	motor.oyente(0.0, 0.0, 0.0, 0.0)
	for _i in range(10):
		motor.tic(0.05)
	return motor


def _suena_bass(motor) -> float:
	canal = motor.reproducir("ruido", bucle=True)
	assert canal > 0
	for _i in range(5):
		motor.tic(0.05)
	nivel = _nivel(motor.renderizar(4096))
	motor.parar(canal)
	return nivel


@pytest.mark.lento
def test_bass_dos_motores_comparten_el_dispositivo_y_cerrar_uno_no_deja_mudo_al_otro():
	modulo = _bass()
	primero = _motor_bass(modulo)
	segundo = _motor_bass(modulo)
	try:
		assert modulo._usos_dispositivo.get(modulo.DISPOSITIVO_SIN_SONIDO) == 2
		primero.cerrar()
		assert modulo._usos_dispositivo.get(modulo.DISPOSITIVO_SIN_SONIDO) == 1
		# La retrollamada del cerrado sigue viva mientras el dispositivo exista, aunque el motor desaparezca.
		del primero
		gc.collect()
		assert _suena_bass(segundo) > 0.05, "el segundo motor se quedó sin dispositivo al cerrar el primero"
	finally:
		segundo.cerrar()
	assert modulo.DISPOSITIVO_SIN_SONIDO not in modulo._usos_dispositivo
	assert modulo.DISPOSITIVO_SIN_SONIDO not in modulo._retrollamadas_vivas


@pytest.mark.lento
def test_bass_abrir_y_cerrar_muchas_veces_intercalando_motores():
	modulo = _bass()
	vivo = None
	for ciclo in range(CICLOS):
		motor = _motor_bass(modulo)
		canal = motor.reproducir("ruido", bucle=True, pos=(1.0, 2.0, 0.0))
		motor.tic(0.05)
		# El sonido se sustituye mientras su flujo lee del WAV en memoria (debe seguir vivo).
		motor.cargar("ruido", datos=_ruido(semilla=ciclo + 2))
		motor.tic(0.05)
		motor.parar(canal)
		if vivo is not None:
			vivo.cerrar()
		vivo = motor
		gc.collect()
	assert _suena_bass(vivo) > 0.05
	vivo.cerrar()
	vivo.cerrar()  # dos veces no libera dos veces
	assert modulo.DISPOSITIVO_SIN_SONIDO not in modulo._usos_dispositivo


# ── OpenAL ───────────────────────────────────────────────────────────────────


def _openal() -> None:
	hay, motivo = MotorOpenAL.disponible()
	if not hay:
		pytest.skip(f"OpenAL Soft no está disponible: {motivo}")


def _motor_openal() -> MotorOpenAL:
	motor = MotorOpenAL()
	motor.iniciar(None, OPCIONES)
	motor.cargar("ruido", datos=_ruido())
	motor.oyente(0.0, 0.0, 0.0, 0.0)
	for _i in range(10):
		motor.tic(0.05)
	return motor


@pytest.mark.lento
def test_openal_sustituir_un_bucle_que_suena_no_deja_buferes_sin_borrar(caplog):
	_openal()
	motor = _motor_openal()
	try:
		canal = motor.reproducir("ruido", bucle=True, pos=(2.0, 0.0, 0.0))
		assert canal > 0
		for ciclo in range(CICLOS):
			motor.recargar_sonido("ruido", _ruido(semilla=ciclo + 2), fundido=0.1)
			motor.tic(0.02)
			motor.renderizar(512)
		# El búfer de la sustitución anterior lo usa el bucle que se está fundiendo: queda apartado.
		assert motor._retirados, "el búfer en uso debería esperar a quedar libre"
		for _i in range(30):
			motor.tic(0.05)
			motor.renderizar(256)
			if not motor._retirados:
				break
		assert motor._retirados == [], "los búferes sustituidos no se borraron al quedar libres"
		assert motor.suena(canal)
	finally:
		with caplog.at_level(logging.WARNING, logger="app.audio.motor_openal"):
			motor.cerrar()
	assert "no borró" not in caplog.text


@pytest.mark.lento
def test_openal_dos_motores_intercalados_abren_y_cierran_sin_pisarse():
	_openal()
	vivo: MotorOpenAL | None = None
	for _ciclo in range(CICLOS):
		motor = _motor_openal()
		motor.reproducir("ruido", bucle=True, pos=(0.0, 3.0, 0.0))
		motor.tic(0.05)
		if vivo is not None:
			# El otro motor sigue mezclando con su contexto mientras este existe.
			assert vivo.suena(vivo.reproducir("ruido", bucle=True))
			vivo.cerrar()
		vivo = motor
		gc.collect()
	assert vivo is not None
	for _i in range(5):
		vivo.tic(0.05)
	assert _nivel(vivo.renderizar(2048)) > 0.01
	vivo.cerrar()
	vivo.cerrar()
