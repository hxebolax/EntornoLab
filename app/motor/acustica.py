"""Fuentes continuas audibles: qué se oye, desde dónde y cuánto lo tapan las paredes.

Para cada cosa que suena (fuentes del entorno, objetos con sonido propio,
semáforos, vehículos, premios y balizas de la actividad) se decide:

- si llega en línea recta, suena en su sitio;
- si hay una pared en medio, se busca el camino más corto que el sonido puede
  seguir por puertas, huecos y ventanas, y la fuente se sitúa en la abertura
  de ese camino que el alumno tiene a la vista: se oye «por la puerta», que es
  justo la pista que una persona ciega usa para encontrarla. Una puerta
  cerrada quita más que una abierta;
- si no hay camino, queda lo poco que atraviesa el tabique, muy apagado;
- de otra planta solo llega lo que sube o baja por el hueco de una escalera.

``volumen`` y ``filtro`` llevan SOLO eso (oclusión y camino). La atenuación
por distancia la aplica la capa de sonido a partir de ``pos`` (ver
``docs/sonido.md``); por eso, cuando la fuente se recoloca en una puerta, el
volumen se corrige para que el nivel corresponda a la longitud real del camino
y no a la distancia hasta la puerta: ninguna pista de distancia engañosa.
"""

from __future__ import annotations

import heapq
import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.dominio.geometria import Punto
from app.motor import eventos as ev
from app.motor.movimiento import sonido_de_objeto
from app.motor.mundo import InfoAbertura

if TYPE_CHECKING:
	from app.motor.sesion import Sesion

log = logging.getLogger(__name__)

# Cada cuánto se recalculan las fuentes fijas (las móviles, en cada consulta).
PERIODO = 0.12
# Lo que deja pasar cada cosa (ganancia) y cuánto apaga (filtro).
GANANCIA_PUERTA_CERRADA = 0.5
GANANCIA_VENTANA = 0.55
GANANCIA_PARED = 0.28
FILTRO_ESQUINA = 0.15
FILTRO_CERRADA = 0.45
FILTRO_PARED = 0.85
GANANCIA_ESCALERA = 0.7
FILTRO_ESCALERA = 0.25
# Metros que «cuesta» al buscar camino pasar por algo que tapa (para preferir las puertas abiertas).
PENA_CERRADA = 4.0
PENA_ESQUINA = 1.0
VOLUMEN_MINIMO = 0.02
ALCANCE_PORTALES = 40.0


@dataclass
class Emisor:
	"""Algo que suena de forma continua (o a intervalos) en un punto de una planta."""

	id: str
	sonido: str
	planta_id: str
	x: float
	y: float
	altura: float = 1.0
	volumen: float = 1.0
	radio: float = 12.0
	bucle: bool = True
	intervalo: float = 0.0
	tono: float = 1.0
	movil: bool = False
	bus: str = "ambiente"
	eco: bool = True
	ocluir: bool = True
	nombre: str = ""
	# Si es el sonido propio de un objeto que solo suena en un estado (una lavadora en marcha): cuál y en cuál.
	objeto_id: str = ""
	estado: str = ""

	@property
	def punto(self) -> Punto:
		"""El punto (x, y)."""
		return self.x, self.y


@dataclass(slots=True)
class Llegada:
	"""Cómo llega un sonido de un punto a otro de la misma planta."""

	punto: Punto  # desde dónde se oye (la fuente, o la abertura visible del camino)
	recta: float  # metros del oyente a ese punto
	camino: float  # metros totales que recorre el sonido
	ganancia: float  # 0..1, sin contar la distancia
	filtro: float  # 0..1
	por_abertura: str = ""  # id de la abertura por la que llega, si no llega directo
	alcance: float = 0.0  # metros que «gasta» del radio de la fuente (más que el camino si atraviesa un tabique)

	@property
	def nivel(self) -> float:
		"""Nivel con el que se percibe (para comparar caminos): ganancia por la ley de la distancia."""
		return self.ganancia / max(1.0, self.camino)


class Acustica:
	"""Calcula las fuentes continuas que se oyen ahora."""

	def __init__(self, sesion: Sesion) -> None:
		self.s = sesion
		self.fijos: list[Emisor] = []
		self.extras: dict[str, Emisor] = {}
		self._temporizadores: dict[str, float] = {}
		self._vecinos: dict[str, dict[int, list[tuple[int, float]]]] = {}
		self._ven_emisor: dict[tuple[str, int], list[tuple[int, float]]] = {}
		self._cache: list[ev.FuenteActiva] = []
		self._visibles: list[tuple[int, float]] = []
		self._cache_en: tuple | None = None
		self._portales_planta: dict[str, tuple[Any, list[InfoAbertura], dict[int, int]]] = {}
		self._recoger_fijos()

	# ── Emisores ──

	def _recoger_fijos(self) -> None:
		"""Fuentes del entorno y objetos con sonido propio."""
		for indice in self.s.mundo.plantas():
			planta = indice.planta
			for fuente in planta.fuentes:
				if not fuente.sonido:
					continue
				continuo = fuente.bucle or fuente.intervalo <= 0.0
				self.fijos.append(
					Emisor(
						id=fuente.id,
						sonido=ev.sonido_de_serie(fuente.sonido),
						planta_id=planta.id,
						x=fuente.x,
						y=fuente.y,
						altura=fuente.altura,
						volumen=max(0.0, min(1.0, fuente.volumen)),
						radio=max(1.0, fuente.radio),
						bucle=continuo,
						intervalo=0.0 if continuo else fuente.intervalo,
						nombre=fuente.nombre,
					)
				)
			for info in indice.objetos:
				propio = info.sonidos.get("propio")
				if not isinstance(propio, dict) or not propio.get("sonido"):
					continue
				try:
					volumen = float(propio.get("volumen", 0.6))
					radio = float(propio.get("radio", 8.0))
				except TypeError, ValueError:
					log.warning("El sonido propio del objeto %s tiene un volumen o un radio que no son números", info.objeto.id)
					volumen, radio = 0.6, 8.0
				self.fijos.append(
					Emisor(
						id=f"obj-son:{info.objeto.id}",
						sonido=sonido_de_objeto(info, str(propio["sonido"])),
						planta_id=planta.id,
						x=info.objeto.x,
						y=info.objeto.y,
						altura=min(1.5, max(0.3, info.objeto.alto * 0.6)),
						volumen=max(0.0, min(1.0, volumen)),
						radio=max(1.0, radio),
						nombre=info.objeto.nombre,
						objeto_id=info.objeto.id,
						estado=str(propio.get("estado") or ""),
					)
				)
		for emisor in self.fijos:
			if emisor.intervalo > 0.0:
				self._temporizadores[emisor.id] = self.s.azar.uniform(0.0, emisor.intervalo)

	def anadir(self, emisor: Emisor) -> None:
		"""Añade (o sustituye) una fuente de la actividad: un premio, una baliza, un personaje."""
		emisor.sonido = ev.sonido_de_serie(emisor.sonido)
		self.extras[emisor.id] = emisor
		self._ven_emisor = {clave: valor for clave, valor in self._ven_emisor.items() if clave[0] != emisor.id}
		if emisor.intervalo > 0.0 and not emisor.bucle:
			self._temporizadores[emisor.id] = emisor.intervalo
		self._cache_en = None

	def quitar(self, emisor_id: str) -> bool:
		"""Quita una fuente añadida. Devuelve si existía."""
		self._temporizadores.pop(emisor_id, None)
		self._cache_en = None
		return self.extras.pop(emisor_id, None) is not None

	# ── Grafo de aberturas por donde pasa el sonido ──

	def _portales(self, planta_id: str) -> list[InfoAbertura]:
		"""Aberturas de la planta por las que pasa el sonido (las que están en una pared), en su orden.

		Se guardan por índice de planta, con el número de cada una: en un barrio
		hay miles, y esto se pedía en cada cálculo de lo que se oye.
		"""
		indice = self.s.mundo.planta(planta_id)
		if indice is None:
			return []
		guardado = self._portales_planta.get(planta_id)
		if guardado is None or guardado[0] is not indice:
			portales = [info for info in indice.aberturas if info.sobre_pared]
			guardado = (indice, portales, {id(info): numero for numero, info in enumerate(portales)})
			self._portales_planta[planta_id] = guardado
		return guardado[1]

	def _portales_cerca(self, planta_id: str, punto: Punto, alcance: float, portales: list[InfoAbertura]) -> list[tuple[int, InfoAbertura]]:
		"""(número, abertura) de los portales cuyo centro puede estar a ``alcance`` del punto, de menor a mayor número.

		Es una preselección por la rejilla del mundo: quien la usa mira después la
		distancia exacta, como antes hacía con todos.
		"""
		guardado = self._portales_planta.get(planta_id)
		if guardado is None or guardado[1] is not portales or not math.isfinite(alcance):
			return list(enumerate(portales))
		numeros = guardado[2]
		cerca: list[tuple[int, InfoAbertura]] = []
		for info in self.s.mundo.aberturas_en_caja(
			planta_id, punto[0] - alcance, punto[1] - alcance, punto[0] + alcance, punto[1] + alcance
		):
			numero = numeros.get(id(info))
			if numero is not None:
				cerca.append((numero, info))
		cerca.sort(key=lambda par: par[0])
		return cerca

	def _ganancia_portal(self, info: InfoAbertura) -> tuple[float, float, float]:
		"""(ganancia, filtro añadido, metros de penalización) de pasar por una abertura en su estado actual."""
		abertura = info.abertura
		if abertura.tipo == "ventana":
			return GANANCIA_VENTANA, FILTRO_CERRADA, PENA_CERRADA
		if abertura.tipo == "hueco" or self.s.mundo.estado_abertura(abertura.id) == "abierta":
			return 1.0, 0.0, 0.0
		return GANANCIA_PUERTA_CERRADA, FILTRO_CERRADA, PENA_CERRADA

	def _se_oyen(self, planta_id: str, a: Punto, b: Punto) -> bool:
		"""Si entre dos puntos no hay ninguna pared que tape del todo."""
		return self.s.mundo.atenuacion(planta_id, a, b)[0] == 0

	def _vecinos_de(self, planta_id: str, numero: int, portales: list[InfoAbertura]) -> list[tuple[int, float]]:
		"""Aberturas que «se ven» desde otra (sin pared en medio), con su distancia. Las paredes no cambian: se recuerda."""
		planta = self._vecinos.setdefault(planta_id, {})
		vecinos = planta.get(numero)
		if vecinos is None:
			vecinos = []
			origen = portales[numero].centro
			for otro, info in self._portales_cerca(planta_id, origen, ALCANCE_PORTALES, portales):
				if otro == numero:
					continue
				d = math.hypot(info.centro[0] - origen[0], info.centro[1] - origen[1])
				if d <= ALCANCE_PORTALES and self._se_oyen(planta_id, origen, info.centro):
					vecinos.append((otro, d))
			planta[numero] = vecinos
		return vecinos

	def _visibles_desde(self, planta_id: str, punto: Punto, portales: list[InfoAbertura], alcance: float) -> list[tuple[int, float]]:
		visibles: list[tuple[int, float]] = []
		for numero, info in self._portales_cerca(planta_id, punto, alcance, portales):
			d = math.hypot(info.centro[0] - punto[0], info.centro[1] - punto[1])
			if d <= alcance and self._se_oyen(planta_id, punto, info.centro):
				visibles.append((numero, d))
		return visibles

	def llegada(
		self,
		planta_id: str,
		oyente: Punto,
		fuente: Punto,
		alcance: float,
		visibles_oyente: list[tuple[int, float]] | None = None,
		clave_fuente: tuple[str, int] | None = None,
		un_salto: bool = False,
	) -> Llegada | None:
		"""Cómo llega el sonido de ``fuente`` a ``oyente`` en una planta; None si no llega dentro de ``alcance`` metros.

		``visibles_oyente`` son las aberturas que el oyente tiene a la vista (se
		calculan si no se dan); ``clave_fuente`` permite recordar las que ve una
		fuente fija. ``un_salto`` limita el camino a una sola abertura: es lo
		que se usa con lo que se mueve (un coche), que hay que recalcular en
		cada fotograma.
		"""
		mundo = self.s.mundo
		recta = math.hypot(fuente[0] - oyente[0], fuente[1] - oyente[1])
		if recta > alcance:
			return None
		totales, transmision = mundo.atenuacion(planta_id, oyente, fuente)
		mejor: Llegada | None = None
		if totales == 0:
			if transmision >= 0.999:
				return Llegada(fuente, recta, recta, 1.0, 0.0)
			# Solo una puerta cerrada o una ventana en medio: se oye a través, apagado.
			mejor = Llegada(fuente, recta, recta, 0.3 + 0.7 * transmision, min(0.9, 1.0 - transmision))
		else:
			ganancia = GANANCIA_PARED**totales * transmision
			# Un tabique no alarga el camino, pero acorta hasta dónde llega la fuente: cada uno la deja en la mitad.
			efectiva = recta * (1.0 + totales)
			if efectiva <= alcance:
				mejor = Llegada(fuente, recta, recta, ganancia, min(0.97, FILTRO_PARED + 0.06 * (totales - 1)), "", efectiva)
		portales = self._portales(planta_id)
		if not portales:
			return mejor
		if visibles_oyente is None:
			visibles_oyente = self._visibles_desde(planta_id, oyente, portales, alcance)
		if not visibles_oyente:
			return mejor
		if un_salto:
			for numero, d in visibles_oyente:
				centro = portales[numero].centro
				resto = math.hypot(centro[0] - fuente[0], centro[1] - fuente[1])
				if d + resto > alcance or not self._se_oyen(planta_id, centro, fuente):
					continue
				ganancia, filtro, _pena = self._ganancia_portal(portales[numero])
				candidata = Llegada(centro, d, d + resto, ganancia, min(0.9, filtro + FILTRO_ESQUINA), portales[numero].abertura.id)
				if mejor is None or candidata.nivel > mejor.nivel:
					mejor = candidata
			return mejor
		if clave_fuente is not None:
			metas = self._ven_emisor.get(clave_fuente)
			if metas is None:
				metas = self._visibles_desde(planta_id, fuente, portales, ALCANCE_PORTALES)
				self._ven_emisor[clave_fuente] = metas
		else:
			metas = self._visibles_desde(planta_id, fuente, portales, alcance)
		if not metas:
			return mejor
		final = {numero: d for numero, d in metas}
		# Dijkstra por las aberturas: coste = metros + penalización de lo que tapa.
		costes: dict[int, float] = {}
		datos: dict[int, tuple[float, float, float, int, int]] = {}  # metros, ganancia, filtro, primera abertura, saltos
		monton: list[tuple[float, int]] = []
		for numero, d in visibles_oyente:
			ganancia, filtro, pena = self._ganancia_portal(portales[numero])
			coste = d + pena + PENA_ESQUINA
			if coste < costes.get(numero, math.inf):
				costes[numero] = coste
				datos[numero] = (d, ganancia, filtro, numero, 1)
				heapq.heappush(monton, (coste, numero))
		hechos: set[int] = set()
		mejor_coste = math.inf
		elegido: tuple[float, float, float, int, int] | None = None
		while monton:
			coste, numero = heapq.heappop(monton)
			if numero in hechos or coste > costes.get(numero, math.inf):
				continue
			hechos.add(numero)
			if coste >= mejor_coste:
				break
			metros, ganancia, filtro, primera, saltos = datos[numero]
			if numero in final and metros + final[numero] <= alcance:
				total = coste + final[numero]
				if total < mejor_coste:
					mejor_coste = total
					elegido = (metros + final[numero], ganancia, filtro, primera, saltos)
			if metros > alcance:
				continue
			for otro, d in self._vecinos_de(planta_id, numero, portales):
				if otro in hechos:
					continue
				ganancia_otro, filtro_otro, pena = self._ganancia_portal(portales[otro])
				nuevo = coste + d + pena + PENA_ESQUINA
				if nuevo < costes.get(otro, math.inf):
					costes[otro] = nuevo
					datos[otro] = (metros + d, ganancia * ganancia_otro, filtro + filtro_otro, primera, saltos + 1)
					heapq.heappush(monton, (nuevo, otro))
		if elegido is not None:
			metros, ganancia, filtro, primera, saltos = elegido
			centro = portales[primera].centro
			por_puerta = Llegada(
				centro,
				math.hypot(centro[0] - oyente[0], centro[1] - oyente[1]),
				metros,
				ganancia,
				min(0.9, filtro + FILTRO_ESQUINA * saltos),
				portales[primera].abertura.id,
			)
			if mejor is None or por_puerta.nivel > mejor.nivel:
				mejor = por_puerta
		return mejor

	# ── Fuentes activas ──

	def _activa(self, emisor: Emisor, llegada: Llegada, extra_ganancia: float = 1.0, extra_filtro: float = 0.0) -> ev.FuenteActiva | None:
		"""Convierte una llegada en fuente activa, con el volumen corregido para la longitud real del camino."""
		gastado = max(llegada.camino, llegada.alcance)
		if gastado > emisor.radio:
			return None
		borde = emisor.radio * 0.25
		fundido = min(1.0, (emisor.radio - gastado) / borde) if borde > 0 else 1.0
		# La capa de sonido atenuará por la distancia a ``pos``; aquí se compensa lo que falta hasta el camino real.
		correccion = max(1.0, llegada.recta) / max(1.0, llegada.camino)
		volumen = emisor.volumen * llegada.ganancia * extra_ganancia * correccion * fundido
		if volumen < VOLUMEN_MINIMO:
			return None
		z = self.s.mundo.altura(self.s.jugador.planta) + emisor.altura
		return ev.FuenteActiva(
			id=emisor.id,
			sonido=emisor.sonido,
			pos=(llegada.punto[0], llegada.punto[1], z),
			volumen=min(1.0, volumen),
			tono=emisor.tono,
			filtro=min(0.97, llegada.filtro + extra_filtro),
			bucle=emisor.bucle,
			eco=emisor.eco,
			bus=emisor.bus,
		)

	def propagar(self, emisor: Emisor, visibles: list[tuple[int, float]] | None = None) -> ev.FuenteActiva | None:
		"""Fuente activa que corresponde a un emisor para el oyente actual, o None si no se oye."""
		s = self.s
		jugador = s.jugador
		oyente = (jugador.x, jugador.y)
		if not emisor.ocluir:
			recta = math.hypot(emisor.x - oyente[0], emisor.y - oyente[1])
			if emisor.planta_id != jugador.planta:
				return None
			return self._activa(emisor, Llegada(emisor.punto, recta, recta, 1.0, 0.0))
		if emisor.planta_id == jugador.planta:
			if abs(emisor.x - oyente[0]) > emisor.radio or abs(emisor.y - oyente[1]) > emisor.radio:
				return None
			clave = None if emisor.movil else (emisor.id, 0)
			llegada = self.llegada(jugador.planta, oyente, emisor.punto, emisor.radio, visibles, clave, un_salto=emisor.movil)
			return self._activa(emisor, llegada) if llegada is not None else None
		# Otra planta: solo por el hueco de una escalera o una rampa.
		mejor: ev.FuenteActiva | None = None
		indice = s.mundo.planta(jugador.planta)
		if indice is None:
			return None
		for numero, boca in enumerate(indice.bocas):
			if boca.destino != emisor.planta_id:
				continue
			otra = boca.tramo.hasta if boca.sentido > 0 else boca.tramo.desde
			resto = emisor.radio - boca.tramo.longitud_m
			if resto <= 0:
				continue
			lejos = self.llegada(
				emisor.planta_id, (otra.x, otra.y), emisor.punto, resto, None, None if emisor.movil else (emisor.id, 1 + numero)
			)
			if lejos is None:
				continue
			cerca = self.llegada(jugador.planta, oyente, boca.punto, resto - lejos.camino, visibles)
			if cerca is None:
				continue
			total = Llegada(
				cerca.punto,
				cerca.recta,
				cerca.camino + boca.tramo.longitud_m + lejos.camino,
				cerca.ganancia * lejos.ganancia,
				cerca.filtro + lejos.filtro,
			)
			activa = self._activa(emisor, total, GANANCIA_ESCALERA, FILTRO_ESCALERA)
			if activa is not None and (mejor is None or activa.volumen > mejor.volumen):
				mejor = activa
		return mejor

	def fuentes(self) -> list[ev.FuenteActiva]:
		"""Las fuentes continuas que se oyen ahora, con su posición aparente, su volumen y su filtro."""
		s = self.s
		jugador = s.jugador
		if jugador.modo == "ascensor":
			# Dentro de la cabina no llega nada de fuera.
			return []
		marca = (jugador.planta, s.mundo.version, len(self.extras))
		previa = self._cache_en
		if (
			previa is None
			or previa[:3] != marca
			or s.t - previa[3] >= PERIODO
			or math.hypot(previa[4] - jugador.x, previa[5] - jugador.y) > 0.25
		):
			portales = self._portales(jugador.planta)
			visibles = self._visibles_desde(jugador.planta, (jugador.x, jugador.y), portales, ALCANCE_PORTALES)
			self._visibles = visibles
			activas: list[ev.FuenteActiva] = []
			for emisor in self.fijos:
				if emisor.intervalo > 0.0 or (emisor.estado and s.mundo.estado_objeto(emisor.objeto_id) != emisor.estado):
					continue
				activa = self.propagar(emisor, visibles)
				if activa is not None:
					activas.append(activa)
			for emisor in self.extras.values():
				if emisor.movil or (emisor.intervalo > 0.0 and not emisor.bucle):
					continue
				activa = self.propagar(emisor, visibles)
				if activa is not None:
					activas.append(activa)
			self._cache = activas
			self._cache_en = (*marca, s.t, jugador.x, jugador.y)
		resultado = list(self._cache)
		moviles = [e for e in self.extras.values() if e.movil and e.bucle] + s.dinamica.emisores()
		for emisor in moviles:
			activa = self.propagar(emisor, self._visibles)
			if activa is not None:
				resultado.append(activa)
		return resultado

	# ── Fuentes a intervalos ──

	def disparar(self, emisor_id: str) -> None:
		"""Hace sonar ahora mismo, una vez, una fuente añadida (con su oclusión) y la quita."""
		emisor = self.extras.get(emisor_id)
		if emisor is None:
			return
		self.quitar(emisor_id)
		if self.s.jugador.modo == "ascensor":
			return
		activa = self.propagar(emisor)
		if activa is not None:
			self.s.emitir(
				ev.EvSonido(activa.sonido, pos=activa.pos, volumen=activa.volumen, tono=activa.tono, bus=emisor.bus, filtro=activa.filtro)
			)

	def tic(self, dt: float) -> None:
		"""Dispara las fuentes que suenan a intervalos (un reloj que da las horas, un pájaro)."""
		if not self._temporizadores:
			return
		s = self.s
		for emisor_id in list(self._temporizadores):
			self._temporizadores[emisor_id] -= dt
			if self._temporizadores[emisor_id] > 0.0:
				continue
			emisor = self.extras.get(emisor_id) or next((e for e in self.fijos if e.id == emisor_id), None)
			if emisor is None or emisor.intervalo <= 0.0:
				del self._temporizadores[emisor_id]
				continue
			self._temporizadores[emisor_id] += emisor.intervalo
			if s.jugador.modo == "ascensor":
				continue
			activa = self.propagar(emisor)
			if activa is not None:
				s.emitir(
					ev.EvSonido(
						activa.sonido, pos=activa.pos, volumen=activa.volumen, tono=activa.tono, bus=emisor.bus, filtro=activa.filtro
					)
				)
