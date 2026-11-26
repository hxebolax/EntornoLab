"""Modo recorrido: el pegamento con wx (temporizador, diálogos y mensajes).

La lógica está en ``app/ui/recorrido.py`` y no sabe nada de ventanas. Aquí
solo se hace lo que necesita la interfaz:

- un ``wx.Timer`` que atiende la sala cada poco EN EL HILO PRINCIPAL, porque
  las peticiones cambian el entorno y pueden abrir un diálogo;
- los dos diálogos que una petición puede necesitar (el catálogo con la
  posición ya puesta y el nombre de un punto), trayendo antes el Estudio al
  frente, ya que el profesional está en la ventana del reproductor;
- los errores de arranque explicados en un mensaje accesible.

Nada de aquí bloquea la interfaz: ``detener`` espera como mucho un segundo.
"""

from __future__ import annotations

import logging
from typing import Any

import wx

from app.core.i18n import _
from app.dominio.modelo import Posicion
from app.ui.accesibilidad.dialogos import mostrar_error, pedir_texto
from app.ui.recorrido import ErrorRecorrido, SesionRecorrido

log = logging.getLogger(__name__)

#: Cada cuánto se mira si el reproductor ha pedido algo, en milisegundos.
INTERVALO_MS = 150


class ControladorRecorrido:
	"""Arranca, atiende y cierra el modo recorrido desde la ventana principal."""

	def __init__(self, contexto: Any, sala: Any = None) -> None:
		"""Prepara el controlador; no abre nada hasta ``iniciar``.

		:param sala: una ``Sala`` ya creada, solo para pruebas.
		"""
		self.contexto = contexto
		self.sesion = SesionRecorrido(contexto, sala=sala, pedir_objeto=self._pedir_objeto, pedir_nombre=self._pedir_nombre)
		self._temporizador: wx.Timer | None = None
		self._atendiendo = False

	@property
	def activo(self) -> bool:
		"""True mientras hay un recorrido en marcha."""
		return self.sesion.activa

	# ── Arranque y cierre ────────────────────────────────────────────────────

	def iniciar(self, inicio: Posicion | None = None) -> bool:
		"""Empieza el recorrido. Si no se puede, lo explica y devuelve False."""
		if self.activo:
			self.contexto.anunciar(_("Ya hay un recorrido en marcha."))
			return True
		from app.core.procesos import ErrorProceso
		from app.supervision.sala import ErrorSala

		try:
			self.sesion.iniciar(inicio)
		except (ErrorRecorrido, ErrorSala, ErrorProceso) as error:
			log.warning("No se pudo iniciar el modo recorrido: %s", error)
			mostrar_error(self._ventana(), str(error), _("Recorrer el entorno"))
			return False
		self._arrancar_temporizador()
		self.contexto.anunciar(_("Abriendo el reproductor para recorrer el entorno."))
		return True

	def detener(self) -> None:
		"""Cierra el reproductor y la sala del recorrido."""
		self._parar_temporizador()
		estaba = self.activo
		self.sesion.detener()
		if estaba:
			self.contexto.anunciar(_("Recorrido terminado."))

	def al_cambiar_entorno(self) -> None:
		"""Tras un cambio hecho en el Estudio mientras se recorre: guarda y avisa al reproductor.

		Los cambios que nacen de una petición del propio reproductor ya se
		guardan y se avisan en su respuesta: aquí se saltan para no guardar dos veces.
		"""
		if self.activo and not self._atendiendo:
			self.sesion.guardar_y_avisar()

	# ── Temporizador ─────────────────────────────────────────────────────────

	def _ventana(self) -> wx.Window | None:
		ventana = self.contexto.ventana
		return ventana if isinstance(ventana, wx.Window) and ventana else None

	def _arrancar_temporizador(self) -> None:
		ventana = self._ventana()
		if ventana is None:
			# Sin ventana (pruebas sin interfaz) quien use el controlador llama a ``atender`` a mano.
			return
		if self._temporizador is None:
			self._temporizador = wx.Timer(ventana)
			ventana.Bind(wx.EVT_TIMER, self._al_latir, self._temporizador)
		self._temporizador.Start(INTERVALO_MS)

	def _parar_temporizador(self) -> None:
		if self._temporizador is not None and self._temporizador.IsRunning():
			self._temporizador.Stop()

	@property
	def temporizador_en_marcha(self) -> bool:
		"""True si el temporizador está atendiendo la sala."""
		return self._temporizador is not None and self._temporizador.IsRunning()

	def _al_latir(self, _evento: wx.TimerEvent) -> None:
		self.atender()

	def atender(self) -> None:
		"""Atiende la sala una vez y anuncia lo que haya pasado.

		Un diálogo abierto por una petición deja correr el temporizador: la
		marca ``_atendiendo`` evita atender otra petición encima de la primera.
		"""
		if self._atendiendo:
			return
		self._atendiendo = True
		try:
			frases = self.sesion.atender()
		except Exception:  # noqa: BLE001 - el temporizador late todo el recorrido; un fallo no debe romperlo
			log.exception("Error al atender el modo recorrido")
			frases = []
		finally:
			self._atendiendo = False
		for frase in frases:
			self.contexto.anunciar(frase)
		if not self.sesion.activa:
			self._parar_temporizador()

	# ── Diálogos que puede necesitar una petición ────────────────────────────

	def _traer_al_frente(self) -> None:
		"""El profesional está en la ventana del reproductor: el diálogo tiene que quedar delante."""
		ventana = self._ventana()
		if ventana is None:
			return
		if isinstance(ventana, wx.TopLevelWindow):
			if ventana.IsIconized():
				ventana.Iconize(False)
			ventana.Raise()
			ventana.RequestUserAttention()

	def _pedir_objeto(self, planta_id: str, x: float, y: float, rumbo: float) -> str | None:
		"""Abre el catálogo con la posición ya puesta; devuelve el id del objeto colocado o None."""
		try:
			from app.ui import dialogo_catalogo
		except ImportError:
			log.exception("No está el diálogo del catálogo; no se puede elegir el objeto")
			return None
		self._traer_al_frente()
		return dialogo_catalogo.insertar_objeto(self.contexto, planta_id, None, (x, y), rumbo)

	def _pedir_nombre(self, propuesta: str) -> str | None:
		"""Pregunta el nombre del punto que se va a marcar."""
		self._traer_al_frente()
		return pedir_texto(self._ventana(), _("&Nombre del punto:"), _("Marcar este punto"), propuesta, max_caracteres=80)
