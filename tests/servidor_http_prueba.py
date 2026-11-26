"""Servidor HTTP local para las pruebas de red, actualizaciones y catálogo en línea.

Las pruebas NUNCA salen a Internet: este servidor escucha en la propia máquina
(``::1`` o ``127.0.0.1``) en un puerto libre, dentro de un hilo, y sirve los
ficheros de una carpeta. Simula los casos difíciles que importan a un
actualizador: rangos (``Range`` e ``If-Range``), una conexión que se corta a
media descarga, errores pasajeros (503, 429) y redirecciones.

Procede de las plantillas de los agentes «red-http» y «actualizador».
"""

from __future__ import annotations

import hashlib
import http.server
import logging
import socket
import threading
import urllib.parse
from pathlib import Path

import pytest


class _Manejador(http.server.BaseHTTPRequestHandler):
	"""Sirve ficheros de una carpeta; admite rangos y obedece los fallos programados."""

	protocol_version = "HTTP/1.1"

	def log_message(self, *argumentos) -> None:  # silencio: no ensuciar la salida de pytest
		return

	def _vacia(self, codigo: int, cabeceras: dict[str, str] | None = None) -> None:
		self.send_response(codigo)
		for nombre, valor in (cabeceras or {}).items():
			self.send_header(nombre, valor)
		self.send_header("Content-Length", "0")
		self.end_headers()

	def do_GET(self) -> None:  # noqa: N802 - nombre impuesto por http.server
		prueba: ServidorPrueba = self.server.prueba  # type: ignore[attr-defined]
		nombre = urllib.parse.unquote(self.path.lstrip("/").split("?", 1)[0])
		with prueba.cerrojo:
			prueba.peticiones.append((nombre, dict(self.headers.items())))
			fallo = prueba.fallos[nombre].pop(0) if prueba.fallos.get(nombre) else None
			destino = prueba.redirecciones.get(nombre)
			cortar = prueba.cortar_en
		if fallo is not None:
			codigo, cabeceras = fallo
			self._vacia(codigo, cabeceras)
			return
		if destino is not None:
			self._vacia(302, {"Location": destino})
			return
		ruta = prueba.carpeta / nombre
		if not ruta.is_file():
			self._vacia(404)
			return
		datos = ruta.read_bytes()
		etiqueta = '"' + hashlib.sha256(datos).hexdigest()[:16] + '"'
		rango = self.headers.get("Range")
		si_rango = self.headers.get("If-Range")
		inicio = 0
		if rango and prueba.admite_rangos and (si_rango is None or si_rango == etiqueta):
			inicio = int(rango.split("=", 1)[1].split("-", 1)[0])
			if inicio >= len(datos):
				self._vacia(416, {"Content-Range": f"bytes */{len(datos)}"})
				return
			self.send_response(206)
			self.send_header("Content-Range", f"bytes {inicio}-{len(datos) - 1}/{len(datos)}")
		else:
			self.send_response(200)
		cuerpo = datos[inicio:]
		self.send_header("Content-Type", "application/octet-stream")
		self.send_header("ETag", etiqueta)
		self.send_header("Content-Length", str(len(cuerpo)))
		self.end_headers()
		if cortar is not None and nombre == prueba.cortar_nombre:
			# Simula una conexión que se cae: anuncia todo y envía solo una parte.
			with prueba.cerrojo:
				prueba.cortar_en = None
			self.wfile.write(cuerpo[:cortar])
			self.wfile.flush()
			self.close_connection = True
			return
		self.wfile.write(cuerpo)


class _ServidorSilencioso(http.server.ThreadingHTTPServer):
	"""No imprime trazas cuando el cliente corta a propósito (cancelación, tiempo agotado)."""

	daemon_threads = True

	def handle_error(self, request, client_address) -> None:  # noqa: ANN001
		import sys

		if isinstance(sys.exc_info()[1], (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
			return
		super().handle_error(request, client_address)


class _ServidorIPv6(_ServidorSilencioso):
	address_family = socket.AF_INET6


def _crear_http() -> http.server.ThreadingHTTPServer:
	"""Prefiere ``::1``: en algunos equipos un filtro de red corta las
	transferencias grandes por 127.0.0.1 y las pruebas fallarían al azar."""
	if socket.has_ipv6:
		try:
			return _ServidorIPv6(("::1", 0), _Manejador)
		except OSError:
			logging.getLogger(__name__).debug("Sin IPv6 en bucle local; se usa 127.0.0.1", exc_info=True)
	return _ServidorSilencioso(("127.0.0.1", 0), _Manejador)


class ServidorPrueba:
	"""Servidor HTTP local en un puerto libre, en un hilo.

	- ``carpeta``: lo que se sirve (``url("version.json")``).
	- ``fallos["nombre"] = [(503, {}), (429, {"Retry-After": "0"})]``: respuestas
	  de error que se dan, por orden, antes de servir el fichero.
	- ``cortar("nombre", bytes)``: la siguiente descarga de ese fichero se corta.
	- ``redirecciones["nombre"] = "https://..."``: responde 302.
	- ``admite_rangos = False``: ignora ``Range`` (siempre 200).
	- ``peticiones``: lo que ha visto, como pares (nombre, cabeceras).
	"""

	def __init__(self, carpeta: Path) -> None:
		self.carpeta = Path(carpeta)
		self.carpeta.mkdir(parents=True, exist_ok=True)
		self.admite_rangos = True
		self.cortar_en: int | None = None
		self.cortar_nombre = ""
		self.fallos: dict[str, list[tuple[int, dict[str, str]]]] = {}
		self.redirecciones: dict[str, str] = {}
		self.peticiones: list[tuple[str, dict[str, str]]] = []
		self.cerrojo = threading.Lock()
		self._http = _crear_http()
		self._http.prueba = self  # type: ignore[attr-defined]
		self._hilo = threading.Thread(target=self._http.serve_forever, name="servidor-prueba", daemon=True)
		self._hilo.start()

	def url(self, nombre: str = "") -> str:
		"""Dirección de un fichero servido (o la raíz, acabada en ``/``)."""
		anfitrion = "[::1]" if self._http.address_family == socket.AF_INET6 else "127.0.0.1"
		return f"http://{anfitrion}:{self._http.server_address[1]}/{urllib.parse.quote(nombre)}"

	def cortar(self, nombre: str, tras_bytes: int) -> None:
		"""La próxima respuesta de ``nombre`` anuncia todo y envía solo ``tras_bytes``."""
		with self.cerrojo:
			self.cortar_nombre = nombre
			self.cortar_en = tras_bytes

	def veces(self, nombre: str) -> int:
		"""Cuántas veces se ha pedido ``nombre``."""
		with self.cerrojo:
			return sum(1 for pedido, _cabeceras in self.peticiones if pedido == nombre)

	def cabeceras_de(self, nombre: str) -> list[dict[str, str]]:
		"""Cabeceras de cada petición de ``nombre``, por orden."""
		with self.cerrojo:
			return [cabeceras for pedido, cabeceras in self.peticiones if pedido == nombre]

	def cerrar(self) -> None:
		self._http.shutdown()
		self._http.server_close()


@pytest.fixture
def servidor(tmp_path):
	"""Un servidor por prueba, sirviendo ``tmp_path/web``."""
	instancia = ServidorPrueba(tmp_path / "web")
	yield instancia
	instancia.cerrar()
