"""Pruebas del teclado: mapa de serie, traducción de eventos, reasignación y captura."""

from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame  # noqa: E402

from app.entrada import acciones  # noqa: E402
from app.entrada import teclado as tec  # noqa: E402


def _tecla(codigo: int, abajo: bool = True, mod: int = 0) -> pygame.event.Event:
	return pygame.event.Event(pygame.KEYDOWN if abajo else pygame.KEYUP, key=codigo, mod=mod)


def test_todas_las_acciones_del_documento_existen():
	esperadas = (
		"avanzar retroceder girar_izquierda girar_derecha paso_izquierda paso_derecha media_vuelta "
		"interactuar donde_estoy mirar_delante mirar_izquierda mirar_detras mirar_derecha alrededor "
		"cercano_siguiente cercano_anterior descubiertos brujula sonda eco objetivo pista confirmar "
		"repetir historial_anterior historial_siguiente callar volver_inicio ayuda pausa "
		"menu_arriba menu_abajo menu_izquierda menu_derecha menu_aceptar menu_atras"
	).split()
	assert list(acciones.ACCIONES) == esperadas
	for accion in acciones.ACCIONES.values():
		assert accion.nombre and accion.ayuda and accion.contextos
	assert acciones.nombre_accion("donde_estoy") == "Dónde estoy"
	assert acciones.nombre_accion("nada") == "Sin asignar"
	assert acciones.es_mantenida("avanzar") and not acciones.es_mantenida("donde_estoy")
	assert acciones.vale_en("repetir", acciones.MENU) and not acciones.vale_en("avanzar", acciones.MENU)


def test_mapa_de_serie_cubre_todas_las_acciones():
	mapa = tec.MapaTeclado()
	for contexto in acciones.CONTEXTOS:
		for accion in acciones.acciones_de(contexto):
			assert mapa.combinaciones_de(contexto, accion.id), f"{accion.id} sin tecla en {contexto}"
	for contexto, serie in tec.POR_DEFECTO.items():
		for comb, accion in serie.items():
			assert tec.normalizar(comb) == comb
			assert acciones.vale_en(accion, contexto)


def test_mapa_del_informe():
	t = tec.Teclado()
	assert t.traducir(_tecla(pygame.K_UP)) == [("avanzar", True)]
	assert t.traducir(_tecla(pygame.K_UP, False)) == [("avanzar", False)]
	assert t.traducir(_tecla(pygame.K_LEFT, mod=pygame.KMOD_LSHIFT)) == [("paso_izquierda", True)]
	assert t.traducir(_tecla(pygame.K_RETURN)) == [("interactuar", True)]
	assert t.traducir(_tecla(pygame.K_SPACE)) == [("interactuar", True)]
	assert t.traducir(_tecla(pygame.K_c)) == [("donde_estoy", True)]
	assert t.traducir(_tecla(pygame.K_w)) == [("mirar_delante", True)]
	assert t.traducir(_tecla(pygame.K_TAB)) == [("cercano_siguiente", True)]
	assert t.traducir(_tecla(pygame.K_k)) == [("brujula", True)]
	assert t.traducir(_tecla(pygame.K_b)) == [("sonda", True)]
	assert t.traducir(_tecla(pygame.K_F1)) == [("ayuda", True)]
	assert t.traducir(_tecla(pygame.K_F2)) == [("repetir", True)]
	assert t.traducir(_tecla(pygame.K_F3)) == [("historial_anterior", True)]
	assert t.traducir(_tecla(pygame.K_LCTRL, mod=pygame.KMOD_LCTRL)) == [("callar", True)]
	assert t.traducir(_tecla(pygame.K_ESCAPE)) == [("pausa", True)]
	assert t.traducir(_tecla(pygame.K_ESCAPE), acciones.MENU) == [("pausa", False), ("menu_atras", True)]
	assert t.traducir(_tecla(pygame.K_DOWN), acciones.MENU) == [("menu_abajo", True)]
	assert t.traducir(pygame.event.Event(pygame.MOUSEMOTION)) == []


def test_soltar_devuelve_la_accion_que_se_pulso():
	t = tec.Teclado()
	# Se pulsa con Mayúsculas y se suelta sin ella: se suelta el paso lateral, no el giro.
	t.traducir(_tecla(pygame.K_RIGHT, mod=pygame.KMOD_SHIFT))
	assert t.traducir(_tecla(pygame.K_RIGHT, False)) == [("paso_derecha", False)]
	assert t.traducir(_tecla(pygame.K_RIGHT, False)) == []


def test_modificador_sin_combinacion_cae_en_la_tecla_sola_y_alt_se_ignora():
	t = tec.Teclado()
	assert t.traducir(_tecla(pygame.K_UP, mod=pygame.KMOD_LSHIFT)) == [("avanzar", True)]
	assert t.traducir(_tecla(pygame.K_F4, mod=pygame.KMOD_LALT)) == []
	assert t.traducir(_tecla(pygame.K_c, mod=pygame.KMOD_LALT)) == []
	assert t.soltar_todo() == [("avanzar", False)]
	assert t.soltar_todo() == []


def test_reasignar_intercambia():
	mapa = tec.MapaTeclado()
	cambio = mapa.cambiar(acciones.JUEGO, "donde_estoy", "p")
	assert cambio.hecho and cambio.desplazada == "pista"
	assert mapa.accion_de(acciones.JUEGO, "p") == "donde_estoy"
	assert mapa.accion_de(acciones.JUEGO, "c") == "pista"
	assert "Dónde estoy" in cambio.frase and "Pista pasa a C" in cambio.frase
	assert len(mapa.cambios()) == 2
	# A una tecla libre: se mueve sin desplazar a nadie y la vieja queda libre.
	cambio = mapa.cambiar(acciones.JUEGO, "brujula", "n")
	assert cambio.hecho and cambio.desplazada is None
	assert mapa.accion_de(acciones.JUEGO, "k") is None
	# A la tecla que ya tiene: no cambia nada.
	antes = mapa.a_dict()
	assert mapa.cambiar(acciones.JUEGO, "brujula", "n").hecho
	assert mapa.a_dict() == antes
	mapa.restablecer()
	assert mapa.a_dict() == tec.POR_DEFECTO and mapa.cambios() == []


def test_teclas_fijas_no_se_tocan():
	mapa = tec.MapaTeclado()
	assert not mapa.cambiar(acciones.JUEGO, "donde_estoy", "escape").hecho
	assert not mapa.cambiar(acciones.JUEGO, "donde_estoy", "f1").hecho
	assert not mapa.cambiar(acciones.JUEGO, "pausa", "p").hecho
	assert not mapa.cambiar(acciones.JUEGO, "menu_aceptar", "p").hecho
	assert not mapa.cambiar(acciones.JUEGO, "donde_estoy", "no_existe").hecho
	assert not mapa.cambiar(acciones.JUEGO, "donde_estoy", "p", vieja="k").hecho
	assert mapa.a_dict() == tec.POR_DEFECTO
	# Interactuar tiene Intro (fija) y Espacio: se cambia el Espacio.
	assert mapa.cambiar(acciones.JUEGO, "interactuar", "x").hecho
	assert mapa.combinaciones_de(acciones.JUEGO, "interactuar") == ["intro", "intro_numerico", "x"]
	assert all(not tec.es_fija(c) for _a, c in mapa.reasignables(acciones.JUEGO))


def test_cargar_y_guardar_tolerante():
	mapa = tec.MapaTeclado()
	mapa.cambiar(acciones.JUEGO, "donde_estoy", "p")
	copia = tec.MapaTeclado.de_dict(mapa.a_dict())
	assert copia.a_dict() == mapa.a_dict()
	raro = tec.MapaTeclado.de_dict(
		{
			"juego": {"Mayus + Z": "eco", "escape": "eco", "zz": "eco", "j": "volar", "x": "menu_arriba"},
			"menu": "roto",
			"otro": {},
		}
	)
	assert raro.accion_de(acciones.JUEGO, "mayus+z") == "eco"
	assert raro.accion_de(acciones.JUEGO, "escape") == "pausa"
	assert raro.accion_de(acciones.JUEGO, "j") is None and raro.accion_de(acciones.JUEGO, "x") is None
	assert raro.accion_de(acciones.JUEGO, "e") is None  # eco ya tiene tecla: no se duplica
	assert raro.accion_de(acciones.JUEGO, "arriba") == "avanzar"  # lo que faltaba, de serie
	assert raro.a_dict()["menu"] == tec.POR_DEFECTO["menu"]
	assert tec.MapaTeclado.de_dict(None).a_dict() == tec.POR_DEFECTO
	assert tec.MapaTeclado.de_dict({"juego": 3}).a_dict() == tec.POR_DEFECTO


def test_nombres_hablados():
	assert tec.nombre_combinacion("mayus+tabulador") == "Mayúsculas Tabulador"
	assert tec.nombre_combinacion("arriba") == "flecha arriba"
	assert tec.nombre_combinacion("c") == "C"
	assert tec.nombre_combinacion("f2") == "F2"
	assert tec.nombre_combinacion("ctrl+repag") == "Control Retroceder página"
	assert tec.id_tecla(pygame.K_KP5) == "numerico_5"
	for codigo in (pygame.K_a, pygame.K_9, pygame.K_F12, pygame.K_KP0, pygame.K_HOME, pygame.K_LCTRL, 1234567):
		assert tec.codigo_tecla(tec.id_tecla(codigo)) == codigo
	assert tec.MapaTeclado().nombre_de(acciones.JUEGO, "sonda") == "B"
	assert tec.combinacion(pygame.K_LCTRL, pygame.KMOD_LCTRL) == "control_izquierdo"
	assert tec.combinacion(pygame.K_g, pygame.KMOD_LCTRL | pygame.KMOD_RSHIFT) == "mayus+ctrl+g"


def test_captura_asigna_cancela_y_rechaza():
	mapa = tec.MapaTeclado()
	captura = tec.CapturaTecla(mapa, acciones.JUEGO, "sonda")
	assert "Bastón sonoro" in captura.al_entrar()
	assert captura.evento(_tecla(pygame.K_LSHIFT, mod=pygame.KMOD_LSHIFT)) is None
	rechazo = captura.evento(_tecla(pygame.K_F1))
	assert rechazo.estado == tec.RECHAZADA and not captura.terminada
	hecho = captura.evento(_tecla(pygame.K_g, mod=pygame.KMOD_LSHIFT))
	assert hecho.estado == tec.ASIGNADA and hecho.combinacion == "mayus+g" and captura.terminada
	assert mapa.accion_de(acciones.JUEGO, "mayus+g") == "sonda"
	assert captura.evento(_tecla(pygame.K_h)) is None  # ya terminada

	cancelada = tec.CapturaTecla(mapa, acciones.JUEGO, "eco")
	assert cancelada.evento(_tecla(pygame.K_ESCAPE)).estado == tec.CANCELADA
	assert mapa.accion_de(acciones.JUEGO, "e") == "eco"


def test_captura_de_control_solo_y_con_otra_tecla():
	mapa = tec.MapaTeclado()
	captura = tec.CapturaTecla(mapa, acciones.JUEGO, "eco")
	assert captura.evento(_tecla(pygame.K_RCTRL, mod=pygame.KMOD_RCTRL)) is None
	resultado = captura.evento(_tecla(pygame.K_RCTRL, False))
	assert resultado.estado == tec.ASIGNADA and resultado.desplazada == "callar"
	assert mapa.accion_de(acciones.JUEGO, "control_derecho") == "eco"
	assert mapa.accion_de(acciones.JUEGO, "e") == "callar"

	otra = tec.CapturaTecla(mapa, acciones.JUEGO, "pista")
	otra.evento(_tecla(pygame.K_LCTRL, mod=pygame.KMOD_LCTRL))
	resultado = otra.evento(_tecla(pygame.K_j, mod=pygame.KMOD_LCTRL))
	assert resultado.combinacion == "ctrl+j"
	t = tec.Teclado(mapa)
	assert t.traducir(_tecla(pygame.K_j, mod=pygame.KMOD_LCTRL)) == [("pista", True)]
