"""Remates de la integración en la interfaz del Estudio y en la ayuda de Jugar.

- Los temporizadores de una ventana se paran al destruirla, también cuando la
  destruye su padre (la guarda compara el id: ``GetEventObject() is self`` no
  sirve en wxPython 4.3).
- «Insertar objeto» busca con ``Catalogo.buscar_avanzado`` y ofrece los filtros
  de lugar, estancia, función, obstáculo y riesgo con el catálogo real.
- «Amueblar el espacio» ofrece todos los usos del dominio.
- «Generar paquete de diagnóstico» en Ayuda del Estudio y en la ayuda de Jugar.
"""

from __future__ import annotations

import time
import zipfile
from pathlib import Path

import pytest

wx = pytest.importorskip("wx")

from app.core import paths, registro  # noqa: E402
from app.core.config import Configuracion  # noqa: E402
from app.dominio import colocacion  # noqa: E402
from app.dominio.catalogo import Catalogo  # noqa: E402
from app.ui import dialogo_catalogo as dc  # noqa: E402
from app.ui import dialogos_herramientas, menus  # noqa: E402
from app.ui.accesibilidad.revision_teclado import afirmar_teclado_correcto  # noqa: E402
from app.ui.contexto import ContextoEstudio  # noqa: E402
from tests._ui_estudio_util import boton, cerrar_ventana, crear_ventana, orden  # noqa: E402
from tests.conftest import RAIZ, procesar_eventos  # noqa: E402
from tests.test_dominio_comun import catalogo_de_prueba  # noqa: E402

PLUGINS = RAIZ / "data" / "plugins"


# ── Temporizadores que no sobreviven a su ventana ────────────────────────────


def test_el_catalogo_destruido_por_su_padre_para_sus_temporizadores(app_wx, tmp_path):
	"""Sin llamar a ``Destroy`` del diálogo: lo destruye el marco, y la guarda por id lo para."""
	catalogo = catalogo_de_prueba(tmp_path)
	marco = wx.Frame(None)
	dialogo = dc.DialogoCatalogo(marco, catalogo, None, ContextoEstudio(ventana=marco, catalogo=catalogo))
	temporizadores = [dialogo._temporizador, dialogo._temporizador_miniatura]
	try:
		for temporizador in temporizadores:
			temporizador.StartOnce(5000)
		marco.Destroy()
		procesar_eventos(lambda: not dialogo and not marco, 2)
		assert not dialogo
		assert not [t for t in temporizadores if t.IsRunning()], "un temporizador sigue en marcha con el diálogo liberado"
	finally:
		for temporizador in temporizadores:
			temporizador.Stop()


def test_el_destroy_de_un_hijo_no_para_los_temporizadores_del_catalogo(app_wx, tmp_path):
	"""El EVT_WINDOW_DESTROY de un control hijo sube hasta el diálogo: no debe confundirse con el suyo."""
	catalogo = catalogo_de_prueba(tmp_path)
	dialogo = dc.DialogoCatalogo(None, catalogo)
	try:
		dialogo._temporizador.StartOnce(5000)
		hijo = wx.Button(dialogo, label="x")
		hijo.Destroy()
		procesar_eventos(lambda: not hijo, 2)
		assert dialogo._temporizador.IsRunning()
	finally:
		dialogo.Destroy()
	assert not dialogo._temporizador.IsRunning()


def test_complementos_y_progreso_paran_su_temporizador(app_wx, tmp_path):
	from app.ui import dialogo_complementos as dcomp
	from app.ui.accesibilidad.progreso import IndicadorProgreso

	contexto = ContextoEstudio(None, Configuracion(), catalogo_de_prueba(tmp_path))
	marco = wx.Frame(None)
	dialogo = dcomp.DialogoComplementos(marco, contexto)
	indicador = IndicadorProgreso(marco, anunciar=False)
	temporizadores = [dialogo._temporizador, indicador._pulso]
	try:
		dialogo._temporizador.StartOnce(5000)
		indicador.fase("Trabajando", indeterminado=True)
		assert all(t.IsRunning() for t in temporizadores)
		marco.Destroy()
		procesar_eventos(lambda: not marco and not dialogo and not indicador, 2)
		assert not [t for t in temporizadores if t.IsRunning()]
	finally:
		for temporizador in temporizadores:
			temporizador.Stop()
	# Y con Destroy directo.
	otro = IndicadorProgreso(wx.Frame(None), anunciar=False)
	pulso = otro._pulso
	padre = otro.GetParent()
	otro.fase("Otra vez", indeterminado=True)
	otro.Destroy()
	assert not pulso.IsRunning()
	padre.Destroy()


# ── Catálogo ampliado ────────────────────────────────────────────────────────


def test_amueblar_ofrece_todos_los_usos_del_dominio():
	claves = [clave for clave, _nombre in dialogos_herramientas.usos()]
	assert claves == list(colocacion.NOMBRES_USOS)
	assert len(claves) >= 21 and {"dormitorio", "salon", "cocina", "bano", "aula", "oficina"} <= set(claves)
	assert not hasattr(dialogos_herramientas, "USOS"), "no debe quedar una lista propia que se quede atrás"


@pytest.fixture(scope="module")
def catalogo_real():
	if not (PLUGINS / "comun" / "complemento.json").is_file():
		pytest.skip("no está el catálogo de serie en data/plugins")
	return Catalogo.cargar(PLUGINS)


@pytest.mark.lento
def test_insertar_objeto_con_el_catalogo_real(app_wx, catalogo_real, monkeypatch, data_temporal):
	"""Abrir, filtrar y buscar entre los más de dos mil objetos de serie, con el buscador del dominio y en poco tiempo."""
	total = len(catalogo_real.objetos())
	assert total > 2000
	llamadas: list[dict] = []
	original = catalogo_real.buscar_avanzado

	def espia(texto: str = "", **filtros):
		llamadas.append({"texto": texto, **filtros})
		return original(texto, **filtros)

	monkeypatch.setattr(catalogo_real, "buscar_avanzado", espia)
	inicio = time.perf_counter()
	dialogo = dc.DialogoCatalogo(None, catalogo_real)
	abrir = time.perf_counter() - inicio
	try:
		assert dialogo.lista.GetItemCount() == total
		assert llamadas, "el diálogo no ha buscado con Catalogo.buscar_avanzado"
		assert {"lugar", "estancia", "funcion", "obstaculo", "riesgo"} <= set(dialogo.elecciones_faceta)
		afirmar_teclado_correcto(dialogo, teclas_propias=["Ctrl+D"])
		for eleccion in dialogo.elecciones_faceta.values():
			hermanos = list(eleccion.GetParent().GetChildren())
			etiqueta = hermanos[hermanos.index(eleccion) - 1]
			assert isinstance(etiqueta, wx.StaticText) and "&" in etiqueta.GetLabel()
		# El árbol es el del dominio (complemento → categoría → subcategoría), sin «comun», que no tiene objetos.
		assert ("comp", "hogar") in dialogo._nodos and ("comp", "comun") not in dialogo._nodos
		tiempos: list[float] = []
		casos: list[tuple[str, dict]] = [("silla", {}), ("mesa de cocina", {})]
		for faceta in ("lugar", "estancia", "funcion", "obstaculo", "riesgo"):
			valor = dialogo._claves_faceta[faceta][1]
			casos.append(("", {faceta: valor}))
		for texto, filtros in casos:
			llamadas.clear()
			libres = {faceta: dc.TODOS for faceta in dialogo.elecciones_faceta}
			libres.update(filtros)
			inicio = time.perf_counter()
			cantidad = dialogo.filtrar(texto, anunciar=False, **libres)
			tiempos.append(time.perf_counter() - inicio)
			assert 0 < cantidad < total, (texto, filtros, cantidad)
			assert llamadas and llamadas[-1]["texto"] == texto
			for faceta, valor in filtros.items():
				assert llamadas[-1][faceta] == valor
			esperados = [d.tipo for d in original(texto, **filtros)]
			assert [d.tipo for d in dialogo._definiciones] == esperados, "el orden es el de buscar_avanzado"
		# Un nodo del árbol pasa al dominio su complemento y su categoría.
		dialogo.filtrar("", anunciar=False, **{faceta: dc.TODOS for faceta in dialogo.elecciones_faceta})
		assert dialogo.elegir_nodo("comp", "hogar")
		assert llamadas[-1]["complemento"] == "hogar"
		assert dialogo.lista.GetItemCount() == len(catalogo_real.complemento("hogar").objetos)
	finally:
		dialogo.Destroy()
	assert abrir < 5.0, f"abrir el catálogo tarda {abrir:.2f} s"
	assert max(tiempos) < 1.0, f"filtrar tarda hasta {max(tiempos):.2f} s"


def test_el_catalogo_sin_buscador_del_dominio_sigue_funcionando(app_wx, tmp_path):
	"""Si ``buscar_avanzado`` falla, el diálogo busca por su cuenta y no se cae."""
	catalogo = catalogo_de_prueba(tmp_path)

	def roto(*_a, **_k):
		raise RuntimeError("roto")

	catalogo.buscar_avanzado = roto
	dialogo = dc.DialogoCatalogo(None, catalogo)
	try:
		assert dialogo.filtrar("sofa", anunciar=False) == 2
	finally:
		dialogo.Destroy()


# ── Paquete de diagnóstico ───────────────────────────────────────────────────


def _registros_de_prueba(monkeypatch: pytest.MonkeyPatch) -> Path:
	"""Un registro con una ruta personal, y datos privados que NO deben viajar.

	La carpeta de registros activa es estado global del módulo de registro: si
	otra prueba anterior configuró el registro en su propia carpeta, el paquete
	saldría de allí. Se fija la de esta prueba para que no dependa del orden.
	"""
	carpeta = paths.ruta_registros()
	monkeypatch.setattr(registro, "carpeta_registros", lambda: carpeta)
	carpeta.mkdir(parents=True, exist_ok=True)
	# Cuenta ficticia (no es la de nadie): por eso la deja pasar tools/comprobar_rutas.py.
	ficticia = "C:\\Users\\Pepe\\Documents\\casa.elab"  # comprobar_rutas: permitido
	(carpeta / "sesion_20260101_000000.log").write_text(f"Abierto {ficticia}\n", encoding="utf-8")
	datos = paths.ruta_datos()
	for relativo in ("config/config.json", "sessions/s1.json.gz", "entornos/casa.elab", "db/alumnos.db"):
		(datos / relativo).parent.mkdir(parents=True, exist_ok=True)
		(datos / relativo).write_text("privado", encoding="utf-8")
	return carpeta


def _comprobar_paquete(ruta: Path) -> None:
	assert ruta.is_file() and ruta.parent.name == "diagnostico"
	with zipfile.ZipFile(ruta) as zip_:
		nombres = zip_.namelist()
		assert "sistema.txt" in nombres and "logs/sesion_20260101_000000.log" in nombres
		assert all(nombre == "sistema.txt" or nombre.startswith("logs/") for nombre in nombres), nombres
		texto = zip_.read("logs/sesion_20260101_000000.log").decode("utf-8")
	assert "Pepe" not in texto and "<usuario>" in texto


def test_menu_ayuda_tiene_el_paquete_de_diagnostico():
	ayuda = next(entradas for titulo, entradas in menus.MENUS if titulo == "Ay&uda")
	entrada = next(e for e in ayuda if e and e[0] == "paquete_diagnostico")
	assert "&d" in entrada[1] and "\t" not in entrada[1], "letra de acceso propia y sin atajo"
	letras = [menus.normalizar_entrada(e)[1].split("&")[1][0].lower() for e in ayuda if e and not menus.es_submenu(e)]
	assert len(letras) == len(set(letras)), letras


@pytest.mark.lento
def test_estudio_genera_el_paquete_y_ofrece_abrir_la_carpeta(app_wx, monkeypatch, data_temporal, dialogo_modal, tmp_path):
	_registros_de_prueba(monkeypatch)
	ventana = crear_ventana(monkeypatch, catalogo_de_prueba(tmp_path))
	abiertas: list[Path] = []
	monkeypatch.setattr(ventana, "_abrir_carpeta", abiertas.append)
	try:
		dialogo_modal.responder(boton(0))
		orden(ventana, "paquete_diagnostico")
		assert procesar_eventos(lambda: ventana.ultimo_paquete_diagnostico is not None, 15) is not False
		ruta = ventana.ultimo_paquete_diagnostico
		assert ruta is not None
		_comprobar_paquete(ruta)
		mostrado = dialogo_modal.mostrados[-1]
		assert ruta.name in " ".join([mostrado.mensaje, *mostrado.textos])
		assert abiertas == [ruta.parent]
	finally:
		cerrar_ventana(ventana)


@pytest.mark.lento
def test_jugar_genera_el_paquete_desde_la_ayuda(data_temporal, monkeypatch):
	from app.entrada import acciones
	from app.reproductor.pantallas import ayuda
	from tests.test_reproductor_comun import Robot, crear_app

	_registros_de_prueba(monkeypatch)
	app = crear_app("--alumno", "Luna")
	try:
		robot = Robot(app)
		ayuda.abrir_ayuda(app, acciones.MENU)
		robot.esperar(2)
		assert "Generar paquete de diagnóstico" in robot.opciones()
		marca = robot.marca()
		robot.elegir("Generar paquete de diagnóstico")
		# Comprimir los registros va en un hilo; con el equipo cargado (otras pruebas a la vez) tarda más de 15 s.
		limite = time.monotonic() + 60
		while app.ultimo_paquete_diagnostico is None and time.monotonic() < limite:
			robot.esperar(1)
		ruta = app.ultimo_paquete_diagnostico
		assert ruta is not None
		_comprobar_paquete(ruta)
		dicho = robot.dicho(marca)
		assert "Generando el paquete de diagnóstico" in dicho and ruta.name in dicho
		assert app.fallos == 0
	finally:
		app.cerrar_todo()
