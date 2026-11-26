"""Pruebas del movimiento: pasos, giros, choques, puertas, modos, escaleras y ascensor."""

from __future__ import annotations

import math

import pytest

from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio.modelo import Posicion
from app.motor import eventos as ev
from app.motor.movimiento import mover_circulo
from app.motor.mundo import Mundo
from tests.test_motor_comun import Robot, registros, sala_de_pruebas, sonidos, texto, vibraciones, voces

# ── Vivienda: de habitación en habitación ────────────────────────────────────


def test_recorre_la_vivienda_abriendo_puertas():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno)
	planta = entorno.plantas[0]
	assert robot.espacio == "Entrada"
	assert "Entrada." in voces(robot.eventos)
	for nombre in ("Salón", "Cocina", "Dormitorio", "Baño"):
		espacio = next(e for e in planta.espacios if e.nombre == nombre)
		centro = espacio.centro()
		robot.seguir((planta.id, centro[0], centro[1]))
		assert robot.espacio == nombre, f"no ha llegado a {nombre}: está en {robot.pos}"
	entradas = [d["nombre"] for d in registros(robot.eventos, "entrada_espacio")]
	assert set(entradas) == {"Entrada", "Pasillo", "Salón", "Cocina", "Dormitorio", "Baño"}
	# El dormitorio y el baño tenían la puerta cerrada: ha tenido que abrirlas.
	abiertas = [d["nombre"] for d in registros(robot.eventos, "puerta") if d["accion"] == "abrir"]
	assert any("Dormitorio" in nombre for nombre in abiertas)
	assert any("Baño" in nombre for nombre in abiertas)
	assert "puerta/abrir" in sonidos(robot.eventos)
	assert len(robot.sesion.resumen()["espacios_visitados"]) == 6
	# El modelo del profesional no se ha tocado: las puertas siguen como él las dejó.
	assert next(a for a in planta.aberturas if "Dormitorio" in a.nombre and a.tipo == "puerta").estado == "cerrada"


def test_un_paso_virtual_es_un_paso_real_y_alterna_los_pies():
	robot = Robot(ejemplos.vivienda_ejemplo(), paso_m=0.6)
	antes = robot.pos
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar")
	assert robot.pos[0] == pytest.approx(antes[0] + 1.2)
	pasos = [e for e in nuevos if isinstance(e, ev.EvSonido) and e.bus == "pasos"]
	assert len(pasos) == 2
	assert "_izq_" in pasos[0].nombre and "_der_" in pasos[1].nombre
	assert pasos[0].relativo[0] < 0 < pasos[1].relativo[0]
	# Entrada con baldosa, pasillo con madera: el segundo paso ya suena a madera.
	assert pasos[0].nombre.startswith("pasos/baldosa") or pasos[0].nombre.startswith("pasos/madera")
	assert robot.sesion.movimiento.distancia == pytest.approx(1.2)


def test_choca_con_la_pared_suena_el_material_en_el_punto_y_vibra():
	robot = Robot(ejemplos.vivienda_ejemplo())
	robot.girar_a(0.0)
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar") + robot.pulsar("avanzar")
	choques = registros(nuevos, "choque")
	assert choques and choques[0]["clase"] == "pared" and choques[0]["material"] == "ladrillo"
	golpe = next(e for e in nuevos if isinstance(e, ev.EvSonido) and e.nombre == "golpe/ladrillo")
	# La entrada llega hasta y = 5,7: el golpe suena ahí, en la pared, no en el alumno.
	assert golpe.pos[1] == pytest.approx(5.7, abs=0.01)
	assert golpe.pos[0] == pytest.approx(robot.pos[0], abs=0.01)
	assert "choque" in vibraciones(nuevos)
	assert "Pared." in voces(nuevos)
	# No atraviesa: se queda a un radio de la pared.
	assert robot.pos[1] == pytest.approx(5.7 - 0.25, abs=0.01)
	assert robot.sesion.movimiento.choques >= 1


def test_el_detalle_cero_no_habla_al_chocar():
	robot = Robot(ejemplos.vivienda_ejemplo(), detalle=0)
	robot.girar_a(0.0)
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar") + robot.pulsar("avanzar")
	assert "golpe/ladrillo" in sonidos(nuevos)
	assert voces(nuevos) == []


def test_puerta_cerrada_para_y_al_interactuar_se_abre_y_se_cierra():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno, inicio=Posicion(entorno.plantas[0].id, 3.0, 4.6, 0.0))
	nuevos = robot.pulsar("avanzar")
	assert "Puerta entre Dormitorio y Pasillo, cerrada." in voces(nuevos)
	assert robot.espacio == "Pasillo"
	nuevos = robot.pulsar("interactuar")
	assert "puerta/abrir" in sonidos(nuevos)
	assert "abierta" in texto(nuevos)
	robot.pulsar("avanzar")
	robot.pulsar("avanzar")
	assert robot.espacio == "Dormitorio"
	# Se da la vuelta y la cierra desde dentro.
	robot.pulsar("media_vuelta")
	nuevos = robot.pulsar("interactuar")
	assert "puerta/cerrar" in sonidos(nuevos)
	robot.pulsar("avanzar")
	assert robot.espacio == "Dormitorio"


def test_puerta_con_llave_suena_y_lo_dice():
	entorno = ejemplos.vivienda_ejemplo()
	planta = entorno.plantas[0]
	next(a for a in planta.aberturas if "Dormitorio" in a.nombre and a.tipo == "puerta").estado = "con_llave"
	robot = Robot(entorno, inicio=Posicion(planta.id, 3.0, 4.6, 0.0))
	nuevos = robot.pulsar("interactuar")
	assert "puerta/con_llave" in sonidos(nuevos)
	assert "cerrada con llave" in texto(nuevos)
	robot.pulsar("avanzar")
	robot.pulsar("avanzar")
	assert robot.espacio == "Pasillo"


def test_sin_nada_que_usar_lo_dice():
	robot = Robot(ejemplos.vivienda_ejemplo(), inicio=Posicion("pla-1", 2.0, 2.0, 0.0))
	assert "No hay nada que usar aquí." in voces(robot.pulsar("interactuar"))


def test_cambio_de_suelo_se_anuncia_y_cambia_el_sonido_de_los_pasos():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno, inicio=Posicion("pla-1", 0.6, 1.8, 90.0))
	nuevos = robot.pulsar("avanzar")
	assert any(nombre.startswith("pasos/alfombra") for nombre in sonidos(nuevos))
	assert registros(nuevos, "cambio_suelo")[0]["suelo"] == "alfombra"
	nuevos += robot.tic(40)
	assert "Alfombra del salón." in voces(nuevos)


def test_salir_por_la_puerta_de_la_calle_se_registra_y_no_se_puede_ir_mas_alla():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno, inicio=Posicion("pla-1", -1.4, 4.6, 270.0))
	robot.pulsar("interactuar")
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar")
	salida = registros(nuevos, "salida")
	assert salida and salida[0]["es_salida"] is True
	assert "Has salido por Puerta de la calle." in voces(nuevos)
	for _i in range(4):
		nuevos = robot.pulsar("avanzar")
	assert "interfaz/borde" in sonidos(nuevos)
	assert robot.pos[0] > -3.3


# ── Objetos: chocar y esquivar ───────────────────────────────────────────────


def test_choca_con_un_objeto_y_lo_esquiva(tmp_path):
	entorno, _planta, catalogo, objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	# La mesa (1,2 × 0,8) está en (4, 3): andando al este desde (1, 3) se la encuentra.
	nuevos: list = []
	for _i in range(5):
		nuevos += robot.pulsar("avanzar")
	choque = registros(nuevos, "choque")
	assert choque and choque[0]["con"] == "Mesa" and choque[0]["clase"] == "objeto"
	assert "Mesa." in voces(nuevos)
	assert "golpe/madera" in sonidos(nuevos)
	assert robot.pos[0] == pytest.approx(3.4 - 0.25, abs=0.02)
	assert objetos["mesa"].id in robot.sesion.percepcion.objetos
	# La rodea por el sur y sigue: acaba al otro lado sin haberla atravesado.
	robot.ir_a(3.0, 2.0)
	robot.ir_a(5.2, 2.0)
	robot.ir_a(5.5, 3.0)
	assert robot.pos == pytest.approx((5.5, 3.0), abs=0.05)


def test_resbala_por_la_esquina_de_un_objeto(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	# Rozando la esquina suroeste de la mesa (3,4; 2,6): pasa, desviado hacia el sur, con roce y sin golpe.
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", 2.6, 2.45, 90.0))
	nuevos: list = []
	for _i in range(3):
		nuevos += robot.pulsar("avanzar")
	assert robot.pos[0] > 3.6
	assert robot.pos[1] < 2.36
	assert not registros(nuevos, "choque")
	assert "roce/madera" in sonidos(nuevos)
	assert "pared_izquierda" in vibraciones(nuevos)


def test_objeto_en_voladizo_se_choca_pero_la_lampara_alta_no(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	# La pizarra (2, 5) tiene la base a 90 cm: se choca con ella.
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", 2.0, 4.0, 0.0))
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar")
	assert registros(nuevos, "choque")[0]["con"] == "Pizarra"
	# La lámpara (2, 1) cuelga a 1,90: se pasa por debajo.
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", 2.0, 2.5, 180.0))
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar") + robot.pulsar("avanzar")
	assert not [d for d in registros(nuevos, "choque") if d["con"] != "Pared"]
	assert robot.pos[1] < 0.6


def test_la_alfombra_no_corta_el_paso(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", 5.0, 1.5, 90.0))
	for _i in range(3):
		robot.pulsar("avanzar")
	assert robot.pos[0] == pytest.approx(7.1, abs=0.01)


def test_usar_un_objeto_con_acciones_cambia_su_estado(tmp_path):
	entorno, _planta, catalogo, objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", 6.6, 0.6, 90.0))
	armario = objetos["armario"]
	assert robot.sesion.mundo.estado_objeto(armario.id) == "cerrado"
	nuevos = robot.pulsar("interactuar")
	assert robot.sesion.mundo.estado_objeto(armario.id) == "abierto"
	assert "Abrir: Armario." in voces(nuevos)
	assert registros(nuevos, "interaccion")[0]["accion"] == "abrir"
	robot.pulsar("interactuar")
	assert robot.sesion.mundo.estado_objeto(armario.id) == "cerrado"
	# El objeto del profesional no cambia.
	assert armario.estado == "cerrado"


def test_el_circulo_no_atraviesa_paredes_ni_a_grandes_pasos():
	mundo = Mundo(ejemplos.vivienda_ejemplo())
	resultado = mover_circulo(mundo, "pla-1", 1.0, 4.6, 0.0, 5.0, 0.25)
	assert resultado.y == pytest.approx(5.2 - 0.25, abs=0.01)
	assert resultado.contacto is not None and resultado.contacto.clase == "pared"
	# En diagonal contra la pared norte del pasillo: resbala hacia el este.
	resultado = mover_circulo(mundo, "pla-1", 1.0, 4.6, 1.0, 1.0, 0.25)
	assert resultado.y == pytest.approx(4.95, abs=0.01)
	assert resultado.x > 1.9


# ── Modos de movimiento ──────────────────────────────────────────────────────


def test_modo_continuo_anda_a_velocidad_de_paseo_mientras_se_mantiene():
	robot = Robot(ejemplos.vivienda_ejemplo(), modo_movimiento="continuo", velocidad_ms=1.0, inicio=Posicion("pla-1", 0.5, 4.6, 90.0))
	robot.sesion.orden("avanzar")
	nuevos = robot.esperar(2.0)
	assert robot.pos[0] == pytest.approx(2.5, abs=0.06)
	assert len([n for n in sonidos(nuevos) if n.startswith("pasos/")]) in (2, 3)
	robot.sesion.orden("avanzar", 0)
	robot.esperar(1.0)
	assert robot.pos[0] == pytest.approx(2.5, abs=0.06)


def test_modo_continuo_con_palanca_y_giro_libre():
	robot = Robot(ejemplos.vivienda_ejemplo(), modo_movimiento="continuo", velocidad_ms=1.0, inicio=Posicion("pla-1", 0.5, 4.6, 90.0))
	robot.sesion.analogico(0.5, 0.0, 0.0, None)
	robot.esperar(2.0)
	assert robot.pos[0] == pytest.approx(1.5, abs=0.06)
	robot.sesion.analogico(0.0, 0.0, 1.0, None)
	robot.esperar(1.0)
	assert robot.sesion.jugador.rumbo == pytest.approx(180.0, abs=1.0)
	robot.sesion.analogico(0.0, 0.0, 0.0, None)
	assert "Sur." in voces(robot.esperar(0.2))


def test_mantener_en_modo_pasos_repite_al_ritmo_de_paseo():
	robot = Robot(ejemplos.vivienda_ejemplo(), paso_m=0.6, velocidad_ms=1.2, inicio=Posicion("pla-1", 0.5, 4.6, 90.0))
	robot.sesion.orden("avanzar")
	robot.esperar(1.7)
	robot.sesion.orden("avanzar", 0)
	robot.esperar(1.0)
	# Un paso al pulsar, otro a los 0,45 s y después uno cada medio segundo.
	assert robot.sesion.movimiento.pasos == 4


def test_modo_brujula_cada_direccion_es_un_punto_cardinal():
	robot = Robot(ejemplos.vivienda_ejemplo(), modo_movimiento="brujula", inicio=Posicion("pla-1", 2.0, 2.0, 37.0))
	robot.pulsar("girar_derecha")
	assert robot.sesion.jugador.rumbo == 90.0 and robot.pos == pytest.approx((2.7, 2.0))
	robot.pulsar("retroceder")
	assert robot.sesion.jugador.rumbo == 180.0 and robot.pos == pytest.approx((2.7, 1.3))
	robot.pulsar("girar_izquierda")
	robot.pulsar("avanzar")
	assert robot.sesion.jugador.rumbo == 0.0 and robot.pos == pytest.approx((2.0, 2.0))


def test_giros_de_noventa_cuarenta_y_cinco_y_media_vuelta():
	robot = Robot(ejemplos.vivienda_ejemplo())
	assert "Sur." in voces(robot.pulsar("girar_derecha"))
	robot.sesion.ajustes.giro_grados = 45
	assert "Sureste." in voces(robot.pulsar("girar_izquierda"))
	robot.pulsar("media_vuelta")
	assert robot.sesion.jugador.rumbo == 315.0
	# Paso lateral: se desplaza sin girarse.
	robot.girar_a(90.0)
	antes = robot.pos
	robot.pulsar("paso_izquierda")
	assert robot.sesion.jugador.rumbo == 90.0
	assert robot.pos == pytest.approx((antes[0], antes[1] + 0.42))
	robot.pulsar("retroceder")
	assert robot.pos[0] == pytest.approx(antes[0] - 0.7)


def test_modo_salas_salta_de_espacio_en_espacio():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno, modo_movimiento="salas")
	assert robot.espacio == "Entrada"
	nuevos = robot.pulsar("girar_derecha")
	dicho = texto(nuevos)
	assert "hacia" in dicho
	# Recorre las salidas de la entrada hasta dar con el pasillo y entra.
	for _i in range(4):
		if "hacia Pasillo" in dicho:
			break
		dicho = texto(robot.pulsar("girar_derecha"))
	assert "hacia Pasillo" in dicho
	robot.pulsar("avanzar")
	assert robot.espacio == "Pasillo"
	# Desde el pasillo, hasta el dormitorio (puerta cerrada: se abre sola al cruzar en este modo).
	for _i in range(8):
		if "hacia Dormitorio" in texto(robot.pulsar("girar_derecha")):
			break
	nuevos = robot.pulsar("avanzar")
	assert robot.espacio == "Dormitorio"
	assert "puerta/abrir" in sonidos(nuevos)
	robot.pulsar("retroceder")
	assert robot.espacio == "Pasillo"


def test_modo_aceras_avanza_hasta_la_siguiente_novedad():
	entorno = ejemplos.barrio_ejemplo()
	robot = Robot(entorno, modo_movimiento="aceras")
	inicio = robot.pos
	nuevos = robot.pulsar("avanzar", 40)
	# Sale de (-20; 4,5) hacia el este y se para al llegar a algo que anunciar, no a los 70 cm.
	assert robot.pos[0] - inicio[0] > 1.5
	assert "Has avanzado" in texto(nuevos)
	assert len([n for n in sonidos(nuevos) if n.startswith("pasos/")]) <= 3
	# Sigue de novedad en novedad y se para nada más bajar el bordillo de la Calle del Río (x = -3).
	nuevos = []
	for _i in range(6):
		nuevos += robot.pulsar("avanzar", 10)
		if "Acera" not in robot.espacio:
			break
	assert "Bordillo." in texto(nuevos + robot.tic(60))
	assert "exterior/bordillo" in sonidos(nuevos)
	assert robot.espacio == "Calzada de Calle del Río"
	assert -3.0 <= robot.pos[0] <= -2.3


# ── Escalera ─────────────────────────────────────────────────────────────────


def _robot_ante_la_escalera(**ajustes) -> Robot:
	entorno = ejemplos.centro_dos_plantas()
	return Robot(entorno, inicio=Posicion("pla-1", 9.2, 7.2, 0.0), **ajustes)


def test_sube_la_escalera_peldano_a_peldano_con_tono_ascendente():
	robot = _robot_ante_la_escalera()
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar")
	assert robot.sesion.jugador.modo == "conector"
	assert "Escalera principal, sube 18 peldaños. Pasamanos a los dos lados." in voces(nuevos)
	assert registros(nuevos, "conector")[0]["sentido"] == "sube"
	subida: list = []
	for _i in range(18):
		subida += robot.pulsar("avanzar")
		if robot.sesion.jugador.modo != "conector":
			break
	peldanos = [e for e in nuevos + subida if isinstance(e, ev.EvSonido) and e.nombre == "escalera/subir"]
	assert len(peldanos) == 18
	tonos = [e.tono for e in peldanos]
	assert tonos == sorted(tonos) and tonos[-1] > tonos[0] + 0.4
	assert vibraciones(subida).count("peldano") >= 17
	jugador = robot.sesion.jugador
	assert (jugador.planta, jugador.modo) == ("pla-2", "andando")
	assert robot.pos == pytest.approx((10.2, 8.6))
	assert jugador.rumbo == 180.0
	assert "Has llegado a Planta primera." in voces(subida)
	cambio = registros(subida, "cambio_planta")[0]
	assert (cambio["de"], cambio["a"], cambio["tipo"]) == ("pla-1", "pla-2", "escalera")
	# La altura del oyente sube con él.
	assert robot.sesion.oyente()[2] == pytest.approx(3.2 + 1.6)
	# Sale al pasillo de arriba rodeando la jamba, sin quedarse clavado en ella.
	for _i in range(3):
		robot.pulsar("avanzar")
	assert robot.espacio == "Pasillo de la planta primera"


def test_baja_la_escalera_con_tono_descendente():
	entorno = ejemplos.centro_dos_plantas()
	robot = Robot(entorno, inicio=Posicion("pla-2", 10.0, 7.2, 0.0))
	nuevos: list = []
	for _i in range(24):
		nuevos += robot.pulsar("avanzar")
		if robot.sesion.jugador.planta == "pla-1" and robot.sesion.jugador.modo == "andando":
			break
	assert "Escalera principal, baja 18 peldaños. Pasamanos a los dos lados." in voces(nuevos)
	peldanos = [e for e in nuevos if isinstance(e, ev.EvSonido) and e.nombre == "escalera/bajar"]
	assert len(peldanos) == 18
	assert [e.tono for e in peldanos] == sorted((e.tono for e in peldanos), reverse=True)
	assert robot.pos == pytest.approx((8.8, 8.6))
	assert robot.sesion.jugador.rumbo == 180.0
	assert "Has llegado a Planta baja." in voces(nuevos)


def test_se_puede_dar_la_vuelta_a_mitad_de_la_escalera():
	robot = _robot_ante_la_escalera()
	robot.pulsar("avanzar")
	robot.pulsar("avanzar")
	for _i in range(5):
		robot.pulsar("avanzar")
	assert robot.sesion.jugador.modo == "conector"
	assert 0.0 < robot.sesion.jugador.z_extra < 3.2
	nuevos = robot.pulsar("media_vuelta")
	assert "Ahora bajas" in texto(nuevos)
	bajada: list = []
	for _i in range(10):
		bajada += robot.pulsar("avanzar")
		if robot.sesion.jugador.modo == "andando":
			break
	jugador = robot.sesion.jugador
	assert (jugador.planta, jugador.modo) == ("pla-1", "andando")
	assert "Has vuelto a Planta baja." in voces(bajada)
	assert not registros(robot.eventos, "cambio_planta")
	assert "escalera/bajar" in sonidos(bajada)


def test_donde_estoy_en_la_escalera_y_escalera_en_modo_continuo():
	robot = _robot_ante_la_escalera(modo_movimiento="continuo")
	robot.sesion.orden("avanzar")
	robot.esperar(1.5)
	assert robot.sesion.jugador.modo == "conector"
	robot.sesion.orden("avanzar", 0)
	# Al entrar se suelta el avance: hay que volver a pedirlo, ya en la escalera.
	robot.sesion.orden("avanzar")
	robot.esperar(3.0)
	dicho = texto(robot.pulsar("donde_estoy"))
	assert "Estás en Escalera principal, subiendo. Llevas" in dicho
	robot.esperar(12.0)
	assert robot.sesion.jugador.planta == "pla-2" and robot.sesion.jugador.modo == "andando"


def test_rampa_y_escalera_mecanica():
	entorno = ed.crear_entorno("Dos niveles")
	baja = ed.crear_planta(entorno, "Planta baja", nivel=0, altura_m=0.0)
	alta = ed.crear_planta(entorno, "Entreplanta", nivel=1, altura_m=1.0)
	ed.crear_habitacion_rectangular(entorno, baja, "Vestíbulo", 0, 0, 10, 10)
	ed.crear_habitacion_rectangular(entorno, alta, "Sala alta", 0, 0, 10, 20)
	ed.crear_rampa(entorno, baja, alta, (2.0, 4.0), 0.0, 8.0, nombre="Rampa", pasamanos="derecha")
	ed.crear_escalera(entorno, baja, alta, (7.0, 4.0), 0.0, 6.0, 12, nombre="Escalera mecánica", tipo="escalera_mecanica")
	ed.fijar_inicio(entorno, baja, 2.0, 3.0, 0.0)
	robot = Robot(entorno, paso_m=0.8)
	nuevos = robot.pulsar("avanzar")
	assert "Rampa, sube 8 metros. Pasamanos a tu derecha." in voces(nuevos)
	for _i in range(10):
		nuevos += robot.pulsar("avanzar")
	assert sonidos(nuevos).count("escalera/rampa") == 10
	assert robot.sesion.jugador.planta == alta.id and robot.pos == pytest.approx((2.0, 12.0))
	# La mecánica sube sola: basta con entrar y esperar.
	robot.sesion.recolocar(Posicion(baja.id, 7.0, 3.5, 0.0))
	robot.pulsar("avanzar")
	assert robot.sesion.jugador.modo == "conector"
	robot.esperar(13.0)
	assert robot.sesion.jugador.planta == alta.id and robot.sesion.jugador.modo == "andando"
	# Por arriba no se puede entrar: viene de cara.
	robot.sesion.recolocar(Posicion(alta.id, 7.0, 10.5, 180.0))
	nuevos = robot.pulsar("avanzar")
	assert robot.sesion.jugador.modo == "andando"
	assert "escalera mecánica viene hacia ti" in texto(nuevos)


# ── Ascensor ─────────────────────────────────────────────────────────────────


def test_ascensor_llamar_entrar_elegir_planta_viajar_y_salir():
	entorno = ejemplos.centro_dos_plantas()
	robot = Robot(entorno, inicio=Posicion("pla-2", 12.0, 6.6, 0.0))
	# La cabina empieza en la planta baja: hay que esperarla.
	nuevos = robot.pulsar("interactuar")
	assert "ascensor/llamada" in sonidos(nuevos)
	assert "Ascensor llamado. Espera." in voces(nuevos)
	assert registros(nuevos, "ascensor")[0]["accion"] == "llamar"
	assert robot.sesion.movimiento.ascensores["con-50"].estado == "viniendo"
	# Mientras viene se oye la maquinaria tras la puerta, apagada.
	espera = next(f for f in robot.sesion.fuentes() if f.id == "ascensor-viene:con-50")
	assert espera.sonido == "ascensor/viaje" and espera.filtro > 0.5 and espera.pos[:2] == (12.0, 7.4)
	nuevos = robot.esperar(3.0)
	assert {"ascensor/llegada", "ascensor/puerta"} <= set(sonidos(nuevos))
	assert "El ascensor ha llegado" in texto(nuevos)
	nuevos = robot.pulsar("avanzar")
	assert robot.sesion.jugador.modo == "ascensor"
	assert "Estás dentro del ascensor" in texto(nuevos) and "Planta primera." in texto(nuevos)
	assert robot.sesion.fuentes() == []
	# Elige la planta baja y acepta.
	assert "Planta baja." in voces(robot.pulsar("girar_izquierda"))
	assert "interfaz/borde" in sonidos(robot.pulsar("girar_izquierda"))
	nuevos = robot.pulsar("interactuar")
	assert "Vas a Planta baja." in voces(nuevos)
	viaje = registros(nuevos, "ascensor")[0]
	assert viaje["accion"] == "viajar" and viaje["duracion"] == pytest.approx(4.5)
	assert [f.sonido for f in robot.sesion.fuentes()] == ["ascensor/viaje"]
	robot.esperar(2.0)
	assert robot.sesion.jugador.planta == "pla-2"
	nuevos = robot.esperar(4.0)
	assert robot.sesion.jugador.planta == "pla-1"
	assert {"ascensor/llegada", "ascensor/planta_0", "ascensor/puerta"} <= set(sonidos(nuevos))
	assert "Planta baja. Puerta abierta. Avanza para salir." in voces(nuevos)
	assert registros(nuevos, "cambio_planta")[0]["tipo"] == "ascensor"
	assert robot.sesion.fuentes() == [] or all(f.sonido != "ascensor/viaje" for f in robot.sesion.fuentes())
	robot.pulsar("avanzar")
	robot.pulsar("avanzar")
	jugador = robot.sesion.jugador
	assert jugador.modo == "andando" and jugador.rumbo == 180.0
	assert robot.espacio == "Pasillo de la planta baja"
	assert robot.pos[1] < 7.4


def test_ascensor_sin_aviso_hablado_no_dice_la_planta():
	entorno = ejemplos.centro_dos_plantas()
	next(c for c in entorno.conectores if c.tipo == "ascensor").datos["aviso_hablado"] = False
	robot = Robot(entorno, inicio=Posicion("pla-1", 12.0, 6.6, 0.0))
	robot.pulsar("interactuar")
	robot.esperar(1.5)
	robot.pulsar("avanzar")
	robot.pulsar("girar_derecha")
	robot.pulsar("interactuar")
	nuevos = robot.esperar(5.0)
	assert "El ascensor se ha parado. Puerta abierta. Avanza para salir." in voces(nuevos)
	assert "ascensor/planta_1" not in sonidos(nuevos)


def test_el_hueco_del_ascensor_es_macizo():
	robot = Robot(ejemplos.centro_dos_plantas(), inicio=Posicion("pla-1", 12.0, 7.4, 0.0))
	nuevos = robot.pulsar("avanzar")
	assert robot.pos[1] == pytest.approx(7.75, abs=0.01)
	assert registros(nuevos, "choque")
	assert math.isclose(robot.sesion.jugador.rumbo, 0.0)
