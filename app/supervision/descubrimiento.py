"""Búsqueda de salas en la red local por difusión UDP, sin dependencias.

Cómo funciona: el reproductor envía un datagrama ``buscar`` a la dirección
de difusión; cada sala abierta en red responde directamente a quien preguntó
con su nombre y su puerto. No se anuncia nada si nadie pregunta.

```
reproductor -> difusión:47901   {"v": 1, "app": "EntornoLab", "tipo": "buscar"}
sala -> reproductor             {"v": 1, "app": "EntornoLab", "tipo": "sala", "nombre": "...",
                                 "puerto": 47900, "tls": true, "huella": "<64 hex>"}
```

La respuesta NO lleva el código de emparejamiento ni ningún dato de alumnos.
La huella que viaja aquí es solo informativa (la red local no es de fiar):
la que cuenta es la del certificado que presenta la sala al conectar.

Muchas redes de centros bloquean la difusión, y los cortafuegos suelen
preguntar la primera vez: por eso SIEMPRE existe la alternativa de escribir
la dirección a mano (``analizar_direccion``).
"""

from __future__ import annotations

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass

from app.core.i18n import _
from app.supervision.protocolo import PUERTO_DESCUBRIMIENTO, PUERTO_SALA, VERSION

log = logging.getLogger(__name__)

APLICACION = "EntornoLab"
_DATAGRAMA_MAXIMO = 1024
# Respuestas por segundo a una misma dirección: evita usar la sala para inundar a otro.
_RESPUESTAS_POR_SEGUNDO = 5
# Instantes (segundos desde el inicio) en que se envía y se repite la pregunta de búsqueda.
_REENVIOS = (0.0, 0.15, 0.5)


@dataclass(frozen=True)
class SalaEncontrada:
	"""Una sala que respondió a la búsqueda."""

	nombre: str
	host: str
	puerto: int
	tls: bool
	huella: str


def direcciones_locales() -> list[str]:
	"""Direcciones IPv4 de este ordenador en sus redes (sin 127.0.0.1).

	Es lo que el profesional dicta cuando la búsqueda automática no funciona.
	"""
	direcciones: list[str] = []
	try:
		candidatas = socket.gethostbyname_ex(socket.gethostname())[2]
	except OSError:
		log.debug("No se han podido averiguar las direcciones locales", exc_info=True)
		candidatas = []
	for direccion in candidatas:
		if not direccion.startswith("127.") and direccion not in direcciones:
			direcciones.append(direccion)
	return direcciones


def analizar_direccion(texto: str, puerto_por_defecto: int = PUERTO_SALA) -> tuple[str, int]:
	"""Convierte lo que escribe la persona («192.168.1.20», «equipo:47900», «[::1]:47900») en ``(host, puerto)``.

	Lanza ``ValueError`` con un mensaje para mostrar.
	"""
	limpio = texto.strip()
	if not limpio or any(letra.isspace() for letra in limpio):
		raise ValueError(_("Escriba la dirección de la sala, por ejemplo 192.168.1.20 o 192.168.1.20:47900."))
	host = limpio
	puerto_texto = ""
	if limpio.startswith("["):
		cierre = limpio.find("]")
		if cierre < 0:
			raise ValueError(_("La dirección no es válida: falta el corchete de cierre."))
		host = limpio[1:cierre]
		resto = limpio[cierre + 1 :]
		if resto.startswith(":"):
			puerto_texto = resto[1:]
		elif resto:
			raise ValueError(_("La dirección no es válida."))
	elif limpio.count(":") == 1:
		host, puerto_texto = limpio.split(":")
		if not puerto_texto:
			raise ValueError(_("Falta el puerto después de los dos puntos."))
	if not host:
		raise ValueError(_("Falta la dirección de la sala."))
	if not puerto_texto:
		return host, puerto_por_defecto
	if not puerto_texto.isdecimal() or not 1 <= int(puerto_texto) <= 65535:
		raise ValueError(_("El puerto debe ser un número entre 1 y 65535."))
	return host, int(puerto_texto)


class Anunciador:
	"""Responde a las búsquedas de salas mientras la sala está abierta en red.

	Vive en su propio hilo. Si no puede abrir el puerto (otro programa, el
	cortafuegos), la sala sigue funcionando: solo deja de ser «encontrable»
	y hay que escribir su dirección.
	"""

	def __init__(
		self,
		nombre: str,
		puerto_sala: int,
		*,
		tls: bool,
		huella: str = "",
		puerto: int = PUERTO_DESCUBRIMIENTO,
		host: str = "",
	) -> None:
		self.nombre = nombre
		self.puerto_sala = puerto_sala
		self.tls = tls
		self.huella = huella
		self.puerto = puerto
		self._host = host
		self._socket: socket.socket | None = None
		self._hilo: threading.Thread | None = None
		self._parar = threading.Event()
		self._ultimas: dict[str, list[float]] = {}

	def iniciar(self) -> bool:
		"""Empieza a responder. Devuelve False (y lo registra) si no se pudo abrir el puerto."""
		if self._hilo is not None:
			return True
		try:
			enchufe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
			enchufe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
			enchufe.bind((self._host, self.puerto))
			enchufe.settimeout(0.2)
		except OSError:
			log.warning("No se ha podido abrir el puerto de búsqueda de salas (%d)", self.puerto, exc_info=True)
			return False
		self.puerto = enchufe.getsockname()[1]
		self._socket = enchufe
		self._parar.clear()
		self._hilo = threading.Thread(target=self._bucle, name="anunciador-sala", daemon=True)
		self._hilo.start()
		return True

	def _permitida(self, direccion: str) -> bool:
		ahora = time.monotonic()
		recientes = [t for t in self._ultimas.get(direccion, []) if ahora - t < 1.0]
		if len(recientes) >= _RESPUESTAS_POR_SEGUNDO:
			self._ultimas[direccion] = recientes
			return False
		recientes.append(ahora)
		self._ultimas[direccion] = recientes
		if len(self._ultimas) > 500:
			self._ultimas.clear()
		return True

	def _bucle(self) -> None:
		enchufe = self._socket
		assert enchufe is not None
		respuesta = json.dumps(
			{
				"v": VERSION,
				"app": APLICACION,
				"tipo": "sala",
				"nombre": self.nombre,
				"puerto": self.puerto_sala,
				"tls": self.tls,
				"huella": self.huella,
			},
			ensure_ascii=False,
		).encode("utf-8")
		while not self._parar.is_set():
			try:
				datos, origen = enchufe.recvfrom(_DATAGRAMA_MAXIMO)
			except TimeoutError:
				continue
			except OSError:
				if self._parar.is_set():
					break
				# En Windows, un datagrama anterior rechazado por el destino aparece aquí como error: se sigue.
				log.debug("Error al recibir una búsqueda de salas", exc_info=True)
				continue
			if not _es_busqueda(datos) or not self._permitida(origen[0]):
				continue
			try:
				enchufe.sendto(respuesta, origen)
			except OSError:
				log.debug("No se ha podido responder a una búsqueda de salas", exc_info=True)
		enchufe.close()

	def detener(self) -> None:
		"""Deja de responder y cierra el puerto."""
		self._parar.set()
		hilo = self._hilo
		if hilo is not None:
			hilo.join(timeout=2.0)
		self._hilo = None
		self._socket = None


def _es_busqueda(datos: bytes) -> bool:
	mensaje = _leer_datagrama(datos)
	return mensaje is not None and mensaje.get("tipo") == "buscar"


def _leer_datagrama(datos: bytes) -> dict | None:
	"""Datagrama de EntornoLab de la versión actual, o ``None`` si es otra cosa (se ignora en silencio)."""
	if len(datos) > _DATAGRAMA_MAXIMO:
		return None
	try:
		mensaje = json.loads(datos.decode("utf-8"))
	except ValueError, RecursionError:
		return None
	if not isinstance(mensaje, dict) or mensaje.get("app") != APLICACION or mensaje.get("v") != VERSION:
		return None
	return mensaje


def _destinos_por_defecto() -> list[str]:
	"""Difusión general, difusión de cada red local (suponiendo máscara /24) y el propio ordenador."""
	destinos = ["255.255.255.255", "127.0.0.1"]
	for direccion in direcciones_locales():
		partes = direccion.split(".")
		if len(partes) == 4:
			dirigida = ".".join(partes[:3] + ["255"])
			if dirigida not in destinos:
				destinos.append(dirigida)
	return destinos


def buscar_salas(
	espera: float = 1.5,
	*,
	puerto: int = PUERTO_DESCUBRIMIENTO,
	destinos: list[str] | None = None,
) -> list[SalaEncontrada]:
	"""Busca salas en la red local durante ``espera`` segundos.

	BLOQUEA ese tiempo: el reproductor la llama desde un hilo de trabajo y
	mientras tanto sigue atendiendo el menú. Una lista vacía no significa
	que no haya salas: puede que la red bloquee la difusión; hay que ofrecer
	entonces escribir la dirección.
	"""
	encontradas: dict[tuple[str, int], SalaEncontrada] = {}
	pregunta = json.dumps({"v": VERSION, "app": APLICACION, "tipo": "buscar"}).encode("utf-8")
	try:
		enchufe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	except OSError:
		log.warning("No se ha podido abrir un puerto para buscar salas", exc_info=True)
		return []
	try:
		enchufe.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
		enchufe.bind(("", 0))
		lista_destinos = destinos if destinos is not None else _destinos_por_defecto()
		inicio = time.monotonic()
		limite = inicio + max(0.05, espera)
		# UDP no garantiza la entrega (y en Windows el primer datagrama de un enchufe nuevo
		# se pierde a veces): la pregunta se repite un par de veces mientras se escucha.
		envios = [inicio + retraso for retraso in _REENVIOS if inicio + retraso < limite]
		while True:
			ahora = time.monotonic()
			while envios and envios[0] <= ahora:
				envios.pop(0)
				for destino in lista_destinos:
					try:
						enchufe.sendto(pregunta, (destino, puerto))
					except OSError:
						log.debug("No se ha podido enviar la búsqueda a un destino", exc_info=True)
			proximo = envios[0] if envios else limite
			queda = min(proximo, limite) - time.monotonic()
			if queda <= 0:
				if not envios:
					break
				continue
			enchufe.settimeout(queda)
			try:
				datos, origen = enchufe.recvfrom(_DATAGRAMA_MAXIMO)
			except TimeoutError:
				continue
			except OSError:
				# Windows avisa así de un destino que rechazó el datagrama; los demás pueden responder.
				continue
			mensaje = _leer_datagrama(datos)
			if mensaje is None or mensaje.get("tipo") != "sala":
				continue
			puerto_sala = mensaje.get("puerto")
			if isinstance(puerto_sala, bool) or not isinstance(puerto_sala, int) or not 1 <= puerto_sala <= 65535:
				continue
			nombre = mensaje.get("nombre")
			huella = mensaje.get("huella")
			encontradas[(origen[0], puerto_sala)] = SalaEncontrada(
				nombre=nombre[:100] if isinstance(nombre, str) else "",
				host=origen[0],
				puerto=puerto_sala,
				tls=bool(mensaje.get("tls", True)),
				huella=huella[:64] if isinstance(huella, str) else "",
			)
	finally:
		enchufe.close()
	return sorted(encontradas.values(), key=lambda sala: (sala.nombre.casefold(), sala.host, sala.puerto))
