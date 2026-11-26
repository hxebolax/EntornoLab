"""Sonidos propios de la ampliación del complemento «oficina_y_comercio», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Los sonidos de los objetos originales siguen en ``sonidos.py``; aquí van los
que piden los objetos nuevos y no existían en ningún otro módulo: la
destructora de papel, el rugido de los ventiladores de un armario de
servidores, la exprimidora de naranjas del supermercado y la máquina de
devolver envases. Todos llevan agudos por encima de 3 kHz para poder
situarlos.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _bip, _motor


@_alta("oficina_destructora", pico=0.5)
def _destructora(rng: np.random.Generator) -> np.ndarray:
	"""Destructora: el motor arranca, las cuchillas muerden el papel con un rasgado áspero y se para sola."""
	d = 2.2
	x = np.zeros(s._muestras(d + 0.2))
	motor = _motor(rng, d, 95, 300, 2500, siseo=0.2) * s._arco(d, 0.15)
	s._poner(x, motor, 0.0, 0.5)
	t = s._t(1.4)
	rasgado = s._filtro(s._ruido(rng, 1.4), 1500, 11000) * (0.6 + 0.4 * np.abs(np.sin(PI2 * 35 * t))) * s._arco(1.4, 0.3)
	s._poner(x, rasgado, 0.35, 0.9)
	return x


@_alta("oficina_servidores", bucle=True, pico=0.3)
def _servidores(rng: np.random.Generator) -> np.ndarray:
	"""Armario de servidores: muchos ventiladores pequeños a la vez, un siseo ancho con tonos agudos que laten despacio."""
	d = 4.0
	t = s._t(d)
	x = s._filtro(s._ruido(rng, d), 400, 9000)
	for f in (2350.0, 3120.0, 4480.0):
		x += 0.08 * np.sin(PI2 * f * t) * (0.7 + 0.3 * np.sin(PI2 * (1 / d) * t))
	x += 0.2 * s._filtro(s._ruido(rng, d), 60, 250)
	return s._bucle(x)


@_alta("oficina_exprimidora", pico=0.5)
def _exprimidora(rng: np.random.Generator) -> np.ndarray:
	"""Exprimidora automática: dos naranjas ruedan, el motor zumba, las cuchillas las parten y el zumo gotea."""
	x = np.zeros(s._muestras(3.6))
	for k in range(2):
		s._poner(x, s._toc(rng, 230, 0.15, 1200), 0.05 + k * 0.25, 0.6)
	motor = _motor(rng, 1.8, 140, 300, 3000, vaiven=6.0, siseo=0.25) * s._arco(1.8, 0.2)
	s._poner(x, motor, 0.6, 0.5)
	for k in range(2):
		s._poner(x, s._filtro(s._ruido(rng, 0.12), 800, 8000) * s._decae(0.12, 0.03), 0.9 + k * 0.6, 0.9)
	for _k in range(14):
		f = rng.uniform(900, 2200)
		gota = s._barrido(f, f * 1.7, 0.03) * s._decae(0.03, 0.008, 0.002)
		s._poner(x, gota, rng.uniform(1.2, 3.4), rng.uniform(0.2, 0.5))
	return x


@_alta("oficina_reciclaje_envases", pico=0.5)
def _reciclaje_envases(rng: np.random.Generator) -> np.ndarray:
	"""Máquina de devolver envases: la cinta arrastra la lata, la gira para leerla, la aplasta con un crujido y pita."""
	x = np.zeros(s._muestras(3.0))
	cinta = _motor(rng, 1.2, 110, 300, 2500, siseo=0.2) * s._arco(1.2, 0.2)
	s._poner(x, cinta, 0.0, 0.5)
	s._poner(x, s._destello(rng, 3600, 0.2), 0.2, 0.4)
	crujido = s._filtro(s._ruido(rng, 0.35), 700, 9000) * s._decae(0.35, 0.09)
	for k in range(3):
		s._poner(x, s._clac(rng, 0.03, 1500, 10000), 1.35 + k * 0.06, 0.7)
	s._poner(x, crujido, 1.3, 1.0)
	s._poner(x, _bip(1760, 0.12), 2.1, 0.8)
	s._poner(x, s._aire(rng, 0.05, 0.4, 0.01), 2.1)
	return x
