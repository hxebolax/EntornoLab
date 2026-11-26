"""Piezas de interfaz comunes a las ventanas del seguimiento.

Todas siguen las reglas de accesibilidad del proyecto (``app/ui/accesibilidad``):
la etiqueta se crea justo antes de su control y con el mismo padre, cada
control tiene letra de acceso sin repetir, los textos largos van en campos de
solo lectura y nada de lo que se actualiza solo roba el foco.
"""

from __future__ import annotations

import logging
import threading
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

import wx

from app.core.i18n import _
from app.ui.accesibilidad.casillas import CheckListBoxAccesible
from app.ui.accesibilidad.ayuda import asegurar_ayudas, describir_control_enfocado
from app.ui.accesibilidad.composicion import PreferenciasLectura
from app.ui.accesibilidad.dialogos import crear_botonera, desplegable_abierto, enfocar, mostrar_error, preparar_dialogo
from app.ui.accesibilidad.lista import ListaAccesible
from app.ui.accesibilidad.nombres import nombre_limpio
from app.ui.accesibilidad.teclado import instalar_atajos
from app.ui.seguimiento.textos import Letras, letra_de

log = logging.getLogger(__name__)

#: Las pruebas lo ponen a False para construir las ventanas sin mostrarlas.
mostrar_al_abrir = True

Problema = tuple[str, wx.Window | None]


# ── Preferencias de lectura de listas ────────────────────────────────────────


def lector_de_preferencias(configuracion: Any) -> Callable[[], PreferenciasLectura]:
	"""Función que lee, en cada anuncio, cómo quiere el usuario que se lean las columnas."""

	def leer() -> PreferenciasLectura:
		if configuracion is None:
			return PreferenciasLectura()
		try:
			cabeceras = bool(configuracion.obtener("accesibilidad.leer_cabeceras", True))
		except KeyError, TypeError, ValueError:
			log.debug("No se ha podido leer accesibilidad.leer_cabeceras", exc_info=True)
			cabeceras = True
		return PreferenciasLectura(numero_fila=False, cabecera=cabeceras, contenido=True)

	return leer


# ── Creación de controles ────────────────────────────────────────────────────


def crear_lista(
	padre: wx.Window,
	etiqueta: str,
	columnas: Sequence[tuple[str, int]],
	configuracion: Any = None,
	ayuda: str = "",
	sizer: wx.Sizer | None = None,
	proporcion: int = 1,
	alto: int = 160,
	**opciones: Any,
) -> ListaAccesible:
	"""Etiqueta y, justo después, una ``ListaAccesible`` en modo informe."""
	texto = wx.StaticText(padre, label=etiqueta)
	lista = ListaAccesible(padre, nombre_limpio(etiqueta), columnas, leer_preferencias=lector_de_preferencias(configuracion), **opciones)
	lista.SetMinSize(wx.Size(-1, alto))
	if ayuda:
		lista.SetHelpText(ayuda)
	if sizer is not None:
		sizer.Add(texto, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		sizer.Add(lista, proporcion, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
	return lista


def crear_texto(
	padre: wx.Window,
	etiqueta: str,
	valor: str = "",
	ayuda: str = "",
	sizer: wx.Sizer | None = None,
	multilinea: bool = False,
	lectura: bool = False,
	contrasena: bool = False,
	alto: int = 90,
	ancho: int = 360,
	proporcion: int = 0,
) -> wx.TextCtrl:
	"""Etiqueta y, justo después, un campo de texto (editable, de solo lectura o de contraseña)."""
	texto = wx.StaticText(padre, label=etiqueta)
	estilo = 0
	if multilinea:
		estilo |= wx.TE_MULTILINE | wx.TE_WORDWRAP
	if lectura:
		estilo |= wx.TE_READONLY
	if contrasena:
		estilo |= wx.TE_PASSWORD
	campo = wx.TextCtrl(padre, value=valor, style=estilo, size=wx.Size(ancho, alto if multilinea else -1), name=nombre_limpio(etiqueta))
	if ayuda:
		campo.SetHelpText(ayuda)
	if sizer is not None:
		sizer.Add(texto, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		sizer.Add(campo, proporcion, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
	return campo


def crear_desplegable(
	padre: wx.Window,
	etiqueta: str,
	opciones: Sequence[str] = (),
	ayuda: str = "",
	sizer: wx.Sizer | None = None,
	seleccion: int = 0,
) -> wx.Choice:
	"""Etiqueta y, justo después, un ``wx.Choice`` nativo."""
	texto = wx.StaticText(padre, label=etiqueta)
	control = wx.Choice(padre, choices=list(opciones), name=nombre_limpio(etiqueta))
	if opciones:
		control.SetSelection(max(0, min(seleccion, len(opciones) - 1)))
	if ayuda:
		control.SetHelpText(ayuda)
	if sizer is not None:
		sizer.Add(texto, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		sizer.Add(control, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
	return control


def crear_boton(padre: wx.Window, etiqueta: str, accion: Callable[[], Any], ayuda: str = "", sizer: wx.Sizer | None = None) -> wx.Button:
	"""Botón con su acción y su ayuda para Ctrl+H."""
	boton = wx.Button(padre, label=etiqueta)
	if ayuda:
		boton.SetHelpText(ayuda)
	boton.Bind(wx.EVT_BUTTON, lambda _evento: accion())
	if sizer is not None:
		sizer.Add(boton, 0, wx.ALL, 4)
	return boton


def crear_casilla(padre: wx.Window, etiqueta: str, valor: bool = False, ayuda: str = "", sizer: wx.Sizer | None = None) -> wx.CheckBox:
	"""Casilla de verificación con su ayuda."""
	casilla = wx.CheckBox(padre, label=etiqueta)
	casilla.SetValue(bool(valor))
	if ayuda:
		casilla.SetHelpText(ayuda)
	if sizer is not None:
		sizer.Add(casilla, 0, wx.ALL, 5)
	return casilla


def crear_casillas(
	padre: wx.Window,
	etiqueta: str,
	opciones: Sequence[str] = (),
	ayuda: str = "",
	sizer: wx.Sizer | None = None,
	alto: int = 110,
	proporcion: int = 0,
) -> CheckListBoxAccesible:
	"""Etiqueta y, justo después, una lista de casillas cuyo estado anuncia el lector."""
	texto = wx.StaticText(padre, label=etiqueta)
	lista = CheckListBoxAccesible(padre, nombre_limpio(etiqueta), opciones, recordar_posicion=False, size=wx.Size(-1, alto))
	if ayuda:
		lista.SetHelpText(ayuda + " " + _("Marque o desmarque con la barra espaciadora; Control+A marca todas."))
	if opciones:
		lista.SetSelection(0)
	if sizer is not None:
		sizer.Add(texto, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		sizer.Add(lista, proporcion, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
	return lista


def poner_opciones(control: wx.Choice, opciones: Sequence[str], seleccion: int = 0) -> None:
	"""Cambia las opciones de un desplegable solo si son otras, conservando lo elegido si se puede."""
	if list(control.GetStrings()) == list(opciones):
		return
	control.Set(list(opciones))
	if opciones:
		control.SetSelection(max(0, min(seleccion, len(opciones) - 1)))


def poner_texto(campo: wx.TextCtrl, texto: str) -> bool:
	"""Cambia el contenido de un campo de solo lectura sin molestar a quien lo lee.

	No escribe si el texto es el mismo (un lector puede releer el campo al
	cambiarlo) y conserva la posición del cursor. Devuelve True si cambió.
	"""
	actual = campo.GetValue().replace("\r\n", "\n")
	if actual == texto:
		return False
	posicion = campo.GetInsertionPoint()
	campo.ChangeValue(texto)
	campo.SetInsertionPoint(min(posicion, campo.GetLastPosition()))
	return True


def anadir_linea(campo: wx.TextCtrl, linea: str) -> None:
	"""Añade una línea al final de un historial sin mover el cursor de quien está leyendo más arriba.

	Si el cursor estaba al final, sigue al final (se va leyendo lo nuevo); si
	estaba más arriba, se queda donde estaba, tenga o no el foco el campo: al
	volver a él se retoma la lectura en el mismo punto.
	"""
	posicion = campo.GetInsertionPoint()
	leyendo = posicion < campo.GetLastPosition()
	campo.AppendText(linea + "\n")
	if leyendo:
		campo.SetInsertionPoint(posicion)


def letras_de_menus(ventana: Any) -> set[str]:
	"""Letras de acceso de los menús de la barra de ``ventana`` (un panel suyo no puede repetirlas)."""
	letras: set[str] = set()
	barra = ventana.GetMenuBar() if isinstance(ventana, wx.Frame) else None
	if barra is not None:
		for indice in range(barra.GetMenuCount()):
			letra = letra_de(barra.GetMenuLabel(indice))
			if letra:
				letras.add(letra)
	return letras


# ── Diálogos ─────────────────────────────────────────────────────────────────


def cerrar_dialogo(dialogo: wx.Dialog, codigo: int) -> None:
	"""Cierra un diálogo con ``codigo`` tanto si se mostró modal como si no (pruebas)."""
	if dialogo.IsModal():
		dialogo.EndModal(codigo)
	else:
		dialogo.SetReturnCode(codigo)
		dialogo.Hide()


def mostrar_modal(dialogo: wx.Dialog) -> int:
	"""Muestra un diálogo modal y devuelve el foco a donde estaba. No lo destruye: quien llama lee sus valores."""
	foco_previo = wx.Window.FindFocus()
	try:
		return dialogo.ShowModal()
	finally:
		if foco_previo:
			foco_previo.SetFocus()


class DialogoFormulario(wx.Dialog):
	"""Base de los diálogos con campos: validación al aceptar y foco en el campo que hay que corregir.

	Las clases hijas crean sus controles sobre ``self.panel`` añadiéndolos a
	``self.sizer`` (con ``self.letras`` para las letras de acceso), llaman a
	``terminar`` y redefinen ``validar`` y ``aplicar``. Las dos devuelven
	``None`` si todo va bien o ``(mensaje, control)`` si hay algo que corregir.
	"""

	def __init__(self, padre: wx.Window | None, titulo: str) -> None:
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name=titulo)
		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		# Letras de Aceptar, Cancelar y Cerrar (A, C y E en español; O, C y L en
		# inglés): se toman de las etiquetas traducidas de la botonera.
		self.letras = Letras({letra_de(_(etiqueta)) for etiqueta in ("&Aceptar", "&Cancelar", "C&errar")})
		self.aceptado = False

	def terminar(
		self,
		foco: wx.Window | None,
		botones: int = wx.OK | wx.CANCEL,
		etiqueta_aceptar: str = "",
		predeterminado: int | None = None,
		tamano_minimo: tuple[int, int] | None = None,
	) -> None:
		"""Añade la botonera, ajusta el tamaño y prepara Escape, Ctrl+H y el foco inicial."""
		botonera = crear_botonera(self.panel, botones, predeterminado)
		self.sizer.Add(botonera, 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		aceptar = self.FindWindow(wx.ID_OK)
		if aceptar is not None:
			if etiqueta_aceptar:
				aceptar.SetLabel(etiqueta_aceptar)
			aceptar.Bind(wx.EVT_BUTTON, lambda _evento: self.aceptar())
		cerrar = self.FindWindow(wx.ID_CLOSE)
		if cerrar is not None:
			cerrar.Bind(wx.EVT_BUTTON, lambda _evento: cerrar_dialogo(self, wx.ID_CLOSE))
		self.panel.SetSizer(self.sizer)
		marco = wx.BoxSizer(wx.VERTICAL)
		marco.Add(self.panel, 1, wx.EXPAND)
		self.SetSizerAndFit(marco)
		if tamano_minimo is not None:
			self.SetMinSize(wx.Size(*tamano_minimo))
			self.SetSize(wx.Size(max(self.GetSize().width, tamano_minimo[0]), max(self.GetSize().height, tamano_minimo[1])))
		id_escape = wx.ID_CANCEL if botones & wx.CANCEL else (wx.ID_CLOSE if botones & wx.CLOSE else wx.ID_OK)
		preparar_dialogo(self, id_escape=id_escape, foco_inicial=foco)
		self.CentreOnParent()

	def validar(self) -> Problema | None:
		"""Comprueba lo escrito. ``None`` si es válido; si no, el mensaje y el control que hay que corregir."""
		return None

	def aplicar(self) -> Problema | None:
		"""Hace lo que el diálogo acepta. ``None`` si salió bien; si no, el mensaje y el control."""
		return None

	def aceptar(self) -> bool:
		"""Valida, aplica y cierra. Si algo falla lo dice y deja el foco en el campo que hay que corregir."""
		problema = self.validar() or self.aplicar()
		if problema is not None:
			mensaje, control = problema
			mostrar_error(self, mensaje)
			if control is not None:
				self.ir_a(control)
			return False
		self.aceptado = True
		cerrar_dialogo(self, wx.ID_OK)
		return True

	def ir_a(self, control: wx.Window) -> None:
		"""Lleva el foco a ``control`` (las clases con pestañas cambian antes de página)."""
		enfocar(control)


class DialogoLectura(DialogoFormulario):
	"""Un texto largo en un campo de solo lectura, con un botón «Cerrar»."""

	def __init__(self, padre: wx.Window | None, titulo: str, etiqueta: str, texto: str) -> None:
		super().__init__(padre, titulo)
		self.campo = crear_texto(
			self.panel,
			self.letras.poner(etiqueta),
			texto,
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=320,
			ancho=620,
			proporcion=1,
			ayuda=_("Texto de solo lectura. Recórralo con las flechas; puede seleccionarlo y copiarlo."),
		)
		self.terminar(self.campo, botones=wx.CLOSE)


def mostrar_texto(padre: wx.Window | None, titulo: str, etiqueta: str, texto: str) -> None:
	"""Muestra un texto largo para leerlo con calma y copiarlo."""
	dialogo = DialogoLectura(padre, titulo, etiqueta, texto)
	try:
		mostrar_modal(dialogo)
	finally:
		dialogo.Destroy()


def pedir_ruta_guardar(padre: wx.Window | None, titulo: str, comodin: str, nombre: str = "") -> Path | None:
	"""Cuadro nativo de «Guardar como». ``None`` si se cancela."""
	dialogo = wx.FileDialog(padre, titulo, defaultFile=nombre, wildcard=comodin, style=wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT)
	try:
		if dialogo.ShowModal() != wx.ID_OK:
			return None
		return Path(dialogo.GetPath())
	finally:
		dialogo.Destroy()


def pedir_ruta_abrir(padre: wx.Window | None, titulo: str, comodin: str) -> Path | None:
	"""Cuadro nativo de «Abrir». ``None`` si se cancela."""
	dialogo = wx.FileDialog(padre, titulo, wildcard=comodin, style=wx.FD_OPEN | wx.FD_FILE_MUST_EXIST)
	try:
		if dialogo.ShowModal() != wx.ID_OK:
			return None
		return Path(dialogo.GetPath())
	finally:
		dialogo.Destroy()


# ── Ventanas no modales ──────────────────────────────────────────────────────


class VentanaSeguimiento(wx.Frame):
	"""Base de las ventanas no modales del seguimiento (alumnos, supervisión, sesiones...).

	No son diálogos modales para que el profesional pueda tener la
	supervisión abierta mientras consulta una ficha o edita el entorno.
	"""

	CLAVE = ""

	def __init__(self, contexto: Any, servicio: Any, titulo: str, tamano: tuple[int, int] = (900, 640)) -> None:
		padre = getattr(contexto, "ventana", None)
		super().__init__(padre if isinstance(padre, wx.Window) else None, title=titulo, size=wx.Size(*tamano), name=titulo)
		self.contexto = contexto
		self.servicio = servicio
		self.panel = wx.Panel(self)
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.letras = Letras()
		self.teclas_propias: list[str] = ["Escape"]
		self._foco_inicial: wx.Window | None = None
		self.Bind(wx.EVT_CLOSE, self._al_cerrar)

	def fila_botones(self) -> wx.BoxSizer:
		"""Fila horizontal para botones, ya añadida a la ventana."""
		fila = wx.WrapSizer(wx.HORIZONTAL)
		self.sizer.Add(fila, 0, wx.EXPAND | wx.ALL, 2)
		return fila

	def terminar(self, foco: wx.Window | None, atajos: Sequence[tuple[int, int, Callable[[], None]]] = ()) -> None:
		"""Coloca el contenido y prepara Ctrl+H, Escape, los atajos y el foco inicial."""
		self.panel.SetSizer(self.sizer)
		marco = wx.BoxSizer(wx.VERTICAL)
		marco.Add(self.panel, 1, wx.EXPAND)
		self.SetSizer(marco)
		if atajos:
			instalar_atajos(self, atajos)
		asegurar_ayudas(self)
		self._foco_inicial = foco
		self.Bind(wx.EVT_CHAR_HOOK, self._al_pulsar)
		self.CentreOnParent()

	def _al_pulsar(self, evento: wx.KeyEvent) -> None:
		tecla, modificadores = evento.GetKeyCode(), evento.GetModifiers()
		if modificadores == wx.MOD_CONTROL and tecla == ord("H"):
			describir_control_enfocado(self)
			return
		if tecla == wx.WXK_ESCAPE and modificadores == wx.MOD_NONE:  # atajo: Escape
			if desplegable_abierto(wx.Window.FindFocus()):
				evento.Skip()
				return
			self.Close()
			return
		evento.Skip()

	def mostrar(self) -> None:
		"""Enseña la ventana y pone el foco inicial (no hace nada visible en las pruebas)."""
		if not mostrar_al_abrir:
			return
		self.Show()
		self.Raise()
		if self._foco_inicial is not None:
			wx.CallAfter(self._enfocar_inicial)

	def _enfocar_inicial(self) -> None:
		if self and self._foco_inicial:
			enfocar(self._foco_inicial)

	def puede_cerrar(self) -> bool:
		"""Las ventanas con algo pendiente (la sala abierta) preguntan aquí antes de cerrarse."""
		return True

	def al_cerrar(self) -> None:
		"""Limpieza propia de cada ventana (parar temporizadores, cancelar suscripciones)."""

	def _al_cerrar(self, evento: wx.CloseEvent) -> None:
		if evento.CanVeto() and not self.puede_cerrar():
			evento.Veto()
			return
		self.al_cerrar()
		if self.servicio is not None and self.servicio.ventanas.get(self.CLAVE) is self:
			del self.servicio.ventanas[self.CLAVE]
		evento.Skip()


def abrir_ventana(servicio: Any, clave: str, fabrica: Callable[[], VentanaSeguimiento]) -> VentanaSeguimiento:
	"""Trae al frente la ventana ``clave`` si ya está abierta; si no, la crea y la muestra."""
	existente = servicio.ventanas.get(clave)
	if existente:
		existente.mostrar()
		return existente
	ventana = fabrica()
	servicio.ventanas[clave] = ventana
	ventana.mostrar()
	return ventana


# ── Temporizador ─────────────────────────────────────────────────────────────


class Reloj(wx.Timer):
	"""Temporizador que llama a una función mientras su ventana siga viva.

	No pertenece a la ventana (no le envía eventos): si la ventana se
	destruye con el temporizador en marcha, el siguiente tic lo nota y se
	para solo. Así no hace falta atender la destrucción de la ventana, que es
	un momento delicado para ejecutar código de Python.
	"""

	def __init__(self, ventana: wx.Window, funcion: Callable[[], Any]) -> None:
		super().__init__()
		self._ventana = ventana
		self._funcion = funcion

	def Notify(self) -> None:  # noqa: N802 - API de wx
		if not self._ventana:
			self.Stop()
			return
		self._funcion()


# ── Trabajo en segundo plano ─────────────────────────────────────────────────


def en_segundo_plano(
	funcion: Callable[[], Any],
	al_terminar: Callable[[Any], None],
	al_fallar: Callable[[BaseException], None],
) -> threading.Thread:
	"""Ejecuta ``funcion`` en un hilo y entrega el resultado en el hilo de la interfaz.

	Para lo poco que aquí puede tardar (abrir la sala en red crea un
	certificado la primera vez): la ventana sigue respondiendo y el lector no
	se queda mudo.
	"""

	def trabajo() -> None:
		try:
			resultado = funcion()
		except Exception as error:  # noqa: BLE001 - se entrega a la interfaz, que es quien sabe mostrarlo
			log.info("Una operación en segundo plano ha fallado: %s", type(error).__name__)
			wx.CallAfter(al_fallar, error)
			return
		wx.CallAfter(al_terminar, resultado)

	hilo = threading.Thread(target=trabajo, name="seguimiento-fondo", daemon=True)
	hilo.start()
	return hilo
