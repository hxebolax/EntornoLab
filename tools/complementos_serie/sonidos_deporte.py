"""Sonidos propios del complemento «deporte», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Máquinas de gimnasio en marcha, hierros de la sala de pesas, el saco de
boxeo, la bocina del marcador, el agua de la piscina y los aparatos de aire
del vestuario.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _motor


def _hierro(rng: np.random.Generator, f: float, d: float = 0.45) -> np.ndarray:
	"""Un golpe de hierro contra hierro: campana corta y áspera con su chasquido."""
	x = s._campana(f, d, (1, 2.32, 3.9, 5.7, 8.1), (1, 0.8, 0.6, 0.45, 0.3))
	s._poner(x, s._clac(rng, 0.04, 1500, 10000), 0.0, 0.6)
	return x


@_alta("cinta_correr_marcha", bucle=True, pico=0.35)
def _cinta_correr_marcha(rng: np.random.Generator) -> np.ndarray:
	"""Cinta de correr en marcha: el motor, la banda que roza y las zancadas de quien corre."""
	d = 3.0
	x = _motor(rng, d, 78, 200, 1600, siseo=0.35)
	x += 0.35 * s._filtro(s._ruido(rng, d), 1500, 6000)
	x = s._bucle(x)
	duracion = len(x) / s.FRECUENCIA
	for k in range(8):
		inicio = k * duracion / 8
		s._poner_ciclico(x, s._toc(rng, 95, 0.12, 1800), inicio, 1.1)
		s._poner_ciclico(x, s._aire(rng, 0.05, 0.5, 0.01), inicio, 1.0)
	return x


@_alta("bici_volante_giro", bucle=True, pico=0.3)
def _bici_volante_giro(rng: np.random.Generator) -> np.ndarray:
	"""Bicicleta estática o elíptica: el volante gira con un silbido que sube y baja a cada pedalada."""
	d = 3.0
	t = s._t(d)
	pedalada = 0.5 + 0.5 * np.sin(PI2 * (4 / d) * t) ** 2
	x = s._filtro(s._ruido(rng, d), 700, 5000) * pedalada
	x += 0.25 * np.sin(PI2 * 210 * t) * pedalada
	x += 0.3 * s._siseo(rng, d, 3500, 9500) * pedalada
	# El tic de la biela en cada vuelta.
	for k in range(4):
		s._poner(x, s._clac(rng, 0.02, 2500, 9000), 0.1 + k * d / 4, 1.2)
	return s._bucle(x, 150.0)


@_alta("remo_tiron", bucle=True, pico=0.35)
def _remo_tiron(rng: np.random.Generator) -> np.ndarray:
	"""Máquina de remo: el ventilador ruge en cada tirón y se va frenando mientras el asiento vuelve."""
	d = 4.4
	x = np.zeros(s._muestras(d))
	for k in range(2):
		inicio = k * 2.2
		tiron = s._filtro(s._ruido(rng, 1.6), 400, 7000) * s._decae(1.6, 0.5, 0.25)
		s._poner(x, tiron, inicio, 1.0)
		s._poner(x, s._barrido(160, 90, 1.6) * s._decae(1.6, 0.5, 0.25), inicio, 0.25)
		# La cadena y el carro del asiento al volver.
		vuelta = s._filtro(s._ruido(rng, 0.6), 1800, 8000) * s._arco(0.6, 1.0)
		s._poner(x, vuelta, inicio + 1.5, 0.25)
		s._poner(x, s._clac(rng, 0.03, 1500, 9000), inicio + 2.1, 0.5)
	x += 0.05 * s._siseo(rng, d, 3200, 9000)
	return s._bucle(x, 80.0)


@_alta("placas_pesas")
def _placas_pesas(rng: np.random.Generator) -> np.ndarray:
	"""Máquina de placas: el cable corre por la polea y las placas caen unas sobre otras."""
	x = np.zeros(s._muestras(1.3))
	cable = s._filtro(s._ruido(rng, 0.6), 1200, 7000) * s._arco(0.6, 0.8)
	s._poner(x, cable, 0.0, 0.3)
	s._poner(x, s._chirrido(520, 640, 0.3), 0.15, 0.08)
	for inicio, fuerza, f in ((0.7, 1.0, 310), (0.82, 0.55, 350), (0.9, 0.3, 330)):
		s._poner(x, _hierro(rng, f, 0.35), inicio, fuerza)
		s._poner(x, s._toc(rng, 120, 0.1, 1200), inicio, fuerza * 0.6)
	return x


@_alta("pesas_hierro")
def _pesas_hierro(rng: np.random.Generator) -> np.ndarray:
	"""Hierros de la sala de pesas: un disco entra en la barra y una mancuerna vuelve a su soporte."""
	x = np.zeros(s._muestras(1.4))
	for inicio, fuerza, f in ((0.0, 1.0, 620), (0.07, 0.5, 880), (0.55, 0.9, 470), (0.63, 0.45, 705), (0.72, 0.25, 500)):
		s._poner(x, _hierro(rng, f, 0.6), inicio, fuerza)
	s._poner(x, s._toc(rng, 90, 0.15, 900), 0.55, 0.6)
	return x


@_alta("saco_golpe")
def _saco_golpe(rng: np.random.Generator) -> np.ndarray:
	"""Saco de boxeo: dos puñetazos sordos contra el cuero y la cadena que tintinea al balancearse."""
	x = np.zeros(s._muestras(1.3))
	for inicio, fuerza in ((0.0, 1.0), (0.28, 0.8)):
		s._poner(x, s._toc(rng, 85, 0.22, 700), inicio, fuerza)
		s._poner(x, s._filtro(s._ruido(rng, 0.08), 800, 6000) * s._decae(0.08, 0.015, 0.001), inicio, fuerza * 0.9)
	for k in range(6):
		s._poner(
			x, s._destello(rng, float(rng.uniform(2400, 4200)), 0.08), 0.4 + 0.13 * k + float(rng.uniform(0, 0.04)), 0.35 * (1 - k / 7)
		)
	return x


@_alta("bocina_marcador", pico=0.5)
def _bocina_marcador(rng: np.random.Generator) -> np.ndarray:
	"""Bocina del marcador: un zumbido áspero y largo que señala el final del tiempo."""
	d = 1.1
	x = s._barrido(233, 233, d, "sierra") + 0.7 * s._barrido(311, 311, d, "sierra") + 0.4 * s._barrido(466, 466, d, "cuadrada")
	x = s._filtro(x, 150, 6500) * np.minimum(1.0, s._t(d) / 0.02) * np.clip((d - s._t(d)) / 0.08, 0, 1)
	x = x + 0.08 * s._siseo(rng, d, 3200, 9000) * np.clip((d - s._t(d)) / 0.08, 0, 1)
	return x


@_alta("chapuzon")
def _chapuzon(rng: np.random.Generator) -> np.ndarray:
	"""Chapuzón: alguien entra en el agua, la salpicadura cae alrededor y suben burbujas."""
	d = 1.6
	x = np.zeros(s._muestras(d))
	s._poner(x, s._toc(rng, 110, 0.2, 900), 0.0, 0.8)
	s._poner(x, s._filtro(s._ruido(rng, 1.2), 500, 9000) * s._decae(1.2, 0.3, 0.015), 0.01, 1.0)
	for _k in range(14):
		f = float(rng.uniform(500, 1800))
		s._poner(
			x, s._barrido(f, f * 1.9, 0.05) * s._decae(0.05, 0.015, 0.003), float(rng.uniform(0.25, 1.4)), float(rng.uniform(0.15, 0.4))
		)
	for _k in range(18):
		s._poner(x, s._clac(rng, 0.015, 3000, 11000), float(rng.uniform(0.15, 1.1)), float(rng.uniform(0.1, 0.35)))
	return x


@_alta("piscina_rebosadero", bucle=True, pico=0.3)
def _piscina_rebosadero(rng: np.random.Generator) -> np.ndarray:
	"""Piscina: el agua lame el borde, cae al rebosadero y gorgotea en la canaleta."""
	d = 5.0
	t = s._t(d)
	ola = 0.55 + 0.45 * np.sin(PI2 * (2 / d) * t) * np.sin(PI2 * (3 / d) * t + 0.9)
	x = s._filtro(s._ruido(rng, d), 600, 8000) * ola
	x += 0.3 * s._filtro(s._ruido(rng, d), 150, 500)
	x = s._bucle(x)
	duracion = len(x) / s.FRECUENCIA
	for _k in range(26):
		f = float(rng.uniform(350, 1500))
		gota = s._barrido(f, f * 1.7, 0.06) * s._decae(0.06, 0.018, 0.004)
		s._poner_ciclico(x, gota, float(rng.uniform(0, duracion)), float(rng.uniform(0.3, 0.8)))
	for _k in range(20):
		s._poner_ciclico(x, s._clac(rng, 0.012, 3500, 11000), float(rng.uniform(0, duracion)), float(rng.uniform(0.2, 0.5)))
	return x


@_alta("jacuzzi_burbujas", bucle=True, pico=0.35)
def _jacuzzi_burbujas(rng: np.random.Generator) -> np.ndarray:
	"""Bañera de hidromasaje: la bomba zumba y el agua hierve de burbujas."""
	d = 4.0
	x = 0.35 * _motor(rng, d, 55, 120, 600, siseo=0.15)
	x += 0.8 * s._filtro(s._ruido(rng, d), 250, 3500)
	x += 0.35 * s._siseo(rng, d, 3500, 10000)
	x = s._bucle(x)
	duracion = len(x) / s.FRECUENCIA
	for _k in range(110):
		f = float(rng.uniform(250, 1300))
		burbuja = s._barrido(f, f * 1.6, 0.04) * s._decae(0.04, 0.012, 0.004)
		s._poner_ciclico(x, burbuja, float(rng.uniform(0, duracion)), float(rng.uniform(0.3, 0.9)))
	return x


@_alta("secador_pared_aire", bucle=True, pico=0.35)
def _secador_pared_aire(rng: np.random.Generator) -> np.ndarray:
	"""Secador de pared: un motor agudo y un chorro de aire caliente que sopla sin parar."""
	d = 2.5
	t = s._t(d)
	x = 0.4 * _motor(rng, d, 190, 400, 2500, siseo=0.2)
	x += s._filtro(s._ruido(rng, d), 1500, 10000) * (0.9 + 0.1 * np.sin(PI2 * (3 / d) * t))
	x += 0.08 * np.sin(PI2 * 2850 * t)
	return s._bucle(x)


@_alta("centrifugadora_banador")
def _centrifugadora_banador(rng: np.random.Generator) -> np.ndarray:
	"""Centrifugadora de bañadores: la tapa baja, el tambor acelera silbando, escurre el agua y se frena."""
	d = 4.2
	t = s._t(d)
	x = np.zeros(s._muestras(d))
	s._poner(x, s._clac(rng, 0.04, 900, 7000), 0.0, 0.8)
	subida = np.clip(t / 1.0, 0, 1) * np.clip((d - t) / 1.2, 0, 1)
	f = 60 + 520 * subida
	fase = PI2 * np.cumsum(f) / s.FRECUENCIA
	x += (0.5 * np.sin(fase) + 0.25 * np.sin(2 * fase) + 0.15 * np.sin(5 * fase)) * subida
	x += 0.6 * s._filtro(s._ruido(rng, d), 1200, 9000) * subida**2
	goteo = s._filtro(s._ruido(rng, d), 3000, 11000) * np.clip((t - 0.8) / 0.4, 0, 1) * np.clip((2.6 - t) / 1.0, 0, 1)
	x += 0.35 * goteo
	s._poner(x, s._toc(rng, 140, 0.12, 1400), d - 0.2, 0.5)
	return x


@_alta("vapor_bano_turco", bucle=True, pico=0.28)
def _vapor_bano_turco(rng: np.random.Generator) -> np.ndarray:
	"""Baño de vapor: la boquilla silba echando vapor y caen gotas del techo."""
	d = 5.0
	t = s._t(d)
	soplo = 0.55 + 0.45 * np.sin(PI2 * (1 / d) * t) ** 2
	x = s._filtro(s._ruido(rng, d), 2500, 12000) * soplo
	x += 0.2 * s._filtro(s._ruido(rng, d), 300, 1200) * soplo
	x = s._bucle(x)
	duracion = len(x) / s.FRECUENCIA
	for _k in range(9):
		f = float(rng.uniform(900, 2200))
		gota = s._barrido(f, f * 1.8, 0.05) * s._decae(0.05, 0.014, 0.002)
		s._poner_ciclico(x, gota, float(rng.uniform(0, duracion)), float(rng.uniform(0.5, 1.0)))
	return x
