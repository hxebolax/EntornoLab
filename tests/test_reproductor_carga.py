"""Pantalla de carga de los entornos grandes: el bucle no se para, se dice cómo va y Escape cancela.

Para no tener que construir un barrio de miles de espacios en cada prueba, el
umbral de «entorno grande» se baja para que la vivienda de ejemplo ya cuente
como grande, y algunas pruebas sustituyen la preparación por una que espera a
que se la deje seguir (así se puede comprobar qué pasa MIENTRAS carga).
"""

# ruff: noqa: F811 - los parámetros de las pruebas se llaman como las fixtures importadas
from __future__ import annotations

import threading
import time

import pytest

from app.dominio.formato import cargar_paquete
from app.reproductor import carga
from app.reproductor.pantallas.juego import PantallaJuego

from .test_reproductor_comun import VIVIENDA, Robot, app, robot, sin_navegador  # noqa: F401 - fixtures

# Un fotograma del bucle mientras se carga no debe tardar más que esto (el alumno no nota un parón de una décima).
LIMITE_FOTOGRAMA = 0.1


@pytest.fixture
def grande(monkeypatch: pytest.MonkeyPatch) -> None:
	"""Cualquier entorno cuenta como grande: se carga siempre con la pantalla de carga."""
	monkeypatch.setattr(carga, "UMBRAL_ELEMENTOS", 1)


def _esperar_carga(robot: Robot, plazo: float = 60.0) -> list[float]:
	"""Avanza fotogramas mientras haya una pantalla de carga arriba. Devuelve lo que tardó cada fotograma."""
	tiempos: list[float] = []
	limite = time.monotonic() + plazo
	while isinstance(robot.cima, carga.PantallaCarga):
		assert time.monotonic() < limite, "la carga no ha terminado a tiempo"
		inicio = time.perf_counter()
		robot.esperar(1)
		tiempos.append(time.perf_counter() - inicio)
		time.sleep(0.002)
	return tiempos


def test_un_entorno_grande_se_carga_con_aviso_y_sin_parar_el_bucle(robot: Robot, grande):
	paquete = cargar_paquete(VIVIENDA)
	marca = robot.marca()
	assert robot.app.empezar_partida(paquete, None)
	assert isinstance(robot.cima, carga.PantallaCarga), "la partida espera a que acabe la carga"
	assert robot.partida is None
	dicho = robot.dicho(marca)
	assert "Cargando el entorno Vivienda de ejemplo: 6 espacios" in dicho
	assert "Escape cancela" in dicho
	assert robot.app.voz.registro[marca][1] == "aviso"
	tiempos = _esperar_carga(robot)
	assert max(tiempos, default=0.0) < LIMITE_FOTOGRAMA
	assert isinstance(robot.cima, PantallaJuego)
	assert robot.partida is robot.cima
	assert robot.pantallas() == ["Menu", "PantallaJuego"]
	# La sesión ya trae calculado lo que la primera consulta calcularía de golpe.
	sesion = robot.sesion
	assert sesion.nav._grafo is not None
	jugador = sesion.jugador
	assert sesion.nav.componente((jugador.planta, jugador.x, jugador.y)) is not None
	# Y se juega con normalidad.
	robot.accion("avanzar", 3)
	assert sesion.t > 0.0


def _preparacion_que_espera(monkeypatch: pytest.MonkeyPatch, fases: list[str]) -> threading.Event:
	"""Sustituye la preparación por una que avisa de esas fases y espera a que se la suelte (o se la cancele)."""
	soltar = threading.Event()
	original = PantallaJuego.preparar

	def preparar(self: PantallaJuego, pedido, progreso=None):
		if progreso is not None:
			for fase in fases:
				progreso(fase, 1, 4)
				time.sleep(0.05)
			while not soltar.wait(0.01):
				progreso(fases[-1] if fases else "caminos", 2, 4)
		return original(self, pedido, progreso)

	monkeypatch.setattr(PantallaJuego, "preparar", preparar)
	return soltar


def test_mientras_carga_se_dicen_las_fases_y_el_estado(robot: Robot, grande, monkeypatch):
	soltar = _preparacion_que_espera(monkeypatch, ["caminos", "sonido"])
	paquete = cargar_paquete(VIVIENDA)
	assert robot.app.empezar_partida(paquete, None)
	pantalla = robot.cima
	assert isinstance(pantalla, carga.PantallaCarga)
	marca = robot.marca()
	limite = time.monotonic() + 10
	while "Preparando el sonido" not in robot.dicho(marca) and time.monotonic() < limite:
		robot.esperar(1)
		time.sleep(0.01)
	dicho = robot.dicho(marca)
	assert "Preparando los caminos…" in dicho
	assert "Preparando el sonido…" in dicho
	# Los avisos de fase no interrumpen: son progreso, no respuesta a una orden.
	assert all(not interrumpir for texto, _canal, interrumpir in robot.app.voz.registro[marca:] if texto.startswith("Preparando"))
	# Intro (o la ayuda) dice cómo va, con lo que lleva.
	marca = robot.marca()
	robot.accion("menu_aceptar")
	assert "Sigue cargando el entorno Vivienda de ejemplo: preparando el sonido. Lleva" in robot.dicho(marca)
	assert "Escape cancela." in robot.dicho(marca)
	assert "Cargando Vivienda de ejemplo" in pantalla.titulo_visible()
	soltar.set()
	_esperar_carga(robot)
	assert isinstance(robot.cima, PantallaJuego)


def test_escape_cancela_la_carga_y_vuelve_al_menu(robot: Robot, grande, monkeypatch):
	_preparacion_que_espera(monkeypatch, ["plantas"])
	paquete = cargar_paquete(VIVIENDA)
	assert robot.app.empezar_partida(paquete, None)
	pantalla = robot.cima
	assert isinstance(pantalla, carga.PantallaCarga)
	robot.esperar(3)
	marca = robot.marca()
	robot.accion("menu_atras")
	assert "Carga cancelada." in robot.dicho(marca)
	assert robot.pantallas() == ["Menu"]
	assert robot.partida is None
	# El hilo se entera en su siguiente aviso de progreso y acaba sin dejar nada.
	assert pantalla.esperar(5.0)
	robot.esperar(3)
	assert robot.partida is None


def test_si_la_preparacion_falla_se_dice_y_se_vuelve_al_menu(robot: Robot, grande, monkeypatch):
	def preparar(self, pedido, progreso=None):
		raise ValueError("datos rotos")

	monkeypatch.setattr(PantallaJuego, "preparar", preparar)
	paquete = cargar_paquete(VIVIENDA)
	assert robot.app.empezar_partida(paquete, None)
	marca = robot.marca()
	_esperar_carga(robot)
	assert "No se ha podido preparar el entorno Vivienda de ejemplo: datos rotos" in robot.dicho(marca)
	assert robot.pantallas() == ["Menu"]
	assert robot.partida is None


def test_reiniciar_un_entorno_grande_tambien_carga_con_aviso(robot: Robot, grande):
	paquete = cargar_paquete(VIVIENDA)
	robot.app.empezar_partida(paquete, None)
	_esperar_carga(robot)
	partida = robot.partida
	anterior = partida.sesion
	partida.reiniciar()
	assert isinstance(robot.cima, carga.PantallaCarga)
	assert robot.pantallas() == ["Menu", "PantallaJuego", "PantallaCarga"]
	_esperar_carga(robot)
	assert robot.cima is partida
	assert partida.sesion is not anterior


def test_un_entorno_pequeno_se_prepara_al_momento(robot: Robot):
	paquete = cargar_paquete(VIVIENDA)
	assert not carga.es_grande(paquete.entorno)
	assert robot.app.empezar_partida(paquete, None)
	assert isinstance(robot.cima, PantallaJuego)


def test_cifras_con_separador_de_miles():
	assert carga.miles(3000) == "3.000"
	assert carga.miles(350) == "350"
	assert carga.contar(cargar_paquete(VIVIENDA).entorno)[0] == 6
