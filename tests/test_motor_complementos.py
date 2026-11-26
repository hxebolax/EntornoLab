"""Pruebas del motor con los complementos reales de ``data/plugins`` y los ejemplos amueblados.

En las pruebas la carpeta ``data`` está redirigida a una temporal, así que el
catálogo se carga de la carpeta del proyecto por su ruta. Si un día no hay
complementos instalados, estas pruebas se saltan.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.dominio import catalogo as cat
from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Posicion
from app.motor import eventos as ev
from app.motor.movimiento import sonido_de_objeto
from app.motor.mundo import InfoObjeto, Mundo
from tests.test_motor_comun import Robot, poner_objeto, registros, sonidos, texto, voces

RAIZ = Path(__file__).resolve().parent.parent
PLUGINS = RAIZ / "data" / "plugins"


@pytest.fixture(scope="module")
def catalogo() -> Catalogo:
	real = Catalogo.cargar(PLUGINS)
	if real.vacio:
		pytest.skip("no hay complementos en data/plugins")
	return real


def _de_tipo(mundo: Mundo, tipo: str) -> InfoObjeto:
	for indice in mundo.plantas():
		for info in indice.objetos:
			if info.objeto.tipo == tipo:
				return info
	raise AssertionError(f"no hay ningún objeto {tipo}")


def _sala(catalogo: Catalogo, ancho: float = 6.0, fondo: float = 6.0):
	entorno = ed.crear_entorno("Sala")
	planta = ed.crear_planta(entorno, "Planta")
	ed.crear_habitacion_rectangular(entorno, planta, "Sala", 0, 0, ancho, fondo)
	ed.fijar_inicio(entorno, planta, ancho / 2, 1.0, 0.0)
	return entorno, planta


def test_los_sonidos_que_citan_los_complementos_existen(catalogo):
	"""Cada sonido de cada ficha es un fichero de su complemento o un sonido de serie del catálogo de sonidos."""
	serie = set(json.loads((RAIZ / "data" / "sounds" / "catalogo.json").read_text(encoding="utf-8"))["sonidos"])
	faltan: list[str] = []
	for complemento in catalogo.complementos():
		for definicion in complemento.objetos:
			nombres = [str(definicion.sonidos.get(clave)) for clave in ("golpe", "uso") if definicion.sonidos.get(clave)]
			propio = definicion.sonidos.get("propio")
			if isinstance(propio, dict) and propio.get("sonido"):
				nombres.append(str(propio["sonido"]))
			nombres += [str(a["sonido"]) for a in definicion.acciones if a.get("sonido")]
			nombres += [str(f["sonido"]) for f in definicion.dinamica.get("fases") or [] if isinstance(f, dict) and f.get("sonido")]
			if definicion.dinamica.get("sonido_al_terminar"):
				nombres.append(str(definicion.dinamica["sonido_al_terminar"]))
			for nombre in nombres:
				if cat.es_sonido_de_complemento(nombre):
					if complemento.ruta_recurso(nombre) is None:
						faltan.append(f"{definicion.tipo}: {nombre}")
				elif ev.sonido_de_serie(nombre) not in serie:
					faltan.append(f"{definicion.tipo}: {nombre}")
	assert not faltan, faltan


def test_recorre_la_vivienda_amueblada_esquivando_los_muebles(catalogo):
	entorno = ejemplos.vivienda_ejemplo()
	puestos = ejemplos.amueblar_ejemplos(entorno, catalogo)
	assert len(puestos) >= 10
	robot = Robot(entorno, catalogo)
	mundo = robot.sesion.mundo
	planta = entorno.plantas[0]
	for nombre in ("Salón", "Cocina", "Dormitorio", "Baño"):
		centro = next(e for e in planta.espacios if e.nombre == nombre).centro()
		robot.seguir((planta.id, centro[0], centro[1]))
		assert robot.espacio == nombre, f"no ha llegado a {nombre}: está en {robot.pos}"
		# Nunca acaba dentro de un mueble ni pegado a menos de su radio.
		assert mundo.dentro_de_objeto(planta.id, *robot.pos) is None
		assert not mundo.contactos(planta.id, robot.pos[0], robot.pos[1], robot.sesion.jugador.radio - 0.01)
	assert len(robot.sesion.resumen()["espacios_visitados"]) == 6


def test_choca_con_un_mueble_real_y_lo_rodea(catalogo):
	entorno = ejemplos.vivienda_ejemplo()
	ejemplos.amueblar_ejemplos(entorno, catalogo)
	mundo = Mundo(entorno, catalogo)
	mesa = _de_tipo(mundo, "hogar/mesa_cocina")
	x0, y0, x1, y1 = mesa.caja
	medio = (y0 + y1) / 2
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", x0 - 0.9, medio, 90.0))
	nuevos: list = []
	for _i in range(3):
		nuevos += robot.pulsar("avanzar")
	choque = registros(nuevos, "choque")[0]
	assert choque["con"] == mesa.objeto.nombre and choque["clase"] == "objeto"
	assert sonido_de_objeto(mesa, str(mesa.sonidos["golpe"])) in sonidos(nuevos)
	assert robot.pos[0] == pytest.approx(x0 - 0.25, abs=0.02)
	# Por el camino que da el navegador llega al otro lado sin tocarla.
	antes = robot.sesion.movimiento.choques
	robot.seguir(("pla-1", x1 + 0.6, medio))
	assert math.hypot(robot.pos[0] - (x1 + 0.6), robot.pos[1] - medio) < 0.3
	assert robot.sesion.movimiento.choques == antes


def test_abrir_y_cerrar_un_armario_real(catalogo):
	entorno = ejemplos.vivienda_ejemplo()
	ejemplos.amueblar_ejemplos(entorno, catalogo)
	robot = Robot(entorno, catalogo)
	mundo = robot.sesion.mundo
	armario = _de_tipo(mundo, "hogar/armario")
	robot.seguir(("pla-1", armario.objeto.x, armario.objeto.y))
	cercano = min(
		(geo.proyeccion_sobre_segmento(robot.pos, a, b) for a, b in geo.lados(armario.huella)), key=lambda p: geo.distancia(robot.pos, p)
	)
	robot.girar_a(geo.rumbo_entre(robot.pos, cercano))
	# Al llegar pegado a él, el robot puede haberlo abierto ya (usa lo que le para): se deja cerrado.
	if mundo.estado_objeto(armario.objeto.id) == "abierto":
		robot.pulsar("interactuar")
	assert mundo.estado_objeto(armario.objeto.id) == "cerrado"
	nuevos = robot.pulsar("interactuar")
	assert mundo.estado_objeto(armario.objeto.id) == "abierto"
	assert "hogar/puerta_mueble.flac" in sonidos(nuevos)
	assert "Abrir: Armario." in voces(nuevos)
	interaccion = registros(nuevos, "interaccion")[0]
	assert (interaccion["accion"], interaccion["estado"]) == ("abrir", "abierto")
	nuevos = robot.pulsar("interactuar")
	assert mundo.estado_objeto(armario.objeto.id) == "cerrado" and "Cerrar: Armario." in voces(nuevos)
	assert armario.objeto.estado == "cerrado"


def test_objeto_colgante_la_sonda_no_lo_detecta_y_se_choca_con_el(catalogo):
	entorno, planta = _sala(catalogo)
	# Un espejo colgado a 90 cm, separado de la pared para que haya sitio detrás: el bastón pasa por debajo.
	espejo = poner_objeto(entorno, planta, catalogo, "hogar/espejo", 3.0, 3.0, 180.0)
	robot = Robot(entorno, catalogo)
	info = robot.sesion.mundo.objeto(espejo.id)
	assert info.altura_base > 0.2 and not info.detectable and info.bloquea
	robot.pulsar("sonda", 1)
	barrido = robot.eventos[-3:] + robot.esperar(1.5)
	nombres = [n for n in sonidos(barrido) if n.startswith("sonda/")]
	assert "sonda/objeto" not in nombres and nombres[-1] == "sonda/pared"
	assert "Pared a 5 metros." in voces(barrido)
	nuevos: list = []
	for _i in range(4):
		nuevos += robot.pulsar("avanzar")
	choque = registros(nuevos, "choque")[0]
	assert choque["con"] == espejo.nombre and choque["material"] == "cristal"
	assert "golpe/cristal" in sonidos(nuevos)
	assert robot.pos[1] < 3.0


def test_pisar_una_alfombra_real_cambia_el_suelo_y_no_corta_el_paso(catalogo):
	entorno, planta = _sala(catalogo)
	alfombra = poner_objeto(entorno, planta, catalogo, "hogar/alfombra", 3.0, 3.0)
	robot = Robot(entorno, catalogo)
	mundo = robot.sesion.mundo
	assert mundo.suelo_en(planta.id, 3.0, 3.0) == "alfombra" and mundo.suelo_en(planta.id, 3.0, 1.0) == "baldosa"
	nuevos: list = []
	for _i in range(3):
		nuevos += robot.pulsar("avanzar")
	assert robot.pos == pytest.approx((3.0, 3.1))
	pasos = [n for n in sonidos(nuevos) if n.startswith("pasos/")]
	assert pasos[0].startswith("pasos/baldosa") and pasos[-1].startswith("pasos/alfombra")
	assert registros(nuevos, "cambio_suelo")[0]["suelo"] == "alfombra"
	assert "Alfombra." in voces(nuevos + robot.esperar(4.0))
	assert alfombra.id in robot.sesion.percepcion.objetos
	assert not registros(robot.eventos, "choque")
	for _i in range(3):
		nuevos = robot.pulsar("avanzar")
	assert registros(robot.eventos, "cambio_suelo")[-1]["suelo"] == "baldosa"


def test_aviso_de_un_objeto_al_pisarlo(catalogo):
	entorno, planta = _sala(catalogo)
	poner_objeto(entorno, planta, catalogo, "transporte/borde_anden", 3.0, 3.0, ancho=4.0)
	# Aunque la actividad haya quitado los avisos de ayuda: el borde del andén es parte del lugar.
	robot = Robot(entorno, catalogo, ayudas={"avisos": False})
	nuevos: list = []
	for _i in range(3):
		nuevos += robot.pulsar("avanzar")
	aviso = next(e for e in nuevos if isinstance(e, ev.EvVoz) and "Borde del andén" in e.texto)
	assert aviso.canal == "aviso"
	assert any(n.startswith("pasos/tactil_botones") for n in sonidos(nuevos))
	# Un paso atrás y otro adelante: no se repite.
	nuevos = robot.pulsar("retroceder") + robot.pulsar("avanzar") + robot.esperar(2.0)
	assert "Borde del andén" not in texto(nuevos)


def test_torno_con_paso_libre(catalogo):
	entorno = ed.crear_entorno("Acceso")
	planta = ed.crear_planta(entorno, "Planta")
	ed.crear_habitacion_rectangular(entorno, planta, "Acceso", 0, 0, 1.0, 8.0, tipo="pasillo")
	torno = poner_objeto(entorno, planta, catalogo, "transporte/torno", 0.5, 4.0)
	ed.fijar_inicio(entorno, planta, 0.5, 2.0, 0.0)
	robot = Robot(entorno, catalogo)
	sesion = robot.sesion
	# Cerrado corta el paso, pero para buscar camino cuenta como una puerta que se puede abrir.
	assert sesion.nav.ruta(entorno.inicio, (planta.id, 0.5, 7.0)) is not None
	nuevos: list = []
	for _i in range(3):
		nuevos += robot.pulsar("avanzar")
	assert registros(nuevos, "choque")[0]["con"] == torno.nombre
	assert robot.pos[1] < 3.4
	nuevos = robot.pulsar("interactuar")
	assert sesion.mundo.estado_objeto(torno.id) == "abierto"
	assert "Validar el billete" in texto(nuevos)
	assert "transporte/torno.flac" in sonidos(nuevos)
	for _i in range(5):
		robot.pulsar("avanzar")
	assert robot.pos[1] > 5.5
	# Ya al otro lado, se cierra y vuelve a cortar.
	robot.pulsar("media_vuelta")
	robot.pulsar("avanzar")
	robot.pulsar("avanzar")
	robot.pulsar("interactuar")
	assert sesion.mundo.estado_objeto(torno.id) == "cerrado"
	for _i in range(4):
		robot.pulsar("avanzar")
	# Su huella real no es un rectángulo (tiene el pasillo entre los dos cuerpos): se entra un poco, pero no se cruza.
	assert robot.pos[1] > 3.6


def test_lavadora_suena_solo_en_marcha_y_el_temporizador_la_para(catalogo):
	entorno, planta = _sala(catalogo)
	lavadora = poner_objeto(entorno, planta, catalogo, "hogar/lavadora", 3.0, 2.0)
	robot = Robot(entorno, catalogo)
	sesion = robot.sesion
	fuente = f"obj-son:{lavadora.id}"
	assert fuente not in {f.id for f in sesion.fuentes()}
	nuevos = robot.pulsar("interactuar")
	assert sesion.mundo.estado_objeto(lavadora.id) == "funcionando"
	assert "Poner en marcha: Lavadora." in voces(nuevos)
	sonando = {f.id: f for f in sesion.fuentes()}
	assert sonando[fuente].sonido == "hogar/lavadora.flac"
	robot.esperar(60.0)
	assert fuente in {f.id for f in sesion.fuentes()}
	nuevos = robot.esperar(31.0)
	assert sesion.mundo.estado_objeto(lavadora.id) == "apagado"
	assert registros(nuevos, "objeto_termina")[0]["elemento"] == lavadora.id
	assert fuente not in {f.id for f in sesion.fuentes()}
	# Tocarla sin acción posible dice qué es y cómo está.
	assert lavadora.estado == "apagado"


def test_el_microondas_pita_al_terminar(catalogo):
	entorno, planta = _sala(catalogo)
	microondas = poner_objeto(entorno, planta, catalogo, "hogar/microondas", 3.0, 1.8)
	robot = Robot(entorno, catalogo)
	robot.pulsar("interactuar")
	assert robot.sesion.mundo.estado_objeto(microondas.id) == "funcionando"
	nuevos = robot.esperar(31.0)
	fin = [e for e in nuevos if isinstance(e, ev.EvSonido) and e.nombre == "hogar/microondas_fin.flac"]
	assert len(fin) == 1 and fin[0].pos[:2] == pytest.approx((3.0, 1.8))
	assert robot.sesion.mundo.estado_objeto(microondas.id) == "apagado"


def _calle_con_semaforos_objeto(catalogo: Catalogo):
	entorno = ed.crear_entorno("Calle")
	planta = ed.crear_planta(entorno, "Calle", exterior=True)
	calle = ed.crear_calle(entorno, planta, "Calle Larga", [(-40.0, 0.0), (40.0, 0.0)], ancho_calzada=6.0, ancho_acera=3.0, trafico=2)
	paso = ed.crear_paso_peatones(entorno, planta, calle, (0.0, 0.0), ancho=4.0, nombre="Paso de Calle Larga")
	norte = poner_objeto(entorno, planta, catalogo, "calle/semaforo_peatones", 2.4, 3.5)
	sur = poner_objeto(entorno, planta, catalogo, "calle/semaforo_peatones", -2.4, -3.5, 180.0)
	ed.fijar_inicio(entorno, planta, 1.9, 3.6, 180.0)
	return entorno, planta, paso, norte, sur


def test_semaforo_puesto_como_objeto_gobierna_su_paso(catalogo):
	entorno, planta, paso, norte, sur = _calle_con_semaforos_objeto(catalogo)
	assert not paso.datos.get("semaforo")
	robot = Robot(entorno, catalogo, trafico=True, semilla=4)
	sesion = robot.sesion
	dinamica = sesion.dinamica
	mundo = sesion.mundo
	# Los dos postes van a la vez y el paso tiene la fase que marcan.
	robot.esperar(1.0)
	assert dinamica.fase(paso.id) in ("rojo", "verde", "intermitente")
	assert mundo.estado_objeto(norte.id) == mundo.estado_objeto(sur.id) == dinamica.fase(paso.id)
	principal = dinamica._semaforos_objeto[paso.id]
	# Se pone al principio del rojo (45 s): suena el rojo desde el poste.
	principal.numero, principal.t = 0, 1.0
	robot.tic(1)
	assert dinamica.fase(paso.id) == "rojo"
	fuentes = {f.id: f for f in sesion.fuentes()}
	assert fuentes[f"din:{norte.id}"].sonido == "semaforo/rojo"
	assert fuentes[f"din:{norte.id}"].pos[:2] == pytest.approx((2.4, 3.5))
	# El alumno pulsa el botón: en 8 segundos, verde.
	assert sesion.interactuables_cerca()[0]["id"] == norte.id
	nuevos = robot.pulsar("interactuar")
	assert "semaforo/pulsador" in sonidos(nuevos)
	assert "Pulsador. Espera a que se ponga en verde." in voces(nuevos)
	assert registros(nuevos, "pulsador")[0]["paso"] == paso.id
	robot.esperar(8.5)
	assert dinamica.fase(paso.id) == "verde"
	assert mundo.estado_objeto(norte.id) == mundo.estado_objeto(sur.id) == "verde"
	assert {f.id: f for f in sesion.fuentes()}[f"din:{norte.id}"].sonido == "semaforo/verde"
	# Con el verde de peatones los vehículos se paran ante el paso.
	robot.esperar(6.0)
	for _i in range(12):
		robot.esperar(1.0)
		assert not [v for v in dinamica.vehiculos if -2.0 < v.x < 2.0 and v.v > 0.5]
	# Y cruzar ahora es seguro.
	robot.ir_a(1.0, 3.6)
	robot.girar_a(180.0)
	for _i in range(11):
		robot.pulsar("avanzar")
	cruce = registros(robot.eventos, "cruce")[0]
	assert cruce["por_paso"] is True and cruce["fase"] == "verde" and cruce["seguro"] is True


def test_en_el_barrio_amueblado_los_semaforos_objeto_siguen_al_del_paso(catalogo):
	entorno = ejemplos.barrio_ejemplo()
	ejemplos.amueblar_ejemplos(entorno, catalogo)
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", -7.0, 4.6, 180.0), semilla=2)
	sesion = robot.sesion
	postes = [i for i in sesion.mundo.planta("pla-1").objetos if i.objeto.tipo.startswith("calle/semaforo_peatones")]
	if not postes:
		pytest.skip("el barrio amueblado ya no trae semáforos como objetos")
	paso = "esp-15"
	semaforo = sesion.dinamica.semaforo_de(paso)
	for t, fase in ((1.0, "verde"), (26.0, "intermitente"), (40.0, "rojo")):
		semaforo.t = t
		robot.tic(2)
		assert sesion.dinamica.fase(paso) == fase
		assert {sesion.mundo.estado_objeto(i.objeto.id) for i in postes} == {fase}
		fuentes = sesion.fuentes()
		# Suena el poste (el objeto), no dos cosas a la vez con fases distintas.
		assert not [f for f in fuentes if f.id.startswith(f"sem:{paso}")]
		assert {f.sonido for f in fuentes if f.id.startswith("din:")} == {f"semaforo/{fase}"}


def test_los_ejemplos_amueblados_se_pueden_recorrer_y_no_frenan_el_motor(catalogo):
	import time

	for construir in ejemplos.EJEMPLOS.values():
		entorno = construir()
		ejemplos.amueblar_ejemplos(entorno, catalogo)
		robot = Robot(entorno, catalogo, modo_movimiento="continuo", trafico=True, detalle=3)
		sesion = robot.sesion
		sesion.orden("avanzar")
		inicio = time.perf_counter()
		for numero in range(600):
			if numero % 120 == 60:
				sesion.orden("girar_derecha")
				sesion.orden("girar_derecha", 0)
			sesion.avanzar(1 / 60)
			sesion.fuentes()
		medio_ms = (time.perf_counter() - inicio) / 600 * 1000.0
		assert medio_ms < 6.0, f"{entorno.nombre}: fotograma medio de {medio_ms:.2f} ms"
		assert sesion.movimiento.distancia > 1.0
