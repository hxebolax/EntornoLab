"""La voz del reproductor: lector de pantalla activo o SAPI, braille, canales e historial repasable.

Qué resuelve y por qué está hecho así:

- **Salida** (``salida``), cuatro posibilidades:

  - ``automatica`` (de serie): el lector de pantalla que esté abierto (NVDA, JAWS…) y, si no hay ninguno,
    la voz de Windows. Se pregunta cuál hay cada vez que se habla y, además, cada dos segundos (``tic``),
    porque el alumno o el profesional pueden abrirlo o cerrarlo con el juego en marcha.
  - ``lector``: solo el lector de pantalla. Si no hay ninguno abierto no se habla, y nunca se cae a SAPI
    (tampoco al redetectar): quien elige esto no quiere oír la voz de Windows.
  - ``sapi``: siempre la voz de Windows, con voz, velocidad y volumen propios.
  - ``ninguna``: no se habla nunca. Para quien lee en braille o en la pantalla, o no quiere voz. El
    historial se sigue llenando y, si hay un lector de pantalla abierto, los mensajes siguen llegando a
    la línea braille (solo el braille: al lector no se le pide que hable ni que se calle).

  Sin voz el reproductor sigue escribiendo abajo, en la pantalla, el último mensaje (``ultimo``).
- **Braille**: ``temporal`` (un mensaje de braille del lector, que lo quita a los pocos segundos), ``fijo``
  (solo NVDA: el mensaje se queda en la línea; ver ``linea_braille``) o ``nada``. Se habla y se manda al
  braille por separado: ``Auto.output()`` de accessible_output2 solo habla.
- **Canales** (``juego``, ``ayuda``, ``aviso``, ``profesional``): cada uno se puede desactivar. Lo que llega
  por un canal desactivado no se dice, pero SÍ queda en el historial: quien lo quiera lo repasa, y el
  informe de la sesión no pierde nada.
- **Historial repasable**: ``anterior``, ``siguiente`` y ``repetir``. Lo que se dice al repasar no entra en
  el historial, y mientras se repasa los mensajes nuevos no mueven el cursor (``REPASO_PAUSA``): si no, con
  el juego hablando, «anterior» se quedaría siempre en el mismo mensaje.
- **No interrumpir** (``nunca_interrumpir``): para línea braille o sordoceguera, ningún mensaje corta al anterior.
- **Duración estimada**: ``decir`` devuelve los segundos que tardará en decirse, para que el sonido baje el
  ambiente y la música mientras tanto. Un lector de pantalla no avisa de cuándo acaba; se estima por la longitud.

``APP_SIN_VOZ=1`` desactiva la voz (pruebas automáticas). ``VozFalsa`` tiene la misma interfaz y solo apunta.
"""

from __future__ import annotations

import logging
import os
import time
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.audio.linea_braille import LineaVentana
from app.core.i18n import _

# Las salidas y cómo se distingue un lector de pantalla de la voz de Windows son las mismas que en el Estudio.
from app.core.voz import SALIDA_DE_SERIE, SALIDAS, primer_lector

log = logging.getLogger(__name__)

CANALES: tuple[str, ...] = ("juego", "ayuda", "aviso", "profesional")
MODOS_BRAILLE: tuple[str, ...] = ("temporal", "fijo", "nada")
# Salidas que usan ``Auto`` de accessible_output2 (para buscar el lector activo); «sapi» abre SAPI5 directo.
_SALIDAS_CON_LECTOR: frozenset[str] = frozenset({"automatica", "lector", "ninguna"})
# Canal con el que VozFalsa apunta lo que se dice al repasar el historial (no es un canal configurable).
CANAL_REPASO = "historial"
CADA_CUANTO_LECTOR = 2.0  # segundos entre dos comprobaciones de qué lector hay
REPASO_PAUSA = 20.0  # segundos tras repasar durante los que los mensajes nuevos no mueven el cursor
DURACION_MAXIMA = 9.0  # no se atenúa el ambiente más de esto por un solo mensaje
SAFT_44KHZ_16BIT_MONO = 34  # SpeechAudioFormatType de SAPI: el formato de los sonidos que se posicionan
SSFM_CREAR_PARA_ESCRIBIR = 3

OPCIONES_DE_SERIE: dict[str, Any] = {
	"activa": True,
	"salida": SALIDA_DE_SERIE,
	"sapi_voz": "",
	"sapi_velocidad": 0,
	"sapi_volumen": 100,
	"braille": "temporal",
	"nunca_interrumpir": False,
	"canales": {canal: True for canal in CANALES},
	"historial_max": 300,
}


def estimar_duracion(texto: str, velocidad: int = 0) -> float:
	"""Segundos que tardará en decirse ``texto``, a ojo: unas quince letras por segundo más el arranque.

	``velocidad`` es la de SAPI (-10 a 10; cada diez puntos, el triple o un tercio). Con un lector de
	pantalla no se conoce su velocidad y se deja en 0. Nunca más de ``DURACION_MAXIMA``: es preferible
	que el ambiente vuelva pronto a que se quede bajado por un mensaje largo.
	"""
	texto = (texto or "").strip()
	if not texto:
		return 0.0
	factor = 3.0 ** (max(-10, min(10, int(velocidad))) / 10.0)
	return min(DURACION_MAXIMA, 0.7 + len(texto) / 15.0 / factor)


def _entero(valor: object, minimo: int, maximo: int, de_serie: int) -> int:
	"""``valor`` como entero dentro de sus límites; el de serie si no es un número."""
	try:
		return max(minimo, min(maximo, int(valor)))  # type: ignore[call-overload]
	except TypeError, ValueError:
		return de_serie


class _VozBase:
	"""Lo común a la voz real y a la falsa: canales, historial, repaso y gancho ``al_hablar``."""

	def __init__(self, opciones: dict | None = None) -> None:
		self.opciones: dict[str, Any] = {k: (dict(v) if isinstance(v, dict) else v) for k, v in OPCIONES_DE_SERIE.items()}
		self.canales: dict[str, bool] = dict(self.opciones["canales"])
		self.nunca_interrumpir = False
		self.braille = "temporal"
		self.nombre = "ninguna"
		# Gancho opcional (texto, duración): la supervisión lo usa para enviar al Estudio lo que oye el alumno.
		self.al_hablar: Callable[[str, float], None] | None = None
		self.historial: deque[str] = deque(maxlen=int(OPCIONES_DE_SERIE["historial_max"]))
		self.historial_canales: deque[str] = deque(maxlen=self.historial.maxlen)
		self._cursor = 0
		self._repaso_t = -1e9
		self._reloj: Callable[[], float] = time.monotonic
		self._mezclar(opciones)

	# ── Opciones ─────────────────────────────────────────────────────────────

	def _mezclar(self, opciones: dict | None) -> None:
		"""Mezcla ``opciones`` con las vigentes, saneando tipos y rangos (una configuración antigua o rota no rompe la voz)."""
		o = self.opciones
		for clave, valor in (opciones or {}).items():
			if clave == "canales" and isinstance(valor, dict):
				for canal, si in valor.items():
					self.canales[str(canal)] = bool(si)
			elif clave in o:
				o[clave] = valor
			else:
				log.debug("Opción de voz desconocida: %s", clave)
		o["activa"] = bool(o["activa"])
		o["salida"] = o["salida"] if o["salida"] in SALIDAS else SALIDA_DE_SERIE
		o["sapi_voz"] = str(o["sapi_voz"] or "")
		o["sapi_velocidad"] = _entero(o["sapi_velocidad"], -10, 10, 0)
		o["sapi_volumen"] = _entero(o["sapi_volumen"], 0, 100, 100)
		o["braille"] = o["braille"] if o["braille"] in MODOS_BRAILLE else "temporal"
		o["historial_max"] = _entero(o["historial_max"], 10, 5000, 300)
		o["canales"] = dict(self.canales)
		self.nunca_interrumpir = bool(o["nunca_interrumpir"])
		self.braille = o["braille"]
		if self.historial.maxlen != o["historial_max"]:
			self.historial = deque(self.historial, maxlen=o["historial_max"])
			self.historial_canales = deque(self.historial_canales, maxlen=o["historial_max"])
			self._cursor = max(0, min(self._cursor, len(self.historial) - 1))

	def configurar(self, opciones: dict) -> None:
		"""Aplica opciones en caliente (las mismas claves que el constructor)."""
		self._mezclar(opciones)

	@property
	def salida(self) -> str:
		"""La salida elegida: ``automatica``, ``lector``, ``sapi`` o ``ninguna``."""
		return str(self.opciones["salida"])

	def activar_canal(self, canal: str, si: bool) -> None:
		"""Activa o desactiva un canal. Lo que llegue por uno desactivado no se dice, pero queda en el historial."""
		self.canales[canal] = bool(si)
		self.opciones["canales"] = dict(self.canales)

	def _velocidad(self) -> int:
		"""Velocidad de la voz si se conoce (SAPI directo); 0 con lector de pantalla."""
		return 0

	# ── Hablar ───────────────────────────────────────────────────────────────

	def decir(self, texto: str, interrumpir: bool = False, canal: str = "juego") -> float:
		"""Dice ``texto`` por ``canal``. Devuelve la duración estimada en segundos, o 0.0 si no se dice.

		No se dice (pero se guarda en el historial) si el canal está desactivado o la voz está inactiva.
		"""
		texto = str(texto or "").strip()
		if not texto:
			return 0.0
		if self.nunca_interrumpir:
			interrumpir = False
		self._guardar(texto, canal)
		log.debug("Voz (%s): %s", canal, texto)
		if not self.canales.get(canal, True):
			return 0.0
		return self._emitir(texto, interrumpir, canal)

	def _emitir(self, texto: str, interrumpir: bool, canal: str) -> float:
		"""Habla de verdad (sin tocar el historial), avisa al gancho y devuelve la duración estimada."""
		if not self._hablar(texto, interrumpir, canal):
			return 0.0
		duracion = estimar_duracion(texto, self._velocidad())
		if self.al_hablar is not None:
			try:
				self.al_hablar(texto, duracion)
			except Exception:  # noqa: BLE001 - un fallo de quien escucha (la red de supervisión) no debe callar la voz
				log.warning("Falló el gancho al_hablar de la voz.", exc_info=True)
		return duracion

	def _hablar(self, texto: str, interrumpir: bool, canal: str) -> bool:
		"""Lo implementa cada voz: devuelve si se ha dicho."""
		raise NotImplementedError

	def callar(self) -> None:
		"""Corta lo que se esté diciendo."""

	def tic(self) -> None:
		"""Una vez por fotograma, desde el hilo principal."""

	def cerrar(self) -> None:
		"""Libera la salida de voz."""

	# ── Historial ────────────────────────────────────────────────────────────

	@property
	def ultimo(self) -> str:
		"""El último mensaje del historial («» si no hay)."""
		return self.historial[-1] if self.historial else ""

	def repasando(self) -> bool:
		"""Si se ha repasado el historial hace poco: entonces los mensajes nuevos no mueven el cursor."""
		return self._reloj() - self._repaso_t < REPASO_PAUSA

	def _guardar(self, texto: str, canal: str) -> None:
		al_final = self._cursor >= len(self.historial) - 1
		lleno = len(self.historial) == self.historial.maxlen
		self.historial.append(texto)
		self.historial_canales.append(canal)
		if al_final or not self.repasando():
			self._cursor = len(self.historial) - 1
		elif lleno:
			self._cursor = max(0, self._cursor - 1)  # el más antiguo se ha ido: el suyo está un puesto antes

	def _marcar_repaso(self) -> None:
		"""Al llegar al último mensaje se deja de repasar: los nuevos vuelven a llevar al final."""
		self._repaso_t = -1e9 if self._cursor >= len(self.historial) - 1 else self._reloj()

	def _repasar(self, delta: int) -> float:
		if not self.historial:
			return self._emitir(_("No hay mensajes."), True, CANAL_REPASO)
		nuevo = self._cursor + delta
		self._cursor = max(0, min(len(self.historial) - 1, nuevo))
		self._marcar_repaso()
		# En el borde se dice: así se sabe que la tecla ha llegado al final y no que no responde.
		borde = ""
		if nuevo < 0:
			borde = _("Primero.") + " "
		elif nuevo > self._cursor:
			borde = _("Último.") + " "
		return self._emitir(borde + self.historial[self._cursor], True, CANAL_REPASO)

	def repetir(self) -> float:
		"""Vuelve a decir el último mensaje (y deja el repaso en él). No lo añade otra vez al historial."""
		if not self.historial:
			return self._emitir(_("No hay mensajes."), True, CANAL_REPASO)
		self._cursor = len(self.historial) - 1
		self._marcar_repaso()
		return self._emitir(self.historial[self._cursor], True, CANAL_REPASO)

	def anterior(self) -> float:
		"""Dice el mensaje anterior del historial; en el primero, avisa con «Primero.»."""
		return self._repasar(-1)

	def siguiente(self) -> float:
		"""Dice el mensaje siguiente del historial; en el último, avisa con «Último.»."""
		return self._repasar(1)


class Voz(_VozBase):
	"""La voz real: lector de pantalla activo (con braille) o SAPI directo."""

	def __init__(self, opciones: dict | None = None, *, salida: object | None = None) -> None:
		"""``salida`` permite inyectar la salida (pruebas): un objeto como ``Auto`` de accessible_output2
		(con ``get_first_available_output``) o directamente un lector con ``speak``, ``braille`` y ``silence``."""
		self.linea = LineaVentana()
		self._ventana = 0
		self._salida: Any = None
		self._inyectada = salida is not None
		self._tipo_salida = ""
		self._sapi_lista: Any = None  # un SAPI5 creado solo para listar voces
		self._con_nvda = False
		self._lector_visto = "ninguna"
		self._t_lector = 0.0
		self._aviso_braille = False  # el fallo del braille se registra una vez, no en cada mensaje
		super().__init__(opciones)
		if salida is not None:
			self._salida = salida
			self._tipo_salida = "inyectada"
			self._actualizar_nombre()
		else:
			self._abrir_salida()

	# ── La salida ────────────────────────────────────────────────────────────

	def _abrir_salida(self) -> None:
		"""Abre la salida que piden las opciones. Sin voz el juego sigue: se registra el motivo."""
		self._salida = None
		self._tipo_salida = ""
		self.nombre = "ninguna"
		if not self.opciones["activa"] or os.environ.get("APP_SIN_VOZ") == "1":
			log.info("Voz desactivada.")
			return
		salida = self.salida
		if salida == "sapi":
			try:
				from accessible_output2.outputs.sapi5 import SAPI5

				self._salida = SAPI5()
				self._tipo_salida = "sapi"
				self._ajustar_sapi()
			except Exception:  # noqa: BLE001 - accessible_output2 lanza OutputError sin detalle; se cae al lector
				log.warning("No se pudo abrir la voz SAPI: se usa el lector de pantalla.", exc_info=True)
		if self._salida is None:
			# «ninguna» también abre Auto: no habla, pero el braille sigue llegando al lector si lo hay.
			try:
				from accessible_output2.outputs.auto import Auto

				self._salida = Auto()
				self._tipo_salida = salida if salida in _SALIDAS_CON_LECTOR else "automatica"
			except Exception:  # noqa: BLE001 - sin voz el juego sigue (se registra el motivo)
				log.exception("No se pudo iniciar accessible_output2: el juego irá sin voz.")
				self._salida = None
		self._actualizar_nombre()
		if salida == "ninguna":
			log.info("Voz apagada por preferencia (salida «ninguna»); braille por %s.", self._nombre_lector())
		else:
			log.info("Voz por %s (salida «%s»).", self.nombre, salida)

	def _ajustar_sapi(self) -> None:
		"""Lleva a SAPI la voz, la velocidad y el volumen de las opciones."""
		s = self._salida
		if self._tipo_salida != "sapi" or s is None:
			return
		o = self.opciones
		try:
			s.set_rate(o["sapi_velocidad"])
			s.set_volume(o["sapi_volumen"])
			if o["sapi_voz"]:
				voces = s.list_voices()
				elegida = next((v for v in voces if v == o["sapi_voz"]), None) or next(
					(v for v in voces if o["sapi_voz"].lower() in v.lower()), None
				)
				if elegida is None:
					log.warning("No está la voz SAPI %s; se deja la de Windows.", o["sapi_voz"])
				else:
					s.set_voice(elegida)
		except Exception:  # noqa: BLE001 - errores COM de SAPI: la voz sigue con lo que tuviera
			log.warning("No se pudieron aplicar los ajustes de la voz SAPI.", exc_info=True)

	def _lector(self) -> Any:
		"""El lector activo ahora: se pregunta cada vez, por si se abre o se cierra.

		Con la salida «lector» o «ninguna» nunca es la voz de Windows: si no hay
		lector de pantalla abierto, None (y no se habla), también al redetectar.
		"""
		s = self._salida
		if s is None:
			return None
		try:
			return primer_lector(s, permitir_sistema=self.salida in ("automatica", "sapi"))
		except Exception:  # noqa: BLE001 - un fallo del lector no debe tumbar el juego
			log.warning("No se pudo saber qué lector de pantalla hay.", exc_info=True)
			return None

	def _nombre_lector(self) -> str:
		"""Nombre de la salida que se vio en la última comprobación («ninguna» si no había)."""
		return self._lector_visto

	def _actualizar_nombre(self) -> None:
		"""Mira qué salida hay ahora. Con «ninguna», ``nombre`` es «ninguna» aunque haya lector (solo recibe el braille)."""
		lector = self._lector()
		self._lector_visto = type(lector).__name__ if lector is not None else "ninguna"
		nombre = "ninguna" if self.salida == "ninguna" else self._lector_visto
		if nombre != self.nombre:
			if self.nombre != "ninguna":
				log.info("Ahora la voz va por %s (antes, %s).", nombre, self.nombre)
			self.nombre = nombre
		if (self._lector_visto == "NVDA") != self._con_nvda:
			self._con_nvda = self._lector_visto == "NVDA"
			self._ajustar_linea()

	def _velocidad(self) -> int:
		return int(self.opciones["sapi_velocidad"]) if self._tipo_salida == "sapi" else 0

	def configurar(self, opciones: dict) -> None:
		"""Aplica opciones en caliente: cambia de salida si hace falta, y ajusta voz, velocidad y volumen.

		Entre «automatica», «lector» y «ninguna» no se vuelve a abrir nada:
		las tres usan el mismo ``Auto`` y solo cambia a quién se le permite
		hablar. Al pasar a «ninguna» no se corta lo que se esté diciendo: suele
		ser el aviso de que la voz se va a apagar, y conviene oírlo entero.
		"""
		activa_antes, salida_antes = self.opciones["activa"], self.salida
		super().configurar(opciones)
		cambia = (self.opciones["activa"], self.salida) != (activa_antes, salida_antes)
		if self._inyectada or not cambia:
			self._ajustar_sapi()
		elif (
			self._salida is not None
			and activa_antes == self.opciones["activa"]
			and self._tipo_salida in _SALIDAS_CON_LECTOR
			and self.salida in _SALIDAS_CON_LECTOR
		):
			self._tipo_salida = self.salida
			self._actualizar_nombre()
			log.info("Salida de voz cambiada a «%s».", self.salida)
		else:
			if "ninguna" not in (salida_antes, self.salida):
				self._callar_con(salida_antes)
			self._abrir_salida()
		if self._inyectada and cambia:
			self._actualizar_nombre()
		self._ajustar_linea()

	def voces_sapi(self) -> list[str]:
		"""Nombres de las voces SAPI instaladas (lista vacía si SAPI no está)."""
		s = self._salida if self._tipo_salida == "sapi" else self._sapi_lista
		try:
			if s is None:
				from accessible_output2.outputs.sapi5 import SAPI5

				s = self._sapi_lista = SAPI5()
			return [str(v) for v in s.list_voices()]
		except Exception:  # noqa: BLE001 - OutputError o error COM: no hay SAPI que listar
			log.info("No se pudieron listar las voces SAPI.", exc_info=True)
			return []

	# ── Braille ──────────────────────────────────────────────────────────────

	def instalar_ventana(self, hwnd: int) -> None:
		"""Da a la voz la ventana del reproductor (su HWND), para el braille fijo con NVDA.

		Conviene llamarlo con la ventana recién creada: la línea la anota como panel antes de que el lector la vea.
		"""
		self._ventana = int(hwnd or 0)
		self._ajustar_linea()

	def _ajustar_linea(self) -> None:
		"""Mensajes fijos en la línea solo con NVDA: a otros lectores el control oculto les quitaría el foco."""
		activa = self.braille == "fijo" and self._con_nvda
		if activa and not self.linea.instalada and self._ventana:
			self.linea.instalar(self._ventana)
		self.linea.activar(activa)

	def _a_braille(self, lector: Any, texto: str, interrumpir: bool) -> None:
		if self.braille == "nada":
			return
		if self.braille == "fijo" and self.linea.instalada and type(lector).__name__ == "NVDA":
			self.linea.mostrar(texto, juntar=not interrumpir)
			return
		try:
			lector.braille(texto)  # NVDA, JAWS y System Access; los demás no tienen braille y no hacen nada
		except Exception:  # noqa: BLE001 - sin braille la voz sigue
			if not self._aviso_braille:
				self._aviso_braille = True
				log.warning("No se pudo mandar el mensaje a la línea braille.", exc_info=True)

	# ── Hablar ───────────────────────────────────────────────────────────────

	def _hablar(self, texto: str, interrumpir: bool, canal: str) -> bool:
		lector = self._lector()
		if lector is None:
			return False
		if self.salida == "ninguna":
			# No se habla: el mensaje ya está en el historial y en la pantalla; el braille sigue.
			self._a_braille(lector, texto, interrumpir)
			return False
		dicho = True
		try:
			lector.speak(texto, interrupt=interrumpir)
		except Exception:  # noqa: BLE001 - un fallo del lector no debe tumbar el juego
			log.warning("El lector de pantalla no pudo hablar.", exc_info=True)
			dicho = False
		self._a_braille(lector, texto, interrumpir)
		return dicho

	def callar(self) -> None:
		"""Corta lo que se esté diciendo. Al lector, no a ``Auto``, que no tiene ``silence``.

		Con la salida «ninguna» no se toca el lector: el juego no está hablando,
		y lo que diga el lector es del usuario (por ejemplo, otra ventana).
		"""
		self._callar_con(self.salida)

	def _callar_con(self, salida: str) -> None:
		"""Calla la salida que correspondía a ``salida`` (al cambiar de salida, la anterior)."""
		if salida == "ninguna" or self._salida is None:
			return
		try:
			lector = primer_lector(self._salida, permitir_sistema=salida in ("automatica", "sapi"))
		except Exception:  # noqa: BLE001 - un fallo del lector no debe tumbar el juego
			log.warning("No se pudo saber qué lector de pantalla hay.", exc_info=True)
			return
		if lector is None:
			return
		try:
			lector.silence()
		except Exception:  # noqa: BLE001 - no todos los lectores permiten callar
			log.debug("No se pudo silenciar la voz.", exc_info=True)

	def tic(self) -> None:
		"""Una vez por fotograma, desde el hilo principal: redetecta el lector cada dos segundos y publica el braille fijo."""
		ahora = self._reloj()
		if self._salida is not None and ahora - self._t_lector >= CADA_CUANTO_LECTOR:
			self._t_lector = ahora
			self._actualizar_nombre()
		self.linea.publicar()

	def cerrar(self) -> None:
		"""Calla, quita el control del braille fijo y suelta la salida."""
		self.callar()
		self.linea.quitar()
		self._salida = None
		self._sapi_lista = None
		self.nombre = "ninguna"


class VozFalsa(_VozBase):
	"""Voz para las pruebas: no habla; apunta en ``registro`` (texto, canal, interrumpir) lo que se habría dicho.

	Lo dicho al repasar el historial se apunta con el canal ``historial``. Lo que llega por un canal
	desactivado no se apunta (no se habría oído), pero queda en ``historial``, como en la voz real.
	"""

	def __init__(self, opciones: dict | None = None) -> None:
		super().__init__(opciones)
		self.registro: list[tuple[str, str, bool]] = []
		self.callada = 0  # veces que se ha llamado a callar()
		self.nombre = "falsa"

	def _hablar(self, texto: str, interrumpir: bool, canal: str) -> bool:
		# Con «ninguna» la voz real no habla: la falsa tampoco apunta (las pruebas del reproductor lo comprueban).
		if not self.opciones["activa"] or self.salida == "ninguna":
			return False
		self.registro.append((texto, canal, interrumpir))
		return True

	def callar(self) -> None:
		"""Apunta que se ha pedido silencio (con «ninguna», como la real, no hay nada que callar)."""
		if self.salida != "ninguna":
			self.callada += 1

	def voces_sapi(self) -> list[str]:
		"""Sin SAPI: ninguna voz."""
		return []

	def instalar_ventana(self, hwnd: int) -> None:
		"""No hay braille que instalar."""


def sintetizar_a_fichero(texto: str, ruta: Path, voz: str | None = None, velocidad: int = 0) -> bool:
	"""Escribe ``texto`` hablado por SAPI en un WAV (44,1 kHz, 16 bits, mono) sin que suene nada.

	Sirve para voz posicionada: el motor de sonido carga el fichero y lo sitúa como cualquier otro sonido.
	``voz`` es el nombre (o parte del nombre) de una voz SAPI; None, la de Windows. Devuelve si se pudo.
	"""
	texto = (texto or "").strip()
	if not texto:
		return False
	try:
		import pythoncom
		import pywintypes
		from win32com.client import Dispatch
	except ImportError:
		log.warning("No está pywin32: no se puede sintetizar voz a un fichero.", exc_info=True)
		return False
	ruta = Path(ruta)
	flujo = None
	try:
		pythoncom.CoInitialize()  # por si se llama desde un hilo que no es el principal
		hablante = Dispatch("SAPI.SpVoice")
		if voz:
			elegida = next((v for v in hablante.GetVoices() if voz.lower() in v.GetDescription().lower()), None)
			if elegida is None:
				log.warning("No está la voz SAPI %s; se usa la de Windows.", voz)
			else:
				hablante.Voice = elegida
		hablante.Rate = max(-10, min(10, int(velocidad)))
		flujo = Dispatch("SAPI.SpFileStream")
		flujo.Format.Type = SAFT_44KHZ_16BIT_MONO
		ruta.parent.mkdir(parents=True, exist_ok=True)
		flujo.Open(str(ruta), SSFM_CREAR_PARA_ESCRIBIR, False)
		hablante.AudioOutputStream = flujo
		hablante.Speak(texto, 0)  # síncrono: al volver, el fichero está completo
		flujo.Close()
		flujo = None
		return ruta.is_file() and ruta.stat().st_size > 44
	except pywintypes.com_error, OSError, AttributeError:
		log.warning("No se pudo sintetizar la voz en %s.", ruta, exc_info=True)
		if flujo is not None:
			try:
				flujo.Close()
			except pywintypes.com_error:
				log.debug("El fichero de voz ya estaba cerrado.", exc_info=True)
		return False
