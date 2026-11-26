"""La sala de supervisión (lado Estudio): servidor TCP en su propio hilo.

Patrón (el mismo del panel del servidor de JuegoGTA): el servidor funciona
con asyncio en un hilo aparte y la ventana NO toca nada suyo. La ventana:

- llama a ``Sala.foto()`` cuando quiere (por ejemplo, con un temporizador) y
  recibe un diccionario nuevo con el estado de todos los alumnos;
- vacía ``Sala.eventos_pendientes()`` para enterarse de lo que ha pasado
  (conexiones, choques, voz, peticiones del modo recorrido...);
- envía órdenes con ``Sala.pedir(alumno, orden, **datos)``, que vuelve al
  momento: el envío se hace dentro del hilo de la sala.

Así ninguna llamada de la interfaz espera a la red, y este módulo se prueba
sin ventanas.

Dos formas de abrir la sala (``iniciar``):

- ``red=False`` (un solo ordenador): escucha solo en ``127.0.0.1``, sin TLS.
- ``red=True``: escucha con TLS en todas las interfaces y, además, sin TLS en
  ``127.0.0.1`` (``puerto_local``) para el reproductor lanzado en el mismo
  ordenador. Fuera de 127.0.0.1 nunca se acepta una conexión sin cifrar.

Privacidad: por la red solo viaja el alias. En los registros no se escribe
ni el alias, ni la dirección, ni el texto de ningún mensaje.
"""

from __future__ import annotations

import asyncio
import logging
import ssl
import threading
import time
from collections import deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from app.core.i18n import _
from app.core.version import APP_VERSION
from app.supervision import protocolo, seguridad
from app.supervision.descubrimiento import Anunciador, direcciones_locales
from app.supervision.protocolo import A_ESTUDIO, A_JUGAR, ORDENES, PUERTO_DESCUBRIMIENTO, PUERTO_SALA, ErrorProtocolo, LectorLineas

# Órdenes de mantenimiento: llegan al reproductor pero no son intervenciones
# del profesional, así que no se apuntan en los eventos del alumno.
ORDENES_DE_SERVICIO: frozenset[str] = frozenset({"alumno", "releer_configuracion"})

log = logging.getLogger(__name__)

# Si a un reproductor se le acumula más que esto sin leer, se le corta: está colgado.
_BUFER_MAXIMO = 1024 * 1024
# Mensajes mal formados seguidos que se toleran antes de cortar la conexión.
_ERRORES_SEGUIDOS = 20
_VOCES_GUARDADAS = 50
_EVENTOS_GUARDADOS = 50
_COLA_INTERFAZ = 2000


class ErrorSala(Exception):
	"""La sala no ha podido abrirse (puerto ocupado, certificado...). El mensaje es para mostrar."""


@dataclass(eq=False)
class _Conexion:
	"""Una conexión TCP viva con un reproductor."""

	escritor: asyncio.StreamWriter
	inicio: float
	cifrada: bool
	seq: int = 0
	ultimo_recibido: float = 0.0
	ultimo_envio: float = 0.0
	errores_seguidos: int = 0
	motivo_cierre: str = ""
	# seq del último mensaje válido recibido; -1 si aún no ha llegado ninguno.
	ultimo_seq: int = -1
	cerrar: bool = False


@dataclass(eq=False)
class _Alumno:
	"""Lo que la sala sabe de un reproductor conectado (o que lo estuvo)."""

	id: str
	alias: str
	instancia: str
	conexion: _Conexion | None = None
	conectado: bool = False
	cifrada: bool = False
	recorrido: bool = False
	entorno: str = ""
	actividad: str = ""
	modo: str = ""
	version_app: str = ""
	planta: str = ""
	x: float | None = None
	y: float | None = None
	rumbo: float | None = None
	espacio: str = ""
	descripcion: str = ""
	delante: str = ""
	pausado: bool = False
	tiempo_activo: float = 0.0
	contadores: dict[str, Any] = field(default_factory=dict)
	ultimo_texto: str = ""
	voces: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=_VOCES_GUARDADAS))
	eventos: deque[dict[str, Any]] = field(default_factory=lambda: deque(maxlen=_EVENTOS_GUARDADOS))
	terminado: bool = False
	resultado: dict[str, Any] | None = None
	conectado_desde: float = 0.0
	ultimo_contacto: float = 0.0
	errores_protocolo: int = 0
	reconexiones: int = 0


class Sala:
	"""Servidor de supervisión para varios alumnos a la vez.

	:param nombre: nombre con que la sala se anuncia en la red (sin datos personales).
	:param carpeta_config: dónde se guarda el certificado; por defecto ``data/config``.
	:param intervalo_latido: cada cuánto se envía un latido si no hay otra cosa que enviar.
	:param tiempo_muerto: segundos sin recibir nada tras los que se da por caída la conexión.
	:param max_alumnos: conexiones simultáneas admitidas.
	:param max_intentos: códigos incorrectos por dirección antes de bloquearla.
	:param bloqueo_s: duración del bloqueo.
	:param espera_hola: segundos que se espera el saludo de una conexión nueva.
	"""

	def __init__(
		self,
		*,
		nombre: str = "",
		carpeta_config: Path | str | None = None,
		intervalo_latido: float = 2.0,
		tiempo_muerto: float = 6.0,
		max_alumnos: int = 16,
		max_intentos: int = 5,
		bloqueo_s: float = 60.0,
		espera_hola: float = 10.0,
	) -> None:
		self.nombre = (nombre or _("Sala de EntornoLab"))[:100]
		self._carpeta_config = carpeta_config
		self._intervalo_latido = intervalo_latido
		self._tiempo_muerto = tiempo_muerto
		self._max_alumnos = max_alumnos
		self._espera_hola = espera_hola
		self._intentos = seguridad.ControlIntentos(max_intentos, bloqueo_s)
		self._candado = threading.Lock()
		self._alumnos: dict[str, _Alumno] = {}
		self._cola: deque[dict[str, Any]] = deque(maxlen=_COLA_INTERFAZ)
		self._hilo: threading.Thread | None = None
		self._bucle: asyncio.AbstractEventLoop | None = None
		self._arrancada = threading.Event()
		self._error_arranque: BaseException | None = None
		self._servidores: list[asyncio.Server] = []
		self._conexiones: set[_Conexion] = set()
		self._anunciador: Anunciador | None = None
		self._contexto: ssl.SSLContext | None = None
		self._codigo = ""
		self._huella = ""
		self._red = False
		self._host = ""
		self._puerto = 0
		self._puerto_local = 0
		self._activa = False

	# ── Arranque y parada ────────────────────────────────────────────────────

	@property
	def activa(self) -> bool:
		"""True mientras la sala acepta conexiones."""
		return self._activa

	@property
	def codigo(self) -> str:
		"""Código de emparejamiento vigente."""
		return self._codigo

	@property
	def puerto(self) -> int:
		"""Puerto principal (con TLS si la sala está en red)."""
		return self._puerto

	@property
	def puerto_local(self) -> int:
		"""Puerto de ``127.0.0.1`` sin TLS, para el reproductor del mismo ordenador."""
		return self._puerto_local

	@property
	def huella(self) -> str:
		"""Huella SHA-256 del certificado (vacía si la sala no está en red)."""
		return self._huella

	def iniciar(
		self,
		puerto: int = PUERTO_SALA,
		codigo: str = "",
		*,
		red: bool = False,
		host: str | None = None,
		puerto_local: int = 0,
		anunciar: bool = True,
		puerto_descubrimiento: int = PUERTO_DESCUBRIMIENTO,
	) -> None:
		"""Abre la sala. Vuelve cuando ya escucha, o lanza ``ErrorSala``.

		:param puerto: puerto principal; 0 deja elegir uno libre al sistema (pruebas).
		:param codigo: código de emparejamiento; vacío para generar uno (queda en ``codigo``).
		:param red: False, solo este ordenador (127.0.0.1 sin TLS); True, red local con TLS.
		:param host: interfaz en la que escuchar en red; por defecto, todas.
		:param puerto_local: con ``red=True``, puerto sin TLS en 127.0.0.1; 0 para uno libre.
		:param anunciar: con ``red=True``, responder a la búsqueda automática de salas.

		Con ``red=True``, la primera vez se crea el certificado (unos
		segundos): llámese desde un hilo de trabajo, no desde la interfaz.
		"""
		if self._hilo is not None:
			raise ErrorSala(_("La sala ya está abierta."))
		self._codigo = seguridad.normalizar_codigo(codigo) or seguridad.generar_codigo()
		self._red = red
		self._host = (host or "0.0.0.0") if red else "127.0.0.1"
		self._contexto = None
		self._huella = ""
		if red:
			try:
				certificado = seguridad.asegurar_certificado(self._carpeta_config)
				self._contexto = seguridad.contexto_servidor(certificado.ruta_certificado, certificado.ruta_llave)
			except (OSError, ssl.SSLError, ValueError) as error:
				raise ErrorSala(_("No se ha podido preparar el certificado de la sala: {error}").format(error=error)) from error
			self._huella = certificado.huella
		self._arrancada.clear()
		self._error_arranque = None
		self._hilo = threading.Thread(target=self._correr, args=(puerto, puerto_local), name="sala-supervision", daemon=True)
		self._hilo.start()
		if not self._arrancada.wait(20.0):
			self.detener()
			raise ErrorSala(_("La sala no ha podido arrancar a tiempo."))
		if self._error_arranque is not None:
			error = self._error_arranque
			self._hilo.join(timeout=5.0)
			self._hilo = None
			raise ErrorSala(
				_(
					"No se ha podido abrir el puerto {puerto}: {error}. Puede que la sala ya esté abierta "
					"en otra ventana o que otro programa esté usando ese puerto."
				).format(puerto=puerto, error=error)
			) from error
		self._activa = True
		if red and anunciar:
			self._anunciador = Anunciador(self.nombre, self._puerto, tls=True, huella=self._huella, puerto=puerto_descubrimiento)
			self._anunciador.iniciar()
		log.info("Sala abierta en el puerto %d (%s)", self._puerto, "red local con TLS" if red else "solo este ordenador")

	def _correr(self, puerto: int, puerto_local: int) -> None:
		bucle = asyncio.new_event_loop()
		try:
			bucle.run_until_complete(self._abrir(puerto, puerto_local))
		except OSError as error:
			self._error_arranque = error
			bucle.run_until_complete(self._cerrar())
			bucle.close()
			self._arrancada.set()
			return
		self._bucle = bucle
		self._arrancada.set()
		try:
			bucle.run_forever()
		finally:
			try:
				bucle.run_until_complete(self._cerrar())
				bucle.run_until_complete(bucle.shutdown_asyncgens())
			except OSError, RuntimeError:
				log.exception("Error al cerrar la sala")
			self._bucle = None
			bucle.close()

	async def _abrir(self, puerto: int, puerto_local: int) -> None:
		async def atender_cifrada(lector: asyncio.StreamReader, escritor: asyncio.StreamWriter) -> None:
			await self._atender(lector, escritor, True)

		async def atender_local(lector: asyncio.StreamReader, escritor: asyncio.StreamWriter) -> None:
			await self._atender(lector, escritor, False)

		if self._red:
			principal = await asyncio.start_server(atender_cifrada, self._host, puerto, ssl=self._contexto, ssl_handshake_timeout=10.0)
			self._servidores.append(principal)
			self._puerto = principal.sockets[0].getsockname()[1]
			local = await asyncio.start_server(atender_local, "127.0.0.1", puerto_local)
			self._servidores.append(local)
			self._puerto_local = local.sockets[0].getsockname()[1]
		else:
			local = await asyncio.start_server(atender_local, "127.0.0.1", puerto)
			self._servidores.append(local)
			self._puerto = local.sockets[0].getsockname()[1]
			self._puerto_local = self._puerto

	async def _cerrar(self) -> None:
		for servidor in self._servidores:
			servidor.close()
		for conexion in list(self._conexiones):
			conexion.motivo_cierre = "cierre"
			self._escribir(conexion, "rechazo", {"motivo": "cierre"})
			conexion.escritor.close()
		self._servidores.clear()
		# Un respiro para que las despedidas salgan y las tareas vean el cierre.
		await asyncio.sleep(0.05)
		pendientes = [tarea for tarea in asyncio.all_tasks() if tarea is not asyncio.current_task() and not tarea.done()]
		for tarea in pendientes:
			tarea.cancel()
		if pendientes:
			await asyncio.gather(*pendientes, return_exceptions=True)

	def detener(self) -> None:
		"""Cierra la sala con orden: avisa a los reproductores y espera a que el hilo termine."""
		self._activa = False
		anunciador = self._anunciador
		self._anunciador = None
		if anunciador is not None:
			anunciador.detener()
		bucle = self._bucle
		hilo = self._hilo
		if bucle is not None:
			try:
				bucle.call_soon_threadsafe(bucle.stop)
			except RuntimeError:
				log.debug("El bucle de la sala ya estaba cerrado")
		if hilo is not None:
			hilo.join(timeout=10.0)
		self._hilo = None
		with self._candado:
			for alumno in self._alumnos.values():
				alumno.conectado = False
				alumno.conexion = None
		log.info("Sala cerrada")

	# ── Lo que lee la interfaz ───────────────────────────────────────────────

	def foto(self) -> dict[str, Any]:
		"""Estado de la sala y de todos sus alumnos, como diccionario nuevo e independiente.

		Claves de cada alumno: ``id``, ``alias``, ``conectado``, ``cifrada``,
		``recorrido``, ``entorno``, ``actividad``, ``modo``, ``planta``, ``x``,
		``y``, ``rumbo``, ``espacio``, ``posicion`` (descrita en palabras),
		``delante``, ``ultimo_texto``, ``voces`` (historial), ``contadores``,
		``pausado``, ``tiempo_activo``, ``eventos`` (los últimos), ``terminado``,
		``resultado``, ``segundos_sin_contacto``, ``conectado_desde``,
		``errores_protocolo`` y ``reconexiones``.
		"""
		ahora = time.monotonic()
		with self._candado:
			alumnos = []
			for alumno in self._alumnos.values():
				alumnos.append(
					{
						"id": alumno.id,
						"alias": alumno.alias,
						"conectado": alumno.conectado,
						"cifrada": alumno.cifrada,
						"recorrido": alumno.recorrido,
						"entorno": alumno.entorno,
						"actividad": alumno.actividad,
						"modo": alumno.modo,
						"version_app": alumno.version_app,
						"planta": alumno.planta,
						"x": alumno.x,
						"y": alumno.y,
						"rumbo": alumno.rumbo,
						"espacio": alumno.espacio,
						"posicion": alumno.descripcion,
						"delante": alumno.delante,
						"ultimo_texto": alumno.ultimo_texto,
						"voces": [dict(voz) for voz in alumno.voces],
						"contadores": _copia(alumno.contadores),
						"pausado": alumno.pausado,
						"tiempo_activo": alumno.tiempo_activo,
						"eventos": [_copia(evento) for evento in alumno.eventos],
						"terminado": alumno.terminado,
						"resultado": _copia(alumno.resultado),
						"segundos_sin_contacto": round(ahora - alumno.ultimo_contacto, 1),
						"conectado_desde": alumno.conectado_desde,
						"errores_protocolo": alumno.errores_protocolo,
						"reconexiones": alumno.reconexiones,
					}
				)
		return {
			"activa": self._activa,
			"nombre": self.nombre,
			"red": self._red,
			"puerto": self._puerto,
			"puerto_local": self._puerto_local,
			"codigo": self._codigo,
			"huella": self._huella,
			"huella_legible": seguridad.huella_legible(self._huella) if self._huella else "",
			"direcciones": direcciones_locales() if self._red else ["127.0.0.1"],
			"bloqueados": self._intentos.bloqueados(),
			"alumnos": alumnos,
		}

	def eventos_pendientes(self) -> list[dict[str, Any]]:
		"""Devuelve y vacía la cola de sucesos para la interfaz, por orden.

		Cada suceso: ``{"tipo", "alumno" (id), "alias", "hora", "datos"}``.
		Tipos: ``conectado``, ``reconectado``, ``desconectado``, ``evento``,
		``voz``, ``fin``, ``peticion``, ``codigo_incorrecto`` y ``bloqueado``.
		"""
		with self._candado:
			pendientes = list(self._cola)
			self._cola.clear()
		return pendientes

	def _avisar(self, tipo: str, alumno: _Alumno | None, datos: dict[str, Any] | None = None) -> None:
		"""Añade un suceso a la cola de la interfaz. Debe llamarse con el candado tomado."""
		self._cola.append(
			{
				"tipo": tipo,
				"alumno": alumno.id if alumno is not None else "",
				"alias": alumno.alias if alumno is not None else "",
				"hora": time.time(),
				"datos": datos or {},
			}
		)

	# ── Órdenes de la interfaz ───────────────────────────────────────────────

	def pedir(self, alumno: str, orden: str, **datos: Any) -> bool:
		"""Envía una orden a un reproductor. Vuelve al momento.

		Órdenes y sus datos:

		- ``pausa``, ``reanudar``, ``reiniciar``, ``terminar``: sin datos.
		- ``recolocar``: ``planta``, ``x``, ``y`` y, opcional, ``rumbo``.
		- ``mensaje``: ``texto`` (se le dice al alumno con la voz del profesional).
		- ``pista``: ``texto`` y/o ``baliza_s`` (segundos de baliza) y ``destino``.
		- ``ayudas``: ``ayudas`` = ``{ayuda: {"permitida": bool, "limite": int | None}}``.
		- ``premio``: ``nombre`` y, opcionales, ``id``, ``planta``, ``x``, ``y``, ``sonido``, ``mensaje``, ``visibilidad``.
		- ``marca``: ``texto`` opcional (queda en la sesión grabada).
		- ``alumno``: ``ajustes``, ``lista`` y ``niveles`` de la ficha (sin datos personales).
		- ``releer_configuracion``: sin datos.

		``alumno`` y ``releer_configuracion`` no se apuntan como intervención
		del profesional: son mantenimiento, no algo que el alumno haya vivido.

		Devuelve False si ese alumno no está conectado. Lanza ``ValueError``
		(``ErrorProtocolo``) si la orden o sus datos no son válidos: es un
		fallo de quien llama y debe verse.
		"""
		if orden not in ORDENES:
			raise ValueError(f"orden de supervisión desconocida: {orden}")
		limpio = protocolo.validar(orden, datos, A_JUGAR)
		return self._enviar_a(alumno, orden, limpio, apuntar=orden not in ORDENES_DE_SERVICIO)

	def responder(self, alumno: str, id_peticion: int, aceptada: bool, texto: str = "", **datos: Any) -> bool:
		"""Responde a una ``peticion`` del modo recorrido («colocar aquí», «marcar punto», «medir desde aquí»).

		:param texto: lo que el reproductor le dirá al profesional («Mesa colocada», «3,2 metros»).
		:param datos: resultado estructurado (por ejemplo, ``distancia_m``).
		"""
		limpio = protocolo.validar("respuesta", {"id": id_peticion, "aceptada": aceptada, "texto": texto, "datos": datos}, A_JUGAR)
		return self._enviar_a(alumno, "respuesta", limpio, apuntar=False)

	def _enviar_a(self, alumno_id: str, tipo: str, datos: dict[str, Any], *, apuntar: bool) -> bool:
		bucle = self._bucle
		with self._candado:
			alumno = self._alumnos.get(alumno_id)
			if bucle is None or alumno is None or not alumno.conectado or alumno.conexion is None:
				return False
			conexion = alumno.conexion
			if apuntar:
				alumno.eventos.append({"t": alumno.tiempo_activo, "tipo": "intervencion", "datos": {"orden": tipo}})
		try:
			bucle.call_soon_threadsafe(self._escribir, conexion, tipo, datos)
		except RuntimeError:
			return False
		return True

	def expulsar(self, alumno: str) -> bool:
		"""Corta la conexión de un reproductor (se equivocó de sala, por ejemplo)."""
		bucle = self._bucle
		with self._candado:
			ficha = self._alumnos.get(alumno)
			conexion = ficha.conexion if ficha is not None else None
		if bucle is None or conexion is None:
			return False

		def cortar() -> None:
			conexion.motivo_cierre = "expulsado"
			self._escribir(conexion, "rechazo", {"motivo": "expulsado"})
			# No se cierra aquí: el bucle de la conexión espera a que cierre el reproductor,
			# para que le llegue el motivo (ver _despedir). Si calla, lo corta el vigilante.
			conexion.cerrar = True

		try:
			bucle.call_soon_threadsafe(cortar)
		except RuntimeError:
			return False
		return True

	def olvidar(self, alumno: str) -> bool:
		"""Quita de la foto a un alumno ya desconectado."""
		with self._candado:
			ficha = self._alumnos.get(alumno)
			if ficha is None or ficha.conectado:
				return False
			del self._alumnos[alumno]
			return True

	# ── Dentro del hilo de la sala ───────────────────────────────────────────

	def _escribir(self, conexion: _Conexion, tipo: str, datos: dict[str, Any]) -> None:
		"""Envía un mensaje por una conexión. Solo se llama desde el hilo de la sala."""
		transporte = conexion.escritor.transport
		if transporte is None or transporte.is_closing():
			return
		if transporte.get_write_buffer_size() > _BUFER_MAXIMO:
			log.warning("Un reproductor no lee lo que se le envía: se corta su conexión")
			conexion.motivo_cierre = "saturado"
			transporte.abort()
			return
		ahora = time.monotonic()
		try:
			linea = protocolo.codificar(tipo, datos, sentido=A_JUGAR, seq=conexion.seq, t=ahora - conexion.inicio)
		except ErrorProtocolo as error:
			log.error("Mensaje de la sala no válido (%s): no se envía", error.codigo)
			return
		conexion.seq += 1
		conexion.ultimo_envio = ahora
		conexion.escritor.write(linea)

	async def _despedir(self, conexion: _Conexion, lector: asyncio.StreamReader, motivo: str, espera_s: float = 0.0) -> None:
		"""Envía un ``rechazo`` y espera a que el otro lado cierre.

		No se cierra de golpe: si quedan datos del reproductor sin leer, el
		sistema cortaría con un RST y el reproductor perdería el motivo del
		rechazo (y, creyendo que es un fallo de red, reintentaría con un
		código incorrecto hasta bloquearse).
		"""
		self._escribir(conexion, "rechazo", {"motivo": motivo, "espera_s": round(espera_s, 1)})
		try:
			await asyncio.wait_for(conexion.escritor.drain(), 2.0)
		except TimeoutError, ConnectionError, OSError:
			log.debug("No se ha podido entregar la despedida a una conexión")
			return
		await self._esperar_cierre(lector)

	@staticmethod
	async def _esperar_cierre(lector: asyncio.StreamReader, plazo: float = 1.0) -> None:
		"""Lee y descarta lo que llegue hasta que el otro lado cierre o pase el plazo."""
		limite = time.monotonic() + plazo
		while True:
			queda = limite - time.monotonic()
			if queda <= 0:
				return
			try:
				datos = await asyncio.wait_for(lector.read(4096), queda)
			except TimeoutError:
				return
			if not datos:
				return

	async def _leer_saludo(
		self, lector: asyncio.StreamReader, troceador: LectorLineas
	) -> tuple[protocolo.Mensaje | None, list[bytes | None]]:
		"""Lee la primera línea de una conexión nueva, que debe ser ``hola``."""
		while True:
			datos = await lector.read(4096)
			if not datos:
				return None, []
			lineas = troceador.alimentar(datos)
			if not lineas:
				continue
			primera = lineas[0]
			if primera is None:
				raise ErrorProtocolo("tamano", "saludo demasiado largo")
			mensaje = protocolo.decodificar(primera, A_ESTUDIO)
			if mensaje.tipo != "hola":
				raise ErrorProtocolo("tipo", "se esperaba el saludo")
			return mensaje, lineas[1:]

	async def _atender(self, lector: asyncio.StreamReader, escritor: asyncio.StreamWriter, con_tls: bool) -> None:
		"""Vida completa de una conexión: reto, saludo, comprobación del código y mensajes."""
		par = escritor.get_extra_info("peername")
		direccion = str(par[0]) if par else "?"
		ahora = time.monotonic()
		conexion = _Conexion(escritor, ahora, con_tls, ultimo_recibido=ahora, ultimo_envio=ahora)
		self._conexiones.add(conexion)
		alumno: _Alumno | None = None
		vigilante: asyncio.Task[None] | None = None
		try:
			espera = self._intentos.espera(direccion)
			if espera > 0:
				await self._despedir(conexion, lector, "bloqueado", espera)
				return
			if len(self._conexiones) > self._max_alumnos:
				await self._despedir(conexion, lector, "lleno")
				return
			reto = seguridad.nuevo_nonce()
			self._escribir(conexion, "reto", {"nonce": reto, "nombre": self.nombre})
			troceador = LectorLineas()
			try:
				saludo, sobrantes = await asyncio.wait_for(self._leer_saludo(lector, troceador), self._espera_hola)
			except TimeoutError:
				log.debug("Una conexión no ha saludado a tiempo")
				return
			except ErrorProtocolo as error:
				log.info("Saludo no válido (%s)", error.codigo)
				await self._despedir(conexion, lector, "version" if error.codigo == "version" else "protocolo")
				return
			if saludo is None:
				return
			huella = self._huella if con_tls else ""
			esperada = seguridad.prueba_cliente(self._codigo, reto, saludo.datos["nonce"], huella)
			if not seguridad.pruebas_iguales(esperada, saludo.datos["prueba"]):
				quedan = self._intentos.fallo(direccion)
				bloqueo = self._intentos.espera(direccion)
				with self._candado:
					self._avisar("codigo_incorrecto", None, {"direccion": direccion, "intentos_restantes": quedan})
					if bloqueo > 0:
						self._avisar("bloqueado", None, {"direccion": direccion, "espera_s": round(bloqueo, 1)})
				log.warning("Código de emparejamiento incorrecto (quedan %d intentos a esa dirección)", quedan)
				await self._despedir(conexion, lector, "codigo", bloqueo)
				return
			self._intentos.acierto(direccion)
			alumno = self._registrar(saludo.datos, conexion)
			self._escribir(
				conexion,
				"bienvenida",
				{
					"prueba": seguridad.prueba_sala(self._codigo, reto, saludo.datos["nonce"], huella),
					"alumno": alumno.id,
					"nombre": self.nombre,
					"latido_s": self._intervalo_latido,
				},
			)
			vigilante = asyncio.create_task(self._vigilar(conexion))
			for linea in sobrantes:
				self._procesar(alumno, conexion, linea)
			while True:
				if conexion.cerrar:
					# Ya se le ha enviado la despedida: se espera a que cierre él (ver _despedir).
					await self._esperar_cierre(lector)
					break
				datos = await lector.read(4096)
				if not datos:
					break
				for linea in troceador.alimentar(datos):
					self._procesar(alumno, conexion, linea)
		except ConnectionError, OSError, ssl.SSLError:
			# Lo normal cuando el otro lado se apaga o se va la red: no es un fallo del programa.
			log.debug("Conexión de supervisión cortada", exc_info=True)
		finally:
			if vigilante is not None:
				vigilante.cancel()
			self._conexiones.discard(conexion)
			if alumno is not None:
				self._desconectar(alumno, conexion)
			escritor.close()

	def _registrar(self, saludo: dict[str, Any], conexion: _Conexion) -> _Alumno:
		"""Da de alta (o recupera) al alumno de un saludo válido.

		- Misma instancia del reproductor que vuelve (reconexión): conserva su
		  ficha, su historial y sus contadores.
		- Mismo alias desde otro reproductor mientras el primero sigue
		  conectado: se le da otro id («Luna (2)») para no mezclarlos.
		"""
		alias = " ".join(saludo["alias"].split()) or _("sin alias")
		instancia = saludo.get("instancia", "")
		anterior: _Conexion | None = None
		with self._candado:
			alumno = None
			for candidato in self._alumnos.values():
				if candidato.alias.casefold() == alias.casefold() and candidato.instancia == instancia and instancia:
					alumno = candidato
					break
			reconexion = alumno is not None
			if alumno is None:
				ident = alias
				numero = 1
				while ident in self._alumnos and self._alumnos[ident].conectado:
					numero += 1
					ident = f"{alias} ({numero})"
				alumno = _Alumno(id=ident, alias=alias, instancia=instancia)
				self._alumnos[ident] = alumno
			else:
				anterior = alumno.conexion
				alumno.reconexiones += 1
			alumno.conexion = conexion
			alumno.conectado = True
			alumno.cifrada = conexion.cifrada
			alumno.recorrido = bool(saludo.get("recorrido", False))
			alumno.entorno = saludo.get("entorno", alumno.entorno)
			alumno.actividad = saludo.get("actividad", alumno.actividad)
			alumno.modo = saludo.get("modo", alumno.modo)
			alumno.version_app = saludo.get("version_app", "")
			alumno.conectado_desde = time.time()
			alumno.ultimo_contacto = time.monotonic()
			self._avisar("reconectado" if reconexion else "conectado", alumno, {"recorrido": alumno.recorrido, "cifrada": alumno.cifrada})
		if anterior is not None and anterior is not conexion:
			anterior.motivo_cierre = "sustituida"
			anterior.cerrar = True
			anterior.escritor.close()
		if alumno.version_app and alumno.version_app != APP_VERSION:
			log.info("Un reproductor usa otra versión de la aplicación (%s)", alumno.version_app)
		return alumno

	def _desconectar(self, alumno: _Alumno, conexion: _Conexion) -> None:
		with self._candado:
			if alumno.conexion is not conexion:
				# Esta conexión ya había sido sustituida por una reconexión: el alumno sigue conectado.
				return
			alumno.conexion = None
			alumno.conectado = False
			self._avisar("desconectado", alumno, {"motivo": conexion.motivo_cierre or "corte", "terminado": alumno.terminado})

	def _latido(self, conexion: _Conexion) -> None:
		"""Envía un latido con el acuse de lo último recibido."""
		self._escribir(conexion, "latido", {"visto": conexion.ultimo_seq} if conexion.ultimo_seq >= 0 else {})

	async def _vigilar(self, conexion: _Conexion) -> None:
		"""Latido: envía uno si hace falta y corta la conexión si el otro lado calla demasiado."""
		while True:
			await asyncio.sleep(min(self._intervalo_latido, self._tiempo_muerto) / 2.0)
			ahora = time.monotonic()
			if ahora - conexion.ultimo_recibido > self._tiempo_muerto:
				conexion.motivo_cierre = "sin_latido"
				conexion.cerrar = True
				transporte = conexion.escritor.transport
				if transporte is not None:
					# abort y no close: con la red caída, close esperaría a vaciar el búfer.
					transporte.abort()
				return
			if ahora - conexion.ultimo_envio >= self._intervalo_latido:
				self._latido(conexion)

	def _procesar(self, alumno: _Alumno, conexion: _Conexion, linea: bytes | None) -> None:
		"""Trata una línea recibida de un alumno ya emparejado.

		Un mensaje mal formado se cuenta y se ignora: la conexión sigue. Solo
		tras muchos seguidos se corta, porque entonces no es un despiste.
		"""
		ahora = time.monotonic()
		conexion.ultimo_recibido = ahora
		if conexion.cerrar:
			# Conexión en despedida: lo que siga llegando se descarta.
			return
		try:
			if linea is None:
				raise ErrorProtocolo("tamano", "línea demasiado larga")
			mensaje = protocolo.decodificar(linea, A_ESTUDIO)
		except ErrorProtocolo as error:
			conexion.errores_seguidos += 1
			with self._candado:
				alumno.errores_protocolo += 1
				alumno.ultimo_contacto = ahora
			log.debug("Mensaje de supervisión rechazado (%s)", error.codigo)
			if conexion.errores_seguidos > _ERRORES_SEGUIDOS:
				log.warning("Demasiados mensajes mal formados seguidos: se corta la conexión")
				conexion.motivo_cierre = "protocolo"
				self._escribir(conexion, "rechazo", {"motivo": "protocolo"})
				conexion.cerrar = True
			return
		conexion.errores_seguidos = 0
		conexion.ultimo_seq = max(conexion.ultimo_seq, mensaje.seq)
		datos = mensaje.datos
		with self._candado:
			alumno.ultimo_contacto = ahora
			if mensaje.tipo == "estado":
				self._aplicar_estado(alumno, datos)
			elif mensaje.tipo == "evento":
				suceso = {"t": alumno.tiempo_activo, "tipo": datos["tipo"], "datos": datos.get("datos", {})}
				alumno.eventos.append(suceso)
				self._avisar("evento", alumno, _copia(suceso))
			elif mensaje.tipo == "voz":
				voz = {"t": alumno.tiempo_activo, "texto": datos["texto"], "canal": datos.get("canal", "juego")}
				alumno.ultimo_texto = datos["texto"]
				alumno.voces.append(voz)
				self._avisar("voz", alumno, dict(voz))
			elif mensaje.tipo == "fin":
				alumno.terminado = True
				alumno.resultado = datos.get("resultado", {})
				self._avisar("fin", alumno, {"completada": bool(datos.get("completada", False)), "resultado": _copia(alumno.resultado)})
			elif mensaje.tipo == "peticion":
				self._avisar("peticion", alumno, _copia(datos))
			# «latido» solo renueva el último contacto; un segundo «hola» se ignora.
		if mensaje.tipo == "fin":
			# Acuse inmediato: el reproductor suele cerrar justo después de enviar «fin», y un
			# cierre que se cruza con datos recién enviados puede hacer que se pierdan. Con el
			# acuse, el reproductor sabe que ya puede cerrar.
			self._latido(conexion)

	@staticmethod
	def _aplicar_estado(alumno: _Alumno, datos: dict[str, Any]) -> None:
		for campo in (
			"planta",
			"x",
			"y",
			"rumbo",
			"espacio",
			"descripcion",
			"delante",
			"pausado",
			"tiempo_activo",
			"entorno",
			"actividad",
			"modo",
		):
			if campo in datos:
				setattr(alumno, campo, datos[campo])
		if "contadores" in datos:
			alumno.contadores = datos["contadores"]
		if alumno.terminado and datos.get("tiempo_activo", 1.0) < 1.0:
			# Tras «reiniciar» empieza otra sesión: la anterior ya no está «terminada».
			alumno.terminado = False
			alumno.resultado = None


def _copia(valor: Any) -> Any:
	"""Copia profunda de un valor JSON, para que la interfaz no comparta objetos con el hilo de la sala."""
	if isinstance(valor, dict):
		return {clave: _copia(elemento) for clave, elemento in valor.items()}
	if isinstance(valor, list):
		return [_copia(elemento) for elemento in valor]
	return valor
