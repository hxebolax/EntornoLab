"""Colocación de objetos a escala y sin ver.

Todo se mide en metros reales, así que antes de dar un objeto por colocado
se comprueba que cabe en su espacio, que no se solapa con otros objetos ni
con paredes, que no tapa una puerta y que deja el paso mínimo que haya
fijado el profesional.

Las funciones de ayuda permiten colocar por relaciones en lugar de por
coordenadas («contra la pared norte, centrado», «en la esquina sureste»,
«al este de la cama»), que es como trabaja quien no ve el plano. Todas
ajustan antes las medidas con el catálogo (variante más pequeña o escala
dentro del rango) y, si ni así cabe, lo dicen y no colocan nada: un objeto
nunca queda más grande que la habitación.
"""

from __future__ import annotations

import contextlib
import logging
import math
import threading
from collections.abc import Callable, Iterator, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.i18n import N_, _, separador_decimal
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo, DefObjeto, sin_acentos
from app.dominio.geometria import RUMBO_DE_LADO, Punto
from app.dominio.modelo import (
	Abertura,
	Aviso,
	Entorno,
	Espacio,
	Objeto,
	Pared,
	Planta,
	ZonaSuelo,
	hay_errores,
	segmentos_solidos,
)

log = logging.getLogger(__name__)

# Paso libre mínimo de serie, en metros (una persona con bastón o perro guía).
PASO_MINIMO = 0.8
# Fondo que debe quedar libre a cada lado de una puerta para poder cruzarla.
FONDO_LIBRE_PUERTA = 0.6
# Por debajo de esta separación dos cosas están «adosadas»: no hay hueco que medir.
HOLGURA = 0.02

LADOS = ("norte", "este", "sur", "oeste")
ESQUINAS: dict[str, tuple[str, str]] = {
	"noreste": ("norte", "fin"),
	"noroeste": ("norte", "inicio"),
	"sureste": ("sur", "fin"),
	"suroeste": ("sur", "inicio"),
}
ALINEACIONES = ("inicio", "centro", "fin")


@dataclass
class Colocacion:
	"""Resultado de intentar colocar un objeto: el objeto (si se colocó) y los avisos."""

	objeto: Objeto | None = None
	avisos: list[Aviso] = field(default_factory=list)

	@property
	def colocado(self) -> bool:
		"""True si el objeto ha quedado en la planta."""
		return self.objeto is not None


def _nombre(objeto: Objeto) -> str:
	return objeto.nombre or objeto.tipo


def _aviso(gravedad: str, codigo: str, mensaje: str, objeto: Objeto | None, planta: Planta | None, sugerencia: str) -> Aviso:
	return Aviso(
		gravedad=gravedad,
		codigo=codigo,
		mensaje=mensaje,
		elemento_id=objeto.id if objeto else "",
		planta_id=planta.id if planta else "",
		sugerencia=sugerencia,
	)


def _metros(valor: float) -> str:
	"""Una medida con dos decimales y coma, como se dice en español."""
	return f"{valor:.2f}".replace(".", separador_decimal())


def _rango_vertical(objeto: Objeto, catalogo: Catalogo) -> tuple[float, float]:
	"""Alturas (suelo, techo) que ocupa el objeto: uno colgado no choca con uno bajo."""
	definicion = catalogo.definicion_de(objeto)
	base = float(objeto.datos.get("altura_base", definicion.altura_base if definicion else 0.0))
	return base, base + max(objeto.alto, 0.0)


def _se_cruzan_en_altura(a: Objeto, b: Objeto, catalogo: Catalogo) -> bool:
	base_a, techo_a = _rango_vertical(a, catalogo)
	base_b, techo_b = _rango_vertical(b, catalogo)
	return base_a < techo_b - 1e-6 and base_b < techo_a - 1e-6


def zona_de_paso(abertura: Abertura, fondo: float = FONDO_LIBRE_PUERTA) -> list[Punto]:
	"""Rectángulo que debe quedar libre delante y detrás de una abertura para cruzarla."""
	centro = abertura.centro()
	ancho = max(abertura.ancho - 0.1, 0.1)
	return geo.rectangulo_girado(centro[0], centro[1], ancho, 2 * fondo, geo.rumbo_entre(abertura.a, abertura.b) - 90.0)


def _adosado_a_la_recta(huella: list[Punto], a: Punto, b: Punto) -> bool:
	"""True si el polígono toca (o cruza) la recta que pasa por a y b."""
	largo = geo.distancia(a, b)
	if largo < 1e-9:
		return False
	lados = [geo.lado_de(punto, a, b) / largo for punto in huella]
	return min(lados) <= HOLGURA and max(lados) >= -HOLGURA


# ── Vecindario de una planta (para comprobar muchos objetos seguidos) ────────

_lote = threading.local()


@contextlib.contextmanager
def lote_de_comprobaciones() -> Iterator[None]:
	"""Mientras dure el bloque, las paredes y las puertas de cada planta se calculan una sola vez.

	Por qué: ``comprobar`` necesita los segmentos que cortan el paso y las
	zonas de paso de las puertas de toda la planta, y la validación y el
	amueblado lo llaman para cada objeto. Con un barrio de miles de espacios y
	cientos de objetos, rehacerlos cada vez era lo que más tardaba al
	comprobar el entorno. Dentro del bloque no se pueden mover paredes,
	espacios ni puertas (los objetos sí: se miran siempre en vivo). Se puede anidar.
	"""
	previo = getattr(_lote, "planta", None)
	if previo is None:
		_lote.planta = {}
	try:
		yield
	finally:
		if previo is None:
			_lote.planta = None


class _Vecindario:
	"""Paredes y zonas de paso de una planta con una rejilla para pedir solo las que hay cerca de una huella.

	Solo preselecciona: quien pregunta aplica la misma comprobación de siempre a
	las candidatas, que salen en el orden de la planta, así que los avisos son
	idénticos a los de recorrer todas.
	"""

	def __init__(self, planta: Planta) -> None:
		from app.dominio.indice_espacial import RejillaCajas

		self.planta = planta
		self.indice = planta.indice_espacios()
		self.segmentos = segmentos_solidos(planta)
		self._cajas_segmentos = [geo.caja((segmento.a, segmento.b)) for segmento in self.segmentos]
		self._rejilla_segmentos = RejillaCajas(4.0)
		for caja in self._cajas_segmentos:
			self._rejilla_segmentos.meter(caja)
		self.zonas = [(abertura, zona_de_paso(abertura)) for abertura in planta.aberturas if abertura.tipo != "ventana"]
		self._rejilla_zonas = RejillaCajas(4.0)
		for _abertura, zona in self.zonas:
			self._rejilla_zonas.meter(geo.caja(zona))

	def segmentos_cerca(self, caja: tuple[float, float, float, float], margen: float) -> list[Any]:
		"""Segmentos cuya caja puede tocar ``caja`` ampliada en ``margen``, en el orden de ``segmentos_solidos``."""
		x0, y0, x1, y1 = caja
		return [self.segmentos[i] for i in self._rejilla_segmentos.en_caja(x0 - margen, y0 - margen, x1 + margen, y1 + margen)]

	def zonas_cerca(self, caja: tuple[float, float, float, float]) -> list[tuple[Abertura, list[Punto]]]:
		"""Puertas (no ventanas) cuya zona de paso puede solaparse con ``caja``, en el orden de la planta."""
		x0, y0, x1, y1 = caja
		return [self.zonas[i] for i in self._rejilla_zonas.en_caja(x0, y0, x1, y1)]


def _vecindario(planta: Planta) -> _Vecindario:
	"""El vecindario de la planta: el del lote en curso si lo hay; si no, uno nuevo."""
	cache: dict[int, _Vecindario] | None = getattr(_lote, "planta", None)
	if cache is None:
		return _Vecindario(planta)
	vecindario = cache.get(id(planta))
	if vecindario is None or vecindario.planta is not planta:
		vecindario = _Vecindario(planta)
		cache[id(planta)] = vecindario
	return vecindario


# ── Comprobación y colocación ────────────────────────────────────────────────


def comprobar(
	entorno: Entorno,
	planta: Planta,
	objeto: Objeto,
	catalogo: Catalogo | None,
	paso_minimo: float = PASO_MINIMO,
) -> list[Aviso]:
	"""Revisa un objeto en su posición sin modificar nada.

	Errores (no debería colocarse): fuera de todo espacio, no cabe en su
	habitación, se mete en un edificio macizo, en una pared o en otro objeto.
	Avisos (conviene revisarlo): tapa una puerta, deja un paso más estrecho
	que ``paso_minimo`` o sobresale de su zona en un exterior.
	"""
	catalogo = catalogo if catalogo is not None else Catalogo()
	avisos: list[Aviso] = []
	nombre = _nombre(objeto)
	if objeto.ancho <= 0 or objeto.fondo <= 0:
		avisos.append(
			_aviso(
				"error",
				"medidas_no_validas",
				_("«{nombre}» tiene medidas no válidas ({ancho} por {fondo} metros).").format(
					nombre=nombre, ancho=_metros(objeto.ancho), fondo=_metros(objeto.fondo)
				),
				objeto,
				planta,
				_("Póngale un ancho y un fondo mayores que cero."),
			)
		)
		return avisos
	huella = catalogo.huella(objeto)
	caja_huella = geo.caja(huella)
	bloquea = catalogo.bloquea(objeto)
	vecindario = _vecindario(planta)
	espacio = next((e for e in vecindario.indice.espacios_en(objeto.x, objeto.y) if not e.macizo), None)

	# Solo pueden solaparse con la huella los macizos cuya caja la toca (el índice los da en el orden de la planta).
	for macizo in vecindario.indice.en_caja(*caja_huella):
		if macizo.macizo and len(macizo.contorno) >= 3 and geo.poligonos_se_solapan(huella, macizo.contorno):
			avisos.append(
				_aviso(
					"error",
					"solapa_macizo",
					_("«{nombre}» se mete dentro de «{espacio}», que es macizo.").format(nombre=nombre, espacio=macizo.nombre),
					objeto,
					planta,
					_("Sepárelo del edificio."),
				)
			)
	if espacio is None:
		if not any(a.codigo == "solapa_macizo" for a in avisos):
			avisos.append(
				_aviso(
					"error",
					"fuera_de_espacio",
					_("«{nombre}» está fuera de todos los espacios de la planta «{planta}».").format(nombre=nombre, planta=planta.nombre),
					objeto,
					planta,
					_("Muévalo dentro de una habitación o de una zona."),
				)
			)
	elif not geo.poligono_contiene(espacio.contorno, huella):
		if espacio.cerrado:
			avisos.append(
				_aviso(
					"error",
					"no_cabe",
					_("«{nombre}» ({ancho} por {fondo} metros) no cabe en ese sitio de «{espacio}»: atraviesa una pared.").format(
						nombre=nombre, ancho=_metros(objeto.ancho), fondo=_metros(objeto.fondo), espacio=espacio.nombre
					),
					objeto,
					planta,
					_("Muévalo hacia dentro, gírelo o elija un tamaño más pequeño."),
				)
			)
		else:
			avisos.append(
				_aviso(
					"aviso",
					"sobresale",
					_("«{nombre}» sobresale de «{espacio}».").format(nombre=nombre, espacio=espacio.nombre),
					objeto,
					planta,
					_("Compruebe que no invade la zona de al lado."),
				)
			)

	for pared in planta.paredes:
		if pared.bloquea_paso and geo.segmento_cruza_poligono(pared.a, pared.b, huella):
			avisos.append(
				_aviso(
					"error",
					"solapa_pared",
					_("«{nombre}» atraviesa la pared «{pared}».").format(nombre=nombre, pared=pared.nombre or pared.id),
					objeto,
					planta,
					_("Sepárelo de la pared."),
				)
			)

	otros: list[tuple[Objeto, list[Punto]]] = []
	for otro in planta.objetos:
		if otro is objeto or (objeto.id and otro.id == objeto.id):
			continue
		margen = paso_minimo + max(otro.ancho, otro.fondo)
		# Descarte barato antes de girar la huella del otro: cabe entera en el círculo de su diagonal.
		radio = math.hypot(otro.ancho, otro.fondo) / 2.0 + 1e-9
		if not geo.cajas_se_tocan(caja_huella, (otro.x - radio, otro.y - radio, otro.x + radio, otro.y + radio), margen=margen):
			continue
		if not geo.cajas_se_tocan(caja_huella, geo.caja(otro.huella_caja()), margen=margen):
			continue
		otros.append((otro, catalogo.huella(otro)))
	if bloquea:
		for otro, huella_otro in otros:
			if not catalogo.bloquea(otro) or not _se_cruzan_en_altura(objeto, otro, catalogo):
				continue
			if geo.poligonos_se_solapan(huella, huella_otro):
				avisos.append(
					_aviso(
						"error",
						"solapa_objeto",
						_("«{nombre}» se solapa con «{otro}».").format(nombre=nombre, otro=_nombre(otro)),
						objeto,
						planta,
						_("Separe uno de los dos."),
					)
				)

		for abertura, zona in vecindario.zonas_cerca(caja_huella):
			if geo.poligonos_se_solapan(huella, zona):
				avisos.append(
					_aviso(
						"aviso",
						"tapa_abertura",
						_("«{nombre}» tapa «{abertura}».").format(nombre=nombre, abertura=abertura.nombre or abertura.id),
						objeto,
						planta,
						_("Deje libres al menos {metros} metros delante de la puerta.").format(metros=_metros(FONDO_LIBRE_PUERTA)),
					)
				)

		# Paso mínimo: el hueco más estrecho (que no sea cero) hasta otro objeto o hasta una pared.
		for otro, huella_otro in otros:
			if not catalogo.bloquea(otro) or not _se_cruzan_en_altura(objeto, otro, catalogo):
				continue
			hueco = geo.distancia_entre_poligonos(huella, huella_otro)
			if HOLGURA < hueco < paso_minimo - 1e-6:
				avisos.append(
					_aviso(
						"aviso",
						"paso_estrecho",
						_("Entre «{nombre}» y «{otro}» queda un paso de {hueco} metros, menos que el mínimo de {minimo}.").format(
							nombre=nombre, otro=_nombre(otro), hueco=_metros(hueco), minimo=_metros(paso_minimo)
						),
						objeto,
						planta,
						_("Júntelos del todo o sepárelos más."),
					)
				)
		menor = math.inf
		for segmento in vecindario.segmentos_cerca(caja_huella, paso_minimo):
			if not geo.cajas_se_tocan(caja_huella, geo.caja((segmento.a, segmento.b)), margen=paso_minimo):
				continue
			if _adosado_a_la_recta(huella, segmento.a, segmento.b):
				# Es la pared en la que se apoya (o su continuación al otro lado de una puerta): ahí no hay paso que medir.
				continue
			hueco = geo.distancia_poligono_segmento(huella, segmento.a, segmento.b)
			if HOLGURA < hueco < menor:
				menor = hueco
		if menor < paso_minimo - 1e-6:
			avisos.append(
				_aviso(
					"aviso",
					"paso_estrecho",
					_("Entre «{nombre}» y la pared queda un paso de {hueco} metros, menos que el mínimo de {minimo}.").format(
						nombre=nombre, hueco=_metros(menor), minimo=_metros(paso_minimo)
					),
					objeto,
					planta,
					_("Péguelo a la pared o sepárelo más."),
				)
			)
	return avisos


def colocar(
	entorno: Entorno,
	planta: Planta,
	objeto: Objeto,
	catalogo: Catalogo | None,
	paso_minimo: float = PASO_MINIMO,
	forzar: bool = False,
) -> list[Aviso]:
	"""Comprueba un objeto y, si no hay errores, lo añade a la planta.

	Devuelve siempre los avisos. Con errores el objeto NO se añade (salvo
	``forzar``); los avisos de gravedad «aviso» no impiden colocarlo. Si el
	objeto no tenía id se le asigna uno, y su complemento queda anotado en el entorno.
	"""
	avisos = comprobar(entorno, planta, objeto, catalogo, paso_minimo)
	if hay_errores(avisos) and not forzar:
		return avisos
	if not objeto.id:
		objeto.id = entorno.nuevo_id("obj")
		for aviso in avisos:
			aviso.elemento_id = objeto.id
	if not any(existente is objeto for existente in planta.objetos):
		planta.objetos.append(objeto)
	id_complemento, separador, _resto = objeto.tipo.partition("/")
	if separador and id_complemento not in entorno.complementos:
		entorno.complementos.append(id_complemento)
	return avisos


# ── Lados de un espacio ──────────────────────────────────────────────────────


def lado_de_espacio(espacio: Espacio, lado: str) -> tuple[int, Punto, Punto] | None:
	"""Lado del contorno que hace de pared «norte», «sur», «este» u «oeste».

	Devuelve (índice, inicio, fin), con el inicio en el extremo oeste (lados
	norte y sur) o sur (lados este y oeste): así «a 1,20 del inicio» significa
	lo mismo en todas las habitaciones. En una habitación con varios lados
	que miran hacia allí (una en ele) se elige el más extremo y, a igualdad, el más largo.
	"""
	if lado not in LADOS or len(espacio.contorno) < 3:
		return None
	contorno = espacio.contorno
	indices = list(range(len(contorno)))
	antihorario = geo.es_antihorario(contorno)
	objetivo = RUMBO_DE_LADO[lado]
	dx, dy = geo.vector_rumbo(objetivo)
	mejor: tuple[float, float, int] | None = None
	for indice in indices:
		a, b = contorno[indice], contorno[(indice + 1) % len(contorno)]
		largo = geo.distancia(a, b)
		if largo < 1e-6:
			continue
		normal = geo.rumbo_entre(a, b) + (90.0 if antihorario else -90.0)
		if abs(geo.diferencia_rumbos(normal, objetivo)) > 45.0 + 1e-6:
			continue
		medio = geo.punto_medio(a, b)
		extremo = round(medio[0] * dx + medio[1] * dy, 6)
		if mejor is None or (extremo, largo) > (mejor[0], mejor[1]):
			mejor = (extremo, largo, indice)
	if mejor is None:
		return None
	indice = mejor[2]
	a, b = contorno[indice], contorno[(indice + 1) % len(contorno)]
	eje = 0 if lado in ("norte", "sur") else 1
	if a[eje] > b[eje]:
		a, b = b, a
	return indice, a, b


def _rumbo_interior(espacio: Espacio, a: Punto, b: Punto) -> float:
	"""Rumbo perpendicular al lado ab que apunta hacia dentro del espacio."""
	medio = geo.punto_medio(a, b)
	base = geo.rumbo_entre(a, b)
	for candidato in (base + 90.0, base - 90.0):
		dentro = geo.punto_a_distancia(medio, candidato, 0.05)
		if geo.punto_en_poligono(dentro, espacio.contorno, borde=False):
			return geo.normalizar_rumbo(candidato)
	return geo.normalizar_rumbo(base + 90.0)


def _crear(catalogo: Catalogo, tipo: str | Objeto, variante: str | None, nombre: str) -> Objeto:
	"""Objeto nuevo del catálogo, o el propio objeto si ya viene hecho (una caja, uno que se recoloca)."""
	if isinstance(tipo, Objeto):
		objeto = tipo
	else:
		objeto = catalogo.crear_objeto(tipo, 0.0, 0.0, 0.0, variante)
	if nombre:
		objeto.nombre = nombre
	return objeto


def _no_existe(tipo: Any, planta: Planta) -> Colocacion:
	return Colocacion(
		None,
		[
			_aviso(
				"error",
				"tipo_desconocido",
				_("El objeto «{tipo}» no está en el catálogo.").format(tipo=tipo),
				None,
				planta,
				_("Instale su complemento o elija otro objeto."),
			)
		],
	)


def _no_cabe(objeto: Objeto, planta: Planta, espacio: Espacio | None, ancho_libre: float, fondo_libre: float) -> Colocacion:
	return Colocacion(
		None,
		[
			_aviso(
				"error",
				"no_cabe",
				_("«{nombre}» no cabe{donde}: el hueco es de {ancho} por {fondo} metros y no admite un tamaño tan pequeño.").format(
					nombre=_nombre(objeto),
					donde=_(" en «{espacio}»").format(espacio=espacio.nombre) if espacio else "",
					ancho=_metros(max(ancho_libre, 0.0)),
					fondo=_metros(max(fondo_libre, 0.0)),
				),
				None,
				planta,
				_("Elija un objeto más pequeño u otro sitio."),
			)
		],
	)


def _terminar(entorno: Entorno, planta: Planta, objeto: Objeto, catalogo: Catalogo, paso_minimo: float, forzar: bool) -> Colocacion:
	avisos = colocar(entorno, planta, objeto, catalogo, paso_minimo, forzar)
	colocado = any(existente is objeto for existente in planta.objetos)
	return Colocacion(objeto if colocado else None, avisos)


# ── Colocar sin ver ──────────────────────────────────────────────────────────


def colocar_contra_pared(
	entorno: Entorno,
	planta: Planta,
	espacio: Espacio,
	tipo: str | Objeto,
	catalogo: Catalogo,
	lado: str,
	alineacion: str = "centro",
	desplazamiento: float | None = None,
	separacion: float = 0.0,
	variante: str | None = None,
	nombre: str = "",
	paso_minimo: float = PASO_MINIMO,
	forzar: bool = False,
) -> Colocacion:
	"""Coloca un objeto con la espalda contra una pared del espacio, mirando hacia dentro.

	``lado`` es norte, sur, este u oeste. ``alineacion`` (inicio, centro, fin)
	dice dónde a lo largo de la pared; el inicio es el extremo oeste o sur.
	``desplazamiento``, si se da, manda sobre la alineación: son los metros
	desde el inicio de la pared hasta el borde más cercano del objeto.
	"""
	try:
		objeto = _crear(catalogo, tipo, variante, nombre)
	except KeyError:
		return _no_existe(tipo, planta)
	encontrado = lado_de_espacio(espacio, lado)
	if encontrado is None:
		return Colocacion(
			None,
			[
				_aviso(
					"error",
					"sin_lado",
					_("«{espacio}» no tiene pared en el lado «{lado}».").format(espacio=espacio.nombre, lado=lado),
					None,
					planta,
					_("Elija norte, sur, este u oeste."),
				)
			],
		)
	_indice, inicio, fin = encontrado
	largo = geo.distancia(inicio, fin)
	hacia_dentro = _rumbo_interior(espacio, inicio, fin)
	dx, dy = geo.vector_rumbo(hacia_dentro)
	_minimo, maximo = geo.extension_en_rumbo(espacio.contorno, hacia_dentro)
	fondo_libre = maximo - (inicio[0] * dx + inicio[1] * dy) - separacion
	ancho_libre = largo - (desplazamiento or 0.0)
	if not catalogo.ajustar_objeto(objeto, ancho_libre, fondo_libre):
		return _no_cabe(objeto, planta, espacio, ancho_libre, fondo_libre)
	if desplazamiento is not None:
		recorrido = desplazamiento + objeto.ancho / 2.0
	elif alineacion == "inicio":
		recorrido = objeto.ancho / 2.0
	elif alineacion == "fin":
		recorrido = largo - objeto.ancho / 2.0
	else:
		recorrido = largo / 2.0
	ux, uy = (fin[0] - inicio[0]) / largo, (fin[1] - inicio[1]) / largo
	adentro = separacion + objeto.fondo / 2.0
	objeto.x = inicio[0] + ux * recorrido + dx * adentro
	objeto.y = inicio[1] + uy * recorrido + dy * adentro
	objeto.rumbo = hacia_dentro
	return _terminar(entorno, planta, objeto, catalogo, paso_minimo, forzar)


def colocar_en_esquina(
	entorno: Entorno,
	planta: Planta,
	espacio: Espacio,
	tipo: str | Objeto,
	catalogo: Catalogo,
	esquina: str,
	variante: str | None = None,
	nombre: str = "",
	paso_minimo: float = PASO_MINIMO,
	forzar: bool = False,
) -> Colocacion:
	"""Coloca un objeto en una esquina (noreste, noroeste, sureste, suroeste).

	Queda con la espalda en la pared norte o sur y el costado en la este u oeste.
	"""
	if esquina not in ESQUINAS:
		return Colocacion(
			None,
			[
				_aviso(
					"error",
					"sin_lado",
					_("«{esquina}» no es una esquina.").format(esquina=esquina),
					None,
					planta,
					_("Elija noreste, noroeste, sureste o suroeste."),
				)
			],
		)
	lado, alineacion = ESQUINAS[esquina]
	return colocar_contra_pared(
		entorno,
		planta,
		espacio,
		tipo,
		catalogo,
		lado,
		alineacion=alineacion,
		variante=variante,
		nombre=nombre,
		paso_minimo=paso_minimo,
		forzar=forzar,
	)


def caja_de(elemento: Any, catalogo: Catalogo | None = None) -> tuple[float, float, float, float]:
	"""Caja envolvente de cualquier elemento con posición (objeto, espacio, puerta, punto…)."""
	if isinstance(elemento, Objeto):
		return geo.caja(catalogo.huella(elemento) if catalogo else elemento.huella_caja())
	if isinstance(elemento, (Espacio, ZonaSuelo)):
		return geo.caja(elemento.contorno)
	if isinstance(elemento, (Abertura, Pared)):
		return geo.caja((elemento.a, elemento.b))
	if hasattr(elemento, "x") and hasattr(elemento, "y"):
		return elemento.x, elemento.y, elemento.x, elemento.y
	raise TypeError(_("El elemento no tiene posición."))


def colocar_junto_a(
	entorno: Entorno,
	planta: Planta,
	referencia: Any,
	tipo: str | Objeto,
	catalogo: Catalogo,
	lado: str,
	separacion: float = 0.0,
	rumbo: float | None = None,
	variante: str | None = None,
	nombre: str = "",
	paso_minimo: float = PASO_MINIMO,
	forzar: bool = False,
) -> Colocacion:
	"""Coloca un objeto al norte, sur, este u oeste de otro elemento, a ``separacion`` metros.

	Queda centrado respecto al elemento de referencia. Si no se da ``rumbo``
	toma el del objeto de referencia (dos muebles en fila miran igual).
	"""
	if isinstance(referencia, str):
		referencia = entorno.elemento(referencia)
	try:
		objeto = _crear(catalogo, tipo, variante, nombre)
	except KeyError:
		return _no_existe(tipo, planta)
	if lado not in LADOS or referencia is None:
		return Colocacion(
			None,
			[
				_aviso(
					"error",
					"sin_lado",
					_("No se puede colocar junto a ese elemento por el lado «{lado}».").format(lado=lado),
					None,
					planta,
					_("Indique un elemento que exista y un lado: norte, sur, este u oeste."),
				)
			],
		)
	x0, y0, x1, y1 = caja_de(referencia, catalogo)
	centro = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
	objeto.rumbo = geo.normalizar_rumbo(rumbo if rumbo is not None else (referencia.rumbo if isinstance(referencia, Objeto) else 0.0))
	direccion = RUMBO_DE_LADO[lado]
	dx, dy = geo.vector_rumbo(direccion)
	borde = {"norte": y1, "sur": -y0, "este": x1, "oeste": -x0}[lado]
	# El espacio es el del sitio donde va a quedar el objeto: junto a una puerta, el del lado pedido.
	hasta_el_borde = {"norte": y1 - centro[1], "sur": centro[1] - y0, "este": x1 - centro[0], "oeste": centro[0] - x0}[lado]
	sonda = geo.punto_a_distancia(centro, direccion, hasta_el_borde + separacion + 0.05)
	espacio = planta.espacio_en(sonda[0], sonda[1], incluir_macizos=False)
	if espacio is None:
		espacio = planta.espacio_en(centro[0], centro[1], incluir_macizos=False)
	if espacio is not None:
		libre_a_lo_largo = geo.extension_en_rumbo(espacio.contorno, direccion)[1] - borde - separacion
		extremos = geo.extension_en_rumbo(espacio.contorno, direccion + 90.0)
		libre_de_traves = extremos[1] - extremos[0]
	else:
		libre_a_lo_largo = libre_de_traves = math.inf
	# ¿El ancho del objeto queda a lo largo de la dirección pedida o de través?
	ancho_a_lo_largo = 45.0 < abs(geo.diferencia_rumbos(objeto.rumbo, direccion)) < 135.0
	ancho_libre, fondo_libre = (libre_a_lo_largo, libre_de_traves) if ancho_a_lo_largo else (libre_de_traves, libre_a_lo_largo)
	if not catalogo.ajustar_objeto(objeto, ancho_libre, fondo_libre):
		return _no_cabe(objeto, planta, espacio, ancho_libre, fondo_libre)
	objeto.x, objeto.y = 0.0, 0.0
	hx0, hy0, hx1, hy1 = geo.caja(catalogo.huella(objeto))
	mitad = (hy1 - hy0) / 2.0 if lado in ("norte", "sur") else (hx1 - hx0) / 2.0
	avance = borde + separacion + mitad
	if lado in ("norte", "sur"):
		objeto.x, objeto.y = centro[0], dy * avance
	else:
		objeto.x, objeto.y = dx * avance, centro[1]
	if espacio is not None and espacio.cerrado:
		# Centrado respecto a un mueble pegado a la pared se saldría por ella: se desliza hacia dentro.
		ex0, ey0, ex1, ey1 = espacio.caja()
		if lado in ("norte", "sur"):
			mitad_traves = (hx1 - hx0) / 2.0
			objeto.x = min(max(objeto.x, ex0 + mitad_traves), max(ex1 - mitad_traves, ex0 + mitad_traves))
		else:
			mitad_traves = (hy1 - hy0) / 2.0
			objeto.y = min(max(objeto.y, ey0 + mitad_traves), max(ey1 - mitad_traves, ey0 + mitad_traves))
	return _terminar(entorno, planta, objeto, catalogo, paso_minimo, forzar)


def _libre_desde(espacio: Espacio, punto: Punto, rumbo: float) -> float:
	"""Metros libres desde un punto hasta el borde del espacio andando con ese rumbo."""
	choque = geo.rayo_contra_segmentos(punto, rumbo, espacio.lados())
	return choque[0] if choque else math.inf


def colocar_en_punto(
	entorno: Entorno,
	planta: Planta,
	tipo: str | Objeto,
	catalogo: Catalogo,
	x: float,
	y: float,
	rumbo: float = 0.0,
	variante: str | None = None,
	nombre: str = "",
	paso_minimo: float = PASO_MINIMO,
	forzar: bool = False,
) -> Colocacion:
	"""Coloca un objeto centrado en un punto (el «colocar aquí» del modo recorrido).

	Si con sus medidas no cabe ahí, se encoge hasta lo que dejan libres las
	paredes alrededor del punto; si ni al mínimo cabe, no se coloca.
	"""
	try:
		objeto = _crear(catalogo, tipo, variante, nombre)
	except KeyError:
		return _no_existe(tipo, planta)
	objeto.x, objeto.y, objeto.rumbo = float(x), float(y), geo.normalizar_rumbo(rumbo)
	espacio = planta.espacio_en(x, y, incluir_macizos=False)
	if espacio is None:
		return Colocacion(None, comprobar(entorno, planta, objeto, catalogo, paso_minimo))
	de_traves = geo.extension_en_rumbo(espacio.contorno, rumbo + 90.0)
	a_lo_largo = geo.extension_en_rumbo(espacio.contorno, rumbo)
	ancho_libre, fondo_libre = de_traves[1] - de_traves[0], a_lo_largo[1] - a_lo_largo[0]
	if not catalogo.ajustar_objeto(objeto, ancho_libre, fondo_libre):
		return _no_cabe(objeto, planta, espacio, ancho_libre, fondo_libre)
	if espacio.cerrado and not geo.poligono_contiene(espacio.contorno, catalogo.huella(objeto)):
		# No cabe centrado ahí: el hueco real es el doble de lo que hay hasta la pared más cercana en cada eje.
		ancho_libre = 2.0 * min(_libre_desde(espacio, (x, y), rumbo + 90.0), _libre_desde(espacio, (x, y), rumbo - 90.0))
		fondo_libre = 2.0 * min(_libre_desde(espacio, (x, y), rumbo), _libre_desde(espacio, (x, y), rumbo + 180.0))
		objeto.variante = ""
		if not catalogo.ajustar_objeto(objeto, ancho_libre, fondo_libre):
			return _no_cabe(objeto, planta, espacio, ancho_libre, fondo_libre)
	return _terminar(entorno, planta, objeto, catalogo, paso_minimo, forzar)


# ── Amueblado asistido ───────────────────────────────────────────────────────


@dataclass(frozen=True)
class _Mueble:
	"""Un mueble de una receta: cómo buscarlo y dónde intentar ponerlo."""

	palabras: tuple[str, ...]
	modo: str = "pared"  # pared | esquina | centro | junto | filas
	junto_a: int = -1  # índice en la receta del mueble al que acompaña (modo «junto»)
	cantidad: int = 1  # cuántos, en modo «filas»
	# Solo en los usos con contexto (``CONTEXTOS``): la función que tiene que tener el objeto, si importa.
	funcion: str = ""


@dataclass(frozen=True)
class _Contexto:
	"""Dónde se buscan los muebles de un uso nuevo: estancias de la clasificación y ámbito.

	Con más de dos mil objetos, buscar «banco» sin más da un banco de calle
	para una sala de espera. Los usos que tienen contexto buscan primero entre
	los objetos clasificados en sus estancias y solo si no hay ninguno miran
	en todo el catálogo, y entonces exigiendo que el nombre o una etiqueta
	coincida exactamente.
	"""

	estancias: tuple[str, ...]
	ambito: str | None = "interior"


USOS: dict[str, tuple[_Mueble, ...]] = {
	"dormitorio": (
		_Mueble(("cama",)),
		_Mueble(("mesilla", "mesita"), "junto", 0),
		_Mueble(("armario", "ropero")),
		_Mueble(("escritorio", "mesa")),
		_Mueble(("silla",), "junto", 3),
	),
	"salon": (
		_Mueble(("sofa",)),
		_Mueble(("television", "televisor", "mueble de television", "tele")),
		_Mueble(("mesa baja", "mesa de centro", "mesa"), "centro"),
		_Mueble(("sillon", "butaca"), "esquina"),
		_Mueble(("estanteria", "libreria")),
	),
	"cocina": (
		_Mueble(("frigorifico", "nevera"), "esquina"),
		_Mueble(("encimera",)),
		_Mueble(("cocina", "vitroceramica", "fogones")),
		_Mueble(("fregadero",)),
		_Mueble(("lavavajillas", "lavadora")),
		_Mueble(("mesa",), "centro"),
		_Mueble(("silla", "taburete"), "junto", 5),
	),
	"bano": (
		_Mueble(("inodoro", "vater", "retrete")),
		_Mueble(("lavabo",)),
		_Mueble(("ducha", "banera"), "esquina"),
		_Mueble(("bide",)),
	),
	"aula": (
		_Mueble(("pizarra",)),
		_Mueble(("mesa del profesor", "mesa de profesor", "escritorio"), "pared"),
		_Mueble(("pupitre", "mesa de alumno", "mesa"), "filas", cantidad=12),
		_Mueble(("armario", "estanteria"), "esquina"),
		_Mueble(("papelera",), "esquina"),
	),
	"oficina": (
		_Mueble(("escritorio", "mesa de oficina", "mesa")),
		_Mueble(("silla de oficina", "silla"), "junto", 0),
		_Mueble(("archivador", "cajonera"), "esquina"),
		_Mueble(("estanteria", "armario")),
		_Mueble(("papelera",), "esquina"),
	),
	# ── Usos que se apoyan en la clasificación (ver ``CONTEXTOS``) ──
	"sala_espera": (
		_Mueble(("bancada", "sillas de espera"), funcion="asiento"),
		_Mueble(("bancada", "sillas de espera", "banco"), funcion="asiento"),
		_Mueble(("pantalla de turnos", "pantalla"), funcion="senalizacion"),
		_Mueble(("gestor de turnos", "dispensador de turno", "turnos"), "esquina"),
		_Mueble(("maquina expendedora", "maquina de cafe"), "esquina", funcion="pago"),
		_Mueble(("planta",), "esquina", funcion="vegetacion"),
		_Mueble(("papelera",), "esquina"),
	),
	"consulta": (
		_Mueble(("mesa de consulta", "mesa"), funcion="mesa"),
		_Mueble(("silla", "sillas"), "junto", 0, funcion="asiento"),
		_Mueble(("camilla",), funcion="equipo_medico"),
		_Mueble(("lavamanos", "lavabo"), "esquina", funcion="sanitario"),
		_Mueble(("bascula", "tallimetro"), "esquina"),
		_Mueble(("contenedor", "papelera"), "esquina", funcion="residuos"),
	),
	"habitacion_hospital": (
		_Mueble(("cama",), funcion="descanso"),
		_Mueble(("mesilla",), "junto", 0),
		_Mueble(("sillon", "butaca"), "esquina", funcion="asiento"),
		_Mueble(("armario",), funcion="almacenaje"),
		_Mueble(("portasueros", "pie de gotero"), "junto", 0),
		_Mueble(("lavamanos", "lavabo"), "esquina", funcion="sanitario"),
	),
	"aseo_adaptado": (
		_Mueble(("inodoro", "vater"), funcion="sanitario"),
		_Mueble(("lavabo",), funcion="sanitario"),
		_Mueble(("plato de ducha", "ducha"), "esquina", funcion="sanitario"),
		_Mueble(("barra", "asidero"), funcion="ayuda_tecnica"),
		_Mueble(("asiento de ducha", "banqueta de ducha"), "esquina", funcion="asiento"),
		_Mueble(("espejo",)),
	),
	"bar": (
		_Mueble(("barra",), funcion="mostrador"),
		_Mueble(("taburete",), "junto", 0, funcion="asiento"),
		_Mueble(("mesa",), "centro", funcion="mesa"),
		_Mueble(("silla",), "junto", 2, funcion="asiento"),
		_Mueble(("tragaperras", "maquina"), "esquina", funcion="juego"),
		_Mueble(("botellero",), funcion="almacenaje"),
		_Mueble(("papelera", "cubo"), "esquina"),
	),
	"restaurante": (
		_Mueble(("mesa de restaurante", "mesa"), "centro", funcion="mesa"),
		_Mueble(("silla de restaurante", "silla"), "junto", 0, funcion="asiento"),
		_Mueble(("banco corrido", "banco"), funcion="asiento"),
		_Mueble(("mesa corrida", "mesa"), funcion="mesa"),
		_Mueble(("aparador", "mueble de cubiertos"), funcion="almacenaje"),
		_Mueble(("atril de reservas", "atril"), "esquina"),
		_Mueble(("trona",), "esquina"),
	),
	"habitacion_hotel": (
		_Mueble(("cama",), funcion="descanso"),
		_Mueble(("armario",), funcion="almacenaje"),
		_Mueble(("escritorio", "tocador"), funcion="mesa"),
		_Mueble(("silla", "butaca"), "junto", 2, funcion="asiento"),
		_Mueble(("minibar", "nevera"), "esquina"),
		_Mueble(("portamaletas",), "esquina"),
	),
	"recepcion": (
		_Mueble(("mostrador de recepcion", "mostrador"), funcion="mostrador"),
		_Mueble(("sofa",), funcion="asiento"),
		_Mueble(("butaca", "sillon"), "esquina", funcion="asiento"),
		_Mueble(("mesa de centro", "mesa"), "centro", funcion="mesa"),
		_Mueble(("planta",), "esquina", funcion="vegetacion"),
		_Mueble(("expositor de folletos", "folletos"), "esquina"),
		_Mueble(("perchero",), "esquina"),
	),
	"biblioteca": (
		_Mueble(("mostrador de prestamo", "mostrador"), funcion="mostrador"),
		_Mueble(("estanteria",), funcion="almacenaje"),
		_Mueble(("estanteria",), funcion="almacenaje"),
		_Mueble(("mesa de lectura", "mesa"), "centro", funcion="mesa"),
		_Mueble(("silla",), "junto", 3, funcion="asiento"),
		_Mueble(("catalogo", "puesto de consulta"), "esquina"),
		_Mueble(("papelera",), "esquina"),
	),
	"gimnasio": (
		_Mueble(("cinta de correr", "cinta"), funcion="maquina"),
		_Mueble(("bicicleta estatica", "bicicleta"), funcion="maquina"),
		_Mueble(("eliptica",), funcion="maquina"),
		_Mueble(("mancuernero", "mancuernas"), funcion="almacenaje"),
		_Mueble(("banco plano", "banco"), "centro", funcion="deporte"),
		_Mueble(("espejo",)),
		_Mueble(("fuente", "dispensador de papel"), "esquina"),
	),
	"vestuario": (
		_Mueble(("taquillas",), funcion="almacenaje"),
		_Mueble(("banco",), funcion="asiento"),
		_Mueble(("duchas", "ducha"), "esquina", funcion="sanitario"),
		_Mueble(("perchas", "percha"), funcion="almacenaje"),
		_Mueble(("secamanos", "secador"), "esquina"),
		_Mueble(("bascula",), "esquina"),
	),
	"garaje": (
		_Mueble(("coche", "turismo"), funcion="vehiculo"),
		_Mueble(("estanteria",), "esquina", funcion="almacenaje"),
		_Mueble(("columna",), "esquina", funcion="estructura"),
		_Mueble(("bicicletas", "bicis"), funcion="almacenaje"),
		_Mueble(("neumaticos",), "esquina"),
		_Mueble(("extintor",), "esquina"),
	),
	"portal": (
		_Mueble(("buzones",), funcion="comunicacion"),
		_Mueble(("banco",), funcion="asiento"),
		_Mueble(("jardinera", "planta"), funcion="vegetacion"),
		_Mueble(("tablon", "tablon de anuncios"), funcion="senalizacion"),
		_Mueble(("espejo",)),
		_Mueble(("boca de incendio", "extintor"), "esquina", funcion="seguridad"),
	),
	"anden": (
		_Mueble(("banco",), funcion="asiento"),
		_Mueble(("asiento abatible", "asientos"), funcion="asiento"),
		_Mueble(("panel", "pantalla"), funcion="senalizacion"),
		_Mueble(("maquina de billetes", "maquina"), "esquina", funcion="pago"),
		_Mueble(("columna",), "centro", funcion="estructura"),
		_Mueble(("papelera",), "esquina", funcion="residuos"),
		_Mueble(("extintor",), "esquina"),
	),
	"parque_infantil": (
		_Mueble(("columpio",), funcion="juego"),
		_Mueble(("tobogan",), funcion="juego"),
		_Mueble(("balancin de muelle", "balancin"), "esquina", funcion="juego"),
		_Mueble(("arenero",), "centro", funcion="juego"),
		_Mueble(("banco",), funcion="asiento"),
		_Mueble(("papelera",), "esquina"),
	),
}

# Usos que buscan sus muebles con la clasificación: uso → estancias (y ámbito) donde mirar primero.
# Los seis usos de siempre no están aquí: se buscan como siempre, para que sus propuestas no cambien.
CONTEXTOS: dict[str, _Contexto] = {
	"sala_espera": _Contexto(("sala_espera",)),
	"consulta": _Contexto(("consulta",)),
	"habitacion_hospital": _Contexto(("habitacion_hospital",)),
	"aseo_adaptado": _Contexto(("aseo_adaptado",)),
	"bar": _Contexto(("barra", "sala_restaurante")),
	"restaurante": _Contexto(("sala_restaurante",)),
	"habitacion_hotel": _Contexto(("habitacion_hotel",)),
	"recepcion": _Contexto(("recepcion", "vestibulo")),
	"biblioteca": _Contexto(("sala_lectura",)),
	"gimnasio": _Contexto(("sala_musculacion",)),
	"vestuario": _Contexto(("vestuario",)),
	"garaje": _Contexto(("garaje", "plaza_aparcamiento"), None),
	"portal": _Contexto(("portal",), None),
	"anden": _Contexto(("anden",), None),
	"parque_infantil": _Contexto(("zona_juegos",), None),
}

# Nombre visible de cada uso, para quien lo ofrezca en una lista.
NOMBRES_USOS: dict[str, str] = {
	"dormitorio": N_("Dormitorio"),
	"salon": N_("Salón"),
	"cocina": N_("Cocina"),
	"bano": N_("Baño"),
	"aula": N_("Aula"),
	"oficina": N_("Oficina"),
	"sala_espera": N_("Sala de espera"),
	"consulta": N_("Consulta médica"),
	"habitacion_hospital": N_("Habitación de hospital"),
	"aseo_adaptado": N_("Aseo adaptado"),
	"bar": N_("Bar"),
	"restaurante": N_("Restaurante"),
	"habitacion_hotel": N_("Habitación de hotel"),
	"recepcion": N_("Recepción"),
	"biblioteca": N_("Biblioteca"),
	"gimnasio": N_("Gimnasio"),
	"vestuario": N_("Vestuario"),
	"garaje": N_("Garaje"),
	"portal": N_("Portal"),
	"anden": N_("Andén"),
	"parque_infantil": N_("Parque infantil"),
}


def _coincide(definicion: DefObjeto, clave: str, exacta: bool) -> bool:
	"""True si el id, el nombre o una etiqueta de la ficha son ``clave`` (o, sin ``exacta``, la contienen como palabra)."""
	nombres = {sin_acentos(definicion.id.replace("_", " ").replace("-", " ")), sin_acentos(definicion.nombre)}
	nombres.update(sin_acentos(e) for e in definicion.etiquetas)
	if clave in nombres:
		return True
	if exacta:
		return False
	return any(f" {clave} " in f" {nombre} " for nombre in nombres)


def _buscar_en_contexto(catalogo: Catalogo, mueble: _Mueble, contexto: _Contexto, preferidos: Sequence[str] = ()) -> DefObjeto | None:
	"""Mejor objeto de un mueble para un uso con contexto.

	Primero, entre los objetos clasificados en las estancias del uso (y con
	la función pedida, si la hay), el más relevante y común cuyo nombre o
	etiqueta contenga la palabra. Si en esas estancias no hay ninguno, en
	todo el catálogo, pero solo uno cuyo nombre o etiqueta sea exactamente la
	palabra: mejor no poner nada que poner algo de otro sitio.
	"""
	orden = {id_complemento: puesto for puesto, id_complemento in enumerate(preferidos)}
	funcion = mueble.funcion or None
	for palabra in mueble.palabras:
		clave = sin_acentos(palabra)
		candidatos = catalogo.buscar_avanzado(palabra, estancia=contexto.estancias, funcion=funcion, ambito=contexto.ambito)
		if orden:
			candidatos.sort(key=lambda definicion: orden.get(definicion.complemento, len(orden)))
		elegido = next((d for d in candidatos if _coincide(d, clave, exacta=True)), None) or next(
			(d for d in candidatos if _coincide(d, clave, exacta=False)), None
		)
		if elegido is not None:
			return elegido
	for palabra in mueble.palabras:
		clave = sin_acentos(palabra)
		candidatos = catalogo.buscar_avanzado(palabra, funcion=funcion, ambito=contexto.ambito, orden="frecuencia")
		elegido = next((d for d in candidatos if _coincide(d, clave, exacta=True)), None)
		if elegido is not None:
			return elegido
	return None


def _buscar_mueble(catalogo: Catalogo, palabras: tuple[str, ...], preferidos: Sequence[str] = ()) -> DefObjeto | None:
	"""Mejor objeto de interior para unas palabras: primero coincidencia exacta de id o etiqueta.

	``preferidos`` son identificadores de complemento: a igualdad de
	coincidencia gana el objeto del complemento que esté antes en esa lista
	(los pupitres del complemento de colegio antes que una mesa de casa).
	"""
	orden = {id_complemento: puesto for puesto, id_complemento in enumerate(preferidos)}
	for palabra in palabras:
		clave = sin_acentos(palabra)
		candidatos = catalogo.buscar(palabra, ambito="interior")
		if orden:
			# La ordenación es estable: dentro de cada complemento se conserva el orden por nombre.
			candidatos.sort(key=lambda definicion: orden.get(definicion.complemento, len(orden)))
		for definicion in candidatos:
			nombres = {sin_acentos(definicion.id.replace("_", " ").replace("-", " ")), sin_acentos(definicion.nombre)}
			nombres.update(sin_acentos(e) for e in definicion.etiquetas)
			if clave in nombres:
				return definicion
		for definicion in candidatos:
			if (
				clave in sin_acentos(definicion.nombre).split()
				or clave in sin_acentos(definicion.id).replace("_", " ").replace("-", " ").split()
			):
				return definicion
	return None


def _mejor_intento(planta: Planta, intentos: list[Callable[[], Colocacion]]) -> Objeto | None:
	"""Prueba varias colocaciones y deja puesta la primera sin ningún aviso.

	Si todas tienen algún aviso, se queda con la que menos tenga, siempre que
	no tape una puerta; si ninguna vale, no deja nada.
	"""
	reserva: tuple[int, Objeto] | None = None
	for intento in intentos:
		resultado = intento()
		if not resultado.colocado or resultado.objeto is None:
			continue
		if not resultado.avisos:
			return resultado.objeto
		planta.objetos.remove(resultado.objeto)
		if any(aviso.codigo == "tapa_abertura" for aviso in resultado.avisos):
			continue
		if reserva is None or len(resultado.avisos) < reserva[0]:
			reserva = (len(resultado.avisos), resultado.objeto)
	if reserva is not None:
		planta.objetos.append(reserva[1])
		return reserva[1]
	return None


def _intentos(
	entorno: Entorno,
	planta: Planta,
	espacio: Espacio,
	catalogo: Catalogo,
	tipo: str,
	mueble: _Mueble,
	indice: int,
	vecino: Objeto | None,
	paso_minimo: float,
) -> list[Callable[[], Colocacion]]:
	"""Colocaciones que merece la pena probar para un mueble de la receta, de la mejor a la peor."""
	# Se empieza cada mueble por una pared distinta para repartirlos por la habitación.
	paredes = [LADOS[(indice + giro) % 4] for giro in range(4)]
	nombres = list(ESQUINAS)
	esquinas = [nombres[(indice + giro) % 4] for giro in range(4)]

	def contra(lado: str, alineacion: str) -> Callable[[], Colocacion]:
		return lambda: colocar_contra_pared(entorno, planta, espacio, tipo, catalogo, lado, alineacion, paso_minimo=paso_minimo)

	def esquina(nombre: str) -> Callable[[], Colocacion]:
		return lambda: colocar_en_esquina(entorno, planta, espacio, tipo, catalogo, nombre, paso_minimo=paso_minimo)

	def junto(referencia: Objeto, lado: str, separacion: float) -> Callable[[], Colocacion]:
		return lambda: colocar_junto_a(entorno, planta, referencia, tipo, catalogo, lado, separacion, paso_minimo=paso_minimo)

	contra_paredes = [contra(lado, alineacion) for lado in paredes for alineacion in ("centro", "inicio", "fin")]
	en_esquinas = [esquina(nombre) for nombre in esquinas]
	if mueble.modo == "junto" and vecino is not None:
		# Un asiento va delante de su mesa; lo demás (una mesilla), a los lados.
		delante = geo.lado_cardinal(vecino.rumbo)
		a_los_lados = [lado for lado in LADOS if lado != delante]
		es_asiento = any(palabra.startswith(("silla", "taburete")) for palabra in mueble.palabras)
		orden = [delante, *a_los_lados] if es_asiento else [*a_los_lados, delante]
		return [junto(vecino, lado, 0.05 if es_asiento else 0.0) for lado in orden] + en_esquinas
	if mueble.modo == "centro":
		centro = espacio.centro()
		return [
			lambda: colocar_en_punto(entorno, planta, tipo, catalogo, centro[0], centro[1], 0.0, paso_minimo=paso_minimo),
			*contra_paredes,
		]
	if mueble.modo == "esquina":
		return en_esquinas + contra_paredes
	return contra_paredes + en_esquinas


def amueblar_espacio(
	entorno: Entorno,
	planta: Planta,
	espacio: Espacio,
	uso: str,
	catalogo: Catalogo,
	paso_minimo: float = PASO_MINIMO,
	aplicar: bool = True,
	preferidos: Sequence[str] = (),
) -> list[Objeto]:
	"""Lo mismo que ``_amueblar_espacio`` dentro de un lote de comprobaciones.

	Cada mueble que se prueba se comprueba contra las paredes y puertas de la
	planta; en el lote se calculan una sola vez (amueblar no las mueve).
	"""
	with lote_de_comprobaciones():
		return _amueblar_espacio(entorno, planta, espacio, uso, catalogo, paso_minimo, aplicar, preferidos)


def _amueblar_espacio(
	entorno: Entorno,
	planta: Planta,
	espacio: Espacio,
	uso: str,
	catalogo: Catalogo,
	paso_minimo: float = PASO_MINIMO,
	aplicar: bool = True,
	preferidos: Sequence[str] = (),
) -> list[Objeto]:
	"""Propone una disposición razonable para un espacio según su uso.

	``uso``: una clave de ``USOS`` (``NOMBRES_USOS`` dice cómo se llama cada
	uno). Los seis de siempre (dormitorio, salon, cocina, bano, aula y
	oficina) buscan los muebles típicos por id, nombre y etiquetas; los demás
	(sala de espera, consulta, habitación de hospital, aseo adaptado, bar,
	restaurante, habitación de hotel, recepción, biblioteca, gimnasio,
	vestuario, garaje, portal, andén y parque infantil) los buscan además por
	su clasificación (``CONTEXTOS``). En todos se reparten por las paredes y
	esquinas sin tapar puertas ni solaparlos, ajustados al hueco y dejando el
	paso libre. Solo usa lo que haya instalado: sin complementos devuelve una
	lista vacía.

	Con ``aplicar=False`` los objetos se devuelven sin dejarlos en la planta,
	para que el profesional revise la propuesta antes de aceptarla.

	``preferidos`` son identificadores de complemento, por orden de
	preferencia: cuando varios complementos tienen el mismo mueble se usa el
	del primero de la lista (``("colegio",)`` para amueblar un aula).
	"""
	receta = USOS.get(uso)
	if receta is None:
		raise ValueError(_("No se sabe amueblar un espacio como «{uso}». Usos: {usos}.").format(uso=uso, usos=", ".join(USOS)))
	if catalogo.vacio or len(espacio.contorno) < 3:
		return []
	colocados: list[Objeto] = []
	por_indice: dict[int, Objeto] = {}
	contexto = CONTEXTOS.get(uso)
	for indice, mueble in enumerate(receta):
		definicion = (
			_buscar_en_contexto(catalogo, mueble, contexto, preferidos)
			if contexto
			else _buscar_mueble(catalogo, mueble.palabras, preferidos)
		)
		if definicion is None:
			continue
		tipo = definicion.tipo
		if mueble.modo == "filas":
			colocados.extend(_en_filas(entorno, planta, espacio, tipo, catalogo, mueble.cantidad, paso_minimo))
			continue
		intentos = _intentos(entorno, planta, espacio, catalogo, tipo, mueble, indice, por_indice.get(mueble.junto_a), paso_minimo)
		puesto = _mejor_intento(planta, intentos)
		if puesto is not None:
			colocados.append(puesto)
			por_indice[indice] = puesto
	if not aplicar:
		for objeto in colocados:
			planta.objetos.remove(objeto)
	log.info("Amueblado de «%s» como %s: %s objetos", espacio.nombre, uso, len(colocados))
	return colocados


def _en_filas(
	entorno: Entorno, planta: Planta, espacio: Espacio, tipo: str, catalogo: Catalogo, cantidad: int, paso_minimo: float
) -> list[Objeto]:
	"""Reparte varios objetos iguales en filas (los pupitres de un aula), dejando pasillos."""
	definicion = catalogo.objeto(tipo)
	if definicion is None:
		return []
	ancho, fondo = definicion.rango("ancho")[1], definicion.rango("fondo")[1]
	x0, y0, x1, y1 = espacio.caja()
	margen = paso_minimo + 0.4
	paso_x, paso_y = ancho + paso_minimo, fondo + paso_minimo + 0.4
	columnas = int((x1 - x0 - 2 * margen + paso_minimo) / paso_x)
	filas = int((y1 - y0 - 2 * margen + paso_minimo) / paso_y)
	if columnas < 1 or filas < 1:
		return []
	ancho_total = columnas * ancho + (columnas - 1) * paso_minimo
	inicio_x = (x0 + x1) / 2.0 - ancho_total / 2.0 + ancho / 2.0
	inicio_y = y1 - margen - 1.0 - fondo / 2.0
	puestos: list[Objeto] = []
	for fila in range(filas):
		for columna in range(columnas):
			if len(puestos) >= cantidad:
				return puestos
			x = inicio_x + columna * paso_x
			y = inicio_y - fila * paso_y
			if y - fondo / 2.0 < y0 + margen - 1e-6:
				continue
			resultado = colocar_en_punto(entorno, planta, tipo, catalogo, x, y, 0.0, paso_minimo=paso_minimo)
			if resultado.colocado and resultado.objeto is not None:
				if resultado.avisos:
					planta.objetos.remove(resultado.objeto)
				else:
					puestos.append(resultado.objeto)
	return puestos
