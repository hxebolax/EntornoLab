"""Sonidos propios del complemento «comunidad_y_edificio», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Son los sonidos con los que se reconoce un edificio de viviendas: el portero
automático y el zumbido del abrepuertas, la puerta pesada que cierra sola, la
puerta del garaje y su aviso, y las máquinas que zumban en los cuartos de
instalaciones, en la azotea y junto a la piscina.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _agua, _alta, _bip, _motor


@_alta("portero_automatico", pico=0.5)
def _portero_automatico(rng: np.random.Generator) -> np.ndarray:
	"""Portero automático: el botón y dos timbrazos eléctricos que suenan arriba, en el piso."""
	x = np.zeros(s._muestras(1.5))
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0, 0.7)
	for inicio in (0.08, 0.75):
		d = 0.5
		t = s._t(d)
		timbre = np.sign(np.sin(PI2 * 460 * t)) * (0.6 + 0.4 * np.sign(np.sin(PI2 * 52 * t)))
		s._poner(x, s._filtro(timbre, 350, 7500) * s._arco(d, 0.25), inicio, 0.7)
	return x


@_alta("abrepuertas_zumbido", pico=0.5)
def _abrepuertas_zumbido(rng: np.random.Generator) -> np.ndarray:
	"""Abrepuertas eléctrico: un zumbido áspero de un segundo y el pestillo que salta."""
	d = 1.1
	t = s._t(d)
	x = np.zeros(s._muestras(d + 0.25))
	zumbido = np.sign(np.sin(PI2 * 100 * t)) + 0.5 * np.sign(np.sin(PI2 * 200 * t + 0.6))
	s._poner(x, s._filtro(zumbido, 180, 8000) * np.clip(t / 0.02, 0, 1) * np.clip((d - t) / 0.03, 0, 1), 0.0, 0.6)
	s._poner(x, s._clac(rng, 0.04, 900, 8000), d + 0.02, 1.0)
	s._poner(x, s._seno(310, 0.12) * s._decae(0.12, 0.03), d + 0.02, 0.5)
	return x


@_alta("puerta_pesada_muelle")
def _puerta_pesada_muelle(rng: np.random.Generator) -> np.ndarray:
	"""Puerta pesada con muelle: el brazo sisea mientras cierra y la hoja da un portazo de hierro y cristal."""
	x = np.zeros(s._muestras(1.9))
	s._poner(x, s._filtro(s._ruido(rng, 1.1), 2500, 9000) * s._arco(1.1, 0.6), 0.0, 0.3)
	s._poner(x, s._chirrido(300, 180, 0.6), 0.45, 0.25)
	s._poner(x, s._filtro(s._ruido(rng, 0.35), 50, 700) * s._decae(0.35, 0.09), 1.12, 1.0)
	s._poner(x, s._seno(72, 0.4) * s._decae(0.4, 0.11), 1.12, 0.9)
	for parcial, peso in ((410, 0.5), (1130, 0.35), (2870, 0.25), (4600, 0.15)):
		s._poner(x, s._seno(parcial, 0.5) * s._decae(0.5, 0.09, 0.002), 1.13, 0.4 * peso)
	s._poner(x, s._clac(rng, 0.05, 1200, 9000), 1.13, 0.9)
	s._poner(x, s._clac(rng, 0.03, 2000, 9000), 1.3, 0.4)
	return x


@_alta("puerta_garaje_basculante", pico=0.5)
def _puerta_garaje_basculante(rng: np.random.Generator) -> np.ndarray:
	"""Puerta de garaje: arranca el motor, la chapa sube traqueteando por las guías y hace tope."""
	d = 4.2
	t = s._t(d)
	x = np.zeros(s._muestras(d + 0.5))
	s._poner(x, s._clac(rng, 0.05, 700, 6000), 0.0, 0.8)
	motor = _motor(rng, d, 88, 200, 1800, vaiven=2.2, siseo=0.25) * np.clip(t / 0.3, 0, 1) * np.clip((d - t) / 0.25, 0, 1)
	s._poner(x, motor, 0.05, 0.7)
	for k in range(26):
		inicio = 0.3 + k * 0.145 + rng.uniform(-0.02, 0.02)
		s._poner(x, s._clac(rng, 0.04, 900, 7000), inicio, rng.uniform(0.25, 0.5))
		s._poner(x, s._seno(rng.uniform(260, 420), 0.09) * s._decae(0.09, 0.02), inicio, 0.2)
	s._poner(x, s._chirrido(520, 380, 0.7), 1.6, 0.18)
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 60, 900) * s._decae(0.3, 0.08), d + 0.08, 1.0)
	for parcial, peso in ((150, 1.0), (390, 0.6), (1040, 0.4), (2500, 0.25)):
		s._poner(x, s._seno(parcial, 0.4) * s._decae(0.4, 0.1, 0.002), d + 0.08, 0.35 * peso)
	s._poner(x, s._clac(rng, 0.05, 1200, 9000), d + 0.08, 0.8)
	return x


@_alta("aviso_garaje_pitido", bucle=True, pico=0.4)
def _aviso_garaje_pitido(rng: np.random.Generator) -> np.ndarray:
	"""Aviso de salida de vehículos: un pitido agudo que se repite dos veces por segundo."""
	d = 2.0
	x = 0.02 * s._siseo(rng, d, 3200, 9000)
	x = s._bucle(x, 100.0)
	total = len(x) / s.FRECUENCIA
	for k in range(4):
		s._poner_ciclico(x, _bip(2350, 0.2), 0.05 + k * total / 4, 1.0)
	return x


@_alta("caldera_comunitaria", bucle=True, pico=0.4)
def _caldera_comunitaria(rng: np.random.Generator) -> np.ndarray:
	"""Caldera comunitaria: el rugido grave del quemador, el soplido de la llama y las bombas que zumban."""
	d = 4.0
	t = s._t(d)
	x = 0.8 * s._filtro(s._ruido(rng, d), 40, 420) * (0.85 + 0.15 * np.sin(PI2 * 0.5 * t))
	x += 0.35 * _motor(rng, d, 48, 120, 900, siseo=0.15)
	x += 0.3 * s._filtro(s._ruido(rng, d), 1500, 7000) * (0.8 + 0.2 * np.sin(PI2 * 7.0 * t))
	x += 0.22 * s._siseo(rng, d, 3200, 9000)
	x = s._bucle(x)
	for inicio in (0.9, 2.7):
		s._poner_ciclico(x, s._clac(rng, 0.04, 1500, 9000), inicio, 0.25)
	return x


@_alta("grupo_presion", bucle=True, pico=0.35)
def _grupo_presion(rng: np.random.Generator) -> np.ndarray:
	"""Grupo de presión: el zumbido tenso de la bomba con el agua silbando por la tubería."""
	d = 3.0
	t = s._t(d)
	x = _motor(rng, d, 146, 300, 2400, vaiven=1.0, siseo=0.3)
	x += 0.18 * np.sin(PI2 * 2920 * t) * (0.7 + 0.3 * np.sin(PI2 * 2.0 * t))
	x += 0.3 * s._filtro(s._ruido(rng, d), 2500, 8000)
	return s._bucle(x)


@_alta("extractor_garaje", bucle=True, pico=0.4)
def _extractor_garaje(rng: np.random.Generator) -> np.ndarray:
	"""Extractor de garaje: un ventilador grande que ruge, con la chapa de la caja vibrando."""
	d = 4.0
	t = s._t(d)
	x = s._filtro(s._ruido(rng, d), 90, 1600) * (0.8 + 0.2 * np.sin(PI2 * 11.0 * t))
	x += 0.4 * _motor(rng, d, 73, 150, 900, vaiven=0.5, siseo=0.2)
	x += 0.12 * np.sin(PI2 * 365 * t) * (0.6 + 0.4 * np.sin(PI2 * 5.5 * t))
	x += 0.35 * s._siseo(rng, d, 3000, 8500)
	return s._bucle(x)


@_alta("compresor_azotea", bucle=True, pico=0.35)
def _compresor_azotea(rng: np.random.Generator) -> np.ndarray:
	"""Unidad exterior de aire acondicionado: el compresor ronronea y el ventilador sopla, con una rejilla que tiembla."""
	d = 3.5
	t = s._t(d)
	x = _motor(rng, d, 55, 140, 700, vaiven=1.0, siseo=0.1)
	x += 0.7 * s._filtro(s._ruido(rng, d), 400, 5500) * (0.85 + 0.15 * np.sin(PI2 * 17.0 * t))
	x += 0.3 * s._siseo(rng, d, 3200, 9500)
	x = s._bucle(x)
	for k in range(7):
		s._poner_ciclico(x, s._clac(rng, 0.02, 2500, 9000), 0.2 + k * 0.45, 0.12)
	return x


@_alta("depuradora_piscina", bucle=True, pico=0.35)
def _depuradora_piscina(rng: np.random.Generator) -> np.ndarray:
	"""Depuradora de piscina: la bomba zumba dentro de su caseta y el agua borbotea al volver al vaso."""
	d = 4.0
	x = 0.8 * _motor(rng, d, 98, 220, 1500, vaiven=0.25, siseo=0.2)
	x += 0.55 * _agua(rng, d, 700, 6500, 26)
	return s._bucle(x)


@_alta("bajante_desague", bucle=True, pico=0.3)
def _bajante_desague(rng: np.random.Generator) -> np.ndarray:
	"""Bajante: de vez en cuando cae agua por dentro del tubo, hueca, y luego gotea."""
	d = 5.5
	x = 0.03 * s._siseo(rng, d, 3200, 8000)
	x = s._bucle(x, 150.0)
	caida = _agua(rng, 2.2, 350, 5000, 14) * s._arco(2.2, 0.7)
	hueco = s._filtro(s._ruido(rng, 2.2), 180, 520) * s._arco(2.2, 0.9)
	s._poner_ciclico(x, caida + 0.8 * hueco, 0.6, 1.0)
	for inicio in (3.1, 3.6, 4.3, 4.8):
		s._poner_ciclico(x, s._barrido(1500, 2600, 0.04) * s._decae(0.04, 0.01, 0.002), inicio, 0.35)
		s._poner_ciclico(x, s._clac(rng, 0.02, 3000, 9000), inicio, 0.2)
	return x


@_alta("polea_tendedero", pico=0.5)
def _polea_tendedero(rng: np.random.Generator) -> np.ndarray:
	"""Cuerda de tender con polea: tres tirones, y a cada tirón la polea chirría."""
	x = np.zeros(s._muestras(1.6))
	for k, (inicio, f0, f1) in enumerate(((0.0, 1500, 2100), (0.5, 1650, 2300), (1.0, 1450, 2000))):
		s._poner(x, s._chirrido(f0, f1, 0.32), inicio, 0.6)
		s._poner(x, s._filtro(s._ruido(rng, 0.3), 2500, 9000) * s._arco(0.3, 1.0), inicio, 0.25)
		s._poner(x, s._clac(rng, 0.03, 1500, 8000), inicio + 0.33, 0.4 + 0.1 * k)
	return x


@_alta("petanca_bolas", pico=0.5)
def _petanca_bolas(rng: np.random.Generator) -> np.ndarray:
	"""Petanca: la bola cae en la gravilla, rueda y choca con otra con un golpe de acero."""
	x = np.zeros(s._muestras(1.7))
	s._poner(x, s._filtro(s._ruido(rng, 0.12), 150, 3500) * s._decae(0.12, 0.03), 0.0, 0.9)
	s._poner(x, s._seno(120, 0.1) * s._decae(0.1, 0.025), 0.0, 0.6)
	d = 0.8
	rodar = s._filtro(s._ruido(rng, d), 900, 7500) * s._arco(d, 0.5) * (0.6 + 0.4 * np.abs(s._seno(21, d)))
	s._poner(x, rodar, 0.1, 0.45)
	for parcial, peso in ((2950, 1.0), (4400, 0.6), (6800, 0.35)):
		s._poner(x, s._seno(parcial, 0.5) * s._decae(0.5, 0.07, 0.0005), 0.92, 0.5 * peso)
	s._poner(x, s._clac(rng, 0.02, 2500, 12000), 0.92, 1.0)
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 900, 7000) * s._decae(0.3, 0.1, 0.01), 0.98, 0.25)
	return x


@_alta("barbacoa_brasas", bucle=True, pico=0.35)
def _barbacoa_brasas(rng: np.random.Generator) -> np.ndarray:
	"""Barbacoa encendida: las brasas crepitan y la grasa chisporrotea sobre el fuego."""
	d = 4.0
	t = s._t(d)
	x = 0.35 * s._filtro(s._ruido(rng, d), 150, 1200) * (0.8 + 0.2 * np.sin(PI2 * 0.75 * t))
	x += 0.3 * s._filtro(s._ruido(rng, d), 3500, 11000) * (0.6 + 0.4 * np.sin(PI2 * 0.5 * t) ** 2)
	x = s._bucle(x)
	for _k in range(70):
		largo = float(rng.uniform(0.006, 0.03))
		s._poner_ciclico(
			x, s._clac(rng, largo, float(rng.uniform(1200, 4000)), 12000), float(rng.uniform(0, d - 0.3)), float(rng.uniform(0.3, 1.0))
		)
	return x
