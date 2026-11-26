"""Pruebas del plano gráfico: la geometría sin ventana y el panel con wx sin mostrarlo."""

from __future__ import annotations

import pytest
import wx

from app.dominio import edicion
from app.dominio.colocacion import colocar
from app.dominio.ejemplos import barrio_ejemplo, vivienda_ejemplo
from app.dominio.modelo import Objeto
from app.ui import modelo_plano as mp
from app.ui.contexto import ContextoEstudio

# ── Geometría sin wx ─────────────────────────────────────────────────────────


def _entorno_sencillo():
	"""Dos habitaciones, una mesa (caja) en el salón, una fuente y una referencia."""
	entorno = edicion.crear_entorno("Prueba")
	planta = edicion.crear_planta(entorno, "Baja")
	salon = edicion.crear_habitacion_rectangular(entorno, planta, "Salón", 0, 0, 6, 4)
	cocina = edicion.crear_habitacion_adosada(entorno, planta, "Cocina", salon, "este", 3, 4)
	edicion.anadir_puerta_entre(entorno, planta, salon, cocina)
	mesa = Objeto(nombre="Mesa", tipo="caja", x=2.0, y=2.0, ancho=1.2, fondo=0.8)
	assert not [a for a in colocar(entorno, planta, mesa, None) if a.es_error]
	edicion.anadir_fuente(entorno, planta, "Reloj", 5.0, 3.5, "reloj")
	edicion.anadir_referencia(entorno, planta, "Columna", 4.0, 1.0)
	edicion.fijar_inicio(entorno, planta, 1.0, 1.0, 90.0)
	return entorno, planta, salon, cocina, mesa


def test_conversion_de_coordenadas_ida_y_vuelta():
	vista = mp.VistaPlano(escala=50.0, origen_x=-2.0, origen_y=10.0, ancho=800, alto=600)
	assert vista.a_pantalla(-2.0, 10.0) == (0.0, 0.0)
	px, py = vista.a_pantalla(3.0, 4.0)
	assert (px, py) == (250.0, 300.0)
	assert vista.a_mundo(px, py) == pytest.approx((3.0, 4.0))
	# El norte queda arriba: más y en el mundo, menos y en la pantalla.
	assert vista.a_pantalla(0.0, 9.0)[1] < vista.a_pantalla(0.0, 1.0)[1]


def test_encajar_centra_y_deja_margen():
	vista = mp.VistaPlano()
	vista.encajar((0.0, 0.0, 10.0, 5.0), 1000, 800)
	izquierda, abajo = vista.a_pantalla(0.0, 0.0)
	derecha, arriba = vista.a_pantalla(10.0, 5.0)
	assert 0 < izquierda < derecha < 1000 and 0 < arriba < abajo < 800
	assert izquierda == pytest.approx(1000 - derecha) and arriba == pytest.approx(800 - abajo)
	assert vista.escala == pytest.approx(1000 * (1 - 2 * mp.MARGEN_ENCAJE) / 10.0)


def test_zoom_conserva_el_punto_bajo_el_cursor():
	vista = mp.VistaPlano(escala=40.0, origen_x=0.0, origen_y=20.0, ancho=800, alto=600)
	antes = vista.a_mundo(333, 222)
	vista.zoom(1.25, 333, 222)
	assert vista.escala == pytest.approx(50.0)
	assert vista.a_mundo(333, 222) == pytest.approx(antes)
	vista.zoom(1e9, 10, 10)
	assert vista.escala == mp.ESCALA_MAXIMA
	vista.desplazar(100, 0)
	assert vista.a_mundo(433, 222)[0] != antes[0]


def test_seleccion_por_punto():
	entorno, planta, salon, cocina, mesa = _entorno_sencillo()
	figuras = mp.figuras_de_planta(entorno, planta, None)
	assert mp.elemento_en(figuras, 2.0, 2.0) == mesa.id, "el objeto gana al espacio en el que está"
	assert mp.elemento_en(figuras, 0.5, 3.5) == salon.id
	assert mp.elemento_en(figuras, 7.5, 2.0) == cocina.id
	assert mp.elemento_en(figuras, 50.0, 50.0) == ""
	fuente = planta.fuentes[0]
	assert mp.elemento_en(figuras, 5.05, 3.5) == fuente.id
	puerta = planta.aberturas[0]
	centro = puerta.centro()
	assert mp.elemento_en(figuras, centro[0], centro[1]) == puerta.id
	# El inicio se dibuja pero no se puede seleccionar.
	assert any(f.clase == "inicio" for f in figuras)
	assert mp.elemento_en([f for f in figuras if f.clase == "inicio"], 1.0, 1.0) == ""


def test_espacio_pequeno_gana_al_grande():
	entorno = barrio_ejemplo()
	planta = entorno.plantas[0]
	figuras = mp.figuras_de_planta(entorno, planta, None)
	paso = next(e for e in planta.espacios if e.tipo == "paso_peatones")
	# Un punto del paso que no esté sobre el eje de la calle (el eje, que es una línea, va encima).
	cx, cy = paso.centro()
	vx, vy = paso.contorno[0]
	x, y = (cx + vx) / 2, (cy + vy) / 2
	assert len(planta.espacios_en(x, y)) >= 2, "el paso está sobre su calzada"
	assert mp.elemento_en(figuras, x, y, 0.05) == paso.id
	ordenes = [f.orden for f in figuras]
	assert ordenes == sorted(ordenes)


def test_figuras_de_actividad_y_objetos():
	entorno, planta, _salon, _cocina, mesa = _entorno_sencillo()
	actividad = {
		"premios": [
			{"id": "p1", "nombre": "Llave", "planta": planta.id, "x": 3.0, "y": 3.0},
			{"nombre": "Otra planta", "planta": "no", "x": 1, "y": 1},
		],
		"inicio": {"planta": planta.id, "x": 5.0, "y": 1.0, "rumbo": 180.0},
	}
	figuras = mp.figuras_de_planta(entorno, planta, None, actividad)
	premios = [f for f in figuras if f.clase == "premio"]
	assert [f.rotulo for f in premios] == ["Llave"]
	assert len([f for f in figuras if f.clase == "inicio"]) == 2
	objeto = mp.figura_de(figuras, mesa.id)
	assert objeto is not None and objeto.letra == "M" and len(objeto.puntos) == 4


def test_cuadricula_arrastre_y_regla():
	assert mp.ajustar_a_cuadricula(1.26, 0.5) == pytest.approx(1.5)
	assert mp.ajustar_a_cuadricula(1.26, 0.0) == pytest.approx(1.26)
	vista = mp.VistaPlano(escala=100.0, origen_x=0.0, origen_y=10.0)
	assert mp.desplazamiento_de_arrastre(vista, (100, 100), (230, 40)) == pytest.approx((1.3, 0.6))
	assert mp.desplazamiento_de_arrastre(vista, (100, 100), (230, 40), 0.5) == pytest.approx((1.5, 0.5))
	assert mp.rectangulo_de_arrastre(vista, (300, 200), (100, 500)) == pytest.approx((1.0, 5.0, 2.0, 3.0))
	assert mp.paso_de_regla(100.0, 120) == 1.0
	assert mp.paso_de_regla(40.0, 120) == 2.0
	assert mp.paso_de_regla(5.0, 120) == 20.0
	assert mp.paso_de_regla(1000.0, 120) == pytest.approx(0.1)
	assert mp.paso_visible_de_cuadricula(0.5, 100.0) == 0.5
	assert mp.paso_visible_de_cuadricula(0.5, 2.0) * 2.0 >= 8.0
	arco = mp.arco_de_puerta((0.0, 0.0), (1.0, 0.0))
	assert arco[0] == pytest.approx((1.0, 0.0)) and arco[-1] == pytest.approx((0.0, 1.0))


# ── Panel con wx ─────────────────────────────────────────────────────────────


class _Configuracion:
	"""Configuración mínima: solo lo que consulta el plano."""

	def __init__(self, **valores):
		self.valores = {"editor.cuadricula": True, "editor.paso_cuadricula": 0.5, "editor.paso_minimo_m": 0.05, **valores}

	def obtener(self, clave, defecto=None):
		return self.valores.get(clave, defecto)


@pytest.fixture
def plano(marco):
	from app.ui.plano import PanelPlano

	entorno, planta, _salon, _cocina, mesa = _entorno_sencillo()
	contexto = ContextoEstudio(ventana=None, configuracion=_Configuracion())
	contexto.abrir_documento(entorno)
	marco.SetClientSize(wx.Size(800, 600))
	panel = PanelPlano(marco, contexto)
	panel.SetSize(wx.Size(800, 600))
	panel.vista.encajar(mp.caja_de_figuras(panel.figuras), 800, 600)
	panel._encajado = True
	panel.mesa_id = mesa.id
	panel.planta_id = planta.id
	return panel


def _raton(panel, tipo, x, y, **estado):
	evento = wx.MouseEvent(tipo)
	evento.SetPosition(wx.Point(int(x), int(y)))
	evento.SetEventObject(panel)
	evento.SetId(panel.GetId())
	if estado.get("izquierdo"):
		evento.SetLeftDown(True)
	if "rueda" in estado:
		evento.SetWheelRotation(estado["rueda"])
		evento.SetWheelDelta(120)
	panel.GetEventHandler().ProcessEvent(evento)


def _pixel(panel, x, y):
	return panel.vista.a_pantalla(x, y)


def test_panel_tiene_nombre_ayuda_y_acepta_foco(plano):
	assert plano.GetLabel() == "Plano gráfico"
	assert "árbol" in plano.GetHelpText() and "menús" in plano.GetHelpText()
	assert plano.AcceptsFocus()
	assert not plano.GetWindowStyleFlag() & wx.WANTS_CHARS, "con WANTS_CHARS el tabulador quedaría atrapado en el plano"
	assert plano.herramienta == "seleccion"
	with pytest.raises(ValueError):
		plano.fijar_herramienta("borrador")


def test_clic_selecciona_y_clic_en_vacio_deselecciona(plano):
	contexto = plano.contexto
	_raton(plano, wx.wxEVT_LEFT_DOWN, *_pixel(plano, 2.0, 2.0))
	_raton(plano, wx.wxEVT_LEFT_UP, *_pixel(plano, 2.0, 2.0))
	assert contexto.seleccion == plano.mesa_id
	assert len(contexto.historial.operaciones()) == 0, "un clic sin arrastre no mueve nada"
	_raton(plano, wx.wxEVT_LEFT_DOWN, 2, 2)
	_raton(plano, wx.wxEVT_LEFT_UP, 2, 2)
	assert contexto.seleccion == ""


def test_arrastre_mueve_entra_en_el_historial_y_se_deshace(plano, voz_simulada):
	contexto = plano.contexto
	inicio = _pixel(plano, 2.0, 2.0)
	fin = _pixel(plano, 3.0, 2.5)
	_raton(plano, wx.wxEVT_LEFT_DOWN, *inicio)
	_raton(plano, wx.wxEVT_MOTION, *fin, izquierdo=True)
	_raton(plano, wx.wxEVT_LEFT_UP, *fin)
	mesa = contexto.entorno.elemento(plano.mesa_id)
	assert (mesa.x, mesa.y) == pytest.approx((3.0, 2.5)), "con el ajuste activo cae en la cuadrícula"
	assert contexto.historial.operaciones() == ["mover Mesa"]
	assert contexto.modificado
	assert voz_simulada.contiene("Mesa: 3 metros al este, 2,5 metros al norte")
	assert contexto.deshacer() == "mover Mesa"
	mesa = contexto.entorno.elemento(plano.mesa_id)
	assert (mesa.x, mesa.y) == pytest.approx((2.0, 2.0))


def test_arrastre_sin_ajuste_y_movimiento_imposible(plano, voz_simulada):
	plano.fijar_ajuste(False)
	assert plano.mover_elemento(plano.mesa_id, 0.13, 0.0) is True
	assert plano.contexto.entorno.elemento(plano.mesa_id).x == pytest.approx(2.13)
	assert plano.mover_elemento(plano.mesa_id, 0.0, 0.0) is False
	assert plano.mover_elemento("no-existe", 1.0, 0.0) is False
	# Lo que el dominio rechace se anuncia y no rompe nada.
	import app.ui.plano as modulo

	def falla(*_a, **_k):
		raise edicion.ErrorEdicion("No se puede mover ahí.")

	original = modulo.edicion.mover
	modulo.edicion.mover = falla
	try:
		assert plano.mover_elemento(plano.mesa_id, 1.0, 0.0) is False
	finally:
		modulo.edicion.mover = original
	assert voz_simulada.contiene("No se puede mover ahí.")
	assert plano.contexto.historial.operaciones() == ["mover Mesa"]


def test_flechas_mueven_y_anuncian(plano, voz_simulada, ayudas_wx):
	contexto = plano.contexto
	resultado = ayudas_wx.simular_tecla(plano, wx.WXK_RIGHT)
	assert resultado.gestionado and voz_simulada.contiene("No hay ningún elemento seleccionado")
	contexto.seleccionar(plano.mesa_id)
	ayudas_wx.simular_tecla(plano, wx.WXK_RIGHT)
	assert contexto.entorno.elemento(plano.mesa_id).x == pytest.approx(2.5)
	assert voz_simulada.ultimo == "Mesa: 2,5 metros al este, 2 metros al norte"
	ayudas_wx.simular_tecla(plano, wx.WXK_UP, mayus=True)
	assert contexto.entorno.elemento(plano.mesa_id).y == pytest.approx(2.05)
	ayudas_wx.simular_tecla(plano, wx.WXK_LEFT)
	ayudas_wx.simular_tecla(plano, wx.WXK_DOWN, mayus=True)
	mesa = contexto.entorno.elemento(plano.mesa_id)
	assert (mesa.x, mesa.y) == pytest.approx((2.0, 2.0))
	assert len(contexto.historial.operaciones()) == 4
	# Lo que el plano no atiende sigue su camino: Tab, F6 y las flechas con Control.
	for tecla, extra in ((wx.WXK_TAB, {}), (wx.WXK_F6, {}), (wx.WXK_RIGHT, {"ctrl": True}), (wx.WXK_ESCAPE, {})):
		suelta = ayudas_wx.simular_tecla(plano, tecla, **extra)
		assert suelta.saltado and not suelta.gestionado, tecla


def test_dibujar_habitacion_y_pared_llaman_con_metros(plano, ayudas_wx):
	habitaciones, paredes, objetos = [], [], []
	plano.al_dibujar_habitacion = lambda x, y, ancho, fondo: habitaciones.append((x, y, ancho, fondo))
	plano.al_dibujar_pared = lambda a, b: paredes.append((a, b))
	plano.al_colocar_objeto = lambda x, y: objetos.append((x, y))

	plano.fijar_herramienta("habitacion")
	_raton(plano, wx.wxEVT_LEFT_DOWN, *_pixel(plano, 10.0, 4.0))
	_raton(plano, wx.wxEVT_MOTION, *_pixel(plano, 13.1, 1.1), izquierdo=True)
	_raton(plano, wx.wxEVT_LEFT_UP, *_pixel(plano, 13.1, 1.1))
	assert habitaciones == [pytest.approx((10.0, 1.0, 3.0, 3.0))]
	# Un clic sin arrastre no crea una habitación diminuta.
	_raton(plano, wx.wxEVT_LEFT_DOWN, *_pixel(plano, 10.0, 4.0))
	_raton(plano, wx.wxEVT_LEFT_UP, *_pixel(plano, 10.0, 4.0))
	assert len(habitaciones) == 1

	plano.fijar_herramienta("pared")
	_raton(plano, wx.wxEVT_LEFT_DOWN, *_pixel(plano, 1.0, 5.0))
	assert paredes == []
	_raton(plano, wx.wxEVT_MOTION, *_pixel(plano, 2.0, 5.0))
	_raton(plano, wx.wxEVT_LEFT_DOWN, *_pixel(plano, 4.02, 5.0))
	assert paredes == [(pytest.approx((1.0, 5.0)), pytest.approx((4.0, 5.0)))]

	plano.fijar_herramienta("objeto")
	_raton(plano, wx.wxEVT_LEFT_DOWN, *_pixel(plano, 7.5, 2.0))
	assert objetos == [pytest.approx((7.5, 2.0))]

	# Escape devuelve a la herramienta de selección.
	assert ayudas_wx.simular_tecla(plano, wx.WXK_ESCAPE).gestionado
	assert plano.herramienta == "seleccion"


def test_doble_clic_y_menu_contextual(plano, monkeypatch):
	editados, menus = [], []
	plano.al_editar = editados.append
	_raton(plano, wx.wxEVT_LEFT_DCLICK, *_pixel(plano, 2.0, 2.0))
	assert editados == [plano.mesa_id] and plano.contexto.seleccion == plano.mesa_id

	def crear_menu():
		menu = wx.Menu()
		menu.Append(wx.ID_ANY, "&Borrar")
		return menu

	plano.al_menu = crear_menu
	monkeypatch.setattr(
		type(plano), "PopupMenu", lambda self, menu, posicion=None: menus.append((menu.GetMenuItemCount(), posicion)) or True
	)
	evento = wx.ContextMenuEvent(wx.wxEVT_CONTEXT_MENU, plano.GetId(), wx.DefaultPosition)
	evento.SetEventObject(plano)
	plano.GetEventHandler().ProcessEvent(evento)
	assert len(menus) == 1 and menus[0][0] == 1
	px, py = _pixel(plano, 2.0, 2.0)
	assert abs(menus[0][1].x - px) <= 1 and abs(menus[0][1].y - py) <= 1, "desde el teclado, junto al elemento seleccionado"


def test_rueda_zoom_y_ordenes_de_vista(plano):
	escala = plano.vista.escala
	punto = _pixel(plano, 2.0, 2.0)
	_raton(plano, wx.wxEVT_MOUSEWHEEL, *punto, rueda=120)
	assert plano.vista.escala > escala
	assert plano.vista.a_mundo(int(punto[0]), int(punto[1])) == pytest.approx((2.0, 2.0), abs=0.05)
	plano.alejar()
	plano.alejar()
	assert plano.vista.escala < escala
	plano.acercar()
	plano.fijar_cuadricula(False)
	assert plano.cuadricula_visible is False


def test_reacciona_a_la_seleccion_y_a_los_cambios(plano, monkeypatch):
	repintados = []
	monkeypatch.setattr(type(plano), "Refresh", lambda self, *a, **k: repintados.append(True))
	plano.contexto.seleccionar(plano.mesa_id)
	assert repintados, "al cambiar la selección en el árbol o en la lista el plano se repinta"
	antes = len(plano.figuras)
	contexto = plano.contexto
	contexto.ejecutar(
		"añadir referencia", lambda: edicion.anadir_referencia(contexto.entorno, contexto.planta_actual(), "Extintor", 8.0, 1.0)
	)
	assert len(plano.figuras) == antes + 1
	contexto.cerrar_documento()
	assert plano.figuras == []


def _pintar(panel, ancho=640, alto=480) -> wx.Bitmap:
	mapa = wx.Bitmap(ancho, alto)
	dc = wx.MemoryDC(mapa)
	try:
		panel.pintar(dc, ancho, alto)
	finally:
		dc.SelectObject(wx.NullBitmap)
	return mapa


def _colores_distintos(mapa: wx.Bitmap) -> int:
	imagen = mapa.ConvertToImage()
	datos = bytes(imagen.GetData())
	return len({datos[i : i + 3] for i in range(0, len(datos), 3 * 97)})


@pytest.mark.parametrize("contraste", [False, True])
@pytest.mark.parametrize("ejemplo", [vivienda_ejemplo, barrio_ejemplo])
def test_pinta_los_ejemplos_sin_errores(marco, ejemplo, contraste):
	from app.ui.plano import PanelPlano

	entorno = ejemplo()
	contexto = ContextoEstudio(configuracion=_Configuracion(**{"general.alto_contraste": contraste}))
	contexto.abrir_documento(entorno)
	planta = contexto.planta_actual()
	contexto.actividad_actual = {
		"premios": [{"nombre": "Premio", "planta": planta.id, "x": 1.0, "y": 1.0}],
		"inicio": {"planta": planta.id, "x": 2.0, "y": 1.0, "rumbo": 45.0},
	}
	panel = PanelPlano(marco, contexto)
	panel.vista.encajar(mp.caja_de_figuras(panel.figuras), 640, 480)
	if planta.espacios:
		contexto.seleccionar(planta.espacios[0].id)
	assert panel.alto_contraste() is contraste or contraste is False
	mapa = _pintar(panel)
	assert _colores_distintos(mapa) >= 2, "tiene que haberse dibujado algo"
	# Con un gesto a medias también se pinta.
	panel.fijar_herramienta("pared")
	panel._primer_punto_pared = (0.0, 0.0)
	_pintar(panel)


def test_pinta_sin_entorno_y_con_fondo_roto(marco):
	from app.ui.plano import PanelPlano

	contexto = ContextoEstudio(configuracion=_Configuracion())
	panel = PanelPlano(marco, contexto)
	_pintar(panel)
	entorno, planta, *_resto = _entorno_sencillo()
	imagen = wx.Image(8, 8)
	flujo = __import__("io").BytesIO()
	imagen.SaveFile(flujo, wx.BITMAP_TYPE_PNG)
	entorno.procedencia["fondos"] = [
		{
			"planta": planta.id,
			"imagen": "imagenes/plano.png",
			"puntos": [{"imagen": [0, 0], "mundo": [0, 4]}, {"imagen": [8, 0], "mundo": [6, 4]}],
		},
		{"planta": planta.id, "imagen": "imagenes/falta.png", "puntos": []},
	]
	contexto.abrir_documento(entorno, recursos={"imagenes/plano.png": flujo.getvalue()})
	assert panel._mapa_de_fondo("imagenes/plano.png") is not None
	assert panel._mapa_de_fondo("imagenes/falta.png") is None
	_pintar(panel)
