"""Opciones del reproductor: todo se cambia en caliente y se guarda en la configuración compartida.

Los menús de aquí solo escriben preferencias (``app.establecer``); quien las
aplica es la aplicación, que está suscrita a la configuración. Así da igual
que una preferencia la cambie este menú, el Estudio o un perfil de alumno al
cargarse: el efecto es el mismo y se oye al momento, también a mitad de
partida. El fichero es el mismo que usa el Estudio.

Cada opción dice su valor al llegar a ella, se cambia con izquierda y derecha
y explica para qué sirve con la ayuda. Las preferencias de juego (movimiento,
direcciones, detalle y estilo) se apuntan además en el perfil del alumno.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Any

import pygame

from app.audio import paquetes
from app.audio.fabrica import motores_disponibles, nombre_motor
from app.core import i18n
from app.core.i18n import _, separador_decimal
from app.entrada import acciones, mando, teclado
from app.reproductor import textos
from app.reproductor.menus import SONIDO_ERROR, Menu, Opcion, Pantalla, confirmar

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)

Nombres = Callable[[Any], str]


# ── Constructores de opciones ────────────────────────────────────────────────


def _cabezas() -> list[str]:
	"""Perfiles de cabeza de OpenAL Soft; solo el integrado si ese motor no se puede cargar en este equipo."""
	try:
		from app.audio.motor_openal import cabezas_disponibles

		return list(cabezas_disponibles())
	except ImportError, OSError:
		log.warning("No se pudieron listar los perfiles de cabeza.", exc_info=True)
		return [""]


def _nombre_cabeza(valor: Any) -> str:
	try:
		from app.audio.motor_openal import nombre_cabeza

		return nombre_cabeza(str(valor or ""))
	except ImportError, OSError:
		return str(valor or _("la integrada"))


def _si_no(valor: Any) -> str:
	return _("sí") if valor else _("no")


def opcion_ciclo(
	app: Aplicacion,
	clave: str,
	etiqueta: str,
	valores: Sequence[Any] | Callable[[], Sequence[Any]],
	nombre: Nombres,
	ayuda: str = "",
	al_cambiar: Callable[[Any], Any] | None = None,
) -> Opcion:
	"""Una opción que recorre una lista cerrada de valores con izquierda y derecha."""

	def lista() -> list[Any]:
		return list(valores() if callable(valores) else valores)

	def texto() -> str:
		return f"{etiqueta}: {nombre(app.preferencia(clave))}"

	def ajustar(delta: int) -> Any:
		posibles = lista()
		if not posibles:
			return None
		actual = app.preferencia(clave)
		indice = posibles.index(actual) if actual in posibles else 0
		nuevo = posibles[(indice + delta) % len(posibles)]
		if al_cambiar is not None:
			return al_cambiar(nuevo)
		app.establecer(clave, nuevo)
		return None

	return Opcion(texto, ajuste=ajustar, ayuda=ayuda)


def opcion_numero(
	app: Aplicacion,
	clave: str,
	etiqueta: str,
	minimo: float,
	maximo: float,
	paso: float,
	formato: Nombres,
	ayuda: str = "",
	entero: bool = False,
	tras_cambiar: Callable[[], None] | None = None,
) -> Opcion:
	"""Una opción numérica con mínimo, máximo y paso. El guardado se agrupa (se cambia muchas veces seguidas)."""

	def texto() -> str:
		return f"{etiqueta}: {formato(app.preferencia(clave))}"

	def ajustar(delta: int) -> None:
		actual = float(app.preferencia(clave, minimo) or 0.0)
		nuevo = max(minimo, min(maximo, round(actual + delta * paso, 4)))
		app.establecer(clave, int(round(nuevo)) if entero else float(nuevo), diferido=True)
		if tras_cambiar is not None:
			tras_cambiar()

	return Opcion(texto, ajuste=ajustar, ayuda=ayuda)


def opcion_si_no(app: Aplicacion, clave: str, etiqueta: str, ayuda: str = "") -> Opcion:
	"""Una opción de activar o desactivar."""

	def ajustar(_delta: int) -> None:
		app.establecer(clave, not bool(app.preferencia(clave, False)))

	return Opcion(lambda: f"{etiqueta}: {_si_no(app.preferencia(clave, False))}", ajuste=ajustar, ayuda=ayuda)


def _por_ciento(valor: Any) -> str:
	return _("{n} por ciento").format(n=round(float(valor or 0.0) * 100))


def _decimal(valor: float, cifras: int = 1) -> str:
	return f"{float(valor):.{cifras}f}".replace(".", separador_decimal())


# ── Sonido ───────────────────────────────────────────────────────────────────


def _etiqueta_bus(bus: str) -> str:
	return {
		"maestro": _("Volumen general"),
		"efectos": _("Volumen de los efectos"),
		"pasos": _("Volumen de tus pasos"),
		"ambiente": _("Volumen del ambiente"),
		"ayudas": _("Volumen de las ayudas"),
		"interfaz": _("Volumen de los menús"),
		"musica": _("Volumen de la música"),
		"voz": _("Volumen de las voces grabadas"),
	}[bus]


def opcion_motor(app: Aplicacion) -> Opcion:
	"""Motor de sonido: cambia en caliente y, si el elegido no arranca, se vuelve al anterior y se dice por qué."""

	def valores() -> list[str]:
		return [m["id"] for m in motores_disponibles() if m["id"] != "nulo" and m["disponible"]]

	def cambiar(nuevo: str) -> bool:
		# El cambio lo hace la aplicación al enterarse de la preferencia, y lo dice ella (también si falla).
		app.establecer("sonido.motor", nuevo)
		return True

	return opcion_ciclo(
		app,
		"sonido.motor",
		_("Motor de sonido"),
		valores,
		lambda valor: nombre_motor(str(valor)),
		_("Binaural para auriculares, clásico, estéreo simple o BASS. Si el que eliges no funciona en este equipo, se vuelve al anterior."),
		al_cambiar=cambiar,
	)


def opcion_paquete(app: Aplicacion) -> Opcion:
	"""Paquete de sonidos: se cambia en caliente; aceptar hace sonar una muestra del elegido."""

	def disponibles() -> list[dict]:
		return paquetes.listar(app.banco)

	def actual() -> dict:
		elegido = app.banco.paquete_actual()
		return next((p for p in disponibles() if p["id"] == elegido), {"id": elegido, "nombre": elegido})

	def ajustar(delta: int) -> None:
		lista = disponibles()
		if not lista:
			return
		ids = [p["id"] for p in lista]
		indice = ids.index(app.banco.paquete_actual()) if app.banco.paquete_actual() in ids else 0
		nuevo = ids[(indice + delta) % len(ids)]
		if paquetes.elegir(nuevo, app.config, app.banco):
			# Para que el cambio se oiga ya en este mismo menú, sin esperar al siguiente fotograma.
			app.presentador.recargar_sonidos()

	def escuchar() -> None:
		app.callar()
		paquetes.escuchar(app.banco.paquete_actual(), app.motor, app.banco)

	return Opcion(
		lambda: _("Paquete de sonidos: {nombre}").format(nombre=actual().get("nombre", "")),
		accion=escuchar,
		ajuste=ajustar,
		ayuda=lambda: paquetes.describir(actual()) + " " + _("Aceptar hace sonar una muestra."),
		callado=True,
	)


def abrir_sonido(app: Aplicacion) -> Menu:
	"""Opciones de sonido."""

	def dispositivos() -> list[str]:
		try:
			return ["", *[str(d) for d in app.motor.dispositivos()]]
		except OSError, RuntimeError:
			log.warning("No se pudieron listar las salidas de sonido.", exc_info=True)
			return [""]

	def centrar() -> None:
		if app.cabeza is None:
			app.sonar(SONIDO_ERROR)
			app.decir(_("El seguimiento de cabeza no está activado."), True)
			return
		app.cabeza.centrar()
		app.decir(_("Centrado: la postura de ahora es mirar al frente."), True)

	def lista() -> list[Opcion]:
		opciones = [
			opcion_motor(app),
			opcion_ciclo(
				app,
				"sonido.modo_salida",
				_("Oigo por"),
				("auriculares", "altavoces"),
				lambda valor: _("auriculares") if valor == "auriculares" else _("altavoces"),
				_("Con auriculares los sonidos se sitúan a tu alrededor. Con altavoces solo a izquierda y derecha."),
			),
			opcion_ciclo(
				app,
				"sonido.perfil_hrtf",
				_("Perfil de cabeza"),
				_cabezas,
				_nombre_cabeza,
				_(
					"Cada persona sitúa mejor los sonidos con una cabeza distinta. Prueba varias con auriculares. Solo vale para el motor binaural."
				),
			),
			opcion_paquete(app),
			opcion_ciclo(
				app,
				"sonido.dispositivo",
				_("Salida de sonido"),
				dispositivos,
				lambda valor: str(valor) if valor else _("la de Windows"),
				_("Por dónde suena el juego: la salida de Windows u otra concreta."),
			),
		]
		for bus in ("maestro", "efectos", "pasos", "ambiente", "ayudas", "interfaz", "musica", "voz"):
			opciones.append(
				opcion_numero(app, f"sonido.volumen_{bus}", _etiqueta_bus(bus), 0.0, 1.0, 0.05, _por_ciento, _("De 0 a 100 por ciento."))
			)
		opciones += [
			opcion_si_no(
				app,
				"sonido.proteccion_auditiva",
				_("Protección auditiva"),
				_("Pone un techo al volumen y hace que las subidas sean graduales. Conviene dejarla activada con auriculares."),
			),
			opcion_si_no(
				app,
				"sonido.refuerzo_detras",
				_("Apagar un poco lo que suena detrás"),
				_("Ayuda a distinguir si un sonido viene de delante o de detrás."),
			),
			opcion_si_no(
				app,
				"sonido.seguimiento_cabeza",
				_("Seguimiento de cabeza"),
				_("Con el programa OpenTrack y una cámara, al girar la cabeza los sonidos se quedan en su sitio."),
			),
			Opcion(_("Centrar el seguimiento de cabeza"), centrar, ayuda=_("Mira al frente y acepta: esa postura pasa a ser «de frente».")),
		]
		return opciones

	menu = Menu(app, _("Sonido"), lista)
	app.abrir(menu)
	return menu


# ── Voz ──────────────────────────────────────────────────────────────────────


def _nombre_detalle(valor: Any) -> str:
	return {
		0: _("0, solo sonidos"),
		1: _("1, lo esencial"),
		2: _("2, normal"),
		3: _("3, todo"),
	}.get(int(valor or 0), str(valor))


SALIDAS_VOZ: tuple[str, ...] = ("automatica", "lector", "sapi", "ninguna")
SONIDO_SIN_VOZ = "interfaz/cerrar"


def nombre_salida_voz(valor: Any) -> str:
	"""Cómo se dice cada salida de voz en la opción «Habla»."""
	return {
		"automatica": _("automática: tu lector de pantalla o, si no hay, la voz de Windows"),
		"lector": _("solo tu lector de pantalla"),
		"sapi": _("siempre la voz de Windows"),
		"ninguna": _("nadie: sin voz"),
	}.get(str(valor), str(valor))


def aviso_sin_voz() -> str:
	"""El aviso que se da (con sonido y por escrito) al elegir que no se hable: qué cambia y cómo deshacerlo."""
	return _(
		"El juego dejará de hablar. Los mensajes se verán abajo en la pantalla, quedarán en el historial "
		"y, si tienes lector de pantalla, irán a la línea braille. Para volver a oír la voz, cambia «Habla» "
		"en Opciones, Voz y braille, o pulsa Control+F12 en cualquier momento."
	)


def opcion_salida_voz(app: Aplicacion) -> Opcion:
	"""«Habla»: automática, solo el lector, siempre SAPI o nadie.

	Al pasar a «nadie» se avisa UNA vez, con un sonido y con el aviso escrito
	en la pantalla (y en el historial). El aviso se dice todavía con la voz que
	había, antes de apagarla: la voz no corta lo que se está diciendo al pasar
	a «ninguna», así que se oye entero.
	"""

	def cambiar(nuevo: str) -> bool | None:
		if nuevo == "ninguna" and app.preferencia("voz.salida") != "ninguna":
			app.sonar(SONIDO_SIN_VOZ)
			app.decir(aviso_sin_voz(), True, "aviso")
			app.establecer("voz.salida", nuevo)
			return True  # ya se ha dicho lo que pasa: el menú no repite la opción encima del aviso
		app.establecer("voz.salida", nuevo)
		return None

	return opcion_ciclo(
		app,
		"voz.salida",
		_("Habla"),
		SALIDAS_VOZ,
		nombre_salida_voz,
		_(
			"Automática: tu lector de pantalla, con su voz y su braille; si no tienes lector, la voz de Windows. "
			"Solo tu lector de pantalla: si no hay ninguno abierto, el juego no habla. "
			"Siempre la voz de Windows: aunque tengas lector. "
			"Nadie: el juego no habla; los mensajes se ven en la pantalla, quedan en el historial y van al braille si hay lector. "
			"Control+F12 vuelve siempre a la voz automática."
		),
		al_cambiar=cambiar,
	)


def restablecer_voz(app: Aplicacion) -> None:
	"""Tecla de emergencia (Control+F12): vuelve a la voz automática desde cualquier pantalla.

	Quien ha elegido «nadie» o «solo el lector» sin tener lector no oye los
	menús, y no podría volver a «Opciones, Voz y braille» a oídas. Esta tecla
	es fija (no se puede reasignar) y no depende de la pantalla abierta.
	"""
	if app.preferencia("voz.salida") == "automatica":
		app.sonar("interfaz/borde")
		app.decir(_("La voz ya está en automática."), True, "aviso")
		return
	if not app.establecer("voz.salida", "automatica"):
		app.sonar(SONIDO_ERROR)
		return
	app.sonar("interfaz/abrir")
	app.decir(_("Voz restablecida: habla tu lector de pantalla o, si no hay, la voz de Windows."), True, "aviso")


def abrir_voz(app: Aplicacion) -> Menu:
	"""Opciones de voz y braille."""

	def voces() -> list[str]:
		try:
			return ["", *app.voz.voces_sapi()]
		except OSError, RuntimeError, AttributeError:
			log.warning("No se pudieron listar las voces de Windows.", exc_info=True)
			return [""]

	def lista() -> list[Opcion]:
		return [
			opcion_salida_voz(app),
			opcion_ciclo(
				app,
				"voz.voz_sapi",
				_("Voz de Windows"),
				voces,
				lambda valor: str(valor) if valor else _("la predeterminada"),
				_("Solo cuenta cuando habla la voz de Windows: con «siempre la voz de Windows», o con la automática si no hay lector."),
			),
			opcion_numero(
				app,
				"voz.velocidad",
				_("Velocidad de la voz de Windows"),
				0,
				100,
				5,
				lambda v: str(int(v or 0)),
				_("De 0 a 100. Solo para la voz de Windows."),
				entero=True,
			),
			opcion_numero(
				app,
				"voz.volumen",
				_("Volumen de la voz de Windows"),
				0,
				100,
				5,
				lambda v: str(int(v or 0)),
				_("De 0 a 100. Solo para la voz de Windows."),
				entero=True,
			),
			opcion_si_no(
				app,
				"voz.braille",
				_("Mensajes en la línea braille"),
				_("Envía cada mensaje también a la línea braille, a través del lector de pantalla."),
			),
			opcion_si_no(
				app,
				"voz.interrumpir",
				_("Un mensaje nuevo corta al anterior"),
				_("Desactívalo si lees en braille o prefieres oír cada mensaje entero."),
			),
			opcion_ciclo(
				app,
				"voz.detalle",
				_("Cuánto cuenta el juego"),
				(0, 1, 2, 3),
				_nombre_detalle,
				_("Con 0 solo hay sonidos. Con 3 se anuncia todo lo que hay cerca. Lo que pides tú se dice siempre."),
			),
			opcion_si_no(
				app, "juego.posicion_menu", _("Decir la posición en los menús"), _("Por ejemplo, «3 de 9» detrás de cada opción.")
			),
		]

	menu = Menu(app, _("Voz y braille"), lista)
	app.abrir(menu)
	return menu


# ── Movimiento ───────────────────────────────────────────────────────────────


def _nombre_modo(valor: Any) -> str:
	return {
		"pasos": _("por pasos"),
		"continuo": _("continuo"),
		"brujula": _("brújula: cada flecha es un punto cardinal"),
		"salas": _("por salas"),
		"aceras": _("por aceras, de novedad en novedad"),
	}.get(str(valor), str(valor))


def _nombre_formato(valor: Any) -> str:
	return {
		"reloj": _("como un reloj: a las tres"),
		"lados": _("por lados: a la derecha"),
		"cardinal": _("puntos cardinales: al este"),
		"grados": _("en grados"),
	}.get(str(valor), str(valor))


def opciones_movimiento(app: Aplicacion) -> list[Opcion]:
	"""Las opciones de movimiento y de cómo se dicen las direcciones."""
	return [
		opcion_ciclo(
			app,
			"juego.modo_movimiento",
			_("Forma de moverse"),
			("pasos", "continuo", "brujula", "salas", "aceras"),
			_nombre_modo,
			_("Por pasos es la recomendada para empezar: cada pulsación es un paso tuyo."),
		),
		opcion_numero(
			app,
			"juego.paso_m",
			_("Longitud del paso"),
			0.25,
			1.5,
			0.05,
			lambda v: _("{n} centímetros").format(n=round(float(v or 0.0) * 100)),
			_("Lo ideal es que sea la de tu paso real: así contar pasos en el juego sirve en el lugar de verdad."),
		),
		opcion_ciclo(
			app,
			"juego.giro_grados",
			_("Cada giro"),
			(15.0, 30.0, 45.0, 90.0),
			lambda v: _("{n} grados").format(n=round(float(v or 0.0))),
			_("Noventa grados es un cuarto de vuelta, lo más fácil en interiores."),
		),
		opcion_numero(
			app,
			"juego.velocidad_ms",
			_("Velocidad al andar seguido"),
			0.3,
			3.0,
			0.1,
			lambda v: _("{n} metros por segundo").format(n=_decimal(float(v or 0.0))),
			_("Para el modo continuo y la palanca del mando. Un paseo normal son 1,2 metros por segundo."),
		),
		opcion_ciclo(
			app,
			"juego.formato_direccion",
			_("Las direcciones se dicen"),
			("reloj", "lados", "cardinal", "grados"),
			_nombre_formato,
			_("Cómo te dice el juego dónde están las cosas."),
		),
		opcion_ciclo(
			app,
			"juego.unidad",
			_("Las distancias se dicen en"),
			("metros", "pasos"),
			lambda v: _("metros") if v == "metros" else _("pasos"),
			_("En pasos se usan los de la longitud que hayas puesto."),
		),
	]


def abrir_movimiento(app: Aplicacion) -> Menu:
	"""Opciones de movimiento."""
	menu = Menu(app, _("Movimiento"), lambda: opciones_movimiento(app))
	app.abrir(menu)
	return menu


# ── Teclado ──────────────────────────────────────────────────────────────────


class PantallaCaptura(Pantalla):
	"""«Pulsa la tecla que quieres usar»: envuelve a ``CapturaTecla`` de ``app/entrada`` y guarda el mapa."""

	def __init__(self, app: Aplicacion, contexto: str, accion: str, vieja: str | None = None) -> None:
		super().__init__(app)
		self.accion_capturada = accion
		self.captura = teclado.CapturaTecla(app.entrada.teclado.mapa, contexto, accion, vieja)
		self._frase_final = ""

	def al_entrar(self) -> None:
		"""Dice qué acción se va a cambiar y cómo se cancela."""
		self.app.decir_menu(self.captura.al_entrar())

	def tecla(self, evento: pygame.event.Event) -> bool:
		"""Todas las teclas son para la captura: ninguna se traduce a acciones."""
		if evento.type not in (pygame.KEYDOWN, pygame.KEYUP):
			return evento.type == pygame.TEXTINPUT
		resultado = self.captura.evento(evento)
		if resultado is None:
			return True
		if self.captura.terminada:
			self._frase_final = resultado.frase
			if resultado.estado == teclado.ASIGNADA:
				self.app.establecer("teclado.mapa", self.app.entrada.teclado.mapa.a_dict())
				self.app.sonar("interfaz/elegir")
			else:
				self.app.sonar("interfaz/atras")
			self.app.cerrar(self)
		else:
			self.app.sonar(SONIDO_ERROR)
			self.app.decir_menu(resultado.frase)
		return True

	def accion(self, accion: str, pulsada: bool) -> bool:
		"""El mando no interviene en la captura de teclas, salvo «atrás», que cancela."""
		if pulsada and accion == "menu_atras":
			self._frase_final = _("Cancelado.")
			self.app.cerrar(self)
		return True

	def al_salir(self) -> None:
		"""Dice el resultado después de que el menú anterior haya vuelto a anunciarse."""
		if self._frase_final:
			self.app.decir(self._frase_final, True)

	def titulo_visible(self) -> str:
		"""Lo que se está cambiando."""
		return _("Pulsa la tecla para: {accion}").format(accion=acciones.nombre_accion(self.accion_capturada))


def abrir_teclas(app: Aplicacion, contexto: str) -> Menu:
	"""Lista de acciones de un contexto con su tecla; al aceptar una se pide la tecla nueva."""

	def cambiar(accion: str, combinacion: str) -> Callable[[], None]:
		def hacer() -> None:
			app.abrir(PantallaCaptura(app, contexto, accion, combinacion))

		return hacer

	def lista() -> list[Opcion]:
		mapa = app.entrada.teclado.mapa
		orden = {a.id: n for n, a in enumerate(acciones.acciones_de(contexto))}
		pares = sorted(mapa.reasignables(contexto), key=lambda par: (orden.get(par[0], 999), par[1]))
		return [
			Opcion(
				f"{acciones.nombre_accion(accion)}: {teclado.nombre_combinacion(combinacion)}",
				cambiar(accion, combinacion),
				ayuda=acciones.ayuda_accion(accion) + " " + _("Acepta para ponerle otra tecla; la que hubiera en ella pasa a esta."),
			)
			for accion, combinacion in pares
		]

	titulo = _("Teclas para jugar") if contexto == acciones.JUEGO else _("Teclas de los menús")
	menu = Menu(app, titulo, lista)
	app.abrir(menu)
	return menu


def abrir_teclado(app: Aplicacion) -> Menu:
	"""Opciones de teclado: reasignar y restablecer."""

	def restablecer() -> None:
		def hacer() -> None:
			app.entrada.teclado.mapa.restablecer()
			app.establecer("teclado.mapa", {})
			app.decir(_("Teclas restablecidas."), True)

		confirmar(app, _("¿Volver a las teclas de serie?"), hacer)

	def decir_cambios() -> None:
		cambios = app.entrada.teclado.mapa.cambios()
		app.decir(" ".join(cambios) if cambios else _("No has cambiado ninguna tecla."), True)

	menu = Menu(
		app,
		_("Teclado"),
		[
			Opcion(
				_("Cambiar las teclas para jugar"),
				lambda: abrir_teclas(app, acciones.JUEGO),
				ayuda=_("Elige una acción y pulsa la tecla que quieres usar."),
			),
			Opcion(
				_("Cambiar las teclas de los menús"),
				lambda: abrir_teclas(app, acciones.MENU),
				ayuda=_("Escape, Intro y F1 no se pueden cambiar."),
			),
			Opcion(_("Oír las teclas que he cambiado"), decir_cambios, ayuda=_("Dice lo que es distinto de las teclas de serie.")),
			Opcion(_("Restablecer las teclas de serie"), restablecer, ayuda=_("Deshace todos los cambios de teclas.")),
		],
	)
	app.abrir(menu)
	return menu


# ── Mando ────────────────────────────────────────────────────────────────────


def _guardar_mando(app: Aplicacion) -> None:
	app.establecer("mando.mapa", app.entrada.mandos.mapa.a_dict())


def abrir_botones(app: Aplicacion, capa: str) -> Menu:
	"""Botones reasignables de una capa del mando; al aceptar uno se elige su acción de una lista."""
	contexto = acciones.MENU if capa == mando.CAPA_MENU else acciones.JUEGO

	def elegir_accion(boton: str) -> Callable[[], None]:
		def abrir() -> None:
			def poner(accion: str) -> Callable[[], None]:
				def hacer() -> None:
					cambio = app.entrada.mandos.mapa.cambiar(capa, boton, accion, app.entrada.mandos.familia)
					if cambio.hecho:
						_guardar_mando(app)
					else:
						app.sonar(SONIDO_ERROR)
					app.cerrar(selector)
					app.decir(cambio.frase, True)

				return hacer

			opciones = [Opcion(a.nombre, poner(a.id), ayuda=a.ayuda) for a in acciones.acciones_de(contexto)]
			opciones.append(Opcion(_("Sin asignar"), poner(acciones.NADA), ayuda=_("El botón no hará nada.")))
			selector = Menu(app, _("Acción para {boton}").format(boton=app.entrada.mandos.nombre_boton(boton)), opciones)
			app.abrir(selector)

		return abrir

	def lista() -> list[Opcion]:
		return [
			Opcion(
				f"{app.entrada.mandos.nombre_boton(boton)}: {acciones.nombre_accion(accion)}",
				elegir_accion(boton),
				ayuda=_("Acepta para elegir otra acción. Si otro botón ya la tenía, se intercambian."),
			)
			for boton, accion in app.entrada.mandos.mapa.reasignables(capa)
		]

	titulos = {
		mando.CAPA_JUEGO: _("Botones para jugar"),
		mando.CAPA_JUEGO_2: _("Botones con la segunda función"),
		mando.CAPA_MENU: _("Botones de los menús"),
	}
	menu = Menu(app, titulos.get(capa, capa), lista)
	app.abrir(menu)
	return menu


def abrir_mando(app: Aplicacion) -> Menu:
	"""Opciones del mando: zona muerta, vibración y botones."""

	def probar() -> None:
		if not app.entrada.mandos.conectado:
			app.decir(_("No hay ningún mando conectado."), True)
			return
		app.haptica.patron("choque")
		app.decir(_("Así vibra un choque."), True)

	def restablecer() -> None:
		def hacer() -> None:
			app.entrada.mandos.mapa.restablecer()
			app.establecer("mando.mapa", {})
			app.decir(_("Botones restablecidos."), True)

		confirmar(app, _("¿Volver a los botones de serie?"), hacer)

	def lista() -> list[Opcion]:
		conectados = app.entrada.mandos.conectados
		estado = _("Mando conectado: {nombre}").format(nombre=", ".join(conectados)) if conectados else _("No hay ningún mando conectado")
		return [
			Opcion(estado, ayuda=_("Sirven los mandos de Xbox y de PlayStation. Se puede conectar y desconectar con el juego abierto.")),
			opcion_numero(
				app,
				"mando.zona_muerta",
				_("Zona muerta de las palancas"),
				0.0,
				0.9,
				0.05,
				_por_ciento,
				_("Recorrido de la palanca que se ignora. Súbela si el personaje se mueve solo."),
			),
			opcion_si_no(
				app,
				"mando.vibracion",
				_("Vibración"),
				_("Un golpe seco al chocar, un pulso suave cerca de un premio, un doble pulso al lograr un objetivo."),
			),
			opcion_numero(
				app,
				"mando.fuerza_vibracion",
				_("Fuerza de la vibración"),
				0.0,
				1.0,
				0.1,
				_por_ciento,
				_("De 0 a 100 por ciento."),
				tras_cambiar=lambda: app.haptica.patron("choque"),
			),
			Opcion(_("Probar la vibración"), probar, ayuda=_("Hace vibrar el mando como en un choque.")),
			Opcion(
				_("Cambiar los botones para jugar"),
				lambda: abrir_botones(app, mando.CAPA_JUEGO),
				ayuda=_("El botón de pausa no se puede cambiar."),
			),
			Opcion(
				_("Cambiar los botones con la segunda función"),
				lambda: abrir_botones(app, mando.CAPA_JUEGO_2),
				ayuda=_("Lo que hace cada botón mientras mantienes el de segunda función."),
			),
			Opcion(
				_("Cambiar los botones de los menús"),
				lambda: abrir_botones(app, mando.CAPA_MENU),
				ayuda=_("Aceptar y atrás no se pueden cambiar."),
			),
			Opcion(_("Restablecer los botones de serie"), restablecer, ayuda=_("Deshace todos los cambios de botones.")),
		]

	menu = Menu(app, _("Mando"), lista)
	app.abrir(menu)
	return menu


# ── Estilo, idioma y pantalla ────────────────────────────────────────────────


def abrir_estilo(app: Aplicacion) -> Menu:
	"""Estilo de presentación e idioma."""

	def idiomas() -> list[str]:
		return ["auto", *i18n.idiomas_disponibles()]

	def lista() -> list[Opcion]:
		return [
			opcion_ciclo(
				app,
				"juego.estilo",
				_("Estilo"),
				textos.ESTILOS,
				lambda valor: textos.nombre_estilo(str(valor)),
				_("Cambia el tono de las frases y las celebraciones, no lo que se aprende. Una actividad puede traer su propio estilo."),
			),
			opcion_ciclo(
				app,
				"general.idioma",
				_("Idioma"),
				idiomas,
				lambda valor: _("el de Windows") if valor == "auto" else i18n.nombre_idioma(str(valor)),
				_("El idioma de los menús y de las frases del juego."),
			),
		]

	menu = Menu(app, _("Estilo e idioma"), lista)
	app.abrir(menu)
	return menu


def abrir_pantalla(app: Aplicacion) -> Menu:
	"""Opciones de la parte visual."""

	def lista() -> list[Opcion]:
		return [
			opcion_si_no(
				app,
				"juego.ver_plano",
				_("Ver el plano mientras juego"),
				_("Dibuja la planta desde arriba, con tu posición. Es para baja visión y para quien te acompaña."),
			),
			opcion_si_no(
				app, "juego.pantalla_negra", _("Pantalla en negro"), _("No se dibuja nada. Todo sigue funcionando igual de oído.")
			),
			opcion_si_no(app, "general.alto_contraste", _("Alto contraste"), _("Blanco y amarillo sobre negro.")),
			opcion_numero(
				app,
				"general.tamano_texto",
				_("Tamaño del texto"),
				75,
				300,
				25,
				lambda v: _("{n} por ciento").format(n=int(v or 100)),
				_("De 75 a 300 por ciento."),
				entero=True,
			),
		]

	menu = Menu(app, _("Pantalla"), lista)
	app.abrir(menu)
	return menu


# ── Menús de opciones ────────────────────────────────────────────────────────


def abrir_opciones(app: Aplicacion) -> Menu:
	"""El menú de opciones completo."""
	menu = Menu(
		app,
		_("Opciones"),
		[
			Opcion(
				_("Sonido"),
				lambda: abrir_sonido(app),
				ayuda=_("Motor de sonido, auriculares o altavoces, paquete de sonidos, volúmenes y protección auditiva."),
			),
			Opcion(_("Voz y braille"), lambda: abrir_voz(app), ayuda=_("Quién habla, a qué velocidad y cuánto cuenta el juego.")),
			Opcion(
				_("Movimiento"), lambda: abrir_movimiento(app), ayuda=_("Cómo te mueves y cómo se dicen las direcciones y las distancias.")
			),
			Opcion(_("Mando"), lambda: abrir_mando(app), ayuda=_("Zona muerta, vibración y botones.")),
			Opcion(_("Teclado"), lambda: abrir_teclado(app), ayuda=_("Cambiar las teclas.")),
			Opcion(_("Estilo e idioma"), lambda: abrir_estilo(app), ayuda=_("Infantil, juvenil o adulto, y el idioma.")),
			Opcion(
				_("Pantalla"),
				lambda: abrir_pantalla(app),
				ayuda=_("El plano, la pantalla en negro, el alto contraste y el tamaño del texto."),
			),
		],
		intro=_("Los cambios se oyen al momento y se guardan solos"),
	)
	app.abrir(menu)
	return menu


def abrir_opciones_rapidas(app: Aplicacion) -> Menu:
	"""Lo que más se retoca a mitad de partida, en un solo menú."""

	def lista() -> list[Opcion]:
		movimiento = opciones_movimiento(app)
		return [
			opcion_numero(
				app, "sonido.volumen_maestro", _etiqueta_bus("maestro"), 0.0, 1.0, 0.05, _por_ciento, _("De 0 a 100 por ciento.")
			),
			opcion_numero(
				app, "sonido.volumen_ambiente", _etiqueta_bus("ambiente"), 0.0, 1.0, 0.05, _por_ciento, _("De 0 a 100 por ciento.")
			),
			opcion_ciclo(
				app,
				"voz.detalle",
				_("Cuánto cuenta el juego"),
				(0, 1, 2, 3),
				_nombre_detalle,
				_("Con 0 solo hay sonidos. Con 3 se anuncia todo lo que hay cerca."),
			),
			movimiento[4],
			movimiento[5],
			opcion_paquete(app),
			Opcion(_("Todas las opciones"), lambda: abrir_opciones(app), ayuda=_("Abre el menú de opciones completo.")),
		]

	menu = Menu(app, _("Opciones rápidas"), lista)
	app.abrir(menu)
	return menu
