"""Rejilla de cajas: encuentra en tiempo constante qué elementos pueden estar cerca de un punto.

Por qué existe: con un barrio importado de OpenStreetMap (miles de espacios,
aberturas y objetos) ni el Estudio ni el motor pueden recorrer todas las
listas en cada clic, en cada fotograma ni en cada celda de la búsqueda de
caminos. Cada elemento se apunta, por su número de orden en la lista
original, en las celdas que toca su caja; una consulta mira solo las celdas
de la zona pedida.

La rejilla solo PRESELECCIONA: devuelve los números de los elementos cuya
caja toca la zona, siempre ordenados de menor a mayor. Quien pregunta aplica
después exactamente la misma comprobación que antes aplicaba a toda la
lista, en el mismo orden, así que el resultado es idéntico al de la búsqueda
exhaustiva (lo vigilan ``tests/test_motor_indice_espacial.py`` y
``tests/test_dominio_indice_espacial.py``).

Un elemento enorme (una calzada de un kilómetro) ocuparía miles de celdas:
los que pasan de ``MAX_CELDAS`` van a una lista aparte que se mira siempre.
"""

from __future__ import annotations

import math

Caja = tuple[float, float, float, float]

# Celdas que puede ocupar un elemento antes de ir a la lista de «grandes» (que se miran siempre).
MAX_CELDAS = 4096


class RejillaCajas:
	"""Índice de cajas por celdas cuadradas de lado ``celda`` metros."""

	__slots__ = ("celda", "_celdas", "_grandes", "_cuantos")

	def __init__(self, celda: float = 8.0) -> None:
		self.celda = float(celda)
		self._celdas: dict[tuple[int, int], list[int]] = {}
		self._grandes: list[int] = []
		self._cuantos = 0

	def __len__(self) -> int:
		return self._cuantos

	def meter(self, caja: Caja, margen: float = 0.0) -> int:
		"""Apunta un elemento con su caja (ampliada en ``margen``). Devuelve su número (el orden de llegada).

		Los números crecen con cada llamada: si se meten en el orden de la lista
		original, el número es su posición en ella.
		"""
		numero = self._cuantos
		self._cuantos += 1
		x0, y0, x1, y1 = caja
		if not all(math.isfinite(valor) for valor in caja):
			# Una caja que no se puede situar (datos dañados) se mira siempre, como las enormes.
			self._grandes.append(numero)
			return numero
		celda = self.celda
		cx0 = math.floor((x0 - margen) / celda)
		cx1 = math.floor((x1 + margen) / celda)
		cy0 = math.floor((y0 - margen) / celda)
		cy1 = math.floor((y1 + margen) / celda)
		if (cx1 - cx0 + 1) * (cy1 - cy0 + 1) > MAX_CELDAS:
			self._grandes.append(numero)
			return numero
		celdas = self._celdas
		for cx in range(cx0, cx1 + 1):
			for cy in range(cy0, cy1 + 1):
				lista = celdas.get((cx, cy))
				if lista is None:
					celdas[(cx, cy)] = [numero]
				else:
					lista.append(numero)
		return numero

	def todos(self) -> list[int]:
		"""Todos los números: lo que se devuelve cuando la zona pedida no se puede situar en la rejilla."""
		return list(range(self._cuantos))

	def en_punto(self, x: float, y: float) -> list[int]:
		"""Números (de menor a mayor) de los elementos cuya caja ampliada puede contener el punto.

		La lista devuelta puede ser la de la propia celda: no se modifica.
		"""
		if not (math.isfinite(x) and math.isfinite(y)):
			return self.todos()
		celda = self.celda
		propios = self._celdas.get((math.floor(x / celda), math.floor(y / celda)))
		if not self._grandes:
			return propios if propios is not None else []
		if propios is None:
			return self._grandes
		return sorted(propios + self._grandes)

	def en_caja(self, x0: float, y0: float, x1: float, y1: float) -> list[int]:
		"""Números (de menor a mayor, sin repetir) de los elementos cuya caja ampliada toca esa zona."""
		if not all(math.isfinite(valor) for valor in (x0, y0, x1, y1)):
			return self.todos()
		celda = self.celda
		cx0, cx1 = math.floor(x0 / celda), math.floor(x1 / celda)
		cy0, cy1 = math.floor(y0 / celda), math.floor(y1 / celda)
		if cx0 == cx1 and cy0 == cy1:
			return self.en_punto(x0, y0)
		celdas = self._celdas
		if (cx1 - cx0 + 1) * (cy1 - cy0 + 1) > len(celdas):
			# Una zona mayor que todo lo ocupado: se recorren las celdas que hay, no las que podría haber.
			vistos = {numero for (cx, cy), lista in celdas.items() if cx0 <= cx <= cx1 and cy0 <= cy <= cy1 for numero in lista}
		else:
			vistos = set()
			for cx in range(cx0, cx1 + 1):
				for cy in range(cy0, cy1 + 1):
					lista = celdas.get((cx, cy))
					if lista is not None:
						vistos.update(lista)
		vistos.update(self._grandes)
		return sorted(vistos)
