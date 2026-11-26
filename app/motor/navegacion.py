"""Rutas y distancias de camino: por dónde se va andando de un punto a otro.

Dos niveles:

- **Rejilla fina por planta.** El suelo se trocea en celdas pequeñas y solo
  cuentan como libres las que dejan sitio a una persona (lejos de paredes y de
  muebles). Buscar por esas celdas resuelve por igual una habitación en ele,
  un salón amueblado y una calle con aceras, sin casos especiales. Las celdas
  se calculan cuando hacen falta y se recuerdan.
- **Grafo de conectores entre plantas.** Escaleras, rampas y ascensores unen
  las rejillas de las plantas.

Una puerta cerrada cuenta como paso (el alumno puede abrirla); una con llave
y una ventana, no. ``evitar`` permite cortar aberturas para pedir una ruta
alternativa.

Lo usan las actividades y los exámenes (cociente camino real / camino óptimo,
salida más corta), la lista de cercanos (distancia de camino) y la baliza.
Además expone el grafo de espacios (qué espacio da a cuál y por dónde), que es
lo que recorre el modo de movimiento por salas.
"""

from __future__ import annotations

import heapq
import logging
import math
import time
from collections import OrderedDict, deque
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.dominio import geometria as geo
from app.dominio.geometria import Punto
from app.dominio.modelo import Abertura
from app.motor.mundo import InfoAbertura, Mundo, Seg

log = logging.getLogger(__name__)

# Lado de las celdas: fino en interiores (puertas de 70 cm), más grueso en la calle (distancias largas).
PASO_INTERIOR = 0.2
PASO_EXTERIOR = 0.4
# Sitio que hay que dejar a cada lado: algo menos que el radio de la persona.
HOLGURA = 0.22
# En el vano de una puerta se exige menos, o una puerta estrecha no tendría ninguna celda libre.
HOLGURA_PUERTA = 0.12
ZONA_PUERTA = 0.4
# Hasta dónde se busca una celda libre junto a un punto que cae en una pared o dentro de un mueble.
RADIO_ENGANCHE = 1.5
RAIZ2 = math.sqrt(2.0)
MAX_CAMPOS = 24

Lugar = tuple[str, float, float]
Celda = tuple[int, int]

_VECINAS: tuple[tuple[int, int, float], ...] = (
	(1, 0, 1.0),
	(-1, 0, 1.0),
	(0, 1, 1.0),
	(0, -1, 1.0),
	(1, 1, RAIZ2),
	(1, -1, RAIZ2),
	(-1, 1, RAIZ2),
	(-1, -1, RAIZ2),
)


def lugar(valor: Any) -> Lugar:
	"""Convierte una ``Posicion`` (o una terna planta, x, y) en un lugar ``(planta, x, y)``."""
	if hasattr(valor, "planta") and hasattr(valor, "x"):
		return str(valor.planta), float(valor.x), float(valor.y)
	planta, x, y = valor[0], valor[1], valor[2]
	return str(planta), float(x), float(y)


@dataclass(slots=True)
class Ruta:
	"""Un camino andando: puntos por planta, longitud y conectores que usa."""

	puntos: list[Lugar] = field(default_factory=list)
	longitud: float = 0.0
	conectores: list[str] = field(default_factory=list)

	def plantas(self) -> list[str]:
		"""Plantas por las que pasa, en orden y sin repetir seguidas."""
		vistas: list[str] = []
		for planta_id, _x, _y in self.puntos:
			if not vistas or vistas[-1] != planta_id:
				vistas.append(planta_id)
		return vistas

	def puntos_de(self, planta_id: str) -> list[Punto]:
		"""Los puntos del camino que caen en una planta."""
		return [(x, y) for planta, x, y in self.puntos if planta == planta_id]

	def giros(self, minimo: float = 30.0) -> int:
		"""Número de giros de al menos ``minimo`` grados (para comparar la dificultad de dos rutas)."""
		cuenta = 0
		for i in range(1, len(self.puntos) - 1):
			a, b, c = self.puntos[i - 1], self.puntos[i], self.puntos[i + 1]
			if a[0] != b[0] or b[0] != c[0]:
				continue
			if math.hypot(b[1] - a[1], b[2] - a[2]) < 1e-6 or math.hypot(c[1] - b[1], c[2] - b[2]) < 1e-6:
				continue
			giro = geo.diferencia_rumbos(geo.rumbo_entre(a[1:], b[1:]), geo.rumbo_entre(b[1:], c[1:]))
			if abs(giro) >= minimo:
				cuenta += 1
		return cuenta


@dataclass(slots=True)
class Salida:
	"""Una salida del edificio con lo que hay que andar hasta ella."""

	abertura: Abertura
	planta_id: str
	distancia: float
	ruta: Ruta | None = None


@dataclass(slots=True)
class Enlace:
	"""Un paso de un espacio a otro: por una abertura, por un conector o por un borde abierto."""

	tipo: str  # abertura | conector | abierto
	id: str
	origen: str
	destino: str
	punto: Lugar
	punto_destino: Lugar
	nombre: str = ""


@dataclass(slots=True)
class Campo:
	"""Distancias de camino desde un punto a las celdas alcanzadas, con por dónde se llegó a cada una."""

	planta_id: str
	paso: float
	origen: Punto
	distancias: dict[Celda, float]
	previas: dict[Celda, Celda | None]
	completo: bool = True


@dataclass(slots=True)
class _Precalculo:
	"""Un recorrido a lo ancho a medio hacer (ver ``Navegador.precalcular``): lo que falta por mirar y lo ya alcanzado."""

	planta_id: str
	cola: deque[Celda]
	vistas: set[Celda]


class Navegador:
	"""Calcula rutas, distancias de camino y salidas sobre un ``Mundo``."""

	def __init__(self, mundo: Mundo, con_llave: bool = False) -> None:
		"""``con_llave`` hace que las puertas con llave también cuenten como paso (para el profesional)."""
		self.mundo = mundo
		self.con_llave = con_llave
		self._libres: dict[str, dict[Celda, int]] = {}
		self._campos: OrderedDict[tuple, Campo] = OrderedDict()
		self._firma: tuple | None = None
		self._version_firma = -1
		self._grafo: dict[str, list[Enlace]] | None = None
		# Componentes conexas ya conocidas (celda → número), por planta: ver ``_buscar`` y ``precalcular``.
		self._componentes: dict[str, dict[Celda, int]] = {}
		self._numero_componente = 0
		self._precalculo: _Precalculo | None = None

	# ── Celdas ──

	def paso(self, planta_id: str) -> float:
		"""Lado de las celdas de esa planta."""
		indice = self.mundo.planta(planta_id)
		return PASO_EXTERIOR if indice is not None and indice.planta.exterior else PASO_INTERIOR

	def _comprobar_firma(self) -> None:
		"""Tira lo calculado si ha cambiado qué puertas tienen la llave echada.

		Solo puede haber cambiado si el mundo ha cambiado de versión (cada
		cambio de puerta la sube): así no se recorren las miles de aberturas de
		un barrio en cada búsqueda.
		"""
		if self._version_firma == self.mundo.version and self._firma is not None:
			return
		self._version_firma = self.mundo.version
		firma = tuple(
			sorted(
				info.abertura.id
				for indice in self.mundo.plantas()
				for info in indice.aberturas
				if self.mundo.estado_abertura(info.abertura.id) == "con_llave"
			)
		)
		if firma != self._firma:
			self._firma = firma
			self._libres.clear()
			self._campos.clear()
			self._grafo = None
			self._componentes.clear()
			self._precalculo = None

	def _para(self, seg: Seg) -> bool:
		"""Si ese segmento corta el camino (una puerta cerrada sin llave no: se puede abrir)."""
		if not seg.paso:
			return False
		if seg.clase == "puerta":
			return not self.con_llave and self.mundo.estado_abertura(seg.elemento_id) == "con_llave"
		if seg.clase == "objeto":
			# Un torno o una mampara que se abren son como una puerta cerrada: se puede pasar abriéndolos.
			info = self.mundo.objeto(seg.elemento_id)
			return info is None or not info.paso_libre
		return True

	def _estado_celda(self, planta_id: str, celda: Celda) -> int:
		"""0 = ocupada, 1 = libre, 2 = libre en el vano de una puerta (hay que comprobar cada movimiento)."""
		libres = self._libres.setdefault(planta_id, {})
		estado = libres.get(celda)
		if estado is not None:
			return estado
		paso = self.paso(planta_id)
		x, y = (celda[0] + 0.5) * paso, (celda[1] + 0.5) * paso
		estado = self._calcular(planta_id, x, y)
		libres[celda] = estado
		return estado

	def _calcular(self, planta_id: str, x: float, y: float) -> int:
		mundo = self.mundo
		if not mundo.transitable(planta_id, x, y) or mundo.dentro_de_objeto(planta_id, x, y, fijos=True) is not None:
			return 0
		minima = HOLGURA
		for seg in mundo.segs_en_caja(planta_id, x - HOLGURA, y - HOLGURA, x + HOLGURA, y + HOLGURA):
			if not self._para(seg):
				continue
			sx, sy = seg.bx - seg.ax, seg.by - seg.ay
			largo2 = sx * sx + sy * sy
			t = 0.0 if largo2 < 1e-18 else ((x - seg.ax) * sx + (y - seg.ay) * sy) / largo2
			t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
			d = math.hypot(x - seg.ax - sx * t, y - seg.ay - sy * t)
			if d < minima:
				minima = d
		if minima >= HOLGURA:
			return 1
		if minima < HOLGURA_PUERTA:
			return 0
		for _d, info in mundo.aberturas_cerca(planta_id, x, y, ZONA_PUERTA):
			if info.abertura.tipo != "ventana" and info.sobre_pared:
				return 2
		return 0

	def _centro(self, planta_id: str, celda: Celda) -> Punto:
		paso = self.paso(planta_id)
		return (celda[0] + 0.5) * paso, (celda[1] + 0.5) * paso

	def _celda(self, planta_id: str, x: float, y: float) -> Celda:
		paso = self.paso(planta_id)
		return math.floor(x / paso), math.floor(y / paso)

	def _enganchar(self, planta_id: str, x: float, y: float) -> Celda | None:
		"""Celda libre más cercana a un punto (él mismo puede caer en una pared o dentro de un mueble).

		Entre las cercanas se prefiere una a la que se llegue en línea recta sin
		atravesar nada (ver ``_preferida``): así una referencia colgada en una
		pared se engancha por su lado de la pared y un mueble pegado a un
		tabique, por su habitación y no por la de detrás.
		"""
		base = self._celda(planta_id, x, y)
		if self._estado_celda(planta_id, base):
			return base
		paso = self.paso(planta_id)
		alcance = int(RADIO_ENGANCHE / paso) + 1
		candidatas: list[tuple[float, Celda]] = []
		for dx in range(-alcance, alcance + 1):
			for dy in range(-alcance, alcance + 1):
				celda = (base[0] + dx, base[1] + dy)
				cx, cy = (celda[0] + 0.5) * paso, (celda[1] + 0.5) * paso
				d = math.hypot(cx - x, cy - y)
				if d <= RADIO_ENGANCHE and self._estado_celda(planta_id, celda):
					candidatas.append((d, celda))
		candidatas.sort()
		return self._preferida(planta_id, x, y, candidatas)

	def _preferida(self, planta_id: str, x: float, y: float, candidatas: list[tuple[float, Celda]]) -> Celda | None:
		"""De unas celdas libres ordenadas por distancia a (x, y), la mejor para empezar o acabar en ese punto.

		El punto puede estar dentro de un mueble (se pide ir a un armario): sus
		propios lados no cuentan, porque de otro modo ninguna celda lo «vería»
		y se cogería la más cercana a su centro, que si el mueble está pegado a
		un tabique cae en la habitación de detrás (la ruta acababa al otro
		lado de la pared). Por orden de preferencia:

		1. la más cercana con la recta hasta el punto libre. Si el punto está
		   dentro de un mueble, otros muebles en medio no cuentan (se alcanza
		   por encima, como con la mano, y exigir que no haya ninguno llevaría
		   a celdas lejanas); solo las paredes y las puertas. Si no lo está,
		   cuenta todo (una valla entre la acera y la calzada también separa);
		2. la más cercana del mismo espacio que el punto;
		3. la más cercana.
		"""
		if not candidatas:
			return None
		propio = self.mundo.dentro_de_objeto(planta_id, x, y)
		propio_id = propio.objeto.id if propio is not None else ""
		espacio = self.mundo.espacio_en(planta_id, x, y)
		segunda: Celda | None = None
		for _d, celda in candidatas:
			pared = any(
				self._para(seg) and seg.elemento_id != propio_id and not (propio_id and seg.clase == "objeto")
				for _t, seg in self.mundo.cortes(planta_id, (x, y), self._centro(planta_id, celda), "paso")
			)
			if not pared:
				return celda
			if segunda is None and espacio is not None:
				centro = self._centro(planta_id, celda)
				suyo = self.mundo.espacio_en(planta_id, centro[0], centro[1])
				if suyo is not None and suyo.id == espacio.id:
					segunda = celda
		return segunda if segunda is not None else candidatas[0][1]

	def _cortado(self, planta_id: str, a: Punto, b: Punto, evitar: frozenset[str] = frozenset()) -> bool:
		"""Si el tramo ab atraviesa algo que corta el camino."""
		for _t, seg in self.mundo.cortes(planta_id, a, b, "paso"):
			if self._para(seg):
				return True
		if evitar:
			# Las aberturas cortadas se miran aparte: un hueco sin hoja no tiene segmento en la rejilla.
			for abertura_id in evitar:
				info = self.mundo.abertura(abertura_id)
				if (
					info is not None
					and info.planta_id == planta_id
					and geo.corte_segmentos(a, b, info.abertura.a, info.abertura.b) is not None
				):
					return True
		return False

	# ── Búsqueda en una planta ──

	def _buscar(
		self,
		planta_id: str,
		origen: Punto,
		destino: Punto | None = None,
		radio: float | None = None,
		evitar: frozenset[str] = frozenset(),
	) -> Campo | None:
		"""Distancias de camino desde ``origen``; con ``destino`` se para al llegar a él (A*)."""
		self._comprobar_firma()
		inicio = self._enganchar(planta_id, origen[0], origen[1])
		if inicio is None:
			return None
		clave = (planta_id, inicio, radio, evitar)
		if destino is None:
			guardado = self._campos.get(clave)
			if guardado is not None:
				self._campos.move_to_end(clave)
				return guardado
		meta: Celda | None = None
		if destino is not None:
			meta = self._enganchar(planta_id, destino[0], destino[1])
			if meta is None:
				return None
		componentes = self._componentes.get(planta_id)
		if meta is not None and not evitar and componentes is not None:
			# Si ya se sabe que el origen y la meta están en trozos sin camino entre ellos, la búsqueda
			# recorrería el trozo entero para acabar sin ruta: se contesta lo mismo sin buscar.
			suya = componentes.get(inicio)
			if suya is not None and componentes.get(meta) != suya:
				return None
		paso = self.paso(planta_id)
		centro_inicio = self._centro(planta_id, inicio)
		arranque = math.hypot(centro_inicio[0] - origen[0], centro_inicio[1] - origen[1])
		distancias: dict[Celda, float] = {inicio: arranque}
		previas: dict[Celda, Celda | None] = {inicio: None}
		cerradas: set[Celda] = set()
		monton: list[tuple[float, float, Celda]] = [(arranque, arranque, inicio)]
		estado_celda = self._estado_celda
		# Lo que ya está calculado se lee directamente del diccionario (es lo que más se repite).
		consultar = self._libres.setdefault(planta_id, {}).get
		empujar = heapq.heappush
		sacar = heapq.heappop
		hypot = math.hypot
		infinito = math.inf
		distancia_de = distancias.get
		completo = True
		agotada = True
		while monton:
			_prioridad, d, celda = sacar(monton)
			if celda in cerradas:
				continue
			cerradas.add(celda)
			if celda == meta:
				agotada = False
				break
			if radio is not None and d > radio:
				completo = False
				continue
			cx, cy = celda
			estado = consultar(celda)
			if estado is None:
				estado = estado_celda(planta_id, celda)
			for dx, dy, coste in _VECINAS:
				vecina = (cx + dx, cy + dy)
				if vecina in cerradas:
					continue
				estado_vecina = consultar(vecina)
				if estado_vecina is None:
					estado_vecina = estado_celda(planta_id, vecina)
				if not estado_vecina:
					continue
				if dx and dy:
					lado_x = consultar((cx + dx, cy))
					if lado_x is None:
						lado_x = estado_celda(planta_id, (cx + dx, cy))
					if not lado_x:
						# No se cortan las esquinas: en diagonal solo si los dos lados están libres.
						continue
					lado_y = consultar((cx, cy + dy))
					if lado_y is None:
						lado_y = estado_celda(planta_id, (cx, cy + dy))
					if not lado_y:
						continue
				if estado == 2 or estado_vecina == 2 or evitar:
					a = ((cx + 0.5) * paso, (cy + 0.5) * paso)
					b = ((vecina[0] + 0.5) * paso, (vecina[1] + 0.5) * paso)
					if self._cortado(planta_id, a, b, evitar):
						continue
				nueva = d + coste * paso
				if nueva < distancia_de(vecina, infinito):
					distancias[vecina] = nueva
					previas[vecina] = celda
					prioridad = nueva
					if meta is not None:
						prioridad += hypot(vecina[0] - meta[0], vecina[1] - meta[1]) * paso
					empujar(monton, (prioridad, nueva, vecina))
		if agotada and radio is None and not evitar:
			# Se ha recorrido todo lo alcanzable desde el origen: es un trozo entero, se apunta.
			self._apuntar_componente(planta_id, cerradas)
		if meta is not None and meta not in cerradas:
			return None
		campo = Campo(planta_id, paso, origen, distancias, previas, completo and meta is None)
		if destino is None:
			self._campos[clave] = campo
			while len(self._campos) > MAX_CAMPOS:
				self._campos.popitem(last=False)
		return campo

	def _apuntar_componente(self, planta_id: str, celdas: Iterable[Celda]) -> None:
		"""Apunta un trozo conexo completo (todas las celdas a las que se llega desde una, y solo esas)."""
		componentes = self._componentes.setdefault(planta_id, {})
		self._numero_componente += 1
		numero = self._numero_componente
		for celda in celdas:
			componentes[celda] = numero

	def componente(self, origen: Any) -> int | None:
		"""Número del trozo conexo en el que está un lugar, si ya se conoce entero (None si aún no)."""
		o = lugar(origen)
		if self.mundo.planta(o[0]) is None:
			return None
		self._comprobar_firma()
		inicio = self._enganchar(o[0], o[1], o[2])
		componentes = self._componentes.get(o[0])
		if inicio is None or componentes is None:
			return None
		return componentes.get(inicio)

	def precalcular(self, origen: Any, presupuesto: float) -> bool:
		"""Calcula por adelantado, durante como mucho ``presupuesto`` segundos, el trozo de planta al que se llega desde un lugar.

		Por qué: la primera búsqueda por una plaza de 300 metros calcula cientos
		de miles de celdas y tarda segundos. El reproductor llama a esto en cada
		fotograma con unos milisegundos (y la pantalla de carga con más): cuando
		el alumno pida una ruta o la lista de cercanos, las celdas ya están
		calculadas y, si el destino está en otro trozo sin camino, se sabe al
		momento. Se puede interrumpir y seguir en cualquier fotograma; lo
		calculado es lo mismo que calcularía la búsqueda, así que los
		resultados no cambian. Devuelve True cuando ya no queda nada por hacer
		para ese lugar.
		"""
		o = lugar(origen)
		if self.mundo.planta(o[0]) is None:
			return True
		self._comprobar_firma()
		planta_id = o[0]
		inicio = self._enganchar(planta_id, o[1], o[2])
		if inicio is None:
			return True
		componentes = self._componentes.get(planta_id)
		if componentes is not None and inicio in componentes:
			return True
		trabajo = self._precalculo
		if trabajo is None or trabajo.planta_id != planta_id or inicio not in trabajo.vistas:
			# El alumno está en otro trozo (o es la primera vez): se empieza desde donde está; lo ya calculado se conserva.
			trabajo = _Precalculo(planta_id, deque([inicio]), {inicio})
			self._precalculo = trabajo
		limite = time.perf_counter() + max(0.0, presupuesto)
		paso = self.paso(planta_id)
		consultar = self._libres.setdefault(planta_id, {}).get
		estado_celda = self._estado_celda
		cola = trabajo.cola
		vistas = trabajo.vistas
		hechas = 0
		while cola:
			hechas += 1
			if hechas % 32 == 0 and time.perf_counter() >= limite:
				return False
			celda = cola.popleft()
			cx, cy = celda
			estado = consultar(celda)
			if estado is None:
				estado = estado_celda(planta_id, celda)
			# Las mismas reglas de paso que la búsqueda (``_buscar``) sin aberturas cortadas.
			for dx, dy, _coste in _VECINAS:
				vecina = (cx + dx, cy + dy)
				if vecina in vistas:
					continue
				estado_vecina = consultar(vecina)
				if estado_vecina is None:
					estado_vecina = estado_celda(planta_id, vecina)
				if not estado_vecina:
					continue
				if dx and dy and not (estado_celda(planta_id, (cx + dx, cy)) and estado_celda(planta_id, (cx, cy + dy))):
					continue
				if estado == 2 or estado_vecina == 2:
					a = ((cx + 0.5) * paso, (cy + 0.5) * paso)
					b = ((vecina[0] + 0.5) * paso, (vecina[1] + 0.5) * paso)
					if self._cortado(planta_id, a, b):
						continue
				vistas.add(vecina)
				cola.append(vecina)
		self._apuntar_componente(planta_id, vistas)
		self._precalculo = None
		return True

	def _distancia_en(self, campo: Campo, x: float, y: float) -> float | None:
		"""Distancia de camino del origen del campo a un punto, o None si no se llega.

		Si se llega en línea recta, es exacta; si no, es la del camino por las
		celdas, que puede pasarse unos centímetros por metro (va en zigzag).
		"""
		recta = math.hypot(x - campo.origen[0], y - campo.origen[1])
		if recta < 0.05 or (
			(campo.completo or recta <= self._radio_de(campo))
			and self._recta_libre(campo.planta_id, campo.origen, (x, y), frozenset(), estricto=False)
		):
			return recta
		celda = self._celda(campo.planta_id, x, y)
		if celda not in campo.distancias:
			celda_libre = self._enganchar_en(campo, x, y)
			if celda_libre is None:
				return None
			celda = celda_libre
		centro = self._centro(campo.planta_id, celda)
		return campo.distancias[celda] + math.hypot(centro[0] - x, centro[1] - y)

	def _enganchar_en(self, campo: Campo, x: float, y: float) -> Celda | None:
		"""Celda alcanzada del campo más cercana a un punto, prefiriendo las que se ven desde él."""
		base = self._celda(campo.planta_id, x, y)
		alcance = int(RADIO_ENGANCHE / campo.paso) + 1
		candidatas: list[tuple[float, Celda]] = []
		for dx in range(-alcance, alcance + 1):
			for dy in range(-alcance, alcance + 1):
				celda = (base[0] + dx, base[1] + dy)
				if celda not in campo.distancias:
					continue
				centro = self._centro(campo.planta_id, celda)
				d = math.hypot(centro[0] - x, centro[1] - y)
				if d <= RADIO_ENGANCHE:
					candidatas.append((d, celda))
		candidatas.sort()
		return self._preferida(campo.planta_id, x, y, candidatas)

	def _camino_en(self, campo: Campo, x: float, y: float, evitar: frozenset[str] = frozenset()) -> list[Punto] | None:
		"""Puntos del camino desde el origen del campo hasta (x, y), con las esquinas ya holgadas."""
		celda = self._celda(campo.planta_id, x, y)
		if celda not in campo.distancias:
			celda_libre = self._enganchar_en(campo, x, y)
			if celda_libre is None:
				return None
			celda = celda_libre
		celdas: list[Celda] = []
		actual: Celda | None = celda
		while actual is not None:
			celdas.append(actual)
			actual = campo.previas.get(actual)
		celdas.reverse()
		puntos = [campo.origen] + [self._centro(campo.planta_id, c) for c in celdas] + [(x, y)]
		return self._estirar(campo.planta_id, puntos, evitar)

	def _recta_libre(self, planta_id: str, a: Punto, b: Punto, evitar: frozenset[str], estricto: bool = True) -> bool:
		"""Si se puede ir recto de ``a`` a ``b`` con sitio a los lados (todas las celdas que pisa están libres).

		Sin ``estricto`` se perdonan los dos extremos (pueden estar pegados a una
		pared o a un mueble) y los vanos de las puertas.
		"""
		largo = math.hypot(b[0] - a[0], b[1] - a[1])
		paso = self.paso(planta_id)
		tramos = max(1, int(largo / (paso * 0.5)))
		margen = 0 if estricto else int(0.6 / (paso * 0.5)) + 1
		# Al estirar una ruta larga esto se llama cientos de veces: lo ya calculado se lee directamente.
		consultar = self._libres.setdefault(planta_id, {}).get
		suelo = math.floor
		for i in range(1 + margen, tramos - margen):
			t = i / tramos
			x, y = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
			celda = (suelo(x / paso), suelo(y / paso))
			estado = consultar(celda)
			if estado is None:
				estado = self._estado_celda(planta_id, celda)
			if estado != 1 and (estricto or estado == 0):
				return False
		return not self._cortado(planta_id, a, b, evitar)

	@staticmethod
	def _radio_de(campo: Campo) -> float:
		"""Hasta dónde llegó la búsqueda de un campo incompleto (la mayor distancia que alcanzó)."""
		return max(campo.distancias.values(), default=0.0)

	def _estirar(self, planta_id: str, puntos: list[Punto], evitar: frozenset[str]) -> list[Punto]:
		"""Quita los puntos intermedios que sobran: el camino en zigzag de las celdas pasa a ser de tramos rectos."""
		if len(puntos) <= 2:
			return puntos
		resultado = [puntos[0]]
		ancla = 0
		i = 1
		while i < len(puntos) - 1:
			if not self._recta_libre(planta_id, puntos[ancla], puntos[i + 1], evitar):
				resultado.append(puntos[i])
				ancla = i
			i += 1
		resultado.append(puntos[-1])
		limpio = [resultado[0]]
		for punto in resultado[1:]:
			if math.hypot(punto[0] - limpio[-1][0], punto[1] - limpio[-1][1]) > 1e-6:
				limpio.append(punto)
		return limpio

	# ── Conectores entre plantas ──

	def _nodos_conectores(self) -> tuple[dict[str, Lugar], list[tuple[str, str, float, str]]]:
		"""Extremos de los conectores (nodo → lugar) y pasos entre ellos (origen, destino, metros andados, conector)."""
		nodos: dict[str, Lugar] = {}
		pasos: list[tuple[str, str, float, str]] = []
		for conector in self.mundo.entorno.conectores:
			for numero, tramo in enumerate(conector.tramos):
				if self.mundo.planta(tramo.desde.planta) is None or self.mundo.planta(tramo.hasta.planta) is None:
					continue
				abajo, arriba = f"{conector.id}/{numero}/abajo", f"{conector.id}/{numero}/arriba"
				nodos[abajo] = (tramo.desde.planta, tramo.desde.x, tramo.desde.y)
				nodos[arriba] = (tramo.hasta.planta, tramo.hasta.x, tramo.hasta.y)
				largo = max(0.5, tramo.longitud_m)
				baja = str(conector.datos.get("sentido") or "") == "baja"
				if conector.tipo != "escalera_mecanica" or not baja:
					pasos.append((abajo, arriba, largo, conector.id))
				if conector.tipo != "escalera_mecanica" or baja:
					pasos.append((arriba, abajo, largo, conector.id))
			validas = [(numero, parada) for numero, parada in enumerate(conector.paradas) if self.mundo.planta(parada.planta) is not None]
			for numero, parada in validas:
				nodos[f"{conector.id}/p{numero}"] = (parada.planta, parada.puerta.x, parada.puerta.y)
			for numero, _parada in validas:
				for otra, _parada_b in validas:
					if numero != otra:
						# En el ascensor no se anda: cuesta un metro simbólico para preferir no usarlo en balde.
						pasos.append((f"{conector.id}/p{numero}", f"{conector.id}/p{otra}", 1.0, conector.id))
		return nodos, pasos

	# ── API ──

	def ruta(self, origen: Any, destino: Any, evitar: Iterable[str] = ()) -> Ruta | None:
		"""Camino más corto andando entre dos lugares (``Posicion`` o ``(planta, x, y)``); None si no lo hay.

		``evitar`` son ids de aberturas o de conectores por los que no se puede pasar (un paso
		cortado, el ascensor averiado). En ``longitud`` cuentan los metros andados: los de una
		escalera o una rampa sí, los del ascensor no.
		"""
		o, d = lugar(origen), lugar(destino)
		cortadas = frozenset(evitar)
		if self.mundo.planta(o[0]) is None or self.mundo.planta(d[0]) is None:
			return None
		if o[0] == d[0]:
			campo = self._buscar(o[0], (o[1], o[2]), (d[1], d[2]), None, cortadas)
			if campo is not None:
				puntos = self._camino_en(campo, d[1], d[2], cortadas)
				if puntos is not None:
					return Ruta([(o[0], x, y) for x, y in puntos], geo.longitud_linea(puntos))
		nodos, pasos = self._nodos_conectores()
		pasos = [paso for paso in pasos if paso[3] not in cortadas]
		if not nodos:
			return None
		# Grafo de alto nivel: origen, destino y extremos de conectores; por cada planta, distancias andando.
		campos: dict[str, Campo | None] = {}

		def campo_de(nodo: str) -> Campo | None:
			if nodo not in campos:
				lugar_nodo = o if nodo == "O" else nodos[nodo]
				campos[nodo] = self._buscar(lugar_nodo[0], (lugar_nodo[1], lugar_nodo[2]), None, None, cortadas)
			return campos[nodo]

		todos = dict(nodos)
		todos["O"] = o
		todos["D"] = d
		saltos: dict[str, list[tuple[str, float, str]]] = {}
		for a, b, metros, conector_id in pasos:
			saltos.setdefault(a, []).append((b, metros, conector_id))
		mejor: dict[str, float] = {"O": 0.0}
		previo: dict[str, tuple[str, str]] = {}
		monton: list[tuple[float, str]] = [(0.0, "O")]
		hechos: set[str] = set()
		while monton:
			coste, nodo = heapq.heappop(monton)
			if nodo in hechos:
				continue
			hechos.add(nodo)
			if nodo == "D":
				break
			vecinos: list[tuple[str, float, str]] = list(saltos.get(nodo, ()))
			campo = campo_de(nodo)
			if campo is not None:
				planta_nodo = todos[nodo][0]
				for otro, sitio in todos.items():
					if otro in hechos or otro == nodo or otro == "O" or sitio[0] != planta_nodo:
						continue
					andando = self._distancia_en(campo, sitio[1], sitio[2])
					if andando is not None:
						vecinos.append((otro, andando, ""))
			for otro, metros, conector_id in vecinos:
				nuevo = coste + metros
				if nuevo < mejor.get(otro, math.inf):
					mejor[otro] = nuevo
					previo[otro] = (nodo, conector_id)
					heapq.heappush(monton, (nuevo, otro))
		if "D" not in hechos:
			return None
		cadena: list[tuple[str, str]] = []
		actual = "D"
		while actual != "O":
			anterior, conector_id = previo[actual]
			cadena.append((actual, conector_id))
			actual = anterior
		cadena.reverse()
		ruta = Ruta()
		desde = "O"
		for nodo, conector_id in cadena:
			sitio_a, sitio_b = todos[desde], todos[nodo]
			if conector_id:
				ruta.conectores.append(conector_id)
				if not ruta.puntos or ruta.puntos[-1] != sitio_a:
					ruta.puntos.append(sitio_a)
				ruta.puntos.append(sitio_b)
				conector = self.mundo.elemento(conector_id)
				if conector is None or conector.tipo != "ascensor":
					# En el ascensor no se anda: no suma metros a la ruta.
					ruta.longitud += next(m for b, m, c in saltos[desde] if b == nodo and c == conector_id)
			else:
				campo = campo_de(desde)
				puntos = self._camino_en(campo, sitio_b[1], sitio_b[2], cortadas) if campo is not None else None
				if puntos is None:
					return None
				tramo = [(sitio_a[0], x, y) for x, y in puntos]
				if ruta.puntos and ruta.puntos[-1] == tramo[0]:
					tramo = tramo[1:]
				ruta.puntos.extend(tramo)
				ruta.longitud += geo.longitud_linea(puntos)
			desde = nodo
		return ruta

	def distancia(self, origen: Any, destino: Any, evitar: Iterable[str] = ()) -> float | None:
		"""Metros que hay que andar de un lugar a otro por el camino más corto; None si no se puede llegar."""
		ruta = self.ruta(origen, destino, evitar)
		return ruta.longitud if ruta is not None else None

	def distancias_desde(self, origen: Any, radio: float | None = None) -> Campo | None:
		"""Distancias de camino desde un lugar a todo lo alcanzable de su planta (hasta ``radio`` metros).

		Sirve para ordenar muchas cosas por distancia de camino con una sola
		búsqueda: después se pregunta cada punto con ``distancia_en``.
		"""
		o = lugar(origen)
		if self.mundo.planta(o[0]) is None:
			return None
		return self._buscar(o[0], (o[1], o[2]), None, radio)

	def distancia_en(self, campo: Campo | None, x: float, y: float) -> float | None:
		"""Distancia de camino del origen de un campo a un punto de su planta; None si no se llega."""
		if campo is None:
			return None
		return self._distancia_en(campo, x, y)

	def salidas(self, origen: Any, con_ruta: bool = False) -> list[Salida]:
		"""Salidas del edificio (aberturas con ``es_salida``) a las que se puede llegar, de la más cercana a la más lejana."""
		o = lugar(origen)
		encontradas: list[Salida] = []
		campo = self.distancias_desde(o)
		for indice in self.mundo.plantas():
			for info in indice.aberturas:
				abertura = info.abertura
				if not abertura.es_salida or abertura.tipo == "ventana":
					continue
				if not self.con_llave and self.mundo.estado_abertura(abertura.id) == "con_llave":
					continue
				destino = (indice.planta.id, info.centro[0], info.centro[1])
				if indice.planta.id == o[0] and not con_ruta:
					# Con el camino ya estirado: la distancia es la que mediría la ruta, no la del zigzag de celdas.
					puntos = self._camino_en(campo, info.centro[0], info.centro[1]) if campo is not None else None
					if puntos is not None:
						encontradas.append(Salida(abertura, indice.planta.id, geo.longitud_linea(puntos)))
						continue
				ruta = self.ruta(o, destino)
				if ruta is not None:
					encontradas.append(Salida(abertura, indice.planta.id, ruta.longitud, ruta if con_ruta else None))
		encontradas.sort(key=lambda salida: salida.distancia)
		return encontradas

	def salida_mas_cercana(self, origen: Any) -> Salida | None:
		"""La salida a la que menos hay que andar, con su ruta; None si no hay ninguna alcanzable."""
		salidas = self.salidas(origen)
		if not salidas:
			return None
		mejor = salidas[0]
		if mejor.ruta is None:
			o = lugar(origen)
			info = self.mundo.abertura(mejor.abertura.id)
			if info is not None:
				mejor.ruta = self.ruta(o, (mejor.planta_id, info.centro[0], info.centro[1]))
		return mejor

	# ── Grafo de espacios ──

	def grafo_espacios(self) -> dict[str, list[Enlace]]:
		"""Para cada espacio (por su id), por dónde se pasa a otros: aberturas, conectores y bordes abiertos."""
		self._comprobar_firma()
		if self._grafo is not None:
			return self._grafo
		grafo: dict[str, list[Enlace]] = {}
		mundo = self.mundo
		for indice in mundo.plantas():
			planta_id = indice.planta.id
			for _caja, espacio in indice.espacios:
				if not espacio.macizo:
					grafo.setdefault(espacio.id, [])
			for info in indice.aberturas:
				if not self._abertura_pasable(info):
					continue
				a, b = info.espacios
				for origen, destino, signo in ((a, b, -1.0), (b, a, 1.0)):
					if not origen:
						continue
					dentro = (planta_id, info.centro[0] + info.normal[0] * 0.8 * -signo, info.centro[1] + info.normal[1] * 0.8 * -signo)
					fuera = (planta_id, info.centro[0] + info.normal[0] * 0.8 * signo, info.centro[1] + info.normal[1] * 0.8 * signo)
					# ``espacios`` es (lado de la normal, lado contrario): el destino queda hacia donde apunta el signo.
					grafo.setdefault(origen, []).append(
						Enlace("abertura", info.abertura.id, origen, destino, dentro, fuera, info.abertura.nombre)
					)
			self._bordes_abiertos(indice, grafo)
		for conector in mundo.entorno.conectores:
			extremos: list[tuple[Lugar, str]] = []
			if conector.tipo == "ascensor":
				for parada in conector.paradas:
					espacio = mundo.espacio_en(parada.planta, parada.puerta.x, parada.puerta.y)
					if espacio is not None:
						extremos.append(((parada.planta, parada.puerta.x, parada.puerta.y), espacio.id))
				pares = [(i, j) for i in range(len(extremos)) for j in range(len(extremos)) if i != j]
			else:
				for tramo in conector.tramos:
					for posicion in (tramo.desde, tramo.hasta):
						espacio = mundo.espacio_en(posicion.planta, posicion.x, posicion.y)
						extremos.append(((posicion.planta, posicion.x, posicion.y), espacio.id if espacio is not None else ""))
				pares = []
				baja = str(conector.datos.get("sentido") or "") == "baja"
				for i in range(0, len(extremos) - 1, 2):
					if conector.tipo != "escalera_mecanica" or not baja:
						pares.append((i, i + 1))
					if conector.tipo != "escalera_mecanica" or baja:
						pares.append((i + 1, i))
			for i, j in pares:
				(lugar_a, espacio_a), (lugar_b, espacio_b) = extremos[i], extremos[j]
				if espacio_a and espacio_b:
					grafo.setdefault(espacio_a, []).append(
						Enlace("conector", conector.id, espacio_a, espacio_b, lugar_a, lugar_b, conector.nombre)
					)
		self._grafo = grafo
		return grafo

	def _abertura_pasable(self, info: InfoAbertura) -> bool:
		if info.abertura.tipo == "ventana" or not info.sobre_pared:
			return False
		if info.abertura.tipo == "hueco":
			return True
		estado = self.mundo.estado_abertura(info.abertura.id)
		return estado != "con_llave" or self.con_llave

	def _bordes_abiertos(self, indice: Any, grafo: dict[str, list[Enlace]]) -> None:
		"""Añade los pasos entre espacios que se tocan sin pared en medio (acera y calzada, plaza y sendero)."""
		planta_id = indice.planta.id
		abiertos = [e for _caja, e in indice.espacios if not e.macizo]
		vistos: set[tuple[str, str]] = set()
		for espacio_a in abiertos:
			if espacio_a.cerrado and not espacio_a.lados_abiertos:
				continue
			for a, b in espacio_a.lados():
				largo = geo.distancia(a, b)
				if largo < 0.3:
					continue
				nx, ny = (b[1] - a[1]) / largo, -(b[0] - a[0]) / largo
				muestras = max(1, int(largo / 1.0))
				for i in range(muestras):
					t = (i + 0.5) / muestras
					mx, my = a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t
					dentro = (mx - nx * 0.3, my - ny * 0.3)
					fuera = (mx + nx * 0.3, my + ny * 0.3)
					if not geo.punto_en_poligono(dentro, espacio_a.contorno):
						dentro, fuera = fuera, dentro
					otro = self.mundo.espacio_en(planta_id, fuera[0], fuera[1])
					if otro is None or otro.id == espacio_a.id or (espacio_a.id, otro.id) in vistos:
						continue
					if self.mundo.corta(planta_id, dentro, fuera, "paso") is not None:
						continue
					vistos.add((espacio_a.id, otro.id))
					vistos.add((otro.id, espacio_a.id))
					grafo.setdefault(espacio_a.id, []).append(
						Enlace("abierto", "", espacio_a.id, otro.id, (planta_id, *dentro), (planta_id, *fuera), otro.nombre)
					)
					grafo.setdefault(otro.id, []).append(
						Enlace("abierto", "", otro.id, espacio_a.id, (planta_id, *fuera), (planta_id, *dentro), espacio_a.nombre)
					)

	def enlaces(self, espacio_id: str) -> list[Enlace]:
		"""Pasos desde un espacio a sus vecinos."""
		return list(self.grafo_espacios().get(espacio_id, ()))

	def espacios_alcanzables(self, origen: Any) -> set[str]:
		"""Ids de los espacios a los que se puede llegar desde un lugar (o desde un espacio, por su id)."""
		if isinstance(origen, str):
			inicio = origen
		else:
			o = lugar(origen)
			espacio = self.mundo.espacio_en(o[0], o[1], o[2])
			if espacio is None:
				return set()
			inicio = espacio.id
		grafo = self.grafo_espacios()
		alcanzados = {inicio}
		cola = deque([inicio])
		while cola:
			actual = cola.popleft()
			for enlace in grafo.get(actual, ()):
				if enlace.destino and enlace.destino not in alcanzados:
					alcanzados.add(enlace.destino)
					cola.append(enlace.destino)
		return alcanzados

	def ruta_espacios(self, origen_id: str, destino_id: str) -> list[str] | None:
		"""Espacios por los que se pasa para ir de uno a otro con el menor número de cambios; None si no se llega."""
		grafo = self.grafo_espacios()
		if origen_id not in grafo or destino_id not in grafo:
			return None
		previo: dict[str, str | None] = {origen_id: None}
		cola = deque([origen_id])
		while cola:
			actual = cola.popleft()
			if actual == destino_id:
				break
			for enlace in grafo.get(actual, ()):
				if enlace.destino and enlace.destino not in previo:
					previo[enlace.destino] = actual
					cola.append(enlace.destino)
		if destino_id not in previo:
			return None
		camino: list[str] = []
		actual_id: str | None = destino_id
		while actual_id is not None:
			camino.append(actual_id)
			actual_id = previo[actual_id]
		camino.reverse()
		return camino
