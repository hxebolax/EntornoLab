"""Las prácticas, jugadas de principio a fin por el robot: exploración, visita, rutas, recados, sala y línea guía."""

from __future__ import annotations

from app.actividades import nueva_actividad, plantillas_de
from app.dominio import edicion as ed
from app.dominio import geometria as geo
from tests.test_actividades_comun import Jugador, barrio, catalogo_real, centro, ejemplo, espacio_en
from tests.test_motor_comun import registros, sonidos


def casa_vacia():
	return ejemplo("vivienda-de-ejemplo", False)


def hay_baliza(eventos: list) -> bool:
	return any(s.startswith("baliza/") for s in sonidos(eventos))


# ── Exploración libre y visita guiada ────────────────────────────────────────


def test_exploracion_libre_no_tiene_final_ni_se_falla():
	entorno = casa_vacia()
	jugador = Jugador(entorno, nueva_actividad("exploracion", entorno), estilo="infantil")
	assert "¡A explorar!" in jugador.dicho()
	jugador.ir_a_espacio(espacio_en(entorno, 6.0, 2.0).id)
	jugador.tic(800, dt=0.25)
	# Ni se termina sola ni ofrece ayuda: no hay nada en lo que atascarse.
	assert not jugador.sesion.terminado and jugador.registrados("ayuda_ofrecida") == []
	assert jugador.actividad.estado()["hechos"] == 3 and jugador.actividad.estado()["total"] == 6
	jugador.sesion.terminar()
	jugador.tic(1)
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["motivo"] == "terminada"
	assert resultado["exploracion"] == 0.5 and resultado["estrellas"] == 0


def test_visita_guiada_con_textos_preparados():
	entorno = casa_vacia()
	cocina, salon = espacio_en(entorno, 6.0, 2.0), espacio_en(entorno, 2.0, 2.0)
	datos = nueva_actividad(
		"visita_guiada",
		entorno,
		objetivos=[
			{"destino": cocina.id, "texto": "Aquí se desayuna. El frigorífico zumba al fondo."},
			{"destino": salon.id},
		],
	)
	jugador = Jugador(entorno, datos)
	assert "Comienza la visita guiada." in jugador.dicho()
	assert jugador.actividad.estado()["total"] == 2
	# En el orden que el alumno quiera: primero el salón, que no tiene texto propio (se dice su nombre).
	antes = len(jugador.eventos)
	jugador.ir_a_espacio(salon.id)
	assert "Salón." in jugador.dicho(antes)
	antes = len(jugador.eventos)
	jugador.ir_a_espacio(cocina.id)
	assert "Cocina. Aquí se desayuna. El frigorífico zumba al fondo." in jugador.dicho(antes)
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["objetivos_hechos"] == 2
	assert resultado["cociente_camino"] is None


def test_visita_guiada_sin_zonas_recorre_todo_y_lee_las_descripciones():
	entorno = barrio()
	jugador = Jugador(entorno, nueva_actividad("visita_guiada", entorno, catalogo_real()))
	total = jugador.actividad.estado()["total"]
	assert total >= 9
	vestibulo = espacio_en(entorno, 8.0, -9.0)
	narraciones = [paso.narracion for paso in jugador.actividad._pasos if paso.lugar.elemento_id == vestibulo.id]
	assert narraciones == [f"{vestibulo.nombre}. {vestibulo.descripcion}"]


def test_visita_narrada_en_vivo_por_el_profesional():
	entorno = casa_vacia()
	cocina = espacio_en(entorno, 6.0, 2.0)
	datos = nueva_actividad("visita_guiada", entorno, narrada_en_vivo=True, objetivos=[{"destino": cocina.id, "texto": "No se debe leer."}])
	jugador = Jugador(entorno, datos)
	assert "El profesional te irá contando lo que hay." in jugador.dicho()
	eventos = jugador.actividad.orden_profesional(jugador.sesion, "mensaje", {"texto": "A tu derecha queda la cocina."})
	assert eventos[0].canal == "profesional"
	jugador.ir_a_espacio(cocina.id)
	assert "No se debe leer." not in jugador.dicho()
	assert jugador.fin["completada"] is True and jugador.fin["mensajes_del_profesional"] == 1


# ── Rutas ────────────────────────────────────────────────────────────────────


def test_ruta_con_parada_mide_el_camino_frente_al_mas_corto():
	entorno = casa_vacia()
	cocina, salon = espacio_en(entorno, 6.0, 2.0), espacio_en(entorno, 2.0, 2.0)
	datos = nueva_actividad("ruta", entorno, destino=cocina.id, objetivos=[{"destino": salon.id}], baliza="nunca")
	jugador = Jugador(entorno, datos)
	assert "Ve a Salón." in jugador.dicho()
	antes = len(jugador.eventos)
	# No vale saltarse la parada.
	jugador.ir_a_espacio(cocina.id)
	assert registros(jugador.eventos[antes:], "objetivo") == []
	jugador.ir_a_espacio(salon.id)
	jugador.jugar(4.0)
	assert "Has llegado a Salón." in jugador.dicho(antes)
	assert "Ve a Cocina." in jugador.dicho(antes)
	jugador.ir_a_espacio(cocina.id)
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["objetivos_hechos"] == 2
	# Ha dado un rodeo (cocina, salón, cocina): el camino real supera con mucho al más corto.
	assert resultado["camino_optimo_m"] > 5 and resultado["cociente_camino"] > 1.4
	assert "atajo" not in resultado["estrellas_motivos"]
	assert [t["destino"] for t in resultado["tramos"]] == ["Salón", "Cocina"]


def test_ruta_directa_gana_la_estrella_del_atajo():
	entorno = casa_vacia()
	cocina = espacio_en(entorno, 6.0, 2.0)
	jugador = Jugador(entorno, nueva_actividad("ruta", entorno, destino=cocina.id, baliza="nunca"))
	jugador.ir_a_espacio(cocina.id)
	resultado = jugador.fin
	assert resultado["cociente_camino"] <= 1.35
	assert set(resultado["estrellas_motivos"]) == {"completar", "pocas_ayudas", "atajo", "sin_choques"}
	assert any(r["motivo"] == "pleno" for r in resultado["recompensas"])


def test_ruta_inversa_ida_con_baliza_y_vuelta_sin_ella():
	entorno = casa_vacia()
	cocina = espacio_en(entorno, 6.0, 2.0)
	datos = nueva_actividad("ruta_inversa", entorno, destino=cocina.id, ida_guiada=True, baliza="nunca")
	jugador = Jugador(entorno, datos)
	jugador.jugar(3.0)
	assert hay_baliza(jugador.eventos)
	jugador.ir_a_espacio(cocina.id)
	assert jugador.actividad.estado()["hechos"] == 1 and not jugador.sesion.terminado
	jugador.jugar(4.0)
	assert "vuelve por donde has venido" in jugador.dicho()
	antes = len(jugador.eventos)
	jugador.jugar(4.0)
	assert not hay_baliza(jugador.eventos[antes:])
	jugador.ir(("pla-1", -1.0, 4.6), cerca=0.5)
	resultado = jugador.fin
	assert resultado["completada"] is True
	# Solo se mide la vuelta, y la baliza de la ida (que pone la actividad) no cuenta como ayuda pedida.
	assert [t["destino"] for t in resultado["tramos"]] == ["Entrada"]
	assert resultado["ayudas_contadas"] == 0 and "pocas_ayudas" in resultado["estrellas_motivos"]


def test_volver_al_origen_tras_varias_paradas():
	entorno = casa_vacia()
	cocina, bano = espacio_en(entorno, 6.0, 2.0), espacio_en(entorno, 5.5, 7.0)
	datos = nueva_actividad(
		"volver_origen", entorno, objetivos=[{"destino": cocina.id}, {"destino": bano.id}], ida_guiada=False, baliza="nunca"
	)
	jugador = Jugador(entorno, datos)
	jugador.ir_a_espacio(cocina.id)
	jugador.ir_a_espacio(bano.id)
	jugador.jugar(4.0)
	assert "Ahora vuelve al punto de partida." in jugador.dicho()
	jugador.ir(("pla-1", -1.0, 4.6), cerca=0.5)
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["objetivos_hechos"] == 3
	assert len(resultado["tramos"]) == 1 and resultado["cociente_camino"] <= 1.35


def casa_con_dos_caminos():
	"""La vivienda con un hueco añadido entre el salón y la cocina: así hay dos caminos del salón a la cocina."""
	entorno = ejemplo("vivienda-de-ejemplo", False)
	import copy

	entorno = copy.deepcopy(entorno)
	planta = entorno.plantas[0]
	salon, cocina = espacio_en(entorno, 2.0, 2.0), espacio_en(entorno, 6.0, 2.0)
	ed.anadir_puerta_entre(entorno, planta, salon, cocina, ancho=1.0, tipo="hueco")
	return entorno


def test_ruta_alternativa_con_una_puerta_cortada():
	entorno = casa_con_dos_caminos()
	planta = entorno.plantas[0]
	salon, cocina = espacio_en(entorno, 2.0, 2.0), espacio_en(entorno, 6.0, 2.0)
	puerta_cocina = next(a for a in planta.aberturas if a.tipo == "puerta" and abs(a.centro()[1] - 4.0) < 0.01 and a.centro()[0] > 4.5)
	datos = nueva_actividad("ruta_alternativa", entorno, destino=cocina.id, corte=puerta_cocina.id, baliza="nunca")
	assert datos["cortes"] == [puerta_cocina.id]
	jugador = Jugador(entorno, datos)
	assert "Hoy no se puede pasar por" in jugador.dicho()
	# La puerta queda con llave en la partida; el entorno no se toca.
	assert jugador.sesion.mundo.estado_abertura(puerta_cocina.id) == "con_llave"
	assert puerta_cocina.estado == "abierta"
	# El camino más corto ya no pasa por ella: hay que dar la vuelta por el salón.
	directa = jugador.sesion.nav.ruta(jugador.sesion.inicio, ("pla-1", 6.0, 2.0))
	puntos_salon = [p for p in directa.puntos if salon.contiene(p[1], p[2])]
	assert puntos_salon
	jugador.ir_a_espacio(cocina.id)
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["cortes"] == [puerta_cocina.id]
	assert salon.id in resultado["espacios_visitados"]
	assert resultado["cociente_camino"] <= 1.35 and resultado["paso_cortado_usado"] is False


def test_ruta_alternativa_propuesta_en_el_centro_corta_un_conector():
	"""En el centro la ruta propuesta sube de planta: se corta el ascensor o la escalera y queda el otro."""
	entorno = centro()
	datos = nueva_actividad("ruta_alternativa", entorno, catalogo_real())
	corte = entorno.elemento(datos["corte"])
	assert corte is not None and corte.tipo in ("escalera", "ascensor")
	jugador = Jugador(entorno, datos)
	paso = jugador.actividad._pasos[0]
	# Cortado un conector, el camino usa el otro.
	ruta = jugador.sesion.nav.ruta(jugador.sesion.inicio, paso.lugar.terna, paso.evitar)
	otro = "escalera" if corte.tipo == "ascensor" else "ascensor"
	assert ruta is not None and [entorno.elemento(c).tipo for c in ruta.conectores] == [otro]
	assert corte.nombre in jugador.dicho()


def test_localizar_con_confirmacion():
	entorno = casa_vacia()
	bano, cocina = espacio_en(entorno, 5.5, 7.0), espacio_en(entorno, 6.0, 2.0)
	datos = nueva_actividad("localizar", entorno, destino=bano.id, confirmar=True)
	assert datos["baliza"] == "nunca"
	jugador = Jugador(entorno, datos)
	assert "Localiza Baño. Cuando creas que has llegado, confírmalo con la orden de usar." in jugador.dicho()
	# Confirmar en el sitio equivocado: se dice (es una práctica, no un examen) y cuenta como tropiezo.
	jugador.ir_a_espacio(cocina.id)
	jugador.ir(("pla-1", 6.0, 1.0), cerca=0.3)
	antes = len(jugador.eventos)
	jugador.pulsar("interactuar")
	assert "Todavía no has llegado." in jugador.dicho(antes)
	assert "No hay nada que usar aquí" not in jugador.dicho(antes)
	# Entrar en el baño no basta: hay que confirmarlo.
	jugador.ir_a_espacio(bano.id)
	assert not jugador.sesion.terminado
	jugador.pulsar("interactuar")
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["confirmaciones_fallidas"] == 1 and resultado["fallos"] == 1


# ── Recadero ─────────────────────────────────────────────────────────────────


def test_recadero_encadenado_en_la_vivienda():
	entorno = casa_vacia()
	cocina, dormitorio, bano = espacio_en(entorno, 6.0, 2.0), espacio_en(entorno, 2.0, 7.0), espacio_en(entorno, 5.5, 7.0)
	datos = nueva_actividad(
		"recadero",
		entorno,
		objetivos=[
			{"id": "vaso", "nombre": "el vaso de agua", "recoger": cocina.id, "entregar": dormitorio.id},
			{"id": "toalla", "nombre": "la toalla", "recoger": bano.id, "entregar": cocina.id},
		],
		baliza="nunca",
	)
	jugador = Jugador(entorno, datos, estilo="infantil")
	assert "¡Hoy eres el recadero!" in jugador.dicho()
	assert "Ve a Cocina y coge el vaso de agua." in jugador.dicho()
	assert jugador.actividad.estado()["total"] == 4
	for espacio in (cocina, dormitorio, bano, cocina):
		jugador.ir_a_espacio(espacio.id)
		jugador.jugar(4.0)
	dicho = jugador.dicho()
	for frase in (
		"¡Ya tienes el vaso de agua!",
		"Lleva el vaso de agua a Dormitorio.",
		"¡Entregado! Muy bien.",
		"Lleva la toalla a Cocina.",
	):
		assert frase in dicho
	resultado = jugador.fin
	assert resultado["completada"] is True and resultado["objetivos_hechos"] == 4
	assert [o["id"] for o in jugador.registrados("objetivo")] == ["vaso-recoger", "vaso-entregar", "toalla-recoger", "toalla-entregar"]
	assert len(resultado["tramos"]) == 4


def test_recadero_hasta_la_parada_en_el_barrio():
	"""La plantilla del barrio: de la carta junto al buzón a la parada de autobús, cruzando las dos calles."""
	entorno = barrio()
	datos = next(d for d in plantillas_de("barrio-de-ejemplo", entorno, catalogo_real()) if d["tipo"] == "recadero")
	jugador = Jugador(entorno, datos)
	assert "Hay encargos que hacer." in jugador.dicho()
	pasos = jugador.actividad._pasos
	assert [p.tipo for p in pasos] == ["recoger", "entregar"]
	assert "Buzón" in pasos[0].lugar.nombre and "Parada" in pasos[1].lugar.nombre
	for paso in pasos:
		for _intento in range(4):
			if paso.hecho:
				break
			jugador.ir(paso.lugar.terna, cerca=0.8, intentos=3)
		assert paso.hecho, f"no ha llegado a {paso.lugar.nombre}: está en {jugador.pos}"
	resultado = jugador.fin
	assert resultado["completada"] is True
	# Para llevarla ha tenido que cruzar calzadas: el motor lo ha registrado.
	assert len(jugador.registrados("cruce")) >= 2
	assert resultado["camino_optimo_m"] > 40


# ── Familiarización de sala y línea guía ─────────────────────────────────────


def test_perimetro_primero_las_paredes_y_luego_el_interior():
	entorno = casa_vacia()
	datos = next(d for d in plantillas_de("vivienda-de-ejemplo", entorno) if d["tipo"] == "perimetro")
	jugador = Jugador(entorno, datos)
	actividad = jugador.actividad
	assert jugador.espacio == "Salón"
	assert "Recorre el perímetro de Salón siguiendo la pared." in jugador.dicho()
	assert actividad.estado()["fase"] == "perimetro" and actividad.estado()["total"] == 2
	# Cruzar por el centro no cuenta como perímetro.
	jugador.ir(("pla-1", 2.25, 2.0), cerca=0.2)
	en_el_centro = actividad.perimetro_recorrido()
	assert en_el_centro < 0.3
	# Una pared entera pegado a ella: se avisa del avance, pero aún no se pasa al interior.
	for x, y in ((0.5, 3.5), (0.5, 0.5)):
		jugador.ir(("pla-1", x, y), cerca=0.2)
	jugador.jugar(6.0)
	assert 0.3 < actividad.perimetro_recorrido() < 0.8
	assert "por ciento del perímetro" in jugador.dicho()
	assert actividad.estado()["fase"] == "perimetro"
	for x, y in ((4.0, 0.5), (4.0, 3.5), (0.5, 3.5)):
		jugador.ir(("pla-1", x, y), cerca=0.2)
	jugador.jugar(4.0)
	assert actividad.estado()["fase"] == "interior" and actividad.perimetro_recorrido() >= 0.8
	assert "Perímetro completado. Ahora recorre el interior." in jugador.dicho()
	assert [o["id"] for o in jugador.registrados("objetivo")] == ["perimetro"]
	for x, y in ((1.5, 1.5), (3.0, 1.5), (3.0, 2.5), (1.5, 2.5)):
		if jugador.sesion.terminado:
			break
		jugador.ir(("pla-1", x, y), cerca=0.2)
	resultado = jugador.fin
	assert resultado is not None and resultado["completada"] is True
	assert resultado["perimetro_recorrido"] >= 0.8 and resultado["interior_recorrido"] >= 0.5
	assert resultado["perimetro_m"] == 17.0 and resultado["sala"] == datos["espacio"]


def test_linea_guia_siguiendo_una_pared():
	entorno = casa_vacia()
	pasillo = espacio_en(entorno, 4.0, 4.6)
	datos = nueva_actividad(
		"linea_guia",
		entorno,
		espacio=pasillo.id,
		lado="norte",
		inicio={"planta": "pla-1", "x": 0.5, "y": 4.8, "rumbo": 90.0},
		baliza="nunca",
	)
	jugador = Jugador(entorno, datos)
	actividad = jugador.actividad
	assert "Sigue la pared norte de Pasillo hasta el final." in jugador.dicho()
	jugador.ir(("pla-1", 4.0, 4.8), cerca=0.2)
	jugador.jugar(6.0)
	assert 0.4 <= actividad.linea_recorrida() < 0.9
	assert "Vas por la mitad." in jugador.dicho()
	# Se separa de la pared (se mete en el salón) más de dos segundos: se le avisa y cuenta como tropiezo.
	jugador.ir(("pla-1", 2.0, 2.0), cerca=0.3)
	jugador.jugar(3.0)
	assert "Te has separado de la línea guía." in jugador.dicho()
	jugador.ir(("pla-1", 4.0, 4.8), cerca=0.2)
	jugador.ir(("pla-1", 7.6, 4.8), cerca=0.2)
	resultado = jugador.fin
	assert resultado is not None and resultado["completada"] is True
	assert resultado["separaciones"] == 1 and resultado["linea_recorrida"] >= 0.9
	assert resultado["linea_m"] == 8.0 and resultado["lado"] == "norte"


def test_linea_guia_propuesta_elige_el_lado_mas_largo():
	"""Sin decirle nada, propone la pared más larga a la que se llega (la del pasillo) y empieza junto a uno de sus extremos."""
	entorno = casa_vacia()
	datos = nueva_actividad("linea_guia", entorno)
	pasillo = espacio_en(entorno, 4.0, 4.6)
	assert datos["espacio"] == pasillo.id and datos["inicio"] is not None
	jugador = Jugador(entorno, datos)
	assert jugador.espacio == "Pasillo"
	largo = max(geo.distancia(a, b) for a, b in pasillo.lados())
	assert jugador.actividad._detalle(jugador.sesion)["linea_m"] == round(largo, 1) == 8.0
	assert jugador.actividad.linea_recorrida() < 0.5 and not jugador.sesion.terminado


def test_en_una_sala_pequena_no_basta_con_quedarse_en_el_centro():
	"""En la entrada (2 por 2,2 metros) todo queda «cerca de la pared»: el alcance se reduce para que haya que recorrerla."""
	entorno = casa_vacia()
	entrada = espacio_en(entorno, -1.0, 4.6)
	for tipo in ("perimetro", "linea_guia"):
		jugador = Jugador(entorno, nueva_actividad(tipo, entorno, espacio=entrada.id, inicio=None))
		jugador.tic(10)
		assert not jugador.sesion.terminado, tipo
		assert jugador.actividad.estado()["hechos"] == 0, tipo
