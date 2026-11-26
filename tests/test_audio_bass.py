"""Motor BASS de verdad, sin que suene nada: dispositivo «sin sonido» de BASS y captura de la mezcla final.

BASS mezcla en tiempo real también sin tarjeta, así que cada medida espera lo que dura (unas décimas
de segundo). Si ``basskit`` no está instalado, todo el módulo se salta con un mensaje claro: se instala
con ``entorno.bat instalar`` (la rueda está en ``__pip__``).

La única prueba que abre una salida real (el cambio de dispositivo en caliente) está apagada de serie
y, cuando se pide con ``APP_PRUEBA_SALIDA_REAL=1``, se hace con el volumen general a cero.
"""

from __future__ import annotations

import os
import time

import numpy as np
import pytest

pytest.importorskip(
	"basskit",
	reason="basskit no está instalado: ejecute «entorno.bat instalar» (instala la rueda de __pip__) para probar el motor BASS",
)

from app.audio import fabrica  # noqa: E402 - después de comprobar que basskit está
from app.audio.base import FRECUENCIA, ErrorMotor, ganancia_distancia  # noqa: E402
from app.audio.motor_bass import (  # noqa: E402
	DECIBELIOS_BANDA,
	DISPOSITIVO_DE_WINDOWS,
	MotorBass,
	decibelios_de_banda,
)

_hay, _motivo = MotorBass.disponible()
pytestmark = pytest.mark.skipif(not _hay, reason=f"el motor BASS no está disponible en este equipo: {_motivo}")

# La ganancia maestra sube deprisa en las pruebas para no esperar la subida gradual de verdad.
OPCIONES = {"memoria": True, "proteccion": {"subida_maestro": 4.0, "techo_mezcla": 1.0}, "volumenes": {"maestro": 1.0}}
MUESTRAS = 8192
# Nivel (RMS) del ruido de prueba tal como está cargado.
NIVEL_RUIDO = 0.2


def _ruido(segundos: float = 1.0, semilla: int = 1) -> np.ndarray:
	return (np.random.default_rng(semilla).standard_normal(int(FRECUENCIA * segundos)) * NIVEL_RUIDO).astype(np.float32)


def _tono(hercios: float, segundos: float = 1.0) -> np.ndarray:
	t = np.arange(int(FRECUENCIA * segundos)) / FRECUENCIA
	return (0.2 * np.sin(2.0 * np.pi * hercios * t)).astype(np.float32)


def _avanzar(motor: MotorBass, veces: int = 10) -> None:
	"""Fotogramas suficientes para que la ganancia maestra y la de los bucles lleguen a su sitio."""
	for _i in range(veces):
		motor.tic(0.05)
	# BASS aplica los cambios de volumen con una rampa de unos milisegundos.
	time.sleep(0.03)


def _crear(**opciones) -> MotorBass:
	motor = MotorBass()
	motor.iniciar(None, {**OPCIONES, **opciones})
	motor.cargar("ruido", datos=_ruido())
	motor.oyente(0.0, 0.0, 0.0, 0.0)
	_avanzar(motor)
	return motor


@pytest.fixture
def motor():
	m = _crear()
	yield m
	m.cerrar()


def _medir(motor: MotorBass, nombre: str = "ruido", muestras: int = MUESTRAS, **argumentos) -> np.ndarray:
	"""Hace sonar ``nombre`` en bucle con esos argumentos y devuelve la mezcla (muestras, 2)."""
	canal = motor.reproducir(nombre, bucle=True, **argumentos)
	assert canal > 0
	_avanzar(motor)
	mezcla = motor.renderizar(muestras)
	motor.parar(canal)
	return mezcla


def _nivel(mezcla: np.ndarray) -> np.ndarray:
	return np.sqrt((mezcla.astype(np.float64) ** 2).mean(axis=0))


def _agudos(mezcla: np.ndarray, desde: float = 4000.0, hasta: float = 12000.0) -> float:
	"""Energía entre ``desde`` y ``hasta``: la zona que el ecualizador de BASS apaga de verdad.

	Por encima de 16 kHz sus bandas ya no llegan (el centro más alto que admite es 16 kHz), y ahí el
	ruido blanco de prueba tiene tanta energía como en cualquier otra parte.
	"""
	espectro = np.abs(np.fft.rfft(mezcla.mean(axis=1))) ** 2
	frecuencias = np.fft.rfftfreq(len(mezcla), 1.0 / FRECUENCIA)
	return float(espectro[(frecuencias >= desde) & (frecuencias < hasta)].sum())


def _frecuencia_dominante(mezcla: np.ndarray) -> float:
	espectro = np.abs(np.fft.rfft(mezcla.mean(axis=1) * np.hanning(len(mezcla))))
	return float(np.fft.rfftfreq(len(mezcla), 1.0 / FRECUENCIA)[int(espectro.argmax())])


# ── Disponibilidad, estado y salidas ─────────────────────────────────────────


def test_bass_viene_incluido_y_esta_disponible():
	assert MotorBass.disponible() == (True, "")
	por_id = {m["id"]: m for m in fabrica.motores_disponibles()}
	assert por_id["bass"]["disponible"] is True
	assert por_id["bass"]["motivo"] == ""
	assert "opcional" not in por_id["bass"]["nombre"].lower()


def test_estado_en_memoria(motor):
	estado = motor.estado()
	assert estado["motor"] == "bass"
	assert estado["version"].startswith("2.4")
	assert estado["memoria"] is True
	assert estado["dispositivo"] == ""
	assert estado["hrtf_activo"] is False
	assert estado["filtro"] is True
	assert estado["compresor"] is True


def test_lista_de_salidas_sin_las_entradas_ficticias(motor):
	nombres = motor.dispositivos()
	assert all(isinstance(nombre, str) and nombre for nombre in nombres)
	assert "No sound" not in nombres
	assert "Default" not in nombres
	# Se puede preguntar también sin haber iniciado el motor (lo hacen las preferencias).
	assert MotorBass().dispositivos() == nombres


def test_en_memoria_no_se_cambia_de_salida(motor):
	assert motor.cambiar_dispositivo("Una salida que no existe") is False
	assert motor.cambiar_dispositivo(None) is False
	assert motor.estado()["dispositivo"] == ""


def test_salida_sin_nombre_es_la_de_windows_y_una_desconocida_no_existe(motor):
	assert motor._indice_de("") == DISPOSITIVO_DE_WINDOWS
	assert motor._indice_de("Una salida que no existe") is None
	for nombre in motor.dispositivos():
		indice = motor._indice_de(nombre)
		assert indice is not None and indice > DISPOSITIVO_DE_WINDOWS
		# Un nombre guardado con OpenAL o cortado por Windows a 31 letras sirve igual.
		assert motor._indice_de("OpenAL Soft on " + nombre) is not None
		assert motor._indice_de(nombre[:31]) is not None


def test_renderizar_solo_en_memoria():
	with pytest.raises(ErrorMotor):
		MotorBass().renderizar(100)


def test_sin_iniciar_no_suena_y_cerrar_dos_veces_no_falla():
	motor = MotorBass()
	motor.cargar("ruido", datos=_ruido(0.1))
	assert motor.reproducir("ruido") == 0
	motor.tic(0.05)
	motor.cerrar()
	motor.cerrar()


def test_se_puede_iniciar_de_nuevo_tras_cerrar():
	motor = _crear()
	motor.cerrar()
	motor.iniciar(None, OPCIONES)
	try:
		motor.cargar("ruido", datos=_ruido())
		_avanzar(motor)
		assert _nivel(_medir(motor)).min() > 0.1
	finally:
		motor.cerrar()


# ── Posición en el mundo ─────────────────────────────────────────────────────


def test_derecha_e_izquierda(motor):
	izquierda, derecha = _nivel(_medir(motor, pos=(3.0, 0.0, 0.0)))
	assert derecha > 0.03
	assert derecha > izquierda * 5
	izquierda, derecha = _nivel(_medir(motor, pos=(-3.0, 0.0, 0.0)))
	assert izquierda > 0.03
	assert izquierda > derecha * 5


def test_delante_suena_igual_en_los_dos_oidos(motor):
	izquierda, derecha = _nivel(_medir(motor, pos=(0.0, 3.0, 0.0)))
	assert izquierda > 0.02
	assert izquierda == pytest.approx(derecha, rel=0.02)


def test_en_diagonal_suena_en_los_dos_pero_mas_en_el_cercano(motor):
	izquierda, derecha = _nivel(_medir(motor, pos=(2.0, 2.0, 0.0)))
	assert izquierda > 0.005
	assert derecha > izquierda * 1.5


def test_al_girar_el_oyente_el_sonido_se_queda_en_su_sitio(motor):
	canal = motor.reproducir("ruido", pos=(0.0, 3.0, 0.0), bucle=True)
	motor.oyente(0.0, 0.0, 0.0, 90.0)  # mira al este: el norte queda a su izquierda
	_avanzar(motor)
	izquierda, derecha = _nivel(motor.renderizar(MUESTRAS))
	assert izquierda > derecha * 5
	motor.oyente(0.0, 0.0, 0.0, 270.0)  # mira al oeste: el norte queda a su derecha
	_avanzar(motor, 2)
	izquierda, derecha = _nivel(motor.renderizar(MUESTRAS))
	assert derecha > izquierda * 5
	motor.parar(canal)


def test_al_acercarse_el_oyente_suena_mas_fuerte(motor):
	canal = motor.reproducir("ruido", pos=(0.0, 8.0, 0.0), bucle=True)
	_avanzar(motor)
	lejos = _nivel(motor.renderizar(MUESTRAS)).mean()
	motor.oyente(0.0, 6.0, 0.0, 0.0)
	_avanzar(motor, 2)
	cerca = _nivel(motor.renderizar(MUESTRAS)).mean()
	motor.parar(canal)
	assert cerca == pytest.approx(lejos * 4.0, rel=0.1)


def test_ley_de_distancia_como_la_de_los_demas_motores(motor):
	uno = _nivel(_medir(motor, pos=(0.0, 1.0, 0.0))).mean()
	for metros in (2.0, 4.0, 10.0):
		medido = _nivel(_medir(motor, pos=(0.0, metros, 0.0))).mean()
		assert medido / uno == pytest.approx(ganancia_distancia(metros), rel=0.1)
	# Más cerca que la referencia no sube, y más allá de la máxima no sigue bajando ni se corta.
	assert _nivel(_medir(motor, pos=(0.0, 0.3, 0.0))).mean() == pytest.approx(uno, rel=0.1)
	en_el_tope = _nivel(_medir(motor, pos=(0.0, 60.0, 0.0))).mean()
	mas_alla = _nivel(_medir(motor, pos=(0.0, 200.0, 0.0))).mean()
	assert mas_alla > 0.0
	assert mas_alla == pytest.approx(en_el_tope, rel=0.1)


def test_la_altura_cuenta_como_distancia(motor):
	mismo_plano = _nivel(_medir(motor, pos=(0.0, 3.0, 0.0))).mean()
	arriba = _nivel(_medir(motor, pos=(0.0, 3.0, 4.0))).mean()
	assert arriba / mismo_plano == pytest.approx(ganancia_distancia(5.0) / ganancia_distancia(3.0), rel=0.1)


def test_sin_caida_la_distancia_no_atenua():
	motor = _crear(distancia_caida=0.0)
	try:
		cerca = _nivel(_medir(motor, pos=(0.0, 1.0, 0.0))).mean()
		lejos = _nivel(_medir(motor, pos=(0.0, 20.0, 0.0))).mean()
		assert lejos == pytest.approx(cerca, rel=0.1)
		# Y se puede volver a poner en caliente.
		motor.configurar({"distancia_caida": 1.0})
		assert _nivel(_medir(motor, pos=(0.0, 20.0, 0.0))).mean() < cerca * 0.1
	finally:
		motor.cerrar()


def test_relativo_gira_con_el_oyente(motor):
	canal = motor.reproducir("ruido", relativo=(90.0, 2.0), bucle=True)
	_avanzar(motor)
	izquierda, derecha = _nivel(motor.renderizar(MUESTRAS))
	assert derecha > izquierda * 5
	motor.oyente(10.0, -4.0, 0.0, 180.0)
	_avanzar(motor, 2)
	izquierda, derecha = _nivel(motor.renderizar(MUESTRAS))
	assert derecha > izquierda * 5
	motor.parar(canal)


def test_sin_posicion_suena_igual_por_los_dos_oidos_y_sin_atenuar(motor):
	motor.oyente(50.0, 50.0, 0.0, 123.0)
	izquierda, derecha = _nivel(_medir(motor, bus="efectos"))
	assert izquierda == pytest.approx(derecha, rel=0.01)
	assert izquierda == pytest.approx(NIVEL_RUIDO, rel=0.1)


def test_un_bucle_se_mueve_al_actualizarlo(motor):
	canal = motor.reproducir("ruido", pos=(3.0, 0.0, 0.0), bucle=True)
	_avanzar(motor)
	izquierda, derecha = _nivel(motor.renderizar(MUESTRAS))
	assert derecha > izquierda * 5
	motor.actualizar(canal, pos=(-3.0, 0.0, 0.0))
	_avanzar(motor, 2)
	izquierda, derecha = _nivel(motor.renderizar(MUESTRAS))
	assert izquierda > derecha * 5
	assert motor.suena(canal)
	motor.parar(canal)
	assert not motor.suena(canal)


def test_con_mono_los_dos_oidos_oyen_lo_mismo():
	motor = _crear(mono=True)
	try:
		izquierda, derecha = _nivel(_medir(motor, pos=(3.0, 0.0, 0.0)))
		assert izquierda > 0.02
		assert izquierda == pytest.approx(derecha, rel=0.02)
		izquierda, derecha = _nivel(_medir(motor, relativo=(-90.0, 2.0)))
		assert izquierda == pytest.approx(derecha, rel=0.02)
		# La distancia se sigue oyendo.
		assert _nivel(_medir(motor, pos=(6.0, 0.0, 0.0))).mean() < izquierda
	finally:
		motor.cerrar()


def test_un_sonido_estereo_conserva_sus_dos_canales(motor):
	estereo = np.zeros((FRECUENCIA, 2), dtype=np.float32)
	estereo[:, 1] = _ruido()
	motor.cargar("solo_derecha", datos=estereo)
	izquierda, derecha = _nivel(_medir(motor, "solo_derecha", bus="ambiente"))
	assert derecha > 0.05
	assert izquierda < derecha * 0.01


# ── Volumen, tono y filtro ───────────────────────────────────────────────────


def test_volumen_del_canal_y_del_bus(motor):
	completo = _nivel(_medir(motor)).mean()
	assert _nivel(_medir(motor, volumen=0.5)).mean() == pytest.approx(completo * 0.5, rel=0.1)
	motor.volumen_bus("efectos", 0.25)
	assert _nivel(_medir(motor)).mean() == pytest.approx(completo * 0.25, rel=0.1)
	# Los demás buses no cambian.
	motor.volumen_bus("interfaz", 1.0)
	assert _nivel(_medir(motor, bus="interfaz")).mean() == pytest.approx(completo, rel=0.1)


def test_actualizar_el_volumen_de_un_bucle(motor):
	canal = motor.reproducir("ruido", bucle=True)
	_avanzar(motor)
	antes = _nivel(motor.renderizar(MUESTRAS)).mean()
	motor.actualizar(canal, volumen=0.3)
	_avanzar(motor, 2)
	despues = _nivel(motor.renderizar(MUESTRAS)).mean()
	motor.parar(canal)
	assert despues == pytest.approx(antes * 0.3, rel=0.1)


def test_volumen_maestro_y_subida_gradual(motor):
	completo = _nivel(_medir(motor)).mean()
	motor.volumen_bus("maestro", 0.5)
	assert _nivel(_medir(motor)).mean() == pytest.approx(completo * 0.5, rel=0.1)
	# Bajar es inmediato; subir, poco a poco (4 por segundo en estas pruebas).
	motor.volumen_bus("maestro", 0.0)
	motor.tic(0.05)
	motor.volumen_bus("maestro", 1.0)
	canal = motor.reproducir("ruido", bucle=True, bus="interfaz")
	motor.tic(0.05)
	assert motor._maestro == pytest.approx(0.2)
	_avanzar(motor)
	assert motor._maestro == pytest.approx(1.0)
	motor.parar(canal)


def test_el_tono_cambia_la_altura_tambien_mientras_suena(motor):
	motor.cargar("la", datos=_tono(1000.0))
	canal = motor.reproducir("la", bucle=True)
	_avanzar(motor)
	assert _frecuencia_dominante(motor.renderizar(MUESTRAS)) == pytest.approx(1000.0, abs=15.0)
	motor.actualizar(canal, tono=2.0)
	_avanzar(motor, 2)
	assert _frecuencia_dominante(motor.renderizar(MUESTRAS)) == pytest.approx(2000.0, abs=30.0)
	motor.actualizar(canal, tono=0.5)
	_avanzar(motor, 2)
	assert _frecuencia_dominante(motor.renderizar(MUESTRAS)) == pytest.approx(500.0, abs=15.0)
	motor.parar(canal)
	# Y al empezar.
	assert _frecuencia_dominante(_medir(motor, "la", tono=1.5)) == pytest.approx(1500.0, abs=25.0)


def test_el_filtro_quita_agudos_y_deja_los_graves(motor):
	motor.cargar("grave", datos=_tono(200.0))
	limpio = _agudos(_medir(motor, pos=(0.0, 2.0, 0.0)))
	medio = _agudos(_medir(motor, pos=(0.0, 2.0, 0.0), filtro=0.5))
	tapado = _agudos(_medir(motor, pos=(0.0, 2.0, 0.0), filtro=1.0))
	assert medio < limpio * 0.25
	assert tapado < medio * 0.25
	assert tapado < limpio * 0.02
	# Una pared deja pasar los graves: como mucho el 25 % menos de nivel general y poco más.
	grave = _nivel(_medir(motor, "grave", pos=(0.0, 2.0, 0.0))).mean()
	grave_tapado = _nivel(_medir(motor, "grave", pos=(0.0, 2.0, 0.0), filtro=1.0)).mean()
	assert grave_tapado > grave * 0.55


def test_el_filtro_de_un_bucle_se_actualiza(motor):
	canal = motor.reproducir("ruido", pos=(0.0, 2.0, 0.0), bucle=True)
	_avanzar(motor)
	limpio = _agudos(motor.renderizar(MUESTRAS))
	motor.actualizar(canal, filtro=1.0)
	_avanzar(motor, 2)
	tapado = _agudos(motor.renderizar(MUESTRAS))
	motor.actualizar(canal, filtro=0.0)
	_avanzar(motor, 2)
	de_nuevo = _agudos(motor.renderizar(MUESTRAS))
	motor.parar(canal)
	assert tapado < limpio * 0.02
	assert de_nuevo == pytest.approx(limpio, rel=0.25)


def test_detras_suena_mas_apagado_que_delante(motor):
	delante = _agudos(_medir(motor, pos=(0.0, 3.0, 0.0)))
	detras = _agudos(_medir(motor, pos=(0.0, -3.0, 0.0)))
	assert detras < delante * 0.2
	# Y cambia al girar el oyente, sin tocar la fuente.
	canal = motor.reproducir("ruido", pos=(0.0, 3.0, 0.0), bucle=True)
	motor.oyente(0.0, 0.0, 0.0, 180.0)
	_avanzar(motor)
	de_espaldas = _agudos(motor.renderizar(MUESTRAS))
	motor.parar(canal)
	assert de_espaldas < delante * 0.2


def test_sin_refuerzo_detras_suena_como_delante():
	motor = _crear(refuerzo_detras=0.0)
	try:
		delante = _agudos(_medir(motor, pos=(0.0, 3.0, 0.0)))
		detras = _agudos(_medir(motor, pos=(0.0, -3.0, 0.0)))
		assert detras == pytest.approx(delante, rel=0.25)
	finally:
		motor.cerrar()


def test_reparto_de_la_bajada_entre_las_bandas():
	assert decibelios_de_banda(1.0) == 0.0
	assert decibelios_de_banda(2.0) == 0.0
	assert decibelios_de_banda(0.0) == DECIBELIOS_BANDA
	assert DECIBELIOS_BANDA < decibelios_de_banda(0.15) < decibelios_de_banda(0.5) < 0.0


# ── Bucles, final, pausa y fundidos ──────────────────────────────────────────


def test_un_sonido_corto_termina_y_un_bucle_sigue(motor):
	motor.cargar("corto", datos=_ruido(0.15))
	suelto = motor.reproducir("corto")
	bucle = motor.reproducir("corto", bucle=True)
	assert suelto > 0 and bucle > 0
	assert motor.suena(suelto)
	time.sleep(0.4)
	motor.tic(0.05)
	assert not motor.suena(suelto)
	assert motor.suena(bucle)
	assert [c.id for c in motor.canales_activos()] == [bucle]
	_avanzar(motor)
	assert _nivel(motor.renderizar(MUESTRAS)).mean() > 0.1
	motor.parar(bucle)
	_avanzar(motor, 1)
	assert _nivel(motor.renderizar(MUESTRAS)).max() < 1e-4


def test_pausar_calla_el_mundo_pero_no_la_interfaz(motor):
	mundo = motor.reproducir("ruido", pos=(-3.0, 0.0, 0.0), bucle=True)
	_avanzar(motor)
	assert _nivel(motor.renderizar(MUESTRAS))[0] > 0.03
	motor.pausar(True)
	_avanzar(motor, 1)
	assert _nivel(motor.renderizar(MUESTRAS)).max() < 1e-4
	assert motor.suena(mundo)
	# Lo que empieza durante la pausa espera; la interfaz suena.
	otro = motor.reproducir("ruido", pos=(-3.0, 0.0, 0.0), bucle=True)
	interfaz = motor.reproducir("ruido", bus="interfaz", bucle=True)
	_avanzar(motor)
	izquierda, derecha = _nivel(motor.renderizar(MUESTRAS))
	assert izquierda == pytest.approx(derecha, rel=0.02)
	assert izquierda > 0.1
	motor.parar(interfaz)
	motor.pausar(False)
	_avanzar(motor)
	izquierda, derecha = _nivel(motor.renderizar(MUESTRAS))
	assert izquierda > 0.05 and derecha < izquierda * 0.2
	motor.parar(mundo)
	motor.parar(otro)


def test_parar_con_fundido_y_parar_todo_por_bus(motor):
	canal = motor.reproducir("ruido", bucle=True)
	ambiente = motor.reproducir("ruido", bucle=True, bus="ambiente")
	_avanzar(motor)
	motor.parar(canal, fundido=0.2)
	motor.tic(0.1)
	assert motor.suena(canal)
	motor.tic(0.15)
	assert not motor.suena(canal)
	assert motor.suena(ambiente)
	motor.parar_todo("ambiente")
	assert motor.canales_activos() == []


def test_la_voz_baja_el_ambiente(motor):
	canal = motor.reproducir("ruido", bucle=True, bus="ambiente")
	_avanzar(motor)
	antes = _nivel(motor.renderizar(MUESTRAS)).mean()
	motor.atenuar_por_voz(5.0)
	_avanzar(motor, 20)
	durante = _nivel(motor.renderizar(MUESTRAS)).mean()
	motor.parar(canal)
	assert durante == pytest.approx(antes * 0.45, rel=0.15)


# ── Protección ───────────────────────────────────────────────────────────────


def test_si_el_juego_deja_de_actualizar_se_calla_y_vuelve_poco_a_poco(motor):
	canal = motor.reproducir("ruido", bucle=True)
	_avanzar(motor)
	assert _nivel(motor.renderizar(MUESTRAS)).mean() > 0.1
	assert motor.vigilante is not None
	assert motor.vigilante.comprobar(time.monotonic() + 10.0) is True
	time.sleep(0.05)
	assert _nivel(motor.renderizar(MUESTRAS)).max() < 1e-4
	motor.tic(0.05)
	assert 0.0 < motor._maestro <= 0.25
	_avanzar(motor)
	assert _nivel(motor.renderizar(MUESTRAS)).mean() > 0.1
	motor.parar(canal)


def test_el_techo_por_fuente_se_respeta(motor):
	normal = _nivel(_medir(motor)).mean()
	exagerado = _nivel(_medir(motor, volumen=5.0)).mean()
	assert exagerado == pytest.approx(normal, rel=0.1)


def test_el_compresor_contiene_la_suma_de_muchos_sonidos(motor):
	uno = _nivel(_medir(motor)).mean()
	canales = []
	for semilla in range(8):
		motor.cargar(f"ruido{semilla}", datos=_ruido(semilla=10 + semilla))
		canales.append(motor.reproducir(f"ruido{semilla}", bucle=True))
	_avanzar(motor)
	time.sleep(0.3)  # el compresor tarda unas décimas en asentarse
	ocho = _nivel(motor.renderizar(MUESTRAS)).mean()
	motor.parar_todo()
	# Ocho ruidos distintos sin comprimir sumarían raíz de ocho veces el nivel de uno.
	assert ocho > uno
	assert ocho < uno * np.sqrt(8.0) * 0.85


def test_robo_de_fuentes_por_prioridad(motor):
	motor.FUENTES_MAXIMAS = 3
	ambiente = [motor.reproducir("ruido", bucle=True, bus="ambiente", volumen=0.1) for _i in range(3)]
	assert all(ambiente)
	interfaz = motor.reproducir("ruido", bus="interfaz", volumen=0.1)
	assert interfaz > 0
	assert len(motor.canales_activos()) == 3
	assert sum(motor.suena(c) for c in ambiente) == 2
	# Lo menos importante no roba a lo más importante.
	motor.parar_todo()
	for _i in range(3):
		assert motor.reproducir("ruido", bucle=True, bus="interfaz", volumen=0.1) > 0
	assert motor.reproducir("ruido", bus="musica", volumen=0.1) == 0


# ── Fábrica ──────────────────────────────────────────────────────────────────


def test_la_fabrica_crea_el_motor_bass_cuando_se_pide():
	motor = fabrica.crear_motor({"motor": "bass", **OPCIONES})
	try:
		assert motor.nombre == "bass"
		assert motor.pedido == "bass"
		assert motor.estado()["memoria"] is True
	finally:
		motor.cerrar()


def test_el_motor_de_serie_sigue_siendo_openal():
	assert fabrica.MOTOR_DE_SERIE == "openal"
	assert "bass" not in fabrica.CADENA
	assert fabrica.cadena_de("bass")[0] == "bass"


# ── Salida real (apagada de serie) ───────────────────────────────────────────


@pytest.mark.skipif(
	os.environ.get("APP_PRUEBA_SALIDA_REAL") != "1",
	reason="abre la tarjeta de sonido (en silencio): solo con APP_PRUEBA_SALIDA_REAL=1",
)
def test_cambio_de_salida_en_caliente_en_silencio():
	motor = MotorBass()
	if len(motor.dispositivos()) < 1:
		pytest.skip("este equipo no tiene ninguna salida de sonido")
	# Volumen maestro a cero: se abre la tarjeta, pero no llega nada a los altavoces.
	motor.iniciar(None, {"volumenes": {"maestro": 0.0}})
	try:
		motor.cargar("ruido", datos=_ruido())
		canal = motor.reproducir("ruido", pos=(1.0, 1.0, 0.0), bucle=True, volumen=0.0)
		motor.tic(0.05)
		assert motor.estado()["dispositivo"] in motor.dispositivos()
		for nombre in motor.dispositivos():
			assert motor.cambiar_dispositivo(nombre) is True
			motor.tic(0.05)
			assert motor.estado()["dispositivo"] == nombre
			assert motor.suena(canal)
		assert motor.cambiar_dispositivo("Una salida que no existe") is False
		assert motor.cambiar_dispositivo("") is True
		motor.tic(0.05)
		assert motor.suena(canal)
		assert motor._maestro == 0.0
	finally:
		motor.cerrar()
