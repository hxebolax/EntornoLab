"""Carga anunciada de los entornos grandes: en segundo plano, con el estado dicho en voz alta y Escape para cancelar.

Por qué existe: preparar una partida en un barrio importado de OpenStreetMap
(miles de espacios) lleva segundos: indexar paredes, puertas y objetos, crear
la actividad (que a veces mide caminos), el grafo de espacios, los caminos
alrededor del inicio y el sonido. Hecho en el bucle de pygame, la ventana
dejaba de responder («No responde»), el lector de pantalla se bloqueaba al
leerla y el alumno no sabía si el programa seguía vivo.

Cómo se hace:

- La parte pesada (``PantallaJuego.preparar``) va en un hilo aparte. Lo que
  solo se puede leer en el hilo principal (ajustes, perfil, catálogo) se lee
  antes (``PantallaJuego.pedido``) y lo que toca la aplicación se hace
  después, otra vez en el hilo principal (``PantallaJuego.instalar``).
- Mientras tanto, ``PantallaCarga`` está arriba de la pila: el bucle sigue
  atendiendo eventos, el sonido sigue vivo y se dibuja «Cargando…».
- La voz va por hitos, sin saturar (reglas del agente de accesibilidad):
  al empezar se dice qué se carga y cuánto («Cargando el entorno Barrio:
  3.000 espacios»); después, solo cada cambio de fase («Preparando los
  caminos…», «Preparando el sonido…») y, si una fase se alarga, un
  recordatorio cada ``RECORDATORIO`` segundos. Nada interrumpe salvo la
  respuesta a lo que pide el alumno: Intro o F1 dicen el estado, Escape
  cancela.
- Cancelar no deja nada a medias: el hilo comprueba la petición en cada
  aviso de progreso, lanza ``CargaCancelada`` y su trabajo se descarta.
- Con un entorno pequeño todo esto sobra: se prepara al momento, como siempre
  (``es_grande``).
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from collections.abc import Callable
from typing import TYPE_CHECKING, Any

from app.core.i18n import _, _n, separador_decimal
from app.dominio.modelo import Entorno
from app.reproductor.menus import SONIDO_BORDE, Pantalla

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)

# A partir de cuántos elementos (espacios, aberturas y objetos) se carga en segundo plano con aviso.
# Con este tamaño la preparación ya pasa de unas décimas de segundo en un equipo normal.
UMBRAL_ELEMENTOS = 1000
# Segundos sin cambio de fase tras los que se recuerda que se sigue cargando.
RECORDATORIO = 8.0
# Intervalo de cambio del GIL mientras carga: así el hilo del bucle (y con él el lector de pantalla) responde enseguida.
INTERVALO_GIL_CARGA = 0.001

# Fases que avisa el motor (``Sesion``, ``Mundo``) agrupadas en lo que se le dice al alumno.
_GRUPO_DE_FASE = {
	"actividad": "actividad",
	"plantas": "plano",
	"paredes": "plano",
	"aberturas": "plano",
	"objetos": "plano",
	"caminos": "caminos",
	"sonido": "sonido",
}


class CargaCancelada(Exception):
	"""El alumno ha pedido cancelar la carga: la preparación se interrumpe en el siguiente aviso de progreso."""


def contar(entorno: Entorno) -> tuple[int, int]:
	"""(espacios, elementos que cuestan al preparar: espacios, aberturas y objetos) de un entorno."""
	espacios = sum(len(planta.espacios) for planta in entorno.plantas)
	elementos = espacios + sum(len(planta.aberturas) + len(planta.objetos) for planta in entorno.plantas)
	return espacios, elementos


def es_grande(entorno: Entorno) -> bool:
	"""Si preparar una partida en este entorno lleva tiempo suficiente como para cargarlo con aviso."""
	return contar(entorno)[1] >= UMBRAL_ELEMENTOS


def miles(numero: int) -> str:
	"""Un número con separador de miles del idioma («3.000» en español): así se lee y se ve bien en braille."""
	texto = f"{int(numero):,}"
	return texto.replace(",", "." if separador_decimal() == "," else ",")


class Progreso:
	"""Cómo va una preparación: lo escribe el hilo que trabaja y lo lee el bucle. Seguro entre hilos.

	Se llama como una función, ``progreso(fase, hechos, total)``, que es lo que
	esperan ``Sesion`` y ``Mundo``. Si se ha pedido cancelar, la llamada lanza
	``CargaCancelada``.
	"""

	def __init__(self) -> None:
		self._cerrojo = threading.Lock()
		self._cancelar = threading.Event()
		self._fase = ""
		self._hechos = 0
		self._total = 0

	def __call__(self, fase: str, hechos: int = 0, total: int = 0) -> None:
		if self._cancelar.is_set():
			raise CargaCancelada
		with self._cerrojo:
			self._fase = str(fase)
			self._hechos = int(hechos)
			self._total = int(total)

	def leer(self) -> tuple[str, int, int]:
		"""(fase, hechos, total) del último aviso."""
		with self._cerrojo:
			return self._fase, self._hechos, self._total

	def cancelar(self) -> None:
		"""Pide al hilo que pare en el siguiente aviso."""
		self._cancelar.set()

	@property
	def cancelado(self) -> bool:
		"""Si se ha pedido cancelar."""
		return self._cancelar.is_set()


def texto_fase(grupo: str) -> str:
	"""Lo que se dice al empezar cada fase."""
	textos = {
		"actividad": _("Preparando la actividad…"),
		"plano": _("Preparando el plano: paredes, puertas y objetos…"),
		"caminos": _("Preparando los caminos…"),
		"sonido": _("Preparando el sonido…"),
	}
	return textos.get(grupo, _("Cargando…"))


class PantallaCarga(Pantalla):
	"""«Cargando…»: hace un trabajo en un hilo aparte y avisa por hitos mientras el bucle sigue vivo.

	``trabajo(progreso)`` se ejecuta en el hilo y devuelve el resultado;
	``al_terminar(resultado)`` se llama después en el hilo principal, ya
	quitada esta pantalla de la pila. Si el trabajo falla, se dice
	``mensaje_de_error(error)`` (o una frase general) y se vuelve a la
	pantalla de antes; ``al_cancelar()`` se llama si el alumno cancela.
	"""

	def __init__(
		self,
		app: Aplicacion,
		nombre: str,
		espacios: int,
		trabajo: Callable[[Progreso], Any],
		al_terminar: Callable[[Any], None],
		al_cancelar: Callable[[], None] | None = None,
		mensaje_de_error: Callable[[BaseException], str] | None = None,
	) -> None:
		super().__init__(app)
		self.nombre = nombre
		self.espacios = espacios
		self.trabajo = trabajo
		self.al_terminar = al_terminar
		self.al_cancelar = al_cancelar
		self.mensaje_de_error = mensaje_de_error
		self.mensaje_error = ""
		self.progreso = Progreso()
		self._hilo: threading.Thread | None = None
		self._resultado: Any = None
		self._error: BaseException | None = None
		self._terminado = threading.Event()
		self._grupo_dicho = ""
		self._t_inicio = 0.0
		self._t_ultimo_aviso = 0.0
		self._acabada = False
		self._intervalo_previo: float | None = None

	# ── El hilo ──

	def _trabajar(self) -> None:
		"""Cuerpo del hilo: hace el trabajo y deja el resultado o el error para el bucle."""
		try:
			self._resultado = self.trabajo(self.progreso)
		except CargaCancelada:
			log.info("Carga de «%s» cancelada por el alumno", self.nombre)
		except Exception as error:  # noqa: BLE001 - cualquier fallo del trabajo se le dice al alumno y se vuelve al menú; nunca se cuelga
			log.exception("Fallo al preparar «%s» en segundo plano", self.nombre)
			self._error = error
		finally:
			self._terminado.set()

	def empezar(self) -> None:
		"""Arranca el hilo (una sola vez)."""
		if self._hilo is not None:
			return
		self._t_inicio = time.monotonic()
		self._t_ultimo_aviso = self._t_inicio
		self._intervalo_previo = sys.getswitchinterval()
		sys.setswitchinterval(INTERVALO_GIL_CARGA)
		self._hilo = threading.Thread(target=self._trabajar, name=f"carga-{self.nombre}", daemon=True)
		self._hilo.start()

	@property
	def terminada(self) -> bool:
		"""Si el hilo ha acabado (bien, mal o cancelado)."""
		return self._terminado.is_set()

	def esperar(self, segundos: float) -> bool:
		"""Espera a que el hilo acabe, como mucho ``segundos``. Para las pruebas; el bucle nunca espera."""
		return self._terminado.wait(segundos)

	# ── Voz ──

	def texto_inicio(self) -> str:
		"""La primera frase: qué se carga, cuánto y cómo cancelar."""
		cuantos = _n("{n} espacio", "{n} espacios", self.espacios).format(n=miles(self.espacios))
		return _("Cargando el entorno {nombre}: {espacios}. Puede tardar unos segundos; Escape cancela.").format(
			nombre=self.nombre, espacios=cuantos
		)

	def texto_estado(self) -> str:
		"""Dónde va la carga ahora mismo, con cifras si las hay (lo que se dice al pedirlo y en los recordatorios)."""
		fase, hechos, total = self.progreso.leer()
		grupo = _GRUPO_DE_FASE.get(fase, "")
		texto = texto_fase(grupo).rstrip("…").rstrip(".")
		if grupo == "plano" and total > 0 and fase in ("aberturas", "objetos"):
			if fase == "aberturas":
				texto += ", " + _("puertas y pasos: {hechos} de {total}").format(hechos=miles(hechos), total=miles(total))
			else:
				texto += ", " + _("objetos: {hechos} de {total}").format(hechos=miles(hechos), total=miles(total))
		segundos = max(0, round(time.monotonic() - self._t_inicio)) if self._t_inicio else 0
		return _("Sigue cargando el entorno {nombre}: {fase}. Lleva {segundos}.").format(
			nombre=self.nombre,
			fase=texto[:1].lower() + texto[1:],
			segundos=_n("{n} segundo", "{n} segundos", segundos).format(n=segundos),
		)

	def _avisar(self, texto: str, interrumpir: bool = False) -> None:
		self.app.decir(texto, interrumpir, "aviso")
		self._t_ultimo_aviso = time.monotonic()

	# ── Pantalla ──

	def al_entrar(self) -> None:
		"""La primera vez arranca la carga y dice qué se carga; al volver a quedar arriba, dice cómo va."""
		if self._hilo is None:
			self.empezar()
			self._avisar(self.texto_inicio(), True)
		elif not self._acabada:
			self._avisar(self.texto_estado(), True)

	def al_salir(self) -> None:
		"""Si la pantalla sale sin haber acabado (el alumno vuelve al menú), el hilo se cancela."""
		if not self.terminada:
			self.progreso.cancelar()
		self._restaurar_gil()

	def _restaurar_gil(self) -> None:
		if self._intervalo_previo is not None:
			sys.setswitchinterval(self._intervalo_previo)
			self._intervalo_previo = None

	def actualizar(self, dt: float) -> None:
		"""Cada fotograma: mira cómo va el hilo, avisa por hitos y, al acabar, sigue adelante."""
		if self._acabada:
			return
		if self.terminada:
			self._acabar()
			return
		if self.progreso.cancelado:
			return
		fase, _hechos, _total = self.progreso.leer()
		grupo = _GRUPO_DE_FASE.get(fase, "")
		ahora = time.monotonic()
		if grupo and grupo != self._grupo_dicho:
			# El plano es lo primero y ya lo cuenta la frase de inicio: solo se dice si ha pasado un rato.
			if grupo != "plano" or ahora - self._t_inicio >= RECORDATORIO / 2:
				self._avisar(texto_fase(grupo))
			self._grupo_dicho = grupo
		elif ahora - self._t_ultimo_aviso >= RECORDATORIO:
			self._avisar(self.texto_estado())

	def _acabar(self) -> None:
		"""El hilo ha acabado: se quita la pantalla y se sigue con el resultado, el error o la cancelación."""
		self._acabada = True
		self._restaurar_gil()
		if self.progreso.cancelado:
			self.app.cerrar(self)
			return
		if self._error is not None:
			error = self._error
			if self.mensaje_de_error is not None:
				self.mensaje_error = self.mensaje_de_error(error)
			else:
				self.mensaje_error = _("No se ha podido preparar el entorno {nombre}: {detalle}").format(
					nombre=self.nombre, detalle=str(error) or type(error).__name__
				)
			# Primero vuelve a hablar la pantalla de antes y después el motivo, que es lo que tiene que oírse al final.
			self.app.cerrar(self)
			self.app.sonar("logro/error")
			self.app.decir(self.mensaje_error, True, "aviso")
			return
		duracion = time.monotonic() - self._t_inicio
		log.info("Entorno «%s» preparado en %.1f s", self.nombre, duracion)
		# Sin pasar por ``cerrar``: la pantalla de debajo no tiene que volver a hablar, ahora empieza la partida.
		if self in self.app.pila:
			self.app.pila.remove(self)
		self.al_salir()
		self.al_terminar(self._resultado)

	def cancelar(self) -> None:
		"""Escape: para la carga y vuelve a donde estaba."""
		if self._acabada:
			return
		self._acabada = True
		self.progreso.cancelar()
		self._restaurar_gil()
		self.app.cerrar(self)
		self.app.decir(_("Carga cancelada."), True, "aviso")
		if self.al_cancelar is not None:
			self.al_cancelar()

	def accion(self, accion: str, pulsada: bool) -> bool:
		"""Escape cancela; Intro y la ayuda dicen cómo va. Lo demás de los menús no hace nada mientras carga."""
		if not pulsada:
			return accion.startswith("menu_")
		if accion == "menu_atras":
			self.cancelar()
		elif accion in ("menu_aceptar", "ayuda"):
			self._avisar(self.texto_estado() + " " + _("Escape cancela."), True)
		elif accion.startswith("menu_"):
			self.app.sonar(SONIDO_BORDE)
		else:
			return False
		return True

	def texto_ayuda(self) -> str:
		"""La ayuda es el estado: mientras carga no hay nada más que hacer."""
		return self.texto_estado() + " " + _("Escape cancela.")

	def titulo_visible(self) -> str:
		"""«Cargando…» y el nombre del entorno."""
		return _("Cargando {nombre}…").format(nombre=self.nombre)

	def lineas(self) -> tuple[list[str], int]:
		"""El estado y cómo cancelar, para quien mira la pantalla."""
		return [self.texto_estado(), _("Escape: cancelar.")], -1


def abrir_partida(
	app: Aplicacion,
	paquete: Any,
	datos_actividad: dict[str, Any] | None,
	recorrido: bool = False,
	tutorial: bool = False,
	actividad: Any = None,
) -> PantallaCarga:
	"""Empieza una partida en un entorno grande: abre la pantalla de carga y, al acabar, la partida.

	Si la actividad no se puede crear, se dice por qué (igual que sin carga) y
	se queda en el menú desde el que se pidió.
	"""
	from app.reproductor import puente_actividades
	from app.reproductor.pantallas.juego import PantallaJuego

	partida = PantallaJuego(app, paquete, datos_actividad, recorrido=recorrido, tutorial=tutorial, actividad=actividad, diferir=True)
	pedido = partida.pedido()
	espacios, _elementos = contar(paquete.entorno)
	nombre = paquete.entorno.nombre or _("sin nombre")

	def trabajo(progreso: Progreso) -> Any:
		return partida.preparar(pedido, progreso)

	def al_terminar(preparada: Any) -> None:
		partida.instalar(preparada)
		app.instalar_partida(partida)

	def mensaje(error: BaseException) -> str:
		# Una actividad que no se puede crear ya trae su frase para el alumno, como cuando se prepara sin carga.
		if isinstance(error, puente_actividades.ErrorActividad):
			return str(error)
		return _("No se ha podido preparar el entorno {nombre}: {detalle}").format(
			nombre=nombre, detalle=str(error) or type(error).__name__
		)

	carga = PantallaCarga(app, nombre, espacios, trabajo, al_terminar, mensaje_de_error=mensaje)
	app.abrir(carga)
	return carga


def recrear_sesion(app: Aplicacion, partida: Any, pedido: Any, instalar: Callable[[Any], None]) -> None:
	"""Vuelve a preparar la sesión de una partida (reiniciar, entorno actualizado): con carga anunciada si es grande.

	``pedido`` es el de ``PantallaJuego.pedido`` (con el entorno que toca) e
	``instalar(preparada)`` pone en marcha la nueva sesión. Mientras carga, la
	partida anterior queda debajo, en pausa (hay otra pantalla encima); si el
	alumno cancela, sigue la partida que había.
	"""
	if not es_grande(pedido.entorno):
		instalar(partida.preparar(pedido))
		return
	espacios, _elementos = contar(pedido.entorno)

	def trabajo(progreso: Progreso) -> Any:
		return partida.preparar(pedido, progreso)

	app.abrir(PantallaCarga(app, pedido.entorno.nombre or _("sin nombre"), espacios, trabajo, instalar))
