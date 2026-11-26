"""Geometría plana en metros: x hacia el este, y hacia el norte, rumbo 0 = norte y horario.

Todas las funciones son puras (no guardan estado ni dependen del modelo), para
que el editor, la validación y el motor compartan exactamente las mismas
cuentas y se puedan probar sin ventana.

Los polígonos son listas de puntos ``(x, y)`` sin repetir el primero al final.
Los solapes y las contenciones se calculan por ÁREA de intersección (triangulando
los polígonos), no por cruces de lados: así dos muebles que solo se tocan por
un lado, o un armario pegado a la pared, no cuentan como solapados aunque sus
bordes coincidan, que es el caso más corriente al amueblar.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Sequence

from app.core.i18n import N_, _

Punto = tuple[float, float]
Poligono = list[Punto]
Tramo2 = tuple[Punto, Punto]

# Por debajo de esta longitud (1 décima de milímetro) dos puntos son el mismo.
EPSILON = 1e-9
# Área (m²) por debajo de la cual dos figuras «solo se tocan»: 1 cm².
AREA_MINIMA = 1e-4

# Los puntos cardinales se guardan en español (N_) y se dicen en el idioma elegido.
PUNTOS = (
	N_("norte"),
	N_("noreste"),
	N_("este"),
	N_("sureste"),
	N_("sur"),
	N_("suroeste"),
	N_("oeste"),
	N_("noroeste"),
)

# Rumbo de cada lado con nombre: lo usan el editor y la colocación sin ver.
RUMBO_DE_LADO: dict[str, float] = {
	"norte": 0.0,
	"noreste": 45.0,
	"este": 90.0,
	"sureste": 135.0,
	"sur": 180.0,
	"suroeste": 225.0,
	"oeste": 270.0,
	"noroeste": 315.0,
}


# ── Rumbos ───────────────────────────────────────────────────────────────────


def normalizar_rumbo(grados: float) -> float:
	"""Lleva un ángulo al intervalo [0, 360)."""
	return grados % 360.0


def rumbo(dx: float, dy: float) -> float:
	"""Rumbo en grados (0 = norte, 90 = este) del vector (dx este, dy norte)."""
	return math.degrees(math.atan2(dx, dy)) % 360.0


def rumbo_entre(a: Punto, b: Punto) -> float:
	"""Rumbo que hay que tomar para ir de ``a`` a ``b``."""
	return rumbo(b[0] - a[0], b[1] - a[1])


def diferencia_rumbos(a: float, b: float) -> float:
	"""Ángulo de ``b`` respecto de ``a``, entre -180 y 180 (positivo = a la derecha)."""
	return (b - a + 180.0) % 360.0 - 180.0


def vector_rumbo(grados: float) -> Punto:
	"""Vector unitario (dx, dy) que apunta hacia ``grados``."""
	radianes = math.radians(grados)
	return math.sin(radianes), math.cos(radianes)


def punto_a_distancia(origen: Punto, grados: float, distancia_m: float) -> Punto:
	"""Punto al que se llega andando ``distancia_m`` desde ``origen`` con rumbo ``grados``."""
	dx, dy = vector_rumbo(grados)
	return origen[0] + dx * distancia_m, origen[1] + dy * distancia_m


def punto_cardinal(grados: float) -> str:
	"""Nombre del punto cardinal más cercano («noreste»), en el idioma elegido."""
	return _(PUNTOS[round(grados % 360.0 / 45.0) % 8])


def lado_cardinal(grados: float) -> str:
	"""Clave sin traducir (norte, este, sur, oeste) del lado principal más cercano."""
	return ("norte", "este", "sur", "oeste")[round(grados % 360.0 / 90.0) % 4]


# ── Puntos y segmentos ───────────────────────────────────────────────────────


def distancia(a: Punto, b: Punto) -> float:
	"""Distancia en línea recta entre dos puntos."""
	return math.hypot(b[0] - a[0], b[1] - a[1])


def punto_medio(a: Punto, b: Punto) -> Punto:
	"""Punto medio del segmento ab."""
	return (a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0


def parametro_segmento(p: Punto, a: Punto, b: Punto, limitar: bool = True) -> float:
	"""Posición (0 en ``a``, 1 en ``b``) de la proyección de ``p`` sobre el segmento."""
	dx, dy = b[0] - a[0], b[1] - a[1]
	largo2 = dx * dx + dy * dy
	if largo2 < EPSILON * EPSILON:
		return 0.0
	t = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / largo2
	return max(0.0, min(1.0, t)) if limitar else t


def proyeccion_sobre_segmento(p: Punto, a: Punto, b: Punto) -> Punto:
	"""Punto del segmento ab más cercano a ``p``."""
	t = parametro_segmento(p, a, b)
	return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def distancia_punto_segmento(p: Punto, a: Punto, b: Punto) -> float:
	"""Distancia de ``p`` al punto más cercano del segmento ab."""
	return distancia(p, proyeccion_sobre_segmento(p, a, b))


def lado_de(p: Punto, a: Punto, b: Punto) -> float:
	"""Producto vectorial: positivo si ``p`` queda a la IZQUIERDA de a→b, negativo a la derecha."""
	return (b[0] - a[0]) * (p[1] - a[1]) - (b[1] - a[1]) * (p[0] - a[0])


def corte_segmentos(a: Punto, b: Punto, c: Punto, d: Punto) -> Punto | None:
	"""Punto de corte de los segmentos ab y cd; None si no se cortan o son paralelos."""
	rx, ry = b[0] - a[0], b[1] - a[1]
	sx, sy = d[0] - c[0], d[1] - c[1]
	denominador = rx * sy - ry * sx
	if abs(denominador) < 1e-12:
		return None
	qx, qy = c[0] - a[0], c[1] - a[1]
	t = (qx * sy - qy * sx) / denominador
	u = (qx * ry - qy * rx) / denominador
	if -1e-9 <= t <= 1 + 1e-9 and -1e-9 <= u <= 1 + 1e-9:
		return a[0] + t * rx, a[1] + t * ry
	return None


def corte_rectas(a: Punto, b: Punto, c: Punto, d: Punto) -> Punto | None:
	"""Punto de corte de las rectas (infinitas) ab y cd; None si son paralelas."""
	rx, ry = b[0] - a[0], b[1] - a[1]
	sx, sy = d[0] - c[0], d[1] - c[1]
	denominador = rx * sy - ry * sx
	if abs(denominador) < 1e-12:
		return None
	t = ((c[0] - a[0]) * sy - (c[1] - a[1]) * sx) / denominador
	return a[0] + t * rx, a[1] + t * ry


def segmentos_se_cruzan(a: Punto, b: Punto, c: Punto, d: Punto) -> bool:
	"""True si ab y cd se atraviesan de verdad (tocarse por un extremo no cuenta)."""
	d1 = lado_de(c, a, b)
	d2 = lado_de(d, a, b)
	d3 = lado_de(a, c, d)
	d4 = lado_de(b, c, d)
	return d1 * d2 < -1e-12 and d3 * d4 < -1e-12


def distancia_segmentos(a: Punto, b: Punto, c: Punto, d: Punto) -> float:
	"""Distancia mínima entre los segmentos ab y cd (0 si se cortan)."""
	if corte_segmentos(a, b, c, d) is not None:
		return 0.0
	return min(
		distancia_punto_segmento(a, c, d),
		distancia_punto_segmento(b, c, d),
		distancia_punto_segmento(c, a, b),
		distancia_punto_segmento(d, a, b),
	)


def intervalo_sobre_segmento(a: Punto, b: Punto, p: Punto, q: Punto, tolerancia: float = 0.05) -> tuple[float, float] | None:
	"""Tramo (en metros desde ``a``) que el segmento pq ocupa sobre ab, o None si no está sobre él.

	Sirve para saber qué trozo de una pared quita una puerta: pq tiene que
	estar pegado a la recta de ab (a menos de ``tolerancia``) y compartir con
	ab algo más que un punto.
	"""
	largo = distancia(a, b)
	if largo < EPSILON:
		return None
	for punto in (p, q):
		if abs(lado_de(punto, a, b)) / largo > tolerancia:
			return None
	d0 = parametro_segmento(p, a, b, limitar=False) * largo
	d1 = parametro_segmento(q, a, b, limitar=False) * largo
	if d0 > d1:
		d0, d1 = d1, d0
	d0 = max(0.0, d0)
	d1 = min(largo, d1)
	if d1 - d0 < 1e-6:
		return None
	return d0, d1


def recortar_segmento(a: Punto, b: Punto, intervalos: Iterable[tuple[float, float]]) -> list[Tramo2]:
	"""Trozos del segmento ab que quedan al quitarle ``intervalos`` (metros desde ``a``).

	Es la operación con la que una pared pierde los tramos de sus puertas.
	Los intervalos pueden venir desordenados y solaparse.
	"""
	largo = distancia(a, b)
	if largo < EPSILON:
		return []
	huecos = sorted((max(0.0, min(i)), min(largo, max(i))) for i in intervalos)
	ux, uy = (b[0] - a[0]) / largo, (b[1] - a[1]) / largo
	trozos: list[Tramo2] = []
	cursor = 0.0
	for inicio, fin in huecos:
		if fin <= cursor:
			continue
		if inicio - cursor > 1e-6:
			trozos.append(((a[0] + ux * cursor, a[1] + uy * cursor), (a[0] + ux * inicio, a[1] + uy * inicio)))
		cursor = max(cursor, fin)
	if largo - cursor > 1e-6:
		trozos.append(((a[0] + ux * cursor, a[1] + uy * cursor), (b[0], b[1])))
	return trozos


def rayo_contra_segmentos(
	origen: Punto, grados: float, segmentos: Sequence[Tramo2], alcance: float = math.inf
) -> tuple[float, Punto, int] | None:
	"""Primer segmento que encuentra un rayo: (distancia, punto, índice) o None.

	Es la base de «qué tengo delante» y de la sonda: se lanza desde el alumno
	con su rumbo y se queda con el obstáculo más cercano dentro de ``alcance``.
	"""
	dx, dy = vector_rumbo(grados)
	mejor: tuple[float, Punto, int] | None = None
	for indice, (a, b) in enumerate(segmentos):
		sx, sy = b[0] - a[0], b[1] - a[1]
		denominador = dx * sy - dy * sx
		if abs(denominador) < 1e-12:
			continue
		qx, qy = a[0] - origen[0], a[1] - origen[1]
		t = (qx * sy - qy * sx) / denominador
		u = (qx * dy - qy * dx) / denominador
		if t < 0.0 or t > alcance or u < -1e-9 or u > 1 + 1e-9:
			continue
		if mejor is None or t < mejor[0]:
			mejor = (t, (origen[0] + dx * t, origen[1] + dy * t), indice)
	return mejor


# ── Líneas ───────────────────────────────────────────────────────────────────


def longitud_linea(linea: Sequence[Punto]) -> float:
	"""Longitud total de una línea quebrada."""
	return sum(distancia(linea[i], linea[i + 1]) for i in range(len(linea) - 1))


def punto_en_linea(linea: Sequence[Punto], distancia_m: float) -> tuple[Punto, float]:
	"""(punto, rumbo) a ``distancia_m`` metros del inicio de una línea quebrada."""
	resto = distancia_m
	for i in range(len(linea) - 1):
		tramo = distancia(linea[i], linea[i + 1])
		if resto <= tramo or i == len(linea) - 2:
			t = 0.0 if tramo < EPSILON else max(0.0, min(1.0, resto / tramo))
			a, b = linea[i], linea[i + 1]
			return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), rumbo_entre(a, b)
		resto -= tramo
	return linea[-1], 0.0


def proyeccion_sobre_linea(p: Punto, linea: Sequence[Punto]) -> tuple[Punto, float, int]:
	"""(punto más cercano, distancia a él, índice del tramo) de ``p`` sobre una línea quebrada."""
	mejor: tuple[Punto, float, int] = (linea[0], math.inf, 0)
	for i in range(len(linea) - 1):
		cercano = proyeccion_sobre_segmento(p, linea[i], linea[i + 1])
		d = distancia(p, cercano)
		if d < mejor[1]:
			mejor = (cercano, d, i)
	return mejor


def desplazar_linea(linea: Sequence[Punto], separacion: float) -> list[Punto]:
	"""Línea paralela a ``linea`` a ``separacion`` metros (positivo = a la derecha del sentido de avance).

	Con ella se sacan los bordes de la calzada y de las aceras a partir del
	eje de una calle. En los vértices se une en inglete (se cortan las dos
	paralelas) para que la acera no tenga muescas en las curvas.
	"""
	if len(linea) < 2:
		return list(linea)
	paralelas: list[Tramo2] = []
	for i in range(len(linea) - 1):
		a, b = linea[i], linea[i + 1]
		largo = distancia(a, b)
		if largo < EPSILON:
			continue
		# Normal a la derecha del avance: (dy, -dx).
		nx, ny = (b[1] - a[1]) / largo * separacion, -(b[0] - a[0]) / largo * separacion
		paralelas.append(((a[0] + nx, a[1] + ny), (b[0] + nx, b[1] + ny)))
	if not paralelas:
		return list(linea)
	resultado = [paralelas[0][0]]
	for i in range(len(paralelas) - 1):
		corte = corte_rectas(*paralelas[i], *paralelas[i + 1])
		# Tramos alineados: no hay corte y vale el final del primero.
		resultado.append(corte if corte is not None else paralelas[i][1])
	resultado.append(paralelas[-1][1])
	return resultado


# ── Polígonos: medidas ───────────────────────────────────────────────────────


def area_con_signo(poligono: Sequence[Punto]) -> float:
	"""Área con signo: positiva si el polígono va en sentido antihorario."""
	suma = 0.0
	for i in range(len(poligono)):
		x1, y1 = poligono[i - 1]
		x2, y2 = poligono[i]
		suma += x1 * y2 - x2 * y1
	return suma / 2.0


def area(poligono: Sequence[Punto]) -> float:
	"""Superficie del polígono en metros cuadrados."""
	return abs(area_con_signo(poligono))


def perimetro(poligono: Sequence[Punto]) -> float:
	"""Longitud del contorno cerrado."""
	return sum(distancia(poligono[i - 1], poligono[i]) for i in range(len(poligono)))


def centroide(poligono: Sequence[Punto]) -> Punto:
	"""Centro de gravedad del polígono (la media de los vértices si no tiene área)."""
	if not poligono:
		return 0.0, 0.0
	superficie = cx = cy = 0.0
	for i in range(len(poligono)):
		x1, y1 = poligono[i - 1]
		x2, y2 = poligono[i]
		cruz = x1 * y2 - x2 * y1
		superficie += cruz
		cx += (x1 + x2) * cruz
		cy += (y1 + y2) * cruz
	if abs(superficie) < EPSILON:
		return sum(p[0] for p in poligono) / len(poligono), sum(p[1] for p in poligono) / len(poligono)
	return cx / (3.0 * superficie), cy / (3.0 * superficie)


def caja(puntos: Iterable[Punto]) -> tuple[float, float, float, float]:
	"""Caja envolvente (x mínima, y mínima, x máxima, y máxima)."""
	lista = list(puntos)
	if not lista:
		return 0.0, 0.0, 0.0, 0.0
	xs = [p[0] for p in lista]
	ys = [p[1] for p in lista]
	return min(xs), min(ys), max(xs), max(ys)


def cajas_se_tocan(a: tuple[float, float, float, float], b: tuple[float, float, float, float], margen: float = 0.0) -> bool:
	"""True si dos cajas envolventes se solapan o quedan a menos de ``margen``."""
	return a[0] <= b[2] + margen and b[0] <= a[2] + margen and a[1] <= b[3] + margen and b[1] <= a[3] + margen


def es_antihorario(poligono: Sequence[Punto]) -> bool:
	"""True si los vértices giran en sentido antihorario."""
	return area_con_signo(poligono) > 0


def orientar_antihorario(poligono: Sequence[Punto]) -> Poligono:
	"""Devuelve el polígono en sentido antihorario (el que usa todo el modelo)."""
	lista = [(float(p[0]), float(p[1])) for p in poligono]
	if area_con_signo(lista) < 0:
		lista.reverse()
	return lista


def lados(poligono: Sequence[Punto]) -> list[Tramo2]:
	"""Lados del polígono: el lado ``i`` va del vértice ``i`` al ``i + 1``."""
	n = len(poligono)
	return [(poligono[i], poligono[(i + 1) % n]) for i in range(n)]


def es_convexo(poligono: Sequence[Punto]) -> bool:
	"""True si el polígono no tiene entrantes."""
	signo = 0
	n = len(poligono)
	for i in range(n):
		giro = lado_de(poligono[(i + 2) % n], poligono[i], poligono[(i + 1) % n])
		if abs(giro) < 1e-12:
			continue
		actual = 1 if giro > 0 else -1
		if signo and actual != signo:
			return False
		signo = actual
	return True


def es_simple(poligono: Sequence[Punto]) -> bool:
	"""True si el contorno no se corta a sí mismo ni repite vértices.

	Un contorno que se cruza no delimita una habitación: no se sabe qué es
	dentro y qué es fuera, así que la validación lo rechaza.
	"""
	n = len(poligono)
	if n < 3:
		return False
	for i in range(n):
		if distancia(poligono[i], poligono[(i + 1) % n]) < 1e-6:
			return False
	for i in range(n):
		a, b = poligono[i], poligono[(i + 1) % n]
		for j in range(i + 1, n):
			# Los lados vecinos comparten un vértice: eso no es cortarse.
			if j == i or (j + 1) % n == i or (i + 1) % n == j:
				continue
			c, d = poligono[j], poligono[(j + 1) % n]
			if distancia_segmentos(a, b, c, d) < 1e-9:
				return False
	return True


def punto_en_poligono(p: Punto, poligono: Sequence[Punto], borde: bool = True, tolerancia: float = 1e-6) -> bool:
	"""True si ``p`` está dentro del polígono.

	``borde`` decide si un punto justo sobre el contorno cuenta como dentro.
	Con ``borde=False`` y una ``tolerancia`` mayor se pregunta «¿está claramente dentro?».
	"""
	n = len(poligono)
	if n < 3:
		return False
	x, y = p
	# Atajo por la caja: un punto que queda fuera de ella (con la tolerancia y
	# un margen de redondeo) no toca ningún lado ni está dentro. Es la
	# pregunta más frecuente (¿en qué espacio está esto?) y casi siempre la
	# respuesta es «en este no»: así no se mide la distancia a cada lado.
	holgura = (tolerancia if tolerancia > 0.0 else 0.0) + 1e-7
	xs = [punto[0] for punto in poligono]
	if x < min(xs) - holgura or x > max(xs) + holgura:
		return False
	ys = [punto[1] for punto in poligono]
	if y < min(ys) - holgura or y > max(ys) + holgura:
		return False
	return punto_en_poligono_sin_caja(p, poligono, borde, tolerancia)


def punto_en_poligono_sin_caja(p: Punto, poligono: Sequence[Punto], borde: bool = True, tolerancia: float = 1e-6) -> bool:
	"""``punto_en_poligono`` para quien YA sabe que el punto cae dentro de la caja del polígono (ampliada en la tolerancia).

	Lo usa el índice espacial de la planta, que guarda la caja de cada espacio:
	así no se recalcula en cada consulta. Fuera de la caja da lo mismo que
	``punto_en_poligono`` siempre que la caja ya se haya mirado antes.
	"""
	n = len(poligono)
	if n < 3:
		return False
	x, y = p
	# Distancia a cada lado con las MISMAS cuentas que ``distancia_punto_segmento``
	# (proyección limitada al segmento), escritas en línea: llamar a tres
	# funciones por lado era lo que más pesaba al buscar espacios.
	minimo2 = EPSILON * EPSILON
	ax, ay = poligono[-1]
	for bx, by in poligono:
		dx = bx - ax
		dy = by - ay
		largo2 = dx * dx + dy * dy
		if largo2 < minimo2:
			t = 0.0
		else:
			t = ((x - ax) * dx + (y - ay) * dy) / largo2
			t = max(0.0, min(1.0, t))
		if math.hypot(ax + dx * t - x, ay + dy * t - y) <= tolerancia:
			return borde
		ax, ay = bx, by
	dentro = False
	j = n - 1
	for i in range(n):
		xi, yi = poligono[i]
		xj, yj = poligono[j]
		if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
			dentro = not dentro
		j = i
	return dentro


def distancia_punto_poligono(p: Punto, poligono: Sequence[Punto]) -> float:
	"""Distancia de ``p`` al polígono: 0 si está dentro, si no la distancia al borde."""
	if punto_en_poligono(p, poligono):
		return 0.0
	return min(distancia_punto_segmento(p, a, b) for a, b in lados(poligono))


# ── Polígonos: construcción y transformaciones ───────────────────────────────


def rectangulo(x: float, y: float, ancho: float, fondo: float) -> Poligono:
	"""Rectángulo alineado con los ejes desde su esquina suroeste, en sentido antihorario.

	El orden de los lados es fijo y el editor cuenta con él: 0 = sur, 1 = este,
	2 = norte, 3 = oeste.
	"""
	return [(x, y), (x + ancho, y), (x + ancho, y + fondo), (x, y + fondo)]


def girar_punto(p: Punto, centro: Punto, grados: float) -> Punto:
	"""Gira ``p`` alrededor de ``centro`` en el sentido del reloj (como los rumbos)."""
	radianes = math.radians(grados)
	coseno, seno = math.cos(radianes), math.sin(radianes)
	dx, dy = p[0] - centro[0], p[1] - centro[1]
	return centro[0] + dx * coseno + dy * seno, centro[1] - dx * seno + dy * coseno


def girar_poligono(poligono: Sequence[Punto], centro: Punto, grados: float) -> Poligono:
	"""Gira todos los puntos alrededor de ``centro`` en el sentido del reloj."""
	return [girar_punto(p, centro, grados) for p in poligono]


def trasladar(poligono: Sequence[Punto], dx: float, dy: float) -> Poligono:
	"""Desplaza todos los puntos."""
	return [(p[0] + dx, p[1] + dy) for p in poligono]


def rectangulo_girado(cx: float, cy: float, ancho: float, fondo: float, grados: float = 0.0) -> Poligono:
	"""Rectángulo de ``ancho`` × ``fondo`` centrado en (cx, cy) y girado a un rumbo.

	Con rumbo 0 el ancho va de oeste a este y el fondo de sur a norte; el
	frente del objeto mira al norte. Sale en sentido antihorario.
	"""
	mitad_a, mitad_f = ancho / 2.0, fondo / 2.0
	base = [(cx - mitad_a, cy - mitad_f), (cx + mitad_a, cy - mitad_f), (cx + mitad_a, cy + mitad_f), (cx - mitad_a, cy + mitad_f)]
	if abs(grados % 360.0) < 1e-9:
		return base
	return girar_poligono(base, (cx, cy), grados)


def forma_a_mundo(puntos_unidad: Sequence[Punto], cx: float, cy: float, ancho: float, fondo: float, grados: float) -> Poligono:
	"""Lleva una forma definida en el cuadrado 0..1 a su huella real en el mundo.

	En la forma, (0, 0) es la esquina trasera izquierda y (1, 1) la delantera
	derecha mirando el objeto desde detrás; el frente (y = 1) apunta al rumbo.
	"""
	locales = [(cx + (px - 0.5) * ancho, cy + (py - 0.5) * fondo) for px, py in puntos_unidad]
	return orientar_antihorario(girar_poligono(locales, (cx, cy), grados))


def circulo(cx: float, cy: float, radio: float, lados_n: int = 16) -> Poligono:
	"""Polígono regular que aproxima un círculo (antihorario)."""
	return [(cx + radio * math.cos(2 * math.pi * i / lados_n), cy + radio * math.sin(2 * math.pi * i / lados_n)) for i in range(lados_n)]


def recortar_por_semiplano(poligono: Sequence[Punto], a: Punto, b: Punto) -> Poligono:
	"""Parte del polígono que queda a la IZQUIERDA de la recta a→b.

	Es un paso del algoritmo de Sutherland-Hodgman. Sirve para quitarle a una
	acera el trozo que pisa la calzada de la calle que la cruza.
	"""
	resultado: Poligono = []
	n = len(poligono)
	for i in range(n):
		actual, siguiente = poligono[i], poligono[(i + 1) % n]
		lado_actual = lado_de(actual, a, b)
		lado_siguiente = lado_de(siguiente, a, b)
		if lado_actual >= -1e-12:
			resultado.append(actual)
		if (lado_actual > 1e-12 and lado_siguiente < -1e-12) or (lado_actual < -1e-12 and lado_siguiente > 1e-12):
			t = lado_actual / (lado_actual - lado_siguiente)
			resultado.append((actual[0] + (siguiente[0] - actual[0]) * t, actual[1] + (siguiente[1] - actual[1]) * t))
	return _sin_repetidos(resultado)


def _sin_repetidos(poligono: Sequence[Punto]) -> Poligono:
	"""Quita vértices consecutivos repetidos (también el último contra el primero)."""
	limpio: Poligono = []
	for p in poligono:
		if not limpio or distancia(p, limpio[-1]) > 1e-9:
			limpio.append(p)
	if len(limpio) > 1 and distancia(limpio[0], limpio[-1]) <= 1e-9:
		limpio.pop()
	return limpio


# ── Polígonos: intersección, contención y separación ─────────────────────────


def interseccion_convexa(sujeto: Sequence[Punto], recorte: Sequence[Punto]) -> Poligono:
	"""Intersección de ``sujeto`` con un polígono CONVEXO ``recorte`` (Sutherland-Hodgman).

	Devuelve una lista vacía si no comparten superficie.
	"""
	resultado = list(sujeto)
	marco = orientar_antihorario(recorte)
	for a, b in lados(marco):
		if len(resultado) < 3:
			return []
		resultado = recortar_por_semiplano(resultado, a, b)
	return resultado if len(resultado) >= 3 else []


def triangular(poligono: Sequence[Punto]) -> list[Poligono]:
	"""Descompone un polígono simple en triángulos (recorte de orejas).

	Permite tratar habitaciones en ele o con entrantes con las mismas
	operaciones que las convexas: se trocean y se opera triángulo a triángulo.
	"""
	puntos = _sin_repetidos(orientar_antihorario(poligono))
	if len(puntos) < 3:
		return []
	if es_convexo(puntos):
		return [[puntos[0], puntos[i], puntos[i + 1]] for i in range(1, len(puntos) - 1)]
	triangulos: list[Poligono] = []
	pendientes = list(puntos)
	intentos = 0
	while len(pendientes) > 3 and intentos < 10000:
		intentos += 1
		n = len(pendientes)
		oreja = False
		for i in range(n):
			anterior, actual, siguiente = pendientes[i - 1], pendientes[i], pendientes[(i + 1) % n]
			giro = lado_de(siguiente, anterior, actual)
			if giro < -1e-12:
				# Vértice entrante: no puede ser una oreja.
				continue
			if abs(giro) <= 1e-12:
				# Vértice alineado: sobra y se quita sin generar triángulo.
				pendientes.pop(i)
				oreja = True
				break
			triangulo = [anterior, actual, siguiente]
			# Un vértice justo sobre el borde de la oreja también la invalida: si no,
			# la diagonal pasaría por él y el resto dejaría de ser un polígono simple.
			if any(p not in triangulo and punto_en_poligono(p, triangulo, borde=True, tolerancia=1e-9) for p in pendientes):
				continue
			triangulos.append(triangulo)
			pendientes.pop(i)
			oreja = True
			break
		if not oreja:
			# Contorno degenerado: se cierra en abanico para no quedarse en un bucle.
			break
	if len(pendientes) >= 3:
		triangulos.extend([pendientes[0], pendientes[i], pendientes[i + 1]] for i in range(1, len(pendientes) - 1))
	return [t for t in triangulos if area(t) > 1e-12]


def area_interseccion(p: Sequence[Punto], q: Sequence[Punto]) -> float:
	"""Superficie que comparten dos polígonos simples (convexos o no)."""
	if len(p) < 3 or len(q) < 3:
		return 0.0
	if not cajas_se_tocan(caja(p), caja(q)):
		return 0.0
	if es_convexo(q):
		return sum(area(interseccion_convexa(t, q)) for t in triangular(p)) if not es_convexo(p) else area(interseccion_convexa(p, q))
	total = 0.0
	triangulos_q = triangular(q)
	for triangulo_p in triangular(p):
		caja_p = caja(triangulo_p)
		for triangulo_q in triangulos_q:
			if cajas_se_tocan(caja_p, caja(triangulo_q)):
				total += area(interseccion_convexa(triangulo_p, triangulo_q))
	return total


def poligonos_se_solapan(p: Sequence[Punto], q: Sequence[Punto], area_minima: float = AREA_MINIMA) -> bool:
	"""True si dos polígonos comparten superficie (tocarse por un lado no cuenta)."""
	return area_interseccion(p, q) > area_minima


def poligono_contiene(exterior: Sequence[Punto], interior: Sequence[Punto], area_minima: float = AREA_MINIMA) -> bool:
	"""True si ``interior`` cabe entero dentro de ``exterior`` (puede tocar su borde)."""
	superficie = area(interior)
	if superficie <= 0.0:
		return all(punto_en_poligono(punto, exterior) for punto in interior)
	return superficie - area_interseccion(interior, exterior) <= area_minima


def segmento_cruza_poligono(a: Punto, b: Punto, poligono: Sequence[Punto], margen: float = 0.01) -> bool:
	"""True si el segmento ab entra en el interior del polígono (rozar el borde no cuenta)."""
	if len(poligono) >= 1:
		# Un segmento cuya caja no toca la del polígono no puede cruzarlo ni tener puntos dentro.
		x0, y0, x1, y1 = caja(poligono)
		holgura = 1e-7
		if (
			max(a[0], b[0]) < x0 - holgura
			or min(a[0], b[0]) > x1 + holgura
			or max(a[1], b[1]) < y0 - holgura
			or min(a[1], b[1]) > y1 + holgura
		):
			return False
	for c, d in lados(poligono):
		if segmentos_se_cruzan(a, b, c, d):
			return True
	largo = distancia(a, b)
	pasos = max(2, int(largo / 0.1) + 1)
	for i in range(pasos + 1):
		t = i / pasos
		punto = (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t)
		if punto_en_poligono(punto, poligono, borde=False, tolerancia=margen):
			return True
	return False


def distancia_poligono_segmento(poligono: Sequence[Punto], a: Punto, b: Punto) -> float:
	"""Distancia mínima entre un polígono y un segmento (0 si se tocan o el segmento está dentro)."""
	if punto_en_poligono(a, poligono) or punto_en_poligono(b, poligono):
		return 0.0
	return min(distancia_segmentos(a, b, c, d) for c, d in lados(poligono))


def distancia_entre_poligonos(p: Sequence[Punto], q: Sequence[Punto]) -> float:
	"""Hueco mínimo entre dos polígonos: 0 si se tocan o se solapan.

	Es la medida del «paso mínimo»: el hueco más estrecho que queda entre dos
	muebles, o entre un mueble y la pared.
	"""
	if not p or not q:
		return math.inf
	if punto_en_poligono(p[0], q) or punto_en_poligono(q[0], p):
		return 0.0
	mejor = math.inf
	for a, b in lados(p):
		for c, d in lados(q):
			mejor = min(mejor, distancia_segmentos(a, b, c, d))
			if mejor <= 0.0:
				return 0.0
	return mejor


def extension_en_rumbo(poligono: Sequence[Punto], grados: float) -> tuple[float, float]:
	"""(mínimo, máximo) de la proyección del polígono sobre la dirección ``grados``.

	Dice cuánto mide una habitación «de norte a sur» o en cualquier otra
	dirección, que es el hueco disponible para un mueble orientado así.
	"""
	dx, dy = vector_rumbo(grados)
	valores = [p[0] * dx + p[1] * dy for p in poligono]
	return min(valores), max(valores)
