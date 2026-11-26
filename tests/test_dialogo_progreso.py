"""El diálogo de progreso de las tareas largas: qué se escribe, qué se dice y cuándo, y cancelar.

El tiempo se simula con un reloj inyectado (``panel.reloj``) y los «tic» del
temporizador se llaman a mano: así se comprueba la política de anuncios
(cambios de fase separados por unos segundos y un recordatorio cada 15 s)
sin esperar de verdad.
"""

from __future__ import annotations

import json
import threading
from pathlib import Path

import pytest

wx = pytest.importorskip("wx")

from app.core import tareas  # noqa: E402
from app.core.configuracion import Configuracion  # noqa: E402
from app.ui import dialogo_progreso as dp  # noqa: E402
from app.ui import dialogos_importar as ui  # noqa: E402
from tests.conftest import procesar_eventos  # noqa: E402
from tests.test_ui_estudio_importar import ContextoPrueba  # noqa: E402

DATOS = Path(__file__).parent / "datos"


@pytest.fixture
def gestor():
	instancia = tareas.GestorTareas(max_hilos=1, nombre="prueba-progreso", prioridad_baja=False, intervalo_progreso=0.0)
	yield instancia
	instancia.apagar(1.0)


class Reloj:
	"""Reloj de mentira: avanza solo cuando la prueba lo dice."""

	def __init__(self) -> None:
		self.ahora = 1000.0

	def __call__(self) -> float:
		return self.ahora

	def pasar(self, segundos: float) -> None:
		self.ahora += segundos


def _panel(marco, gestor) -> tuple[dp.PanelProgreso, Reloj]:
	panel = dp.PanelProgreso(marco, gestor, Configuracion())
	reloj = Reloj()
	panel.reloj = reloj
	panel._temporizador.Stop()  # los tic los da la prueba
	return panel, reloj


def test_fases_cifras_tiempo_y_anuncios_por_hitos(app_wx, marco, gestor, voz_simulada):
	pasos = [threading.Event() for _i in range(3)]
	resultados: list = []

	def trabajo(tarea):
		dp.informar(tarea, "Convirtiendo calles", 1, 30)
		pasos[0].wait(10)
		dp.informar(tarea, "Convirtiendo calles", 20, 30)
		pasos[1].wait(10)
		dp.informar(tarea, "Creando aceras", 1, 16)
		pasos[2].wait(10)
		return 7

	panel, reloj = _panel(marco, gestor)
	panel.lanzar(trabajo, resultados.append, resultados.append, "prueba", "Empezando la prueba.")
	panel._temporizador.Stop()
	assert voz_simulada.textos == ["Empezando la prueba."]
	assert procesar_eventos(lambda: panel.texto_estado == "Convirtiendo calles: 1 de 30.", 5)
	assert panel.barra.GetValue() == 3
	# Menos de 3 segundos desde el último anuncio: la fase nueva aún no se dice.
	reloj.pasar(1.0)
	panel.tic()
	assert voz_simulada.textos == ["Empezando la prueba."]
	assert "Tiempo transcurrido: 1 segundo." in panel.estado.GetValue()
	reloj.pasar(2.5)
	panel.tic()
	assert voz_simulada.ultimo == "Convirtiendo calles: 1 de 30."
	# La misma fase no se repite aunque cambien las cifras.
	pasos[0].set()
	assert procesar_eventos(lambda: panel.texto_estado == "Convirtiendo calles: 20 de 30.", 5)
	reloj.pasar(5.0)
	panel.tic()
	assert len(voz_simulada.textos) == 2
	# Quince segundos sin anunciar nada: recordatorio de que sigue, con el tiempo.
	reloj.pasar(10.5)
	panel.tic()
	assert voz_simulada.ultimo == "Sigue: Convirtiendo calles: 20 de 30. Tiempo: 19 segundos."
	assert panel.estado.GetValue() == "Convirtiendo calles: 20 de 30.\nTiempo transcurrido: 19 segundos."
	# Fase nueva: se dice, pero no antes de 3 segundos desde el recordatorio.
	pasos[1].set()
	assert procesar_eventos(lambda: panel.texto_estado == "Creando aceras: 1 de 16.", 5)
	reloj.pasar(1.0)
	panel.tic()
	assert len(voz_simulada.textos) == 3
	reloj.pasar(2.0)
	panel.tic()
	assert voz_simulada.ultimo == "Creando aceras: 1 de 16."
	assert len(voz_simulada.textos) == 4, voz_simulada.textos
	pasos[2].set()
	assert procesar_eventos(lambda: not panel.trabajando(), 5)
	procesar_eventos(segundos=0.05)
	assert resultados == [7]
	assert "Tiempo transcurrido" not in panel.estado.GetValue(), "al terminar ya no corre el tiempo"
	assert panel.duracion_ultima == pytest.approx(22.0)
	assert not panel._temporizador.IsRunning()


def test_sin_total_la_barra_es_indeterminada(app_wx, marco, gestor, voz_simulada):
	soltar = threading.Event()

	def trabajo(tarea):
		dp.informar(tarea, "Esperando al servidor")
		soltar.wait(10)

	panel, _reloj = _panel(marco, gestor)
	panel.lanzar(trabajo, lambda _r: None, lambda _e: None, "prueba", "")
	try:
		assert procesar_eventos(lambda: panel.texto_estado == "Esperando al servidor…", 5)
		assert panel._indeterminado
		panel.tic()  # mueve la barra sin fallar
	finally:
		soltar.set()
	assert procesar_eventos(lambda: not panel.trabajando(), 5)


def test_con_el_progreso_callado_solo_se_dice_lo_que_pide_la_persona(app_wx, marco, gestor, voz_simulada):
	soltar = threading.Event()

	def trabajo(tarea):
		while not soltar.wait(0.02):
			dp.informar(tarea, "Convirtiendo calles", 3, 30)

	config = Configuracion()
	config.establecer("accesibilidad.anunciar_progreso", False)
	panel = dp.PanelProgreso(marco, gestor, config)
	reloj = Reloj()
	panel.reloj = reloj
	panel.lanzar(trabajo, lambda _r: None, lambda _e: None, "prueba", "Empezando.")
	panel._temporizador.Stop()
	try:
		assert procesar_eventos(lambda: panel.texto_estado.startswith("Convirtiendo"), 5)
		for _vuelta in range(5):
			reloj.pasar(20.0)
			panel.tic()
		assert voz_simulada.textos == ["Empezando."], "sin recordatorios ni fases"
		assert "Tiempo transcurrido: 1 minuto y 40 segundos." in panel.estado.GetValue()
		panel.cancelar()
		assert voz_simulada.ultimo == "Cancelando...", "la respuesta a una orden se dice siempre"
	finally:
		soltar.set()
	assert procesar_eventos(lambda: not panel.trabajando(), 5)


def test_cancelar_detiene_una_tarea_que_informa(app_wx, gestor, dialogo_modal, voz_simulada):
	vueltas = [0]

	def trabajo(tarea):
		while True:
			vueltas[0] += 1
			dp.informar(tarea, "Comprobando espacios", vueltas[0] % 100, 100)
			tarea.esperar(0.01)

	dialogo_modal.responder(lambda dialogo: (dialogo.panel.cancelar(), wx.ID_CANCEL)[1])
	with pytest.raises(tareas.TareaCancelada):
		dp.ejecutar_tarea(None, "Comprobar", trabajo, gestor, Configuracion(), fase="Comprobando el entorno...")
	assert voz_simulada.contiene("Cancelando")
	assert gestor.estadisticas()["canceladas"] == 1


def test_ejecutar_tarea_devuelve_el_resultado_e_informar_sin_gestor(app_wx, gestor, dialogo_modal, voz_simulada):
	def trabajo(tarea):
		for numero in range(1, 4):
			dp.informar(tarea, "Exportando", numero, 3)
		return "hecho"

	assert dp.ejecutar_tarea(None, "Exportar", trabajo, gestor, Configuracion()) == "hecho"
	assert dp.ejecutar_tarea(None, "Exportar", trabajo) == "hecho", "sin gestor, en el mismo hilo"


def test_progreso_de_tarea_reparte_la_barra_y_pasa_las_fases():
	recibidos: list[tuple] = []

	class Tarea:
		def progresar(self, hecho, total=None, texto="", fase=""):
			recibidos.append((round(hecho, 3), total, texto, fase))

	avance = dp.progreso_de_tarea(Tarea(), 0.5, 1.0)
	avance(0.5, "A medias.")
	avance.por_fases(1.0, "Calles: 3 de 3.", "Calles", 3, 3, False)
	avance.por_fases(0.2, "Esperando.", "Descarga", None, None, True)
	assert recibidos == [(75.0, 100.0, "A medias.", ""), (100.0, 100.0, "Calles: 3 de 3.", "Calles"), (0.0, None, "Esperando.", "Descarga")]


# ── El diálogo de OpenStreetMap ──────────────────────────────────────────────


def test_osm_avisa_del_tamano_antes_de_una_zona_grande(app_wx, gestor, dialogo_modal, voz_simulada):
	contexto = ContextoPrueba(gestor)
	contexto.configuracion.establecer("importar.aviso_privacidad_visto", True)
	mapa = json.loads((DATOS / "cruce.osm.json").read_text(encoding="utf-8"))
	llamadas: list[str] = []

	def descargar(url: str, datos: bytes | None = None) -> bytes:
		llamadas.append(url)
		return json.dumps({"elements": mapa["elements"]}).encode("utf-8")

	dialogo = ui.DialogoOSM(None, contexto, descargar=descargar)
	try:
		dialogo.fijar(latitud="40", longitud="-3,7", radio="350")
		dialogo_modal.responder(lambda d: d.ids_opciones[1])
		dialogo.importar_en_linea()
		aviso = dialogo_modal.mostrados[-1]
		assert aviso.titulo == "Zona grande"
		texto = " ".join(aviso.textos)
		assert "700 por 700 metros" in texto and "espacios" in texto and "MB" in texto and "cancelar" in texto
		assert not dialogo.trabajando() and llamadas == [], "«Cambiar el radio» no descarga"
		dialogo_modal.responder(lambda d: d.ids_opciones[0])
		dialogo.importar_en_linea()
		assert procesar_eventos(lambda: not dialogo.trabajando(), 20)
		procesar_eventos(segundos=0.05)
		assert dialogo.ultimo_error == "" and llamadas
		assert voz_simulada.textos[0] == "Importando una zona de 700 por 700 metros. Descargando el mapa de OpenStreetMap..."
		assert voz_simulada.contiene("Importación terminada en")
	finally:
		dialogo.Destroy()


def test_osm_radio_pequeno_no_pregunta(app_wx, gestor, dialogo_modal, voz_simulada):
	contexto = ContextoPrueba(gestor)
	contexto.configuracion.establecer("importar.aviso_privacidad_visto", True)
	mapa = json.loads((DATOS / "cruce.osm.json").read_text(encoding="utf-8"))
	dialogo = ui.DialogoOSM(None, contexto, descargar=lambda url, datos=None: json.dumps({"elements": mapa["elements"]}).encode("utf-8"))
	try:
		dialogo.fijar(latitud="40", longitud="-3,7", radio="80")
		dialogo.importar_en_linea()
		assert procesar_eventos(lambda: not dialogo.trabajando(), 20)
		assert not [m for m in dialogo_modal.mostrados if m.titulo == "Zona grande"]
	finally:
		dialogo.Destroy()
