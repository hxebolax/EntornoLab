"""Editor de actividades: formulario generado del esquema, premios, objetivos, ayudas y panel de la pestaña."""

# ruff: noqa: F811 - las fixtures importadas de _ui_seguimiento_util se usan como parámetros
from __future__ import annotations

import time

import pytest

wx = pytest.importorskip("wx")

from app.dominio import formato  # noqa: E402
from app.seguimiento.alumnos import Fichas  # noqa: E402
from app.supervision.cliente import ClienteSupervision  # noqa: E402
from app.ui.seguimiento import actividades_api as api  # noqa: E402
from app.ui.seguimiento import campos, editor_ayudas, editor_objetivos, editor_premios, lugares, panel_actividades, selector_lugar  # noqa: E402
from app.ui.seguimiento import presentador_actividades as pres  # noqa: E402
from app.ui.seguimiento import presentador_alumnos  # noqa: E402
from app.ui.seguimiento import reserva_actividades as reserva  # noqa: E402
from app.ui.seguimiento.formulario_actividad import DialogoActividad  # noqa: E402
from app.ui.seguimiento.textos import Letras, letra_de  # noqa: E402
from tests._ui_seguimiento_util import casa, elegir, equipo, responder_con, revisar, sin_voz  # noqa: E402, F401


@pytest.fixture
def con_reserva(monkeypatch):
	"""Fuerza el esquema de prueba (el de reserva), exista o no ``app.actividades``."""
	monkeypatch.setattr(api, "_real", lambda nombre: None)


def _armario(entorno):
	return next(objeto for objeto in entorno.plantas[0].objetos if objeto.nombre == "Armario")


# ── Lógica ───────────────────────────────────────────────────────────────────


def test_letras_no_se_repiten_y_respetan_las_reservadas():
	letras = Letras("ac")
	etiquetas = [letras.poner(texto) for texto in ("Aceptar todo", "Cancelar algo", "Casa", "Árbol", "Nombre:", "Nombre:")]
	usadas = [letra_de(etiqueta) for etiqueta in etiquetas]
	assert len(set(usadas)) == len(usadas)
	assert "a" not in usadas and "c" not in usadas
	assert letras.poner("&Guardar") == "&Guardar"
	# Sin letras libres se recurre a un número.
	agotadas = Letras("abcdefghijklmnñopqrstuvwxyz")
	assert agotadas.poner("Nombre:") == "Nombre (&1):"


def test_condicion_cumplida_en_todas_sus_formas():
	datos = {"usar_niveles": True, "travieso": {"activo": False}, "modo": "juego"}
	assert pres.condicion_cumplida(None, datos)
	assert pres.condicion_cumplida("usar_niveles", datos)
	assert not pres.condicion_cumplida("travieso.activo", datos)
	assert pres.condicion_cumplida("modo=juego", datos) and not pres.condicion_cumplida("modo!=juego", datos)
	assert pres.condicion_cumplida(("modo", ["juego", "practica"]), datos)
	assert not pres.condicion_cumplida({"modo": "examen"}, datos)
	assert pres.clave_de_dependencia("modo!=juego") == "modo"


def test_campo_de_aviso_deduce_el_campo():
	claves = ["nombre", "premios", "destino", "mensajes.inicio"]
	assert pres.campo_de_aviso(reserva.Aviso("error", "nombre_vacio", "x", "nombre"), claves) == "nombre"
	assert pres.campo_de_aviso(reserva.Aviso("aviso", "premio_fuera", "x"), claves) == "premios"
	assert pres.campo_de_aviso(reserva.Aviso("error", "destino_inexistente", "x"), claves) == "destino"
	assert pres.campo_de_aviso(reserva.Aviso("error", "otra_cosa", "x"), claves) is None


def test_duplicar_y_mover():
	actividades = [{"id": "buscar", "nombre": "Buscar"}, {"id": "buscar-2", "nombre": "Otra"}]
	copia = pres.duplicar(actividades[0], actividades)
	assert copia["id"] == "buscar-3" and copia["nombre"] == "Copia de Buscar"
	assert pres.mover(actividades, 0, 1) == 1 and actividades[1]["id"] == "buscar"
	assert pres.mover(actividades, 1, 1) == 1


def test_lugares_en_palabras():
	entorno, catalogo = casa()
	planta = entorno.plantas[0]
	dormitorio = next(e for e in planta.espacios if e.nombre == "Dormitorio")
	armario = _armario(entorno)
	assert [o.nombre for o in lugares.contenedores(planta, dormitorio, catalogo)] == ["Armario"]
	assert lugares.describir_punto(entorno, planta.id, armario.x, armario.y, armario.id) == "Dormitorio, dentro de Armario"
	x, y = lugares.calcular_punto(dormitorio, lugares.JUNTO, next(o for o in planta.objetos if o.nombre == "Mesa"))
	assert dormitorio.contiene(x, y)
	assert lugares.describir_punto(entorno, planta.id, x, y) == "Dormitorio, junto a Mesa"
	for esquina in lugares.ESQUINAS:
		punto = lugares.calcular_punto(dormitorio, lugares.ESQUINA, esquina=esquina)
		assert dormitorio.contiene(*punto)
	assert "fuera de todos los espacios" in lugares.describir_punto(entorno, planta.id, 50.0, 50.0)
	assert lugares.describir_elemento(entorno, "no-existe").startswith("El elemento")


def test_ayudas_tres_estados():
	reglas: dict = {}
	pres.cambiar_ayuda(reglas, "baliza", pres.PROHIBIDA)
	pres.cambiar_ayuda(reglas, "pista", pres.PERMITIDA, 3)
	assert pres.fila_ayuda("baliza", reglas["baliza"])[1:] == ["Prohibida", ""]
	assert pres.fila_ayuda("pista", reglas["pista"])[1:] == ["Permitida", "3"]
	assert pres.fila_ayuda("eco", None)[1] == "Como en la ficha del alumno"
	pres.cambiar_ayuda(reglas, "baliza", pres.SIN_INDICAR)
	assert "baliza" not in reglas
	assert pres.estado_ayuda(False) == pres.PROHIBIDA and pres.regla_completa(2) == {"permitida": True, "limite": 2}
	assert len(pres.niveles_de_serie()) == 4


# ── Selectores ───────────────────────────────────────────────────────────────


def test_panel_lugar_dentro_de_un_objeto_y_errores(equipo, marco):
	entorno, catalogo = equipo.contexto.entorno, equipo.contexto.catalogo
	dialogo = selector_lugar.DialogoLugar(marco, entorno, catalogo, con_contenedores=True, con_rumbo=True)
	revisar(dialogo)
	panel = dialogo.lugar
	elegir(panel.espacio, "Dormitorio")
	assert panel.modo_elegido() == lugares.DENTRO
	assert panel.elemento.GetStrings() == ["Armario"]
	valor = panel.leer()
	assert valor["dentro_de"] == _armario(entorno).id
	assert "dentro de Armario" in panel.descripcion.GetValue()
	# En la cocina no hay contenedores: se explica y se señala qué cambiar.
	elegir(panel.espacio, "Cocina")
	with pytest.raises(selector_lugar.ErrorLugar) as error:
		panel.leer()
	assert error.value.control is panel.modo
	assert dialogo.aceptar() is False
	elegir(panel.modo, "centro")
	assert not panel.elemento.IsShown() and not panel.x.IsShown()
	assert dialogo.aceptar() is True and dialogo.valor["dentro_de"] is None and "rumbo" in dialogo.valor
	dialogo.Destroy()


def test_panel_lugar_coordenadas_y_cargar_un_punto(equipo, marco, dialogo_modal):
	entorno = equipo.contexto.entorno
	dialogo = selector_lugar.DialogoLugar(
		marco, entorno, None, valor={"planta": entorno.plantas[0].id, "x": 6.0, "y": 2.0, "rumbo": 90.0}, con_rumbo=True
	)
	panel = dialogo.lugar
	assert panel.espacio.GetStringSelection() == "Cocina" and panel.modo_elegido() == lugares.COORDENADAS
	assert panel.leer()["rumbo"] == 90.0
	panel.x.SetValue("abc")
	assert dialogo.validar()[1] is panel.x
	panel.x.SetValue("6,5")
	assert panel.leer()["x"] == 6.5
	dialogo.Destroy()


def test_dialogo_elemento_por_clases(equipo, marco):
	entorno, catalogo = equipo.contexto.entorno, equipo.contexto.catalogo
	premios = [{"id": "premio-1", "nombre": "Llave", "planta": entorno.plantas[0].id, "x": 1.0, "y": 1.0}]
	dialogo = selector_lugar.DialogoElemento(marco, entorno, catalogo, ["espacio", "objeto", "salida"], premios=premios)
	revisar(dialogo)
	assert set(dialogo.lista.GetStrings()) == {"Dormitorio", "Cocina"}
	elegir(dialogo.clase, "Objetos")
	assert set(dialogo.lista.GetStrings()) == {"Armario", "Mesa"}
	elegir(dialogo.espacio, "Cocina")
	assert dialogo.lista.GetCount() == 0 and dialogo.validar() is not None
	elegir(dialogo.clase, "Salidas")
	elegir(dialogo.espacio, "Todos")
	assert dialogo.lista.GetStrings() == ["Puerta de la calle"]
	elegir(dialogo.clase, "Premios")
	assert dialogo.lista.GetStrings() == ["Premio «Llave»"]
	assert dialogo.aceptar() is True and dialogo.valor == "premio-1"
	dialogo.Destroy()


# ── Premios ──────────────────────────────────────────────────────────────────


def test_dialogo_premio_dentro_de_un_objeto_con_audio(equipo, marco, tmp_path, dialogo_modal):
	dialogo = editor_premios.DialogoPremio(marco, equipo.contexto, equipo.servicio)
	revisar(dialogo)
	assert dialogo.validar()[1] is dialogo.nombre
	dialogo.nombre.SetValue("Llave dorada")
	elegir(dialogo.lugar.espacio, "Dormitorio")
	elegir(dialogo.visibilidad, "Oculto")
	dialogo.mensaje.SetValue("¡La encontraste!")
	audio = tmp_path / "Mensaje de mamá.wav"
	audio.write_bytes(b"RIFF" + b"\0" * 64)
	assert dialogo.poner_audio(audio) is True
	malo = tmp_path / "notas.txt"
	malo.write_text("no es audio")
	assert dialogo.poner_audio(malo) is False
	assert dialogo.aceptar() is True
	premio = dialogo.premio
	assert premio["dentro_de"] == _armario(equipo.contexto.entorno).id and premio["visibilidad"] == "oculto"
	assert premio["audio"].startswith("sonidos/") and premio["audio"].endswith(".wav")
	assert equipo.contexto.recursos[premio["audio"]].startswith(b"RIFF")
	assert formato.nombre_interno_seguro(premio["audio"])
	dialogo.Destroy()


def test_escuchar_es_tolerante_si_no_hay_sonido(equipo, marco):
	class EscuchaMuda:
		def escuchar(self, nombre):
			return False

	equipo.servicio.escucha = EscuchaMuda()
	dialogo = editor_premios.DialogoPremio(marco, equipo.contexto, equipo.servicio)
	dialogo.escuchar()
	assert any("No se ha podido reproducir" in texto for texto in equipo.contexto.anunciados)
	equipo.servicio.escucha = None
	dialogo.Destroy()


def test_panel_premios_anadir_editar_ordenar_y_quitar(equipo, marco, dialogo_modal):
	panel = editor_premios.PanelPremios(marco, equipo.contexto, equipo.servicio, Letras())

	def rellenar(dialogo):
		dialogo.nombre.SetValue("Osito")
		elegir(dialogo.lugar.espacio, "Dormitorio")

	dialogo_modal.responder(responder_con(rellenar))
	panel.anadir()
	assert panel.lista.valores_fila(0)[:3] == ["Osito", "Dormitorio, dentro de Armario", "Solo se oye de cerca"]
	assert any("Osito escondido" in texto for texto in equipo.contexto.anunciados)

	def otro(dialogo):
		dialogo.nombre.SetValue("Pelota")
		elegir(dialogo.lugar.espacio, "Cocina")
		elegir(dialogo.lugar.modo, "esquina")

	dialogo_modal.responder(responder_con(otro))
	panel.anadir()
	assert [premio["id"] for premio in panel.leer()] == ["premio-1", "premio-2"]
	assert panel.lista.valores_fila(1)[1].startswith("Cocina")
	panel.mover(-1)
	assert [premio["nombre"] for premio in panel.leer()] == ["Pelota", "Osito"]
	dialogo_modal.responder(responder_con(lambda d: d.nombre.SetValue("Pelota roja")))
	panel.editar()
	assert panel.leer()[0]["nombre"] == "Pelota roja" and panel.leer()[0]["planta"]
	panel.quitar()
	assert [premio["nombre"] for premio in panel.leer()] == ["Osito"]


def test_repartir_premios_con_vista_previa(equipo, marco, dialogo_modal, con_reserva):
	panel = editor_premios.PanelPremios(
		marco, equipo.contexto, equipo.servicio, Letras(), [{"id": "premio-1", "nombre": "Viejo", "planta": "", "x": 1.0, "y": 1.0}]
	)
	dialogo = editor_premios.DialogoRepartir(marco, equipo.contexto, hay_premios=True)
	revisar(dialogo)
	assert dialogo.cuantos.GetValue() == 2
	dialogo.cuantos.SetValue(4)
	dialogo.generar()
	assert dialogo.lista.numero_filas() == 4
	lugares_vistos = {dialogo.lista.valores_fila(fila)[1].split(",")[0] for fila in range(4)}
	assert lugares_vistos == {"Dormitorio", "Cocina"}
	primero = [dict(premio) for premio in dialogo.premios]
	dialogo.generar()
	assert len(dialogo.premios) == 4 and primero is not dialogo.premios
	dialogo.Destroy()

	def configurar(d):
		d.cuantos.SetValue(3)
		d.casilla_sustituir.SetValue(True)

	dialogo_modal.responder(responder_con(configurar))
	panel.repartir()
	premios = panel.leer()
	assert len(premios) == 3 and len({premio["id"] for premio in premios}) == 3
	assert all(premio["nombre"] != "Viejo" for premio in premios)
	assert any("3 premios añadidos" in texto for texto in equipo.contexto.anunciados)


def test_colocar_recorriendo_explica_por_que_no_se_puede(equipo, marco, dialogo_modal):
	panel = editor_premios.PanelPremios(marco, equipo.contexto, equipo.servicio, Letras())
	assert "guardado" in panel.motivo_sin_recorrido()
	panel.colocar_recorriendo()
	assert any("no se puede colocar recorriendo" in texto for texto in dialogo_modal.ultimo.textos)
	assert equipo.contexto.lanzados == []


def test_colocar_recorriendo_con_sala_y_cliente_reales(equipo, marco, ayudas_wx):
	sala = equipo.servicio.sala
	sala.asegurar_local()
	dialogo = editor_premios.DialogoColocarRecorriendo(marco, equipo.contexto, equipo.servicio)
	revisar(dialogo)
	cliente = ClienteSupervision(
		"127.0.0.1", sala.sala.puerto_local, sala.sala.codigo, "Profe", recorrido=True, carpeta_config=equipo.carpeta / "cliente"
	)
	cliente.iniciar()
	try:
		limite = time.monotonic() + 5.0
		while not cliente.conectado and time.monotonic() < limite:
			time.sleep(0.02)
		assert cliente.conectado
		planta = equipo.contexto.entorno.plantas[0].id
		ident = cliente.peticion("marcar_punto", planta=planta, x=6.0, y=2.0, rumbo=0.0)
		limite = time.monotonic() + 5.0
		while dialogo.posicion is None and time.monotonic() < limite:
			dialogo.sondear()
			time.sleep(0.02)
		assert dialogo.posicion == {"planta": planta, "x": 6.0, "y": 2.0, "dentro_de": None}
		assert dialogo.aceptado
		respuesta = None
		limite = time.monotonic() + 5.0
		while respuesta is None and time.monotonic() < limite:
			for tipo, datos in cliente.ordenes_pendientes():
				if tipo == "respuesta":
					respuesta = datos
			time.sleep(0.02)
		assert respuesta is not None and respuesta["id"] == ident and respuesta["aceptada"] and "Cocina" in respuesta["texto"]
	finally:
		cliente.detener()
		dialogo.Destroy()


def test_colocar_recorriendo_lanza_el_reproductor_y_anade_el_premio(equipo, marco, dialogo_modal, tmp_path):
	equipo.contexto.ruta_paquete = tmp_path / "casa.elab"
	panel = editor_premios.PanelPremios(marco, equipo.contexto, equipo.servicio, Letras())
	planta = equipo.contexto.entorno.plantas[0].id

	def llega_la_peticion(dialogo):
		dialogo._suceso(
			{"tipo": "peticion", "alumno": "Profe", "datos": {"id": 1, "accion": "marcar_punto", "planta": planta, "x": 2.0, "y": 2.0}}
		)
		return wx.ID_OK if dialogo.aceptado else wx.ID_CANCEL

	dialogo_modal.responder(llega_la_peticion, responder_con(lambda d: d.nombre.SetValue("Tesoro")))
	panel.colocar_recorriendo()
	lanzado = equipo.contexto.lanzados[0]
	assert (
		lanzado.orden[0] == "--recorrido"
		and lanzado.orden[1].endswith("casa.elab")
		and "--sala" in lanzado.orden
		and "--codigo" in lanzado.orden
	)
	assert lanzado.terminado
	assert equipo.contexto.guardados == 1 and (tmp_path / "casa.elab").is_file()
	assert not equipo.servicio.sala.activa
	premio = panel.leer()[0]
	assert (premio["nombre"], premio["x"], premio["y"]) == ("Tesoro", 2.0, 2.0)
	assert panel.lista.valores_fila(0)[1].startswith("Dormitorio")


# ── Objetivos y ayudas ───────────────────────────────────────────────────────


def test_panel_objetivos(equipo, marco, dialogo_modal):
	entorno = equipo.contexto.entorno
	cocina = next(e for e in entorno.plantas[0].espacios if e.nombre == "Cocina")
	panel = editor_objetivos.PanelObjetivos(marco, equipo.contexto, Letras(), con_orden=True, orden_obligatorio=True)
	dialogo = editor_objetivos.DialogoObjetivo(marco, entorno, equipo.contexto.catalogo)
	revisar(dialogo)
	assert dialogo.validar()[1] is dialogo.destino
	dialogo_modal.responder(
		responder_con(lambda d: elegir(d.lista, "Cocina") if False else d.lista.SetSelection(d.lista.FindString("Cocina")))
	)
	dialogo.elegir_elemento()
	assert dialogo.destino.GetValue() == "Cocina"
	dialogo.texto.SetValue("Ve a la cocina")
	assert dialogo.aceptar() is True and dialogo.objetivo == {"tipo": "ir_a", "destino": cocina.id, "texto": "Ve a la cocina"}
	dialogo.Destroy()

	def rellenar(d):
		d._destino = cocina.id
		elegir(d.tipo, "Salir")

	dialogo_modal.responder(responder_con(rellenar))
	panel.anadir()
	assert panel.lista.valores_fila(0)[:2] == ["Salir por una salida", "Cocina"]
	assert panel.leer()[0]["id"] == "objetivo-1" and panel.orden.GetValue() is True
	panel.quitar()
	assert panel.leer() == []


def test_tabla_de_ayudas_y_niveles(equipo, marco, dialogo_modal):
	dialogo = editor_ayudas.DialogoAyudas(marco, {"baliza": False, "pista": {"permitida": True, "limite": 2}})
	revisar(dialogo)
	tabla = dialogo.tabla
	fila_pista = tabla._claves.index("pista")
	assert tabla.lista.valores_fila(fila_pista)[1:] == ["Permitida", "2"]
	tabla.lista.enfocar_fila(tabla._claves.index("eco"), anunciar=False)
	tabla.cambiar("prohibida")
	tabla.lista.enfocar_fila(fila_pista, anunciar=False)
	dialogo_modal.responder(lambda d: (d.campo.SetValue("5"), wx.ID_OK)[1])
	tabla.pedir_limite()
	assert dialogo.aceptar() is True
	assert dialogo.reglas == {
		"baliza": {"permitida": False, "limite": None},
		"pista": {"permitida": True, "limite": 5},
		"eco": {"permitida": False, "limite": None},
	}
	dialogo.Destroy()

	niveles = editor_ayudas.DialogoNiveles(marco, [])
	revisar(niveles)
	niveles.de_serie()
	assert niveles.lista.numero_filas() == 4 and "Dónde estoy" in niveles.lista.valores_fila(3)[2]
	niveles.lista.enfocar_fila(3, anunciar=False)
	niveles.mover(-1)
	assert niveles.niveles[2]["nombre"].startswith("Sin baliza y sin")
	nivel = editor_ayudas.DialogoNivel(marco, niveles.niveles[0])
	revisar(nivel)
	nivel.nombre.SetValue("")
	assert nivel.validar()[1] is nivel.nombre
	nivel.Destroy()
	niveles.Destroy()


# ── Formulario generado ──────────────────────────────────────────────────────


@pytest.mark.parametrize("tipo", sorted(reserva.TIPOS))
def test_formulario_generado_del_esquema_de_prueba(equipo, marco, con_reserva, tipo):
	datos = api.nueva_actividad(tipo, equipo.contexto.entorno, equipo.contexto.catalogo)
	dialogo = DialogoActividad(marco, equipo.contexto, equipo.servicio, datos)
	try:
		revisar(dialogo)
		claves = {editor.clave for editor in dialogo.editores}
		assert claves == {campo.clave for campo in reserva.campos_de(tipo)}
		assert {type(editor) for editor in dialogo.editores} <= set(campos.EDITORES.values())
		assert dialogo.cuaderno.GetPageCount() == len(pres.grupos_en_orden(reserva.campos_de(tipo)))
		# Sin tocar nada, lo que sale es lo que entró.
		recogido = dialogo.recoger()
		for clave in claves:
			esperado = api.leer_campo(datos, clave)
			assert api.leer_campo(recogido, clave) == (esperado if esperado is not None else api.leer_campo(recogido, clave))
		assert recogido["tipo"] == tipo and recogido["modo"] == reserva.TIPOS[tipo].modo_por_defecto
	finally:
		dialogo.Destroy()


def test_todos_los_tipos_de_campo_tienen_editor_en_el_esquema_de_prueba(con_reserva):
	usados = {campo.tipo for tipo in reserva.TIPOS for campo in reserva.campos_de(tipo)}
	assert usados == set(campos.EDITORES)


def test_campos_condicionales_y_ayuda_por_campo(equipo, marco, con_reserva):
	datos = api.nueva_actividad("busqueda", equipo.contexto.entorno)
	dialogo = DialogoActividad(marco, equipo.contexto, equipo.servicio, datos)
	nivel, usar = dialogo.editor("nivel"), dialogo.editor("usar_niveles")
	assert not nivel.principal.IsEnabled()
	usar.control.SetValue(True)
	ayudas_evento = wx.CommandEvent(wx.wxEVT_CHECKBOX, usar.control.GetId())
	ayudas_evento.SetEventObject(usar.control)
	usar.control.GetEventHandler().ProcessEvent(ayudas_evento)
	assert nivel.principal.IsEnabled()
	# La ayuda del esquema queda en cada control, para Ctrl+H.
	assert "Nivel en el que empieza" in nivel.principal.GetHelpText()
	assert "Nombre con el que" in dialogo.editor("nombre").principal.GetHelpText()
	# Un campo atenuado no se valida ni se guarda.
	usar.control.SetValue(False)
	dialogo.al_cambiar_campo("usar_niveles")
	nivel.principal.SetValue("no es un número")
	assert dialogo.recoger()["nivel"] == 0
	dialogo.Destroy()


def test_validacion_lleva_el_foco_al_campo_erroneo_y_cambia_de_pestana(equipo, marco, con_reserva, dialogo_modal):
	datos = api.nueva_actividad("examen_salida", equipo.contexto.entorno)
	dialogo = DialogoActividad(marco, equipo.contexto, equipo.servicio, datos)
	pruebas = dialogo.editor("numero_pruebas")
	pruebas.principal.SetValue("99")
	dialogo.cuaderno.SetSelection(0)
	with pytest.raises(campos.ErrorCampo) as error:
		dialogo.recoger()
	assert error.value.control is pruebas.principal and "entre 1 y 30" in str(error.value)
	assert dialogo.aceptar() is False
	assert dialogo.cuaderno.GetPageText(dialogo.cuaderno.GetSelection()) == "Examen"
	assert any("entre 1 y 30" in texto for texto in dialogo_modal.ultimo.textos)
	pruebas.principal.SetValue("7")
	dialogo.editor("tolerancia_m").principal.SetValue("1,5")
	assert dialogo.aceptar() is True
	assert dialogo.resultado["numero_pruebas"] == 7 and dialogo.resultado["tolerancia_m"] == 1.5 and dialogo.resultado["modo"] == "examen"
	assert not dialogo.modo.IsEnabled()
	dialogo.Destroy()


def test_errores_de_la_actividad_dejan_corregir_o_guardar(equipo, marco, con_reserva, dialogo_modal):
	datos = api.nueva_actividad("ruta", equipo.contexto.entorno)
	dialogo = DialogoActividad(marco, equipo.contexto, equipo.servicio, datos)
	dialogo.cuaderno.SetSelection(0)
	# Primera vez: «Corregir» (la primera opción): no se cierra y se va a la pestaña del destino.
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	assert dialogo.aceptar() is False
	assert "no tiene destino" in dialogo_modal.ultimo.textos[0] or any("no tiene destino" in t for t in dialogo_modal.ultimo.textos)
	assert dialogo.cuaderno.GetPageText(dialogo.cuaderno.GetSelection()) == "Objetivos"
	# Segunda: «Guardar de todos modos».
	dialogo_modal.responder(lambda d: d.ids_opciones[1])
	assert dialogo.aceptar() is True and dialogo.resultado["destino"] is None
	dialogo.Destroy()


def test_el_formulario_edita_premios_objetivos_posicion_y_elemento(equipo, marco, con_reserva, dialogo_modal):
	entorno = equipo.contexto.entorno
	cocina = next(e for e in entorno.plantas[0].espacios if e.nombre == "Cocina")
	datos = api.nueva_actividad("ruta", entorno)
	datos["campo_de_otra_version"] = {"se": "conserva"}
	dialogo = DialogoActividad(marco, equipo.contexto, equipo.servicio, datos)
	dialogo.editor("nombre").principal.SetValue("Ir a la cocina")
	dialogo_modal.responder(responder_con(lambda d: d.lista.SetSelection(d.lista.FindString("Cocina"))))
	dialogo.editor("destino").elegir()
	assert "Cocina" in dialogo.editor("destino").control.GetValue()
	dialogo_modal.responder(responder_con(lambda d: (elegir(d.lugar.espacio, "Dormitorio"), elegir(d.lugar.modo, "centro"))))
	dialogo.editor("inicio").elegir()
	assert "Dormitorio" in dialogo.editor("inicio").control.GetValue()
	dialogo.modo.SetSelection(0)
	assert dialogo.aceptar() is True
	resultado = dialogo.resultado
	assert resultado["nombre"] == "Ir a la cocina" and resultado["destino"] == cocina.id and resultado["modo"] == "juego"
	assert resultado["inicio"]["planta"] == entorno.plantas[0].id and "rumbo" in resultado["inicio"]
	assert resultado["campo_de_otra_version"] == {"se": "conserva"}
	dialogo.editor("inicio").quitar()
	assert dialogo.editor("inicio").leer() is None
	dialogo.Destroy()


def test_un_tipo_de_campo_desconocido_se_ensena_sin_tocarlo(equipo, marco, con_reserva, monkeypatch):
	originales = reserva.campos_de

	def con_campo_raro(tipo):
		return [*originales(tipo), reserva.Campo("cosa_nueva", "Cosa nueva", "matriz", "De otra versión.", defecto=None)]

	monkeypatch.setattr(reserva, "campos_de", con_campo_raro)
	datos = api.nueva_actividad("exploracion", equipo.contexto.entorno)
	datos["cosa_nueva"] = [[1, 2], [3, 4]]
	dialogo = DialogoActividad(marco, equipo.contexto, equipo.servicio, datos)
	assert isinstance(dialogo.editor("cosa_nueva"), campos.EditorDesconocido)
	assert dialogo.recoger()["cosa_nueva"] == [[1, 2], [3, 4]]
	dialogo.Destroy()


def _tipos_reales() -> list[str]:
	if api._real("TIPOS") is None or api._real("campos_de") is None:
		return []
	return sorted(api.tipos())


@pytest.mark.parametrize(
	"tipo", _tipos_reales() or [pytest.param("", marks=pytest.mark.skip(reason="app.actividades no ofrece TIPOS y campos_de"))]
)
def test_formulario_generado_del_esquema_real(equipo, marco, tipo, dialogo_modal):
	"""Con ``app.actividades`` de verdad: cada tipo abre su formulario, pasa la revisión de teclado y se recoge sin errores."""
	datos = api.nueva_actividad(tipo, equipo.contexto.entorno, equipo.contexto.catalogo)
	dialogo = DialogoActividad(marco, equipo.contexto, equipo.servicio, datos)
	try:
		revisar(dialogo)
		esquema = api.campos_de(tipo)
		assert {editor.clave for editor in dialogo.editores} >= {str(campo.clave) for campo in esquema}
		assert not any(isinstance(editor, campos.EditorDesconocido) for editor in dialogo.editores)
		recogido = dialogo.recoger()
		assert recogido["tipo"] == tipo
		avisos = api.validar_actividad(recogido, equipo.contexto.entorno, equipo.contexto.catalogo)
		assert isinstance(pres.texto_avisos(avisos), str)
		assert isinstance(api.describir_actividad(recogido, equipo.contexto.entorno), str)
	finally:
		dialogo.Destroy()


# ── Panel de la pestaña ──────────────────────────────────────────────────────


def _marco_con_menus(marco):
	barra = wx.MenuBar()
	for titulo in ("&Archivo", "&Editar", "&Insertar", "&Ver", "A&lumnos", "&Supervisión", "&Herramientas", "Ay&uda"):
		menu = wx.Menu()
		menu.Append(wx.ID_ANY, "&Elemento")
		barra.Append(menu, titulo)
	marco.SetMenuBar(barra)
	return marco


def test_panel_no_repite_las_letras_de_los_menus(equipo, marco, con_reserva):
	_marco_con_menus(marco)
	panel = panel_actividades.PanelActividades(marco, equipo.contexto, equipo.servicio)
	revisar(marco)
	letras = {letra_de(boton.GetLabel()) for boton in panel.botones.values()}
	assert not letras & set("aeivlshu") and len(letras) == len(panel.botones)
	assert not panel.botones["editar"].IsEnabled() and panel.botones["nueva"].IsEnabled()
	for dialogo in (
		panel_actividades.DialogoTipoActividad(marco),
		panel_actividades.DialogoAsignar(marco, {"id": "a", "nombre": "A"}, [], "e"),
		panel_actividades.DialogoExportarPaquete(marco, [{"id": "a", "nombre": "A"}]),
	):
		revisar(dialogo)
		dialogo.Destroy()


def test_panel_sin_entorno_esta_vacio_y_se_rellena_al_abrir(equipo, marco, con_reserva):
	entorno = equipo.contexto.entorno
	equipo.contexto.entorno = None
	equipo.contexto.actividades.append(api.nueva_actividad("busqueda", entorno))
	panel = panel_actividades.PanelActividades(marco, equipo.contexto, equipo.servicio)
	assert panel.lista.numero_filas() == 0 and not panel.botones["nueva"].IsEnabled()
	equipo.contexto.entorno = entorno
	equipo.contexto.emitir("entorno_abierto")
	assert panel.lista.numero_filas() == 1 and panel.botones["editar"].IsEnabled()
	assert panel.lista.valores_fila(0)[:3] == ["Búsqueda del tesoro", "Búsqueda del tesoro", "Juego"]


def test_panel_nueva_editar_duplicar_ordenar_y_borrar(equipo, marco, con_reserva, dialogo_modal):
	panel = panel_actividades.PanelActividades(marco, equipo.contexto, equipo.servicio)

	def elegir_tipo(dialogo):
		assert dialogo.grupo.GetStrings() == ["Juegos", "Prácticas", "Exámenes"]
		elegir(dialogo.grupo, "Prácticas")
		assert set(dialogo.lista.GetStrings()) == {"Exploración libre", "Ruta"}
		dialogo.lista.SetSelection(dialogo.lista.FindString("Exploración libre"))
		dialogo._describir()
		assert "libertad" in dialogo.descripcion.GetValue()

	dialogo_modal.responder(responder_con(elegir_tipo), responder_con(lambda d: d.editor("nombre").principal.SetValue("Paseo por la casa")))
	panel.nueva()
	actividades = equipo.contexto.actividades
	assert [a["nombre"] for a in actividades] == ["Paseo por la casa"] and actividades[0]["id"] == "exploracion"
	assert equipo.contexto.modificaciones == ["nueva actividad"]
	assert panel.lista.valores_fila(0)[1:3] == ["Exploración libre", "Práctica"]
	assert equipo.contexto.actividad_actual is None or equipo.contexto.actividad_actual is actividades[0]

	dialogo_modal.responder(responder_con(lambda d: d.editor("nombre").principal.SetValue("Paseo largo")))
	panel.editar()
	assert actividades[0]["nombre"] == "Paseo largo"
	panel.duplicar()
	assert [a["id"] for a in actividades] == ["exploracion", "exploracion-2"] and actividades[1]["nombre"] == "Copia de Paseo largo"
	assert panel.indice() == 1
	panel.mover(-1)
	assert [a["id"] for a in actividades] == ["exploracion-2", "exploracion"] and panel.indice() == 0
	# Cancelar el borrado no borra; confirmarlo, sí.
	dialogo_modal.responder(wx.ID_CANCEL)
	panel.borrar()
	assert len(actividades) == 2
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	panel.borrar()
	assert [a["id"] for a in actividades] == ["exploracion"]
	assert equipo.contexto.modificaciones[-1] == "borrar la actividad"


def test_panel_comprobar_y_probar_ahora(equipo, marco, con_reserva, dialogo_modal, tmp_path):
	equipo.contexto.actividades.append(api.nueva_actividad("busqueda", equipo.contexto.entorno))
	panel = panel_actividades.PanelActividades(marco, equipo.contexto, equipo.servicio)
	panel.comprobar()
	assert any("necesita al menos un premio" in texto for texto in dialogo_modal.ultimo.textos)
	# Sin fichero: se ofrece guardar; al cancelar no se lanza nada.
	dialogo_modal.responder(wx.ID_CANCEL)
	panel.probar()
	assert equipo.contexto.lanzados == []
	equipo.contexto.ruta_paquete = tmp_path / "casa.elab"
	equipo.contexto.modificado = True
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	panel.probar()
	assert equipo.contexto.guardados == 1
	assert equipo.contexto.lanzados[0].orden == [str(tmp_path / "casa.elab"), "--actividad", "busqueda"]
	# Con la sala abierta, el reproductor se conecta a ella.
	equipo.servicio.sala.asegurar_local()
	panel.probar()
	assert equipo.contexto.lanzados[1].orden[3:5] == ["--sala", f"127.0.0.1:{equipo.servicio.sala.sala.puerto_local}"]


def test_panel_asignar_a_alumnos(equipo, marco, con_reserva, dialogo_modal):
	base = equipo.abrir_base()
	fichas = Fichas(base)
	fichas.alta("Luna")
	fichas.alta("Sol")
	equipo.contexto.actividades.append(api.nueva_actividad("busqueda", equipo.contexto.entorno))
	panel = panel_actividades.PanelActividades(marco, equipo.contexto, equipo.servicio)

	def marcar(dialogo):
		assert dialogo.lista.GetStrings() == ["Luna", "Sol"]
		dialogo.lista.Check(0, True)

	dialogo_modal.responder(responder_con(marcar))
	panel.asignar()
	entorno_id = equipo.contexto.entorno.id
	assert presentador_alumnos.tiene_asignada(fichas.por_alias("Luna"), entorno_id, "busqueda")
	assert not presentador_alumnos.tiene_asignada(fichas.por_alias("Sol"), entorno_id, "busqueda")
	assert any("1 alumno" in texto for texto in equipo.contexto.anunciados)
	# Al volver a abrir sale marcada, y desmarcarla la quita.
	dialogo_modal.responder(responder_con(lambda d: d.lista.Check(0, not d.lista.IsChecked(0))))
	panel.asignar()
	assert not presentador_alumnos.tiene_asignada(fichas.por_alias("Luna"), entorno_id, "busqueda")


def test_panel_exportar_paquete_para_el_alumno(equipo, marco, con_reserva, dialogo_modal, monkeypatch, tmp_path):
	una = api.nueva_actividad("busqueda", equipo.contexto.entorno)
	una["premios"] = [
		{
			"id": "premio-1",
			"nombre": "Llave",
			"planta": equipo.contexto.entorno.plantas[0].id,
			"x": 1.0,
			"y": 1.0,
			"audio": "sonidos/llave.wav",
		}
	]
	otra = api.nueva_actividad("exploracion", equipo.contexto.entorno)
	otra["premios"] = [{"id": "premio-1", "nombre": "Otro", "planta": "", "x": 1.0, "y": 1.0, "audio": "sonidos/otro.wav"}]
	equipo.contexto.actividades.extend([una, otra])
	equipo.contexto.recursos.update({"sonidos/llave.wav": b"RIFFllave", "sonidos/otro.wav": b"RIFFotro"})
	panel = panel_actividades.PanelActividades(marco, equipo.contexto, equipo.servicio)
	destino = tmp_path / "para el alumno.elab"
	monkeypatch.setattr(panel_actividades, "pedir_ruta_guardar", lambda *args, **kwargs: destino)

	def comprobar_marcas(dialogo):
		assert [dialogo.lista.IsChecked(i) for i in range(2)] == [True, False]

	dialogo_modal.responder(responder_con(comprobar_marcas))
	panel.exportar()
	paquete = formato.cargar_paquete(destino)
	assert [a["id"] for a in paquete.actividades] == ["busqueda"]
	assert paquete.nombres_recursos() == ["sonidos/llave.wav"]
	assert paquete.entorno.nombre == equipo.contexto.entorno.nombre


# ── Contra la API real de app.actividades ────────────────────────────────────

requiere_api_real = pytest.mark.skipif(not api.es_real(), reason="app.actividades no ofrece todavía toda su API")


@requiere_api_real
def test_api_real_completa_y_con_la_forma_esperada(equipo):
	import app.actividades as real

	for nombre in api.NOMBRES:
		assert api.obtener(nombre) is getattr(real, nombre)
	for tipo, info in api.tipos().items():
		assert info.grupo in ("juego", "practica", "examen") and api.nombre_tipo(tipo) and api.descripcion_tipo(tipo)
		claves = {campo.clave for campo in api.campos_de(tipo)}
		for campo in api.campos_de(tipo):
			assert campo.tipo in campos.EDITORES, f"el tipo de campo «{campo.tipo}» de {tipo}.{campo.clave} no tiene editor"
			assert pres.titulo_grupo(campo.grupo)
			if campo.tipo == "opcion":
				assert all(isinstance(etiqueta, str) for _valor, etiqueta in pres.opciones_normalizadas(campo.opciones))
			if campo.depende_de:
				assert pres.clave_de_dependencia(campo.depende_de) in claves


@requiere_api_real
def test_real_nueva_busqueda_desde_el_panel(equipo, marco, dialogo_modal):
	panel = panel_actividades.PanelActividades(marco, equipo.contexto, equipo.servicio)

	def tipo_busqueda(dialogo):
		elegir(dialogo.grupo, "Juegos")
		dialogo.lista.SetSelection(dialogo.lista.FindString(api.nombre_tipo("busqueda")))

	def poner_nombre(dialogo):
		dialogo.editor("nombre").principal.SetValue("Busca las llaves")
		if not dialogo.editor("premios").leer():
			dialogo_modal.respuestas.insert(
				0, responder_con(lambda d: (d.nombre.SetValue("Llaves"), elegir(d.lugar.espacio, "Dormitorio")))
			)
			dialogo.editor("premios").panel.anadir()

	dialogo_modal.responder(responder_con(tipo_busqueda), responder_con(poner_nombre))
	panel.nueva()
	actividad = equipo.contexto.actividades[0]
	assert actividad["tipo"] == "busqueda" and actividad["nombre"] == "Busca las llaves" and actividad["premios"]
	fila = panel.lista.valores_fila(0)
	assert fila[0] == "Busca las llaves" and fila[1] == api.nombre_tipo("busqueda") and fila[2] == "Juego" and fila[3]
	assert not pres.hay_errores(api.validar_actividad(actividad, equipo.contexto.entorno, equipo.contexto.catalogo))


@requiere_api_real
def test_real_reparto_de_premios_en_palabras(equipo, marco):
	dialogo = editor_premios.DialogoRepartir(marco, equipo.contexto)
	dialogo.cuantos.SetValue(4)
	dialogo.generar()
	assert len(dialogo.premios) == 4
	entorno = equipo.contexto.entorno
	for fila, premio in enumerate(dialogo.premios):
		donde = dialogo.lista.valores_fila(fila)[1]
		assert donde.split(",")[0] in ("Dormitorio", "Cocina"), donde
		assert premio.get("dentro_de") or lugares.espacio_en(entorno, premio["planta"], premio["x"], premio["y"])[1] is not None
	assert {dialogo.lista.valores_fila(fila)[1].split(",")[0] for fila in range(4)} == {"Dormitorio", "Cocina"}
	dialogo.Destroy()


@requiere_api_real
def test_real_validacion_lleva_el_foco_al_campo_y_a_la_fila(equipo, marco, dialogo_modal):
	entorno = equipo.contexto.entorno
	datos = api.nueva_actividad("busqueda", entorno, equipo.contexto.catalogo)
	datos["premios"] = [
		{"id": "premio-1", "nombre": "Bien puesto", "planta": entorno.plantas[0].id, "x": 2.0, "y": 2.5, "visibilidad": "cerca"},
		{"id": "premio-2", "nombre": "Dentro de un muro", "planta": entorno.plantas[0].id, "x": 50.0, "y": 50.0, "visibilidad": "cerca"},
	]
	avisos = api.validar_actividad(datos, entorno, equipo.contexto.catalogo)
	errores = [aviso for aviso in avisos if aviso.gravedad == "error"]
	assert errores and pres.campo_de_aviso(errores[0], ["nombre", "premios", "inicio"], datos) == "premios"
	dialogo = DialogoActividad(marco, equipo.contexto, equipo.servicio, datos)
	dialogo.cuaderno.SetSelection(0)
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	assert dialogo.aceptar() is False
	assert dialogo.cuaderno.GetPageText(dialogo.cuaderno.GetSelection()) == "Premios"
	assert dialogo.editor("premios").panel.lista.fila_actual() == 1, "queda elegido el premio que falla"
	dialogo.Destroy()
	# Sin premios: el aviso no trae id, pero su código señala el campo.
	sin_premios = api.validar_actividad({**datos, "premios": []}, entorno, equipo.contexto.catalogo)
	assert pres.campo_de_aviso(sin_premios[0], ["nombre", "premios"], datos) == "premios"


@requiere_api_real
def test_real_ruta_sin_destino_y_examen(equipo, marco, dialogo_modal):
	entorno = equipo.contexto.entorno
	ruta = api.nueva_actividad("ruta", entorno, equipo.contexto.catalogo)
	ruta["destino"] = None
	dialogo = DialogoActividad(marco, equipo.contexto, equipo.servicio, ruta)
	dialogo.cuaderno.SetSelection(0)
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	assert dialogo.aceptar() is False
	assert dialogo.cuaderno.GetPage(dialogo.cuaderno.GetSelection()) is dialogo.editor("destino").principal.GetParent()
	dialogo.Destroy()
	examen = api.nueva_actividad("examen_salida", entorno, equipo.contexto.catalogo)
	dialogo = DialogoActividad(marco, equipo.contexto, equipo.servicio, examen)
	assert not dialogo.modo.IsEnabled() and dialogo.recoger()["modo"] == "examen"
	parada = dialogo.editor("regla_parada.activa")
	parada.control.SetValue(False)
	dialogo.al_cambiar_campo("regla_parada.activa")
	assert not dialogo.editor("regla_parada.de").principal.IsEnabled()
	assert dialogo.recoger()["regla_parada"]["activa"] is False
	dialogo.Destroy()


def test_panel_probar_como_un_alumno_y_aviso_al_cerrarse_el_reproductor(equipo, marco, con_reserva, dialogo_modal, tmp_path, monkeypatch):
	equipo.contexto.actividades.append(api.nueva_actividad("busqueda", equipo.contexto.entorno))
	equipo.contexto.ruta_paquete = tmp_path / "casa.elab"
	equipo.contexto.guardar()
	panel = panel_actividades.PanelActividades(marco, equipo.contexto, equipo.servicio)
	# Con los datos bloqueados no se pregunta (probar no pide la contraseña) y se prueba sin alumno.
	panel.probar()
	assert "--alumno" not in equipo.contexto.lanzados[-1].orden
	# Con los datos abiertos y alumnos, se elige con quién se prueba: abre la sala para que le llegue su ficha.
	Fichas(equipo.abrir_base()).alta("Luna")
	dialogo_modal.responder(responder_con(lambda d: elegir(d.alumno, "Luna")))
	panel.probar()
	orden = equipo.contexto.lanzados[-1].orden
	sala = equipo.servicio.sala
	assert sala.activa and orden[3:5] == ["--alumno", "Luna"] and orden[5:7] == ["--sala", f"127.0.0.1:{sala.sala.puerto_local}"]
	assert panel._sondeo.IsRunning(), "mientras el reproductor esté abierto, el panel lee la sala"
	assert any("como Luna" in texto for texto in equipo.contexto.anunciados)
	# Cancelar la elección no lanza nada.
	lanzados = len(equipo.contexto.lanzados)
	dialogo_modal.responder(wx.ID_CANCEL)
	panel.probar()
	assert len(equipo.contexto.lanzados) == lanzados
	# Si el reproductor se cierra solo, el panel lo dice (la ventana de supervisión está cerrada).
	suceso = {
		"tipo": "proceso_terminado",
		"alumno": "Luna",
		"alias": "Luna",
		"hora": time.time(),
		"datos": {"codigo": 3, "inesperado": True},
	}
	monkeypatch.setattr(sala.sala, "eventos_pendientes", lambda: [suceso])
	for proceso in equipo.contexto.lanzados:
		proceso.terminado = True
	panel._sondear()
	assert "El reproductor de Luna se ha cerrado inesperadamente; puede volver a abrirlo." in equipo.contexto.anunciados
	if callable(getattr(sala, "vigilar", None)):
		# La sala vigila de verdad los procesos lanzados por el servicio: el que llevaba --alumno Luna avisa con su alias.
		assert sum(texto.startswith("El reproductor de Luna se ha cerrado") for texto in equipo.contexto.anunciados) >= 2
	monkeypatch.setattr(sala.sala, "eventos_pendientes", lambda: [])
	panel._sondear()
	assert not panel._sondeo.IsRunning(), "sin reproductores vivos, deja de leer la sala"


def test_validar_actividad_recibe_los_recursos_del_paquete(monkeypatch):
	recibidos: list = []

	def validar(datos, entorno, catalogo=None, recursos=None):
		recibidos.append(recursos)
		return []

	monkeypatch.setattr(api, "obtener", lambda nombre: validar)
	api.validar_actividad({}, None)
	api.validar_actividad({}, None, None, recursos={"sonidos/llave.wav": b""})
	assert recibidos == [None, {"sonidos/llave.wav": b""}]
	assert reserva.validar_actividad({"nombre": "x", "tipo": "exploracion"}, None, None, recursos={}) == []
