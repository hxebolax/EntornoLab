"""Sonidos propios de la ampliación del complemento «juego», sintetizados con numpy (mismo sistema que ``sonidos.py``).

En un audiojuego el sonido ES el objeto: cada personaje, trampa o
mecanismo nuevo tiene una voz propia que se reconoce y se localiza (el
ronquido del dragón dormido, el burbujeo del caldero, el zumbido del
portal, la arena del reloj, los cuatro tonos del panel de memoria, el
ulular del búho…). Todos llevan agudos por encima de 3 kHz para que se
puedan situar en el espacio.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _bip, _motor

# Tonos del panel de memoria (mi, do sostenido, la y mi grave): fáciles de distinguir entre sí.
TONOS_SIMON = (659.3, 554.4, 440.0, 329.6)


@_alta("juego_dragon_ronquido", bucle=True, pico=0.45)
def _dragon_ronquido(rng: np.random.Generator) -> np.ndarray:
	"""Dragón dormido: inspira con un ronquido grave y áspero y suelta el aire con un siseo de brasas."""
	d = 5.0
	x = 0.03 * s._siseo(rng, d, 3200, 9000)
	x = s._bucle(x)
	for ciclo in range(2):
		t0 = ciclo * 2.5
		ronquido = s._vocal(70, 55, 1.2, (300, 650), 0.9) + 0.6 * s._filtro(s._ruido(rng, 1.2), 60, 400) * s._arco(1.2, 1.5)
		s._poner_ciclico(x, ronquido * s._arco(1.2, 0.6), t0, 0.9)
		soplido = s._filtro(s._ruido(rng, 1.0), 2500, 10000) * s._arco(1.0, 1.2)
		s._poner_ciclico(x, soplido, t0 + 1.3, 0.35)
	return x


@_alta("juego_rugido", pico=0.6)
def _rugido(rng: np.random.Generator) -> np.ndarray:
	"""Dragón que se despierta: un rugido grave y rasposo que sube y se apaga con un bufido de fuego."""
	x = np.zeros(s._muestras(2.4))
	rugido = s._vocal(80, 120, 1.3, (350, 800, 2400), 1.0) + 0.7 * s._filtro(s._ruido(rng, 1.3), 100, 1500) * s._arco(1.3, 0.6)
	s._poner(x, rugido * s._arco(1.3, 0.4), 0.0, 1.0)
	s._poner(x, s._aire(rng, 0.08, 0.5, 0.02), 0.0)
	fuego = s._filtro(s._ruido(rng, 0.9), 1500, 11000) * s._decae(0.9, 0.35, 0.05)
	s._poner(x, fuego, 1.3, 0.7)
	return x


@_alta("juego_canonazo", pico=0.55)
def _canonazo(rng: np.random.Generator) -> np.ndarray:
	"""Cañón pirata: la mecha que chisporrotea, el estampido y el retumbar que se aleja."""
	x = np.zeros(s._muestras(3.0))
	for _k in range(14):
		s._poner(x, s._clac(rng, 0.012, 3000, 11000), rng.uniform(0.0, 0.6), rng.uniform(0.2, 0.5))
	estampido = s._filtro(s._ruido(rng, 0.25), 40, 6000) * s._decae(0.25, 0.06, 0.001) + s._toc(rng, 55, 0.25, 900)
	s._poner(x, estampido, 0.7, 1.0)
	retumbo = s._filtro(s._ruido(rng, 2.0), 30, 250) * s._decae(2.0, 0.7, 0.05)
	s._poner(x, retumbo, 0.75, 0.8)
	return x


@_alta("juego_caldero", bucle=True, pico=0.35)
def _caldero(rng: np.random.Generator) -> np.ndarray:
	"""Caldero al fuego: burbujas gordas que revientan sobre el chisporroteo de la leña."""
	d = 4.0
	x = 0.12 * s._filtro(s._ruido(rng, d), 80, 600) + 0.04 * s._siseo(rng, d, 3500, 10000)
	x = s._bucle(x)
	for _k in range(26):
		f = rng.uniform(120, 320)
		burbuja = s._barrido(f, f * 2.2, 0.08) * s._decae(0.08, 0.03, 0.004)
		s._poner_ciclico(x, burbuja, rng.uniform(0, d), rng.uniform(0.4, 0.9))
	for _k in range(30):
		s._poner_ciclico(x, s._clac(rng, 0.015, 2500, 11000), rng.uniform(0, d), rng.uniform(0.2, 0.6))
	return x


@_alta("juego_portal", bucle=True, pico=0.35)
def _portal(rng: np.random.Generator) -> np.ndarray:
	"""Portal mágico: un acorde que late despacio y un brillo de campanillas que gira alrededor."""
	d = 6.0
	t = s._t(d)
	latido = 0.6 + 0.4 * np.sin(PI2 * (2 / d) * t)
	x = (np.sin(PI2 * 110 * t) + 0.6 * np.sin(PI2 * 165 * t) + 0.4 * np.sin(PI2 * 220.5 * t)) * latido * 0.4
	x += 0.08 * s._siseo(rng, d, 4000, 11000) * latido
	x = s._bucle(x)
	for k in range(12):
		s._poner_ciclico(x, s._destello(rng, 2600 + 300 * (k % 5), 0.25), k * 0.5, 0.3)
	return x


@_alta("juego_reloj_arena", bucle=True, pico=0.3)
def _reloj_arena(rng: np.random.Generator) -> np.ndarray:
	"""Reloj de arena: un hilo fino de arena que cae sin parar sobre el montoncito de abajo."""
	d = 3.0
	hilo = s._filtro(s._ruido(rng, d), 3500, 12000)
	grano = np.abs(s._filtro(s._ruido(rng, d), 20, 120))
	x = hilo * (0.7 + 0.3 * grano / (float(np.max(grano)) or 1.0))
	x += 0.25 * s._filtro(s._ruido(rng, d), 600, 2500)
	return s._bucle(x)


@_alta("juego_simon", pico=0.5)
def _simon(rng: np.random.Generator) -> np.ndarray:
	"""Panel de memoria: los cuatro botones suenan uno tras otro, cada uno con su nota."""
	x = np.zeros(s._muestras(2.2))
	for k, f in enumerate(TONOS_SIMON):
		s._poner(x, s._clac(rng, 0.02, 1500, 9000), k * 0.45, 1.0)
		s._poner(x, s._filtro(s._ruido(rng, 0.3), 4000, 10000) * s._arco(0.3, 1.2), k * 0.45 + 0.01, 0.25)
		s._poner(x, _bip(f, 0.35) + 0.2 * s._seno(f * 4, 0.35) * s._arco(0.35, 0.3), k * 0.45 + 0.01, 0.8)
	return x


@_alta("juego_robot", bucle=True, pico=0.35)
def _robot(rng: np.random.Generator) -> np.ndarray:
	"""Robot guía: el zumbido de sus motores al girar la cabeza y unos pitidos que parecen frases."""
	d = 5.0
	x = 0.4 * _motor(rng, 1.0, 160, 400, 3000, siseo=0.4)
	cuerpo = np.zeros(s._muestras(d))
	s._poner(cuerpo, x * s._arco(1.0, 0.5), 0.3, 0.5)
	s._poner(cuerpo, x * s._arco(1.0, 0.5), 3.0, 0.4)
	cuerpo += 0.02 * s._siseo(rng, d, 3200, 9000)
	cuerpo = s._bucle(cuerpo)
	for k, f in enumerate((1800, 2400, 1500, 2100, 2700)):
		s._poner_ciclico(cuerpo, _bip(f, 0.08), 1.6 + k * 0.13, 0.6)
	return cuerpo


@_alta("juego_buho", pico=0.5)
def _buho(rng: np.random.Generator) -> np.ndarray:
	"""Búho: «uh… uh-uuuh», grave y suave, con un roce de plumas al moverse en la percha."""
	x = np.zeros(s._muestras(2.4))
	for t0, d, f in ((0.0, 0.35, 390), (0.7, 0.2, 400), (0.95, 0.7, 380)):
		uh = s._seno(f, d) + 0.15 * s._seno(2 * f, d)
		s._poner(x, uh * s._arco(d, 0.8), t0, 0.8)
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 3000, 9000) * s._arco(0.3, 1.0), 1.9, 0.8)
	# Antes de ulular, el búho se acomoda en la percha: un roce de plumas que deja situarlo.
	s._poner(x, s._filtro(s._ruido(rng, 0.25), 3000, 9000) * s._arco(0.25, 1.0), 0.4, 0.6)
	return x


@_alta("juego_maullido", pico=0.5)
def _maullido(rng: np.random.Generator) -> np.ndarray:
	"""Gato: un maullido que sube y baja («miau») y un ronroneo corto."""
	x = np.zeros(s._muestras(1.9))
	s._poner(x, s._vocal(520, 760, 0.25, (900, 2200, 3600), 0.3), 0.0, 0.7)
	s._poner(x, s._vocal(760, 430, 0.45, (800, 1800, 3400), 0.3), 0.24, 0.8)
	t = s._t(0.9)
	ronroneo = s._filtro(s._ruido(rng, 0.9), 40, 400) * (0.5 + 0.5 * np.sin(PI2 * 25 * t)) * s._arco(0.9, 0.5)
	s._poner(x, ronroneo, 0.9, 0.5)
	return x


@_alta("juego_fantasma", bucle=True, pico=0.3)
def _fantasma(rng: np.random.Generator) -> np.ndarray:
	"""Fantasma: un lamento hueco que sube y baja («uuuuh») y el roce de la sábana."""
	d = 6.0
	t = s._t(d)
	f = 300 + 80 * np.sin(PI2 * (1 / d) * t) + 6 * np.sin(PI2 * 5 * t)
	lamento = np.sin(PI2 * np.cumsum(f) / s.FRECUENCIA)
	lamento = s._filtro(lamento + 0.3 * np.sign(lamento), 200, 1800) * (0.5 + 0.5 * np.sin(PI2 * (2 / d) * t) ** 2)
	tela = s._filtro(s._ruido(rng, d), 3000, 9000) * (0.4 + 0.6 * np.abs(np.sin(PI2 * (3 / d) * t)))
	return s._bucle(0.8 * lamento + 0.35 * tela)


@_alta("juego_cuerno", pico=0.55)
def _cuerno(rng: np.random.Generator) -> np.ndarray:
	"""Cuerno de caza: dos toques largos y metálicos, el segundo más agudo."""
	x = np.zeros(s._muestras(2.6))
	for t0, f, d in ((0.0, 233.1, 0.9), (1.0, 349.2, 1.3)):
		toque = s._barrido(f * 0.97, f, d, "sierra")
		toque = s._filtro(toque, 150, 4500) * s._arco(d, 0.4)
		s._poner(x, toque, t0, 0.8)
		s._poner(x, s._aire(rng, 0.08, 0.4, 0.02), t0)
	return x


@_alta("juego_litofono", pico=0.55)
def _litofono(rng: np.random.Generator) -> np.ndarray:
	"""Litófono de piedras: cinco losas que suenan secas y claras, de grave a agudo."""
	x = np.zeros(s._muestras(2.4))
	for k, f in enumerate((587.3, 659.3, 784.0, 880.0, 1046.5)):
		piedra = s._campana(f, 0.6, (1, 2.32, 4.25, 6.63), (1, 0.5, 0.3, 0.2))
		s._poner(x, piedra, k * 0.35, 0.8)
		s._poner(x, s._golpe(rng, "piedra")[: s._muestras(0.1)], k * 0.35, 0.5)
	return x


@_alta("juego_escotilla", pico=0.55)
def _escotilla(rng: np.random.Generator) -> np.ndarray:
	"""Escotilla de nave espacial: pitido doble, el siseo largo de la presión y el golpe del cierre."""
	x = np.zeros(s._muestras(2.0))
	s._poner(x, _bip(1760, 0.08), 0.0, 0.6)
	s._poner(x, _bip(2349, 0.08), 0.12, 0.6)
	siseo = s._filtro(s._ruido(rng, 0.9), 2500, 12000) * s._decae(0.9, 0.35, 0.02)
	s._poner(x, siseo, 0.3, 0.9)
	s._poner(x, s._filtro(s._barrido(90, 60, 0.6, "sierra"), 60, 900) * s._arco(0.6, 0.6), 0.4, 0.4)
	s._poner(x, s._golpe(rng, "metal"), 1.2, 0.8)
	return x


@_alta("juego_loro", pico=0.5)
def _loro(rng: np.random.Generator) -> np.ndarray:
	"""Loro: dos graznidos ásperos y una «palabra» chillona de tres sílabas."""
	x = np.zeros(s._muestras(1.8))
	for t0 in (0.0, 0.3):
		graznido = s._vocal(900, 650, 0.18, (1400, 2800, 4200), 0.12) + 0.4 * s._filtro(s._ruido(rng, 0.18), 2000, 8000) * s._decae(
			0.18, 0.08
		)
		s._poner(x, graznido, t0, 0.9)
	for k, (f0, f1) in enumerate(((700, 820), (820, 640), (640, 900))):
		s._poner(x, s._vocal(f0, f1, 0.16, (1100, 2500, 3800), 0.12), 0.8 + k * 0.18, 0.8)
	return x


@_alta("juego_dado", pico=0.55)
def _dado(rng: np.random.Generator) -> np.ndarray:
	"""Dado gigante de espuma dura: rueda dando tumbos, cada golpe más flojo, y se para."""
	x = np.zeros(s._muestras(1.6))
	t0 = 0.0
	for k in range(6):
		s._poner(x, s._toc(rng, 260 - 15 * k, 0.12, 2200), t0, 0.9 * (0.8**k))
		s._poner(x, s._aire(rng, 0.03, 0.4, 0.006), t0, 0.8**k)
		t0 += 0.28 * (0.82**k)
	return x
