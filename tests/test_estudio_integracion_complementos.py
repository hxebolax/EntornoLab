"""Complementos que faltan al abrir un entorno: el objeto queda como caja y se avisa UNA vez.

En el Estudio el aviso es un mensaje accesible que nombra los complementos y
pregunta «¿Buscar en el catálogo en línea?». Sin aceptar no se intenta
ninguna conexión; aceptando se abre el diálogo del catálogo (aquí, un doble).
En el reproductor, ``entornos.complementos_que_faltan`` da cada complemento
una sola vez; la partida lo dice una vez al empezar
(``tests/test_reproductor_juego.py::test_complemento_que_falta_el_objeto_queda_como_caja_y_se_avisa_una_vez``).
"""

from __future__ import annotations

import pytest
import wx

from app.dominio.formato import guardar_paquete
from app.dominio.modelo import Objeto
from app.reproductor import entornos
from app.ui import dialogo_complementos_en_linea as dialogo_en_linea
from app.ui import modelo_plano as mp
from app.ui import operaciones
from tests.test_dominio_comun import catalogo_de_prueba, piso_minimo

from ._ui_estudio_util import boton, cerrar_ventana, crear_ventana

TITULO = "Complementos que faltan"


@pytest.fixture
def catalogo(tmp_path):
	return catalogo_de_prueba(tmp_path)


def _piso_con_ajenos(catalogo, tipos=("museo/vitrina", "museo/vitrina", "taller/torno")):
	"""Piso mínimo con un objeto del catálogo y otros de complementos que no están instalados."""
	entorno, planta, _salon, _cocina = piso_minimo()
	cama = catalogo.crear_objeto("prueba/cama", 1.5, 1.5)
	cama.id = "cama-1"
	planta.objetos.append(cama)
	for numero, tipo in enumerate(tipos, start=1):
		planta.objetos.append(
			Objeto(id=f"ajeno-{numero}", nombre=f"Ajeno {numero}", tipo=tipo, x=6.0, y=float(numero), ancho=0.8, fondo=0.5, alto=1.2)
		)
	planta.objetos.append(Objeto(id="caja-1", nombre="Caja", tipo="caja", x=3.0, y=3.0))
	return entorno, planta


@pytest.fixture
def doble_catalogo(monkeypatch):
	"""Sustituye el diálogo del catálogo en línea: apunta cómo se le llamaría y no abre nada."""
	llamadas: list[dict] = []

	def doble(padre, al_cambiar=None, buscar=""):
		llamadas.append({"padre": padre, "al_cambiar": al_cambiar, "buscar": buscar})
		return 0

	monkeypatch.setattr(dialogo_en_linea, "mostrar_complementos_en_linea", doble)
	return llamadas


@pytest.fixture
def ventana(app_wx, monkeypatch, catalogo, dialogo_modal, voz_simulada):
	marco = crear_ventana(monkeypatch, catalogo)
	yield marco
	cerrar_ventana(marco)


# ── Sin ventana ──────────────────────────────────────────────────────────────


def test_cuenta_los_complementos_que_faltan_y_el_texto_los_nombra(catalogo):
	entorno, _planta = _piso_con_ajenos(catalogo)
	faltan = operaciones.complementos_que_faltan(entorno, catalogo)
	assert faltan == {"museo": 2, "taller": 1}, "«caja» y los del catálogo no cuentan"
	texto = operaciones.texto_complementos_que_faltan(faltan)
	assert "museo, taller" in texto and "3 objetos" in texto and "cajas con sus medidas" in texto
	assert texto.endswith("¿Buscar en el catálogo en línea?")
	assert operaciones.complementos_que_faltan(entorno, None) == {}, "sin catálogo cargado no se avisa de todo"
	assert operaciones.texto_complementos_que_faltan({}) == ""


def test_el_objeto_que_falta_se_dibuja_como_caja_con_sus_medidas(catalogo):
	entorno, planta = _piso_con_ajenos(catalogo, tipos=("museo/vitrina",))
	figura = next(f for f in mp.figuras_de_planta(entorno, planta, catalogo) if f.id == "ajeno-1")
	objeto = next(o for o in planta.objetos if o.id == "ajeno-1")
	assert figura.puntos == objeto.huella_caja() and figura.letra == "A"


def test_reproductor_cada_complemento_que_falta_una_sola_vez(catalogo):
	entorno, _planta = _piso_con_ajenos(catalogo)
	assert entornos.complementos_que_faltan(entorno, catalogo) == ["museo", "taller"]
	sin_ajenos, _ = _piso_con_ajenos(catalogo, tipos=())
	assert entornos.complementos_que_faltan(sin_ajenos, catalogo) == []


# ── Con la ventana principal ─────────────────────────────────────────────────


def test_al_abrir_se_avisa_una_vez_y_sin_aceptar_no_se_conecta(ventana, dialogo_modal, catalogo, doble_catalogo, sin_red, tmp_path):
	entorno, _planta = _piso_con_ajenos(catalogo)
	ruta = tmp_path / "con-ajenos.elab"
	guardar_paquete(ruta, entorno)
	dialogo_modal.responder(boton(1))
	assert ventana.abrir_paquete(ruta)
	avisos = [d for d in dialogo_modal.mostrados if d.titulo == TITULO]
	assert len(avisos) == 1, "se avisa UNA vez al abrir"
	texto = " ".join(" ".join(avisos[0].textos).split())  # el mensaje viene partido en líneas
	assert "museo, taller" in texto and "¿Buscar en el catálogo en línea?" in texto
	assert {"&Buscar en el catálogo en línea", "&Cerrar"} <= set(avisos[0].textos)
	assert doble_catalogo == [] and sin_red.intentos == [], "sin aceptar no se abre el catálogo ni se intenta ninguna conexión"
	# Los objetos siguen en el entorno con sus medidas: nada se pierde.
	ajenos = [o for p in ventana.contexto.entorno.plantas for o in p.objetos if o.id.startswith("ajeno-")]
	assert [(o.tipo, o.ancho, o.fondo, o.alto) for o in ajenos] == [
		("museo/vitrina", 0.8, 0.5, 1.2),
		("museo/vitrina", 0.8, 0.5, 1.2),
		("taller/torno", 0.8, 0.5, 1.2),
	]
	assert {f.id for f in ventana.plano.figuras if f.clase == "objeto"} >= {"ajeno-1", "ajeno-2", "ajeno-3"}
	# Seguir trabajando (cambiar algo, comprobar) no vuelve a avisar.
	ventana.contexto.ejecutar("renombrar", lambda: setattr(ventana.contexto.entorno, "nombre", "Otro"))
	assert len([d for d in dialogo_modal.mostrados if d.titulo == TITULO]) == 1


def test_aceptando_se_abre_el_catalogo_en_linea(ventana, dialogo_modal, catalogo, doble_catalogo, tmp_path):
	entorno, _planta = _piso_con_ajenos(catalogo)
	ruta = tmp_path / "con-ajenos.elab"
	guardar_paquete(ruta, entorno)
	dialogo_modal.responder(boton(0))
	assert ventana.abrir_paquete(ruta)
	assert len(doble_catalogo) == 1
	llamada = doble_catalogo[0]
	assert llamada["padre"] is ventana and llamada["al_cambiar"] == ventana.contexto.recargar_catalogo
	assert llamada["buscar"] == "", "con varios complementos no se filtra por uno solo"
	# Con uno solo, el catálogo se abre ya filtrado por su identificador.
	uno, _ = _piso_con_ajenos(catalogo, tipos=("museo/vitrina",))
	otra_ruta = tmp_path / "uno.elab"
	guardar_paquete(otra_ruta, uno)
	dialogo_modal.responder(boton(0))
	assert ventana.abrir_paquete(otra_ruta)
	assert doble_catalogo[-1]["buscar"] == "museo"


def test_sin_complementos_que_falten_no_se_pregunta(ventana, dialogo_modal, catalogo, doble_catalogo, tmp_path):
	entorno, _planta = _piso_con_ajenos(catalogo, tipos=())
	ruta = tmp_path / "completo.elab"
	guardar_paquete(ruta, entorno)
	assert ventana.abrir_paquete(ruta)
	assert not [d for d in dialogo_modal.mostrados if d.titulo == TITULO] and doble_catalogo == []


def test_el_catalogo_en_linea_se_abre_filtrado_sin_conectarse_hasta_mostrarse(app_wx, dialogo_modal, monkeypatch, sin_red):
	"""El parámetro ``buscar`` deja escrito el identificador; la descarga solo se pide al mostrarse (aquí no llega a pedirse)."""
	monkeypatch.setattr(dialogo_en_linea.wx, "CallAfter", lambda *_argumentos, **_opciones: None)
	vistos: list[str] = []

	def mirar(dialogo):
		vistos.append(dialogo.buscar.GetValue())
		return wx.ID_CANCEL

	dialogo_modal.responder(mirar)
	assert dialogo_en_linea.mostrar_complementos_en_linea(None, buscar="museo") == 0
	assert vistos == ["museo"] and sin_red.intentos == []
