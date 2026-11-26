"""Modo sin ventana ni sonido y modo guion del reproductor.

Para qué sirve:

- **Pruebas de proceso real.** El Estudio lanza el reproductor como proceso
  hijo (``app.core.procesos.lanzar_reproductor``) con los mismos argumentos
  de siempre; el hijo hereda el entorno, así que basta con poner antes
  ``APP_SIN_VENTANA=1`` (y, si se quiere, ``APP_GUION``) para que arranque sin
  ventana ni sonido y siga un guion.
- **Diagnóstico.** ``jugar.py --guion fichero.json [paquete ...]`` (o
  ``EntornoLabJugar.exe`` en la versión compilada) ejecuta los pasos del
  guion sin abrir la ventana ni la tarjeta de sonido, sale con un código y
  deja, si se pide, un informe JSON con lo dicho, el estado final, el motor
  de sonido usado (y si cargó el HRTF), los paquetes de sonido y los
  complementos que faltan.

Variables de entorno (todas opcionales; ver ``docs/desarrollo.md``):

=====================  ===============================================================
``APP_SIN_VENTANA=1``  Controladores «dummy» de SDL (sin ventana ni tarjeta), motor de
                       sonido nulo, voz muda que apunta lo dicho y sin mandos. Es el
                       ``Aplicacion(pruebas=True)`` de las pruebas.
``APP_GUION``          Ruta de un guion JSON (como ``--guion``). Implica sin ventana.
``APP_GUION_INFORME``  Dónde escribir el informe JSON (como ``--informe``).
``APP_GUION_MOTOR``    Motor de sonido para el guion (manda sobre la clave ``motor``
                       del guion): ``openal``, ``bass``, ``clasico``, ``estereo`` o
                       ``nulo``. Se abre siempre «en memoria», sin tarjeta.
=====================  ===============================================================

Formato del guion::

	{
	  "motor": "openal",          opcional; en memoria (sin tarjeta de sonido)
	  "plazo": 30,                plazo por defecto de las esperas, en segundos
	  "seguir_tras_fallo": false, por defecto se para en la primera comprobación fallida
	  "al_terminar": "cerrar",    o «seguir»: tras el último paso sigue el bucle hasta que el reproductor salga
	  "pasos": [
	    {"nota": "texto libre, no hace nada"},
	    {"accion": "menu_abajo"},                       una acción (pulsar y soltar)
	    {"tecla": "F4"},                                una tecla por el camino real; "mod": ["ctrl"], "texto": "a"
	    {"escribir": "mesa", "intro": true},            letras en una entrada de texto
	    {"elegir": "Colocar un objeto"},                va a la opción del menú que empieza así y la acepta
	    {"fotogramas": 10},
	    {"segundos": 0.5},
	    {"hasta": "conectado", "plazo": 10},            espera una condición (falla si vence el plazo)
	    {"hasta": "dicho", "texto": "pausa"},
	    {"comprobar": "dicho", "texto": "Hola"},        comprueba ya; "no": true la niega
	    {"salir": true}
	  ]
	}

Condiciones (para ``hasta`` y ``comprobar``): ``conectado``, ``desconectado``,
``partida``, ``sin_partida``, ``fin`` (la última partida ha terminado),
``completada``, ``pausada``, ``dicho`` (``texto``), ``pantalla`` (``texto``:
parte del título de la pantalla de arriba o el nombre de su clase),
``posicion`` (``x``, ``y``, ``planta`` y ``tolerancia``), ``salida`` (el
reproductor ha terminado), ``motor`` (``nombre``), ``hrtf`` (OpenAL con HRTF
activo), ``sin_fallos`` (ningún fotograma ha fallado) y
``sin_complementos_que_faltan``.

Códigos de salida: 0 bien, 2 guion no válido, 3 entorno que no se puede abrir
y 4 alguna comprobación o espera ha fallado.
"""

from __future__ import annotations

import json
import logging
import math
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.i18n import _

log = logging.getLogger(__name__)

VARIABLE_SIN_VENTANA = "APP_SIN_VENTANA"
VARIABLE_GUION = "APP_GUION"
VARIABLE_INFORME = "APP_GUION_INFORME"
VARIABLE_MOTOR = "APP_GUION_MOTOR"

CODIGO_CORRECTO = 0
CODIGO_GUION_NO_VALIDO = 2
CODIGO_ENTORNO = 3
CODIGO_FALLO = 4

PLAZO_DE_SERIE = 30.0
# Tope de cualquier espera: un guion con un plazo disparatado no debe dejar un proceso colgado para siempre.
PLAZO_MAXIMO = 600.0
FOTOGRAMAS_POR_SEGUNDO = 60
MOTORES = ("openal", "bass", "clasico", "estereo", "nulo")
CONDICIONES = (
	"conectado",
	"desconectado",
	"partida",
	"sin_partida",
	"fin",
	"completada",
	"pausada",
	"dicho",
	"pantalla",
	"posicion",
	"salida",
	"motor",
	"hrtf",
	"sin_fallos",
	"sin_complementos_que_faltan",
)
_CLASES_DE_PASO = ("nota", "accion", "tecla", "escribir", "elegir", "fotogramas", "segundos", "hasta", "comprobar", "salir")
_MODIFICADORES = {
	"ctrl": "KMOD_CTRL",
	"control": "KMOD_CTRL",
	"mayus": "KMOD_SHIFT",
	"mayús": "KMOD_SHIFT",
	"shift": "KMOD_SHIFT",
	"alt": "KMOD_ALT",
}
_VERDADERO = ("1", "si", "sí", "true", "verdadero")


class ErrorGuion(ValueError):
	"""El guion no se puede leer o no es válido. El mensaje explica qué falta."""


@dataclass
class Guion:
	"""Un guion ya leído y validado."""

	pasos: list[dict[str, Any]]
	motor: str = ""
	plazo: float = PLAZO_DE_SERIE
	seguir_tras_fallo: bool = False
	al_terminar: str = "cerrar"
	ruta: Path | None = None


@dataclass
class Resultado:
	"""Lo que ha pasado al ejecutar un guion."""

	codigo: int = CODIGO_CORRECTO
	fallos: list[str] = field(default_factory=list)
	pasos: list[dict[str, Any]] = field(default_factory=list)


# ── Variables de entorno ─────────────────────────────────────────────────────


def _activada(nombre: str) -> bool:
	return os.environ.get(nombre, "").strip().casefold() in _VERDADERO


def pedido_sin_ventana() -> bool:
	"""True si el entorno pide arrancar sin ventana ni sonido (``APP_SIN_VENTANA`` o un guion)."""
	return _activada(VARIABLE_SIN_VENTANA) or bool(os.environ.get(VARIABLE_GUION, "").strip())


def preparar_sin_ventana() -> None:
	"""Pone los controladores «dummy» de SDL antes de que se importe pygame: ni ventana ni tarjeta de sonido.

	Se fuerzan (no ``setdefault``): un ``SDL_VIDEODRIVER`` heredado de la
	sesión no debe abrir una ventana en una prueba ni en un diagnóstico.
	"""
	os.environ["SDL_VIDEODRIVER"] = "dummy"
	os.environ["SDL_AUDIODRIVER"] = "dummy"
	os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")


def ruta_de_entorno(nombre: str) -> Path | None:
	"""La ruta de una variable de entorno, o None si no está puesta."""
	valor = os.environ.get(nombre, "").strip()
	return Path(valor).expanduser() if valor else None


# ── Leer y validar ───────────────────────────────────────────────────────────


def _numero(valor: Any, que: str, minimo: float = 0.0) -> float:
	if isinstance(valor, bool) or not isinstance(valor, (int, float)) or not math.isfinite(valor) or valor < minimo:
		raise ErrorGuion(_("«{que}» debe ser un número mayor o igual que {minimo}.").format(que=que, minimo=minimo))
	return float(valor)


def clase_de(paso: dict[str, Any]) -> str:
	"""Qué hace un paso (``accion``, ``hasta``...); «» si no tiene una sola clave de clase."""
	clases = [clase for clase in _CLASES_DE_PASO if clase in paso]
	if len(clases) > 1 and "fotogramas" in clases:
		# Junto a otra clave, «fotogramas» es cuántos se dejan pasar después (en accion, tecla, escribir y elegir).
		clases.remove("fotogramas")
	return clases[0] if len(clases) == 1 else ""


def validar_paso(paso: Any, numero: int) -> dict[str, Any]:
	"""Comprueba un paso y lo devuelve. Lanza ``ErrorGuion`` diciendo qué paso falla."""
	if not isinstance(paso, dict):
		raise ErrorGuion(_("El paso {n} no es un objeto JSON.").format(n=numero))
	clase = clase_de(paso)
	if not clase:
		raise ErrorGuion(
			_("El paso {n} debe tener una sola de estas claves: {claves}.").format(n=numero, claves=", ".join(_CLASES_DE_PASO))
		)
	valor = paso[clase]
	try:
		if clase in ("accion", "tecla", "elegir") and (not isinstance(valor, str) or not valor.strip()):
			raise ErrorGuion(_("«{clase}» necesita un texto.").format(clase=clase))
		if clase == "escribir" and not isinstance(valor, str):
			raise ErrorGuion(_("«escribir» necesita un texto."))
		if "fotogramas" in paso:
			_numero(paso["fotogramas"], "fotogramas", 1)
		if clase == "segundos":
			_numero(valor, "segundos")
		if clase in ("hasta", "comprobar"):
			if valor not in CONDICIONES:
				raise ErrorGuion(
					_("Condición desconocida «{valor}». Las que hay: {lista}.").format(valor=valor, lista=", ".join(CONDICIONES))
				)
			if valor in ("dicho", "pantalla") and not isinstance(paso.get("texto"), str):
				raise ErrorGuion(_("La condición «{valor}» necesita «texto».").format(valor=valor))
			if valor == "posicion":
				_numero(paso.get("x"), "x", -1e9)
				_numero(paso.get("y"), "y", -1e9)
			if valor == "motor" and paso.get("nombre") not in MOTORES:
				raise ErrorGuion(_("La condición «motor» necesita «nombre»: {lista}.").format(lista=", ".join(MOTORES)))
			if "plazo" in paso:
				_numero(paso["plazo"], "plazo")
		if clase == "tecla":
			codigo_tecla(valor)
	except ErrorGuion as error:
		raise ErrorGuion(_("Paso {n}: {error}").format(n=numero, error=error)) from None
	return dict(paso)


def leer_guion(datos: Any, ruta: Path | None = None) -> Guion:
	"""Convierte el JSON ya cargado en un ``Guion``. Lanza ``ErrorGuion``."""
	if isinstance(datos, list):
		datos = {"pasos": datos}
	if not isinstance(datos, dict) or not isinstance(datos.get("pasos"), list):
		raise ErrorGuion(_("El guion debe ser un objeto JSON con la lista «pasos»."))
	motor = str(os.environ.get(VARIABLE_MOTOR, "").strip() or datos.get("motor") or "")
	if motor and motor not in MOTORES:
		raise ErrorGuion(_("Motor de sonido desconocido «{motor}». Los que hay: {lista}.").format(motor=motor, lista=", ".join(MOTORES)))
	plazo = _numero(datos.get("plazo", PLAZO_DE_SERIE), "plazo")
	al_terminar = str(datos.get("al_terminar") or "cerrar")
	if al_terminar not in ("cerrar", "seguir"):
		raise ErrorGuion(_("«al_terminar» debe ser «cerrar» o «seguir»."))
	pasos = [validar_paso(paso, numero) for numero, paso in enumerate(datos["pasos"], start=1)]
	return Guion(pasos, motor, min(plazo, PLAZO_MAXIMO), bool(datos.get("seguir_tras_fallo", False)), al_terminar, ruta)


def cargar_guion(ruta: Path | str) -> Guion:
	"""Lee y valida un guion de un fichero JSON (UTF-8). Lanza ``ErrorGuion``."""
	ruta = Path(ruta)
	try:
		datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
	except OSError as error:
		raise ErrorGuion(_("No se puede leer el guion «{ruta}»: {error}").format(ruta=ruta.name, error=error)) from error
	except json.JSONDecodeError as error:
		raise ErrorGuion(_("El guion «{ruta}» no es JSON válido (línea {linea}).").format(ruta=ruta.name, linea=error.lineno)) from error
	return leer_guion(datos, ruta)


def codigo_tecla(nombre: str) -> int:
	"""El código de pygame de una tecla por su nombre (``F4``, ``RETURN``, ``escape``, ``a``). Lanza ``ErrorGuion``."""
	import pygame

	limpio = str(nombre).strip()
	for candidato in (limpio, limpio.upper(), limpio.lower()):
		codigo = getattr(pygame, "K_" + candidato, None)
		if isinstance(codigo, int):
			return codigo
	raise ErrorGuion(_("Tecla desconocida «{tecla}». Se escribe como en pygame sin «K_»: F4, RETURN, ESCAPE, UP, a.").format(tecla=nombre))


# ── Motor de sonido en memoria ───────────────────────────────────────────────


def poner_motor(app: Any, nombre: str) -> None:
	"""Cambia el motor de sonido de la aplicación por ``nombre`` abierto «en memoria» (sin tarjeta).

	No toca la configuración (``Aplicacion.cambiar_motor`` la repondría si
	fallara, y un guion no debe cambiar las preferencias del usuario). Si el
	motor pedido no arranca, ``crear_motor`` cae al siguiente de la cadena,
	también en memoria; el informe dice cuál quedó.
	"""
	from app.audio.fabrica import crear_motor
	from app.reproductor import ajustes

	opciones = ajustes.opciones_sonido(app.config, memoria=True)
	opciones["motor"] = nombre
	try:
		app.presentador.detener_fuentes(0.0)
		app.motor.cerrar()
	except Exception:  # noqa: BLE001 - el motor nulo de arranque no debería fallar al cerrarse; si falla, se sigue con el nuevo
		log.warning("El motor de sonido de arranque no se cerró limpiamente.", exc_info=True)
	nuevo = crear_motor(opciones, app.banco)
	app.motor = nuevo
	app.presentador.motor = nuevo
	if app.partida is not None:
		app.partida.motor_cambiado()
	log.info("Guion: motor de sonido %s en memoria (pedido %s).", nuevo.nombre, nombre)


# ── Ejecutar ─────────────────────────────────────────────────────────────────


class Ejecutor:
	"""Lleva la aplicación fotograma a fotograma siguiendo el guion."""

	def __init__(self, app: Any, guion: Guion) -> None:
		self.app = app
		self.guion = guion
		self.fotogramas = 0
		self.inicio = time.monotonic()
		self._ultima_partida: Any = None

	# ── Fotogramas ──

	def fotograma(self) -> None:
		"""Un fotograma con el reloj real: la red y los temporizadores avanzan como en el uso normal."""
		import pygame

		app = self.app
		dt = app.reloj.tick(FOTOGRAMAS_POR_SEGUNDO) / 1000.0
		app.paso(dt, pygame.event.get())
		try:
			app.dibujar()
		except Exception:  # noqa: BLE001 - igual que el bucle normal: un fallo al dibujar no para un juego de oído
			log.exception("Fallo al dibujar la pantalla (guion)")
			app.fallos += 1
		self.fotogramas += 1
		self._mirar_partida()

	def _mirar_partida(self) -> None:
		if self.app.partida is not None:
			self._ultima_partida = self.app.partida

	def _fotogramas(self, cuantos: int) -> None:
		for _vuelta in range(max(1, int(cuantos))):
			if not self.app.activa:
				return
			self.fotograma()

	# ── Condiciones ──

	def dicho(self) -> list[tuple[str, str]]:
		"""(texto, canal) de todo lo que ha dicho el reproductor."""
		registro = getattr(self.app.voz, "registro", None) or []
		return [(str(texto), str(canal)) for texto, canal, *_resto in registro]

	def condicion(self, paso: dict[str, Any]) -> bool:
		"""Evalúa la condición de un paso ``hasta`` o ``comprobar`` (con ``no`` la niega)."""
		valor = self._condicion(str(paso.get("hasta") or paso.get("comprobar")), paso)
		return not valor if paso.get("no") else valor

	def _condicion(self, nombre: str, paso: dict[str, Any]) -> bool:
		app = self.app
		partida = app.partida
		ultima = partida if partida is not None else self._ultima_partida
		enlace = app.enlace
		if nombre == "conectado":
			return enlace is not None and bool(enlace.conectado)
		if nombre == "desconectado":
			return enlace is None or not enlace.conectado
		if nombre == "partida":
			return partida is not None
		if nombre == "sin_partida":
			return partida is None
		if nombre == "fin":
			return ultima is not None and bool(ultima.terminado)
		if nombre == "completada":
			return ultima is not None and bool(ultima.terminado) and bool(ultima.completada)
		if nombre == "pausada":
			return partida is not None and bool(partida.pausada)
		if nombre == "dicho":
			buscado = str(paso.get("texto", "")).casefold()
			return any(buscado in texto.casefold() for texto, _canal in self.dicho())
		if nombre == "pantalla":
			cima = app.cima
			if cima is None:
				return False
			buscado = str(paso.get("texto", "")).casefold()
			return buscado == type(cima).__name__.casefold() or buscado in str(cima.titulo_visible() or "").casefold()
		if nombre == "posicion":
			if partida is None:
				return False
			jugador = partida.sesion.jugador
			if paso.get("planta") and str(paso["planta"]) != jugador.planta:
				return False
			tolerancia = float(paso.get("tolerancia", 0.3))
			return math.hypot(jugador.x - float(paso["x"]), jugador.y - float(paso["y"])) <= tolerancia
		if nombre == "salida":
			return not app.activa
		if nombre == "motor":
			return str(app.motor.nombre) == str(paso.get("nombre"))
		if nombre == "hrtf":
			return bool(_estado_motor(app).get("hrtf_activo"))
		if nombre == "sin_fallos":
			return int(app.fallos) == 0
		if nombre == "sin_complementos_que_faltan":
			return not self.complementos_que_faltan()
		raise ErrorGuion(_("Condición desconocida «{valor}».").format(valor=nombre))

	def complementos_que_faltan(self) -> list[str]:
		"""Complementos que usa el entorno en juego (o el pedido por argumento) y no están instalados."""
		from app.reproductor import entornos

		ultima = self.app.partida if self.app.partida is not None else self._ultima_partida
		entorno = getattr(ultima, "entorno", None)
		if entorno is None:
			ruta = getattr(self.app.opciones, "paquete", None)
			if ruta is None:
				return []
			try:
				entorno = entornos.abrir(ruta).entorno
			except entornos.ErrorEntorno:
				return []
		return list(entornos.complementos_que_faltan(entorno, self.app.catalogo))

	# ── Pasos ──

	def paso(self, paso: dict[str, Any]) -> str:
		"""Ejecuta un paso. Devuelve «» si fue bien o el motivo del fallo."""
		app = self.app
		clase = clase_de(paso)
		if clase == "nota":
			return ""
		if clase == "salir":
			app.salir()
			return ""
		if clase == "fotogramas":
			self._fotogramas(int(paso["fotogramas"]))
			return ""
		if clase == "segundos":
			limite = time.monotonic() + min(float(paso["segundos"]), PLAZO_MAXIMO)
			while app.activa and time.monotonic() < limite:
				self.fotograma()
			return ""
		if clase == "hasta":
			return self._hasta(paso)
		if clase == "comprobar":
			if self.condicion(paso):
				return ""
			return _("No se cumple «{condicion}»{detalle}.").format(condicion=paso["comprobar"], detalle=self._detalle(paso))
		if not app.activa:
			return _("El reproductor ya se ha cerrado.")
		if clase == "accion":
			app.inyectar(str(paso["accion"]))
			self._fotogramas(int(paso.get("fotogramas", 1)))
			return ""
		if clase == "tecla":
			app.tecla(codigo_tecla(str(paso["tecla"])), self._mod(paso), str(paso.get("texto", "")))
			self._fotogramas(int(paso.get("fotogramas", 1)))
			return ""
		if clase == "escribir":
			return self._escribir(paso)
		if clase == "elegir":
			return self._elegir(str(paso["elegir"]), int(paso.get("fotogramas", 2)))
		return _("Paso desconocido.")

	def _mod(self, paso: dict[str, Any]) -> int:
		import pygame

		mod = 0
		for nombre in paso.get("mod") or []:
			atributo = _MODIFICADORES.get(str(nombre).casefold())
			if atributo is not None:
				mod |= int(getattr(pygame, atributo))
		return mod

	def _escribir(self, paso: dict[str, Any]) -> str:
		import pygame

		for letra in str(paso["escribir"]):
			self.app.tecla(pygame.K_a if letra.isalpha() else pygame.K_0, 0, letra)
		if paso.get("intro"):
			self.app.tecla(pygame.K_RETURN, 0, "\r")
		self._fotogramas(int(paso.get("fotogramas", 1)))
		return ""

	def _elegir(self, texto: str, fotogramas: int) -> str:
		from app.reproductor.menus import Menu

		cima = self.app.cima
		if not isinstance(cima, Menu):
			return _("Arriba no hay un menú, sino {pantalla}.").format(pantalla=type(cima).__name__)
		if not cima.elegir(texto):
			return _("No hay ninguna opción «{texto}» en el menú «{menu}». Hay: {opciones}.").format(
				texto=texto, menu=cima.titulo, opciones="; ".join(opcion.texto for opcion in cima.opciones)
			)
		self.app.inyectar("menu_aceptar")
		self._fotogramas(fotogramas)
		return ""

	def _hasta(self, paso: dict[str, Any]) -> str:
		plazo = min(float(paso.get("plazo", self.guion.plazo)), PLAZO_MAXIMO)
		limite = time.monotonic() + plazo
		while True:
			if self.condicion(paso):
				return ""
			if not self.app.activa:
				return _("El reproductor se cerró antes de que se cumpliera «{condicion}»{detalle}.").format(
					condicion=paso["hasta"], detalle=self._detalle(paso)
				)
			if time.monotonic() >= limite:
				return _("Pasaron {segundos} s sin que se cumpliera «{condicion}»{detalle}.").format(
					segundos=f"{plazo:g}", condicion=paso["hasta"], detalle=self._detalle(paso)
				)
			self.fotograma()

	@staticmethod
	def _detalle(paso: dict[str, Any]) -> str:
		extra = {clave: valor for clave, valor in paso.items() if clave not in ("hasta", "comprobar", "plazo")}
		return f" ({json.dumps(extra, ensure_ascii=False)})" if extra else ""

	def ejecutar(self) -> Resultado:
		"""Ejecuta todos los pasos. No cierra la aplicación."""
		resultado = Resultado()
		self._mirar_partida()
		# Un primer fotograma: las pantallas iniciales hablan y el enlace con la sala arranca.
		if self.app.activa:
			self.fotograma()
		for numero, paso in enumerate(self.guion.pasos, start=1):
			comienzo = time.monotonic()
			try:
				motivo = self.paso(paso)
			except ErrorGuion as error:
				motivo = str(error)
			resultado.pasos.append(
				{"n": numero, "paso": paso, "correcto": not motivo, "motivo": motivo, "segundos": round(time.monotonic() - comienzo, 3)}
			)
			if motivo:
				texto = _("Paso {n}: {motivo}").format(n=numero, motivo=motivo)
				resultado.fallos.append(texto)
				log.warning("Guion: %s", texto)
				if not self.guion.seguir_tras_fallo:
					break
		if self.guion.al_terminar == "seguir" and not resultado.fallos:
			while self.app.activa:
				self.fotograma()
		resultado.codigo = CODIGO_FALLO if resultado.fallos else CODIGO_CORRECTO
		return resultado

	# ── Informe ──

	def estado_final(self) -> dict[str, Any]:
		"""Lo que hay ahora en el reproductor: pantallas, conexión y la última partida."""
		app = self.app
		cima = app.cima
		estado: dict[str, Any] = {
			"activa": bool(app.activa),
			"codigo_salida": int(app.codigo_salida),
			"pantalla": type(cima).__name__ if cima is not None else "",
			"titulo": str(cima.titulo_visible() or "") if cima is not None else "",
			"pila": [type(pantalla).__name__ for pantalla in app.pila],
			"alias": app.alias,
			"conectado": bool(app.enlace is not None and app.enlace.conectado),
			"estado_conexion": str(getattr(getattr(app.enlace, "cliente", None), "estado_conexion", "") or "sin_sala"),
			"error_inicial": str(app.error_inicial or ""),
			"partida": None,
		}
		partida = app.partida if app.partida is not None else self._ultima_partida
		if partida is not None:
			jugador = partida.sesion.jugador
			estado["partida"] = {
				"en_curso": partida is app.partida,
				"entorno": str(partida.entorno.nombre),
				"actividad": str(partida.nombre_actividad),
				"id_actividad": str(partida.id_actividad),
				"modo": str(partida.modo),
				"recorrido": bool(partida.recorrido),
				"terminado": bool(partida.terminado),
				"completada": bool(partida.completada),
				"pausada": bool(partida.pausada),
				"planta": str(jugador.planta),
				"x": round(float(jugador.x), 3),
				"y": round(float(jugador.y), 3),
				"rumbo": round(float(jugador.rumbo), 1),
				"resultado": partida.resultado if isinstance(partida.resultado, dict) else {},
			}
		return estado


def _estado_motor(app: Any) -> dict[str, Any]:
	"""``motor.estado()`` sin que un motor raro rompa el informe."""
	try:
		estado = dict(app.motor.estado())
	except Exception:  # noqa: BLE001 - es diagnóstico: un motor que no sabe describirse no debe impedir el informe
		log.warning("El motor de sonido no ha dado su estado.", exc_info=True)
		estado = {}
	estado.setdefault("motor", str(getattr(app.motor, "nombre", "")))
	estado.setdefault("pedido", str(getattr(app.motor, "pedido", "") or estado["motor"]))
	estado.setdefault("hrtf_activo", False)
	estado.setdefault("memoria", bool(getattr(app.motor, "memoria", False)))
	return estado


def _paquetes_de_sonido(app: Any) -> list[dict[str, Any]]:
	from app.audio import paquetes

	try:
		lista = paquetes.listar(app.banco)
	except Exception:  # noqa: BLE001 - es diagnóstico: sin la lista, el informe sigue
		log.warning("No se han podido listar los paquetes de sonido.", exc_info=True)
		return []
	claves = ("id", "nombre", "sonidos", "total", "completo", "defecto", "actual")
	return [{clave: paquete.get(clave) for clave in claves} for paquete in lista]


def _motores_disponibles() -> list[dict[str, Any]]:
	from app.audio import fabrica

	try:
		return [
			{"id": motor["id"], "disponible": bool(motor["disponible"]), "motivo": str(motor["motivo"] or "")}
			for motor in fabrica.motores_disponibles()
		]
	except Exception:  # noqa: BLE001 - es diagnóstico
		log.warning("No se han podido comprobar los motores de sonido.", exc_info=True)
		return []


def _sesiones_guardadas() -> list[str]:
	from app.core import paths

	carpeta = paths.ruta_datos() / "sessions"
	return sorted(ruta.name for ruta in carpeta.glob("*.json.gz")) if carpeta.is_dir() else []


def escribir_informe(ruta: Path, informe: dict[str, Any]) -> None:
	"""Escribe el informe JSON (UTF-8, legible). Un fallo al escribir se registra, no cambia el código de salida."""
	try:
		ruta.parent.mkdir(parents=True, exist_ok=True)
		temporal = ruta.with_name(ruta.name + ".tmp")
		temporal.write_text(json.dumps(informe, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
		os.replace(temporal, ruta)
	except OSError:
		log.exception("No se ha podido escribir el informe del guion")


def informe_de_error(error: str, codigo: int) -> dict[str, Any]:
	"""Informe de un guion que ni siquiera ha podido empezar."""
	from app.core.version import APP_VERSION

	return {"version": APP_VERSION, "correcto": False, "codigo": codigo, "fallos": [error], "pasos": [], "dicho": []}


def ejecutar(app: Any, guion: Guion, ruta_informe: Path | None = None) -> int:
	"""Sigue el guion con la aplicación ya creada, la cierra y devuelve el código de salida.

	La aplicación se cierra SIEMPRE antes de escribir el informe: así la
	sesión grabada ya está en ``data/sessions`` y el informe la nombra.
	"""
	from app.core.version import APP_VERSION

	comienzo = time.monotonic()
	if guion.motor:
		poner_motor(app, guion.motor)
	ejecutor = Ejecutor(app, guion)
	try:
		resultado = ejecutor.ejecutar()
	except Exception as error:  # noqa: BLE001 - un fallo del propio guion se cuenta en el informe y el reproductor se cierra con orden
		log.exception("Fallo al ejecutar el guion")
		resultado = Resultado(CODIGO_FALLO, [_("Fallo inesperado: {error}").format(error=error)])
	estado = ejecutor.estado_final()
	sonido = _estado_motor(app)
	faltan = ejecutor.complementos_que_faltan()
	dicho = [{"texto": texto, "canal": canal} for texto, canal in ejecutor.dicho()]
	paquetes_sonido = _paquetes_de_sonido(app)
	catalogo = app.catalogo
	app.cerrar_todo()
	codigo = resultado.codigo
	if codigo == CODIGO_CORRECTO and int(app.codigo_salida) == CODIGO_ENTORNO:
		codigo = CODIGO_ENTORNO
	if resultado.fallos:
		log.warning("Guion terminado con %d fallos (código %d).", len(resultado.fallos), codigo)
	else:
		log.info("Guion terminado sin fallos en %d fotogramas.", ejecutor.fotogramas)
	if ruta_informe is not None:
		escribir_informe(
			ruta_informe,
			{
				"version": APP_VERSION,
				"guion": str(guion.ruta.name) if guion.ruta is not None else "",
				"correcto": not resultado.fallos and codigo == CODIGO_CORRECTO,
				"codigo": codigo,
				"fallos": resultado.fallos,
				"pasos": resultado.pasos,
				"fotogramas": ejecutor.fotogramas,
				"fallos_de_fotograma": int(app.fallos),
				"segundos": round(time.monotonic() - comienzo, 2),
				"dicho": dicho,
				"estado_final": estado,
				"sonido": sonido,
				"motores_disponibles": _motores_disponibles(),
				"paquetes_sonido": paquetes_sonido,
				"complementos": {
					"instalados": len(catalogo.complementos()),
					"objetos": len(catalogo.objetos()),
					"faltan": faltan,
				},
				"sesiones": _sesiones_guardadas(),
			},
		)
	return codigo
