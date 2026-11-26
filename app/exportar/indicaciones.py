"""Indicaciones paso a paso de una ruta, en texto.

El motor de navegación calcula la ruta (una lista de puntos por planta) y
aquí se convierte en lo que diría un instructor de movilidad: «Sal del aula
por la puerta y entra en el pasillo. Avanza 8 metros y gira a la derecha…».

La ruta se recibe como dato, en cualquiera de estas formas:

- una lista de puntos ``(planta_id, x, y)``, de objetos con ``planta``, ``x``
  e ``y`` (como ``Posicion``) o de diccionarios con esas claves;
- una lista de tramos ``(planta_id, [(x, y), …])`` o de diccionarios
  ``{"planta": id, "puntos": [[x, y], …]}``.

Qué se cuenta: los giros (a la derecha, a la izquierda o por horas del
reloj), las distancias (en metros o en pasos), los cambios de espacio y las
puertas que se cruzan, los pasos de peatones con lo esencial de su ficha, las
calzadas que se pisan sin paso, las escaleras exteriores y los cambios de
planta por su escalera, rampa o ascensor. En los giros y en la llegada se
nombra la referencia que haya a mano.

Las distancias salen de la geometría del entorno: son tan buenas como él.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.i18n import _, _n, separador_decimal
from app.dominio import geometria as geo
from app.dominio.geometria import Punto
from app.dominio.modelo import PASAMANOS, Abertura, Conector, Entorno, Espacio, Planta, nombre_visible
from app.exportar.fichas import NO, SI, estado_de, viene_de_mapa
from app.importar.georef import texto_atribucion

log = logging.getLogger(__name__)

# Un cambio de rumbo menor que esto no es un giro: es seguir recto.
GIRO_MINIMO = 20.0
# Paso con el que se recorre la ruta para saber en qué espacio se está.
PASO_MUESTRA = 0.25
# Dos avisos a menos de esta distancia se dicen en la misma indicación.
JUNTOS = 1.0
# Distancia máxima a la boca de un conector para considerar que la ruta lo usa.
ALCANCE_CONECTOR = 2.5

PuntoRuta = tuple[str, float, float]


@dataclass
class OpcionesIndicaciones:
	"""Cómo se quieren las indicaciones: unidad de distancia, forma de decir los giros y referencias."""

	unidad: str = "metros"
	paso_m: float = 0.65
	giros: str = "lados"
	referencias: bool = True
	radio_referencia: float = 3.0


@dataclass
class Indicacion:
	"""Una indicación: la frase y el punto de la ruta donde se da."""

	texto: str
	planta: str
	x: float
	y: float
	distancia_m: float = 0.0
	tipo: str = "avance"


@dataclass
class Indicaciones:
	"""La ruta redactada: resumen, indicaciones en orden y longitud total."""

	resumen: str
	pasos: list[Indicacion] = field(default_factory=list)
	total_m: float = 0.0
	nota: str = ""

	def lineas(self) -> list[str]:
		"""Las indicaciones numeradas, una por línea."""
		return [f"{numero}. {paso.texto}" for numero, paso in enumerate(self.pasos, start=1)]

	def a_texto(self) -> str:
		"""Texto llano: resumen, indicaciones numeradas y nota final."""
		partes = [self.resumen, ""] + self.lineas()
		if self.nota:
			partes.extend(["", self.nota])
		return "\n".join(partes) + "\n"

	def a_markdown(self) -> str:
		"""Markdown con la lista numerada, para pegar en un documento."""
		partes = [f"# {self.resumen}", ""] + self.lineas()
		if self.nota:
			partes.extend(["", self.nota])
		return "\n".join(partes) + "\n"


@dataclass
class _Aviso:
	"""Algo que pasa en un punto de un tramo de planta: un giro o un cambio de espacio."""

	distancia: float
	texto: str
	punto: Punto
	tipo: str


def normalizar_ruta(ruta: Iterable[Any]) -> list[PuntoRuta]:
	"""Convierte cualquiera de las formas admitidas de ruta en una lista de (planta, x, y)."""
	puntos: list[PuntoRuta] = []

	def anadir(planta: Any, x: Any, y: Any) -> None:
		try:
			punto = (str(planta), float(x), float(y))
		except (TypeError, ValueError) as error:
			raise ValueError(_("La ruta tiene un punto que no se entiende: {punto!r}").format(punto=(planta, x, y))) from error
		if not (math.isfinite(punto[1]) and math.isfinite(punto[2])):
			raise ValueError(_("La ruta tiene un punto con coordenadas no válidas."))
		if not puntos or puntos[-1][0] != punto[0] or math.dist(puntos[-1][1:], punto[1:]) >= 0.05:
			puntos.append(punto)

	for elemento in ruta:
		if isinstance(elemento, dict):
			if "puntos" in elemento:
				for par in elemento["puntos"]:
					anadir(elemento.get("planta", ""), par[0], par[1])
			else:
				anadir(elemento.get("planta", ""), elemento.get("x"), elemento.get("y"))
		elif hasattr(elemento, "planta") and hasattr(elemento, "x"):
			anadir(elemento.planta, elemento.x, elemento.y)
		elif (
			isinstance(elemento, (list, tuple))
			and len(elemento) == 2
			and isinstance(elemento[1], (list, tuple))
			and not isinstance(elemento[0], (list, tuple))
		):
			for par in elemento[1]:
				anadir(elemento[0], par[0], par[1])
		elif isinstance(elemento, (list, tuple)) and len(elemento) >= 3:
			anadir(elemento[0], elemento[1], elemento[2])
		else:
			raise ValueError(_("La ruta tiene un elemento que no se entiende: {elemento!r}").format(elemento=elemento))
	return puntos


class _Redactor:
	"""Recorre la ruta y va componiendo las frases."""

	def __init__(self, entorno: Entorno, opciones: OpcionesIndicaciones) -> None:
		self.entorno = entorno
		self.op = opciones
		self.pasos: list[Indicacion] = []
		self.total = 0.0
		self.giros = 0
		self.cruces = 0

	# ── Frases ──

	def distancia(self, metros: float) -> str:
		"""«12 metros», «3,5 metros» o «18 pasos», según la unidad pedida."""
		if self.op.unidad == "pasos" and self.op.paso_m > 0:
			pasos = max(1, round(metros / self.op.paso_m))
			return _n("{n} paso", "{n} pasos", pasos).format(n=pasos)
		redondeado = round(metros * 2.0) / 2.0 if metros < 10.0 else float(round(metros))
		redondeado = max(redondeado, 0.5)
		texto = f"{redondeado:.1f}".rstrip("0").rstrip(".").replace(".", separador_decimal())
		return _n("{n} metro", "{n} metros", 1 if redondeado == 1.0 else 2).format(n=texto)

	def giro(self, angulo: float) -> str:
		"""Frase de un giro; ``angulo`` es positivo a la derecha."""
		absoluto = abs(angulo)
		if self.op.giros == "reloj":
			hora = round(angulo / 30.0) % 12 or 12
			return _("gira hacia las {hora}").format(hora=hora)
		lado = _("a la derecha") if angulo > 0 else _("a la izquierda")
		if absoluto >= 160.0:
			return _("da media vuelta")
		if absoluto >= 120.0:
			return _("gira mucho {lado}, casi media vuelta").format(lado=lado)
		if absoluto >= 60.0:
			return _("gira {lado}").format(lado=lado)
		return _("gira un poco {lado}").format(lado=lado)

	def referencia_cerca(self, planta: Planta, punto: Punto) -> str:
		"""Nombre de la referencia fija más cercana a un punto, si hay alguna a mano."""
		if not self.op.referencias:
			return ""
		mejor: tuple[float, str] | None = None
		for referencia in planta.referencias:
			distancia = math.dist(punto, (referencia.x, referencia.y))
			if referencia.permanente and distancia <= self.op.radio_referencia and (mejor is None or distancia < mejor[0]):
				mejor = (distancia, referencia.nombre)
		for fuente in planta.fuentes:
			distancia = math.dist(punto, (fuente.x, fuente.y))
			if distancia <= self.op.radio_referencia and (mejor is None or distancia < mejor[0]):
				mejor = (distancia, fuente.nombre)
		return mejor[1] if mejor else ""

	@staticmethod
	def espacio_en(planta: Planta, punto: Punto) -> Espacio | None:
		"""Espacio en que cae un punto, sin contar el terreno de base de un exterior importado."""
		for espacio in planta.espacios_en(punto[0], punto[1]):
			if not espacio.datos.get("terreno_base") and not espacio.macizo:
				return espacio
		return None

	def _frase_paso(self, paso: Espacio) -> str:
		"""Lo esencial de un paso de peatones para quien va a cruzarlo ahora."""
		datos = paso.datos
		semaforo = estado_de(datos, "semaforo")
		if semaforo == SI:
			sonoro = estado_de(datos, "sonoro")
			if sonoro == SI:
				detalle = _("tiene semáforo con señal sonora")
			elif sonoro == NO:
				detalle = _("tiene semáforo sin señal sonora")
			else:
				detalle = _("tiene semáforo; si suena, el mapa no lo dice")
			if estado_de(datos, "pulsador") == SI:
				detalle += _(", con pulsador")
		elif semaforo == NO:
			detalle = _("no tiene semáforo: escucha el tráfico antes de cruzar")
		elif viene_de_mapa(datos):
			detalle = _("el mapa no dice si tiene semáforo: compruébalo antes de cruzar")
		else:
			detalle = ""
		if estado_de(datos, "isleta") == SI:
			detalle += (_("; ") if detalle else "") + _("hay una isleta en medio y se cruza en dos tiempos")
		longitud = datos.get("longitud")
		frase = _("Cruza por «{paso}»").format(paso=paso.nombre)
		if isinstance(longitud, (int, float)) and longitud > 0:
			frase += _(", de {distancia}").format(distancia=self.distancia(float(longitud)))
		return frase + (": " + detalle if detalle else "") + "."

	def _frase_entrada(self, planta: Planta, anterior: Espacio | None, nuevo: Espacio | None, a: Punto, b: Punto) -> tuple[str, str]:
		"""(frase, tipo) de pasar de un espacio a otro entre los puntos a y b."""
		puerta = self._abertura_cruzada(planta, a, b)
		if nuevo is None:
			return _("Sales de {espacio} a una zona sin detallar.").format(espacio=anterior.nombre) if anterior else "", "entrada"
		if nuevo.tipo == "paso_peatones":
			self.cruces += 1
			return self._frase_paso(nuevo), "cruce"
		if nuevo.tipo == "calzada":
			if anterior is not None and anterior.tipo in ("paso_peatones", "calzada"):
				return "", "entrada"
			self.cruces += 1
			return _("Atención: bajas a la calzada («{espacio}») sin paso de peatones.").format(espacio=nuevo.nombre), "cruce"
		if nuevo.tipo == "escalera" and planta.exterior:
			peldanos = nuevo.datos.get("peldanos")
			if isinstance(peldanos, int) and peldanos > 0:
				return _("Llegas a «{espacio}»: {peldanos}.").format(
					espacio=nuevo.nombre, peldanos=_n("{n} peldaño", "{n} peldaños", peldanos).format(n=peldanos)
				), "escaleras"
			return _("Llegas a «{espacio}»: cuenta los peldaños, que no están apuntados.").format(espacio=nuevo.nombre), "escaleras"
		if puerta is not None:
			estado = _(" (está cerrada: ábrela)") if puerta.tipo in ("puerta", "portal") and puerta.estado == "cerrada" else ""
			if puerta.estado == "con_llave" and puerta.tipo != "hueco":
				estado = _(" (está cerrada con llave)")
			return _("Cruza «{puerta}»{estado} y entra en {espacio}.").format(
				puerta=puerta.nombre or _("la puerta"), estado=estado, espacio=nuevo.nombre
			), "entrada"
		if anterior is not None and anterior.tipo == "paso_peatones" and nuevo.tipo == "acera":
			return _("Subes a {espacio}.").format(espacio=nuevo.nombre), "entrada"
		return _("Entras en {espacio}.").format(espacio=nuevo.nombre), "entrada"

	@staticmethod
	def _abertura_cruzada(planta: Planta, a: Punto, b: Punto) -> Abertura | None:
		for abertura in planta.aberturas:
			# Distancia y no cruce estricto: el punto de muestra puede caer justo sobre el umbral.
			if abertura.tipo != "ventana" and geo.distancia_segmentos(a, b, abertura.a, abertura.b) < 0.05:
				return abertura
		return None

	# ── Recorrido ──

	def tramo(self, planta: Planta, puntos: Sequence[Punto], primero: bool, ultimo: bool) -> None:
		"""Redacta el trozo de la ruta que transcurre por una planta."""
		avisos: list[_Aviso] = []
		recorrido = 0.0
		espacio = self.espacio_en(planta, puntos[0])
		rumbo_actual: float | None = None
		for i in range(len(puntos) - 1):
			a, b = puntos[i], puntos[i + 1]
			largo = geo.distancia(a, b)
			if largo < 0.05:
				continue
			rumbo = geo.rumbo_entre(a, b)
			if rumbo_actual is not None:
				angulo = geo.diferencia_rumbos(rumbo_actual, rumbo)
				if abs(angulo) >= GIRO_MINIMO:
					self.giros += 1
					cerca = self.referencia_cerca(planta, a)
					frase = self.giro(angulo).capitalize()
					if cerca:
						frase += _(", a la altura de «{referencia}»").format(referencia=cerca)
					avisos.append(
						_Aviso(recorrido, frase + _(": quedas mirando al {punto}.").format(punto=geo.punto_cardinal(rumbo)), a, "giro")
					)
			rumbo_actual = rumbo
			muestras = max(1, math.ceil(largo / PASO_MUESTRA))
			anterior_punto = a
			for k in range(1, muestras + 1):
				punto = (a[0] + (b[0] - a[0]) * k / muestras, a[1] + (b[1] - a[1]) * k / muestras)
				nuevo = self.espacio_en(planta, punto)
				if nuevo is not espacio:
					frase, tipo = self._frase_entrada(planta, espacio, nuevo, anterior_punto, punto)
					if frase:
						avisos.append(_Aviso(recorrido + largo * (k - 0.5) / muestras, frase, punto, tipo))
					espacio = nuevo
				anterior_punto = punto
			recorrido += largo
		if primero:
			inicio = self.espacio_en(planta, puntos[0])
			donde = inicio.nombre if inicio is not None else _("un punto fuera de todo espacio")
			if len(puntos) >= 2:
				texto = _("Empiezas en {espacio}, planta {planta}. Ponte mirando al {punto}.").format(
					espacio=donde, planta=planta.nombre, punto=geo.punto_cardinal(geo.rumbo_entre(puntos[0], puntos[1]))
				)
			else:
				texto = _("Empiezas en {espacio}, planta {planta}.").format(espacio=donde, planta=planta.nombre)
			self.pasos.append(Indicacion(texto, planta.id, puntos[0][0], puntos[0][1], 0.0, "salida"))
		hecho = 0.0
		i = 0
		while i < len(avisos):
			grupo = [avisos[i]]
			while i + 1 < len(avisos) and avisos[i + 1].distancia - grupo[-1].distancia <= JUNTOS:
				i += 1
				grupo.append(avisos[i])
			i += 1
			avance = grupo[0].distancia - hecho
			frases = " ".join(aviso.texto for aviso in grupo)
			texto = (_("Avanza {distancia}.").format(distancia=self.distancia(avance)) + " " + frases) if avance >= 0.4 else frases
			tipos = [aviso.tipo for aviso in grupo]
			tipo = "cruce" if "cruce" in tipos else ("giro" if "giro" in tipos else tipos[0])
			self.pasos.append(Indicacion(texto, planta.id, grupo[0].punto[0], grupo[0].punto[1], max(avance, 0.0), tipo))
			hecho = grupo[-1].distancia
		resto = recorrido - hecho
		self.total += recorrido
		fin = puntos[-1]
		if ultimo:
			destino = self.espacio_en(planta, fin)
			cerca = self.referencia_cerca(planta, fin)
			llegada = _("has llegado: estás en {espacio}").format(espacio=destino.nombre) if destino is not None else _("has llegado")
			if cerca:
				llegada += _(", junto a «{referencia}»").format(referencia=cerca)
			texto = (
				(_("Avanza {distancia} y {llegada}.").format(distancia=self.distancia(resto), llegada=llegada))
				if resto >= 0.4
				else llegada.capitalize() + "."
			)
			self.pasos.append(Indicacion(texto, planta.id, fin[0], fin[1], max(resto, 0.0), "llegada"))
		elif resto >= 0.4:
			self.pasos.append(
				Indicacion(_("Avanza {distancia}.").format(distancia=self.distancia(resto)), planta.id, fin[0], fin[1], resto, "avance")
			)

	def cambio_de_planta(self, desde: PuntoRuta, hasta: PuntoRuta) -> None:
		"""Redacta el paso de una planta a otra por el conector que une esos dos puntos."""
		origen, destino = self.entorno.planta(desde[0]), self.entorno.planta(hasta[0])
		nombre_destino = destino.nombre if destino is not None else hasta[0]
		sube = (destino.altura_m if destino is not None else 0.0) >= (origen.altura_m if origen is not None else 0.0)
		conector = self._conector(desde, hasta)
		if conector is None:
			texto = _("Cambia a la planta {planta}.").format(planta=nombre_destino)
		elif conector.tipo == "ascensor":
			texto = _("Toma «{conector}» hasta la planta {planta}.").format(conector=conector.nombre, planta=nombre_destino)
			if conector.datos.get("aviso_hablado"):
				texto += " " + _("Avisa de la planta con voz.")
		else:
			verbo = _("Sube") if sube else _("Baja")
			texto = _("{verbo} por «{conector}» hasta la planta {planta}").format(
				verbo=verbo, conector=conector.nombre, planta=nombre_destino
			)
			peldanos = sum(tramo.peldanos for tramo in conector.tramos)
			if peldanos:
				texto += ": " + _n("{n} peldaño", "{n} peldaños", peldanos).format(n=peldanos)
			pasamanos = str(conector.datos.get("pasamanos") or "")
			if pasamanos in PASAMANOS and pasamanos != "ninguno":
				texto += _(", pasamanos {lado}").format(lado=nombre_visible(PASAMANOS, pasamanos).lower())
			texto += "."
		self.pasos.append(Indicacion(texto, hasta[0], hasta[1], hasta[2], 0.0, "planta"))

	def _conector(self, desde: PuntoRuta, hasta: PuntoRuta) -> Conector | None:
		mejor: tuple[float, Conector] | None = None
		for conector in self.entorno.conectores:
			cerca_origen = min((math.dist(p.punto, desde[1:]) for p in conector.posiciones() if p.planta == desde[0]), default=math.inf)
			cerca_destino = min((math.dist(p.punto, hasta[1:]) for p in conector.posiciones() if p.planta == hasta[0]), default=math.inf)
			if (
				cerca_origen <= ALCANCE_CONECTOR
				and cerca_destino <= ALCANCE_CONECTOR
				and (mejor is None or cerca_origen + cerca_destino < mejor[0])
			):
				mejor = (cerca_origen + cerca_destino, conector)
		return mejor[1] if mejor else None


def redactar(entorno: Entorno, ruta: Iterable[Any], opciones: OpcionesIndicaciones | None = None) -> Indicaciones:
	"""Redacta las indicaciones paso a paso de una ruta sobre un entorno.

	``ruta`` es la lista de puntos por planta que da el motor de navegación
	(ver las formas admitidas en la cabecera del módulo). Lanza ``ValueError``
	si la ruta está vacía o nombra una planta que no existe.
	"""
	opciones = opciones or OpcionesIndicaciones()
	puntos = normalizar_ruta(ruta)
	if not puntos:
		raise ValueError(_("La ruta está vacía."))
	tramos: list[list[PuntoRuta]] = []
	for punto in puntos:
		if tramos and tramos[-1][-1][0] == punto[0]:
			tramos[-1].append(punto)
		else:
			tramos.append([punto])
	redactor = _Redactor(entorno, opciones)
	for numero, tramo in enumerate(tramos):
		planta = entorno.planta(tramo[0][0])
		if planta is None:
			raise ValueError(_("La ruta pasa por una planta que no existe en el entorno: «{planta}».").format(planta=tramo[0][0]))
		if numero > 0:
			redactor.cambio_de_planta(tramos[numero - 1][-1], tramo[0])
		redactor.tramo(planta, [(p[1], p[2]) for p in tramo], numero == 0, numero == len(tramos) - 1)
	partes = [_("Ruta de {distancia}").format(distancia=redactor.distancia(redactor.total))]
	partes.append(_n("{n} giro", "{n} giros", redactor.giros).format(n=redactor.giros))
	if redactor.cruces:
		partes.append(_n("{n} cruce de calzada", "{n} cruces de calzada", redactor.cruces).format(n=redactor.cruces))
	if len(tramos) > 1:
		partes.append(_n("{n} cambio de planta", "{n} cambios de planta", len(tramos) - 1).format(n=len(tramos) - 1))
	nota = _("Las distancias son aproximadas.")
	atribucion = texto_atribucion(entorno.procedencia)
	if atribucion:
		nota = _("Datos del mapa: {atribucion}. Las distancias son aproximadas.").format(atribucion=atribucion)
	log.info("Indicaciones redactadas: %s pasos, %s metros", len(redactor.pasos), round(redactor.total, 1))
	return Indicaciones(resumen=", ".join(partes) + ".", pasos=redactor.pasos, total_m=round(redactor.total, 2), nota=nota)


__all__ = ["Indicacion", "Indicaciones", "OpcionesIndicaciones", "normalizar_ruta", "redactar"]
