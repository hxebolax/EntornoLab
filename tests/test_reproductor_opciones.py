"""Pruebas de las opciones en caliente del reproductor: motor y paquete de sonido, teclas, botones, voz y perfil."""

# ruff: noqa: F811 - los parámetros de las pruebas se llaman como las fixtures importadas
from __future__ import annotations

import json

import pygame
import pytest

from app.audio.base import ErrorMotor
from app.core.configuracion import VALORES_POR_DEFECTO, Configuracion, ErrorValidacion
from app.reproductor import ajustes
from app.reproductor import aplicacion as modulo_aplicacion
from app.reproductor.pantallas.juego import PantallaJuego
from app.reproductor.pantallas import opciones as opciones_reproductor
from app.reproductor.pantallas.opciones import PantallaCaptura

from .test_reproductor_comun import Robot, actividades, app, crear_app, paquete_con_busqueda, robot, sin_navegador  # noqa: F401 - fixtures
from .test_reproductor_menus import MandoFalso


def _ir_a_opciones(robot: Robot, *camino: str) -> None:
	robot.elegir("Opciones")
	for paso in camino:
		robot.elegir(paso)


def _explorar(robot: Robot) -> PantallaJuego:
	robot.elegir("Elegir entorno")
	robot.elegir("Vivienda de ejemplo, de ejemplo")
	robot.elegir("Exploración libre", 3)
	return robot.partida


# ── Claves de configuración añadidas por el reproductor ──────────────────────


def test_claves_de_configuracion_del_reproductor(tmp_path):
	juego = VALORES_POR_DEFECTO["juego"]
	assert juego["ver_plano"] is True and juego["pantalla_negra"] is False and juego["posicion_menu"] is True and juego["alias"] == ""
	assert VALORES_POR_DEFECTO["supervision"]["ultima_sala"] == ""
	config = Configuracion(tmp_path / "config.json")
	config.establecer("juego.alias", "Luna")
	config.establecer("supervision.ultima_sala", "192.168.1.20:47900")
	config.establecer("juego.modo_movimiento", "aceras")
	with pytest.raises(ErrorValidacion):
		config.establecer("juego.alias", "x" * 61)
	with pytest.raises(ErrorValidacion):
		config.establecer("supervision.ultima_sala", "x" * 256)
	with pytest.raises(ErrorValidacion):
		config.establecer("juego.ver_plano", "sí")
	with pytest.raises(ErrorValidacion):
		config.establecer("juego.modo_movimiento", "volando")
	otra = Configuracion(tmp_path / "config.json")
	assert otra.obtener("juego.alias") == "Luna" and otra.obtener("juego.modo_movimiento") == "aceras"


def test_la_configuracion_se_traduce_a_los_diccionarios_de_cada_pieza(tmp_path):
	config = Configuracion(tmp_path / "config.json")
	config.establecer_varias(
		{
			"sonido.motor": "clasico",
			"sonido.modo_salida": "altavoces",
			"sonido.perfil_hrtf": "ku100",
			"sonido.volumen_pasos": 0.4,
			"sonido.refuerzo_detras": False,
			"sonido.proteccion_auditiva": False,
			"voz.salida": "sapi",
			"voz.velocidad": 80,
			"voz.braille": False,
			"voz.interrumpir": False,
			"voz.detalle": 3,
			"juego.unidad": "pasos",
			"juego.giro_grados": 90.0,
			"mando.zona_muerta": 0.4,
			"mando.vibracion": False,
		}
	)
	sonido = ajustes.opciones_sonido(config, memoria=True)
	assert sonido["motor"] == "clasico" and sonido["salida"] == "altavoces" and sonido["cabeza"] == "ku100"
	assert sonido["volumenes"]["pasos"] == 0.4 and sonido["refuerzo_detras"] == 0.0 and sonido["memoria"] is True
	assert sonido["proteccion"]["techo_mezcla"] == 1.0, "sin protección los límites se relajan, no desaparecen"
	assert ajustes.opciones_sonido(Configuracion(tmp_path / "otra.json"))["proteccion"] == {}
	voz = ajustes.opciones_voz(config)
	assert voz["salida"] == "sapi" and voz["sapi_velocidad"] == 6 and voz["braille"] == "nada" and voz["nunca_interrumpir"] is True
	juego = ajustes.ajustes_juego(config)
	assert juego.unidad == "pasos" and juego.giro_grados == 90.0 and juego.detalle == 3
	assert ajustes.opciones_mando(config) == {"zona_muerta": 0.4, "vibracion": False, "fuerza_vibracion": 1.0}
	assert ajustes.opciones_haptica(config) == {"activa": False, "fuerza": 1.0}


# ── Motor de sonido ──────────────────────────────────────────────────────────


def test_cambio_en_caliente_de_motor_de_sonido(robot: Robot):
	app = robot.app
	nulo = app.motor
	assert nulo.nombre == "nulo"
	_ir_a_opciones(robot, "Sonido")
	assert robot.cima.elegir("Motor de sonido")
	assert robot.cima.opciones[robot.cima.i].texto.startswith("Motor de sonido: Binaural")
	robot.accion("menu_derecha", 2)
	assert app.config.obtener("sonido.motor") == "clasico"
	assert app.motor is not nulo and app.motor.nombre == "clasico", "el motor nuevo está en uso sin reiniciar"
	assert app.presentador.motor is app.motor
	assert nulo.de("cerrar"), "el motor anterior se ha cerrado"
	assert "Motor de sonido: Clásico" in robot.ultimo()
	# El motor nuevo suena: los menús siguen pidiendo sus sonidos y no hay fallos.
	robot.accion("menu_abajo")
	robot.esperar(5)
	assert app.fallos == 0


def test_si_el_motor_nuevo_no_arranca_se_vuelve_al_anterior(robot: Robot, monkeypatch, caplog):
	app = robot.app
	app.establecer("sonido.motor", "clasico")
	assert app.motor.nombre == "clasico"
	original = modulo_aplicacion.clase_motor

	def clase_rota(nombre: str):
		clase = original(nombre)
		if nombre != "estereo":
			return clase

		class Rota(clase):  # type: ignore[misc, valid-type]
			def iniciar(self, dispositivo, opciones):
				raise ErrorMotor("no hay tarjeta de sonido")

		return Rota

	monkeypatch.setattr(modulo_aplicacion, "clase_motor", clase_rota)
	_ir_a_opciones(robot, "Sonido")
	assert robot.cima.elegir("Motor de sonido")
	marca = robot.marca()
	robot.accion("menu_derecha", 2)
	assert app.motor.nombre == "clasico", "se sigue con el motor que había"
	assert app.presentador.motor is app.motor
	assert app.config.obtener("sonido.motor") == "clasico", "y la preferencia vuelve a su valor"
	dicho = robot.dicho(marca)
	assert "No se ha podido usar «Estéreo simple" in dicho and "no hay tarjeta de sonido" in dicho and "Se sigue con «Clásico" in dicho
	assert robot.app.voz.registro[-1][1] == "aviso", "el menú no tapa la explicación del fallo"
	assert "no ha arrancado" in caplog.text
	assert robot.cima.opciones[robot.cima.i].texto.startswith("Motor de sonido: Clásico")
	robot.esperar(5)
	assert app.fallos == 0


def test_cambiar_de_motor_a_mitad_de_partida_conserva_la_pausa_y_el_eco(robot: Robot):
	partida = _explorar(robot)
	robot.segundos(0.5)
	robot.tecla(pygame.K_ESCAPE, fotogramas=2)
	robot.app.establecer("sonido.motor", "clasico")
	assert robot.app.motor.nombre == "clasico" and partida.sesion.pausado
	robot.elegir("Continuar", 3)
	robot.andar(2)
	robot.segundos(0.5)
	assert robot.app.fallos == 0 and not partida.sesion.pausado


# ── Paquete de sonidos ───────────────────────────────────────────────────────


def test_cambio_en_caliente_de_paquete_de_sonidos(robot: Robot):
	app = robot.app
	partida = _explorar(robot)
	robot.andar(3)
	robot.segundos(0.5)
	assert app.banco.paquete_actual() == "por_defecto"
	cargados = set(app.motor.sonidos_cargados())
	assert any(nombre.startswith("pasos/") for nombre in cargados)
	cargas = len(app.motor.de("cargar"))
	robot.tecla(pygame.K_ESCAPE, fotogramas=2)
	robot.elegir("Opciones rápidas")
	# El siguiente paquete instalado después del de por defecto (hay varios: natural, grabado...).
	siguiente = app.banco.paquetes_disponibles()[1]
	elegido, nombre = siguiente["id"], siguiente["nombre"]
	texto = robot.ajustar("Paquete de sonidos")
	assert texto == f"Paquete de sonidos: {nombre}"
	assert app.config.obtener("sonido.paquete") == elegido and app.banco.paquete_actual() == elegido
	recargados = [llamada["nombre"] for llamada in app.motor.de("cargar")[cargas:]]
	assert recargados, "lo que estaba cargado se vuelve a cargar con el paquete nuevo, sin esperar"
	assert app.banco.sonido("pasos/madera_izq_1").paquete in (elegido, "por_defecto")
	marca = robot.marca()
	robot.accion("ayuda")
	assert nombre in robot.dicho(marca) and "Aceptar hace sonar una muestra." in robot.dicho(marca)
	robot.accion("menu_aceptar")
	assert app.motor.de("reproducir")[-1]["nombre"] == f"_muestra/{elegido}", "aceptar hace sonar una muestra del paquete"
	robot.atras()
	robot.elegir("Continuar", 3)
	robot.andar(2)
	assert not partida.sesion.pausado and app.fallos == 0
	assert Configuracion().obtener("sonido.paquete") == elegido, "queda guardado en la configuración compartida"


# ── Teclado ──────────────────────────────────────────────────────────────────


def test_reasignar_una_tecla_con_la_pantalla_de_captura(robot: Robot, data_temporal):
	app = robot.app
	_ir_a_opciones(robot, "Teclado", "Cambiar las teclas para jugar")
	assert "Dónde estoy: C" in robot.opciones()
	robot.elegir("Dónde estoy: C")
	assert isinstance(robot.cima, PantallaCaptura)
	assert robot.ultimo() == "Dónde estoy. Pulsa la tecla que quieres usar. Escape cancela."
	robot.tecla(pygame.K_F1)
	assert "no se puede usar: está reservada" in robot.ultimo() and isinstance(robot.cima, PantallaCaptura)
	robot.tecla(pygame.K_h, unicode="h")
	assert not isinstance(robot.cima, PantallaCaptura)
	assert "Dónde estoy" in robot.ultimo() and "H" in robot.ultimo(), robot.ultimo()
	assert "Dónde estoy: H" in robot.opciones(), "la lista refleja la tecla nueva"
	assert app.config.obtener("teclado.mapa")["juego"]["h"] == "donde_estoy"
	# Cancelar no cambia nada.
	robot.elegir("Brújula: K")
	robot.tecla(pygame.K_ESCAPE)
	assert robot.ultimo() == "Cancelado." and "Brújula: K" in robot.opciones()
	# La tecla nueva funciona jugando, y la vieja ya no.
	robot.atras(3)
	_explorar(robot)
	marca = robot.marca()
	robot.tecla(pygame.K_h, unicode="h", fotogramas=2)
	assert "Estás en" in robot.dicho(marca)
	marca = robot.marca()
	robot.tecla(pygame.K_c, unicode="c", fotogramas=2)
	assert "Estás en" not in robot.dicho(marca)
	app.cerrar_todo()
	# Y se conserva para la próxima vez.
	otra = crear_app("--alumno", "Luna")
	try:
		assert otra.entrada.teclado.mapa.accion_de("juego", "h") == "donde_estoy"
		Robot(otra).elegir("Opciones")
		Robot(otra).elegir("Teclado")
		Robot(otra).elegir("Oír las teclas que he cambiado")
		assert "Dónde estoy" in otra.voz.registro[-1][0]
		Robot(otra).elegir("Restablecer las teclas de serie")
		Robot(otra).elegir("Sí")
		assert otra.entrada.teclado.mapa.accion_de("juego", "c") == "donde_estoy"
		assert otra.config.obtener("teclado.mapa") == {}
	finally:
		otra.cerrar_todo()


# ── Mando ────────────────────────────────────────────────────────────────────


def test_reasignar_un_boton_del_mando(robot: Robot):
	app = robot.app
	app.entrada.mandos.conectar(MandoFalso(), 1)
	_ir_a_opciones(robot, "Mando")
	assert robot.opciones()[0] == "Mando conectado: Xbox Wireless Controller"
	robot.elegir("Cambiar los botones para jugar")
	assert "Y: Mirar delante" in robot.opciones() and not any(o.startswith("Menú:") for o in robot.opciones()), (
		"el botón de pausa no se cambia"
	)
	robot.elegir("Y: Mirar delante")
	assert robot.cima.titulo == "Acción para Y"
	robot.elegir("Brújula")
	assert app.entrada.mandos.mapa.accion_de("juego", "y") == "brujula"
	assert app.entrada.mandos.mapa.accion_de("juego", "izquierda") == "mirar_delante", "si otro botón la tenía, se intercambian"
	assert app.config.obtener("mando.mapa")["juego"]["y"] == "brujula"
	assert "Y: Brújula" in robot.opciones()
	robot.atras()
	assert robot.ajustar("Zona muerta de las palancas") == "Zona muerta de las palancas: 25 por ciento"
	assert app.entrada.mandos.opciones["zona_muerta"] == 0.25
	robot.elegir("Probar la vibración")
	robot.esperar(3)
	assert app.entrada.mandos._mandos[1].vibraciones, "la prueba hace vibrar el mando"
	assert robot.ajustar("Vibración:") == "Vibración: no"
	assert app.entrada.mandos.opciones["vibracion"] is False


# ── Voz, movimiento y perfil ─────────────────────────────────────────────────


def test_voz_y_movimiento_en_caliente_a_mitad_de_partida(robot: Robot):
	app = robot.app
	partida = _explorar(robot)
	app.establecer("voz.detalle", 0)
	app.establecer("juego.formato_direccion", "cardinal")
	app.establecer("juego.paso_m", 0.5)
	ajustes_sesion = partida.sesion.ajustes
	assert (ajustes_sesion.detalle, ajustes_sesion.formato_direccion, ajustes_sesion.paso_m) == (0, "cardinal", 0.5)
	antes = (robot.jugador.x, robot.jugador.y)
	robot.andar(1)
	import math

	assert math.hypot(robot.jugador.x - antes[0], robot.jugador.y - antes[1]) == pytest.approx(0.5, abs=0.01)
	app.establecer("voz.braille", False)
	app.establecer("voz.interrumpir", False)
	assert app.voz.braille == "nada" and app.voz.nunca_interrumpir is True
	app.establecer("juego.estilo", "infantil")
	assert app.estilo == "infantil" and partida.sesion.ajustes.estilo == "infantil"


def test_las_preferencias_de_juego_son_del_alumno(robot: Robot, data_temporal, sin_navegador):
	app = robot.app
	_ir_a_opciones(robot, "Movimiento")
	assert robot.ajustar("Las distancias se dicen en") == "Las distancias se dicen en: pasos"
	assert robot.ajustar("Cada giro") == "Cada giro: 90 grados"
	robot.atras()
	robot.elegir("Estilo e idioma")
	assert robot.ajustar("Estilo", -1) == "Estilo: Juvenil"
	perfil = json.loads((data_temporal / "config" / "alumnos" / "luna.json").read_text(encoding="utf-8"))
	assert perfil["preferencias"] == {"juego.unidad": "pasos", "juego.giro_grados": 90.0, "juego.estilo": "juvenil"}
	app.cerrar_todo()
	# Otro alumno juega en el mismo equipo y cambia sus cosas...
	otro = crear_app("--alumno", "Sol")
	try:
		otro.establecer("juego.unidad", "metros")
		otro.establecer("juego.estilo", "adulto")
	finally:
		otro.cerrar_todo()
	# ...y al volver Luna, tiene las suyas.
	de_nuevo = crear_app("--alumno", "Luna")
	try:
		assert de_nuevo.preferencia("juego.unidad") == "pasos" and de_nuevo.estilo == "juvenil"
		assert de_nuevo.ajustes_juego().unidad == "pasos"
		# Las preferencias de cada alumno viven en su perfil: la configuración compartida con el Estudio no se toca.
		assert de_nuevo.config.obtener("juego.unidad") == "metros" and de_nuevo.config.obtener("juego.estilo") == "adulto"
		assert "¿Preparado para otra misión?" in de_nuevo.voz.registro[0][0], "el saludo va en el estilo del alumno"
	finally:
		de_nuevo.cerrar_todo()


def test_lo_que_fija_la_actividad_manda_sobre_las_opciones_del_alumno(robot: Robot, data_temporal, actividades):
	paquete_con_busqueda(data_temporal / "entornos", ayudas={"sonda": {"permitida": False, "limite": None}})
	robot.elegir("Elegir entorno")
	robot.elegir("Vivienda de ejemplo")
	robot.elegir("Busca los premios", 3)
	partida = robot.partida
	assert partida.sesion.ajustes.ayudas["sonda"]["permitida"] is False
	robot.app.establecer("juego.unidad", "pasos")
	assert partida.sesion.ajustes.unidad == "pasos", "el alumno cambia sus opciones..."
	assert partida.sesion.ajustes.ayudas["sonda"]["permitida"] is False, "...pero no lo que fijó el profesional"
	marca = robot.marca()
	robot.tecla(pygame.K_b, unicode="b", fotogramas=3)
	assert not any(nombre.startswith("sonda/") for nombre in robot.sonidos()), robot.dicho(marca)


def test_pantalla_y_tamano_de_texto(robot: Robot):
	_ir_a_opciones(robot, "Pantalla")
	assert robot.ajustar("Alto contraste") == "Alto contraste: sí"
	assert robot.app.paleta[0] == (0, 0, 0)
	assert robot.ajustar("Tamaño del texto") == "Tamaño del texto: 125 por ciento"
	assert robot.ajustar("Ver el plano mientras juego") == "Ver el plano mientras juego: no"
	robot.app.dibujar()
	assert robot.app.fallos == 0


# ── Salida de voz: automática, solo el lector, SAPI o nadie ──────────────────


def test_opcion_habla_recorre_las_cuatro_salidas_y_avisa_una_vez_al_apagar(robot: Robot):
	app = robot.app
	_ir_a_opciones(robot, "Voz y braille")
	assert robot.cima.elegir("Habla")
	assert robot.cima.opciones[robot.cima.i].texto == "Habla: automática: tu lector de pantalla o, si no hay, la voz de Windows"
	ayuda = robot.cima.texto_ayuda()
	for fragmento in ("Automática", "Solo tu lector de pantalla", "Siempre la voz de Windows", "Nadie", "Control+F12"):
		assert fragmento in ayuda
	assert robot.ajustar("Habla") == "Habla: solo tu lector de pantalla"
	assert app.config.obtener("voz.salida") == "lector" and app.voz.salida == "lector"
	assert robot.ajustar("Habla") == "Habla: siempre la voz de Windows"
	assert app.voz.salida == "sapi"
	marca = robot.marca()
	robot.ajustar("Habla")
	assert app.config.obtener("voz.salida") == "ninguna" and app.voz.salida == "ninguna"
	assert "interfaz/cerrar" in robot.sonidos()
	# El aviso se dice con la voz que había, una sola vez, y queda escrito abajo en la pantalla.
	assert robot.canales(marca) == [(opciones_reproductor.aviso_sin_voz(), "aviso")]
	assert app.voz.ultimo == opciones_reproductor.aviso_sin_voz()
	assert "Control+F12" in app.voz.ultimo
	# Ya sin voz: nada se dice, pero todo queda en el historial (y abajo en la pantalla).
	marca = robot.marca()
	robot.accion("menu_abajo")
	assert robot.dicho(marca) == "", "con «nadie» la voz no dice nada"
	assert app.voz.ultimo.startswith("Voz de Windows"), "el historial sigue llenándose"
	robot.accion("menu_arriba")
	assert robot.cima.opciones[robot.cima.i].texto == "Habla: nadie: sin voz"
	# Dando la vuelta se vuelve a la automática, sin aviso.
	robot.ajustar("Habla")
	assert app.config.obtener("voz.salida") == "automatica"
	assert robot.ultimo() == "Habla: automática: tu lector de pantalla o, si no hay, la voz de Windows"


def test_control_f12_devuelve_la_voz_automatica_desde_cualquier_pantalla(robot: Robot):
	app = robot.app
	app.establecer("voz.salida", "ninguna")
	_explorar(robot)
	marca = robot.marca()
	robot.tecla(pygame.K_F12, pygame.KMOD_LCTRL)
	assert app.config.obtener("voz.salida") == "automatica" and app.voz.salida == "automatica"
	assert "interfaz/abrir" in robot.sonidos()
	assert robot.dicho(marca) == "Voz restablecida: habla tu lector de pantalla o, si no hay, la voz de Windows."
	# Ya en automática, lo dice y no cambia nada.
	robot.tecla(pygame.K_F12, pygame.KMOD_LCTRL)
	assert robot.ultimo() == "La voz ya está en automática."
	# F12 sin Control, o con Alt, no hace nada de esto.
	app.establecer("voz.salida", "lector")
	robot.tecla(pygame.K_F12)
	robot.tecla(pygame.K_F12, pygame.KMOD_LCTRL | pygame.KMOD_LALT)
	assert app.config.obtener("voz.salida") == "lector"


def test_f12_es_una_tecla_fija(robot: Robot):
	from app.entrada import teclado

	assert teclado.es_fija("ctrl+f12") and teclado.es_fija("f12")
	cambio = robot.app.entrada.teclado.mapa.cambiar("juego", "donde_estoy", "f12")
	assert not cambio.hecho and "reservada" in cambio.frase
	# Un mapa guardado a mano con F12 no la quita a la emergencia.
	mapa = teclado.MapaTeclado({"juego": {"ctrl+f12": "donde_estoy"}})
	assert mapa.accion_de("juego", "ctrl+f12") is None


def test_voz_en_caliente_desde_el_estudio(robot: Robot, tmp_path):
	"""El Estudio cambia «voz.salida» en el fichero compartido y pide releer: el reproductor la aplica al momento."""
	app = robot.app
	otra = Configuracion(app.config.ruta)
	otra.establecer("voz.salida", "ninguna")
	assert "voz.salida" in app.releer_configuracion()
	assert app.voz.salida == "ninguna"
	marca = robot.marca()
	app.decir("Hola")
	assert robot.dicho(marca) == "" and app.voz.ultimo == "Hola"
