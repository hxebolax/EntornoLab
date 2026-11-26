"""Índice espacial de los espacios de una planta: mismos resultados que buscar en todos y se entera de los cambios.

Por qué hay que vigilarlo: ``Planta.espacios_en`` decide en qué espacio está
cada puerta, objeto y referencia (el árbol del Estudio, la descripción, la
validación, el motor). Si el índice devolviera otra cosa que la búsqueda
exhaustiva, o se quedara con espacios viejos tras una edición, el alumno oiría
que está donde no está.
"""

from __future__ import annotations

import random

import pytest

from app.dominio import edicion
from app.dominio import geometria as geo
from app.dominio.indice_espacial import RejillaCajas
from app.dominio.modelo import Entorno, Espacio, IndiceEspacios, ListaEspacios, Planta, invalidar_indices
from app.ui import operaciones
from tests import _entornos_grandes as eg


@pytest.fixture(scope="module")
def plaza() -> Entorno:
	return eg.plaza_real()


@pytest.fixture(scope="module")
def barrio() -> Entorno:
	return eg.barrio(1000)


def _puntos_de_prueba(planta: Planta, cuantos: int, semilla: int = 3) -> list[tuple[float, float]]:
	"""Puntos al azar en la zona de la planta, más los vértices, los centros y los puntos medios de los lados (los casos de borde)."""
	azar = random.Random(semilla)
	x0, y0, x1, y1 = planta.caja()
	puntos = [(azar.uniform(x0 - 5, x1 + 5), azar.uniform(y0 - 5, y1 + 5)) for _ in range(cuantos)]
	for espacio in planta.espacios[:120]:
		puntos.extend(espacio.contorno[:3])
		puntos.append(espacio.centro())
		for a, b in espacio.lados()[:2]:
			puntos.append(geo.punto_medio(a, b))
	return puntos


def _ids(espacios: list[Espacio]) -> list[int]:
	return [id(espacio) for espacio in espacios]


def test_mismos_espacios_que_la_busqueda_exhaustiva(plaza: Entorno, barrio: Entorno) -> None:
	for entorno in (plaza, barrio):
		planta = entorno.plantas[0]
		for x, y in _puntos_de_prueba(planta, 1500):
			assert _ids(planta.espacios_en(x, y)) == _ids(planta.espacios_en_exhaustivo(x, y)), (x, y)
			assert planta.espacio_en(x, y, incluir_macizos=False) is next(
				(e for e in planta.espacios_en_exhaustivo(x, y) if not e.macizo), None
			)


def test_planta_pequena_sin_rejilla() -> None:
	entorno = edicion.crear_entorno("Casa")
	planta = edicion.crear_planta(entorno, "Baja")
	salon = edicion.crear_habitacion_rectangular(entorno, planta, "Salón", 0, 0, 5, 4)
	# Una zona dentro de otra (como un paso de peatones sobre la calzada): gana la más pequeña.
	alfombra = Espacio(id="esp-rincon", nombre="Rincón", contorno=geo.rectangulo(1, 1, 1, 1), cerrado=False)
	planta.espacios.append(alfombra)
	assert planta.espacios_en(1.5, 1.5) == [alfombra, salon]
	assert planta.espacios_en(5.0, 4.0) == [salon], "el borde cuenta"
	assert planta.espacios_en(5.1, 4.0) == []


def test_se_entera_de_mover_un_espacio(plaza: Entorno) -> None:
	entorno = Entorno.de_dict(plaza.a_dict())
	planta = entorno.plantas[0]
	espacio = next(e for e in planta.espacios if e.tipo == "acera")
	centro = espacio.centro()
	assert espacio in planta.espacios_en(*centro)
	indice = planta.indice_espacios()
	edicion.mover(entorno, espacio, 500.0, 0.0)
	assert not indice.vigente(planta.espacios)
	assert espacio not in planta.espacios_en(*centro)
	assert espacio in planta.espacios_en(centro[0] + 500.0, centro[1])


def test_se_entera_de_anadir_y_quitar_espacios(plaza: Entorno) -> None:
	entorno = Entorno.de_dict(plaza.a_dict())
	planta = entorno.plantas[0]
	assert isinstance(planta.espacios, ListaEspacios)
	lejos = (5000.0, 5000.0)
	assert planta.espacios_en(*lejos) == []
	nuevo = edicion.crear_habitacion_rectangular(entorno, planta, "Caseta", 4999.0, 4999.0, 2.0, 2.0)
	assert planta.espacios_en(*lejos) == [nuevo]
	planta.espacios.remove(nuevo)
	assert planta.espacios_en(*lejos) == []
	planta.espacios.append(nuevo)
	assert planta.espacios_en(*lejos) == [nuevo]
	del planta.espacios[-1]
	assert planta.espacios_en(*lejos) == []
	# Una lista normal puesta a mano también vale: se compara entera.
	planta.espacios = [*planta.espacios, nuevo]
	assert planta.espacios_en(*lejos) == [nuevo]
	planta.espacios.pop()
	assert planta.espacios_en(*lejos) == []


def test_se_entera_de_sustituir_un_contorno_y_de_invalidar_a_mano(plaza: Entorno) -> None:
	entorno = Entorno.de_dict(plaza.a_dict())
	planta = entorno.plantas[0]
	espacio = planta.espacios[3]
	planta.espacios_en(0.0, 0.0)
	espacio.contorno = geo.rectangulo(7000.0, 7000.0, 3.0, 3.0)
	assert planta.espacios_en(7001.0, 7001.0) == [espacio]
	# Cambiarlo en el sitio no se detecta solo (la regla es sustituirlo); con invalidar_indices sí.
	espacio.contorno[0] = (6990.0, 6990.0)
	invalidar_indices()
	assert planta.espacios_en(6991.0, 6991.0) == planta.espacios_en_exhaustivo(6991.0, 6991.0)


def test_otro_entorno_con_los_mismos_datos_no_reutiliza_espacios_viejos(plaza: Entorno) -> None:
	# Al deshacer, el entorno nuevo tiene espacios iguales pero distintos: el índice no puede devolver los viejos.
	uno = Entorno.de_dict(plaza.a_dict())
	otro = Entorno.de_dict(uno.a_dict())
	centro = uno.plantas[0].espacios[5].centro()
	de_uno = uno.plantas[0].espacios_en(*centro)
	assert de_uno and all(any(e is propio for propio in uno.plantas[0].espacios) for e in de_uno)
	otro.plantas[0].__dict__["_indice_espacios"] = uno.plantas[0].indice_espacios()
	de_otro = otro.plantas[0].espacios_en(*centro)
	assert len(de_otro) == len(de_uno)
	assert all(any(e is propio for propio in otro.plantas[0].espacios) for e in de_otro)


def test_en_caja_es_una_preseleccion_completa(barrio: Entorno) -> None:
	planta = barrio.plantas[0]
	indice = planta.indice_espacios()
	azar = random.Random(5)
	x0, y0, x1, y1 = planta.caja()
	for _vez in range(200):
		ax, ay = azar.uniform(x0, x1), azar.uniform(y0, y1)
		caja = (ax, ay, ax + azar.uniform(0, 30), ay + azar.uniform(0, 30))
		esperados = [e for e in planta.espacios if len(e.contorno) >= 3 and geo.cajas_se_tocan(caja, e.caja(), margen=0.06)]
		assert _ids(indice.en_caja(*caja, margen=0.06)) == _ids(esperados)


def test_rejilla_ordena_y_no_pierde_los_enormes() -> None:
	rejilla = RejillaCajas(1.0)
	rejilla.meter((0, 0, 1, 1))
	rejilla.meter((-1e6, -1e6, 1e6, 1e6))
	rejilla.meter((5, 5, 6, 6))
	assert rejilla.en_punto(0.5, 0.5) == [0, 1]
	assert rejilla.en_punto(5.5, 5.5) == [1, 2]
	assert rejilla.en_caja(0, 0, 6, 6) == [0, 1, 2]
	assert rejilla.en_punto(float("nan"), 0) == [0, 1, 2]


def test_aberturas_y_vecinos_iguales_que_antes(plaza: Entorno) -> None:
	planta = plaza.plantas[0]
	todas = edicion.aberturas_por_espacio(planta)
	for espacio in planta.espacios:
		exhaustivas = [
			abertura
			for abertura in planta.aberturas
			if any(geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, 0.05) is not None for a, b in espacio.lados())
		]
		assert _ids(edicion.aberturas_de(planta, espacio)) == _ids(exhaustivas)
		assert _ids(todas[id(espacio)]) == _ids(exhaustivas)
	for espacio in planta.espacios[:80]:
		exhaustivos = [
			otro
			for otro in planta.espacios
			if otro is not espacio and len(otro.contorno) >= 3 and edicion.pared_compartida(espacio, otro) is not None
		]
		assert [o for o, _lado in edicion.vecinos(planta, espacio)] == exhaustivos


def test_contenido_de_planta_igual_que_espacio_a_espacio_y_al_mover(plaza: Entorno) -> None:
	entorno = Entorno.de_dict(plaza.a_dict())
	planta = entorno.plantas[0]

	def comparar() -> None:
		todo = operaciones.contenido_de_planta(planta)
		for espacio in planta.espacios:
			assert _ids(todo[id(espacio)]) == _ids(operaciones.contenido_de_espacio(planta, espacio))

	comparar()
	referencia = planta.referencias[0]
	destino = next(e for e in planta.espacios if e.tipo == "calzada")
	edicion.mover_a(entorno, referencia, *destino.centro())
	comparar()
	assert referencia in operaciones.contenido_de_planta(planta)[id(planta.espacio_en(*destino.centro()))]
	edicion.borrar(entorno, referencia)
	comparar()


def test_el_indice_no_cuenta_al_guardar_ni_al_comparar(plaza: Entorno) -> None:
	planta = Entorno.de_dict(plaza.a_dict()).plantas[0]
	antes = planta.a_dict()
	planta.espacios_en(0.0, 0.0)
	assert isinstance(planta.__dict__.get("_indice_espacios"), IndiceEspacios)
	assert planta.a_dict() == antes
	assert Planta.de_dict(antes) == planta
