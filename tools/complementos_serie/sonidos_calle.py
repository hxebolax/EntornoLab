"""Sonidos propios de la ampliación del complemento «calle», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Son sonidos que en la calle sirven de referencia o de aviso: las campanadas
de un reloj de plaza, la música de organillo de un tiovivo (se oye desde
toda la feria), la basura que cae muy hondo en un contenedor soterrado y el
chirrido de un expositor giratorio a la puerta de una tienda. Todos llevan
agudos por encima de 3 kHz para poder localizarlos.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import _alta

# Notas (Hz) de un vals sencillo de organillo: do mayor, compás de tres.
_VALS = (523.3, 659.3, 784.0, 659.3, 698.5, 880.0, 698.5, 587.3, 784.0, 987.8, 784.0, 523.3)


@_alta("calle_reloj_campanadas", pico=0.5)
def _reloj_campanadas(rng: np.random.Generator) -> np.ndarray:
	"""Reloj de plaza: los cuartos en cuatro notas y tres campanadas graves que dan la hora."""
	x = np.zeros(s._muestras(7.5))
	for k, f in enumerate((659.3, 523.3, 587.3, 392.0)):
		s._poner(x, s._campana(f, 1.4), k * 0.6, 0.6)
		s._poner(x, s._aire(rng, 0.05, 0.3, 0.01), k * 0.6)
		# El martillo golpea el bronce: ese chasquido agudo es lo que deja situar la campana.
		s._poner(x, s._filtro(s._ruido(rng, 0.8), 2500, 10000) * s._decae(0.8, 0.25, 0.001), k * 0.6, 0.35)
	for k in range(3):
		s._poner(x, s._campana(196.0, 2.4), 3.0 + k * 1.4, 1.0)
		s._poner(x, s._aire(rng, 0.06, 0.4, 0.012), 3.0 + k * 1.4)
		s._poner(x, s._filtro(s._ruido(rng, 1.0), 2500, 10000) * s._decae(1.0, 0.3, 0.001), 3.0 + k * 1.4, 0.4)
	return x


@_alta("calle_soterrado_caida", pico=0.55)
def _soterrado_caida(rng: np.random.Generator) -> np.ndarray:
	"""Contenedor soterrado: la bolsa resbala por la tolva de chapa, cae dos metros y golpea abajo con eco hueco."""
	x = np.zeros(s._muestras(2.0))
	roce = s._filtro(s._ruido(rng, 0.35), 900, 7000) * s._arco(0.35, 0.8)
	s._poner(x, roce, 0.0, 0.5)
	golpe = s._toc(rng, 95, 0.5, 900) + 0.6 * s._golpe(rng, "metal")[: s._muestras(0.5)]
	s._poner(x, golpe, 0.55, 0.9)
	for k, g in enumerate((0.35, 0.2, 0.1)):
		s._poner(x, s._filtro(golpe, 150, 2500), 0.72 + k * 0.17, g)
	s._poner(x, s._clac(rng, 0.04, 1200, 9000), 1.4, 0.6)
	return x


@_alta("calle_tiovivo_organillo", bucle=True, pico=0.4)
def _tiovivo_organillo(rng: np.random.Generator) -> np.ndarray:
	"""Tiovivo en marcha: un vals de organillo con bajo de tuba, el traqueteo de la plataforma y el siseo de los tubos."""
	paso = 0.3
	d = paso * len(_VALS) * 2
	x = 0.04 * s._siseo(rng, d, 3200, 9000) + 0.05 * s._filtro(s._ruido(rng, d), 80, 400)
	x = s._bucle(x)
	for vuelta in range(2):
		for k, f in enumerate(_VALS):
			t0 = (vuelta * len(_VALS) + k) * paso
			nota = s._nota(f, paso * 1.1, 0.5, (1, 0.7, 0.5, 0.35, 0.2)) + 0.15 * s._seno(f * 4, paso * 1.1) * s._decae(paso * 1.1, 0.08)
			s._poner_ciclico(x, nota, t0, 0.5)
			if k % 3 == 0:
				s._poner_ciclico(x, s._nota(f / 4, paso * 0.9, 0.2, (1, 0.5)), t0, 0.6)
			else:
				s._poner_ciclico(x, s._nota(f / 2, paso * 0.5, 0.08, (1, 0.6, 0.3)), t0, 0.25)
		s._poner_ciclico(x, s._clac(rng, 0.03, 600, 4000), vuelta * len(_VALS) * paso + 0.1, 0.3)
	return x


@_alta("calle_expositor_giro", pico=0.45)
def _expositor_giro(rng: np.random.Generator) -> np.ndarray:
	"""Expositor giratorio de postales: el eje chirría al girar y las tarjetas tiemblan en la rejilla."""
	x = np.zeros(s._muestras(1.3))
	s._poner(x, s._chirrido(2200, 2900, 0.5) * s._arco(0.5, 0.6), 0.0, 0.35)
	s._poner(x, s._chirrido(2600, 2100, 0.4) * s._arco(0.4, 0.6), 0.5, 0.3)
	for _k in range(9):
		s._poner(
			x, s._filtro(s._ruido(rng, 0.05), 3000, 10000) * s._decae(0.05, 0.012, 0.001), rng.uniform(0.02, 1.0), rng.uniform(0.15, 0.35)
		)
	return x
