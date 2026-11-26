"""Pruebas del diálogo del catálogo en línea de complementos (sin mostrarlo; nunca un modal real)."""

from __future__ import annotations

import pytest

wx = pytest.importorskip("wx")

from app.core import paths, red, tareas, voz  # noqa: E402
from app.core.configuracion import obtener_configuracion  # noqa: E402
from app.services import actualizador  # noqa: E402
from app.services import complementos_en_linea as cel  # noqa: E402
from app.ui import dialogo_complementos_en_linea as ui  # noqa: E402
from app.ui import dialogo_texto  # noqa: E402
from tests._actualizador_util import Claves, escribir_json  # noqa: E402
from tests.conftest import procesar_eventos  # noqa: E402
from tests.servidor_http_prueba import servidor  # noqa: E402, F401 - fixture
from tests.test_actualizador_dialogo import comprobar_etiquetas, letras_de_acceso  # noqa: E402
from tests.test_complementos_en_linea_servicio import Tienda, ficha  # noqa: E402


@pytest.fixture(scope="module")
def claves(tmp_path_factory) -> Claves:
	return Claves(tmp_path_factory.mktemp("claves"))


@pytest.fixture
def dicho(monkeypatch) -> list[str]:
	textos: list[str] = []
	monkeypatch.setattr(voz, "hablar", lambda texto, interrumpir=False: textos.append(texto) or True)
	return textos


@pytest.fixture
def tienda(servidor, claves, monkeypatch) -> Tienda:  # noqa: F811
	monkeypatch.setattr(red, "ESPERA_INICIAL", 0.01)
	monkeypatch.setattr(actualizador, "CLAVES_PUBLICAS_ED25519", (claves.publica,))
	instancia = Tienda(servidor, claves)
	obtener_configuracion().establecer("complementos.url_catalogo", instancia.url)
	return instancia


@pytest.fixture
def gestor():
	instancia = tareas.GestorTareas(max_hilos=1, nombre="prueba", prioridad_baja=False)
	yield instancia
	instancia.apagar(1.0)


@pytest.fixture
def dialogo(app_wx, tienda, gestor):
	cambios: list[bool] = []
	instancia = ui.DialogoComplementosEnLinea(None, al_cambiar=lambda: cambios.append(True), gestor=gestor)
	instancia.avisos = cambios
	yield instancia
	procesar_eventos(lambda: not instancia.trabajando(), 10)
	instancia.Destroy()


def _esperar(dialogo) -> None:
	assert procesar_eventos(lambda: not dialogo.trabajando(), 20), "la tarea no terminó"
	procesar_eventos(segundos=0.05)


def _instalar_local(identificador: str, version: str = "1.0") -> None:
	carpeta = paths.ruta_complementos() / identificador
	carpeta.mkdir(parents=True)
	escribir_json(carpeta / "complemento.json", ficha(identificador, version))


def _filas(dialogo) -> list[list[str]]:
	return [[dialogo.lista.GetItemText(fila, columna) for columna in range(5)] for fila in range(dialogo.lista.GetItemCount())]


def _seleccionar(dialogo, identificador: str) -> None:
	indice = [fila.id for fila in dialogo.filas].index(identificador)
	dialogo.lista.Select(indice)
	dialogo.lista.Focus(indice)
	dialogo._habilitar()


def _botones_activos(dialogo) -> set[str]:
	nombres = ("instalar", "actualizar", "todos", "desinstalar", "anterior", "detalles", "refrescar")
	return {nombre for nombre in nombres if getattr(dialogo, f"boton_{nombre}").IsEnabled()}


def test_accesibilidad_del_dialogo(dialogo):
	comprobar_etiquetas(dialogo)
	letras = letras_de_acceso(dialogo)
	assert len(letras) == len(set(letras)) == 12, letras
	assert isinstance(dialogo.buscar, wx.TextCtrl) and not isinstance(dialogo.buscar, wx.SearchCtrl)
	assert dialogo.lista.HasFlag(wx.LC_REPORT) and dialogo.lista.HasFlag(wx.LC_SINGLE_SEL)
	columnas = [dialogo.lista.GetColumn(indice).GetText() for indice in range(dialogo.lista.GetColumnCount())]
	assert columnas == ["Nombre", "Estado", "Versión instalada", "Versión disponible", "Tamaño"]
	etiquetas = [boton.GetLabel() for boton in dialogo.GetChildren() if isinstance(boton, wx.Button)]
	assert etiquetas == [
		"&Instalar",
		"&Actualizar",
		"Actualizar t&odos",
		"&Desinstalar",
		"Versió&n anterior",
		"D&etalles",
		"&Refrescar",
		"&Cerrar",
	]
	assert dialogo.GetEscapeId() == wx.ID_CANCEL and not dialogo.estado.IsEditable()
	assert _botones_activos(dialogo) == {"refrescar"}  # lista vacía: nada que hacer salvo refrescar


def test_sin_conexion_se_ve_lo_instalado(dialogo, tienda, dicho):
	_instalar_local("hogar")
	dialogo.refrescar()  # el catálogo todavía no existe en el servidor: 404
	_esperar(dialogo)
	assert "404" in dialogo.estado.GetValue() and dicho[-1] == dialogo.estado.GetValue()
	assert _filas(dialogo) == [["Complemento hogar", "Solo en este equipo (de serie)", "1.0", "No está en el catálogo", ""]]
	assert _botones_activos(dialogo) == {"detalles", "refrescar"}


def test_lista_con_estados_y_botones(dialogo, tienda, dicho):
	for identificador in ("hogar", "ciudad", "propio"):
		_instalar_local(identificador)
	escribir_json(paths.ruta_complementos() / "de_serie.json", {"de_serie": {"hogar": "1.0", "ciudad": "1.0"}})
	tienda.publicar(ficha("hogar", "1.0"))
	tienda.publicar(ficha("ciudad", "1.2"))
	tienda.publicar(ficha("oficina", "2.0"))
	dialogo.refrescar()
	assert dialogo.boton_cerrar.GetLabel() == "&Cancelar"
	_esperar(dialogo)
	assert dialogo.boton_cerrar.GetLabel() == "&Cerrar"
	filas = {fila[0]: fila[1:4] for fila in _filas(dialogo)}
	assert filas == {
		"Complemento ciudad": ["Hay actualización (de serie)", "1.0", "1.2"],
		"Complemento hogar": ["Al día (de serie)", "1.0", "1.0"],
		"Complemento oficina": ["Disponible", "No instalado", "2.0"],
		"Complemento propio": ["Solo en este equipo", "1.0", "No está en el catálogo"],
	}
	assert all(fila[4].endswith("KB") for fila in _filas(dialogo) if fila[3][0].isdigit())
	assert dialogo.estado.GetValue() == "4 complementos. 1 tiene actualización. 1 se puede instalar."
	assert dicho[-1] == dialogo.estado.GetValue()
	assert dialogo.lista.GetFocusedItem() == 0 and dialogo.seleccionado().id == "ciudad"  # siempre hay una fila enfocada
	esperado = {
		"ciudad": {"actualizar", "todos", "detalles", "refrescar"},
		"hogar": {"todos", "detalles", "refrescar"},
		"oficina": {"instalar", "todos", "detalles", "refrescar"},
		"propio": {"desinstalar", "todos", "detalles", "refrescar"},
	}
	for identificador, activos in esperado.items():
		_seleccionar(dialogo, identificador)
		assert _botones_activos(dialogo) == activos, identificador


def test_buscar_y_filtrar_por_categoria_conservan_la_seleccion(dialogo, tienda):
	tienda.publicar(ficha("hogar", "1.0", descripcion="Muebles de casa"))
	tienda.publicar(ficha("ciudad", "1.0", descripcion="Semáforos y bancos", objetos=[{**ficha()["objetos"][0], "categoria": "calle"}]))
	dialogo.refrescar()
	_esperar(dialogo)
	categorias = [dialogo.categoria.GetString(indice) for indice in range(dialogo.categoria.GetCount())]
	assert categorias[0] == "Todas" and "calle" in categorias and "dormitorio" in categorias
	_seleccionar(dialogo, "hogar")
	dialogo.buscar.SetValue("SEMÁFOROS")
	procesar_eventos(segundos=0.05)
	assert [fila.id for fila in dialogo.filas] == ["ciudad"] and dialogo.seleccionado().id == "ciudad"
	dialogo.buscar.SetValue("")
	procesar_eventos(segundos=0.05)
	_seleccionar(dialogo, "hogar")
	dialogo.categoria.SetSelection(categorias.index("dormitorio"))
	dialogo._filtrar()
	assert [fila.id for fila in dialogo.filas] == ["hogar"] and dialogo.seleccionado().id == "hogar"
	dialogo.buscar.SetValue("no hay nada así")
	procesar_eventos(segundos=0.05)
	assert dialogo.filas == [] and dialogo.seleccionado() is None
	assert _botones_activos(dialogo) == {"refrescar"}


def test_instalar_el_seleccionado(dialogo, tienda, dicho):
	tienda.publicar(ficha("oficina", "2.0"))
	escribir_json(paths.ruta_complementos() / "de_serie.json", {"de_serie": {}})
	dialogo.refrescar()
	_esperar(dialogo)
	dialogo.instalar()
	_esperar(dialogo)
	assert (paths.ruta_complementos() / "oficina" / "complemento.json").is_file()
	assert dialogo.estado.GetValue() == "«Complemento oficina» instalado, versión 2.0."
	assert dicho[-1] == dialogo.estado.GetValue()
	assert _filas(dialogo)[0][1:4] == ["Al día", "2.0", "2.0"]
	assert dialogo.avisos == [True] and dialogo.cambios == 1
	assert dialogo.seleccionado().id == "oficina"
	assert _botones_activos(dialogo) == {"desinstalar", "detalles", "refrescar"}


def test_actualizar_todos_y_volver_a_la_anterior(dialogo, tienda, dialogo_modal):
	for identificador in ("hogar", "ciudad"):
		tienda.publicar(ficha(identificador, "1.0"))
		cel.instalar(tienda.indice().complementos[identificador])
		tienda.publicar(ficha(identificador, "1.1"))
	dialogo.refrescar()
	_esperar(dialogo)
	assert dialogo.boton_todos.IsEnabled()
	dialogo.actualizar_todos()
	_esperar(dialogo)
	assert "«Complemento ciudad» actualizado de la versión 1.0 a la 1.1." in dialogo.estado.GetValue()
	assert "«Complemento hogar» actualizado de la versión 1.0 a la 1.1." in dialogo.estado.GetValue()
	assert {fila[0]: fila[1] for fila in _filas(dialogo)} == {"Complemento ciudad": "Al día", "Complemento hogar": "Al día"}
	assert not dialogo.boton_todos.IsEnabled() and dialogo.avisos == [True]
	_seleccionar(dialogo, "hogar")
	assert dialogo.boton_anterior.IsEnabled()
	dialogo_modal.responder(wx.ID_NO)
	dialogo.volver_a_anterior()
	assert not dialogo.trabajando()
	dialogo_modal.responder(wx.ID_YES)
	dialogo.volver_a_anterior()
	_esperar(dialogo)
	assert dialogo.estado.GetValue() == "«Complemento hogar» ha vuelto a la versión 1.0."
	assert dialogo.seleccionado().id == "hogar" and dialogo.seleccionado().estado == cel.ACTUALIZABLE
	assert dialogo.avisos == [True, True]


def test_desinstalar_pide_confirmacion(dialogo, tienda, dialogo_modal):
	tienda.publicar(ficha("oficina", "2.0"))
	escribir_json(paths.ruta_complementos() / "de_serie.json", {"de_serie": {}})
	cel.instalar(tienda.indice().complementos["oficina"])
	dialogo.refrescar()
	_esperar(dialogo)
	dialogo_modal.responder(wx.ID_NO)
	dialogo.desinstalar()
	assert (paths.ruta_complementos() / "oficina").is_dir() and "cajas" in dialogo_modal.ultimo.mensaje
	dialogo_modal.responder(wx.ID_YES)
	dialogo.desinstalar()
	_esperar(dialogo)
	assert not (paths.ruta_complementos() / "oficina").exists()
	assert dialogo.estado.GetValue() == "«Complemento oficina» desinstalado."
	assert _filas(dialogo)[0][1:3] == ["Disponible", "No instalado"]
	assert dialogo.avisos == [True]


def test_un_paquete_malicioso_no_se_instala_y_se_explica(dialogo, tienda, dicho):
	tienda.publicar(ficha("trampa", "1.0"), {"instalar.exe": b"MZ"})
	dialogo.refrescar()
	_esperar(dialogo)
	dialogo.instalar()
	_esperar(dialogo)
	assert "programa o un guion" in dialogo.estado.GetValue()
	assert not (paths.ruta_complementos() / "trampa").exists()
	assert dialogo.avisos == [] and _filas(dialogo)[0][1] == "Disponible"


def test_detalles_en_un_campo_de_solo_lectura(dialogo, tienda, monkeypatch):
	tienda.publicar(ficha("hogar", "1.0", descripcion="Muebles de casa"), version_minima_app="0.1.0")
	dialogo.refrescar()
	_esperar(dialogo)
	mostrados: list[tuple] = []
	monkeypatch.setattr(
		dialogo_texto, "mostrar_texto", lambda padre, titulo, etiqueta, texto, copiable=False: mostrados.append((titulo, etiqueta, texto))
	)
	dialogo.detalles()
	titulo, etiqueta, texto = mostrados[0]
	assert titulo == "Detalles de «Complemento hogar»" and "&" in etiqueta
	for fragmento in (
		"Identificador: hogar",
		"Estado: Disponible",
		"Autor: Pruebas",
		"Licencia: CC0",
		"objetos.",
		"Muebles de casa",
		"2026-11-26",
	):
		assert fragmento in texto, fragmento


def test_textos_de_tamano():
	assert ui.texto_tamano(0) == ""
	assert ui.texto_tamano(300) == "1 KB"
	assert ui.texto_tamano(350_000) == "342 KB"
	assert ui.texto_tamano(1_300_000) == "1,2 MB"


def test_aviso_en_segundo_plano_de_complementos_con_actualizacion(app_wx, tienda, gestor):
	tienda.publicar(ficha("hogar", "1.0"))
	cel.instalar(tienda.indice().complementos["hogar"])
	avisos: list[int] = []
	tarea = ui.buscar_actualizaciones_en_segundo_plano(avisos.append, gestor)
	assert procesar_eventos(lambda: tarea.terminada, 10)
	procesar_eventos(segundos=0.1)
	assert avisos == []  # todo al día: no molesta
	tienda.publicar(ficha("hogar", "1.1"))
	tarea = ui.buscar_actualizaciones_en_segundo_plano(avisos.append, gestor)
	assert procesar_eventos(lambda: bool(avisos), 10)
	assert avisos == [1]
	assert cel.instalados()["hogar"].version == "1.0"  # avisa, no instala nada
	obtener_configuracion().establecer("complementos.comprobar_actualizaciones", False)
	assert ui.buscar_actualizaciones_en_segundo_plano(avisos.append, gestor) is None
