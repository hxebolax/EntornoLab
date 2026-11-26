"""Pruebas del diálogo de actualizaciones (se crea sin mostrarse; nunca un modal real)."""

from __future__ import annotations

import re

import pytest

wx = pytest.importorskip("wx")

from app.core import red, tareas, voz  # noqa: E402
from app.core.configuracion import obtener_configuracion  # noqa: E402
from app.services import actualizador  # noqa: E402
from app.ui import dialogo_actualizacion as ui  # noqa: E402
from tests._actualizador_util import Claves, publicar_version  # noqa: E402
from tests.conftest import procesar_eventos  # noqa: E402
from tests.servidor_http_prueba import servidor  # noqa: E402, F401 - fixture

ARCHIVOS = {"EntornoLab.exe": b"EXE 1.1.0", "EntornoLabJugar.exe": b"JUGAR 1.1.0", "lib/m.bin": bytes(range(256)) * 4000}


def letras_de_acceso(ventana) -> list[str]:
	"""Letra de acceso (la que sigue a «&») de cada control con etiqueta, recorriendo los hijos."""
	letras: list[str] = []
	pendientes = list(ventana.GetChildren())
	while pendientes:
		control = pendientes.pop(0)
		pendientes.extend(control.GetChildren())
		if isinstance(control, (wx.StaticText, wx.Button, wx.CheckBox, wx.RadioButton)):
			coincidencia = re.search(r"&([^&\s])", control.GetLabel())
			if coincidencia:
				letras.append(coincidencia.group(1).lower())
	return letras


def comprobar_etiquetas(ventana) -> None:
	"""Cada campo, lista o desplegable tiene una etiqueta con letra de acceso creada justo antes."""
	hijos = list(ventana.GetChildren())
	for indice, control in enumerate(hijos):
		if isinstance(control, (wx.TextCtrl, wx.Choice, wx.ListCtrl)):
			anterior = hijos[indice - 1]
			assert isinstance(anterior, wx.StaticText), f"{type(control).__name__} sin etiqueta delante"
			assert "&" in anterior.GetLabel(), f"la etiqueta «{anterior.GetLabel()}» no tiene letra de acceso"
			assert anterior.GetLabel().rstrip().endswith(":")
		if isinstance(control, (wx.Button, wx.CheckBox)):
			assert "&" in control.GetLabel(), f"«{control.GetLabel()}» no tiene letra de acceso"


@pytest.fixture(scope="module")
def claves(tmp_path_factory) -> Claves:
	return Claves(tmp_path_factory.mktemp("claves"))


@pytest.fixture
def gestor():
	instancia = tareas.GestorTareas(max_hilos=1, nombre="prueba", prioridad_baja=False)
	yield instancia
	instancia.apagar(1.0)


@pytest.fixture
def dicho(monkeypatch) -> list[str]:
	textos: list[str] = []
	monkeypatch.setattr(voz, "hablar", lambda texto, interrumpir=False: textos.append(texto) or True)
	return textos


@pytest.fixture
def config(tmp_path, servidor, claves, monkeypatch):  # noqa: F811
	monkeypatch.setattr(red, "ESPERA_INICIAL", 0.01)
	instalacion = tmp_path / "instalación"
	(instalacion / "data").mkdir(parents=True)
	(instalacion / "EntornoLab.exe").write_bytes(b"EXE 1.0.0")
	return actualizador.Configuracion(
		version_actual="1.0.0",
		carpeta_app=instalacion,
		url_estable=servidor.url("version.json"),
		url_pruebas=servidor.url("pruebas/version.json"),
		claves_publicas=(claves.publica,),
		comando=["no-se-lanza"],
		permitir_desde_codigo=True,
	)


@pytest.fixture
def dialogo(app_wx, config, gestor):
	cerradas: list[bool] = []
	instancia = ui.DialogoActualizacion(None, config=config, gestor=gestor, al_cerrar_app=lambda: cerradas.append(True))
	instancia.cerradas = cerradas
	yield instancia
	procesar_eventos(lambda: not instancia.trabajando(), 10)
	instancia.Destroy()


def _esperar(dialogo) -> None:
	assert procesar_eventos(lambda: not dialogo.trabajando(), 20), "la tarea no terminó"
	procesar_eventos(segundos=0.05)


def test_accesibilidad_del_dialogo(dialogo):
	comprobar_etiquetas(dialogo)
	letras = letras_de_acceso(dialogo)
	assert len(letras) == len(set(letras)) == 8, letras
	assert dialogo.novedades.IsMultiLine() and not dialogo.novedades.IsEditable()
	assert not dialogo.estado.IsEditable()
	assert dialogo.GetEscapeId() == wx.ID_CANCEL
	assert dialogo.boton_cerrar.GetId() == wx.ID_CANCEL
	etiquetas = {boton.GetLabel() for boton in dialogo.GetChildren() if isinstance(boton, wx.Button)}
	assert etiquetas == {"&Comprobar ahora", "&Actualizar ahora", "&Saltar esta versión", "Cerra&r"}
	assert "1.0.0" in dialogo.estado.GetValue()
	assert not dialogo.boton_actualizar.IsEnabled() and not dialogo.boton_saltar.IsEnabled()
	assert [dialogo.canal.GetString(i) for i in range(dialogo.canal.GetCount())] == ["Estable", "Pruebas (versiones preliminares)"]
	assert dialogo.casilla_arrancar.GetValue() is False  # de fábrica no se conecta al arrancar


def test_comprobar_encuentra_version_nueva(dialogo, servidor, claves, dicho):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves, novedades="- Catálogo en línea de complementos.")
	dialogo.comprobar()
	assert dialogo.trabajando()
	assert dialogo.boton_cerrar.GetLabel() == "Cancela&r" and not dialogo.boton_comprobar.IsEnabled()
	_esperar(dialogo)
	assert dialogo.info.version == "1.1.0"
	assert "Hay una versión nueva: 1.1.0" in dialogo.estado.GetValue() and "2026-11-26" in dialogo.estado.GetValue()
	assert "Catálogo en línea" in dialogo.novedades.GetValue()
	assert dialogo.boton_actualizar.IsEnabled() and dialogo.boton_saltar.IsEnabled()
	assert dialogo.boton_cerrar.GetLabel() == "Cerra&r"
	assert dicho[0] == "Buscando actualizaciones..." and "1.1.0" in dicho[-1]


def test_comprobar_al_dia_y_con_error(dialogo, servidor, claves, dicho):  # noqa: F811
	dialogo.comprobar()
	_esperar(dialogo)
	assert "404" in dialogo.estado.GetValue()  # todavía no hay nada publicado
	publicar_version(servidor.carpeta, "1.0.0", ARCHIVOS, claves)
	dialogo.comprobar()
	_esperar(dialogo)
	assert "Ya tiene la versión más reciente (1.0.0)" in dialogo.estado.GetValue()
	assert not dialogo.boton_actualizar.IsEnabled()
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, None)  # sin firmar
	dialogo.comprobar()
	_esperar(dialogo)
	assert "no está firmada" in dialogo.estado.GetValue()
	assert dialogo.info is None and not dialogo.boton_actualizar.IsEnabled()
	assert dicho[-1] == dialogo.estado.GetValue()


def test_actualizar_descarga_prepara_y_cierra(dialogo, servidor, claves, dicho, monkeypatch):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	lanzados: list = []
	monkeypatch.setattr(actualizador, "lanzar_sustitucion", lambda ruta: lanzados.append(ruta))
	monkeypatch.setattr(actualizador, "reproductores_abiertos", lambda config: [])
	dialogo.comprobar()
	_esperar(dialogo)
	dicho.clear()
	dialogo.actualizar()
	_esperar(dialogo)
	assert lanzados and lanzados[0].name == "actualizar.bat"
	assert dialogo.resultado == ui.RESULTADO_ACTUALIZAR
	assert "se cerrará" in dialogo.estado.GetValue()
	assert dialogo.barra.GetValue() == 100
	# El progreso se anuncia por fases e hitos, no por cada porcentaje.
	assert dicho[0] == "Iniciando la descarga..."
	assert 3 <= len(dicho) <= 12, dicho
	assert procesar_eventos(lambda: bool(dialogo.cerradas), 5), "debe pedir el cierre de la aplicación"


def test_con_un_reproductor_abierto_se_avisa_y_no_se_cierra_sin_permiso(dialogo, servidor, claves, dialogo_modal, monkeypatch):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	monkeypatch.setattr(actualizador, "reproductores_abiertos", lambda config: [4242])
	cerrados: list[bool] = []
	monkeypatch.setattr(actualizador, "cerrar_reproductores", lambda config: cerrados.append(True) or [4242])
	dialogo.comprobar()
	_esperar(dialogo)
	dialogo_modal.responder(wx.ID_NO)
	dialogo.actualizar()
	assert not dialogo.trabajando() and not cerrados
	assert "reproductor" in dialogo_modal.ultimo.mensaje and "sesión" in dialogo_modal.ultimo.mensaje
	assert "aplazada" in dialogo.estado.GetValue()
	assert servidor.veces("EntornoLab_v1.1.0.zip") == 0
	# Acepta cerrarlos, pero queda uno que no lanzó el Estudio: tampoco se actualiza.
	dialogo_modal.responder(wx.ID_YES)
	dialogo.actualizar()
	assert cerrados and not dialogo.trabajando()
	assert "Ciérrelo a mano" in dialogo.estado.GetValue()


def test_saltar_esta_version(dialogo, servidor, claves):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	dialogo.comprobar()
	_esperar(dialogo)
	dialogo.saltar()
	assert dialogo.resultado == ui.RESULTADO_SALTADA
	assert actualizador.version_saltada() == "1.1.0"


def test_opciones_se_guardan_al_momento(dialogo, dicho):
	dialogo.casilla_arrancar.SetValue(True)
	dialogo._al_cambiar_casilla(None)
	assert actualizador.comprobacion_al_arrancar() and not actualizador.debe_preguntar()
	dialogo.canal.SetSelection(1)
	dialogo._al_cambiar_canal(None)
	assert actualizador.canal_elegido() == "pruebas" and dialogo.config.canal == "pruebas"
	assert "Canal cambiado" in dialogo.estado.GetValue()


def test_desde_el_codigo_fuente_informa_pero_no_instala(app_wx, config, gestor, servidor, claves):  # noqa: F811
	config.permitir_desde_codigo = False
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	dialogo = ui.DialogoActualizacion(None, config=config, gestor=gestor)
	try:
		dialogo.comprobar()
		_esperar(dialogo)
		assert "código fuente" in dialogo.estado.GetValue()
		assert not dialogo.boton_actualizar.IsEnabled() and dialogo.boton_saltar.IsEnabled()
	finally:
		dialogo.Destroy()


# ── Permiso y arranque ───────────────────────────────────────────────────────


def test_la_pregunta_de_permiso_guarda_la_respuesta(app_wx, dialogo_modal):
	dialogo_modal.responder(wx.ID_NO)
	assert ui.preguntar_permiso(None) is False
	assert "No se envía ningún dato" in dialogo_modal.ultimo.mensaje
	assert not actualizador.comprobacion_al_arrancar() and not actualizador.debe_preguntar()
	dialogo_modal.responder(wx.ID_YES)
	assert ui.preguntar_permiso(None) is True
	assert actualizador.comprobacion_al_arrancar()


def test_al_arrancar_sin_permiso_no_hay_ninguna_conexion(marco, config, gestor, servidor, claves, dialogo_modal, monkeypatch):  # noqa: F811
	monkeypatch.setattr(actualizador, "RETRASO_CONFIRMACION", 0)
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	dialogo_modal.responder(wx.ID_NO)
	ui.al_arrancar(marco, config=config, gestor=gestor)
	assert procesar_eventos(lambda: "version_confirmada" in actualizador.leer_estado(config), 5)
	assert len(dialogo_modal.mostrados) == 1  # la pregunta, una sola vez
	procesar_eventos(segundos=0.3)
	assert servidor.peticiones == []
	# La segunda vez ya no pregunta ni conecta.
	ui.al_arrancar(marco, config=config, gestor=gestor)
	procesar_eventos(segundos=0.3)
	assert len(dialogo_modal.mostrados) == 1 and servidor.peticiones == []


def test_al_arrancar_con_permiso_comprueba_una_vez_al_dia(marco, config, gestor, servidor, claves, dialogo_modal, monkeypatch):  # noqa: F811
	monkeypatch.setattr(actualizador, "RETRASO_CONFIRMACION", 0)
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	encontradas: list[str] = []
	monkeypatch.setattr(ui, "mostrar_dialogo_actualizacion", lambda padre, **opciones: encontradas.append(opciones["info"].version))
	avisos: list[bool] = []
	dialogo_modal.responder(wx.ID_YES)
	ui.al_arrancar(marco, config=config, gestor=gestor, al_haber_permiso=lambda: avisos.append(True))
	assert procesar_eventos(lambda: bool(encontradas), 10)
	assert encontradas == ["1.1.0"] and avisos == [True]
	assert servidor.veces("version.json") == 1
	# Segundo arranque el mismo día: no vuelve a conectar.
	ui.al_arrancar(marco, config=config, gestor=gestor, al_haber_permiso=lambda: avisos.append(True))
	procesar_eventos(segundos=0.3)
	assert servidor.veces("version.json") == 1 and avisos == [True]
	assert obtener_configuracion().obtener("actualizaciones.ultima_comprobacion")


def test_la_comprobacion_automatica_respeta_la_version_saltada_y_calla_los_fallos(marco, config, gestor, servidor, claves):  # noqa: F811
	encontradas: list[str] = []
	tarea = ui.comprobar_en_segundo_plano(marco, config, gestor, al_encontrar=lambda info: encontradas.append(info.version))
	assert procesar_eventos(lambda: tarea.terminada, 10)  # 404: no hay nada publicado; no molesta
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	actualizador.saltar_version("1.1.0")
	tarea = ui.comprobar_en_segundo_plano(marco, config, gestor, al_encontrar=lambda info: encontradas.append(info.version))
	assert procesar_eventos(lambda: tarea.terminada, 10)
	procesar_eventos(segundos=0.1)
	assert encontradas == []


def test_aviso_tras_una_actualizacion_que_volvio_atras(marco, config, gestor, dialogo_modal, monkeypatch):
	monkeypatch.setattr(actualizador, "RETRASO_CONFIRMACION", 0)
	actualizador.establecer_comprobacion_al_arrancar(False)
	config.carpeta_trabajo.mkdir(parents=True)
	config.archivo_resultado.write_text("estado=revertida\nmotivo=sin_marcador_de_salud\nversion=1.1.0\nanterior=1.0.0\n", encoding="utf-8")
	ui.al_arrancar(marco, config=config, gestor=gestor)
	assert procesar_eventos(lambda: bool(dialogo_modal.mostrados), 5)
	assert "se ha vuelto a la versión 1.0.0" in dialogo_modal.ultimo.mensaje
	assert actualizador.version_saltada() == "1.1.0"
