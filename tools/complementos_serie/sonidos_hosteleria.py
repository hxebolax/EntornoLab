"""Sonidos propios del complemento «hosteleria», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Cubren lo que de verdad suena en un bar, un restaurante o un hotel y sirve
para orientarse o para jugar: la cafetera, el molinillo, el grifo de cerveza,
la tragaperras, el futbolín, el billar, la diana, el vivero de marisco, la
vajilla, la estufa de terraza, los nebulizadores, el carro de las maletas y
la máquina de hielo.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _agua, _alta, _bip, _motor


@_alta("cafetera_vapor", pico=0.5)
def _cafetera_vapor(rng: np.random.Generator) -> np.ndarray:
	"""Cafetera exprés: el golpe del portafiltro, la bomba y el vaporizador que silba al calentar la leche."""
	x = np.zeros(s._muestras(2.8))
	s._poner(x, s._toc(rng, 220, 0.1, 2500), 0.0, 0.8)
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0, 0.5)
	bomba = (0.6 * s._seno(55, 0.9) + 0.3 * s._seno(110, 0.9)) * (0.7 + 0.3 * s._seno(14, 0.9)) * s._arco(0.9, 0.3)
	s._poner(x, bomba, 0.2, 0.5)
	d = 1.7
	vapor = s._filtro(s._ruido(rng, d), 2500, 12000) * (0.75 + 0.25 * s._seno(23, d))
	vapor += 0.12 * s._barrido(1900, 900, d)
	s._poner(x, vapor * s._arco(d, 0.25), 1.0, 0.9)
	return x


@_alta("molinillo_cafe", pico=0.5)
def _molinillo_cafe(rng: np.random.Generator) -> np.ndarray:
	"""Molinillo de café: el motor chilla, el grano cruje y la palanca del dosificador da dos golpes."""
	d = 1.1
	x = np.zeros(s._muestras(1.6))
	motor = _motor(rng, d, 185, 800, 5000, siseo=0.4)
	grano = s._filtro(s._ruido(rng, d), 1500, 7000) * (0.6 + 0.4 * np.sign(s._seno(43, d)))
	s._poner(x, (motor + 0.7 * grano) * s._arco(d, 0.2), 0.0, 0.8)
	for k in range(2):
		s._poner(x, s._clac(rng, 0.03, 1200, 8000), 1.2 + 0.16 * k, 0.9)
		s._poner(x, s._toc(rng, 300, 0.08, 2000), 1.2 + 0.16 * k, 0.6)
	return x


@_alta("cerveza_tirar", pico=0.5)
def _cerveza_tirar(rng: np.random.Generator) -> np.ndarray:
	"""Grifo de cerveza: la palanca, el chorro que llena el vaso y la espuma que sube siseando."""
	d = 1.4
	x = np.zeros(s._muestras(1.9))
	s._poner(x, s._clac(rng, 0.03, 1000, 7000), 0.0, 0.8)
	s._poner(x, _agua(rng, d, 900, 7000, 4) * s._arco(d, 0.4), 0.08, 0.8)
	espuma = s._siseo(rng, d, 4000, 11000) * np.linspace(0.1, 1.0, s._muestras(d)) * s._arco(d, 0.3)
	s._poner(x, espuma, 0.2, 0.6)
	s._poner(x, s._clac(rng, 0.03, 1000, 7000), 1.6, 0.7)
	s._poner(x, s._toc(rng, 260, 0.1, 1800), 1.62, 0.5)
	return x


@_alta("tragaperras_musica", bucle=True, pico=0.3)
def _tragaperras_musica(rng: np.random.Generator) -> np.ndarray:
	"""Máquina tragaperras: una musiquilla electrónica que no para, el carraqueo de los rodillos y alguna moneda."""
	d = 4.8
	x = s._bucle(0.04 * s._siseo(rng, d + 0.25, 3200, 9000))
	duracion = len(x) / s.FRECUENCIA
	notas = (659.25, 783.99, 1046.5, 783.99, 880.0, 1046.5, 1318.5, 1046.5, 698.46, 880.0, 1174.7, 880.0, 783.99, 987.77, 1174.7, 1568.0)
	paso = duracion / len(notas)
	for k, f in enumerate(notas):
		s._poner_ciclico(x, s._nota(f, 0.26, 0.09, (1, 0.0, 0.45, 0.0, 0.3, 0.0, 0.2)), k * paso, 0.5)
	for k in range(24):
		s._poner_ciclico(x, s._clac(rng, 0.012, 2500, 10000), 0.3 + k * 0.045, 0.18)
	for k in range(3):
		s._poner_ciclico(x, s._destello(rng, rng.uniform(3500, 5800), 0.2), 3.1 + 0.11 * k, 0.4)
	return x


@_alta("futbolin_golpe")
def _futbolin_golpe(rng: np.random.Generator) -> np.ndarray:
	"""Futbolín: la barra golpea contra el tope, la bola rueda por el tablero y cae en la portería."""
	x = np.zeros(s._muestras(1.1))
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0, 0.9)
	s._poner(x, s._seno(2300, 0.25) * s._decae(0.25, 0.05, 0.001), 0.0, 0.35)
	s._poner(x, s._toc(rng, 320, 0.08, 2500), 0.02, 0.8)
	s._poner(x, s._filtro(s._ruido(rng, 0.45), 300, 2500) * s._arco(0.45, 0.6), 0.12, 0.4)
	s._poner(x, s._toc(rng, 900, 0.04, 4000), 0.3, 0.5)
	s._poner(x, s._toc(rng, 130, 0.25, 1500), 0.62, 1.0)
	s._poner(x, s._clac(rng, 0.03, 2000, 9000), 0.62, 0.4)
	return x


@_alta("billar_bolas")
def _billar_bolas(rng: np.random.Generator) -> np.ndarray:
	"""Billar: el taco golpea, las bolas chocan con chasquidos secos, ruedan y una cae en la tronera."""
	x = np.zeros(s._muestras(1.3))
	s._poner(x, s._toc(rng, 520, 0.05, 3000), 0.0, 0.8)
	for inicio in (0.09, 0.14, 0.2, 0.31, 0.47):
		f = rng.uniform(2600, 4200)
		s._poner(x, s._seno(f, 0.05) * s._decae(0.05, 0.009, 0.0005), inicio, rng.uniform(0.5, 1.0))
		s._poner(x, s._clac(rng, 0.015, 3000, 12000), inicio, 0.6)
	s._poner(x, s._filtro(s._ruido(rng, 0.7), 150, 1200) * s._arco(0.7, 0.7), 0.1, 0.25)
	s._poner(x, s._toc(rng, 140, 0.25, 1200), 0.92, 0.9)
	s._poner(x, s._clac(rng, 0.02, 2000, 9000), 0.92, 0.3)
	return x


@_alta("dardo_diana")
def _dardo_diana(rng: np.random.Generator) -> np.ndarray:
	"""Diana electrónica: el dardo se clava con un golpe seco y la máquina canta la puntuación con tres pitidos."""
	x = np.zeros(s._muestras(1.0))
	s._poner(x, s._toc(rng, 260, 0.09, 2500), 0.0, 1.0)
	s._poner(x, s._clac(rng, 0.02, 2000, 10000), 0.0, 0.7)
	for k, f in enumerate((1318.5, 1760.0, 2093.0)):
		s._poner(x, _bip(f, 0.11), 0.28 + 0.15 * k, 0.5)
		s._poner(x, s._aire(rng, 0.03, 0.25, 0.006), 0.28 + 0.15 * k)
	return x


@_alta("vivero_burbujas", bucle=True, pico=0.3)
def _vivero_burbujas(rng: np.random.Generator) -> np.ndarray:
	"""Vivero de marisco: la bomba zumba bajito y las burbujas del oxigenador suben sin parar."""
	d = 4.0
	base = 0.25 * _motor(rng, d + 0.25, 50, 100, 500, siseo=0.2)
	base += 0.3 * s._filtro(s._ruido(rng, d + 0.25), 1500, 8000)
	x = s._bucle(base)
	duracion = len(x) / s.FRECUENCIA
	for _k in range(70):
		f = rng.uniform(350, 1400)
		burbuja = s._barrido(f, f * rng.uniform(1.5, 2.2), 0.05) * s._decae(0.05, 0.015, 0.003)
		s._poner_ciclico(x, burbuja, rng.uniform(0, duracion), rng.uniform(0.25, 0.7))
	return x


@_alta("vajilla_tintineo", pico=0.5)
def _vajilla_tintineo(rng: np.random.Generator) -> np.ndarray:
	"""Vajilla: platos que se rozan, cubiertos y copas que tintinean al mover un carro o abrir el aparador."""
	x = np.zeros(s._muestras(1.0))
	for _k in range(7):
		s._poner(x, s._destello(rng, rng.uniform(2600, 5600), 0.2), rng.uniform(0, 0.55), rng.uniform(0.4, 0.9))
	s._poner(x, s._campana(1400, 0.35), 0.05, 0.5)
	s._poner(x, s._campana(1870, 0.3), 0.33, 0.4)
	s._poner(x, s._clac(rng, 0.02, 2500, 11000), 0.05, 0.5)
	return x


@_alta("estufa_terraza_gas", bucle=True, pico=0.25)
def _estufa_terraza_gas(rng: np.random.Generator) -> np.ndarray:
	"""Estufa de terraza encendida: el quemador de gas ruge suave y sisea por arriba."""
	d = 3.75
	t = s._t(d)
	x = 0.6 * s._filtro(s._ruido(rng, d), 150, 900) * (0.8 + 0.2 * np.sin(PI2 * 0.8 * t) * np.sin(PI2 * 5.3 * t))
	x += 0.4 * s._siseo(rng, d, 3500, 10000)
	return s._bucle(x)


@_alta("nebulizador_terraza", bucle=True, pico=0.25)
def _nebulizador_terraza(rng: np.random.Generator) -> np.ndarray:
	"""Nebulizadores de terraza: un siseo muy fino de agua pulverizada y la bomba al fondo."""
	d = 3.25
	t = s._t(d)
	x = s._siseo(rng, d, 5000, 13000) * (0.8 + 0.2 * np.sin(PI2 * 2 * t / d))
	x += 0.15 * _motor(rng, d, 100, 200, 800, siseo=0.0)
	return s._bucle(x)


@_alta("portamaletas_ruedas", pico=0.5)
def _portamaletas_ruedas(rng: np.random.Generator) -> np.ndarray:
	"""Carro portamaletas del botones: ruedas grandes que retumban, los tubos de latón que vibran y un chirrido."""
	d = 1.5
	x = np.zeros(s._muestras(1.7))
	rodar = s._filtro(s._ruido(rng, d), 80, 600) * (0.7 + 0.3 * s._seno(9, d)) * s._arco(d, 0.4)
	s._poner(x, rodar, 0.0, 0.9)
	for _k in range(6):
		s._poner(x, s._destello(rng, rng.uniform(2200, 3800), 0.18), rng.uniform(0.05, 1.2), rng.uniform(0.2, 0.5))
	for inicio in (0.35, 1.0):
		s._poner(x, s._chirrido(1900, 2400, 0.14), inicio, 0.25)
	s._poner(x, s._siseo(rng, d, 3200, 9000) * s._arco(d, 0.5), 0.0, 0.15)
	return x


@_alta("maquina_hielo_hotel", bucle=True, pico=0.35)
def _maquina_hielo_hotel(rng: np.random.Generator) -> np.ndarray:
	"""Máquina de hielo del pasillo: el compresor zumba fuerte y cada poco cae una tanda de cubitos al depósito."""
	d = 5.0
	x = s._bucle(_motor(rng, d + 0.25, 58, 150, 900, vaiven=0.4, siseo=0.3))
	for k in range(9):
		inicio = 2.2 + 0.07 * k + rng.uniform(0, 0.03)
		s._poner_ciclico(x, s._toc(rng, rng.uniform(700, 1500), 0.06, 4000), inicio, rng.uniform(0.5, 1.0))
		s._poner_ciclico(x, s._clac(rng, 0.02, 2500, 11000), inicio, 0.5)
	return x


@_alta("hielo_cubitos", pico=0.5)
def _hielo_cubitos(rng: np.random.Generator) -> np.ndarray:
	"""Cubitos de hielo: la pala rasca el montón y varios cubitos caen y chocan."""
	x = np.zeros(s._muestras(0.9))
	pala = s._filtro(s._ruido(rng, 0.35), 1500, 8000) * s._arco(0.35, 0.5) * (0.6 + 0.4 * np.sign(s._seno(31, 0.35)))
	s._poner(x, pala, 0.0, 0.7)
	for k in range(6):
		inicio = 0.34 + 0.07 * k + rng.uniform(0, 0.03)
		f = rng.uniform(2000, 3600)
		s._poner(x, s._seno(f, 0.07) * s._decae(0.07, 0.014, 0.0005), inicio, rng.uniform(0.5, 1.0))
		s._poner(x, s._clac(rng, 0.015, 3000, 12000), inicio, 0.5)
	return x
