"""Sesiones, informes en los tres formatos, cuaderno de evaluación real y punto de integración."""

# ruff: noqa: F811 - las fixtures importadas de _ui_seguimiento_util se usan como parámetros
from __future__ import annotations

import pytest

wx = pytest.importorskip("wx")

from app.seguimiento import cuaderno, informes, sesiones  # noqa: E402
from app.seguimiento.alumnos import Fichas  # noqa: E402
from app.ui.seguimiento import comun, integracion  # noqa: E402
from app.ui.seguimiento import cuaderno as ui_cuaderno  # noqa: E402
from app.ui.seguimiento import informes as ui_informes  # noqa: E402
from app.ui.seguimiento import presentador_registros as pres  # noqa: E402
from app.ui.seguimiento import sesiones as ui_sesiones  # noqa: E402
from app.ui.seguimiento.contexto import ContextoSeguimiento  # noqa: E402
from tests._seguimiento_util import documento_sesion  # noqa: E402
from tests._ui_seguimiento_util import CONTRASENA, elegir, equipo, responder_con, revisar, sin_voz  # noqa: E402, F401


@pytest.fixture
def con_datos(equipo):
	"""Base con dos alumnos y tres sesiones de Luna (dos de juego y un examen) y una de Sol."""
	base = equipo.abrir_base()
	fichas = Fichas(base)
	luna = fichas.alta("Luna", ajustes={"paso_m": 0.5})
	sol = fichas.alta("Sol")
	sesiones.guardar_sesion(
		base, luna.id, documento_sesion("1" * 32, "Luna", inicio="2026-11-10T10:00:00+00:00", fin="2026-11-10T10:05:00+00:00")
	)
	sesiones.guardar_sesion(
		base,
		luna.id,
		documento_sesion(
			"2" * 32,
			"Luna",
			inicio="2026-11-17T10:00:00+00:00",
			fin="2026-11-17T10:04:00+00:00",
			marcas=[{"t": 5.0, "planta": "p0", "x": 5.0, "y": 1.0, "texto": "Duda en la puerta"}],
		),
	)
	sesiones.guardar_sesion(
		base,
		luna.id,
		documento_sesion(
			"3" * 32,
			"Luna",
			inicio="2026-11-20T09:00:00+00:00",
			fin="2026-11-20T09:10:00+00:00",
			actividad="examen",
			modo="examen",
			resumen={"examen": {"puntos": 7}},
		),
	)
	sesiones.guardar_sesion(
		base,
		sol.id,
		documento_sesion("4" * 32, "Sol", inicio="2026-11-18T10:00:00+00:00", fin="2026-11-18T10:05:00+00:00", entorno="colegio"),
	)
	return equipo, base, luna, sol


# ── Lógica ───────────────────────────────────────────────────────────────────


def test_leer_fecha_admite_dos_formas_y_explica_el_error():
	assert pres.leer_fecha("", "Desde") is None
	assert pres.leer_fecha("2026-11-20", "Desde") == "2026-11-20"
	assert pres.leer_fecha("5/3/2026", "Desde") == "2026-03-05"
	with pytest.raises(ValueError, match="Desde"):
		pres.leer_fecha("mañana", "Desde")
	with pytest.raises(ValueError):
		pres.leer_fecha("2026-13-40", "Desde")


def test_buscar_sesiones_con_filtros(con_datos):
	_equipo, base, luna, sol = con_datos
	assert [s["id"][0] for s in pres.buscar_sesiones(base)] == ["3", "4", "2", "1"]
	assert [s["id"][0] for s in pres.buscar_sesiones(base, luna.id)] == ["3", "2", "1"]
	assert [s["id"][0] for s in pres.buscar_sesiones(base, modo="examen")] == ["3"]
	assert [s["id"][0] for s in pres.buscar_sesiones(base, entorno_id="colegio")] == ["4"]
	assert [s["id"][0] for s in pres.buscar_sesiones(base, desde="2026-11-17", hasta="2026-11-18")] == ["4", "2"]
	entornos, actividades = pres.valores_de_filtro(base)
	assert {ident for ident, _n in entornos} == {"casa", "colegio"} and {ident for ident, _n in actividades} == {"buscar", "examen"}


def test_nombre_de_fichero_y_extensiones(tmp_path):
	informe = informes.Informe('Informe de sesión: Casa "nueva"/2', aviso="x")
	assert pres.nombre_de_fichero(informe, "Luna", "html") == "Informe de sesión Casa nueva 2 - Luna.html"
	destino = pres.guardar_informe(informe, tmp_path / "informe", "csv")
	assert destino.name == "informe.csv" and destino.read_bytes().startswith(b"\xef\xbb\xbf")


# ── Sesiones ─────────────────────────────────────────────────────────────────


def test_ventana_de_sesiones_lista_filtra_y_revisa_el_teclado(con_datos):
	equipo, _base, luna, _sol = con_datos
	ventana = ui_sesiones.VentanaSesiones(equipo.contexto, equipo.servicio)
	revisar(ventana)
	assert ventana.lista.numero_filas() == 4
	assert ventana.lista.valores_fila(0)[1:5] == ["Luna", "Casa de ejemplo", "Buscar la llave", "Examen"]
	elegir(ventana.alumno, "Sol")
	assert [ventana.lista.valores_fila(i)[1] for i in range(ventana.lista.numero_filas())] == ["Sol"]
	elegir(ventana.alumno, "Todos")
	elegir(ventana.modo, "Examen")
	assert ventana.lista.numero_filas() == 1
	elegir(ventana.modo, "Todos")
	ventana.desde.SetValue("17/11/2026")
	ventana.hasta.SetValue("2026-11-18")
	assert ventana.buscar() is True and ventana.lista.numero_filas() == 2
	ventana.hasta.SetValue("ayer")
	assert ventana.buscar() is False
	ventana.elegir_alumno(luna.id)
	assert ventana.alumno.GetStringSelection() == "Luna"
	ventana.Destroy()


def test_detalle_de_sesion_notas_cifradas_y_marcas(con_datos, dialogo_modal):
	equipo, base, luna, _sol = con_datos
	sesion = sesiones.obtener(base, "2" * 32)
	dialogo = ui_sesiones.DialogoSesion(equipo.contexto.ventana, base, sesion, equipo.contexto)
	revisar(dialogo)
	resumen = dialogo.resumen.GetValue()
	assert "Informe de sesión" in resumen and "Luna" in resumen and "no equivale a competencia" in resumen
	assert dialogo.marcas.valores_fila(0)[2] == "Duda en la puerta"
	dialogo.notas.SetValue("Hoy estaba cansada")
	dialogo.guardar_notas()
	assert sesiones.obtener(base, "2" * 32)["notas"] == "Hoy estaba cansada"
	dialogo_modal.responder(
		lambda d: (d.campo.SetValue("12,5"), wx.ID_OK)[1], lambda d: (d.campo.SetValue("Se orienta por el frigorífico"), wx.ID_OK)[1]
	)
	dialogo.anadir_marca()
	marcas = sesiones.marcas(base, "2" * 32)
	assert [(m["t"], m["texto"]) for m in marcas] == [(5.0, "Duda en la puerta"), (12.5, "Se orienta por el frigorífico")]
	assert dialogo.marcas.numero_filas() == 2
	dialogo.Destroy()
	equipo.servicio.acceso.bloquear()
	crudo = (equipo.carpeta / "db" / "entornolab.db").read_bytes()
	assert b"Hoy estaba cansada" not in crudo and "Se orienta por el frigorífico".encode() not in crudo
	equipo.servicio.acceso.desbloquear(CONTRASENA)


def test_repetir_el_recorrido_paso_a_paso(con_datos):
	equipo, base, _luna, _sol = con_datos
	sesion = sesiones.obtener(base, "1" * 32)
	dialogo = ui_sesiones.DialogoRecorrido(equipo.contexto.ventana, base, sesion, equipo.contexto)
	revisar(dialogo)
	pasos = dialogo.pasos.GetStrings()
	assert len(pasos) >= 4 and any(paso.startswith("Avanza") and "metros" in paso for paso in pasos)
	assert any("Choca con mesa" in paso for paso in pasos)
	dialogo.pasos.SetSelection(2)
	elegir(dialogo.unidad, "Pasos")
	en_pasos = dialogo.pasos.GetStrings()
	# Con el paso de 0,5 m de la ficha de Luna, 2 metros son 4 pasos (con el de serie, 0,7 m, serían 3).
	assert en_pasos[1] == "Avanza 4 pasos." and dialogo.pasos.GetSelection() == 2
	dialogo.tiempos.SetValue(True)
	dialogo.cargar()
	assert dialogo.pasos.GetString(1)[0].isdigit()
	assert len(dialogo.plano._recorrido) > 10
	dialogo.Destroy()


def test_borrar_una_sesion_pide_confirmacion(con_datos, dialogo_modal):
	equipo, base, _luna, _sol = con_datos
	ventana = ui_sesiones.VentanaSesiones(equipo.contexto, equipo.servicio)
	dialogo_modal.responder(wx.ID_CANCEL)
	ventana.borrar()
	assert len(sesiones.listar(base)) == 4
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	ventana.borrar()
	assert [s["id"][0] for s in sesiones.listar(base)] == ["1", "2", "4"]
	assert ventana.lista.numero_filas() == 3 and "Sesión borrada." in equipo.contexto.anunciados
	ventana.Destroy()


# ── Informes ─────────────────────────────────────────────────────────────────


def test_ventana_de_informes_los_cinco_tipos(con_datos, dialogo_modal):
	equipo, base, luna, _sol = con_datos
	cuaderno.anotar(
		base,
		luna.id,
		fecha="2026-11-25",
		lugar="Casa de la abuela",
		entorno_id="casa",
		entorno_nombre="Casa de ejemplo",
		rutas=[{"nombre": "Entrada a cocina", "resultado": "conseguida"}],
	)
	ventana = ui_informes.VentanaInformes(equipo.contexto, equipo.servicio, luna.id, "2" * 32)
	revisar(ventana)
	assert ventana.alumno.GetStringSelection() == "Luna" and ventana.lista.numero_filas() == 3
	assert ventana.lista.fila_actual() == 1, "queda elegida la sesión pedida"
	assert ventana.generar() is True
	assert ventana.vista.GetValue().startswith("Informe de sesión") and "no diagnostica" in ventana.vista.GetValue()
	# Comparación: sin marcar dos sesiones se explica; marcándolas, sale.
	elegir(ventana.tipo, "Comparación")
	assert ventana.generar() is False
	assert any("dos sesiones" in texto for texto in dialogo_modal.ultimo.textos)
	ventana.lista.CheckItem(1, True)
	ventana.lista.CheckItem(2, True)
	assert ventana.generar() is True and "Comparación de sesiones" in ventana.vista.GetValue()
	for nombre, esperado in (
		("Evolución", "Evolución en el tiempo"),
		("examen", "Informe de examen"),
		("real", "Evaluación real frente a sesiones"),
	):
		elegir(ventana.tipo, nombre)
		ventana.lista.enfocar_fila(0, anunciar=False)
		assert ventana.generar() is True
		assert esperado in ventana.vista.GetValue() and "no equivale a competencia" in ventana.vista.GetValue()
	assert "Casa de la abuela" in ventana.vista.GetValue()
	ventana.Destroy()


def test_guardar_el_informe_en_los_tres_formatos_y_abrirlo(con_datos, monkeypatch, tmp_path):
	equipo, _base, luna, _sol = con_datos
	ventana = ui_informes.VentanaInformes(equipo.contexto, equipo.servicio, luna.id)
	propuestos: list[str] = []

	def pedir(_padre, _titulo, _comodin, nombre=""):
		propuestos.append(nombre)
		return tmp_path / ("informe" + nombre[nombre.rfind(".") :])

	monkeypatch.setattr(ui_informes, "pedir_ruta_guardar", pedir)
	for formato in ("texto", "html", "csv"):
		ventana.guardar(formato)
	assert [nombre[nombre.rfind(".") :] for nombre in propuestos] == [".txt", ".html", ".csv"] and all(
		"Luna" in nombre for nombre in propuestos
	)
	texto = (tmp_path / "informe.txt").read_text(encoding="utf-8")
	html = (tmp_path / "informe.html").read_text(encoding="utf-8")
	csv = (tmp_path / "informe.csv").read_text(encoding="utf-8-sig")
	assert texto == ventana.vista.GetValue()
	assert html.lower().startswith("<!doctype html") and html.count("<h1") == 1 and "<script" not in html
	assert ";" in csv
	for contenido in (texto, html, csv):
		assert "no equivale a competencia en el lugar real" in contenido
	abiertos: list[str] = []
	monkeypatch.setattr(ui_informes, "abrir_navegador", lambda direccion: abiertos.append(direccion) or True)
	ventana.abrir_en_navegador()
	assert abiertos and abiertos[0].startswith("file:") and abiertos[0].endswith(".html")
	temporal = equipo.servicio.temporales[0]
	assert temporal.is_file()
	ventana.Destroy()
	equipo.servicio.cerrar()
	assert not temporal.exists(), "el informe temporal se borra al cerrar"


# ── Cuaderno de evaluación real ──────────────────────────────────────────────


def test_anotar_una_evaluacion_real_con_rutas_y_dias_calculados(con_datos, dialogo_modal):
	equipo, base, luna, _sol = con_datos
	ventana = ui_cuaderno.VentanaCuaderno(equipo.contexto, equipo.servicio, luna.id)
	revisar(ventana)
	dialogo = ui_cuaderno.DialogoEvaluacion(ventana, base, luna, equipo.contexto)
	revisar(dialogo)
	ruta = ui_cuaderno.DialogoRuta(dialogo)
	revisar(ruta)
	assert ruta.validar()[1] is ruta.nombre
	ruta.Destroy()
	dialogo.fecha.SetValue("no es una fecha")
	assert dialogo.validar()[1] is dialogo.fecha
	dialogo.fecha.SetValue("24/11/2026")
	elegir(dialogo.entorno, "Ninguno")
	assert dialogo.validar()[1] is dialogo.lugar
	assert "No hay sesiones anteriores" not in dialogo.dias.GetValue()
	elegir(dialogo.entorno, "Casa de ejemplo")
	assert "4 días" in dialogo.dias.GetValue()
	dialogo.lugar.SetValue("Casa de la abuela")

	def una_ruta(d):
		d.nombre.SetValue("De la entrada a la cocina")
		elegir(d.resultado, "con ayuda")
		d.notas.SetValue("Dudó en el pasillo")

	dialogo_modal.responder(responder_con(una_ruta), responder_con(lambda d: d.nombre.SetValue("De la cocina al baño")))
	dialogo.nueva_ruta()
	dialogo.nueva_ruta()
	assert dialogo.lista.valores_fila(0) == ["De la entrada a la cocina", "Conseguida con ayuda", "Dudó en el pasillo"]
	elegir(dialogo.nivel, "indicaciones verbales")
	elegir(dialogo.tipo, "entrenado en el simulador")
	dialogo.ayudas.SetValue("bastón largo, perro guía")
	dialogo.observaciones.SetValue("Observación reservada")
	assert dialogo.aceptar() is True
	dialogo.Destroy()
	guardada = cuaderno.listar(base, luna.id)[0]
	assert (guardada.fecha, guardada.lugar, guardada.entorno_id) == ("2026-11-24", "Casa de la abuela", "casa")
	assert [r["resultado"] for r in guardada.rutas] == ["con_ayuda", "conseguida"]
	assert (guardada.nivel_ayuda, guardada.tipo_recorrido, guardada.ayudas_movilidad) == (
		"indicacion_verbal",
		"entrenado",
		["bastón largo", "perro guía"],
	)
	assert guardada.dias_desde_entrenamiento == 4 and guardada.observaciones == "Observación reservada"
	ventana.recargar()
	assert ventana.lista.valores_fila(0) == [
		"24/11/2026",
		"Casa de la abuela",
		"Casa de ejemplo",
		"1 de 2 conseguidas sin ayuda, 1 con ayuda",
		"Con indicaciones verbales",
		"4",
	]
	equipo.servicio.acceso.bloquear()
	assert "Observación reservada".encode() not in (equipo.carpeta / "db" / "entornolab.db").read_bytes()
	equipo.servicio.acceso.desbloquear(CONTRASENA)
	ventana.Destroy()


def test_cuaderno_ver_comparar_y_borrar(con_datos, dialogo_modal):
	equipo, base, luna, _sol = con_datos
	cuaderno.anotar(
		base,
		luna.id,
		fecha="2026-11-25",
		lugar="Casa de la abuela",
		entorno_id="casa",
		entorno_nombre="Casa de ejemplo",
		rutas=[{"nombre": "Entrada a cocina", "resultado": "conseguida"}],
		observaciones="Muy segura",
	)
	ventana = ui_cuaderno.VentanaCuaderno(equipo.contexto, equipo.servicio, luna.id)
	assert ventana.lista.numero_filas() == 1
	ventana.ver()
	visto = " ".join(dialogo_modal.ultimo.textos)
	assert "Casa de la abuela" in visto and "Muy segura" in visto and "no equivale a competencia" in visto
	ventana.comparar()
	comparado = " ".join(dialogo_modal.ultimo.textos)
	assert "Evaluación real frente a sesiones" in comparado and "En el simulador" in comparado
	elegir(ventana.alumno, "Sol")
	assert ventana.lista.numero_filas() == 0
	elegir(ventana.alumno, "Luna")
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	ventana.borrar()
	assert cuaderno.listar(base, luna.id) == [] and ventana.lista.numero_filas() == 0
	ventana.Destroy()


# ── Punto de integración ─────────────────────────────────────────────────────


def test_menus_de_seguimiento_con_el_formato_documentado():
	titulos = [titulo for titulo, _entradas in integracion.MENUS_SEGUIMIENTO]
	assert titulos == ["A&lumnos", "&Supervisión"]
	atajos: list[str] = []
	for _titulo, entradas in integracion.MENUS_SEGUIMIENTO:
		letras: list[str] = []
		for entrada in entradas:
			if entrada is None:
				continue
			nombre, etiqueta, ayuda = entrada
			assert callable(getattr(integracion, nombre)), nombre
			assert "&" in etiqueta and ayuda.endswith(".")
			letras.append(etiqueta[etiqueta.index("&") + 1].lower())
			if "\t" in etiqueta:
				atajos.append(etiqueta.split("\t")[1])
		assert len(set(letras)) == len(letras), "letras de acceso repetidas en un menú"
	usados_por_la_ventana = {
		"Ctrl+N",
		"Ctrl+O",
		"Ctrl+S",
		"Ctrl+Z",
		"Ctrl+Y",
		"Ctrl+D",
		"Ctrl+M",
		"Ctrl+G",
		"Ctrl+R",
		"Ctrl+F",
		"F1",
		"F2",
		"F4",
		"F5",
		"F6",
		"F8",
		"F9",
	}
	assert len(set(atajos)) == len(atajos) and not set(atajos) & usados_por_la_ventana
	for nombre in (
		"crear_panel_actividades",
		"mostrar_alumnos",
		"mostrar_supervision",
		"mostrar_sesiones",
		"mostrar_informes",
		"mostrar_cuaderno",
		"al_cerrar",
	):
		assert callable(getattr(integracion, nombre))


def test_el_contexto_real_cumple_el_protocolo_si_existe():
	contexto_real = pytest.importorskip("app.ui.contexto")
	contexto = contexto_real.ContextoEstudio()
	assert isinstance(contexto, ContextoSeguimiento)
	assert isinstance(contexto.recursos, dict) and hasattr(contexto, "actividad_actual") and callable(contexto.letras_ocupadas)


def test_integracion_abre_cada_ventana_una_sola_vez_y_cierra_todo(con_datos, dialogo_modal):
	equipo, _base, luna, _sol = con_datos
	contexto = equipo.contexto
	assert comun.mostrar_al_abrir is False
	alumnos = integracion.mostrar_alumnos(contexto)
	assert integracion.mostrar_alumnos(contexto) is alumnos
	sesiones_ventana = integracion.mostrar_sesiones(contexto, alumno_id=luna.id)
	assert sesiones_ventana.alumno.GetStringSelection() == "Luna"
	informes_ventana = integracion.mostrar_informes(contexto, alumno_id=luna.id, sesion_id="1" * 32)
	cuaderno_ventana = integracion.mostrar_cuaderno(contexto, alumno_id=luna.id)
	supervision = integracion.mostrar_supervision(contexto)
	assert set(equipo.servicio.ventanas) == {"alumnos", "sesiones", "informes", "cuaderno", "supervision"}
	for ventana in (alumnos, sesiones_ventana, informes_ventana, cuaderno_ventana, supervision):
		assert isinstance(ventana, wx.Frame) and not ventana.IsShown()
	# Desde la ventana de alumnos se abren las demás con el alumno elegido.
	alumnos.lista.enfocar_fila(1, anunciar=False)
	alumnos.abrir("sesiones")
	assert sesiones_ventana.alumno.GetStringSelection() == "Sol"
	panel = integracion.crear_panel_actividades(contexto.ventana, contexto)
	assert isinstance(panel, wx.Window)
	equipo.servicio.sala.asegurar_local()
	proceso = equipo.servicio.lanzar(["casa.elab"])
	integracion.bloquear_datos(contexto)
	assert equipo.servicio.acceso.base is None and set(equipo.servicio.ventanas) == {"supervision"}
	integracion.al_cerrar(contexto)
	assert proceso.terminado and not equipo.servicio.sala.activa and equipo.servicio.ventanas == {}
	integracion.al_cerrar(contexto)


def test_sin_contrasena_no_se_abren_las_ventanas_de_datos(equipo, dialogo_modal):
	dialogo_modal.responder(wx.ID_CANCEL, wx.ID_CANCEL)
	assert integracion.mostrar_alumnos(equipo.contexto) is None
	assert integracion.mostrar_sesiones(equipo.contexto) is None
	assert equipo.servicio.ventanas == {}
	# La supervisión no necesita la contraseña.
	assert integracion.mostrar_supervision(equipo.contexto) is not None


# ── Con la ventana principal de verdad ───────────────────────────────────────


def test_enganche_en_la_ventana_principal_real(app_wx, monkeypatch, sin_voz, dialogo_modal):
	"""La ventana principal real carga los menús y la pestaña de actividades sin choques de teclado por esta parte."""
	util = pytest.importorskip("tests._ui_estudio_util")
	from app.ui.accesibilidad.revision_teclado import revisar_teclado
	from app.ui.seguimiento.panel_actividades import PanelActividades

	ventana = util.crear_ventana(monkeypatch, con_seguimiento=True)
	try:
		barra = ventana.GetMenuBar()
		titulos = [barra.GetMenuLabel(indice) for indice in range(barra.GetMenuCount())]
		assert "A&lumnos" in titulos and "&Supervisión" in titulos
		letras_menus = [titulo[titulo.index("&") + 1].lower() for titulo in titulos]
		assert len(set(letras_menus)) == len(letras_menus), "dos menús de la barra comparten letra"
		paneles = [hijo for hijo in ventana.cuaderno.GetChildren() if isinstance(hijo, PanelActividades)]
		assert len(paneles) == 1, "la pestaña Actividades no se ha creado"
		panel = paneles[0]
		letras_panel = {boton.GetLabel()[boton.GetLabel().index("&") + 1].lower() for boton in panel.botones.values()}
		assert not letras_panel & set(letras_menus)
		propios = ("Alumnos", "Supervisión", "Actividades de este entorno", *[boton.GetLabelText() for boton in panel.botones.values()])
		problemas = [str(problema) for problema in revisar_teclado(ventana) if not problema.aviso]
		mios = [
			problema
			for problema in problemas
			if any(f"«{texto}" in problema for texto in propios) or "Ctrl+L" in problema or "F7" in problema
		]
		assert mios == []
		# Las órdenes de menú llegan a este módulo con el contexto de la ventana.
		for nombre in ("mostrar_supervision",):
			util.orden(ventana, nombre)
		assert "supervision" in integracion.obtener_servicio(ventana.contexto).ventanas
	finally:
		util.cerrar_ventana(ventana)


def test_texto_largo_en_un_campo_de_solo_lectura(equipo, ayudas_wx):
	dialogo = comun.DialogoLectura(equipo.contexto.ventana, "Comprobación", "&Resultado:", "Primera línea.\nSegunda línea.")
	revisar(dialogo)
	assert not dialogo.campo.IsEditable() and dialogo.campo.IsMultiLine()
	assert dialogo.campo.GetValue().splitlines() == ["Primera línea.", "Segunda línea."]
	# Escape lo cierra y Control+H no se traga el resto del teclado.
	assert ayudas_wx.simular_tecla(dialogo, wx.WXK_ESCAPE).gestionado
	assert ayudas_wx.simular_tecla(dialogo, "x").saltado
	dialogo.Destroy()


def test_escape_y_control_h_en_las_ventanas_no_modales(con_datos, ayudas_wx, sin_voz):
	equipo, _base, _luna, _sol = con_datos
	ventana = integracion.mostrar_sesiones(equipo.contexto)
	assert ayudas_wx.simular_tecla(ventana, "h", ctrl=True).gestionado
	assert sin_voz, "Control+H dice la ayuda del control enfocado (o que no hay ninguno)"
	assert ayudas_wx.simular_tecla(ventana, wx.WXK_TAB).saltado, "las teclas que no se atienden siguen su camino"
	assert ayudas_wx.simular_tecla(ventana, wx.WXK_ESCAPE).gestionado
	ayudas_wx.esperar_hasta(lambda: "sesiones" not in equipo.servicio.ventanas, mensaje="Escape no ha cerrado la ventana")


@pytest.mark.interfaz
def test_foco_inicial_real_de_la_ventana_de_alumnos(con_datos, ayudas_wx, monkeypatch):
	"""Con la ventana a la vista: el foco inicial cae en la lista de alumnos y hay un alumno enfocado."""
	equipo, _base, _luna, _sol = con_datos
	monkeypatch.setattr(comun, "mostrar_al_abrir", True)
	ventana = integracion.mostrar_alumnos(equipo.contexto)
	try:
		assert ventana.IsShown()
		ayudas_wx.esperar_hasta(
			lambda: wx.Window.FindFocus() is ventana.lista or not ventana.IsActive(), mensaje="el foco inicial no ha llegado a la lista"
		)
		if not ventana.IsActive():
			pytest.skip("la ventana de pruebas no está en primer plano; no se puede comprobar el foco real")
		assert ventana.lista.GetFocusedItem() == 0
	finally:
		ventana.Destroy()
