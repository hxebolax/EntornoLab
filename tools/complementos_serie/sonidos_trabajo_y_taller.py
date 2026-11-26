"""Sonidos propios del complemento «trabajo_y_taller», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Son las máquinas que en un taller, un almacén, una fábrica, un laboratorio,
una cocina profesional o una obra se oyen desde lejos y sirven para situarse:
el compresor, la sierra, el esmeril, la soldadura, la cinta, el pitido de la
carretilla, la prensa, el telar, la freidora, la hormigonera, la centrífuga…
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _bip, _motor


def _modulacion(rng: np.random.Generator, d: float, lo: float, hi: float) -> np.ndarray:
	"""Envolvente irregular entre 0 y 1: ruido lento rectificado, para que un roce o un chisporroteo no suene plano."""
	onda = np.abs(s._filtro(s._ruido(rng, d), lo, hi))
	return onda / (float(np.max(onda)) or 1.0)


@_alta("compresor_aire", bucle=True, pico=0.35)
def _compresor_aire(rng: np.random.Generator) -> np.ndarray:
	"""Compresor de aire de taller: el motor grave y el pistón que golpetea deprisa."""
	d = 3.0
	t = s._t(d)
	x = _motor(rng, d, 48, 100, 900, siseo=0.35)
	x *= 0.55 + 0.45 * np.abs(np.sin(PI2 * 6.0 * t))
	x += 0.2 * s._filtro(s._ruido(rng, d), 1500, 6000) * np.abs(np.sin(PI2 * 6.0 * t)) ** 4
	return s._bucle(x)


@_alta("sierra_circular", bucle=True, pico=0.35)
def _sierra_circular(rng: np.random.Generator) -> np.ndarray:
	"""Sierra de carpintería en marcha: un aullido agudo y tenso con el aire que corta el disco."""
	d = 3.0
	t = s._t(d)
	fase = PI2 * 310 * t + 2.0 * np.sin(PI2 * (2 / d) * t)
	x = 0.4 * np.sin(fase) + 0.3 * np.sin(2 * fase) + 0.25 * np.sin(3 * fase) + 0.2 * np.sin(5 * fase) + 0.12 * np.sin(9 * fase)
	x += 0.7 * s._filtro(s._ruido(rng, d), 1800, 10000)
	return s._bucle(x)


@_alta("esmeril_chispas", bucle=True, pico=0.35)
def _esmeril_chispas(rng: np.random.Generator) -> np.ndarray:
	"""Esmeril o lijadora: la muela zumba y el metal raspa con ráfagas de chispas."""
	d = 3.0
	x = 0.6 * _motor(rng, d, 95, 250, 1500, siseo=0.2)
	x += 0.9 * s._filtro(s._ruido(rng, d), 2500, 11000) * (0.35 + 0.65 * _modulacion(rng, d, 1, 6))
	x = s._bucle(x)
	for _k in range(40):
		s._poner_ciclico(
			x, s._filtro(s._ruido(rng, 0.01), 4000, 12000) * s._decae(0.01, 0.003, 0.0004), rng.uniform(0, d - 0.3), rng.uniform(0.3, 0.8)
		)
	return x


@_alta("soldadura_arco", bucle=True, pico=0.35)
def _soldadura_arco(rng: np.random.Generator) -> np.ndarray:
	"""Soldadura eléctrica: el arco zumba y crepita como una fritura seca y fuerte."""
	d = 3.0
	t = s._t(d)
	zumbido = 0.35 * np.sin(PI2 * 100 * t) + 0.25 * np.sin(PI2 * 200 * t + 0.6) + 0.2 * np.sin(PI2 * 300 * t + 1.1)
	crepitar = s._filtro(s._ruido(rng, d), 1500, 10000) * _modulacion(rng, d, 20, 120) ** 2
	x = (zumbido + 1.6 * crepitar) * (0.7 + 0.3 * _modulacion(rng, d, 0.5, 3))
	return s._bucle(x)


@_alta("martillo_yunque")
def _martillo_yunque(rng: np.random.Generator) -> np.ndarray:
	"""Martillo en el yunque: un golpe que canta, el rebote corto y otro golpe."""
	x = np.zeros(s._muestras(1.3))
	for inicio, fuerza in ((0.0, 1.0), (0.13, 0.35), (0.42, 0.9), (0.55, 0.3)):
		tañido = sum(a * s._seno(f, 0.7) for f, a in ((1100, 1.0), (2530, 0.7), (4170, 0.5), (6300, 0.3))) * s._decae(0.7, 0.16, 0.001)
		s._poner(x, tañido, inicio, fuerza)
		s._poner(x, s._clac(rng, 0.03, 1500, 10000), inicio, fuerza)
	return x


@_alta("cinta_banda_almacen", bucle=True, pico=0.3)
def _cinta_banda_almacen(rng: np.random.Generator) -> np.ndarray:
	"""Cinta transportadora de banda: zumbido del motor, la goma que rueda y el empalme que pasa cada segundo."""
	d = 4.0
	t = s._t(d)
	x = 0.6 * _motor(rng, d, 55, 120, 800, siseo=0.3)
	x += 0.5 * s._filtro(s._ruido(rng, d), 200, 2500) * (0.75 + 0.25 * np.sin(PI2 * 4.0 * t))
	x = s._bucle(x)
	for k in range(4):
		s._poner_ciclico(x, s._clac(rng, 0.04, 900, 7000), 0.3 + k, 1.4)
	return x


@_alta("pitido_carretilla", bucle=True, pico=0.3)
def _pitido_carretilla(rng: np.random.Generator) -> np.ndarray:
	"""Carretilla o transpaleta eléctrica en marcha: pitido de aviso, pi… pi…, sobre el zumbido del motor."""
	d = 2.0
	x = 0.12 * _motor(rng, d, 80, 150, 900, siseo=0.3)
	x = s._bucle(x)
	for inicio in (0.4, 1.4):
		s._poner_ciclico(x, _bip(1250, 0.35) + 0.4 * _bip(3750, 0.35), inicio, 1.0)
		s._poner_ciclico(x, s._aire(rng, 0.05, 0.4, 0.01), inicio, 1.0)
	return x


@_alta("prensa_industrial", bucle=True, pico=0.4)
def _prensa_industrial(rng: np.random.Generator) -> np.ndarray:
	"""Prensa o máquina de ciclo: zumbido hidráulico, un golpe sordo y el escape de aire, una y otra vez."""
	d = 3.0
	x = s._bucle(0.3 * _motor(rng, d, 70, 150, 1000, siseo=0.3))
	for inicio in (0.5, 2.0):
		s._poner_ciclico(x, s._toc(rng, 60, 0.25, 1200), inicio, 1.6)
		s._poner_ciclico(x, s._filtro(s._ruido(rng, 0.3), 80, 800) * s._decae(0.3, 0.07), inicio, 1.2)
		s._poner_ciclico(x, s._filtro(s._ruido(rng, 0.4), 3000, 10000) * s._decae(0.4, 0.1, 0.01), inicio + 0.3, 0.8)
	return x


@_alta("telar_industrial", bucle=True, pico=0.35)
def _telar_industrial(rng: np.random.Generator) -> np.ndarray:
	"""Telar industrial: un clac, clac, clac muy rápido y parejo sobre el motor."""
	d = 2.4
	x = s._bucle(0.25 * _motor(rng, d, 60, 200, 1500, siseo=0.3))
	for k in range(12):
		fuerza = 1.2 if k % 2 == 0 else 0.8
		s._poner_ciclico(x, s._clac(rng, 0.04, 600, 8000), 0.1 + k * 0.2, fuerza)
		s._poner_ciclico(x, s._seno(220 if k % 2 == 0 else 180, 0.06) * s._decae(0.06, 0.015), 0.1 + k * 0.2, 0.6 * fuerza)
	return x


@_alta("zumbador_alarma", bucle=True, pico=0.3)
def _zumbador_alarma(rng: np.random.Generator) -> np.ndarray:
	"""Zumbador de un armario de control: pitidos agudos y secos, cuatro por cada vuelta de la baliza."""
	d = 1.6
	x = s._bucle(0.03 * s._siseo(rng, d, 3200, 9000))
	for k in range(4):
		s._poner_ciclico(x, _bip(2800, 0.2) * (0.7 + 0.3 * np.sign(s._seno(70, 0.2))), 0.1 + 0.4 * k, 1.0)
	return x


@_alta("freidora_aceite", bucle=True, pico=0.3)
def _freidora_aceite(rng: np.random.Generator) -> np.ndarray:
	"""Freidora o plancha: el aceite chisporrotea, con burbujas y pequeños estallidos."""
	d = 3.0
	x = s._filtro(s._ruido(rng, d), 3000, 12000) * (0.5 + 0.5 * _modulacion(rng, d, 2, 12))
	x += 0.25 * s._filtro(s._ruido(rng, d), 300, 900) * _modulacion(rng, d, 4, 20)
	x = s._bucle(x)
	for _k in range(50):
		s._poner_ciclico(
			x, s._filtro(s._ruido(rng, 0.012), 1500, 8000) * s._decae(0.012, 0.004, 0.0004), rng.uniform(0, d - 0.3), rng.uniform(0.5, 1.3)
		)
	return x


@_alta("hormigonera_obra", bucle=True, pico=0.4)
def _hormigonera_obra(rng: np.random.Generator) -> np.ndarray:
	"""Hormigonera: el motor ronca y la grava cae dentro del bombo a cada vuelta."""
	d = 4.0
	t = s._t(d)
	x = _motor(rng, d, 45, 100, 800, vaiven=0.5, siseo=0.25)
	x += 0.7 * s._filtro(s._ruido(rng, d), 400, 5000) * (0.3 + 0.7 * np.sin(PI2 * 0.75 * t) ** 2)
	x = s._bucle(x)
	for _k in range(14):
		inicio = rng.uniform(0, d - 0.3)
		s._poner_ciclico(x, s._toc(rng, rng.uniform(140, 320), 0.07, 2500), inicio, rng.uniform(0.5, 1.1))
		s._poner_ciclico(x, s._clac(rng, 0.03, 1500, 9000), inicio, 0.5)
	return x


@_alta("centrifuga_laboratorio", bucle=True, pico=0.3)
def _centrifuga_laboratorio(rng: np.random.Generator) -> np.ndarray:
	"""Centrífuga girando: un silbido agudo y constante, con el aire que arrastra el rotor."""
	d = 3.0
	t = s._t(d)
	fase = PI2 * 520 * t + 1.5 * np.sin(PI2 * (3 / d) * t)
	x = 0.5 * np.sin(fase) + 0.3 * np.sin(2 * fase) + 0.2 * np.sin(4 * fase) + 0.15 * np.sin(8 * fase)
	x += 0.5 * s._filtro(s._ruido(rng, d), 1500, 8000)
	return s._bucle(x)


@_alta("enfardadora_film", bucle=True, pico=0.3)
def _enfardadora_film(rng: np.random.Generator) -> np.ndarray:
	"""Enfardadora de palés: el plato gira con un zumbido grave y el film chirría al estirarse a cada vuelta."""
	d = 4.0
	t = s._t(d)
	x = 0.5 * _motor(rng, d, 65, 120, 900, vaiven=0.3, siseo=0.2)
	estirar = np.clip(np.sin(PI2 * 0.5 * t), 0, 1) ** 2
	fase = PI2 * (900 + 250 * np.sin(PI2 * 0.5 * t)) * t
	x += 0.35 * (np.sin(fase) + 0.4 * np.sin(2.1 * fase)) * estirar * (0.6 + 0.4 * _modulacion(rng, d, 8, 40))
	x += 0.25 * s._filtro(s._ruido(rng, d), 2500, 9000) * estirar
	return s._bucle(x)


@_alta("fuegos_gas_cocina", bucle=True, pico=0.3)
def _fuegos_gas_cocina(rng: np.random.Generator) -> np.ndarray:
	"""Fuegos de gas de una cocina industrial: un rugido sordo y continuo de la llama, con algún chasquido del hierro."""
	d = 3.0
	x = s._filtro(s._ruido(rng, d), 60, 450) * (0.75 + 0.25 * _modulacion(rng, d, 0.5, 4))
	x += 0.3 * s._filtro(s._ruido(rng, d), 600, 2500) * (0.6 + 0.4 * _modulacion(rng, d, 2, 10))
	x = s._bucle(x)
	for _k in range(5):
		s._poner_ciclico(x, s._clac(rng, 0.02, 1500, 7000), rng.uniform(0, d - 0.1), rng.uniform(0.2, 0.5))
	return x


@_alta("marmita_borboteo", bucle=True, pico=0.3)
def _marmita_borboteo(rng: np.random.Generator) -> np.ndarray:
	"""Marmita hirviendo: burbujas gordas y graves que revientan, sobre el siseo del vapor."""
	d = 3.0
	x = s._bucle(0.25 * s._filtro(s._ruido(rng, d), 2000, 8000) * (0.5 + 0.5 * _modulacion(rng, d, 1, 5)))
	for _k in range(30):
		f = rng.uniform(120, 320)
		burbuja = s._seno(f, 0.08) * s._decae(0.08, 0.02, 0.001)
		s._poner_ciclico(x, burbuja, rng.uniform(0, d - 0.1), rng.uniform(0.4, 1.0))
	return x


@_alta("amasadora_espiral", bucle=True, pico=0.35)
def _amasadora_espiral(rng: np.random.Generator) -> np.ndarray:
	"""Amasadora de espiral: el motor ronca, la cuba gira y la masa da golpes sordos a cada vuelta del gancho."""
	d = 3.0
	x = s._bucle(0.6 * _motor(rng, d, 50, 100, 700, vaiven=0.2, siseo=0.15))
	for k in range(4):
		s._poner_ciclico(x, s._toc(rng, 90, 0.18, 700), 0.2 + 0.75 * k, 1.0)
		s._poner_ciclico(x, s._filtro(s._ruido(rng, 0.2), 150, 1200) * s._decae(0.2, 0.05), 0.25 + 0.75 * k, 0.6)
	return x


@_alta("puerta_seccional_muelle", pico=0.5)
def _puerta_seccional_muelle(rng: np.random.Generator) -> np.ndarray:
	"""Puerta seccional de muelle: el motor tira, los paneles traquetean por las guías y hace tope."""
	d = 2.6
	x = np.zeros(s._muestras(d))
	s._poner(x, (s._seno(110, 2.3) + 0.5 * s._seno(220, 2.3)) * s._arco(2.3, 0.4), 0.0, 0.5)
	s._poner(x, s._filtro(s._ruido(rng, 2.3), 300, 5000) * s._arco(2.3, 0.5), 0.0, 0.4)
	for k in range(8):
		inicio = 0.15 + k * 0.27
		s._poner(x, s._clac(rng, 0.04, 800, 9000), inicio, 0.9)
		s._poner(x, s._seno(700 + 40 * k, 0.15) * s._decae(0.15, 0.04, 0.001), inicio, 0.35)
	s._poner(x, s._toc(rng, 90, 0.2, 1500), 2.35, 1.2)
	return x
