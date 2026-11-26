"""Estado compartido del seguimiento durante una sesión de trabajo del Estudio. Sin wx.

Un ``ServicioSeguimiento`` por contexto: guarda el acceso a la base (una sola
contraseña por sesión de trabajo), la sala de supervisión, las ventanas
abiertas (para no abrir dos veces la misma) y los reproductores lanzados.
``integracion.al_cerrar`` lo cierra todo.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from app.seguimiento.alumnos import Fichas
from app.seguimiento.base import BaseSeguimiento
from app.ui.seguimiento import presentador_alumnos
from app.ui.seguimiento.acceso import AccesoDatos
from app.ui.seguimiento.sala import GestorSala

log = logging.getLogger(__name__)

_SERVICIOS: dict[int, ServicioSeguimiento] = {}


class ServicioSeguimiento:
	"""Lo que comparten todas las ventanas del seguimiento."""

	def __init__(self, contexto: Any, acceso: AccesoDatos | None = None, sala: GestorSala | None = None) -> None:
		self.contexto = contexto
		configuracion = getattr(contexto, "configuracion", None)
		self.acceso = acceso if acceso is not None else AccesoDatos(configuracion)
		self.sala = sala if sala is not None else GestorSala(configuracion)
		self.ventanas: dict[str, Any] = {}
		self.procesos: list[Any] = []
		self.temporales: list[Path] = []
		self.escucha: Any = None
		# Lo último enviado a cada alumno conectado (id en la sala → datos), para no repetir envíos iguales.
		self._fichas_enviadas: dict[str, dict[str, Any]] = {}
		escuchar = getattr(self.sala, "escuchar", None)
		self._dejar_sala = escuchar(self._suceso_sala) if callable(escuchar) else None

	@property
	def base(self) -> BaseSeguimiento | None:
		"""La base abierta, o ``None`` si está bloqueada."""
		return self.acceso.base

	def fichas(self) -> Fichas:
		"""Operaciones sobre las fichas de la base abierta."""
		if self.acceso.base is None:
			raise RuntimeError("la base del seguimiento no está abierta")
		return Fichas(self.acceso.base)

	def lanzar(self, argumentos: list[str]) -> Any:
		"""Lanza el reproductor por el contexto y lo recuerda para cerrarlo al salir.

		Si la sala sabe vigilar procesos (``GestorSala.vigilar``), se le pasa
		para que avise cuando el reproductor se cierre, con el alias que lleve.
		"""
		textos = [str(argumento) for argumento in argumentos]
		proceso = self.contexto.lanzar_reproductor(textos)
		self.procesos = [otro for otro in self.procesos if _vivo(otro)]
		if proceso is not None:
			self.procesos.append(proceso)
			vigilar = getattr(self.sala, "vigilar", None)
			if callable(vigilar):
				try:
					vigilar(proceso, _alias_de_argumentos(textos))
				except Exception:  # noqa: BLE001 - sin vigilancia el reproductor funciona igual; solo no se avisará de su cierre
					log.exception("No se ha podido vigilar el reproductor lanzado")
		return proceso

	# ── Ficha del alumno y preferencias hacia los reproductores ──────────────

	def _suceso_sala(self, suceso: dict[str, Any]) -> None:
		"""Al conectarse (o volver) un alumno con ficha, se le envía lo que dice su ficha."""
		tipo = suceso.get("tipo")
		ident = str(suceso.get("alumno") or "")
		if tipo == "desconectado":
			self._fichas_enviadas.pop(ident, None)
			return
		if tipo not in ("conectado", "reconectado") or not ident:
			return
		datos = suceso.get("datos") if isinstance(suceso.get("datos"), dict) else {}
		if datos.get("recorrido"):
			# El modo recorrido es el profesional, no un alumno.
			return
		self._fichas_enviadas.pop(ident, None)
		self.enviar_ficha_a(ident, str(suceso.get("alias") or ""))

	def enviar_ficha_a(self, ident: str, alias: str) -> bool:
		"""Envía al reproductor ``ident`` la ficha del alumno de ese alias. False si no hay ficha, base o conexión."""
		if self.base is None or not alias:
			return False
		try:
			ficha = self.fichas().por_alias(alias)
		except Exception:  # noqa: BLE001 - una base que falla al leer no debe tumbar el reparto de sucesos de la sala
			log.exception("No se ha podido leer la ficha de un alumno conectado")
			return False
		if ficha is None or ficha.archivado:
			return False
		datos = presentador_alumnos.datos_para_reproductor(ficha)
		if self._fichas_enviadas.get(ident) == datos:
			return True
		try:
			enviado = bool(self.sala.pedir(ident, "alumno", **datos))
		except ValueError:
			log.exception("La ficha de un alumno no cumple el protocolo de la sala; no se envía")
			return False
		if enviado:
			self._fichas_enviadas[ident] = datos
			log.info("Ficha enviada a un reproductor conectado")
		return enviado

	def enviar_ficha(self, alumno: Any) -> int:
		"""La ficha de ``alumno`` ha cambiado: se envía a sus reproductores conectados. Devuelve a cuántos."""
		alias = str(getattr(alumno, "alias", "") or "")
		enviados = 0
		for ident in self._conectados_con_alias(alias):
			if self.enviar_ficha_a(ident, alias):
				enviados += 1
		return enviados

	def _conectados_con_alias(self, alias: str) -> list[str]:
		"""Ids en la sala de los reproductores conectados con ese alias (sin distinguir mayúsculas)."""
		if not alias:
			return []
		buscado = " ".join(alias.split()).casefold()
		try:
			alumnos = self.sala.foto().get("alumnos") or []
		except Exception:  # noqa: BLE001 - sin foto no hay a quién enviar
			log.exception("No se ha podido mirar quién está conectado a la sala")
			return []
		return [
			str(alumno.get("id"))
			for alumno in alumnos
			if alumno.get("conectado")
			and not alumno.get("recorrido")
			and " ".join(str(alumno.get("alias") or "").split()).casefold() == buscado
		]

	def enviar_fichas_conectadas(self) -> int:
		"""Vuelve a enviar su ficha a todos los conectados (tras incorporar sesiones, por ejemplo). Devuelve a cuántos."""
		try:
			alumnos = self.sala.foto().get("alumnos") or []
		except Exception:  # noqa: BLE001 - sin foto no hay a quién enviar
			log.exception("No se ha podido mirar quién está conectado a la sala")
			return 0
		enviados = 0
		for alumno in alumnos:
			if (
				alumno.get("conectado")
				and not alumno.get("recorrido")
				and self.enviar_ficha_a(str(alumno.get("id")), str(alumno.get("alias") or ""))
			):
				enviados += 1
		return enviados

	def releer_configuracion_en_reproductores(self) -> int:
		"""Pide a todos los reproductores conectados que relean las preferencias compartidas. Devuelve a cuántos."""
		try:
			alumnos = self.sala.foto().get("alumnos") or []
		except Exception:  # noqa: BLE001 - sin foto no hay a quién avisar
			log.exception("No se ha podido mirar quién está conectado a la sala")
			return 0
		avisados = 0
		for alumno in alumnos:
			if alumno.get("conectado") and self.sala.pedir(str(alumno.get("id")), "releer_configuracion"):
				avisados += 1
		if avisados:
			log.info("Se ha pedido releer la configuración a %d reproductores", avisados)
		return avisados

	def cerrar_ventanas(self) -> None:
		"""Destruye las ventanas abiertas del seguimiento."""
		for nombre, ventana in list(self.ventanas.items()):
			try:
				if ventana:
					ventana.Destroy()
			except RuntimeError:
				log.debug("La ventana %s ya estaba destruida", nombre)
		self.ventanas.clear()

	def cerrar(self) -> None:
		"""Cierra ventanas, sala, reproductores y base. Idempotente."""
		self.cerrar_ventanas()
		if callable(self._dejar_sala):
			self._dejar_sala()
			self._dejar_sala = None
		self._fichas_enviadas.clear()
		for proceso in self.procesos:
			try:
				if _vivo(proceso):
					proceso.terminar()
			except OSError:
				log.warning("No se ha podido terminar un reproductor al cerrar", exc_info=True)
		self.procesos.clear()
		try:
			self.sala.cerrar()
		except OSError:
			log.warning("No se ha podido cerrar la sala con orden", exc_info=True)
		if self.escucha is not None:
			try:
				self.escucha.cerrar()
			except Exception:  # noqa: BLE001 - una biblioteca de sonido puede fallar de cualquier forma al cerrarse
				log.warning("No se ha podido cerrar el sonido de la escucha", exc_info=True)
			self.escucha = None
		for ruta in self.temporales:
			try:
				ruta.unlink(missing_ok=True)
			except OSError:
				log.warning("No se ha podido borrar un informe temporal", exc_info=True)
		self.temporales.clear()
		self.acceso.cerrar()


def _alias_de_argumentos(argumentos: list[str]) -> str:
	"""El alias que se pasa al reproductor con ``--alumno`` («» si juega como invitado)."""
	for posicion, argumento in enumerate(argumentos[:-1]):
		if argumento == "--alumno":
			return argumentos[posicion + 1]
	return ""


def _vivo(proceso: Any) -> bool:
	try:
		return bool(proceso.vivo())
	except AttributeError, OSError:
		log.debug("No se ha podido saber si un reproductor sigue vivo; se da por terminado", exc_info=True)
		return False


def obtener_servicio(contexto: Any) -> ServicioSeguimiento:
	"""El servicio de ese contexto; se crea la primera vez."""
	servicio = _SERVICIOS.get(id(contexto))
	if servicio is None or servicio.contexto is not contexto:
		servicio = ServicioSeguimiento(contexto)
		_SERVICIOS[id(contexto)] = servicio
	return servicio


def servicio_existente(contexto: Any) -> ServicioSeguimiento | None:
	"""El servicio de ese contexto si ya se creó; no crea ninguno (para avisos que solo tienen sentido con la sala abierta)."""
	servicio = _SERVICIOS.get(id(contexto))
	return servicio if servicio is not None and servicio.contexto is contexto else None


def poner_servicio(contexto: Any, servicio: ServicioSeguimiento) -> None:
	"""Asocia un servicio ya construido (pruebas: base y sala en carpetas temporales)."""
	_SERVICIOS[id(contexto)] = servicio


def cerrar_servicio(contexto: Any) -> None:
	"""Cierra y olvida el servicio del contexto, si lo hay."""
	servicio = _SERVICIOS.pop(id(contexto), None)
	if servicio is not None:
		servicio.cerrar()
