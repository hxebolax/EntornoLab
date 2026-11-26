"""La aplicación del reproductor: ventana, bucle a 60 fotogramas y pila de pantallas.

Une lo que ya existe (motor, sonido, voz, entrada, seguimiento y supervisión)
y no contiene reglas de juego. Cada fotograma hace, siempre en este orden::

	entrada  →  pantalla de arriba y partida  →  Presentador.aplicar(eventos, sesion, dt)

``Presentador.aplicar`` se llama en TODOS los fotogramas, también en los
menús y aunque una pantalla haya fallado: es quien llama a ``tic`` del motor
de sonido, y la protección auditiva calla la salida si deja de recibirlo.

Decisiones que conviene conocer:

- **Un fallo en un fotograma no cierra el reproductor.** Se registra, se dice
  una vez y se sigue; si la misma pantalla falla varias veces seguidas, se
  vuelve al menú principal. El alumno nunca se queda ante una ventana muerta.
- **Pila de pantallas**, como en Puerto Bravo: la de arriba recibe las
  acciones; la partida, si existe, sigue viva debajo de sus menús (en pausa) y
  sigue atendiendo al profesor.
- **Opciones en caliente.** La aplicación se suscribe a la configuración
  compartida y aplica cada cambio al momento (volúmenes, motor de sonido,
  perfil de cabeza, voz, mando, ajustes de juego, idioma), lo cambie el menú
  de opciones o quien sea.
- **Modo de pruebas** (``pruebas=True``): controladores «dummy» de SDL, motor
  de sonido nulo, ``VozFalsa`` y sin tocar los mandos reales. Las pruebas
  manejan la aplicación con ``inyectar`` (acciones), ``tecla`` (teclas por el
  camino real) y ``avanzar`` (fotogramas).
- **Arranque oculto** (``oculta=True``, para ``--comprobar-arranque``): la
  ventana no se muestra, y no suena ni habla nada.
"""

from __future__ import annotations

import logging
import os
import time
from pathlib import Path
from typing import Any

import pygame

from app.audio import paquetes
from app.audio.banco import Banco
from app.audio.base import ErrorMotor, MotorAudio
from app.audio.cabeza import Cabeza
from app.audio.fabrica import clase_motor, crear_motor, nombre_motor
from app.audio.haptica import Haptica
from app.audio.presentador import Presentador
from app.audio.voz import Voz, VozFalsa
from app.core import i18n
from app.core.configuracion import ErrorConfiguracion, obtener_configuracion
from app.core.i18n import _
from app.core.version import APP_VERSION, NOMBRE_APLICACION
from app.dominio.catalogo import Catalogo
from app.entrada import acciones
from app.entrada.entrada import Entrada
from app.entrada.mando import sanear_opciones
from app.motor.sesion import AjustesJuego
from app.reproductor import ajustes, entornos, textos
from app.reproductor.alumno import Perfil, alias_para_mostrar, normalizar_alias
from app.reproductor.menus import Menu, Pantalla

log = logging.getLogger(__name__)

ANCHO = 960
ALTO = 600
FOTOGRAMAS = 60
# Un fotograma nunca avanza más que esto: tras un parón (arrastrar la ventana, un antivirus) no se da un salto.
DT_MAXIMO = 0.1
# Fallos seguidos de la misma pantalla tras los que se vuelve al menú principal.
FALLOS_SEGUIDOS_MAXIMOS = 5
# Segundos mínimos entre dos avisos hablados de fallo.
ESPERA_AVISO_FALLO = 15.0

_EVENTOS_CRUDOS = (
	pygame.KEYDOWN,
	pygame.KEYUP,
	pygame.TEXTINPUT,
	pygame.CONTROLLERBUTTONDOWN,
	pygame.CONTROLLERBUTTONUP,
)


def es_tecla_restablecer_voz(evento: pygame.event.Event) -> bool:
	"""Si la pulsación es Control+F12, la tecla de emergencia que devuelve la voz automática.

	Se atiende antes que la pantalla y que el mapa de teclas, porque quien se ha
	quedado sin voz no puede saber en qué pantalla está. F12 es una tecla fija
	(``app.entrada.teclado.FIJAS``): el alumno no puede asignarle otra acción.
	Con Alt no cuenta (Alt con otra tecla es del sistema).
	"""
	mod = int(getattr(evento, "mod", 0))
	return getattr(evento, "key", None) == pygame.K_F12 and bool(mod & pygame.KMOD_CTRL) and not mod & pygame.KMOD_ALT


# Paletas: (fondo, texto, destacado, tenue). Ninguna información depende solo del color.
PALETA_NORMAL = ((16, 20, 28), (235, 235, 235), (255, 214, 64), (150, 156, 168))
PALETA_CONTRASTE = ((0, 0, 0), (255, 255, 255), (255, 255, 0), (200, 200, 200))


class Aplicacion:
	"""El reproductor en marcha. Ver el docstring del módulo."""

	def __init__(self, opciones: Any = None, pruebas: bool = False, oculta: bool = False, config: Any = None) -> None:
		"""``opciones`` son las ``OpcionesReproductor`` de la línea de órdenes (None = sin argumentos)."""
		self.opciones = opciones
		self.pruebas = pruebas
		self.oculta = oculta
		self.silenciosa = pruebas or oculta
		self.config = config if config is not None else obtener_configuracion()
		self.activa = True
		self.codigo_salida = 0
		self.con_foco = True
		self.pila: list[Pantalla] = []
		self.partida: Any = None
		self.enlace: Any = None
		self.error_inicial = ""
		self.fallos = 0
		self._fallos_seguidos = 0
		#: Último paquete de diagnóstico generado desde la ayuda (None mientras no se haya generado ninguno).
		self.ultimo_paquete_diagnostico: Any = None
		self._t_aviso_fallo = -1e9
		self._eventos: list[Any] = []
		self._sesion: Any = None
		self._catalogo: Catalogo | None = None
		self._textos: dict[tuple[str, int, tuple[int, int, int]], pygame.Surface] = {}
		self._fuentes: dict[int, pygame.font.Font] = {}
		self._cancelar_config: Any = None
		self._cancelar_paquetes: Any = None
		self._cambiando_motor = False
		self._ultimo_dibujado = ""
		self.cabeza: Cabeza | None = None
		# Opciones extra para ``ClienteSupervision`` (las pruebas acortan sus esperas).
		self.opciones_cliente: dict[str, Any] = {}

		if pruebas:
			os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
			os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
		os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")
		pygame.init()
		banderas = pygame.HIDDEN if oculta else 0
		self.lienzo = pygame.display.set_mode((ANCHO, ALTO), banderas)
		pygame.display.set_caption(NOMBRE_APLICACION)
		pygame.key.set_repeat(0)
		self.reloj = pygame.time.Clock()

		# La voz primero: si algo de lo que sigue tarda o falla, ya se puede decir.
		self.voz: Any = VozFalsa(ajustes.opciones_voz(self.config)) if self.silenciosa else Voz(ajustes.opciones_voz(self.config))
		self._instalar_ventana()
		self.banco = Banco()
		opciones_sonido = ajustes.opciones_sonido(self.config, memoria=pruebas)
		if self.silenciosa:
			opciones_sonido["motor"] = "nulo"
		self.motor: MotorAudio = crear_motor(opciones_sonido, self.banco)
		self.entrada = Entrada(
			ajustes.mapa_o_nada(self.config.obtener("teclado.mapa")),
			ajustes.mapa_o_nada(self.config.obtener("mando.mapa")),
			ajustes.opciones_mando(self.config),
			iniciar_mandos=not pruebas,
		)
		self.haptica = Haptica(self.entrada.vibrar, ajustes.opciones_haptica(self.config))
		self._ajustar_cabeza()
		self.presentador = Presentador(self.motor, self.voz, self.haptica, self.cabeza, banco=self.banco)
		self._cancelar_paquetes = paquetes.conectar(self.banco, self.config)
		self._cancelar_config = self.config.suscribir(self._config_cambiada)

		alias = normalizar_alias(getattr(opciones, "alumno", None) or "")
		self.alias_pedido = bool(alias)
		if not alias:
			alias = normalizar_alias(str(self.config.obtener("juego.alias", "") or ""))
		self.perfil: Perfil | None = None
		if alias:
			self.poner_alumno(alias, anunciar=False)
		log.info(
			"Reproductor %s iniciado: motor de sonido %s, voz %s, modo %s.",
			APP_VERSION,
			self.motor.nombre,
			getattr(self.voz, "nombre", "?"),
			"pruebas" if pruebas else ("oculto" if oculta else "normal"),
		)
		if getattr(opciones, "supervisado", False):
			self.conectar_sala(str(opciones.sala_host), int(opciones.sala_puerto), str(opciones.codigo or ""))
		self._pantallas_iniciales()

	# ── Arranque ─────────────────────────────────────────────────────────────

	def _instalar_ventana(self) -> None:
		"""Da a la voz el identificador de la ventana, para el braille fijo de NVDA."""
		try:
			ventana = int(pygame.display.get_wm_info().get("window") or 0)
		except pygame.error, TypeError, ValueError:
			ventana = 0
		if ventana and not self.silenciosa:
			try:
				self.voz.instalar_ventana(ventana)
			except OSError, AttributeError:
				log.warning("No se pudo preparar la ventana para el braille.", exc_info=True)

	def _ajustar_cabeza(self) -> None:
		"""Arranca o para el seguimiento de cabeza según la configuración."""
		quiere = bool(self.config.obtener("sonido.seguimiento_cabeza", False)) and not self.silenciosa
		if quiere and self.cabeza is None:
			cabeza = Cabeza(int(self.config.obtener("sonido.seguimiento_cabeza_puerto", 4242)))
			if cabeza.iniciar():
				self.cabeza = cabeza
			else:
				log.warning("No se pudo iniciar el seguimiento de cabeza (¿puerto ocupado?).")
		elif not quiere and self.cabeza is not None:
			self.cabeza.parar()
			self.cabeza = None
		if hasattr(self, "presentador"):
			self.presentador.cabeza = self.cabeza

	def _pantallas_iniciales(self) -> None:
		"""Abre lo que piden los argumentos: el recorrido, un entorno, una actividad o el menú principal."""
		from app.reproductor.pantallas import elegir, principal

		opciones = self.opciones
		ruta: Path | None = getattr(opciones, "paquete", None)
		recorrido = getattr(opciones, "modo", "") == "recorrido"
		principal.abrir_menu_principal(self, saludar=ruta is None)
		if ruta is None:
			if self.perfil is None:
				principal.abrir_quien_eres(self)
			return
		try:
			paquete = entornos.abrir(ruta)
		except entornos.ErrorEntorno as error:
			self.error_inicial = str(error)
			self.codigo_salida = 3
			self.sonar("logro/error")
			self.decir(str(error), True, "aviso")
			return
		if recorrido:
			self.empezar_partida(paquete, None, recorrido=True)
			return
		pedida = getattr(opciones, "actividad", None)
		if pedida:
			datos = paquete.actividad(str(pedida))
			if datos is None:
				self.decir(_("El entorno no tiene la actividad «{id}». Elige otra.").format(id=pedida), True, "aviso")
				elegir.abrir_actividades(self, paquete)
			else:
				self.empezar_partida(paquete, datos)
			return
		elegir.abrir_actividades(self, paquete)

	# ── Alumno ───────────────────────────────────────────────────────────────

	@property
	def alias(self) -> str:
		"""Alias del alumno actual («invitado» si no se ha elegido ninguno)."""
		return self.perfil.alias if self.perfil is not None else "invitado"

	@property
	def estilo(self) -> str:
		"""Estilo de presentación del alumno: infantil, juvenil o adulto."""
		return textos.estilo_valido(str(self.preferencia("juego.estilo", "adulto")))

	def preferencia(self, clave: str, defecto: Any = None) -> Any:
		"""El valor que vale para el alumno: su ficha del Estudio, si no su perfil y, si no, la configuración.

		Por qué en capas y no en la configuración compartida: ``config.json`` lo
		escriben el Estudio y el reproductor. Si las preferencias de cada
		alumno se volcaran ahí al elegir alias, pisarían las del profesional
		(que en el Estudio son los valores de serie para todos) y las del
		alumno anterior. Así la configuración solo guarda lo del equipo, el
		perfil lo del alumno y la ficha (que llega por la sala) lo que fija el
		profesional, que manda sobre lo demás.
		"""
		if clave in ajustes.PREFERENCIAS_JUEGO and self.perfil is not None:
			campo = ajustes.CAMPO_DE_CLAVE.get(clave, "")
			de_ficha = self.perfil.ficha.get("ajustes")
			if isinstance(de_ficha, dict) and campo in de_ficha:
				return de_ficha[campo]
			if clave in self.perfil.preferencias:
				return self.perfil.preferencias[clave]
		return self.config.obtener(clave, defecto)

	def _preferencias_juego(self) -> dict[str, Any]:
		"""Lo que vale ahora para cada preferencia de juego (para saber qué cambia al cambiar de capa)."""
		return {clave: self.preferencia(clave) for clave in ajustes.PREFERENCIAS_JUEGO}

	def _avisar_preferencias(self, antes: dict[str, Any]) -> None:
		"""Aplica en caliente las preferencias de juego que han cambiado respecto de ``antes``."""
		for clave, nuevo in self._preferencias_juego().items():
			if nuevo != antes.get(clave):
				self._config_cambiada(clave, antes.get(clave), nuevo)

	def poner_alumno(self, alias: str, anunciar: bool = True) -> None:
		"""Cambia de alumno: carga su perfil, aplica sus preferencias de juego y lo recuerda para la próxima vez.

		Las preferencias del alumno se quedan en su perfil (ver ``preferencia``):
		en la configuración compartida solo se apunta el alias.
		"""
		antes = self._preferencias_juego()
		limpio = normalizar_alias(alias)
		if not limpio:
			self.perfil = None
			self._avisar_preferencias(antes)
			return
		perfil = Perfil.cargar(limpio)
		for clave, valor in list(perfil.preferencias.items()):
			if clave not in ajustes.PREFERENCIAS_JUEGO:
				continue
			try:
				self.config.validar(clave, valor)
			except ErrorConfiguracion:
				log.warning("Preferencia no válida en el perfil del alumno: %s; se ignora.", clave)
				del perfil.preferencias[clave]
		self.perfil = perfil
		try:
			self.config.establecer("juego.alias", perfil.alias)
		except ErrorConfiguracion:
			log.exception("No se pudo recordar el alias del alumno")
		if not perfil.ruta.is_file():
			perfil.guardar()
		self._avisar_preferencias(antes)
		if anunciar:
			self.decir(textos.frase("saludo", self.estilo, alias=alias_para_mostrar(perfil.alias)), True)

	# ── Ficha del Estudio y niveles ──────────────────────────────────────────

	def recibir_ficha(self, datos: dict[str, Any]) -> None:
		"""Orden ``alumno`` de la sala: ajustes, lista de trabajo y niveles de la ficha del Estudio.

		Mandan sobre las preferencias locales y se guardan en el perfil para
		los días sin sala. La partida en curso se recalcula al momento.
		"""
		if self.perfil is None:
			log.info("Ficha del Estudio recibida sin alumno elegido: se ignora.")
			return
		antes = self._preferencias_juego()
		ajustes_ficha = datos.get("ajustes") if isinstance(datos.get("ajustes"), dict) else None
		lista = datos.get("lista") if isinstance(datos.get("lista"), list) else None
		niveles = datos.get("niveles") if isinstance(datos.get("niveles"), dict) else None
		cambiados = self.perfil.recibir_ficha(ajustes_ficha, lista, niveles)
		log.info(
			"Ficha del Estudio recibida: %d ajustes, %d actividades asignadas, %d niveles cambiados.",
			len(ajustes_ficha or {}),
			len(lista or []),
			len(cambiados),
		)
		self._avisar_preferencias(antes)

	def nivel_actividad(self, entorno_id: str, actividad_id: str) -> int | None:
		"""Nivel de ayudas con el que empieza la actividad (lo pide ``PantallaJuego``). None = el de la actividad."""
		if self.perfil is None or not actividad_id:
			return None
		return self.perfil.nivel(str(entorno_id), str(actividad_id))

	def anotar_nivel(self, entorno_id: str, actividad_id: str, nivel: int) -> None:
		"""Apunta en el perfil el nivel con el que empezará la próxima vez (lo llama ``PantallaJuego`` al terminar)."""
		if self.perfil is None or not actividad_id or isinstance(nivel, bool) or not isinstance(nivel, int):
			return
		self.perfil.poner_nivel(str(entorno_id), str(actividad_id), nivel)

	def releer_configuracion(self) -> list[str]:
		"""Vuelve a leer ``config.json`` (lo ha cambiado el Estudio) y aplica solo lo que haya cambiado.

		Los avisos llegan a ``_config_cambiada`` y a la suscripción de los
		paquetes de sonido: los mismos manejadores que un cambio hecho aquí.
		"""
		recargar = getattr(self.config, "recargar", None)
		if not callable(recargar):
			return []
		try:
			return list(recargar())
		except Exception:  # noqa: BLE001 - una configuración ilegible del otro proceso no debe parar el juego
			log.exception("No se pudo releer la configuración compartida")
			return []

	# ── Voz y sonido ─────────────────────────────────────────────────────────

	def decir(self, texto: str, interrumpir: bool = True, canal: str = "juego") -> float:
		"""Dice un texto (con los nombres de botón del mando si lo hay) y baja el ambiente mientras dura."""
		if not texto:
			return 0.0
		return self.presentador.decir(self.entrada.textos(texto, self.contexto), interrumpir, canal)

	def decir_menu(self, texto: str) -> float:
		"""Lo que se dice al moverse por un menú: corta lo anterior."""
		return self.decir(texto, True, "juego")

	def callar(self) -> None:
		"""Corta la voz."""
		self.voz.callar()

	def sonar(self, nombre: str, volumen: float = 1.0, bus: str = "interfaz") -> int:
		"""Un sonido de interfaz, sin posición. Devuelve el canal (0 si no pudo sonar)."""
		try:
			return int(self.presentador.sonido(nombre, bus=bus, volumen=volumen))
		except ErrorMotor, OSError, ValueError, KeyError:
			log.warning("No se pudo reproducir el sonido %s.", nombre, exc_info=True)
			return 0

	def entregar(self, eventos: list[Any], sesion: Any) -> None:
		"""La partida deja aquí lo ocurrido en el fotograma; la aplicación lo presenta al final del mismo."""
		self._eventos.extend(eventos)
		self._sesion = sesion

	@property
	def posicion_menu(self) -> bool:
		"""Si los menús dicen «3 de 9»."""
		return bool(self.config.obtener("juego.posicion_menu", True))

	@property
	def catalogo(self) -> Catalogo:
		"""El catálogo de complementos (se carga la primera vez que hace falta)."""
		if self._catalogo is None:
			self._catalogo = entornos.cargar_catalogo()
		return self._catalogo

	def ajustes_juego(self) -> AjustesJuego:
		"""Los ajustes de juego del alumno: ficha del Estudio encima de su perfil, encima de la configuración."""
		return ajustes.ajustes_juego(self.config, self.preferencia)

	# ── Pila de pantallas ────────────────────────────────────────────────────

	@property
	def cima(self) -> Pantalla | None:
		"""La pantalla de arriba, que es la que recibe las acciones."""
		return self.pila[-1] if self.pila else None

	@property
	def contexto(self) -> str:
		"""Contexto de entrada de la pantalla de arriba (``menu`` o ``juego``)."""
		cima = self.cima
		return cima.contexto if cima is not None else acciones.MENU

	def abrir(self, pantalla: Pantalla) -> None:
		"""Pone una pantalla arriba de la pila."""
		log.debug("Se abre la pantalla %s", type(pantalla).__name__)
		self.pila.append(pantalla)
		pantalla.al_entrar()

	def cerrar(self, pantalla: Pantalla | None = None) -> None:
		"""Quita una pantalla (la de arriba si no se dice cuál).

		Primero vuelve a hablar la que queda arriba y después se avisa a la que
		sale: así lo que diga su respuesta («Alias guardado») se oye lo último,
		no tapado por el título del menú al que se vuelve.
		"""
		if not self.pila:
			return
		if pantalla is None:
			pantalla = self.pila[-1]
		if pantalla not in self.pila:
			return
		era_cima = self.pila[-1] is pantalla
		log.debug("Se cierra la pantalla %s", type(pantalla).__name__)
		self.pila.remove(pantalla)
		cima = self.cima
		if era_cima and cima is not None:
			cima.al_entrar()
		pantalla.al_salir()

	def empezar_partida(
		self, paquete: Any, datos_actividad: dict[str, Any] | None, recorrido: bool = False, tutorial: bool = False, actividad: Any = None
	) -> bool:
		"""Empieza a jugar un entorno (con una actividad o en exploración libre). False si no se pudo preparar.

		Un entorno grande (un barrio importado) se prepara en segundo plano con
		la pantalla de carga (``app.reproductor.carga``): la ventana sigue
		respondiendo, se dice cómo va y Escape cancela. Entonces devuelve True
		en cuanto empieza la carga; la partida se abre al acabar.
		"""
		from app.reproductor import carga, puente_actividades
		from app.reproductor.pantallas.juego import PantallaJuego

		if carga.es_grande(paquete.entorno):
			try:
				carga.abrir_partida(self, paquete, datos_actividad, recorrido=recorrido, tutorial=tutorial, actividad=actividad)
			except puente_actividades.ErrorActividad as error:
				self.sonar("logro/error")
				self.decir(str(error), True, "aviso")
				return False
			return True
		try:
			partida = PantallaJuego(self, paquete, datos_actividad, recorrido=recorrido, tutorial=tutorial, actividad=actividad)
		except puente_actividades.ErrorActividad as error:
			self.sonar("logro/error")
			self.decir(str(error), True, "aviso")
			return False
		self.instalar_partida(partida)
		return True

	def instalar_partida(self, partida: Pantalla) -> None:
		"""Pone una partida ya preparada en marcha, sobre el menú principal (cierra la que hubiera)."""
		self.cerrar_partida()
		# La partida va sobre el menú principal: al terminar se vuelve a él.
		del self.pila[1:]
		self.partida = partida
		self.abrir(partida)

	def cerrar_partida(self) -> None:
		"""Termina la partida en curso (si la hay) y graba su sesión."""
		partida, self.partida = self.partida, None
		if partida is None:
			return
		try:
			partida.finalizar()
		except Exception:  # noqa: BLE001 - cerrar una partida rota no debe impedir volver al menú
			log.exception("Fallo al cerrar la partida")
		if partida in self.pila:
			self.pila.remove(partida)
		self._sesion = None

	def volver_al_menu(self) -> None:
		"""Cierra la partida y todo lo que haya abierto, y deja el menú principal."""
		from app.reproductor.pantallas import principal

		self.cerrar_partida()
		self.config.guardar_pendiente()
		# Sin sala que avise, es aquí donde se ve lo que el Estudio haya cambiado en las preferencias compartidas.
		self.releer_configuracion()
		del self.pila[1:]
		if self.pila and isinstance(self.pila[0], Menu):
			self.pila[0].al_entrar()
		else:
			self.pila.clear()
			principal.abrir_menu_principal(self, saludar=False)

	def salir(self) -> None:
		"""Pide terminar el bucle."""
		self.activa = False

	# ── Supervisión ──────────────────────────────────────────────────────────

	def conectar_sala(self, host: str, puerto: int, codigo: str) -> None:
		"""Se conecta (en su hilo) a la sala del profesor; si ya había una conexión, la sustituye."""
		from app.reproductor.supervision import Enlace

		if self.enlace is not None:
			self.enlace.detener()
		recorrido = getattr(self.opciones, "modo", "") == "recorrido"
		self.enlace = Enlace(self, host, puerto, codigo, recorrido=recorrido)
		self.enlace.iniciar()

	def desconectar_sala(self) -> None:
		"""Deja la sala del profesor."""
		if self.enlace is not None:
			self.enlace.detener()
			self.enlace = None

	# ── Configuración en caliente ────────────────────────────────────────────

	def establecer(self, clave: str, valor: Any, diferido: bool = False) -> bool:
		"""Cambia una preferencia. False si no es válida.

		Las de juego del alumno van a su perfil (no a la configuración
		compartida, ver ``preferencia``) y se aplican al momento. Si la ficha
		del Estudio fijaba esa misma preferencia, desde ahora vale lo que ha
		elegido el alumno, hasta que llegue otra ficha.
		"""
		if self.perfil is not None and clave in ajustes.PREFERENCIAS_JUEGO:
			try:
				self.config.validar(clave, valor)
			except ErrorConfiguracion:
				log.warning("Valor no válido para %s.", clave, exc_info=True)
				return False
			anterior = self.preferencia(clave)
			self.perfil.poner_preferencia(clave, valor)
			self.perfil.olvidar_ajuste_de_ficha(ajustes.CAMPO_DE_CLAVE.get(clave, ""))
			nuevo = self.preferencia(clave)
			if nuevo != anterior:
				self._config_cambiada(clave, anterior, nuevo)
			return True
		try:
			if diferido:
				self.config.establecer_diferido(clave, valor)
			else:
				self.config.establecer(clave, valor)
		except ErrorConfiguracion:
			log.warning("Valor no válido para %s.", clave, exc_info=True)
			return False
		return True

	def _config_cambiada(self, clave: str, anterior: Any, nuevo: Any) -> None:
		"""Aplica al momento un cambio de la configuración compartida."""
		try:
			self._aplicar_cambio(clave, anterior, nuevo)
		except Exception:  # noqa: BLE001 - una preferencia que no se puede aplicar no debe romper el menú que la cambió
			log.exception("No se pudo aplicar el cambio de «%s»", clave)

	def _aplicar_cambio(self, clave: str, anterior: Any, nuevo: Any) -> None:
		seccion, _punto, nombre = clave.partition(".")
		if seccion == "sonido":
			if nombre.startswith("volumen_") and nombre[8:] in ajustes.BUSES:
				self.motor.volumen_bus(nombre[8:], float(nuevo))
			elif nombre == "motor":
				if not self._cambiando_motor:
					self.cambiar_motor(str(nuevo), str(anterior or ""))
			elif nombre == "perfil_hrtf":
				poner = getattr(self.motor, "poner_cabeza", None)
				if callable(poner):
					poner(str(nuevo or ""))
			elif nombre == "modo_salida":
				poner = getattr(self.motor, "poner_salida", None)
				if callable(poner):
					poner(str(nuevo))
			elif nombre == "dispositivo":
				self.motor.cambiar_dispositivo(str(nuevo or "") or None)
			elif nombre in ("proteccion_auditiva", "refuerzo_detras"):
				self.motor.configurar(ajustes.opciones_sonido(self.config, memoria=self.pruebas))
			elif nombre in ("seguimiento_cabeza", "seguimiento_cabeza_puerto"):
				if self.cabeza is not None:
					self.cabeza.parar()
					self.cabeza = None
				self._ajustar_cabeza()
		elif seccion == "voz":
			if nombre == "detalle":
				self._ajustes_cambiados()
			else:
				self.voz.configurar(ajustes.opciones_voz(self.config))
		elif seccion == "juego":
			if nombre not in ("alias", "ver_plano", "pantalla_negra", "posicion_menu"):
				self._ajustes_cambiados()
		elif seccion == "mando":
			if nombre == "mapa":
				return
			self.entrada.mandos.opciones = sanear_opciones({**self.entrada.mandos.opciones, **ajustes.opciones_mando(self.config)})
			self.haptica.configurar(ajustes.opciones_haptica(self.config))
		elif clave == "general.idioma":
			i18n.cambiar_idioma(str(nuevo or "auto"))
		elif clave == "general.tamano_texto":
			self._fuentes.clear()
			self._textos.clear()

	def _ajustes_cambiados(self) -> None:
		if self.partida is not None:
			self.partida.ajustes_cambiados()

	def cambiar_motor(self, nombre: str, anterior: str = "") -> bool:
		"""Cambia de motor de sonido sin cerrar el reproductor; si el nuevo no arranca, se vuelve al anterior.

		Se cierra el motor en uso antes de abrir el otro (dos motores no deben
		disputarse la tarjeta de sonido) y, si el nuevo falla, se vuelve a abrir
		el que había y se repone la preferencia.
		"""
		previo = anterior or str(getattr(self.motor, "pedido", self.motor.nombre))
		opciones = ajustes.opciones_sonido(self.config, memoria=self.pruebas)
		opciones["motor"] = nombre
		dispositivo = str(opciones.get("dispositivo") or "") or None
		self.presentador.detener_fuentes(0.0)
		try:
			self.motor.cerrar()
		except ErrorMotor, OSError:
			log.warning("El motor de sonido anterior no se cerró limpiamente.", exc_info=True)
		nuevo: MotorAudio | None = None
		motivo = ""
		try:
			clase = clase_motor(nombre)
			hay, motivo = clase.disponible()
			if hay:
				nuevo = clase()
				nuevo.pedido = nombre  # type: ignore[attr-defined]
				nuevo.resolver = self.banco.datos  # type: ignore[attr-defined]
				nuevo.iniciar(dispositivo, opciones)
		except (ErrorMotor, ImportError, OSError, KeyError) as error:
			log.warning("El motor de sonido %s no ha arrancado: %s", nombre, error)
			motivo = str(error)
			nuevo = None
		except Exception as error:  # noqa: BLE001 - una biblioteca de sonido puede fallar de cualquier forma: se vuelve al motor anterior
			log.exception("Fallo inesperado al arrancar el motor de sonido %s", nombre)
			motivo = str(error)
			nuevo = None
		conseguido = nuevo is not None
		if nuevo is None:
			opciones["motor"] = previo
			nuevo = crear_motor(opciones, self.banco)
			self._cambiando_motor = True
			try:
				if previo and previo != nombre:
					self.config.establecer("sonido.motor", previo)
			except ErrorConfiguracion:
				log.warning("No se pudo reponer el motor de sonido anterior en la configuración.", exc_info=True)
			finally:
				self._cambiando_motor = False
		self.motor = nuevo
		self.presentador.motor = nuevo
		if self.partida is not None:
			self.partida.motor_cambiado()
		if conseguido:
			log.info("Motor de sonido cambiado a %s.", nombre)
			self.decir(_("Motor de sonido: {nombre}.").format(nombre=nombre_motor(nuevo.nombre)), True)
		else:
			self.sonar("logro/error")
			self.decir(
				_("No se ha podido usar «{pedido}»: {motivo} Se sigue con «{actual}».").format(
					pedido=nombre_motor(nombre), motivo=(motivo.rstrip(".") + ".") if motivo else "", actual=nombre_motor(nuevo.nombre)
				),
				True,
				"aviso",
			)
		return conseguido

	# ── Fotograma ────────────────────────────────────────────────────────────

	def paso(self, dt: float, eventos: list[pygame.event.Event] | None = None) -> None:
		"""Un fotograma completo. Nunca lanza: un fallo se registra y el juego sigue."""
		dt = max(0.0, min(DT_MAXIMO, float(dt)))
		self._eventos = []
		self._sesion = None
		try:
			self._fotograma(dt, eventos or [])
			self._fallos_seguidos = 0
		except Exception:  # noqa: BLE001 - red de seguridad del bucle: el alumno no debe quedarse ante una ventana muerta
			log.exception("Fallo en un fotograma (pantalla %s); el reproductor sigue.", type(self.cima).__name__)
			self._fallo_en_fotograma()
		try:
			self.presentador.aplicar(self._eventos, self._sesion, dt)
		except Exception:  # noqa: BLE001 - igual: el sonido de un fotograma no vale el cierre del reproductor
			log.exception("Fallo al presentar el fotograma")
			self.fallos += 1

	def _fotograma(self, dt: float, eventos: list[pygame.event.Event]) -> None:
		for evento in eventos:
			self._evento(evento)
		for accion, pulsada in self.entrada.actualizar(dt, self.contexto):
			self._accion(accion, pulsada)
		for frase in self.entrada.avisos():
			self.decir(frase, False, "aviso")
		if self.enlace is not None:
			self.enlace.atender(dt)
		partida = self.partida
		if partida is not None:
			partida.fotograma(dt, self.cima is partida)
		cima = self.cima
		if cima is not None:
			cima.actualizar(dt)

	def _fallo_en_fotograma(self) -> None:
		self.fallos += 1
		self._fallos_seguidos += 1
		ahora = time.monotonic()
		if ahora - self._t_aviso_fallo >= ESPERA_AVISO_FALLO:
			self._t_aviso_fallo = ahora
			try:
				self.decir(_("Ha habido un problema, pero puedes seguir."), False, "aviso")
			except Exception:  # noqa: BLE001 - si ni la voz funciona, queda el registro
				log.exception("No se pudo avisar del fallo")
		if self._fallos_seguidos >= FALLOS_SEGUIDOS_MAXIMOS:
			self._fallos_seguidos = 0
			log.error("Demasiados fallos seguidos: se vuelve al menú principal.")
			try:
				self.volver_al_menu()
			except Exception:  # noqa: BLE001 - último recurso: dejar solo el menú principal
				log.exception("No se pudo volver al menú principal tras los fallos")

	def _evento(self, evento: pygame.event.Event) -> None:
		tipo = evento.type
		if tipo == pygame.QUIT:
			self.salir()
			return
		if tipo == pygame.WINDOWFOCUSLOST:
			self.con_foco = False
			cima = self.cima
			if cima is not None:
				cima.al_perder_foco()
		elif tipo == pygame.WINDOWFOCUSGAINED:
			self.con_foco = True
		if tipo == pygame.KEYDOWN and es_tecla_restablecer_voz(evento):
			from app.reproductor.pantallas.opciones import restablecer_voz

			restablecer_voz(self)  # atajo: Ctrl+F12 (volver a la voz automática desde cualquier pantalla)
			return
		cima = self.cima
		if cima is not None and tipo in _EVENTOS_CRUDOS and cima.tecla(evento):
			return
		for accion, pulsada in self.entrada.traducir(evento, self.contexto):
			self._accion(accion, pulsada)

	def _accion(self, accion: str, pulsada: bool) -> None:
		"""Reparte una acción: primero la pantalla de arriba y, si no la quiere, las comunes a todas."""
		cima = self.cima
		if cima is not None and cima.accion(accion, pulsada):
			return
		if not pulsada:
			return
		if accion == "repetir":  # atajo: F2 (repetir el último mensaje)
			self.motor.atenuar_por_voz(self.voz.repetir())
		elif accion == "historial_anterior":  # atajo: F3 (mensaje anterior del historial)
			self.motor.atenuar_por_voz(self.voz.anterior())
		elif accion == "historial_siguiente":  # atajo: Mayús+F3 (mensaje siguiente del historial)
			self.motor.atenuar_por_voz(self.voz.siguiente())
		elif accion == "callar":
			self.callar()
		elif accion == "ayuda":  # atajo: F1 (ayuda de la pantalla o de la opción)
			self.mostrar_ayuda()

	def mostrar_ayuda(self) -> None:
		"""Dice la ayuda de la pantalla de arriba o, si no tiene, abre la lista de teclas y botones del contexto."""
		from app.reproductor.pantallas import ayuda

		cima = self.cima
		texto = cima.texto_ayuda() if cima is not None else ""
		if texto:
			self.decir_menu(texto)
		else:
			ayuda.abrir_ayuda(self, self.contexto)

	# ── Pruebas: manejar la aplicación sin teclado ni reloj ──────────────────

	def inyectar(self, accion: str, mantener: bool = False) -> None:
		"""Simula una acción (pulsar y soltar; con ``mantener``, solo pulsar)."""
		self._accion(accion, True)
		if not mantener:
			self._accion(accion, False)

	def soltar(self, accion: str) -> None:
		"""Suelta una acción que se inyectó con ``mantener``."""
		self._accion(accion, False)

	def tecla(self, codigo: int, mod: int = 0, unicode: str = "", soltar: bool = True) -> None:
		"""Simula una tecla por el mismo camino que una real (pantalla, mapa de teclado y acciones)."""
		self._evento(pygame.event.Event(pygame.KEYDOWN, key=codigo, mod=mod, unicode=unicode))
		if soltar:
			self._evento(pygame.event.Event(pygame.KEYUP, key=codigo, mod=mod))

	def evento(self, evento: pygame.event.Event) -> None:
		"""Entrega un evento de pygame cualquiera (mando simulado, foco)."""
		self._evento(evento)

	def avanzar(self, fotogramas: int = 1, dt: float = 1.0 / FOTOGRAMAS) -> None:
		"""Deja pasar fotogramas sin leer la cola de eventos de pygame."""
		for _i in range(max(0, int(fotogramas))):
			self.paso(dt, [])
			if not self.activa:
				break

	# ── Dibujo ───────────────────────────────────────────────────────────────

	@property
	def paleta(self) -> tuple[tuple[int, int, int], ...]:
		"""Colores en uso: los normales o los de alto contraste."""
		return PALETA_CONTRASTE if self.config.obtener("general.alto_contraste", False) else PALETA_NORMAL

	def fuente(self, tamano: int) -> pygame.font.Font:
		"""Una fuente del tamaño pedido, escalada con la preferencia de tamaño de texto."""
		escala = max(75, min(300, int(self.config.obtener("general.tamano_texto", 100) or 100))) / 100.0
		puntos = max(10, round(tamano * escala))
		fuente = self._fuentes.get(puntos)
		if fuente is None:
			try:
				fuente = pygame.font.SysFont("segoeui,arial", puntos)
			except pygame.error, OSError:
				fuente = pygame.font.Font(None, puntos)
			self._fuentes[puntos] = fuente
		return fuente

	def texto(self, texto: str, tamano: int, color: tuple[int, int, int]) -> pygame.Surface:
		"""Un texto ya dibujado (se guarda: los menús repiten las mismas líneas fotograma tras fotograma)."""
		clave = (texto, tamano, color)
		superficie = self._textos.get(clave)
		if superficie is None:
			if len(self._textos) > 400:
				self._textos.clear()
			superficie = self.fuente(tamano).render(texto, True, color)
			self._textos[clave] = superficie
		return superficie

	def partir(self, texto: str, tamano: int, ancho: int) -> list[str]:
		"""Parte un texto en líneas que caben en ``ancho`` píxeles."""
		fuente = self.fuente(tamano)
		lineas: list[str] = []
		actual = ""
		for palabra in texto.split():
			prueba = f"{actual} {palabra}".strip()
			if actual and fuente.size(prueba)[0] > ancho:
				lineas.append(actual)
				actual = palabra
			else:
				actual = prueba
		if actual:
			lineas.append(actual)
		return lineas

	def dibujar(self) -> None:
		"""Dibuja la pantalla de arriba. Con «pantalla en negro» no se dibuja nada."""
		fondo, color, destacado, tenue = self.paleta
		lienzo = self.lienzo
		if self.config.obtener("juego.pantalla_negra", False):
			lienzo.fill((0, 0, 0))
			pygame.display.flip()
			return
		lienzo.fill(fondo)
		cima = self.cima
		if cima is None or not cima.dibujar(lienzo):
			self._dibujar_lineas(cima)
		self._dibujar_ultimo_mensaje(color, tenue)
		pygame.display.flip()

	def _dibujar_lineas(self, cima: Pantalla | None) -> None:
		_fondo, color, destacado, _tenue = self.paleta
		margen = 24
		y = 16
		titulo = cima.titulo_visible() if cima is not None else NOMBRE_APLICACION
		for linea in self.partir(titulo or NOMBRE_APLICACION, 34, ANCHO - 2 * margen)[:2]:
			self.lienzo.blit(self.texto(linea, 34, destacado), (margen, y))
			y += self.fuente(34).get_linesize()
		y += 8
		lineas, indice = cima.lineas() if cima is not None else ([], -1)
		alto = self.fuente(24).get_linesize()
		caben = max(1, (ALTO - y - 110) // alto)
		primera = max(0, min(max(0, indice) - caben // 2, max(0, len(lineas) - caben)))
		for numero in range(primera, min(len(lineas), primera + caben)):
			elegida = numero == indice
			# La opción elegida se marca con un signo además del color.
			texto = ("► " if elegida else "   ") + lineas[numero]
			recortado = self.partir(texto, 24, ANCHO - 2 * margen)
			self.lienzo.blit(self.texto(recortado[0] if recortado else "", 24, destacado if elegida else color), (margen, y))
			y += alto

	def _dibujar_ultimo_mensaje(self, color: tuple[int, int, int], tenue: tuple[int, int, int]) -> None:
		"""Lo último que ha dicho la voz, abajo: texto como alternativa para quien oye poco o acompaña."""
		ultimo = str(getattr(self.voz, "ultimo", "") or "")
		if not ultimo:
			return
		lineas = self.partir(ultimo, 20, ANCHO - 48)[-3:]
		alto = self.fuente(20).get_linesize()
		y = ALTO - 12 - alto * len(lineas)
		pygame.draw.line(self.lienzo, tenue, (24, y - 6), (ANCHO - 24, y - 6), 1)
		for linea in lineas:
			self.lienzo.blit(self.texto(linea, 20, color), (24, y))
			y += alto

	# ── Bucle y cierre ───────────────────────────────────────────────────────

	def bucle(self, fotogramas: int | None = None) -> int:
		"""El bucle principal. ``fotogramas`` lo limita (comprobación de arranque). Devuelve el código de salida."""
		hechos = 0
		try:
			while self.activa:
				dt = self.reloj.tick(FOTOGRAMAS) / 1000.0
				self.paso(dt, pygame.event.get())
				try:
					self.dibujar()
				except Exception:  # noqa: BLE001 - un fallo al dibujar no debe cerrar un juego que se maneja de oído
					log.exception("Fallo al dibujar la pantalla")
					self.fallos += 1
				hechos += 1
				if fotogramas is not None and hechos >= fotogramas:
					break
		finally:
			self.cerrar_todo()
		return self.codigo_salida

	def cerrar_todo(self) -> None:
		"""Cierre ordenado: graba la sesión, se despide de la sala, guarda y suelta sonido, voz, mandos y ventana."""
		if getattr(self, "_cerrada", False):
			return
		self._cerrada = True
		self.activa = False
		pasos = (
			("la partida", self.cerrar_partida),
			("la supervisión", self.desconectar_sala),
			("la configuración", self.config.guardar_pendiente),
			("la suscripción a la configuración", lambda: self._cancelar_config and self._cancelar_config()),
			("los paquetes de sonido", lambda: self._cancelar_paquetes and self._cancelar_paquetes()),
			("el presentador", self.presentador.cerrar),
			("el motor de sonido", self.motor.cerrar),
			("el seguimiento de cabeza", lambda: self.cabeza and self.cabeza.parar()),
			("la voz", self.voz.cerrar),
			("los mandos", self.entrada.cerrar),
		)
		for nombre, funcion in pasos:
			try:
				funcion()
			except Exception:  # noqa: BLE001 - cada paso del cierre se intenta aunque falle el anterior
				log.exception("Fallo al cerrar %s", nombre)
		if not self.pruebas:
			pygame.quit()
		log.info("Reproductor cerrado (%d fallos de fotograma).", self.fallos)
