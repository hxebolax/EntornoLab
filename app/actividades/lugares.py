"""Lugares de una actividad: de un id o una posición a un punto con nombre, y lo que se deduce del entorno.

Las actividades nombran los sitios como los nombra el profesional: «la
cocina» (el id de un espacio), «el frigorífico» (el de un objeto) o un punto
marcado en el plano. Aquí se convierte todo eso en un ``Lugar`` con el que el
motor puede trabajar y se saca del entorno lo que las actividades generan
solas: pistas con relaciones espaciales reales, puntos libres donde dejar un
premio, rutas de dificultad comparable para un examen y el punto por el que
se vuelve a entrar tras cruzar una salida.

Nada de esto ejecuta código del entorno ni lo modifica.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from typing import Any

from app.core.i18n import _
from app.dominio import geometria as geo
from app.dominio.geometria import Punto
from app.dominio.modelo import Abertura, Conector, Entorno, Espacio, FuenteSonido, Objeto, Planta, Posicion, Referencia
from app.motor.mundo import InfoAbertura, Mundo
from app.motor.navegacion import Navegador, Ruta

log = logging.getLogger(__name__)

RADIO_LLEGADA = 1.2
# Tipos de espacio que no se proponen como destino ni como sitio para un premio.
TIPOS_NO_DESTINO = frozenset({"calzada", "paso_peatones", "cabina", "escalera"})
# Separación mínima a paredes y muebles de un punto que el programa elige solo.
HOLGURA_PUNTO = 0.45

Terna = tuple[str, float, float]


@dataclass
class Lugar:
	"""Un sitio del entorno al que una actividad manda ir, o del que parte.

	Si es un espacio (``clase`` «espacio») se llega al entrar en él; si es un
	punto, un objeto o una referencia, al acercarse a menos de ``radio``.
	"""

	planta: str
	x: float
	y: float
	nombre: str = ""
	clase: str = "punto"
	elemento_id: str = ""
	radio: float = RADIO_LLEGADA
	rumbo: float = 0.0

	@property
	def terna(self) -> Terna:
		"""(planta, x, y), que es como el motor nombra un lugar."""
		return self.planta, self.x, self.y

	@property
	def punto(self) -> Punto:
		"""El punto (x, y)."""
		return self.x, self.y

	def posicion(self, rumbo: float | None = None) -> Posicion:
		"""La posición completa, mirando a ``rumbo`` (o al rumbo propio del lugar)."""
		return Posicion(self.planta, self.x, self.y, self.rumbo if rumbo is None else rumbo)

	def alcanzado(self, sesion: Any) -> bool:
		"""Si el alumno está ahora en este lugar."""
		jugador = sesion.jugador
		if jugador.planta != self.planta or jugador.modo != "andando":
			return False
		if self.clase == "espacio":
			return (sesion.movimiento.espacio_id or "") == self.elemento_id
		if self.clase == "objeto":
			info = sesion.mundo.objeto(self.elemento_id)
			if info is not None:
				return info.distancia(jugador.x, jugador.y) <= self.radio and objeto_a_mano(
					sesion.mundo, jugador.planta, jugador.punto, info
				)
		return math.hypot(self.x - jugador.x, self.y - jugador.y) <= self.radio

	def a_dato(self) -> dict[str, Any]:
		"""Resumen para el resultado y los registros (tipos básicos)."""
		return {"id": self.elemento_id, "nombre": self.nombre, "planta": self.planta, "x": round(self.x, 2), "y": round(self.y, 2)}


def punto_de_espacio(espacio: Espacio) -> Punto:
	"""Un punto que está seguro dentro del espacio: su centro o, en una sala en ele, uno de sus triángulos."""
	if len(espacio.contorno) < 3:
		return espacio.contorno[0] if espacio.contorno else (0.0, 0.0)
	centro = espacio.centro()
	if geo.punto_en_poligono(centro, espacio.contorno, borde=False):
		return centro
	mejor: tuple[float, Punto] | None = None
	for triangulo in geo.triangular(espacio.contorno):
		candidato = geo.centroide(triangulo)
		area = geo.area(triangulo)
		if mejor is None or area > mejor[0]:
			mejor = (area, candidato)
	return mejor[1] if mejor is not None else centro


def nombre_de_punto(entorno: Entorno, planta_id: str, x: float, y: float) -> str:
	"""Nombre hablado de un punto suelto: el del espacio que lo contiene."""
	planta = entorno.planta(planta_id)
	espacio = planta.espacio_en(x, y, incluir_macizos=False) if planta is not None else None
	if espacio is not None and espacio.nombre:
		return espacio.nombre
	return _("un punto del plano")


def resolver_lugar(entorno: Entorno, valor: Any, radio: float = RADIO_LLEGADA) -> Lugar | None:
	"""Convierte lo que guarda una actividad (un id, una posición, una terna) en un ``Lugar``; None si no se entiende.

	Admite el id de un espacio, abertura, objeto, referencia, fuente o
	conector; un diccionario ``{"planta", "x", "y"}`` (con ``nombre`` y
	``rumbo`` opcionales) o uno con ``{"id": ...}``; una ``Posicion`` y una
	terna ``(planta, x, y)``.
	"""
	if valor is None or valor == "":
		return None
	if isinstance(valor, Lugar):
		return valor
	if isinstance(valor, Posicion):
		return Lugar(
			valor.planta,
			float(valor.x),
			float(valor.y),
			nombre_de_punto(entorno, valor.planta, valor.x, valor.y),
			rumbo=float(valor.rumbo),
			radio=radio,
		)
	if isinstance(valor, dict):
		if valor.get("id") and "x" not in valor:
			return resolver_lugar(entorno, str(valor["id"]), radio)
		try:
			planta_id, x, y = str(valor["planta"]), float(valor["x"]), float(valor["y"])
			rumbo = float(valor.get("rumbo", 0.0) or 0.0)
		except KeyError, TypeError, ValueError:
			return None
		if entorno.planta(planta_id) is None or not (math.isfinite(x) and math.isfinite(y)):
			return None
		nombre = str(valor.get("nombre") or "") or nombre_de_punto(entorno, planta_id, x, y)
		return Lugar(planta_id, x, y, nombre, radio=radio, rumbo=rumbo)
	if isinstance(valor, (list, tuple)) and len(valor) >= 3:
		return resolver_lugar(entorno, {"planta": valor[0], "x": valor[1], "y": valor[2]}, radio)
	if not isinstance(valor, str):
		return None
	encontrado = entorno.buscar(valor)
	if encontrado is None:
		return None
	planta, elemento = encontrado
	if isinstance(elemento, Espacio) and planta is not None:
		x, y = punto_de_espacio(elemento)
		return Lugar(planta.id, x, y, elemento.nombre or valor, "espacio", elemento.id, radio)
	if isinstance(elemento, Abertura) and planta is not None:
		x, y = elemento.centro()
		return Lugar(planta.id, x, y, elemento.nombre or _("la puerta"), "abertura", elemento.id, radio)
	if isinstance(elemento, Objeto) and planta is not None:
		return Lugar(planta.id, elemento.x, elemento.y, elemento.nombre or valor, "objeto", elemento.id, max(radio, 0.9))
	if isinstance(elemento, (Referencia, FuenteSonido)) and planta is not None:
		clase = "referencia" if isinstance(elemento, Referencia) else "fuente"
		return Lugar(planta.id, elemento.x, elemento.y, elemento.nombre or valor, clase, elemento.id, max(radio, 1.5))
	if isinstance(elemento, Conector):
		if elemento.tramos:
			boca = elemento.tramos[0].desde
			return Lugar(boca.planta, boca.x, boca.y, elemento.nombre or valor, "conector", elemento.id, max(radio, 1.5))
		if elemento.paradas:
			puerta = elemento.paradas[0].puerta
			return Lugar(puerta.planta, puerta.x, puerta.y, elemento.nombre or valor, "conector", elemento.id, max(radio, 1.5))
	return None


# ── Espacios y puntos libres ─────────────────────────────────────────────────


def espacios_jugables(entorno: Entorno, plantas: list[str] | None = None, con_paso: bool = False) -> list[tuple[Planta, Espacio]]:
	"""Espacios a los que tiene sentido mandar al alumno, en el orden del entorno.

	Quedan fuera los macizos, el terreno de fondo de un mapa importado y, si
	no se pide ``con_paso``, calzadas, pasos de peatones, cabinas y cajas de escalera.
	"""
	lista: list[tuple[Planta, Espacio]] = []
	for planta in entorno.plantas:
		if plantas and planta.id not in plantas:
			continue
		for espacio in planta.espacios:
			if espacio.macizo or len(espacio.contorno) < 3 or espacio.datos.get("terreno_base"):
				continue
			if not con_paso and espacio.tipo in TIPOS_NO_DESTINO:
				continue
			lista.append((planta, espacio))
	return lista


def punto_esta_libre(mundo: Mundo, planta_id: str, x: float, y: float, holgura: float = HOLGURA_PUNTO) -> bool:
	"""Si en ese punto cabe una persona: dentro de un espacio, fuera de los muebles y separado de las paredes."""
	if mundo.espacio_en(planta_id, x, y) is None:
		return False
	if mundo.dentro_de_objeto(planta_id, x, y) is not None:
		return False
	return mundo.distancia_libre(planta_id, x, y, holgura) >= holgura - 1e-9


def puntos_libres(mundo: Mundo, planta_id: str, espacio: Espacio, paso: float = 0.5, holgura: float = HOLGURA_PUNTO) -> list[Punto]:
	"""Puntos del espacio donde cabe una persona, en rejilla y en orden estable (para que el azar con semilla sea reproducible)."""
	x0, y0, x1, y1 = espacio.caja()
	puntos: list[Punto] = []
	columnas = max(1, int((x1 - x0) / paso))
	filas = max(1, int((y1 - y0) / paso))
	# En la calle una acera de 80 metros no necesita 300 candidatos: se aclara la rejilla.
	salto = max(1, int(math.sqrt(columnas * filas / 400.0)))
	for i in range(0, columnas + 1, salto):
		for j in range(0, filas + 1, salto):
			x, y = x0 + (i + 0.5) * paso, y0 + (j + 0.5) * paso
			if x >= x1 or y >= y1:
				continue
			espacio_ahi = mundo.espacio_en(planta_id, x, y)
			if espacio_ahi is None or espacio_ahi.id != espacio.id:
				continue
			if punto_esta_libre(mundo, planta_id, x, y, holgura):
				puntos.append((round(x, 2), round(y, 2)))
	return puntos


def punto_libre_en(mundo: Mundo, planta_id: str, espacio: Espacio, azar: random.Random | None = None) -> Punto | None:
	"""Un punto libre del espacio: el más céntrico o, con ``azar``, uno cualquiera. None si no cabe nadie."""
	candidatos = puntos_libres(mundo, planta_id, espacio)
	if not candidatos:
		candidatos = puntos_libres(mundo, planta_id, espacio, paso=0.25, holgura=0.3)
	if not candidatos:
		return None
	if azar is not None:
		return azar.choice(candidatos)
	centro = punto_de_espacio(espacio)
	return min(candidatos, key=lambda p: (round(geo.distancia(p, centro), 3), p))


def objeto_a_mano(mundo: Mundo, planta_id: str, punto: Punto, info: Any) -> bool:
	"""Si entre un punto y un objeto no hay una pared ni una puerta cerrada (otros muebles no cuentan)."""
	cercano = min((geo.proyeccion_sobre_segmento(punto, a, b) for a, b in geo.lados(info.huella)), key=lambda p: geo.distancia(punto, p))
	return not any(seg.clase != "objeto" for _t, seg in mundo.cortes(planta_id, punto, cercano, "paso"))


def punto_de_acceso(mundo: Mundo, objeto_id: str) -> Punto | None:
	"""Punto libre desde el que se puede usar un objeto: delante de uno de sus lados y en su misma habitación.

	El centro de un mueble no sirve como destino (no se puede pisar) y, si
	está pegado a una pared, el sitio libre más cercano a su centro puede
	caer en la habitación de al lado. Aquí se busca el punto de verdad: a un
	paso de uno de sus lados, sin pared por medio. None si está encajonado.

	La ruta del navegador hasta el centro del mueble ya llega por su lado de
	la pared (``Navegador._preferida``); esto sigue haciendo falta porque un
	``Lugar`` necesita un punto que se pueda pisar: la llegada por radio, la
	baliza y la validación miden contra él, no contra el centro del mueble.
	"""
	info = mundo.objeto(objeto_id)
	if info is None or len(info.huella) < 3:
		return None
	planta_id = info.planta_id
	centro = (info.objeto.x, info.objeto.y)
	propio = mundo.espacio_en(planta_id, centro[0], centro[1])
	candidatos: list[tuple[float, float, Punto]] = []
	for a, b in geo.lados(info.huella):
		largo = geo.distancia(a, b)
		if largo < 1e-6:
			continue
		medio = geo.punto_medio(a, b)
		nx, ny = (b[1] - a[1]) / largo, -(b[0] - a[0]) / largo
		if (medio[0] - centro[0]) * nx + (medio[1] - centro[1]) * ny < 0.0:
			nx, ny = -nx, -ny
		for separacion in (0.45, 0.6, 0.8):
			punto = (round(medio[0] + nx * separacion, 3), round(medio[1] + ny * separacion, 3))
			espacio = mundo.espacio_en(planta_id, punto[0], punto[1])
			if espacio is None or (propio is not None and espacio.id != propio.id):
				continue
			if not punto_esta_libre(mundo, planta_id, punto[0], punto[1], 0.3) or not objeto_a_mano(mundo, planta_id, punto, info):
				continue
			# Se prefiere el lado más ancho (el frente de un armario) y, en él, lo más cerca posible.
			candidatos.append((-round(largo, 2), separacion, punto))
			break
	if not candidatos:
		return None
	return min(candidatos)[2]


def lugar_de_espacio(mundo: Mundo, planta: Planta, espacio: Espacio) -> Lugar:
	"""El espacio como destino, apuntando a un punto suyo donde cabe una persona."""
	punto = punto_libre_en(mundo, planta.id, espacio) or punto_de_espacio(espacio)
	return Lugar(planta.id, punto[0], punto[1], espacio.nombre or espacio.id, "espacio", espacio.id)


def lugares_de_espacios(mundo: Mundo, nav: Navegador, origen: Any, plantas: list[str] | None = None) -> list[Lugar]:
	"""Un lugar por cada espacio jugable al que se puede llegar andando desde ``origen``."""
	alcanzables = nav.espacios_alcanzables(origen)
	lugares: list[Lugar] = []
	for planta, espacio in espacios_jugables(mundo.entorno, plantas):
		if alcanzables and espacio.id not in alcanzables:
			continue
		lugares.append(lugar_de_espacio(mundo, planta, espacio))
	return lugares


# ── Relaciones espaciales ────────────────────────────────────────────────────


def rumbo_entre_espacios(a: Espacio, b: Espacio) -> float:
	"""Rumbo desde el centro de un espacio al de otro."""
	return geo.rumbo_entre(punto_de_espacio(a), punto_de_espacio(b))


def _nombre_generico(espacio: Espacio, exterior: bool) -> str:
	"""«la habitación», «el pasillo», «el lugar»: cómo llamar a un espacio sin decir su nombre."""
	if espacio.tipo == "pasillo":
		return _("el pasillo")
	if espacio.tipo in ("acera", "plaza", "parque", "sendero", "exterior") or exterior:
		return _("el lugar")
	return _("la habitación")


def vecinos_de(nav: Navegador, espacio_id: str) -> list[str]:
	"""Ids de los espacios a los que se pasa directamente desde uno, sin repetir y en orden estable."""
	vistos: list[str] = []
	for enlace in nav.enlaces(espacio_id):
		if enlace.destino and enlace.destino != espacio_id and enlace.destino not in vistos:
			vistos.append(enlace.destino)
	return vistos


def pista_de_lugar(entorno: Entorno, nav: Navegador, lugar: Lugar, detalle: int = 1, dentro_de: str = "") -> str:
	"""Redacta una pista sobre dónde está un lugar, con relaciones reales del entorno.

	``detalle`` 1 lo sitúa respecto de un espacio vecino sin nombrarlo («en la
	habitación que queda al norte de la cocina»); 2 dice el espacio; 3 añade
	en qué punto del espacio está o dentro de qué objeto.
	"""
	planta = entorno.planta(lugar.planta)
	if planta is None:
		return ""
	espacio = planta.espacio_en(lugar.x, lugar.y, incluir_macizos=False)
	if espacio is None:
		return _("Está fuera de todos los espacios con nombre.")
	nombre = espacio.nombre or _nombre_generico(espacio, planta.exterior)
	contenedor = entorno.elemento(dentro_de) if dentro_de else None
	if detalle >= 3:
		centro = punto_de_espacio(espacio)
		if geo.distancia(centro, lugar.punto) < 1.0:
			donde = _("hacia el centro")
		else:
			donde = _("en la parte {punto}").format(punto=geo.punto_cardinal(geo.rumbo_entre(centro, lugar.punto)))
		if isinstance(contenedor, Objeto) and contenedor.nombre:
			return _("Está en {espacio}, {donde}, dentro de {objeto}.").format(espacio=nombre, donde=donde, objeto=contenedor.nombre)
		return _("Está en {espacio}, {donde}.").format(espacio=nombre, donde=donde)
	if detalle == 2:
		if isinstance(contenedor, Objeto):
			return _("Está en {espacio}, dentro de algo que se puede abrir o tocar.").format(espacio=nombre)
		return _("Está en {espacio}.").format(espacio=nombre)
	# Detalle 1: respecto de otro espacio con nombre, sin nombrar este. Se prefiere una habitación que lo toque
	# (comparten pared, aunque no haya puerta entre ellas) y que quede bien alineada con un punto cardinal: «al este del salón».
	enlazados = set(vecinos_de(nav, espacio.id))
	candidatos: list[tuple[int, float, str, Espacio]] = []
	for otro in planta.espacios:
		if otro.id == espacio.id or not otro.nombre or otro.macizo or otro.datos.get("terreno_base") or len(otro.contorno) < 3:
			continue
		toca = (
			geo.cajas_se_tocan(otro.caja(), espacio.caja(), 1.0) and geo.distancia_entre_poligonos(otro.contorno, espacio.contorno) <= 1.0
		)
		if not toca and otro.id not in enlazados:
			continue
		peso = 1 if otro.tipo in ("pasillo", "calzada", "paso_peatones", "escalera") else 0
		rumbo = rumbo_entre_espacios(otro, espacio)
		desvio = min(abs(geo.diferencia_rumbos(eje, rumbo)) for eje in (0.0, 90.0, 180.0, 270.0))
		candidatos.append((peso, round(desvio, 1), otro.id, otro))
	if not candidatos:
		# Un espacio aislado: se sitúa respecto del espacio con nombre más cercano de la planta.
		for otro in planta.espacios:
			if otro.id != espacio.id and otro.nombre and not otro.macizo and not otro.datos.get("terreno_base") and len(otro.contorno) >= 3:
				candidatos.append((2, round(geo.distancia(punto_de_espacio(otro), punto_de_espacio(espacio)), 2), otro.id, otro))
	if not candidatos:
		return _("Está en {espacio}.").format(espacio=nombre)
	candidatos.sort(key=lambda dato: dato[:3])
	referencia = candidatos[0][3]
	punto = geo.punto_cardinal(rumbo_entre_espacios(referencia, espacio))
	return _("Está en {generico} que queda al {punto} de {referencia}.").format(
		generico=_nombre_generico(espacio, planta.exterior), punto=punto, referencia=referencia.nombre
	)


def relaciones_cardinales(entorno: Entorno, tolerancia: float = 30.0) -> list[tuple[Espacio, str, Espacio]]:
	"""Ternas (referencia, lado, espacio): «espacio» queda claramente al norte, este, sur u oeste de «referencia».

	Solo se dan relaciones entre espacios jugables de la misma planta que se
	tocan o casi (menos de un metro entre sus contornos) y cuyo rumbo de
	centro a centro se aparta menos de ``tolerancia`` grados del eje: son las
	que una persona que conoce el lugar puede contestar sin dudar.
	"""
	ternas: list[tuple[Espacio, str, Espacio]] = []
	for planta in entorno.plantas:
		espacios = [e for p, e in espacios_jugables(entorno, [planta.id]) if e.nombre]
		for referencia in espacios:
			for otro in espacios:
				if otro is referencia:
					continue
				if not geo.cajas_se_tocan(referencia.caja(), otro.caja(), 1.0):
					continue
				if geo.distancia_entre_poligonos(referencia.contorno, otro.contorno) > 1.0:
					continue
				rumbo = rumbo_entre_espacios(referencia, otro)
				lado = geo.lado_cardinal(rumbo)
				eje = {"norte": 0.0, "este": 90.0, "sur": 180.0, "oeste": 270.0}[lado]
				if abs(geo.diferencia_rumbos(eje, rumbo)) <= tolerancia:
					ternas.append((referencia, lado, otro))
	return ternas


# ── Salidas ──────────────────────────────────────────────────────────────────


def punto_interior_de_abertura(mundo: Mundo, info: InfoAbertura, distancia: float = 0.9) -> tuple[Punto, float] | None:
	"""Punto justo dentro del entorno junto a una abertura, y el rumbo con el que se entra por ella.

	Sirve para devolver al alumno adentro después de cruzar una salida.
	"""
	for signo in (1.0, -1.0):
		x = info.centro[0] + info.normal[0] * distancia * signo
		y = info.centro[1] + info.normal[1] * distancia * signo
		if mundo.espacio_en(info.planta_id, x, y) is not None:
			return (x, y), geo.rumbo_entre(info.centro, (x, y))
	return None


def abertura_cruzada(sesion: Any) -> InfoAbertura | None:
	"""La abertura por la que el alumno acaba de salir del entorno (está fuera de todo espacio), o None."""
	jugador = sesion.jugador
	if jugador.modo != "andando" or sesion.mundo.espacio_en(jugador.planta, jugador.x, jugador.y) is not None:
		return None
	cercanas = sesion.mundo.aberturas_cerca(jugador.planta, jugador.x, jugador.y, 1.5)
	return cercanas[0][1] if cercanas else None


def salidas_ordenadas(nav: Navegador, origen: Any) -> list[tuple[str, float]]:
	"""(id de abertura, metros de camino) de cada salida alcanzable, de la más cercana a la más lejana."""
	return [(salida.abertura.id, salida.distancia) for salida in nav.salidas(origen)]


# ── Rutas comparables ────────────────────────────────────────────────────────


@dataclass
class RutaCandidata:
	"""Un par origen-destino con lo que mide su camino más corto."""

	origen: Lugar
	destino: Lugar
	longitud: float
	giros: int
	plantas: int


def rutas_candidatas(nav: Navegador, lugares: list[Lugar], minimo_m: float = 4.0, maximo: int = 14) -> list[RutaCandidata]:
	"""Rutas entre los lugares dados, una por pareja (el sentido lo decide después quien las use).

	Se limita el número de lugares para que generar un examen no tarde: con
	catorce lugares son noventa y una rutas.
	"""
	usados = lugares[:maximo]
	candidatas: list[RutaCandidata] = []
	for i, origen in enumerate(usados):
		for destino in usados[i + 1 :]:
			ruta: Ruta | None = nav.ruta(origen.terna, destino.terna)
			if ruta is None or ruta.longitud < minimo_m:
				continue
			candidatas.append(RutaCandidata(origen, destino, ruta.longitud, ruta.giros(), len(ruta.plantas())))
	return candidatas


def elegir_comparables(candidatas: list[RutaCandidata], cuantas: int, azar: random.Random) -> list[RutaCandidata]:
	"""Elige ``cuantas`` rutas de longitud y número de giros parecidos.

	Se ordenan por longitud y se toma el tramo de la lista, del doble de
	tamaño que lo pedido, cuyas longitudes y giros varían menos; de él se
	sortean las rutas con ``azar`` y a cada una se le sortea el sentido. Con
	la misma semilla sale siempre lo mismo.
	"""
	if not candidatas:
		return []
	ordenadas = sorted(candidatas, key=lambda c: (round(c.longitud, 2), c.origen.elemento_id, c.destino.elemento_id))
	cuantas = max(1, min(cuantas, len(ordenadas)))
	ventana = min(len(ordenadas), max(cuantas, cuantas * 2))
	mejor_inicio = 0
	mejor_coste = math.inf
	mediana = ordenadas[len(ordenadas) // 2].longitud
	for inicio in range(0, len(ordenadas) - ventana + 1):
		tramo = ordenadas[inicio : inicio + ventana]
		largos = [c.longitud for c in tramo]
		giros = [c.giros for c in tramo]
		media = sum(largos) / len(largos)
		dispersion = (max(largos) - min(largos)) / max(media, 1.0) + 0.15 * (max(giros) - min(giros))
		# A igualdad, las rutas de longitud media: ni las triviales ni las de punta a punta.
		coste = dispersion + 0.1 * abs(media - mediana) / max(mediana, 1.0)
		if coste < mejor_coste - 1e-9:
			mejor_coste = coste
			mejor_inicio = inicio
	tramo = ordenadas[mejor_inicio : mejor_inicio + ventana]
	elegidas = azar.sample(tramo, cuantas)
	resultado: list[RutaCandidata] = []
	for candidata in elegidas:
		if azar.random() < 0.5:
			candidata = RutaCandidata(candidata.destino, candidata.origen, candidata.longitud, candidata.giros, candidata.plantas)
		resultado.append(candidata)
	return resultado
