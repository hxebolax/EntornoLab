"""Pantallas habladas del reproductor: menús, mensajes por pasos, entrada de texto y esperas.

Vienen de los menús de Puerto Bravo (mismo autor), adaptados a EntornoLab:

- No miran teclas, sino **acciones** de ``app/entrada`` (``menu_arriba``,
  ``menu_aceptar``...): así valen igual el teclado, la cruceta y la palanca, y
  respetan las teclas y los botones que el alumno haya reasignado. Solo lo que
  no es una acción se atiende como tecla: Inicio y Fin, el salto por inicial
  y, al escribir, las letras.
- Todo se dice: el título al entrar, cada opción al llegar a ella, su
  posición («3 de 9») si se quiere, y su ayuda con F1 o el botón de ayuda.
- Lo visual es un añadido para baja visión y acompañantes: cada pantalla da
  sus líneas (``lineas``) y la aplicación las dibuja en grande. La opción
  elegida se marca con un signo, no solo con el color.

Toda pantalla hereda de ``Pantalla``; para añadir una nueva basta con eso
(ver ``docs/reproductor.md``).
"""

from __future__ import annotations

import logging
import threading
import unicodedata
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

import pygame

from app.core.i18n import N_, _
from app.entrada import acciones

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)

SONIDO_MOVER = "interfaz/mover"
SONIDO_ELEGIR = "interfaz/elegir"
SONIDO_ATRAS = "interfaz/atras"
SONIDO_BORDE = "interfaz/borde"
SONIDO_AJUSTE = "interfaz/ajuste"
SONIDO_ABRIR = "interfaz/abrir"
SONIDO_CERRAR = "interfaz/cerrar"
SONIDO_ERROR = "logro/error"

Texto = str | Callable[[], str]


def _valor(texto: Texto | None) -> str:
	"""Un texto fijo o el que devuelve una función (opciones cuyo texto cambia con su valor)."""
	if texto is None:
		return ""
	return str(texto() if callable(texto) else texto)


def llana(letra: str) -> str:
	"""Una letra en minúscula y sin tilde, para saltar por inicial; la eñe sigue siendo eñe."""
	letra = letra.casefold()
	return letra if letra == "ñ" else unicodedata.normalize("NFD", letra)[:1]


class Pantalla:
	"""Base de todo lo que se pone en la pila de la aplicación.

	``contexto`` dice con qué mapa se traducen las teclas y los botones
	(``menu`` o ``juego``). La aplicación llama, por este orden: ``tecla`` con
	cada evento crudo (si devuelve True, el evento no se traduce a acciones),
	``accion`` con cada acción (si devuelve False, la aplicación atiende las
	comunes: repetir, historial, callar y ayuda) y ``actualizar`` una vez por
	fotograma.
	"""

	contexto: str = acciones.MENU

	def __init__(self, app: Aplicacion) -> None:
		self.app = app

	def al_entrar(self) -> None:
		"""Se llama al abrirla y cada vez que vuelve a quedar arriba de la pila: aquí se dice dónde se está."""

	def al_salir(self) -> None:
		"""Se llama una vez, cuando la pantalla sale de la pila."""

	def tecla(self, evento: pygame.event.Event) -> bool:
		"""Evento crudo de pygame. True si la pantalla lo consume."""
		return False

	def accion(self, accion: str, pulsada: bool) -> bool:
		"""Una acción de ``app/entrada``. True si la pantalla la atiende."""
		return False

	def actualizar(self, dt: float) -> None:
		"""Una vez por fotograma mientras es la pantalla de arriba."""

	def al_perder_foco(self) -> None:
		"""La ventana ha dejado de ser la activa."""

	def texto_ayuda(self) -> str:
		"""Lo que se dice al pedir ayuda (F1 o el botón de ayuda) si la pantalla no tiene nada más concreto."""
		return ""

	def titulo_visible(self) -> str:
		"""Título para la parte visual."""
		return ""

	def lineas(self) -> tuple[list[str], int]:
		"""(líneas de texto, índice de la destacada o −1) para la parte visual."""
		return [], -1

	def dibujar(self, lienzo: Any) -> bool:
		"""Dibujo propio. False para que la aplicación dibuje el título y las líneas."""
		return False


class Opcion:
	"""Una línea de un menú.

	:param texto: texto fijo o función que lo da (si muestra un valor que cambia).
	:param accion: lo que hace al aceptar.
	:param ajuste: función ``(delta)`` para las opciones que se cambian con izquierda y derecha. Si devuelve
		True, el menú no dice el valor nuevo: ya ha hablado ella.
	:param ayuda: explicación que se dice con F1 o el botón de ayuda.
	:param callado: al aceptarla no suena el toque de menú (para opciones que hacen sonar algo).
	"""

	def __init__(
		self,
		texto: Texto,
		accion: Callable[[], None] | None = None,
		ajuste: Callable[[int], Any] | None = None,
		ayuda: Texto | None = None,
		callado: bool = False,
	) -> None:
		self._texto = texto
		self.accion = accion
		self.ajuste = ajuste
		self._ayuda = ayuda
		self.callado = callado

	@property
	def texto(self) -> str:
		"""El texto actual de la opción."""
		return _valor(self._texto)

	@property
	def ayuda(self) -> str:
		"""La explicación de la opción («» si no tiene)."""
		return _valor(self._ayuda)


class Menu(Pantalla):
	"""Un menú hablado: una lista de opciones que se recorre, se acepta y se ajusta.

	:param opciones: lista de ``Opcion`` o función que la da (se vuelve a pedir al entrar y al refrescar).
	:param escapable: si se puede salir con «atrás».
	:param intro: frase que se dice una sola vez, tras el título.
	:param al_cerrar: función que se llama cuando el menú sale de la pila.
	:param con_volver: añade al final la opción «Volver» (todo menú del que se sale con Escape tiene también su opción).
	"""

	def __init__(
		self,
		app: Aplicacion,
		titulo: Texto,
		opciones: Sequence[Opcion] | Callable[[], Sequence[Opcion]],
		escapable: bool = True,
		intro: str | None = None,
		al_cerrar: Callable[[], None] | None = None,
		con_volver: bool = True,
	) -> None:
		super().__init__(app)
		self._titulo = titulo
		self._fuente = opciones
		self.opciones: list[Opcion] = []
		self.i = 0
		self.escapable = escapable
		self.intro = intro
		self.al_cerrar = al_cerrar
		self.con_volver = con_volver
		# Con True, la primera vez que habla no corta lo que se estuviera diciendo (un menú que llega tras un mensaje del juego).
		self.sin_cortar = False
		self.refrescar(hablar=False)

	@property
	def titulo(self) -> str:
		"""El título actual."""
		return _valor(self._titulo)

	def refrescar(self, hablar: bool = True) -> None:
		"""Vuelve a pedir las opciones (tras un cambio que las altera) y, si se pide, lee la actual."""
		self.opciones = list(self._fuente() if callable(self._fuente) else self._fuente)
		if self.escapable and self.con_volver:
			self.opciones.append(
				Opcion(
					_("Volver"), self.volver, ayuda=_("Vuelve atrás. También sirve Escape, o el botón de atrás del mando."), callado=True
				)
			)
		self.i = max(0, min(self.i, len(self.opciones) - 1))
		if hablar:
			self.leer()

	def volver(self) -> None:
		"""Cierra el menú con su sonido."""
		self.app.sonar(SONIDO_ATRAS)
		self.app.cerrar(self)

	def elegir(self, texto: str) -> bool:
		"""Pone el cursor en la primera opción cuyo texto empieza así (pruebas y accesos directos)."""
		for indice, opcion in enumerate(self.opciones):
			if opcion.texto.startswith(texto):
				self.i = indice
				return True
		return False

	# ── Voz ──

	def _posicion(self) -> str:
		if not self.app.posicion_menu or not self.opciones:
			return ""
		return _("{n} de {total}").format(n=self.i + 1, total=len(self.opciones))

	def al_entrar(self) -> None:
		"""Dice el título, la frase de entrada (una vez) y la opción en la que se está."""
		self.refrescar(hablar=False)
		partes = [self.titulo]
		if self.intro:
			partes.append(self.intro)
			self.intro = None
		if self.opciones:
			partes.append(self.opciones[self.i].texto)
			partes.append(self._posicion())
		cortar, self.sin_cortar = not self.sin_cortar, False
		self.app.decir(". ".join(parte.rstrip(". ") for parte in partes if parte) + ".", cortar)

	def leer(self) -> None:
		"""Dice la opción actual y, si está activado, su posición."""
		if not self.opciones:
			return
		partes = [self.opciones[self.i].texto, self._posicion()]
		self.app.decir_menu(". ".join(parte.rstrip(". ") for parte in partes if parte) + ".")

	def al_salir(self) -> None:
		"""Avisa a quien abrió el menú."""
		if self.al_cerrar is not None:
			funcion, self.al_cerrar = self.al_cerrar, None
			funcion()

	# ── Movimiento ──

	def mover(self, nuevo: int) -> None:
		"""Lleva el cursor a otra opción; al pasarse del borde da la vuelta con su sonido."""
		total = len(self.opciones)
		if total == 0:
			return
		if nuevo < 0 or nuevo >= total:
			self.app.sonar(SONIDO_BORDE)
			nuevo %= total
		else:
			self.app.sonar(SONIDO_MOVER)
		self.i = nuevo
		self.leer()

	def _aceptar(self) -> None:
		if not self.opciones:
			return
		opcion = self.opciones[self.i]
		if opcion.accion is not None:
			if not opcion.callado:
				self.app.sonar(SONIDO_ELEGIR)
			opcion.accion()
		elif opcion.ajuste is not None:
			self._ajustar(1)
		else:
			self.leer()

	def _ajustar(self, delta: int) -> None:
		if not self.opciones or self.opciones[self.i].ajuste is None:
			self.app.sonar(SONIDO_BORDE)
			return
		antes = self.opciones[self.i].texto
		hablado = self.opciones[self.i].ajuste(delta)
		if self.app.cima is not self or hablado:
			return  # el ajuste ha abierto otra pantalla o ya ha dicho él lo que ha pasado (un fallo, por ejemplo)
		self.app.sonar(SONIDO_AJUSTE if self.opciones[self.i].texto != antes else SONIDO_BORDE)
		self.app.decir_menu(self.opciones[self.i].texto)

	def accion(self, accion: str, pulsada: bool) -> bool:
		"""Atiende las acciones de menú y la ayuda de la opción."""
		if not pulsada:
			return accion.startswith("menu_")
		if accion == "menu_abajo":
			self.mover(self.i + 1)
		elif accion == "menu_arriba":
			self.mover(self.i - 1)
		elif accion == "menu_aceptar":
			self._aceptar()
		elif accion == "menu_derecha":
			self._ajustar(1)
		elif accion == "menu_izquierda":
			self._ajustar(-1)
		elif accion == "menu_atras":
			if self.escapable:
				self.volver()
			else:
				self.app.sonar(SONIDO_BORDE)
		elif accion == "ayuda":
			self.app.decir_menu(self.texto_ayuda())
		else:
			return False
		return True

	def tecla(self, evento: pygame.event.Event) -> bool:
		"""Inicio, Fin y salto por inicial: lo que no es una acción reasignable."""
		if evento.type != pygame.KEYDOWN or not self.opciones:
			return False
		if self.app.entrada.teclado.mapa.buscar(acciones.MENU, evento.key, int(getattr(evento, "mod", 0))) is not None:
			return False  # la tecla tiene una acción de menú (quizá reasignada por el alumno): manda la acción
		if evento.key == pygame.K_HOME:  # atajo: Inicio (primera opción del menú)
			self.app.sonar(SONIDO_MOVER)
			self.i = 0
			self.leer()
			return True
		if evento.key == pygame.K_END:  # atajo: Fin (última opción del menú)
			self.app.sonar(SONIDO_MOVER)
			self.i = len(self.opciones) - 1
			self.leer()
			return True
		if int(getattr(evento, "mod", 0)) & (pygame.KMOD_CTRL | pygame.KMOD_ALT):
			return False
		letra = llana((getattr(evento, "unicode", "") or "")[:1])
		if not letra or not letra.isalnum():
			return False
		total = len(self.opciones)
		for salto in range(1, total + 1):
			candidata = (self.i + salto) % total
			if llana(self.opciones[candidata].texto[:1]) == letra:
				self.app.sonar(SONIDO_MOVER)
				self.i = candidata
				self.leer()
				return True
		self.app.sonar(SONIDO_BORDE)
		return True

	# ── Ayuda y parte visual ──

	def texto_ayuda(self) -> str:
		"""La ayuda de la opción actual o, si no tiene, cómo se maneja un menú con lo que haya conectado."""
		if self.opciones and self.opciones[self.i].ayuda:
			return self.opciones[self.i].ayuda
		entrada = self.app.entrada
		return _(
			"Menú. {arriba} y {abajo} para moverte, {aceptar} para elegir, {izquierda} y {derecha} para cambiar un valor, {atras} para volver."
		).format(
			arriba=entrada.control_de("menu_arriba", acciones.MENU),
			abajo=entrada.control_de("menu_abajo", acciones.MENU),
			aceptar=entrada.control_de("menu_aceptar", acciones.MENU),
			izquierda=entrada.control_de("menu_izquierda", acciones.MENU),
			derecha=entrada.control_de("menu_derecha", acciones.MENU),
			atras=entrada.control_de("menu_atras", acciones.MENU),
		)

	def titulo_visible(self) -> str:
		"""El título del menú."""
		return self.titulo

	def lineas(self) -> tuple[list[str], int]:
		"""Las opciones, con la actual destacada."""
		return [opcion.texto for opcion in self.opciones], self.i


class Mensaje(Pantalla):
	"""Un texto en varias frases que se oye paso a paso: aceptar avanza, arriba repite, atrás lo salta entero.

	Sirve para explicaciones (ayuda, resultados, avisos largos): quien usa voz
	no puede «releer», así que cada frase espera a que se pida la siguiente.
	"""

	def __init__(self, app: Aplicacion, titulo: str, frases: Sequence[str], al_terminar: Callable[[], None] | None = None) -> None:
		super().__init__(app)
		self.titulo = titulo
		self.frases = [frase for frase in frases if frase]
		self.i = 0
		self.al_terminar = al_terminar
		self._primera = True

	def _decir(self) -> None:
		if not self.frases:
			return
		texto = self.frases[self.i]
		if self._primera:
			self._primera = False
			entrada = self.app.entrada
			texto = _("{titulo}. {texto} {aceptar} para seguir, {atras} para saltarlo.").format(
				titulo=self.titulo.rstrip("."),
				texto=texto,
				aceptar=_mayuscula(entrada.control_de("menu_aceptar", acciones.MENU)),
				atras=entrada.control_de("menu_atras", acciones.MENU),
			)
		if len(self.frases) > 1 and self.app.posicion_menu:
			texto = _("{texto} {n} de {total}.").format(texto=texto, n=self.i + 1, total=len(self.frases))
		self.app.decir_menu(texto)

	def al_entrar(self) -> None:
		"""Dice la frase en la que se está; sin frases, se cierra sola."""
		if self.frases:
			self._decir()
		else:
			self.app.cerrar(self)

	def al_salir(self) -> None:
		"""Avisa a quien lo abrió."""
		if self.al_terminar is not None:
			funcion, self.al_terminar = self.al_terminar, None
			funcion()

	def accion(self, accion: str, pulsada: bool) -> bool:
		"""Avanzar, repetir, retroceder o saltar."""
		if not pulsada:
			return accion.startswith("menu_")
		if accion in ("menu_aceptar", "menu_abajo", "menu_derecha"):
			if self.i + 1 >= len(self.frases):
				self.app.sonar(SONIDO_ELEGIR)
				self.app.cerrar(self)
			else:
				self.i += 1
				self.app.sonar(SONIDO_MOVER)
				self._decir()
		elif accion == "menu_arriba":
			self._decir()
		elif accion == "menu_izquierda":
			self.i = max(0, self.i - 1)
			self._decir()
		elif accion == "menu_atras":
			self.app.sonar(SONIDO_ATRAS)
			self.app.callar()
			self.app.cerrar(self)
		else:
			return False
		return True

	def titulo_visible(self) -> str:
		"""El título del mensaje."""
		return self.titulo

	def lineas(self) -> tuple[list[str], int]:
		"""Todas las frases, con la actual destacada."""
		return list(self.frases), self.i


def _mayuscula(texto: str) -> str:
	return texto[:1].upper() + texto[1:]


_NOMBRES_SIGNOS: dict[str, str] = {
	" ": N_("espacio"),
	".": N_("punto"),
	",": N_("coma"),
	"-": N_("guion"),
	"_": N_("guion bajo"),
	":": N_("dos puntos"),
	"/": N_("barra"),
	"@": N_("arroba"),
}


def nombre_caracter(caracter: str) -> str:
	"""Cómo se dice un carácter al escribirlo («a mayúscula», «espacio», «punto»)."""
	if caracter in _NOMBRES_SIGNOS:
		return _(_NOMBRES_SIGNOS[caracter])
	if caracter.isupper():
		return _("{letra} mayúscula").format(letra=caracter)
	return caracter


class EntradaTexto(Pantalla):
	"""Pide un texto corto (un alias, una dirección) diciendo en voz alta cada carácter.

	Con el teclado se escribe sin más: Intro acepta, Escape cancela, Retroceso
	borra y flecha arriba lee lo escrito. Con el mando se usa una **rueda de
	letras** con las acciones de menú: arriba y abajo recorren las letras,
	derecha escribe la elegida, izquierda borra la última, «mensaje anterior»
	(LB o L1) pone un espacio, «mensaje siguiente» (RB o R1) cambia de grupo
	(minúsculas, mayúsculas, números y signos), «repetir» lee lo escrito,
	aceptar termina y atrás cancela.
	"""

	GRUPOS: tuple[tuple[str, str], ...] = (
		(N_("Minúsculas"), "abcdefghijklmnñopqrstuvwxyz"),
		(N_("Mayúsculas"), "ABCDEFGHIJKLMNÑOPQRSTUVWXYZ"),
		(N_("Números"), "0123456789"),
		(N_("Signos"), ".-_:,/@"),
	)

	def __init__(
		self,
		app: Aplicacion,
		titulo: str,
		al_aceptar: Callable[[str], None],
		inicial: str = "",
		maximo: int = 40,
		ayuda: str = "",
		permitidos: Callable[[str], bool] | None = None,
	) -> None:
		super().__init__(app)
		self.titulo = titulo
		self.al_aceptar: Callable[[str], None] | None = al_aceptar
		self.texto = inicial or ""
		self.maximo = maximo
		self.ayuda = ayuda
		self.permitidos = permitidos
		self.aceptado = False
		self.grupo = 0
		self.letra = 0
		self._eco: str | None = None

	def _leer(self) -> str:
		return self.texto if self.texto else _("Vacío")

	def _instrucciones(self) -> str:
		entrada = self.app.entrada
		if entrada.con_mando:
			return _(
				"Elige cada letra con {arriba} y {abajo} y escríbela con {derecha}. {izquierda} borra. "
				"{espacio} pone un espacio y {grupo} cambia entre minúsculas, mayúsculas, números y signos. "
				"{aceptar} termina y {atras} cancela. También puedes escribir con el teclado."
			).format(
				arriba=entrada.control_de("menu_arriba", acciones.MENU),
				abajo=entrada.control_de("menu_abajo", acciones.MENU),
				derecha=entrada.control_de("menu_derecha", acciones.MENU),
				izquierda=_mayuscula(entrada.control_de("menu_izquierda", acciones.MENU)),
				espacio=_mayuscula(entrada.control_de("historial_anterior", acciones.MENU)),
				grupo=entrada.control_de("historial_siguiente", acciones.MENU),
				aceptar=_mayuscula(entrada.control_de("menu_aceptar", acciones.MENU)),
				atras=entrada.control_de("menu_atras", acciones.MENU),
			)
		return _("Escribe y pulsa Intro. Retroceso borra, flecha arriba lee lo escrito y Escape cancela.")

	def al_entrar(self) -> None:
		"""Dice qué se pide, cómo se escribe y lo que ya hay escrito."""
		self.app.decir_menu(f"{self.titulo}. {self._instrucciones()} {self._leer()}")

	def al_salir(self) -> None:
		"""Entrega el texto si se aceptó."""
		if self.aceptado and self.al_aceptar is not None:
			funcion, self.al_aceptar = self.al_aceptar, None
			funcion(self.texto.strip())

	# ── Escribir ──

	def _poner(self, caracter: str) -> None:
		if len(self.texto) >= self.maximo:
			self.app.sonar(SONIDO_BORDE)
			self.app.decir_menu(_("No cabe más."))
			return
		if self.permitidos is not None and not self.permitidos(caracter):
			self.app.sonar(SONIDO_BORDE)
			return
		self.texto += caracter
		self.app.sonar(SONIDO_MOVER)
		self.app.decir_menu(nombre_caracter(caracter))

	def _borrar(self) -> None:
		if not self.texto:
			self.app.sonar(SONIDO_BORDE)
			self.app.decir_menu(_("Vacío"))
			return
		quitado = self.texto[-1]
		self.texto = self.texto[:-1]
		self.app.sonar(SONIDO_AJUSTE)
		self.app.decir_menu(_("Borrado {caracter}").format(caracter=nombre_caracter(quitado)))

	def _aceptar(self) -> None:
		self.aceptado = True
		self.app.sonar(SONIDO_ELEGIR)
		self.app.cerrar(self)

	def _cancelar(self) -> None:
		self.app.sonar(SONIDO_ATRAS)
		self.app.decir_menu(_("Cancelado."))
		self.app.cerrar(self)

	def tecla(self, evento: pygame.event.Event) -> bool:
		"""El teclado escribe directamente: ninguna tecla se traduce a acciones mientras se escribe."""
		if evento.type == pygame.TEXTINPUT:
			texto = "".join(c for c in str(getattr(evento, "text", "")) if c.isprintable())
			eco, self._eco = self._eco, None
			# La letra suele llegar dos veces (pulsación y texto); una vocal con tilde, solo como texto.
			if texto and texto != eco:
				for caracter in texto:
					self._poner(caracter)
			return True
		if evento.type == pygame.KEYUP:
			return True
		if evento.type != pygame.KEYDOWN:
			return False
		tecla = evento.key
		mod = int(getattr(evento, "mod", 0))
		if tecla in (pygame.K_RETURN, pygame.K_KP_ENTER):
			self._aceptar()
		elif tecla == pygame.K_ESCAPE:
			self._cancelar()
		elif tecla == pygame.K_BACKSPACE:
			self._borrar()
		elif tecla == pygame.K_UP:
			self.app.decir_menu(self._leer())
		elif tecla == pygame.K_F1:
			self.app.decir_menu(self.texto_ayuda())
		else:
			caracter = getattr(evento, "unicode", "") or ""
			if caracter and caracter.isprintable() and not mod & (pygame.KMOD_CTRL | pygame.KMOD_ALT):
				self._eco = caracter
				self._poner(caracter)
		return True

	def accion(self, accion: str, pulsada: bool) -> bool:
		"""La rueda de letras del mando."""
		if not pulsada:
			return True
		letras = self.GRUPOS[self.grupo][1]
		if accion in ("menu_arriba", "menu_abajo"):
			self.letra = (self.letra + (1 if accion == "menu_abajo" else -1)) % len(letras)
			self.app.sonar(SONIDO_MOVER)
			self.app.decir_menu(nombre_caracter(letras[self.letra]))
		elif accion == "menu_derecha":
			self._poner(letras[self.letra])
		elif accion == "menu_izquierda":
			self._borrar()
		elif accion == "historial_anterior":
			self._poner(" ")
		elif accion == "historial_siguiente":
			self.grupo = (self.grupo + 1) % len(self.GRUPOS)
			self.letra = 0
			self.app.sonar(SONIDO_AJUSTE)
			self.app.decir_menu(f"{_(self.GRUPOS[self.grupo][0])}. {nombre_caracter(self.GRUPOS[self.grupo][1][0])}")
		elif accion == "repetir":
			self.app.decir_menu(self._leer())
		elif accion == "menu_aceptar":
			self._aceptar()
		elif accion == "menu_atras":
			self._cancelar()
		elif accion == "ayuda":
			self.app.decir_menu(self.texto_ayuda())
		return True

	def texto_ayuda(self) -> str:
		"""La explicación propia, cómo se escribe y lo escrito."""
		return " ".join(parte for parte in (self.ayuda, self._instrucciones(), self._leer()) if parte)

	def titulo_visible(self) -> str:
		"""Lo que se pide."""
		return self.titulo

	def lineas(self) -> tuple[list[str], int]:
		"""Lo escrito, con un cursor."""
		return [self.texto + "_"], 0


class Espera(Pantalla):
	"""Hace un trabajo lento en un hilo y lo cuenta: «Buscando…», «Sigo buscando…».

	El bucle del juego no se para (el sonido necesita su ``tic`` y el alumno
	puede cancelar con «atrás»). El resultado se entrega en el hilo principal
	con ``al_terminar(resultado)``; si el trabajo falla, llega ``None`` y el
	fallo queda en el registro.
	"""

	CADA = 4.0

	def __init__(
		self,
		app: Aplicacion,
		mensaje: str,
		trabajo: Callable[[], Any],
		al_terminar: Callable[[Any], None],
		mensaje_espera: str = "",
	) -> None:
		super().__init__(app)
		self.mensaje = mensaje
		self.mensaje_espera = mensaje_espera or _("Un momento más.")
		self.al_terminar: Callable[[Any], None] | None = al_terminar
		self._resultado: Any = None
		self._hecho = threading.Event()
		self._t = 0.0
		self._hilo = threading.Thread(target=self._correr, args=(trabajo,), name="reproductor-espera", daemon=True)
		self._lanzado = False

	def _correr(self, trabajo: Callable[[], Any]) -> None:
		try:
			self._resultado = trabajo()
		except Exception:  # noqa: BLE001 - el fallo de un trabajo de fondo se anota y se entrega None
			log.exception("Falló un trabajo en segundo plano del reproductor")
			self._resultado = None
		finally:
			self._hecho.set()

	def al_entrar(self) -> None:
		"""Dice qué se está haciendo y arranca el trabajo (una sola vez)."""
		self.app.decir_menu(self.mensaje)
		if not self._lanzado:
			self._lanzado = True
			self._hilo.start()

	def actualizar(self, dt: float) -> None:
		"""Entrega el resultado cuando está, y entretanto avisa de que sigue."""
		if self._hecho.is_set():
			funcion, self.al_terminar = self.al_terminar, None
			self.app.cerrar(self)
			if funcion is not None:
				funcion(self._resultado)
			return
		self._t += dt
		if self._t >= self.CADA:
			self._t = 0.0
			self.app.decir(self.mensaje_espera, False)

	def accion(self, accion: str, pulsada: bool) -> bool:
		"""«Atrás» cancela: el trabajo termina solo y su resultado se descarta."""
		if pulsada and accion == "menu_atras":
			self.al_terminar = None
			self.app.sonar(SONIDO_ATRAS)
			self.app.decir_menu(_("Cancelado."))
			self.app.cerrar(self)
			return True
		return accion.startswith("menu_")

	def titulo_visible(self) -> str:
		"""Lo que se está haciendo."""
		return self.mensaje


def confirmar(app: Aplicacion, pregunta: str, al_aceptar: Callable[[], None], texto_si: str = "", texto_no: str = "") -> Menu:
	"""Abre un menú de sí o no (el «no» primero: aceptar sin querer no hace nada irreversible)."""

	def si() -> None:
		app.cerrar(menu)
		al_aceptar()

	menu = Menu(
		app,
		pregunta,
		[Opcion(texto_no or _("No"), lambda: menu.volver(), callado=True), Opcion(texto_si or _("Sí"), si)],
		con_volver=False,
	)
	app.abrir(menu)
	return menu
