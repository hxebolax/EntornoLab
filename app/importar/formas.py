"""Geometría auxiliar de los importadores: recortar, simplificar y ensanchar líneas.

Los datos de fuera llegan como líneas (el eje de una calle, el trazo de un
plano) y el modelo quiere superficies simples. Estas funciones hacen ese
paso con tolerancia: un polígono que no sirve se devuelve como None para que
el importador lo anote en el informe en lugar de fallar entero.
"""

from __future__ import annotations

import math
from collections.abc import Sequence

from app.dominio import geometria as geo
from app.dominio.geometria import Poligono, Punto

Caja = tuple[float, float, float, float]

# Tolerancias (metros) con las que se va simplificando un eje hasta que su franja sale simple.
_TOLERANCIAS_FRANJA = (0.0, 0.3, 1.0, 3.0)
# Celda (metros) de la rejilla con la que se buscan los edificios vecinos, y holgura
# extra por si una caja crece al ajustar sus medianeras.
_CELDA_MEDIANERAS = 25.0
_HOLGURA_MEDIANERAS = 2.0


def sin_puntos_repetidos(linea: Sequence[Punto], minimo: float = 0.02) -> list[Punto]:
	"""La línea sin puntos consecutivos casi iguales (los datos reales traen nodos duplicados)."""
	resultado: list[Punto] = []
	for punto in linea:
		if not resultado or geo.distancia(resultado[-1], punto) >= minimo:
			resultado.append((float(punto[0]), float(punto[1])))
	return resultado


def simplificar_linea(linea: Sequence[Punto], tolerancia: float) -> list[Punto]:
	"""Quita los vértices que se apartan menos de ``tolerancia`` de la recta (Douglas-Peucker).

	Una calle dibujada con un nodo cada dos metros da franjas con muescas;
	con menos vértices la acera sale limpia y el entorno pesa menos.
	"""
	puntos = list(linea)
	if tolerancia <= 0.0 or len(puntos) < 3:
		return puntos
	conservar = [False] * len(puntos)
	conservar[0] = conservar[-1] = True
	pendientes = [(0, len(puntos) - 1)]
	while pendientes:
		inicio, fin = pendientes.pop()
		peor = 0.0
		indice = -1
		for i in range(inicio + 1, fin):
			d = geo.distancia_punto_segmento(puntos[i], puntos[inicio], puntos[fin])
			if d > peor:
				peor = d
				indice = i
		if indice >= 0 and peor > tolerancia:
			conservar[indice] = True
			pendientes.append((inicio, indice))
			pendientes.append((indice, fin))
	return [p for p, queda in zip(puntos, conservar, strict=True) if queda]


def limpiar_poligono(puntos: Sequence[Punto], tolerancia: float = 0.02) -> Poligono:
	"""Contorno sin el cierre repetido, sin vértices duplicados y sin vértices alineados.

	Quitar los alineados importa: el nodo de un portal parte la fachada en
	dos lados, y una abertura tiene que caer entera sobre un solo lado.
	"""
	limpio = sin_puntos_repetidos(puntos, tolerancia)
	if len(limpio) >= 2 and geo.distancia(limpio[0], limpio[-1]) < tolerancia:
		limpio.pop()
	cambiado = True
	while cambiado and len(limpio) > 3:
		cambiado = False
		for i in range(len(limpio)):
			anterior, actual, siguiente = limpio[i - 1], limpio[i], limpio[(i + 1) % len(limpio)]
			if geo.distancia(anterior, siguiente) < 1e-9:
				continue
			entre = geo.parametro_segmento(actual, anterior, siguiente, limitar=False)
			if 0.0 < entre < 1.0 and geo.distancia_punto_segmento(actual, anterior, siguiente) < tolerancia:
				del limpio[i]
				cambiado = True
				break
	return limpio


def poligono_valido(puntos: Sequence[Punto], area_minima: float = 0.05) -> bool:
	"""True si el contorno sirve como espacio: tres vértices, sin cruces y con superficie."""
	return len(puntos) >= 3 and geo.es_simple(puntos) and geo.area(puntos) >= area_minima


def distancia_en_linea(linea: Sequence[Punto], punto: Punto) -> float:
	"""Metros desde el inicio de la línea hasta el punto de ella más cercano a ``punto``."""
	cercano, _distancia, indice = geo.proyeccion_sobre_linea(punto, linea)
	return geo.longitud_linea(linea[: indice + 1]) + geo.distancia(linea[indice], cercano)


def tramo_de_linea(linea: Sequence[Punto], desde: float, hasta: float) -> list[Punto]:
	"""Trozo de la línea entre dos distancias medidas desde su inicio."""
	total = geo.longitud_linea(linea)
	desde = max(0.0, min(total, desde))
	hasta = max(0.0, min(total, hasta))
	if hasta - desde < 1e-6:
		return []
	resultado: list[Punto] = [geo.punto_en_linea(linea, desde)[0]]
	recorrido = 0.0
	for i in range(len(linea) - 1):
		recorrido += geo.distancia(linea[i], linea[i + 1])
		if desde + 1e-6 < recorrido < hasta - 1e-6:
			resultado.append(linea[i + 1])
	resultado.append(geo.punto_en_linea(linea, hasta)[0])
	return sin_puntos_repetidos(resultado)


def rumbo_en_linea(linea: Sequence[Punto], distancia_m: float) -> float:
	"""Rumbo de avance de la línea a esa distancia de su inicio."""
	return geo.punto_en_linea(linea, distancia_m)[1]


def _paralela(linea: Sequence[Punto], separacion: float) -> list[Punto] | None:
	"""Paralela a la línea, o None si un inglete se dispara (curva demasiado cerrada para ese ancho)."""
	if abs(separacion) < 1e-9:
		return list(linea)
	paralela = geo.desplazar_linea(linea, separacion)
	if len(paralela) != len(linea):
		return None
	limite = abs(separacion) * 3.0 + 0.5
	for original, movido in zip(linea, paralela, strict=True):
		if geo.distancia(original, movido) > limite:
			return None
	return paralela


def franja(linea: Sequence[Punto], desde: float, hasta: float) -> Poligono | None:
	"""Polígono entre dos paralelas a la línea (separaciones con signo: positivo a la derecha del avance).

	Es la forma de una calzada, de una acera o de un sendero a partir de su
	eje. Devuelve None si el resultado no es un polígono simple.
	"""
	puntos = sin_puntos_repetidos(linea, 0.05)
	if len(puntos) < 2 or geo.longitud_linea(puntos) < 0.2:
		return None
	una = _paralela(puntos, desde)
	otra = _paralela(puntos, hasta)
	if una is None or otra is None:
		return None
	poligono = limpiar_poligono(una + otra[::-1], 0.005)
	if not poligono_valido(poligono):
		return None
	return geo.orientar_antihorario(poligono)


def franja_tolerante(linea: Sequence[Punto], desde: float, hasta: float) -> tuple[Poligono | None, bool]:
	"""Como ``franja``, pero si no sale simple simplifica el eje poco a poco.

	Devuelve (polígono, simplificado). El último intento es la recta entre
	los extremos: vale más una calle recta que una calle que falta.
	"""
	base = sin_puntos_repetidos(linea, 0.05)
	for tolerancia in _TOLERANCIAS_FRANJA:
		poligono = franja(simplificar_linea(base, tolerancia), desde, hasta)
		if poligono is not None:
			return poligono, tolerancia > 0.0
	if len(base) >= 2:
		poligono = franja([base[0], base[-1]], desde, hasta)
		if poligono is not None:
			return poligono, True
	return None, True


# ── Recorte a un recuadro ────────────────────────────────────────────────────


def dentro_de_caja(punto: Punto, caja: Caja, margen: float = 0.0) -> bool:
	"""True si el punto está dentro del recuadro (con un margen opcional)."""
	return caja[0] - margen <= punto[0] <= caja[2] + margen and caja[1] - margen <= punto[1] <= caja[3] + margen


def _recortar_segmento(a: Punto, b: Punto, caja: Caja) -> tuple[Punto, Punto, bool, bool] | None:
	"""Trozo del segmento dentro del recuadro (Liang-Barsky) y si se movió cada extremo."""
	x0, y0, x1, y1 = caja
	dx, dy = b[0] - a[0], b[1] - a[1]
	t0, t1 = 0.0, 1.0
	for p, q in ((-dx, a[0] - x0), (dx, x1 - a[0]), (-dy, a[1] - y0), (dy, y1 - a[1])):
		if abs(p) < 1e-12:
			if q < 0.0:
				return None
			continue
		t = q / p
		if p < 0.0:
			if t > t1:
				return None
			t0 = max(t0, t)
		else:
			if t < t0:
				return None
			t1 = min(t1, t)
	if t1 - t0 < 1e-9:
		return None
	return (a[0] + dx * t0, a[1] + dy * t0), (a[0] + dx * t1, a[1] + dy * t1), t0 > 1e-9, t1 < 1.0 - 1e-9


def recortar_linea(linea: Sequence[Punto], ids: Sequence[int | None], caja: Caja) -> list[tuple[list[Punto], list[int | None]]]:
	"""Trozos de una línea que quedan dentro del recuadro, con el identificador de cada punto.

	Los puntos nuevos que aparecen en el borde llevan None: no son nodos del
	mapa y no pueden ser cruces. Una calle que sale y vuelve a entrar da
	varios trozos.
	"""
	trozos: list[tuple[list[Punto], list[int | None]]] = []
	puntos: list[Punto] = []
	marcas: list[int | None] = []
	for i in range(len(linea) - 1):
		recorte = _recortar_segmento(linea[i], linea[i + 1], caja)
		if recorte is None:
			if len(puntos) >= 2:
				trozos.append((puntos, marcas))
			puntos, marcas = [], []
			continue
		p, q, p_movido, q_movido = recorte
		if not puntos or p_movido:
			if len(puntos) >= 2:
				trozos.append((puntos, marcas))
			puntos, marcas = [p], [None if p_movido else ids[i]]
		puntos.append(q)
		marcas.append(None if q_movido else ids[i + 1])
		if q_movido:
			trozos.append((puntos, marcas))
			puntos, marcas = [], []
	if len(puntos) >= 2:
		trozos.append((puntos, marcas))
	return trozos


def recortar_poligono(poligono: Sequence[Punto], caja: Caja) -> Poligono:
	"""Parte de un polígono dentro del recuadro (Sutherland-Hodgman contra sus cuatro lados)."""
	x0, y0, x1, y1 = caja
	resultado = list(poligono)
	if geo.area_con_signo(resultado) < 0:
		resultado.reverse()
	for a, b in (((x0, y0), (x1, y0)), ((x1, y0), (x1, y1)), ((x1, y1), (x0, y1)), ((x0, y1), (x0, y0))):
		if len(resultado) < 3:
			return []
		resultado = geo.recortar_por_semiplano(resultado, a, b)
	return resultado


def tramo_centrado(a: Punto, b: Punto, punto: Punto, ancho: float) -> tuple[Punto, Punto] | None:
	"""Tramo de ``ancho`` metros sobre el segmento ab, centrado en la proyección de ``punto``.

	Es donde va un portal o una puerta: si no cabe centrado se arrima hacia
	dentro, y si el lado es más corto que el hueco, se ajusta al lado.
	"""
	largo = geo.distancia(a, b)
	if largo < 0.3:
		return None
	ancho = min(ancho, largo)
	centro = geo.parametro_segmento(punto, a, b) * largo
	inicio = max(0.0, min(largo - ancho, centro - ancho / 2.0))
	ux, uy = (b[0] - a[0]) / largo, (b[1] - a[1]) / largo
	return (a[0] + ux * inicio, a[1] + uy * inicio), (a[0] + ux * (inicio + ancho), a[1] + uy * (inicio + ancho))


def lado_mas_cercano(contorno: Sequence[Punto], punto: Punto) -> tuple[int, float]:
	"""(índice del lado, distancia) del lado del contorno más cercano a un punto."""
	mejor = (0, math.inf)
	for indice, (a, b) in enumerate(geo.lados(contorno)):
		d = geo.distancia_punto_segmento(punto, a, b)
		if d < mejor[1]:
			mejor = (indice, d)
	return mejor


def _pegar_vertices(contorno: Sequence[Punto], vecino: Sequence[Punto], tolerancia: float) -> Poligono:
	"""El contorno con los vértices que caen dentro de ``vecino``, cerca de su borde, llevados a ese borde."""
	resultado: Poligono = []
	# Un vértice fuera de la caja del vecino no puede estar dentro de él: se
	# descarta sin la comprobación completa, que mide la distancia a cada lado.
	x0, y0, x1, y1 = geo.caja(vecino)
	for punto in contorno:
		if x0 <= punto[0] <= x1 and y0 <= punto[1] <= y1 and geo.punto_en_poligono(punto, vecino, borde=False, tolerancia=1e-9):
			indice, distancia = lado_mas_cercano(vecino, punto)
			if distancia <= tolerancia:
				a, b = geo.lados(vecino)[indice]
				punto = geo.proyeccion_sobre_segmento(punto, a, b)
		resultado.append(punto)
	return resultado


def ajustar_medianeras(contornos: Sequence[Sequence[Punto]], tolerancia: float = 0.5) -> list[Poligono]:
	"""Contornos sin los solapes de pocos centímetros entre polígonos vecinos.

	En un mapa real, dos edificios pegados casi nunca comparten exactamente
	la medianera: una esquina de uno se mete unos centímetros en el otro.
	Para la persona que revisa el borrador eso son decenas de avisos de
	«se pisan» que no puede arreglar; para el motor, una pared doble. Aquí
	cada vértice metido en el vecino a menos de ``tolerancia`` metros de su
	borde se lleva a ese borde. Si el contorno resultante dejara de ser
	válido, se conserva el original: es mejor un aviso que un hueco.
	"""
	resultado = [list(contorno) for contorno in contornos]
	cajas = [geo.caja(contorno) for contorno in resultado]
	# La rejilla evita comparar cada edificio con todos los demás (con 1.000
	# edificios eran medio millón de parejas). Se apunta cada caja con holgura
	# de sobra: al ajustar, un vértice se mueve como mucho ``tolerancia`` y la
	# caja puede crecer un poco; la comprobación exacta sigue siendo la de antes.
	holgura = tolerancia + _HOLGURA_MEDIANERAS
	rejilla = RejillaCajas(_CELDA_MEDIANERAS)
	for indice, caja in enumerate(cajas):
		rejilla.anadir(indice, caja, holgura)
	for i in range(len(resultado)):
		for j in rejilla.cerca(cajas[i]):
			if j <= i:
				continue
			if not geo.cajas_se_tocan(cajas[i], cajas[j], tolerancia):
				continue
			for uno, otro in ((i, j), (j, i)):
				ajustado = _pegar_vertices(resultado[uno], resultado[otro], tolerancia)
				if ajustado != resultado[uno] and poligono_valido(ajustado, 1.0):
					resultado[uno] = ajustado
					cajas[uno] = geo.caja(ajustado)
	return resultado


class RejillaCajas:
	"""Índice espacial sencillo: cada caja se apunta en las celdas de una rejilla regular que toca.

	Por qué: al convertir una zona grande (400 metros de radio, unos 2.000
	espacios y 10.000 lados de fachada) las comprobaciones «¿qué hay cerca de
	aquí?» recorrían TODOS los elementos para cada consulta, y el tiempo crecía
	con el cuadrado del tamaño de la zona. Con la rejilla, cada consulta mira
	solo las celdas que toca. Es aproximada por exceso: devuelve candidatos
	cuya caja PUEDE tocar la pedida, y quien consulta hace la comprobación
	exacta. Así el resultado es el mismo que recorriéndolo todo.

	Las claves son enteros (la posición del elemento en su lista) y se
	devuelven ordenadas, para que quien necesite «el primero de la lista que
	cumpla» obtenga el mismo que con el recorrido completo.
	"""

	def __init__(self, celda: float = 20.0) -> None:
		if celda <= 0:
			raise ValueError("La celda de la rejilla tiene que medir más de cero.")
		self._celda = float(celda)
		self._celdas: dict[tuple[int, int], list[int]] = {}
		self.cuantas = 0

	def _rango(self, caja: Caja, margen: float) -> tuple[int, int, int, int]:
		celda = self._celda
		return (
			math.floor((caja[0] - margen) / celda),
			math.floor((caja[1] - margen) / celda),
			math.floor((caja[2] + margen) / celda),
			math.floor((caja[3] + margen) / celda),
		)

	def anadir(self, clave: int, caja: Caja, margen: float = 0.0) -> None:
		"""Apunta ``clave`` en todas las celdas que toca ``caja`` (agrandada en ``margen``)."""
		i0, j0, i1, j1 = self._rango(caja, margen)
		for i in range(i0, i1 + 1):
			for j in range(j0, j1 + 1):
				self._celdas.setdefault((i, j), []).append(clave)
		self.cuantas += 1

	def cerca(self, caja: Caja, margen: float = 0.0) -> list[int]:
		"""Claves cuya caja puede tocar ``caja`` agrandada en ``margen``, sin repetir y en orden creciente."""
		i0, j0, i1, j1 = self._rango(caja, margen)
		if i0 == i1 and j0 == j1:
			return sorted(set(self._celdas.get((i0, j0), ())))
		vistas: set[int] = set()
		for i in range(i0, i1 + 1):
			for j in range(j0, j1 + 1):
				vistas.update(self._celdas.get((i, j), ()))
		return sorted(vistas)


def punto_interior(poligono: Sequence[Punto]) -> Punto:
	"""Un punto que está seguro dentro del polígono (el centro de gravedad puede caer fuera en una L)."""
	centro = geo.centroide(poligono)
	if geo.punto_en_poligono(centro, poligono, borde=False, tolerancia=0.01):
		return centro
	for triangulo in geo.triangular(poligono):
		candidato = geo.centroide(triangulo)
		if geo.punto_en_poligono(candidato, poligono, borde=False, tolerancia=0.001):
			return candidato
	return centro
