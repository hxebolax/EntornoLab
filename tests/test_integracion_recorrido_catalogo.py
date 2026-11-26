"""«Colocar un objeto aquí» eligiendo el objeto en el catálogo del propio reproductor, de extremo a extremo.

reproductor (menú de edición → catálogo) → sala → ``app.ui.recorrido`` →
objeto colocado en el entorno abierto en el Estudio → respuesta → el
reproductor recarga el paquete.

El reproductor es la ``Aplicacion`` de verdad en modo de pruebas, en este
mismo proceso (la versión con un proceso hijo está en
``test_integracion_proceso_real.py``); el catálogo es el instalado, con sus
más de dos mil objetos: el menú tiene que poder recorrerse a oído.
"""

from __future__ import annotations

from typing import Any

import pygame
import pytest

from app.dominio.formato import cargar_paquete
from app.reproductor import entornos
from app.reproductor.menus import EntradaTexto, Menu
from app.reproductor.pantallas import recorrido as pantalla_recorrido
from app.ui.contexto import ContextoEstudio
from app.ui.recorrido import SesionRecorrido
from app.ui.seguimiento.sala import GestorSala
from tests._supervision_util import esperar
from tests.test_reproductor_comun import VIVIENDA, Robot, crear_app, sin_navegador  # noqa: F401

# Cada prueba arranca un reproductor y lo conecta a una sala de verdad.
pytestmark = pytest.mark.lento


@pytest.fixture(scope="module")
def catalogo():
	return entornos.cargar_catalogo()


@pytest.fixture
def montaje(catalogo, data_temporal, tmp_path, sin_navegador, monkeypatch):  # noqa: F811 - fixture importada
	"""Estudio con la vivienda abierta, recorrido iniciado y el reproductor real ya conectado."""
	from app.ui import recorrido as recorrido_ui

	# El reproductor vive en este proceso y no cierra solo: no hace falta esperarle al detener.
	monkeypatch.setattr(recorrido_ui, "ESPERA_TERMINAR", 0.0)
	creadas: list[Any] = []

	class ProcesoEnCasa:
		terminado = False
		pid = None

		def vivo(self) -> bool:
			return not self.terminado

		def terminar(self, espera: float = 0.0) -> int:
			self.terminado = True
			return 0

	def lanzador(argumentos: list[str]) -> ProcesoEnCasa:
		creadas.append(crear_app(*argumentos, "--alumno", "Profe"))
		return ProcesoEnCasa()

	contexto = ContextoEstudio(catalogo=catalogo, lanzador=lanzador)
	contexto.abrir_documento(cargar_paquete(VIVIENDA).entorno)
	ruta = data_temporal / "entornos" / "vivienda.elab"
	assert contexto.guardar(ruta)
	sesion = SesionRecorrido(contexto, GestorSala(None, carpeta_config=tmp_path / "sala"))
	sesion.iniciar()
	robot = Robot(creadas[0])
	frases: list[str] = []

	def hasta(condicion, segundos: float = 10.0) -> bool:
		def paso() -> bool:
			robot.esperar(1)
			frases.extend(sesion.atender())
			return bool(condicion())

		return esperar(paso, segundos)

	assert hasta(lambda: robot.app.enlace is not None and robot.app.enlace.conectado and sesion.listo)
	yield robot, sesion, contexto, hasta, ruta
	sesion.detener()
	robot.app.cerrar_todo()


def _objetos(contexto) -> list[Any]:
	return [objeto for planta in contexto.entorno.plantas for objeto in planta.objetos]


def test_buscar_por_nombre_y_colocar(montaje):
	robot, sesion, contexto, hasta, ruta = montaje
	antes = len(_objetos(contexto))
	robot.tecla(pygame.K_F4)
	robot.elegir("Colocar un objeto aquí")
	principal = robot.cima
	assert isinstance(principal, Menu) and principal.titulo == "Colocar un objeto"
	opciones = robot.opciones()
	# No es una lista plana de dos mil objetos: unas pocas entradas (búsqueda y complementos).
	assert len(opciones) < 40
	assert opciones[0].startswith("Los que ya hay en este entorno") and opciones[1] == "Buscar por nombre"
	assert all(", " in texto and texto.split(", ")[-1].endswith("objetos") for texto in opciones[2:-1])
	robot.elegir("Buscar por nombre")
	assert isinstance(robot.cima, EntradaTexto)
	robot.escribir("paraguero")
	assert isinstance(robot.cima, Menu) and robot.cima.titulo.endswith("con «paraguero»")
	assert "Paragüero, " in " ".join(robot.opciones())
	robot.elegir("Paragüero,")
	assert robot.cima is robot.partida, "al elegir se vuelve al juego, sin menús del catálogo encima"
	assert hasta(lambda: len(_objetos(contexto)) == antes + 1)
	nuevo = contexto.entorno.elemento(contexto.seleccion)
	assert nuevo.tipo == "hogar/paraguero"
	assert abs(nuevo.x - robot.jugador.x) < 1.5 and abs(nuevo.y - robot.jugador.y) < 1.5
	assert hasta(lambda: "Paragüero: colocado." in robot.dicho() and "Entorno actualizado." in robot.dicho())
	assert any(objeto.tipo == "hogar/paraguero" for planta in cargar_paquete(ruta).entorno.plantas for objeto in planta.objetos)
	# «Otra vez» repite el último objeto colocado.
	robot.tecla(pygame.K_F4)
	robot.elegir("Colocar un objeto aquí")
	assert any(texto == "Otra vez: Paragüero" for texto in robot.opciones())
	assert robot.app.fallos == 0


def test_por_complemento_categoria_y_subcategoria(montaje, catalogo):
	robot, sesion, contexto, hasta, _ruta = montaje
	antes = len(_objetos(contexto))
	hogar = catalogo.complemento("hogar")
	robot.tecla(pygame.K_F4)
	robot.elegir("Colocar un objeto aquí")
	robot.elegir(hogar.nombre + ", ")
	assert robot.cima.titulo == hogar.nombre
	categorias = robot.opciones()
	assert len(categorias) > 1 and all(texto[-1].isdigit() for texto in categorias[:-1])
	# Una categoría grande se abre por subcategorías; una pequeña enseña sus objetos.
	grande = max(
		{definicion.categoria for definicion in hogar.objetos},
		key=lambda categoria: sum(1 for definicion in hogar.objetos if definicion.categoria == categoria),
	)
	robot.elegir(catalogo.nombre_categoria(grande) + ", ")
	nivel = robot.opciones()
	tamano = sum(1 for definicion in hogar.objetos if definicion.categoria == grande)
	if tamano > pantalla_recorrido.MAXIMO_SIN_SUBCATEGORIAS and len({d.subcategoria for d in hogar.objetos if d.categoria == grande}) > 1:
		assert all(texto[-1].isdigit() for texto in nivel[:-1]), "primero las subcategorías"
		robot.accion("menu_aceptar", 2)
	nombre = robot.opciones()[0]
	robot.accion("menu_aceptar", 2)
	assert robot.cima is robot.partida
	assert hasta(lambda: len(_objetos(contexto)) == antes + 1), "el Estudio no colocó el objeto elegido por categorías"
	assert contexto.entorno.elemento(contexto.seleccion).nombre == nombre
	assert hasta(lambda: f"{nombre}: colocado." in robot.dicho())
	assert robot.app.fallos == 0


def test_busqueda_con_muchos_resultados_pide_afinar(montaje):
	robot, _sesion, _contexto, _hasta, _ruta = montaje
	robot.tecla(pygame.K_F4)
	robot.elegir("Colocar un objeto aquí")
	robot.elegir("Buscar por nombre")
	robot.escribir("a")
	opciones = robot.opciones()
	assert opciones[0].startswith("Hay ") and "Buscar con más palabras" in opciones[0]
	assert len(opciones) == pantalla_recorrido.MAXIMO_RESULTADOS + 2, "aviso, los primeros resultados y Volver"
	robot.accion("menu_aceptar", 2)
	assert isinstance(robot.cima, EntradaTexto) and robot.cima.texto == "a "
	robot.tecla(pygame.K_ESCAPE)
	robot.atras(1)
	# Una búsqueda sin resultados lo dice y deja seguir.
	robot.elegir("Buscar por nombre")
	robot.escribir("zzzxyq")
	assert "No hay ningún objeto con «zzzxyq»" in robot.dicho()
	assert isinstance(robot.cima, Menu) and robot.cima.titulo == "Colocar un objeto"
	assert robot.app.fallos == 0
