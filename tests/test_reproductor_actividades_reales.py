"""Los 22 tipos de actividad, jugados de principio a fin desde el reproductor de verdad.

Aquí no hay dobles: ``Aplicacion(pruebas=True)`` con ``app.actividades`` real,
los entornos de ``data/ejemplos`` (solo se leen; cada prueba guarda su copia
con la actividad en una carpeta temporal) y un robot que maneja el reproductor
como el alumno: inyecta acciones reales (``avanzar``, ``interactuar``,
``confirmar``…), elige en los menús hablados y deja pasar fotogramas. Para
moverse usa el robot del motor (``Robot.recorrer``: rutas, puertas, escaleras
y ascensor), pero cada orden pasa por la aplicación, la pantalla de juego y
la sesión, igual que una tecla.

Cada actividad es la de su ejemplo en ``docs/actividades.md``. Cada prueba
comprueba que termina con su ``EvFin`` y con la pantalla de fin, y que la
sesión grabada lleva el resultado con el nivel y la semilla.

Con el tráfico apagado en el barrio: el robot no mira antes de cruzar, y lo
que se prueba aquí es el reproductor, no la prudencia del robot.
"""

# ruff: noqa: F811 - los parámetros de las pruebas se llaman como las fixtures importadas
from __future__ import annotations

import functools
import json
import math
import os
import re
from pathlib import Path
from typing import Any

import pygame
import pytest

from app.actividades import TIPOS
from app.actividades.lugares import punto_interior_de_abertura, salidas_ordenadas
from app.dominio import ejemplos
from app.dominio import geometria as geo
from app.dominio.formato import cargar_paquete, guardar_paquete
from app.motor import eventos as ev
from app.reproductor import entornos
from app.reproductor.aplicacion import Aplicacion
from app.reproductor.menus import Menu
from app.reproductor.pantallas.juego import MenuPregunta, PantallaJuego
from app.seguimiento.grabadora import leer_sesion
from tests.test_actividades_comun import Jugador
from tests.test_motor_comun import registros

from .conftest import RAIZ
from .test_reproductor_comun import Robot, crear_app, sin_navegador  # noqa: F401 - fixture

pytestmark = pytest.mark.lento

DOCUMENTO = RAIZ / "docs" / "actividades.md"
BLOQUE = re.compile(r"<!-- entorno: ([a-z0-9-]+) -->\n```json\n(.*?)\n```", re.DOTALL)
DT = 0.05
CENTRO = "centro-de-dos-plantas"
VIVIENDA = "vivienda-de-ejemplo"
BARRIO = "barrio-de-ejemplo"
PROBADOS: set[str] = set()


# ── Las actividades del documento ────────────────────────────────────────────


@functools.cache
def _ejemplos() -> tuple[tuple[str, str], ...]:
	texto = DOCUMENTO.read_text(encoding="utf-8")
	return tuple((nombre, cuerpo) for nombre, cuerpo in BLOQUE.findall(texto))


def ejemplo(ident: str) -> tuple[str, dict[str, Any]]:
	"""(entorno, datos) del ejemplo JSON del documento con ese id; los datos son una copia nueva."""
	for nombre, cuerpo in _ejemplos():
		datos = json.loads(cuerpo)
		if datos["id"] == ident:
			return nombre, datos
	raise AssertionError(f"docs/actividades.md no tiene el ejemplo {ident}")


def preparar(carpeta: Path, entorno: str, datos: dict[str, Any], sin_muebles: bool = False) -> Path:
	"""Guarda en ``carpeta`` una copia del paquete de ejemplo con solo esa actividad. Devuelve su ruta.

	``sin_muebles`` usa el entorno de ejemplo sin amueblar (como las pruebas de
	las actividades): para recorrer paredes, los muebles pegados a ellas estorban.
	"""
	original = cargar_paquete(RAIZ / "data" / "ejemplos" / f"{entorno}.elab")
	modelo = ejemplos.EJEMPLOS[entorno]() if sin_muebles else original.entorno
	carpeta.mkdir(parents=True, exist_ok=True)
	ruta = carpeta / f"{datos['id']}.elab"
	guardar_paquete(ruta, modelo, [datos], dict(original.recursos))
	return ruta


# ── El alumno automático, jugando en el reproductor ──────────────────────────


class JugadorReal(Jugador):
	"""El ``Jugador`` de las pruebas de actividades, pero cada orden va por la aplicación.

	``pulsar`` inyecta la acción en la ``Aplicacion`` (la recibe la pantalla
	de juego, que se la da a la sesión) y ``tic`` deja pasar fotogramas de la
	aplicación. Los eventos se recogen al entregarlos la partida a la
	aplicación, así que son los mismos que se presentan al alumno.
	"""

	def __init__(self, app: Aplicacion) -> None:
		assert isinstance(app.cima, PantallaJuego), f"no se ha empezado a jugar: arriba está {type(app.cima).__name__}"
		self.app = app
		self.partida: PantallaJuego = app.partida
		self.entorno = self.partida.entorno
		self.manos = Robot(app)
		self.eventos: list[Any] = []
		entregar = app.entregar

		def apuntar(eventos: list[Any], sesion: Any) -> None:
			self.eventos.extend(eventos)
			entregar(eventos, sesion)

		app.entregar = apuntar  # type: ignore[method-assign]
		self.tic(3)

	@property
	def sesion(self) -> Any:  # type: ignore[override]
		return self.partida.sesion

	@property
	def actividad(self) -> Any:  # type: ignore[override]
		return self.partida.actividad

	def tic(self, n: int = 1, dt: float = DT) -> list[Any]:
		antes = len(self.eventos)
		self.app.avanzar(n, dt)
		return self.eventos[antes:]

	def pulsar(self, accion: str, n: int = 2) -> list[Any]:
		antes = len(self.eventos)
		self.app.inyectar(accion)
		self.app.avanzar(n, DT)
		return self.eventos[antes:]

	def confirmar(self) -> list[Any]:
		"""La acción «confirmar» del reproductor (tecla M), no una llamada directa a la actividad."""
		return self.pulsar("confirmar", 2)

	def esperar_que(self, condicion: Any, segundos: float = 10.0) -> bool:
		"""Deja pasar fotogramas hasta que se cumpla la condición (o pase el plazo, en tiempo de juego)."""
		for _i in range(max(1, round(segundos / DT))):
			if condicion():
				return True
			self.tic(1)
		return bool(condicion())

	# ── Moverse ──

	def ir_a(self, x: float, y: float, abrir: bool = True) -> list[Any]:
		"""Como ``Robot.ir_a``, pero si algo le para solo usa «interactuar» cuando es una puerta.

		El robot del motor usa lo que tenga delante al chocar; en un examen o al
		localizar, usar un mueble es confirmar, y el robot confirmaría sin querer.
		"""
		jugador = self.sesion.jugador
		ajustes = self.sesion.ajustes
		antes = len(self.eventos)
		for _intento in range(3):
			distancia = math.hypot(x - jugador.x, y - jugador.y)
			if distancia < 0.05 or self.sesion.terminado:
				break
			self.girar_a(geo.rumbo_entre((jugador.x, jugador.y), (x, y)))
			pasos = max(1, math.ceil(distancia / 0.7))
			previo = ajustes.paso_m
			ajustes.paso_m = distancia / pasos
			bloqueado = False
			for _i in range(pasos):
				desde = (jugador.planta, jugador.x, jugador.y)
				self.pulsar("avanzar", 1)
				if jugador.modo != "andando" or jugador.planta != desde[0] or self.sesion.terminado:
					break
				if math.hypot(jugador.x - desde[1], jugador.y - desde[2]) < ajustes.paso_m * 0.5:
					bloqueado = True
					break
			ajustes.paso_m = previo
			if jugador.modo != "andando" or not bloqueado or not abrir:
				break
			a_mano = self.sesion.interactuables_cerca()
			if not a_mano or a_mano[0]["clase"] not in ("abertura", "parada", "pulsador"):
				break
			self.pulsar("interactuar", 1)
		return self.eventos[antes:]

	def a(self, destino: Any, cerca: float = 0.5, evitar: Any = ()) -> bool:
		"""Va a ``(planta, x, y)`` de cualquier planta, por el camino del navegador."""
		terna = destino.terna if hasattr(destino, "terna") else destino
		return self.recorrer(terna, cerca=cerca, evitar=evitar)

	def lugar(self, valor: Any) -> Any:
		lugar = self.actividad.lugar(valor)
		assert lugar is not None, valor
		return lugar

	def salir_por_abertura(self, abertura_id: str) -> None:
		"""Sale del edificio por una abertura de cualquier planta: llega por dentro, se pone de cara y cruza."""
		mundo = self.sesion.mundo
		info = mundo.abertura(abertura_id)
		assert info is not None, abertura_id
		dentro = punto_interior_de_abertura(mundo, info, 0.9)
		assert dentro is not None
		(x, y), _rumbo = dentro
		antes = len(self.eventos)
		self.a((info.planta_id, x, y), cerca=0.3)
		jugador = self.sesion.jugador
		self.girar_a(geo.rumbo_entre((jugador.x, jugador.y), info.centro))
		previo = self.sesion.ajustes.paso_m
		self.sesion.ajustes.paso_m = 0.5
		for _paso in range(14):
			if self.sesion.terminado or registros(self.eventos[antes:], "salida"):
				break
			posicion = (jugador.x, jugador.y)
			self.pulsar("avanzar", 1)
			if math.hypot(jugador.x - posicion[0], jugador.y - posicion[1]) < 0.1:
				self.pulsar("interactuar", 1)
		self.sesion.ajustes.paso_m = previo
		self.tic(3)

	def salir_por_la_mas_cercana(self) -> None:
		jugador = self.sesion.jugador
		salidas = salidas_ordenadas(self.sesion.nav, (jugador.planta, jugador.x, jugador.y))
		assert salidas, "no hay salidas alcanzables"
		self.salir_por_abertura(salidas[0][0])


# ── Arranque y final comunes ─────────────────────────────────────────────────


@pytest.fixture
def lanzar(data_temporal: Path, sin_navegador: list[str]) -> Any:
	"""Devuelve una función que abre el reproductor real con una actividad del documento y da el ``JugadorReal``."""
	abiertas: list[Aplicacion] = []

	def hacer(
		ident: str, cambios: dict[str, Any] | None = None, sin_muebles: bool = False, sin_trafico: bool = False, antes: Any = None
	) -> JugadorReal:
		entorno, datos = ejemplo(ident)
		datos.update(cambios or {})
		ruta = preparar(data_temporal / "entornos", entorno, datos, sin_muebles)
		app = crear_app("--alumno", "Luna")
		abiertas.append(app)
		if sin_trafico:
			ajustes_del_alumno = app.ajustes_juego

			def sin_coches() -> Any:
				ajustes = ajustes_del_alumno()
				ajustes.trafico = False
				return ajustes

			app.ajustes_juego = sin_coches  # type: ignore[method-assign]
		if callable(antes):
			antes(app)
		paquete = entornos.abrir(ruta)
		assert app.empezar_partida(paquete, paquete.actividad(datos["id"])), robot_dijo(app)
		jugador = JugadorReal(app)
		assert type(jugador.actividad).__module__.startswith("app.actividades"), "es la actividad real"
		assert jugador.actividad.tipo == datos["tipo"]
		PROBADOS.add(datos["tipo"])
		return jugador

	yield hacer
	for app in abiertas:
		app.cerrar_todo()


def robot_dijo(app: Aplicacion) -> str:
	return " | ".join(texto for texto, _canal, _interrumpir in app.voz.registro)


def menu_de_fin(app: Aplicacion) -> Menu | None:
	return next((p for p in app.pila if isinstance(p, Menu) and p.titulo.startswith("Fin de")), None)


def acabar(jugador: JugadorReal, completada: bool = True) -> dict[str, Any]:
	"""Comprueba el final (``EvFin``, pantalla de fin) y la sesión grabada. Devuelve el resultado."""
	app = jugador.app
	jugador.esperar_que(lambda: jugador.fin is not None and jugador.partida.terminado, 5.0)
	resultado = jugador.fin
	assert resultado is not None, f"la actividad no ha terminado: {jugador.actividad.estado()}"
	assert jugador.partida.terminado
	if completada:
		assert resultado["completada"] is True, (resultado.get("motivo"), jugador.actividad.estado())
	assert resultado["actividad"]["tipo"] == jugador.actividad.tipo
	assert menu_de_fin(app) is not None, f"no se ha abierto la pantalla de fin: {[type(p).__name__ for p in app.pila]}"
	# El nivel y la semilla viajan en el resultado (a la grabación y a la sala).
	for clave in ("nivel", "nivel_siguiente", "nivel_superado", "semilla", "semilla_actividad"):
		assert clave in resultado, clave
	assert resultado["semilla"] == jugador.partida.semilla
	# Si se ha abierto solo el cuestionario, se deja sin contestar.
	while not isinstance(app.cima, Menu) or not app.cima.titulo.startswith("Fin de"):
		assert isinstance(app.cima, Menu) and app.cima.titulo.startswith("Pregunta"), app.cima
		if not app.cima.elegir("Dejar las preguntas"):
			app.cima.elegir("Prefiero no contestar")
		app.inyectar("menu_aceptar")
		app.avanzar(1)
	assert app.fallos == 0
	sesiones_antes = set(_carpeta_sesiones(app).glob("*.json.gz"))
	jugador.manos.elegir("Volver al menú principal")
	assert app.partida is None
	nuevas = set(_carpeta_sesiones(app).glob("*.json.gz")) - sesiones_antes
	(fichero,) = nuevas
	grabada = leer_sesion(fichero)
	guardado = grabada["resumen"]["resultado"]
	assert guardado["nivel"] == resultado["nivel"] and guardado["nivel_siguiente"] == resultado["nivel_siguiente"]
	assert grabada["manifiesto"]["actividad"]["tipo"] == resultado["actividad"]["tipo"]
	assert grabada["manifiesto"]["completada"] is bool(resultado["completada"])
	return resultado


def _carpeta_sesiones(_app: Aplicacion) -> Path:
	"""Donde la grabadora deja las sesiones: ``sessions`` de la carpeta data de la prueba (``data_temporal``)."""
	return Path(os.environ["APP_DATA_DIR"]) / "sessions"


# ── Juegos ───────────────────────────────────────────────────────────────────


def test_busqueda_con_premios_en_muebles_y_cuestionario_final(lanzar):
	jugador = lanzar("busqueda-del-tesoro")
	assert "Tiko ha escondido cinco tesoros" in jugador.dicho()
	for premio in jugador.actividad.datos["premios"]:
		if jugador.sesion.terminado:
			break
		if premio.get("dentro_de"):
			jugador.usar(premio["dentro_de"])
		else:
			jugador.a((premio["planta"], premio["x"], premio["y"]), cerca=0.3)
	jugador.esperar_que(lambda: jugador.partida.terminado, 3.0)
	app = jugador.app
	# La actividad pide el cuestionario: se abre solo tras el resultado, sin cortarlo.
	assert isinstance(app.cima, Menu) and app.cima.titulo.startswith("Pregunta 1 de 3."), app.cima
	jugador.manos.elegir("Bastante")
	jugador.manos.elegir("Prefiero no contestar")
	jugador.manos.elegir("Mucho")
	assert "Tus respuestas se han guardado" in robot_dijo(app)
	assert registros(jugador.eventos, "valoracion")[-1]["esfuerzo"] == 4
	assert jugador.partida.resultado["valoracion"] == {"esfuerzo": 4, "confianza": None, "disfrute": 5}
	resultado = acabar(jugador)
	assert resultado["objetivos_hechos"] == 5
	# Las recompensas las registra la actividad una sola vez.
	assert len(registros(jugador.eventos, "recompensa")) == len(resultado["recompensas"])


def test_pistas_encadenadas_con_el_nivel_guardado_del_alumno(lanzar):
	pedidos: list[tuple[str, str]] = []
	anotados: list[tuple[str, str, int]] = []

	def con_niveles(app: Aplicacion) -> None:
		# El contrato con la aplicación: nivel_actividad al empezar y anotar_nivel al terminar.
		app.nivel_actividad = lambda entorno, actividad: pedidos.append((entorno, actividad)) or 2  # type: ignore[attr-defined]
		app.anotar_nivel = lambda entorno, actividad, nivel: anotados.append((entorno, actividad, nivel))  # type: ignore[attr-defined]

	jugador = lanzar("pistas-por-la-casa", antes=con_niveles)
	assert pedidos == [(jugador.entorno.id, "pistas-por-la-casa")]
	assert jugador.partida.nivel_pedido == 2 and jugador.actividad.nivel == 2
	for premio in jugador.actividad.datos["premios"]:
		if jugador.sesion.terminado:
			break
		if premio.get("dentro_de"):
			jugador.usar(premio["dentro_de"])
		else:
			jugador.a((premio["planta"], premio["x"], premio["y"]), cerca=0.3)
		jugador.tic(10)
	resultado = acabar(jugador)
	assert resultado["nivel"] == 2
	assert anotados == [(jugador.entorno.id, "pistas-por-la-casa", resultado["nivel_siguiente"])]


def test_sacar_los_tesoros_por_las_dos_plantas(lanzar):
	_entorno, datos = ejemplo("sacar-los-tesoros")
	# Dos de los cinco: uno en cada planta (el de arriba obliga a bajar por la escalera o el ascensor).
	premios = [p for p in datos["premios"] if p["id"] in ("premio-5", "premio-1")]
	jugador = lanzar("sacar-los-tesoros", {"premios": premios, "cuestionario": False})
	for premio in premios:
		if jugador.sesion.terminado:
			break
		assert jugador.a((premio["planta"], premio["x"], premio["y"]), cerca=0.3), premio["id"]
		jugador.tic(3)
		assert jugador.actividad.estado()["fase"] == "sacar", jugador.actividad.estado()
		jugador.salir_por_la_mas_cercana()
	resultado = acabar(jugador)
	assert len(registros(jugador.eventos, "salida_puntuada")) == 2
	assert resultado["puntuaciones"]["medida"] == "salida_mas_corta"


def test_recadero_hasta_la_parada(lanzar):
	jugador = lanzar("recado-a-la-parada", sin_trafico=True)
	for paso in jugador.actividad._pasos:
		for _intento in range(4):
			if paso.hecho or jugador.sesion.terminado:
				break
			jugador.a(paso.lugar.terna, cerca=0.8)
			jugador.tic(3)
		assert paso.hecho, f"no ha llegado a {paso.lugar.nombre}"
	acabar(jugador)


def test_escondite(lanzar):
	jugador = lanzar("el-escondite")
	for _ronda in range(12):
		if jugador.sesion.terminado:
			break
		escondite = jugador.actividad._lugar_actual()
		assert escondite is not None
		jugador.a(escondite.terna, cerca=0.4)
		jugador.tic(3)
	acabar(jugador)


def test_sigue_al_guia_hasta_la_biblioteca(lanzar):
	jugador = lanzar("sigue-al-guia")
	for _vuelta in range(150):
		if jugador.sesion.terminado:
			break
		guia = jugador.actividad._lugar_actual()
		if guia is not None:
			jugador.recorrer(guia.terna, cerca=1.0, intentos=1)
		jugador.tic(10)
	acabar(jugador)


def test_explorador(lanzar):
	jugador = lanzar("explorador")
	for planta in jugador.entorno.plantas:
		for espacio in planta.espacios:
			if jugador.sesion.terminado:
				break
			if espacio.macizo:
				continue
			jugador.a(jugador.lugar(espacio.id), cerca=0.4)
			jugador.tic(2)
	resultado = acabar(jugador)
	assert resultado["exploracion"] == 1.0


def test_cruce_dos_veces(lanzar):
	jugador = lanzar("practica-de-cruce", {"trafico": False}, sin_trafico=True)
	assert "no dice si un cruce real es seguro" in jugador.dicho()
	assert jugador.a(("pla-1", -8.0, 4.4), cerca=0.4)
	jugador.ir_a(-8.0, -4.4)
	jugador.tic(3)
	jugador.ir_a(-8.0, 4.4)
	jugador.tic(3)
	acabar(jugador)
	assert len(registros(jugador.eventos, "cruce_puntuado")) == 2


# ── Prácticas ────────────────────────────────────────────────────────────────


def test_exploracion_se_termina_desde_la_pausa_y_no_es_abandonarla(lanzar):
	jugador = lanzar("exploracion-libre")
	jugador.a(jugador.lugar("esp-5"), cerca=0.5)
	manos = jugador.manos
	manos.tecla(pygame.K_ESCAPE)
	assert "Terminar la exploración" in manos.opciones() and "Abandonar la actividad" not in manos.opciones()
	manos.elegir("Terminar la exploración")
	manos.elegir("Sí, terminar", 3)
	resultado = acabar(jugador)
	assert resultado["motivo"] == "terminada" and not resultado.get("abandonada")


def test_visita_guiada_con_textos(lanzar):
	jugador = lanzar("visita-con-textos")
	for objetivo in jugador.actividad.datos["objetivos"]:
		jugador.a(jugador.lugar(objetivo["destino"]), cerca=0.4)
		jugador.tic(20)
	acabar(jugador)
	assert "El frigorífico zumba en la esquina." in jugador.dicho()


def test_ruta_al_aula_de_informatica_con_cambio_de_planta(lanzar):
	jugador = lanzar("ruta-a-informatica")
	assert jugador.actividad.nivel == 0
	destino = jugador.lugar(jugador.actividad.datos["destino"])
	inicio = jugador.sesion.jugador.planta
	assert destino.planta != inicio, "la ruta cambia de planta"
	jugador.a(destino, cerca=0.5)
	resultado = acabar(jugador)
	assert resultado["nivel"] == 0


def test_ruta_inversa(lanzar):
	jugador = lanzar("ida-y-vuelta-a-la-cocina")
	jugador.a(jugador.lugar("esp-5"), cerca=0.5)
	assert jugador.esperar_que(lambda: jugador.actividad.estado()["hechos"] == 1, 5.0)
	jugador.tic(40)
	inicio = jugador.entorno.inicio
	jugador.a((inicio.planta, inicio.x, inicio.y), cerca=0.4)
	acabar(jugador)


def test_volver_al_origen(lanzar):
	jugador = lanzar("vuelta-a-la-entrada")
	for objetivo in jugador.actividad.datos["objetivos"]:
		jugador.a(jugador.lugar(objetivo["destino"]), cerca=0.4)
		jugador.tic(20)
	inicio = jugador.entorno.inicio
	jugador.a((inicio.planta, inicio.x, inicio.y), cerca=0.4)
	acabar(jugador)


def test_ruta_alternativa_sin_el_ascensor(lanzar):
	jugador = lanzar("ascensor-averiado")
	cortes = jugador.actividad.datos["cortes"]
	jugador.a(jugador.lugar(jugador.actividad.datos["destino"]), cerca=0.5, evitar=cortes)
	resultado = acabar(jugador)
	assert resultado["paso_cortado_usado"] is False


def test_localizar_con_la_tecla_de_confirmar(lanzar):
	jugador = lanzar("encuentra-el-centro-civico", sin_trafico=True)
	# Confirmar donde no es: se dice y cuenta como tropiezo (es una práctica).
	antes = len(jugador.eventos)
	jugador.confirmar()
	jugador.tic(2)
	assert "Todavía no has llegado." in jugador.dicho(antes)
	jugador.a(jugador.lugar("esp-30"), cerca=0.5)
	# (Si un mueble le ha parado al llegar, el robot ya ha usado «interactuar», que también confirma.)
	if not jugador.sesion.terminado:
		jugador.manos.tecla(pygame.K_m, unicode="m")
		jugador.tic(2)
	resultado = acabar(jugador)
	assert resultado["confirmaciones_fallidas"] == 1


def test_perimetro_del_salon(lanzar):
	jugador = lanzar("conoce-el-salon", sin_muebles=True)
	for x, y in ((0.5, 3.5), (0.5, 0.5), (4.0, 0.5), (4.0, 3.5), (0.5, 3.5)):
		jugador.ir(("pla-1", x, y), cerca=0.2)
	jugador.tic(40)
	assert jugador.actividad.estado()["fase"] == "interior"
	for x, y in ((1.5, 1.5), (3.0, 1.5), (3.0, 2.5), (1.5, 2.5)):
		if jugador.sesion.terminado:
			break
		jugador.ir(("pla-1", x, y), cerca=0.2)
	acabar(jugador)


def test_linea_guia_del_pasillo(lanzar):
	jugador = lanzar("pared-del-pasillo", sin_muebles=True)
	jugador.ir(("pla-1", 4.0, 4.8), cerca=0.2)
	jugador.ir(("pla-1", 7.6, 4.8), cerca=0.2)
	acabar(jugador)


# ── Exámenes ─────────────────────────────────────────────────────────────────


def test_examen_de_rutas_con_la_tecla_de_confirmar(lanzar):
	jugador = lanzar("examen-de-rutas")
	actividad = jugador.actividad
	assert actividad.semilla == 2026, "un examen usa su semilla, no la de la partida"
	jugador.tic(5)
	assert actividad.estado()["total"] == 5
	# La primera ruta se anda (por las dos plantas si hace falta) y se confirma con la tecla propia.
	destino = actividad._prueba()["destino"]
	jugador.a(destino, cerca=0.5)
	antes = len(jugador.eventos)
	jugador.confirmar()
	assert "Anotado." in jugador.dicho(antes)
	(primera,) = registros(jugador.eventos, "examen")
	assert primera["acierto"] is True and primera["motivo"] == "confirmada", primera
	# Las demás se confirman sin moverse: la regla de parada corta el examen.
	for _prueba in range(5):
		if jugador.sesion.terminado:
			break
		jugador.confirmar()
		jugador.tic(3)
	resultado = acabar(jugador)
	assert resultado["examen"]["pruebas_hechas"] >= 3


def test_examen_de_salida(lanzar):
	jugador = lanzar("examen-de-salida")
	jugador.tic(5)
	for _prueba in range(8):
		if jugador.sesion.terminado:
			break
		hechas = jugador.actividad.estado()["hechos"]
		salidas = jugador.actividad._salidas
		assert salidas
		jugador.salir_por_abertura(salidas[0][0])
		jugador.esperar_que(lambda hechas=hechas: jugador.sesion.terminado or jugador.actividad.estado()["hechos"] > hechas, 3.0)
	resultado = acabar(jugador)
	assert resultado["examen"]["pruebas_hechas"] == 5
	assert sum(1 for p in resultado["examen"]["pruebas"] if p["motivo"] == "salida") == 5


def test_examen_de_senalar(lanzar):
	jugador = lanzar("examen-de-senalar")
	jugador.tic(5)
	for _prueba in range(8):
		if jugador.sesion.terminado:
			break
		destino = jugador.actividad._prueba()["destino"]
		posicion = jugador.sesion.jugador
		jugador.girar_a(geo.rumbo_entre(posicion.punto, destino.punto))
		jugador.confirmar()
		jugador.tic(3)
	resultado = acabar(jugador)
	assert resultado["examen"]["aciertos"] == 5


def _contestar_con_el_menu(jugador: JugadorReal, correcta: Any) -> None:
	"""Espera el menú de respuestas de la pregunta en curso y elige la opción que dice ``correcta(pregunta)``."""
	app = jugador.app
	assert jugador.esperar_que(lambda: isinstance(app.cima, MenuPregunta) or jugador.sesion.terminado, 2.0), app.cima
	if jugador.sesion.terminado:
		return
	pregunta = jugador.actividad.estado()["pregunta"]
	jugador.manos.elegir(correcta(pregunta))
	jugador.tic(3)


def test_examen_de_distancias_con_el_menu_de_respuestas(lanzar):
	jugador = lanzar("examen-de-distancias")
	app = jugador.app
	assert jugador.esperar_que(lambda: isinstance(app.cima, MenuPregunta), 2.0)
	menu = app.cima
	assert menu.titulo.startswith("Estás en") and "¿qué queda más cerca" in menu.titulo
	assert "Cambia de opción" not in menu.titulo, "el menú lee la pregunta sola"
	assert [o.texto for o in menu.opciones[:2]] == jugador.actividad.estado()["pregunta"]["opciones"]
	# El menú no pausa: el tiempo de la prueba sigue corriendo.
	t = jugador.sesion.t
	jugador.tic(10)
	assert not jugador.sesion.pausado and jugador.sesion.t > t
	# Consultar la pregunta no gasta usos de la ayuda «objetivo».
	assert jugador.sesion.percepcion.usos.get("objetivo", 0) == 0
	# Atrás vuelve al juego sin contestar y sin «seguimos»; confirmar vuelve a abrir las respuestas.
	marca = len(app.voz.registro)
	jugador.manos.atras()
	dicho_al_volver = [texto for texto, _canal, _cortar in app.voz.registro[marca:]]
	assert app.cima is jugador.partida and "Continúa." not in dicho_al_volver, dicho_al_volver
	jugador.confirmar()
	assert isinstance(app.cima, MenuPregunta)
	assert registros(jugador.eventos, "examen") == []
	contestadas = 0
	while not jugador.sesion.terminado and contestadas < 10:
		_contestar_con_el_menu(jugador, lambda pregunta: pregunta["opciones"][0])
		contestadas += 1
	resultado = acabar(jugador)
	assert resultado["examen"]["pruebas_hechas"] == contestadas == 6
	assert jugador.sesion.percepcion.usos.get("objetivo", 0) == 0


def test_examen_de_reconstruccion_con_el_menu_de_respuestas(lanzar):
	jugador = lanzar("examen-de-reconstruccion")
	_contestar_con_el_menu(jugador, lambda pregunta: "Cocina")
	resultado = acabar(jugador)
	assert resultado["examen"]["aciertos"] == 1


# ── Órdenes del profesional ──────────────────────────────────────────────────


def test_las_ordenes_del_profesional_se_presentan(lanzar):
	jugador = lanzar("ruta-a-informatica")
	partida = jugador.partida
	antes = len(jugador.eventos)
	partida.orden_profesor("pista", {"texto": "Busca la escalera al fondo del pasillo", "baliza_s": 5})
	partida.orden_profesor("premio", {"nombre": "una medalla"})
	jugador.tic(3)
	voces = [(e.texto, e.canal) for e in jugador.eventos[antes:] if isinstance(e, ev.EvVoz)]
	assert ("Busca la escalera al fondo del pasillo", "profesional") in voces
	assert any("una medalla" in texto and canal == "profesional" for texto, canal in voces)
	dicho = robot_dijo(jugador.app)
	assert "Busca la escalera al fondo del pasillo" in dicho
	assert jugador.actividad.estado()["nivel"] == 0
	jugador.partida.abandonar()
	assert jugador.app.partida is None or jugador.partida.terminado
	assert jugador.fin["intervenciones_profesional"] == {"pista": 1, "premio": 1}


# ── Todos los tipos ──────────────────────────────────────────────────────────


def test_zz_se_han_jugado_los_22_tipos():
	"""Se ejecuta la última (por su nombre): cada tipo de ``TIPOS`` tiene arriba su partida entera."""
	if len(PROBADOS) < 3:
		pytest.skip("solo tiene sentido al ejecutar el fichero entero")
	assert set(TIPOS) <= PROBADOS, sorted(set(TIPOS) - PROBADOS)
	assert len(TIPOS) == 22
