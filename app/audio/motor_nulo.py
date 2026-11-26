"""Motor que no suena: apunta todas las llamadas. Para las pruebas y como última reserva.

Es también lo que queda si en un equipo no arranca ningún motor de verdad: el programa sigue
funcionando con la voz. Los canales «duran» lo que dura su sonido (según ``tic``), para que el
código que espera a que algo termine se comporte igual que con un motor real.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.audio.base import FRECUENCIA, Canal, MotorBase, Posicion3, Relativo

log = logging.getLogger(__name__)

# Lo que se supone que dura un sonido que no se ha podido cargar (el motor nulo no exige que exista).
DURACION_SUPUESTA = 0.5


class MotorNulo(MotorBase):
	"""No abre ningún dispositivo. ``llamadas`` guarda (método, argumentos) en orden."""

	nombre = "nulo"
	FUENTES_MAXIMAS = 256

	def __init__(self) -> None:
		super().__init__()
		self.llamadas: list[tuple[str, dict]] = []
		self.dispositivo: str | None = None

	def _apuntar(self, metodo: str, **argumentos: Any) -> None:
		self.llamadas.append((metodo, argumentos))
		if len(self.llamadas) > 20000:
			del self.llamadas[:10000]

	def de(self, metodo: str) -> list[dict]:
		"""Los argumentos de todas las llamadas a ``metodo``, en orden (cómodo en las pruebas)."""
		return [argumentos for nombre, argumentos in self.llamadas if nombre == metodo]

	def vaciar(self) -> None:
		"""Olvida las llamadas apuntadas."""
		self.llamadas.clear()

	def iniciar(self, dispositivo: str | None, opciones: dict) -> None:
		"""Solo apunta: nunca falla."""
		self._leer_opciones(opciones)
		self.dispositivo = dispositivo
		self._iniciado = True
		self._apuntar("iniciar", dispositivo=dispositivo, opciones=dict(opciones or {}))

	def cerrar(self) -> None:
		"""Olvida los canales."""
		self._canales.clear()
		self._iniciado = False
		self._apuntar("cerrar")

	def dispositivos(self) -> list[str]:
		"""No hay salidas."""
		return []

	def cargar(self, nombre: str, ruta: Path | None = None, datos: Any = None, frecuencia: int = FRECUENCIA) -> None:
		"""Apunta la carga; un fichero ilegible no es un fallo aquí (se anota y se sigue)."""
		self._apuntar("cargar", nombre=nombre, ruta=ruta, frecuencia=frecuencia)
		try:
			super().cargar(nombre, ruta, datos, frecuencia)
		except OSError, ValueError:
			log.debug("El motor nulo no pudo leer %s; lo da por cargado.", nombre, exc_info=True)

	def _datos(self, nombre: str):  # noqa: ANN202 - mismo tipo que la clase base
		"""Un sonido que no existe también «suena»: lo que se prueba es que se pidió."""
		datos = super()._datos(nombre)
		if datos is None:
			import numpy as np

			datos = np.zeros(int(FRECUENCIA * DURACION_SUPUESTA), dtype=np.float32)
			self._sonidos[nombre] = datos
		return datos

	def oyente(self, x: float, y: float, z: float, rumbo: float) -> None:
		"""Apunta la posición del oyente."""
		super().oyente(x, y, z, rumbo)
		self._apuntar("oyente", x=x, y=y, z=z, rumbo=rumbo)

	def reproducir(
		self,
		nombre: str,
		*,
		pos: Posicion3 | None = None,
		relativo: Relativo | None = None,
		volumen: float = 1.0,
		tono: float = 1.0,
		bus: str = "efectos",
		bucle: bool = False,
		filtro: float = 0.0,
		eco: bool = True,
		prioridad: int | None = None,
	) -> int:
		"""Apunta el sonido y devuelve un canal que dura lo que dura el sonido."""
		canal = super().reproducir(
			nombre,
			pos=pos,
			relativo=relativo,
			volumen=volumen,
			tono=tono,
			bus=bus,
			bucle=bucle,
			filtro=filtro,
			eco=eco,
			prioridad=prioridad,
		)
		self._apuntar(
			"reproducir",
			nombre=nombre,
			pos=pos,
			relativo=relativo,
			volumen=volumen,
			tono=tono,
			bus=bus,
			bucle=bucle,
			filtro=filtro,
			eco=eco,
			canal=canal,
		)
		return canal

	def actualizar(
		self,
		canal: int,
		*,
		pos: Posicion3 | None = None,
		volumen: float | None = None,
		tono: float | None = None,
		filtro: float | None = None,
	) -> None:
		"""Apunta el cambio."""
		super().actualizar(canal, pos=pos, volumen=volumen, tono=tono, filtro=filtro)
		self._apuntar("actualizar", canal=canal, pos=pos, volumen=volumen, tono=tono, filtro=filtro)

	def parar(self, canal: int, fundido: float = 0.0) -> None:
		"""Apunta la parada."""
		super().parar(canal, fundido)
		self._apuntar("parar", canal=canal, fundido=fundido)

	def parar_todo(self, bus: str | None = None) -> None:
		"""Apunta la parada general."""
		super().parar_todo(bus)
		self._apuntar("parar_todo", bus=bus)

	def acustica(self, preset: str) -> None:
		"""Apunta el preset pedido."""
		super().acustica(preset)
		self._apuntar("acustica", preset=preset)

	def volumen_bus(self, bus: str, valor: float) -> None:
		"""Apunta el volumen."""
		super().volumen_bus(bus, valor)
		self._apuntar("volumen_bus", bus=bus, valor=valor)

	def atenuar_por_voz(self, segundos: float) -> None:
		"""Apunta la atenuación."""
		super().atenuar_por_voz(segundos)
		self._apuntar("atenuar_por_voz", segundos=segundos)

	def pausar(self, si: bool) -> None:
		"""Apunta la pausa."""
		super().pausar(si)
		self._apuntar("pausar", si=si)

	def tic(self, dt: float) -> None:
		"""Avanza el tiempo de los canales (no se apunta: sería una línea por fotograma)."""
		super().tic(dt)

	def _empezar(self, canal: Canal) -> bool:
		datos = self._sonidos.get(canal.nombre)
		canal.interno = DURACION_SUPUESTA if datos is None else len(datos) / FRECUENCIA
		return True

	def _aplicar(self, canal: Canal) -> None:
		"""Nada que aplicar."""

	def _detener(self, canal: Canal) -> None:
		canal.interno = None

	def _sigue(self, canal: Canal) -> bool:
		if canal.interno is None:
			return False
		return canal.bucle or canal.edad * canal.tono < canal.interno
