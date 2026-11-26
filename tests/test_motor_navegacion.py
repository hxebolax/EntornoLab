"""Pruebas de la navegación: rutas, distancias de camino, salidas y grafo de espacios."""

from __future__ import annotations

import math

import pytest

from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio import geometria as geo
from app.dominio.modelo import Posicion
from app.motor.mundo import Mundo
from app.motor.navegacion import Navegador, Ruta, lugar
from tests.test_motor_comun import Robot, poner_objeto, sala_de_pruebas


def _vivienda() -> tuple[Mundo, Navegador]:
	mundo = Mundo(ejemplos.vivienda_ejemplo())
	return mundo, Navegador(mundo)


def _centro(mundo: Mundo, nombre: str) -> tuple[str, float, float]:
	for indice in mundo.plantas():
		for _caja, espacio in indice.espacios:
			if espacio.nombre == nombre:
				x, y = espacio.centro()
				return indice.planta.id, x, y
	raise AssertionError(f"no existe el espacio {nombre}")


def test_lugar_admite_posicion_y_terna():
	assert lugar(Posicion("p", 1, 2, 90)) == ("p", 1.0, 2.0)
	assert lugar(("p", 1, 2)) == ("p", 1.0, 2.0)


def test_ruta_por_la_vivienda_pasa_por_las_puertas():
	mundo, nav = _vivienda()
	origen = ("pla-1", -1.0, 4.6)
	destino = _centro(mundo, "Baño")
	ruta = nav.ruta(origen, destino)
	assert ruta is not None
	recta = math.hypot(destino[1] - origen[1], destino[2] - origen[2])
	assert recta < ruta.longitud < recta * 1.5
	assert ruta.puntos[0] == origen and ruta.puntos[-1] == destino
	# Ningún tramo atraviesa una pared (las puertas cerradas sí valen: se pueden abrir).
	for a, b in zip(ruta.puntos, ruta.puntos[1:], strict=False):
		for _t, seg in mundo.cortes("pla-1", a[1:], b[1:], "paso"):
			assert seg.clase == "puerta"
	espacios = {mundo.espacio_en("pla-1", x, y).nombre for _p, x, y in ruta.puntos if mundo.espacio_en("pla-1", x, y) is not None}
	assert {"Entrada", "Pasillo", "Baño"} <= espacios
	# Pasa por el vano de la puerta del baño, que mide 72 cm.
	puerta = next(a for a in mundo.entorno.plantas[0].aberturas if "Baño" in a.nombre)
	assert any(geo.distancia_punto_segmento((x, y), puerta.a, puerta.b) < 0.3 for _p, x, y in ruta.puntos)
	assert nav.distancia(origen, destino) == pytest.approx(ruta.longitud)
	assert nav.distancia(destino, origen) == pytest.approx(ruta.longitud, rel=0.1)


def test_la_ruta_rodea_los_muebles(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	mundo = Mundo(entorno, catalogo)
	nav = Navegador(mundo)
	ruta = nav.ruta(("pla-1", 1.0, 3.0), ("pla-1", 7.0, 3.0))
	assert ruta is not None
	# La mesa ocupa de x = 3,4 a 4,6 y de y = 2,6 a 3,4, justo en la recta: hay que rodearla con holgura.
	assert 6.0 < ruta.longitud < 7.5
	for a, b in zip(ruta.puntos, ruta.puntos[1:], strict=False):
		assert not geo.segmento_cruza_poligono(a[1:], b[1:], geo.rectangulo(3.25, 2.45, 1.5, 1.1))
	assert ruta.giros(15.0) >= 2
	# Un destino dentro de un mueble (el centro de la mesa) se alcanza por el lado libre más cercano, sin fallar.
	assert nav.distancia(("pla-1", 1.0, 3.0), ("pla-1", 4.0, 3.0)) == pytest.approx(3.5, abs=0.5)


def test_puerta_con_llave_corta_el_camino_salvo_para_el_profesional():
	entorno = ejemplos.vivienda_ejemplo()
	puerta = next(a for a in entorno.plantas[0].aberturas if "Dormitorio" in a.nombre and a.tipo == "puerta")
	puerta.estado = "con_llave"
	mundo = Mundo(entorno)
	nav = Navegador(mundo)
	dormitorio = _centro(mundo, "Dormitorio")
	assert nav.ruta(("pla-1", -1.0, 4.6), dormitorio) is None
	alcanzables = {mundo.entorno.elemento(i).nombre for i in nav.espacios_alcanzables(("pla-1", -1.0, 4.6))}
	assert alcanzables == {"Entrada", "Pasillo", "Salón", "Cocina", "Baño"}
	assert Navegador(mundo, con_llave=True).ruta(("pla-1", -1.0, 4.6), dormitorio) is not None
	# Si se abre con la llave durante la partida, el navegador se entera.
	mundo.poner_abertura(puerta.id, "cerrada")
	assert nav.ruta(("pla-1", -1.0, 4.6), dormitorio) is not None


def test_ruta_alternativa_con_un_paso_cortado():
	entorno = ed.crear_entorno("Dos puertas")
	planta = ed.crear_planta(entorno, "Planta")
	a = ed.crear_habitacion_rectangular(entorno, planta, "A", 0, 0, 5, 8)
	b = ed.crear_habitacion_adosada(entorno, planta, "B", a, "este", 4, 8)
	cerca = ed.anadir_puerta_entre(entorno, planta, a, b, desplazamiento=0.5, estado="abierta")
	lejos = ed.anadir_puerta_entre(entorno, planta, a, b, desplazamiento=6.5, estado="cerrada")
	mundo = Mundo(entorno)
	nav = Navegador(mundo)
	origen, destino = (planta.id, 2.5, 1.0), (planta.id, 7.0, 1.0)
	directa = nav.ruta(origen, destino)
	alternativa = nav.ruta(origen, destino, evitar=[cerca.id])
	assert directa is not None and alternativa is not None
	assert directa.longitud < 5.5
	assert alternativa.longitud > directa.longitud + 8.0
	assert any(geo.distancia_punto_segmento((x, y), lejos.a, lejos.b) < 0.3 for _p, x, y in alternativa.puntos)
	assert nav.ruta(origen, destino, evitar=[cerca.id, lejos.id]) is None


def test_salidas_ordenadas_por_distancia_de_camino():
	entorno = ejemplos.centro_dos_plantas()
	nav = Navegador(Mundo(entorno))
	salidas = nav.salidas(entorno.inicio)
	assert [s.abertura.nombre for s in salidas] == ["Puerta principal", "Salida de emergencia oeste", "Salida de emergencia este"]
	distancias = [s.distancia for s in salidas]
	assert distancias == sorted(distancias)
	assert distancias[0] == pytest.approx(1.5, abs=0.3)
	# Desde el aula 2 (al este) la más cercana ya no es la principal.
	desde_aula = nav.salidas(("pla-1", 17.0, 3.0))
	assert desde_aula[0].abertura.nombre == "Salida de emergencia este"
	mejor = nav.salida_mas_cercana(("pla-1", 17.0, 3.0))
	assert mejor is not None and mejor.ruta is not None
	assert mejor.ruta.longitud == pytest.approx(mejor.distancia, abs=0.5)
	# Desde la planta primera hay que bajar: todas las salidas quedan más lejos que desde abajo.
	desde_arriba = nav.salidas(("pla-2", 17.0, 3.0))
	assert len(desde_arriba) == 3
	assert desde_arriba[0].distancia > desde_aula[0].distancia + 5.0


def test_ruta_entre_plantas_por_ascensor_o_por_escalera():
	entorno = ejemplos.centro_dos_plantas()
	nav = Navegador(Mundo(entorno))
	escalera = next(c for c in entorno.conectores if c.tipo == "escalera")
	ascensor = next(c for c in entorno.conectores if c.tipo == "ascensor")
	origen, destino = ("pla-1", 4.0, 1.5), ("pla-2", 3.0, 3.0)
	ruta = nav.ruta(origen, destino)
	assert isinstance(ruta, Ruta)
	assert ruta.plantas() == ["pla-1", "pla-2"]
	# En el ascensor no se anda: es el camino con menos metros.
	assert ruta.conectores == [ascensor.id]
	andando = nav.ruta(origen, destino, evitar=[ascensor.id])
	assert andando is not None and andando.conectores == [escalera.id]
	assert andando.longitud > ruta.longitud
	# Los seis metros de escalera cuentan como andados.
	en_baja = geo.longitud_linea(andando.puntos_de("pla-1"))
	en_primera = geo.longitud_linea(andando.puntos_de("pla-2"))
	assert andando.longitud == pytest.approx(en_baja + en_primera + 6.0, abs=0.01)
	assert ("pla-1", 8.8, 8.6) in andando.puntos and ("pla-2", 10.2, 8.6) in andando.puntos
	assert nav.ruta(origen, destino, evitar=[ascensor.id, escalera.id]) is None
	assert nav.ruta(origen, ("no-existe", 0, 0)) is None


def test_grafo_de_espacios():
	mundo, nav = _vivienda()
	grafo = nav.grafo_espacios()
	nombres = {i: mundo.entorno.elemento(i).nombre for i in grafo}
	pasillo = next(i for i, nombre in nombres.items() if nombre == "Pasillo")
	vecinos = {nombres.get(e.destino, "") for e in grafo[pasillo]}
	assert vecinos == {"Entrada", "Salón", "Cocina", "Dormitorio", "Baño"}
	assert all(e.tipo == "abertura" for e in grafo[pasillo])
	entrada = next(i for i, nombre in nombres.items() if nombre == "Entrada")
	# La puerta de la calle da fuera del entorno: destino vacío.
	assert {e.destino for e in grafo[entrada]} == {pasillo, ""}
	salon = next(i for i, nombre in nombres.items() if nombre == "Salón")
	bano = next(i for i, nombre in nombres.items() if nombre == "Baño")
	assert nav.ruta_espacios(salon, bano) == [salon, pasillo, bano]
	assert len(nav.espacios_alcanzables(salon)) == 6
	# Las ventanas no son pasos.
	assert all("Ventana" not in e.nombre for enlaces in grafo.values() for e in enlaces)


def test_grafo_con_conectores_y_bordes_abiertos():
	entorno = ejemplos.centro_dos_plantas()
	nav = Navegador(Mundo(entorno))
	tipos = {e.tipo for enlaces in nav.grafo_espacios().values() for e in enlaces}
	assert tipos == {"abertura", "conector"}
	assert len(nav.espacios_alcanzables(entorno.inicio)) == 16
	# En la calle no hay puertas entre acera y calzada: se pasa por el borde.
	barrio = ejemplos.barrio_ejemplo()
	mundo = Mundo(barrio)
	nav = Navegador(mundo)
	planta = barrio.plantas[0]
	acera = mundo.espacio_en(planta.id, -20.0, 4.5)
	enlaces = nav.enlaces(acera.id)
	assert enlaces and all(e.tipo == "abierto" for e in enlaces)
	destinos = {mundo.entorno.elemento(e.destino).tipo for e in enlaces}
	assert "calzada" in destinos and "paso_peatones" in destinos
	# Los edificios macizos no son alcanzables; el vestíbulo del centro cívico sí, por su portal.
	alcanzables = {mundo.entorno.elemento(i).nombre for i in nav.espacios_alcanzables(barrio.inicio)}
	assert "Vestíbulo del centro cívico" in alcanzables
	assert "Mercado" not in alcanzables and "Centro cívico" not in alcanzables


def test_ruta_por_la_calle_y_distancias_desde():
	barrio = ejemplos.barrio_ejemplo()
	mundo = Mundo(barrio)
	nav = Navegador(mundo)
	ruta = nav.ruta(barrio.inicio, ("pla-1", 8.0, -9.0))
	assert ruta is not None
	recta = math.hypot(28.0, 13.5)
	assert recta <= ruta.longitud < recta * 1.4
	# No atraviesa ningún edificio.
	for _planta, x, y in ruta.puntos:
		espacio = mundo.espacio_en("pla-1", x, y, macizos=True)
		assert espacio is None or not espacio.macizo
	campo = nav.distancias_desde(barrio.inicio, 15.0)
	assert nav.distancia_en(campo, -18.0, 5.2) == pytest.approx(2.1, abs=0.4)
	assert nav.distancia_en(campo, 30.0, 4.5) is None


def test_la_ruta_a_un_mueble_pegado_a_un_tabique_acaba_en_su_habitacion(tmp_path):
	"""Regresión: la celda libre más cercana al centro de un armario pegado al tabique estaba en la antesala.

	La ruta acababa al otro lado de la pared y el alumno (o el robot) no
	podía usar el armario. Ahora el final de la ruta está en la sala, con la
	recta libre hasta el mueble, se salga de donde se salga.
	"""
	entorno, planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	armario = poner_objeto(entorno, planta, catalogo, "prueba/armario", 0.4, 1.2, 90.0, estado="cerrado")
	mundo = Mundo(entorno, catalogo)
	nav = Navegador(mundo)
	destino = (planta.id, armario.x, armario.y)
	for origen in ((planta.id, 1.0, 3.0), (planta.id, 6.0, 3.0), (planta.id, -1.5, 3.0)):
		ruta = nav.ruta(origen, destino)
		assert ruta is not None
		_planta, x, y = ruta.puntos[-2]
		assert mundo.espacio_en(planta.id, x, y).nombre == "Sala", ruta.puntos
		cortes = [seg for _t, seg in mundo.cortes(planta.id, (x, y), (armario.x, armario.y), "paso") if seg.elemento_id != armario.id]
		assert cortes == []
		# La distancia de camino también llega por la sala: desde la antesala hay que dar la vuelta por la puerta.
		campo = nav.distancias_desde(origen)
		assert nav.distancia_en(campo, armario.x, armario.y) == pytest.approx(ruta.longitud, rel=0.25)
	# Un robot que sigue la ruta desde la antesala acaba en la sala con el armario a mano.
	robot = Robot(entorno, catalogo, inicio=Posicion(planta.id, -1.5, 3.0, 90.0))
	robot.seguir(destino)
	assert robot.espacio == "Sala"
	if robot.sesion.mundo.estado_objeto(armario.id) == "abierto":
		robot.pulsar("interactuar")
	robot.girar_a(geo.rumbo_entre(robot.pos, (armario.x, armario.y)))
	assert armario.id in [dato["id"] for dato in robot.sesion.interactuables_cerca()]
