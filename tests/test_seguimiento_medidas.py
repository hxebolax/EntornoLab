"""Pruebas de las medidas del resumen y de la clasificación de la estrategia de exploración."""

from __future__ import annotations

import json

import pytest

from app.seguimiento import medidas
from tests._seguimiento_util import ESPACIOS, SALA, andar


def test_distancia_y_velocidad():
	muestras = andar([(1, 1), (5, 1), (5, 4)], velocidad=1.0)
	resumen = medidas.calcular_resumen(muestras)
	assert resumen["distancia_m"] == pytest.approx(7.0, abs=0.05)
	assert resumen["tiempo_activo_s"] == pytest.approx(7.0, abs=0.3)
	assert resumen["velocidad_media_ms"] == pytest.approx(1.0, abs=0.05)
	assert resumen["saltos"] == 0
	json.dumps(resumen)  # todo el resumen se puede guardar como JSON


def test_una_recolocacion_no_cuenta_como_distancia():
	muestras = andar([(1, 1), (3, 1)]) + andar([(9, 7), (9, 5)], t0=3.0)
	recorrido = medidas.medir_distancia(muestras)
	assert recorrido["saltos"] == 1
	assert recorrido["distancia_m"] == pytest.approx(4.0, abs=0.05)


def test_cambio_de_planta_no_suma_distancia():
	muestras = andar([(1, 1), (3, 1)], planta="p0") + andar([(20, 20), (22, 20)], planta="p1", t0=3.0)
	assert medidas.medir_distancia(muestras)["distancia_m"] == pytest.approx(4.0, abs=0.05)


def test_muestras_rotas_se_descartan():
	muestras = [[0, "p0", 0, 0, 0], ["x", "p0"], None, [1, "p0", float("nan"), 0, 0], [1, "p0", 1, 0, 0]]
	assert medidas.medir_distancia(muestras)["distancia_m"] == pytest.approx(1.0)
	assert medidas.calcular_resumen([], [])["distancia_m"] == 0


def test_giros_se_cuentan_por_rotacion_acumulada():
	muestras = []
	t = 0.0
	rumbo = 0.0
	# 90 grados a la derecha en seis pulsaciones de 15, parado.
	for _vuelta in range(6):
		muestras.append([t, "p0", 0, 0, rumbo])
		rumbo += 15
		t += 0.25
	# Dos segundos quieto.
	for _vuelta in range(8):
		muestras.append([t, "p0", 0, 0, rumbo])
		t += 0.25
	# Media vuelta a la izquierda.
	for _vuelta in range(12):
		rumbo -= 15
		muestras.append([t, "p0", 0, 0, rumbo % 360])
		t += 0.25
	# Un temblor de 10 grados no es un giro.
	muestras.append([t + 3, "p0", 0, 0, (rumbo + 10) % 360])
	giros = medidas.medir_giros(muestras)
	assert giros["numero"] == 2
	assert giros["derecha"] == 1
	assert giros["izquierda"] == 1
	assert giros["medias_vueltas"] == 1


def test_choques_ayudas_objetivos_y_premios():
	muestras = andar([(1, 1), (9, 1)])
	eventos = [
		{"t": 1.0, "tipo": "choque", "datos": {"con": "mesa", "planta": "p0", "x": 2.0, "y": 1.0}},
		{"t": 2.0, "tipo": "choque", "datos": {"objeto": "silla"}, "pos": ["p0", 12.0, 1.0]},
		{"t": 2.5, "tipo": "choque", "datos": {}},
		{"t": 3.0, "tipo": "ayuda", "datos": {"ayuda": "donde_estoy"}},
		{"t": 3.5, "tipo": "ayuda", "datos": {"ayuda": "donde_estoy"}},
		{"t": 4.0, "tipo": "ayuda", "datos": {"ayuda": "baliza"}},
		{"t": 5.0, "tipo": "objetivo", "datos": {"id": "o1", "texto": "Llegar a la cocina"}},
		{"t": 6.0, "tipo": "premio", "datos": {"id": "p1", "nombre": "Llave"}},
		{"t": 6.5, "tipo": "intervencion", "datos": {"tipo": "pista"}},
		{"t": 7.0, "tipo": "valoracion", "datos": {"esfuerzo": 2}},
		{"sin": "tipo"},
	]
	resumen = medidas.calcular_resumen(muestras, eventos, espacios=ESPACIOS)
	assert resumen["choques"]["total"] == 3
	assert resumen["choques"]["por_espacio"] == {"sala": 1, "cocina": 1, "": 1}
	assert resumen["choques"]["lugares"][0]["con"] == "mesa"
	assert resumen["choques"]["lugares"][1]["espacio"] == "cocina"
	assert resumen["ayudas"]["total"] == 3
	assert resumen["ayudas"]["por_tipo"] == {"donde_estoy": 2, "baliza": 1}
	assert resumen["objetivos"] == [{"t": 5.0, "id": "o1", "nombre": "Llegar a la cocina"}]
	assert resumen["premios"] == [{"t": 6.0, "id": "p1", "nombre": "Llave"}]
	assert resumen["intervenciones"] == {"total": 1, "por_tipo": {"pista": 1}}
	assert resumen["valoracion"] == {"esfuerzo": 2}
	assert resumen["eventos_por_tipo"]["choque"] == 3


def test_espacios_visitados_por_contorno():
	muestras = andar([(2, 2), (14, 2), (2, 2)])
	datos = medidas.medir_espacios(muestras, [], ESPACIOS)
	assert datos["fuente"] == "traza"
	assert [e["id"] for e in datos["visitados"]] == ["sala", "cocina"]
	assert datos["visitados"][0]["entradas"] == 2
	assert datos["visitados"][0]["tiempo_s"] > datos["visitados"][1]["tiempo_s"] > 0
	assert [e["id"] for e in datos["no_visitados"]] == ["bano"]
	assert datos["proporcion_visitada"] == pytest.approx(2 / 3)


def test_espacios_visitados_por_eventos_si_no_hay_contornos():
	espacios = [
		{"id": "a", "nombre": "Aula"},
		{"id": "b", "nombre": "Pasillo"},
		{"id": "c", "nombre": "Patio"},
		{"id": "m", "nombre": "Muro", "macizo": True},
	]
	eventos = [
		{"t": 0.0, "tipo": "entrada_espacio", "datos": {"espacio": "a", "nombre": "Aula"}},
		{"t": 10.0, "tipo": "entrada_espacio", "datos": {"espacio": "b"}},
		{"t": 15.0, "tipo": "entrada_espacio", "datos": {"espacio": "a"}},
	]
	datos = medidas.medir_espacios([[0, "p0", 0, 0, 0], [20, "p0", 0, 0, 0]], eventos, espacios)
	assert datos["fuente"] == "eventos"
	assert {e["id"]: e["entradas"] for e in datos["visitados"]} == {"a": 2, "b": 1}
	assert datos["visitados"][0]["tiempo_s"] == pytest.approx(15.0)
	assert datos["visitados"][1]["nombre"] == "Pasillo"
	assert [e["id"] for e in datos["no_visitados"]] == ["c"]


def test_cociente_camino_real_entre_optimo():
	muestras = andar([(1, 1), (5, 1), (5, 5), (1, 5)])
	resumen = medidas.calcular_resumen(muestras, camino_optimo_m=4.0)
	assert resumen["cociente_camino"] == pytest.approx(3.0, abs=0.05)
	assert medidas.calcular_resumen(muestras)["cociente_camino"] is None
	assert medidas.calcular_resumen(muestras, camino_optimo_m=0.0)["cociente_camino"] is None


def test_pausas_y_puntuaciones_de_examen():
	muestras = andar([(1, 1), (5, 1)])
	resumen = medidas.calcular_resumen(
		muestras, pausas=[[1.0, 20.0], [3.0, 5.5]], puntuaciones={"puntos": 3, "pruebas": [{"ruta": "A", "acierto": True}]}
	)
	assert resumen["pausas"]["numero"] == 2
	assert resumen["tiempo_pausa_s"] == pytest.approx(25.5)
	assert resumen["examen"]["puntos"] == 3
	con_eventos = medidas.calcular_resumen(muestras, [{"t": 2, "tipo": "examen", "datos": {"ruta": "B", "puntos": 2}}])
	assert con_eventos["examen"]["pruebas"] == [{"t": 2.0, "ruta": "B", "puntos": 2}]


def test_estrategia_perimetro():
	vuelta = [(0.6, 0.6), (9.4, 0.6), (9.4, 7.4), (0.6, 7.4), (0.6, 0.6)]
	estrategia = medidas.clasificar_estrategia(andar(vuelta), [], [SALA])
	assert estrategia["tipo"] == "perimetro"
	assert estrategia["indicadores"]["cerca_de_pared"] > 0.9
	assert estrategia["indicadores"]["cobertura_perimetro"] > 0.9
	assert estrategia["confianza"] == "alta"
	assert not estrategia["aproximada"]


def test_estrategia_cuadricula():
	sala_grande = {"id": "g", "nombre": "Gimnasio", "planta": "p0", "contorno": [[0, 0], [30, 0], [30, 30], [0, 30]]}
	puntos = []
	for i, x in enumerate((8, 10, 12, 14, 16, 18)):
		tramo = [(x, 8), (x, 22)]
		puntos += tramo if i % 2 == 0 else list(reversed(tramo))
	estrategia = medidas.clasificar_estrategia(andar(puntos), [], [sala_grande])
	assert estrategia["tipo"] == "cuadricula"
	assert estrategia["indicadores"]["pasadas"] >= 6
	assert estrategia["indicadores"]["eje_dominante"] > 0.8


def test_estrategia_objeto_a_objeto():
	sala_grande = {"id": "g", "nombre": "Gimnasio", "planta": "p0", "contorno": [[0, 0], [40, 0], [40, 40], [0, 40]]}
	objetos = [(10, 10), (22, 14), (15, 27), (28, 25), (20, 18)]
	muestras = andar(objetos)
	eventos = []
	for x, y in objetos:
		t = next(m[0] for m in muestras if abs(m[2] - x) < 0.01 and abs(m[3] - y) < 0.01)
		eventos.append({"t": t, "tipo": "choque", "datos": {"con": "objeto", "planta": "p0", "x": x, "y": y}})
	estrategia = medidas.clasificar_estrategia(muestras, eventos, [sala_grande])
	assert estrategia["tipo"] == "objeto_a_objeto"
	assert estrategia["indicadores"]["tramos_entre_contactos"] == 4


def test_estrategia_sin_patron_e_insuficiente():
	sala_grande = {"id": "g", "nombre": "Gimnasio", "planta": "p0", "contorno": [[0, 0], [40, 0], [40, 40], [0, 40]]}
	deambular = [(20, 20), (23, 26), (17, 22), (25, 19), (19, 15), (22, 24), (15, 18), (24, 23)]
	assert medidas.clasificar_estrategia(andar(deambular), [], [sala_grande])["tipo"] == "sin_patron"
	assert medidas.clasificar_estrategia(andar([(1, 1), (3, 1)]), [], [SALA])["tipo"] == "insuficiente"
	assert medidas.clasificar_estrategia([], [], [])["tipo"] == "insuficiente"


def test_estrategia_sin_contornos_es_aproximada_y_de_confianza_baja():
	vuelta = [(0, 0), (9, 0), (9, 7), (0, 7), (0, 0)]
	estrategia = medidas.clasificar_estrategia(andar(vuelta), [], [])
	assert estrategia["aproximada"]
	assert estrategia["tipo"] == "perimetro"
	assert estrategia["confianza"] == "baja"


def test_en_un_pasillo_estrecho_no_se_valora_el_perimetro():
	pasillo = {"id": "pas", "nombre": "Pasillo", "planta": "p0", "contorno": [[0, 0], [20, 0], [20, 2], [0, 2]]}
	estrategia = medidas.clasificar_estrategia(andar([(1, 1), (19, 1), (1, 1)]), [], [pasillo])
	assert "cerca_de_pared" not in estrategia["indicadores"]
	assert estrategia["tipo"] != "perimetro"
