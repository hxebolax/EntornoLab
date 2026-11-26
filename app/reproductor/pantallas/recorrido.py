"""Modo recorrido del profesional: menú de edición y salto a cualquier lugar.

El profesional recorre su entorno con el mismo motor que el alumno y, desde
dentro, le pide cosas al Estudio: «coloca un objeto aquí», «pon un premio
aquí», «marca este punto», «mide desde aquí hasta aquí», «pon aquí el
inicio». El reproductor no edita nada: envía una ``peticion`` por la conexión
de supervisión con el punto y el rumbo en que está, el Estudio hace el cambio
y contesta con una ``respuesta`` que aquí se dice en voz alta (y, si el
entorno ha cambiado, se recarga).

Las tres acciones del protocolo (``colocar_aqui``, ``marcar_punto`` y
``medir_desde_aqui``) se concretan con ``datos``:

- ``colocar_aqui`` con ``clase`` = ``objeto`` (y ``objeto`` = tipo del
  catálogo), ``premio`` (y ``nombre``) o ``inicio``. El objeto se elige en
  el catálogo cargado en el propio reproductor (``abrir_catalogo``): los que
  ya hay en el entorno, una búsqueda por nombre o complemento → categoría →
  subcategoría, porque son más de dos mil y una lista plana no se puede
  recorrer a oído;
- ``marcar_punto`` con ``nombre``;
- ``medir_desde_aqui`` con ``fase`` = ``desde`` o ``hasta`` (en la segunda
  viaja también la distancia en línea recta, que el reproductor ya dice).
"""

from __future__ import annotations

import logging
import math
import weakref
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.core.i18n import _, _n, separador_decimal
from app.reproductor.menus import SONIDO_ERROR, EntradaTexto, Menu, Opcion

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)


def _donde(partida: Any) -> dict[str, Any]:
	jugador = partida.sesion.jugador
	return {"planta": jugador.planta, "x": round(jugador.x, 3), "y": round(jugador.y, 3), "rumbo": round(jugador.rumbo % 360.0, 1)}


def pedir(app: Aplicacion, partida: Any, accion: str, **datos: Any) -> int:
	"""Envía una petición al Estudio con el lugar actual. Devuelve su id (0 si no hay conexión)."""
	if app.enlace is None:
		app.sonar(SONIDO_ERROR)
		app.decir(_("No hay conexión con el Estudio: no se puede pedir el cambio."), True, "aviso")
		return 0
	identificador = app.enlace.peticion(accion, **_donde(partida), **datos)
	if app.enlace.conectado:
		app.decir(_("Petición enviada al Estudio."), True)
	else:
		app.decir(_("Ahora no hay conexión con el Estudio. La petición se enviará cuando vuelva."), True, "aviso")
	return identificador


def abrir_edicion(app: Aplicacion, partida: Any) -> Menu:
	"""Abre el menú de edición del modo recorrido."""

	def cerrar_y(funcion: Callable[[], None]) -> Callable[[], None]:
		def hacer() -> None:
			app.cerrar(menu)
			funcion()

		return hacer

	def colocar_objeto() -> None:
		abrir_catalogo(app, partida, al_elegir=lambda: app.cerrar(menu))

	def poner_premio() -> None:
		def aceptado(nombre: str) -> None:
			app.cerrar(menu)
			pedir(app, partida, "colocar_aqui", clase="premio", nombre=nombre or _("Premio"))

		app.abrir(EntradaTexto(app, _("Nombre del premio"), aceptado, inicial=_("Premio"), maximo=60))

	def marcar() -> None:
		def aceptado(nombre: str) -> None:
			app.cerrar(menu)
			pedir(app, partida, "marcar_punto", nombre=nombre or _("Punto"))

		app.abrir(EntradaTexto(app, _("Nombre del punto"), aceptado, inicial=_("Punto"), maximo=60))

	def medir_desde() -> None:
		jugador = partida.sesion.jugador
		partida.medida_desde = (jugador.planta, jugador.x, jugador.y)
		pedir(app, partida, "medir_desde_aqui", fase="desde")
		app.decir(_("Origen de la medida fijado aquí. Ve al otro punto y elige «Medir hasta aquí»."), True)

	def medir_hasta() -> None:
		origen = partida.medida_desde
		jugador = partida.sesion.jugador
		if origen is None:
			app.sonar(SONIDO_ERROR)
			app.decir(_("Primero fija el origen con «Medir desde aquí»."), True)
			return
		if origen[0] != jugador.planta:
			pedir(app, partida, "medir_desde_aqui", fase="hasta")
			app.decir(_("El origen está en otra planta: no se puede medir en línea recta."), True)
			return
		distancia = math.hypot(jugador.x - origen[1], jugador.y - origen[2])
		pedir(app, partida, "medir_desde_aqui", fase="hasta", distancia_m=round(distancia, 2))
		app.decir(_("En línea recta hay {metros} metros.").format(metros=f"{distancia:.2f}".replace(".", separador_decimal())), True)

	def poner_inicio() -> None:
		pedir(app, partida, "colocar_aqui", clase="inicio")

	menu = Menu(
		app,
		_("Menú de edición"),
		[
			Opcion(
				_("Colocar un objeto aquí"),
				colocar_objeto,
				ayuda=_("Elige un objeto del catálogo; el Estudio lo coloca donde estás, mirando hacia donde miras."),
			),
			Opcion(
				_("Poner un premio aquí"),
				poner_premio,
				ayuda=_("El Estudio añade un premio en este punto a la actividad que tenga abierta."),
			),
			Opcion(_("Marcar este punto"), marcar, ayuda=_("Crea una referencia con nombre en este punto.")),
			Opcion(_("Medir desde aquí"), cerrar_y(medir_desde), ayuda=_("Fija el origen de una medida.")),
			Opcion(_("Medir hasta aquí"), cerrar_y(medir_hasta), ayuda=_("Dice la distancia en línea recta desde el origen fijado.")),
			Opcion(
				_("Poner aquí el inicio"), cerrar_y(poner_inicio), ayuda=_("El punto y el rumbo de inicio del entorno pasan a ser estos.")
			),
		],
	)
	app.sonar("interfaz/abrir")
	app.abrir(menu)
	return menu


class _Catalogo:
	"""El catálogo de complementos del reproductor, navegable a oído.

	Con más de dos mil objetos en una veintena de complementos, una lista
	plana sería inmanejable con voz. Se llega a un objeto de dos formas:

	- **buscando** por su nombre (una ``EntradaTexto``; vale cualquier palabra
	  del nombre, la categoría, las etiquetas o la descripción, sin tildes);
	- **por complemento, categoría y subcategoría**, que es como están
	  ordenados en el Estudio. Una categoría pequeña enseña sus objetos
	  directamente; una grande, primero sus subcategorías.

	Además, «Otra vez» repite el último objeto colocado en este recorrido.
	"""

	def __init__(self, app: Aplicacion, partida: Any, al_elegir: Callable[[], None] | None) -> None:
		self.app = app
		self.partida = partida
		self.al_elegir = al_elegir
		self.catalogo = app.catalogo
		self.abiertos: list[Any] = []

	def _abrir(self, pantalla: Any) -> Any:
		self.abiertos.append(pantalla)
		self.app.abrir(pantalla)
		return pantalla

	# ── Elegir y pedir ──

	def colocar(self, definicion: Any) -> Callable[[], None]:
		def hacer() -> None:
			# Se quitan sin hablar los menús del catálogo; el de edición lo cierra quien lo abrió (y el juego dice que sigue).
			for pantalla in reversed(self.abiertos):
				if pantalla in self.app.pila:
					self.app.pila.remove(pantalla)
			self.abiertos.clear()
			if self.al_elegir is not None:
				self.al_elegir()
			_ULTIMOS[self.app] = definicion.tipo
			pedir(self.app, self.partida, "colocar_aqui", clase="objeto", objeto=definicion.tipo, nombre=definicion.nombre)

		return hacer

	def _opcion_objeto(self, definicion: Any, con_categoria: bool = False) -> Opcion:
		texto = definicion.nombre
		if con_categoria and definicion.categoria:
			texto = _("{objeto}, {categoria}").format(
				objeto=definicion.nombre, categoria=self.catalogo.nombre_categoria(definicion.categoria)
			)
		complemento = self.catalogo.complemento(definicion.complemento)
		ayuda = (definicion.descripcion or _("Sin descripción.")).rstrip(".") + ". "
		ayuda += _("Complemento: {complemento}.").format(
			complemento=complemento.nombre if complemento is not None else definicion.complemento
		)
		return Opcion(texto, self.colocar(definicion), ayuda=ayuda)

	# ── Menús ──

	def _usados(self) -> list[Any]:
		"""Las fichas de los tipos de objeto que ya hay en el entorno recorrido, por nombre."""
		tipos = {objeto.tipo for planta in getattr(self.partida.entorno, "plantas", []) for objeto in planta.objetos}
		fichas = [self.catalogo.objeto(tipo) for tipo in tipos]
		return sorted((ficha for ficha in fichas if ficha is not None), key=lambda d: d.nombre.casefold())

	def principal(self) -> Menu:
		opciones: list[Opcion] = []
		complementos = [complemento for complemento in self.catalogo.complementos() if complemento.activo and complemento.objetos]
		usados = self._usados()
		if usados:
			opciones.append(
				Opcion(
					_("Los que ya hay en este entorno, {n}").format(n=len(usados)),
					lambda: self._abrir(Menu(self.app, _("Objetos que ya hay en este entorno"), [self._opcion_objeto(d) for d in usados])),
					ayuda=_("Los tipos de objeto que ya están colocados en este entorno: lo más rápido para poner otro igual."),
				)
			)
		if complementos:
			opciones.append(
				Opcion(
					_("Buscar por nombre"),
					self.buscar,
					ayuda=_("Escribe una o varias palabras del objeto: «mesa», «silla de ruedas», «semáforo»."),
				)
			)
			ultimo = self.catalogo.objeto(_ULTIMOS.get(self.app, ""))
			if ultimo is not None:
				opciones.append(
					Opcion(
						_("Otra vez: {objeto}").format(objeto=ultimo.nombre),
						self.colocar(ultimo),
						ayuda=_("Coloca aquí otro objeto igual que el último."),
					)
				)
			for complemento in complementos:
				opciones.append(
					Opcion(
						_("{complemento}, {n} objetos").format(complemento=complemento.nombre, n=len(complemento.objetos)),
						self._abrir_complemento(complemento),
						ayuda=complemento.descripcion or _("Los objetos de este complemento, por categorías."),
					)
				)
		else:
			opciones.append(Opcion(_("No hay complementos instalados."), ayuda=_("Instala complementos de objetos desde el Estudio.")))
		return self._abrir(
			Menu(
				self.app, _("Colocar un objeto"), opciones, intro=_("Busca el objeto por su nombre o elígelo por complemento y categoría.")
			)
		)

	def buscar(self, inicial: str = "") -> None:
		self._abrir(
			EntradaTexto(
				self.app, _("Buscar un objeto"), self._resultados, inicial=inicial, maximo=60, ayuda=_("Una o varias palabras del objeto.")
			)
		)

	def _resultados(self, texto: str) -> None:
		texto = texto.strip()
		if not texto:
			self.app.decir_menu(_("No has escrito nada."))
			return
		encontrados = self.catalogo.buscar(texto)
		if not encontrados:
			self.app.sonar(SONIDO_ERROR)
			self.app.decir_menu(_("No hay ningún objeto con «{texto}». Prueba con otra palabra.").format(texto=texto))
			return
		opciones: list[Opcion] = []
		if len(encontrados) > MAXIMO_RESULTADOS:
			opciones.append(
				Opcion(
					_("Hay {n} objetos; aquí van los {maximo} primeros. Buscar con más palabras").format(
						n=len(encontrados), maximo=MAXIMO_RESULTADOS
					),
					lambda: self.buscar(texto + " "),
					ayuda=_("Vuelve a la búsqueda con lo escrito, para añadir palabras."),
				)
			)
		opciones += [self._opcion_objeto(definicion, con_categoria=True) for definicion in encontrados[:MAXIMO_RESULTADOS]]
		titulo = _n("{n} objeto con «{texto}»", "{n} objetos con «{texto}»", len(encontrados)).format(n=len(encontrados), texto=texto)
		self._abrir(Menu(self.app, titulo, opciones))

	def _abrir_complemento(self, complemento: Any) -> Callable[[], None]:
		def abrir() -> None:
			categorias = sorted(
				{definicion.categoria for definicion in complemento.objetos if definicion.categoria},
				key=lambda c: self.catalogo.nombre_categoria(c).casefold(),
			)
			opciones = []
			for categoria in categorias:
				cuantos = sum(1 for definicion in complemento.objetos if definicion.categoria == categoria)
				opciones.append(
					Opcion(
						_("{categoria}, {n}").format(categoria=self.catalogo.nombre_categoria(categoria), n=cuantos),
						self._abrir_categoria(complemento, categoria),
						ayuda=_("Los objetos de esta categoría."),
					)
				)
			sueltos = [definicion for definicion in complemento.objetos if not definicion.categoria]
			opciones += [self._opcion_objeto(definicion) for definicion in sorted(sueltos, key=lambda d: d.nombre.casefold())]
			self._abrir(Menu(self.app, complemento.nombre, opciones))

		return abrir

	def _abrir_categoria(self, complemento: Any, categoria: str, subcategoria: str | None = None) -> Callable[[], None]:
		def abrir() -> None:
			objetos = sorted(
				(d for d in complemento.objetos if d.categoria == categoria and (subcategoria is None or d.subcategoria == subcategoria)),
				key=lambda d: d.nombre.casefold(),
			)
			subcategorias = sorted({d.subcategoria for d in objetos if d.subcategoria})
			titulo = self.catalogo.nombre_categoria(categoria)
			if subcategoria is None and len(objetos) > MAXIMO_SIN_SUBCATEGORIAS and len(subcategorias) > 1:
				opciones = [
					Opcion(
						_("{subcategoria}, {n}").format(
							subcategoria=complemento.nombre_subcategoria(sub), n=sum(1 for d in objetos if d.subcategoria == sub)
						),
						self._abrir_categoria(complemento, categoria, sub),
						ayuda=_("Los objetos de esta subcategoría."),
					)
					for sub in subcategorias
				]
				opciones += [self._opcion_objeto(d) for d in objetos if not d.subcategoria]
			else:
				if subcategoria is not None:
					titulo = complemento.nombre_subcategoria(subcategoria)
				opciones = [self._opcion_objeto(d) for d in objetos]
			self._abrir(Menu(self.app, titulo, opciones))

		return abrir


# Resultados de búsqueda que se enseñan como mucho (más no se recorren a oído: mejor afinar la búsqueda).
MAXIMO_RESULTADOS = 40
# Una categoría con más objetos que esto y varias subcategorías se enseña primero por subcategorías.
MAXIMO_SIN_SUBCATEGORIAS = 15
# El último objeto colocado en cada reproductor, para «Otra vez».
_ULTIMOS: weakref.WeakKeyDictionary[Any, str] = weakref.WeakKeyDictionary()


def abrir_catalogo(app: Aplicacion, partida: Any, al_elegir: Callable[[], None] | None = None) -> Menu:
	"""El catálogo de complementos: buscar por nombre o elegir por complemento y categoría; al elegir se pide colocarlo.

	:param al_elegir: se llama al elegir un objeto, antes de enviar la
		petición (el menú de edición lo usa para cerrarse).
	"""
	return _Catalogo(app, partida, al_elegir).principal()


def abrir_lugares(app: Aplicacion, partida: Any) -> Menu:
	"""Lista de plantas y lugares del entorno; al elegir uno se salta a su centro."""

	def saltar(planta_id: str, x: float, y: float) -> Callable[[], None]:
		def hacer() -> None:
			# Se cierran todos los menús abiertos sobre la partida: el salto se oye ya dentro del juego.
			while app.cima is not partida and partida in app.pila:
				app.cerrar()
			partida.saltar_a(planta_id, x, y)

		return hacer

	opciones: list[Opcion] = []
	varias = len(partida.entorno.plantas) > 1
	for planta in partida.entorno.plantas:
		for espacio in planta.espacios:
			if espacio.macizo or len(espacio.contorno) < 3:
				continue
			centro = espacio.centro()
			nombre = espacio.nombre or espacio.id
			texto = _("{lugar}, en {planta}").format(lugar=nombre, planta=planta.nombre or planta.id) if varias else nombre
			opciones.append(
				Opcion(texto, saltar(planta.id, centro[0], centro[1]), ayuda=espacio.descripcion or _("Salta al centro de este lugar."))
			)
	if not opciones:
		opciones.append(Opcion(_("El entorno no tiene lugares.")))
	menu = Menu(app, _("Saltar a un lugar"), opciones)
	app.abrir(menu)
	return menu
