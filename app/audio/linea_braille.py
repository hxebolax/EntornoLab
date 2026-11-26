"""Un texto dentro de la ventana para lo que el lector de pantalla muestra en la línea braille.

Los lectores de pantalla muestran en braille, de forma fija, el objeto que tiene el foco; los mensajes
sueltos (``nvdaController_brailleMessage``) los quitan a los pocos segundos y vuelven a ese objeto. En
un programa con controles normales, el foco es una lista o un cuadro de texto dentro de la ventana; en
pygame la ventana no tiene nada dentro, y por eso al quitar el mensaje se veía su título.

Así que se le pone dentro lo que tendría cualquier programa (estudiado en el código de NVDA y comprobado
con una línea braille virtual en Reconocedor de Ciudades, de donde viene este módulo sin cambios de fondo):

- Un **control de texto** de Windows (clase ``Static``, de un píxel) hijo de la ventana. Se avisa al
  lector de que tiene el foco (``EVENT_OBJECT_FOCUS``), sin quitárselo de verdad a pygame, que sigue
  recibiendo el teclado: NVDA acepta el foco en un hijo de la ventana que lo tiene. La ventana sigue
  siendo lo que está en primer plano, con su título de siempre (NVDA+T, Alt+Tab), y como panel no se
  muestra en la línea delante del mensaje.
- Su **nombre** es el último mensaje, puesto con las anotaciones dinámicas de MSAA
  (``IAccPropServices::SetHwndPropStr``), que no avisan al lector: cambiar el texto del control sí lo
  haría, y NVDA lo diría otra vez.
- Para que el lector lo vuelva a leer **sin decirlo en voz alta** se avisa de que se ha movido el cursor
  (``EVENT_OBJECT_LOCATIONCHANGE`` con ``OBJID_CARET``): NVDA lo trata como ``caret`` del objeto con el
  foco y su ``event_caret`` solo refresca el braille.
- Al refrescar, NVDA conserva el punto de la línea en el que estaba el usuario: si había desplazado un
  mensaje largo, el siguiente empezaría por la mitad. Pero si ese punto queda fuera del texto, vuelve al
  principio; así que, si el mensaje no cabe en la línea, antes se pone un instante solo lo que cabe en ella
  (``celdas``, una opción): quien no ha desplazado no ve ningún cambio (antes salía la primera letra sola
  y se notaba un parpadeo, «como si el mensaje se pusiera dos veces»).
- La ventana se anota como **panel** (``ROLE_SYSTEM_PANE``): NVDA muestra en la línea, delante del foco,
  la ventana raíz de un programa (un «cliente» con menú de sistema, ``isPresentableFocusAncestor``), y el
  título se quedaba delante del mensaje al entrar o volver a la ventana. Un panel no se muestra. Su nombre
  y su título no se tocan. Tiene que estar anotada antes de que el lector la vea: la aplicación crea la
  ventana oculta, llama a ``instalar`` y la muestra.
- Cada vez que la ventana vuelve a primer plano se avisa otra vez del foco del control (y se repite a los
  0,3 y 0,8 s, porque NVDA atiende a veces a la ventana después): el lector dice el último mensaje, como
  al volver a cualquier programa.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes as w
import logging
import sys
import threading
import time
import uuid

log = logging.getLogger(__name__)

EVENT_OBJECT_FOCUS = 0x8005
EVENT_OBJECT_LOCATIONCHANGE = 0x800B
OBJID_CLIENT = -4
OBJID_CARET = -8
CHILDID_SELF = 0
ROLE_SYSTEM_PANE = 16
VT_I4 = 3
WS_CHILD = 0x40000000
WS_VISIBLE = 0x10000000
RESPIRO = 0.06  # segundos entre el trozo que cabe en la línea y el mensaje entero, para que el lector los vea
TRAS_FOCO = 0.3  # tras darle el foco al control: que el lector lo anuncie antes de cambiarle el nombre
# Al volver a la ventana el lector atiende primero a la ventana, y a veces lo hace después de nuestro aviso: se
# repite (si ya tiene el foco el control, el lector descarta el aviso repetido sin decir nada).
REAFIRMAR = (0.3, 0.8)


class _GUID(ctypes.Structure):
	_fields_ = [("a", ctypes.c_ulong), ("b", ctypes.c_ushort), ("c", ctypes.c_ushort), ("d", ctypes.c_ubyte * 8)]


def _guid(texto: str) -> _GUID:
	u = uuid.UUID(texto)
	return _GUID(u.time_low, u.time_mid, u.time_hi_version, (ctypes.c_ubyte * 8)(*u.bytes[8:]))


CLSID_AccPropServices = _guid("b5f8350b-0548-48b1-a6ee-88bd00b4a5e7")
IID_IAccPropServices = _guid("6e26e776-04f0-495d-80e4-3330352e3169")
PROPID_ACC_NAME = _guid("608d3df8-8128-4aa7-a428-f55e49267291")
PROPID_ACC_ROLE = _guid("cb905ff2-7bd1-4c05-b3c8-e6c241364d70")


class _VARIANT(ctypes.Structure):
	_fields_ = [
		("vt", ctypes.c_ushort),
		("r1", ctypes.c_ushort),
		("r2", ctypes.c_ushort),
		("r3", ctypes.c_ushort),
		("val", ctypes.c_longlong),
		("extra", ctypes.c_longlong),
	]


class _Anotaciones:
	"""``IAccPropServices`` por ctypes (sin comtypes): el nombre del control y el rol de la ventana."""

	def __init__(self) -> None:
		ole32 = ctypes.WinDLL("ole32")
		ole32.CoInitialize(None)  # ya iniciado o en otro modo: da igual, CoCreateInstance funciona
		self._p = ctypes.c_void_p()
		r = ole32.CoCreateInstance(ctypes.byref(CLSID_AccPropServices), None, 1, ctypes.byref(IID_IAccPropServices), ctypes.byref(self._p))
		if r != 0:
			raise OSError(r, "CoCreateInstance(AccPropServices)")
		vt = ctypes.cast(ctypes.cast(self._p, ctypes.POINTER(ctypes.c_void_p))[0], ctypes.POINTER(ctypes.c_void_p))
		hr = ctypes.c_long
		self._prop = ctypes.WINFUNCTYPE(hr, ctypes.c_void_p, w.HWND, w.DWORD, w.DWORD, _GUID, _VARIANT)(vt[6])
		self._texto = ctypes.WINFUNCTYPE(hr, ctypes.c_void_p, w.HWND, w.DWORD, w.DWORD, _GUID, w.LPCWSTR)(vt[7])
		self._limpiar = ctypes.WINFUNCTYPE(hr, ctypes.c_void_p, w.HWND, w.DWORD, w.DWORD, ctypes.POINTER(_GUID), ctypes.c_int)(vt[9])
		self._soltar = ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt[2])

	def nombre(self, hwnd: int, texto: str) -> None:
		hr = self._texto(self._p, hwnd, OBJID_CLIENT & 0xFFFFFFFF, CHILDID_SELF, PROPID_ACC_NAME, texto)
		if hr != 0:
			raise OSError(hr & 0xFFFFFFFF, "IAccPropServices::SetHwndPropStr")

	def rol(self, hwnd: int, rol: int) -> None:
		hr = self._prop(self._p, hwnd, OBJID_CLIENT & 0xFFFFFFFF, CHILDID_SELF, PROPID_ACC_ROLE, _VARIANT(vt=VT_I4, val=rol))
		if hr != 0:
			raise OSError(hr & 0xFFFFFFFF, "IAccPropServices::SetHwndProp")

	def quitar_rol(self, hwnd: int) -> None:
		self._limpiar(self._p, hwnd, OBJID_CLIENT & 0xFFFFFFFF, CHILDID_SELF, ctypes.byref(PROPID_ACC_ROLE), 1)

	def cerrar(self, control: int, ventana: int) -> None:
		self._limpiar(self._p, control, OBJID_CLIENT & 0xFFFFFFFF, CHILDID_SELF, ctypes.byref(PROPID_ACC_NAME), 1)
		self._limpiar(self._p, ventana, OBJID_CLIENT & 0xFFFFFFFF, CHILDID_SELF, ctypes.byref(PROPID_ACC_ROLE), 1)
		self._soltar(self._p)


def lo_que_cabe(texto: str, celdas: int) -> str:
	"""Lo que enseña la línea del principio de ``texto``: NVDA no parte palabras (opción «evitar dividir
	palabras», de fábrica), así que corta en el último espacio que cabe. Comprobado con una línea virtual:
	si no se corta igual, las últimas letras cambian y se nota un parpadeo."""
	if len(texto) <= celdas or texto[celdas] == " ":
		return texto[:celdas]
	corte = texto[:celdas]
	espacio = corte.rfind(" ")
	return corte[: espacio + 1] if espacio > 0 else corte


class LineaVentana:
	"""El control de texto oculto que mantiene el último mensaje fijo en la línea braille (solo NVDA)."""

	def __init__(self) -> None:
		self.hwnd = 0  # la ventana del programa
		self.control = 0  # el texto de dentro, que es lo que tiene el foco para el lector
		self.desde_principio = True
		self.celdas = 40  # celdas de la línea braille del usuario (opción)
		self.en_primer_plano = self._ventana_delante  # la aplicación puede sustituirlo
		self._reafirmar: list[float] = []  # cuándo volver a avisar del foco del control
		self._activa = False
		self._con_foco = False  # si ya se ha dicho al lector que el foco está en el control
		self._visible = ""
		self._pendiente: str | None = None
		self._primera_hecha = False
		self._t = 0.0
		self._cerrojo = threading.Lock()
		self._anotaciones: _Anotaciones | None = None
		self._user32 = None

	def _ventana_delante(self) -> bool:
		"""Si la ventana del programa es la que está en primer plano (sin ventana instalada, se supone que sí)."""
		if self._user32 is None or not self.hwnd:
			return True
		return int(self._user32.GetForegroundWindow() or 0) == int(self.hwnd)

	# ── Instalar en la ventana ───────────────────────────────────────────────

	def instalar(self, hwnd: int) -> bool:
		"""Crea el control de texto dentro de la ventana. Falso si no se puede."""
		if sys.platform != "win32" or not hwnd or self._anotaciones is not None:
			return False
		try:
			u = ctypes.WinDLL("user32", use_last_error=True)
			u.CreateWindowExW.restype = w.HWND
			u.CreateWindowExW.argtypes = [
				w.DWORD, w.LPCWSTR, w.LPCWSTR, w.DWORD, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
				w.HWND, w.HMENU, w.HINSTANCE, w.LPVOID,
			]  # fmt: skip
			u.NotifyWinEvent.argtypes = [w.DWORD, w.HWND, w.LONG, w.LONG]
			u.NotifyWinEvent.restype = None
			u.DestroyWindow.argtypes = [w.HWND]
			u.GetForegroundWindow.restype = w.HWND
			anotaciones = _Anotaciones()
			anotaciones.rol(hwnd, ROLE_SYSTEM_PANE)  # que la línea no ponga el título delante del mensaje
			self._activa = True  # ya anotada: activar(False) la deja como siempre
			control = u.CreateWindowExW(0, "Static", "", WS_CHILD | WS_VISIBLE, 0, 0, 1, 1, hwnd, None, None, None)
			if not control:
				raise OSError(ctypes.get_last_error(), "CreateWindowExW(Static)")
		except Exception:  # noqa: BLE001 - sin esto el braille va como mensajes sueltos
			log.warning("No se pudo preparar la línea braille.", exc_info=True)
			return False
		self._user32, self._anotaciones, self.hwnd, self.control = u, anotaciones, hwnd, control
		log.info("Línea braille: los mensajes se quedan en la línea (control de texto dentro de la ventana).")
		return True

	def quitar(self) -> None:
		"""Antes de cerrar la ventana."""
		if self._anotaciones is None:
			return
		try:
			self._anotaciones.cerrar(self.control, self.hwnd)
			self._user32.DestroyWindow(self.control)
		except Exception:  # noqa: BLE001 - se está cerrando
			log.debug("No se pudo quitar el control de la línea braille.", exc_info=True)
		self._anotaciones = None

	@property
	def instalada(self) -> bool:
		"""Si el control ya está creado dentro de la ventana."""
		return self._anotaciones is not None

	def activar(self, si: bool) -> None:
		"""Con mensajes fijos (y NVDA) el foco está en el control y la ventana es un panel; si no, todo como
		siempre: la ventana, sin anotar, con el foco."""
		if si == self._activa:
			return
		self._activa = si
		if not self.instalada:
			return
		try:
			if si:
				self._anotaciones.rol(self.hwnd, ROLE_SYSTEM_PANE)
			else:
				self._anotaciones.quitar_rol(self.hwnd)
		except Exception:  # noqa: BLE001 - un fallo aquí no debe tumbar el programa
			log.warning("No se pudo cambiar el rol de la ventana.", exc_info=True)
		if not si:
			with self._cerrojo:
				self._pendiente = None
			if self._con_foco:
				self._poner("")
				self._avisar(EVENT_OBJECT_FOCUS, self.hwnd, OBJID_CLIENT)  # el foco, otra vez a la ventana
			self._con_foco = False

	# ── Mostrar ──────────────────────────────────────────────────────────────

	def mostrar(self, texto: str, juntar: bool = False) -> None:
		"""Lo que tiene que quedar en la línea. Se aplica en ``publicar`` (hilo de la ventana).

		``juntar``: si aún no se ha mostrado el anterior (dichos en el mismo momento sin cortarse), van
		los dos, como se oyen."""
		with self._cerrojo:
			if juntar and self._pendiente:
				texto = f"{self._pendiente} {texto}"
			self._pendiente = texto
			self._primera_hecha = False

	def publicar(self, ahora: float | None = None) -> None:
		"""Se llama en cada fotograma, desde el hilo principal.

		Para que cada mensaje se vea desde el principio aunque se desplazara el anterior: NVDA conserva el
		punto de la línea en el que estaba el usuario, salvo que quede fuera del texto, y entonces vuelve al
		principio. Así que, si el mensaje no cabe en la línea, se pone antes un instante solo lo que cabe
		(``celdas``): para quien no ha desplazado, la línea no cambia; para quien sí, su punto queda fuera y
		vuelve al principio. Si cabe entero, no hace falta: el punto ya queda fuera.
		"""
		if not self._activa or not self.instalada:
			return
		try:
			delante = bool(self.en_primer_plano())
		except Exception:  # noqa: BLE001 - ante la duda, sin avisar
			delante = False
		ahora = time.monotonic() if ahora is None else ahora
		if not delante:
			self._con_foco = False  # al volver habrá que darle otra vez el foco al control
			self._reafirmar = []
		elif not self._con_foco:
			self._con_foco = True
			self._avisar(EVENT_OBJECT_FOCUS, self.control, OBJID_CLIENT)  # el lector dice el último mensaje
			self._reafirmar = [ahora + d for d in REAFIRMAR]
		elif self._reafirmar and ahora >= self._reafirmar[0]:
			self._reafirmar.pop(0)
			self._avisar(EVENT_OBJECT_FOCUS, self.control, OBJID_CLIENT)
		if self._reafirmar:
			# Mientras tanto no se cambia el nombre: si el lector pasara entonces al control, diría el mensaje
			# nuevo, que ya se ha dicho.
			self._t = max(self._t, self._reafirmar[-1] + TRAS_FOCO)
		if self._pendiente is None or ahora < self._t:
			return
		with self._cerrojo:
			texto = self._pendiente
			if texto is None:
				return
			primero = (
				delante
				and self.desde_principio
				and not self._primera_hecha
				and len(self._visible) > self.celdas
				and len(texto) > self.celdas
			)
			if primero:
				self._primera_hecha = True
				texto = lo_que_cabe(texto, self.celdas)
			else:
				self._pendiente = None
		if not self._poner(texto):
			return
		if delante:  # en otra ventana se guarda: el lector lo dirá al volver
			self._avisar(EVENT_OBJECT_LOCATIONCHANGE, self.control, OBJID_CARET)
		self._t = ahora + RESPIRO if primero else ahora

	def _poner(self, texto: str) -> bool:
		try:
			self._anotaciones.nombre(self.control, texto)
		except Exception:  # noqa: BLE001 - un fallo aquí no debe tumbar el programa
			log.warning("No se pudo poner el mensaje en la línea braille.", exc_info=True)
			return False
		self._visible = texto
		return True

	def _avisar(self, evento: int, hwnd: int, objeto: int) -> None:
		try:
			self._user32.NotifyWinEvent(evento, hwnd, objeto, CHILDID_SELF)
		except Exception:  # noqa: BLE001 - sin el aviso, la línea se actualiza al siguiente
			log.debug("No se pudo avisar al lector.", exc_info=True)
