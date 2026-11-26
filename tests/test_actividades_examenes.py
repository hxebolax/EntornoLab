"""Los exámenes: sin pistas ni celebraciones, con tiempo sin pausas, regla de parada y semilla reproducible."""

from __future__ import annotations

import pytest

from app.actividades import crear_actividad, nueva_actividad, plantillas_de
from app.dominio import geometria as geo
from app.motor import eventos as ev
from tests.test_actividades_comun import Jugador, catalogo_real, centro, ejemplo, espacio_en, presentar
from tests.test_motor_comun import Robot, registros, sonidos

CELEBRACIONES = ("logro/logro", "logro/estrella_1", "logro/estrella_2", "logro/estrella_3", "logro/medalla", "premio/tesoro", "logro/error")
PALABRAS_DE_VALORACION = ("Muy bien", "Correcto", "Has acertado", "Has fallado", "Incorrecto", "Bravo", "estrella")


def casa_vacia():
	return ejemplo("vivienda-de-ejemplo", False)


def ruta_definida(entorno, origen, destino) -> dict:
	return {"origen": origen, "destino": destino}


def pruebas_de(jugador: Jugador) -> list[tuple[str, str]]:
	"""(origen, destino) de las pruebas que ha generado un examen."""
	return [(p["origen"].nombre, p["destino"].nombre) for p in jugador.actividad._pruebas]


def sin_valorar(jugador: Jugador) -> None:
	"""Durante un examen no hay celebraciones ni se dice si se acierta."""
	dicho = jugador.dicho()
	for palabra in PALABRAS_DE_VALORACION:
		assert palabra not in dicho, palabra
	for sonido in CELEBRACIONES:
		assert sonido not in sonidos(jugador.eventos), sonido


# ── Examen de rutas ──────────────────────────────────────────────────────────


def test_examen_de_rutas_acierto_fallo_y_tiempo():
	entorno = casa_vacia()
	cocina, salon, bano, dormitorio = (espacio_en(entorno, x, y) for x, y in ((6.0, 2.0), (2.0, 2.0), (5.5, 7.0), (2.0, 7.0)))
	datos = nueva_actividad(
		"examen_rutas",
		entorno,
		pruebas=[
			ruta_definida(entorno, salon.id, cocina.id),
			ruta_definida(entorno, cocina.id, bano.id),
			ruta_definida(entorno, bano.id, dormitorio.id),
		],
		tiempo_por_prueba_s=60,
		regla_parada=None,
	)
	assert datos["modo"] == "examen"
	jugador = Jugador(entorno, datos, estilo="infantil")
	actividad = jugador.actividad
	jugador.tic(3)
	assert "No hay pistas" in jugador.dicho()
	assert (
		"Prueba 1 de 3. Estás en Salón. Ve a Cocina. Cuando creas que has llegado, confírmalo con la orden de usar. Tienes 1 minuto."
		in jugador.dicho()
	)
	# El examen coloca al alumno en el origen de cada ruta.
	assert jugador.espacio == "Salón"
	assert actividad.estado()["total"] == 3 and actividad.estado()["tiempo_restante"] > 59
	# Prueba 1: llega y confirma. No se le dice que ha acertado.
	jugador.ir_a_espacio(cocina.id)
	assert actividad.estado()["hechos"] == 0, "llegar no basta: hay que confirmar"
	antes = len(jugador.eventos)
	jugador.pulsar("interactuar")
	assert "Anotado." in jugador.dicho(antes) and "No hay nada que usar" not in jugador.dicho(antes)
	primera = registros(jugador.eventos[antes:], "examen")[0]
	assert primera["acierto"] is True and primera["motivo"] == "confirmada" and primera["n"] == 1
	assert primera["origen"] == "Salón" and primera["destino"] == "Cocina" and primera["cociente"] is not None
	# Prueba 2: confirma sin haber llegado. Tampoco se le dice.
	assert jugador.espacio == "Cocina"
	antes = len(jugador.eventos)
	jugador.pulsar("interactuar")
	segunda = registros(jugador.eventos[antes:], "examen")[0]
	assert segunda["acierto"] is False and segunda["motivo"] == "confirmada"
	assert "Anotado." in jugador.dicho(antes)
	# Prueba 3: se queda parado. La pausa no cuenta para el límite; el tiempo de juego, sí.
	assert jugador.espacio == "Baño"
	jugador.tic(80, dt=0.25)
	jugador.sesion.pausar(True)
	jugador.tic(800, dt=0.25)
	jugador.sesion.pausar(False)
	jugador.tic(1)
	assert actividad.estado()["hechos"] == 2 and 38 <= actividad.estado()["tiempo_restante"] <= 40
	antes = len(jugador.eventos)
	jugador.tic(170, dt=0.25)
	tercera = registros(jugador.eventos[antes:], "examen")[0]
	assert tercera["acierto"] is False and tercera["motivo"] == "tiempo" and 60 <= tercera["tiempo_s"] <= 61
	assert "Se acabó el tiempo de esta prueba." in jugador.dicho(antes)
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["actividad"]["modo"] == "examen"
	examen = resultado["examen"]
	assert (
		examen["medida"] == "rutas" and examen["aciertos"] == 1 and examen["pruebas_hechas"] == 3 and examen["porcentaje_aciertos"] == 33.3
	)
	assert [p["acierto"] for p in examen["pruebas"]] == [True, False, False]
	assert examen["parada"] is False and resultado["puntuaciones"] == examen
	assert "El examen ha terminado. Gracias." in jugador.dicho()
	# Sin celebraciones, sin estrellas, sin recompensas y sin decir el resultado.
	sin_valorar(jugador)
	assert resultado["estrellas"] == 0 and resultado["recompensas"] == [] and jugador.registrados("recompensa") == []
	assert "Rutas conseguidas" not in jugador.dicho()
	assert jugador.registrados("puntuacion")[0]["aciertos"] == 1


def test_examen_sin_pistas_ni_baliza_ni_donde_estoy():
	entorno = casa_vacia()
	# Aunque el profesional intente permitir las pistas, en un examen no las hay.
	datos = nueva_actividad("examen_rutas", entorno, regla_parada=None, ayudas={"pista": True, "baliza": True, "sonda": True})
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	ayudas = jugador.sesion.ajustes.ayudas
	assert ayudas["pista"]["permitida"] is False and ayudas["baliza"]["permitida"] is False
	assert ayudas["donde_estoy"]["permitida"] is False and ayudas["cercanos"]["permitida"] is False
	for accion in ("pista", "donde_estoy", "cercano_siguiente"):
		jugador.pulsar(accion)
	assert {d["ayuda"] for d in jugador.registrados("ayuda_denegada")} == {"pista", "donde_estoy", "cercanos"}
	# Lo que sirve para percibir (el bastón sonoro) sigue disponible, y se puede oír otra vez la instrucción.
	jugador.pulsar("sonda")
	antes = len(jugador.eventos)
	jugador.pulsar("objetivo")
	assert "Cuando creas que has llegado" in jugador.dicho(antes)
	assert [a["ayuda"] for a in jugador.registrados("ayuda")] == ["sonda", "objetivo"]
	# Ni atascado se ofrece ayuda en un examen.
	jugador.tic(700, dt=0.25)
	assert jugador.registrados("ayuda_ofrecida") == []


def test_examen_de_rutas_generado_es_reproducible_con_la_semilla():
	entorno = casa_vacia()
	datos = nueva_actividad("examen_rutas", entorno, numero_pruebas=4, semilla=5, regla_parada=None)
	primero, segundo = Jugador(entorno, datos), Jugador(entorno, datos, semilla=5)
	primero.tic(3)
	segundo.tic(3)
	assert len(pruebas_de(primero)) == 4
	# Mismo examen, misma semilla: mismas rutas, en el mismo orden y con el mismo rumbo de salida.
	assert pruebas_de(primero) == pruebas_de(segundo)
	assert primero.sesion.jugador.rumbo == segundo.sesion.jugador.rumbo
	assert (primero.sesion.jugador.x, primero.sesion.jugador.y) == (segundo.sesion.jugador.x, segundo.sesion.jugador.y)
	# La semilla del reproductor (la de la sesión) no cambia el examen: manda la de la actividad.
	actividad = crear_actividad(datos, entorno, semilla=1234)
	assert actividad.semilla == 5
	# En cambio, a una actividad que no trae semilla (un juego) sí se le da la de la partida.
	assert crear_actividad(nueva_actividad("escondite", entorno), entorno, semilla=1234).semilla == 1234
	robot = Robot(entorno, None, actividad=actividad, semilla=99)
	robot.tic(3)
	assert [(p["origen"].nombre, p["destino"].nombre) for p in actividad._pruebas] == pruebas_de(primero)
	# Con otra semilla sale otro examen.
	variantes = set()
	for semilla in (6, 7, 8, 9):
		otro = Jugador(entorno, dict(datos, semilla=semilla))
		otro.tic(3)
		variantes.add(tuple(pruebas_de(otro)))
	assert any(v != tuple(pruebas_de(primero)) for v in variantes)
	# Las rutas son de longitud parecida y no repiten pareja.
	largos = [p["longitud"] for p in primero.actividad._pruebas]
	assert max(largos) <= 2.0 * min(largos)
	assert len({frozenset(par) for par in pruebas_de(primero)}) == 4


def test_examen_de_rutas_del_centro_excluye_las_entrenadas():
	entorno = centro()
	datos = next(d for d in plantillas_de("centro-de-dos-plantas", entorno, catalogo_real()) if d["tipo"] == "examen_rutas")
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	rutas = jugador.actividad._pruebas
	assert len(rutas) == 5
	entrenada = [rutas[0]["origen"].elemento_id, rutas[0]["destino"].elemento_id]
	datos = dict(datos, entrenadas=[entrenada])
	otro = Jugador(entorno, datos)
	otro.tic(3)
	pares = [frozenset((p["origen"].elemento_id, p["destino"].elemento_id)) for p in otro.actividad._pruebas]
	assert len(pares) == 5 and frozenset(entrenada) not in pares


def test_regla_de_parada_corta_el_examen():
	"""Con «3 de las 5 primeras», al tercer fallo ya no se puede llegar a 3 aciertos: se deja ahí."""
	entorno = casa_vacia()
	datos = nueva_actividad("examen_rutas", entorno, numero_pruebas=5, semilla=3, regla_parada={"de": 5, "minimo": 3})
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	assert jugador.actividad.estado()["total"] == 5
	for _prueba in range(3):
		assert not jugador.sesion.terminado
		jugador.confirmar()
	resultado = jugador.fin
	assert resultado is not None and resultado["motivo"] == "regla_parada" and resultado["completada"] is True
	assert (
		resultado["examen"]["parada"] is True and resultado["examen"]["pruebas_hechas"] == 3 and resultado["examen"]["pruebas_total"] == 5
	)
	assert "Lo dejamos aquí por hoy." in jugador.dicho()
	sin_valorar(jugador)


def test_sin_regla_de_parada_se_hacen_todas():
	entorno = casa_vacia()
	datos = nueva_actividad("examen_rutas", entorno, numero_pruebas=5, semilla=3, regla_parada=None, decir_resultado=True)
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	for _prueba in range(5):
		jugador.confirmar()
	assert jugador.fin["examen"]["pruebas_hechas"] == 5 and jugador.fin["examen"]["parada"] is False
	# El resultado solo se dice al final, y solo si el profesional lo ha pedido.
	assert "Rutas conseguidas: 0 de 5." in jugador.dicho()


def test_abrir_una_puerta_no_es_confirmar():
	entorno = casa_vacia()
	salon, dormitorio = espacio_en(entorno, 2.0, 2.0), espacio_en(entorno, 2.0, 7.0)
	datos = nueva_actividad("examen_rutas", entorno, pruebas=[ruta_definida(entorno, salon.id, dormitorio.id)], regla_parada=None)
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	# La puerta del dormitorio está cerrada: el robot la abre con la misma orden de usar y el examen no lo toma por una confirmación.
	jugador.ir_a_espacio(dormitorio.id)
	assert any(p["accion"] == "abrir" for p in jugador.registrados("puerta"))
	assert jugador.registrados("examen") == [] and not jugador.sesion.terminado
	jugador.actividad.confirmar(jugador.sesion)
	jugador.tic(1)
	assert jugador.fin["examen"]["aciertos"] == 1


def test_variante_inversa_ensena_la_ida_y_mide_la_vuelta():
	entorno = casa_vacia()
	salon, cocina = espacio_en(entorno, 2.0, 2.0), espacio_en(entorno, 6.0, 2.0)
	datos = nueva_actividad(
		"examen_rutas", entorno, variante="inversa", pruebas=[ruta_definida(entorno, salon.id, cocina.id)], regla_parada=None
	)
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	assert "Primero sigue la baliza hasta Cocina." in jugador.dicho()
	jugador.jugar(3.0)
	assert any(s.startswith("baliza/") for s in sonidos(jugador.eventos))
	# En la ida no hay nada que confirmar.
	jugador.pulsar("interactuar")
	assert jugador.registrados("examen") == []
	jugador.jugar(20.0)
	jugador.ir_a_espacio(cocina.id)
	jugador.jugar(1.0)
	assert "Ahora vuelve a Salón sin ayuda." in jugador.dicho()
	assert jugador.sesion.ajustes.ayudas["baliza"]["permitida"] is False
	antes = len(jugador.eventos)
	jugador.jugar(4.0)
	assert not any(s.startswith("baliza/") for s in sonidos(jugador.eventos[antes:]))
	# El reloj de la prueba arranca con la vuelta: los 24 segundos de la ida no cuentan.
	jugador.ir_a_espacio(salon.id)
	jugador.pulsar("interactuar")
	prueba = jugador.fin["examen"]["pruebas"][0]
	assert prueba["acierto"] is True and prueba["variante"] == "inversa" and prueba["destino"] == "Salón"
	assert prueba["tiempo_s"] < 15 and jugador.fin["ayudas_contadas"] == 0


def test_variante_atajo_mide_un_camino_no_practicado():
	entorno = casa_vacia()
	salon, cocina, bano = espacio_en(entorno, 2.0, 2.0), espacio_en(entorno, 6.0, 2.0), espacio_en(entorno, 5.5, 7.0)
	datos = nueva_actividad(
		"examen_rutas", entorno, variante="atajo", pruebas=[{"origen": salon.id, "destino": cocina.id, "via": bano.id}], regla_parada=None
	)
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	jugador.ir_a_espacio(cocina.id)
	jugador.jugar(1.0)
	assert "Ahora sigue la baliza hasta Baño." in jugador.dicho()
	jugador.ir_a_espacio(bano.id)
	jugador.jugar(1.0)
	assert "Ahora ve a Salón por el camino más corto que sepas." in jugador.dicho()
	jugador.ir_a_espacio(salon.id)
	jugador.pulsar("interactuar")
	prueba = jugador.fin["examen"]["pruebas"][0]
	# El robot entra hasta el fondo del baño antes de volver, así que su camino no es el más corto; lo que importa es que se mide.
	assert prueba["acierto"] is True and prueba["variante"] == "atajo" and 1.0 <= prueba["cociente"] < 2.0
	assert prueba["origen"] == "Baño" and prueba["destino"] == "Salón" and prueba["optimo_m"] > 5


# ── Examen de salida más corta ───────────────────────────────────────────────


def test_examen_de_salida_puntua_3_2_1_0():
	entorno = centro()
	baja = entorno.plantas[0]
	salidas = {a.nombre: a.id for a in baja.aberturas if a.es_salida}
	datos = nueva_actividad(
		"examen_salida",
		entorno,
		catalogo_real(),
		pruebas=[
			{"origen": {"planta": baja.id, "x": 18.0, "y": 7.0}},
			{"origen": {"planta": baja.id, "x": 2.0, "y": 7.0}},
			{"origen": {"planta": baja.id, "x": 18.0, "y": 7.0}},
			{"origen": {"planta": baja.id, "x": 10.0, "y": 7.0}},
		],
		tiempo_por_prueba_s=40,
		regla_parada=None,
	)
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	assert "Sal del edificio por la salida más cercana." in jugador.dicho()
	# 1) Desde el extremo este, por la salida este: 3 puntos.
	jugador.salir_por(salidas["Salida de emergencia este"])
	# 2) Desde el extremo oeste, por la principal (la segunda más cercana): 2 puntos.
	assert abs(jugador.pos[0] - 2.0) < 0.01
	jugador.salir_por(salidas["Puerta principal"])
	# 3) Desde el extremo este, por la principal (la más lejana de las tres andando): 1 punto.
	jugador.salir_por(salidas["Puerta principal"])
	# 4) No sale: se acaba el tiempo y vale 0.
	jugador.tic(170, dt=0.25)
	resultado = jugador.fin
	examen = resultado["examen"]
	assert [p["puntos"] for p in examen["pruebas"]] == [3, 2, 1, 0]
	assert [p["motivo"] for p in examen["pruebas"]] == ["salida", "salida", "salida", "tiempo"]
	assert (
		examen["medida"] == "salida_mas_corta"
		and examen["puntos"] == 6
		and examen["puntos_maximos"] == 12
		and examen["media_puntos"] == 1.5
	)
	assert examen["salidas_optimas"] == 1 and examen["aciertos"] == 2
	assert examen["pruebas"][0]["salida_mas_cercana"] == salidas["Salida de emergencia este"]
	assert examen["pruebas"][0]["cociente"] is not None and examen["pruebas"][3]["cociente"] is None
	assert len(jugador.registrados("examen")) == 4
	sin_valorar(jugador)


def test_examen_de_salida_generado_prefiere_puntos_donde_elegir_importa():
	entorno = centro()
	datos = next(d for d in plantillas_de("centro-de-dos-plantas", entorno, catalogo_real()) if d["tipo"] == "examen_salida")
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	pruebas = jugador.actividad._pruebas
	assert len(pruebas) == 5 and len({p["origen"].elemento_id for p in pruebas}) == 5
	otro = Jugador(entorno, datos)
	otro.tic(3)
	assert [p["origen"].elemento_id for p in otro.actividad._pruebas] == [p["origen"].elemento_id for p in pruebas]


# ── Examen de señalar ────────────────────────────────────────────────────────


def test_examen_de_senalar_mide_el_error_en_grados():
	entorno = casa_vacia()
	salon, bano, cocina = espacio_en(entorno, 2.0, 2.0), espacio_en(entorno, 5.5, 7.0), espacio_en(entorno, 6.0, 2.0)
	datos = nueva_actividad(
		"examen_senalar",
		entorno,
		pruebas=[{"origen": salon.id, "destino": bano.id}, {"origen": salon.id, "destino": cocina.id}],
		tolerancia_grados=20,
		regla_parada=None,
	)
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	assert "gírate hacia Baño y confírmalo" in jugador.dicho()
	# En este examen cada pulsación gira 15 grados, para poder afinar.
	assert jugador.sesion.ajustes.giro_grados == 15
	sesion = jugador.sesion
	destino = jugador.actividad._pruebas[0]["destino"]
	real = geo.rumbo_entre(sesion.jugador.punto, destino.punto)
	jugador.girar_a(real)
	jugador.pulsar("interactuar")
	# La segunda: señala justo al revés.
	destino = jugador.actividad._pruebas[1]["destino"]
	jugador.girar_a(geo.rumbo_entre(sesion.jugador.punto, destino.punto) + 180.0)
	jugador.pulsar("interactuar")
	examen = jugador.fin["examen"]
	assert examen["medida"] == "senalar"
	assert examen["pruebas"][0]["error_grados"] == 0.0 and examen["pruebas"][0]["acierto"] is True
	assert examen["pruebas"][1]["error_grados"] == 180.0 and examen["pruebas"][1]["acierto"] is False
	assert examen["error_medio_grados"] == 90.0 and examen["error_mediano_grados"] == 90.0
	assert examen["pruebas"][0]["rumbo_real"] == pytest.approx(real % 360.0, abs=0.1)
	sin_valorar(jugador)


def test_examen_de_senalar_generado_apunta_a_lugares_que_no_se_perciben():
	entorno = casa_vacia()
	jugador = Jugador(entorno, nueva_actividad("examen_senalar", entorno, numero_pruebas=4, regla_parada=None))
	jugador.tic(3)
	pruebas = jugador.actividad._pruebas
	assert len(pruebas) == 4
	mundo = jugador.sesion.mundo
	for prueba in pruebas:
		origen, destino = prueba["origen"], prueba["destino"]
		assert origen.elemento_id != destino.elemento_id
		assert not mundo.visible(origen.planta, origen.punto, destino.punto, "vista")


# ── Examen de distancias ─────────────────────────────────────────────────────


def test_examen_de_distancias_por_camino_y_en_linea_recta():
	"""Desde el salón, la cocina está pared con pared (cerca en línea recta) pero el dormitorio... depende de cómo se mida."""
	entorno = casa_vacia()
	salon, cocina, entrada, bano = (espacio_en(entorno, x, y) for x, y in ((2.0, 2.0), (6.0, 2.0), (-1.0, 4.6), (5.5, 7.0)))
	pregunta = [{"origen": salon.id, "a": bano.id, "b": entrada.id}, {"origen": salon.id, "a": cocina.id, "b": bano.id}]
	por_camino = Jugador(entorno, nueva_actividad("examen_distancias", entorno, pruebas=pregunta, criterio="camino", regla_parada=None))
	por_camino.tic(3)
	assert "Andando desde aquí, ¿qué queda más cerca: Baño o Entrada?" in por_camino.dicho()
	assert "Cambia de opción con la orden de objetivo y confirma con la orden de usar." in por_camino.dicho()
	estado = por_camino.actividad.estado()
	assert estado["pregunta"]["opciones"] == ["Baño", "Entrada"] and estado["pregunta"]["elegida"] == -1
	# Confirmar sin haber elegido no anota nada: repite la pregunta.
	por_camino.pulsar("interactuar")
	assert por_camino.registrados("examen") == []
	# La orden de objetivo va pasando por las opciones.
	antes = len(por_camino.eventos)
	por_camino.pulsar("objetivo")
	assert "Opción 1 de 2: Baño." in por_camino.dicho(antes)
	antes = len(por_camino.eventos)
	por_camino.pulsar("objetivo")
	assert "Opción 2 de 2: Entrada." in por_camino.dicho(antes)
	por_camino.pulsar("interactuar")
	# La segunda se contesta como lo haría un menú del reproductor: eligiendo por número.
	eventos = por_camino.actividad.responder(por_camino.sesion, 1)
	assert isinstance(eventos[0], ev.EvVoz) and "Opción 2 de 2: Baño." in eventos[0].texto
	presentar(por_camino, eventos)
	por_camino.actividad.confirmar(por_camino.sesion)
	por_camino.tic(1)
	examen = por_camino.fin["examen"]
	assert examen["medida"] == "distancias" and examen["criterio"] == "camino"
	primera, segunda = examen["pruebas"]
	assert primera["d_a"] > 0 and primera["d_b"] > 0
	assert primera["correcta"] == ("Baño" if primera["d_a"] <= primera["d_b"] else "Entrada")
	assert primera["respuesta"] == "Entrada" and primera["acierto"] is (primera["correcta"] == "Entrada")
	assert segunda["correcta"] == ("Cocina" if segunda["d_a"] <= segunda["d_b"] else "Baño")
	assert segunda["respuesta"] == "Baño" and segunda["acierto"] is (segunda["correcta"] == "Baño")
	sin_valorar(por_camino)
	en_recta = Jugador(entorno, nueva_actividad("examen_distancias", entorno, pruebas=pregunta, criterio="recta", regla_parada=None))
	en_recta.tic(3)
	assert "En línea recta desde aquí" in en_recta.dicho()
	recta = en_recta.actividad._pruebas[1]
	camino = por_camino.actividad._pruebas[1]
	# En línea recta la cocina queda a 4 metros del salón; andando hay que salir al pasillo y volver a entrar.
	assert recta["d_a"] < camino["d_a"]


def test_examen_de_distancias_generado_evita_las_preguntas_dudosas():
	entorno = casa_vacia()
	jugador = Jugador(entorno, nueva_actividad("examen_distancias", entorno, numero_pruebas=5, regla_parada=None))
	jugador.tic(3)
	pruebas = jugador.actividad._pruebas
	assert len(pruebas) == 5
	for prueba in pruebas:
		mayor, menor = max(prueba["d_a"], prueba["d_b"]), min(prueba["d_a"], prueba["d_b"])
		assert (mayor - menor) / mayor >= 0.19


# ── Examen de reconstrucción ─────────────────────────────────────────────────


def test_examen_de_reconstruccion_pregunta_relaciones_reales():
	entorno = casa_vacia()
	jugador = Jugador(entorno, nueva_actividad("examen_reconstruccion", entorno, numero_pruebas=4, regla_parada=None))
	jugador.tic(3)
	pruebas = jugador.actividad._pruebas
	assert len(pruebas) == 4
	planta = entorno.plantas[0]
	por_nombre = {e.nombre: e for e in planta.espacios}
	ejes = {"norte": 0.0, "este": 90.0, "sur": 180.0, "oeste": 270.0}
	for prueba in pruebas:
		referencia, correcta = por_nombre[prueba["referencia"]], por_nombre[prueba["correcta"]]
		# La respuesta correcta está de verdad en esa dirección, y es la única de las opciones que lo está.
		rumbo = geo.rumbo_entre(referencia.centro(), correcta.centro())
		assert abs(geo.diferencia_rumbos(ejes[prueba["lado"]], rumbo)) <= 30.0
		assert prueba["opciones"].count(prueba["correcta"]) == 1 and 2 <= len(prueba["opciones"]) <= 4
		assert prueba["referencia"] not in prueba["opciones"]
	assert "¿Qué hay al" in jugador.dicho()
	# Contesta bien las dos primeras y mal las otras dos.
	for numero, prueba in enumerate(pruebas):
		opciones = jugador.actividad.estado()["pregunta"]["opciones"]
		buena = opciones.index(prueba["correcta"])
		elegida = buena if numero < 2 else next(i for i in range(len(opciones)) if i != buena)
		jugador.actividad.responder(jugador.sesion, elegida)
		jugador.pulsar("interactuar")
	examen = jugador.fin["examen"]
	assert examen["medida"] == "reconstruccion" and examen["aciertos"] == 2 and examen["pruebas_hechas"] == 4
	assert len(examen["relaciones_acertadas"]) == 2
	sin_valorar(jugador)


def test_examen_de_reconstruccion_definido_por_el_profesional():
	entorno = casa_vacia()
	salon, cocina, bano, dormitorio = (espacio_en(entorno, x, y) for x, y in ((2.0, 2.0), (6.0, 2.0), (5.5, 7.0), (2.0, 7.0)))
	datos = nueva_actividad(
		"examen_reconstruccion",
		entorno,
		pruebas=[{"referencia": salon.id, "direccion": "este", "correcta": cocina.id, "opciones": [bano.id, dormitorio.id]}],
		regla_parada=None,
	)
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	assert "¿Qué hay al este de Salón?" in jugador.dicho()
	assert sorted(jugador.actividad.estado()["pregunta"]["opciones"]) == ["Baño", "Cocina", "Dormitorio"]


# ── El profesional en un examen ──────────────────────────────────────────────


def test_pista_del_profesional_en_un_examen_queda_anotada():
	entorno = casa_vacia()
	salon, cocina = espacio_en(entorno, 2.0, 2.0), espacio_en(entorno, 6.0, 2.0)
	datos = nueva_actividad("examen_rutas", entorno, pruebas=[ruta_definida(entorno, salon.id, cocina.id)], regla_parada=None)
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	eventos = jugador.actividad.orden_profesional(jugador.sesion, "pista", {"texto": "Sal al pasillo y gira a la derecha"})
	assert any(isinstance(e, ev.EvVoz) and e.canal == "profesional" for e in eventos)
	jugador.ir_a_espacio(cocina.id)
	jugador.pulsar("interactuar")
	resultado = jugador.fin
	assert resultado["examen"]["pruebas"][0]["con_ayuda_profesional"] is True and resultado["examen"]["con_ayuda_profesional"] == 1
	assert resultado["intervenciones_profesional"] == {"pista": 1}


def test_examen_abandonado_no_esta_completado():
	entorno = casa_vacia()
	jugador = Jugador(entorno, nueva_actividad("examen_rutas", entorno, numero_pruebas=4, regla_parada=None))
	jugador.tic(3)
	jugador.confirmar()
	jugador.sesion.terminar()
	jugador.tic(1)
	resultado = jugador.fin
	assert resultado["completada"] is False and resultado["motivo"] == "abandonada"
	assert resultado["examen"]["pruebas_hechas"] == 1 and resultado["examen"]["pruebas_total"] == 4
