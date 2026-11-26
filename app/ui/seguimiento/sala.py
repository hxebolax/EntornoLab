"""Gestor de la sala de supervisión para el Estudio. Sin wx.

Envuelve ``app.supervision.sala.Sala`` con lo que necesitan varias ventanas a
la vez: la sala es UNA para todo el Estudio (la ventana de supervisión, el
«Probar ahora» y el «Colocar recorriendo» la comparten), así que alguien
tiene que repartir sus sucesos. ``sondear`` vacía la cola de la sala y entrega
cada suceso a todos los que escuchan; lo llama el temporizador de cualquier
ventana abierta, de modo que da igual cuál sea.

Además vigila los reproductores que lanza el Estudio (``vigilar``): si uno
termina, ``sondear`` reparte el suceso ``proceso_terminado`` con su código de
salida y si fue inesperado (un reproductor que se cuelga o que alguien cierra
desde el Administrador de tareas no se despide por la sala).

Y guarda qué recorrido hay en marcha (``recorrido``): el «Recorrer el entorno»
del Estudio y el «Colocar recorriendo» del editor de premios usan la misma
sala y el mismo reproductor, nunca dos a la vez.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.i18n import _
from app.supervision.sala import ErrorSala, Sala

log = logging.getLogger(__name__)

Oyente = Callable[[dict[str, Any]], None]

_FOTO_CERRADA: dict[str, Any] = {
	"activa": False,
	"nombre": "",
	"red": False,
	"puerto": 0,
	"puerto_local": 0,
	"codigo": "",
	"huella": "",
	"huella_legible": "",
	"direcciones": [],
	"bloqueados": 0,
	"alumnos": [],
}

#: Tipo del suceso que ``sondear`` emite cuando termina un reproductor vigilado.
PROCESO_TERMINADO = "proceso_terminado"


@dataclass(eq=False)
class _Vigilado:
	"""Un reproductor lanzado por el Estudio al que se vigila hasta que termina."""

	proceso: Any
	alias: str = ""
	cero_es_normal: bool = False
	desde: float = field(default_factory=time.time)
	esperado: bool = False


def _proceso_vivo(proceso: Any) -> bool:
	"""``proceso.vivo()`` sin que un doble o un proceso ya cerrado rompa el sondeo."""
	try:
		return bool(proceso.vivo())
	except AttributeError, OSError:
		log.debug("No se ha podido saber si un reproductor sigue vivo; se da por terminado", exc_info=True)
		return False


def _cerrado_por_el_estudio(proceso: Any) -> bool:
	"""True si el propio Estudio pidió terminarlo (``Proceso.terminar`` o el doble de las pruebas)."""
	return bool(getattr(proceso, "terminado_por_el_estudio", False) or getattr(proceso, "terminado", False))


class GestorSala:
	"""Abre, cierra y consulta la sala, y reparte sus sucesos."""

	def __init__(self, configuracion: Any = None, *, carpeta_config: Path | str | None = None, fabrica: Callable[..., Sala] = Sala) -> None:
		self.configuracion = configuracion
		self._carpeta_config = carpeta_config
		self._fabrica = fabrica
		self.sala: Sala | None = None
		self._oyentes: list[Oyente] = []
		#: Marcas puestas por el profesional en esta sesión de trabajo (el reproductor las guarda en la sesión grabada).
		self.marcas: list[dict[str, Any]] = []
		#: El recorrido en marcha (``app.ui.recorrido.SesionRecorrido``), o None. Solo hay uno por Estudio.
		self.recorrido: Any = None
		self._vigilados: list[_Vigilado] = []
		# Alumno → hora del último «fin» recibido: un reproductor que sale con 0 tras su fin ha terminado bien.
		self._fines: dict[str, float] = {}

	@property
	def activa(self) -> bool:
		"""True si la sala está abierta."""
		return self.sala is not None and self.sala.activa

	def puerto_configurado(self) -> int:
		"""Puerto de la preferencia ``supervision.puerto`` (47900 si no hay configuración)."""
		if self.configuracion is None:
			return 47900
		try:
			return int(self.configuracion.obtener("supervision.puerto", 47900))
		except TypeError, ValueError:
			log.warning("La preferencia supervision.puerto no es un número; se usa el puerto de serie")
			return 47900

	def abrir(self, red: bool = False, puerto: int | None = None, codigo: str = "", anunciar: bool = True) -> None:
		"""Abre la sala. Lanza ``ErrorSala`` con un mensaje para mostrar.

		Con ``red=True`` la primera vez crea el certificado y tarda: llámese desde un hilo de trabajo.
		"""
		if self.activa:
			raise ErrorSala(_("La sala ya está abierta."))
		sala = self._fabrica(carpeta_config=self._carpeta_config)
		sala.iniciar(self.puerto_configurado() if puerto is None else puerto, codigo, red=red, anunciar=anunciar)
		self.sala = sala

	def asegurar_local(self) -> None:
		"""Deja una sala abierta para el reproductor de este ordenador.

		Si ya hay una, se usa. Si no, se abre una solo para este equipo en un
		puerto libre: «Probar ahora» y «Colocar recorriendo» no deben chocar
		con el puerto de la sala de supervisión ni exigir abrirla a mano.
		"""
		if not self.activa:
			self.abrir(red=False, puerto=0)

	def cerrar(self) -> None:
		"""Cierra la sala si está abierta."""
		sala, self.sala = self.sala, None
		if sala is not None:
			sala.detener()

	def foto(self) -> dict[str, Any]:
		"""Estado de la sala; con la sala cerrada, una foto vacía con la misma forma."""
		if self.sala is None:
			return {clave: (list(valor) if isinstance(valor, list) else valor) for clave, valor in _FOTO_CERRADA.items()}
		return self.sala.foto()

	def argumentos_conexion(self) -> list[str]:
		"""``["--sala", "127.0.0.1:puerto", "--codigo", código]`` para lanzar un reproductor de este ordenador."""
		if self.sala is None or not self.activa:
			raise ErrorSala(_("La sala no está abierta."))
		return ["--sala", f"127.0.0.1:{self.sala.puerto_local}", "--codigo", self.sala.codigo]

	# ── Sucesos ──────────────────────────────────────────────────────────────

	def escuchar(self, funcion: Oyente) -> Callable[[], None]:
		"""Apunta a ``funcion`` para recibir cada suceso. Devuelve cómo dejar de escuchar."""
		self._oyentes.append(funcion)

		def cancelar() -> None:
			if funcion in self._oyentes:
				self._oyentes.remove(funcion)

		return cancelar

	def sondear(self) -> list[dict[str, Any]]:
		"""Vacía la cola de la sala, mira los reproductores vigilados y entrega cada suceso a quienes escuchan.

		Devuelve los sucesos. Los de la sala van primero: así el «fin» de un
		alumno se conoce antes de decidir si su reproductor terminó bien.
		"""
		sucesos = self.sala.eventos_pendientes() if self.sala is not None else []
		for suceso in sucesos:
			if suceso.get("tipo") == "fin":
				self._fines[str(suceso.get("alumno") or "").casefold()] = float(suceso.get("hora") or time.time())
		sucesos = [*sucesos, *self._procesos_terminados()]
		for suceso in sucesos:
			for oyente in list(self._oyentes):
				try:
					oyente(suceso)
				except Exception:  # noqa: BLE001 - un oyente roto no puede dejar sin sucesos a las demás ventanas
					log.exception("Un oyente de la sala ha fallado al recibir un suceso")
		return sucesos

	# ── Reproductores vigilados ──────────────────────────────────────────────

	def vigilar(self, proceso: Any, alias: str = "", *, cero_es_normal: bool = False) -> None:
		"""Vigila un reproductor lanzado por el Estudio: cuando termine, ``sondear`` emitirá ``proceso_terminado``.

		El suceso es ``{"tipo": "proceso_terminado", "alumno": alias, "alias": alias,
		"hora": time.time(), "datos": {"codigo": int | None, "inesperado": bool, "pid": int | None}}``.
		``inesperado`` es True salvo que lo cerrara el Estudio (``Proceso.terminar``
		o ``cierre_esperado``) o que saliera con 0 tras el «fin» de su sesión.

		:param alias: el alias con que se conectará (vacío si no se sabe, como en el recorrido).
		:param cero_es_normal: salir con 0 es lo normal aunque no haya «fin» (el
			recorrido del profesional, que se cierra con Escape, no envía «fin»).
		"""
		if proceso is None:
			return
		for vigilado in self._vigilados:
			if vigilado.proceso is proceso:
				vigilado.alias = alias or vigilado.alias
				vigilado.cero_es_normal = vigilado.cero_es_normal or cero_es_normal
				return
		self._vigilados.append(_Vigilado(proceso, str(alias or ""), cero_es_normal))

	def cierre_esperado(self, proceso: Any) -> None:
		"""Avisa de que ese reproductor va a cerrarse a petición del Estudio (orden «terminar»): no será inesperado."""
		for vigilado in self._vigilados:
			if vigilado.proceso is proceso:
				vigilado.esperado = True

	def vigilados(self) -> list[Any]:
		"""Los reproductores vigilados que siguen en marcha."""
		return [vigilado.proceso for vigilado in self._vigilados if _proceso_vivo(vigilado.proceso)]

	def _procesos_terminados(self) -> list[dict[str, Any]]:
		"""Sucesos de los reproductores vigilados que han terminado desde el último sondeo (y deja de vigilarlos)."""
		sucesos: list[dict[str, Any]] = []
		for vigilado in list(self._vigilados):
			proceso = vigilado.proceso
			if _proceso_vivo(proceso):
				continue
			self._vigilados.remove(vigilado)
			codigo = getattr(proceso, "codigo", None)
			codigo = codigo if isinstance(codigo, int) and not isinstance(codigo, bool) else None
			fin = self._fines.get(vigilado.alias.casefold()) if vigilado.alias else max(self._fines.values(), default=None)
			tras_fin = fin is not None and fin >= vigilado.desde
			normal = codigo == 0 and (tras_fin or vigilado.cero_es_normal)
			inesperado = not (vigilado.esperado or _cerrado_por_el_estudio(proceso) or normal)
			pid = getattr(proceso, "pid", None)
			log.log(
				logging.WARNING if inesperado else logging.INFO,
				"Reproductor %s terminado con el código %s%s.",
				pid if isinstance(pid, int) else "?",
				codigo,
				" de forma inesperada" if inesperado else "",
			)
			sucesos.append(
				{
					"tipo": PROCESO_TERMINADO,
					"alumno": vigilado.alias,
					"alias": vigilado.alias,
					"hora": time.time(),
					"datos": {"codigo": codigo, "inesperado": inesperado, "pid": pid if isinstance(pid, int) else None},
				}
			)
		return sucesos

	# ── Órdenes ──────────────────────────────────────────────────────────────

	def pedir(self, alumno: str, orden: str, **datos: Any) -> bool:
		"""Envía una orden a un alumno. False si la sala está cerrada o el alumno no está conectado."""
		if self.sala is None:
			return False
		return self.sala.pedir(alumno, orden, **datos)

	def responder(self, alumno: str, id_peticion: int, aceptada: bool, texto: str = "", **datos: Any) -> bool:
		"""Responde a una petición del modo recorrido."""
		if self.sala is None:
			return False
		return self.sala.responder(alumno, id_peticion, aceptada, texto, **datos)

	def marcar(self, alumno: dict[str, Any], texto: str) -> bool:
		"""Marca este momento de la sesión del alumno con una nota.

		La nota viaja al reproductor, que la guarda en la sesión grabada; aquí
		queda apuntada (sin el alias en ningún registro) para verla en la lista de sucesos.
		"""
		enviado = self.pedir(str(alumno.get("id", "")), "marca", texto=texto)
		if enviado:
			self.marcas.append(
				{
					"alumno": alumno.get("id", ""),
					"t": alumno.get("tiempo_activo", 0.0),
					"planta": alumno.get("planta", ""),
					"x": alumno.get("x"),
					"y": alumno.get("y"),
					"texto": texto,
					"hora": time.time(),
				}
			)
		return enviado
