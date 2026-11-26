"""Entornos que el alumno puede elegir: dónde están, cómo se abren y cómo se dicen sus fallos.

Los paquetes ``.elab`` se buscan en ``data/entornos`` (los del profesional),
en la carpeta de entornos que el profesional haya elegido en el Estudio y en
``data/ejemplos`` (los que viajan con el programa). Con ``APP_DATA_DIR``
redirigida, los ejemplos y los complementos se siguen encontrando junto al
programa, igual que los sonidos de serie.

Abrir un paquete nunca tira el reproductor: un fichero dañado se convierte en
un ``ErrorEntorno`` cuyo mensaje se puede decir tal cual al alumno.
"""

from __future__ import annotations

import logging
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.audio.base import carpetas_de_serie
from app.core import paths
from app.core.i18n import _, _n
from app.dominio.catalogo import Catalogo
from app.dominio.formato import ErrorFormato, Paquete, cargar_paquete, leer_manifiesto
from app.dominio.modelo import Entorno

log = logging.getLogger(__name__)

EXTENSION = ".elab"
ORIGEN_PROPIO = "propio"
ORIGEN_EJEMPLO = "ejemplo"
ORIGEN_ARGUMENTO = "argumento"


class ErrorEntorno(Exception):
	"""Un entorno no se puede abrir. El mensaje está pensado para decírselo al alumno."""


@dataclass(frozen=True)
class FichaEntorno:
	"""Un paquete que se puede elegir en el menú, sin abrirlo entero."""

	ruta: Path
	nombre: str
	origen: str
	valido: bool = True


def _carpetas(config: Any) -> list[tuple[Path, str]]:
	"""(carpeta, origen) donde se buscan entornos, sin repetir y solo las que existen."""
	candidatas: list[tuple[Path, str]] = [(paths.ruta_datos() / "entornos", ORIGEN_PROPIO)]
	propia = str(config.obtener("editor.carpeta_entornos", "") or "").strip() if config is not None else ""
	if propia:
		candidatas.append((Path(propia).expanduser(), ORIGEN_PROPIO))
	candidatas.extend((carpeta, ORIGEN_EJEMPLO) for carpeta in carpetas_de_serie("ejemplos"))
	vistas: list[tuple[Path, str]] = []
	for carpeta, origen in candidatas:
		try:
			existe = carpeta.is_dir()
		except OSError:
			existe = False
		if existe and all(carpeta != otra for otra, _origen in vistas):
			vistas.append((carpeta, origen))
	return vistas


def _ficha(ruta: Path, origen: str) -> FichaEntorno:
	try:
		manifiesto = leer_manifiesto(ruta)
	except (ErrorFormato, OSError, ValueError, zipfile.BadZipFile) as error:
		log.warning("El paquete %s no se puede leer; se lista como dañado (%s).", ruta.name, error)
		return FichaEntorno(ruta, ruta.stem, origen, valido=False)
	return FichaEntorno(ruta, str(manifiesto.get("nombre") or ruta.stem), origen)


def listar(config: Any = None, extra: Path | None = None) -> list[FichaEntorno]:
	"""Los entornos disponibles: el recibido por argumento primero, luego los del profesional y los de ejemplo."""
	fichas: list[FichaEntorno] = []
	vistos: set[Path] = set()

	def anadir(ruta: Path, origen: str) -> None:
		try:
			clave = ruta.resolve()
		except OSError:
			clave = ruta
		if clave in vistos:
			return
		vistos.add(clave)
		fichas.append(_ficha(ruta, origen))

	if extra is not None and extra.is_file():
		anadir(extra, ORIGEN_ARGUMENTO)
	for carpeta, origen in _carpetas(config):
		try:
			rutas = sorted(p for p in carpeta.glob(f"*{EXTENSION}") if p.is_file())
		except OSError:
			log.warning("No se pudo leer la carpeta de entornos %s", carpeta, exc_info=True)
			continue
		for ruta in rutas:
			anadir(ruta, origen)
	return fichas


def abrir(ruta: Path | str) -> Paquete:
	"""Abre un paquete. Lanza ``ErrorEntorno`` con una frase clara si falta o está dañado."""
	origen = Path(ruta)
	if not origen.is_file():
		raise ErrorEntorno(_("No se encuentra el entorno «{nombre}». Puede que se haya movido o borrado.").format(nombre=origen.stem))
	try:
		paquete = cargar_paquete(origen)
	except ErrorFormato as error:
		# Sin traza: un paquete dañado no es un fallo del programa, y el mensaje ya dice qué le pasa.
		log.warning("Paquete no válido: %s (%s)", origen.name, error)
		raise ErrorEntorno(
			_("No se puede abrir el entorno «{nombre}». {detalle}").format(nombre=origen.stem, detalle=str(error))
		) from error
	except (OSError, ValueError, KeyError, TypeError, AttributeError, zipfile.BadZipFile) as error:
		log.exception("Paquete dañado: %s", origen.name)
		raise ErrorEntorno(
			_("No se puede abrir el entorno «{nombre}»: el fichero está dañado. Pide a tu profesor que lo vuelva a guardar.").format(
				nombre=origen.stem
			)
		) from error
	if not paquete.entorno.plantas:
		raise ErrorEntorno(
			_("El entorno «{nombre}» está vacío: no tiene ninguna planta.").format(nombre=paquete.entorno.nombre or origen.stem)
		)
	return paquete


def describir(paquete: Paquete) -> str:
	"""Una frase con lo que es el entorno: su descripción, cuántas plantas y cuántas actividades trae."""
	entorno = paquete.entorno
	partes: list[str] = []
	if entorno.descripcion.strip():
		partes.append(entorno.descripcion.strip().rstrip("."))
	plantas = len(entorno.plantas)
	espacios = sum(len(planta.espacios) for planta in entorno.plantas)
	partes.append(
		_("{plantas} y {espacios}").format(
			plantas=_n("{n} planta", "{n} plantas", plantas).format(n=plantas),
			espacios=_n("{n} lugar", "{n} lugares", espacios).format(n=espacios),
		)
	)
	actividades = len(paquete.actividades)
	if actividades:
		partes.append(_n("{n} actividad", "{n} actividades", actividades).format(n=actividades))
	else:
		partes.append(_("Sin actividades: solo exploración libre"))
	return ". ".join(partes) + "."


def cargar_catalogo() -> Catalogo:
	"""El catálogo de complementos: los de la carpeta de datos activa y los que viajan con el programa."""
	try:
		return Catalogo.cargar(carpetas_de_serie("plugins"))
	except OSError, ValueError:
		log.exception("No se pudo cargar el catálogo de complementos; los objetos se verán como cajas.")
		return Catalogo()


def complementos_que_faltan(entorno: Entorno, catalogo: Catalogo) -> list[str]:
	"""Identificadores de los complementos que usa el entorno y no están instalados."""
	objetos = [objeto for planta in entorno.plantas for objeto in planta.objetos]
	tipos = catalogo.tipos_que_faltan(objetos)
	return sorted({tipo.split("/", 1)[0] for tipo in tipos})


def espacios_para_grabadora(entorno: Entorno) -> list[dict[str, Any]]:
	"""Los espacios del entorno en la forma que pide ``Grabadora`` (para saber cuáles se visitan)."""
	return [
		{"id": espacio.id, "nombre": espacio.nombre, "planta": planta.id, "contorno": [list(punto) for punto in espacio.contorno]}
		for planta in entorno.plantas
		for espacio in planta.espacios
		if not espacio.macizo
	]
