"""Punto de entrada de EntornoLab.

- Sin argumentos (o con archivos): abre el **Estudio** (wxPython).
- Con ``--jugar`` o ``--recorrido``: delega en el **reproductor** (pygame),
  ANTES de la comprobación de instancia única y sin crear ``wx.App``. El
  reproductor es otra clase de aplicación: puede haber varios abiertos y
  convive con el Estudio. ``jugar.py`` hace lo mismo sin pasar por aquí (es
  el segundo ejecutable).

El ORDEN de arranque importa:

1. ``multiprocessing.freeze_support()`` lo primero: en la versión compilada,
   un proceso hijo de multiprocessing arranca este mismo ``.exe``; si llegara
   a la comprobación de instancia única creería ser una segunda instancia.
2. Registro (solo biblioteca estándar) antes de importar wx y lo pesado: así
   hasta un fallo de importación queda escrito en ``data/logs``.
3. Configuración (valores por defecto en código; un archivo dañado no impide
   arrancar) e idioma (``i18n.inicializar``), antes de importar las ventanas.
4. ``wx.App`` → puente de los mensajes de wx al registro → ``wx.HelpProvider``
   (Ctrl+H) → ``wx.Locale`` del idioma elegido (``i18n.configurar_wx``, que
   conserva la referencia) → instancia única.
5. Anuncio de arranque por voz, SIN ventana de espera: una ventana visible
   mientras el hilo principal importa módulos pesados se marca como «no
   responde» y bloquea al lector de pantalla.
6. Importaciones pesadas, ventana principal, aviso accesible de errores,
   vigilante de congelaciones, novedades de la versión y bucle de eventos.

Todo va envuelto en una red de seguridad: si el arranque falla, se escribe
``data/logs/arranque_fallido.log`` y se enseña un cartel (la versión
compilada no tiene consola donde ver nada).

Argumentos:

- ``--comprobar-arranque``: arranca sin mostrar la ventana y sale con código
  0 si todo fue bien (3 si el paquete pedido no se puede abrir; nunca se
  abre un diálogo). Sirve para pruebas automáticas y para comprobar el
  ``.exe`` recién compilado. Vale también junto a ``--jugar``.
- ``--jugar [paquete] [--actividad id] [--alumno alias] [--sala host:puerto
  --codigo c] [--inicio planta,x,y,rumbo]``: reproductor.
- ``--recorrido paquete --sala host:puerto --codigo c``: modo recorrido.
- Cualquier otro argumento se toma como archivo que abrir en el Estudio.
"""

from __future__ import annotations

import logging
import sys
import time

# Los mismos valores que en app/core/arranque.py. Se repiten aquí para que este
# archivo no importe nada de la aplicación al cargarse: si faltara medio
# programa, el fallo debe ocurrir DENTRO de la red de seguridad de principal().
ARGUMENTO_COMPROBAR = "--comprobar-arranque"
ARGUMENTO_JUGAR = "--jugar"
ARGUMENTO_RECORRIDO = "--recorrido"
# Código de salida de ``--comprobar-arranque`` cuando el paquete pedido no se puede abrir (como en el reproductor).
CODIGO_PAQUETE_NO_VALIDO = 3

# El GIL cede el turno cada 5 ms por defecto. Con hilos de fondo trabajando,
# el hilo de la interfaz tardaba en recuperarlo y el lector de pantalla (que
# pregunta a la interfaz en ese hilo) se quedaba mudo. Con 1 ms la interfaz
# responde enseguida; el coste es despreciable en una aplicación de escritorio.
sys.setswitchinterval(0.001)

log = logging.getLogger("app.main")

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


# Objetos que deben vivir toda la sesión: si el recolector se llevara el
# wx.Locale, los botones volverían al inglés; si se llevara el comprobador de
# instancia, se liberaría el mutex; si se llevara el puente, los mensajes
# internos de wx volverían a salir como cuadros de diálogo.
_VIVOS: dict[str, object] = {}


def _(texto: str) -> str:
	"""Traduce con ``app.core.i18n`` si se puede; si no, devuelve el texto.

	La importación es diferida y protegida: esta función se usa también para
	el cartel de un arranque fallido, cuando puede que nada más funcione.
	"""
	try:
		from app.core import i18n

		return i18n._(texto)
	except Exception:  # noqa: BLE001 - sin traducción se muestra el texto en español
		log.debug("No se pudo traducir un texto del arranque", exc_info=True)
		return texto


def _mostrar_error_arranque(mensaje: str) -> None:
	"""Cartel de error aunque wx no esté disponible (último recurso)."""
	from app.core import arranque

	# Si se pidió el reproductor no se importa wx: se usa el cartel nativo.
	con_wx = not arranque.pide_reproductor(sys.argv[1:])
	arranque.mostrar_error_arranque(mensaje, _("Error al iniciar"), con_wx=con_wx, boton_aceptar=_("&Aceptar"))


def _principal_estudio(argumentos: list[str]) -> int:
	"""Arranca el Estudio: la aplicación wxPython del profesional."""
	inicio = time.perf_counter()
	comprobar = ARGUMENTO_COMPROBAR in argumentos
	archivos = [a for a in argumentos if not a.startswith("--")]

	# 2. Registro (solo biblioteca estándar).
	from app.core import arranque, registro
	from app.core.version import APP_VERSION, ID_APLICACION, NOMBRE_APLICACION

	registro.configurar_registro(NOMBRE_APLICACION, APP_VERSION)

	# 3. Configuración e idioma (antes de importar las ventanas).
	configuracion, idioma = arranque.preparar_configuracion_e_idioma()

	# 3b. Una actualización que quedó a medias (corte de luz, script cerrado a la
	# fuerza) se deshace antes de abrir nada: se lanza recuperar.bat, que espera a
	# que este proceso se cierre, restaura la versión anterior y la vuelve a abrir.
	if not comprobar:
		from app.services import actualizador

		if actualizador.recuperar_al_arrancar():
			log.warning("Actualización interrumpida: se cierra para que recuperar.bat la deshaga.")
			return 0

	# 4. wx, puente de mensajes, ayuda contextual, idioma de wx e instancia única.
	import wx

	from app.core import i18n

	registro.registrar_version_wx()
	# redirect=False: la salida estándar va al registro, no a una ventana de wx.
	aplicacion = wx.App(False)
	aplicacion.SetAppName(ID_APLICACION)
	_VIVOS["puente_wx"] = registro.instalar_puente_wx()
	wx.HelpProvider.Set(wx.SimpleHelpProvider())
	_VIVOS["idioma"] = i18n.configurar_wx(idioma)

	from app.core.instancia_unica import InstanciaUnica

	instancia = InstanciaUnica(ID_APLICACION)
	_VIVOS["instancia"] = instancia
	if instancia.hay_otra():
		log.info("Ya hay otra instancia en marcha; se le pide que se muestre.")
		if not instancia.pedir_mostrar(archivos):
			from app.ui.dialogo_texto import mostrar_mensaje

			mostrar_mensaje(None, _("{nombre} ya está en ejecución.").format(nombre=NOMBRE_APLICACION), NOMBRE_APLICACION)
		return 0

	# 5. Aviso por voz antes de lo pesado (el lector habla aunque estemos ocupados).
	from app.core import voz

	# La salida de voz elegida (automática, solo el lector, SAPI o ninguna) vale ya para este aviso, y
	# después para todo anuncio del Estudio; la suscripción aplica al momento cada cambio de «voz.*».
	_VIVOS["voz"] = voz.aplicar_configuracion(configuracion)
	if not comprobar and configuracion.obtener("general.anunciar_arranque", True):
		# Se espera un momento a que el hilo de voz lo diga: después vienen las importaciones pesadas.
		voz.hablar(_("Iniciando {nombre}").format(nombre=NOMBRE_APLICACION), interrumpir=True, esperar=2.0)

	# 6. Importaciones pesadas y ventana principal.
	from pathlib import Path

	from app.core import procesos, vigilante_ui
	from app.ui import dialogo_error
	from app.ui.ventana_principal import VentanaPrincipal

	ventana = VentanaPrincipal(configuracion, instancia)
	if not comprobar:
		# Errores no controlados: un diálogo accesible (nunca una traza ni una
		# cascada de cuadros). En la comprobación automática no hay nadie que lo
		# cierre: el error queda en el registro y basta.
		dialogo_error.instalar(nombre_app=NOMBRE_APLICACION, anunciar=voz.hablar)
	if archivos:
		# En la comprobación automática no puede abrirse ningún diálogo (nadie lo cerraría y el proceso
		# esperaría para siempre): un paquete que no se puede abrir se registra y sale con el código 3,
		# el mismo que usa el reproductor.
		abierto = ventana.abrir_archivos([Path(a) for a in archivos], interactivo=not comprobar)
		if comprobar and not abierto and any(Path(a).suffix.lower() == ".elab" for a in archivos):
			log.error("Comprobación de arranque: no se pudo abrir %s", ", ".join(archivos))
			ventana.contexto.modificado = False
			ventana.Destroy()
			return CODIGO_PAQUETE_NO_VALIDO

	if comprobar:
		# Las dependencias nativas que solo se usan más tarde (el cifrado de las
		# fichas) se comprueban aquí: así una compilación incompleta falla al
		# compilar y no cuando el profesional abre los alumnos.
		from app.core import cifrado

		motivo = cifrado.comprobar_disponible()
		if motivo:
			log.error("Comprobación de arranque: el cifrado de las fichas no funciona: %s", motivo)
			ventana.Destroy()
			return 1
		# Sin mostrar nada: se cierra en cuanto arranca el bucle de eventos.
		wx.CallAfter(ventana.Close, True)
	else:
		instancia.registrar_ventana(ventana.GetHandle())
		if not (configuracion.obtener("general.iniciar_en_bandeja", False) and ventana.ocultar_en_bandeja()):
			ventana.mostrar()
		vigilante_ui.iniciar()
		if configuracion.obtener("general.comprobar_novedades", True):
			from app.ui import visor_ayuda

			# Con la ventana ya visible, para que el visor quede encima y el lector lo anuncie.
			wx.CallAfter(visor_ayuda.mostrar_novedades_si_procede, ventana, APP_VERSION)
		# Actualizaciones (con su permiso) y oferta de recuperar el trabajo sin guardar de una sesión anterior.
		wx.CallAfter(ventana.despues_de_arrancar)

	log.info("Arranque completado en %.2f s.", time.perf_counter() - inicio)
	aplicacion.MainLoop()

	vigilante_ui.detener()
	registro.establecer_avisador(None)
	# El reproductor lanzado desde el Estudio no debe sobrevivirle.
	procesos.terminar_todos()
	voz.detener()
	configuracion.guardar_pendiente()
	instancia.liberar()
	log.info("Cierre normal.")
	return 0


def _principal(argumentos: list[str]) -> int:
	"""Decide qué aplicación arranca: el reproductor o el Estudio."""
	from app.core import arranque

	if arranque.pide_reproductor(argumentos):
		# Antes de la instancia única y sin wx.App (ver el docstring del módulo).
		return arranque.arrancar_reproductor(argumentos)
	return _principal_estudio(argumentos)


def principal(argumentos: list[str] | None = None) -> int:
	"""Arranca la aplicación y garantiza que ningún fallo quede sin explicación."""
	import multiprocessing

	# 1. Imprescindible en la versión compilada si algo usa multiprocessing.
	multiprocessing.freeze_support()
	try:
		from app.core import arranque
	except BaseException as error:  # noqa: BLE001 - sin el arranque común no hay red de seguridad que valga
		return _cartel_sin_red(error)
	return arranque.con_red_de_seguridad(
		# Envuelto en lambda: así se llama al _principal y al cartel que haya
		# en el módulo en ese momento (las pruebas los sustituyen).
		lambda lista: _principal(lista),
		sys.argv[1:] if argumentos is None else argumentos,
		lambda mensaje: _mostrar_error_arranque(mensaje),
		_,
	)


if __name__ == "__main__":
	sys.exit(principal())
