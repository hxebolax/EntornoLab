"""Material común de las pruebas de actividades: un robot que juega una actividad de principio a fin.

Las actividades se prueban como las usará el reproductor: se crean con
``crear_actividad``, se cuelgan de una ``Sesion`` con los ajustes que da
``Actividad.ajustes`` y un robot (el de las pruebas del motor) da órdenes y
mira los eventos. Los entornos son los tres de ejemplo, amueblados con el
catálogo real de ``data/plugins`` (solo se lee; nunca se escribe en ``data``).
"""

from __future__ import annotations

import functools
import math
from pathlib import Path
from typing import Any

from app.actividades import crear_actividad
from app.actividades.lugares import punto_de_acceso, punto_interior_de_abertura
from app.dominio import ejemplos
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Entorno
from app.motor import eventos as ev
from app.motor.sesion import AjustesJuego, Sesion
from tests.test_motor_comun import Robot, registros, texto

RAIZ = Path(__file__).resolve().parent.parent


@functools.cache
def catalogo_real() -> Catalogo:
	"""El catálogo de complementos de serie (``data/plugins``), leído una sola vez."""
	return Catalogo.cargar([RAIZ / "data" / "plugins"])


@functools.cache
def ejemplo(nombre: str, amueblado: bool = True) -> Entorno:
	"""Uno de los entornos de ejemplo, amueblado con el catálogo real. El motor no lo modifica, así que se comparte."""
	entorno = ejemplos.EJEMPLOS[nombre]()
	if amueblado:
		ejemplos.amueblar_ejemplos(entorno, catalogo_real())
	return entorno


def vivienda() -> Entorno:
	return ejemplo("vivienda-de-ejemplo")


def centro() -> Entorno:
	return ejemplo("centro-de-dos-plantas")


def barrio() -> Entorno:
	return ejemplo("barrio-de-ejemplo")


def espacio_en(entorno: Entorno, x: float, y: float, planta: int = 0) -> Any:
	"""El espacio que contiene un punto de una planta (por su número de orden)."""
	return entorno.plantas[planta].espacio_en(x, y, incluir_macizos=False)


class Jugador(Robot):
	"""Un alumno automático jugando una actividad."""

	def __init__(
		self,
		entorno: Entorno,
		datos: dict[str, Any],
		catalogo: Catalogo | None = None,
		estilo: str | None = None,
		semilla: int = 7,
		nivel: int | None = None,
		**ajustes: Any,
	) -> None:
		ajustes.setdefault("trafico", False)
		self.entorno = entorno
		# Como hará el reproductor: se pasa la semilla de la partida. Un examen trae la suya en los datos y esa es la que manda.
		self.actividad = crear_actividad(
			datos, entorno, catalogo if catalogo is not None else catalogo_real(), estilo=estilo, semilla=semilla, nivel=nivel
		)
		self.sesion = Sesion(
			entorno,
			catalogo if catalogo is not None else catalogo_real(),
			self.actividad.ajustes(AjustesJuego(**ajustes)),
			actividad=self.actividad,
			semilla=semilla,
			inicio=self.actividad.inicio(),
		)
		self.eventos: list[Any] = []
		self.tic(2)

	# ── Moverse ──

	def ir(self, destino: Any, cerca: float = 0.5, intentos: int = 6) -> bool:
		"""Va andando a un lugar ``(planta, x, y)`` de la planta actual por el camino del navegador. Devuelve si ha llegado."""
		planta, x, y = destino[0], float(destino[1]), float(destino[2])
		for _intento in range(intentos):
			jugador = self.sesion.jugador
			if self.sesion.terminado or jugador.planta != planta:
				return False
			if math.hypot(jugador.x - x, jugador.y - y) <= cerca:
				return True
			if self.sesion.nav.ruta((jugador.planta, jugador.x, jugador.y), (planta, x, y)) is None:
				return False
			self.seguir((planta, x, y))
		jugador = self.sesion.jugador
		return math.hypot(jugador.x - x, jugador.y - y) <= cerca + 0.6

	def ir_a_espacio(self, espacio_id: str) -> bool:
		"""Entra en un espacio (va a un punto suyo donde cabe una persona)."""
		from app.actividades.lugares import lugar_de_espacio

		planta, espacio = self.entorno.buscar(espacio_id)
		lugar = lugar_de_espacio(self.sesion.mundo, planta, espacio)
		self.ir(lugar.terna)
		return (self.sesion.movimiento.espacio_id or "") == espacio_id

	def usar(self, objeto_id: str) -> list[Any]:
		"""Va hasta un objeto, se pone de cara a él y lo usa una sola vez."""
		info = self.sesion.mundo.objeto(objeto_id)
		assert info is not None, objeto_id
		objeto = info.objeto
		jugador = self.sesion.jugador
		acceso = punto_de_acceso(self.sesion.mundo, objeto_id)
		assert acceso is not None, f"no hay sitio junto a {objeto_id}"
		self.ir((info.planta_id, acceso[0], acceso[1]), cerca=0.25)
		previo = self.sesion.ajustes.paso_m
		for _paso in range(12):
			self.girar_a(geo.rumbo_entre((jugador.x, jugador.y), (objeto.x, objeto.y)))
			a_mano = self.sesion.interactuables_cerca()
			if a_mano and a_mano[0]["id"] == objeto_id:
				break
			self.sesion.ajustes.paso_m = 0.25
			self.pulsar("avanzar", 1)
			self.sesion.ajustes.paso_m = previo
		self.sesion.ajustes.paso_m = previo
		return self.pulsar("interactuar", 2)

	def salir_por(self, abertura_id: str) -> list[Any]:
		"""Sale del entorno cruzando una abertura (abre la puerta si hace falta) y se para en cuanto está fuera o le recolocan."""
		info = self.sesion.mundo.abertura(abertura_id)
		assert info is not None, abertura_id
		dentro = punto_interior_de_abertura(self.sesion.mundo, info, 0.9)
		assert dentro is not None
		(x, y), _rumbo = dentro
		antes = len(self.eventos)
		self.ir((info.planta_id, x, y), cerca=0.3)
		jugador = self.sesion.jugador
		self.girar_a(geo.rumbo_entre((jugador.x, jugador.y), info.centro))
		previo = self.sesion.ajustes.paso_m
		self.sesion.ajustes.paso_m = 0.5
		for _paso in range(12):
			if self.sesion.terminado:
				break
			posicion = (jugador.x, jugador.y)
			self.pulsar("avanzar", 1)
			if registros(self.eventos[antes:], "salida"):
				break
			if math.hypot(jugador.x - posicion[0], jugador.y - posicion[1]) < 0.1:
				# Le ha parado la puerta: la abre.
				self.pulsar("interactuar", 1)
		self.sesion.ajustes.paso_m = previo
		self.tic(2)
		return self.eventos[antes:]

	def confirmar(self) -> list[Any]:
		"""Confirma como lo haría una tecla propia del reproductor, sin depender de lo que haya al alcance de la mano."""
		for evento in self.actividad.confirmar(self.sesion):
			self.sesion.emitir(evento)
		return self.tic(2)

	def jugar(self, segundos: float) -> list[Any]:
		"""Deja pasar tiempo de juego sin hacer nada."""
		return self.esperar(segundos)

	# ── Lo ocurrido ──

	@property
	def fin(self) -> dict[str, Any] | None:
		"""Resultado de ``EvFin`` si la sesión ha terminado."""
		for evento in self.eventos:
			if isinstance(evento, ev.EvFin):
				return evento.resultado
		return None

	def dicho(self, desde: int = 0) -> str:
		"""Todo lo dicho desde el evento número ``desde``."""
		return texto(self.eventos[desde:])

	def registrados(self, tipo: str) -> list[dict[str, Any]]:
		"""Datos de los registros de un tipo emitidos en toda la partida."""
		return registros(self.eventos, tipo)


def presentar(jugador: Jugador, eventos: list[Any]) -> None:
	"""Hace lo que hará el reproductor con los eventos de una orden del profesional: pasárselos a la sesión."""
	for evento in eventos:
		jugador.sesion.emitir(evento)
	jugador.tic(1)


def test_el_catalogo_real_trae_contenedores():
	"""Los ejemplos amueblados tienen objetos donde esconder premios: sin ellos no se probaría «dentro de»."""
	catalogo = catalogo_real()
	assert not catalogo.vacio
	contenedores = [
		objeto
		for planta in vivienda().plantas
		for objeto in planta.objetos
		if catalogo.definicion_de(objeto) is not None and catalogo.definicion_de(objeto).contenedor
	]
	assert len(contenedores) >= 3
