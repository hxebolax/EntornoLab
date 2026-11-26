"""Pruebas del arranque del reproductor por línea de órdenes: comprobación, paquete inexistente, dañado y válido."""

# ruff: noqa: F811 - los parámetros de las pruebas se llaman como las fixtures importadas
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from app.reproductor import arranque
from app.reproductor.pantallas.juego import PantallaJuego

from .conftest import RAIZ
from .test_reproductor_comun import VIVIENDA, Robot, actividades, crear_app, paquete_con_busqueda, sin_navegador  # noqa: F401 - fixtures


def _ejecutar(guion: str, datos, *argumentos: str) -> subprocess.CompletedProcess:
	return subprocess.run(
		[sys.executable, str(RAIZ / guion), *argumentos],
		capture_output=True,
		text=True,
		encoding="utf-8",
		errors="replace",
		timeout=180,
		env={**os.environ, "APP_DATA_DIR": str(datos)},
		cwd=str(RAIZ),
		check=False,
	)


def _registro(datos) -> str:
	return "".join(ruta.read_text(encoding="utf-8") for ruta in sorted((datos / "logs").glob("jugar_*.log")))


# ── En otro proceso, como lo lanza el usuario o el Estudio ───────────────────


@pytest.mark.lento
@pytest.mark.parametrize(
	("guion", "argumentos"), [("jugar.py", ["--comprobar-arranque"]), ("main.py", ["--jugar", "--comprobar-arranque"])]
)
def test_comprobar_arranque_sale_con_cero_sin_errores(data_temporal, guion, argumentos):
	resultado = _ejecutar(guion, data_temporal, *argumentos)
	assert resultado.returncode == 0, resultado.stderr
	texto = _registro(data_temporal)
	assert "Reproductor 0.1.0 iniciado" in texto or "iniciado: motor de sonido nulo" in texto
	assert "modo oculto" in texto and "Comprobación de arranque correcta." in texto
	assert "Reproductor cerrado (0 fallos de fotograma)." in texto
	assert "Reproductor terminado con el código 0" in texto
	assert "ERROR" not in texto and "CRITICAL" not in texto and "Traceback" not in texto
	assert not (data_temporal / "sessions").exists(), "comprobar el arranque no graba sesiones"
	assert not (data_temporal / "logs" / "arranque_fallido.log").exists()


@pytest.mark.lento
def test_paquete_inexistente_sale_con_dos(data_temporal):
	resultado = _ejecutar("jugar.py", data_temporal, str(data_temporal / "no_existe.elab"), "--comprobar-arranque")
	assert resultado.returncode == 2
	assert "Argumentos del reproductor no válidos: No se encuentra el entorno" in _registro(data_temporal)


@pytest.mark.lento
def test_paquete_danado_sale_con_tres_en_la_comprobacion(data_temporal):
	roto = data_temporal / "roto.elab"
	roto.write_bytes(b"PK\x03\x04 esto no es un paquete")
	resultado = _ejecutar("jugar.py", data_temporal, str(roto), "--comprobar-arranque")
	assert resultado.returncode == 3, resultado.stderr
	texto = _registro(data_temporal)
	assert "el entorno pedido no se puede abrir" in texto and "Reproductor terminado con el código 3" in texto
	assert "Traceback" not in texto and "ERROR" not in texto, "un paquete dañado es un aviso, no un fallo del programa"
	assert not (data_temporal / "logs" / "arranque_fallido.log").exists()


@pytest.mark.lento
def test_paquete_valido_con_alumno_e_inicio(data_temporal):
	resultado = _ejecutar(
		"main.py", data_temporal, "--jugar", str(VIVIENDA), "--alumno", "Ana García", "--inicio", "pla-1,2,4.6,0", "--comprobar-arranque"
	)
	assert resultado.returncode == 0, resultado.stderr
	texto = _registro(data_temporal)
	assert "entorno vivienda-de-ejemplo.elab" in texto and "ERROR" not in texto
	assert "Ana García" not in texto and "ana_garcia" not in texto, "el alias no va al registro"
	assert (data_temporal / "config" / "alumnos" / "ana_garcia.json").is_file()


# ── En el mismo proceso ──────────────────────────────────────────────────────


def test_ejecutar_con_paquete_danado_devuelve_tres_y_no_lanza(data_temporal, caplog):
	roto = data_temporal / "mi casa.elab"
	roto.write_bytes(b"PK")
	assert arranque.ejecutar([str(roto), "--comprobar-arranque", "--alumno", "Ana García"]) == arranque.CODIGO_ENTORNO
	assert "Ana García" not in caplog.text
	assert arranque.ejecutar(["--comprobar-arranque"]) == arranque.CODIGO_CORRECTO
	assert arranque.ejecutar([str(data_temporal / "no_esta.elab")]) == arranque.CODIGO_ARGUMENTOS


def test_un_paquete_danado_por_argumento_se_dice_y_deja_el_menu_principal(data_temporal, sin_navegador):
	roto = data_temporal / "roto.elab"
	roto.write_bytes(b"PK")
	aplicacion = crear_app(str(roto), "--alumno", "Luna")
	try:
		robot = Robot(aplicacion)
		assert robot.pantallas() == ["Menu"]
		assert "No se puede abrir el entorno «roto»" in robot.ultimo() and aplicacion.voz.registro[-1][1] == "aviso"
		assert aplicacion.error_inicial and aplicacion.codigo_salida == 3
		robot.accion("menu_abajo")
		assert robot.ultimo().startswith("Elegir entorno"), "el menú sigue funcionando"
	finally:
		aplicacion.cerrar_todo()


def test_paquete_por_argumento_abre_sus_actividades_y_actividad_la_empieza(data_temporal, sin_navegador, actividades):
	ruta = paquete_con_busqueda(data_temporal / "fuera")
	aplicacion = crear_app(str(ruta), "--alumno", "Luna")
	try:
		robot = Robot(aplicacion)
		assert robot.pantallas() == ["Menu", "Menu"] and robot.cima.titulo == "Vivienda de ejemplo"
		assert robot.opciones()[:2] == ["Busca los premios", "Exploración libre"]
		robot.atras()
		robot.elegir("Elegir entorno")
		assert robot.opciones()[0] == "Vivienda de ejemplo", "el entorno recibido por argumento sale el primero de la lista"
	finally:
		aplicacion.cerrar_todo()
	directa = crear_app(str(ruta), "--actividad", "busca", "--alumno", "Luna", "--inicio", "pla-1,2,4.6,0")
	try:
		robot = Robot(directa)
		assert isinstance(robot.cima, PantallaJuego) and robot.partida.id_actividad == "busca"
		assert (robot.jugador.x, robot.jugador.y, robot.jugador.rumbo) == (2.0, 4.6, 0.0), "el inicio pedido manda"
	finally:
		directa.cerrar_todo()
	inexistente = crear_app(str(ruta), "--actividad", "otra", "--alumno", "Luna")
	try:
		robot = Robot(inexistente)
		assert "no tiene la actividad «otra»" in robot.dicho() and robot.cima.titulo == "Vivienda de ejemplo"
	finally:
		inexistente.cerrar_todo()


def test_el_cierre_es_ordenado_y_se_puede_repetir(data_temporal, sin_navegador):
	aplicacion = crear_app("--alumno", "Luna")
	robot = Robot(aplicacion)
	robot.elegir("Salir")
	assert not aplicacion.activa and "Hasta pronto." in robot.ultimo()
	motor = aplicacion.motor
	aplicacion.cerrar_todo()
	aplicacion.cerrar_todo()
	assert motor.de("cerrar") and aplicacion.voz.al_hablar is None
