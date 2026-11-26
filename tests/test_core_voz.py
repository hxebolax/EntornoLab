"""Pruebas de la voz del Estudio (``app.core.voz``) con cada salida: automática, solo el lector, SAPI y ninguna.

Ninguna habla de verdad: las salidas de accessible_output2 se sustituyen por
dobles con ``usar_salidas``. El ``conftest`` sustituye ``app.core.voz.hablar``
en todas las pruebas; aquí se usa la función real, guardada al importar este
módulo (antes de que actúe la fixture), y se vuelve a poner en cada prueba.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator

import pytest

from app.core import voz
from app.core.configuracion import Configuracion
from app.ui.accesibilidad import voz as voz_accesible

HABLAR_REAL = voz.hablar


def decir(texto: str, interrumpir: bool = False) -> bool:
	"""Habla y espera a que el hilo de voz lo haya hecho: así la prueba ve el resultado real."""
	return voz.hablar(texto, interrumpir, esperar=2.0)


class Lector:
	"""Doble de un lector de pantalla o de SAPI: apunta lo que se le pide."""

	system_output = False

	def __init__(self, activo: bool = True) -> None:
		self.activo = activo
		self.dicho: list[tuple[str, bool]] = []
		self.braille_visto: list[str] = []
		self.ajustes: dict[str, object] = {}

	def is_active(self) -> bool:
		return self.activo

	def speak(self, texto: str, interrupt: bool = False) -> None:
		self.dicho.append((texto, interrupt))

	def braille(self, texto: str) -> None:
		self.braille_visto.append(texto)


class NVDA(Lector):
	"""Se llama como el lector de accessible_output2."""


class SAPI5(Lector):
	"""La voz de Windows: es una salida «del sistema»."""

	system_output = True

	def set_rate(self, valor: int) -> None:
		self.ajustes["velocidad"] = valor

	def set_volume(self, valor: int) -> None:
		self.ajustes["volumen"] = valor

	def list_voices(self) -> list[str]:
		return ["Microsoft Helena", "Microsoft Pablo"]

	def set_voice(self, nombre: str) -> None:
		self.ajustes["voz"] = nombre


class Auto:
	"""Como ``Auto`` de accessible_output2: lectores por prioridad y SAPI al final."""

	def __init__(self, *salidas: Lector) -> None:
		self.outputs = list(salidas)

	def get_first_available_output(self) -> Lector | None:
		return next((s for s in self.outputs if s.is_active()), None)


@pytest.fixture
def salidas(monkeypatch) -> Iterator[dict[str, Lector]]:
	"""La función real de hablar con dobles de NVDA (cerrado), del SAPI de ``Auto`` y del SAPI propio."""
	monkeypatch.setattr(voz, "hablar", HABLAR_REAL)
	dobles = {"nvda": NVDA(activo=False), "sapi_de_auto": SAPI5(), "sapi": SAPI5()}
	voz.usar_salidas(Auto(dobles["nvda"], dobles["sapi_de_auto"]), dobles["sapi"])
	voz.olvidar_historial()
	voz.configurar(salida="automatica", braille=True, voz_sapi="", velocidad=50, volumen=100)
	yield dobles
	assert voz.esperar_cola()
	voz.configurar(salida="automatica", braille=True, voz_sapi="", velocidad=50, volumen=100)
	voz.usar_salidas(None, None)
	voz.olvidar_historial()


def test_automatica(salidas) -> None:
	assert decir("Sin lector") is True
	assert salidas["sapi_de_auto"].dicho == [("Sin lector", False)]
	salidas["nvda"].activo = True
	assert decir("Con lector", interrumpir=True) is True
	assert salidas["nvda"].dicho == [("Con lector", True)]


def test_solo_el_lector_nunca_usa_sapi(salidas) -> None:
	voz.configurar(salida="lector")
	assert decir("Nadie") is False
	assert salidas["sapi_de_auto"].dicho == [] and salidas["sapi"].dicho == []
	salidas["nvda"].activo = True
	assert decir("NVDA") is True
	assert salidas["nvda"].dicho == [("NVDA", False)]
	assert voz.historial() == ["Nadie", "NVDA"]


def test_siempre_sapi_con_sus_ajustes(salidas) -> None:
	salidas["nvda"].activo = True
	voz.configurar(salida="sapi", voz_sapi="helena", velocidad=80, volumen=40)
	assert voz.esperar_cola()
	assert salidas["sapi"].ajustes == {"velocidad": 6, "volumen": 40, "voz": "Microsoft Helena"}
	assert decir("Por Windows") is True
	assert salidas["sapi"].dicho == [("Por Windows", False)]
	assert salidas["nvda"].dicho == []


def test_ninguna_silencia_los_anuncios_pero_llena_el_historial(salidas) -> None:
	voz.configurar(salida="ninguna")
	salidas["nvda"].activo = True
	assert decir("Sala abierta.") is False
	assert salidas["nvda"].dicho == [] and salidas["sapi"].dicho == [] and salidas["sapi_de_auto"].dicho == []
	assert salidas["nvda"].braille_visto == ["Sala abierta."], "el braille sigue si hay lector"
	assert voz.historial() == ["Sala abierta."] and voz.ultimo() == "Sala abierta."
	voz.configurar(braille=False)
	decir("Otro")
	assert salidas["nvda"].braille_visto == ["Sala abierta."]
	assert voz.historial() == ["Sala abierta.", "Otro"]


def test_una_salida_desconocida_es_la_de_serie(salidas) -> None:
	voz.configurar(salida="telepatía")
	assert voz.salida_actual() == "automatica"


def test_cambio_en_caliente_por_la_configuracion(salidas, tmp_path) -> None:
	config = Configuracion(tmp_path / "config.json")
	config.establecer("voz.salida", "ninguna")
	cancelar = voz.aplicar_configuracion(config)
	try:
		assert voz.salida_actual() == "ninguna"
		assert decir("Callado") is False
		config.establecer("voz.salida", "sapi")
		assert voz.salida_actual() == "sapi"
		assert decir("Ya hablo") is True and salidas["sapi"].dicho == [("Ya hablo", False)]
		# Lo que cambia otro proceso (el reproductor) llega al releer la configuración.
		otra = Configuracion(tmp_path / "config.json")
		otra.establecer("voz.salida", "lector")
		config.recargar()
		assert voz.salida_actual() == "lector"
	finally:
		cancelar()
	config.establecer("voz.salida", "ninguna")
	assert voz.salida_actual() == "lector", "sin suscripción ya no se sigue la configuración"


def test_la_voz_de_accesibilidad_respeta_ninguna_y_guarda_su_historial(salidas) -> None:
	"""``app/ui/accesibilidad/voz.py`` habla por ``app.core.voz``: con «ninguna» no suena, pero no se pierde."""
	voz.configurar(salida="ninguna")
	voz_accesible.hablar("Lista vacía", canal=voz_accesible.NAVEGACION, sincrono=True)
	assert voz.esperar_cola()
	assert voz_accesible.ultimo_anuncio() == "Lista vacía"
	assert voz.ultimo() == "Lista vacía"
	assert salidas["sapi_de_auto"].dicho == [] and salidas["sapi"].dicho == []


def test_el_anuncio_del_contexto_del_estudio_queda_escrito(salidas) -> None:
	"""``contexto.anunciar`` (supervisión, avisos) escribe en la barra de estado y pasa por la voz: con «ninguna», callado."""
	from app.ui.contexto import ContextoEstudio

	voz.configurar(salida="ninguna")

	class Ventana:
		def __init__(self) -> None:
			self.estado = ""

		def SetStatusText(self, texto: str) -> None:  # noqa: N802 - nombre de wx
			self.estado = texto

	contexto = ContextoEstudio.__new__(ContextoEstudio)
	contexto.ventana = Ventana()
	ContextoEstudio.anunciar(contexto, "Luna: choca con la mesa.")
	assert voz.esperar_cola()
	assert contexto.ventana.estado == "Luna: choca con la mesa."
	assert voz.ultimo() == "Luna: choca con la mesa."
	assert salidas["sapi_de_auto"].dicho == [] and salidas["nvda"].dicho == []


# ── Hilo de voz: ninguna llamada a COM desde el hilo de la interfaz ──────────


class LectorQueExigeOtroHilo(NVDA):
	"""Doble que, como Windows, falla si se le llama desde el hilo de la interfaz durante una activación de ventana.

	Windows lanza RPC_E_CANTCALLOUT_ININPUTSYNCCALL (0x8001010d) si se hace
	una llamada COM saliente mientras atiende una llamada síncrona de entrada
	(activar o enfocar una ventana al abrir un diálogo).
	"""

	en_activacion = False

	def __init__(self) -> None:
		super().__init__(activo=True)
		self.hilos: list[str] = []

	def speak(self, texto: str, interrupt: bool = False) -> None:
		if self.en_activacion and threading.current_thread() is threading.main_thread():
			raise OSError(-2147417843, "RPC_E_CANTCALLOUT_ININPUTSYNCCALL")
		self.hilos.append(threading.current_thread().name)
		super().speak(texto, interrupt)


def test_hablar_durante_una_activacion_no_llama_a_la_voz_desde_la_interfaz(monkeypatch) -> None:
	monkeypatch.setattr(voz, "hablar", HABLAR_REAL)
	lector = LectorQueExigeOtroHilo()
	voz.usar_salidas(Auto(lector), None)
	voz.configurar(salida="automatica")
	try:
		LectorQueExigeOtroHilo.en_activacion = True  # como dentro de EVT_ACTIVATE al abrir un diálogo
		assert voz.hablar("Diálogo abierto.", interrumpir=True) is True, "vuelve enseguida, sin llamar a COM"
		voz.hablar("Segundo anuncio.")
		voz.hablar("Tercero, interrumpe.", interrumpir=True)
		LectorQueExigeOtroHilo.en_activacion = False
		assert voz.esperar_cola()
		assert lector.dicho == [("Diálogo abierto.", True), ("Segundo anuncio.", False), ("Tercero, interrumpe.", True)], (
			"ningún anuncio se pierde y se dicen en orden, con su interrupción"
		)
		assert set(lector.hilos) == {voz.NOMBRE_HILO}
	finally:
		LectorQueExigeOtroHilo.en_activacion = False
		voz.usar_salidas(None, None)
		assert voz.esperar_cola()


def test_hablar_dentro_de_un_evento_de_activacion_de_wx(app_wx, monkeypatch) -> None:
	"""Con wx de verdad: el anuncio hecho en el manejador de EVT_ACTIVATE de un diálogo se dice fuera de él."""
	import wx

	from tests.conftest import procesar_eventos

	monkeypatch.setattr(voz, "hablar", HABLAR_REAL)
	lector = LectorQueExigeOtroHilo()
	voz.usar_salidas(Auto(lector), None)
	voz.configurar(salida="automatica")
	dialogo = wx.Dialog(None, title="Prueba")

	def al_activar(evento: wx.ActivateEvent) -> None:
		LectorQueExigeOtroHilo.en_activacion = True
		try:
			voz.hablar("Prueba, diálogo.", interrumpir=True)
		finally:
			LectorQueExigeOtroHilo.en_activacion = False
		evento.Skip()

	dialogo.Bind(wx.EVT_ACTIVATE, al_activar)
	try:
		dialogo.ProcessEvent(wx.ActivateEvent(wx.wxEVT_ACTIVATE, True, dialogo.GetId()))
		procesar_eventos(segundos=0.05)
		assert voz.esperar_cola()
		assert lector.dicho == [("Prueba, diálogo.", True)]
		assert lector.hilos == [voz.NOMBRE_HILO]
	finally:
		dialogo.Destroy()
		voz.usar_salidas(None, None)
		assert voz.esperar_cola()


def test_las_voces_sapi_se_listan_desde_el_hilo_de_voz(monkeypatch) -> None:
	pytest.importorskip("accessible_output2")
	from accessible_output2.outputs import sapi5

	hilos: list[str] = []

	class SAPIQueApunta(SAPI5):
		def __init__(self) -> None:
			super().__init__()
			hilos.append(threading.current_thread().name)

	monkeypatch.setattr(sapi5, "SAPI5", SAPIQueApunta)
	assert voz.voces_sapi() == ["Microsoft Helena", "Microsoft Pablo"]
	assert hilos == [voz.NOMBRE_HILO]
