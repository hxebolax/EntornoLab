"""Mando de Xbox, de PlayStation o compatible, por la interfaz normalizada de SDL.

Se usa ``pygame._sdl2.controller``, que da la misma disposición de botones a
todos los mandos conocidos; lo que cambia de una familia a otra es cómo se
**llama** cada botón (A o Equis, LB o L1), y la voz debe decir siempre el
nombre del mando que el alumno tiene en las manos.

El mapa de serie sigue el apartado 12.4 del informe:

- Palanca izquierda: moverse (adelante y atrás; a los lados, girar).
- Palanca derecha: mirar en la dirección apuntada (delante, derecha, detrás, izquierda), sin girarse.
- A o Equis, interactuar; X o Cuadrado, dónde estoy; Y o Triángulo, qué hay delante.
- B o Círculo: atrás en los menús; recorriendo el entorno, calla la voz («cancelar» lo que se está diciendo).
- Botones superiores: girar un paso. Gatillo derecho: bastón sonoro.
- Gatillo izquierdo: mantenido, da a los demás botones su segunda función.
- Cruceta: lista de lo cercano. Menú u Options: pausa. Vista o Crear: ayuda.

Los ejes se normalizan a ±1 dividiendo por 32767; la zona muerta es ajustable
y se reescala para que el recorrido útil empiece en cero; los gatillos se
tratan como botones con histéresis, para que no tiemblen en el umbral.

Todo se puede probar sin un mando real: los eventos de pygame se construyen a
mano y ``Mandos.conectar`` acepta cualquier objeto con ``name``, ``rumble`` y
``get_axis``.

Este módulo no lee ni escribe la configuración: recibe y devuelve
diccionarios.
"""

from __future__ import annotations

import logging
import math
import re
from typing import Any

import pygame

from app.core.i18n import IDIOMA_ORIGEN, N_, _, idioma_actual
from app.entrada import acciones
from app.entrada.teclado import Cambio, MapaTeclado, nombre_combinacion

log = logging.getLogger(__name__)

# ── Botones y ejes ───────────────────────────────────────────────────────────

# Los dos últimos (15 y 20 en SDL) no tienen constante en pygame: son el
# botón Compartir o del micrófono y el panel táctil de los mandos de PlayStation.
BOTONES_SDL: dict[int, str] = {
	pygame.CONTROLLER_BUTTON_A: "a",
	pygame.CONTROLLER_BUTTON_B: "b",
	pygame.CONTROLLER_BUTTON_X: "x",
	pygame.CONTROLLER_BUTTON_Y: "y",
	pygame.CONTROLLER_BUTTON_BACK: "vista",
	pygame.CONTROLLER_BUTTON_GUIDE: "guia",
	pygame.CONTROLLER_BUTTON_START: "menu",
	pygame.CONTROLLER_BUTTON_LEFTSTICK: "l3",
	pygame.CONTROLLER_BUTTON_RIGHTSTICK: "r3",
	pygame.CONTROLLER_BUTTON_LEFTSHOULDER: "lb",
	pygame.CONTROLLER_BUTTON_RIGHTSHOULDER: "rb",
	pygame.CONTROLLER_BUTTON_DPAD_UP: "arriba",
	pygame.CONTROLLER_BUTTON_DPAD_DOWN: "abajo",
	pygame.CONTROLLER_BUTTON_DPAD_LEFT: "izquierda",
	pygame.CONTROLLER_BUTTON_DPAD_RIGHT: "derecha",
	15: "misc",
	20: "panel",
}
SDL_DE_BOTON: dict[str, int] = {nombre: codigo for codigo, nombre in BOTONES_SDL.items()}
EJES_SDL: dict[int, str] = {
	pygame.CONTROLLER_AXIS_LEFTX: "lx",
	pygame.CONTROLLER_AXIS_LEFTY: "ly",
	pygame.CONTROLLER_AXIS_RIGHTX: "rx",
	pygame.CONTROLLER_AXIS_RIGHTY: "ry",
	pygame.CONTROLLER_AXIS_TRIGGERLEFT: "lt",
	pygame.CONTROLLER_AXIS_TRIGGERRIGHT: "rt",
}
SDL_DE_EJE: dict[str, int] = {nombre: codigo for codigo, nombre in EJES_SDL.items()}
GATILLOS: tuple[str, ...] = ("lt", "rt")
# Los gatillos cuentan como botones. El botón guía (Xbox, PlayStation) es del sistema y no se asigna.
ORDEN_BOTONES: tuple[str, ...] = (
	"a",
	"b",
	"x",
	"y",
	"lb",
	"rb",
	"lt",
	"rt",
	"l3",
	"r3",
	"arriba",
	"abajo",
	"izquierda",
	"derecha",
	"vista",
	"menu",
	"panel",
	"misc",
)
EJE_MAXIMO = 32767.0

XBOX = "xbox"
PS = "ps"
FAMILIAS: tuple[str, ...] = (XBOX, PS)

# Nombre corto de cada botón, como viene escrito en el mando.
NOMBRES: dict[str, dict[str, str]] = {
	XBOX: {
		"a": "A",
		"b": "B",
		"x": "X",
		"y": "Y",
		"lb": "LB",
		"rb": "RB",
		"lt": N_("gatillo izquierdo"),
		"rt": N_("gatillo derecho"),
		"l3": N_("pulsar la palanca izquierda"),
		"r3": N_("pulsar la palanca derecha"),
		"arriba": N_("cruceta arriba"),
		"abajo": N_("cruceta abajo"),
		"izquierda": N_("cruceta izquierda"),
		"derecha": N_("cruceta derecha"),
		"vista": N_("Vista"),
		"menu": N_("Menú"),
		"panel": N_("panel táctil"),
		"misc": N_("Compartir"),
		"guia": N_("Xbox"),
	},
	PS: {
		"a": N_("Equis"),
		"b": N_("Círculo"),
		"x": N_("Cuadrado"),
		"y": N_("Triángulo"),
		"lb": "L1",
		"rb": "R1",
		"lt": "L2",
		"rt": "R2",
		"l3": N_("L3, pulsar la palanca izquierda"),
		"r3": N_("R3, pulsar la palanca derecha"),
		"arriba": N_("cruceta arriba"),
		"abajo": N_("cruceta abajo"),
		"izquierda": N_("cruceta izquierda"),
		"derecha": N_("cruceta derecha"),
		"vista": N_("Crear o Share"),
		"menu": N_("Options"),
		"panel": N_("panel táctil"),
		"misc": N_("micrófono"),
		"guia": N_("PlayStation"),
	},
}
# El mismo botón dicho dentro de una frase, con su artículo: «pulsa el botón A».
FRASES: dict[str, dict[str, str]] = {
	XBOX: {
		"a": N_("el botón A"),
		"b": N_("el botón B"),
		"x": N_("el botón X"),
		"y": N_("el botón Y"),
		"lb": N_("el botón LB"),
		"rb": N_("el botón RB"),
		"lt": N_("el gatillo izquierdo"),
		"rt": N_("el gatillo derecho"),
		"l3": N_("la palanca izquierda pulsada"),
		"r3": N_("la palanca derecha pulsada"),
		"arriba": N_("la cruceta arriba"),
		"abajo": N_("la cruceta abajo"),
		"izquierda": N_("la cruceta izquierda"),
		"derecha": N_("la cruceta derecha"),
		"vista": N_("el botón Vista"),
		"menu": N_("el botón Menú"),
		"panel": N_("el panel táctil"),
		"misc": N_("el botón Compartir"),
		"guia": N_("el botón Xbox"),
	},
	PS: {
		"a": N_("el botón Equis"),
		"b": N_("el botón Círculo"),
		"x": N_("el botón Cuadrado"),
		"y": N_("el botón Triángulo"),
		"lb": N_("el botón L1"),
		"rb": N_("el botón R1"),
		"lt": N_("el botón L2"),
		"rt": N_("el botón R2"),
		"l3": N_("la palanca izquierda pulsada, L3"),
		"r3": N_("la palanca derecha pulsada, R3"),
		"arriba": N_("la cruceta arriba"),
		"abajo": N_("la cruceta abajo"),
		"izquierda": N_("la cruceta izquierda"),
		"derecha": N_("la cruceta derecha"),
		"vista": N_("el botón Crear o Share"),
		"menu": N_("el botón Options"),
		"panel": N_("el panel táctil"),
		"misc": N_("el botón del micrófono"),
		"guia": N_("el botón PlayStation"),
	},
}

# Palabras del nombre del dispositivo que delatan un mando de PlayStation.
# «wireless controller» es como se presenta el DualShock 4 por Bluetooth.
_PISTAS_PS = ("ps3", "ps4", "ps5", "dualshock", "dualsense", "playstation", "sony", "wireless controller")


# Palabras que delatan un mando de Xbox y mandan sobre las anteriores: el de Xbox se
# presenta como «Xbox Wireless Controller», que contiene la pista del DualShock 4.
_PISTAS_XBOX = ("xbox", "x-box", "xinput", "microsoft")


def familia_de(nombre: str) -> str:
	"""Familia de un mando por el nombre con el que se presenta: «ps» o «xbox» (y compatibles)."""
	n = (nombre or "").lower()
	if any(pista in n for pista in _PISTAS_XBOX):
		return XBOX
	return PS if any(pista in n for pista in _PISTAS_PS) else XBOX


def nombre_boton(boton: str, familia: str = XBOX) -> str:
	"""Nombre corto de un botón en esa familia («A», «Equis», «gatillo derecho»)."""
	return _(NOMBRES.get(familia, NOMBRES[XBOX]).get(boton, boton))


def frase_boton(boton: str, familia: str = XBOX) -> str:
	"""El botón dicho dentro de una frase, con artículo («el botón Equis»)."""
	return _(FRASES.get(familia, FRASES[XBOX]).get(boton, boton))


# ── Mapa de serie ────────────────────────────────────────────────────────────

CAPA_JUEGO = "juego"
CAPA_JUEGO_2 = "juego_2"  # con el botón modificador mantenido
CAPA_MENU = "menu"
CAPAS: tuple[str, ...] = (CAPA_JUEGO, CAPA_JUEGO_2, CAPA_MENU)
_CONTEXTO_DE_CAPA = {CAPA_JUEGO: acciones.JUEGO, CAPA_JUEGO_2: acciones.JUEGO, CAPA_MENU: acciones.MENU}
MODIFICADOR_POR_DEFECTO = "lt"

POR_DEFECTO: dict[str, dict[str, str]] = {
	CAPA_JUEGO: {
		"a": "interactuar",
		"b": "callar",
		"x": "donde_estoy",
		"y": "mirar_delante",
		"lb": "girar_izquierda",
		"rb": "girar_derecha",
		"rt": "sonda",
		"l3": "alrededor",
		"r3": "repetir",
		"arriba": "cercano_anterior",
		"abajo": "cercano_siguiente",
		"izquierda": "brujula",
		"derecha": "objetivo",
		"vista": "ayuda",
		"menu": "pausa",
	},
	CAPA_JUEGO_2: {
		"a": "pista",
		"b": "volver_inicio",
		"x": "descubiertos",
		"y": "confirmar",
		"lb": "paso_izquierda",
		"rb": "paso_derecha",
		"rt": "eco",
		"l3": "brujula",
		"r3": "objetivo",
		"arriba": "repetir",
		"abajo": "media_vuelta",
		"izquierda": "historial_anterior",
		"derecha": "historial_siguiente",
		"vista": "ayuda",
		"menu": "pausa",
	},
	CAPA_MENU: {
		"a": "menu_aceptar",
		"b": "menu_atras",
		"x": "repetir",
		"y": "ayuda",
		"lb": "historial_anterior",
		"rb": "historial_siguiente",
		"arriba": "menu_arriba",
		"abajo": "menu_abajo",
		"izquierda": "menu_izquierda",
		"derecha": "menu_derecha",
		"vista": "ayuda",
		"menu": "menu_atras",
	},
}
# Botones que no se reasignan: siempre tiene que haber cómo pausar, y cómo aceptar y volver en un menú.
FIJOS: dict[str, frozenset[str]] = {
	CAPA_JUEGO: frozenset({"menu"}),
	CAPA_JUEGO_2: frozenset({"menu"}),
	CAPA_MENU: frozenset({"a", "b"}),
}


class MapaMando:
	"""Qué acción hace cada botón en cada capa, y cuál es el botón modificador."""

	def __init__(self, datos: dict | None = None) -> None:
		self.modificador = MODIFICADOR_POR_DEFECTO
		self._mapa: dict[str, dict[str, str]] = {c: dict(m) for c, m in POR_DEFECTO.items()}
		if datos:
			self._cargar(datos)

	@classmethod
	def de_dict(cls, datos: dict | None) -> MapaMando:
		"""Crea el mapa desde lo guardado; tolera claves que faltan, sobran o están mal."""
		return cls(datos)

	def a_dict(self) -> dict[str, Any]:
		"""El mapa completo, listo para guardar como JSON.

		Un botón de serie que se ha dejado sin asignar se guarda como
		``nada``: si simplemente faltara, al cargar volvería su valor de
		serie (que es lo que debe pasar con un botón nuevo de otra versión).
		"""
		datos: dict[str, Any] = {"modificador": self.modificador}
		for capa, mapa in self._mapa.items():
			datos[capa] = dict(mapa)
			for boton in POR_DEFECTO[capa]:
				if boton not in mapa and not (capa != CAPA_MENU and boton == self.modificador):
					datos[capa][boton] = acciones.NADA
		return datos

	def _cargar(self, datos: dict) -> None:
		"""Aplica lo guardado sobre el mapa de serie, descartando botones y acciones que no existan."""
		if not isinstance(datos, dict):
			return
		modificador = datos.get("modificador")
		if isinstance(modificador, str) and modificador in ORDEN_BOTONES and modificador != "menu":
			self.modificador = modificador
		for capa in CAPAS:
			guardado = datos.get(capa)
			if not isinstance(guardado, dict):
				continue
			contexto = _CONTEXTO_DE_CAPA[capa]
			nuevo = dict(POR_DEFECTO[capa])
			for boton, accion in guardado.items():
				if boton not in ORDEN_BOTONES or boton in FIJOS[capa]:
					continue
				if accion == acciones.NADA:
					nuevo.pop(boton, None)
				elif acciones.vale_en(str(accion), contexto):
					nuevo[boton] = str(accion)
				else:
					log.warning("Mapa de mando: se descarta la acción desconocida %s (%s).", accion, capa)
			self._mapa[capa] = nuevo
		for capa in (CAPA_JUEGO, CAPA_JUEGO_2):
			self._mapa[capa].pop(self.modificador, None)

	def restablecer(self, capa: str | None = None) -> None:
		"""Vuelve al mapa de serie, en una capa o en todas (y al modificador de serie)."""
		for c in CAPAS:
			if capa is None or capa == c:
				self._mapa[c] = dict(POR_DEFECTO[c])
		if capa is None:
			self.modificador = MODIFICADOR_POR_DEFECTO

	def accion_de(self, capa: str, boton: str) -> str | None:
		"""La acción de un botón en una capa; None si no tiene."""
		return self._mapa.get(capa, {}).get(boton)

	def boton_de(self, capa: str, accion: str) -> str | None:
		"""El primer botón (en el orden del mando) que hace una acción en una capa."""
		mapa = self._mapa.get(capa, {})
		return next((b for b in ORDEN_BOTONES if mapa.get(b) == accion), None)

	def reasignables(self, capa: str) -> list[tuple[str, str]]:
		"""(botón, acción o ``nada``) de los botones que se pueden cambiar en una capa."""
		mapa = self._mapa.get(capa, {})
		fuera = set(FIJOS.get(capa, ()))
		if capa != CAPA_MENU:
			fuera.add(self.modificador)
		return [(b, mapa.get(b, acciones.NADA)) for b in ORDEN_BOTONES if b not in fuera]

	def cambiar(self, capa: str, boton: str, accion: str, familia: str = XBOX) -> Cambio:
		"""Pone ``accion`` en ``boton`` e intercambia con el botón que ya la tuviera.

		Como en el teclado: la acción que estaba en ``boton`` pasa al botón
		que tenía ``accion``. ``nada`` deja el botón sin asignar.
		"""
		mapa = self._mapa.get(capa)
		if mapa is None or boton not in ORDEN_BOTONES:
			return Cambio(False, _("Ese botón no existe."))
		if boton in FIJOS[capa] or (capa != CAPA_MENU and boton == self.modificador):
			return Cambio(False, _("{boton} no se puede cambiar: está reservado.").format(boton=frase_boton(boton, familia).capitalize()))
		if accion == acciones.NADA:
			mapa.pop(boton, None)
			return Cambio(True, _("{boton}, sin asignar.").format(boton=frase_boton(boton, familia).capitalize()), boton)
		if not acciones.vale_en(accion, _CONTEXTO_DE_CAPA[capa]):
			return Cambio(False, _("Esa acción no se puede asignar aquí."))
		anterior = mapa.get(boton)
		if anterior == accion:
			return Cambio(
				True,
				_("{accion} ya está en {boton}.").format(accion=acciones.nombre_accion(accion), boton=frase_boton(boton, familia)),
				boton,
			)
		origen = next((b for b in ORDEN_BOTONES if mapa.get(b) == accion and b not in FIJOS[capa]), None)
		mapa[boton] = accion
		frase = _("{accion}, ahora con {boton}.").format(accion=acciones.nombre_accion(accion), boton=frase_boton(boton, familia))
		desplazada = None
		if origen is not None:
			if anterior is not None:
				mapa[origen] = anterior
				desplazada = anterior
				frase += " " + _("{accion} pasa a {boton}.").format(
					accion=acciones.nombre_accion(anterior), boton=frase_boton(origen, familia)
				)
			else:
				del mapa[origen]
		elif anterior is not None:
			desplazada = anterior
			frase += " " + _("{accion} se queda sin botón en esta capa.").format(accion=acciones.nombre_accion(anterior))
		return Cambio(True, frase, boton, desplazada)

	def cambiar_modificador(self, boton: str, familia: str = XBOX) -> Cambio:
		"""Elige el botón que, mantenido, da la segunda función. Lo que hiciera ese botón jugando se pierde."""
		if boton not in ORDEN_BOTONES or boton in FIJOS[CAPA_JUEGO]:
			return Cambio(False, _("Ese botón no puede ser el de segunda función."))
		self.modificador = boton
		for capa in (CAPA_JUEGO, CAPA_JUEGO_2):
			self._mapa[capa].pop(boton, None)
		return Cambio(True, _("Segunda función, ahora con {boton}.").format(boton=frase_boton(boton, familia)), boton)

	def frase_de(self, accion: str, contexto: str = acciones.JUEGO, familia: str = XBOX) -> str:
		"""Cómo se hace una acción con el mando, dicho en una frase; cadena vacía si no tiene botón.

		Una segunda función se dice con su modificador: «el gatillo izquierdo
		más el botón A».
		"""
		if contexto == acciones.MENU:
			boton = self.boton_de(CAPA_MENU, accion)
			return frase_boton(boton, familia) if boton else ""
		boton = self.boton_de(CAPA_JUEGO, accion)
		if boton:
			return frase_boton(boton, familia)
		boton = self.boton_de(CAPA_JUEGO_2, accion)
		if boton:
			return _("{modificador} más {boton}").format(
				modificador=frase_boton(self.modificador, familia), boton=frase_boton(boton, familia)
			)
		return ""

	def cambios(self, familia: str = XBOX) -> list[str]:
		"""Frases con lo cambiado respecto al mapa de serie, para la ayuda."""
		titulos = {CAPA_JUEGO: _("Jugando"), CAPA_JUEGO_2: _("Jugando, segunda función"), CAPA_MENU: _("En los menús")}
		frases: list[str] = []
		if self.modificador != MODIFICADOR_POR_DEFECTO:
			frases.append(_("La segunda función se hace con {boton}.").format(boton=frase_boton(self.modificador, familia)))
		for capa in CAPAS:
			for boton in ORDEN_BOTONES:
				ahora = self._mapa[capa].get(boton)
				if ahora != POR_DEFECTO[capa].get(boton) and not (capa != CAPA_MENU and boton == self.modificador):
					frases.append(
						_("{capa}: {boton}, {accion}.").format(
							capa=titulos[capa],
							boton=frase_boton(boton, familia),
							accion=acciones.nombre_accion(ahora or acciones.NADA).lower(),
						)
					)
		return frases


# ── Ejes ─────────────────────────────────────────────────────────────────────


def normalizar_eje(crudo: float) -> float:
	"""Valor de un eje de SDL (−32768 a 32767) llevado a −1..1."""
	return max(-1.0, min(1.0, float(crudo) / EJE_MAXIMO))


def zona_muerta(x: float, y: float, zona: float) -> tuple[float, float]:
	"""Aplica una zona muerta circular a una palanca y reescala el resto a 0..1.

	Circular y no por eje, para que empujar en diagonal no «se pegue» a los
	ejes; reescalada, para que justo al salir de la zona muerta el movimiento
	empiece despacio y no de golpe.
	"""
	zona = max(0.0, min(0.95, zona))
	modulo = math.hypot(x, y)
	if modulo <= zona or modulo == 0.0:
		return 0.0, 0.0
	escala = min(1.0, (modulo - zona) / (1.0 - zona)) / modulo
	return x * escala, y * escala


OPCIONES_POR_DEFECTO: dict[str, Any] = {
	"zona_muerta": 0.25,  # 0 a 0,95 del recorrido de la palanca
	"gatillo_pulsar": 0.3,  # el gatillo cuenta como pulsado al pasar de aquí...
	"gatillo_soltar": 0.15,  # ...y como soltado al bajar de aquí
	"umbral_palanca": 0.6,  # inclinación que cuenta como «pulsación» (menús y mirar)
	"repeticion_inicial": 0.45,  # segundos hasta la primera repetición en un menú
	"repeticion": 0.3,  # segundos entre repeticiones
	"vibracion": True,
	"fuerza_vibracion": 1.0,  # 0 a 1
	"palanca_izquierda": "giro",  # «giro»: a los lados gira; «lateral»: a los lados da pasos de lado
	"palanca_derecha": "mirar",  # «mirar»: acciones mirar_*; «analogica»: se pasa al motor; «giro»: gira
	"decir_botones": True,  # con un mando conectado, las frases nombran botones en vez de teclas
}

_SECTORES_MIRAR = ("mirar_delante", "mirar_derecha", "mirar_detras", "mirar_izquierda")


def sanear_opciones(datos: dict | None) -> dict[str, Any]:
	"""Opciones saneadas: las de serie más las recibidas que sean del tipo y rango esperados."""
	opciones = dict(OPCIONES_POR_DEFECTO)
	for clave, valor in (datos or {}).items():
		if clave not in opciones:
			continue
		serie = opciones[clave]
		if isinstance(serie, bool):
			opciones[clave] = bool(valor)
		elif isinstance(serie, float):
			try:
				opciones[clave] = float(valor)
			except TypeError, ValueError:
				log.warning("Opción de mando %s con un valor que no es un número: %r.", clave, valor)
		elif isinstance(valor, str):
			opciones[clave] = valor
	opciones["zona_muerta"] = max(0.0, min(0.95, opciones["zona_muerta"]))
	opciones["fuerza_vibracion"] = max(0.0, min(1.0, opciones["fuerza_vibracion"]))
	opciones["gatillo_pulsar"] = max(0.05, min(0.95, opciones["gatillo_pulsar"]))
	# Sin separación entre los dos umbrales no hay histéresis: se impone una mínima.
	opciones["gatillo_soltar"] = max(0.01, min(opciones["gatillo_pulsar"] - 0.02, opciones["gatillo_soltar"]))
	opciones["umbral_palanca"] = max(0.2, min(0.95, opciones["umbral_palanca"]))
	if opciones["palanca_izquierda"] not in ("giro", "lateral"):
		opciones["palanca_izquierda"] = "giro"
	if opciones["palanca_derecha"] not in ("mirar", "analogica", "giro"):
		opciones["palanca_derecha"] = "mirar"
	return opciones


class Mandos:
	"""Los mandos conectados: traduce sus eventos a acciones y los hace vibrar.

	Puede haber varios enchufados (un alumno y su profesor): todos valen, y
	la familia que se usa para nombrar los botones es la del último que se
	ha tocado.
	"""

	def __init__(self, mapa: MapaMando | dict | None = None, opciones: dict | None = None, iniciar: bool = True) -> None:
		self.mapa = mapa if isinstance(mapa, MapaMando) else MapaMando(mapa)
		self.opciones = sanear_opciones(opciones)
		self._sdl: Any = None
		self._mandos: dict[int, Any] = {}
		self._familias: dict[int, str] = {}
		self._activo: int | None = None
		self._ejes: dict[int, dict[str, float]] = {}
		self._pulsados: dict[tuple[int, str], str] = {}
		self._modificadores: set[int] = set()
		self._gatillos: set[tuple[int, str]] = set()
		self._repeticion: dict[str, float] = {}
		self._sector: int | None = None
		self._avisos: list[str] = []
		if iniciar:
			self.iniciar()

	# ── Conexión ──

	def iniciar(self) -> bool:
		"""Arranca el soporte de mandos de SDL y abre los que ya estén enchufados. Devuelve si se pudo."""
		try:
			from pygame._sdl2 import controller

			controller.init()
		except ImportError, pygame.error:
			log.warning("No se pudo iniciar el soporte de mandos: se sigue con el teclado.", exc_info=True)
			self._sdl = None
			return False
		self._sdl = controller
		for indice in range(controller.get_count()):
			self._abrir(indice, anunciar=False)
		return True

	def _abrir(self, indice: int, anunciar: bool = True) -> None:
		if self._sdl is None:
			return
		try:
			if not self._sdl.is_controller(indice):
				return
			mando = self._sdl.Controller(indice)
			identificador = int(mando.as_joystick().get_instance_id())
		except pygame.error:
			log.warning("No se pudo abrir el mando %s.", indice, exc_info=True)
			return
		if identificador not in self._mandos:
			self.conectar(mando, identificador, anunciar)

	def conectar(self, mando: Any, identificador: int, anunciar: bool = True) -> None:
		"""Añade un mando ya abierto (o uno falso, en las pruebas).

		``mando`` solo necesita ``name``; ``rumble`` si vibra. El aviso de
		conexión no se dice aquí: queda en ``tomar_avisos()`` para que lo
		diga quien tiene la voz.
		"""
		nombre = str(getattr(mando, "name", "") or _("mando"))
		self._mandos[identificador] = mando
		self._familias[identificador] = familia_de(nombre)
		self._ejes[identificador] = dict.fromkeys(SDL_DE_EJE, 0.0)
		self._activo = identificador
		log.info("Mando conectado: %s (familia %s).", nombre, self._familias[identificador])
		if anunciar:
			self._avisos.append(_("Mando conectado: {nombre}.").format(nombre=nombre))

	def desconectar(self, identificador: int, anunciar: bool = True) -> list[tuple[str, bool]]:
		"""Quita un mando y devuelve las acciones que tenía pulsadas, ya soltadas."""
		mando = self._mandos.pop(identificador, None)
		if mando is None:
			return []
		self._familias.pop(identificador, None)
		self._ejes.pop(identificador, None)
		self._modificadores.discard(identificador)
		self._gatillos = {g for g in self._gatillos if g[0] != identificador}
		sueltas = [(accion, False) for clave, accion in self._pulsados.items() if clave[0] == identificador]
		self._pulsados = {clave: accion for clave, accion in self._pulsados.items() if clave[0] != identificador}
		if self._activo == identificador:
			self._activo = next(iter(self._mandos), None)
		cerrar = getattr(mando, "quit", None)
		if callable(cerrar):
			try:
				cerrar()
			except pygame.error:
				log.debug("El mando ya estaba cerrado.", exc_info=True)
		log.info("Mando desconectado.")
		if anunciar:
			self._avisos.append(_("Mando desconectado. Puedes seguir con el teclado."))
		return sueltas

	def tomar_avisos(self) -> list[str]:
		"""Frases pendientes de decir (mando conectado o desconectado); se vacían al leerlas."""
		avisos, self._avisos = self._avisos, []
		return avisos

	@property
	def conectado(self) -> bool:
		"""Si hay al menos un mando."""
		return bool(self._mandos)

	@property
	def conectados(self) -> list[str]:
		"""Nombres de los mandos conectados."""
		return [str(getattr(m, "name", "") or _("mando")) for m in self._mandos.values()]

	@property
	def familia(self) -> str:
		"""Familia del último mando usado («xbox» si no hay ninguno)."""
		return self._familias.get(self._activo, XBOX) if self._activo is not None else XBOX

	@property
	def modificador_pulsado(self) -> bool:
		"""Si algún mando tiene mantenido el botón de segunda función."""
		return bool(self._modificadores)

	# ── Eventos ──

	def evento(self, evento: pygame.event.Event, contexto: str = acciones.JUEGO) -> list[tuple[str, bool]]:
		"""(acción, pulsada) de un evento de mando; lista vacía si no es de mando o no tiene acción."""
		tipo = evento.type
		if tipo == pygame.CONTROLLERDEVICEADDED:
			self._abrir(int(evento.device_index))
			return []
		if tipo == pygame.CONTROLLERDEVICEREMOVED:
			return self.desconectar(int(evento.instance_id))
		if tipo not in (pygame.CONTROLLERBUTTONDOWN, pygame.CONTROLLERBUTTONUP, pygame.CONTROLLERAXISMOTION):
			return []
		identificador = int(getattr(evento, "instance_id", 0))
		if identificador not in self._mandos:
			return []
		if tipo == pygame.CONTROLLERAXISMOTION:
			return self._eje(identificador, EJES_SDL.get(evento.axis), normalizar_eje(evento.value), contexto)
		boton = BOTONES_SDL.get(evento.button)
		if boton is None:
			return []
		self._activo = identificador
		return self._boton(identificador, boton, tipo == pygame.CONTROLLERBUTTONDOWN, contexto)

	def _eje(self, identificador: int, eje: str | None, valor: float, contexto: str) -> list[tuple[str, bool]]:
		if eje is None:
			return []
		self._ejes[identificador][eje] = valor
		if eje not in GATILLOS:
			if abs(valor) >= self.opciones["umbral_palanca"]:
				self._activo = identificador
			return []
		# Histéresis: se pulsa al pasar del umbral alto y no se suelta hasta bajar del bajo.
		clave = (identificador, eje)
		if clave not in self._gatillos and valor >= self.opciones["gatillo_pulsar"]:
			self._gatillos.add(clave)
			self._activo = identificador
			return self._boton(identificador, eje, True, contexto)
		if clave in self._gatillos and valor < self.opciones["gatillo_soltar"]:
			self._gatillos.discard(clave)
			return self._boton(identificador, eje, False, contexto)
		return []

	def _boton(self, identificador: int, boton: str, abajo: bool, contexto: str) -> list[tuple[str, bool]]:
		clave = (identificador, boton)
		if not abajo:
			if boton == self.mapa.modificador:
				self._modificadores.discard(identificador)
			accion = self._pulsados.pop(clave, None)
			return [(accion, False)] if accion is not None else []
		if contexto == acciones.MENU:
			capa = CAPA_MENU
		else:
			if boton == self.mapa.modificador:
				self._modificadores.add(identificador)
				return []
			capa = CAPA_JUEGO_2 if identificador in self._modificadores else CAPA_JUEGO
		accion = self.mapa.accion_de(capa, boton)
		if accion is None:
			return []
		self._pulsados[clave] = accion
		return [(accion, True)]

	def soltar_todo(self) -> list[tuple[str, bool]]:
		"""Suelta lo que estuviera pulsado (se abre un menú con un botón aún apretado)."""
		salida = [(accion, False) for accion in self._pulsados.values()]
		self._pulsados.clear()
		self._repeticion.clear()
		return salida

	# ── Palancas ──

	def _palanca(self, lado: str) -> tuple[float, float]:
		"""(x, y) de una palanca con la zona muerta aplicada: x a la derecha, y hacia delante. La del mando que más se mueve."""
		mejor = (0.0, 0.0)
		for ejes in self._ejes.values():
			x, y = zona_muerta(ejes[lado + "x"], -ejes[lado + "y"], self.opciones["zona_muerta"])
			if math.hypot(x, y) > math.hypot(*mejor):
				mejor = (x, y)
		return mejor

	def ejes(self, contexto: str = acciones.JUEGO) -> tuple[float, float, float, tuple[float, float] | None]:
		"""(avance, lateral, giro, mirada) para ``Sesion.analogico``, cada uno de −1 a 1.

		- avance: palanca izquierda adelante (+) o atrás (−).
		- giro o lateral: palanca izquierda a los lados, según la opción
		  ``palanca_izquierda``; con el modificador mantenido es siempre paso
		  lateral (su «segunda función»).
		- mirada: ``(x, y)`` de la palanca derecha (x a la derecha, y hacia
		  delante) solo con ``palanca_derecha = "analogica"``; None si está
		  en reposo o si la palanca se traduce a acciones ``mirar_*``.

		En un menú todo es cero: allí las palancas mueven el menú.
		"""
		if contexto != acciones.JUEGO or not self._mandos:
			return 0.0, 0.0, 0.0, None
		lx, ly = self._palanca("l")
		rx, ry = self._palanca("r")
		lateral = giro = 0.0
		if self.opciones["palanca_izquierda"] == "lateral" or self.modificador_pulsado:
			lateral = lx
		else:
			giro = lx
		mirada = None
		modo = self.opciones["palanca_derecha"]
		if modo == "giro":
			giro = max(-1.0, min(1.0, giro + rx))
		elif modo == "analogica" and (rx or ry):
			mirada = (rx, ry)
		return ly, lateral, giro, mirada

	def actualizar(self, dt: float, contexto: str = acciones.JUEGO) -> list[tuple[str, bool]]:
		"""Lo que las palancas convierten en acciones; se llama una vez por fotograma.

		En un menú, la palanca izquierda mueve el cursor con repetición al
		mantenerla. Jugando, la palanca derecha dice qué hay en la dirección
		a la que se empuja (una vez por dirección, hasta que vuelve al centro
		o cambia de sector).
		"""
		if not self._mandos:
			self._repeticion.clear()
			self._sector = None
			return []
		umbral = self.opciones["umbral_palanca"]
		salida: list[tuple[str, bool]] = []
		if contexto == acciones.MENU:
			self._sector = None
			lx, ly = self._palanca("l")
			vertical = abs(ly) >= umbral and abs(ly) >= abs(lx)
			horizontal = abs(lx) >= umbral and not vertical
			if self._repetir("vertical", vertical, dt):
				salida += _toque("menu_arriba" if ly > 0 else "menu_abajo")
			if self._repetir("horizontal", horizontal, dt):
				salida += _toque("menu_derecha" if lx > 0 else "menu_izquierda")
			return salida
		self._repeticion.clear()
		if self.opciones["palanca_derecha"] != "mirar":
			self._sector = None
			return salida
		rx, ry = self._palanca("r")
		modulo = math.hypot(rx, ry)
		if modulo >= umbral:
			sector = round(math.degrees(math.atan2(rx, ry)) / 90.0) % 4
			if sector != self._sector:
				self._sector = sector
				salida += _toque(_SECTORES_MIRAR[sector])
		elif modulo < umbral * 0.5:
			self._sector = None
		return salida

	def _repetir(self, nombre: str, activo: bool, dt: float) -> bool:
		"""True cuando toca «pulsar»: al empezar y luego cada cierto tiempo mientras se mantiene."""
		if not activo:
			self._repeticion.pop(nombre, None)
			return False
		restante = self._repeticion.get(nombre)
		if restante is None:
			self._repeticion[nombre] = float(self.opciones["repeticion_inicial"])
			return True
		restante -= dt
		if restante > 0:
			self._repeticion[nombre] = restante
			return False
		self._repeticion[nombre] = float(self.opciones["repeticion"])
		return True

	# ── Vibración ──

	def vibrar(self, grave: float, agudo: float, ms: int) -> bool:
		"""Hace vibrar los mandos: motores grave y agudo de 0 a 1, durante ``ms`` milisegundos.

		Devuelve si algún mando vibró. La fuerza se multiplica por la opción
		``fuerza_vibracion``; con ``vibracion`` desactivada no hace nada.
		"""
		if not self.opciones["vibracion"] or ms <= 0:
			return False
		fuerza = float(self.opciones["fuerza_vibracion"])
		grave = max(0.0, min(1.0, grave * fuerza))
		agudo = max(0.0, min(1.0, agudo * fuerza))
		hecho = False
		for mando in self._mandos.values():
			vibrador = getattr(mando, "rumble", None)
			if not callable(vibrador):
				continue
			try:
				vibrador(grave, agudo, int(ms))
				hecho = True
			except pygame.error:
				log.debug("El mando no pudo vibrar.", exc_info=True)
		return hecho

	def parar_vibracion(self) -> None:
		"""Corta la vibración en marcha (al pausar o al salir)."""
		for mando in self._mandos.values():
			parar = getattr(mando, "stop_rumble", None)
			if callable(parar):
				try:
					parar()
				except pygame.error:
					log.debug("No se pudo parar la vibración.", exc_info=True)

	# ── Textos ──

	def nombre_boton(self, boton: str) -> str:
		"""Nombre corto de un botón en el mando que se está usando."""
		return nombre_boton(boton, self.familia)

	def frase_de(self, accion: str, contexto: str = acciones.JUEGO) -> str:
		"""Cómo se hace una acción con el mando que se está usando; cadena vacía si no tiene botón."""
		return self.mapa.frase_de(accion, contexto, self.familia)

	def a_dict(self) -> dict[str, Any]:
		"""El mapa de botones, para guardarlo."""
		return self.mapa.a_dict()

	def cerrar(self) -> None:
		"""Para la vibración y suelta los mandos."""
		self.parar_vibracion()
		for identificador in list(self._mandos):
			self.desconectar(identificador, anunciar=False)


def _toque(accion: str) -> list[tuple[str, bool]]:
	"""Una pulsación completa (pulsar y soltar) de una acción de un solo toque."""
	return [(accion, True), (accion, False)]


# ── Decir botones en vez de teclas ───────────────────────────────────────────

_VERBOS = r"(?P<verbo>\b(?:[Pp]uls(?:a|ar|as|ando|es)|[Cc]on|[Uu]sa|[Uu]sar|[Mm]antén(?: pulsad[ao])?|[Tt]oca))"
_FIN = r"(?![\wáéíóúñÁÉÍÓÚÑ])"
# Las acciones de moverse van en la palanca, que no es un botón del mapa.
_PALANCA = {
	"avanzar": N_("la palanca izquierda hacia delante"),
	"retroceder": N_("la palanca izquierda hacia atrás"),
	"menu_arriba": N_("la cruceta arriba"),
	"menu_abajo": N_("la cruceta abajo"),
}


def _nombres_hablados(comb: str) -> list[str]:
	"""Formas en que una frase puede nombrar una combinación: «Control izquierdo» también es «Control»."""
	nombre = nombre_combinacion(comb)
	formas = [nombre]
	if comb in ("control_izquierdo", "control_derecho"):
		formas.append(_("Control"))
	if comb.startswith("mayus+"):
		resto = nombre_combinacion(comb[6:])
		formas.append(_("Mayúsculas más {tecla}").format(tecla=resto))
		formas.append(_("Mayúsculas y {tecla}").format(tecla=resto))
	return formas


def textos_mando(
	texto: str,
	mapa_teclado: MapaTeclado,
	mapa_mando: MapaMando,
	familia: str = XBOX,
	contexto: str = acciones.JUEGO,
) -> str:
	"""Cambia en una frase las teclas por los botones del mando que hacen lo mismo.

	«Pulsa C para saber dónde estás» pasa a «Pulsa el botón X para saber
	dónde estás» (o «el botón Cuadrado»). Lo que no tiene botón se deja como
	está, porque el teclado sigue funcionando con el mando conectado.

	Las frases se reconocen por cómo se escriben en español, que es el idioma
	de origen: en otro idioma el texto se devuelve sin tocar.
	"""
	if not texto or not isinstance(texto, str) or idioma_actual() != IDIOMA_ORIGEN:
		return texto
	# nombre hablado (en minúsculas) → frase del botón que hace la misma acción
	sustitutos: dict[str, str] = {}
	for comb, accion in mapa_teclado.a_dict().get(contexto, {}).items():
		frase = mapa_mando.frase_de(accion, contexto, familia)
		if not frase and accion in _PALANCA:
			frase = _(_PALANCA[accion])
		if not frase:
			continue
		for forma in _nombres_hablados(comb):
			sustitutos.setdefault(forma.lower(), frase)
	if not sustitutos:
		return texto
	# Las más largas primero: «Mayúsculas Tabulador» antes que «Tabulador».
	alternativas = "|".join(re.escape(n) for n in sorted(sustitutos, key=len, reverse=True))
	teclas = rf"(?P<tecla>(?i:{alternativas}))"

	def boton(coincidencia: re.Match[str]) -> str | None:
		nombre = coincidencia.group("tecla")
		if not (nombre[0].isupper() or nombre.lower().startswith("flecha")):
			return None  # «con a», «con espacio de sobra»: en minúscula es una palabra, no una tecla
		return sustitutos.get(nombre.lower())

	def con_verbo(coincidencia: re.Match[str]) -> str:
		frase = boton(coincidencia)
		return coincidencia.group(0) if frase is None else f"{coincidencia.group('verbo')} {frase}"

	def con_articulo(coincidencia: re.Match[str]) -> str:
		frase = boton(coincidencia)
		if frase is None:
			return coincidencia.group(0)
		return frase[0].upper() + frase[1:] if coincidencia.group(0)[0].isupper() else frase

	def enlazada(coincidencia: re.Match[str]) -> str:
		frase = boton(coincidencia)
		return coincidencia.group(0) if frase is None else f"{coincidencia.group('nexo')} {frase} para"

	# «pulsa C», «con la tecla B», «usa Mayúsculas Tabulador»
	texto = re.sub(rf"{_VERBOS} (?:(?:la|el|las) )?(?:teclas? )?{teclas}{_FIN}", con_verbo, texto)
	# «la tecla K dice...»
	texto = re.sub(rf"\b(?:[Ll]a|[Ee]l) tecla {teclas}{_FIN}", con_articulo, texto)
	# «pulsa B para el bastón y K para la brújula»
	texto = re.sub(rf"(?<![\wáéíóúñ])(?P<nexo>y|o|ni) (?:la )?{teclas} para{_FIN}", enlazada, texto)
	# Las flechas, dichas en conjunto, son la palanca izquierda (o la cruceta en un menú).
	conjunto = _("la cruceta") if contexto == acciones.MENU else _("la palanca izquierda")
	texto = re.sub(r"\b([Ll])as flechas\b", lambda m: ("L" if m.group(1) == "L" else "l") + conjunto[1:], texto)
	return texto
