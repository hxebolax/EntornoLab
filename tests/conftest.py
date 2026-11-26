"""Preparación común de las pruebas de EntornoLab.

Qué garantiza:

- **Nunca se toca el ``data/`` real.** ``APP_DATA_DIR`` apunta a una carpeta
  temporal ANTES de que las pruebas importen la aplicación y, además, cada
  prueba recibe su propia carpeta (``data_temporal``; ``datos_temporales`` es
  el nombre que usaban las pruebas del esqueleto y devuelve la misma). Al
  final se avisa si el ``data/`` real cambió.
- **Sin red por defecto.** Cualquier conexión a un equipo no local falla con
  un mensaje claro, salvo en las pruebas marcadas ``@pytest.mark.red``. Las
  conexiones a ``127.0.0.1`` (la sala de supervisión) sí se permiten.
- **Sin ventanas ni sonido.** Una única ``wx.App`` para toda la sesión, con
  el proveedor de ayuda y el idioma español como en ``main.py``; los marcos
  se crean sin mostrar. pygame usa los controladores «dummy» de SDL: no abre
  ventana ni dispositivo de sonido.
- **Sin voz.** Con un lector de pantalla abierto, las pruebas no deben
  ponerse a hablar: ``app.core.voz.hablar`` se sustituye siempre, y la
  fixture ``voz_simulada`` permite además comprobar lo que se habría dicho.
- **Siempre en español.** ``APP_IDIOMA=es``: el resultado no depende del
  idioma de Windows de quien ejecuta las pruebas.
- **Diálogos modales simulados** (``dialogo_modal``); uno real sin simular
  hace fallar la prueba al momento en vez de colgar la sesión.

Marcadores: ``lento``, ``red`` e ``interfaz`` (declarados en ``pyproject.toml``).
Por defecto no se ejecutan ``red`` ni ``interfaz``.

Procede de la plantilla del agente «pruebas», integrada con el conftest del
esqueleto.
"""

from __future__ import annotations

import importlib
import logging
import os
import shutil
import socket
import sys
import tempfile
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from pathlib import Path
from types import ModuleType

import pytest

log = logging.getLogger(__name__)

# La raíz del proyecto en el path: así ``import app`` funciona aunque pytest
# se lance desde otra carpeta o sin ``pythonpath`` en la configuración.
RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
	sys.path.insert(0, str(RAIZ))


# ════════════════════════════════════════════════════════════════════════════
# Configuración del proyecto
# ════════════════════════════════════════════════════════════════════════════

# Variable de entorno que app.core.paths usa para redirigir data/.
VARIABLE_DATA = "APP_DATA_DIR"

# Si True, TODAS las pruebas reciben su propia carpeta data vacía.
AISLAR_DATA_SIEMPRE = True

# Atributos de módulo que guardan la ruta de data calculada al importar.
# app.core.paths la calcula en cada llamada, así que no hay ninguno.
ATRIBUTOS_RUTA_DATA: list[tuple[str, str]] = []

# Si True, las pruebas sin @pytest.mark.red no pueden salir a Internet.
BLOQUEAR_RED_SIEMPRE = True

# Funciones de voz que se sustituyen en la fixture voz_simulada, como
# «paquete.modulo.funcion». Se parchea donde se USA la función.
FUNCIONES_VOZ: list[str] = ["app.core.voz.hablar"]

MARCADORES = {
	"lento": "prueba lenta (más de un segundo); se excluye con -m 'not lento'",
	"red": "necesita Internet; no se ejecuta por defecto (usa -m red)",
	"interfaz": "muestra ventanas o envía teclas reales; no se ejecuta por defecto (usa -m interfaz)",
}

HOSTS_LOCALES = {"localhost", "127.0.0.1", "::1", "0.0.0.0", ""}

# Variables de entorno fijadas para toda la sesión, también para los procesos
# que lancen las pruebas (main.py y jugar.py en otro proceso).
ENTORNO_DE_PRUEBAS = {
	# pygame/SDL sin ventana ni dispositivo de sonido reales.
	"SDL_VIDEODRIVER": "dummy",
	"SDL_AUDIODRIVER": "dummy",
	# Sin el saludo de pygame en la salida de cada proceso.
	"PYGAME_HIDE_SUPPORT_PROMPT": "1",
	# El idioma no depende del Windows de quien ejecuta las pruebas.
	"APP_IDIOMA": "es",
}


# ════════════════════════════════════════════════════════════════════════════
# Entorno de la sesión (antes de importar la aplicación)
# ════════════════════════════════════════════════════════════════════════════

# Se fija al importar conftest, que pytest carga antes que los módulos de
# prueba: así ni siquiera una importación que calcule rutas ve el data real,
# y pygame encuentra los controladores «dummy» en cuanto alguien lo importe.
_DATA_SESION = Path(tempfile.mkdtemp(prefix="pruebas_data_"))
os.environ[VARIABLE_DATA] = str(_DATA_SESION)
os.environ.update(ENTORNO_DE_PRUEBAS)
os.environ.pop("APP_DEPURACION", None)


def _instantanea(carpeta: Path, limite: int = 20000) -> dict[str, tuple[int, int]]:
	"""Tamaño y fecha de cada archivo de ``carpeta`` (para detectar cambios)."""
	datos: dict[str, tuple[int, int]] = {}
	if not carpeta.is_dir():
		return datos
	for numero, archivo in enumerate(carpeta.rglob("*")):
		if numero >= limite:
			break
		try:
			if archivo.is_file():
				estado = archivo.stat()
				datos[str(archivo.relative_to(carpeta))] = (estado.st_size, estado.st_mtime_ns)
		except OSError:
			log.debug("No se pudo leer %s", archivo, exc_info=True)
	return datos


def pytest_configure(config: pytest.Config) -> None:
	"""Registra los marcadores y toma una instantánea del data real."""
	for nombre, descripcion in MARCADORES.items():
		config.addinivalue_line("markers", f"{nombre}: {descripcion}")
	config._instantanea_data_real = _instantanea(RAIZ / "data")  # type: ignore[attr-defined]


def pytest_terminal_summary(terminalreporter, exitstatus, config) -> None:
	"""Avisa si el data real cambió durante las pruebas (fuga de aislamiento).

	Es un aviso y no un fallo: si la aplicación estaba abierta a la vez, o
	alguien estaba generando recursos en ``data/``, también cambia.
	"""
	antes = getattr(config, "_instantanea_data_real", {})
	despues = _instantanea(RAIZ / "data")
	cambios = sorted(set(antes.items()) ^ set(despues.items()))
	if cambios:
		nombres = sorted({nombre for nombre, _estado in cambios})
		terminalreporter.write_line(
			f"AVISO: el data real cambió durante las pruebas ({len(nombres)} archivos), "
			f"por ejemplo: {', '.join(nombres[:5])}. Revisa el aislamiento.",
			yellow=True,
		)


def pytest_unconfigure(config: pytest.Config) -> None:
	"""Borra la carpeta data de la sesión."""
	shutil.rmtree(_DATA_SESION, ignore_errors=True)


# ════════════════════════════════════════════════════════════════════════════
# data temporal por prueba
# ════════════════════════════════════════════════════════════════════════════


def redirigir_data(carpeta: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	"""Hace que la aplicación use ``carpeta`` como data mientras dure la prueba.

	Redirige ``APP_DATA_DIR`` y los atributos de ``ATRIBUTOS_RUTA_DATA`` (rutas
	que algún módulo calculó al importarse).
	"""
	monkeypatch.setenv(VARIABLE_DATA, str(carpeta))
	for modulo, atributo in ATRIBUTOS_RUTA_DATA:
		objeto = importlib.import_module(modulo)
		valor = str(carpeta) if isinstance(getattr(objeto, atributo), str) else carpeta
		monkeypatch.setattr(objeto, atributo, valor)
	return carpeta


@pytest.fixture
def data_temporal(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
	"""Carpeta data vacía y exclusiva de esta prueba."""
	carpeta = tmp_path / "data"
	carpeta.mkdir(exist_ok=True)
	return redirigir_data(carpeta, monkeypatch)


@pytest.fixture
def datos_temporales(data_temporal: Path) -> Path:
	"""La misma carpeta que ``data_temporal`` (nombre que usaban las pruebas del esqueleto)."""
	return data_temporal


@pytest.fixture(autouse=True)
def _aislar_data(request: pytest.FixtureRequest) -> None:
	"""Aplica ``data_temporal`` a todas las pruebas si ``AISLAR_DATA_SIEMPRE``."""
	if AISLAR_DATA_SIEMPRE:
		request.getfixturevalue("data_temporal")


@pytest.fixture(autouse=True)
def _entorno_limpio(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
	"""Deja cada prueba sin voz, sin modo depuración, en español y sin estado compartido.

	- La voz se silencia siempre (no solo con ``voz_simulada``).
	- ``APP_DEPURACION`` cambiaría el nivel del registro y copiaría mensajes a la consola.
	- Al terminar se devuelve el idioma al español y se olvida la configuración
	  compartida: lo que una prueba cambie no debe verlo la siguiente.
	"""
	monkeypatch.delenv("APP_DEPURACION", raising=False)
	for nombre, valor in ENTORNO_DE_PRUEBAS.items():
		monkeypatch.setenv(nombre, valor)
	from app.core import voz

	monkeypatch.setattr(voz, "hablar", lambda texto, interrumpir=False, esperar=0.0: False)
	yield
	from app.core import configuracion, i18n

	configuracion.establecer_configuracion(None)
	if i18n.idioma_actual() != i18n.IDIOMA_ORIGEN:
		i18n.cambiar_idioma(i18n.IDIOMA_ORIGEN)


# ════════════════════════════════════════════════════════════════════════════
# Red
# ════════════════════════════════════════════════════════════════════════════


class ConexionBloqueada(RuntimeError):
	"""Una prueba sin ``@pytest.mark.red`` intentó salir a Internet.

	Hereda de ``RuntimeError`` y no de ``OSError`` a propósito: así no la
	absorbe un ``except OSError`` del código probado, y la prueba falla con
	este mensaje.
	"""


def _host_de(direccion) -> str:
	if isinstance(direccion, tuple) and direccion:
		return str(direccion[0])
	return str(direccion)


def _es_local(host: str) -> bool:
	return host in HOSTS_LOCALES or host.startswith("127.") or host.lower() == "localhost"


@dataclass
class RegistroRed:
	"""Intentos de conexión bloqueados (para comprobarlos en la prueba)."""

	intentos: list[str] = field(default_factory=list)


@pytest.fixture
def sin_red(monkeypatch: pytest.MonkeyPatch) -> RegistroRed:
	"""Bloquea las conexiones y resoluciones DNS a equipos no locales."""
	registro = RegistroRed()
	conectar_original = socket.socket.connect
	conectar_ex_original = socket.socket.connect_ex
	resolver_original = socket.getaddrinfo

	def _rechazar(host: str) -> None:
		registro.intentos.append(host)
		raise ConexionBloqueada(
			f"Conexión a «{host}» bloqueada: las pruebas no salen a Internet. Simula la respuesta o marca la prueba con @pytest.mark.red."
		)

	def conectar(sock, direccion):
		if not _es_local(_host_de(direccion)):
			_rechazar(_host_de(direccion))
		return conectar_original(sock, direccion)

	def conectar_ex(sock, direccion):
		if not _es_local(_host_de(direccion)):
			_rechazar(_host_de(direccion))
		return conectar_ex_original(sock, direccion)

	def resolver(host, *args, **kwargs):
		nombre = host.decode() if isinstance(host, bytes) else str(host or "")
		if not _es_local(nombre):
			_rechazar(nombre)
		return resolver_original(host, *args, **kwargs)

	monkeypatch.setattr(socket.socket, "connect", conectar)
	monkeypatch.setattr(socket.socket, "connect_ex", conectar_ex)
	monkeypatch.setattr(socket, "getaddrinfo", resolver)
	return registro


@pytest.fixture(autouse=True)
def _red_controlada(request: pytest.FixtureRequest) -> None:
	"""Aplica ``sin_red`` salvo en las pruebas marcadas ``red``."""
	if BLOQUEAR_RED_SIEMPRE and request.node.get_closest_marker("red") is None:
		request.getfixturevalue("sin_red")


# ════════════════════════════════════════════════════════════════════════════
# Voz simulada
# ════════════════════════════════════════════════════════════════════════════


class VozSimulada:
	"""Sustituye funciones de voz y guarda lo que se habría anunciado."""

	def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
		self._monkeypatch = monkeypatch
		self.llamadas: list[tuple[tuple, dict]] = []

	def parchear(self, ruta: str, obligatorio: bool = True) -> None:
		"""Sustituye la función ``ruta`` («paquete.modulo.funcion»).

		Con ``obligatorio=False`` ignora las rutas que no existen (útil para la
		lista por defecto de ``FUNCIONES_VOZ``).
		"""

		def falsa(*args, **kwargs):
			self.llamadas.append((args, kwargs))
			return True

		try:
			self._monkeypatch.setattr(ruta, falsa)
		except ImportError, AttributeError:
			if obligatorio:
				raise
			log.debug("Función de voz no encontrada: %s", ruta)

	@property
	def textos(self) -> list[str]:
		"""Primer argumento de cada anuncio (el texto)."""
		return [str(args[0]) if args else str(kwargs.get("texto", "")) for args, kwargs in self.llamadas]

	@property
	def ultimo(self) -> str | None:
		"""El último texto anunciado, o ``None`` si no se anunció nada."""
		return self.textos[-1] if self.llamadas else None

	def contiene(self, fragmento: str) -> bool:
		"""True si algún anuncio contiene ``fragmento``."""
		return any(fragmento in texto for texto in self.textos)

	def limpiar(self) -> None:
		"""Olvida los anuncios guardados."""
		self.llamadas.clear()


@pytest.fixture
def voz_simulada(monkeypatch: pytest.MonkeyPatch) -> VozSimulada:
	"""Captura los anuncios en una lista en lugar de hablar.

	Parchea las funciones de ``FUNCIONES_VOZ`` que existan; para otras, llame a
	``voz_simulada.parchear("app.ui.ventana.hablar")``.
	"""
	voz = VozSimulada(monkeypatch)
	for ruta in FUNCIONES_VOZ:
		voz.parchear(ruta, obligatorio=False)
	return voz


# ════════════════════════════════════════════════════════════════════════════
# wx
# ════════════════════════════════════════════════════════════════════════════


def procesar_eventos(condicion: Callable[[], bool] = lambda: False, segundos: float = 3.0) -> bool:
	"""Procesa eventos de wx hasta que se cumple ``condicion`` o pasa el tiempo.

	Sin ``MainLoop`` hay que activar un bucle de eventos a mano: ``wx.CallAfter``
	se atiende en ``ProcessPendingEvents`` y la destrucción diferida de las
	ventanas (``Destroy``) en ``ProcessIdle``. Devuelve el valor final de la
	condición (no falla: quien la llama decide). ``tests.ayudas_wx.esperar_hasta``
	es la variante que falla con un mensaje.
	"""
	import wx

	bucle = wx.GUIEventLoop()
	activo = wx.EventLoopActivator(bucle)
	try:
		limite = time.monotonic() + segundos
		while time.monotonic() < limite:
			while bucle.Pending():
				bucle.Dispatch()
			wx.GetApp().ProcessPendingEvents()
			bucle.ProcessIdle()
			if condicion():
				return True
			time.sleep(0.01)
		return condicion()
	finally:
		del activo


@pytest.fixture(scope="session")
def app_wx():
	"""Una única ``wx.App`` para toda la sesión (crear varias da problemas).

	Con el proveedor de ayuda (Ctrl+H) y el idioma español de wx, como en
	``main.py``. Ninguna prueba debe crear ni destruir la suya.
	"""
	wx = pytest.importorskip("wx")
	aplicacion = wx.App.Get() or wx.App(False)
	wx.HelpProvider.Set(wx.SimpleHelpProvider())
	# La referencia debe vivir toda la sesión: sin ella los botones vuelven al inglés.
	idioma = wx.Locale(wx.LANGUAGE_SPANISH)
	yield aplicacion
	for ventana in list(wx.GetTopLevelWindows()):
		ventana.Destroy()
	procesar_eventos(segundos=0.1)
	del idioma


def _destruir_nuevas(antes: set[int]) -> None:
	"""Destruye las ventanas de nivel superior creadas durante la prueba."""
	import wx

	for ventana in list(wx.GetTopLevelWindows()):
		if id(ventana) not in antes and ventana:
			ventana.Destroy()
	procesar_eventos(segundos=0.05)


@pytest.fixture
def marco(app_wx):
	"""Marco SIN mostrar; al terminar se destruye junto con los diálogos que queden."""
	import wx

	antes = {id(ventana) for ventana in wx.GetTopLevelWindows()}
	ventana = wx.Frame(None, title="Pruebas")
	yield ventana
	_destruir_nuevas(antes)


@pytest.fixture
def panel(marco):
	"""Panel dentro de ``marco`` para crear controles."""
	import wx

	return wx.Panel(marco)


@pytest.fixture
def marco_visible(app_wx, request: pytest.FixtureRequest):
	"""Marco visible: solo para pruebas marcadas ``interfaz`` (foco real, teclas reales)."""
	import wx

	if request.node.get_closest_marker("interfaz") is None:
		pytest.fail("marco_visible solo se usa en pruebas marcadas @pytest.mark.interfaz")
	antes = {id(ventana) for ventana in wx.GetTopLevelWindows()}
	ventana = wx.Frame(None, title="Pruebas (se cerrará sola)")
	ventana.Show()
	yield ventana
	_destruir_nuevas(antes)


@pytest.fixture
def ayudas_wx(app_wx) -> ModuleType:
	"""El módulo ``tests.ayudas_wx`` ya con ``wx.App`` creada.

	Da ``simular_tecla``, ``esperar_hasta``, ``procesar_eventos``,
	``enviar_orden`` y ``propiedades_msaa`` sin tener que importarlo en cada
	módulo de pruebas::

		def test_escape_cierra(marco, ayudas_wx):
			resultado = ayudas_wx.simular_tecla(marco, wx.WXK_ESCAPE)
	"""
	from tests import ayudas_wx as modulo

	return modulo


@dataclass
class DialogoMostrado:
	"""Lo que tenía un diálogo cuando se «mostró» (sigue disponible tras Destroy)."""

	clase: str
	titulo: str
	mensaje: str
	textos: list[str]


class DialogosSimulados:
	"""Sustituye ``ShowModal`` y ``wx.MessageBox`` por respuestas programadas."""

	CLASES = (
		"Dialog",
		"MessageDialog",
		"RichMessageDialog",
		"GenericMessageDialog",
		"FileDialog",
		"DirDialog",
		"TextEntryDialog",
		"PasswordEntryDialog",
		"SingleChoiceDialog",
		"MultiChoiceDialog",
		"ColourDialog",
		"FontDialog",
	)

	def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
		import wx

		self._wx = wx
		self.respuestas: list = []
		self.respuesta_por_defecto = wx.ID_OK
		self.mostrados: list[DialogoMostrado] = []
		for nombre in self.CLASES:
			clase = getattr(wx, nombre, None)
			if clase is not None and "ShowModal" in vars(clase):
				monkeypatch.setattr(clase, "ShowModal", self._sustituto_show_modal())
		monkeypatch.setattr(wx, "MessageBox", self._caja_mensaje)

	def _sustituto_show_modal(self):
		"""Función (no método ligado) para que Python le pase el diálogo como ``self``."""

		def show_modal(dialogo):
			return self._mostrar(dialogo)

		return show_modal

	def responder(self, *respuestas) -> None:
		"""Encola respuestas: un id (``wx.ID_CANCEL``) o una función ``f(dialogo) -> id``.

		La función sirve para rellenar campos antes de «pulsar» Aceptar.
		"""
		self.respuestas.extend(respuestas)

	def _siguiente(self, dialogo):
		respuesta = self.respuestas.pop(0) if self.respuestas else self.respuesta_por_defecto
		return respuesta(dialogo) if callable(respuesta) else respuesta

	def _foto(self, dialogo) -> DialogoMostrado:
		wx = self._wx
		textos: list[str] = []
		for hijo in dialogo.GetChildren():
			pendientes = [hijo]
			while pendientes:
				control = pendientes.pop(0)
				if isinstance(control, wx.TextCtrl):
					textos.append(control.GetValue())
				elif control.GetLabel():
					textos.append(control.GetLabel())
				pendientes.extend(control.GetChildren())
		mensaje = dialogo.GetMessage() if hasattr(dialogo, "GetMessage") else ""
		return DialogoMostrado(type(dialogo).__name__, dialogo.GetTitle(), mensaje, textos)

	def _mostrar(self, dialogo):
		self.mostrados.append(self._foto(dialogo))
		return self._siguiente(dialogo)

	def _caja_mensaje(self, mensaje, titulo="", estilo=0, padre=None, *args, **kwargs):
		self.mostrados.append(DialogoMostrado("MessageBox", str(titulo), str(mensaje), [str(mensaje)]))
		respuesta = self._siguiente(None)
		# wx.MessageBox devuelve wx.OK/wx.YES/wx.NO/wx.CANCEL, no los ID_*.
		equivalencias = {
			self._wx.ID_OK: self._wx.OK,
			self._wx.ID_YES: self._wx.YES,
			self._wx.ID_NO: self._wx.NO,
			self._wx.ID_CANCEL: self._wx.CANCEL,
		}
		return equivalencias.get(respuesta, respuesta)

	@property
	def ultimo(self) -> DialogoMostrado | None:
		"""El último diálogo «mostrado», o ``None``."""
		return self.mostrados[-1] if self.mostrados else None


@pytest.fixture
def dialogo_modal(app_wx, monkeypatch: pytest.MonkeyPatch) -> DialogosSimulados:
	"""Los diálogos modales no se muestran: devuelven la respuesta programada.

	Uso: ``dialogo_modal.responder(wx.ID_CANCEL)`` y, después de la acción,
	``dialogo_modal.ultimo.mensaje``. Sin respuestas encoladas, devuelve
	``wx.ID_OK``.
	"""
	return DialogosSimulados(monkeypatch)


@pytest.fixture(autouse=True)
def _sin_modales_reales(request: pytest.FixtureRequest, monkeypatch: pytest.MonkeyPatch) -> None:
	"""Un ``ShowModal`` real en una prueba se vería en pantalla y colgaría la sesión.

	Falla al momento diciendo qué cuadro era (su título) y en qué prueba. Cubre
	``wx.Dialog`` (y los diálogos propios que heredan de él), los diálogos
	nativos y ``wx.MessageBox``. Las pruebas que necesitan modales usan la
	fixture ``dialogo_modal`` (que los sustituye después) o parchean la función
	que los abre. Las marcadas ``interfaz`` quedan fuera.
	"""
	if request.node.get_closest_marker("interfaz"):
		return
	try:
		import wx
	except ImportError:
		return

	def prohibido(dialogo, *args, **kwargs):
		try:
			titulo = dialogo.GetTitle() if dialogo else "?"
		except Exception:  # noqa: BLE001 - el diálogo puede estar a medio crear
			titulo = "?"
		log.error("ShowModal real durante las pruebas: «%s» (%s)", titulo, request.node.nodeid)
		raise RuntimeError(f"ShowModal real durante las pruebas: «{titulo}» ({request.node.nodeid})")

	def caja_prohibida(mensaje, titulo="", *args, **kwargs):
		log.error("wx.MessageBox real durante las pruebas: «%s» (%s)", titulo, request.node.nodeid)
		raise RuntimeError(f"wx.MessageBox real durante las pruebas: «{titulo}» ({request.node.nodeid})")

	for nombre in DialogosSimulados.CLASES:
		clase = getattr(wx, nombre, None)
		if clase is not None and "ShowModal" in vars(clase):
			monkeypatch.setattr(clase, "ShowModal", prohibido)
	monkeypatch.setattr(wx, "MessageBox", caja_prohibida)
