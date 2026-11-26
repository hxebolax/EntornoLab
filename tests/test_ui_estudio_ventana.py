"""Pruebas de la ventana principal del Estudio: construir un entorno solo con órdenes de menú y diálogos simulados.

La ventana se crea sin mostrarla y los diálogos se contestan con la fixture
``dialogo_modal``; nunca hay un ``ShowModal`` real.
"""

from __future__ import annotations

import sys
import types

import pytest
import wx

from app.core.config import Configuracion
from app.core.i18n import N_
from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio.formato import cargar_paquete, guardar_paquete
from app.dominio.modelo import Abertura, Conector, Espacio, FuenteSonido, Objeto, Pared, Referencia, Via, ZonaSuelo
from app.ui import archivos, dialogos_herramientas, dialogos_insertar, operaciones
from app.ui import ventana_principal as vp
from app.ui.accesibilidad.revision_teclado import afirmar_teclado_correcto
from app.ui.contexto import ContextoEstudio
from app.ui.esquemas_elementos import ORDENES, esquema_de, sonidos
from app.ui.formulario import DialogoFormulario
from tests.test_dominio_comun import catalogo_de_prueba, piso_minimo

from ._ui_estudio_util import boton, cerrar_ventana, crear_ventana, elegir_objeto, espacio, fichero, orden, rellenar, textos_del_arbol
from .conftest import procesar_eventos

#: Teclas que la ventana atiende a mano (la revisión del teclado no puede deducirlas).
TECLAS_PROPIAS = ["Supr"]


@pytest.fixture
def catalogo(tmp_path):
	return catalogo_de_prueba(tmp_path)


@pytest.fixture
def ventana(app_wx, monkeypatch, catalogo, dialogo_modal):
	marco = crear_ventana(monkeypatch, catalogo)
	yield marco
	cerrar_ventana(marco)


def _abrir(ventana, entorno) -> None:
	ventana.contexto.abrir_documento(entorno)


def _construir_vivienda(ventana, dialogo_modal) -> None:
	"""Crea, solo con órdenes de menú, una vivienda con tres habitaciones, puertas, un objeto y una fuente."""
	dialogo_modal.responder(rellenar(nombre="Casa de prueba", plantilla="en_blanco", autor="Ana"))
	orden(ventana, "nuevo")
	dialogo_modal.responder(rellenar(nombre="Salón", ancho="5", fondo="4", x="0", y="0"))
	orden(ventana, "insertar_habitacion")
	salon = espacio(ventana, "Salón")
	dialogo_modal.responder(rellenar(junto_a=salon.id, lado="este", nombre="Cocina", ancho="3", fondo="4", con_puerta=True))
	orden(ventana, "insertar_adosada")
	dialogo_modal.responder(rellenar(junto_a=salon.id, lado="norte", nombre="Dormitorio", ancho="5", fondo="3", con_puerta=False))
	orden(ventana, "insertar_adosada")
	dormitorio = espacio(ventana, "Dormitorio")
	dialogo_modal.responder(rellenar(espacio=dormitorio.id, lado="sur", centrada=False, desplazamiento="1,20"))
	orden(ventana, "insertar_abertura")
	dialogo_modal.responder(rellenar(espacio=salon.id, lado="oeste", nombre="Entrada", es_salida=True))
	orden(ventana, "insertar_abertura")
	planta_id = ventana.contexto.entorno.plantas[0].id
	ventana.contexto.seleccionar(salon.id)
	dialogo_modal.responder(
		elegir_objeto("prueba/mesa"), rellenar(planta=planta_id, modo="pared", espacio=salon.id, lado="sur", alineacion="centro")
	)
	orden(ventana, "insertar_objeto")
	disponibles = sonidos()
	dialogo_modal.responder(
		rellenar(nombre="Frigorífico", sonido=disponibles[0][0] if disponibles else "fuente/frigorifico", x="6,5", y="3,5")
	)
	orden(ventana, "insertar_fuente")


# ── El escenario completo ────────────────────────────────────────────────────


def test_crear_vivienda_solo_con_menus_deshacer_guardar_y_reabrir(ventana, dialogo_modal, voz_simulada, tmp_path):
	_construir_vivienda(ventana, dialogo_modal)
	contexto = ventana.contexto
	entorno = contexto.entorno
	planta = entorno.plantas[0]
	assert entorno.nombre == "Casa de prueba" and entorno.autor == "Ana"
	assert [e.nombre for e in planta.espacios] == ["Salón", "Cocina", "Dormitorio"]
	assert len(planta.aberturas) == 3, "la puerta de la cocina, la del dormitorio y la entrada"
	dormitorio = espacio(ventana, "Dormitorio")
	puerta_dormitorio = next(
		a
		for a in planta.aberturas
		if dormitorio in ed.espacios_de_abertura(planta, a)
		and len(ed.espacios_de_abertura(planta, a)) == 2
		and a.nombre != "Entrada"
		and "Cocina" not in a.nombre
	)
	assert min(puerta_dormitorio.a[0], puerta_dormitorio.b[0]) == pytest.approx(1.2), "a 1,20 m de la esquina oeste"
	assert [o.tipo for o in planta.objetos] == ["prueba/mesa"]
	assert [f.nombre for f in planta.fuentes] == ["Frigorífico"]
	assert espacio(ventana, "Cocina").contiene(planta.fuentes[0].x, planta.fuentes[0].y)
	# Todo quedó en el historial con su nombre, y el título lleva el asterisco de «modificado».
	operaciones_hechas = contexto.historial.operaciones()
	assert len(operaciones_hechas) == 7 and operaciones_hechas[0] == "crear Salón" and "Frigorífico" in operaciones_hechas[-1]
	assert ventana.GetTitle().startswith("*Casa de prueba")
	assert "Deshacer: añadir el sonido Frigorífico" in ventana.elementos_menu["deshacer"].GetItemLabelText()
	assert voz_simulada.textos, "cada operación se anuncia"
	textos = textos_del_arbol(ventana)
	assert any("Salón" in t for t in textos) and any("Frigorífico" in t for t in textos)

	# Deshacer y rehacer, con el nombre de la operación.
	orden(ventana, "deshacer")
	orden(ventana, "deshacer")
	assert not contexto.entorno.plantas[0].fuentes and not contexto.entorno.plantas[0].objetos
	assert voz_simulada.contiene("Deshecho: colocar")
	assert ventana.elementos_menu["rehacer"].IsEnabled()
	orden(ventana, "rehacer")
	orden(ventana, "rehacer")
	assert len(contexto.entorno.plantas[0].fuentes) == 1 and len(contexto.entorno.plantas[0].objetos) == 1
	assert not ventana.elementos_menu["rehacer"].IsEnabled()

	# Guardar (pregunta dónde la primera vez), cerrar y reabrir idéntico.
	ruta = tmp_path / "casa.elab"
	dialogo_modal.responder(fichero(ruta))
	orden(ventana, "guardar")
	assert ruta.is_file() and not contexto.modificado
	assert ventana.GetTitle().startswith("Casa de prueba"), "sin asterisco tras guardar"
	guardado = contexto.entorno.a_dict()
	contexto.cerrar_documento()
	assert ventana.GetTitle() == "EntornoLab" and textos_del_arbol(ventana) == ["No hay ningún entorno abierto"]
	assert ventana.abrir_paquete(ruta) is True
	assert contexto.entorno.a_dict() == guardado
	assert archivos.recientes(contexto.configuracion) == [ruta.resolve()]
	ventana._rellenar_dinamicos()
	recientes = ventana._submenus_dinamicos["recientes"].GetMenuItems()
	assert [item.GetItemLabel() for item in recientes] == ["&1 casa"]


def test_un_error_de_edicion_deja_el_dialogo_y_el_entorno_como_estaban(ventana, dialogo_modal):
	_abrir(ventana, piso_minimo()[0])
	antes = ventana.contexto.entorno.a_dict()
	# Una habitación encima del salón no se puede crear: se explica y no cambia nada.
	dialogo_modal.responder(rellenar(nombre="Encima", ancho="2", fondo="2", x="1", y="1"))
	orden(ventana, "insertar_habitacion")
	assert ventana.contexto.entorno.a_dict() == antes
	assert not ventana.contexto.historial.puede_deshacer and not ventana.contexto.modificado
	assert any(d.clase == "DialogoMensaje" for d in dialogo_modal.mostrados), "el motivo se enseña en un mensaje"


def test_objeto_que_no_cabe_no_se_coloca(ventana, dialogo_modal):
	entorno = ed.crear_entorno("Trastero")
	planta = ed.crear_planta(entorno, "Planta baja")
	cuarto = ed.crear_habitacion_rectangular(entorno, planta, "Cuarto", 0, 0, 1, 1)
	_abrir(ventana, entorno)
	ventana.contexto.seleccionar(cuarto.id)
	dialogo_modal.responder(elegir_objeto("prueba/sofa"), rellenar(planta=planta.id, modo="pared", espacio=cuarto.id, lado="norte"))
	orden(ventana, "insertar_objeto")
	assert not ventana.contexto.entorno.plantas[0].objetos, "un sofá de 1,4 m como mínimo no cabe en un cuarto de 1 m"
	assert not ventana.contexto.historial.puede_deshacer and not ventana.contexto.modificado


# ── Sincronía árbol ↔ lista ↔ plano ↔ propiedades ───────────────────────────


def test_sincronia_arbol_lista_plano_y_propiedades(ventana):
	entorno, planta, salon, cocina = piso_minimo()
	fuente = ed.anadir_fuente(entorno, planta, "Frigorífico", 6.5, 3.5, "fuente/frigorifico")
	_abrir(ventana, entorno)
	contexto = ventana.contexto
	# Del árbol a los demás.
	ventana.arbol.SelectItem(ventana._nodos[cocina.id])
	assert contexto.seleccion == cocina.id
	assert [fila.nombre for fila in ventana._filas][-1] == "Frigorífico", "la lista enseña lo que hay en la cocina"
	assert "Cocina" in ventana.titulo_propiedades.GetLabel()
	assert ventana.propiedades.controles["nombre"].GetValue() == "Cocina"
	assert "3 por 4" in ventana.frase.GetValue() or "3" in ventana.frase.GetValue()
	assert ventana.lista.GetFocusedItem() >= 0, "con filas, siempre hay una enfocada"
	# De la lista al árbol (y al plano, que lee la selección del contexto).
	indice = [fila.id for fila in ventana._filas].index(fuente.id)
	ventana.lista.Focus(indice)
	ventana.lista.Select(indice)
	assert contexto.seleccion == fuente.id
	assert ventana.arbol.GetItemText(ventana.arbol.GetSelection()).startswith("Frigorífico")
	assert ventana.propiedades.controles["nombre"].GetValue() == "Frigorífico"
	assert [fila.id for fila in ventana._filas][indice] == fuente.id, "moverse por la lista no la rehace"
	# Del plano (un clic llama a contexto.seleccionar) al árbol y a la lista.
	contexto.seleccionar(salon.id)
	assert ventana.arbol.GetItemData(ventana.arbol.GetSelection()) == salon.id
	assert ventana.propiedades.controles["nombre"].GetValue() == "Salón"
	figura = next(f for f in ventana.plano.figuras if f.id == salon.id)
	assert figura is not None and ventana.plano.contexto.seleccion == salon.id
	px, py = ventana.plano.vista.a_pantalla(6.5, 3.5)
	assert ventana.plano.elemento_en_pixel(px, py) == fuente.id, "el plano y el árbol hablan de los mismos elementos"
	# Una puerta está bajo sus dos espacios: elegirla en uno u otro es el mismo elemento.
	puerta = planta.aberturas[0]
	ventana.arbol.SelectItem(ventana._nodos[f"{salon.id}/{puerta.id}"])
	assert contexto.seleccion == puerta.id
	ventana.arbol.SelectItem(ventana._nodos[f"{cocina.id}/{puerta.id}"])
	assert contexto.seleccion == puerta.id and ventana.propiedades.controles["tipo"].GetSelection() >= 0


def test_panel_de_propiedades_aplica_valida_y_descarta(ventana, dialogo_modal, voz_simulada):
	entorno, _planta, salon, _cocina = piso_minimo()
	_abrir(ventana, entorno)
	contexto = ventana.contexto
	contexto.seleccionar(salon.id)
	ventana.propiedades.fijar({"nombre": "Sala de estar", "suelo": "madera"})
	assert ventana.aplicar_propiedades() is True
	salon = contexto.entorno.elemento(salon.id)
	assert salon.nombre == "Sala de estar" and salon.suelo == "madera"
	assert contexto.historial.operaciones() == ["cambiar Salón"]
	assert any("Sala de estar" in texto for texto in textos_del_arbol(ventana))
	assert voz_simulada.contiene("habitación"), "se anuncia la frase que describe el elemento"
	# Un valor que no vale: mensaje y foco en el campo; nada cambia.
	ventana.propiedades.fijar({"ancho": "ancho"})
	assert ventana.aplicar_propiedades() is False
	assert dialogo_modal.ultimo.titulo == "Revise las propiedades"
	assert contexto.historial.operaciones() == ["cambiar Salón"]
	# Descartar vuelve a los valores del elemento; aplicar sin cambios no apunta nada.
	evento = wx.CommandEvent(wx.wxEVT_BUTTON, ventana.boton_descartar.GetId())
	ventana.boton_descartar.GetEventHandler().ProcessEvent(evento)
	assert ventana.propiedades.controles["ancho"].GetValue() == "5"
	assert ventana.aplicar_propiedades() is True and contexto.historial.operaciones() == ["cambiar Salón"]
	orden(ventana, "deshacer")
	assert contexto.entorno.elemento(salon.id).nombre == "Salón"


# ── Teclado y letras de acceso ───────────────────────────────────────────────


def _un_elemento_de_cada_clase():
	"""(entorno, id) de un elemento de cada clase, de los entornos de ejemplo."""
	vistos: dict[type, tuple] = {}
	for entorno in ejemplos.todos().values():
		if not entorno.plantas[0].exterior and not entorno.plantas[0].objetos:
			# Los ejemplos vienen sin amueblar: se pone una caja para tener también un objeto.
			x, y = entorno.plantas[0].espacios[0].centro()
			entorno.plantas[0].objetos.append(Objeto(id="obj-prueba", nombre="Caja", x=x, y=y, ancho=0.5, fondo=0.5, alto=0.5))
		for _planta, elemento in entorno.elementos():
			vistos.setdefault(type(elemento), (entorno, elemento.id))
		vistos.setdefault(type(entorno.plantas[0]), (entorno, entorno.plantas[0].id))
		paso = next((e for p in entorno.plantas for e in p.espacios if e.tipo == "paso_peatones"), None)
		if paso is not None:
			vistos.setdefault("paso", (entorno, paso.id))  # type: ignore[arg-type]
	return vistos


def test_teclado_de_la_ventana_con_cada_clase_de_elemento(ventana):
	afirmar_teclado_correcto(ventana, teclas_propias=TECLAS_PROPIAS)
	vistos = _un_elemento_de_cada_clase()
	for clase in (Espacio, Abertura, Objeto, FuenteSonido, Referencia, Via, Conector, ZonaSuelo, "paso"):
		assert clase in vistos, f"los ejemplos no tienen ningún {clase}"
	for clase, (entorno, id_elemento) in vistos.items():
		_abrir(ventana, entorno)
		ventana.contexto.seleccionar(id_elemento)
		assert ventana.propiedades.controles, clase
		try:
			afirmar_teclado_correcto(ventana, teclas_propias=TECLAS_PROPIAS)
		except AssertionError as error:
			raise AssertionError(f"Con un elemento {clase} seleccionado:\n{error}") from error
	# El entorno entero también tiene propiedades.
	ventana.contexto.seleccionar("")
	afirmar_teclado_correcto(ventana, teclas_propias=TECLAS_PROPIAS)


def test_teclado_de_cada_dialogo_de_orden(app_wx, catalogo):
	"""Cada formulario de «Insertar» y «Editar»: etiquetas, letras sin repetir y sin controles prohibidos."""
	contexto = ContextoEstudio(None, Configuracion(), catalogo)
	contexto.abrir_documento(ejemplos.barrio_ejemplo())
	interior = ejemplos.centro_dos_plantas()
	for clave, definicion in ORDENES.items():
		for entorno in (interior, ejemplos.barrio_ejemplo()):
			contexto.abrir_documento(entorno)
			if clave in ("mover", "girar", "medidas"):
				contexto.seleccionar(entorno.plantas[0].espacios[0].id)
			if definicion.requisito(contexto):
				continue
			dialogo = DialogoFormulario(None, definicion.titulo, definicion.campos(contexto), definicion.valores(contexto))
			try:
				afirmar_teclado_correcto(dialogo)
				assert dialogo.GetEscapeId() == wx.ID_CANCEL
				for control in dialogo.formulario.controles.values():
					assert not isinstance(control, (wx.SpinCtrlDouble, wx.SearchCtrl)), clave
			except AssertionError as error:
				raise AssertionError(f"En el diálogo de «{clave}»:\n{error}") from error
			finally:
				dialogo.Destroy()
			break
		else:
			raise AssertionError(f"La orden {clave} no se pudo abrir con ningún ejemplo")


def test_teclado_del_dialogo_de_propiedades_de_cada_clase(app_wx, catalogo):
	for clase, (entorno, id_elemento) in _un_elemento_de_cada_clase().items():
		_planta, elemento = operaciones.resolver(entorno, id_elemento)
		dialogo = DialogoFormulario(
			None, "Propiedades", esquema_de(elemento, entorno, catalogo), operaciones.valores_de(entorno, elemento, catalogo)
		)
		try:
			afirmar_teclado_correcto(dialogo)
		except AssertionError as error:
			raise AssertionError(f"Propiedades de {clase}:\n{error}") from error
		finally:
			dialogo.Destroy()


def test_teclado_de_los_dialogos_de_herramientas(app_wx, catalogo):
	contexto = ContextoEstudio(None, Configuracion(), catalogo)
	contexto.abrir_documento(piso_minimo()[0])
	for dialogo in (
		dialogos_herramientas.DialogoComprobar(None, contexto),
		dialogos_herramientas.DialogoMedir(None, contexto),
		dialogos_herramientas.DialogoBuscar(None, contexto),
		dialogos_herramientas.DialogoPropuesta(None, "Propuesta", [("Cama", "1,5 × 2 m", "Contra la pared norte")]),
	):
		try:
			afirmar_teclado_correcto(dialogo)
			assert dialogo.GetEscapeId() == wx.ID_CANCEL, type(dialogo).__name__
		finally:
			dialogo.Destroy()


def test_f6_recorre_los_paneles_y_el_menu_contextual_existe(ventana):
	_abrir(ventana, piso_minimo()[0])
	paneles = ventana.paneles()
	assert paneles[0] is ventana.arbol and paneles[1] is ventana.lista and paneles[-1] is ventana.plano
	assert len(paneles) == 4, "árbol, lista, propiedades y plano"
	menu = ventana._crear_menu_contextual()
	try:
		etiquetas = [item.GetItemLabel() for item in menu.GetMenuItems() if not item.IsSeparator()]
		letras = [etiqueta[etiqueta.index("&") + 1].lower() for etiqueta in etiquetas]
		assert len(letras) == len(set(letras)) and "&Borrar" in etiquetas
	finally:
		menu.Destroy()
	orden(ventana, "mostrar_plano", marcada=False)
	assert not ventana.plano.IsShown() and len(ventana.paneles()) == 3
	assert Configuracion().obtener("editor.plano_visible") is False
	orden(ventana, "ver_plano")
	assert ventana.plano.IsShown(), "ir al plano lo vuelve a enseñar"


# ── Editar ───────────────────────────────────────────────────────────────────


def test_renombrar_duplicar_mover_girar_medidas_y_borrar(ventana, dialogo_modal, voz_simulada, ayudas_wx):
	entorno, planta, salon, cocina = piso_minimo()
	_abrir(ventana, entorno)
	contexto = ventana.contexto
	contexto.seleccionar(cocina.id)
	dialogo_modal.responder(lambda d: (d.campo.SetValue("Office"), wx.ID_OK)[1])
	orden(ventana, "renombrar")
	assert contexto.entorno.elemento(cocina.id).nombre == "Office"
	dialogo_modal.responder(rellenar(modo="desplazar", dx="0", dy="-1"))
	orden(ventana, "mover")
	assert contexto.entorno.elemento(cocina.id).caja()[1] == pytest.approx(-1.0)
	dialogo_modal.responder(rellenar(ancho="3", fondo="5"))
	orden(ventana, "medidas")
	assert contexto.entorno.elemento(cocina.id).caja()[3] == pytest.approx(4.0)
	referencia = contexto.ejecutar("añadir", lambda: ed.anadir_referencia(contexto.entorno, contexto.entorno.plantas[0], "Reloj", 1.0, 1.0))
	contexto.seleccionar(referencia.id)
	orden(ventana, "duplicar")
	referencias = contexto.entorno.plantas[0].referencias
	assert len(referencias) == 2 and contexto.seleccion == referencias[1].id and referencias[1].x == pytest.approx(1.5)
	# Suprimir en la lista o en el árbol borra, con confirmación: «Cancelar» es el botón de Intro.
	dialogo_modal.responder(boton(0))
	ayudas_wx.simular_tecla(ventana.arbol, wx.WXK_DELETE, tipo=wx.wxEVT_KEY_DOWN)
	assert len(contexto.entorno.plantas[0].referencias) == 2, "con Cancelar no se borra"
	assert dialogo_modal.ultimo.titulo == "Borrar" and "&Borrar" in dialogo_modal.ultimo.textos
	dialogo_modal.responder(boton(1))
	ayudas_wx.simular_tecla(ventana.lista, wx.WXK_DELETE, tipo=wx.wxEVT_KEY_DOWN)
	assert len(contexto.entorno.plantas[0].referencias) == 1
	assert contexto.seleccion == contexto.entorno.plantas[0].id, "tras borrar, la selección pasa a la planta"
	assert voz_simulada.contiene("Borrado")
	nombres = contexto.historial.operaciones()
	assert nombres[0] == "renombrar Cocina como Office" and nombres[1] == "mover Office" and nombres[-1].startswith("borrar")
	# Al borrar una habitación se van las puertas que se quedan sin pared.
	contexto.seleccionar(salon.id)
	dialogo_modal.responder(boton(1))
	orden(ventana, "borrar")
	assert [e.nombre for e in contexto.entorno.plantas[0].espacios] == ["Office"]
	assert planta.id == contexto.entorno.plantas[0].id


def test_dibujar_en_el_plano_abre_el_formulario_con_las_medidas(ventana, dialogo_modal):
	entorno = ed.crear_entorno("Dibujo")
	ed.crear_planta(entorno, "Planta baja")
	_abrir(ventana, entorno)
	vistos = {}

	def anotar(dialogo):
		vistos.update(dialogo.formulario.leer.__self__.crudos())
		dialogo.fijar({"nombre": "Dibujada"})
		return wx.ID_OK

	dialogo_modal.responder(anotar)
	ventana.plano.al_dibujar_habitacion(2.0, 1.0, 4.5, 3.0)
	assert (vistos["x"], vistos["y"], vistos["ancho"], vistos["fondo"]) == ("2", "1", "4,5", "3")
	assert espacio(ventana, "Dibujada").caja() == pytest.approx((2.0, 1.0, 6.5, 4.0))
	dialogo_modal.responder(rellenar(nombre="Valla"))
	ventana.plano.al_dibujar_pared((10.0, 0.0), (14.0, 0.0))
	pared = ventana.contexto.entorno.plantas[0].paredes[0]
	assert isinstance(pared, Pared) and pared.a == (10.0, 0.0) and pared.b == (14.0, 0.0)
	orden(ventana, "herramienta_pared")
	assert ventana.plano.herramienta == "pared"
	ventana._actualizar_marcas()
	assert ventana.elementos_menu["herramienta_pared"].IsChecked()


# ── Herramientas ─────────────────────────────────────────────────────────────


def test_comprobar_lleva_al_elemento(ventana, dialogo_modal, voz_simulada):
	entorno, planta, _salon, _cocina = piso_minimo()
	aislada = ed.crear_habitacion_rectangular(entorno, planta, "Trastero", 20, 0, 2, 2)
	_abrir(ventana, entorno)

	def ir_al_trastero(dialogo):
		assert dialogo.lista.GetColumnCount() == 4 and dialogo.lista.GetItemCount() == len(dialogo.avisos) >= 1
		indice = next(i for i, aviso in enumerate(dialogo.avisos) if aviso.elemento_id == aislada.id)
		assert dialogo.avisos[indice].sugerencia and dialogo.lista.texto_celda(indice, 2) == dialogo.avisos[indice].sugerencia
		dialogo.lista.enfocar_fila(indice)
		assert dialogo.ir() is True
		return wx.ID_OK

	dialogo_modal.responder(ir_al_trastero)
	orden(ventana, "comprobar")
	assert ventana.contexto.seleccion == aislada.id
	assert ventana.arbol.GetItemText(ventana.arbol.GetSelection()).startswith("Trastero")
	assert voz_simulada.textos, "el resultado de la comprobación se anuncia"


def test_medir_buscar_y_fijar_inicio(ventana, dialogo_modal, voz_simulada):
	entorno, _planta, salon, cocina = piso_minimo()
	_abrir(ventana, entorno)
	contexto = ventana.contexto
	dialogo = dialogos_herramientas.DialogoMedir(None, contexto)
	try:
		dialogo.elegir(salon.id, cocina.id)
		frase = dialogo.medir()
		assert "4 metros hacia el este" in frase and dialogo.resultado.GetValue() == frase and not dialogo.resultado.IsEditable()
		assert voz_simulada.contiene("4 metros")
	finally:
		dialogo.Destroy()

	def buscar_cocina(dialogo):
		assert dialogo.buscar("cocin") >= 1
		assert dialogo.buscar("cocina habitacion") == 1
		return wx.ID_OK

	dialogo_modal.responder(buscar_cocina)
	orden(ventana, "buscar")
	assert contexto.seleccion == cocina.id
	orden(ventana, "fijar_inicio")
	inicio = contexto.entorno.inicio
	assert contexto.entorno.elemento(cocina.id).contiene(inicio.x, inicio.y)
	assert contexto.historial.operaciones() == ["poner el inicio junto a Cocina"]


def test_amueblar_con_vista_previa_aceptar_y_descartar(ventana, dialogo_modal):
	entorno = ed.crear_entorno("Piso")
	planta = ed.crear_planta(entorno, "Planta baja")
	dormitorio = ed.crear_habitacion_rectangular(entorno, planta, "Dormitorio", 0, 0, 4, 4)
	ed.anadir_puerta(entorno, planta, dormitorio, "sur")
	_abrir(ventana, entorno)
	contexto = ventana.contexto
	contexto.seleccionar(dormitorio.id)
	propuestas = []

	def revisar(dialogo):
		propuestas.append([dialogo.lista.texto_celda(i, 0) for i in range(dialogo.lista.GetItemCount())])
		return wx.ID_CANCEL

	dialogo_modal.responder(rellenar(uso="dormitorio"), revisar)
	orden(ventana, "amueblar")
	assert propuestas and propuestas[0], "se enseña la propuesta antes de colocar nada"
	assert not contexto.entorno.plantas[0].objetos and not contexto.modificado, "al descartar no se coloca nada"
	dialogo_modal.responder(rellenar(uso="dormitorio"), wx.ID_OK)
	orden(ventana, "amueblar")
	colocados = contexto.entorno.plantas[0].objetos
	assert [o.nombre for o in colocados] == propuestas[0], "se coloca exactamente lo que se enseñó"
	assert contexto.historial.operaciones() == ["amueblar Dormitorio"]


def test_recorrer_lanza_el_reproductor_con_un_doble(app_wx, monkeypatch, catalogo, dialogo_modal, tmp_path):
	lanzados = []

	class ProcesoFalso:
		def vivo(self):
			return True

		def terminar(self, espera=3.0):
			return 0

		def esperar(self, tiempo=None):
			return 0

	def lanzador(argumentos):
		lanzados.append(list(argumentos))
		return ProcesoFalso()

	ventana = crear_ventana(monkeypatch, catalogo, lanzador=lanzador)
	try:
		entorno, _planta, _salon, cocina = piso_minimo()
		ruta = tmp_path / "piso.elab"
		guardar_paquete(ruta, entorno)
		assert ventana.abrir_paquete(ruta)
		ventana.contexto.seleccionar(cocina.id)
		orden(ventana, "recorrer_desde")
		assert len(lanzados) == 1
		argumentos = lanzados[0]
		assert argumentos[:2] == ["--recorrido", str(ruta)]
		assert argumentos[argumentos.index("--sala") + 1].startswith("127.0.0.1:") and "--codigo" in argumentos and "--inicio" in argumentos
		assert ventana._recorrido.activo
		orden(ventana, "recorrer")
		assert len(lanzados) == 1, "no se lanza un segundo reproductor mientras hay uno en marcha"
		orden(ventana, "detener_recorrido")
		assert not ventana._recorrido.activo
	finally:
		if ventana._recorrido is not None:
			ventana._recorrido.detener()
		cerrar_ventana(ventana)


# ── Archivos ─────────────────────────────────────────────────────────────────


def test_cambios_sin_guardar_guardar_no_guardar_y_cancelar(ventana, dialogo_modal, tmp_path):
	entorno, planta, _salon, _cocina = piso_minimo()
	ruta = tmp_path / "piso.elab"
	guardar_paquete(ruta, entorno)
	assert ventana.abrir_paquete(ruta)
	contexto = ventana.contexto
	assert ventana.confirmar_descartar() is True and not dialogo_modal.mostrados, "sin cambios no se pregunta"
	contexto.ejecutar("añadir", lambda: ed.anadir_referencia(contexto.entorno, contexto.entorno.plantas[0], "Reloj", 1, 1))
	assert ventana.GetTitle().startswith("*")
	# Cancelar: la ventana no se cierra.
	dialogo_modal.responder(boton(2))
	ventana.Close()
	procesar_eventos(segundos=0.1)
	assert ventana and contexto.modificado
	pregunta = dialogo_modal.ultimo
	assert pregunta.titulo == "Cambios sin guardar" and {"&Guardar", "&No guardar", "&Cancelar"} <= set(pregunta.textos)
	# No guardar: se sigue adelante sin tocar el fichero.
	dialogo_modal.responder(boton(1))
	assert ventana.confirmar_descartar() is True
	assert not cargar_paquete(ruta).entorno.plantas[0].referencias
	# Guardar: se escribe y se sigue.
	dialogo_modal.responder(boton(0))
	assert ventana.confirmar_descartar() is True and not contexto.modificado
	assert [r.nombre for r in cargar_paquete(ruta).entorno.plantas[0].referencias] == ["Reloj"]
	assert planta.id == contexto.entorno.plantas[0].id


def test_recuperacion_tras_un_cierre_inesperado(app_wx, monkeypatch, catalogo, dialogo_modal, tmp_path):
	primera = crear_ventana(monkeypatch, catalogo)
	ruta = tmp_path / "piso.elab"
	guardar_paquete(ruta, piso_minimo()[0])
	primera.abrir_paquete(ruta)
	contexto = primera.contexto
	contexto.ejecutar("añadir", lambda: ed.anadir_referencia(contexto.entorno, contexto.entorno.plantas[0], "Reloj", 1, 1))
	primera._al_autoguardar(None)
	assert len(archivos.recuperaciones()) == 1 and contexto.modificado, "el autoguardado no toca el documento"
	# El programa «muere» sin cerrar bien: la ventana se destruye sin pasar por el cierre ordenado.
	primera.Destroy()
	procesar_eventos(segundos=0.05)
	segunda = crear_ventana(monkeypatch, catalogo)
	try:
		dialogo_modal.responder(boton(0))
		assert segunda.ofrecer_recuperacion() is True
		assert dialogo_modal.ultimo.titulo == "Recuperar el trabajo" and "&Recuperar" in dialogo_modal.ultimo.textos
		assert [r.nombre for r in segunda.contexto.entorno.plantas[0].referencias] == ["Reloj"]
		assert segunda.contexto.modificado and segunda.contexto.ruta_paquete == ruta
		# Al guardar, la copia de recuperación desaparece.
		assert segunda.guardar() is True and archivos.recuperaciones() == []
	finally:
		cerrar_ventana(segunda)


def test_adoptar_borrador_y_abrir_ejemplo(ventana, dialogo_modal, datos_temporales):
	assert ventana.adoptar_borrador(ejemplos.barrio_ejemplo(), "Barrio") is True
	contexto = ventana.contexto
	assert contexto.modificado and contexto.ruta_paquete is None and contexto.entorno.plantas[0].exterior
	dialogo_modal.responder(boton(2))
	assert ventana.adoptar_borrador(piso_minimo()[0], "Piso") is False, "con Cancelar se conserva el documento abierto"
	assert contexto.entorno.plantas[0].exterior
	# Un ejemplo se abre como documento nuevo: guardar no escribe encima del fichero que viene con el programa.
	carpeta = datos_temporales / "ejemplos"
	carpeta.mkdir(parents=True, exist_ok=True)
	guardar_paquete(carpeta / "vivienda.elab", ejemplos.vivienda_ejemplo())
	assert [nombre for _ruta, nombre in archivos.ejemplos()] == [ejemplos.vivienda_ejemplo().nombre]
	contexto.modificado = False
	assert ventana.abrir_paquete(carpeta / "vivienda.elab", como_ejemplo=True) is True
	assert contexto.ruta_paquete is None and not contexto.modificado
	assert archivos.recientes(contexto.configuracion) == []


def test_fichero_danado_se_explica_y_ofrece_la_copia(ventana, dialogo_modal, tmp_path):
	ruta = tmp_path / "piso.elab"
	guardar_paquete(ruta, piso_minimo()[0])
	guardar_paquete(ruta, piso_minimo()[0])  # la segunda vez deja la copia .bak
	ruta.write_bytes(b"esto no es un zip")
	dialogo_modal.responder(boton(0))
	assert ventana.abrir_paquete(ruta) is True
	assert "copia de seguridad" in " ".join(dialogo_modal.ultimo.textos)
	assert ventana.contexto.entorno.nombre == "Piso mínimo"
	roto = tmp_path / "roto.elab"
	roto.write_bytes(b"nada")
	assert ventana.abrir_paquete(roto) is False and dialogo_modal.ultimo.titulo == "Abrir"


# ── Integración con la otra mitad del Estudio ────────────────────────────────


def _modulo_de_seguimiento(llamadas: list) -> types.ModuleType:
	modulo = types.ModuleType("app.ui.seguimiento.integracion")
	modulo.MENUS_SEGUIMIENTO = [
		(
			N_("A&lumnos"),
			[
				("mostrar_alumnos", N_("&Fichas de alumnos...\tCtrl+L"), N_("Abre las fichas.")),
				None,
				("mostrar_sesiones", N_("&Sesiones..."), N_("Lista las sesiones.")),
				("orden_rota", N_("&Rota"), N_("Falla siempre.")),
			],
		)
	]
	modulo.mostrar_alumnos = lambda contexto: llamadas.append(("alumnos", contexto))
	modulo.mostrar_sesiones = lambda contexto: llamadas.append(("sesiones", contexto))

	def orden_rota(_contexto):
		raise RuntimeError("fallo de la otra mitad")

	modulo.orden_rota = orden_rota

	def crear_panel_actividades(padre, contexto):
		panel = wx.Panel(padre, name="Actividades")
		usadas = contexto.letras_ocupadas()
		assert {"a", "e", "i", "v", "h", "u", "l", "1"} <= usadas, "el panel puede saber qué letras ocupan los menús"
		wx.Button(panel, label="A&ñadir actividad")
		llamadas.append(("panel", contexto))
		return panel

	modulo.crear_panel_actividades = crear_panel_actividades
	modulo.al_cerrar = lambda contexto: llamadas.append(("cerrar", contexto))
	return modulo


def test_integracion_con_seguimiento(app_wx, monkeypatch, catalogo, dialogo_modal):
	llamadas: list = []
	monkeypatch.setattr(vp.VentanaPrincipal, "_cargar_seguimiento", lambda self: _modulo_de_seguimiento(llamadas))
	ventana = vp.VentanaPrincipal(Configuracion(), catalogo=catalogo)
	barra = ventana.GetMenuBar()
	titulos = [barra.GetMenuLabel(i) for i in range(barra.GetMenuCount())]
	assert titulos == ["&Archivo", "&Editar", "&Insertar", "&Ver", "A&lumnos", "&Herramientas", "Ay&uda"]
	assert [ventana.cuaderno.GetPageText(i) for i in range(ventana.cuaderno.GetPageCount())] == ["Entorno", "Descripción", "Actividades"]
	afirmar_teclado_correcto(ventana, teclas_propias=TECLAS_PROPIAS)
	orden(ventana, "mostrar_alumnos")
	orden(ventana, "mostrar_sesiones")
	assert [nombre for nombre, _c in llamadas] == ["panel", "alumnos", "sesiones"]
	assert all(contexto is ventana.contexto for _n, contexto in llamadas)
	orden(ventana, "orden_rota")
	assert ventana and dialogo_modal.ultimo.clase == "DialogoMensaje", "un fallo de la otra mitad se explica y no tira la ventana"
	cerrar_ventana(ventana)
	assert llamadas[-1][0] == "cerrar"


def test_sin_modulo_de_seguimiento_la_ventana_funciona(app_wx, monkeypatch, catalogo):
	try:
		import app.ui.seguimiento as paquete

		monkeypatch.delattr(paquete, "integracion", raising=False)
	except ImportError:
		pass  # ni siquiera existe el paquete: la importación fallará igual
	monkeypatch.setitem(sys.modules, "app.ui.seguimiento.integracion", None)  # importarlo lanza ImportError
	ventana = vp.VentanaPrincipal(Configuracion(), catalogo=catalogo)
	try:
		assert ventana._integracion is None and ventana.panel_actividades is None
		assert ventana.GetMenuBar().GetMenuCount() == 6
	finally:
		cerrar_ventana(ventana)


def test_con_el_modulo_real_de_seguimiento_si_ya_existe(app_wx, catalogo, dialogo_modal):
	"""Si la otra mitad ya está escrita, la ventana la carga y el teclado del conjunto sigue sin choques."""
	try:
		from app.ui.seguimiento import integracion  # noqa: F401
	except ImportError:
		pytest.skip("app.ui.seguimiento.integracion todavía no existe")
	ventana = vp.VentanaPrincipal(Configuracion(), catalogo=catalogo)
	try:
		assert ventana._integracion is not None
		ventana.contexto.abrir_documento(piso_minimo()[0])
		afirmar_teclado_correcto(ventana, teclas_propias=TECLAS_PROPIAS)
	finally:
		cerrar_ventana(ventana)


def test_propiedades_del_entorno_y_descripcion(ventana, dialogo_modal):
	_abrir(ventana, piso_minimo()[0])
	dialogo_modal.responder(rellenar(autor="Ana", descripcion="Piso de prueba"))
	orden(ventana, "propiedades_entorno")
	assert ventana.contexto.entorno.autor == "Ana" and ventana.contexto.entorno.descripcion == "Piso de prueba"
	orden(ventana, "ver_descripcion")
	assert ventana.cuaderno.GetSelection() == 1
	texto = ventana.texto_descripcion.GetValue()
	assert "Salón" in texto and "Cocina" in texto and not ventana.texto_descripcion.IsEditable()
	assert dialogos_insertar.describir(ventana.contexto, ventana.contexto.entorno).startswith("Entorno Piso mínimo")
