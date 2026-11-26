"""Piezas del arranque que comparten ``main.py`` (Estudio) y ``jugar.py`` (reproductor).

Los dos puntos de entrada siguen el mismo orden de seguridad:

1. ``multiprocessing.freeze_support()`` lo primero (versión compilada).
2. Registro, con solo la biblioteca estándar, antes de importar nada pesado:
   hasta un fallo de importación queda escrito en ``data/logs``.
3. Configuración (un archivo dañado no impide arrancar).
4. Idioma.
5. La aplicación.

Y todo dentro de una red de seguridad (``con_red_de_seguridad``): si el
arranque muere, se escribe ``data/logs/arranque_fallido.log`` y se enseña un
cartel, porque la versión compilada no tiene consola donde ver nada.

Este módulo solo usa la biblioteca estándar al importarse. No importa wx
(el reproductor no lo usa) salvo dentro de ``mostrar_error_arranque`` y solo
si se le pide.
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable

log = logging.getLogger(__name__)

ARGUMENTO_COMPROBAR = "--comprobar-arranque"
ARGUMENTO_JUGAR = "--jugar"
ARGUMENTO_RECORRIDO = "--recorrido"

# MB_OK | MB_ICONERROR | MB_SETFOREGROUND: el cartel sale delante y el lector lo anuncia.
_ESTILO_CARTEL = 0x0 | 0x10 | 0x10000


def N_(texto: str) -> str:  # noqa: N802 - nombre convencional de gettext
	"""Marca un texto para el extractor de cadenas sin traducirlo.

	Es una copia local de ``app.core.i18n.N_``: este módulo no puede importar
	``i18n`` al cargarse, porque debe funcionar aunque el idioma falle.
	"""
	return texto


_TEXTO_NO_INICIA = N_("No se pudo iniciar la aplicación.")
_TEXTO_DETALLES = N_("Los detalles están en {ruta}.")
_TEXTO_SIN_REGISTRO = N_("Compruebe que la carpeta «data» existe y no es de solo lectura.")


def pide_reproductor(argumentos: list[str]) -> bool:
	"""True si la línea de órdenes pide el reproductor (``--jugar`` o ``--recorrido``)."""
	return ARGUMENTO_JUGAR in argumentos or ARGUMENTO_RECORRIDO in argumentos


def mostrar_error_arranque(mensaje: str, titulo: str, con_wx: bool = True, boton_aceptar: str = "&Aceptar") -> None:
	"""Cartel de error de último recurso, aunque casi nada funcione.

	:param con_wx: probar primero un diálogo de wx (el Estudio). El
		reproductor pasa ``False``: no debe importar wx solo para un cartel.
	"""
	if con_wx:
		try:
			import wx

			if wx.GetApp() is None:
				wx.App(False)
			# MessageDialog y no MessageBox: este deja que el botón diga «Aceptar».
			dialogo = wx.MessageDialog(None, mensaje, titulo, wx.OK | wx.ICON_ERROR)
			dialogo.SetOKLabel(boton_aceptar)
			try:
				dialogo.ShowModal()
			finally:
				dialogo.Destroy()
			return
		except Exception:  # noqa: BLE001 - si wx falla, se prueba el cartel nativo
			log.debug("No se pudo mostrar el cartel con wx", exc_info=True)
	try:
		import ctypes

		ctypes.windll.user32.MessageBoxW(0, mensaje, titulo, _ESTILO_CARTEL)
	except Exception:  # noqa: BLE001 - ya no queda dónde avisar salvo la consola
		log.debug("No se pudo mostrar el cartel nativo", exc_info=True)
		if sys.__stderr__ is not None:
			print(mensaje, file=sys.__stderr__)


def preparar_configuracion_e_idioma() -> tuple[object, str]:
	"""Carga la configuración, ajusta el nivel del registro y elige el idioma.

	Deja la configuración como instancia compartida
	(``obtener_configuracion()``), para que el resto de la aplicación use la
	misma que el arranque.

	:return: (configuración, código del idioma activo).
	"""
	from app.core import i18n, registro
	from app.core.configuracion import Configuracion, establecer_configuracion

	configuracion = Configuracion()
	establecer_configuracion(configuracion)
	if configuracion.recuperacion:
		log.warning("Configuración: %s", configuracion.recuperacion)
	nivel = str(configuracion.obtener("registro.nivel", "INFO")).upper()
	# En depuración (APP_DEPURACION=1) manda DEBUG y no se baja.
	raiz = logging.getLogger()
	if nivel in ("DEBUG", "INFO", "WARNING", "ERROR") and not raiz.isEnabledFor(logging.DEBUG) and raiz.level != getattr(logging, nivel):
		registro.cambiar_nivel(nivel)
	idioma = i18n.inicializar(str(configuracion.obtener("general.idioma", "auto")))
	return configuracion, idioma


def arrancar_reproductor(argumentos: list[str]) -> int:
	"""Arranca el reproductor (``--jugar`` o ``--recorrido``) y devuelve su código de salida.

	Se llama ANTES de la comprobación de instancia única y sin crear
	``wx.App``: el reproductor es otro tipo de aplicación (pygame), puede
	haber varios abiertos y convive con el Estudio. Usa un registro propio
	(``jugar_*.log``) porque el Estudio puede estar escribiendo en la misma
	carpeta.
	"""
	from app.core import registro
	from app.core.version import APP_VERSION, NOMBRE_APLICACION

	registro.configurar_registro_auxiliar(f"{NOMBRE_APLICACION} (reproductor)", APP_VERSION)
	preparar_configuracion_e_idioma()

	from app.reproductor import arranque as arranque_reproductor

	codigo = int(arranque_reproductor.ejecutar(list(argumentos)))
	log.info("Reproductor terminado con el código %d.", codigo)
	return codigo


def con_red_de_seguridad(
	funcion: Callable[[list[str]], int],
	argumentos: list[str],
	mostrar: Callable[[str], None],
	traducir: Callable[[str], str] = str,
) -> int:
	"""Ejecuta ``funcion(argumentos)`` y garantiza que ningún fallo quede sin explicación.

	:param mostrar: función que enseña el cartel de error (recibe el mensaje).
	:param traducir: función de traducción; por defecto, el texto tal cual
		(el fallo puede ocurrir antes de que exista el idioma).
	:return: el código de ``funcion``, o 1 si falló.
	"""
	try:
		return funcion(argumentos)
	except SystemExit:
		raise
	except BaseException as error:  # noqa: BLE001 - red de seguridad del arranque
		log.critical("Fallo no controlado al iniciar la aplicación.", exc_info=True)
		ruta = None
		try:
			from app.core import registro

			ruta = registro.registrar_fallo_de_arranque(error)
		except Exception:  # noqa: BLE001 - el propio registro puede ser lo que falla
			log.debug("No se pudo escribir arranque_fallido.log", exc_info=True)
		detalle = traducir(_TEXTO_DETALLES).format(ruta=ruta) if ruta else traducir(_TEXTO_SIN_REGISTRO)
		mostrar(traducir(_TEXTO_NO_INICIA) + f"\n\n{type(error).__name__}: {error}\n\n" + detalle)
		return 1
