"""Motor estéreo simple con ``pygame.mixer``: para equipos modestos y para altavoces.

Es el estéreo de siempre (el que usó AbES y con el que se demostró la transferencia al lugar real):

- **panorama** de potencia constante, sin dejar nunca mudo del todo un lado;
- **distancia** con la misma ley que los demás motores;
- lo que queda **detrás** o tras una pared suena con la versión apagada del sonido (sin agudos) y
  algo más flojo;
- sin diferencia de tiempo entre oídos, sin HRTF y sin reverberación.

Límites de pygame que conviene conocer: el tono se fija al empezar (se prepara una versión
remuestreada) y no cambia mientras suena; y la versión apagada también se elige al empezar, así que
en un bucle el cambio delante/detrás solo se nota en el volumen.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.audio import sintesis
from app.audio.base import (
	FRECUENCIA,
	Canal,
	ErrorMotor,
	MotorBase,
	MotorNoDisponible,
	a_mono,
	factor_detras,
	ganancia_distancia,
	ganancias_filtro,
	mundo_a_relativo,
)
from app.audio.proteccion import Vigilante
from app.core.i18n import _

log = logging.getLogger(__name__)

CANALES_MEZCLADOR = 32
FORMATO = (FRECUENCIA, -16, 2)
CORTE_APAGADO = 900.0
SUELO_LADO = 0.15  # el lado contrario nunca baja de esta parte
CERCA = 0.75  # metros por debajo de los cuales el panorama se cierra hacia el centro
VARIANTES_MAXIMAS = 96  # versiones remuestreadas o apagadas que se guardan preparadas
PASOS_TONO = 24  # el tono se redondea a 1/24 de octava para no preparar una versión por cada valor


@dataclass
class _Sonando:
	"""El canal de pygame de un sonido en marcha."""

	canal: Any
	sonido: Any


class MotorEstereo(MotorBase):
	"""Paneo simple con pygame.mixer. Ver el docstring del módulo."""

	nombre = "estereo"
	FUENTES_MAXIMAS = CANALES_MEZCLADOR

	def __init__(self) -> None:
		super().__init__()
		self._pygame: Any = None
		self._mezclador_propio = False
		self._variantes: dict[tuple[str, bool, bool, int], Any] = {}
		self.memoria = False
		self.nombre_salida = ""
		self.vigilante: Vigilante | None = None
		self._callado = False

	@classmethod
	def disponible(cls) -> tuple[bool, str]:
		"""Hace falta pygame con su mezclador."""
		try:
			import pygame.mixer  # noqa: F401 - solo se comprueba que está
		except (ImportError, OSError) as error:
			return False, _("No se puede usar el mezclador de pygame: {error}").format(error=error)
		return True, ""

	def iniciar(self, dispositivo: str | None, opciones: dict) -> None:
		"""Abre el mezclador de pygame a 44,1 kHz, 16 bits, estéreo."""
		if self._iniciado:
			self.cerrar()
		self._leer_opciones(opciones)
		self.memoria = bool(self.opciones.get("memoria", False))
		try:
			import pygame
			import pygame.mixer
		except (ImportError, OSError) as error:
			raise MotorNoDisponible(f"no se puede usar pygame.mixer: {error}") from error
		self._pygame = pygame
		if dispositivo and dispositivo.lower().startswith("openal soft on "):
			# Un nombre guardado con el motor OpenAL: SDL conoce la misma salida sin ese prefijo.
			dispositivo = dispositivo[len("openal soft on ") :]
		try:
			if pygame.mixer.get_init() != FORMATO:
				if pygame.mixer.get_init():
					pygame.mixer.quit()
				bloque = 2048 if self.opciones.get("holgado") else 512
				try:
					pygame.mixer.init(*FORMATO, bloque, devicename=dispositivo or None, allowedchanges=0)
				except pygame.error:
					if not dispositivo:
						raise
					log.warning("No se pudo abrir la salida «%s»: se usa la de Windows.", dispositivo, exc_info=True)
					dispositivo = None
					pygame.mixer.init(*FORMATO, bloque, allowedchanges=0)
				self._mezclador_propio = True
			pygame.mixer.set_num_channels(CANALES_MEZCLADOR)
		except pygame.error as error:
			raise ErrorMotor(f"pygame no pudo abrir el sonido: {error}") from error
		self.nombre_salida = str(dispositivo or "")
		self._callado = False
		self.vigilante = Vigilante(self.proteccion.silencio_sin_tic, self._callar_por_seguridad, self._volver_de_silencio)
		if not self.memoria:
			self.vigilante.iniciar()
		self._iniciado = True
		log.info("Motor estéreo iniciado (pygame.mixer %s).", pygame.mixer.get_init())

	def dispositivos(self) -> list[str]:
		"""Las salidas que ve SDL (hace falta que el sonido de SDL esté iniciado)."""
		try:
			import pygame
			import pygame._sdl2.audio as sdl_audio

			if not pygame.mixer.get_init():
				return []
			return list(sdl_audio.get_audio_device_names(False))
		except ImportError, OSError:
			log.warning("No se pudieron enumerar las salidas de SDL.", exc_info=True)
			return []
		except pygame.error:
			log.warning("SDL no pudo enumerar las salidas de sonido.", exc_info=True)
			return []

	# ── Sonidos preparados ──

	@staticmethod
	def _tono_redondeado(tono: float) -> int:
		"""El tono en pasos de 1/24 de octava (0 = sin cambio)."""
		return int(round(math.log2(max(0.25, min(4.0, tono))) * PASOS_TONO))

	def _sonido(self, nombre: str, mono: bool, apagado: bool, paso_tono: int) -> Any:
		"""Un ``pygame.mixer.Sound`` del sonido, quizá a un canal, apagado o con otro tono. Se guarda preparado."""
		clave = (nombre, mono, apagado, paso_tono)
		hecho = self._variantes.get(clave)
		if hecho is not None:
			return hecho
		datos = self._sonidos[nombre]
		if mono:
			datos = a_mono(datos)
		if apagado:
			datos = sintesis.apagar(datos, CORTE_APAGADO)
		if paso_tono:
			tono = 2.0 ** (paso_tono / PASOS_TONO)
			datos = sintesis.remuestrear(datos, int(round(FRECUENCIA * tono)), FRECUENCIA)
		if datos.ndim == 1:
			datos = np.column_stack([datos, datos])
		pcm = np.ascontiguousarray(np.clip(datos, -1.0, 1.0) * 32767.0, dtype=np.int16)
		hecho = self._pygame.mixer.Sound(buffer=pcm.tobytes())
		if len(self._variantes) >= VARIANTES_MAXIMAS:
			self._variantes.pop(next(iter(self._variantes)))
		self._variantes[clave] = hecho
		return hecho

	def _sonido_cambiado(self, nombre: str) -> None:
		for clave in [c for c in self._variantes if c[0] == nombre]:
			self._variantes.pop(clave, None)

	# ── Canales ──

	def _lados(self, canal: Canal) -> tuple[float, float, float]:
		"""(volumen izquierdo, volumen derecho, cuánto se apagan los agudos) de un canal ahora."""
		g = canal.ganancia * (0.0 if self._callado else self._maestro)
		angulo: float | None = None
		distancia = 0.0
		if canal.pos is not None:
			angulo, horizontal, altura = mundo_a_relativo(self._oyente, canal.pos)
			distancia = math.hypot(horizontal, altura)
		elif canal.relativo is not None:
			angulo, distancia = canal.relativo
		if angulo is None:
			general, agudos = ganancias_filtro(canal.filtro)
			return g * general, g * general, 1.0 - agudos
		g *= ganancia_distancia(distancia, self.referencia, self.caida, self.maxima)
		detras = factor_detras(angulo)
		general, agudos = ganancias_filtro(canal.filtro, detras, self.refuerzo_detras)
		# Sin filtro variable, lo de detrás baja además un poco de volumen (hasta un 30 %), como en Puerto Bravo.
		g *= general * (1.0 - 0.3 * detras * self.refuerzo_detras)
		pan = 0.0 if self.mono else math.sin(math.radians(angulo)) * min(1.0, distancia / CERCA)
		a = (pan + 1.0) * math.pi / 4.0
		izquierda = g * 1.3 * (SUELO_LADO + (1.0 - SUELO_LADO) * math.cos(a))
		derecha = g * 1.3 * (SUELO_LADO + (1.0 - SUELO_LADO) * math.sin(a))
		return izquierda, derecha, 1.0 - agudos

	def _empezar(self, canal: Canal) -> bool:
		datos = self._datos(canal.nombre)
		if datos is None:
			return False
		posicionada = canal.pos is not None or canal.relativo is not None
		izquierda, derecha, apagar = self._lados(canal)
		try:
			sonido = self._sonido(canal.nombre, datos.ndim == 2 and posicionada, apagar > 0.5, self._tono_redondeado(canal.tono))
			canal_pg = sonido.play(loops=-1 if canal.bucle else 0)
		except self._pygame.error:
			log.warning("pygame no pudo hacer sonar %s.", canal.nombre, exc_info=True)
			return False
		if canal_pg is None:
			log.debug("pygame no tiene canales libres para %s.", canal.nombre)
			return False
		canal_pg.set_volume(min(1.0, izquierda), min(1.0, derecha))
		if canal.pausado:
			canal_pg.pause()
		canal.interno = _Sonando(canal_pg, sonido)
		return True

	def _aplicar(self, canal: Canal) -> None:
		sonando: _Sonando | None = canal.interno
		if sonando is None:
			return
		izquierda, derecha, _apagar = self._lados(canal)
		sonando.canal.set_volume(min(1.0, izquierda), min(1.0, derecha))

	def _detener(self, canal: Canal) -> None:
		sonando: _Sonando | None = canal.interno
		canal.interno = None
		if sonando is None or self._pygame is None or not self._pygame.mixer.get_init():
			return
		if sonando.canal.get_sound() is sonando.sonido:
			sonando.canal.stop()

	def _sigue(self, canal: Canal) -> bool:
		sonando: _Sonando | None = canal.interno
		if sonando is None:
			return False
		# pygame reutiliza los canales: hay que comprobar que sigue siendo nuestro sonido.
		return bool(sonando.canal.get_busy()) and sonando.canal.get_sound() is sonando.sonido

	def _pausar_canal(self, canal: Canal, si: bool) -> None:
		sonando: _Sonando | None = canal.interno
		if sonando is None:
			return
		if si:
			sonando.canal.pause()
		else:
			sonando.canal.unpause()

	# ── Por fotograma y cierre ──

	def tic(self, dt: float) -> None:
		"""Además de lo común, avisa al vigilante."""
		if not self._iniciado:
			return
		if self.vigilante is not None:
			self.vigilante.latido()
		super().tic(dt)

	def _callar_por_seguridad(self) -> None:
		"""Lo llama el vigilante desde su hilo: pausa todo el mezclador."""
		self._callado = True
		if self._pygame is not None and self._pygame.mixer.get_init():
			self._pygame.mixer.pause()

	def _volver_de_silencio(self) -> None:
		"""El juego ha vuelto: se reanuda desde el silencio, respetando lo que estaba en pausa."""
		self._callado = False
		self._maestro = 0.0
		if self._pygame is None or not self._pygame.mixer.get_init():
			return
		self._pygame.mixer.unpause()
		for canal in self._canales.values():
			if canal.pausado:
				self._pausar_canal(canal, True)

	def cerrar(self) -> None:
		"""Para lo que suena y, si este motor abrió el mezclador, lo cierra."""
		if self.vigilante is not None:
			self.vigilante.parar()
			self.vigilante = None
		if self._iniciado:
			self.parar_todo()
		self._iniciado = False
		self._variantes.clear()
		if self._pygame is not None and self._mezclador_propio and self._pygame.mixer.get_init():
			self._pygame.mixer.quit()
		self._mezclador_propio = False

	def estado(self) -> dict:
		"""Lo común más el formato del mezclador."""
		datos = super().estado()
		datos.update(
			{
				"dispositivo": self.nombre_salida,
				"formato": self._pygame.mixer.get_init() if self._pygame is not None else None,
				"hrtf_activo": False,
				"reverberacion": False,
			}
		)
		return datos
