"""Importación de planos SVG sencillos.

Sirve para un plano dibujado a mano en un programa de dibujo vectorial:
rectángulos y polígonos para las salas, líneas para las paredes y textos
para los nombres. Entiende ``rect``, ``polygon``, ``polyline``, ``line``,
``circle``, ``ellipse``, ``text`` y ``path`` con las órdenes M, L, H, V y Z
(las curvas se sustituyen por la recta a su punto final y se avisa).

Un SVG es un fichero que viene de fuera y puede traer de todo, así que:

- el XML se analiza sin entidades ni DOCTYPE (ver ``analizar_xml_seguro``):
  no se lee ningún fichero ni dirección externa;
- no se ejecuta nada: ``script``, ``foreignObject``, ``image``, ``use`` y las
  hojas de estilo se ignoran;
- hay límites de tamaño, de número de elementos y de puntos.

Un SVG no tiene unidades reales: la escala (cuántos metros es una unidad del
dibujo) hay que indicarla siempre.
"""

from __future__ import annotations

import logging
import math
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path

from app.core.i18n import _
from app.dominio.geometria import Punto
from app.importar.comun import Cancelado, ErrorImportacion, Progreso, ResultadoImportacion, analizar_xml_seguro, leer_fichero
from app.importar.plano import OpcionesPlano, Plano, Rotulo, Trazo, convertir_plano

log = logging.getLogger(__name__)

__all__ = ["OpcionesPlano", "convertir_svg", "importar_svg", "leer_svg"]

MAX_BYTES_SVG = 8 * 1024 * 1024
MAX_ELEMENTOS_SVG = 60_000
MAX_PUNTOS_SVG = 400_000
CAPA_SIN_NOMBRE = "sin capa"

# Elementos cuyo contenido no es dibujo del plano (definiciones, código, incrustaciones).
_NO_SE_DIBUJAN = frozenset(
	{"defs", "clipPath", "mask", "pattern", "symbol", "marker", "script", "style", "foreignObject", "metadata", "filter", "title", "desc"}
)
_IGNORADOS = frozenset({"image", "use", "a", "switch", "iframe", "audio", "video"})

_NUMERO = r"[-+]?(?:\d+\.?\d*|\.\d+)(?:[eE][-+]?\d+)?"
_FICHAS_PATH = re.compile(rf"[MmLlHhVvZzCcSsQqTtAa]|{_NUMERO}")
_NUMEROS = re.compile(_NUMERO)
_TRANSFORMACION = re.compile(r"(matrix|translate|scale|rotate|skewX|skewY)\s*\(([^)]*)\)")
# Parámetros que consume cada orden de curva de un path: solo interesa su punto final.
_PARAMETROS_CURVA = {"C": 6, "S": 4, "Q": 4, "T": 2, "A": 7}

Matriz = tuple[float, float, float, float, float, float]
IDENTIDAD: Matriz = (1.0, 0.0, 0.0, 1.0, 0.0, 0.0)


def _numero(texto: str | None, defecto: float = 0.0) -> float:
	"""Número de un atributo, sin sus unidades («12.5px» → 12.5)."""
	if not texto:
		return defecto
	hallado = _NUMEROS.search(texto)
	if hallado is None:
		return defecto
	valor = float(hallado.group())
	return valor if math.isfinite(valor) else defecto


def _componer(m: Matriz, n: Matriz) -> Matriz:
	"""Matriz de aplicar primero ``n`` y después ``m``."""
	a, b, c, d, e, f = m
	a2, b2, c2, d2, e2, f2 = n
	return (a * a2 + c * b2, b * a2 + d * b2, a * c2 + c * d2, b * c2 + d * d2, a * e2 + c * f2 + e, b * e2 + d * f2 + f)


def _transformacion(texto: str | None) -> Matriz:
	"""Matriz del atributo ``transform`` (las inclinaciones se ignoran)."""
	matriz = IDENTIDAD
	for nombre, argumentos in _TRANSFORMACION.findall(texto or ""):
		valores = [float(v) for v in _NUMEROS.findall(argumentos)]
		paso = IDENTIDAD
		if nombre == "matrix" and len(valores) == 6:
			paso = (valores[0], valores[1], valores[2], valores[3], valores[4], valores[5])
		elif nombre == "translate" and valores:
			paso = (1.0, 0.0, 0.0, 1.0, valores[0], valores[1] if len(valores) > 1 else 0.0)
		elif nombre == "scale" and valores:
			paso = (valores[0], 0.0, 0.0, valores[1] if len(valores) > 1 else valores[0], 0.0, 0.0)
		elif nombre == "rotate" and valores:
			angulo = math.radians(valores[0])
			coseno, seno = math.cos(angulo), math.sin(angulo)
			paso = (coseno, seno, -seno, coseno, 0.0, 0.0)
			if len(valores) >= 3:
				cx, cy = valores[1], valores[2]
				paso = _componer(_componer((1.0, 0.0, 0.0, 1.0, cx, cy), paso), (1.0, 0.0, 0.0, 1.0, -cx, -cy))
		matriz = _componer(matriz, paso)
	return matriz


def _subtrazos_de_path(datos: str) -> tuple[list[tuple[list[Punto], bool]], bool]:
	"""Trazos de un atributo ``d`` y si tenía curvas (que se han simplificado a rectas)."""
	fichas = _FICHAS_PATH.findall(datos)
	trazos: list[tuple[list[Punto], bool]] = []
	actual: list[Punto] = []
	x = y = inicio_x = inicio_y = 0.0
	orden = ""
	curvas = False
	i = 0

	def cerrar(cerrado: bool) -> None:
		nonlocal actual
		if len(actual) >= 2:
			trazos.append((actual, cerrado))
		actual = []

	def siguiente() -> float:
		nonlocal i
		if i >= len(fichas) or fichas[i].isalpha():
			raise ValueError("faltan números en el path")
		valor = float(fichas[i])
		i += 1
		return valor

	try:
		while i < len(fichas):
			if fichas[i].isalpha():
				orden = fichas[i]
				i += 1
				if orden in "Zz":
					cerrar(True)
					x, y = inicio_x, inicio_y
					continue
			elif not orden:
				raise ValueError("el path no empieza por una orden")
			relativo = orden.islower()
			mayuscula = orden.upper()
			if mayuscula == "M":
				cerrar(False)
				nx, ny = siguiente(), siguiente()
				x, y = (x + nx, y + ny) if relativo else (nx, ny)
				inicio_x, inicio_y = x, y
				actual = [(x, y)]
				# Los pares que siguen a un M son líneas, según la norma.
				orden = "l" if relativo else "L"
				continue
			if mayuscula == "L":
				nx, ny = siguiente(), siguiente()
				x, y = (x + nx, y + ny) if relativo else (nx, ny)
			elif mayuscula == "H":
				nx = siguiente()
				x = x + nx if relativo else nx
			elif mayuscula == "V":
				ny = siguiente()
				y = y + ny if relativo else ny
			elif mayuscula in _PARAMETROS_CURVA:
				valores = [siguiente() for _numero_parametro in range(_PARAMETROS_CURVA[mayuscula])]
				x, y = (x + valores[-2], y + valores[-1]) if relativo else (valores[-2], valores[-1])
				curvas = True
			else:
				raise ValueError(f"orden desconocida {orden!r}")
			if not actual:
				actual = [(inicio_x, inicio_y)]
			actual.append((x, y))
	except ValueError as error:
		log.info("Path SVG incompleto o mal formado (%s); se importa hasta donde se entiende.", error)
	cerrar(False)
	return trazos, curvas


class _LectorSVG:
	"""Recorre el árbol del SVG acumulando transformaciones y capas."""

	def __init__(self) -> None:
		self.plano = Plano(formato="SVG")
		self.puntos = 0
		self.curvas = False
		self.ignorados: set[str] = set()

	def _anadir(self, capa: str, puntos: list[Punto], cerrado: bool, matriz: Matriz, origen: str) -> None:
		if len(puntos) < 2:
			return
		self.puntos += len(puntos)
		if self.puntos > MAX_PUNTOS_SVG:
			raise ErrorImportacion(
				_("El SVG tiene más de {n} puntos: es demasiado detallado para importarlo como plano.").format(n=MAX_PUNTOS_SVG)
			)
		a, b, c, d, e, f = matriz
		# La y de un SVG crece hacia abajo; en el entorno, hacia el norte: se le cambia el signo.
		transformados = [(a * x + c * y + e, -(b * x + d * y + f)) for x, y in puntos]
		if cerrado and len(transformados) >= 2 and math.dist(transformados[0], transformados[-1]) < 1e-9:
			transformados.pop()
		self.plano.trazos.append(Trazo(capa, transformados, cerrado and len(transformados) >= 3, origen))

	def recorrer(self, elemento: ET.Element, matriz: Matriz, capa: str) -> None:
		"""Procesa un elemento y sus hijos; ``capa`` es la del grupo que lo contiene."""
		etiqueta = elemento.tag
		if etiqueta in _NO_SE_DIBUJAN:
			return
		if etiqueta in _IGNORADOS:
			self.ignorados.add(etiqueta)
			return
		estilo = (elemento.get("style") or "").replace(" ", "")
		if elemento.get("display") == "none" or "display:none" in estilo:
			return
		matriz = _componer(matriz, _transformacion(elemento.get("transform")))
		if etiqueta in ("g", "svg"):
			# Inkscape guarda el nombre de la capa en «label»; si no, vale el id del grupo.
			nombre = elemento.get("label") or (elemento.get("id") if etiqueta == "g" else None)
			capa_hijos = nombre.strip() if nombre and nombre.strip() else capa
			for hijo in elemento:
				self.recorrer(hijo, matriz, capa_hijos)
			return
		capa_propia = (elemento.get("class") or "").strip() or capa
		if etiqueta == "rect":
			x, y = _numero(elemento.get("x")), _numero(elemento.get("y"))
			ancho, alto = _numero(elemento.get("width")), _numero(elemento.get("height"))
			if ancho > 0 and alto > 0:
				self._anadir(capa_propia, [(x, y), (x + ancho, y), (x + ancho, y + alto), (x, y + alto)], True, matriz, etiqueta)
		elif etiqueta in ("polygon", "polyline"):
			valores = [float(v) for v in _NUMEROS.findall(elemento.get("points") or "")]
			self._anadir(capa_propia, list(zip(valores[0::2], valores[1::2], strict=False)), etiqueta == "polygon", matriz, etiqueta)
		elif etiqueta == "line":
			self._anadir(
				capa_propia,
				[(_numero(elemento.get("x1")), _numero(elemento.get("y1"))), (_numero(elemento.get("x2")), _numero(elemento.get("y2")))],
				False,
				matriz,
				etiqueta,
			)
		elif etiqueta in ("circle", "ellipse"):
			cx, cy = _numero(elemento.get("cx")), _numero(elemento.get("cy"))
			rx = _numero(elemento.get("r")) if etiqueta == "circle" else _numero(elemento.get("rx"))
			ry = rx if etiqueta == "circle" else _numero(elemento.get("ry"))
			if rx > 0 and ry > 0:
				self._anadir(
					capa_propia,
					[(cx + rx * math.cos(2 * math.pi * i / 24), cy + ry * math.sin(2 * math.pi * i / 24)) for i in range(24)],
					True,
					matriz,
					etiqueta,
				)
		elif etiqueta == "path":
			trazos, curvas = _subtrazos_de_path(elemento.get("d") or "")
			self.curvas = self.curvas or curvas
			for puntos, cerrado in trazos:
				self._anadir(capa_propia, puntos, cerrado, matriz, etiqueta)
		elif etiqueta == "text":
			texto = " ".join("".join(elemento.itertext()).split())
			if texto:
				origen = elemento
				if elemento.get("x") is None:
					origen = next((hijo for hijo in elemento.iter("tspan") if hijo.get("x") is not None), elemento)
				x, y = _numero(origen.get("x")), _numero(origen.get("y"))
				a, b, c, d, e, f = matriz
				tamano = _numero(elemento.get("font-size")) or _numero(estilo.partition("font-size:")[2]) or 1.0
				self.plano.rotulos.append(
					Rotulo(capa_propia, texto[:200], a * x + c * y + e, -(b * x + d * y + f), tamano * abs(a or d or 1.0))
				)
		else:
			self.ignorados.add(etiqueta)


def leer_svg(origen: str | os.PathLike[str] | bytes) -> Plano:
	"""Lee un SVG (ruta o bytes) y devuelve el plano con sus trazos y rótulos por capas.

	La capa de cada trazo es la del grupo que lo contiene (el nombre de capa
	de Inkscape o el ``id`` del grupo), o su ``class`` si la tiene.
	"""
	nombre = ""
	if isinstance(origen, (bytes, bytearray)):
		datos = bytes(origen)
	else:
		datos = leer_fichero(origen, MAX_BYTES_SVG)
		nombre = Path(origen).stem
	raiz = analizar_xml_seguro(datos, MAX_BYTES_SVG, MAX_ELEMENTOS_SVG)
	if raiz.tag != "svg":
		raise ErrorImportacion(_("El fichero no es un SVG: su elemento principal no es «svg»."))
	lector = _LectorSVG()
	lector.plano.nombre = nombre
	lector.recorrer(raiz, IDENTIDAD, CAPA_SIN_NOMBRE)
	if lector.curvas:
		lector.plano.avisos.append(
			_("El SVG tiene curvas: cada una se ha sustituido por una recta hasta su punto final. Revise las paredes curvas.")
		)
	sin_importar = sorted(lector.ignorados & _IGNORADOS)
	if sin_importar:
		lector.plano.avisos.append(
			_("Elementos del SVG que no se importan (imágenes, enlaces o referencias a otros dibujos): {lista}.").format(
				lista=", ".join(sin_importar)
			)
		)
	lector.plano.nota_unidades = _("Un SVG no tiene unidades reales: indique cuántos metros es una unidad del dibujo.")
	log.info("SVG leído: %s trazos y %s rótulos", len(lector.plano.trazos), len(lector.plano.rotulos))
	return lector.plano


def convertir_svg(
	plano: Plano, opciones: OpcionesPlano | None = None, progreso: Progreso | None = None, cancelado: Cancelado | None = None
) -> ResultadoImportacion:
	"""Convierte un plano SVG ya leído en un entorno. La escala (``metros_por_unidad``) es obligatoria."""
	if opciones is None or opciones.metros_por_unidad is None:
		x0, y0, x1, y1 = plano.caja()
		raise ErrorImportacion(
			_("Indique la escala del SVG: el dibujo mide {ancho} por {alto} unidades; diga cuántos metros es una unidad.").format(
				ancho=round(x1 - x0, 2), alto=round(y1 - y0, 2)
			)
		)
	return convertir_plano(plano, opciones, progreso, cancelado)


def importar_svg(
	origen: str | os.PathLike[str] | bytes,
	metros_por_unidad: float,
	opciones: OpcionesPlano | None = None,
	progreso: Progreso | None = None,
	cancelado: Cancelado | None = None,
) -> ResultadoImportacion:
	"""Lee y convierte un SVG de una vez con la escala indicada (metros por unidad del dibujo)."""
	opciones = opciones or OpcionesPlano()
	opciones.metros_por_unidad = metros_por_unidad
	return convertir_svg(leer_svg(origen), opciones, progreso, cancelado)
