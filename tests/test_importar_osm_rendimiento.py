"""Rendimiento de la conversión de OpenStreetMap con zonas grandes (las de un barrio entero).

Las zonas grandes se fabrican repitiendo en mosaico la muestra real de la
Plaza Mayor de Valladolid (``tests/datos/osm_real_valladolid_overpass.json``,
300 por 300 metros) con ids nuevos: la densidad de calles, edificios, portales
y comercios es la de un centro urbano real, sin salir a la red.

Medidas en el equipo de desarrollo (conversión sola):

========================  ========  ===========  ===========
Zona                      Espacios  Antes        Después
========================  ========  ===========  ===========
Muestra real, 150 m          249     0,26 s       0,09 s
Mosaico, 300 m             1.048     4,6 s        0,46 s
Mosaico, 400 m             1.993     23,6 s       1,0 s
Mosaico denso, 400 m       2.855     53,4 s       2,1 s
========================  ========  ===========  ===========

Antes, el tiempo crecía con el cuadrado del tamaño (cada espacio nuevo
recorría todos los anteriores para darse un id y cada comprobación de
cercanía recorría la zona entera); ahora crece casi en línea recta.
"""

from __future__ import annotations

import json
import random
import time
from pathlib import Path

import pytest

from app.dominio import geometria as geo
from app.importar import formas, osm
from app.importar.georef import Proyeccion

DATOS = Path(__file__).parent / "datos"
MUESTRA = DATOS / "osm_real_valladolid_overpass.json"
LAT, LON = 41.6520609, -4.7285484

# Presupuesto de la zona densa de 400 m (unos 2.900 espacios): medida en 2,1 s
# en el equipo de desarrollo; con el algoritmo de antes, 53 s. Quince segundos
# dejan margen de sobra para un equipo de pruebas siete veces más lento y aun
# así detectan enseguida que algo ha vuelto a ser cuadrático.
PRESUPUESTO_S = 15.0


def zona_sintetica(radio: float, paso: float = 300.0) -> dict:
	"""Datos de Overpass de ``radio`` metros: la muestra real repetida en mosaico cada ``paso`` metros, con ids nuevos."""
	base = json.loads(MUESTRA.read_text(encoding="utf-8"))
	proyeccion = Proyeccion(LAT, LON)
	lado = 1
	while lado * paso < 2 * radio:
		lado += 1
	elementos: list[dict] = []
	for numero in range(lado * lado):
		fila, columna = divmod(numero, lado)
		latitud, longitud = proyeccion.a_latlon((columna - (lado - 1) / 2.0) * paso, (fila - (lado - 1) / 2.0) * paso)
		dlat, dlon = latitud - LAT, longitud - LON
		desplazamiento = numero * 10_000_000_000
		for elemento in base["elements"]:
			nuevo = dict(elemento, id=elemento["id"] + desplazamiento)
			if elemento["type"] == "node":
				nuevo["lat"] = elemento["lat"] + dlat
				nuevo["lon"] = elemento["lon"] + dlon
			elif elemento["type"] == "way":
				nuevo["nodes"] = [nodo + desplazamiento for nodo in elemento["nodes"]]
			else:
				nuevo["members"] = [dict(miembro, ref=miembro["ref"] + desplazamiento) for miembro in elemento["members"]]
			elementos.append(nuevo)
	return {"elements": elementos, "osm3s": base["osm3s"], "recuadro": list(osm.recuadro_de(LAT, LON, radio)), "centro": [LAT, LON]}


def test_la_rejilla_da_lo_mismo_que_recorrerlo_todo() -> None:
	azar = random.Random(7)
	cajas = []
	for _numero in range(400):
		x, y = azar.uniform(-300, 300), azar.uniform(-300, 300)
		cajas.append((x, y, x + azar.uniform(0, 40), y + azar.uniform(0, 40)))
	rejilla = formas.RejillaCajas(20.0)
	for indice, caja in enumerate(cajas):
		rejilla.anadir(indice, caja)
	for _consulta in range(200):
		x, y = azar.uniform(-320, 320), azar.uniform(-320, 320)
		pedida = (x, y, x + azar.uniform(0, 15), y + azar.uniform(0, 15))
		exactas = [i for i, caja in enumerate(cajas) if geo.cajas_se_tocan(pedida, caja)]
		candidatas = rejilla.cerca(pedida)
		assert candidatas == sorted(candidatas)
		assert [i for i in candidatas if geo.cajas_se_tocan(pedida, cajas[i])] == exactas


@pytest.mark.lento
def test_zona_densa_de_400_metros_dentro_del_presupuesto(caplog: pytest.LogCaptureFixture) -> None:
	datos = zona_sintetica(400.0, 240.0)
	inicio = time.perf_counter()
	with caplog.at_level("INFO", logger="app.importar.osm_conversion"):
		resultado = osm.convertir(datos, osm.OpcionesOSM(nombre="Barrio de prueba"))
	segundos = time.perf_counter() - inicio
	planta = resultado.entorno.plantas[0]
	assert len(planta.espacios) >= 2500, len(planta.espacios)
	assert segundos < PRESUPUESTO_S, f"La conversión de {len(planta.espacios)} espacios tardó {segundos:.1f} s"
	ids = resultado.entorno.ids()
	assert len(ids) == len(set(ids)), "ningún id repetido"
	assert "nuevo_id" not in vars(resultado.entorno), "el entorno vuelve con su generador de ids de siempre"
	assert any("Duración de cada fase" in r.getMessage() for r in caplog.records)


@pytest.mark.lento
def test_el_tiempo_crece_casi_en_linea_recta() -> None:
	"""Con el doble de espacios no puede tardar el cuádruple (lo que pasaba antes)."""
	tiempos: list[tuple[int, float]] = []
	for radio in (150.0, 300.0):
		datos = zona_sintetica(radio)
		inicio = time.perf_counter()
		resultado = osm.convertir(datos)
		tiempos.append((len(resultado.entorno.plantas[0].espacios), time.perf_counter() - inicio))
	(pocos, rapido), (muchos, lento) = tiempos
	# 4 veces más espacios; con un crecimiento cuadrático tardaría 16 veces más.
	assert muchos >= 3 * pocos
	assert lento < rapido * (muchos / pocos) * 2.5 + 0.5, tiempos
