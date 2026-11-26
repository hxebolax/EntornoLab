"""Pruebas de lo general de la ventana principal con wx real, SIN mostrarla: menús, geometría, cierre y bandeja.

Lo propio de construir entornos (árbol, lista, propiedades, órdenes) está en
``test_ui_estudio_ventana.py``.
"""

from __future__ import annotations

import threading
from pathlib import Path

import pytest
import wx

from app.core.config import Configuracion
from app.core.instancia_unica import ORDEN_ABRIR, Orden
from app.core.version import NOMBRE_APLICACION
from app.dominio.formato import guardar_paquete
from app.ui import ventana_principal as vp
from tests.test_dominio_comun import piso_minimo

from ._ui_estudio_util import cerrar_ventana, crear_ventana, orden
from .conftest import procesar_eventos

MENUS_ESPERADOS = ["&Archivo", "&Editar", "&Insertar", "&Ver", "&Herramientas", "Ay&uda"]
# nombre del elemento → (modificadores, tecla)
ATAJOS_ESPERADOS = {
	"nuevo": (wx.ACCEL_CTRL, ord("N")),
	"abrir": (wx.ACCEL_CTRL, ord("O")),
	"guardar": (wx.ACCEL_CTRL, ord("S")),
	"guardar_como": (wx.ACCEL_CTRL | wx.ACCEL_SHIFT, ord("S")),
	"deshacer": (wx.ACCEL_CTRL, ord("Z")),
	"rehacer": (wx.ACCEL_CTRL, ord("Y")),
	"renombrar": (wx.ACCEL_NORMAL, wx.WXK_F2),
	"buscar": (wx.ACCEL_CTRL, ord("F")),
	"panel_siguiente": (wx.ACCEL_NORMAL, wx.WXK_F6),
	"panel_anterior": (wx.ACCEL_SHIFT, wx.WXK_F6),
	"comprobar": (wx.ACCEL_NORMAL, wx.WXK_F5),
	"recorrer": (wx.ACCEL_NORMAL, wx.WXK_F9),
	"preferencias": (wx.ACCEL_CTRL, ord(",")),
	"manual": (wx.ACCEL_NORMAL, wx.WXK_F1),
	"teclas": (wx.ACCEL_CTRL, wx.WXK_F1),
	"ayuda_contextual": (wx.ACCEL_CTRL, ord("H")),
}
PALABRAS_EN_INGLES = {
	"file",
	"edit",
	"view",
	"tools",
	"help",
	"open",
	"exit",
	"quit",
	"copy",
	"select",
	"about",
	"options",
	"refresh",
	"save",
	"undo",
	"redo",
}


@pytest.fixture
def ventana(app_wx, monkeypatch):
	marco = crear_ventana(monkeypatch)
	yield marco
	cerrar_ventana(marco)


def _elementos(menu: wx.Menu):
	"""Todos los elementos de un menú, también los de sus submenús."""
	for item in menu.GetMenuItems():
		if item.IsSeparator():
			continue
		yield item
		if item.GetSubMenu() is not None:
			yield from _elementos(item.GetSubMenu())


def test_arranca_sin_mostrarse(ventana):
	assert ventana.GetTitle() == NOMBRE_APLICACION
	assert not ventana.IsShown()
	assert ventana.GetStatusBar() is not None
	assert ventana.contexto.ventana is ventana and ventana.contexto.entorno is None


def test_menus_en_espanol_con_teclas_de_acceso(ventana):
	barra = ventana.GetMenuBar()
	assert [barra.GetMenuLabel(i) for i in range(barra.GetMenuCount())] == MENUS_ESPERADOS

	def revisar(menu: wx.Menu, titulo: str) -> None:
		letras = []
		for item in menu.GetMenuItems():
			if item.IsSeparator():
				continue
			etiqueta = item.GetItemLabel()
			assert "&" in etiqueta, f"«{etiqueta}» no tiene tecla de acceso"
			letras.append(etiqueta[etiqueta.index("&") + 1].lower())
			palabras = {p.lower().strip(".&") for p in item.GetItemLabelText().split()}
			assert not palabras & PALABRAS_EN_INGLES, f"«{etiqueta}» parece estar en inglés"
			if item.GetSubMenu() is not None:
				revisar(item.GetSubMenu(), etiqueta)
			elif item.IsEnabled():
				assert item.GetHelp(), f"«{etiqueta}» no tiene texto de ayuda"
		assert len(letras) == len(set(letras)), f"teclas de acceso repetidas en {titulo}: {letras}"

	ventana._rellenar_dinamicos()
	for i in range(barra.GetMenuCount()):
		revisar(barra.GetMenu(i), barra.GetMenuLabel(i))


def test_atajos_de_teclado(ventana):
	for nombre, (modificadores, tecla) in ATAJOS_ESPERADOS.items():
		atajo = ventana.elementos_menu[nombre].GetAccel()
		assert atajo is not None, f"{nombre} no tiene atajo"
		assert (atajo.GetFlags(), atajo.GetKeyCode()) == (modificadores, tecla), nombre
	# Escape nunca cierra la ventana principal, y Suprimir no es atajo de menú (se lo robaría a los campos de texto).
	barra = ventana.GetMenuBar()
	for i in range(barra.GetMenuCount()):
		for item in _elementos(barra.GetMenu(i)):
			atajo = item.GetAccel()
			assert atajo is None or atajo.GetKeyCode() not in (wx.WXK_ESCAPE, wx.WXK_DELETE), item.GetItemLabel()


def test_etiquetas_creadas_justo_antes_del_arbol_y_de_la_lista(ventana):
	hijos = list(ventana.pagina_entorno.GetChildren())
	for control in (ventana.arbol, ventana.lista, ventana.frase):
		anterior = hijos[hijos.index(control) - 1]
		assert isinstance(anterior, wx.StaticText), control.GetName()
		assert "&" in anterior.GetLabel(), anterior.GetLabel()
		assert control.GetHelpText(), "Ctrl+H necesita la ayuda del control"
	assert isinstance(ventana.arbol, wx.TreeCtrl) and ventana.lista.GetWindowStyleFlag() & wx.LC_REPORT
	assert [ventana.lista.GetColumn(i).GetText() for i in range(4)] == ["Nombre", "Tipo", "Medidas", "Posición"]
	assert not ventana.frase.IsEditable()


def test_cierre_guarda_la_geometria(app_wx, datos_temporales, monkeypatch):
	marco = crear_ventana(monkeypatch)
	marco.SetSize(wx.Size(640, 480))
	marco._rect_normal = marco.GetRect()
	marco.Close()
	assert procesar_eventos(lambda: not marco), "la ventana debe destruirse"
	guardada = Configuracion()
	assert guardada.obtener("ventana.ancho") == 640
	assert guardada.obtener("ventana.alto") == 480
	assert (datos_temporales / "config" / "config.json").is_file()


def test_posicion_fuera_de_pantalla_se_centra(app_wx, monkeypatch):
	monkeypatch.setattr(vp.VentanaPrincipal, "_cargar_seguimiento", lambda self: None)
	config = Configuracion()
	config.establecer("ventana.x", 30000)
	config.establecer("ventana.y", 30000)
	config.establecer("ventana.ancho", 50)  # demasiado pequeña: se usa el tamaño de serie
	marco = vp.VentanaPrincipal(config)
	try:
		assert marco.GetPosition().x != 30000
		assert marco.GetSize().width >= vp.TAMANO_MINIMO[0]
	finally:
		cerrar_ventana(marco)


def test_cerrar_a_bandeja_oculta_y_salir_cierra(app_wx, monkeypatch):
	monkeypatch.setattr(vp.IconoBandeja, "mostrar", lambda self: True)
	monkeypatch.setattr(vp.VentanaPrincipal, "_cargar_seguimiento", lambda self: None)
	config = Configuracion()
	config.establecer("general.cerrar_a_bandeja", True)
	marco = vp.VentanaPrincipal(config)
	# No se muestra la ventana en pruebas: se comprueba que se pide ocultarla.
	ocultada = []
	monkeypatch.setattr(marco, "Hide", lambda: ocultada.append(True) or True)
	marco.Close()  # como Alt+F4: se puede vetar
	procesar_eventos(segundos=0.2)
	assert marco, "con «cerrar a la bandeja» la ventana sigue viva"
	assert ocultada == [True]
	marco.salir()  # Archivo, Salir: cierra de verdad
	assert procesar_eventos(lambda: not marco)


def test_tarea_en_segundo_plano_vuelve_al_hilo_principal(ventana):
	resultado = {}

	def trabajo(_tarea):
		return threading.current_thread() is threading.main_thread()

	def al_terminar(en_principal):
		resultado["trabajo_en_principal"] = en_principal
		resultado["entrega_en_principal"] = threading.current_thread() is threading.main_thread()

	ventana.tareas.enviar(trabajo, al_terminar=al_terminar, nombre="prueba")
	assert procesar_eventos(lambda: "entrega_en_principal" in resultado)
	assert resultado == {"trabajo_en_principal": False, "entrega_en_principal": True}


def test_ordenes_de_otra_instancia_abren_el_entorno(app_wx, monkeypatch, tmp_path):
	ruta = tmp_path / "recibido.elab"
	guardar_paquete(ruta, piso_minimo()[0])
	restauradas = []

	class InstanciaFalsa:
		def recoger_ordenes(self):
			return [Orden(ORDEN_ABRIR, [str(ruta)], 1.0)]

	monkeypatch.setattr(vp.VentanaPrincipal, "_cargar_seguimiento", lambda self: None)
	marco = vp.VentanaPrincipal(Configuracion(), InstanciaFalsa())
	monkeypatch.setattr(marco, "restaurar", lambda: restauradas.append(True))
	try:
		marco._al_revisar_buzon(None)
		assert marco.contexto.entorno is not None and marco.contexto.entorno.nombre == "Piso mínimo"
		assert marco.contexto.ruta_paquete == ruta
		assert restauradas == [True]
		assert marco.abrir_archivos([Path("notas.txt")]) is False, "lo que no es un .elab no se abre"
	finally:
		cerrar_ventana(marco)


def test_ayuda_contextual_sin_ayuda(ventana, monkeypatch):
	mensajes = []
	monkeypatch.setattr(vp, "mostrar_mensaje", lambda padre, texto, *a, **k: mensajes.append(texto))
	monkeypatch.setattr(wx.Window, "FindFocus", staticmethod(lambda: None))
	orden(ventana, "ayuda_contextual")
	assert mensajes and "F1" in mensajes[0]


def test_ordenes_sin_entorno_lo_explican(ventana, monkeypatch):
	"""Sin entorno abierto, una orden no calla: dice qué hay que hacer antes."""
	mensajes = []
	monkeypatch.setattr(vp, "mostrar_mensaje", lambda padre, texto, *a, **k: mensajes.append(texto))
	for nombre in ("guardar", "exportar_texto", "insertar_objeto", "recorrer"):
		orden(ventana, nombre)
	assert len(mensajes) == 4 and all("Nuevo entorno" in texto for texto in mensajes)


def test_documento_inexistente_avisa(ventana, monkeypatch):
	mensajes = []
	from app.ui import dialogo_texto

	monkeypatch.setattr(dialogo_texto, "mostrar_mensaje", lambda padre, texto, *a, **k: mensajes.append(texto))
	assert dialogo_texto.mostrar_documento(ventana, "no_existe", "Prueba") is False
	assert mensajes and "no_existe" in mensajes[0]


def test_documento_markdown_se_muestra_como_texto(ventana, monkeypatch, datos_temporales):
	mostrados = []
	from app.ui import dialogo_texto

	(datos_temporales / "docs").mkdir(parents=True)
	(datos_temporales / "docs" / "manual.md").write_text("# Manual\n\nHola", encoding="utf-8")
	monkeypatch.setattr(dialogo_texto, "mostrar_texto", lambda padre, titulo, etiqueta, texto, copiable=False: mostrados.append(texto))
	assert dialogo_texto.mostrar_documento(ventana, "manual", "Manual") is True
	assert mostrados == ["# Manual\n\nHola"]
	assert Path(dialogo_texto.buscar_documento("manual")).suffix == ".md"
