"""Sonidos que se pueden elegir para un premio, y cómo oírlos desde el Estudio. Sin wx.

Todo aquí es tolerante: el Estudio no necesita sonido para editar, así que si
el paquete de audio no está, falla o no hay tarjeta de sonido, la lista sale
con los nombres de serie y «Escuchar» dice que no puede, sin romper nada.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.i18n import N_, _, idioma_actual

log = logging.getLogger(__name__)

# Sonidos de premio de serie, por si no se puede leer el catálogo de sonidos.
_DE_SERIE: tuple[tuple[str, str], ...] = (
	("premio/cerca", N_("Centelleo que se repite")),
	("premio/aparece", N_("Tintineos que suben")),
	("premio/recogido", N_("Monedas")),
	("premio/tesoro", N_("Melodía de tesoro")),
)
GRUPO_PREMIOS = "premios"


_cache: tuple[str, list[tuple[str, str]]] | None = None


def listar_sonidos() -> list[tuple[str, str]]:
	"""Pares (clave, nombre) de los sonidos elegibles, con los de premio primero.

	Leer el catálogo tarda (carga la síntesis de sonidos): se hace una vez
	por idioma y se recuerda, para que abrir el diálogo de un premio sea inmediato.
	"""
	global _cache
	idioma = idioma_actual()
	if _cache is not None and _cache[0] == idioma:
		return list(_cache[1])
	lista = _leer_sonidos()
	_cache = (idioma, lista)
	return list(lista)


def _leer_sonidos() -> list[tuple[str, str]]:
	try:
		from app.audio.banco import catalogo_sonidos

		catalogo = catalogo_sonidos()
	except Exception:  # noqa: BLE001 - el audio es opcional en el Estudio y puede fallar de muchas formas (numpy, ficheros, bibliotecas)
		log.warning("No se ha podido leer el catálogo de sonidos; se ofrecen los de serie", exc_info=True)
		return [(clave, _(nombre)) for clave, nombre in _DE_SERIE]
	sonidos = catalogo.get("sonidos") if isinstance(catalogo, dict) else None
	if not isinstance(sonidos, dict) or not sonidos:
		return [(clave, _(nombre)) for clave, nombre in _DE_SERIE]
	premios: list[tuple[str, str]] = []
	otros: list[tuple[str, str]] = []
	for clave, ficha in sonidos.items():
		if not isinstance(ficha, dict):
			continue
		par = (str(clave), str(ficha.get("nombre") or clave))
		(premios if ficha.get("grupo") == GRUPO_PREMIOS else otros).append(par)
	otros.sort(key=lambda par: par[1].casefold())
	return (premios + otros) or [(clave, _(nombre)) for clave, nombre in _DE_SERIE]


class Escucha:
	"""Reproduce un sonido del banco para que el profesional sepa cómo suena.

	El motor de sonido se crea la primera vez que se pide escuchar algo, no al
	abrir el Estudio: arrancarlo tarda y casi nunca hace falta.
	"""

	def __init__(self, configuracion: Any = None, recursos: Any = None) -> None:
		self._configuracion = configuracion
		self._recursos = recursos
		self._motor: Any = None
		self._banco: Any = None
		self._canal = 0
		self.ultimo_error = ""

	def _preparar(self) -> bool:
		if self._motor is not None:
			return True
		try:
			from app.audio.banco import Banco
			from app.audio.fabrica import crear_motor

			opciones: dict[str, Any] = {}
			if self._configuracion is not None:
				seccion = self._configuracion.obtener("sonido", {})
				if isinstance(seccion, dict):
					opciones = dict(seccion)
			self._banco = Banco(recurso_entorno=self._recurso)
			self._motor = crear_motor(opciones, self._banco)
		except Exception as error:  # noqa: BLE001 - una biblioteca de sonido puede fallar de cualquier forma al arrancar
			log.warning("No se ha podido preparar el sonido para escuchar", exc_info=True)
			self.ultimo_error = str(error)
			self._motor = None
			return False
		return True

	def _recurso(self, nombre: str) -> bytes:
		"""Bytes de un sonido propio del paquete abierto (``KeyError`` si no lo tiene)."""
		recursos = self._recursos() if callable(self._recursos) else self._recursos
		if isinstance(recursos, dict):
			for candidato in (nombre, f"sonidos/{nombre}"):
				datos = recursos.get(candidato)
				if isinstance(datos, (bytes, bytearray)):
					return bytes(datos)
		raise KeyError(nombre)

	def escuchar(self, nombre: str) -> bool:
		"""Hace sonar ``nombre``. False si no se pudo (queda el motivo en ``ultimo_error``)."""
		if not nombre or not self._preparar():
			return False
		try:
			if self._canal:
				self._motor.parar(self._canal, 0.05)
			self._banco.precargar(self._motor, [nombre])
			self._canal = int(self._motor.reproducir(nombre, bus="interfaz", eco=False))
			self._motor.tic(0.0)
		except Exception as error:  # noqa: BLE001 - mismo motivo: el sonido nunca debe romper el editor
			log.warning("No se ha podido reproducir un sonido de muestra", exc_info=True)
			self.ultimo_error = str(error)
			return False
		return True

	def cerrar(self) -> None:
		"""Para y cierra el motor de sonido si se llegó a crear."""
		motor, self._motor = self._motor, None
		if motor is not None:
			motor.cerrar()


def mensaje_sin_sonido() -> str:
	"""Lo que se dice cuando «Escuchar» no puede sonar."""
	return _("No se ha podido reproducir el sonido en este equipo. El sonido elegido se guarda igualmente.")
