"""Sonidos propios del complemento «educacion_superior_e_infantil», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Guardería y ludoteca (piscina de bolas, futbolín), universidad (asiento
abatible de la grada, micrófono del atril, pizarra de guillotina, pantalla de
proyección, esqueleto de prácticas, cabina de ensayo) y residencia de
estudiantes (cinta de devolución de bandejas, guitarra).
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _motor


@_alta("guarderia_piscina_bolas", pico=0.5)
def _guarderia_piscina_bolas(rng: np.random.Generator) -> np.ndarray:
	"""Piscina de bolas: decenas de bolas huecas de plástico que entrechocan y ruedan."""
	x = np.zeros(s._muestras(1.2))
	for _k in range(28):
		inicio = rng.uniform(0, 0.85)
		f = rng.uniform(900, 2600)
		s._poner(x, s._seno(f, 0.05) * s._decae(0.05, 0.01, 0.0008), inicio, rng.uniform(0.3, 1.0))
		s._poner(x, s._clac(rng, 0.02, 2000, 9000), inicio, 0.4)
	s._poner(x, s._filtro(s._ruido(rng, 0.9), 1500, 7000) * s._arco(0.9, 1.0), 0.05, 0.25)
	return x


@_alta("ludoteca_futbolin")
def _ludoteca_futbolin(rng: np.random.Generator) -> np.ndarray:
	"""Futbolín: la barra gira con un carraqueo, el muñeco pega a la bola y la bola cae en la portería."""
	x = np.zeros(s._muestras(1.3))
	for k in range(7):
		s._poner(x, s._clac(rng, 0.025, 900, 6000), 0.04 * k, 0.5)
	s._poner(x, s._toc(rng, 520, 0.07, 3200), 0.34, 1.0)
	s._poner(x, s._seno(1900, 0.04) * s._decae(0.04, 0.008, 0.0005), 0.34, 0.6)
	for inicio, fuerza in ((0.55, 0.6), (0.68, 0.4)):
		s._poner(x, s._toc(rng, 300, 0.06, 2500), inicio, fuerza)
	s._poner(x, s._toc(rng, 140, 0.2, 1200), 0.86, 1.0)
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 1200, 8000) * s._decae(0.3, 0.08, 0.004), 0.9, 0.5)
	return x


@_alta("uni_asiento_abatible")
def _uni_asiento_abatible(rng: np.random.Generator) -> np.ndarray:
	"""Asiento abatible de bancada de aula: el muelle cruje y la tabla hace tope con un golpe de madera."""
	x = np.zeros(s._muestras(0.7))
	s._poner(x, s._chirrido(420, 300, 0.22), 0.0, 0.3)
	s._poner(x, s._toc(rng, 210, 0.16, 1800), 0.24, 1.0)
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.24, 0.7)
	s._poner(x, s._toc(rng, 230, 0.1, 1600), 0.4, 0.35)
	return x


@_alta("uni_micro_atril", pico=0.5)
def _uni_micro_atril(rng: np.random.Generator) -> np.ndarray:
	"""Micrófono del atril: dos golpecitos amplificados por los altavoces y un amago de acople."""
	x = np.zeros(s._muestras(1.3))
	for inicio in (0.0, 0.26):
		s._poner(x, s._seno(120, 0.16) * s._decae(0.16, 0.045, 0.002), inicio, 1.0)
		s._poner(x, s._filtro(s._ruido(rng, 0.12), 300, 5000) * s._decae(0.12, 0.03, 0.001), inicio, 0.7)
		s._poner(x, s._aire(rng, 0.06, 0.5, 0.01), inicio)
	d = 0.55
	acople = s._barrido(2900, 3250, d) + 0.3 * s._barrido(5800, 6500, d)
	s._poner(x, acople * s._arco(d, 1.5), 0.6, 0.45)
	return x


@_alta("uni_pizarra_guillotina", pico=0.5)
def _uni_pizarra_guillotina(rng: np.random.Generator) -> np.ndarray:
	"""Pizarra de guillotina: el tablero sube por sus guías, las poleas del contrapeso chirrían y hace tope."""
	d = 0.95
	x = np.zeros(s._muestras(1.3))
	rodar = s._filtro(s._ruido(rng, d), 250, 5000) * s._arco(d, 0.6) * (0.7 + 0.3 * np.sign(s._seno(22, d)))
	s._poner(x, rodar, 0.0, 0.8)
	s._poner(x, s._chirrido(900, 1300, 0.4), 0.2, 0.2)
	s._poner(x, s._toc(rng, 130, 0.2, 1300), 0.95, 1.0)
	s._poner(x, s._clac(rng, 0.04, 1200, 8000), 0.95, 0.7)
	return x


@_alta("uni_pantalla_motor", pico=0.45)
def _uni_pantalla_motor(rng: np.random.Generator) -> np.ndarray:
	"""Pantalla de proyección eléctrica: el motor del tubo zumba mientras la tela corre y se para con un clic."""
	d = 1.8
	x = np.zeros(s._muestras(2.0))
	t = s._t(d)
	motor = _motor(rng, d, 95, 400, 2600, siseo=0.35) * np.clip(t / 0.1, 0, 1) * np.clip((d - t) / 0.08, 0, 1)
	s._poner(x, motor, 0.0, 0.8)
	s._poner(x, s._filtro(s._ruido(rng, d), 2500, 8000) * s._arco(d, 0.5), 0.0, 0.2)
	s._poner(x, s._clac(rng, 0.04, 1500, 9000), 1.82, 1.0)
	return x


@_alta("uni_esqueleto_practicas", pico=0.5)
def _uni_esqueleto_practicas(rng: np.random.Generator) -> np.ndarray:
	"""Esqueleto de prácticas: huesos huecos de plástico que entrechocan y se quedan bailando."""
	x = np.zeros(s._muestras(1.1))
	for k in range(12):
		inicio = 0.07 * k + rng.uniform(0, 0.04)
		f = rng.uniform(450, 1500)
		fuerza = 1.0 / (1 + 0.25 * k)
		s._poner(x, s._seno(f, 0.07) * s._decae(0.07, 0.014, 0.0008), inicio, fuerza)
		s._poner(x, s._clac(rng, 0.025, 1800, 9000), inicio, 0.6 * fuerza)
	return x


@_alta("uni_cabina_ensayo", bucle=True, pico=0.3)
def _uni_cabina_ensayo(rng: np.random.Generator) -> np.ndarray:
	"""Cabina de ensayo: alguien repite una escala de piano al otro lado de una puerta gruesa."""
	d = 4.0
	x = 0.05 * s._siseo(rng, d, 3200, 9000)
	x = s._bucle(x, 200.0)
	paso = len(x) / s.FRECUENCIA / 8
	for k, f in enumerate((261.63, 293.66, 329.63, 349.23, 392.0, 349.23, 329.63, 293.66)):
		nota = s._nota(f, 0.6, 0.22, (1, 0.5, 0.3, 0.18, 0.1, 0.06))
		s._poner_ciclico(x, s._filtro(nota, None, 2600, 2), k * paso, 0.6)
		s._poner_ciclico(x, s._aire(rng, 0.05, 0.12, 0.01), k * paso)
		# El golpe de la tecla y el mecanismo se oyen aunque la puerta apague la nota.
		s._poner_ciclico(x, s._filtro(s._ruido(rng, 0.3), 2500, 9000) * s._decae(0.3, 0.08, 0.001), k * paso, 0.3)
	return x


@_alta("residencia_cinta_bandejas", bucle=True, pico=0.3)
def _residencia_cinta_bandejas(rng: np.random.Generator) -> np.ndarray:
	"""Cinta de devolución de bandejas: rodillos que giran y, de vez en cuando, platos y cubiertos que tintinean."""
	d = 3.6
	t = s._t(d)
	x = 0.6 * _motor(rng, d, 48, 200, 1500, siseo=0.3)
	x += 0.25 * s._filtro(s._ruido(rng, d), 600, 3500) * (0.6 + 0.4 * np.abs(np.sin(PI2 * 3.0 * t)))
	x = s._bucle(x)
	for inicio, f in ((0.5, 2300), (1.3, 3100), (1.42, 2700), (2.6, 3500)):
		s._poner_ciclico(x, s._campana(f, 0.25, (1, 2.3, 3.9), (1, 0.6, 0.35)), inicio, 0.45)
		s._poner_ciclico(x, s._clac(rng, 0.02, 2500, 10000), inicio, 0.4)
	return x


@_alta("residencia_guitarra", pico=0.5)
def _residencia_guitarra(rng: np.random.Generator) -> np.ndarray:
	"""Guitarra: un rasgueo de las seis cuerdas al aire, de la más grave a la más aguda, y la caja que resuena."""
	x = np.zeros(s._muestras(2.2))
	for k, f in enumerate((82.41, 110.0, 146.83, 196.0, 246.94, 329.63)):
		cuerda = s._nota(f, 1.9, 0.55, (1, 0.7, 0.5, 0.4, 0.28, 0.2, 0.14, 0.1, 0.07, 0.05))
		s._poner(x, cuerda, 0.028 * k, 0.6)
		s._poner(x, s._aire(rng, 0.05, 0.5, 0.008), 0.028 * k)
		# La púa rozando cada cuerda: da el brillo que sitúa la guitarra.
		s._poner(x, s._filtro(s._ruido(rng, 0.8), 2500, 10000) * s._decae(0.8, 0.2, 0.001), 0.028 * k, 0.3)
	s._poner(x, s._toc(rng, 105, 0.18, 900), 0.0, 0.35)
	return x
