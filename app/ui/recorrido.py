"""Modo recorrido: colocar cosas andando por el entorno. Lógica sin wx.

El profesional recorre el entorno con el reproductor (el mismo audiojuego
que usará el alumno) y, cuando llega a un sitio, pide al Estudio «colocar un
objeto aquí», «poner aquí el inicio», «marcar este punto» o «medir desde
aquí». Es la tercera forma de colocar, y la más natural para quien no ve el
plano: la posición no se escribe, se anda hasta ella.

Cómo funciona:

1. ``SesionRecorrido.iniciar`` guarda el paquete, se asegura de que la sala
   ÚNICA del Estudio está abierta (``GestorSala.asegurar_local`` del servicio
   del seguimiento: solo ``127.0.0.1`` si no estaba ya abierta en red) y
   lanza el reproductor como proceso hijo con
   ``--recorrido <paquete> --sala 127.0.0.1:<puerto> --codigo <código>``
   (y ``--inicio planta,x,y,rumbo`` si se pide empezar en un punto). El
   proceso queda vigilado (``GestorSala.vigilar``): si muere, se sabe.
2. La interfaz llama a ``atender()`` cada poco, que sondea la sala
   (``GestorSala.sondear`` reparte los sucesos a todas las ventanas que
   escuchan, también a la de supervisión) y atiende los de SU reproductor.
   Por cada ``peticion``, ``resolver`` hace el cambio en el entorno (siempre
   con ``contexto.ejecutar``, de modo que entra en el historial y se puede
   deshacer) y se contesta con ``responder``. El texto de la respuesta es
   una frase corta que el reproductor dice tal cual.
3. Tras cada cambio aceptado se guarda el paquete.

Solo hay un recorrido a la vez (``GestorSala.recorrido``). El «Colocar
recorriendo» del editor de premios usa este mismo mecanismo: si ya hay un
recorrido abierto, lo reutiliza poniendo ``al_pedir`` (la petición la
contesta el editor de premios en vez de ``resolver``); si no, abre uno y lo
cierra al terminar.

CONVENCIÓN DE LAS PETICIONES (la del reproductor real, ``docs/reproductor.md``,
apartado «Modo recorrido»). El protocolo solo deja viajar tres acciones, que
se concretan con sus ``datos``:

- ``colocar_aqui`` con ``clase``:
  - ``"objeto"``: ``objeto`` = ``<complemento>/<id>`` y ``nombre``. Sin
    ``objeto``, el Estudio abre su catálogo con la posición ya puesta.
  - ``"premio"``: ``nombre``. El premio se añade a la actividad elegida en la
    pestaña Actividades del Estudio (``contexto.actividad_actual``); si no
    hay ninguna, se contesta que no y se explica.
  - ``"inicio"``: pone ahí el punto y el rumbo de inicio del entorno.
  Sin ``clase`` se deduce: con ``objeto`` es un objeto. Se toleran además
  ``tipo: "inicio"`` y la acción ``poner_inicio``.
- ``marcar_punto`` con ``nombre`` (si falta, el Estudio lo pregunta).
- ``medir_desde_aqui`` con ``fase``: ``"desde"`` fija el origen y
  ``"hasta"`` mide. En la segunda el reproductor envía ``distancia_m`` (la
  línea recta, que él ya ha dicho); el Estudio contesta con esa misma
  distancia y añade el punto cardinal. Si ``distancia_m`` falta es que el
  origen estaba en otra planta. Sin ``fase`` se mide en dos pasos: la
  primera petición fija el origen y la segunda mide.

RECARGA. Tras cada cambio aceptado el paquete se guarda y la ``respuesta``
lleva ``datos.recargar = true`` (y ``datos.paquete``, la ruta): el
reproductor vuelve a leer el paquete y sigue en el mismo punto. Para los
cambios hechos en el Estudio FUERA de una petición (el profesional edita algo
en la ventana con el reproductor abierto), ``avisar_recarga`` envía la orden
``reiniciar``, que en modo recorrido el reproductor trata como «recarga el
paquete y sigue donde estabas».

Este módulo no importa wx: lo que necesita de la interfaz (abrir el catálogo
con la posición ya puesta, preguntar un nombre) se le inyecta como funciones.
"""

from __future__ import annotations

import logging
import math
import re
import time
from collections import deque
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core import paths
from app.core.i18n import _
from app.dominio import colocacion, edicion
from app.dominio import geometria as geo
from app.dominio.catalogo import sin_acentos
from app.dominio.formato import identificador_seguro
from app.dominio.modelo import Planta, Posicion

log = logging.getLogger(__name__)

COLOCAR = "colocar_aqui"
PREMIO = "poner_premio"
INICIO = "poner_inicio"
MARCAR = "marcar_punto"
MEDIR = "medir_desde_aqui"
#: Acciones que sabe resolver el Estudio.
ACCIONES = (COLOCAR, PREMIO, INICIO, MARCAR, MEDIR)

# Otras formas razonables de pedir lo mismo (un reproductor más nuevo o más antiguo).
_SINONIMOS = {
	"colocar": COLOCAR,
	"colocar_objeto": COLOCAR,
	"colocar_objeto_aqui": COLOCAR,
	"premio": PREMIO,
	"premio_aqui": PREMIO,
	"poner_premio_aqui": PREMIO,
	"poner_un_premio_aqui": PREMIO,
	"inicio": INICIO,
	"inicio_aqui": INICIO,
	"fijar_inicio": INICIO,
	"poner_inicio_aqui": INICIO,
	"poner_aqui_el_inicio": INICIO,
	"marcar": MARCAR,
	"marcar_aqui": MARCAR,
	"marcar_este_punto": MARCAR,
	"medir": MEDIR,
	"medir_aqui": MEDIR,
	"medir_hasta_aqui": MEDIR,
}

#: Orden de la sala con la que se avisa de un cambio hecho en el Estudio (en modo recorrido, recarga).
ORDEN_RECARGA = "reiniciar"
#: Segundos que ``detener`` espera a que el reproductor cierre por las buenas antes de terminarlo.
ESPERA_TERMINAR = 1.0

PedirObjeto = Callable[[str, float, float, float], str | None]
PedirNombre = Callable[[str], str | None]


class ErrorRecorrido(Exception):
	"""El modo recorrido no ha podido empezar; el mensaje está pensado para la persona."""


@dataclass
class Respuesta:
	"""Lo que se contesta a una petición: si se hizo, la frase para decir y los datos."""

	aceptada: bool
	texto: str
	datos: dict[str, Any] = field(default_factory=dict)


def normalizar_accion(accion: str, datos: dict[str, Any] | None = None) -> str:
	"""La acción con su nombre canónico; cadena vacía si no se reconoce.

	«Poner un premio» y «poner aquí el inicio» llegan como ``colocar_aqui``
	con ``clase`` (el protocolo no tiene acciones propias para ellas): aquí
	se separan para que cada una tenga su camino.
	"""
	clave = re.sub(r"[^a-z0-9]+", "_", sin_acentos(str(accion or ""))).strip("_")
	clave = _SINONIMOS.get(clave, clave)
	if clave not in ACCIONES:
		return ""
	datos = datos or {}
	clase = sin_acentos(str(datos.get("clase") or "")).strip()
	es_inicio = str(datos.get("tipo", "")).lower() == "inicio" or datos.get("inicio") is True
	if clave == COLOCAR:
		if clase == "premio":
			return PREMIO
		if clase == "inicio":
			return INICIO
		if clase not in ("", "objeto"):
			return ""
		if not clase and not datos.get("objeto") and es_inicio:
			return INICIO
	if clave == MARCAR and (es_inicio or clase == "inicio"):
		return INICIO
	return clave


def texto_inicio(inicio: Posicion) -> str:
	"""``planta,x,y,rumbo`` como lo espera el argumento ``--inicio`` del reproductor."""
	return f"{inicio.planta},{inicio.x:.3f},{inicio.y:.3f},{inicio.rumbo:.1f}"


def argumentos_reproductor(paquete: Path, puerto: int, codigo: str, inicio: Posicion | None = None) -> list[str]:
	"""Argumentos con los que se lanza el reproductor en modo recorrido."""
	argumentos = ["--recorrido", str(paquete), "--sala", f"127.0.0.1:{puerto}", "--codigo", codigo]
	if inicio is not None and inicio.planta:
		argumentos += ["--inicio", texto_inicio(inicio)]
	return argumentos


AlPedir = Callable[[str, dict[str, Any]], Respuesta | None]


def _gestor_de(contexto: Any, sala: Any) -> tuple[Any, Callable[[list[str]], Any] | None]:
	"""La sala por la que irá el recorrido y cómo lanzar el reproductor.

	Lo normal es la sala ÚNICA del servicio del seguimiento (la misma de la
	ventana de supervisión y de «Probar ahora») y su ``lanzar``, que apunta el
	proceso para cerrarlo al cerrar el Estudio. Con una ``Sala`` suelta (pruebas)
	se envuelve en un ``GestorSala`` propio.
	"""
	from app.ui.seguimiento.sala import GestorSala

	if sala is not None:
		if isinstance(sala, GestorSala):
			return sala, None
		gestor = GestorSala(getattr(contexto, "configuracion", None), fabrica=lambda **_opciones: sala)
		if getattr(sala, "activa", False):
			gestor.sala = sala
		return gestor, None
	try:
		from app.ui.seguimiento.servicio import obtener_servicio

		servicio = obtener_servicio(contexto)
	except Exception:  # noqa: BLE001 - sin el seguimiento (instalación parcial) el recorrido funciona con una sala propia
		log.warning("No se ha podido usar el servicio del seguimiento; el recorrido abre una sala propia", exc_info=True)
		return GestorSala(getattr(contexto, "configuracion", None)), None
	return servicio.sala, servicio.lanzar


class SesionRecorrido:
	"""Un recorrido en marcha: la sala del Estudio, el reproductor hijo y la atención de sus peticiones."""

	def __init__(
		self,
		contexto: Any,
		sala: Any = None,
		pedir_objeto: PedirObjeto | None = None,
		pedir_nombre: PedirNombre | None = None,
		*,
		lanzar: Callable[[list[str]], Any] | None = None,
	) -> None:
		"""Prepara la sesión sin abrir nada todavía.

		:param contexto: el ``ContextoEstudio``.
		:param sala: la sala por la que va el recorrido: un ``GestorSala`` (el del
			servicio, normalmente) o una ``Sala`` suelta (pruebas). Por defecto,
			la sala única del servicio del seguimiento de ese contexto.
		:param pedir_objeto: ``(planta_id, x, y, rumbo) -> id del objeto colocado o None``.
			La interfaz abre el catálogo con la posición ya puesta y coloca ella.
		:param pedir_nombre: ``(propuesta) -> nombre o None`` para una referencia sin nombre.
		:param lanzar: ``(argumentos) -> Proceso``; por defecto el del servicio
			(que lo cierra al cerrar el Estudio) o el del contexto.
		"""
		self.contexto = contexto
		self.gestor, lanzador = _gestor_de(contexto, sala)
		self._lanzar = lanzar or lanzador or contexto.lanzar_reproductor
		self._pedir_objeto = pedir_objeto
		self._pedir_nombre = pedir_nombre
		self.proceso: Any = None
		self.paquete: Path | None = None
		self.argumentos: list[str] = []
		self.activa = False
		#: True desde que el reproductor de este recorrido se ha conectado a la sala.
		self.listo = False
		#: Si está puesta, se le ofrece cada petición antes que a ``resolver``: ``(alumno, datos) -> Respuesta``
		#: o None para dejarla seguir. La usa el editor de premios para «Colocar recorriendo».
		self.al_pedir: AlPedir | None = None
		#: Origen de la medida en curso: (planta_id, x, y), o None si no hay ninguna empezada.
		self.origen_medida: tuple[str, float, float] | None = None
		self._abrio_sala = False
		self._dejar_de_escuchar: Callable[[], None] | None = None
		self._pendientes: deque[dict[str, Any]] = deque()
		# Ids en la sala del reproductor de este recorrido (la sala es compartida con los alumnos).
		self._alumnos: set[str] = set()

	@property
	def sala(self) -> Any:
		"""La ``Sala`` en uso (la del gestor), o None si está cerrada."""
		return self.gestor.sala

	# ── Ciclo de vida ────────────────────────────────────────────────────────

	def _guardar_para_recorrer(self) -> Path:
		"""Deja en disco lo que hay en pantalla y devuelve la ruta que leerá el reproductor.

		Un entorno que aún no se ha guardado nunca se escribe en ``data/temp``
		SIN cambiar la ruta ni el estado «modificado» del documento: recorrerlo
		no debe ponerle nombre ni darlo por guardado.
		"""
		contexto = self.contexto
		if contexto.entorno is None:
			raise ErrorRecorrido(_("No hay ningún entorno abierto que recorrer."))
		if not contexto.entorno.plantas or not any(planta.espacios for planta in contexto.entorno.plantas):
			raise ErrorRecorrido(_("El entorno está vacío. Cree al menos un espacio antes de recorrerlo."))
		if contexto.ruta_paquete is not None:
			if not contexto.guardar():
				raise ErrorRecorrido(_("No se pudo guardar el entorno, así que no se puede recorrer."))
			return Path(contexto.ruta_paquete)
		return self._guardar_temporal()

	def _guardar_temporal(self) -> Path:
		contexto = self.contexto
		ruta = paths.ruta_temporales() / "recorrido" / (identificador_seguro(contexto.entorno.nombre, "entorno") + ".elab")
		ruta_previa, modificado_previo = contexto.ruta_paquete, contexto.modificado
		guardado = contexto.guardar(ruta)
		contexto.ruta_paquete, contexto.modificado = ruta_previa, modificado_previo
		if not guardado:
			raise ErrorRecorrido(_("No se pudo preparar el entorno para recorrerlo."))
		return ruta

	def _guardar_cambio(self) -> bool:
		"""Guarda tras un cambio, en el mismo fichero que tiene abierto el reproductor."""
		if self.contexto.ruta_paquete is not None and self.paquete == Path(self.contexto.ruta_paquete):
			return bool(self.contexto.guardar())
		try:
			self.paquete = self._guardar_temporal()
		except ErrorRecorrido:
			return False
		return True

	def iniciar(self, inicio: Posicion | None = None) -> None:
		"""Guarda, se asegura de que la sala del Estudio está abierta y lanza el reproductor en modo recorrido.

		Lanza ``ErrorRecorrido``, ``ErrorSala`` o ``ErrorProceso`` (todas con
		un mensaje para la persona) si algo no se puede; en ese caso no queda
		nada abierto que no estuviera antes. Si ya hay otro recorrido en marcha
		en este Estudio, lo dice en vez de abrir un segundo reproductor.
		"""
		if self.activa:
			raise ErrorRecorrido(_("Ya hay un recorrido en marcha."))
		otro = getattr(self.gestor, "recorrido", None)
		if otro is not None and otro is not self and getattr(otro, "activa", False):
			raise ErrorRecorrido(_("Ya hay un reproductor recorriendo el entorno. Úselo, o ciérrelo antes de abrir otro."))
		self.paquete = self._guardar_para_recorrer()
		self._abrio_sala = not self.gestor.activa
		try:
			# Si la sala no estaba abierta, se abre solo para este ordenador en un puerto libre.
			self.gestor.asegurar_local()
			sala = self.gestor.sala
			puerto = sala.puerto_local or sala.puerto
			self.argumentos = argumentos_reproductor(self.paquete, puerto, sala.codigo, inicio)
			self._pendientes.clear()
			self._alumnos.clear()
			self._dejar_de_escuchar = self.gestor.escuchar(self._suceso)
			self.proceso = self._lanzar(self.argumentos)
		except Exception:
			self._dejar_la_sala()
			raise
		vigilar = getattr(self.gestor, "vigilar", None)
		if callable(vigilar):
			# Salir con 0 es lo normal: el profesional cierra el recorrido con Escape y el recorrido no envía «fin».
			vigilar(self.proceso, "", cero_es_normal=True)
		self.gestor.recorrido = self
		self.activa = True
		self.listo = False
		self.origen_medida = None
		log.info("Modo recorrido iniciado con %s", self.paquete)

	def detener(self) -> None:
		"""Cierra el recorrido: pide al reproductor que termine, lo espera un poco y deja la sala como estaba.

		Como mucho espera ``ESPERA_TERMINAR`` segundos (y nada si el
		reproductor ni siquiera se ha conectado): se llama desde el hilo de la
		interfaz y no debe dejarla parada.
		"""
		if not self.activa and self.proceso is None:
			return
		self.activa = False
		self.listo = False
		self.al_pedir = None
		sala, proceso = self.sala, self.proceso
		if proceso is not None:
			cierre_esperado = getattr(self.gestor, "cierre_esperado", None)
			if callable(cierre_esperado):
				cierre_esperado(proceso)
		pedidos = 0
		if sala is not None and sala.activa:
			for alias in self._conectados():
				try:
					pedidos += 1 if sala.pedir(alias, "terminar") else 0
				except Exception:  # noqa: BLE001 - se está cerrando: si no llega la orden, se termina el proceso
					log.debug("No se pudo pedir al reproductor que termine", exc_info=True)
		if proceso is not None:
			if pedidos:
				limite = time.monotonic() + ESPERA_TERMINAR
				while _vivo(proceso) and time.monotonic() < limite:
					time.sleep(0.02)
			if _vivo(proceso):
				proceso.terminar(0.5)
		self.proceso = None
		self._dejar_la_sala()
		log.info("Modo recorrido terminado")

	def _dejar_la_sala(self) -> None:
		"""Deja de escuchar y cierra la sala solo si se abrió para este recorrido y no queda nadie más en ella."""
		if self._dejar_de_escuchar is not None:
			self._dejar_de_escuchar()
			self._dejar_de_escuchar = None
		if getattr(self.gestor, "recorrido", None) is self:
			self.gestor.recorrido = None
		if not self._abrio_sala:
			return
		self._abrio_sala = False
		sala = self.sala
		if sala is None:
			return
		try:
			otros = [a for a in sala.foto()["alumnos"] if a.get("conectado") and a.get("id") not in self._alumnos] if sala.activa else []
			if otros:
				log.info("La sala se queda abierta: hay %d reproductores más conectados.", len(otros))
				return
			self.gestor.cerrar()
		except Exception:  # noqa: BLE001 - cerrar no debe impedir seguir trabajando en el Estudio
			log.exception("No se pudo cerrar la sala del recorrido")

	def _conectados(self) -> list[str]:
		"""Ids de los reproductores de ESTE recorrido conectados a la sala."""
		if self.sala is None or not self.sala.activa:
			return []
		return [alumno["id"] for alumno in self.sala.foto()["alumnos"] if alumno.get("conectado") and alumno.get("id") in self._alumnos]

	# ── Atención de la sala ──────────────────────────────────────────────────

	def _suceso(self, suceso: dict[str, Any]) -> None:
		"""Oyente de la sala compartida: aparta los sucesos que son de este recorrido."""
		tipo, datos = suceso.get("tipo"), suceso.get("datos") or {}
		alumno = str(suceso.get("alumno") or "")
		if tipo in ("conectado", "reconectado") and datos.get("recorrido"):
			# La sala es de todo el Estudio: de los reproductores conectados, el del recorrido es el que dice serlo.
			self._alumnos.add(alumno)
		elif tipo == "proceso_terminado":
			if self.proceso is None or datos.get("pid") not in (None, getattr(self.proceso, "pid", None)):
				return
		elif tipo == "codigo_incorrecto":
			log.warning("Un programa intentó entrar en la sala del Estudio con un código incorrecto.")
			return
		elif alumno not in self._alumnos:
			return
		self._pendientes.append(suceso)

	def atender(self) -> list[str]:
		"""Sondea la sala, atiende lo que haya llegado del reproductor y devuelve las frases que conviene anunciar.

		Se llama a menudo desde el hilo de la interfaz (los cambios del entorno
		y los diálogos tienen que ocurrir ahí). No espera a nada.
		"""
		if not self.activa:
			return []
		try:
			self.gestor.sondear()
		except Exception:  # noqa: BLE001 - un fallo al sondear se registra; el recorrido sigue
			log.exception("No se pudo sondear la sala del recorrido")
		frases: list[str] = []
		terminado = False
		while self._pendientes and self.activa:
			suceso = self._pendientes.popleft()
			tipo, datos = suceso.get("tipo"), suceso.get("datos") or {}
			if tipo == "peticion":
				respuesta = self._atender_peticion(str(suceso.get("alumno", "")), datos)
				frases.append(respuesta.texto)
			elif tipo == "conectado":
				self.listo = True
				frases.append(_("El reproductor está listo para recorrer el entorno."))
			elif tipo == "reconectado":
				self.listo = True
			elif tipo == "fin":
				terminado = True
			elif tipo == "desconectado" and datos.get("motivo") in ("cierre", "expulsado"):
				terminado = True
			elif tipo == "proceso_terminado":
				terminado = True
				if datos.get("inesperado"):
					codigo = datos.get("codigo")
					frases.append(
						_("El reproductor del recorrido se ha cerrado de forma inesperada (código {codigo}).").format(codigo=codigo)
						if codigo is not None
						else _("El reproductor del recorrido se ha cerrado de forma inesperada.")
					)
		if not terminado and self.proceso is not None and not _vivo(self.proceso):
			terminado = True
		if terminado and self.activa:
			self.detener()
			frases.append(_("Recorrido terminado."))
		return [frase for frase in frases if frase]

	def _atender_peticion(self, alumno: str, datos: dict[str, Any]) -> Respuesta:
		"""Resuelve una petición y la contesta. Un fallo inesperado también se contesta: el reproductor espera."""
		try:
			respuesta = self.al_pedir(alumno, datos) if self.al_pedir is not None else None
			if respuesta is None:
				respuesta = self.resolver(
					str(datos.get("accion", "")),
					str(datos.get("planta", "")),
					_numero(datos.get("x")),
					_numero(datos.get("y")),
					_numero(datos.get("rumbo")),
					dict(datos.get("datos") or {}),
				)
		except Exception:  # noqa: BLE001 - sin respuesta el profesional se quedaría esperando en el reproductor
			log.exception("Falló la petición del modo recorrido %s", datos.get("id"))
			respuesta = Respuesta(False, _("No se pudo hacer. Los detalles están en el registro del Estudio."))
		try:
			self.gestor.responder(alumno, int(datos.get("id", 0)), respuesta.aceptada, respuesta.texto[:1000], **respuesta.datos)
		except Exception:  # noqa: BLE001 - el cambio ya está hecho y guardado; solo se pierde el aviso
			log.exception("No se pudo responder a la petición %s", datos.get("id"))
		return respuesta

	def avisar_recarga(self) -> bool:
		"""Avisa al reproductor de que el paquete ha cambiado por una edición hecha en el Estudio.

		Envía la orden ``reiniciar``, que en modo recorrido el reproductor
		entiende como «vuelve a leer el paquete y sigue en el mismo punto».
		Devuelve True si se envió a algún reproductor.
		"""
		if not self.activa or self.sala is None:
			return False
		enviado = False
		for alias in self._conectados():
			try:
				enviado = bool(self.gestor.pedir(alias, ORDEN_RECARGA)) or enviado
			except Exception:  # noqa: BLE001 - el aviso es una cortesía: el paquete ya está guardado
				log.exception("No se pudo avisar al reproductor de que recargue")
		if not enviado:
			log.info("Ningún reproductor conectado al que avisar de la recarga.")
		return enviado

	def guardar_y_avisar(self) -> bool:
		"""Tras un cambio hecho en el Estudio durante el recorrido: guarda y avisa al reproductor."""
		if not self.activa:
			return False
		if not self._guardar_cambio():
			return False
		return self.avisar_recarga()

	# ── Resolver una petición ────────────────────────────────────────────────

	def resolver(self, accion: str, planta: str, x: float, y: float, rumbo: float, datos: dict[str, Any] | None = None) -> Respuesta:
		"""Hace lo que pide el profesional desde el reproductor y devuelve la respuesta.

		No toca la red: recibe la petición ya desmenuzada y devuelve qué
		contestar, de modo que se prueba sin sala ni reproductor.
		"""
		datos = dict(datos or {})
		contexto = self.contexto
		if contexto.entorno is None:
			return Respuesta(False, _("No hay ningún entorno abierto en el Estudio."))
		canonica = normalizar_accion(accion, datos)
		if not canonica:
			return Respuesta(False, _("El Estudio no sabe hacer eso."))
		if not (math.isfinite(x) and math.isfinite(y)):
			return Respuesta(False, _("No se sabe en qué punto está."))
		planta_obj = contexto.entorno.planta(planta) or (contexto.planta_actual() if not planta else None)
		if planta_obj is None:
			return Respuesta(False, _("Esa planta no existe en el entorno abierto en el Estudio."))
		if canonica == MEDIR:
			return self._medir(planta_obj, x, y, datos)
		if canonica == COLOCAR:
			respuesta = self._colocar(planta_obj, x, y, rumbo, datos)
		elif canonica == PREMIO:
			respuesta = self._poner_premio(planta_obj, x, y, datos)
		elif canonica == INICIO:
			respuesta = self._poner_inicio(planta_obj, x, y, rumbo)
		else:
			respuesta = self._marcar(planta_obj, x, y, datos)
		if respuesta.aceptada:
			self._tras_cambio(respuesta)
		return respuesta

	def _tras_cambio(self, respuesta: Respuesta) -> None:
		"""Guarda el paquete y apunta en la respuesta que el reproductor tiene que recargarlo."""
		if self.paquete is None and self.contexto.ruta_paquete is not None:
			self.paquete = Path(self.contexto.ruta_paquete)
		if self._guardar_cambio():
			respuesta.datos["recargar"] = True
			respuesta.datos["paquete"] = str(self.paquete)
		else:
			respuesta.datos["recargar"] = False
			respuesta.texto += " " + _("Pero no se pudo guardar: no lo notará hasta que se guarde en el Estudio.")

	def _colocar(self, planta: Planta, x: float, y: float, rumbo: float, datos: dict[str, Any]) -> Respuesta:
		contexto = self.contexto
		tipo = str(datos.get("objeto") or "").strip()
		if not tipo:
			if self._pedir_objeto is None:
				return Respuesta(False, _("Falta decir qué objeto colocar."))
			id_objeto = self._pedir_objeto(planta.id, x, y, rumbo)
			if not id_objeto:
				return Respuesta(False, _("No se ha colocado nada."))
			objeto = contexto.entorno.elemento(id_objeto)
			nombre = objeto.nombre if objeto is not None else _("Objeto")
			return Respuesta(True, _("{nombre}: colocado.").format(nombre=nombre), {"objeto_id": id_objeto})
		if contexto.catalogo is None:
			return Respuesta(False, _("No hay complementos de objetos instalados."))
		variante = str(datos.get("variante") or "") or None
		nombre_pedido = str(datos.get("nombre") or "")
		id_planta = planta.id

		def operacion() -> colocacion.Colocacion:
			# La planta se busca de nuevo: ``ejecutar`` puede haber sustituido el entorno.
			destino = contexto.entorno.planta(id_planta)
			resultado = colocacion.colocar_en_punto(
				contexto.entorno,
				destino,
				tipo,
				contexto.catalogo,
				x,
				y,
				rumbo,
				variante=variante,
				nombre=nombre_pedido,
				paso_minimo=contexto.paso_libre(),
			)
			if not resultado.colocado:
				# Sin objeto no hay cambio: se sale con excepción para que no quede nada en el historial.
				raise _NoColocado(resultado)
			return resultado

		definicion = contexto.catalogo.objeto(tipo)
		nombre_tipo = definicion.nombre if definicion is not None else tipo
		try:
			resultado = contexto.ejecutar(_("colocar {objeto} recorriendo").format(objeto=nombre_tipo), operacion)
		except _NoColocado as error:
			return Respuesta(False, _frase_avisos(error.colocacion.avisos) or _("No cabe ahí. No se ha colocado."))
		objeto = resultado.objeto
		contexto.seleccionar(objeto.id)
		texto = _("{nombre}: colocado.").format(nombre=objeto.nombre or nombre_tipo)
		avisos = _frase_avisos(resultado.avisos)
		if avisos:
			texto += " " + _("Aviso: {avisos}").format(avisos=avisos)
		return Respuesta(True, texto, {"objeto_id": objeto.id, "ancho": objeto.ancho, "fondo": objeto.fondo})

	def _actividad_abierta(self) -> dict[str, Any] | None:
		"""La actividad elegida en el Estudio, solo si de verdad es una de las del paquete abierto."""
		contexto = self.contexto
		actual = getattr(contexto, "actividad_actual", None)
		if not isinstance(actual, dict):
			return None
		for actividad in contexto.actividades:
			if actividad is actual or (actual.get("id") and actividad.get("id") == actual.get("id")):
				return actividad
		return None

	def _poner_premio(self, planta: Planta, x: float, y: float, datos: dict[str, Any]) -> Respuesta:
		"""Añade un premio a la actividad abierta en el Estudio.

		Un premio es de una actividad, no del entorno: sin actividad elegida no
		hay dónde guardarlo, y se dice en lugar de inventar una. No pasa por el
		historial del entorno (no es un cambio suyo): se quita en el panel de
		actividades.
		"""
		contexto = self.contexto
		actividad = self._actividad_abierta()
		if actividad is None:
			return Respuesta(
				False, _("No hay ninguna actividad abierta. Abra una actividad en la pestaña Actividades del Estudio y vuelva a pedirlo.")
			)
		premios = actividad.get("premios")
		if not isinstance(premios, list):
			premios = []
			actividad["premios"] = premios
		nombre = str(datos.get("nombre") or "").strip() or _("Premio")
		premio = _premio_nuevo(nombre, planta.id, x, y, datos, premios)
		premios.append(premio)
		contexto.marcar_modificado(_("poner el premio {nombre} recorriendo").format(nombre=nombre))
		nombre_actividad = str(actividad.get("nombre") or actividad.get("id") or "")
		return Respuesta(
			True,
			_("{nombre}: premio puesto en la actividad {actividad}.").format(nombre=premio["nombre"], actividad=nombre_actividad),
			{"premio_id": premio["id"], "actividad": str(actividad.get("id") or "")},
		)

	def _poner_inicio(self, planta: Planta, x: float, y: float, rumbo: float) -> Respuesta:
		contexto = self.contexto
		id_planta = planta.id
		contexto.ejecutar(
			_("poner el inicio recorriendo"),
			lambda: edicion.fijar_inicio(contexto.entorno, contexto.entorno.planta(id_planta), x, y, geo.normalizar_rumbo(rumbo)),
		)
		return Respuesta(True, _("Inicio puesto aquí."), {"planta": id_planta, "x": x, "y": y})

	def _marcar(self, planta: Planta, x: float, y: float, datos: dict[str, Any]) -> Respuesta:
		contexto = self.contexto
		nombre = str(datos.get("nombre") or "").strip()
		if not nombre:
			propuesta = _("Punto {n}").format(n=len(planta.referencias) + 1)
			nombre = (self._pedir_nombre(propuesta) or "").strip() if self._pedir_nombre is not None else propuesta
			if not nombre:
				return Respuesta(False, _("No se ha marcado nada."))
		tipo = str(datos.get("tipo") or "punto")
		id_planta = planta.id
		referencia = contexto.ejecutar(
			_("marcar el punto {nombre} recorriendo").format(nombre=nombre),
			lambda: edicion.anadir_referencia(
				contexto.entorno,
				contexto.entorno.planta(id_planta),
				nombre,
				x,
				y,
				tipo=tipo,
				descripcion=str(datos.get("descripcion") or ""),
			),
		)
		contexto.seleccionar(referencia.id)
		return Respuesta(True, _("{nombre}: punto marcado.").format(nombre=nombre), {"referencia_id": referencia.id})

	def _medir(self, planta: Planta, x: float, y: float, datos: dict[str, Any]) -> Respuesta:
		"""Mide entre dos puntos por los que pasa el profesional (o hasta un elemento).

		Con ``fase`` manda el reproductor: ``desde`` fija el origen y ``hasta``
		mide. Sin ``fase``, la primera petición fija el origen y la segunda mide.
		"""
		contexto = self.contexto
		hasta = str(datos.get("hasta") or "")
		if hasta:
			encontrado = contexto.entorno.buscar(hasta)
			if encontrado is None:
				return Respuesta(False, _("Ese elemento no existe."))
			planta_destino, elemento = encontrado
			destino = edicion.centro_de(elemento)
			if planta_destino is not None and planta_destino.id != planta.id:
				return Respuesta(True, _("{nombre} está en otra planta.").format(nombre=elemento.nombre), {"misma_planta": False})
			distancia = geo.distancia((x, y), destino)
			return Respuesta(
				True,
				_("{nombre}: {medida}.").format(nombre=elemento.nombre, medida=_frase_medida(distancia, geo.rumbo_entre((x, y), destino))),
				{"distancia_m": round(distancia, 2), "rumbo": round(geo.rumbo_entre((x, y), destino), 1), "misma_planta": True},
			)
		fase = sin_acentos(str(datos.get("fase") or "")).strip()
		if fase not in ("desde", "hasta"):
			fase = "desde" if self.origen_medida is None or datos.get("origen") is True else "hasta"
		if fase == "desde":
			self.origen_medida = (planta.id, x, y)
			return Respuesta(True, _("Origen fijado."), {"origen": True})
		origen = self.origen_medida
		self.origen_medida = None
		dicha = datos.get("distancia_m")
		if not (isinstance(dicha, (int, float)) and not isinstance(dicha, bool) and math.isfinite(dicha) and dicha >= 0):
			dicha = None
		if origen is None:
			if dicha is None:
				return Respuesta(False, _("Falta el origen de la medida. Elija primero «Medir desde aquí»."))
			# El Estudio no vio el origen (se fijó antes de conectar): vale la distancia del reproductor, sin rumbo.
			return Respuesta(True, edicion._metros(float(dicha)) + ".", {"distancia_m": round(float(dicha), 2), "misma_planta": True})
		planta_origen, ox, oy = origen
		if planta_origen != planta.id:
			otra = contexto.entorno.planta(planta_origen)
			desnivel = planta.altura_m - otra.altura_m if otra is not None else 0.0
			return Respuesta(
				True,
				_("El origen está en otra planta, {metros} de desnivel.").format(metros=edicion._metros(abs(desnivel))),
				{"misma_planta": False, "desnivel_m": round(desnivel, 2)},
			)
		calculada = geo.distancia((ox, oy), (x, y))
		rumbo = geo.rumbo_entre((ox, oy), (x, y)) if calculada > 0.005 else 0.0
		# Si el reproductor ya dijo una distancia, se repite la suya: dos cifras distintas confundirían.
		distancia = float(dicha) if dicha is not None else calculada
		return Respuesta(
			True,
			_frase_medida(distancia, rumbo) + ".",
			{"distancia_m": round(distancia, 2), "rumbo": round(rumbo, 1), "misma_planta": True},
		)


class _NoColocado(Exception):
	"""El objeto no se ha podido colocar: saca el resultado de ``contexto.ejecutar`` sin dejar rastro en el historial."""

	def __init__(self, resultado: colocacion.Colocacion) -> None:
		super().__init__("objeto no colocado")
		self.colocacion = resultado


def _premio_nuevo(nombre: str, planta_id: str, x: float, y: float, datos: dict[str, Any], existentes: list[Any]) -> dict[str, Any]:
	"""Un premio con la forma y los valores de serie de ``app.actividades`` y un id que no se repite.

	Se completa con ``app.actividades.formato.normalizar_premio`` si está (es
	quien sabe qué claves lleva un premio); si ese paquete falta o cambia,
	queda la forma mínima del contrato de arquitectura.
	"""
	usados = {str(premio.get("id")) for premio in existentes if isinstance(premio, dict) and premio.get("id")}
	visibilidad = str(datos.get("visibilidad") or "cerca")
	base = {
		"nombre": nombre[:200],
		"planta": planta_id,
		"x": round(x, 3),
		"y": round(y, 3),
		"sonido": str(datos.get("sonido") or ""),
		"visibilidad": visibilidad if visibilidad in ("lejos", "cerca", "oculto") else "cerca",
		"dentro_de": None,
		"mensaje": str(datos.get("mensaje") or ""),
	}
	numero = len(existentes) + 1
	try:
		from app.actividades.formato import normalizar_premio

		completo = normalizar_premio(base, numero, set(usados))
	except Exception:  # noqa: BLE001 - el paquete de actividades es de otra mano: sin él vale la forma mínima
		log.debug("No se pudo normalizar el premio con app.actividades; se usa la forma mínima", exc_info=True)
		completo = None
	if isinstance(completo, dict) and completo.get("id"):
		return completo
	ident = f"premio-{numero}"
	while ident in usados:
		numero += 1
		ident = f"premio-{numero}"
	return {"id": ident, **base}


def _vivo(proceso: Any) -> bool:
	"""``proceso.vivo()`` tolerante: un proceso que ya no se deja consultar se da por terminado."""
	try:
		return bool(proceso.vivo())
	except AttributeError, OSError:
		log.debug("No se ha podido saber si el reproductor sigue vivo; se da por terminado", exc_info=True)
		return False


def _numero(valor: Any) -> float:
	"""Un número de la petición; ``nan`` si falta o no lo es (``resolver`` lo rechaza)."""
	if isinstance(valor, (int, float)) and not isinstance(valor, bool):
		return float(valor)
	return math.nan


def _frase_medida(distancia: float, rumbo: float) -> str:
	"""«3,2 metros hacia el noreste»; a menos de un centímetro, «Está en el mismo punto»."""
	if distancia <= 0.005:
		return _("Está en el mismo punto")
	return _("{distancia} hacia el {punto}").format(distancia=edicion._metros(distancia), punto=geo.punto_cardinal(rumbo))


def _frase_avisos(avisos: list[Any]) -> str:
	"""Los avisos de una colocación en una sola frase, con los errores primero."""
	ordenados = sorted(avisos, key=lambda aviso: not aviso.es_error)
	return " ".join(aviso.mensaje.strip() for aviso in ordenados if aviso.mensaje).strip()
