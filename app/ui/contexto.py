"""``ContextoEstudio``: el documento abierto y los servicios que comparten todas las partes del Estudio.

El Estudio lo escriben varias manos (la construcción de entornos en
``app/ui`` y los alumnos, actividades, supervisión e informes en
``app/ui/seguimiento``). Para que ninguna parte tenga que conocer la ventana
de la otra, todas reciben este objeto y solo hablan con él:

- qué hay abierto: ``entorno``, ``ruta_paquete``, ``actividades``, ``recursos``;
- con qué se trabaja: ``catalogo``, ``configuracion``, ``tareas``;
- qué se puede pedir: ``ejecutar`` (un cambio que se puede deshacer),
  ``marcar_modificado``, ``guardar``, ``anunciar``, ``lanzar_reproductor``;
- cómo enterarse de lo que pasa: ``suscribir(evento, funcion)``.

No importa wx: la ventana se le pasa ya hecha y solo se usa lo que tenga
(``SetStatusText``, ``guardar_como``…), de modo que las pruebas pueden crear
un contexto sin ventana.

REGLA: el objeto ``entorno`` se SUSTITUYE por otro al deshacer, rehacer y
abrir. Nadie debe guardarse una referencia al entorno, a una planta o a un
elemento entre dos eventos: se guarda el ``id`` y se vuelve a buscar con
``contexto.entorno.buscar(id)``.
"""

from __future__ import annotations

import inspect
import logging
from collections.abc import Callable
from pathlib import Path
from typing import Any

from app.core.i18n import _
from app.dominio.colocacion import PASO_MINIMO
from app.dominio.edicion import Historial
from app.dominio.formato import guardar_paquete
from app.dominio.modelo import Entorno, Planta

log = logging.getLogger(__name__)

#: Eventos a los que se puede suscribir cualquier parte del Estudio.
EVENTOS = (
	"entorno_abierto",  # hay un entorno nuevo en ``contexto.entorno`` (abrir, nuevo, importar)
	"entorno_cerrado",  # ya no hay entorno abierto
	"entorno_cambiado",  # el entorno abierto ha cambiado (edición, deshacer, rehacer)
	"actividades_cambiadas",  # ha cambiado ``contexto.actividades``
	"seleccion_cambiada",  # ha cambiado ``contexto.seleccion`` (id del elemento elegido)
	"planta_cambiada",  # ha cambiado ``contexto.planta_id`` (la planta que se está viendo)
	"documento_cambiado",  # ha cambiado el nombre, la ruta o el estado «modificado» (título de la ventana)
	"catalogo_cambiado",  # se han instalado, quitado, activado o desactivado complementos
)


class _Instantanea:
	"""Un estado del entorno ya convertido a diccionario, con la forma que espera ``Historial.anotar``."""

	def __init__(self, estado: dict[str, Any]) -> None:
		self._estado = estado

	def a_dict(self) -> dict[str, Any]:
		return self._estado


class ContextoEstudio:
	"""El documento abierto en el Estudio y lo que se puede hacer con él."""

	def __init__(
		self,
		ventana: Any = None,
		configuracion: Any = None,
		catalogo: Any = None,
		tareas: Any = None,
		lanzador: Callable[[list[str]], Any] | None = None,
	) -> None:
		"""Crea un contexto sin entorno abierto.

		:param ventana: la ventana principal (o ``None`` en pruebas sin interfaz).
		:param lanzador: función que arranca el reproductor; por defecto
			``app.core.procesos.lanzar_reproductor``. Las pruebas pasan un doble.
		"""
		self.ventana = ventana
		self.configuracion = configuracion
		self.catalogo = catalogo
		self.tareas = tareas
		self._lanzador = lanzador
		self.entorno: Entorno | None = None
		self.ruta_paquete: Path | None = None
		#: Actividades del paquete abierto (lista de diccionarios). La edita el panel de actividades.
		self.actividades: list[dict[str, Any]] = []
		#: Recursos del paquete (``sonidos/x.ogg``, ``imagenes/plano.png``): nombre interno → bytes.
		self.recursos: dict[str, bytes] = {}
		self.historial = Historial(self._niveles_deshacer())
		self.modificado = False
		#: Crece con cada cambio del entorno (abrir, editar, deshacer, rehacer). Lo que se calcula en
		#: segundo plano (la descripción del entorno) lo compara al terminar para no enseñar algo viejo.
		self.version = 0
		#: Id del elemento elegido en el árbol, la lista o el plano («» si no hay ninguno).
		self.seleccion: str = ""
		#: Id de la planta que se está viendo.
		self.planta_id: str = ""
		#: Actividad elegida en el panel de actividades (el plano dibuja sus premios y su inicio).
		self.actividad_actual: dict[str, Any] | None = None
		self._suscriptores: dict[str, list[Callable[..., Any]]] = {evento: [] for evento in EVENTOS}

	def _niveles_deshacer(self) -> int:
		if self.configuracion is None:
			return 100
		return int(self.configuracion.obtener("editor.deshacer_niveles", 100))

	# ── Eventos ──────────────────────────────────────────────────────────────

	def suscribir(self, evento: str, funcion: Callable[..., Any]) -> Callable[[], None]:
		"""Pide que se llame a ``funcion`` cada vez que ocurra ``evento``. Devuelve cómo darse de baja.

		La función se llama sin argumentos (lo que haya cambiado se lee del
		contexto). Si declara un parámetro obligatorio, recibe el propio contexto.
		Se llama siempre en el hilo de la interfaz, que es donde ocurren los cambios.
		"""
		if evento not in self._suscriptores:
			raise ValueError(f"Evento desconocido: {evento}. Los que hay: {', '.join(EVENTOS)}")
		self._suscriptores[evento].append(funcion)

		def cancelar() -> None:
			if funcion in self._suscriptores[evento]:
				self._suscriptores[evento].remove(funcion)

		return cancelar

	def emitir(self, evento: str) -> None:
		"""Avisa a los suscritos. Un suscriptor que falla no impide avisar a los demás."""
		for funcion in list(self._suscriptores.get(evento, ())):
			try:
				if _pide_argumento(funcion):
					funcion(self)
				else:
					funcion()
			except Exception:  # noqa: BLE001 - un panel roto no debe dejar a medias un cambio ya hecho
				log.exception("Falló un suscriptor del evento %s", evento)

	# ── Documento ────────────────────────────────────────────────────────────

	def abrir_documento(
		self,
		entorno: Entorno,
		ruta: str | Path | None = None,
		actividades: list[dict[str, Any]] | None = None,
		recursos: dict[str, bytes] | None = None,
		modificado: bool = False,
	) -> None:
		"""Pone un entorno como documento abierto (recién creado, leído de un paquete o importado)."""
		self.entorno = entorno
		self.ruta_paquete = Path(ruta) if ruta else None
		self.actividades = list(actividades or [])
		self.recursos = dict(recursos or {})
		self.historial = Historial(self._niveles_deshacer())
		self.modificado = modificado
		self.seleccion = ""
		self.actividad_actual = None
		self.planta_id = (
			entorno.inicio.planta if entorno.planta(entorno.inicio.planta) else (entorno.plantas[0].id if entorno.plantas else "")
		)
		self.version += 1
		self.emitir("entorno_abierto")
		self.emitir("actividades_cambiadas")
		self.emitir("documento_cambiado")

	def cerrar_documento(self) -> None:
		"""Deja el Estudio sin entorno abierto."""
		self.entorno = None
		self.ruta_paquete = None
		self.actividades = []
		self.recursos = {}
		self.historial.limpiar()
		self.modificado = False
		self.seleccion = ""
		self.planta_id = ""
		self.actividad_actual = None
		self.version += 1
		self.emitir("entorno_cerrado")
		self.emitir("actividades_cambiadas")
		self.emitir("documento_cambiado")

	def nombre_documento(self) -> str:
		"""Nombre con el que se anuncia el documento: el del entorno o el del fichero."""
		if self.entorno is None:
			return ""
		return self.entorno.nombre or (self.ruta_paquete.stem if self.ruta_paquete else _("Entorno sin nombre"))

	# ── Cambios ──────────────────────────────────────────────────────────────

	def ejecutar(self, nombre: str, operacion: Callable[[], Any], anuncio: str | None = None) -> Any:
		"""Hace un cambio en el entorno que se podrá deshacer con su nombre.

		Guarda antes el estado para el historial, llama a ``operacion()`` y, si
		termina bien, marca el documento como modificado, avisa
		(``entorno_cambiado``) y lo anuncia. Si la operación lanza una excepción
		(``ErrorEdicion`` cuando lo pedido no se puede hacer), el entorno queda
		como estaba, no se apunta nada en el historial y la excepción sigue su
		camino para que quien llamó se la explique a la persona.

		:param nombre: nombre de la operación en minúsculas, como se leerá tras
			«Deshacer: » («crear la habitación Cocina»).
		:param anuncio: frase que se dice al terminar; por defecto no se dice nada.
		:return: lo que devuelva ``operacion``.
		"""
		if self.entorno is None:
			raise ValueError(_("No hay ningún entorno abierto."))
		estado = self.entorno.a_dict()
		try:
			resultado = operacion()
		except Exception:
			if self.entorno.a_dict() != estado:
				# La operación dejó el entorno a medias: se devuelve a como estaba.
				self.entorno = Entorno.de_dict(estado)
				self.version += 1
				self.emitir("entorno_cambiado")
			raise
		self.historial.anotar(_Instantanea(estado), nombre)  # type: ignore[arg-type]
		self.modificado = True
		self.version += 1
		self.emitir("entorno_cambiado")
		self.emitir("documento_cambiado")
		if anuncio:
			self.anunciar(anuncio)
		return resultado

	def deshacer(self) -> str | None:
		"""Deshace la última operación y devuelve su nombre; ``None`` si no hay nada que deshacer."""
		return self._retroceder(deshacer=True)

	def rehacer(self) -> str | None:
		"""Vuelve a hacer la última operación deshecha y devuelve su nombre; ``None`` si no hay nada."""
		return self._retroceder(deshacer=False)

	def _retroceder(self, deshacer: bool) -> str | None:
		if self.entorno is None:
			return None
		if deshacer:
			if not self.historial.puede_deshacer:
				return None
			nombre = self.historial.operaciones()[-1]
			nuevo = self.historial.deshacer(self.entorno)
		else:
			if not self.historial.puede_rehacer:
				return None
			# «Rehacer: crear la habitación Cocina» → «crear la habitación Cocina».
			nombre = self.historial.texto_rehacer().partition(": ")[2]
			nuevo = self.historial.rehacer(self.entorno)
		if nuevo is None:
			return None
		self.entorno = nuevo
		self.modificado = True
		self.version += 1
		if self.seleccion and nuevo.buscar(self.seleccion) is None and nuevo.planta(self.seleccion) is None:
			self.seleccion = ""
		if nuevo.planta(self.planta_id) is None:
			self.planta_id = nuevo.plantas[0].id if nuevo.plantas else ""
		self.emitir("entorno_cambiado")
		self.emitir("documento_cambiado")
		return nombre

	def marcar_modificado(self, nombre_operacion: str = "") -> None:
		"""Avisa de que se ha cambiado algo del paquete que NO es el entorno: las actividades.

		Lo llama el panel de actividades después de tocar ``contexto.actividades``.
		El documento queda pendiente de guardar y se emite ``actividades_cambiadas``.
		Los cambios del entorno no pasan por aquí sino por ``ejecutar``, que
		además los apunta para deshacer.
		"""
		self.modificado = True
		if nombre_operacion:
			log.debug("Paquete modificado: %s", nombre_operacion)
		self.emitir("actividades_cambiadas")
		self.emitir("documento_cambiado")

	def anadir_recurso(self, nombre: str, datos: bytes) -> None:
		"""Añade (o sustituye) un recurso del paquete: ``sonidos/premio.ogg``, ``imagenes/plano.png``.

		Viaja dentro del ``.elab`` al guardar. Deja el documento pendiente de guardar.
		"""
		self.recursos[nombre] = bytes(datos)
		self.modificado = True
		self.emitir("documento_cambiado")

	# ── Guardar ──────────────────────────────────────────────────────────────

	def guardar(self, ruta: str | Path | None = None) -> bool:
		"""Guarda el paquete abierto (entorno, actividades y recursos). True si quedó guardado.

		Sin ruta conocida se le pide a la ventana («Guardar como»); sin ventana
		no se puede y devuelve False. Nunca lanza: el fallo se registra y se anuncia.
		"""
		if self.entorno is None:
			return False
		destino = Path(ruta) if ruta else self.ruta_paquete
		if destino is None:
			guardar_como = getattr(self.ventana, "guardar_como", None)
			return bool(guardar_como()) if callable(guardar_como) else False
		try:
			destino.parent.mkdir(parents=True, exist_ok=True)
			guardar_paquete(destino, self.entorno, self.actividades, self.recursos or None)
		except Exception as error:  # noqa: BLE001 - disco lleno, sin permiso, ruta imposible: se explica y se sigue
			log.exception("No se pudo guardar %s", destino)
			self.anunciar(_("No se pudo guardar: {error}").format(error=error))
			return False
		self.ruta_paquete = destino
		self.modificado = False
		self.emitir("documento_cambiado")
		return True

	# ── Selección y planta ───────────────────────────────────────────────────

	def seleccionar(self, id_elemento: str) -> None:
		"""Elige un elemento (o una planta) por su id y avisa a los paneles para que se pongan de acuerdo."""
		if id_elemento == self.seleccion:
			return
		self.seleccion = id_elemento
		if self.entorno is not None and id_elemento:
			planta = self.entorno.planta(id_elemento)
			if planta is None:
				encontrado = self.entorno.buscar(id_elemento)
				planta = encontrado[0] if encontrado else None
			if planta is not None and planta.id != self.planta_id:
				self.planta_id = planta.id
				self.emitir("planta_cambiada")
		self.emitir("seleccion_cambiada")

	def elemento_seleccionado(self) -> tuple[Planta | None, Any] | None:
		"""(planta, elemento) de la selección; una planta elegida sale como (planta, planta). None si no hay."""
		if self.entorno is None or not self.seleccion:
			return None
		planta = self.entorno.planta(self.seleccion)
		if planta is not None:
			return planta, planta
		return self.entorno.buscar(self.seleccion)

	def planta_actual(self) -> Planta | None:
		"""La planta que se está viendo, o la primera si la apuntada ya no existe."""
		if self.entorno is None:
			return None
		planta = self.entorno.planta(self.planta_id)
		if planta is None and self.entorno.plantas:
			planta = self.entorno.plantas[0]
			self.planta_id = planta.id
		return planta

	def ir_a_planta(self, id_planta: str) -> None:
		"""Cambia la planta que se ve."""
		if self.entorno is None or self.entorno.planta(id_planta) is None or id_planta == self.planta_id:
			return
		self.planta_id = id_planta
		self.emitir("planta_cambiada")

	# ── Servicios ────────────────────────────────────────────────────────────

	def anunciar(self, texto: str, interrumpir: bool = False) -> None:
		"""Dice una frase breve por el lector de pantalla y la deja en la barra de estado.

		La voz es un complemento: lo que se anuncia queda también escrito en la
		barra de estado, donde se puede volver a leer.
		"""
		if not texto:
			return
		poner_estado = getattr(self.ventana, "SetStatusText", None)
		if callable(poner_estado):
			try:
				poner_estado(texto)
			except Exception:  # noqa: BLE001 - la ventana puede estar cerrándose
				log.debug("No se pudo escribir en la barra de estado", exc_info=True)
		from app.core import voz

		voz.hablar(texto, interrumpir)

	def lanzar_reproductor(self, argumentos: list[str]) -> Any:
		"""Arranca el reproductor como proceso hijo del Estudio y devuelve su ``Proceso``.

		:param argumentos: los del reproductor sin ``--jugar`` (ver ``app.core.procesos.lanzar_reproductor``).
		:raises app.core.procesos.ErrorProceso: si no se pudo arrancar.
		"""
		if self._lanzador is not None:
			return self._lanzador(argumentos)
		from app.core import procesos

		return procesos.lanzar_reproductor(argumentos)

	def paso_libre(self) -> float:
		"""Paso libre mínimo, en metros, que el profesional quiere dejar al colocar objetos."""
		if self.configuracion is None:
			return PASO_MINIMO
		return float(self.configuracion.obtener("editor.paso_libre_m", PASO_MINIMO))

	def letras_ocupadas(self) -> set[str]:
		"""Letras de acceso de los menús de la barra: ningún control de la ventana principal puede repetirlas."""
		obtener = getattr(self.ventana, "letras_de_menus", None)
		return set(obtener()) if callable(obtener) else set()

	def recargar_catalogo(self) -> None:
		"""Vuelve a leer los complementos del disco (tras instalar, quitar, activar o desactivar) y avisa."""
		from app.dominio.catalogo import Catalogo

		desactivados = self.configuracion.obtener("complementos.desactivados", []) if self.configuracion is not None else []
		self.catalogo = Catalogo.cargar(desactivados=desactivados)
		self.emitir("catalogo_cambiado")


def _pide_argumento(funcion: Callable[..., Any]) -> bool:
	"""True si a la función hay que pasarle un argumento (se le pasa el contexto)."""
	try:
		firma = inspect.signature(funcion)
	except TypeError, ValueError:
		return False
	for parametro in firma.parameters.values():
		if parametro.kind in (parametro.POSITIONAL_ONLY, parametro.POSITIONAL_OR_KEYWORD) and parametro.default is parametro.empty:
			return True
	return False
