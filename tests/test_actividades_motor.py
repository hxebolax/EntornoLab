"""Lo que las actividades necesitan del motor: regresiones de fallos encontrados al escribirlas.

- Con la mano no se llega a un objeto que está al otro lado de una pared:
  antes se podía abrir un armario (y sacar el premio que escondía) desde la
  habitación de al lado. Corregido en ``Movimiento.interactuables``.
- Las actividades reciben los registros del motor (un choque, un cruce, una
  salida) por el gancho ``al_registrar`` y los atienden en su ``tic``; antes
  los leían de un atributo privado de la sesión.
"""

from __future__ import annotations

from app.actividades import nueva_actividad
from app.motor import eventos as ev
from app.actividades.lugares import objeto_a_mano, punto_de_acceso
from app.dominio.modelo import Posicion
from tests.test_actividades_comun import Jugador
from tests.test_motor_comun import Robot, poner_objeto, registros, sala_de_pruebas, texto


def sala_con_armario_en_el_tabique(tmp_path):
	"""La sala de pruebas con un armario pegado, por dentro, al tabique que la separa de la antesala (x = 0)."""
	entorno, planta, catalogo, objetos = sala_de_pruebas(tmp_path)
	objetos["tabique"] = poner_objeto(entorno, planta, catalogo, "prueba/armario", 0.4, 1.2, 90.0, estado="cerrado")
	return entorno, planta, catalogo, objetos


def test_no_se_usa_un_objeto_a_traves_de_una_pared(tmp_path):
	entorno, planta, catalogo, objetos = sala_con_armario_en_el_tabique(tmp_path)
	armario = objetos["tabique"]
	# Desde la antesala, pegado al tabique y de cara al armario: está a un palmo, pero hay una pared en medio.
	robot = Robot(entorno, catalogo, inicio=Posicion(planta.id, -0.4, 1.2, 90.0))
	info = robot.sesion.mundo.objeto(armario.id)
	assert info.distancia(*robot.pos) < 1.0
	assert armario.id not in [dato["id"] for dato in robot.sesion.interactuables_cerca()]
	eventos = robot.pulsar("interactuar")
	assert robot.sesion.mundo.estado_objeto(armario.id) == "cerrado"
	assert registros(eventos, "interaccion") == []
	assert "No hay nada que usar aquí" in texto(eventos)
	# Desde dentro de la sala, sí.
	robot = Robot(entorno, catalogo, inicio=Posicion(planta.id, 1.4, 1.2, 270.0))
	assert robot.sesion.interactuables_cerca()[0]["id"] == armario.id
	eventos = robot.pulsar("interactuar")
	assert robot.sesion.mundo.estado_objeto(armario.id) == "abierto"
	assert registros(eventos, "interaccion")[0]["elemento"] == armario.id


def test_un_mueble_delante_de_otro_no_impide_usarlo(tmp_path):
	"""Lo que corta es la pared: por encima de una silla o de una mesa baja sí se alcanza lo que hay detrás."""
	entorno, planta, catalogo, objetos = sala_de_pruebas(tmp_path)
	armario = poner_objeto(entorno, planta, catalogo, "prueba/armario", 4.0, 5.6, 0.0, estado="cerrado")
	silla = poner_objeto(entorno, planta, catalogo, "prueba/silla", 4.0, 4.9, 0.0)
	robot = Robot(entorno, catalogo, inicio=Posicion(planta.id, 4.0, 4.3, 0.0))
	a_mano = [dato["id"] for dato in robot.sesion.interactuables_cerca()]
	assert silla.id in a_mano and armario.id in a_mano
	info = robot.sesion.mundo.objeto(armario.id)
	assert objeto_a_mano(robot.sesion.mundo, planta.id, robot.pos, info)


def test_el_premio_de_un_armario_no_se_saca_desde_la_habitacion_de_al_lado(tmp_path):
	entorno, planta, catalogo, objetos = sala_con_armario_en_el_tabique(tmp_path)
	armario = objetos["tabique"]
	datos = nueva_actividad(
		"busqueda",
		entorno,
		catalogo,
		premios=[{"id": "a", "nombre": "la llave", "dentro_de": armario.id, "visibilidad": "oculto"}],
		inicio={"planta": planta.id, "x": -0.4, "y": 1.2, "rumbo": 90.0},
	)
	jugador = Jugador(entorno, datos, catalogo)
	# El punto desde el que se usa el armario está en la sala, no en la antesala (que queda más cerca de su centro).
	acceso = punto_de_acceso(jugador.sesion.mundo, armario.id)
	assert acceso is not None and planta.espacio_en(*acceso).nombre == "Sala"
	assert jugador.actividad.premios[0].lugar().punto == acceso
	jugador.pulsar("interactuar")
	assert jugador.registrados("premio") == [] and not jugador.sesion.terminado
	jugador.usar(armario.id)
	assert [p["id"] for p in jugador.registrados("premio")] == ["a"]
	assert jugador.espacio == "Sala" and jugador.fin["completada"] is True


def test_las_actividades_ven_los_registros_del_motor(tmp_path):
	"""Un choque registrado por el motor llega a la actividad en el mismo fotograma (así cuenta los tropiezos)."""
	entorno, planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	datos = nueva_actividad(
		"busqueda",
		entorno,
		catalogo,
		premios=[{"id": "a", "nombre": "la llave", "planta": planta.id, "x": 6.0, "y": 4.0}],
		fallos_para_ayuda=1,
	)
	jugador = Jugador(entorno, datos, catalogo)
	vistos: list[str] = []
	original = jugador.actividad._al_registro
	jugador.actividad._al_registro = lambda sesion, tipo, datos_registro: (vistos.append(tipo), original(sesion, tipo, datos_registro))[1]
	jugador.girar_a(270.0)
	for _paso in range(6):
		jugador.pulsar("avanzar", 1)
	jugador.tic(2)
	choques = len(jugador.registrados("choque"))
	assert choques >= 4 and vistos.count("choque") == choques
	assert jugador.actividad._fallos >= 1 and jugador.registrados("ayuda_ofrecida")


def test_los_registros_llegan_por_el_gancho_y_se_atienden_en_el_tic(tmp_path):
	"""``Actividad.al_registrar`` solo apunta; la regla del tipo los atiende en el ``tic`` del mismo fotograma, en orden."""
	entorno, planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	datos = nueva_actividad(
		"busqueda", entorno, catalogo, premios=[{"id": "a", "nombre": "la llave", "planta": planta.id, "x": 6.0, "y": 4.0}]
	)
	jugador = Jugador(entorno, datos, catalogo)
	actividad = jugador.actividad
	vistos: list[tuple[str, str]] = []
	actividad._al_registro = lambda sesion, tipo, datos_registro: vistos.append((tipo, datos_registro.get("marca", "")))
	# Un registro que el reproductor reenvía con «emitir» entre fotogramas también llega.
	jugador.sesion.emitir(ev.EvRegistro("choque", {"marca": "uno"}))
	jugador.sesion.emitir(ev.EvRegistro("cosa_que_no_interesa", {"marca": "dos"}))
	jugador.sesion.registrar("cambio_planta", marca="tres")
	assert vistos == []
	jugador.tic(1)
	assert vistos == [("choque", "uno"), ("cambio_planta", "tres")]
	# Al atender un choque la actividad cuenta el tropiezo.
	assert actividad._t_choques
	# Cerrada la actividad, ya no se apunta nada.
	jugador.sesion.terminar()
	jugador.sesion.emitir(ev.EvRegistro("choque", {"marca": "cuatro"}))
	assert actividad._registros_pendientes == []
