"""Pruebas de la acústica: oclusión, sonido que llega por la puerta, plantas y fuentes de la actividad."""

from __future__ import annotations

import math

import pytest

from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio.modelo import Posicion
from app.motor import eventos as ev
from tests.test_motor_comun import Robot, sala_de_pruebas


def _fuentes(robot: Robot) -> dict[str, ev.FuenteActiva]:
	return {fuente.id: fuente for fuente in robot.sesion.fuentes()}


def _id(entorno, nombre: str) -> str:
	for planta in entorno.plantas:
		for fuente in planta.fuentes:
			if fuente.nombre == nombre:
				return fuente.id
	raise AssertionError(nombre)


def test_fuente_a_la_vista_suena_en_su_sitio_sin_filtro():
	entorno = ejemplos.vivienda_ejemplo()
	reloj = _id(entorno, "Reloj de pared")
	robot = Robot(entorno, inicio=Posicion("pla-1", 1.0, 2.0, 0.0))
	fuente = _fuentes(robot)[reloj]
	assert fuente.sonido == "fuente/reloj"
	# En su sitio (0,3; 2,0) y a su altura (1,8 m). El volumen es el suyo: la distancia la pone la capa de sonido.
	assert fuente.pos == pytest.approx((0.3, 2.0, 1.8))
	assert fuente.volumen == pytest.approx(0.4)
	assert fuente.filtro == 0.0
	assert fuente.bucle and fuente.bus == "ambiente"


def test_sin_linea_directa_el_sonido_llega_por_la_puerta():
	entorno = ejemplos.vivienda_ejemplo()
	reloj = _id(entorno, "Reloj de pared")
	puerta = next(a for a in entorno.plantas[0].aberturas if "Salón" in a.nombre and a.tipo == "puerta")
	# En el pasillo, pasada la puerta del salón: entre el reloj y el alumno está el tabique.
	robot = Robot(entorno, inicio=Posicion("pla-1", 4.0, 4.6, 90.0))
	assert robot.sesion.mundo.atenuacion("pla-1", (4.0, 4.6), (0.3, 2.0))[0] == 1
	fuente = _fuentes(robot)[reloj]
	centro = puerta.centro()
	# Se oye desde la puerta abierta del salón, no desde donde está el reloj.
	assert fuente.pos[:2] == pytest.approx(centro)
	assert fuente.filtro == pytest.approx(0.15)
	# El volumen corresponde al camino entero (alumno → puerta → reloj), no al tramo hasta la puerta.
	hasta_puerta = math.hypot(centro[0] - 4.0, centro[1] - 4.6)
	camino = hasta_puerta + math.hypot(centro[0] - 0.3, centro[1] - 2.0)
	assert camino < 5.0
	assert fuente.volumen == pytest.approx(0.4 * (hasta_puerta / camino) * (5.0 - camino) / 1.25, rel=0.01)
	# Más lejos por el pasillo el camino pasa de su radio (5 m): deja de oírse, aunque en línea recta esté cerca.
	robot = Robot(entorno, inicio=Posicion("pla-1", 5.0, 4.6, 90.0))
	assert reloj not in _fuentes(robot)


def test_puerta_cerrada_atenua_mas_que_abierta():
	entorno = ejemplos.vivienda_ejemplo()
	planta = entorno.plantas[0]
	radio = ed.anadir_fuente(entorno, planta, "Radio", 2.0, 7.0, "television", volumen=1.0, radio=12.0)
	puerta = next(a for a in planta.aberturas if "Dormitorio" in a.nombre and a.tipo == "puerta")
	# Justo delante de la puerta del dormitorio: la radio queda en línea recta, con la hoja en medio.
	robot = Robot(entorno, inicio=Posicion("pla-1", 3.0, 4.6, 0.0))
	cerrada = _fuentes(robot)[radio.id]
	assert cerrada.pos[:2] == pytest.approx((2.0, 7.0))
	assert cerrada.filtro == pytest.approx(0.6) and cerrada.volumen == pytest.approx(0.58)
	robot.pulsar("interactuar")
	abierta = _fuentes(robot)[radio.id]
	assert abierta.filtro == 0.0 and abierta.volumen == pytest.approx(1.0)
	# Desde el fondo del pasillo no hay línea recta: llega por esa puerta, y cerrada llega menos y más apagada.
	robot = Robot(entorno, inicio=Posicion("pla-1", 6.5, 4.6, 0.0))
	por_cerrada = _fuentes(robot)[radio.id]
	assert por_cerrada.pos[:2] == pytest.approx(puerta.centro())
	robot.sesion.mundo.poner_abertura(puerta.id, "abierta")
	por_abierta = _fuentes(robot)[radio.id]
	assert por_abierta.pos[:2] == pytest.approx(puerta.centro())
	assert por_cerrada.volumen == pytest.approx(por_abierta.volumen * 0.5, rel=0.01)
	assert por_cerrada.filtro == pytest.approx(por_abierta.filtro + 0.45)


def test_a_traves_de_un_tabique_llega_muy_apagado_y_tras_dos_casi_nada():
	entorno = ed.crear_entorno("Tres cuartos")
	planta = ed.crear_planta(entorno, "Planta")
	a = ed.crear_habitacion_rectangular(entorno, planta, "A", 0, 0, 3, 3)
	b = ed.crear_habitacion_adosada(entorno, planta, "B", a, "este", 3, 3)
	c = ed.crear_habitacion_adosada(entorno, planta, "C", b, "este", 3, 3)
	# Cada cuarto con su puerta a la calle (al sur), sin puertas entre ellos: el sonido solo puede atravesar.
	for cuarto in (a, b, c):
		ed.anadir_puerta(entorno, planta, cuarto, "sur", ancho=0.8, estado="cerrada", material="metal")
	fuente = ed.anadir_fuente(entorno, planta, "Zumbido", 1.5, 1.5, "ventilador", volumen=1.0, radio=20.0)
	robot = Robot(entorno, inicio=Posicion(planta.id, 4.5, 1.5, 0.0))
	al_lado = _fuentes(robot)[fuente.id]
	assert al_lado.pos[:2] == pytest.approx((1.5, 1.5))
	assert al_lado.filtro == pytest.approx(0.85)
	assert al_lado.volumen == pytest.approx(0.28, rel=0.05)
	robot = Robot(entorno, inicio=Posicion(planta.id, 7.5, 1.5, 0.0))
	dos = _fuentes(robot).get(fuente.id)
	assert dos is not None and dos.volumen < al_lado.volumen * 0.5 and dos.filtro > al_lado.filtro


def test_de_otra_planta_solo_llega_por_el_hueco_de_la_escalera():
	entorno = ejemplos.centro_dos_plantas()
	baja, primera = entorno.plantas
	campana = ed.anadir_fuente(entorno, primera, "Campana", 10.2, 7.0, "campanas", volumen=1.0, radio=30.0)
	reloj_arriba = _id(entorno, "Reloj del pasillo")
	robot = Robot(entorno, inicio=Posicion(baja.id, 9.5, 7.0, 0.0))
	fuentes = _fuentes(robot)
	llega = fuentes[campana.id]
	# Se oye desde la boca de la escalera de esta planta, a la altura de esta planta, y apagada.
	assert llega.pos[:2] == pytest.approx((8.8, 8.6))
	assert llega.pos[2] == pytest.approx(1.0)
	assert llega.filtro >= 0.25
	assert 0.02 < llega.volumen < 0.3
	# El reloj de arriba (radio 6 m) no llega: solo la escalera ya mide 6.
	assert reloj_arriba not in fuentes
	# En la misma planta que la campana se oye mucho más.
	arriba = Robot(entorno, inicio=Posicion(primera.id, 9.5, 7.0, 0.0))
	assert _fuentes(arriba)[campana.id].volumen > llega.volumen * 3


def test_objeto_con_sonido_propio(tmp_path):
	entorno, _planta, catalogo, objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", 6.0, 5.0, 90.0))
	fuente = _fuentes(robot)[f"obj-son:{objetos['frigorifico'].id}"]
	assert fuente.sonido == "fuente/frigorifico"
	assert fuente.volumen == pytest.approx(0.5)
	assert fuente.pos[:2] == pytest.approx((7.6, 5.6))
	# A más de su radio (6 m) no se oye.
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", 1.0, 1.0, 90.0))
	assert f"obj-son:{objetos['frigorifico'].id}" not in _fuentes(robot)


def test_la_acustica_cambia_con_el_espacio():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno)
	bano = next(e for e in entorno.plantas[0].espacios if e.nombre == "Baño").centro()
	robot.seguir(("pla-1", bano[0], bano[1]))
	presets = [e.preset for e in robot.eventos if isinstance(e, ev.EvAcustica)]
	# Entrada (habitación), pasillo y baño; no se repite mientras no cambie.
	assert presets == ["habitacion", "pasillo", "bano"]


def test_fuentes_de_la_actividad_y_fuentes_a_intervalos():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno)
	sesion = robot.sesion
	sesion.anadir_fuente("premio-1", "premio/cerca", ("pla-1", 0.5, 4.6), volumen=0.8, radio=6.0, bus="ayudas")
	premio = _fuentes(robot)["premio-1"]
	assert premio.sonido == "premio/cerca" and premio.bus == "ayudas" and premio.volumen == pytest.approx(0.8)
	# Moverla es volver a añadirla con el mismo id; quitarla, que deje de listarse.
	sesion.anadir_fuente("premio-1", "premio/cerca", Posicion("pla-1", 6.0, 2.0, 0.0), radio=6.0)
	assert "premio-1" not in _fuentes(robot)
	sesion.anadir_fuente("premio-1", "premio/cerca", ("pla-1", 0.5, 4.6), radio=6.0)
	assert sesion.quitar_fuente("premio-1") and not sesion.quitar_fuente("premio-1")
	assert "premio-1" not in _fuentes(robot)
	# Un sonido que se repite cada 2 s no es una fuente continua: llega como eventos, ya con su oclusión.
	sesion.anadir_fuente("pajaro", "pajaros", ("pla-1", 0.5, 4.6), bucle=False, intervalo=2.0, radio=10.0)
	assert "pajaro" not in _fuentes(robot)
	cantos = [e for e in robot.esperar(6.5) if isinstance(e, ev.EvSonido) and e.nombre == "fuente/pajaros"]
	assert len(cantos) == 3
	assert cantos[0].pos[:2] == pytest.approx((0.5, 4.6))
	# Una fuente sin oclusión (una guía que se oye siempre) atraviesa las paredes.
	sesion.anadir_fuente("guia", "baliza/pulso", ("pla-1", 6.0, 2.0), radio=30.0, ocluir=False)
	guia = _fuentes(robot)["guia"]
	assert guia.filtro == 0.0 and guia.pos[:2] == pytest.approx((6.0, 2.0))


def test_en_pausa_y_dentro_del_ascensor_no_hay_fuentes():
	robot = Robot(ejemplos.vivienda_ejemplo(), inicio=Posicion("pla-1", 1.0, 2.0, 0.0))
	assert robot.sesion.fuentes()
	robot.sesion.pausar(True)
	assert robot.sesion.fuentes() == []


def test_el_presentador_aplica_los_eventos_y_las_fuentes_del_motor():
	from app.audio.motor_nulo import MotorNulo
	from app.audio.presentador import Presentador
	from app.audio.voz import VozFalsa

	motor = MotorNulo()
	motor.iniciar(None, {})
	voz = VozFalsa()
	presentador = Presentador(motor, voz)
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno, inicio=Posicion("pla-1", 1.0, 2.0, 0.0))
	sesion = robot.sesion
	presentador.aplicar(robot.eventos, sesion, 0.05)
	sesion.orden("avanzar")
	sesion.orden("donde_estoy")
	for _i in range(5):
		presentador.aplicar(sesion.avanzar(0.05), sesion, 0.05)
	sonando = presentador.fuentes_sonando()
	assert _id(entorno, "Reloj de pared") in sonando
	nombres = [llamada["nombre"] for llamada in motor.de("reproducir")]
	assert "fuente/reloj" in nombres and any(nombre.startswith("pasos/") for nombre in nombres)
	assert motor.de("acustica")[0]["preset"] == "habitacion"
	assert any("Estás en Salón" in texto for texto, _canal, _interrumpir in voz.registro)
	assert motor.de("oyente")[-1]["z"] == pytest.approx(1.6)
