"""Pruebas de la dinámica: semáforos, tráfico, cruces de calzada, puertas automáticas y objetos con fases."""

from __future__ import annotations

import pytest

from app.dominio import ejemplos
from app.dominio.modelo import Posicion
from app.motor import eventos as ev
from tests.test_motor_comun import Robot, registros, sala_de_pruebas, sonidos, texto, vibraciones, voces

PASO = "esp-15"  # Paso con semáforo de Calle Mayor, en x de -10 a -6


def _barrio(**ajustes) -> Robot:
	ajustes.setdefault("trafico", True)
	ajustes.setdefault("semilla", 11)
	semilla = ajustes.pop("semilla")
	return Robot(ejemplos.barrio_ejemplo(), semilla=semilla, **ajustes)


def _via(robot: Robot, nombre: str):
	return next(v for v in robot.sesion.entorno.plantas[0].vias if v.nombre == nombre)


def test_el_semaforo_recorre_sus_fases_con_los_tiempos_del_ciclo():
	robot = _barrio(trafico=False)
	semaforo = robot.sesion.dinamica.semaforo_de(PASO)
	assert semaforo.duraciones == (25.0, 5.0, 45.0) and semaforo.ciclo == 75.0
	semaforo.t = 0.0
	assert semaforo.fase == "verde" and not semaforo.pasan_coches
	robot.esperar(25.5)
	assert robot.sesion.dinamica.fase(PASO) == "intermitente"
	robot.esperar(5.0)
	assert semaforo.fase == "rojo" and semaforo.pasan_coches
	assert semaforo.restante == pytest.approx(44.5, abs=0.2)
	robot.esperar(45.0)
	assert semaforo.fase == "verde"
	assert robot.sesion.dinamica.fase("no-existe") == ""


def test_el_semaforo_sonoro_suena_distinto_en_cada_fase():
	robot = _barrio(trafico=False, inicio=Posicion("pla-1", -8.5, 4.5, 180.0))
	semaforo = robot.sesion.dinamica.semaforo_de(PASO)
	semaforo.t = 0.0
	fuentes = {f.id: f for f in robot.sesion.fuentes()}
	# Un poste a cada lado del paso; el cercano suena en su sitio.
	assert fuentes[f"sem:{PASO}:0"].sonido == "semaforo/verde" and fuentes[f"sem:{PASO}:1"].sonido == "semaforo/verde"
	assert fuentes[f"sem:{PASO}:0"].pos[:2] == pytest.approx((-8.0, 3.8), abs=0.01)
	nuevos = robot.esperar(25.5)
	assert {f.sonido for f in robot.sesion.fuentes() if f.id.startswith("sem:")} == {"semaforo/intermitente"}
	assert "El verde se acaba." in voces(nuevos)
	nuevos = robot.esperar(5.0)
	rojo = {f.id: f for f in robot.sesion.fuentes() if f.id.startswith("sem:")}
	# En rojo suena más flojo y llega menos lejos: el poste de enfrente (a 8 m) ya casi no se oye.
	assert rojo[f"sem:{PASO}:0"].sonido == "semaforo/rojo"
	assert rojo[f"sem:{PASO}:0"].volumen < fuentes[f"sem:{PASO}:0"].volumen
	assert "Semáforo en rojo para peatones." in voces(nuevos)


def test_el_pulsador_acorta_la_espera():
	robot = _barrio(trafico=False, inicio=Posicion("pla-1", -8.3, 4.3, 180.0))
	semaforo = robot.sesion.dinamica.semaforo_de(PASO)
	semaforo.t = 31.0
	assert semaforo.fase == "rojo" and semaforo.restante == pytest.approx(44.0)
	assert robot.sesion.interactuables_cerca()[0]["clase"] == "pulsador"
	nuevos = robot.pulsar("interactuar")
	assert "semaforo/pulsador" in sonidos(nuevos)
	assert "Pulsador. Espera a que se ponga en verde." in voces(nuevos)
	assert registros(nuevos, "pulsador")[0]["fase"] == "rojo"
	assert semaforo.restante <= 4.0
	nuevos = robot.esperar(4.5)
	assert semaforo.fase == "verde"
	assert "Semáforo en verde para peatones." in voces(nuevos)
	assert "Ya está en verde" in texto(robot.pulsar("interactuar"))


def test_el_trafico_circula_por_las_vias_y_es_reproducible():
	robot = _barrio()
	robot.esperar(10.0)
	dinamica = robot.sesion.dinamica
	assert dinamica.vehiculos
	mayor, rio = _via(robot, "Calle Mayor"), _via(robot, "Calle del Río")
	for vehiculo in dinamica.vehiculos:
		if vehiculo.via is mayor:
			# Doble sentido: cada uno por su derecha (al este por el carril sur, al oeste por el norte).
			assert vehiculo.y == pytest.approx(-1.75 if vehiculo.sentido > 0 else 1.75)
			assert vehiculo.rumbo == pytest.approx(90.0 if vehiculo.sentido > 0 else 270.0)
		else:
			# Sentido único hacia el norte, por el centro.
			assert vehiculo.via is rio and vehiculo.sentido == 1
			assert vehiculo.x == pytest.approx(0.0) and vehiculo.rumbo == pytest.approx(0.0)
	fuentes = {f.id: f for f in robot.sesion.fuentes()}
	assert any(ident.startswith("veh-") for ident in fuentes)
	assert fuentes[f"trafico:{mayor.id}"].sonido == "trafico/ambiente_medio"
	assert fuentes[f"trafico:{rio.id}"].sonido == "trafico/ambiente_leve"
	# El rumor de la calle suena desde el punto de la calzada más cercano al alumno.
	assert fuentes[f"trafico:{mayor.id}"].pos[:2] == pytest.approx((robot.pos[0], 0.0))
	# Misma semilla, mismo tráfico; otra semilla, otro.
	otro = _barrio()
	otro.esperar(10.0)
	assert [(v.id, round(v.x, 3), round(v.y, 3)) for v in otro.sesion.dinamica.vehiculos] == [
		(v.id, round(v.x, 3), round(v.y, 3)) for v in dinamica.vehiculos
	]
	distinto = _barrio(semilla=12)
	distinto.esperar(10.0)
	assert [(round(v.x, 3)) for v in distinto.sesion.dinamica.vehiculos] != [(round(v.x, 3)) for v in dinamica.vehiculos]
	# Sin tráfico en los ajustes no hay vehículos ni rumor.
	callado = _barrio(trafico=False)
	callado.esperar(5.0)
	assert not [f for f in callado.sesion.fuentes() if f.id.startswith(("veh-", "trafico:"))]


def test_los_vehiculos_paran_con_el_verde_de_peatones():
	robot = _barrio()
	dinamica = robot.sesion.dinamica
	semaforo = dinamica.semaforo_de(PASO)
	mayor = _via(robot, "Calle Mayor")
	semaforo.t = 0.0
	robot.esperar(6.0)
	# Pasados unos segundos de verde para peatones, nadie se mueve dentro del paso…
	for _i in range(18):
		robot.esperar(1.0)
		dentro = [v for v in dinamica.vehiculos if v.via is mayor and -10.0 < v.x < -6.0 and v.v > 0.5]
		assert not dentro, f"vehículo cruzando el paso en verde de peatones: {dentro}"
	# …y hay alguno parado esperando ante él.
	assert [v for v in dinamica.vehiculos if v.via is mayor and v.v < 0.1]
	# Con el rojo de peatones vuelven a pasar.
	semaforo.t = 31.0
	han_pasado = False
	for _i in range(20):
		robot.esperar(0.5)
		han_pasado = han_pasado or any(v.via is mayor and -10.0 < v.x < -6.0 and v.v > 2.0 for v in dinamica.vehiculos)
	assert han_pasado


def test_cruzar_en_verde_es_seguro():
	robot = _barrio(inicio=Posicion("pla-1", -8.0, 4.3, 180.0))
	robot.sesion.dinamica.semaforo_de(PASO).t = 0.0
	robot.esperar(6.0)
	for _i in range(13):
		robot.pulsar("avanzar")
	assert "Acera sur" in robot.espacio
	assert registros(robot.eventos, "cruce_empieza")[0]["por_paso"] is True
	cruce = registros(robot.eventos, "cruce")[0]
	assert cruce["seguro"] is True and cruce["por_paso"] is True and cruce["fase"] == "verde" and cruce["paso"] == PASO
	assert not registros(robot.eventos, "cruce_inseguro")
	assert "exterior/bordillo" in sonidos(robot.eventos)
	assert "Bordillo." in texto(robot.eventos)


def test_cruzar_con_coches_pasando_avisa_pero_no_termina_la_partida():
	robot = _barrio(inicio=Posicion("pla-1", -8.0, 3.9, 180.0))
	dinamica = robot.sesion.dinamica
	dinamica.semaforo_de(PASO).t = 31.0
	mayor = _via(robot, "Calle Mayor")
	# Un solo coche, hacia el oeste por el carril norte, a 14 m del paso y a su velocidad.
	dinamica.vehiculos.clear()
	coche = dinamica._nuevo_vehiculo(mayor, -1, 34.0)
	dinamica.vehiculos.append(coche)
	assert coche.x == pytest.approx(6.0) and coche.v > 6.0
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar") + robot.tic(4)
	assert robot.espacio == "Paso con semáforo de Calle Mayor"
	assert "Estás cruzando en rojo." in voces(nuevos)
	aviso = registros(nuevos, "cruce_inseguro")
	assert aviso and aviso[0]["fase"] == "rojo" and aviso[0]["paso"] == PASO
	assert "Has cruzado con coches pasando." in voces(nuevos)
	assert "aviso" in vibraciones(nuevos)
	hablado = next(e for e in nuevos if isinstance(e, ev.EvVoz) and "coches pasando" in e.texto)
	assert hablado.canal == "aviso"
	# El coche frena y se queda antes del alumno: no hay atropello ni fin de partida.
	robot.esperar(4.0)
	assert coche.v == 0.0 and coche.x > robot.pos[0] + 2.0
	assert not robot.sesion.terminado
	assert not [e for e in robot.eventos if isinstance(e, ev.EvFin)]
	# Solo se avisa una vez por cruce, y al llegar a la otra acera queda registrado como inseguro.
	for _i in range(12):
		robot.pulsar("avanzar")
	assert len(registros(robot.eventos, "cruce_inseguro")) == 1
	cruce = registros(robot.eventos, "cruce")[0]
	assert cruce["seguro"] is False and cruce["en_rojo"] is True


def test_en_un_paso_sin_semaforo_los_coches_ceden_el_paso():
	# Paso sin semáforo de la Calle del Río (x de -3 a 3, y de 7 a 11); la calle es de sentido único hacia el norte.
	robot = _barrio(inicio=Posicion("pla-1", -3.4, 9.0, 90.0))
	dinamica = robot.sesion.dinamica
	rio = _via(robot, "Calle del Río")
	dinamica.vehiculos.clear()
	coche = dinamica._nuevo_vehiculo(rio, 1, 15.0)
	dinamica.vehiculos.append(coche)
	assert coche.y == pytest.approx(-15.0)
	robot.pulsar("avanzar")
	robot.pulsar("avanzar")
	assert robot.espacio == "Paso sin semáforo de Calle del Río"
	robot.esperar(8.0)
	# Se ha parado antes del paso, con tiempo: no es un cruce inseguro.
	assert coche.v == 0.0 and coche.y < 7.0
	assert not registros(robot.eventos, "cruce_inseguro")
	for _i in range(9):
		robot.pulsar("avanzar")
	cruce = registros(robot.eventos, "cruce")[0]
	assert cruce["seguro"] is True and cruce["por_paso"] is True and cruce["fase"] == ""
	# Con el paso libre, sigue su camino.
	robot.esperar(3.0)
	assert coche.v > 1.0


def test_cruzar_fuera_del_paso_queda_registrado():
	robot = _barrio(trafico=False, inicio=Posicion("pla-1", -20.0, 3.9, 180.0))
	for _i in range(13):
		robot.pulsar("avanzar")
	cruce = registros(robot.eventos, "cruce")[0]
	assert cruce["por_paso"] is False and cruce["paso"] == "" and cruce["seguro"] is True
	# Volver a la misma acera también cuenta, y se nota.
	for _vuelta in range(2):
		robot.pulsar("media_vuelta")
		for _i in range(3):
			robot.pulsar("avanzar")
	assert registros(robot.eventos, "cruce")[-1]["vuelve"] is True


def test_la_puerta_automatica_se_abre_al_acercarse_y_se_cierra_al_alejarse():
	entorno = ejemplos.centro_dos_plantas()
	puerta = next(a for a in entorno.plantas[0].aberturas if a.nombre == "Puerta principal")
	robot = Robot(entorno, inicio=Posicion("pla-1", 4.0, 4.5, 180.0))
	mundo = robot.sesion.mundo
	assert mundo.estado_abertura(puerta.id) == "cerrada"
	nuevos: list = []
	for _i in range(4):
		nuevos += robot.pulsar("avanzar", 3)
	assert mundo.estado_abertura(puerta.id) == "abierta"
	assert "puerta/automatica" in sonidos(nuevos)
	assert registros(nuevos, "puerta")[0]["accion"] == "automatica_abre"
	# Sale por ella sin tener que abrirla.
	for _i in range(3):
		nuevos += robot.pulsar("avanzar", 3)
	assert registros(nuevos, "salida")[0]["nombre"] == "Puerta principal"
	# Vuelve dentro y se aleja: se cierra sola.
	robot.pulsar("media_vuelta")
	nuevos = []
	for _i in range(7):
		nuevos += robot.pulsar("avanzar", 3)
	assert mundo.estado_abertura(puerta.id) == "cerrada"
	assert registros(nuevos, "puerta")[-1]["accion"] == "automatica_cierra"
	assert puerta.estado == "cerrada"


def test_objeto_con_fases_declaradas(tmp_path):
	entorno, _planta, catalogo, objetos = sala_de_pruebas(tmp_path)
	mesa = objetos["mesa"]
	mesa.datos["dinamica"] = {"fases": [{"estado": "encendido", "s": 2, "sonido": "ventilador"}, {"estado": "apagado", "s": 3}]}
	robot = Robot(entorno, catalogo)
	vistos: set[tuple[str, bool]] = set()
	for _i in range(60):
		robot.esperar(0.1)
		estado = robot.sesion.mundo.estado_objeto(mesa.id)
		suena = any(f.id == f"din:{mesa.id}" and f.sonido == "fuente/ventilador" for f in robot.sesion.fuentes())
		vistos.add((estado, suena))
	# Suena mientras está encendido y calla mientras está apagado.
	assert vistos == {("encendido", True), ("apagado", False)}
	assert mesa.estado == ""
