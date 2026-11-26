"""La pantalla de juego: une la entrada, la sesión del motor, la grabación y la supervisión.

No tiene reglas: traduce acciones a ``Sesion.orden`` y ejes a
``Sesion.analogico``, entrega los eventos de ``Sesion.avanzar`` a la
aplicación (que los presenta), apunta la sesión con la ``Grabadora`` y aplica
las órdenes del profesor. Es la misma pantalla para:

- una **actividad** del paquete (juego, práctica o examen);
- la **exploración libre** (sin actividad);
- el **tutorial** (una actividad propia del reproductor, sin grabación);
- el **modo recorrido** del profesional (sin actividad ni grabación, con el
  menú de edición de ``pantallas/recorrido.py``).

Pausas: la sesión se pausa mientras haya algún motivo (un menú abierto encima,
la orden del profesor). Así cualquier pantalla que se abra sobre el juego lo
detiene sin tener que acordarse, y el tiempo de los exámenes no corre.

Quién manda en los ajustes: la base son las preferencias del alumno; la
actividad las retoca con ``actividad.ajustes(base)`` y lo que el profesor fija
en vivo (ayudas permitidas o no) se vuelve a poner encima cada vez que algo
cambia. El alumno puede cambiar sus opciones a mitad de partida, pero no
saltarse lo que fijó el profesional.

Actividades:

- **Semilla y nivel.** Cada partida sortea una semilla que va a la actividad y
  a la sesión (queda en el resultado y en la grabación). El nivel de ayudas lo
  da ``app.nivel_actividad(entorno, actividad)`` si la aplicación lo sabe y, al
  terminar, se le devuelve el ``nivel_siguiente`` con ``app.anotar_nivel``.
- **Confirmar.** La acción ``confirmar`` llama a ``actividad.confirmar(sesion)``.
- **Preguntas.** Cuando ``actividad.estado()["pregunta"]`` trae una pregunta
  con opciones (exámenes de distancias y de reconstrucción) se abre un menú
  con las respuestas. Ese menú no pausa la partida: el tiempo de la prueba es
  tiempo de juego y contestar forma parte de ella.
- **Órdenes del profesor.** Los eventos que devuelve
  ``actividad.orden_profesional`` se presentan con ``presentar_eventos``.
"""

from __future__ import annotations

import logging
import math
import random
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

import pygame

from app.core.i18n import _, _n
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Entorno, Posicion
from app.entrada import acciones
from app.entrada.mando import BOTONES_SDL
from app.motor.sesion import AjustesJuego, Sesion, regla_ayuda
from app.reproductor import carga, entornos, plano, puente_actividades, textos
from app.reproductor.menus import SONIDO_ABRIR, Menu, Opcion, Pantalla, confirmar
from app.seguimiento.grabadora import Grabadora

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)

# Aviso de progreso de la preparación: (fase, hechos, total). Ver ``Sesion.__init__``.
Progreso = Callable[[str, int, int], None]
# Tiempo de cada fotograma que se dedica a calcular por adelantado los caminos del alumno (ver ``Navegador.precalcular``).
PRESUPUESTO_CAMINOS = 0.003

PAUSA_MENU = "menu"
PAUSA_PROFESOR = "profesor"
# Cada cuánto se compone el estado para la supervisión (el cliente envía el último 5 veces por segundo).
CADA_ESTADO = 0.2
# Alcance del «qué tiene delante» que ve el profesor.
ALCANCE_DELANTE = 8.0
_PASOS_FANTASMA = {"avanzar": 0.0, "retroceder": 180.0, "paso_izquierda": -90.0, "paso_derecha": 90.0}
# Acciones que no son del motor: las atiende la aplicación.
_DE_LA_APLICACION = ("repetir", "historial_anterior", "historial_siguiente", "callar")


@dataclass
class Pedido:
	"""Lo que la preparación de una sesión necesita leer de la aplicación (en el hilo principal, antes de empezar)."""

	base: AjustesJuego
	catalogo: Catalogo
	semilla: int
	nivel: int | None
	datos_crear: dict[str, Any] | None
	estilo: str
	inicio: Posicion | None
	entorno: Entorno
	ayudas_profesor: dict[str, dict[str, Any]]


@dataclass
class Preparada:
	"""Una sesión lista para jugar, con su actividad: lo que devuelve ``PantallaJuego.preparar``."""

	actividad: Any
	sesion: Sesion
	semilla: int
	nivel: int | None


class MenuPregunta(Menu):
	"""Las respuestas de una pregunta de examen. A diferencia de los demás menús, no pausa la partida.

	El tiempo de cada prueba es tiempo de juego y contestar es la prueba: si el
	menú la pausara, una pregunta tendría tiempo ilimitado.
	"""

	pausa_partida = False

	def __init__(self, partida: PantallaJuego, clave: tuple[str, tuple[str, ...]] | None, *argumentos: Any, **opciones: Any) -> None:
		self.partida = partida
		self.clave = clave
		super().__init__(partida.app, *argumentos, **opciones)

	def volver(self) -> None:
		"""Vuelve al juego sin contestar; la partida no dice «seguimos» porque no se había parado."""
		self.partida._callar_al_volver = self.app.cima is self
		super().volver()


class PantallaJuego(Pantalla):
	"""Una partida en marcha. Ver el docstring del módulo."""

	contexto = acciones.JUEGO

	def __init__(
		self,
		app: Aplicacion,
		paquete: Any,
		datos_actividad: dict[str, Any] | None = None,
		recorrido: bool = False,
		tutorial: bool = False,
		actividad: Any = None,
		diferir: bool = False,
	) -> None:
		"""Prepara la sesión. Lanza ``ErrorActividad`` si la actividad no se puede crear.

		Con ``diferir`` no se prepara nada todavía: lo hace la pantalla de carga
		(``app.reproductor.carga``) con ``pedido``, ``preparar`` y ``instalar``,
		la parte pesada en segundo plano.
		"""
		super().__init__(app)
		self.paquete = paquete
		self.entorno = paquete.entorno
		self.datos = datos_actividad if isinstance(datos_actividad, dict) else None
		self.recorrido = recorrido
		self.tutorial = tutorial
		self.actividad: Any = actividad
		self.pausas: set[str] = set()
		self.terminado = False
		self.completada = False
		self.resultado: dict[str, Any] = {}
		self.premios_recogidos: set[str] = set()
		self.ayudas_profesor: dict[str, dict[str, Any]] = {}
		self.fantasma = False
		self.medida_desde: tuple[str, float, float] | None = None
		self.grabadora: Grabadora | None = None
		self._presentada = False
		self._finalizada = False
		self._fin_pendiente: dict[str, Any] | None = None
		self._ordenes_pendientes: list[str] = []
		self._t_estado = 0.0
		self._t_aviso_pausa = -1e9
		self._reloj = 0.0
		self.semilla: int | None = None
		self.nivel_pedido: int | None = None
		self._menu_pregunta: MenuPregunta | None = None
		self._pregunta_vista: tuple[str, tuple[str, ...]] | None = None
		self._pregunta_pendiente: tuple[str, tuple[str, ...]] | None = None
		self._callar_al_volver = False
		self._inicio_pedido = self._inicio_de_argumentos()
		if not diferir:
			self._crear_sesion()

	# ── Preparación ──────────────────────────────────────────────────────────

	def _inicio_de_argumentos(self) -> Posicion | None:
		"""El ``--inicio`` de la línea de órdenes, solo para el entorno que se pasó con él."""
		opciones = self.app.opciones
		pedido = getattr(opciones, "inicio", None)
		ruta = getattr(opciones, "paquete", None)
		if pedido is None or ruta is None or self.paquete.ruta is None:
			return None
		try:
			mismo = ruta.resolve() == self.paquete.ruta.resolve()
		except OSError:
			mismo = False
		return Posicion(pedido.planta, pedido.x, pedido.y, pedido.rumbo) if mismo else None

	def _crear_sesion(self, preparada: Preparada | None = None) -> None:
		"""Crea la actividad, la sesión y la grabadora (también al reiniciar).

		Con ``preparada`` (lo que ha hecho la pantalla de carga en segundo
		plano, ver ``app.reproductor.carga``) solo queda instalarla; sin ella se
		prepara aquí mismo, lo que con un entorno pequeño es instantáneo.
		"""
		if preparada is None:
			preparada = self.preparar(self.pedido())
		self._instalar(preparada)

	def pedido(self, entorno: Entorno | None = None) -> Pedido:
		"""Lo que hace falta para preparar la sesión y solo se puede leer en el hilo principal (ajustes, perfil, catálogo).

		``entorno`` es el entorno para el que se prepara (otro si se acaba de recargar del disco).
		"""
		app = self.app
		# Una semilla por partida: la actividad sortea con ella lo que no fija (un examen trae la suya) y queda grabada.
		semilla = random.SystemRandom().randrange(1, 2**31)
		crear = self.datos is not None and not self.tutorial
		nivel = self._nivel_guardado() if crear else None
		return Pedido(
			base=app.ajustes_juego(),
			catalogo=app.catalogo,
			semilla=semilla,
			nivel=nivel,
			datos_crear=self._datos_para_crear() if crear else None,
			estilo=self._estilo_actividad() if crear else "",
			inicio=self._inicio_pedido,
			entorno=entorno if entorno is not None else self.entorno,
			ayudas_profesor={ayuda: dict(regla) for ayuda, regla in self.ayudas_profesor.items()},
		)

	def preparar(self, pedido: Pedido, progreso: Progreso | None = None) -> Preparada:
		"""La parte pesada: crea la actividad y la sesión del motor. Puede ir en un hilo aparte.

		No toca nada de la aplicación ni de esta pantalla (solo lee datos que no
		cambian mientras tanto): así la pantalla de carga puede llamarla en
		segundo plano mientras el bucle de pygame sigue atendiendo al alumno.
		``progreso`` recibe las fases (ver ``Sesion.__init__``) y, si lanza una
		excepción, la preparación se interrumpe.
		"""
		actividad = self.actividad
		if pedido.datos_crear is not None:
			if progreso is not None:
				progreso("actividad", 0, 0)
			actividad = puente_actividades.crear(
				pedido.datos_crear,
				pedido.entorno,
				pedido.catalogo,
				estilo=pedido.estilo,
				semilla=pedido.semilla,
				nivel=pedido.nivel,
			)
		inicio = pedido.inicio
		if inicio is None and actividad is not None and callable(getattr(actividad, "inicio", None)):
			try:
				propio = actividad.inicio()
			except Exception:  # noqa: BLE001 - la actividad es código ajeno al reproductor: se empieza en el inicio del entorno
				log.exception("Fallo al pedir el inicio a la actividad")
				propio = None
			inicio = propio if isinstance(propio, Posicion) else None
		ajustes = self._ajustes_de(pedido.base, actividad, pedido.ayudas_profesor)
		sesion = Sesion(
			pedido.entorno, pedido.catalogo, ajustes, actividad=actividad, semilla=pedido.semilla, inicio=inicio, progreso=progreso
		)
		if progreso is not None:
			# Solo con la pantalla de carga: lo que la primera consulta calcularía de golpe, ahora que se está esperando.
			sesion.preparar(progreso)
		return Preparada(actividad, sesion, pedido.semilla, pedido.nivel)

	def instalar(self, preparada: Preparada) -> None:
		"""Pone en marcha una sesión ya preparada (en el hilo principal)."""
		self._crear_sesion(preparada)

	def _instalar(self, preparada: Preparada) -> None:
		"""Pone en marcha una sesión ya preparada: grabadora, sala del profesor y estado de la partida."""
		app = self.app
		self.actividad = preparada.actividad
		self.sesion = preparada.sesion
		self.semilla = preparada.semilla
		if self.datos is not None and not self.tutorial:
			self.nivel_pedido = preparada.nivel
		self.pausas.clear()
		self.terminado = False
		self.completada = False
		self.resultado = {}
		self.premios_recogidos.clear()
		self._fin_pendiente = None
		self._ordenes_pendientes.clear()
		self._menu_pregunta = None
		self._pregunta_vista = None
		self._pregunta_pendiente = None
		self._callar_al_volver = False
		self.grabadora = None
		if not self.recorrido and not self.tutorial:
			self.grabadora = Grabadora(
				app.alias,
				self.entorno.id,
				self.entorno.nombre,
				self.id_actividad,
				self.nombre_actividad,
				self.tipo_actividad,
				self.modo,
				espacios=entornos.espacios_para_grabadora(self.entorno),
			)
		if app.enlace is not None:
			app.enlace.cambiar_contexto(self.entorno.nombre, self.nombre_actividad, self.modo)

	def _datos_para_crear(self) -> dict[str, Any]:
		"""Los datos de la actividad con las estrellas que el alumno ya tenía, para los premios que se desbloquean al sumar."""
		datos = dict(self.datos or {})
		recompensas = datos.get("recompensas")
		recompensas = dict(recompensas) if isinstance(recompensas, dict) else {}
		perfil = self.app.perfil
		recompensas["estrellas_previas"] = perfil.cuenta_premios().get("estrella", 0) if perfil is not None else 0
		datos["recompensas"] = recompensas
		return datos

	def _estilo_actividad(self) -> str:
		"""El estilo con el que se crea la actividad: el suyo, salvo que diga «del alumno»."""
		propio = str((self.datos or {}).get("estilo") or "del_alumno")
		return propio if propio in textos.ESTILOS else self.app.estilo

	def _nivel_guardado(self) -> int | None:
		"""El nivel de ayudas en que quedó el alumno en esta actividad, si la aplicación lo guarda (``app.nivel_actividad``)."""
		funcion = getattr(self.app, "nivel_actividad", None)
		if not callable(funcion) or not self.id_actividad:
			return None
		try:
			nivel = funcion(self.entorno.id, self.id_actividad)
		except Exception:  # noqa: BLE001 - sin el nivel guardado se juega con el de la actividad
			log.exception("No se pudo leer el nivel guardado de la actividad")
			return None
		if isinstance(nivel, bool) or not isinstance(nivel, int) or nivel < 0:
			return None
		return nivel

	def _anotar_nivel(self, resultado: dict[str, Any]) -> None:
		"""Devuelve a la aplicación el nivel con el que debe empezar la próxima vez (``app.anotar_nivel``)."""
		siguiente = resultado.get("nivel_siguiente")
		funcion = getattr(self.app, "anotar_nivel", None)
		if not callable(funcion) or not self.id_actividad or isinstance(siguiente, bool) or not isinstance(siguiente, int):
			return
		try:
			funcion(self.entorno.id, self.id_actividad, siguiente)
		except Exception:  # noqa: BLE001 - no guardar el nivel no debe impedir enseñar el resultado
			log.exception("No se pudo guardar el nivel de la actividad")

	def _ajustes_de(
		self, base: AjustesJuego, actividad: Any = None, ayudas_profesor: dict[str, dict[str, Any]] | None = None
	) -> AjustesJuego:
		"""Los ajustes con los que se juega: los del alumno, retocados por la actividad y por el profesor.

		``actividad`` es la que se está preparando (en la carga aún no es
		``self.actividad``) y ``ayudas_profesor``, la copia que se tomó al
		pedirla (el profesor puede cambiarlas mientras carga en otro hilo).
		"""
		actividad = actividad if actividad is not None else self.actividad
		ayudas_profesor = ayudas_profesor if ayudas_profesor is not None else self.ayudas_profesor
		ajustes = base
		if self.recorrido:
			# El profesional que recorre su entorno quiere toda la información y todas las ayudas.
			ajustes.detalle = max(ajustes.detalle, 2)
			ajustes.ayudas = {}
		funcion = getattr(actividad, "ajustes", None) if actividad is not None else None
		if callable(funcion):
			try:
				propios = funcion(base)
			except Exception:  # noqa: BLE001 - igual que los ganchos del motor: se anota y se juega con los ajustes del alumno
				log.exception("Fallo al pedir los ajustes a la actividad")
				propios = None
			if isinstance(propios, AjustesJuego):
				ajustes = propios
		for ayuda, regla in ayudas_profesor.items():
			ajustes.ayudas[ayuda] = dict(regla)
		return ajustes

	# ── Datos de la actividad ────────────────────────────────────────────────

	@property
	def id_actividad(self) -> str:
		"""Identificador de la actividad («» en la exploración libre)."""
		return str((self.datos or {}).get("id") or "")

	@property
	def nombre_actividad(self) -> str:
		"""Nombre visible de lo que se juega."""
		if self.recorrido:
			return _("Recorrido del profesional")
		nombre = getattr(self.actividad, "nombre", None) or (self.datos or {}).get("nombre")
		return str(nombre) if nombre else _("Exploración libre")

	@property
	def tipo_actividad(self) -> str:
		"""Tipo de la actividad («exploracion» si no hay)."""
		return str(getattr(self.actividad, "tipo", None) or (self.datos or {}).get("tipo") or "exploracion")

	@property
	def modo(self) -> str:
		"""juego, practica o examen."""
		if self.actividad is None:
			return "practica"
		return puente_actividades.modo_de(self.actividad)

	@property
	def libre(self) -> bool:
		"""Si es una exploración sin actividad."""
		return self.actividad is None and not self.recorrido

	def estado_actividad(self) -> dict[str, Any]:
		"""``actividad.estado()``: objetivo, hechos, total, puntos, estrellas, tiempo restante y nivel."""
		return puente_actividades.estado_de(self.actividad) if self.actividad is not None else {}

	def texto_objetivo(self) -> str:
		"""El objetivo actual dicho en una frase, con lo que se lleva hecho."""
		if self.recorrido:
			return _("Modo recorrido: recorre el entorno y usa el menú de edición para pedir cambios al Estudio.")
		estado = self.estado_actividad()
		objetivo = str(estado.get("objetivo") or "").strip()
		if not objetivo:
			return (
				_("Exploración libre: no hay objetivo. Recorre el lugar a tu aire.")
				if self.actividad is None
				else _("Ahora no hay ningún objetivo.")
			)
		partes = [objetivo.rstrip(".") + "."]
		total = estado.get("total")
		if isinstance(total, int) and total > 0:
			partes.append(_("Llevas {hechos} de {total}.").format(hechos=int(estado.get("hechos") or 0), total=total))
		restante = estado.get("tiempo_restante")
		if isinstance(restante, (int, float)) and restante > 0:
			partes.append(_("Te quedan {tiempo}.").format(tiempo=textos.duracion(restante)))
		return " ".join(partes)

	def texto_instrucciones(self) -> str:
		"""Las instrucciones de la actividad: su mensaje de inicio o, si no tiene, su descripción."""
		if self.datos is not None:
			mensajes = self.datos.get("mensajes")
			inicio = str(mensajes.get("inicio") or "").strip() if isinstance(mensajes, dict) else ""
			return inicio or puente_actividades.describir(self.datos, self.entorno)
		if self.recorrido:
			return self.texto_objetivo()
		return textos.frase("empieza_libre", self.app.estilo, entorno=self.entorno.nombre)

	# ── Entrar y salir ───────────────────────────────────────────────────────

	def al_entrar(self) -> None:
		"""La primera vez presenta el entorno; al volver de un menú, solo dice que se sigue."""
		app = self.app
		if self._presentada:
			if self._callar_al_volver:
				# Se vuelve del menú de respuestas, que no pausaba: no hay nada que «seguir».
				self._callar_al_volver = False
				return
			if not self.terminado:
				app.decir(textos.frase("sigue", app.estilo), True)
			return
		self._presentada = True
		app.banco.poner_entorno(self.paquete.recurso)
		app.sonar(SONIDO_ABRIR)
		frases: list[str] = []
		if self.recorrido:
			frases.append(_("Modo recorrido de {entorno}.").format(entorno=self.entorno.nombre))
		elif self.actividad is None:
			frases.append(textos.frase("empieza_libre", app.estilo, entorno=self.entorno.nombre))
		faltan = entornos.complementos_que_faltan(self.entorno, app.catalogo)
		if faltan:
			# Se avisa una sola vez por partida: los objetos siguen ahí, como cajas con su tamaño.
			log.warning("Faltan complementos para este entorno: %s", ", ".join(faltan))
			frases.append(
				_n(
					"Falta el complemento {lista}: sus objetos aparecen como cajas.",
					"Faltan los complementos {lista}: sus objetos aparecen como cajas.",
					len(faltan),
				).format(lista=", ".join(faltan))
			)
		if frases:
			app.decir(" ".join(frases), True, "aviso" if faltan else "juego")
		if app.perfil is not None and self.paquete.ruta is not None and not self.recorrido and not self.tutorial:
			app.perfil.recordar_ultima(
				self.paquete.ruta, self.id_actividad, self.entorno.nombre, self.nombre_actividad if self.actividad is not None else ""
			)

	def al_perder_foco(self) -> None:
		"""Pausa automática: sin el foco el alumno no oye ni maneja el juego."""
		if not self.terminado and not self.recorrido and self.app.cima is self:
			self.abrir_pausa(anunciar=False)

	def finalizar(self) -> None:
		"""Cierra la partida: graba la sesión y deja el sonido limpio. Se puede llamar varias veces."""
		if self._finalizada:
			return
		self._finalizada = True
		app = self.app
		if not self.terminado:
			# Cierre sin terminar (se sale del reproductor a mitad): se guarda lo jugado como no completado,
			# con lo que dice la actividad (nivel, pruebas hechas…) si la hay.
			self.resultado = {**self.sesion.resumen(), "abandonada": True, "completada": False}
			if self._fin_pendiente is not None:
				# La sesión acababa de terminar y aún no se había atendido su fin: vale su resultado.
				self.resultado = dict(self._fin_pendiente)
				self.completada = bool(self.resultado.get("completada"))
			elif self.actividad is not None and not self.sesion.terminado:
				try:
					self.sesion.terminar({"abandonada": True, "completada": False})
					for evento in self.sesion.avanzar(0.0):
						if type(evento).__name__ == "EvRegistro" and self.grabadora is not None:
							self.grabadora.registrar(evento)
					if isinstance(self.sesion.resultado, dict) and self.sesion.resultado:
						self.resultado = dict(self.sesion.resultado)
				except Exception:  # noqa: BLE001 - al cerrar a mitad se guarda al menos el resumen de la sesión
					log.exception("No se pudo cerrar la actividad al salir a mitad")
			if app.enlace is not None and not self.recorrido:
				app.enlace.fin(False, self.resultado)
		if self.grabadora is not None:
			try:
				ruta = self.grabadora.terminar(self.completada, self.resultado)
				log.info("Sesión guardada en %s", ruta.name)
			except OSError:
				log.exception("No se pudo guardar la sesión")
				app.decir(_("No se ha podido guardar la sesión en el disco."), False, "aviso")
		app.presentador.detener_fuentes()
		app.presentador.pausar(False)
		app.banco.poner_entorno(None)

	# ── Pausas ───────────────────────────────────────────────────────────────

	@property
	def pausada(self) -> bool:
		"""Si hay algún motivo de pausa."""
		return bool(self.pausas)

	def pausar(self, motivo: str) -> None:
		"""Añade un motivo de pausa; con el primero se detienen la sesión, la grabación y los sonidos del mundo."""
		antes = bool(self.pausas)
		self.pausas.add(motivo)
		if not antes:
			self.sesion.pausar(True)
			if self.grabadora is not None:
				self.grabadora.pausar(True)
			self.app.presentador.pausar(True)

	def reanudar(self, motivo: str) -> None:
		"""Quita un motivo de pausa; al quitar el último, todo sigue."""
		if motivo not in self.pausas:
			return
		self.pausas.discard(motivo)
		if not self.pausas:
			self.sesion.pausar(False)
			if self.grabadora is not None:
				self.grabadora.pausar(False)
			self.app.presentador.pausar(False)

	# ── Fotograma ────────────────────────────────────────────────────────────

	def fotograma(self, dt: float, activa: bool) -> None:
		"""Un fotograma de la partida. ``activa`` es falso si hay un menú abierto encima."""
		if self.terminado:
			return
		if self._fin_pendiente is not None:
			# El fin se atiende un fotograma después de ocurrir: así lo último de la partida
			# («Has encontrado la moneda») ya se ha dicho cuando habla la pantalla de resultado.
			resultado, self._fin_pendiente = self._fin_pendiente, None
			self._fin(resultado)
			return
		# El menú de respuestas de un examen no pausa: contestar es parte de la prueba.
		en_pregunta = self._menu_pregunta is not None and self.app.cima is self._menu_pregunta
		if activa or en_pregunta:
			self.reanudar(PAUSA_MENU)
		else:
			self.pausar(PAUSA_MENU)
		sesion = self.sesion
		if activa and not self.pausada:
			for accion in self._ordenes_pendientes:
				sesion.orden(accion)
			self._ordenes_pendientes.clear()
			avance, lateral, giro, mirada = self.app.entrada.ejes(acciones.JUEGO)
			if self.fantasma:
				avance = lateral = 0.0
			sesion.analogico(avance, lateral, giro, mirada)
		elif en_pregunta:
			# En el menú las palancas mueven el cursor, no al alumno.
			sesion.analogico(0.0, 0.0, 0.0, None)
		eventos = sesion.avanzar(dt)
		self._procesar(eventos)
		self.app.entregar(eventos, sesion)
		if self.grabadora is not None:
			self.grabadora.muestra(*sesion.muestra())
		self._reloj += dt
		if not self.terminado and self._fin_pendiente is None:
			self._revisar_pregunta()
		self._precalcular_caminos(activa)
		if self.app.enlace is not None and self._reloj - self._t_estado >= CADA_ESTADO:
			self._t_estado = self._reloj
			self.app.enlace.estado(self.estado_para_profesor())

	def _precalcular_caminos(self, activa: bool) -> None:
		"""Usa unos milisegundos del fotograma para calcular por adelantado los caminos alrededor del alumno.

		Así, cuando pide la lista de cercanos o una actividad le busca una ruta,
		no hay que calcular de golpe cientos de miles de celdas (en una plaza
		grande eran segundos). Los resultados son los mismos: solo se adelanta
		el trabajo. Cuando ya está todo hecho, cuesta unos microsegundos.
		"""
		if not activa or self.pausada or self.terminado or getattr(self, "_sin_precalculo", False):
			return
		sesion = self.sesion
		jugador = sesion.jugador
		if jugador.modo != "andando":
			return
		try:
			sesion.nav.precalcular((jugador.planta, jugador.x, jugador.y), PRESUPUESTO_CAMINOS)
		except ValueError, KeyError, TypeError, ZeroDivisionError:
			# Un dato raro del entorno no debe costar el fotograma: se deja de adelantar y el camino se calculará cuando se pida.
			log.warning("No se pudieron precalcular los caminos del alumno; se calcularán cuando hagan falta", exc_info=True)
			self._sin_precalculo = True

	def _procesar(self, eventos: list[Any]) -> None:
		"""Reparte lo que no es sonido: registros a la grabadora y a la sala, y el fin."""
		enlace = self.app.enlace
		for evento in eventos:
			clase = type(evento).__name__
			if clase == "EvRegistro":
				if self.grabadora is not None:
					self.grabadora.registrar(evento)
				if enlace is not None:
					enlace.evento(str(evento.tipo), dict(evento.datos))
				if evento.tipo == "premio":
					self.premios_recogidos.add(str(evento.datos.get("id") or evento.datos.get("premio") or ""))
			elif clase == "EvVoz":
				# Con mando, «pulsa C» se dice con el botón que hace lo mismo.
				evento.texto = self.app.entrada.textos(evento.texto, acciones.JUEGO)
			elif clase == "EvFin":
				self._fin_pendiente = dict(evento.resultado)

	def estado_para_profesor(self) -> dict[str, Any]:
		"""El estado que se envía a la sala: dónde está, qué tiene delante, objetivo y contadores."""
		sesion = self.sesion
		estado = sesion.estado()
		actividad = self.estado_actividad()
		contadores: dict[str, Any] = {
			"distancia_m": estado.get("distancia_m", 0.0),
			"pasos": estado.get("pasos", 0),
			"choques": estado.get("choques", 0),
			"ayudas": sum(int(v) for v in (estado.get("ayudas") or {}).values()),
			"lugares": estado.get("descubiertos", 0),
		}
		for clave in ("hechos", "total", "puntos", "estrellas", "nivel", "tiempo_restante"):
			if isinstance(actividad.get(clave), (int, float)) and not isinstance(actividad.get(clave), bool):
				contadores[clave] = actividad[clave]
		objetivo = str(actividad.get("objetivo") or "")
		if objetivo:
			contadores["objetivo"] = objetivo[:500]
		return {
			"planta": estado.get("planta", ""),
			"x": estado.get("x", 0.0),
			"y": estado.get("y", 0.0),
			"rumbo": estado.get("rumbo", 0.0),
			"espacio": estado.get("espacio_nombre") or estado.get("espacio") or "",
			"descripcion": estado.get("descripcion", ""),
			"delante": self._texto_delante(),
			"pausado": bool(estado.get("pausado")),
			"tiempo_activo": estado.get("tiempo_activo", 0.0),
			"contadores": contadores,
			"entorno": self.entorno.nombre,
			"actividad": self.nombre_actividad,
			"modo": self.modo,
		}

	def _texto_delante(self) -> str:
		"""Lo primero que hay delante del alumno y a qué distancia, para el panel del profesor."""
		sesion = self.sesion
		jugador = sesion.jugador
		if jugador.modo != "andando":
			return ""
		try:
			impacto = sesion.mundo.rayo(jugador.planta, jugador.punto, jugador.rumbo, ALCANCE_DELANTE)
			if impacto is None:
				return _("Nada en {metros} metros").format(metros=int(ALCANCE_DELANTE))
			return sesion.leng.a_distancia(sesion.movimiento.nombre_obstaculo(impacto.seg), impacto.distancia)
		except AttributeError, ValueError, TypeError:
			log.debug("No se pudo describir lo que hay delante", exc_info=True)
			return ""

	# ── Confirmar, preguntas y eventos de la actividad ───────────────────────

	def presentar_eventos(self, eventos: list[Any] | None) -> None:
		"""Presenta al alumno eventos que la actividad ha devuelto sin emitirlos (una orden del profesor, una confirmación).

		Con la partida en marcha (también en pausa) se pasan a la sesión, que
		los devuelve en el siguiente ``avanzar`` junto con lo demás: así llegan
		a la grabadora, a la sala y al presentador por el mismo camino. Con la
		sesión ya terminada no habrá más fotogramas de juego y se entregan ya.
		"""
		if not eventos:
			return
		sesion = self.sesion
		for evento in eventos:
			sesion.emitir(evento)
		if self.terminado or sesion.terminado:
			# Si la sesión acaba de terminar por lo que ha hecho la actividad (la última confirmación), su EvFin
			# sale aquí y el fin se atiende en el fotograma siguiente; si la partida ya había terminado, no hay más fin.
			salida = sesion.avanzar(0.0)
			self._procesar(salida)
			if self.terminado:
				self._fin_pendiente = None
			self.app.entregar(salida, None)

	def confirmar(self) -> None:
		"""La acción «confirmar»: responde a la pregunta en curso o le dice a la actividad «ya está»."""
		app = self.app
		if self.actividad is None:
			app.decir(_("Aquí no hay nada que confirmar."), True, "ayuda")
			return
		pregunta = puente_actividades.pregunta_de(self.actividad)
		if pregunta is not None and pregunta["elegida"] < 0:
			# Sin respuesta elegida no hay nada que confirmar: se ofrecen las respuestas.
			self.abrir_pregunta()
			return
		eventos = puente_actividades.confirmar(self.actividad, self.sesion)
		if not eventos:
			app.sonar("interfaz/borde")
			app.decir(_("Ahora no hay nada que confirmar."), True, "ayuda")
			return
		self.presentar_eventos(eventos)

	@staticmethod
	def _clave_pregunta(pregunta: dict[str, Any] | None) -> tuple[str, tuple[str, ...]] | None:
		if pregunta is None:
			return None
		return str(pregunta["texto"]), tuple(pregunta["opciones"])

	def _revisar_pregunta(self) -> None:
		"""Abre el menú de respuestas cuando aparece una pregunta nueva y lo cierra si la prueba ha cambiado.

		Se abre un fotograma después de que aparezca, para que la instrucción de
		la prueba («Prueba 2 de 5…») suene antes que el menú, que no la corta.
		"""
		if self.actividad is None:
			return
		pregunta = puente_actividades.pregunta_de(self.actividad)
		clave = self._clave_pregunta(pregunta)
		menu = self._menu_pregunta
		if menu is not None and menu not in self.app.pila:
			self._menu_pregunta = menu = None
		if menu is not None and getattr(menu, "clave", None) != clave:
			self._cerrar_pregunta()
		if clave is None:
			self._pregunta_pendiente = None
			return
		if clave == self._pregunta_vista:
			return
		if self._pregunta_pendiente != clave:
			self._pregunta_pendiente = clave
			return
		if self.app.cima is self and not self.pausada:
			self._pregunta_vista = clave
			self._pregunta_pendiente = None
			self.abrir_pregunta(sin_cortar=True)

	def abrir_pregunta(self, sin_cortar: bool = False) -> MenuPregunta | None:
		"""Menú hablado con las respuestas de la pregunta en curso. Aceptar una es contestar (elegir y confirmar)."""
		app = self.app
		pregunta = puente_actividades.pregunta_de(self.actividad)
		if pregunta is None or self.terminado:
			return None
		if self._menu_pregunta is not None and self._menu_pregunta in app.pila:
			return self._menu_pregunta
		clave = self._clave_pregunta(pregunta)
		self._pregunta_vista = clave

		def contestar(indice: int) -> Any:
			def hacer() -> None:
				if self._clave_pregunta(puente_actividades.pregunta_de(self.actividad)) != clave:
					# La prueba ha cambiado mientras tanto (se acabó su tiempo): esta respuesta ya no vale.
					self._cerrar_pregunta()
					return
				self._cerrar_pregunta()
				eventos = list(puente_actividades.responder(self.actividad, self.sesion, indice) or [])
				eventos += puente_actividades.confirmar(self.actividad, self.sesion) or []
				self.presentar_eventos(eventos)

			return hacer

		opciones = [
			Opcion(texto, contestar(numero), ayuda=_("Elige esta respuesta y la da por buena."), callado=True)
			for numero, texto in enumerate(pregunta["opciones"])
		]
		menu = MenuPregunta(
			self,
			clave,
			pregunta["texto"],
			opciones,
			intro=_("Elige una respuesta y acéptala. Atrás vuelve al juego sin contestar; {control} abre otra vez las respuestas.").format(
				control=app.entrada.control_de("confirmar", acciones.JUEGO) or _("confirmar")
			),
		)
		if pregunta["elegida"] >= 0:
			menu.i = pregunta["elegida"]
		menu.sin_cortar = sin_cortar
		self._menu_pregunta = menu
		app.abrir(menu)
		return menu

	def _cerrar_pregunta(self) -> None:
		"""Quita el menú de respuestas sin que la partida diga «seguimos» (no estaba en pausa)."""
		menu, self._menu_pregunta = self._menu_pregunta, None
		if menu is None or menu not in self.app.pila:
			return
		self._callar_al_volver = self.app.cima is menu
		self.app.cerrar(menu)

	# ── Acciones y teclas ────────────────────────────────────────────────────

	def accion(self, accion: str, pulsada: bool) -> bool:
		"""Traduce las acciones a órdenes de la sesión; la pausa y la ayuda las atiende la pantalla."""
		if accion in _DE_LA_APLICACION:
			return False
		if accion == "pausa":  # atajo: Escape (pausa y menú)
			if pulsada:
				self.abrir_pausa()
			return True
		if accion == "ayuda":
			if pulsada:
				from app.reproductor.pantallas import ayuda

				ayuda.abrir_ayuda(self.app, acciones.JUEGO, self.ayuda_extra())
			return True
		if self.terminado or not acciones.vale_en(accion, acciones.JUEGO):
			return True
		if PAUSA_PROFESOR in self.pausas:
			if pulsada and self._reloj - self._t_aviso_pausa > 3.0:
				self._t_aviso_pausa = self._reloj
				self.app.decir(_("El juego está en pausa: lo ha parado tu profesor."), True, "aviso")
			return True
		if self.fantasma and accion in _PASOS_FANTASMA:
			if pulsada:
				self._paso_fantasma(_PASOS_FANTASMA[accion])
			return True
		if accion == "confirmar":  # atajo: M (confirmar: «ya he llegado», «esta respuesta»)
			if pulsada:
				self.confirmar()
			return True
		if acciones.es_mantenida(accion):
			self.sesion.orden(accion, 1.0 if pulsada else 0.0)
		elif pulsada:
			self.sesion.orden(accion)
		return True

	def _tecla_libre(self, evento: pygame.event.Event) -> bool:
		"""Si la tecla no tiene acción en el mapa del alumno (para no pisar una reasignación suya)."""
		return self.app.entrada.teclado.mapa.buscar(acciones.JUEGO, evento.key, int(getattr(evento, "mod", 0))) is None

	def tecla(self, evento: pygame.event.Event) -> bool:
		"""Teclas propias de la pantalla: la parte visual y, en el recorrido, la edición."""
		from app.reproductor.pantallas import recorrido

		if evento.type == pygame.CONTROLLERBUTTONDOWN:
			# El panel táctil y el botón extra no tienen acción de juego: en el recorrido abren el menú de edición.
			if self.recorrido and BOTONES_SDL.get(int(evento.button)) in ("panel", "misc"):
				recorrido.abrir_edicion(self.app, self)
				return True
			return False
		if evento.type != pygame.KEYDOWN or not self._tecla_libre(evento):
			return False
		if evento.key == pygame.K_F5:  # atajo: F5 (mostrar u ocultar el plano)
			self._alternar("juego.ver_plano", _("Plano visible."), _("Plano oculto."))
			return True
		if evento.key == pygame.K_F6:  # atajo: F6 (pantalla en negro)
			self._alternar("juego.pantalla_negra", _("Pantalla en negro."), _("Pantalla visible."))
			return True
		if self.recorrido:
			if evento.key == pygame.K_F4:  # atajo: F4 (menú de edición del modo recorrido)
				recorrido.abrir_edicion(self.app, self)
				return True
			if evento.key == pygame.K_F7:  # atajo: F7 (modo fantasma: atravesar paredes en el recorrido)
				self.alternar_fantasma()
				return True
			if evento.key == pygame.K_F8:  # atajo: F8 (saltar a un lugar en el recorrido)
				recorrido.abrir_lugares(self.app, self)
				return True
		return False

	def _alternar(self, clave: str, texto_si: str, texto_no: str) -> None:
		nuevo = not bool(self.app.config.obtener(clave, False))
		self.app.establecer(clave, nuevo)
		self.app.decir(texto_si if nuevo else texto_no, True)

	def ayuda_extra(self) -> list[str]:
		"""Líneas de ayuda de las teclas que no son acciones."""
		lineas = [_("F5: mostrar u ocultar el plano."), _("F6: pantalla en negro.")]
		if self.recorrido:
			lineas += [
				_("F4, o el panel táctil del mando: menú de edición."),
				_("F7: modo fantasma, para atravesar paredes."),
				_("F8: saltar a un lugar."),
			]
		return lineas

	# ── Recorrido: fantasma y saltos ─────────────────────────────────────────

	def alternar_fantasma(self) -> None:
		"""Activa o desactiva las colisiones (solo tiene sentido en el modo recorrido)."""
		self.fantasma = not self.fantasma
		if self.fantasma:
			self.app.decir(_("Modo fantasma activado: atraviesas paredes y objetos."), True)
		else:
			self.app.decir(_("Modo fantasma desactivado: vuelves a chocar."), True)

	def _paso_fantasma(self, relativo: float) -> None:
		"""Un paso sin colisiones: se mueve al jugador directamente y se deja que el motor anuncie el lugar."""
		sesion = self.sesion
		jugador = sesion.jugador
		if jugador.modo != "andando":
			return
		dx, dy = geo.vector_rumbo((jugador.rumbo + relativo) % 360.0)
		paso = sesion.ajustes.paso_m
		jugador.x += dx * paso
		jugador.y += dy * paso
		self.app.sonar("pasos/baldosa_izq_1", volumen=0.6, bus="pasos")
		sesion.movimiento.tras_mover(None)

	def saltar_a(self, planta: str, x: float, y: float, rumbo: float | None = None) -> None:
		"""Lleva al jugador a otro punto (lista de lugares del recorrido)."""
		actual = self.sesion.jugador.rumbo if rumbo is None else rumbo
		self.sesion.recolocar(Posicion(planta, float(x), float(y), float(actual)))

	def recargar_entorno(self) -> bool:
		"""Vuelve a leer el paquete del disco (el Estudio lo ha cambiado) y sigue en el mismo punto."""
		ruta = self.paquete.ruta
		if ruta is None:
			return False
		jugador = self.sesion.jugador
		donde = Posicion(jugador.planta, jugador.x, jugador.y, jugador.rumbo)
		try:
			paquete = entornos.abrir(ruta)
		except entornos.ErrorEntorno as error:
			self.app.decir(str(error), True, "aviso")
			return False
		inicio = donde if paquete.entorno.planta(donde.planta) is not None else None
		pedido = self.pedido(paquete.entorno)
		pedido.inicio = inicio

		def instalar(preparada: Preparada) -> None:
			# Se cambia de entorno solo al tenerlo listo: si se cancela la carga, se sigue en el de antes.
			self.app.presentador.detener_fuentes()
			self.paquete = paquete
			self.entorno = paquete.entorno
			self.app.banco.poner_entorno(paquete.recurso)
			self._inicio_pedido = inicio
			self.instalar(preparada)
			self.app.decir(_("Entorno actualizado."), True)

		carga.recrear_sesion(self.app, self, pedido, instalar)
		return True

	# ── Cambios en caliente ──────────────────────────────────────────────────

	def ajustes_cambiados(self) -> None:
		"""El alumno ha cambiado sus opciones a mitad de partida: se aplican respetando a la actividad y al profesor."""
		if not self.terminado:
			self.sesion.aplicar_ajustes(self._ajustes_de(self.app.ajustes_juego()))

	def motor_cambiado(self) -> None:
		"""El motor de sonido es otro: se le repone la pausa y el eco del lugar."""
		self.app.presentador.pausar(self.pausada)
		jugador = self.sesion.jugador
		espacio = self.sesion.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		if espacio is not None:
			self.app.motor.acustica(str(espacio.acustica))

	# ── Pausa ────────────────────────────────────────────────────────────────

	def abrir_pausa(self, anunciar: bool = True) -> Menu:
		"""Abre el menú de pausa (la sesión se detiene sola al tener un menú encima)."""
		from app.reproductor.pantallas import ayuda, opciones, recorrido

		app = self.app

		def continuar() -> None:
			app.cerrar(menu)

		def recordar_objetivo() -> None:
			app.decir(self.texto_objetivo(), True, "ayuda")

		def repetir_instrucciones() -> None:
			app.decir(self.texto_instrucciones(), True, "ayuda")

		def volver_al_inicio() -> None:
			self._ordenes_pendientes.append("volver_inicio")
			app.cerrar(menu)

		def abandonar() -> None:
			hacer = self.abandonar
			if self.recorrido:
				pregunta, si = _("¿Salir del recorrido?"), _("Sí, salir")
			elif self.actividad is None:
				pregunta, si = _("¿Terminar la exploración?"), _("Sí, terminar")
			elif puente_actividades.termina_a_voluntad(self.actividad):
				pregunta, si = _("¿Terminar la exploración? Se guardará lo que has recorrido."), _("Sí, terminar")
				hacer = self.terminar_a_voluntad
			else:
				pregunta, si = _("¿Abandonar la actividad? Se guardará lo que has hecho."), _("Sí, abandonar")
			confirmar(app, pregunta, hacer, texto_si=si, texto_no=_("No, seguir jugando"))

		def lista() -> list[Opcion]:
			opciones_menu = [
				Opcion(_("Continuar"), continuar, ayuda=_("Vuelve al juego donde lo dejaste."), callado=True),
				Opcion(_("Recordar el objetivo"), recordar_objetivo, ayuda=_("Dice lo que hay que hacer y cuánto llevas.")),
				Opcion(_("Repetir las instrucciones"), repetir_instrucciones, ayuda=_("Vuelve a decir cómo es la actividad.")),
				Opcion(
					_("Opciones rápidas"),
					lambda: opciones.abrir_opciones_rapidas(app),
					ayuda=_("Volumen, voz, detalle y forma de decir las direcciones."),
				),
				Opcion(_("Volver al inicio"), volver_al_inicio, ayuda=_("Te lleva al punto de partida del entorno.")),
			]
			if self.recorrido:
				opciones_menu += [
					Opcion(
						_("Menú de edición"),
						lambda: recorrido.abrir_edicion(app, self),
						ayuda=_("Pide al Estudio que coloque, marque o mida algo donde estás."),
					),
					Opcion(
						_("Saltar a un lugar"),
						lambda: recorrido.abrir_lugares(app, self),
						ayuda=_("Lista de plantas y lugares del entorno."),
					),
					Opcion(
						lambda: _("Modo fantasma: {estado}").format(estado=_("activado") if self.fantasma else _("desactivado")),
						ajuste=lambda _delta: self.alternar_fantasma(),
						ayuda=_("Con el modo fantasma atraviesas paredes y objetos."),
					),
				]
			opciones_menu.append(
				Opcion(
					_("Ayuda"), lambda: ayuda.abrir_ayuda(app, acciones.JUEGO, self.ayuda_extra()), ayuda=_("La lista de teclas y botones.")
				)
			)
			if self.recorrido:
				opciones_menu.append(Opcion(_("Salir del recorrido"), abandonar, ayuda=_("Cierra el recorrido y vuelve al Estudio.")))
			elif self.actividad is None:
				opciones_menu.append(
					Opcion(_("Terminar la exploración"), abandonar, ayuda=_("Guarda lo recorrido y vuelve al menú principal."))
				)
			elif puente_actividades.termina_a_voluntad(self.actividad):
				opciones_menu.append(
					Opcion(_("Terminar la exploración"), abandonar, ayuda=_("Da la exploración por terminada y dice lo que has recorrido."))
				)
			else:
				opciones_menu.append(
					Opcion(_("Abandonar la actividad"), abandonar, ayuda=_("Deja la actividad sin terminar y vuelve al menú principal."))
				)
			return opciones_menu

		menu = Menu(app, textos.frase("pausa", app.estilo), lista, con_volver=False)
		app.sonar("interfaz/abrir")
		app.abrir(menu)
		return menu

	def terminar_a_voluntad(self) -> None:
		"""Da por terminada una actividad sin final propio (exploración): no es abandonarla, y se va a la pantalla de fin."""
		if not self.terminado:
			# El menú de pausa sale sin hablar: lo siguiente que se oye es el resultado.
			while self.app.cima is not self and self in self.app.pila:
				self.app.pila.pop()
			self.sesion.terminar()
			eventos = self.sesion.avanzar(0.0)
			self._procesar(eventos)
			self.app.entregar(eventos, None)
			if self._fin_pendiente is not None:
				resultado, self._fin_pendiente = self._fin_pendiente, None
				self._fin(resultado)

	def abandonar(self) -> None:
		"""Termina la partida sin completarla (o da por terminada la exploración libre)."""
		if not self.terminado:
			self.sesion.terminar({"abandonada": self.actividad is not None, "completada": False})
			# La sesión está en pausa por el menú: se recoge el fin aquí, sin esperar al siguiente fotograma.
			eventos = self.sesion.avanzar(0.0)
			self._procesar(eventos)
			self.app.entregar(eventos, None)
			if self._fin_pendiente is not None:
				resultado, self._fin_pendiente = self._fin_pendiente, None
				self._fin(resultado)

	# ── Fin ──────────────────────────────────────────────────────────────────

	def _fin(self, resultado: dict[str, Any]) -> None:
		"""La sesión ha terminado: se avisa a la sala, se guardan las puntuaciones y se abre lo que toque."""
		from app.reproductor.pantallas import fin

		app = self.app
		self.terminado = True
		self.resultado = resultado
		abandonada = bool(resultado.get("abandonada"))
		self.completada = bool(resultado.get("completada", self.actividad is not None and not abandonada))
		menu, self._menu_pregunta = self._menu_pregunta, None
		if menu is not None and menu in app.pila:
			# La pregunta ya no espera respuesta: el menú sale sin hablar (lo que sigue es el resultado).
			app.pila.remove(menu)
		if self.actividad is not None and not self.recorrido and not self.tutorial:
			self._anotar_nivel(resultado)
		if self.grabadora is not None:
			puntuaciones = resultado.get("puntuaciones")
			if not isinstance(puntuaciones, dict):
				puntuaciones = {
					clave: resultado[clave] for clave in ("puntos", "estrellas", "nota", "aciertos", "errores") if clave in resultado
				}
			if puntuaciones:
				self.grabadora.puntuaciones(puntuaciones)
		if app.enlace is not None and not self.recorrido:
			app.enlace.fin(self.completada, resultado)
		app.presentador.detener_fuentes()
		if self.recorrido:
			app.decir(_("Recorrido terminado."), True)
			app.cerrar_partida()
			app.salir()
			return
		if self.tutorial:
			if self.completada and app.perfil is not None:
				app.perfil.tutorial_hecho = True
				app.perfil.guardar()
			frase = (
				textos.frase("tutorial_fin", app.estilo)
				if self.completada
				else _("Tutorial sin terminar. Puedes repetirlo cuando quieras.")
			)
			if self.completada:
				app.sonar("logro/logro")
			app.volver_al_menu()
			app.decir(frase, True)
			return
		if self.actividad is None or abandonada:
			frase = self._resumen_corto(resultado, abandonada)
			app.volver_al_menu()
			app.decir(frase, True)
			return
		fin.abrir_fin(app, self)

	def _resumen_corto(self, resultado: dict[str, Any], abandonada: bool) -> str:
		"""Lo que se dice al dejar una exploración o abandonar una actividad."""
		lugares = len(resultado.get("espacios_visitados") or ())
		datos = _("Has recorrido {metros} metros en {tiempo} y has pasado por {lugares}.").format(
			metros=round(float(resultado.get("distancia_m") or 0.0)),
			tiempo=textos.duracion(float(resultado.get("tiempo_activo") or 0.0)),
			lugares=_n("{n} lugar", "{n} lugares", lugares).format(n=lugares),
		)
		cabecera = _("Actividad abandonada.") if abandonada else _("Exploración terminada.")
		return f"{cabecera} {datos}"

	def apuntar_valoracion(self, respuestas: dict[str, Any]) -> None:
		"""Guarda en la sesión las respuestas del cuestionario final (evento «valoracion»).

		Si la actividad sabe valorarse (``valorar``), lo apunta ella con su
		registro, que se recoge aquí aunque la sesión ya haya terminado; si no,
		se apunta directamente en la grabación y se envía a la sala.
		"""
		valorar = getattr(self.actividad, "valorar", None) if self.actividad is not None else None
		if callable(valorar):
			try:
				limpias = valorar(self.sesion, dict(respuestas))
			except Exception:  # noqa: BLE001 - la actividad es código ajeno al reproductor: se apunta de forma genérica
				log.exception("Fallo de la actividad al apuntar la valoración")
			else:
				# El resultado que se grabará al salir de la pantalla de fin lleva también las respuestas.
				if isinstance(self.resultado, dict):
					self.resultado["valoracion"] = dict(limpias) if isinstance(limpias, dict) else dict(respuestas)
				eventos = self.sesion.avanzar(0.0)
				self._procesar(eventos)
				self.app.entregar(eventos, None)
				self._fin_pendiente = None
				return
		if self.grabadora is not None:
			self.grabadora.evento("valoracion", dict(respuestas))
		if self.app.enlace is not None:
			self.app.enlace.evento("valoracion", dict(respuestas))

	def reiniciar(self) -> None:
		"""Empieza de nuevo la misma actividad (lo pide el profesor). La sesión anterior se guarda como no completada.

		En un entorno grande la nueva sesión se prepara con la pantalla de
		carga; la anterior se guarda al tener lista la nueva (si se cancela la
		carga, se sigue jugando la de antes).
		"""
		# Si había una pantalla de fin o un menú encima, se quitan: se vuelve a jugar.
		while self.app.cima is not self and self in self.app.pila:
			self.app.pila.pop()

		def instalar(preparada: Preparada) -> None:
			if self.grabadora is not None:
				try:
					self.grabadora.terminar(False, {**self.sesion.resumen(), "reiniciada": True, "completada": False})
				except OSError:
					log.exception("No se pudo guardar la sesión antes de reiniciar")
			self.app.presentador.detener_fuentes()
			self.app.presentador.pausar(False)
			self.instalar(preparada)

		carga.recrear_sesion(self.app, self, self.pedido(), instalar)

	# ── Órdenes del profesor ─────────────────────────────────────────────────

	def orden_profesor(self, tipo: str, datos: dict[str, Any]) -> None:
		"""Aplica una orden llegada de la sala del Estudio (ver ``docs/supervision.md``)."""
		app = self.app
		sesion = self.sesion
		if self.grabadora is not None and tipo not in ("respuesta", "marca"):
			self.grabadora.intervencion(tipo, datos)
		if tipo == "pausa":
			if PAUSA_PROFESOR not in self.pausas:
				self.pausar(PAUSA_PROFESOR)
				app.decir(_("Tu profesor ha puesto el juego en pausa."), True, "profesional")
		elif tipo == "reanudar":
			if PAUSA_PROFESOR in self.pausas:
				self.reanudar(PAUSA_PROFESOR)
				app.decir(_("Tu profesor ha reanudado el juego."), True, "profesional")
		elif tipo == "recolocar":
			rumbo = datos.get("rumbo")
			sesion.recolocar(
				Posicion(
					str(datos.get("planta") or sesion.jugador.planta),
					float(datos.get("x", sesion.jugador.x)),
					float(datos.get("y", sesion.jugador.y)),
					float(rumbo) if isinstance(rumbo, (int, float)) and math.isfinite(rumbo) else sesion.jugador.rumbo,
				)
			)
			app.decir(_("Tu profesor te ha llevado a otro sitio."), True, "profesional")
		elif tipo == "mensaje":
			app.sonar("logro/pista", volumen=0.7)
			app.haptica.patron("aviso")
			app.decir(str(datos.get("texto") or ""), True, "profesional")
			if self.actividad is not None:
				# La actividad también se entera (una visita narrada cuenta los mensajes del profesional). Su voz
				# sobra: el mensaje ya se ha dicho arriba; se presenta solo lo demás (un registro, un sonido).
				eventos = puente_actividades.orden(self.actividad, sesion, "mensaje", dict(datos))
				self.presentar_eventos([evento for evento in (eventos or []) if type(evento).__name__ != "EvVoz"])
		elif tipo in ("pista", "ayudas", "premio"):
			self._orden_de_actividad(tipo, datos)
		elif tipo == "marca":
			if self.grabadora is not None:
				self.grabadora.marca(str(datos.get("texto") or ""))
		elif tipo == "reiniciar":
			if self.recorrido:
				self.recargar_entorno()
			else:
				self.reiniciar()
				app.decir(_("Tu profesor ha reiniciado la actividad. Empezamos de nuevo."), True, "profesional")
		elif tipo == "terminar":
			if not self.terminado:
				app.decir(_("Tu profesor ha terminado la actividad."), True, "profesional")
				sesion.terminar({"terminada_por_profesor": True})
				eventos = sesion.avanzar(0.0)
				self._procesar(eventos)
				app.entregar(eventos, None)
		elif tipo == "respuesta":
			self._respuesta(datos)
		else:
			log.warning("Orden del profesor desconocida: %s", tipo)

	def _orden_de_actividad(self, tipo: str, datos: dict[str, Any]) -> None:
		"""Pista, ayudas y premio: primero se le ofrecen a la actividad; si no las atiende, las aplica el reproductor."""
		app = self.app
		sesion = self.sesion
		if tipo == "ayudas":
			reglas = datos.get("ayudas")
			for ayuda, regla in reglas.items() if isinstance(reglas, dict) else ():
				self.ayudas_profesor[str(ayuda)] = regla_ayuda(regla)
		# La actividad devuelve los eventos sin emitirlos: hay que presentarlos (voz «profesional», sonido de pista…).
		eventos = puente_actividades.orden(self.actividad, sesion, tipo, dict(datos)) if self.actividad is not None else None
		if eventos is not None:
			self.presentar_eventos(eventos)
			if tipo == "ayudas":
				self.ajustes_cambiados()
			return
		if tipo == "ayudas":
			for ayuda, regla in self.ayudas_profesor.items():
				sesion.permitir_ayuda(ayuda, bool(regla.get("permitida", True)), regla.get("limite"))
			app.decir(_("Tu profesor ha cambiado las ayudas disponibles."), False, "profesional")
		elif tipo == "pista":
			texto = str(datos.get("texto") or "")
			app.sonar("logro/pista")
			if texto:
				app.decir(texto, True, "profesional")
			destino = datos.get("destino")
			segundos = datos.get("baliza_s")
			if isinstance(destino, dict) and isinstance(segundos, (int, float)) and segundos > 0:
				try:
					lugar = (str(destino.get("planta") or sesion.jugador.planta), float(destino["x"]), float(destino["y"]))
				except KeyError, TypeError, ValueError:
					log.warning("El destino de la pista del profesor no es válido.")
				else:
					sesion.permitir_ayuda("baliza", True, None)
					sesion.baliza(lugar)
					sesion.programar(float(segundos), lambda: sesion.baliza(None))
		elif tipo == "premio":
			nombre = str(datos.get("nombre") or _("un premio"))
			mensaje = str(datos.get("mensaje") or "") or _("Tu profesor ha escondido {nombre}. ¡Búscalo!").format(nombre=nombre)
			app.sonar("premio/aparece")
			app.decir(mensaje, True, "profesional")
			if all(isinstance(datos.get(clave), (int, float)) for clave in ("x", "y")):
				sesion.anadir_fuente(
					f"premio_profesor_{datos.get('id') or nombre}",
					str(datos.get("sonido") or "premio/cerca"),
					(str(datos.get("planta") or sesion.jugador.planta), float(datos["x"]), float(datos["y"])),
					bus="ayudas",
				)

	def _respuesta(self, datos: dict[str, Any]) -> None:
		"""Respuesta del Estudio a una petición del modo recorrido: se dice y, si cambió el entorno, se recarga."""
		texto = str(datos.get("texto") or "")
		aceptada = bool(datos.get("aceptada"))
		self.app.sonar("interfaz/elegir" if aceptada else "logro/error")
		self.app.decir(texto or (_("Hecho.") if aceptada else _("El Estudio no ha podido hacerlo.")), True, "profesional")
		extra = datos.get("datos")
		if aceptada and isinstance(extra, dict) and extra.get("recargar"):
			self.recargar_entorno()

	# ── Parte visual ─────────────────────────────────────────────────────────

	def titulo_visible(self) -> str:
		"""Entorno y actividad."""
		return f"{self.entorno.nombre}. {self.nombre_actividad}"

	def lineas(self) -> tuple[list[str], int]:
		"""Sin plano: el objetivo en texto grande."""
		return self.app.partir(self.texto_objetivo(), 24, 900), -1

	def dibujar(self, lienzo: Any) -> bool:
		"""Dibuja el plano de la planta si está activado; si no, deja que se dibuje el texto."""
		if not self.app.config.obtener("juego.ver_plano", True):
			return False
		plano.dibujar(self.app, lienzo, self)
		return True
