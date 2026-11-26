"""Presentador: convierte lo que decide el motor del juego en sonido, voz y vibración.

El motor del juego (``app.motor``) no suena ni habla: devuelve eventos y dice dónde está el oyente y
qué fuentes continuas se oyen. El presentador es el único sitio donde eso se convierte en llamadas
al motor de sonido, a la voz y a la vibración. Una vez por fotograma::

    eventos = sesion.avanzar(dt)
    presentador.aplicar(eventos, sesion, dt)

``aplicar`` hace, en este orden: sitúa al oyente (sumando el giro de la cabeza si se sigue con
OpenTrack), traduce los eventos, sincroniza las fuentes continuas (crea las nuevas, mueve y ajusta
las que siguen, apaga con un fundido las que ya no se oyen) y llama a ``tic`` del motor de sonido, de
la voz y de la vibración. No hay que llamar a esos ``tic`` por otro lado.

Para no depender de un módulo concreto, los eventos se reconocen por el nombre de su clase
(``EvSonido``, ``EvVoz``, ``EvVibrar``, ``EvAcustica``); un objeto de otra clase que no empiece por
``Ev`` también vale si trae un atributo ``tipo`` equivalente (``sonido``, ``voz``, ``vibrar``,
``acustica``). Los demás (``EvRegistro``, ``EvFin``) no son cosa del sonido y se ignoran.

**Cambio de paquete de sonidos en caliente.** Si se le da el banco de sonidos, el presentador se
entera de cuándo cambian los sonidos (otro paquete, el igualado, el volumen de un sonido) y, en el
siguiente ``aplicar``, vuelve a cargar en el motor lo que haya cambiado. Los bucles que estén
sonando (ambientes, fuentes continuas) pasan al sonido nuevo con un fundido corto y sin moverse de
su sitio. Se hace en ``aplicar`` y no en el aviso porque el aviso llega en el hilo de quien cambió
la preferencia, y el motor de sonido solo se toca desde el hilo del juego.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any

from app.audio.base import BUSES, MotorAudio, SesionP

log = logging.getLogger(__name__)

_TIPOS = {"EvSonido": "sonido", "EvVoz": "voz", "EvVibrar": "vibrar", "EvAcustica": "acustica"}
# Buses cuyos sonidos no llevan el eco del lugar: no están en el mundo.
BUSES_SIN_ECO = ("interfaz", "voz", "musica")
FUNDIDO_FUENTE = 0.3  # segundos que tarda en apagarse una fuente continua que deja de oírse
FUNDIDO_CAMBIO = 0.25  # segundos del fundido con que un bucle pasa al sonido de otro paquete
BUS_FUENTES = "ambiente"
DT_MAXIMO = 0.25


@dataclass
class _Continua:
	"""Una fuente continua del juego y el canal del motor de sonido que la hace sonar."""

	canal: int
	sonido: str
	bucle: bool


def tipo_evento(evento: Any) -> str:
	"""«sonido», «voz», «vibrar», «acustica» o «» si el evento no es para la capa de sonido."""
	clase = type(evento).__name__
	if clase in _TIPOS:
		return _TIPOS[clase]
	if clase.startswith("Ev"):
		# Otro evento del motor (EvRegistro tiene su propio campo «tipo»: choque, premio...): no es para el sonido.
		return ""
	tipo = getattr(evento, "tipo", None)
	return tipo if isinstance(tipo, str) and tipo in _TIPOS.values() else ""


class Presentador:
	"""Aplica los eventos del juego al motor de sonido, la voz y la vibración."""

	def __init__(self, motor: MotorAudio, voz: Any = None, haptica: Any = None, cabeza: Any = None, banco: Any = None) -> None:
		"""``voz`` y ``haptica`` pueden faltar (None); ``cabeza`` es el seguimiento de OpenTrack, opcional.

		``banco`` (un :class:`app.audio.banco.Banco`) es opcional: con él, cambiar de paquete de sonidos
		se oye al momento, también en mitad de una partida.
		"""
		self.motor = motor
		self.voz = voz
		self.haptica = haptica
		self.cabeza = cabeza
		self.banco: Any = None
		self._continuas: dict[str, _Continua] = {}
		self._ultimo = time.monotonic()
		self._recarga_pendiente = False
		self._cancelar_banco: Any = None
		if banco is not None:
			self.conectar_banco(banco)

	# ── Paquetes de sonidos ──

	def conectar_banco(self, banco: Any) -> None:
		"""Se suscribe a los cambios del banco de sonidos (o deja de estarlo, con None)."""
		if self._cancelar_banco is not None:
			self._cancelar_banco()
			self._cancelar_banco = None
		self.banco = banco
		if banco is not None:
			self._cancelar_banco = banco.suscribir(self._sonidos_cambiados)

	def _sonidos_cambiados(self, _motivo: str) -> None:
		"""Aviso del banco, quizá desde otro hilo: solo se apunta; la recarga la hace ``aplicar``."""
		self._recarga_pendiente = True

	def recargar_sonidos(self, fundido: float = FUNDIDO_CAMBIO) -> int:
		"""Vuelve a cargar en el motor los sonidos que han cambiado. Devuelve cuántos.

		``aplicar`` lo llama solo cuando el banco avisa; se puede llamar a mano (desde el hilo del
		juego) para que el cambio se oiga ya, por ejemplo en un menú que no llama a ``aplicar``.
		"""
		self._recarga_pendiente = False
		if self.banco is None:
			return 0
		return int(self.banco.recargar_en(self.motor, fundido))

	# ── Por fotograma ──

	def aplicar(self, eventos: Iterable[Any] | None, sesion: SesionP | None = None, dt: float | None = None) -> None:
		"""Lleva al sonido, la voz y la vibración lo ocurrido en este fotograma. Ver el docstring del módulo.

		``dt`` son los segundos del fotograma; si no se da, se mide el tiempo desde la llamada anterior.
		"""
		ahora = time.monotonic()
		if dt is None:
			dt = ahora - self._ultimo
		self._ultimo = ahora
		dt = max(0.0, min(DT_MAXIMO, float(dt)))
		if self._recarga_pendiente:
			self.recargar_sonidos()
		if sesion is not None:
			self._situar_oyente(sesion)
		for evento in eventos or ():
			try:
				self.evento(evento)
			except AttributeError, TypeError, ValueError:
				log.exception("No se pudo presentar el evento %r.", evento)
		if sesion is not None:
			self._sincronizar_fuentes(sesion)
		self.motor.tic(dt)
		if self.voz is not None:
			self.voz.tic()
		if self.haptica is not None:
			self.haptica.tic(dt)

	def _situar_oyente(self, sesion: SesionP) -> None:
		x, y, z, rumbo = sesion.oyente()
		if self.cabeza is not None:
			# Con la cabeza girada, los sonidos se quedan en su sitio: se oye como si se girara el cuerpo.
			rumbo += self.cabeza.giro()
		self.motor.oyente(x, y, z, rumbo % 360.0)

	# ── Eventos ──

	def evento(self, evento: Any) -> int:
		"""Presenta un evento suelto. Devuelve el canal si era un sonido (0 en otro caso)."""
		tipo = tipo_evento(evento)
		if tipo == "sonido":
			return self._sonido(evento)
		if tipo == "voz":
			self.decir(evento.texto, bool(getattr(evento, "interrumpir", False)), str(getattr(evento, "canal", "juego")))
		elif tipo == "vibrar":
			self._vibrar(evento)
		elif tipo == "acustica":
			self.motor.acustica(str(evento.preset))
		return 0

	def _sonido(self, evento: Any) -> int:
		bus = str(getattr(evento, "bus", "efectos") or "efectos")
		if bus not in BUSES or bus == "maestro":
			log.warning("Evento de sonido con un bus desconocido (%s): se usa «efectos».", bus)
			bus = "efectos"
		pos = getattr(evento, "pos", None)
		relativo = getattr(evento, "relativo", None) if pos is None else None
		return self.motor.reproducir(
			str(evento.nombre),
			pos=pos,
			relativo=relativo,
			volumen=float(getattr(evento, "volumen", 1.0)),
			tono=float(getattr(evento, "tono", 1.0)),
			bus=bus,
			bucle=bool(getattr(evento, "bucle", False)),
			filtro=float(getattr(evento, "filtro", 0.0)),
			eco=bool(getattr(evento, "eco", bus not in BUSES_SIN_ECO)),
		)

	def decir(self, texto: str, interrumpir: bool = False, canal: str = "juego") -> float:
		"""Dice un texto y baja el ambiente y la música lo que vaya a durar. Devuelve esa duración estimada."""
		if self.voz is None or not texto:
			return 0.0
		duracion = self.voz.decir(texto, interrumpir, canal)
		try:
			segundos = float(duracion or 0.0)
		except TypeError, ValueError:
			segundos = 0.0
		if segundos > 0.0:
			self.motor.atenuar_por_voz(segundos)
		return segundos

	def sonido(self, nombre: str, bus: str = "interfaz", volumen: float = 1.0, **opciones: Any) -> int:
		"""Hace sonar algo directamente (menús del reproductor): por defecto, sin posición y por el bus de interfaz."""
		opciones.setdefault("eco", bus not in BUSES_SIN_ECO)
		return self.motor.reproducir(nombre, bus=bus, volumen=volumen, **opciones)

	def _vibrar(self, evento: Any) -> None:
		if self.haptica is None:
			return
		patron = getattr(evento, "patron", None)
		if patron:
			# Extensión: un evento puede nombrar un patrón del vocabulario en vez de dar los motores.
			self.haptica.patron(str(patron), float(getattr(evento, "intensidad", 1.0)))
			return
		self.haptica.vibrar(float(evento.grave), float(evento.agudo), int(evento.ms))

	# ── Fuentes continuas ──

	def _sincronizar_fuentes(self, sesion: SesionP) -> None:
		"""Deja sonando exactamente las fuentes que la sesión dice que se oyen, con su posición y su filtro."""
		vistas: set[str] = set()
		for fuente in sesion.fuentes():
			identificador = str(fuente.id)
			vistas.add(identificador)
			sonido = str(fuente.sonido)
			bucle = bool(getattr(fuente, "bucle", True))
			volumen = float(getattr(fuente, "volumen", 1.0))
			tono = float(getattr(fuente, "tono", 1.0))
			filtro = float(getattr(fuente, "filtro", 0.0))
			actual = self._continuas.get(identificador)
			if actual is not None and actual.sonido != sonido:
				# La misma fuente ha cambiado de sonido (un semáforo que pasa a verde): se sustituye.
				self.motor.parar(actual.canal, FUNDIDO_FUENTE / 2)
				actual = None
			if actual is not None and actual.bucle and not self.motor.suena(actual.canal):
				# Un bucle que ya no suena es que le han robado la fuente: se vuelve a pedir.
				actual = None
			if actual is None:
				canal = self.motor.reproducir(
					sonido,
					pos=fuente.pos,
					volumen=volumen,
					tono=tono,
					bus=str(getattr(fuente, "bus", BUS_FUENTES)),
					bucle=bucle,
					filtro=filtro,
					eco=bool(getattr(fuente, "eco", True)),
				)
				self._continuas[identificador] = _Continua(canal, sonido, bucle)
			elif actual.canal:
				self.motor.actualizar(actual.canal, pos=fuente.pos, volumen=volumen, tono=tono, filtro=filtro)
		for identificador in [i for i in self._continuas if i not in vistas]:
			self.motor.parar(self._continuas.pop(identificador).canal, FUNDIDO_FUENTE)

	def fuentes_sonando(self) -> dict[str, int]:
		"""Identificador de fuente → canal del motor de sonido (para diagnóstico y pruebas)."""
		return {identificador: continua.canal for identificador, continua in self._continuas.items()}

	def detener_fuentes(self, fundido: float = FUNDIDO_FUENTE) -> None:
		"""Apaga todas las fuentes continuas (al salir de un entorno o cambiar de planta de golpe)."""
		for continua in self._continuas.values():
			self.motor.parar(continua.canal, fundido)
		self._continuas.clear()

	def pausar(self, si: bool) -> None:
		"""Pausa o reanuda los sonidos del mundo; al pausar se calla también la vibración pendiente."""
		self.motor.pausar(si)
		if si and self.haptica is not None:
			self.haptica.parar()

	def cerrar(self) -> None:
		"""Deja todo en silencio. No cierra el motor ni la voz: son de quien los creó."""
		self.conectar_banco(None)
		self.detener_fuentes(0.0)
		if self.haptica is not None:
			self.haptica.parar()
