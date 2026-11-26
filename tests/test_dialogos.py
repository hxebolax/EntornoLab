"""Pruebas de los diálogos y la bandeja (se crean sin mostrarse; nunca ShowModal)."""

from __future__ import annotations

import sys
import types

import wx

from app.core.config import Configuracion
from app.core.version import APP_VERSION, NOMBRE_APLICACION
from app.ui.acerca_de import texto_acerca_de
from app.ui.bandeja import IconoBandeja
from app.ui import dialogo_texto
from app.ui.dialogo_texto import DialogoTexto


def _botones(ventana: wx.Window) -> dict[int, str]:
	return {hijo.GetId(): hijo.GetLabel() for hijo in ventana.GetChildren() if isinstance(hijo, wx.Button)}


def test_dialogo_texto_accesible(app_wx):
	dialogo = DialogoTexto(None, "Título", "&Contenido:", "línea 1\nlínea 2", copiable=True)
	try:
		campo = dialogo.campo
		assert campo.IsMultiLine() and not campo.IsEditable(), "texto largo: multilínea de solo lectura"
		hijos = list(dialogo.GetChildren())
		anterior = hijos[hijos.index(campo) - 1]
		assert isinstance(anterior, wx.StaticText) and anterior.GetLabel() == "&Contenido:"
		botones = _botones(dialogo)
		assert botones[wx.ID_CANCEL] == "C&errar"
		assert "Co&piar al portapapeles" in botones.values()
		assert dialogo.GetEscapeId() == wx.ID_CANCEL
		assert campo.GetInsertionPoint() == 0
	finally:
		dialogo.Destroy()


def test_las_opciones_antiguas_las_cubre_preferencias(app_wx, datos_temporales):
	"""El diálogo «Opciones» del esqueleto se sustituyó por Preferencias: las casillas de bandeja siguen ahí y se guardan."""
	from app.ui.preferencias import DialogoPreferencias

	config = Configuracion()
	dialogo = DialogoPreferencias(None, config)
	try:
		botones = _botones_de(dialogo)
		assert "&Aceptar" in botones and "&Cancelar" in botones
		dialogo.fijar({"general.minimizar_a_bandeja": True})
		assert dialogo.aplicar() is True
	finally:
		dialogo.Destroy()
	assert Configuracion().obtener("general.minimizar_a_bandeja") is True


def _botones_de(ventana: wx.Window) -> list[str]:
	"""Etiquetas de todos los botones de una ventana, también los de sus paneles."""
	etiquetas: list[str] = []
	pendientes = list(ventana.GetChildren())
	while pendientes:
		hijo = pendientes.pop(0)
		if isinstance(hijo, wx.Button):
			etiquetas.append(hijo.GetLabel())
		pendientes.extend(hijo.GetChildren())
	return etiquetas


def test_texto_acerca_de():
	texto = texto_acerca_de()
	assert NOMBRE_APLICACION in texto and APP_VERSION in texto
	assert "Carpeta de datos" in texto


def test_menu_de_bandeja_en_espanol(app_wx):
	llamadas = []
	icono = IconoBandeja("Prueba", lambda: llamadas.append("restaurar"), lambda: llamadas.append("salir"))
	try:
		menu = icono.CreatePopupMenu()
		etiquetas = [item.GetItemLabel() for item in menu.GetMenuItems() if not item.IsSeparator()]
		assert etiquetas == ["&Mostrar la ventana", "&Salir"]
		menu.Destroy()
		icono._restaurar()
		assert llamadas == ["restaurar"]
	finally:
		icono.quitar()


def test_mensajes_con_boton_en_espanol(app_wx, dialogo_modal):
	"""Los mensajes salen por el diálogo accesible del proyecto, con el botón «Aceptar» en español (nunca wx.MessageBox)."""
	dialogo_texto.mostrar_mensaje(None, "Hola", "Ayuda")
	dialogo_texto.mostrar_error(None, "Fallo")
	assert [(d.clase, d.titulo) for d in dialogo_modal.mostrados] == [("DialogoMensaje", "Ayuda"), ("DialogoMensaje", "Error")]
	assert all("&Aceptar" in d.textos for d in dialogo_modal.mostrados)
	assert "Hola" in dialogo_modal.mostrados[0].textos and "Fallo" in dialogo_modal.mostrados[1].textos


def test_mensajes_usan_los_dialogos_del_proyecto_si_existen(app_wx, monkeypatch):
	recibidos = []
	falso = types.SimpleNamespace(
		mostrar_mensaje=lambda padre, mensaje, titulo, icono=None: recibidos.append(("mensaje", mensaje, titulo)),
		mostrar_error=lambda padre, mensaje, titulo: recibidos.append(("error", mensaje, titulo)),
	)
	paquete = types.ModuleType("app.ui.accesibilidad")
	paquete.dialogos = falso
	monkeypatch.setitem(sys.modules, "app.ui.accesibilidad", paquete)
	monkeypatch.setitem(sys.modules, "app.ui.accesibilidad.dialogos", falso)
	dialogo_texto.mostrar_mensaje(None, "Hola", "Ayuda")
	dialogo_texto.mostrar_error(None, "Fallo", "Abrir")
	assert recibidos == [("mensaje", "Hola", "Ayuda"), ("error", "Fallo", "Abrir")]


def test_documento_inexistente_avisa_en_espanol(app_wx, dialogo_modal):
	assert dialogo_texto.mostrar_documento(None, "no_existe_nunca", "Manual") is False
	assert len(dialogo_modal.mostrados) == 1 and dialogo_modal.ultimo.titulo == "Manual"
	assert "&Aceptar" in dialogo_modal.ultimo.textos
	assert any("no_existe_nunca" in texto for texto in dialogo_modal.ultimo.textos)


def test_sin_el_paquete_de_accesibilidad_se_usa_un_cuadro_nativo_en_espanol(app_wx, monkeypatch):
	"""Reserva de ``dialogo_texto``: si faltaran los diálogos accesibles, un MessageDialog con «Aceptar» (nunca wx.MessageBox)."""
	import app.ui.accesibilidad as paquete

	monkeypatch.delattr(paquete, "dialogos", raising=False)
	monkeypatch.setitem(sys.modules, "app.ui.accesibilidad.dialogos", None)
	vistos = []
	monkeypatch.setattr(wx.MessageDialog, "ShowModal", lambda d: vistos.append((d.GetTitle(), d.GetMessage(), d.GetOKLabel())) or wx.ID_OK)
	dialogo_texto.mostrar_mensaje(None, "Hola", "Ayuda")
	dialogo_texto.mostrar_error(None, "Fallo")
	assert vistos == [("Ayuda", "Hola", "&Aceptar"), ("Error", "Fallo", "&Aceptar")]
