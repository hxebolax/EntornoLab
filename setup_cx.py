"""Compilación de EntornoLab con cx_Freeze.

Uso (lo invoca ``entorno.bat compilar``)::

	python setup_cx.py build            versión final, sin consola
	python setup_cx.py build --debug    la misma, pero CON consola (para ver errores)

Genera una distribución portable de 64 bits en ``build/entornolab`` con:

- **Dos ejecutables** que comparten bibliotecas: ``EntornoLab.exe`` (el
  Estudio, ``main.py``) y ``EntornoLabJugar.exe`` (el reproductor,
  ``jugar.py``). Los dos sin consola (``base="gui"``).
- Los runtimes de Microsoft Visual C++ (``include_msvcr``), para que arranque
  en un Windows recién instalado sin el redistribuible.
- Los paquetes con DLL o datos propios FUERA del zip de bibliotecas (wx con
  sus catálogos, pygame con SDL2, numpy, sounddevice y soundfile con sus
  bibliotecas, accessible_output2 con las DLL de los lectores, cryptography,
  basskit con ``bass.dll``): dentro de un zip sus DLL no se pueden cargar.
- El motor de sonido BASS completo: el paquete ``basskit`` (la rueda recortada
  de ``__pip__``) viaja en ``lib/basskit`` con ``bass.dll`` y su licencia
  dentro, que es donde el propio paquete la busca también compilado.
- ``LICENSE.txt`` (GPL 3 con el permiso adicional para BASS) junto a los
  ejecutables, y los avisos de terceros en ``data/docs/licencias``.
- Una carpeta ``data`` LIMPIA por lista blanca: solo lo que hace falta para
  arrancar (OpenAL Soft con sus perfiles HRTF, sonidos de serie con su
  índice, traducciones compiladas ``.mo`` sin los ``.po``, manual y
  licencias, iconos, complementos y entornos de ejemplo). Nunca
  configuración, registros, fichas de alumnos, sesiones ni entornos del
  profesional, ni cachés de Python.
- Todos los paquetes de ``app`` nombrados uno a uno (se leen del disco), y
  ``certifi`` (con ``cacert.pem``) y ``markdown`` como obligatorios.

- Sin rutas del equipo que compila: ``replace_paths`` completo
  (:func:`rutas_a_reemplazar`), ``__LIBS__`` con rutas relativas
  (:func:`parchear_constantes_cx_freeze`) y sin ``direct_url.json`` ni
  ``RECORD`` en los metadatos (:func:`limpiar_metadatos`). Lo comprueba
  ``tools/comprobar_rutas.py`` desde ``tools/verificar_build.py``.

Antes de compilar, ``entorno.bat`` ejecuta ``tools/antes_de_compilar.py``
(compila las traducciones y comprueba que el repositorio no lleva rutas del
equipo). Después, este guion pasa ``tools/verificar_build.py``.
"""

from __future__ import annotations

import contextlib
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent

# ════════════════════════════════════════════════════════════════════════════
# CONFIGURACIÓN DEL PROYECTO
# ════════════════════════════════════════════════════════════════════════════

# Identificador y carpeta de salida (build/<NOMBRE_APP>). Coincide con ID_APLICACION.
NOMBRE_APP = "entornolab"
# Ejecutable del Estudio y del reproductor. Coinciden con EJECUTABLE_ESTUDIO y
# EJECUTABLE_REPRODUCTOR de app/core/version.py (lo comprueba una prueba).
EJECUTABLE = "EntornoLab.exe"
EJECUTABLE_JUGAR = "EntornoLabJugar.exe"
SCRIPT = "main.py"
SCRIPT_JUGAR = "jugar.py"
DESCRIPCION = "EntornoLab: aprender lugares antes de visitarlos"
DESCRIPCION_JUGAR = "EntornoLab Jugar: audiojuego de orientación"
AUTOR = ""
# Iconos opcionales; si no existen, se compila sin icono.
ICONO = RAIZ / "data" / "icons" / "app.ico"
ICONO_JUGAR = RAIZ / "data" / "icons" / "jugar.ico"

# Subcarpetas de data/ que SÍ viajan en la distribución. Todo lo demás se
# queda fuera por defecto (lista blanca: lo nuevo no se cuela sin querer).
DATA_DISTRIBUIBLE = [
	"bin",  # OpenAL Soft (openal/soft_oal.dll) y perfiles HRTF
	"sounds",  # sonidos de serie
	"locales",  # traducciones (data/locales/<idioma>/LC_MESSAGES)
	"docs",  # manual, lista de teclas, novedades y licencias de terceros (no la documentación de desarrollo)
	"icons",  # iconos de la aplicación
	"plugins",  # complementos de objetos incluidos de fábrica
	"ejemplos",  # entornos de ejemplo
]

# Carpetas de data/ que JAMÁS pueden aparecer en la distribución: datos del
# profesional, de sus alumnos o generados al usar la aplicación. Si alguien
# las añade a la lista blanca por error, la compilación se detiene.
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

# Archivos que nunca se copian aunque estén dentro de una carpeta distribuible.
PATRONES_EXCLUIDOS = (
	"__pycache__",
	"*.pyc",
	"*.pyo",
	"*.log",
	"*.jsonl",
	"*.tmp",
	"*.bak",
	"*.db",
	"*.db-wal",
	"*.db-shm",
	"*.sqlite",
	"*.key",
	"*.dat",
	".gitkeep",
	"desktop.ini",
	"Thumbs.db",
	".DS_Store",
	# Traducciones editables: la versión compilada lee solo el .mo (arranca más deprisa
	# y no depende de que el .po sea más antiguo que el .mo al copiarlos).
	"*.po",
	"*.pot",
)

# Archivos sueltos que se copian desde fuera de data/ (origen, destino).
ARCHIVOS_EXTRA: list[tuple[str, str]] = [
	# La licencia del programa (GPL 3 con el permiso adicional para BASS), junto a los ejecutables.
	("LICENSE", "LICENSE.txt"),
]

# Paquetes que cx_Freeze debe incluir completos (cargan módulos o datos de
# forma dinámica y su análisis no los detecta). Los obligatorios paran la
# compilación si faltan; los opcionales se añaden solo si están instalados.
PAQUETES = [
	"wx",
	"app",
	# Motor de sonido BASS: la rueda recortada de __pip__ (solo bass.dll, sin FFmpeg ni complementos).
	# Obligatorio: la distribución trae todos los motores. Lleva dentro data/dlls/x64/bass.dll.
	"basskit",
	# Certificados para https (actualizaciones y catálogo de complementos): viaja con su cacert.pem.
	"certifi",
	# Manual y ayuda en HTML navegable por encabezados (F1); carga sus extensiones por nombre.
	"markdown",
]
PAQUETES_OPCIONALES = [
	"pygame",  # reproductor y mandos (SDL2)
	"numpy",  # mezcla y síntesis de sonido
	"_sounddevice_data",  # PortAudio
	"_soundfile_data",  # libsndfile
	"accessible_output2",  # voz por lector de pantalla
	"libloader",  # lo usa accessible_output2 para cargar sus DLL
	"platform_utils",
	"cryptography",  # cifrado de las fichas
	"comtypes",  # SAPI por COM
	"win32com",
]
# Módulos sueltos (no son paquetes) que hay que nombrar uno a uno.
INCLUDES_OPCIONALES = ["sounddevice", "_sounddevice", "soundfile", "_soundfile", "pythoncom", "pywintypes"]
EXCLUDES = [
	"tkinter",
	"pydoc_data",
	# Herramientas de desarrollo que no deben viajar en el ejecutable.
	"pip",
	"pytest",
	"_pytest",
	"ruff",
	"cx_Freeze",
	"wheel",
	"setuptools",
	# Coloreado de código: solo lo trae el entorno de desarrollo (pytest); markdown funciona sin él.
	"pygments",
	# Ejemplos y pruebas de pygame: no los usa la aplicación.
	"pygame.examples",
	"pygame.tests",
	# No se excluye «unittest»: numpy y otras bibliotecas lo importan en algunas rutas.
]

# ════════════════════════════════════════════════════════════════════════════
# A PARTIR DE AQUÍ NO SUELE HACER FALTA TOCAR NADA
# ════════════════════════════════════════════════════════════════════════════

# La variable ENTORNOLAB_DESTINO_BUILD permite compilar en otra carpeta (para no pisar
# una compilación que se está usando); sin ella, build/<NOMBRE_APP> como siempre.
DESTINO = Path(os.environ.get("ENTORNOLAB_DESTINO_BUILD", "").strip() or RAIZ / "build" / NOMBRE_APP).resolve()


def leer_version() -> str:
	"""Lee APP_VERSION de app/core/version.py sin importar la aplicación.

	Importarla arrastraría wx solo para saber un número; con una expresión
	regular basta y no hay efectos secundarios.
	"""
	ruta = RAIZ / "app" / "core" / "version.py"
	try:
		texto = ruta.read_text(encoding="utf-8")
	except OSError:
		print(f"AVISO: no se encontró {ruta}; se usa la versión 0.0.0.")
		return "0.0.0"
	coincidencia = re.search(r"APP_VERSION\s*=\s*[\"']([^\"']+)[\"']", texto)
	return coincidencia.group(1) if coincidencia else "0.0.0"


def modulo_disponible(nombre: str) -> bool:
	"""Indica si un módulo está instalado en el entorno virtual."""
	import importlib.util

	try:
		return importlib.util.find_spec(nombre) is not None
	except ImportError, ValueError:
		return False


def _excluido(ruta: Path) -> bool:
	"""Indica si alguna parte de la ruta coincide con un patrón excluido."""
	return any(Path(parte).match(patron) for parte in ruta.parts for patron in PATRONES_EXCLUIDOS)


def archivos_de_data() -> list[tuple[str, str]]:
	"""Construye la lista ``include_files`` de data/ ARCHIVO A ARCHIVO.

	cx_Freeze copiaría una carpeta entera tal cual (con ``__pycache__``,
	registros o bases de datos que hubiera dentro); recorriéndola a mano se
	filtra cada archivo con ``PATRONES_EXCLUIDOS``.
	"""
	prohibidas = DATA_PROHIBIDO.intersection(DATA_DISTRIBUIBLE)
	if prohibidas:
		raise SystemExit("ERROR: DATA_DISTRIBUIBLE incluye carpetas con datos personales: " + ", ".join(sorted(prohibidas)))
	data = RAIZ / "data"
	resultado: list[tuple[str, str]] = []
	for nombre in DATA_DISTRIBUIBLE:
		carpeta = data / nombre
		if not carpeta.is_dir():
			print(f"Aviso: data/{nombre} no existe; no se incluye.")
			continue
		for archivo in sorted(carpeta.rglob("*")):
			if not archivo.is_file():
				continue
			relativo = archivo.relative_to(RAIZ)
			if _excluido(relativo):
				continue
			resultado.append((str(archivo), relativo.as_posix()))
	return resultado


def comprobar_basskit() -> None:
	"""Detiene la compilación si basskit no está instalado o le falta ``bass.dll``.

	cx_Freeze copia el paquete tal como esté en el entorno virtual: si la DLL no está dentro, la
	distribución saldría con un motor de sonido que no arranca, y es mejor saberlo aquí.
	"""
	import importlib.util

	try:
		especificacion = importlib.util.find_spec("basskit")
	except ImportError, ValueError:
		especificacion = None
	if especificacion is None or not especificacion.submodule_search_locations:
		raise SystemExit(
			"ERROR: falta el paquete basskit (motor de sonido BASS). Ejecute «entorno.bat instalar»: instala la rueda de __pip__."
		)
	carpeta = Path(next(iter(especificacion.submodule_search_locations)))
	dll = carpeta / "data" / "dlls" / "x64" / "bass.dll"
	if not dll.is_file():
		raise SystemExit(f"ERROR: el paquete basskit instalado no trae {dll}. Reinstale la rueda de __pip__ con «entorno.bat instalar».")


def archivos_extra() -> list[tuple[str, str]]:
	"""Valida y devuelve los archivos sueltos de ``ARCHIVOS_EXTRA``."""
	resultado = []
	for origen, destino in ARCHIVOS_EXTRA:
		ruta = RAIZ / origen
		if ruta.exists():
			resultado.append((str(ruta), destino))
		else:
			print(f"Aviso: no se encontró {origen}; no se incluye.")
	return resultado


def limpiar_destino() -> None:
	"""Borra la compilación anterior para que no se cuelen restos.

	Si la copia compilada se ejecutó para probarla, su data/ contiene ya
	configuración, registros y fichas: compilar encima los arrastraría a la
	distribución.
	"""
	if DESTINO.exists():
		print(f"Limpiando la compilación anterior: {DESTINO}")
		shutil.rmtree(DESTINO, ignore_errors=False)


def subpaquetes_de_app() -> list[str]:
	"""Todos los paquetes de ``app`` (``app.actividades``, ``app.reproductor.pantallas``...).

	«app» ya los incluye, pero nombrarlos uno a uno hace que cx_Freeze
	pare con un error claro si alguno no se puede importar al compilar, en
	lugar de dejarlo fuera en silencio. Se leen del disco para que un paquete
	nuevo no haya que acordarse de añadirlo aquí.
	"""
	carpeta_app = RAIZ / "app"
	resultado = []
	for inicio in sorted(carpeta_app.rglob("__init__.py")):
		relativo = inicio.parent.relative_to(RAIZ)
		if "__pycache__" in relativo.parts:
			continue
		resultado.append(".".join(relativo.parts))
	return resultado


def paquetes_finales() -> tuple[list[str], list[str]]:
	"""Paquetes e ``includes`` que se pasan a cx_Freeze, según lo que esté instalado."""
	paquetes = list(PAQUETES)
	paquetes += [nombre for nombre in subpaquetes_de_app() if nombre not in paquetes]
	for opcional in PAQUETES_OPCIONALES:
		if modulo_disponible(opcional):
			paquetes.append(opcional)
		else:
			print(f"Aviso: el paquete opcional {opcional} no está instalado; no se incluye.")
	includes = [modulo for modulo in INCLUDES_OPCIONALES if modulo_disponible(modulo)]
	return paquetes, includes


def python3t_apunta_a_variante(ruta: Path) -> bool:
	"""True si la ``python3t.dll`` de ``ruta`` redirige a la variante sin bloqueo global (``python3XXt``).

	Una ``python3t.dll`` es solo una tabla de redirecciones: cada función dice
	en qué DLL está de verdad. Basta con buscar ese nombre en el fichero.
	"""
	version = f"python{sys.version_info.major}{sys.version_info.minor}"
	return f"{version}t.".encode("ascii") in ruta.read_bytes()


def corregir_python3t() -> None:
	"""Da a la compilación una ``python3t.dll`` que redirige al Python normal.

	Por qué: desde Python 3.15 hay extensiones «abi3t» (la de cryptography, por
	ejemplo) que valen para el Python normal y para la variante sin bloqueo
	global, y enlazan con ``python3t.dll``. Si en la carpeta de Python del equipo
	que compila conviven las dos variantes, la ``python3t.dll`` que hay es la de
	la variante y redirige a ``python3XXt.dll``, que no viaja con la aplicación:
	el cifrado de las fichas no carga («DLL load failed while importing _rust»).
	La ``python3.dll`` del Python normal exporta las mismas funciones y redirige
	a ``python3XX.dll``, que sí viaja; copiada con el nombre ``python3t.dll``
	resuelve el problema. Si el Python que compila es la propia variante, no se
	toca nada.
	"""
	con_bloqueo_global = sys._is_gil_enabled() if hasattr(sys, "_is_gil_enabled") else True
	if not con_bloqueo_global:
		return
	destino = DESTINO / "python3t.dll"
	if not destino.is_file() or not python3t_apunta_a_variante(destino):
		return
	origen = Path(sys.base_prefix) / "python3.dll"
	if not origen.is_file():
		raise SystemExit(f"Falta {origen}: hace falta para que el cifrado funcione en la versión compilada.")
	shutil.copy2(origen, destino)
	print(f"python3t.dll sustituida por {origen} (redirige al Python normal).")


def rutas_a_reemplazar() -> list[tuple[str, str]]:
	"""``replace_paths`` de cx_Freeze: que ningún ``.pyc`` lleve una ruta del equipo que compila.

	Por qué: cada módulo compilado guarda en ``co_filename`` la ruta de su fuente,
	y esa ruta sale en las trazas y queda escrita dentro del ``.pyc``. Con
	``("*", "")`` cx_Freeze la deja relativa a la carpeta de su paquete raíz,
	pero se salta los paquetes sin ``__init__.py`` (paquetes de espacio de
	nombres como ``win32comext``): sus ``.pyc`` viajaban con la ruta completa
	del entorno virtual. cx_Freeze prueba las parejas por orden y se queda con
	la primera que sirve; por eso, tras «*», van las carpetas de las que puede
	colgar cualquier módulo: las de paquetes del entorno virtual y del Python
	base, la biblioteca estándar, el propio Python y el proyecto. Técnica del
	autor (Puerto Bravo, ``setup_cx.py``), completada aquí.
	"""
	import site

	carpetas: list[Path] = []
	# Primero las de paquetes (las más profundas): así queda «win32comext/...» y no «Lib/site-packages/win32comext/...».
	with contextlib.suppress(AttributeError):
		carpetas += [Path(carpeta) for carpeta in site.getsitepackages() if Path(carpeta).name.lower() == "site-packages"]
	carpetas += [
		Path(sys.prefix) / "Lib" / "site-packages",
		Path(sys.base_prefix) / "Lib" / "site-packages",
		Path(sys.base_prefix) / "Lib",
		Path(sys.base_prefix) / "DLLs",
		RAIZ,
		Path(sys.prefix),
		Path(sys.base_prefix),
	]
	reemplazos: list[tuple[str, str]] = [("*", "")]
	vistas: set[str] = set()
	for carpeta in carpetas:
		texto = str(carpeta.resolve())
		if texto.lower() not in vistas:
			vistas.add(texto.lower())
			reemplazos.append((texto, ""))
	return reemplazos


def _libs_relativas(valor: str) -> str:
	"""Convierte las carpetas de DLL de ``__LIBS__`` en relativas a ``lib`` y quita las repetidas.

	cx_Freeze guarda en la constante ``__LIBS__`` (``BUILD_CONSTANTS`` dentro de
	``library.zip``) las carpetas con DLL de los módulos que van en el zip
	(``sounddevice``, ``soundfile``, pywin32), pero las escribe ABSOLUTAS: las del
	entorno virtual de quien compila. Así la ruta viajaba con el programa y,
	además, en el propio equipo del autor el ejecutable cargaba DLL del entorno
	virtual en lugar de las suyas (lo que escondería una DLL que falta). Al
	arrancar se resuelven con ``os.path.join(sys.prefix, "lib", entrada)``: con
	la ruta relativa al ``site-packages`` apuntan a la copia que viaja en ``lib``.
	"""
	bases = [carpeta for carpeta, _vacio in rutas_a_reemplazar()[1:] if Path(carpeta).name.lower() == "site-packages"]
	resultado: list[str] = []
	for entrada in valor.split(os.pathsep):
		if not entrada:
			continue
		relativa = entrada
		ruta = Path(entrada)
		if ruta.is_absolute():
			for base in bases:
				with contextlib.suppress(ValueError):
					relativa = ruta.resolve().relative_to(Path(base)).as_posix()
					break
			else:
				# Ninguna base la contiene: mejor no dar la carpeta que dar una ruta del equipo que compila.
				print(f"Aviso: se omite la carpeta de DLL {ruta.name} de __LIBS__ (no cuelga de ningún site-packages).")
				continue
		if relativa not in resultado:
			resultado.append(relativa)
	return os.pathsep.join(resultado)


def parchear_constantes_cx_freeze() -> None:
	"""Hace que cx_Freeze guarde ``__LIBS__`` con rutas relativas (ver :func:`_libs_relativas`)."""
	from cx_Freeze.finder import ModuleFinder

	original = ModuleFinder.add_constant
	if getattr(original, "_entornolab", False):
		return

	def add_constant(self: ModuleFinder, name: str, value: str) -> None:
		original(self, name, _libs_relativas(value) if name == "__LIBS__" else value)

	add_constant._entornolab = True  # type: ignore[attr-defined]
	ModuleFinder.add_constant = add_constant  # type: ignore[method-assign]


# Ficheros de los metadatos ``*.dist-info`` que se retiran de ``library.zip``:
# - ``direct_url.json`` dice desde qué carpeta se instaló el paquete (basskit
#   llevaba ``file:///<carpeta del proyecto>/__pip__/...``: la ruta del equipo que compila);
# - ``RECORD`` es la lista de ficheros instalados en el entorno virtual, que nada usa en ejecución.
# Se conservan ``METADATA`` (``importlib.metadata.version`` y el paquete de
# diagnóstico leen la versión) y ``entry_points.txt`` (markdown busca ahí sus extensiones).
METADATOS_RETIRADOS = ("direct_url.json", "RECORD")


def limpiar_metadatos() -> None:
	"""Rehace ``lib/library.zip`` sin los metadatos que pueden llevar rutas del equipo que compila."""
	import zipfile

	biblioteca = DESTINO / "lib" / "library.zip"
	if not biblioteca.is_file():
		return
	temporal = biblioteca.with_suffix(".zip.tmp")
	retirados = 0
	with zipfile.ZipFile(biblioteca) as origen, zipfile.ZipFile(temporal, "w", zipfile.ZIP_DEFLATED) as destino:
		for miembro in origen.infolist():
			partes = miembro.filename.split("/")
			if len(partes) == 2 and partes[0].endswith(".dist-info") and partes[1] in METADATOS_RETIRADOS:
				retirados += 1
				continue
			destino.writestr(miembro, origen.read(miembro))
	temporal.replace(biblioteca)
	print(f"Metadatos retirados de library.zip: {retirados} ficheros ({', '.join(METADATOS_RETIRADOS)}).")


def principal() -> None:
	"""Prepara las opciones y lanza la compilación."""
	from cx_Freeze import Executable, setup

	parchear_constantes_cx_freeze()

	modo_debug = "--debug" in sys.argv
	if modo_debug:
		sys.argv.remove("--debug")
	compilando = any(orden.startswith("build") for orden in sys.argv[1:])
	# setuptools deja entornolab.egg-info en la raíz al leer pyproject.toml; si no
	# estaba antes de compilar, se borra después para no dejar restos en el proyecto.
	egg_info = RAIZ / f"{NOMBRE_APP}.egg-info"
	habia_egg_info = egg_info.exists()
	if compilando:
		comprobar_basskit()
		limpiar_destino()

	paquetes, includes = paquetes_finales()
	opciones_build = {
		"build_exe": str(DESTINO),
		"packages": paquetes,
		"includes": includes,
		"excludes": EXCLUDES,
		"include_files": archivos_de_data() + archivos_extra(),
		# Nada dentro del zip de bibliotecas: los paquetes con DLL o datos (wx,
		# pygame, numpy, accessible_output2, cryptography, basskit...) no funcionan desde un zip.
		"zip_include_packages": [],
		"zip_exclude_packages": ["*"],
		# Runtimes de Visual C++ junto a los ejecutables (vcruntime140.dll,
		# vcruntime140_1.dll, msvcp140*.dll...): arranca sin instalar el redistribuible.
		"include_msvcr": True,
		# Las trazas muestran rutas relativas (app/ui/ventana.py) en lugar de las
		# de la máquina donde se compiló: más legibles y sin datos personales.
		# «*» no basta: lo de un paquete sin __init__.py (win32comext) se quedaba
		# con la ruta completa del entorno virtual (ver rutas_a_reemplazar).
		"replace_paths": rutas_a_reemplazar(),
		# optimize=2 elimina las docstrings y rompe bibliotecas que las leen.
		"optimize": 1,
	}
	# "gui" = sin consola. En modo --debug, con consola para ver los errores.
	base = None if modo_debug else "gui"
	ejecutables = [
		Executable(
			script=str(RAIZ / SCRIPT),
			base=base,
			target_name=EJECUTABLE,
			icon=str(ICONO) if ICONO.is_file() else None,
			copyright=AUTOR or None,
		),
		Executable(
			script=str(RAIZ / SCRIPT_JUGAR),
			base=base,
			target_name=EJECUTABLE_JUGAR,
			icon=str(ICONO_JUGAR) if ICONO_JUGAR.is_file() else (str(ICONO) if ICONO.is_file() else None),
			copyright=AUTOR or None,
		),
	]
	setup(
		name=NOMBRE_APP,
		version=leer_version(),
		description=DESCRIPCION,
		author=AUTOR or None,
		options={"build_exe": opciones_build},
		executables=ejecutables,
	)
	if not habia_egg_info and egg_info.is_dir():
		shutil.rmtree(egg_info, ignore_errors=True)
	if compilando:
		corregir_python3t()
		limpiar_metadatos()

	# Solo tras una compilación real: comprueba que la distribución está completa y limpia.
	verificador = RAIZ / "tools" / "verificar_build.py"
	if compilando and verificador.is_file():
		resultado = subprocess.run(  # noqa: S603 - herramienta propia del proyecto
			[sys.executable, str(verificador), str(DESTINO), EJECUTABLE, EJECUTABLE_JUGAR],
			check=False,
		)
		if resultado.returncode != 0:
			raise SystemExit("La verificación de la compilación ha fallado; revise los mensajes anteriores.")


if __name__ == "__main__":
	principal()
