"""Paquete ``.elab``: el fichero en el que viaja un entorno.

Es un ZIP con ``manifiesto.json``, ``entorno.json``, las actividades y los
sonidos e imágenes propios. Aquí se decide cómo se escribe sin riesgo de
perder el trabajo (escritura atómica y copia ``.bak``) y cómo se abre un
paquete AJENO sin fiarse de él: se comprueban nombres, tamaños y tipos de
fichero antes de leer nada, porque un ZIP puede traer rutas que se salen de
su carpeta o ficheros gigantes. Dentro solo hay datos: nunca se ejecuta nada.

Las actividades se guardan y se cargan como diccionarios sin interpretar;
el paquete ``app.actividades`` es quien las entiende.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import zipfile
from collections.abc import Callable, Iterable, Mapping
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from app.core.i18n import _
from app.core.version import APP_VERSION, NOMBRE_APLICACION
from app.dominio.modelo import FORMATO_ACTUAL, Entorno

log = logging.getLogger(__name__)

EXTENSION_PAQUETE = ".elab"
NOMBRE_MANIFIESTO = "manifiesto.json"
NOMBRE_ENTORNO = "entorno.json"
CARPETA_ACTIVIDADES = "actividades"
CARPETA_SONIDOS = "sonidos"
CARPETA_IMAGENES = "imagenes"

EXTENSIONES_SONIDO = frozenset({".wav", ".ogg", ".flac"})
# Sin SVG a propósito: un SVG puede llevar guiones y enlaces externos.
EXTENSIONES_IMAGEN = frozenset({".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"})

# Límites al abrir un paquete: generosos para un entorno real, pequeños para una «bomba» ZIP.
MAX_ENTRADAS = 2000
MAX_BYTES_JSON = 20 * 1024 * 1024
MAX_BYTES_RECURSO = 50 * 1024 * 1024
MAX_BYTES_TOTAL = 300 * 1024 * 1024

# Nombres que Windows reserva para dispositivos: no pueden ser ficheros.
_RESERVADOS_WINDOWS = frozenset({"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)})
_PATRON_ID = re.compile(r"[^a-z0-9_-]+")


class ErrorFormato(Exception):
	"""El fichero no es un paquete válido; el mensaje ya está pensado para la persona."""


# ── Seguridad de nombres y tamaños (también la usa el catálogo de complementos) ──


def nombre_interno_seguro(nombre: str) -> bool:
	"""True si un nombre de dentro de un ZIP es inofensivo.

	Se rechazan rutas absolutas, unidades de disco, barras invertidas, ``..``,
	caracteres de control, nombres reservados de Windows y los que acaban en
	punto o espacio (Windows los cambia al escribirlos).
	"""
	if not nombre or len(nombre) > 240:
		return False
	if "\\" in nombre or ":" in nombre or nombre.startswith("/"):
		return False
	if any(ord(caracter) < 32 for caracter in nombre):
		return False
	partes = nombre.rstrip("/").split("/")
	for parte in partes:
		if parte in ("", ".", ".."):
			return False
		if parte != parte.strip() or parte.endswith("."):
			return False
		if any(caracter in '<>"|?*' for caracter in parte):
			return False
		if parte.split(".")[0].lower() in _RESERVADOS_WINDOWS:
			return False
	return True


def identificador_seguro(texto: str, reserva: str = "elemento") -> str:
	"""Convierte un texto en un identificador válido como nombre de fichero (minúsculas, cifras, - y _)."""
	limpio = _PATRON_ID.sub("-", str(texto).strip().lower()).strip("-")
	return limpio[:80] or reserva


def comprobar_zip(
	archivo: zipfile.ZipFile,
	permitido: Callable[[str], bool],
	max_entradas: int = MAX_ENTRADAS,
	max_total: int = MAX_BYTES_TOTAL,
	limite_de: Callable[[str], int] | None = None,
) -> list[zipfile.ZipInfo]:
	"""Revisa TODAS las entradas de un ZIP antes de leer ninguna y devuelve las de fichero.

	``permitido`` decide si un nombre es de los que el formato admite y
	``limite_de`` da el tamaño máximo de cada uno. Lanza ``ErrorFormato`` con
	el motivo exacto en cuanto algo no cuadra.
	"""
	entradas = archivo.infolist()
	if len(entradas) > max_entradas:
		raise ErrorFormato(
			_("El paquete contiene demasiados ficheros ({n}); el máximo es {maximo}.").format(n=len(entradas), maximo=max_entradas)
		)
	ficheros: list[zipfile.ZipInfo] = []
	vistos: set[str] = set()
	total = 0
	for entrada in entradas:
		nombre = entrada.filename
		if not nombre_interno_seguro(nombre):
			raise ErrorFormato(_("El paquete contiene un nombre de fichero no permitido: «{nombre}».").format(nombre=nombre))
		if entrada.is_dir():
			continue
		if entrada.flag_bits & 0x1:
			raise ErrorFormato(_("El paquete está cifrado con contraseña y no se puede abrir."))
		clave = nombre.lower()
		if clave in vistos:
			raise ErrorFormato(_("El paquete contiene dos veces el fichero «{nombre}».").format(nombre=nombre))
		vistos.add(clave)
		if not permitido(nombre):
			raise ErrorFormato(_("El paquete contiene un fichero de un tipo no admitido: «{nombre}».").format(nombre=nombre))
		limite = limite_de(nombre) if limite_de else MAX_BYTES_RECURSO
		if entrada.file_size > limite:
			raise ErrorFormato(
				_("El fichero «{nombre}» del paquete es demasiado grande ({megas:.1f} MB; el máximo es {maximo:.0f} MB).").format(
					nombre=nombre, megas=entrada.file_size / 1048576, maximo=limite / 1048576
				)
			)
		total += entrada.file_size
		if total > max_total:
			raise ErrorFormato(
				_("El contenido del paquete es demasiado grande (más de {maximo:.0f} MB).").format(maximo=max_total / 1048576)
			)
		ficheros.append(entrada)
	return ficheros


def leer_entrada(archivo: zipfile.ZipFile, entrada: zipfile.ZipInfo, limite: int) -> bytes:
	"""Lee una entrada sin fiarse del tamaño que declara: corta si pasa de ``limite``."""
	try:
		with archivo.open(entrada) as flujo:
			datos = flujo.read(limite + 1)
	except (zipfile.BadZipFile, OSError, RuntimeError, NotImplementedError, EOFError) as error:
		raise ErrorFormato(_("No se puede leer «{nombre}» dentro del paquete: está dañado.").format(nombre=entrada.filename)) from error
	if len(datos) > limite:
		raise ErrorFormato(_("El fichero «{nombre}» del paquete es más grande de lo que declara.").format(nombre=entrada.filename))
	return datos


def leer_json(datos: bytes, nombre: str) -> Any:
	"""Interpreta un JSON en UTF-8 y explica el fallo con el nombre del fichero."""
	try:
		return json.loads(datos.decode("utf-8-sig"))
	except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as error:
		raise ErrorFormato(_("«{nombre}» no es un JSON válido: {detalle}").format(nombre=nombre, detalle=error)) from error


def _recurso_permitido(nombre: str) -> bool:
	"""True si el nombre es de los que admite un paquete ``.elab``."""
	if nombre in (NOMBRE_MANIFIESTO, NOMBRE_ENTORNO):
		return True
	ruta = PurePosixPath(nombre)
	if len(ruta.parts) != 2:
		return False
	carpeta, extension = ruta.parts[0], ruta.suffix.lower()
	if carpeta == CARPETA_ACTIVIDADES:
		return extension == ".json"
	if carpeta == CARPETA_SONIDOS:
		return extension in EXTENSIONES_SONIDO
	if carpeta == CARPETA_IMAGENES:
		return extension in EXTENSIONES_IMAGEN
	return False


def _limite_recurso(nombre: str) -> int:
	return MAX_BYTES_JSON if nombre.lower().endswith(".json") else MAX_BYTES_RECURSO


# ── Migraciones ──────────────────────────────────────────────────────────────


def _migrar_0_a_1(datos: dict[str, Any]) -> dict[str, Any]:
	"""Borradores anteriores a la primera versión: sin número de formato y con «habitaciones».

	Los primeros prototipos llamaban ``habitaciones`` a los espacios de cada
	planta y guardaban el inicio como lista ``[planta, x, y, rumbo]``.
	"""
	for planta in datos.get("plantas") or []:
		if isinstance(planta, dict) and "habitaciones" in planta and "espacios" not in planta:
			planta["espacios"] = planta.pop("habitaciones")
	inicio = datos.get("inicio")
	if isinstance(inicio, list) and len(inicio) >= 3:
		datos["inicio"] = {"planta": inicio[0], "x": inicio[1], "y": inicio[2], "rumbo": inicio[3] if len(inicio) > 3 else 0.0}
	datos["formato"] = 1
	return datos


# Cada función convierte del formato de su clave al siguiente.
MIGRACIONES: dict[int, Callable[[dict[str, Any]], dict[str, Any]]] = {0: _migrar_0_a_1}


def migrar(datos: dict) -> dict:
	"""Convierte un ``entorno.json`` de un formato antiguo al actual.

	Aplica las migraciones en cadena (0 → 1 → 2…). Un formato más nuevo que el
	del programa no se intenta leer: se pide actualizar, que es mejor que
	abrirlo a medias y estropearlo al guardar.
	"""
	if not isinstance(datos, dict):
		raise ErrorFormato(_("El entorno no tiene la estructura esperada."))
	bruto = datos.get("formato", 0)
	try:
		version = int(bruto)
	except (TypeError, ValueError) as error:
		raise ErrorFormato(_("El número de formato del entorno no es válido: «{valor}».").format(valor=bruto)) from error
	if version > FORMATO_ACTUAL:
		raise ErrorFormato(
			_(
				"Este entorno se creó con una versión más nueva de {aplicacion} (formato {formato}). Actualice el programa para abrirlo."
			).format(aplicacion=NOMBRE_APLICACION, formato=version)
		)
	if version < 0:
		raise ErrorFormato(_("El número de formato del entorno no es válido: «{valor}».").format(valor=bruto))
	actual = dict(datos)
	while version < FORMATO_ACTUAL:
		paso = MIGRACIONES.get(version)
		if paso is None:
			raise ErrorFormato(_("No se sabe convertir un entorno del formato {formato}.").format(formato=version))
		log.info("Se convierte el entorno del formato %s al %s", version, version + 1)
		actual = paso(actual)
		version += 1
	actual["formato"] = FORMATO_ACTUAL
	return actual


# ── Paquete ──────────────────────────────────────────────────────────────────


@dataclass
class Paquete:
	"""Contenido de un ``.elab`` ya abierto y comprobado."""

	entorno: Entorno
	actividades: list[dict[str, Any]] = field(default_factory=list)
	recursos: dict[str, bytes] = field(default_factory=dict)
	manifiesto: dict[str, Any] = field(default_factory=dict)
	ruta: Path | None = None

	def recurso(self, nombre: str) -> bytes:
		"""Bytes de un sonido o imagen del paquete (``sonidos/timbre.ogg``).

		Admite también el nombre sin carpeta. Lanza ``KeyError`` si no existe.
		"""
		if nombre in self.recursos:
			return self.recursos[nombre]
		for carpeta in (CARPETA_SONIDOS, CARPETA_IMAGENES):
			candidato = f"{carpeta}/{nombre}"
			if candidato in self.recursos:
				return self.recursos[candidato]
		raise KeyError(nombre)

	def tiene_recurso(self, nombre: str) -> bool:
		"""True si el paquete trae ese sonido o imagen."""
		try:
			self.recurso(nombre)
		except KeyError:
			return False
		return True

	def nombres_recursos(self) -> list[str]:
		"""Nombres de todos los recursos, ordenados."""
		return sorted(self.recursos)

	def actividad(self, id_actividad: str) -> dict[str, Any] | None:
		"""Actividad con ese id, o None."""
		for actividad in self.actividades:
			if actividad.get("id") == id_actividad:
				return actividad
		return None


def _manifiesto_de(entorno: Entorno) -> dict[str, Any]:
	return {
		"formato": FORMATO_ACTUAL,
		"aplicacion": NOMBRE_APLICACION,
		"version": APP_VERSION,
		"id": entorno.id,
		"nombre": entorno.nombre,
	}


def _json_bytes(datos: Any) -> bytes:
	return json.dumps(datos, ensure_ascii=False, indent="\t").encode("utf-8")


def _nombres_actividades(actividades: Iterable[Mapping[str, Any]]) -> list[tuple[str, dict[str, Any]]]:
	"""Asigna a cada actividad su nombre de fichero, único y seguro."""
	resultado: list[tuple[str, dict[str, Any]]] = []
	usados: set[str] = set()
	for numero, actividad in enumerate(actividades, start=1):
		if not isinstance(actividad, Mapping):
			raise ErrorFormato(_("La actividad número {n} no es un diccionario y no se puede guardar.").format(n=numero))
		datos = dict(actividad)
		base = identificador_seguro(str(datos.get("id") or ""), f"actividad-{numero}")
		nombre = base
		sufijo = 2
		while nombre in usados:
			nombre = f"{base}-{sufijo}"
			sufijo += 1
		usados.add(nombre)
		datos.setdefault("id", nombre)
		resultado.append((f"{CARPETA_ACTIVIDADES}/{nombre}.json", datos))
	return resultado


def guardar_paquete(
	ruta: str | os.PathLike[str],
	entorno: Entorno,
	actividades: Iterable[Mapping[str, Any]] = (),
	recursos: Mapping[str, bytes | str | os.PathLike[str]] | None = None,
) -> None:
	"""Escribe el paquete de forma atómica y deja la versión anterior como ``.bak``.

	Se escribe entero en un fichero temporal de la misma carpeta, se comprueba
	que es un ZIP legible y solo entonces sustituye al bueno: un corte de luz
	o un disco lleno a mitad dejan intacto el fichero anterior.

	``recursos`` asocia nombres internos (``sonidos/timbre.ogg``,
	``imagenes/plano.png``) con sus bytes o con la ruta de un fichero.
	"""
	destino = Path(ruta)
	contenido: list[tuple[str, bytes]] = [
		(NOMBRE_MANIFIESTO, _json_bytes(_manifiesto_de(entorno))),
		(NOMBRE_ENTORNO, _json_bytes(entorno.a_dict())),
	]
	for nombre, datos in _nombres_actividades(actividades):
		contenido.append((nombre, _json_bytes(datos)))
	for nombre, origen in (recursos or {}).items():
		if not nombre_interno_seguro(nombre) or not _recurso_permitido(nombre) or nombre in (NOMBRE_MANIFIESTO, NOMBRE_ENTORNO):
			raise ErrorFormato(
				_(
					"«{nombre}» no se puede incluir en el paquete: solo se admiten sonidos (wav, ogg, flac) en «sonidos/» e imágenes en «imagenes/»."
				).format(nombre=nombre)
			)
		if nombre.startswith(CARPETA_ACTIVIDADES + "/"):
			raise ErrorFormato(_("Las actividades se pasan en «actividades», no como recursos: «{nombre}».").format(nombre=nombre))
		try:
			datos_recurso = bytes(origen) if isinstance(origen, (bytes, bytearray, memoryview)) else Path(origen).read_bytes()
		except OSError as error:
			raise ErrorFormato(_("No se puede leer el recurso «{nombre}»: {detalle}").format(nombre=nombre, detalle=error)) from error
		if len(datos_recurso) > MAX_BYTES_RECURSO:
			raise ErrorFormato(_("El recurso «{nombre}» es demasiado grande para el paquete.").format(nombre=nombre))
		contenido.append((nombre, datos_recurso))

	temporal = destino.with_name(destino.name + ".tmp")
	copia = destino.with_name(destino.name + ".bak")
	try:
		destino.parent.mkdir(parents=True, exist_ok=True)
		with open(temporal, "wb") as fichero:
			with zipfile.ZipFile(fichero, "w", compression=zipfile.ZIP_DEFLATED) as archivo:
				for nombre, datos in contenido:
					# Fecha fija: el mismo entorno produce siempre el mismo fichero.
					entrada = zipfile.ZipInfo(nombre, date_time=(2020, 1, 1, 0, 0, 0))
					entrada.compress_type = zipfile.ZIP_DEFLATED
					archivo.writestr(entrada, datos)
			fichero.flush()
			os.fsync(fichero.fileno())
		with zipfile.ZipFile(temporal) as comprobacion:
			averiado = comprobacion.testzip()
		if averiado is not None:
			raise ErrorFormato(
				_("El paquete no se ha escrito bien («{nombre}» está dañado). No se ha tocado el fichero anterior.").format(nombre=averiado)
			)
		if destino.exists():
			shutil.copy2(destino, copia)
		os.replace(temporal, destino)
	except OSError as error:
		raise ErrorFormato(_("No se puede guardar «{ruta}»: {detalle}").format(ruta=destino, detalle=error)) from error
	finally:
		if temporal.exists():
			try:
				temporal.unlink()
			except OSError as error:
				log.warning("No se pudo borrar el temporal %s: %s", temporal, error)
	log.info("Entorno «%s» guardado en %s", entorno.nombre, destino)


def _abrir_zip(ruta: Path) -> zipfile.ZipFile:
	if not ruta.is_file():
		raise ErrorFormato(_("No existe el fichero «{ruta}».").format(ruta=ruta))
	try:
		return zipfile.ZipFile(ruta)
	except (zipfile.BadZipFile, OSError) as error:
		raise ErrorFormato(
			_("«{nombre}» no es un paquete de {aplicacion} o está dañado.").format(nombre=ruta.name, aplicacion=NOMBRE_APLICACION)
		) from error


def _leer_manifiesto(archivo: zipfile.ZipFile, ficheros: dict[str, zipfile.ZipInfo]) -> dict[str, Any]:
	if NOMBRE_MANIFIESTO not in ficheros:
		raise ErrorFormato(
			_("Al paquete le falta «{nombre}»: no es un entorno de {aplicacion}.").format(
				nombre=NOMBRE_MANIFIESTO, aplicacion=NOMBRE_APLICACION
			)
		)
	manifiesto = leer_json(leer_entrada(archivo, ficheros[NOMBRE_MANIFIESTO], MAX_BYTES_JSON), NOMBRE_MANIFIESTO)
	if not isinstance(manifiesto, dict):
		raise ErrorFormato(_("«{nombre}» no tiene la estructura esperada.").format(nombre=NOMBRE_MANIFIESTO))
	try:
		formato = int(manifiesto.get("formato", 0))
	except (TypeError, ValueError) as error:
		raise ErrorFormato(_("El número de formato del paquete no es válido.")) from error
	if formato > FORMATO_ACTUAL:
		raise ErrorFormato(
			_(
				"Este paquete se creó con una versión más nueva de {aplicacion} (formato {formato}). Actualice el programa para abrirlo."
			).format(aplicacion=NOMBRE_APLICACION, formato=formato)
		)
	return manifiesto


def leer_manifiesto(ruta: str | os.PathLike[str]) -> dict[str, Any]:
	"""Lee solo el manifiesto (id, nombre, versión): para listar entornos sin abrirlos enteros."""
	origen = Path(ruta)
	with _abrir_zip(origen) as archivo:
		ficheros = {entrada.filename: entrada for entrada in comprobar_zip(archivo, _recurso_permitido, limite_de=_limite_recurso)}
		return _leer_manifiesto(archivo, ficheros)


def cargar_paquete(ruta: str | os.PathLike[str]) -> Paquete:
	"""Abre un ``.elab`` comprobando su seguridad y convirtiendo formatos antiguos.

	Lanza ``ErrorFormato`` con un mensaje claro si el fichero no existe, no
	es un ZIP, trae nombres peligrosos, ficheros de tipos no admitidos o
	demasiado grandes, le falta el manifiesto o el entorno, o es de una
	versión más nueva del programa.
	"""
	origen = Path(ruta)
	with _abrir_zip(origen) as archivo:
		ficheros = {entrada.filename: entrada for entrada in comprobar_zip(archivo, _recurso_permitido, limite_de=_limite_recurso)}
		manifiesto = _leer_manifiesto(archivo, ficheros)
		if NOMBRE_ENTORNO not in ficheros:
			raise ErrorFormato(_("Al paquete le falta «{nombre}».").format(nombre=NOMBRE_ENTORNO))
		datos = leer_json(leer_entrada(archivo, ficheros[NOMBRE_ENTORNO], MAX_BYTES_JSON), NOMBRE_ENTORNO)
		entorno = Entorno.de_dict(migrar(datos))
		if not entorno.id:
			entorno.id = identificador_seguro(str(manifiesto.get("id") or origen.stem), "entorno")
		if not entorno.nombre:
			entorno.nombre = str(manifiesto.get("nombre") or origen.stem)
		actividades: list[dict[str, Any]] = []
		recursos: dict[str, bytes] = {}
		for nombre in sorted(ficheros):
			if nombre in (NOMBRE_MANIFIESTO, NOMBRE_ENTORNO):
				continue
			contenido = leer_entrada(archivo, ficheros[nombre], _limite_recurso(nombre))
			if nombre.startswith(CARPETA_ACTIVIDADES + "/"):
				actividad = leer_json(contenido, nombre)
				if not isinstance(actividad, dict):
					raise ErrorFormato(_("La actividad «{nombre}» no tiene la estructura esperada.").format(nombre=nombre))
				actividad.setdefault("id", PurePosixPath(nombre).stem)
				actividades.append(actividad)
			else:
				recursos[nombre] = contenido
	log.info("Entorno «%s» cargado de %s (%s actividades, %s recursos)", entorno.nombre, origen, len(actividades), len(recursos))
	return Paquete(entorno=entorno, actividades=actividades, recursos=recursos, manifiesto=manifiesto, ruta=origen)


def recuperar_copia(ruta: str | os.PathLike[str]) -> Paquete:
	"""Abre la copia ``.bak`` de un paquete: el último recurso si el bueno está dañado."""
	origen = Path(ruta)
	return cargar_paquete(origen.with_name(origen.name + ".bak"))
