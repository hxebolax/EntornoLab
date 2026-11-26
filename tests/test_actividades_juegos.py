"""Los juegos, jugados de principio a fin por el robot en los entornos de ejemplo."""

from __future__ import annotations

import math

from app.actividades import nueva_actividad, plantillas_de, repartir_premios
from app.motor import eventos as ev
from app.motor.sesion import AjustesJuego
from tests.test_actividades_comun import Jugador, barrio, catalogo_real, centro, ejemplo, espacio_en, presentar, vivienda
from tests.test_motor_comun import registros, sonidos, vibraciones


def casa_vacia():
	"""La vivienda sin muebles: para las pruebas en las que importa la geometría y no los objetos."""
	return ejemplo("vivienda-de-ejemplo", False)


def premio(ident: str, nombre: str, x: float, y: float, planta: str = "pla-1", **extra) -> dict:
	dato = {"id": ident, "nombre": nombre, "planta": planta, "x": x, "y": y, "visibilidad": "cerca"}
	dato.update(extra)
	return dato


def hay_baliza(eventos: list) -> bool:
	return any(s.startswith("baliza/") for s in sonidos(eventos))


# ── Búsqueda ─────────────────────────────────────────────────────────────────


def test_busqueda_infantil_con_premios_dentro_de_objetos():
	"""La plantilla infantil de la vivienda: premios dentro de muebles del catálogo real, sueltos y uno que se oye de lejos."""
	entorno = vivienda()
	datos = plantillas_de("vivienda-de-ejemplo", entorno, catalogo_real())[0]
	assert datos["tipo"] == "busqueda" and datos["estilo"] == "infantil"
	dentro = [p for p in datos["premios"] if p["dentro_de"]]
	assert len(dentro) >= 3
	jugador = Jugador(entorno, datos, estilo="adulto")
	assert "Tiko ha escondido cinco tesoros" in jugador.dicho()
	assert jugador.actividad.estado()["total"] == 5
	# Los premios son fuentes de sonido de la sesión; el que se oye desde lejos tiene mucho más alcance.
	extras = jugador.sesion.acustica.extras
	assert extras["premio:estrella"].radio > extras["premio:patito"].radio
	primero = dentro[0]
	antes = len(jugador.eventos)
	# Hay que usar el mueble: el premio sale al interactuar con él.
	jugador.usar(primero["dentro_de"])
	recogido = registros(jugador.eventos[antes:], "premio")[0]
	assert recogido["id"] == primero["id"] and recogido["dentro_de"] == primero["dentro_de"]
	assert "¡Sorpresa! Dentro estaba" in jugador.dicho(antes)
	assert "premio/recogido" in sonidos(jugador.eventos[antes:])
	for dato in datos["premios"][1:]:
		if dato["dentro_de"]:
			jugador.usar(dato["dentro_de"])
		else:
			jugador.ir((dato["planta"], dato["x"], dato["y"]), cerca=0.3)
	resultado = jugador.fin
	assert resultado is not None and resultado["completada"] is True
	assert resultado["objetivos_hechos"] == 5 and resultado["objetivos_total"] == 5
	assert [p["id"] for p in jugador.registrados("premio")] == [o["id"] for o in jugador.registrados("objetivo")]
	assert len(resultado["coleccion"]) == 5
	assert "completar" in resultado["estrellas_motivos"]
	# Cada recompensa sale además como registro, que es lo que lee el seguimiento.
	assert len(jugador.registrados("recompensa")) == len(resultado["recompensas"])
	assert {r["tipo"] for r in resultado["recompensas"]} >= {"estrella", "objeto"}
	assert "premio/tesoro" in sonidos(jugador.eventos)
	assert resultado["cuestionario"] and resultado["valoracion"] is None
	assert "simulador" in resultado["aviso"]
	# El estilo lo fija la actividad (infantil), aunque la ficha del alumno diga otra cosa.
	assert resultado["actividad"]["estilo"] == "infantil"
	assert jugador.sesion.ajustes.estilo == "infantil"


def test_pasar_junto_al_mueble_no_basta():
	entorno = vivienda()
	datos = plantillas_de("vivienda-de-ejemplo", entorno, catalogo_real())[0]
	primero = next(p for p in datos["premios"] if p["dentro_de"])
	jugador = Jugador(entorno, datos)
	info = jugador.sesion.mundo.objeto(primero["dentro_de"])
	ruta = jugador.sesion.nav.ruta(jugador.sesion.inicio, (info.planta_id, info.objeto.x, info.objeto.y))
	for _planta, x, y in ruta.puntos[1:-1]:
		jugador.ir_a(x, y)
	jugador.tic(5)
	assert primero["id"] not in [p["id"] for p in jugador.registrados("premio")]


def test_busqueda_adulta_prepara_la_visita_es_sobria():
	entorno = vivienda()
	datos = plantillas_de("vivienda-de-ejemplo", entorno, catalogo_real())[1]
	jugador = Jugador(entorno, datos)
	dicho = jugador.dicho()
	assert "Prepara la visita: encuentra las llaves, el abrigo y el paraguas." in dicho
	assert "¡" not in dicho
	# Los premios ocultos no suenan: no son fuentes de la sesión hasta que se abre el mueble.
	assert "premio:llaves" not in jugador.sesion.acustica.extras
	assert "premio:paraguas" in jugador.sesion.acustica.extras
	for dato in datos["premios"]:
		if dato["dentro_de"]:
			jugador.usar(dato["dentro_de"])
		else:
			jugador.ir((dato["planta"], dato["x"], dato["y"]), cerca=0.3)
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["actividad"]["estilo"] == "adulto"
	propias = [
		t
		for t in jugador.dicho().split(" | ")
		if "Encontrado" in t or "Dentro estaba" in t or "Actividad completada" in t or "Ya lo tienes" in t
	]
	assert propias and all("¡" not in frase for frase in propias)


def test_busqueda_en_orden_solo_suena_el_que_toca():
	entorno = casa_vacia()
	datos = nueva_actividad(
		"busqueda",
		entorno,
		premios=[premio("a", "la pelota", 6.0, 2.0), premio("b", "el libro", 2.0, 2.0)],
		orden_obligatorio=True,
	)
	jugador = Jugador(entorno, datos)
	assert set(jugador.sesion.acustica.extras) & {"premio:a", "premio:b"} == {"premio:a"}
	# Pisar el segundo antes de tiempo no lo recoge.
	jugador.ir(("pla-1", 2.0, 2.0), cerca=0.3)
	assert jugador.registrados("premio") == []
	jugador.ir(("pla-1", 6.0, 2.0), cerca=0.3)
	assert [p["id"] for p in jugador.registrados("premio")] == ["a"]
	assert "premio:b" in jugador.sesion.acustica.extras
	jugador.ir(("pla-1", 2.0, 2.0), cerca=0.3)
	assert jugador.fin["completada"] is True


def test_vibracion_al_estar_cerca_de_un_premio():
	entorno = casa_vacia()
	datos = nueva_actividad(
		"busqueda", entorno, premios=[premio("a", "la pelota", 3.0, 4.6), premio("b", "el libro", 6.0, 2.0, vibrar=False)]
	)
	jugador = Jugador(entorno, datos)
	jugador.ir(("pla-1", 1.4, 4.6), cerca=0.2)
	jugador.jugar(2.0)
	assert "premio_cerca" in vibraciones(jugador.eventos)
	assert jugador.registrados("premio") == []


def test_estilos_distintos_mismo_contenido():
	"""Los tres estilos dicen cosas distintas con los mismos premios y la misma puntuación."""
	entorno = casa_vacia()
	frases = {}
	resultados = {}
	for estilo in ("infantil", "juvenil", "adulto"):
		datos = nueva_actividad("busqueda", entorno, premios=[premio("a", "la pelota", 3.0, 4.6)])
		jugador = Jugador(entorno, datos, estilo=estilo)
		jugador.ir(("pla-1", 3.0, 4.6), cerca=0.3)
		frases[estilo] = jugador.dicho()
		resultados[estilo] = jugador.fin
	assert len(set(frases.values())) == 3
	assert "¡A buscar tesoros!" in frases["infantil"] and "Misión" in frases["juvenil"] and "Prepara la visita" in frases["adulto"]
	# El personaje acompañante solo existe en el estilo infantil.
	assert "Soy Tiko y voy contigo." in frases["infantil"]
	assert "Tiko" not in frases["juvenil"] and "Tiko" not in frases["adulto"]
	assert len({r["estrellas"] for r in resultados.values()}) == 1
	assert resultados["infantil"]["recompensas"][0]["nombre"] != resultados["adulto"]["recompensas"][0]["nombre"]
	assert "Tu marca" in frases["juvenil"]


# ── Pistas encadenadas ───────────────────────────────────────────────────────


def test_pistas_cada_premio_da_la_pista_del_siguiente():
	entorno = casa_vacia()
	datos = nueva_actividad(
		"pistas",
		entorno,
		premios=[
			premio("a", "el primer sobre", 6.0, 2.0),
			premio("b", "el segundo sobre", 2.0, 7.0, pista="Mira donde se duerme."),
			premio("c", "el tercer sobre", 2.0, 2.0),
		],
	)
	jugador = Jugador(entorno, datos, estilo="juvenil")
	# La primera pista se redacta sola con una relación real: la cocina queda al este del salón.
	assert "Primera pista: Está en la habitación que queda al este de Salón." in jugador.dicho()
	assert set(jugador.sesion.acustica.extras) & {"premio:a", "premio:b", "premio:c"} == {"premio:a"}
	antes = len(jugador.eventos)
	jugador.ir(("pla-1", 6.0, 2.0), cerca=0.3)
	jugador.tic(20)
	# La segunda es la que escribió el profesional.
	assert "Pista del siguiente: Mira donde se duerme." in jugador.dicho(antes)
	assert "logro/pista" in sonidos(jugador.eventos[antes:])
	antes = len(jugador.eventos)
	jugador.ir(("pla-1", 2.0, 7.0), cerca=0.3)
	jugador.tic(20)
	assert "que queda al" in jugador.dicho(antes)
	# Pedir pista una vez repite la de la cadena; insistir dice la habitación.
	jugador.pulsar("pista")
	antes = len(jugador.eventos)
	jugador.pulsar("pista")
	assert "Está en Salón." in jugador.dicho(antes)
	jugador.ir(("pla-1", 2.0, 2.0), cerca=0.3)
	assert jugador.fin["completada"] is True
	assert jugador.fin["ayudas_usadas"]["pista"] == 2


# ── Sacar los tesoros ────────────────────────────────────────────────────────


def tesoros_del_centro() -> dict:
	return nueva_actividad(
		"sacar_tesoros",
		centro(),
		catalogo_real(),
		estilo="juvenil",
		premios=[premio("a", "el trofeo", 19.0, 7.0), premio("b", "el mapa", 1.0, 7.0)],
	)


def test_sacar_tesoros_puntua_la_salida_elegida():
	"""Tesoro junto a la salida este: sacarlo por ella vale 3; el otro, junto a la oeste, sacado por la principal vale menos."""
	entorno = centro()
	jugador = Jugador(entorno, tesoros_del_centro())
	baja = entorno.plantas[0]
	salidas = {a.nombre: a.id for a in baja.aberturas if a.es_salida}
	assert len(salidas) == 3
	assert "salida más cercana" in jugador.dicho()
	jugador.ir(("pla-1", 19.0, 7.0), cerca=0.3)
	assert jugador.actividad.estado()["fase"] == "sacar"
	assert "Llevas el trofeo" in jugador.actividad.estado()["objetivo"]
	# Mientras se lleva uno, los demás callan.
	assert "premio:b" not in jugador.sesion.acustica.extras
	antes = len(jugador.eventos)
	jugador.salir_por(salidas["Salida de emergencia este"])
	puntuada = registros(jugador.eventos[antes:], "salida_puntuada")[0]
	assert puntuada["puntos"] == 3 and puntuada["salida_mas_cercana"] == salidas["Salida de emergencia este"]
	assert "A salvo por la salida más corta. 3 puntos." in jugador.dicho(antes)
	# Se le devuelve adentro para seguir jugando.
	assert jugador.espacio == "Pasillo de la planta baja"
	assert not jugador.sesion.terminado
	jugador.ir(("pla-1", 1.0, 7.0), cerca=0.3)
	antes = len(jugador.eventos)
	jugador.salir_por(salidas["Puerta principal"])
	puntuada = registros(jugador.eventos[antes:], "salida_puntuada")[0]
	assert puntuada["puntos"] < 3 and puntuada["salida_mas_cercana"] == salidas["Salida de emergencia oeste"]
	assert "había una salida más cerca" in jugador.dicho(antes)
	resultado = jugador.fin
	assert resultado["completada"] is True
	assert resultado["puntos"] == 3 + puntuada["puntos"] and resultado["puntos_maximos"] == 6
	# La puntuación de salida del juego va en «puntuaciones» (es la que predice el rendimiento real), no en «examen».
	assert resultado["examen"] is None
	assert resultado["puntuaciones"]["medida"] == "salida_mas_corta"
	assert [p["puntos"] for p in resultado["puntuaciones"]["pruebas"]] == [3, puntuada["puntos"]]
	assert resultado["puntuaciones"]["pruebas"][0]["cociente"] is not None
	# La principal es la segunda más cercana desde allí: 2 puntos. Con media 2,5 hay estrella de salida, pero no la medalla de pleno.
	assert puntuada["puntos"] == 2 and resultado["puntuaciones"]["media_puntos"] == 2.5
	assert "salida_optima" in resultado["estrellas_motivos"]
	assert not any(r["motivo"] == "salidas" for r in resultado["recompensas"])
	assert jugador.registrados("puntuacion")[0]["puntos"] == resultado["puntos"]


def test_sacar_tesoros_salir_sin_tesoro_no_puntua():
	entorno = centro()
	jugador = Jugador(entorno, tesoros_del_centro())
	principal = next(a.id for a in entorno.plantas[0].aberturas if a.es_salida and a.hoja == "automatica")
	antes = len(jugador.eventos)
	jugador.salir_por(principal)
	assert "Has salido sin llevar nada" in jugador.dicho(antes)
	assert jugador.espacio == "Vestíbulo"
	assert jugador.registrados("salida_puntuada") == []


# ── Escondite ────────────────────────────────────────────────────────────────


def test_escondite_por_rondas():
	entorno = casa_vacia()
	datos = nueva_actividad("escondite", entorno, rondas=2, cada_s=1.0, personaje="Rita")
	jugador = Jugador(entorno, datos, estilo="infantil", semilla=3)
	assert "Rita se ha escondido" in jugador.dicho()
	sitios = []
	for ronda in range(2):
		escondite = jugador.actividad._lugar_actual()
		assert escondite is not None
		sitios.append(escondite.terna)
		# Es una fuente de la sesión que suena a intervalos desde donde está.
		emisor = jugador.sesion.acustica.extras["escondite"]
		assert (emisor.planta_id, emisor.x, emisor.y) == escondite.terna and emisor.intervalo == 1.0
		jugador.ir(escondite.terna, cerca=0.4)
		assert jugador.actividad.estado()["hechos"] == ronda + 1
	assert sitios[0] != sitios[1]
	resultado = jugador.fin
	assert resultado["completada"] is True and len(resultado["rondas"]) == 2
	assert resultado["cociente_camino"] is not None
	assert "escondite" not in jugador.sesion.acustica.extras


def test_acompanante_con_nombre_propio_o_sin_el():
	entorno = casa_vacia()
	con_nombre = Jugador(entorno, nueva_actividad("explorador", entorno, acompanante="Nube"), estilo="infantil")
	assert "Soy Nube y voy contigo." in con_nombre.dicho()
	con_nombre.tic(700, dt=0.25)
	assert "Nube dice: ¡tú puedes!" in con_nombre.dicho()
	sin_el = Jugador(entorno, nueva_actividad("explorador", entorno, con_acompanante=False), estilo="infantil")
	assert "voy contigo" not in sin_el.dicho()
	examen = Jugador(entorno, nueva_actividad("examen_rutas", entorno, regla_parada=None), estilo="infantil")
	assert "voy contigo" not in examen.dicho()


def test_escondite_adulto_es_un_telefono():
	jugador = Jugador(casa_vacia(), nueva_actividad("escondite", casa_vacia(), rondas=1))
	assert "Suena el teléfono en algún lugar. Localízalo por el sonido." in jugador.dicho()


# ── Sigue al guía ────────────────────────────────────────────────────────────


def test_sigue_al_guia_por_sus_pasos():
	entorno = casa_vacia()
	cocina = espacio_en(entorno, 6.0, 2.0)
	datos = nueva_actividad("sigue_guia", entorno, destino=cocina.id, velocidad_guia=1.5, distancia_espera=3.0)
	jugador = Jugador(entorno, datos, estilo="infantil")
	assert "¡Sígueme!" in jugador.dicho()
	# El guía echa a andar y se le oyen los pasos del suelo que pisa.
	jugador.jugar(2.0)
	assert [s for s in sonidos(jugador.eventos) if s.startswith("pasos/")]
	# Si el alumno no le sigue, se para a esperar y le llama, en vez de irse.
	antes = len(jugador.eventos)
	jugador.jugar(12.0)
	guia = jugador.actividad._lugar_actual()
	assert "Por aquí" in jugador.dicho(antes)
	assert jugador.sesion.distancia_a(guia.terna) < 5.0
	assert not jugador.sesion.terminado
	# Siguiéndole de cerca se llega al destino.
	for _vuelta in range(60):
		if jugador.sesion.terminado:
			break
		guia = jugador.actividad._lugar_actual()
		jugador.ir(guia.terna, cerca=1.0, intentos=1)
		jugador.jugar(1.0)
	resultado = jugador.fin
	assert resultado is not None and resultado["completada"] is True
	assert resultado["destino"]["id"] == cocina.id
	assert 0.0 < resultado["tiempo_cerca_del_guia"] <= 1.0
	assert "¡Hemos llegado a Cocina!" in jugador.dicho()


# ── Explorador ───────────────────────────────────────────────────────────────


def test_explorador_cada_espacio_nuevo_suena_a_hallazgo():
	entorno = casa_vacia()
	jugador = Jugador(entorno, nueva_actividad("explorador", entorno), estilo="juvenil")
	planta = entorno.plantas[0]
	total = len([e for e in planta.espacios if not e.macizo])
	assert jugador.actividad.estado()["total"] == total == 6
	jugador.tic(3)
	# El espacio donde se empieza ya cuenta.
	assert jugador.actividad.estado()["hechos"] == 1
	for espacio in planta.espacios:
		jugador.ir_a_espacio(espacio.id)
		jugador.tic(2)
	assert sonidos(jugador.eventos).count("premio/aparece") == total
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["exploracion"] == 1.0
	assert "exploracion" in resultado["estrellas_motivos"]
	assert any(r["tipo"] == "medalla" for r in resultado["recompensas"])
	assert len(jugador.registrados("objetivo")) == total


# ── Cruces ───────────────────────────────────────────────────────────────────


def test_cruce_por_el_paso_con_semaforo():
	"""En el barrio: cruzar en rojo por el paso puntúa 1 y cruzar en verde, 3. Usa los registros de cruce del motor."""
	entorno = barrio()
	datos = nueva_actividad("cruce", entorno, catalogo_real(), cruces=2, trafico=False, estilo="adulto")
	jugador = Jugador(entorno, datos)
	assert "no dice si un cruce real es seguro" in jugador.dicho()
	paso = next(e for e in entorno.plantas[0].espacios if e.tipo == "paso_peatones" and e.datos.get("semaforo"))
	dinamica = jugador.sesion.dinamica
	# El paso está en x de -10 a -6 y la calzada en y de -3,5 a 3,5.
	jugador.ir(("pla-1", -8.0, 4.4), cerca=0.4)

	def esperar_fase(fase: str) -> None:
		for _i in range(4000):
			if dinamica.fase(paso.id) == fase:
				return
			jugador.tic(1, dt=0.25)
		raise AssertionError(f"el semáforo no llega a {fase}")

	esperar_fase("rojo")
	antes = len(jugador.eventos)
	jugador.ir_a(-8.0, -4.4)
	jugador.tic(3)
	primero = registros(jugador.eventos[antes:], "cruce_puntuado")[0]
	assert primero["por_paso"] is True and primero["en_rojo"] is True and primero["puntos"] == 1
	assert "semáforo en rojo" in jugador.dicho(antes)
	esperar_fase("verde")
	antes = len(jugador.eventos)
	jugador.ir_a(-8.0, 4.4)
	jugador.tic(3)
	segundo = registros(jugador.eventos[antes:], "cruce_puntuado")[0]
	assert segundo["puntos"] == 3 and segundo["en_rojo"] is False
	resultado = jugador.fin
	assert resultado["completada"] is True
	assert resultado["puntuaciones"]["medida"] == "cruces" and resultado["puntos"] == 4 and resultado["puntos_maximos"] == 6
	assert resultado["puntuaciones"]["cruces_en_rojo"] == 1
	assert "seguridad" not in resultado["estrellas_motivos"]


# ── Travieso, contrarreloj y pausas ──────────────────────────────────────────


def test_el_travieso_recoloca_un_premio():
	entorno = casa_vacia()
	datos = nueva_actividad(
		"busqueda",
		entorno,
		premios=[premio("a", "la pelota", 6.0, 2.0)],
		travieso={"activo": True, "cada_s": 5, "veces": 1},
	)
	jugador = Jugador(entorno, datos, estilo="infantil", semilla=11)
	jugador.jugar(6.0)
	movido = jugador.registrados("travieso")
	assert len(movido) == 1 and movido[0]["id"] == "a"
	assert "El travieso ha cambiado un premio de sitio" in jugador.dicho()
	nuevo = jugador.actividad.premios[0]
	assert (nuevo.x, nuevo.y) != (6.0, 2.0)
	assert espacio_en(entorno, nuevo.x, nuevo.y).nombre != "Cocina"
	# Solo una travesura, como se pidió.
	jugador.jugar(12.0)
	assert len(jugador.registrados("travieso")) == 1
	# En el sitio viejo ya no está; en el nuevo, sí.
	jugador.ir(("pla-1", 6.0, 2.0), cerca=0.3)
	assert jugador.registrados("premio") == []
	jugador.ir(nuevo.terna, cerca=0.3)
	assert jugador.fin["completada"] is True and jugador.fin["travesuras"] == 1


def test_contrarreloj_no_cuenta_las_pausas():
	entorno = casa_vacia()
	datos = nueva_actividad("busqueda", entorno, premios=[premio("a", "la pelota", 6.0, 2.0)], tiempo_limite_s=90)
	jugador = Jugador(entorno, datos)
	assert "Tienes 1 minuto y 30 segundos." in jugador.dicho()
	jugador.tic(40, dt=0.25)
	resto = jugador.actividad.estado()["tiempo_restante"]
	assert 79.0 <= resto <= 80.0
	# Cinco minutos en pausa: el tiempo de la actividad no corre.
	jugador.sesion.pausar(True)
	jugador.tic(1200, dt=0.25)
	jugador.sesion.pausar(False)
	jugador.tic(1)
	assert not jugador.sesion.terminado
	assert jugador.actividad.estado()["tiempo_restante"] > resto - 1.0
	antes = len(jugador.eventos)
	jugador.tic(100, dt=0.25)
	assert "Queda un minuto." in jugador.dicho(antes)
	jugador.tic(260, dt=0.25)
	resultado = jugador.fin
	assert resultado is not None and resultado["completada"] is False and resultado["fuera_de_tiempo"] is True
	assert resultado["motivo"] == "tiempo"
	assert resultado["tiempo_pausa"] >= 290 and 89 <= resultado["tiempo_juego_s"] <= 92
	assert resultado["estrellas"] == 0
	assert "Se ha agotado el tiempo." in jugador.dicho()


def test_sin_contrarreloj_no_hay_limite():
	entorno = casa_vacia()
	datos = nueva_actividad("busqueda", entorno, premios=[premio("a", "la pelota", 6.0, 2.0)])
	assert datos["tiempo_limite_s"] is None
	jugador = Jugador(entorno, datos)
	jugador.tic(2000, dt=0.25)
	assert not jugador.sesion.terminado and jugador.actividad.estado()["tiempo_restante"] is None


# ── Niveles, ayudas y tropiezos ──────────────────────────────────────────────


def test_niveles_retiran_las_ayudas_poco_a_poco():
	entorno = casa_vacia()
	cocina = espacio_en(entorno, 6.0, 2.0)
	datos = nueva_actividad("ruta", entorno, destino=cocina.id, usar_niveles=True)
	assert [n["baliza"] for n in datos["niveles"]] == ["siempre", "al_pedir", "nunca", "nunca"]
	# Nivel 0: la baliza suena sola, paso a paso.
	jugador = Jugador(entorno, datos, nivel=0)
	jugador.jugar(3.0)
	assert hay_baliza(jugador.eventos)
	jugador.ir_a_espacio(cocina.id)
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["baliza_continua"] is True
	assert resultado["nivel"] == 0 and resultado["nivel_superado"] is True and resultado["nivel_siguiente"] == 1
	# Ganar nunca depende solo de seguir una baliza: con ella puesta no hay estrella de pocas ayudas.
	assert "pocas_ayudas" not in resultado["estrellas_motivos"]
	assert "Nivel superado. La próxima vez: Baliza solo al pedirla." in jugador.dicho()
	assert any(r["tipo"] == "medalla" for r in resultado["recompensas"])
	# Nivel 1: solo suena un rato al pedir una pista, y pedirla impide subir de nivel.
	jugador = Jugador(entorno, datos, nivel=resultado["nivel_siguiente"])
	jugador.jugar(3.0)
	assert not hay_baliza(jugador.eventos)
	antes = len(jugador.eventos)
	jugador.pulsar("pista")
	jugador.jugar(3.0)
	assert hay_baliza(jugador.eventos[antes:])
	assert "Una baliza sonará unos segundos desde allí." in jugador.dicho(antes)
	jugador.jugar(25.0)
	antes = len(jugador.eventos)
	jugador.jugar(3.0)
	assert not hay_baliza(jugador.eventos[antes:])
	jugador.ir_a_espacio(cocina.id)
	assert jugador.fin["nivel_superado"] is False and jugador.fin["nivel_siguiente"] == 1
	# Nivel 2: sin baliza ni siquiera al pedir pista.
	jugador = Jugador(entorno, datos, nivel=2)
	assert jugador.sesion.ajustes.ayudas["baliza"]["permitida"] is False
	antes = len(jugador.eventos)
	jugador.pulsar("pista")
	jugador.jugar(3.0)
	assert not hay_baliza(jugador.eventos[antes:])
	jugador.pulsar("donde_estoy")
	assert jugador.registrados("ayuda_denegada") == []
	# Nivel 3: además sin «dónde estoy».
	jugador = Jugador(entorno, datos, nivel=3)
	jugador.pulsar("donde_estoy")
	assert jugador.registrados("ayuda_denegada")[0]["ayuda"] == "donde_estoy"
	jugador.ir_a_espacio(cocina.id)
	final = jugador.fin
	assert final["nivel"] == 3 and final["nivel_superado"] is True and final["nivel_siguiente"] == 3
	assert "pocas_ayudas" in final["estrellas_motivos"]


def test_limites_de_ayudas_de_la_actividad():
	entorno = casa_vacia()
	cocina = espacio_en(entorno, 6.0, 2.0)
	datos = nueva_actividad("ruta", entorno, destino=cocina.id, ayudas={"donde_estoy": 1, "sonda": False})
	jugador = Jugador(entorno, datos)
	assert jugador.sesion.ajustes.ayudas["donde_estoy"] == {"permitida": True, "limite": 1}
	jugador.pulsar("donde_estoy")
	jugador.pulsar("donde_estoy")
	jugador.pulsar("sonda")
	denegadas = {(d["ayuda"], d["motivo"]) for d in jugador.registrados("ayuda_denegada")}
	assert denegadas == {("donde_estoy", "agotada"), ("sonda", "prohibida")}
	# Los ajustes de la ficha no se tocan: la actividad devuelve una copia.
	base = AjustesJuego()
	retocados = jugador.actividad.ajustes(base)
	assert base.ayudas == {} and retocados.ayudas["sonda"]["permitida"] is False


def test_tras_varios_tropiezos_se_ofrece_ayuda_en_vez_de_insistir():
	entorno = casa_vacia()
	datos = nueva_actividad("busqueda", entorno, premios=[premio("a", "la pelota", 6.0, 2.0)], fallos_para_ayuda=1, baliza="nunca")
	jugador = Jugador(entorno, datos, estilo="juvenil")
	# Chocar informa pero no elimina: tras muchos choques seguidos la partida sigue y se ofrece una pista.
	jugador.girar_a(270.0)
	for _i in range(8):
		jugador.pulsar("avanzar", 1)
	jugador.tic(3)
	assert jugador.sesion.movimiento.choques >= 4
	assert not jugador.sesion.terminado
	assert jugador.registrados("ayuda_ofrecida")[0]["motivo"] == "choques"
	assert "¿Atascado? Puedes pedir una pista." in jugador.dicho()
	# La pista ofrecida viene con baliza un rato, aunque la actividad no la tuviera.
	antes = len(jugador.eventos)
	jugador.pulsar("pista")
	jugador.jugar(3.0)
	assert hay_baliza(jugador.eventos[antes:])
	jugador.ir(("pla-1", 6.0, 2.0), cerca=0.3)
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["ayudas_ofrecidas"] == 1 and resultado["fallos"] >= 1
	assert "sin_choques" not in resultado["estrellas_motivos"]


def test_sin_avance_durante_mucho_rato_tambien_se_ofrece_ayuda():
	entorno = casa_vacia()
	datos = nueva_actividad("busqueda", entorno, premios=[premio("a", "la pelota", 6.0, 2.0)])
	jugador = Jugador(entorno, datos)
	jugador.tic(700, dt=0.25)
	assert jugador.registrados("ayuda_ofrecida")[0]["motivo"] == "sin_avance"


# ── Órdenes del profesional ──────────────────────────────────────────────────


def test_ordenes_del_profesional():
	entorno = casa_vacia()
	datos = nueva_actividad("busqueda", entorno, premios=[premio("a", "la pelota", 6.0, 2.0)], baliza="nunca")
	jugador = Jugador(entorno, datos, estilo="infantil")
	actividad, sesion = jugador.actividad, jugador.sesion
	# Mensaje: voz por el canal del profesional.
	eventos = actividad.orden_profesional(sesion, "mensaje", {"texto": "Sigue la pared"})
	assert [(e.texto, e.canal) for e in eventos if isinstance(e, ev.EvVoz)] == [("Sigue la pared", "profesional")]
	# Premio en caliente en una posición: suena, se suma al total y se puede recoger.
	eventos = actividad.orden_profesional(
		sesion, "premio", {"nombre": "la sorpresa", "planta": "pla-1", "x": 3.0, "y": 4.6, "mensaje": "De parte de mamá."}
	)
	assert any(isinstance(e, ev.EvSonido) and e.nombre == "premio/aparece" for e in eventos)
	assert any(isinstance(e, ev.EvVoz) and "la sorpresa" in e.texto for e in eventos)
	presentar(jugador, eventos)
	assert actividad.estado()["total"] == 2
	assert len([ident for ident in sesion.acustica.extras if ident.startswith("premio:")]) == 2
	# Un premio en un sitio imposible no entra en juego.
	malos = actividad.orden_profesional(sesion, "premio", {"nombre": "x", "planta": "no-existe", "x": 0, "y": 0})
	assert [e.nombre for e in malos] == ["logro/error"] and actividad.estado()["total"] == 2
	antes = len(jugador.eventos)
	jugador.ir(("pla-1", 3.0, 4.6), cerca=0.3)
	assert "De parte de mamá." in jugador.dicho(antes)
	# Ayudas: cambia los permisos en marcha.
	actividad.orden_profesional(sesion, "ayudas", {"ayudas": {"donde_estoy": {"permitida": False, "limite": None}}})
	jugador.pulsar("donde_estoy")
	assert jugador.registrados("ayuda_denegada")[0]["ayuda"] == "donde_estoy"
	# Pista con baliza: suena aunque la actividad no tenga baliza, y queda anotada.
	antes = len(jugador.eventos)
	eventos = actividad.orden_profesional(sesion, "pista", {"texto": "Está en la cocina", "baliza_s": 5})
	presentar(jugador, eventos)
	jugador.jugar(3.0)
	assert "Está en la cocina" in jugador.dicho(antes)
	assert hay_baliza(jugador.eventos[antes:])
	jugador.jugar(4.0)
	antes = len(jugador.eventos)
	jugador.jugar(3.0)
	assert not hay_baliza(jugador.eventos[antes:])
	# Una orden que no existe no rompe nada.
	assert actividad.orden_profesional(sesion, "bailar", {}) == []
	jugador.ir(("pla-1", 6.0, 2.0), cerca=0.3)
	resultado = jugador.fin
	assert resultado["completada"] is True
	assert resultado["intervenciones_profesional"] == {"mensaje": 1, "premio": 2, "ayudas": 1, "pista": 1, "bailar": 0}
	assert resultado["ayudas_contadas"] >= 1


def test_premio_del_profesional_sin_lugar_cae_cerca_del_alumno():
	entorno = casa_vacia()
	jugador = Jugador(entorno, nueva_actividad("exploracion", entorno))
	eventos = jugador.actividad.orden_profesional(jugador.sesion, "premio", {"nombre": "la sorpresa"})
	assert any(isinstance(e, ev.EvSonido) for e in eventos)
	nuevo = jugador.actividad.premios[-1]
	assert espacio_en(entorno, nuevo.x, nuevo.y).nombre == jugador.espacio
	jugador.ir(nuevo.terna, cerca=0.3)
	assert [p["nombre"] for p in jugador.registrados("premio")] == ["la sorpresa"]
	assert not jugador.sesion.terminado


# ── Valoración y reparto en juego ────────────────────────────────────────────


def test_valoracion_al_terminar():
	entorno = casa_vacia()
	datos = nueva_actividad("busqueda", entorno, premios=[premio("a", "la pelota", 3.0, 4.6)], cuestionario=True)
	jugador = Jugador(entorno, datos, estilo="infantil")
	jugador.ir(("pla-1", 3.0, 4.6), cerca=0.3)
	resultado = jugador.fin
	assert [p["id"] for p in resultado["cuestionario"]] == ["esfuerzo", "confianza", "disfrute"]
	limpias = jugador.actividad.valorar(jugador.sesion, {"esfuerzo": 2, "confianza": 9, "disfrute": 5})
	assert limpias == {"esfuerzo": 2, "confianza": None, "disfrute": 5}
	jugador.tic(1)
	assert jugador.registrados("valoracion")[0]["disfrute"] == 5
	assert jugador.sesion.resultado["valoracion"]["esfuerzo"] == 2


def test_reparto_asistido_jugado_entero():
	"""Un reparto de seis premios por la vivienda amueblada se puede jugar entero y obliga a entrar en todas las habitaciones."""
	entorno = vivienda()
	premios = repartir_premios(entorno, 6, catalogo_real(), semilla=4)
	datos = nueva_actividad("busqueda", entorno, catalogo_real(), premios=premios)
	jugador = Jugador(entorno, datos)
	for dato in premios:
		if dato["dentro_de"]:
			jugador.usar(dato["dentro_de"])
		else:
			jugador.ir((dato["planta"], dato["x"], dato["y"]), cerca=0.3)
	resultado = jugador.fin
	assert resultado is not None and resultado["completada"] is True
	assert resultado["exploracion"] == 1.0
	assert not math.isnan(resultado["tiempo_juego_s"])
