"""Georreferencia: pasar de latitud y longitud a los metros del entorno y al revés.

Un entorno que viene de un mapa real guarda en ``entorno.georef`` la latitud
y la longitud de su punto (0, 0). Con eso basta para volver a situar sobre él
una ruta GPX o para exportarlo en coordenadas reales.

También viven aquí los textos de procedencia de OpenStreetMap, porque los
necesitan tanto el importador como todo lo que se exporta: la licencia ODbL
obliga a citar la fuente en cualquier obra derivada.
"""

from __future__ import annotations

import math
from typing import Any

from app.dominio.modelo import Entorno

R_TIERRA = 6371008.8
M_GRADO = math.pi * R_TIERRA / 180.0

ATRIBUCION = "© colaboradores de OpenStreetMap"
LICENCIA = "ODbL 1.0"
URL_LICENCIA = "https://www.openstreetmap.org/copyright"
FUENTE_OSM = "OpenStreetMap"


class Proyeccion:
	"""Coordenadas locales en metros alrededor de un punto: x al este, y al norte.

	En un recuadro de menos de un kilómetro la Tierra se puede tratar como
	plana: el error es de centímetros, muy por debajo del de los propios datos.
	"""

	def __init__(self, lat0: float, lon0: float) -> None:
		self.lat0 = float(lat0)
		self.lon0 = float(lon0)
		self.kx = M_GRADO * math.cos(math.radians(self.lat0))

	def a_xy(self, lat: float, lon: float) -> tuple[float, float]:
		"""Latitud y longitud → metros locales."""
		return (lon - self.lon0) * self.kx, (lat - self.lat0) * M_GRADO

	def a_latlon(self, x: float, y: float) -> tuple[float, float]:
		"""Metros locales → latitud y longitud."""
		return self.lat0 + y / M_GRADO, self.lon0 + x / self.kx


def proyeccion_de(entorno: Entorno) -> Proyeccion | None:
	"""Proyección de un entorno georreferenciado; None si no viene de un mapa real."""
	georef = entorno.georef
	if not isinstance(georef, dict):
		return None
	try:
		lat0, lon0 = float(georef["lat0"]), float(georef["lon0"])
	except KeyError, TypeError, ValueError:
		return None
	if not (math.isfinite(lat0) and math.isfinite(lon0) and abs(lat0) < 89.0):
		return None
	return Proyeccion(lat0, lon0)


def texto_atribucion(procedencia: dict[str, Any] | None) -> str:
	"""Frase de atribución que debe acompañar a todo lo exportado, o cadena vacía si no hace falta.

	Si el entorno viene de OpenStreetMap, la licencia ODbL exige citar a sus
	colaboradores; para otras fuentes se cita lo que diga la procedencia.
	"""
	if not isinstance(procedencia, dict):
		return ""
	atribucion = str(procedencia.get("atribucion") or "").strip()
	licencia = str(procedencia.get("licencia") or "").strip()
	if not atribucion and str(procedencia.get("fuente") or "").strip().lower() == FUENTE_OSM.lower():
		atribucion = ATRIBUCION
		licencia = licencia or LICENCIA
	if not atribucion:
		return ""
	return f"{atribucion} ({licencia})" if licencia else atribucion
