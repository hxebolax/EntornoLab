"""Selectores accesibles de un punto y de un elemento del entorno, sin plano.

Quien no ve el plano elige un lugar bajando por listas: planta, espacio y,
dentro del espacio, «dentro de un objeto», «junto a algo», «en el centro»,
«en una esquina» o unas coordenadas. Lo elegido se describe siempre en
palabras en un campo de solo lectura, que se actualiza con cada cambio.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence
from typing import Any

import wx

from app.core.i18n import N_, _
from app.ui.seguimiento import lugares, textos
from app.ui.seguimiento.comun import DialogoFormulario, Problema, crear_desplegable, crear_texto, poner_opciones, poner_texto
from app.ui.seguimiento.textos import Letras, leer_numero, texto_numero

log = logging.getLogger(__name__)


_CLASES_EXTRA: dict[str, str] = {
	"conector": N_("Escaleras, rampas y ascensores"),
	"fuente": N_("Sonidos fijos"),
	"premio": N_("Premios de esta actividad"),
}


class ErrorLugar(ValueError):
	"""Lo elegido no es un lugar válido. Lleva el control que hay que corregir."""

	def __init__(self, mensaje: str, control: wx.Window | None = None) -> None:
		super().__init__(mensaje)
		self.control = control


class PanelLugar(wx.Panel):
	"""Controles para elegir un punto del entorno: planta, espacio y dónde dentro del espacio."""

	def __init__(
		self,
		padre: wx.Window,
		entorno: Any,
		catalogo: Any,
		letras: Letras,
		con_contenedores: bool = False,
		con_rumbo: bool = False,
		al_cambiar: Callable[[], None] | None = None,
	) -> None:
		super().__init__(padre, name=_("Lugar"))
		self.entorno = entorno
		self.catalogo = catalogo
		self.con_contenedores = con_contenedores
		self.con_rumbo = con_rumbo
		self._al_cambiar = al_cambiar
		self._plantas = lugares.plantas(entorno)
		self._espacios: list[Any] = []
		self._elementos: list[Any] = []
		self._modos = [modo for modo in lugares.MODOS_PUNTO if con_contenedores or modo != lugares.DENTRO]
		self._esquinas = list(lugares.ESQUINAS)
		columna = wx.BoxSizer(wx.VERTICAL)
		self.planta = crear_desplegable(
			self,
			letras.poner(_("Planta:")),
			[lugares.nombre_de(planta) for planta in self._plantas],
			sizer=columna,
			ayuda=_("Planta del entorno en la que está el lugar."),
		)
		self.espacio = crear_desplegable(
			self,
			letras.poner(_("Espacio:")),
			sizer=columna,
			ayuda=_("Habitación, pasillo o zona de esa planta."),
		)
		self.modo = crear_desplegable(
			self,
			letras.poner(_("Dónde, dentro del espacio:")),
			[textos.nombre(lugares.MODOS_PUNTO, modo) for modo in self._modos],
			sizer=columna,
			ayuda=_(
				"Cómo se indica el punto: dentro de un objeto, junto a algo, en el centro, en una esquina o con coordenadas. "
				"Según lo que elija aparecen debajo los campos que hacen falta."
			),
		)
		self.etiqueta_elemento = wx.StaticText(self, label=letras.poner(_("Objeto o elemento:")))
		self.elemento = wx.Choice(self, name=_("Objeto o elemento"))
		self.elemento.SetHelpText(_("El objeto que esconde el premio, o aquello junto a lo que se pone el punto."))
		columna.Add(self.etiqueta_elemento, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		columna.Add(self.elemento, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		self.etiqueta_esquina = wx.StaticText(self, label=letras.poner(_("Esquina:")))
		self.esquina = wx.Choice(self, choices=[textos.nombre(lugares.ESQUINAS, clave) for clave in self._esquinas], name=_("Esquina"))
		self.esquina.SetSelection(0)
		self.esquina.SetHelpText(_("El norte es hacia arriba del plano: la esquina noreste es la del fondo a la derecha mirando al norte."))
		columna.Add(self.etiqueta_esquina, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		columna.Add(self.esquina, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		self.etiqueta_x = wx.StaticText(self, label=letras.poner(_("Coordenada X, en metros hacia el este:")))
		self.x = wx.TextCtrl(self, name=_("Coordenada X"))
		self.x.SetHelpText(_("Metros hacia el este desde el origen del plano. Admite decimales con coma."))
		columna.Add(self.etiqueta_x, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		columna.Add(self.x, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		self.etiqueta_y = wx.StaticText(self, label=letras.poner(_("Coordenada Y, en metros hacia el norte:")))
		self.y = wx.TextCtrl(self, name=_("Coordenada Y"))
		self.y.SetHelpText(_("Metros hacia el norte desde el origen del plano. Admite decimales con coma."))
		columna.Add(self.etiqueta_y, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		columna.Add(self.y, 0, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		self.rumbo: wx.Choice | None = None
		if con_rumbo:
			self.rumbo = crear_desplegable(
				self,
				letras.poner(_("Mirando hacia el:")),
				[nombre.capitalize() for nombre in (_(n) for _g, n in textos.RUMBOS)],
				sizer=columna,
				ayuda=_("Hacia dónde mira el alumno al empezar en este punto."),
			)
		self.descripcion = crear_texto(
			self,
			letras.poner(_("Lugar elegido, en palabras:")),
			sizer=columna,
			multilinea=True,
			lectura=True,
			alto=54,
			ancho=420,
			ayuda=_("Dice con palabras el lugar que resulta de lo elegido arriba. Se actualiza solo."),
		)
		self.SetSizer(columna)
		self.planta.Bind(wx.EVT_CHOICE, lambda _evento: self._cambio_planta())
		self.espacio.Bind(wx.EVT_CHOICE, lambda _evento: self._cambio_espacio())
		self.modo.Bind(wx.EVT_CHOICE, lambda _evento: self._cambio_modo())
		self.elemento.Bind(wx.EVT_CHOICE, lambda _evento: self._actualizar())
		self.esquina.Bind(wx.EVT_CHOICE, lambda _evento: self._actualizar())
		self.x.Bind(wx.EVT_TEXT, lambda _evento: self._actualizar())
		self.y.Bind(wx.EVT_TEXT, lambda _evento: self._actualizar())
		if self.rumbo is not None:
			self.rumbo.Bind(wx.EVT_CHOICE, lambda _evento: self._actualizar())
		self._cambio_planta()

	# ── Estado ───────────────────────────────────────────────────────────────

	def planta_elegida(self) -> Any | None:
		"""La planta del desplegable, o ``None`` si el entorno no tiene plantas."""
		indice = self.planta.GetSelection()
		return self._plantas[indice] if 0 <= indice < len(self._plantas) else None

	def espacio_elegido(self) -> Any | None:
		"""El espacio del desplegable, o ``None``."""
		indice = self.espacio.GetSelection()
		return self._espacios[indice] if 0 <= indice < len(self._espacios) else None

	def modo_elegido(self) -> str:
		"""Forma de indicar el punto (``dentro``, ``junto``, ``centro``, ``esquina`` o ``coordenadas``)."""
		indice = self.modo.GetSelection()
		return self._modos[indice] if 0 <= indice < len(self._modos) else lugares.CENTRO

	def elemento_elegido(self) -> Any | None:
		"""El objeto o elemento del desplegable, o ``None``."""
		indice = self.elemento.GetSelection()
		return self._elementos[indice] if 0 <= indice < len(self._elementos) else None

	def _cambio_planta(self) -> None:
		self._espacios = lugares.espacios(self.planta_elegida())
		poner_opciones(self.espacio, [lugares.nombre_de(espacio) for espacio in self._espacios])
		self._cambio_espacio()

	def _cambio_espacio(self) -> None:
		self._cargar_elementos()
		self._actualizar()

	def _cambio_modo(self) -> None:
		self._cargar_elementos()
		self._mostrar_segun_modo()
		self._actualizar()

	def _cargar_elementos(self) -> None:
		planta, espacio = self.planta_elegida(), self.espacio_elegido()
		if self.modo_elegido() == lugares.DENTRO:
			self._elementos = lugares.contenedores(planta, espacio, self.catalogo)
		else:
			self._elementos = lugares.vecinos(planta, espacio)
		self.elemento.Set([lugares.nombre_de(elemento) for elemento in self._elementos])
		if self._elementos:
			self.elemento.SetSelection(0)
		self._mostrar_segun_modo()

	def _mostrar_segun_modo(self) -> None:
		modo = self.modo_elegido()
		visibles = {
			self.etiqueta_elemento: modo in (lugares.DENTRO, lugares.JUNTO),
			self.elemento: modo in (lugares.DENTRO, lugares.JUNTO),
			self.etiqueta_esquina: modo == lugares.ESQUINA,
			self.esquina: modo == lugares.ESQUINA,
			self.etiqueta_x: modo == lugares.COORDENADAS,
			self.x: modo == lugares.COORDENADAS,
			self.etiqueta_y: modo == lugares.COORDENADAS,
			self.y: modo == lugares.COORDENADAS,
		}
		cambio = False
		for control, visible in visibles.items():
			if control.IsShown() != visible:
				control.Show(visible)
				cambio = True
		if cambio:
			self.Layout()
			superior = self.GetTopLevelParent()
			if superior is not None:
				superior.Layout()

	def _actualizar(self) -> None:
		try:
			valor = self.leer()
		except ErrorLugar as error:
			poner_texto(self.descripcion, str(error))
		else:
			poner_texto(self.descripcion, self.describir(valor))
		if self._al_cambiar is not None:
			self._al_cambiar()

	def describir(self, valor: dict[str, Any]) -> str:
		"""El lugar en palabras, con el rumbo si se pide."""
		texto = lugares.describir_punto(self.entorno, valor["planta"], valor["x"], valor["y"], valor.get("dentro_de"))
		rumbo = textos.cardinal(valor.get("rumbo")) if self.con_rumbo else ""
		if rumbo:
			texto = _("{lugar}, mirando al {rumbo}").format(lugar=texto, rumbo=rumbo)
		return texto[:1].upper() + texto[1:] + "."

	# ── Valor ────────────────────────────────────────────────────────────────

	def poner(self, valor: dict[str, Any] | None) -> None:
		"""Muestra un lugar ya guardado (planta, x, y y quizá ``dentro_de`` y ``rumbo``)."""
		if not isinstance(valor, dict) or not isinstance(valor.get("x"), (int, float)) or not isinstance(valor.get("y"), (int, float)):
			self._seleccionar_modo(lugares.DENTRO if self.con_contenedores else lugares.CENTRO)
			return
		planta, espacio = lugares.espacio_en(self.entorno, str(valor.get("planta") or ""), valor["x"], valor["y"])
		if planta in self._plantas:
			self.planta.SetSelection(self._plantas.index(planta))
			self._espacios = lugares.espacios(planta)
			poner_opciones(self.espacio, [lugares.nombre_de(e) for e in self._espacios])
		if espacio in self._espacios:
			self.espacio.SetSelection(self._espacios.index(espacio))
		dentro = valor.get("dentro_de")
		if dentro and self.con_contenedores:
			self._seleccionar_modo(lugares.DENTRO)
			for indice, elemento in enumerate(self._elementos):
				if elemento.id == dentro:
					self.elemento.SetSelection(indice)
					break
		else:
			# Un punto ya guardado se enseña con sus coordenadas, para no moverlo al aceptar sin tocar nada.
			self.x.ChangeValue(texto_numero(float(valor["x"])))
			self.y.ChangeValue(texto_numero(float(valor["y"])))
			self._seleccionar_modo(lugares.COORDENADAS)
		if self.rumbo is not None and isinstance(valor.get("rumbo"), (int, float)):
			self.rumbo.SetSelection(int(((float(valor["rumbo"]) % 360.0) + 22.5) // 45.0) % 8)
		self._actualizar()

	def _seleccionar_modo(self, modo: str) -> None:
		if modo in self._modos:
			self.modo.SetSelection(self._modos.index(modo))
		self._cambio_modo()

	def leer(self) -> dict[str, Any]:
		"""El lugar elegido. Lanza ``ErrorLugar`` si falta algo, con el control que hay que corregir."""
		planta = self.planta_elegida()
		if planta is None:
			raise ErrorLugar(_("El entorno no tiene ninguna planta."), self.planta)
		espacio = self.espacio_elegido()
		if espacio is None:
			raise ErrorLugar(_("Esta planta no tiene ningún espacio en el que se pueda estar."), self.planta)
		modo = self.modo_elegido()
		dentro_de: str | None = None
		if modo == lugares.COORDENADAS:
			try:
				x = leer_numero(self.x.GetValue())
				y = leer_numero(self.y.GetValue())
			except ValueError:
				raise ErrorLugar(_("Las coordenadas deben ser números."), self.x) from None
			if x is None or y is None:
				raise ErrorLugar(_("Escriba las dos coordenadas, o elija otra forma de indicar el lugar."), self.x if x is None else self.y)
			punto = (float(x), float(y))
		elif modo in (lugares.DENTRO, lugares.JUNTO):
			elemento = self.elemento_elegido()
			if elemento is None:
				if modo == lugares.DENTRO:
					raise ErrorLugar(
						_(
							"En este espacio no hay ningún objeto dentro del que se pueda esconder algo. Elija otro espacio u otra forma de indicar el lugar."
						),
						self.modo,
					)
				raise ErrorLugar(
					_("En este espacio no hay objetos, puertas ni referencias. Elija otra forma de indicar el lugar."), self.modo
				)
			punto = lugares.calcular_punto(espacio, modo, elemento)
			if modo == lugares.DENTRO:
				dentro_de = elemento.id
		else:
			indice = self.esquina.GetSelection()
			punto = lugares.calcular_punto(espacio, modo, esquina=self._esquinas[indice] if indice >= 0 else "noreste")
		valor: dict[str, Any] = {"planta": planta.id, "x": round(punto[0], 2), "y": round(punto[1], 2), "dentro_de": dentro_de}
		if self.rumbo is not None:
			valor["rumbo"] = textos.RUMBOS[max(0, self.rumbo.GetSelection())][0]
		return valor


class DialogoLugar(DialogoFormulario):
	"""Diálogo para elegir un punto del entorno (el inicio de una actividad, dónde recolocar al alumno...)."""

	def __init__(
		self,
		padre: wx.Window | None,
		entorno: Any,
		catalogo: Any = None,
		titulo: str = "",
		valor: dict[str, Any] | None = None,
		con_contenedores: bool = False,
		con_rumbo: bool = False,
	) -> None:
		super().__init__(padre, titulo or _("Elegir un lugar"))
		self.valor: dict[str, Any] | None = None
		self.lugar = PanelLugar(self.panel, entorno, catalogo, self.letras, con_contenedores=con_contenedores, con_rumbo=con_rumbo)
		self.sizer.Add(self.lugar, 1, wx.EXPAND | wx.ALL, 4)
		self.lugar.poner(valor)
		self.terminar(self.lugar.planta, tamano_minimo=(480, 420))

	def validar(self) -> Problema | None:
		try:
			self.valor = self.lugar.leer()
		except ErrorLugar as error:
			return str(error), error.control
		return None


class DialogoElemento(DialogoFormulario):
	"""Diálogo para elegir un elemento del entorno por su clase, su planta y su espacio."""

	TODOS = -1

	def __init__(
		self,
		padre: wx.Window | None,
		entorno: Any,
		catalogo: Any = None,
		clases: Sequence[str] = ("espacio",),
		valor: str = "",
		titulo: str = "",
		premios: Sequence[dict[str, Any]] = (),
	) -> None:
		super().__init__(padre, titulo or _("Elegir un elemento del entorno"))
		self.entorno = entorno
		self.catalogo = catalogo
		self.valor: str = ""
		self._premios = [premio for premio in premios if isinstance(premio, dict) and premio.get("id")]
		self._clases = [clase for clase in clases if clase]
		if self._premios and "premio" not in self._clases:
			self._clases.append("premio")
		self._plantas = lugares.plantas(entorno)
		self._espacios: list[Any] = []
		self._ids: list[str] = []
		nombres_clase = {**textos.CLASES_ELEMENTO, **_CLASES_EXTRA}
		self.clase = crear_desplegable(
			self.panel,
			self.letras.poner(_("Clase de elemento:")),
			[_(nombres_clase.get(clase, clase)) for clase in self._clases],
			sizer=self.sizer,
			ayuda=_("Qué se busca: un espacio, un objeto, una puerta, una referencia..."),
		)
		self.planta = crear_desplegable(
			self.panel,
			self.letras.poner(_("Planta:")),
			[lugares.nombre_de(planta) for planta in self._plantas],
			sizer=self.sizer,
			ayuda=_("Planta en la que está el elemento."),
		)
		self.espacio = crear_desplegable(
			self.panel,
			self.letras.poner(_("Espacio en el que está:")),
			sizer=self.sizer,
			ayuda=_("Para acortar la lista a los elementos de un espacio. «Todos» los muestra todos."),
		)
		self.etiqueta_lista = wx.StaticText(self.panel, label=self.letras.poner(_("Elementos:")))
		self.lista = wx.ListBox(self.panel, style=wx.LB_SINGLE, size=wx.Size(420, 160), name=_("Elementos"))
		self.lista.SetHelpText(_("Elija el elemento con las flechas. Debajo se describe el que está elegido."))
		self.sizer.Add(self.etiqueta_lista, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		self.sizer.Add(self.lista, 1, wx.EXPAND | wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)
		self.descripcion = crear_texto(
			self.panel,
			self.letras.poner(_("Descripción del elegido:")),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=70,
			ancho=420,
			ayuda=_("Qué es, cuánto mide y dónde está el elemento elegido en la lista."),
		)
		self.clase.Bind(wx.EVT_CHOICE, lambda _evento: self._cambio_planta())
		self.planta.Bind(wx.EVT_CHOICE, lambda _evento: self._cambio_planta())
		self.espacio.Bind(wx.EVT_CHOICE, lambda _evento: self._cargar())
		self.lista.Bind(wx.EVT_LISTBOX, lambda _evento: self._describir())
		self.lista.Bind(wx.EVT_LISTBOX_DCLICK, lambda _evento: self.aceptar())
		self._situar(valor)
		self.terminar(self.lista, tamano_minimo=(480, 480))

	def clase_elegida(self) -> str:
		"""Clase de elemento del desplegable."""
		indice = self.clase.GetSelection()
		return self._clases[indice] if 0 <= indice < len(self._clases) else "espacio"

	def _situar(self, valor: str) -> None:
		"""Deja elegidos la clase, la planta y el elemento ``valor`` si existe."""
		encontrado = self.entorno.buscar(valor) if (self.entorno is not None and valor) else None
		if any(premio.get("id") == valor for premio in self._premios):
			self.clase.SetSelection(self._clases.index("premio"))
		elif encontrado is not None:
			planta, elemento = encontrado
			clase = _clase_de(elemento)
			if clase in self._clases:
				self.clase.SetSelection(self._clases.index(clase))
			elif clase == "abertura" and "salida" in self._clases:
				self.clase.SetSelection(self._clases.index("salida"))
			if planta in self._plantas:
				self.planta.SetSelection(self._plantas.index(planta))
		self._cambio_planta()
		if valor in self._ids:
			self.lista.SetSelection(self._ids.index(valor))
			self._describir()

	def _cambio_planta(self) -> None:
		indice = self.planta.GetSelection()
		planta = self._plantas[indice] if 0 <= indice < len(self._plantas) else None
		self._espacios = lugares.espacios(planta)
		opciones = [_("Todos los espacios"), *[lugares.nombre_de(espacio) for espacio in self._espacios]]
		if list(self.espacio.GetStrings()) != opciones:
			self.espacio.Set(opciones)
			self.espacio.SetSelection(0)
		clase = self.clase_elegida()
		# Estas clases no viven en una planta o en un espacio: sus filtros no tienen sentido.
		self.planta.Enable(clase not in ("premio", "conector"))
		self.espacio.Enable(clase not in ("premio", "conector", "espacio"))
		self._cargar()

	def _cargar(self) -> None:
		clase = self.clase_elegida()
		indice = self.planta.GetSelection()
		planta = self._plantas[indice] if 0 <= indice < len(self._plantas) else None
		espacio = self._espacios[self.espacio.GetSelection() - 1] if self.espacio.GetSelection() > 0 else None
		if clase == "premio":
			pares = [
				(str(premio["id"]), _("Premio «{nombre}»").format(nombre=premio.get("nombre") or premio["id"])) for premio in self._premios
			]
		elif clase == "conector":
			pares = [(conector.id, lugares.nombre_de(conector)) for conector in lugares.conectores(self.entorno)]
		else:
			pares = [
				(elemento.id, lugares.nombre_de(elemento)) for elemento in lugares.elementos_de_clase(planta, espacio, clase, self.catalogo)
			]
		self._ids = [ident for ident, _nombre in pares]
		self.lista.Set([nombre for _ident, nombre in pares])
		if pares:
			self.lista.SetSelection(0)
		self._describir()

	def _describir(self) -> None:
		indice = self.lista.GetSelection()
		if not 0 <= indice < len(self._ids):
			poner_texto(self.descripcion, _("No hay ningún elemento de esa clase en ese lugar."))
			return
		ident = self._ids[indice]
		if self.clase_elegida() == "premio":
			premio = next((p for p in self._premios if p.get("id") == ident), {})
			lugar = lugares.describir_punto(
				self.entorno, str(premio.get("planta") or ""), premio.get("x"), premio.get("y"), premio.get("dentro_de")
			)
			poner_texto(self.descripcion, _("Premio de esta actividad. Está en: {lugar}.").format(lugar=lugar))
			return
		poner_texto(self.descripcion, lugares.describir_elemento(self.entorno, ident, self.catalogo))

	def validar(self) -> Problema | None:
		indice = self.lista.GetSelection()
		if not 0 <= indice < len(self._ids):
			return _("Elija un elemento de la lista."), self.lista
		self.valor = self._ids[indice]
		return None


def _clase_de(elemento: Any) -> str:
	"""Clase («espacio», «objeto»...) de un elemento del modelo."""
	from app.dominio.modelo import Abertura, Conector, Espacio, FuenteSonido, Objeto, Referencia

	for clase, nombre in (
		(Espacio, "espacio"),
		(Objeto, "objeto"),
		(Abertura, "abertura"),
		(Referencia, "referencia"),
		(Conector, "conector"),
		(FuenteSonido, "fuente"),
	):
		if isinstance(elemento, clase):
			return nombre
	return ""
