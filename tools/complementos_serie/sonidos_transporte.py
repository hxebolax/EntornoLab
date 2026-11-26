"""Sonidos propios de la ampliación del complemento «transporte», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Son los que orientan a una persona ciega dentro del autobús, del tranvía y
del tren: el aviso de la próxima parada, el «parada solicitada» del
pulsador, el soplido de las puertas neumáticas, los pitidos de la rampa al
desplegarse, el traqueteo de una escalera mecánica (se oye antes de llegar
a ella) y la descarga de vacío del aseo del tren. Todos llevan agudos por
encima de 3 kHz para poder localizarlos.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _bip, _motor


@_alta("transporte_proxima_parada", pico=0.5)
def _proxima_parada(rng: np.random.Generator) -> np.ndarray:
	"""Aviso de próxima parada: dos notas que suben y una sílaba de voz sintética que sugiere el nombre."""
	x = np.zeros(s._muestras(2.2))
	s._poner(x, s._campana(988, 0.7, (1, 2.0, 3.0), (1, 0.6, 0.4)), 0.0, 0.8)
	s._poner(x, s._aire(rng, 0.05, 0.4, 0.01), 0.0)
	s._poner(x, s._campana(1319, 0.9, (1, 2.0, 3.0), (1, 0.6, 0.4)), 0.32, 0.8)
	for k, (f0, f1) in enumerate(((180, 210), (210, 170), (190, 150))):
		s._poner(x, s._vocal(f0, f1, 0.28, (700, 1200, 2600), 0.2), 1.1 + k * 0.3, 0.7)
	s._poner(x, 0.05 * s._siseo(rng, 1.0, 3200, 9000) * s._arco(1.0, 0.5), 1.05)
	return x


@_alta("transporte_pulsador_parada", pico=0.5)
def _pulsador_parada(rng: np.random.Generator) -> np.ndarray:
	"""Pulsador de parada: el clic del botón y un «din» agudo que dice que la parada está pedida."""
	x = np.zeros(s._muestras(1.1))
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0, 0.7)
	s._poner(x, s._campana(2093, 0.9, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.2)), 0.05, 0.9)
	s._poner(x, s._aire(rng, 0.04, 0.4, 0.008), 0.05)
	return x


@_alta("transporte_puerta_bus", pico=0.55)
def _puerta_bus(rng: np.random.Generator) -> np.ndarray:
	"""Puerta de autobús: tres pitidos de aviso, el soplido del aire comprimido y el golpe de goma de las hojas."""
	x = np.zeros(s._muestras(2.0))
	for k in range(3):
		s._poner(x, _bip(2400, 0.1), k * 0.2, 0.6)
	soplido = s._filtro(s._ruido(rng, 0.6), 1800, 11000) * s._decae(0.6, 0.18, 0.01)
	s._poner(x, soplido, 0.65, 0.9)
	s._poner(x, s._filtro(s._ruido(rng, 0.5), 150, 900) * s._arco(0.5, 0.7), 0.7, 0.4)
	s._poner(x, s._toc(rng, 120, 0.2, 1200), 1.25, 0.8)
	return x


@_alta("transporte_rampa_aviso", pico=0.5)
def _rampa_aviso(rng: np.random.Generator) -> np.ndarray:
	"""Rampa del autobús: pitidos lentos de aviso mientras la plancha se abate y el golpe al tocar la acera."""
	x = np.zeros(s._muestras(3.2))
	for k in range(6):
		s._poner(x, _bip(1600, 0.16), k * 0.45, 0.6)
	giro = s._filtro(s._ruido(rng, 1.8), 300, 3000) * s._arco(1.8, 0.4)
	s._poner(x, giro, 0.4, 0.25)
	s._poner(x, s._golpe(rng, "metal"), 2.4, 0.8)
	return x


@_alta("transporte_escalera_mecanica", bucle=True, pico=0.35)
def _escalera_mecanica(rng: np.random.Generator) -> np.ndarray:
	"""Escalera mecánica: el zumbido del motor, el traqueteo regular de los peldaños y el roce del pasamanos."""
	d = 4.0
	x = 0.6 * _motor(rng, d, 100, 200, 1500, siseo=0.25)
	t = s._t(d)
	x += 0.15 * s._filtro(s._ruido(rng, d), 2500, 8000) * (0.8 + 0.2 * np.sin(PI2 * 0.5 * t))
	x = s._bucle(x)
	for k in range(10):
		s._poner_ciclico(x, s._clac(rng, 0.04, 700, 6000), k * 0.4, 0.35)
	return x


@_alta("transporte_aseo_vacio", pico=0.55)
def _aseo_vacio(rng: np.random.Generator) -> np.ndarray:
	"""Aseo de tren: el pulsador, un silbido de aire y una descarga de vacío seca y fuerte que se corta de golpe."""
	x = np.zeros(s._muestras(2.0))
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0, 0.6)
	s._poner(x, s._filtro(s._ruido(rng, 0.4), 3000, 12000) * s._arco(0.4, 0.5), 0.15, 0.4)
	succion = s._filtro(s._ruido(rng, 0.7), 200, 5000) * s._decae(0.7, 0.3, 0.02)
	s._poner(x, succion + 0.4 * s._barrido(180, 90, 0.7) * s._decae(0.7, 0.25, 0.02), 0.55, 1.0)
	s._poner(x, s._toc(rng, 140, 0.15, 1500), 1.3, 0.6)
	return x
