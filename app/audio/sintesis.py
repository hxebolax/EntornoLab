"""Síntesis con numpy de todos los sonidos de serie, y lectura y escritura de audio.

Los sonidos del paquete por defecto (``data/sounds/por_defecto``) no son
grabaciones: se generan aquí, con ``tools/sintetizar_sonidos.py``, y se
distribuyen ya escritos (FLAC a 44,1 kHz). Los demás paquetes de sonidos
(``data/sounds/<paquete>``) usan los mismos nombres; ver ``app/audio/banco.py``.
Así no hay licencias de terceros que vigilar, todos comparten nivel y estilo, y
cualquiera puede sustituir uno dejando su propia grabación con el mismo nombre.

Decisiones que conviene conocer antes de tocar nada:

- **Lo que hay que localizar lleva agudos.** El oído distingue delante de
  detrás (y arriba de abajo) por cómo la oreja cambia el sonido por encima de
  unos 3 kHz. Un tono puro de 800 Hz suena igual delante que detrás con
  cualquier perfil de cabeza. Por eso las balizas, las sondas, los premios y
  las fuentes graves (el frigorífico) llevan un chasquido o un siseo de 2 a
  14 kHz (``_aire``). Lo vigila ``tests/test_audio_sintesis.py``.
- **Mono lo que se sitúa.** El motor coloca en el espacio sonidos de un canal;
  solo los ambientes de fondo, que no vienen de ningún punto, son estéreo.
- **Deterministas.** Cada sonido usa una semilla derivada de su nombre: generar
  dos veces da exactamente las mismas muestras, y cambiar un sonido no altera
  los demás.
- **Niveles prudentes.** Nadie debe llevarse un susto con auriculares: el pico
  de cada sonido está fijado en el catálogo (0,8 como mucho; los ambientes,
  bastante menos) y todos empiezan y acaban sin clic.

El catálogo (``CATALOGO``) da a cada sonido su nombre hablado, su explicación y
su grupo: de ahí sale ``catalogo.json``, que alimenta el menú «Aprender los
sonidos». Los textos están en español (idioma de origen), marcados con ``N_``;
quien los muestra los traduce con ``DefSonido.nombre_visible()``.

Las utilidades de síntesis y de remuestreo proceden de ``sintesis.py`` de
Puerto Bravo (JuegoGTA) y de ``tools/sintetizar_sonidos.py`` de Reconocedor de
Ciudades, del mismo autor, adaptadas al estilo de este proyecto.
"""

from __future__ import annotations

import fnmatch
import json
import logging
import math
import os
import zlib
from collections.abc import Callable
from dataclasses import dataclass
from functools import partial
from pathlib import Path

import numpy as np

from app.core import i18n
from app.core.i18n import N_

log = logging.getLogger(__name__)

FRECUENCIA = 44100
PI2 = 2.0 * np.pi

# Formato de catalogo.json; súbase si cambia su estructura.
FORMATO_CATALOGO = 1
# Extensión → (formato de libsndfile, subtipo). FLAC no pierde nada y ocupa menos de la mitad que WAV.
FORMATOS_AUDIO: dict[str, tuple[str, str | None]] = {
	".flac": ("FLAC", "PCM_16"),
	".wav": ("WAV", "PCM_16"),
	".ogg": ("OGG", "VORBIS"),
}
# En este orden se busca un sonido en disco: manda el que no es FLAC, que es el que alguien ha puesto a mano.
EXTENSIONES = (".wav", ".ogg", ".flac")
# Por encima de esta frecuencia están las pistas con las que el oído sitúa un sonido delante o detrás.
CORTE_AGUDOS = 3000.0

SUELOS = (
	"baldosa",
	"madera",
	"moqueta",
	"alfombra",
	"hormigon",
	"asfalto",
	"acera",
	"adoquin",
	"tierra",
	"hierba",
	"grava",
	"metal",
	"arena",
	"agua",
	"tactil_botones",
	"tactil_rayas",
)
MATERIALES = ("ladrillo", "madera", "metal", "cristal", "plastico", "tela", "piedra")
PIES = ("izq", "der")
VARIANTES_PASO = 3
PLANTAS_ASCENSOR = 10

GRUPOS: list[tuple[str, str]] = [
	("orientacion", N_("Orientación: balizas, bastón sonoro, brújula y eco")),
	("movimiento", N_("Tus pasos sobre cada suelo")),
	("choques", N_("Choques y roces con paredes y objetos")),
	("puertas", N_("Puertas, escaleras, rampas y ascensor")),
	("premios", N_("Premios, logros y pistas")),
	("calle", N_("La calle: semáforos, tráfico y bordillos")),
	("fuentes", N_("Cosas que suenan en los lugares")),
	("ambientes", N_("Ambientes de fondo")),
	("interfaz", N_("Menús")),
]


# ── Catálogo ─────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class DefSonido:
	"""Ficha de un sonido de serie: cómo se llama en voz alta, qué significa y cómo se usa.

	``nombre`` y ``explicacion`` son textos en español marcados para traducir;
	pueden llevar huecos (``{suelo}``) que se rellenan con ``argumentos``, cuyos
	valores también se traducen. Así una sola frase vale para toda una familia.
	"""

	clave: str
	nombre: str
	explicacion: str
	grupo: str
	bucle: bool = False
	posicionable: bool = True
	pico: float = 0.6
	argumentos: tuple[tuple[str, str], ...] = ()

	def _rellenar(self, texto: str, traducir: Callable[[str], str]) -> str:
		return traducir(texto).format(**{clave: traducir(valor) for clave, valor in self.argumentos})

	def nombre_visible(self) -> str:
		"""El nombre en el idioma activo, para decirlo o mostrarlo."""
		return self._rellenar(self.nombre, i18n._)

	def explicacion_visible(self) -> str:
		"""La explicación en el idioma activo."""
		return self._rellenar(self.explicacion, i18n._)

	def nombre_origen(self) -> str:
		"""El nombre en español, sin traducir (para ``catalogo.json``)."""
		return self._rellenar(self.nombre, str)

	def explicacion_origen(self) -> str:
		"""La explicación en español, sin traducir (para ``catalogo.json``)."""
		return self._rellenar(self.explicacion, str)


Generador = Callable[[np.random.Generator], np.ndarray]

CATALOGO: dict[str, DefSonido] = {}
_GENERADORES: dict[str, Generador] = {}


def _alta(
	clave: str,
	nombre: str,
	explicacion: str,
	grupo: str,
	hacer: Generador,
	*,
	bucle: bool = False,
	posicionable: bool = True,
	pico: float = 0.6,
	**argumentos: str,
) -> None:
	"""Apunta un sonido en el catálogo junto con la función que lo sintetiza."""
	if clave in CATALOGO:
		raise ValueError(f"Sonido repetido en el catálogo: {clave}")
	CATALOGO[clave] = DefSonido(clave, nombre, explicacion, grupo, bucle, posicionable, pico, tuple(argumentos.items()))
	_GENERADORES[clave] = hacer


# ── Utilidades de síntesis ───────────────────────────────────────────────────


def _muestras(segundos: float) -> int:
	return int(FRECUENCIA * segundos)


def _t(segundos: float) -> np.ndarray:
	return np.arange(_muestras(segundos)) / FRECUENCIA


def _ruido(rng: np.random.Generator, segundos: float) -> np.ndarray:
	return rng.standard_normal(_muestras(segundos))


def _filtro(x: np.ndarray, lo: float | None = None, hi: float | None = None, orden: int = 4) -> np.ndarray:
	"""Paso banda suave en el dominio de la frecuencia (sin transitorios ni dependencias)."""
	if len(x) < 8:
		return x.copy()
	espectro = np.fft.rfft(x, axis=0)
	f = np.fft.rfftfreq(len(x), 1.0 / FRECUENCIA)
	g = np.ones_like(f)
	if hi:
		g *= 1.0 / (1.0 + (f / hi) ** orden)
	if lo:
		r = (f / lo) ** orden
		g *= r / (1.0 + r)
	if x.ndim == 2:
		g = g[:, None]
	return np.fft.irfft(espectro * g, len(x), axis=0)


def _decae(segundos: float, tau: float, ataque: float = 0.003) -> np.ndarray:
	"""Envolvente de golpe: sube en ``ataque`` y cae con constante ``tau``."""
	t = _t(segundos)
	return np.minimum(1.0, t / max(ataque, 1e-5)) * np.exp(-t / max(tau, 1e-4))


def _arco(segundos: float, potencia: float = 2.0) -> np.ndarray:
	"""Envolvente que entra y sale suave (medio seno elevado)."""
	n = _muestras(segundos)
	return np.sin(np.pi * np.arange(n) / max(1, n)) ** potencia


def _bordes(x: np.ndarray, entrada_ms: float = 2.0, salida_ms: float = 8.0) -> np.ndarray:
	"""Fundidos mínimos al principio y al final para que el sonido no haga clic."""
	x = x.copy()
	ne = min(_muestras(entrada_ms / 1000.0), len(x) // 2)
	ns = min(_muestras(salida_ms / 1000.0), len(x) // 2)
	forma = (-1,) + (1,) * (x.ndim - 1)
	if ne > 0:
		x[:ne] *= np.linspace(0.0, 1.0, ne).reshape(forma)
	if ns > 0:
		x[-ns:] *= np.linspace(1.0, 0.0, ns).reshape(forma)
	return x


def _bucle(x: np.ndarray, ms: float = 250.0) -> np.ndarray:
	"""Funde el final con el principio para que el bucle no tenga costura.

	La última muestra del resultado es la anterior a la que ahora es la
	primera en la señal original: al repetirse, la onda sigue sin salto.
	"""
	n = min(_muestras(ms / 1000.0), len(x) // 3)
	r = np.linspace(0.0, 1.0, n).reshape((-1,) + (1,) * (x.ndim - 1))
	cuerpo = x[:-n].copy()
	cuerpo[:n] = cuerpo[:n] * r + x[-n:] * (1.0 - r)
	return cuerpo


def _seno(f: float, segundos: float, fase: float = 0.0) -> np.ndarray:
	return np.sin(PI2 * f * _t(segundos) + fase)


def _barrido(f0: float, f1: float, segundos: float, forma: str = "seno") -> np.ndarray:
	"""Tono que va de ``f0`` a ``f1``: seno, sierra o cuadrada."""
	t = _t(segundos)
	f = f0 + (f1 - f0) * (t / segundos)
	fase = PI2 * np.cumsum(f) / FRECUENCIA
	if forma == "sierra":
		return 2.0 * ((fase / PI2) % 1.0) - 1.0
	if forma == "cuadrada":
		return np.sign(np.sin(fase))
	return np.sin(fase)


def _nota(f: float, segundos: float, tau: float = 0.25, arm: tuple[float, ...] = (1, 0.4, 0.2)) -> np.ndarray:
	"""Nota con armónicos que decae, como una marimba o una campanilla."""
	x = sum(a * _seno(f * (k + 1), segundos) for k, a in enumerate(arm))
	return x * _decae(segundos, tau)


def _poner(dest: np.ndarray, x: np.ndarray, t0: float, g: float = 1.0) -> None:
	"""Suma ``x`` en ``dest`` a partir del segundo ``t0``; lo que no cabe se pierde."""
	i = int(t0 * FRECUENCIA)
	if i >= len(dest) or i < 0:
		return
	n = min(len(x), len(dest) - i)
	dest[i : i + n] += x[:n] * g


def _poner_ciclico(dest: np.ndarray, x: np.ndarray, t0: float, g: float = 1.0) -> None:
	"""Como ``_poner``, pero lo que se sale por el final entra por el principio.

	Con esto un bucle hecho de sucesos (gotas, campanadas, pájaros) empalma
	solo: la cola de lo último que suena ya está mezclada al empezar.
	"""
	indices = (int(t0 * FRECUENCIA) + np.arange(len(x))) % len(dest)
	np.add.at(dest, indices, x * g)


def _sec(
	notas: tuple[float, ...] | list[float],
	paso: float,
	d_nota: float,
	tau: float = 0.2,
	arm: tuple[float, ...] = (1, 0.4, 0.2),
) -> np.ndarray:
	"""Melodía corta: una nota cada ``paso`` segundos (0 es silencio)."""
	salida = np.zeros(_muestras(paso * len(notas) + d_nota))
	for k, f in enumerate(notas):
		if f:
			_poner(salida, _nota(f, d_nota, tau, arm), k * paso)
	return salida


def _campana(
	f: float,
	segundos: float,
	parciales: tuple[float, ...] = (1, 2.0, 2.76, 5.4, 8.93),
	caidas: tuple[float, ...] = (1, 0.7, 0.5, 0.3, 0.2),
) -> np.ndarray:
	"""Campana: parciales inarmónicos, los agudos se apagan antes."""
	s = np.zeros(_muestras(segundos))
	for p, c in zip(parciales, caidas, strict=False):
		if f * p < FRECUENCIA * 0.45:
			s += _seno(f * p, segundos) * _decae(segundos, segundos * c / 2.5, 0.002) / p**0.5
	return s


def _toc(rng: np.random.Generator, f: float, segundos: float, brillo: float = 1500.0) -> np.ndarray:
	"""Golpe de madera o sordo: tono grave que cae de tono más un clic filtrado."""
	t = _t(segundos)
	cuerpo = np.sin(PI2 * np.cumsum(f * (1.0 + 0.6 * np.exp(-t / 0.01))) / FRECUENCIA) * _decae(segundos, segundos / 4.0)
	clic = _filtro(_ruido(rng, segundos), brillo * 0.5, brillo * 2.0) * _decae(segundos, 0.004, 0.001)
	return cuerpo + 0.5 * clic


def _aire(rng: np.random.Generator, segundos: float, volumen: float = 0.5, tau: float = 0.012) -> np.ndarray:
	"""Chasquido corto de agudos (2 a 14 kHz) para el ataque de un sonido.

	Es la lección de Reconocedor de Ciudades: un tono de menos de 2 kHz apenas
	lleva las pistas con las que la oreja distingue delante de detrás, y con
	el sonido binaural se confunde. Con este chasquido se sitúa bien.
	"""
	return _filtro(_ruido(rng, segundos), 2000, 14000) * _decae(segundos, tau, 0.001) * volumen


def _con_aire(rng: np.random.Generator, x: np.ndarray, volumen: float = 0.7, tau: float = 0.015) -> np.ndarray:
	"""``x`` (llevado a pico 1) con el chasquido de agudos al empezar."""
	maximo = float(np.max(np.abs(x))) or 1.0
	return x / maximo + _aire(rng, len(x) / FRECUENCIA, volumen, tau)[: len(x)]


def _siseo(rng: np.random.Generator, segundos: float, lo: float = 3000, hi: float = 9000) -> np.ndarray:
	"""Ruido continuo de agudos, para que una fuente grave en bucle se pueda situar."""
	return _filtro(_ruido(rng, segundos), lo, hi)


def _vocal(f0: float, f1: float, segundos: float, formantes: tuple[float, ...], tau: float) -> np.ndarray:
	"""Sílaba sin palabras: diente de sierra pasado por dos formantes."""
	x = _barrido(f0, f1, segundos, "sierra")
	y = sum(_filtro(x, fo * 0.8, fo * 1.25, 6) for fo in formantes)
	return y * _decae(segundos, tau, 0.02)


def _estereo(izquierda: np.ndarray, derecha: np.ndarray) -> np.ndarray:
	n = min(len(izquierda), len(derecha))
	return np.stack([izquierda[:n], derecha[:n]], axis=1)


# ── Pasos ────────────────────────────────────────────────────────────────────

# suelo: (grave, agudo, segundos, caída, pico, nombre hablado, cómo suena)
_PASOS: dict[str, tuple[float, float, float, float, float, str, str]] = {
	"baldosa": (900, 5500, 0.09, 0.016, 0.50, N_("baldosa"), N_("Un toque seco y claro.")),
	"madera": (350, 3200, 0.14, 0.035, 0.55, N_("madera"), N_("Un golpe hueco, con algo de eco de tarima.")),
	"moqueta": (200, 2600, 0.13, 0.040, 0.36, N_("moqueta"), N_("Muy apagado y corto.")),
	"alfombra": (150, 2000, 0.15, 0.050, 0.34, N_("alfombra"), N_("Apagado y blando, más grave que la moqueta.")),
	"hormigon": (400, 3600, 0.10, 0.022, 0.48, N_("hormigón"), N_("Seco y algo sordo.")),
	"asfalto": (300, 2800, 0.11, 0.028, 0.48, N_("asfalto"), N_("Sordo, con un poco de arenilla. Estás en la calzada.")),
	"acera": (700, 4200, 0.09, 0.020, 0.46, N_("acera"), N_("Seco, de losa de calle.")),
	"adoquin": (600, 4000, 0.12, 0.022, 0.48, N_("adoquín"), N_("Dos toques irregulares, de piedra desigual.")),
	"tierra": (300, 2500, 0.14, 0.040, 0.42, N_("tierra"), N_("Blando, con un crujido leve.")),
	"hierba": (2000, 7000, 0.17, 0.050, 0.32, N_("hierba"), N_("Un roce suave y agudo.")),
	"grava": (1500, 8000, 0.22, 0.060, 0.45, N_("grava"), N_("Varios crujidos de piedrecillas.")),
	"metal": (500, 6000, 0.22, 0.060, 0.50, N_("metal"), N_("Un golpe que resuena, como en una pasarela o una rejilla.")),
	"arena": (500, 3500, 0.20, 0.070, 0.36, N_("arena"), N_("Un siseo blando que se hunde.")),
	"agua": (300, 5000, 0.30, 0.090, 0.45, N_("agua"), N_("Un chapoteo: has pisado un charco.")),
	"tactil_botones": (
		900,
		5500,
		0.12,
		0.018,
		0.50,
		N_("pavimento táctil de botones"),
		N_("Baldosa con un repique doble: avisa de un peligro o de un cruce justo delante."),
	),
	"tactil_rayas": (
		900,
		5500,
		0.14,
		0.018,
		0.50,
		N_("pavimento táctil de rayas"),
		N_("Baldosa con un raspado corto: marca un camino que puedes seguir."),
	),
}


def _paso(rng: np.random.Generator, suelo: str, pie: str) -> np.ndarray:
	"""Una pisada. Cada variante sale distinta porque su semilla lo es."""
	lo, hi, d, tau, _pico, _nombre, _como = _PASOS[suelo]
	afinacion = 1.0 + rng.uniform(-0.08, 0.08)
	# El pie derecho, un pelo más brillante: ayuda a notar la alternancia sin que parezcan dos suelos.
	brillo = 1.06 if pie == "der" else 0.96
	lo, hi = lo * afinacion, hi * afinacion * brillo
	x = np.zeros(_muestras(d + 0.05))
	_poner(x, _filtro(_ruido(rng, d), lo, hi) * _decae(d, tau, 0.002), 0.0)
	# El peso del cuerpo: un golpe grave, más flojo en los suelos blandos.
	blando = suelo in ("moqueta", "alfombra", "hierba", "arena", "agua")
	_poner(x, _seno(75 * afinacion, 0.06) * _decae(0.06, 0.018), 0.0, 0.25 if blando else 0.5)
	# Un poco de roce de suela por encima de 3 kHz en todos, para que el paso se sitúe a tus pies.
	_poner(x, _filtro(_ruido(rng, 0.05), 3500, 9000) * _decae(0.05, 0.012, 0.001), 0.002, 0.40 if blando else 0.32)
	if suelo == "madera":
		_poner(x, _seno(185 * afinacion, 0.12) * _decae(0.12, 0.03), 0.0, 0.6)
	elif suelo == "adoquin":
		_poner(x, _filtro(_ruido(rng, 0.05), lo, hi) * _decae(0.05, 0.012, 0.001), rng.uniform(0.035, 0.06), 0.55)
	elif suelo in ("tierra", "grava"):
		granos = 3 if suelo == "tierra" else 9
		for _k in range(granos):
			grano = _filtro(_ruido(rng, 0.025), 2000, 9000) * _decae(0.025, rng.uniform(0.003, 0.008), 0.0005)
			_poner(x, grano, rng.uniform(0.0, d * 0.8), rng.uniform(0.3, 0.9) * (0.5 if suelo == "tierra" else 1.0))
	elif suelo == "metal":
		for parcial, peso in ((520, 1.0), (1130, 0.6), (2210, 0.4), (3650, 0.25)):
			_poner(x, _seno(parcial * afinacion, 0.2) * _decae(0.2, 0.05, 0.001), 0.0, 0.35 * peso)
	elif suelo == "agua":
		t = _t(d)
		chapoteo = _filtro(_ruido(rng, d), 400, 6000) * _decae(d, 0.08, 0.01) * (1.0 + 0.6 * np.sin(PI2 * 14 * t))
		_poner(x, chapoteo, 0.01, 0.9)
		_poner(x, _barrido(900, 300, 0.08) * _decae(0.08, 0.025), 0.03, 0.3)
	elif suelo == "tactil_botones":
		for retraso in (0.028, 0.056):
			_poner(x, _seno(1400 * afinacion, 0.03) * _decae(0.03, 0.007, 0.001), retraso, 0.6)
			_poner(x, _filtro(_ruido(rng, 0.02), 3000, 9000) * _decae(0.02, 0.004, 0.0005), retraso, 0.4)
	elif suelo == "tactil_rayas":
		raspado = _filtro(_ruido(rng, 0.09), 2500, 7000) * _arco(0.09) * (0.5 + 0.5 * np.sign(_seno(85, 0.09)))
		_poner(x, raspado, 0.02, 0.7)
	return x


def _alta_pasos() -> None:
	for suelo in SUELOS:
		pico, hablado, como = _PASOS[suelo][4:]
		for pie in PIES:
			for variante in range(1, VARIANTES_PASO + 1):
				_alta(
					f"pasos/{suelo}_{pie}_{variante}",
					N_("Paso sobre {suelo}, pie {pie}, variante {variante}"),
					N_("{como} Lo oyes a tus pies cada vez que das un paso sobre {suelo}."),
					"movimiento",
					partial(_paso, suelo=suelo, pie=pie),
					pico=pico,
					suelo=hablado,
					pie=N_("izquierdo") if pie == "izq" else N_("derecho"),
					variante=str(variante),
					como=como,
				)


# ── Golpes y roces por material ──────────────────────────────────────────────

_MATERIAL_HABLADO = {
	"ladrillo": N_("ladrillo"),
	"madera": N_("madera"),
	"metal": N_("metal"),
	"cristal": N_("cristal"),
	"plastico": N_("plástico"),
	"tela": N_("tela"),
	"piedra": N_("piedra"),
}
_MATERIAL_GOLPE = {
	"ladrillo": N_("Un golpe sordo y corto, con algo de arenilla."),
	"madera": N_("Un toc hueco."),
	"metal": N_("Un golpe que se queda sonando, como una chapa."),
	"cristal": N_("Un toque agudo que tintinea."),
	"plastico": N_("Un clac hueco y ligero."),
	"tela": N_("Un golpe blando, casi sin sonido, con un roce."),
	"piedra": N_("Un golpe duro y seco."),
}
_MATERIAL_ROCE = {
	"ladrillo": N_("Un raspado áspero."),
	"madera": N_("Un deslizar suave y algo grave."),
	"metal": N_("Un roce agudo con un punto de chirrido."),
	"cristal": N_("Un roce liso y muy agudo."),
	"plastico": N_("Un roce hueco y ligero."),
	"tela": N_("Un siseo blando."),
	"piedra": N_("Un raspado duro y granulado."),
}


def _golpe(rng: np.random.Generator, material: str) -> np.ndarray:
	"""Choque contra una pared o un objeto de ese material."""
	x = np.zeros(_muestras(0.7 if material in ("metal", "cristal") else 0.3))
	if material == "ladrillo":
		_poner(x, _filtro(_ruido(rng, 0.14), 80, 700) * _decae(0.14, 0.04), 0.0)
		_poner(x, _seno(85, 0.12) * _decae(0.12, 0.04), 0.0, 0.8)
		_poner(x, _filtro(_ruido(rng, 0.08), 2500, 8000) * _decae(0.08, 0.02, 0.001), 0.0, 0.7)
	elif material == "madera":
		_poner(x, _toc(rng, 220, 0.16, 1800), 0.0)
		_poner(x, _seno(440, 0.1) * _decae(0.1, 0.025), 0.0, 0.3)
		_poner(x, _aire(rng, 0.06, 0.9, 0.012), 0.0)
	elif material == "metal":
		for parcial, peso, cola in ((310, 1.0, 0.22), (835, 0.8, 0.18), (1620, 0.6, 0.14), (2890, 0.45, 0.1), (4410, 0.3, 0.07)):
			_poner(x, _seno(parcial, 0.65) * _decae(0.65, cola, 0.001), 0.0, peso * 0.5)
		_poner(x, _filtro(_ruido(rng, 0.04), 1500, 9000) * _decae(0.04, 0.008, 0.0005), 0.0, 1.6)
	elif material == "cristal":
		for parcial, peso in ((2100, 1.0), (3370, 0.7), (5150, 0.5), (7300, 0.3)):
			_poner(x, _seno(parcial, 0.5) * _decae(0.5, 0.09, 0.001), 0.0, peso * 0.5)
		_poner(x, _seno(160, 0.08) * _decae(0.08, 0.02), 0.0, 0.5)
		_poner(x, _filtro(_ruido(rng, 0.02), 3000, 12000) * _decae(0.02, 0.003, 0.0005), 0.0, 0.6)
	elif material == "plastico":
		_poner(x, _seno(640, 0.08) * _decae(0.08, 0.016), 0.0)
		_poner(x, _seno(980, 0.06) * _decae(0.06, 0.012), 0.0, 0.6)
		_poner(x, _filtro(_ruido(rng, 0.05), 1200, 7000) * _decae(0.05, 0.008, 0.0005), 0.0, 0.7)
	elif material == "tela":
		_poner(x, _filtro(_ruido(rng, 0.18), 90, 800) * _decae(0.18, 0.05, 0.01), 0.0)
		_poner(x, _filtro(_ruido(rng, 0.2), 2500, 8000) * _arco(0.2), 0.0, 0.3)
	else:  # piedra
		_poner(x, _filtro(_ruido(rng, 0.06), 500, 5000) * _decae(0.06, 0.012, 0.0008), 0.0)
		_poner(x, _seno(110, 0.1) * _decae(0.1, 0.03), 0.0, 0.7)
		_poner(x, _seno(1750, 0.04) * _decae(0.04, 0.008), 0.0, 0.3)
	return x


def _roce(rng: np.random.Generator, material: str) -> np.ndarray:
	"""Rozar una pared o un objeto de ese material al pasar pegado a él."""
	d = 0.4
	t = _t(d)
	lo, hi, grano = {
		"ladrillo": (800, 5500, 0.8),
		"madera": (500, 3800, 0.3),
		"metal": (2000, 9000, 0.4),
		"cristal": (4000, 11000, 0.1),
		"plastico": (1000, 4800, 0.25),
		"tela": (1500, 7000, 0.15),
		"piedra": (600, 6500, 1.0),
	}[material]
	x = _filtro(_ruido(rng, d), lo, hi)
	# La aspereza es una modulación de volumen irregular: cuanto más grano, más rugoso se oye.
	rugosidad = np.abs(_filtro(_ruido(rng, d), 20, 140))
	rugosidad /= float(np.max(rugosidad)) or 1.0
	x = x * ((1.0 - grano) + grano * rugosidad) * _arco(d, 0.7)
	if material == "metal":
		x += 0.25 * np.sin(PI2 * (3100 * t + 40 * np.sin(PI2 * 7 * t))) * _arco(d)
	elif material == "cristal":
		x += 0.3 * np.sin(PI2 * (5200 * t + 25 * np.sin(PI2 * 11 * t))) * _arco(d)
	elif material == "madera":
		x += 0.2 * _filtro(_ruido(rng, d), 150, 500) * _arco(d)
	return x


def _alta_materiales() -> None:
	for material in MATERIALES:
		_alta(
			f"golpe/{material}",
			N_("Choque con {material}"),
			N_("{como} Has chocado con una pared o un objeto de {material}; suena desde donde está."),
			"choques",
			partial(_golpe, material=material),
			pico=0.7,
			material=_MATERIAL_HABLADO[material],
			como=_MATERIAL_GOLPE[material],
		)
	for material in MATERIALES:
		_alta(
			f"roce/{material}",
			N_("Roce con {material}"),
			N_("{como} Vas rozando una pared o un objeto de {material}, por el lado en que suena."),
			"choques",
			partial(_roce, material=material),
			pico=0.4,
			material=_MATERIAL_HABLADO[material],
			como=_MATERIAL_ROCE[material],
		)


# ── Puertas, escaleras, rampas y ascensor ────────────────────────────────────


def _chirrido(f0: float, f1: float, segundos: float) -> np.ndarray:
	"""Bisagra: onda cuadrada que sube o baja de tono, temblando."""
	t = _t(segundos)
	f = f0 + (f1 - f0) * t / segundos + 40 * np.sin(PI2 * 9 * t)
	onda = np.sign(np.sin(PI2 * np.cumsum(f) / FRECUENCIA))
	return _filtro(onda, 400, 5000) * _arco(segundos)


def _clac(rng: np.random.Generator, segundos: float = 0.03, lo: float = 800, hi: float = 7000) -> np.ndarray:
	return _filtro(_ruido(rng, segundos), lo, hi) * _decae(segundos, segundos / 5.0, 0.0005)


def _puerta_abrir(rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(0.75))
	_poner(x, _clac(rng, 0.04), 0.0)
	_poner(x, _seno(240, 0.05) * _decae(0.05, 0.012), 0.0, 0.5)
	_poner(x, _chirrido(190, 470, 0.5), 0.12, 0.55)
	return x


def _puerta_cerrar(rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(0.7))
	_poner(x, _chirrido(430, 210, 0.28), 0.0, 0.4)
	_poner(x, _filtro(_ruido(rng, 0.2), 70, 900) * _decae(0.2, 0.05), 0.3)
	_poner(x, _seno(95, 0.18) * _decae(0.18, 0.05), 0.3, 0.9)
	_poner(x, _clac(rng, 0.04), 0.31, 0.8)
	_poner(x, _clac(rng, 0.025, 1500, 8000), 0.4, 0.5)
	return x


def _puerta_con_llave(rng: np.random.Generator) -> np.ndarray:
	"""La manilla baja dos veces y la puerta no cede: traqueteo metálico corto."""
	x = np.zeros(_muestras(0.6))
	for inicio, fuerza in ((0.0, 1.0), (0.07, 0.6), (0.24, 0.9), (0.31, 0.55)):
		_poner(x, _clac(rng, 0.035, 1200, 8000), inicio, fuerza)
		_poner(x, _seno(1850, 0.05) * _decae(0.05, 0.012, 0.001), inicio, 0.25 * fuerza)
		_poner(x, _seno(140, 0.06) * _decae(0.06, 0.018), inicio, 0.5 * fuerza)
	return x


def _puerta_automatica(rng: np.random.Generator) -> np.ndarray:
	"""Puerta corredera automática: motor que arranca, hojas que se deslizan y tope."""
	d = 1.1
	t = _t(d)
	x = _filtro(_ruido(rng, d), 600, 6500) * _arco(d, 0.6) * 0.7
	x += 0.35 * np.sin(PI2 * np.cumsum(90 + 60 * np.sin(np.pi * t / d)) / FRECUENCIA) * _arco(d)
	x += 0.2 * _siseo(rng, d, 3500, 9000) * _arco(d, 0.5)
	_poner(x, _filtro(_ruido(rng, 0.08), 100, 1500) * _decae(0.08, 0.02), d - 0.12, 1.2)
	return x


def _peldano(rng: np.random.Generator, sube: bool) -> np.ndarray:
	"""Un peldaño: pisada y dos notas que suben o bajan. El motor cambia el tono de un peldaño a otro."""
	x = np.zeros(_muestras(0.32))
	_poner(x, _toc(rng, 190 if sube else 150, 0.08, 1600), 0.0, 0.8)
	notas = (587, 784) if sube else (784, 587)
	_poner(x, _nota(notas[0], 0.12, 0.04), 0.04, 0.6)
	_poner(x, _nota(notas[1], 0.16, 0.05), 0.11, 0.6)
	_poner(x, _aire(rng, 0.06, 0.9, 0.012), 0.04)
	return x


def _rampa(rng: np.random.Generator) -> np.ndarray:
	"""Rampa: un deslizamiento continuo que sube de tono, sin escalones."""
	d = 0.45
	x = 0.6 * _barrido(330, 660, d) * _arco(d)
	x += 0.25 * _barrido(660, 1320, d) * _arco(d)
	x += 0.5 * _filtro(_ruido(rng, d), 2500, 8000) * _arco(d, 1.5)
	return x


def _ascensor_llamada(rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(0.45))
	_poner(x, _clac(rng, 0.03, 1000, 7000), 0.0, 0.8)
	_poner(x, _seno(180, 0.04) * _decae(0.04, 0.01), 0.0, 0.5)
	_poner(x, _con_aire(rng, _nota(1175, 0.3, 0.1, (1, 0.3, 0.15)), 0.7), 0.08, 0.8)
	return x


def _ascensor_puerta(rng: np.random.Generator) -> np.ndarray:
	d = 1.3
	t = _t(d)
	x = _filtro(_ruido(rng, d), 150, 2500) * _arco(d, 0.5) * 0.8
	x += 0.3 * np.sin(PI2 * 70 * t) * _arco(d)
	x += 0.25 * _siseo(rng, d) * _arco(d, 0.5)
	_poner(x, _filtro(_ruido(rng, 0.1), 80, 1200) * _decae(0.1, 0.025), d - 0.14, 1.5)
	_poner(x, _clac(rng, 0.03, 1500, 8000), d - 0.13, 0.6)
	return x


def _ascensor_viaje(rng: np.random.Generator) -> np.ndarray:
	"""La cabina en marcha: zumbido del motor y aire, para repetir mientras dura el viaje."""
	d = 3.5
	t = _t(d)
	x = 0.5 * np.sin(PI2 * 92 * t) + 0.25 * np.sin(PI2 * 184 * t + 1.0) + 0.12 * np.sin(PI2 * 276 * t + 2.0)
	x = x * (0.85 + 0.15 * np.sin(PI2 * 4 * t))
	x += 0.5 * _filtro(_ruido(rng, d), 200, 1800)
	x += 0.12 * _siseo(rng, d)
	return _bucle(x)


def _ascensor_llegada(rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(1.0))
	_poner(x, _campana(1319, 0.9, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.0)
	_poner(x, _campana(1047, 0.75, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.22, 0.9)
	_poner(x, _aire(rng, 0.05, 0.3, 0.008), 0.0)
	return x


# Escala mayor desde do: cada planta, una nota más alta. La planta 0 es la más grave.
_ESCALA = (0, 2, 4, 5, 7, 9, 11, 12, 14, 16)


def _ascensor_planta(rng: np.random.Generator, planta: int) -> np.ndarray:
	f = 523.25 * 2.0 ** (_ESCALA[planta] / 12.0)
	x = np.zeros(_muestras(0.5))
	_poner(x, _con_aire(rng, _campana(f, 0.48, (1, 2.0, 3.0, 4.2), (1, 0.6, 0.4, 0.25)), 0.9), 0.0)
	return x


def _alta_puertas() -> None:
	g = "puertas"
	_alta(
		"puerta/abrir",
		N_("Puerta que se abre"),
		N_("Un clic de manilla y la bisagra que sube de tono: has abierto una puerta. Suena desde la puerta."),
		g,
		_puerta_abrir,
	)
	_alta(
		"puerta/cerrar",
		N_("Puerta que se cierra"),
		N_("La bisagra baja de tono y la puerta da un golpe: una puerta se ha cerrado."),
		g,
		_puerta_cerrar,
		pico=0.65,
	)
	_alta(
		"puerta/con_llave",
		N_("Puerta cerrada con llave"),
		N_("La manilla traquetea dos veces y la puerta no cede: está cerrada con llave y no puedes pasar por ahí."),
		g,
		_puerta_con_llave,
	)
	_alta(
		"puerta/automatica",
		N_("Puerta automática"),
		N_("Un deslizamiento con zumbido de motor: una puerta corredera automática se abre o se cierra."),
		g,
		_puerta_automatica,
		pico=0.5,
	)
	_alta(
		"escalera/subir",
		N_("Peldaño que sube"),
		N_("Una pisada y dos notas que suben: has subido un peldaño. Cada peldaño suena un poco más agudo que el anterior."),
		g,
		partial(_peldano, sube=True),
	)
	_alta(
		"escalera/bajar",
		N_("Peldaño que baja"),
		N_("Una pisada y dos notas que bajan: has bajado un peldaño. Cada peldaño suena un poco más grave que el anterior."),
		g,
		partial(_peldano, sube=False),
	)
	_alta(
		"escalera/rampa",
		N_("Rampa"),
		N_("Un deslizamiento continuo, sin escalones: avanzas por una rampa. Más agudo si subes, más grave si bajas."),
		g,
		_rampa,
		pico=0.5,
	)
	_alta(
		"ascensor/llamada",
		N_("Ascensor, botón de llamada"),
		N_("Un clic y un pitido: has llamado al ascensor o has elegido planta."),
		g,
		_ascensor_llamada,
		pico=0.5,
	)
	_alta(
		"ascensor/puerta",
		N_("Ascensor, puerta"),
		N_("Un deslizamiento grave que acaba en un tope: la puerta del ascensor se abre o se cierra."),
		g,
		_ascensor_puerta,
		pico=0.5,
	)
	_alta(
		"ascensor/viaje",
		N_("Ascensor en marcha"),
		N_("Un zumbido continuo a tu alrededor mientras el ascensor se mueve entre plantas."),
		g,
		_ascensor_viaje,
		bucle=True,
		posicionable=False,
		pico=0.35,
	)
	_alta(
		"ascensor/llegada",
		N_("Ascensor, llegada"),
		N_("Dos campanadas, la segunda más grave: el ascensor ha llegado a la planta."),
		g,
		_ascensor_llegada,
		pico=0.55,
	)
	for planta in range(PLANTAS_ASCENSOR):
		_alta(
			f"ascensor/planta_{planta}",
			N_("Ascensor, tono de la planta {planta}"),
			N_("Una campanilla cuya nota dice la planta: cuanto más aguda, más arriba. La planta 0 es la más grave."),
			g,
			partial(_ascensor_planta, planta=planta),
			pico=0.5,
			planta=str(planta),
		)


# ── Orientación: balizas, sonda, brújula y eco ───────────────────────────────


def _baliza_pulso(rng: np.random.Generator) -> np.ndarray:
	d = 0.35
	nota = (_seno(660, d) + 0.35 * _seno(1320, d) + 0.15 * _seno(1980, d)) * _decae(d, 0.08, 0.004)
	return _con_aire(rng, nota, 0.7)


def _baliza_alineado(rng: np.random.Generator) -> np.ndarray:
	d = 0.35
	nota = (_seno(990, d) + 0.5 * _seno(1980, d) + 0.3 * _seno(2970, d) + 0.15 * _seno(3960, d)) * _decae(d, 0.09, 0.003)
	return _con_aire(rng, nota, 0.7)


def _baliza_detras(rng: np.random.Generator) -> np.ndarray:
	"""Dos notas graves que bajan: «lo tienes a la espalda». El chasquido sigue ahí para poder situarla."""
	x = np.zeros(_muestras(0.4))
	_poner(x, _nota(440, 0.16, 0.06, (1, 0.5, 0.25)), 0.0)
	_poner(x, _nota(330, 0.24, 0.08, (1, 0.5, 0.25)), 0.13)
	return _con_aire(rng, x, 0.9)


def _baliza_cerca(rng: np.random.Generator) -> np.ndarray:
	"""Dos pulsos rápidos y agudos: el destino está a pocos pasos."""
	x = np.zeros(_muestras(0.3))
	for inicio in (0.0, 0.11):
		pulso = (_seno(1320, 0.1) + 0.4 * _seno(2640, 0.1)) * _decae(0.1, 0.03, 0.002)
		_poner(x, pulso, inicio)
		_poner(x, _aire(rng, 0.05, 0.7, 0.01), inicio)
	return x


def _baliza_llegada(rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(1.0))
	for k, f in enumerate((523.25, 659.25, 783.99, 1046.5)):
		_poner(x, _nota(f, 0.5, 0.2, (1, 0.4, 0.2)), k * 0.11, 0.7)
		_poner(x, _aire(rng, 0.05, 0.7, 0.012), k * 0.11)
	return x


def _sonda(rng: np.random.Generator, hallazgo: str) -> np.ndarray:
	"""El bastón sonoro toca algo. Cada hallazgo tiene su timbre; el motor sube el tono cuanto más cerca está."""
	x = np.zeros(_muestras(0.3))
	if hallazgo == "pared":
		_poner(x, _seno(520, 0.12) * _decae(0.12, 0.03, 0.002), 0.0)
		_poner(x, _seno(1040, 0.08) * _decae(0.08, 0.02, 0.002), 0.0, 0.35)
		_poner(x, _aire(rng, 0.05, 0.7, 0.01), 0.0)
	elif hallazgo == "puerta":
		_poner(x, _toc(rng, 330, 0.09, 2200), 0.0, 0.9)
		_poner(x, _toc(rng, 440, 0.11, 2200), 0.1, 0.9)
		_poner(x, _aire(rng, 0.04, 0.6, 0.008), 0.0)
		_poner(x, _aire(rng, 0.04, 0.6, 0.008), 0.1)
	elif hallazgo == "objeto":
		_poner(x, _nota(988, 0.16, 0.045, (1, 0.0, 0.33, 0.0, 0.2)), 0.0)
		_poner(x, _aire(rng, 0.05, 0.5, 0.008), 0.0)
	elif hallazgo == "libre":
		soplo = _filtro(_ruido(rng, 0.22), 2500, 9000) * _arco(0.22, 1.5)
		_poner(x, soplo, 0.0, 0.8)
		_poner(x, _barrido(1800, 2600, 0.22) * _arco(0.22), 0.0, 0.15)
	elif hallazgo == "escalon":
		for k, f in enumerate((700, 880, 1109)):
			_poner(x, _seno(f, 0.06) * _decae(0.06, 0.015, 0.001), k * 0.06, 0.9)
			_poner(x, _aire(rng, 0.03, 0.45, 0.005), k * 0.06)
	else:  # bordillo
		_poner(x, _filtro(_ruido(rng, 0.08), 120, 900) * _decae(0.08, 0.022), 0.0)
		_poner(x, _seno(160, 0.08) * _decae(0.08, 0.025), 0.0, 0.7)
		_poner(x, _clac(rng, 0.03, 2500, 9000), 0.0, 0.7)
		_poner(x, _clac(rng, 0.03, 2500, 9000), 0.09, 0.9)
		_poner(x, _seno(1250, 0.05) * _decae(0.05, 0.012), 0.09, 0.5)
	return x


def _sonda_distancia(rng: np.random.Generator, f: float, repeticiones: int) -> np.ndarray:
	"""Pitido de distancia: más agudo y más repetido cuanto más cerca."""
	x = np.zeros(_muestras(0.09 * repeticiones + 0.08))
	for k in range(repeticiones):
		_poner(x, (_seno(f, 0.07) + 0.3 * _seno(f * 2, 0.07)) * _decae(0.07, 0.02, 0.002), k * 0.09)
		_poner(x, _aire(rng, 0.04, 0.7, 0.008), k * 0.09)
	return x


def _brujula(rng: np.random.Generator, notas: tuple[float, ...]) -> np.ndarray:
	x = np.zeros(_muestras(0.08 * len(notas) + 0.18))
	for k, f in enumerate(notas):
		_poner(x, _nota(f, 0.2, 0.05, (1, 0.3, 0.12)), k * 0.08)
		_poner(x, _aire(rng, 0.05, 0.9, 0.012), k * 0.08)
	return x


def _eco_chasquido(rng: np.random.Generator) -> np.ndarray:
	"""Chasquido de lengua: muy corto y de banda ancha, para oír cómo responde el lugar."""
	x = np.zeros(_muestras(0.06))
	_poner(x, _filtro(_ruido(rng, 0.012), 1500, 12000) * _decae(0.012, 0.0022, 0.0003), 0.0)
	_poner(x, _seno(2400, 0.01) * _decae(0.01, 0.002, 0.0003), 0.0, 0.5)
	return x


def _alta_orientacion() -> None:
	g = "orientacion"
	_alta(
		"baliza/pulso",
		N_("Baliza"),
		N_("Un pulso suave que suena desde tu destino. Gírate hasta oírlo delante y camina hacia él."),
		g,
		_baliza_pulso,
	)
	_alta(
		"baliza/alineado",
		N_("Baliza, bien encaminado"),
		N_("El mismo pulso, más agudo y brillante: estás mirando hacia el destino."),
		g,
		_baliza_alineado,
	)
	_alta(
		"baliza/detras",
		N_("Baliza, destino a tu espalda"),
		N_("Dos notas graves que bajan: el destino queda detrás de ti. Date la vuelta."),
		g,
		_baliza_detras,
	)
	_alta(
		"baliza/cerca",
		N_("Baliza, destino cerca"),
		N_("Dos pulsos rápidos y agudos: estás a pocos pasos del destino."),
		g,
		_baliza_cerca,
	)
	_alta(
		"baliza/llegada",
		N_("Llegada"),
		N_("Cuatro notas que suben: has llegado al destino."),
		g,
		_baliza_llegada,
		pico=0.55,
	)
	hallazgos = (
		("pared", N_("Bastón sonoro, pared"), N_("Un tono lleno y corto: el bastón ha encontrado una pared. Más agudo cuanto más cerca.")),
		(
			"puerta",
			N_("Bastón sonoro, puerta"),
			N_("Dos toques de madera, el segundo más agudo: en esa dirección hay una puerta o un hueco para pasar."),
		),
		("objeto", N_("Bastón sonoro, objeto"), N_("Una nota hueca, como un xilófono: hay un mueble o un objeto en esa dirección.")),
		(
			"libre",
			N_("Bastón sonoro, paso libre"),
			N_("Un soplo de aire, sin nota: no hay nada en esa dirección hasta donde alcanza el bastón."),
		),
		("escalon", N_("Bastón sonoro, escalón"), N_("Tres toques rápidos que suben: hay una escalera o un escalón.")),
		("bordillo", N_("Bastón sonoro, bordillo"), N_("Un golpe grave y dos chasquidos: hay un bordillo, el borde de la acera.")),
	)
	for clave, nombre, explicacion in hallazgos:
		_alta(f"sonda/{clave}", nombre, explicacion, g, partial(_sonda, hallazgo=clave), pico=0.55)
	distancias = (
		("cerca", 1397.0, 3, N_("Distancia: cerca"), N_("Tres pitidos agudos: lo que señalas está a menos de dos pasos.")),
		("media", 932.0, 2, N_("Distancia: media"), N_("Dos pitidos medios: lo que señalas está a unos pocos metros.")),
		("lejos", 554.0, 1, N_("Distancia: lejos"), N_("Un pitido grave: lo que señalas está lejos.")),
	)
	for clave, f, veces, nombre, explicacion in distancias:
		_alta(f"sonda/{clave}", nombre, explicacion, g, partial(_sonda_distancia, f=f, repeticiones=veces), pico=0.5)
	cardinales = (
		("norte", (1568.0,), N_("Brújula, norte"), N_("Una nota aguda y sola, que suena desde el norte.")),
		("este", (1174.7, 1174.7), N_("Brújula, este"), N_("Dos notas iguales, que suenan desde el este.")),
		("sur", (784.0,), N_("Brújula, sur"), N_("Una nota grave y sola, que suena desde el sur.")),
		("oeste", (987.8, 987.8, 987.8), N_("Brújula, oeste"), N_("Tres notas iguales, que suenan desde el oeste.")),
		("noreste", (1568.0, 1174.7), N_("Brújula, noreste"), N_("La nota del norte y luego la del este.")),
		("sureste", (784.0, 1174.7), N_("Brújula, sureste"), N_("La nota del sur y luego la del este.")),
		("suroeste", (784.0, 987.8), N_("Brújula, suroeste"), N_("La nota del sur y luego la del oeste.")),
		("noroeste", (1568.0, 987.8), N_("Brújula, noroeste"), N_("La nota del norte y luego la del oeste.")),
	)
	for clave, notas, nombre, explicacion in cardinales:
		_alta(f"brujula/{clave}", nombre, explicacion, g, partial(_brujula, notas=notas), pico=0.5)
	_alta(
		"eco/chasquido",
		N_("Chasquido para el eco"),
		N_(
			"Un chasquido de lengua. Escucha cómo responde el lugar: seco en una habitación pequeña, con cola en una sala grande o una escalera."
		),
		g,
		_eco_chasquido,
		pico=0.7,
	)


# ── Premios, logros y pistas ─────────────────────────────────────────────────


def _destello(rng: np.random.Generator, f: float, segundos: float = 0.12) -> np.ndarray:
	"""Tintineo de moneda o de cristal: muy agudo y corto."""
	return _campana(f, segundos, (1, 1.41, 2.3), (1, 0.6, 0.4)) + _aire(rng, segundos, 0.2, 0.006)


def _premio_aparece(rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(0.6))
	for k, f in enumerate((1568, 2093, 2637, 3136, 4186)):
		_poner(x, _destello(rng, f), k * 0.07, 0.6 + 0.1 * k)
	return x


def _premio_cerca(rng: np.random.Generator) -> np.ndarray:
	"""Centelleo que se repite: hay un premio aquí al lado. Empalma solo, sin costura."""
	x = np.zeros(_muestras(1.2))
	for inicio, f, fuerza in ((0.0, 2637, 1.0), (0.15, 3136, 0.8), (0.3, 3951, 0.9), (0.6, 3136, 0.7), (0.75, 4186, 0.8)):
		_poner_ciclico(x, _destello(rng, f, 0.2), inicio, fuerza)
	return x


def _premio_recogido(rng: np.random.Generator) -> np.ndarray:
	x = _sec((2093, 2637, 0, 2093, 3136), 0.05, 0.3, 0.08, (1, 0.3))
	_poner(x, _aire(rng, 0.05, 0.25, 0.008), 0.0)
	return x


def _premio_tesoro(rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(1.6))
	_poner(x, _sec((523.25, 659.25, 783.99, 1046.5, 783.99, 1046.5, 1318.5), 0.1, 0.7, 0.3, (1, 0.5, 0.3, 0.2)), 0.0)
	for _k in range(10):
		_poner(x, _destello(rng, rng.uniform(3000, 6000), 0.1), rng.uniform(0.5, 1.3), rng.uniform(0.15, 0.35))
	return x


def _logro(rng: np.random.Generator) -> np.ndarray:
	x = _sec((659.25, 783.99, 1046.5), 0.09, 0.45, 0.16, (1, 0.4, 0.2))
	_poner(x, _aire(rng, 0.04, 0.2, 0.008), 0.0)
	return x


def _estrella(rng: np.random.Generator, cuantas: int) -> np.ndarray:
	"""Tantas campanillas como estrellas, cada una más aguda."""
	x = np.zeros(_muestras(0.22 * cuantas + 0.7))
	for k, f in enumerate((1046.5, 1318.5, 1568.0)[:cuantas]):
		_poner(x, _campana(f, 0.8, (1, 2.0, 3.01, 4.1), (1, 0.7, 0.45, 0.3)), k * 0.22)
		_poner(x, _destello(rng, f * 3.0, 0.1), k * 0.22 + 0.02, 0.25)
	return x


def _medalla(rng: np.random.Generator) -> np.ndarray:
	"""Fanfarria corta de metales: sierra filtrada, tres notas y un acorde final."""
	x = np.zeros(_muestras(1.9))

	def metal(f: float, d: float) -> np.ndarray:
		onda = _filtro(_barrido(f, f, d, "sierra"), 200, 3200)
		return onda * np.minimum(1.0, _t(d) / 0.02) * np.exp(-_t(d) / (d * 0.9))

	for inicio, f, d in ((0.0, 392.0, 0.16), (0.17, 392.0, 0.16), (0.34, 523.25, 0.22), (0.58, 659.25, 0.22)):
		_poner(x, metal(f, d), inicio, 0.8)
	for f in (523.25, 659.25, 783.99, 1046.5):
		_poner(x, metal(f, 1.0), 0.82, 0.45)
	for _k in range(8):
		_poner(x, _destello(rng, rng.uniform(3000, 6000), 0.1), rng.uniform(0.85, 1.6), rng.uniform(0.1, 0.25))
	return x


def _error_suave(_rng: np.random.Generator) -> np.ndarray:
	"""Dos notas graves y redondas que bajan: «eso no», sin sobresalto ni zumbido desagradable."""
	x = np.zeros(_muestras(0.42))
	_poner(x, _nota(311.1, 0.18, 0.07, (1, 0.25)), 0.0)
	_poner(x, _nota(233.1, 0.28, 0.1, (1, 0.25)), 0.13)
	return x


def _pista(rng: np.random.Generator) -> np.ndarray:
	"""Dos notas que suben y se quedan en el aire, como una pregunta: «¿y si pruebas esto?»."""
	x = np.zeros(_muestras(0.6))
	_poner(x, _campana(880, 0.3, (1, 2.0, 3.0), (1, 0.6, 0.4)), 0.0)
	_poner(x, _campana(1318.5, 0.45, (1, 2.0, 3.0), (1, 0.6, 0.4)), 0.14)
	_poner(x, _aire(rng, 0.04, 0.2, 0.008), 0.0)
	return x


def _alta_premios() -> None:
	g = "premios"
	_alta(
		"premio/aparece",
		N_("Premio que aparece"),
		N_("Cinco tintineos que suben: hay un premio por aquí. Suena desde donde está."),
		g,
		_premio_aparece,
		pico=0.5,
	)
	_alta(
		"premio/cerca",
		N_("Premio cerca"),
		N_("Un centelleo que se repite desde el premio. Acércate hasta tenerlo encima y recógelo."),
		g,
		_premio_cerca,
		bucle=True,
		pico=0.4,
	)
	_alta(
		"premio/recogido",
		N_("Premio recogido"),
		N_("Unas monedas rápidas: has recogido un premio."),
		g,
		_premio_recogido,
		pico=0.5,
	)
	_alta(
		"premio/tesoro",
		N_("Tesoro"),
		N_("Una melodía que sube con una lluvia de tintineos: has encontrado un tesoro o el premio principal."),
		g,
		_premio_tesoro,
		pico=0.6,
	)
	_alta(
		"logro/logro",
		N_("Logro"),
		N_("Tres notas que suben: has completado un objetivo."),
		g,
		_logro,
		posicionable=False,
		pico=0.5,
	)
	estrellas = (
		(1, N_("Una estrella"), N_("Una campanilla: has conseguido una estrella.")),
		(2, N_("Dos estrellas"), N_("Dos campanillas que suben: has conseguido dos estrellas.")),
		(3, N_("Tres estrellas"), N_("Tres campanillas que suben: has conseguido las tres estrellas.")),
	)
	for cuantas, nombre, explicacion in estrellas:
		_alta(f"logro/estrella_{cuantas}", nombre, explicacion, g, partial(_estrella, cuantas=cuantas), posicionable=False, pico=0.5)
	_alta(
		"logro/medalla",
		N_("Medalla"),
		N_("Una fanfarria de trompetas: has ganado una medalla."),
		g,
		_medalla,
		posicionable=False,
		pico=0.6,
	)
	_alta(
		"logro/error",
		N_("Eso no es"),
		N_("Dos notas graves y suaves que bajan: no era eso, o por ahí no se puede. Prueba otra cosa."),
		g,
		_error_suave,
		posicionable=False,
		pico=0.45,
	)
	_alta(
		"logro/pista",
		N_("Pista"),
		N_("Dos campanillas que suben y se quedan en el aire: a continuación viene una pista."),
		g,
		_pista,
		posicionable=False,
		pico=0.45,
	)


# ── Interfaz ─────────────────────────────────────────────────────────────────


def _alta_interfaz() -> None:
	g = "interfaz"
	sonidos: tuple[tuple[str, str, str, Generador, float], ...] = (
		(
			"mover",
			N_("Menú, moverse"),
			N_("Un toque muy corto: has pasado a otra opción."),
			lambda _rng: _seno(1100, 0.03) * _decae(0.03, 0.01),
			0.3,
		),
		(
			"elegir",
			N_("Menú, elegir"),
			N_("Dos notas que suben: has elegido la opción."),
			lambda _rng: _sec((880, 1320), 0.06, 0.15, 0.06),
			0.4,
		),
		(
			"atras",
			N_("Menú, atrás"),
			N_("Dos notas que bajan: has vuelto atrás o has cancelado."),
			lambda _rng: _sec((660, 440), 0.06, 0.15, 0.06),
			0.4,
		),
		(
			"borde",
			N_("Menú, borde"),
			N_("Un toque grave: no hay más opciones en esa dirección."),
			lambda _rng: _seno(180, 0.08) * _decae(0.08, 0.03) + 0.3 * _seno(360, 0.08) * _decae(0.08, 0.03),
			0.45,
		),
		(
			"abrir",
			N_("Menú, abrir"),
			N_("Tres notas rápidas que suben: se abre un menú."),
			lambda _rng: _sec((523.25, 659.25, 783.99), 0.05, 0.16, 0.06),
			0.4,
		),
		(
			"cerrar",
			N_("Menú, cerrar"),
			N_("Tres notas rápidas que bajan: se cierra el menú."),
			lambda _rng: _sec((783.99, 659.25, 523.25), 0.05, 0.16, 0.06),
			0.4,
		),
		(
			"ajuste",
			N_("Menú, ajuste"),
			N_("Un toque agudo y muy corto: has cambiado el valor de un ajuste."),
			lambda _rng: _seno(1500, 0.03) * _decae(0.03, 0.012),
			0.3,
		),
	)
	for clave, nombre, explicacion, hacer, pico in sonidos:
		_alta(f"interfaz/{clave}", nombre, explicacion, g, hacer, posicionable=False, pico=pico)


# ── La calle: semáforos, tráfico y bordillos ─────────────────────────────────


def _pio(segundos: float = 0.1) -> np.ndarray:
	"""El «pío» del semáforo sonoro: un silbido corto que sube."""
	return _barrido(2300, 3800, segundos) * _arco(segundos, 1.0)


def _semaforo_verde(_rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(1.0))
	for k in range(4):
		_poner(x, _pio(), 0.02 + k * 0.25)
	return x


def _semaforo_intermitente(_rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(0.5))
	for k in range(4):
		_poner(x, _pio(0.07), 0.01 + k * 0.125)
	return x


def _semaforo_rojo(rng: np.random.Generator) -> np.ndarray:
	"""Un «toc» lento cada segundo y medio: sirve para encontrar el poste mientras esperas."""
	x = np.zeros(_muestras(1.5))
	toc = (_seno(950, 0.06) + 0.3 * _seno(1900, 0.06)) * _decae(0.06, 0.012, 0.001)
	_poner(x, toc, 0.02)
	_poner(x, _aire(rng, 0.04, 0.4, 0.006), 0.02)
	return x


def _semaforo_pulsador(rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(0.5))
	_poner(x, _clac(rng, 0.035, 900, 7000), 0.0)
	_poner(x, _seno(210, 0.05) * _decae(0.05, 0.014), 0.0, 0.6)
	_poner(x, _nota(1480, 0.12, 0.04, (1, 0.3)), 0.12, 0.7)
	_poner(x, _nota(1480, 0.16, 0.05, (1, 0.3)), 0.26, 0.7)
	_poner(x, _aire(rng, 0.04, 0.3, 0.006), 0.12)
	return x


def _pasada(
	rng: np.random.Generator,
	segundos: float,
	f_motor: float,
	armonicos: int,
	dureza: float,
	rodadura: tuple[float, float],
	peso_motor: float,
) -> np.ndarray:
	"""Un vehículo que se acerca, pasa y se aleja: motor que baja de tono al pasar y ruido de rodadura.

	El motor del juego lo mueve además por la vía, así que aquí la subida y la
	bajada de volumen son suaves: solo evitan que el sonido empiece de golpe.
	"""
	t = _t(segundos)
	centro = segundos / 2.0
	envolvente = np.exp(-(((t - centro) / (segundos * 0.24)) ** 2))
	# Efecto Doppler: un seis por ciento más agudo al venir y más grave al irse.
	f = f_motor * (1.06 - 0.12 / (1.0 + np.exp(-(t - centro) * 5.0)))
	fase = PI2 * np.cumsum(f) / FRECUENCIA
	motor = np.zeros_like(t)
	for k in range(1, armonicos + 1):
		motor += np.sin(k * fase + rng.uniform(0, PI2)) / k**dureza
	motor *= 0.75 + 0.25 * np.sin(fase / 2.0)
	x = peso_motor * motor / (float(np.max(np.abs(motor))) or 1.0)
	x += _filtro(_ruido(rng, segundos), *rodadura) * 0.7
	x += 0.35 * _siseo(rng, segundos, 3000, 8000)
	return x * envolvente


def _autobus(rng: np.random.Generator) -> np.ndarray:
	x = _pasada(rng, 4.5, 62.0, 8, 1.0, (60, 1600), 1.0)
	# El soplido de los frenos de aire, lo que más lo distingue de un coche.
	soplido = _filtro(_ruido(rng, 0.45), 2500, 8000) * _decae(0.45, 0.12, 0.02)
	_poner(x, soplido, 2.9, 0.45)
	return x


def _trafico_ambiente(rng: np.random.Generator, intensidad: int) -> np.ndarray:
	"""Fondo de tráfico en estéreo: rumor continuo y oleadas de coches, más cuantos más carriles."""
	d = 10.0 + 0.25
	canales = []
	for _canal in range(2):
		rumor = _filtro(_ruido(rng, d), 50, 700) * (0.25 + 0.2 * intensidad)
		rumor += _filtro(_ruido(rng, d), 700, 4500) * (0.05 + 0.06 * intensidad)
		canales.append(rumor)
	x = _bucle(_estereo(*canales))
	duracion = len(x) / FRECUENCIA
	for _k in range((2, 5, 9)[intensidad - 1]):
		largo = rng.uniform(2.5, 4.0)
		coche = _pasada(rng, largo, rng.uniform(70, 120), 6, 1.2, (100, 2600), 0.6)
		inicio = rng.uniform(0.0, duracion)
		fuerza = rng.uniform(0.35, 0.75)
		# Cada coche cruza de un lado a otro: en un canal entra antes que en el otro.
		paneo = np.linspace(0.15, 0.85, len(coche)) if rng.random() < 0.5 else np.linspace(0.85, 0.15, len(coche))
		_poner_ciclico(x[:, 0], coche * np.cos(paneo * np.pi / 2.0), inicio, fuerza)
		_poner_ciclico(x[:, 1], coche * np.sin(paneo * np.pi / 2.0), inicio, fuerza)
	return x


def _bordillo(rng: np.random.Generator) -> np.ndarray:
	"""Bajar o subir un bordillo: el pie cae a otra altura (golpe grave) y la suela raspa el canto."""
	x = np.zeros(_muestras(0.3))
	_poner(x, _filtro(_ruido(rng, 0.06), 2000, 8000) * _arco(0.06), 0.0, 0.5)
	_poner(x, _filtro(_ruido(rng, 0.12), 100, 1200) * _decae(0.12, 0.035), 0.06)
	_poner(x, _seno(120, 0.12) * _decae(0.12, 0.04), 0.06, 0.8)
	_poner(x, _clac(rng, 0.03, 2500, 9000), 0.06, 0.5)
	return x


def _alta_calle() -> None:
	g = "calle"
	_alta(
		"semaforo/verde",
		N_("Semáforo en verde"),
		N_("Píos seguidos desde el poste del semáforo: los coches están parados y puedes cruzar. Camina hacia el que suena enfrente."),
		g,
		_semaforo_verde,
		bucle=True,
		pico=0.45,
	)
	_alta(
		"semaforo/intermitente",
		N_("Semáforo intermitente"),
		N_("Píos muy rápidos: el verde se acaba. Si no has empezado a cruzar, espera al siguiente."),
		g,
		_semaforo_intermitente,
		bucle=True,
		pico=0.45,
	)
	_alta(
		"semaforo/rojo",
		N_("Semáforo en rojo"),
		N_("Un toque lento desde el poste: está en rojo para ti. Sirve para encontrar el poste y esperar junto a él."),
		g,
		_semaforo_rojo,
		bucle=True,
		pico=0.4,
	)
	_alta(
		"semaforo/pulsador",
		N_("Pulsador del semáforo"),
		N_("Un clic y dos pitidos: has pulsado el botón para pedir el verde."),
		g,
		_semaforo_pulsador,
		pico=0.5,
	)
	_alta(
		"trafico/coche",
		N_("Coche que pasa"),
		N_("Un motor que se acerca, pasa y se aleja con ruido de ruedas: un coche circula por la calzada."),
		g,
		partial(_pasada, segundos=3.2, f_motor=95.0, armonicos=6, dureza=1.2, rodadura=(100, 2800), peso_motor=0.6),
		pico=0.6,
	)
	_alta(
		"trafico/moto",
		N_("Moto que pasa"),
		N_("Un motor agudo y zumbón que pasa deprisa: una moto."),
		g,
		partial(_pasada, segundos=2.6, f_motor=165.0, armonicos=12, dureza=0.7, rodadura=(300, 3500), peso_motor=1.3),
		pico=0.6,
	)
	_alta(
		"trafico/autobus",
		N_("Autobús que pasa"),
		N_("Un motor grave y largo, y al final el soplido de los frenos: un autobús."),
		g,
		_autobus,
		pico=0.65,
	)
	ambientes = (
		(1, "leve", N_("Tráfico leve"), N_("Un rumor lejano con algún coche suelto: una calle tranquila.")),
		(2, "medio", N_("Tráfico medio"), N_("Rumor continuo y coches frecuentes: una calle con bastante circulación.")),
		(3, "intenso", N_("Tráfico intenso"), N_("Rumor fuerte y coches sin parar: una avenida. Extrema el cuidado al cruzar.")),
	)
	for intensidad, clave, nombre, explicacion in ambientes:
		_alta(
			f"trafico/ambiente_{clave}",
			nombre,
			explicacion,
			g,
			partial(_trafico_ambiente, intensidad=intensidad),
			bucle=True,
			posicionable=False,
			pico=0.22 + 0.06 * intensidad,
		)
	_alta(
		"exterior/bordillo",
		N_("Bordillo"),
		N_("Un raspado y un golpe grave a tus pies: has bajado de la acera a la calzada, o has subido a la acera."),
		g,
		_bordillo,
		pico=0.6,
	)


# ── Fuentes típicas (bucles mono que se sitúan) ──────────────────────────────


def _frigorifico(rng: np.random.Generator) -> np.ndarray:
	d = 4.25
	t = _t(d)
	x = 0.6 * np.sin(PI2 * 50 * t) + 0.45 * np.sin(PI2 * 100 * t + 0.7) + 0.25 * np.sin(PI2 * 150 * t + 1.9) + 0.12 * np.sin(PI2 * 300 * t)
	x *= 0.9 + 0.1 * np.sin(PI2 * 0.75 * t)
	x += 0.35 * _filtro(_ruido(rng, d), 200, 1500)
	# El zumbido solo no se podría situar: el compresor también sisea y vibra en los agudos.
	x += 0.5 * _siseo(rng, d, 3000, 8000) * (0.8 + 0.2 * np.sin(PI2 * 25 * t))
	return _bucle(x)


def _reloj(rng: np.random.Generator) -> np.ndarray:
	"""Tic, tac: dos segundos justos, para que el bucle lleve el compás exacto."""
	x = np.zeros(_muestras(2.0))
	for inicio, f in ((0.0, 2600.0), (1.0, 1900.0)):
		_poner(x, _seno(f, 0.03) * _decae(0.03, 0.006, 0.0005), inicio)
		_poner(x, _filtro(_ruido(rng, 0.02), 2500, 10000) * _decae(0.02, 0.004, 0.0003), inicio, 0.8)
		_poner(x, _seno(420, 0.04) * _decae(0.04, 0.01), inicio, 0.3)
	return x


def _agua_corriente(rng: np.random.Generator, segundos: float, lo: float, hi: float, burbujas: int) -> np.ndarray:
	"""Agua que cae: ruido brillante con borboteo y gotas sueltas."""
	x = _filtro(_ruido(rng, segundos), lo, hi)
	borboteo = np.abs(_filtro(_ruido(rng, segundos), 4, 30))
	x *= 0.6 + 0.4 * borboteo / (float(np.max(borboteo)) or 1.0)
	x = _bucle(x)
	duracion = len(x) / FRECUENCIA
	for _k in range(burbujas):
		f = rng.uniform(700, 2400)
		gota = _barrido(f, f * 1.8, 0.035) * _decae(0.035, 0.01, 0.002)
		_poner_ciclico(x, gota, rng.uniform(0, duracion), rng.uniform(0.2, 0.6))
	return x


def _ventilador(rng: np.random.Generator) -> np.ndarray:
	d = 3.25
	t = _t(d)
	aspas = 0.75 + 0.25 * np.sin(PI2 * 13 * t)
	x = _filtro(_ruido(rng, d), 150, 5000) * aspas
	x += 0.3 * np.sin(PI2 * 100 * t) + 0.15 * np.sin(PI2 * 200 * t + 0.5)
	x += 0.3 * _siseo(rng, d, 3000, 9000) * aspas
	return _bucle(x)


def _television(rng: np.random.Generator) -> np.ndarray:
	"""Una tele en otra habitación: voces sin palabras, apagadas, con las eses asomando."""
	d = 5.0
	x = np.zeros(_muestras(d))
	instante = 0.0
	while instante < d - 0.05:
		hombre = rng.random() < 0.5
		f0 = rng.uniform(100, 140) if hombre else rng.uniform(180, 240)
		largo = rng.uniform(0.12, 0.26)
		formantes = (rng.uniform(450, 800), rng.uniform(1100, 2200))
		silaba = _vocal(f0, f0 * rng.uniform(0.85, 1.15), largo, formantes, largo * 0.6)
		_poner_ciclico(x, silaba, instante, rng.uniform(0.5, 1.0))
		if rng.random() < 0.35:
			ese = _filtro(_ruido(rng, 0.07), 3500, 8000) * _arco(0.07)
			_poner_ciclico(x, ese, instante + largo * 0.8, 0.25)
		# Pausas entre frases, como alguien que habla.
		instante += largo * rng.uniform(0.7, 1.0) + (rng.uniform(0.25, 0.6) if rng.random() < 0.15 else 0.0)
	return x


def _maquina_expendedora(rng: np.random.Generator) -> np.ndarray:
	d = 4.25
	t = _t(d)
	x = 0.5 * np.sin(PI2 * 100 * t) + 0.3 * np.sin(PI2 * 200 * t + 1.1) + 0.2 * np.sin(PI2 * 400 * t + 0.4)
	x += 0.4 * _filtro(_ruido(rng, d), 300, 3000)
	x += 0.3 * _siseo(rng, d, 3500, 9000)
	# El fluorescente del frontal: un zumbido agudo y fino que la distingue del frigorífico.
	x += 0.08 * np.sin(PI2 * 3900 * t) * (0.7 + 0.3 * np.sin(PI2 * 100 * t))
	x = _bucle(x)
	_poner_ciclico(x, _clac(rng, 0.03, 1000, 7000), 2.6, 0.9)
	return x


def _campanas(rng: np.random.Generator) -> np.ndarray:
	"""Dos campanadas de iglesia cada cinco segundos; la cola de la última empalma con la primera."""
	x = np.zeros(_muestras(5.0))
	parciales = (0.5, 1, 1.19, 1.5, 2, 2.52, 3, 4.1, 5.4, 8.2, 10.7)
	caidas = (1.2, 1, 0.8, 0.6, 0.5, 0.4, 0.3, 0.2, 0.15, 0.25, 0.2)
	for inicio, fuerza in ((0.0, 1.0), (1.6, 0.85)):
		_poner_ciclico(x, _campana(392, 3.0, parciales, caidas), inicio, fuerza)
		# El golpe del badajo: sin él, una campana grave no se sabría situar delante o detrás.
		_poner_ciclico(x, _aire(rng, 0.3, 2.5, 0.06), inicio, fuerza)
	return x


def _trino(rng: np.random.Generator) -> np.ndarray:
	"""Un pájaro: de una a cuatro notas que suben o bajan, con gorjeo."""
	notas = int(rng.integers(1, 5))
	x = np.zeros(_muestras(0.16 * notas + 0.05))
	base = rng.uniform(2800, 4600)
	for k in range(notas):
		d = rng.uniform(0.07, 0.13)
		t = _t(d)
		f = base + rng.uniform(-900, 1200) * (t / d) + 250 * np.sin(PI2 * rng.uniform(25, 45) * t)
		_poner(x, np.sin(PI2 * np.cumsum(f) / FRECUENCIA) * _arco(d), k * 0.15, rng.uniform(0.6, 1.0))
	return x


def _pajaros(rng: np.random.Generator) -> np.ndarray:
	x = np.zeros(_muestras(6.0))
	for _k in range(9):
		_poner_ciclico(x, _trino(rng), rng.uniform(0.0, 6.0), rng.uniform(0.4, 1.0))
	return x


def _alta_fuentes() -> None:
	g = "fuentes"
	_alta(
		"fuente/frigorifico",
		N_("Frigorífico"),
		N_("Un zumbido grave y constante. Suele estar en la cocina y sirve de referencia fija."),
		g,
		_frigorifico,
		bucle=True,
		pico=0.4,
	)
	_alta(
		"fuente/reloj",
		N_("Reloj de pared"),
		N_("Tic, tac, un golpe por segundo. Marca siempre el mismo punto de la habitación."),
		g,
		_reloj,
		bucle=True,
		pico=0.4,
	)
	_alta(
		"fuente/grifo",
		N_("Grifo abierto"),
		N_("Un chorro de agua fino contra el fregadero o el lavabo."),
		g,
		partial(_agua_corriente, segundos=3.25, lo=1500, hi=9000, burbujas=10),
		bucle=True,
		pico=0.4,
	)
	_alta(
		"fuente/ventilador",
		N_("Ventilador"),
		N_("Un soplo continuo con el batir de las aspas."),
		g,
		_ventilador,
		bucle=True,
		pico=0.4,
	)
	_alta(
		"fuente/television",
		N_("Televisión lejana"),
		N_("Voces apagadas que no se entienden: hay una tele encendida. Te dice hacia dónde queda el salón."),
		g,
		_television,
		bucle=True,
		pico=0.4,
	)
	_alta(
		"fuente/fuente_agua",
		N_("Fuente de agua"),
		N_("Agua que cae y borbotea, más llena que un grifo: una fuente en una plaza, un parque o un vestíbulo."),
		g,
		partial(_agua_corriente, segundos=4.25, lo=500, hi=8000, burbujas=40),
		bucle=True,
		pico=0.45,
	)
	_alta(
		"fuente/maquina_expendedora",
		N_("Máquina expendedora"),
		N_("Un zumbido eléctrico con un pitido muy fino y, de vez en cuando, un clic. Suele estar en pasillos y vestíbulos."),
		g,
		_maquina_expendedora,
		bucle=True,
		pico=0.4,
	)
	_alta(
		"fuente/campanas",
		N_("Campanas"),
		N_("Dos campanadas graves que se repiten: una iglesia o un reloj de torre, que se oye desde lejos."),
		g,
		_campanas,
		bucle=True,
		pico=0.5,
	)
	_alta(
		"fuente/pajaros",
		N_("Pájaros"),
		N_("Trinos sueltos desde un árbol o un seto."),
		g,
		_pajaros,
		bucle=True,
		pico=0.4,
	)


# ── Ambientes de fondo (estéreo, en bucle) ───────────────────────────────────

_DURACION_AMBIENTE = 10.0


def _fondo(rng: np.random.Generator, capas: tuple[tuple[float, float, float], ...]) -> np.ndarray:
	"""Fondo estéreo en bucle: capas de ruido (grave, agudo, peso) distintas en cada oído."""
	d = _DURACION_AMBIENTE + 0.25
	canales = []
	for _canal in range(2):
		x = np.zeros(_muestras(d))
		for lo, hi, peso in capas:
			x += peso * _filtro(_ruido(rng, d), lo, hi)
		canales.append(x)
	return _bucle(_estereo(*canales))


def _esparcir(rng: np.random.Generator, x: np.ndarray, suceso: np.ndarray, fuerza: float) -> None:
	"""Pone un suceso suelto en un momento y un lado cualesquiera del fondo."""
	inicio = rng.uniform(0.0, len(x) / FRECUENCIA)
	lado = rng.uniform(0.1, 0.9)
	_poner_ciclico(x[:, 0], suceso, inicio, fuerza * math.cos(lado * math.pi / 2.0))
	_poner_ciclico(x[:, 1], suceso, inicio, fuerza * math.sin(lado * math.pi / 2.0))


def _ambiente_casa(rng: np.random.Generator) -> np.ndarray:
	"""Una casa en silencio: casi nada, el aire de la habitación y algún crujido lejano."""
	x = _fondo(rng, ((40, 300, 1.0), (300, 2500, 0.12), (2500, 8000, 0.02)))
	for _k in range(2):
		crujido = _filtro(_ruido(rng, 0.06), 300, 2500) * _decae(0.06, 0.015)
		_esparcir(rng, x, crujido, 0.8)
	return x


def _ambiente_oficina(rng: np.random.Generator) -> np.ndarray:
	"""Oficina: aire acondicionado, teclas sueltas y un murmullo de fondo."""
	x = _fondo(rng, ((80, 600, 1.0), (600, 5000, 0.35), (5000, 10000, 0.08)))
	for _k in range(26):
		tecla = _filtro(_ruido(rng, 0.02), 1500, 7000) * _decae(0.02, 0.004, 0.0005)
		_esparcir(rng, x, tecla, rng.uniform(0.5, 1.4))
	for _k in range(8):
		largo = rng.uniform(0.15, 0.3)
		voz = _filtro(_vocal(rng.uniform(110, 220), rng.uniform(110, 220), largo, (600, 1400), largo * 0.6), None, 1800)
		_esparcir(rng, x, voz, rng.uniform(0.15, 0.3))
	return x


def _ambiente_pasillo(rng: np.random.Generator) -> np.ndarray:
	"""Pasillo: aire hueco, con resonancia, y unos pasos lejanos."""
	x = _fondo(rng, ((60, 400, 1.0), (180, 320, 0.8), (400, 3000, 0.15)))
	lado = rng.uniform(0.2, 0.8)
	inicio = rng.uniform(0.0, 6.0)
	for k in range(5):
		paso = _filtro(_ruido(rng, 0.12), 300, 1800) * _decae(0.12, 0.04)
		_poner_ciclico(x[:, 0], paso, inicio + k * 0.55, 1.2 * math.cos(lado * math.pi / 2.0))
		_poner_ciclico(x[:, 1], paso, inicio + k * 0.55, 1.2 * math.sin(lado * math.pi / 2.0))
	return x


def _ambiente_calle(rng: np.random.Generator) -> np.ndarray:
	"""Calle: rumor de ciudad, un par de coches lejanos y voces sueltas."""
	x = _fondo(rng, ((50, 700, 1.0), (700, 4000, 0.25), (4000, 9000, 0.05)))
	for _k in range(3):
		coche = _pasada(rng, rng.uniform(3.0, 4.5), rng.uniform(70, 110), 6, 1.2, (100, 2200), 0.5)
		_esparcir(rng, x, coche, rng.uniform(1.2, 2.2))
	for _k in range(5):
		largo = rng.uniform(0.15, 0.3)
		voz = _filtro(_vocal(rng.uniform(120, 240), rng.uniform(120, 240), largo, (650, 1500), largo * 0.6), None, 2200)
		_esparcir(rng, x, voz, rng.uniform(0.3, 0.6))
	return x


def _ambiente_parque(rng: np.random.Generator) -> np.ndarray:
	"""Parque: viento en las hojas, que viene y va, y pájaros alrededor."""
	x = _fondo(rng, ((1500, 7000, 1.0), (100, 600, 0.5)))
	t = np.arange(len(x)) / FRECUENCIA
	# Rachas con un número entero de ciclos en el bucle, para que el empalme no se note.
	racha = 0.65 + 0.35 * np.sin(PI2 * 2.0 * t / (len(x) / FRECUENCIA) + 1.0)
	x *= racha[:, None]
	for _k in range(12):
		_esparcir(rng, x, _trino(rng), rng.uniform(0.6, 1.6))
	return x


def _ambiente_cocina(rng: np.random.Generator) -> np.ndarray:
	"""Cocina: el frigorífico de fondo, algo que hierve y cacharros de vez en cuando."""
	x = _fondo(rng, ((60, 400, 0.8), (400, 3000, 0.2), (3000, 8000, 0.05)))
	t = np.arange(len(x)) / FRECUENCIA
	x += (0.5 * np.sin(PI2 * 50 * t) + 0.35 * np.sin(PI2 * 100 * t + 0.7))[:, None] * 0.6
	for _k in range(45):
		f = rng.uniform(250, 700)
		burbuja = _barrido(f, f * 1.6, 0.05) * _decae(0.05, 0.015, 0.004)
		_esparcir(rng, x, burbuja, rng.uniform(0.4, 0.9))
	for _k in range(3):
		cacharro = _campana(rng.uniform(1800, 3000), 0.25, (1, 1.52, 2.23, 3.1), (1, 0.6, 0.4, 0.3))
		_esparcir(rng, x, cacharro, rng.uniform(0.6, 1.0))
	return x


def _alta_ambientes() -> None:
	g = "ambientes"
	ambientes: tuple[tuple[str, str, str, Generador, float], ...] = (
		("casa", N_("Casa silenciosa"), N_("Casi nada: el aire de una casa tranquila y algún crujido."), _ambiente_casa, 0.12),
		("oficina", N_("Oficina"), N_("Aire acondicionado, teclados y un murmullo lejano."), _ambiente_oficina, 0.22),
		("pasillo", N_("Pasillo"), N_("Un aire hueco, que resuena, con pasos lejanos."), _ambiente_pasillo, 0.2),
		("calle", N_("Calle"), N_("El rumor de la ciudad, coches lejanos y alguna voz."), _ambiente_calle, 0.3),
		("parque", N_("Parque"), N_("Viento en las hojas y pájaros alrededor."), _ambiente_parque, 0.28),
		("cocina", N_("Cocina"), N_("El frigorífico de fondo, algo que hierve y cacharros."), _ambiente_cocina, 0.24),
	)
	for clave, nombre, explicacion, hacer, pico in ambientes:
		_alta(f"ambiente/{clave}", nombre, explicacion, g, hacer, bucle=True, posicionable=False, pico=pico)


# El orden de las altas es el orden del catálogo dentro de cada grupo.
_alta_orientacion()
_alta_pasos()
_alta_materiales()
_alta_puertas()
_alta_premios()
_alta_calle()
_alta_fuentes()
_alta_ambientes()
_alta_interfaz()


# ── API de síntesis ──────────────────────────────────────────────────────────


def nombres() -> list[str]:
	"""Las claves de todos los sonidos de serie, en el orden del catálogo."""
	return list(CATALOGO)


def _semilla(nombre: str) -> int:
	"""Semilla propia de cada sonido: estable entre ejecuciones (``hash()`` no lo es)."""
	return zlib.crc32(nombre.encode("utf-8"))


def _acabado(x: np.ndarray, pico: float, bucle: bool) -> np.ndarray:
	"""Quita la componente continua, fija el pico y, si no es un bucle, redondea los bordes."""
	x = np.asarray(x, dtype=np.float64)
	x = x - np.mean(x, axis=0)
	if not bucle:
		x = _bordes(x)
	maximo = float(np.max(np.abs(x))) if len(x) else 0.0
	if maximo > 0:
		x = x * (pico / maximo)
	return np.ascontiguousarray(x, dtype=np.float32)


def generar(nombre: str) -> np.ndarray:
	"""Sintetiza el sonido ``nombre`` del catálogo: float32, ``(n,)`` mono o ``(n, 2)`` estéreo.

	Lanza ``KeyError`` si no está en el catálogo (para un nombre cualquiera,
	úsese ``sonido_reserva``).
	"""
	definicion = CATALOGO[nombre]
	rng = np.random.default_rng(_semilla(nombre))
	return _acabado(_GENERADORES[nombre](rng), definicion.pico, definicion.bucle)


def generar_todos() -> dict[str, np.ndarray]:
	"""Todos los sonidos del catálogo. Tarda unos segundos (los ambientes son largos)."""
	return {nombre: generar(nombre) for nombre in CATALOGO}


# Familia → el sonido de serie que la representa cuando falta uno suyo.
_RESERVA_FAMILIA = {
	"pasos": "pasos/acera_izq_1",
	"golpe": "golpe/madera",
	"roce": "roce/madera",
	"puerta": "puerta/abrir",
	"escalera": "escalera/subir",
	"ascensor": "ascensor/llamada",
	"baliza": "baliza/pulso",
	"sonda": "sonda/objeto",
	"premio": "premio/aparece",
	"logro": "logro/logro",
	"interfaz": "interfaz/mover",
	"brujula": "brujula/norte",
	"eco": "eco/chasquido",
	"semaforo": "semaforo/pulsador",
	"exterior": "exterior/bordillo",
}


def sonido_reserva(nombre: str) -> np.ndarray:
	"""Sonido corto para cuando ``nombre`` no existe en ningún sitio: nunca silencio.

	Si el nombre es de una familia conocida («pasos/…», «golpe/…») suena algo
	de esa familia, para que el juego siga teniendo sentido; los pasos sobre un
	suelo conocido conservan incluso su suelo. Para lo demás, un toque neutro
	con agudos, que se puede situar y no se confunde con ningún aviso.
	"""
	if nombre in CATALOGO:
		return generar(nombre)
	familia, _barra, resto = nombre.replace("\\", "/").partition("/")
	if familia == "pasos":
		for suelo in sorted(SUELOS, key=len, reverse=True):
			if resto.startswith(suelo):
				pie = "der" if "der" in resto[len(suelo) :] else "izq"
				return generar(f"pasos/{suelo}_{pie}_1")
	if familia in _RESERVA_FAMILIA:
		return generar(_RESERVA_FAMILIA[familia])
	rng = np.random.default_rng(_semilla("reserva"))
	toque = _con_aire(rng, _nota(880, 0.12, 0.035, (1, 0.3, 0.15)), 0.5)
	return _acabado(toque, 0.4, False)


def fraccion_agudos(datos: np.ndarray, corte: float = CORTE_AGUDOS, frecuencia: int = FRECUENCIA) -> float:
	"""Parte de la energía de un sonido que queda por encima de ``corte`` Hz (0 a 1).

	Es la medida con la que se vigila que lo que hay que localizar se pueda
	localizar: sin agudos, el sonido binaural no distingue delante de detrás.
	"""
	x = np.asarray(datos, dtype=np.float64)
	if x.ndim == 2:
		x = x.mean(axis=1)
	if len(x) < 8:
		return 0.0
	energia = np.abs(np.fft.rfft(x)) ** 2
	total = float(energia.sum())
	if total <= 0:
		return 0.0
	f = np.fft.rfftfreq(len(x), 1.0 / frecuencia)
	return float(energia[f >= corte].sum()) / total


# ── Tratamiento de audio ─────────────────────────────────────────────────────


def apagar(datos: np.ndarray, corte: float = 900.0, frecuencia: int = FRECUENCIA) -> np.ndarray:
	"""Versión apagada de un sonido (paso bajo por FFT), para lo que queda detrás o tras una pared."""
	n = len(datos)
	if n < 8:
		return np.array(datos, dtype=np.float32)
	espectro = np.fft.rfft(datos, axis=0)
	f = np.fft.rfftfreq(n, 1.0 / frecuencia)
	g = 1.0 / (1.0 + (f / corte) ** 2)
	if np.ndim(datos) == 2:
		g = g[:, None]
	return np.fft.irfft(espectro * g, n, axis=0).astype(np.float32)


def a_mono(datos: np.ndarray) -> np.ndarray:
	"""Pasa a mono un sonido de varios canales.

	Con la media, una grabación estéreo de verdad (dos micrófonos algo
	desfasados) se anula en parte y suena hueca. Si la media se queda en menos
	de las tres cuartas partes del canal más fuerte, se usa ese canal solo.
	"""
	if datos.ndim == 1 or datos.shape[1] == 1:
		return datos.reshape(-1)
	media = datos.mean(axis=1)
	fuerza = np.sqrt(np.mean(np.square(datos.astype(np.float64)), axis=0))
	if fuerza.max() > 1e-6 and np.sqrt(np.mean(np.square(media.astype(np.float64)))) < 0.75 * fuerza.max():
		return np.ascontiguousarray(datos[:, int(np.argmax(fuerza))])
	return media


def remuestrear(datos: np.ndarray, de: int, a: int) -> np.ndarray:
	"""Cambia la frecuencia de muestreo de ``de`` a ``a`` hercios sin estropear los agudos.

	Se hace en el dominio de la frecuencia. Un sonido corto, de una vez; uno
	largo, por tramos que se solapan y se funden, porque convertir de golpe
	varios minutos cuesta segundos.
	"""
	de, a = int(de), int(a)
	if de <= 0 or a <= 0:
		raise ValueError(f"Frecuencia de muestreo no válida: de {de} a {a}")
	datos = np.asarray(datos, dtype=np.float32)
	if de == a or len(datos) < 2:
		return datos
	divisor = math.gcd(de, a)
	entra, sale = de // divisor, a // divisor  # cada «entra» muestras de entrada son «sale» de salida, exactas
	if len(datos) > 4 * 51200 and entra <= 2048:
		return _remuestrear_tramos(datos, entra, sale)
	return _remuestrear_entero(datos, de, a)


def _remuestrear_tramos(d: np.ndarray, a: int, b: int) -> np.ndarray:
	m = max(1, round(40960 / a))
	paso_e, paso_s = a * m, b * m  # lo que avanza cada tramo, en la entrada y en la salida
	sol_e, sol_s = a * max(1, m // 4), b * max(1, m // 4)  # lo que se solapa con el siguiente
	n_e, n_s = paso_e + sol_e, paso_s + sol_s
	canales = d[:, None] if d.ndim == 1 else d
	total = int(math.ceil(len(canales) / paso_e))
	salida = np.zeros((total * paso_s + sol_s, canales.shape[1]), np.float32)
	sube = np.linspace(0.0, 1.0, sol_s, dtype=np.float32)[:, None]
	k = min(n_s // 2 + 1, n_e // 2 + 1)
	for i in range(total):
		trozo = canales[i * paso_e : i * paso_e + n_e]
		if len(trozo) < n_e:
			trozo = np.concatenate([trozo, np.zeros((n_e - len(trozo), canales.shape[1]), trozo.dtype)])
		espectro = np.fft.rfft(trozo, axis=0)
		nuevo = np.zeros((n_s // 2 + 1, canales.shape[1]), espectro.dtype)
		nuevo[:k] = espectro[:k]
		y = (np.fft.irfft(nuevo, n_s, axis=0) * (n_s / n_e)).astype(np.float32)
		if i:
			y[:sol_s] *= sube  # entra fundiéndose con la cola del anterior
		if i < total - 1:
			y[paso_s:] *= 1.0 - sube
		salida[i * paso_s : i * paso_s + n_s] += y
	salida = salida[: max(2, int(round(len(canales) * b / a)))]
	return salida[:, 0] if d.ndim == 1 else salida


def _remuestrear_entero(d: np.ndarray, de: int, a: int) -> np.ndarray:
	n = max(2, int(round(len(d) * a / de)))
	canales = d[:, None] if d.ndim == 1 else d
	salida = np.empty((n, canales.shape[1]), np.float32)
	for c in range(canales.shape[1]):
		espectro = np.fft.rfft(canales[:, c].astype(np.float64))
		m = n // 2 + 1
		nuevo = np.zeros(m, np.complex128)
		k = min(m, len(espectro))
		nuevo[:k] = espectro[:k]
		salida[:, c] = np.fft.irfft(nuevo, n) * (n / len(d))
	return salida[:, 0] if d.ndim == 1 else salida


# ── Lectura y escritura ──────────────────────────────────────────────────────


def leer_audio(ruta: Path, mono: bool = False) -> tuple[np.ndarray, int]:
	"""Lee un fichero de audio (WAV, FLAC u OGG). Devuelve ``(datos, frecuencia)``.

	``datos`` es float32 entre -1 y 1, ``(n,)`` si es mono (o se pide mono) o
	``(n, 2)`` si es estéreo; los canales de más se descartan. No remuestrea:
	devuelve la frecuencia del fichero para que quien llama decida
	(``remuestrear``). Lanza ``OSError`` si el fichero no se puede abrir y
	``ValueError`` si no es audio válido.
	"""
	import soundfile as sf

	ruta = Path(ruta)
	if not ruta.is_file():
		raise FileNotFoundError(f"No existe el fichero de sonido: {ruta}")
	try:
		with sf.SoundFile(str(ruta)) as fichero:
			frecuencia = int(fichero.samplerate)
			datos = fichero.read(dtype="float32", always_2d=True)
	except sf.LibsndfileError as error:
		raise ValueError(f"No se pudo leer el sonido {ruta}: {error}") from error
	if frecuencia <= 0 or datos.shape[1] < 1:
		raise ValueError(f"El sonido {ruta} no tiene un formato válido ({datos.shape[1]} canales a {frecuencia} Hz)")
	if mono:
		datos = a_mono(datos)
	elif datos.shape[1] == 1:
		datos = datos[:, 0]  # un fichero mono se queda mono: no se gana nada duplicándolo
	else:
		datos = datos[:, :2]
	return np.ascontiguousarray(datos, dtype=np.float32), frecuencia


def escribir_audio(ruta: Path, datos: np.ndarray, frecuencia: int = FRECUENCIA) -> None:
	"""Escribe ``datos`` en ``ruta``; el formato lo decide la extensión (``.flac``, ``.wav`` u ``.ogg``).

	FLAC y WAV, a 16 bits. Se escribe en un fichero temporal al lado y se
	renombra, para no dejar nunca un sonido a medias si algo falla.
	"""
	import soundfile as sf

	ruta = Path(ruta)
	extension = ruta.suffix.lower()
	if extension not in FORMATOS_AUDIO:
		raise ValueError(f"Formato de sonido no admitido: «{extension}» ({ruta}). Use .flac, .wav u .ogg.")
	formato, subtipo = FORMATOS_AUDIO[extension]
	ruta.parent.mkdir(parents=True, exist_ok=True)
	temporal = ruta.with_name(ruta.name + ".tmp")
	try:
		sf.write(str(temporal), np.clip(datos, -1.0, 1.0), int(frecuencia), format=formato, subtype=subtipo)
		os.replace(temporal, ruta)
	except sf.LibsndfileError as error:
		raise ValueError(f"No se pudo escribir el sonido {ruta}: {error}") from error
	finally:
		if temporal.exists():
			temporal.unlink()


def fichero_de(carpeta: Path, nombre: str) -> Path | None:
	"""El fichero de ``carpeta`` que contiene el sonido ``nombre``, o None.

	Si está en varios formatos manda el que no es FLAC: es el que alguien ha
	puesto a mano para sustituir al de serie.
	"""
	for extension in EXTENSIONES:
		ruta = Path(carpeta) / f"{nombre}{extension}"
		if ruta.is_file():
			return ruta
	return None


def escribir_todos(carpeta: Path, formato: str = "flac", solo: str | None = None) -> list[Path]:
	"""Sintetiza y escribe en ``carpeta`` los sonidos de serie. Devuelve las rutas escritas.

	``solo`` es un patrón de nombres al estilo del intérprete de órdenes
	(``pasos/*``, ``*metal*``) para regenerar solo una parte.
	"""
	extension = "." + formato.lower().lstrip(".")
	if extension not in FORMATOS_AUDIO:
		raise ValueError(f"Formato de sonido no admitido: «{formato}». Use flac, wav u ogg.")
	carpeta = Path(carpeta)
	escritos: list[Path] = []
	for nombre in CATALOGO:
		if solo and not fnmatch.fnmatchcase(nombre, solo):
			continue
		ruta = carpeta / f"{nombre}{extension}"
		escribir_audio(ruta, generar(nombre))
		escritos.append(ruta)
	log.info("Sonidos de serie escritos en %s: %s ficheros.", carpeta, len(escritos))
	return escritos


def datos_catalogo(carpeta: Path | None = None, formato: str = "flac") -> dict:
	"""El contenido de ``catalogo.json``: grupos y, de cada sonido, nombre, explicación, grupo y fichero.

	Con ``carpeta``, el fichero y la duración de cada sonido salen de lo que
	hay escrito allí; lo que falte (o sin carpeta) se calcula sintetizando.
	Los textos van en español, el idioma de origen: quien los muestra los
	traduce.
	"""
	import soundfile as sf

	extension = "." + formato.lower().lstrip(".")
	sonidos: dict[str, dict] = {}
	for nombre, definicion in CATALOGO.items():
		ruta = fichero_de(carpeta, nombre) if carpeta is not None else None
		if ruta is not None:
			info = sf.info(str(ruta))
			duracion = info.frames / float(info.samplerate)
			fichero = f"{nombre}{ruta.suffix.lower()}"
		else:
			duracion = len(generar(nombre)) / FRECUENCIA
			fichero = f"{nombre}{extension}"
		sonidos[nombre] = {
			"nombre": definicion.nombre_origen(),
			"explicacion": definicion.explicacion_origen(),
			"grupo": definicion.grupo,
			"bucle": definicion.bucle,
			"posicionable": definicion.posicionable,
			"fichero": fichero,
			"duracion": round(duracion, 3),
		}
	return {
		"formato": FORMATO_CATALOGO,
		"grupos": [{"id": identificador, "nombre": nombre} for identificador, nombre in GRUPOS],
		"sonidos": sonidos,
	}


def escribir_catalogo(carpeta: Path, formato: str = "flac", carpeta_sonidos: Path | None = None) -> Path:
	"""Escribe ``catalogo.json`` en ``carpeta`` (de forma atómica) y devuelve su ruta.

	El catálogo es común a todos los paquetes de sonidos y vive en ``data/sounds``;
	los ficheros con los que se calcula la duración de cada sonido son los del
	paquete por defecto, que están en ``carpeta_sonidos`` (la propia ``carpeta``
	si no se indica). El campo ``fichero`` es relativo a la carpeta del paquete.
	"""
	carpeta = Path(carpeta)
	carpeta.mkdir(parents=True, exist_ok=True)
	ruta = carpeta / "catalogo.json"
	temporal = ruta.with_name(ruta.name + ".tmp")
	origen = carpeta if carpeta_sonidos is None else Path(carpeta_sonidos)
	texto = json.dumps(datos_catalogo(origen, formato), ensure_ascii=False, indent="\t")
	temporal.write_text(texto + "\n", encoding="utf-8")
	os.replace(temporal, ruta)
	return ruta
