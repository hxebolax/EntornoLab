"""Los ficheros del Estudio, sin wx: carpeta de entornos, recientes, ejemplos y copia de recuperación.

- Los entornos del profesional se guardan por defecto en ``data/entornos``
  (o en la carpeta que elija en las preferencias).
- Los recientes se recuerdan en la configuración (``editor.recientes``).
- Cada pocos minutos, si hay cambios sin guardar, se escribe una COPIA DE
  RECUPERACIÓN en ``data/temp/recuperacion``. No toca el fichero del
  profesional: sirve solo para ofrecerle el trabajo al volver a arrancar si
  el programa o el equipo se cerraron sin guardar. Al guardar o al cerrar
  con normalidad se borra.
"""

from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core import paths
from app.dominio.formato import ErrorFormato, guardar_paquete, identificador_seguro, leer_manifiesto

log = logging.getLogger(__name__)

EXTENSION = ".elab"
COMODIN = "Entornos de EntornoLab (*.elab)|*.elab"


def carpeta_entornos(configuracion: Any = None) -> Path:
	"""Carpeta donde se proponen guardar y abrir los entornos: la de las preferencias o ``data/entornos``."""
	elegida = str(configuracion.obtener("editor.carpeta_entornos", "") or "").strip() if configuracion is not None else ""
	if elegida:
		carpeta = Path(elegida)
		if carpeta.is_dir():
			return carpeta
		log.warning("La carpeta de entornos de las preferencias no existe: %s", carpeta)
	return paths.ruta_entornos()


def nombre_de_fichero(nombre: str) -> str:
	"""Nombre de fichero seguro para un entorno: «Casa de Ana» → «casa-de-ana.elab»."""
	return identificador_seguro(nombre, "entorno") + EXTENSION


def con_extension(ruta: str | Path) -> Path:
	"""La ruta con la extensión ``.elab`` si no la traía."""
	ruta = Path(ruta)
	return ruta if ruta.suffix.lower() == EXTENSION else ruta.with_name(ruta.name + EXTENSION)


# ── Recientes ────────────────────────────────────────────────────────────────


def recientes(configuracion: Any) -> list[Path]:
	"""Entornos abiertos hace poco que siguen existiendo, del más reciente al más antiguo."""
	if configuracion is None:
		return []
	lista = configuracion.obtener("editor.recientes", []) or []
	return [Path(ruta) for ruta in lista if isinstance(ruta, str) and Path(ruta).is_file()]


def anotar_reciente(configuracion: Any, ruta: str | Path) -> None:
	"""Pone un entorno el primero de los recientes (sin repetirlo) y recorta la lista."""
	if configuracion is None:
		return
	maximo = int(configuracion.obtener("editor.max_recientes", 10))
	actual = str(Path(ruta).resolve())
	lista = [r for r in (configuracion.obtener("editor.recientes", []) or []) if isinstance(r, str) and r != actual]
	nueva = ([actual] + lista)[: max(0, maximo)]
	try:
		configuracion.establecer("editor.recientes", nueva)
	except Exception:  # noqa: BLE001 - no poder recordar un reciente no debe estropear abrir ni guardar
		log.exception("No se pudo apuntar el entorno reciente %s", actual)


# ── Ejemplos ─────────────────────────────────────────────────────────────────


def ejemplos() -> list[tuple[Path, str]]:
	"""Entornos de ejemplo que vienen con el programa: (ruta, nombre), por orden de nombre."""
	encontrados: list[tuple[Path, str]] = []
	for ruta in sorted(paths.ruta_ejemplos().glob("*" + EXTENSION)):
		try:
			nombre = str(leer_manifiesto(ruta).get("nombre") or ruta.stem)
		except ErrorFormato, OSError:
			log.warning("No se pudo leer el ejemplo %s", ruta, exc_info=True)
			continue
		encontrados.append((ruta, nombre))
	return sorted(encontrados, key=lambda par: par[1].lower())


# ── Copia de recuperación ────────────────────────────────────────────────────


@dataclass(frozen=True)
class Recuperacion:
	"""Una copia de recuperación que quedó de una sesión que no se cerró bien."""

	ruta: Path
	nombre: str
	ruta_original: Path | None
	fecha: float


def carpeta_recuperacion() -> Path:
	"""``data/temp/recuperacion`` (se crea si falta)."""
	carpeta = paths.ruta_temporales() / "recuperacion"
	carpeta.mkdir(parents=True, exist_ok=True)
	return carpeta


def _ruta_recuperacion(id_entorno: str) -> Path:
	return carpeta_recuperacion() / (identificador_seguro(id_entorno, "entorno") + EXTENSION)


def guardar_recuperacion(contexto: Any) -> Path | None:
	"""Escribe la copia de recuperación del documento abierto si tiene cambios. Devuelve su ruta, o None.

	Nunca lanza: un autoguardado que falla (disco lleno) se registra y no
	interrumpe el trabajo. No cambia la ruta ni el estado «modificado».
	"""
	if contexto.entorno is None or not contexto.modificado:
		return None
	ruta = _ruta_recuperacion(contexto.entorno.id)
	try:
		guardar_paquete(ruta, contexto.entorno, contexto.actividades, contexto.recursos or None)
		ficha = {
			"nombre": contexto.entorno.nombre,
			"ruta_original": str(contexto.ruta_paquete) if contexto.ruta_paquete else "",
			"fecha": time.time(),
		}
		ruta.with_suffix(".json").write_text(json.dumps(ficha, ensure_ascii=False), encoding="utf-8")
	except Exception:  # noqa: BLE001 - el autoguardado es una red de seguridad: si falla, se anota y se sigue
		log.exception("No se pudo escribir la copia de recuperación en %s", ruta)
		return None
	log.debug("Copia de recuperación escrita en %s", ruta)
	return ruta


def borrar_recuperacion(id_entorno: str) -> None:
	"""Borra la copia de recuperación de un entorno (tras guardarlo o descartarlo). No falla si no existe."""
	ruta = _ruta_recuperacion(id_entorno)
	for fichero in (ruta, ruta.with_suffix(".json"), ruta.with_name(ruta.name + ".bak")):
		try:
			fichero.unlink(missing_ok=True)
		except OSError:
			log.warning("No se pudo borrar %s", fichero, exc_info=True)


def recuperaciones() -> list[Recuperacion]:
	"""Copias de recuperación que hay en disco, de la más reciente a la más antigua."""
	encontradas: list[Recuperacion] = []
	for ruta in carpeta_recuperacion().glob("*" + EXTENSION):
		ficha: dict[str, Any] = {}
		try:
			ficha = json.loads(ruta.with_suffix(".json").read_text(encoding="utf-8"))
		except OSError, ValueError:
			log.debug("Copia de recuperación sin ficha legible: %s", ruta)
		original = str(ficha.get("ruta_original") or "")
		encontradas.append(
			Recuperacion(
				ruta=ruta,
				nombre=str(ficha.get("nombre") or ruta.stem),
				ruta_original=Path(original) if original else None,
				fecha=float(ficha.get("fecha") or ruta.stat().st_mtime),
			)
		)
	return sorted(encontradas, key=lambda r: r.fecha, reverse=True)


def descartar_recuperacion(recuperacion: Recuperacion) -> None:
	"""Borra una copia de recuperación que la persona no quiere."""
	for fichero in (
		recuperacion.ruta,
		recuperacion.ruta.with_suffix(".json"),
		recuperacion.ruta.with_name(recuperacion.ruta.name + ".bak"),
	):
		try:
			fichero.unlink(missing_ok=True)
		except OSError:
			log.warning("No se pudo borrar %s", fichero, exc_info=True)
