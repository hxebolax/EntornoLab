"""Entornos GRANDES y realistas para medir el rendimiento (Estudio y reproductor).

Por qué existen: el profesional importó un barrio de OpenStreetMap con 350
espacios y el Estudio se quedó colgado diez segundos en cada clic del árbol.
Con los entornos de ejemplo (una vivienda, un cruce) esos fallos no se ven.
Aquí se construyen, sin red y de forma determinista:

- ``plaza_real()``: la muestra REAL de OpenStreetMap de ``tests/datos``
  (Plaza Mayor de Valladolid, 150 m de radio) ya convertida: 249 espacios,
  156 puertas y portales, 204 referencias, 48 objetos y 16 calles.
- ``barrio(n)``: un barrio de unos ``n`` espacios hecho con copias de esa
  plaza puestas una al lado de otra (como si se hubiera importado un radio
  mayor), con los ids renombrados para que no se repitan.
- ``amueblar(entorno, catalogo, n)``: ``n`` objetos REALES del catálogo
  instalado repartidos por los espacios interiores, como si el profesional
  hubiera amueblado el entorno.

Datos de la plaza: © colaboradores de OpenStreetMap, licencia ODbL.
"""

from __future__ import annotations

import copy
import functools
import math
import random
from typing import Any

from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Entorno, Objeto

# Separación entre copias de la plaza: algo más que su recuadro (300 m) para que no se pisen.
SEPARACION_M = 320.0
# Claves de los diccionarios del modelo que son UN punto o una lista de puntos (se desplazan al copiar).
_CLAVES_PUNTO = ("a", "b")
_CLAVES_PUNTOS = ("contorno", "eje")


@functools.cache
def _plaza_en_dict() -> dict[str, Any]:
	"""La plaza real convertida, como diccionario (se convierte una sola vez por sesión)."""
	from tests.test_importar_osm_real import _datos_como_descargados

	from app.importar import osm

	resultado = osm.convertir(_datos_como_descargados(), osm.OpcionesOSM(nombre="Plaza Mayor de Valladolid"))
	return resultado.entorno.a_dict()


def plaza_real() -> Entorno:
	"""La muestra real de OpenStreetMap ya convertida (un entorno nuevo en cada llamada)."""
	return Entorno.de_dict(copy.deepcopy(_plaza_en_dict()))


def _desplazar_elemento(datos: dict[str, Any], dx: float, dy: float, sufijo: str) -> None:
	"""Mueve un elemento ya en diccionario y le pone un id que no se repite."""
	if datos.get("id"):
		datos["id"] = f"{datos['id']}{sufijo}"
	for clave in _CLAVES_PUNTO:
		if isinstance(datos.get(clave), list) and len(datos[clave]) == 2:
			datos[clave] = [datos[clave][0] + dx, datos[clave][1] + dy]
	for clave in _CLAVES_PUNTOS:
		if isinstance(datos.get(clave), list):
			datos[clave] = [[x + dx, y + dy] for x, y in datos[clave]]
	if "x" in datos and "y" in datos:
		datos["x"] = datos["x"] + dx
		datos["y"] = datos["y"] + dy
	extra = datos.get("datos")
	if isinstance(extra, dict) and isinstance(extra.get("extremos"), list):
		extra["extremos"] = [[x + dx, y + dy] for x, y in extra["extremos"]]


def barrio(espacios: int, nombre: str = "") -> Entorno:
	"""Un barrio de ``espacios`` espacios hecho con copias de la plaza real puestas en rejilla.

	La última copia se recorta para llegar justo a la cifra pedida: así las
	mediciones de 350, 1.000 y 3.000 espacios son comparables entre sí.
	"""
	base = _plaza_en_dict()
	planta_base = base["plantas"][0]
	por_copia = len(planta_base["espacios"])
	copias = max(1, math.ceil(espacios / por_copia))
	lado = math.ceil(math.sqrt(copias))
	datos = copy.deepcopy(base)
	datos["nombre"] = nombre or f"Barrio de {espacios} espacios"
	planta = datos["plantas"][0]
	listas = ("espacios", "paredes", "aberturas", "objetos", "fuentes", "zonas", "referencias", "vias")
	for lista in listas:
		planta[lista] = []
	for numero in range(copias):
		dx = (numero % lado) * SEPARACION_M
		dy = (numero // lado) * SEPARACION_M
		sufijo = f"-c{numero}" if numero else ""
		for lista in listas:
			for elemento in planta_base[lista]:
				nuevo = copy.deepcopy(elemento)
				if numero:
					_desplazar_elemento(nuevo, dx, dy, sufijo)
				planta[lista].append(nuevo)
	planta["espacios"] = planta["espacios"][:espacios]
	return Entorno.de_dict(datos)


def amueblar(entorno: Entorno, catalogo: Catalogo, objetos: int, semilla: int = 7) -> int:
	"""Pone ``objetos`` objetos reales del catálogo dentro de los espacios del entorno. Devuelve cuántos puso.

	Se eligen al azar (con semilla fija: el resultado es siempre el mismo)
	entre todas las definiciones del catálogo, y cada uno va al centro de un
	espacio con un pequeño desplazamiento. No se comprueba que quepan: lo que
	se mide es el coste de tener cientos de objetos, no la colocación.
	"""
	azar = random.Random(semilla)
	definiciones = [definicion for definicion in catalogo.objetos() if definicion.se_puede_usar]
	planta = entorno.plantas[0]
	destinos = [espacio for espacio in planta.espacios if len(espacio.contorno) >= 3 and not espacio.macizo] or planta.espacios
	puestos = 0
	for numero in range(objetos):
		definicion = azar.choice(definiciones)
		espacio = destinos[numero % len(destinos)]
		x, y = espacio.centro()
		objeto: Objeto = catalogo.crear_objeto(definicion.tipo, x + azar.uniform(-0.5, 0.5), y + azar.uniform(-0.5, 0.5))
		objeto.id = entorno.nuevo_id("obj")
		planta.objetos.append(objeto)
		puestos += 1
	return puestos
