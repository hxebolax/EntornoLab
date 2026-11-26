"""Integración REAL del script de sustitución (.bat) sobre una instalación falsa.

Solo en Windows. Cada caso:

1. Crea una «instalación» 1.0.0 en una carpeta con espacios, tilde, eñe y
   apóstrofo: los dos ejecutables (falsos), ``lib/``, ``app_falsa.py`` (el
   programa que se relanza) y un ``data/`` con configuración, base de datos,
   sesiones, entornos, registros y complementos del usuario.
2. Publica la 1.1.0 firmada en un servidor HTTP local. Su ZIP trae además un
   ``data/config/config.json`` y una base de datos que NUNCA deben llegar.
3. Recorre el flujo real: comprobar, descargar y preparar, lanzar el .bat. Un
   proceso aparte hace de «Estudio en ejecución» que el script espera.
4. La versión nueva arranca bien (escribe el marcador) o falla; se comprueba
   la sustitución o la vuelta atrás y que los datos del usuario siguen
   intactos byte a byte.

Tardan unos segundos por caso (esperas reales del script).
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.core import red
from app.services import actualizador
from tests._actualizador_util import RAIZ, Claves, escribir_json, publicar_version
from tests.servidor_http_prueba import ServidorPrueba

pytestmark = [pytest.mark.skipif(sys.platform != "win32", reason="El script de sustitución es un .bat de Windows"), pytest.mark.lento]

# pythonw evita que se abran ventanas de consola al relanzar el programa falso.
PYTHON_SIN_VENTANA = (
	str(Path(sys.executable).with_name("pythonw.exe")) if Path(sys.executable).with_name("pythonw.exe").is_file() else sys.executable
)

APP_FALSA = '''"""Programa falso que hace de Estudio instalado (versión {version})."""
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent
sys.path.insert(0, {proyecto!r})
VERSION = "{version}"
COMPORTAMIENTO = "{comportamiento}"


def main():
	logs = RAIZ / "data" / "logs"
	logs.mkdir(parents=True, exist_ok=True)
	with open(logs / "arranques.txt", "a", encoding="utf-8") as registro:
		registro.write(VERSION + " " + " ".join(sys.argv[1:]) + "\\n")
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


def _archivos_version(version: str, comportamiento: str) -> dict[str, bytes]:
	return {
		"EntornoLab.exe": f"ESTUDIO {version}".encode(),
		"EntornoLabJugar.exe": f"REPRODUCTOR {version}".encode(),
		"lib/modulo.txt": f"modulo {version}".encode(),
		f"lib/solo_{version}.txt": b"solo en esta version",
		"lib/paquete/data/interno.txt": f"interno {version}".encode(),
		"app_falsa.py": APP_FALSA.format(version=version, comportamiento=comportamiento, proyecto=str(RAIZ)).encode("utf-8"),
		"data/sounds/aviso.wav": f"sonido {version}".encode(),
		"data/plugins/mobiliario/complemento.json": _ficha("mobiliario", version),
		"data/plugins/ciudad/complemento.json": _ficha("ciudad", version),
	}


def _crear_instalacion(carpeta: Path) -> None:
	for nombre, contenido in _archivos_version("1.0.0", "sana").items():
		ruta = carpeta / nombre
		ruta.parent.mkdir(parents=True, exist_ok=True)
		ruta.write_bytes(contenido)
	usuario = {
		"data/config/config.json": b'{"general": {"idioma": "es"}}',
		# «ciudad» lo actualizó el usuario desde el catálogo en línea a la 5.0; «propio» es suyo.
		"data/config/complementos.json": json.dumps({"instalados": {"ciudad": {"version": "5.0"}, "propio": {"version": "1.0"}}}).encode(),
		"data/plugins/ciudad/complemento.json": _ficha("ciudad", "5.0"),
		"data/plugins/propio/complemento.json": _ficha("propio", "1.0"),
		"data/plugins/propio/sonidos/mio.wav": os.urandom(128),
		"data/db/entornolab.db": os.urandom(4096),
		"data/sessions/sesion ñ.json.gz": os.urandom(256),
		"data/entornos/mi casa.elab": os.urandom(512),
		"data/backups/copia.zip": os.urandom(64),
	}
	for nombre, contenido in usuario.items():
		ruta = carpeta / nombre
		ruta.parent.mkdir(parents=True, exist_ok=True)
		ruta.write_bytes(contenido)


def _datos_usuario(datos: Path) -> dict[str, bytes]:
	"""Todo data/ salvo lo que escribe el propio proceso (registros, temporales, memoria
	del actualizador) y los recursos que una versión puede refrescar."""
	resultado = {}
	for ruta in datos.rglob("*"):
		relativa = ruta.relative_to(datos)
		if not ruta.is_file() or relativa.parts[0] in ("logs", "temp", "sounds") or ruta.name == "actualizaciones.json":
			continue
		if relativa.parts[:2] == ("plugins", "mobiliario"):
			continue  # complemento de serie: la versión nueva lo pone al día
		resultado[relativa.as_posix()] = ruta.read_bytes()
	return resultado


def _esperar(condicion, segundos: float) -> bool:
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		if condicion():
			return True
		time.sleep(0.25)
	return condicion()


def _terminar_restos(carpeta: Path) -> None:
	"""Mata cualquier proceso que siga ejecutando algo de la instalación de prueba."""
	filtro = str(carpeta).replace("'", "''")
	orden = (
		"Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -and $_.CommandLine.Contains('" + filtro + "') } "
		"| ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"
	)
	subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", orden], capture_output=True, timeout=60, check=False)


@pytest.fixture
def entorno(tmp_path, monkeypatch):
	monkeypatch.setattr(red, "ESPERA_INICIAL", 0.01)
	claves = Claves(tmp_path / "claves")
	servidor = ServidorPrueba(tmp_path / "servidor")
	instalacion = tmp_path / "Programas d'prueba ñ" / "Entorno Lab"
	_crear_instalacion(instalacion)
	procesos: list[subprocess.Popen] = []
	yield {"claves": claves, "servidor": servidor, "instalacion": instalacion, "procesos": procesos}
	servidor.cerrar()
	for proceso in procesos:
		if proceso.poll() is None:
			proceso.kill()
	_terminar_restos(instalacion)


def _ejecutar(entorno, comportamiento: str, *, espera_salud: int = 25, espera_cierre: int = 30, vida_app: float = 3):
	"""Publica la 1.1.0, prepara el script, lo lanza y espera a que termine."""
	instalacion: Path = entorno["instalacion"]
	publicar_version(
		entorno["servidor"].carpeta,
		"1.1.0",
		{
			**_archivos_version("1.1.0", comportamiento),
			"data/config/config.json": b'{"sobrescrito": 1}',
			"data/db/entornolab.db": b"base de datos del paquete",
			"data/entornos/mi casa.elab": b"entorno del paquete",
		},
		entorno["claves"],
	)
	app_en_marcha = subprocess.Popen([PYTHON_SIN_VENTANA, "-c", f"import time; time.sleep({vida_app})"])
	entorno["procesos"].append(app_en_marcha)
	config = actualizador.Configuracion(
		version_actual="1.0.0",
		carpeta_app=instalacion,
		url_estable=entorno["servidor"].url("version.json"),
		claves_publicas=(entorno["claves"].publica,),
		comando=[PYTHON_SIN_VENTANA, str(instalacion / "app_falsa.py")],
		permitir_desde_codigo=True,
		espera_salud=espera_salud,
		espera_cierre=espera_cierre,
		pid_a_esperar=app_en_marcha.pid,
	)
	info = actualizador.comprobar(config)
	assert info is not None and info.version == "1.1.0"
	ruta_bat = actualizador.descargar_y_preparar(config, info)
	script = actualizador.lanzar_sustitucion(ruta_bat)
	entorno["procesos"].append(script)
	script.wait(timeout=espera_cierre * 3 + espera_salud + 120)
	resultado = {}
	if config.archivo_resultado.is_file():
		for linea in config.archivo_resultado.read_text(encoding="utf-8").splitlines():
			clave, _sep, valor = linea.partition("=")
			resultado[clave] = valor
	return config, ruta_bat, resultado


def _registro(config) -> str:
	return config.registro_script.read_text(encoding="utf-8", errors="replace") if config.registro_script.is_file() else "(sin registro)"


def test_actualizacion_correcta_sin_tocar_los_datos_del_usuario(entorno):
	instalacion = entorno["instalacion"]
	antes = _datos_usuario(instalacion / "data")
	config, ruta_bat, resultado = _ejecutar(entorno, "sana")
	assert resultado.get("estado") == "correcta", _registro(config)
	# Los DOS ejecutables y las bibliotecas son los nuevos.
	assert (instalacion / "EntornoLab.exe").read_bytes() == b"ESTUDIO 1.1.0"
	assert (instalacion / "EntornoLabJugar.exe").read_bytes() == b"REPRODUCTOR 1.1.0"
	assert (instalacion / "lib" / "modulo.txt").read_bytes() == b"modulo 1.1.0"
	assert (instalacion / "lib" / "paquete" / "data" / "interno.txt").read_bytes() == b"interno 1.1.0"
	assert (instalacion / "data" / "sounds" / "aviso.wav").read_bytes() == b"sonido 1.1.0"
	# Configuración, base de datos, sesiones, entornos, copias y complementos del usuario: intactos.
	assert _datos_usuario(instalacion / "data") == antes
	# Complementos: el de serie se pone al día; el que el usuario tenía más nuevo se conserva.
	assert json.loads((instalacion / "data" / "plugins" / "mobiliario" / "complemento.json").read_text())["version"] == "1.1.0"
	assert json.loads((instalacion / "data" / "plugins" / "ciudad" / "complemento.json").read_text())["version"] == "5.0"
	assert (instalacion / "data" / "plugins" / "propio" / "sonidos" / "mio.wav").is_file()
	assert actualizador.leer_estado(config)["version_confirmada"] == "1.1.0"
	assert not config.carpeta_respaldo.exists()
	assert not (config.carpeta_trabajo / "nueva").exists()
	assert _esperar(lambda: not ruta_bat.exists(), 5)  # el .bat se borra solo
	assert "1.1.0 --tras-actualizar" in (instalacion / "data" / "logs" / "arranques.txt").read_text(encoding="utf-8")
	assert actualizador.leer_resultado_anterior(config) is None


def test_vuelta_atras_si_la_version_nueva_no_arranca(entorno):
	instalacion = entorno["instalacion"]
	antes = _datos_usuario(instalacion / "data")
	config, _ruta, resultado = _ejecutar(entorno, "falla")
	assert resultado.get("estado") == "revertida", _registro(config)
	assert resultado.get("motivo") == "se_cerro_sin_confirmar"
	assert (instalacion / "EntornoLab.exe").read_bytes() == b"ESTUDIO 1.0.0"
	assert (instalacion / "EntornoLabJugar.exe").read_bytes() == b"REPRODUCTOR 1.0.0"
	assert (instalacion / "lib" / "modulo.txt").read_bytes() == b"modulo 1.0.0"
	assert not (instalacion / "lib" / "solo_1.1.0.txt").exists()  # la restauración quita lo nuevo
	assert (instalacion / "data" / "sounds" / "aviso.wav").read_bytes() == b"sonido 1.0.0"
	assert json.loads((instalacion / "data" / "plugins" / "mobiliario" / "complemento.json").read_text())["version"] == "1.0.0"
	assert _datos_usuario(instalacion / "data") == antes
	# La versión anterior se relanza (sin --tras-actualizar) y el usuario recibe el aviso.
	arranques = instalacion / "data" / "logs" / "arranques.txt"
	assert _esperar(lambda: "1.0.0 \n" in arranques.read_text(encoding="utf-8"), 20)
	mensaje = actualizador.leer_resultado_anterior(config)
	assert mensaje and "1.1.0" in mensaje and "1.0.0" in mensaje
	assert actualizador.version_saltada() == "1.1.0"  # no se vuelve a ofrecer sola


def test_con_un_reproductor_abierto_no_se_toca_nada(entorno):
	"""El segundo ejecutable: mientras haya un reproductor de esta carpeta abierto, no se sustituye."""
	instalacion = entorno["instalacion"]
	(instalacion / "jugar_falso.py").write_text("import time\ntime.sleep(300)\n", encoding="utf-8")
	reproductor = subprocess.Popen([PYTHON_SIN_VENTANA, str(instalacion / "jugar_falso.py")])
	entorno["procesos"].append(reproductor)
	antes = _datos_usuario(instalacion / "data")
	config, _ruta, resultado = _ejecutar(entorno, "sana", espera_cierre=3, vida_app=1)
	assert resultado.get("estado") == "no_aplicada", _registro(config)
	assert resultado.get("motivo") == "la_aplicacion_no_se_cerro"
	assert "reproductor" in _registro(config)
	assert reproductor.poll() is None, "el script nunca mata al reproductor"
	assert (instalacion / "EntornoLab.exe").read_bytes() == b"ESTUDIO 1.0.0"
	assert (instalacion / "EntornoLabJugar.exe").read_bytes() == b"REPRODUCTOR 1.0.0"
	assert _datos_usuario(instalacion / "data") == antes
	assert not config.carpeta_respaldo.exists()
	mensaje = actualizador.leer_resultado_anterior(config)
	assert mensaje and "seguían abiertos" in mensaje


def test_si_el_estudio_no_se_cierra_no_se_toca_nada(entorno):
	instalacion = entorno["instalacion"]
	config, _ruta, resultado = _ejecutar(entorno, "sana", espera_cierre=3, vida_app=120)
	assert resultado.get("estado") == "no_aplicada", _registro(config)
	assert (instalacion / "EntornoLab.exe").read_bytes() == b"ESTUDIO 1.0.0"
	assert not config.carpeta_respaldo.exists()


def test_el_registro_de_complementos_de_prueba_es_coherente(tmp_path):
	"""Comprobación del propio material de la prueba: el registro marca los del usuario."""
	escribir_json(tmp_path / "config" / "complementos.json", {"instalados": {"ciudad": {}, "propio": {}}})
	assert actualizador.complementos_del_usuario(tmp_path) == {"ciudad", "propio"}
