"""Estudio y reproductor comparten ``config.json``: ninguno pisa al otro y los cambios llegan en caliente.

- Dos ``Configuracion`` sobre el mismo archivo (dos procesos): al guardar, cada
  una conserva lo que guardó la otra; ``recargar`` avisa de lo que cambió.
- El reproductor en marcha aplica lo que cambia el Estudio sin reiniciar: con
  la sala, por la orden ``releer_configuracion``; sin ella, al volver al menú.
  Se comprueba con el PAQUETE DE SONIDO: los datos que tiene cargados el motor
  (en memoria, sin tarjeta de sonido) pasan a ser los del paquete nuevo.
- Las preferencias del alumno se quedan en su perfil: elegir alias no vuelca
  nada suyo en la configuración compartida.
"""

# ruff: noqa: F811 - los parámetros de las pruebas se llaman como las fixtures importadas
from __future__ import annotations

import time
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import numpy as np
import pytest

from app.core.configuracion import Configuracion, ruta_por_defecto
from app.ui.seguimiento.sala import GestorSala
from app.ui.seguimiento.servicio import ServicioSeguimiento

from .test_reproductor_comun import Robot, crear_app, sin_navegador  # noqa: F401 - fixtures

RAPIDO = {"intervalo_estado": 0.05, "intervalo_latido": 0.2, "tiempo_muerto": 1.0, "reintento_min": 0.05, "reintento_max": 0.2}
SONIDO = "pasos/madera_izq_1"


def _otro_paquete(app: Any) -> str:
	"""Un paquete de sonidos instalado distinto del de por defecto, que traiga su propio ``SONIDO``."""
	for paquete in app.banco.paquetes_disponibles():
		if paquete["defecto"]:
			continue
		if app.banco.sonido_de_paquete(paquete["id"], SONIDO).paquete == paquete["id"]:
			return str(paquete["id"])
	pytest.skip("no hay otro paquete de sonidos instalado con sonidos propios")
	return ""


def _datos(app: Any) -> np.ndarray:
	return np.asarray(app.banco.datos(SONIDO)[0])


# ── Dos procesos, un archivo ─────────────────────────────────────────────────


def test_guardar_no_pisa_lo_que_guardo_el_otro_proceso_y_recargar_avisa(tmp_path: Path):
	ruta = tmp_path / "config.json"
	estudio = Configuracion(ruta)
	reproductor = Configuracion(ruta)
	avisos: list[tuple[str, Any, Any]] = []
	reproductor.suscribir(lambda clave, anterior, nuevo: avisos.append((clave, anterior, nuevo)))
	estudio.establecer("voz.velocidad", 70)
	estudio.establecer("sonido.volumen_ambiente", 0.3)
	# El reproductor no se ha enterado y guarda lo suyo: lo del Estudio sigue en el archivo.
	reproductor.establecer("juego.alias", "Luna")
	en_disco = Configuracion(ruta)
	assert (en_disco.obtener("voz.velocidad"), en_disco.obtener("sonido.volumen_ambiente"), en_disco.obtener("juego.alias")) == (
		70,
		0.3,
		"Luna",
	)
	# Y el Estudio, al guardar otra cosa, tampoco pisa el alias del reproductor.
	estudio.establecer("general.tamano_texto", 125)
	en_disco = Configuracion(ruta)
	assert (en_disco.obtener("juego.alias"), en_disco.obtener("general.tamano_texto")) == ("Luna", 125)
	# recargar avisa de lo del otro proceso, también de lo que ya se absorbió al guardar, una vez cada cosa.
	assert avisos == [("juego.alias", "", "Luna")]
	avisos.clear()
	cambiadas = reproductor.recargar()
	assert sorted(cambiadas) == ["general.tamano_texto", "sonido.volumen_ambiente", "voz.velocidad"]
	assert ("voz.velocidad", 50, 70) in avisos and ("sonido.volumen_ambiente", 0.7, 0.3) in avisos
	assert reproductor.recargar() == [], "sin cambios en disco no se avisa de nada"


def test_recargar_conserva_lo_propio_sin_guardar(tmp_path: Path):
	ruta = tmp_path / "config.json"
	uno = Configuracion(ruta)
	otro = Configuracion(ruta)
	uno.establecer_diferido("voz.volumen", 40, retraso=30.0)
	otro.establecer("voz.velocidad", 80)
	uno.recargar()
	assert (uno.obtener("voz.volumen"), uno.obtener("voz.velocidad")) == (40, 80)
	assert Configuracion(ruta).obtener("voz.volumen") == 40, "lo diferido se guarda antes de releer"


# ── El reproductor en marcha ─────────────────────────────────────────────────


def hasta(robot: Robot, servicio: ServicioSeguimiento, condicion: Callable[[], Any], segundos: float = 8.0) -> bool:
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		robot.esperar(1)
		servicio.sala.sondear()
		if condicion():
			return True
		time.sleep(0.01)
	return bool(condicion())


@pytest.fixture
def estudio(tmp_path: Path, data_temporal: Path):
	"""El Estudio con su propia instancia de la configuración compartida y la sala abierta para este ordenador."""
	configuracion = Configuracion(ruta_por_defecto())
	contexto = SimpleNamespace(configuracion=configuracion)
	sala = GestorSala(configuracion, carpeta_config=tmp_path / "estudio")
	servicio = ServicioSeguimiento(contexto, sala=sala)
	sala.abrir(red=False, puerto=0, anunciar=False)
	yield servicio
	servicio.cerrar()


@pytest.mark.lento
def test_el_paquete_de_sonido_cambia_en_caliente_por_la_sala(estudio, data_temporal, sin_navegador):
	app = crear_app("--alumno", "Luna")
	try:
		robot = Robot(app)
		otro = _otro_paquete(app)
		antes = _datos(app)
		app.presentador.sonido(SONIDO)
		cargas = len(app.motor.de("cargar"))
		sala = estudio.sala.sala
		app.opciones_cliente = dict(RAPIDO)
		app.conectar_sala("127.0.0.1", sala.puerto, sala.codigo)
		assert hasta(robot, estudio, lambda: app.enlace.conectado)
		configuraciones_voz: list[dict] = []
		configurar_voz = app.voz.configurar
		app.voz.configurar = lambda opciones: (configuraciones_voz.append(dict(opciones)), configurar_voz(opciones))[1]
		# El profesional cambia en Preferencias del Estudio el paquete, un volumen y la voz.
		estudio.contexto.configuracion.establecer_varias({"sonido.paquete": otro, "sonido.volumen_ambiente": 0.25, "voz.volumen": 60})
		assert app.banco.paquete_actual() == "por_defecto", "sin aviso, el reproductor aún no lo sabe"
		assert estudio.releer_configuracion_en_reproductores() == 1
		assert hasta(robot, estudio, lambda: app.banco.paquete_actual() == otro), "el paquete nuevo no ha llegado"
		despues = _datos(app)
		assert despues.shape != antes.shape or not np.array_equal(despues, antes), "los datos del sonido son los del paquete nuevo"
		robot.esperar(3)
		recargados = [llamada["nombre"] for llamada in app.motor.de("cargar")[cargas:]]
		assert SONIDO in recargados, "el motor vuelve a cargar con el paquete nuevo lo que ya tenía cargado"
		assert app.config.obtener("sonido.volumen_ambiente") == 0.25
		assert any(opciones.get("sapi_volumen") == 60 for opciones in configuraciones_voz), "la voz se reconfigura con el volumen nuevo"
		assert app.fallos == 0
	finally:
		app.cerrar_todo()


def test_sin_sala_el_reproductor_relee_al_volver_al_menu(data_temporal, sin_navegador):
	app = crear_app("--alumno", "Luna")
	try:
		robot = Robot(app)
		otro = _otro_paquete(app)
		antes = _datos(app)
		# Otro proceso (el Estudio) guarda el archivo.
		Configuracion(ruta_por_defecto()).establecer("sonido.paquete", otro)
		robot.esperar(3)
		assert app.banco.paquete_actual() == "por_defecto"
		robot.elegir("Mis premios")
		robot.atras()
		assert app.banco.paquete_actual() == otro, "al volver al menú principal se aplica lo cambiado"
		assert not np.array_equal(_datos(app), antes) or _datos(app).shape != antes.shape
		assert app.fallos == 0
	finally:
		app.cerrar_todo()


def test_el_reproductor_no_vuelca_las_preferencias_del_alumno_en_la_configuracion(data_temporal, sin_navegador):
	compartida = Configuracion(ruta_por_defecto())
	compartida.establecer("juego.paso_m", 0.75)  # lo que el profesional pone de serie para todos
	app = crear_app("--alumno", "Luna")
	try:
		app.establecer("juego.paso_m", 0.5)
		app.establecer("juego.estilo", "juvenil")
		assert app.ajustes_juego().paso_m == 0.5 and app.estilo == "juvenil"
		app.poner_alumno("Sol", anunciar=False)
		assert app.ajustes_juego().paso_m == 0.75 and app.estilo == "adulto", "Sol no hereda las preferencias de Luna"
	finally:
		app.cerrar_todo()
	en_disco = Configuracion(ruta_por_defecto())
	assert en_disco.obtener("juego.paso_m") == 0.75 and en_disco.obtener("juego.estilo") == "adulto"
	assert en_disco.obtener("juego.alias") == "Sol"


def test_preferencias_del_estudio_avisan_a_los_reproductores_conectados(estudio, monkeypatch):
	pytest.importorskip("wx")
	from app.ui import preferencias
	from app.ui.seguimiento import servicio as mod_servicio

	pedidas: list[tuple[str, str]] = []
	estudio.sala.foto = lambda: {
		"alumnos": [{"id": "Luna", "alias": "Luna", "conectado": True}, {"id": "Sol", "alias": "Sol", "conectado": False}]
	}
	monkeypatch.setattr(estudio.sala, "pedir", lambda alumno, orden, **datos: pedidas.append((alumno, orden)) or True)
	contexto = estudio.contexto
	assert preferencias.avisar_reproductores(contexto, ["sonido.paquete"]) == 0, "sin servicio del seguimiento no se crea ninguno"
	mod_servicio.poner_servicio(contexto, estudio)
	try:
		assert preferencias.avisar_reproductores(contexto, ["editor.cuadricula"]) == 0, "lo que no usa el reproductor no se avisa"
		assert preferencias.avisar_reproductores(contexto, ["editor.cuadricula", "voz.velocidad"]) == 1
		assert pedidas == [("Luna", "releer_configuracion")]
	finally:
		mod_servicio._SERVICIOS.pop(id(contexto), None)
