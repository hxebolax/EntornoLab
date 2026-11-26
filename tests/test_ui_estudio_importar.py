"""Pruebas de los diálogos de importar del Estudio (sin mostrarlos; nunca un modal real ni red)."""

from __future__ import annotations

import json
import struct
import zlib
from pathlib import Path

import pytest

wx = pytest.importorskip("wx")

from app.core import tareas  # noqa: E402
from app.core.configuracion import Configuracion  # noqa: E402
from app.dominio import edicion  # noqa: E402
from app.dominio.catalogo import Catalogo  # noqa: E402
from app.dominio.modelo import Entorno  # noqa: E402
from app.importar import imagen as importar_imagen  # noqa: E402
from app.importar import osm  # noqa: E402
from app.ui import dialogo_progreso  # noqa: E402
from app.ui import dialogos_importar as ui  # noqa: E402
from app.ui.accesibilidad.revision_teclado import afirmar_teclado_correcto  # noqa: E402
from app.ui.contexto import ContextoEstudio  # noqa: E402
from app.ui.formulario import DialogoFormulario  # noqa: E402
from tests.conftest import procesar_eventos  # noqa: E402

DATOS = Path(__file__).parent / "datos"


class VentanaFalsa:
	"""Lo que los diálogos usan de la ventana principal: adoptar un borrador y la barra de estado."""

	def __init__(self, aceptar: bool = True) -> None:
		self.borradores: list[tuple[Entorno, str, dict | None]] = []
		self.estados: list[str] = []
		self._aceptar = aceptar

	def adoptar_borrador(self, entorno: Entorno, nombre: str, recursos: dict[str, bytes] | None = None) -> bool:
		self.borradores.append((entorno, nombre, recursos))
		return self._aceptar

	def SetStatusText(self, texto: str) -> None:  # noqa: N802 - mismo nombre que wx.Frame
		self.estados.append(texto)


class ContextoPrueba(ContextoEstudio):
	"""Contexto con ventana falsa: los diálogos se crean sin padre."""

	def __init__(self, gestor: tareas.GestorTareas | None = None) -> None:
		self.falsa = VentanaFalsa()
		super().__init__(ventana=self.falsa, configuracion=Configuracion(), catalogo=Catalogo(), tareas=gestor)


@pytest.fixture
def gestor():
	instancia = tareas.GestorTareas(max_hilos=1, nombre="prueba", prioridad_baja=False)
	yield instancia
	instancia.apagar(1.0)


@pytest.fixture
def contexto(app_wx, gestor):
	return ContextoPrueba(gestor)


def _crear(clase, ctx, *argumentos, **opciones):
	"""Crea un diálogo con padre None aunque el contexto tenga una ventana falsa."""
	return clase(None, ctx, *argumentos, **opciones)


def _esperar(dialogo, segundos: float = 20) -> None:
	assert procesar_eventos(lambda: not dialogo.trabajando(), segundos), "la tarea no terminó"
	procesar_eventos(segundos=0.05)


def _casa() -> Entorno:
	entorno = edicion.crear_entorno("Casa")
	planta = edicion.crear_planta(entorno, "Planta baja")
	edicion.crear_habitacion_rectangular(entorno, planta, "Salón", 0, 0, 5, 4)
	return entorno


def _png(ruta: Path) -> Path:
	"""Escribe un PNG válido de 1×1."""

	def trozo(tipo: bytes, datos: bytes) -> bytes:
		return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)

	contenido = b"\x89PNG\r\n\x1a\n" + trozo(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
	contenido += trozo(b"IDAT", zlib.compress(b"\x00\xff\xff\xff")) + trozo(b"IEND", b"")
	ruta.write_bytes(contenido)
	return ruta


# ── Informe y privacidad ─────────────────────────────────────────────────────


def test_dialogo_informe_teclado_y_solo_lectura(app_wx):
	for con_decision in (True, False):
		dialogo = ui.DialogoInforme(None, "Informe", "Importado:\n- 3 calles", con_decision)
		try:
			afirmar_teclado_correcto(dialogo)
			assert dialogo.campo.IsMultiLine() and not dialogo.campo.IsEditable()
			assert dialogo.GetEscapeId() == wx.ID_CANCEL
			etiquetas = {hijo.GetLabel() for hijo in dialogo.GetChildren() if isinstance(hijo, wx.Button)}
			assert etiquetas == ({"&Usar este borrador", "&Descartar"} if con_decision else {"C&errar"})
		finally:
			dialogo.Destroy()


def test_aviso_de_privacidad_dice_que_sale_y_sus_botones_dicen_la_accion(app_wx):
	dialogo = ui.crear_aviso_privacidad(None)
	try:
		afirmar_teclado_correcto(dialogo)
		etiquetas = [hijo.GetLabel() for hijo in dialogo.GetChildren()[0].GetChildren() if isinstance(hijo, wx.Button)]
		assert etiquetas[:2] == ["C&onectar", "&No conectar"]
		texto = ui.texto_aviso_privacidad()
		assert "coordenadas" in texto and "alumnos" in texto and "ODbL" in texto
	finally:
		dialogo.Destroy()


def test_permiso_de_conexion_se_pregunta_una_vez_y_se_recuerda(app_wx, dialogo_modal):
	config = Configuracion()
	dialogo_modal.responder(lambda d: d.ids_opciones[1])
	assert ui.permiso_de_conexion(None, config) is False
	assert config.obtener("importar.aviso_privacidad_visto") is False
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	assert ui.permiso_de_conexion(None, config) is True
	assert Configuracion().obtener("importar.aviso_privacidad_visto") is True
	mostrados = len(dialogo_modal.mostrados)
	assert ui.permiso_de_conexion(None, config) is True
	assert len(dialogo_modal.mostrados) == mostrados, "la segunda vez ya no se pregunta"


# ── OpenStreetMap ────────────────────────────────────────────────────────────


def test_dialogo_osm_teclado(contexto):
	dialogo = _crear(ui.DialogoOSM, contexto)
	try:
		afirmar_teclado_correcto(dialogo)
		assert dialogo.GetEscapeId() == wx.ID_CANCEL
		assert dialogo.radio.GetValue() == "150"
		assert not isinstance(dialogo.radio, wx.SpinCtrlDouble)
	finally:
		dialogo.Destroy()


def test_osm_desde_fichero_sin_red_hasta_el_borrador(contexto, dialogo_modal, sin_red):
	dialogo = _crear(ui.DialogoOSM, contexto)
	try:
		dialogo.fijar(nombre="Cruce de prueba")
		dialogo.importar_fichero(DATOS / "cruce.osm.json")
		_esperar(dialogo)
		assert dialogo.ultimo_error == ""
		assert dialogo.creado is True
		informe = next(m for m in dialogo_modal.mostrados if m.clase == "DialogoInforme")
		assert any("OpenStreetMap" in texto for texto in informe.textos), "el informe lleva la atribución"
	finally:
		dialogo.Destroy()
	entorno, nombre, _recursos = contexto.falsa.borradores[0]
	assert nombre == "Cruce de prueba"
	assert entorno.plantas and entorno.plantas[0].exterior and entorno.georef


def test_osm_descartar_el_borrador_no_abre_nada(contexto, dialogo_modal):
	dialogo = _crear(ui.DialogoOSM, contexto)
	try:
		dialogo_modal.responder(wx.ID_CANCEL)
		dialogo.importar_fichero(DATOS / "cruce.osm.json")
		_esperar(dialogo)
		assert dialogo.resultado is not None and dialogo.creado is False
	finally:
		dialogo.Destroy()
	assert contexto.falsa.borradores == []


def test_osm_en_linea_con_descarga_simulada_y_aviso_previo(contexto, dialogo_modal):
	mapa = json.loads((DATOS / "cruce.osm.json").read_text(encoding="utf-8"))
	llamadas: list[str] = []

	def descargar(url: str, datos: bytes | None = None) -> bytes:
		llamadas.append(url)
		if "nominatim" in url:
			lugar = {"display_name": "Cruce de prueba, Ciudad", "name": "Cruce de prueba", "lat": "40.0", "lon": "-3.7", "type": "crossing"}
			return json.dumps([lugar]).encode("utf-8")
		return json.dumps({"elements": mapa["elements"]}).encode("utf-8")

	dialogo = _crear(ui.DialogoOSM, contexto, descargar=descargar)
	try:
		# Primera conexión: se pregunta, y si se dice que no, no se conecta.
		dialogo.fijar(buscar="Cruce de prueba")
		dialogo_modal.responder(lambda d: d.ids_opciones[1])
		dialogo.buscar()
		assert not dialogo.trabajando() and llamadas == []
		dialogo_modal.responder(lambda d: d.ids_opciones[0])
		dialogo.buscar()
		_esperar(dialogo)
		assert len(dialogo.candidatos) == 1 and dialogo.lista.numero_filas() == 1
		assert dialogo.latitud.GetValue() == "40" and dialogo.longitud.GetValue() == "-3,7"
		assert dialogo.lista.GetFocusedItem() == 0, "la lista con filas tiene una enfocada"
		dialogo.fijar(radio="80")
		dialogo.importar_en_linea()
		_esperar(dialogo)
		assert dialogo.ultimo_error == "" and dialogo.creado is True
	finally:
		dialogo.Destroy()
	assert len(llamadas) >= 2
	assert contexto.falsa.borradores[0][0].plantas[0].exterior


def test_osm_valida_radio_y_coordenadas_con_el_foco_en_el_campo(contexto, dialogo_modal):
	contexto.configuracion.establecer("importar.aviso_privacidad_visto", True)
	dialogo = _crear(ui.DialogoOSM, contexto, descargar=lambda url, datos=None: b"")
	try:
		dialogo.fijar(latitud="40", longitud="-3,7", radio="5000")
		dialogo.importar_en_linea()
		assert not dialogo.trabajando()
		assert "Radio" in dialogo.ultimo_error and "400" in dialogo.ultimo_error
		dialogo.fijar(latitud="norte", radio="100")
		dialogo.importar_en_linea()
		assert "Latitud" in dialogo.ultimo_error
	finally:
		dialogo.Destroy()


def test_osm_fichero_que_no_sirve_explica_el_error(contexto, dialogo_modal, tmp_path):
	malo = tmp_path / "vacio.json"
	malo.write_text("{}", encoding="utf-8")
	dialogo = _crear(ui.DialogoOSM, contexto)
	try:
		dialogo.importar_fichero(malo)
		_esperar(dialogo)
		assert dialogo.creado is False and dialogo.ultimo_error
		assert dialogo.progreso.estado.GetValue() == dialogo.ultimo_error
	finally:
		dialogo.Destroy()


def test_osm_cancelar_detiene_la_tarea_y_lo_dice(contexto, dialogo_modal, monkeypatch):
	def lento(datos, opciones=None, progreso=None, cancelado=None):
		for _vuelta in range(400):
			if cancelado():
				raise ui.ImportacionCancelada("cancelada")
			import time

			time.sleep(0.01)
		raise AssertionError("no se canceló")

	monkeypatch.setattr(osm, "convertir", lento)
	dialogo = _crear(ui.DialogoOSM, contexto)
	try:
		dialogo.importar_fichero(DATOS / "cruce.osm.json")
		assert procesar_eventos(lambda: dialogo.progreso.boton_cancelar.IsEnabled(), 5)
		assert not dialogo.boton_importar.IsEnabled()
		dialogo.progreso.cancelar()
		assert dialogo.progreso.texto_estado == "Cancelando..."
		_esperar(dialogo)
		assert dialogo.creado is False and dialogo.ultimo_error == ""
		assert "cancelada" in dialogo.progreso.estado.GetValue().lower()
		assert dialogo.boton_importar.IsEnabled()
	finally:
		dialogo.Destroy()


def test_progreso_por_hitos_no_dice_cada_porcentaje(app_wx, marco, voz_simulada):
	voz_simulada.parchear("app.core.voz.hablar")
	config = Configuracion()
	panel = dialogo_progreso.PanelProgreso(marco, None, config)
	for hecho in range(0, 100, 5):
		panel._al_progresar(tareas.Progreso(hecho, 100, "Convirtiendo."))
	assert len(voz_simulada.textos) == 3, voz_simulada.textos
	voz_simulada.limpiar()
	config.establecer("accesibilidad.anunciar_progreso", False)
	mudo = dialogo_progreso.PanelProgreso(marco, None, config)
	for hecho in range(0, 100, 5):
		mudo._al_progresar(tareas.Progreso(hecho, 100, "Convirtiendo."))
	assert voz_simulada.textos == [] and mudo.estado.GetValue(), "sin voz, el estado sigue escrito"


# ── Planos DXF y SVG ─────────────────────────────────────────────────────────


@pytest.mark.parametrize("formato", ["dxf", "svg"])
def test_dialogo_plano_teclado(contexto, formato):
	contexto.abrir_documento(_casa())
	dialogo = _crear(ui.DialogoPlano, contexto, formato)
	try:
		afirmar_teclado_correcto(dialogo)
		assert dialogo.destino.GetCount() == 2
		assert not dialogo.boton_importar.IsEnabled(), "sin plano leído no se puede importar"
	finally:
		dialogo.Destroy()


def test_dxf_capas_escala_y_borrador_nuevo(contexto, dialogo_modal):
	dialogo = _crear(ui.DialogoPlano, contexto, "dxf")
	try:
		dialogo.cargar(DATOS / "planta.dxf")
		_esperar(dialogo)
		assert {capa.nombre for capa in dialogo.capas} == {"MUROS", "PUERTAS", "TEXTOS", "MOBILIARIO"}
		assert dialogo.usos["MUROS"] == "paredes" and dialogo.usos["MOBILIARIO"] == "ignorar"
		assert dialogo.lista.numero_filas() == 4 and dialogo.lista.GetFocusedItem() >= 0
		assert dialogo.propuesta.GetValue()
		assert dialogo.escala.GetValue() == "0,001", "el DXF de prueba declara milímetros"
		fila = [capa.nombre for capa in dialogo.capas].index("MOBILIARIO")
		dialogo.fijar_uso("MOBILIARIO", "paredes")
		assert dialogo.lista.texto_celda(fila, 1) == "Paredes"
		dialogo.fijar_uso("MOBILIARIO", "ignorar")
		dialogo.fijar(nombre="Piso de prueba")
		dialogo.importar()
		_esperar(dialogo)
		assert dialogo.ultimo_error == "" and dialogo.creado is True
	finally:
		dialogo.Destroy()
	entorno, nombre, _recursos = contexto.falsa.borradores[0]
	assert nombre == "Piso de prueba"
	planta = entorno.plantas[0]
	assert len(entorno.plantas) == 1 and {espacio.nombre for espacio in planta.espacios} == {"Cocina", "Salon comedor"}
	assert len(planta.paredes) == 2 and len(planta.aberturas) == 1, "mismas capas que propone el programa: mismo resultado"


def test_svg_exige_la_escala_y_convierte_con_ella(contexto, dialogo_modal):
	dialogo = _crear(ui.DialogoPlano, contexto, "svg")
	try:
		dialogo.cargar(DATOS / "planta.svg")
		_esperar(dialogo)
		assert dialogo.capas
		dialogo.importar()
		assert not dialogo.trabajando() and "escala" in dialogo.ultimo_error.lower()
		dialogo.fijar(escala="0,1")
		dialogo.importar()
		_esperar(dialogo)
		assert dialogo.ultimo_error == "" and dialogo.creado is True
	finally:
		dialogo.Destroy()
	entorno = contexto.falsa.borradores[0][0]
	nombres = {espacio.nombre for espacio in entorno.plantas[0].espacios}
	assert {"Cocina", "Pasillo"} <= nombres


def test_plano_como_planta_nueva_del_entorno_abierto_se_puede_deshacer(contexto, dialogo_modal):
	contexto.abrir_documento(_casa())
	original = contexto.entorno
	dialogo = _crear(ui.DialogoPlano, contexto, "dxf")
	try:
		dialogo.cargar(DATOS / "planta.dxf")
		_esperar(dialogo)
		dialogo.fijar(destino="planta", nivel="1", nombre_planta="Primera")
		dialogo.importar()
		_esperar(dialogo)
		assert dialogo.ultimo_error == "" and dialogo.creado is True
	finally:
		dialogo.Destroy()
	assert contexto.falsa.borradores == [], "no se abre un documento nuevo"
	assert contexto.entorno is original, "el entorno abierto se cambia en el sitio, dentro de ejecutar"
	assert [planta.nombre for planta in contexto.entorno.plantas] == ["Planta baja", "Primera"]
	nueva = contexto.entorno.plantas[1]
	assert nueva.nivel == 1 and nueva.espacios and contexto.planta_id == nueva.id
	ids = contexto.entorno.ids()
	assert len(ids) == len(set(ids)), "ningún id repetido tras añadir la planta"
	assert contexto.modificado and "importar la planta" in contexto.historial.texto_deshacer()
	contexto.deshacer()
	assert len(contexto.entorno.plantas) == 1


# ── Imagen de fondo ──────────────────────────────────────────────────────────


def _valores_imagen(ruta: Path, planta: str) -> dict:
	return {
		"fichero": str(ruta),
		"planta": planta,
		"px1": 0,
		"py1": 0,
		"mx1": 0,
		"my1": 4,
		"px2": 100,
		"py2": 80,
		"mx2": 5,
		"my2": 0,
		"opacidad": 40,
	}


def test_formulario_de_imagen_de_fondo_teclado(contexto):
	contexto.abrir_documento(_casa())
	dialogo = DialogoFormulario(None, "Imagen de fondo", ui.campos_imagen_fondo(contexto))
	try:
		afirmar_teclado_correcto(dialogo)
		assert isinstance(dialogo.formulario.controles["opacidad"], wx.Slider)
	finally:
		dialogo.Destroy()


def test_imagen_de_fondo_queda_en_la_procedencia_y_en_los_recursos(contexto, tmp_path):
	contexto.abrir_documento(_casa())
	planta = contexto.entorno.plantas[0].id
	ruta = _png(tmp_path / "plano.png")
	fondo = ui.aplicar_imagen_fondo(contexto, _valores_imagen(ruta, planta))
	fondos = contexto.entorno.procedencia["fondos"]
	assert len(fondos) == 1 and fondos[0]["planta"] == planta and fondos[0]["opacidad"] == pytest.approx(0.4)
	assert fondo["imagen"] in contexto.recursos and contexto.recursos[fondo["imagen"]] == ruta.read_bytes()
	assert importar_imagen.imagen_a_mundo(fondos[0], 100, 80) == pytest.approx((5.0, 0.0))
	assert contexto.modificado and contexto.historial.puede_deshacer


def test_imagen_de_fondo_con_puntos_iguales_no_cambia_nada(contexto, tmp_path, dialogo_modal):
	contexto.abrir_documento(_casa())
	planta = contexto.entorno.plantas[0].id
	valores = _valores_imagen(_png(tmp_path / "plano.png"), planta)
	valores.update(px2=0, py2=0)
	with pytest.raises(ui.ErrorCampo):
		ui.aplicar_imagen_fondo(contexto, valores)
	assert "fondos" not in contexto.entorno.procedencia or not contexto.entorno.procedencia["fondos"]
	assert not contexto.historial.puede_deshacer and contexto.recursos == {}
	valores["fichero"] = str(tmp_path / "programa.exe")
	(tmp_path / "programa.exe").write_bytes(b"MZ")
	with pytest.raises(ui.ErrorCampo) as error:
		ui.aplicar_imagen_fondo(contexto, valores)
	assert error.value.clave == "fichero"


def test_importar_imagen_de_fondo_con_el_dialogo(contexto, tmp_path, dialogo_modal, monkeypatch):
	contexto.abrir_documento(_casa())
	monkeypatch.setattr(contexto, "ventana", None)
	planta = contexto.entorno.plantas[0].id
	valores = _valores_imagen(_png(tmp_path / "plano.png"), planta)
	dialogo_modal.responder(lambda d: (d.fijar(valores), wx.ID_OK)[1])
	assert ui.importar_imagen_fondo(contexto) is True
	assert contexto.entorno.procedencia["fondos"]
	dialogo_modal.responder(wx.ID_CANCEL)
	assert ui.importar_imagen_fondo(contexto) is False


# ── GPX ──────────────────────────────────────────────────────────────────────


def _exterior() -> Entorno:
	return osm.convertir(osm.importar_fichero_osm(DATOS / "cruce.osm.json")).entorno


def test_gpx_sobre_un_exterior_georreferenciado(contexto, dialogo_modal, monkeypatch):
	contexto.abrir_documento(_exterior())
	monkeypatch.setattr(contexto, "ventana", None)
	planta = contexto.entorno.plantas[0]
	antes = len(planta.referencias)
	formulario = DialogoFormulario(None, "Ruta", ui.campos_gpx(contexto))
	try:
		afirmar_teclado_correcto(formulario)
	finally:
		formulario.Destroy()
	dialogo_modal.responder(
		lambda d: (d.fijar({"fichero": str(DATOS / "ruta.gpx"), "planta": planta.id, "referencias": True}), wx.ID_OK)[1]
	)
	assert ui.importar_gpx(contexto) is True
	planta = contexto.entorno.plantas[0]
	assert len(planta.referencias) > antes
	assert contexto.entorno.procedencia.get("rutas")
	assert any(m.clase == "DialogoInforme" for m in dialogo_modal.mostrados), "se enseña el informe"
	assert "importar la ruta" in contexto.historial.texto_deshacer()


def test_gpx_sin_georreferencia_se_explica_y_no_se_hace(contexto, dialogo_modal, monkeypatch):
	contexto.abrir_documento(_casa())
	monkeypatch.setattr(contexto, "ventana", None)
	assert ui.importar_gpx(contexto) is False
	assert "georreferenciado" in " ".join(dialogo_modal.ultimo.textos)
	assert not contexto.historial.puede_deshacer
