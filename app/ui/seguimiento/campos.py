"""Editores de campo del formulario de actividades: uno por tipo de campo del esquema.

El formulario de una actividad no está escrito a mano: se genera a partir de
``campos_de(tipo)``. Cada tipo de campo («texto», «entero», «lista_premios»...)
tiene aquí su editor, apuntado en ``EDITORES``. Para dar soporte a un tipo de
campo nuevo basta con escribir una clase ``EditorCampo`` y apuntarla con
``registrar`` (ver ``docs/estudio-seguimiento.md``).

Todos los editores cumplen lo mismo: la etiqueta se crea justo antes del
control y con el mismo padre, lleva letra de acceso repartida por ``Letras``,
la ayuda del esquema queda para Ctrl+H y ``volcar`` lanza ``ErrorCampo`` con
el control que hay que corregir.
"""

from __future__ import annotations

import copy
import logging
from typing import Any

import wx

from app.core.i18n import N_, _
from app.ui.seguimiento import actividades_api as api
from app.ui.seguimiento import lugares, sonidos
from app.ui.seguimiento import presentador_actividades as pres
from app.ui.seguimiento.comun import crear_boton, crear_texto, mostrar_modal, poner_texto
from app.ui.seguimiento.contexto import anunciar
from app.ui.seguimiento.editor_ayudas import DialogoNiveles, PanelAyudas
from app.ui.seguimiento.editor_objetivos import PanelObjetivos
from app.ui.seguimiento.editor_premios import PanelPremios
from app.ui.seguimiento.selector_lugar import DialogoElemento, DialogoLugar
from app.ui.seguimiento.textos import Letras, leer_numero, texto_numero

log = logging.getLogger(__name__)


class ErrorCampo(ValueError):
	"""Lo escrito en un campo no vale. Lleva el control al que hay que llevar el foco."""

	def __init__(self, mensaje: str, control: wx.Window | None = None) -> None:
		super().__init__(mensaje)
		self.control = control


def _con_dos_puntos(etiqueta: str) -> str:
	limpia = etiqueta.strip()
	return limpia if limpia.endswith((":", "?")) else limpia + ":"


class EditorCampo:
	"""Base de los editores: crea sus controles en ``padre`` y sabe cargar y volcar su valor.

	:param padre: la página del formulario (los controles son hijos directos suyos).
	:param campo: el ``Campo`` del esquema (``clave``, ``etiqueta``, ``tipo``, ``ayuda``, ``opciones``...).
	:param letras: reparte las letras de acceso de la página.
	:param formulario: el diálogo; da ``contexto``, ``servicio``, ``datos`` y ``editor(clave)``.
	"""

	#: Si el editor ocupa mucho alto y conviene que se estire con la ventana.
	expande = False

	def __init__(self, padre: wx.Window, campo: Any, letras: Letras, formulario: Any) -> None:
		self.padre = padre
		self.campo = campo
		self.letras = letras
		self.formulario = formulario
		self.clave: str = str(campo.clave)
		self.nombre: str = str(campo.etiqueta).rstrip(":").strip()
		self.sizer = wx.BoxSizer(wx.VERTICAL)
		self.ventanas: list[wx.Window] = []
		self.principal: wx.Window | None = None
		self.crear()
		for ventana in self.ventanas:
			if not ventana.GetHelpText() and getattr(campo, "ayuda", ""):
				ventana.SetHelpText(str(campo.ayuda))

	# ── Para las clases hijas ────────────────────────────────────────────────

	def crear(self) -> None:
		"""Crea los controles y los añade a ``self.sizer`` y a ``self.ventanas``."""
		raise NotImplementedError

	def etiqueta(self) -> str:
		"""La etiqueta del esquema con dos puntos y su letra de acceso."""
		return self.letras.poner(_con_dos_puntos(str(self.campo.etiqueta)))

	def anadir_etiqueta(self) -> wx.StaticText:
		"""Crea la etiqueta. Debe llamarse JUSTO ANTES de crear el control al que nombra."""
		texto = wx.StaticText(self.padre, label=self.etiqueta())
		self.sizer.Add(texto, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		self.ventanas.append(texto)
		return texto

	def anadir_control(self, control: wx.Window, proporcion: int = 0, principal: bool = True) -> None:
		"""Añade un control ya creado."""
		self.sizer.Add(control, proporcion, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		self.ventanas.append(control)
		if principal:
			self.principal = control

	# ── Valor ────────────────────────────────────────────────────────────────

	def poner(self, valor: Any) -> None:
		"""Muestra un valor."""
		raise NotImplementedError

	def leer(self) -> Any:
		"""Devuelve el valor. Lanza ``ErrorCampo`` si no vale."""
		raise NotImplementedError

	def cargar(self, datos: dict[str, Any]) -> None:
		"""Lee su valor de la actividad (o el de serie del esquema si no está)."""
		valor = api.leer_campo(datos, self.clave, None)
		if valor is None:
			valor = copy.deepcopy(getattr(self.campo, "defecto", None))
		self.poner(valor)

	def volcar(self, datos: dict[str, Any]) -> None:
		"""Escribe su valor en la actividad. Lanza ``ErrorCampo`` si no vale."""
		api.poner_campo(datos, self.clave, self.leer())

	def activar(self, activo: bool) -> None:
		"""Atenúa o reactiva el campo (cuando depende de otro que está apagado)."""
		for ventana in self.ventanas:
			ventana.Enable(activo)

	@property
	def activo(self) -> bool:
		"""False si el campo está atenuado: entonces no se valida."""
		return self.principal is None or self.principal.IsEnabled()


class EditorTexto(EditorCampo):
	"""Texto de una línea, o de varias si el tipo es «texto_largo»."""

	def crear(self) -> None:
		self.anadir_etiqueta()
		largo = self.campo.tipo == "texto_largo"
		estilo = (wx.TE_MULTILINE | wx.TE_WORDWRAP) if largo else 0
		self.control = wx.TextCtrl(self.padre, style=estilo, size=wx.Size(420, 70 if largo else -1), name=self.nombre)
		self.anadir_control(self.control)

	def poner(self, valor: Any) -> None:
		self.control.ChangeValue("" if valor is None else str(valor))

	def leer(self) -> str:
		return self.control.GetValue().strip()


class EditorNumero(EditorCampo):
	"""Número entero o decimal en un campo de texto, con sus límites.

	No se usa ``wx.SpinCtrlDouble``: es un control genérico cuyo campo
	interno no toma la etiqueta y el lector no lo nombra al tabular.
	"""

	def crear(self) -> None:
		self.anadir_etiqueta()
		self.control = wx.TextCtrl(self.padre, size=wx.Size(140, -1), name=self.nombre)
		self.anadir_control(self.control)
		minimo, maximo = getattr(self.campo, "minimo", None), getattr(self.campo, "maximo", None)
		ayuda = str(getattr(self.campo, "ayuda", "") or "")
		if minimo is not None and maximo is not None:
			ayuda += " " + _("Entre {minimo} y {maximo}.").format(minimo=texto_numero(minimo), maximo=texto_numero(maximo))
		if self.campo.tipo == "decimal":
			ayuda += " " + _("Admite decimales con coma.")
		self.control.SetHelpText(ayuda.strip())

	def poner(self, valor: Any) -> None:
		self.control.ChangeValue(texto_numero(valor))

	def leer(self) -> int | float | None:
		entero = self.campo.tipo == "entero"
		try:
			valor = leer_numero(self.control.GetValue(), entero=entero)
		except ValueError:
			mensaje = _("«{campo}» debe ser un número entero.") if entero else _("«{campo}» debe ser un número.")
			raise ErrorCampo(mensaje.format(campo=self.nombre), self.control) from None
		if valor is None:
			defecto = getattr(self.campo, "defecto", None)
			if defecto is None:
				return None
			raise ErrorCampo(_("Escriba un valor en «{campo}».").format(campo=self.nombre), self.control)
		minimo, maximo = getattr(self.campo, "minimo", None), getattr(self.campo, "maximo", None)
		if (minimo is not None and valor < minimo) or (maximo is not None and valor > maximo):
			raise ErrorCampo(
				_("«{campo}» debe estar entre {minimo} y {maximo}.").format(
					campo=self.nombre,
					minimo=texto_numero(minimo) if minimo is not None else "−∞",
					maximo=texto_numero(maximo) if maximo is not None else "∞",
				),
				self.control,
			)
		return valor


class EditorSiNo(EditorCampo):
	"""Casilla de verificación. Al cambiarla se revisan los campos que dependen de ella."""

	def crear(self) -> None:
		self.control = wx.CheckBox(self.padre, label=self.letras.poner(str(self.campo.etiqueta).rstrip(":")), name=self.nombre)
		self.sizer.Add(self.control, 0, wx.ALL, 5)
		self.ventanas.append(self.control)
		self.principal = self.control
		self.control.Bind(wx.EVT_CHECKBOX, lambda _evento: self.formulario.al_cambiar_campo(self.clave))

	def poner(self, valor: Any) -> None:
		self.control.SetValue(bool(valor))

	def leer(self) -> bool:
		return bool(self.control.GetValue())


class EditorOpcion(EditorCampo):
	"""Lista desplegable con las opciones del esquema."""

	def crear(self) -> None:
		self.opciones = pres.opciones_normalizadas(getattr(self.campo, "opciones", None))
		self.anadir_etiqueta()
		self.control = wx.Choice(self.padre, choices=[etiqueta for _valor, etiqueta in self.opciones], name=self.nombre)
		self.anadir_control(self.control)
		self.control.Bind(wx.EVT_CHOICE, lambda _evento: self.formulario.al_cambiar_campo(self.clave))

	def poner(self, valor: Any) -> None:
		valores = [opcion for opcion, _etiqueta in self.opciones]
		if valor not in valores and valor not in (None, ""):
			# Un valor de otra versión no se pierde: se enseña tal cual.
			self.opciones.append((valor, str(valor)))
			self.control.Append(str(valor))
			valores.append(valor)
		if valor in valores:
			self.control.SetSelection(valores.index(valor))
		elif self.opciones:
			self.control.SetSelection(0)

	def leer(self) -> Any:
		indice = self.control.GetSelection()
		if not 0 <= indice < len(self.opciones):
			raise ErrorCampo(_("Elija una opción en «{campo}».").format(campo=self.nombre), self.control)
		return self.opciones[indice][0]


class EditorSonido(EditorCampo):
	"""Lista de sonidos con un botón «Escuchar»."""

	def crear(self) -> None:
		self.sonidos = [("", _("El de serie")), *sonidos.listar_sonidos()]
		self.anadir_etiqueta()
		self.control = wx.Choice(self.padre, choices=[nombre for _clave, nombre in self.sonidos], name=self.nombre)
		self.anadir_control(self.control)
		self.boton = crear_boton(
			self.padre,
			self.letras.poner(_("Escuchar: {campo}").format(campo=self.nombre.lower())),
			self.escuchar,
			_("Reproduce el sonido elegido, para saber cómo suena."),
		)
		self.sizer.Add(self.boton, 0, wx.LEFT | wx.BOTTOM, 5)
		self.ventanas.append(self.boton)

	def poner(self, valor: Any) -> None:
		claves = [clave for clave, _nombre in self.sonidos]
		texto = str(valor or "")
		if texto not in claves:
			self.sonidos.append((texto, texto))
			self.control.Append(texto)
			claves.append(texto)
		self.control.SetSelection(claves.index(texto))

	def leer(self) -> str:
		return self.sonidos[max(0, self.control.GetSelection())][0]

	def escuchar(self) -> None:
		"""Reproduce el sonido elegido, si el equipo puede."""
		servicio = self.formulario.servicio
		contexto = self.formulario.contexto
		if servicio.escucha is None:
			servicio.escucha = sonidos.Escucha(getattr(contexto, "configuracion", None), lambda: getattr(contexto, "recursos", None))
		if not servicio.escucha.escuchar(self.leer() or str(getattr(self.campo, "defecto", "") or "premio/cerca")):
			anunciar(contexto, sonidos.mensaje_sin_sonido())


class _EditorConSelector(EditorCampo):
	"""Base de «posicion» y «elemento»: el valor se dice en palabras y se cambia con un selector."""

	texto_elegir = ""
	texto_quitar = ""

	def crear(self) -> None:
		self.valor: Any = None
		self.anadir_etiqueta()
		self.control = wx.TextCtrl(self.padre, style=wx.TE_READONLY, size=wx.Size(420, -1), name=self.nombre)
		self.anadir_control(self.control)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		minuscula = self.nombre[:1].lower() + self.nombre[1:]
		self.boton_elegir = crear_boton(
			self.padre,
			self.letras.poner(_(self.texto_elegir).format(campo=minuscula)),
			self.elegir,
			_("Abre el selector para elegirlo por planta y por espacio."),
			fila,
		)
		self.boton_quitar = crear_boton(
			self.padre, self.letras.poner(_(self.texto_quitar).format(campo=minuscula)), self.quitar, _("Lo deja sin indicar."), fila
		)
		self.sizer.Add(fila, 0, wx.LEFT | wx.BOTTOM, 2)
		self.ventanas.extend([self.boton_elegir, self.boton_quitar])

	def describir(self) -> str:
		raise NotImplementedError

	def elegir(self) -> None:
		raise NotImplementedError

	def poner(self, valor: Any) -> None:
		self.valor = copy.deepcopy(valor) if valor else None
		poner_texto(self.control, self.describir())

	def leer(self) -> Any:
		return copy.deepcopy(self.valor)

	def quitar(self) -> None:
		"""Deja el campo sin valor."""
		self.poner(None)
		self.control.SetFocus()


class EditorPosicion(_EditorConSelector):
	"""Un punto del entorno y hacia dónde se mira (el inicio de la actividad)."""

	texto_elegir = N_("Elegir {campo}...")
	texto_quitar = N_("Quitar {campo}")

	def describir(self) -> str:
		return lugares.describir_posicion(getattr(self.formulario.contexto, "entorno", None), self.valor)

	def elegir(self) -> None:
		contexto = self.formulario.contexto
		dialogo = DialogoLugar(
			self.padre.GetTopLevelParent(),
			getattr(contexto, "entorno", None),
			getattr(contexto, "catalogo", None),
			self.nombre,
			self.valor,
			con_rumbo=True,
		)
		try:
			mostrar_modal(dialogo)
			if dialogo.aceptado and dialogo.valor is not None:
				elegido = dialogo.valor
				self.poner({"planta": elegido["planta"], "x": elegido["x"], "y": elegido["y"], "rumbo": elegido.get("rumbo", 0.0)})
		finally:
			dialogo.Destroy()
		self.control.SetFocus()


class EditorElemento(_EditorConSelector):
	"""El id de un elemento del entorno (un espacio, una puerta, un objeto...), elegido por su nombre."""

	texto_elegir = N_("Elegir {campo}...")
	texto_quitar = N_("Quitar {campo}")

	def describir(self) -> str:
		contexto = self.formulario.contexto
		if isinstance(self.valor, dict):
			return lugares.describir_posicion(getattr(contexto, "entorno", None), self.valor)
		return lugares.describir_elemento(getattr(contexto, "entorno", None), str(self.valor or ""), getattr(contexto, "catalogo", None))

	def elegir(self) -> None:
		contexto = self.formulario.contexto
		dialogo = DialogoElemento(
			self.padre.GetTopLevelParent(),
			getattr(contexto, "entorno", None),
			getattr(contexto, "catalogo", None),
			pres.clases_de(getattr(self.campo, "opciones", None)),
			self.valor if isinstance(self.valor, str) else "",
			self.nombre,
		)
		try:
			mostrar_modal(dialogo)
			if dialogo.aceptado:
				self.poner(dialogo.valor)
		finally:
			dialogo.Destroy()
		self.control.SetFocus()


class EditorPremios(EditorCampo):
	"""La lista de premios escondidos."""

	expande = True

	def crear(self) -> None:
		self.panel = PanelPremios(
			self.padre,
			self.formulario.contexto,
			self.formulario.servicio,
			self.letras,
			etiqueta=_con_dos_puntos(str(self.campo.etiqueta)),
			al_cambiar=lambda: self.formulario.al_cambiar_campo(self.clave),
		)
		self.sizer.Add(self.panel, 1, wx.EXPAND)
		self.ventanas.append(self.panel)
		self.principal = self.panel.lista
		self.panel.lista.SetHelpText(str(getattr(self.campo, "ayuda", "") or "") + " " + self.panel.lista.GetHelpText())

	def poner(self, valor: Any) -> None:
		self.panel.poner(valor if isinstance(valor, list) else [])

	def leer(self) -> list[dict[str, Any]]:
		return self.panel.leer()


class EditorObjetivos(EditorCampo):
	"""La lista de objetivos; si el esquema no trae el campo «en orden», lo ofrece ella."""

	expande = True

	def crear(self) -> None:
		self._con_orden = self.clave == "objetivos" and not self.formulario.tiene_campo("orden_obligatorio")
		self.panel = PanelObjetivos(
			self.padre,
			self.formulario.contexto,
			self.letras,
			etiqueta=_con_dos_puntos(str(self.campo.etiqueta)),
			premios=self.formulario.premios_actuales,
			con_orden=self._con_orden,
		)
		self.sizer.Add(self.panel, 1, wx.EXPAND)
		self.ventanas.append(self.panel)
		self.principal = self.panel.lista
		self.panel.lista.SetHelpText(str(getattr(self.campo, "ayuda", "") or "") + " " + self.panel.lista.GetHelpText())

	def poner(self, valor: Any) -> None:
		self.panel.poner(valor if isinstance(valor, list) else [])

	def leer(self) -> list[dict[str, Any]]:
		return self.panel.leer()

	def cargar(self, datos: dict[str, Any]) -> None:
		super().cargar(datos)
		if self._con_orden and self.panel.orden is not None:
			self.panel.orden.SetValue(bool(datos.get("orden_obligatorio", False)))

	def volcar(self, datos: dict[str, Any]) -> None:
		super().volcar(datos)
		if self._con_orden and self.panel.orden is not None:
			datos["orden_obligatorio"] = bool(self.panel.orden.GetValue())


class EditorAyudas(EditorCampo):
	"""La tabla de ayudas permitidas y, en un diálogo aparte, los niveles de retirada progresiva."""

	expande = True

	def crear(self) -> None:
		contexto = self.formulario.contexto
		self.niveles: list[dict[str, Any]] = []
		self.panel = PanelAyudas(
			self.padre, self.letras, None, getattr(contexto, "configuracion", None), etiqueta=_con_dos_puntos(str(self.campo.etiqueta))
		)
		self.sizer.Add(self.panel, 1, wx.EXPAND)
		self.ventanas.append(self.panel)
		self.principal = self.panel.lista
		self.resumen_niveles = crear_texto(
			self.padre,
			self.letras.poner(_("Niveles de retirada progresiva:")),
			lectura=True,
			ayuda=_(
				"Cuántos niveles propios tiene esta actividad. Cada nivel retira alguna ayuda al anterior y el alumno sube de nivel "
				"cuando completa la actividad sin pistas. Se editan con el botón siguiente."
			),
		)
		self.sizer.Add(self.resumen_niveles.GetPrevSibling(), 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		self.sizer.Add(self.resumen_niveles, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		self.boton_niveles = crear_boton(
			self.padre,
			self.letras.poner(_("Editar los niveles...")),
			self.editar_niveles,
			_("Abre la lista de niveles: añadir, editar, ordenar o poner los cuatro de serie."),
		)
		self.sizer.Add(self.boton_niveles, 0, wx.LEFT | wx.BOTTOM, 5)
		self.ventanas.extend([self.resumen_niveles.GetPrevSibling(), self.resumen_niveles, self.boton_niveles])

	def _pintar_niveles(self) -> None:
		if self.niveles:
			nombres = ", ".join(pres.resumen_nivel(nivel)[0] for nivel in self.niveles)
			texto = _("{n} niveles propios: {nombres}.").format(n=len(self.niveles), nombres=nombres)
		else:
			texto = _("Sin niveles propios: si se retiran las ayudas por niveles, se usan los cuatro de serie.")
		poner_texto(self.resumen_niveles, texto)

	def poner(self, valor: Any) -> None:
		self.panel.poner(valor if isinstance(valor, dict) else {})

	def leer(self) -> dict[str, Any]:
		return self.panel.leer()

	def cargar(self, datos: dict[str, Any]) -> None:
		super().cargar(datos)
		niveles = datos.get("niveles")
		self.niveles = [copy.deepcopy(nivel) for nivel in niveles if isinstance(nivel, dict)] if isinstance(niveles, list) else []
		self._pintar_niveles()

	def volcar(self, datos: dict[str, Any]) -> None:
		super().volcar(datos)
		if self.niveles or "niveles" in datos:
			datos["niveles"] = copy.deepcopy(self.niveles)

	def editar_niveles(self) -> None:
		"""Abre el diálogo de los niveles."""
		contexto = self.formulario.contexto
		dialogo = DialogoNiveles(self.padre.GetTopLevelParent(), self.niveles, getattr(contexto, "configuracion", None))
		try:
			mostrar_modal(dialogo)
			if dialogo.aceptado:
				self.niveles = dialogo.niveles
		finally:
			dialogo.Destroy()
		self._pintar_niveles()
		self.resumen_niveles.SetFocus()


class EditorDesconocido(EditorTexto):
	"""Campo de un tipo que este editor no conoce: se enseña, pero no se toca.

	Convertir a texto un valor que quizá sea una lista o un diccionario lo
	estropearía al guardar; es preferible conservarlo tal como estaba.
	"""

	def crear(self) -> None:
		super().crear()
		self.control.SetEditable(False)
		self.control.SetHelpText(_("Este dato es de un tipo que esta versión del programa no sabe editar. Se conserva como está."))

	def volcar(self, datos: dict[str, Any]) -> None:
		"""No escribe nada: el valor original se queda en la actividad."""


#: Tipo de campo del esquema → clase que lo edita.
EDITORES: dict[str, type[EditorCampo]] = {
	"texto": EditorTexto,
	"texto_largo": EditorTexto,
	"entero": EditorNumero,
	"decimal": EditorNumero,
	"si_no": EditorSiNo,
	"opcion": EditorOpcion,
	"sonido": EditorSonido,
	"posicion": EditorPosicion,
	"elemento": EditorElemento,
	"lista_premios": EditorPremios,
	"lista_objetivos": EditorObjetivos,
	"ayudas": EditorAyudas,
}


def registrar(tipo: str, clase: type[EditorCampo]) -> None:
	"""Apunta el editor de un tipo de campo nuevo (o sustituye el de uno existente)."""
	EDITORES[tipo] = clase


def crear_editor(padre: wx.Window, campo: Any, letras: Letras, formulario: Any) -> EditorCampo:
	"""El editor que corresponde al tipo del campo; uno de solo lectura si el tipo no se conoce.

	Un tipo desconocido (un esquema más nuevo que este editor) no impide
	abrir la actividad: su valor se enseña sin dejar cambiarlo y se avisa en el registro.
	"""
	clase = EDITORES.get(str(getattr(campo, "tipo", "")))
	if clase is None:
		log.warning("Tipo de campo desconocido en el esquema de actividades: %s; se enseña sin editar", getattr(campo, "tipo", ""))
		clase = EditorDesconocido
	return clase(padre, campo, letras, formulario)
