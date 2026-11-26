"""Sonidos propios de la ampliación del complemento «colegio», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Los sonidos de los objetos originales de «colegio» siguen en ``sonidos.py``;
aquí van los dos que piden los objetos nuevos y que no había en ningún otro
módulo: el timbre de cambio de clase, que se oye desde casi todo el centro y
sirve para orientarse, y el anemómetro de la estación meteorológica del
patio. Ambos llevan agudos por encima de 3 kHz para poder situarlos.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta


@_alta("colegio_timbre", pico=0.5)
def _timbre(rng: np.random.Generator) -> np.ndarray:
	"""Timbre eléctrico de colegio: el martillo golpea la campana metálica muy deprisa durante unos segundos."""
	d = 3.0
	t = s._t(d)
	campana = sum(a * np.sin(PI2 * f * t) for f, a in ((1350, 1.0), (2900, 0.6), (4400, 0.4), (6100, 0.25)))
	martilleo = 0.55 + 0.45 * np.sign(np.sin(PI2 * 22 * t))
	x = campana * martilleo * s._arco(d, 0.08)
	x += 0.3 * s._filtro(s._ruido(rng, d), 3000, 10000) * martilleo * s._arco(d, 0.08)
	cola = s._campana(1350, 1.2, (1, 2.15, 3.26, 4.5), (1, 0.6, 0.4, 0.25))
	salida = np.zeros(s._muestras(d + 1.2))
	s._poner(salida, x, 0.0, 0.8)
	s._poner(salida, cola, d - 0.02, 0.6)
	return salida


@_alta("colegio_anemometro", bucle=True, pico=0.3)
def _anemometro(rng: np.random.Generator) -> np.ndarray:
	"""Anemómetro con viento: el eje gira con un chasquido por vuelta que acelera y frena con las rachas."""
	d = 6.0
	x = 0.25 * s._filtro(s._ruido(rng, d), 300, 2500) * (0.5 + 0.5 * np.sin(PI2 * (1 / d) * s._t(d)))
	x += 0.04 * s._siseo(rng, d, 3500, 10000)
	x = s._bucle(x)
	instante = 0.0
	while instante < d:
		velocidad = 4.0 + 3.0 * np.sin(PI2 * instante / d)
		s._poner_ciclico(x, s._clac(rng, 0.012, 2500, 11000), instante, 0.5)
		instante += 1.0 / velocidad
	return x
