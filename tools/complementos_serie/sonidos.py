"""Sonidos propios de los complementos de serie, sintetizados con numpy.

Siguen el estilo de ``app/audio/sintesis.py`` y reutilizan sus utilidades
(filtros, envolventes, campanas): son mono, a 44,1 kHz, deterministas (cada
uno con una semilla derivada de su nombre), con el pico fijado y sin clics.
Lo que hay que localizar lleva agudos por encima de 3 kHz.

Cada complemento guarda en su carpeta ``sonidos/`` los que solo usa él; los
que comparten varios van al complemento ``comun`` (lo decide
``tools/generar_complementos.py``).

Este módulo tiene los sonidos de los seis complementos originales. Los de
los demás están en los ``sonidos_<complemento>.py`` de esta misma carpeta,
que se dan de alta aquí con el mismo decorador ``_alta``.
"""

from __future__ import annotations

import zlib
from collections.abc import Callable
from dataclasses import dataclass

import numpy as np

from app.audio import sintesis as s

PI2 = s.PI2
Generador = Callable[[np.random.Generator], np.ndarray]


@dataclass(frozen=True)
class SonidoSerie:
	"""Un sonido de complemento: cómo se sintetiza, si es un bucle y su pico."""

	hacer: Generador
	bucle: bool = False
	pico: float = 0.55


SONIDOS: dict[str, SonidoSerie] = {}


def _alta(nombre: str, bucle: bool = False, pico: float = 0.55) -> Callable[[Generador], Generador]:
	def decorador(hacer: Generador) -> Generador:
		anterior = SONIDOS.get(nombre)
		if anterior is not None and anterior.hacer.__module__ != hacer.__module__:
			# Dos módulos con el mismo nombre de sonido: uno taparía al otro según el orden de importación.
			raise ValueError(
				f"El sonido «{nombre}» ya está dado de alta en {anterior.hacer.__module__}; elija otro nombre en {hacer.__module__}."
			)
		SONIDOS[nombre] = SonidoSerie(hacer, bucle, pico)
		return hacer

	return decorador


def generar(nombre: str) -> np.ndarray:
	"""Sintetiza el sonido ``nombre``: float32 mono, con el pico fijado."""
	definicion = SONIDOS[nombre]
	rng = np.random.default_rng(zlib.crc32(f"complemento/{nombre}".encode()))
	return s._acabado(definicion.hacer(rng), definicion.pico, definicion.bucle)


def _motor(
	rng: np.random.Generator, d: float, f: float, ruido_lo: float, ruido_hi: float, vaiven: float = 0.0, siseo: float = 0.3
) -> np.ndarray:
	"""Zumbido de motor eléctrico con su ruido mecánico y un siseo agudo para poder situarlo."""
	t = s._t(d)
	x = 0.5 * np.sin(PI2 * f * t) + 0.3 * np.sin(PI2 * 2 * f * t + 0.8) + 0.15 * np.sin(PI2 * 3 * f * t + 1.7)
	x += 0.45 * s._filtro(s._ruido(rng, d), ruido_lo, ruido_hi)
	if vaiven:
		x *= 0.75 + 0.25 * np.sin(PI2 * vaiven * t)
	x += siseo * s._siseo(rng, d, 3200, 9000)
	return x


def _agua(rng: np.random.Generator, d: float, lo: float, hi: float, gotas: int) -> np.ndarray:
	"""Agua que cae durante ``d`` segundos justos (sin preparar para bucle): ruido brillante con borboteo y gotas."""
	x = s._filtro(s._ruido(rng, d), lo, hi)
	borboteo = np.abs(s._filtro(s._ruido(rng, d), 4, 30))
	x *= 0.6 + 0.4 * borboteo / (float(np.max(borboteo)) or 1.0)
	for _k in range(gotas):
		f = rng.uniform(700, 2400)
		s._poner(x, s._barrido(f, f * 1.8, 0.035) * s._decae(0.035, 0.01, 0.002), rng.uniform(0, d - 0.05), rng.uniform(0.2, 0.6))
	return x


def _bip(f: float, d: float = 0.09) -> np.ndarray:
	return (s._seno(f, d) + 0.3 * s._seno(2 * f, d) + 0.15 * s._seno(3 * f, d)) * s._arco(d, 0.3)


# ── Hogar ────────────────────────────────────────────────────────────────────


@_alta("lavadora", bucle=True, pico=0.4)
def _lavadora(rng: np.random.Generator) -> np.ndarray:
	"""El tambor da vueltas: un zumbido que va y viene, con el agua y la ropa cayendo."""
	d = 4.0
	x = _motor(rng, d, 62, 150, 1200, vaiven=0.5)
	chapoteo = s._filtro(s._ruido(rng, d), 500, 4500) * (0.5 + 0.5 * np.sin(PI2 * 1.0 * s._t(d)) ** 2)
	x += 0.5 * chapoteo
	x = s._bucle(x)
	for k in range(4):
		s._poner_ciclico(x, s._filtro(s._ruido(rng, 0.12), 90, 600) * s._decae(0.12, 0.04), 0.45 + k, 1.2)
	return x


@_alta("lavavajillas", bucle=True, pico=0.35)
def _lavavajillas(rng: np.random.Generator) -> np.ndarray:
	"""Chorros de agua que barren por dentro, con el zumbido grave de la bomba."""
	d = 3.5
	t = s._t(d)
	x = 0.5 * _motor(rng, d, 50, 120, 700, siseo=0.1)
	x += s._filtro(s._ruido(rng, d), 900, 7000) * (0.45 + 0.55 * np.abs(np.sin(PI2 * (2 / d) * t)))
	return s._bucle(x)


@_alta("microondas", bucle=True, pico=0.35)
def _microondas(rng: np.random.Generator) -> np.ndarray:
	"""Zumbido tenso de microondas con el plato girando."""
	d = 3.0
	t = s._t(d)
	x = _motor(rng, d, 100, 300, 2500, siseo=0.35)
	x += 0.15 * np.sin(PI2 * 1200 * t) * (0.6 + 0.4 * np.sin(PI2 * 100 * t))
	return s._bucle(x)


@_alta("microondas_fin")
def _microondas_fin(rng: np.random.Generator) -> np.ndarray:
	"""Tres pitidos: el microondas ha terminado."""
	x = np.zeros(s._muestras(1.0))
	for k in range(3):
		s._poner(x, _bip(2000, 0.16), k * 0.3)
		s._poner(x, s._aire(rng, 0.04, 0.3, 0.008), k * 0.3)
	return x


@_alta("puerta_mueble")
def _puerta_mueble(rng: np.random.Generator) -> np.ndarray:
	"""Puerta de armario: un chasquido de imán, la bisagra corta y un toque de madera."""
	x = np.zeros(s._muestras(0.55))
	s._poner(x, s._clac(rng, 0.03, 1200, 8000), 0.0, 0.8)
	s._poner(x, s._chirrido(260, 380, 0.25), 0.05, 0.35)
	s._poner(x, s._toc(rng, 180, 0.12, 1500), 0.32, 0.8)
	return x


@_alta("cajon")
def _cajon(rng: np.random.Generator) -> np.ndarray:
	"""Cajón que corre por sus guías y hace tope."""
	d = 0.5
	x = np.zeros(s._muestras(0.65))
	s._poner(x, s._filtro(s._ruido(rng, d), 300, 4500) * s._arco(d, 0.6) * (0.7 + 0.3 * np.sign(s._seno(45, d))), 0.0, 0.7)
	s._poner(x, s._toc(rng, 150, 0.12, 1400), 0.48, 1.0)
	return x


@_alta("puerta_electrodomestico")
def _puerta_electrodomestico(rng: np.random.Generator) -> np.ndarray:
	"""Puerta de frigorífico, horno o lavadora: la goma se despega y la chapa suena hueca."""
	x = np.zeros(s._muestras(0.5))
	s._poner(x, s._filtro(s._ruido(rng, 0.12), 200, 2500) * s._arco(0.12, 0.5), 0.0, 0.8)
	s._poner(x, s._seno(140, 0.2) * s._decae(0.2, 0.05), 0.1, 0.8)
	s._poner(x, s._seno(610, 0.25) * s._decae(0.25, 0.06, 0.001), 0.1, 0.3)
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.1, 0.7)
	return x


@_alta("interruptor", pico=0.5)
def _interruptor(rng: np.random.Generator) -> np.ndarray:
	"""Clic de interruptor o de botón."""
	x = np.zeros(s._muestras(0.12))
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0)
	s._poner(x, s._seno(900, 0.03) * s._decae(0.03, 0.006, 0.0005), 0.0, 0.5)
	s._poner(x, s._clac(rng, 0.02, 2500, 10000), 0.045, 0.5)
	return x


@_alta("cisterna", pico=0.5)
def _cisterna(rng: np.random.Generator) -> np.ndarray:
	"""Cisterna: el pulsador, la descarga de agua y el depósito que vuelve a llenarse."""
	d = 3.2
	t = s._t(d)
	x = np.zeros(s._muestras(d))
	s._poner(x, s._clac(rng, 0.04, 800, 6000), 0.0, 0.8)
	descarga = s._filtro(s._ruido(rng, 1.6), 250, 6500) * s._decae(1.6, 0.55, 0.08)
	s._poner(x, descarga, 0.08, 1.0)
	s._poner(x, s._barrido(260, 90, 1.2) * s._decae(1.2, 0.4, 0.1), 0.2, 0.3)
	llenado = s._filtro(s._ruido(rng, d), 2500, 9000) * np.clip((t - 1.2) / 0.5, 0, 1) * np.clip((d - t) / 0.6, 0, 1)
	return x + 0.25 * llenado


@_alta("sentarse", pico=0.4)
def _sentarse(rng: np.random.Generator) -> np.ndarray:
	"""Sentarse: el cojín cede con un soplo y la estructura cruje un poco."""
	x = np.zeros(s._muestras(0.5))
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 100, 900) * s._decae(0.3, 0.08, 0.02), 0.0, 1.0)
	s._poner(x, s._filtro(s._ruido(rng, 0.35), 2500, 8000) * s._arco(0.35, 1.5), 0.02, 0.35)
	s._poner(x, s._chirrido(180, 140, 0.1), 0.12, 0.15)
	return x


@_alta("piano", pico=0.5)
def _piano(rng: np.random.Generator) -> np.ndarray:
	"""Tres notas de piano que suben (do, mi, sol) y se quedan sonando."""
	x = np.zeros(s._muestras(2.0))
	for k, f in enumerate((261.63, 329.63, 392.0)):
		nota = sum(
			a * s._seno(f * (n + 1) * (1 + 0.0004 * n * n), 1.5) * s._decae(1.5, 0.5 / (1 + 0.35 * n), 0.004)
			for n, a in enumerate((1, 0.6, 0.35, 0.2, 0.12, 0.08))
		)
		s._poner(x, nota, k * 0.22, 0.8)
		# El macillo: sin este golpe de agudos, las notas graves del piano no se podrían situar.
		s._poner(x, s._aire(rng, 0.08, 1.2, 0.02), k * 0.22)
	return x


@_alta("ducha", bucle=True, pico=0.4)
def _ducha(rng: np.random.Generator) -> np.ndarray:
	"""Lluvia de ducha sobre el plato: un siseo denso con gotas que repican."""
	d = 3.0
	x = s._filtro(s._ruido(rng, d), 1800, 11000)
	x += 0.4 * s._filtro(s._ruido(rng, d), 300, 1500)
	x = s._bucle(x)
	for _k in range(60):
		s._poner_ciclico(
			x, s._filtro(s._ruido(rng, 0.012), 2500, 9000) * s._decae(0.012, 0.003, 0.0004), rng.uniform(0, d - 0.3), rng.uniform(0.4, 1.0)
		)
	return x


@_alta("aspiradora")
def _aspiradora(rng: np.random.Generator) -> np.ndarray:
	"""Golpe contra una aspiradora: plástico hueco y el tubo que traquetea."""
	x = np.zeros(s._muestras(0.6))
	s._poner(x, s._golpe(rng, "plastico"), 0.0, 1.0)
	for inicio in (0.12, 0.2, 0.31):
		s._poner(x, s._clac(rng, 0.04, 700, 5000), inicio, 0.5)
		s._poner(x, s._seno(420, 0.06) * s._decae(0.06, 0.015), inicio, 0.3)
	return x


@_alta("juguetes")
def _juguetes(rng: np.random.Generator) -> np.ndarray:
	"""Piezas de plástico que ruedan y un sonajero: has pisado o empujado juguetes."""
	x = np.zeros(s._muestras(0.9))
	for _k in range(9):
		inicio = rng.uniform(0, 0.55)
		f = rng.uniform(500, 1800)
		s._poner(x, s._seno(f, 0.06) * s._decae(0.06, 0.012, 0.001), inicio, rng.uniform(0.4, 1.0))
		s._poner(x, s._clac(rng, 0.03, 1500, 9000), inicio, 0.5)
	s._poner(x, s._destello(rng, 2600, 0.2), 0.35, 0.4)
	return x


# ── Colegio ──────────────────────────────────────────────────────────────────


@_alta("tiza", pico=0.45)
def _tiza(rng: np.random.Generator) -> np.ndarray:
	"""Tiza en la pizarra: tres trazos rasposos y un punto final."""
	x = np.zeros(s._muestras(1.1))
	for inicio, d in ((0.0, 0.22), (0.28, 0.18), (0.52, 0.26)):
		trazo = s._filtro(s._ruido(rng, d), 2200, 9000) * s._arco(d, 0.6) * (0.6 + 0.4 * np.abs(s._seno(38, d)))
		s._poner(x, trazo, inicio)
	s._poner(x, s._toc(rng, 700, 0.05, 3000), 0.88, 0.8)
	return x


@_alta("taquilla")
def _taquilla(rng: np.random.Generator) -> np.ndarray:
	"""Puerta de chapa de una taquilla: pestillo y chapa que vibra."""
	x = np.zeros(s._muestras(0.9))
	s._poner(x, s._clac(rng, 0.04, 1500, 9000), 0.0, 0.9)
	for parcial, peso, cola in ((180, 1.0, 0.16), (455, 0.7, 0.14), (1210, 0.5, 0.1), (2650, 0.35, 0.07), (4100, 0.2, 0.05)):
		s._poner(x, s._seno(parcial, 0.7) * s._decae(0.7, cola, 0.002), 0.07, 0.4 * peso)
	s._poner(x, s._chirrido(520, 760, 0.18), 0.1, 0.2)
	return x


@_alta("balon")
def _balon(rng: np.random.Generator) -> np.ndarray:
	"""Balón que bota tres veces, cada vez más bajo, y roza la red."""
	x = np.zeros(s._muestras(1.3))
	for inicio, fuerza in ((0.0, 1.0), (0.38, 0.7), (0.66, 0.45)):
		s._poner(x, s._seno(110, 0.14) * s._decae(0.14, 0.035, 0.002), inicio, fuerza)
		s._poner(x, s._filtro(s._ruido(rng, 0.05), 600, 6000) * s._decae(0.05, 0.01, 0.0008), inicio, 0.8 * fuerza)
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 3000, 10000) * s._arco(0.3, 1.5), 0.9, 0.45)
	return x


@_alta("pimpon", pico=0.5)
def _pimpon(rng: np.random.Generator) -> np.ndarray:
	"""Pelota de pimpón: pala, mesa, pala, mesa."""
	x = np.zeros(s._muestras(1.0))
	for k, (inicio, f) in enumerate(((0.0, 1500), (0.2, 2300), (0.45, 1450), (0.65, 2350))):
		s._poner(x, s._seno(f, 0.04) * s._decae(0.04, 0.008, 0.0005), inicio, 1.0 if k % 2 == 0 else 0.7)
		s._poner(x, s._clac(rng, 0.02, 2500, 11000), inicio, 0.6)
	return x


@_alta("impresora", pico=0.45)
def _impresora(rng: np.random.Generator) -> np.ndarray:
	"""Impresora: coge el papel, el cabezal va y viene y suelta la hoja."""
	d = 2.4
	t = s._t(d)
	x = np.zeros(s._muestras(d))
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 400, 5000) * s._arco(0.3), 0.0, 0.7)
	pasada = s._filtro(s._ruido(rng, 1.6), 1200, 8000) * (0.4 + 0.6 * np.abs(np.sin(PI2 * 3.0 * s._t(1.6))))
	s._poner(x, pasada * s._arco(1.6, 0.3), 0.35, 0.8)
	x += 0.2 * np.sin(PI2 * 310 * t) * np.clip((t - 0.3) / 0.1, 0, 1) * np.clip((2.0 - t) / 0.1, 0, 1)
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 2000, 9000) * s._arco(0.3, 1.2), 2.05, 0.6)
	return x


@_alta("pandereta", pico=0.5)
def _pandereta(rng: np.random.Generator) -> np.ndarray:
	"""Instrumentos de aula: un golpe de pandereta con sus sonajas y una nota de triángulo."""
	x = np.zeros(s._muestras(1.2))
	s._poner(x, s._toc(rng, 240, 0.1, 2000), 0.0, 0.9)
	sonajas = s._filtro(s._ruido(rng, 0.35), 5000, 14000) * s._decae(0.35, 0.09, 0.002) * (0.6 + 0.4 * np.abs(s._seno(33, 0.35)))
	s._poner(x, sonajas, 0.0, 1.0)
	s._poner(x, s._campana(2650, 0.8, (1, 2.71, 5.2), (1, 0.8, 0.5)), 0.38, 0.5)
	return x


@_alta("chorro", pico=0.45)
def _chorro(rng: np.random.Generator) -> np.ndarray:
	"""Fuente de beber: el botón, un chorro fino de agua y las gotas al soltar."""
	d = 1.6
	x = np.zeros(s._muestras(d + 0.3))
	s._poner(x, s._clac(rng, 0.03, 1000, 7000), 0.0, 0.7)
	chorro = s._filtro(s._ruido(rng, d - 0.2), 1500, 9000) * s._arco(d - 0.2, 0.35)
	borboteo = np.abs(s._filtro(s._ruido(rng, d - 0.2), 6, 30))
	s._poner(x, chorro * (0.6 + 0.4 * borboteo / (float(np.max(borboteo)) or 1.0)), 0.05, 0.9)
	for inicio in (d - 0.05, d + 0.1):
		s._poner(x, s._barrido(1900, 900, 0.05) * s._decae(0.05, 0.012, 0.001), inicio, 0.5)
	return x


@_alta("colchoneta", pico=0.45)
def _colchoneta(rng: np.random.Generator) -> np.ndarray:
	"""Caer sobre una colchoneta: un golpe sordo y el aire que sale."""
	x = np.zeros(s._muestras(0.5))
	s._poner(x, s._seno(70, 0.2) * s._decae(0.2, 0.06, 0.004), 0.0, 1.0)
	s._poner(x, s._filtro(s._ruido(rng, 0.2), 100, 700) * s._decae(0.2, 0.06, 0.004), 0.0, 0.8)
	s._poner(x, s._filtro(s._ruido(rng, 0.4), 2500, 7500) * s._arco(0.4, 2.0), 0.03, 0.4)
	return x


@_alta("teclado", pico=0.4)
def _teclado(rng: np.random.Generator) -> np.ndarray:
	"""Varias teclas de ordenador y la barra espaciadora."""
	x = np.zeros(s._muestras(0.9))
	inicio = 0.0
	for _k in range(7):
		s._poner(x, s._clac(rng, 0.025, 1800, 9000), inicio, rng.uniform(0.6, 1.0))
		s._poner(x, s._seno(rng.uniform(300, 420), 0.03) * s._decae(0.03, 0.008), inicio, 0.3)
		inicio += rng.uniform(0.07, 0.12)
	s._poner(x, s._toc(rng, 210, 0.07, 1800), inicio + 0.03, 0.8)
	return x


# ── Oficina y comercio ───────────────────────────────────────────────────────


@_alta("fotocopiadora", pico=0.45)
def _fotocopiadora(rng: np.random.Generator) -> np.ndarray:
	"""Fotocopiadora: la lámpara barre de un lado a otro con un zumbido que sube y baja, y sale la hoja."""
	d = 2.8
	t = s._t(d)
	barrido = np.sin(PI2 * np.cumsum(180 + 220 * np.sin(np.pi * np.clip(t / 2.0, 0, 1)) ** 2) / s.FRECUENCIA)
	x = 0.5 * barrido * np.clip((2.1 - t) / 0.1, 0, 1)
	x += 0.5 * s._filtro(s._ruido(rng, d), 500, 5000) * (0.5 + 0.5 * np.clip((2.1 - t) / 0.1, 0, 1))
	x += 0.2 * s._siseo(rng, d)
	x *= s._arco(d, 0.25)
	s._poner(x, s._clac(rng, 0.04, 800, 6000), 0.0, 0.9)
	s._poner(x, s._filtro(s._ruido(rng, 0.35), 2000, 9000) * s._arco(0.35, 1.2), 2.25, 0.8)
	return x


@_alta("maquina_cafe", pico=0.5)
def _maquina_cafe(rng: np.random.Generator) -> np.ndarray:
	"""Máquina de café: muele, la bomba aprieta, cae el chorro en el vaso y pita al acabar."""
	d = 3.6
	x = np.zeros(s._muestras(d))
	molinillo = s._filtro(s._ruido(rng, 0.9), 700, 6000) * (0.6 + 0.4 * np.sign(s._seno(55, 0.9))) * s._arco(0.9, 0.3)
	s._poner(x, molinillo, 0.0, 0.9)
	bomba = (0.6 * s._seno(100, 1.6) + 0.3 * s._seno(200, 1.6)) * (0.7 + 0.3 * s._seno(12, 1.6)) * s._arco(1.6, 0.3)
	s._poner(x, bomba, 1.0, 0.6)
	s._poner(x, _agua(rng, 1.5, 1200, 8000, 6) * s._arco(1.5, 0.4), 1.15, 0.6)
	s._poner(x, _bip(1760, 0.2), 3.0, 0.5)
	s._poner(x, s._aire(rng, 0.05, 0.3, 0.008), 3.0)
	return x


@_alta("garrafa", pico=0.45)
def _garrafa(rng: np.random.Generator) -> np.ndarray:
	"""Dispensador de agua: el chorro llena el vaso y la garrafa suelta dos burbujas graves."""
	x = np.zeros(s._muestras(1.9))
	s._poner(x, _agua(rng, 1.2, 900, 7000, 4) * s._arco(1.2, 0.4), 0.0, 0.8)
	for inicio, f in ((0.9, 150), (1.25, 120)):
		s._poner(x, s._barrido(f, f * 1.8, 0.22) * s._decae(0.22, 0.07, 0.01), inicio, 0.9)
		s._poner(x, s._filtro(s._ruido(rng, 0.1), 1500, 6000) * s._decae(0.1, 0.03, 0.002), inicio, 0.4)
	return x


@_alta("caja_registradora", pico=0.5)
def _caja_registradora(rng: np.random.Generator) -> np.ndarray:
	"""Caja registradora: dos pitidos del lector, la campanilla y el cajón que salta."""
	x = np.zeros(s._muestras(1.3))
	for inicio in (0.0, 0.22):
		s._poner(x, _bip(2400, 0.08), inicio, 0.7)
	s._poner(x, s._campana(1760, 0.7, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.5, 0.7)
	s._poner(x, s._filtro(s._ruido(rng, 0.25), 300, 4000) * s._arco(0.25, 0.6), 0.62, 0.5)
	s._poner(x, s._toc(rng, 160, 0.12, 1400), 0.86, 0.9)
	for _k in range(5):
		s._poner(x, s._destello(rng, rng.uniform(3000, 5500), 0.08), rng.uniform(0.88, 1.05), 0.25)
	return x


@_alta("cinta_caja", bucle=True, pico=0.3)
def _cinta_caja(rng: np.random.Generator) -> np.ndarray:
	"""Cinta de la caja en marcha: un rodar continuo de goma con un pitido de lector de vez en cuando."""
	d = 3.0
	t = s._t(d)
	x = _motor(rng, d, 75, 200, 1800, siseo=0.25) * (0.9 + 0.1 * np.sin(PI2 * 6 * t))
	x = s._bucle(x)
	s._poner_ciclico(x, _bip(2400, 0.08), 1.1, 0.7)
	s._poner_ciclico(x, _bip(2400, 0.08), 2.3, 0.7)
	return x


@_alta("torno")
def _torno(rng: np.random.Generator) -> np.ndarray:
	"""Torno de entrada: pitido de billete aceptado, el brazo gira con un carraqueo y hace tope."""
	x = np.zeros(s._muestras(1.1))
	s._poner(x, _bip(1568, 0.12), 0.0, 0.6)
	s._poner(x, s._aire(rng, 0.04, 0.3, 0.008), 0.0)
	for k in range(5):
		s._poner(x, s._clac(rng, 0.03, 900, 7000), 0.28 + k * 0.07, 0.6)
	s._poner(x, s._seno(130, 0.2) * s._decae(0.2, 0.05), 0.68, 1.0)
	s._poner(x, s._seno(870, 0.3) * s._decae(0.3, 0.08, 0.001), 0.68, 0.4)
	s._poner(x, s._clac(rng, 0.04, 1200, 8000), 0.68, 0.9)
	return x


@_alta("teclas_cajero", pico=0.45)
def _teclas_cajero(rng: np.random.Generator) -> np.ndarray:
	"""Cajero o máquina de billetes: cuatro teclas, un pitido de aceptado y el billete que sale."""
	x = np.zeros(s._muestras(1.9))
	for k in range(4):
		s._poner(x, _bip(1200, 0.06), k * 0.16, 0.6)
		s._poner(x, s._clac(rng, 0.02, 1500, 8000), k * 0.16, 0.5)
	s._poner(x, _bip(1760, 0.18), 0.8, 0.7)
	salida = s._filtro(s._ruido(rng, 0.6), 1500, 8000) * (0.5 + 0.5 * np.sign(s._seno(60, 0.6))) * s._arco(0.6, 0.4)
	s._poner(x, salida, 1.1, 0.7)
	return x


@_alta("puerta_giratoria", pico=0.4)
def _puerta_giratoria(rng: np.random.Generator) -> np.ndarray:
	"""Puerta giratoria: las hojas barren el aire y las escobillas rozan el suelo."""
	d = 2.2
	t = s._t(d)
	x = s._filtro(s._ruido(rng, d), 300, 3500) * (0.5 + 0.5 * np.sin(PI2 * 1.4 * t) ** 2)
	x += 0.4 * s._filtro(s._ruido(rng, d), 3000, 8000) * (0.5 + 0.5 * np.cos(PI2 * 1.4 * t) ** 2)
	x += 0.3 * np.sin(PI2 * 60 * t)
	return x * s._arco(d, 0.4)


@_alta("carrito")
def _carrito(rng: np.random.Generator) -> np.ndarray:
	"""Carro de la compra: rejilla de alambre que traquetea y ruedas pequeñas."""
	x = np.zeros(s._muestras(1.0))
	for _k in range(10):
		inicio = rng.uniform(0, 0.6)
		f = rng.uniform(1800, 4200)
		s._poner(x, s._seno(f, 0.12) * s._decae(0.12, 0.03, 0.0008), inicio, rng.uniform(0.3, 0.8))
		s._poner(x, s._clac(rng, 0.02, 2500, 11000), inicio, 0.5)
	s._poner(x, s._filtro(s._ruido(rng, 0.7), 200, 1500) * s._arco(0.7, 0.5) * (0.6 + 0.4 * np.sign(s._seno(18, 0.7))), 0.05, 0.5)
	return x


@_alta("cortina", pico=0.4)
def _cortina(rng: np.random.Generator) -> np.ndarray:
	"""Cortina de probador: las anillas corren por la barra y la tela roza."""
	x = np.zeros(s._muestras(0.8))
	s._poner(x, s._filtro(s._ruido(rng, 0.6), 2000, 8000) * s._arco(0.6, 0.8), 0.0, 0.6)
	for k in range(7):
		s._poner(x, s._seno(rng.uniform(2800, 4200), 0.05) * s._decae(0.05, 0.01, 0.0005), 0.05 + k * 0.07, 0.5)
	return x


@_alta("silla_ruedas", pico=0.4)
def _silla_ruedas(rng: np.random.Generator) -> np.ndarray:
	"""Silla giratoria: las ruedas ruedan un poco y el pistón de gas cede."""
	x = np.zeros(s._muestras(0.8))
	s._poner(x, s._filtro(s._ruido(rng, 0.45), 250, 2500) * s._arco(0.45, 0.6) * (0.6 + 0.4 * np.sign(s._seno(26, 0.45))), 0.0, 0.8)
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 2500, 8000) * s._decae(0.3, 0.09, 0.02), 0.4, 0.6)
	s._poner(x, s._chirrido(300, 230, 0.12), 0.42, 0.2)
	return x


# ── Calle y transporte ───────────────────────────────────────────────────────


@_alta("surtidor", bucle=True, pico=0.4)
def _surtidor(rng: np.random.Generator) -> np.ndarray:
	"""Fuente ornamental: varios chorros que caen sobre el agua del vaso, con borboteo."""
	d = 4.0
	x = _agua(rng, d, 500, 9000, 30)
	x += 0.4 * s._filtro(s._ruido(rng, d), 150, 700) * (0.7 + 0.3 * np.sin(PI2 * 0.5 * s._t(d)))
	return s._bucle(x)


@_alta("hojas", bucle=True, pico=0.25)
def _hojas(rng: np.random.Generator) -> np.ndarray:
	"""Hojas de un árbol movidas por el aire: un siseo que crece y mengua."""
	d = 4.0
	t = s._t(d)
	racha = 0.45 + 0.35 * np.sin(PI2 * t / d) + 0.2 * np.sin(PI2 * 3 * t / d + 1.0)
	x = s._filtro(s._ruido(rng, d), 2500, 10000) * racha
	x += 0.3 * s._filtro(s._ruido(rng, d), 600, 2500) * racha**2
	return s._bucle(x)


@_alta("tapa_contenedor")
def _tapa_contenedor(rng: np.random.Generator) -> np.ndarray:
	"""Tapa de contenedor que cae: plástico grande y hueco, con un rebote."""
	x = np.zeros(s._muestras(0.8))
	for inicio, fuerza in ((0.0, 1.0), (0.22, 0.4)):
		s._poner(x, s._seno(95, 0.3) * s._decae(0.3, 0.08, 0.002), inicio, fuerza)
		s._poner(x, s._seno(310, 0.2) * s._decae(0.2, 0.05, 0.002), inicio, 0.5 * fuerza)
		s._poner(x, s._filtro(s._ruido(rng, 0.08), 500, 6000) * s._decae(0.08, 0.015, 0.0008), inicio, 0.9 * fuerza)
	return x


@_alta("vidrio", pico=0.5)
def _vidrio(rng: np.random.Generator) -> np.ndarray:
	"""Botella que cae en el contenedor de vidrio: golpe hueco y cristales."""
	x = np.zeros(s._muestras(0.9))
	s._poner(x, s._seno(120, 0.2) * s._decae(0.2, 0.05), 0.0, 0.8)
	for _k in range(7):
		s._poner(x, s._destello(rng, rng.uniform(2200, 6500), 0.25), rng.uniform(0.02, 0.35), rng.uniform(0.3, 0.9))
	return x


@_alta("trampilla_buzon")
def _trampilla_buzon(rng: np.random.Generator) -> np.ndarray:
	"""Trampilla metálica de un buzón: se levanta con un chirrido y cae con un golpe de chapa."""
	x = np.zeros(s._muestras(0.9))
	s._poner(x, s._chirrido(700, 950, 0.18), 0.0, 0.3)
	for parcial, peso, cola in ((240, 1.0, 0.14), (690, 0.7, 0.12), (1730, 0.5, 0.09), (3900, 0.3, 0.06)):
		s._poner(x, s._seno(parcial, 0.6) * s._decae(0.6, cola, 0.001), 0.25, 0.45 * peso)
	s._poner(x, s._clac(rng, 0.04, 1500, 9000), 0.25, 1.0)
	return x


@_alta("bip_validacion", pico=0.45)
def _bip_validacion(rng: np.random.Generator) -> np.ndarray:
	"""Dos pitidos, el segundo más agudo: billete, tarjeta o pago aceptado."""
	x = np.zeros(s._muestras(0.5))
	s._poner(x, _bip(1319, 0.1), 0.0)
	s._poner(x, _bip(1976, 0.16), 0.13)
	s._poner(x, s._aire(rng, 0.04, 0.3, 0.008), 0.0)
	return x


@_alta("zumbido_recarga", bucle=True, pico=0.25)
def _zumbido_recarga(rng: np.random.Generator) -> np.ndarray:
	"""Punto de recarga o armario eléctrico: zumbido de transformador con un silbido fino."""
	d = 3.0
	t = s._t(d)
	x = _motor(rng, d, 100, 400, 2000, siseo=0.2)
	x += 0.1 * np.sin(PI2 * 5200 * t) * (0.6 + 0.4 * np.sin(PI2 * 100 * t))
	return s._bucle(x)


@_alta("timbre_bici", pico=0.5)
def _timbre_bici(rng: np.random.Generator) -> np.ndarray:
	"""Timbre de bicicleta: ring, ring."""
	x = np.zeros(s._muestras(1.0))
	for inicio in (0.0, 0.28):
		s._poner(x, s._campana(2350, 0.7, (1, 2.4, 3.9, 5.3), (1, 0.8, 0.5, 0.3)), inicio, 0.8)
		s._poner(x, s._clac(rng, 0.02, 2500, 10000), inicio, 0.5)
	return x


@_alta("megafonia", pico=0.45)
def _megafonia(rng: np.random.Generator) -> np.ndarray:
	"""Aviso de megafonía o de panel informativo: tres notas que bajan, din, don, dan."""
	x = np.zeros(s._muestras(1.8))
	for k, f in enumerate((1046.5, 830.6, 659.25)):
		s._poner(x, s._campana(f, 1.1, (1, 2.0, 3.0, 4.0), (1, 0.6, 0.4, 0.25)), k * 0.32, 0.8)
		s._poner(x, s._aire(rng, 0.04, 0.25, 0.008), k * 0.32)
	return x


@_alta("interfono", pico=0.45)
def _interfono(rng: np.random.Generator) -> np.ndarray:
	"""Interfono de ayuda: el botón y dos tonos de llamada."""
	x = np.zeros(s._muestras(1.9))
	s._poner(x, s._clac(rng, 0.03, 1200, 8000), 0.0, 0.8)
	for inicio in (0.2, 1.0):
		tono = (s._seno(440, 0.55) + s._seno(480, 0.55)) * s._arco(0.55, 0.2)
		s._poner(x, tono, inicio, 0.5)
		s._poner(x, s._siseo(rng, 0.55, 3000, 8000) * s._arco(0.55, 0.2), inicio, 0.35)
		s._poner(x, s._aire(rng, 0.05, 0.5, 0.01), inicio)
	return x


@_alta("puerta_cristal", pico=0.45)
def _puerta_cristal(rng: np.random.Generator) -> np.ndarray:
	"""Puerta corredera de cristal o de terraza: rueda por su carril y hace tope."""
	d = 0.8
	x = np.zeros(s._muestras(1.0))
	s._poner(x, s._filtro(s._ruido(rng, d), 500, 5500) * s._arco(d, 0.5), 0.0, 0.7)
	s._poner(x, 0.3 * s._barrido(150, 110, d) * s._arco(d), 0.0)
	s._poner(x, s._seno(2100, 0.25) * s._decae(0.25, 0.06, 0.001), d - 0.02, 0.3)
	s._poner(x, s._toc(rng, 170, 0.1, 1500), d - 0.02, 0.9)
	return x


@_alta("valla_obra")
def _valla_obra(rng: np.random.Generator) -> np.ndarray:
	"""Valla de obra: malla y tubo de metal que se sacuden y tintinean."""
	x = np.zeros(s._muestras(1.0))
	for parcial, peso, cola in ((205, 1.0, 0.2), (540, 0.8, 0.18), (1320, 0.6, 0.14), (2480, 0.5, 0.1), (3950, 0.35, 0.08)):
		s._poner(x, s._seno(parcial, 0.9) * s._decae(0.9, cola, 0.001) * (0.7 + 0.3 * s._seno(23, 0.9)), 0.0, 0.4 * peso)
	for inicio in (0.0, 0.09, 0.2, 0.36):
		s._poner(x, s._clac(rng, 0.03, 1800, 10000), inicio, 0.7)
	return x


# ── Juego ────────────────────────────────────────────────────────────────────


@_alta("cofre_abrir", pico=0.5)
def _cofre_abrir(rng: np.random.Generator) -> np.ndarray:
	"""Cofre que se abre: el cierre, la tapa que cruje subiendo de tono y un brillo dentro."""
	x = np.zeros(s._muestras(1.6))
	s._poner(x, s._clac(rng, 0.05, 900, 7000), 0.0, 0.9)
	s._poner(x, s._seno(210, 0.08) * s._decae(0.08, 0.02), 0.0, 0.6)
	s._poner(x, s._chirrido(120, 420, 0.7), 0.12, 0.5)
	for k, f in enumerate((1568, 2093, 2637, 3136)):
		s._poner(x, s._destello(rng, f, 0.3), 0.85 + k * 0.09, 0.5)
	return x


@_alta("cofre_cerrar", pico=0.5)
def _cofre_cerrar(rng: np.random.Generator) -> np.ndarray:
	"""Cofre que se cierra: la tapa baja crujiendo y cae con un golpe de madera y herrajes."""
	x = np.zeros(s._muestras(0.9))
	s._poner(x, s._chirrido(380, 150, 0.4), 0.0, 0.45)
	s._poner(x, s._toc(rng, 110, 0.25, 1300), 0.42, 1.0)
	s._poner(x, s._seno(1450, 0.3) * s._decae(0.3, 0.07, 0.001), 0.43, 0.25)
	s._poner(x, s._clac(rng, 0.04, 1500, 9000), 0.5, 0.7)
	return x


@_alta("muelle", pico=0.5)
def _muelle(rng: np.random.Generator) -> np.ndarray:
	"""Caja sorpresa: la tapa salta y un muelle hace boing, boing, cada vez menos."""
	d = 1.1
	t = s._t(d)
	f = 180 + 260 * np.exp(-t / 0.25) * (0.5 + 0.5 * np.cos(PI2 * 7 * t))
	x = np.sin(PI2 * np.cumsum(f) / s.FRECUENCIA) * s._decae(d, 0.3, 0.003)
	x += 0.4 * np.sin(2 * PI2 * np.cumsum(f) / s.FRECUENCIA) * s._decae(d, 0.2, 0.003)
	s._poner(x, s._clac(rng, 0.04, 1000, 9000), 0.0, 0.9)
	s._poner(x, s._destello(rng, 3136, 0.2), 0.05, 0.4)
	return x


@_alta("monedas", pico=0.5)
def _monedas(rng: np.random.Generator) -> np.ndarray:
	"""Monedas que caen dentro de una hucha y tintinean."""
	x = np.zeros(s._muestras(1.0))
	for k in range(6):
		inicio = k * 0.08 + rng.uniform(0, 0.03)
		s._poner(x, s._destello(rng, rng.uniform(3200, 6200), 0.22), inicio, rng.uniform(0.5, 1.0))
	s._poner(x, s._seno(430, 0.12) * s._decae(0.12, 0.03), 0.0, 0.3)
	return x


@_alta("campana", pico=0.5)
def _campana(rng: np.random.Generator) -> np.ndarray:
	"""Una campana de bronce: el golpe del badajo y una cola larga."""
	x = np.zeros(s._muestras(2.6))
	s._poner(x, s._campana(523.25, 2.5), 0.0)
	s._poner(x, s._clac(rng, 0.03, 1500, 9000), 0.0, 0.8)
	s._poner(x, s._aire(rng, 0.1, 0.9, 0.025), 0.0)
	return x


@_alta("xilofono", pico=0.5)
def _xilofono(rng: np.random.Generator) -> np.ndarray:
	"""Xilófono gigante: cinco láminas de madera que suben la escala."""
	x = np.zeros(s._muestras(1.5))
	for k, f in enumerate((523.25, 587.33, 659.25, 783.99, 880.0)):
		s._poner(x, s._nota(f, 0.6, 0.16, (1, 0.0, 0.0, 0.35, 0.0, 0.0, 0.0, 0.0, 0.0, 0.12)), k * 0.17, 0.8)
		s._poner(x, s._clac(rng, 0.02, 2000, 9000), k * 0.17, 0.5)
	return x


@_alta("tambor", pico=0.55)
def _tambor(rng: np.random.Generator) -> np.ndarray:
	"""Tambor: pom, pom, porrompom."""
	x = np.zeros(s._muestras(1.2))
	for inicio, fuerza in ((0.0, 1.0), (0.25, 0.9), (0.5, 0.7), (0.62, 0.7), (0.75, 1.0)):
		t = s._t(0.3)
		parche = np.sin(PI2 * np.cumsum(95 * (1 + 0.5 * np.exp(-t / 0.02))) / s.FRECUENCIA) * s._decae(0.3, 0.08, 0.002)
		s._poner(x, parche, inicio, fuerza)
		s._poner(x, s._filtro(s._ruido(rng, 0.08), 2000, 10000) * s._decae(0.08, 0.02, 0.0008), inicio, 1.0 * fuerza)
	return x


@_alta("baliza_musical", bucle=True, pico=0.35)
def _baliza_musical(rng: np.random.Generator) -> np.ndarray:
	"""Baliza musical: una melodía corta de caja de música que se repite sin costura."""
	paso = 0.3
	notas = (659.25, 783.99, 1046.5, 783.99, 880.0, 1046.5, 1318.5, 0, 1174.7, 1046.5, 880.0, 783.99)
	x = np.zeros(s._muestras(paso * len(notas)))
	for k, f in enumerate(notas):
		if f:
			s._poner_ciclico(x, s._campana(f, 0.9, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), k * paso, 0.7)
			s._poner_ciclico(x, s._aire(rng, 0.04, 0.35, 0.008), k * paso)
	return x


@_alta("arbol_magico", bucle=True, pico=0.3)
def _arbol_magico(rng: np.random.Generator) -> np.ndarray:
	"""Árbol mágico: hojas que susurran y campanillas de cristal aquí y allá."""
	d = 5.0
	t = s._t(d)
	x = 0.5 * s._filtro(s._ruido(rng, d), 2500, 9000) * (0.5 + 0.5 * np.sin(PI2 * t / d) ** 2)
	x = s._bucle(x, 400.0)
	escala = (1318.5, 1568.0, 1760.0, 2093.0, 2637.0)
	for _k in range(11):
		s._poner_ciclico(x, s._destello(rng, float(rng.choice(escala)), 0.5), rng.uniform(0, len(x) / s.FRECUENCIA), rng.uniform(0.3, 0.7))
	return x


@_alta("fuente_deseos", bucle=True, pico=0.35)
def _fuente_deseos(rng: np.random.Generator) -> np.ndarray:
	"""Fuente de los deseos: un hilo de agua y, de vez en cuando, un brillo."""
	d = 4.0
	x = s._bucle(_agua(rng, d, 900, 8000, 14))
	for inicio in (0.9, 2.8):
		for k, f in enumerate((2093, 2637, 3136)):
			s._poner_ciclico(x, s._destello(rng, f, 0.3), inicio + k * 0.08, 0.35)
	return x


@_alta("deseo", pico=0.5)
def _deseo(rng: np.random.Generator) -> np.ndarray:
	"""Una moneda cae al agua con un «plop» y sube un arpegio brillante."""
	x = np.zeros(s._muestras(1.5))
	s._poner(x, s._destello(rng, 4200, 0.12), 0.0, 0.6)
	s._poner(x, s._barrido(700, 220, 0.12) * s._decae(0.12, 0.035, 0.002), 0.18, 0.9)
	s._poner(x, s._filtro(s._ruido(rng, 0.2), 800, 6000) * s._decae(0.2, 0.05, 0.004), 0.2, 0.5)
	for k, f in enumerate((1046.5, 1318.5, 1568.0, 2093.0, 2637.0)):
		s._poner(x, s._destello(rng, f, 0.5), 0.45 + k * 0.1, 0.5)
	return x


@_alta("globo", pico=0.45)
def _globo(rng: np.random.Generator) -> np.ndarray:
	"""Globo: la goma chirría al rozarlo y rebota hueco."""
	x = np.zeros(s._muestras(0.7))
	d = 0.3
	t = s._t(d)
	chirrido = np.sin(PI2 * np.cumsum(900 + 500 * np.sin(PI2 * 9 * t)) / s.FRECUENCIA) * s._arco(d)
	s._poner(x, chirrido, 0.0, 0.5)
	s._poner(x, s._seno(260, 0.25) * s._decae(0.25, 0.07, 0.003), 0.3, 0.9)
	s._poner(x, s._filtro(s._ruido(rng, 0.08), 2500, 10000) * s._decae(0.08, 0.02, 0.0008), 0.3, 1.2)
	s._poner(x, s._filtro(s._ruido(rng, d), 3000, 9000) * s._arco(d), 0.0, 0.25)
	return x


@_alta("globo_explota", pico=0.6)
def _globo_explota(rng: np.random.Generator) -> np.ndarray:
	"""El globo explota: un estallido seco, no muy fuerte."""
	x = np.zeros(s._muestras(0.4))
	s._poner(x, s._filtro(s._ruido(rng, 0.3), 300, 12000) * s._decae(0.3, 0.03, 0.0005), 0.0)
	s._poner(x, s._seno(160, 0.12) * s._decae(0.12, 0.03), 0.0, 0.6)
	return x


@_alta("cremallera", pico=0.4)
def _cremallera(rng: np.random.Generator) -> np.ndarray:
	"""Cremallera de mochila o de tienda de campaña: un zumbido de dientes que sube de tono."""
	d = 0.7
	t = s._t(d)
	dientes = np.sign(np.sin(PI2 * np.cumsum(160 + 420 * t / d) / s.FRECUENCIA))
	x = s._filtro(s._ruido(rng, d), 1800, 9000) * (0.55 + 0.45 * dientes) * s._arco(d, 0.5)
	return x


@_alta("caja_fuerte", pico=0.5)
def _caja_fuerte(rng: np.random.Generator) -> np.ndarray:
	"""Caja fuerte: la rueda gira con clics finos, salta el cerrojo y la puerta pesada cede."""
	x = np.zeros(s._muestras(1.7))
	for k in range(9):
		s._poner(x, s._clac(rng, 0.015, 3000, 11000), k * 0.07, 0.5)
	s._poner(x, s._seno(150, 0.2) * s._decae(0.2, 0.05), 0.78, 1.0)
	s._poner(x, s._clac(rng, 0.05, 800, 7000), 0.78, 1.0)
	s._poner(x, s._chirrido(90, 140, 0.5), 1.0, 0.35)
	s._poner(x, s._seno(620, 0.5) * s._decae(0.5, 0.12, 0.002), 0.78, 0.25)
	return x


@_alta("llaves", pico=0.5)
def _llaves(rng: np.random.Generator) -> np.ndarray:
	"""Un manojo de llaves que tintinea."""
	x = np.zeros(s._muestras(0.9))
	for _k in range(12):
		s._poner(x, s._destello(rng, rng.uniform(3500, 8000), 0.15), rng.uniform(0, 0.55), rng.uniform(0.3, 1.0))
	return x


@_alta("papel", pico=0.4)
def _papel(rng: np.random.Generator) -> np.ndarray:
	"""Papel o cartón que cruje: un paquete, un sobre que cae en el buzón."""
	d = 0.7
	x = s._filtro(s._ruido(rng, d), 1500, 10000)
	arrugas = np.abs(s._filtro(s._ruido(rng, d), 8, 60))
	x *= (arrugas / (float(np.max(arrugas)) or 1.0)) ** 2 * s._arco(d, 0.5)
	s._poner(x, s._toc(rng, 200, 0.08, 1500), 0.5, 0.25)
	return x


@_alta("magia", pico=0.45)
def _magia(rng: np.random.Generator) -> np.ndarray:
	"""Un barrido de campanillas que sube: algo mágico acaba de pasar."""
	x = np.zeros(s._muestras(1.3))
	for k in range(10):
		f = 1046.5 * 2 ** (k * 2 / 12)
		s._poner(x, s._destello(rng, f, 0.45), k * 0.06, 0.4 + 0.04 * k)
	s._poner(x, s._filtro(s._ruido(rng, 0.8), 5000, 13000) * s._arco(0.8, 2.0), 0.0, 0.2)
	return x


@_alta("bandera", bucle=True, pico=0.25)
def _bandera(rng: np.random.Generator) -> np.ndarray:
	"""Bandera que ondea: la tela chasquea con el viento."""
	d = 3.0
	t = s._t(d)
	x = s._filtro(s._ruido(rng, d), 400, 6000) * (0.3 + 0.7 * np.abs(np.sin(PI2 * 2.0 * t)) ** 3)
	x += 0.3 * s._filtro(s._ruido(rng, d), 3000, 9000)
	return s._bucle(x)
