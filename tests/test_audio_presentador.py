"""Presentador con dobles: eventos del juego → motor de sonido, voz y vibración; fuentes continuas."""

from __future__ import annotations

from dataclasses import dataclass, field

import pytest

from app.audio.haptica import Haptica
from app.audio.motor_nulo import MotorNulo
from app.audio.presentador import Presentador, tipo_evento
from app.audio.voz import VozFalsa


# Dobles con los mismos nombres de clase que tendrá app/motor/eventos.py: el presentador los reconoce por el nombre.
@dataclass
class EvSonido:
	nombre: str
	pos: tuple | None = None
	volumen: float = 1.0
	tono: float = 1.0
	bus: str = "efectos"
	filtro: float = 0.0
	relativo: tuple | None = None


@dataclass
class EvVoz:
	texto: str
	interrumpir: bool = False
	canal: str = "juego"


@dataclass
class EvVibrar:
	grave: float
	agudo: float
	ms: int


@dataclass
class EvAcustica:
	preset: str


@dataclass
class EvRegistro:
	tipo: str
	datos: dict = field(default_factory=dict)


@dataclass
class EvFin:
	resultado: dict = field(default_factory=dict)


@dataclass
class FuenteActiva:
	id: str
	sonido: str
	pos: tuple
	volumen: float = 1.0
	tono: float = 1.0
	filtro: float = 0.0
	bucle: bool = True


class SesionFalsa:
	def __init__(self) -> None:
		self.donde = (1.0, 2.0, 1.6, 90.0)
		self.lista: list[FuenteActiva] = []

	def oyente(self):
		return self.donde

	def fuentes(self):
		return list(self.lista)


class CabezaFalsa:
	def __init__(self, grados: float) -> None:
		self.grados = grados

	def giro(self) -> float:
		return self.grados


@pytest.fixture
def partes():
	motor = MotorNulo()
	motor.iniciar(None, {})
	voz = VozFalsa()
	haptica = Haptica()
	return motor, voz, haptica, Presentador(motor, voz, haptica)


def test_tipo_de_evento_por_nombre_de_clase_o_por_atributo():
	assert tipo_evento(EvSonido("a")) == "sonido"
	assert tipo_evento(EvVoz("hola")) == "voz"
	assert tipo_evento(EvVibrar(1, 1, 10)) == "vibrar"
	assert tipo_evento(EvAcustica("bano")) == "acustica"
	assert tipo_evento(EvFin()) == ""
	# EvRegistro tiene un campo «tipo» propio (choque, premio...): no se confunde con un evento de sonido.
	assert tipo_evento(EvRegistro("choque")) == ""
	assert tipo_evento(EvRegistro("voz")) == ""

	class Otro:
		tipo = "voz"
		texto = "por atributo"

	assert tipo_evento(Otro()) == "voz"


def test_evento_de_sonido_llega_al_motor_con_todo(partes):
	motor, _voz, _haptica, presentador = partes
	presentador.aplicar(
		[
			EvSonido("golpe/madera", pos=(3.0, 4.0, 1.0), volumen=0.7, tono=1.2, bus="efectos", filtro=0.3),
			EvSonido("sonda/pared", relativo=(-45.0, 2.5), bus="ayudas"),
			EvSonido("interfaz/mover", bus="interfaz"),
		],
		None,
		0.016,
	)
	golpe, sonda, interfaz = motor.de("reproducir")
	assert golpe["nombre"] == "golpe/madera" and golpe["pos"] == (3.0, 4.0, 1.0)
	assert golpe["volumen"] == 0.7 and golpe["tono"] == 1.2 and golpe["filtro"] == 0.3 and golpe["eco"] is True
	assert golpe["bucle"] is False and golpe["canal"] > 0
	assert sonda["relativo"] == (-45.0, 2.5) and sonda["pos"] is None and sonda["bus"] == "ayudas"
	assert interfaz["pos"] is None and interfaz["relativo"] is None
	assert interfaz["eco"] is False  # un sonido de menú no lleva el eco del lugar


def test_bus_desconocido_se_corrige(partes):
	motor, _voz, _haptica, presentador = partes
	presentador.aplicar([EvSonido("a", bus="inventado")], None, 0.016)
	assert motor.de("reproducir")[0]["bus"] == "efectos"


def test_la_voz_habla_y_atenua_el_ambiente(partes):
	motor, voz, _haptica, presentador = partes
	presentador.aplicar([EvVoz("Estás en la cocina.", interrumpir=True, canal="ayuda"), EvVoz("")], None, 0.016)
	assert voz.registro == [("Estás en la cocina.", "ayuda", True)]
	atenuaciones = motor.de("atenuar_por_voz")
	assert len(atenuaciones) == 1 and atenuaciones[0]["segundos"] > 0.5
	# Un canal desactivado no se dice y no baja el ambiente.
	voz.activar_canal("aviso", False)
	presentador.aplicar([EvVoz("No se oye", canal="aviso")], None, 0.016)
	assert len(motor.de("atenuar_por_voz")) == 1


def test_vibracion_y_acustica(partes):
	motor, _voz, haptica, presentador = partes
	presentador.aplicar([EvVibrar(0.8, 0.2, 120), EvAcustica("escalera"), EvRegistro("choque"), EvFin()], None, 0.016)
	assert haptica.registro == [(0.8, 0.2, 120)]
	assert motor.de("acustica") == [{"preset": "escalera"}]
	assert motor.preset == "escalera"
	assert motor.de("reproducir") == []  # EvRegistro y EvFin no suenan


def test_vibracion_por_patron(partes):
	_motor, _voz, haptica, presentador = partes

	class VibrarPatron:
		tipo = "vibrar"
		patron = "choque"

	presentador.aplicar([VibrarPatron()], None, 0.016)
	assert len(haptica.registro) == 1


def test_oyente_y_giro_de_cabeza(partes):
	motor, voz, haptica, _presentador = partes
	sesion = SesionFalsa()
	Presentador(motor, voz, haptica).aplicar([], sesion, 0.016)
	assert motor.de("oyente")[-1] == {"x": 1.0, "y": 2.0, "z": 1.6, "rumbo": 90.0}
	sesion.donde = (1.0, 2.0, 1.6, 350.0)
	Presentador(motor, voz, haptica, cabeza=CabezaFalsa(30.0)).aplicar([], sesion, 0.016)
	assert motor.de("oyente")[-1]["rumbo"] == pytest.approx(20.0)


def test_fuentes_continuas_se_crean_se_actualizan_y_se_apagan(partes):
	motor, _voz, _haptica, presentador = partes
	sesion = SesionFalsa()
	sesion.lista = [FuenteActiva("f1", "fuente/reloj", (5.0, 5.0, 1.5), volumen=0.6, filtro=0.2)]
	presentador.aplicar([], sesion, 0.05)
	creadas = motor.de("reproducir")
	assert len(creadas) == 1
	assert creadas[0]["nombre"] == "fuente/reloj" and creadas[0]["bucle"] is True and creadas[0]["bus"] == "ambiente"
	assert creadas[0]["pos"] == (5.0, 5.0, 1.5) and creadas[0]["filtro"] == 0.2
	canal = presentador.fuentes_sonando()["f1"]
	assert canal == creadas[0]["canal"]

	# Sigue: no se crea otra vez; se actualiza con lo que diga la sesión.
	sesion.lista = [FuenteActiva("f1", "fuente/reloj", (5.0, 5.0, 1.5), volumen=0.3, filtro=0.9, tono=1.1)]
	presentador.aplicar([], sesion, 0.05)
	assert len(motor.de("reproducir")) == 1
	ultima = motor.de("actualizar")[-1]
	assert ultima == {"canal": canal, "pos": (5.0, 5.0, 1.5), "volumen": 0.3, "tono": 1.1, "filtro": 0.9}

	# Aparece otra y la primera cambia de sonido: se sustituye.
	sesion.lista = [
		FuenteActiva("f1", "semaforo/verde", (5.0, 5.0, 1.5)),
		FuenteActiva("f2", "fuente/grifo", (0.0, 1.0, 1.0)),
	]
	presentador.aplicar([], sesion, 0.05)
	assert [r["nombre"] for r in motor.de("reproducir")] == ["fuente/reloj", "semaforo/verde", "fuente/grifo"]
	assert presentador.fuentes_sonando()["f1"] != canal
	assert any(p["canal"] == canal for p in motor.de("parar"))

	# Dejan de oírse: se apagan con fundido y desaparecen.
	sesion.lista = []
	presentador.aplicar([], sesion, 0.05)
	assert presentador.fuentes_sonando() == {}
	paradas = motor.de("parar")
	assert all(p["fundido"] > 0 for p in paradas)
	for _i in range(20):
		presentador.aplicar([], sesion, 0.05)
	assert motor.canales_activos() == []


def test_fuente_sin_bucle_suena_una_vez(partes):
	motor, _voz, _haptica, presentador = partes
	sesion = SesionFalsa()
	sesion.lista = [FuenteActiva("campana", "fuente/campanas", (9.0, 9.0, 8.0), bucle=False)]
	for _i in range(30):
		presentador.aplicar([], sesion, 0.05)
	assert len(motor.de("reproducir")) == 1


def test_un_bucle_al_que_le_roban_la_fuente_se_recupera(partes):
	motor, _voz, _haptica, presentador = partes
	sesion = SesionFalsa()
	sesion.lista = [FuenteActiva("f1", "fuente/reloj", (1.0, 1.0, 1.0))]
	presentador.aplicar([], sesion, 0.05)
	motor.parar(presentador.fuentes_sonando()["f1"])  # como si otra más importante se la hubiera quitado
	presentador.aplicar([], sesion, 0.05)
	assert len(motor.de("reproducir")) == 2
	assert motor.suena(presentador.fuentes_sonando()["f1"])


def test_un_evento_roto_no_impide_los_demas(partes, caplog):
	motor, voz, _haptica, presentador = partes

	class EvSonido:  # noqa: F811 - a propósito: un evento de sonido sin nombre
		pass

	EvSonidoRoto = EvSonido

	with caplog.at_level("ERROR"):
		presentador.aplicar([EvSonidoRoto(), EvVoz("sigue")], None, 0.016)
	assert voz.registro == [("sigue", "juego", False)]
	assert "No se pudo presentar" in caplog.text
	assert motor.de("reproducir") == []


def test_sin_voz_ni_haptica_ni_sesion(partes):
	motor, _voz, _haptica, _presentador = partes
	solo = Presentador(motor)
	solo.aplicar([EvVoz("nadie lo dice"), EvVibrar(1, 1, 50), EvSonido("interfaz/elegir", bus="interfaz")])
	assert len(motor.de("reproducir")) == 1
	assert solo.decir("nada") == 0.0


def test_atajos_del_reproductor_pausa_y_cierre(partes):
	motor, voz, haptica, presentador = partes
	canal = presentador.sonido("interfaz/mover")
	assert canal > 0
	assert motor.de("reproducir")[-1]["bus"] == "interfaz" and motor.de("reproducir")[-1]["eco"] is False
	assert presentador.decir("Menú principal", interrumpir=True, canal="ayuda") > 0
	assert voz.registro[-1] == ("Menú principal", "ayuda", True)
	sesion = SesionFalsa()
	sesion.lista = [FuenteActiva("f1", "fuente/reloj", (1.0, 1.0, 1.0))]
	presentador.aplicar([], sesion, 0.05)
	haptica.patron("objetivo")
	presentador.pausar(True)
	assert motor.de("pausar")[-1] == {"si": True}
	assert haptica.pendiente == 0 or not haptica.pendiente
	presentador.cerrar()
	assert presentador.fuentes_sonando() == {}
