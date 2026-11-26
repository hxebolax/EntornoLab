"""Sonidos propios del complemento «cultura_y_ocio», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Cubren lo que suena de verdad en un cine, un teatro, una sala de conciertos,
una bolera y unos recreativos: la palomitera, el proyector, la música de las
máquinas, los bolos, el aire de la mesa de hockey y varios instrumentos.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _bip, _motor


def _ciclo(y: np.ndarray) -> np.ndarray:
	"""Bucle exacto de una señal que ya es periódica (hecha con ``_poner_ciclico``): repite su principio y lo funde."""
	return s._bucle(np.concatenate([y, y[: s._muestras(0.25)]]))


@_alta("palomitera", bucle=True, pico=0.35)
def _palomitera(rng: np.random.Generator) -> np.ndarray:
	"""Máquina de palomitas: el motor que remueve y los granos que estallan contra el cristal."""
	d = 4.0
	x = s._bucle(0.3 * _motor(rng, d, 55, 200, 1500, siseo=0.5))
	largo = len(x) / s.FRECUENCIA
	for _k in range(48):
		f = rng.uniform(900, 2600)
		estallido = s._seno(f, 0.03) * s._decae(0.03, 0.006, 0.0005) + s._clac(rng, 0.03, 2000, 10000)
		s._poner_ciclico(x, estallido, rng.uniform(0, largo), rng.uniform(0.5, 1.2))
	return x


@_alta("proyector_cine", bucle=True, pico=0.3)
def _proyector_cine(rng: np.random.Generator) -> np.ndarray:
	"""Proyector: el ventilador sopla y el mecanismo hace un tableteo rápido y regular."""
	y = s._bucle(0.5 * _motor(rng, 2.0, 100, 400, 3000, siseo=0.6))
	for k in range(42):
		s._poner_ciclico(y, s._clac(rng, 0.012, 1800, 9000), k * (len(y) / s.FRECUENCIA) / 42, 0.9)
	return y


@_alta("recreativa_melodia", bucle=True, pico=0.3)
def _recreativa_melodia(rng: np.random.Generator) -> np.ndarray:
	"""Máquina recreativa en espera: una melodía de ocho bits que se repite, con algún disparo."""
	paso = 0.2
	notas = (659.25, 783.99, 987.77, 783.99, 659.25, 523.25, 587.33, 783.99, 880.0, 783.99, 659.25, 523.25, 587.33, 659.25, 523.25, 392.0)
	y = np.zeros(s._muestras(paso * len(notas)))
	for k, f in enumerate(notas):
		s._poner_ciclico(y, s._barrido(f, f, 0.18, "cuadrada") * s._decae(0.18, 0.09, 0.002), k * paso, 0.5)
		if k % 4 == 0:
			s._poner_ciclico(y, s._barrido(f / 4, f / 4, 0.3, "sierra") * s._decae(0.3, 0.15, 0.004), k * paso, 0.4)
	for inicio in (0.9, 2.5):
		s._poner_ciclico(y, s._barrido(2400, 600, 0.12, "cuadrada") * s._arco(0.12, 0.5), inicio, 0.3)
		s._poner_ciclico(y, s._aire(rng, 0.05, 0.3, 0.01), inicio)
	return _ciclo(y)


@_alta("pinball_campanas", pico=0.5)
def _pinball_campanas(rng: np.random.Generator) -> np.ndarray:
	"""Pinball: el muelle lanza la bola, rebota en los topes con chasquidos y suenan dos campanas de puntos."""
	x = np.zeros(s._muestras(1.9))
	s._poner(x, s._barrido(180, 520, 0.14) * s._arco(0.14, 0.6), 0.0, 0.6)
	s._poner(x, s._clac(rng, 0.04, 900, 8000), 0.13, 0.9)
	for inicio in (0.42, 0.55, 0.63, 0.86, 1.02):
		s._poner(x, s._toc(rng, 240, 0.07, 2500), inicio, 0.7)
		s._poner(x, s._clac(rng, 0.03, 2000, 10000), inicio, 0.6)
	for inicio, f in ((0.6, 1760.0), (0.95, 2217.0), (1.15, 2637.0)):
		s._poner(x, s._campana(f, 0.6, (1, 2.4, 3.9), (1, 0.6, 0.35)), inicio, 0.6)
	return x


@_alta("hockey_aire", bucle=True, pico=0.3)
def _hockey_aire(rng: np.random.Generator) -> np.ndarray:
	"""Mesa de hockey de aire en marcha: la turbina zumba y el aire silba por los agujeros del tablero."""
	d = 3.5
	t = s._t(d)
	x = 0.5 * _motor(rng, d, 92, 250, 1800, siseo=0.3)
	x += 0.8 * s._filtro(s._ruido(rng, d), 2200, 9500) * (0.85 + 0.15 * np.sin(PI2 * 0.6 * t))
	return s._bucle(x)


@_alta("bolera_retorno", bucle=True, pico=0.35)
def _bolera_retorno(rng: np.random.Generator) -> np.ndarray:
	"""Retorno de bolas: el motor de la cinta, una bola que llega rodando por el carril y choca con las que esperan."""
	y = s._bucle(0.35 * _motor(rng, 5.25, 48, 150, 900, siseo=0.35))
	rodar = s._filtro(s._ruido(rng, 1.8), 60, 500) * s._arco(1.8, 1.2) * (0.7 + 0.3 * np.sign(s._seno(9, 1.8)))
	s._poner_ciclico(y, rodar, 0.6, 1.6)
	s._poner_ciclico(y, s._filtro(s._ruido(rng, 1.8), 2500, 7000) * s._arco(1.8, 1.2), 0.6, 0.25)
	for inicio, g in ((2.35, 1.0), (2.52, 0.5), (2.62, 0.25)):
		s._poner_ciclico(y, s._toc(rng, 320, 0.09, 2800), inicio, g)
		s._poner_ciclico(y, s._clac(rng, 0.03, 1500, 9000), inicio, 0.7 * g)
	return y


@_alta("bolos_derribo", pico=0.55)
def _bolos_derribo(rng: np.random.Generator) -> np.ndarray:
	"""Lanzamiento en la bolera: la bola rueda por la madera, se aleja y derriba los bolos con estrépito."""
	x = np.zeros(s._muestras(2.6))
	t = s._t(1.4)
	rodar = s._filtro(s._ruido(rng, 1.4), 70, 700) * np.clip(t / 0.15, 0, 1) * (1.0 - 0.5 * t / 1.4)
	s._poner(x, rodar, 0.0, 0.8)
	s._poner(x, s._toc(rng, 110, 0.15, 1200), 0.0, 0.8)
	for _k in range(11):
		inicio = 1.4 + rng.uniform(0, 0.45)
		f = rng.uniform(450, 1300)
		s._poner(x, s._toc(rng, f, 0.12, 3000), inicio, rng.uniform(0.5, 1.0))
		s._poner(x, s._clac(rng, 0.04, 1800, 10000), inicio, rng.uniform(0.3, 0.7))
	s._poner(x, s._filtro(s._ruido(rng, 0.6), 300, 5000) * s._decae(0.6, 0.18, 0.01), 1.4, 0.5)
	return x


@_alta("arpa_glissando", pico=0.5)
def _arpa_glissando(rng: np.random.Generator) -> np.ndarray:
	"""Arpa: los dedos recorren las cuerdas de grave a agudo y las notas se quedan sonando."""
	x = np.zeros(s._muestras(2.4))
	escala = (261.63, 293.66, 329.63, 392.0, 440.0, 523.25, 587.33, 659.25, 783.99, 880.0, 1046.5, 1174.7)
	for k, f in enumerate(escala):
		s._poner(x, s._nota(f, 1.3, 0.45, (1, 0.5, 0.3, 0.15, 0.08)), k * 0.07, 0.7)
		s._poner(x, s._aire(rng, 0.04, 0.5, 0.008), k * 0.07)
	return x


@_alta("bateria_ritmo", pico=0.55)
def _bateria_ritmo(rng: np.random.Generator) -> np.ndarray:
	"""Batería: bombo, caja y charles en un compás, y un platillo para acabar."""
	x = np.zeros(s._muestras(2.3))
	paso = 0.16
	for k in range(8):
		s._poner(x, s._filtro(s._ruido(rng, 0.05), 6000, 13000) * s._decae(0.05, 0.012, 0.0005), k * paso, 0.45)
		if k in (0, 3, 4):
			s._poner(x, s._toc(rng, 62, 0.22, 900), k * paso, 1.0)
		if k in (2, 6, 7):
			s._poner(x, s._filtro(s._ruido(rng, 0.16), 1200, 9000) * s._decae(0.16, 0.045, 0.001), k * paso, 0.8)
			s._poner(x, s._seno(190, 0.1) * s._decae(0.1, 0.03), k * paso, 0.5)
	s._poner(x, s._toc(rng, 62, 0.22, 900), 8 * paso, 1.0)
	s._poner(x, s._filtro(s._ruido(rng, 1.0), 3500, 13000) * s._decae(1.0, 0.3, 0.002), 8 * paso, 0.7)
	return x


@_alta("contrabajo_pizzicato", pico=0.5)
def _contrabajo_pizzicato(rng: np.random.Generator) -> np.ndarray:
	"""Contrabajo: tres cuerdas graves pellizcadas con el dedo, redondas y con cuerpo de madera."""
	x = np.zeros(s._muestras(2.2))
	for k, f in enumerate((98.0, 73.42, 110.0)):
		nota = sum(
			a * s._seno(f * (n + 1), 1.1) * s._decae(1.1, 0.45 / (1 + 0.5 * n), 0.005)
			for n, a in enumerate((1, 0.7, 0.45, 0.3, 0.2, 0.12, 0.08))
		)
		s._poner(x, nota, k * 0.5, 0.8)
		# El dedo que suelta la cuerda: sin estos agudos, una nota tan grave no se podría situar.
		s._poner(x, s._aire(rng, 0.09, 1.3, 0.02), k * 0.5)
		s._poner(x, s._toc(rng, 210, 0.06, 2600), k * 0.5, 0.35)
	return x


@_alta("audioguia_locucion", pico=0.5)
def _audioguia_locucion(rng: np.random.Generator) -> np.ndarray:
	"""Audioguía o estación con audio: un tono de inicio y una voz que explica, sin palabras que se entiendan."""
	x = np.zeros(s._muestras(2.9))
	s._poner(x, _bip(1175, 0.12), 0.0, 0.7)
	s._poner(x, _bip(1568, 0.16), 0.14, 0.7)
	silabas = (
		(150, 135, (700, 1200)),
		(140, 150, (400, 2000)),
		(155, 130, (500, 1500)),
		(135, 125, (750, 1100)),
		(150, 160, (350, 2200)),
		(145, 120, (600, 1300)),
		(130, 105, (700, 1150)),
	)
	for k, (f0, f1, formantes) in enumerate(silabas):
		inicio = 0.5 + k * 0.31 + rng.uniform(-0.02, 0.02)
		s._poner(x, s._vocal(f0, f1, 0.26, formantes, 0.12), inicio, 0.5)
		s._poner(x, s._filtro(s._ruido(rng, 0.06), 3500, 9000) * s._arco(0.06, 1.0), inicio - 0.04, 0.5)
	return x


@_alta("musica_discoteca", bucle=True, pico=0.35)
def _musica_discoteca(rng: np.random.Generator) -> np.ndarray:
	"""Música de baile a través de los altavoces: bombo a negras, charles a contratiempo, palmas y un bajo."""
	negra = 0.48
	y = np.zeros(s._muestras(negra * 8))
	bajo = (55.0, 55.0, 65.41, 55.0, 49.0, 49.0, 65.41, 73.42)
	for k in range(8):
		s._poner_ciclico(y, s._toc(rng, 55, 0.28, 800), k * negra, 1.0)
		s._poner_ciclico(y, s._filtro(s._ruido(rng, 0.07), 7000, 13000) * s._decae(0.07, 0.018, 0.0005), (k + 0.5) * negra, 0.5)
		nota = s._filtro(s._barrido(bajo[k], bajo[k], 0.2, "sierra"), 40, 900) * s._decae(0.2, 0.08, 0.004)
		s._poner_ciclico(y, nota, (k + 0.5) * negra, 0.6)
		if k % 2 == 1:
			s._poner_ciclico(y, s._filtro(s._ruido(rng, 0.14), 1000, 8000) * s._decae(0.14, 0.035, 0.001), k * negra, 0.6)
	for k, f in enumerate((880.0, 1046.5, 1318.5, 1046.5)):
		s._poner_ciclico(y, s._barrido(f, f, 0.2, "cuadrada") * s._decae(0.2, 0.07, 0.003), (2 * k + 0.25) * negra, 0.18)
	return _ciclo(y)
