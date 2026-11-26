"""Progreso accesible de una tarea larga: qué se hace, cuánto lleva, cuánto tarda, y cancelar.

Lo usan los diálogos de importar y exportar, y vale para cualquier operación
larga (comprobar, describir, exportar, abrir un paquete grande). La regla es
que el hilo de la interfaz no se bloquee nunca (un hilo ocupado deja mudo al
lector de pantalla) y que el profesional SIEMPRE sepa qué se está haciendo:

- el estado está siempre escrito en un campo de solo lectura («Estado»),
  donde se puede volver a leer aunque la voz esté desactivada: la fase con
  sus cifras («Convirtiendo calles: 12 de 30.») y el tiempo transcurrido;
- la barra es determinada cuando se sabe el total e indeterminada (se mueve
  sola) cuando no, por ejemplo mientras un servidor prepara los datos;
- la voz NO dice cada actualización (reglas de ``voz-y-braille.md`` del
  agente de accesibilidad: solo fases e hitos, sin interrumpir): dice cada
  CAMBIO de fase, con al menos ``PAUSA_ENTRE_ANUNCIOS_S`` segundos entre
  dos avisos (las fases que duran un instante no se anuncian), y cada
  ``INTERVALO_RECORDATORIO_S`` segundos sin novedades recuerda que sigue
  («Sigue: Convirtiendo calles: 20 de 30. Tiempo: 45 segundos.»). Si la
  tarea no da fases, se anuncian los hitos de porcentaje de siempre (cada
  25 % de fábrica). ``accesibilidad.anunciar_progreso`` lo calla todo;
- cancelar dice que se está cancelando y espera a que la tarea se detenga
  sola en un punto seguro.

Cómo usarlo desde otra operación
--------------------------------

Para esperar una tarea con un diálogo pequeño::

	from app.ui import dialogo_progreso as dp

	def trabajo(tarea) -> Resultado:          # corre en un hilo de trabajo
		for numero, cosa in enumerate(cosas, start=1):
			dp.informar(tarea, _("Comprobando espacios"), numero, len(cosas))
			...                               # nunca tocar wx aquí
		dp.informar(tarea, _("Escribiendo el informe"))   # fase sin cifras
		return resultado

	resultado = dp.ejecutar_tarea(ventana, _("Comprobar el entorno"), trabajo,
		contexto.tareas, contexto.configuracion, fase=_("Comprobando el entorno..."))

``informar(tarea, fase, hecho=None, total=None, texto="")`` se llama desde
el hilo de trabajo tantas veces como se quiera (el gestor de tareas limita
las entregas a unas pocas por segundo y las lleva al hilo de la interfaz con
``wx.CallAfter``); además comprueba la cancelación y lanza
``tareas.TareaCancelada`` si se pidió parar. ``ejecutar_tarea`` devuelve el
resultado o relanza el error (``TareaCancelada`` si se canceló).

Para un diálogo propio con más controles, ``PanelProgreso`` se incrusta y se
lanza con ``panel.lanzar(trabajo, al_terminar, al_fallar, nombre, fase)``.

Para un importador que recibe ``progreso(fraccion, texto)``, pásele
``progreso_de_tarea(tarea)``: además de esa llamada entiende
``por_fases`` (ver ``app.importar.comun.avisar_fase``), con lo que el
diálogo recibe la fase y sus cifras.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any

import wx

from app.core import tareas, voz
from app.core.i18n import _
from app.importar.comun import texto_duracion
from app.ui.esquemas import con_letra

log = logging.getLogger(__name__)

#: Segundos sin novedades tras los que se recuerda por voz que la tarea sigue.
INTERVALO_RECORDATORIO_S = 15.0
#: Segundos mínimos entre dos anuncios de voz del progreso (para no saturar al lector).
PAUSA_ENTRE_ANUNCIOS_S = 3.0
#: Cada cuánto se refresca el tiempo transcurrido y se mueve la barra indeterminada.
TIC_MS = 500


class TareaDirecta:
	"""Tarea de mentira para ejecutar el trabajo en el mismo hilo cuando no hay gestor (pruebas sin hilos)."""

	cancelado = False

	def comprobar(self) -> None:
		"""Nunca se cancela."""

	def progresar(self, hecho: float, total: float | None = None, texto: str = "", fase: str = "") -> None:
		"""El avance de un trabajo directo solo deja rastro en el registro."""
		log.debug("Progreso directo: %s de %s. %s %s", hecho, total, fase, texto)


def informar(tarea: Any, fase: str, hecho: float | None = None, total: float | None = None, texto: str = "") -> None:
	"""Lo que llama una tarea, desde su hilo de trabajo, para decir qué está haciendo.

	:param fase: etapa en curso, dicha a la persona («Comprobando espacios»).
		El diálogo anuncia cada cambio de fase (sin saturar: ver el módulo).
	:param hecho: cuántos lleva, si se sabe.
	:param total: de cuántos; con ``hecho`` y ``total`` la barra es
		determinada y el texto dice «Comprobando espacios: 12 de 30.».
		Sin ellos, la barra se mueve sola (indeterminada).
	:param texto: frase propia en lugar de la que se forma con lo anterior.
	:raises tareas.TareaCancelada: si se ha pedido cancelar (así basta con
		llamar a ``informar`` en cada vuelta para que cancelar funcione).

	No toca wx: se puede llamar desde cualquier hilo.
	"""
	tarea.comprobar()
	cifras = hecho is not None and total is not None and total > 0
	if not texto:
		if cifras:
			texto = _("{fase}: {hecho} de {total}.").format(fase=fase, hecho=_cifra(hecho), total=_cifra(total))
		else:
			texto = _("{fase}…").format(fase=fase)
	tarea.progresar(float(hecho) if cifras and hecho is not None else 0.0, float(total) if cifras and total else None, texto, fase=fase)


def _cifra(valor: float | None) -> str:
	"""Un recuento sin decimales si es entero («12», no «12.0»)."""
	if valor is None:
		return ""
	return str(int(valor)) if float(valor).is_integer() else f"{valor:.1f}"


def _preferencias_de_progreso(configuracion: Any) -> tuple[bool, int]:
	"""(anunciar por voz, cada cuántos puntos de porcentaje) según las preferencias."""
	if configuracion is None:
		return True, 25
	return bool(configuracion.obtener("accesibilidad.anunciar_progreso", True)), int(
		configuracion.obtener("accesibilidad.progreso_cada", 25)
	)


class PanelProgreso(wx.Panel):
	"""Estado en texto, tiempo transcurrido, barra y botón de cancelar de UNA tarea a la vez."""

	def __init__(
		self,
		padre: wx.Window,
		gestor: tareas.GestorTareas | None,
		configuracion: Any = None,
		letras_usadas: set[str] | None = None,
		al_cambiar: Callable[[], None] | None = None,
	) -> None:
		"""Crea el panel.

		:param letras_usadas: letras de acceso ya ocupadas en el diálogo; se
			amplía con las que tome este panel.
		:param al_cambiar: se llama al empezar y al terminar una tarea, para
			que el diálogo active o desactive sus botones.
		"""
		super().__init__(padre, name=_("Progreso"))
		self._gestor = gestor
		self._al_cambiar = al_cambiar
		self._tarea: tareas.Tarea | None = None
		self._anunciar, paso = _preferencias_de_progreso(configuracion)
		self._hitos = tareas.HitosProgreso(paso)
		#: Reloj inyectable: las pruebas simulan el paso del tiempo sin esperar.
		self.reloj: Callable[[], float] = time.monotonic
		self._inicio = 0.0
		self._estado = ""
		self._fase = ""
		self._fase_anunciada = ""
		self._ultimo_anuncio = 0.0
		self._indeterminado = False
		self._segundos_mostrados = -1
		#: Lo que tardó la última tarea, en segundos (para decirlo al terminar).
		self.duracion_ultima = 0.0
		usadas = letras_usadas if letras_usadas is not None else set()
		sizer = wx.BoxSizer(wx.VERTICAL)
		etiqueta = wx.StaticText(self, label=con_letra(_("Estado") + ":", usadas))
		self.estado = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=self.FromDIP(wx.Size(-1, 56)), name=_("Estado"))
		self.estado.SetHelpText(
			_(
				"Lo que se está haciendo ahora, con sus cifras y el tiempo que lleva. Se actualiza solo; puede volver a leerlo cuando quiera."
			)
		)
		etiqueta_barra = wx.StaticText(self, label=_("Progreso:"))
		self.barra = wx.Gauge(self, range=100, name=_("Progreso"))
		self.boton_cancelar = wx.Button(self, label=con_letra(_("Detener la tarea"), usadas))
		self.boton_cancelar.SetHelpText(_("Cancela lo que se está haciendo. Tarda un momento: la tarea se detiene en un punto seguro."))
		self.boton_cancelar.Enable(False)
		self.boton_cancelar.Bind(wx.EVT_BUTTON, lambda _evento: self.cancelar())
		sizer.Add(etiqueta, 0, wx.BOTTOM, self.FromDIP(3))
		sizer.Add(self.estado, 0, wx.EXPAND)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		fila.Add(etiqueta_barra, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, self.FromDIP(6))
		fila.Add(self.barra, 1, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, self.FromDIP(6))
		fila.Add(self.boton_cancelar, 0)
		sizer.Add(fila, 0, wx.EXPAND | wx.TOP, self.FromDIP(6))
		self.SetSizer(sizer)
		# Se guarda el id: en wxPython 4.3 ``evento.GetEventObject()`` de EVT_WINDOW_DESTROY no es ``self``.
		self._id_propio = self.GetId()
		self._temporizador = wx.Timer(self)
		self.Bind(wx.EVT_TIMER, lambda _evento: self.tic(), self._temporizador)
		self.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)

	# ── Consultas ──

	def trabajando(self) -> bool:
		"""True mientras hay una tarea en curso."""
		return self._tarea is not None and not self._tarea.terminada

	@property
	def texto_estado(self) -> str:
		"""La frase de estado actual, sin la línea del tiempo transcurrido."""
		return self._estado

	def transcurrido(self) -> float:
		"""Segundos desde que empezó la tarea en curso (0 si no hay ninguna)."""
		return max(0.0, self.reloj() - self._inicio) if self.trabajando() else 0.0

	# ── Estado y voz ──

	def decir(self, texto: str, hablar: bool = True) -> None:
		"""Escribe el estado y, si procede, lo dice (sin cortar lo que el lector esté leyendo).

		Es para lo que la persona tiene que oír aunque haya callado el progreso
		(``accesibilidad.anunciar_progreso``): el resultado de una orden suya
		(«Cancelando...») o el final de la tarea.
		"""
		self._estado = texto
		self._pintar()
		if hablar and texto:
			self._hablar(texto)

	def _hablar(self, texto: str) -> None:
		self._ultimo_anuncio = self.reloj()
		voz.hablar(texto, False)

	def _pintar(self) -> None:
		"""Pone en el campo de estado la frase y, mientras trabaja, el tiempo transcurrido.

		Se conserva la posición del cursor: si el profesional está leyendo el
		campo con las flechas, una actualización no le devuelve al principio.
		"""
		lineas = [self._estado] if self._estado else []
		if self.trabajando():
			segundos = int(self.transcurrido())
			self._segundos_mostrados = segundos
			if segundos >= 1:
				lineas.append(_("Tiempo transcurrido: {tiempo}.").format(tiempo=texto_duracion(segundos)))
		texto = "\n".join(lineas)
		if self.estado.GetValue() == texto:
			return
		posicion = self.estado.GetInsertionPoint()
		self.estado.ChangeValue(texto)
		self.estado.SetInsertionPoint(min(posicion, self.estado.GetLastPosition()))

	# ── Tarea ──

	def lanzar(
		self,
		trabajo: Callable[[Any], Any],
		al_terminar: Callable[[Any], Any],
		al_fallar: Callable[[BaseException], Any],
		nombre: str,
		fase: str = "",
	) -> None:
		"""Ejecuta ``trabajo(tarea)`` en segundo plano y entrega el resultado en el hilo de la interfaz.

		``fase`` es la primera frase que se dice y se escribe. Sin gestor de
		tareas (pruebas) se ejecuta aquí mismo.
		"""
		if self.trabajando():
			return
		self._hitos.reiniciar()
		self._fase = ""
		self._fase_anunciada = ""
		self._indeterminado = False
		self.barra.SetValue(0)
		self._inicio = self.reloj()
		self._ultimo_anuncio = self._inicio
		if fase:
			self.decir(fase)

		def terminado(resultado: Any) -> None:
			if not self:
				return
			self._acabar()
			self.barra.SetValue(100)
			self._actualizar()
			al_terminar(resultado)

		def fallado(error: BaseException) -> None:
			if not self:
				return
			self._acabar()
			self.barra.SetValue(0)
			self._actualizar()
			if isinstance(error, tareas.TareaCancelada):
				self.decir(_("Cancelado."))
			al_fallar(error)

		if self._gestor is None:
			try:
				resultado = trabajo(TareaDirecta())
			except Exception as error:  # noqa: BLE001 - el fallo se entrega a quien lanzó la tarea, como haría el gestor
				fallado(error)
				return
			terminado(resultado)
			return
		self._tarea = self._gestor.enviar(trabajo, al_terminar=terminado, al_fallar=fallado, al_progresar=self._al_progresar, nombre=nombre)
		if self._tarea is None:
			fallado(RuntimeError(_("La aplicación se está cerrando.")))
			return
		self._temporizador.Start(TIC_MS)
		self._actualizar()

	def _acabar(self) -> None:
		"""La tarea ha terminado (bien, mal o cancelada): para el reloj y anota lo que tardó."""
		# No vale ``transcurrido()``: cuando llega este aviso la tarea ya consta como terminada.
		self.duracion_ultima = max(0.0, self.reloj() - self._inicio)
		self._tarea = None
		if self._temporizador.IsRunning():
			self._temporizador.Stop()
		self._indeterminado = False
		self._pintar()
		log.debug("Tarea terminada en %.1f s", self.duracion_ultima)

	def cancelar(self) -> None:
		"""Pide cancelar la tarea en curso y lo dice: la tarea tarda un momento en detenerse."""
		if self._tarea is not None and not self._tarea.terminada:
			self._tarea.cancelar("cancelada por el usuario")
			self.decir(_("Cancelando..."))
			self.boton_cancelar.Enable(False)

	def _actualizar(self) -> None:
		self.boton_cancelar.Enable(self.trabajando())
		if self._al_cambiar is not None:
			self._al_cambiar()

	def _al_destruir(self, evento: wx.WindowDestroyEvent) -> None:
		# Un temporizador vivo tras destruir su dueño puede tumbar el proceso: se para siempre.
		# Se compara el id (no GetEventObject() is self, que falla en wxPython 4.3); el de un hijo también sube hasta aquí.
		if evento.GetId() == self._id_propio and self._temporizador.IsRunning():
			self._temporizador.Stop()
		evento.Skip()

	# ── Progreso ──

	def _al_progresar(self, progreso: tareas.Progreso) -> None:
		"""Llega en el hilo de la interfaz (el gestor lo trae con ``wx.CallAfter``), unas pocas veces por segundo."""
		if not self:
			return
		porcentaje = progreso.porcentaje
		if porcentaje is None:
			self._indeterminado = True
		else:
			self._indeterminado = False
			self.barra.SetValue(max(0, min(100, porcentaje)))
		if progreso.fase:
			self._fase = progreso.fase
			self._estado = progreso.texto or progreso.fase
			self._pintar()
			return
		# Sin fases: los hitos de porcentaje de siempre.
		hito = self._hitos.nuevo_hito(porcentaje or 0)
		if hito is not None and hito < 100:
			texto = _("{fase} {porcentaje} %.").format(fase=progreso.texto, porcentaje=hito).strip()
			self.decir(texto, hablar=self._anunciar)
		elif progreso.texto:
			self._estado = progreso.texto
			self._pintar()

	def tic(self) -> None:
		"""Cada medio segundo mientras trabaja: mueve la barra indeterminada, el tiempo y, si toca, habla.

		Decide los anuncios aquí (y no al llegar cada progreso) para
		agruparlos: de varias fases seguidas solo se dice la que esté en
		curso cuando toca hablar.
		"""
		if not self:
			return
		if not self.trabajando():
			if self._temporizador.IsRunning():
				self._temporizador.Stop()
			return
		if self._indeterminado:
			self.barra.Pulse()
		if int(self.transcurrido()) != self._segundos_mostrados:
			self._pintar()
		if not self._anunciar or self._tarea is None or self._tarea.cancelado:
			return
		ahora = self.reloj()
		desde_anuncio = ahora - self._ultimo_anuncio
		if self._fase and self._fase != self._fase_anunciada and desde_anuncio >= PAUSA_ENTRE_ANUNCIOS_S:
			self._fase_anunciada = self._fase
			self._hablar(self._estado or self._fase)
		elif desde_anuncio >= INTERVALO_RECORDATORIO_S:
			self._fase_anunciada = self._fase
			self._hablar(
				_("Sigue: {estado} Tiempo: {tiempo}.").format(
					estado=self._estado or _("trabajando."), tiempo=texto_duracion(ahora - self._inicio)
				)
			)


class ProgresoDeTarea:
	"""Función ``progreso(fraccion, texto)`` de los importadores que informa a una tarea del gestor.

	Además tiene ``por_fases`` (ver ``app.importar.comun.avisar_fase``): así
	el importador pasa también la fase y sus cifras, y el diálogo puede
	anunciar los cambios de fase y poner la barra indeterminada cuando no se
	sabe el total. ``desde`` y ``hasta`` reparten la barra cuando una tarea
	hace varias cosas seguidas (leer un fichero y convertirlo).
	"""

	def __init__(self, tarea: Any, desde: float = 0.0, hasta: float = 1.0) -> None:
		self._tarea = tarea
		self._desde = desde
		self._hasta = hasta

	def _porcentaje(self, fraccion: float) -> float:
		return (self._desde + (self._hasta - self._desde) * max(0.0, min(1.0, float(fraccion)))) * 100.0

	def __call__(self, fraccion: float, texto: str) -> None:
		self._tarea.progresar(self._porcentaje(fraccion), 100.0, texto)

	def por_fases(self, fraccion: float, texto: str, fase: str, hecho: int | None, total: int | None, indeterminado: bool) -> None:
		"""Avance con su fase; ``indeterminado`` deja la barra moviéndose sola."""
		if indeterminado:
			self._tarea.progresar(0.0, None, texto, fase=fase)
			return
		self._tarea.progresar(self._porcentaje(fraccion), 100.0, texto, fase=fase)


def progreso_de_tarea(tarea: Any, desde: float = 0.0, hasta: float = 1.0) -> ProgresoDeTarea:
	"""Función ``progreso(fraccion, texto)`` de los importadores que informa a una tarea del gestor (con fases)."""
	return ProgresoDeTarea(tarea, desde, hasta)


def cancelado_de_tarea(tarea: Any) -> Callable[[], bool]:
	"""Función ``cancelado()`` de los importadores a partir de una tarea del gestor."""
	return lambda: bool(tarea.cancelado)


class DialogoTarea(wx.Dialog):
	"""Diálogo pequeño que espera una tarea: estado, tiempo, barra y cancelar. Se cierra solo al terminar."""

	def __init__(self, padre: wx.Window | None, titulo: str, gestor: tareas.GestorTareas | None, configuracion: Any = None) -> None:
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE, name=titulo)
		self.resultado: Any = None
		self.error: BaseException | None = None
		self.terminada = False
		self.panel = PanelProgreso(self, gestor, configuracion)
		sizer = wx.BoxSizer(wx.VERTICAL)
		sizer.Add(self.panel, 1, wx.EXPAND | wx.ALL, self.FromDIP(10))
		self.SetSizer(sizer)
		self.SetSize(self.FromDIP(wx.Size(480, 210)))
		self.Bind(wx.EVT_CLOSE, self._al_cerrar)
		self.Bind(wx.EVT_CHAR_HOOK, self._al_teclear)
		self.CentreOnParent()

	def _al_teclear(self, evento: wx.KeyEvent) -> None:
		# atajo: Escape
		if evento.GetKeyCode() == wx.WXK_ESCAPE and evento.GetModifiers() == wx.MOD_NONE:
			self.panel.cancelar()
			return
		evento.Skip()

	def _al_cerrar(self, evento: wx.CloseEvent) -> None:
		"""Cerrar mientras trabaja es pedir que se cancele; se cierra cuando la tarea se detiene."""
		if self.panel.trabajando() and evento.CanVeto():
			self.panel.cancelar()
			evento.Veto()
			return
		evento.Skip()

	def empezar(self, trabajo: Callable[[Any], Any], fase: str) -> None:
		"""Lanza el trabajo; al acabar guarda el resultado o el error y cierra el diálogo."""
		self.panel.lanzar(trabajo, self._bien, self._mal, self.GetTitle(), fase)

	def _bien(self, resultado: Any) -> None:
		self.resultado = resultado
		self._fin(wx.ID_OK)

	def _mal(self, error: BaseException) -> None:
		self.error = error
		self._fin(wx.ID_CANCEL)

	def _fin(self, codigo: int) -> None:
		self.terminada = True
		if self.IsModal():
			self.EndModal(codigo)


def ejecutar_tarea(
	padre: wx.Window | None,
	titulo: str,
	trabajo: Callable[[Any], Any],
	gestor: tareas.GestorTareas | None = None,
	configuracion: Any = None,
	fase: str = "",
) -> Any:
	"""Ejecuta ``trabajo(tarea)`` sin bloquear la interfaz y devuelve su resultado.

	Mientras dura se ve un diálogo con el estado, el tiempo transcurrido y un
	botón para cancelar (también Escape). Dentro de ``trabajo``, llame a
	``informar(tarea, fase, hecho, total)`` para decir qué hace. Si el
	trabajo falla o se cancela, la excepción sale por aquí
	(``tareas.TareaCancelada`` si se canceló). Sin gestor se ejecuta en el
	mismo hilo, sin diálogo.
	"""
	if gestor is None:
		return trabajo(TareaDirecta())
	dialogo = DialogoTarea(padre, titulo, gestor, configuracion)
	foco_previo = wx.Window.FindFocus()
	try:
		dialogo.empezar(trabajo, fase or titulo)
		if not dialogo.terminada:
			dialogo.ShowModal()
		# Un ShowModal sustituido (pruebas, automatización) vuelve antes de que
		# la tarea acabe: se atienden los eventos hasta que termine.
		aplicacion = wx.GetApp()
		while not dialogo.terminada:
			aplicacion.ProcessPendingEvents()
			wx.YieldIfNeeded()
			time.sleep(0.01)
		if dialogo.error is not None:
			raise dialogo.error
		return dialogo.resultado
	finally:
		dialogo.Destroy()
		if foco_previo:
			foco_previo.SetFocus()
