"""Sonidos propios del complemento «obstaculos_temporales», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Son los ruidos que delatan un obstáculo que ayer no estaba: la obra (martillo
neumático, generador, polea, chapa que suena al pisarla, baliza, cinta que
vibra con el viento), la mudanza, el baldeo, la gente que hace cola, el
músico de la esquina, el perro atado, las brasas de la castañera, los
cristales rotos y la fregadora de un vestíbulo.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _agua, _alta, _bip, _motor


@_alta("martillo_neumatico", bucle=True, pico=0.4)
def _martillo_neumatico(rng: np.random.Generator) -> np.ndarray:
	"""Martillo neumático: dos ráfagas de golpes muy seguidos sobre el motor del compresor."""
	d = 3.25
	x = s._bucle(0.3 * _motor(rng, d, 48, 100, 900, siseo=0.25))
	total = len(x) / s.FRECUENCIA
	for inicio, golpes in ((0.1, 24), (1.65, 20)):
		for k in range(golpes):
			momento = inicio + k / 21.0
			if momento < total - 0.05:
				s._poner_ciclico(x, s._clac(rng, 0.035, 500, 9000), momento, rng.uniform(0.8, 1.0))
				s._poner_ciclico(x, s._seno(170, 0.035) * s._decae(0.035, 0.01, 0.001), momento, 0.6)
	return x


@_alta("generador_obra", bucle=True, pico=0.35)
def _generador_obra(rng: np.random.Generator) -> np.ndarray:
	"""Grupo electrógeno: motor de gasolina que petardea sin parar, con su siseo de escape."""
	d = 3.25
	t = s._t(d)
	x = _motor(rng, d, 55, 80, 700, siseo=0.3)
	x *= 0.65 + 0.35 * np.sign(np.sin(PI2 * 27.5 * t))
	x += 0.25 * s._filtro(s._ruido(rng, d), 1500, 6000) * (0.5 + 0.5 * np.sin(PI2 * 27.5 * t) ** 2)
	return s._bucle(x)


@_alta("murmullo_cola", bucle=True, pico=0.3)
def _murmullo_cola(rng: np.random.Generator) -> np.ndarray:
	"""Murmullo de gente parada: muchas voces sin palabras, unas encima de otras, y roce de ropa."""
	d = 5.25
	x = s._bucle(0.12 * s._filtro(s._ruido(rng, d), 300, 2500) + 0.1 * s._siseo(rng, d, 3200, 9000))
	total = len(x) / s.FRECUENCIA
	for _k in range(80):
		largo = float(rng.uniform(0.12, 0.3))
		tono = float(rng.uniform(100, 260))
		formantes = (float(rng.uniform(400, 900)), float(rng.uniform(1100, 2600)))
		silaba = s._vocal(tono, tono * float(rng.uniform(0.85, 1.15)), largo, formantes, largo / 2.5)
		s._poner_ciclico(x, silaba, float(rng.uniform(0, total)), float(rng.uniform(0.3, 1.0)))
	for _k in range(10):
		s._poner_ciclico(x, s._aire(rng, 0.05, 0.5, 0.012), float(rng.uniform(0, total)))
	return x


@_alta("musico_callejero", bucle=True, pico=0.35)
def _musico_callejero(rng: np.random.Generator) -> np.ndarray:
	"""Músico callejero: un arpegio de guitarra de cuatro acordes que da la vuelta sin costura."""
	paso = 0.3
	acordes = (
		(220.0, 261.63, 329.63, 440.0),
		(174.61, 261.63, 349.23, 440.0),
		(130.81, 261.63, 329.63, 392.0),
		(196.0, 246.94, 293.66, 392.0),
	)
	x = np.zeros(s._muestras(paso * 16))
	for compas, acorde in enumerate(acordes):
		for k, f in enumerate(acorde):
			momento = (compas * 4 + k) * paso
			s._poner_ciclico(x, s._nota(f, 1.1, 0.35, (1, 0.55, 0.4, 0.28, 0.18, 0.12, 0.08)), momento, 0.8)
			s._poner_ciclico(x, s._aire(rng, 0.06, 0.45, 0.01), momento)
			s._poner_ciclico(x, s._filtro(s._ruido(rng, 0.5), 2500, 10000) * s._decae(0.5, 0.15, 0.001), momento, 0.3)
	return x


@_alta("baliza_obra", bucle=True, pico=0.25)
def _baliza_obra(rng: np.random.Generator) -> np.ndarray:
	"""Baliza luminosa de obra: el clic del destello, dos veces por vuelta, con un pitido muy fino."""
	x = np.zeros(s._muestras(1.2))
	for momento in (0.0, 0.6):
		s._poner_ciclico(x, s._clac(rng, 0.02, 2500, 10000), momento, 1.0)
		s._poner_ciclico(x, _bip(2400, 0.05), momento + 0.005, 0.3)
	return x


@_alta("chapa_zanja")
def _chapa_zanja(rng: np.random.Generator) -> np.ndarray:
	"""Plancha de acero suelta sobre una zanja: retumba grave al pisarla y bailotea contra el asfalto."""
	x = np.zeros(s._muestras(0.9))
	s._poner(x, s._clac(rng, 0.04, 700, 9000), 0.0, 0.9)
	for parcial, peso, cola in ((92, 1.0, 0.2), (236, 0.7, 0.16), (610, 0.5, 0.12), (1480, 0.35, 0.08), (3350, 0.25, 0.05)):
		s._poner(x, s._seno(parcial, 0.8) * s._decae(0.8, cola, 0.002), 0.0, 0.45 * peso)
	s._poner(x, s._clac(rng, 0.03, 1200, 8000), 0.14, 0.5)
	s._poner(x, s._seno(236, 0.3) * s._decae(0.3, 0.07, 0.002), 0.14, 0.25)
	return x


@_alta("polea_obra", bucle=True, pico=0.3)
def _polea_obra(rng: np.random.Generator) -> np.ndarray:
	"""Polea de obra: la rueda chirría a cada tirón de la cuerda y el cubo da un golpe de chapa al llegar."""
	d = 4.0
	x = np.zeros(s._muestras(d))
	for k in range(6):
		momento = 0.2 + k * 0.5
		s._poner_ciclico(x, s._chirrido(900 + 40 * (k % 2), 1350, 0.26) * s._arco(0.26, 0.8), momento, 0.35)
		s._poner_ciclico(x, s._filtro(s._ruido(rng, 0.3), 2500, 9000) * s._arco(0.3, 1.2), momento, 0.4)
	s._poner_ciclico(x, s._clac(rng, 0.04, 900, 9000), 3.3, 1.0)
	for parcial, peso in ((310, 1.0), (790, 0.6), (2100, 0.4), (4300, 0.25)):
		s._poner_ciclico(x, s._seno(parcial, 0.5) * s._decae(0.5, 0.1, 0.002), 3.3, 0.4 * peso)
	return x


@_alta("fregadora_suelos", bucle=True, pico=0.35)
def _fregadora_suelos(rng: np.random.Generator) -> np.ndarray:
	"""Máquina fregadora: el motor de aspiración y los cepillos mojados que giran sobre el suelo."""
	d = 3.75
	t = s._t(d)
	x = _motor(rng, d, 92, 200, 2500, vaiven=0.4, siseo=0.4)
	x += 0.5 * s._filtro(s._ruido(rng, d), 800, 6500) * (0.6 + 0.4 * np.sin(PI2 * 6.0 * t) ** 2)
	return s._bucle(x)


@_alta("manguera_baldeo", bucle=True, pico=0.35)
def _manguera_baldeo(rng: np.random.Generator) -> np.ndarray:
	"""Baldeo de la calle: el chorro de la manguera a presión contra el suelo y el agua que corre."""
	d = 3.75
	t = s._t(d)
	x = _agua(rng, d, 1200, 10000, 25)
	x += 0.5 * s._filtro(s._ruido(rng, d), 2500, 12000) * (0.7 + 0.3 * np.sin(PI2 * 0.8 * t))
	return s._bucle(x)


@_alta("brasas_castanera", bucle=True, pico=0.3)
def _brasas_castanera(rng: np.random.Generator) -> np.ndarray:
	"""Brasas: un fondo sordo de fuego con chasquidos secos que saltan aquí y allá."""
	d = 4.25
	x = s._bucle(0.18 * s._filtro(s._ruido(rng, d), 150, 1400) + 0.08 * s._siseo(rng, d, 3200, 9000))
	total = len(x) / s.FRECUENCIA
	for _k in range(90):
		s._poner_ciclico(
			x, s._clac(rng, 0.02, float(rng.uniform(1200, 4000)), 11000), float(rng.uniform(0, total)), float(rng.uniform(0.2, 1.0))
		)
	return x


@_alta("cinta_baliza", bucle=True, pico=0.3)
def _cinta_baliza(rng: np.random.Generator) -> np.ndarray:
	"""Cinta de balizar tensa que vibra con el viento: un zumbido de plástico que crece y mengua."""
	d = 3.25
	t = s._t(d)
	racha = 0.35 + 0.65 * np.sin(np.pi * t / d) ** 2
	x = s._filtro(s._ruido(rng, d), 1500, 9000) * (0.5 + 0.5 * np.sign(np.sin(PI2 * 31.0 * t))) * racha
	x += 0.25 * np.sin(PI2 * 124.0 * t) * racha
	return s._bucle(x)


@_alta("perro_atado", bucle=True, pico=0.35)
def _perro_atado(rng: np.random.Generator) -> np.ndarray:
	"""Perro atado que espera: jadea, sacude el collar y suelta dos ladridos cortos."""
	d = 5.0
	x = np.zeros(s._muestras(d))
	for k in range(9):
		jadeo = s._filtro(s._ruido(rng, 0.16), 1500, 7000) * s._arco(0.16, 1.0)
		s._poner_ciclico(x, jadeo, 0.2 + k * 0.3, 0.3 if k % 2 == 0 else 0.2)
	for momento in (3.2, 3.55):
		s._poner_ciclico(x, s._vocal(430, 300, 0.17, (850, 1900), 0.06), momento, 1.0)
		s._poner_ciclico(x, s._aire(rng, 0.08, 0.6, 0.02), momento)
	for momento in (4.1, 4.2, 4.33):
		s._poner_ciclico(x, s._destello(rng, 3300, 0.1), momento, 0.35)
	return x


@_alta("cristales_rotos", pico=0.5)
def _cristales_rotos(rng: np.random.Generator) -> np.ndarray:
	"""Cristales rotos bajo el zapato: crujen y tintinean unos contra otros."""
	x = np.zeros(s._muestras(0.65))
	crujido = s._filtro(s._ruido(rng, 0.3), 2500, 12000) * s._decae(0.3, 0.08, 0.004)
	s._poner(x, crujido, 0.0, 0.8)
	for _k in range(14):
		s._poner(x, s._destello(rng, float(rng.uniform(2500, 6000)), 0.09), float(rng.uniform(0.0, 0.45)), float(rng.uniform(0.3, 0.8)))
	return x


@_alta("montamuebles", bucle=True, pico=0.35)
def _montamuebles(rng: np.random.Generator) -> np.ndarray:
	"""Montamuebles de mudanzas: el motor eléctrico y el carraqueo de la plataforma que sube por el carril."""
	d = 3.25
	x = s._bucle(_motor(rng, d, 76, 200, 1800, siseo=0.3))
	total = len(x) / s.FRECUENCIA
	for k in range(int(total * 9)):
		s._poner_ciclico(x, s._clac(rng, 0.025, 1200, 8000), k / 9.0, 0.7)
	return x
