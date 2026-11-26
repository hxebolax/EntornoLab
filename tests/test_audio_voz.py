"""Pruebas de la voz: canales, historial, repaso, braille, redetección del lector y síntesis a fichero.

Ninguna hace hablar al lector de pantalla real: se usa ``VozFalsa`` o se inyecta un lector de mentira.
"""

from __future__ import annotations

import wave

import pytest

from app.audio import voz as modulo
from app.audio.voz import Voz, VozFalsa, estimar_duracion, sintetizar_a_fichero


class LectorFalso:
	"""Un lector con la interfaz de accessible_output2: apunta lo que se le pide."""

	def __init__(self) -> None:
		self.dicho: list[tuple[str, bool]] = []
		self.braille_visto: list[str] = []
		self.silencios = 0

	def speak(self, texto: str, interrupt: bool = False) -> None:
		self.dicho.append((texto, interrupt))

	def braille(self, texto: str) -> None:
		self.braille_visto.append(texto)

	def silence(self) -> None:
		self.silencios += 1


class OtroLector(LectorFalso):
	"""Un segundo lector, para simular que se abre otro."""


class AutoFalso:
	"""Como ``Auto``: devuelve el lector activo, que puede cambiar."""

	def __init__(self, lector: object | None) -> None:
		self.lector = lector

	def get_first_available_output(self) -> object | None:
		return self.lector


def test_estimar_duracion() -> None:
	assert estimar_duracion("") == 0.0
	corta = estimar_duracion("Hola")
	larga = estimar_duracion("Hola " * 20)
	assert 0.7 < corta < larga <= 9.0
	assert estimar_duracion("x" * 5000) == 9.0
	assert estimar_duracion("Hola " * 20, velocidad=10) < larga < estimar_duracion("Hola " * 20, velocidad=-10)


def test_voz_falsa_registra_y_devuelve_duracion() -> None:
	v = VozFalsa()
	d = v.decir("Estás en la cocina.", interrumpir=True, canal="ayuda")
	assert d == pytest.approx(estimar_duracion("Estás en la cocina."))
	assert v.registro == [("Estás en la cocina.", "ayuda", True)]
	assert v.ultimo == "Estás en la cocina."
	assert v.decir("   ") == 0.0
	assert len(v.historial) == 1


def test_canal_desactivado_no_se_dice_pero_queda_en_el_historial() -> None:
	v = VozFalsa({"canales": {"profesional": False}})
	assert v.decir("Mensaje del profesional", canal="profesional") == 0.0
	assert v.registro == []
	assert list(v.historial) == ["Mensaje del profesional"]
	assert list(v.historial_canales) == ["profesional"]
	v.activar_canal("profesional", True)
	assert v.decir("Otro", canal="profesional") > 0
	assert v.registro[-1] == ("Otro", "profesional", False)


def test_voz_inactiva_devuelve_cero() -> None:
	v = VozFalsa({"activa": False})
	assert v.decir("Hola") == 0.0
	assert v.registro == []
	assert v.ultimo == "Hola"


def test_nunca_interrumpir() -> None:
	v = VozFalsa({"nunca_interrumpir": True})
	v.decir("Uno", interrumpir=True)
	assert v.registro == [("Uno", "juego", False)]


def test_repaso_del_historial() -> None:
	v = VozFalsa()
	ahora = [100.0]
	v._reloj = lambda: ahora[0]
	assert v.anterior() > 0
	assert v.registro[-1][0] == "No hay mensajes."
	for texto in ("uno", "dos", "tres"):
		v.decir(texto)
	v.anterior()
	assert v.registro[-1] == ("dos", "historial", True)
	# Mientras se repasa, un mensaje nuevo no mueve el cursor.
	v.decir("cuatro")
	v.anterior()
	assert v.registro[-1][0] == "uno"
	v.anterior()
	assert v.registro[-1][0] == "Primero. uno"
	v.siguiente()
	assert v.registro[-1][0] == "dos"
	# Lo dicho al repasar no entra en el historial.
	assert list(v.historial) == ["uno", "dos", "tres", "cuatro"]
	# Pasada la pausa, un mensaje nuevo lleva otra vez al final.
	ahora[0] += modulo.REPASO_PAUSA + 1
	v.decir("cinco")
	v.siguiente()
	assert v.registro[-1][0] == "Último. cinco"
	v.anterior()
	v.repetir()
	assert v.registro[-1][0] == "cinco"


def test_historial_con_limite() -> None:
	v = VozFalsa({"historial_max": 10})
	for i in range(25):
		v.decir(f"m{i}")
	assert len(v.historial) == 10
	assert v.ultimo == "m24"
	v.anterior()
	assert v.registro[-1][0] == "m23"


def test_gancho_al_hablar() -> None:
	v = VozFalsa({"canales": {"aviso": False}})
	oido: list[tuple[str, float]] = []
	v.al_hablar = lambda texto, duracion: oido.append((texto, duracion))
	v.decir("Hola")
	v.decir("Callado", canal="aviso")
	assert len(oido) == 1 and oido[0][0] == "Hola" and oido[0][1] > 0

	def roto(texto: str, duracion: float) -> None:
		raise RuntimeError("red caída")

	v.al_hablar = roto
	assert v.decir("Sigue hablando") > 0


def test_voz_real_con_lector_inyectado_habla_y_manda_braille() -> None:
	lector = LectorFalso()
	v = Voz(salida=AutoFalso(lector))
	assert v.nombre == "LectorFalso"
	assert v.decir("Puerta delante.", interrumpir=True) > 0
	assert lector.dicho == [("Puerta delante.", True)]
	assert lector.braille_visto == ["Puerta delante."]
	v.callar()
	assert lector.silencios == 1
	v.configurar({"braille": "nada"})
	v.decir("Sin braille")
	assert lector.braille_visto == ["Puerta delante."]
	v.cerrar()
	assert v.decir("Ya cerrada") == 0.0


def test_voz_real_sin_lector_no_dice_nada() -> None:
	v = Voz(salida=AutoFalso(None))
	assert v.nombre == "ninguna"
	assert v.decir("Hola") == 0.0
	assert v.ultimo == "Hola"
	v.callar()


def test_redeteccion_del_lector_en_tic() -> None:
	auto = AutoFalso(LectorFalso())
	v = Voz(salida=auto)
	ahora = [10.0]
	v._reloj = lambda: ahora[0]
	v.tic()
	nuevo = OtroLector()
	auto.lector = nuevo
	ahora[0] += 0.5
	v.tic()
	assert v.nombre == "LectorFalso"  # aún no toca mirar
	ahora[0] += modulo.CADA_CUANTO_LECTOR
	v.tic()
	assert v.nombre == "OtroLector"
	v.decir("Hola")
	assert nuevo.dicho == [("Hola", False)]


def test_un_lector_que_falla_no_rompe() -> None:
	class Roto(LectorFalso):
		def speak(self, texto: str, interrupt: bool = False) -> None:
			raise OSError("lector cerrado a medias")

		def braille(self, texto: str) -> None:
			raise OSError("sin línea")

		def silence(self) -> None:
			raise OSError("no calla")

	v = Voz(salida=Roto())
	assert v.decir("Hola") == 0.0
	v.callar()


def test_app_sin_voz(monkeypatch) -> None:
	monkeypatch.setenv("APP_SIN_VOZ", "1")
	v = Voz()
	assert v.nombre == "ninguna"
	assert v.decir("Hola") == 0.0
	assert v.ultimo == "Hola"


def test_opciones_rotas_se_sanean() -> None:
	v = VozFalsa({"salida": "telepatía", "sapi_velocidad": "rápida", "sapi_volumen": 500, "braille": 7, "desconocida": 1})
	assert v.opciones["salida"] == "automatica"
	assert v.opciones["sapi_velocidad"] == 0
	assert v.opciones["sapi_volumen"] == 100
	assert v.opciones["braille"] == "temporal"


# ── Salidas de voz: automática, solo el lector, SAPI y ninguna ───────────────


class NVDA(LectorFalso):
	"""Doble de un lector de pantalla de verdad (se llama como el de accessible_output2)."""

	system_output = False

	def __init__(self, activo: bool = True) -> None:
		super().__init__()
		self.activo = activo

	def is_active(self) -> bool:
		return self.activo


class SAPI5(LectorFalso):
	"""Doble de la voz de Windows de accessible_output2: no habla, apunta."""

	system_output = True

	def __init__(self) -> None:
		super().__init__()
		self.ajustes: dict[str, object] = {}

	def is_active(self) -> bool:
		return True

	def set_rate(self, valor: int) -> None:
		self.ajustes["velocidad"] = valor

	def set_volume(self, valor: int) -> None:
		self.ajustes["volumen"] = valor

	def list_voices(self) -> list[str]:
		return ["Microsoft Helena", "Microsoft Pablo"]

	def set_voice(self, nombre: str) -> None:
		self.ajustes["voz"] = nombre


class AutoConSalidas:
	"""Como ``Auto`` de accessible_output2: una lista de salidas por prioridad, con SAPI al final."""

	def __init__(self, *salidas: object) -> None:
		self.outputs = list(salidas)

	def get_first_available_output(self) -> object | None:
		return next((s for s in self.outputs if s.is_active()), None)


@pytest.fixture
def sin_accessible_output2(monkeypatch):
	"""Sustituye ``Auto`` y ``SAPI5`` de accessible_output2 por dobles: ninguna prueba habla de verdad."""
	pytest.importorskip("accessible_output2")
	from accessible_output2.outputs import auto, sapi5

	creados: dict[str, list[object]] = {"auto": [], "sapi": []}
	lectores = {"nvda": NVDA(activo=False), "sapi_de_auto": SAPI5()}

	def nuevo_auto() -> AutoConSalidas:
		doble = AutoConSalidas(lectores["nvda"], lectores["sapi_de_auto"])
		creados["auto"].append(doble)
		return doble

	def nueva_sapi() -> SAPI5:
		doble = SAPI5()
		creados["sapi"].append(doble)
		return doble

	monkeypatch.setattr(auto, "Auto", nuevo_auto)
	monkeypatch.setattr(sapi5, "SAPI5", nueva_sapi)
	monkeypatch.delenv("APP_SIN_VOZ", raising=False)
	return creados, lectores


def test_automatica_usa_el_lector_y_si_no_hay_la_voz_de_windows(sin_accessible_output2) -> None:
	creados, lectores = sin_accessible_output2
	v = Voz({"salida": "automatica"})
	assert v.salida == "automatica" and len(creados["auto"]) == 1
	assert v.decir("Sin lector") > 0
	assert lectores["sapi_de_auto"].dicho == [("Sin lector", False)], "sin lector, habla SAPI"
	lectores["nvda"].activo = True
	v.decir("Con lector")
	assert lectores["nvda"].dicho == [("Con lector", False)]
	assert lectores["nvda"].braille_visto == ["Con lector"]


def test_lector_sin_lector_no_habla_ni_cae_a_sapi(sin_accessible_output2) -> None:
	_creados, lectores = sin_accessible_output2
	v = Voz({"salida": "lector"})
	assert v.nombre == "ninguna"
	assert v.decir("Nadie lo oye") == 0.0
	assert lectores["sapi_de_auto"].dicho == [], "con «lector» nunca habla la voz de Windows"
	assert list(v.historial) == ["Nadie lo oye"], "el historial se sigue llenando"
	v.callar()
	assert lectores["sapi_de_auto"].silencios == 0
	lectores["nvda"].activo = True
	assert v.decir("Ya hay lector") > 0
	assert lectores["nvda"].dicho == [("Ya hay lector", False)]


def test_redeteccion_con_lector_no_acaba_en_sapi(sin_accessible_output2) -> None:
	_creados, lectores = sin_accessible_output2
	lectores["nvda"].activo = True
	v = Voz({"salida": "lector"})
	ahora = [10.0]
	v._reloj = lambda: ahora[0]
	assert v.nombre == "NVDA"
	lectores["nvda"].activo = False  # se cierra NVDA con el juego en marcha
	ahora[0] += modulo.CADA_CUANTO_LECTOR
	v.tic()
	assert v.nombre == "ninguna"
	v.decir("Tras cerrar el lector")
	assert lectores["sapi_de_auto"].dicho == []
	lectores["nvda"].activo = True
	ahora[0] += modulo.CADA_CUANTO_LECTOR
	v.tic()
	assert v.nombre == "NVDA"


def test_sapi_habla_siempre_por_la_voz_de_windows(sin_accessible_output2) -> None:
	creados, lectores = sin_accessible_output2
	lectores["nvda"].activo = True
	v = Voz({"salida": "sapi", "sapi_velocidad": 4, "sapi_volumen": 60, "sapi_voz": "pablo"})
	sapi = creados["sapi"][-1]
	assert sapi.ajustes == {"velocidad": 4, "volumen": 60, "voz": "Microsoft Pablo"}
	v.decir("Por Windows")
	assert sapi.dicho == [("Por Windows", False)]
	assert lectores["nvda"].dicho == [], "aunque haya lector"


def test_ninguna_no_habla_pero_guarda_y_manda_al_braille(sin_accessible_output2) -> None:
	_creados, lectores = sin_accessible_output2
	v = Voz({"salida": "ninguna"})
	oido: list[str] = []
	v.al_hablar = lambda texto, _duracion: oido.append(texto)
	assert v.nombre == "ninguna"
	assert v.decir("Sin lector") == 0.0
	lectores["nvda"].activo = True
	assert v.decir("Puerta delante.", interrumpir=True) == 0.0
	assert lectores["nvda"].dicho == [] and lectores["sapi_de_auto"].dicho == []
	assert lectores["nvda"].braille_visto == ["Puerta delante."], "el braille sigue si hay lector"
	assert list(v.historial) == ["Sin lector", "Puerta delante."]
	assert v.ultimo == "Puerta delante.", "es lo que el reproductor escribe abajo en la pantalla"
	assert oido == [], "lo que no se oye no se cuenta como dicho"
	v.callar()
	assert lectores["nvda"].silencios == 0, "con «ninguna» no se calla al lector del usuario"
	assert v.repetir() == 0.0
	assert lectores["nvda"].braille_visto == ["Puerta delante."] * 2, "repetir vuelve a llevarlo al braille"
	v.configurar({"braille": "nada"})
	v.decir("Sin braille")
	assert lectores["nvda"].braille_visto == ["Puerta delante."] * 2


def test_cambio_de_salida_en_caliente(sin_accessible_output2) -> None:
	creados, lectores = sin_accessible_output2
	v = Voz({"salida": "automatica"})
	v.configurar({"salida": "ninguna"})
	assert len(creados["auto"]) == 1, "entre salidas con lector no se vuelve a abrir nada"
	v.decir("Callado")
	assert lectores["sapi_de_auto"].dicho == []
	v.configurar({"salida": "sapi"})
	assert len(creados["sapi"]) == 1
	v.decir("Por SAPI")
	assert creados["sapi"][-1].dicho == [("Por SAPI", False)]
	v.configurar({"salida": "lector"})
	assert v.decir("Sin lector") == 0.0
	v.configurar({"salida": "automatica"})
	assert v.decir("Otra vez") > 0
	assert lectores["sapi_de_auto"].dicho == [("Otra vez", False)]
	assert list(v.historial) == ["Callado", "Por SAPI", "Sin lector", "Otra vez"]


def test_voz_falsa_con_ninguna_no_apunta() -> None:
	v = VozFalsa({"salida": "ninguna"})
	assert v.decir("Hola") == 0.0
	assert v.registro == [] and v.ultimo == "Hola"
	v.configurar({"salida": "automatica"})
	assert v.decir("Otra") > 0 and v.registro == [("Otra", "juego", False)]


def test_sintetizar_a_fichero(tmp_path) -> None:
	pytest.importorskip("win32com.client")
	ruta = tmp_path / "voz" / "frase.wav"
	if not sintetizar_a_fichero("Salida a la derecha.", ruta):
		pytest.skip("SAPI no está disponible en este equipo")
	with wave.open(str(ruta)) as w:
		assert w.getframerate() == 44100
		assert w.getnchannels() == 1
		assert w.getsampwidth() == 2
		assert w.getnframes() > 4410
	assert sintetizar_a_fichero("", tmp_path / "vacio.wav") is False
