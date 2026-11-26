"""Red HTTP mínima y prudente: la única puerta de EntornoLab a Internet.

Por qué existe: EntornoLab trata datos de salud y de menores y presume de no
conectarse sin permiso. Concentrar aquí toda petición permite garantizar, en
un solo sitio y con pruebas, que:

- Solo se habla ``https`` (``http`` únicamente contra la propia máquina, para
  las pruebas), con los certificados verificados SIEMPRE. No hay ninguna
  opción para desactivar la verificación.
- No viaja ningún dato personal: las peticiones son ``GET`` sin cuerpo, sin
  galletas, sin ``Referer`` y con un ``User-Agent`` genérico
  (``EntornoLab/<versión>``) que no identifica ni al equipo ni a la persona.
- Ninguna petición cuelga un hilo: siempre hay tiempo de espera.
- Los fallos pasajeros (corte, 429, 5xx) se reintentan unas pocas veces con
  espera creciente, y todo error llega clasificado con un mensaje en español
  que un lector de pantalla lee bien.
- Una redirección nunca baja de ``https`` a ``http``.

Solo biblioteca estándar (``urllib``, ``ssl``). Si ``certifi`` está
instalado, sus certificados se SUMAN a los de Windows: Python solo ve las
raíces que Windows ya tiene en su almacén, y un Windows recién instalado
puede no tener todavía la que firma a GitHub.

Procede de la plantilla del agente «red-http», reescrita sin ``requests``
para no añadir dependencias a una aplicación que apenas usa la red.
"""

from __future__ import annotations

import errno
import http.client
import json
import logging
import socket
import ssl
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Any

from app.core.i18n import _
from app.core.version import APP_VERSION, NOMBRE_APLICACION

log = logging.getLogger(__name__)

# Segundos máximos para conectar y para cada lectura del socket.
TIEMPO_ESPERA = 20.0
# Intentos totales de una petición ante fallos pasajeros.
INTENTOS = 3
# Segundos de la primera espera entre intentos (se duplica en cada uno).
ESPERA_INICIAL = 0.5
# Si el servidor pide esperar más que esto (Retry-After), se falla enseguida
# con un mensaje claro en lugar de dejar un hilo dormido.
ESPERA_MAXIMA_SERVIDOR = 10.0
MAX_REDIRECCIONES = 8
ESTADOS_REINTENTABLES = frozenset({429, 500, 502, 503, 504})
HOSTS_LOCALES = frozenset({"localhost", "127.0.0.1", "::1"})


def user_agent() -> str:
	"""Identificación ante el servidor: nombre y versión de la aplicación, nada más.

	A propósito no incluye sistema operativo, idioma, nombre del equipo ni
	ningún identificador de instalación.
	"""
	return f"{NOMBRE_APLICACION}/{APP_VERSION}"


# ── Errores ──────────────────────────────────────────────────────────────────


class ErrorRed(Exception):
	"""Error de red ya clasificado, con un mensaje apto para el usuario.

	``transitorio`` lo lee el gestor de tareas para no volcar una traza
	completa por un fallo pasajero (no hay conexión, el servidor está caído).
	"""

	def __init__(
		self,
		mensaje_usuario: str,
		categoria: str = "desconocido",
		reintentar: bool = False,
		codigo_http: int | None = None,
		detalle: str = "",
	) -> None:
		super().__init__(detalle or mensaje_usuario)
		self.mensaje_usuario = mensaje_usuario
		self.categoria = categoria
		self.reintentar = reintentar
		self.codigo_http = codigo_http
		self.transitorio = reintentar and categoria in ("red", "servidor")

	def __str__(self) -> str:
		return self.mensaje_usuario


@dataclass(frozen=True)
class ErrorClasificado:
	"""Resultado de :func:`clasificar_error`.

	- ``categoria``: red, servidor, cliente, cancelado, seguridad, local o desconocido.
	- ``mensaje``: frase para mostrar o anunciar.
	- ``reintentar``: si tiene sentido ofrecer «Reintentar».
	- ``detalle``: texto técnico para el registro.
	"""

	categoria: str
	mensaje: str
	reintentar: bool
	codigo_http: int | None = None
	detalle: str = ""


def _mensaje_http(codigo: int) -> tuple[str, bool, str]:
	"""Categoría, si conviene reintentar y mensaje para un estado HTTP de error."""
	if codigo == 404:
		return "cliente", False, _("No se ha encontrado lo que se buscaba en el servidor (error 404).")
	if codigo == 403:
		return "cliente", False, _("El servidor ha denegado el acceso (error 403).")
	if codigo == 429:
		return "servidor", True, _("El servidor está recibiendo demasiadas peticiones. Inténtelo de nuevo más tarde (error 429).")
	if codigo in (500, 502, 503, 504):
		return "servidor", True, _("El servidor no está disponible en este momento (error {codigo}).").format(codigo=codigo)
	if 400 <= codigo < 500:
		return "cliente", False, _("El servidor ha rechazado la petición (error {codigo}).").format(codigo=codigo)
	return "servidor", False, _("El servidor ha respondido con un error (código {codigo}).").format(codigo=codigo)


def _cadena(error: BaseException) -> list[BaseException]:
	"""El error y todas sus causas (``urllib`` envuelve unas excepciones en otras)."""
	vistos: list[BaseException] = []
	pendientes: list[BaseException | None] = [error]
	while pendientes and len(vistos) < 12:
		actual = pendientes.pop(0)
		if actual is None or any(actual is visto for visto in vistos):
			continue
		vistos.append(actual)
		razon = getattr(actual, "reason", None)
		pendientes.extend([actual.__cause__, actual.__context__, razon if isinstance(razon, BaseException) else None])
	return vistos


def clasificar_error(error: BaseException) -> ErrorClasificado:
	"""Traduce cualquier error de red o de disco a categoría y mensaje en español.

	Se usa en los ``al_fallar`` de la interfaz para anunciar ``mensaje`` y
	decidir si se ofrece «Reintentar», y en el registro para ``detalle``.
	"""
	detalle = f"{type(error).__name__}: {error}"[:300]
	if isinstance(error, ErrorRed):
		return ErrorClasificado(error.categoria, error.mensaje_usuario, error.reintentar, error.codigo_http, detalle)
	cadena = _cadena(error)
	nombres = {clase.__name__ for eslabon in cadena for clase in type(eslabon).__mro__}
	if nombres & {"TareaCancelada", "DescargaCancelada"}:
		return ErrorClasificado("cancelado", _("Operación cancelada."), False, None, detalle)
	if isinstance(error, urllib.error.HTTPError):
		categoria, reintentar, mensaje = _mensaje_http(error.code)
		return ErrorClasificado(categoria, mensaje, reintentar, error.code, detalle)
	if any(isinstance(e, ssl.SSLError) for e in cadena):
		return ErrorClasificado(
			"seguridad",
			_(
				"No se ha podido comprobar la identidad del servidor (certificado no válido). Por seguridad no se ha "
				"conectado. Revise la fecha y la hora del equipo."
			),
			False,
			None,
			detalle,
		)
	if any(isinstance(e, socket.gaierror) for e in cadena):
		return ErrorClasificado("red", _("No se ha encontrado el servidor. Compruebe que hay conexión a Internet."), True, None, detalle)
	if any(isinstance(e, TimeoutError) for e in cadena):
		return ErrorClasificado(
			"red", _("El servidor no ha respondido a tiempo. Inténtelo de nuevo dentro de un momento."), True, None, detalle
		)
	if any(isinstance(e, (http.client.IncompleteRead, ConnectionResetError, ConnectionAbortedError)) for e in cadena):
		return ErrorClasificado(
			"red", _("La conexión se ha cortado mientras se recibían los datos. Inténtelo de nuevo."), True, None, detalle
		)
	if isinstance(error, PermissionError):
		return ErrorClasificado(
			"local",
			_("No hay permiso para escribir en la carpeta de la aplicación, o el fichero está abierto en otro programa."),
			False,
			None,
			detalle,
		)
	if isinstance(error, OSError) and error.errno == errno.ENOSPC:
		return ErrorClasificado("local", _("No queda espacio libre en el disco."), False, None, detalle)
	if isinstance(error, (urllib.error.URLError, http.client.HTTPException, ConnectionError)):
		return ErrorClasificado(
			"red",
			_("No se ha podido conectar con el servidor. Compruebe la conexión a Internet e inténtelo de nuevo."),
			True,
			None,
			detalle,
		)
	return ErrorClasificado("desconocido", _("Se ha producido un error inesperado."), False, None, detalle)


def _error_de(error: BaseException) -> ErrorRed:
	"""Convierte cualquier excepción en un :class:`ErrorRed` conservando la causa."""
	if isinstance(error, ErrorRed):
		return error
	clasificado = clasificar_error(error)
	return ErrorRed(clasificado.mensaje, clasificado.categoria, clasificado.reintentar, clasificado.codigo_http, clasificado.detalle)


# ── Direcciones ──────────────────────────────────────────────────────────────


def comprobar_url(url: str) -> None:
	"""Acepta solo ``https``; ``http`` únicamente contra la propia máquina (pruebas).

	:raises ErrorRed: de categoría «seguridad» si la dirección no es admisible.
	"""
	try:
		partes = urllib.parse.urlsplit(str(url))
		anfitrion = (partes.hostname or "").lower()
	except ValueError as error:
		raise ErrorRed(_("La dirección no es válida."), categoria="seguridad", detalle=f"URL no válida: {url!r}") from error
	if partes.scheme == "https" and anfitrion:
		return
	if partes.scheme == "http" and anfitrion in HOSTS_LOCALES:
		return
	raise ErrorRed(
		_("Dirección no segura: solo se admiten conexiones cifradas (https)."),
		categoria="seguridad",
		detalle=f"Esquema no admitido en {url!r}",
	)


def es_local(url: str) -> bool:
	"""True si la dirección apunta a la propia máquina (servidor de pruebas)."""
	try:
		return (urllib.parse.urlsplit(str(url)).hostname or "").lower() in HOSTS_LOCALES
	except ValueError:
		return False


# ── Conexión ─────────────────────────────────────────────────────────────────

_cerrojo = threading.Lock()
_contexto: ssl.SSLContext | None = None


def contexto_tls() -> ssl.SSLContext:
	"""Contexto TLS con verificación de certificado y de nombre de servidor.

	Parte del almacén de Windows y le suma el paquete de ``certifi`` si está
	instalado. Nunca se devuelve un contexto sin verificación.
	"""
	global _contexto
	with _cerrojo:
		if _contexto is None:
			contexto = ssl.create_default_context()
			contexto.minimum_version = ssl.TLSVersion.TLSv1_2
			try:
				import certifi

				contexto.load_verify_locations(cafile=certifi.where())
			except ImportError:
				log.debug("certifi no está instalado: se usan solo los certificados de Windows.")
			except OSError, ssl.SSLError:
				log.warning("No se pudieron cargar los certificados de certifi; se usan los de Windows.", exc_info=True)
			_contexto = contexto
		return _contexto


class _RedireccionSegura(urllib.request.HTTPRedirectHandler):
	"""Sigue redirecciones solo hacia direcciones admitidas (nunca de https a http)."""

	max_redirections = MAX_REDIRECCIONES

	def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001, ANN201 - firma de urllib
		comprobar_url(newurl)
		if not es_local(req.full_url) and es_local(newurl):
			# Un servidor de Internet no puede mandarnos a hablar con este equipo.
			raise ErrorRed(
				_("El servidor ha redirigido la conexión a un sitio no permitido; se ha detenido por seguridad."),
				categoria="seguridad",
				detalle=f"Redirección a la máquina local desde {req.full_url}",
			)
		return super().redirect_request(req, fp, code, msg, headers, newurl)


def _abridor() -> urllib.request.OpenerDirector:
	"""Abridor sin galletas ni autenticación: solo proxy del sistema, TLS y redirecciones seguras."""
	return urllib.request.build_opener(
		urllib.request.ProxyHandler(),
		urllib.request.HTTPSHandler(context=contexto_tls()),
		_RedireccionSegura(),
	)


def _segundos_retry_after(valor: str | None) -> float | None:
	"""Segundos de una cabecera ``Retry-After`` numérica (las fechas se ignoran)."""
	if valor and valor.strip().isdigit():
		return float(valor.strip())
	return None


def _esta_cancelado(cancelacion: Any) -> bool:
	"""Admite ``threading.Event``, un token con ``cancelado`` o una función."""
	if cancelacion is None:
		return False
	if hasattr(cancelacion, "cancelado"):
		return bool(cancelacion.cancelado)
	if hasattr(cancelacion, "is_set"):
		return bool(cancelacion.is_set())
	return bool(cancelacion())


def _dormir(segundos: float, cancelacion: Any) -> None:
	"""Espera entre intentos despertándose enseguida si se cancela."""
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		if _esta_cancelado(cancelacion):
			return
		time.sleep(min(0.05, max(0.0, limite - time.monotonic())))


def abrir(
	url: str,
	cabeceras: dict[str, str] | None = None,
	*,
	tiempo: float | None = None,
	intentos: int | None = None,
	cancelacion: Any = None,
	estados_aceptados: tuple[int, ...] = (),
) -> http.client.HTTPResponse:
	"""Hace un ``GET`` y devuelve la respuesta abierta (hay que cerrarla; sirve con ``with``).

	Reintenta los fallos de conexión y los estados 429 y 5xx. Llamar SIEMPRE
	fuera del hilo de la interfaz.

	:param estados_aceptados: estados de error que no se convierten en
		excepción (la descarga reanudable necesita ver el 416).
	:raises ErrorRed: con ``mensaje_usuario`` en español.
	"""
	comprobar_url(url)
	# Los valores por defecto se leen al llamar: las pruebas acortan las esperas.
	tiempo = TIEMPO_ESPERA if tiempo is None else tiempo
	intentos = INTENTOS if intentos is None else intentos
	todas = {"User-Agent": user_agent(), "Accept": "*/*", "Accept-Encoding": "identity"}
	todas.update(cabeceras or {})
	ultimo: ErrorRed | None = None
	for intento in range(1, max(1, intentos) + 1):
		if _esta_cancelado(cancelacion):
			raise ErrorRed(_("Operación cancelada."), categoria="cancelado")
		peticion = urllib.request.Request(url, headers=todas, method="GET")
		espera = ESPERA_INICIAL * (2 ** (intento - 1))
		try:
			respuesta = _abridor().open(peticion, timeout=tiempo)
		except urllib.error.HTTPError as error:
			if error.code in estados_aceptados:
				return error  # type: ignore[return-value]  # HTTPError también es una respuesta legible
			pedida = _segundos_retry_after(error.headers.get("Retry-After") if error.headers else None)
			error.close()
			ultimo = _error_de(error)
			if error.code not in ESTADOS_REINTENTABLES:
				log.warning("El servidor respondió %d a %s", error.code, url)
				raise ultimo from error
			if pedida is not None:
				if pedida > ESPERA_MAXIMA_SERVIDOR:
					raise ultimo from error
				espera = max(espera, pedida)
		except ErrorRed:
			raise
		except (urllib.error.URLError, http.client.HTTPException, OSError) as error:
			ultimo = _error_de(error)
			if not ultimo.reintentar:
				log.warning("No se pudo conectar con %s: %s", url, error)
				raise ultimo from error
		else:
			try:
				comprobar_url(respuesta.geturl())
			except ErrorRed:
				respuesta.close()
				raise
			log.debug("GET %s → %d", url, respuesta.status)
			return respuesta
		if intento < intentos:
			log.info("Fallo pasajero al pedir %s (intento %d de %d): %s", url, intento, intentos, ultimo)
			_dormir(espera, cancelacion)
	log.warning("No se pudo obtener %s tras %d intentos: %s", url, intentos, ultimo)
	assert ultimo is not None
	raise ultimo


def leer_bytes(url: str, maximo: int, *, tiempo: float | None = None, intentos: int | None = None, cancelacion: Any = None) -> bytes:
	"""Descarga un recurso pequeño en memoria, sin pasar nunca de ``maximo`` bytes.

	Para índices y manifiestos. Los ficheros grandes van con
	``app.core.descargas.descargar``, que escribe en disco y reanuda.
	"""
	intentos = INTENTOS if intentos is None else intentos
	ultimo: ErrorRed | None = None
	for intento in range(1, max(1, intentos) + 1):
		try:
			with abrir(url, {"Cache-Control": "no-cache"}, tiempo=tiempo, intentos=1, cancelacion=cancelacion) as respuesta:
				datos = respuesta.read(maximo + 1)
		except ErrorRed as error:
			ultimo = error
		except (http.client.HTTPException, OSError) as error:
			ultimo = _error_de(error)
		else:
			if len(datos) > maximo:
				raise ErrorRed(
					_("La respuesta del servidor es demasiado grande; se ha descartado."),
					categoria="servidor",
					detalle=f"Más de {maximo} bytes en {url}",
				)
			return datos
		if not ultimo.reintentar or intento >= intentos:
			raise ultimo
		_dormir(ESPERA_INICIAL * (2 ** (intento - 1)), cancelacion)
	assert ultimo is not None
	raise ultimo


def leer_json(url: str, maximo: int, **opciones: Any) -> dict:
	"""Descarga y decodifica un objeto JSON pequeño (un manifiesto o un índice).

	:raises ErrorRed: si no llega, es demasiado grande o no es un objeto JSON.
	"""
	datos = leer_bytes(url, maximo, **opciones)
	try:
		resultado = json.loads(datos.decode("utf-8"))
	except (UnicodeDecodeError, ValueError) as error:
		raise ErrorRed(
			_("La información recibida del servidor está dañada."), categoria="servidor", detalle=f"JSON no válido en {url}"
		) from error
	if not isinstance(resultado, dict):
		raise ErrorRed(_("La información recibida del servidor está dañada."), categoria="servidor", detalle=f"No es un objeto JSON: {url}")
	return resultado
