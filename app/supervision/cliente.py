"""Cliente de supervisión (lado reproductor): un hilo que habla con la sala del Estudio.

Regla de oro: NUNCA bloquea el bucle del juego. Todo lo que el juego llama
(``estado``, ``evento``, ``voz``, ``fin``, ``peticion``, ``ordenes_pendientes``)
solo toca colas en memoria protegidas por un candado; conectar, enviar,
recibir y reconectar ocurre en el hilo del cliente. Si la sala desaparece,
el juego sigue: el alumno no debe notar un corte de red.

Qué hace el hilo:

1. Conecta con ``host:puerto`` (con TLS salvo en 127.0.0.1), recibe el
   ``reto``, comprueba la huella del certificado contra la recordada, envía
   ``hola`` con la prueba del código y espera la ``bienvenida``.
2. Envía el último ``estado`` 5 veces por segundo, los eventos y la voz en
   cuanto llegan, y un ``latido`` si no hay otra cosa.
3. Deja las órdenes recibidas en una cola que el juego vacía una vez por
   fotograma con ``ordenes_pendientes()``.
4. Si se corta, espera (cada vez un poco más, hasta un tope) y vuelve a
   conectar solo. Los eventos ocurridos mientras tanto se envían al volver.

Si el código es incorrecto o la huella de la sala ha cambiado NO reintenta:
insistir bloquearía la dirección o entregaría la sesión a un impostor. Se
queda en ``rechazado`` hasta que el juego llame a ``cambiar_codigo``,
``aceptar_huella_nueva`` o ``reintentar``.
"""

from __future__ import annotations

import logging
import select
import socket
import ssl
import threading
import time
import uuid
from collections import deque
from pathlib import Path
from typing import Any

from app.core.version import APP_VERSION
from app.supervision import protocolo, seguridad
from app.supervision.protocolo import A_ESTUDIO, A_JUGAR, ACCIONES_PETICION, PUERTO_SALA, ErrorProtocolo, LectorLineas

log = logging.getLogger(__name__)

# Estados de ``ClienteSupervision.estado_conexion``.
PARADO = "parado"
CONECTANDO = "conectando"
CONECTADO = "conectado"
ESPERANDO = "esperando"
RECHAZADO = "rechazado"

_COLA_SALIDA = 500
_COLA_ORDENES = 200
_DIRECCIONES_LOCALES = ("127.0.0.1", "localhost", "::1")


class _Rechazo(Exception):
	"""La sala (o una comprobación propia) ha rechazado la conexión."""

	def __init__(self, motivo: str, espera_s: float = 0.0) -> None:
		super().__init__(motivo)
		self.motivo = motivo
		self.espera_s = espera_s


class ClienteSupervision:
	"""Conexión del reproductor con la sala del Estudio.

	:param host: dirección de la sala.
	:param puerto: puerto de la sala.
	:param codigo: código de emparejamiento que dicta el profesional.
	:param alias: alias del alumno. Es lo ÚNICO suyo que viaja por la red.
	:param entorno, actividad, modo: lo que se está jugando (nombres para mostrar).
	:param recorrido: True si es el modo recorrido del profesional.
	:param tls: None para decidir solo (sin TLS únicamente en 127.0.0.1); True o False para forzarlo.
	:param almacen: dónde se recuerdan las huellas; por defecto ``data/config/salas_conocidas.json``.
	:param intervalo_estado: segundos entre estados (0,2 = 5 por segundo).
	"""

	def __init__(
		self,
		host: str,
		puerto: int = PUERTO_SALA,
		codigo: str = "",
		alias: str = "",
		*,
		entorno: str = "",
		actividad: str = "",
		modo: str = "juego",
		recorrido: bool = False,
		tls: bool | None = None,
		almacen: seguridad.AlmacenHuellas | None = None,
		carpeta_config: Path | str | None = None,
		intervalo_estado: float = 0.2,
		intervalo_latido: float = 2.0,
		tiempo_muerto: float = 6.0,
		reintento_min: float = 0.5,
		reintento_max: float = 10.0,
		espera_conexion: float = 5.0,
	) -> None:
		self.host = host.strip()
		self.puerto = int(puerto)
		self.alias = " ".join(alias.split())[:60] or "invitado"
		self._codigo = codigo
		self._contexto_juego = {"entorno": entorno[:200], "actividad": actividad[:200], "modo": modo[:20]}
		self._recorrido = recorrido
		self.tls = tls if tls is not None else self.host.lower() not in _DIRECCIONES_LOCALES
		if almacen is not None:
			self._almacen = almacen
		elif carpeta_config is not None:
			self._almacen = seguridad.AlmacenHuellas(Path(carpeta_config) / seguridad.NOMBRE_HUELLAS)
		else:
			self._almacen = seguridad.AlmacenHuellas()
		self._intervalo_estado = intervalo_estado
		self._intervalo_latido = intervalo_latido
		self._tiempo_muerto = tiempo_muerto
		self._reintento_min = reintento_min
		self._reintento_max = reintento_max
		self._espera_conexion = espera_conexion
		# Identifica a ESTE reproductor entre reconexiones (no a la persona): la sala conserva su ficha.
		self._instancia = uuid.uuid4().hex
		self._candado = threading.Lock()
		self._salida: deque[tuple[str, dict[str, Any]]] = deque(maxlen=_COLA_SALIDA)
		self._estado: dict[str, Any] | None = None
		self._ordenes: deque[tuple[str, dict[str, Any]]] = deque(maxlen=_COLA_ORDENES)
		self._avisos: deque[tuple[str, dict[str, Any]]] = deque(maxlen=_COLA_ORDENES)
		self._parar = threading.Event()
		self._despertar = threading.Event()
		self._hilo: threading.Thread | None = None
		self._siguiente_peticion = 1
		self._huella_pendiente = ""
		self._campos_avisados: set[str] = set()
		# seq del último mensaje nuestro que la sala dice haber tratado (acuse en sus latidos).
		self._visto = -1
		self.estado_conexion = PARADO
		self.motivo_rechazo = ""
		self.huella_sala = ""
		self.alumno_en_sala = ""
		self.nombre_sala = ""
		self.conexiones = 0

	# ── Lo que llama el juego (nunca bloquea) ────────────────────────────────

	@property
	def conectado(self) -> bool:
		"""True mientras hay conexión emparejada con la sala."""
		return self.estado_conexion == CONECTADO

	def iniciar(self) -> None:
		"""Arranca el hilo del cliente. Vuelve al momento; la conexión llega después."""
		if self._hilo is not None and self._hilo.is_alive():
			return
		self._parar.clear()
		self._despertar.clear()
		self.estado_conexion = CONECTANDO
		self._hilo = threading.Thread(target=self._bucle, name="cliente-supervision", daemon=True)
		self._hilo.start()

	def detener(self, espera: float = 2.0) -> None:
		"""Para el cliente. Espera como mucho ``espera`` segundos a que salga lo pendiente (el ``fin``)."""
		self._parar.set()
		self._despertar.set()
		hilo = self._hilo
		if hilo is not None:
			hilo.join(timeout=max(0.0, espera))
		self._hilo = None
		self.estado_conexion = PARADO

	def estado(self, datos: dict[str, Any] | None = None, **campos: Any) -> None:
		"""Deja el estado actual del alumno; el hilo envía el último 5 veces por segundo.

		Campos: ``planta``, ``x``, ``y``, ``rumbo``, ``espacio``,
		``descripcion`` (posición en palabras), ``delante``, ``pausado``,
		``tiempo_activo`` y ``contadores`` (distancia, choques, ayudas...).
		Se puede pasar tal cual ``Sesion.estado()``: lo que sobra se descarta.
		"""
		nuevo = dict(datos or {})
		nuevo.update(campos)
		limpio, descartados = protocolo.filtrar("estado", nuevo, A_ESTUDIO)
		for campo in descartados:
			if campo not in self._campos_avisados:
				# Una sola vez por campo: esto se llama en cada fotograma.
				self._campos_avisados.add(campo)
				log.warning("El campo «%s» del estado no tiene el tipo esperado y no se envía", campo)
		with self._candado:
			self._estado = limpio

	def evento(self, tipo: str, datos: dict[str, Any] | None = None) -> None:
		"""Envía un suceso (un ``EvRegistro``: choque, ayuda, objetivo, premio...)."""
		self._encolar("evento", {"tipo": str(tipo)[:40], "datos": dict(datos or {})})

	def voz(self, texto: str, canal: str = "juego") -> None:
		"""Envía lo que acaba de oír el alumno, para que el profesional lo lea."""
		if not self.conectado or not texto:
			# La voz atrasada no sirve de nada al reconectar: solo se envía en vivo.
			return
		self._encolar("voz", {"texto": texto[:2000], "canal": canal[:20]})

	def fin(self, completada: bool = False, resultado: dict[str, Any] | None = None) -> None:
		"""Avisa de que la sesión ha terminado.

		Olvida además el último estado: el hilo lo reenvía cinco veces por
		segundo, y repetirlo tras el ``fin`` le diría a la sala que sigue la
		misma sesión. Con menos de un segundo de juego, la sala lo tomaba por
		el primer estado de una sesión nueva (tras «reiniciar») y volvía a
		marcar al alumno como no terminado. El siguiente ``estado()`` (otra
		partida) vuelve a enviarse con normalidad.
		"""
		with self._candado:
			self._estado = None
			self._salida.append(("fin", {"completada": bool(completada), "resultado": dict(resultado or {})}))

	def peticion(self, accion: str, **datos: Any) -> int:
		"""Modo recorrido: pide algo al Estudio y devuelve el id de la petición.

		``accion``: ``colocar_aqui``, ``marcar_punto`` o ``medir_desde_aqui``.
		Los datos ``planta``, ``x``, ``y`` y ``rumbo`` dicen dónde está el
		profesional; cualquier otro va en ``datos``. La respuesta llega por
		``ordenes_pendientes()`` como ``("respuesta", {"id", "aceptada", "texto", "datos"})``.
		"""
		if accion not in ACCIONES_PETICION:
			raise ValueError(f"petición desconocida: {accion}")
		with self._candado:
			ident = self._siguiente_peticion
			self._siguiente_peticion += 1
		cuerpo: dict[str, Any] = {"id": ident, "accion": accion}
		extra: dict[str, Any] = {}
		for clave, valor in datos.items():
			if clave in ("planta", "x", "y", "rumbo"):
				cuerpo[clave] = valor
			else:
				extra[clave] = valor
		cuerpo["datos"] = extra
		self._encolar("peticion", cuerpo)
		return ident

	def ordenes_pendientes(self) -> list[tuple[str, dict[str, Any]]]:
		"""Devuelve y vacía las órdenes recibidas del Estudio, por orden de llegada.

		Tipos: ``pausa``, ``reanudar``, ``recolocar``, ``mensaje``, ``pista``,
		``ayudas``, ``premio``, ``marca``, ``reiniciar``, ``terminar`` y
		``respuesta`` (a una ``peticion``). El bucle del juego la llama una
		vez por fotograma.
		"""
		with self._candado:
			pendientes = list(self._ordenes)
			self._ordenes.clear()
		return pendientes

	def avisos_pendientes(self) -> list[tuple[str, dict[str, Any]]]:
		"""Cambios de la conexión, para decírselos a quien juega si procede.

		Tipos: ``conectado``, ``desconectado`` (``motivo``), ``rechazado``
		(``motivo``: codigo, bloqueado, version, lleno, huella, sala, protocolo,
		expulsado; y ``espera_s``).
		"""
		with self._candado:
			pendientes = list(self._avisos)
			self._avisos.clear()
		return pendientes

	def cambiar_contexto(self, entorno: str = "", actividad: str = "", modo: str = "juego") -> None:
		"""Cambia lo que se anuncia a la sala (al empezar otra actividad sin cerrar el reproductor)."""
		with self._candado:
			self._contexto_juego = {"entorno": entorno[:200], "actividad": actividad[:200], "modo": modo[:20]}

	def cambiar_codigo(self, codigo: str) -> None:
		"""Pone otro código (el anterior era incorrecto) y vuelve a intentarlo."""
		self._codigo = codigo
		self.reintentar()

	def aceptar_huella_nueva(self) -> None:
		"""La persona confirma que la sala ha cambiado de certificado: se recuerda la huella nueva y se reintenta."""
		if self._huella_pendiente:
			self._almacen.recordar(self.host, self.puerto, self._huella_pendiente)
			self._huella_pendiente = ""
		self.reintentar()

	def reintentar(self) -> None:
		"""Vuelve a intentar la conexión tras un rechazo."""
		self.motivo_rechazo = ""
		self._despertar.set()

	def _encolar(self, tipo: str, datos: dict[str, Any]) -> None:
		with self._candado:
			self._salida.append((tipo, datos))

	def _avisar(self, tipo: str, datos: dict[str, Any] | None = None) -> None:
		with self._candado:
			self._avisos.append((tipo, datos or {}))

	# ── Hilo del cliente ─────────────────────────────────────────────────────

	def _bucle(self) -> None:
		espera = self._reintento_min
		while not self._parar.is_set():
			self.estado_conexion = CONECTANDO
			enchufe: socket.socket | None = None
			motivo = "red"
			try:
				enchufe = self._conectar()
				espera = self._reintento_min
				self.conexiones += 1
				self.estado_conexion = CONECTADO
				self.motivo_rechazo = ""
				self._avisar("conectado", {"sala": self.nombre_sala, "cifrada": self.tls})
				log.info("Conectado con la sala de supervisión")
				motivo = self._atender(enchufe)
			except _Rechazo as rechazo:
				motivo = rechazo.motivo
				if self._tras_rechazo(rechazo):
					continue
			except (OSError, ssl.SSLError, ErrorProtocolo) as error:
				# Sala cerrada, red caída, cortafuegos: lo normal es reintentar en silencio.
				log.debug("Sin conexión con la sala (%s)", type(error).__name__)
			finally:
				if enchufe is not None:
					if motivo == "parado":
						_despedir(enchufe)
					_cerrar(enchufe)
			if self.estado_conexion == CONECTADO:
				self._avisar("desconectado", {"motivo": motivo})
				log.info("Conexión con la sala perdida (%s)", motivo)
			if self._parar.is_set():
				break
			self.estado_conexion = ESPERANDO
			self._despertar.clear()
			self._despertar.wait(espera)
			espera = min(self._reintento_max, espera * 2.0)
		self.estado_conexion = PARADO

	def _tras_rechazo(self, rechazo: _Rechazo) -> bool:
		"""Decide qué hacer tras un rechazo. Devuelve True si ya se ha esperado aquí y hay que reintentar ya."""
		self.motivo_rechazo = rechazo.motivo
		self._avisar("rechazado", {"motivo": rechazo.motivo, "espera_s": rechazo.espera_s})
		log.warning("La sala ha rechazado la conexión (%s)", rechazo.motivo)
		if rechazo.motivo in ("lleno", "cierre"):
			# Pasajero: se reintenta con la espera normal.
			return False
		self.estado_conexion = RECHAZADO
		self._despertar.clear()
		if rechazo.motivo == "bloqueado" and rechazo.espera_s > 0:
			# Bloqueo temporal por intentos: se espera lo que dice la sala y se prueba otra vez.
			self._despertar.wait(rechazo.espera_s + 0.5)
		else:
			# Código incorrecto, huella cambiada, otra versión...: insistir no arregla nada.
			# Se espera a que el juego llame a cambiar_codigo, aceptar_huella_nueva o reintentar.
			self._despertar.wait()
		return True

	def _conectar(self) -> socket.socket:
		"""Abre la conexión y hace el emparejamiento. Devuelve el enchufe ya emparejado."""
		enchufe: socket.socket = socket.create_connection((self.host, self.puerto), timeout=self._espera_conexion)
		try:
			enchufe.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
			huella = ""
			if self.tls:
				enchufe = seguridad.contexto_cliente().wrap_socket(enchufe)
				der = enchufe.getpeercert(binary_form=True)  # type: ignore[attr-defined]
				if not der:
					raise _Rechazo("sala")
				huella = seguridad.huella_de_der(der)
				conocida = self._almacen.obtener(self.host, self.puerto)
				if conocida is not None and conocida != huella:
					# No se envía nada más: ni el alias ni la prueba del código llegan a una sala distinta.
					self._huella_pendiente = huella
					self.huella_sala = huella
					raise _Rechazo("huella")
			enchufe.settimeout(self._espera_conexion)
			troceador = LectorLineas()
			reto = self._leer_uno(enchufe, troceador)
			if reto.tipo == "rechazo":
				raise _Rechazo(reto.datos["motivo"], float(reto.datos.get("espera_s", 0.0)))
			if reto.tipo != "reto":
				raise ErrorProtocolo("tipo", "se esperaba el reto")
			nonce = seguridad.nuevo_nonce()
			with self._candado:
				contexto = dict(self._contexto_juego)
			saludo = {
				"alias": self.alias,
				"instancia": self._instancia,
				"nonce": nonce,
				"prueba": seguridad.prueba_cliente(self._codigo, reto.datos["nonce"], nonce, huella),
				"recorrido": self._recorrido,
				"version_app": APP_VERSION,
				**contexto,
			}
			enchufe.sendall(protocolo.codificar("hola", saludo, sentido=A_ESTUDIO, seq=0, t=0.0))
			respuesta = self._leer_uno(enchufe, troceador)
			if respuesta.tipo == "rechazo":
				raise _Rechazo(respuesta.datos["motivo"], float(respuesta.datos.get("espera_s", 0.0)))
			if respuesta.tipo != "bienvenida":
				raise ErrorProtocolo("tipo", "se esperaba la bienvenida")
			esperada = seguridad.prueba_sala(self._codigo, reto.datos["nonce"], nonce, huella)
			if not seguridad.pruebas_iguales(esperada, respuesta.datos["prueba"]):
				# Quien responde no conoce el código: no es la sala del profesional.
				raise _Rechazo("sala")
			if self.tls and self._almacen.obtener(self.host, self.puerto) is None:
				self._almacen.recordar(self.host, self.puerto, huella)
			self.huella_sala = huella
			self.alumno_en_sala = respuesta.datos.get("alumno", "")
			self.nombre_sala = respuesta.datos.get("nombre", "")
			return enchufe
		except BaseException:
			_cerrar(enchufe)
			raise

	@staticmethod
	def _leer_uno(enchufe: socket.socket, troceador: LectorLineas) -> protocolo.Mensaje:
		"""Lee un mensaje completo durante el emparejamiento (con el tiempo límite del enchufe)."""
		while True:
			datos = enchufe.recv(4096)
			if not datos:
				raise ConnectionError("la sala ha cerrado la conexión")
			lineas = troceador.alimentar(datos)
			if not lineas:
				continue
			if lineas[0] is None:
				raise ErrorProtocolo("tamano", "línea demasiado larga")
			return protocolo.decodificar(lineas[0], A_JUGAR)

	def _atender(self, enchufe: socket.socket) -> str:
		"""Bucle de una conexión emparejada. Devuelve el motivo por el que termina."""
		inicio = time.monotonic()
		seq = 1
		ultimo_envio = inicio
		ultimo_estado = 0.0
		ultimo_recibido = inicio
		seq_fin = -1
		self._visto = -1
		troceador = LectorLineas()
		enchufe.settimeout(5.0)

		def enviar(tipo: str, datos: dict[str, Any]) -> None:
			nonlocal seq, ultimo_envio, seq_fin
			try:
				linea = protocolo.codificar(tipo, datos, sentido=A_ESTUDIO, seq=seq, t=time.monotonic() - inicio)
			except ErrorProtocolo as error:
				# Un dato raro del juego no debe tumbar la supervisión: se descarta ese mensaje.
				log.error("Mensaje de supervisión no válido (%s, %s): no se envía", tipo, error.codigo)
				return
			enchufe.sendall(linea)
			if tipo == "fin":
				seq_fin = seq
			seq += 1
			ultimo_envio = time.monotonic()

		try:
			while True:
				ahora = time.monotonic()
				# Se mira ANTES de vaciar la cola: lo encolado justo antes de detener() (el «fin») aún sale.
				parando = self._parar.is_set()
				while True:
					with self._candado:
						pendiente = self._salida[0] if self._salida else None
					if pendiente is None:
						break
					enviar(pendiente[0], pendiente[1])
					with self._candado:
						# Solo se quita de la cola una vez enviado: si falla el envío, se reintenta al reconectar.
						if self._salida and self._salida[0] is pendiente:
							self._salida.popleft()
				if parando:
					if seq_fin > self._visto:
						self._esperar_acuse(enchufe, troceador, seq_fin)
					return "parado"
				if ahora - ultimo_estado >= self._intervalo_estado:
					with self._candado:
						actual = dict(self._estado) if self._estado is not None else None
						contexto = dict(self._contexto_juego)
					if actual is not None:
						enviar("estado", {**contexto, **actual})
						ultimo_estado = ahora
				if ahora - ultimo_envio >= self._intervalo_latido:
					enviar("latido", {})
				hay_datos = bool(getattr(enchufe, "pending", lambda: 0)())
				if not hay_datos:
					legibles, _escribibles, _errores = select.select([enchufe], [], [], min(0.05, self._intervalo_estado))
					hay_datos = bool(legibles)
				if hay_datos:
					datos = enchufe.recv(4096)
					if not datos:
						return "corte"
					ultimo_recibido = time.monotonic()
					for linea in troceador.alimentar(datos):
						motivo = self._recibir(linea)
						if motivo:
							return motivo
				elif time.monotonic() - ultimo_recibido > self._tiempo_muerto:
					return "sin_latido"
		except (OSError, ssl.SSLError, ValueError) as error:
			log.debug("Conexión con la sala cortada (%s)", type(error).__name__)
			return "corte"

	def _esperar_acuse(self, enchufe: socket.socket, troceador: LectorLineas, objetivo: int, plazo: float = 1.0) -> bool:
		"""Espera (poco) a que la sala confirme que ha tratado el ``fin`` antes de cerrar.

		Cerrar justo después de enviar puede hacer que el otro lado vea la
		conexión cortada antes de leer lo último (se ha visto en Windows,
		incluso en 127.0.0.1). Solo se espera al parar, nunca durante el juego.
		"""
		limite = time.monotonic() + plazo
		while self._visto < objetivo:
			queda = limite - time.monotonic()
			if queda <= 0:
				log.debug("La sala no ha confirmado el fin de la sesión a tiempo")
				return False
			hay_datos = bool(getattr(enchufe, "pending", lambda: 0)())
			if not hay_datos:
				legibles, _escribibles, _errores = select.select([enchufe], [], [], min(0.05, queda))
				hay_datos = bool(legibles)
			if not hay_datos:
				continue
			datos = enchufe.recv(4096)
			if not datos:
				return False
			for linea in troceador.alimentar(datos):
				if self._recibir(linea):
					return False
		return True

	def _recibir(self, linea: bytes | None) -> str:
		"""Trata una línea de la sala. Devuelve un motivo si hay que cerrar la conexión."""
		try:
			if linea is None:
				raise ErrorProtocolo("tamano", "línea demasiado larga")
			mensaje = protocolo.decodificar(linea, A_JUGAR)
		except ErrorProtocolo as error:
			# Se ignora el mensaje y se sigue: una orden rota no debe cortar la sesión del alumno.
			log.warning("Mensaje de la sala rechazado (%s)", error.codigo)
			return ""
		if mensaje.tipo == "latido":
			self._visto = max(self._visto, int(mensaje.datos.get("visto", -1)))
			return ""
		if mensaje.tipo == "rechazo":
			motivo = mensaje.datos["motivo"]
			if motivo == "expulsado":
				raise _Rechazo(motivo)
			return motivo
		if mensaje.tipo in ("reto", "bienvenida"):
			return ""
		with self._candado:
			self._ordenes.append((mensaje.tipo, mensaje.datos))
		return ""


def _despedir(enchufe: socket.socket) -> None:
	"""Cierre ordenado al parar: da tiempo a que la sala reciba lo último enviado (el ``fin``).

	Cerrar de golpe con datos de la sala sin leer puede hacer que el sistema
	corte la conexión con un RST y la sala pierda las últimas líneas.
	"""
	try:
		enchufe.shutdown(socket.SHUT_WR)
		enchufe.settimeout(0.3)
		limite = time.monotonic() + 1.0
		while time.monotonic() < limite:
			if not enchufe.recv(4096):
				break
	except OSError, ssl.SSLError, ValueError:
		log.debug("La sala no ha confirmado el cierre a tiempo")


def _cerrar(enchufe: socket.socket) -> None:
	"""Cierra un enchufe sin que un error al cerrar tape el motivo real."""
	try:
		enchufe.close()
	except OSError:
		log.debug("Error al cerrar la conexión de supervisión", exc_info=True)
