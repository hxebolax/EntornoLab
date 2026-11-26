"""Descarga de ficheros reanudable, verificada, cancelable y atómica.

Por qué existe: una descarga ingenua deja un fichero a medias con el nombre
definitivo si se corta, no se puede cancelar ni continuar, y se fía del
tamaño que diga el servidor. Aquí:

1. Se escribe por bloques en ``<nombre>.parcial`` junto al destino (mismo
   disco: así ``os.replace`` es atómico).
2. Si ya hay un ``.parcial``, se pide solo el resto con ``Range`` (e
   ``If-Range`` con el ETag guardado, para no mezclar dos versiones del
   fichero). Con 206 se continúa; con 200 se empieza de cero.
3. Nunca se escriben más bytes que ``tamano`` (el anunciado en un índice
   firmado) o ``tamano_maximo``: un servidor no puede llenar el disco.
4. Se comprueban el tamaño y el SHA-256 y solo entonces se renombra. Un
   fichero que no coincide se borra.
5. El progreso se limita a unas pocas llamadas por segundo y la descarga se
   cancela con un ``threading.Event``, un token con ``cancelado`` o una función.

Las peticiones salen por ``app.core.red``: https, certificados verificados y
ningún dato personal.

Procede de la plantilla del agente «red-http», adaptada a ``urllib``.
"""

from __future__ import annotations

import hashlib
import hmac
import http.client
import json
import logging
import os
import re
import time
import unicodedata
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from app.core import red
from app.core.i18n import _
from app.core.red import ErrorRed

log = logging.getLogger(__name__)

SUFIJO_PARCIAL = ".parcial"
SUFIJO_METADATOS = ".parcial.json"
TAMANO_BLOQUE = 64 * 1024


class ErrorDescarga(ErrorRed):
	"""Fallo de una descarga con mensaje para el usuario (ver ``ErrorRed``)."""


class DescargaCancelada(ErrorDescarga):
	"""El usuario (o el cierre de la aplicación) canceló la descarga."""

	def __init__(self, conservado: bool) -> None:
		super().__init__(_("Descarga cancelada."), categoria="cancelado")
		#: True si la parte descargada sigue en disco para continuar otro día.
		self.parcial_conservado = conservado


class ErrorIntegridad(ErrorDescarga):
	"""El fichero descargado no coincide con el tamaño o la huella SHA-256 esperados."""


@dataclass(frozen=True)
class ResultadoDescarga:
	"""Qué se descargó y cómo."""

	ruta: Path
	tamano: int
	sha256: str
	reanudada: bool
	segundos: float


# ── Nombres de fichero seguros ───────────────────────────────────────────────

_PROHIBIDOS = re.compile(r'[<>:"/\\|?*\x00-\x1f]')
# Nombres de dispositivo de Windows: no valen ni con extensión («NUL.txt»).
_RESERVADOS = frozenset(
	{"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$", "CLOCK$"} | {f"COM{i}" for i in "123456789"} | {f"LPT{i}" for i in "123456789"}
)


def nombre_seguro(nombre: str | None, respaldo: str = "descarga", max_longitud: int = 120) -> str:
	"""Convierte un nombre cualquiera en un nombre de fichero válido y sin trampas en Windows.

	Se queda con la última parte (nada de ``..\\`` ni rutas absolutas), quita
	caracteres de control y prohibidos, los puntos y espacios finales, y
	antepone ``_`` a los nombres de dispositivo (``CON``, ``NUL``...). El
	servidor no decide dónde se escribe.
	"""
	texto = unicodedata.normalize("NFC", str(nombre or ""))
	texto = texto.replace("\\", "/").rsplit("/", 1)[-1]
	texto = "".join(c for c in texto if unicodedata.category(c) not in ("Cc", "Cf"))
	texto = _PROHIBIDOS.sub("_", texto)
	texto = re.sub(r"\s+", " ", texto).strip().rstrip(". ")
	if not texto or set(texto) <= {".", "_", " "}:
		texto = respaldo
	base, punto, extension = texto.rpartition(".")
	if not punto or not base or len(extension) > 16 or " " in extension:
		base, extension = texto, ""
	if base.split(".")[0].strip().upper() in _RESERVADOS:
		base = "_" + base
	sufijo = f".{extension}" if extension else ""
	base = base[: max(1, max_longitud - len(sufijo))]
	return (base.rstrip(". ") or respaldo) + sufijo


# ── Utilidades ───────────────────────────────────────────────────────────────


def sha256_de(ruta: str | os.PathLike[str]) -> str:
	"""SHA-256 de un fichero leído por bloques (no lo carga entero en memoria)."""
	resumen = hashlib.sha256()
	with open(ruta, "rb") as fichero:
		for bloque in iter(lambda: fichero.read(1024 * 1024), b""):
			resumen.update(bloque)
	return resumen.hexdigest()


def _esta_cancelado(cancelacion: Any) -> bool:
	"""Admite ``threading.Event``, cualquier objeto con ``cancelado`` o una función."""
	if cancelacion is None:
		return False
	if hasattr(cancelacion, "cancelado"):
		return bool(cancelacion.cancelado)
	if hasattr(cancelacion, "is_set"):
		return bool(cancelacion.is_set())
	return bool(cancelacion())


def _borrar(*rutas: Path) -> None:
	for ruta in rutas:
		try:
			ruta.unlink(missing_ok=True)
		except OSError:
			log.warning("No se pudo borrar %s.", ruta, exc_info=True)


def _leer_metadatos(ruta: Path) -> dict:
	"""ETag y fecha con los que se empezó el parcial; vacío si no hay o no se entiende."""
	try:
		datos = json.loads(ruta.read_text(encoding="utf-8"))
	except FileNotFoundError:
		return {}
	except OSError, ValueError:
		log.debug("Metadatos de reanudación ilegibles en %s; se ignoran.", ruta, exc_info=True)
		return {}
	return datos if isinstance(datos, dict) else {}


def _guardar_metadatos(ruta: Path, respuesta: http.client.HTTPResponse) -> None:
	"""Guarda el validador para que la reanudación detecte si el fichero cambió."""
	etag = respuesta.headers.get("ETag") or ""
	datos = {"etag": None if etag.startswith("W/") else etag or None, "last_modified": respuesta.headers.get("Last-Modified")}
	try:
		ruta.write_text(json.dumps(datos), encoding="utf-8")
	except OSError:
		log.debug("No se pudieron guardar los metadatos de reanudación en %s.", ruta, exc_info=True)


def _inicio_y_total(valor: str | None) -> tuple[int | None, int | None]:
	"""De ``bytes 100-199/1000`` devuelve (100, 1000); de ``bytes */1000``, (None, 1000)."""
	coincidencia = re.match(r"\s*bytes\s+(?:(\d+)-\d+|\*)/(\d+|\*)", valor or "")
	if not coincidencia:
		return None, None
	inicio = int(coincidencia.group(1)) if coincidencia.group(1) else None
	total = int(coincidencia.group(2)) if coincidencia.group(2) != "*" else None
	return inicio, total


class _Progreso:
	"""Limita las llamadas de progreso a ``por_segundo`` (la última siempre llega)."""

	def __init__(self, funcion: Callable[[int, int | None], Any] | None, por_segundo: float) -> None:
		self._funcion = funcion
		self._intervalo = 1.0 / por_segundo if por_segundo > 0 else 0.0
		self._ultima = 0.0

	def __call__(self, hecho: int, total: int | None, final: bool = False) -> None:
		if self._funcion is None:
			return
		ahora = time.monotonic()
		if not final and ahora - self._ultima < self._intervalo:
			return
		self._ultima = ahora
		self._funcion(hecho, total)


# ── Descarga ─────────────────────────────────────────────────────────────────


def descargar(
	url: str,
	destino: str | os.PathLike[str],
	sha256: str | None = None,
	tamano: int | None = None,
	*,
	reanudar: bool = True,
	al_progresar: Callable[[int, int | None], Any] | None = None,
	cancelacion: Any = None,
	tamano_maximo: int | None = None,
	conservar_parcial: bool = True,
	progresos_por_segundo: float = 4.0,
	tiempo: float | None = None,
) -> ResultadoDescarga:
	"""Descarga ``url`` en ``destino`` (sustituyéndolo). Llamar SIEMPRE fuera del hilo de la interfaz.

	:param sha256: huella esperada en hexadecimal; si no coincide se borra lo
		descargado y se lanza ``ErrorIntegridad``.
	:param tamano: tamaño exacto esperado (el de un índice firmado). Hace de
		tope durante la descarga y se comprueba al final.
	:param al_progresar: ``funcion(bytes_hechos, bytes_totales_o_None)``, en el
		hilo de la descarga.
	:param cancelacion: ``threading.Event``, token con ``cancelado`` o función.
	:param tamano_maximo: tope de bytes cuando no se conoce ``tamano``.
	:param conservar_parcial: al cancelar o cortarse, conservar lo descargado
		para continuar en el siguiente intento.
	:raises DescargaCancelada, ErrorIntegridad, ErrorDescarga, ErrorRed: todas
		con ``mensaje_usuario`` en español.
	"""
	red.comprobar_url(url)
	final = Path(destino)
	final.parent.mkdir(parents=True, exist_ok=True)
	parcial = final.with_name(final.name + SUFIJO_PARCIAL)
	metadatos_ruta = final.with_name(final.name + SUFIJO_METADATOS)
	tope = tamano if tamano is not None else tamano_maximo
	inicio_reloj = time.monotonic()
	progreso = _Progreso(al_progresar, progresos_por_segundo)
	reanudada = False
	hecho = 0
	total: int | None = tamano

	for _vuelta in range(2):  # la segunda, solo si el parcial no sirve y hay que empezar de cero
		desplazamiento = parcial.stat().st_size if (reanudar and parcial.is_file()) else 0
		if tope is not None and desplazamiento > tope:
			_borrar(parcial, metadatos_ruta)
			desplazamiento = 0
		if tamano is not None and desplazamiento == tamano:
			# Ya estaba entero (se cortó justo al final o falló el renombrado).
			hecho, reanudada = desplazamiento, True
			break
		cabeceras: dict[str, str] = {}
		if desplazamiento:
			cabeceras["Range"] = f"bytes={desplazamiento}-"
			metadatos = _leer_metadatos(metadatos_ruta)
			validador = metadatos.get("etag") or metadatos.get("last_modified")
			if validador:
				cabeceras["If-Range"] = str(validador)
		respuesta = red.abrir(url, cabeceras, tiempo=tiempo, cancelacion=cancelacion, estados_aceptados=(416,))
		try:
			if respuesta.status == 416:
				_inicio, total_servidor = _inicio_y_total(respuesta.headers.get("Content-Range"))
				if desplazamiento and total_servidor == desplazamiento and tamano in (None, desplazamiento):
					hecho, reanudada = desplazamiento, True
					break
				log.info("El servidor rechazó continuar %s desde el byte %d; se empieza de cero.", url, desplazamiento)
				_borrar(parcial, metadatos_ruta)
				continue
			anadir = False
			if respuesta.status == 206 and desplazamiento:
				inicio, total_servidor = _inicio_y_total(respuesta.headers.get("Content-Range"))
				if inicio != desplazamiento:
					log.warning("Rango inesperado (%s) en %s; se empieza de cero.", respuesta.headers.get("Content-Range"), url)
					_borrar(parcial, metadatos_ruta)
					continue
				anadir = True
				_comprobar_tamano_anunciado(total_servidor, tamano, url, parcial, metadatos_ruta)
				total = tamano if tamano is not None else total_servidor
				log.info("Reanudando %s desde el byte %d.", url, desplazamiento)
			else:
				if desplazamiento:
					log.info("El servidor no admite continuar %s (o el fichero cambió): se descarga entero.", url)
				longitud = respuesta.headers.get("Content-Length") or ""
				_comprobar_tamano_anunciado(int(longitud) if longitud.isdigit() else None, tamano, url, parcial, metadatos_ruta)
				total = tamano if tamano is not None else (int(longitud) if longitud.isdigit() else None)
				_guardar_metadatos(metadatos_ruta, respuesta)
			if tope is not None and total is not None and total > tope:
				raise ErrorDescarga(
					_("El fichero es más grande de lo permitido ({megas:.0f} MB).").format(megas=total / 1_048_576),
					categoria="servidor",
					detalle=f"{total} bytes > máximo {tope} en {url}",
				)
			reanudada = anadir
			hecho = _escribir(respuesta, parcial, anadir, total, tope, progreso, cancelacion, conservar_parcial, metadatos_ruta, url)
		finally:
			respuesta.close()
		break
	else:
		raise ErrorDescarga(_("El servidor no permite descargar este fichero."), categoria="servidor", detalle=url)

	if total is not None and hecho != total:
		if not conservar_parcial:
			_borrar(parcial, metadatos_ruta)
		raise ErrorDescarga(
			_("La descarga se ha cortado antes de terminar. Vuelva a intentarlo: continuará donde se quedó."),
			categoria="red",
			reintentar=True,
			detalle=f"{hecho} de {total} bytes en {url}",
		)
	huella = sha256_de(parcial)
	if sha256 and not hmac.compare_digest(huella.lower(), sha256.strip().lower()):
		_borrar(parcial, metadatos_ruta)
		log.error("SHA-256 incorrecto en %s: esperado %s, obtenido %s", url, sha256, huella)
		raise ErrorIntegridad(
			_("El fichero descargado no supera la comprobación de integridad y se ha descartado. No se instalará."),
			categoria="seguridad",
			reintentar=True,
			detalle=f"SHA-256 {huella} distinto de {sha256} en {url}",
		)
	os.replace(parcial, final)
	_borrar(metadatos_ruta)
	progreso(hecho, total, final=True)
	resultado = ResultadoDescarga(final, hecho, huella, reanudada, time.monotonic() - inicio_reloj)
	log.info("Descargado %s en %s (%d bytes en %.1f s%s).", url, final.name, hecho, resultado.segundos, ", reanudada" if reanudada else "")
	return resultado


def _comprobar_tamano_anunciado(del_servidor: int | None, esperado: int | None, url: str, *restos: Path) -> None:
	"""Si el servidor ofrece un fichero de otro tamaño que el firmado, no es el mismo fichero.

	Se rechaza antes de descargar nada: no es una descarga cortada que convenga
	reintentar, sino un fichero distinto del que se anunció.
	"""
	if del_servidor is None or esperado is None or del_servidor == esperado:
		return
	_borrar(*restos)
	raise ErrorIntegridad(
		_("El fichero del servidor no tiene el tamaño anunciado; se ha descartado por seguridad."),
		categoria="seguridad",
		detalle=f"{del_servidor} bytes en el servidor, {esperado} esperados en {url}",
	)


def _escribir(
	respuesta: http.client.HTTPResponse,
	parcial: Path,
	anadir: bool,
	total: int | None,
	tope: int | None,
	progreso: _Progreso,
	cancelacion: Any,
	conservar_parcial: bool,
	metadatos_ruta: Path,
	url: str,
) -> int:
	"""Vuelca el cuerpo al parcial comprobando cancelación y tamaño en cada bloque."""
	hecho = parcial.stat().st_size if anadir else 0
	with open(parcial, "ab" if anadir else "wb") as fichero:
		while True:
			if _esta_cancelado(cancelacion):
				fichero.close()
				if not conservar_parcial:
					_borrar(parcial, metadatos_ruta)
				log.info("Descarga cancelada con %d bytes; parcial %s.", hecho, "conservado" if conservar_parcial else "borrado")
				raise DescargaCancelada(conservar_parcial)
			try:
				bloque = respuesta.read(TAMANO_BLOQUE)
			except (http.client.HTTPException, OSError) as error:
				# IncompleteRead (conexión cortada) es HTTPException, no OSError.
				log.warning("La descarga de %s se cortó con %d bytes: %s", url, hecho, error)
				fichero.close()
				if not conservar_parcial:
					_borrar(parcial, metadatos_ruta)
				raise ErrorDescarga(
					_("La descarga se ha cortado antes de terminar. Vuelva a intentarlo: continuará donde se quedó."),
					categoria="red",
					reintentar=True,
					detalle=f"{type(error).__name__} con {hecho} bytes en {url}",
				) from error
			if not bloque:
				break
			hecho += len(bloque)
			if tope is not None and hecho > tope:
				fichero.close()
				_borrar(parcial, metadatos_ruta)
				raise ErrorIntegridad(
					_("El fichero descargado es mayor de lo anunciado; se ha descartado por seguridad."),
					categoria="seguridad",
					detalle=f"Más de {tope} bytes en {url}",
				)
			fichero.write(bloque)
			progreso(hecho, total)
	return hecho
