"""Diálogo accesible de actualizaciones del Estudio y arranque del actualizador.

- :func:`mostrar_dialogo_actualizacion`: lo que abre Ayuda, «Buscar actualizaciones».
  Busca la versión nueva, enseña las novedades en un campo de solo lectura,
  descarga e instala con progreso cancelable, y reúne las opciones: comprobar
  al arrancar, canal y saltar una versión.
- :func:`al_arrancar`: se llama una vez tras mostrar la ventana principal.
  Explica cómo acabó la actualización anterior, confirma el arranque (para la
  vuelta atrás), PREGUNTA la primera vez si se quiere comprobar al arrancar y,
  solo con ese permiso, comprueba en segundo plano una vez al día.

Accesibilidad: cada campo tiene su etiqueta creada justo antes (de ella toma
el nombre el lector de pantalla), todas las letras de acceso son distintas,
los botones están en español y dicen la acción, el progreso se anuncia por
hitos (25, 50, 75 y 100 %) y no por cada cambio, y todo se puede cancelar.

La red y el disco van siempre en tareas de fondo (``app.core.tareas``): la
ventana nunca se bloquea y el lector de pantalla nunca se queda mudo.

Procede de la plantilla del agente «actualizador».
"""

from __future__ import annotations

import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import wx

from app.core import tareas, voz
from app.core.i18n import _, _n, separador_decimal
from app.core.version import NOMBRE_APLICACION
from app.services import actualizador

log = logging.getLogger(__name__)

RESULTADO_CERRADO = "cerrado"
RESULTADO_ACTUALIZAR = "actualizar"
RESULTADO_SALTADA = "saltada"

_gestor: tareas.GestorTareas | None = None


def gestor_de_red() -> tareas.GestorTareas:
	"""Gestor de tareas compartido por los diálogos que usan la red (se crea al primer uso)."""
	global _gestor
	if _gestor is None:
		_gestor = tareas.GestorTareas(max_hilos=2, nombre="red")
	return _gestor


def _decir(texto: str) -> None:
	"""Anuncia por el lector de pantalla un cambio que este no puede saber por sí solo."""
	if texto:
		voz.hablar(texto)


def _megas(tamano: int) -> str:
	return _("{megas} MB").format(megas=f"{tamano / 1_048_576:.1f}".replace(".", separador_decimal()))


def mostrar_mensaje(padre: wx.Window | None, mensaje: str, titulo: str, icono: int = wx.ICON_INFORMATION) -> None:
	"""Mensaje modal con el botón «Aceptar» en español (delegado en ``dialogo_texto``)."""
	from app.ui import dialogo_texto

	dialogo_texto.mostrar_mensaje(padre, mensaje, titulo, icono)


def confirmar(padre: wx.Window | None, mensaje: str, titulo: str, si: str, no: str, por_defecto_no: bool = True) -> bool:
	"""Pregunta con dos botones que dicen la acción (nunca «Sí» y «No» a secas)."""
	estilo = wx.YES_NO | wx.ICON_QUESTION | (wx.NO_DEFAULT if por_defecto_no else wx.YES_DEFAULT)
	dialogo = wx.MessageDialog(padre, mensaje, titulo, estilo)
	dialogo.SetYesNoLabels(si, no)
	try:
		return dialogo.ShowModal() == wx.ID_YES
	finally:
		dialogo.Destroy()


def preguntar_permiso(padre: wx.Window | None) -> bool:
	"""Pregunta, UNA sola vez, si se quiere comprobar al arrancar; guarda y devuelve la respuesta.

	El botón predeterminado es el de no conectar: un Intro sin leer no da permiso.
	"""
	aceptado = confirmar(
		padre,
		_(
			"¿Quiere que {aplicacion} compruebe al arrancar si hay una versión nueva?\n\n"
			"Si acepta, una vez al día descargará de GitHub un fichero pequeño con el número de la última versión "
			"y la lista de complementos. No se envía ningún dato suyo, de sus alumnos ni de sus entornos.\n\n"
			"Si no acepta, {aplicacion} no se conectará a Internet salvo que usted lo pida. "
			"Puede cambiarlo cuando quiera en el menú Ayuda, «Buscar actualizaciones»."
		).format(aplicacion=NOMBRE_APLICACION),
		_("Comprobar actualizaciones"),
		_("&Sí, comprobar al arrancar"),
		_("&No conectar"),
	)
	actualizador.establecer_comprobacion_al_arrancar(aceptado)
	return aceptado


def _cerrar_aplicacion() -> None:
	"""Cierre normal de la ventana principal (se guardan preferencias y trabajo).

	Si la ventana tiene ``salir()``, se usa: con «minimizar a la bandeja»,
	``Close()`` solo la oculta, la aplicación sigue abierta y el script de
	sustitución se cansa de esperar.
	"""
	aplicacion = wx.GetApp()
	ventana = aplicacion.GetTopWindow() if aplicacion else None
	if not ventana:
		return
	salir = getattr(ventana, "salir", None)
	if callable(salir):
		salir()
	else:
		ventana.Close(force=True)


class DialogoActualizacion(wx.Dialog):
	"""Busca, enseña e instala la versión nueva, y reúne las opciones de actualización."""

	def __init__(
		self,
		padre: wx.Window | None,
		config: actualizador.Configuracion | None = None,
		info: actualizador.InfoActualizacion | None = None,
		gestor: tareas.GestorTareas | None = None,
		al_cerrar_app: Callable[[], None] | None = None,
	) -> None:
		super().__init__(padre, title=_("Actualizaciones"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER)
		self.config = config or actualizador.configuracion_por_defecto()
		self.info: actualizador.InfoActualizacion | None = None
		self.resultado = RESULTADO_CERRADO
		self._gestor = gestor or gestor_de_red()
		self._al_cerrar_app = al_cerrar_app or _cerrar_aplicacion
		self._tarea: tareas.Tarea | None = None
		self._fase = ""
		self._decena = -1
		self._hitos = tareas.HitosProgreso(25)
		self._crear_controles()
		self._mostrar_sin_novedad(_("Versión instalada: {version}.").format(version=self.config.version_actual))
		if info is not None:
			self._mostrar_info(info, anunciar=False)
		self.CentreOnParent()

	# ── Construcción ─────────────────────────────────────────────────────────

	def _crear_controles(self) -> None:
		principal = wx.BoxSizer(wx.VERTICAL)
		borde = self.FromDIP(10)

		# Cada etiqueta se crea justo antes de su campo: el lector la usa como nombre.
		etiqueta_estado = wx.StaticText(self, label=_("&Estado:"))
		self.estado = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY, size=self.FromDIP(wx.Size(520, 60)))
		principal.Add(etiqueta_estado, 0, wx.LEFT | wx.RIGHT | wx.TOP, borde)
		principal.Add(self.estado, 0, wx.ALL | wx.EXPAND, borde)

		etiqueta_novedades = wx.StaticText(self, label=_("&Novedades de la versión nueva:"))
		self.novedades = wx.TextCtrl(self, style=wx.TE_MULTILINE | wx.TE_READONLY | wx.TE_RICH2, size=self.FromDIP(wx.Size(520, 200)))
		principal.Add(etiqueta_novedades, 0, wx.LEFT | wx.RIGHT, borde)
		principal.Add(self.novedades, 1, wx.ALL | wx.EXPAND, borde)

		self.barra = wx.Gauge(self, range=100)
		self.barra.SetName(_("Progreso de la actualización"))
		principal.Add(self.barra, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, borde)

		self.casilla_arrancar = wx.CheckBox(self, label=_("Compro&bar al arrancar si hay una versión nueva (una vez al día)"))
		self.casilla_arrancar.SetValue(actualizador.comprobacion_al_arrancar())
		self.casilla_arrancar.SetHelpText(
			_("Si está marcada, la aplicación descarga de GitHub un fichero pequeño al arrancar. No envía ningún dato personal.")
		)
		principal.Add(self.casilla_arrancar, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, borde)

		fila_canal = wx.BoxSizer(wx.HORIZONTAL)
		etiqueta_canal = wx.StaticText(self, label=_("Cana&l:"))
		self.canal = wx.Choice(self, choices=[_("Estable"), _("Pruebas (versiones preliminares)")])
		self.canal.SetSelection(actualizador.CANALES.index(self.config.canal))
		fila_canal.Add(etiqueta_canal, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, self.FromDIP(6))
		fila_canal.Add(self.canal, 0)
		principal.Add(fila_canal, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, borde)

		botones = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_comprobar = wx.Button(self, label=_("&Comprobar ahora"))
		self.boton_actualizar = wx.Button(self, label=_("&Actualizar ahora"))
		self.boton_saltar = wx.Button(self, label=_("&Saltar esta versión"))
		self.boton_cerrar = wx.Button(self, wx.ID_CANCEL, label=_("Cerra&r"))
		for boton in (self.boton_comprobar, self.boton_actualizar, self.boton_saltar, self.boton_cerrar):
			botones.Add(boton, 0, wx.ALL, self.FromDIP(5))
		principal.Add(botones, 0, wx.ALIGN_RIGHT | wx.ALL, self.FromDIP(5))
		self.SetSizerAndFit(principal)

		self.SetEscapeId(wx.ID_CANCEL)
		self.boton_comprobar.Bind(wx.EVT_BUTTON, lambda _evento: self.comprobar())
		self.boton_actualizar.Bind(wx.EVT_BUTTON, lambda _evento: self.actualizar())
		self.boton_saltar.Bind(wx.EVT_BUTTON, lambda _evento: self.saltar())
		self.boton_cerrar.Bind(wx.EVT_BUTTON, self._al_boton_cerrar)
		self.casilla_arrancar.Bind(wx.EVT_CHECKBOX, self._al_cambiar_casilla)
		self.canal.Bind(wx.EVT_CHOICE, self._al_cambiar_canal)
		self.Bind(wx.EVT_CLOSE, self._al_cerrar)

	# ── Estado ───────────────────────────────────────────────────────────────

	def trabajando(self) -> bool:
		"""True mientras hay una comprobación o una descarga en curso."""
		return self._tarea is not None and not self._tarea.terminada

	def _poner_estado(self, texto: str, decir: bool = False) -> None:
		self.estado.SetValue(texto)
		if decir:
			_decir(texto)

	def _habilitar(self) -> None:
		ocupado = self.trabajando()
		hay_nueva = self.info is not None
		self.boton_comprobar.Enable(not ocupado)
		self.boton_actualizar.Enable(not ocupado and hay_nueva and actualizador.puede_instalar(self.config))
		self.boton_saltar.Enable(not ocupado and hay_nueva)
		self.canal.Enable(not ocupado)
		self.boton_cerrar.SetLabel(_("Cancela&r") if ocupado else _("Cerra&r"))

	def _mostrar_sin_novedad(self, texto: str, decir: bool = False) -> None:
		self.info = None
		self.novedades.SetValue(_("No hay ninguna versión nueva que mostrar."))
		self.barra.SetValue(0)
		self._poner_estado(texto, decir)
		self._habilitar()

	def _mostrar_info(self, info: actualizador.InfoActualizacion, anunciar: bool = True) -> None:
		self.info = info
		partes = [
			_("Hay una versión nueva: {nueva}. Versión instalada: {actual}.").format(nueva=info.version, actual=self.config.version_actual)
		]
		if info.fecha:
			partes.append(_("Publicada el {fecha}.").format(fecha=info.fecha))
		partes.append(_("Tamaño de la descarga: {tamano}.").format(tamano=_megas(info.tamano)))
		if info.canal == "pruebas":
			partes.append(_("Es una versión de pruebas."))
		if not actualizador.puede_instalar(self.config):
			partes.append(_("Esta copia se ejecuta desde el código fuente: actualícela con su sistema de control de versiones."))
		self.novedades.SetValue(info.novedades or _("Esta versión no trae notas de novedades."))
		self.novedades.SetInsertionPoint(0)
		self.barra.SetValue(0)
		self._poner_estado(" ".join(partes), anunciar)
		self._habilitar()
		if self.boton_actualizar.IsEnabled():
			self.boton_actualizar.SetDefault()

	def enfocar_inicial(self) -> None:
		"""Foco en el estado: el lector lo lee entero y se puede releer con las flechas."""
		if self:
			self.estado.SetFocus()

	# ── Opciones ─────────────────────────────────────────────────────────────

	def _al_cambiar_casilla(self, _evento: wx.CommandEvent) -> None:
		actualizador.establecer_comprobacion_al_arrancar(self.casilla_arrancar.GetValue())

	def _al_cambiar_canal(self, _evento: wx.CommandEvent) -> None:
		canal = actualizador.CANALES[max(0, self.canal.GetSelection())]
		actualizador.establecer_canal(canal)
		self.config.canal = canal
		# Lo que se encontró era del otro canal: hay que volver a mirar.
		self._mostrar_sin_novedad(_("Canal cambiado. Pulse «Comprobar ahora» para buscar versiones en este canal."), decir=True)

	# ── Comprobar ────────────────────────────────────────────────────────────

	def comprobar(self) -> None:
		"""Busca la versión nueva en segundo plano. La manual siempre informa del resultado."""
		if self.trabajando():
			return
		self._mostrar_sin_novedad(_("Buscando actualizaciones..."), decir=True)
		config = self.config
		self._tarea = self._gestor.enviar(
			lambda tarea: actualizador.comprobar(config, cancelacion=tarea.token),
			al_terminar=self._al_comprobar,
			al_fallar=self._al_fallar,
			nombre="comprobar actualizaciones",
		)
		self._habilitar()

	def _al_comprobar(self, info: actualizador.InfoActualizacion | None) -> None:
		if not self:
			return
		self._tarea = None
		if info is None:
			self._mostrar_sin_novedad(
				_("Ya tiene la versión más reciente ({version}).").format(version=self.config.version_actual), decir=True
			)
		else:
			self._mostrar_info(info)
		self.estado.SetFocus()

	def _al_fallar(self, error: BaseException) -> None:
		if not self:
			return
		self._tarea = None
		self.barra.SetValue(0)
		if isinstance(error, (tareas.TareaCancelada, actualizador.ErrorCancelado)):
			mensaje = _("Cancelado. Si había empezado la descarga, continuará donde se quedó la próxima vez.")
		elif isinstance(error, actualizador.ErrorActualizacion):
			mensaje = str(error)
		else:
			log.error("Fallo inesperado en el diálogo de actualizaciones", exc_info=error)
			mensaje = _("Se ha producido un error inesperado. Los detalles están en el registro.")
		self._poner_estado(mensaje, decir=True)
		self._habilitar()
		# El foco va al estado para que el lector lea el error y se pueda releer.
		self.estado.SetFocus()

	# ── Actualizar ───────────────────────────────────────────────────────────

	def _reproductores_cerrados(self) -> bool:
		"""Comprueba que no hay reproductores abiertos; si los hay, avisa y pide permiso para cerrarlos.

		El reproductor comparte carpeta y bibliotecas con el Estudio: abierto,
		no se puede sustituir. Nunca se cierra sin avisar: puede haber un alumno
		en plena sesión.
		"""
		abiertos = actualizador.reproductores_abiertos(self.config)
		if not abiertos:
			return True
		aceptado = confirmar(
			self,
			_n(
				"Hay {n} reproductor abierto. Para actualizar hay que cerrarlo, y la sesión en curso del alumno se perderá.",
				"Hay {n} reproductores abiertos. Para actualizar hay que cerrarlos, y las sesiones en curso se perderán.",
				len(abiertos),
			).format(n=len(abiertos)),
			_("Reproductor abierto"),
			_("&Cerrar el reproductor y actualizar"),
			_("&No actualizar ahora"),
		)
		if not aceptado:
			self._poner_estado(_("Actualización aplazada: hay un reproductor abierto."), decir=True)
			return False
		quedan = actualizador.cerrar_reproductores(self.config)
		if quedan:
			self._poner_estado(
				_("Sigue habiendo un reproductor abierto que no lanzó el Estudio. Ciérrelo a mano y vuelva a pulsar «Actualizar ahora»."),
				decir=True,
			)
			self.estado.SetFocus()
			return False
		return True

	def actualizar(self) -> None:
		"""Descarga, verifica y prepara la versión nueva; después cierra el Estudio para instalarla."""
		if self.trabajando() or self.info is None or not actualizador.puede_instalar(self.config):
			return
		if not self._reproductores_cerrados():
			return
		self._fase = ""
		self._decena = -1
		self._hitos.reiniciar()
		self.barra.SetValue(0)
		self._poner_estado(_("Iniciando la descarga..."), decir=True)
		config, info = self.config, self.info

		def trabajo(tarea: tareas.Tarea) -> Path:
			return actualizador.descargar_y_preparar(
				config, info, progreso=lambda fase, hecho, total: tarea.progresar(hecho, total, fase), cancelacion=tarea.token
			)

		self._tarea = self._gestor.enviar(
			trabajo,
			al_terminar=self._al_preparada,
			al_fallar=self._al_fallar,
			al_progresar=self._al_progresar,
			nombre="descargar actualización",
		)
		self._habilitar()
		self.boton_cerrar.SetFocus()  # «Cancelar»: el único botón útil mientras se descarga

	def _al_progresar(self, progreso: tareas.Progreso) -> None:
		"""Barra siempre; texto cada 10 %; voz solo en los cambios de fase y en los hitos."""
		if not self:
			return
		porcentaje = progreso.porcentaje or 0
		self.barra.SetValue(porcentaje)
		fase = progreso.texto
		if fase != self._fase:
			self._fase = fase
			self._decena = -1
			self._hitos.reiniciar()
			nombres = {
				"verificacion": _("Verificando el paquete..."),
				"extraccion": _("Descomprimiendo..."),
				"preparacion": _("Preparando la instalación..."),
			}
			if fase in nombres:
				self._poner_estado(nombres[fase], decir=True)
		if fase != "descarga":
			return
		hito = self._hitos.nuevo_hito(porcentaje)
		decena = porcentaje // 10 * 10
		if hito is None and decena <= self._decena:
			return
		self._decena = decena
		texto = _("Descargando: {porcentaje} % ({hecho} de {total}).").format(
			porcentaje=hito if hito is not None else decena, hecho=_megas(int(progreso.hecho)), total=_megas(int(progreso.total or 0))
		)
		self._poner_estado(texto, decir=hito is not None)

	def _al_preparada(self, ruta_bat: Path) -> None:
		if not self:
			return
		self._tarea = None
		self.barra.SetValue(100)
		self._habilitar()
		if not self._reproductores_cerrados():
			return
		try:
			actualizador.lanzar_sustitucion(ruta_bat)
		except OSError:
			log.exception("No se pudo lanzar el script de sustitución")
			self._poner_estado(
				_("No se ha podido iniciar la instalación de la actualización. Los detalles están en el registro."), decir=True
			)
			self.estado.SetFocus()
			return
		self._poner_estado(_("Actualización lista. La aplicación se cerrará y volverá a abrirse sola en unos segundos."), decir=True)
		self._terminar(RESULTADO_ACTUALIZAR, wx.ID_OK)
		# Un momento de margen para que el lector de pantalla diga el aviso.
		wx.CallLater(1500, self._al_cerrar_app)

	# ── Saltar y cerrar ──────────────────────────────────────────────────────

	def saltar(self) -> None:
		"""No volver a ofrecer esta versión en la comprobación automática."""
		if self.info is None or self.trabajando():
			return
		actualizador.saltar_version(self.info.version)
		self._terminar(RESULTADO_SALTADA, wx.ID_CANCEL)

	def cancelar_trabajo(self) -> None:
		"""Pide cancelar la comprobación o la descarga en curso."""
		if self._tarea is not None and self.trabajando():
			self._tarea.cancelar()
			self._poner_estado(_("Cancelando..."), decir=True)

	def _al_boton_cerrar(self, _evento: wx.CommandEvent) -> None:
		if self.trabajando():
			self.cancelar_trabajo()
			return
		self._terminar(RESULTADO_CERRADO, wx.ID_CANCEL)

	def _al_cerrar(self, evento: wx.CloseEvent) -> None:
		if self.trabajando():
			self.cancelar_trabajo()
			if evento.CanVeto():
				evento.Veto()
				return
		self._terminar(RESULTADO_CERRADO, wx.ID_CANCEL)

	def _terminar(self, resultado: str, codigo: int) -> None:
		self.resultado = resultado
		if self.IsModal():
			self.EndModal(codigo)
		else:
			self.SetReturnCode(codigo)
			self.Hide()


def mostrar_dialogo_actualizacion(
	padre: wx.Window | None,
	comprobar_al_abrir: bool = True,
	info: actualizador.InfoActualizacion | None = None,
	config: actualizador.Configuracion | None = None,
) -> str:
	"""Abre el diálogo de actualizaciones (menú Ayuda) y devuelve su resultado.

	Abrirlo desde el menú es una acción explícita del usuario: por eso busca
	enseguida la versión nueva, salvo que ya se le pase (``info``).

	:return: ``"cerrado"``, ``"saltada"`` o ``"actualizar"`` (la aplicación va a cerrarse).
	"""
	dialogo = DialogoActualizacion(padre, config=config, info=info)
	try:
		wx.CallAfter(dialogo.enfocar_inicial)
		if comprobar_al_abrir and info is None:
			wx.CallAfter(dialogo.comprobar)
		dialogo.ShowModal()
		return dialogo.resultado
	finally:
		dialogo.Destroy()


# ════════════════════════════════════════════════════════════════════════════
# Arranque
# ════════════════════════════════════════════════════════════════════════════


def comprobar_en_segundo_plano(
	ventana: wx.Window | None,
	config: actualizador.Configuracion | None = None,
	gestor: tareas.GestorTareas | None = None,
	al_encontrar: Callable[[actualizador.InfoActualizacion], Any] | None = None,
) -> tareas.Tarea | None:
	"""Comprobación automática y silenciosa: solo molesta si hay una versión nueva.

	Respeta la versión saltada y no informa de los fallos de red (no se
	molesta a nadie por no tener conexión): quedan en el registro.
	"""
	config = config or actualizador.configuracion_por_defecto()

	def encontrada(info: actualizador.InfoActualizacion | None) -> None:
		if info is None or (ventana is not None and not ventana):
			return
		if al_encontrar is not None:
			al_encontrar(info)
			return
		_decir(_("Hay una versión nueva de {aplicacion}: {version}.").format(aplicacion=NOMBRE_APLICACION, version=info.version))
		mostrar_dialogo_actualizacion(ventana, comprobar_al_abrir=False, info=info, config=config)

	def fallida(error: BaseException) -> None:
		if isinstance(error, (actualizador.ErrorActualizacion, tareas.ErrorTarea)):
			log.info("Comprobación automática de actualizaciones sin éxito: %s", error)
		else:
			log.error("Fallo inesperado en la comprobación automática", exc_info=error)

	return (gestor or gestor_de_red()).enviar(
		lambda tarea: actualizador.comprobar(config, respetar_saltada=True, cancelacion=tarea.token),
		al_terminar=encontrada,
		al_fallar=fallida,
		clave_unica="actualizaciones:automatica",
		nombre="comprobación automática de actualizaciones",
	)


def al_arrancar(
	ventana: wx.Window,
	config: actualizador.Configuracion | None = None,
	gestor: tareas.GestorTareas | None = None,
	al_haber_permiso: Callable[[], Any] | None = None,
) -> None:
	"""Llamar una vez, justo después de mostrar la ventana principal del Estudio.

	1. Si la actualización anterior no salió bien, lo explica.
	2. Pasados unos segundos confirma el arranque: marcador de salud (si se
	   arrancó con ``--tras-actualizar``) y versión confirmada.
	3. La primera vez PREGUNTA si se quiere comprobar al arrancar. Sin un sí
	   expreso no se hace ninguna conexión.
	4. Con permiso, y como mucho una vez al día, busca la versión nueva en
	   segundo plano y llama a ``al_haber_permiso`` (para que quien integre
	   mire también el catálogo de complementos).
	"""
	config = config or actualizador.configuracion_por_defecto()
	tras_actualizar = actualizador.ARGUMENTO_TRAS_ACTUALIZAR in sys.argv
	try:
		mensaje = actualizador.leer_resultado_anterior(config)
	except Exception:  # noqa: BLE001 - un resto ilegible de otra actualización no debe impedir arrancar
		log.exception("No se pudo leer el resultado de la actualización anterior")
		mensaje = None

	def confirmar_arranque() -> None:
		actualizador.confirmar_arranque(config, tras_actualizar)
		if tras_actualizar:
			_decir(
				_("{aplicacion} se ha actualizado a la versión {version}.").format(
					aplicacion=NOMBRE_APLICACION, version=config.version_actual
				)
			)

	def despues_de_mostrar() -> None:
		if not ventana:
			return
		if mensaje:
			mostrar_mensaje(ventana, mensaje, _("Actualización"), wx.ICON_WARNING)
		if actualizador.debe_preguntar():
			preguntar_permiso(ventana)
		if actualizador.toca_comprobar():
			comprobar_en_segundo_plano(ventana, config, gestor)
			if al_haber_permiso is not None:
				al_haber_permiso()

	wx.CallLater(actualizador.RETRASO_CONFIRMACION * 1000, confirmar_arranque)
	wx.CallAfter(despues_de_mostrar)
