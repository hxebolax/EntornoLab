"""Sonidos propios del complemento «estaciones_y_aeropuerto», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Son los que sirven para orientarse en una estación grande, un aeropuerto o un
puerto: la cinta de recogida de equipajes, el escáner del control, el arco
detector, el buggy de asistencia, las puertas de andén, la campana del paso
entre andenes, el tren parado y las amarras de un pantalán.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _bip, _motor


@_alta("cinta_equipajes", bucle=True, pico=0.35)
def _cinta_equipajes(rng: np.random.Generator) -> np.ndarray:
	"""Cinta de recogida de equipajes: un rodar grave y continuo con el clac de las láminas al pasar la curva."""
	d = 4.0
	x = 0.7 * _motor(rng, d, 48, 120, 900, vaiven=0.25, siseo=0.25)
	x += 0.35 * s._filtro(s._ruido(rng, d), 500, 3500)
	x = s._bucle(x)
	for k in range(8):
		s._poner_ciclico(x, s._clac(rng, 0.05, 900, 7000), 0.2 + k * 0.5, 0.55)
		s._poner_ciclico(x, s._toc(rng, 140, 0.08, 1800), 0.21 + k * 0.5, 0.35)
	return x


@_alta("rayos_x_equipajes", bucle=True, pico=0.3)
def _rayos_x_equipajes(rng: np.random.Generator) -> np.ndarray:
	"""Escáner de rayos X del control: zumbido tenso de ventiladores y la cinta que arrastra las bandejas."""
	d = 3.0
	t = s._t(d)
	x = _motor(rng, d, 100, 250, 1800, siseo=0.4)
	x += 0.12 * np.sin(PI2 * 2400 * t) * (0.7 + 0.3 * np.sin(PI2 * 0.67 * t))
	x += 0.3 * s._filtro(s._ruido(rng, d), 700, 5000) * (0.6 + 0.4 * np.sin(PI2 * (1 / d) * t) ** 2)
	return s._bucle(x)


@_alta("arco_detector_pitido")
def _arco_detector_pitido(rng: np.random.Generator) -> np.ndarray:
	"""Arco detector de metales: tres pitidos agudos e insistentes al pasar con algo metálico."""
	x = np.zeros(s._muestras(0.9))
	for k in range(3):
		s._poner(x, _bip(2600, 0.14), k * 0.24)
		s._poner(x, s._aire(rng, 0.04, 0.3, 0.008), k * 0.24)
	return x


@_alta("buggy_aeropuerto", bucle=True, pico=0.35)
def _buggy_aeropuerto(rng: np.random.Generator) -> np.ndarray:
	"""Buggy eléctrico de asistencia: silbido de motor eléctrico, ruedas de goma y un pitido doble de aviso."""
	d = 2.4
	t = s._t(d)
	x = 0.4 * np.sin(PI2 * 420 * t) * (0.8 + 0.2 * np.sin(PI2 * 3 * t)) + 0.2 * np.sin(PI2 * 840 * t)
	x += 0.35 * s._filtro(s._ruido(rng, d), 300, 2500)
	x += 0.2 * s._siseo(rng, d, 3200, 9000)
	x = s._bucle(x)
	for inicio in (0.3, 0.55, 1.5, 1.75):
		s._poner_ciclico(x, _bip(1900, 0.13), inicio, 0.9)
	return x


@_alta("puertas_anden_aviso")
def _puertas_anden_aviso(rng: np.random.Generator) -> np.ndarray:
	"""Puertas de andén o de tren: cuatro pitidos rápidos de aviso y las hojas que corren y hacen tope."""
	x = np.zeros(s._muestras(1.9))
	for k in range(4):
		s._poner(x, _bip(1500, 0.09), k * 0.16)
	corre = s._filtro(s._ruido(rng, 0.8), 400, 6500) * s._arco(0.8, 0.6)
	s._poner(x, corre, 0.75, 0.6)
	s._poner(x, s._barrido(180, 120, 0.8) * s._arco(0.8), 0.75, 0.25)
	s._poner(x, s._toc(rng, 120, 0.15, 1600), 1.55, 0.9)
	s._poner(x, s._clac(rng, 0.04, 1200, 9000), 1.56, 0.7)
	return x


@_alta("consigna_bip")
def _consigna_bip(rng: np.random.Generator) -> np.ndarray:
	"""Consigna automática: un pitido de aceptado, el cerrojo eléctrico que salta y la puerta de chapa que se suelta."""
	x = np.zeros(s._muestras(0.95))
	s._poner(x, _bip(1320, 0.2), 0.0)
	s._poner(x, s._aire(rng, 0.05, 0.3, 0.01), 0.0)
	s._poner(x, s._clac(rng, 0.05, 700, 8000), 0.35, 0.9)
	s._poner(x, s._seno(95, 0.12) * s._decae(0.12, 0.03), 0.35, 0.6)
	s._poner(x, s._seno(520, 0.4) * s._decae(0.4, 0.09, 0.001), 0.48, 0.35)
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.48, 0.5)
	return x


@_alta("paso_nivel_campana", pico=0.5)
def _paso_nivel_campana(rng: np.random.Generator) -> np.ndarray:
	"""Señal del paso entre andenes: una campana eléctrica que repica deprisa, ding, ding, ding: viene un tren."""
	x = np.zeros(s._muestras(2.0))
	for k in range(8):
		golpe = s._campana(1250 if k % 2 == 0 else 1050, 0.45)
		s._poner(x, golpe, k * 0.24, 0.8)
		s._poner(x, s._aire(rng, 0.04, 0.35, 0.008), k * 0.24)
	return x


@_alta("tren_parado", bucle=True, pico=0.3)
def _tren_parado(rng: np.random.Generator) -> np.ndarray:
	"""Tren parado en el andén: el zumbido de los equipos, la ventilación y, de vez en cuando, un soplido de aire comprimido."""
	d = 5.0
	x = _motor(rng, d, 55, 100, 700, vaiven=0.2, siseo=0.3)
	x += 0.3 * s._filtro(s._ruido(rng, d), 1500, 7000)
	x = s._bucle(x)
	for inicio in (1.1, 3.6):
		soplido = s._filtro(s._ruido(rng, 0.5), 2500, 11000) * s._decae(0.5, 0.14, 0.01)
		s._poner_ciclico(x, soplido, inicio, 0.9)
	return x


@_alta("amarras_crujido", bucle=True, pico=0.3)
def _amarras_crujido(rng: np.random.Generator) -> np.ndarray:
	"""Pantalán o barco amarrado: el agua que chapotea contra el muelle y las amarras que crujen al tensarse."""
	d = 5.0
	t = s._t(d)
	x = s._filtro(s._ruido(rng, d), 300, 6000) * (0.35 + 0.65 * np.sin(PI2 * (2 / d) * t) ** 2)
	x += 0.25 * s._siseo(rng, d, 3500, 9000) * (0.4 + 0.6 * np.sin(PI2 * (2 / d) * t + 0.6) ** 2)
	x = s._bucle(x)
	for inicio, f0, f1 in ((0.8, 210, 300), (2.9, 260, 190), (4.0, 180, 240)):
		s._poner_ciclico(x, s._chirrido(f0, f1, 0.45), inicio, 0.3)
	for _k in range(6):
		f = rng.uniform(500, 1400)
		s._poner_ciclico(x, s._barrido(f, f * 1.7, 0.05) * s._decae(0.05, 0.015, 0.002), rng.uniform(0, d - 0.1), 0.4)
	return x


@_alta("cinta_facturacion")
def _cinta_facturacion(rng: np.random.Generator) -> np.ndarray:
	"""Facturación: la maleta cae en la báscula, pita el peso, la impresora saca la etiqueta y la cinta se lleva la maleta."""
	x = np.zeros(s._muestras(2.6))
	s._poner(x, s._toc(rng, 90, 0.2, 1200), 0.0, 1.0)
	s._poner(x, _bip(1760, 0.12), 0.4, 0.8)
	impresora = s._filtro(s._ruido(rng, 0.5), 1800, 8000) * (0.6 + 0.4 * np.sign(s._seno(60, 0.5))) * s._arco(0.5, 0.5)
	s._poner(x, impresora, 0.65, 0.5)
	cinta = _motor(rng, 1.3, 70, 200, 1500, siseo=0.3) * s._arco(1.3, 0.5)
	s._poner(x, cinta, 1.25, 0.7)
	return x


@_alta("bandeja_seguridad")
def _bandeja_seguridad(rng: np.random.Generator) -> np.ndarray:
	"""Bandeja del control de seguridad: plástico hueco que golpea y rueda por los rodillos de metal."""
	x = np.zeros(s._muestras(0.9))
	s._poner(x, s._golpe(rng, "plastico"), 0.0, 1.0)
	for k in range(7):
		s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.16 + k * 0.085, 0.5 - 0.05 * k)
		s._poner(x, s._seno(900 + 40 * k, 0.04) * s._decae(0.04, 0.01), 0.16 + k * 0.085, 0.2)
	return x
