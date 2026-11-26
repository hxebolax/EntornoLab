"""Editor de la lista de objetivos de una actividad (ir a un lugar, recoger, entregar, salir, señalar...)."""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable, Sequence
from typing import Any

import wx

from app.core.i18n import _
from app.ui.seguimiento import presentador_actividades as pres
from app.ui.seguimiento import textos
from app.ui.seguimiento.comun import (
	DialogoFormulario,
	Problema,
	crear_boton,
	crear_desplegable,
	crear_lista,
	crear_texto,
	mostrar_modal,
	poner_texto,
)
from app.ui.seguimiento.selector_lugar import DialogoElemento, DialogoLugar
from app.ui.seguimiento.textos import Letras

log = logging.getLogger(__name__)

# Clases de elemento que tiene sentido ofrecer como destino de cada tipo de objetivo.
_CLASES_POR_TIPO: dict[str, list[str]] = {
	"salir": ["salida"],
	"localizar": ["espacio"],
}
_CLASES_GENERALES = ["espacio", "objeto", "referencia", "abertura"]


class DialogoObjetivo(DialogoFormulario):
	"""Un objetivo: qué hay que hacer, dónde y qué se le dice al alumno."""

	def __init__(
		self,
		padre: wx.Window | None,
		entorno: Any,
		catalogo: Any = None,
		objetivo: dict[str, Any] | None = None,
		premios: Sequence[dict[str, Any]] = (),
	) -> None:
		super().__init__(padre, _("Objetivo"))
		self.entorno = entorno
		self.catalogo = catalogo
		self.premios = list(premios)
		self._original = copy.deepcopy(objetivo) if objetivo else {}
		self._destino: Any = self._original.get("destino")
		self.objetivo: dict[str, Any] = {}
		self._tipos = list(pres.TIPOS_OBJETIVO)
		tipo = self._original.get("tipo") if self._original.get("tipo") in self._tipos else "ir_a"
		self.tipo = crear_desplegable(
			self.panel,
			self.letras.poner(_("Qué hay que hacer:")),
			[textos.nombre(pres.TIPOS_OBJETIVO, clave) for clave in self._tipos],
			sizer=self.sizer,
			seleccion=self._tipos.index(tipo),
			ayuda=_("El tipo de objetivo."),
		)
		self.destino = crear_texto(
			self.panel,
			self.letras.poner(_("Dónde:")),
			sizer=self.sizer,
			lectura=True,
			ayuda=_("El lugar del objetivo, en palabras. Se elige con los dos botones siguientes."),
		)
		fila = wx.BoxSizer(wx.HORIZONTAL)
		crear_boton(
			self.panel,
			self.letras.poner(_("Elegir un elemento...")),
			self.elegir_elemento,
			_("Elige como lugar un espacio, un objeto, una puerta, una referencia o un premio de la actividad."),
			fila,
		)
		crear_boton(
			self.panel,
			self.letras.poner(_("Elegir un punto...")),
			self.elegir_punto,
			_("Elige como lugar un punto cualquiera: en el centro de un espacio, junto a algo, en una esquina o por coordenadas."),
			fila,
		)
		crear_boton(self.panel, self.letras.poner(_("Quitar el lugar")), self.quitar_lugar, _("Deja el objetivo sin lugar."), fila)
		self.sizer.Add(fila, 0, wx.ALL, 2)
		self.texto = crear_texto(
			self.panel,
			self.letras.poner(_("Texto que se le dice al alumno (opcional):")),
			str(self._original.get("texto") or ""),
			sizer=self.sizer,
			multilinea=True,
			alto=70,
			ancho=460,
			ayuda=_("Lo que oye el alumno cuando le toca este objetivo. Vacío: una frase de serie."),
		)
		self._pintar_destino()
		self.terminar(self.tipo, tamano_minimo=(520, 380))

	def tipo_elegido(self) -> str:
		"""Tipo de objetivo del desplegable."""
		return self._tipos[max(0, self.tipo.GetSelection())]

	def _pintar_destino(self) -> None:
		poner_texto(self.destino, pres.describir_lugar(self.entorno, self._destino, self.premios))

	def elegir_elemento(self) -> None:
		"""Abre el selector de elementos y pone el elegido como lugar."""
		clases = _CLASES_POR_TIPO.get(self.tipo_elegido(), _CLASES_GENERALES)
		dialogo = DialogoElemento(
			self,
			self.entorno,
			self.catalogo,
			clases,
			self._destino if isinstance(self._destino, str) else "",
			_("Lugar del objetivo"),
			premios=self.premios if self.tipo_elegido() in ("recoger", "ir_a") else (),
		)
		try:
			mostrar_modal(dialogo)
			if dialogo.aceptado:
				self._destino = dialogo.valor
		finally:
			dialogo.Destroy()
		self._pintar_destino()
		self.destino.SetFocus()

	def elegir_punto(self) -> None:
		"""Abre el selector de puntos y pone el elegido como lugar."""
		dialogo = DialogoLugar(
			self, self.entorno, self.catalogo, _("Punto del objetivo"), self._destino if isinstance(self._destino, dict) else None
		)
		try:
			mostrar_modal(dialogo)
			if dialogo.aceptado and dialogo.valor is not None:
				self._destino = {"planta": dialogo.valor["planta"], "x": dialogo.valor["x"], "y": dialogo.valor["y"]}
		finally:
			dialogo.Destroy()
		self._pintar_destino()
		self.destino.SetFocus()

	def quitar_lugar(self) -> None:
		"""Deja el objetivo sin lugar."""
		self._destino = None
		self._pintar_destino()

	def validar(self) -> Problema | None:
		tipo = self.tipo_elegido()
		if not self._destino and tipo != "salir":
			return _("Elija el lugar del objetivo con «Elegir un elemento» o «Elegir un punto»."), self.destino
		objetivo = dict(self._original)
		objetivo.update({"tipo": tipo, "destino": self._destino, "texto": self.texto.GetValue().strip()})
		self.objetivo = objetivo
		return None


class PanelObjetivos(wx.Panel):
	"""Lista ordenada de objetivos con sus botones."""

	def __init__(
		self,
		padre: wx.Window,
		contexto: Any,
		letras: Letras,
		objetivos: list[dict[str, Any]] | None = None,
		etiqueta: str = "",
		premios: Callable[[], Sequence[dict[str, Any]]] | None = None,
		con_orden: bool = False,
		orden_obligatorio: bool = False,
	) -> None:
		super().__init__(padre, name=_("Objetivos"))
		self.contexto = contexto
		self._premios = premios or (lambda: ())
		self.objetivos: list[dict[str, Any]] = []
		columna = wx.BoxSizer(wx.VERTICAL)
		self.lista = crear_lista(
			self,
			letras.poner(etiqueta or _("Objetivos, en orden:")),
			[(_("Qué hay que hacer"), 200), (_("Dónde"), 240), (_("Texto"), 240)],
			getattr(contexto, "configuracion", None),
			sizer=columna,
			alto=170,
			ayuda=_("Cada fila es un objetivo. Intro lo edita y Suprimir lo quita. Izquierda y derecha leen las columnas."),
		)
		fila = wx.WrapSizer(wx.HORIZONTAL)
		crear_boton(self, letras.poner(_("Añadir objetivo...")), self.anadir, _("Añade un objetivo al final de la lista."), fila)
		crear_boton(self, letras.poner(_("Editar objetivo...")), self.editar, _("Edita el objetivo elegido."), fila)
		crear_boton(self, letras.poner(_("Quitar objetivo")), self.quitar, _("Quita el objetivo elegido."), fila)
		crear_boton(
			self, letras.poner(_("Subir objetivo")), lambda: self.mover(-1), _("Mueve el objetivo elegido un puesto hacia arriba."), fila
		)
		crear_boton(
			self, letras.poner(_("Bajar objetivo")), lambda: self.mover(1), _("Mueve el objetivo elegido un puesto hacia abajo."), fila
		)
		columna.Add(fila, 0, wx.ALL, 2)
		self.orden: wx.CheckBox | None = None
		if con_orden:
			self.orden = wx.CheckBox(self, label=letras.poner(_("Hay que cumplirlos en este orden")))
			self.orden.SetValue(orden_obligatorio)
			self.orden.SetHelpText(
				_("Marcada: el orden de la lista es obligatorio. Sin marcar: el alumno puede cumplirlos en el orden que quiera.")
			)
			columna.Add(self.orden, 0, wx.ALL, 5)
		self.SetSizer(columna)
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.editar())
		self.lista.Bind(wx.EVT_KEY_DOWN, self._tecla)
		self.poner(objetivos)

	def _tecla(self, evento: wx.KeyEvent) -> None:
		if evento.GetKeyCode() == wx.WXK_DELETE and evento.GetModifiers() == wx.MOD_NONE:  # atajo: Supr
			self.quitar()
			return
		evento.Skip()

	def poner(self, objetivos: list[dict[str, Any]] | None) -> None:
		"""Carga una lista de objetivos (se copian)."""
		self.objetivos = [copy.deepcopy(objetivo) for objetivo in (objetivos or []) if isinstance(objetivo, dict)]
		self.recargar()

	def leer(self) -> list[dict[str, Any]]:
		"""Los objetivos, en orden."""
		return [copy.deepcopy(objetivo) for objetivo in self.objetivos]

	def recargar(self, fila: int | None = None) -> None:
		"""Vuelve a pintar la lista."""
		entorno = getattr(self.contexto, "entorno", None)
		premios = list(self._premios())
		self.lista.reemplazar_filas([pres.fila_objetivo(objetivo, entorno, premios) for objetivo in self.objetivos])
		if fila is not None:
			self.lista.enfocar_fila(fila, anunciar=False)

	def _pedir(self, objetivo: dict[str, Any] | None) -> dict[str, Any] | None:
		dialogo = DialogoObjetivo(
			self.GetTopLevelParent(),
			getattr(self.contexto, "entorno", None),
			getattr(self.contexto, "catalogo", None),
			objetivo,
			list(self._premios()),
		)
		try:
			mostrar_modal(dialogo)
			return dialogo.objetivo if dialogo.aceptado else None
		finally:
			dialogo.Destroy()

	def anadir(self) -> None:
		"""Añade un objetivo."""
		objetivo = self._pedir(None)
		if objetivo is not None:
			objetivo.setdefault("id", pres.id_objetivo_unico(self.objetivos))
			self.objetivos.append(objetivo)
			self.recargar(len(self.objetivos) - 1)
		self.lista.SetFocus()

	def editar(self) -> None:
		"""Edita el objetivo elegido."""
		fila = self.lista.fila_actual()
		if not 0 <= fila < len(self.objetivos):
			return
		objetivo = self._pedir(self.objetivos[fila])
		if objetivo is not None:
			self.objetivos[fila] = objetivo
			self.recargar(fila)
		self.lista.SetFocus()

	def quitar(self) -> None:
		"""Quita el objetivo elegido."""
		fila = self.lista.fila_actual()
		if 0 <= fila < len(self.objetivos):
			del self.objetivos[fila]
			self.recargar(min(fila, len(self.objetivos) - 1) if self.objetivos else None)

	def mover(self, delta: int) -> None:
		"""Sube o baja el objetivo elegido."""
		self.recargar(pres.mover(self.objetivos, self.lista.fila_actual(), delta))
