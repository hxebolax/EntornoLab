"""Punto de entrada directo del reproductor de EntornoLab (segundo ejecutable).

Equivale a ``main.py --jugar``: es lo que se compila como
``EntornoLabJugar.exe`` y lo que abre el alumno. Admite los mismos
argumentos que ``main.py --jugar`` (sin necesidad de escribir ``--jugar``),
``--recorrido`` y ``--comprobar-arranque``::

	jugar.py [paquete] [--actividad id] [--alumno alias]
	         [--sala host:puerto --codigo c] [--inicio planta,x,y,rumbo]
	jugar.py --recorrido paquete --sala host:puerto --codigo c
	jugar.py --comprobar-arranque
	jugar.py --guion pasos.json [--informe informe.json] [paquete ...]

``--guion`` (con ``APP_SIN_VENTANA=1`` para no abrir ventana ni sonar)
ejecuta los pasos del JSON y sale con un código: sirve a las pruebas de
proceso real, al diagnóstico y a la comprobación de la versión compilada
(ver ``docs/reproductor.md``).

Sigue el mismo orden de seguridad que ``main.py`` (está en
``app/core/arranque.py``): ``freeze_support``, registro, configuración,
idioma y, dentro de una red de seguridad que deja
``data/logs/arranque_fallido.log`` y enseña un cartel, el reproductor.

Aquí nunca se importa wx ni se comprueba la instancia única: puede haber
varios reproductores a la vez y conviven con el Estudio.
"""

from __future__ import annotations

import logging
import sys

# Los mismos valores que en app/core/arranque.py. Se repiten aquí para que este
# archivo no importe nada de la aplicación al cargarse: si faltara medio
# programa, el fallo debe ocurrir DENTRO de la red de seguridad de principal().
ARGUMENTO_COMPROBAR = "--comprobar-arranque"
ARGUMENTO_JUGAR = "--jugar"
ARGUMENTO_RECORRIDO = "--recorrido"

# Igual que en main.py: con el turno del GIL a 1 ms, el hilo principal (el
# bucle del juego y la voz) recupera antes el control aunque haya hilos de
# sonido y de red trabajando.
sys.setswitchinterval(0.001)

log = logging.getLogger("app.jugar")

__all__ = ["ARGUMENTO_COMPROBAR", "ARGUMENTO_JUGAR", "ARGUMENTO_RECORRIDO", "principal"]


def _cartel_sin_red(error: BaseException) -> int:
	"""Último recurso si ni siquiera se puede importar el arranque común (instalación incompleta).

	Solo biblioteca estándar: a estas alturas no se puede contar con nada de
	``app``. Devuelve el código de salida 1.
	"""
	mensaje = f"No se pudo iniciar la aplicación: faltan archivos del programa.\n\n{type(error).__name__}: {error}"
	try:
		import ctypes

		ctypes.windll.user32.MessageBoxW(0, mensaje, "Error al iniciar", 0x10 | 0x10000)
	except Exception:  # noqa: BLE001 - ya no queda dónde avisar salvo la consola
		log.debug("No se pudo mostrar el cartel nativo", exc_info=True)
		if sys.__stderr__ is not None:
			print(mensaje, file=sys.__stderr__)
	return 1


def _(texto: str) -> str:
	"""Traduce si el idioma ya está disponible; si no, devuelve el texto en español."""
	try:
		from app.core import i18n

		return i18n._(texto)
	except Exception:  # noqa: BLE001 - sin traducción se muestra el texto en español
		log.debug("No se pudo traducir un texto del arranque", exc_info=True)
		return texto


def _mostrar_error_arranque(mensaje: str) -> None:
	"""Cartel nativo de Windows: el reproductor no usa wx."""
	from app.core import arranque

	arranque.mostrar_error_arranque(mensaje, _("Error al iniciar"), con_wx=False)


def _principal(argumentos: list[str]) -> int:
	"""Arranca el reproductor con los argumentos de la línea de órdenes."""
	from app.core import arranque

	return arranque.arrancar_reproductor(argumentos)


def principal(argumentos: list[str] | None = None) -> int:
	"""Arranca el reproductor y garantiza que ningún fallo quede sin explicación."""
	import multiprocessing

	# Imprescindible en la versión compilada si algo usa multiprocessing.
	multiprocessing.freeze_support()
	try:
		from app.core import arranque
	except BaseException as error:  # noqa: BLE001 - sin el arranque común no hay red de seguridad que valga
		return _cartel_sin_red(error)
	return arranque.con_red_de_seguridad(
		lambda lista: _principal(lista),
		sys.argv[1:] if argumentos is None else argumentos,
		lambda mensaje: _mostrar_error_arranque(mensaje),
		_,
	)


if __name__ == "__main__":
	sys.exit(principal())
