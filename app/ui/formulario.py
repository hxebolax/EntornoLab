"""Formularios accesibles generados a partir de un esquema (``app/ui/esquemas.py``).

Un solo generador para todo el Estudio: el panel de propiedades de la ventana
principal, los diálogos de «Insertar…» y las preferencias. Así las reglas de
accesibilidad se cumplen en un único sitio:

- la etiqueta (``wx.StaticText``) se crea JUSTO ANTES de su control y con el
  mismo padre, que es de donde el lector de pantalla toma el nombre;
- cada campo, casilla y botón lleva su letra de acceso, repartida de modo
  que no se repita en la página ni choque con los menús de la barra;
- solo controles nativos; las medidas son ``wx.TextCtrl`` validados que
  admiten coma o punto decimal (nunca ``wx.SpinCtrlDouble``);
- la ayuda de cada campo se oye con Control+H;
- al validar, el foco va al campo que hay que corregir.

Los campos condicionados (``Campo.si``) se resuelven reconstruyendo el
formulario cuando cambia un campo marcado con ``recarga``.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable, Sequence
from typing import Any

import wx

from app.core.i18n import _
from app.ui.accesibilidad.ayuda import ayuda_generica
from app.ui.accesibilidad.casillas import CheckListBoxAccesible
from app.ui.accesibilidad.controles import SliderAccesible
from app.ui.accesibilidad.dialogos import ETIQUETAS, crear_botonera, enfocar, mostrar_error, preparar_dialogo
from app.ui.accesibilidad.nombres import crear_campo, nombre_limpio
from app.ui.esquemas import Campo, ErrorCampo, con_letra, convertir_valor, grupos_de, letras_de, texto_numero

log = logging.getLogger(__name__)

#: Validador de un formulario entero: recibe los valores y devuelve None o lanza ``ErrorCampo``.
Validador = Callable[[dict[str, Any]], Any]


def letras_de_botonera(*identificadores: int) -> set[str]:
	"""Letras de acceso que ocupan los botones estándar (Aceptar, Cancelar, Aplicar…) ya traducidos."""
	return letras_de(_(ETIQUETAS[identificador]) for identificador in identificadores)


def letras_de_barra(ventana: wx.Window | None) -> set[str]:
	"""Letras de los menús de la barra de la ventana que contiene a ``ventana``.

	Alt+letra abre el menú antes de llegar a ningún campo: por eso un campo
	de la ventana principal no puede usar la letra de un menú.
	"""
	marco = wx.GetTopLevelParent(ventana) if ventana is not None else None
	barra = marco.GetMenuBar() if isinstance(marco, wx.Frame) else None
	if barra is None:
		return set()
	return letras_de(barra.GetMenuLabel(indice) for indice in range(barra.GetMenuCount()))


class Formulario(wx.Panel):
	"""Los campos de un esquema, con sus pestañas si el esquema tiene grupos."""

	def __init__(
		self,
		padre: wx.Window,
		campos: Sequence[Campo] = (),
		valores: dict[str, Any] | None = None,
		letras_usadas: Iterable[str] = (),
		al_cambiar: Callable[[str], None] | None = None,
		nombre: str = "",
	) -> None:
		"""Crea el formulario.

		:param letras_usadas: letras de acceso que ya tiene la pantalla fuera
			de este formulario (menús de la barra, botones de la botonera).
		:param al_cambiar: se llama con la clave cuando la persona cambia un campo.
		"""
		super().__init__(padre, name=nombre or _("Formulario"))
		self.campos: list[Campo] = list(campos)
		self._valores: dict[str, Any] = dict(valores or {})
		self._letras_base = set(letras_usadas)
		self._al_cambiar = al_cambiar
		self.controles: dict[str, wx.Window] = {}
		self._lectores: dict[str, Callable[[], Any]] = {}
		self._escritores: dict[str, Callable[[Any], None]] = {}
		self._cuerpo: wx.Window | None = None
		#: Cuántos cuerpos de otros esquemas se guardan ocultos para volver a ellos sin crear controles
		#: (el panel de propiedades del Estudio, al pasar de una acera a una puerta y vuelta). 0: ninguno.
		self.guardar_cuerpos = 0
		self._guardados: dict[tuple[Any, ...], tuple[wx.Window, dict[str, wx.Window], dict[str, Any], dict[str, Any]]] = {}
		self._sizer = wx.BoxSizer(wx.VERTICAL)
		self.SetSizer(self._sizer)
		self._construir()

	# ── Construcción ─────────────────────────────────────────────────────────

	def cargar(self, campos: Sequence[Campo], valores: dict[str, Any] | None = None) -> None:
		"""Sustituye el esquema entero (el panel de propiedades al cambiar de elemento).

		Si el esquema nuevo tiene los mismos campos que el que se ve (pasar de
		una acera a otra, de una puerta a otra), se reutilizan los controles y
		solo se escriben los valores: crear una docena de controles nativos
		cuesta más de 100 ms y se notaba al recorrer el árbol con las flechas.
		"""
		campos = list(campos)
		valores = dict(valores or {})
		anterior = self._firma(self.campos, self._valores) if self._cuerpo is not None else None
		self.campos = campos
		self._valores = valores
		nueva = self._firma(campos, valores)
		if anterior is not None and anterior == nueva:
			self._escribir_visibles()
			return
		if self.guardar_cuerpos > 0 and self._cuerpo is not None and anterior is not None:
			# Se aparta el cuerpo que se ve (oculto) por si se vuelve a un elemento de ese tipo.
			self.Freeze()
			try:
				self._sizer.Detach(self._cuerpo)
				self._cuerpo.Hide()
				self._guardados[anterior] = (self._cuerpo, self.controles, self._lectores, self._escritores)
				self._cuerpo = None
				guardado = self._guardados.pop(nueva, None)
				while len(self._guardados) > self.guardar_cuerpos:
					viejo = next(iter(self._guardados))
					self._guardados.pop(viejo)[0].Destroy()
				if guardado is not None:
					self._cuerpo, self.controles, self._lectores, self._escritores = guardado
					self._sizer.Add(self._cuerpo, 1, wx.EXPAND)
					self._cuerpo.Show()
					self._escribir_visibles()
					self.Layout()
					return
			finally:
				self.Thaw()
		self._construir()

	def _escribir_visibles(self) -> None:
		"""Pone en los controles que ya hay los valores de ``_valores`` (los mismos campos, otro elemento)."""
		for campo in self.visibles():
			escritor = self._escritores.get(campo.clave)
			if escritor is not None:
				escritor(self._valores.get(campo.clave, campo.defecto))

	@staticmethod
	def _firma(campos: Sequence[Campo], valores: dict[str, Any]) -> tuple[Any, ...]:
		"""Lo que decide qué controles se crean: si coincide, los controles que hay sirven para los valores nuevos."""
		firma: list[Any] = []
		for campo in campos:
			if not campo.visible(valores):
				continue
			valor = valores.get(campo.clave, campo.defecto)
			parte: tuple[Any, ...] = (campo.clave, campo.tipo, campo.etiqueta, campo.grupo, campo.ayuda, campo.obligatorio, campo.recarga)
			if campo.tipo in ("opcion", "casillas"):
				opciones = tuple(campo.lista_opciones(valores))
				claves = [opcion for opcion, _texto in opciones]
				fuera = campo.tipo == "opcion" and valor not in claves and valor not in (None, "")
				parte += (opciones, fuera, campo.tipo == "opcion" and valor in claves)
			elif campo.tipo == "solo_lectura":
				texto = "" if valor is None else str(valor)
				parte += ("\n" in texto or len(texto) > 80,)
			elif campo.tipo == "deslizador":
				parte += (campo.minimo, campo.maximo, tuple(sorted(campo.extra.items())))
			firma.append(parte)
		return tuple(firma)

	def visibles(self) -> list[Campo]:
		"""Campos que proceden con los valores actuales."""
		return [campo for campo in self.campos if campo.visible(self._valores)]

	def _construir(self, foco: str | None = None) -> None:
		"""Crea (o vuelve a crear) los controles a partir del esquema y los valores."""
		self.Freeze()
		try:
			if self._cuerpo is not None:
				self._sizer.Detach(self._cuerpo)
				self._cuerpo.Destroy()
				self._cuerpo = None
			self.controles = {}
			self._lectores = {}
			self._escritores = {}
			visibles = self.visibles()
			grupos = grupos_de(visibles)
			if len(grupos) > 1:
				cuaderno = wx.Notebook(self)
				for grupo in grupos:
					titulo = _(grupo) if grupo else _("General")
					pagina = self._pagina(cuaderno, [campo for campo in visibles if campo.grupo == grupo], titulo)
					cuaderno.AddPage(pagina, titulo)
				self._cuerpo = cuaderno
			else:
				self._cuerpo = self._pagina(self, visibles, self.GetName())
			self._sizer.Add(self._cuerpo, 1, wx.EXPAND)
			self.Layout()
		finally:
			self.Thaw()
		if foco and foco in self.controles:
			wx.CallAfter(self._enfocar_seguro, foco)

	def _pagina(self, padre: wx.Window, campos: Sequence[Campo], nombre: str) -> wx.ScrolledWindow:
		"""Una página con barra de desplazamiento: un formulario largo no se corta en pantallas pequeñas."""
		pagina = wx.ScrolledWindow(padre, style=wx.TAB_TRAVERSAL, name=nombre)
		pagina.SetScrollRate(0, self.FromDIP(16))
		sizer = wx.BoxSizer(wx.VERTICAL)
		usadas = set(self._letras_base)
		for campo in campos:
			self._crear_control(pagina, sizer, campo, usadas)
		pagina.SetSizer(sizer)
		return pagina

	def _crear_control(self, pagina: wx.Window, sizer: wx.Sizer, campo: Campo, usadas: set[str]) -> None:
		"""Crea la etiqueta y el control de un campo, y apunta cómo leerlo y escribirlo."""
		clave, tipo = campo.clave, campo.tipo
		valor = self._valores.get(clave, campo.defecto)
		ayuda = _(campo.ayuda) if campo.ayuda else ""
		if campo.obligatorio:
			ayuda = (ayuda + " " + _("Obligatorio.")).strip()
		etiqueta = con_letra(_(campo.etiqueta), usadas)
		control: wx.Window
		if tipo in ("texto", "largo", "metros", "decimal", "entero"):
			if tipo == "metros":
				ayuda = (ayuda + " " + _("En metros; los decimales, con coma o con punto.")).strip()
			texto = texto_numero(valor) if tipo in ("metros", "decimal", "entero") else ("" if valor is None else str(valor))
			estilo = wx.TE_MULTILINE if tipo == "largo" else 0
			tamano = self.FromDIP(wx.Size(320, 70)) if estilo else wx.DefaultSize
			_e, control = crear_campo(pagina, etiqueta + ":", wx.TextCtrl, value=texto, style=estilo, size=tamano, ayuda=ayuda, sizer=sizer)
			self._lectores[clave] = control.GetValue
			if tipo in ("metros", "decimal", "entero"):
				self._escritores[clave] = lambda v, c=control: c.ChangeValue(texto_numero(v))
			else:
				self._escritores[clave] = lambda v, c=control: c.ChangeValue("" if v is None else str(v))
			control.Bind(wx.EVT_KILL_FOCUS, lambda e, k=clave: self._al_salir_de(e, k))
		elif tipo == "solo_lectura":
			texto = "" if valor is None else str(valor)
			largo = "\n" in texto or len(texto) > 80
			estilo = wx.TE_READONLY | (wx.TE_MULTILINE if largo else 0)
			tamano = self.FromDIP(wx.Size(320, 70)) if largo else wx.DefaultSize
			_e, control = crear_campo(pagina, etiqueta + ":", wx.TextCtrl, value=texto, style=estilo, size=tamano, ayuda=ayuda, sizer=sizer)
			self._escritores[clave] = lambda v, c=control: c.ChangeValue("" if v is None else str(v))
		elif tipo == "si_no":
			control = wx.CheckBox(pagina, label=etiqueta)
			control.SetValue(bool(valor))
			control.SetHelpText(ayuda or _("Casilla. La barra espaciadora la marca o la desmarca."))
			sizer.Add(control, 0, wx.ALL, 5)
			self._lectores[clave] = lambda c=control: bool(c.GetValue())
			self._escritores[clave] = lambda v, c=control: c.SetValue(bool(v))
			control.Bind(wx.EVT_CHECKBOX, lambda _e, k=clave, r=campo.recarga: self._cambio(k, r))
		elif tipo == "opcion":
			opciones = campo.lista_opciones(self._valores)
			claves = [opcion for opcion, _texto in opciones]
			textos = [texto for _opcion, texto in opciones]
			if valor not in claves and valor not in (None, ""):
				# Un valor que ya no está en la lista (un sonido de un complemento que falta) no se pierde.
				claves.append(valor)
				textos.append(_("{valor} (no disponible)").format(valor=valor))
			_e, control = crear_campo(pagina, etiqueta + ":", wx.Choice, choices=textos, ayuda=ayuda, sizer=sizer)
			if claves:
				control.SetSelection(claves.index(valor) if valor in claves else 0)
			self._lectores[clave] = lambda c=control, ks=claves: ks[c.GetSelection()] if 0 <= c.GetSelection() < len(ks) else None
			self._escritores[clave] = lambda v, c=control, ks=claves: c.SetSelection(ks.index(v)) if v in ks else None
			control.Bind(wx.EVT_CHOICE, lambda _e, k=clave, r=campo.recarga: self._cambio(k, r))
		elif tipo == "casillas":
			opciones = campo.lista_opciones(self._valores)
			claves = [opcion for opcion, _texto in opciones]
			textos = [texto for _opcion, texto in opciones]
			_e, control = crear_campo(
				pagina,
				etiqueta + ":",
				# crear_campo pasa el nombre como ``name=``; esta lista lo quiere como segundo argumento.
				lambda p, ts=textos, **kw: CheckListBoxAccesible(p, kw.pop("name"), ts, **kw),
				size=self.FromDIP(wx.Size(320, 90)),
				ayuda=(ayuda + " " + _("Lista de casillas: la barra espaciadora marca o desmarca cada una.")).strip(),
				sizer=sizer,
			)
			control.SetCheckedItems([claves.index(v) for v in (valor or []) if v in claves])
			if claves:
				control.SetSelection(0)
			self._lectores[clave] = lambda c=control, ks=claves: [ks[i] for i in c.GetCheckedItems()]
			self._escritores[clave] = lambda v, c=control, ks=claves: c.SetCheckedItems([ks.index(x) for x in (v or []) if x in ks])
			control.Bind(wx.EVT_CHECKLISTBOX, lambda _e, k=clave, r=campo.recarga: self._cambio(k, r))
		elif tipo == "deslizador":
			minimo = int(campo.minimo if campo.minimo is not None else 0)
			maximo = int(campo.maximo if campo.maximo is not None else 100)
			inicial = max(minimo, min(maximo, int(valor if valor is not None else minimo)))
			_e, control = crear_campo(
				pagina,
				etiqueta + ":",
				SliderAccesible,
				inicial,
				minimo,
				maximo,
				unidad=_(campo.extra.get("unidad", "")) if campo.extra.get("unidad") else "",
				paso=int(campo.extra.get("paso", 1)),
				paso_pagina=int(campo.extra.get("paso_pagina", max(1, (maximo - minimo) // 10))),
				ayuda=ayuda,
				sizer=sizer,
			)
			self._lectores[clave] = control.GetValue
			self._escritores[clave] = lambda v, c=control: c.SetValue(int(v))
			control.Bind(wx.EVT_SLIDER, lambda _e, k=clave, r=campo.recarga: self._cambio(k, r))
		elif tipo in ("ruta_fichero", "ruta_carpeta"):
			_e, control = crear_campo(pagina, etiqueta + ":", wx.TextCtrl, value="" if valor is None else str(valor), ayuda=ayuda)
			nombre = nombre_limpio(etiqueta)
			boton = wx.Button(pagina, label=con_letra(_("Examinar {campo}...").format(campo=nombre.lower()), usadas))
			boton.SetHelpText(_("Abre un cuadro de Windows para elegir «{campo}».").format(campo=nombre))
			boton.Bind(wx.EVT_BUTTON, lambda _e, cp=campo, c=control: self._examinar(cp, c))
			sizer.Add(_e, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
			fila = wx.BoxSizer(wx.HORIZONTAL)
			fila.Add(control, 1, wx.EXPAND | wx.RIGHT, 5)
			fila.Add(boton, 0)
			sizer.Add(fila, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
			self._lectores[clave] = control.GetValue
			self._escritores[clave] = lambda v, c=control: c.ChangeValue("" if v is None else str(v))
		else:
			log.error("Tipo de campo desconocido en un esquema: %s (%s)", tipo, clave)
			return
		if not control.GetHelpText():
			# Control+H tiene que decir algo de todos los campos, también de los que el esquema no explica.
			control.SetHelpText(ayuda_generica(control))
		self.controles[clave] = control

	def _examinar(self, campo: Campo, control: wx.TextCtrl) -> None:
		"""Diálogo nativo de Windows para elegir el fichero o la carpeta de un campo de ruta."""
		titulo = _(campo.etiqueta).replace("&", "")
		if campo.tipo == "ruta_carpeta":
			dialogo: wx.Dialog = wx.DirDialog(self, titulo, control.GetValue(), style=wx.DD_DEFAULT_STYLE)
		else:
			estilo = wx.FD_SAVE | wx.FD_OVERWRITE_PROMPT if campo.extra.get("guardar") else wx.FD_OPEN | wx.FD_FILE_MUST_EXIST
			dialogo = wx.FileDialog(self, titulo, wildcard=_(campo.comodin) if campo.comodin else "*.*", style=estilo)
		try:
			if dialogo.ShowModal() == wx.ID_OK:
				control.SetValue(dialogo.GetPath())
				self._cambio(campo.clave, campo.recarga)
		finally:
			dialogo.Destroy()
		control.SetFocus()

	# ── Cambios ──────────────────────────────────────────────────────────────

	def _al_salir_de(self, evento: wx.FocusEvent, clave: str) -> None:
		"""Al dejar un campo de texto se avisa del cambio si lo hubo (sin validar todavía)."""
		evento.Skip()
		if not self or clave not in self._lectores:
			return
		actual = self._lectores[clave]()
		anterior = self._valores.get(clave)
		if actual != ("" if anterior is None else anterior) and self._al_cambiar is not None:
			self._al_cambiar(clave)

	def _cambio(self, clave: str, recarga: bool) -> None:
		"""Un control de elección cambió: se recarga el formulario si de él dependen otros campos."""
		if recarga:
			self._valores.update(self.crudos())
			wx.CallAfter(self._reconstruir_si_vivo, clave)
		if self._al_cambiar is not None:
			self._al_cambiar(clave)

	def _reconstruir_si_vivo(self, clave: str) -> None:
		if self:
			self._construir(foco=clave)

	def _enfocar_seguro(self, clave: str) -> None:
		if self and clave in self.controles and self.controles[clave]:
			self.enfocar(clave)

	# ── Valores ──────────────────────────────────────────────────────────────

	def crudos(self) -> dict[str, Any]:
		"""Lo que hay ahora en los controles, sin validar (los números, como texto)."""
		return {clave: lector() for clave, lector in self._lectores.items()}

	def fijar(self, valores: dict[str, Any]) -> None:
		"""Pone valores en los controles; reconstruye si cambian campos de los que dependen otros."""
		self._valores.update(valores)
		if any(campo.recarga and campo.clave in valores for campo in self.campos):
			self._construir()
			return
		for clave, valor in valores.items():
			escritor = self._escritores.get(clave)
			if escritor is not None:
				escritor(valor)

	def leer(self) -> dict[str, Any]:
		"""Los valores validados y con su tipo; lanza ``ErrorCampo`` con el primer campo que no vale.

		Solo devuelve los campos visibles: los de otro tipo de elemento, que ya
		no proceden, no se arrastran.
		"""
		resultado: dict[str, Any] = {}
		for campo in self.visibles():
			lector = self._lectores.get(campo.clave)
			if lector is None:
				continue
			resultado[campo.clave] = convertir_valor(campo, lector())
		return resultado

	def enfocar(self, clave: str) -> None:
		"""Lleva el foco a un campo, abriendo antes su pestaña si hace falta."""
		control = self.controles.get(clave)
		if control is None:
			return
		if isinstance(self._cuerpo, wx.Notebook):
			for indice in range(self._cuerpo.GetPageCount()):
				if control.GetParent() is self._cuerpo.GetPage(indice):
					self._cuerpo.SetSelection(indice)
					break
		enfocar(control)

	def primer_control(self) -> wx.Window | None:
		"""El primer control editable, para el foco inicial."""
		for campo in self.visibles():
			control = self.controles.get(campo.clave)
			if control is not None and campo.tipo != "solo_lectura":
				return control
		return next(iter(self.controles.values()), None)


class DialogoFormulario(wx.Dialog):
	"""Diálogo con un formulario de esquema y los botones Aceptar y Cancelar.

	``validar`` recibe los valores ya convertidos; puede lanzar ``ErrorCampo``
	(el foco va al campo) o cualquier ``ValueError`` con un mensaje para la
	persona (``ErrorEdicion`` lo es): el diálogo sigue abierto para corregir.
	Lo que devuelva ``validar`` queda en ``producto`` (por ejemplo, el
	elemento recién creado).
	"""

	def __init__(
		self,
		padre: wx.Window | None,
		titulo: str,
		campos: Sequence[Campo],
		valores: dict[str, Any] | None = None,
		validar: Validador | None = None,
		introduccion: str = "",
	) -> None:
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name=titulo)
		self._validar = validar
		self.resultado: dict[str, Any] | None = None
		self.producto: Any = None
		self.ultimo_error: str = ""
		sizer = wx.BoxSizer(wx.VERTICAL)
		if introduccion:
			texto = wx.StaticText(self, label=introduccion)
			texto.Wrap(self.FromDIP(460))
			sizer.Add(texto, 0, wx.ALL, 8)
		self.formulario = Formulario(self, campos, valores, letras_usadas=letras_de_botonera(wx.ID_OK, wx.ID_CANCEL), nombre=titulo)
		sizer.Add(self.formulario, 1, wx.EXPAND | wx.ALL, 5)
		sizer.Add(crear_botonera(self, wx.OK | wx.CANCEL), 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		self.SetSizer(sizer)
		self.Bind(wx.EVT_BUTTON, self._al_aceptar, id=wx.ID_OK)
		preparar_dialogo(self, foco_inicial=self.formulario.primer_control())
		alto = min(self.FromDIP(640), sizer.GetMinSize().height + self.FromDIP(40) + self.FromDIP(34) * len(self.formulario.visibles()))
		self.SetSize(wx.Size(self.FromDIP(520), max(self.FromDIP(220), alto)))
		self.CentreOnParent()

	def fijar(self, valores: dict[str, Any]) -> None:
		"""Rellena campos (lo usan las pruebas y los asistentes que proponen valores)."""
		self.formulario.fijar(valores)

	def aceptar(self) -> bool:
		"""Valida y guarda el resultado. False (con el foco en el campo erróneo) si algo no vale."""
		try:
			valores = self.formulario.leer()
			self.producto = self._validar(valores) if self._validar is not None else None
		except ErrorCampo as error:
			self.ultimo_error = error.mensaje
			mostrar_error(self, error.mensaje, _("Revise el formulario"))
			self.formulario.enfocar(error.clave)
			return False
		except ValueError as error:
			self.ultimo_error = str(error)
			mostrar_error(self, str(error), _("No se puede hacer"))
			primero = self.formulario.primer_control()
			if primero is not None:
				enfocar(primero)
			return False
		self.ultimo_error = ""
		self.resultado = valores
		return True

	def _al_aceptar(self, _evento: wx.CommandEvent) -> None:
		if self.aceptar():
			self.EndModal(wx.ID_OK)


def mostrar_dialogo(dialogo: wx.Dialog) -> int:
	"""Muestra un diálogo modal, lo destruye y devuelve el foco al control que lo abrió."""
	foco_previo = wx.Window.FindFocus()
	try:
		return dialogo.ShowModal()
	finally:
		dialogo.Destroy()
		if foco_previo:
			foco_previo.SetFocus()


def pedir_formulario(
	padre: wx.Window | None,
	titulo: str,
	campos: Sequence[Campo],
	valores: dict[str, Any] | None = None,
	validar: Validador | None = None,
	introduccion: str = "",
) -> dict[str, Any] | None:
	"""Abre un formulario modal y devuelve sus valores, o ``None`` si se cancela.

	Si ``validar`` devuelve algo, sale en la clave ``"_producto"`` del resultado.
	"""
	dialogo = DialogoFormulario(padre, titulo, campos, valores, validar, introduccion)
	foco_previo = wx.Window.FindFocus()
	try:
		if dialogo.ShowModal() != wx.ID_OK:
			return None
		# Con un ShowModal de verdad el botón Aceptar ya validó; con uno
		# sustituido (pruebas, automatización) se valida aquí.
		if dialogo.resultado is None and not dialogo.aceptar():
			return None
		resultado = dict(dialogo.resultado or {})
		resultado["_producto"] = dialogo.producto
		return resultado
	finally:
		dialogo.Destroy()
		if foco_previo:
			foco_previo.SetFocus()
