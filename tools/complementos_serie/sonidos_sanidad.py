"""Sonidos propios del complemento «sanidad», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Son los que de verdad se oyen en un centro de salud o en un hospital y
sirven para situarse: la llamada de turnos, el pitido del monitor, la alarma
de una bomba de infusión, el martilleo de la resonancia, la turbina del
dentista… Todos llevan agudos por encima de 3 kHz para poder localizarlos.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _bip, _motor


def _pitido(rng: np.random.Generator, f: float, d: float = 0.1) -> np.ndarray:
	"""Pitido electrónico de aparato clínico: tono con armónicos altos y un chasquido de agudos al empezar."""
	x = _bip(f, d) + 0.2 * s._seno(4 * f, d) * s._arco(d, 0.3) + 0.12 * s._seno(6 * f, d) * s._arco(d, 0.3)
	return x + s._aire(rng, d, 0.25, 0.008)


@_alta("sanidad_llamada_turno", bucle=True, pico=0.35)
def _llamada_turno(rng: np.random.Generator) -> np.ndarray:
	"""Pantalla de turnos: din, don, el número que cambia con dos chasquidos y unos segundos de calma."""
	d = 6.0
	x = 0.004 * s._siseo(rng, d, 3200, 9000)
	x = s._bucle(x)
	s._poner_ciclico(x, s._campana(1175, 1.1, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.4, 1.0)
	s._poner_ciclico(x, s._aire(rng, 0.06, 0.5, 0.01), 0.4)
	s._poner_ciclico(x, s._campana(880, 1.4, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.95, 1.0)
	s._poner_ciclico(x, s._aire(rng, 0.06, 0.5, 0.01), 0.95)
	for inicio in (2.2, 2.38):
		s._poner_ciclico(x, s._clac(rng, 0.03, 1800, 9000), inicio, 0.35)
	return x


@_alta("sanidad_monitor_cardiaco", bucle=True, pico=0.3)
def _monitor_cardiaco(rng: np.random.Generator) -> np.ndarray:
	"""Monitor de constantes: un pitido corto y regular con cada latido, sobre el soplo del ventilador."""
	d = 4.0
	x = 0.02 * s._siseo(rng, d, 3200, 9000) + 0.015 * s._filtro(s._ruido(rng, d), 150, 900)
	x = s._bucle(x)
	for k in range(5):
		s._poner_ciclico(x, _pitido(rng, 1000, 0.09), 0.1 + k * 0.75, 1.0)
	return x


@_alta("sanidad_bomba_infusion", bucle=True, pico=0.3)
def _bomba_infusion(rng: np.random.Generator) -> np.ndarray:
	"""Bomba de infusión: el motorcillo da un paso cada segundo y, de tanto en tanto, tres pitidos de aviso."""
	d = 5.0
	x = 0.03 * _motor(rng, d, 120, 300, 1800, siseo=0.5)
	x = s._bucle(x)
	for k in range(5):
		s._poner_ciclico(x, s._clac(rng, 0.04, 1200, 8000), 0.15 + k * 0.95, 0.3)
		s._poner_ciclico(x, s._seno(340, 0.08) * s._decae(0.08, 0.02), 0.15 + k * 0.95, 0.2)
	for k in range(3):
		s._poner_ciclico(x, _pitido(rng, 2400, 0.12), 3.3 + k * 0.22, 0.9)
	return x


@_alta("sanidad_resonancia", bucle=True, pico=0.4)
def _resonancia(rng: np.random.Generator) -> np.ndarray:
	"""Resonancia magnética en marcha: martilleo rápido y áspero que cambia de tono, con el bombeo del helio de fondo."""
	d = 3.25
	t = s._t(d)
	grave = np.sign(np.sin(PI2 * 560 * t)) * (np.sin(PI2 * 12 * t) > 0)
	agudo = np.sign(np.sin(PI2 * 780 * t)) * (np.sin(PI2 * 18 * t) > 0.2)
	x = np.where(t < d / 2, grave, agudo).astype(np.float64)
	x = s._filtro(x, 200, 7000)
	bombeo = s._filtro(s._ruido(rng, d), 300, 2500) * (0.5 + 0.5 * np.sin(PI2 * (4 / d) * t)) ** 4
	x = x + 0.35 * bombeo + 0.08 * s._siseo(rng, d, 3200, 9000)
	return s._bucle(x)


@_alta("sanidad_gel", pico=0.45)
def _gel(rng: np.random.Generator) -> np.ndarray:
	"""Dispensador de gel: la palanca cede, sale un chorrito con un soplo y la palanca vuelve."""
	x = np.zeros(s._muestras(0.55))
	s._poner(x, s._clac(rng, 0.04, 900, 7000), 0.0, 0.8)
	s._poner(x, s._filtro(s._ruido(rng, 0.2), 2500, 10000) * s._arco(0.2, 0.6), 0.05, 0.9)
	s._poner(x, s._barrido(500, 260, 0.12) * s._decae(0.12, 0.04, 0.01), 0.1, 0.35)
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.36, 0.6)
	return x


@_alta("sanidad_cama_motor", pico=0.45)
def _cama_motor(rng: np.random.Generator) -> np.ndarray:
	"""Cama articulada: el botón del mando, el motor que sube el cabecero zumbando y el tope."""
	d = 1.5
	x = np.zeros(s._muestras(d + 0.3))
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0, 0.6)
	motor = s._filtro(s._barrido(170, 215, d, "sierra"), 120, 5000) + 0.5 * s._filtro(s._ruido(rng, d), 700, 6000)
	s._poner(x, motor * s._arco(d, 0.25), 0.06, 0.8)
	s._poner(x, s._toc(rng, 160, 0.12, 1800), d + 0.05, 0.7)
	return x


@_alta("sanidad_bascula_farmacia", pico=0.5)
def _bascula_farmacia(rng: np.random.Generator) -> np.ndarray:
	"""Báscula de farmacia: cae la moneda, pita, baja el tallímetro zumbando, dos pitidos y sale el tique."""
	x = np.zeros(s._muestras(3.4))
	s._poner(x, s._destello(rng, 3100, 0.15), 0.0, 0.8)
	s._poner(x, s._toc(rng, 320, 0.08, 2500), 0.12, 0.5)
	s._poner(x, _pitido(rng, 1320, 0.14), 0.4, 0.8)
	motor = s._filtro(s._barrido(260, 200, 1.0, "sierra"), 150, 5000) + 0.4 * s._filtro(s._ruido(rng, 1.0), 900, 7000)
	s._poner(x, motor * s._arco(1.0, 0.3), 0.7, 0.5)
	for k in range(2):
		s._poner(x, _pitido(rng, 1760, 0.12), 1.9 + k * 0.2, 0.9)
	tique = s._filtro(s._ruido(rng, 0.7), 1500, 9000) * s._arco(0.7, 0.4) * (0.6 + 0.4 * np.abs(s._seno(28, 0.7)))
	s._poner(x, tique, 2.45, 0.6)
	return x


@_alta("sanidad_turbina_dental", bucle=True, pico=0.3)
def _turbina_dental(rng: np.random.Generator) -> np.ndarray:
	"""Turbina del dentista: un silbido muy agudo que tiembla, con el borboteo del aspirador de saliva."""
	d = 3.0
	t = s._t(d)
	silbido = np.sin(PI2 * 5200 * t + 6.0 * np.sin(PI2 * 2.0 * t)) + 0.5 * np.sin(PI2 * 7900 * t + 4.0 * np.sin(PI2 * 3.0 * t))
	silbido *= 0.7 + 0.3 * np.sin(PI2 * (2 / d) * t)
	aire = s._filtro(s._ruido(rng, d), 3500, 12000)
	gorgoteo = s._filtro(s._ruido(rng, d), 350, 2200)
	pulso = np.abs(s._filtro(s._ruido(rng, d), 5, 25))
	gorgoteo *= pulso / (float(np.max(pulso)) or 1.0)
	return s._bucle(0.5 * silbido + 0.35 * aire + 0.6 * gorgoteo)


@_alta("sanidad_carro_clinico")
def _carro_clinico(rng: np.random.Generator) -> np.ndarray:
	"""Golpe contra un carro clínico: chapa que suena, instrumental que tintinea en las bandejas y las ruedas que ceden."""
	x = np.zeros(s._muestras(0.95))
	s._poner(x, s._golpe(rng, "metal"), 0.0, 1.0)
	for _k in range(7):
		s._poner(x, s._destello(rng, rng.uniform(2800, 5200), 0.1), rng.uniform(0.04, 0.5), rng.uniform(0.2, 0.5))
	s._poner(x, s._filtro(s._ruido(rng, 0.35), 200, 1800) * s._arco(0.35, 0.8), 0.3, 0.3)
	return x


@_alta("sanidad_oxigeno_burbujeo", bucle=True, pico=0.28)
def _oxigeno_burbujeo(rng: np.random.Generator) -> np.ndarray:
	"""Oxígeno abierto: un siseo fino de gas y el burbujeo menudo del vaso humidificador."""
	d = 3.0
	x = 0.5 * s._filtro(s._ruido(rng, d), 4000, 12000) + 0.1 * s._filtro(s._ruido(rng, d), 600, 2500)
	x = s._bucle(x)
	for _k in range(45):
		f = rng.uniform(350, 900)
		burbuja = s._barrido(f, f * 1.7, 0.03) * s._decae(0.03, 0.009, 0.002)
		s._poner_ciclico(x, burbuja, rng.uniform(0, d - 0.3), rng.uniform(0.3, 0.8))
	return x


@_alta("sanidad_timbre_enfermera", pico=0.5)
def _timbre_enfermera(rng: np.random.Generator) -> np.ndarray:
	"""Timbre de llamada a enfermería: el pulsador y dos notas suaves que bajan."""
	x = np.zeros(s._muestras(1.3))
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0, 0.5)
	s._poner(x, s._campana(1568, 0.6, (1, 2.0, 3.0), (1, 0.6, 0.4)), 0.08, 0.9)
	s._poner(x, s._aire(rng, 0.05, 0.4, 0.01), 0.08)
	s._poner(x, s._campana(1245, 0.75, (1, 2.0, 3.0), (1, 0.6, 0.4)), 0.5, 0.9)
	s._poner(x, s._aire(rng, 0.05, 0.4, 0.01), 0.5)
	return x


@_alta("sanidad_desfibrilador_alarma")
def _desfibrilador_alarma(rng: np.random.Generator) -> np.ndarray:
	"""Vitrina del desfibrilador: la puerta se despega y salta una alarma aguda y entrecortada."""
	x = np.zeros(s._muestras(1.9))
	s._poner(x, s._clac(rng, 0.04, 1000, 8000), 0.0, 0.8)
	for k in range(7):
		pulso = (s._barrido(2900, 3400, 0.14, "cuadrada") * 0.5 + s._seno(3100, 0.14)) * s._arco(0.14, 0.25)
		s._poner(x, pulso, 0.15 + k * 0.24, 0.9)
	return x


@_alta("sanidad_rayos_disparo", pico=0.5)
def _rayos_disparo(rng: np.random.Generator) -> np.ndarray:
	"""Radiografía: el tubo coge vueltas con un zumbido que sube, un pitido largo de disparo y el chasquido final."""
	x = np.zeros(s._muestras(1.6))
	giro = s._filtro(s._barrido(140, 420, 0.8, "sierra"), 100, 6000) + 0.3 * s._filtro(s._ruido(rng, 0.8), 2000, 9000)
	s._poner(x, giro * s._arco(0.8, 0.35), 0.0, 0.6)
	s._poner(x, _pitido(rng, 2100, 0.4), 0.85, 0.9)
	s._poner(x, s._clac(rng, 0.05, 700, 8000), 1.3, 0.9)
	return x


@_alta("sanidad_tensiometro", pico=0.5)
def _tensiometro(rng: np.random.Generator) -> np.ndarray:
	"""Tensiómetro automático: la bomba hincha el manguito, el aire se escapa despacio y tres pitidos dan el resultado."""
	x = np.zeros(s._muestras(4.2))
	d = 1.7
	t = s._t(d)
	bomba = _motor(rng, d, 95, 250, 2200, vaiven=11.0, siseo=0.3) * (0.5 + 0.5 * t / d)
	s._poner(x, bomba * s._arco(d, 0.2), 0.0, 0.7)
	escape = s._filtro(s._ruido(rng, 1.3), 3000, 11000) * s._decae(1.3, 0.6, 0.05)
	s._poner(x, escape, d + 0.05, 0.45)
	for k in range(3):
		s._poner(x, _pitido(rng, 1500, 0.12), 3.3 + k * 0.25, 0.9)
	return x
