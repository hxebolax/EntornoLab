"""Anuncios por voz del Estudio (opcionales), por la salida de voz que elija el profesional.

Usa ``accessible_output2`` si está instalado. Si no está, los anuncios se
omiten sin error: la voz directa es un COMPLEMENTO; lo esencial es que cada
control tenga su nombre, rol y valor correctos para que el lector los lea por
sí solo.

Es la única puerta a la voz del Estudio: el aviso de arranque, los anuncios de
``contexto.anunciar`` (también los de la supervisión) y la voz de
accesibilidad (``app/ui/accesibilidad/voz.py``) pasan por ``hablar``. Por eso
aquí se respeta la preferencia ``voz.salida``, la misma que usa el
reproductor (ver docs/voz.md):

- ``automatica`` (de serie): el lector de pantalla activo y, si no hay, SAPI.
- ``lector``: solo el lector de pantalla; sin él no se habla (nunca SAPI).
- ``sapi``: siempre la voz de Windows, con la voz, la rapidez y la fuerza de
  las preferencias.
- ``ninguna``: no se habla nunca. Si hay un lector abierto y ``voz.braille``
  está activado, el texto va solo a la línea braille.

Con cualquier salida, cada texto queda en ``historial()``: lo que no se oye
se puede repasar (y el Estudio lo deja además en la barra de estado). El
cambio de preferencia se aplica al momento con ``aplicar_configuracion``, que
se suscribe a la sección ``voz`` (también a lo que llegue de otro proceso al
releer la configuración).

**Un hilo propio para COM.** Ninguna llamada a la voz (NVDA, JAWS, SAPI)
se hace en el hilo de la interfaz: ``hablar`` deja el texto en una cola y
un hilo de voz, con su propio apartamento COM (``CoInitializeEx`` en modo
multihilo), crea las salidas de accessible_output2 y las usa. Por qué: si
la voz se llama (o sus objetos COM viven) en el hilo de wx, Windows lanza
``RPC_E_CANTCALLOUT_ININPUTSYNCCALL`` (0x8001010d) cuando se habla justo al
abrir un diálogo, mientras atiende una llamada síncrona de entrada
(activación o foco de ventana), y el anuncio se pierde. La cola respeta el
orden; la interrupción la hace el propio lector (``interrupt=True``). Para el
aviso de arranque, que va antes de lo pesado, ``hablar(..., esperar=...)``
espera un momento a que se haya dicho.
"""

from __future__ import annotations

import logging
import queue
import threading
from collections import deque
from collections.abc import Callable
from typing import Any

log = logging.getLogger(__name__)

SALIDAS: tuple[str, ...] = ("automatica", "lector", "sapi", "ninguna")
SALIDA_DE_SERIE = "automatica"
HISTORIAL_MAXIMO = 200
# Nombres de clase de las voces del sistema que ``Auto`` ofrece cuando no hay lector de pantalla.
_VOCES_DEL_SISTEMA: frozenset[str] = frozenset({"SAPI5", "SAPI4"})

_salida: Any = None
_iniciada = False
_sapi: Any = None
_sapi_iniciada = False
_candado = threading.Lock()
# Aparte del del historial: crear las salidas tarda, y ``hablar`` no debe esperar por ello.
_candado_salidas = threading.Lock()
_estado: dict[str, Any] = {"salida": SALIDA_DE_SERIE, "braille": True, "voz_sapi": "", "velocidad": 0, "volumen": 100}
_historial: deque[str] = deque(maxlen=HISTORIAL_MAXIMO)
_cancelar: Callable[[], None] | None = None
# Cola de trabajos para el hilo de voz: (función, evento de terminado, caja del resultado). None lo para.
_cola: queue.Queue[tuple[Callable[[], Any], threading.Event, list[Any]] | None] = queue.Queue()
_hilo: threading.Thread | None = None
_candado_hilo = threading.Lock()
NOMBRE_HILO = "voz-com"


# ── Lectores ──────────────────────────────────────────────────────────────────


def es_voz_del_sistema(salida: object) -> bool:
	"""Si una salida de accessible_output2 es una voz del sistema (SAPI) y no un lector de pantalla.

	Hace falta para la salida «lector»: ``Auto`` devuelve SAPI como «primera
	salida disponible» cuando no hay lector abierto, y quien eligió «lector»
	no quiere oírla. Se mira el nombre de la clase y el atributo
	``system_output`` de accessible_output2 (los dobles de las pruebas pueden
	usar cualquiera de los dos).
	"""
	if salida is None:
		return False
	return type(salida).__name__ in _VOCES_DEL_SISTEMA or getattr(salida, "system_output", False) is True


def primer_lector(auto: Any, permitir_sistema: bool) -> Any:
	"""El lector de pantalla activo de ``auto`` (``Auto`` de accessible_output2), o None.

	Con ``permitir_sistema`` vale también la voz de Windows (es lo que hace
	``Auto`` por su cuenta). Sin él se recorren sus salidas en orden y se
	salta SAPI, para no caer en la voz de Windows por la puerta de atrás.
	Un objeto sin ``get_first_available_output`` se toma como el lector mismo.
	Lanza lo que lance accessible_output2; quien llama lo registra.
	"""
	if auto is None:
		return None
	if not hasattr(auto, "get_first_available_output"):
		return None if not permitir_sistema and es_voz_del_sistema(auto) else auto
	if permitir_sistema:
		return auto.get_first_available_output()
	salidas = getattr(auto, "outputs", None)
	if isinstance(salidas, (list, tuple)):
		for salida in salidas:
			if not es_voz_del_sistema(salida) and salida.is_active():
				return salida
		return None
	primera = auto.get_first_available_output()
	return None if es_voz_del_sistema(primera) else primera


def _obtener_salida() -> Any:
	"""Crea ``Auto`` la primera vez que se necesita (importación perezosa: el arranque habla antes de lo pesado)."""
	global _salida, _iniciada
	with _candado_salidas:
		if not _iniciada:
			_iniciada = True
			try:
				from accessible_output2.outputs.auto import Auto

				_salida = Auto()
			except Exception:  # noqa: BLE001 - sin voz la aplicación sigue funcionando
				log.info("Voz directa no disponible (accessible_output2 no está instalado o falló).", exc_info=True)
				_salida = None
	return _salida


def _obtener_sapi() -> Any:
	"""Crea la voz SAPI propia la primera vez que la salida «sapi» la necesita."""
	global _sapi, _sapi_iniciada
	with _candado_salidas:
		if not _sapi_iniciada:
			_sapi_iniciada = True
			try:
				from accessible_output2.outputs.sapi5 import SAPI5

				_sapi = SAPI5()
			except Exception:  # noqa: BLE001 - accessible_output2 lanza OutputError sin detalle; se usa la automática
				log.warning("No se pudo abrir la voz SAPI: se usa la salida automática.", exc_info=True)
				_sapi = None
			_ajustar_sapi()
	return _sapi


def _ajustar_sapi() -> None:
	"""Lleva a la voz SAPI propia la voz, la rapidez y la fuerza de las preferencias."""
	if _sapi is None:
		return
	try:
		_sapi.set_rate(int(_estado["velocidad"]))
		_sapi.set_volume(int(_estado["volumen"]))
		nombre = str(_estado["voz_sapi"] or "")
		if nombre:
			voces = [str(voz) for voz in _sapi.list_voices()]
			elegida = next((v for v in voces if v == nombre), None) or next((v for v in voces if nombre.lower() in v.lower()), None)
			if elegida is None:
				log.warning("No está la voz SAPI %s; se deja la de Windows.", nombre)
			else:
				_sapi.set_voice(elegida)
	except Exception:  # noqa: BLE001 - errores COM de SAPI: la voz sigue con lo que tuviera
		log.warning("No se pudieron aplicar los ajustes de la voz SAPI.", exc_info=True)


def usar_salidas(auto: Any = None, sapi: Any = None) -> None:
	"""Sustituye las salidas reales (``Auto`` y SAPI) por las dadas; None, ninguna.

	Para las pruebas: así se comprueba cada salida con dobles que no hablan.
	"""
	global _salida, _iniciada, _sapi, _sapi_iniciada
	with _candado_salidas:
		_salida, _iniciada = auto, True
		_sapi, _sapi_iniciada = sapi, True
	_en_hilo(_ajustar_sapi)


# ── Hilo de voz ───────────────────────────────────────────────────────────────


def _iniciar_com() -> Callable[[], None]:
	"""Abre el apartamento COM del hilo de voz (multihilo: no necesita bombear mensajes). Devuelve cómo cerrarlo."""
	try:
		import pythoncom
	except ImportError:
		log.info("Sin pywin32: el hilo de voz no inicializa COM.")
		return lambda: None
	try:
		pythoncom.CoInitializeEx(pythoncom.COINIT_MULTITHREADED)
	except pythoncom.com_error:
		log.warning("No se pudo inicializar COM en el hilo de voz.", exc_info=True)
		return lambda: None
	return pythoncom.CoUninitialize


def _trabajador() -> None:
	"""Atiende la cola en orden. Toda llamada a accessible_output2 ocurre aquí, nunca en el hilo de wx."""
	cerrar_com = _iniciar_com()
	try:
		while True:
			trabajo = _cola.get()
			if trabajo is None:
				return
			funcion, hecho, caja = trabajo
			try:
				caja.append(funcion())
			except Exception:  # noqa: BLE001 - un fallo de voz no debe parar el hilo: el siguiente anuncio debe poder decirse
				log.warning("Falló un trabajo del hilo de voz.", exc_info=True)
			finally:
				hecho.set()
	finally:
		cerrar_com()


def _asegurar_hilo() -> None:
	global _hilo
	with _candado_hilo:
		if _hilo is None or not _hilo.is_alive():
			_hilo = threading.Thread(target=_trabajador, name=NOMBRE_HILO, daemon=True)
			_hilo.start()


def _en_hilo(funcion: Callable[[], Any], esperar: float = 0.0) -> Any:
	"""Encarga ``funcion`` al hilo de voz. Con ``esperar`` (segundos) aguarda y devuelve su resultado (None si no llega).

	Si quien llama ya ES el hilo de voz, se ejecuta en el momento (si no, se
	esperaría a sí mismo).
	"""
	if threading.current_thread() is _hilo:
		return funcion()
	hecho = threading.Event()
	caja: list[Any] = []
	_asegurar_hilo()
	_cola.put((funcion, hecho, caja))
	if esperar > 0 and hecho.wait(esperar):
		return caja[0] if caja else None
	return None


def esperar_cola(segundos: float = 2.0) -> bool:
	"""Espera a que el hilo de voz haya atendido todo lo pedido hasta ahora. True si ha dado tiempo (pruebas y cierre)."""
	hecho = threading.Event()
	_asegurar_hilo()
	_cola.put((lambda: None, hecho, []))
	return hecho.wait(segundos)


def detener(segundos: float = 2.0) -> None:
	"""Para el hilo de voz tras decir lo pendiente (al cerrar la aplicación)."""
	global _hilo
	with _candado_hilo:
		hilo = _hilo
		_hilo = None
	if hilo is not None and hilo.is_alive():
		_cola.put(None)
		hilo.join(timeout=segundos)


def voces_sapi(segundos: float = 3.0) -> list[str]:
	"""Nombres de las voces SAPI instaladas, consultados desde el hilo de voz (nunca COM en el hilo de wx)."""

	def listar() -> list[str]:
		try:
			from accessible_output2.outputs.sapi5 import SAPI5

			return [str(voz) for voz in SAPI5().list_voices()]
		except Exception:  # noqa: BLE001 - sin SAPI o sin la biblioteca no hay voces que listar
			log.info("No se pudieron listar las voces SAPI.", exc_info=True)
			return []

	resultado = _en_hilo(listar, esperar=segundos)
	return list(resultado) if isinstance(resultado, list) else []


# ── Preferencias ──────────────────────────────────────────────────────────────


def configurar(
	salida: str | None = None,
	braille: bool | None = None,
	voz_sapi: str | None = None,
	velocidad: int | None = None,
	volumen: int | None = None,
) -> None:
	"""Aplica la salida de voz y los ajustes de SAPI. ``velocidad`` va de 0 a 100, como en las preferencias.

	Un valor desconocido de ``salida`` (configuración de otra versión) se
	toma como la de serie: es mejor hablar de más que dejar al profesional
	sin voz por un error.
	"""
	if salida is not None:
		nueva = salida if salida in SALIDAS else SALIDA_DE_SERIE
		if nueva != _estado["salida"]:
			log.info("Salida de voz del Estudio: %s", nueva)
		_estado["salida"] = nueva
	if braille is not None:
		_estado["braille"] = bool(braille)
	if voz_sapi is not None:
		_estado["voz_sapi"] = str(voz_sapi)
	if velocidad is not None:
		_estado["velocidad"] = max(-10, min(10, round((int(velocidad) - 50) / 5)))
	if volumen is not None:
		_estado["volumen"] = max(0, min(100, int(volumen)))
	if _sapi_iniciada:
		_en_hilo(_ajustar_sapi)


def salida_actual() -> str:
	"""La salida de voz que se está usando: automatica, lector, sapi o ninguna."""
	return str(_estado["salida"])


def _leer_configuracion(configuracion: Any) -> None:
	"""Toma de la sección ``voz`` lo que usa el Estudio (se tolera una sección rota: queda lo de serie)."""
	seccion = configuracion.obtener("voz", {}) or {}
	if not isinstance(seccion, dict):
		log.warning("La sección «voz» de la configuración no es un diccionario; se deja la voz de serie.")
		return
	try:
		configurar(
			salida=str(seccion.get("salida") or SALIDA_DE_SERIE),
			braille=bool(seccion.get("braille", True)),
			voz_sapi=str(seccion.get("voz_sapi") or ""),
			velocidad=int(seccion.get("velocidad", 50)),
			volumen=int(seccion.get("volumen", 100)),
		)
	except TypeError, ValueError:
		log.warning("Valores de voz no válidos en la configuración; se deja la voz de serie.", exc_info=True)


def aplicar_configuracion(configuracion: Any) -> Callable[[], None]:
	"""Aplica ``voz.*`` ahora y cada vez que cambie (Preferencias, el reproductor o ``recargar``).

	Devuelve la función que cancela la suscripción. Una segunda llamada
	sustituye a la primera: el Estudio tiene una sola configuración.
	"""
	global _cancelar
	_leer_configuracion(configuracion)
	if _cancelar is not None:
		_cancelar()

	def al_cambiar(_clave: str, _anterior: Any, _nuevo: Any) -> None:
		_leer_configuracion(configuracion)

	cancelar = configuracion.suscribir(al_cambiar, "voz.")

	def cancelar_y_olvidar() -> None:
		global _cancelar
		cancelar()
		if _cancelar is cancelar_y_olvidar:
			_cancelar = None

	_cancelar = cancelar_y_olvidar
	return cancelar_y_olvidar


# ── Historial ─────────────────────────────────────────────────────────────────


def historial() -> list[str]:
	"""Copia de los últimos textos anunciados, se hayan dicho o no (con «ninguna» tampoco se pierden)."""
	with _candado:
		return list(_historial)


def ultimo() -> str:
	"""El último texto anunciado («» si no hay)."""
	with _candado:
		return _historial[-1] if _historial else ""


def olvidar_historial() -> None:
	"""Vacía el historial (pruebas)."""
	with _candado:
		_historial.clear()


# ── Hablar ────────────────────────────────────────────────────────────────────


def _decir(texto: str, interrumpir: bool, modo: str, braille: bool) -> bool:
	"""Dice ``texto`` con la salida ``modo``; en el hilo de voz. True si se ha dicho en voz alta."""
	try:
		if modo == "ninguna":
			# No se habla: el texto va solo a la línea braille del lector, si lo hay y el braille está activado.
			lector = primer_lector(_obtener_salida(), permitir_sistema=False) if braille else None
			if lector is not None:
				lector.braille(texto)
			return False
		if modo == "sapi":
			sapi = _obtener_sapi()
			if sapi is not None:
				sapi.speak(texto, interrupt=interrumpir)
				return True
		lector = primer_lector(_obtener_salida(), permitir_sistema=modo != "lector")
		if lector is None:
			return False
		lector.speak(texto, interrupt=interrumpir)
		return True
	except Exception:  # noqa: BLE001 - un fallo de voz no debe romper nada
		log.warning("No se pudo anunciar por voz: %s", texto, exc_info=True)
		return False


def hablar(texto: str, interrumpir: bool = False, esperar: float = 0.0) -> bool:
	"""Anuncia ``texto`` por la salida de voz elegida, desde el hilo de voz.

	Vuelve enseguida: el texto queda en la cola (en orden) y en el historial,
	aunque no se diga. Devuelve True si se va a decir en voz alta (la salida
	no es «ninguna»); con ``esperar`` (segundos) aguarda a que se haya dicho
	y devuelve si de verdad se dijo. Se puede llamar desde cualquier hilo y
	desde cualquier manejador de eventos: no toca controles wx ni COM.
	"""
	texto = (texto or "").strip()
	if not texto:
		return False
	with _candado:
		_historial.append(texto)
	modo = str(_estado["salida"])
	braille = bool(_estado["braille"])
	if modo == "ninguna" and not braille:
		return False
	resultado = _en_hilo(lambda: _decir(texto, interrumpir, modo, braille), esperar=esperar)
	if esperar > 0:
		return bool(resultado)
	return modo != "ninguna"
