"""Pruebas del mando y de ``Entrada`` con eventos simulados y un mando falso (sin mando real)."""

from __future__ import annotations

import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402
import pytest  # noqa: E402

from app.entrada import acciones  # noqa: E402
from app.entrada import mando as md  # noqa: E402
from app.entrada.entrada import Entrada  # noqa: E402
from app.entrada.teclado import MapaTeclado  # noqa: E402


class MandoFalso:
	"""Lo mínimo que ``Mandos`` usa de un mando: nombre y vibración."""

	def __init__(self, nombre: str = "Xbox Series X Controller") -> None:
		self.name = nombre
		self.vibraciones: list[tuple[float, float, int]] = []
		self.cerrado = False

	def rumble(self, grave: float, agudo: float, ms: int) -> bool:
		self.vibraciones.append((grave, agudo, ms))
		return True

	def stop_rumble(self) -> None:
		self.vibraciones.append((0.0, 0.0, 0))

	def quit(self) -> None:
		self.cerrado = True


def _boton(nombre: str, abajo: bool = True, mando: int = 7) -> pygame.event.Event:
	tipo = pygame.CONTROLLERBUTTONDOWN if abajo else pygame.CONTROLLERBUTTONUP
	return pygame.event.Event(tipo, button=md.SDL_DE_BOTON[nombre], instance_id=mando)


def _eje(nombre: str, valor: float, mando: int = 7) -> pygame.event.Event:
	return pygame.event.Event(pygame.CONTROLLERAXISMOTION, axis=md.SDL_DE_EJE[nombre], value=int(valor * 32767), instance_id=mando)


@pytest.fixture
def mandos() -> md.Mandos:
	m = md.Mandos(iniciar=False)
	m.conectar(MandoFalso(), 7)
	m.tomar_avisos()
	return m


def test_familias_y_nombres_de_boton():
	assert md.familia_de("Xbox Series X Controller") == md.XBOX
	# El mando de Xbox por Bluetooth se llama así, y «wireless controller» es también la pista del DualShock 4.
	assert md.familia_de("Xbox Wireless Controller") == md.XBOX
	assert md.familia_de("Controller (XBOX 360 For Windows)") == md.XBOX
	assert md.familia_de("PS5 Controller") == md.PS
	assert md.familia_de("DualSense Wireless Controller") == md.PS
	assert md.familia_de("Wireless Controller") == md.PS
	assert md.familia_de("Logitech F310") == md.XBOX
	assert md.nombre_boton("a", md.XBOX) == "A" and md.nombre_boton("a", md.PS) == "Equis"
	assert md.nombre_boton("b", md.PS) == "Círculo"
	assert md.nombre_boton("x", md.PS) == "Cuadrado" and md.nombre_boton("y", md.PS) == "Triángulo"
	assert md.nombre_boton("lb", md.PS) == "L1" and md.nombre_boton("rt", md.PS) == "R2"
	assert md.frase_boton("rt", md.XBOX) == "el gatillo derecho"
	assert md.frase_boton("menu", md.PS) == "el botón Options"
	for familia in md.FAMILIAS:
		for boton in (*md.ORDEN_BOTONES, "guia"):
			assert boton in md.NOMBRES[familia] and boton in md.FRASES[familia]


def test_mapa_de_serie_valido():
	for capa, mapa in md.POR_DEFECTO.items():
		contexto = acciones.MENU if capa == md.CAPA_MENU else acciones.JUEGO
		for boton, accion in mapa.items():
			assert boton in md.ORDEN_BOTONES
			assert acciones.vale_en(accion, contexto), (capa, boton, accion)
	# Entre las dos capas y las palancas, todo lo del juego se puede hacer con el mando.
	con_boton = set(md.POR_DEFECTO[md.CAPA_JUEGO].values()) | set(md.POR_DEFECTO[md.CAPA_JUEGO_2].values())
	de_palanca = {"avanzar", "retroceder", "mirar_izquierda", "mirar_derecha", "mirar_detras"}
	assert {a.id for a in acciones.acciones_de(acciones.JUEGO)} <= con_boton | de_palanca
	assert {a.id for a in acciones.acciones_de(acciones.MENU)} - {"callar"} <= set(md.POR_DEFECTO[md.CAPA_MENU].values())


def test_botones_del_informe(mandos):
	assert mandos.evento(_boton("a")) == [("interactuar", True)]
	assert mandos.evento(_boton("a", False)) == [("interactuar", False)]
	assert mandos.evento(_boton("x")) == [("donde_estoy", True)]
	assert mandos.evento(_boton("y")) == [("mirar_delante", True)]
	assert mandos.evento(_boton("lb")) == [("girar_izquierda", True)]
	assert mandos.evento(_boton("rb")) == [("girar_derecha", True)]
	assert mandos.evento(_boton("menu")) == [("pausa", True)]
	assert mandos.evento(_boton("vista")) == [("ayuda", True)]
	assert mandos.evento(_boton("abajo")) == [("cercano_siguiente", True)]
	assert mandos.evento(_boton("arriba")) == [("cercano_anterior", True)]
	assert mandos.evento(_boton("b"), acciones.MENU) == [("menu_atras", True)]
	assert mandos.evento(_boton("a", mando=99)) == []  # un mando que no está abierto
	assert mandos.evento(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_a, mod=0)) == []


def test_gatillo_derecho_con_histeresis(mandos):
	assert mandos.evento(_eje("rt", 0.2)) == []
	assert mandos.evento(_eje("rt", 0.35)) == [("sonda", True)]
	assert mandos.evento(_eje("rt", 0.9)) == []
	assert mandos.evento(_eje("rt", 0.2)) == []  # entre los dos umbrales sigue pulsado
	assert mandos.evento(_eje("rt", 0.1)) == [("sonda", False)]
	assert mandos.evento(_eje("rt", 0.2)) == []


def test_gatillo_izquierdo_da_la_segunda_funcion(mandos):
	assert mandos.evento(_eje("lt", 1.0)) == []
	assert mandos.modificador_pulsado
	assert mandos.evento(_boton("a")) == [("pista", True)]
	assert mandos.evento(_boton("rb")) == [("paso_derecha", True)]
	# Se suelta el gatillo antes que el botón: se suelta la acción que se pulsó.
	assert mandos.evento(_eje("lt", 0.0)) == []
	assert not mandos.modificador_pulsado
	assert mandos.evento(_boton("rb", False)) == [("paso_derecha", False)]
	assert mandos.evento(_boton("a", False)) == [("pista", False)]
	assert mandos.evento(_boton("a")) == [("interactuar", True)]


def test_ejes_normalizados_y_zona_muerta(mandos):
	assert md.normalizar_eje(32767) == 1.0 and md.normalizar_eje(-32768) == -1.0 and md.normalizar_eje(0) == 0.0
	assert md.normalizar_eje(16383.5) == pytest.approx(0.5)
	assert md.zona_muerta(0.2, 0.0, 0.25) == (0.0, 0.0)
	x, y = md.zona_muerta(1.0, 0.0, 0.25)
	assert x == pytest.approx(1.0) and y == 0.0
	x, _y = md.zona_muerta(0.625, 0.0, 0.25)
	assert x == pytest.approx(0.5)
	assert mandos.ejes() == (0.0, 0.0, 0.0, None)
	mandos.evento(_eje("ly", -1.0))  # hacia delante: SDL lo da negativo
	mandos.evento(_eje("lx", 0.1))
	avance, lateral, giro, mirada = mandos.ejes()
	assert avance == pytest.approx(1.0, abs=0.01) and lateral == 0.0 and abs(giro) < 0.15 and mirada is None
	mandos.evento(_eje("ly", 0.0))
	mandos.evento(_eje("lx", -1.0))
	assert mandos.ejes()[2] == pytest.approx(-1.0, abs=0.01)
	mandos.evento(_eje("lt", 1.0))  # con el modificador, a los lados es paso lateral
	_avance, lateral, giro, _mirada = mandos.ejes()
	assert lateral == pytest.approx(-1.0, abs=0.01) and giro == 0.0
	assert mandos.ejes(acciones.MENU) == (0.0, 0.0, 0.0, None)


def test_zona_muerta_ajustable():
	m = md.Mandos(opciones={"zona_muerta": 0.6, "palanca_izquierda": "lateral", "palanca_derecha": "analogica"}, iniciar=False)
	m.conectar(MandoFalso(), 7)
	m.evento(_eje("lx", 0.5))
	assert m.ejes() == (0.0, 0.0, 0.0, None)
	m.evento(_eje("lx", 0.8))
	_avance, lateral, giro, _mirada = m.ejes()
	assert lateral == pytest.approx(0.5, abs=0.01) and giro == 0.0
	m.evento(_eje("rx", 1.0))
	mirada = m.ejes()[3]
	assert mirada is not None and mirada[0] == pytest.approx(1.0, abs=0.01) and mirada[1] == 0.0
	assert m.actualizar(0.016) == []  # en analógico no se emiten acciones mirar_*
	m.opciones["palanca_derecha"] = "giro"
	assert m.ejes()[2] == pytest.approx(1.0, abs=0.01) and m.ejes()[3] is None


def test_palanca_derecha_mira_por_sectores(mandos):
	assert mandos.actualizar(0.016) == []
	mandos.evento(_eje("rx", 1.0))
	assert mandos.actualizar(0.016) == [("mirar_derecha", True), ("mirar_derecha", False)]
	assert mandos.actualizar(0.016) == []  # mantenida: no se repite
	mandos.evento(_eje("rx", 0.0))
	mandos.evento(_eje("ry", 1.0))  # hacia el usuario: detrás
	assert mandos.actualizar(0.016) == [("mirar_detras", True), ("mirar_detras", False)]
	mandos.evento(_eje("ry", 0.0))
	assert mandos.actualizar(0.016) == []
	mandos.evento(_eje("ry", -1.0))
	assert mandos.actualizar(0.016)[0] == ("mirar_delante", True)
	mandos.evento(_eje("ry", 0.0))
	mandos.actualizar(0.016)
	mandos.evento(_eje("rx", -1.0))
	assert mandos.actualizar(0.016)[0] == ("mirar_izquierda", True)
	assert mandos.ejes()[3] is None  # la mirada no va además como analógica


def test_palanca_izquierda_en_menu_con_repeticion(mandos):
	mandos.evento(_eje("ly", 1.0), acciones.MENU)
	assert mandos.actualizar(0.016, acciones.MENU) == [("menu_abajo", True), ("menu_abajo", False)]
	assert mandos.actualizar(0.2, acciones.MENU) == []
	assert mandos.actualizar(0.3, acciones.MENU) == [("menu_abajo", True), ("menu_abajo", False)]
	assert mandos.actualizar(0.31, acciones.MENU) == [("menu_abajo", True), ("menu_abajo", False)]
	mandos.evento(_eje("ly", 0.0), acciones.MENU)
	assert mandos.actualizar(0.016, acciones.MENU) == []
	mandos.evento(_eje("lx", -1.0), acciones.MENU)
	assert mandos.actualizar(0.016, acciones.MENU)[0] == ("menu_izquierda", True)


def test_vibrar_fuerza_y_desactivar():
	falso = MandoFalso()
	m = md.Mandos(opciones={"fuerza_vibracion": 0.5}, iniciar=False)
	assert m.vibrar(1.0, 1.0, 100) is False  # sin mando
	m.conectar(falso, 1)
	assert m.vibrar(1.0, 0.4, 120) is True
	assert falso.vibraciones == [(0.5, 0.2, 120)]
	assert m.vibrar(5.0, -1.0, 50) is True  # se recorta a 0..1
	assert falso.vibraciones[-1] == (1.0, 0.0, 50)
	assert m.vibrar(1.0, 1.0, 0) is False
	m.opciones["vibracion"] = False
	assert m.vibrar(1.0, 1.0, 100) is False
	assert len(falso.vibraciones) == 2
	m.parar_vibracion()
	assert falso.vibraciones[-1] == (0.0, 0.0, 0)


def test_conexion_y_desconexion_en_caliente():
	m = md.Mandos(iniciar=False)
	assert not m.conectado and m.familia == md.XBOX
	falso = MandoFalso("DualSense Wireless Controller")
	m.conectar(falso, 3)
	assert m.conectado and m.familia == md.PS and m.conectados == ["DualSense Wireless Controller"]
	assert m.tomar_avisos() == ["Mando conectado: DualSense Wireless Controller."]
	assert m.tomar_avisos() == []
	assert m.frase_de("interactuar") == "el botón Equis"
	assert m.frase_de("pista") == "el botón L2 más el botón Equis"
	assert m.frase_de("menu_aceptar", acciones.MENU) == "el botón Equis"
	assert m.frase_de("avanzar") == ""
	m.evento(_boton("lb", mando=3))
	sueltas = m.evento(pygame.event.Event(pygame.CONTROLLERDEVICEREMOVED, instance_id=3))
	assert sueltas == [("girar_izquierda", False)]
	assert not m.conectado and falso.cerrado
	assert "desconectado" in m.tomar_avisos()[0]
	# Un mando añadido sin SDL iniciado no rompe nada.
	assert m.evento(pygame.event.Event(pygame.CONTROLLERDEVICEADDED, device_index=0)) == []


def test_dos_mandos_la_familia_es_la_del_ultimo_usado():
	m = md.Mandos(iniciar=False)
	m.conectar(MandoFalso("Xbox One Controller"), 1)
	m.conectar(MandoFalso("PS4 Controller"), 2)
	assert m.familia == md.PS
	m.evento(_boton("a", mando=1))
	assert m.familia == md.XBOX
	m.evento(_eje("ly", -1.0, mando=2))
	assert m.familia == md.PS and m.ejes()[0] == pytest.approx(1.0, abs=0.01)
	m.cerrar()
	assert not m.conectado


def test_reasignar_botones_por_intercambio():
	mapa = md.MapaMando()
	cambio = mapa.cambiar(md.CAPA_JUEGO, "y", "donde_estoy")
	assert cambio.hecho and cambio.desplazada == "mirar_delante"
	assert mapa.accion_de(md.CAPA_JUEGO, "y") == "donde_estoy"
	assert mapa.accion_de(md.CAPA_JUEGO, "x") == "mirar_delante"
	assert not mapa.cambiar(md.CAPA_JUEGO, "menu", "eco").hecho
	assert not mapa.cambiar(md.CAPA_JUEGO, "lt", "eco").hecho  # es el modificador
	assert not mapa.cambiar(md.CAPA_MENU, "a", "repetir").hecho
	assert not mapa.cambiar(md.CAPA_JUEGO, "a", "menu_aceptar").hecho
	assert not mapa.cambiar(md.CAPA_JUEGO, "zz", "eco").hecho
	assert mapa.cambiar(md.CAPA_JUEGO, "r3", acciones.NADA).hecho
	assert mapa.accion_de(md.CAPA_JUEGO, "r3") is None
	assert len(mapa.cambios()) == 3
	assert ("r3", acciones.NADA) in mapa.reasignables(md.CAPA_JUEGO)
	copia = md.MapaMando.de_dict(json.loads(json.dumps(mapa.a_dict())))
	assert copia.a_dict() == mapa.a_dict()
	assert copia.accion_de(md.CAPA_JUEGO, "r3") is None
	mapa.restablecer()
	assert mapa.cambios() == []
	assert {c: m for c, m in mapa.a_dict().items() if c != "modificador"} == md.POR_DEFECTO


def test_mapa_de_mando_tolerante_y_cambio_de_modificador():
	raro = md.MapaMando.de_dict({"juego": {"a": "volar", "zz": "eco", "x": "eco", "menu": "eco"}, "menu": 5, "modificador": "nada"})
	assert raro.accion_de(md.CAPA_JUEGO, "a") == "interactuar"
	assert raro.accion_de(md.CAPA_JUEGO, "x") == "eco"
	assert raro.accion_de(md.CAPA_JUEGO, "menu") == "pausa"
	assert raro.accion_de(md.CAPA_JUEGO, "y") == "mirar_delante"  # lo que falta, de serie
	assert raro.modificador == "lt"
	assert md.MapaMando.de_dict(None).a_dict() == md.MapaMando().a_dict()

	m = md.Mandos(iniciar=False)
	m.conectar(MandoFalso(), 7)
	assert m.mapa.cambiar_modificador("l3").hecho
	assert not m.mapa.cambiar_modificador("menu").hecho
	assert m.evento(_boton("l3")) == []
	assert m.evento(_boton("a")) == [("pista", True)]
	assert m.evento(_eje("lt", 1.0)) == []  # el gatillo izquierdo ya no hace nada
	assert md.MapaMando.de_dict(m.a_dict()).modificador == "l3"
	assert any("segunda función" in f for f in m.mapa.cambios())


def test_opciones_saneadas():
	opciones = md.sanear_opciones(
		{"zona_muerta": 7, "gatillo_pulsar": 0.2, "gatillo_soltar": 0.9, "palanca_derecha": "raro", "otra": 1, "repeticion": "x"}
	)
	assert opciones["zona_muerta"] == 0.95
	assert opciones["gatillo_soltar"] < opciones["gatillo_pulsar"]
	assert opciones["palanca_derecha"] == "mirar"
	assert "otra" not in opciones and opciones["repeticion"] == md.OPCIONES_POR_DEFECTO["repeticion"]
	assert md.sanear_opciones(None) == md.OPCIONES_POR_DEFECTO


def test_textos_con_botones():
	teclas, botones = MapaTeclado(), md.MapaMando()
	frase = "Pulsa C para saber dónde estás, y B para el bastón. Con la tecla Tabulador recorres lo cercano."
	xbox = md.textos_mando(frase, teclas, botones, md.XBOX)
	assert xbox == "Pulsa el botón X para saber dónde estás, y el gatillo derecho para el bastón. Con la cruceta abajo recorres lo cercano."
	ps = md.textos_mando(frase, teclas, botones, md.PS)
	assert "el botón Cuadrado" in ps and "el botón R2" in ps
	assert (
		md.textos_mando("Pulsa P para pedir una pista.", teclas, botones)
		== "Pulsa el gatillo izquierdo más el botón A para pedir una pista."
	)
	assert md.textos_mando("La tecla K dice el rumbo.", teclas, botones) == "La cruceta izquierda dice el rumbo."
	assert md.textos_mando("Usa las flechas para moverte.", teclas, botones) == "Usa la palanca izquierda para moverte."
	assert md.textos_mando("Pulsa la flecha arriba para andar.", teclas, botones) == "Pulsa la palanca izquierda hacia delante para andar."
	assert md.textos_mando("Pulsa Mayúsculas Tabulador.", teclas, botones) == "Pulsa la cruceta arriba."
	assert md.textos_mando("Pulsa Intro para aceptar.", teclas, botones, md.PS, acciones.MENU) == "Pulsa el botón Equis para aceptar."
	assert md.textos_mando("Pulsa Control para callar la voz.", teclas, botones) == "Pulsa el botón B para callar la voz."
	# Lo que no nombra una tecla se deja igual.
	for intacta in ("Camina con cuidado.", "Hay una mesa con espacio de sobra.", "Con a de casa.", "Pulsa Z para nada.", ""):
		assert md.textos_mando(intacta, teclas, botones) == intacta
	# Tras reasignar, la frase sigue al mapa.
	botones.cambiar(md.CAPA_JUEGO, "y", "donde_estoy")
	assert md.textos_mando("Pulsa C.", teclas, botones) == "Pulsa el botón Y."


def test_entrada_une_teclado_y_mando():
	entrada = Entrada(iniciar_mandos=False)
	assert entrada.traducir(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_UP, mod=0)) == [("avanzar", True)]
	assert entrada.ejes() == (0.0, 0.0, 0.0, None)
	assert entrada.control_de("donde_estoy") == "C"
	assert entrada.textos("Pulsa C.") == "Pulsa C."
	assert entrada.vibrar(1.0, 1.0, 50) is False
	# Al cambiar de contexto se suelta lo pulsado antes de traducir lo nuevo.
	abajo = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_DOWN, mod=0)
	assert entrada.traducir(abajo, acciones.MENU) == [("avanzar", False), ("menu_abajo", True)]
	assert entrada.actualizar(0.016, acciones.JUEGO) == [("menu_abajo", False)]

	falso = MandoFalso("PS4 Controller")
	entrada.mandos.conectar(falso, 7)
	assert entrada.avisos() == ["Mando conectado: PS4 Controller."]
	assert entrada.traducir(_boton("x")) == [("donde_estoy", True)]
	assert entrada.control_de("donde_estoy") == "el botón Cuadrado"
	assert entrada.control_de("avanzar") == "flecha arriba"  # sin botón: se dice la tecla
	assert entrada.textos("Pulsa C.") == "Pulsa el botón Cuadrado."
	assert entrada.vibrar(0.5, 0.5, 80) is True and falso.vibraciones == [(0.5, 0.5, 80)]
	entrada.traducir(_eje("ly", -1.0))
	assert entrada.ejes()[0] == pytest.approx(1.0, abs=0.01)
	assert entrada.traducir(pygame.event.Event(pygame.WINDOWFOCUSLOST)) == [("donde_estoy", False)]
	assert any("Cuadrado" in f for f in entrada.ayuda())
	assert any("Equis" in f for f in entrada.ayuda(acciones.MENU))
	entrada.mandos.opciones["decir_botones"] = False
	assert entrada.control_de("donde_estoy") == "C"


def test_entrada_guarda_y_carga_dicts():
	entrada = Entrada(iniciar_mandos=False, opciones={"zona_muerta": 0.4})
	entrada.teclado.mapa.cambiar(acciones.JUEGO, "donde_estoy", "p")
	entrada.mandos.mapa.cambiar(md.CAPA_JUEGO, "y", "donde_estoy")
	datos = entrada.a_dict()
	assert set(datos) == {"teclado", "mando", "opciones"} and datos["opciones"]["zona_muerta"] == 0.4
	otra = Entrada(iniciar_mandos=False)
	otra.cargar(json.loads(json.dumps(datos)))
	assert otra.a_dict() == datos
	otra.cargar(None)
	assert otra.a_dict() == Entrada(iniciar_mandos=False).a_dict()
	nueva = Entrada(datos["teclado"], datos["mando"], datos["opciones"], iniciar_mandos=False)
	assert nueva.a_dict() == datos
	nueva.cerrar()


def test_iniciar_sdl_sin_mandos_no_falla():
	entrada = Entrada()  # con SDL de verdad: no debe lanzar aunque no haya ningún mando enchufado
	assert isinstance(entrada.mandos.conectado, bool)
	entrada.cerrar()
