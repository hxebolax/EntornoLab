"""Cerrar el Estudio con un entorno abierto no debe dejar escapar errores.

Al destruirse la ventana, Windows borra los nodos del árbol y puede enviar
«selección cambiada» cuando wx ya ha destruido el control. Con el manejador
conectado, se leía un árbol inexistente («wrapped C/C++ object of type TreeCtrl
has been deleted») y el cierre acababa en una cascada de errores no
controlados. Pasó en la versión compilada al salir con un entorno abierto.

La destrucción nativa no se deja provocar igual en una prueba automática, así
que se comprueba la situación exacta del fallo: el aviso llega con el árbol (o
la lista) ya destruido, y el manejador no debe tocarlo.
"""

from __future__ import annotations

import sys

import pytest

wx = pytest.importorskip("wx")

from app.dominio.ejemplos import centro_dos_plantas  # noqa: E402
from app.dominio.formato import guardar_paquete  # noqa: E402

from ._ui_estudio_util import cerrar_ventana, crear_ventana  # noqa: E402
from .conftest import procesar_eventos  # noqa: E402


@pytest.fixture
def ventana_abierta(app_wx, monkeypatch, tmp_path):
	"""Estudio con el «Centro de dos plantas» abierto y un nodo hondo del árbol elegido."""
	ruta = tmp_path / "centro.elab"
	guardar_paquete(ruta, centro_dos_plantas())
	ventana = crear_ventana(monkeypatch)
	assert ventana.abrir_paquete(ruta)
	arbol = ventana.arbol
	item = arbol.GetRootItem()
	for _nivel in range(4):
		arbol.Expand(item)
		hijo, _cookie = arbol.GetFirstChild(item)
		if not hijo.IsOk():
			break
		item = hijo
	arbol.SelectItem(item)
	procesar_eventos(segundos=0.2)
	yield ventana
	cerrar_ventana(ventana)


def test_aviso_del_arbol_con_el_arbol_destruido(ventana_abierta) -> None:
	"""El manejador del árbol no lee el control si ya no existe."""
	ventana = ventana_abierta
	item = ventana.arbol.GetSelection()
	aviso = wx.TreeEvent(wx.wxEVT_TREE_SEL_CHANGED, ventana.arbol, item)
	ventana.arbol.Destroy()
	procesar_eventos(segundos=0.1)
	assert not ventana.arbol, "el árbol está destruido, como al cerrar"
	ventana._al_elegir_en_arbol(aviso)
	ventana._al_desplegar(aviso)
	ventana._al_plegar(aviso)


def test_aviso_durante_el_cierre_no_hace_nada(ventana_abierta) -> None:
	"""Con la ventana saliendo, los avisos del árbol y de la lista se ignoran."""
	ventana = ventana_abierta
	ventana._saliendo = True
	aviso = wx.TreeEvent(wx.wxEVT_TREE_SEL_CHANGED, ventana.arbol, ventana.arbol.GetSelection())
	clave_antes = ventana._clave_nodo
	ventana._al_elegir_en_arbol(aviso)
	assert ventana._clave_nodo == clave_antes, "no se cambia de nodo mientras se cierra"
	ventana._saliendo = False


def test_cerrar_con_un_nodo_elegido_no_deja_errores(ventana_abierta, monkeypatch) -> None:
	"""El cierre completo con un nodo elegido termina sin errores no controlados."""
	errores: list[BaseException] = []
	monkeypatch.setattr(sys, "excepthook", lambda tipo, valor, traza: errores.append(valor))
	ventana = ventana_abierta
	ventana.contexto.modificado = False
	ventana.salir()
	procesar_eventos(lambda: not ventana, 3)
	assert not ventana, "la ventana se ha cerrado"
	assert not errores, f"el cierre dejó escapar errores: {errores!r}"
