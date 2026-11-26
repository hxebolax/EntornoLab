"""La sesión de juego: recibe órdenes, hace avanzar el mundo y devuelve eventos.

Es la única puerta del motor. El reproductor hace, una vez por fotograma::

    sesion.orden("avanzar")                  # al pulsar; orden("avanzar", 0) al soltar
    sesion.analogico(avance, lateral, giro, mirada)
    eventos = sesion.avanzar(dt)
    presentador.aplicar(eventos, sesion, dt)

y la sesión no sabe nada de teclas, ventanas ni altavoces: se prueba entera
con un «robot» que da órdenes y mira los eventos.

Protección frente a la sobrecarga: lo que el alumno PIDE se dice al momento
e interrumpe; lo que el motor dice por su cuenta espera su turno en una cola
pequeña, con prioridades, y caduca si deja de ser cierto antes de llegar a
decirse. Así nunca se encadenan más de unos pocos avisos automáticos.

Una actividad (cualquier objeto, por «duck typing») puede colgarse de la
sesión con estos ganchos, todos opcionales y que devuelven una lista de
eventos (o nada): ``al_empezar(sesion)``, ``tras_mover(sesion)``,
``al_interactuar(sesion, elemento)``, ``tic(sesion, dt)``,
``al_pedir(sesion, accion)``, ``al_registrar(sesion, registro)`` (cada
``EvRegistro`` que sale de la sesión, también los del propio motor) y
``resultado(sesion) -> dict``. Ver ``docs/motor.md``.
"""

from __future__ import annotations

import dataclasses
import heapq
import logging
import math
import random
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.core.configuracion import VALORES_POR_DEFECTO
from app.core.i18n import _
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Entorno, Posicion
from app.motor import eventos as ev
from app.motor import lenguaje as leng
from app.motor import movimiento as mov
from app.motor.acustica import Acustica, Emisor
from app.motor.dinamica import Dinamica
from app.motor.eventos import Evento, FuenteActiva
from app.motor.mundo import Mundo, Progreso
from app.motor.navegacion import Navegador, Ruta, lugar
from app.motor.percepcion import AYUDAS, Percepcion

log = logging.getLogger(__name__)

# Altura de los oídos sobre el suelo.
ALTURA_OIDOS = 1.6
# Un fotograma nunca avanza más que esto: tras un parón no se da un salto.
DT_MAXIMO = 0.25
# Frases automáticas que pueden estar esperando turno.
MAX_COLA_VOZ = 4
DISTANCIA_LLEGADA_BALIZA = 0.9
# Segundos que la pantalla de carga dedica, como mucho, a calcular por adelantado los caminos alrededor del inicio.
PRESUPUESTO_PREPARAR_CAMINOS = 2.0
# Ajustes de juego de serie: los mismos que enseñan las preferencias.
_JUEGO_DE_SERIE: dict[str, Any] = VALORES_POR_DEFECTO["juego"]


@dataclass
class AjustesJuego:
	"""Cómo se mueve y qué se le dice a un alumno. Los fija su ficha y los retoca la actividad."""

	# Los valores de serie son los de las preferencias (``app.core.configuracion``): una sola fuente de verdad,
	# la que ve el usuario. tests/test_motor_sesion.py vigila que no se separen.
	modo_movimiento: str = str(_JUEGO_DE_SERIE["modo_movimiento"])  # pasos | continuo | brujula | salas | aceras
	paso_m: float = float(_JUEGO_DE_SERIE["paso_m"])
	giro_grados: float = float(_JUEGO_DE_SERIE["giro_grados"])  # 90, 45, 15…; 0 = giro libre mientras se mantiene
	velocidad_ms: float = float(_JUEGO_DE_SERIE["velocidad_ms"])
	formato_direccion: str = str(_JUEGO_DE_SERIE["formato_direccion"])  # reloj | lados | cardinal | grados
	unidad: str = str(_JUEGO_DE_SERIE["unidad"])  # metros | pasos
	detalle: int = int(VALORES_POR_DEFECTO["voz"]["detalle"])  # 0 (solo sonidos) a 3 (todo)
	ayudas: dict[str, dict[str, Any]] = field(default_factory=dict)  # ayuda → {"permitida": bool, "limite": int | None}
	estilo: str = str(_JUEGO_DE_SERIE["estilo"])  # infantil | juvenil | adulto
	radio_m: float = 0.25
	alcance_sonda: float = 8.0
	trafico: bool = True

	def __post_init__(self) -> None:
		# Las reglas de las ayudas pueden venir abreviadas (False, un número): se dejan siempre completas.
		self.ayudas = {str(nombre): regla_ayuda(regla) for nombre, regla in dict(self.ayudas or {}).items()}

	def a_dict(self) -> dict[str, Any]:
		"""Diccionario con tipos básicos, listo para JSON."""
		datos = dataclasses.asdict(self)
		datos["ayudas"] = {nombre: dict(regla) for nombre, regla in self.ayudas.items()}
		return datos

	@classmethod
	def de_dict(cls, datos: Any) -> AjustesJuego:
		"""Lee los ajustes de forma tolerante: lo que falta o no vale toma su valor de serie, y todo queda en rango."""
		ajustes = cls()
		if not isinstance(datos, dict):
			return ajustes

		def numero(clave: str, minimo: float, maximo: float) -> None:
			if clave not in datos:
				return
			try:
				valor = float(datos[clave])
			except TypeError, ValueError:
				log.warning("Ajuste de juego no válido: %s = %r; se usa el valor de serie", clave, datos[clave])
				return
			if math.isfinite(valor):
				setattr(ajustes, clave, max(minimo, min(maximo, valor)))

		def elegir(clave: str, validos: tuple[str, ...]) -> None:
			if clave in datos and datos[clave] in validos:
				setattr(ajustes, clave, datos[clave])
			elif clave in datos:
				log.warning("Ajuste de juego no válido: %s = %r; se usa el valor de serie", clave, datos[clave])

		elegir("modo_movimiento", mov.MODOS)
		elegir("formato_direccion", leng.FORMATOS)
		elegir("unidad", leng.UNIDADES)
		elegir("estilo", leng.ESTILOS)
		numero("paso_m", 0.25, 1.5)
		numero("giro_grados", 0.0, 180.0)
		numero("velocidad_ms", 0.3, 3.0)
		numero("radio_m", 0.1, 0.6)
		numero("alcance_sonda", 1.0, 30.0)
		if "detalle" in datos:
			try:
				ajustes.detalle = max(0, min(3, int(datos["detalle"])))
			except TypeError, ValueError:
				log.warning("Nivel de detalle no válido: %r; se usa el de serie", datos["detalle"])
		if "trafico" in datos:
			ajustes.trafico = bool(datos["trafico"])
		ayudas = datos.get("ayudas")
		if isinstance(ayudas, dict):
			for nombre, regla in ayudas.items():
				ajustes.ayudas[str(nombre)] = regla_ayuda(regla)
		return ajustes


def regla_ayuda(regla: Any) -> dict[str, Any]:
	"""Normaliza la regla de una ayuda: admite ``True``/``False``, un número (límite) o el diccionario completo."""
	if isinstance(regla, bool):
		return {"permitida": regla, "limite": None}
	if isinstance(regla, (int, float)):
		return {"permitida": True, "limite": max(0, int(regla))}
	if isinstance(regla, dict):
		limite = regla.get("limite")
		try:
			limite = None if limite is None else max(0, int(limite))
		except TypeError, ValueError:
			limite = None
		return {"permitida": bool(regla.get("permitida", True)), "limite": limite}
	return {"permitida": True, "limite": None}


@dataclass
class _Frase:
	"""Una frase automática que espera turno."""

	texto: str
	canal: str
	prioridad: int
	caduca: float
	clave: str
	vale: Callable[[], bool] | None
	orden: int


@dataclass
class _Baliza:
	"""Un destino que suena para guiar hacia él."""

	destino: tuple[str, float, float]
	por_ruta: bool
	sonido: str
	t: float = 0.0
	ruta: Ruta | None = None
	ruta_en: tuple[str, float, float] | None = None


class Sesion:
	"""Una partida: un alumno recorriendo un entorno, con o sin actividad."""

	def __init__(
		self,
		entorno: Entorno,
		catalogo: Catalogo | None,
		ajustes: AjustesJuego | None = None,
		actividad: Any = None,
		semilla: int | None = None,
		inicio: Posicion | None = None,
		progreso: Progreso | None = None,
	) -> None:
		"""``semilla`` hace reproducible todo lo que depende del azar (tráfico, variantes de los pasos, fases).

		``progreso(fase, hechos, total)`` cuenta cómo va la preparación de un
		entorno grande (fases ``plantas``, ``paredes``, ``aberturas`` y
		``objetos`` del ``Mundo``; ver también ``preparar``). Se llama desde
		el hilo que construye la sesión; si lanza una excepción, la
		construcción se interrumpe ahí (así se cancela una carga).
		"""
		self.entorno = entorno
		self.catalogo = catalogo if catalogo is not None else Catalogo()
		self.ajustes = ajustes if ajustes is not None else AjustesJuego()
		self.actividad = actividad
		self.semilla = semilla if semilla is not None else random.SystemRandom().randrange(1, 2**31)
		self.azar = random.Random(self.semilla)
		self.mundo = Mundo(entorno, self.catalogo, progreso)
		self.nav = Navegador(self.mundo)
		self.leng = leng.Lenguaje(self.ajustes.formato_direccion, self.ajustes.unidad, self.ajustes.paso_m, self.ajustes.estilo)
		self.inicio = self._inicio_valido(inicio if inicio is not None else entorno.inicio)
		self.jugador = mov.Jugador(self.inicio.planta, self.inicio.x, self.inicio.y, self.inicio.rumbo % 360.0, self.ajustes.radio_m)
		# Tiempo activo (sin pausas), que es el que cuentan los exámenes, y tiempo en pausa aparte.
		self.t = 0.0
		self.tiempo_pausa = 0.0
		self.pausado = False
		self.terminado = False
		self.resultado: dict[str, Any] = {}
		self.contadores: dict[str, int] = {}
		self._salida: list[Evento] = []
		# Registros que esperan a pasar por el gancho «al_registrar» (ver ``_avisar_registro``).
		self._registros_por_avisar: list[ev.EvRegistro] = []
		self._avisando_registros = False
		self._ordenes: list[tuple[str, bool]] = []
		self._mirada: tuple[float, float] | None = None
		self._programados: list[tuple[float, int, str, Any]] = []
		self._numero = 0
		self._cola_voz: list[_Frase] = []
		self._voz_libre = 0.0
		self._empezada = False
		self._baliza: _Baliza | None = None
		self.movimiento = mov.Movimiento(self)
		self.percepcion = Percepcion(self)
		self.acustica = Acustica(self)
		self.dinamica = Dinamica(self)

	def preparar(self, progreso: Progreso | None = None, presupuesto_caminos: float = PRESUPUESTO_PREPARAR_CAMINOS) -> None:
		"""Calcula ya lo que la primera consulta calcularía de golpe: el grafo de espacios, los caminos y el sonido.

		Lo llama la pantalla de carga del reproductor, mientras el alumno ya
		está esperando: en un barrio importado, el grafo de espacios (que usa
		«dónde estoy» dicho dos veces y el movimiento por salas) y los caminos
		alrededor del inicio tardaban segundos en la primera petición. Los
		resultados son exactamente los mismos que si se calcularan después; los
		caminos que no quepan en ``presupuesto_caminos`` segundos se terminan
		de calcular poco a poco durante la partida (``Navegador.precalcular``).
		Las fases que se avisan son ``caminos`` y ``sonido``.
		"""
		if progreso is not None:
			progreso("caminos", 0, 2)
		self.nav.grafo_espacios()
		if progreso is not None:
			progreso("caminos", 1, 2)
		limite = time.perf_counter() + max(0.0, presupuesto_caminos)
		jugador = self.jugador
		while not self.nav.precalcular((jugador.planta, jugador.x, jugador.y), min(0.2, max(0.0, limite - time.perf_counter()))):
			if progreso is not None:
				progreso("caminos", 1, 2)
			if time.perf_counter() >= limite:
				break
		if progreso is not None:
			progreso("caminos", 2, 2)
			progreso("sonido", 0, 1)
		self.acustica.fuentes()
		if progreso is not None:
			progreso("sonido", 1, 1)

	def _inicio_valido(self, inicio: Posicion) -> Posicion:
		"""El inicio pedido si su planta existe; si no, el centro del primer espacio de la primera planta."""
		if self.mundo.planta(inicio.planta) is not None:
			return Posicion(inicio.planta, inicio.x, inicio.y, inicio.rumbo)
		for indice in self.mundo.plantas():
			for _caja, espacio in indice.espacios:
				if not espacio.macizo:
					centro = espacio.centro()
					log.warning("El inicio apunta a una planta que no existe; se empieza en %s", espacio.nombre or espacio.id)
					return Posicion(indice.planta.id, centro[0], centro[1], 0.0)
		plantas = self.mundo.plantas()
		return Posicion(plantas[0].planta.id if plantas else "", 0.0, 0.0, 0.0)

	# ── Entrada ──

	def orden(self, accion: str, valor: float = 1.0) -> None:
		"""Apunta una acción de ``app/entrada/acciones.py``; ``valor`` 0 es soltar una acción mantenida.

		Se atiende en la siguiente llamada a ``avanzar``, que es quien devuelve los eventos.
		"""
		self._ordenes.append((str(accion), float(valor) > 0.5))

	def analogico(self, avance: float, lateral: float, giro: float, mirada: tuple[float, float] | None = None) -> None:
		"""Posición de las palancas, de -1 a 1; ``mirada`` es (derecha, delante) de la palanca de mirar."""
		self.movimiento.analogico(avance, lateral, giro)
		self._mirada = mirada

	def avanzar(self, dt: float) -> list[Evento]:
		"""Hace avanzar la partida ``dt`` segundos y devuelve lo ocurrido."""
		dt = max(0.0, min(DT_MAXIMO, float(dt)))
		if self.terminado:
			self._ordenes.clear()
			return self._vaciar()
		if self.pausado:
			self.tiempo_pausa += dt
			self._ordenes.clear()
			return self._vaciar()
		if not self._empezada:
			self._empezar()
		self.t += dt
		ordenes, self._ordenes = self._ordenes, []
		for accion, pulsada in ordenes:
			self._atender(accion, pulsada)
			if self.terminado:
				return self._vaciar()
		self.percepcion.mirada(self._mirada)
		self.movimiento.tic(dt)
		self.dinamica.tic(dt)
		self.percepcion.tic(dt)
		self.acustica.tic(dt)
		self._tic_baliza(dt)
		self._soltar_programados()
		self.gancho("tic", dt)
		self._despachar_voz()
		return self._vaciar()

	def _vaciar(self) -> list[Evento]:
		salida, self._salida = self._salida, []
		return salida

	def _empezar(self) -> None:
		self._empezada = True
		self.registrar(
			"inicio", entorno=self.entorno.id, semilla=self.semilla, modo=self.ajustes.modo_movimiento, rumbo=round(self.jugador.rumbo, 1)
		)
		# Primero la actividad (su mensaje de inicio, sus premios) y después el anuncio del lugar donde se empieza.
		self.gancho("al_empezar")
		self.movimiento.tras_mover(None, forzar=True)

	def _atender(self, accion: str, pulsada: bool) -> None:
		if self.movimiento.orden(accion, pulsada):
			return
		if self.percepcion.orden(accion, pulsada):
			return
		if not pulsada:
			return
		if accion in ("objetivo", "pista"):
			if self.percepcion.usar(accion):
				if not self.gancho("al_pedir", accion):
					if accion == "objetivo":
						self.decir(_("No hay ningún objetivo: explora con libertad."), canal="ayuda", pedida=True, clave="objetivo")
					else:
						self.decir(_("Ahora no hay ninguna pista."), canal="ayuda", pedida=True, clave="objetivo")
		elif accion == "volver_inicio":
			self.recolocar(self.inicio)
			self.decir(_("Has vuelto al inicio."), canal="juego", pedida=True, clave="inicio")
			self.registrar("volver_inicio")
		else:
			# Repetir, historial, callar, ayuda, pausa y menús son cosa del reproductor.
			log.debug("Acción que no atiende el motor: %s", accion)

	# ── Salida: eventos ──

	def emitir(self, evento: Evento) -> None:
		"""Añade un evento a lo que devolverá ``avanzar`` (un ``EvRegistro`` pasa además por ``al_registrar``)."""
		self._salida.append(evento)
		if isinstance(evento, ev.EvRegistro):
			self._avisar_registro(evento)

	def _avisar_registro(self, registro: ev.EvRegistro) -> None:
		"""Pasa un registro recién emitido al gancho ``al_registrar`` de la actividad.

		Si la actividad registra algo mientras atiende un registro, el nuevo no
		se le pasa anidado: espera en la cola y se le da al terminar el actual.
		Así la actividad nunca recibe un registro a medias de atender otro y
		el orden de llegada es el de emisión.
		"""
		if self.actividad is None or not callable(getattr(self.actividad, "al_registrar", None)):
			return
		self._registros_por_avisar.append(registro)
		if self._avisando_registros:
			return
		self._avisando_registros = True
		try:
			while self._registros_por_avisar:
				self.gancho("al_registrar", self._registros_por_avisar.pop(0))
		finally:
			self._avisando_registros = False

	def pos3(self, x: float, y: float, altura: float = 1.0) -> tuple[float, float, float]:
		"""Punto (x, y) de la planta del alumno a ``altura`` metros del suelo, en coordenadas del mundo."""
		return x, y, self.mundo.altura(self.jugador.planta) + altura

	def sonar(
		self,
		nombre: str,
		pos: tuple[float, float, float] | None = None,
		relativo: tuple[float, float] | None = None,
		volumen: float = 1.0,
		tono: float = 1.0,
		bus: str = "efectos",
		filtro: float = 0.0,
		retardo: float = 0.0,
		grupo: str = "",
	) -> None:
		"""Emite un sonido, ahora o dentro de ``retardo`` segundos (``grupo`` permite cancelarlo)."""
		evento = ev.EvSonido(nombre, pos, max(0.0, min(1.0, volumen)), tono, bus, max(0.0, min(1.0, filtro)), relativo)
		if retardo > 0.0:
			self.programar(retardo, evento, grupo)
		else:
			self._salida.append(evento)

	def vibrar(self, patron: str, retardo: float = 0.0, grupo: str = "") -> None:
		"""Emite un patrón de vibración del vocabulario de ``app.audio.haptica``."""
		evento = ev.EvVibrar(patron=patron)
		if retardo > 0.0:
			self.programar(retardo, evento, grupo)
		else:
			self._salida.append(evento)

	def registrar(self, tipo: str, /, **datos: Any) -> None:
		"""Emite un ``EvRegistro`` con el lugar y el momento, lo cuenta y se lo pasa a la actividad (``al_registrar``)."""
		jugador = self.jugador
		completos: dict[str, Any] = {
			"t": round(self.t, 3),
			"planta": jugador.planta,
			"x": round(jugador.x, 3),
			"y": round(jugador.y, 3),
			"espacio": self.movimiento.espacio_id or "",
		}
		completos.update(datos)
		self.contadores[tipo] = self.contadores.get(tipo, 0) + 1
		self.emitir(ev.EvRegistro(tipo, completos))

	def programar(self, retardo: float, cosa: Any, grupo: str = "") -> None:
		"""Deja un evento (o una función sin argumentos) para dentro de ``retardo`` segundos de tiempo activo."""
		self._numero += 1
		heapq.heappush(self._programados, (self.t + max(0.0, retardo), self._numero, grupo, cosa))

	def cancelar(self, grupo: str) -> None:
		"""Quita lo programado de un grupo (la sonda anterior al lanzar otra)."""
		if any(g == grupo for _t, _n, g, _c in self._programados):
			self._programados = [p for p in self._programados if p[2] != grupo]
			heapq.heapify(self._programados)

	def _soltar_programados(self) -> None:
		while self._programados and self._programados[0][0] <= self.t + 1e-9:
			_t, _n, _grupo, cosa = heapq.heappop(self._programados)
			if callable(cosa):
				cosa()
			else:
				self.emitir(cosa)

	# ── Voz ──

	@staticmethod
	def _duracion(texto: str) -> float:
		"""Segundos que tarda en decirse una frase, a ojo (el motor no oye la voz)."""
		return 0.3 + 0.045 * len(texto)

	def decir(
		self,
		texto: str,
		canal: str = "juego",
		pedida: bool = False,
		prioridad: int = 1,
		clave: str = "",
		caduca: float = 5.0,
		retardo: float = 0.0,
		grupo: str = "",
		vale: Callable[[], bool] | None = None,
	) -> None:
		"""Dice una frase.

		``pedida``: la ha pedido el alumno; se dice ya, interrumpe y vacía la
		cola de lo automático. Si no, espera turno según ``prioridad`` (3 = no
		espera), sustituye a otra pendiente con la misma ``clave`` y se
		descarta si pasan ``caduca`` segundos o ``vale()`` deja de ser cierto.
		"""
		if not texto:
			return
		if retardo > 0.0:
			self.programar(retardo, lambda: self.decir(texto, canal, pedida, prioridad, clave, caduca, 0.0, "", vale), grupo)
			return
		if canal not in ev.CANALES_VOZ:
			canal = "juego"
		if pedida:
			self._cola_voz = [f for f in self._cola_voz if f.prioridad >= 3]
			self._salida.append(ev.EvVoz(texto, True, canal))
			self._voz_libre = self.t + self._duracion(texto)
			return
		if prioridad >= 3:
			self._salida.append(ev.EvVoz(texto, False, canal))
			self._voz_libre = max(self._voz_libre, self.t) + self._duracion(texto)
			return
		if clave:
			self._cola_voz = [f for f in self._cola_voz if f.clave != clave]
		self._numero += 1
		self._cola_voz.append(_Frase(texto, canal, prioridad, self.t + caduca, clave, vale, self._numero))
		if len(self._cola_voz) > MAX_COLA_VOZ:
			# Sobra una: se va la menos importante y, entre iguales, la más vieja.
			sobra = min(self._cola_voz, key=lambda f: (f.prioridad, f.orden))
			self._cola_voz.remove(sobra)

	def _despachar_voz(self) -> None:
		"""Suelta la siguiente frase automática si la voz ha quedado libre; tira las caducadas."""
		while self._cola_voz and self.t >= self._voz_libre - 1e-9:
			frase = max(self._cola_voz, key=lambda f: (f.prioridad, -f.orden))
			self._cola_voz.remove(frase)
			if self.t > frase.caduca or (frase.vale is not None and not frase.vale()):
				continue
			self._salida.append(ev.EvVoz(frase.texto, False, frase.canal))
			self._voz_libre = self.t + self._duracion(frase.texto)

	# ── Actividad ──

	def gancho(self, nombre: str, *argumentos: Any) -> list[Any]:
		"""Llama a un gancho de la actividad, si lo tiene, y emite los eventos que devuelva.

		Un fallo de la actividad se anota y no para la partida: el alumno no
		debe quedarse colgado por un error en un juego.
		"""
		funcion = getattr(self.actividad, nombre, None) if self.actividad is not None else None
		if not callable(funcion):
			return []
		try:
			devuelto = funcion(self, *argumentos)
		except Exception:  # noqa: BLE001 - la actividad es código ajeno al motor; se anota y se sigue
			log.exception("Fallo en el gancho «%s» de la actividad", nombre)
			return []
		eventos = list(devuelto) if devuelto else []
		for evento in eventos:
			self.emitir(evento)
		return eventos

	def terminar(self, resultado: dict[str, Any] | None = None) -> None:
		"""Da la partida por terminada: emite ``EvFin`` con el resumen, lo de la actividad y ``resultado``."""
		if self.terminado:
			return
		final = self.resumen()
		if self.actividad is not None and callable(getattr(self.actividad, "resultado", None)):
			try:
				propio = self.actividad.resultado(self)
			except Exception:  # noqa: BLE001 - igual que en los ganchos
				log.exception("Fallo al pedir el resultado a la actividad")
				propio = None
			if isinstance(propio, dict):
				final.update(propio)
		if resultado:
			final.update(resultado)
		self.resultado = final
		self.terminado = True
		self.movimiento.soltar_todo()
		self._salida.append(ev.EvFin(final))

	def resumen(self) -> dict[str, Any]:
		"""Cifras de la partida hasta ahora (tiempos, distancia, choques, ayudas, lugares)."""
		return {
			"tiempo_activo": round(self.t, 2),
			"tiempo_pausa": round(self.tiempo_pausa, 2),
			"distancia_m": round(self.movimiento.distancia, 2),
			"pasos": self.movimiento.pasos,
			"choques": self.movimiento.choques,
			"ayudas": dict(self.percepcion.usos),
			"espacios_visitados": sorted(self.movimiento.visitados),
			"semilla": self.semilla,
		}

	# ── Estado ──

	def oyente(self) -> tuple[float, float, float, float]:
		"""(x, y, z, rumbo) de la cabeza del alumno, para la capa de sonido."""
		jugador = self.jugador
		return jugador.x, jugador.y, self.mundo.altura(jugador.planta) + jugador.z_extra + ALTURA_OIDOS, jugador.rumbo % 360.0

	def fuentes(self) -> list[FuenteActiva]:
		"""Fuentes continuas que se oyen ahora, ya con su oclusión y su camino por puertas."""
		if self.pausado or self.terminado:
			return []
		return self.acustica.fuentes() + self.movimiento.fuentes()

	def estado(self) -> dict[str, Any]:
		"""Foto de la partida, para la supervisión y las pantallas del reproductor."""
		jugador = self.jugador
		planta = self.mundo.planta(jugador.planta)
		espacio = self.mundo.espacio_en(jugador.planta, jugador.x, jugador.y) if jugador.modo == "andando" else None
		return {
			"planta": jugador.planta,
			"planta_nombre": planta.planta.nombre if planta is not None else "",
			"x": round(jugador.x, 3),
			"y": round(jugador.y, 3),
			"z": round(self.mundo.altura(jugador.planta) + jugador.z_extra, 3),
			"rumbo": round(jugador.rumbo % 360.0, 1),
			"espacio": espacio.id if espacio is not None else "",
			"espacio_nombre": espacio.nombre if espacio is not None else "",
			"descripcion": self.percepcion.texto_donde(),
			"modo": jugador.modo,
			"suelo": self.movimiento.suelo,
			"tiempo_activo": round(self.t, 2),
			"tiempo_pausa": round(self.tiempo_pausa, 2),
			"pausado": self.pausado,
			"terminado": self.terminado,
			"distancia_m": round(self.movimiento.distancia, 2),
			"pasos": self.movimiento.pasos,
			"choques": self.movimiento.choques,
			"ayudas": dict(self.percepcion.usos),
			"descubiertos": len([c for c in self.percepcion.conocidos.values() if c.visitado]),
		}

	def muestra(self) -> tuple[float, str, float, float, float]:
		"""(t, planta, x, y, rumbo) para la traza de la grabadora; ``t`` es tiempo activo."""
		jugador = self.jugador
		return round(self.t, 3), jugador.planta, round(jugador.x, 3), round(jugador.y, 3), round(jugador.rumbo % 360.0, 1)

	@property
	def tiempo_activo(self) -> float:
		"""Segundos de partida sin contar las pausas."""
		return self.t

	def pausar(self, si: bool) -> None:
		"""Pausa o reanuda. En pausa no corre el tiempo activo ni se atienden órdenes."""
		si = bool(si)
		if si == self.pausado:
			return
		self.pausado = si
		self.movimiento.soltar_todo()
		self.registrar("pausa", activa=si, tiempo_pausa=round(self.tiempo_pausa, 2))

	def recolocar(self, pos: Posicion) -> None:
		"""Lleva al alumno a otra posición (el profesional desde la supervisión, o «volver al inicio»)."""
		if self.mundo.planta(pos.planta) is None:
			log.warning("No se puede recolocar en la planta %s: no existe", pos.planta)
			return
		jugador = self.jugador
		movimiento = self.movimiento
		jugador.planta, jugador.x, jugador.y, jugador.rumbo = pos.planta, float(pos.x), float(pos.y), float(pos.rumbo) % 360.0
		jugador.modo = "andando"
		jugador.z_extra = 0.0
		movimiento.en_tramo = None
		movimiento.cabina = None
		movimiento.soltar_todo()
		self.cancelar("sonda")
		self.registrar("recolocar", rumbo=round(jugador.rumbo, 1))
		if self._empezada:
			movimiento.tras_mover(None, forzar=True)

	def aplicar_ajustes(self, ajustes: AjustesJuego) -> None:
		"""Cambia los ajustes en marcha (el profesional retira una ayuda, el alumno cambia de formato)."""
		self.ajustes = ajustes
		self.leng = leng.Lenguaje(ajustes.formato_direccion, ajustes.unidad, ajustes.paso_m, ajustes.estilo)
		self.jugador.radio = ajustes.radio_m
		self.movimiento.soltar_todo()

	def permitir_ayuda(self, ayuda: str, permitida: bool = True, limite: int | None = None) -> None:
		"""Permite, prohíbe o limita una ayuda en marcha (``AYUDAS`` de ``percepcion``)."""
		if ayuda not in AYUDAS:
			log.warning("Ayuda desconocida: %s", ayuda)
		self.ajustes.ayudas[ayuda] = {"permitida": bool(permitida), "limite": limite}

	# ── Cosas que usan las actividades ──

	def interactuables_cerca(self) -> list[dict[str, Any]]:
		"""Lo que el alumno tiene al alcance de la mano (ver ``Movimiento.interactuables``)."""
		return self.movimiento.interactuables()

	def distancia_a(self, destino: Any) -> float:
		"""Metros en línea recta del alumno a un lugar de su planta (infinito si es de otra)."""
		planta, x, y = lugar(destino)
		if planta != self.jugador.planta:
			return math.inf
		return math.hypot(x - self.jugador.x, y - self.jugador.y)

	def anadir_fuente(
		self,
		id: str,  # noqa: A002 - es el nombre natural del identificador de la fuente
		sonido: str,
		pos: Any,
		volumen: float = 1.0,
		radio: float = 12.0,
		bucle: bool = True,
		intervalo: float = 0.0,
		altura: float = 1.0,
		bus: str = "ambiente",
		ocluir: bool = True,
		movil: bool = False,
		tono: float = 1.0,
	) -> None:
		"""Pone a sonar algo en un lugar (un premio, un personaje que se esconde); ``pos`` es ``Posicion`` o ``(planta, x, y)``.

		Con ``bucle`` falso e ``intervalo`` mayor que cero suena cada tantos
		segundos. Volver a llamar con el mismo ``id`` la mueve o la cambia.
		"""
		planta, x, y = lugar(pos)
		self.acustica.anadir(
			Emisor(str(id), sonido, planta, x, y, altura, volumen, radio, bucle, intervalo, tono, movil, bus, True, ocluir)
		)

	def quitar_fuente(self, id: str) -> bool:  # noqa: A002
		"""Quita una fuente añadida con ``anadir_fuente``. Devuelve si existía."""
		return self.acustica.quitar(str(id))

	def baliza(self, pos: Any | None, por_ruta: bool = False, sonido: str = "baliza/pulso") -> bool:
		"""Enciende una baliza sonora en un lugar (``None`` la apaga). Devuelve si quedó encendida.

		Directa, suena desde el destino. ``por_ruta`` la hace sonar desde el
		siguiente punto del camino que el alumno puede alcanzar en línea
		recta: guía paso a paso (es mucha ayuda; úsese en los primeros niveles).
		Cuenta como un uso de la ayuda «baliza» y respeta su permiso.
		"""
		if pos is None:
			self._baliza = None
			return False
		if not self.percepcion.usar("baliza"):
			return False
		self._baliza = _Baliza(lugar(pos), por_ruta, sonido)
		return True

	def _tic_baliza(self, dt: float) -> None:
		baliza = self._baliza
		if baliza is None or self.jugador.modo != "andando":
			return
		baliza.t -= dt
		if baliza.t > 0.0:
			return
		jugador = self.jugador
		planta, x, y = baliza.destino
		recta = math.hypot(x - jugador.x, y - jugador.y) if planta == jugador.planta else math.inf
		if recta <= DISTANCIA_LLEGADA_BALIZA:
			self.sonar("baliza/llegada", pos=self.pos3(x, y, 1.0), bus="ayudas")
			self.vibrar("objetivo")
			self.registrar("baliza_llegada", destino=[planta, round(x, 2), round(y, 2)])
			self._baliza = None
			return
		objetivo = (x, y)
		directa = planta == jugador.planta and (not baliza.por_ruta or self.mundo.visible(planta, jugador.punto, (x, y), "paso"))
		if not directa:
			en = baliza.ruta_en
			if baliza.ruta is None or en is None or en[0] != jugador.planta or math.hypot(en[1] - jugador.x, en[2] - jugador.y) > 1.5:
				baliza.ruta = self.nav.ruta((jugador.planta, jugador.x, jugador.y), baliza.destino)
				baliza.ruta_en = (jugador.planta, jugador.x, jugador.y)
			if baliza.ruta is None:
				if planta != jugador.planta:
					baliza.t = 2.0
					return
			else:
				# El punto más avanzado del camino, en esta planta, al que se llega en línea recta.
				for punto_planta, px, py in baliza.ruta.puntos:
					if punto_planta != jugador.planta:
						break
					if math.hypot(px - jugador.x, py - jugador.y) < 0.4 or self.mundo.visible(
						jugador.planta, jugador.punto, (px, py), "paso"
					):
						objetivo = (px, py)
		distancia = math.hypot(objetivo[0] - jugador.x, objetivo[1] - jugador.y)
		relativo = geo.diferencia_rumbos(jugador.rumbo, geo.rumbo_entre(jugador.punto, objetivo)) if distancia > 0.05 else 0.0
		if recta < 3.0:
			nombre = "baliza/cerca"
		elif abs(relativo) <= 15.0:
			nombre = "baliza/alineado"
		elif abs(relativo) >= 120.0:
			nombre = "baliza/detras"
		else:
			nombre = baliza.sonido
		self.sonar(nombre, pos=self.pos3(objetivo[0], objetivo[1], 1.0), bus="ayudas")
		baliza.t = max(0.45, min(1.6, 0.4 + 0.12 * (recta if math.isfinite(recta) else 12.0)))
