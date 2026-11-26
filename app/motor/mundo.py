"""Índice del entorno para consultas rápidas: qué corta el paso, la vista y el sonido.

El modelo (``app.dominio.modelo``) está pensado para editarse; el motor
pregunta sesenta veces por segundo «¿choco?», «¿en qué espacio estoy?», «¿qué
hay entre esta fuente y yo?». ``Mundo`` prepara una vez, por planta, una
rejilla espacial con todos los segmentos (paredes derivadas de los contornos,
puertas, ventanas, edificios macizos y huellas reales de los objetos de los
complementos) y responde a esas preguntas mirando solo lo cercano.

El estado que cambia durante la partida (puertas abiertas o cerradas, estado
de los objetos) se guarda AQUÍ y no en el modelo: una sesión nunca modifica
el entorno del profesional, y dos sesiones del mismo entorno no se pisan.
Cambiar una puerta solo activa o desactiva su segmento; no se reconstruye nada.

Cada consulta dice para qué es (``modo``), porque no todo corta lo mismo:

- ``paso``: lo que para a una persona (incluye los objetos a la altura de la cabeza).
- ``sonda``: lo que encuentra un bastón (no los objetos colgados o en voladizo).
- ``vista``: lo que impide percibir a distancia (paredes y puertas cerradas, no los muebles).
- ``sonido``: lo que tapa el sonido, con cuánto (una puerta cerrada, parte; una pared, todo).
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from app.dominio import geometria as geo
from app.dominio import modelo
from app.dominio.catalogo import Catalogo, DefObjeto
from app.dominio.geometria import Punto
from app.dominio.modelo import Abertura, Conector, Entorno, Espacio, FuenteSonido, Objeto, Parada, Planta, Referencia, Tramo, ZonaSuelo
from app.motor.indice_espacial import RejillaCajas

log = logging.getLogger(__name__)

# Lado de las celdas de la rejilla espacial, en metros.
CELDA = 2.0
# Por encima de esta altura un objeto colgado no toca a una persona.
ALTURA_PERSONA = 1.75
# Por encima de esta altura de su base, el bastón pasa por debajo de un objeto sin encontrarlo.
ALTURA_BASTON = 0.2
# Fuera de todo espacio solo se puede estar a esta distancia de una abertura (para poder cruzar una salida).
MARGEN_SALIDA = 1.0
# Tipos de espacio que son calzada (para bordillos y tráfico).
TIPOS_CALZADA = frozenset({"calzada", "paso_peatones"})

MODOS = ("paso", "sonda", "vista", "sonido")

# Aviso de progreso de una construcción larga: (fase, hechos, total). Ver ``Mundo.__init__``.
Progreso = Callable[[str, int, int], None]
# Lado de las celdas de las rejillas de elementos (espacios, objetos, aberturas…), en metros.
CELDA_ELEMENTOS = 8.0
# Margen con el que se apuntan los lados con pared: algo más que la tolerancia con la que una abertura «está sobre» uno.
MARGEN_LADOS = modelo.TOLERANCIA_PARED + 0.01
# Margen de la caja de los espacios: el mismo que perdona ``_espacio_en`` al comparar con ella.
MARGEN_ESPACIOS = 1e-6


class Seg:
	"""Un segmento de la rejilla, con lo que corta y de dónde sale."""

	__slots__ = (
		"ax",
		"ay",
		"bx",
		"by",
		"elemento_id",
		"clase",
		"material",
		"paso",
		"sonido",
		"baston",
		"vista",
		"abertura",
		"objeto",
		"nombre",
		"activo",
		"sello",
	)

	def __init__(
		self,
		a: Punto,
		b: Punto,
		elemento_id: str,
		clase: str,
		material: str,
		paso: bool = True,
		sonido: float = 1.0,
		baston: bool = True,
		vista: bool = True,
		abertura: Abertura | None = None,
		objeto: Objeto | None = None,
		nombre: str = "",
	) -> None:
		self.ax, self.ay = a
		self.bx, self.by = b
		self.elemento_id = elemento_id
		self.clase = clase
		self.material = material
		self.paso = paso
		self.sonido = sonido
		self.baston = baston
		self.vista = vista
		self.abertura = abertura
		self.objeto = objeto
		self.nombre = nombre
		# Una puerta abierta deja de contar sin salir de la rejilla.
		self.activo = True
		self.sello = 0

	@property
	def a(self) -> Punto:
		"""Primer extremo."""
		return self.ax, self.ay

	@property
	def b(self) -> Punto:
		"""Segundo extremo."""
		return self.bx, self.by

	def cuenta(self, modo: str) -> bool:
		"""Si este segmento cuenta para ese modo de consulta."""
		if not self.activo:
			return False
		if modo == "paso":
			return self.paso
		if modo == "sonda":
			return self.paso and self.baston
		if modo == "vista":
			return self.vista
		return self.sonido > 0.0


@dataclass(slots=True)
class Impacto:
	"""Dónde da un rayo: a qué distancia, en qué punto y contra qué."""

	distancia: float
	punto: Punto
	seg: Seg


@dataclass(slots=True)
class InfoObjeto:
	"""Un objeto colocado con todo lo que el motor necesita saber de él ya resuelto."""

	objeto: Objeto
	definicion: DefObjeto | None
	huella: list[Punto]
	caja: tuple[float, float, float, float]
	bloquea: bool
	altura_base: float
	detectable: bool
	material: str
	planta_id: str = ""
	# Estados en los que deja pasar aunque corte el paso (un torno abierto), suelo que se pisa encima y frase de aviso.
	paso_libre: tuple[str, ...] = ()
	suelo: str = ""
	aviso: str = ""
	segs: list[Seg] = field(default_factory=list)

	@property
	def sonidos(self) -> dict[str, Any]:
		"""Sonidos declarados en su ficha (golpe, uso, propio)."""
		propios = self.objeto.datos.get("sonidos")
		if isinstance(propios, dict):
			return propios
		return self.definicion.sonidos if self.definicion is not None else {}

	@property
	def acciones(self) -> list[dict[str, Any]]:
		"""Acciones declaradas en su ficha."""
		return self.definicion.acciones if self.definicion is not None else []

	@property
	def dinamica(self) -> dict[str, Any]:
		"""Comportamiento declarado (fases y tiempos), o vacío."""
		propia = self.objeto.datos.get("dinamica")
		if isinstance(propia, dict):
			return propia
		return self.definicion.dinamica if self.definicion is not None else {}

	def distancia(self, x: float, y: float) -> float:
		"""Distancia de un punto a la huella (0 si está dentro)."""
		return geo.distancia_punto_poligono((x, y), self.huella)


@dataclass(slots=True)
class InfoAbertura:
	"""Una abertura con su centro, su normal y los espacios que une."""

	abertura: Abertura
	centro: Punto
	normal: Punto
	sobre_pared: bool
	planta_id: str = ""
	espacios: tuple[str, str] = ("", "")
	seg: Seg | None = None

	def distancia(self, x: float, y: float) -> float:
		"""Distancia de un punto al tramo de la abertura."""
		return geo.distancia_punto_segmento((x, y), self.abertura.a, self.abertura.b)

	def otro_lado(self, espacio_id: str) -> str:
		"""Id del espacio del otro lado (vacío si da al exterior del entorno)."""
		a, b = self.espacios
		return b if a == espacio_id else a


@dataclass(slots=True)
class Boca:
	"""Un extremo de un tramo de escalera, rampa o escalera mecánica en una planta."""

	conector: Conector
	tramo: Tramo
	sentido: int  # +1: por esta boca se sube; -1: se baja
	planta_id: str
	x: float
	y: float
	rumbo: float  # rumbo con el que se entra en el tramo por esta boca
	destino: str  # id de la planta a la que lleva

	@property
	def punto(self) -> Punto:
		"""Punto de la boca."""
		return self.x, self.y


@dataclass(slots=True)
class InfoParada:
	"""Una parada de ascensor en una planta."""

	conector: Conector
	parada: Parada
	indice: int

	@property
	def punto(self) -> Punto:
		"""Punto delante de la puerta."""
		return self.parada.puerta.x, self.parada.puerta.y


@dataclass
class IndicePlanta:
	"""Todo lo de una planta, preparado para consultar.

	Además de las listas, cada clase de elemento tiene su ``RejillaCajas``
	(números de orden en su lista): así «¿en qué espacio estoy?», «¿qué hay
	cerca?» o «¿hay una puerta aquí?» miran unas pocas decenas de elementos y
	no los miles de un barrio importado.
	"""

	planta: Planta
	segs: list[Seg] = field(default_factory=list)
	rejilla: dict[tuple[int, int], list[Seg]] = field(default_factory=dict)
	espacios: list[tuple[tuple[float, float, float, float], Espacio]] = field(default_factory=list)
	zonas: list[tuple[tuple[float, float, float, float], ZonaSuelo]] = field(default_factory=list)
	objetos: list[InfoObjeto] = field(default_factory=list)
	aberturas: list[InfoAbertura] = field(default_factory=list)
	bocas: list[Boca] = field(default_factory=list)
	paradas: list[InfoParada] = field(default_factory=list)
	caja: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
	rejilla_espacios: RejillaCajas = field(default_factory=lambda: RejillaCajas(CELDA_ELEMENTOS))
	rejilla_zonas: RejillaCajas = field(default_factory=lambda: RejillaCajas(CELDA_ELEMENTOS))
	rejilla_objetos: RejillaCajas = field(default_factory=lambda: RejillaCajas(CELDA_ELEMENTOS))
	rejilla_aberturas: RejillaCajas = field(default_factory=lambda: RejillaCajas(CELDA_ELEMENTOS))
	# Referencias y fuentes son listas del modelo: se indexan la primera vez y se rehacen si cambia su longitud.
	rejilla_referencias: RejillaCajas | None = None
	referencias_indexadas: int = -1
	rejilla_fuentes: RejillaCajas | None = None
	fuentes_indexadas: int = -1


def _lados_con_pared(planta: Planta) -> tuple[list[tuple[Punto, Punto]], RejillaCajas]:
	"""Lados con pared de los espacios cerrados y paredes sueltas, con su rejilla (para ``_sobre_pared``)."""
	lados: list[tuple[Punto, Punto]] = []
	rejilla = RejillaCajas(CELDA_ELEMENTOS)
	for espacio in planta.espacios:
		if len(espacio.contorno) < 3 or espacio.macizo or not espacio.cerrado:
			continue
		for indice, (a, b) in enumerate(espacio.lados()):
			if indice in espacio.lados_abiertos:
				continue
			lados.append((a, b))
			rejilla.meter(geo.caja([a, b]), MARGEN_LADOS)
	for pared in planta.paredes:
		lados.append((pared.a, pared.b))
		rejilla.meter(geo.caja([pared.a, pared.b]), MARGEN_LADOS)
	return lados, rejilla


def _sobre_pared(lados: list[tuple[Punto, Punto]], rejilla: RejillaCajas, abertura: Abertura) -> bool:
	"""True si la abertura cae sobre un lado con pared de un espacio cerrado o sobre una pared suelta.

	Es la misma regla que aplica el modelo al derivar las paredes: el portal
	de un edificio macizo no cumple y por eso es solo una referencia. Solo se
	miran los lados cuya caja (ampliada en la tolerancia) toca la abertura:
	un lado más lejano no puede tenerla encima.
	"""
	x0, y0, x1, y1 = geo.caja([abertura.a, abertura.b])
	for numero in rejilla.en_caja(x0, y0, x1, y1):
		a, b = lados[numero]
		if geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, modelo.TOLERANCIA_PARED) is not None:
			return True
	return False


def _clave(a: Punto, b: Punto) -> tuple[Punto, Punto]:
	p = (round(a[0], 3), round(a[1], 3))
	q = (round(b[0], 3), round(b[1], 3))
	return (p, q) if p <= q else (q, p)


class Mundo:
	"""El entorno indexado y su estado dinámico (puertas y objetos)."""

	def __init__(self, entorno: Entorno, catalogo: Catalogo | None = None, progreso: Progreso | None = None) -> None:
		"""``progreso(fase, hechos, total)`` se llama entre plantas y entre fases de cada una (ver ``Progreso``).

		Sirve para que el reproductor diga cómo va la carga de un entorno
		grande; si lanza una excepción (el alumno ha cancelado), la
		construcción se interrumpe ahí.
		"""
		self.entorno = entorno
		self.catalogo = catalogo if catalogo is not None else Catalogo()
		# Crece con cada cambio de puerta: quien guarda cálculos (acústica, rutas) sabe cuándo tirarlos.
		self.version = 0
		self._sello = 0
		self._estado_abertura: dict[str, str] = {}
		self._estado_objeto: dict[str, str] = {}
		self._plantas: dict[str, IndicePlanta] = {}
		self._aberturas: dict[str, InfoAbertura] = {}
		self._objetos: dict[str, InfoObjeto] = {}
		self._elementos: dict[str, Any] | None = None
		self._progreso = progreso
		for numero, planta in enumerate(entorno.plantas):
			self._avisar("plantas", numero, len(entorno.plantas))
			self._plantas[planta.id] = self._indexar(planta)
		self._avisar("plantas", len(entorno.plantas), len(entorno.plantas))
		self._indexar_conectores()
		self._progreso = None

	def _avisar(self, fase: str, hechos: int, total: int) -> None:
		"""Cuenta cómo va la construcción a quien la pidió (si lo pidió)."""
		if self._progreso is not None:
			self._progreso(fase, hechos, total)

	# ── Construcción ──

	def _indexar(self, planta: Planta) -> IndicePlanta:
		indice = IndicePlanta(planta=planta, caja=planta.caja())
		self._avisar("paredes", 0, 1)
		nombres = {pared.id: pared.nombre for pared in planta.paredes}
		nombres.update({espacio.id: espacio.nombre for espacio in planta.espacios if espacio.macizo})
		paredes: dict[tuple[Punto, Punto], Seg] = {}
		for s in modelo.segmentos_solidos(planta, None, incluir_puertas_cerradas=False):
			if s.clase == "pared":
				seg = Seg(s.a, s.b, s.elemento_id, "pared", s.material, paso=True, sonido=0.0, nombre=nombres.get(s.elemento_id, ""))
				paredes[_clave(s.a, s.b)] = seg
				indice.segs.append(seg)
			elif s.clase == "ventana":
				abertura = next((a for a in planta.aberturas if a.id == s.elemento_id), None)
				nombre = abertura.nombre if abertura is not None else ""
				indice.segs.append(
					Seg(s.a, s.b, s.elemento_id, "ventana", s.material, sonido=s.atenuacion, abertura=abertura, nombre=nombre)
				)
			elif s.clase == "macizo":
				indice.segs.append(Seg(s.a, s.b, s.elemento_id, "macizo", s.material, nombre=nombres.get(s.elemento_id, "")))
		for s in modelo.segmentos_opacos(planta):
			if s.clase != "pared":
				continue
			existente = paredes.get(_clave(s.a, s.b))
			if existente is not None:
				existente.sonido = 1.0
			else:
				# Tapa el sonido pero no el paso (una cortina gruesa): no para ni se ve, pero se oye menos.
				indice.segs.append(Seg(s.a, s.b, s.elemento_id, "pared", s.material, paso=False, sonido=1.0, baston=False, vista=False))
		for seg in paredes.values():
			# Una valla o un cristal bajo cortan el paso pero no la percepción a distancia.
			seg.vista = seg.sonido > 0.0
		self._avisar("paredes", 1, 1)
		lados, rejilla_lados = _lados_con_pared(planta)
		total_aberturas = len(planta.aberturas)
		for numero_abertura, abertura in enumerate(planta.aberturas):
			if numero_abertura % 500 == 0:
				self._avisar("aberturas", numero_abertura, total_aberturas)
			sobre = _sobre_pared(lados, rejilla_lados, abertura)
			largo = geo.distancia(abertura.a, abertura.b) or 1.0
			normal = (-(abertura.b[1] - abertura.a[1]) / largo, (abertura.b[0] - abertura.a[0]) / largo)
			info = InfoAbertura(abertura, abertura.centro(), normal, sobre, planta.id)
			if sobre and abertura.tipo in ("puerta", "portal"):
				seg = Seg(
					abertura.a,
					abertura.b,
					abertura.id,
					"puerta",
					abertura.material,
					sonido=modelo.ATENUACION_PUERTA,
					abertura=abertura,
					nombre=abertura.nombre,
				)
				estado = abertura.estado if abertura.estado in modelo.ESTADOS_ABERTURA else "cerrada"
				self._estado_abertura[abertura.id] = estado
				seg.activo = estado != "abierta"
				info.seg = seg
				indice.segs.append(seg)
			indice.aberturas.append(info)
			indice.rejilla_aberturas.meter(geo.caja([abertura.a, abertura.b]))
			self._aberturas[abertura.id] = info
		total_objetos = len(planta.objetos)
		for numero_objeto, objeto in enumerate(planta.objetos):
			if numero_objeto % 500 == 0:
				self._avisar("objetos", numero_objeto, total_objetos)
			info_objeto = self._info_objeto(objeto, planta.id)
			indice.objetos.append(info_objeto)
			indice.rejilla_objetos.meter(info_objeto.caja)
			self._objetos[objeto.id] = info_objeto
			self._estado_objeto[objeto.id] = objeto.estado
			if info_objeto.bloquea and info_objeto.altura_base < ALTURA_PERSONA:
				libre = objeto.estado in info_objeto.paso_libre
				for a, b in geo.lados(info_objeto.huella):
					seg = Seg(
						a,
						b,
						objeto.id,
						"objeto",
						info_objeto.material,
						sonido=0.0,
						baston=info_objeto.detectable,
						vista=False,
						objeto=objeto,
						nombre=objeto.nombre,
					)
					# Un torno o una mampara en un estado de «paso libre» dejan pasar: su huella se desactiva, como una puerta abierta.
					seg.activo = not libre
					info_objeto.segs.append(seg)
					indice.segs.append(seg)
		self._avisar("objetos", total_objetos, total_objetos)
		for seg in indice.segs:
			self._meter(indice, seg)
		validos = [e for e in planta.espacios if len(e.contorno) >= 3]
		validos.sort(key=lambda e: e.area())
		indice.espacios = [(e.caja(), e) for e in validos]
		for caja, _espacio in indice.espacios:
			indice.rejilla_espacios.meter(caja, MARGEN_ESPACIOS)
		indice.zonas = [(geo.caja(z.contorno), z) for z in planta.zonas if len(z.contorno) >= 3]
		for caja, _zona in indice.zonas:
			indice.rejilla_zonas.meter(caja)
		# Los espacios que une cada abertura se miran con el índice ya hecho.
		for info in indice.aberturas:
			info.espacios = self._espacios_de(indice, info)
		return indice

	def _info_objeto(self, objeto: Objeto, planta_id: str) -> InfoObjeto:
		definicion = self.catalogo.definicion_de(objeto)
		huella = self.catalogo.huella(objeto)
		altura_base = 0.0
		detectable = True
		if definicion is not None:
			altura_base = definicion.altura_base
			detectable = definicion.detectable_baston
		if "altura_base" in objeto.datos:
			try:
				altura_base = float(objeto.datos["altura_base"])
			except TypeError, ValueError:
				log.warning("El objeto %s tiene una altura_base que no es un número; se usa la de su ficha", objeto.id)
		if "detectable_baston" in objeto.datos:
			detectable = bool(objeto.datos["detectable_baston"])
		# ``bloquea`` es si PUEDE cortar el paso; si lo corta ahora depende además de su estado (ver ``corta_el_paso``).
		if "bloquea" in objeto.datos:
			bloquea = bool(objeto.datos["bloquea"])
		else:
			bloquea = True if definicion is None else definicion.bloquea
		return InfoObjeto(
			objeto=objeto,
			definicion=definicion,
			huella=huella,
			caja=geo.caja(huella),
			bloquea=bloquea,
			altura_base=altura_base,
			detectable=detectable and altura_base <= ALTURA_BASTON,
			material=self.catalogo.material(objeto),
			planta_id=planta_id,
			paso_libre=tuple(definicion.paso_libre) if definicion is not None else (),
			suelo=str(objeto.datos.get("suelo") or (definicion.suelo if definicion is not None else "")),
			aviso=str(objeto.datos.get("aviso") or (definicion.aviso if definicion is not None else "")),
		)

	@staticmethod
	def _meter(indice: IndicePlanta, seg: Seg) -> None:
		x0, x1 = (seg.ax, seg.bx) if seg.ax <= seg.bx else (seg.bx, seg.ax)
		y0, y1 = (seg.ay, seg.by) if seg.ay <= seg.by else (seg.by, seg.ay)
		for cx in range(math.floor(x0 / CELDA), math.floor(x1 / CELDA) + 1):
			for cy in range(math.floor(y0 / CELDA), math.floor(y1 / CELDA) + 1):
				indice.rejilla.setdefault((cx, cy), []).append(seg)

	def _espacios_de(self, indice: IndicePlanta, info: InfoAbertura) -> tuple[str, str]:
		ids: list[str] = []
		for signo in (1.0, -1.0):
			x = info.centro[0] + info.normal[0] * 0.3 * signo
			y = info.centro[1] + info.normal[1] * 0.3 * signo
			espacio = self._espacio_en(indice, x, y, False)
			ids.append(espacio.id if espacio is not None else "")
		return ids[0], ids[1]

	def _indexar_conectores(self) -> None:
		for conector in self.entorno.conectores:
			for tramo in conector.tramos:
				abajo = self._plantas.get(tramo.desde.planta)
				arriba = self._plantas.get(tramo.hasta.planta)
				if abajo is None or arriba is None:
					log.warning("El conector %s une plantas que no existen; se ignora ese tramo", conector.id)
					continue
				abajo.bocas.append(
					Boca(conector, tramo, 1, abajo.planta.id, tramo.desde.x, tramo.desde.y, tramo.desde.rumbo % 360.0, arriba.planta.id)
				)
				arriba.bocas.append(
					Boca(
						conector,
						tramo,
						-1,
						arriba.planta.id,
						tramo.hasta.x,
						tramo.hasta.y,
						(tramo.hasta.rumbo + 180.0) % 360.0,
						abajo.planta.id,
					)
				)
			for numero, parada in enumerate(conector.paradas):
				indice = self._plantas.get(parada.planta)
				if indice is None:
					log.warning("El ascensor %s para en una planta que no existe; se ignora esa parada", conector.id)
					continue
				indice.paradas.append(InfoParada(conector, parada, numero))

	# ── Plantas ──

	def planta(self, planta_id: str) -> IndicePlanta | None:
		"""Índice de una planta, o None si no existe."""
		return self._plantas.get(planta_id)

	def plantas(self) -> list[IndicePlanta]:
		"""Índices de todas las plantas, en el orden del entorno."""
		return list(self._plantas.values())

	def altura(self, planta_id: str) -> float:
		"""Cota del suelo de una planta."""
		indice = self._plantas.get(planta_id)
		return indice.planta.altura_m if indice is not None else 0.0

	# ── Espacios y suelo ──

	@staticmethod
	def _espacio_en(indice: IndicePlanta, x: float, y: float, macizos: bool) -> Espacio | None:
		# La rejilla da, de menor a mayor área (el orden de ``indice.espacios``), los que pueden contener el punto.
		espacios = indice.espacios
		for numero in indice.rejilla_espacios.en_punto(x, y):
			(x0, y0, x1, y1), espacio = espacios[numero]
			if x < x0 - 1e-6 or x > x1 + 1e-6 or y < y0 - 1e-6 or y > y1 + 1e-6:
				continue
			if espacio.macizo and not macizos:
				continue
			if geo.punto_en_poligono((x, y), espacio.contorno):
				return espacio
		return None

	def espacio_en(self, planta_id: str, x: float, y: float, macizos: bool = False) -> Espacio | None:
		"""Espacio en el que cae un punto; si varios lo contienen gana el más pequeño (el más concreto)."""
		indice = self._plantas.get(planta_id)
		return self._espacio_en(indice, x, y, macizos) if indice is not None else None

	def zona_en(self, planta_id: str, x: float, y: float) -> ZonaSuelo | None:
		"""Zona de suelo (alfombra, pavimento táctil) que pisa un punto, o None."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return None
		zonas = indice.zonas
		for numero in indice.rejilla_zonas.en_punto(x, y):
			(x0, y0, x1, y1), zona = zonas[numero]
			if x0 <= x <= x1 and y0 <= y <= y1 and geo.punto_en_poligono((x, y), zona.contorno):
				return zona
		return None

	def objeto_de_suelo_en(self, planta_id: str, x: float, y: float) -> InfoObjeto | None:
		"""Objeto que no corta el paso y cambia el suelo que se pisa en ese punto (una alfombra, una tapa de metal), o None."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return None
		objetos = indice.objetos
		for numero in indice.rejilla_objetos.en_punto(x, y):
			info = objetos[numero]
			if not info.suelo or self.corta_el_paso(info):
				continue
			x0, y0, x1, y1 = info.caja
			if x0 <= x <= x1 and y0 <= y <= y1 and geo.punto_en_poligono((x, y), info.huella):
				return info
		return None

	def corta_el_paso(self, info: InfoObjeto) -> bool:
		"""Si ese objeto corta el paso AHORA: puede cortarlo y no está en un estado de paso libre."""
		return info.bloquea and self._estado_objeto.get(info.objeto.id, info.objeto.estado) not in info.paso_libre

	def suelo_en(self, planta_id: str, x: float, y: float) -> str:
		"""Material del suelo en un punto: el del objeto que se pisa, el de la zona de suelo o, si no, el del espacio."""
		sobre = self.objeto_de_suelo_en(planta_id, x, y)
		if sobre is not None:
			return sobre.suelo
		zona = self.zona_en(planta_id, x, y)
		if zona is not None:
			return zona.suelo
		espacio = self.espacio_en(planta_id, x, y)
		if espacio is not None:
			return espacio.suelo
		indice = self._plantas.get(planta_id)
		return "hormigon" if indice is not None and indice.planta.exterior else "baldosa"

	def transitable(self, planta_id: str, x: float, y: float) -> bool:
		"""Si se puede estar en ese punto: dentro de un espacio, o justo al otro lado de una abertura.

		Lo segundo permite cruzar una salida del edificio (y que la actividad
		se entere) sin dejar que el alumno se pierda por el vacío que rodea al entorno.
		"""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return False
		if not indice.espacios:
			return True
		espacio = self._espacio_en(indice, x, y, True)
		if espacio is not None:
			# Si lo más concreto que hay ahí es un edificio macizo, no se puede estar (aunque lo rodee una plaza).
			return not espacio.macizo
		aberturas = indice.aberturas
		for numero in indice.rejilla_aberturas.en_caja(x - MARGEN_SALIDA, y - MARGEN_SALIDA, x + MARGEN_SALIDA, y + MARGEN_SALIDA):
			info = aberturas[numero]
			if info.abertura.tipo != "ventana" and info.sobre_pared and info.distancia(x, y) <= MARGEN_SALIDA:
				return True
		return False

	# ── Segmentos ──

	def segs_en_caja(self, planta_id: str, x0: float, y0: float, x1: float, y1: float) -> list[Seg]:
		"""Segmentos (de cualquier clase, activos o no) cuyas celdas tocan esa caja, sin repetir."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return []
		self._sello += 1
		sello = self._sello
		rejilla = indice.rejilla
		encontrados: list[Seg] = []
		for cx in range(math.floor(x0 / CELDA), math.floor(x1 / CELDA) + 1):
			for cy in range(math.floor(y0 / CELDA), math.floor(y1 / CELDA) + 1):
				celda = rejilla.get((cx, cy))
				if celda is None:
					continue
				for seg in celda:
					if seg.sello != sello:
						seg.sello = sello
						encontrados.append(seg)
		return encontrados

	def rayo(self, planta_id: str, origen: Punto, rumbo: float, alcance: float, modo: str = "paso") -> Impacto | None:
		"""Primer segmento que encuentra un rayo lanzado desde ``origen`` con ese rumbo."""
		radianes = math.radians(rumbo)
		dx, dy = math.sin(radianes), math.cos(radianes)
		ox, oy = origen
		fx, fy = ox + dx * alcance, oy + dy * alcance
		mejor_t = alcance
		mejor: Seg | None = None
		for seg in self.segs_en_caja(planta_id, min(ox, fx), min(oy, fy), max(ox, fx), max(oy, fy)):
			if not seg.cuenta(modo):
				continue
			sx, sy = seg.bx - seg.ax, seg.by - seg.ay
			denominador = dx * sy - dy * sx
			if abs(denominador) < 1e-12:
				continue
			qx, qy = seg.ax - ox, seg.ay - oy
			t = (qx * sy - qy * sx) / denominador
			if t < 0.0 or t >= mejor_t:
				continue
			u = (qx * dy - qy * dx) / denominador
			if u < -1e-9 or u > 1.0 + 1e-9:
				continue
			mejor_t = t
			mejor = seg
		if mejor is None:
			return None
		return Impacto(mejor_t, (ox + dx * mejor_t, oy + dy * mejor_t), mejor)

	def cortes(self, planta_id: str, a: Punto, b: Punto, modo: str = "paso") -> list[tuple[float, Seg]]:
		"""Segmentos que atraviesa el tramo ab, con la fracción (0 a 1) a la que lo hace, ordenados.

		Tocar un segmento justo con un extremo no cuenta: así se puede mirar
		desde o hacia un punto que está sobre una pared (el centro de una puerta).
		"""
		ax, ay = a
		rx, ry = b[0] - ax, b[1] - ay
		encontrados: list[tuple[float, Seg]] = []
		for seg in self.segs_en_caja(planta_id, min(ax, b[0]), min(ay, b[1]), max(ax, b[0]), max(ay, b[1])):
			if not seg.cuenta(modo):
				continue
			sx, sy = seg.bx - seg.ax, seg.by - seg.ay
			denominador = rx * sy - ry * sx
			if abs(denominador) < 1e-12:
				continue
			qx, qy = seg.ax - ax, seg.ay - ay
			t = (qx * sy - qy * sx) / denominador
			if t <= 1e-6 or t >= 1.0 - 1e-6:
				continue
			u = (qx * ry - qy * rx) / denominador
			if u < -1e-9 or u > 1.0 + 1e-9:
				continue
			encontrados.append((t, seg))
		encontrados.sort(key=lambda par: par[0])
		return encontrados

	def corta(self, planta_id: str, a: Punto, b: Punto, modo: str = "paso") -> Seg | None:
		"""Primer segmento que corta el tramo ab, o None si está libre."""
		cortes = self.cortes(planta_id, a, b, modo)
		return cortes[0][1] if cortes else None

	def visible(self, planta_id: str, a: Punto, b: Punto, modo: str = "vista") -> bool:
		"""Si entre ``a`` y ``b`` no hay nada que corte en ese modo."""
		return not self.cortes(planta_id, a, b, modo)

	def atenuacion(self, planta_id: str, a: Punto, b: Punto) -> tuple[int, float]:
		"""Lo que tapa el sonido entre dos puntos: (paredes que lo tapan del todo, transmisión de lo demás).

		La transmisión va de 1 (nada en medio) hacia 0: cada puerta cerrada o
		ventana la multiplica por lo que deja pasar. Los lados de un mismo
		elemento (las dos caras de un edificio macizo) cuentan una vez, y
		también dos paredes que coinciden en el mismo sitio (el lado común de
		dos habitaciones adosadas de distinto tamaño, que el modelo da dos veces).
		"""
		totales = 0
		transmision = 1.0
		vistos: set[str] = set()
		largo = math.hypot(b[0] - a[0], b[1] - a[1])
		ultima = -1.0
		for t, seg in self.cortes(planta_id, a, b, "sonido"):
			if seg.sonido >= 1.0:
				if seg.clase == "macizo":
					if seg.elemento_id in vistos:
						continue
					vistos.add(seg.elemento_id)
				elif (t - ultima) * largo < 0.06:
					continue
				ultima = t
				totales += 1
			else:
				transmision *= 1.0 - seg.sonido
		return totales, transmision

	def contactos(self, planta_id: str, x: float, y: float, radio: float, modo: str = "paso") -> list[tuple[float, Punto, Seg]]:
		"""Segmentos a menos de ``radio`` de un punto: (distancia, punto más cercano, segmento), del más cercano al más lejano."""
		encontrados: list[tuple[float, Punto, Seg]] = []
		for seg in self.segs_en_caja(planta_id, x - radio, y - radio, x + radio, y + radio):
			if not seg.cuenta(modo):
				continue
			sx, sy = seg.bx - seg.ax, seg.by - seg.ay
			largo2 = sx * sx + sy * sy
			if largo2 < 1e-18:
				t = 0.0
			else:
				t = ((x - seg.ax) * sx + (y - seg.ay) * sy) / largo2
				t = 0.0 if t < 0.0 else 1.0 if t > 1.0 else t
			px, py = seg.ax + sx * t, seg.ay + sy * t
			d = math.hypot(x - px, y - py)
			if d < radio:
				encontrados.append((d, (px, py), seg))
		encontrados.sort(key=lambda terna: terna[0])
		return encontrados

	def dentro_de_objeto(self, planta_id: str, x: float, y: float, fijos: bool = False) -> InfoObjeto | None:
		"""Objeto que corta el paso y cuya huella contiene el punto, o None.

		Con ``fijos`` solo cuentan los que no se pueden abrir (un torno cerrado
		se puede abrir: para buscar caminos es como una puerta cerrada).
		"""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return None
		objetos = indice.objetos
		for numero in indice.rejilla_objetos.en_punto(x, y):
			info = objetos[numero]
			x0, y0, x1, y1 = info.caja
			if fijos and info.paso_libre:
				continue
			if (
				x0 <= x <= x1
				and y0 <= y <= y1
				and self.corta_el_paso(info)
				and info.altura_base < ALTURA_PERSONA
				and geo.punto_en_poligono((x, y), info.huella)
			):
				return info
		return None

	def distancia_libre(self, planta_id: str, x: float, y: float, tope: float, modo: str = "paso") -> float:
		"""Distancia al segmento más cercano (como mucho ``tope``)."""
		contactos = self.contactos(planta_id, x, y, tope, modo)
		return contactos[0][0] if contactos else tope

	# ── Elementos cercanos ──

	def abertura(self, abertura_id: str) -> InfoAbertura | None:
		"""Ficha de una abertura por su id."""
		return self._aberturas.get(abertura_id)

	def objeto(self, objeto_id: str) -> InfoObjeto | None:
		"""Ficha de un objeto por su id."""
		return self._objetos.get(objeto_id)

	def elemento(self, elemento_id: str) -> Any | None:
		"""El elemento del entorno con ese id (planta, espacio, referencia, conector…), o None.

		Da lo mismo que ``Entorno.elemento`` pero sin recorrer el entorno entero
		en cada pregunta: con un barrio de miles de elementos, el motor pregunta
		por ids en los avisos, en los semáforos y al moverse por salas. El
		diccionario se hace la primera vez y se tira al reindexar.
		"""
		if not elemento_id:
			return None
		if self._elementos is None:
			elementos: dict[str, Any] = {}
			# El mismo orden de búsqueda que ``Entorno.buscar``: primero las plantas, después todo lo demás; gana el primero.
			for planta in self.entorno.plantas:
				elementos.setdefault(planta.id, planta)
			for _planta, elemento in self.entorno.elementos():
				elementos.setdefault(elemento.id, elemento)
			self._elementos = elementos
		return self._elementos.get(elemento_id)

	def aberturas_en_caja(self, planta_id: str, x0: float, y0: float, x1: float, y1: float) -> list[InfoAbertura]:
		"""Aberturas cuyo tramo puede tocar esa caja, en el orden de la planta (una preselección; ver ``_candidatas``)."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return []
		if not all(math.isfinite(valor) for valor in (x0, y0, x1, y1)):
			return list(indice.aberturas)
		return [indice.aberturas[numero] for numero in indice.rejilla_aberturas.en_caja(x0, y0, x1, y1)]

	def espacios_en_caja(self, planta_id: str, x0: float, y0: float, x1: float, y1: float) -> list[Espacio]:
		"""Espacios cuya caja puede tocar esa caja, de menor a mayor área como ``IndicePlanta.espacios`` (una preselección)."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return []
		if not all(math.isfinite(valor) for valor in (x0, y0, x1, y1)):
			return [espacio for _caja, espacio in indice.espacios]
		return [indice.espacios[numero][1] for numero in indice.rejilla_espacios.en_caja(x0, y0, x1, y1)]

	def aberturas_cerca(self, planta_id: str, x: float, y: float, radio: float) -> list[tuple[float, InfoAbertura]]:
		"""Aberturas a menos de ``radio`` (distancia a su tramo), de la más cercana a la más lejana."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return []
		cerca = [
			(info.distancia(x, y), info)
			for info in self._candidatas(indice.aberturas, indice.rejilla_aberturas, x, y, radio + 3.0)
			if abs(info.centro[0] - x) < radio + 3.0 and abs(info.centro[1] - y) < radio + 3.0
		]
		cerca = [par for par in cerca if par[0] <= radio]
		cerca.sort(key=lambda par: par[0])
		return cerca

	def objetos_cerca(self, planta_id: str, x: float, y: float, radio: float) -> list[tuple[float, InfoObjeto]]:
		"""Objetos cuya huella está a menos de ``radio``, del más cercano al más lejano."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return []
		cerca: list[tuple[float, InfoObjeto]] = []
		for info in self._candidatas(indice.objetos, indice.rejilla_objetos, x, y, radio):
			x0, y0, x1, y1 = info.caja
			if x < x0 - radio or x > x1 + radio or y < y0 - radio or y > y1 + radio:
				continue
			d = info.distancia(x, y)
			if d <= radio:
				cerca.append((d, info))
		cerca.sort(key=lambda par: par[0])
		return cerca

	def referencias_cerca(self, planta_id: str, x: float, y: float, radio: float) -> list[tuple[float, Referencia]]:
		"""Referencias a menos de ``radio``, de la más cercana a la más lejana."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return []
		referencias = indice.planta.referencias
		if indice.rejilla_referencias is None or indice.referencias_indexadas != len(referencias):
			indice.rejilla_referencias = self._rejilla_de_puntos(referencias)
			indice.referencias_indexadas = len(referencias)
		cerca = [(math.hypot(r.x - x, r.y - y), r) for r in self._candidatas(referencias, indice.rejilla_referencias, x, y, radio)]
		cerca = [par for par in cerca if par[0] <= radio]
		cerca.sort(key=lambda par: par[0])
		return cerca

	def fuentes_cerca(self, planta_id: str, x: float, y: float, radio: float) -> list[tuple[float, FuenteSonido]]:
		"""Fuentes de sonido del entorno a menos de ``radio``."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return []
		fuentes = indice.planta.fuentes
		if indice.rejilla_fuentes is None or indice.fuentes_indexadas != len(fuentes):
			indice.rejilla_fuentes = self._rejilla_de_puntos(fuentes)
			indice.fuentes_indexadas = len(fuentes)
		cerca = [(math.hypot(f.x - x, f.y - y), f) for f in self._candidatas(fuentes, indice.rejilla_fuentes, x, y, radio)]
		cerca = [par for par in cerca if par[0] <= radio]
		cerca.sort(key=lambda par: par[0])
		return cerca

	@staticmethod
	def _rejilla_de_puntos(elementos: list[Any]) -> RejillaCajas:
		"""Rejilla de elementos que son un punto (referencias, fuentes), por su orden en la lista."""
		rejilla = RejillaCajas(CELDA_ELEMENTOS)
		for elemento in elementos:
			rejilla.meter((elemento.x, elemento.y, elemento.x, elemento.y))
		return rejilla

	@staticmethod
	def _candidatas(lista: list[Any], rejilla: RejillaCajas, x: float, y: float, radio: float) -> list[Any]:
		"""Los elementos de ``lista`` cuya caja toca el cuadrado de lado 2·``radio`` alrededor del punto, en el orden de la lista.

		Es solo una preselección: quien la pide aplica después su propia
		condición, la misma que aplicaría a la lista entera. Con un radio no
		finito (o enorme) se devuelve la lista completa.
		"""
		if not math.isfinite(radio) or radio > 1e6 or not math.isfinite(x) or not math.isfinite(y):
			return lista
		return [lista[numero] for numero in rejilla.en_caja(x - radio, y - radio, x + radio, y + radio)]

	def bocas_cerca(self, planta_id: str, x: float, y: float, radio: float) -> list[tuple[float, Boca]]:
		"""Bocas de escalera o rampa a menos de ``radio``."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return []
		cerca = [(math.hypot(b.x - x, b.y - y), b) for b in indice.bocas]
		cerca = [par for par in cerca if par[0] <= radio]
		cerca.sort(key=lambda par: par[0])
		return cerca

	def paradas_cerca(self, planta_id: str, x: float, y: float, radio: float) -> list[tuple[float, InfoParada]]:
		"""Paradas de ascensor a menos de ``radio``."""
		indice = self._plantas.get(planta_id)
		if indice is None:
			return []
		cerca = [(math.hypot(p.parada.puerta.x - x, p.parada.puerta.y - y), p) for p in indice.paradas]
		cerca = [par for par in cerca if par[0] <= radio]
		cerca.sort(key=lambda par: par[0])
		return cerca

	# ── Estado dinámico ──

	def estado_abertura(self, abertura_id: str) -> str:
		"""Estado actual de una abertura en esta partida (abierta, cerrada, con_llave)."""
		estado = self._estado_abertura.get(abertura_id)
		if estado is not None:
			return estado
		info = self._aberturas.get(abertura_id)
		if info is None:
			return ""
		return "abierta" if info.abertura.tipo == "hueco" else info.abertura.estado

	def poner_abertura(self, abertura_id: str, estado: str) -> bool:
		"""Abre, cierra o echa la llave a una puerta. Devuelve si cambió algo."""
		info = self._aberturas.get(abertura_id)
		if info is None or info.seg is None or estado not in modelo.ESTADOS_ABERTURA:
			return False
		if self._estado_abertura.get(abertura_id) == estado:
			return False
		self._estado_abertura[abertura_id] = estado
		info.seg.activo = estado != "abierta"
		self.version += 1
		return True

	def deja_pasar(self, abertura_id: str, contar_cerradas: bool = False) -> bool:
		"""Si una persona puede cruzar ahora esa abertura (con ``contar_cerradas``, también si puede abrirla)."""
		info = self._aberturas.get(abertura_id)
		if info is None or info.abertura.tipo == "ventana" or not info.sobre_pared:
			return False
		if info.abertura.tipo == "hueco":
			return True
		estado = self.estado_abertura(abertura_id)
		return estado == "abierta" or (contar_cerradas and estado == "cerrada")

	def estado_objeto(self, objeto_id: str) -> str:
		"""Estado actual de un objeto en esta partida."""
		return self._estado_objeto.get(objeto_id, "")

	def poner_estado_objeto(self, objeto_id: str, estado: str) -> bool:
		"""Cambia el estado de un objeto. Devuelve si cambió."""
		info = self._objetos.get(objeto_id)
		if info is None or self._estado_objeto.get(objeto_id) == estado:
			return False
		self._estado_objeto[objeto_id] = estado
		libre = estado in info.paso_libre
		for seg in info.segs:
			seg.activo = not libre
		self.version += 1
		return True

	def reindexar(self, planta_id: str) -> None:
		"""Vuelve a indexar una planta tras editarla (modo recorrido), conservando el estado de puertas y objetos."""
		planta = self.entorno.planta(planta_id)
		if planta is None:
			return
		puertas = dict(self._estado_abertura)
		objetos = dict(self._estado_objeto)
		viejo = self._plantas.get(planta_id)
		nuevo = self._indexar(planta)
		self._elementos = None
		if viejo is not None:
			nuevo.bocas = viejo.bocas
			nuevo.paradas = viejo.paradas
		self._plantas[planta_id] = nuevo
		for info in nuevo.aberturas:
			if info.seg is not None and info.abertura.id in puertas:
				self._estado_abertura[info.abertura.id] = puertas[info.abertura.id]
				info.seg.activo = puertas[info.abertura.id] != "abierta"
		for info_objeto in nuevo.objetos:
			if info_objeto.objeto.id in objetos:
				self._estado_objeto[info_objeto.objeto.id] = objetos[info_objeto.objeto.id]
				for seg in info_objeto.segs:
					seg.activo = objetos[info_objeto.objeto.id] not in info_objeto.paso_libre
		self.version += 1
