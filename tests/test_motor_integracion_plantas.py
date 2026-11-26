"""El robot que juega solo, ahora de planta en planta y en la calle con tráfico de verdad.

El robot de las pruebas (``Robot.recorrer`` en ``tests/test_motor_comun.py``)
pide la ruta al navegador y la anda con las mismas órdenes que el alumno:
pasos y giros, puertas que se abren al topar, escaleras peldaño a peldaño y
el ascensor llamándolo, entrando, eligiendo planta y saliendo. Con él se
juegan de principio a fin actividades que cambian de planta (el guía, los
tesoros de la planta primera) y un cruce con semáforo y vehículos reales de
``app/motor/dinamica.py``.

Los entornos son los de ejemplo, amueblados con el catálogo real (solo se leen).
"""

from __future__ import annotations

import math

from app.actividades import nueva_actividad
from app.actividades.lugares import punto_interior_de_abertura
from app.dominio import ejemplos
from tests.test_actividades_comun import Jugador, barrio, catalogo_real, centro
from tests.test_motor_comun import Robot, registros

AULA_4 = ("pla-2", 10.5, 3.0)


def _conector(entorno, tipo: str):
	return next(c for c in entorno.conectores if c.tipo == tipo)


def _premio(ident: str, nombre: str, planta: str, x: float, y: float) -> dict:
	return {"id": ident, "nombre": nombre, "planta": planta, "x": x, "y": y, "visibilidad": "cerca"}


# ── El robot entre plantas ───────────────────────────────────────────────────


def test_el_robot_sube_en_ascensor_y_baja_por_la_escalera():
	entorno = ejemplos.centro_dos_plantas()
	robot = Robot(entorno)
	ascensor = _conector(entorno, "ascensor")
	escalera = _conector(entorno, "escalera")
	# Del vestíbulo al pasillo de arriba: el navegador prefiere el ascensor (no se anda en él).
	assert robot.recorrer(("pla-2", 16.0, 7.0), cerca=0.4)
	cambio = registros(robot.eventos, "cambio_planta")
	assert [(c["de"], c["a"], c["tipo"]) for c in cambio] == [("pla-1", "pla-2", "ascensor")]
	acciones = [r["accion"] for r in registros(robot.eventos, "ascensor")]
	assert acciones[:1] == ["llamar"] and {"entrar", "viajar", "salir"} <= set(acciones)
	assert robot.espacio == "Pasillo de la planta primera"
	# De vuelta a la planta baja sin ascensor: escalera abajo, peldaño a peldaño.
	antes = len(robot.eventos)
	assert robot.recorrer(("pla-1", 4.0, 3.0), cerca=0.4, evitar=[ascensor.id])
	nuevos = robot.eventos[antes:]
	assert [(c["a"], c["conector"]) for c in registros(nuevos, "cambio_planta")] == [("pla-1", escalera.id)]
	assert len([e for e in nuevos if getattr(e, "nombre", "") == "escalera/bajar"]) == 18
	assert robot.espacio == "Vestíbulo" and robot.sesion.jugador.modo == "andando"
	# Y otra vez arriba, ahora subiendo la escalera hasta un aula con la puerta cerrada.
	antes = len(robot.eventos)
	assert robot.recorrer(AULA_4, cerca=0.5, evitar=[ascensor.id])
	nuevos = robot.eventos[antes:]
	assert len([e for e in nuevos if getattr(e, "nombre", "") == "escalera/subir"]) == 18
	assert robot.espacio == "Aula 4"
	assert [r["accion"] for r in registros(nuevos, "puerta")].count("abrir") >= 1


# ── Sigue al guía de una planta a otra ───────────────────────────────────────


def test_el_guia_lleva_a_la_planta_primera_y_se_le_sigue():
	entorno = centro()
	aula = entorno.plantas[1].espacio_en(AULA_4[1], AULA_4[2], incluir_macizos=False)
	datos = nueva_actividad("sigue_guia", entorno, destino=aula.id, velocidad_guia=1.5, distancia_espera=3.0)
	jugador = Jugador(entorno, datos, estilo="adulto")
	guia = jugador.actividad
	assert guia._conectores, "la ruta del guía tiene que cambiar de planta"
	for _vuelta in range(120):
		if jugador.sesion.terminado:
			break
		donde = guia._lugar_actual()
		jugador.recorrer(donde.terna, cerca=1.0, intentos=2)
		jugador.jugar(0.5)
	resultado = jugador.fin
	assert resultado is not None and resultado["completada"] is True, jugador.dicho()[-400:]
	assert resultado["destino"]["id"] == aula.id
	assert jugador.sesion.jugador.planta == "pla-2"
	assert [c["a"] for c in jugador.registrados("cambio_planta")] == ["pla-2"]
	# El guía dijo por dónde se cambia de planta.
	nombre = entorno.elemento(guia._conectores[0]).nombre
	assert nombre in jugador.dicho()


# ── Tesoros en la planta primera ─────────────────────────────────────────────


def test_busqueda_con_premios_en_la_planta_primera():
	entorno = centro()
	premios = [_premio("a", "la llave", "pla-2", 3.0, 7.0), _premio("b", "la brújula", "pla-2", 17.0, 7.0)]
	jugador = Jugador(entorno, nueva_actividad("busqueda", entorno, catalogo_real(), premios=premios))
	assert jugador.recorrer(("pla-2", 3.0, 7.0), cerca=0.4)
	# Al coger el último la partida termina: el robot se para ahí, aunque no haya pisado el punto exacto.
	jugador.recorrer(("pla-2", 17.0, 7.0), cerca=0.4)
	assert [p["id"] for p in jugador.registrados("premio")] == ["a", "b"]
	resultado = jugador.fin
	assert resultado is not None and resultado["completada"] is True
	assert jugador.registrados("cambio_planta")[0]["a"] == "pla-2"


def test_sacar_un_tesoro_de_la_planta_primera_por_la_salida_mas_cercana():
	entorno = centro()
	datos = nueva_actividad(
		"sacar_tesoros", entorno, catalogo_real(), estilo="juvenil", premios=[_premio("a", "el trofeo", "pla-2", 17.0, 7.0)]
	)
	jugador = Jugador(entorno, datos)
	assert jugador.recorrer(("pla-2", 17.0, 7.0), cerca=0.4)
	assert jugador.actividad.estado()["fase"] == "sacar"
	# Lo saca por la salida que le queda más cerca andando, sea cual sea, bajando por donde diga la ruta.
	sesion = jugador.sesion
	salida = sesion.nav.salidas((sesion.jugador.planta, sesion.jugador.x, sesion.jugador.y))[0]
	info = sesion.mundo.abertura(salida.abertura.id)
	(x, y), _rumbo = punto_interior_de_abertura(sesion.mundo, info, 0.9)
	assert jugador.recorrer((info.planta_id, x, y), cerca=0.4)
	antes = len(jugador.eventos)
	jugador.salir_por(salida.abertura.id)
	puntuada = registros(jugador.eventos[antes:], "salida_puntuada")[0]
	assert puntuada["puntos"] == 3
	resultado = jugador.fin
	assert resultado is not None and resultado["completada"] is True


# ── Cruce con semáforo y tráfico real ────────────────────────────────────────


def test_cruce_esperando_al_verde_con_trafico():
	"""Con vehículos de verdad: el robot va al paso, espera al verde (y a que los coches paren) y cruza."""
	entorno = barrio()
	datos = nueva_actividad("cruce", entorno, catalogo_real(), cruces=1, estilo="adulto")
	jugador = Jugador(entorno, datos, semilla=11, trafico=True)
	sesion = jugador.sesion
	dinamica = sesion.dinamica
	assert sesion.ajustes.trafico
	paso = next(e for e in entorno.plantas[0].espacios if e.tipo == "paso_peatones" and e.datos.get("semaforo"))
	# El paso está en x de -10 a -6; la calzada, en y de -3,5 a 3,5.
	assert jugador.recorrer(("pla-1", -8.0, 4.3), cerca=0.4)
	jugador.esperar(5.0)
	assert dinamica.vehiculos, "sin vehículos no se prueba nada"
	semaforo = dinamica.semaforo_de(paso.id)

	def se_puede_cruzar() -> bool:
		# Verde con tiempo de sobra y ningún vehículo en marcha cerca del paso.
		if dinamica.fase(paso.id) != "verde" or semaforo.restante < 12.0:
			return False
		return not any(abs(v.x + 8.0) < 12.0 and abs(v.y) < 4.0 and v.v > 0.5 for v in dinamica.vehiculos)

	# Si está en rojo, pulsa el pulsador del poste; después, espera con plazo.
	if dinamica.fase(paso.id) != "verde" and sesion.interactuables_cerca() and sesion.interactuables_cerca()[0]["clase"] == "pulsador":
		jugador.pulsar("interactuar")
	assert jugador.esperar_hasta(se_puede_cruzar, 160.0, dt=0.25)
	antes = len(jugador.eventos)
	jugador.ir_a(-8.0, -4.4)
	jugador.tic(3)
	nuevos = jugador.eventos[antes:]
	cruce = registros(nuevos, "cruce")[0]
	assert cruce["por_paso"] is True and cruce["fase"] == "verde" and cruce["seguro"] is True
	assert not registros(nuevos, "cruce_inseguro")
	assert registros(nuevos, "cruce_puntuado")[0]["puntos"] == 3
	resultado = jugador.fin
	assert resultado is not None and resultado["completada"] is True
	assert resultado["puntuaciones"]["cruces_en_rojo"] == 0
	assert math.isfinite(resultado["tiempo_activo"])
