"""Pruebas de la pantalla de juego: elegir entorno y actividad, jugar, pausa, fin, grabación, tutorial y mando."""

# ruff: noqa: F811 - los parámetros de las pruebas se llaman como las fixtures importadas
from __future__ import annotations

import shutil

import pygame
import pytest

from app.dominio.formato import cargar_paquete, guardar_paquete
from app.dominio.modelo import Objeto
from app.reproductor import puente_actividades
from app.reproductor.menus import Menu
from app.reproductor.pantallas.juego import PAUSA_MENU, PantallaJuego
from app.seguimiento.grabadora import leer_sesion

from .test_reproductor_comun import (  # noqa: F401 - fixtures
	VIVIENDA,
	Robot,
	actividades,
	app,
	crear_app,
	paquete_con_busqueda,
	robot,
	sin_navegador,
)
from .test_reproductor_menus import MandoFalso


def _sesiones(data_temporal) -> list[dict]:
	return [leer_sesion(ruta) for ruta in sorted((data_temporal / "sessions").glob("*.json.gz"))]


def _empezar_busqueda(robot: Robot, data_temporal, **extra) -> PantallaJuego:
	"""Desde el menú principal: Elegir entorno → la vivienda con juego → «Busca los premios»."""
	paquete_con_busqueda(data_temporal / "entornos", **extra)
	robot.elegir("Elegir entorno")
	robot.elegir("Vivienda de ejemplo")
	robot.elegir("Busca los premios", 3)
	assert isinstance(robot.cima, PantallaJuego)
	return robot.partida


def _recoger_todo(robot: Robot) -> None:
	for premio in list(robot.partida.datos["premios"]):
		if robot.partida.terminado:
			break
		robot.seguir((premio["planta"], premio["x"], premio["y"]))
		robot.esperar(3)


# ── Elegir y jugar ───────────────────────────────────────────────────────────


def test_elegir_entorno_lista_ejemplos_y_propios_con_su_descripcion(robot: Robot, data_temporal, actividades):
	paquete_con_busqueda(data_temporal / "entornos")
	robot.elegir("Elegir entorno")
	opciones = robot.opciones()
	assert opciones[0] == "Vivienda de ejemplo", "primero los entornos del profesional"
	assert "Vivienda de ejemplo, de ejemplo" in opciones and "Barrio de ejemplo, de ejemplo" in opciones
	marca = robot.marca()
	robot.accion("ayuda")
	assert "Un piso pequeño" in robot.dicho(marca) and "1 actividad" in robot.dicho(marca)
	robot.accion("menu_aceptar", 2)
	assert robot.cima.titulo == "Vivienda de ejemplo"
	assert robot.opciones()[:2] == ["Busca los premios", "Exploración libre"]
	robot.accion("ayuda")
	assert robot.ultimo() == "Doble: Encuentra los premios escondidos por la casa.", "la descripción la da describir_actividad"


def test_vivienda_de_ejemplo_busqueda_de_premios_completa(robot: Robot, data_temporal, actividades):
	partida = _empezar_busqueda(robot, data_temporal)
	robot.esperar(5)
	assert "Hay monedas escondidas" in robot.dicho()
	assert partida.modo == "juego" and partida.nombre_actividad == "Busca los premios"
	assert partida.texto_objetivo() == "Encuentra todos los premios. Llevas 0 de 2."
	robot.app.dibujar()
	_recoger_todo(robot)
	robot.esperar(3)
	# Fin de actividad: resultado hablado, estrellas, medalla y celebración.
	assert partida.terminado and partida.completada
	assert isinstance(robot.cima, Menu) and robot.cima.titulo == "Fin de Busca los premios"
	final = robot.ultimo()
	assert "Actividad completada." in final and "Has conseguido 3 estrellas." in final
	assert "Has conseguido 2 de 2." in final and "20 puntos." in final
	assert "Premios nuevos: Estrella 1, Estrella 2, Estrella 3, Medalla de explorador." in final
	assert "mejor resultado" in final
	sonidos = robot.sonidos()
	assert sonidos.count("premio/recogido") == 2 and "logro/estrella_3" in sonidos
	# La colección del alumno.
	perfil = robot.app.perfil
	assert perfil.estrellas() == 3 and perfil.cuenta_premios() == {"estrella": 3, "medalla": 1}
	assert perfil.ultima["actividad"] == "busca" and perfil.ultima["entorno"] == "Vivienda de ejemplo"
	# Cuestionario opcional.
	robot.elegir("Responder unas preguntas")
	assert "Pregunta 1 de 2. ¿Te ha costado?" in robot.ultimo() and "Dos preguntas, si quieres." in robot.ultimo()
	robot.elegir("Regular")
	robot.elegir("Prefiero no contestar")
	assert "Tus respuestas se han guardado" in robot.dicho()
	assert not any(o.startswith("Responder") for o in robot.opciones()), "las preguntas se hacen una vez"
	assert partida.actividad.valoracion == {"esfuerzo": 2}
	robot.elegir("Volver al menú principal")
	assert robot.pantallas() == ["Menu"] and robot.app.partida is None
	# La sesión grabada.
	(sesion,) = _sesiones(data_temporal)
	manifiesto = sesion["manifiesto"]
	assert manifiesto["alias"] == "Luna" and manifiesto["completada"] is True and manifiesto["parcial"] is False
	assert manifiesto["entorno"]["nombre"] == "Vivienda de ejemplo" and manifiesto["actividad"]["id"] == "busca"
	assert manifiesto["actividad"]["tipo"] == "busqueda" and manifiesto["modo"] == "juego"
	tipos = [evento["tipo"] for evento in sesion["traza"]["eventos"]]
	assert tipos.count("premio") == 2 and "inicio" in tipos and "entrada_espacio" in tipos
	assert tipos.count("recompensa") == 4 and "valoracion" in tipos
	assert len(sesion["traza"]["muestras"]) >= 2
	assert robot.app.fallos == 0
	# «Mis premios» y «Continuar».
	robot.elegir("Mis premios")
	assert robot.opciones()[0] == "Tienes 3 estrellas, 1 medalla."
	robot.atras()
	assert robot.opciones()[0] == "Continuar: Busca los premios, en Vivienda de ejemplo"
	robot.elegir("Continuar", 3)
	assert isinstance(robot.cima, PantallaJuego) and robot.partida.id_actividad == "busca"


def test_las_muestras_se_graban_cuatro_veces_por_segundo(robot: Robot, data_temporal, actividades):
	_empezar_busqueda(robot, data_temporal)
	robot.segundos(2.0)
	robot.andar(2)
	robot.segundos(1.0)
	robot.tecla(pygame.K_ESCAPE)
	robot.elegir("Abandonar la actividad")
	robot.elegir("Sí, abandonar", 3)
	assert robot.pantallas() == ["Menu"]
	assert "Actividad abandonada." in robot.ultimo()
	(sesion,) = _sesiones(data_temporal)
	muestras = sesion["traza"]["muestras"]
	assert 10 <= len(muestras) <= 15, "unos tres segundos a cuatro muestras por segundo"
	assert sesion["manifiesto"]["completada"] is False and sesion["manifiesto"]["frecuencia_hz"] == 4
	assert sesion["resumen"], "el resumen lo calcula la grabadora"
	assert robot.app.perfil.estrellas() == 0, "abandonar no da premios"


def test_repetir_la_actividad_graba_dos_sesiones(robot: Robot, data_temporal, actividades):
	_empezar_busqueda(robot, data_temporal, premios=1)
	_recoger_todo(robot)
	robot.esperar(3)
	primera = robot.partida
	robot.elegir("Repetir la actividad", 3)
	assert robot.partida is not primera and isinstance(robot.cima, PantallaJuego)
	assert not robot.partida.terminado and robot.pantallas() == ["Menu", "PantallaJuego"]
	assert len(_sesiones(data_temporal)) == 1, "la primera ya está guardada"
	_recoger_todo(robot)
	robot.esperar(3)
	assert "mejor resultado" not in robot.ultimo(), "repetir con las mismas estrellas no es una marca nueva"
	robot.elegir("Elegir otra actividad", 2)
	assert robot.cima.titulo == "Vivienda de ejemplo" and len(_sesiones(data_temporal)) == 2


def test_exploracion_libre_de_la_vivienda_de_ejemplo(robot: Robot, data_temporal):
	robot.elegir("Elegir entorno")
	robot.elegir("Vivienda de ejemplo, de ejemplo")
	robot.elegir("Exploración libre", 5)
	partida = robot.partida
	assert partida.libre and partida.modo == "practica"
	assert "Exploración libre de Vivienda de ejemplo." in robot.dicho()
	marca = robot.marca()
	robot.tecla(pygame.K_c, unicode="c")
	assert "Estás en" in robot.dicho(marca), "«dónde estoy» llega a la sesión por la tecla C"
	robot.tecla(pygame.K_o, unicode="o")
	assert "No hay ningún objetivo" in robot.dicho(marca)
	antes = (robot.jugador.x, robot.jugador.y)
	robot.tecla(pygame.K_UP)
	assert (robot.jugador.x, robot.jugador.y) != antes
	assert any(nombre.startswith("pasos/") for nombre in robot.sonidos())
	assert robot.app.motor.de("oyente"), "el presentador sitúa al oyente con la sesión"
	robot.tecla(pygame.K_ESCAPE)
	assert "Terminar la exploración" in robot.opciones()
	robot.elegir("Terminar la exploración")
	robot.elegir("Sí, terminar", 3)
	assert "Exploración terminada. Has recorrido" in robot.ultimo()
	(sesion,) = _sesiones(data_temporal)
	assert sesion["manifiesto"]["actividad"]["tipo"] == "exploracion" and sesion["manifiesto"]["completada"] is False


def test_con_las_actividades_reales_una_busqueda_completa(robot: Robot, data_temporal):
	"""El mismo recorrido con ``app.actividades`` de verdad (se salta si el paquete aún no se puede importar)."""
	if not puente_actividades.disponible():
		pytest.skip("app.actividades no está disponible")
	partida = _empezar_busqueda(robot, data_temporal)
	robot.esperar(5)
	assert type(partida.actividad).__module__.startswith("app.actividades"), "es la actividad real, no un doble"
	assert "Hay monedas escondidas" in robot.dicho()
	assert partida.estado_actividad()["total"] == 2 and "moneda" in partida.texto_objetivo()
	robot.app.dibujar()
	for premio in list(partida.datos["premios"]):
		if partida.terminado:
			break
		robot.seguir((premio["planta"], premio["x"], premio["y"]))
		robot.esperar(5)
		if not partida.terminado and str(premio["id"]) not in partida.premios_recogidos:
			robot.accion("interactuar", 5)
	robot.esperar(5)
	assert partida.terminado and partida.completada, partida.estado_actividad()
	assert isinstance(robot.cima, Menu) and robot.cima.titulo == "Fin de Busca los premios"
	final = robot.ultimo()
	assert "Actividad completada." in final and "Has conseguido 2 de 2." in final and "estrella" in final
	assert "0 puntos" not in final, "una actividad que no puntúa no dice puntos"
	perfil = robot.app.perfil
	assert perfil.cuenta_premios().get("estrella", 0) >= 1 and perfil.cuenta_premios().get("objeto", 0) == 2
	robot.elegir("Volver al menú principal")
	(sesion,) = _sesiones(data_temporal)
	assert sesion["manifiesto"]["completada"] is True and sesion["manifiesto"]["actividad"]["tipo"] == "busqueda"
	tipos = [evento["tipo"] for evento in sesion["traza"]["eventos"]]
	assert tipos.count("premio") == 2 and "recompensa" in tipos
	# La segunda vez, la actividad sabe las estrellas que el alumno ya tenía.
	robot.elegir("Continuar", 3)
	assert robot.partida.actividad.datos["recompensas"]["estrellas_previas"] == perfil.cuenta_premios()["estrella"]
	assert robot.app.fallos == 0


# ── Pausa ────────────────────────────────────────────────────────────────────


def test_pausa_y_reanudacion(robot: Robot, data_temporal, actividades):
	partida = _empezar_busqueda(robot, data_temporal)
	robot.segundos(1.0)
	robot.tecla(pygame.K_ESCAPE)
	assert robot.cima.titulo == "Pausa."
	assert robot.opciones() == [
		"Continuar",
		"Recordar el objetivo",
		"Repetir las instrucciones",
		"Opciones rápidas",
		"Volver al inicio",
		"Ayuda",
		"Abandonar la actividad",
	]
	robot.esperar(2)
	assert partida.sesion.pausado and partida.pausas == {PAUSA_MENU}
	assert robot.app.motor.de("pausar")[-1] == {"si": True}
	activo = partida.sesion.t
	posicion = (robot.jugador.x, robot.jugador.y)
	robot.segundos(1.0)
	assert partida.sesion.t == activo, "en pausa no corre el tiempo activo"
	assert partida.sesion.tiempo_pausa > 0.9
	robot.elegir("Recordar el objetivo")
	assert robot.app.voz.registro[-1][:2] == ("Encuentra todos los premios. Llevas 0 de 2.", "ayuda")
	robot.elegir("Repetir las instrucciones")
	assert robot.ultimo() == "Hay monedas escondidas. ¡Búscalas!"
	robot.elegir("Opciones rápidas")
	assert robot.ajustar("Las distancias se dicen en") == "Las distancias se dicen en: pasos"
	assert partida.sesion.ajustes.unidad == "pasos", "la opción se aplica a la partida en marcha"
	robot.atras()
	robot.elegir("Continuar", 3)
	assert robot.cima is partida and not partida.sesion.pausado and not partida.pausas
	assert robot.app.motor.de("pausar")[-1] == {"si": False}
	assert "Continúa." in robot.dicho()
	robot.segundos(0.5)
	assert partida.sesion.t > activo
	assert (robot.jugador.x, robot.jugador.y) == posicion
	# Volver al inicio desde la pausa.
	robot.andar(2)
	robot.tecla(pygame.K_ESCAPE)
	robot.elegir("Volver al inicio", 4)
	inicio = partida.entorno.inicio
	assert (robot.jugador.x, robot.jugador.y) == (inicio.x, inicio.y)
	assert "Has vuelto al inicio." in robot.dicho()
	# La pausa queda en la grabación.
	robot.tecla(pygame.K_ESCAPE)
	robot.elegir("Abandonar la actividad")
	robot.elegir("No, seguir jugando")
	assert robot.cima.titulo == "Pausa.", "decir que no deja en la pausa"
	robot.elegir("Abandonar la actividad")
	robot.elegir("Sí, abandonar", 3)
	(sesion,) = _sesiones(data_temporal)
	assert len(sesion["traza"]["pausas"]) == 3
	assert [e["tipo"] for e in sesion["traza"]["eventos"]].count("pausa") >= 4


def test_perder_el_foco_pausa_el_juego(robot: Robot, data_temporal, actividades):
	partida = _empezar_busqueda(robot, data_temporal)
	robot.app.inyectar("avanzar", mantener=True)
	robot.app.evento(pygame.event.Event(pygame.WINDOWFOCUSLOST))
	robot.esperar(2)
	assert robot.cima.titulo == "Pausa." and partida.sesion.pausado
	assert not robot.app.con_foco
	robot.app.evento(pygame.event.Event(pygame.WINDOWFOCUSGAINED))
	assert robot.app.con_foco


def test_la_ayuda_durante_el_juego_pausa_y_lista_los_controles(robot: Robot, data_temporal, actividades):
	partida = _empezar_busqueda(robot, data_temporal)
	robot.tecla(pygame.K_F1, fotogramas=2)
	assert robot.cima.titulo == "Ayuda: controles para recorrer el entorno"
	assert partida.sesion.pausado
	assert "F5: mostrar u ocultar el plano." in robot.opciones()
	robot.atras()
	robot.esperar(2)
	assert robot.cima is partida and not partida.sesion.pausado


def test_plano_y_pantalla_en_negro_con_sus_teclas(robot: Robot, data_temporal, actividades):
	_empezar_busqueda(robot, data_temporal)
	robot.app.dibujar()
	fondo = robot.app.paleta[0]
	colores = {robot.app.lienzo.get_at((x, y))[:3] for x in range(20, 940, 8) for y in range(80, 480, 8)}
	assert len(colores - {fondo}) >= 3, "el plano dibuja suelos, paredes y al alumno"
	robot.tecla(pygame.K_F5)
	assert robot.ultimo() == "Plano oculto." and robot.app.config.obtener("juego.ver_plano") is False
	robot.app.dibujar()
	robot.tecla(pygame.K_F6)
	assert robot.ultimo() == "Pantalla en negro."
	robot.app.dibujar()
	assert robot.app.lienzo.get_at((480, 300))[:3] == (0, 0, 0)
	robot.tecla(pygame.K_F6)
	robot.tecla(pygame.K_F5)
	robot.app.establecer("general.alto_contraste", True)
	robot.app.dibujar()
	assert robot.app.fallos == 0


# ── Robustez ─────────────────────────────────────────────────────────────────


def test_paquete_danado_se_dice_y_se_sigue_en_el_menu(robot: Robot, data_temporal):
	carpeta = data_temporal / "entornos"
	carpeta.mkdir(parents=True)
	(carpeta / "roto.elab").write_bytes(b"PK esto no es un zip")
	robot.elegir("Elegir entorno")
	assert robot.opciones()[0] == "roto, no se puede abrir"
	marca = robot.marca()
	robot.accion("menu_aceptar", 2)
	assert "no es un paquete de EntornoLab o está dañado" in robot.dicho(marca)
	assert robot.app.voz.registro[-1][1] == "aviso"
	assert robot.cima.titulo == "Elegir entorno" and robot.app.partida is None
	assert "logro/error" in robot.sonidos()


def test_actividad_mal_definida_no_rompe_el_menu(robot: Robot, data_temporal, actividades):
	paquete_con_busqueda(data_temporal / "entornos", tipo="rota")
	robot.elegir("Elegir entorno")
	robot.elegir("Vivienda de ejemplo")
	marca = robot.marca()
	robot.elegir("Busca los premios")
	assert "no se puede preparar: está mal definida" in robot.dicho(marca)
	assert robot.cima.titulo == "Vivienda de ejemplo" and robot.app.partida is None


def test_sin_modulo_de_actividades_queda_la_exploracion_libre(robot: Robot, data_temporal, monkeypatch):
	monkeypatch.setattr(puente_actividades, "modulo", lambda: None)
	paquete_con_busqueda(data_temporal / "entornos")
	robot.elegir("Elegir entorno")
	robot.elegir("Vivienda de ejemplo")
	marca = robot.marca()
	robot.elegir("Busca los premios")
	assert "no se pueden jugar actividades" in robot.dicho(marca)
	robot.elegir("Exploración libre", 3)
	assert isinstance(robot.cima, PantallaJuego)


def test_complemento_que_falta_el_objeto_queda_como_caja_y_se_avisa_una_vez(robot: Robot, data_temporal):
	original = cargar_paquete(VIVIENDA)
	planta = original.entorno.plantas[0]
	inicio = original.entorno.inicio
	planta.objetos.append(
		Objeto(id="obj-raro", nombre="Máquina rara", tipo="inexistente/maquina", x=inicio.x + 1.4, y=inicio.y, ancho=0.6, fondo=0.6)
	)
	carpeta = data_temporal / "entornos"
	carpeta.mkdir(parents=True)
	guardar_paquete(carpeta / "con-objeto-raro.elab", original.entorno)
	robot.elegir("Elegir entorno")
	robot.elegir("Vivienda de ejemplo")
	robot.elegir("Exploración libre", 3)
	avisos = [texto for texto, canal in robot.canales() if "inexistente" in texto]
	assert avisos == ["Exploración libre de Vivienda de ejemplo. Falta el complemento inexistente: sus objetos aparecen como cajas."]
	info = robot.sesion.mundo.objeto("obj-raro")
	assert info is not None and info.definicion is None and info.bloquea, "sigue ahí, como una caja con su tamaño"
	robot.tecla(pygame.K_ESCAPE)
	robot.elegir("Continuar", 3)
	robot.segundos(1.0)
	assert len([texto for texto, _canal in robot.canales() if "inexistente" in texto]) == 1, "no se repite al volver de la pausa"
	robot.app.dibujar()
	assert robot.app.fallos == 0


def test_un_fallo_en_un_fotograma_se_registra_y_no_cierra(robot: Robot, data_temporal, monkeypatch, caplog):
	robot.elegir("Elegir entorno")
	robot.elegir("Vivienda de ejemplo, de ejemplo")
	robot.elegir("Exploración libre", 3)
	partida = robot.partida
	tics: list[float] = []
	tic_original = robot.app.motor.tic
	monkeypatch.setattr(robot.app.motor, "tic", lambda dt: (tics.append(dt), tic_original(dt))[1])

	def romper(dt: float):
		raise RuntimeError("fallo de prueba")

	monkeypatch.setattr(partida.sesion, "avanzar", romper)
	robot.esperar(3)
	assert robot.app.activa and robot.app.fallos == 3
	assert "Fallo en un fotograma" in caplog.text and "fallo de prueba" in caplog.text
	assert "Ha habido un problema, pero puedes seguir." in robot.dicho()
	assert len(tics) == 3, "el sonido recibe su tic aunque el fotograma falle"
	robot.esperar(3)
	assert robot.pantallas() == ["Menu"], "si la pantalla sigue fallando se vuelve al menú principal"
	assert robot.app.activa
	robot.accion("menu_abajo")
	assert robot.ultimo().startswith("Mis premios"), "y el menú sigue respondiendo"


def test_cerrar_a_mitad_guarda_la_sesion(data_temporal, sin_navegador, actividades):
	ruta = paquete_con_busqueda(data_temporal / "entornos")
	aplicacion = crear_app(str(ruta), "--actividad", "busca", "--alumno", "Sol")
	robot = Robot(aplicacion)
	assert isinstance(robot.cima, PantallaJuego)
	robot.segundos(1.0)
	aplicacion.cerrar_todo()
	(sesion,) = _sesiones(data_temporal)
	assert sesion["manifiesto"]["alias"] == "Sol" and sesion["manifiesto"]["completada"] is False
	assert sesion["manifiesto"]["parcial"] is False


# ── Tutorial ─────────────────────────────────────────────────────────────────


def test_tutorial_completo(robot: Robot, data_temporal):
	robot.elegir("Tutorial", 3)
	partida = robot.partida
	actividad = partida.actividad
	assert partida.tutorial and partida.grabadora is None
	assert "Vamos a andar. Pulsa flecha arriba dos veces" in robot.dicho()
	claves = [paso.clave for paso in actividad.pasos]
	assert claves == ["avanzar", "chocar", "girar", "rodear", "donde_estoy", "alrededor", "sonda", "puerta", "premio"]

	def paso() -> str:
		return actividad.pasos[actividad.indice].clave

	robot.tecla(pygame.K_UP)
	assert paso() == "avanzar", "hacen falta dos pasos"
	robot.tecla(pygame.K_UP, fotogramas=2)
	assert paso() == "chocar"
	for _i in range(6):
		if paso() != "chocar":
			break
		robot.tecla(pygame.K_UP, fotogramas=2)
	assert paso() == "girar", "al chocar con la mesa se pasa a girar"
	assert "golpe/madera" in robot.sonidos() or any(s.startswith("golpe/") for s in robot.sonidos())
	robot.tecla(pygame.K_o, unicode="o", fotogramas=2)
	assert "Para rodearla hay que girar" in robot.ultimo(), "«objetivo» repite el paso"
	robot.tecla(pygame.K_LEFT, fotogramas=2)
	assert paso() == "rodear"
	marca = robot.marca()
	robot.tecla(pygame.K_p, unicode="p", fotogramas=2)
	assert "El otro lado de la mesa está" in robot.dicho(marca), "«pista» dice hacia dónde ir"
	# Rodea la mesa por el norte: dos pasos al norte, y al este hasta dejarla atrás.
	robot.andar(2)
	robot.tecla(pygame.K_RIGHT, fotogramas=2)
	for _i in range(6):
		if paso() != "rodear":
			break
		robot.tecla(pygame.K_UP, fotogramas=2)
	assert paso() == "donde_estoy"
	robot.tecla(pygame.K_c, unicode="c", fotogramas=2)
	assert paso() == "alrededor"
	robot.tecla(pygame.K_q, unicode="q", fotogramas=2)
	assert paso() == "sonda"
	robot.tecla(pygame.K_b, unicode="b", fotogramas=2)
	assert paso() == "puerta"
	# Hasta la puerta, que está en el centro de la pared del este, y se abre.
	puerta = actividad.piezas["puerta"]
	centro = ((puerta.a[0] + puerta.b[0]) / 2, (puerta.a[1] + puerta.b[1]) / 2)
	robot.ir_a(robot.jugador.x, centro[1], abrir=False)
	robot.girar_a(90.0)
	for _i in range(8):
		if paso() != "puerta":
			break
		antes = robot.jugador.x
		robot.tecla(pygame.K_UP, fotogramas=2)
		if robot.jugador.x - antes < 0.1:
			robot.tecla(pygame.K_RETURN, unicode="\r", fotogramas=2)
	assert paso() == "premio"
	assert "premio_tutorial" in {fuente.id for fuente in robot.sesion.fuentes()}, "el premio suena al abrir la puerta"
	for _i in range(8):
		if partida.terminado:
			break
		robot.tecla(pygame.K_UP, fotogramas=2)
	robot.esperar(3)
	assert partida.terminado and partida.completada
	assert robot.pantallas() == ["Menu"]
	assert "Tutorial terminado. Ya conoces los controles básicos." in robot.ultimo()
	assert "premio/recogido" in robot.sonidos() and "logro/logro" in robot.sonidos()
	assert robot.app.perfil.tutorial_hecho
	assert not list((data_temporal / "sessions").glob("*.json.gz")), "el tutorial no se graba"
	assert robot.app.fallos == 0


def test_el_tutorial_funciona_sin_el_complemento_del_hogar():
	from app.dominio.catalogo import Catalogo
	from app.reproductor.pantallas import tutorial

	entorno, piezas = tutorial.crear_entorno_tutorial(Catalogo())
	assert piezas["mesa"].tipo == "caja" and len(entorno.plantas[0].espacios) == 2
	assert piezas["puerta"].estado == "cerrada"


# ── Mando ────────────────────────────────────────────────────────────────────


def test_mando_simulado_botones_palanca_y_vibracion(robot: Robot, data_temporal):
	from app.entrada.mando import SDL_DE_BOTON, SDL_DE_EJE

	mando = MandoFalso()
	robot.app.entrada.mandos.conectar(mando, 3)
	robot.elegir("Elegir entorno")
	robot.elegir("Vivienda de ejemplo, de ejemplo")
	robot.elegir("Exploración libre", 3)

	def boton(nombre: str, fotogramas: int = 2) -> None:
		robot.app.evento(pygame.event.Event(pygame.CONTROLLERBUTTONDOWN, instance_id=3, button=SDL_DE_BOTON[nombre]))
		robot.app.evento(pygame.event.Event(pygame.CONTROLLERBUTTONUP, instance_id=3, button=SDL_DE_BOTON[nombre]))
		robot.esperar(fotogramas)

	def eje(nombre: str, valor: float) -> None:
		robot.app.evento(pygame.event.Event(pygame.CONTROLLERAXISMOTION, instance_id=3, axis=SDL_DE_EJE[nombre], value=int(valor * 32767)))

	marca = robot.marca()
	boton("x")
	assert "Estás en" in robot.dicho(marca), "X es «dónde estoy»"
	rumbo = robot.jugador.rumbo
	boton("rb")
	assert robot.jugador.rumbo != rumbo, "RB gira a la derecha"
	# La palanca izquierda hacia delante anda mientras se mantiene.
	antes = (robot.jugador.x, robot.jugador.y)
	nombres_ejes = list(SDL_DE_EJE)
	eje_avance = next(nombre for nombre in nombres_ejes if nombre.endswith("y") and ("izq" in nombre or nombre.startswith("l")))
	eje(eje_avance, -1.0)
	robot.segundos(1.5)
	eje(eje_avance, 0.0)
	robot.esperar(2)
	assert (robot.jugador.x, robot.jugador.y) != antes, "la palanca llega a Sesion.analogico"
	# Anda hasta chocar: el mando vibra.
	for _i in range(40):
		robot.accion("avanzar")
		if robot.sesion.movimiento.choques:
			break
	robot.esperar(10)
	assert robot.sesion.movimiento.choques >= 1
	assert mando.vibraciones, "un choque hace vibrar el mando"
	# Pausa con el botón de menú, y vuelta con B.
	boton("menu")
	assert robot.cima.titulo == "Pausa."
	boton("b", 3)
	assert isinstance(robot.cima, PantallaJuego)
	# La vibración se puede apagar en caliente.
	robot.app.establecer("mando.vibracion", False)
	assert robot.app.entrada.mandos.opciones["vibracion"] is False


def test_con_mando_las_frases_del_juego_nombran_botones(robot: Robot, data_temporal):
	robot.app.entrada.mandos.conectar(MandoFalso("PS5 Controller"), 4)
	robot.elegir("Tutorial", 3)
	dicho = robot.dicho()
	assert "cruceta" in dicho or "palanca" in dicho or "botón" in dicho
	assert "flecha arriba" not in dicho.split("Tutorial.")[-1], "con mando el tutorial no habla de flechas"


@pytest.fixture(autouse=True)
def _limpiar_sesiones(data_temporal):
	yield
	shutil.rmtree(data_temporal / "sessions", ignore_errors=True)
