"""Sonidos propios del complemento «residencia_y_ayudas_tecnicas», sintetizados con numpy (mismo sistema que ``sonidos.py``).

Son los de las ayudas técnicas que suenan de verdad y sirven para situarse:
la baliza de orientación de un vestíbulo, el motor de una grúa o de una cama
articulada, la silla salvaescaleras, la impresora braille, la máquina Perkins,
el reloj parlante, la llamada de asistencia, el timbre de casa, el teléfono
de teclas grandes, el chasquido de una barra abatible, el bombo del bingo y
el perro guía bebiendo.
"""

from __future__ import annotations

import numpy as np

from app.audio import sintesis as s
from tools.complementos_serie.sonidos import PI2, _alta, _bip, _motor


@_alta("baliza_orientacion_interior", bucle=True, pico=0.35)
def _baliza_orientacion_interior(rng: np.random.Generator) -> np.ndarray:
	"""Baliza de orientación de vestíbulo: dos golpes de madera agudos y secos, «toc, toc», y una pausa, sin fin."""
	d = 2.0
	x = np.zeros(s._muestras(d))
	for inicio, f in ((0.1, 1250.0), (0.38, 1650.0)):
		s._poner_ciclico(x, s._toc(rng, f, 0.12, 4200), inicio, 1.0)
		s._poner_ciclico(x, s._aire(rng, 0.05, 0.6, 0.01), inicio, 1.0)
	return x


@_alta("actuador_ayuda_tecnica", pico=0.45)
def _actuador_ayuda_tecnica(rng: np.random.Generator) -> np.ndarray:
	"""Actuador eléctrico de grúa, cama articulada o encimera regulable: arranca, zumba subiendo de tono y para con un clic."""
	d = 2.2
	t = s._t(d)
	f = 85.0 + 25.0 * np.clip(t / 0.4, 0, 1)
	fase = PI2 * np.cumsum(f) / s.FRECUENCIA
	x = 0.5 * np.sin(fase) + 0.3 * np.sin(2 * fase + 0.7) + 0.2 * np.sin(5 * fase)
	x += 0.4 * s._filtro(s._ruido(rng, d), 600, 3500)
	x += 0.3 * s._siseo(rng, d, 3200, 9000)
	x *= np.clip(t / 0.15, 0, 1) * np.clip((d - 0.12 - t) / 0.1, 0, 1)
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0, 0.8)
	s._poner(x, s._clac(rng, 0.04, 1000, 8000), d - 0.1, 0.9)
	return x


@_alta("salvaescaleras_motor", bucle=True, pico=0.35)
def _salvaescaleras_motor(rng: np.random.Generator) -> np.ndarray:
	"""Silla o plataforma salvaescaleras en marcha: motor lento, el piñón que repica en la cremallera del raíl y un pitido de aviso."""
	d = 3.0
	x = _motor(rng, d, 70, 200, 1600, vaiven=0.0, siseo=0.3)
	x = s._bucle(x)
	largo = len(x) / s.FRECUENCIA
	for k in range(int(largo * 8)):
		s._poner_ciclico(x, s._clac(rng, 0.02, 1800, 8000), k / 8.0, 0.35)
	s._poner_ciclico(x, _bip(1900, 0.12), 0.3, 0.5)
	s._poner_ciclico(x, _bip(1900, 0.12), 1.65, 0.5)
	return x


@_alta("impresora_braille_martilleo", bucle=True, pico=0.4)
def _impresora_braille_martilleo(rng: np.random.Generator) -> np.ndarray:
	"""Impresora braille: ráfagas de punzones que martillean el papel grueso, muy ruidosa, con el arrastre entre líneas."""
	d = 3.0
	x = 0.25 * _motor(rng, d, 110, 300, 2000, siseo=0.2)
	x = s._bucle(x)
	largo = len(x) / s.FRECUENCIA
	for linea in range(3):
		inicio = linea * largo / 3.0
		for k in range(22):
			golpe = s._toc(rng, 320.0, 0.03, 3500) + 0.6 * s._clac(rng, 0.03, 2500, 11000)
			s._poner_ciclico(x, golpe, inicio + k * 0.03 + rng.uniform(0, 0.004), rng.uniform(0.6, 1.0))
		arrastre = s._filtro(s._ruido(rng, 0.14), 900, 6000) * s._arco(0.14, 0.8)
		s._poner_ciclico(x, arrastre, inicio + 0.72, 0.5)
	return x


@_alta("maquina_perkins", pico=0.5)
def _maquina_perkins(rng: np.random.Generator) -> np.ndarray:
	"""Máquina Perkins: cinco golpes de teclas pesadas sobre el papel, la campanilla de fin de línea y el carro que vuelve."""
	x = np.zeros(s._muestras(2.0))
	for k, inicio in enumerate((0.0, 0.17, 0.33, 0.52, 0.68)):
		s._poner(x, s._toc(rng, 210.0 + 15.0 * (k % 2), 0.08, 2600), inicio, 0.9)
		s._poner(x, s._clac(rng, 0.03, 2000, 10000), inicio, 0.7)
	s._poner(x, s._campana(2400, 0.5, (1, 2.4, 4.1), (1, 0.6, 0.3)), 0.9, 0.5)
	retorno = s._filtro(s._ruido(rng, 0.45), 700, 7000) * s._arco(0.45, 0.6) * (0.6 + 0.4 * np.sign(s._seno(60, 0.45)))
	s._poner(x, retorno, 1.2, 0.6)
	s._poner(x, s._toc(rng, 160, 0.1, 1800), 1.66, 0.9)
	return x


@_alta("reloj_parlante_hora", pico=0.5)
def _reloj_parlante_hora(rng: np.random.Generator) -> np.ndarray:
	"""Reloj parlante: el botón, un pitido y una voz sintética, sin palabras, que dice la hora en cinco sílabas."""
	x = np.zeros(s._muestras(2.1))
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0, 0.7)
	s._poner(x, _bip(1500, 0.1), 0.08, 0.6)
	silabas = ((170, 160, (700, 1200)), (160, 175, (400, 2000)), (175, 150, (500, 900)), (150, 165, (650, 1500)), (165, 120, (450, 1100)))
	for k, (f0, f1, formantes) in enumerate(silabas):
		largo = 0.2 if k < 4 else 0.32
		s._poner(x, s._vocal(f0, f1, largo, formantes, largo * 0.6), 0.4 + k * 0.27, 0.9)
		s._poner(x, s._aire(rng, 0.04, 0.35, 0.01), 0.4 + k * 0.27, 1.0)
	return x


@_alta("llamada_asistencia", pico=0.5)
def _llamada_asistencia(rng: np.random.Generator) -> np.ndarray:
	"""Llamada de asistencia: el pulsador y tres zumbidos cortos e insistentes, como los de un control de enfermería."""
	x = np.zeros(s._muestras(1.5))
	s._poner(x, s._clac(rng, 0.03, 1200, 8000), 0.0, 0.8)
	for k in range(3):
		d = 0.22
		zumbido = (s._barrido(820, 820, d, "cuadrada") * 0.5 + s._seno(2460, d) * 0.3 + s._seno(4100, d) * 0.15) * s._arco(d, 0.25)
		s._poner(x, s._filtro(zumbido, 300, 9000), 0.15 + k * 0.4, 0.8)
	return x


@_alta("timbre_luminoso_dindon", pico=0.5)
def _timbre_luminoso_dindon(rng: np.random.Generator) -> np.ndarray:
	"""Timbre de casa con destellos: «din, don» de dos campanas y, debajo, los chasquidos del destellador."""
	x = np.zeros(s._muestras(1.8))
	s._poner(x, s._campana(1320, 0.9, (1, 2.0, 3.0, 4.2), (1, 0.7, 0.4, 0.3)), 0.0, 0.9)
	s._poner(x, s._campana(1047, 1.2, (1, 2.0, 3.0, 4.2), (1, 0.7, 0.4, 0.3)), 0.45, 0.9)
	for k in range(6):
		s._poner(x, s._clac(rng, 0.015, 3000, 12000), 0.02 + k * 0.25, 0.35)
	return x


@_alta("telefono_teclas_grandes_tonos", pico=0.5)
def _telefono_teclas_grandes_tonos(rng: np.random.Generator) -> np.ndarray:
	"""Teléfono de teclas grandes: se descuelga, cuatro teclas con su tono doble y un tono de llamada."""
	x = np.zeros(s._muestras(2.4))
	s._poner(x, s._clac(rng, 0.05, 900, 7000), 0.0, 0.8)
	pares = ((697, 1209), (770, 1336), (852, 1477), (941, 1336))
	for k, (grave, agudo) in enumerate(pares):
		d = 0.13
		tono = (s._seno(grave, d) + s._seno(agudo, d) + 0.25 * s._seno(agudo * 3, d)) * s._arco(d, 0.3)
		s._poner(x, tono, 0.2 + k * 0.22, 0.5)
		s._poner(x, s._clac(rng, 0.02, 2500, 10000), 0.2 + k * 0.22, 0.5)
	d = 0.9
	llamada = (s._seno(425, d) + 0.2 * s._seno(1275, d)) * s._arco(d, 0.2)
	s._poner(x, llamada, 1.3, 0.45)
	s._poner(x, 0.12 * s._siseo(rng, d, 3200, 8000) * s._arco(d, 0.2), 1.3, 1.0)
	return x


@_alta("barra_abatible_clac", pico=0.5)
def _barra_abatible_clac(rng: np.random.Generator) -> np.ndarray:
	"""Barra o asiento abatible: la bisagra gira con un roce metálico y encaja en su tope con un golpe de tubo."""
	x = np.zeros(s._muestras(0.8))
	s._poner(x, s._chirrido(420, 620, 0.3), 0.0, 0.3)
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 1500, 7000) * s._arco(0.3, 1.0), 0.0, 0.25)
	s._poner(x, s._clac(rng, 0.04, 1200, 9000), 0.32, 1.0)
	for parcial, peso, cola in ((310, 1.0, 0.1), (870, 0.6, 0.08), (2300, 0.4, 0.06), (3900, 0.25, 0.04)):
		s._poner(x, s._seno(parcial, 0.4) * s._decae(0.4, cola, 0.002), 0.32, 0.4 * peso)
	return x


@_alta("bombo_bingo", pico=0.45)
def _bombo_bingo(rng: np.random.Generator) -> np.ndarray:
	"""Bombo de bingo: la jaula gira y las bolas repican dentro, hasta que una cae por la rampa y se para."""
	d = 2.4
	x = np.zeros(s._muestras(d))
	giro = s._filtro(s._ruido(rng, 1.6), 500, 5000) * s._arco(1.6, 0.5) * (0.6 + 0.4 * np.abs(s._seno(3.0, 1.6)))
	s._poner(x, giro, 0.0, 0.35)
	for _k in range(40):
		inicio = float(rng.uniform(0.0, 1.55))
		f = float(rng.uniform(1400, 3200))
		s._poner(x, s._seno(f, 0.03) * s._decae(0.03, 0.006, 0.0005), inicio, float(rng.uniform(0.3, 0.8)))
		s._poner(x, s._clac(rng, 0.012, 3000, 12000), inicio, 0.4)
	rodar = s._filtro(s._ruido(rng, 0.35), 1200, 6000) * s._arco(0.35, 0.7)
	s._poner(x, rodar, 1.65, 0.5)
	s._poner(x, s._toc(rng, 900, 0.08, 4000), 2.02, 1.0)
	return x


@_alta("perro_guia_bebe", pico=0.4)
def _perro_guia_bebe(rng: np.random.Generator) -> np.ndarray:
	"""Perro guía que bebe: seis lengüetazos en el agua y la chapa del collar que tintinea contra el cuenco."""
	x = np.zeros(s._muestras(1.9))
	for k in range(6):
		inicio = 0.05 + k * 0.26 + float(rng.uniform(0, 0.03))
		lametazo = s._filtro(s._ruido(rng, 0.09), 700, 6500) * s._arco(0.09, 0.8)
		s._poner(x, lametazo, inicio, 0.8)
		s._poner(x, s._barrido(900, 1900, 0.04) * s._decae(0.04, 0.01, 0.002), inicio + 0.05, 0.4)
	for inicio in (0.6, 1.45):
		s._poner(x, s._destello(rng, 3400, 0.15), inicio, 0.35)
	return x
