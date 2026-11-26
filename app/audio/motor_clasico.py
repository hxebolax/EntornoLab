"""Motor clásico: mezclador propio con numpy y salida por sounddevice.

Es el mezclador de Puerto Bravo (mismo autor) adaptado a la interfaz común. No usa HRTF: cada
sonido se coloca con

- **panorama** de potencia constante, sin dejar nunca mudo del todo el oído lejano;
- **diferencia de tiempo entre oídos** (hasta 0,63 ms: el oído lejano lo recibe más tarde);
- **atenuación por distancia** con la misma ley que los demás motores;
- **filtro** que apaga lo que queda detrás y lo que llega a través de una pared (se funde con una
  versión del sonido pasada por un paso bajo).

Lo que tiene y no tienen los demás: una **segunda salida** con exactamente la misma mezcla, para que
el profesional oiga por sus auriculares o por un altavoz lo mismo que el alumno. No tiene
reverberación (el preset de acústica se recuerda pero no se oye).

La salida es la de Windows por WASAPI, siguiéndola si cambia, o la elegida; si se desconecta, se
vuelve a abrir sola donde toque. Con ``memoria`` en las opciones no se abre ninguna salida y
:meth:`renderizar` devuelve la mezcla (pruebas).
"""

from __future__ import annotations

import collections
import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Any

import numpy as np

from app.audio import salidas, sintesis
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

ITD_MAXIMO = 28.0  # muestras de retardo máximo entre oídos (0,63 ms a 44,1 kHz)
RELLENO = 32  # muestras de margen para poder retrasar un oído
CORTE_APAGADO = 900.0  # hercios del paso bajo de la versión apagada
SUELO_OIDO_LEJANO = 0.15  # el oído contrario nunca baja de esta parte: una cabeza no tapa del todo
CERCA = 0.75  # metros por debajo de los cuales el panorama se va cerrando hacia el centro
VIGILAR_CADA = 1.5  # segundos entre dos miradas a la salida de sonido
CORTE_SALIDA = 1.5  # sin que la salida pida sonido en este tiempo, se ha cortado


@dataclass
class _Voz:
	"""Estado de mezcla de un canal. Lo escribe el hilo del juego y lo lee el de la tarjeta de sonido."""

	datos: np.ndarray
	apagado: np.ndarray | None
	largo: int
	estereo: bool
	bucle: bool
	pos: float = 0.0
	ritmo: float = 1.0
	ritmo_objetivo: float = 1.0
	gi: float = 0.0  # ganancia izquierda aplicada y su objetivo
	gd: float = 0.0
	gi_objetivo: float = 0.0
	gd_objetivo: float = 0.0
	ri: float = 0.0  # retardo de cada oído, en muestras, y su objetivo
	rd: float = 0.0
	ri_objetivo: float = 0.0
	rd_objetivo: float = 0.0
	apagar: float = 0.0  # cuánto de la versión apagada se mezcla (0 nada, 1 todo)
	apagar_objetivo: float = 0.0
	pausada: bool = False
	fin: bool = False


class MotorClasico(MotorBase):
	"""Mezcla propia con numpy; sale por sounddevice. Ver el docstring del módulo."""

	nombre = "clasico"
	FUENTES_MAXIMAS = 56

	def __init__(self) -> None:
		super().__init__()
		self.memoria = False
		self.holgado = False
		self.dispositivo_pedido = ""
		self.segunda_pedida = ""
		self.nombre_salida = ""
		self.nombre_segunda = ""
		self.vigilante: Vigilante | None = None
		self._sd: Any = None
		self._flujo: Any = None
		self._flujo_segundo: Any = None
		self._cola_segunda: collections.deque[np.ndarray] = collections.deque()
		self._candado_segunda = threading.Lock()
		self._candado = threading.Lock()
		self._voces: dict[int, _Voz] = {}
		self._variantes: dict[tuple[str, bool, bool, bool], np.ndarray] = {}
		self._indices = np.arange(8192 + RELLENO, dtype=np.float64)
		self._maestro_mezcla = 0.0
		self._callado = False
		self._t_pedido = 0.0
		self._t_vigila = 0.0
		self._defecto_visto = ""
		self._fallo_avisado = False

	# ── Disponibilidad y arranque ──

	@classmethod
	def disponible(cls) -> tuple[bool, str]:
		"""Hace falta el paquete sounddevice (PortAudio)."""
		try:
			import sounddevice  # noqa: F401 - solo se comprueba que está
		except (ImportError, OSError) as error:
			return False, _("No se puede usar sounddevice: {error}").format(error=error)
		return True, ""

	def _leer_opciones(self, opciones: dict) -> None:
		super()._leer_opciones(opciones)
		self.holgado = bool(self.opciones.get("holgado", False))
		self.segunda_pedida = str(self.opciones.get("segunda_salida") or "")

	def iniciar(self, dispositivo: str | None, opciones: dict) -> None:
		"""Abre la salida (y la segunda, si se pide). En memoria no abre nada."""
		if self._iniciado:
			self.cerrar()
		self._leer_opciones(opciones)
		self.memoria = bool(self.opciones.get("memoria", False))
		self.dispositivo_pedido = str(dispositivo or "")
		self._callado = False
		self.vigilante = Vigilante(self.proteccion.silencio_sin_tic, self._callar_por_seguridad, self._volver_de_silencio)
		if not self.memoria:
			try:
				import sounddevice as sd
			except (ImportError, OSError) as error:
				raise MotorNoDisponible(f"no se puede usar sounddevice: {error}") from error
			self._sd = sd
			self._abrir()
			if self._flujo is None:
				raise ErrorMotor("no se pudo abrir ninguna salida de sonido con sounddevice")
		self._iniciado = True
		log.info(
			"Motor clásico iniciado: salida «%s»%s.",
			self.nombre_salida or "en memoria",
			f", segunda salida «{self.nombre_segunda}»" if self.nombre_segunda else "",
		)

	def _wasapi(self, nombre: str = "") -> int | None:
		"""El índice WASAPI de esa salida, o el de la de por defecto si no se da nombre."""
		sd = self._sd
		try:
			for anfitrion in sd.query_hostapis():
				if "WASAPI" not in anfitrion["name"]:
					continue
				if not nombre:
					return anfitrion["default_output_device"] if anfitrion["default_output_device"] >= 0 else None
				for indice in anfitrion["devices"]:
					info = sd.query_devices(indice)
					if info["max_output_channels"] > 0 and (info["name"] == nombre or salidas.coincide(nombre, info["name"])):
						return indice
		except sd.PortAudioError, KeyError, ValueError:
			log.warning("No se pudieron consultar las salidas WASAPI.", exc_info=True)
		return None

	def dispositivos(self) -> list[str]:
		"""Nombres de las salidas WASAPI (o de todas, si no hay WASAPI)."""
		try:
			import sounddevice as sd
		except ImportError, OSError:
			log.warning("No se puede usar sounddevice para listar las salidas.", exc_info=True)
			return []
		nombres: list[str] = []
		try:
			anfitriones = sd.query_hostapis()
			wasapi = [a for a in anfitriones if "WASAPI" in a["name"]]
			indices = wasapi[0]["devices"] if wasapi else range(len(sd.query_devices()))
			for indice in indices:
				info = sd.query_devices(indice)
				if info["max_output_channels"] > 0 and info["name"] not in nombres:
					nombres.append(info["name"])
		except sd.PortAudioError, KeyError, ValueError:
			log.warning("No se pudieron enumerar las salidas de sonido.", exc_info=True)
		return nombres

	def _abrir(self) -> None:
		"""Abre la salida: la elegida, si está; si no, la de Windows por WASAPI; y si falla, la de PortAudio."""
		sd = self._sd
		self._defecto_visto = salidas.por_defecto()
		bloque_wasapi = 2048 if self.holgado else 512
		intentos: list[tuple[int | None, Any, int]] = []
		elegida = self._wasapi(self.dispositivo_pedido) if self.dispositivo_pedido else None
		if self.dispositivo_pedido and elegida is None:
			log.warning("No está la salida de sonido «%s»: se usa la de Windows.", self.dispositivo_pedido)
		if elegida is not None:
			intentos.append((elegida, sd.WasapiSettings(auto_convert=True), bloque_wasapi))
		defecto = self._wasapi()
		if defecto is not None and defecto != elegida:
			intentos.append((defecto, sd.WasapiSettings(auto_convert=True), bloque_wasapi))
		intentos.append((None, None, 4096 if self.holgado else 1024))
		for dispositivo, extra, bloque in intentos:
			try:
				flujo = sd.OutputStream(
					samplerate=FRECUENCIA,
					channels=2,
					dtype="float32",
					blocksize=bloque,
					callback=self._al_pedir,
					latency="high" if self.holgado else "low",
					device=dispositivo,
					extra_settings=extra,
				)
				flujo.start()
			except sd.PortAudioError, ValueError, OSError:
				log.warning("No se pudo abrir la salida de sonido %s con bloque %s.", dispositivo, bloque, exc_info=True)
				continue
			self._flujo = flujo
			self._t_pedido = time.monotonic()
			try:
				self.nombre_salida = str(sd.query_devices(flujo.device)["name"])
			except sd.PortAudioError, KeyError, ValueError, TypeError:
				log.debug("No se pudo saber el nombre de la salida abierta.", exc_info=True)
				self.nombre_salida = ""
			self._abrir_segunda()
			return
		self._flujo = None

	def _abrir_segunda(self) -> None:
		"""La segunda salida: otros auriculares, un altavoz o un cable virtual, con la misma mezcla."""
		self._cerrar_segunda()
		if not self.segunda_pedida or self._flujo is None:
			return
		sd = self._sd
		indice = self._wasapi(self.segunda_pedida)
		if indice is None:
			log.warning("No está la segunda salida de sonido «%s».", self.segunda_pedida)
			return
		if indice == getattr(self._flujo, "device", None):
			log.info("La segunda salida es la misma que la principal: no se abre dos veces.")
			return
		try:
			flujo = sd.OutputStream(
				samplerate=FRECUENCIA,
				channels=2,
				dtype="float32",
				blocksize=self._flujo.blocksize or 512,
				callback=self._al_pedir_segunda,
				latency="high",
				device=indice,
				extra_settings=sd.WasapiSettings(auto_convert=True),
			)
			flujo.start()
		except sd.PortAudioError, ValueError, OSError:
			log.warning("No se pudo abrir la segunda salida de sonido.", exc_info=True)
			return
		self._flujo_segundo = flujo
		try:
			self.nombre_segunda = str(sd.query_devices(indice)["name"])
		except sd.PortAudioError, KeyError, ValueError, TypeError:
			log.debug("No se pudo saber el nombre de la segunda salida.", exc_info=True)
			self.nombre_segunda = self.segunda_pedida

	def _cerrar_flujo(self, flujo: Any) -> None:
		if flujo is None:
			return
		try:
			flujo.stop()
			flujo.close()
		except self._sd.PortAudioError, OSError:
			log.debug("Error al cerrar una salida de sonido.", exc_info=True)

	def _cerrar_segunda(self) -> None:
		flujo, self._flujo_segundo = self._flujo_segundo, None
		self.nombre_segunda = ""
		self._cerrar_flujo(flujo)
		with self._candado_segunda:
			self._cola_segunda.clear()

	def _cerrar_salidas(self) -> None:
		self._cerrar_segunda()
		flujo, self._flujo = self._flujo, None
		self._cerrar_flujo(flujo)

	# ── Seguir, recuperar y cambiar la salida ──

	def _vigilar_salida(self) -> None:
		"""Cada poco: si la salida se ha cortado, si la de Windows ha cambiado o si ha vuelto la elegida, se reabre."""
		ahora = time.monotonic()
		if self.memoria or ahora - self._t_vigila < VIGILAR_CADA:
			return
		self._t_vigila = ahora
		defecto = salidas.por_defecto()
		motivo = ""
		if self._flujo is None:
			motivo = "sin salida"
		elif ahora - self._t_pedido > CORTE_SALIDA:
			motivo = "se ha cortado"
		elif not self.dispositivo_pedido and defecto and self._defecto_visto and defecto != self._defecto_visto:
			motivo = "ha cambiado la de Windows"
		elif (
			self.dispositivo_pedido
			and self.dispositivo_pedido != self.nombre_salida
			and not salidas.coincide(self.dispositivo_pedido, self.nombre_salida)
			and salidas.presente(self.dispositivo_pedido)
		):
			motivo = "ha vuelto la elegida"
		elif self.segunda_pedida and self._flujo_segundo is None and salidas.presente(self.segunda_pedida):
			motivo = "ha vuelto la segunda"
		if defecto:
			self._defecto_visto = defecto
		if motivo:
			self._reabrir(motivo)

	def _reabrir(self, motivo: str) -> bool:
		"""Cierra la salida y la vuelve a abrir con la lista de dispositivos al día. Lo que sonaba sigue."""
		if self.memoria or self._sd is None:
			return False
		antes = self.nombre_salida
		self._cerrar_salidas()
		sd = self._sd
		try:
			# PortAudio solo ve los dispositivos nuevos si se reinicia (no hay otra forma en sounddevice).
			sd._terminate()
			sd._initialize()
		except sd.PortAudioError, OSError:
			log.warning("No se pudo reiniciar PortAudio.", exc_info=True)
		self._abrir()
		log.info(
			"Salida de sonido abierta de nuevo (%s): antes «%s», ahora «%s», segunda «%s».",
			motivo,
			antes,
			self.nombre_salida,
			self.nombre_segunda,
		)
		return self._flujo is not None

	def cambiar_dispositivo(self, dispositivo: str | None) -> bool:
		"""Cambia en caliente la salida principal (vacío: la de Windows)."""
		self.dispositivo_pedido = str(dispositivo or "")
		return self._reabrir("cambiada en las preferencias")

	def cambiar_segunda_salida(self, dispositivo: str | None) -> bool:
		"""Pone, cambia o quita (vacío) la segunda salida, la del profesional. Devuelve si quedó abierta."""
		self.segunda_pedida = str(dispositivo or "")
		self.opciones["segunda_salida"] = self.segunda_pedida
		if self.memoria or self._sd is None:
			return False
		self._abrir_segunda()
		return self._flujo_segundo is not None

	def configurar(self, opciones: dict) -> None:
		"""Aplica en caliente lo común y la segunda salida."""
		antes = self.segunda_pedida
		super().configurar(opciones)
		if self._iniciado and self.segunda_pedida != antes:
			self.cambiar_segunda_salida(self.segunda_pedida)

	# ── Canales ──

	def _variante(self, nombre: str, mono: bool, apagado: bool, bucle: bool) -> np.ndarray:
		"""El sonido listo para leerse interpolando: con dos muestras de más (las del principio si es bucle)."""
		clave = (nombre, mono, apagado, bucle)
		hecha = self._variantes.get(clave)
		if hecha is None:
			datos = self._sonidos[nombre]
			if mono:
				datos = a_mono(datos)
			if apagado:
				datos = np.ascontiguousarray(sintesis.apagar(datos, CORTE_APAGADO), dtype=np.float32)
			if bucle:
				hecha = np.concatenate([datos, datos[:2]])
			else:
				hecha = np.concatenate([datos, np.zeros((2,) + datos.shape[1:], np.float32)])
			self._variantes[clave] = hecha
		return hecha

	def _sonido_cambiado(self, nombre: str) -> None:
		for clave in [c for c in self._variantes if c[0] == nombre]:
			self._variantes.pop(clave, None)

	def _empezar(self, canal: Canal) -> bool:
		datos = self._datos(canal.nombre)
		if datos is None or len(datos) < 2:
			return False
		posicionada = canal.pos is not None or canal.relativo is not None
		estereo = datos.ndim == 2 and not posicionada
		mono = datos.ndim == 2 and posicionada
		voz = _Voz(
			datos=self._variante(canal.nombre, mono, False, canal.bucle),
			apagado=None if estereo else self._variante(canal.nombre, mono, True, canal.bucle),
			largo=len(datos),
			estereo=estereo,
			bucle=canal.bucle,
			ritmo=canal.tono,
			ritmo_objetivo=canal.tono,
			pausada=canal.pausado,
		)
		canal.interno = voz
		self._aplicar(canal)
		voz.gi, voz.gd = voz.gi_objetivo, voz.gd_objetivo
		voz.ri, voz.rd, voz.apagar = voz.ri_objetivo, voz.rd_objetivo, voz.apagar_objetivo
		with self._candado:
			self._voces[canal.id] = voz
		return True

	def _aplicar(self, canal: Canal) -> None:
		"""Calcula las ganancias de cada oído, el retardo entre oídos y el apagado de un canal."""
		voz: _Voz = canal.interno
		g = canal.ganancia
		voz.ritmo_objetivo = canal.tono
		angulo: float | None = None
		distancia = 0.0
		if canal.pos is not None:
			angulo, horizontal, altura = mundo_a_relativo(self._oyente, canal.pos)
			distancia = math.hypot(horizontal, altura)
		elif canal.relativo is not None:
			angulo, distancia = canal.relativo
		if angulo is None:
			general, agudos = ganancias_filtro(canal.filtro)
			voz.gi_objetivo = voz.gd_objetivo = g * general
			voz.ri_objetivo = voz.rd_objetivo = 0.0
			voz.apagar_objetivo = min(0.97, 1.0 - agudos)
			return
		g *= ganancia_distancia(distancia, self.referencia, self.caida, self.maxima)
		detras = factor_detras(angulo)
		pan = 0.0 if self.mono else math.sin(math.radians(angulo)) * min(1.0, distancia / CERCA)
		general, agudos = ganancias_filtro(canal.filtro, detras, self.refuerzo_detras)
		g *= general
		a = (pan + 1.0) * math.pi / 4.0
		voz.gi_objetivo = g * 1.3 * (SUELO_OIDO_LEJANO + (1.0 - SUELO_OIDO_LEJANO) * math.cos(a))
		voz.gd_objetivo = g * 1.3 * (SUELO_OIDO_LEJANO + (1.0 - SUELO_OIDO_LEJANO) * math.sin(a))
		voz.ri_objetivo = ITD_MAXIMO * pan if pan > 0 else 0.0
		voz.rd_objetivo = -ITD_MAXIMO * pan if pan < 0 else 0.0
		voz.apagar_objetivo = min(0.97, 1.0 - agudos)

	def _detener(self, canal: Canal) -> None:
		voz: _Voz | None = canal.interno
		if voz is not None:
			voz.fin = True
		with self._candado:
			self._voces.pop(canal.id, None)
		canal.interno = None

	def _sigue(self, canal: Canal) -> bool:
		voz: _Voz | None = canal.interno
		return voz is not None and not voz.fin

	def _pausar_canal(self, canal: Canal, si: bool) -> None:
		voz: _Voz | None = canal.interno
		if voz is not None:
			voz.pausada = si

	# ── Mezcla ──

	@staticmethod
	def _leer(datos: np.ndarray, indices: np.ndarray, largo: int, bucle: bool) -> np.ndarray:
		"""Muestras en posiciones fraccionarias (interpolación lineal): así se cambia el tono."""
		indices = np.mod(indices, largo) if bucle else np.clip(indices, 0.0, float(largo))
		enteros = indices.astype(np.int64)
		fraccion = (indices - enteros).astype(np.float32)
		if datos.ndim == 2:
			fraccion = fraccion[:, None]
		a = datos[enteros]
		return a + (datos[enteros + 1] - a) * fraccion

	def renderizar(self, muestras: int) -> np.ndarray:
		"""Mezcla las siguientes ``muestras``: matriz float32 (muestras, 2). Lo llama la tarjeta de sonido (o una prueba)."""
		n = int(muestras)
		mezcla = np.zeros((n, 2), np.float32)
		if n + RELLENO > len(self._indices):
			self._indices = np.arange(n + RELLENO, dtype=np.float64)
		ar = self._indices
		with self._candado:
			voces = list(self._voces.values())
		rampa = ar[:n].astype(np.float32) / max(1, n)
		for v in voces:
			if v.fin or v.pausada:
				continue
			v.ritmo += (v.ritmo_objetivo - v.ritmo) * 0.4
			r = v.ritmo
			largo = v.largo
			gi1, gd1 = v.gi_objetivo, v.gd_objetivo
			if v.gi < 1e-4 and v.gd < 1e-4 and gi1 < 1e-4 and gd1 < 1e-4:
				# No se oye: avanza sin gastar cálculo.
				v.ri, v.rd, v.apagar = v.ri_objetivo, v.rd_objetivo, v.apagar_objetivo
			elif v.estereo:
				s = self._leer(v.datos, v.pos + ar[:n] * r, largo, v.bucle)
				mezcla[:, 0] += s[:, 0] * (v.gi + (gi1 - v.gi) * rampa)
				mezcla[:, 1] += s[:, 1] * (v.gd + (gd1 - v.gd) * rampa)
			else:
				indices = v.pos + (ar[: n + RELLENO] - RELLENO) * r
				s = self._leer(v.datos, indices, largo, v.bucle)
				if v.apagado is not None and (v.apagar > 0.02 or v.apagar_objetivo > 0.02):
					sm = self._leer(v.apagado, indices, largo, v.bucle)
					m = np.empty(n + RELLENO, np.float32)
					m[:RELLENO] = v.apagar
					m[RELLENO:] = v.apagar + (v.apagar_objetivo - v.apagar) * rampa
					s = s + (sm - s) * m
				base = s[RELLENO:]
				if v.ri > 0.01 or v.ri_objetivo > 0.01:
					izquierda = np.interp(RELLENO + ar[:n] - (v.ri + (v.ri_objetivo - v.ri) * rampa), ar[: n + RELLENO], s)
				else:
					izquierda = base
				if v.rd > 0.01 or v.rd_objetivo > 0.01:
					derecha = np.interp(RELLENO + ar[:n] - (v.rd + (v.rd_objetivo - v.rd) * rampa), ar[: n + RELLENO], s)
				else:
					derecha = base
				mezcla[:, 0] += izquierda * (v.gi + (gi1 - v.gi) * rampa)
				mezcla[:, 1] += derecha * (v.gd + (gd1 - v.gd) * rampa)
				v.ri, v.rd, v.apagar = v.ri_objetivo, v.rd_objetivo, v.apagar_objetivo
			v.gi, v.gd = gi1, gd1
			v.pos += n * r
			if v.bucle:
				v.pos %= largo
			elif v.pos >= largo:
				v.fin = True
		# Ganancia maestra con rampa dentro del bloque: ni un cambio de volumen ni el silencio de seguridad dan un clic.
		objetivo = 0.0 if self._callado else self._maestro
		if objetivo != self._maestro_mezcla:
			mezcla *= (self._maestro_mezcla + (objetivo - self._maestro_mezcla) * rampa)[:, None]
			self._maestro_mezcla = objetivo
		else:
			mezcla *= objetivo
		if self.mono:
			medio = mezcla.mean(axis=1)
			mezcla[:, 0] = medio
			mezcla[:, 1] = medio
		return self.proteccion.limitar_mezcla(mezcla)

	def _al_pedir(self, salida: np.ndarray, cuadros: int, _tiempo: Any, _estado: Any) -> None:
		"""La tarjeta de sonido pide muestras (hilo de PortAudio)."""
		self._t_pedido = time.monotonic()
		if self.vigilante is not None:
			self.vigilante.comprobar(self._t_pedido)
		try:
			salida[:] = self.renderizar(cuadros)
		except Exception:  # noqa: BLE001 - en el hilo de sonido un fallo no puede propagarse: silencio y registro
			salida.fill(0)
			if not self._fallo_avisado:
				self._fallo_avisado = True
				log.exception("Fallo al mezclar el sonido; ese bloque sale en silencio.")
		if self._flujo_segundo is not None:
			with self._candado_segunda:
				self._cola_segunda.append(salida.copy())
				# Sin acumular retraso: lo viejo se tira.
				while sum(len(b) for b in self._cola_segunda) > FRECUENCIA // 4:
					self._cola_segunda.popleft()

	def _al_pedir_segunda(self, salida: np.ndarray, cuadros: int, _tiempo: Any, _estado: Any) -> None:
		"""La segunda salida toma de la cola lo mismo que acaba de salir por la principal."""
		puesto = 0
		with self._candado_segunda:
			while puesto < cuadros and self._cola_segunda:
				bloque = self._cola_segunda[0]
				cuantos = min(cuadros - puesto, len(bloque))
				salida[puesto : puesto + cuantos] = bloque[:cuantos]
				if cuantos == len(bloque):
					self._cola_segunda.popleft()
				else:
					self._cola_segunda[0] = bloque[cuantos:]
				puesto += cuantos
		if puesto < cuadros:
			salida[puesto:] = 0

	# ── Por fotograma, cierre y diagnóstico ──

	def tic(self, dt: float) -> None:
		"""Además de lo común: avisa al vigilante y mira si hay que reabrir la salida."""
		if not self._iniciado:
			return
		if self.vigilante is not None:
			self.vigilante.latido()
		self._vigilar_salida()
		super().tic(dt)

	def _callar_por_seguridad(self) -> None:
		self._callado = True

	def _volver_de_silencio(self) -> None:
		self._callado = False
		self._maestro = 0.0

	def cerrar(self) -> None:
		"""Para todo y cierra las salidas."""
		if self._iniciado:
			self.parar_todo()
		self._iniciado = False
		if self._sd is not None:
			self._cerrar_salidas()
		with self._candado:
			self._voces.clear()

	def estado(self) -> dict:
		"""Lo común más las salidas abiertas."""
		datos = super().estado()
		datos.update(
			{
				"dispositivo": self.nombre_salida,
				"segunda_salida": self.nombre_segunda,
				"memoria": self.memoria,
				"hrtf_activo": False,
				"reverberacion": False,
			}
		)
		return datos
