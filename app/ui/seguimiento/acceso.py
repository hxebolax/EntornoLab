"""Acceso a los datos de los alumnos: contraseña del profesional y apertura de la base. Sin wx.

Flujo:

- La primera vez no hay contraseña: ``crear_contrasena`` genera una sal, deriva
  la clave (scrypt) y guarda en ``data/config/seguimiento_acceso.json`` la sal
  y un comprobante. La contraseña NO se guarda en ningún sitio, y la clave
  solo vive en memoria mientras la sesión de trabajo está desbloqueada.
- Después, ``desbloquear`` deriva la clave con la sal guardada y la compara con
  el comprobante antes de tocar la base: una contraseña mal escrita se dice
  sin abrir nada.
- ``bloquear`` cierra la base y suelta la clave: la siguiente función de
  alumnos volverá a pedir la contraseña.
- ``cambiar_contrasena`` recifra todos los campos sensibles en una sola
  transacción y solo entonces sustituye el fichero de acceso.

Si se pierde la contraseña no hay recuperación: es la consecuencia de que no
esté guardada. La interfaz lo explica al crearla.

Con ``privacidad.cifrar_fichas`` apagado y sin contraseña creada, la base se
abre sin cifrar. Si ya hay contraseña, se sigue pidiendo aunque la preferencia
se apague: los datos ya están cifrados con ella.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core import cifrado, paths
from app.core.i18n import N_, _
from app.seguimiento import grabadora
from app.seguimiento.alumnos import Fichas
from app.seguimiento.base import BaseSeguimiento, Cifrador, ErrorBase, ErrorClave, abrir_base

log = logging.getLogger(__name__)

NOMBRE_FICHERO = "seguimiento_acceso.json"
FORMATO_FICHERO = 1
LONGITUD_MINIMA = 8

SIN_CONTRASENA = "sin_contrasena"
BLOQUEADA = "bloqueada"
ABIERTA = "abierta"
SIN_CIFRAR = "sin_cifrar"

EXPLICACION_CREAR = N_(
	"Las fichas de los alumnos contienen datos personales, a menudo de menores. Para protegerlos, el nombre real, "
	"las notas y las observaciones se guardan cifrados con una contraseña que solo usted conoce.\n\n"
	"Elija una contraseña de {minimo} caracteres o más y escríbala dos veces. Se le pedirá una vez cada vez que "
	"abra el programa y entre en los alumnos, las sesiones, los informes o el cuaderno.\n\n"
	"MUY IMPORTANTE: la contraseña no se guarda en ningún sitio. Si la olvida, NO hay forma de recuperar los "
	"campos cifrados: ni usted, ni nosotros, ni nadie. Apúntela en un lugar seguro.\n\n"
	"El alias de cada alumno, las medidas de las sesiones y los recorridos no se cifran: no contienen el nombre real."
)


class ErrorAcceso(Exception):
	"""No se ha podido abrir o proteger la base. El mensaje es para mostrar."""


class ContrasenaIncorrecta(ErrorAcceso):
	"""La contraseña escrita no es la de estos datos."""


@dataclass
class ResumenApertura:
	"""Lo que se hizo al abrir la base, para contárselo al profesional."""

	nuevas: int = 0
	actualizadas: int = 0
	alumnos_creados: int = 0
	erroneas: int = 0
	caducadas: int = 0
	avisos: list[str] = field(default_factory=list)

	def frase(self) -> str:
		"""Una frase breve, o cadena vacía si no hay nada que contar."""
		partes: list[str] = []
		if self.nuevas or self.actualizadas:
			total = self.nuevas + self.actualizadas
			partes.append(_("Sesiones nuevas incorporadas: {n}.").format(n=total))
		if self.alumnos_creados:
			partes.append(_("Alumnos nuevos creados a partir de sus sesiones: {n}.").format(n=self.alumnos_creados))
		if self.erroneas:
			partes.append(_("Ficheros de sesión que no se han podido leer: {n}.").format(n=self.erroneas))
		if self.caducadas:
			partes.append(_("Sesiones caducadas y borradas: {n}.").format(n=self.caducadas))
		return " ".join(partes)


def validar_contrasena_nueva(contrasena: str, repetida: str) -> str:
	"""Mensaje de error para una contraseña nueva, o cadena vacía si vale."""
	if not contrasena:
		return _("Escriba la contraseña.")
	if len(contrasena) < LONGITUD_MINIMA:
		return _("La contraseña debe tener al menos {minimo} caracteres.").format(minimo=LONGITUD_MINIMA)
	if contrasena != repetida:
		return _("Las dos contraseñas no coinciden. Escríbalas de nuevo.")
	return ""


def _valor(configuracion: Any, clave: str, defecto: Any) -> Any:
	"""Lee una preferencia tolerando una configuración ausente (pruebas) o sin esa clave."""
	if configuracion is None:
		return defecto
	try:
		valor = configuracion.obtener(clave, defecto)
	except KeyError, ValueError, TypeError:
		log.warning("No se ha podido leer la preferencia %s", clave, exc_info=True)
		return defecto
	return defecto if valor is None else valor


class AccesoDatos:
	"""Guarda el estado de la contraseña y la base abierta durante la sesión de trabajo.

	:param configuracion: para leer ``privacidad.cifrar_fichas`` y ``privacidad.caducidad_dias``.
	:param ruta_base: fichero de la base; por defecto el de ``data/db``.
	:param ruta_acceso: fichero de la sal y el comprobante; por defecto en ``data/config``.
	:param carpeta_sesiones: de dónde se incorporan las sesiones; por defecto ``data/sessions``.
	"""

	def __init__(
		self,
		configuracion: Any = None,
		*,
		ruta_base: Path | str | None = None,
		ruta_acceso: Path | str | None = None,
		carpeta_sesiones: Path | str | None = None,
	) -> None:
		self.configuracion = configuracion
		self._ruta_base = Path(ruta_base) if ruta_base is not None else None
		self._ruta_acceso = Path(ruta_acceso) if ruta_acceso is not None else None
		self._carpeta_sesiones = Path(carpeta_sesiones) if carpeta_sesiones is not None else None
		self._clave: bytes | None = None
		self.base: BaseSeguimiento | None = None
		self.ultimo_resumen = ResumenApertura()

	# ── Estado ───────────────────────────────────────────────────────────────

	@property
	def ruta_acceso(self) -> Path:
		"""Fichero con la sal y el comprobante (nunca la contraseña)."""
		return self._ruta_acceso if self._ruta_acceso is not None else paths.ruta_configuracion() / NOMBRE_FICHERO

	@property
	def carpeta_sesiones(self) -> Path:
		"""Carpeta donde el reproductor deja las sesiones."""
		return self._carpeta_sesiones if self._carpeta_sesiones is not None else paths.ruta_sesiones()

	@property
	def cifrado_pedido(self) -> bool:
		"""Valor de la preferencia ``privacidad.cifrar_fichas``."""
		return bool(_valor(self.configuracion, "privacidad.cifrar_fichas", True))

	def hay_contrasena(self) -> bool:
		"""True si ya se creó la contraseña (existe el fichero de acceso legible)."""
		return self._leer_fichero() is not None

	@property
	def abierta(self) -> bool:
		"""True si la base está abierta y lista para usarse."""
		return self.base is not None

	def estado(self) -> str:
		"""``abierta``, ``bloqueada``, ``sin_contrasena`` o ``sin_cifrar`` (se puede abrir sin preguntar)."""
		if self.base is not None:
			return ABIERTA
		if self.hay_contrasena():
			return BLOQUEADA
		return SIN_CONTRASENA if self.cifrado_pedido else SIN_CIFRAR

	# ── Fichero de acceso ────────────────────────────────────────────────────

	def _leer_fichero(self) -> tuple[bytes, bytes] | None:
		ruta = self.ruta_acceso
		if not ruta.is_file():
			return None
		try:
			datos = json.loads(ruta.read_text(encoding="utf-8"))
			sal = bytes.fromhex(str(datos["sal"]))
			comprobante = bytes.fromhex(str(datos["comprobante"]))
		except OSError, ValueError, KeyError, TypeError:
			log.error("El fichero de acceso a los datos de alumnos no se puede leer")
			raise ErrorAcceso(
				_(
					"El fichero que acompaña a la contraseña ({nombre}) está dañado. Restaure una copia de la carpeta "
					"de configuración; sin él no se puede comprobar la contraseña."
				).format(nombre=NOMBRE_FICHERO)
			) from None
		return sal, comprobante

	def _escribir_fichero(self, ruta: Path, sal: bytes, comprobante: bytes) -> None:
		ruta.parent.mkdir(parents=True, exist_ok=True)
		temporal = ruta.with_name(ruta.name + ".tmp")
		contenido = json.dumps({"formato": FORMATO_FICHERO, "sal": sal.hex(), "comprobante": comprobante.hex()}, indent="\t")
		try:
			temporal.write_text(contenido, encoding="utf-8")
			os.replace(temporal, ruta)
		finally:
			if temporal.exists():
				temporal.unlink()

	# ── Abrir ────────────────────────────────────────────────────────────────

	def _abrir(self, clave: bytes | None) -> BaseSeguimiento:
		try:
			if clave is None:
				base = abrir_base(self._ruta_base)
			else:
				base = abrir_base(self._ruta_base, clave=clave, cifrar=cifrado.cifrar, descifrar=cifrado.descifrar)
		except ErrorClave as error:
			if clave is None:
				raise ErrorAcceso(
					_(
						"La base de datos de los alumnos está cifrada, pero falta el fichero que acompaña a la contraseña "
						"({nombre}). Restaure la carpeta de configuración con la que se creó."
					).format(nombre=NOMBRE_FICHERO)
				) from error
			raise ContrasenaIncorrecta(_("La contraseña no corresponde a esta base de datos.")) from error
		except ErrorBase as error:
			raise ErrorAcceso(str(error)) from error
		self.base = base
		self._clave = clave
		self.ultimo_resumen = self._al_abrir(base)
		return base

	def _al_abrir(self, base: BaseSeguimiento) -> ResumenApertura:
		"""Incorpora las sesiones nuevas y aplica la caducidad. Nunca impide usar la base."""
		resumen = ResumenApertura()
		try:
			# El fichero de sesión va sin cifrar: una vez en la base, se borra.
			resultado = grabadora.incorporar_sesiones(self.carpeta_sesiones, base, crear_alumnos=True, borrar_incorporadas=True)
			resumen.nuevas = resultado.nuevas
			resumen.actualizadas = resultado.actualizadas
			resumen.alumnos_creados = resultado.alumnos_creados
			resumen.erroneas = len(resultado.erroneas)
		except ErrorBase, OSError:
			log.exception("No se han podido incorporar las sesiones nuevas")
			resumen.avisos.append(_("No se han podido incorporar las sesiones nuevas. Mire el registro de incidencias."))
		dias = _valor(self.configuracion, "privacidad.caducidad_dias", 0)
		if isinstance(dias, int) and not isinstance(dias, bool) and dias > 0:
			try:
				resumen.caducadas = Fichas(base).caducar_sesiones(dias)
				grabadora.caducar_ficheros(self.carpeta_sesiones, dias)
			except ErrorBase, OSError:
				log.exception("No se ha podido aplicar la caducidad de las sesiones")
				resumen.avisos.append(_("No se ha podido aplicar la caducidad de las sesiones."))
		return resumen

	def abrir_sin_cifrar(self) -> BaseSeguimiento:
		"""Abre la base sin contraseña (preferencia de cifrado apagada y sin contraseña creada)."""
		if self.base is not None:
			return self.base
		if self.hay_contrasena():
			raise ErrorAcceso(_("Los datos están protegidos con contraseña."))
		return self._abrir(None)

	def crear_contrasena(self, contrasena: str) -> BaseSeguimiento:
		"""Define la contraseña por primera vez y abre la base cifrada con ella.

		Si la base ya tenía datos sin cifrar, ``BaseSeguimiento`` los cifra al abrirla con clave.
		"""
		if self.hay_contrasena():
			raise ErrorAcceso(_("La contraseña ya está creada."))
		if len(contrasena) < LONGITUD_MINIMA:
			raise ErrorAcceso(_("La contraseña debe tener al menos {minimo} caracteres.").format(minimo=LONGITUD_MINIMA))
		self.bloquear()
		try:
			sal = cifrado.nueva_sal()
			clave = cifrado.derivar_clave(contrasena, sal)
			comprobante = cifrado.crear_comprobante(clave)
		except cifrado.ErrorCifrado as error:
			raise ErrorAcceso(_("No se ha podido preparar el cifrado: {error}").format(error=error)) from error
		base = self._abrir(clave)
		try:
			self._escribir_fichero(self.ruta_acceso, sal, comprobante)
		except OSError as error:
			# Sin el fichero la contraseña no se podría comprobar la próxima vez: se deshace el cifrado.
			log.exception("No se ha podido guardar el fichero de acceso")
			try:
				base.cambiar_cifrador(None)
			except ErrorBase:
				log.exception("No se ha podido deshacer el cifrado tras fallar el guardado del fichero de acceso")
			self.bloquear()
			raise ErrorAcceso(_("No se ha podido guardar la contraseña: {error}").format(error=error)) from error
		log.info("Contraseña del profesional creada")
		return base

	def desbloquear(self, contrasena: str) -> BaseSeguimiento:
		"""Abre la base con la contraseña. Lanza ``ContrasenaIncorrecta`` si no es la buena."""
		if self.base is not None:
			return self.base
		guardado = self._leer_fichero()
		if guardado is None:
			raise ErrorAcceso(_("Todavía no se ha creado la contraseña."))
		sal, comprobante = guardado
		try:
			clave = cifrado.derivar_clave(contrasena, sal)
		except cifrado.ErrorCifrado as error:
			raise ContrasenaIncorrecta(_("La contraseña no es correcta.")) from error
		if not cifrado.clave_correcta(clave, comprobante):
			log.info("Intento de desbloqueo con una contraseña incorrecta")
			raise ContrasenaIncorrecta(_("La contraseña no es correcta."))
		return self._abrir(clave)

	def bloquear(self) -> None:
		"""Cierra la base y olvida la clave. La próxima vez se pedirá la contraseña."""
		base, self.base = self.base, None
		self._clave = None
		if base is not None:
			base.cerrar()

	cerrar = bloquear

	def cambiar_contrasena(self, actual: str, nueva: str) -> None:
		"""Cambia la contraseña recifrando todos los campos sensibles. Todo o nada."""
		guardado = self._leer_fichero()
		if guardado is None:
			raise ErrorAcceso(_("Todavía no se ha creado la contraseña."))
		if len(nueva) < LONGITUD_MINIMA:
			raise ErrorAcceso(_("La contraseña debe tener al menos {minimo} caracteres.").format(minimo=LONGITUD_MINIMA))
		sal, comprobante = guardado
		try:
			clave_actual = cifrado.derivar_clave(actual, sal)
		except cifrado.ErrorCifrado as error:
			raise ContrasenaIncorrecta(_("La contraseña actual no es correcta.")) from error
		if not cifrado.clave_correcta(clave_actual, comprobante):
			raise ContrasenaIncorrecta(_("La contraseña actual no es correcta."))
		if self.base is None:
			self._abrir(clave_actual)
		base = self.base
		assert base is not None
		try:
			sal_nueva = cifrado.nueva_sal()
			clave_nueva = cifrado.derivar_clave(nueva, sal_nueva)
			comprobante_nuevo = cifrado.crear_comprobante(clave_nueva)
		except cifrado.ErrorCifrado as error:
			raise ErrorAcceso(_("No se ha podido preparar el cifrado: {error}").format(error=error)) from error
		anterior = base.cifrador
		# El fichero nuevo se prepara ANTES de recifrar: si no se puede escribir, no se toca la base.
		preparado = self.ruta_acceso.with_name(self.ruta_acceso.name + ".nuevo")
		try:
			self._escribir_fichero(preparado, sal_nueva, comprobante_nuevo)
		except OSError as error:
			raise ErrorAcceso(_("No se ha podido guardar la contraseña nueva: {error}").format(error=error)) from error
		try:
			base.cambiar_cifrador(Cifrador.con_clave(clave_nueva, cifrado.cifrar, cifrado.descifrar))
		except Exception as error:
			preparado.unlink(missing_ok=True)
			log.exception("No se han podido recifrar los datos con la contraseña nueva")
			raise ErrorAcceso(_("No se han podido cifrar los datos con la contraseña nueva. Se conserva la anterior.")) from error
		try:
			os.replace(preparado, self.ruta_acceso)
		except OSError as error:
			log.exception("No se ha podido sustituir el fichero de acceso; se vuelve a la contraseña anterior")
			base.cambiar_cifrador(anterior)
			preparado.unlink(missing_ok=True)
			raise ErrorAcceso(_("No se ha podido guardar la contraseña nueva. Se conserva la anterior.")) from error
		self._clave = clave_nueva
		# Las copias de seguridad anteriores están cifradas con la contraseña vieja: se deja una nueva.
		try:
			base.copia_seguridad(motivo="tras-cambiar-contrasena")
		except ErrorBase, OSError:
			log.warning("No se ha podido crear la copia de seguridad tras cambiar la contraseña", exc_info=True)
		log.info("Contraseña del profesional cambiada")
