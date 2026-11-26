"""OpenStreetMap: buscar un lugar, descargar un recuadro pequeño y convertirlo en un entorno.

A diferencia de un importador de ciudades enteras, aquí se trae solo lo que
cabe en un recuadro de unas pocas calles (como mucho ``RADIO_MAXIMO_M``
alrededor de un punto), directamente de Overpass en JSON y con la biblioteca
estándar. El resultado es un borrador editable, no un mapa.

Política de uso de los servidores públicos, que este módulo cumple:

- Nominatim: identificación genérica de la aplicación (nombre y versión, sin
  datos de la persona ni del equipo), una petición por segundo como máximo y
  resultados guardados en caché para no repetir búsquedas.
- Overpass: una sola consulta por importación, acotada en tiempo y tamaño,
  con caché en ``data/cache/osm`` y varios servidores por si uno está ocupado.

Privacidad: lo único que sale del equipo es el texto buscado o las cuatro
coordenadas del recuadro, y solo cuando el profesional pulsa importar.

Las funciones de red reciben una función ``descargar(url, datos=None) ->
bytes`` inyectable: por defecto usa ``app.core.red`` (HTTPS con verificación,
reintentos), y en las pruebas se sustituye para no tocar la red.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import threading
import time
import urllib.parse
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core import paths
from app.core.i18n import _, separador_decimal
from app.core.red import ErrorRed
from app.importar.comun import (
	Cancelado,
	ErrorImportacion,
	ImportacionCancelada,
	Progreso,
	analizar_xml_seguro,
	avisar_fase,
	comprobar_cancelacion,
	leer_fichero,
	texto_duracion,
)
from app.importar.georef import ATRIBUCION, LICENCIA, URL_LICENCIA, Proyeccion
from app.importar.osm_conversion import OpcionesOSM, convertir

log = logging.getLogger(__name__)

__all__ = [
	"ATRIBUCION",
	"Candidato",
	"LICENCIA",
	"OpcionesOSM",
	"Proyeccion",
	"RADIO_MAXIMO_M",
	"URL_LICENCIA",
	"buscar_lugar",
	"consulta_overpass",
	"convertir",
	"descargar_recuadro",
	"descargar_zona",
	"importar_fichero_osm",
	"recuadro_de",
]

# Una función de descarga recibe la dirección y, si la petición lleva parámetros,
# estos ya codificados como formulario. Devuelve el cuerpo de la respuesta.
Descargar = Callable[..., bytes]

NOMINATIM = "https://nominatim.openstreetmap.org/search"
# Servidores públicos de Overpass (el principal y espejos): si uno está ocupado, el siguiente.
OVERPASS: tuple[str, ...] = (
	"https://overpass-api.de/api/interpreter",
	"https://overpass.private.coffee/api/interpreter",
	"https://overpass.kumi.systems/api/interpreter",
)
# Claves de configuración con las que el profesional puede poner su propio servidor.
CLAVE_URL_OVERPASS = "importar.overpass_url"
CLAVE_URL_NOMINATIM = "importar.nominatim_url"

# Radio máximo de la zona: más allá deja de ser «unas pocas calles» y el
# borrador sale tan grande que no se puede revisar ni recorrer.
RADIO_MAXIMO_M = 400.0
RADIO_MINIMO_M = 20.0
# Segundos mínimos entre dos peticiones a Nominatim (su política de uso).
INTERVALO_NOMINATIM = 1.0
DIAS_CACHE = 30
MAX_BYTES_RESPUESTA = 32 * 1024 * 1024
MAX_BYTES_FICHERO = 64 * 1024 * 1024
MAX_ELEMENTOS_XML = 600_000
TIEMPO_OVERPASS = 90.0
# Intentos con un mismo servidor de Overpass ante un fallo pasajero, y pausa entre ellos.
INTENTOS_OVERPASS = 2
PAUSA_REINTENTO = 1.0
# Bytes que se leen de cada vez: lo bastante pequeño para avisar a menudo de lo recibido.
TROZO_DESCARGA = 64 * 1024
# Segundos entre dos avisos de «sigue esperando» o «van recibidos tantos KB».
INTERVALO_AVISO_DESCARGA = 1.0

# ── Estimación del tamaño de una zona ──
# Medido con la muestra real de la Plaza Mayor de Valladolid (150 m de radio,
# un recuadro de 300 por 300 metros, centro histórico denso): 377.679 bytes,
# 2.488 elementos y 249 espacios al convertir. Por metro cuadrado de recuadro:
BYTES_POR_M2 = 377_679 / 90_000.0
ESPACIOS_POR_M2 = 249 / 90_000.0
# Conversión ya optimizada, medida con zonas de 150, 300 y 400 metros (de 249
# a 2.855 espacios): entre 0,4 y 0,75 milisegundos por espacio en un equipo de
# sobremesa. Se toma 1,5 ms por espacio más medio segundo, para dejar margen a
# un portátil modesto.
SEGUNDOS_POR_ESPACIO = 0.0015
# Lo que tarda Overpass en preparar la respuesta no se puede medir sin red y
# depende de lo ocupado que esté: de unos pocos segundos a más de un minuto.
# Se da un margen: de 5 a 30 segundos más el envío a 1 MB/s y a 0,25 MB/s.
ESPERA_SERVIDOR_MINIMA = 5.0
ESPERA_SERVIDOR_HABITUAL = 30.0
# A partir de este radio se avisa del tamaño y del tiempo antes de descargar.
RADIO_AVISO_M = 200.0


# ── Recuadros ────────────────────────────────────────────────────────────────


def recuadro_de(lat: float, lon: float, radio_m: float) -> tuple[float, float, float, float]:
	"""Recuadro (sur, oeste, norte, este) de ``radio_m`` metros alrededor de un punto."""
	if not (-85.0 <= lat <= 85.0 and -180.0 <= lon <= 180.0):
		raise ErrorImportacion(_("Las coordenadas no son válidas: la latitud va de -85 a 85 y la longitud de -180 a 180."))
	if radio_m > RADIO_MAXIMO_M:
		raise ErrorImportacion(
			_(
				"La zona pedida tiene {pedido} metros de radio y el máximo son {maximo}. EntornoLab importa unas pocas "
				"calles, no un barrio entero: elija un radio menor o importe la zona en varias partes."
			).format(pedido=round(radio_m), maximo=round(RADIO_MAXIMO_M))
		)
	if radio_m < RADIO_MINIMO_M:
		raise ErrorImportacion(_("El radio tiene que ser de al menos {minimo} metros.").format(minimo=round(RADIO_MINIMO_M)))
	proyeccion = Proyeccion(lat, lon)
	sur, oeste = proyeccion.a_latlon(-radio_m, -radio_m)
	norte, este = proyeccion.a_latlon(radio_m, radio_m)
	return sur, oeste, norte, este


def _comprobar_recuadro(sur: float, oeste: float, norte: float, este: float) -> None:
	if not (sur < norte and oeste < este):
		raise ErrorImportacion(_("El recuadro no es válido: el sur tiene que ser menor que el norte y el oeste menor que el este."))
	proyeccion = Proyeccion((sur + norte) / 2.0, (oeste + este) / 2.0)
	ancho = proyeccion.a_xy(sur, este)[0] - proyeccion.a_xy(sur, oeste)[0]
	alto = proyeccion.a_xy(norte, oeste)[1] - proyeccion.a_xy(sur, oeste)[1]
	maximo = RADIO_MAXIMO_M * 2.0 + 1.0
	if ancho > maximo or alto > maximo:
		raise ErrorImportacion(
			_(
				"El recuadro pedido mide {ancho} por {alto} metros y el máximo son {maximo} por {maximo}. Elija una zona "
				"más pequeña o impórtela en varias partes."
			).format(ancho=round(ancho), alto=round(alto), maximo=round(RADIO_MAXIMO_M * 2.0))
		)


# ── Red: ritmo, descarga y caché ─────────────────────────────────────────────


class LimitadorRitmo:
	"""Garantiza un intervalo mínimo entre peticiones a un servidor.

	Nominatim pide no pasar de una petición por segundo. El reloj y la
	espera son inyectables para probarlo sin dormir de verdad.
	"""

	def __init__(self, intervalo: float, reloj: Callable[[], float] = time.monotonic, dormir: Callable[[float], None] = time.sleep) -> None:
		self.intervalo = intervalo
		self._reloj = reloj
		self._dormir = dormir
		self._ultima: float | None = None
		self._cerrojo = threading.Lock()

	def esperar(self, cancelado: Cancelado | None = None) -> None:
		"""Bloquea lo justo para respetar el intervalo y apunta la hora de esta petición."""
		with self._cerrojo:
			while self._ultima is not None:
				falta = self._ultima + self.intervalo - self._reloj()
				if falta <= 0.0:
					break
				comprobar_cancelacion(cancelado)
				self._dormir(min(falta, 0.1))
			self._ultima = self._reloj()


_limitador_nominatim = LimitadorRitmo(INTERVALO_NOMINATIM)


def _descargador_por_defecto(
	cancelado: Cancelado | None,
	al_recibir: Callable[[int, int | None], None] | None = None,
	al_reintentar: Callable[[int, int, BaseException], None] | None = None,
) -> Descargar:
	"""Función de descarga real: HTTPS verificado de ``app.core.red``, leída por trozos.

	Se lee por trozos (y no de una vez) para poder decir cuántos bytes han
	llegado (``al_recibir(recibidos, total_o_None)``) y para cortar enseguida
	si se cancela. Un fallo pasajero se reintenta una vez, avisando antes con
	``al_reintentar(intento, intentos, error)``: así el profesional sabe por
	qué la espera se alarga.
	"""

	def descargar(url: str, datos: bytes | None = None) -> bytes:
		from app.core import red

		if datos:
			url = f"{url}?{datos.decode('ascii')}"
		intento = 1
		while True:
			try:
				return _leer_por_trozos(url, cancelado, al_recibir)
			except red.ErrorRed as error:
				if error.categoria == "cancelado" or not error.reintentar or intento >= INTENTOS_OVERPASS:
					raise
				intento += 1
				log.info("Reintento %s de %s con %s tras: %s", intento, INTENTOS_OVERPASS, urllib.parse.urlsplit(url).hostname, error)
				if al_reintentar is not None:
					al_reintentar(intento, INTENTOS_OVERPASS, error)
				_pausa(PAUSA_REINTENTO * (intento - 1), cancelado)

	return descargar


def _leer_por_trozos(url: str, cancelado: Cancelado | None, al_recibir: Callable[[int, int | None], None] | None) -> bytes:
	"""Pide ``url`` y lee la respuesta en trozos, avisando de los bytes recibidos; nunca más de ``MAX_BYTES_RESPUESTA``."""
	import http.client

	from app.core import red

	trozos: list[bytes] = []
	recibidos = 0
	try:
		with red.abrir(url, {"Cache-Control": "no-cache"}, tiempo=TIEMPO_OVERPASS, intentos=1, cancelacion=cancelado) as respuesta:
			largo = respuesta.headers.get("Content-Length") if respuesta.headers else None
			total = int(largo) if largo and largo.isdigit() else None
			leer = respuesta.read1 if hasattr(respuesta, "read1") else respuesta.read
			while True:
				if cancelado is not None and cancelado():
					raise red.ErrorRed(_("Operación cancelada."), categoria="cancelado")
				trozo = leer(TROZO_DESCARGA)
				if not trozo:
					break
				recibidos += len(trozo)
				if recibidos > MAX_BYTES_RESPUESTA:
					raise red.ErrorRed(
						_("La respuesta del servidor es demasiado grande; se ha descartado."),
						categoria="servidor",
						detalle=f"Más de {MAX_BYTES_RESPUESTA} bytes en {url}",
					)
				trozos.append(trozo)
				if al_recibir is not None:
					al_recibir(recibidos, total)
	except red.ErrorRed:
		raise
	except (http.client.HTTPException, OSError) as error:
		clasificado = red.clasificar_error(error)
		raise red.ErrorRed(
			clasificado.mensaje, clasificado.categoria, clasificado.reintentar, clasificado.codigo_http, clasificado.detalle
		) from error
	return b"".join(trozos)


def _pausa(segundos: float, cancelado: Cancelado | None) -> None:
	"""Espera entre reintentos, despertándose enseguida si se cancela."""
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		if cancelado is not None and cancelado():
			return
		time.sleep(min(0.05, max(0.0, limite - time.monotonic())))


def texto_bytes(cantidad: int) -> str:
	"""«380 KB», «2,7 MB»: un tamaño dicho como lo diría una persona (decimales con coma en español)."""
	if cantidad < 1024 * 1024:
		return _("{n} KB").format(n=max(1, round(cantidad / 1024)) if cantidad else 0)
	megas = f"{cantidad / (1024 * 1024):.1f}".replace(".", separador_decimal())
	return _("{n} MB").format(n=megas)


def _esperar_sin_bloquear(funcion: Callable[[], bytes], cancelado: Cancelado | None, cada_rato: Callable[[float], None]) -> bytes:
	"""Ejecuta una descarga en un hilo aparte y espera a que acabe, atenta a la cancelación.

	Por qué: mientras Overpass prepara la respuesta (a veces un minuto o más)
	la conexión está bloqueada esperando el primer byte, y un hilo bloqueado
	no puede comprobar si se ha cancelado. Así el hilo de la tarea sigue
	libre: cada décima de segundo mira si se ha cancelado (y entonces se va
	ya, dejando que la petición abandonada termine sola por su tiempo
	máximo) y cada poco llama a ``cada_rato(segundos_esperando)`` para que
	el diálogo diga que sigue esperando.
	"""
	resultado: dict[str, Any] = {}
	listo = threading.Event()

	def correr() -> None:
		try:
			resultado["datos"] = funcion()
		except BaseException as error:  # noqa: BLE001 - se vuelve a lanzar en el hilo que espera
			resultado["error"] = error
		finally:
			listo.set()

	hilo = threading.Thread(target=correr, name="osm-descarga", daemon=True)
	inicio = time.monotonic()
	hilo.start()
	while not listo.wait(0.1):
		if cancelado is not None and cancelado():
			log.info(
				"Descarga de Overpass cancelada tras %.1f s; la petición abandonada se cierra sola (como mucho %s s).",
				time.monotonic() - inicio,
				TIEMPO_OVERPASS,
			)
			raise ImportacionCancelada(_("Importación cancelada."))
		cada_rato(time.monotonic() - inicio)
	if "error" in resultado:
		raise resultado["error"]
	return resultado["datos"]


def _url_configurada(clave: str) -> str:
	"""Dirección de servidor puesta por el profesional en la configuración, o cadena vacía."""
	try:
		from app.core.configuracion import ErrorConfiguracion, obtener_configuracion
	except ImportError:
		log.debug("No hay módulo de configuración; se usan los servidores de serie.")
		return ""
	try:
		valor = obtener_configuracion().obtener(clave, "")
	except (OSError, ErrorConfiguracion) as error:
		log.warning("No se pudo leer «%s» de la configuración: %s", clave, error)
		return ""
	return valor.strip() if isinstance(valor, str) else ""


def carpeta_cache() -> Path:
	"""Carpeta ``data/cache/osm``: respuestas ya descargadas, que se pueden borrar sin perder nada."""
	carpeta = paths.ruta_cache() / "osm"
	carpeta.mkdir(parents=True, exist_ok=True)
	return carpeta


def _ruta_cache(prefijo: str, clave: str) -> Path:
	return carpeta_cache() / f"{prefijo}-{hashlib.sha256(clave.encode('utf-8')).hexdigest()[:24]}.json"


def _leer_cache(ruta: Path) -> Any | None:
	"""Contenido de una entrada de caché reciente; None si no existe, caducó o está dañada."""
	try:
		if time.time() - ruta.stat().st_mtime > DIAS_CACHE * 86400:
			return None
		return json.loads(ruta.read_text(encoding="utf-8"))
	except FileNotFoundError:
		return None
	except (OSError, ValueError) as error:
		log.warning("La entrada de caché %s no se puede leer (%s); se descarga de nuevo.", ruta.name, error)
		return None


def _guardar_cache(ruta: Path, contenido: Any) -> None:
	"""Escribe la entrada de caché de forma atómica; si falla, solo se pierde la caché."""
	temporal = ruta.with_name(ruta.name + ".tmp")
	try:
		temporal.write_text(json.dumps(contenido, ensure_ascii=False), encoding="utf-8")
		os.replace(temporal, ruta)
	except OSError as error:
		log.warning("No se pudo guardar la caché %s: %s", ruta.name, error)


def _mensaje_de(error: BaseException) -> str:
	"""Mensaje para la persona de un error de red (``ErrorRed`` trae uno ya redactado)."""
	return str(getattr(error, "mensaje_usuario", "") or error)


# ── Buscar un lugar (Nominatim) ──────────────────────────────────────────────


@dataclass
class Candidato:
	"""Un lugar encontrado al buscar: lo que se enseña en la lista para elegir."""

	nombre: str
	descripcion: str
	lat: float
	lon: float
	tipo: str = ""
	recuadro: tuple[float, float, float, float] | None = None
	osm: str = ""
	etiquetas: dict[str, str] = field(default_factory=dict)

	def __str__(self) -> str:
		return self.descripcion or self.nombre


def buscar_lugar(
	texto: str,
	limite: int = 8,
	*,
	descargar: Descargar | None = None,
	cancelado: Cancelado | None = None,
	usar_cache: bool = True,
) -> list[Candidato]:
	"""Lugares que responden a un texto («Calle Mayor 12, Soria»), para elegir el centro de la zona.

	Usa Nominatim respetando su política: una petición por segundo como
	máximo, identificación genérica de la aplicación y caché de resultados.
	"""
	texto = " ".join(str(texto).split())
	if len(texto) < 3:
		raise ErrorImportacion(_("Escriba al menos tres letras del lugar que busca."))
	limite = max(1, min(int(limite), 20))
	ruta = _ruta_cache("nominatim", f"{texto.lower()}|{limite}")
	resultados = _leer_cache(ruta) if usar_cache else None
	if resultados is None:
		consulta = urllib.parse.urlencode({"q": texto, "format": "jsonv2", "limit": limite, "addressdetails": 0, "accept-language": "es"})
		servidor = _url_configurada(CLAVE_URL_NOMINATIM) or NOMINATIM
		_limitador_nominatim.esperar(cancelado)
		comprobar_cancelacion(cancelado)
		try:
			cuerpo = (descargar or _descargador_por_defecto(cancelado))(servidor, consulta.encode("ascii"))
			resultados = json.loads(cuerpo.decode("utf-8"))
		except (OSError, ValueError, ErrorRed) as error:
			raise ErrorImportacion(_("No se ha podido buscar el lugar: {motivo}").format(motivo=_mensaje_de(error))) from error
		if not isinstance(resultados, list):
			raise ErrorImportacion(_("El servidor de búsqueda ha dado una respuesta que no se entiende."))
		_guardar_cache(ruta, resultados)
	candidatos: list[Candidato] = []
	for resultado in resultados:
		if not isinstance(resultado, dict):
			continue
		try:
			lat, lon = float(resultado["lat"]), float(resultado["lon"])
		except KeyError, TypeError, ValueError:
			log.debug("Resultado de búsqueda sin coordenadas; se descarta.")
			continue
		descripcion = str(resultado.get("display_name") or "")
		recuadro = None
		caja = resultado.get("boundingbox")
		if isinstance(caja, list) and len(caja) == 4:
			try:
				sur, norte, oeste, este = (float(v) for v in caja)
				recuadro = (sur, oeste, norte, este)
			except TypeError, ValueError:
				log.debug("Recuadro no válido en un resultado de búsqueda; se ignora.")
		candidatos.append(
			Candidato(
				nombre=str(resultado.get("name") or descripcion.split(",")[0]),
				descripcion=descripcion,
				lat=lat,
				lon=lon,
				tipo=str(resultado.get("type") or resultado.get("addresstype") or ""),
				recuadro=recuadro,
				osm=f"{resultado.get('osm_type', '')}/{resultado.get('osm_id', '')}".strip("/"),
			)
		)
	return candidatos


# ── Descargar una zona (Overpass) ────────────────────────────────────────────


def consulta_overpass(recuadro: tuple[float, float, float, float]) -> str:
	"""Consulta Overpass QL que trae todo lo del recuadro en JSON.

	Nodos y vías del recuadro, los nodos de esas vías aunque caigan fuera
	(para poder dibujarlas enteras) y los multipolígonos de los que forman
	parte, con sus vías (plazas y edificios con patio). No se piden las demás
	relaciones: una línea de autobús arrastraría media ciudad.
	"""
	sur, oeste, norte, este = recuadro
	caja = f"{sur:.6f},{oeste:.6f},{norte:.6f},{este:.6f}"
	return (
		"[out:json][timeout:60][maxsize:67108864];"
		f"(node({caja});way({caja});)->.b;"
		"rel(bw.b)[type=multipolygon]->.r;"
		"(.b;way(r.r);)->.c;"
		"(.c;node(w.c);.r;);"
		"out body;"
	)


def _interpretar_overpass(cuerpo: bytes) -> dict[str, Any]:
	"""Respuesta de Overpass como diccionario, o ``ErrorImportacion`` si es un error disfrazado."""
	try:
		datos = json.loads(cuerpo.decode("utf-8"))
	except (UnicodeDecodeError, ValueError) as error:
		# Cuando está saturado, Overpass responde con una página HTML en vez de JSON.
		raise ErrorImportacion(_("el servidor está ocupado o ha dado una respuesta que no es un mapa")) from error
	if not isinstance(datos, dict) or not isinstance(datos.get("elements"), list):
		raise ErrorImportacion(_("la respuesta no contiene un mapa"))
	aviso = str(datos.get("remark") or "")
	if "error" in aviso.lower():
		if "memory" in aviso or "timed out" in aviso or "maxsize" in aviso:
			raise ErrorImportacion(_("la zona tiene demasiados datos para descargarla de una vez; elija un radio menor"))
		raise ErrorImportacion(aviso[:200])
	return datos


class _SeguimientoDescarga:
	"""Lo que va pasando en una petición a Overpass, para contarlo con cifras.

	``recibido`` y ``reintento`` los llama el hilo que descarga; ``avisar``,
	el hilo de la tarea mientras espera (ver ``_esperar_sin_bloquear``). Así
	todos los avisos de progreso salen del hilo de la tarea, y una petición
	abandonada al cancelar ya no avisa de nada.
	"""

	def __init__(self, progreso: Progreso | None, fraccion: float, fase: str, servidor: str) -> None:
		self._progreso = progreso
		self._fraccion = fraccion
		self._fase = fase
		self._fase_base = fase
		self._servidor = servidor
		self._inicio = time.monotonic()
		self._ultimo_aviso = self._inicio
		self._reintento_pendiente = ""
		self.recibidos = 0
		self.total: int | None = None
		self.primer_byte: float | None = None
		self.reintentos = 0

	def recibido(self, recibidos: int, total: int | None) -> None:
		"""Han llegado ``recibidos`` bytes de ``total`` (None si el servidor no dice cuántos)."""
		if self.primer_byte is None and recibidos:
			self.primer_byte = time.monotonic() - self._inicio
		self.recibidos = recibidos
		self.total = total

	def reintento(self, intento: int, intentos: int, error: BaseException) -> None:
		"""El servidor ha fallado de forma pasajera y se va a volver a intentar."""
		self.reintentos += 1
		self.recibidos = 0
		self._fase = _("{fase} (intento {n} de {total})").format(fase=self._fase_base, n=intento, total=intentos)
		self._reintento_pendiente = _("{servidor} no ha contestado bien ({motivo}); se vuelve a intentar (intento {n} de {total}).").format(
			servidor=self._servidor, motivo=_mensaje_de(error).rstrip("."), n=intento, total=intentos
		)

	def avisar(self, segundos: float) -> None:
		"""Dice, como mucho una vez por segundo, si sigue esperando al servidor o cuánto ha llegado."""
		ahora = time.monotonic()
		if ahora - self._ultimo_aviso < INTERVALO_AVISO_DESCARGA and not self._reintento_pendiente:
			return
		self._ultimo_aviso = ahora
		if self._reintento_pendiente:
			texto, self._reintento_pendiente = self._reintento_pendiente, ""
		elif not self.recibidos:
			texto = _("Esperando a que {servidor} prepare los datos: {tiempo}.").format(
				servidor=self._servidor, tiempo=texto_duracion(segundos)
			)
		elif self.total:
			texto = _("Descargando datos de OpenStreetMap: {tamano} de {total}.").format(
				tamano=texto_bytes(self.recibidos), total=texto_bytes(self.total)
			)
		else:
			texto = _("Descargando datos de OpenStreetMap: {tamano}.").format(tamano=texto_bytes(self.recibidos))
		avisar_fase(
			self._progreso,
			self._fraccion,
			self._fase,
			texto,
			self.recibidos or None,
			self.total,
			indeterminado=not self.total,
		)


@dataclass(frozen=True)
class EstimacionZona:
	"""Lo que cabe esperar de una zona antes de descargarla: tamaño y tiempos aproximados."""

	lado_m: int
	espacios: int
	bytes: int
	descarga_minima_s: float
	descarga_habitual_s: float
	conversion_s: float

	def texto(self) -> str:
		"""Frase para el profesional: tamaño, cuánto se descarga y cuánto puede tardar."""
		return _(
			"La zona mide {lado} por {lado} metros. Saldrán unos {espacios} espacios y se descargarán unos {tamano}. "
			"La descarga suele tardar entre {minimo} y {habitual}, y más si los servidores de OpenStreetMap están "
			"ocupados; la conversión, unos {conversion}. Durante la espera verá y oirá lo que se está haciendo, y "
			"puede cancelar en cualquier momento."
		).format(
			lado=self.lado_m,
			espacios=_redondear(self.espacios),
			tamano=texto_bytes(self.bytes),
			minimo=texto_duracion(self.descarga_minima_s),
			habitual=texto_duracion(self.descarga_habitual_s),
			conversion=texto_duracion(self.conversion_s),
		)


def _redondear(cantidad: int) -> int:
	"""Una cifra aproximada dicha sin falsa precisión: 1.770 espacios se dicen «unos 1.800»."""
	if cantidad < 100:
		return max(1, round(cantidad / 10) * 10)
	return round(cantidad, -2)


def estimar_zona(radio_m: float) -> EstimacionZona:
	"""Tamaño y tiempos aproximados de importar una zona de ``radio_m`` metros.

	La fórmula es proporcional a la superficie del recuadro ((2 × radio)²),
	con las densidades de la muestra real de Valladolid (centro histórico:
	por eso es una estimación por lo alto para un barrio de las afueras):

	- espacios = 0,00277 por m²: 250 a 150 m, 1.000 a 300 m, 1.800 a 400 m
	  (las zonas de prueba de 300 y 400 m dieron 1.048 y 1.993);
	- bytes = 4,2 por m²: 380 KB a 150 m, 2,7 MB a 400 m;
	- conversión = 0,5 s + 1,5 ms por espacio (medido: de 0,4 a 0,75 ms);
	- descarga = espera del servidor (de 5 a 30 s, que es lo que no se puede
	  medir sin red) + envío a entre 1 y 0,25 MB por segundo.
	"""
	radio = max(RADIO_MINIMO_M, min(float(radio_m), RADIO_MAXIMO_M))
	superficie = (2.0 * radio) ** 2
	espacios = round(superficie * ESPACIOS_POR_M2)
	tamano = round(superficie * BYTES_POR_M2)
	megas = tamano / (1024 * 1024)
	return EstimacionZona(
		lado_m=round(2.0 * radio),
		espacios=espacios,
		bytes=tamano,
		descarga_minima_s=ESPERA_SERVIDOR_MINIMA + megas,
		descarga_habitual_s=ESPERA_SERVIDOR_HABITUAL + megas * 4.0,
		conversion_s=0.5 + espacios * SEGUNDOS_POR_ESPACIO,
	)


def descargar_recuadro(
	sur: float,
	oeste: float,
	norte: float,
	este: float,
	*,
	servidores: tuple[str, ...] | list[str] | None = None,
	descargar: Descargar | None = None,
	usar_cache: bool = True,
	progreso: Progreso | None = None,
	cancelado: Cancelado | None = None,
) -> dict[str, Any]:
	"""Descarga de Overpass todo lo que hay en un recuadro y lo devuelve como diccionario.

	El diccionario es el JSON de Overpass con una clave más, ``recuadro``
	(sur, oeste, norte, este), que ``convertir`` usa para recortar. Prueba
	los servidores por orden: el de la configuración si lo hay, y después
	los públicos. La respuesta se guarda en ``data/cache/osm``.

	Progreso: ``progreso(fraccion, texto)`` va diciendo a qué servidor se
	pide, cuánto lleva esperando a que prepare los datos, los bytes que van
	llegando («Descargando datos de OpenStreetMap: 380 KB.») y los
	reintentos; con ``por_fases`` (ver ``comun.avisar_fase``) además sabe
	que el total es desconocido y la barra va indeterminada. Cancelar
	(``cancelado()``) corta también la espera del primer byte, que es la
	parte larga. El registro guarda, a nivel INFO, los bytes y los segundos
	de cada intento.
	"""
	recuadro = (float(sur), float(oeste), float(norte), float(este))
	_comprobar_recuadro(*recuadro)
	consulta = consulta_overpass(recuadro)
	ruta = _ruta_cache("overpass", consulta)
	fase = _("Descargando el mapa de OpenStreetMap")
	if usar_cache:
		guardado = _leer_cache(ruta)
		if isinstance(guardado, dict) and isinstance(guardado.get("elements"), list):
			log.info("Mapa de la zona leído de la caché (%s elementos).", len(guardado["elements"]))
			avisar_fase(progreso, 1.0, fase, _("Mapa de la zona recuperado de la caché."), indeterminado=True)
			guardado["recuadro"] = list(recuadro)
			return guardado
	if servidores is None:
		propio = _url_configurada(CLAVE_URL_OVERPASS)
		servidores = ((propio,) if propio else ()) + OVERPASS
	if not servidores:
		raise ErrorImportacion(_("No hay ningún servidor de Overpass configurado."))
	formulario = urllib.parse.urlencode({"data": consulta}).encode("ascii")
	fallos: list[str] = []
	fallido = ""
	for numero, servidor in enumerate(servidores):
		comprobar_cancelacion(cancelado)
		anfitrion = urllib.parse.urlsplit(servidor).hostname or servidor
		fraccion = numero / (len(servidores) + 1)
		previo = _("{servidor} no ha dado el mapa; se prueba con otro servidor.").format(servidor=fallido) + " " if fallido else ""
		fallido = anfitrion
		fase_servidor = _("{fase} desde {servidor}").format(fase=fase, servidor=anfitrion)
		avisar_fase(
			progreso,
			fraccion,
			fase_servidor,
			previo
			+ _("Pidiendo el mapa de la zona a {servidor} (servidor {n} de {total}).").format(
				servidor=anfitrion, n=numero + 1, total=len(servidores)
			),
			indeterminado=True,
		)
		seguimiento = _SeguimientoDescarga(progreso, fraccion, fase_servidor, anfitrion)
		funcion = descargar or _descargador_por_defecto(cancelado, seguimiento.recibido, seguimiento.reintento)
		inicio = time.monotonic()
		try:
			cuerpo = _esperar_sin_bloquear(
				lambda funcion=funcion, servidor=servidor: funcion(servidor, formulario), cancelado, seguimiento.avisar
			)
			seguimiento.recibido(len(cuerpo), len(cuerpo))
			segundos = time.monotonic() - inicio
			avisar_fase(
				progreso,
				fraccion,
				fase_servidor,
				_("Leyendo la respuesta del servidor ({tamano}).").format(tamano=texto_bytes(len(cuerpo))),
				indeterminado=True,
			)
			datos = _interpretar_overpass(cuerpo)
		except ErrorImportacion as error:
			if isinstance(error, ImportacionCancelada):
				raise
			log.info("Overpass %s no dio la zona tras %.1f s: %s", anfitrion, time.monotonic() - inicio, error)
			fallos.append(f"{anfitrion}: {error}")
			continue
		except (OSError, ErrorRed) as error:
			if getattr(error, "categoria", "") == "cancelado":
				raise ImportacionCancelada(_("Importación cancelada.")) from error
			log.info("Overpass %s no contestó tras %.1f s: %s", anfitrion, time.monotonic() - inicio, error)
			fallos.append(f"{anfitrion}: {_mensaje_de(error)}")
			continue
		log.info(
			"Descarga de Overpass desde %s: %s bytes en %.1f s (primer byte a los %s s, %s reintentos); %s elementos; %.1f s en total con la lectura",
			anfitrion,
			len(cuerpo),
			segundos,
			f"{seguimiento.primer_byte:.1f}" if seguimiento.primer_byte is not None else "?",
			seguimiento.reintentos,
			len(datos["elements"]),
			time.monotonic() - inicio,
		)
		datos["recuadro"] = list(recuadro)
		datos["servidor"] = anfitrion
		_guardar_cache(ruta, datos)
		avisar_fase(
			progreso,
			1.0,
			fase,
			_("Mapa de la zona descargado: {n} elementos, {tamano}.").format(n=len(datos["elements"]), tamano=texto_bytes(len(cuerpo))),
			indeterminado=True,
		)
		return datos
	raise ErrorImportacion(
		_(
			"Ningún servidor ha podido dar el mapa de la zona. {detalle}. Inténtelo más tarde o importe un fichero .osm ya descargado."
		).format(detalle="; ".join(fallos[-3:]))
	)


def descargar_zona(lat: float, lon: float, radio_m: float = 150.0, **opciones: Any) -> dict[str, Any]:
	"""Descarga la zona de ``radio_m`` metros alrededor de un punto (como mucho ``RADIO_MAXIMO_M``).

	``opciones`` son las de ``descargar_recuadro``. Añade al resultado la
	clave ``centro`` para que el punto pedido sea el (0, 0) del entorno.
	"""
	sur, oeste, norte, este = recuadro_de(float(lat), float(lon), float(radio_m))
	datos = descargar_recuadro(sur, oeste, norte, este, **opciones)
	datos["centro"] = [float(lat), float(lon)]
	return datos


# ── Ficheros ya descargados ──────────────────────────────────────────────────


def _de_xml(datos: bytes) -> dict[str, Any]:
	"""Convierte un .osm (XML) a la misma forma que el JSON de Overpass."""
	raiz = analizar_xml_seguro(datos, MAX_BYTES_FICHERO, MAX_ELEMENTOS_XML)
	if raiz.tag != "osm":
		raise ErrorImportacion(_("El fichero XML no es de OpenStreetMap (le falta el elemento «osm»)."))
	elementos: list[dict[str, Any]] = []
	resultado: dict[str, Any] = {"elements": elementos}
	for hijo in raiz:
		try:
			if hijo.tag == "bounds":
				resultado["recuadro"] = [float(hijo.get(clave, "")) for clave in ("minlat", "minlon", "maxlat", "maxlon")]
				continue
			if hijo.tag == "meta" and hijo.get("osm_base"):
				resultado["osm3s"] = {"timestamp_osm_base": hijo.get("osm_base")}
				continue
			if hijo.tag not in ("node", "way", "relation"):
				continue
			if hijo.get("action") == "delete" or hijo.get("visible") == "false":
				continue
			elemento: dict[str, Any] = {"type": hijo.tag, "id": int(hijo.get("id", ""))}
			etiquetas = {str(t.get("k")): str(t.get("v") or "") for t in hijo.iter("tag") if t.get("k")}
			if etiquetas:
				elemento["tags"] = etiquetas
			if hijo.tag == "node":
				elemento["lat"] = float(hijo.get("lat", ""))
				elemento["lon"] = float(hijo.get("lon", ""))
			elif hijo.tag == "way":
				elemento["nodes"] = [int(nd.get("ref", "")) for nd in hijo.iter("nd")]
			else:
				elemento["members"] = [
					{"type": str(m.get("type") or ""), "ref": int(m.get("ref", "")), "role": str(m.get("role") or "")}
					for m in hijo.iter("member")
				]
		except ValueError:
			log.warning("Elemento «%s» con datos no numéricos en el fichero OSM; se descarta.", hijo.tag)
			continue
		elementos.append(elemento)
	return resultado


def importar_fichero_osm(ruta: str | os.PathLike[str]) -> dict[str, Any]:
	"""Lee un ``.osm`` (XML) o un JSON de Overpass ya descargado, para trabajar sin conexión.

	Devuelve los datos en la forma que espera ``convertir``. El XML se
	analiza de forma segura: sin entidades ni referencias externas.
	"""
	datos = leer_fichero(ruta, MAX_BYTES_FICHERO)
	inicio = datos.lstrip()[:1]
	if inicio in (b"{", b"["):
		try:
			contenido = json.loads(datos.decode("utf-8-sig"))
		except (UnicodeDecodeError, ValueError) as error:
			raise ErrorImportacion(_("El fichero no es un JSON válido de Overpass.")) from error
		if not isinstance(contenido, dict) or not isinstance(contenido.get("elements"), list):
			raise ErrorImportacion(_("El fichero JSON no es de Overpass: le falta la lista «elements»."))
		return contenido
	if inicio == b"<":
		contenido = _de_xml(datos)
		if not contenido["elements"]:
			raise ErrorImportacion(_("El fichero OSM no contiene ningún elemento."))
		return contenido
	raise ErrorImportacion(_("«{ruta}» no es un fichero .osm ni un JSON de Overpass.").format(ruta=Path(ruta).name))
