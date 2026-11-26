"""Sonidos propios del complemento «parque_y_naturaleza», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Olas en la orilla, columpio que chirría, balancín, carrusel, tirolina,
campanas tubulares, aparatos biosaludables, cascada, gallinas, abejas,
cañas al viento, aspersor, gaviotas, ovejas y brasas de barbacoa.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _agua, _alta


@_alta("playa_olas", bucle=True, pico=0.35)
def _playa_olas(rng: np.random.Generator) -> np.ndarray:
	"""Olas en la orilla: la ola crece, rompe y se retira con un siseo de espuma."""
	d = 6.0
	fase = (s._t(d) / d) % 1.0
	ola = np.sin(np.pi * fase) ** 3
	x = s._filtro(s._ruido(rng, d), 150, 2500) * (0.25 + 0.75 * ola)
	espuma = np.sin(np.pi * ((fase + 0.85) % 1.0)) ** 4
	x += 0.6 * s._siseo(rng, d, 3000, 10000) * (0.15 + 0.85 * espuma)
	return s._bucle(x)


@_alta("columpio_chirrido", bucle=True, pico=0.3)
def _columpio_chirrido(rng: np.random.Generator) -> np.ndarray:
	"""Columpio en marcha: las cadenas chirrían a la ida y a la vuelta y el aire silba al pasar."""
	d = 3.0
	t = s._t(d)
	x = 0.35 * s._siseo(rng, d, 2500, 8000) * np.abs(np.sin(PI2 * t / d)) ** 2
	s._poner_ciclico(x, s._chirrido(950, 1350, 0.45), 0.15, 0.8)
	s._poner_ciclico(x, s._chirrido(1300, 900, 0.45), 1.65, 0.7)
	s._poner_ciclico(x, s._clac(rng, 0.03, 1500, 8000), 0.6, 0.3)
	s._poner_ciclico(x, s._clac(rng, 0.03, 1500, 8000), 2.1, 0.3)
	return s._bucle(x)


@_alta("balancin_golpe")
def _balancin_golpe(rng: np.random.Generator) -> np.ndarray:
	"""Balancín: el eje cruje al bascular y el extremo golpea el tope de goma del suelo."""
	x = np.zeros(s._muestras(1.0))
	s._poner(x, s._chirrido(600, 420, 0.4), 0.0, 0.5)
	s._poner(x, s._toc(rng, 85, 0.3, 1200), 0.42, 1.0)
	s._poner(x, s._aire(rng, 0.08, 0.6, 0.012), 0.42)
	s._poner(x, s._toc(rng, 95, 0.2, 1200), 0.66, 0.35)
	return x


@_alta("carrusel_giro", bucle=True, pico=0.3)
def _carrusel_giro(rng: np.random.Generator) -> np.ndarray:
	"""Carrusel de suelo girando: el rodamiento ronronea y da un chirrido en cada vuelta."""
	d = 2.0
	t = s._t(d)
	x = s._filtro(s._ruido(rng, d), 120, 600) * (0.7 + 0.3 * np.sin(PI2 * 2 * t / d))
	x += 0.25 * s._siseo(rng, d, 3200, 9000)
	s._poner_ciclico(x, s._chirrido(1500, 1850, 0.16), 0.9, 0.9)
	return s._bucle(x)


@_alta("tirolina_cable")
def _tirolina_cable(rng: np.random.Generator) -> np.ndarray:
	"""Tirolina: la polea corre zumbando por el cable y hace tope al final."""
	d = 2.4
	t = s._t(d)
	x = s._filtro(s._ruido(rng, d), 900, 7000) * s._arco(d, 0.6) * (0.75 + 0.25 * np.sin(PI2 * 34 * t))
	x += 0.35 * s._filtro(s._barrido(430, 250, d, "sierra"), 300, 5000) * s._arco(d, 0.8)
	s._poner(x, s._clac(rng, 0.05, 1200, 9000), 2.15, 1.6)
	s._poner(x, s._seno(1900, 0.2) * s._decae(0.2, 0.05, 0.001), 2.15, 0.5)
	return x


@_alta("campanas_tubulares", pico=0.5)
def _campanas_tubulares(rng: np.random.Generator) -> np.ndarray:
	"""Panel musical de parque: cuatro tubos de metal golpeados, de grave a agudo."""
	x = np.zeros(s._muestras(2.6))
	for k, f in enumerate((523.25, 659.25, 783.99, 1046.5)):
		s._poner(x, s._campana(f, 1.6), 0.3 * k, 0.8)
		s._poner(x, s._aire(rng, 0.03, 0.4, 0.006), 0.3 * k)
	return x


@_alta("biosaludable_giro", pico=0.45)
def _biosaludable_giro(rng: np.random.Generator) -> np.ndarray:
	"""Aparato biosaludable: el eje gira con un chirrido de ida y otro de vuelta y un traqueteo."""
	x = np.zeros(s._muestras(1.3))
	s._poner(x, s._chirrido(700, 1000, 0.4), 0.0, 0.6)
	s._poner(x, s._chirrido(1000, 700, 0.4), 0.6, 0.6)
	for k in range(8):
		s._poner(x, s._clac(rng, 0.02, 1500, 8000), 0.05 + 0.14 * k, 0.5)
	return x


@_alta("cascada_parque", bucle=True, pico=0.4)
def _cascada_parque(rng: np.random.Generator) -> np.ndarray:
	"""Cascada pequeña: una cortina de agua que cae sobre piedra, con un fondo grave."""
	d = 4.0
	x = _agua(rng, d, 300, 10000, 45)
	x += 0.5 * s._filtro(s._ruido(rng, d), 80, 400)
	return s._bucle(x)


@_alta("gallinas_corral", bucle=True, pico=0.35)
def _gallinas_corral(rng: np.random.Generator) -> np.ndarray:
	"""Gallinas en el corral: cloqueos cortos, uno largo de vez en cuando y patas que escarban."""
	d = 5.0
	x = 0.12 * s._siseo(rng, d, 3000, 8000) * (0.5 + 0.5 * np.sin(PI2 * 3 * s._t(d) / d) ** 2)
	for _k in range(13):
		f = rng.uniform(380, 520)
		s._poner_ciclico(x, s._vocal(f, f * 1.5, 0.09, (900, 2400, 3600), 0.035), rng.uniform(0, d), rng.uniform(0.5, 1.0))
	s._poner_ciclico(x, s._vocal(420, 760, 0.45, (1000, 2600, 3800), 0.2), 1.9, 1.0)
	s._poner_ciclico(x, s._vocal(460, 800, 0.4, (1000, 2600, 3800), 0.18), 4.1, 0.8)
	return s._bucle(x)


@_alta("abejas_colmena", bucle=True, pico=0.3)
def _abejas_colmena(rng: np.random.Generator) -> np.ndarray:
	"""Colmena: el zumbido de muchas abejas, que tiembla y cambia un poco de tono."""
	d = 4.0
	t = s._t(d)
	x = np.zeros(s._muestras(d))
	for _k in range(6):
		fase0 = rng.uniform(0, PI2)
		f = rng.uniform(190, 260) * (1.0 + 0.04 * np.sin(PI2 * rng.uniform(3, 9) * t + fase0))
		fase = np.cumsum(f) / s.FRECUENCIA
		x += (2.0 * (fase % 1.0) - 1.0) * (0.6 + 0.4 * np.sin(PI2 * rng.uniform(0.3, 1.2) * t + fase0))
	x = s._filtro(x, 180, 7000)
	x += 0.5 * s._siseo(rng, d, 3200, 9000)
	return s._bucle(x)


@_alta("canaveral_viento", bucle=True, pico=0.3)
def _canaveral_viento(rng: np.random.Generator) -> np.ndarray:
	"""Cañaveral con viento: hojas secas que rozan y cañas huecas que chocan entre sí."""
	d = 5.0
	t = s._t(d)
	racha = 0.4 + 0.4 * np.sin(PI2 * t / d) ** 2 + 0.2 * np.sin(PI2 * 2 * t / d + 0.7)
	x = s._filtro(s._ruido(rng, d), 2200, 9000) * racha
	for _k in range(16):
		s._poner_ciclico(x, s._toc(rng, rng.uniform(380, 900), 0.08, 2500), rng.uniform(0, d), rng.uniform(0.3, 0.8))
	return s._bucle(x)


@_alta("aspersor_riego", bucle=True, pico=0.35)
def _aspersor_riego(rng: np.random.Generator) -> np.ndarray:
	"""Aspersor de impacto: tic, tic, tic mientras barre y un traqueteo rápido al volver."""
	d = 3.0
	x = 0.3 * s._siseo(rng, d, 3000, 10000)
	for k in range(11):
		s._poner_ciclico(x, s._clac(rng, 0.03, 1200, 9000), 0.2 * k, 1.0)
		s._poner_ciclico(x, s._siseo(rng, 0.12, 3500, 10000) * s._decae(0.12, 0.04, 0.002), 0.2 * k + 0.02, 0.6)
	for k in range(14):
		s._poner_ciclico(x, s._clac(rng, 0.02, 1500, 9000), 2.25 + 0.045 * k, 0.7)
	return s._bucle(x)


@_alta("gaviotas_playa", bucle=True, pico=0.35)
def _gaviotas_playa(rng: np.random.Generator) -> np.ndarray:
	"""Gaviotas sobre la escollera: graznidos agudos que suben y caen, sobre el rumor del mar."""
	d = 6.0
	t = s._t(d)
	x = 0.3 * s._filtro(s._ruido(rng, d), 120, 1800) * (0.6 + 0.4 * np.sin(PI2 * t / d) ** 2)
	for _k in range(7):
		inicio = rng.uniform(0, d)
		f = rng.uniform(1100, 1500)
		for repeticion in range(int(rng.integers(2, 5))):
			grito = s._vocal(f, f * rng.uniform(0.7, 0.85), 0.22, (1800, 3200, 4500), 0.12)
			s._poner_ciclico(x, grito, inicio + 0.26 * repeticion, rng.uniform(0.5, 1.0))
		s._poner_ciclico(x, s._aire(rng, 0.03, 0.3, 0.006), inicio)
	return s._bucle(x)


@_alta("ovejas_balido", bucle=True, pico=0.35)
def _ovejas_balido(rng: np.random.Generator) -> np.ndarray:
	"""Rebaño en el cercado: balidos temblorosos de varias ovejas y el tintineo suelto de las esquilas."""
	d = 6.0
	x = 0.08 * s._siseo(rng, d, 2500, 7000)
	for _k in range(5):
		f = rng.uniform(260, 420)
		duracion = rng.uniform(0.5, 0.8)
		temblor = 1.0 + 0.12 * np.sin(PI2 * 7.0 * s._t(duracion))
		balido = s._vocal(f, f * 0.92, duracion, (700, 1300, 2600), duracion / 2.5) * temblor
		s._poner_ciclico(x, balido, rng.uniform(0, d), rng.uniform(0.5, 1.0))
	for _k in range(6):
		s._poner_ciclico(
			x, s._campana(rng.uniform(900, 1300), 0.5, (1, 2.4, 3.9), (1, 0.6, 0.3)), rng.uniform(0, d), rng.uniform(0.15, 0.35)
		)
	return s._bucle(x)


@_alta("merendero_brasas", bucle=True, pico=0.3)
def _merendero_brasas(rng: np.random.Generator) -> np.ndarray:
	"""Barbacoa encendida: las brasas crepitan con chasquidos sueltos sobre un soplo de fuego."""
	d = 4.0
	x = 0.25 * s._filtro(s._ruido(rng, d), 300, 6000) * (0.7 + 0.3 * np.sin(PI2 * s._t(d) / d))
	for _k in range(70):
		s._poner_ciclico(x, s._clac(rng, rng.uniform(0.006, 0.03), 1500, 11000), rng.uniform(0, d), rng.uniform(0.2, 1.0))
	return s._bucle(x)
