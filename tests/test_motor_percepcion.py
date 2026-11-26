"""Pruebas de las ayudas de percepción, sus límites, el descubrimiento y los avisos automáticos."""

from __future__ import annotations

import pytest

from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio.modelo import Posicion
from app.motor import eventos as ev
from app.motor import lenguaje
from app.motor.percepcion import AYUDAS
from tests.test_motor_comun import Robot, registros, sala_de_pruebas, sonidos, texto, vibraciones, voces

# ── Lenguaje ─────────────────────────────────────────────────────────────────


def test_formatos_de_direccion_y_unidades():
	reloj = lenguaje.Lenguaje("reloj", "metros", 0.7)
	assert reloj.direccion(90.0, 90.0) == "a las 3"
	assert reloj.direccion(0.0, 0.0) == "a las 12"
	assert reloj.direccion(30.0, 30.0) == "a la 1"
	assert reloj.direccion(-90.0, 270.0) == "a las 9"
	lados = lenguaje.Lenguaje("lados", "metros", 0.7)
	assert lados.direccion(-90.0, 0.0) == "a tu izquierda"
	assert lados.direccion(140.0, 0.0) == "detrás a la derecha"
	assert lenguaje.Lenguaje("cardinal").direccion(-90.0, 225.0) == "al suroeste"
	assert lenguaje.Lenguaje("grados").direccion(-40.0, 0.0) == "40 grados a la izquierda"
	assert lenguaje.Lenguaje("grados").direccion(2.0, 0.0) == "de frente"
	assert reloj.distancia(3.2) == "3 metros"
	assert reloj.distancia(1.0) == "1 metro"
	assert reloj.distancia(0.4) == "medio metro"
	pasos = lenguaje.Lenguaje("reloj", "pasos", 0.5)
	assert pasos.distancia(3.2) == "6 pasos"
	assert pasos.distancia(0.4) == "1 paso"
	assert reloj.giro(90.0) == "gira a la derecha"
	assert reloj.giro(-30.0) == "gira ligeramente a la izquierda"
	assert reloj.giro(180.0) == "da media vuelta"
	assert reloj.rumbo(45.0) == "Miras al noreste."
	assert reloj.a_distancia("Mesa", 3.0, "a las 2") == "Mesa, a 3 metros, a las 2"
	assert lenguaje.lista(["a", "b", "c"]) == "a, b y c"
	# Un formato desconocido no rompe: se usa el reloj.
	assert lenguaje.Lenguaje("al revés").formato == "reloj"


def test_los_estilos_solo_cambian_el_tono():
	infantil = lenguaje.Lenguaje(estilo="infantil")
	adulto = lenguaje.Lenguaje(estilo="adulto")
	assert infantil.con_tono("choque", "Pared.") == "¡Pum! Pared."
	assert adulto.con_tono("choque", "Pared.") == "Pared."
	assert adulto.tono("trafico") == "Has cruzado con coches pasando."
	assert infantil.tono("trafico").startswith("¡Cuidado!")
	# Los datos de orientación son idénticos en los tres estilos.
	assert infantil.direccion(90.0, 0.0) == adulto.direccion(90.0, 0.0)


# ── Dónde estoy, mirar, delante, alrededor ───────────────────────────────────


def test_donde_estoy_dice_espacio_planta_y_rumbo_pero_nunca_la_ruta():
	robot = Robot(ejemplos.centro_dos_plantas())
	nuevos = robot.pulsar("donde_estoy")
	assert voces(nuevos) == ["Estás en Vestíbulo, Planta baja, mirando al norte."]
	assert registros(nuevos, "ayuda")[0]["ayuda"] == "donde_estoy"
	# En un entorno de una sola planta no hace falta decirla.
	robot = Robot(ejemplos.vivienda_ejemplo())
	assert voces(robot.pulsar("donde_estoy")) == ["Estás en Entrada, mirando al este."]


def test_donde_estoy_dos_veces_seguidas_anade_la_descripcion(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	robot.pulsar("donde_estoy")
	dicho = texto(robot.pulsar("donde_estoy"))
	assert "Estás en Sala, mirando al este." in dicho
	assert "Una sala amplia con una mesa en el centro." in dicho
	assert "Tiene 1 puerta o paso." in dicho


def test_la_descripcion_se_da_una_sola_vez_al_entrar(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	assert "Sala. Una sala amplia con una mesa en el centro." in voces(robot.eventos)
	# Sale a la antesala y vuelve: la segunda vez solo el nombre.
	robot.girar_a(270.0)
	robot.pulsar("interactuar")
	robot.pulsar("avanzar")
	robot.pulsar("avanzar")
	assert robot.espacio == "Antesala"
	robot.pulsar("media_vuelta")
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar") + robot.tic(60)
	assert robot.espacio == "Sala"
	assert "Sala." in voces(nuevos)
	assert "sala amplia" not in texto(nuevos)


def test_mirar_en_las_cuatro_direcciones(tmp_path):
	entorno, _planta, catalogo, objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	# En (1, 3) mirando al este: la mesa empieza en x = 3,4.
	nuevos = robot.pulsar("mirar_delante")
	assert voces(nuevos)[0].startswith("Delante: Mesa a 2 metros.")
	sonido = next(e for e in nuevos if isinstance(e, ev.EvSonido))
	assert sonido.nombre == "sonda/objeto" and sonido.bus == "ayudas"
	assert sonido.pos[:2] == pytest.approx((3.4, 3.0))
	assert objetos["mesa"].id in robot.sesion.percepcion.objetos
	# Al norte, antes que la pared, está la pizarra (2,4 m de ancha, de x = 0,8 a 3,2).
	assert voces(robot.pulsar("mirar_izquierda")) == ["A tu izquierda: Pizarra a 2 metros."]
	assert voces(robot.pulsar("mirar_derecha")) == ["A tu derecha: Pared a 3 metros."]
	assert voces(robot.pulsar("mirar_detras")) == ["Detrás: Puerta entre Antesala y Sala, cerrada a 1 metro."]
	usos = robot.sesion.percepcion.usos
	assert usos["delante"] == 1 and usos["mirar"] == 3


def test_mirar_cuenta_la_puerta_abierta_y_el_cambio_de_suelo():
	entorno = ejemplos.vivienda_ejemplo()
	# En el pasillo, frente a la puerta abierta del salón, mirando al sur.
	robot = Robot(entorno, inicio=Posicion("pla-1", 1.95, 4.6, 180.0))
	dicho = voces(robot.pulsar("mirar_delante"))[0]
	assert "puerta abierta hacia Salón a medio metro" in dicho
	assert "Alfombra del salón a 2 metros" in dicho
	assert "Ventana a 4 metros" in dicho or "Ventana del salón a 4 metros" in dicho


def test_mirar_en_pasos_y_con_cardinales(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo, unidad="pasos", formato_direccion="cardinal", paso_m=0.7)
	assert voces(robot.pulsar("mirar_izquierda")) == ["Al norte: Pizarra a 2 pasos."]
	assert voces(robot.pulsar("mirar_derecha")) == ["Al sur: Pared a 4 pasos."]


def test_palanca_de_mirar(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	robot.sesion.analogico(0.0, 0.0, 0.0, (1.0, 0.0))
	nuevos = robot.tic(3)
	assert voces(nuevos) == ["A tu derecha: Pared a 3 metros."]
	# Mientras se mantiene en la misma dirección no se repite.
	assert voces(robot.tic(5)) == []
	robot.sesion.analogico(0.0, 0.0, 0.0, (0.0, 0.0))
	robot.tic(1)
	robot.sesion.analogico(0.0, 0.0, 0.0, (1.0, 0.0))
	assert len(voces(robot.tic(2))) == 1


def test_alrededor_por_cuadrantes(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	dicho = voces(robot.pulsar("alrededor"))[0]
	# Delante, además de la mesa contra la que daría, se percibe la alfombra de detrás (no corta la vista).
	assert dicho.startswith("Delante: Mesa a 2 metros; Alfombra a 5 metros.")
	assert "A tu derecha: Pared a 3 metros; Lámpara colgante a 2 metros." in dicho
	assert "Detrás: Puerta entre Antesala y Sala, cerrada a 1 metro." in dicho
	assert "A tu izquierda: Pizarra a 2 metros." in dicho
	assert dicho.index("Delante") < dicho.index("A tu derecha") < dicho.index("Detrás") < dicho.index("A tu izquierda")


# ── Sonda, brújula, eco ──────────────────────────────────────────────────────


def test_la_sonda_avanza_a_ritmo_constante_y_cuenta_los_pasos(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo, unidad="pasos")
	nuevos = robot.pulsar("sonda", 1)
	# El primer pulso sale al momento; los demás, uno cada 0,11 s.
	assert sonidos(nuevos) == ["sonda/libre"]
	nuevos += robot.esperar(1.5)
	pulsos = [e for e in nuevos if isinstance(e, ev.EvSonido) and e.nombre.startswith("sonda/")]
	# La mesa está a 2,4 m y el paso es de 0,7: tres pulsos libres y el choque con el objeto.
	assert [e.nombre for e in pulsos] == ["sonda/libre", "sonda/libre", "sonda/libre", "sonda/objeto"]
	assert [round(e.pos[0], 1) for e in pulsos] == [1.7, 2.4, 3.1, 3.4]
	assert pulsos[0].volumen > pulsos[1].volumen > pulsos[2].volumen
	assert all(e.bus == "ayudas" for e in pulsos)
	assert "Mesa a 3 pasos." in voces(nuevos)
	assert "peldano" in vibraciones(nuevos)


def test_la_sonda_no_encuentra_lo_que_esta_en_voladizo_pero_mirar_si(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", 2.0, 3.6, 0.0))
	robot.pulsar("sonda", 1)
	nuevos = robot.esperar(1.5)
	# La pizarra está a 1,36 m, con la base a 90 cm: el bastón pasa por debajo y da en la pared, a 2,4 m.
	assert "sonda/objeto" not in sonidos(nuevos)
	assert "sonda/pared" in sonidos(nuevos)
	assert "Pared a 2 metros." in voces(nuevos)
	assert voces(robot.pulsar("mirar_delante"))[0].startswith("Delante: Pizarra a 1 metro")


def test_la_sonda_distingue_la_puerta_abierta_y_el_vacio():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno, inicio=Posicion("pla-1", 1.95, 4.6, 180.0), detalle=1)
	robot.pulsar("sonda", 1)
	nuevos = robot.eventos[-1:] + robot.esperar(1.5)
	nombres = [n for n in sonidos(robot.eventos) if n.startswith("sonda/")]
	assert nombres[0] == "sonda/puerta"
	assert nombres[-1] == "sonda/pared"
	# Con detalle 1 la sonda solo suena: no dice nada.
	assert voces(nuevos) == []
	# Pasillo adelante, 8 metros de alcance y la pared a 6: llega; con 3 de alcance, «lejos».
	robot = Robot(entorno, inicio=Posicion("pla-1", 1.95, 4.6, 90.0), alcance_sonda=3.0)
	robot.pulsar("sonda", 1)
	robot.esperar(1.0)
	assert [n for n in sonidos(robot.eventos) if n.startswith("sonda/")][-1] == "sonda/lejos"


def test_la_sonda_mantenida_se_repite_sin_gastar_mas_usos(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	robot.sesion.orden("sonda")
	nuevos = robot.esperar(3.0)
	robot.sesion.orden("sonda", 0)
	assert sonidos(nuevos).count("sonda/objeto") >= 2
	assert robot.sesion.percepcion.usos["sonda"] == 1
	assert "sonda/objeto" not in sonidos(robot.esperar(2.0)[10:])


def test_brujula_dice_el_rumbo_y_suena_el_norte(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	nuevos = robot.pulsar("brujula")
	assert voces(nuevos) == ["Miras al este."]
	norte = next(e for e in nuevos if isinstance(e, ev.EvSonido))
	# Mirando al este, el norte queda a la izquierda.
	assert norte.nombre == "brujula/norte" and norte.relativo == (-90.0, 3.0)
	robot.sesion.ajustes.detalle = 3
	assert voces(robot.pulsar("brujula")) == ["Miras al este, 90 grados."]


def test_el_eco_depende_del_tamano_y_de_la_distancia_a_las_paredes(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo, inicio=Posicion("pla-1", 1.0, 5.0, 0.0))
	nuevos = robot.pulsar("eco", 1) + robot.esperar(1.5)
	ecos = [e for e in nuevos if isinstance(e, ev.EvSonido) and e.nombre == "eco/chasquido"]
	assert ecos[0].pos is None
	rebotes = sorted(ecos[1:], key=lambda e: -e.volumen)
	assert len(rebotes) == 4
	# La pared norte (a 1 m) y la oeste (a 1 m) responden más fuerte que la este (a 7 m).
	assert rebotes[0].volumen > rebotes[-1].volumen * 2
	assert rebotes[-1].pos[0] == pytest.approx(8.0)
	assert "Lugar grande." in texto(nuevos)
	assert "Lo más cercano" in texto(nuevos)
	# Los ecos lejanos llegan más tarde: el último en salir es el de la pared más lejana.
	assert ecos[-1].pos[0] == pytest.approx(8.0)


# ── Cercanos y descubiertos ──────────────────────────────────────────────────


def test_lista_de_cercanos_ordenada_por_distancia_de_camino(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	lista = robot.sesion.percepcion.lista_cercanos()
	nombres = [cosa.nombre for cosa in lista]
	assert nombres[0] == "Puerta entre Antesala y Sala, cerrada"
	assert set(nombres[1:4]) == {"Pizarra", "Lámpara colgante", "Mesa"}
	assert nombres.index("Mesa") < nombres.index("Frigorífico")
	assert set(nombres) >= {"Mesa", "Pizarra", "Frigorífico", "Armario", "Alfombra", "Lámpara colgante"}
	caminos = [cosa.camino for cosa in lista]
	assert caminos == sorted(caminos)
	# Al frigorífico (esquina noreste) hay que rodear la mesa: el camino es más largo que la recta.
	frigorifico = next(cosa for cosa in lista if cosa.nombre == "Frigorífico")
	assert frigorifico.camino >= frigorifico.distancia
	nuevos = robot.pulsar("cercano_siguiente")
	assert voces(nuevos) == [f"Puerta entre Antesala y Sala, cerrada, a 1 metro, a las 6. 1 de {len(lista)}."]
	sonido = next(e for e in nuevos if isinstance(e, ev.EvSonido))
	assert sonido.nombre == "sonda/puerta" and sonido.pos[:2] == pytest.approx((0.0, 3.0))
	nuevos = robot.pulsar("cercano_siguiente")
	assert voces(nuevos)[0].startswith(f"{nombres[1]}, a 2 metros, ")
	assert next(e for e in nuevos if isinstance(e, ev.EvSonido)).nombre == "sonda/objeto"
	assert voces(robot.pulsar("cercano_anterior"))[0].startswith("Puerta entre Antesala y Sala")
	assert "interfaz/borde" in sonidos(robot.pulsar("cercano_anterior"))


def test_los_cercanos_no_revelan_lo_que_hay_tras_una_puerta_cerrada():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno, inicio=Posicion("pla-1", 3.0, 4.6, 0.0))
	nombres = [cosa.nombre for cosa in robot.sesion.percepcion.lista_cercanos()]
	assert "Puerta entre Dormitorio y Pasillo, cerrada" in nombres
	assert "Ventana del dormitorio" not in nombres
	# La ventana del salón sí: se ve por la puerta abierta del salón desde aquí cerca.
	robot = Robot(entorno, inicio=Posicion("pla-1", 1.95, 4.6, 180.0))
	assert "Ventana del salón" in [cosa.nombre for cosa in robot.sesion.percepcion.lista_cercanos()]


def test_descubrimiento_progresivo_y_lugares_conocidos():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno)
	# Desde la entrada ya se percibe, por el hueco, que al lado hay un pasillo.
	assert voces(robot.pulsar("descubiertos")) == ["Conoces 2 lugares: Entrada; Pasillo, sin visitar."]
	robot.ir_a(1.95, 4.6)
	dicho = voces(robot.pulsar("descubiertos"))[0]
	# El pasillo solo lo ha pisado por un extremo; el salón lo percibe por la puerta abierta, sin haber entrado.
	assert dicho == "Conoces 3 lugares: Entrada; Pasillo, no explorada del todo; Salón, sin visitar."
	lugares = {dato["nombre"]: dato for dato in robot.sesion.percepcion.lugares_conocidos()}
	assert lugares["Entrada"]["completo"] and lugares["Entrada"]["visitado"]
	assert not lugares["Pasillo"]["completo"] and 0.0 < lugares["Pasillo"]["explorado"] < 0.85
	assert not lugares["Salón"]["visitado"]
	# Recorre el pasillo hasta el fondo: ya está explorado del todo y queda registrado.
	robot.ir_a(7.5, 4.6)
	assert registros(robot.eventos, "espacio_explorado")[-1]["nombre"] == "Pasillo"
	assert {dato["nombre"]: dato for dato in robot.sesion.percepcion.lugares_conocidos()}["Pasillo"]["completo"]
	# El radiador del fondo del pasillo ya es una referencia conocida.
	referencia = next(r for r in entorno.plantas[0].referencias if "Radiador" in r.nombre)
	assert referencia.id in robot.sesion.percepcion.referencias


# ── Permisos y límites ───────────────────────────────────────────────────────


def test_todas_las_ayudas_tienen_nombre():
	assert set(AYUDAS) >= {
		"donde_estoy",
		"mirar",
		"delante",
		"alrededor",
		"sonda",
		"cercanos",
		"descubiertos",
		"brujula",
		"eco",
		"objetivo",
		"pista",
		"baliza",
		"avisos",
		"descripcion",
	}


def test_ayuda_prohibida_y_ayuda_limitada(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	ayudas = {"eco": {"permitida": False, "limite": None}, "brujula": {"permitida": True, "limite": 2}}
	robot = Robot(entorno, catalogo, ayudas=ayudas)
	nuevos = robot.pulsar("eco")
	assert voces(nuevos) == ["Esa ayuda no está disponible en esta actividad."]
	assert "eco/chasquido" not in sonidos(nuevos)
	assert registros(nuevos, "ayuda_denegada")[0] | {} == registros(nuevos, "ayuda_denegada")[0]
	assert registros(nuevos, "ayuda_denegada")[0]["motivo"] == "prohibida"
	assert not registros(nuevos, "ayuda")
	primera = registros(robot.pulsar("brujula"), "ayuda")[0]
	assert (primera["uso"], primera["restantes"]) == (1, 1)
	assert registros(robot.pulsar("brujula"), "ayuda")[0]["restantes"] == 0
	nuevos = robot.pulsar("brujula")
	assert voces(nuevos) == ["Ya no quedan usos de esa ayuda."]
	assert registros(nuevos, "ayuda_denegada")[0]["motivo"] == "agotada"
	assert robot.sesion.percepcion.usos == {"brujula": 2}
	# El profesional puede devolverla en marcha.
	robot.sesion.permitir_ayuda("brujula", True, None)
	assert voces(robot.pulsar("brujula")) == ["Miras al este."]
	# Las demás ayudas, sin regla, están permitidas y sin límite.
	assert robot.sesion.percepcion.permitida("sonda") and robot.sesion.percepcion.restantes("sonda") is None


def test_objetivo_y_pista_sin_actividad(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo, ayudas={"pista": False})
	assert voces(robot.pulsar("objetivo")) == ["No hay ningún objetivo: explora con libertad."]
	assert voces(robot.pulsar("pista")) == ["Esa ayuda no está disponible en esta actividad."]


# ── Avisos automáticos ───────────────────────────────────────────────────────


def test_avisos_de_proximidad_con_antirrepeticion():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno)
	robot.esperar(4.0)
	avisos = [d["texto"] for d in registros(robot.eventos, "aviso")]
	assert "Felpudo, a las 6." in avisos and "Perchero, a las 9." in avisos
	# Un paso adelante y otro atrás: sigue junto al felpudo y no se le repite.
	robot.pulsar("avanzar")
	robot.pulsar("retroceder")
	robot.esperar(3.0)
	assert [d["texto"] for d in registros(robot.eventos, "aviso")].count("Felpudo, a las 6.") == 1
	# Pasado el tiempo de espera (dos minutos), al volver a moverse por allí se le recuerda.
	robot.esperar(125.0)
	robot.pulsar("avanzar")
	robot.pulsar("retroceder")
	felpudo = registros(robot.eventos, "aviso")[0]["elemento"]
	assert len([d for d in registros(robot.eventos, "aviso") if d["elemento"] == felpudo]) == 2


def test_niveles_de_detalle_de_los_avisos():
	entorno = ejemplos.vivienda_ejemplo()
	mudo = Robot(entorno, detalle=0)
	mudo.ir_a(3.0, 4.6)
	assert not registros(mudo.eventos, "aviso") and voces(mudo.eventos) == []
	uno = Robot(entorno, detalle=1)
	uno.ir_a(3.0, 4.6)
	clases = {d["clase"] for d in registros(uno.eventos, "aviso")}
	assert "referencia" in clases and "abertura" not in clases
	dos = Robot(entorno, detalle=2)
	dos.ir_a(3.0, 4.6)
	assert "Puerta cerrada, delante a la izquierda." in [d["texto"] for d in registros(dos.eventos, "aviso")]
	tres = Robot(entorno, detalle=3)
	tres.ir_a(3.0, 4.6)
	assert any("Puerta entre Dormitorio y Pasillo, cerrada" in d["texto"] for d in registros(tres.eventos, "aviso"))


def test_prohibir_los_avisos_los_calla():
	robot = Robot(ejemplos.vivienda_ejemplo(), ayudas={"avisos": False})
	robot.ir_a(3.0, 4.6)
	assert not registros(robot.eventos, "aviso")
	# Entrar en un espacio se sigue diciendo: no es una ayuda, es saber dónde se está.
	assert "Pasillo." in voces(robot.eventos + robot.esperar(3.0))


def test_aviso_de_boca_de_escalera_y_de_ascensor():
	robot = Robot(ejemplos.centro_dos_plantas(), inicio=Posicion("pla-1", 10.5, 6.8, 0.0))
	robot.esperar(4.0)
	avisos = [d["texto"] for d in registros(robot.eventos, "aviso")]
	assert "Escalera que sube, a 2 metros, a las 11." in avisos
	assert any(aviso.startswith("Ascensor, ") for aviso in avisos)
	boca = next(e for e in robot.eventos if isinstance(e, ev.EvVoz) and "Escalera que sube" in e.texto)
	assert boca.canal == "aviso"


def test_aviso_de_paso_de_peatones_y_de_cruce_con_su_forma():
	robot = Robot(ejemplos.barrio_ejemplo(), inicio=Posicion("pla-1", -11.5, 4.5, 90.0))
	robot.pulsar("avanzar")
	robot.esperar(1.0)
	avisos = [d["texto"] for d in registros(robot.eventos, "aviso")]
	assert "A la 1, paso de peatones con semáforo sonoro. Cruza Calle Mayor, 7 metros. Tiene pulsador." in avisos
	robot = Robot(ejemplos.barrio_ejemplo(), inicio=Posicion("pla-1", -9.5, 4.5, 90.0), semilla=3)
	robot.ir_a(-6.0, 4.5)
	robot.esperar(1.0)
	cruce = next(d["texto"] for d in registros(robot.eventos, "aviso") if d["clase"] == "cruce")
	assert cruce.startswith("Cruce de Calle Mayor con Calle del Río, en cruz.")
	assert "Calle Mayor: delante y detrás." in cruce
	assert "Calle del Río: a tu izquierda y a tu derecha." in cruce
	paso = robot.sesion.mundo.entorno.elemento("esp-15")
	assert robot.sesion.percepcion.texto_paso(paso, False) == "Paso de peatones con semáforo sonoro"
	sin = next(e for e in robot.sesion.mundo.entorno.plantas[0].espacios if e.tipo == "paso_peatones" and not e.datos.get("semaforo"))
	assert robot.sesion.percepcion.texto_paso(sin).startswith("Paso de peatones sin semáforo. Cruza Calle del Río")


def test_cruce_en_te():
	entorno = ed.crear_entorno("Te")
	calle = ed.crear_planta(entorno, "Calle", exterior=True)
	larga = ed.crear_calle(entorno, calle, "Avenida", [(-30.0, 0.0), (30.0, 0.0)], trafico=0)
	corta = ed.crear_calle(entorno, calle, "Travesía", [(0.0, 0.0), (0.0, 30.0)], trafico=0)
	cruce = ed.crear_cruce(entorno, calle, larga, corta)
	ed.fijar_inicio(entorno, calle, -10.0, -4.0, 90.0)
	robot = Robot(entorno)
	numero, ramas = robot.sesion.percepcion.forma_cruce(cruce)
	assert numero == 3
	assert sorted(round(rumbo) for rumbo, _nombre in ramas) == [0, 90, 270]
	assert "en forma de te" in robot.sesion.percepcion.texto_cruce(cruce)


# ── Protección frente a la sobrecarga ────────────────────────────────────────


def test_lo_pedido_interrumpe_y_lo_automatico_espera_y_caduca():
	entorno = ed.crear_entorno("Muchas referencias")
	planta = ed.crear_planta(entorno, "Planta")
	ed.crear_habitacion_rectangular(entorno, planta, "Almacén", 0, 0, 10, 10)
	for numero in range(8):
		ed.anadir_referencia(entorno, planta, f"Caja {numero}", 4.0 + 0.2 * numero, 6.0)
	ed.fijar_inicio(entorno, planta, 5.0, 5.0, 0.0)
	robot = Robot(entorno, detalle=3)
	primeros = robot.tic(1)
	# Ocho referencias a la vez: como mucho dos avisos por comprobación, y de la voz sale uno solo cada vez.
	assert len(registros(robot.eventos, "aviso")) <= 2
	assert len(voces(robot.eventos)) == 1
	del primeros
	automaticas = [e for e in robot.eventos if isinstance(e, ev.EvVoz)]
	assert all(not e.interrumpir for e in automaticas)
	# Lo que pide el alumno sale al momento, interrumpe y vacía lo que esperaba turno.
	nuevos = robot.pulsar("brujula")
	pedida = next(e for e in nuevos if isinstance(e, ev.EvVoz))
	assert pedida.interrumpir and pedida.canal == "ayuda"
	assert voces(robot.esperar(10.0)) == []
	# Una frase automática que deja de ser cierta antes de su turno no se dice.
	sesion = robot.sesion
	sesion.decir("Frase larga que ocupa la voz durante un buen rato para que la siguiente espere.", pedida=True)
	sesion.decir("Esto ya no es verdad.", caduca=30.0, vale=lambda: False)
	sesion.decir("Esto caduca enseguida.", caduca=0.5)
	sesion.decir("Esto sí llega.", caduca=30.0)
	dicho = voces(robot.esperar(8.0))
	assert dicho == ["Frase larga que ocupa la voz durante un buen rato para que la siguiente espere.", "Esto sí llega."]


def test_la_cola_de_voz_no_crece_sin_limite(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	sesion = robot.sesion
	sesion.decir("Ocupada con una frase bastante larga para que las demás tengan que esperar su turno.", pedida=True)
	for numero in range(20):
		sesion.decir(f"Aviso {numero}.", prioridad=1 if numero != 3 else 2, caduca=60.0)
	dicho = voces(robot.esperar(30.0))
	automaticas = [frase for frase in dicho if frase.startswith("Aviso")]
	assert len(automaticas) == 4
	# La más importante no se ha perdido y sale la primera.
	assert automaticas[0] == "Aviso 3."
