"""Diálogos del menú Herramientas y de «Buscar elemento»: comprobar, medir, amueblar y buscar.

Todos siguen el mismo patrón accesible: una lista nativa con su etiqueta
delante (``ListaAccesible``, que lee las columnas una a una), el resultado en
un campo de solo lectura que se puede repasar y copiar, botones en español
que dicen la acción, Intro que actúa sobre la fila elegida y Escape que cierra.

Cada clase de diálogo expone métodos con nombre (``ir``, ``aceptar``,
``medir``…) para poder manejarla desde las pruebas sin un ``ShowModal`` real.
"""

from __future__ import annotations

import logging
from typing import Any

import wx

from app.core.i18n import N_, _, _n
from app.core.tareas import TareaCancelada
from app.dominio import colocacion, edicion, validacion
from app.dominio.edicion import ErrorEdicion
from app.dominio.modelo import Aviso, Entorno, Espacio
from app.dominio.validacion import resumen
from app.ui import espera, operaciones
from app.ui.accesibilidad.dialogos import crear_botonera, enfocar, mostrar_error, mostrar_mensaje, preparar_dialogo
from app.ui.accesibilidad.lista import ListaAccesible
from app.ui.accesibilidad.nombres import crear_campo
from app.ui.dialogo_progreso import informar
from app.ui.esquemas import c
from app.ui.esquemas_elementos import espacios, plantas
from app.ui.formulario import mostrar_dialogo, pedir_formulario

log = logging.getLogger(__name__)


def usos() -> list[tuple[str, str]]:
	"""Usos con los que se sabe amueblar un espacio, ya traducidos, en el orden en que los declara el dominio.

	Se toman de ``colocacion.NOMBRES_USOS`` (y no de una lista propia) para
	que cada uso nuevo del catálogo salga en «Amueblar espacio» sin tocar la interfaz.
	"""
	return [(clave, _(nombre)) for clave, nombre in colocacion.NOMBRES_USOS.items()]


def _sin_entorno(contexto: Any, titulo: str) -> bool:
	if contexto.entorno is not None:
		return False
	mostrar_mensaje(contexto.ventana, _("No hay ningún entorno abierto."), titulo)
	return True


# ── Comprobar el entorno ─────────────────────────────────────────────────────


def _validar_una_actividad(validar: Any, actividad: dict[str, Any], contexto: Any) -> list[Any]:
	"""Avisos de una actividad, pasándole los recursos del paquete para que compruebe los audios de los premios.

	Si la función de validación instalada es de antes del parámetro
	``recursos`` (una versión de reserva), se llama sin él: se pierde solo esa
	comprobación.
	"""
	recursos = list(getattr(contexto, "recursos", None) or {})
	try:
		return list(validar(actividad, contexto.entorno, contexto.catalogo, recursos=recursos))
	except TypeError as error:
		if "recursos" not in str(error):
			raise
		log.debug("La validación de actividades no admite recursos; se comprueba sin los audios.")
		return list(validar(actividad, contexto.entorno, contexto.catalogo))


def avisos_de_actividades(contexto: Any) -> list[Any]:
	"""Avisos de cada actividad del paquete abierto, con el nombre de la actividad delante.

	Un premio no es un elemento del plano: si el aviso señala algo que no
	existe en el entorno, se le quita el ``elemento_id`` para que «Ir al
	elemento» no prometa llevar a ningún sitio.
	"""
	try:
		from app import actividades as modulo_actividades
	except ImportError:
		log.debug("No hay módulo de actividades: se comprueba solo el entorno.")
		return []
	validar = getattr(modulo_actividades, "validar_actividad", None)
	if not callable(validar):
		return []
	entorno = contexto.entorno
	avisos: list[Any] = []
	for actividad in list(contexto.actividades or []):
		if not isinstance(actividad, dict):
			continue
		try:
			propios = _validar_una_actividad(validar, actividad, contexto)
		except Exception:  # noqa: BLE001 - una actividad que no se puede comprobar no impide comprobar las demás; queda en el registro
			log.exception("No se pudo comprobar la actividad %s", actividad.get("id"))
			continue
		nombre = str(actividad.get("nombre") or actividad.get("id") or "")
		for aviso in propios:
			elemento = (
				aviso.elemento_id
				if aviso.elemento_id and (entorno.buscar(aviso.elemento_id) is not None or entorno.planta(aviso.elemento_id) is not None)
				else ""
			)
			avisos.append(
				Aviso(
					aviso.gravedad,
					aviso.codigo,
					_("Actividad «{actividad}»: {mensaje}").format(actividad=nombre, mensaje=aviso.mensaje),
					elemento,
					aviso.planta_id,
					aviso.sugerencia,
				)
			)
	return avisos


def avisos_del_documento(contexto: Any, tarea: Any = None) -> list[Any]:
	"""Avisos del entorno abierto y de las actividades de su paquete (con sus audios), con los errores primero.

	Con ``tarea`` (la del diálogo de progreso) se informa de cada fase con sus
	cifras: con un barrio importado comprobar tarda segundos.
	"""

	def progreso(fase: str, hecho: int | None, total: int | None) -> None:
		if tarea is not None:
			informar(tarea, fase, hecho, total)

	avisos = list(validacion.validar(contexto.entorno, contexto.catalogo, contexto.paso_libre(), progreso=progreso))
	if tarea is not None:
		informar(tarea, _("Comprobando las actividades"), 0, len(contexto.actividades or []))
	avisos.extend(avisos_de_actividades(contexto))
	return sorted(avisos, key=lambda aviso: 0 if aviso.es_error else 1)


def avisos_con_progreso(contexto: Any) -> list[Any] | None:
	"""Los avisos del documento; con un entorno grande, en segundo plano con el diálogo de progreso. None si se cancela."""
	try:
		return espera.hacer(
			contexto,
			_("Comprobar el entorno"),
			lambda tarea: avisos_del_documento(contexto, tarea),
			_("Comprobando el entorno: {n} elementos").format(n=espera.tamano(contexto.entorno)),
		)
	except TareaCancelada:
		contexto.anunciar(_("Comprobación cancelada."))
		return None


def _lugar_de(entorno: Entorno, aviso: Any) -> str:
	"""Dónde está el problema, en palabras: el nombre del elemento y de su planta."""
	partes: list[str] = []
	if aviso.elemento_id:
		elemento = entorno.elemento(aviso.elemento_id)
		if elemento is not None:
			partes.append(operaciones.nombre_de(elemento))
	if aviso.planta_id:
		planta = entorno.planta(aviso.planta_id)
		if planta is not None:
			partes.append(operaciones.nombre_de(planta))
	return ", ".join(partes)


class DialogoComprobar(wx.Dialog):
	"""Lista de problemas del entorno: gravedad, mensaje, sugerencia y lugar. Intro lleva al elemento."""

	def __init__(self, padre: wx.Window | None, contexto: Any, avisos: list[Any] | None = None) -> None:
		"""``avisos``: los ya calculados (en segundo plano si el entorno es grande); sin ellos se comprueba al abrir."""
		super().__init__(
			padre, title=_("Comprobar el entorno"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name=_("Comprobar el entorno")
		)
		self.contexto = contexto
		self.avisos: list[Any] = []
		self._iniciales = avisos
		#: Id del elemento al que la persona pidió ir (vacío si solo cerró).
		self.elegido = ""
		sizer = wx.BoxSizer(wx.VERTICAL)
		_e, self.resumen = crear_campo(
			self, _("&Resultado:"), wx.TextCtrl, style=wx.TE_READONLY, ayuda=_("Cuántos errores y avisos se han encontrado."), sizer=sizer
		)
		etiqueta = wx.StaticText(self, label=_("&Problemas encontrados:"))
		self.lista = ListaAccesible(
			self,
			_("Problemas encontrados"),
			[
				(_("Gravedad"), self.FromDIP(80)),
				(_("Problema"), self.FromDIP(330)),
				(_("Sugerencia"), self.FromDIP(300)),
				(_("Dónde"), self.FromDIP(180)),
			],
		)
		self.lista.SetHelpText(
			_(
				"Un problema por fila. Izquierda y derecha leen la gravedad, el problema, la sugerencia y el lugar. Intro cierra y lleva al elemento."
			)
		)
		self.lista.SetMinSize(self.FromDIP(wx.Size(720, 260)))
		sizer.Add(etiqueta, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		sizer.Add(self.lista, 1, wx.EXPAND | wx.ALL, 5)
		botones = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_ir = wx.Button(self, label=_("&Ir al elemento"))
		self.boton_ir.SetHelpText(_("Cierra esta ventana y selecciona en el árbol el elemento del problema elegido."))
		self.boton_repetir = wx.Button(self, label=_("&Volver a comprobar"))
		self.boton_repetir.SetHelpText(_("Revisa otra vez el entorno."))
		boton_cerrar = wx.Button(self, wx.ID_CANCEL, _("C&errar"))
		for boton in (self.boton_ir, self.boton_repetir, boton_cerrar):
			botones.Add(boton, 0, wx.ALL, 5)
		sizer.Add(botones, 0, wx.ALIGN_RIGHT)
		self.SetSizerAndFit(sizer)
		self.boton_ir.Bind(wx.EVT_BUTTON, lambda _evento: self.ir())
		self.boton_repetir.Bind(wx.EVT_BUTTON, lambda _evento: self.comprobar(anunciar=True))
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.ir())
		self.boton_ir.SetDefault()
		self.comprobar(avisos=self._iniciales)
		preparar_dialogo(self, foco_inicial=self.lista if self.avisos else self.resumen)
		self.CentreOnParent()

	def comprobar(self, anunciar: bool = False, avisos: list[Any] | None = None) -> None:
		"""Valida el entorno (o toma ``avisos`` ya calculados) y rellena la lista."""
		if avisos is None:
			avisos = avisos_con_progreso(self.contexto)
			if avisos is None:
				return
		self.avisos = avisos
		entorno = self.contexto.entorno
		filas = [
			(_("Error") if aviso.es_error else _("Aviso"), aviso.mensaje, aviso.sugerencia, _lugar_de(entorno, aviso))
			for aviso in self.avisos
		]
		self.lista.reemplazar_filas(filas, conservar_foco=False)
		texto = resumen(self.avisos)
		self.resumen.ChangeValue(texto)
		self.boton_ir.Enable(bool(self.avisos))
		if self.avisos:
			self.lista.enfocar_fila(0, anunciar=False)
		if anunciar:
			self.contexto.anunciar(texto)

	def ir(self) -> bool:
		"""Cierra y deja en ``elegido`` el elemento del problema enfocado. False si ese problema no señala ninguno."""
		fila = self.lista.fila_actual()
		if not 0 <= fila < len(self.avisos):
			return False
		aviso = self.avisos[fila]
		destino = aviso.elemento_id or aviso.planta_id
		if not destino:
			self.contexto.anunciar(_("Este problema no señala ningún elemento del plano: es del entorno entero o de una actividad."))
			return False
		self.elegido = destino
		if self.IsModal():
			self.EndModal(wx.ID_OK)
		return True


def comprobar_entorno(contexto: Any) -> str:
	"""Abre «Comprobar el entorno». Devuelve el id del elemento al que ir (también lo selecciona), o «»."""
	if _sin_entorno(contexto, _("Comprobar el entorno")):
		return ""
	avisos = avisos_con_progreso(contexto)
	if avisos is None:
		return ""
	dialogo = DialogoComprobar(contexto.ventana, contexto, avisos)
	contexto.anunciar(dialogo.resumen.GetValue())
	elegido = ""
	try:
		dialogo.ShowModal()
		elegido = dialogo.elegido
	finally:
		dialogo.Destroy()
	if elegido and (contexto.entorno.buscar(elegido) is not None or contexto.entorno.planta(elegido) is not None):
		contexto.seleccionar(elegido)
	return elegido


# ── Medir ────────────────────────────────────────────────────────────────────


def _elementos_medibles(contexto: Any) -> list[tuple[str, str]]:
	"""Elementos entre los que se puede medir: (id, «nombre (tipo), planta»)."""
	return [
		(id_elemento, rotulo)
		for id_elemento, rotulo in operaciones.buscar_elementos(contexto.entorno, "", contexto.catalogo)
		if contexto.entorno.planta(id_elemento) is None
	]


class DialogoMedir(wx.Dialog):
	"""Elige dos elementos y dice la distancia, el rumbo y el hueco libre entre ellos."""

	def __init__(self, padre: wx.Window | None, contexto: Any) -> None:
		super().__init__(
			padre,
			title=_("Medir entre dos elementos"),
			style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER,
			name=_("Medir entre dos elementos"),
		)
		self.contexto = contexto
		self.elementos = _elementos_medibles(contexto)
		rotulos = [rotulo for _id, rotulo in self.elementos]
		sizer = wx.BoxSizer(wx.VERTICAL)
		_e, self.desde = crear_campo(
			self, _("&Desde:"), wx.Choice, choices=rotulos, ayuda=_("El elemento desde el que se mide."), sizer=sizer
		)
		_e, self.hasta = crear_campo(
			self, _("&Hasta:"), wx.Choice, choices=rotulos, ayuda=_("El elemento hasta el que se mide."), sizer=sizer
		)
		_e, self.resultado = crear_campo(
			self,
			_("&Medida:"),
			wx.TextCtrl,
			style=wx.TE_READONLY | wx.TE_MULTILINE,
			size=self.FromDIP(wx.Size(460, 70)),
			ayuda=_("Distancia entre los centros, hacia dónde queda el segundo y hueco libre entre los dos."),
			sizer=sizer,
		)
		botones = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_medir = wx.Button(self, label=_("&Calcular la medida"))
		self.boton_medir.SetHelpText(_("Calcula la medida entre los dos elementos elegidos y la dice."))
		boton_cerrar = wx.Button(self, wx.ID_CANCEL, _("C&errar"))
		botones.Add(self.boton_medir, 0, wx.ALL, 5)
		botones.Add(boton_cerrar, 0, wx.ALL, 5)
		sizer.Add(botones, 0, wx.ALIGN_RIGHT)
		self.SetSizerAndFit(sizer)
		ids = [id_elemento for id_elemento, _rotulo in self.elementos]
		if ids:
			primero = ids.index(contexto.seleccion) if contexto.seleccion in ids else 0
			self.desde.SetSelection(primero)
			self.hasta.SetSelection(1 if primero == 0 and len(ids) > 1 else 0)
		self.boton_medir.Bind(wx.EVT_BUTTON, lambda _evento: self.medir())
		self.boton_medir.SetDefault()
		preparar_dialogo(self, foco_inicial=self.desde)
		self.CentreOnParent()

	def elegir(self, desde: str, hasta: str) -> None:
		"""Elige los dos elementos por su id."""
		ids = [id_elemento for id_elemento, _rotulo in self.elementos]
		self.desde.SetSelection(ids.index(desde))
		self.hasta.SetSelection(ids.index(hasta))

	def medir(self) -> str:
		"""Calcula la medida, la escribe en el campo de resultado y la anuncia. Devuelve la frase."""
		if self.desde.GetSelection() < 0 or self.hasta.GetSelection() < 0:
			return ""
		id_a = self.elementos[self.desde.GetSelection()][0]
		id_b = self.elementos[self.hasta.GetSelection()][0]
		if id_a == id_b:
			frase = _("Elija dos elementos distintos.")
		else:
			try:
				medida = edicion.medir(self.contexto.entorno, id_a, id_b, self.contexto.catalogo)
				frase = _("De {a} a {b}: {medida}.").format(
					a=self.elementos[self.desde.GetSelection()][1], b=self.elementos[self.hasta.GetSelection()][1], medida=medida.texto()
				)
			except ValueError as error:
				frase = str(error)
		self.resultado.ChangeValue(frase)
		self.contexto.anunciar(frase)
		return frase


def medir(contexto: Any) -> None:
	"""Abre «Medir entre dos elementos»."""
	if _sin_entorno(contexto, _("Medir")):
		return
	if len(_elementos_medibles(contexto)) < 2:
		mostrar_mensaje(contexto.ventana, _("Hacen falta al menos dos elementos para medir entre ellos."), _("Medir"))
		return
	mostrar_dialogo(DialogoMedir(contexto.ventana, contexto))


# ── Amueblar un espacio ──────────────────────────────────────────────────────


def proponer_mobiliario(contexto: Any, id_planta: str, id_espacio: str, uso: str) -> list[tuple[str, str, str]]:
	"""Propuesta de mobiliario SIN tocar el entorno abierto: filas (objeto, medidas, dónde queda).

	Se ensaya sobre una copia del entorno. Como el amueblado es determinista,
	al aceptarlo sobre el entorno de verdad sale lo mismo que se enseñó.
	"""
	copia = Entorno.de_dict(contexto.entorno.a_dict())
	planta = copia.planta(id_planta)
	espacio = planta.espacio(id_espacio) if planta is not None else None
	if planta is None or espacio is None:
		raise ErrorEdicion(_("Elija el espacio que quiere amueblar."))
	objetos = colocacion.amueblar_espacio(copia, planta, espacio, uso, contexto.catalogo, contexto.paso_libre(), aplicar=True)
	return [
		(operaciones.nombre_de(objeto), operaciones.texto_medidas(objeto), edicion.describir_elemento(copia, objeto, contexto.catalogo))
		for objeto in objetos
	]


class DialogoPropuesta(wx.Dialog):
	"""Vista previa del amueblado en una lista, con «Aceptar la propuesta» y «Descartar»."""

	def __init__(self, padre: wx.Window | None, titulo: str, filas: list[tuple[str, str, str]]) -> None:
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name=titulo)
		sizer = wx.BoxSizer(wx.VERTICAL)
		etiqueta = wx.StaticText(self, label=_("&Mobiliario propuesto:"))
		self.lista = ListaAccesible(
			self,
			_("Mobiliario propuesto"),
			[(_("Objeto"), self.FromDIP(170)), (_("Medidas"), self.FromDIP(140)), (_("Dónde queda"), self.FromDIP(420))],
		)
		self.lista.SetHelpText(
			_("Un objeto por fila. Izquierda y derecha leen sus medidas y dónde quedaría. Nada se coloca hasta que acepte la propuesta.")
		)
		self.lista.SetMinSize(self.FromDIP(wx.Size(700, 240)))
		self.lista.reemplazar_filas(filas, conservar_foco=False)
		sizer.Add(etiqueta, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		sizer.Add(self.lista, 1, wx.EXPAND | wx.ALL, 5)
		botones = wx.BoxSizer(wx.HORIZONTAL)
		aceptar = wx.Button(self, wx.ID_OK, _("&Aceptar la propuesta"))
		aceptar.SetHelpText(_("Coloca todos los objetos de la lista en el espacio."))
		descartar = wx.Button(self, wx.ID_CANCEL, _("&Descartar"))
		descartar.SetHelpText(_("Cierra sin colocar nada."))
		aceptar.SetDefault()
		botones.Add(aceptar, 0, wx.ALL, 5)
		botones.Add(descartar, 0, wx.ALL, 5)
		sizer.Add(botones, 0, wx.ALIGN_RIGHT)
		self.SetSizerAndFit(sizer)
		preparar_dialogo(self, foco_inicial=self.lista)
		self.CentreOnParent()


def amueblar(contexto: Any) -> int:
	"""Amueblado asistido: pregunta espacio y uso, enseña la propuesta y, si se acepta, la coloca. Devuelve cuántos objetos."""
	titulo = _("Amueblar el espacio")
	if _sin_entorno(contexto, titulo):
		return 0
	if contexto.catalogo is None or contexto.catalogo.vacio:
		mostrar_mensaje(
			contexto.ventana,
			_("No hay complementos de objetos activos. Actívelos o añádalos en Herramientas, Complementos instalados."),
			titulo,
		)
		return 0
	entorno = contexto.entorno
	interiores = [(id_planta, nombre) for id_planta, nombre in plantas(entorno) if espacios(entorno, id_planta, macizos=False)]
	if not interiores:
		mostrar_mensaje(contexto.ventana, _("Primero cree un espacio: Insertar, Habitación por medidas."), titulo)
		return 0
	elegido = contexto.elemento_seleccionado()
	planta_actual = contexto.planta_actual()
	id_planta = planta_actual.id if planta_actual is not None and any(planta_actual.id == p for p, _n2 in interiores) else interiores[0][0]
	lista_espacios = espacios(entorno, id_planta, macizos=False)
	id_espacio = (
		elegido[1].id
		if elegido is not None and isinstance(elegido[1], Espacio) and any(elegido[1].id == e for e, _n2 in lista_espacios)
		else lista_espacios[0][0]
	)
	campos = [
		c("planta", N_("Planta"), "opcion", opciones=interiores, obligatorio=True, recarga=True),
		c("espacio", N_("Espacio"), "opcion", opciones=lambda v: espacios(entorno, v.get("planta"), macizos=False), obligatorio=True),
		c("uso", N_("Amueblarlo como"), "opcion", N_("Decide qué muebles se proponen."), opciones=usos(), obligatorio=True),
	]
	valores = pedir_formulario(
		contexto.ventana,
		titulo,
		campos,
		{"planta": id_planta, "espacio": id_espacio, "uso": "dormitorio"},
		introduccion=_(
			"El programa propone una disposición con los complementos instalados. Antes de colocar nada se enseña la lista para revisarla."
		),
	)
	if valores is None:
		return 0
	try:
		filas = proponer_mobiliario(contexto, valores["planta"], valores["espacio"], valores["uso"])
	except ValueError as error:
		mostrar_error(contexto.ventana, str(error), titulo)
		return 0
	nombre_espacio = operaciones.nombre_de(entorno.elemento(valores["espacio"]))
	if not filas:
		mostrar_mensaje(
			contexto.ventana,
			_("No se ha encontrado ningún mueble que quepa en «{espacio}» sin tapar puertas ni cortar el paso.").format(
				espacio=nombre_espacio
			),
			titulo,
		)
		return 0
	contexto.anunciar(_n("Se propone {n} objeto.", "Se proponen {n} objetos.", len(filas)).format(n=len(filas)))
	if mostrar_dialogo(DialogoPropuesta(contexto.ventana, _("Propuesta para {espacio}").format(espacio=nombre_espacio), filas)) != wx.ID_OK:
		contexto.anunciar(_("Propuesta descartada: no se ha colocado nada."))
		return 0

	def operacion() -> list[Any]:
		planta = contexto.entorno.planta(valores["planta"])
		espacio = planta.espacio(valores["espacio"]) if planta is not None else None
		if planta is None or espacio is None:
			raise ErrorEdicion(_("El espacio ya no existe."))
		return colocacion.amueblar_espacio(
			contexto.entorno, planta, espacio, valores["uso"], contexto.catalogo, contexto.paso_libre(), aplicar=True
		)

	try:
		colocados = contexto.ejecutar(_("amueblar {espacio}").format(espacio=nombre_espacio), operacion)
	except ValueError as error:
		mostrar_error(contexto.ventana, str(error), titulo)
		return 0
	contexto.anunciar(
		_n("Colocado {n} objeto en {espacio}.", "Colocados {n} objetos en {espacio}.", len(colocados)).format(
			n=len(colocados), espacio=nombre_espacio
		)
	)
	return len(colocados)


# ── Buscar un elemento ───────────────────────────────────────────────────────


class DialogoBuscar(wx.Dialog):
	"""Busca elementos por nombre o tipo y lleva al elegido."""

	def __init__(self, padre: wx.Window | None, contexto: Any) -> None:
		super().__init__(padre, title=_("Buscar elemento"), style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name=_("Buscar elemento"))
		self.contexto = contexto
		self.resultados: list[tuple[str, str]] = []
		self.elegido = ""
		sizer = wx.BoxSizer(wx.VERTICAL)
		_e, self.texto = crear_campo(
			self,
			_("&Texto que buscar:"),
			wx.TextCtrl,
			style=wx.TE_PROCESS_ENTER,
			ayuda=_(
				"Escriba parte del nombre o del tipo («mesa», «puerta cocina»). La lista de abajo se actualiza al escribir; Intro pasa a ella."
			),
			sizer=sizer,
		)
		etiqueta = wx.StaticText(self, label=_("&Resultados:"))
		self.lista = ListaAccesible(self, _("Resultados"), [(_("Elemento"), self.FromDIP(480))])
		self.lista.SetHelpText(_("Elementos encontrados. Intro cierra y selecciona el elegido."))
		self.lista.SetMinSize(self.FromDIP(wx.Size(500, 220)))
		sizer.Add(etiqueta, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		sizer.Add(self.lista, 1, wx.EXPAND | wx.ALL, 5)
		sizer.Add(crear_botonera(self, wx.OK | wx.CANCEL), 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		self.FindWindow(wx.ID_OK).SetLabel(_("&Ir al elemento"))
		self.SetSizerAndFit(sizer)
		self.texto.Bind(wx.EVT_TEXT, lambda _evento: self.buscar(self.texto.GetValue()))
		self.texto.Bind(wx.EVT_TEXT_ENTER, lambda _evento: self._a_la_lista())
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self._aceptar_y_cerrar())
		self.Bind(wx.EVT_BUTTON, lambda _evento: self._aceptar_y_cerrar(), id=wx.ID_OK)
		self.buscar("")
		preparar_dialogo(self, foco_inicial=self.texto)
		self.CentreOnParent()

	def buscar(self, texto: str) -> int:
		"""Rellena la lista con lo que coincide. Devuelve cuántos hay."""
		self.resultados = operaciones.buscar_elementos(self.contexto.entorno, texto, self.contexto.catalogo)
		self.lista.reemplazar_filas([(rotulo,) for _id, rotulo in self.resultados], conservar_foco=False)
		if self.resultados:
			self.lista.enfocar_fila(0, anunciar=False)
		return len(self.resultados)

	def _a_la_lista(self) -> None:
		"""Intro en el campo de texto: dice cuántos hay y pasa a la lista."""
		cantidad = len(self.resultados)
		if not cantidad:
			self.contexto.anunciar(_("No se ha encontrado nada."))
			return
		self.contexto.anunciar(_n("{n} resultado.", "{n} resultados.", cantidad).format(n=cantidad))
		enfocar(self.lista)

	def aceptar(self) -> bool:
		"""Deja en ``elegido`` el id de la fila enfocada. False si no hay ninguna."""
		fila = self.lista.fila_actual()
		if not 0 <= fila < len(self.resultados):
			return False
		self.elegido = self.resultados[fila][0]
		return True

	def _aceptar_y_cerrar(self) -> None:
		if self.aceptar() and self.IsModal():
			self.EndModal(wx.ID_OK)


def buscar_elemento(contexto: Any) -> str:
	"""Abre «Buscar elemento», selecciona el elegido y devuelve su id («» si se cancela)."""
	if _sin_entorno(contexto, _("Buscar elemento")):
		return ""
	dialogo = DialogoBuscar(contexto.ventana, contexto)
	elegido = ""
	try:
		if dialogo.ShowModal() == wx.ID_OK:
			if not dialogo.elegido:
				dialogo.aceptar()
			elegido = dialogo.elegido
	finally:
		dialogo.Destroy()
	if elegido:
		contexto.seleccionar(elegido)
	return elegido
