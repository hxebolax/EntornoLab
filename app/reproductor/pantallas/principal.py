"""Menú principal, elección de alumno (alias), «Mis premios» y «Acerca de».

El menú principal es lo primero que oye el alumno y a donde vuelve siempre:
pocas opciones, siempre las mismas y en el mismo orden, para que se aprenda
de memoria. «Acerca de» sigue el de Puerto Bravo (mismo autor), con la
invitación al café que abre el navegador.
"""

from __future__ import annotations

import logging
import webbrowser
from collections.abc import Callable
from typing import TYPE_CHECKING

from app.core.i18n import _, _n
from app.core.version import ANIO, APP_VERSION, AUTOR, CAFE, FALLOS, LICENCIA, MASTODON, NOMBRE_APLICACION, WEB
from app.entrada import acciones
from app.reproductor import alumno, textos
from app.reproductor.menus import SONIDO_ERROR, EntradaTexto, Menu, Opcion

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)


# ── Menú principal ───────────────────────────────────────────────────────────


def abrir_menu_principal(app: Aplicacion, saludar: bool = True) -> Menu:
	"""Abre el menú principal (la base de la pila: no se puede salir de él con «atrás»)."""
	from app.reproductor.pantallas import aprender, ayuda, conexion, elegir, opciones, tutorial

	def texto_continuar() -> str:
		ultima = app.perfil.ultima if app.perfil is not None else {}
		if ultima.get("entorno"):
			return _("Continuar: {actividad}, en {entorno}").format(
				actividad=ultima.get("nombre") or _("exploración libre"), entorno=ultima.get("entorno")
			)
		return _("Continuar la última actividad")

	def lista() -> list[Opcion]:
		return [
			Opcion(texto_continuar, lambda: elegir.continuar(app), ayuda=_("Vuelve a lo último que jugaste, sin tener que buscarlo.")),
			Opcion(
				_("Elegir entorno"),
				lambda: elegir.abrir_entornos(app),
				ayuda=_("Elige el lugar que quieres recorrer y, después, la actividad."),
			),
			Opcion(_("Mis premios"), lambda: abrir_premios(app), ayuda=_("Las estrellas, las medallas y los objetos que has ganado.")),
			Opcion(
				_("Aprender los sonidos"),
				lambda: aprender.abrir_sonidos(app),
				ayuda=_("Escucha cada sonido del juego con su explicación, por grupos."),
			),
			Opcion(
				_("Practicar los controles"),
				lambda: aprender.abrir_practica(app),
				ayuda=_("Pulsa cualquier tecla o botón y se te dice para qué sirve, sin que pase nada."),
			),
			Opcion(
				_("Tutorial"),
				lambda: tutorial.empezar_tutorial(app),
				ayuda=_("Un recorrido corto y guiado para aprender a moverte, preguntar y encontrar un premio."),
			),
			Opcion(
				_("Opciones"),
				lambda: opciones.abrir_opciones(app),
				ayuda=_("Sonido, voz, movimiento, mando, teclado, estilo, idioma y pantalla."),
			),
			Opcion(
				_("Conectar con mi profesor"),
				lambda: conexion.abrir_conexion(app),
				ayuda=_("Para que tu profesor te acompañe desde su ordenador. Necesitas el código que te diga."),
			),
			Opcion(
				lambda: _("Cambiar de jugador. Ahora juega {alias}").format(alias=alumno.alias_para_mostrar(app.alias)),
				lambda: abrir_quien_eres(app),
				ayuda=_("Cada jugador tiene sus premios y sus preferencias. Se usa un alias, nunca el nombre real."),
			),
			Opcion(
				_("Ayuda"),
				lambda: ayuda.abrir_ayuda(app, acciones.JUEGO),
				ayuda=_("La lista de teclas y botones para recorrer un entorno."),
			),
			Opcion(
				_("Acerca de"),
				lambda: abrir_acerca_de(app),
				ayuda=_("La versión, el autor, la licencia, dónde avisar de un fallo y cómo invitarle a un café."),
			),
			Opcion(
				_("Salir"), lambda: salir(app), ayuda=_("Cierra el juego. Tus premios y tus preferencias quedan guardados."), callado=True
			),
		]

	intro = None
	if saludar:
		saludo = (
			textos.frase("saludo", app.estilo, alias=alumno.alias_para_mostrar(app.alias)) if app.perfil is not None else textos.frase("saludo_sin_alias", app.estilo)
		)
		intro = _("{saludo} Muévete con {arriba} y {abajo} y elige con {aceptar}").format(
			saludo=saludo,
			arriba=app.entrada.control_de("menu_arriba", acciones.MENU),
			abajo=app.entrada.control_de("menu_abajo", acciones.MENU),
			aceptar=app.entrada.control_de("menu_aceptar", acciones.MENU),
		)
	menu = Menu(app, _("{nombre}. Menú principal").format(nombre=NOMBRE_APLICACION), lista, escapable=False, intro=intro)
	decir_donde = menu.al_entrar

	def al_entrar() -> None:
		# Cada vez que se vuelve al menú principal se mira si el Estudio ha cambiado las preferencias compartidas.
		# Con la sala, el Estudio avisa al momento (orden «releer_configuracion»); sin ella, este es el sitio
		# natural: el alumno vuelve aquí entre partida y partida, y releer cuesta una consulta al disco si nada cambió.
		releer = getattr(app, "releer_configuracion", None)
		if callable(releer):
			releer()
		decir_donde()

	menu.al_entrar = al_entrar  # type: ignore[method-assign]
	app.abrir(menu)
	return menu


def salir(app: Aplicacion) -> None:
	"""Se despide y termina el bucle."""
	app.sonar("interfaz/cerrar")
	app.decir(textos.frase("despedida", app.estilo), True)
	app.salir()


# ── Quién juega ──────────────────────────────────────────────────────────────


def abrir_quien_eres(app: Aplicacion) -> Menu:
	"""Elegir un alias de la lista de este equipo, crear uno nuevo o jugar como invitado."""

	def elegir(alias: str) -> Callable[[], None]:
		def hacer() -> None:
			app.cerrar(menu)
			app.poner_alumno(alias)

		return hacer

	def nuevo() -> None:
		def aceptado(texto: str) -> None:
			alias = alumno.normalizar_alias(texto)
			if not alias:
				app.sonar(SONIDO_ERROR)
				app.decir(_("No has escrito nada. Elige otra vez."), True)
				return
			app.cerrar(menu)
			app.poner_alumno(alias)

		app.abrir(
			EntradaTexto(
				app,
				_("Escribe tu alias"),
				aceptado,
				maximo=alumno.LONGITUD_MAXIMA,
				ayuda=_("Un alias es un nombre de juego. No escribas tu nombre y apellidos de verdad."),
			)
		)

	def lista() -> list[Opcion]:
		opciones = [
			Opcion(alias, elegir(alias), ayuda=_("Juega con los premios y las preferencias de este alias."))
			for alias in alumno.listar_alias()
		]
		opciones.append(Opcion(_("Soy nuevo: escribir mi alias"), nuevo, ayuda=_("Un alias es un nombre de juego, no tu nombre real.")))
		opciones.append(
			Opcion(
				_("Jugar como invitado"),
				elegir(alumno.ALIAS_INVITADO),
				ayuda=_("Para probar. Lo que ganes se guarda con el alias «invitado»."),
			)
		)
		return opciones

	menu = Menu(
		app, _("¿Quién juega?"), lista, intro=_("Elige tu alias"), con_volver=app.perfil is not None, escapable=app.perfil is not None
	)
	app.abrir(menu)
	return menu


# ── Mis premios ──────────────────────────────────────────────────────────────


def _resumen_premios(app: Aplicacion) -> str:
	perfil = app.perfil
	if perfil is None:
		return ""
	partes: list[str] = []
	cuenta = perfil.cuenta_premios()
	estrellas = cuenta.get("estrella", 0)
	partes.append(_n("{n} estrella", "{n} estrellas", estrellas).format(n=estrellas))
	medallas = cuenta.get("medalla", 0)
	if medallas:
		partes.append(_n("{n} medalla", "{n} medallas", medallas).format(n=medallas))
	otros = sum(cantidad for tipo, cantidad in cuenta.items() if tipo not in ("medalla", "estrella"))
	if otros:
		partes.append(_n("{n} objeto", "{n} objetos", otros).format(n=otros))
	return _("Tienes {lista}.").format(lista=", ".join(partes))


def abrir_premios(app: Aplicacion) -> Menu:
	"""La colección del alumno: el total y, uno a uno, lo que ha ganado y dónde."""
	perfil = app.perfil

	def lista() -> list[Opcion]:
		if perfil is None or (not perfil.premios and not perfil.actividades):
			return [Opcion(textos.frase("sin_premios", app.estilo))]
		opciones = [Opcion(_resumen_premios(app), ayuda=_("Todo lo que has ganado jugando. Debajo está uno a uno, lo último primero."))]
		for premio in reversed(perfil.premios):
			tipo = str(premio.get("tipo") or "objeto")
			nombre_tipo = {"medalla": _("Medalla"), "estrella": _("Estrella"), "objeto": _("Objeto")}.get(tipo, _("Premio"))
			donde = ", ".join(str(premio.get(clave)) for clave in ("actividad", "entorno") if premio.get(clave))
			texto = f"{nombre_tipo}: {premio.get('nombre', '')}"
			opciones.append(
				Opcion(
					texto,
					ayuda=_("Ganado en {donde}, el {fecha}.").format(
						donde=donde or _("un entorno"), fecha=premio.get("fecha") or _("día sin apuntar")
					),
				)
			)
		return opciones

	menu = Menu(app, _("Mis premios. {alias}").format(alias=alumno.alias_para_mostrar(app.alias)), lista)
	app.sonar("logro/logro" if perfil is not None and perfil.premios else "interfaz/abrir")
	app.abrir(menu)
	return menu


# ── Acerca de ────────────────────────────────────────────────────────────────


def abrir_enlace(app: Aplicacion, enlace: str, nombre: str) -> bool:
	"""Abre un enlace en el navegador y lo dice; si no se puede, dice la dirección."""
	try:
		abierto = bool(webbrowser.open(enlace))
	except OSError, webbrowser.Error:
		log.exception("No se pudo abrir el enlace %s", enlace)
		abierto = False
	if abierto:
		app.decir(_("Abriendo {nombre} en tu navegador.").format(nombre=nombre), True)
	else:
		app.sonar(SONIDO_ERROR)
		app.decir(_("No se pudo abrir el navegador. La dirección es {enlace}").format(enlace=enlace), True)
	return abierto


def abrir_acerca_de(app: Aplicacion) -> Menu:
	"""Versión, autor, licencia, componentes, enlaces y la invitación a un café."""
	menu = Menu(
		app,
		_("Acerca de {nombre}").format(nombre=NOMBRE_APLICACION),
		[
			Opcion(
				_("{nombre}, versión {version}").format(nombre=NOMBRE_APLICACION, version=APP_VERSION),
				ayuda=_("Aprender lugares antes de visitarlos: entornos creados por profesionales y recorridos de oído."),
			),
			Opcion(
				_("Hecho por {autor}").format(autor=AUTOR), ayuda=_("Más abajo están la página del proyecto y dónde avisar de un fallo.")
			),
			Opcion(
				_("Copyright {anio}, {autor}. Licencia {licencia}: software libre que puedes usar, estudiar, compartir y mejorar").format(
					anio=ANIO, autor=AUTOR, licencia=LICENCIA
				),
				ayuda=_("Las licencias de todo lo que acompaña al programa están en la carpeta data, docs, licencias."),
			),
			Opcion(
				_("Invítame a un café si te gusta mi trabajo"),
				lambda: abrir_enlace(app, CAFE, _("la página de donaciones")),
				ayuda=_(
					"EntornoLab es gratis y lo seguirá siendo. Si quieres agradecerlo, aceptar abre la página de donaciones en el navegador."
				),
			),
			Opcion(
				_("Página del proyecto"),
				lambda: abrir_enlace(app, WEB, _("la página del proyecto")),
				ayuda=_("La descripción, el código y las versiones."),
			),
			Opcion(
				_("Avisar de un fallo o proponer una mejora"),
				lambda: abrir_enlace(app, FALLOS, _("la página de incidencias")),
				ayuda=_("Abre en el navegador la página donde se apuntan los fallos."),
			),
			Opcion(
				_("Mastodon del autor"),
				lambda: abrir_enlace(app, MASTODON, _("el perfil de Mastodon")),
				ayuda=_("Abre el perfil del autor en Mastodon."),
			),
			Opcion(
				_(
					"Aviso: es una herramienta educativa y de entrenamiento. No sustituye al aprendizaje en el lugar real con un profesional"
				),
			),
			Opcion(
				_("Incluye OpenAL Soft, con licencia LGPL, como biblioteca aparte en data, bin, openal"),
				ayuda=_("Es el motor de sonido binaural, el que sitúa los sonidos a tu alrededor con auriculares."),
			),
			Opcion(
				_(
					"Incluye BASS, de Un4seen Developments, para el motor de sonido 3D con BASS. BASS no es software libre: "
					"es gratuita solo para uso no comercial"
				),
				ayuda=_(
					"Para un uso comercial hace falta su licencia de pago, o bien elegir otro motor de sonido y borrar bass punto dll."
				),
			),
		],
	)
	app.abrir(menu)
	return menu
