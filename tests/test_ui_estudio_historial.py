"""Deshacer y rehacer en el Estudio: en el sitio, poniendo al día solo lo afectado y llevando la selección allí.

Por qué existe: con el historial por diferencias la ventana ya no rehace el
árbol, la lista y el plano tras cada cambio, sino que pone al día solo los
nodos, las filas y las figuras de los elementos que dice el parche. Si se le
escapara uno, el árbol enseñaría un nombre viejo o una puerta en el espacio
equivocado, y quien usa un lector de pantalla no tiene otra forma de verlo.
Aquí, tras cada edición, deshacer y rehacer, lo puesto al día por partes se
compara con lo que saldría calculándolo todo desde cero, en un entorno
pequeño (árbol creado entero) y en un barrio (árbol que se crea al desplegar).
"""

from __future__ import annotations

import pytest
import wx

from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.ui import modelo_plano as mp
from app.ui import operaciones
from tests import _entornos_grandes as eg
from tests.test_dominio_comun import catalogo_de_prueba

from ._ui_estudio_util import cerrar_ventana, crear_ventana, orden


@pytest.fixture
def catalogo(tmp_path):
	return catalogo_de_prueba(tmp_path)


@pytest.fixture
def ventana(app_wx, monkeypatch, catalogo, dialogo_modal):
	marco = crear_ventana(monkeypatch, catalogo)
	marco.confirmar_descartar = lambda: True
	yield marco
	cerrar_ventana(marco)


def _comprobar_arbol_nativo(ventana) -> None:
	"""Cada nodo nativo dice lo mismo que su nodo lógico y, si tiene los hijos creados, son los mismos y en el mismo orden."""
	arbol = ventana.arbol
	logico = ventana._arbol_logico

	def revisar(item: wx.TreeItemId) -> None:
		clave = arbol.GetItemData(item)
		nodo = logico.buscar(clave)
		assert nodo is not None, clave
		assert arbol.GetItemText(item) == nodo.texto, clave
		assert ventana._nodos.get(clave) == item, clave
		hijos = []
		hijo, galleta = arbol.GetFirstChild(item)
		while hijo.IsOk():
			hijos.append(hijo)
			hijo, galleta = arbol.GetNextChild(item, galleta)
		if hijos:
			assert [arbol.GetItemData(h) for h in hijos] == [n.clave for n in nodo.hijos], clave
			for hijo in hijos:
				revisar(hijo)
		else:
			assert arbol.ItemHasChildren(item) == bool(nodo.hijos), clave

	revisar(arbol.GetRootItem())


def _comprobar(ventana) -> None:
	"""Árbol, lista y plano iguales a los que saldrían calculándolos desde cero."""
	contexto = ventana.contexto
	entorno = contexto.entorno
	assert ventana._arbol_logico == operaciones.arbol_de(entorno, contexto.catalogo), "árbol lógico"
	_comprobar_arbol_nativo(ventana)
	elementos = operaciones.elementos_de_nodo(entorno, ventana._clave_nodo, ventana._arbol_logico)
	assert ventana._ids == [e.id for e in elementos], "filas de la lista"
	for fila, elemento in enumerate(elementos[:60]):
		assert tuple(ventana.lista.valores_fila(fila)) == operaciones.fila_de(elemento, contexto.catalogo).celdas(), elemento.id
	planta = contexto.planta_actual()
	assert ventana.plano.figuras == mp.figuras_de_planta(entorno, planta, contexto.catalogo, contexto.actividad_actual), "plano"


def _ediciones(ventana, lejano: str = "") -> None:
	"""Ediciones variadas con su deshacer y rehacer, comprobando todo tras cada paso.

	Con ``lejano`` (un espacio que ninguna edición toca) se comprueba además
	que su nodo del árbol es el MISMO objeto antes y después: la ventana no
	rehízo el árbol, lo puso al día por partes.
	"""
	contexto = ventana.contexto
	entorno = contexto.entorno
	planta = entorno.plantas[0]
	espacios = [e for e in planta.espacios if len(e.contorno) >= 3]
	movido, otro = espacios[1], espacios[len(espacios) // 2]
	contexto.seleccionar(planta.id)
	pasos = [
		("mover", lambda: ed.mover(entorno, movido.id, 1.5, 0.5)),
		("renombrar", lambda: ed.renombrar(entorno, otro.id, "Rincón nuevo")),
		("habitación", lambda: ed.crear_habitacion_rectangular(entorno, planta, "Trastero", 5000, 5000, 3, 2)),
		("duplicar", lambda: ed.duplicar(entorno, otro.id)),
		("borrar", lambda: ed.borrar(entorno, espacios[2].id)),
		("referencia", lambda: ed.anadir_referencia(entorno, planta, "Banco", *movido.centro())),
	]

	def nodo_lejano() -> operaciones.Nodo | None:
		return ventana._arbol_logico.buscar(lejano) if lejano else None

	def hecho(accion) -> None:
		antes = nodo_lejano()
		assert accion() is not None
		_comprobar(ventana)
		if lejano:
			assert nodo_lejano() is antes, "el nodo de un espacio no tocado se reutiliza"

	for nombre, operacion in pasos:
		hecho(lambda n=nombre, o=operacion: (contexto.ejecutar(n, o), True))
	for _vez in pasos:
		hecho(contexto.deshacer)
		assert contexto.entorno is entorno, "deshacer no sustituye el entorno"
	for _vez in pasos:
		hecho(contexto.rehacer)
	# Con un espacio desplegado y elegido en el árbol, también.
	contexto.seleccionar(movido.id)
	item = ventana._asegurar_item(movido.id)
	ventana.arbol.Expand(item)
	contexto.ejecutar("mover otra vez", lambda: ed.mover(entorno, movido.id, -1.0, 0.0))
	_comprobar(ventana)
	contexto.deshacer()
	_comprobar(ventana)


def test_vivienda_se_pone_al_dia_por_partes(ventana) -> None:
	ventana.contexto.abrir_documento(ejemplos.vivienda_ejemplo())
	_ediciones(ventana)


@pytest.mark.lento
def test_barrio_se_pone_al_dia_por_partes(ventana) -> None:
	entorno = eg.barrio(700)
	ventana.contexto.abrir_documento(entorno)
	assert not ventana._arbol_completo, "un barrio crea los hijos al desplegar"
	_ediciones(ventana, lejano=entorno.plantas[0].espacios[-1].id)


def test_deshacer_lleva_la_seleccion_a_lo_afectado_y_lo_anuncia(ventana, voz_simulada) -> None:
	contexto = ventana.contexto
	contexto.abrir_documento(ejemplos.vivienda_ejemplo())
	entorno = contexto.entorno
	planta = entorno.plantas[0]
	cocina = next(e for e in planta.espacios if e.nombre == "Cocina")
	contexto.ejecutar("mover Cocina", lambda: ed.mover(entorno, cocina.id, 0.5, 0.0))
	contexto.seleccionar(planta.id)
	orden(ventana, "deshacer")
	assert voz_simulada.contiene("Deshecho: mover Cocina")
	assert contexto.seleccion == cocina.id, "la selección vuelve al elemento afectado"
	assert ventana.arbol.GetItemData(ventana.arbol.GetSelection()) == cocina.id
	assert ventana._clave_propiedades == cocina.id
	# Deshacer la creación de algo: la selección va a su planta, que sigue existiendo.
	contexto.ejecutar("crear Aseo", lambda: ed.crear_habitacion_rectangular(entorno, planta, "Aseo", 300, 300, 2, 2))
	creado = planta.espacios[-1]
	contexto.seleccionar(creado.id)
	orden(ventana, "deshacer")
	assert entorno.buscar(creado.id) is None
	assert contexto.seleccion == planta.id
	orden(ventana, "rehacer")
	assert voz_simulada.contiene("Rehecho: crear Aseo")
	assert contexto.seleccion == planta.espacios[-1].id and planta.espacios[-1].nombre == "Aseo"
	assert contexto.modificado


def test_una_operacion_que_falla_a_medias_se_repinta_y_no_queda(ventana) -> None:
	contexto = ventana.contexto
	contexto.abrir_documento(ejemplos.vivienda_ejemplo())
	entorno = contexto.entorno
	planta = entorno.plantas[0]
	antes = entorno.a_dict()

	def a_medias() -> None:
		ed.renombrar(entorno, planta.espacios[0], "A medias")
		raise ed.ErrorEdicion("no se puede")

	with pytest.raises(ed.ErrorEdicion):
		contexto.ejecutar("falla", a_medias)
	assert entorno.a_dict() == antes and not contexto.historial.puede_deshacer
	_comprobar(ventana)
