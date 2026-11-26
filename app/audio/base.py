"""Interfaz común de los motores de sonido y las cuentas que comparten.

Todos los motores (OpenAL, clásico, estéreo, BASS y nulo) reciben lo mismo: posiciones en las
coordenadas del proyecto (x al este, y al norte, z hacia arriba, en metros; rumbo 0 = norte, en el
sentido del reloj) y cada uno las convierte a lo suyo. Lo que aquí se decide una sola vez, para que
todos suenen coherentes:

- **Distancia.** Ley inversa recortada, la misma que ``AL_INVERSE_DISTANCE_CLAMPED`` de OpenAL::

      ganancia = ref / (ref + caida * (min(max(d, ref), maxima) - ref))

  Con ``ref = 1 m`` y ``caida = 1`` es la ley física de un punto sonoro (6 dB menos cada vez que se
  dobla la distancia). Nunca sube por encima de 1 al acercarse y no hay un «borde» artificial donde
  el sonido desaparezca: lo que suena lejos está lejos. La referencia es pequeña porque el programa
  es sobre todo de interiores; es ajustable.
- **Oclusión y «detrás».** ``filtro`` (0 a 1) lo calcula el motor del juego (paredes, puertas); la
  capa de sonido lo convierte en un paso bajo. Además, lo que queda detrás del oyente se apaga un
  poco como refuerzo de la pista delante/detrás (ver :func:`ganancias_filtro`).
- **Buses** con su volumen, y la atenuación del ambiente y la música mientras habla la voz.
- **Protección auditiva** (:mod:`app.audio.proteccion`).

Este módulo no importa ninguna biblioteca de sonido: solo numpy.
"""

from __future__ import annotations

import logging
import math
from abc import ABC, abstractmethod
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from app.audio.proteccion import Proteccion

log = logging.getLogger(__name__)

FRECUENCIA = 44100

# Buses de volumen. «maestro» multiplica a todos.
BUSES: tuple[str, ...] = ("maestro", "efectos", "pasos", "ambiente", "ayudas", "interfaz", "musica", "voz")
VOLUMENES_DE_SERIE: dict[str, float] = {
	"maestro": 0.8,
	"efectos": 1.0,
	"pasos": 0.8,
	"ambiente": 0.6,
	"ayudas": 1.0,
	"interfaz": 0.8,
	"musica": 0.5,
	"voz": 1.0,
}
# Buses que bajan mientras habla la voz, y cuánto.
BUSES_ATENUADOS: tuple[str, ...] = ("ambiente", "musica")
ATENUACION_VOZ = 0.45
# Buses que NO se detienen con ``pausar``: los menús y la voz grabada siguen sonando.
BUSES_SIN_PAUSA: tuple[str, ...] = ("interfaz", "voz")
# Importancia de cada bus al repartir las fuentes: cuando no quedan, se roba la menos importante.
PRIORIDAD_BUS: dict[str, int] = {
	"voz": 100,
	"interfaz": 90,
	"ayudas": 80,
	"pasos": 60,
	"efectos": 50,
	"ambiente": 30,
	"musica": 20,
}

ACUSTICAS: tuple[str, ...] = (
	"seca",
	"habitacion",
	"sala_grande",
	"pasillo",
	"bano",
	"escalera",
	"nave",
	"exterior",
	"calle",
	"parque",
)

# Distancia: metros a los que un sonido suena a su volumen nominal, pendiente de la caída y tope.
DISTANCIA_REFERENCIA = 1.0
DISTANCIA_CAIDA = 1.0
DISTANCIA_MAXIMA = 60.0

# Refuerzo de lo que queda detrás: empieza pasados los 70 grados a cada lado y es total justo detrás.
ANGULO_DETRAS = 70.0
# Cuánto quita de agudos lo de detrás con el refuerzo al máximo (0.85 = queda el 15 %).
APAGADO_DETRAS = 0.85

Posicion3 = tuple[float, float, float]
Relativo = tuple[float, float]


class ErrorMotor(RuntimeError):
	"""Un motor de sonido no ha podido arrancar o ha fallado al usarlo."""


class MotorNoDisponible(ErrorMotor):
	"""Falta algo para usar ese motor en este equipo (una biblioteca, una DLL, un dispositivo)."""


# ── Lo que la capa de sonido espera del motor del juego (duck typing) ────────


class FuenteActivaP(Protocol):
	"""Una fuente continua que el motor del juego dice que se oye ahora."""

	id: str
	sonido: str
	pos: Posicion3
	volumen: float
	tono: float
	filtro: float
	bucle: bool


class SesionP(Protocol):
	"""Lo que el presentador usa de ``app.motor.sesion.Sesion``."""

	def oyente(self) -> tuple[float, float, float, float]: ...

	def fuentes(self) -> list[FuenteActivaP]: ...


# ── Cuentas compartidas ──────────────────────────────────────────────────────


def recortar(valor: float, minimo: float = 0.0, maximo: float = 1.0) -> float:
	"""``valor`` dentro de [minimo, maximo]; un NaN se queda en el mínimo para no llevar basura al sonido."""
	if valor != valor:  # NaN
		return minimo
	return max(minimo, min(maximo, float(valor)))


def normalizar_angulo(grados: float) -> float:
	"""El mismo ángulo entre -180 y 180."""
	return (grados + 180.0) % 360.0 - 180.0


def mundo_a_relativo(oyente: tuple[float, float, float, float], pos: Posicion3) -> tuple[float, float, float]:
	"""(ángulo, distancia horizontal, diferencia de altura) de ``pos`` vista por el oyente.

	El ángulo va en grados respecto de hacia dónde mira: 0 delante, 90 a la derecha, ±180 detrás.
	"""
	ox, oy, oz, rumbo = oyente
	dx = pos[0] - ox
	dy = pos[1] - oy
	distancia = math.hypot(dx, dy)
	if distancia < 1e-6:
		return 0.0, 0.0, pos[2] - oz
	return normalizar_angulo(math.degrees(math.atan2(dx, dy)) - rumbo), distancia, pos[2] - oz


def relativo_a_mundo(oyente: tuple[float, float, float, float], angulo: float, distancia: float) -> Posicion3:
	"""Punto del mundo que está a ``distancia`` metros y ``angulo`` grados (0 delante, 90 derecha) del oyente."""
	ox, oy, oz, rumbo = oyente
	r = math.radians(rumbo + angulo)
	return ox + math.sin(r) * distancia, oy + math.cos(r) * distancia, oz


def factor_detras(angulo: float | None) -> float:
	"""0 delante y a los lados; crece desde los 70 grados hasta 1 justo detrás."""
	if angulo is None:
		return 0.0
	return max(0.0, (abs(normalizar_angulo(angulo)) - ANGULO_DETRAS) / (180.0 - ANGULO_DETRAS))


def ganancia_distancia(
	distancia: float,
	referencia: float = DISTANCIA_REFERENCIA,
	caida: float = DISTANCIA_CAIDA,
	maxima: float = DISTANCIA_MAXIMA,
) -> float:
	"""Ley inversa recortada (la de OpenAL): 1 hasta ``referencia`` y luego ``ref / (ref + caida·(d − ref))``.

	Más allá de ``maxima`` no sigue bajando (no se corta): un sonido lejano se oye flojo, no desaparece
	de golpe, que sería una pista falsa.
	"""
	referencia = max(0.01, referencia)
	d = min(max(distancia, referencia), max(maxima, referencia))
	return referencia / (referencia + max(0.0, caida) * (d - referencia))


def ganancias_filtro(filtro: float, detras: float = 0.0, refuerzo: float = 1.0) -> tuple[float, float]:
	"""(ganancia general, ganancia de agudos) del paso bajo de una fuente.

	- Oclusión (``filtro`` de 0 a 1, la da el motor del juego): los agudos caen con el cuadrado,
	  ``(1 − filtro)²`` con un suelo de 0,02 (una pared deja pasar los graves), y el nivel general baja
	  como mucho un 25 %, porque el volumen ya lo ha decidido el motor del juego.
	- Detrás (``detras`` de 0 a 1 por ``refuerzo``): solo agudos, ``1 − 0,85·detras·refuerzo``.

	Las dos se multiplican. Es lo que se le da al filtro EFX de OpenAL, y los demás motores lo imitan.
	"""
	f = recortar(filtro)
	agudos = max(0.02, (1.0 - f) ** 2)
	agudos *= 1.0 - APAGADO_DETRAS * recortar(detras) * recortar(refuerzo)
	return 1.0 - 0.25 * f, max(0.01, agudos)


def preparar_datos(datos: Any, frecuencia: int = FRECUENCIA) -> np.ndarray:
	"""Muestras listas para un motor: float32 entre -1 y 1, forma (n,) o (n, 2), a 44,1 kHz.

	Admite enteros de 16 bits (se escalan) y cualquier frecuencia (se remuestrea): así los sonidos
	propios de un entorno, grabados como sea, entran igual que los de serie.
	"""
	matriz = np.asarray(datos)
	if matriz.dtype.kind in "iu":
		matriz = matriz.astype(np.float32) / float(np.iinfo(matriz.dtype).max)
	matriz = np.ascontiguousarray(matriz, dtype=np.float32)
	if matriz.ndim == 2 and matriz.shape[1] == 1:
		matriz = matriz[:, 0]
	if matriz.ndim == 2 and matriz.shape[1] > 2:
		matriz = matriz[:, :2]
	if matriz.ndim not in (1, 2):
		raise ValueError(f"forma de sonido no admitida: {matriz.shape}")
	if frecuencia != FRECUENCIA and len(matriz):
		from app.audio import sintesis

		matriz = np.ascontiguousarray(sintesis.remuestrear(matriz, int(frecuencia), FRECUENCIA), dtype=np.float32)
	return np.clip(matriz, -1.0, 1.0)


def a_mono(datos: np.ndarray) -> np.ndarray:
	"""Mezcla a un canal: lo que se posiciona en el espacio tiene que ser mono."""
	return datos if datos.ndim == 1 else np.ascontiguousarray(datos.mean(axis=1), dtype=np.float32)


def carpetas_de_serie(*partes: str) -> list[Path]:
	"""Dónde buscar un recurso que viaja con el programa (``bin/openal``, ``sounds``, ``plugins``).

	Primero en la carpeta ``data`` activa y después en la ``data`` que está junto al programa: con
	``APP_DATA_DIR`` (pruebas, perfiles aparte) los datos del usuario van a otra carpeta, pero las
	bibliotecas y los sonidos de serie siguen estando donde se instaló el programa.
	"""
	from app.core import paths

	candidatas = [paths.ruta_datos().joinpath(*partes), paths.ruta_base().joinpath("data", *partes)]
	vistas: list[Path] = []
	for carpeta in candidatas:
		if carpeta not in vistas:
			vistas.append(carpeta)
	return vistas


@dataclass
class Canal:
	"""Un sonido en marcha, tal como lo pidió el juego. Cada motor guarda aparte lo suyo."""

	id: int
	nombre: str
	bus: str = "efectos"
	pos: Posicion3 | None = None
	relativo: Relativo | None = None
	volumen: float = 1.0
	tono: float = 1.0
	bucle: bool = False
	filtro: float = 0.0
	eco: bool = True
	prioridad: int = 0
	edad: float = 0.0  # segundos sonando (lo cuenta ``tic``)
	fundido: float = 0.0  # segundos del fundido de salida en curso; 0 si no se está parando
	nivel: float = 1.0  # multiplicador del fundido (1 normal, baja a 0 al parar)
	ganancia: float = 0.0  # ganancia aplicada ahora (para las subidas graduales)
	pausado: bool = False
	interno: Any = None  # lo que el motor necesite recordar (fuente de OpenAL, canal de pygame...)

	@property
	def parando(self) -> bool:
		"""Si se está apagando para terminar."""
		return self.fundido > 0.0


class MotorAudio(ABC):
	"""Interfaz de un motor de sonido (docs/arquitectura.md, apartado «Sonido»)."""

	nombre: str = ""
	# El motor que se pidió en la configuración; distinto de ``nombre`` si este es una reserva.
	pedido: str = ""

	@classmethod
	def disponible(cls) -> tuple[bool, str]:
		"""(se puede usar en este equipo, motivo si no). No abre ningún dispositivo."""
		return True, ""

	@abstractmethod
	def iniciar(self, dispositivo: str | None, opciones: dict) -> None:
		"""Abre la salida de sonido. Lanza :class:`ErrorMotor` si no puede."""

	@abstractmethod
	def cerrar(self) -> None:
		"""Para todo y suelta el dispositivo. Se puede llamar más de una vez."""

	@abstractmethod
	def dispositivos(self) -> list[str]:
		"""Nombres de las salidas que este motor puede abrir."""

	@abstractmethod
	def cargar(self, nombre: str, ruta: Path | None = None, datos: Any = None, frecuencia: int = FRECUENCIA) -> None:
		"""Deja un sonido en memoria con ese nombre, leído de ``ruta`` o dado en ``datos``."""

	@abstractmethod
	def oyente(self, x: float, y: float, z: float, rumbo: float) -> None:
		"""Sitúa y orienta al oyente en el mundo."""

	@abstractmethod
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
		"""Hace sonar ``nombre`` y devuelve su canal (0 si no ha podido sonar)."""

	@abstractmethod
	def actualizar(
		self,
		canal: int,
		*,
		pos: Posicion3 | None = None,
		volumen: float | None = None,
		tono: float | None = None,
		filtro: float | None = None,
	) -> None:
		"""Cambia lo indicado de un sonido en marcha; lo que va a None se queda como está."""

	@abstractmethod
	def parar(self, canal: int, fundido: float = 0.0) -> None:
		"""Detiene un sonido, al momento o apagándolo en ``fundido`` segundos."""

	@abstractmethod
	def parar_todo(self, bus: str | None = None) -> None:
		"""Detiene todo, o solo lo de un bus."""

	@abstractmethod
	def suena(self, canal: int) -> bool:
		"""Si ese canal sigue sonando."""

	@abstractmethod
	def acustica(self, preset: str) -> None:
		"""Cambia la reverberación del lugar (uno de :data:`ACUSTICAS`)."""

	@abstractmethod
	def volumen_bus(self, bus: str, valor: float) -> None:
		"""Volumen de un bus, de 0 a 1."""

	@abstractmethod
	def atenuar_por_voz(self, segundos: float) -> None:
		"""Baja el ambiente y la música durante ese tiempo, porque va a hablar la voz."""

	@abstractmethod
	def pausar(self, si: bool) -> None:
		"""Detiene o reanuda los sonidos del mundo (los de interfaz siguen)."""

	@abstractmethod
	def tic(self, dt: float) -> None:
		"""Una vez por fotograma: fundidos, subidas graduales, limpieza y vigilancia de la salida."""

	# ── Opcionales: cada motor hace lo que puede ──

	def cambiar_dispositivo(self, dispositivo: str | None) -> bool:
		"""Lleva el sonido a otra salida sin cortar lo que suena. False si el motor no sabe o no puede."""
		return False

	def configurar(self, opciones: dict) -> None:  # noqa: B027 - opcional: un motor sin opciones no hace nada
		"""Aplica en caliente opciones cambiadas en las preferencias."""

	def sonidos_cargados(self) -> list[str]:
		"""Nombres de los sonidos que el motor tiene en memoria (para recargarlos al cambiar de paquete)."""
		return []

	def recargar_sonido(self, nombre: str, datos: Any, frecuencia: int = FRECUENCIA, fundido: float = 0.25) -> int:
		"""Sustituye un sonido ya cargado por otro; devuelve cuántos bucles en marcha han pasado al nuevo.

		Un motor que no sepa cambiar un bucle sobre la marcha se limita a cargar el sonido: lo nuevo
		se oirá la próxima vez que se pida.
		"""
		self.cargar(nombre, datos=datos, frecuencia=frecuencia)
		return 0

	def estado(self) -> dict:
		"""Datos para diagnóstico y para la pantalla de preferencias."""
		return {"motor": self.nombre}


class MotorBase(MotorAudio):
	"""Lo que comparten los motores de verdad: sonidos cargados, buses, canales, atenuación y protección.

	Las subclases implementan cómo suena cada canal (``_empezar``, ``_aplicar``, ``_detener``,
	``_sigue``) y la salida; aquí está la contabilidad, igual para todos.
	"""

	FUENTES_MAXIMAS = 48

	def __init__(self) -> None:
		self.opciones: dict = {}
		self.volumenes: dict[str, float] = dict(VOLUMENES_DE_SERIE)
		self.proteccion = Proteccion()
		self.resolver: Callable[[str], tuple[np.ndarray, int] | None] | None = None
		self.preset = "seca"
		self.refuerzo_detras = 1.0
		self.atenuar_voz = True
		self.referencia = DISTANCIA_REFERENCIA
		self.caida = DISTANCIA_CAIDA
		self.maxima = DISTANCIA_MAXIMA
		self.mono = False
		self.pedido = ""  # el motor que se pidió en la configuración (lo pone la fábrica)
		self._sonidos: dict[str, np.ndarray] = {}
		self._faltan: set[str] = set()
		self._canales: dict[int, Canal] = {}
		# Canal que conoce el juego → canal que suena ahora en su lugar (tras recargar un bucle en marcha).
		self._relevos: dict[int, int] = {}
		self._siguiente = 1
		self._oyente: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
		self._reloj = 0.0
		self._voz_hasta = 0.0
		self._atenuacion = 1.0
		self._maestro = 0.0  # ganancia maestra aplicada ahora: arranca en 0 y sube poco a poco
		self._pausado = False
		self._iniciado = False

	# ── Opciones ──

	def _leer_opciones(self, opciones: dict) -> None:
		"""Lo común de ``opciones`` (ver docs/sonido.md). Las claves desconocidas se ignoran."""
		self.opciones = {**self.opciones, **dict(opciones or {})}
		o = self.opciones
		for bus, valor in dict(o.get("volumenes") or {}).items():
			if bus in BUSES:
				self.volumenes[bus] = recortar(_numero(valor, self.volumenes[bus]))
		self.refuerzo_detras = recortar(_numero(o.get("refuerzo_detras", self.refuerzo_detras), 1.0))
		self.atenuar_voz = bool(o.get("atenuar_voz", self.atenuar_voz))
		self.referencia = max(0.1, _numero(o.get("distancia_referencia", self.referencia), DISTANCIA_REFERENCIA))
		self.caida = max(0.0, _numero(o.get("distancia_caida", self.caida), DISTANCIA_CAIDA))
		self.maxima = max(self.referencia, _numero(o.get("distancia_maxima", self.maxima), DISTANCIA_MAXIMA))
		self.mono = bool(o.get("mono", self.mono))
		if "proteccion" in o:
			self.proteccion = Proteccion.de_dict(o.get("proteccion"))

	def configurar(self, opciones: dict) -> None:
		"""Aplica en caliente lo común; las subclases añaden lo suyo."""
		self._leer_opciones(opciones)

	# ── Sonidos ──

	def cargar(self, nombre: str, ruta: Path | None = None, datos: Any = None, frecuencia: int = FRECUENCIA) -> None:
		"""Deja ``nombre`` listo para sonar. Con ``ruta`` se lee el fichero; con ``datos``, se usan tal cual."""
		if datos is None:
			if ruta is None:
				raise ValueError("cargar necesita una ruta o unos datos")
			from app.audio import sintesis

			datos, frecuencia = sintesis.leer_audio(Path(ruta))
		self._sonidos[nombre] = preparar_datos(datos, frecuencia)
		self._faltan.discard(nombre)
		self._sonido_cambiado(nombre)

	def _sonido_cambiado(self, nombre: str) -> None:  # noqa: B027 - gancho opcional
		"""Un sonido se ha cargado o sustituido: el motor tira lo que tuviera preparado con él."""

	def sonidos_cargados(self) -> list[str]:
		"""Nombres de los sonidos que hay en memoria, en el orden en que se cargaron."""
		return list(self._sonidos)

	def recargar_sonido(self, nombre: str, datos: Any, frecuencia: int = FRECUENCIA, fundido: float = 0.25) -> int:
		"""Sustituye ``nombre`` por otras muestras **sin cortar lo que suena**. Devuelve cuántos bucles han pasado al nuevo.

		Es lo que permite cambiar de paquete de sonidos en mitad de una partida:

		- Lo que se pida a partir de ahora suena con el sonido nuevo.
		- Un sonido corto que esté sonando termina con el antiguo (cortarlo se oiría más que dejarlo).
		- Un **bucle** en marcha (un ambiente, el frigorífico de la cocina) no puede seguir con el
		  antiguo para siempre: se pone a sonar un canal nuevo con el sonido nuevo, en el mismo sitio y
		  con el mismo volumen, tono y filtro, que entra desde el silencio, mientras el antiguo se apaga
		  en ``fundido`` segundos. El juego sigue usando el número de canal que ya tenía: aquí se
		  recuerda que ese número lo «releva» el canal nuevo.

		Si no queda ninguna fuente libre para solapar los dos, se corta el antiguo y se arranca el
		nuevo (suena un instante de silencio, no un error).
		"""
		self.cargar(nombre, datos=datos, frecuencia=frecuencia)
		if not self._iniciado:
			return 0
		pasados = 0
		for viejo in list(self._canales.values()):
			if viejo.nombre != nombre or not viejo.bucle or viejo.parando:
				continue
			nuevo = Canal(
				id=self._siguiente,
				nombre=viejo.nombre,
				bus=viejo.bus,
				pos=viejo.pos,
				relativo=viejo.relativo,
				volumen=viejo.volumen,
				tono=viejo.tono,
				bucle=True,
				filtro=viejo.filtro,
				eco=viejo.eco,
				prioridad=viejo.prioridad,
				ganancia=0.0,
				pausado=viejo.pausado,
			)
			empezado = self._empezar(nuevo)
			if not empezado:
				# Sin sitio para los dos a la vez: se suelta el antiguo y se intenta de nuevo.
				self._soltar_sin_relevo(viejo)
				empezado = self._empezar(nuevo)
				if not empezado:
					log.warning("No se pudo volver a poner en marcha el bucle %s tras cambiar su sonido.", nombre)
					self._olvidar_relevos(viejo.id)
					continue
			else:
				if fundido > 0.0:
					viejo.fundido = float(fundido)
				else:
					self._soltar_sin_relevo(viejo)
			self._siguiente += 1
			self._canales[nuevo.id] = nuevo
			# Quien tenía el número del antiguo (o el de uno anterior a él) pasa a manejar el nuevo.
			for publico, real in list(self._relevos.items()):
				if real == viejo.id:
					self._relevos[publico] = nuevo.id
			self._relevos[viejo.id] = nuevo.id
			pasados += 1
		return pasados

	def _canal(self, canal: int) -> Canal | None:
		"""El canal que suena ahora para ese número (el propio, o el que lo relevó al recargar su sonido)."""
		return self._canales.get(self._relevos.get(canal, canal))

	def _soltar_sin_relevo(self, canal: Canal) -> None:
		"""Corta un canal que está siendo relevado, conservando el apunte de su relevo."""
		self._canales.pop(canal.id, None)
		self._detener(canal)

	def _datos(self, nombre: str) -> np.ndarray | None:
		"""Las muestras de ``nombre``; si no está cargado se le pide al banco. None si no hay manera."""
		datos = self._sonidos.get(nombre)
		if datos is not None:
			return datos
		if nombre in self._faltan:
			return None
		if self.resolver is not None:
			try:
				resuelto = self.resolver(nombre)
			except OSError, ValueError, KeyError:
				log.warning("No se pudo resolver el sonido %s.", nombre, exc_info=True)
				resuelto = None
			if resuelto is not None:
				self.cargar(nombre, datos=resuelto[0], frecuencia=resuelto[1])
				return self._sonidos[nombre]
		self._faltan.add(nombre)
		log.warning("Falta el sonido %s.", nombre)
		return None

	def duracion(self, nombre: str) -> float:
		"""Segundos que dura un sonido (0 si no existe)."""
		datos = self._datos(nombre)
		return 0.0 if datos is None else len(datos) / FRECUENCIA

	# ── Oyente, buses, voz ──

	def oyente(self, x: float, y: float, z: float, rumbo: float) -> None:
		"""Guarda dónde está y hacia dónde mira el oyente; la subclase lo lleva a su biblioteca."""
		self._oyente = (float(x), float(y), float(z), float(rumbo) % 360.0)
		self._oyente_cambiado()

	def _oyente_cambiado(self) -> None:  # noqa: B027 - gancho opcional
		"""El oyente se ha movido."""

	def volumen_bus(self, bus: str, valor: float) -> None:
		"""Volumen de un bus (0 a 1). Las subidas se oyen poco a poco: las suaviza ``tic``."""
		if bus not in BUSES:
			log.warning("Bus de sonido desconocido: %s.", bus)
			return
		self.volumenes[bus] = recortar(valor)

	def atenuar_por_voz(self, segundos: float) -> None:
		"""La voz va a hablar ``segundos``: el ambiente y la música bajan y luego vuelven despacio."""
		if segundos > 0:
			self._voz_hasta = max(self._voz_hasta, self._reloj + min(float(segundos), 30.0))

	def _ganancia_canal(self, canal: Canal) -> float:
		"""Ganancia de un canal antes de la distancia: volumen pedido, bus, atenuación por voz y techo."""
		g = canal.volumen * self.volumenes.get(canal.bus, 1.0) * canal.nivel
		if canal.bus in BUSES_ATENUADOS:
			g *= self._atenuacion
		return self.proteccion.limitar_fuente(g)

	def _prioridad(self, bus: str, bucle: bool, volumen: float, prioridad: int | None) -> int:
		"""Importancia de un sonido nuevo: la pedida, o la de su bus (los bucles valen algo más)."""
		if prioridad is not None:
			return int(prioridad)
		return PRIORIDAD_BUS.get(bus, 40) + (5 if bucle else 0) + int(4 * recortar(volumen))

	# ── Canales ──

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
		"""Crea el canal y se lo da a la subclase. Devuelve 0 si el sonido no existe o no hay sitio."""
		if not self._iniciado:
			return 0
		if self._datos(nombre) is None:
			return 0
		if bus not in BUSES or bus == "maestro":
			log.warning("Bus de sonido desconocido: %s; se usa «efectos».", bus)
			bus = "efectos"
		canal = Canal(
			id=self._siguiente,
			nombre=nombre,
			bus=bus,
			pos=None if pos is None else (float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) > 2 else 0.0),
			relativo=None if relativo is None or pos is not None else (float(relativo[0]), float(relativo[1])),
			volumen=max(0.0, float(volumen)),
			tono=recortar(tono, 0.25, 4.0),
			bucle=bool(bucle),
			filtro=recortar(filtro),
			eco=bool(eco),
			prioridad=self._prioridad(bus, bucle, volumen, prioridad),
		)
		if len(self._canales) >= self.FUENTES_MAXIMAS and not self._hacer_sitio(canal.prioridad):
			log.debug("Sin fuentes libres para %s (prioridad %s).", nombre, canal.prioridad)
			return 0
		# Los bucles entran desde el silencio (subida gradual); un golpe conserva su ataque.
		canal.ganancia = 0.0 if canal.bucle else self._ganancia_canal(canal)
		canal.pausado = self._pausado and bus not in BUSES_SIN_PAUSA
		if not self._empezar(canal):
			return 0
		self._siguiente += 1
		self._canales[canal.id] = canal
		return canal.id

	def _hacer_sitio(self, prioridad: int) -> bool:
		"""Roba el canal menos importante (y, entre iguales, el más viejo) si lo es menos que el nuevo."""
		if not self._canales:
			return True
		victima = min(self._canales.values(), key=lambda c: (c.prioridad, -c.edad))
		if victima.prioridad > prioridad:
			return False
		log.debug("Se roba la fuente de %s (prioridad %s).", victima.nombre, victima.prioridad)
		self._soltar(victima)
		return True

	def actualizar(
		self,
		canal: int,
		*,
		pos: Posicion3 | None = None,
		volumen: float | None = None,
		tono: float | None = None,
		filtro: float | None = None,
	) -> None:
		"""Cambia la posición, el volumen, el tono o el filtro de un canal en marcha."""
		c = self._canal(canal)
		if c is None:
			return
		if pos is not None:
			c.pos = (float(pos[0]), float(pos[1]), float(pos[2]) if len(pos) > 2 else 0.0)
			c.relativo = None
		if volumen is not None:
			c.volumen = max(0.0, float(volumen))
		if tono is not None:
			c.tono = recortar(tono, 0.25, 4.0)
		if filtro is not None:
			c.filtro = recortar(filtro)

	def parar(self, canal: int, fundido: float = 0.0) -> None:
		"""Detiene un canal; con ``fundido`` se apaga en esos segundos (lo lleva ``tic``)."""
		c = self._canal(canal)
		if c is None:
			return
		if fundido <= 0.0:
			self._soltar(c)
		elif not c.parando:
			c.fundido = float(fundido)

	def parar_todo(self, bus: str | None = None) -> None:
		"""Detiene al momento todos los canales, o los de un bus."""
		for c in list(self._canales.values()):
			if bus is None or c.bus == bus:
				self._soltar(c)

	def suena(self, canal: int) -> bool:
		"""Si el canal existe y no ha terminado."""
		c = self._canal(canal)
		return c is not None and self._sigue(c)

	def canales_activos(self) -> list[Canal]:
		"""Copia de los canales en marcha (para diagnóstico y pruebas)."""
		return list(self._canales.values())

	def _soltar(self, canal: Canal) -> None:
		self._canales.pop(canal.id, None)
		self._detener(canal)
		self._olvidar_relevos(canal.id)

	def _olvidar_relevos(self, real: int) -> None:
		"""Ese canal ya no suena: los números que apuntaban a él dejan de valer."""
		if self._relevos:
			self._relevos = {publico: destino for publico, destino in self._relevos.items() if destino != real}

	def pausar(self, si: bool) -> None:
		"""Detiene o reanuda los sonidos del mundo; interfaz y voz grabada no se pausan."""
		si = bool(si)
		if si == self._pausado:
			return
		self._pausado = si
		for c in self._canales.values():
			if c.bus not in BUSES_SIN_PAUSA:
				c.pausado = si
				self._pausar_canal(c, si)

	def acustica(self, preset: str) -> None:
		"""Recuerda el preset; los motores con reverberación lo aplican."""
		if preset not in ACUSTICAS:
			log.warning("Acústica desconocida: %s; se usa «seca».", preset)
			preset = "seca"
		if preset != self.preset:
			self.preset = preset
			self._acustica_cambiada()

	def _acustica_cambiada(self) -> None:  # noqa: B027 - gancho opcional
		"""Ha cambiado el preset de reverberación."""

	# ── Por fotograma ──

	def tic(self, dt: float) -> None:
		"""Avanza relojes, atenuación por voz, ganancia maestra y fundidos, y retira lo terminado."""
		dt = recortar(dt, 0.0, 0.25)
		self._reloj += dt
		hablando = self.atenuar_voz and self._reloj < self._voz_hasta
		objetivo = ATENUACION_VOZ if hablando else 1.0
		# Baja deprisa (en unos 0,15 s) y vuelve despacio (alrededor de 1 s): así la voz no pisa nada.
		ritmo = 12.0 if objetivo < self._atenuacion else 2.0
		self._atenuacion += (objetivo - self._atenuacion) * min(1.0, ritmo * dt)
		self._maestro = self.proteccion.subir(self._maestro, self.proteccion.limitar_maestro(self.volumenes["maestro"]), dt)
		for c in list(self._canales.values()):
			if not c.pausado:
				c.edad += dt
			if c.parando:
				c.nivel -= dt / c.fundido
				if c.nivel <= 0.0:
					self._soltar(c)
					continue
			if not self._sigue(c):
				self._soltar(c)
				continue
			objetivo_canal = self._ganancia_canal(c)
			if objetivo_canal > c.ganancia:
				c.ganancia = self.proteccion.subir_fuente(c.ganancia, objetivo_canal, dt)
			else:
				c.ganancia = objetivo_canal
			self._aplicar(c)

	# ── Lo que implementa cada motor ──

	@abstractmethod
	def _empezar(self, canal: Canal) -> bool:
		"""Pone a sonar el canal. False si no ha podido."""

	@abstractmethod
	def _aplicar(self, canal: Canal) -> None:
		"""Lleva al sonido la posición, la ganancia (``canal.ganancia``), el tono y el filtro actuales."""

	@abstractmethod
	def _detener(self, canal: Canal) -> None:
		"""Corta el sonido y libera lo que usara."""

	@abstractmethod
	def _sigue(self, canal: Canal) -> bool:
		"""Si el sonido aún no ha llegado al final."""

	def _pausar_canal(self, canal: Canal, si: bool) -> None:  # noqa: B027 - gancho opcional
		"""Pausa o reanuda un canal."""

	def estado(self) -> dict:
		"""Diagnóstico común."""
		return {
			"motor": self.nombre,
			"pedido": self.pedido or self.nombre,
			"canales": len(self._canales),
			"sonidos": len(self._sonidos),
			"acustica": self.preset,
			"pausado": self._pausado,
		}


def _numero(valor: Any, defecto: float) -> float:
	"""``valor`` como número; el de defecto si la configuración trae otra cosa."""
	try:
		return float(valor)
	except TypeError, ValueError:
		log.warning("Opción de sonido no numérica: %r; se usa %s.", valor, defecto)
		return defecto
