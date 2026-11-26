"""Sonidos propios del complemento «tiendas», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Son los que hacen reconocible una tienda con el oído: el horno de la
panadería, las cortadoras, la máquina de llaves, la campanilla de la puerta,
el goteo del hielo de la pescadería, las perchas que corren por la barra, la
persiana del puesto, las máquinas de monedas, el enfundador de paraguas y el
peluche motorizado del centro comercial.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _bip, _motor


@_alta("horno_panaderia", bucle=True, pico=0.3)
def _horno_panaderia(rng: np.random.Generator) -> np.ndarray:
	"""Horno de panadería: la turbina de aire caliente sopla sin parar, con un zumbido grave."""
	d = 4.0
	t = s._t(d)
	x = 0.6 * _motor(rng, d, 48, 120, 900, siseo=0.2)
	soplo = s._filtro(s._ruido(rng, d), 400, 6000) * (0.8 + 0.2 * np.sin(PI2 * 0.5 * t))
	return s._bucle(x + 0.7 * soplo)


@_alta("cortadora_pan")
def _cortadora_pan(rng: np.random.Generator) -> np.ndarray:
	"""Cortadora de pan: el motor arranca, las cuchillas traquetean a toda prisa y se para."""
	d = 2.4
	t = s._t(d)
	x = _motor(rng, d, 95, 300, 3000, siseo=0.3)
	traqueteo = s._filtro(s._ruido(rng, d), 1200, 8000) * (0.5 + 0.5 * np.sign(np.sin(PI2 * 24 * t)))
	x = (x + 0.9 * traqueteo) * np.clip(t / 0.15, 0, 1) * np.clip((d - t) / 0.35, 0, 1)
	s._poner(x, s._clac(rng, 0.04, 1000, 8000), 0.0, 1.2)
	s._poner(x, s._toc(rng, 170, 0.12, 1600), d - 0.2, 1.0)
	return x


@_alta("cortadora_fiambre")
def _cortadora_fiambre(rng: np.random.Generator) -> np.ndarray:
	"""Cortadora de fiambre: el disco gira con un silbido fino y el carro pasa tres veces, ris, ris, ris."""
	d = 2.6
	t = s._t(d)
	x = 0.6 * _motor(rng, d, 110, 400, 2500, siseo=0.25)
	x += 0.25 * np.sin(PI2 * 3400 * t) * (0.7 + 0.3 * np.sin(PI2 * 7 * t))
	x *= np.clip(t / 0.25, 0, 1) * np.clip((d - t) / 0.4, 0, 1)
	for k in range(3):
		s._poner(x, s._filtro(s._ruido(rng, 0.3), 2500, 10000) * s._arco(0.3, 1.5), 0.5 + 0.6 * k, 1.1)
	return x


@_alta("duplicadora_llaves", bucle=True, pico=0.4)
def _duplicadora_llaves(rng: np.random.Generator) -> np.ndarray:
	"""Máquina de duplicar llaves: la fresa muerde el metal con un chirrido agudo que va y viene."""
	d = 3.0
	t = s._t(d)
	x = 0.5 * _motor(rng, d, 120, 500, 3000, siseo=0.2)
	mordida = 0.5 + 0.5 * np.sin(PI2 * (2 / d) * t) ** 2
	chirrido = np.sign(np.sin(PI2 * 2900 * t + 2.0 * np.sin(PI2 * 31 * t)))
	x += 0.35 * s._filtro(chirrido, 2000, 9000) * mordida
	x += 0.5 * s._filtro(s._ruido(rng, d), 3500, 11000) * mordida
	return s._bucle(x)


@_alta("campanilla_tienda")
def _campanilla_tienda(rng: np.random.Generator) -> np.ndarray:
	"""Campanilla de la puerta de una tienda: din, don."""
	x = np.zeros(s._muestras(1.5))
	s._poner(x, s._campana(1318.5, 1.0, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.0)
	s._poner(x, s._campana(1046.5, 1.1, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.35)
	s._poner(x, s._aire(rng, 0.04, 0.4, 0.008), 0.0)
	s._poner(x, s._aire(rng, 0.04, 0.4, 0.008), 0.35)
	return x


@_alta("zumbador_joyeria")
def _zumbador_joyeria(rng: np.random.Generator) -> np.ndarray:
	"""Puerta con apertura eléctrica: el timbre, el zumbido del abrepuertas y el pestillo que salta."""
	x = np.zeros(s._muestras(2.0))
	s._poner(x, _bip(1760, 0.25), 0.0, 0.8)
	d = 1.0
	zumbido = s._filtro(np.sign(s._seno(100, d)), 80, 7000) * (0.8 + 0.2 * s._seno(50, d))
	s._poner(x, zumbido * np.clip(s._t(d) / 0.02, 0, 1) * np.clip((d - s._t(d)) / 0.03, 0, 1), 0.55, 0.6)
	s._poner(x, 0.3 * s._siseo(rng, d, 3200, 9000) * s._arco(d, 0.5), 0.55)
	s._poner(x, s._clac(rng, 0.05, 900, 8000), 1.6, 1.2)
	s._poner(x, s._toc(rng, 190, 0.15, 1800), 1.63, 0.8)
	return x


@_alta("goteo_pescaderia", bucle=True, pico=0.3)
def _goteo_pescaderia(rng: np.random.Generator) -> np.ndarray:
	"""Mostrador de hielo: gotas que caen sin orden a la bandeja y un hilo de agua al desagüe."""
	d = 5.0
	x = 0.12 * s._filtro(s._ruido(rng, d), 2500, 9000)
	x = s._bucle(x, 400.0)
	duracion = len(x) / s.FRECUENCIA
	for _k in range(16):
		f = rng.uniform(900, 2600)
		gota = s._barrido(f, f * 1.7, 0.05) * s._decae(0.05, 0.012, 0.002)
		s._poner_ciclico(x, gota, rng.uniform(0, duracion), rng.uniform(0.4, 1.0))
		s._poner_ciclico(x, s._aire(rng, 0.03, 0.3, 0.006), rng.uniform(0, duracion))
	return x


@_alta("caballito_monedas", bucle=True, pico=0.35)
def _caballito_monedas(rng: np.random.Generator) -> np.ndarray:
	"""Atracción infantil de monedas: una musiquilla de organillo y el motor que la balancea."""
	paso = 0.25
	notas = (523.25, 659.25, 783.99, 659.25, 698.46, 880.0, 783.99, 0, 587.33, 698.46, 783.99, 698.46, 659.25, 523.25, 587.33, 0)
	d = paso * len(notas)
	# El motor se hace un cuarto de segundo más largo: es lo que ``_bucle`` gasta en fundir el final con el principio.
	t = s._t(d + 0.25)
	x = 0.25 * _motor(rng, d + 0.25, 55, 150, 900, siseo=0.25) * (0.7 + 0.3 * np.sin(PI2 * (2 / d) * t))
	x = s._bucle(x, 250.0)
	for k, f in enumerate(notas):
		if f:
			nota = s._filtro(s._barrido(f, f, 0.3, "cuadrada"), 200, 8000) * s._decae(0.3, 0.12, 0.004)
			s._poner_ciclico(x, nota, k * paso, 0.5)
			s._poner_ciclico(x, s._aire(rng, 0.03, 0.3, 0.008), k * paso)
	return x


@_alta("sillon_masaje_monedas", bucle=True, pico=0.3)
def _sillon_masaje_monedas(rng: np.random.Generator) -> np.ndarray:
	"""Sillón de masaje: los rodillos suben y bajan con un zumbido que va y viene, y la tapicería cruje."""
	d = 4.0
	t = s._t(d)
	x = _motor(rng, d, 70, 150, 1100, vaiven=0.5, siseo=0.3)
	x += 0.3 * s._filtro(s._ruido(rng, d), 3000, 8000) * np.abs(np.sin(PI2 * 1.0 * t)) ** 4
	return s._bucle(x)


@_alta("turno_tienda")
def _turno_tienda(rng: np.random.Generator) -> np.ndarray:
	"""Pantalla de turno: un «din» de campana eléctrica y el clac del número que cambia."""
	x = np.zeros(s._muestras(1.1))
	s._poner(x, s._campana(1568.0, 0.9, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.0)
	s._poner(x, s._aire(rng, 0.04, 0.4, 0.008), 0.0)
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.3, 0.6)
	return x


@_alta("bolas_centro_comercial")
def _bolas_centro_comercial(rng: np.random.Generator) -> np.ndarray:
	"""Piscina de bolas: un montón de bolas huecas de plástico que entrechocan y ruedan."""
	d = 1.6
	x = 0.15 * s._filtro(s._ruido(rng, d), 1500, 8000) * s._arco(d, 0.8)
	for _k in range(40):
		f = rng.uniform(500, 1400)
		bola = (s._seno(f, 0.05) + 0.4 * s._seno(f * 2.7, 0.05)) * s._decae(0.05, 0.01, 0.001)
		momento = rng.uniform(0, d - 0.1)
		s._poner(x, bola, momento, rng.uniform(0.3, 1.0) * (1.0 - 0.5 * momento / d))
		s._poner(x, s._clac(rng, 0.015, 2500, 10000), momento, 0.4)
	return x


@_alta("perchas_barra")
def _perchas_barra(rng: np.random.Generator) -> np.ndarray:
	"""Perchas que corren por la barra de un perchero: roce de metal y varios tintineos seguidos."""
	d = 0.9
	x = 0.5 * s._filtro(s._ruido(rng, d), 2500, 9000) * s._arco(d, 1.2)
	for k in range(6):
		f = rng.uniform(2200, 4200)
		tin = (s._seno(f, 0.12) + 0.5 * s._seno(f * 2.4, 0.12)) * s._decae(0.12, 0.03, 0.001)
		s._poner(x, tin, 0.08 + 0.12 * k + rng.uniform(0, 0.04), rng.uniform(0.5, 1.0))
	return x


@_alta("tajo_carnicero")
def _tajo_carnicero(rng: np.random.Generator) -> np.ndarray:
	"""Tajo de carnicero: tres golpes secos de cuchilla sobre la madera maciza."""
	x = np.zeros(s._muestras(1.3))
	for k, momento in enumerate((0.0, 0.4, 0.8)):
		s._poner(x, s._toc(rng, 120 - 8 * k, 0.25, 1300), momento, 1.0)
		s._poner(x, s._clac(rng, 0.03, 2500, 11000), momento, 0.9)
		s._poner(x, s._seno(3100, 0.08) * s._decae(0.08, 0.02, 0.001), momento, 0.25)
	return x


@_alta("enfundador_paraguas")
def _enfundador_paraguas(rng: np.random.Generator) -> np.ndarray:
	"""Enfundador de paraguas: el paraguas entra rozando, la funda de plástico cruje al estirarse y el corte hace clac."""
	d = 1.4
	x = np.zeros(s._muestras(d))
	s._poner(x, s._filtro(s._ruido(rng, 0.35), 1500, 7000) * s._arco(0.35, 1.5), 0.0, 0.5)
	for _k in range(26):
		s._poner(x, s._clac(rng, rng.uniform(0.004, 0.015), 2500, 12000), rng.uniform(0.35, 1.05), rng.uniform(0.2, 0.7))
	s._poner(x, s._filtro(s._ruido(rng, 0.5), 3000, 11000) * s._arco(0.5, 2.0), 0.4, 0.35)
	s._poner(x, s._clac(rng, 0.04, 1200, 9000), 1.12, 1.2)
	s._poner(x, s._toc(rng, 260, 0.1, 2000), 1.13, 0.5)
	return x


@_alta("peluche_motorizado", bucle=True, pico=0.35)
def _peluche_motorizado(rng: np.random.Generator) -> np.ndarray:
	"""Animal de peluche motorizado: el motor eléctrico zumba agudo, las ruedas ruedan y suena una cancioncilla de pitidos."""
	paso = 0.3
	notas = (659.25, 783.99, 880.0, 783.99, 659.25, 587.33, 523.25, 0, 587.33, 659.25, 587.33, 0)
	d = paso * len(notas)
	t = s._t(d + 0.25)
	x = 0.3 * _motor(rng, d + 0.25, 180, 600, 4000, vaiven=1.5, siseo=0.3)
	x += 0.25 * s._filtro(s._ruido(rng, d + 0.25), 200, 1200) * (0.7 + 0.3 * np.sin(PI2 * 3 * t))
	x = s._bucle(x, 250.0)
	for k, f in enumerate(notas):
		if f:
			s._poner_ciclico(x, _bip(f, 0.2) * s._decae(0.2, 0.08, 0.004), k * paso, 0.45)
	return x


@_alta("persiana_puesto")
def _persiana_puesto(rng: np.random.Generator) -> np.ndarray:
	"""Persiana metálica: las lamas suben traqueteando por las guías y hacen tope arriba."""
	d = 2.2
	t = s._t(d)
	lamas = 0.5 + 0.5 * np.sign(np.sin(PI2 * (9 + 5 * t / d) * t))
	x = s._filtro(s._ruido(rng, d), 500, 9000) * lamas * np.clip(t / 0.1, 0, 1) * np.clip((d - t) / 0.2, 0, 1)
	x += 0.3 * s._filtro(np.sign(s._seno(140, d)), 100, 3000) * lamas
	s._poner(x, s._toc(rng, 150, 0.2, 2000), d - 0.22, 1.5)
	s._poner(x, s._clac(rng, 0.05, 1500, 9000), d - 0.22, 1.0)
	return x
