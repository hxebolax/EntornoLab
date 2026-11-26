"""«Paquete para el alumno» (pestaña Actividades del Estudio): el ``.elab`` que produce se abre y se juega en el reproductor.

Se exporta con la misma función que usa el botón (``exportar_paquete_alumno``),
solo con una de las actividades del entorno; después el reproductor lo abre
por ``app/reproductor/entornos.py`` y un robot juega esa actividad, la real,
hasta su final.
"""

# ruff: noqa: F811 - los parámetros de las pruebas se llaman como las fixtures importadas
from __future__ import annotations

import copy

import pytest

from app.dominio.formato import cargar_paquete
from app.reproductor import entornos, puente_actividades
from app.reproductor.menus import Menu
from app.ui.seguimiento import presentador_actividades
from app.ui.seguimiento.contexto import ContextoDePrueba

from .test_reproductor_comun import Robot, crear_app, paquete_con_busqueda, sin_navegador  # noqa: F401 - fixtures


@pytest.mark.lento
def test_el_paquete_para_el_alumno_se_abre_y_se_juega_hasta_el_final(data_temporal, tmp_path, sin_navegador):
	if not puente_actividades.disponible():
		pytest.skip("app.actividades no está disponible")
	origen = cargar_paquete(paquete_con_busqueda(tmp_path / "estudio", premios=1))
	otra = copy.deepcopy(origen.actividades[0])
	otra.update({"id": "otra", "nombre": "Otra búsqueda"})
	contexto = ContextoDePrueba(entorno=origen.entorno, actividades=[*origen.actividades, otra])
	contexto.recursos = dict(origen.recursos)
	destino = tmp_path / "para el alumno" / "Vivienda (alumno).elab"
	destino.parent.mkdir()

	assert presentador_actividades.exportar_paquete_alumno(contexto, ["busca"], destino) == 1

	paquete = entornos.abrir(destino)
	assert [actividad["id"] for actividad in paquete.actividades] == ["busca"], "lleva solo la actividad elegida"
	assert paquete.entorno.id == origen.entorno.id
	app = crear_app("--alumno", "Luna")
	try:
		robot = Robot(app)
		assert app.empezar_partida(paquete, paquete.actividad("busca"))
		partida = robot.partida
		robot.esperar(5)
		assert type(partida.actividad).__module__.startswith("app.actividades"), "es la actividad real"
		for premio in list(partida.datos["premios"]):
			robot.seguir((premio["planta"], premio["x"], premio["y"]))
			robot.esperar(5)
			if not partida.terminado and str(premio["id"]) not in partida.premios_recogidos:
				robot.accion("interactuar", 5)
		robot.esperar(5)
		assert partida.terminado and partida.completada, partida.estado_actividad()
		assert isinstance(robot.cima, Menu) and robot.cima.titulo == "Fin de Busca los premios"
		robot.elegir("Volver al menú principal")
		assert app.fallos == 0
	finally:
		app.cerrar_todo()
	assert list((data_temporal / "sessions").glob("*.json.gz")), "la sesión jugada con el paquete del alumno queda grabada"
