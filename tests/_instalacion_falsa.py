"""Instalación falsa de EntornoLab y bloqueos REALES para las pruebas del actualizador.

La instalación tiene la misma forma que la compilación de cx_Freeze: los dos
ejecutables en la raíz (falsos: unos bytes con su versión), una biblioteca
suelta en la raíz (``python315.dll``, también falsa), ``lib/`` con una DLL de
verdad (copia de ``python3.dll``, para poder CARGARLA desde otro proceso), y
``data/`` con recursos de serie y datos del usuario.

El programa que se relanza es ``app_falsa.py`` (con ``pythonw``). Con
``--comprobar-arranque`` comprueba que todos sus ficheros son de SU versión y
dice cuál es: así se distingue una versión entera de una mezcla a medias.

Los bloqueos los mantiene un proceso hijo que recibe la ruta por una variable
de entorno: su línea de órdenes no nombra la carpeta de la instalación, como un
antivirus o el indexador (el script de sustitución busca «copias abiertas» por
la ruta, y a esos no los debe confundir con un reproductor).
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from tests._actualizador_util import RAIZ

PYTHON = sys.executable
PYTHON_SIN_VENTANA = (
	str(Path(sys.executable).with_name("pythonw.exe")) if Path(sys.executable).with_name("pythonw.exe").is_file() else PYTHON
)
DLL_DE_PRUEBA = (Path(sys.base_prefix) / "python3.dll").read_bytes()
# Carpeta del usuario con espacios, paréntesis, «&», «%», eñe y apóstrofo, como
# «E:\Mis cosas\EntornoLab (copia)».
NOMBRE_INSTALACION = ("Mis cosas", "EntornoLab (copia) & 100% ñ'")

APP_FALSA = '''"""Programa falso que hace de Estudio instalado (versión {version})."""
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, {proyecto!r})
VERSION = "{version}"
COMPORTAMIENTO = "{comportamiento}"
ESPERADOS = {esperados!r}


def comprobar():
	"""Todos los ficheros del programa deben ser de esta versión: si no, la instalación está a medias."""
	for relativa, contenido in ESPERADOS.items():
		ruta = RAIZ / relativa
		try:
			if not ruta.is_file() or ruta.read_bytes() != contenido.encode("utf-8"):
				return "MEZCLA " + relativa
		except OSError:
			return "ILEGIBLE " + relativa
	return "ok"


def main():
	if "--comprobar-arranque" in sys.argv:
		estado = comprobar()
		print("VERSION " + VERSION + " " + estado)
		return 0 if estado == "ok" else 1
	logs = RAIZ / "data" / "logs"
	logs.mkdir(parents=True, exist_ok=True)
	with open(logs / "arranques.txt", "a", encoding="utf-8") as registro:
		registro.write(VERSION + "|" + " ".join(sys.argv[1:]) + "|" + comprobar() + "\\n")
	if "--tras-actualizar" not in sys.argv:
		return 0
	if COMPORTAMIENTO == "falla":
		return 3
	time.sleep(1)
	from app.services import actualizador
	config = actualizador.Configuracion(version_actual=VERSION, carpeta_app=RAIZ, comando=[])
	actualizador.confirmar_arranque(config, tras_actualizar=True)
	time.sleep(2)
	return 0


sys.exit(main())
'''


def _ficha(identificador: str, version: str) -> bytes:
	return json.dumps({"formato": 1, "id": identificador, "version": version, "objetos": []}).encode("utf-8")


def _textos(version: str) -> dict[str, str]:
	"""Ficheros de texto del programa con su versión (los que comprueba ``app_falsa.py``)."""
	return {
		"EntornoLab.exe": f"ESTUDIO {version}",
		"EntornoLabJugar.exe": f"REPRODUCTOR {version}",
		"python315.dll": f"NUCLEO {version}",
		"lib/modulo.txt": f"modulo {version}",
		"lib/paquete/data/interno.txt": f"interno {version}",
	}


def archivos_version(version: str, comportamiento: str = "sana", hondo: str = "") -> dict[str, bytes]:
	"""Ficheros de una versión (programa y recursos de serie), como los lleva su ZIP."""
	archivos = {nombre: texto.encode("utf-8") for nombre, texto in _textos(version).items()}
	archivos.update(
		{
			f"lib/solo_{version}.txt": b"solo en esta version",
			"lib/prueba.dll": DLL_DE_PRUEBA,
			"app_falsa.py": APP_FALSA.format(
				version=version, comportamiento=comportamiento, proyecto=str(RAIZ), esperados=_textos(version)
			).encode("utf-8"),
			"data/sounds/aviso.wav": f"sonido {version}".encode(),
			"data/plugins/mobiliario/complemento.json": _ficha("mobiliario", version),
			"data/plugins/ciudad/complemento.json": _ficha("ciudad", version),
		}
	)
	if hondo:
		archivos[f"lib/{hondo}/profundo.txt"] = f"profundo {version}".encode()
	return archivos


DATOS_USUARIO = {
	"data/config/config.json": b'{"general": {"idioma": "es"}}',
	# «ciudad» lo actualizó el usuario desde el catálogo en línea a la 5.0; «propio» es suyo.
	"data/config/complementos.json": json.dumps({"instalados": {"ciudad": {"version": "5.0"}, "propio": {"version": "1.0"}}}).encode(),
	"data/plugins/ciudad/complemento.json": _ficha("ciudad", "5.0"),
	"data/plugins/propio/complemento.json": _ficha("propio", "1.0"),
	"data/plugins/propio/sonidos/mio.wav": b"sonido del usuario" * 10,
	"data/db/entornolab.db": b"SQLite falso del usuario" * 100,
	"data/sessions/sesion ñ.json.gz": b"sesion del alumno" * 10,
	"data/entornos/mi casa.elab": b"entorno del profesional" * 20,
	"data/backups/copia.zip": b"copia de seguridad" * 5,
	"data/logs/estudio.log": b"registro del usuario\n",
}

# Lo que el ZIP trae y NUNCA debe llegar a la instalación.
CEBO_DATOS_USUARIO = {
	"data/config/config.json": b'{"sobrescrito": 1}',
	"data/db/entornolab.db": b"base de datos del paquete",
	"data/entornos/mi casa.elab": b"entorno del paquete",
	"data/sessions/sesion ñ.json.gz": b"sesion del paquete",
}


def crear_instalacion(carpeta: Path, version: str = "1.0.0", hondo: str = "") -> None:
	"""Instalación completa: programa de ``version`` más los datos del usuario."""
	for nombre, contenido in {**archivos_version(version, hondo=hondo), **DATOS_USUARIO}.items():
		ruta = carpeta / nombre
		ruta.parent.mkdir(parents=True, exist_ok=True)
		ruta.write_bytes(contenido)


def huellas(carpeta: Path, *, programa: bool) -> dict[str, str]:
	"""SHA-256 de cada fichero: del programa (todo menos ``data``) o de los datos del usuario.

	De ``data`` se excluye lo que escriben el propio script y el programa falso
	(registro de la actualización, arranques, temporales, memoria contra
	retrocesos) y los recursos que la versión nueva refresca por diseño.
	"""
	resultado: dict[str, str] = {}
	for ruta in carpeta.rglob("*"):
		if not ruta.is_file():
			continue
		relativa = ruta.relative_to(carpeta)
		es_data = relativa.parts[0].lower() == "data"
		if programa == es_data:
			continue
		if es_data:
			interior = relativa.parts[1:]
			if interior[0] == "temp" or interior[0] == "sounds" or interior[:2] == ("plugins", "mobiliario"):
				continue
			if relativa.as_posix() in ("data/logs/actualizacion.log", "data/logs/arranques.txt", "data/config/actualizaciones.json"):
				continue
		resultado[relativa.as_posix()] = hashlib.sha256(ruta.read_bytes()).hexdigest()
	return resultado


def huellas_esperadas(version: str, hondo: str = "") -> dict[str, str]:
	"""Huellas del programa de ``version`` tal como lo trae su ZIP (sin ``data``)."""
	return {
		nombre: hashlib.sha256(contenido).hexdigest()
		for nombre, contenido in archivos_version(version, hondo=hondo).items()
		if not nombre.startswith("data/")
	}


def comprobar_arranque(carpeta: Path) -> tuple[int, str]:
	"""Ejecuta ``app_falsa.py --comprobar-arranque`` y devuelve (código, salida)."""
	proceso = subprocess.run(
		[PYTHON, str(carpeta / "app_falsa.py"), "--comprobar-arranque"], capture_output=True, text=True, timeout=60, check=False
	)
	return proceso.returncode, proceso.stdout.strip()


_CODIGO_BLOQUEO = r"""
import ctypes, os, sys, time
from ctypes import wintypes
ruta, modo, segundos = os.environ["RUTA_BLOQUEO"], os.environ["MODO_BLOQUEO"], float(os.environ["SEGUNDOS_BLOQUEO"])
k = ctypes.WinDLL("kernel32", use_last_error=True)
k.CreateFileW.restype = wintypes.HANDLE
k.CreateFileW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD, wintypes.LPVOID, wintypes.DWORD, wintypes.DWORD, wintypes.HANDLE]
if modo == "dll":
	ctypes.WinDLL(ruta)
elif modo == "exclusivo":
	# Abierto para leer SIN compartir nada: como un antivirus que examina el fichero.
	h = k.CreateFileW(ruta, 0x80000000, 0, None, 3, 0, None)
	if h == wintypes.HANDLE(-1).value:
		sys.exit("no se pudo abrir: %d" % ctypes.get_last_error())
elif modo == "compartido":
	# Abierto como lo abre Python (lectura y escritura compartidas, borrado no).
	f = open(ruta, "rb")
print("listo", flush=True)
time.sleep(segundos)
"""


def bloquear(ruta: Path, modo: str, segundos: float = 600) -> subprocess.Popen:
	"""Proceso hijo que mantiene ``ruta`` bloqueada (``exclusivo``, ``compartido`` o ``dll``) durante ``segundos``.

	Devuelve cuando el bloqueo ya está puesto. Matarlo lo libera.
	"""
	entorno = {**os.environ, "RUTA_BLOQUEO": str(ruta), "MODO_BLOQUEO": modo, "SEGUNDOS_BLOQUEO": str(segundos)}
	proceso = subprocess.Popen([PYTHON, "-c", _CODIGO_BLOQUEO], env=entorno, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
	linea = proceso.stdout.readline().strip()
	if linea != "listo":
		proceso.kill()
		raise RuntimeError(f"El bloqueo de prueba no se pudo poner: {linea or proceso.stderr.read()}")
	return proceso


def sid_actual() -> str:
	"""SID del usuario actual (para las reglas de denegación de icacls)."""
	salida = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"], capture_output=True, text=True, check=True).stdout
	return salida.strip().split(",")[-1].strip('"')


def denegar(ruta: Path, permisos: str) -> None:
	"""Niega al usuario actual ``permisos`` (sintaxis de icacls) sobre ``ruta``."""
	subprocess.run(["icacls", str(ruta), "/deny", f"*{sid_actual()}:{permisos}"], capture_output=True, check=True)


def quitar_denegaciones(ruta: Path) -> None:
	"""Quita las denegaciones del usuario actual (el propietario siempre puede cambiar los permisos)."""
	subprocess.run(["icacls", str(ruta), "/remove:d", f"*{sid_actual()}"], capture_output=True, check=False)


def terminar_restos(carpeta: Path) -> None:
	"""Mata cualquier proceso que siga ejecutando algo de la instalación de prueba."""
	filtro = str(carpeta).replace("'", "''")
	orden = (
		"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains('" + filtro + "') } "
		"| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
	)
	subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", orden], capture_output=True, timeout=60, check=False)


def esperar(condicion, segundos: float) -> bool:
	"""Espera hasta que ``condicion()`` sea cierta o pasen ``segundos``."""
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		if condicion():
			return True
		time.sleep(0.25)
	return bool(condicion())
