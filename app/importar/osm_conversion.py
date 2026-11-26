"""Conversión de datos de OpenStreetMap en un entorno editable de EntornoLab.

OpenStreetMap describe una calle con una línea (su eje) y unas etiquetas; el
alumno necesita superficies por las que andar. Este módulo hace ese paso:

- cada calle con coches da una vía (para el tráfico), su calzada y sus
  aceras, que son espacios editables;
- las aceras salen del mapa cuando el mapa las dice (``sidewalk=*`` o vías
  ``footway=sidewalk``) y, si solo hay eje, se DEDUCEN por anchura hasta la
  fachada; el informe dice cuáles son deducidas;
- cruces con su forma, pasos de peatones con su ficha, edificios macizos con
  portales y números, plazas, parques, senderos, escaleras, paradas, lugares,
  barreras y obstáculos.

Dos reglas mandan sobre todo lo demás:

1. Nada inventado. Lo que el mapa no dice se guarda como «desconocido» y se
   dice «el mapa no lo dice»; lo que se estima (anchuras, carriles, tráfico)
   se anota como estimado.
2. El resultado es un borrador que tiene que poder abrirse y recorrerse: un
   elemento con geometría imposible se deja fuera y se anota en el informe,
   en lugar de hacer fallar la importación entera.
"""

from __future__ import annotations

import datetime
import logging
import math
import time
from collections import Counter
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.i18n import N_, _, _n, separador_decimal
from app.dominio import edicion as ed
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.geometria import Poligono, Punto
from app.dominio.modelo import SUELO_POR_TIPO, SUELOS, Abertura, Entorno, Espacio, Objeto, Planta, Via
from app.exportar.fichas import DESCONOCIDO, NO, SI, atributos_que_faltan, ficha_escalera, ficha_paso
from app.importar import formas
from app.importar import osm_etiquetas as et
from app.importar.comun import (
	Cancelado,
	ErrorImportacion,
	Informe,
	Progreso,
	ResultadoImportacion,
	avisar_fase,
	candidatos_en_rejilla,
	comprobar_cancelacion,
	fijar_inicio_valido,
	frase_cuenta,
)
from app.importar.georef import ATRIBUCION, FUENTE_OSM, LICENCIA, URL_LICENCIA, Proyeccion

log = logging.getLogger(__name__)

# Lado máximo de la zona que se convierte (metros). Un fichero .osm más grande
# hay que recortarlo indicando centro y radio en las opciones.
LADO_MAXIMO_M = 1000.0
ANCHO_PORTAL = 1.2
# Anchura mínima de una acera para que merezca existir, y máxima que se deduce hasta la fachada.
ACERA_MINIMA = 0.9
ACERA_HASTA_FACHADA = 4.0
# Media calzada mínima cuando las fachadas obligan a estrecharla.
MEDIA_CALZADA_MINIMA = 1.2
ALCANCE_FACHADA = 14.0
# Trozo de acera más corto que esto no se crea: sería un pegote entre dos cruces.
TRAMO_MINIMO_ACERA = 1.5
# Una zona que entra en el recuadro menos que esto (y menos de esa fracción de
# su superficie) es el borde de una zona de fuera: no se importa.
AREA_MINIMA_BORDE = 10.0
FRACCION_MINIMA_BORDE = 0.1
# Segundos mínimos entre dos avisos de progreso dentro de una fase: el diálogo
# solo necesita unos pocos por segundo y cada aviso cuesta formatear un texto.
INTERVALO_AVISOS = 0.1
# Celda (metros) de las rejillas con que se buscan los elementos cercanos.
CELDA_REJILLA = 20.0

# Etiquetas que no cambian cómo es una vía: no impiden unir dos tramos en una misma calle.
_IRRELEVANTES = (
	"source",
	"note",
	"fixme",
	"created_by",
	"check_date",
	"survey",
	"wikidata",
	"wikipedia",
	"old_name",
	"alt_name",
	"lit",
	"ref",
)
_PREFIJOS_IRRELEVANTES = ("name:", "source:", "check_date:", "note:", "old_name:", "alt_name:", "is_in")

_ATRIBUTOS_PASO = {
	"semaforo": "semáforo",
	"sonoro": "señal sonora",
	"vibracion": "vibración",
	"pulsador": "pulsador",
	"isleta": "isleta",
	"tactil": "pavimento táctil",
	"bordillo": "bordillo",
}


@dataclass
class OpcionesOSM:
	"""Lo que el profesional puede decidir al convertir.

	``centro`` (latitud, longitud) será el (0, 0) del entorno; con ``radio_m``
	además se recorta a ese radio, que es como se importa un trozo de un
	fichero grande. Sin ellos se usa el recuadro de los datos.
	"""

	nombre: str = ""
	descripcion: str = ""
	autor: str = ""
	centro: tuple[float, float] | None = None
	radio_m: float | None = None
	recuadro: tuple[float, float, float, float] | None = None
	aceras: bool = True
	deducir_aceras: bool = True
	ancho_acera: float = 2.0
	edificios: bool = True
	lugares: bool = True
	obstaculos: bool = True
	vias_de_servicio: bool = True
	terreno_base: bool = True
	interiores: bool = False
	catalogo: Catalogo | None = None


@dataclass
class Area:
	"""Un contorno cerrado del mapa con sus etiquetas (una vía cerrada o un multipolígono)."""

	osm: str
	etiquetas: dict[str, str]
	puntos: list[Punto]
	ids: list[int] = field(default_factory=list)


@dataclass(eq=False)
class _Tramo:
	"""Trozo de una vía del mapa ya recortado al recuadro; varios se unen en una cadena."""

	puntos: list[Punto]
	ids: list[int | None]
	etiquetas: dict[str, str]
	osm: list[int]
	# Lo que sigue se rellena al convertir la cadena en calle.
	via: Via | None = None
	eje: list[Punto] = field(default_factory=list)
	mitad: float = 0.0
	nombre: str = ""
	cerrada: bool = False


def numero(texto: str | None) -> float | None:
	"""Primer número de un texto de etiqueta («3,5 m», «30 mph», «8%»); None si no hay."""
	if not texto:
		return None
	acumulado = ""
	for caracter in texto.strip().replace(",", "."):
		if caracter.isdigit() or (caracter in ".-" and caracter not in acumulado):
			acumulado += caracter
		elif acumulado:
			break
	try:
		valor = float(acumulado)
	except ValueError:
		return None
	return valor if math.isfinite(valor) else None


def nombre_de_obstaculo(tipo: str, nombre: str) -> str:
	"""Nombre de un obstáculo del mapa: su clase y, si el mapa le da nombre, ese nombre.

	En un mapa real el ``name`` de un panel informativo es el de lo que
	explica: en la Plaza Mayor de Valladolid hay dos paneles llamados
	«Iglesia de Santiago» e «Iglesia de la Pasión». Dicho a secas, el
	alumno creería que ha tocado una iglesia. Si el nombre ya dice la clase
	(«Fuente de la Plaza» para una fuente), se deja tal cual.
	"""
	nombre = " ".join(nombre.split())
	if not nombre:
		return tipo
	primera = tipo.split()[0].lower() if tipo.split() else ""
	if primera and primera in nombre.lower():
		return nombre
	return _("{tipo} «{nombre}»").format(tipo=tipo, nombre=nombre)


def _m(valor: float) -> str:
	texto = f"{valor:.1f}".rstrip("0").rstrip(".")
	return (texto or "0").replace(".", separador_decimal())


def _clave_cadena(etiquetas: dict[str, str]) -> frozenset[tuple[str, str]]:
	"""Etiquetas que definen cómo es una vía: dos tramos con la misma clave son la misma calle."""
	return frozenset(
		(clave, valor) for clave, valor in etiquetas.items() if clave not in _IRRELEVANTES and not clave.startswith(_PREFIJOS_IRRELEVANTES)
	)


def _reversible(etiquetas: dict[str, str]) -> bool:
	"""True si la vía se puede recorrer al revés sin que cambie el sentido de sus etiquetas."""
	if etiquetas.get("oneway", "no") not in ("no", "false", "0"):
		return False
	if etiquetas.get("junction") in ("roundabout", "circular"):
		return False
	for clave, valor in etiquetas.items():
		if valor in ("left", "right", "up", "down", "forward", "backward"):
			return False
		if ":left" in clave or ":right" in clave or ":forward" in clave or ":backward" in clave:
			return False
	return "incline" not in etiquetas


def _unir(a: _Tramo, b: _Tramo, grado: Counter[int]) -> _Tramo | None:
	"""Une dos tramos de la misma calle que comparten un extremo; None si no se tocan.

	Una calle sin nombre solo se une donde no hay bifurcación: si no, saldría
	una «vía sin nombre» kilométrica que da la vuelta a la manzana.
	"""
	con_nombre = bool(a.etiquetas.get("name"))

	def vale(nodo: int | None) -> bool:
		return nodo is not None and (con_nombre or grado[nodo] == 2)

	b_puntos, b_ids = b.puntos, b.ids
	if a.ids[-1] == b_ids[0] and vale(a.ids[-1]):
		puntos, ids = a.puntos + b_puntos[1:], a.ids + b_ids[1:]
	elif b_ids[-1] == a.ids[0] and vale(a.ids[0]):
		puntos, ids = b_puntos + a.puntos[1:], b_ids + a.ids[1:]
	elif _reversible(b.etiquetas) and a.ids[-1] == b_ids[-1] and vale(a.ids[-1]):
		puntos, ids = a.puntos + b_puntos[::-1][1:], a.ids + b_ids[::-1][1:]
	elif _reversible(b.etiquetas) and a.ids[0] == b_ids[0] and vale(a.ids[0]):
		puntos, ids = b_puntos[::-1] + a.puntos[1:], b_ids[::-1] + a.ids[1:]
	else:
		return None
	if ids[0] is not None and ids[0] == ids[-1]:
		# Cerraría un anillo: se dejan como dos tramos, que dan polígonos simples.
		return None
	return _Tramo(puntos, ids, a.etiquetas, a.osm + b.osm)


def encadenar(tramos: Sequence[_Tramo], grado: Counter[int]) -> list[_Tramo]:
	"""Agrupa los tramos que son la misma calle (mismas etiquetas y extremos compartidos) en cadenas."""
	grupos: dict[frozenset[tuple[str, str]], list[_Tramo]] = {}
	for tramo in tramos:
		grupos.setdefault(_clave_cadena(tramo.etiquetas), []).append(tramo)
	cadenas: list[_Tramo] = []
	for grupo in grupos.values():
		pendientes = list(grupo)
		while pendientes:
			actual = pendientes.pop(0)
			unido = True
			while unido:
				unido = False
				for otro in pendientes:
					union = _unir(actual, otro, grado)
					if union is not None:
						actual = union
						pendientes.remove(otro)
						unido = True
						break
			cadenas.append(actual)
	return cadenas


def forma_de_cruce(rumbos: Sequence[float]) -> str:
	"""Clave de la forma de un cruce según los rumbos de sus ramas: t, y, cruz, aspa, desalineado o complejo."""
	n = len(rumbos)
	rectas: list[tuple[int, int]] = []
	for i in range(n):
		for j in range(i + 1, n):
			if abs(abs(geo.diferencia_rumbos(rumbos[i], rumbos[j])) - 180.0) <= 30.0:
				rectas.append((i, j))
	if n == 3:
		return "t" if rectas else "y"
	if n == 4:
		usados = {k for par in rectas for k in par}
		if len(rectas) >= 2 and len(usados) == 4:
			angulo = abs(geo.diferencia_rumbos(rumbos[rectas[0][0]], rumbos[rectas[1][0]]))
			return "cruz" if 60.0 <= angulo <= 120.0 else "aspa"
		return "desalineado"
	return "complejo"


def _anillos(vias: list[list[int]]) -> list[list[int]]:
	"""Cose las vías exteriores de un multipolígono en anillos cerrados de nodos."""
	pendientes = [list(v) for v in vias if len(v) >= 2]
	anillos: list[list[int]] = []
	while pendientes:
		actual = pendientes.pop(0)
		avanzado = True
		while actual[0] != actual[-1] and avanzado:
			avanzado = False
			for otro in pendientes:
				if otro[0] == actual[-1]:
					actual.extend(otro[1:])
				elif otro[-1] == actual[-1]:
					actual.extend(otro[::-1][1:])
				else:
					continue
				pendientes.remove(otro)
				avanzado = True
				break
		if actual[0] == actual[-1] and len(actual) >= 4:
			anillos.append(actual)
	return anillos


class _IndiceDeLista:
	"""Rejilla sobre una lista que solo crece (los espacios de la planta, sus aberturas, las fachadas).

	La conversión añade elementos y pregunta «¿qué hay cerca?» a la vez: el
	índice se pone al día solo con lo que se haya añadido desde la última
	consulta. Si la lista se sustituye o encoge, se rehace entero.
	"""

	def __init__(self, caja_de: Callable[[Any], formas.Caja], margen: float = 0.0) -> None:
		self._caja_de = caja_de
		self._margen = margen
		self._lista: list[Any] | None = None
		self._vistos = 0
		self._rejilla = formas.RejillaCajas(CELDA_REJILLA)

	def cerca(self, lista: list[Any], caja: formas.Caja, margen: float = 0.0) -> list[Any]:
		"""Elementos de ``lista`` cuya caja puede tocar ``caja``, en el orden de la lista."""
		if lista is not self._lista or len(lista) < self._vistos:
			self._lista = lista
			self._vistos = 0
			self._rejilla = formas.RejillaCajas(CELDA_REJILLA)
		for indice in range(self._vistos, len(lista)):
			self._rejilla.anadir(indice, self._caja_de(lista[indice]), self._margen)
		self._vistos = len(lista)
		return [lista[indice] for indice in self._rejilla.cerca(caja, margen)]


class _IdsSecuenciales:
	"""Generador de ids para el entorno que se está creando, sin recorrerlo entero cada vez.

	``Entorno.nuevo_id`` repasa todos los ids en uso para no repetir ninguno:
	es lo correcto para un entorno editado a mano, pero al crear miles de
	elementos seguidos hacía la conversión cuadrática (con 2.000 espacios, el
	40 % del tiempo se iba ahí). Mientras se convierte, TODOS los ids salen de
	aquí: el primero se pide al método de siempre (que sincroniza el
	contador con lo que ya hubiera) y los siguientes solo suben el contador.
	Salen exactamente los mismos ids que con el método de siempre.
	"""

	def __init__(self, entorno: Entorno) -> None:
		self._entorno = entorno
		self._sincronizado = False

	def __call__(self, prefijo: str) -> str:
		if not self._sincronizado:
			self._sincronizado = True
			return Entorno.nuevo_id(self._entorno, prefijo)
		self._entorno.contador_ids += 1
		return f"{prefijo}-{self._entorno.contador_ids}"

	@classmethod
	def instalar(cls, entorno: Entorno) -> None:
		"""Hace que ``entorno.nuevo_id`` (y con él ``id_para``) use este generador."""
		entorno.nuevo_id = cls(entorno)  # type: ignore[method-assign]

	@staticmethod
	def retirar(entorno: Entorno) -> None:
		"""Devuelve al entorno su ``nuevo_id`` de siempre y comprueba que no se repitió ningún id."""
		entorno.__dict__.pop("nuevo_id", None)
		ids = entorno.ids()
		if len(ids) != len(set(ids)):
			repetidos = sorted(clave for clave, veces in Counter(ids).items() if veces > 1)
			log.error("La conversión de OpenStreetMap ha dado ids repetidos: %s", ", ".join(repetidos[:10]))


class Conversor:
	"""Estado de una conversión: los datos indexados, el entorno que se va formando y el informe."""

	def __init__(self, datos: dict[str, Any], opciones: OpcionesOSM, progreso: Progreso | None, cancelado: Cancelado | None) -> None:
		self.datos = datos
		self.op = opciones
		self.progreso = progreso
		self.cancelado = cancelado
		self.informe = Informe()
		self.catalogo = opciones.catalogo
		self.etiquetas_nodo: dict[int, dict[str, str]] = {}
		self.vias_osm: dict[int, tuple[list[int], dict[str, str]]] = {}
		self.relaciones: list[tuple[int, dict[str, str], list[dict[str, Any]]]] = []
		self.xy: dict[int, Punto] = {}
		self.caja: formas.Caja = (0.0, 0.0, 0.0, 0.0)
		self.recuadro: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
		self.proyeccion = Proyeccion(0.0, 0.0)
		self.entorno = Entorno()
		self.planta = Planta()
		self.areas: list[Area] = []
		self.macizos: list[Espacio] = []
		self.fachadas: list[tuple[Punto, Punto, formas.Caja]] = []
		self.cadenas: list[_Tramo] = []
		self.ramas: dict[int, list[tuple[_Tramo, float, bool]]] = {}
		self.vias_de_paso: list[_Tramo] = []
		self.aceras_dibujadas: list[Punto] = []
		self.nodos_usados: set[int] = set()
		self.edificios_con_interior: list[Area] = []
		self.apariciones: dict[int, list[tuple[_Tramo, int]]] = {}
		self._grado: Counter[int] = Counter()
		self._nombres: Counter[str] = Counter()
		# Índices espaciales: ver ``_IndiceDeLista``.
		self._indice_espacios = _IndiceDeLista(lambda espacio: espacio.caja())
		self._indice_macizos = _IndiceDeLista(lambda espacio: espacio.caja())
		self._indice_fachadas = _IndiceDeLista(lambda fachada: fachada[2])
		self._indices_aberturas: dict[int, tuple[Planta, _IndiceDeLista]] = {}
		# Progreso por fases: (clave, texto de la fase, fracción al empezar, fracción al acabar).
		self._fases: list[tuple[str, str, float, float]] = []
		self._fase_actual: tuple[str, str, float, float] = ("", "", 0.0, 0.0)
		self._ultimo_aviso = 0.0
		self._inicio_fase = time.monotonic()
		#: Segundos que ha durado cada fase, para el registro.
		self.duraciones: dict[str, float] = {}

	# ── Progreso por fases ──

	def _fase(self, fraccion: float, texto: str) -> None:
		comprobar_cancelacion(self.cancelado)
		avisar_fase(self.progreso, fraccion, texto, texto)

	def _entrar(self, clave: str, detalle: str = "") -> None:
		"""Empieza la fase ``clave`` de la tabla: anota cuánto duró la anterior y lo dice."""
		comprobar_cancelacion(self.cancelado)
		nueva = next((fase for fase in self._fases if fase[0] == clave), None)
		if nueva is None:
			log.debug("Fase «%s» sin entrada en la tabla de fases; se sigue contando en la anterior.", clave)
			return
		ahora = time.monotonic()
		anterior = self._fase_actual[0]
		if anterior:
			self.duraciones[anterior] = self.duraciones.get(anterior, 0.0) + ahora - self._inicio_fase
		self._inicio_fase = ahora
		self._fase_actual = nueva
		_clave, nombre, inicio, _fin = nueva
		self._ultimo_aviso = ahora
		avisar_fase(self.progreso, inicio, nombre, detalle or _("{fase}…").format(fase=nombre))

	def _avance(self, hecho: int, total: int) -> None:
		"""Avisa de cuánto lleva la fase actual («Convirtiendo calles: 12 de 30») y comprueba si se canceló.

		Se puede llamar en cada vuelta de un bucle: solo avisa unas pocas
		veces por segundo y siempre al terminar.
		"""
		comprobar_cancelacion(self.cancelado)
		ahora = time.monotonic()
		if hecho < total and ahora - self._ultimo_aviso < INTERVALO_AVISOS:
			return
		self._ultimo_aviso = ahora
		_clave, nombre, inicio, fin = self._fase_actual
		parte = min(1.0, hecho / total) if total > 0 else 1.0
		avisar_fase(
			self.progreso,
			inicio + (fin - inicio) * parte,
			nombre,
			_("{fase}: {hecho} de {total}.").format(fase=nombre, hecho=hecho, total=total),
			hecho,
			total,
		)

	def _terminar_fases(self) -> None:
		"""Anota la duración de la última fase."""
		anterior = self._fase_actual[0]
		if anterior:
			self.duraciones[anterior] = self.duraciones.get(anterior, 0.0) + time.monotonic() - self._inicio_fase
		self._fase_actual = ("", "", 1.0, 1.0)

	# ── Búsquedas por cercanía ──

	def espacios_en(self, x: float, y: float) -> list[Espacio]:
		"""Lo mismo que ``self.planta.espacios_en`` pero mirando solo los espacios cercanos."""
		candidatos = self._indice_espacios.cerca(self.planta.espacios, (x, y, x, y), 1e-5)
		dentro = [espacio for espacio in candidatos if len(espacio.contorno) >= 3 and espacio.contiene(x, y)]
		dentro.sort(key=lambda espacio: espacio.area())
		return dentro

	def espacio_en(self, x: float, y: float, incluir_macizos: bool = True) -> Espacio | None:
		"""Lo mismo que ``self.planta.espacio_en`` pero mirando solo los espacios cercanos."""
		for espacio in self.espacios_en(x, y):
			if incluir_macizos or not espacio.macizo:
				return espacio
		return None

	def nombre_unico(self, base: str) -> str:
		"""«Escaleras», «Escaleras 2», «Escaleras 3»: distingue lo que el mapa deja sin nombre."""
		self._nombres[base] += 1
		return base if self._nombres[base] == 1 else f"{base} {self._nombres[base]}"

	def espacio(self, nombre: str, contorno: Sequence[Punto], planta: Planta | None = None, **opciones: Any) -> Espacio | None:
		"""Crea un espacio; si su contorno no vale, lo anota en el informe y devuelve None."""
		try:
			return ed.crear_espacio_poligonal(self.entorno, planta or self.planta, nombre, contorno, permitir_solape=True, **opciones)
		except ed.ErrorEdicion as error:
			log.info("No se pudo crear el espacio «%s»: %s", nombre, error)
			self.informe.anotar_aviso(_("«{nombre}» no se ha importado: su contorno en el mapa no es válido.").format(nombre=nombre))
			return None

	def pisa_abertura(self, planta: Planta, tramo: tuple[Punto, Punto]) -> bool:
		"""True si en ese tramo de pared ya hay otra abertura (dos entradas del mapa casi en el mismo punto).

		Solo se miran las aberturas cercanas (rejilla): con 1.300 portales,
		comparar cada uno con todos los anteriores era cuadrático. El margen
		cubre la tolerancia de 5 cm de ``intervalo_sobre_segmento``.
		"""
		guardado = self._indices_aberturas.get(id(planta))
		if guardado is None or guardado[0] is not planta:
			guardado = (planta, _IndiceDeLista(lambda abertura: geo.caja((abertura.a, abertura.b))))
			self._indices_aberturas[id(planta)] = guardado
		for otra in guardado[1].cerca(planta.aberturas, geo.caja(tramo), 0.1):
			intervalo = geo.intervalo_sobre_segmento(tramo[0], tramo[1], otra.a, otra.b)
			if intervalo is not None and intervalo[1] - intervalo[0] > 0.01:
				return True
		return False

	def suelo_de(self, etiquetas: dict[str, str], defecto: str, clave: str = "surface") -> str:
		"""Suelo del modelo que corresponde a la superficie del mapa, o el de serie si no la dice."""
		suelo = et.SUELOS_SUPERFICIE.get(etiquetas.get(clave, ""), defecto)
		return suelo if suelo in SUELOS else defecto

	def dentro(self, punto: Punto, margen: float = 0.0) -> bool:
		"""True si el punto cae en el recuadro que se importa."""
		return formas.dentro_de_caja(punto, self.caja, margen)

	def puntos_de(self, ids: Sequence[int]) -> tuple[list[Punto], list[int]]:
		"""Puntos locales de una lista de nodos (los que falten en los datos se saltan)."""
		puntos: list[Punto] = []
		presentes: list[int] = []
		for nodo in ids:
			punto = self.xy.get(nodo)
			if punto is not None:
				puntos.append(punto)
				presentes.append(nodo)
		return puntos, presentes

	# ── Lectura de los datos ──

	def indexar(self) -> None:
		"""Ordena los elementos del mapa y fija el recuadro, el centro y la proyección."""
		elementos = self.datos.get("elements") if isinstance(self.datos, dict) else None
		if not isinstance(elementos, list):
			raise ErrorImportacion(_("Los datos no son de OpenStreetMap: falta la lista de elementos."))
		nodos: dict[int, tuple[float, float]] = {}
		for elemento in elementos:
			if not isinstance(elemento, dict):
				continue
			try:
				identificador = int(elemento["id"])
				etiquetas_brutas = elemento.get("tags")
				etiquetas = {str(k): str(v) for k, v in etiquetas_brutas.items()} if isinstance(etiquetas_brutas, dict) else {}
				tipo = elemento.get("type")
				if tipo == "node":
					lat, lon = float(elemento["lat"]), float(elemento["lon"])
					if not (math.isfinite(lat) and math.isfinite(lon)):
						continue
					nodos[identificador] = (lat, lon)
					if etiquetas:
						self.etiquetas_nodo[identificador] = etiquetas
				elif tipo == "way":
					self.vias_osm[identificador] = ([int(n) for n in elemento.get("nodes") or []], etiquetas)
				elif tipo == "relation":
					miembros = [m for m in elemento.get("members") or [] if isinstance(m, dict)]
					self.relaciones.append((identificador, etiquetas, miembros))
			except KeyError, TypeError, ValueError:
				log.debug("Elemento de OpenStreetMap mal formado; se descarta.")
		if not nodos:
			raise ErrorImportacion(_("Los datos de OpenStreetMap no contienen ningún punto: la zona está vacía o el fichero no es válido."))
		recuadro = self._recuadro_inicial(nodos)
		centro = (
			self.op.centro or self._par(self.datos.get("centro")) or ((recuadro[0] + recuadro[2]) / 2.0, (recuadro[1] + recuadro[3]) / 2.0)
		)
		self.proyeccion = Proyeccion(centro[0], centro[1])
		if self.op.radio_m:
			radio = float(self.op.radio_m)
			sur, oeste = self.proyeccion.a_latlon(-radio, -radio)
			norte, este = self.proyeccion.a_latlon(radio, radio)
			recuadro = (sur, oeste, norte, este)
		x0, y0 = self.proyeccion.a_xy(recuadro[0], recuadro[1])
		x1, y1 = self.proyeccion.a_xy(recuadro[2], recuadro[3])
		if x1 - x0 > LADO_MAXIMO_M or y1 - y0 > LADO_MAXIMO_M:
			raise ErrorImportacion(
				_(
					"La zona mide {ancho} por {alto} metros y el máximo que se puede convertir son {maximo} por {maximo}. "
					"Indique un centro y un radio para importar solo una parte."
				).format(ancho=round(x1 - x0), alto=round(y1 - y0), maximo=round(LADO_MAXIMO_M))
			)
		if x1 - x0 < 5.0 or y1 - y0 < 5.0:
			raise ErrorImportacion(_("La zona es demasiado pequeña para importarla (menos de 5 metros de lado)."))
		self.recuadro = recuadro
		self.caja = (x0, y0, x1, y1)
		self.xy = {nodo: self.proyeccion.a_xy(lat, lon) for nodo, (lat, lon) in nodos.items()}

	@staticmethod
	def _par(valor: Any) -> tuple[float, float] | None:
		if isinstance(valor, (list, tuple)) and len(valor) == 2:
			try:
				return float(valor[0]), float(valor[1])
			except TypeError, ValueError:
				return None
		return None

	def _recuadro_inicial(self, nodos: dict[int, tuple[float, float]]) -> tuple[float, float, float, float]:
		for candidato in (self.op.recuadro, self.datos.get("recuadro")):
			if isinstance(candidato, (list, tuple)) and len(candidato) == 4:
				try:
					sur, oeste, norte, este = (float(v) for v in candidato)
				except TypeError, ValueError:
					continue
				if sur < norte and oeste < este:
					return sur, oeste, norte, este
		latitudes = [lat for lat, _lon in nodos.values()]
		longitudes = [lon for _lat, lon in nodos.values()]
		return min(latitudes), min(longitudes), max(latitudes), max(longitudes)

	def crear_entorno(self) -> None:
		"""Entorno vacío con su planta de calle y, si se pide, el terreno de base."""
		nombre = self.op.nombre.strip() or _("Zona importada de OpenStreetMap")
		descripcion = self.op.descripcion or _("Borrador importado de OpenStreetMap. Revíselo y complételo antes de usarlo con un alumno.")
		self.entorno = ed.crear_entorno(nombre, descripcion, self.op.autor)
		_IdsSecuenciales.instalar(self.entorno)
		self.planta = ed.crear_planta(self.entorno, _("Calle"), nivel=0, exterior=True)
		if self.op.terreno_base:
			x0, y0, x1, y1 = self.caja
			self.espacio(
				_("Terreno sin detallar"),
				geo.rectangulo(x0, y0, x1 - x0, y1 - y0),
				tipo="exterior",
				descripcion=_("Lo que queda entre los elementos importados. El mapa no dice qué hay aquí: revíselo in situ."),
				datos={"terreno_base": True},
			)
			self.informe.anotar_deducido(
				_(
					"Se ha puesto un «Terreno sin detallar» debajo de todo, para que la zona se pueda recorrer entera. El mapa no dice qué hay en esos huecos."
				)
			)

	def reunir_areas(self) -> None:
		"""Junta todos los contornos cerrados del mapa: vías cerradas y multipolígonos."""
		consumidas: set[int] = set()
		for identificador, etiquetas, miembros in self.relaciones:
			if etiquetas.get("type") != "multipolygon":
				continue
			propias = {k: v for k, v in etiquetas.items() if k != "type"}
			exteriores = [
				int(m["ref"])
				for m in miembros
				if m.get("type") == "way" and m.get("role") in ("outer", "") and isinstance(m.get("ref"), int)
			]
			if not propias:
				for via in exteriores:
					propias = dict(self.vias_osm.get(via, ([], {}))[1])
					if propias:
						break
			if not propias:
				continue
			if any(m.get("role") == "inner" for m in miembros) and "building" in propias:
				self.informe.anotar_revisar(
					_(
						"Hay edificios con patio interior en el mapa: se han importado como bloques macizos enteros. Revise si el patio es accesible."
					)
				)
			for anillo in _anillos([self.vias_osm[via][0] for via in exteriores if via in self.vias_osm]):
				puntos, ids = self.puntos_de(anillo[:-1])
				if len(puntos) >= 3:
					self.areas.append(Area(f"relation/{identificador}", propias, puntos, ids))
			consumidas.update(exteriores)
		for identificador, (nodos, etiquetas) in self.vias_osm.items():
			if not etiquetas or identificador in consumidas or len(nodos) < 4 or nodos[0] != nodos[-1]:
				continue
			puntos, ids = self.puntos_de(nodos[:-1])
			if len(puntos) >= 3:
				self.areas.append(Area(f"way/{identificador}", etiquetas, puntos, ids))

	# ── Edificios ──

	def edificios(self) -> None:
		"""Edificios como bloques macizos, con sus portales y sus números."""
		creados = 0
		sin_nombre = 0
		portales = 0
		portales_sin_numero = 0
		ajustados = self._contornos_de_edificios()
		total = sum(1 for area in self.areas if area.etiquetas.get("building", "no") != "no" and "indoor" not in area.etiquetas)
		hechos = 0
		for indice, area in enumerate(self.areas):
			etiquetas = area.etiquetas
			clase = etiquetas.get("building", "no")
			if clase == "no" or "indoor" in etiquetas:
				continue
			hechos += 1
			self._avance(hechos, total)
			contorno = ajustados.get(indice) or formas.limpiar_poligono(area.puntos)
			if len(contorno) < 3 or not self.dentro(geo.centroide(contorno)):
				continue
			if etiquetas.get("location") == "underground" or (numero(etiquetas.get("layer")) or 0.0) < 0:
				self.informe.anotar_revisar(_("Hay construcciones subterráneas en el mapa que no se han importado."))
				continue
			if any(area is otro for otro in self.edificios_con_interior):
				continue
			# Los contornos de ``ajustados`` ya se comprobaron con esta misma regla:
			# no se repite la comprobación (cuesta el cuadrado de los vértices).
			if indice not in ajustados and not formas.poligono_valido(contorno, 1.0):
				self.informe.anotar_aviso(
					_("Un edificio ({osm}) no se ha importado: su contorno en el mapa se corta a sí mismo o es demasiado pequeño.").format(
						osm=area.osm
					)
				)
				continue
			tipo_dicho = _(et.EDIFICIOS.get(clase, et.EDIFICIOS["yes"]))
			if clase in et.EDIFICIOS_ABIERTOS or etiquetas.get("building:walls") == "no":
				self.espacio(
					etiquetas.get("name") or self.nombre_unico(_("Zona cubierta")),
					contorno,
					tipo="exterior",
					descripcion=_("Tiene techo pero no paredes, según el mapa: se puede pasar por debajo."),
					datos={"osm": area.osm, "cubierta": True},
				)
				continue
			numero_portal = etiquetas.get("addr:housenumber", "")
			calle = etiquetas.get("addr:street", "")
			nombre = etiquetas.get("name", "")
			if not nombre:
				sin_nombre += 1
				if numero_portal and calle:
					nombre = _("{tipo} de {calle}, {numero}").format(tipo=tipo_dicho.capitalize(), calle=calle, numero=numero_portal)
				elif numero_portal:
					nombre = _("{tipo} número {numero}").format(tipo=tipo_dicho.capitalize(), numero=numero_portal)
				else:
					nombre = self.nombre_unico(tipo_dicho.capitalize())
			partes = [tipo_dicho.capitalize() + "."]
			lugar = self._tipo_de_lugar(etiquetas)
			if lugar is not None:
				partes.append(_("Es un sitio de tipo «{tipo}».").format(tipo=_(lugar[1])))
			plantas = numero(etiquetas.get("building:levels"))
			if plantas:
				partes.append(
					_n("Tiene {n} planta, según el mapa.", "Tiene {n} plantas, según el mapa.", round(plantas)).format(n=round(plantas))
				)
			if numero_portal:
				partes.append(_("Dirección: {calle} {numero}.").format(calle=calle, numero=numero_portal).replace("  ", " "))
			espacio = self.espacio(
				nombre,
				contorno,
				tipo="edificio",
				cerrado=True,
				macizo=True,
				descripcion=" ".join(partes),
				datos={"osm": area.osm, "numero": numero_portal, "calle": calle},
			)
			if espacio is None:
				continue
			creados += 1
			self.macizos.append(espacio)
			for a, b in espacio.lados():
				self.fachadas.append((a, b, geo.caja((a, b))))
			entradas = [nodo for nodo in area.ids if self._es_entrada(self.etiquetas_nodo.get(nodo, {}))]
			for nodo in entradas:
				datos_nodo = self.etiquetas_nodo[nodo]
				numero_de_este = datos_nodo.get("addr:housenumber") or (
					numero_portal if len(entradas) == 1 or datos_nodo.get("entrance") == "main" else ""
				)
				if self._portal(espacio, nodo, datos_nodo, numero_de_este):
					portales += 1
					portales_sin_numero += 0 if numero_de_este else 1
		if creados:
			self.informe.contar("edificios", creados)
			self.informe.contar("portales", portales)
			self.informe.anotar_importado(
				_("{edificios}, como bloques macizos en los que no se entra, con {portales}.").format(
					edificios=frase_cuenta(creados, "{n} edificio", "{n} edificios"),
					portales=frase_cuenta(portales, "{n} portal", "{n} portales"),
				)
			)
			self.informe.anotar_revisar(
				_(
					"Los portales de los edificios macizos son referencias para orientarse: no dan paso. Si quiere que se entre en un edificio, dibuje su interior."
				)
			)
		if sin_nombre:
			self.informe.anotar_falta(
				_n("{n} edificio no tiene nombre en el mapa.", "{n} edificios no tienen nombre en el mapa.", sin_nombre).format(
					n=sin_nombre
				)
			)
		if portales_sin_numero:
			self.informe.anotar_falta(
				_n("{n} portal no tiene número en el mapa.", "{n} portales no tienen número en el mapa.", portales_sin_numero).format(
					n=portales_sin_numero
				)
			)
		if creados and not portales:
			self.informe.anotar_falta(_("El mapa no marca ningún portal en los edificios de la zona."))

	def _contornos_de_edificios(self) -> dict[int, Poligono]:
		"""Contornos de los edificios macizos (por índice en ``self.areas``) con las medianeras ajustadas.

		Con datos reales, los edificios pegados se pisan unos centímetros
		(probado con la Plaza Mayor de Valladolid: 17 parejas, de 0,01 a 0,09
		metros cuadrados). Se ajustan antes de crear los espacios para que el
		borrador no salga con un aviso por cada medianera.
		"""
		indices: list[int] = []
		contornos: list[Poligono] = []
		for indice, area in enumerate(self.areas):
			etiquetas = area.etiquetas
			clase = etiquetas.get("building", "no")
			if clase == "no" or "indoor" in etiquetas or clase in et.EDIFICIOS_ABIERTOS or etiquetas.get("building:walls") == "no":
				continue
			contorno = formas.limpiar_poligono(area.puntos)
			if formas.poligono_valido(contorno, 1.0) and self.dentro(geo.centroide(contorno), 50.0):
				indices.append(indice)
				contornos.append(contorno)
		return dict(zip(indices, formas.ajustar_medianeras(contornos), strict=True))

	@staticmethod
	def _es_entrada(etiquetas: dict[str, str]) -> bool:
		if "level" in etiquetas or "indoor" in etiquetas:
			return False
		return etiquetas.get("entrance", "no") != "no" or "addr:housenumber" in etiquetas

	def _portal(self, edificio: Espacio, nodo: int, etiquetas: dict[str, str], numero_portal: str) -> bool:
		"""Abre el portal en el lado del edificio donde el mapa pone la entrada. True si se creó."""
		punto = self.xy[nodo]
		indice, distancia = formas.lado_mas_cercano(edificio.contorno, punto)
		a, b = edificio.lados()[indice]
		tramo = formas.tramo_centrado(a, b, punto, ANCHO_PORTAL) if distancia < 1.0 else None
		clase = _(et.ENTRADAS.get(etiquetas.get("entrance", "yes"), et.ENTRADAS["yes"]))
		if numero_portal:
			nombre = _("Portal número {numero} de {edificio}").format(numero=numero_portal, edificio=edificio.nombre)
		else:
			nombre = _("{entrada} de {edificio}").format(entrada=clase, edificio=edificio.nombre)
		partes = [clase + "."]
		if not numero_portal:
			partes.append(_("Número: el mapa no lo dice."))
		calle = etiquetas.get("addr:street") or str(edificio.datos.get("calle") or "")
		if calle:
			partes.append(_("Da a {calle}, según su dirección.").format(calle=calle))
		silla = etiquetas.get("wheelchair")
		if silla == "yes":
			partes.append(_("Accesible en silla de ruedas, según el mapa."))
		elif silla == "no":
			partes.append(_("Con escalón o no accesible en silla de ruedas, según el mapa."))
		self.nodos_usados.add(nodo)
		if tramo is None or self.pisa_abertura(self.planta, tramo):
			ed.anadir_referencia(self.entorno, self.planta, nombre, punto[0], punto[1], tipo="portal", descripcion=" ".join(partes))
			return True
		hoja = "batiente"
		if etiquetas.get("automatic_door", "no") != "no":
			hoja = "automatica"
		elif etiquetas.get("door") == "sliding":
			hoja = "corredera"
		portal = Abertura(
			nombre=nombre,
			descripcion=" ".join(partes),
			tipo="portal",
			a=tramo[0],
			b=tramo[1],
			estado="cerrada",
			hoja=hoja,
			material="metal",
		)
		portal.id = self.entorno.id_para(portal)
		self.planta.aberturas.append(portal)
		return True

	# ── Áreas: plazas, parques, agua ──

	def zonas(self) -> None:
		"""Plazas, parques, zonas peatonales, agua y aparcamientos: superficies con nombre."""
		cuenta: Counter[str] = Counter()
		for area in self.areas:
			etiquetas = area.etiquetas
			if etiquetas.get("building", "no") != "no" or "indoor" in etiquetas:
				continue
			clase = self._clase_de_area(etiquetas)
			if clase is None:
				continue
			tipo, nombre_tipo, suelo = clase
			contorno = formas.limpiar_poligono(formas.recortar_poligono(area.puntos, self.caja))
			if not formas.poligono_valido(contorno, 1.0):
				if len(contorno) >= 3:
					self.informe.anotar_aviso(
						_("«{nombre}» ({osm}) no se ha importado: su contorno, recortado a la zona, no es válido.").format(
							nombre=etiquetas.get("name") or _(nombre_tipo), osm=area.osm
						)
					)
				continue
			if self._es_borde_de_fuera(area.puntos, contorno):
				log.info("La zona %s queda casi entera fuera del recuadro; no se importa el borde que entra.", area.osm)
				continue
			nombre = etiquetas.get("name") or self.nombre_unico(_(nombre_tipo))
			suelo_final = self.suelo_de(etiquetas, suelo or SUELO_POR_TIPO.get(tipo, "hormigon"))
			partes = [_(nombre_tipo) + "."]
			if "surface" not in etiquetas:
				partes.append(_("Suelo: el mapa no lo dice; se ha puesto el habitual."))
			if suelo_final == "agua":
				partes.append(_("Es agua: no se pisa."))
			if (
				self.espacio(nombre, contorno, tipo=tipo, suelo=suelo_final, descripcion=" ".join(partes), datos={"osm": area.osm})
				is not None
			):
				cuenta[tipo] += 1
		if cuenta:
			self.informe.contar("zonas", sum(cuenta.values()))
			self.informe.anotar_importado(
				_("{n} zonas: plazas, parques, zonas peatonales y otras superficies.").format(n=sum(cuenta.values()))
				if sum(cuenta.values()) != 1
				else _("1 zona (plaza, parque u otra superficie).")
			)

	@staticmethod
	def _es_borde_de_fuera(original: Sequence[Punto], recortado: Sequence[Punto]) -> bool:
		"""True si lo que entra en el recuadro es solo una tira del borde de una zona que está fuera.

		Con datos reales pasa en cada importación: una plaza vecina asoma unos
		centímetros por el lado del recuadro (en Valladolid, 3,7 metros
		cuadrados de la Plaza de la Fuente Dorada). Con su nombre, esa tira
		haría creer al alumno que ha llegado a la plaza.
		"""
		return geo.area(recortado) < AREA_MINIMA_BORDE and geo.area(recortado) < geo.area(original) * FRACCION_MINIMA_BORDE

	@staticmethod
	def _clase_de_area(etiquetas: dict[str, str]) -> tuple[str, str, str] | None:
		for clave in et.CLAVES_AREA:
			clase = et.AREAS.get((clave, etiquetas.get(clave, "")))
			if clase is None:
				continue
			if clave == "highway" and etiquetas.get("area") != "yes":
				continue
			return clase
		return None

	# ── Calles ──

	def _tramos(self) -> tuple[list[_Tramo], list[_Tramo]]:
		"""Vías del mapa recortadas al recuadro: (con coches, peatonales)."""
		rodados: list[_Tramo] = []
		peatonales: list[_Tramo] = []
		for identificador, (nodos, etiquetas) in self.vias_osm.items():
			clase = etiquetas.get("highway", "")
			if not clase or clase in et.VIAS_DESCARTADAS or etiquetas.get("area") == "yes":
				continue
			base = clase.removesuffix("_link")
			es_rodada = base in et.VIAS_RODADAS
			if not es_rodada and base not in et.VIAS_PEATONALES:
				continue
			if (
				"level" in etiquetas
				or etiquetas.get("indoor", "no") != "no"
				or etiquetas.get("tunnel") == "yes"
				or etiquetas.get("location") == "underground"
			):
				continue
			if es_rodada and base == "service" and not self.op.vias_de_servicio:
				continue
			if not es_rodada and len(nodos) >= 4 and nodos[0] == nodos[-1] and self._clase_de_area(etiquetas) is not None:
				# Una plaza dibujada como vía peatonal cerrada con ``place=square`` (la Plaza Mayor
				# de Valladolid) ya es una zona: como línea daría además una franja con su nombre
				# alrededor del borde, encima de la plaza.
				continue
			puntos, ids = self.puntos_de(nodos)
			for trozo, marcas in formas.recortar_linea(puntos, ids, self.caja):
				if geo.longitud_linea(trozo) < 2.0:
					continue
				(rodados if es_rodada else peatonales).append(_Tramo(trozo, marcas, etiquetas, [identificador]))
		return rodados, peatonales

	def calles(self) -> list[_Tramo]:
		"""Vías con coches: la vía, su calzada, los cruces y las aceras. Devuelve los tramos peatonales."""
		rodados, peatonales = self._tramos()
		grado: Counter[int] = Counter()
		for tramo in rodados + peatonales:
			for posicion, nodo in enumerate(tramo.ids):
				if nodo is not None:
					grado[nodo] += 1 if posicion in (0, len(tramo.ids) - 1) else 2
		self._grado = grado
		for tramo in peatonales:
			if tramo.etiquetas.get("footway") == "sidewalk":
				self.aceras_dibujadas.append(geo.punto_en_linea(tramo.puntos, geo.longitud_linea(tramo.puntos) / 2.0)[0])
		sin_nombre = 0
		estimadas: Counter[str] = Counter()
		cadenas = encadenar(rodados, grado)
		for numero_cadena, cadena in enumerate(cadenas, start=1):
			self._avance(numero_cadena, len(cadenas))
			if self._calle(cadena, estimadas):
				self.cadenas.append(cadena)
				sin_nombre += 0 if cadena.etiquetas.get("name") else 1
		if self.cadenas:
			self.informe.contar("vias", len(self.cadenas))
			self.informe.anotar_importado(
				_("{vias} con su calzada, su sentido y sus carriles.").format(
					vias=frase_cuenta(len(self.cadenas), "{n} calle", "{n} calles")
				)
			)
			self.informe.anotar_deducido(
				_(
					"El nivel de tráfico de cada calle es una estimación por su tipo de vía (principal, de barrio, residencial…): el mapa no mide el tráfico."
				)
			)
			self.informe.anotar_revisar(_("Escuche el tráfico real de cada calle y ajuste su nivel y su velocidad."))
		if sin_nombre:
			self.informe.anotar_falta(
				_n("{n} calle no tiene nombre en el mapa.", "{n} calles no tienen nombre en el mapa.", sin_nombre).format(n=sin_nombre)
			)
		for clave, frase_uno, frase_varios in (
			(
				"ancho",
				N_("{n} calle sin anchura en el mapa: se ha estimado por sus carriles o su tipo."),
				N_("{n} calles sin anchura en el mapa: se ha estimado por sus carriles o su tipo."),
			),
			(
				"carriles",
				N_("{n} calle sin número de carriles en el mapa: se ha estimado."),
				N_("{n} calles sin número de carriles en el mapa: se ha estimado."),
			),
			(
				"velocidad",
				N_("{n} calle sin velocidad máxima en el mapa: se ha puesto la habitual de su tipo."),
				N_("{n} calles sin velocidad máxima en el mapa: se ha puesto la habitual de su tipo."),
			),
			(
				"estrechada",
				N_("{n} calzada se ha estrechado porque las fachadas no dejaban sitio."),
				N_("{n} calzadas se han estrechado porque las fachadas no dejaban sitio."),
			),
			(
				"simplificada",
				N_("{n} calle con curvas muy cerradas se ha dibujado simplificada."),
				N_("{n} calles con curvas muy cerradas se han dibujado simplificadas."),
			),
		):
			if estimadas[clave]:
				self.informe.anotar_deducido(_n(frase_uno, frase_varios, estimadas[clave]).format(n=estimadas[clave]))
		self._entrar("cruces")
		self._cruces()
		if self.op.aceras:
			self._entrar("aceras")
			self._aceras()
		return peatonales

	def _calle(self, cadena: _Tramo, estimadas: Counter[str]) -> bool:
		"""Convierte una cadena en vía y calzada. False si no se pudo dibujar."""
		etiquetas = cadena.etiquetas
		clase = etiquetas["highway"]
		base = clase.removesuffix("_link")
		nombre_tipo, ancho_tipo, trafico, velocidad_tipo, carriles_tipo = et.VIAS_RODADAS[base]
		cadena.cerrada = (cadena.ids[0] is not None and cadena.ids[0] == cadena.ids[-1]) or geo.distancia(
			cadena.puntos[0], cadena.puntos[-1]
		) < 0.1
		rotonda = etiquetas.get("junction") in ("roundabout", "circular")
		cadena.nombre = etiquetas.get("name") or self.nombre_unico(_("{tipo} sin nombre").format(tipo=_(nombre_tipo).capitalize()))
		partes = [_(nombre_tipo).capitalize() + "."]
		sentido = "doble"
		unico = etiquetas.get("oneway", "")
		if unico in ("yes", "true", "1") or rotonda:
			sentido = "ida"
		elif unico in ("-1", "reverse"):
			sentido = "vuelta"
		carriles_mapa = numero(etiquetas.get("lanes"))
		if carriles_mapa and carriles_mapa >= 1:
			carriles = round(carriles_mapa)
			partes.append(_n("{n} carril, según el mapa.", "{n} carriles, según el mapa.", carriles).format(n=carriles))
		else:
			carriles = 1 if sentido != "doble" else carriles_tipo
			estimadas["carriles"] += 1
			partes.append(
				_n("{n} carril (estimado: el mapa no lo dice).", "{n} carriles (estimado: el mapa no lo dice).", carriles).format(
					n=carriles
				)
			)
		ancho_mapa = numero(etiquetas.get("width")) or numero(etiquetas.get("est_width"))
		if ancho_mapa and ancho_mapa >= 1.0:
			ancho = ancho_mapa
		else:
			estimadas["ancho"] += 1
			if carriles_mapa:
				ancho = max(3.0, carriles * et.ANCHO_CARRIL)
			elif clase.endswith("_link"):
				ancho = 5.0
			else:
				ancho = ancho_tipo if sentido == "doble" else max(3.5, ancho_tipo * 0.65)
		velocidad_mapa = numero(etiquetas.get("maxspeed"))
		if velocidad_mapa and velocidad_mapa > 0:
			velocidad = velocidad_mapa * (1.609 if "mph" in etiquetas.get("maxspeed", "") else 1.0)
			partes.append(_("Velocidad máxima: {v} kilómetros por hora, según el mapa.").format(v=round(velocidad)))
		else:
			velocidad = velocidad_tipo
			estimadas["velocidad"] += 1
			partes.append(
				_("Velocidad máxima: el mapa no lo dice; se ha puesto {v}, la habitual en este tipo de vía.").format(v=round(velocidad))
			)
		if etiquetas.get("access") in ("no", "private") or etiquetas.get("motor_vehicle") in ("no", "private"):
			trafico = 0
			partes.append(_("Cerrada al tráfico general, según el mapa."))
		if base == "living_street":
			partes.append(_("Coches y peatones comparten el espacio, casi sin bordillos."))
		eje = formas.simplificar_linea(formas.sin_puntos_repetidos(cadena.puntos, 0.05), 0.15)
		if cadena.cerrada:
			eje = formas.sin_puntos_repetidos(cadena.puntos, 0.05)
		if len(eje) < 2:
			return False
		mitad = ancho / 2.0
		if not (ancho_mapa and ancho_mapa >= 1.0) and not cadena.cerrada:
			izquierda, derecha = self._fachadas_de(eje)
			cercana = min(izquierda, derecha)
			if cercana - mitad < ACERA_MINIMA:
				nueva = max(MEDIA_CALZADA_MINIMA, cercana - 1.5)
				if nueva < mitad:
					mitad = nueva
					estimadas["estrechada"] += 1
		cadena.eje = eje
		cadena.mitad = mitad
		via = Via(
			nombre=cadena.nombre,
			descripcion=" ".join(partes),
			eje=list(eje),
			ancho=round(mitad * 2.0, 2),
			carriles=max(1, carriles),
			sentido=sentido,
			trafico=trafico,
			velocidad_kmh=float(round(velocidad)),
		)
		via.id = self.entorno.id_para(via)
		suelo = self.suelo_de(etiquetas, "asfalto")
		referencia_osm = [f"way/{identificador}" for identificador in cadena.osm]
		if cadena.cerrada:
			anillo = formas.limpiar_poligono(eje)
			centro = geo.centroide(anillo) if len(anillo) >= 3 else eje[0]
			exterior = [geo.punto_a_distancia(p, geo.rumbo_entre(centro, p), mitad) for p in anillo]
			nombre = _("Rotonda de {calle}").format(calle=etiquetas["name"]) if etiquetas.get("name") else self.nombre_unico(_("Rotonda"))
			calzada = self.espacio(
				nombre if rotonda else _("Calzada de {calle}").format(calle=cadena.nombre),
				exterior,
				tipo="calzada",
				suelo=suelo,
				descripcion=_("Se circula alrededor en un solo sentido.") if rotonda else "",
				datos={
					"via": via.id,
					"cruce": rotonda,
					"vias": [via.id],
					"centro": [round(centro[0], 2), round(centro[1], 2)],
					"forma": "rotonda" if rotonda else "",
					"osm": referencia_osm,
				},
			)
			if rotonda:
				self.informe.anotar_revisar(
					_(
						"En las rotondas se ha importado el círculo entero como calzada: la isleta central y los pasos de alrededor hay que revisarlos in situ."
					)
				)
		else:
			contorno, simplificada = formas.franja_tolerante(eje, -mitad, mitad)
			if simplificada:
				estimadas["simplificada"] += 1
			calzada = None
			if contorno is not None:
				calzada = self.espacio(
					_("Calzada de {calle}").format(calle=cadena.nombre),
					contorno,
					tipo="calzada",
					suelo=suelo,
					datos={"via": via.id, "osm": referencia_osm},
				)
			else:
				self.informe.anotar_aviso(
					_("La calle «{nombre}» no se ha podido dibujar: su trazado en el mapa es demasiado enrevesado.").format(
						nombre=cadena.nombre
					)
				)
		if calzada is None:
			return False
		self.planta.vias.append(via)
		cadena.via = via
		return True

	def _fachadas_de(self, eje: Sequence[Punto]) -> tuple[float, float]:
		"""Distancia del eje a la línea de fachadas a cada lado (izquierda, derecha); infinito si no hay.

		Se lanzan rayos perpendiculares cada pocos metros. Para que un
		edificio suelto o mal dibujado no mande, se toma un valor bajo pero
		no el mínimo, y solo cuenta si al menos un tercio de los rayos toca.
		"""
		if not self.fachadas:
			return math.inf, math.inf
		largo = geo.longitud_linea(eje)
		muestras = [largo / 2.0] if largo < 12.0 else [3.0 + 6.0 * i for i in range(int((largo - 6.0) / 6.0) + 1)]
		resultados: list[float] = []
		for signo in (-1.0, 1.0):
			toques: list[float] = []
			for distancia in muestras:
				punto, rumbo = geo.punto_en_linea(eje, distancia)
				fin = geo.punto_a_distancia(punto, rumbo + signo * 90.0, ALCANCE_FACHADA)
				caja_rayo = geo.caja((punto, fin))
				mejor = math.inf
				for a, b, caja_lado in self._indice_fachadas.cerca(self.fachadas, caja_rayo):
					if not geo.cajas_se_tocan(caja_rayo, caja_lado):
						continue
					corte = geo.corte_segmentos(punto, fin, a, b)
					if corte is not None:
						mejor = min(mejor, geo.distancia(punto, corte))
				if mejor < math.inf:
					toques.append(mejor)
			if len(toques) * 3 < len(muestras) or not toques:
				resultados.append(math.inf)
				continue
			toques.sort()
			resultados.append(toques[len(toques) // 5] if len(toques) >= 5 else toques[0])
		return resultados[0], resultados[1]

	def _cruces(self) -> None:
		"""Localiza los nudos donde se juntan calles y crea el espacio de cada cruce con su forma."""
		apariciones = self.apariciones
		for cadena in self.cadenas:
			ultimo = len(cadena.ids) - 1
			for posicion, nodo in enumerate(cadena.ids):
				if nodo is None or (cadena.cerrada and posicion == ultimo):
					continue
				apariciones.setdefault(nodo, []).append((cadena, posicion))
		creados = 0
		for nodo, lista in apariciones.items():
			ramas: list[tuple[_Tramo, float, bool]] = []
			for cadena, posicion in lista:
				punto = cadena.puntos[posicion]
				ultimo = len(cadena.puntos) - 1
				extremo = not cadena.cerrada and posicion in (0, ultimo)
				anterior = cadena.puntos[posicion - 1] if posicion > 0 else (cadena.puntos[-2] if cadena.cerrada else None)
				siguiente = cadena.puntos[posicion + 1] if posicion < ultimo else None
				for vecino in (anterior, siguiente):
					if vecino is not None and geo.distancia(punto, vecino) > 0.01:
						ramas.append((cadena, geo.rumbo_entre(punto, vecino), extremo))
			if len(lista) < 2:
				continue
			self.ramas[nodo] = ramas
			if len(ramas) < 3 or any(cadena.cerrada for cadena, _rumbo, _extremo in ramas):
				continue
			centro = self.xy[nodo]
			if not self.dentro(centro):
				continue
			rumbos = [rumbo for _cadena, rumbo, _extremo in ramas]
			forma = forma_de_cruce(rumbos)
			nombres: list[str] = []
			for cadena, _rumbo, _extremo in ramas:
				if cadena.nombre not in nombres:
					nombres.append(cadena.nombre)
			forma_dicha = _(et.FORMAS_CRUCE[forma])
			if len(nombres) >= 2:
				nombre = _("{forma} de {a} con {b}").format(forma=forma_dicha, a=nombres[0], b=_(" y ").join(nombres[1:]))
			else:
				nombre = _("{forma} en {a}").format(forma=forma_dicha, a=nombres[0])
			salidas = sorted(((rumbo, cadena.nombre) for cadena, rumbo, _extremo in ramas), key=lambda par: par[0])
			partes = [
				_("Salen {n} ramas: {lista}.").format(
					n=len(ramas),
					lista="; ".join(
						_("al {punto}, {calle}").format(punto=geo.punto_cardinal(rumbo), calle=calle) for rumbo, calle in salidas
					),
				)
			]
			etiquetas = self.etiquetas_nodo.get(nodo, {})
			datos: dict[str, Any] = {
				"cruce": True,
				"vias": [cadena.via.id for cadena in dict.fromkeys(c for c, _r, _e in ramas) if cadena.via is not None],
				"centro": [round(centro[0], 3), round(centro[1], 3)],
				"forma": forma,
				"ramas": len(ramas),
				"rumbos": [round(rumbo, 1) for rumbo, _calle in salidas],
				"osm": f"node/{nodo}",
			}
			if etiquetas.get("highway") == "traffic_signals":
				datos["semaforo_vehiculos"] = True
				partes.append(_("Los coches tienen semáforo, según el mapa."))
			radio = max(cadena.mitad for cadena, _rumbo, _extremo in ramas) * 1.1 + 0.3
			if (
				self.espacio(
					self.nombre_unico(nombre),
					geo.circulo(centro[0], centro[1], radio, 8),
					tipo="calzada",
					descripcion=" ".join(partes),
					datos=datos,
				)
				is not None
			):
				creados += 1
		if creados:
			self.informe.contar("cruces", creados)
			self.informe.anotar_importado(
				_("{cruces} con su forma (en T, en cruz, en Y…).").format(cruces=frase_cuenta(creados, "{n} cruce", "{n} cruces"))
			)
			self.informe.anotar_deducido(
				_(
					"La superficie de cada cruce es aproximada (un octógono sobre el punto donde se juntan los ejes): el mapa no dibuja las esquinas."
				)
			)

	def _aceras_segun_mapa(self, etiquetas: dict[str, str]) -> dict[str, str]:
		"""Lo que el mapa dice de la acera de cada lado: «si», «no», «separada» o «desconocido»."""
		estado = {"izquierda": DESCONOCIDO, "derecha": DESCONOCIDO}
		general = etiquetas.get("sidewalk") or etiquetas.get("sidewalk:both") or ""
		if general in ("both", "yes"):
			estado = {"izquierda": SI, "derecha": SI}
		elif general == "left":
			estado = {"izquierda": SI, "derecha": NO}
		elif general == "right":
			estado = {"izquierda": NO, "derecha": SI}
		elif general in ("no", "none"):
			estado = {"izquierda": NO, "derecha": NO}
		elif general == "separate":
			estado = {"izquierda": "separada", "derecha": "separada"}
		for lado, clave in (("izquierda", "sidewalk:left"), ("derecha", "sidewalk:right")):
			valor = etiquetas.get(clave)
			if valor in ("yes", "both"):
				estado[lado] = SI
			elif valor in ("no", "none"):
				estado[lado] = NO
			elif valor == "separate":
				estado[lado] = "separada"
		return estado

	def _acera_dibujada_cerca(self, cadena: _Tramo) -> bool:
		"""True si junto a esta calle el mapa ya dibuja la acera como vía aparte."""
		alcance = cadena.mitad + 6.0
		for punto in self.aceras_dibujadas:
			if geo.proyeccion_sobre_linea(punto, cadena.eje)[1] <= alcance:
				return True
		return False

	def _cortes(self, cadena: _Tramo) -> dict[str, list[tuple[float, float]]]:
		"""Tramos del eje (en metros) donde otra calle sale por cada lado: ahí no hay acera."""
		cortes: dict[str, list[tuple[float, float]]] = {"izquierda": [], "derecha": []}
		ultimo = len(cadena.ids) - 1
		for posicion, nodo in enumerate(cadena.ids):
			if nodo is None or nodo not in self.ramas:
				continue
			distancia = formas.distancia_en_linea(cadena.eje, cadena.puntos[posicion])
			rumbo_propio = formas.rumbo_en_linea(cadena.eje, distancia)
			en_extremo = posicion in (0, ultimo)
			for otra, rumbo, _extremo in self.ramas[nodo]:
				if otra is cadena:
					continue
				giro = geo.diferencia_rumbos(rumbo_propio, rumbo)
				seno = abs(math.sin(math.radians(giro)))
				if otra.cerrada:
					medio = otra.mitad
				elif seno < 0.34:
					# Casi en línea: es la misma calle que sigue con otro nombre, no una bocacalle.
					continue
				else:
					medio = otra.mitad / max(seno, 0.5)
				intervalo = (distancia - medio, distancia + medio)
				if en_extremo or otra.cerrada:
					cortes["izquierda"].append(intervalo)
					cortes["derecha"].append(intervalo)
				else:
					cortes["derecha" if giro > 0 else "izquierda"].append(intervalo)
		return cortes

	def _aceras(self) -> None:
		"""Materializa las aceras de cada calle: las que dice el mapa y, si no dice nada, las deducidas."""
		del_mapa = 0
		deducidas: list[str] = []
		sin_dato: list[str] = []
		sin_acera: list[str] = []
		separadas = False
		for numero_cadena, cadena in enumerate(self.cadenas, start=1):
			self._avance(numero_cadena, len(self.cadenas))
			if cadena.cerrada or cadena.via is None:
				continue
			etiquetas = cadena.etiquetas
			base = etiquetas["highway"].removesuffix("_link")
			estados = self._aceras_segun_mapa(etiquetas)
			dibujada = self._acera_dibujada_cerca(cadena)
			fachadas = dict(zip(("izquierda", "derecha"), self._fachadas_de(cadena.eje), strict=True))
			cortes = self._cortes(cadena)
			largo = geo.longitud_linea(cadena.eje)
			for lado, signo in (("izquierda", -1.0), ("derecha", 1.0)):
				estado = estados[lado]
				if estado == NO:
					if cadena.nombre not in sin_acera:
						sin_acera.append(cadena.nombre)
					continue
				if estado == "separada" or (estado == DESCONOCIDO and dibujada):
					separadas = True
					continue
				origen = "mapa"
				if estado == DESCONOCIDO:
					puede = (
						self.op.deducir_aceras
						and base in et.VIAS_CON_ACERA_SUPUESTA
						and (bool(etiquetas.get("name")) or base != "unclassified")
					)
					if not puede:
						if cadena.nombre not in sin_dato:
							sin_dato.append(cadena.nombre)
						continue
					origen = "deducida"
				clave_lado = "left" if lado == "izquierda" else "right"
				ancho_mapa = (
					numero(etiquetas.get(f"sidewalk:{clave_lado}:width"))
					or numero(etiquetas.get("sidewalk:both:width"))
					or numero(etiquetas.get("sidewalk:width"))
				)
				libre = fachadas[lado] - cadena.mitad
				if ancho_mapa and ancho_mapa >= 0.5:
					ancho = ancho_mapa
				elif libre < 0.6:
					self.informe.anotar_aviso(
						_("En «{calle}» no cabe acera en el lado {lado}: la fachada queda a {metros} metros del eje de la calle.").format(
							calle=cadena.nombre, lado=_(lado), metros=_m(fachadas[lado])
						)
					)
					continue
				elif libre <= ACERA_HASTA_FACHADA:
					ancho = libre
				else:
					ancho = self.op.ancho_acera
				huecos = sorted(cortes[lado])
				piezas: list[tuple[float, float]] = []
				cursor = 0.0
				for inicio, fin in huecos:
					if inicio - cursor >= TRAMO_MINIMO_ACERA:
						piezas.append((cursor, inicio))
					cursor = max(cursor, fin)
				if largo - cursor >= TRAMO_MINIMO_ACERA:
					piezas.append((cursor, largo))
				suelo = self.suelo_de(etiquetas, "acera", "sidewalk:surface")
				creadas = 0
				for numero_pieza, (inicio, fin) in enumerate(piezas, start=1):
					tramo = formas.tramo_de_linea(cadena.eje, inicio, fin)
					if len(tramo) < 2:
						continue
					contorno, _simplificada = formas.franja_tolerante(tramo, signo * cadena.mitad, signo * (cadena.mitad + ancho))
					if contorno is None:
						continue
					cardinal = geo.lado_cardinal(geo.rumbo_entre(tramo[0], tramo[-1]) + signo * 90.0)
					nombre = _("Acera {lado} de {calle}").format(lado=_(cardinal), calle=cadena.nombre)
					if len(piezas) > 1:
						nombre = _("{acera}, tramo {n}").format(acera=nombre, n=numero_pieza)
					if origen == "deducida":
						descripcion = _(
							"Acera deducida: el mapa solo da el eje de la calle y no dice si hay acera. Compruebe in situ que existe y cuánto mide."
						)
					elif ancho_mapa:
						descripcion = _("Acera que figura en el mapa, con su anchura.")
					else:
						descripcion = _(
							"Acera que figura en el mapa. Su anchura no: se ha calculado hasta la fachada o se ha puesto la habitual."
						)
					datos = {
						"via": cadena.via.id,
						"lado": lado,
						"ancho": round(ancho, 2),
						"tramo": numero_pieza,
						"origen": origen,
						"ancho_segun_mapa": bool(ancho_mapa),
						"osm": [f"way/{identificador}" for identificador in cadena.osm],
					}
					if self.espacio(nombre, contorno, tipo="acera", suelo=suelo, descripcion=descripcion, datos=datos) is not None:
						creadas += 1
				if creadas and origen == "mapa":
					del_mapa += creadas
				elif creadas and cadena.nombre not in deducidas:
					deducidas.append(cadena.nombre)
		self.informe.contar("aceras_mapa", del_mapa)
		self.informe.contar("calles_con_aceras_deducidas", len(deducidas))
		if del_mapa:
			self.informe.anotar_importado(
				_("{aceras} que figuran en el mapa (etiqueta «sidewalk»).").format(
					aceras=frase_cuenta(del_mapa, "{n} tramo de acera", "{n} tramos de acera")
				)
			)
			self.informe.anotar_deducido(
				_(
					"La anchura de las aceras casi nunca está en el mapa: donde falta se ha calculado hasta la fachada, o se ha puesto la habitual."
				)
			)
		if deducidas:
			self.informe.anotar_deducido(
				_("Aceras DEDUCIDAS (el mapa solo da el eje de la calle) en: {calles}. Compruebe in situ que existen.").format(
					calles=", ".join(deducidas)
				)
			)
		if sin_dato:
			self.informe.anotar_falta(_("El mapa no dice si hay aceras en: {calles}. No se han creado.").format(calles=", ".join(sin_dato)))
		if sin_acera:
			self.informe.anotar_importado(_("Sin acera en algún lado, según el mapa: {calles}.").format(calles=", ".join(sin_acera)))
		if separadas:
			self.informe.anotar_importado(
				_("Donde el mapa dibuja la acera como una vía aparte, se ha usado ese dibujo en lugar de calcularla.")
			)
		if del_mapa or deducidas:
			self.informe.anotar_revisar(_("Recorra las aceras: anchura real, vados, obstáculos y si son continuas en las esquinas."))

	# ── Caminos peatonales, aceras dibujadas y escaleras ──

	def caminos(self, peatonales: list[_Tramo]) -> None:
		"""Senderos, calles peatonales, aceras dibujadas como vía, escaleras y rampas."""
		cuenta: Counter[str] = Counter()
		escaleras_sin_peldanos = 0
		cadenas = encadenar(peatonales, self._grado)
		for numero_cadena, cadena in enumerate(cadenas, start=1):
			self._avance(numero_cadena, len(cadenas))
			etiquetas = cadena.etiquetas
			clase = etiquetas["highway"].removesuffix("_link")
			if etiquetas.get("footway") == "crossing" or etiquetas.get("path") == "crossing" or etiquetas.get("cycleway") == "crossing":
				self.vias_de_paso.append(cadena)
				continue
			nombre_tipo, ancho_tipo, tipo, suelo_tipo = et.VIAS_PEATONALES[clase]
			puntos = formas.sin_puntos_repetidos(cadena.puntos, 0.05)
			if len(puntos) >= 3 and geo.distancia(puntos[0], puntos[-1]) < 0.1:
				puntos = puntos[:-1]
			eje = formas.simplificar_linea(puntos, 0.1)
			ancho = numero(etiquetas.get("width")) or ancho_tipo
			ancho = max(0.6, min(ancho, 12.0))
			contorno, _simplificada = formas.franja_tolerante(eje, -ancho / 2.0, ancho / 2.0)
			if contorno is None:
				self.informe.anotar_aviso(_("Un camino peatonal ({osm}) no se ha podido dibujar.").format(osm=f"way/{cadena.osm[0]}"))
				continue
			datos: dict[str, Any] = {
				"osm": [f"way/{identificador}" for identificador in cadena.osm],
				"ancho": round(ancho, 2),
				"ancho_segun_mapa": "width" in etiquetas,
			}
			partes: list[str] = []
			nombre = etiquetas.get("name", "")
			suelo = self.suelo_de(etiquetas, suelo_tipo)
			rumbo = geo.rumbo_entre(eje[0], eje[-1])
			if clase == "steps":
				self._datos_escalera(datos, etiquetas, rumbo)
				nombre = nombre or self.nombre_unico(_("Escaleras"))
				escaleras_sin_peldanos += 0 if datos["peldanos"] else 1
			elif etiquetas.get("footway") == "sidewalk":
				tipo = "acera"
				suelo = self.suelo_de(etiquetas, "acera")
				nombre = nombre or self._nombre_de_acera(cadena, eje, datos)
				datos["origen"] = "mapa"
				partes.append(_("Acera dibujada en el mapa como vía aparte."))
			else:
				rampa = (
					etiquetas.get("ramp") == "yes"
					or etiquetas.get("ramp:wheelchair") == "yes"
					or self._es_pendiente(etiquetas.get("incline"))
				)
				if rampa:
					self._datos_escalera(datos, etiquetas, rumbo)
					datos["rampa"] = True
					datos.pop("peldanos", None)
					datos["segun_mapa"].pop("peldanos", None)
					nombre = nombre or self.nombre_unico(_("Rampa"))
				else:
					nombre = nombre or self.nombre_unico(_(nombre_tipo))
				if clase == "cycleway":
					datos["bicis"] = True
					partes.append(_("Por aquí pasan bicicletas."))
			if "segun_mapa" in datos:
				escalon = Espacio(datos=datos)
				partes.extend(ficha_escalera(escalon))
				datos["descripcion_automatica"] = True
			if "surface" not in etiquetas and clase != "steps":
				partes.append(_("Suelo: el mapa no lo dice; se ha puesto el habitual."))
			if (
				self.espacio(
					nombre,
					contorno,
					tipo=tipo,
					cerrado=False,
					suelo=suelo,
					acustica="calle" if tipo in ("escalera", "acera") else None,
					descripcion=" ".join(partes),
					datos=datos,
				)
				is not None
			):
				cuenta["escaleras" if clase == "steps" else ("aceras_dibujadas" if tipo == "acera" else "caminos")] += 1
		for clave, valor in cuenta.items():
			self.informe.contar(clave, valor)
		if cuenta["caminos"]:
			self.informe.anotar_importado(
				_("{n} caminos peatonales, senderos o calles peatonales.").format(n=cuenta["caminos"])
				if cuenta["caminos"] != 1
				else _("1 camino peatonal.")
			)
		if cuenta["aceras_dibujadas"]:
			self.informe.anotar_importado(
				_("{aceras} dibujadas en el mapa como vías aparte.").format(
					aceras=frase_cuenta(cuenta["aceras_dibujadas"], "{n} acera", "{n} aceras")
				)
			)
		if cuenta["escaleras"]:
			self.informe.anotar_importado(
				_("{escaleras} exteriores.").format(escaleras=frase_cuenta(cuenta["escaleras"], "{n} escalera", "{n} escaleras"))
			)
			self.informe.anotar_revisar(
				_(
					"Las escaleras exteriores se importan como una zona de tipo escalera dentro de la calle, no como un conector entre plantas: cuente los peldaños y compruebe el pasamanos."
				)
			)
		if escaleras_sin_peldanos:
			self.informe.anotar_falta(
				_n(
					"{n} escalera no dice cuántos peldaños tiene.",
					"{n} escaleras no dicen cuántos peldaños tienen.",
					escaleras_sin_peldanos,
				).format(n=escaleras_sin_peldanos)
			)

	@staticmethod
	def _es_pendiente(valor: str | None) -> bool:
		"""True si ``incline`` describe una rampa de verdad (no un 0 %)."""
		if not valor:
			return False
		if valor in ("up", "down"):
			return True
		pendiente = numero(valor)
		return pendiente is not None and abs(pendiente) >= 4.0

	@staticmethod
	def _datos_escalera(datos: dict[str, Any], etiquetas: dict[str, str], rumbo: float) -> None:
		"""Rellena peldaños, pasamanos y sentido de subida, cada uno con lo que el mapa dice o no dice."""
		peldanos = numero(etiquetas.get("step_count"))
		datos["peldanos"] = round(peldanos) if peldanos and peldanos >= 1 else None
		izquierda = etiquetas.get("handrail:left")
		derecha = etiquetas.get("handrail:right")
		general = etiquetas.get("handrail")
		pasamanos = DESCONOCIDO
		if izquierda == "yes" and derecha == "yes" or general == "both":
			pasamanos = "ambos"
		elif izquierda == "yes" or general == "left":
			pasamanos = "izquierda"
		elif derecha == "yes" or general == "right":
			pasamanos = "derecha"
		elif general == "no" or (izquierda == "no" and derecha == "no"):
			pasamanos = "ninguno"
		datos["pasamanos"] = pasamanos if pasamanos != DESCONOCIDO else ""
		if general == "yes" and pasamanos == DESCONOCIDO:
			datos["pasamanos_lado_desconocido"] = True
		inclinacion = etiquetas.get("incline", "")
		pendiente = numero(inclinacion)
		sube: float | None = None
		if inclinacion == "up" or (pendiente is not None and pendiente > 0):
			sube = rumbo
		elif inclinacion == "down" or (pendiente is not None and pendiente < 0):
			sube = geo.normalizar_rumbo(rumbo + 180.0)
		datos["sube_hacia"] = round(sube, 1) if sube is not None else None
		if pendiente is not None and "%" in inclinacion:
			datos["pendiente_pct"] = pendiente
		datos["segun_mapa"] = {
			"peldanos": SI if datos["peldanos"] else DESCONOCIDO,
			"pasamanos": SI if pasamanos != DESCONOCIDO else (SI if general == "yes" else DESCONOCIDO),
			"sube_hacia": SI if sube is not None else DESCONOCIDO,
			"tactil": et.tres_estados(etiquetas.get("tactile_paving"), ("yes", "contrasted", "partial"), ("no",)),
		}

	def _nombre_de_acera(self, cadena: _Tramo, eje: Sequence[Punto], datos: dict[str, Any]) -> str:
		"""Nombre de una acera dibujada: el de la calle que tiene al lado, con el lado en que queda."""
		medio = geo.punto_en_linea(eje, geo.longitud_linea(eje) / 2.0)[0]
		mejor: tuple[float, _Tramo, Punto] | None = None
		for calle in self.cadenas:
			if calle.cerrada:
				continue
			cercano, distancia, _indice = geo.proyeccion_sobre_linea(medio, calle.eje)
			if distancia <= calle.mitad + 12.0 and (mejor is None or distancia < mejor[0]):
				mejor = (distancia, calle, cercano)
		if mejor is None or mejor[1].via is None:
			return self.nombre_unico(_("Acera"))
		_distancia, calle, cercano = mejor
		datos["via"] = calle.via.id
		rumbo_calle = formas.rumbo_en_linea(calle.eje, formas.distancia_en_linea(calle.eje, cercano))
		datos["lado"] = "derecha" if geo.diferencia_rumbos(rumbo_calle, geo.rumbo_entre(cercano, medio)) > 0 else "izquierda"
		cardinal = geo.lado_cardinal(geo.rumbo_entre(cercano, medio))
		return self.nombre_unico(_("Acera {lado} de {calle}").format(lado=_(cardinal), calle=calle.nombre))

	# ── Pasos de peatones ──

	def pasos(self) -> None:
		"""Pasos de peatones con su ficha, distinguiendo «no tiene» de «el mapa no lo dice»."""
		candidatos: dict[int, dict[str, str]] = {}
		for nodo, etiquetas in self.etiquetas_nodo.items():
			cruce = etiquetas.get("crossing", "")
			if cruce == "no":
				continue
			if etiquetas.get("highway") == "crossing" or (cruce and etiquetas.get("highway") in (None, "traffic_signals")):
				candidatos[nodo] = dict(etiquetas)
		for via in self.vias_de_paso:
			for nodo in via.ids:
				if nodo is None or nodo not in self.apariciones:
					continue
				unidas = dict(via.etiquetas)
				unidas.update(candidatos.get(nodo, {}))
				candidatos[nodo] = unidas
		creados = 0
		con_huecos: list[str] = []
		fuera_de_calzada = 0
		for numero_paso, (nodo, etiquetas) in enumerate(candidatos.items(), start=1):
			self._avance(numero_paso, len(candidatos))
			punto = self.xy.get(nodo)
			if punto is None or not self.dentro(punto):
				continue
			lugares = self.apariciones.get(nodo)
			if not lugares:
				fuera_de_calzada += 1
				continue
			cadena = lugares[0][0]
			if cadena.via is None:
				continue
			segun = self._segun_mapa_paso(etiquetas)
			semaforo = segun["semaforo"] == SI
			if semaforo:
				base = _("Paso con semáforo de {calle}")
			elif segun["semaforo"] == NO:
				base = _("Paso sin semáforo de {calle}")
			else:
				base = _("Paso de peatones de {calle}")
			try:
				paso = ed.crear_paso_peatones(
					self.entorno,
					self.planta,
					cadena.via,
					punto,
					semaforo=semaforo,
					sonoro=semaforo and segun["sonoro"] == SI,
					pulsador=semaforo and segun["pulsador"] == SI,
					isleta=segun["isleta"] == SI,
					ancho=min(numero(etiquetas.get("width")) or 4.0, 8.0),
					nombre=self.nombre_unico(base.format(calle=cadena.nombre)),
					tactil=segun["tactil"] == SI,
				)
			except ed.ErrorEdicion as error:
				log.info("No se pudo crear el paso del nodo %s: %s", nodo, error)
				self.informe.anotar_aviso(_("Un paso de peatones de «{calle}» no se ha podido dibujar.").format(calle=cadena.nombre))
				continue
			paso.datos["segun_mapa"] = segun
			paso.datos["vibracion"] = semaforo and segun["vibracion"] == SI
			paso.datos["tactil"] = segun["tactil"] == SI
			paso.datos["bordillo"] = etiquetas.get("kerb", "") if etiquetas.get("kerb") in et.BORDILLOS else ""
			marcas = etiquetas.get("crossing:markings") or ("zebra" if etiquetas.get("crossing") == "zebra" else "")
			if marcas:
				paso.datos["marcas"] = marcas
			paso.datos["osm"] = f"node/{nodo}"
			if semaforo:
				paso.datos["ciclo_estimado"] = True
				self.informe.anotar_deducido(
					_(
						"Los tiempos de los semáforos (verde, intermitente y rojo) son los de serie del programa: el mapa no los dice. Mídalos in situ."
					)
				)
			lineas = ficha_paso(paso)
			if marcas in et.MARCAS_PASO:
				lineas.append(_("Marcas en el suelo: {marcas}.").format(marcas=_(et.MARCAS_PASO[marcas])))
			paso.descripcion = " ".join(lineas)
			paso.datos["descripcion_automatica"] = True
			faltan = atributos_que_faltan(paso.datos, _ATRIBUTOS_PASO)
			if faltan:
				con_huecos.append(_("{paso}: {lista}").format(paso=paso.nombre, lista=", ".join(_(nombre) for nombre in faltan)))
			creados += 1
		if creados:
			self.informe.contar("pasos", creados)
			self.informe.anotar_importado(
				_("{pasos} con su ficha (semáforo, señal sonora, vibración, pulsador, isleta, pavimento táctil y bordillo).").format(
					pasos=frase_cuenta(creados, "{n} paso de peatones", "{n} pasos de peatones")
				)
			)
			self.informe.anotar_deducido(_("La anchura de los pasos (4 metros) es la habitual: el mapa casi nunca la dice."))
			self.informe.anotar_revisar(
				_(
					"En cada paso: compruebe si el semáforo suena, cómo se activa, dónde está el poste, el bordillo y el pavimento táctil, y hacia dónde se cruza."
				)
			)
		for frase in con_huecos:
			self.informe.anotar_falta(_("El mapa no dice, en {detalle}.").format(detalle=frase))
		if fuera_de_calzada:
			self.informe.anotar_aviso(
				_n(
					"{n} paso de peatones del mapa no está sobre ninguna calzada importada y se ha dejado fuera.",
					"{n} pasos de peatones del mapa no están sobre ninguna calzada importada y se han dejado fuera.",
					fuera_de_calzada,
				).format(n=fuera_de_calzada)
			)

	@staticmethod
	def _segun_mapa_paso(etiquetas: dict[str, str]) -> dict[str, str]:
		"""Los atributos de un paso con tres estados cada uno: sí, no o el mapa no lo dice."""
		cruce = etiquetas.get("crossing", "")
		senales = etiquetas.get("crossing:signals", "")
		if cruce == "traffic_signals" or senales == "yes":
			semaforo = SI
		elif cruce in ("uncontrolled", "unmarked", "marked", "zebra") or senales == "no":
			semaforo = NO
		else:
			semaforo = DESCONOCIDO
		sonoro = et.tres_estados(etiquetas.get("traffic_signals:sound"), ("yes", "walk", "locate"), ("no",))
		vibracion = et.tres_estados(etiquetas.get("traffic_signals:vibration"))
		pulsador = et.tres_estados(etiquetas.get("button_operated"))
		if SI in (sonoro, vibracion, pulsador):
			# Un semáforo que suena o tiene pulsador es un semáforo, aunque falte la etiqueta principal.
			semaforo = SI
		if semaforo == NO:
			sonoro = vibracion = pulsador = NO
		bordillo = SI if etiquetas.get("kerb") in et.BORDILLOS else DESCONOCIDO
		return {
			"semaforo": semaforo,
			"sonoro": sonoro,
			"vibracion": vibracion,
			"pulsador": pulsador,
			"isleta": et.tres_estados(etiquetas.get("crossing:island") or etiquetas.get("traffic_island")),
			"tactil": et.tres_estados(etiquetas.get("tactile_paving"), ("yes", "contrasted", "partial", "incorrect"), ("no",)),
			"bordillo": bordillo,
		}

	# ── Barreras y obstáculos ──

	def barreras(self) -> None:
		"""Muros, vallas y setos como paredes sueltas, con sus cancelas."""
		tramos = 0
		for identificador, (nodos, etiquetas) in self.vias_osm.items():
			clase = etiquetas.get("barrier", "")
			if clase not in et.BARRERAS_LINEA:
				continue
			comprobar_cancelacion(self.cancelado)
			nombre_tipo, material, altura_tipo, tapa_sonido = et.BARRERAS_LINEA[clase]
			altura = numero(etiquetas.get("height")) or altura_tipo
			nombre = etiquetas.get("name") or self.nombre_unico(_(nombre_tipo))
			puntos, ids = self.puntos_de(nodos)
			creadas = []
			for trozo, _marcas in formas.recortar_linea(puntos, ids, self.caja):
				linea = formas.simplificar_linea(formas.sin_puntos_repetidos(trozo, 0.05), 0.1)
				for a, b in zip(linea, linea[1:], strict=False):
					if geo.distancia(a, b) < 0.3:
						continue
					creadas.append(
						ed.anadir_pared(
							self.entorno,
							self.planta,
							a,
							b,
							nombre=nombre,
							grosor=0.3 if material in ("piedra", "hormigon") else 0.1,
							material=material,
							bloquea_sonido=tapa_sonido and altura >= 1.6,
							altura=max(0.2, min(altura, 12.0)),
							descripcion=_("Altura típica, no medida.") if "height" not in etiquetas else "",
						)
					)
			tramos += len(creadas)
			for nodo in ids:
				clase_nodo = self.etiquetas_nodo.get(nodo, {}).get("barrier", "")
				if clase_nodo in et.PUERTAS_DE_BARRERA and creadas:
					self._cancela(nodo, clase_nodo, creadas, f"way/{identificador}")
		if tramos:
			self.informe.contar("paredes", tramos)
			self.informe.anotar_importado(
				_("{n} tramos de muro, valla o seto, como paredes sueltas.").format(n=tramos)
				if tramos != 1
				else _("1 tramo de muro, valla o seto.")
			)
			self.informe.anotar_deducido(_("La altura de muros y vallas es la típica de cada clase cuando el mapa no la dice."))

	def _cancela(self, nodo: int, clase: str, paredes: list[Any], osm: str) -> None:
		"""Abre en la barrera el hueco de una cancela o un portillo del mapa."""
		punto = self.xy[nodo]
		pared = min(paredes, key=lambda p: geo.distancia_punto_segmento(punto, p.a, p.b))
		if geo.distancia_punto_segmento(punto, pared.a, pared.b) > 0.5:
			return
		nombre_tipo, ancho = et.PUERTAS_DE_BARRERA[clase]
		tramo = formas.tramo_centrado(pared.a, pared.b, punto, ancho)
		if tramo is None:
			return
		etiquetas = self.etiquetas_nodo[nodo]
		hueco = clase == "entrance"
		abertura = Abertura(
			nombre=etiquetas.get("name") or self.nombre_unico(_(nombre_tipo)),
			descripcion="" if hueco else _("El mapa no dice si suele estar abierta."),
			tipo="hueco" if hueco else "puerta",
			a=tramo[0],
			b=tramo[1],
			estado="abierta" if hueco else ("con_llave" if etiquetas.get("locked") == "yes" else "cerrada"),
			hoja="ninguna" if hueco else ("corredera" if clase == "sliding_gate" else "batiente"),
			material="metal",
		)
		abertura.id = self.entorno.id_para(abertura)
		self.planta.aberturas.append(abertura)
		self.nodos_usados.add(nodo)
		self.informe.contar("cancelas")
		log.debug("Cancela del nodo %s abierta en la barrera %s", nodo, osm)

	def _cabe(self, objeto: Objeto) -> bool:
		"""True si el objeto se puede dejar como obstáculo sin que la validación lo dé por error.

		Hace las mismas comprobaciones que ``colocacion.comprobar`` pero con
		filtros por cercanía: en una zona con cientos de árboles y farolas,
		la comprobación completa de cada uno tardaría demasiado.
		"""
		huella = self.catalogo.huella(objeto) if self.catalogo is not None else objeto.huella_caja()
		caja_huella = geo.caja(huella)
		espacio = self.espacio_en(objeto.x, objeto.y, incluir_macizos=False)
		if espacio is None:
			return False
		if espacio.cerrado and not geo.poligono_contiene(espacio.contorno, huella):
			return False
		for macizo in self._indice_espacios.cerca(self.planta.espacios, caja_huella):
			if macizo.macizo and geo.cajas_se_tocan(caja_huella, macizo.caja()) and geo.poligonos_se_solapan(huella, macizo.contorno):
				return False
		for pared in self.planta.paredes:
			if (
				pared.bloquea_paso
				and geo.cajas_se_tocan(caja_huella, geo.caja((pared.a, pared.b)))
				and geo.segmento_cruza_poligono(pared.a, pared.b, huella)
			):
				return False
		for otro in self.planta.objetos:
			if otro is objeto:
				continue
			huella_otro = otro.huella_caja()
			if geo.cajas_se_tocan(caja_huella, geo.caja(huella_otro)) and geo.poligonos_se_solapan(huella, huella_otro):
				return False
		return True

	def _obstaculo(self, clave: tuple[str, str], punto: Punto, etiquetas: dict[str, str], osm: str, nota: str = "") -> bool:
		"""Coloca un obstáculo del mapa; si no cabe, lo deja como referencia. True si quedó como objeto."""
		id_catalogo, nombre_tipo, ancho, fondo, alto = et.OBSTACULOS[clave]
		tipo = id_catalogo if "/" in id_catalogo else f"{et.COMPLEMENTO_CALLE}/{id_catalogo}"
		nombre = nombre_de_obstaculo(_(nombre_tipo), etiquetas.get("name", ""))
		descripcion = (nota + " " if nota else "") + _("Medidas típicas, no tomadas en el sitio.")
		if self.catalogo is not None and self.catalogo.objeto(tipo) is not None:
			objeto = self.catalogo.crear_objeto(tipo, punto[0], punto[1], 0.0)
			objeto.nombre = nombre
			objeto.descripcion = descripcion
			complemento = tipo.partition("/")[0]
			if complemento not in self.entorno.complementos:
				self.entorno.complementos.append(complemento)
		else:
			objeto = Objeto(
				nombre=nombre, descripcion=descripcion, tipo="caja", x=punto[0], y=punto[1], ancho=ancho, fondo=fondo, alto=alto
			)
			objeto.datos["tipo_previsto"] = tipo
		objeto.datos["osm"] = osm
		if not self._cabe(objeto):
			ed.anadir_referencia(
				self.entorno,
				self.planta,
				nombre,
				punto[0],
				punto[1],
				tipo="mobiliario",
				descripcion=_("Está en el mapa, pero no cabía como obstáculo en ese punto."),
			)
			return False
		objeto.id = self.entorno.id_para(objeto)
		self.planta.objetos.append(objeto)
		return True

	def obstaculos(self) -> None:
		"""Bolardos, farolas, árboles, bancos y demás mobiliario como objetos con medidas típicas."""
		colocados = 0
		como_referencia = 0
		cajas = False
		filas_de_bolardos = [
			identificador for identificador, (_nodos, etiquetas) in self.vias_osm.items() if etiquetas.get("barrier") == "bollard"
		]
		candidatos = [
			nodo
			for nodo, etiquetas in self.etiquetas_nodo.items()
			if any((clave, valor) in et.OBSTACULOS for clave, valor in etiquetas.items())
		]
		total = len(candidatos) + len(filas_de_bolardos)
		hechos = 0
		for nodo in candidatos:
			hechos += 1
			self._avance(hechos, total)
			etiquetas = self.etiquetas_nodo[nodo]
			punto = self.xy[nodo]
			if not self.dentro(punto) or nodo in self.nodos_usados:
				continue
			for clave, valor in etiquetas.items():
				if (clave, valor) not in et.OBSTACULOS:
					continue
				self.nodos_usados.add(nodo)
				if self._obstaculo((clave, valor), punto, etiquetas, f"node/{nodo}"):
					colocados += 1
					cajas = cajas or self.planta.objetos[-1].tipo == "caja"
				else:
					como_referencia += 1
				break
		for identificador in filas_de_bolardos:
			hechos += 1
			self._avance(hechos, total)
			nodos = self.vias_osm[identificador][0]
			for nodo in dict.fromkeys(nodos):
				punto = self.xy.get(nodo)
				if punto is None or not self.dentro(punto):
					continue
				if self._obstaculo(("barrier", "bollard"), punto, {}, f"way/{identificador}", _("De una fila de bolardos.")):
					colocados += 1
					cajas = cajas or self.planta.objetos[-1].tipo == "caja"
				else:
					como_referencia += 1
			self.informe.anotar_deducido(
				_("En las filas de bolardos se ha puesto uno en cada vértice del dibujo del mapa: cuente los reales.")
			)
		if colocados:
			self.informe.contar("obstaculos", colocados)
			self.informe.anotar_importado(
				_("{obstaculos} (bolardos, farolas, árboles, bancos, papeleras…).").format(
					obstaculos=frase_cuenta(colocados, "{n} obstáculo", "{n} obstáculos")
				)
			)
			self.informe.anotar_deducido(_("Las medidas de los obstáculos son las típicas de cada clase, no las reales."))
			self.informe.anotar_revisar(
				_("El mapa no recoge casi nunca todos los obstáculos de una acera: recórrala y añada los que falten.")
			)
		if cajas:
			self.informe.anotar_deducido(
				_(
					"Los obstáculos se han dejado como cajas con nombre porque no está instalado el complemento «calle» (o no tiene ese objeto). Funcionan igual."
				)
			)
		if como_referencia:
			self.informe.contar("obstaculos_como_referencia", como_referencia)
			self.informe.anotar_aviso(
				_n(
					"{n} obstáculo del mapa no cabía en su sitio (cae dentro de un edificio o sobre otro) y se ha dejado como referencia.",
					"{n} obstáculos del mapa no cabían en su sitio (caen dentro de un edificio o sobre otro) y se han dejado como referencias.",
					como_referencia,
				).format(n=como_referencia)
			)

	# ── Paradas y lugares ──

	def paradas(self) -> None:
		"""Paradas de autobús, tranvía, taxi y bocas de metro como referencias."""
		candidatas: list[tuple[Punto, dict[str, str], str, int | None]] = []
		for nodo, etiquetas in self.etiquetas_nodo.items():
			if self._clave_de_parada(etiquetas) is not None and self.dentro(self.xy[nodo]):
				candidatas.append((self.xy[nodo], etiquetas, f"node/{nodo}", nodo))
		for identificador, (nodos, etiquetas) in self.vias_osm.items():
			if self._clave_de_parada(etiquetas) is None:
				continue
			puntos, _ids = self.puntos_de(nodos)
			if not puntos:
				continue
			cerrado = len(puntos) >= 4 and nodos[0] == nodos[-1]
			punto = formas.punto_interior(puntos[:-1]) if cerrado else geo.punto_en_linea(puntos, geo.longitud_linea(puntos) / 2.0)[0]
			if self.dentro(punto):
				candidatas.append((punto, etiquetas, f"way/{identificador}", None))
		firmes = [c for c in candidatas if c[1].get("public_transport") != "stop_position"]
		creadas: list[tuple[Punto, str]] = []
		sin_lineas = 0
		for punto, etiquetas, _osm, nodo in firmes + [c for c in candidatas if c[1].get("public_transport") == "stop_position"]:
			if etiquetas.get("public_transport") == "stop_position" and any(geo.distancia(punto, otro[0]) < 30.0 for otro in firmes):
				continue
			clave = self._clave_de_parada(etiquetas)
			if clave is None:
				continue
			base = _(et.PARADAS[clave])
			if clave[0] == "public_transport":
				for medio, nombre_medio in et.MEDIOS_DE_PARADA.items():
					if etiquetas.get(medio) == "yes":
						base = _(nombre_medio)
						break
			propio = etiquetas.get("name", "")
			nombre = f"{base} {propio}".strip()
			if any(nombre == otro and geo.distancia(punto, lugar) < 12.0 for lugar, otro in creadas):
				continue
			partes: list[str] = []
			if etiquetas.get("ref") or etiquetas.get("local_ref"):
				partes.append(_("Código de parada: {ref}.").format(ref=etiquetas.get("ref") or etiquetas.get("local_ref")))
			lineas = etiquetas.get("route_ref") or etiquetas.get("lines") or ""
			if lineas:
				partes.append(
					_("Líneas, según el mapa: {lineas}.").format(
						lineas=", ".join(parte.strip() for parte in lineas.replace(",", ";").split(";") if parte.strip())
					)
				)
			elif clave[1] not in ("subway_entrance", "taxi"):
				partes.append(_("Líneas: el mapa no lo dice."))
				sin_lineas += 1
			for clave_osm, con, sin, atributo in (
				("shelter", _("Con marquesina."), _("Sin marquesina."), _("Marquesina")),
				("bench", _("Con banco."), _("Sin banco."), _("Banco")),
				("tactile_paving", _("Con pavimento táctil."), _("Sin pavimento táctil."), _("Pavimento táctil")),
			):
				if clave[1] in ("subway_entrance", "station") and clave_osm != "tactile_paving":
					continue
				estado = et.tres_estados(etiquetas.get(clave_osm))
				partes.append(
					con if estado == SI else sin if estado == NO else _("{atributo}: el mapa no lo dice.").format(atributo=atributo)
				)
			ed.crear_parada(
				self.entorno,
				self.planta,
				self.nombre_unico(nombre) if not propio else nombre,
				punto[0],
				punto[1],
				descripcion=" ".join(partes),
			)
			creadas.append((punto, nombre))
			if nodo is not None:
				self.nodos_usados.add(nodo)
		if creadas:
			self.informe.contar("paradas", len(creadas))
			self.informe.anotar_importado(
				_("{paradas} de transporte (como referencias).").format(paradas=frase_cuenta(len(creadas), "{n} parada", "{n} paradas"))
			)
			self.informe.anotar_revisar(_("En cada parada: sitúe el poste o la marquesina exactos y compruebe las líneas."))
		if sin_lineas:
			self.informe.anotar_falta(
				_n("{n} parada no dice qué líneas paran.", "{n} paradas no dicen qué líneas paran.", sin_lineas).format(n=sin_lineas)
			)

	@staticmethod
	def _clave_de_parada(etiquetas: dict[str, str]) -> tuple[str, str] | None:
		for clave in ("highway", "railway", "public_transport", "amenity"):
			par = (clave, etiquetas.get(clave, ""))
			if par in et.PARADAS:
				return par
		return None

	@staticmethod
	def _tipo_de_lugar(etiquetas: dict[str, str]) -> tuple[str, str, tuple[str, str]] | None:
		"""(tipo de referencia, nombre del tipo, etiqueta) de un sitio de interés; None si no lo es."""
		for clave in et.CLAVES_LUGAR:
			valor = etiquetas.get(clave, "")
			if not valor or valor == "no":
				continue
			if (clave, valor) in et.LUGARES:
				tipo, nombre = et.LUGARES[(clave, valor)]
				return tipo, nombre, (clave, valor)
			if clave in et.LUGARES_GENERICOS and etiquetas.get("name"):
				tipo, nombre = et.LUGARES_GENERICOS[clave]
				return tipo, nombre, (clave, valor)
		return None

	def lugares(self) -> None:
		"""Comercios y servicios con nombre como referencias, con su tipo en español."""
		candidatos: list[tuple[Punto, dict[str, str]]] = []
		for nodo, etiquetas in self.etiquetas_nodo.items():
			if nodo not in self.nodos_usados and self.dentro(self.xy[nodo]):
				candidatos.append((self.xy[nodo], etiquetas))
		for area in self.areas:
			if (
				area.etiquetas.get("building", "no") != "no"
				or "indoor" in area.etiquetas
				or self._clase_de_area(area.etiquetas) is not None
			):
				continue
			contorno = formas.limpiar_poligono(area.puntos)
			if len(contorno) >= 3 and self.dentro(geo.centroide(contorno)):
				candidatos.append((formas.punto_interior(contorno), area.etiquetas))
		creados = 0
		for numero_lugar, (punto, etiquetas) in enumerate(candidatos, start=1):
			self._avance(numero_lugar, len(candidatos))
			lugar = self._tipo_de_lugar(etiquetas)
			if lugar is None or lugar[0] == "parada":
				continue
			tipo, nombre_tipo, par = lugar
			if not etiquetas.get("name") and par not in et.LUGARES_SIN_NOMBRE:
				continue
			tipo_dicho = _(nombre_tipo)
			partes = [tipo_dicho.capitalize() + "."]
			if etiquetas.get("addr:housenumber"):
				partes.append(
					_("Dirección: {calle} {numero}.")
					.format(calle=etiquetas.get("addr:street", ""), numero=etiquetas["addr:housenumber"])
					.replace("  ", " ")
				)
			caja_punto = (punto[0], punto[1], punto[0], punto[1])
			dentro_de = next(
				(
					m
					for m in self._indice_macizos.cerca(self.macizos, caja_punto)
					if geo.cajas_se_tocan(m.caja(), caja_punto) and m.contiene(*punto)
				),
				None,
			)
			if dentro_de is not None:
				partes.append(_("Está dentro de «{edificio}»; el mapa no dice dónde tiene la puerta.").format(edificio=dentro_de.nombre))
			nombre = etiquetas.get("name") or self.nombre_unico(tipo_dicho.capitalize())
			ed.anadir_referencia(self.entorno, self.planta, nombre, punto[0], punto[1], tipo=tipo, descripcion=" ".join(partes))
			creados += 1
		if creados:
			self.informe.contar("lugares", creados)
			self.informe.anotar_importado(
				_("{lugares} (comercios y servicios) con su tipo, como referencias.").format(
					lugares=frase_cuenta(creados, "{n} lugar", "{n} lugares")
				)
			)
			self.informe.anotar_revisar(
				_(
					"Los comercios cambian a menudo y el mapa puede estar anticuado: compruebe los que quiera usar como referencia, y dónde está su puerta."
				)
			)
		self.informe.anotar_falta(
			_(
				"El mapa no describe sonidos ni olores: no se ha creado ninguna fuente de sonido. Añada las que sirvan de referencia (una fuente, una terraza, un semáforo)."
			)
		)

	# ── Final ──

	def inicio(self) -> None:
		"""Deja el punto de inicio en un sitio donde se pueda estar: una acera, un camino o una plaza."""
		candidatos: list[tuple[Punto, float]] = []
		centro = ((self.caja[0] + self.caja[2]) / 2.0, (self.caja[1] + self.caja[3]) / 2.0)
		for tipos in (("acera",), ("sendero", "plaza"), ("parque",)):
			grupo = [e for e in self.planta.espacios if e.tipo in tipos and not e.macizo]
			grupo.sort(key=lambda e: geo.distancia(e.centro(), centro))
			for espacio in grupo:
				punto = formas.punto_interior(espacio.contorno)
				candidatos.append((punto, self._rumbo_a_lo_largo(espacio, punto)))
		candidatos.extend(candidatos_en_rejilla(self.caja, 2.0))
		if not fijar_inicio_valido(self.entorno, self.planta, candidatos, self.catalogo):
			self.entorno.inicio.planta = self.planta.id
			self.informe.anotar_aviso(_("No se ha encontrado un punto libre para el inicio: fíjelo a mano antes de recorrer el entorno."))
		else:
			donde = self.planta.espacio_en(self.entorno.inicio.x, self.entorno.inicio.y)
			self.informe.anotar_deducido(
				_("El punto de inicio se ha puesto en «{espacio}». Cámbielo al sitio desde el que el alumno empezará.").format(
					espacio=donde.nombre if donde else ""
				)
			)

	def _rumbo_a_lo_largo(self, espacio: Espacio, punto: Punto) -> float:
		"""Rumbo inicial a lo largo del espacio: el de su calle en una acera; si no, el de su lado largo.

		Con calles reales, que casi nunca van de este a oeste, mirar «al lado
		largo de la caja» ponía al alumno de cara a la calzada: en la Plaza
		Mayor de Valladolid, tres pasos y estaba en mitad de la calle.
		"""
		via = next((v for v in self.planta.vias if v.id == espacio.datos.get("via")), None) if espacio.tipo == "acera" else None
		if via is not None and len(via.eje) >= 2:
			_cerca, _distancia, indice = geo.proyeccion_sobre_linea(punto, via.eje)
			indice = min(max(indice, 0), len(via.eje) - 2)
			rumbo = geo.rumbo_entre(via.eje[indice], via.eje[indice + 1])
			# De los dos sentidos de la calle, el que deja más acera por delante.
			return round(
				max(
					(rumbo, (rumbo + 180.0) % 360.0),
					key=lambda r: sum(espacio.contiene(*geo.punto_a_distancia(punto, r, d)) for d in range(1, 11)),
				),
				1,
			)
		x0, y0, x1, y1 = espacio.caja()
		return 90.0 if x1 - x0 >= y1 - y0 else 0.0

	def procedencia(self) -> None:
		"""Apunta de dónde sale el entorno: fuente, fecha, licencia, atribución y recuadro."""
		sur, oeste, norte, este = self.recuadro
		recuadro = [round(sur, 7), round(oeste, 7), round(norte, 7), round(este, 7)]
		self.entorno.georef = {
			"lat0": round(self.proyeccion.lat0, 7),
			"lon0": round(self.proyeccion.lon0, 7),
			"proyeccion": "local_plana",
			"recuadro": recuadro,
		}
		base = self.datos.get("osm3s")
		self.entorno.procedencia = {
			"fuente": FUENTE_OSM,
			"fecha": datetime.date.today().isoformat(),
			"fecha_datos": str(base.get("timestamp_osm_base") or "") if isinstance(base, dict) else "",
			"escala": "1:1",
			"licencia": LICENCIA,
			"atribucion": ATRIBUCION,
			"url_licencia": URL_LICENCIA,
			"recuadro": recuadro,
			"servidor": str(self.datos.get("servidor") or ""),
			"notas": _(
				"Borrador importado de OpenStreetMap. Lo que el mapa no dice figura como «el mapa no lo dice»; las aceras, anchuras y "
				"tiempos deducidos están marcados. Cualquier copia o exportación debe conservar la atribución."
			),
		}
		self.informe.titulo = _("Informe de la importación de OpenStreetMap: «{nombre}»").format(nombre=self.entorno.nombre)
		x0, y0, x1, y1 = self.caja
		self.informe.importado.insert(
			0,
			_("Zona de {ancho} por {alto} metros. Datos: {atribucion}, licencia {licencia}.").format(
				ancho=round(x1 - x0), alto=round(y1 - y0), atribucion=ATRIBUCION, licencia=LICENCIA
			),
		)
		self.informe.anotar_revisar(
			_(
				"Todo el entorno es un borrador: OpenStreetMap lo hacen voluntarios y puede tener errores, faltas o estar anticuado. Recórralo antes de usarlo con un alumno."
			)
		)

	def _preparar_fases(self, interiores: bool) -> None:
		"""Tabla de fases con la parte de la barra que le toca a cada una.

		Los pesos salen de medir la conversión de zonas de 150, 300 y 400
		metros de radio (ver ``tests/test_importar_osm_rendimiento.py``): los
		edificios se llevan algo más de la mitad del tiempo (ajustar las
		medianeras y comprobar cada contorno), el punto de inicio y los
		obstáculos un 10 % cada uno y el resto poco. Así la barra avanza más o
		menos al ritmo del tiempo real y no se queda parada en una fase larga.
		"""
		pesos: list[tuple[str, str, float]] = [("leer", _("Leyendo los datos del mapa"), 2.0)]
		if self.op.edificios:
			pesos.append(("edificios", _("Creando edificios y portales"), 50.0))
		pesos.append(("zonas", _("Creando plazas, parques y zonas peatonales"), 3.0))
		pesos.append(("calles", _("Convirtiendo calles"), 5.0))
		pesos.append(("cruces", _("Formando los cruces"), 1.0))
		if self.op.aceras:
			pesos.append(("aceras", _("Creando aceras"), 4.0))
		pesos.append(("caminos", _("Convirtiendo caminos, escaleras y rampas"), 4.0))
		pesos.append(("pasos", _("Colocando pasos de peatones"), 1.0))
		pesos.append(("barreras", _("Convirtiendo muros y vallas"), 1.0))
		if interiores:
			pesos.append(("interiores", _("Importando interiores de edificios"), 5.0))
		if self.op.obstaculos:
			pesos.append(("obstaculos", _("Colocando obstáculos y mobiliario"), 10.0))
		pesos.append(("paradas", _("Colocando paradas de transporte"), 1.0))
		if self.op.lugares:
			pesos.append(("lugares", _("Colocando comercios y servicios"), 4.0))
		pesos.append(("inicio", _("Buscando el punto de inicio"), 12.0))
		pesos.append(("comprobar", _("Comprobando el entorno"), 1.0))
		suma = sum(peso for _clave, _nombre, peso in pesos)
		acumulado = 0.0
		self._fases = []
		for clave, nombre, peso in pesos:
			inicio = 0.02 + 0.96 * acumulado / suma
			acumulado += peso
			self._fases.append((clave, nombre, inicio, 0.02 + 0.96 * acumulado / suma))

	def ejecutar(self) -> ResultadoImportacion:
		"""Hace la conversión completa, fase a fase, avisando del progreso con la fase y sus cifras."""
		fases: list[tuple[str, Callable[[], Any]]] = []
		self._preparar_fases(bool(self.op.interiores))
		elementos = self.datos.get("elements") if isinstance(self.datos, dict) else None
		self._entrar(
			"leer",
			_("{fase}: {n} elementos.").format(fase=_("Leyendo los datos del mapa"), n=len(elementos))
			if isinstance(elementos, list)
			else "",
		)
		self.indexar()
		self.crear_entorno()
		self.reunir_areas()
		interiores = None
		if self.op.interiores:
			from app.importar import osm_interiores

			interiores = osm_interiores
			interiores.preparar(self)
		elif any("indoor" in area.etiquetas for area in self.areas):
			self.informe.anotar_revisar(
				_("La zona tiene interiores de edificios en el mapa. No se han importado: active la opción de interiores si los quiere.")
			)
		peatonales: list[_Tramo] = []

		def paso_calles() -> None:
			peatonales.extend(self.calles())

		if self.op.edificios:
			fases.append(("edificios", self.edificios))
		fases.append(("zonas", self.zonas))
		fases.append(("calles", paso_calles))
		fases.append(("caminos", lambda: self.caminos(peatonales)))
		fases.append(("pasos", self.pasos))
		fases.append(("barreras", self.barreras))
		if interiores is not None:
			fases.append(("interiores", lambda: interiores.importar(self)))
		if self.op.obstaculos:
			fases.append(("obstaculos", self.obstaculos))
		fases.append(("paradas", self.paradas))
		if self.op.lugares:
			fases.append(("lugares", self.lugares))
		fases.append(("inicio", self.inicio))
		for clave, funcion in fases:
			self._entrar(clave)
			funcion()
		espacios = sum(len(planta.espacios) for planta in self.entorno.plantas)
		self._entrar(
			"comprobar",
			_("{fase}: {espacios}.").format(
				fase=_("Comprobando el entorno"), espacios=frase_cuenta(espacios, "{n} espacio", "{n} espacios")
			),
		)
		self.procedencia()
		_IdsSecuenciales.retirar(self.entorno)
		self._terminar_fases()
		avisar_fase(self.progreso, 1.0, _("Importación terminada"), _("Importación terminada."))
		return ResultadoImportacion(self.entorno, self.informe)


def convertir(
	datos_osm: dict[str, Any], opciones: OpcionesOSM | None = None, progreso: Progreso | None = None, cancelado: Cancelado | None = None
) -> ResultadoImportacion:
	"""Convierte datos de OpenStreetMap (el JSON de Overpass) en un entorno con su informe.

	``datos_osm`` es lo que devuelven ``descargar_zona`` e
	``importar_fichero_osm``. El entorno resultante tiene una planta
	exterior (y plantas interiores si se pide y el mapa las tiene),
	georreferencia y procedencia completas. Lanza ``ErrorImportacion`` con
	un mensaje legible si los datos no sirven, e ``ImportacionCancelada`` si
	``cancelado()`` devuelve True (se comprueba entre fases y dentro de cada
	una, elemento a elemento).

	``progreso(fraccion, texto)`` recibe la fase y sus cifras en el texto
	(«Convirtiendo calles: 12 de 30.»); si además tiene ``por_fases``, recibe
	la fase y las cifras por separado (ver ``comun.avisar_fase``). Se llama
	desde el hilo que convierte, nunca desde el de la interfaz.

	Deja en el registro (INFO) cuánto ha tardado cada fase, para saber dónde
	se va el tiempo si una importación tarda.
	"""
	inicio = time.monotonic()
	conversor = Conversor(datos_osm, opciones or OpcionesOSM(), progreso, cancelado)
	try:
		resultado = conversor.ejecutar()
	except ErrorImportacion:
		conversor._terminar_fases()
		log.info(
			"Conversión de OpenStreetMap detenida tras %.1f s; fases hechas: %s",
			time.monotonic() - inicio,
			_texto_duraciones(conversor.duraciones),
		)
		raise
	log.info(
		"Importación de OpenStreetMap: %s espacios, %s vías, %s referencias, %s objetos; %s elementos del mapa convertidos en %.2f s",
		sum(len(p.espacios) for p in resultado.entorno.plantas),
		sum(len(p.vias) for p in resultado.entorno.plantas),
		sum(len(p.referencias) for p in resultado.entorno.plantas),
		sum(len(p.objetos) for p in resultado.entorno.plantas),
		len(datos_osm.get("elements") or []) if isinstance(datos_osm, dict) else 0,
		time.monotonic() - inicio,
	)
	log.info("Duración de cada fase de la conversión (segundos): %s", _texto_duraciones(conversor.duraciones))
	return resultado


def _texto_duraciones(duraciones: dict[str, float]) -> str:
	"""«edificios 0.52; calles 0.30…» para el registro, en el orden en que se hicieron (no se traduce)."""
	return "; ".join(f"{clave} {segundos:.2f}" for clave, segundos in duraciones.items()) or "ninguna"
