"""Catálogo en línea de complementos: descargar, actualizar y quitar complementos uno a uno.

Un complemento (mobiliario, material de ciudad...) es una carpeta de SOLO
DATOS en ``data/plugins/<id>``. Este módulo permite ponerlos al día sin
descargar toda la aplicación y sin esperar a una versión nueva. Sin wx: la
interfaz está en ``app/ui/dialogo_complementos_en_linea.py``.

Dónde está el catálogo: en un repositorio aparte de GitHub,
``hxebolax/EntornoLab-complementos``. En su raíz hay un índice firmado,
``catalogo.json``, y los paquetes ``.elabc`` en ``paquetes/``. Se eligió un
repositorio aparte (y no una carpeta del principal ni recursos de una
publicación) porque así publicar o corregir un complemento es un «commit»
que no exige sacar versión de la aplicación, y un tercero propone el suyo con
una petición de cambios («pull request») que el autor revisa, empaqueta y
firma. El formato del índice está en ``docs/catalogo-de-complementos.md``.

Seguridad:

- El índice va firmado con la misma clave Ed25519 que las versiones. La firma
  se comprueba antes de mirar ningún campo; sin firma válida no se instala nada.
- Cada paquete se descarga comprobando el tamaño y el SHA-256 del índice.
- Antes de instalar, :func:`revisar_paquete` rechaza cualquier paquete con
  ejecutables o guiones (también disfrazados de imagen), rutas peligrosas o
  tipos de fichero que no sean datos.
- La instalación real la hace ``app.dominio.catalogo.instalar_complemento``; al
  terminar se pasa ``validar_complemento`` y, si la versión nueva no es válida,
  se vuelve a la anterior.

De serie y del usuario: los complementos que viajan con la aplicación son «de
serie» (los enumera ``data/plugins/de_serie.json``); los demás son del
usuario. ``data/config/complementos.json`` apunta lo que se instaló o
actualizó desde aquí. Al actualizar la aplicación, un complemento del usuario
o uno de serie que el catálogo dejó más nuevo no se pisa (ver
``app.services.actualizador._complementos_a_saltar``).

Privacidad: solo peticiones ``GET`` a GitHub, sin datos del equipo, del
profesional ni de los alumnos.
"""

from __future__ import annotations

import json
import logging
import os
import re
import shutil
import stat
import threading
import urllib.parse
import zipfile
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath
from typing import Any

from app.core import descargas, paths, red
from app.core.configuracion import obtener_configuracion
from app.core.i18n import N_, _
from app.core.version import APP_VERSION, NOMBRE_APLICACION
from app.services import actualizador

log = logging.getLogger(__name__)

REPOSITORIO_CATALOGO = "hxebolax/EntornoLab-complementos"
URL_CATALOGO = f"https://raw.githubusercontent.com/{REPOSITORIO_CATALOGO}/main/catalogo.json"
FORMATO_INDICE = 1
TIPO_INDICE = "catalogo-complementos"
EXTENSION = ".elabc"
MAX_INDICE = 2 * 1024 * 1024
MAX_PAQUETE = 200 * 1024 * 1024
MAX_EXPANDIDO = 400 * 1024 * 1024
MAX_ENTRADAS = 2000
_PATRON_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_PATRON_SHA = re.compile(r"^[0-9a-f]{64}$")

# Lo único que puede traer un complemento: fichas, textos, sonidos e imágenes.
EXTENSIONES_PERMITIDAS = frozenset({".json", ".txt", ".md", ".wav", ".ogg", ".flac", ".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp"})
# Para dar un mensaje claro cuando alguien intenta colar código.
EXTENSIONES_EJECUTABLES = frozenset(
	{
		".exe", ".dll", ".com", ".scr", ".pif", ".cpl", ".sys", ".msi", ".msp", ".bat", ".cmd", ".ps1", ".psm1", ".vbs", ".vbe",
		".js", ".jse", ".wsf", ".wsh", ".hta", ".lnk", ".url", ".reg", ".jar", ".py", ".pyc", ".pyd", ".pyw", ".sh", ".so",
		".php", ".pl", ".rb", ".html", ".htm", ".svg",
	}
)  # fmt: skip
# Comienzos de fichero de los formatos ejecutables (un .exe renombrado a .png sigue empezando por «MZ»).
_FIRMAS_EJECUTABLES = (b"MZ", b"\x7fELF", b"#!", b"\xca\xfe\xba\xbe", b"\xcf\xfa\xed\xfe")

# Estados de un complemento al comparar el catálogo con lo instalado.
NUEVO = "nuevo"
ACTUALIZABLE = "actualizable"
AL_DIA = "al_dia"
SOLO_LOCAL = "solo_local"
REQUIERE_APP = "requiere_app"
_NOMBRES_ESTADO = {
	NUEVO: N_("Disponible"),
	ACTUALIZABLE: N_("Hay actualización"),
	AL_DIA: N_("Al día"),
	SOLO_LOCAL: N_("Solo en este equipo"),
	REQUIERE_APP: N_("Necesita una versión más nueva de la aplicación"),
}

Instalador = Callable[[Path], str]
Validador = Callable[[Path], list]

# Una sola operación a la vez sobre data/plugins (instalar, quitar, volver atrás).
_cerrojo = threading.Lock()


# ── Errores ──────────────────────────────────────────────────────────────────


class ErrorComplementoEnLinea(Exception):
	"""Fallo del catálogo en línea con un mensaje claro para el usuario."""

	#: True si tiene sentido ofrecer «Reintentar» (fallo pasajero de red).
	reintentar = False


class ErrorCatalogo(ErrorComplementoEnLinea):
	"""El índice no llegó, no está firmado o no es válido."""


class ErrorPaqueteComplemento(ErrorComplementoEnLinea):
	"""El paquete es peligroso (trae código o rutas raras) o no corresponde al índice."""


class ErrorValidacionComplemento(ErrorComplementoEnLinea):
	"""La versión nueva se instaló pero no pasó la validación; se volvió a la anterior."""

	def __init__(self, mensaje: str, avisos: list | None = None) -> None:
		super().__init__(mensaje)
		#: Avisos de ``validar_complemento`` que motivaron el rechazo.
		self.avisos = list(avisos or [])


class OperacionCancelada(ErrorComplementoEnLinea):
	"""El usuario canceló la descarga."""


# ── Datos ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class ComplementoEnLinea:
	"""Un complemento tal como lo describe el índice firmado."""

	id: str
	nombre: str
	version: str
	url: str
	sha256: str
	tamano: int
	descripcion: str = ""
	autor: str = ""
	licencia: str = ""
	version_minima_app: str = ""
	categorias: tuple[str, ...] = ()
	objetos: int = 0
	fecha: str = ""


@dataclass(frozen=True)
class Indice:
	"""El catálogo en línea ya verificado."""

	complementos: dict[str, ComplementoEnLinea]
	url: str
	generado: str = ""
	serie: int = 0


@dataclass(frozen=True)
class ComplementoLocal:
	"""Un complemento instalado en ``data/plugins``."""

	id: str
	nombre: str
	version: str
	carpeta: Path
	descripcion: str = ""
	autor: str = ""
	licencia: str = ""
	categorias: tuple[str, ...] = ()
	objetos: int = 0
	#: True si viaja con la aplicación (no se puede desinstalar).
	de_serie: bool = False
	#: «serie» (tal como vino), «catalogo» (instalado o actualizado desde aquí) o «manual».
	origen: str = "manual"


@dataclass(frozen=True)
class EstadoComplemento:
	"""Una fila de la lista: lo que hay en el catálogo frente a lo instalado."""

	id: str
	estado: str
	local: ComplementoLocal | None = None
	en_linea: ComplementoEnLinea | None = None
	#: True si se guarda la versión anterior y se puede volver a ella.
	hay_anterior: bool = False

	@property
	def nombre(self) -> str:
		"""Nombre visible: el del catálogo si lo hay; si no, el instalado."""
		return (self.en_linea.nombre if self.en_linea else "") or (self.local.nombre if self.local else "") or self.id

	@property
	def version_instalada(self) -> str:
		return self.local.version if self.local else ""

	@property
	def version_disponible(self) -> str:
		return self.en_linea.version if self.en_linea else ""

	@property
	def tamano(self) -> int:
		return self.en_linea.tamano if self.en_linea else 0

	@property
	def categorias(self) -> tuple[str, ...]:
		return (self.en_linea.categorias if self.en_linea else ()) or (self.local.categorias if self.local else ())

	@property
	def de_serie(self) -> bool:
		return bool(self.local and self.local.de_serie)

	@property
	def instalable(self) -> bool:
		"""Se puede pulsar «Instalar»."""
		return self.estado == NUEVO

	@property
	def actualizable(self) -> bool:
		"""Se puede pulsar «Actualizar»."""
		return self.estado == ACTUALIZABLE

	@property
	def desinstalable(self) -> bool:
		"""Se puede pulsar «Desinstalar»: está instalado y no es de serie."""
		return self.local is not None and not self.local.de_serie


@dataclass(frozen=True)
class ResultadoInstalacion:
	"""Qué pasó con un complemento al instalarlo o actualizarlo."""

	id: str
	nombre: str = ""
	version: str = ""
	version_anterior: str = ""
	error: str = ""
	cancelado: bool = False
	avisos: tuple = field(default_factory=tuple)

	@property
	def correcto(self) -> bool:
		return not self.error and not self.cancelado


def nombre_estado(estado: str) -> str:
	"""Texto traducido de un estado, para la columna «Estado» de la lista."""
	return _(_NOMBRES_ESTADO.get(estado, estado))


# ── Preferencias y registro ──────────────────────────────────────────────────


def url_catalogo() -> str:
	"""Dirección del índice: la de las preferencias o, si está vacía, la oficial.

	Una dirección propia solo sirve de espejo: el índice debe venir firmado
	con la clave de la aplicación igualmente.
	"""
	propia = str(obtener_configuracion().obtener("complementos.url_catalogo") or "").strip()
	return propia or URL_CATALOGO


def comprobar_con_la_aplicacion() -> bool:
	"""True si el catálogo se mira junto a la comprobación de actualizaciones al arrancar."""
	return bool(obtener_configuracion().obtener("complementos.comprobar_actualizaciones"))


def ruta_registro() -> Path:
	"""``data/config/complementos.json``: lo instalado desde el catálogo. Es del usuario."""
	return paths.ruta_configuracion() / actualizador.REGISTRO_COMPLEMENTOS


def leer_registro() -> dict:
	"""Registro de lo instalado desde el catálogo; vacío si falta o está dañado."""
	try:
		datos = json.loads(ruta_registro().read_text(encoding="utf-8"))
	except FileNotFoundError:
		datos = {}
	except OSError, ValueError:
		log.warning("No se pudo leer %s; se empieza con el registro vacío", ruta_registro(), exc_info=True)
		datos = {}
	if not isinstance(datos, dict):
		datos = {}
	if not isinstance(datos.get("instalados"), dict):
		datos["instalados"] = {}
	if not isinstance(datos.get("series"), dict):
		datos["series"] = {}
	return datos


def _guardar_registro(datos: dict) -> None:
	"""Escritura atómica: un corte de luz no deja el registro a medias."""
	ruta = ruta_registro()
	temporal = ruta.with_name(ruta.name + ".tmp")
	temporal.write_text(json.dumps(datos, indent="\t", ensure_ascii=False, sort_keys=True), encoding="utf-8")
	os.replace(temporal, ruta)


def carpeta_anteriores() -> Path:
	"""``data/backups/complementos``: la versión anterior de cada complemento actualizado."""
	return paths.ruta_copias() / "complementos"


def _carpeta_descargas() -> Path:
	return paths.ruta_temporales() / "complementos"


# ── Índice ───────────────────────────────────────────────────────────────────


def _error_de_red(error: red.ErrorRed) -> ErrorComplementoEnLinea:
	if error.categoria == "cancelado":
		return OperacionCancelada(error.mensaje_usuario)
	nuevo = ErrorCatalogo(error.mensaje_usuario)
	nuevo.reintentar = error.reintentar
	return nuevo


def _complemento_de_indice(bruto: Any, url_indice: str) -> ComplementoEnLinea:
	"""Valida una entrada del índice (ya con la firma comprobada). Lanza ``ValueError`` si no vale."""
	if not isinstance(bruto, dict):
		raise ValueError("la entrada no es un objeto")
	identificador = str(bruto.get("id") or "")
	if not _PATRON_ID.match(identificador):
		raise ValueError(f"identificador no válido: {identificador!r}")
	version = str(bruto.get("version") or "")
	actualizador.clave_version(version)
	minima = str(bruto.get("version_minima_app") or "")
	if minima:
		actualizador.clave_version(minima)
	sha = str(bruto.get("sha256") or "").strip().lower()
	if not _PATRON_SHA.match(sha):
		raise ValueError("huella SHA-256 no válida")
	tamano = bruto.get("tamano")
	if not isinstance(tamano, int) or isinstance(tamano, bool) or not 0 < tamano <= MAX_PAQUETE:
		raise ValueError("tamaño no válido")
	direccion = str(bruto.get("url") or "")
	if not direccion:
		raise ValueError("falta la dirección de descarga")
	direccion = urllib.parse.urljoin(url_indice, direccion)
	red.comprobar_url(direccion)
	categorias = bruto.get("categorias") or []
	if not isinstance(categorias, list):
		raise ValueError("las categorías no son una lista")
	objetos = bruto.get("objetos")
	return ComplementoEnLinea(
		id=identificador,
		nombre=str(bruto.get("nombre") or identificador)[:200],
		version=version,
		url=direccion,
		sha256=sha,
		tamano=tamano,
		descripcion=str(bruto.get("descripcion") or "")[:4000],
		autor=str(bruto.get("autor") or "")[:200],
		licencia=str(bruto.get("licencia") or "")[:200],
		version_minima_app=minima,
		categorias=tuple(str(categoria)[:60] for categoria in categorias[:30]),
		objetos=objetos if isinstance(objetos, int) and not isinstance(objetos, bool) and objetos >= 0 else 0,
		fecha=str(bruto.get("fecha") or "")[:40],
	)


def interpretar_indice(manifiesto: dict, url: str, claves: Iterable[str] | None = None) -> Indice:
	"""Verifica la firma del índice y lo convierte en un :class:`Indice`.

	Una entrada mal formada se descarta (y se registra) sin tirar el catálogo
	entero: un error en la ficha de un complemento no debe dejar sin catálogo
	a todo el mundo.
	"""
	try:
		actualizador.verificar_firma(manifiesto, tuple(claves) if claves is not None else actualizador.CLAVES_PUBLICAS_ED25519)
	except actualizador.ErrorFirma as error:
		raise ErrorCatalogo(_("El catálogo de complementos no está firmado correctamente; por seguridad se ignora.")) from error
	if manifiesto.get("tipo") != TIPO_INDICE or manifiesto.get("app") not in (None, NOMBRE_APLICACION):
		raise ErrorCatalogo(_("El fichero recibido no es un catálogo de complementos de esta aplicación."))
	if manifiesto.get("formato") != FORMATO_INDICE:
		raise ErrorCatalogo(_("El catálogo de complementos usa un formato que esta versión no entiende. Actualice la aplicación."))
	brutos = manifiesto.get("complementos")
	if not isinstance(brutos, list):
		raise ErrorCatalogo(_("El catálogo de complementos está dañado."))
	complementos: dict[str, ComplementoEnLinea] = {}
	for bruto in brutos:
		try:
			complemento = _complemento_de_indice(bruto, url)
		except (ValueError, red.ErrorRed) as error:
			log.warning("Entrada del catálogo descartada: %s", error)
			continue
		complementos[complemento.id] = complemento
	serie = manifiesto.get("serie")
	return Indice(
		complementos=complementos,
		url=url,
		generado=str(manifiesto.get("generado") or ""),
		serie=serie if isinstance(serie, int) and not isinstance(serie, bool) else 0,
	)


def descargar_catalogo(url: str | None = None, claves: Iterable[str] | None = None, cancelacion: Any = None) -> Indice:
	"""Descarga el índice, comprueba su firma y lo devuelve. Llamar fuera del hilo de la interfaz.

	Rechaza un índice más antiguo que el último visto en esa dirección: quien
	controle el servidor no puede volver a servir un catálogo retirado.

	:raises ErrorCatalogo: red, firma, formato o retroceso.
	:raises OperacionCancelada: si se canceló.
	"""
	direccion = url or url_catalogo()
	log.info("Descargando el catálogo de complementos de %s", direccion)
	try:
		manifiesto = red.leer_json(direccion, MAX_INDICE, cancelacion=cancelacion)
	except red.ErrorRed as error:
		raise _error_de_red(error) from error
	indice = interpretar_indice(manifiesto, direccion, claves)
	registro = leer_registro()
	vista = registro["series"].get(direccion)
	if isinstance(vista, int) and indice.serie < vista:
		log.warning("Catálogo antiguo rechazado: serie %d, ya se vio la %d", indice.serie, vista)
		raise ErrorCatalogo(_("El servidor ha enviado un catálogo más antiguo que el último que se descargó; por seguridad se ignora."))
	if indice.serie != vista:
		registro["series"][direccion] = indice.serie
		try:
			_guardar_registro(registro)
		except OSError:
			log.warning("No se pudo anotar la serie del catálogo", exc_info=True)
	log.info("Catálogo recibido: %d complementos (serie %d)", len(indice.complementos), indice.serie)
	return indice


# ── Lo instalado ─────────────────────────────────────────────────────────────


def ids_de_serie() -> dict[str, str] | None:
	"""Complementos que viajan con la aplicación ({id: versión}), o ``None`` si no hay lista.

	La lista (``data/plugins/de_serie.json``) la escribe la herramienta de
	publicación dentro del ZIP de cada versión. Desde el código fuente no
	existe: entonces es de serie todo lo que no instaló el usuario.
	"""
	ruta = paths.ruta_complementos() / actualizador.FICHERO_DE_SERIE
	try:
		datos = json.loads(ruta.read_text(encoding="utf-8"))
	except FileNotFoundError:
		return None
	except OSError, ValueError:
		log.warning("No se pudo leer %s", ruta, exc_info=True)
		return None
	lista = datos.get("de_serie") if isinstance(datos, dict) else None
	return {str(clave): str(valor) for clave, valor in lista.items()} if isinstance(lista, dict) else None


def _leer_local(carpeta: Path, de_serie: dict[str, str] | None, registrados: dict) -> ComplementoLocal | None:
	"""Lee la ficha de un complemento instalado; ``None`` si no se entiende."""
	try:
		ficha = json.loads((carpeta / actualizador.FICHA_COMPLEMENTO).read_text(encoding="utf-8-sig"))
	except OSError, ValueError:
		log.warning("Complemento ilegible en %s", carpeta, exc_info=True)
		return None
	if not isinstance(ficha, dict):
		return None
	identificador = str(ficha.get("id") or carpeta.name)
	objetos = ficha.get("objetos") if isinstance(ficha.get("objetos"), list) else []
	categorias = sorted({str(objeto.get("categoria")) for objeto in objetos if isinstance(objeto, dict) and objeto.get("categoria")})
	anotado = registrados.get(identificador)
	if de_serie is not None:
		es_de_serie = identificador in de_serie
	else:
		# Sin lista (desde el código fuente): es de serie lo que no instaló el usuario,
		# y lo que ya lo era cuando el catálogo lo actualizó.
		es_de_serie = anotado is None or (isinstance(anotado, dict) and bool(anotado.get("de_serie")))
	if identificador in registrados:
		origen = "catalogo"
	elif es_de_serie:
		origen = "serie"
	else:
		origen = "manual"
	return ComplementoLocal(
		id=identificador,
		nombre=str(ficha.get("nombre") or identificador),
		version=str(ficha.get("version") or ""),
		carpeta=carpeta,
		descripcion=str(ficha.get("descripcion") or ""),
		autor=str(ficha.get("autor") or ""),
		licencia=str(ficha.get("licencia") or ""),
		categorias=tuple(categorias),
		objetos=len(objetos),
		de_serie=es_de_serie,
		origen=origen,
	)


def instalados() -> dict[str, ComplementoLocal]:
	"""Complementos que hay en ``data/plugins``, por identificador."""
	raiz = paths.ruta_complementos()
	de_serie = ids_de_serie()
	registrados = leer_registro()["instalados"]
	resultado: dict[str, ComplementoLocal] = {}
	for carpeta in sorted(p for p in raiz.iterdir() if p.is_dir() and not p.name.startswith(".")):
		local = _leer_local(carpeta, de_serie, registrados)
		if local is not None:
			resultado[local.id] = local
	return resultado


def hay_anterior(identificador: str) -> bool:
	"""True si se guarda la versión anterior de ese complemento."""
	return (carpeta_anteriores() / identificador / actualizador.FICHA_COMPLEMENTO).is_file()


def _es_mas_nueva(a: str, b: str) -> bool:
	"""``a`` más nueva que ``b``; si alguna no es comparable, basta con que sean distintas."""
	try:
		return actualizador.es_mas_nueva(a, b)
	except actualizador.VersionInvalida:
		return a != b


def comparar(
	indice: Indice | None, locales: dict[str, ComplementoLocal] | None = None, version_app: str = APP_VERSION
) -> list[EstadoComplemento]:
	"""Cruza el catálogo con lo instalado y devuelve una fila por complemento, ordenadas por nombre.

	Estados: ``NUEVO`` (está en el catálogo y no instalado), ``ACTUALIZABLE``
	(el catálogo tiene una versión más nueva), ``AL_DIA``, ``SOLO_LOCAL`` (no
	está en el catálogo) y ``REQUIERE_APP`` (la versión del catálogo pide una
	aplicación más nueva que esta). Sin índice (sin conexión) todo es local.
	"""
	locales = instalados() if locales is None else locales
	en_linea = indice.complementos if indice else {}
	filas: list[EstadoComplemento] = []
	for identificador in sorted(set(locales) | set(en_linea)):
		local = locales.get(identificador)
		remoto = en_linea.get(identificador)
		if remoto is None:
			estado = SOLO_LOCAL
		else:
			hay_novedad = local is None or _es_mas_nueva(remoto.version, local.version)
			if not hay_novedad:
				estado = AL_DIA
			elif remoto.version_minima_app and _es_mas_nueva(remoto.version_minima_app, version_app):
				estado = REQUIERE_APP
			else:
				estado = NUEVO if local is None else ACTUALIZABLE
		filas.append(EstadoComplemento(identificador, estado, local, remoto, hay_anterior(identificador)))
	return sorted(filas, key=lambda fila: (fila.nombre.casefold(), fila.id))


def actualizables(filas: Iterable[EstadoComplemento]) -> list[ComplementoEnLinea]:
	"""Los complementos instalados que tienen versión nueva (para «Actualizar todos»)."""
	return [fila.en_linea for fila in filas if fila.actualizable and fila.en_linea is not None]


# ── Revisión del paquete ─────────────────────────────────────────────────────


def revisar_paquete(ruta_zip: str | Path, id_esperado: str | None = None) -> str:
	"""Comprueba que un ``.elabc`` es SOLO DATOS y devuelve el identificador de su ficha.

	Rechaza el paquete entero si alguna entrada tiene una ruta peligrosa
	(absoluta, con ``..``, nombre reservado), es un enlace, está cifrada, tiene
	una extensión que no es de datos, o EMPIEZA como un ejecutable aunque se
	llame ``.png``. También si la ficha no es del complemento que se pidió.

	:raises ErrorPaqueteComplemento: con el motivo.
	"""
	ruta = Path(ruta_zip)
	try:
		archivo = zipfile.ZipFile(ruta)
	except (zipfile.BadZipFile, OSError) as error:
		raise ErrorPaqueteComplemento(_("El paquete del complemento está dañado.")) from error
	with archivo:
		entradas = [entrada for entrada in archivo.infolist() if not entrada.is_dir()]
		if len(entradas) > MAX_ENTRADAS:
			raise ErrorPaqueteComplemento(_("El paquete del complemento contiene demasiados ficheros; se rechaza."))
		if sum(entrada.file_size for entrada in entradas) > MAX_EXPANDIDO:
			raise ErrorPaqueteComplemento(_("El paquete del complemento ocupa demasiado al descomprimirse; se rechaza."))
		fichas: list[zipfile.ZipInfo] = []
		for entrada in entradas:
			try:
				partes = actualizador.partes_seguras(entrada.filename)
			except actualizador.ErrorPaquete as error:
				raise ErrorPaqueteComplemento(str(error)) from error
			if stat.S_ISLNK(entrada.external_attr >> 16) or entrada.flag_bits & 0x1:
				raise ErrorPaqueteComplemento(_("El paquete del complemento contiene enlaces o ficheros cifrados; se rechaza."))
			extension = PurePosixPath(partes[-1]).suffix.lower()
			if extension in EXTENSIONES_EJECUTABLES:
				raise ErrorPaqueteComplemento(
					_("El paquete contiene un programa o un guion ({nombre}). Los complementos son solo datos: se rechaza.").format(
						nombre=entrada.filename
					)
				)
			if extension not in EXTENSIONES_PERMITIDAS:
				raise ErrorPaqueteComplemento(
					_("El paquete contiene un tipo de fichero que un complemento no puede traer ({nombre}); se rechaza.").format(
						nombre=entrada.filename
					)
				)
			try:
				with archivo.open(entrada) as contenido:
					comienzo = contenido.read(4)
			except (zipfile.BadZipFile, OSError, RuntimeError) as error:
				raise ErrorPaqueteComplemento(_("El paquete del complemento está dañado.")) from error
			if comienzo.startswith(_FIRMAS_EJECUTABLES):
				raise ErrorPaqueteComplemento(
					_("El paquete contiene un programa disfrazado de datos ({nombre}); se rechaza.").format(nombre=entrada.filename)
				)
			if partes[-1] == actualizador.FICHA_COMPLEMENTO and len(partes) <= 2:
				fichas.append(entrada)
		if len(fichas) != 1:
			raise ErrorPaqueteComplemento(_("El paquete no contiene una ficha de complemento válida; se rechaza."))
		try:
			ficha = json.loads(archivo.read(fichas[0]).decode("utf-8-sig"))
		except (UnicodeDecodeError, ValueError, zipfile.BadZipFile, OSError) as error:
			raise ErrorPaqueteComplemento(_("La ficha del complemento está dañada; se rechaza.")) from error
	identificador = str(ficha.get("id") or "") if isinstance(ficha, dict) else ""
	if not _PATRON_ID.match(identificador):
		raise ErrorPaqueteComplemento(_("El identificador del complemento no es válido; se rechaza."))
	if id_esperado is not None and identificador != id_esperado:
		raise ErrorPaqueteComplemento(
			_("El paquete descargado es del complemento «{recibido}» y no de «{pedido}»; se rechaza.").format(
				recibido=identificador, pedido=id_esperado
			)
		)
	return identificador


# ── Instalar, actualizar, quitar y volver atrás ──────────────────────────────


def _instalador_por_defecto(ruta_zip: Path) -> str:
	from app.dominio.catalogo import instalar_complemento

	return instalar_complemento(ruta_zip)


def _validador_por_defecto(carpeta: Path) -> list:
	from app.dominio.catalogo import validar_complemento

	return validar_complemento(carpeta)


def _version_en(carpeta: Path) -> str:
	try:
		ficha = json.loads((carpeta / actualizador.FICHA_COMPLEMENTO).read_text(encoding="utf-8-sig"))
	except OSError, ValueError:
		return ""
	return str(ficha.get("version") or "") if isinstance(ficha, dict) else ""


def _borrar_carpeta(carpeta: Path) -> None:
	if carpeta.exists():
		shutil.rmtree(carpeta)


def _guardar_anterior(identificador: str) -> Path | None:
	"""Copia la versión instalada a una carpeta provisional de ``data/backups/complementos``.

	Es provisional hasta saber cómo acaba el intento: si va bien,
	:func:`_consolidar_anterior` la convierte en «la versión anterior»; si va
	mal, :func:`_restaurar` la devuelve a su sitio y la copia que hubiera de
	antes se conserva.
	"""
	instalada = paths.ruta_complementos() / identificador
	if not instalada.is_dir():
		return None
	provisional = carpeta_anteriores() / f"{identificador}.intento"
	_borrar_carpeta(provisional)
	provisional.parent.mkdir(parents=True, exist_ok=True)
	shutil.copytree(instalada, provisional)
	return provisional


def _consolidar_anterior(identificador: str, respaldo: Path | None) -> None:
	"""La copia provisional pasa a ser la versión anterior a la que se puede volver."""
	if respaldo is None:
		return
	destino = carpeta_anteriores() / identificador
	try:
		_borrar_carpeta(destino)
		respaldo.rename(destino)
	except OSError:
		log.warning("No se pudo conservar la versión anterior de %s", identificador, exc_info=True)


def _restaurar(identificador: str, respaldo: Path | None) -> None:
	"""Deja el complemento como estaba antes del intento (o lo quita si no existía)."""
	instalada = paths.ruta_complementos() / identificador
	_borrar_carpeta(instalada)
	if respaldo is not None and respaldo.is_dir():
		shutil.copytree(respaldo, instalada)
		_borrar_carpeta(respaldo)
		log.info("Complemento «%s» devuelto a la versión %s", identificador, _version_en(instalada))


def _errores_de(avisos: list) -> list:
	"""De los avisos de ``validar_complemento``, los que impiden usar el complemento."""
	return [aviso for aviso in avisos if getattr(aviso, "gravedad", "") == "error"]


def _anotar(identificador: str, datos: dict | None) -> None:
	registro = leer_registro()
	if datos is None:
		registro["instalados"].pop(identificador, None)
	else:
		registro["instalados"][identificador] = datos
	_guardar_registro(registro)


def instalar(
	complemento: ComplementoEnLinea,
	*,
	instalador: Instalador | None = None,
	validador: Validador | None = None,
	al_progresar: Callable[[int, int], Any] | None = None,
	cancelacion: Any = None,
	version_app: str = APP_VERSION,
) -> ResultadoInstalacion:
	"""Descarga, revisa e instala (o actualiza) un complemento. Llamar fuera del hilo de la interfaz.

	Pasos: comprobar que sirve para esta versión de la aplicación; descargar
	verificando tamaño y SHA-256; revisar que el paquete es solo datos; guardar
	la versión instalada; instalar; validar. Si la instalación falla o la
	versión nueva no pasa la validación, se vuelve a dejar la anterior.

	:param instalador: ``funcion(ruta_zip) -> id``; por defecto,
		``app.dominio.catalogo.instalar_complemento``.
	:param validador: ``funcion(carpeta) -> list[Aviso]``; por defecto,
		``app.dominio.catalogo.validar_complemento``.
	:param al_progresar: ``funcion(bytes_hechos, bytes_totales)``.
	:raises ErrorComplementoEnLinea: con un mensaje para el usuario.
	"""
	instalador = instalador or _instalador_por_defecto
	validador = validador or _validador_por_defecto
	if complemento.version_minima_app and _es_mas_nueva(complemento.version_minima_app, version_app):
		raise ErrorComplementoEnLinea(
			_("«{nombre}» necesita la versión {minima} de {aplicacion} o posterior. Actualice primero la aplicación.").format(
				nombre=complemento.nombre, minima=complemento.version_minima_app, aplicacion=NOMBRE_APLICACION
			)
		)
	destino = _carpeta_descargas() / descargas.nombre_seguro(f"{complemento.id}-{complemento.version}{EXTENSION}")
	try:
		descargas.descargar(
			complemento.url,
			destino,
			sha256=complemento.sha256,
			tamano=complemento.tamano,
			al_progresar=(lambda hecho, _total: al_progresar(hecho, complemento.tamano)) if al_progresar else None,
			cancelacion=cancelacion,
		)
	except descargas.DescargaCancelada as error:
		raise OperacionCancelada(_("Descarga cancelada.")) from error
	except descargas.ErrorIntegridad as error:
		raise ErrorPaqueteComplemento(
			_("El paquete de «{nombre}» no coincide con el del catálogo firmado y se ha descartado.").format(nombre=complemento.nombre)
		) from error
	except red.ErrorRed as error:
		raise _error_de_red(error) from error
	except OSError as error:
		log.exception("Fallo de disco al descargar el complemento %s", complemento.id)
		raise ErrorComplementoEnLinea(red.clasificar_error(error).mensaje) from error
	try:
		revisar_paquete(destino, complemento.id)
		with _cerrojo:
			return _instalar_descargado(complemento, destino, instalador, validador)
	finally:
		try:
			destino.unlink(missing_ok=True)
		except OSError:
			log.warning("No se pudo borrar el paquete descargado %s", destino, exc_info=True)


def _instalar_descargado(
	complemento: ComplementoEnLinea, ruta_zip: Path, instalador: Instalador, validador: Validador
) -> ResultadoInstalacion:
	"""Instala un paquete ya descargado y revisado, con vuelta atrás si algo falla."""
	instalada = paths.ruta_complementos() / complemento.id
	version_anterior = _version_en(instalada) if instalada.is_dir() else ""
	era_de_serie = False
	if instalada.is_dir():
		anterior = instalados().get(complemento.id)
		era_de_serie = bool(anterior and anterior.de_serie)
	try:
		respaldo = _guardar_anterior(complemento.id)
	except OSError as error:
		log.exception("No se pudo guardar la versión anterior de %s", complemento.id)
		raise ErrorComplementoEnLinea(
			_("No se ha podido guardar la versión instalada de «{nombre}»; no se actualiza. {detalle}").format(
				nombre=complemento.nombre, detalle=red.clasificar_error(error).mensaje
			)
		) from error
	try:
		instalado = instalador(ruta_zip)
	except Exception as error:  # noqa: BLE001 - el instalador es inyectable: cualquier fallo debe dejar lo anterior
		log.warning("La instalación de %s falló: %s", complemento.id, error, exc_info=True)
		_restaurar(complemento.id, respaldo)
		raise ErrorComplementoEnLinea(
			_("No se ha podido instalar «{nombre}»: {detalle}").format(nombre=complemento.nombre, detalle=error)
		) from error
	if instalado != complemento.id:
		log.error("El instalador devolvió «%s» al instalar «%s»", instalado, complemento.id)
		_restaurar(complemento.id, respaldo)
		raise ErrorPaqueteComplemento(_("El paquete instalado no corresponde al complemento pedido; se ha deshecho."))
	avisos = list(validador(instalada))
	errores = _errores_de(avisos)
	if errores:
		detalle = "; ".join(str(getattr(aviso, "mensaje", aviso)) for aviso in errores[:3])
		log.warning("La versión %s de %s no pasa la validación: %s", complemento.version, complemento.id, detalle)
		_restaurar(complemento.id, respaldo)
		if version_anterior:
			mensaje = _("La versión {version} de «{nombre}» no es válida y se ha vuelto a la {anterior}. Motivo: {detalle}").format(
				version=complemento.version, nombre=complemento.nombre, anterior=version_anterior, detalle=detalle
			)
		else:
			mensaje = _("«{nombre}» no es válido y no se ha instalado. Motivo: {detalle}").format(
				nombre=complemento.nombre, detalle=detalle
			)
		raise ErrorValidacionComplemento(mensaje, errores)
	_consolidar_anterior(complemento.id, respaldo)
	_anotar(
		complemento.id,
		{
			"version": complemento.version,
			"origen": "catalogo",
			"sha256": complemento.sha256,
			"de_serie": era_de_serie,
			"fecha": datetime.now(timezone.utc).isoformat(timespec="seconds"),
		},
	)
	log.info("Complemento «%s» %s (antes: %s)", complemento.id, complemento.version, version_anterior or "no instalado")
	return ResultadoInstalacion(complemento.id, complemento.nombre, complemento.version, version_anterior, avisos=tuple(avisos))


def instalar_varios(
	complementos: Iterable[ComplementoEnLinea],
	*,
	instalador: Instalador | None = None,
	validador: Validador | None = None,
	al_progresar: Callable[[int, int, ComplementoEnLinea, int, int], Any] | None = None,
	cancelacion: Any = None,
	version_app: str = APP_VERSION,
) -> list[ResultadoInstalacion]:
	"""Instala o actualiza varios complementos, uno tras otro.

	El fallo de uno no detiene a los demás: cada resultado dice si fue bien o
	su error. Al cancelar se dejan de procesar los que faltan.

	:param al_progresar: ``funcion(indice, cuantos, complemento, bytes_hechos, bytes_totales)``.
	"""
	lista = list(complementos)
	resultados: list[ResultadoInstalacion] = []
	for indice, complemento in enumerate(lista, start=1):
		if descargas._esta_cancelado(cancelacion):
			resultados.append(ResultadoInstalacion(complemento.id, complemento.nombre, cancelado=True))
			continue

		def progreso(hecho: int, total: int, indice: int = indice, complemento: ComplementoEnLinea = complemento) -> None:
			if al_progresar:
				al_progresar(indice, len(lista), complemento, hecho, total)

		try:
			resultados.append(
				instalar(
					complemento,
					instalador=instalador,
					validador=validador,
					al_progresar=progreso,
					cancelacion=cancelacion,
					version_app=version_app,
				)
			)
		except OperacionCancelada:
			resultados.append(ResultadoInstalacion(complemento.id, complemento.nombre, cancelado=True))
		except ErrorComplementoEnLinea as error:
			log.warning("No se pudo instalar %s: %s", complemento.id, error)
			resultados.append(ResultadoInstalacion(complemento.id, complemento.nombre, error=str(error)))
	return resultados


def desinstalar(identificador: str) -> None:
	"""Quita un complemento instalado por el usuario (y su versión anterior guardada).

	Los complementos de serie no se desinstalan: forman parte de la aplicación
	y la siguiente actualización los volvería a traer. Si uno de serie se
	actualizó desde el catálogo, :func:`volver_a_anterior` lo deja como vino.
	Los entornos que usen el complemento quitado mostrarán sus objetos como cajas.

	:raises ErrorComplementoEnLinea: si no está instalado o es de serie.
	"""
	if not _PATRON_ID.match(identificador):
		raise ErrorComplementoEnLinea(_("El identificador del complemento no es válido."))
	with _cerrojo:
		local = instalados().get(identificador)
		if local is None:
			raise ErrorComplementoEnLinea(_("El complemento «{id}» no está instalado.").format(id=identificador))
		if local.de_serie:
			raise ErrorComplementoEnLinea(_("«{nombre}» viene con la aplicación y no se puede desinstalar.").format(nombre=local.nombre))
		try:
			_borrar_carpeta(local.carpeta)
			_borrar_carpeta(carpeta_anteriores() / identificador)
			_anotar(identificador, None)
		except OSError as error:
			log.exception("No se pudo desinstalar %s", identificador)
			raise ErrorComplementoEnLinea(
				_("No se ha podido desinstalar «{nombre}». {detalle}").format(
					nombre=local.nombre, detalle=red.clasificar_error(error).mensaje
				)
			) from error
	log.info("Complemento «%s» desinstalado", identificador)


def volver_a_anterior(identificador: str, validador: Validador | None = None) -> str:
	"""Vuelve a la versión anterior guardada de un complemento y devuelve su número.

	La versión que se retira no se conserva: se puede volver a instalar desde
	el catálogo. Si la versión guardada no pasa la validación, no se cambia nada.

	:raises ErrorComplementoEnLinea: si no hay versión anterior o no es válida.
	"""
	validador = validador or _validador_por_defecto
	if not _PATRON_ID.match(identificador):
		raise ErrorComplementoEnLinea(_("El identificador del complemento no es válido."))
	with _cerrojo:
		respaldo = carpeta_anteriores() / identificador
		if not hay_anterior(identificador):
			raise ErrorComplementoEnLinea(_("No se guarda ninguna versión anterior de «{id}».").format(id=identificador))
		errores = _errores_de(list(validador(respaldo)))
		if errores:
			raise ErrorValidacionComplemento(
				_("La versión anterior guardada de «{id}» no es válida; no se cambia nada.").format(id=identificador), errores
			)
		instalada = paths.ruta_complementos() / identificador
		retirada = instalada.with_name(f".{identificador}.retirado")
		try:
			_borrar_carpeta(retirada)
			if instalada.is_dir():
				instalada.rename(retirada)
			try:
				shutil.copytree(respaldo, instalada)
			except OSError:
				_borrar_carpeta(instalada)
				if retirada.is_dir():
					retirada.rename(instalada)
				raise
			_borrar_carpeta(retirada)
			_borrar_carpeta(respaldo)
			version = _version_en(instalada)
			de_serie = ids_de_serie()
			registrado = leer_registro()["instalados"].get(identificador)
			if de_serie is not None and de_serie.get(identificador) == version:
				# Vuelve a estar tal como vino con la aplicación: deja de ser «del usuario».
				_anotar(identificador, None)
			elif isinstance(registrado, dict):
				if registrado.get("de_serie"):
					_anotar(identificador, None)
				else:
					_anotar(identificador, {**registrado, "version": version, "sha256": ""})
		except OSError as error:
			log.exception("No se pudo volver a la versión anterior de %s", identificador)
			raise ErrorComplementoEnLinea(
				_("No se ha podido volver a la versión anterior de «{id}». {detalle}").format(
					id=identificador, detalle=red.clasificar_error(error).mensaje
				)
			) from error
	log.info("Complemento «%s» devuelto a la versión %s", identificador, version)
	return version
