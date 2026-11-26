"""Pruebas de la supervisión y del modo recorrido: el reproductor contra una ``Sala`` de verdad en 127.0.0.1."""

# ruff: noqa: F811 - los parámetros de las pruebas se llaman como las fixtures importadas
from __future__ import annotations

import time
from collections.abc import Callable
from typing import Any

import pygame
import pytest

from app.dominio.formato import cargar_paquete, guardar_paquete
from app.dominio.modelo import Objeto
from app.reproductor.menus import EntradaTexto, Menu
from app.reproductor.pantallas.juego import PAUSA_PROFESOR, PantallaJuego
from app.reproductor.supervision import deletrear_huella
from app.seguimiento.grabadora import leer_sesion
from app.supervision import descubrimiento
from app.supervision.sala import Sala
from tests._supervision_util import alumno_de

from .test_reproductor_comun import VIVIENDA, Robot, actividades, app, crear_app, paquete_con_busqueda, robot, sin_navegador  # noqa: F401 - fixtures

CODIGO = "246810"
RAPIDO = {"intervalo_estado": 0.05, "intervalo_latido": 0.2, "tiempo_muerto": 1.0, "reintento_min": 0.05, "reintento_max": 0.2}


@pytest.fixture
def sala():
	abierta = Sala(nombre="Aula de pruebas", intervalo_latido=0.2, tiempo_muerto=1.0)
	abierta.iniciar(0, CODIGO)
	yield abierta
	abierta.detener()


def hasta(robot: Robot, condicion: Callable[[], Any], segundos: float = 6.0) -> bool:
	"""Deja pasar fotogramas (y tiempo real, para el hilo de red) hasta que se cumpla la condición."""
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		robot.esperar(1)
		if condicion():
			return True
		time.sleep(0.01)
	return bool(condicion())


def conectar(robot: Robot, sala: Sala, codigo: str = CODIGO) -> None:
	robot.app.opciones_cliente = dict(RAPIDO)
	robot.app.conectar_sala("127.0.0.1", sala.puerto, codigo)
	assert hasta(robot, lambda: robot.app.enlace.conectado), "el reproductor no se ha conectado a la sala"


def sucesos(sala: Sala, acumulados: list[dict]) -> list[dict]:
	acumulados.extend(sala.eventos_pendientes())
	return acumulados


def _empezar_busqueda(robot: Robot, data_temporal) -> PantallaJuego:
	paquete_con_busqueda(data_temporal / "entornos")
	robot.elegir("Elegir entorno")
	robot.elegir("Vivienda de ejemplo")
	robot.elegir("Busca los premios", 3)
	return robot.partida


# ── Supervisión ──────────────────────────────────────────────────────────────


def test_supervision_estado_ordenes_y_fin(robot: Robot, sala: Sala, data_temporal, actividades):
	conectar(robot, sala)
	assert "Conectado con tu profesor, en la sala Aula de pruebas." in robot.dicho()
	partida = _empezar_busqueda(robot, data_temporal)
	vistos: list[dict] = []

	# Estado: dónde está, descrito en palabras, con objetivo y contadores.
	assert hasta(robot, lambda: (alumno_de(sala, "Luna") or {}).get("actividad") == "Busca los premios")
	assert hasta(robot, lambda: bool((alumno_de(sala, "Luna") or {}).get("espacio")))
	ficha = alumno_de(sala, "Luna")
	assert ficha["entorno"] == "Vivienda de ejemplo" and ficha["modo"] == "juego" and not ficha["recorrido"]
	assert ficha["planta"] == robot.jugador.planta and ficha["x"] == pytest.approx(robot.jugador.x, abs=0.01)
	assert "Estás en" in ficha["posicion"] or ficha["espacio"] in ficha["posicion"], ficha["posicion"]
	assert ficha["contadores"]["objetivo"] == "Encuentra todos los premios" and ficha["contadores"]["total"] == 2
	assert ficha["delante"], "qué tiene delante"

	# Eventos y voz: lo que le pasa y lo que oye el alumno.
	robot.andar(2)
	marca = robot.marca()
	robot.tecla(pygame.K_c, unicode="c", fotogramas=2)
	oido = robot.dicho(marca)
	assert hasta(robot, lambda: any(s["tipo"] == "voz" and s["datos"]["texto"] in oido for s in sucesos(sala, vistos)))
	assert any(s["tipo"] == "evento" and s["datos"]["tipo"] == "inicio" for s in vistos)
	assert any(s["tipo"] == "evento" and s["datos"]["tipo"] == "ayuda" for s in vistos)
	assert hasta(robot, lambda: alumno_de(sala, "Luna")["contadores"]["ayudas"] >= 1)

	# Pausa y reanudación.
	assert sala.pedir("Luna", "pausa")
	assert hasta(robot, lambda: partida.sesion.pausado)
	assert partida.pausas == {PAUSA_PROFESOR}
	assert ("Tu profesor ha puesto el juego en pausa.", "profesional") in robot.canales()
	posicion = (robot.jugador.x, robot.jugador.y)
	robot.tecla(pygame.K_UP, fotogramas=2)
	assert (robot.jugador.x, robot.jugador.y) == posicion and "lo ha parado tu profesor" in robot.ultimo()
	assert hasta(robot, lambda: alumno_de(sala, "Luna")["pausado"] is True)
	assert sala.pedir("Luna", "reanudar")
	assert hasta(robot, lambda: not partida.sesion.pausado)
	assert "Tu profesor ha reanudado el juego." in robot.dicho()

	# Mensaje: por el canal del profesional y repasable en el historial.
	assert sala.pedir("Luna", "mensaje", texto="Muy bien, sigue por la pared")
	assert hasta(robot, lambda: ("Muy bien, sigue por la pared", "profesional") in robot.canales())
	historial = list(zip(robot.app.voz.historial, robot.app.voz.historial_canales, strict=True))
	assert ("Muy bien, sigue por la pared", "profesional") in historial
	robot.tecla(pygame.K_F2)
	assert robot.app.voz.registro[-1][:2] == ("Muy bien, sigue por la pared", "historial")

	# Recolocar.
	inicio = partida.entorno.inicio
	assert sala.pedir("Luna", "recolocar", planta=inicio.planta, x=inicio.x + 0.5, y=inicio.y, rumbo=180)
	assert hasta(robot, lambda: robot.jugador.rumbo == 180.0)
	assert (robot.jugador.x, robot.jugador.y) == (inicio.x + 0.5, inicio.y)

	# Pista, ayudas y premio: los atiende la actividad.
	assert sala.pedir("Luna", "pista", texto="Mira hacia la cocina")
	assert sala.pedir("Luna", "ayudas", ayudas={"sonda": {"permitida": False, "limite": None}})
	assert sala.pedir("Luna", "premio", nombre="una llave")
	assert hasta(robot, lambda: len(partida.actividad.ordenes) == 4)
	# El mensaje de antes también le llega a la actividad (una visita narrada lo cuenta).
	assert [tipo for tipo, _datos in partida.actividad.ordenes] == ["mensaje", "pista", "ayudas", "premio"]
	assert ("Mira hacia la cocina", "profesional") in robot.canales()
	assert partida.sesion.ajustes.ayudas["sonda"]["permitida"] is False
	robot.app.establecer("juego.unidad", "pasos")
	assert partida.sesion.ajustes.ayudas["sonda"]["permitida"] is False, "lo que fija el profesor sobrevive a un cambio de opciones"
	assert sala.pedir("Luna", "marca", texto="Aquí duda")
	# Más de un segundo de juego: la sala toma un estado con menos tiempo activo por una sesión recién reiniciada.
	robot.segundos(1.5)

	# Terminar: el fin llega a la sala y la sesión queda grabada con las intervenciones.
	assert sala.pedir("Luna", "terminar")
	assert hasta(robot, lambda: partida.terminado)
	assert hasta(robot, lambda: alumno_de(sala, "Luna")["terminado"] is True)
	assert any(s["tipo"] == "fin" and s["datos"]["completada"] is False for s in sucesos(sala, vistos))
	assert isinstance(robot.cima, Menu) and robot.cima.titulo == "Fin de Busca los premios"
	assert "Tu profesor ha terminado la actividad." in robot.dicho()
	robot.elegir("Volver al menú principal")
	(ruta,) = sorted((data_temporal / "sessions").glob("*.json.gz"))
	traza = leer_sesion(ruta)["traza"]
	intervenciones = [e["datos"]["tipo"] for e in traza["eventos"] if e["tipo"] == "intervencion"]
	assert intervenciones == ["pausa", "reanudar", "mensaje", "recolocar", "pista", "ayudas", "premio", "terminar"]
	assert "sigue por la pared" not in str(traza["eventos"]), "el texto de los mensajes no se guarda"
	assert [m["texto"] for m in traza["marcas"]] == ["Aquí duda"]
	assert robot.app.fallos == 0


def test_reiniciar_la_actividad_desde_la_sala(robot: Robot, sala: Sala, data_temporal, actividades):
	conectar(robot, sala)
	partida = _empezar_busqueda(robot, data_temporal)
	robot.andar(3)
	primera = partida.sesion
	assert sala.pedir("Luna", "reiniciar")
	assert hasta(robot, lambda: partida.sesion is not primera)
	assert "Tu profesor ha reiniciado la actividad" in robot.dicho()
	inicio = partida.entorno.inicio
	assert (robot.jugador.x, robot.jugador.y) == (inicio.x, inicio.y) and not partida.terminado
	assert len(list((data_temporal / "sessions").glob("*.json.gz"))) == 1, "lo jugado antes de reiniciar queda guardado"
	robot.andar(1)
	assert robot.app.fallos == 0


def test_si_la_sala_se_cae_se_sigue_jugando_y_se_reconecta(robot: Robot, data_temporal, actividades):
	primera = Sala(nombre="Aula", intervalo_latido=0.2, tiempo_muerto=1.0)
	primera.iniciar(0, CODIGO)
	puerto = primera.puerto
	try:
		conectar(robot, primera)
		partida = _empezar_busqueda(robot, data_temporal)
	finally:
		primera.detener()
	assert hasta(robot, lambda: not robot.app.enlace.conectado)
	assert hasta(robot, lambda: "Se ha perdido la conexión con tu profesor. Puedes seguir jugando" in robot.dicho())
	antes = (robot.jugador.x, robot.jugador.y)
	robot.andar(2)
	assert (robot.jugador.x, robot.jugador.y) != antes, "sin sala se juega igual"
	segunda = Sala(nombre="Aula", intervalo_latido=0.2, tiempo_muerto=1.0)
	segunda.iniciar(puerto, CODIGO)
	try:
		assert hasta(robot, lambda: robot.app.enlace.conectado, 10.0), "se vuelve a conectar sola"
		assert hasta(robot, lambda: "Conexión con tu profesor recuperada." in robot.dicho())
		assert hasta(robot, lambda: (alumno_de(segunda, "Luna") or {}).get("actividad") == "Busca los premios")
		assert not partida.terminado and robot.app.fallos == 0
	finally:
		segunda.detener()


def test_codigo_incorrecto_y_sala_que_no_existe(robot: Robot, sala: Sala):
	robot.app.opciones_cliente = dict(RAPIDO)
	robot.app.conectar_sala("127.0.0.1", sala.puerto, "000000")
	assert hasta(robot, lambda: "El código no es correcto" in robot.dicho())
	assert not robot.app.enlace.conectado and robot.app.enlace.descripcion() == "La sala ha rechazado la conexión."
	robot.app.desconectar_sala()
	# Un puerto en el que no escucha nadie: no se dice nada alarmante y el menú sigue funcionando.
	puerto = sala.puerto
	sala.detener()
	marca = robot.marca()
	robot.app.conectar_sala("127.0.0.1", puerto, CODIGO)
	robot.segundos(0.5)
	time.sleep(0.3)
	robot.accion("menu_abajo")
	assert "Intentando conectar" in robot.app.enlace.descripcion()
	assert "perdido la conexión" not in robot.dicho(marca) and robot.app.fallos == 0


def test_conectar_desde_el_menu_escribiendo_la_direccion_y_el_codigo(robot: Robot, sala: Sala):
	robot.app.opciones_cliente = dict(RAPIDO)
	robot.elegir("Conectar con mi profesor")
	assert robot.opciones()[:3] == [
		"Buscar salas en la red",
		"Escribir la dirección de la sala",
		"El profesor está en este mismo ordenador",
	]
	robot.elegir("Escribir la dirección")
	assert isinstance(robot.cima, EntradaTexto)
	robot.escribir("esto no vale")
	assert "Escriba la dirección de la sala" in robot.ultimo() and robot.app.enlace is None
	robot.elegir("Escribir la dirección")
	robot.escribir(f"127.0.0.1:{sala.puerto}")
	assert isinstance(robot.cima, EntradaTexto) and "código" in robot.ultimo()
	robot.escribir(CODIGO)
	assert robot.pantallas() == ["Menu"]
	assert "Conectando con la sala" in robot.ultimo()
	assert hasta(robot, lambda: robot.app.enlace is not None and robot.app.enlace.conectado)
	assert robot.app.config.obtener("supervision.ultima_sala") == f"127.0.0.1:{sala.puerto}"
	robot.elegir("Conectar con mi profesor")
	assert robot.opciones()[0] == "Conectado con Aula de pruebas." and robot.opciones()[1] == "Desconectar"
	robot.elegir("Desconectar")
	assert robot.app.enlace is None and "Desconectado de la sala." in robot.dicho()


def test_buscar_salas_en_la_red_y_en_este_mismo_ordenador(robot: Robot, sala: Sala, monkeypatch):
	robot.app.opciones_cliente = dict(RAPIDO)
	encontrada = descubrimiento.SalaEncontrada("Aula de pruebas", "127.0.0.1", sala.puerto, False, "")
	respuestas = [[], [encontrada]]
	monkeypatch.setattr(descubrimiento, "buscar_salas", lambda espera=1.5, **_k: respuestas.pop(0))
	robot.elegir("Conectar con mi profesor")
	robot.elegir("Buscar salas en la red")
	assert "Buscando salas en la red." in robot.dicho()
	assert hasta(robot, lambda: "No se ha encontrado ninguna sala" in robot.dicho())
	assert "escríbela" in robot.ultimo(), "siempre se ofrece escribir la dirección"
	robot.elegir("Buscar salas en la red")
	assert hasta(robot, lambda: isinstance(robot.cima, Menu) and robot.cima.titulo == "Salas encontradas")
	robot.elegir("Aula de pruebas")
	robot.escribir(CODIGO)
	assert hasta(robot, lambda: robot.app.enlace is not None and robot.app.enlace.conectado)
	robot.app.desconectar_sala()
	# El profesor en este mismo ordenador: 127.0.0.1 y el puerto de la configuración.
	robot.app.establecer("supervision.puerto", sala.puerto)
	robot.elegir("Conectar con mi profesor")
	robot.elegir("El profesor está en este mismo ordenador")
	robot.escribir(CODIGO)
	assert hasta(robot, lambda: robot.app.enlace is not None and robot.app.enlace.conectado)


def test_un_mensaje_del_profesor_tambien_se_oye_en_los_menus(robot: Robot, sala: Sala):
	conectar(robot, sala)
	assert sala.pedir("Luna", "mensaje", texto="Elige la vivienda")
	assert hasta(robot, lambda: ("Elige la vivienda", "profesional") in robot.canales())
	assert sala.pedir("Luna", "pausa")
	robot.segundos(0.3)
	assert robot.app.fallos == 0, "una orden de juego sin partida se ignora sin romper nada"


def test_la_huella_se_dice_de_forma_comprensible_y_se_pregunta_si_cambia(robot: Robot, sala: Sala):
	huella = "ab12cd34ef56ab78" + "0" * 48
	assert deletrear_huella(huella) == "A B 1 2, C D 3 4, E F 5 6, A B 7 8"
	conectar(robot, sala)
	enlace = robot.app.enlace
	# Primera conexión cifrada: se dice la clave para compararla de viva voz.
	enlace._primera_vez = True
	enlace._conectado_alguna_vez = False
	enlace.cliente.tls = True
	enlace.cliente.huella_sala = huella
	enlace._aviso("conectado", {})
	assert "Es la primera vez que te conectas a esta sala" in robot.ultimo() and "A B 1 2, C D 3 4" in robot.ultimo()
	# La sala presenta otra identificación: no se conecta sin preguntar.
	aceptadas: list[bool] = []
	enlace.cliente.aceptar_huella_nueva = lambda: aceptadas.append(True)
	enlace._aviso("rechazado", {"motivo": "huella"})
	assert robot.cima.titulo == "La sala del profesor ha cambiado de identificación"
	assert robot.opciones() == ["No conectar", "Las letras coinciden: conectar"], "lo seguro va primero"
	assert "A B 1 2, C D 3 4" in robot.ultimo()
	robot.accion("menu_atras")
	assert robot.cima.titulo.startswith("La sala del profesor"), "no se puede esquivar la pregunta"
	robot.elegir("Las letras coinciden")
	assert aceptadas == [True]
	enlace._aviso("rechazado", {"motivo": "huella"})
	robot.elegir("No conectar")
	assert robot.app.enlace is None and "No se ha conectado." in robot.ultimo()


# ── Modo recorrido ───────────────────────────────────────────────────────────


@pytest.fixture
def recorrido(data_temporal, sala: Sala, sin_navegador):
	ruta = data_temporal / "entornos" / "mi-vivienda.elab"
	ruta.parent.mkdir(parents=True)
	original = cargar_paquete(VIVIENDA)
	guardar_paquete(ruta, original.entorno)
	aplicacion = crear_app("--recorrido", str(ruta), "--sala", f"127.0.0.1:{sala.puerto}", "--codigo", CODIGO, "--alumno", "Profe")
	maquina = Robot(aplicacion)
	assert hasta(maquina, lambda: aplicacion.enlace.conectado)
	yield maquina, ruta
	aplicacion.cerrar_todo()


def _peticion(robot: Robot, sala: Sala, vistos: list[dict], accion: str) -> dict:
	assert hasta(robot, lambda: any(s["tipo"] == "peticion" and s["datos"]["accion"] == accion for s in sucesos(sala, vistos))), accion
	suceso = next(s for s in vistos if s["tipo"] == "peticion" and s["datos"]["accion"] == accion)
	vistos.remove(suceso)
	return suceso["datos"]


def test_modo_recorrido_peticiones_contestadas(recorrido, sala: Sala):
	robot, _ruta = recorrido
	partida = robot.partida
	vistos: list[dict] = []
	assert isinstance(robot.cima, PantallaJuego) and partida.recorrido and partida.grabadora is None
	assert "Modo recorrido de Vivienda de ejemplo." in robot.dicho() and "Conectado con el Estudio." in robot.dicho()
	assert hasta(robot, lambda: (alumno_de(sala, "Profe") or {}).get("recorrido") is True)
	robot.andar(1)
	donde = (round(robot.jugador.x, 3), round(robot.jugador.y, 3))

	# Marcar este punto.
	robot.tecla(pygame.K_F4)
	assert robot.cima.titulo == "Menú de edición"
	assert robot.opciones()[:6] == [
		"Colocar un objeto aquí",
		"Poner un premio aquí",
		"Marcar este punto",
		"Medir desde aquí",
		"Medir hasta aquí",
		"Poner aquí el inicio",
	]
	robot.elegir("Marcar este punto")
	assert isinstance(robot.cima, EntradaTexto)
	robot.tecla(pygame.K_BACKSPACE)
	robot.escribir("a")
	assert isinstance(robot.cima, PantallaJuego) and "Petición enviada al Estudio." in robot.dicho()
	pedida = _peticion(robot, sala, vistos, "marcar_punto")
	assert (pedida["x"], pedida["y"]) == donde and pedida["planta"] == robot.jugador.planta
	assert pedida["datos"] == {"nombre": "Punta"}
	assert sala.responder("Profe", pedida["id"], True, "Punto «Punta» marcado")
	assert hasta(robot, lambda: ("Punto «Punta» marcado", "profesional") in robot.canales())

	# Colocar un objeto del catálogo.
	robot.tecla(pygame.K_F4)
	robot.elegir("Colocar un objeto aquí")
	assert len(robot.opciones()) > 3, "las categorías de los complementos instalados"
	robot.accion("menu_aceptar", 2)
	nombre_objeto = robot.opciones()[0]
	robot.accion("menu_aceptar", 2)
	assert isinstance(robot.cima, PantallaJuego)
	pedida = _peticion(robot, sala, vistos, "colocar_aqui")
	assert pedida["datos"]["clase"] == "objeto" and "/" in pedida["datos"]["objeto"] and pedida["datos"]["nombre"] == nombre_objeto
	assert pedida["rumbo"] == round(robot.jugador.rumbo, 1)
	assert sala.responder("Profe", pedida["id"], False, "Aquí no cabe")
	assert hasta(robot, lambda: "Aquí no cabe" in robot.dicho())
	assert "logro/error" in robot.sonidos()

	# Premio, inicio y medida.
	robot.tecla(pygame.K_F4)
	robot.elegir("Poner un premio aquí")
	robot.tecla(pygame.K_RETURN, unicode="\r")
	assert _peticion(robot, sala, vistos, "colocar_aqui")["datos"] == {"clase": "premio", "nombre": "Premio"}
	robot.tecla(pygame.K_F4)
	robot.elegir("Poner aquí el inicio")
	assert _peticion(robot, sala, vistos, "colocar_aqui")["datos"] == {"clase": "inicio"}
	robot.tecla(pygame.K_F4)
	robot.elegir("Medir hasta aquí")
	assert "Primero fija el origen" in robot.ultimo()
	robot.tecla(pygame.K_F4)
	robot.elegir("Medir desde aquí")
	assert _peticion(robot, sala, vistos, "medir_desde_aqui")["datos"] == {"fase": "desde"}
	antes = (robot.jugador.x, robot.jugador.y)
	robot.tecla(pygame.K_F7)
	robot.andar(2)
	recorrida = round(((robot.jugador.x - antes[0]) ** 2 + (robot.jugador.y - antes[1]) ** 2) ** 0.5, 2)
	robot.tecla(pygame.K_F4)
	robot.elegir("Medir hasta aquí")
	assert _peticion(robot, sala, vistos, "medir_desde_aqui")["datos"] == {"fase": "hasta", "distancia_m": recorrida}
	assert f"En línea recta hay {recorrida:.2f}".replace(".", ",") in robot.ultimo()
	assert robot.app.fallos == 0


def test_modo_recorrido_fantasma_saltos_y_recarga(recorrido, sala: Sala):
	robot, ruta = recorrido
	partida = robot.partida
	# Sin fantasma se choca con la pared; con fantasma se atraviesa.
	robot.girar_a(180.0)
	for _i in range(15):
		robot.andar(1)
	bloqueado = (robot.jugador.x, robot.jugador.y)
	robot.andar(1)
	assert (robot.jugador.x, robot.jugador.y) == pytest.approx(bloqueado, abs=0.05), "la pared o el límite paran al profesional"
	robot.tecla(pygame.K_F7)
	assert partida.fantasma and "Modo fantasma activado" in robot.ultimo()
	robot.andar(3)
	assert robot.jugador.y < bloqueado[1] - 1.0, "con el modo fantasma se atraviesa"
	robot.tecla(pygame.K_F7)
	assert not partida.fantasma and "desactivado" in robot.ultimo()

	# Saltar a cualquier lugar desde una lista.
	robot.tecla(pygame.K_F8)
	assert robot.cima.titulo == "Saltar a un lugar"
	lugares = [o for o in robot.opciones() if o != "Volver"]
	assert len(lugares) == 6
	destino = partida.entorno.plantas[0].espacios[3]
	marca = robot.marca()
	robot.elegir(destino.nombre, 3)
	assert isinstance(robot.cima, PantallaJuego)
	assert robot.sesion.mundo.espacio_en(robot.jugador.planta, robot.jugador.x, robot.jugador.y) is destino
	assert hasta(robot, lambda: destino.nombre in robot.dicho(marca)), "el motor anuncia el lugar al llegar"

	# El menú de pausa del recorrido también lleva a la edición.
	robot.tecla(pygame.K_ESCAPE)
	assert {"Menú de edición", "Saltar a un lugar", "Modo fantasma: desactivado", "Salir del recorrido"} <= set(robot.opciones())
	robot.elegir("Continuar", 3)

	# El Estudio cambia el entorno y avisa: se recarga y se sigue en el mismo punto.
	donde = (robot.jugador.planta, robot.jugador.x, robot.jugador.y)
	cambiado = cargar_paquete(ruta)
	cambiado.entorno.plantas[0].objetos.append(
		Objeto(id="obj-nuevo", nombre="Caja nueva", tipo="caja", x=donde[1] + 3.0, y=donde[2], ancho=0.4, fondo=0.4)
	)
	guardar_paquete(ruta, cambiado.entorno)
	assert robot.sesion.mundo.objeto("obj-nuevo") is None
	robot.tecla(pygame.K_F4)
	robot.elegir("Poner aquí el inicio")
	vistos: list[dict] = []
	pedida = _peticion(robot, sala, vistos, "colocar_aqui")
	assert sala.responder("Profe", pedida["id"], True, "Hecho", recargar=True)
	assert hasta(robot, lambda: robot.sesion.mundo.objeto("obj-nuevo") is not None), "el entorno se ha vuelto a leer del disco"
	assert (robot.jugador.planta, robot.jugador.x, robot.jugador.y) == donde
	assert "Entorno actualizado." in robot.dicho()
	# «reiniciar» en el recorrido también recarga.
	assert sala.pedir("Profe", "reiniciar")
	sesion = robot.sesion
	assert hasta(robot, lambda: robot.sesion is not sesion)
	# Salir del recorrido cierra el reproductor.
	robot.tecla(pygame.K_ESCAPE)
	robot.elegir("Salir del recorrido")
	robot.elegir("Sí, salir", 3)
	assert not robot.app.activa
	assert robot.app.fallos == 0
