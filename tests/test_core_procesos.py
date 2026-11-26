"""Pruebas de los procesos auxiliares: lanzamiento, Job Object y orden del reproductor.

Los procesos de prueba son inocuos: el propio intérprete con ``-c`` y una
línea de código que duerme o sale con un código.
"""

from __future__ import annotations

import subprocess
import sys
import time

import pytest

from app.core import paths, procesos
from app.core.procesos import ErrorProceso
from app.core.version import EJECUTABLE_REPRODUCTOR

DORMIR = [sys.executable, "-c", "import time; time.sleep(60)"]


def _salir_con(codigo: int) -> list[str]:
	return [sys.executable, "-c", f"raise SystemExit({codigo})"]


def _pid_vivo(pid: int) -> bool:
	"""Pregunta a Windows si el proceso sigue en marcha (sin depender del texto de tasklist)."""
	import ctypes
	from ctypes import wintypes

	kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
	kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
	kernel32.OpenProcess.restype = wintypes.HANDLE
	kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
	kernel32.WaitForSingleObject.restype = wintypes.DWORD
	kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
	sincronizar = 0x00100000
	descriptor = kernel32.OpenProcess(sincronizar, False, pid)
	if not descriptor:
		return False
	try:
		# 0x102 = WAIT_TIMEOUT: el proceso aún no ha terminado.
		return kernel32.WaitForSingleObject(descriptor, 0) == 0x102
	finally:
		kernel32.CloseHandle(descriptor)


@pytest.fixture(autouse=True)
def _sin_procesos_colgados():
	"""Ninguna prueba deja procesos vivos, pase o falle."""
	yield
	procesos.terminar_todos(espera=5.0)


def test_lanzar_esperar_y_codigo_de_salida():
	proceso = procesos.lanzar(_salir_con(7))
	assert proceso.pid > 0
	assert proceso.esperar(30) == 7
	assert proceso.vivo() is False
	assert proceso.codigo == 7
	assert proceso not in procesos.procesos_vivos()
	assert "terminado con 7" in repr(proceso)


def test_vivo_terminar_y_esperar_con_limite():
	proceso = procesos.lanzar(DORMIR)
	assert proceso.vivo() is True
	assert proceso.codigo is None
	assert proceso in procesos.procesos_vivos()
	inicio = time.monotonic()
	assert proceso.esperar(0.2) is None, "si pasa el tiempo y sigue vivo, devuelve None sin matarlo"
	assert time.monotonic() - inicio < 5
	assert proceso.vivo() is True
	assert proceso.terminar(10) is not None
	assert proceso.vivo() is False
	assert proceso.terminar() is not None, "terminar dos veces no falla"
	assert procesos.procesos_vivos() == []
	assert proceso.terminado_por_el_estudio is True, "quien vigila el proceso sabe que no fue un cierre inesperado"


def test_un_proceso_que_termina_solo_no_lo_cerro_el_estudio():
	proceso = procesos.lanzar(_salir_con(0))
	assert proceso.esperar(30) == 0
	assert proceso.terminar() == 0
	assert proceso.terminado_por_el_estudio is False


@pytest.mark.skipif(sys.platform != "win32", reason="Los Job Objects son de Windows")
def test_el_hijo_queda_atado_al_job_object():
	proceso = procesos.lanzar(DORMIR)
	assert proceso.atado is True, "sin Job Object, un Estudio caído dejaría el reproductor huérfano"
	proceso.terminar(10)


@pytest.mark.lento
@pytest.mark.skipif(sys.platform != "win32", reason="Los Job Objects son de Windows")
def test_si_muere_el_padre_windows_mata_al_hijo(tmp_path):
	"""Un padre que muere de golpe (sin atexit) no deja huérfano al hijo."""
	guion = tmp_path / "padre.py"
	guion.write_text(
		"import os, sys\n"
		f"sys.path.insert(0, {str(paths.ruta_base())!r})\n"
		"from app.core import procesos\n"
		"hijo = procesos.lanzar([sys.executable, '-c', 'import time; time.sleep(120)'])\n"
		"print(hijo.pid, hijo.atado, flush=True)\n"
		"os._exit(0)\n",
		encoding="utf-8",
	)
	resultado = subprocess.run([sys.executable, str(guion)], capture_output=True, text=True, timeout=60, check=False)
	assert resultado.returncode == 0, resultado.stderr
	pid, atado = resultado.stdout.split()
	assert atado == "True"
	limite = time.monotonic() + 15
	vivo = True
	while vivo and time.monotonic() < limite:
		vivo = _pid_vivo(int(pid))
		if vivo:
			time.sleep(0.1)
	assert not vivo, "el hijo debe morir con el padre"


def test_terminar_todos():
	primero = procesos.lanzar(DORMIR)
	segundo = procesos.lanzar(DORMIR)
	assert set(procesos.procesos_vivos()) == {primero, segundo}
	procesos.terminar_todos(espera=10)
	assert not primero.vivo() and not segundo.vivo()
	assert procesos.procesos_vivos() == []


def test_ejecutable_inexistente_y_orden_vacia(tmp_path):
	with pytest.raises(ErrorProceso, match="no_existe.exe"):
		procesos.lanzar([str(tmp_path / "no_existe.exe")])
	with pytest.raises(ErrorProceso):
		procesos.lanzar([])


def test_el_hijo_hereda_la_carpeta_data_y_admite_entorno_propio(tmp_path, data_temporal):
	salida = tmp_path / "salida.txt"
	codigo = "import os, sys; open(sys.argv[1], 'w', encoding='utf-8').write(os.environ.get('APP_DATA_DIR', '') + '|' + os.environ.get('EXTRA', '') + '|' + os.getcwd())"
	assert procesos.lanzar([sys.executable, "-c", codigo, str(salida)]).esperar(30) == 0
	datos, extra, carpeta = salida.read_text(encoding="utf-8").split("|")
	assert datos == str(data_temporal), "el reproductor debe usar la misma carpeta data que el Estudio"
	assert extra == ""
	assert carpeta.lower() == str(paths.ruta_base()).lower(), "la carpeta de trabajo es la del programa"
	import os

	propio = {**os.environ, "EXTRA": "valor"}
	assert procesos.lanzar([sys.executable, "-c", codigo, str(salida)], entorno=propio, carpeta=tmp_path).esperar(30) == 0
	datos, extra, carpeta = salida.read_text(encoding="utf-8").split("|")
	assert extra == "valor" and carpeta.lower() == str(tmp_path).lower()


def test_orden_del_reproductor_desde_codigo():
	orden = procesos.orden_reproductor(["casa.elab", "--alumno", "ana"])
	assert orden == [sys.executable, str(paths.ruta_base() / "main.py"), "--jugar", "casa.elab", "--alumno", "ana"]


def test_orden_del_reproductor_compilado(monkeypatch, tmp_path):
	monkeypatch.setattr(paths, "CONGELADA", True)
	monkeypatch.setattr(paths, "ruta_base", lambda: tmp_path)
	assert procesos.orden_reproductor(["casa.elab"]) == [str(tmp_path / EJECUTABLE_REPRODUCTOR), "casa.elab"]
	with pytest.raises(ErrorProceso, match=EJECUTABLE_REPRODUCTOR):
		procesos.lanzar_reproductor(["casa.elab"])


@pytest.mark.lento
def test_lanzar_reproductor_de_verdad(data_temporal):
	"""El Estudio lanza el reproductor real (provisional) y este sale con 0 dejando su registro."""
	proceso = procesos.lanzar_reproductor(["--comprobar-arranque"])
	assert proceso.orden[1:3] == [str(paths.ruta_base() / "main.py"), "--jugar"]
	assert proceso.esperar(120) == 0
	registros = list((data_temporal / "logs").glob("jugar_*.log"))
	assert len(registros) == 1
	assert not list((data_temporal / "logs").glob("sesion_*.log")), "el reproductor no escribe en los archivos del Estudio"
