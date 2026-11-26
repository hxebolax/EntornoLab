"""Pruebas de la geometría plana del dominio."""

from __future__ import annotations

import math

import pytest

from app.dominio import geometria as geo

CUADRADO = [(0.0, 0.0), (2.0, 0.0), (2.0, 2.0), (0.0, 2.0)]
ELE = [(0.0, 0.0), (4.0, 0.0), (4.0, 2.0), (2.0, 2.0), (2.0, 4.0), (0.0, 4.0)]


def test_rumbos_basicos():
	assert geo.rumbo(0, 1) == pytest.approx(0)
	assert geo.rumbo(1, 0) == pytest.approx(90)
	assert geo.rumbo(0, -1) == pytest.approx(180)
	assert geo.rumbo(-1, 0) == pytest.approx(270)
	assert geo.rumbo_entre((1, 1), (2, 2)) == pytest.approx(45)
	assert geo.normalizar_rumbo(-90) == pytest.approx(270)
	assert geo.normalizar_rumbo(720) == pytest.approx(0)


def test_diferencia_de_rumbos_con_signo():
	assert geo.diferencia_rumbos(350, 10) == pytest.approx(20)
	assert geo.diferencia_rumbos(10, 350) == pytest.approx(-20)
	assert geo.diferencia_rumbos(0, 180) == pytest.approx(-180)
	assert abs(geo.diferencia_rumbos(90, 90)) < 1e-9


def test_punto_a_distancia_y_cardinales():
	assert geo.punto_a_distancia((0, 0), 90, 3) == pytest.approx((3, 0))
	assert geo.punto_a_distancia((1, 1), 180, 2) == pytest.approx((1, -1))
	assert geo.punto_cardinal(0) == "norte"
	assert geo.punto_cardinal(44) == "noreste"
	assert geo.punto_cardinal(359) == "norte"
	assert geo.lado_cardinal(100) == "este"
	assert geo.lado_cardinal(260) == "oeste"


def test_distancia_y_proyeccion_sobre_segmento():
	assert geo.distancia((0, 0), (3, 4)) == pytest.approx(5)
	assert geo.proyeccion_sobre_segmento((1, 5), (0, 0), (2, 0)) == pytest.approx((1, 0))
	assert geo.proyeccion_sobre_segmento((9, 5), (0, 0), (2, 0)) == pytest.approx((2, 0))
	assert geo.distancia_punto_segmento((1, 5), (0, 0), (2, 0)) == pytest.approx(5)
	assert geo.parametro_segmento((1, 0), (0, 0), (4, 0)) == pytest.approx(0.25)
	assert geo.parametro_segmento((6, 0), (0, 0), (4, 0), limitar=False) == pytest.approx(1.5)
	assert geo.parametro_segmento((1, 1), (2, 2), (2, 2)) == 0.0


def test_corte_de_segmentos():
	assert geo.corte_segmentos((0, 0), (2, 2), (0, 2), (2, 0)) == pytest.approx((1, 1))
	assert geo.corte_segmentos((0, 0), (1, 0), (0, 1), (1, 1)) is None
	assert geo.corte_segmentos((0, 0), (1, 1), (2, 0), (3, 1)) is None
	assert geo.corte_rectas((0, 0), (1, 0), (5, -1), (5, 1)) == pytest.approx((5, 0))
	assert geo.segmentos_se_cruzan((0, 0), (2, 2), (0, 2), (2, 0))
	# Tocarse por un extremo no es cruzarse.
	assert not geo.segmentos_se_cruzan((0, 0), (1, 0), (1, 0), (1, 1))
	assert geo.distancia_segmentos((0, 0), (1, 0), (0, 2), (1, 2)) == pytest.approx(2)
	assert geo.distancia_segmentos((0, 0), (2, 2), (0, 2), (2, 0)) == 0.0


def test_intervalo_y_recorte_de_segmento():
	a, b = (0.0, 0.0), (10.0, 0.0)
	assert geo.intervalo_sobre_segmento(a, b, (2, 0), (3, 0)) == pytest.approx((2, 3))
	assert geo.intervalo_sobre_segmento(a, b, (3, 0.01), (2, 0)) == pytest.approx((2, 3))
	assert geo.intervalo_sobre_segmento(a, b, (2, 1), (3, 1)) is None
	assert geo.intervalo_sobre_segmento(a, b, (12, 0), (13, 0)) is None
	# Una puerta que se sale del lado se recorta a lo que hay de pared.
	assert geo.intervalo_sobre_segmento(a, b, (9, 0), (11, 0)) == pytest.approx((9, 10))
	trozos = geo.recortar_segmento(a, b, [(6, 7), (2, 3)])
	assert trozos == [((0.0, 0.0), (2.0, 0.0)), ((3.0, 0.0), (6.0, 0.0)), ((7.0, 0.0), (10.0, 0.0))]
	assert geo.recortar_segmento(a, b, [(0, 10)]) == []
	assert geo.recortar_segmento(a, b, []) == [(a, b)]
	assert len(geo.recortar_segmento(a, b, [(2, 5), (4, 6)])) == 2
	assert geo.recortar_segmento(a, a, []) == []


def test_rayo_contra_segmentos():
	paredes = [((-1.0, 5.0), (1.0, 5.0)), ((-1.0, 2.0), (1.0, 2.0)), ((3.0, -1.0), (3.0, 1.0))]
	choque = geo.rayo_contra_segmentos((0, 0), 0, paredes)
	assert choque is not None
	assert choque[0] == pytest.approx(2)
	assert choque[1] == pytest.approx((0, 2))
	assert choque[2] == 1
	assert geo.rayo_contra_segmentos((0, 0), 90, paredes)[2] == 2
	assert geo.rayo_contra_segmentos((0, 0), 180, paredes) is None
	assert geo.rayo_contra_segmentos((0, 0), 0, paredes, alcance=1.5) is None


def test_lineas():
	linea = [(0.0, 0.0), (3.0, 0.0), (3.0, 4.0)]
	assert geo.longitud_linea(linea) == pytest.approx(7)
	punto, rumbo = geo.punto_en_linea(linea, 5)
	assert punto == pytest.approx((3, 2))
	assert rumbo == pytest.approx(0)
	cercano, distancia, indice = geo.proyeccion_sobre_linea((5, 3), linea)
	assert cercano == pytest.approx((3, 3))
	assert distancia == pytest.approx(2)
	assert indice == 1
	derecha = geo.desplazar_linea([(0, 0), (10, 0)], 1)
	assert derecha[0] == pytest.approx((0, -1))
	assert derecha[1] == pytest.approx((10, -1))
	# En una esquina las paralelas se unen en inglete, sin muescas.
	esquina = geo.desplazar_linea(linea, 1)
	assert len(esquina) == 3
	assert esquina[1] == pytest.approx((4, -1))


def test_medidas_de_poligonos():
	assert geo.area(CUADRADO) == pytest.approx(4)
	assert geo.area_con_signo(CUADRADO[::-1]) == pytest.approx(-4)
	assert geo.area(ELE) == pytest.approx(12)
	assert geo.perimetro(CUADRADO) == pytest.approx(8)
	assert geo.centroide(CUADRADO) == pytest.approx((1, 1))
	assert geo.centroide([(0, 0), (2, 0)]) == pytest.approx((1, 0))
	assert geo.caja(ELE) == (0.0, 0.0, 4.0, 4.0)
	assert geo.es_antihorario(CUADRADO)
	assert geo.orientar_antihorario(CUADRADO[::-1]) == CUADRADO
	assert geo.es_convexo(CUADRADO)
	assert not geo.es_convexo(ELE)
	assert len(geo.lados(CUADRADO)) == 4


def test_poligono_simple_o_autointersecante():
	assert geo.es_simple(CUADRADO)
	assert geo.es_simple(ELE)
	lazo = [(0.0, 0.0), (2.0, 2.0), (2.0, 0.0), (0.0, 2.0)]
	assert not geo.es_simple(lazo)
	assert not geo.es_simple([(0.0, 0.0), (1.0, 0.0)])
	assert not geo.es_simple([(0.0, 0.0), (0.0, 0.0), (1.0, 0.0), (1.0, 1.0)])


def test_punto_en_poligono():
	assert geo.punto_en_poligono((1, 1), CUADRADO)
	assert not geo.punto_en_poligono((3, 1), CUADRADO)
	assert geo.punto_en_poligono((2, 1), CUADRADO)
	assert not geo.punto_en_poligono((2, 1), CUADRADO, borde=False)
	assert geo.punto_en_poligono((1, 3), ELE)
	assert not geo.punto_en_poligono((3, 3), ELE)
	assert geo.distancia_punto_poligono((1, 1), CUADRADO) == 0.0
	assert geo.distancia_punto_poligono((5, 1), CUADRADO) == pytest.approx(3)


def test_rectangulo_girado():
	recto = geo.rectangulo_girado(0, 0, 2, 1, 0)
	assert geo.caja(recto) == pytest.approx((-1, -0.5, 1, 0.5))
	girado = geo.rectangulo_girado(0, 0, 2, 1, 90)
	assert geo.caja(girado) == pytest.approx((-0.5, -1, 0.5, 1))
	oblicuo = geo.rectangulo_girado(5, 5, 2, 2, 45)
	assert geo.area(oblicuo) == pytest.approx(4)
	assert geo.caja(oblicuo)[2] == pytest.approx(5 + math.sqrt(2))
	assert geo.girar_punto((0, 1), (0, 0), 90) == pytest.approx((1, 0))
	assert geo.rectangulo(1, 2, 3, 4) == [(1, 2), (4, 2), (4, 6), (1, 6)]
	assert geo.trasladar(CUADRADO, 1, -1)[0] == (1.0, -1.0)


def test_forma_a_mundo_respeta_medidas_y_rumbo():
	unidad = [(0, 0), (1, 0), (1, 1), (0, 1)]
	assert geo.caja(geo.forma_a_mundo(unidad, 10, 10, 2, 1, 0)) == pytest.approx((9, 9.5, 11, 10.5))
	# El frente (y = 1) mira al rumbo: con rumbo 90 el fondo queda de oeste a este.
	assert geo.caja(geo.forma_a_mundo(unidad, 10, 10, 2, 1, 90)) == pytest.approx((9.5, 9, 10.5, 11))
	triangulo = geo.forma_a_mundo([(0, 0), (1, 0), (0, 1)], 0, 0, 2, 2, 0)
	assert geo.area(triangulo) == pytest.approx(2)
	assert geo.es_antihorario(triangulo)
	assert geo.area(geo.circulo(0, 0, 1, 64)) == pytest.approx(math.pi, rel=0.01)


def test_interseccion_de_convexos():
	otro = geo.trasladar(CUADRADO, 1, 1)
	comun = geo.interseccion_convexa(CUADRADO, otro)
	assert geo.area(comun) == pytest.approx(1)
	assert geo.interseccion_convexa(CUADRADO, geo.trasladar(CUADRADO, 5, 0)) == []
	assert geo.area_interseccion(CUADRADO, otro) == pytest.approx(1)
	assert geo.area_interseccion(CUADRADO, CUADRADO) == pytest.approx(4)


def test_triangulacion_conserva_el_area():
	assert sum(geo.area(t) for t in geo.triangular(ELE)) == pytest.approx(12)
	assert sum(geo.area(t) for t in geo.triangular(CUADRADO)) == pytest.approx(4)
	estrella = [(0, 0), (2, 1), (4, 0), (3, 2), (4, 4), (2, 3), (0, 4), (1, 2)]
	assert sum(geo.area(t) for t in geo.triangular(estrella)) == pytest.approx(geo.area(estrella))
	assert geo.triangular([(0, 0), (1, 1)]) == []


def test_solape_de_no_convexos():
	# Un cuadrado en el hueco de la ele no la pisa, aunque sus cajas se solapen.
	en_el_hueco = geo.rectangulo(2.5, 2.5, 1, 1)
	assert not geo.poligonos_se_solapan(ELE, en_el_hueco)
	en_el_brazo = geo.rectangulo(0.5, 2.5, 1, 1)
	assert geo.poligonos_se_solapan(ELE, en_el_brazo)
	assert geo.area_interseccion(ELE, geo.rectangulo(1, 1, 2, 2)) == pytest.approx(3)
	assert geo.area_interseccion(geo.rectangulo(1, 1, 2, 2), ELE) == pytest.approx(3)
	assert geo.area_interseccion(ELE, geo.trasladar(ELE, 1, 0)) == pytest.approx(8)
	assert geo.area_interseccion(ELE, geo.trasladar(ELE, 4, 4)) == pytest.approx(0, abs=1e-9)


def test_tocarse_no_es_solaparse():
	vecino = geo.trasladar(CUADRADO, 2, 0)
	assert not geo.poligonos_se_solapan(CUADRADO, vecino)
	assert geo.poligonos_se_solapan(CUADRADO, geo.trasladar(CUADRADO, 1.9, 0))
	# Caso delicado: lados colineales y centroides sobre el borde del otro.
	assert geo.poligonos_se_solapan(CUADRADO, geo.trasladar(CUADRADO, 1, 0))


def test_poligono_contenido_en_poligono():
	assert geo.poligono_contiene(CUADRADO, geo.rectangulo(0.5, 0.5, 1, 1))
	# Pegado a la pared por dentro sigue estando dentro.
	assert geo.poligono_contiene(CUADRADO, geo.rectangulo(0, 0, 1, 2))
	assert not geo.poligono_contiene(CUADRADO, geo.rectangulo(1.5, 0.5, 1, 1))
	assert geo.poligono_contiene(ELE, geo.rectangulo(0.2, 2.2, 1.5, 1.5))
	assert not geo.poligono_contiene(ELE, geo.rectangulo(1.5, 1.5, 1.5, 1.5))
	assert geo.poligono_contiene(CUADRADO, CUADRADO)


def test_segmento_que_cruza_un_poligono():
	assert geo.segmento_cruza_poligono((-1, 1), (3, 1), CUADRADO)
	assert geo.segmento_cruza_poligono((0.5, 1), (1.5, 1), CUADRADO)
	assert not geo.segmento_cruza_poligono((-1, 0), (3, 0), CUADRADO)
	assert not geo.segmento_cruza_poligono((3, 0), (3, 5), CUADRADO)


def test_distancia_minima_entre_poligonos():
	assert geo.distancia_entre_poligonos(CUADRADO, geo.trasladar(CUADRADO, 3, 0)) == pytest.approx(1)
	assert geo.distancia_entre_poligonos(CUADRADO, geo.trasladar(CUADRADO, 2, 0)) == pytest.approx(0)
	assert geo.distancia_entre_poligonos(CUADRADO, geo.trasladar(CUADRADO, 1, 1)) == 0.0
	assert geo.distancia_entre_poligonos(CUADRADO, geo.rectangulo(0.5, 0.5, 0.5, 0.5)) == 0.0
	assert geo.distancia_entre_poligonos(CUADRADO, geo.trasladar(CUADRADO, 3, 3)) == pytest.approx(math.sqrt(2))
	assert geo.distancia_poligono_segmento(CUADRADO, (3, 0), (3, 2)) == pytest.approx(1)
	assert geo.distancia_poligono_segmento(CUADRADO, (1, 1), (5, 5)) == 0.0
	assert geo.distancia_entre_poligonos([], CUADRADO) == math.inf


def test_recorte_por_semiplano_y_extension():
	mitad = geo.recortar_por_semiplano(CUADRADO, (1, 2), (1, 0))
	assert geo.area(mitad) == pytest.approx(2)
	assert geo.caja(mitad) == pytest.approx((1, 0, 2, 2))
	assert geo.recortar_por_semiplano(CUADRADO, (5, 0), (5, 2)) != []
	assert geo.recortar_por_semiplano(CUADRADO, (5, 2), (5, 0)) == []
	assert geo.extension_en_rumbo(CUADRADO, 0) == pytest.approx((0, 2))
	assert geo.extension_en_rumbo(CUADRADO, 270) == pytest.approx((-2, 0))
	assert geo.cajas_se_tocan((0, 0, 1, 1), (1.5, 0, 2, 1), margen=0.5)
	assert not geo.cajas_se_tocan((0, 0, 1, 1), (1.5, 0, 2, 1))
