"""Utilidades para probar interfaces wxPython sin mostrar ventanas.

Se importan desde las pruebas (``from tests.ayudas_wx import simular_tecla``)
y desde ``conftest.py``. No dependen de ningún módulo de la aplicación.

Por qué existen:

- Sin ``MainLoop`` en marcha, ``wx.CallAfter`` deja eventos pendientes y los
  temporizadores (``wx.Timer``, ``wx.CallLater``) no disparan nunca. Aquí se
  activa un bucle de eventos temporal para procesarlos.
- Los eventos de teclado sintéticos (``wx.KeyEvent``) prueban los manejadores
  sin depender del foco real ni del sistema operativo.
- ``wx.UIActionSimulator`` sí envía pulsaciones reales: solo se usa con la
  ventana visible y en primer plano, porque si no, las teclas acabarían en otra
  aplicación (por ejemplo, en el editor o en el lector de pantalla).

Procede de la plantilla del agente «pruebas».
"""

from __future__ import annotations

import logging
import sys
import time
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Callable, Iterator

import pytest

wx = pytest.importorskip("wx")

log = logging.getLogger(__name__)


# ── Bucle de eventos ─────────────────────────────────────────────────────────


@contextmanager
def bucle_activo() -> Iterator[None]:
	"""Garantiza un bucle de eventos activo mientras dura el bloque.

	Si ya hay uno (por ejemplo, dentro de ``MainLoop``), no hace nada. Si no,
	crea un ``wx.GUIEventLoop`` y lo activa: sin él, ``wx.Yield`` no entrega
	los mensajes de temporizador de Windows.
	"""
	if wx.EventLoopBase.GetActive() is not None:
		yield
		return
	bucle = wx.GUIEventLoop()
	with wx.EventLoopActivator(bucle):
		yield


def procesar_eventos(veces: int = 3) -> None:
	"""Procesa los eventos pendientes (``wx.CallAfter``, ``PostEvent``, mensajes).

	Se repite varias veces porque un manejador puede encolar otro evento.
	"""
	app = wx.GetApp()
	if app is None:
		raise RuntimeError("No hay wx.App: usa la fixture app_wx (o marco/panel).")
	with bucle_activo():
		for _vuelta in range(veces):
			app.ProcessPendingEvents()
			app.Yield(True)


def esperar_hasta(
	condicion: Callable[[], bool],
	tiempo: float = 2.0,
	mensaje: str = "",
	intervalo: float = 0.01,
) -> None:
	"""Procesa eventos hasta que ``condicion()`` sea verdadera o se agote el tiempo.

	Pensada para hilos que terminan con ``wx.CallAfter`` y para temporizadores.
	Falla con un mensaje claro en lugar de colgar la sesión de pruebas.
	"""
	app = wx.GetApp()
	if app is None:
		raise RuntimeError("No hay wx.App: usa la fixture app_wx (o marco/panel).")
	limite = time.monotonic() + tiempo
	with bucle_activo():
		while True:
			app.ProcessPendingEvents()
			app.Yield(True)
			if condicion():
				return
			if time.monotonic() >= limite:
				raise AssertionError(f"No se cumplió la condición en {tiempo} s. {mensaje}".strip())
			time.sleep(intervalo)


# ── Teclado y órdenes ────────────────────────────────────────────────────────


@dataclass
class ResultadoTecla:
	"""Qué pasó con una pulsación sintética.

	``gestionado``: un manejador la consumió (``ProcessEvent`` devolvió True, lo
	que solo ocurre si NO llamó a ``Skip()``). ``saltado``: el manejador llamó a
	``Skip()``, así que la tecla seguiría su camino normal (Tab, flechas,
	escritura). Un ``EVT_CHAR_HOOK`` que no salta las teclas que no gestiona
	deja el teclado bloqueado.
	"""

	gestionado: bool
	saltado: bool
	evento: object


def simular_tecla(
	ventana,
	tecla: int | str,
	*,
	ctrl: bool = False,
	mayus: bool = False,
	alt: bool = False,
	tipo=None,
) -> ResultadoTecla:
	"""Envía un ``wx.KeyEvent`` sintético a ``ventana``.

	:param tecla: código de wx (``wx.WXK_F5``, ``wx.WXK_ESCAPE``) o un carácter
		(``"s"``: se convierte a mayúscula, que es lo que entrega Windows en
		``EVT_KEY_DOWN`` y ``EVT_CHAR_HOOK``).
	:param tipo: tipo de evento; por defecto ``wx.wxEVT_CHAR_HOOK``. También
		``wx.wxEVT_KEY_DOWN`` o ``wx.wxEVT_CHAR``.
	"""
	codigo = ord(tecla.upper()) if isinstance(tecla, str) else int(tecla)
	evento = wx.KeyEvent(tipo if tipo is not None else wx.wxEVT_CHAR_HOOK)
	evento.SetKeyCode(codigo)
	evento.SetControlDown(ctrl)
	evento.SetShiftDown(mayus)
	evento.SetAltDown(alt)
	evento.SetEventObject(ventana)
	evento.SetId(ventana.GetId())
	gestionado = ventana.GetEventHandler().ProcessEvent(evento)
	return ResultadoTecla(gestionado=bool(gestionado), saltado=evento.GetSkipped(), evento=evento)


def enviar_orden(control, tipo_evento=None) -> bool:
	"""Simula la orden de un control (pulsar un botón, marcar una casilla...).

	Por defecto envía ``wx.wxEVT_BUTTON``. Para una casilla, usa
	``wx.wxEVT_CHECKBOX`` después de ``SetValue`` (``SetValue`` no genera evento).
	"""
	evento = wx.CommandEvent(tipo_evento if tipo_evento is not None else wx.wxEVT_BUTTON, control.GetId())
	evento.SetEventObject(control)
	if isinstance(control, (wx.CheckBox, wx.ToggleButton)):
		evento.SetInt(int(control.GetValue()))
	return bool(control.GetEventHandler().ProcessEvent(evento))


# ── Entrada real (solo pruebas marcadas «interfaz») ──────────────────────────


def _ventana_en_primer_plano(ventana) -> bool:
	"""Indica si la ventana de nivel superior de ``ventana`` es la activa de Windows."""
	if sys.platform != "win32":
		return ventana.GetTopLevelParent().IsActive()
	import ctypes

	activa = ctypes.windll.user32.GetForegroundWindow()
	return int(activa) == int(ventana.GetTopLevelParent().GetHandle())


def _foco_de_teclado_real(control) -> bool:
	"""Indica si Windows entrega ya el teclado a ``control`` (foco del hilo de primer plano).

	``GetForegroundWindow`` cambia antes de que el hilo de la ventana procese
	su activación; hasta entonces las teclas simuladas se pierden o van a la
	ventana anterior. ``GetGUIThreadInfo`` dice dónde va de verdad el teclado.
	"""
	if sys.platform != "win32":
		return wx.Window.FindFocus() is control
	import ctypes
	from ctypes import wintypes

	class InfoHilo(ctypes.Structure):
		_fields_ = [
			("cbSize", wintypes.DWORD),
			("flags", wintypes.DWORD),
			("hwndActive", wintypes.HWND),
			("hwndFocus", wintypes.HWND),
			("hwndCapture", wintypes.HWND),
			("hwndMenuOwner", wintypes.HWND),
			("hwndMoveSize", wintypes.HWND),
			("hwndCaret", wintypes.HWND),
			("rcCaret", wintypes.RECT),
		]

	user32 = ctypes.windll.user32
	user32.GetForegroundWindow.restype = wintypes.HWND
	user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.c_void_p]
	user32.GetWindowThreadProcessId.restype = wintypes.DWORD
	user32.GetGUIThreadInfo.argtypes = [wintypes.DWORD, ctypes.c_void_p]
	user32.GetGUIThreadInfo.restype = wintypes.BOOL
	hilo = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
	info = InfoHilo()
	info.cbSize = ctypes.sizeof(InfoHilo)
	if not hilo or not user32.GetGUIThreadInfo(hilo, ctypes.byref(info)):
		return False
	return int(info.hwndFocus or 0) == int(control.GetHandle())


def escribir_con_simulador(control, texto: str, espera: float = 2.0) -> None:
	"""Escribe ``texto`` con pulsaciones reales (``wx.UIActionSimulator``).

	Se salta la prueba si la ventana no está visible y en primer plano: Windows
	impide robar el foco a otra aplicación y las teclas irían a parar a ella.
	"""
	marco = control.GetTopLevelParent()
	if not marco.IsShown():
		pytest.skip("UIActionSimulator necesita la ventana visible (usa la fixture marco_visible).")
	marco.Raise()
	control.SetFocus()
	procesar_eventos()
	if not _ventana_en_primer_plano(control) or wx.Window.FindFocus() is not control:
		pytest.skip("La ventana de pruebas no está en primer plano; no se envían teclas reales.")
	# No se escribe hasta que Windows lleve el teclado al control: si se envían
	# antes, las teclas pueden ir a parar a la ventana que tenía el foco (otra aplicación).
	try:
		esperar_hasta(lambda: _foco_de_teclado_real(control), 1.0)
	except AssertionError:
		pytest.skip("Windows no ha llevado el teclado a la ventana de pruebas; no se envían teclas reales.")
	# Text() recibe bytes y solo garantiza letras ASCII: con la distribución de
	# teclado española, los dígitos y signos pueden salir cambiados.
	try:
		datos = texto.encode("ascii")
	except UnicodeEncodeError as error:
		raise ValueError("UIActionSimulator solo escribe ASCII; usa SetValue para otros textos") from error
	simulador = wx.UIActionSimulator()
	enviado = simulador.Text(datos)
	if not enviado:
		# SendInput rechazado: escritorio bloqueado o de otra sesión, o una ventana con más privilegios delante.
		pytest.skip("Windows no admite teclas simuladas ahora (escritorio bloqueado o protegido).")
	try:
		esperar_hasta(lambda: texto in control.GetValue(), espera, "El control no recibió el texto simulado.")
	except AssertionError:
		# Otra aplicación (o la ventana de pruebas de otro proceso) puede quitarnos el primer plano
		# mientras se escribe: entonces las teclas fueron a ella y no es un fallo de lo probado.
		# Se vio en repeticiones con varias baterías a la vez (4 de 13 pasadas).
		if not _ventana_en_primer_plano(control) or wx.Window.FindFocus() is not control:
			pytest.skip("La ventana de pruebas perdió el primer plano mientras se escribía; las teclas fueron a otra.")
		raise AssertionError(f"El control no recibió el texto simulado: tiene {control.GetValue()!r}, se esperaba {texto!r}.") from None


# ── Accesibilidad (MSAA) ─────────────────────────────────────────────────────


def propiedades_msaa(ventana, hijo: int = 0) -> dict:
	"""Nombre, rol, estado y valor MSAA de una ventana, como los ve un lector.

	Necesita Windows y ``comtypes`` (dependencia de desarrollo); si falta, la
	prueba se salta. No sustituye a la prueba con un lector de pantalla real.
	"""
	if sys.platform != "win32":
		pytest.skip("MSAA solo existe en Windows.")
	pytest.importorskip("comtypes")
	import ctypes
	from ctypes import POINTER, byref, wintypes

	import comtypes.client

	interfaz = comtypes.client.GetModule("oleacc.dll").IAccessible
	puntero = POINTER(interfaz)()
	objid_client = -4
	ctypes.oledll.oleacc.AccessibleObjectFromWindow(
		wintypes.HWND(int(ventana.GetHandle())),
		wintypes.DWORD(objid_client & 0xFFFFFFFF),
		byref(interfaz._iid_),
		byref(puntero),
	)
	datos: dict = {}
	for clave, propiedad in (("nombre", "accName"), ("rol", "accRole"), ("estado", "accState"), ("valor", "accValue")):
		try:
			datos[clave] = getattr(puntero, propiedad)(hijo)
		except Exception:  # noqa: BLE001 - el control no implementa esa propiedad
			log.debug("MSAA sin %s para %r", propiedad, ventana, exc_info=True)
			datos[clave] = None
	return datos
