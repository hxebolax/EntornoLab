"""Motor OpenAL en memoria (loopback): se mezcla sin tarjeta de sonido y se mide lo que llega a cada oído."""

from __future__ import annotations

import time

import numpy as np
import pytest

from app.audio import _openal
from app.audio.base import ACUSTICAS, FRECUENCIA, ganancia_distancia
from app.audio.motor_openal import PRESETS, MotorOpenAL, cabezas_disponibles, nombre_cabeza

pytestmark = pytest.mark.skipif(not MotorOpenAL.disponible()[0], reason="OpenAL Soft no está disponible en este equipo")

# La ganancia maestra sube deprisa en las pruebas para no esperar la subida gradual de verdad.
OPCIONES = {"memoria": True, "proteccion": {"subida_maestro": 4.0, "techo_mezcla": 1.0}, "volumenes": {"maestro": 1.0}}


def _ruido(segundos: float = 1.0, semilla: int = 1) -> np.ndarray:
	return (np.random.default_rng(semilla).standard_normal(int(FRECUENCIA * segundos)) * 0.2).astype(np.float32)


def _crear(**opciones) -> MotorOpenAL:
	motor = MotorOpenAL()
	motor.iniciar(None, {**OPCIONES, **opciones})
	motor.cargar("ruido", datos=_ruido())
	motor.oyente(0.0, 0.0, 0.0, 0.0)
	for _i in range(10):
		motor.tic(0.05)
	return motor


@pytest.fixture
def motor():
	m = _crear()
	yield m
	m.cerrar()


def _medir(motor: MotorOpenAL, muestras: int = 16384, **argumentos) -> np.ndarray:
	"""Hace sonar el ruido con esos argumentos y devuelve la mezcla (muestras, 2)."""
	canal = motor.reproducir("ruido", **argumentos)
	assert canal > 0
	motor.tic(0.01)
	mezcla = motor.renderizar(muestras)
	motor.parar(canal)
	motor.renderizar(8192)  # deja apagarse lo que quede
	return mezcla


def _nivel(mezcla: np.ndarray) -> np.ndarray:
	return np.sqrt((mezcla.astype(np.float64) ** 2).mean(axis=0))


def _agudos(mezcla: np.ndarray, corte: float = 4000.0) -> float:
	"""Parte de la energía que está por encima de ``corte``."""
	espectro = np.abs(np.fft.rfft(mezcla.mean(axis=1))) ** 2
	frecuencias = np.fft.rfftfreq(len(mezcla), 1.0 / FRECUENCIA)
	return float(espectro[frecuencias >= corte].sum() / max(espectro.sum(), 1e-20))


def test_hrtf_pedido_y_verificado(motor):
	estado = motor.estado()
	assert estado["hrtf_activo"] is True
	assert estado["perfil_hrtf"] == _openal.INTEGRADA
	assert estado["frecuencia"] == FRECUENCIA
	assert estado["reverberacion"] is True
	assert estado["filtro"] is True
	assert estado["fuentes"] >= 8


def test_derecha_suena_mas_en_el_canal_derecho(motor):
	izquierda, derecha = _nivel(_medir(motor, pos=(3.0, 0.0, 0.0)))
	assert derecha > izquierda * 2
	izquierda, derecha = _nivel(_medir(motor, pos=(-3.0, 0.0, 0.0)))
	assert izquierda > derecha * 2


def test_el_oido_lejano_lo_recibe_mas_tarde(motor):
	"""Con HRTF hay diferencia de tiempo entre oídos; con panorama simple no la habría."""
	mezcla = _medir(motor, pos=(3.0, 0.0, 0.0))
	tramo = mezcla[2000:10000]
	correlacion = np.correlate(tramo[:, 0], tramo[:, 1], mode="full")
	retardo = int(np.argmax(correlacion)) - (len(tramo) - 1)  # positivo: la izquierda va retrasada
	assert 5 <= retardo <= 45


def test_delante_llega_igual_a_los_dos_oidos(motor):
	izquierda, derecha = _nivel(_medir(motor, pos=(0.0, 3.0, 0.0)))
	assert izquierda == pytest.approx(derecha, rel=0.05)


def test_el_rumbo_del_oyente_gira_el_mundo(motor):
	"""Una fuente al este queda delante si el oyente mira al este (rumbo 90), y a la izquierda si mira al sur."""
	motor.oyente(0.0, 0.0, 0.0, 90.0)
	izquierda, derecha = _nivel(_medir(motor, pos=(3.0, 0.0, 0.0)))
	assert izquierda == pytest.approx(derecha, rel=0.05)
	motor.oyente(0.0, 0.0, 0.0, 180.0)
	izquierda, derecha = _nivel(_medir(motor, pos=(3.0, 0.0, 0.0)))
	assert izquierda > derecha * 2


def test_relativo_sigue_al_oyente(motor):
	motor.oyente(10.0, -4.0, 0.0, 200.0)
	izquierda, derecha = _nivel(_medir(motor, relativo=(90.0, 2.0)))
	assert derecha > izquierda * 2


def test_sin_posicion_suena_centrado(motor):
	izquierda, derecha = _nivel(_medir(motor, bus="interfaz"))
	assert izquierda == pytest.approx(derecha, rel=0.01)
	assert izquierda > 0.05


def test_el_filtro_atenua_los_agudos(motor):
	limpio = _medir(motor, pos=(0.0, 2.0, 0.0), eco=False)
	tapado = _medir(motor, pos=(0.0, 2.0, 0.0), filtro=1.0, eco=False)
	assert _agudos(tapado) < _agudos(limpio) * 0.2
	# El nivel general baja, pero poco: el volumen lo decide el motor del juego.
	graves_limpio = 1.0 - _agudos(limpio, 500.0)
	graves_tapado = 1.0 - _agudos(tapado, 500.0)
	assert graves_tapado > graves_limpio


def test_detras_suena_mas_apagado_que_delante(motor):
	delante = _medir(motor, pos=(0.0, 2.0, 0.0), eco=False)
	detras = _medir(motor, pos=(0.0, -2.0, 0.0), eco=False)
	assert _agudos(detras, 6000.0) < _agudos(delante, 6000.0) * 0.6


def test_sin_refuerzo_detras_no_se_filtra():
	motor = _crear(refuerzo_detras=0.0)
	try:
		delante = _nivel(_medir(motor, pos=(0.0, 2.0, 0.0), eco=False))
		detras = _nivel(_medir(motor, pos=(0.0, -2.0, 0.0), eco=False))
		# Sin refuerzo solo queda la diferencia que da la propia cabeza (HRTF), mucho menor que con filtro.
		assert detras[0] > delante[0] * 0.5
	finally:
		motor.cerrar()


def test_la_distancia_sigue_la_ley_documentada(motor):
	cerca = _nivel(_medir(motor, pos=(0.0, 2.0, 0.0), eco=False))[0]
	lejos = _nivel(_medir(motor, pos=(0.0, 8.0, 0.0), eco=False))[0]
	esperado = ganancia_distancia(8.0) / ganancia_distancia(2.0)
	assert lejos / cerca == pytest.approx(esperado, rel=0.1)
	# Más cerca que la distancia de referencia no sube más: ninguna pista falsa.
	pegado = _nivel(_medir(motor, pos=(0.0, 0.5, 0.0), eco=False))[0]
	referencia = _nivel(_medir(motor, pos=(0.0, 1.0, 0.0), eco=False))[0]
	assert pegado == pytest.approx(referencia, rel=0.1)


@pytest.mark.parametrize("cabeza", [c for c in cabezas_disponibles() if c])
def test_cada_cabeza_se_activa_en_caliente(motor, cabeza):
	assert motor.poner_cabeza(cabeza) is True
	assert motor.hrtf_activo is True
	assert motor.perfil_hrtf == cabeza
	assert nombre_cabeza(cabeza)
	izquierda, derecha = _nivel(_medir(motor, pos=(3.0, 0.0, 0.0)))
	assert derecha > izquierda * 1.5


def test_hay_ocho_cabezas():
	assert len(cabezas_disponibles()) == 8
	assert cabezas_disponibles()[0] == ""


def test_cabeza_desconocida_cae_a_la_integrada():
	motor = _crear(cabeza="no_existe")
	try:
		assert motor.hrtf_activo is True
		assert motor.perfil_hrtf == _openal.INTEGRADA
	finally:
		motor.cerrar()


def test_altavoces_es_estereo_sin_hrtf(motor):
	assert motor.poner_salida("altavoces") is True
	assert motor.hrtf_activo is False
	mezcla = _medir(motor, pos=(3.0, 0.0, 0.0))
	izquierda, derecha = _nivel(mezcla)
	assert derecha > izquierda * 2
	# Sin HRTF no hay retardo entre oídos.
	tramo = mezcla[2000:10000]
	correlacion = np.correlate(tramo[:, 0], tramo[:, 1], mode="full")
	assert int(np.argmax(correlacion)) - (len(tramo) - 1) == 0
	assert motor.poner_salida("auriculares") is True
	assert motor.hrtf_activo is True


def test_mono_da_lo_mismo_a_los_dos_oidos():
	motor = _crear(mono=True)
	try:
		assert motor.hrtf_activo is False
		izquierda, derecha = _nivel(_medir(motor, pos=(3.0, 0.0, 0.0)))
		assert izquierda == pytest.approx(derecha, rel=0.01)
	finally:
		motor.cerrar()


def test_reserva_de_fuentes_roba_la_menos_importante():
	motor = _crear(fuentes=8)
	try:
		assert motor.estado()["fuentes"] == 8
		ambientes = [motor.reproducir("ruido", pos=(1.0, 1.0, 0.0), bus="ambiente", bucle=True, volumen=0.1) for _i in range(8)]
		assert all(ambientes)
		# Un sonido de música (menos importante que el ambiente) no entra.
		assert motor.reproducir("ruido", bus="musica", volumen=0.1) == 0
		# Uno de interfaz sí: roba un ambiente.
		interfaz = motor.reproducir("ruido", bus="interfaz")
		assert interfaz > 0
		assert sum(motor.suena(c) for c in ambientes) == 7
		assert motor.suena(interfaz)
		assert motor.estado()["fuentes_libres"] == 0
	finally:
		motor.cerrar()


def test_bucle_actualizar_y_fundido(motor):
	canal = motor.reproducir("ruido", pos=(2.0, 0.0, 0.0), bucle=True, bus="ambiente")
	for _i in range(10):
		motor.tic(0.05)
	motor.renderizar(FRECUENCIA * 2)  # más largo que el sonido: sigue por ser bucle
	assert motor.suena(canal)
	derecha_antes = _nivel(motor.renderizar(8192))
	motor.actualizar(canal, pos=(-2.0, 0.0, 0.0))
	motor.tic(0.05)
	motor.renderizar(4096)
	izquierda_despues = _nivel(motor.renderizar(8192))
	assert derecha_antes[1] > derecha_antes[0]
	assert izquierda_despues[0] > izquierda_despues[1]
	motor.parar(canal, fundido=0.2)
	assert motor.suena(canal)
	for _i in range(6):
		motor.tic(0.05)
	assert not motor.suena(canal)
	assert motor.estado()["fuentes_libres"] == motor.estado()["fuentes"]


def test_un_sonido_corto_termina_y_libera_su_fuente(motor):
	motor.cargar("corto", datos=_ruido(0.1))
	canal = motor.reproducir("corto")
	assert motor.suena(canal)
	motor.renderizar(FRECUENCIA // 2)
	motor.tic(0.05)
	assert not motor.suena(canal)
	assert motor.estado()["canales"] == 0


def test_el_tono_acorta_el_sonido(motor):
	motor.cargar("corto", datos=_ruido(0.4))
	canal = motor.reproducir("corto", tono=2.0)
	motor.renderizar(int(FRECUENCIA * 0.3))
	motor.tic(0.05)
	assert not motor.suena(canal)


def test_pausar_detiene_el_mundo_pero_no_la_interfaz(motor):
	mundo = motor.reproducir("ruido", pos=(0.0, 2.0, 0.0), bucle=True)
	motor.pausar(True)
	motor.tic(0.05)
	motor.renderizar(4096)  # OpenAL apaga la fuente con un fundido muy corto al pausarla
	assert _nivel(motor.renderizar(8192))[0] < 1e-4
	assert motor.suena(mundo)
	assert _nivel(_medir(motor, bus="interfaz"))[0] > 0.01
	motor.pausar(False)
	motor.tic(0.05)
	assert _nivel(motor.renderizar(8192))[0] > 1e-3


def test_reverberacion_deja_cola_y_la_seca_no(motor):
	motor.cargar("golpe", datos=_ruido(0.1))

	def cola(preset: str) -> float:
		motor.acustica(preset)
		for _i in range(20):
			motor.tic(0.05)
		motor.reproducir("golpe", pos=(0.0, 2.0, 0.0))
		motor.tic(0.01)
		motor.renderizar(int(FRECUENCIA * 0.25))  # el golpe y un poco más
		resto = motor.renderizar(int(FRECUENCIA * 0.5))
		motor.tic(0.05)
		motor.renderizar(FRECUENCIA * 3)
		return float(_nivel(resto).max())

	assert cola("seca") < 1e-5
	assert cola("nave") > 1e-4
	assert cola("nave") > cola("habitacion")


def test_hay_preset_para_todas_las_acusticas(motor):
	assert set(PRESETS) == set(ACUSTICAS)
	for preset in ACUSTICAS:
		motor.acustica(preset)
		for _i in range(15):
			motor.tic(0.05)
		activa = motor._ranuras[motor._ranura_activa]
		assert activa.preset == preset
		assert activa.ganancia == pytest.approx(PRESETS[preset].envio)


def test_la_voz_baja_el_ambiente(motor):
	canal = motor.reproducir("ruido", bucle=True, bus="ambiente")
	for _i in range(10):
		motor.tic(0.05)
	antes = _nivel(motor.renderizar(8192))[0]
	motor.atenuar_por_voz(2.0)
	for _i in range(10):
		motor.tic(0.05)
	motor.renderizar(4096)
	durante = _nivel(motor.renderizar(8192))[0]
	assert durante < antes * 0.6
	for _i in range(100):
		motor.tic(0.05)
	motor.renderizar(4096)
	despues = _nivel(motor.renderizar(8192))[0]
	assert despues == pytest.approx(antes, rel=0.1)
	motor.parar(canal)


def test_proteccion_techo_por_fuente_y_subida_gradual():
	motor = MotorOpenAL()
	motor.iniciar(None, {"memoria": True, "volumenes": {"maestro": 1.0}})
	try:
		motor.cargar("ruido", datos=_ruido())
		# Recién arrancado, la ganancia maestra está en cero y sube poco a poco.
		canal = motor.reproducir("ruido", bucle=True, volumen=50.0, bus="interfaz")
		motor.tic(0.05)
		primero = _nivel(motor.renderizar(4096))[0]
		for _i in range(40):
			motor.tic(0.05)
		motor.renderizar(4096)
		despues = _nivel(motor.renderizar(8192))[0]
		assert primero < despues * 0.2
		# Un volumen disparatado se queda en el techo de la fuente y en el de mezcla.
		assert motor.canales_activos()[0].ganancia <= motor.proteccion.techo_fuente
		assert despues <= 0.2 * motor.proteccion.techo_fuente * motor.proteccion.techo_mezcla * 1.15
		motor.parar(canal)
	finally:
		motor.cerrar()


def test_silencio_si_el_juego_deja_de_actualizar(motor):
	canal = motor.reproducir("ruido", bucle=True, bus="interfaz")
	motor.tic(0.05)
	assert _nivel(motor.renderizar(8192))[0] > 0.01
	assert motor.vigilante.comprobar(time.monotonic() + 10.0) is True
	motor.renderizar(4096)
	assert _nivel(motor.renderizar(8192))[0] < 1e-4
	# Al volver, sube poco a poco desde el silencio.
	motor.tic(0.01)
	assert motor.vigilante.callado is False
	assert _nivel(motor.renderizar(4096))[0] < 0.02
	for _i in range(20):
		motor.tic(0.05)
	motor.renderizar(4096)
	assert _nivel(motor.renderizar(8192))[0] > 0.01
	motor.parar(canal)


def test_estereo_sin_posicion_conserva_sus_dos_canales(motor):
	ruido = _ruido()
	motor.cargar("ambiente", datos=np.column_stack([ruido, np.zeros_like(ruido)]))
	canal = motor.reproducir("ambiente", bus="ambiente", bucle=True, eco=False)
	for _i in range(10):
		motor.tic(0.05)
	motor.renderizar(4096)
	izquierda, derecha = _nivel(motor.renderizar(8192))
	assert izquierda > 0.01
	assert derecha < izquierda * 0.05
	motor.parar(canal)
	# El mismo sonido estéreo, situado en el mundo, se mezcla a un canal y se posiciona.
	izquierda, derecha = _nivel(_medir_nombre(motor, "ambiente", pos=(3.0, 0.0, 0.0)))
	assert derecha > izquierda * 2


def _medir_nombre(motor: MotorOpenAL, nombre: str, **argumentos) -> np.ndarray:
	canal = motor.reproducir(nombre, **argumentos)
	motor.tic(0.01)
	mezcla = motor.renderizar(16384)
	motor.parar(canal)
	motor.renderizar(8192)
	return mezcla


def test_sonido_que_falta_no_suena_ni_rompe(motor):
	assert motor.reproducir("no/existe") == 0
	motor.resolver = lambda nombre: (_ruido(0.2), FRECUENCIA)
	assert motor.reproducir("otro/que/da/el/banco") > 0


def test_cerrar_dos_veces_y_reabrir():
	motor = _crear()
	motor.cerrar()
	motor.cerrar()
	assert motor.reproducir("ruido") == 0
	motor.iniciar(None, OPCIONES)
	assert motor.hrtf_activo is True
	motor.cerrar()


def test_carpeta_de_la_dll_y_variables_de_entorno():
	import os

	carpeta = _openal.carpeta()
	assert carpeta is not None
	assert (carpeta / "soft_oal.dll").is_file()
	assert any(carpeta.glob("LICENCIA*"))
	_openal.cargar()
	assert os.environ["ALSOFT_LOCAL_PATH"].endswith("hrtf")
	assert os.path.isdir(os.environ["ALSOFT_LOCAL_PATH"])
