"""Verifica que una compilación de cx_Freeze de EntornoLab está completa y LIMPIA.

Comprueba, sin ejecutar la aplicación:

1. Que existen los DOS ejecutables: el Estudio y el reproductor.
2. Que viajan los runtimes de Visual C++ (``include_msvcr``).
3. Que cada paquete lleva sus recursos: el catálogo español de wx
   (``wxstd.mo``), las DLL de los lectores de pantalla de accessible_output2,
   SDL2 de pygame, PortAudio, libsndfile, ``cacert.pem`` de certifi y las
   extensiones de markdown; y que viajan todos los paquetes propios de ``app``.
4. Que viaja OpenAL Soft en ``data/bin/openal/soft_oal.dll`` (el motor de
   sonido 3D de serie) con ``alsoft.ini`` y los perfiles HRTF; los paquetes de
   sonido con su índice (``catalogo.json`` y un ``pack.json`` por paquete); al
   menos un complemento, con cada complemento del que dependen otros
   (``depende_de``, como ``comun``) y sus sonidos, y un entorno de ejemplo; el manual; un catálogo de
   traducción compilado por cada ``.po`` del proyecto, y cada aviso de
   licencia enlazado desde ``data/docs/licencias/LEEME.md``.
   Que viaja el motor BASS completo: ``lib/basskit`` con ``bass.dll`` y su
   licencia dentro; y que NO viaja nada del basskit completo (FFmpeg y
   complementos), que la aplicación no usa.
   Que viajan la licencia del programa (``LICENSE.txt``) y los avisos de
   terceros (``data/docs/licencias``).
5. Que ``data/`` no contiene nada personal ni generado durante las pruebas
   (configuración, registros, fichas, sesiones, entornos del profesional).
6. Que no se han colado cachés de Python ni herramientas de desarrollo.
7. Que no lleva ninguna ruta ni dato del equipo de desarrollo (carpeta de
   usuario, carpeta de los proyectos, Python, entorno virtual, nombre de
   usuario), ni en los ``.pyc`` ni en ``library.zip`` ni en los metadatos:
   ``tools/comprobar_rutas.py``.

Uso::

	python tools/verificar_build.py                      build/entornolab con los nombres de serie
	python tools/verificar_build.py build/entornolab EntornoLab.exe EntornoLabJugar.exe
	python tools/verificar_build.py --motores            abre OpenAL (HRTF) y BASS de la compilación, sin sonar
	python tools/verificar_build.py --guion              ejecuta EntornoLabJugar.exe en modo guion (sin ventana ni sonido)

``--motores`` carga, en un Python aislado que solo ve ``build/entornolab/lib``,
los motores OpenAL con HRTF (el perfil integrado y uno de ``data/bin/openal/hrtf``)
y BASS en modo «en memoria»: no abre la tarjeta de sonido ni suena nada.

``--guion`` ejecuta ``EntornoLabJugar.exe`` de verdad en modo guion (sin ventana
ni sonido, ``app/reproductor/guion.py``), con una COPIA temporal de la ``data``
compilada: abre un entorno de ejemplo, empieza su primera actividad y comprueba
con el informe que OpenAL (con HRTF) y BASS arrancan en memoria, que hay paquetes
de sonido y que no falta ningún complemento del ejemplo.

	python tools/verificar_build.py --guion [build/entornolab]

Devuelve 0 si todo está bien y 1 si hay algún problema (lo usan setup_cx.py,
empaquetar.py y entorno.bat para detener el empaquetado).

Procede de la plantilla del agente «entorno-virtual».
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
CARPETA_POR_DEFECTO = RAIZ / "build" / "entornolab"
# Comprueba además que OpenAL con HRTF y BASS cargan con lo que viaja (ver comprobar_motores).
ORDEN_MOTORES = "--motores"
# Uso interno: el proceso aislado que lanza comprobar_motores.
ORDEN_MOTORES_INTERNA = "--motores-en-proceso-aislado"
# Ejecuta el reproductor compilado en modo guion (ver comprobar_guion).
ORDEN_GUION = "--guion"
# Entorno de ejemplo con el que se prueba el reproductor compilado (el primero que haya si falta).
EJEMPLO_GUION = "vivienda-de-ejemplo.elab"
# Segundos como mucho que puede tardar cada ejecución del reproductor compilado.
PLAZO_GUION = 240

# Carpetas de data/ que nunca deben distribuirse (mismo criterio que setup_cx.py).
DATA_PROHIBIDO = {
	"config",
	"logs",
	"db",
	"sessions",
	"entornos",
	"cache",
	"temp",
	"backups",
	"downloads",
	"diagnostico",
	"database",
	"tmp",
	"claves",
	"keys",
}
# Extensiones que delatan datos generados en tiempo de ejecución.
EXTENSIONES_SOSPECHOSAS = {".log", ".jsonl", ".db", ".db-wal", ".db-shm", ".sqlite", ".key", ".dat", ".bak", ".tmp", ".gz"}
# Runtimes de Visual C++ que include_msvcr copia junto al ejecutable. En x64,
# Python y wxPython de 64 bits necesitan además vcruntime140_1.dll.
RUNTIMES_VC = ("vcruntime140.dll", "vcruntime140_1.dll", "msvcp140.dll")
# Recursos que deben viajar si el paquete correspondiente está en la compilación
# (carpeta del paquete dentro de lib/ → archivos que tienen que existir).
RECURSOS_DE_PAQUETES: dict[str, tuple[str, ...]] = {
	# Botones estándar en español.
	"wx": ("wx/locale/es/LC_MESSAGES/wxstd.mo",),
	# Voz con NVDA, JAWS (por COM, sin DLL), Dolphin, System Access y ZDSR.
	"accessible_output2": (
		"accessible_output2/lib/nvdaControllerClient64.dll",
		"accessible_output2/lib/SAAPI32.dll",
		"accessible_output2/lib/dolapi.dll",
	),
	# Ventana, sonido y mandos del reproductor.
	"pygame": ("pygame/SDL2.dll", "pygame/SDL2_mixer.dll", "pygame/SDL2_ttf.dll"),
	# Salida de audio del motor clásico.
	"_sounddevice_data": ("_sounddevice_data/portaudio-binaries/libportaudio64bit.dll",),
	# Lectura de ficheros de sonido.
	"_soundfile_data": ("_soundfile_data/libsndfile_x64.dll",),
	# Motor de sonido BASS: la DLL viaja dentro del paquete, con el texto de su licencia.
	"basskit": (
		"basskit/data/dlls/x64/bass.dll",
		"basskit/data/licenses/bass24/bass.txt",
	),
	# Certificados de confianza para https: sin cacert.pem, certifi.where() apunta a la nada.
	"certifi": ("certifi/cacert.pem",),
}
# Paquetes sin los cuales la aplicación no cumple su función.
PAQUETES_OBLIGATORIOS = (
	"wx",
	"app",
	"pygame",
	"numpy",
	"accessible_output2",
	"cryptography",
	"basskit",
	"certifi",
	"markdown",
	# Las extensiones de markdown se cargan por nombre: el análisis de cx_Freeze no las ve.
	"markdown/extensions",
)
# Paquetes propios que deben viajar (lib/app/...). Si falta uno, una pantalla o una
# función entera fallaría al usarla, no al arrancar: mejor saberlo aquí.
PAQUETES_APP = (
	"app/core",
	"app/dominio",
	"app/motor",
	"app/actividades",
	"app/audio",
	"app/entrada",
	"app/ui",
	"app/reproductor",
	"app/reproductor/pantallas",
	"app/importar",
	"app/exportar",
	"app/services",
	"app/seguimiento",
	"app/supervision",
)
# Archivos de data/ que deben viajar siempre.
DATA_OBLIGATORIO = (
	"bin/openal/soft_oal.dll",
	# Configuración de OpenAL Soft que apunta a los perfiles HRTF de serie.
	"bin/openal/alsoft.ini",
	# Índice de los paquetes de sonido.
	"sounds/catalogo.json",
	"docs/manual.md",
	"docs/teclas.md",
	"docs/novedades.md",
	# Avisos de licencia de lo que viaja con el programa (BASS exige acompañarla de la suya).
	"docs/licencias/LEEME.md",
	"docs/licencias/BASS.txt",
	"docs/licencias/OpenAL-Soft-LGPL.txt",
)
# Archivos que deben estar junto a los ejecutables.
ARCHIVOS_RAIZ = ("LICENSE.txt",)
# El basskit que viaja es el recortado: FFmpeg y los complementos de BASS no deben colarse
# (la aplicación no los usa, pesan decenas de megas y FFmpeg traería sus propias obligaciones).
PROHIBIDOS_EN_BUILD = (
	"avcodec-*.dll",
	"avformat-*.dll",
	"avfilter-*.dll",
	"avutil-*.dll",
	"swscale-*.dll",
	"swresample-*.dll",
	"ffmpeg.exe",
	"ffprobe.exe",
	"bass_*.dll",
	"bassenc*.dll",
	"bassmix.dll",
	"bassmidi.dll",
	"basswasapi.dll",
	"bassasio.dll",
)
# Paquetes de desarrollo que no deberían viajar.
PAQUETES_DESARROLLO = ("pytest", "_pytest", "pip", "ruff", "cx_Freeze")


def _tamano_legible(bytes_: int) -> str:
	"""Formatea un tamaño en MB con un decimal."""
	return f"{bytes_ / (1024 * 1024):.1f} MB"


def ejecutables_por_defecto() -> tuple[str, str]:
	"""Nombres de los dos ejecutables, leídos de app/core/version.py sin importar la aplicación."""
	nombres = {"EJECUTABLE_ESTUDIO": "EntornoLab.exe", "EJECUTABLE_REPRODUCTOR": "EntornoLabJugar.exe"}
	try:
		texto = (RAIZ / "app" / "core" / "version.py").read_text(encoding="utf-8")
	except OSError:
		return nombres["EJECUTABLE_ESTUDIO"], nombres["EJECUTABLE_REPRODUCTOR"]
	for constante in nombres:
		coincidencia = re.search(rf"^{constante}\s*=\s*[\"']([^\"']+)[\"']", texto, re.MULTILINE)
		if coincidencia:
			nombres[constante] = coincidencia.group(1)
	return nombres["EJECUTABLE_ESTUDIO"], nombres["EJECUTABLE_REPRODUCTOR"]


def _verificar_ejecutables(destino: Path, ejecutables: tuple[str, ...]) -> list[str]:
	problemas = [f"Falta el ejecutable {nombre}." for nombre in ejecutables if not (destino / nombre).is_file()]
	problemas += [f"Falta {nombre} junto a los ejecutables." for nombre in ARCHIVOS_RAIZ if not (destino / nombre).is_file()]
	return problemas


def _verificar_prohibidos(destino: Path) -> list[str]:
	"""Nada del basskit completo: solo ``bass.dll``."""
	problemas: list[str] = []
	for patron in PROHIBIDOS_EN_BUILD:
		for archivo in sorted(destino.rglob(patron)):
			problemas.append(
				f"No debe viajar {archivo.relative_to(destino).as_posix()}: instale el basskit recortado de __pip__ (solo bass.dll)."
			)
	return problemas


def _verificar_runtimes(destino: Path) -> list[str]:
	presentes = {archivo.name.lower() for archivo in destino.glob("*.dll")}
	if (destino / "lib").is_dir():
		presentes |= {archivo.name.lower() for archivo in (destino / "lib").glob("*.dll")}
	faltan = [dll for dll in RUNTIMES_VC if dll not in presentes]
	if faltan:
		return ["Faltan runtimes de Visual C++ (" + ", ".join(faltan) + "). Compruebe que setup_cx.py tiene include_msvcr=True."]
	return []


def _verificar_data(destino: Path) -> list[str]:
	problemas: list[str] = []
	data = destino / "data"
	if not data.is_dir():
		return ["Falta la carpeta data en la distribución."]
	for carpeta in data.iterdir():
		if carpeta.is_dir() and carpeta.name.lower() in DATA_PROHIBIDO:
			problemas.append(f"data/{carpeta.name} NO debe distribuirse (datos personales o generados).")
	for archivo in data.rglob("*"):
		if archivo.is_file() and archivo.suffix.lower() in EXTENSIONES_SOSPECHOSAS:
			problemas.append(f"Archivo sospechoso en la distribución: {archivo.relative_to(destino).as_posix()}")
		if archivo.is_dir() and archivo.name == "__pycache__":
			problemas.append(f"Caché de Python en la distribución: {archivo.relative_to(destino).as_posix()}")
	for relativo in DATA_OBLIGATORIO:
		if not (data / relativo).is_file():
			problemas.append(f"Falta data/{relativo}.")
	problemas += _verificar_sonidos(data)
	problemas += _verificar_hrtf(data)
	problemas += _verificar_traducciones(data)
	problemas += _verificar_licencias(data)
	if not (data / "plugins").is_dir() or not any((data / "plugins").rglob("complemento.json")):
		problemas.append("data/plugins no contiene ningún complemento (complemento.json).")
	else:
		problemas += _verificar_dependencias_complementos(data / "plugins")
	if not (data / "ejemplos").is_dir() or not any((data / "ejemplos").glob("*.elab")):
		problemas.append("data/ejemplos no contiene ningún entorno de ejemplo (ejecute entorno.bat ejemplos).")
	return problemas


def _verificar_dependencias_complementos(plugins: Path) -> list[str]:
	"""Viaja cada complemento del que dependen otros (``depende_de``), con sus sonidos.

	Los complementos de serie citan sonidos de otro como ``comun:fichero.flac``
	en lugar de llevar copia; si ``data/plugins/comun`` no viajara, esos objetos
	sonarían con el sonido de reserva en el ordenador del profesional.
	"""
	import json

	problemas: list[str] = []
	requeridos: dict[str, list[str]] = {}
	for ficha in sorted(plugins.glob("*/complemento.json")):
		try:
			datos = json.loads(ficha.read_text(encoding="utf-8"))
		except OSError, ValueError:
			problemas.append(f"No se puede leer data/plugins/{ficha.parent.name}/complemento.json.")
			continue
		dependencias = datos.get("depende_de") if isinstance(datos, dict) else None
		for dependencia in dependencias if isinstance(dependencias, list) else []:
			requeridos.setdefault(str(dependencia), []).append(ficha.parent.name)
	for dependencia, quienes in sorted(requeridos.items()):
		carpeta = plugins / dependencia
		if not (carpeta / "complemento.json").is_file():
			problemas.append(f"Falta data/plugins/{dependencia}, del que dependen {', '.join(sorted(quienes))}.")
		elif not any(archivo.suffix.lower() in (".wav", ".ogg", ".flac") for archivo in (carpeta / "sonidos").glob("*")):
			problemas.append(f"data/plugins/{dependencia} no lleva sus sonidos (sonidos/), y {', '.join(sorted(quienes))} los usan.")
	return problemas


def _verificar_sonidos(data: Path) -> list[str]:
	"""Hay sonidos y cada paquete de ``data/sounds`` lleva su ``pack.json``."""
	sonidos = data / "sounds"
	if not sonidos.is_dir() or not any(archivo.suffix.lower() in (".wav", ".ogg", ".flac") for archivo in sonidos.rglob("*")):
		return ["data/sounds no contiene ningún sonido (ejecute entorno.bat sonidos antes de compilar)."]
	problemas: list[str] = []
	for paquete in sorted(carpeta for carpeta in sonidos.iterdir() if carpeta.is_dir()):
		if not (paquete / "pack.json").is_file():
			problemas.append(f"El paquete de sonidos data/sounds/{paquete.name} no lleva pack.json.")
	return problemas


def _verificar_hrtf(data: Path) -> list[str]:
	"""Viaja al menos un perfil HRTF: sin ellos OpenAL Soft no da sonido binaural."""
	carpeta = data / "bin" / "openal" / "hrtf"
	if not carpeta.is_dir() or not any(carpeta.glob("*.mhr")):
		return ["Faltan los perfiles HRTF en data/bin/openal/hrtf (*.mhr)."]
	return []


def _verificar_traducciones(data: Path) -> list[str]:
	"""Cada idioma traducido en el proyecto viaja compilado: la versión distribuida lee el ``.mo``.

	Se miran los ``.po`` del proyecto (que no viajan) y los que hubiera en la
	compilación, y se avisa una sola vez por idioma.
	"""
	locales = data / "locales"
	idiomas: set[tuple[str, str]] = set()
	for raiz in (RAIZ / "data" / "locales", locales):
		if raiz.is_dir():
			idiomas |= {(po.parent.parent.name, po.stem) for po in raiz.glob("*/LC_MESSAGES/*.po")}
	problemas: list[str] = []
	for idioma, dominio in sorted(idiomas):
		if not (locales / idioma / "LC_MESSAGES" / f"{dominio}.mo").is_file():
			problemas.append(f"Falta el catálogo compilado data/locales/{idioma}/LC_MESSAGES/{dominio}.mo (ejecute entorno.bat idiomas).")
	return problemas


def _verificar_licencias(data: Path) -> list[str]:
	"""Cada aviso de licencia enlazado desde ``docs/licencias/LEEME.md`` viaja de verdad."""
	carpeta = data / "docs" / "licencias"
	leeme = carpeta / "LEEME.md"
	if not leeme.is_file():
		return []
	texto = leeme.read_text(encoding="utf-8", errors="replace")
	problemas: list[str] = []
	for enlace in sorted(set(re.findall(r"\]\(([^)/\\:]+\.(?:txt|md))\)", texto))):
		if not (carpeta / enlace).is_file():
			problemas.append(f"Falta data/docs/licencias/{enlace}, enlazado desde su LEEME.md.")
	return problemas


def _verificar_bibliotecas(destino: Path) -> list[str]:
	problemas: list[str] = []
	lib = destino / "lib"
	if not lib.is_dir():
		return ["Falta la carpeta lib con las bibliotecas."]
	for paquete in PAQUETES_OBLIGATORIOS:
		if not (lib / paquete).is_dir():
			problemas.append(f"Falta el paquete lib/{paquete} (¿está instalado en el entorno virtual y fuera del zip?).")
	for paquete in PAQUETES_APP:
		if not (lib / paquete).is_dir():
			problemas.append(f"Falta el paquete propio lib/{paquete}.")
	for paquete, recursos in RECURSOS_DE_PAQUETES.items():
		if not (lib / paquete).is_dir():
			continue
		for recurso in recursos:
			if not (lib / recurso).is_file():
				problemas.append(
					f"Falta lib/{recurso}: el paquete {paquete} no funcionará bien "
					"(los paquetes con DLL o datos deben ir completos y fuera del zip)."
				)
	for paquete in PAQUETES_DESARROLLO:
		if (lib / paquete).exists():
			problemas.append(f"Herramienta de desarrollo incluida: lib/{paquete} (añádala a EXCLUDES).")
	return problemas


def verificar(destino: Path, ejecutable: str | None = None, ejecutable_jugar: str | None = None) -> list[str]:
	"""Devuelve la lista de problemas encontrados (vacía si todo está bien).

	:param destino: carpeta de la compilación (``build/entornolab``).
	:param ejecutable: nombre del ejecutable del Estudio; por defecto, el de ``version.py``.
	:param ejecutable_jugar: nombre del ejecutable del reproductor; por defecto, el de ``version.py``.
	"""
	if not destino.is_dir():
		return [f"No existe la carpeta de compilación: {destino}"]
	estudio, reproductor = ejecutables_por_defecto()
	ejecutables = (ejecutable or estudio, ejecutable_jugar or reproductor)
	problemas = _verificar_ejecutables(destino, ejecutables)
	problemas += _verificar_runtimes(destino)
	problemas += _verificar_bibliotecas(destino)
	problemas += _verificar_prohibidos(destino)
	problemas += _verificar_data(destino)
	problemas += _verificar_python3t(destino)
	problemas += _verificar_rutas(destino)
	return problemas


def _verificar_rutas(destino: Path) -> list[str]:
	"""Ninguna ruta ni dato del equipo de desarrollo dentro de la compilación (``tools/comprobar_rutas.py``).

	Mira el contenido de todo: ``.pyc`` (``co_filename``), ``library.zip``, metadatos
	``dist-info``, ``.mo``, ``data/``... El autor no quiere que el programa que se
	distribuye lleve su carpeta de usuario, la de sus proyectos ni su Python.
	"""
	if str(Path(__file__).resolve().parent) not in sys.path:
		sys.path.insert(0, str(Path(__file__).resolve().parent))
	import comprobar_rutas

	return [f"Rutas del equipo de desarrollo en la compilación: {hallazgo}" for hallazgo in comprobar_rutas.comprobar_carpeta(destino)]


def _verificar_python3t(destino: Path) -> list[str]:
	"""Comprueba que ``python3t.dll`` no redirige a una variante de Python que no viaja.

	Las extensiones «abi3t» de Python 3.15 (cryptography) enlazan con
	``python3t.dll``. Si esa DLL redirige a ``python3XXt.dll`` y esa no está en la
	carpeta, el cifrado de las fichas no carga en el equipo del usuario.
	"""
	dll = destino / "python3t.dll"
	if not dll.is_file():
		return []
	contenido = dll.read_bytes()
	variante = f"python{sys.version_info.major}{sys.version_info.minor}t."
	if variante.encode("ascii") in contenido and not (destino / f"{variante}dll").is_file():
		return [f"python3t.dll redirige a {variante}dll, que no viaja: el cifrado no cargaría (vuelva a compilar con setup_cx.py)"]
	return []


def comprobar_motores(destino: Path) -> int:
	"""Abre OpenAL (con HRTF) y BASS con las bibliotecas y los datos de la COMPILACIÓN, sin sonar.

	Lanza este mismo guion en otro proceso de Python aislado (``-I -S``: sin
	el entorno virtual ni la carpeta del proyecto) que solo ve
	``<destino>/lib``: carga los ``.pyc``, ``soft_oal.dll`` y ``bass.dll``
	que viajan en la distribución. Los motores se abren «en memoria», sin
	tarjeta de sonido. Los datos se copian a una carpeta temporal para que
	la compilación siga limpia.
	"""
	import subprocess
	import tempfile

	with tempfile.TemporaryDirectory(prefix="entornolab_motores_") as temporal:
		entorno = {clave: valor for clave, valor in os.environ.items() if clave not in ("APP_SIN_SONIDO", "PYTHONPATH", "PYTHONHOME")}
		resultado = subprocess.run(  # noqa: S603 - este mismo guion, con argumentos propios
			[sys.executable, "-I", "-S", str(Path(__file__).resolve()), ORDEN_MOTORES_INTERNA, str(destino), str(Path(temporal) / "data")],
			check=False,
			env=entorno,
			cwd=temporal,
		)
	return resultado.returncode


def _motores_en_proceso_aislado(destino: Path, datos: Path) -> int:
	"""Lo que hace :func:`comprobar_motores` dentro del proceso aislado."""
	import shutil

	lib = destino / "lib"
	sys.path[:0] = [str(lib), str(lib / "library.zip")]
	shutil.copytree(destino / "data", datos)
	os.environ["APP_DATA_DIR"] = str(datos)
	os.add_dll_directory(str(lib))
	from app.audio import fabrica  # type: ignore[import-not-found]  # el de la compilación

	if str(lib) not in str(fabrica.__file__):
		print(f"ERROR: se cargó app desde {fabrica.__file__}, no desde la compilación.")
		return 1
	fallos = 0
	perfiles = sorted(perfil.stem for perfil in (datos / "bin" / "openal" / "hrtf").glob("*.mhr"))
	for cabeza in ["", *perfiles[:1]]:
		motor = fabrica.crear_motor({"motor": "openal", "memoria": True, "cabeza": cabeza, "salida": "auriculares"})
		estado = motor.estado()
		correcto = type(motor).__name__ == "MotorOpenAL" and bool(estado.get("hrtf_activo"))
		if correcto:
			motor.renderizar(256)
		print(
			f"OpenAL {estado.get('version')} con el perfil «{cabeza or 'integrado'}»: "
			f"motor {type(motor).__name__}, HRTF {estado.get('estado_hrtf')} ({estado.get('perfil_hrtf')})."
		)
		motor.cerrar()
		fallos += 0 if correcto else 1
	motor = fabrica.crear_motor({"motor": "bass", "memoria": True})
	import basskit  # type: ignore[import-not-found]  # el de la compilación

	correcto = type(motor).__name__ == "MotorBass" and str(lib) in str(basskit.__file__)
	print(f"BASS {motor.estado().get('version')}: motor {type(motor).__name__}, basskit de {Path(basskit.__file__).parent}.")
	motor.cerrar()
	fallos += 0 if correcto else 1
	print("Motores de sonido de la compilación: correctos." if not fallos else f"Motores de sonido de la compilación: {fallos} fallos.")
	return 1 if fallos else 0


def _pasos_guion(motor: str) -> list[dict]:
	"""Los pasos del guion de comprobación: elegir la primera actividad del ejemplo, jugar un poco y comprobar."""
	pasos: list[dict] = [
		{"nota": "El ejemplo se abre en la lista de sus actividades: se elige la primera."},
		{"hasta": "pantalla", "texto": "Menu", "plazo": 120},
		{"accion": "menu_aceptar", "fotogramas": 2},
		{"hasta": "partida", "plazo": 120},
		{"accion": "avanzar", "fotogramas": 30},
		{"comprobar": "motor", "nombre": motor},
		{"comprobar": "sin_complementos_que_faltan"},
		{"comprobar": "sin_fallos"},
	]
	if motor == "openal":
		pasos.append({"comprobar": "hrtf"})
	pasos.append({"salir": True})
	return pasos


def comprobar_guion(destino: Path, motores: tuple[str, ...] = ("openal", "bass")) -> int:
	"""Ejecuta el reproductor COMPILADO en modo guion con cada motor de sonido, en memoria y sin ventana.

	Usa una copia temporal de ``<destino>/data`` (la compilación sigue limpia)
	y un entorno de ejemplo con sus complementos. Comprueba el código de
	salida y el informe: el motor que quedó (y el HRTF con OpenAL), los
	paquetes de sonido, los complementos y que se dijo algo. Devuelve 0 o 1.
	"""
	import json
	import shutil
	import subprocess
	import tempfile

	_estudio, reproductor = ejecutables_por_defecto()
	ejecutable = destino / reproductor
	if not ejecutable.is_file():
		print(f"ERROR: no existe {ejecutable}.")
		return 1
	ejemplos = destino / "data" / "ejemplos"
	ejemplo = ejemplos / EJEMPLO_GUION
	if not ejemplo.is_file():
		ejemplo = next(iter(sorted(ejemplos.glob("*.elab"))), ejemplo)
	if not ejemplo.is_file():
		print("ERROR: la compilación no trae ningún entorno de ejemplo.")
		return 1
	fallos = 0
	with tempfile.TemporaryDirectory(prefix="entornolab_guion_") as temporal:
		datos = Path(temporal) / "data"
		shutil.copytree(destino / "data", datos)
		for motor in motores:
			guion = Path(temporal) / f"guion_{motor}.json"
			informe = Path(temporal) / f"informe_{motor}.json"
			guion.write_text(json.dumps({"motor": motor, "pasos": _pasos_guion(motor)}, ensure_ascii=False), encoding="utf-8")
			entorno = {
				clave: valor
				for clave, valor in os.environ.items()
				if clave not in ("APP_SIN_SONIDO", "APP_GUION", "APP_GUION_MOTOR", "PYTHONPATH", "PYTHONHOME")
			}
			entorno["APP_DATA_DIR"] = str(datos)
			# La copia del ejemplo dentro de la data temporal: el reproductor no debe abrir nada de la compilación para escribir.
			copia = datos / "ejemplos" / ejemplo.name
			try:
				resultado = subprocess.run(  # noqa: S603 - el ejecutable de la compilación, con argumentos propios
					[str(ejecutable), "--guion", str(guion), "--informe", str(informe), str(copia)],
					check=False,
					env=entorno,
					cwd=str(destino),
					timeout=PLAZO_GUION,
				)
				codigo: int | None = resultado.returncode
			except subprocess.TimeoutExpired:
				codigo = None
			problemas: list[str] = []
			if codigo != 0:
				problemas.append(f"salió con el código {codigo}" if codigo is not None else f"no terminó en {PLAZO_GUION} s")
			datos_informe: dict = {}
			if informe.is_file():
				datos_informe = json.loads(informe.read_text(encoding="utf-8"))
				problemas += [str(fallo) for fallo in datos_informe.get("fallos", [])]
			else:
				problemas.append("no dejó el informe del guion (mire los registros jugar_*.log)")
			sonido = datos_informe.get("sonido", {})
			if datos_informe and sonido.get("motor") != motor:
				problemas.append(f"quedó el motor {sonido.get('motor')} en vez de {motor}")
			if datos_informe and not datos_informe.get("paquetes_sonido"):
				problemas.append("no encontró ningún paquete de sonidos")
			if datos_informe and datos_informe.get("complementos", {}).get("faltan"):
				problemas.append(f"faltan complementos: {', '.join(datos_informe['complementos']['faltan'])}")
			if datos_informe and not datos_informe.get("dicho"):
				problemas.append("no dijo nada")
			partida = (datos_informe.get("estado_final") or {}).get("partida") or {}
			detalle = f"motor {sonido.get('motor')} {sonido.get('version', '')}".strip()
			if motor == "openal":
				detalle += f", HRTF {sonido.get('estado_hrtf')} ({sonido.get('perfil_hrtf')})"
			detalle += f", {len(datos_informe.get('paquetes_sonido', []))} paquetes de sonidos, {datos_informe.get('complementos', {}).get('objetos', 0)} objetos"
			if partida:
				detalle += f", jugó «{partida.get('actividad')}» de «{partida.get('entorno')}»"
			if problemas:
				fallos += 1
				print(f"ERROR: {reproductor} con {motor}: " + "; ".join(problemas))
			else:
				print(f"{reproductor} en modo guion con {motor}: correcto ({detalle}).")
	print("Reproductor compilado en modo guion: correcto." if not fallos else f"Reproductor compilado en modo guion: {fallos} fallos.")
	return 1 if fallos else 0


def main(argumentos: list[str]) -> int:
	"""Punto de entrada de línea de órdenes."""
	if argumentos[:1] == [ORDEN_MOTORES_INTERNA]:
		return _motores_en_proceso_aislado(Path(argumentos[1]), Path(argumentos[2]))
	if ORDEN_GUION in argumentos:
		resto = [argumento for argumento in argumentos if argumento != ORDEN_GUION]
		destino = Path(resto[0]).resolve() if resto else CARPETA_POR_DEFECTO
		print(f"Comprobando {destino} en modo guion (sin ventana ni sonido)...", flush=True)
		return comprobar_guion(destino)
	motores = ORDEN_MOTORES in argumentos
	argumentos = [argumento for argumento in argumentos if argumento != ORDEN_MOTORES]
	if motores:
		destino = Path(argumentos[0]).resolve() if argumentos else CARPETA_POR_DEFECTO
		print(f"Comprobando los motores de sonido de {destino} (sin sonar)...", flush=True)
		return comprobar_motores(destino)
	destino = Path(argumentos[0]).resolve() if argumentos else CARPETA_POR_DEFECTO
	ejecutable = argumentos[1] if len(argumentos) > 1 else None
	ejecutable_jugar = argumentos[2] if len(argumentos) > 2 else None
	print(f"Verificando la compilación en {destino}...")
	problemas = verificar(destino, ejecutable, ejecutable_jugar)
	if problemas:
		print(f"Se encontraron {len(problemas)} problemas:")
		for problema in problemas:
			print(f"  - {problema}")
		return 1
	archivos = [archivo for archivo in destino.rglob("*") if archivo.is_file()]
	total = sum(archivo.stat().st_size for archivo in archivos)
	print(f"Compilación correcta y limpia: {len(archivos)} archivos, {_tamano_legible(total)}.")
	return 0


if __name__ == "__main__":
	sys.exit(main(sys.argv[1:]))
