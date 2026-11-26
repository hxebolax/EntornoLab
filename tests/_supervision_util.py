"""Utilidades compartidas por las pruebas de supervisión (no es un fichero de pruebas)."""

from __future__ import annotations

import json
import socket
import time
from collections.abc import Callable
from typing import Any

from app.supervision import protocolo, seguridad
from app.supervision.protocolo import A_ESTUDIO, A_JUGAR, LectorLineas


def esperar(condicion: Callable[[], Any], segundos: float = 5.0) -> bool:
	"""Espera activa con límite: vuelve en cuanto se cumple la condición."""
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		if condicion():
			return True
		time.sleep(0.01)
	return bool(condicion())


def alumno_de(sala, ident: str) -> dict[str, Any] | None:
	"""Ficha de un alumno en la foto de la sala."""
	for alumno in sala.foto()["alumnos"]:
		if alumno["id"] == ident:
			return alumno
	return None


class ConexionCruda:
	"""Reproductor «a mano» sobre un enchufe: permite enviar lo que un cliente correcto nunca enviaría."""

	def __init__(self, puerto: int, espera: float = 3.0) -> None:
		self.enchufe = socket.create_connection(("127.0.0.1", puerto), timeout=espera)
		self.troceador = LectorLineas()
		self.pendientes: list[bytes | None] = []
		self.seq = 0

	def leer(self) -> protocolo.Mensaje:
		"""Siguiente mensaje de la sala."""
		while not self.pendientes:
			datos = self.enchufe.recv(4096)
			if not datos:
				raise ConnectionError("cerrada")
			self.pendientes.extend(self.troceador.alimentar(datos))
		linea = self.pendientes.pop(0)
		assert linea is not None
		return protocolo.decodificar(linea, A_JUGAR)

	def leer_tipo(self, tipo: str, intentos: int = 50) -> protocolo.Mensaje:
		"""Lee hasta encontrar un mensaje del tipo pedido (saltando latidos)."""
		for _vuelta in range(intentos):
			mensaje = self.leer()
			if mensaje.tipo == tipo:
				return mensaje
		raise AssertionError(f"no ha llegado ningún mensaje {tipo}")

	def enviar(self, tipo: str, datos: dict[str, Any] | None = None) -> None:
		"""Envía un mensaje bien formado."""
		self.enchufe.sendall(protocolo.codificar(tipo, datos or {}, sentido=A_ESTUDIO, seq=self.seq, t=0.0))
		self.seq += 1

	def enviar_crudo(self, datos: bytes) -> None:
		"""Envía octetos tal cual."""
		self.enchufe.sendall(datos)

	def enviar_sobre(self, sobre: dict[str, Any]) -> None:
		"""Envía un sobre JSON sin validar."""
		self.enchufe.sendall(json.dumps(sobre).encode("utf-8") + b"\n")

	def saludar(self, codigo: str, alias: str = "Cruda", huella: str = "") -> protocolo.Mensaje:
		"""Hace el emparejamiento y devuelve la respuesta de la sala (bienvenida o rechazo)."""
		reto = self.leer()
		if reto.tipo != "reto":
			return reto
		nonce = seguridad.nuevo_nonce()
		self.enviar(
			"hola",
			{
				"alias": alias,
				"instancia": "cruda-" + nonce[:8],
				"nonce": nonce,
				"prueba": seguridad.prueba_cliente(codigo, reto.datos["nonce"], nonce, huella),
			},
		)
		return self.leer()

	def cerrada_por_la_sala(self, segundos: float = 3.0, avisar: bool = True) -> bool:
		"""True si la sala cierra la conexión dentro del plazo.

		Con ``avisar`` se cierra antes el sentido de escritura, como hace un
		reproductor real al recibir un rechazo; sin él se comprueba que la
		sala corta por su cuenta.
		"""
		if avisar:
			try:
				self.enchufe.shutdown(socket.SHUT_WR)
			except OSError:
				return True
		self.enchufe.settimeout(segundos)
		try:
			while True:
				if not self.enchufe.recv(4096):
					return True
		except TimeoutError:
			return False
		except OSError:
			return True

	def cerrar(self) -> None:
		self.enchufe.close()
