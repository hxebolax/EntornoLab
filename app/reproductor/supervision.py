"""Enlace con la sala del profesor: lo que el reproductor hace con ``ClienteSupervision``.

El cliente (``app/supervision/cliente.py``) vive en su hilo y nunca bloquea el
juego. Este módulo es la parte que corre en el bucle, una vez por fotograma:

- reparte las **órdenes** del profesor a la partida (o, sin partida, dice sus
  mensajes); ``alumno`` (la ficha del Estudio) y ``releer_configuracion`` las
  atiende la aplicación, haya partida o no;
- convierte los **avisos de conexión** en frases que entienda un alumno:
  «Conectado con tu profesor», «Se ha perdido la conexión; puedes seguir
  jugando», «El código no es correcto»;
- envía al Estudio **la voz que oye el alumno** (gancho ``al_hablar``).

Si la sala no está o se cae, se sigue jugando: el cliente reintenta solo y
los eventos ocurridos entretanto se envían al volver.

**Huella de la sala.** En una conexión cifrada, la primera vez se dice la
huella corta de la sala para que alumno y profesor comprueben de viva voz que
es la misma («comparad estas letras»); si un día la sala presenta otra
identificación, no se envía nada y se pregunta antes de aceptarla.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.i18n import _
from app.reproductor.menus import Menu, Opcion
from app.supervision import seguridad
from app.supervision.cliente import ClienteSupervision

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)


def deletrear_huella(huella: str) -> str:
	"""La huella corta (16 caracteres en grupos de cuatro) dicha carácter a carácter, para compararla de viva voz."""
	legible = seguridad.huella_legible(huella)
	grupos = [" ".join(grupo) for grupo in legible.replace("-", " ").split()]
	return ", ".join(grupos)


class Enlace:
	"""La conexión del reproductor con una sala, atendida desde el bucle del juego."""

	def __init__(self, app: Aplicacion, host: str, puerto: int, codigo: str, recorrido: bool = False) -> None:
		self.app = app
		self.host = host
		self.puerto = int(puerto)
		self.recorrido = recorrido
		# Si la sala no tenía huella guardada, es la primera vez: tras conectar se dice para compararla.
		try:
			self._primera_vez = seguridad.AlmacenHuellas().obtener(host, self.puerto) is None
		except OSError:
			self._primera_vez = False
		partida = app.partida
		self.cliente = ClienteSupervision(
			host,
			self.puerto,
			codigo,
			app.alias,
			entorno=partida.entorno.nombre if partida is not None else "",
			actividad=partida.nombre_actividad if partida is not None else "",
			modo=partida.modo if partida is not None else "juego",
			recorrido=recorrido,
			**app.opciones_cliente,
		)
		self._conectado_alguna_vez = False
		self._menu_huella: Menu | None = None

	# ── Ciclo de vida ──

	def iniciar(self) -> None:
		"""Arranca el hilo del cliente y engancha la voz."""
		self.app.voz.al_hablar = self._voz
		self.cliente.iniciar()
		log.info("Supervisión: conectando con la sala (TLS: %s).", "sí" if self.cliente.tls else "no")

	def detener(self) -> None:
		"""Cierra la conexión (enviando antes lo pendiente) y suelta la voz."""
		if self.app.voz.al_hablar == self._voz:
			self.app.voz.al_hablar = None
		try:
			self.cliente.detener()
		except OSError:
			log.warning("La conexión con la sala no se cerró limpiamente.", exc_info=True)

	@property
	def conectado(self) -> bool:
		"""Si ahora mismo hay conexión con la sala."""
		return bool(self.cliente.conectado)

	def descripcion(self) -> str:
		"""Estado de la conexión en una frase, para el menú."""
		if self.cliente.conectado:
			return _("Conectado con {sala}.").format(sala=self.cliente.nombre_sala or self.host)
		if self.cliente.estado_conexion == "rechazado":
			return _("La sala ha rechazado la conexión.")
		return _("Intentando conectar con {sala}.").format(sala=self.host)

	# ── Lo que envía el juego ──

	def _voz(self, texto: str, _duracion: float) -> None:
		"""Gancho de la voz: el profesor ve lo que oye el alumno, con su canal."""
		canales = self.app.voz.historial_canales
		canal = canales[-1] if canales and self.app.voz.ultimo == texto else "juego"
		self.cliente.voz(texto, canal if canal in ("juego", "ayuda", "aviso", "profesional") else "juego")

	def estado(self, datos: dict[str, Any]) -> None:
		"""Estado de la partida (el cliente envía el último cinco veces por segundo)."""
		self.cliente.estado(datos)

	def evento(self, tipo: str, datos: dict[str, Any] | None = None) -> None:
		"""Un ``EvRegistro`` del motor."""
		self.cliente.evento(tipo, datos)

	def fin(self, completada: bool, resultado: dict[str, Any]) -> None:
		"""La sesión ha terminado."""
		self.cliente.fin(completada, resultado)

	def cambiar_contexto(self, entorno: str, actividad: str, modo: str) -> None:
		"""Se empieza otra actividad sin cerrar el reproductor."""
		self.cliente.cambiar_contexto(entorno, actividad, modo)

	def peticion(self, accion: str, **datos: Any) -> int:
		"""Modo recorrido: pide algo al Estudio."""
		return self.cliente.peticion(accion, **datos)

	# ── Una vez por fotograma ──

	def atender(self, dt: float) -> None:
		"""Reparte órdenes y avisos pendientes."""
		for tipo, datos in self.cliente.avisos_pendientes():
			self._aviso(tipo, datos)
		for tipo, datos in self.cliente.ordenes_pendientes():
			self._orden(tipo, datos)

	def _orden(self, tipo: str, datos: dict[str, Any]) -> None:
		# Estas dos no son de la partida: valen también en los menús, y la partida se entera por la aplicación.
		if tipo == "alumno":
			self.app.recibir_ficha(datos)
			return
		if tipo == "releer_configuracion":
			cambiadas = self.app.releer_configuracion()
			log.info("El Estudio ha pedido releer la configuración: %d cambios.", len(cambiadas))
			return
		partida = self.app.partida
		if partida is not None:
			partida.orden_profesor(tipo, datos)
		elif tipo == "mensaje":
			self.app.sonar("logro/pista", volumen=0.7)
			self.app.decir(str(datos.get("texto") or ""), True, "profesional")
		elif tipo == "respuesta":
			self.app.decir(str(datos.get("texto") or ""), True, "profesional")
		else:
			log.info("Orden «%s» del profesor sin partida en marcha: se ignora.", tipo)

	def _aviso(self, tipo: str, datos: dict[str, Any]) -> None:
		app = self.app
		if tipo == "conectado":
			sala = self.cliente.nombre_sala
			if self._conectado_alguna_vez:
				texto = _("Conexión con tu profesor recuperada.")
			elif self.recorrido:
				texto = _("Conectado con el Estudio.")
			else:
				texto = _("Conectado con tu profesor, en la sala {sala}.").format(sala=sala) if sala else _("Conectado con tu profesor.")
			if self._primera_vez and self.cliente.tls and self.cliente.huella_sala:
				texto += " " + _(
					"Es la primera vez que te conectas a esta sala. Para estar seguros de que es la de tu profesor, "
					"comparad esta clave con la que ve en su pantalla: {huella}."
				).format(huella=deletrear_huella(self.cliente.huella_sala))
			self._primera_vez = False
			self._conectado_alguna_vez = True
			app.sonar("interfaz/elegir")
			app.decir(texto, False, "aviso")
		elif tipo == "desconectado":
			if self._conectado_alguna_vez:
				app.decir(
					_("Se ha perdido la conexión con tu profesor. Puedes seguir jugando: se volverá a conectar sola."), False, "aviso"
				)
		elif tipo == "rechazado":
			self._rechazo(str(datos.get("motivo") or ""), datos)

	def _rechazo(self, motivo: str, datos: dict[str, Any]) -> None:
		app = self.app
		if motivo == "huella":
			self._preguntar_huella()
			return
		frases = {
			"codigo": _("El código no es correcto. Pídeselo otra vez a tu profesor."),
			"bloqueado": _("Demasiados intentos con un código incorrecto. Espera un minuto: se volverá a probar solo."),
			"version": _("El programa de tu profesor es de otra versión. Hay que actualizar uno de los dos."),
			"lleno": _("La sala de tu profesor está llena."),
			"sala": _("Esa sala no conoce el código: puede que no sea la de tu profesor. No se ha conectado."),
			"expulsado": _("Tu profesor ha cerrado tu conexión."),
			"cierre": _("Tu profesor ha cerrado la sala."),
		}
		app.sonar("logro/error")
		app.decir(
			frases.get(motivo, _("No se ha podido conectar con la sala de tu profesor.")) + " " + _("Puedes seguir jugando."),
			False,
			"aviso",
		)

	def _preguntar_huella(self) -> None:
		"""La sala presenta otra identificación: no se ha enviado nada; se pregunta antes de aceptarla."""
		app = self.app
		if self._menu_huella is not None and self._menu_huella in app.pila:
			return
		huella = deletrear_huella(self.cliente.huella_sala)

		def aceptar() -> None:
			app.cerrar(menu)
			self.cliente.aceptar_huella_nueva()
			app.decir(_("De acuerdo. Conectando."), True)

		def rechazar() -> None:
			app.cerrar(menu)
			app.desconectar_sala()
			app.decir(_("No se ha conectado."), True)

		menu = Menu(
			app,
			_("La sala del profesor ha cambiado de identificación"),
			[
				Opcion(_("No conectar"), rechazar, ayuda=_("Lo más seguro si tu profesor no está contigo para comprobarlo.")),
				Opcion(
					_("Las letras coinciden: conectar"),
					aceptar,
					ayuda=_("Solo si tu profesor ve en su pantalla exactamente estas letras: {huella}.").format(huella=huella),
				),
			],
			intro=_(
				"Puede ser que haya reinstalado el programa, o que sea otro ordenador. Pide a tu profesor que te lea la clave de su sala. Debe ser: {huella}"
			).format(huella=huella),
			escapable=False,
		)
		self._menu_huella = menu
		app.sonar("logro/error")
		app.abrir(menu)
