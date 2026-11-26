"""Pruebas de «Archivo, Exportar» del Estudio (sin mostrar diálogos; todo se escribe en la carpeta de la prueba)."""

from __future__ import annotations

from pathlib import Path

import pytest

wx = pytest.importorskip("wx")

from app.core import tareas  # noqa: E402
from app.core.configuracion import Configuracion  # noqa: E402
from app.dominio import edicion  # noqa: E402
from app.dominio.catalogo import Catalogo  # noqa: E402
from app.dominio.formato import cargar_paquete  # noqa: E402
from app.dominio.modelo import Aviso, Entorno  # noqa: E402
from app.ui import dialogos_exportar as ui  # noqa: E402
from app.ui.accesibilidad.revision_teclado import afirmar_teclado_correcto  # noqa: E402
from app.ui.contexto import ContextoEstudio  # noqa: E402
from app.ui.formulario import DialogoFormulario  # noqa: E402


def _casa(con_error: bool = False) -> Entorno:
	entorno = edicion.crear_entorno("Casa de prueba")
	planta = edicion.crear_planta(entorno, "Planta baja")
	salon = edicion.crear_habitacion_rectangular(entorno, planta, "Salón", 0, 0, 5, 4)
	cocina = edicion.crear_habitacion_adosada(entorno, planta, "Cocina", salon, "este", 3, 4)
	edicion.anadir_puerta_entre(entorno, planta, salon, cocina, estado="abierta")
	# Con el inicio fuera de todos los espacios, la comprobación da un error.
	edicion.fijar_inicio(entorno, planta, 100.0 if con_error else 2.5, 2.0)
	return entorno


@pytest.fixture
def abiertas(monkeypatch) -> list[Path]:
	"""Carpetas que se habrían abierto en el Explorador (en las pruebas no se abre nada)."""
	carpetas: list[Path] = []
	monkeypatch.setattr(ui, "abrir_carpeta", lambda carpeta: carpetas.append(Path(carpeta)) or True)
	return carpetas


@pytest.fixture
def contexto(app_wx, abiertas):
	ctx = ContextoEstudio(ventana=None, configuracion=Configuracion(), catalogo=Catalogo(), tareas=None)
	ctx.abrir_documento(_casa(), actividades=[{"formato": 1, "id": "act-1", "nombre": "Buscar la llave", "tipo": "exploracion"}])
	return ctx


def _elegir_ruta(monkeypatch, ruta: Path) -> None:
	"""Lo que «elige» la persona en los cuadros de Windows de guardar y de carpeta."""
	monkeypatch.setattr(wx.FileDialog, "GetPath", lambda self: str(ruta))
	monkeypatch.setattr(wx.DirDialog, "GetPath", lambda self: str(ruta))


def _cerrar(dialogo) -> int:
	return dialogo.ids_opciones[1]


def test_dialogos_de_exportar_teclado(app_wx):
	final = ui.crear_aviso_final(None, "Exportados 2 ficheros en la carpeta.", "Exportar")
	errores = ui.crear_pregunta_de_errores(None, [Aviso("error", "sin_puerta", "La cocina no tiene puerta.", sugerencia="Añada una.")])
	planos = DialogoFormulario(None, "Exportar el plano", ui.campos_plano())
	try:
		for dialogo in (final, errores, planos):
			afirmar_teclado_correcto(dialogo)
		etiquetas = [hijo.GetLabel() for hijo in errores.GetChildren()[0].GetChildren() if isinstance(hijo, wx.Button)]
		assert etiquetas[:2] == ["&Exportar de todos modos", "&No exportar"]
		assert isinstance(errores.cuerpo, wx.TextCtrl) and not errores.cuerpo.IsEditable(), "los errores se pueden repasar"
	finally:
		for dialogo in (final, errores, planos):
			dialogo.Destroy()


def test_paquete_para_el_alumno_con_actividades_y_recursos(contexto, dialogo_modal, monkeypatch, tmp_path, abiertas):
	contexto.recursos["imagenes/plano.png"] = b"\x89PNG\r\n\x1a\n" + b"0" * 20
	destino = tmp_path / "salida" / "casa-alumno.elab"
	destino.parent.mkdir()
	_elegir_ruta(monkeypatch, destino)
	dialogo_modal.responder(wx.ID_OK, lambda d: d.ids_opciones[0])
	assert ui.exportar(contexto, "paquete") is True
	paquete = cargar_paquete(destino)
	assert paquete.entorno.nombre == "Casa de prueba" and len(paquete.entorno.plantas[0].espacios) == 2
	assert [actividad["id"] for actividad in paquete.actividades] == ["act-1"]
	assert paquete.tiene_recurso("imagenes/plano.png")
	assert abiertas == [destino.parent], "se eligió «Abrir la carpeta»"
	assert contexto.modificado is False and contexto.ruta_paquete is None, "exportar no cambia el documento abierto"


def test_paquete_con_errores_pregunta_y_se_puede_no_exportar(contexto, dialogo_modal, monkeypatch, tmp_path, abiertas):
	contexto.abrir_documento(_casa(con_error=True))
	destino = tmp_path / "con-errores.elab"
	_elegir_ruta(monkeypatch, destino)
	dialogo_modal.responder(lambda d: d.ids_opciones[1])
	assert ui.exportar(contexto, "paquete") is False
	assert not destino.exists()
	assert dialogo_modal.ultimo.titulo == "El entorno tiene errores"
	dialogo_modal.responder(lambda d: d.ids_opciones[0], wx.ID_OK, _cerrar)
	assert ui.exportar(contexto, "paquete") is True
	assert destino.is_file() and abiertas == []


def test_paquete_no_pisa_el_fichero_abierto(contexto, dialogo_modal, monkeypatch, tmp_path):
	abierto = tmp_path / "casa.elab"
	assert contexto.guardar(abierto)
	_elegir_ruta(monkeypatch, abierto)
	assert ui.exportar(contexto, "paquete") is False
	assert "otro nombre" in " ".join(dialogo_modal.ultimo.textos)


@pytest.mark.parametrize(("extension", "marca"), [(".txt", "CASA DE PRUEBA"), (".md", "# "), (".html", "<html")])
def test_descripcion_en_texto_por_extension(contexto, dialogo_modal, monkeypatch, tmp_path, extension, marca):
	destino = tmp_path / f"casa{extension}"
	_elegir_ruta(monkeypatch, destino)
	dialogo_modal.responder(wx.ID_OK, _cerrar)
	assert ui.exportar(contexto, "texto") is True
	contenido = destino.read_text(encoding="utf-8")
	assert marca in contenido and "Salón" in contenido


@pytest.mark.parametrize(("formato", "extensiones"), [("svg", {".svg", ".txt"}), ("tactil", {".svg", ".txt", ".brf"})])
def test_planos_svg_en_la_carpeta_elegida(contexto, dialogo_modal, tmp_path, formato, extensiones):
	carpeta = tmp_path / "planos"
	dialogo_modal.responder(lambda d: (d.fijar({"carpeta": str(carpeta), "pagina": "A3"}), wx.ID_OK)[1], _cerrar)
	assert ui.exportar(contexto, formato) is True
	assert {ruta.suffix for ruta in carpeta.iterdir()} == extensiones
	assert "<svg" in next(carpeta.glob("*.svg")).read_text(encoding="utf-8")


@pytest.mark.parametrize(("formato", "extension"), [("geojson", ".geojson"), ("dxf", ".dxf")])
def test_geojson_y_dxf_un_fichero_por_planta(contexto, dialogo_modal, monkeypatch, tmp_path, formato, extension):
	_elegir_ruta(monkeypatch, tmp_path)
	dialogo_modal.responder(wx.ID_OK, _cerrar)
	assert ui.exportar(contexto, formato) is True
	assert len(list(tmp_path.glob(f"*{extension}"))) == 1


def test_cancelar_el_destino_no_escribe_nada(contexto, dialogo_modal, tmp_path, monkeypatch):
	_elegir_ruta(monkeypatch, tmp_path / "nada.txt")
	for formato in ("texto", "geojson", "svg"):
		dialogo_modal.responder(wx.ID_CANCEL)
		assert ui.exportar(contexto, formato) is False
	assert [ruta.name for ruta in tmp_path.iterdir() if ruta.name != "data"] == []


def test_sin_entorno_abierto_se_explica(contexto, dialogo_modal):
	contexto.cerrar_documento()
	assert ui.exportar(contexto, "dxf") is False
	assert "ningún entorno" in " ".join(dialogo_modal.ultimo.textos)
	with pytest.raises(ValueError):
		ui.exportar(contexto, "pdf")


def test_exportar_con_gestor_de_tareas_no_bloquea_y_anuncia(contexto, dialogo_modal, monkeypatch, tmp_path, voz_simulada):
	gestor = tareas.GestorTareas(max_hilos=1, nombre="prueba", prioridad_baja=False)
	contexto.tareas = gestor
	try:
		_elegir_ruta(monkeypatch, tmp_path)
		dialogo_modal.responder(wx.ID_OK, wx.ID_OK, _cerrar)
		assert ui.exportar(contexto, "geojson") is True
	finally:
		gestor.apagar(1.0)
	assert len(list(tmp_path.glob("*.geojson"))) == 1
	assert voz_simulada.contiene("Exportado 1 fichero")


def test_fallo_al_escribir_se_explica(contexto, dialogo_modal, monkeypatch, tmp_path):
	def falla(*_a, **_k):
		raise OSError("disco lleno")

	monkeypatch.setattr(ui, "escribir", falla)
	_elegir_ruta(monkeypatch, tmp_path)
	assert ui.exportar(contexto, "dxf") is False
	assert "disco lleno" in " ".join(dialogo_modal.ultimo.textos)
