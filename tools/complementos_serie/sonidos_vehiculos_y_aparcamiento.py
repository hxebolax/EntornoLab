"""Sonidos propios del complemento «vehiculos_y_aparcamiento», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Motores al ralentí (los de serie ``trafico/…`` son pasadas, no bucles), el
pitido de marcha atrás, el camión de la basura, la barredora, la barrera y
la columna de tiques del aparcamiento, el túnel de lavado y poco más.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _agua, _alta, _bip, _motor


def _diesel(rng: np.random.Generator, d: float, f: float = 38.0, golpeteo: float = 13.0) -> np.ndarray:
	"""Motor diésel al ralentí durante ``d`` segundos (sin preparar para bucle): zumbido grave y el golpeteo de los cilindros."""
	t = s._t(d)
	x = _motor(rng, d, f, 70, 900, siseo=0.2)
	x += 0.5 * s._filtro(s._ruido(rng, d), 900, 4500) * (0.5 + 0.5 * np.sign(np.sin(PI2 * golpeteo * t)))
	return x


@_alta("vehiculos_ralenti_diesel", bucle=True, pico=0.35)
def _ralenti_diesel(rng: np.random.Generator) -> np.ndarray:
	"""Camión, autobús o furgón parado con el motor en marcha: diésel al ralentí, grave y con golpeteo."""
	return s._bucle(_diesel(rng, 4.0))


@_alta("vehiculos_ralenti_gasolina", bucle=True, pico=0.28)
def _ralenti_gasolina(rng: np.random.Generator) -> np.ndarray:
	"""Coche parado con el motor en marcha: un ronroneo suave y el soplo del escape."""
	d = 3.5
	t = s._t(d)
	x = _motor(rng, d, 27, 60, 600, vaiven=0.0, siseo=0.25)
	x += 0.3 * s._filtro(s._ruido(rng, d), 1500, 6000) * (0.6 + 0.4 * np.sin(PI2 * 27 * t) ** 2)
	return s._bucle(x)


@_alta("vehiculos_marcha_atras", bucle=True, pico=0.45)
def _marcha_atras(rng: np.random.Generator) -> np.ndarray:
	"""Vehículo grande maniobrando marcha atrás: pitido que se repite, pi, pi, pi, sobre el motor diésel."""
	x = s._bucle(0.35 * _diesel(rng, 2.5))
	periodo = len(x) / s.FRECUENCIA / 3.0
	for k in range(3):
		s._poner_ciclico(x, _bip(1250, 0.38) * 1.6, 0.05 + k * periodo)
		s._poner_ciclico(x, s._aire(rng, 0.05, 0.4, 0.01), 0.05 + k * periodo)
	return x


@_alta("vehiculos_camion_basura", bucle=True, pico=0.4)
def _camion_basura(rng: np.random.Generator) -> np.ndarray:
	"""Camión de la basura trabajando: el motor, el gemido del elevador hidráulico, el contenedor que vuelca y la prensa."""
	x = s._bucle(0.6 * _diesel(rng, 5.75, 42, 15))
	gemido = (s._barrido(310, 520, 1.6, "sierra") * 0.5 + s._barrido(620, 1040, 1.6)) * s._arco(1.6, 0.6)
	s._poner_ciclico(x, s._filtro(gemido, 250, 5000), 0.4, 0.55)
	vuelco = s._filtro(s._ruido(rng, 0.7), 150, 7000) * s._decae(0.7, 0.18, 0.01)
	s._poner_ciclico(x, vuelco, 2.1, 1.3)
	s._poner_ciclico(x, s._toc(rng, 95, 0.3, 1800), 2.1, 1.2)
	s._poner_ciclico(x, s._toc(rng, 110, 0.25, 2200), 2.55, 0.9)
	prensa = s._filtro(s._ruido(rng, 1.4), 2500, 9000) * s._arco(1.4, 0.8)
	s._poner_ciclico(x, prensa, 3.2, 0.45)
	s._poner_ciclico(x, s._barrido(500, 300, 1.2, "sierra") * s._arco(1.2, 0.6), 3.3, 0.25)
	return x


@_alta("vehiculos_barredora", bucle=True, pico=0.4)
def _barredora(rng: np.random.Generator) -> np.ndarray:
	"""Barredora: los cepillos raspan el suelo en redondo, la turbina aspira y el motor zumba."""
	d = 4.0
	t = s._t(d)
	x = 0.7 * _motor(rng, d, 74, 150, 1400, siseo=0.2)
	x += 0.9 * s._filtro(s._ruido(rng, d), 1200, 8000) * (0.55 + 0.45 * np.sin(PI2 * 5.5 * t) ** 2)
	x += 0.5 * s._filtro(s._ruido(rng, d), 250, 1100)
	x += 0.12 * np.sin(PI2 * 1900 * t) * (0.7 + 0.3 * np.sin(PI2 * 74 * t))
	return s._bucle(x)


@_alta("vehiculos_hormigonera", bucle=True, pico=0.35)
def _hormigonera(rng: np.random.Generator) -> np.ndarray:
	"""Camión hormigonera: la cuba gira despacio y la grava rueda dentro, sobre el motor."""
	d = 4.25
	t = s._t(d)
	x = 0.7 * _diesel(rng, d, 40, 12)
	x += 0.8 * s._filtro(s._ruido(rng, d), 300, 3500) * (0.5 + 0.5 * np.sin(PI2 * 0.5 * t) ** 2)
	x = s._bucle(x)
	for _k in range(26):
		s._poner_ciclico(x, s._clac(rng, 0.03, 1500, 9000), float(rng.uniform(0.0, 3.9)), float(rng.uniform(0.3, 0.9)))
	return x


@_alta("vehiculos_puerta_coche")
def _puerta_coche(rng: np.random.Generator) -> np.ndarray:
	"""Puerta de coche que se cierra: el pestillo y un golpe sordo y lleno de chapa y goma."""
	x = np.zeros(s._muestras(0.5))
	s._poner(x, s._clac(rng, 0.03, 1800, 9000), 0.0, 0.6)
	s._poner(x, s._toc(rng, 85, 0.3, 1300), 0.05, 1.0)
	s._poner(x, s._filtro(s._ruido(rng, 0.2), 200, 2500) * s._decae(0.2, 0.05, 0.002), 0.05, 0.6)
	s._poner(x, s._aire(rng, 0.06, 0.4, 0.012), 0.05)
	return x


@_alta("vehiculos_cadena", pico=0.5)
def _cadena(rng: np.random.Generator) -> np.ndarray:
	"""Cadena o cepo de hierro que se sacude: eslabones que chocan y tintinean."""
	x = np.zeros(s._muestras(0.9))
	for k in range(9):
		inicio = 0.07 * k + float(rng.uniform(0.0, 0.03))
		f = float(rng.uniform(2200, 5200))
		s._poner(x, s._nota(f, 0.12, 0.03, (1, 0.5, 0.3)), inicio, float(rng.uniform(0.4, 0.9)) * (1.0 - 0.08 * k))
		s._poner(x, s._clac(rng, 0.02, 2500, 11000), inicio, 0.6 * (1.0 - 0.08 * k))
	return x


@_alta("vehiculos_plataforma_hidraulica", pico=0.5)
def _plataforma_hidraulica(rng: np.random.Generator) -> np.ndarray:
	"""Plataforma elevadora de un camión: la bomba hidráulica zumba mientras baja o sube y la chapa hace tope."""
	d = 2.2
	x = np.zeros(s._muestras(d + 0.3))
	bomba = (s._barrido(165, 150, d, "sierra") * 0.6 + s._barrido(330, 300, d) * 0.4) * s._arco(d, 0.3)
	s._poner(x, s._filtro(bomba, 120, 5000), 0.0, 0.7)
	s._poner(x, s._siseo(rng, d, 3200, 9000) * s._arco(d, 0.5), 0.0, 0.3)
	s._poner(x, s._toc(rng, 120, 0.25, 2500), d - 0.05, 1.0)
	s._poner(x, s._clac(rng, 0.04, 1500, 9000), d - 0.05, 0.8)
	return x


@_alta("vehiculos_compresor_aire", bucle=True, pico=0.35)
def _compresor_aire(rng: np.random.Generator) -> np.ndarray:
	"""Compresor de aire para hinchar ruedas: un petardeo rápido de pistón y el aire que silba por la manguera."""
	d = 3.0
	t = s._t(d)
	x = _motor(rng, d, 48, 100, 1200, siseo=0.15) * (0.55 + 0.45 * np.sign(np.sin(PI2 * 16 * t)))
	x += 0.45 * s._filtro(s._ruido(rng, d), 4000, 11000)
	return s._bucle(x)


@_alta("aparcamiento_barrera")
def _barrera(rng: np.random.Generator) -> np.ndarray:
	"""Barrera de aparcamiento: el motor del brazo zumba un segundo largo y el brazo hace tope con un clac."""
	d = 1.5
	x = np.zeros(s._muestras(d + 0.3))
	motor = (s._barrido(190, 230, d, "sierra") * 0.6 + s._barrido(760, 920, d) * 0.25) * s._arco(d, 0.25)
	s._poner(x, s._filtro(motor, 150, 6000), 0.0, 0.7)
	s._poner(x, s._siseo(rng, d, 3000, 9000) * s._arco(d, 0.5), 0.0, 0.25)
	s._poner(x, s._clac(rng, 0.03, 1200, 8000), 0.0, 0.6)
	s._poner(x, s._toc(rng, 160, 0.2, 2400), d, 1.0)
	s._poner(x, s._clac(rng, 0.04, 1500, 9000), d, 0.8)
	return x


@_alta("aparcamiento_tique")
def _tique(rng: np.random.Generator) -> np.ndarray:
	"""Columna de tiques: un pitido, la impresora que saca el tique con un zumbido rasposo y el corte del papel."""
	x = np.zeros(s._muestras(1.3))
	s._poner(x, _bip(1568, 0.14), 0.0)
	s._poner(x, s._aire(rng, 0.04, 0.3, 0.008), 0.0)
	d = 0.6
	impresora = s._filtro(s._ruido(rng, d), 1500, 7000) * (0.5 + 0.5 * np.sign(s._seno(70, d))) * s._arco(d, 0.3)
	s._poner(x, impresora, 0.3, 0.6)
	s._poner(x, s._clac(rng, 0.04, 2000, 10000), 0.95, 0.9)
	s._poner(x, _bip(2093, 0.1), 1.05, 0.7)
	return x


@_alta("aparcamiento_avisador_salida", bucle=True, pico=0.4)
def _avisador_salida(rng: np.random.Generator) -> np.ndarray:
	"""Avisador de salida de vehículos de un garaje: dos pitidos agudos que se repiten mientras sale un coche."""
	x = s._bucle(0.03 * s._siseo(rng, 1.45, 3000, 9000))
	for inicio in (0.05, 0.35):
		s._poner_ciclico(x, _bip(2400, 0.2), inicio)
		s._poner_ciclico(x, s._aire(rng, 0.04, 0.3, 0.008), inicio)
	return x


@_alta("aparcamiento_tunel_lavado", bucle=True, pico=0.4)
def _tunel_lavado(rng: np.random.Generator) -> np.ndarray:
	"""Túnel de lavado en marcha: agua a presión, los rodillos que giran y golpean la chapa y el motor del pórtico."""
	d = 4.5
	t = s._t(d)
	x = _agua(rng, d, 700, 9000, 24)
	x += 0.5 * _motor(rng, d, 55, 120, 900, vaiven=0.5, siseo=0.1)
	x += 0.5 * s._filtro(s._ruido(rng, d), 200, 1500) * (0.5 + 0.5 * np.sin(PI2 * 3.0 * t) ** 4)
	return s._bucle(x)
