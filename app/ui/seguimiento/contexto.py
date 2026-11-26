"""Forma del contexto del Estudio que usa el seguimiento, y un contexto de prueba.

El contexto real es ``app.ui.contexto.ContextoEstudio`` y lo escribe quien
programa la ventana principal. Este paquete NO lo importa: declara aquí, como
``Protocol``, lo único que necesita de él. Así las dos partes se programan a
la vez y las pruebas de esta usan ``ContextoDePrueba`` sin ventana principal.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

log = logging.getLogger(__name__)

#: Eventos a los que el contexto deja suscribirse.
EVENTOS: tuple[str, ...] = ("entorno_cambiado", "entorno_abierto", "entorno_cerrado", "actividades_cambiadas")


@runtime_checkable
class ContextoSeguimiento(Protocol):
	"""Lo que el seguimiento necesita del Estudio.

	Opcionales (se usan si existen): ``recursos`` (dict nombre interno →
	bytes o ruta de los recursos del paquete abierto) y
	``anadir_recurso(nombre, datos)``, para el audio grabado de un premio.
	"""

	ventana: Any
	entorno: Any
	ruta_paquete: Any
	actividades: list[dict[str, Any]]
	catalogo: Any
	configuracion: Any
	tareas: Any

	def marcar_modificado(self, nombre_operacion: str) -> None:
		"""Anota que el paquete abierto ha cambiado (para guardar y deshacer)."""

	def guardar(self) -> Any:
		"""Guarda el paquete abierto."""

	def anunciar(self, texto: str) -> None:
		"""Dice un texto por voz y lo deja en la barra de estado."""

	def lanzar_reproductor(self, argumentos: list[str]) -> Any:
		"""Arranca el reproductor y devuelve su ``Proceso``."""

	def suscribir(self, evento: str, funcion: Callable[..., Any]) -> Any:
		"""Avisa a ``funcion`` cuando ocurre ``evento``."""


class ProcesoDePrueba:
	"""Doble de ``app.core.procesos.Proceso``: recuerda con qué se lanzó y se deja terminar."""

	def __init__(self, argumentos: list[str]) -> None:
		self.orden = list(argumentos)
		self.terminado = False

	def vivo(self) -> bool:
		"""True hasta que se llama a ``terminar``."""
		return not self.terminado

	def terminar(self, espera: float = 0.0) -> int:
		"""Marca el proceso como terminado."""
		self.terminado = True
		return 0


class ContextoDePrueba:
	"""Contexto sin ventana principal: guarda lo que se le pide para comprobarlo en las pruebas."""

	def __init__(
		self,
		ventana: Any = None,
		entorno: Any = None,
		actividades: list[dict[str, Any]] | None = None,
		catalogo: Any = None,
		configuracion: Any = None,
		ruta_paquete: Path | str | None = None,
	) -> None:
		self.ventana = ventana
		self.entorno = entorno
		self.actividades: list[dict[str, Any]] = actividades if actividades is not None else []
		self.catalogo = catalogo
		if configuracion is None:
			from app.core.configuracion import obtener_configuracion

			configuracion = obtener_configuracion()
		self.configuracion = configuracion
		self.ruta_paquete = Path(ruta_paquete) if ruta_paquete is not None else None
		self.tareas = None
		self.recursos: dict[str, Any] = {}
		self.modificado = False
		self.actividad_actual: dict[str, Any] | None = None
		self.anunciados: list[str] = []
		self.modificaciones: list[str] = []
		self.guardados = 0
		self.lanzados: list[ProcesoDePrueba] = []
		self._suscritos: dict[str, list[Callable[..., Any]]] = {}

	def marcar_modificado(self, nombre_operacion: str = "") -> None:
		"""Apunta la operación y avisa, como el contexto real."""
		self.modificaciones.append(nombre_operacion)
		self.modificado = True
		self.emitir("actividades_cambiadas")

	def guardar(self) -> bool:
		"""Cuenta el guardado; si hay ruta y entorno, escribe el paquete de verdad."""
		self.guardados += 1
		if self.ruta_paquete is not None and self.entorno is not None:
			from app.dominio.formato import guardar_paquete

			guardar_paquete(self.ruta_paquete, self.entorno, self.actividades, self.recursos or None)
		self.modificado = False
		return True

	def anunciar(self, texto: str) -> None:
		"""Apunta el anuncio en lugar de decirlo."""
		self.anunciados.append(texto)

	def lanzar_reproductor(self, argumentos: list[str]) -> ProcesoDePrueba:
		"""No lanza nada: devuelve un proceso de mentira con los argumentos."""
		proceso = ProcesoDePrueba([str(argumento) for argumento in argumentos])
		self.lanzados.append(proceso)
		return proceso

	def suscribir(self, evento: str, funcion: Callable[..., Any]) -> Callable[[], None]:
		"""Apunta la suscripción y devuelve cómo cancelarla."""
		self._suscritos.setdefault(evento, []).append(funcion)

		def cancelar() -> None:
			if funcion in self._suscritos.get(evento, []):
				self._suscritos[evento].remove(funcion)

		return cancelar

	def anadir_recurso(self, nombre: str, datos: bytes) -> None:
		"""Guarda un recurso del paquete (el audio de un premio)."""
		self.recursos[nombre] = datos

	def emitir(self, evento: str, *args: Any) -> None:
		"""Avisa a los suscritos, como haría el Estudio."""
		for funcion in list(self._suscritos.get(evento, [])):
			funcion(*args)


def anunciar(contexto: Any, texto: str) -> None:
	"""Dice ``texto`` por el contexto sin que un fallo de voz rompa la acción que lo pidió."""
	if not texto:
		return
	try:
		contexto.anunciar(texto)
	except Exception:  # noqa: BLE001 - la voz es un complemento: su fallo no puede deshacer la acción ya hecha
		log.warning("No se ha podido anunciar un mensaje por el contexto", exc_info=True)


def guardar_recurso(contexto: Any, nombre: str, datos: bytes) -> bool:
	"""Añade un recurso al paquete abierto por la vía que ofrezca el contexto. False si no ofrece ninguna."""
	metodo = getattr(contexto, "anadir_recurso", None)
	if callable(metodo):
		metodo(nombre, datos)
		return True
	recursos = getattr(contexto, "recursos", None)
	if isinstance(recursos, dict):
		recursos[nombre] = datos
		return True
	return False
