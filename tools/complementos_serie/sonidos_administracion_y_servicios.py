"""Sonidos propios del complemento «administracion_y_servicios», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Son los que de verdad suenan en una oficina de atención, un banco, una
iglesia, una peluquería o una lavandería y sirven para orientarse: la voz
del gestor de turnos, el aviso de la pantalla, el pitido del arco detector,
la cinta del escáner, el cerrojo de la esclusa, el órgano, el secador de
casco, las máquinas de la lavandería, la lijadora del zapatero, la
guillotina, el transportador de perchas, el sello y la prensa de vapor.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _bip, _motor


def _frase(rng: np.random.Generator, silabas: tuple[tuple[float, float, tuple[float, ...]], ...], paso: float = 0.17) -> np.ndarray:
	"""Voz sin palabras: unas sílabas seguidas, cada una con su chasquido de agudos para poder situarla."""
	x = np.zeros(s._muestras(paso * len(silabas) + 0.2))
	for k, (f0, f1, formantes) in enumerate(silabas):
		s._poner(x, s._vocal(f0, f1, 0.16, formantes, 0.07), k * paso, 1.0)
		s._poner(x, s._aire(rng, 0.03, 0.25, 0.006), k * paso)
	return x


@_alta("turno_voz_admin", pico=0.5)
def _turno_voz_admin(rng: np.random.Generator) -> np.ndarray:
	"""Gestor de turnos: la tecla, sale el tique con un roce de papel y una voz dice el número."""
	x = np.zeros(s._muestras(1.9))
	s._poner(x, _bip(1320, 0.08), 0.0, 0.7)
	s._poner(x, s._filtro(s._ruido(rng, 0.35), 1800, 9000) * s._arco(0.35, 0.6) * (0.6 + 0.4 * np.sign(s._seno(70, 0.35))), 0.15, 0.6)
	voz = _frase(
		rng, ((190, 170, (700, 1200)), (180, 200, (400, 2100)), (200, 160, (500, 900)), (170, 150, (300, 2300)), (160, 130, (700, 1200)))
	)
	s._poner(x, voz, 0.65, 0.9)
	return x


@_alta("turno_dindon_admin", pico=0.5)
def _turno_dindon_admin(rng: np.random.Generator) -> np.ndarray:
	"""Pantalla de turnos: din, don, y cambia el número."""
	x = np.zeros(s._muestras(1.5))
	s._poner(x, s._campana(988, 0.9, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.0, 0.9)
	s._poner(x, s._aire(rng, 0.05, 0.5, 0.01), 0.0)
	s._poner(x, s._campana(784, 1.0, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.42, 1.0)
	s._poner(x, s._aire(rng, 0.05, 0.5, 0.01), 0.42)
	return x


@_alta("detector_metales_pitido")
def _detector_metales_pitido(rng: np.random.Generator) -> np.ndarray:
	"""Arco detector de metales: cuatro pitidos agudos y seguidos, con un zumbido debajo."""
	x = np.zeros(s._muestras(0.95))
	for k in range(4):
		s._poner(x, _bip(2750, 0.12), k * 0.19)
		s._poner(x, s._barrido(160, 160, 0.12, "cuadrada") * s._arco(0.12, 0.4), k * 0.19, 0.12)
	s._poner(x, s._aire(rng, 0.04, 0.3, 0.008), 0.0)
	return x


@_alta("escaner_bolsos_cinta", bucle=True, pico=0.3)
def _escaner_bolsos_cinta(rng: np.random.Generator) -> np.ndarray:
	"""Escáner de bolsos: la cinta rueda sin parar, los rodillos repican y las cortinillas de goma rozan."""
	d = 3.6
	x = 0.7 * _motor(rng, d, 58, 200, 1600, siseo=0.35)
	x += 0.3 * s._filtro(s._ruido(rng, d), 900, 5000) * (0.7 + 0.3 * np.sin(PI2 * 5 * s._t(d)))
	x = s._bucle(x)
	duracion = len(x) / s.FRECUENCIA
	for k in range(9):
		s._poner_ciclico(x, s._clac(rng, 0.03, 1500, 8000), k * duracion / 9, 0.5)
	s._poner_ciclico(x, s._filtro(s._ruido(rng, 0.4), 2500, 9000) * s._arco(0.4, 1.0), 1.4, 0.5)
	return x


@_alta("esclusa_cerrojo", pico=0.5)
def _esclusa_cerrojo(rng: np.random.Generator) -> np.ndarray:
	"""Puerta de esclusa de banco: zumba el cerrojo eléctrico, salta con un golpe y una voz dice que pases."""
	x = np.zeros(s._muestras(2.0))
	zumbido = s._filtro(s._barrido(118, 118, 0.6, "cuadrada"), 100, 6000) * s._arco(0.6, 0.25)
	s._poner(x, zumbido, 0.0, 0.5)
	s._poner(x, s._siseo(rng, 0.6, 3200, 9000) * s._arco(0.6, 0.25), 0.0, 0.12)
	s._poner(x, s._clac(rng, 0.05, 700, 7000), 0.6, 1.0)
	s._poner(x, s._toc(rng, 140, 0.14, 1600), 0.62, 0.8)
	voz = _frase(rng, ((200, 185, (700, 1200)), (190, 210, (450, 1900)), (180, 150, (500, 900))), 0.2)
	s._poner(x, voz, 0.95, 0.85)
	return x


@_alta("organo_iglesia", pico=0.5)
def _organo_iglesia(rng: np.random.Generator) -> np.ndarray:
	"""Órgano de iglesia: un acorde lleno que entra, se sostiene y se apaga con el eco de la nave."""
	d = 3.2
	t = s._t(d)
	x = np.zeros(s._muestras(d))
	for f, peso in ((130.81, 1.0), (196.0, 0.7), (261.63, 0.8), (329.63, 0.6), (392.0, 0.6), (523.25, 0.4)):
		for n, a in enumerate((1.0, 0.5, 0.35, 0.25, 0.18, 0.12, 0.09, 0.07)):
			x += peso * a * np.sin(PI2 * f * (n + 1) * t + 0.9 * n)
	envolvente = np.clip(t / 0.12, 0, 1) * np.where(t < 2.0, 1.0, np.exp(-(t - 2.0) / 0.35))
	x *= envolvente * (1.0 + 0.03 * np.sin(PI2 * 5.5 * t))
	# El aire de los tubos: sin él, el acorde grave no se sabría de dónde viene.
	x += 1.2 * s._siseo(rng, d, 3000, 9000) * envolvente
	return x


@_alta("secador_casco", bucle=True, pico=0.3)
def _secador_casco(rng: np.random.Generator) -> np.ndarray:
	"""Secador de casco de peluquería: un soplo de aire caliente continuo con el zumbido del motor."""
	d = 3.0
	x = 0.5 * _motor(rng, d, 100, 300, 2000, siseo=0.3)
	x += s._filtro(s._ruido(rng, d), 700, 8500)
	return s._bucle(x)


@_alta("lavadora_industrial", bucle=True, pico=0.4)
def _lavadora_industrial(rng: np.random.Generator) -> np.ndarray:
	"""Lavadora industrial: un tambor grande que voltea despacio, con mucha agua y la ropa cayendo a plomo."""
	d = 4.5
	t = s._t(d)
	x = _motor(rng, d, 46, 110, 1400, vaiven=0.9, siseo=0.3)
	x += 0.7 * s._filtro(s._ruido(rng, d), 400, 5500) * (0.4 + 0.6 * np.sin(PI2 * 0.9 * t) ** 2)
	x += 0.08 * np.sin(PI2 * 940 * t) * (0.7 + 0.3 * np.sin(PI2 * 46 * t))
	x = s._bucle(x)
	duracion = len(x) / s.FRECUENCIA
	for k in range(4):
		s._poner_ciclico(x, s._filtro(s._ruido(rng, 0.16), 70, 500) * s._decae(0.16, 0.05), 0.3 + k * duracion / 4, 1.5)
	return x


@_alta("secadora_industrial", bucle=True, pico=0.35)
def _secadora_industrial(rng: np.random.Generator) -> np.ndarray:
	"""Secadora industrial: aire caliente que sopla, el tambor que rueda y botones y cremalleras que repican en la chapa."""
	d = 4.0
	x = 0.8 * _motor(rng, d, 72, 150, 1000, vaiven=0.75, siseo=0.25)
	x += 0.8 * s._filtro(s._ruido(rng, d), 350, 5000)
	x = s._bucle(x)
	duracion = len(x) / s.FRECUENCIA
	for _k in range(11):
		inicio = rng.uniform(0, duracion)
		s._poner_ciclico(x, s._clac(rng, 0.03, 2000, 10000), inicio, rng.uniform(0.5, 1.1))
		s._poner_ciclico(x, s._seno(rng.uniform(1800, 3200), 0.04) * s._decae(0.04, 0.01, 0.001), inicio, 0.35)
	return x


@_alta("lijadora_zapatero", bucle=True, pico=0.35)
def _lijadora_zapatero(rng: np.random.Generator) -> np.ndarray:
	"""Máquina del zapatero: el motor gira deprisa y la lija muerde la suela a ratos, rasposa."""
	d = 3.5
	t = s._t(d)
	x = _motor(rng, d, 118, 400, 2600, siseo=0.3)
	x += 0.12 * np.sin(PI2 * 1650 * t)
	mordida = np.clip(np.sin(PI2 * (2 / d) * t), 0, 1) ** 0.5
	x += 1.1 * s._filtro(s._ruido(rng, d), 1800, 9000) * mordida
	return s._bucle(x)


@_alta("guillotina_papel")
def _guillotina_papel(rng: np.random.Generator) -> np.ndarray:
	"""Guillotina de copistería: la palanca baja con un quejido, la cuchilla corta el taco de papel y hace tope."""
	x = np.zeros(s._muestras(1.0))
	s._poner(x, s._chirrido(300, 190, 0.3), 0.0, 0.3)
	corte = s._filtro(s._ruido(rng, 0.22), 1500, 10000) * s._decae(0.22, 0.07, 0.01)
	s._poner(x, corte, 0.3, 1.0)
	s._poner(x, s._toc(rng, 130, 0.16, 1500), 0.5, 1.0)
	s._poner(x, s._clac(rng, 0.04, 1200, 8000), 0.5, 0.6)
	return x


@_alta("transportador_perchas", bucle=True, pico=0.3)
def _transportador_perchas(rng: np.random.Generator) -> np.ndarray:
	"""Transportador de tintorería: la cadena avanza por el carril y los ganchos de las perchas tintinean al pasar."""
	d = 4.0
	x = 0.6 * _motor(rng, d, 44, 300, 2200, siseo=0.3)
	x += 0.25 * s._filtro(s._ruido(rng, d), 1200, 6000) * (0.6 + 0.4 * np.sign(np.sin(PI2 * 12 * s._t(d))))
	x = s._bucle(x)
	duracion = len(x) / s.FRECUENCIA
	for _k in range(14):
		s._poner_ciclico(x, s._destello(rng, rng.uniform(2600, 5200), 0.1), rng.uniform(0, duracion), rng.uniform(0.3, 0.8))
	return x


@_alta("sello_tampon")
def _sello_tampon(rng: np.random.Generator) -> np.ndarray:
	"""Sello de registro: un toque blando en el tampón de tinta y el golpe seco sobre el papel."""
	x = np.zeros(s._muestras(0.6))
	s._poner(x, s._toc(rng, 200, 0.09, 1200), 0.0, 0.45)
	s._poner(x, s._toc(rng, 150, 0.16, 1900), 0.28, 1.0)
	s._poner(x, s._aire(rng, 0.06, 0.8, 0.012), 0.28)
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.34, 0.4)
	return x


@_alta("plancha_vapor", pico=0.5)
def _plancha_vapor(rng: np.random.Generator) -> np.ndarray:
	"""Prensa de planchar: el plato baja con un golpe sordo y suelta un bufido largo de vapor."""
	x = np.zeros(s._muestras(1.9))
	s._poner(x, s._toc(rng, 110, 0.18, 1300), 0.0, 0.9)
	s._poner(x, s._clac(rng, 0.04, 900, 7000), 0.02, 0.5)
	vapor = s._filtro(s._ruido(rng, 1.6), 2500, 11000) * s._decae(1.6, 0.5, 0.06)
	s._poner(x, vapor, 0.15, 1.0)
	s._poner(x, s._filtro(s._ruido(rng, 1.2), 400, 1800) * s._decae(1.2, 0.3, 0.05), 0.15, 0.3)
	return x
