"""Supervisión en vivo contra una ``Sala`` real y un ``ClienteSupervision`` real en 127.0.0.1."""

# ruff: noqa: F811 - las fixtures importadas de _ui_seguimiento_util se usan como parámetros
from __future__ import annotations

import time
from collections.abc import Callable, Iterator

import pytest

wx = pytest.importorskip("wx")

from app.core.configuracion import ErrorValidacion, obtener_configuracion  # noqa: E402
from app.seguimiento import grabadora, sesiones  # noqa: E402
from app.seguimiento.alumnos import Fichas  # noqa: E402
from app.supervision.cliente import ClienteSupervision  # noqa: E402
from app.ui.seguimiento import presentador_supervision as pres  # noqa: E402
from app.ui.seguimiento import supervision as ui  # noqa: E402
from app.ui.seguimiento import textos  # noqa: E402
from tests._ui_seguimiento_util import elegir, equipo, responder_con, revisar, sin_voz  # noqa: E402, F401


def _esperar(condicion: Callable[[], bool], paso: Callable[[], None] = lambda: None, segundos: float = 6.0) -> bool:
	"""Repite ``paso`` hasta que se cumpla ``condicion`` (la sala y el cliente trabajan en sus hilos)."""
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		paso()
		if condicion():
			return True
		time.sleep(0.02)
	return condicion()


def _ordenes(cliente: ClienteSupervision, recibidas: list) -> None:
	recibidas.extend(cliente.ordenes_pendientes())


@pytest.fixture
def sala_abierta(equipo):
	"""La sala del equipo abierta solo para este ordenador en un puerto libre."""
	equipo.servicio.sala.abrir(red=False, puerto=0)
	return equipo.servicio.sala


@pytest.fixture
def conectar(equipo, sala_abierta) -> Iterator[Callable[..., ClienteSupervision]]:
	"""Crea clientes reales conectados a la sala y los detiene al terminar."""
	clientes: list[ClienteSupervision] = []

	def crear(alias: str = "Luna", **opciones) -> ClienteSupervision:
		cliente = ClienteSupervision(
			"127.0.0.1",
			sala_abierta.sala.puerto_local,
			sala_abierta.sala.codigo,
			alias,
			entorno="Casa de prueba",
			actividad="Buscar la llave",
			modo="juego",
			carpeta_config=equipo.carpeta / f"cliente-{len(clientes)}",
			**opciones,
		)
		cliente.iniciar()
		clientes.append(cliente)
		assert _esperar(lambda: cliente.conectado), "el cliente no ha conectado con la sala"
		return cliente

	yield crear
	for cliente in clientes:
		cliente.detener(0.5)


def _estado(cliente: ClienteSupervision, equipo, **extra) -> None:
	datos = {
		"planta": equipo.contexto.entorno.plantas[0].id,
		"x": 6.0,
		"y": 2.0,
		"rumbo": 90.0,
		"espacio": "Cocina",
		"descripcion": "Cocina, mirando al este",
		"delante": "Una mesa a dos metros",
		"pausado": False,
		"tiempo_activo": 12.5,
		"contadores": {"distancia_m": 8.2, "choques": 1, "ayudas": 2},
	}
	datos.update(extra)
	cliente.estado(datos)


# ── Lógica ───────────────────────────────────────────────────────────────────


def test_clave_de_configuracion_de_los_sucesos_anunciados():
	config = obtener_configuracion()
	assert config.obtener("supervision.eventos_anunciados") == textos.EVENTOS_ANUNCIADOS_DE_SERIE
	assert pres.leer_tipos(config) == set(textos.EVENTOS_ANUNCIADOS_DE_SERIE.split(","))
	pres.guardar_anuncios(config, False, ["voz", "choque", "tipo_inventado"])
	assert config.obtener("supervision.eventos_anunciados") == "choque,voz"
	assert config.obtener("supervision.anunciar_eventos") is False
	with pytest.raises(ErrorValidacion):
		config.establecer("supervision.eventos_anunciados", "x" * 300)
	with pytest.raises(ErrorValidacion):
		config.establecer("supervision.eventos_anunciados", ["choque"])


def test_fila_y_textos_de_un_alumno():
	alumno = {
		"id": "Luna",
		"alias": "Luna",
		"conectado": True,
		"entorno": "Casa",
		"actividad": "Buscar",
		"posicion": "Cocina, mirando al este",
		"delante": "Una mesa",
		"rumbo": 90.0,
		"tiempo_activo": 75.0,
		"contadores": {"choques": 2},
		"eventos": [{"tipo": "ayuda"}, {"tipo": "objetivo"}, {"tipo": "objetivo"}],
		"pausado": False,
	}
	assert pres.fila_alumno(alumno) == ["Luna", "Jugando", "Casa", "Buscar", "Cocina, mirando al este", "Este", "1 min 15 s", "2", "1", "2"]
	assert pres.texto_posicion(alumno) == "Cocina, mirando al este. Delante: Una mesa"
	assert pres.estado_alumno({**alumno, "pausado": True}) == "En pausa"
	assert pres.estado_alumno({**alumno, "conectado": False}) == "Sin conexión"
	assert "Luna, jugando. Cocina" in pres.resumen_hablado(alumno)
	assert pres.texto_posicion(None) == "Ningún alumno elegido."


def test_texto_de_la_sala_cerrada_local_y_en_red():
	assert "cerrada" in pres.texto_sala({"activa": False})
	assert "no se pudo abrir: puerto ocupado" in pres.texto_sala({"activa": False}, error="puerto ocupado")
	local = pres.texto_sala({"activa": True, "codigo": "123456", "red": False, "puerto_local": 5000, "alumnos": []})
	assert "1 2 3 4 5 6" in local and "solo este ordenador" in local and "cortafuegos" not in local
	red = pres.texto_sala(
		{
			"activa": True,
			"codigo": "123456",
			"red": True,
			"puerto": 47900,
			"direcciones": ["192.168.1.20"],
			"huella_legible": "ab12 cd34",
			"alumnos": [],
		},
		segunda_salida=True,
	)
	assert "192.168.1.20" in red and "ab12 cd34" in red and "cortafuegos" in red and "Segunda salida" in red


def test_frases_a_anunciar_filtra_por_tipo_y_no_satura():
	choque = {"tipo": "evento", "alias": "Luna", "datos": {"t": 1.0, "tipo": "choque", "datos": {"con": "la mesa"}}}
	voz = {"tipo": "voz", "alias": "Luna", "datos": {"texto": "Mesa."}}
	entra = {"tipo": "conectado", "alias": "Luna", "datos": {}}
	raro = {"tipo": "evento", "alias": "Luna", "datos": {"tipo": "cambio_suelo", "datos": {}}}
	assert pres.categoria(choque) == "choque" and pres.categoria(voz) == "voz" and pres.categoria(raro) is None
	assert pres.frases_a_anunciar([choque, voz, entra, raro], True, {"choque", "conexion"}) == [
		"Luna: choca con la mesa.",
		"Luna se ha conectado.",
	]
	assert pres.frases_a_anunciar([choque], False, {"choque"}) == []
	muchas = pres.frases_a_anunciar([choque] * 5, True, {"choque"})
	assert len(muchas) == 3 and muchas[-1] == "Y 3 sucesos más."
	assert pres.texto_evento("ayuda", {"ayuda": "donde_estoy"}) == "Pide la ayuda «Dónde estoy»"


# ── Ventana ──────────────────────────────────────────────────────────────────


def test_teclado_de_la_ventana_y_sus_dialogos(equipo):
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)
	revisar(ventana)
	atajos = {(banderas, tecla) for banderas, tecla, _id in ventana._atajos_accesibles}
	assert (wx.ACCEL_CTRL, ord("P")) in atajos and (wx.ACCEL_NORMAL, wx.WXK_F6) in atajos and len(atajos) == 10
	for dialogo in (
		ui.DialogoPista(ventana, "Luna"),
		ui.DialogoAnuncios(ventana, equipo.contexto.configuracion),
		ui.DialogoSesionLocal(ventana, equipo.contexto, ["Luna"], [("Casa", equipo.carpeta / "casa.elab")]),
	):
		revisar(dialogo)
		dialogo.Destroy()
	ventana.Destroy()


def test_abrir_copiar_y_cerrar_la_sala_desde_la_ventana(equipo, monkeypatch):
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)
	assert "cerrada" in ventana.estado.GetValue()
	assert not ventana.botones["cerrar_sala"].IsEnabled() and not ventana.botones["pausar"].IsEnabled()
	monkeypatch.setattr(equipo.servicio.sala, "puerto_configurado", lambda: 0)
	copiado: list[str] = []
	monkeypatch.setattr(wx.TheClipboard, "Open", lambda: True)
	monkeypatch.setattr(wx.TheClipboard, "Close", lambda: None)
	monkeypatch.setattr(wx.TheClipboard, "SetData", lambda dato: copiado.append(dato.GetText()) or True)
	ventana.abrir_sala()
	codigo = equipo.servicio.sala.sala.codigo
	assert equipo.servicio.sala.activa and " ".join(codigo) in ventana.estado.GetValue()
	assert any("Sala abierta solo para este ordenador" in texto for texto in equipo.contexto.anunciados)
	assert not ventana.botones["abrir"].IsEnabled() and not ventana.modo.IsEnabled()
	ventana.copiar_codigo()
	assert copiado == [codigo]
	ventana.cerrar_sala()
	assert not equipo.servicio.sala.activa and "cerrada" in ventana.estado.GetValue()
	ventana.Destroy()


def test_aparece_el_alumno_y_llega_lo_que_oye_sin_mover_el_foco(equipo, conectar):
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)
	reconstrucciones: list[int] = []
	original = ventana.lista.reemplazar_filas
	ventana.lista.reemplazar_filas = lambda filas, **kw: (reconstrucciones.append(len(filas)), original(filas, **kw))[1]
	luna = conectar("Luna")
	_estado(luna, equipo)
	assert _esperar(lambda: ventana.lista.numero_filas() == 1 and ventana.lista.valores_fila(0)[4].startswith("Cocina"), ventana.refrescar)
	fila = ventana.lista.valores_fila(0)
	assert fila[:4] == ["Luna", "Jugando", "Casa de prueba", "Buscar la llave"]
	assert fila[5:] == ["Este", "13 s", "1", "2", "0"]
	assert ventana.posicion.GetValue() == "Cocina, mirando al este. Delante: Una mesa a dos metros"
	assert ventana.botones["pausar"].IsEnabled()

	luna.voz("Estás en la cocina.")
	luna.voz("Mesa.")
	luna.evento("choque", {"con": "la mesa", "t": 12.6})
	luna.evento("premio", {"id": "llave", "nombre": "Llave dorada", "t": 13.0})
	assert _esperar(lambda: ventana.sucesos.numero_filas() == 2 and ventana.ultimo.GetValue() == "Mesa.", ventana.refrescar)
	assert ventana.historial.GetValue().splitlines() == ["Estás en la cocina.", "Mesa."]
	assert [ventana.sucesos.valores_fila(i)[1] for i in range(2)] == ["Choca con la mesa", "Encuentra el premio «Llave dorada»"]
	dicho = equipo.contexto.anunciados
	assert "Luna se ha conectado." in dicho and "Luna: choca con la mesa." in dicho and "Luna: encuentra el premio «Llave dorada»." in dicho
	assert not any("oye:" in texto for texto in dicho), "lo que oye el alumno no se anuncia si no se pide"

	# Llega otro alumno y cambian los datos: la fila elegida y el cursor del historial no se mueven, y la lista no se rehace.
	ventana.historial.SetInsertionPoint(0)
	sol = conectar("Sol")
	_estado(sol, equipo, descripcion="Dormitorio, mirando al norte", rumbo=0.0)
	_estado(luna, equipo, tiempo_activo=40.0, contadores={"choques": 3, "ayudas": 2})
	luna.voz("Puerta abierta.")
	assert _esperar(
		lambda: (
			ventana.lista.numero_filas() == 2
			and ventana.lista.valores_fila(0)[7] == "3"
			and "Puerta abierta." in ventana.historial.GetValue()
		),
		ventana.refrescar,
	)
	assert ventana.lista.fila_actual() == 0 and ventana.elegido()["alias"] == "Luna"
	assert ventana.historial.GetInsertionPoint() == 0
	assert reconstrucciones == []
	assert ventana.lista.valores_fila(1)[0] == "Sol"
	# Al elegir al otro alumno se enseña lo suyo.
	ventana.lista.enfocar_fila(1, anunciar=False)
	ventana._pintar_elegido()
	assert ventana.historial.GetValue() == "" and ventana.sucesos.numero_filas() == 0
	assert ventana.posicion.GetValue().startswith("Dormitorio")
	ventana.decir_estado()
	assert equipo.contexto.anunciados[-1].startswith("Sol, jugando. Dormitorio")
	ventana.Destroy()


def test_la_ventana_abierta_despues_recupera_lo_ya_ocurrido(equipo, conectar):
	luna = conectar("Luna")
	_estado(luna, equipo)
	luna.voz("Hola.")
	luna.evento("choque", {"con": "la pared"})
	assert _esperar(lambda: bool(equipo.servicio.sala.foto()["alumnos"]) and equipo.servicio.sala.foto()["alumnos"][0]["eventos"])
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)
	assert ventana.lista.numero_filas() == 1
	assert ventana.historial.GetValue().splitlines() == ["Hola."]
	assert ventana.sucesos.valores_fila(0)[1] == "Choca con la pared"
	ventana.refrescar()
	assert ventana.sucesos.numero_filas() == 1, "lo que ya estaba en la foto no se apunta dos veces"
	ventana.Destroy()


def test_pausa_mensaje_pista_y_ayudas_llegan_al_cliente(equipo, conectar, dialogo_modal):
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)
	luna = conectar("Luna")
	_estado(luna, equipo)
	assert _esperar(lambda: ventana.lista.numero_filas() == 1, ventana.refrescar)
	recibidas: list = []
	ventana.pausar()
	assert _esperar(lambda: ("pausa", {}) in recibidas, lambda: _ordenes(luna, recibidas))
	assert "Sesión de Luna en pausa." in equipo.contexto.anunciados
	_estado(luna, equipo, pausado=True)
	assert _esperar(lambda: ventana.lista.valores_fila(0)[1] == "En pausa", ventana.refrescar)
	ventana.pausar()
	assert _esperar(lambda: ("reanudar", {}) in recibidas, lambda: _ordenes(luna, recibidas))

	dialogo_modal.responder(lambda d: (d.campo.SetValue("  Muy bien, sigue por la pared  "), wx.ID_OK)[1])
	ventana.mensaje()
	assert _esperar(lambda: ("mensaje", {"texto": "Muy bien, sigue por la pared"}) in recibidas, lambda: _ordenes(luna, recibidas))

	def pista(dialogo):
		dialogo.campo.SetValue("Está cerca de la ventana")
		dialogo.baliza.SetSelection(2)

	dialogo_modal.responder(responder_con(pista))
	ventana.pista()
	assert _esperar(lambda: any(tipo == "pista" for tipo, _d in recibidas), lambda: _ordenes(luna, recibidas))
	assert dict(recibidas)["pista"] == {"texto": "Está cerca de la ventana", "baliza_s": 20}

	def prohibir_baliza(dialogo):
		tabla = dialogo.tabla
		tabla.lista.enfocar_fila(tabla._claves.index("baliza"), anunciar=False)
		tabla.cambiar("prohibida")

	dialogo_modal.responder(responder_con(prohibir_baliza))
	ventana.ayudas()
	assert _esperar(lambda: any(tipo == "ayudas" for tipo, _d in recibidas), lambda: _ordenes(luna, recibidas))
	assert dict(recibidas)["ayudas"] == {"ayudas": {"baliza": {"permitida": False, "limite": None}}}
	# Las intervenciones quedan en la lista de sucesos del alumno.
	textos_sucesos = [ventana.sucesos.valores_fila(i)[1] for i in range(ventana.sucesos.numero_filas())]
	assert "Intervención del profesional: pausa" in textos_sucesos and "Intervención del profesional: ayudas" in textos_sucesos
	ventana.Destroy()


def test_recolocar_premio_reiniciar_y_terminar(equipo, conectar, dialogo_modal):
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)
	luna = conectar("Luna")
	_estado(luna, equipo)
	assert _esperar(lambda: ventana.lista.numero_filas() == 1 and ventana.elegido().get("x") == 6.0, ventana.refrescar)
	recibidas: list = []
	planta = equipo.contexto.entorno.plantas[0].id

	def al_dormitorio(dialogo):
		assert dialogo.lugar.espacio.GetStringSelection() == "Cocina", "se parte de donde está el alumno"
		elegir(dialogo.lugar.espacio, "Dormitorio")
		elegir(dialogo.lugar.modo, "centro")

	dialogo_modal.responder(responder_con(al_dormitorio))
	ventana.recolocar()
	assert _esperar(lambda: any(tipo == "recolocar" for tipo, _d in recibidas), lambda: _ordenes(luna, recibidas))
	recolocar = dict(recibidas)["recolocar"]
	assert recolocar["planta"] == planta and (recolocar["x"], recolocar["y"]) == (2.0, 2.0) and recolocar["rumbo"] == 90.0
	assert any("Luna recolocado: Dormitorio" in texto for texto in equipo.contexto.anunciados)

	def premio(dialogo):
		dialogo.nombre.SetValue("Estrella sorpresa")
		elegir(dialogo.lugar.espacio, "Cocina")
		elegir(dialogo.lugar.modo, "centro")

	dialogo_modal.responder(responder_con(premio))
	ventana.premio()
	assert _esperar(lambda: any(tipo == "premio" for tipo, _d in recibidas), lambda: _ordenes(luna, recibidas))
	enviado = dict(recibidas)["premio"]
	assert (
		enviado["nombre"] == "Estrella sorpresa"
		and enviado["id"] == "extra-1"
		and enviado["planta"] == planta
		and enviado["visibilidad"] == "cerca"
	)

	# Reiniciar y terminar piden confirmación con un botón que nombra la acción; cancelar no envía nada.
	dialogo_modal.responder(wx.ID_CANCEL)
	ventana.reiniciar()
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	ventana.reiniciar()
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	ventana.terminar_sesion()
	assert _esperar(lambda: ("terminar", {}) in recibidas, lambda: _ordenes(luna, recibidas))
	assert [tipo for tipo, _d in recibidas].count("reiniciar") == 1
	ventana.Destroy()


def test_la_marca_queda_guardada_en_la_sesion_del_alumno(equipo, conectar, dialogo_modal):
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)
	luna = conectar("Luna")
	_estado(luna, equipo)
	assert _esperar(lambda: ventana.lista.numero_filas() == 1, ventana.refrescar)
	dialogo_modal.responder(lambda d: (d.campo.SetValue("Duda en la puerta de la cocina"), wx.ID_OK)[1])
	ventana.marca()
	recibidas: list = []
	assert _esperar(lambda: any(tipo == "marca" for tipo, _d in recibidas), lambda: _ordenes(luna, recibidas))
	assert ventana.sucesos.valores_fila(0)[1] == "Marca del profesional: Duda en la puerta de la cocina"
	assert equipo.servicio.sala.marcas[0]["texto"] == "Duda en la puerta de la cocina"
	# El reproductor pasa la marca a su grabadora; al incorporar la sesión queda, cifrada, en la base.
	grabacion = grabadora.Grabadora(
		"Luna", "casa", "Casa de prueba", "buscar", "Buscar la llave", "busqueda", "juego", carpeta=equipo.servicio.acceso.carpeta_sesiones
	)
	grabacion.muestra(0.0, "p0", 1.0, 1.0, 0.0)
	grabacion.muestra(5.0, "p0", 2.0, 1.0, 0.0)
	grabacion.marca(dict(recibidas)["marca"]["texto"])
	grabacion.terminar(True, {})
	base = equipo.abrir_base()
	lista = sesiones.listar(base, Fichas(base).por_alias("Luna").id)
	assert [marca["texto"] for marca in sesiones.marcas(base, lista[0]["id"])] == ["Duda en la puerta de la cocina"]
	equipo.servicio.acceso.bloquear()
	assert b"Duda en la puerta" not in (equipo.carpeta / "db" / "entornolab.db").read_bytes()
	ventana.Destroy()


def test_desconexion_y_quitar_de_la_lista(equipo, conectar):
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)
	luna = conectar("Luna")
	_estado(luna, equipo)
	assert _esperar(lambda: ventana.lista.numero_filas() == 1, ventana.refrescar)
	luna.detener(0.5)
	assert _esperar(lambda: ventana.lista.valores_fila(0)[1] != "Jugando", ventana.refrescar)
	assert not ventana.botones["pausar"].IsEnabled() and ventana.botones["olvidar"].IsEnabled()
	ventana.pausar()
	assert equipo.contexto.anunciados[-1] == "Luna no está conectado."
	ventana.olvidar()
	assert ventana.lista.numero_filas() == 0 and ventana.posicion.GetValue() == "Ningún alumno elegido."
	ventana.Destroy()


def test_anuncios_por_voz_configurables(equipo, conectar, dialogo_modal):
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)

	def solo_voz(dialogo):
		for indice in range(dialogo.lista.GetCount()):
			dialogo.lista.Check(indice, dialogo._tipos[indice] == "voz")

	dialogo_modal.responder(responder_con(solo_voz))
	ventana.anuncios()
	assert equipo.contexto.configuracion.obtener("supervision.eventos_anunciados") == "voz"
	luna = conectar("Luna")
	luna.evento("choque", {"con": "la mesa"})
	luna.voz("Mesa.")
	assert _esperar(lambda: "Luna oye: Mesa." in equipo.contexto.anunciados, ventana.refrescar)
	assert not any("choca" in texto or "conectado" in texto for texto in equipo.contexto.anunciados)
	# Con el interruptor general apagado no se dice nada, pero todo sigue en las listas.
	dialogo_modal.responder(responder_con(lambda d: d.activados.SetValue(False)))
	ventana.anuncios()
	antes = len(equipo.contexto.anunciados)
	luna.voz("Silla.")
	assert _esperar(lambda: "Silla." in ventana.historial.GetValue(), ventana.refrescar)
	assert len(equipo.contexto.anunciados) == antes
	ventana.segunda.SetValue(True)
	ventana._guardar_segunda()
	assert equipo.contexto.configuracion.obtener("supervision.segunda_salida") is True
	ventana.Destroy()


def test_empezar_sesion_en_este_ordenador(equipo, dialogo_modal, tmp_path):
	base = equipo.abrir_base()
	Fichas(base).alta("Luna")
	equipo.contexto.ruta_paquete = tmp_path / "casa.elab"
	equipo.contexto.actividades.append({"id": "buscar", "nombre": "Buscar la llave", "tipo": "busqueda"})
	equipo.contexto.guardar()
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)

	def elegir_todo(dialogo):
		assert dialogo.alumno.GetStrings() == ["Invitado (sin ficha)", "Luna"]
		assert "el entorno abierto" in dialogo.entorno.GetStringSelection()
		assert dialogo.actividad.GetStrings()[1] == "Buscar la llave" and dialogo.actividad.GetSelection() == 1
		dialogo.alumno.SetSelection(1)

	dialogo_modal.responder(responder_con(elegir_todo))
	ventana.empezar_sesion()
	sala = equipo.servicio.sala
	assert sala.activa, "si la sala estaba cerrada se abre una solo para este ordenador"
	orden = equipo.contexto.lanzados[0].orden
	assert orden == [
		str(tmp_path / "casa.elab"),
		"--actividad",
		"buscar",
		"--alumno",
		"Luna",
		"--sala",
		f"127.0.0.1:{sala.sala.puerto_local}",
		"--codigo",
		sala.sala.codigo,
	]
	assert equipo.servicio.procesos == equipo.contexto.lanzados
	ventana.Destroy()


def test_cerrar_la_ventana_con_la_sala_abierta_pregunta(equipo, sala_abierta, dialogo_modal):
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)
	dialogo_modal.responder(wx.ID_CANCEL)
	assert ventana.puede_cerrar() is False and sala_abierta.activa
	dialogo_modal.responder(lambda d: d.ids_opciones[1])
	assert ventana.puede_cerrar() is True and sala_abierta.activa
	dialogo_modal.responder(lambda d: d.ids_opciones[0])
	assert ventana.puede_cerrar() is True and not sala_abierta.activa
	ventana.al_cerrar()
	ventana.Destroy()


# ── Ficha del alumno, preferencias y cierre del reproductor ──────────────────


def test_frases_del_reproductor_que_se_cierra():
	normal = {"tipo": "proceso_terminado", "alumno": "Luna", "alias": "Luna", "datos": {"codigo": 0, "inesperado": False}}
	roto = {"tipo": "proceso_terminado", "alumno": "", "alias": "", "datos": {"codigo": None, "inesperado": True}}
	assert pres.frase_suceso(normal) == "El reproductor de Luna se ha cerrado."
	assert pres.frase_suceso(roto) == "El reproductor se ha cerrado inesperadamente; puede volver a abrirlo."
	assert pres.categoria(normal) == "conexion"
	# El cierre inesperado se dice aunque no se hayan elegido los avisos de conexión.
	assert pres.frases_a_anunciar([normal, roto], True, set()) == ["El reproductor se ha cerrado inesperadamente; puede volver a abrirlo."]
	assert pres.frases_a_anunciar([normal], True, {"conexion"}) == ["El reproductor de Luna se ha cerrado."]


def test_la_ventana_apunta_y_dice_que_el_reproductor_se_ha_cerrado(equipo, conectar, monkeypatch):
	conectar("Luna")
	ventana = ui.VentanaSupervision(equipo.contexto, equipo.servicio)
	assert _esperar(lambda: bool(ventana._ids), ventana.refrescar)
	suceso = {
		"tipo": "proceso_terminado",
		"alumno": "Luna",
		"alias": "Luna",
		"hora": time.time(),
		"datos": {"codigo": 1, "inesperado": True},
	}
	sala = equipo.servicio.sala.sala
	pendientes = sala.eventos_pendientes
	monkeypatch.setattr(sala, "eventos_pendientes", lambda: [suceso, *pendientes()])
	ventana.refrescar()
	monkeypatch.setattr(sala, "eventos_pendientes", pendientes)
	assert "El reproductor de Luna se ha cerrado inesperadamente; puede volver a abrirlo." in equipo.contexto.anunciados
	assert any("se ha cerrado inesperadamente" in evento["tipo"] for evento in ventana._eventos["Luna"])
	ventana.Destroy()


def test_al_conectarse_un_alumno_con_ficha_le_llega_su_ficha(equipo, conectar):
	fichas = Fichas(equipo.abrir_base())
	luna = fichas.alta("Luna", nombre_real="Nombre Muy Privado", estilo="juvenil", ajustes={"paso_m": 0.8, "unidad": "pasos"})
	cliente = conectar("Luna")
	sin_ficha = conectar("Sol")
	recibidas: list = []
	otras: list = []
	assert _esperar(
		lambda: any(tipo == "alumno" for tipo, _datos in recibidas), lambda: (equipo.servicio.sala.sondear(), _ordenes(cliente, recibidas))
	)
	(datos,) = [datos for tipo, datos in recibidas if tipo == "alumno"]
	assert datos["ajustes"] == {"paso_m": 0.8, "unidad": "pasos", "estilo": "juvenil"} and datos["lista"] == [] and datos["niveles"] == {}
	assert "Nombre Muy Privado" not in str(datos)
	_ordenes(sin_ficha, otras)
	assert not any(tipo == "alumno" for tipo, _datos in otras), "sin ficha no se envía nada"
	# Al cambiar la ficha se reenvía; si no cambia nada, no.
	luna = fichas.editar(luna.id, ajustes={"paso_m": 0.9, "unidad": "pasos"})
	assert equipo.servicio.enviar_ficha(luna) == 1
	assert equipo.servicio.enviar_ficha(luna) == 1
	recibidas.clear()
	assert _esperar(lambda: any(tipo == "alumno" for tipo, _datos in recibidas), lambda: _ordenes(cliente, recibidas))
	time.sleep(0.2)
	_ordenes(cliente, recibidas)
	assert [datos["ajustes"]["paso_m"] for tipo, datos in recibidas if tipo == "alumno"] == [0.9], (
		"el envío repetido e igual no se manda dos veces"
	)
	# Preferencias del Estudio: se pide releer a todos los conectados.
	assert equipo.servicio.releer_configuracion_en_reproductores() == 2
	assert _esperar(lambda: any(tipo == "releer_configuracion" for tipo, _datos in recibidas), lambda: _ordenes(cliente, recibidas))
