"""Plano pequeño y solo visual: el contorno de los espacios, un recorrido y dónde está el alumno.

Es un complemento para quien tiene resto visual o para un acompañante que
ve: toda la información que dibuja está también en palabras en la ventana
(posición descrita, lista de pasos). Por eso no recibe el foco ni tiene nada
que leer: un lector de pantalla simplemente no lo encuentra al tabular.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Sequence
from typing import Any

import wx

log = logging.getLogger(__name__)

_MARGEN = 10


class PlanoSimple(wx.Window):
	"""Dibujo de una planta con un recorrido y una posición."""

	def __init__(self, padre: wx.Window, tamano: tuple[int, int] = (260, 200)) -> None:
		super().__init__(padre, size=wx.Size(*tamano), style=wx.BORDER_THEME, name="plano")
		self.SetMinSize(wx.Size(*tamano))
		self.SetBackgroundStyle(wx.BG_STYLE_PAINT)
		self._contornos: list[list[tuple[float, float]]] = []
		self._recorrido: list[tuple[float, float]] = []
		self._posicion: tuple[float, float, float | None] | None = None
		self._clave: Any = None
		self.Bind(wx.EVT_PAINT, self._al_pintar)
		self.Bind(wx.EVT_SIZE, lambda evento: (self.Refresh(), evento.Skip()))

	def AcceptsFocus(self) -> bool:  # noqa: N802 - API de wx
		"""Nunca recibe el foco: no tiene nada que un lector pueda leer."""
		return False

	def AcceptsFocusFromKeyboard(self) -> bool:  # noqa: N802 - API de wx
		"""Queda fuera del recorrido del tabulador."""
		return False

	def poner_planta(self, entorno: Any, planta_id: str, version: int = 0) -> None:
		"""Dibuja los espacios de esa planta (nada si no hay entorno o no tiene esa planta).

		``version`` es la del documento (``contexto.version``): deshacer y
		rehacer cambian el entorno en el sitio, sin cambiar de objeto, y sin
		ella el plano no se enteraría.
		"""
		clave = (id(entorno), planta_id, version)
		if clave == self._clave:
			return
		self._clave = clave
		planta = entorno.planta(planta_id) if entorno is not None and planta_id else None
		if planta is None and entorno is not None and entorno.plantas and not planta_id:
			planta = entorno.plantas[0]
		self._contornos = (
			[[(float(x), float(y)) for x, y in espacio.contorno] for espacio in planta.espacios if len(espacio.contorno) >= 3]
			if planta is not None
			else []
		)
		self.Refresh()

	def poner_recorrido(self, puntos: Sequence[tuple[float, float]]) -> None:
		"""Dibuja un recorrido como una línea quebrada."""
		self._recorrido = [(float(x), float(y)) for x, y in puntos]
		self.Refresh()

	def poner_posicion(self, x: Any, y: Any, rumbo: Any = None) -> None:
		"""Marca dónde está el alumno (y hacia dónde mira). Con datos que no son números, borra la marca."""
		if isinstance(x, (int, float)) and isinstance(y, (int, float)) and not isinstance(x, bool) and not isinstance(y, bool):
			nueva: tuple[float, float, float | None] | None = (
				float(x),
				float(y),
				float(rumbo) if isinstance(rumbo, (int, float)) and not isinstance(rumbo, bool) else None,
			)
		else:
			nueva = None
		if nueva != self._posicion:
			self._posicion = nueva
			self.Refresh()

	def _caja(self) -> tuple[float, float, float, float] | None:
		puntos = [punto for contorno in self._contornos for punto in contorno] + list(self._recorrido)
		if self._posicion is not None:
			puntos.append((self._posicion[0], self._posicion[1]))
		if not puntos:
			return None
		xs = [punto[0] for punto in puntos]
		ys = [punto[1] for punto in puntos]
		return min(xs), min(ys), max(xs), max(ys)

	def _al_pintar(self, _evento: wx.PaintEvent) -> None:
		dc = wx.AutoBufferedPaintDC(self)
		dc.SetBackground(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)))
		dc.Clear()
		caja = self._caja()
		if caja is None:
			return
		x1, y1, x2, y2 = caja
		ancho, alto = self.GetClientSize()
		escala = min((ancho - 2 * _MARGEN) / max(x2 - x1, 0.1), (alto - 2 * _MARGEN) / max(y2 - y1, 0.1))

		def a_pantalla(punto: tuple[float, float]) -> wx.Point:
			# El norte (Y creciente) va hacia arriba de la pantalla.
			return wx.Point(int(_MARGEN + (punto[0] - x1) * escala), int(alto - _MARGEN - (punto[1] - y1) * escala))

		texto = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOWTEXT)
		dc.SetPen(wx.Pen(texto, 1))
		dc.SetBrush(wx.TRANSPARENT_BRUSH)
		for contorno in self._contornos:
			dc.DrawPolygon([a_pantalla(punto) for punto in contorno])
		if len(self._recorrido) >= 2:
			dc.SetPen(wx.Pen(wx.SystemSettings.GetColour(wx.SYS_COLOUR_HOTLIGHT), 2))
			dc.DrawLines([a_pantalla(punto) for punto in self._recorrido])
		if self._posicion is not None:
			centro = a_pantalla((self._posicion[0], self._posicion[1]))
			dc.SetPen(wx.Pen(texto, 2))
			dc.SetBrush(wx.Brush(wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)))
			dc.DrawCircle(centro, 5)
			if self._posicion[2] is not None:
				angulo = math.radians(self._posicion[2])
				dc.DrawLine(centro, wx.Point(int(centro.x + 12 * math.sin(angulo)), int(centro.y - 12 * math.cos(angulo))))
