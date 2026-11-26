"""Importación de planos DXF sin dependencias externas.

Un DXF de texto es una lista de parejas de líneas: un código numérico y un
valor. Este lector propio entiende lo que hace falta para un plano de
arquitectura sencillo: las entidades LINE, LWPOLYLINE, POLYLINE, CIRCLE, ARC,
TEXT, MTEXT e INSERT (bloques insertados con escala y giro), cada una en su
capa. Todo lo demás se cuenta y se ignora: es tolerante a propósito, porque
cada programa de CAD escribe el DXF a su manera.

Uso:

	plano = leer_dxf("planta.dxf")
	for capa in plano.capas(): ...        # enseñar las capas y dejar elegir
	resultado = convertir_dxf(plano, OpcionesPlano(metros_por_unidad=0.001, capas_paredes=["MUROS"]))

No se ejecuta nada del fichero y el plano no sale del equipo.
"""

from __future__ import annotations

import logging
import math
import os
import re
from collections import Counter
from pathlib import Path

from app.core.i18n import _
from app.dominio.geometria import Punto
from app.importar.comun import Cancelado, ErrorImportacion, Progreso, ResultadoImportacion, decodificar_texto, leer_fichero
from app.importar.plano import Arco, OpcionesPlano, Plano, Rotulo, Trazo, convertir_plano

log = logging.getLogger(__name__)

__all__ = ["OpcionesPlano", "convertir_dxf", "importar_dxf", "leer_dxf"]

MAX_BYTES_DXF = 60 * 1024 * 1024
MAX_ENTIDADES = 300_000
MAX_PROFUNDIDAD_BLOQUES = 4
GRADOS_POR_TRAMO = 15.0

# $INSUNITS → metros por unidad.
_UNIDADES: dict[int, tuple[float, str]] = {
	1: (0.0254, "pulgadas"),
	2: (0.3048, "pies"),
	4: (0.001, "milímetros"),
	5: (0.01, "centímetros"),
	6: (1.0, "metros"),
	14: (0.1, "decímetros"),
}
# Comentario que escribe el exportador de EntornoLab para decir que el dibujo va en metros.
MARCA_METROS = "EntornoLab: unidades en metros"

_FORMATO_MTEXT = re.compile(r"\\[ACFHQTWfacfhqtw][^;\\]*;|\\[LlOoKk]|[{}]")

Registro = list[tuple[int, str]]


def _numero(valor: str, defecto: float = 0.0) -> float:
	try:
		numero = float(valor)
	except ValueError:
		return defecto
	return numero if math.isfinite(numero) else defecto


def _parejas(texto: str) -> list[tuple[int, str]]:
	"""El fichero como lista de (código, valor); lanza si no tiene pinta de DXF."""
	lineas = texto.splitlines()
	parejas: list[tuple[int, str]] = []
	malas = 0
	for i in range(0, len(lineas) - 1, 2):
		try:
			codigo = int(lineas[i].strip())
		except ValueError:
			malas += 1
			if malas > 20 and malas > len(parejas):
				break
			continue
		parejas.append((codigo, lineas[i + 1].strip()))
	if len(parejas) < 4 or not any(codigo == 0 and valor.upper() in ("SECTION", "EOF") for codigo, valor in parejas[:2000]):
		raise ErrorImportacion(_("El fichero no es un DXF de texto válido."))
	return parejas


def _registros(parejas: list[tuple[int, str]], inicio: int, fin: int) -> list[Registro]:
	"""Parte un tramo del fichero en registros: cada uno empieza en un código 0."""
	registros: list[Registro] = []
	actual: Registro | None = None
	for codigo, valor in parejas[inicio:fin]:
		if codigo == 0:
			actual = [(0, valor.upper())]
			registros.append(actual)
		elif actual is not None:
			actual.append((codigo, valor))
	return registros


def _primero(registro: Registro, codigo: int, defecto: str = "") -> str:
	for clave, valor in registro:
		if clave == codigo:
			return valor
	return defecto


def _arco(centro: Punto, radio: float, inicio: float, fin: float) -> list[Punto]:
	"""Puntos de un arco de circunferencia en sentido antihorario, de ``inicio`` a ``fin`` grados."""
	barrido = (fin - inicio) % 360.0 or 360.0
	tramos = max(2, math.ceil(barrido / GRADOS_POR_TRAMO))
	return [
		(
			centro[0] + radio * math.cos(math.radians(inicio + barrido * i / tramos)),
			centro[1] + radio * math.sin(math.radians(inicio + barrido * i / tramos)),
		)
		for i in range(tramos + 1)
	]


def _con_curvas(vertices: list[tuple[Punto, float]], cerrado: bool) -> list[Punto]:
	"""Vértices de una polilínea con sus «bulges» (tramos curvos) convertidos en tramos rectos cortos."""
	puntos: list[Punto] = []
	total = len(vertices)
	for i, (p, curva) in enumerate(vertices):
		puntos.append(p)
		if abs(curva) < 1e-6 or (i == total - 1 and not cerrado):
			continue
		q = vertices[(i + 1) % total][0]
		cuerda = math.hypot(q[0] - p[0], q[1] - p[1])
		if cuerda < 1e-9:
			continue
		angulo = 4.0 * math.atan(curva)
		radio = cuerda / (2.0 * math.sin(abs(angulo) / 2.0))
		# El centro queda a un lado u otro de la cuerda según el signo de la curva.
		medio = ((p[0] + q[0]) / 2.0, (p[1] + q[1]) / 2.0)
		flecha = math.sqrt(max(radio * radio - (cuerda / 2.0) ** 2, 0.0)) * (1.0 if abs(angulo) <= math.pi else -1.0)
		nx, ny = -(q[1] - p[1]) / cuerda, (q[0] - p[0]) / cuerda
		signo = 1.0 if curva > 0 else -1.0
		centro = (medio[0] + nx * flecha * signo, medio[1] + ny * flecha * signo)
		inicio = math.atan2(p[1] - centro[1], p[0] - centro[0])
		tramos = max(2, math.ceil(math.degrees(abs(angulo)) / GRADOS_POR_TRAMO))
		for k in range(1, tramos):
			a = inicio + angulo * k / tramos
			puntos.append((centro[0] + radio * math.cos(a), centro[1] + radio * math.sin(a)))
	return puntos


def _limpiar_mtext(texto: str) -> str:
	"""Texto legible de un MTEXT: sin códigos de formato y con los saltos como espacios."""
	texto = texto.replace("\\P", " ").replace("\\p", " ").replace("\\~", " ").replace("\\N", " ")
	texto = _FORMATO_MTEXT.sub("", texto)
	return " ".join(texto.replace("\\\\", "\\").split())


class _Lector:
	"""Convierte los registros del DXF en trazos, rótulos y arcos, expandiendo los bloques."""

	def __init__(self) -> None:
		self.plano = Plano(formato="DXF")
		self.bloques: dict[str, tuple[Punto, list[Registro]]] = {}
		self.ignoradas: Counter[str] = Counter()
		self.entidades = 0

	def entidades_de(
		self,
		registros: list[Registro],
		transformar: tuple[float, float, float, float, float, float] | None,
		capa_padre: str,
		profundidad: int,
	) -> None:
		"""Procesa una lista de entidades; ``transformar`` es la matriz del bloque en que están (o None)."""
		i = 0
		while i < len(registros):
			registro = registros[i]
			tipo = registro[0][1]
			i += 1
			vertices: list[Registro] = []
			if tipo == "POLYLINE":
				while i < len(registros) and registros[i][0][1] == "VERTEX":
					vertices.append(registros[i])
					i += 1
				if i < len(registros) and registros[i][0][1] == "SEQEND":
					i += 1
			if tipo in ("SEQEND", "VERTEX", "ENDBLK", "BLOCK", "ATTRIB"):
				continue
			if _primero(registro, 67) == "1":
				# Espacio papel: es la lámina con el cajetín, no el plano.
				continue
			self.entidades += 1
			if self.entidades > MAX_ENTIDADES:
				raise ErrorImportacion(
					_("El DXF tiene más de {n} entidades: es demasiado grande. Exporte solo las capas del plano.").format(n=MAX_ENTIDADES)
				)
			capa = _primero(registro, 8, "0") or "0"
			if capa == "0" and capa_padre:
				capa = capa_padre
			self._entidad(tipo, registro, vertices, capa, transformar, profundidad)

	def _entidad(
		self,
		tipo: str,
		registro: Registro,
		vertices: list[Registro],
		capa: str,
		matriz: tuple[float, float, float, float, float, float] | None,
		profundidad: int,
	) -> None:
		espejo = -1.0 if _numero(_primero(registro, 230, "1"), 1.0) < 0 else 1.0

		def mover(p: Punto, con_espejo: bool = True) -> Punto:
			x, y = (p[0] * espejo if con_espejo else p[0]), p[1]
			if matriz is None:
				return x, y
			a, b, c, d, e, f = matriz
			return a * x + c * y + e, b * x + d * y + f

		def punto(cx: int, cy: int) -> Punto:
			return _numero(_primero(registro, cx)), _numero(_primero(registro, cy))

		if tipo == "LINE":
			self.plano.trazos.append(Trazo(capa, [mover(punto(10, 20), False), mover(punto(11, 21), False)], False, tipo))
		elif tipo == "LWPOLYLINE":
			lista: list[tuple[Punto, float]] = []
			x: float | None = None
			for codigo, valor in registro:
				if codigo == 10:
					x = _numero(valor)
				elif codigo == 20 and x is not None:
					lista.append(((x, _numero(valor)), 0.0))
					x = None
				elif codigo == 42 and lista:
					lista[-1] = (lista[-1][0], _numero(valor))
			cerrado = int(_numero(_primero(registro, 70, "0"))) & 1 == 1
			self._polilinea(capa, lista, cerrado, tipo, mover)
		elif tipo == "POLYLINE":
			marcas = int(_numero(_primero(registro, 70, "0")))
			if marcas & (16 | 64):
				self.ignoradas["malla 3D"] += 1
				return
			lista = [((_numero(_primero(v, 10)), _numero(_primero(v, 20))), _numero(_primero(v, 42, "0"))) for v in vertices]
			self._polilinea(capa, lista, marcas & 1 == 1, tipo, mover)
		elif tipo == "CIRCLE":
			radio = _numero(_primero(registro, 40))
			if radio > 0:
				self.plano.trazos.append(Trazo(capa, [mover(p) for p in _arco(punto(10, 20), radio, 0.0, 360.0)[:-1]], True, tipo))
		elif tipo == "ARC":
			radio = _numero(_primero(registro, 40))
			if radio <= 0:
				return
			inicio, fin = _numero(_primero(registro, 50)), _numero(_primero(registro, 51))
			puntos = [mover(p) for p in _arco(punto(10, 20), radio, inicio, fin)]
			self.plano.trazos.append(Trazo(capa, puntos, False, tipo))
			centro = mover(punto(10, 20))
			radio_real = math.hypot(puntos[0][0] - centro[0], puntos[0][1] - centro[1])
			angulos = [math.degrees(math.atan2(p[1] - centro[1], p[0] - centro[0])) for p in (puntos[0], puntos[-1])]
			if _producto_cruz(centro, puntos[0], puntos[len(puntos) // 2]) < 0:
				angulos.reverse()
			self.plano.arcos.append(Arco(capa, centro, radio_real, angulos[0], angulos[1]))
		elif tipo in ("TEXT", "MTEXT"):
			texto = _primero(registro, 1)
			if tipo == "MTEXT":
				texto = _limpiar_mtext("".join(valor for codigo, valor in registro if codigo == 3) + texto)
			texto = texto.replace("%%c", "Ø").replace("%%d", "°").replace("%%p", "±").strip()
			if texto:
				x0, y0 = mover(punto(10, 20))
				self.plano.rotulos.append(
					Rotulo(capa, texto, x0, y0, abs(_numero(_primero(registro, 40))) * (abs(matriz[0]) if matriz else 1.0))
				)
		elif tipo == "INSERT":
			self._insertar(registro, capa, matriz, mover, profundidad)
		else:
			self.ignoradas[tipo] += 1

	def _polilinea(self, capa: str, vertices: list[tuple[Punto, float]], cerrado: bool, tipo: str, mover) -> None:  # noqa: ANN001 - función local de transformación
		if len(vertices) < 2:
			return
		puntos = [mover(p) for p in _con_curvas(vertices, cerrado)]
		if cerrado and len(puntos) < 3:
			cerrado = False
		self.plano.trazos.append(Trazo(capa, puntos, cerrado, tipo))

	def _insertar(
		self, registro: Registro, capa: str, matriz: tuple[float, float, float, float, float, float] | None, mover, profundidad: int
	) -> None:  # noqa: ANN001
		nombre = _primero(registro, 2)
		bloque = self.bloques.get(nombre.upper())
		if bloque is None:
			self.ignoradas[_("bloque que no está en el fichero")] += 1
			return
		if profundidad >= MAX_PROFUNDIDAD_BLOQUES:
			self.ignoradas[_("bloques demasiado anidados")] += 1
			return
		base, contenido = bloque
		escala_x = _numero(_primero(registro, 41, "1"), 1.0) or 1.0
		escala_y = _numero(_primero(registro, 42, "1"), 1.0) or 1.0
		giro = math.radians(_numero(_primero(registro, 50, "0")))
		ix, iy = _numero(_primero(registro, 10)), _numero(_primero(registro, 20))
		coseno, seno = math.cos(giro), math.sin(giro)
		# p' = R · S · (p - base) + inserción, como matriz afín (a, b, c, d, e, f).
		a, b = coseno * escala_x, seno * escala_x
		c, d = -seno * escala_y, coseno * escala_y
		e = ix - a * base[0] - c * base[1]
		f = iy - b * base[0] - d * base[1]
		if matriz is not None:
			a0, b0, c0, d0, e0, f0 = matriz
			a, b, c, d, e, f = (
				a0 * a + c0 * b,
				b0 * a + d0 * b,
				a0 * c + c0 * d,
				b0 * c + d0 * d,
				a0 * e + c0 * f + e0,
				b0 * e + d0 * f + f0,
			)
		self.entidades_de(contenido, (a, b, c, d, e, f), capa, profundidad + 1)


def _producto_cruz(o: Punto, a: Punto, b: Punto) -> float:
	return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def leer_dxf(origen: str | os.PathLike[str] | bytes) -> Plano:
	"""Lee un DXF (ruta o bytes) y devuelve el plano con sus trazos, rótulos y arcos por capas.

	No convierte nada todavía: con ``plano.capas()`` se enseñan las capas
	para elegir cuáles son paredes, y ``plano.sugerir_escala()`` dice las
	unidades si el fichero las declara.
	"""
	nombre = ""
	if isinstance(origen, (bytes, bytearray)):
		datos = bytes(origen)
		if len(datos) > MAX_BYTES_DXF:
			raise ErrorImportacion(_("El DXF es demasiado grande para importarlo."))
	else:
		datos = leer_fichero(origen, MAX_BYTES_DXF)
		nombre = Path(origen).stem
	if datos.startswith(b"AutoCAD Binary DXF"):
		raise ErrorImportacion(_("Es un DXF binario. Guárdelo desde el programa de CAD como DXF de texto (ASCII) y vuelva a importarlo."))
	parejas = _parejas(decodificar_texto(datos))
	lector = _Lector()
	lector.plano.nombre = nombre
	secciones: dict[str, tuple[int, int]] = {}
	i = 0
	while i < len(parejas) - 1:
		if parejas[i] == (0, "SECTION") or (parejas[i][0] == 0 and parejas[i][1].upper() == "SECTION"):
			nombre_seccion = parejas[i + 1][1].upper() if parejas[i + 1][0] == 2 else ""
			fin = i + 2
			while fin < len(parejas) and not (parejas[fin][0] == 0 and parejas[fin][1].upper() == "ENDSEC"):
				fin += 1
			secciones[nombre_seccion] = (i + 2, fin)
			i = fin
		i += 1
	if "ENTITIES" not in secciones:
		raise ErrorImportacion(_("El DXF no tiene sección de entidades: no hay nada que importar."))
	if any(codigo == 999 and MARCA_METROS in valor for codigo, valor in parejas[:200]):
		lector.plano.metros_por_unidad = 1.0
		lector.plano.nota_unidades = _("El fichero lo escribió EntornoLab, en metros.")
	if "HEADER" in secciones:
		inicio, fin = secciones["HEADER"]
		for j in range(inicio, fin - 1):
			if parejas[j] == (9, "$INSUNITS"):
				unidad = _UNIDADES.get(int(_numero(parejas[j + 1][1])))
				if unidad is not None and lector.plano.metros_por_unidad is None:
					lector.plano.metros_por_unidad = unidad[0]
					lector.plano.nota_unidades = _("El fichero declara sus unidades: {unidad}.").format(unidad=_(unidad[1]))
	if "BLOCKS" in secciones:
		actual: list[Registro] | None = None
		for registro in _registros(parejas, *secciones["BLOCKS"]):
			tipo = registro[0][1]
			if tipo == "BLOCK":
				actual = []
				lector.bloques[_primero(registro, 2).upper()] = ((_numero(_primero(registro, 10)), _numero(_primero(registro, 20))), actual)
			elif tipo == "ENDBLK":
				actual = None
			elif actual is not None:
				actual.append(registro)
	lector.entidades_de(_registros(parejas, *secciones["ENTITIES"]), None, "", 0)
	if lector.ignoradas:
		detalle = ", ".join(f"{tipo} ({veces})" for tipo, veces in sorted(lector.ignoradas.items()))
		lector.plano.avisos.append(_("Entidades del DXF que no se importan: {detalle}.").format(detalle=detalle))
	log.info(
		"DXF leído: %s trazos, %s rótulos, %s arcos, %s capas",
		len(lector.plano.trazos),
		len(lector.plano.rotulos),
		len(lector.plano.arcos),
		len(lector.plano.capas()),
	)
	return lector.plano


def convertir_dxf(
	plano: Plano, opciones: OpcionesPlano | None = None, progreso: Progreso | None = None, cancelado: Cancelado | None = None
) -> ResultadoImportacion:
	"""Convierte un plano DXF ya leído en un entorno, con las capas y la escala elegidas."""
	return convertir_plano(plano, opciones, progreso, cancelado)


def importar_dxf(
	origen: str | os.PathLike[str] | bytes,
	opciones: OpcionesPlano | None = None,
	progreso: Progreso | None = None,
	cancelado: Cancelado | None = None,
) -> ResultadoImportacion:
	"""Lee y convierte un DXF de una vez, con las sugerencias del programa si no se dan opciones."""
	return convertir_plano(leer_dxf(origen), opciones, progreso, cancelado)
