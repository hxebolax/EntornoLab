"""Pruebas del motor con lo que trae un mapa importado: escaleras de calle, atributos de tres estados y terreno base."""

from __future__ import annotations

from app.dominio import edicion as ed
from app.dominio.modelo import Posicion
from tests.test_motor_comun import Robot, registros, sonidos, texto, vibraciones, voces


def _calle_importada():
	"""Una plaza sobre «terreno sin detallar», con unas escaleras de calle hacia el norte y un paso importado."""
	entorno = ed.crear_entorno("Importado")
	planta = ed.crear_planta(entorno, "Calle", exterior=True)
	ed.crear_espacio_poligonal(
		entorno,
		planta,
		"Terreno sin detallar",
		[(-30, -30), (30, -30), (30, 30), (-30, 30)],
		tipo="exterior",
		cerrado=False,
		datos={"terreno_base": True},
	)
	ed.crear_espacio_poligonal(entorno, planta, "Plaza Vieja", [(-5, -5), (5, -5), (5, 5), (-5, 5)], tipo="plaza", cerrado=False)
	escalera = ed.crear_espacio_poligonal(
		entorno,
		planta,
		"Escaleras de la plaza",
		[(-1, 5), (1, 5), (1, 9), (-1, 9)],
		tipo="escalera",
		cerrado=False,
		datos={"peldanos": 12, "sube_hacia": 0.0, "pasamanos": "derecha", "segun_mapa": {"tactil": "desconocido"}},
	)
	ed.fijar_inicio(entorno, planta, 0.0, 3.2, 0.0)
	return entorno, planta, escalera


def test_escaleras_de_calle_como_espacio():
	entorno, _planta, _escalera = _calle_importada()
	robot = Robot(entorno)
	assert "Plaza Vieja." in voces(robot.eventos)
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar") + robot.pulsar("avanzar")
	dicho = texto(nuevos)
	assert "Escaleras, 12 peldaños. Suben." in dicho
	assert "Pasamanos: a la derecha." in dicho
	# Distingue lo que no tiene de lo que el mapa no dice.
	assert "Pavimento táctil: el mapa no lo dice." in dicho
	assert "escalera/subir" in sonidos(nuevos) and "peldano" in vibraciones(nuevos)
	assert registros(nuevos, "entrada_espacio")[0]["tipo"] == "escalera"
	# Mientras se recorren, cada paso es un peldaño; al salir por arriba, se avisa.
	nuevos = []
	for _i in range(7):
		nuevos += robot.pulsar("avanzar")
	assert sonidos(nuevos).count("escalera/subir") >= 4
	assert not [n for n in sonidos(nuevos)[:3] if n.startswith("pasos/")]
	assert "Fin de las escaleras." in texto(nuevos)
	# De vuelta, bajan.
	robot.pulsar("media_vuelta")
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar") + robot.pulsar("avanzar")
	assert "Escaleras, 12 peldaños. Bajan." in texto(nuevos)
	assert "escalera/bajar" in sonidos(nuevos)


def test_escaleras_sin_numero_de_peldanos_segun_el_mapa():
	entorno, _planta, escalera = _calle_importada()
	escalera.datos = {"segun_mapa": {"tactil": "no"}}
	robot = Robot(entorno, detalle=1)
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar") + robot.pulsar("avanzar")
	assert "Escaleras. El mapa no dice cuántos peldaños." in voces(nuevos)


def test_el_terreno_sin_detallar_no_se_anuncia_como_lugar():
	entorno, _planta, _escalera = _calle_importada()
	robot = Robot(entorno, inicio=Posicion("pla-1", 4.2, 0.0, 90.0))
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar") + robot.esperar(4.0)
	assert robot.espacio == "Terreno sin detallar"
	assert "Terreno sin detallar" not in texto(nuevos)
	assert voces(robot.pulsar("donde_estoy")) == ["Estás en una zona que el mapa no detalla, mirando al este."]
	assert [dato["nombre"] for dato in robot.sesion.percepcion.lugares_conocidos()] == ["Plaza Vieja"]
	assert "Terreno" not in texto(robot.pulsar("descubiertos"))
	# Al volver a la plaza sí se dice dónde se entra.
	robot.pulsar("media_vuelta")
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar") + robot.esperar(4.0)
	assert "Plaza Vieja." in voces(nuevos)


def test_paso_importado_distingue_no_tiene_de_el_mapa_no_lo_dice():
	entorno = ed.crear_entorno("Pasos")
	planta = ed.crear_planta(entorno, "Calle", exterior=True)
	calle = ed.crear_calle(entorno, planta, "Calle Nueva", [(-30.0, 0.0), (30.0, 0.0)], trafico=0)
	paso = ed.crear_paso_peatones(entorno, planta, calle, (0.0, 0.0), nombre="Paso")
	ed.fijar_inicio(entorno, planta, -10.0, 4.0, 90.0)
	percepcion = Robot(entorno).sesion.percepcion
	# Hecho a mano: falso es «no tiene».
	assert percepcion.texto_paso(paso, False) == "Paso de peatones sin semáforo"
	paso.datos["segun_mapa"] = {"semaforo": "desconocido", "pulsador": "desconocido", "isleta": "desconocido"}
	assert percepcion.texto_paso(paso, False) == "Paso de peatones; el mapa no dice si tiene semáforo"
	completo = percepcion.texto_paso(paso)
	assert "El mapa no dice si tiene pulsador." in completo and "El mapa no dice si hay isleta." in completo
	paso.datos["segun_mapa"] = {"semaforo": "si", "sonoro": "desconocido", "pulsador": "no", "isleta": "no"}
	assert percepcion.texto_paso(paso, False) == "Paso de peatones con semáforo; el mapa no dice si es sonoro"
	assert "pulsador" not in percepcion.texto_paso(paso) and "isleta" not in percepcion.texto_paso(paso)
	paso.datos["segun_mapa"] = {"semaforo": "si", "sonoro": "si"}
	assert percepcion.texto_paso(paso, False) == "Paso de peatones con semáforo sonoro"


def test_cruce_importado_con_su_forma_y_acera_deducida():
	entorno = ed.crear_entorno("Cruce")
	planta = ed.crear_planta(entorno, "Calle", exterior=True)
	cruce = ed.crear_espacio_poligonal(
		entorno,
		planta,
		"Cruce de la fuente",
		[(-3, -3), (3, -3), (3, 3), (-3, 3)],
		tipo="calzada",
		cerrado=False,
		datos={"cruce": True, "forma": "y", "rumbos": [0.0, 120.0, 240.0]},
	)
	ed.crear_espacio_poligonal(
		entorno, planta, "Acera", [(-10, 3), (-3, 3), (-3, 6), (-10, 6)], tipo="acera", cerrado=False, datos={"origen": "deducida"}
	)
	ed.fijar_inicio(entorno, planta, -8.0, 4.5, 90.0)
	robot = Robot(entorno)
	assert "Acera. Esta acera no está en el mapa: se ha supuesto." in voces(robot.eventos)
	dicho = robot.sesion.percepcion.texto_cruce(cruce)
	assert dicho.startswith("Cruce de la fuente, en forma de i griega.")
	assert "Salen calles: a tu izquierda, delante y detrás." in dicho
	for forma, trozo in (
		("rotonda", "es una rotonda"),
		("aspa", "en aspa"),
		("desalineado", "desalineadas"),
		("complejo", "varias calles"),
		("t", "forma de te"),
		("cruz", "en cruz"),
	):
		cruce.datos["forma"] = forma
		assert trozo in robot.sesion.percepcion.texto_cruce(cruce)
	# Y el aviso automático, dado al empezar a menos de seis metros del cruce, llevaba la forma del mapa.
	assert any(d["clase"] == "cruce" and "i griega" in d["texto"] for d in registros(robot.eventos, "aviso"))
