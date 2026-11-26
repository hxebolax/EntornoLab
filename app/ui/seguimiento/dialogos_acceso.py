"""Diálogos de la contraseña del profesional y puerta de entrada a los datos de alumnos.

``asegurar_base`` es lo que llaman todas las funciones de alumnos: devuelve la
base abierta, pidiendo antes la contraseña si hace falta (una vez por sesión
de trabajo) o creándola la primera vez.
"""

from __future__ import annotations

import logging
from typing import Any

import wx

from app.core.i18n import _
from app.seguimiento.base import BaseSeguimiento
from app.ui.accesibilidad.dialogos import mostrar_error, mostrar_mensaje
from app.ui.seguimiento import acceso as mod_acceso
from app.ui.seguimiento.acceso import AccesoDatos, ContrasenaIncorrecta, ErrorAcceso, validar_contrasena_nueva
from app.ui.seguimiento.comun import DialogoFormulario, Problema, crear_texto, mostrar_modal
from app.ui.seguimiento.contexto import anunciar

log = logging.getLogger(__name__)


class DialogoCrearContrasena(DialogoFormulario):
	"""Primera vez: explica el cifrado y pide la contraseña dos veces."""

	def __init__(self, padre: wx.Window | None, acceso: AccesoDatos) -> None:
		super().__init__(padre, _("Crear la contraseña de los datos de alumnos"))
		self.acceso = acceso
		self.explicacion = crear_texto(
			self.panel,
			self.letras.poner(_("Información:")),
			_(mod_acceso.EXPLICACION_CREAR).format(minimo=mod_acceso.LONGITUD_MINIMA),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=200,
			ancho=560,
			proporcion=1,
			ayuda=_("Explica para qué sirve la contraseña y qué ocurre si se pierde. Léalo con las flechas antes de continuar."),
		)
		self.nueva = crear_texto(
			self.panel,
			self.letras.poner(_("Contraseña nueva:")),
			sizer=self.sizer,
			contrasena=True,
			ayuda=_("Escriba la contraseña, de {minimo} caracteres o más. Lo que escribe no se ve ni se lee en voz alta.").format(
				minimo=mod_acceso.LONGITUD_MINIMA
			),
		)
		self.repetida = crear_texto(
			self.panel,
			self.letras.poner(_("Repita la contraseña:")),
			sizer=self.sizer,
			contrasena=True,
			ayuda=_("Escriba otra vez la misma contraseña, para comprobar que no hay un error al teclear."),
		)
		self.terminar(self.explicacion, tamano_minimo=(600, 460))

	def validar(self) -> Problema | None:
		mensaje = validar_contrasena_nueva(self.nueva.GetValue(), self.repetida.GetValue())
		if not mensaje:
			return None
		self.repetida.SetValue("")
		return mensaje, self.nueva

	def aplicar(self) -> Problema | None:
		try:
			with wx.BusyCursor():
				self.acceso.crear_contrasena(self.nueva.GetValue())
		except ErrorAcceso as error:
			return str(error), self.nueva
		return None


class DialogoPedirContrasena(DialogoFormulario):
	"""Pide la contraseña para desbloquear los datos. Si no es la buena, lo dice y deja volver a escribirla."""

	def __init__(self, padre: wx.Window | None, acceso: AccesoDatos) -> None:
		super().__init__(padre, _("Contraseña de los datos de alumnos"))
		self.acceso = acceso
		self.intentos = 0
		self.campo = crear_texto(
			self.panel,
			self.letras.poner(_("Contraseña del profesional:")),
			sizer=self.sizer,
			contrasena=True,
			ayuda=_(
				"Escriba la contraseña con la que protegió las fichas de los alumnos y pulse Intro. Se pide una vez "
				"por sesión de trabajo. Si la ha olvidado, los campos cifrados no se pueden recuperar."
			),
		)
		self.terminar(self.campo)

	def validar(self) -> Problema | None:
		if not self.campo.GetValue():
			return _("Escriba la contraseña."), self.campo
		return None

	def aplicar(self) -> Problema | None:
		try:
			with wx.BusyCursor():
				self.acceso.desbloquear(self.campo.GetValue())
		except ContrasenaIncorrecta as error:
			self.intentos += 1
			self.campo.SetValue("")
			return str(error), self.campo
		except ErrorAcceso as error:
			return str(error), self.campo
		return None


class DialogoCambiarContrasena(DialogoFormulario):
	"""Cambia la contraseña: la actual y la nueva dos veces."""

	def __init__(self, padre: wx.Window | None, acceso: AccesoDatos) -> None:
		super().__init__(padre, _("Cambiar la contraseña de los datos de alumnos"))
		self.acceso = acceso
		self.actual = crear_texto(
			self.panel,
			self.letras.poner(_("Contraseña de ahora:")),
			sizer=self.sizer,
			contrasena=True,
			ayuda=_("La contraseña que usa actualmente."),
		)
		self.nueva = crear_texto(
			self.panel,
			self.letras.poner(_("Contraseña nueva:")),
			sizer=self.sizer,
			contrasena=True,
			ayuda=_("La contraseña que quiere usar a partir de ahora, de {minimo} caracteres o más.").format(
				minimo=mod_acceso.LONGITUD_MINIMA
			),
		)
		self.repetida = crear_texto(
			self.panel,
			self.letras.poner(_("Repita la contraseña nueva:")),
			sizer=self.sizer,
			contrasena=True,
			ayuda=_("Otra vez la contraseña nueva. Al aceptar, todos los datos cifrados se vuelven a cifrar con ella."),
		)
		self.terminar(self.actual)

	def validar(self) -> Problema | None:
		if not self.actual.GetValue():
			return _("Escriba la contraseña de ahora."), self.actual
		mensaje = validar_contrasena_nueva(self.nueva.GetValue(), self.repetida.GetValue())
		if mensaje:
			self.repetida.SetValue("")
			return mensaje, self.nueva
		return None

	def aplicar(self) -> Problema | None:
		try:
			with wx.BusyCursor():
				self.acceso.cambiar_contrasena(self.actual.GetValue(), self.nueva.GetValue())
		except ContrasenaIncorrecta as error:
			self.actual.SetValue("")
			return str(error), self.actual
		except ErrorAcceso as error:
			return str(error), self.nueva
		return None


def _contar_apertura(contexto: Any, acceso: AccesoDatos) -> None:
	"""Dice lo que se hizo al abrir (sesiones incorporadas, caducadas) y muestra los avisos."""
	resumen = acceso.ultimo_resumen
	frase = resumen.frase()
	if frase:
		anunciar(contexto, frase)


def asegurar_base(contexto: Any, servicio: Any, padre: wx.Window | None = None) -> BaseSeguimiento | None:
	"""Devuelve la base abierta, pidiendo o creando la contraseña si hace falta. ``None`` si se cancela."""
	acceso: AccesoDatos = servicio.acceso
	padre = padre if padre is not None else getattr(contexto, "ventana", None)
	try:
		estado = acceso.estado()
		if estado == mod_acceso.ABIERTA:
			return acceso.base
		if estado == mod_acceso.SIN_CIFRAR:
			base = acceso.abrir_sin_cifrar()
			_contar_apertura(contexto, acceso)
			_enviar_fichas(servicio)
			return base
	except ErrorAcceso as error:
		mostrar_error(padre, str(error), _("No se pueden abrir los datos de alumnos"))
		return None
	clase = DialogoCrearContrasena if estado == mod_acceso.SIN_CONTRASENA else DialogoPedirContrasena
	dialogo = clase(padre, acceso)
	try:
		mostrar_modal(dialogo)
	finally:
		dialogo.Destroy()
	if acceso.base is None:
		return None
	if estado == mod_acceso.SIN_CONTRASENA:
		anunciar(contexto, _("Contraseña creada. Los datos de los alumnos quedan protegidos."))
	_contar_apertura(contexto, acceso)
	for aviso in acceso.ultimo_resumen.avisos:
		mostrar_mensaje(padre, aviso, _("Aviso"), icono=wx.ICON_WARNING)
	_enviar_fichas(servicio)
	return acceso.base


def _enviar_fichas(servicio: Any) -> None:
	"""Con los datos recién abiertos (y las sesiones nuevas incorporadas), los alumnos ya conectados reciben su ficha.

	Un reproductor que se conectó con la base bloqueada no la recibió al
	conectarse; y al incorporar sesiones puede haber cambiado su nivel.
	"""
	enviar = getattr(servicio, "enviar_fichas_conectadas", None)
	if callable(enviar):
		enviar()


def cambiar_contrasena(contexto: Any, servicio: Any, padre: wx.Window | None = None) -> bool:
	"""Abre el diálogo de cambio de contraseña. True si se cambió."""
	acceso: AccesoDatos = servicio.acceso
	try:
		if not acceso.hay_contrasena():
			mostrar_mensaje(
				padre,
				_("Todavía no hay contraseña. Se creará la primera vez que entre en los datos de alumnos."),
				_("Cambiar la contraseña"),
			)
			return False
	except ErrorAcceso as error:
		mostrar_error(padre, str(error))
		return False
	dialogo = DialogoCambiarContrasena(padre, acceso)
	try:
		mostrar_modal(dialogo)
		cambiada = dialogo.aceptado
	finally:
		dialogo.Destroy()
	if cambiada:
		anunciar(contexto, _("Contraseña cambiada. Los datos se han cifrado de nuevo."))
	return cambiada


def bloquear(contexto: Any, servicio: Any) -> None:
	"""Cierra las ventanas con datos de alumnos y la base: lo siguiente volverá a pedir la contraseña."""
	for clave in ("alumnos", "sesiones", "informes", "cuaderno"):
		ventana = servicio.ventanas.get(clave)
		if ventana:
			ventana.Destroy()
		servicio.ventanas.pop(clave, None)
	servicio.acceso.bloquear()
	anunciar(contexto, _("Datos de alumnos bloqueados. Se pedirá la contraseña la próxima vez."))
