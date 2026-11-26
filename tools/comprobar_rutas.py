"""Busca rutas y datos del equipo de DESARROLLO en el repositorio o en una compilación.

Por qué existe: el autor no quiere que EntornoLab muestre ni guarde nada de su
equipo (su carpeta de usuario, la carpeta de sus proyectos, la de su Python o
su entorno virtual, su nombre de usuario ni su correo). Esas cadenas se cuelan
sin querer: en una prueba que apunta a una carpeta propia, en una receta
generada con la ruta de las fuentes, en la cabecera de un ``.pot``, en los
``.pyc`` compilados (``co_filename``), en los metadatos ``dist-info`` de los
paquetes (``RECORD``, ``direct_url.json``)... Esta herramienta las busca en el
CONTENIDO de cada fichero (texto y binarios, y dentro de los ZIP: ``.zip``,
``.whl``, ``.elab``, ``library.zip``) y falla si encuentra alguna.

Las cadenas no se escriben aquí: se calculan en el equipo donde se ejecuta
(``os.path.expanduser("~")``, el nombre de usuario, la carpeta que contiene el
proyecto, ``sys.base_prefix``, ``sys.prefix``, la carpeta temporal y el correo
de ``git config``), y se completan con patrones genéricos (cualquier
``C:\\Users\\<nombre>`` concreto, un Python instalado en ``C:\\Python3XX``, la
carpeta temporal de los agentes...). Así sirve igual en el equipo del autor,
en el de otra persona que colabore y en la integración continua.

Uso::

	python tools/comprobar_rutas.py                         el repositorio (lo que subiría git)
	python tools/comprobar_rutas.py --build build/entornolab una compilación
	python tools/comprobar_rutas.py --zip dist/EntornoLab-1.0.zip
	python tools/comprobar_rutas.py --carpeta <carpeta>      cualquier carpeta (todo su contenido)

Una línea de texto que necesite de verdad una de esas cadenas (un ejemplo
ficticio en una prueba, por ejemplo) se acepta si lleva el marcador
``comprobar_rutas: permitido`` en la misma línea. En binarios no hay excepción.

Devuelve 0 si está limpio y 1 si encuentra algo (lo usan ``verificar_build.py``,
``antes_de_compilar.py`` y ``tests/test_sin_rutas_locales.py``).

Solo biblioteca estándar.
"""

from __future__ import annotations

import getpass
import io
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from collections.abc import Iterable, Iterator
from dataclasses import dataclass
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
MARCADOR_PERMITIDO = "comprobar_rutas: permitido"
# Extensiones que se abren como ZIP para mirar dentro (los entornos .elab y las ruedas .whl lo son).
EXTENSIONES_ZIP = {".zip", ".whl", ".elab", ".elabpack", ".elabc"}
# Carpetas que nunca se recorren al mirar una carpeta suelta (no forman parte de lo que se distribuye ni se sube).
CARPETAS_IGNORADAS = {".git", ".venv", "venv", "__pycache__", ".pytest_cache", ".ruff_cache", "node_modules"}
# Nombres de cuenta tan genéricos que buscarlos sueltos daría falsos positivos (se siguen buscando dentro de rutas).
NOMBRES_GENERICOS = {
	"user",
	"usuario",
	"admin",
	"administrador",
	"administrator",
	"runner",
	"runneradmin",
	"default",
	"public",
	"test",
	"root",
}
# Carpetas de la carpeta de cuentas de Windows que no son de una persona.
CUENTAS_COMUNES = {"public", "default", "default user", "all users", "usuario", "runneradmin", "user", "username", "nombre", "name"}
# Binarios nativos de terceros: suelen llevar la ruta de depuración (PDB) del equipo de QUIEN LOS COMPILÓ
# (accessible_output2/lib/SAAPI32.dll lleva la de un programador de Serotek). No son del autor y no se pueden
# cambiar: en ellos solo se buscan las cadenas de ESTE equipo, no los patrones genéricos.
EXTENSIONES_NATIVAS = {".dll", ".pyd", ".exe"}
# Descripciones de las cadenas que se buscan como palabra suelta (no dentro de otra: el nombre
# de usuario puede formar parte, a propósito, del nombre público del autor en GitHub).
SUELTAS = {"nombre de usuario", "nombre del equipo", "carpeta de los proyectos (nombre)"}

# Patrones genéricos: valen para cualquier equipo de desarrollo, no solo para el actual.
PATRONES_GENERICOS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
	# Carpeta de una cuenta concreta de Windows (con \, con / o con \\ como en un JSON).
	# No cuentan los marcadores (<usuario>, %USERNAME%, {usuario}, *) ni las cuentas comunes.
	(
		"carpeta de usuario concreta",
		re.compile(rb"(?i)\b[A-Z]:(?:\\\\|\\|/)(?:Users|Usuarios|Documents and Settings)(?:\\\\|\\|/)([A-Za-z0-9_.\- ]{2,40})"),
	),
	# Un Python instalado en la raíz de una unidad: es el del equipo que compiló.
	("Python del equipo de desarrollo", re.compile(rb"(?i)\b[A-Z]:(?:\\\\|\\|/)Python3\d{1,2}\b")),
	# La carpeta de trabajo temporal de los agentes que ayudan a programar.
	("carpeta temporal de un agente", re.compile(rb"(?i)(?:\\\\|\\|/)Temp(?:\\\\|\\|/)claude\b")),
	("carpeta temporal de un agente", re.compile(rb"(?i)\bscratchpad\b")),  # comprobar_rutas: permitido
)
# Palabras (en minúsculas) sin las que el patrón genérico correspondiente no puede aparecer.
PISTAS: dict[str, tuple[bytes, ...]] = {
	"carpeta de usuario concreta": (b"users", b"usuarios", b"documents and settings"),
	"Python del equipo de desarrollo": (b"python3",),
	"carpeta temporal de un agente": (b"claude", b"scratch"),
}


@dataclass(frozen=True)
class Hallazgo:
	"""Una aparición de algo del equipo de desarrollo dentro de un fichero."""

	fichero: str
	linea: int | None
	que: str
	fragmento: str

	def __str__(self) -> str:
		donde = f"{self.fichero}:{self.linea}" if self.linea else self.fichero
		return f"{donde}: {self.que} → {self.fragmento}"


def _git_correo() -> str:
	"""Correo de ``git config user.email`` (vacío si no hay git o no está configurado)."""
	try:
		resultado = subprocess.run(  # noqa: S603 S607 - git del sistema, solo lectura
			["git", "-C", str(RAIZ), "config", "user.email"],
			capture_output=True,
			text=True,
			timeout=15,
			check=False,
			creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
		)
	except OSError, subprocess.SubprocessError:
		return ""
	return resultado.stdout.strip()


def _variantes(ruta: str) -> set[str]:
	"""La misma ruta con ``\\``, con ``/`` y con ``\\\\`` (como queda escrita dentro de un JSON)."""
	normal = ruta.rstrip("\\/")
	return {normal, normal.replace("\\", "/"), normal.replace("/", "\\"), normal.replace("/", "\\").replace("\\", "\\\\")}


def cadenas_del_equipo(raiz: Path = RAIZ) -> list[tuple[str, str]]:
	"""Las cadenas concretas de ESTE equipo que no deben aparecer: (descripción, cadena).

	Se calculan al vuelo para no escribir en el código ninguna ruta real. Las
	demasiado cortas (una unidad ``C:\\``) o genéricas se descartan porque
	darían falsos positivos en cualquier texto.
	"""
	candidatas: list[tuple[str, str]] = []
	casa = os.path.expanduser("~")
	if casa and casa != "~":
		candidatas.append(("carpeta de usuario", casa))
	padre = raiz.resolve().parent
	if len(str(padre)) > 3:
		candidatas.append(("carpeta de los proyectos del desarrollador", str(padre)))
	for descripcion, ruta in (
		("Python del desarrollador", sys.base_prefix),
		("entorno virtual", sys.prefix),
		("carpeta temporal", tempfile.gettempdir()),
	):
		if ruta and len(ruta) > 3:
			candidatas.append((descripcion, ruta))
	for variable in ("USERPROFILE", "APPDATA", "LOCALAPPDATA", "TEMP", "TMP"):
		valor = os.environ.get(variable, "")
		if len(valor) > 3:
			candidatas.append((f"%{variable}%", valor))
	resultado: list[tuple[str, str]] = []
	vistas: set[str] = set()
	for descripcion, ruta in candidatas:
		# El propio proyecto puede vivir dentro de la carpeta de usuario o de la temporal: no se busca la raíz del proyecto (sale en muchos sitios legítimos como ruta relativa).
		for variante in _variantes(ruta):
			if variante.lower() not in vistas:
				vistas.add(variante.lower())
				resultado.append((descripcion, variante))
	try:
		usuario = getpass.getuser()
	except OSError, KeyError:
		usuario = os.environ.get("USERNAME", "")
	nombre_proyecto = raiz.resolve().name.lower()
	sueltas = [("nombre de usuario", usuario), ("nombre del equipo", os.environ.get("COMPUTERNAME", ""))]
	# El nombre de la carpeta que contiene los proyectos delata la ruta aunque cambie la unidad (el
	# autor tiene proyectos en dos unidades con la misma carpeta). No vale si es el propio proyecto.
	nombre_padre = padre.name
	# Un nombre corriente (Temp, source, Documentos...) aparece en cualquier texto y no delata a
	# nadie: buscarlo como palabra daría una «fuga» en cada mención a data/temp. Solo se busca un
	# nombre propio, el que eligió la persona para su carpeta de proyectos. En una carpeta temporal tampoco: es de pruebas o de un clon.
	genericas = {
		"temp",
		"tmp",
		"source",
		"sources",
		"src",
		"repos",
		"repo",
		"git",
		"github",
		"code",
		"codigo",
		"dev",
		"desarrollo",
		"projects",
		"proyectos",
		"documents",
		"documentos",
		"desktop",
		"escritorio",
		"downloads",
		"descargas",
		"home",
		"users",
		"usuarios",
		"work",
		"trabajo",
		"build",
		"programas",
		"program files",
		"python",
		"workspace",
		"a",
	}
	en_temporal = str(padre).lower().startswith(tempfile.gettempdir().lower())
	if (
		len(nombre_padre) >= 4
		and nombre_padre.lower() not in genericas
		and not en_temporal
		and nombre_padre.lower() not in nombre_proyecto
		and nombre_proyecto not in nombre_padre.lower()
	):
		# En cualquier unidad: «X:\<carpeta>» (con \, / o \\).
		for separador in ("\\", "/", "\\\\"):
			variante = f":{separador}{nombre_padre}"
			if variante.lower() not in vistas:
				vistas.add(variante.lower())
				resultado.append(("carpeta de los proyectos en otra unidad", variante))
		sueltas.append(("carpeta de los proyectos (nombre)", nombre_padre))
	correo = _git_correo()
	if correo:
		sueltas.append(("correo del desarrollador", correo))
	for descripcion, valor in sueltas:
		if len(valor) >= 4 and valor.lower() not in NOMBRES_GENERICOS and valor.lower() not in vistas:
			vistas.add(valor.lower())
			resultado.append((descripcion, valor))
	return resultado


@dataclass(frozen=True)
class Aguja:
	"""Una cadena del equipo ya preparada para buscarla en bytes, sin distinguir mayúsculas."""

	que: str
	bytes_bajos: bytes
	suelta: bool
	# Solo en ficheros de texto: la palabra es además el nombre de un módulo de Python
	# (la biblioteca estándar tiene un módulo de broma con un nombre corriente: python3XX.dll lo lleva
	# dentro y no tiene que ver con nadie).
	solo_texto: bool = False


def _patrones(cadenas: Iterable[tuple[str, str]]) -> list[Aguja]:
	"""Prepara cada cadena del equipo en UTF-8 y UTF-16 (los recursos de los .exe y .dll van en UTF-16).

	Se buscan con ``bytes.find`` sobre el contenido en minúsculas, no con expresiones
	regulares: el repositorio tiene miles de ficheros y así la comprobación tarda segundos.
	"""
	agujas: list[Aguja] = []
	modulos = getattr(sys, "stdlib_module_names", frozenset())
	for descripcion, cadena in cadenas:
		suelta = descripcion in SUELTAS
		agujas.append(Aguja(descripcion, cadena.lower().encode("utf-8"), suelta, suelta and cadena.lower() in modulos))
		if not suelta:
			agujas.append(Aguja(descripcion, cadena.lower().encode("utf-16-le"), False))
	return agujas


def _apariciones(bajo: bytes, aguja: Aguja) -> Iterator[tuple[int, int]]:
	"""Posiciones (inicio, fin) de la aguja; las sueltas solo como palabra completa."""
	posicion = bajo.find(aguja.bytes_bajos)
	while posicion >= 0:
		fin = posicion + len(aguja.bytes_bajos)
		antes = bajo[posicion - 1 : posicion] if posicion else b""
		despues = bajo[fin : fin + 1]
		# Pegada a otra letra o cifra es otra palabra (el nombre público del autor en GitHub contiene su
		# nombre de usuario y no lo delata); con «_», «-» o «\» al lado sigue siendo el nombre de usuario.
		if not aguja.suelta or not (antes.isalnum() or despues.isalnum()):
			yield posicion, fin
		posicion = bajo.find(aguja.bytes_bajos, posicion + 1)


def _linea_de(datos: bytes, posicion: int) -> tuple[int, bytes]:
	"""Número de línea (desde 1) y contenido de la línea donde está ``posicion``."""
	inicio = datos.rfind(b"\n", 0, posicion) + 1
	fin = datos.find(b"\n", posicion)
	if fin < 0:
		fin = len(datos)
	return datos.count(b"\n", 0, posicion) + 1, datos[inicio:fin]


def _es_texto(datos: bytes) -> bool:
	"""Heurística: sin bytes nulos en el primer bloque y decodificable como UTF-8."""
	muestra = datos[:8192]
	if b"\x00" in muestra:
		return False
	try:
		muestra.decode("utf-8")
	except UnicodeDecodeError as error:
		# Un carácter multibyte cortado al final de la muestra no lo hace binario.
		return error.start >= len(muestra) - 3
	return True


def _posiciones(datos: bytes, bajo: bytes, agujas: list[Aguja], texto: bool, nativo: bool) -> Iterator[tuple[str, int, int]]:
	"""Todas las apariciones (qué, inicio, fin): primero los patrones genéricos y luego las cadenas del equipo."""
	for que, patron in () if nativo else PATRONES_GENERICOS:
		# Pista barata antes de la expresión regular: casi ningún fichero contiene la palabra clave.
		if not any(pista in bajo for pista in PISTAS[que]):
			continue
		for coincidencia in patron.finditer(datos):
			if que == "carpeta de usuario concreta" and coincidencia.group(1).decode("latin-1").strip(" .").lower() in CUENTAS_COMUNES:
				continue
			yield que, coincidencia.start(), coincidencia.end()
	for aguja in agujas:
		if aguja.solo_texto and not texto:
			continue
		for inicio, fin in _apariciones(bajo, aguja):
			yield aguja.que, inicio, fin


def buscar_en_bytes(nombre: str, datos: bytes, agujas: list[Aguja]) -> list[Hallazgo]:
	"""Busca en el contenido de un fichero. En texto, respeta el marcador de línea permitida."""
	texto = _es_texto(datos)
	nativo = Path(nombre.split("!")[-1]).suffix.lower() in EXTENSIONES_NATIVAS
	bajo = datos.lower()
	hallazgos: list[Hallazgo] = []
	vistos: set[tuple[int | None, str]] = set()
	for que, inicio, fin in _posiciones(datos, bajo, agujas, texto, nativo):
		linea: int | None = None
		if texto:
			linea, contenido = _linea_de(datos, inicio)
			if MARCADOR_PERMITIDO.encode() in contenido:
				continue
		# En un binario basta con decir una vez qué hay; en un texto, una vez por línea.
		if (linea, que) in vistos:
			continue
		vistos.add((linea, que))
		fragmento = datos[max(0, inicio - 30) : fin + 30].decode("utf-8", errors="replace")
		fragmento = re.sub(r"[\x00-\x1f]+", " ", fragmento).strip()
		hallazgos.append(Hallazgo(nombre, linea, que, fragmento))
	return hallazgos


def buscar_en_fichero(ruta: Path, nombre: str, patrones: list[Aguja]) -> list[Hallazgo]:
	"""Busca en un fichero y, si es un ZIP, también en cada fichero que lleva dentro."""
	try:
		datos = ruta.read_bytes()
	except OSError as error:
		return [Hallazgo(nombre, None, "no se pudo leer", str(error))]
	return _buscar_en_datos(nombre, datos, ruta.suffix.lower(), patrones)


def _buscar_en_datos(nombre: str, datos: bytes, extension: str, patrones: list[Aguja]) -> list[Hallazgo]:
	hallazgos = buscar_en_bytes(nombre, datos, patrones)
	if extension in EXTENSIONES_ZIP or (datos[:4] == b"PK\x03\x04" and extension not in {".docx", ".xlsx", ".pptx"}):
		try:
			with zipfile.ZipFile(io.BytesIO(datos)) as zip_:
				for miembro in zip_.infolist():
					if miembro.is_dir():
						continue
					interno = f"{nombre}!{miembro.filename}"
					# El nombre del miembro también cuenta: un ZIP puede guardar rutas absolutas.
					hallazgos += buscar_en_bytes(interno + " (nombre)", miembro.filename.encode("utf-8"), patrones)
					hallazgos += _buscar_en_datos(interno, zip_.read(miembro), Path(miembro.filename).suffix.lower(), patrones)
		except zipfile.BadZipFile:
			pass  # no era un ZIP de verdad (un .elab dañado a propósito en las pruebas): ya se buscó en sus bytes
	return hallazgos


def ficheros_del_repositorio(raiz: Path = RAIZ) -> list[Path]:
	"""Lo que subiría git: los ficheros versionados y los nuevos que no ignora ``.gitignore``."""
	resultado = subprocess.run(  # noqa: S603 S607 - git del sistema, solo lectura
		["git", "-C", str(raiz), "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
		capture_output=True,
		check=False,
		timeout=120,
		creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
	)
	if resultado.returncode != 0:
		raise RuntimeError(f"git ls-files falló: {resultado.stderr.decode('utf-8', errors='replace').strip()}")
	nombres = [nombre for nombre in resultado.stdout.decode("utf-8").split("\0") if nombre]
	return [raiz / nombre for nombre in nombres if (raiz / nombre).is_file()]


def ficheros_de_carpeta(carpeta: Path) -> Iterator[Path]:
	"""Todos los ficheros de una carpeta, sin cachés ni entornos virtuales."""
	for actual, carpetas, ficheros in os.walk(carpeta):
		carpetas[:] = [nombre for nombre in carpetas if nombre not in CARPETAS_IGNORADAS]
		for fichero in ficheros:
			yield Path(actual) / fichero


def comprobar(ficheros: Iterable[Path], base: Path, cadenas: list[tuple[str, str]] | None = None) -> list[Hallazgo]:
	"""Busca en cada fichero; los nombres del informe van relativos a ``base`` (así el informe tampoco lleva rutas)."""
	patrones = _patrones(cadenas_del_equipo() if cadenas is None else cadenas)
	hallazgos: list[Hallazgo] = []
	for ruta in ficheros:
		try:
			nombre = ruta.resolve().relative_to(base.resolve()).as_posix()
		except ValueError:
			nombre = ruta.name
		# El nombre del fichero también puede delatar (un fichero llamado como el usuario).
		hallazgos += buscar_en_bytes(nombre + " (nombre)", nombre.encode("utf-8"), patrones)
		hallazgos += buscar_en_fichero(ruta, nombre, patrones)
	return hallazgos


def comprobar_repositorio(raiz: Path = RAIZ) -> list[Hallazgo]:
	"""Hallazgos en los ficheros que se subirían al repositorio."""
	return comprobar(ficheros_del_repositorio(raiz), raiz)


def comprobar_carpeta(carpeta: Path) -> list[Hallazgo]:
	"""Hallazgos en todo el contenido de una carpeta (por ejemplo, ``build/entornolab``)."""
	return comprobar(ficheros_de_carpeta(carpeta), carpeta)


def _informar(titulo: str, hallazgos: list[Hallazgo]) -> int:
	if not hallazgos:
		print(f"{titulo}: limpio, no hay rutas ni datos del equipo de desarrollo.")
		return 0
	print(f"{titulo}: {len(hallazgos)} apariciones de rutas o datos del equipo de desarrollo:")
	for hallazgo in hallazgos:
		print(f"  - {hallazgo}")
	print(
		"Quítelas o sustitúyalas por una ruta relativa o un marcador (%USERPROFILE%, <carpeta del programa>); "
		f"si una línea de texto la necesita de verdad, márquela con «{MARCADOR_PERMITIDO}»."
	)
	return 1


def main(argumentos: list[str]) -> int:
	"""Punto de entrada de línea de órdenes."""
	if not argumentos:
		try:
			hallazgos = comprobar_repositorio()
		except (OSError, RuntimeError, subprocess.SubprocessError) as error:
			print(f"No se pudo listar el repositorio con git ({error}); no se ha comprobado nada.")
			return 2
		return _informar("Repositorio", hallazgos)
	if len(argumentos) != 2 or argumentos[0] not in ("--build", "--zip", "--carpeta"):
		print(__doc__)
		return 2
	objetivo = Path(argumentos[1]).resolve()
	if not objetivo.exists():
		print(f"ERROR: no existe {argumentos[1]}.")
		return 2
	if argumentos[0] == "--zip":
		return _informar(f"ZIP {objetivo.name}", comprobar([objetivo], objetivo.parent))
	return _informar(f"Carpeta {objetivo.name}", comprobar_carpeta(objetivo))


if __name__ == "__main__":
	sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
	sys.exit(main(sys.argv[1:]))
