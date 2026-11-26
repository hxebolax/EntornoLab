"""Editor de las ayudas permitidas y de los niveles de retirada progresiva.

La tabla es una lista nativa de tres columnas (ayuda, estado y límite de
usos). Cada ayuda puede quedar «como en la ficha del alumno», permitida (con
o sin límite) o prohibida; se cambia con botones, que es lo que un lector de
pantalla anuncia sin ambigüedad. La misma tabla sirve en el formulario de la
actividad, en cada nivel de retirada y en la supervisión en vivo.
"""

from __future__ import annotations

import copy
import logging
from collections.abc import Callable
from typing import Any

import wx

from app.core.i18n import _
from app.ui.accesibilidad.dialogos import pedir_texto
from app.ui.seguimiento import presentador_actividades as pres
from app.ui.seguimiento import textos
from app.ui.seguimiento.comun import DialogoFormulario, Problema, crear_boton, crear_desplegable, crear_lista, crear_texto, mostrar_modal
from app.ui.seguimiento.textos import Letras, leer_numero

log = logging.getLogger(__name__)


class PanelAyudas(wx.Panel):
	"""Tabla de ayudas con su estado y su límite de usos."""

	def __init__(
		self,
		padre: wx.Window,
		letras: Letras,
		reglas: dict[str, Any] | None = None,
		configuracion: Any = None,
		etiqueta: str = "",
		al_cambiar: Callable[[], None] | None = None,
	) -> None:
		super().__init__(padre, name=_("Ayudas permitidas"))
		self._al_cambiar = al_cambiar
		self._reglas: dict[str, Any] = {}
		self._claves: list[str] = []
		columna = wx.BoxSizer(wx.VERTICAL)
		self.lista = crear_lista(
			self,
			letras.poner(etiqueta or _("Ayudas permitidas:")),
			[(_("Ayuda"), 230), (_("Estado"), 210), (_("Límite de usos"), 110)],
			configuracion,
			sizer=columna,
			alto=200,
			ayuda=_(
				"Cada fila es una ayuda del alumno: su nombre, si está permitida, prohibida o como diga su ficha, y cuántas veces "
				"puede usarla. Elija una fila y use los botones de debajo para cambiarla. Izquierda y derecha leen las columnas."
			),
		)
		fila = wx.WrapSizer(wx.HORIZONTAL)
		self.boton_permitir = crear_boton(
			self,
			letras.poner(_("Permitir")),
			lambda: self.cambiar(pres.PERMITIDA),
			_("Permite la ayuda elegida, sin límite de usos."),
			fila,
		)
		self.boton_prohibir = crear_boton(
			self,
			letras.poner(_("Prohibir")),
			lambda: self.cambiar(pres.PROHIBIDA),
			_("Prohíbe la ayuda elegida: el alumno no podrá usarla."),
			fila,
		)
		self.boton_ficha = crear_boton(
			self,
			letras.poner(_("Dejar como en la ficha")),
			lambda: self.cambiar(pres.SIN_INDICAR),
			_("La ayuda elegida deja de estar indicada aquí: vale lo que diga la ficha del alumno."),
			fila,
		)
		self.boton_limite = crear_boton(
			self,
			letras.poner(_("Límite de usos...")),
			self.pedir_limite,
			_("Pone cuántas veces puede usar el alumno la ayuda elegida. Vacío: sin límite."),
			fila,
		)
		columna.Add(fila, 0, wx.ALL, 2)
		self.SetSizer(columna)
		self.poner(reglas)

	def poner(self, reglas: dict[str, Any] | None) -> None:
		"""Carga unas reglas de ayudas (se copian)."""
		self._reglas = {str(clave): copy.deepcopy(valor) for clave, valor in (reglas or {}).items()} if isinstance(reglas, dict) else {}
		self._claves = pres.claves_ayudas(self._reglas)
		self.lista.reemplazar_filas([pres.fila_ayuda(clave, self._reglas.get(clave)) for clave in self._claves])

	def leer(self) -> dict[str, dict[str, Any]]:
		"""Reglas indicadas (las ayudas «como en la ficha» no aparecen)."""
		resultado: dict[str, dict[str, Any]] = {}
		for clave, regla in self._reglas.items():
			completa = pres.regla_completa(regla)
			if completa is not None:
				resultado[clave] = completa
		return resultado

	def clave_elegida(self) -> str | None:
		"""Clave de la ayuda de la fila enfocada."""
		fila = self.lista.fila_actual()
		return self._claves[fila] if 0 <= fila < len(self._claves) else None

	def _repintar(self, clave: str) -> None:
		fila = self._claves.index(clave)
		self.lista.actualizar_fila(fila, pres.fila_ayuda(clave, self._reglas.get(clave)))
		if self._al_cambiar is not None:
			self._al_cambiar()

	def cambiar(self, estado: str, limite: int | None = None) -> None:
		"""Pone la ayuda elegida en ``estado``."""
		clave = self.clave_elegida()
		if clave is None:
			return
		pres.cambiar_ayuda(self._reglas, clave, estado, limite)
		self._repintar(clave)

	def pedir_limite(self) -> None:
		"""Pregunta el límite de usos de la ayuda elegida y la deja permitida con él."""
		clave = self.clave_elegida()
		if clave is None:
			return
		completa = pres.regla_completa(self._reglas.get(clave))
		actual = "" if completa is None or completa["limite"] is None else str(completa["limite"])
		escrito = pedir_texto(
			self.GetTopLevelParent(),
			_("&Usos permitidos de «{ayuda}» (vacío, sin límite):").format(ayuda=textos.nombre(textos.AYUDAS, clave)),
			_("Límite de usos"),
			actual,
			max_caracteres=4,
		)
		if escrito is None:
			return
		try:
			limite = leer_numero(escrito, entero=True)
		except ValueError:
			limite = None
			log.debug("Límite de usos no numérico: se deja sin límite")
		if limite is not None and limite < 0:
			limite = None
		pres.cambiar_ayuda(self._reglas, clave, pres.PERMITIDA, int(limite) if limite is not None else None)
		self._repintar(clave)
		self.lista.SetFocus()


class DialogoAyudas(DialogoFormulario):
	"""La tabla de ayudas en un diálogo (para cambiar las ayudas de un alumno durante la supervisión)."""

	def __init__(self, padre: wx.Window | None, reglas: dict[str, Any] | None = None, titulo: str = "", configuracion: Any = None) -> None:
		super().__init__(padre, titulo or _("Ayudas permitidas"))
		self.tabla = PanelAyudas(self.panel, self.letras, reglas, configuracion)
		self.sizer.Add(self.tabla, 1, wx.EXPAND | wx.ALL, 4)
		self.reglas: dict[str, dict[str, Any]] = {}
		self.terminar(self.tabla.lista, tamano_minimo=(620, 420))

	def validar(self) -> Problema | None:
		self.reglas = self.tabla.leer()
		return None


class DialogoNivel(DialogoFormulario):
	"""Un nivel de retirada: su nombre, cómo se usa la baliza y qué ayudas cambia."""

	def __init__(self, padre: wx.Window | None, nivel: dict[str, Any] | None = None, configuracion: Any = None) -> None:
		super().__init__(padre, _("Nivel de retirada de ayudas"))
		nivel = nivel or {"nombre": "", "baliza": "nunca", "ayudas": {}}
		self.nivel: dict[str, Any] = {}
		self.nombre = crear_texto(
			self.panel,
			self.letras.poner(_("Nombre del nivel:")),
			str(nivel.get("nombre") or ""),
			sizer=self.sizer,
			ayuda=_("Se le dice al alumno cuando sube de nivel, por ejemplo «Sin baliza»."),
		)
		self._balizas = list(pres.MODOS_BALIZA)
		baliza = nivel.get("baliza") if nivel.get("baliza") in self._balizas else "nunca"
		self.baliza = crear_desplegable(
			self.panel,
			self.letras.poner(_("Baliza hacia el objetivo:")),
			[textos.nombre(pres.MODOS_BALIZA, clave) for clave in self._balizas],
			sizer=self.sizer,
			seleccion=self._balizas.index(baliza),
			ayuda=_("En este nivel la baliza suena siempre, solo al pedir una pista o nunca."),
		)
		self.tabla = PanelAyudas(
			self.panel,
			self.letras,
			nivel.get("ayudas") if isinstance(nivel.get("ayudas"), dict) else {},
			configuracion,
			etiqueta=_("Ayudas que cambia este nivel:"),
		)
		self.sizer.Add(self.tabla, 1, wx.EXPAND | wx.ALL, 4)
		self.terminar(self.nombre, tamano_minimo=(620, 520))

	def validar(self) -> Problema | None:
		nombre = self.nombre.GetValue().strip()
		if not nombre:
			return _("Escriba el nombre del nivel."), self.nombre
		self.nivel = {"nombre": nombre, "baliza": self._balizas[self.baliza.GetSelection()], "ayudas": self.tabla.leer()}
		return None


class DialogoNiveles(DialogoFormulario):
	"""Niveles de retirada progresiva de ayudas: lista ordenada, del más fácil al más difícil."""

	def __init__(self, padre: wx.Window | None, niveles: list[dict[str, Any]] | None = None, configuracion: Any = None) -> None:
		super().__init__(padre, _("Niveles de retirada progresiva de ayudas"))
		self.configuracion = configuracion
		self.niveles: list[dict[str, Any]] = [copy.deepcopy(nivel) for nivel in (niveles or []) if isinstance(nivel, dict)]
		crear_texto(
			self.panel,
			self.letras.poner(_("Cómo funcionan:")),
			_(
				"El alumno empieza en el nivel de partida y sube al siguiente cuando completa la actividad sin pedir pistas. "
				"Cada nivel retira alguna ayuda al anterior. Con la lista vacía se usan los cuatro niveles de serie."
			),
			sizer=self.sizer,
			multilinea=True,
			lectura=True,
			alto=70,
			ancho=560,
		)
		self.lista = crear_lista(
			self.panel,
			self.letras.poner(_("Niveles, del más fácil al más difícil:")),
			[(_("Nivel"), 200), (_("Baliza"), 140), (_("Ayudas que retira"), 300)],
			configuracion,
			sizer=self.sizer,
			ayuda=_("Intro edita el nivel elegido."),
		)
		fila = wx.WrapSizer(wx.HORIZONTAL)
		crear_boton(self.panel, self.letras.poner(_("Nuevo nivel...")), self.nuevo, _("Añade un nivel al final de la lista."), fila)
		crear_boton(self.panel, self.letras.poner(_("Editar nivel...")), self.editar, _("Edita el nivel elegido."), fila)
		crear_boton(self.panel, self.letras.poner(_("Quitar")), self.quitar, _("Quita el nivel elegido."), fila)
		crear_boton(
			self.panel,
			self.letras.poner(_("Subir")),
			lambda: self.mover(-1),
			_("Mueve el nivel elegido un puesto hacia arriba: será más fácil."),
			fila,
		)
		crear_boton(
			self.panel,
			self.letras.poner(_("Bajar")),
			lambda: self.mover(1),
			_("Mueve el nivel elegido un puesto hacia abajo: será más difícil."),
			fila,
		)
		crear_boton(
			self.panel,
			self.letras.poner(_("Poner los de serie")),
			self.de_serie,
			_("Sustituye la lista por los cuatro niveles habituales."),
			fila,
		)
		self.sizer.Add(fila, 0, wx.ALL, 2)
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, lambda _evento: self.editar())
		self.recargar()
		self.terminar(self.lista, tamano_minimo=(700, 460))

	def recargar(self, fila: int | None = None) -> None:
		"""Vuelve a pintar la lista y deja elegida la fila ``fila``."""
		self.lista.reemplazar_filas([pres.resumen_nivel(nivel) for nivel in self.niveles])
		if fila is not None:
			self.lista.enfocar_fila(fila, anunciar=False)

	def _pedir(self, nivel: dict[str, Any] | None) -> dict[str, Any] | None:
		dialogo = DialogoNivel(self, nivel, self.configuracion)
		try:
			mostrar_modal(dialogo)
			return dialogo.nivel if dialogo.aceptado else None
		finally:
			dialogo.Destroy()

	def nuevo(self) -> None:
		"""Añade un nivel."""
		nivel = self._pedir(None)
		if nivel is not None:
			self.niveles.append(nivel)
			self.recargar(len(self.niveles) - 1)

	def editar(self) -> None:
		"""Edita el nivel elegido."""
		fila = self.lista.fila_actual()
		if not 0 <= fila < len(self.niveles):
			return
		nivel = self._pedir(self.niveles[fila])
		if nivel is not None:
			self.niveles[fila] = nivel
			self.recargar(fila)

	def quitar(self) -> None:
		"""Quita el nivel elegido."""
		fila = self.lista.fila_actual()
		if 0 <= fila < len(self.niveles):
			del self.niveles[fila]
			self.recargar(min(fila, len(self.niveles) - 1) if self.niveles else None)

	def mover(self, delta: int) -> None:
		"""Sube o baja el nivel elegido."""
		fila = self.lista.fila_actual()
		self.recargar(pres.mover(self.niveles, fila, delta))

	def de_serie(self) -> None:
		"""Pone los cuatro niveles habituales."""
		self.niveles = pres.niveles_de_serie()
		self.recargar(0)
