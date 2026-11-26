"""Utilidades comunes de las pruebas de la ventana principal del Estudio.

Las pruebas manejan la ventana como lo haría una persona con el teclado:
lanzan órdenes de menú y contestan a los diálogos con la fixture
``dialogo_modal`` (nunca un ``ShowModal`` real).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import wx

from app.core.config import Configuracion
from app.ui import ventana_principal as vp

from .conftest import procesar_eventos


def crear_ventana(monkeypatch, catalogo=None, con_seguimiento: bool = False, **opciones) -> vp.VentanaPrincipal:
	"""Ventana principal SIN mostrar. Por defecto sin la otra mitad del Estudio, para que la prueba no dependa de ella."""
	if not con_seguimiento:
		monkeypatch.setattr(vp.VentanaPrincipal, "_cargar_seguimiento", lambda self: None)
	return vp.VentanaPrincipal(Configuracion(), catalogo=catalogo, **opciones)


def cerrar_ventana(ventana: vp.VentanaPrincipal) -> None:
	"""Cierra la ventana sin preguntar por los cambios (la prueba ya terminó)."""
	if ventana:
		ventana.contexto.modificado = False
		ventana.salir()
		procesar_eventos(lambda: not ventana, 2)


def orden(ventana: wx.Frame, nombre: str, marcada: bool | None = None) -> None:
	"""Lanza una orden de menú por su nombre, como si se eligiera en la barra."""
	item = ventana.elementos_menu[nombre]
	evento = wx.CommandEvent(wx.wxEVT_MENU, item.GetId())
	evento.SetEventObject(ventana)
	if marcada is not None:
		evento.SetInt(int(marcada))
	ventana.GetEventHandler().ProcessEvent(evento)


def rellenar(**valores: Any):
	"""Respuesta para un ``DialogoFormulario``: rellena esos campos y acepta."""
	return lambda dialogo: (dialogo.fijar(valores), wx.ID_OK)[1]


def elegir_objeto(tipo: str, variante: str | None = None):
	"""Respuesta para el diálogo del catálogo: elige un objeto y acepta."""
	return lambda dialogo: (dialogo.elegir(tipo, variante), wx.ID_OK)[1]


def boton(indice: int):
	"""Respuesta para un mensaje con botones que dicen la acción (``elegir_opcion``): pulsa el botón ``indice``."""
	return lambda dialogo: dialogo.ids_opciones[indice]


def fichero(ruta: Path):
	"""Respuesta para un ``wx.FileDialog``: elige esa ruta y acepta."""
	return lambda dialogo: (dialogo.SetPath(str(ruta)), wx.ID_OK)[1]


def espacio(ventana, nombre: str):
	"""Espacio del entorno abierto con ese nombre."""
	for planta in ventana.contexto.entorno.plantas:
		for candidato in planta.espacios:
			if candidato.nombre == nombre:
				return candidato
	raise AssertionError(f"No existe el espacio {nombre}")


def textos_del_arbol(ventana) -> list[str]:
	"""Textos de todos los nodos del árbol, en orden."""
	arbol = ventana.arbol
	textos: list[str] = []

	def recorrer(item) -> None:
		textos.append(arbol.GetItemText(item))
		hijo, galleta = arbol.GetFirstChild(item)
		while hijo.IsOk():
			recorrer(hijo)
			hijo, galleta = arbol.GetNextChild(item, galleta)

	raiz = arbol.GetRootItem()
	if raiz.IsOk():
		recorrer(raiz)
	return textos
