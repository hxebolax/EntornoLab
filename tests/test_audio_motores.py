"""Motores nulo, clásico (en memoria) y estéreo (con el sonido «dummy» de SDL), protección y fábrica."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import time  # noqa: E402 - las variables de SDL van antes de cualquier import que cargue pygame

import numpy as np  # noqa: E402
import pytest  # noqa: E402

from app.audio import base, fabrica  # noqa: E402
from app.audio.base import FRECUENCIA, MotorNoDisponible  # noqa: E402
from app.audio.motor_bass import MotorBass  # noqa: E402
from app.audio.motor_clasico import MotorClasico  # noqa: E402
from app.audio.motor_estereo import MotorEstereo  # noqa: E402
from app.audio.motor_nulo import MotorNulo  # noqa: E402
from app.audio.proteccion import Proteccion, Vigilante  # noqa: E402

RAPIDO = {"proteccion": {"subida_maestro": 4.0, "techo_mezcla": 1.0}, "volumenes": {"maestro": 1.0}}


def _ruido(segundos: float = 1.0, semilla: int = 3) -> np.ndarray:
	return (np.random.default_rng(semilla).standard_normal(int(FRECUENCIA * segundos)) * 0.2).astype(np.float32)


def _nivel(mezcla: np.ndarray) -> np.ndarray:
	return np.sqrt((mezcla.astype(np.float64) ** 2).mean(axis=0))


def _agudos(mezcla: np.ndarray, corte: float = 4000.0) -> float:
	espectro = np.abs(np.fft.rfft(mezcla.mean(axis=1))) ** 2
	frecuencias = np.fft.rfftfreq(len(mezcla), 1.0 / FRECUENCIA)
	return float(espectro[frecuencias >= corte].sum() / max(espectro.sum(), 1e-20))


# ── Cuentas comunes ──────────────────────────────────────────────────────────


def test_conversion_de_coordenadas():
	oyente = (10.0, 5.0, 1.6, 0.0)
	assert base.mundo_a_relativo(oyente, (10.0, 8.0, 1.6)) == pytest.approx((0.0, 3.0, 0.0))
	assert base.mundo_a_relativo(oyente, (13.0, 5.0, 1.6))[0] == pytest.approx(90.0)
	assert abs(base.mundo_a_relativo(oyente, (10.0, 2.0, 1.6))[0]) == pytest.approx(180.0)
	# Mirando al este, lo que está al norte queda a la izquierda.
	assert base.mundo_a_relativo((0.0, 0.0, 0.0, 90.0), (0.0, 4.0, 0.0))[0] == pytest.approx(-90.0)
	x, y, z = base.relativo_a_mundo((0.0, 0.0, 1.0, 90.0), 90.0, 2.0)
	assert (x, y, z) == pytest.approx((0.0, -2.0, 1.0), abs=1e-9)


def test_ley_de_distancia_sin_pistas_falsas():
	assert base.ganancia_distancia(0.2) == 1.0
	assert base.ganancia_distancia(1.0) == 1.0
	assert base.ganancia_distancia(2.0) == pytest.approx(0.5)
	assert base.ganancia_distancia(4.0) == pytest.approx(0.25)
	valores = [base.ganancia_distancia(d) for d in np.linspace(0.1, 80.0, 200)]
	assert all(a >= b for a, b in zip(valores, valores[1:], strict=False))
	assert valores[-1] > 0.0  # lejos se oye flojo, pero no se corta de golpe
	assert base.ganancia_distancia(10.0, caida=0.0) == 1.0


def test_filtro_y_detras():
	assert base.factor_detras(0.0) == 0.0
	assert base.factor_detras(90.0) == pytest.approx(20.0 / 110.0)
	assert base.factor_detras(180.0) == pytest.approx(1.0)
	assert base.factor_detras(-180.0) == pytest.approx(1.0)
	assert base.ganancias_filtro(0.0) == (1.0, 1.0)
	general, agudos = base.ganancias_filtro(1.0)
	assert general == pytest.approx(0.75)
	assert agudos == pytest.approx(0.02)
	assert base.ganancias_filtro(0.0, detras=1.0)[1] == pytest.approx(0.15)
	assert base.ganancias_filtro(0.0, detras=1.0, refuerzo=0.0)[1] == 1.0


def test_preparar_datos_admite_enteros_estereo_y_otra_frecuencia():
	enteros = (np.ones(100) * 16384).astype(np.int16)
	assert base.preparar_datos(enteros).max() == pytest.approx(0.5, abs=0.01)
	assert base.preparar_datos(np.zeros((50, 1), np.float32)).shape == (50,)
	assert base.preparar_datos(np.zeros((50, 4), np.float32)).shape == (50, 2)
	remuestreado = base.preparar_datos(np.zeros(22050, np.float32), 22050)
	assert abs(len(remuestreado) - 44100) <= 2
	assert base.preparar_datos(np.array([5.0, -5.0], np.float32)).tolist() == [1.0, -1.0]


# ── Protección auditiva ──────────────────────────────────────────────────────


def test_proteccion_limites_y_subidas():
	p = Proteccion.de_dict({"techo_fuente": 99, "techo_mezcla": 5, "subida_maestro": "x", "silencio_sin_tic": 0})
	assert p.techo_fuente == 1.5  # ni la configuración puede quitar el techo
	assert p.techo_mezcla == 1.0
	assert p.subida_maestro == Proteccion().subida_maestro
	assert p.silencio_sin_tic == 0.2
	p = Proteccion()
	assert p.limitar_fuente(7.0) == p.techo_fuente
	assert p.limitar_fuente(float("nan")) == 0.0
	assert p.limitar_maestro(1.0) == p.techo_mezcla
	assert p.subir(0.0, 0.8, 0.1) == pytest.approx(0.08)  # sube despacio
	assert p.subir(0.8, 0.2, 0.1) == 0.2  # baja al momento
	assert Proteccion.de_dict(p.a_dict()) == p


def test_limitador_de_mezcla_no_pasa_del_techo():
	p = Proteccion()
	mezcla = np.linspace(-6.0, 6.0, 2001, dtype=np.float32).reshape(-1, 1).repeat(2, axis=1)
	original = mezcla.copy()
	limitada = p.limitar_mezcla(mezcla)
	assert np.abs(limitada).max() <= p.techo_mezcla + 1e-6
	bajo = np.abs(original) < 0.6 * p.techo_mezcla
	assert np.array_equal(limitada[bajo], original[bajo])  # lo normal no se toca
	assert np.all(np.diff(limitada[:, 0]) >= 0)  # sin saltos: comprime, no recorta


def test_vigilante_calla_y_vuelve():
	hechos: list[str] = []
	v = Vigilante(0.5, lambda: hechos.append("callar"), lambda: hechos.append("volver"))
	v.latido(100.0)
	assert v.comprobar(100.3) is False
	assert v.comprobar(100.6) is True
	assert v.comprobar(101.0) is True
	assert hechos == ["callar"]  # una sola vez
	v.latido(101.1)
	assert hechos == ["callar", "volver"]
	assert v.comprobar(101.2) is False


def test_vigilante_con_hilo_de_verdad():
	callado: list[float] = []
	v = Vigilante(0.2, lambda: callado.append(time.monotonic()))
	v.iniciar()
	try:
		limite = time.monotonic() + 3.0
		while not callado and time.monotonic() < limite:
			time.sleep(0.05)
	finally:
		v.parar()
	assert callado


# ── Motor nulo ───────────────────────────────────────────────────────────────


def test_motor_nulo_apunta_las_llamadas():
	motor = MotorNulo()
	motor.iniciar("Auriculares", {"volumenes": {"pasos": 0.3}})
	motor.cargar("clic", datos=_ruido(0.2))
	motor.oyente(1.0, 2.0, 1.6, 450.0)
	canal = motor.reproducir("clic", pos=(3.0, 2.0, 1.0), bus="pasos", volumen=0.5, filtro=0.4)
	bucle = motor.reproducir("clic", bucle=True, bus="ambiente")
	motor.actualizar(canal, volumen=0.2)
	motor.acustica("bano")
	motor.atenuar_por_voz(1.5)
	assert canal > 0 and bucle > 0 and canal != bucle
	assert motor._oyente == (1.0, 2.0, 1.6, 90.0)
	assert [n for n, _a in motor.llamadas] == [
		"iniciar",
		"cargar",
		"oyente",
		"reproducir",
		"reproducir",
		"actualizar",
		"acustica",
		"atenuar_por_voz",
	]
	primera = motor.de("reproducir")[0]
	assert primera["nombre"] == "clic" and primera["pos"] == (3.0, 2.0, 1.0) and primera["bus"] == "pasos" and primera["canal"] == canal
	assert motor.volumenes["pasos"] == 0.3
	assert motor.suena(canal)
	for _i in range(10):
		motor.tic(0.05)
	assert not motor.suena(canal)  # 0,2 s de sonido ya han pasado
	assert motor.suena(bucle)
	motor.parar(bucle, fundido=0.1)
	for _i in range(4):
		motor.tic(0.05)
	assert not motor.suena(bucle)
	motor.cerrar()
	assert motor.reproducir("clic") == 0


def test_motor_nulo_acepta_sonidos_que_no_existen_y_buses_raros():
	motor = MotorNulo()
	motor.iniciar(None, {})
	assert motor.reproducir("lo/que/sea") > 0
	canal = motor.reproducir("lo/que/sea", bus="inventado")
	assert motor.canales_activos()[-1].bus == "efectos"
	assert motor.canales_activos()[-1].id == canal
	motor.acustica("catedral")
	assert motor.preset == "seca"
	motor.parar_todo()
	assert motor.canales_activos() == []


def test_atenuacion_por_voz_y_pausa_en_la_base():
	motor = MotorNulo()
	motor.iniciar(None, RAPIDO)
	ambiente = motor.reproducir("a", bucle=True, bus="ambiente")
	efecto = motor.reproducir("a", bucle=True, bus="efectos")
	for _i in range(20):
		motor.tic(0.05)
	canales = {c.id: c for c in motor.canales_activos()}
	assert canales[ambiente].ganancia == pytest.approx(0.6)
	assert canales[efecto].ganancia == pytest.approx(1.0)
	assert motor._maestro == pytest.approx(1.0)
	motor.atenuar_por_voz(1.0)
	for _i in range(10):
		motor.tic(0.05)
	assert canales[ambiente].ganancia == pytest.approx(0.6 * base.ATENUACION_VOZ, rel=0.05)
	assert canales[efecto].ganancia == pytest.approx(1.0)  # los efectos no bajan
	for _i in range(80):
		motor.tic(0.05)
	assert canales[ambiente].ganancia == pytest.approx(0.6, rel=0.05)
	motor.pausar(True)
	interfaz = motor.reproducir("a", bus="interfaz")
	nuevo = motor.reproducir("a", bus="efectos")
	canales = {c.id: c for c in motor.canales_activos()}
	assert canales[efecto].pausado and canales[nuevo].pausado and not canales[interfaz].pausado
	motor.pausar(False)
	assert not canales[efecto].pausado


# ── Motor clásico ────────────────────────────────────────────────────────────


@pytest.fixture
def clasico():
	motor = MotorClasico()
	motor.iniciar(None, {"memoria": True, **RAPIDO})
	motor.cargar("ruido", datos=_ruido())
	motor.oyente(0.0, 0.0, 0.0, 0.0)
	for _i in range(10):
		motor.tic(0.05)
	motor.renderizar(1024)
	yield motor
	motor.cerrar()


def _medir(motor: MotorClasico, **argumentos) -> np.ndarray:
	canal = motor.reproducir("ruido", **argumentos)
	assert canal > 0
	motor.tic(0.01)
	mezcla = motor.renderizar(16384)
	motor.parar(canal)
	return mezcla


def test_clasico_derecha_izquierda_y_retardo(clasico):
	mezcla = _medir(clasico, pos=(3.0, 0.0, 0.0))
	izquierda, derecha = _nivel(mezcla)
	assert derecha > izquierda * 2
	assert izquierda > 0.0  # el oído lejano nunca queda mudo
	tramo = mezcla[2000:10000]
	correlacion = np.correlate(tramo[:, 0], tramo[:, 1], mode="full")
	assert int(np.argmax(correlacion)) - (len(tramo) - 1) == pytest.approx(28, abs=2)
	izquierda, derecha = _nivel(_medir(clasico, pos=(-3.0, 0.0, 0.0)))
	assert izquierda > derecha * 2


def test_clasico_distancia_filtro_y_detras(clasico):
	cerca = _nivel(_medir(clasico, pos=(0.0, 2.0, 0.0)))[0]
	lejos = _nivel(_medir(clasico, pos=(0.0, 8.0, 0.0)))[0]
	assert lejos / cerca == pytest.approx(0.25, rel=0.05)
	limpio = _medir(clasico, pos=(0.0, 2.0, 0.0))
	tapado = _medir(clasico, pos=(0.0, 2.0, 0.0), filtro=1.0)
	detras = _medir(clasico, pos=(0.0, -2.0, 0.0))
	assert _agudos(tapado) < _agudos(limpio) * 0.2
	assert _agudos(detras) < _agudos(limpio) * 0.6


def test_clasico_tono_bucle_y_fin(clasico):
	clasico.cargar("corto", datos=_ruido(0.2))
	canal = clasico.reproducir("corto", tono=2.0)
	clasico.renderizar(int(FRECUENCIA * 0.15))
	clasico.tic(0.01)
	assert not clasico.suena(canal)  # al doble de tono dura la mitad
	bucle = clasico.reproducir("corto", bucle=True, bus="ambiente")
	clasico.renderizar(FRECUENCIA)
	clasico.tic(0.01)
	assert clasico.suena(bucle)
	clasico.parar(bucle)
	assert _nivel(clasico.renderizar(4096))[0] == 0.0


def test_clasico_estereo_y_mono(clasico):
	ruido = _ruido()
	clasico.cargar("ambiente", datos=np.column_stack([ruido, np.zeros_like(ruido)]))
	canal = clasico.reproducir("ambiente", bus="ambiente", bucle=True)
	for _i in range(10):
		clasico.tic(0.05)
	clasico.renderizar(2048)
	izquierda, derecha = _nivel(clasico.renderizar(8192))
	assert izquierda > 0.01 and derecha == 0.0
	clasico.parar(canal)
	clasico.configurar({"mono": True})
	izquierda, derecha = _nivel(_medir(clasico, pos=(3.0, 0.0, 0.0)))
	assert izquierda == pytest.approx(derecha)


def test_clasico_calla_si_no_se_actualiza_y_limita_la_mezcla(clasico):
	for _i in range(40):
		clasico.reproducir("ruido", bucle=True, volumen=9.0, bus="interfaz")
	clasico.tic(0.05)
	clasico.renderizar(2048)
	mezcla = clasico.renderizar(8192)
	assert np.abs(mezcla).max() <= clasico.proteccion.techo_mezcla + 1e-6
	assert clasico.vigilante.comprobar(time.monotonic() + 10.0) is True
	clasico.renderizar(2048)  # rampa hacia el silencio
	assert np.abs(clasico.renderizar(2048)).max() == 0.0
	clasico.tic(0.01)
	assert np.abs(clasico.renderizar(2048)).max() < 0.5 * np.abs(mezcla).max()  # vuelve poco a poco


def test_clasico_segunda_salida_recibe_la_misma_mezcla(clasico):
	"""Sin abrir dispositivos: se simulan las dos peticiones de la tarjeta de sonido."""
	clasico._flujo_segundo = object()
	clasico.reproducir("ruido", bucle=True, bus="interfaz")
	clasico.tic(0.05)
	principal = np.zeros((512, 2), np.float32)
	clasico._al_pedir(principal, 512, None, None)
	segunda = np.zeros((512, 2), np.float32)
	clasico._al_pedir_segunda(segunda, 512, None, None)
	assert np.abs(principal).max() > 0.0
	assert np.array_equal(principal, segunda)
	sobra = np.ones((256, 2), np.float32)
	clasico._al_pedir_segunda(sobra, 256, None, None)
	assert np.abs(sobra).max() == 0.0  # sin datos nuevos, silencio
	clasico._flujo_segundo = None


# ── Motor estéreo (pygame con el controlador «dummy») ────────────────────────


@pytest.fixture
def estereo():
	if os.environ.get("SDL_AUDIODRIVER") != "dummy":
		pytest.skip("solo con el sonido «dummy» de SDL: no debe sonar nada de verdad")
	motor = MotorEstereo()
	motor.iniciar(None, {"memoria": True, **RAPIDO})
	motor.cargar("ruido", datos=_ruido(0.3))
	motor.oyente(0.0, 0.0, 0.0, 0.0)
	for _i in range(10):
		motor.tic(0.05)
	yield motor
	motor.cerrar()


def test_estereo_panorama_y_distancia(estereo):
	derecha = estereo.reproducir("ruido", pos=(3.0, 0.0, 0.0), bucle=True)
	canal = estereo.canales_activos()[0]
	for _i in range(10):
		estereo.tic(0.05)  # un bucle entra desde el silencio
	izq, der, _apagar = estereo._lados(canal)
	assert der > izq * 2 and izq > 0.0
	estereo.actualizar(derecha, pos=(0.0, 3.0, 0.0))
	delante = estereo._lados(canal)
	assert delante[0] == pytest.approx(delante[1])
	estereo.actualizar(derecha, pos=(0.0, 6.0, 0.0))
	assert estereo._lados(canal)[0] == pytest.approx(delante[0] / 2.0)
	estereo.actualizar(derecha, pos=(0.0, -3.0, 0.0))
	detras = estereo._lados(canal)
	assert detras[0] < delante[0] and detras[2] > 0.5  # más flojo y apagado
	estereo.tic(0.05)
	assert estereo.suena(derecha)
	volumen = canal.interno.canal.get_volume()
	assert 0.0 < volumen <= 1.0
	estereo.parar(derecha)
	assert not estereo.suena(derecha)


def test_estereo_tono_pausa_y_variantes(estereo):
	assert estereo._tono_redondeado(1.0) == 0
	assert estereo._tono_redondeado(2.0) == 24
	normal = estereo._sonido("ruido", False, False, 0)
	agudo = estereo._sonido("ruido", False, False, 24)
	assert agudo.get_length() == pytest.approx(normal.get_length() / 2.0, rel=0.05)
	assert estereo._sonido("ruido", False, False, 24) is agudo
	canal = estereo.reproducir("ruido", bucle=True)
	estereo.pausar(True)
	assert estereo.suena(canal)
	estereo.pausar(False)
	estereo.parar_todo()
	assert estereo.canales_activos() == []
	assert estereo.estado()["formato"][0] == FRECUENCIA


# ── BASS (viene incluido; aquí, solo qué pasa si faltara basskit) ──────────────────────────────────────────────────────────


def test_bass_sin_basskit_se_declara_no_disponible():
	try:
		import basskit  # noqa: F401
	except ImportError:
		hay, motivo = MotorBass.disponible()
		assert hay is False
		assert "basskit" in motivo
		with pytest.raises(MotorNoDisponible):
			MotorBass().iniciar(None, {})
	else:
		pytest.skip("basskit está instalado: el motor BASS se prueba de verdad en test_audio_bass.py")


# ── Fábrica ──────────────────────────────────────────────────────────────────


def test_motores_disponibles_lista_todos():
	lista = fabrica.motores_disponibles()
	assert [m["id"] for m in lista] == ["openal", "clasico", "estereo", "bass", "nulo"]
	por_id = {m["id"]: m for m in lista}
	assert por_id["nulo"]["disponible"] is True
	assert all(m["nombre"] for m in lista)
	assert all(m["disponible"] or m["motivo"] for m in lista)


def test_cadena_de_reserva():
	assert fabrica.cadena_de("openal") == ["openal", "clasico", "estereo", "nulo"]
	assert fabrica.cadena_de("clasico") == ["clasico", "estereo", "nulo"]
	assert fabrica.cadena_de("estereo") == ["estereo", "nulo"]
	assert fabrica.cadena_de("bass") == ["bass", "openal", "clasico", "estereo", "nulo"]
	assert fabrica.cadena_de("nulo") == ["nulo"]


def test_fabrica_crea_el_pedido():
	motor = fabrica.crear_motor({"motor": "nulo"})
	assert motor.nombre == "nulo" and motor.pedido == "nulo"
	motor.cerrar()
	motor = fabrica.crear_motor({"motor": "clasico", "memoria": True})
	assert motor.nombre == "clasico"
	motor.cerrar()


@pytest.mark.skipif(not fabrica.clase_motor("openal").disponible()[0], reason="OpenAL Soft no está disponible")
def test_fabrica_openal_en_memoria_con_banco():
	class BancoFalso:
		def datos(self, nombre: str):
			return _ruido(0.1), FRECUENCIA

	motor = fabrica.crear_motor({"motor": "openal", "memoria": True, "cabeza": "ku100"}, banco=BancoFalso())
	try:
		assert motor.nombre == "openal"
		assert motor.estado()["hrtf_activo"] is True
		assert motor.estado()["perfil_hrtf"] == "ku100"
		assert motor.reproducir("cualquier/nombre") > 0
	finally:
		motor.cerrar()


def test_fabrica_cae_al_siguiente_si_uno_falla(monkeypatch, caplog):
	from app.audio import motor_clasico, motor_estereo, motor_openal

	def rota(self, dispositivo, opciones):
		raise base.ErrorMotor("dispositivo roto (prueba)")

	monkeypatch.setattr(motor_openal.MotorOpenAL, "disponible", classmethod(lambda cls: (False, "sin DLL (prueba)")))
	monkeypatch.setattr(motor_clasico.MotorClasico, "iniciar", rota)

	def revienta(self, dispositivo, opciones):
		raise RuntimeError("fallo raro de una biblioteca (prueba)")

	monkeypatch.setattr(motor_estereo.MotorEstereo, "iniciar", revienta)
	with caplog.at_level("WARNING"):
		motor = fabrica.crear_motor({"motor": "openal"})
	assert motor.nombre == "nulo"
	assert motor.pedido == "openal"
	texto = caplog.text
	assert "sin DLL (prueba)" in texto and "dispositivo roto (prueba)" in texto and "fallo raro" in texto


def test_fabrica_motor_desconocido_y_sin_sonido(monkeypatch):
	monkeypatch.setenv("APP_SIN_SONIDO", "1")
	motor = fabrica.crear_motor({"motor": "openal"})
	assert motor.nombre == "nulo" and motor.pedido == "openal"
	motor = fabrica.crear_motor({"motor": "inventado"})
	assert motor.pedido == "openal"
	motor = fabrica.crear_motor(None)
	assert motor.nombre == "nulo"


def test_bass_pedido_sin_basskit_cae_a_la_cadena(monkeypatch):
	monkeypatch.setattr(MotorBass, "disponible", classmethod(lambda cls: (False, "falta basskit (prueba)")))
	motor = fabrica.crear_motor({"motor": "bass", "memoria": True})
	try:
		assert motor.nombre in ("openal", "clasico")
		assert motor.pedido == "bass"
	finally:
		motor.cerrar()
