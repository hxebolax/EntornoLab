"""Pruebas del diálogo de Preferencias y de su tabla declarativa (sin mostrarlo; sin abrir dispositivos de sonido)."""

from __future__ import annotations

import pytest

wx = pytest.importorskip("wx")

from app.core import i18n  # noqa: E402
from app.core.configuracion import VALORES_POR_DEFECTO, Configuracion  # noqa: E402
from app.ui import esquema_preferencias as esquema  # noqa: E402
from app.ui import preferencias as ui  # noqa: E402
from app.ui.accesibilidad.revision_teclado import afirmar_teclado_correcto  # noqa: E402
from app.ui.contexto import ContextoEstudio  # noqa: E402


PAQUETES = [
	{
		"id": "por_defecto",
		"nombre": "De serie",
		"descripcion": "Sonidos sintetizados",
		"completo": True,
		"total": 120,
		"sonidos": 120,
		"defecto": True,
	},
	{
		"id": "natural",
		"nombre": "Natural",
		"descripcion": "Sonidos grabados",
		"completo": False,
		"total": 120,
		"sonidos": 40,
		"defecto": False,
	},
]


@pytest.fixture(autouse=True)
def _listas_fijas(monkeypatch):
	"""Las listas que dependen del equipo se fijan: la prueba no enumera salidas, voces ni paquetes reales."""
	monkeypatch.setattr(
		esquema,
		"motores",
		lambda: [("openal", "Binaural"), ("clasico", "Clásico"), ("estereo", "Estéreo"), ("bass", "BASS"), ("nulo", "Sin sonido")],
	)
	monkeypatch.setattr(esquema, "dispositivos", lambda: [("", "La predeterminada de Windows"), ("Auriculares", "Auriculares")])
	monkeypatch.setattr(esquema, "segundas_salidas", lambda: [("", "Ninguna"), ("Altavoces", "Altavoces")])
	monkeypatch.setattr(esquema, "perfiles_hrtf", lambda: [("", "La integrada"), ("kemar_oreja_grande", "Maniquí con oreja grande")])
	monkeypatch.setattr(esquema, "lista_paquetes", lambda: [dict(paquete) for paquete in PAQUETES])
	monkeypatch.setattr(esquema, "voces_sapi", lambda: [("", "La predeterminada de Windows"), ("Helena", "Helena")])
	monkeypatch.setattr(esquema, "idiomas", lambda: [("auto", "El de Windows"), ("es", "Español"), ("en", "English")])


@pytest.fixture
def config(data_temporal) -> Configuracion:
	return Configuracion()


@pytest.fixture
def dialogo(app_wx, config):
	instancia = ui.DialogoPreferencias(None, config)
	yield instancia
	instancia.Destroy()


# ── Tabla ────────────────────────────────────────────────────────────────────


def test_todas_las_claves_tienen_campo_o_son_internas():
	con_campo = {campo.clave for campo in esquema.CAMPOS if esquema.es_clave_de_configuracion(campo.clave)}
	todas = {f"{seccion}.{clave}" for seccion, valores in VALORES_POR_DEFECTO.items() for clave in valores}
	sin_campo = sorted(clave for clave in todas - con_campo if not esquema.es_interna(clave))
	assert sin_campo == [], f"preferencias sin campo en el diálogo: {sin_campo}"
	assert con_campo <= todas, f"campos de claves que no existen: {sorted(con_campo - todas)}"
	assert not {clave for clave in con_campo if esquema.es_interna(clave)}, "una clave interna no lleva campo"
	restablecer = {
		campo.clave[len(esquema.PREFIJO_RESTABLECER) :] for campo in esquema.CAMPOS if campo.clave.startswith(esquema.PREFIJO_RESTABLECER)
	}
	assert restablecer == {"teclado.mapa", "mando.mapa", "editor.recientes"} and restablecer <= todas


def test_todas_las_secciones_tienen_pestana_y_las_claves_pedidas_estan():
	secciones = {campo.clave.split(".")[0] for campo in esquema.CAMPOS if esquema.es_clave_de_configuracion(campo.clave)}
	assert secciones == set(VALORES_POR_DEFECTO) - {"ventana", "teclado"}
	claves = {campo.clave for campo in esquema.CAMPOS}
	for clave in (
		"sonido.motor",
		"sonido.perfil_hrtf",
		"sonido.paquete",
		"sonido.dispositivo",
		"sonido.segunda_salida",
		"importar.overpass_url",
		"importar.nominatim_url",
		"general.idioma",
	):
		assert clave in claves
	volumenes = [campo for campo in esquema.CAMPOS if campo.clave.startswith("sonido.volumen_")]
	assert len(volumenes) == 8 and all(campo.tipo == "deslizador" for campo in volumenes)


def test_las_listas_cerradas_ofrecen_justo_lo_que_admite_la_regla(config):
	"""Si alguien añade una opción a una regla de la configuración, tiene que aparecer en Preferencias."""
	for campo in esquema.CAMPOS:
		regla = config.regla(campo.clave) if esquema.es_clave_de_configuracion(campo.clave) else None
		if campo.tipo == "opcion" and regla is not None and regla.opciones is not None and not callable(campo.opciones):
			assert {valor for valor, _texto in campo.opciones} == set(regla.opciones), campo.clave


def test_conversiones_entre_formulario_y_configuracion(config):
	por_clave = {campo.clave: campo for campo in esquema.CAMPOS}
	volumen = por_clave["sonido.volumen_ambiente"]
	assert esquema.a_formulario(volumen, 0.7) == 70 and esquema.a_configuracion(volumen, 35) == pytest.approx(0.35)
	canales = por_clave["voz.canales"]
	assert esquema.a_formulario(canales, {"juego": True, "ayuda": False, "aviso": True, "profesional": True}) == [
		"juego",
		"aviso",
		"profesional",
	]
	assert esquema.a_configuracion(canales, ["juego"]) == {"juego": True, "ayuda": False, "aviso": False, "profesional": False}
	con_limites = {campo.clave: campo for campo in esquema.campos_preferencias(config)}
	assert (con_limites["juego.paso_m"].minimo, con_limites["juego.paso_m"].maximo) == (0.2, 2.0)
	assert con_limites["importar.radio_m"].maximo == 400


# ── Diálogo ──────────────────────────────────────────────────────────────────


def test_teclado_de_cada_pestana(dialogo):
	cuaderno = dialogo.cuaderno()
	assert cuaderno is not None and cuaderno.GetPageCount() == 10
	for pagina in range(cuaderno.GetPageCount()):
		cuaderno.SetSelection(pagina)
		afirmar_teclado_correcto(dialogo)
	etiquetas = {hijo.GetLabel() for hijo in dialogo.GetChildren() if isinstance(hijo, wx.Button)}
	assert etiquetas == {"&Aceptar", "&Cancelar", "A&plicar", "&Valores de fábrica..."}
	assert dialogo.GetEscapeId() == wx.ID_CANCEL


def test_controles_nativos_con_etiqueta_y_ayuda(dialogo):
	for clave, control in dialogo.formulario.controles.items():
		assert not isinstance(control, (wx.SpinCtrlDouble, wx.SearchCtrl)), clave
		assert control.GetHelpText(), f"{clave} sin ayuda para Control+H"
		if not isinstance(control, wx.CheckBox):
			hermanos = list(control.GetParent().GetChildren())
			anterior = hermanos[hermanos.index(control) - 1]
			assert isinstance(anterior, wx.StaticText) and "&" in anterior.GetLabel(), clave
	assert isinstance(dialogo.formulario.controles["sonido.volumen_maestro"], wx.Slider)
	assert dialogo.formulario.controles["sonido.volumen_ambiente"].GetValue() == 70
	assert isinstance(dialogo.formulario.controles["juego.paso_m"], wx.TextCtrl)
	assert dialogo.formulario.controles["juego.paso_m"].GetValue() == "0,6"


def test_aceptar_guarda_y_se_relee(dialogo, config):
	dialogo.fijar(
		{
			"sonido.motor": "clasico",
			"sonido.volumen_musica": 25,
			"sonido.dispositivo": "Auriculares",
			"juego.paso_m": "0,75",
			"voz.canales": ["juego", "aviso"],
			"general.alto_contraste": True,
			"importar.overpass_url": "https://overpass.example.org/api/interpreter",
			"editor.carpeta_entornos": "",
		}
	)
	assert dialogo.aplicar() is True and dialogo.cambios_aplicados is True
	guardada = Configuracion()
	assert guardada.obtener("sonido.motor") == "clasico"
	assert guardada.obtener("sonido.volumen_musica") == pytest.approx(0.25)
	assert guardada.obtener("sonido.dispositivo") == "Auriculares"
	assert guardada.obtener("juego.paso_m") == pytest.approx(0.75)
	assert guardada.obtener("voz.canales") == {"juego": True, "ayuda": False, "aviso": True, "profesional": False}
	assert guardada.obtener("general.alto_contraste") is True
	assert guardada.obtener("importar.overpass_url").startswith("https://overpass.example.org")
	assert guardada.obtener("juego.unidad") == "metros", "lo que no se tocó sigue igual"


def test_aplicar_avisa_a_los_suscriptores_de_la_configuracion(dialogo, config):
	recibidos: list[str] = []
	config.suscribir(lambda clave, _antes, _ahora: recibidos.append(clave), prefijo="editor.")
	dialogo.fijar({"editor.paso_cuadricula": "0,25"})
	assert dialogo.aplicar() is True
	assert recibidos == ["editor.paso_cuadricula"], "se aplica a las ventanas abiertas sin reiniciar"
	recibidos.clear()
	assert dialogo.aplicar() is True and recibidos == [], "aplicar sin cambios no guarda ni avisa"


def test_cancelar_no_cambia_nada(app_wx, config, dialogo_modal):
	contexto = ContextoEstudio(ventana=None, configuracion=config)
	dialogo_modal.responder(lambda d: (d.fijar({"sonido.motor": "estereo", "juego.paso_m": "1,5"}), wx.ID_CANCEL)[1])
	assert ui.mostrar_preferencias(contexto) is False
	assert Configuracion().obtener("sonido.motor") == "openal" and Configuracion().obtener("juego.paso_m") == pytest.approx(0.6)


def test_mostrar_preferencias_aceptando_y_aplicando(app_wx, config, dialogo_modal):
	contexto = ContextoEstudio(ventana=None, configuracion=config)
	dialogo_modal.responder(lambda d: (d.fijar({"juego.unidad": "pasos"}), wx.ID_OK)[1])
	assert ui.mostrar_preferencias(contexto) is True
	assert Configuracion().obtener("juego.unidad") == "pasos"
	# Aplicar y después Cancelar: lo aplicado queda guardado.
	dialogo_modal.responder(lambda d: (d.fijar({"voz.detalle": 3}), d.aplicar(), d.fijar({"voz.detalle": 0}), wx.ID_CANCEL)[3])
	assert ui.mostrar_preferencias(contexto) is True
	assert Configuracion().obtener("voz.detalle") == 3


def test_error_de_validacion_con_el_foco_en_su_campo(dialogo, config, dialogo_modal, monkeypatch):
	enfocados: list[str] = []
	monkeypatch.setattr(dialogo.formulario, "enfocar", lambda clave: enfocados.append(clave))
	dialogo.fijar({"juego.paso_m": "9", "sonido.motor": "clasico"})
	assert dialogo.aplicar() is False
	assert enfocados == ["juego.paso_m"]
	assert "Longitud del paso" in dialogo.ultimo_error and "2" in dialogo.ultimo_error
	assert Configuracion().obtener("sonido.motor") == "openal", "con un error no se guarda nada"
	dialogo.fijar({"juego.paso_m": "medio metro"})
	assert dialogo.aplicar() is False and "número" in dialogo.ultimo_error
	dialogo.fijar({"juego.paso_m": "0,5", "complementos.url_catalogo": "x" * 2000})
	assert dialogo.aplicar() is False
	assert enfocados[-1] == "complementos.url_catalogo" and "demasiado largo" in dialogo.ultimo_error
	dialogo.fijar({"complementos.url_catalogo": ""})
	assert dialogo.aplicar() is True and dialogo.ultimo_error == ""


def test_enfocar_un_campo_abre_su_pestana(dialogo):
	dialogo.formulario.enfocar("importar.radio_m")
	cuaderno = dialogo.cuaderno()
	assert cuaderno.GetPageText(cuaderno.GetSelection()) == "Red y registro"
	assert dialogo.grupo_actual() == esquema.G_RED


def test_valores_de_fabrica_de_una_pestana_o_de_todas(dialogo, config):
	config.establecer_varias({"juego.paso_m": 1.0, "sonido.volumen_voz": 0.3, "editor.autoguardado_min": 30})
	dialogo.fijar(esquema.valores_de_formulario(config))
	dialogo.ir_a_grupo(esquema.G_JUEGO)
	dialogo.valores_de_fabrica(ui.ALCANCE_PESTANA)
	assert dialogo.formulario.controles["juego.paso_m"].GetValue() == "0,6"
	assert dialogo.formulario.controles["sonido.volumen_voz"].GetValue() == 30, "las otras pestañas no cambian"
	assert config.obtener("juego.paso_m") == 1.0, "no se guarda hasta aceptar o aplicar"
	dialogo.valores_de_fabrica(ui.ALCANCE_TODO)
	assert dialogo.formulario.controles["sonido.volumen_voz"].GetValue() == 100
	assert dialogo.aplicar() is True
	guardada = Configuracion()
	assert guardada.obtener("juego.paso_m") == pytest.approx(0.6) and guardada.obtener("editor.autoguardado_min") == 5


def test_pregunta_de_valores_de_fabrica_dice_la_accion(dialogo, dialogo_modal, config):
	pregunta = dialogo.crear_pregunta_fabrica()
	try:
		afirmar_teclado_correcto(pregunta)
		etiquetas = [hijo.GetLabel() for hijo in pregunta.GetChildren()[0].GetChildren() if isinstance(hijo, wx.Button)]
		assert etiquetas == ["&Solo esta pestaña", "&Todas las pestañas", "&Cancelar"]
	finally:
		pregunta.Destroy()
	config.establecer("juego.paso_m", 1.0)
	dialogo.fijar({"juego.paso_m": 1.0})
	dialogo_modal.responder(wx.ID_CANCEL)
	dialogo._al_fabrica()
	assert dialogo.formulario.controles["juego.paso_m"].GetValue() == "1"
	dialogo_modal.responder(lambda d: d.ids_opciones[1])
	dialogo._al_fabrica()
	assert dialogo.formulario.controles["juego.paso_m"].GetValue() == "0,6"


def test_restablecer_mapas_y_recientes_al_aceptar(dialogo, config):
	config.establecer_varias({"teclado.mapa": {"juego": {"avanzar": ["W"]}}, "editor.recientes": ["a.elab", "b.elab"]})
	dialogo.fijar({esquema.PREFIJO_RESTABLECER + "teclado.mapa": True, esquema.PREFIJO_RESTABLECER + "editor.recientes": True})
	assert dialogo.aplicar() is True
	guardada = Configuracion()
	assert guardada.obtener("teclado.mapa") == {} and guardada.obtener("editor.recientes") == []
	assert dialogo.formulario.controles[esquema.PREFIJO_RESTABLECER + "teclado.mapa"].GetValue() is False, "la casilla vuelve a su sitio"


def test_cambio_de_idioma_se_aplica_y_avisa_si_hace_falta_reiniciar(dialogo, config, dialogo_modal, monkeypatch):
	pedidos: list[str] = []
	monkeypatch.setattr(i18n, "cambiar_idioma", lambda codigo: pedidos.append(codigo) or True)
	monkeypatch.setattr(i18n, "necesita_reinicio", lambda: True)
	dialogo.fijar({"general.idioma": "en"})
	assert dialogo.aplicar() is True
	assert pedidos == ["en"] and Configuracion().obtener("general.idioma") == "en"
	assert "reinicie" in " ".join(dialogo_modal.ultimo.textos)
	monkeypatch.setattr(i18n, "cambiar_idioma", lambda codigo: False)
	dialogo.fijar({"general.idioma": "es"})
	assert dialogo.aplicar() is True
	assert "sigue en español" in " ".join(dialogo_modal.ultimo.textos)


def test_valor_guardado_que_ya_no_esta_en_la_lista_no_se_pierde(app_wx, config):
	config.establecer("sonido.dispositivo", "Altavoz desconectado")
	dialogo = ui.DialogoPreferencias(None, config)
	try:
		control = dialogo.formulario.controles["sonido.dispositivo"]
		assert "Altavoz desconectado" in control.GetStringSelection()
		assert dialogo.aplicar() is True
		assert config.obtener("sonido.dispositivo") == "Altavoz desconectado"
	finally:
		dialogo.Destroy()


# ── Paquete de sonidos ───────────────────────────────────────────────────────


def test_paquete_de_sonidos_lista_descripcion_y_boton(dialogo):
	lista = dialogo.formulario.controles["sonido.paquete"]
	descripcion = dialogo.formulario.controles[esquema.NOTA_PAQUETE]
	assert isinstance(lista, wx.Choice) and lista.GetStrings() == ["De serie", "Natural"]
	assert isinstance(descripcion, wx.TextCtrl) and not descripcion.IsEditable()
	hermanos = list(descripcion.GetParent().GetChildren())
	assert isinstance(hermanos[hermanos.index(descripcion) - 1], wx.StaticText), "la descripción lleva su etiqueta delante"
	assert "De serie" in descripcion.GetValue() and "trae los 120 sonidos" in descripcion.GetValue()
	boton = dialogo.boton_muestra
	assert boton is not None and boton.GetParent() is lista.GetParent()
	assert "&" in boton.GetLabel() and boton.GetHelpText()
	assert "sonido.igualar_paquetes" in dialogo.formulario.controles
	dialogo.ir_a_grupo(esquema.G_SONIDO)
	afirmar_teclado_correcto(dialogo)


def test_la_descripcion_sigue_a_la_eleccion(dialogo, ayudas_wx):
	lista = dialogo.formulario.controles["sonido.paquete"]
	descripcion = dialogo.formulario.controles[esquema.NOTA_PAQUETE]
	lista.SetSelection(1)
	ayudas_wx.enviar_orden(lista, wx.wxEVT_CHOICE)
	assert "Natural" in descripcion.GetValue() and "40 de 120" in descripcion.GetValue()
	dialogo.fijar({"sonido.paquete": "por_defecto"})
	assert "De serie" in descripcion.GetValue()
	dialogo.fijar({"sonido.paquete": "natural"})
	dialogo.valores_de_fabrica(ui.ALCANCE_TODO)
	assert dialogo.paquete_elegido() == "por_defecto" and "De serie" in descripcion.GetValue()


def test_escuchar_una_muestra_llama_con_el_paquete_elegido_y_tolera_el_fallo(app_wx, config, ayudas_wx):
	pedidos: list[str] = []
	dichos: list[str] = []

	def escuchar(identificador: str) -> int:
		pedidos.append(identificador)
		if identificador == "natural":
			raise OSError("no hay dispositivo de sonido")
		return 7

	dialogo = ui.DialogoPreferencias(None, config, escuchar=escuchar, anunciar=dichos.append)
	try:
		ayudas_wx.enviar_orden(dialogo.boton_muestra)
		assert pedidos == ["por_defecto"] and dichos == []
		dialogo.fijar({"sonido.paquete": "natural"})
		ayudas_wx.enviar_orden(dialogo.boton_muestra)
		assert pedidos == ["por_defecto", "natural"]
		assert len(dichos) == 1 and "No se puede escuchar" in dichos[0]
		assert config.obtener("sonido.paquete") == "por_defecto", "escuchar no elige el paquete"
	finally:
		dialogo.Destroy()


def test_aceptar_guarda_el_paquete_elegido(dialogo, config):
	recibidos: list[tuple[str, object]] = []
	config.suscribir(lambda clave, _antes, ahora: recibidos.append((clave, ahora)), prefijo="sonido.")
	dialogo.fijar({"sonido.paquete": "natural", "sonido.igualar_paquetes": False})
	assert dialogo.aplicar() is True
	guardada = Configuracion()
	assert guardada.obtener("sonido.paquete") == "natural" and guardada.obtener("sonido.igualar_paquetes") is False
	assert ("sonido.paquete", "natural") in recibidos, "quien tenga un banco conectado en este proceso cambia en el acto"


def test_paquete_guardado_que_ya_no_esta_instalado_se_explica(app_wx, config):
	config.establecer("sonido.paquete", "desaparecido")
	dialogo = ui.DialogoPreferencias(None, config, escuchar=lambda _id: 0, anunciar=lambda _t: None)
	try:
		assert "no está instalado" in dialogo.formulario.controles[esquema.NOTA_PAQUETE].GetValue()
	finally:
		dialogo.Destroy()


# ── Salida de voz ────────────────────────────────────────────────────────────


def test_salida_de_voz_con_cuatro_valores_y_su_ayuda(dialogo, config, monkeypatch):
	"""«Salida de voz» ofrece las cuatro salidas con nombre claro; elegir «Sin voz» calla al Estudio al momento."""
	from app.core import voz

	control = dialogo.formulario.controles["voz.salida"]
	assert isinstance(control, wx.Choice)
	assert [control.GetString(i) for i in range(control.GetCount())] == [
		"Automática: el lector de pantalla y, si no hay, la voz de Windows",
		"Solo el lector de pantalla, nunca la voz de Windows",
		"Siempre la voz de Windows (SAPI)",
		"Sin voz: no hablar nunca",
	]
	assert control.GetSelection() == 0, "de serie, la automática"
	ayuda = control.GetHelpText()
	for fragmento in ("Automática", "Solo el lector de pantalla", "Siempre la voz de Windows", "Sin voz", "historial", "braille"):
		assert fragmento in ayuda
	dialogo.ir_a_grupo(esquema.G_VOZ)
	afirmar_teclado_correcto(dialogo)
	cancelar = voz.aplicar_configuracion(config)
	try:
		dialogo.fijar({"voz.salida": "ninguna"})
		assert dialogo.aplicar() is True
		assert Configuracion().obtener("voz.salida") == "ninguna"
		assert voz.salida_actual() == "ninguna", "la voz del Estudio sigue a la preferencia sin reiniciar"
	finally:
		cancelar()
		voz.configurar(salida="automatica")
