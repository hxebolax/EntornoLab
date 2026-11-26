"""La ficha del alumno en el Estudio llega al reproductor por la sala, y lo jugado vuelve a la ficha.

Tramo a tramo, con piezas de verdad: la base cifrada del seguimiento, el
``ServicioSeguimiento`` con su ``GestorSala`` y una ``Sala`` real en
127.0.0.1, y el reproductor ``Aplicacion(pruebas=True)`` conectado a ella.

- Ajustes de juego, lista de trabajo y niveles de la ficha → orden ``alumno``
  → mandan sobre las preferencias locales, también en la partida en marcha, y
  quedan en el perfil para los días sin sala. Nunca viaja el nombre real ni
  las notas.
- Nivel de ida y vuelta: la ficha dice en qué nivel empieza la actividad; al
  terminarla, el reproductor lo apunta, la sesión grabada lo lleva y al
  incorporarla vuelve a la ficha, junto con las recompensas ganadas.
"""

# ruff: noqa: F811 - los parámetros de las pruebas se llaman como las fixtures importadas
from __future__ import annotations

import json
import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from app.dominio.formato import cargar_paquete
from app.reproductor import puente_actividades
from app.reproductor.alumno import Perfil
from app.seguimiento import grabadora, recompensas
from app.supervision import protocolo
from app.ui.seguimiento import presentador_alumnos
from app.ui.seguimiento.acceso import AccesoDatos
from app.ui.seguimiento.sala import GestorSala
from app.ui.seguimiento.servicio import ServicioSeguimiento

from .test_reproductor_comun import VIVIENDA, Robot, crear_app, paquete_con_busqueda, sin_navegador  # noqa: F401 - fixtures

CONTRASENA = "clave de prueba 1"
RAPIDO = {"intervalo_estado": 0.05, "intervalo_latido": 0.2, "tiempo_muerto": 1.0, "reintento_min": 0.05, "reintento_max": 0.2}
NOMBRE_REAL = "Ana Secretísima"
NOTAS = "Notas privadas de la profesional"


@pytest.fixture
def estudio(tmp_path: Path, data_temporal: Path):
	"""El lado del Estudio: base desbloqueada y sala abierta solo para este ordenador."""
	from app.core.configuracion import Configuracion

	contexto = SimpleNamespace(configuracion=Configuracion(tmp_path / "estudio" / "config.json"))
	acceso = AccesoDatos(
		contexto.configuracion,
		ruta_base=tmp_path / "estudio" / "entornolab.db",
		ruta_acceso=tmp_path / "estudio" / "acceso.json",
		carpeta_sesiones=data_temporal / "sessions",
	)
	acceso.crear_contrasena(CONTRASENA)
	sala = GestorSala(contexto.configuracion, carpeta_config=tmp_path / "estudio")
	servicio = ServicioSeguimiento(contexto, acceso=acceso, sala=sala)
	sala.abrir(red=False, puerto=0, anunciar=False)
	yield servicio
	servicio.cerrar()


def hasta(robot: Robot, servicio: ServicioSeguimiento, condicion: Callable[[], Any], segundos: float = 8.0) -> bool:
	"""Deja pasar fotogramas del reproductor y sondea la sala del Estudio hasta que se cumpla la condición."""
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		robot.esperar(1)
		servicio.sala.sondear()
		if condicion():
			return True
		time.sleep(0.01)
	return bool(condicion())


def conectar(robot: Robot, servicio: ServicioSeguimiento) -> None:
	sala = servicio.sala.sala
	robot.app.opciones_cliente = dict(RAPIDO)
	robot.app.conectar_sala("127.0.0.1", sala.puerto, sala.codigo)
	assert hasta(robot, servicio, lambda: robot.app.enlace.conectado), "el reproductor no se ha conectado a la sala"


def _id_vivienda() -> str:
	return str(cargar_paquete(VIVIENDA).entorno.id)


# ── Lo que viaja: solo lo de jugar ───────────────────────────────────────────


def test_lo_que_se_envia_no_lleva_datos_personales_y_cumple_el_protocolo(estudio):
	fichas = estudio.fichas()
	alumno = fichas.alta(
		"Luna",
		nombre_real=NOMBRE_REAL,
		notas=NOTAS,
		ano_nacimiento=2012,
		perfil="baston",
		estilo="infantil",
		ajustes={
			"paso_m": 0.8,
			"giro_grados": 30.0,
			"unidad": "pasos",
			"detalle": 3,
			"velocidad_ms": 99.0,  # fuera de rango: no se envía, pero no impide enviar el resto
			presentador_alumnos.CLAVE_LISTA_TRABAJO: [
				{
					"entorno_id": "casa",
					"entorno_nombre": "Casa",
					"actividad_id": "busca",
					"actividad_nombre": "Busca",
					"paquete": "casa.elab",
					"asignada": "2026-01-01",
				}
			],
			presentador_alumnos.CLAVE_NIVELES: {"casa/busca": 2},
		},
	)
	datos = presentador_alumnos.datos_para_reproductor(alumno)
	assert datos["ajustes"] == {"paso_m": 0.8, "giro_grados": 30.0, "unidad": "pasos", "estilo": "infantil", "detalle": 3}
	assert datos["lista"] == [
		{"entorno_id": "casa", "entorno_nombre": "Casa", "actividad_id": "busca", "actividad_nombre": "Busca", "paquete": "casa.elab"}
	]
	assert datos["niveles"] == {"casa/busca": 2}
	linea = protocolo.codificar("alumno", datos, sentido=protocolo.A_JUGAR).decode("utf-8")
	for privado in (NOMBRE_REAL, NOTAS, "2012", "baston"):
		assert privado not in linea
	assert protocolo.decodificar(linea, protocolo.A_JUGAR).datos == datos


# ── Estudio → sala → reproductor ─────────────────────────────────────────────


def test_la_ficha_manda_sobre_lo_local_tambien_a_mitad_de_partida(estudio, data_temporal, sin_navegador):
	from app.core.configuracion import Configuracion

	entorno_id = _id_vivienda()
	ruta = paquete_con_busqueda(data_temporal / "entornos")
	fichas = estudio.fichas()
	alumno = fichas.alta(
		"Luna",
		nombre_real=NOMBRE_REAL,
		notas=NOTAS,
		estilo="infantil",
		ajustes={"paso_m": 0.8, "giro_grados": 30.0, "unidad": "pasos", "formato_direccion": "cardinal"},
	)
	alumno = presentador_alumnos.asignar(
		fichas,
		alumno,
		SimpleNamespace(id=entorno_id, nombre="Vivienda de ejemplo"),
		{"id": "busca", "nombre": "Busca los premios"},
		ruta.name,
	)
	app = crear_app("--alumno", "Luna")
	try:
		robot = Robot(app)
		# El alumno tenía sus propias preferencias en este equipo.
		app.establecer("juego.unidad", "metros")
		app.establecer("juego.paso_m", 0.5)
		assert app.ajustes_juego().paso_m == 0.5
		conectar(robot, estudio)
		assert hasta(robot, estudio, lambda: app.perfil.ficha.get("ajustes", {}).get("paso_m") == 0.8), (
			"la ficha no ha llegado al reproductor"
		)
		ajustes = app.ajustes_juego()
		assert (ajustes.paso_m, ajustes.giro_grados, ajustes.unidad, ajustes.formato_direccion, ajustes.estilo) == (
			0.8,
			30.0,
			"pasos",
			"cardinal",
			"infantil",
		)
		assert app.estilo == "infantil"
		# Queda en el perfil (para los días sin sala) sin ningún dato personal; la configuración compartida no se toca.
		texto_perfil = app.perfil.ruta.read_text(encoding="utf-8")
		assert NOMBRE_REAL not in texto_perfil and NOTAS not in texto_perfil
		assert [entrada["actividad_id"] for entrada in app.perfil.lista_trabajo] == ["busca"]
		compartida = Configuracion()
		assert compartida.obtener("juego.paso_m") == 0.6 and compartida.obtener("juego.unidad") == "metros"

		# La lista de trabajo se ofrece la primera en «Elegir entorno», y la actividad asignada va delante.
		robot.elegir("Elegir entorno")
		assert robot.opciones()[0] == "Lo que te ha puesto tu profesor"
		robot.elegir("Lo que te ha puesto tu profesor")
		assert robot.opciones()[0] == "Busca los premios, en Vivienda de ejemplo"
		robot.elegir("Busca los premios", 3)
		partida = robot.partida
		assert partida is not None and partida.id_actividad == "busca"
		assert partida.sesion.ajustes.paso_m == 0.8

		# El profesional cambia la ficha con la partida en marcha: la partida se recalcula al momento.
		alumno = fichas.editar(alumno.id, ajustes={**fichas.obtener(alumno.id).ajustes, "paso_m": 0.9, "detalle": 1})
		assert estudio.enviar_ficha(alumno) == 1
		assert hasta(robot, estudio, lambda: partida.sesion.ajustes.paso_m == 0.9)
		assert partida.sesion.ajustes.detalle == 1
		assert app.fallos == 0
	finally:
		app.cerrar_todo()

	# Otro día, sin sala: el reproductor sigue usando lo último que dijo la ficha.
	otra_vez = crear_app("--alumno", "Luna")
	try:
		assert otra_vez.ajustes_juego().paso_m == 0.9 and otra_vez.estilo == "infantil"
		assert otra_vez.enlace is None
	finally:
		otra_vez.cerrar_todo()


def test_un_ajuste_que_cambia_el_alumno_vale_hasta_la_siguiente_ficha(data_temporal, sin_navegador):
	app = crear_app("--alumno", "Sol")
	try:
		app.recibir_ficha({"ajustes": {"paso_m": 0.8, "unidad": "pasos"}, "lista": [], "niveles": {}})
		assert app.preferencia("juego.paso_m") == 0.8
		app.establecer("juego.paso_m", 0.55)
		assert app.preferencia("juego.paso_m") == 0.55 and app.preferencia("juego.unidad") == "pasos"
		app.recibir_ficha({"ajustes": {"paso_m": 0.8}})
		assert app.preferencia("juego.paso_m") == 0.8, "la ficha que llega después vuelve a mandar"
		# Sin alumno elegido no hay ficha que aplicar.
		app.poner_alumno("")
		app.recibir_ficha({"ajustes": {"paso_m": 1.2}})
		assert app.preferencia("juego.paso_m") == 0.6
	finally:
		app.cerrar_todo()


def test_los_niveles_de_la_ficha_mandan_solo_si_la_ficha_ha_cambiado(data_temporal):
	perfil = Perfil.cargar("Mar")
	assert perfil.recibir_ficha(None, None, {"casa/busca": 1}) == ["casa/busca"]
	assert perfil.nivel("casa", "busca") == 1
	perfil.poner_nivel("casa", "busca", 2)  # sube de nivel jugando aquí
	assert perfil.recibir_ficha(None, None, {"casa/busca": 1}) == [], "la misma ficha sin poner al día no le hace retroceder"
	assert perfil.nivel("casa", "busca") == 2
	assert perfil.recibir_ficha(None, None, {"casa/busca": 0}) == ["casa/busca"], "si el profesional lo cambia, manda la ficha"
	assert Perfil.cargar("Mar").nivel("casa", "busca") == 0


# ── Nivel y recompensas: de la ficha a la partida y de vuelta a la ficha ─────


@pytest.mark.lento
def test_nivel_de_ida_y_vuelta_y_recompensas_en_la_ficha(estudio, data_temporal, sin_navegador):
	if not puente_actividades.disponible():
		pytest.skip("app.actividades no está disponible")
	entorno_id = _id_vivienda()
	clave = f"{entorno_id}/busca"
	paquete_con_busqueda(data_temporal / "entornos", premios=1, usar_niveles=True)
	fichas = estudio.fichas()
	fichas.alta("Luna", ajustes={presentador_alumnos.CLAVE_NIVELES: {clave: 1}})
	app = crear_app("--alumno", "Luna")
	try:
		robot = Robot(app)
		conectar(robot, estudio)
		assert hasta(robot, estudio, lambda: app.nivel_actividad(entorno_id, "busca") == 1), "el nivel de la ficha no ha llegado"
		robot.elegir("Elegir entorno")
		robot.elegir("Vivienda de ejemplo")
		robot.elegir("Busca los premios", 3)
		partida = robot.partida
		assert partida.nivel_pedido == 1 and partida.estado_actividad().get("nivel") == 1, partida.estado_actividad()
		for premio in list(partida.datos["premios"]):
			robot.seguir((premio["planta"], premio["x"], premio["y"]))
			robot.esperar(5)
			if not partida.terminado and str(premio["id"]) not in partida.premios_recogidos:
				robot.accion("interactuar", 5)
		robot.esperar(5)
		assert partida.terminado and partida.completada, partida.estado_actividad()
		assert partida.resultado["nivel_superado"] and partida.resultado["nivel_siguiente"] == 2
		assert app.nivel_actividad(entorno_id, "busca") == 2, "el reproductor apunta el nivel siguiente en el perfil"
		ganadas = list(partida.resultado["recompensas"])
		assert ganadas, "la actividad completada da alguna recompensa"
		robot.elegir("Volver al menú principal")
	finally:
		app.cerrar_todo()

	# El Estudio incorpora la sesión: el nivel y las recompensas acaban en la ficha.
	resultado = grabadora.incorporar_sesiones(data_temporal / "sessions", estudio.base)
	assert resultado.nuevas == 1 and not resultado.erroneas
	alumno = fichas.por_alias("Luna")
	assert presentador_alumnos.niveles_de(alumno) == {clave: 2}
	coleccion = recompensas.coleccion(estudio.base, alumno.id)
	assert coleccion["estrellas"] == sum(1 for r in ganadas if r["tipo"] == "estrella")
	assert [m["nombre"] for m in coleccion["medallas"]] == [r["nombre"] for r in ganadas if r["tipo"] == "medalla"]
	# Incorporar otra vez no duplica nada ni cambia el nivel.
	grabadora.incorporar_sesiones(data_temporal / "sessions", estudio.base)
	assert recompensas.coleccion(estudio.base, alumno.id)["estrellas"] == coleccion["estrellas"]
	assert presentador_alumnos.niveles_de(fichas.por_alias("Luna")) == {clave: 2}
	# Y la próxima vez que se conecte, la ficha le dice el nivel 2 (el mismo que ya tenía).
	assert presentador_alumnos.datos_para_reproductor(fichas.por_alias("Luna"))["niveles"] == {clave: 2}


def test_una_sesion_vieja_no_hace_retroceder_el_nivel_de_la_ficha(estudio):
	fichas = estudio.fichas()
	alumno = fichas.alta("Río")
	nueva = {"actividad_id": "busca", "entorno_id": "casa", "fin": "2026-03-02T10:00:00", "resumen": {"resultado": {"nivel_siguiente": 3}}}
	vieja = {"actividad_id": "busca", "entorno_id": "casa", "fin": "2026-03-01T10:00:00", "resumen": {"resultado": {"nivel_siguiente": 1}}}
	alumno = grabadora.anotar_nivel_de_sesion(fichas, alumno, nueva)
	alumno = grabadora.anotar_nivel_de_sesion(fichas, alumno, vieja)
	assert presentador_alumnos.niveles_de(alumno) == {"casa/busca": 3}
	sin_nivel = {"actividad_id": "busca", "entorno_id": "casa", "fin": "2026-03-03T10:00:00", "resumen": {"resultado": None}}
	assert grabadora.anotar_nivel_de_sesion(fichas, alumno, sin_nivel) is alumno


def test_el_perfil_aguanta_una_ficha_tocada_a_mano(data_temporal):
	perfil = Perfil.cargar("Eco")
	perfil.guardar()
	datos = json.loads(perfil.ruta.read_text(encoding="utf-8"))
	datos["ficha"] = {
		"ajustes": {"paso_m": [1, 2], "unidad": "pasos"},
		"lista": ["no", {"actividad_id": 7}],
		"niveles": {"a/b": "dos", "c/d": 1},
	}
	datos["niveles"] = {"a/b": -1, "c/d": 2, "e/f": True}
	perfil.ruta.write_text(json.dumps(datos), encoding="utf-8")
	leido = Perfil.cargar("Eco")
	assert leido.ficha["ajustes"] == {"unidad": "pasos"}
	assert leido.lista_trabajo == [{"actividad_id": "7"}]
	assert leido.ficha["niveles"] == {"c/d": 1} and leido.niveles == {"c/d": 2}
