"""Sonidos propios de la ampliación del complemento «hogar», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Los sonidos de los objetos originales de «hogar» siguen en ``sonidos.py``;
aquí van solo los que piden los objetos nuevos y que no existían en ningún
otro módulo: el crujido de la mecedora, el repiqueteo de la cortina de tiras,
el motor del cortacésped y el traqueteo de la máquina de coser. Todos llevan
agudos por encima de 3 kHz para poder situarlos.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _motor


@_alta("hogar_mecedora", pico=0.45)
def _mecedora(rng: np.random.Generator) -> np.ndarray:
	"""Mecedora: tres vaivenes, cada uno con el crujido de la madera y el golpecito del patín en el suelo."""
	x = np.zeros(s._muestras(3.0))
	for k in range(3):
		inicio = k * 0.95
		s._poner(x, s._chirrido(520, 380, 0.32) * 0.5, inicio + 0.05, 0.6)
		s._poner(x, s._toc(rng, 190, 0.12, 1600), inicio + 0.4, 0.7)
		s._poner(x, s._aire(rng, 0.05, 0.4, 0.008), inicio + 0.4)
	return x


@_alta("hogar_cortina_tiras", pico=0.45)
def _cortina_tiras(rng: np.random.Generator) -> np.ndarray:
	"""Cortina de tiras: al atravesarla, decenas de tiras de plástico chocan y repiquetean hasta quedarse quietas."""
	d = 1.4
	x = np.zeros(s._muestras(d))
	for _k in range(60):
		t0 = rng.uniform(0.0, 1.1) ** 1.6
		golpe = s._clac(rng, 0.018, 2200, 11000) + 0.3 * s._seno(rng.uniform(1800, 3200), 0.018) * s._decae(0.018, 0.004)
		s._poner(x, golpe, t0, rng.uniform(0.2, 0.7) * (1.0 - t0 / 1.4))
	roce = s._filtro(s._ruido(rng, 0.6), 1500, 9000) * s._arco(0.6, 0.5)
	s._poner(x, roce, 0.0, 0.35)
	return x


@_alta("hogar_cortacesped", bucle=True, pico=0.35)
def _cortacesped(rng: np.random.Generator) -> np.ndarray:
	"""Cortacésped de gasolina en marcha: el petardeo del motor monocilíndrico y la cuchilla segando hierba."""
	d = 4.0
	t = s._t(d)
	pulsos = np.maximum(0.0, np.sin(PI2 * 28 * t)) ** 6
	motor = s._filtro(s._ruido(rng, d), 80, 900) * (0.3 + pulsos) + 0.4 * np.sin(PI2 * 56 * t)
	hierba = s._filtro(s._ruido(rng, d), 2500, 10000) * (0.6 + 0.4 * np.abs(s._filtro(s._ruido(rng, d), 2, 8)) * 8)
	return s._bucle(motor + 0.25 * hierba)


@_alta("hogar_maquina_coser", bucle=True, pico=0.35)
def _maquina_coser(rng: np.random.Generator) -> np.ndarray:
	"""Máquina de coser: el traqueteo rápido de la aguja sobre el zumbido del motorcito."""
	d = 3.0
	x = 0.25 * _motor(rng, d, 110, 400, 3000, siseo=0.2)
	x = s._bucle(x)
	for k in range(int(d * 12)):
		s._poner_ciclico(x, s._clac(rng, 0.02, 1800, 9000), k / 12, 0.8)
		s._poner_ciclico(x, s._toc(rng, 420, 0.04, 2500), k / 12 + 0.02, 0.25)
	return x
