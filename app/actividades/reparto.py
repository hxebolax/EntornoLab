"""Colocación asistida de premios: «reparte N premios de modo que haya que pasar por todos los espacios».

Los premios que obligan a recorrer todo el entorno, y no solo el camino
principal, son los que hacen que jugar sirva para aprender el lugar. El
reparto empieza por el espacio más lejano del inicio y va eligiendo cada vez
el que queda más lejos de los ya elegidos, de modo que con pocos premios se
cubren los extremos y con muchos hay uno en cada espacio.

Cuando el espacio tiene un objeto contenedor del catálogo (un cofre, un
armario, una mochila) el premio se esconde dentro, y hay que usarlo para
encontrarlo; si no, se deja en un punto libre.

Con la misma semilla el reparto es siempre el mismo.
"""

from __future__ import annotations

import logging
import math
import random
from typing import Any

from app.actividades.formato import normalizar_premio
from app.actividades.lugares import espacios_jugables, punto_de_espacio, punto_libre_en
from app.actividades.tipos import VISIBILIDADES
from app.core.i18n import _
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Entorno, Espacio, Objeto, Planta
from app.motor.mundo import Mundo
from app.motor.navegacion import Navegador

log = logging.getLogger(__name__)

# Dos espacios de plantas distintas se tratan como muy alejados al repartir.
PENA_OTRA_PLANTA = 1000.0
# Un premio suelto no se deja a menos de esto del punto de inicio.
LEJOS_DEL_INICIO = 1.6


def contenedores_de(mundo: Mundo, planta: Planta, espacio: Espacio, catalogo: Catalogo | None) -> list[Objeto]:
	"""Objetos del espacio que pueden esconder un premio (``contenedor`` en su ficha), en orden estable."""
	if catalogo is None:
		return []
	encontrados: list[Objeto] = []
	for objeto in planta.objetos:
		definicion = catalogo.definicion_de(objeto)
		if definicion is None or not definicion.contenedor:
			continue
		en = mundo.espacio_en(planta.id, objeto.x, objeto.y)
		if en is not None and en.id == espacio.id:
			encontrados.append(objeto)
	encontrados.sort(key=lambda objeto: objeto.id)
	return encontrados


def _separacion(a: tuple[Planta, Espacio], b: tuple[Planta, Espacio]) -> float:
	distancia = geo.distancia(punto_de_espacio(a[1]), punto_de_espacio(b[1]))
	return distancia + (PENA_OTRA_PLANTA if a[0].id != b[0].id else 0.0)


def ordenar_para_cubrir(nav: Navegador, entorno: Entorno, candidatos: list[tuple[Planta, Espacio]]) -> list[tuple[Planta, Espacio]]:
	"""Ordena los espacios para que los primeros de la lista sean los que más obligan a recorrer.

	Primero el más lejano del inicio por distancia de camino; después, cada
	vez, el más alejado de todos los ya elegidos. El espacio donde se empieza
	queda el último: es el único por el que se pasa seguro.
	"""
	inicio = entorno.inicio
	planta_inicio = entorno.planta(inicio.planta)
	espacio_inicio = planta_inicio.espacio_en(inicio.x, inicio.y, incluir_macizos=False) if planta_inicio is not None else None
	lejania: dict[str, float] = {}
	for planta, espacio in candidatos:
		punto = punto_de_espacio(espacio)
		distancia = nav.distancia(inicio, (planta.id, punto[0], punto[1]))
		lejania[espacio.id] = distancia if distancia is not None else -1.0
	resto = [par for par in candidatos if espacio_inicio is None or par[1].id != espacio_inicio.id]
	propio = [par for par in candidatos if espacio_inicio is not None and par[1].id == espacio_inicio.id]
	orden: list[tuple[Planta, Espacio]] = []
	while resto:
		if not orden:
			elegido = max(resto, key=lambda par: (round(lejania[par[1].id], 2), par[1].id))
		else:
			elegido = max(
				resto, key=lambda par: (round(min(_separacion(par, otro) for otro in orden), 2), round(lejania[par[1].id], 2), par[1].id)
			)
		resto.remove(elegido)
		orden.append(elegido)
	return orden + propio


def repartir_premios(
	entorno: Entorno,
	cantidad: int,
	catalogo: Catalogo | None = None,
	semilla: int | None = None,
	plantas: list[str] | None = None,
	visibilidad: str = "cerca",
	dentro_de_objetos: bool = True,
) -> list[dict]:
	"""Reparte ``cantidad`` premios por los espacios a los que se puede llegar desde el inicio del entorno.

	Devuelve la lista de premios lista para ``datos["premios"]`` (con nombres
	provisionales «Premio 1», «Premio 2»… que el profesional cambiará). Si
	hay más premios que espacios se da otra vuelta por ellos; si no cabe
	ninguno (un entorno sin espacios transitables) la lista sale vacía.
	"""
	cantidad = max(0, int(cantidad))
	if cantidad == 0:
		return []
	if visibilidad not in VISIBILIDADES:
		visibilidad = "cerca"
	azar = random.Random(semilla)
	mundo = Mundo(entorno, catalogo)
	nav = Navegador(mundo)
	alcanzables = nav.espacios_alcanzables(entorno.inicio)
	candidatos = [par for par in espacios_jugables(entorno, plantas) if not alcanzables or par[1].id in alcanzables]
	if not candidatos:
		log.warning("No hay espacios donde repartir premios en el entorno %s", entorno.id)
		return []
	orden = ordenar_para_cubrir(nav, entorno, candidatos)
	premios: list[dict[str, Any]] = []
	usados_objetos: set[str] = set()
	usados_ids: set[str] = set()
	puntos_usados: list[tuple[str, float, float]] = []
	vueltas = 0
	while len(premios) < cantidad and vueltas < 4:
		vueltas += 1
		for planta, espacio in orden:
			if len(premios) >= cantidad:
				break
			numero = len(premios) + 1
			dato: dict[str, Any] = {"id": f"premio-{numero}", "nombre": _("Premio {n}").format(n=numero), "visibilidad": visibilidad}
			contenedores = (
				[o for o in contenedores_de(mundo, planta, espacio, catalogo) if o.id not in usados_objetos] if dentro_de_objetos else []
			)
			if contenedores:
				objeto = azar.choice(contenedores)
				usados_objetos.add(objeto.id)
				dato.update({"planta": planta.id, "x": objeto.x, "y": objeto.y, "dentro_de": objeto.id})
			else:
				punto = None
				for _intento in range(12):
					candidato = punto_libre_en(mundo, planta.id, espacio, azar)
					if candidato is None:
						break
					# Dos premios no se dejan pegados, y el punto tiene que ser alcanzable andando.
					if any(p[0] == planta.id and math.hypot(p[1] - candidato[0], p[2] - candidato[1]) < 1.2 for p in puntos_usados):
						continue
					andando = nav.distancia(entorno.inicio, (planta.id, candidato[0], candidato[1]))
					if andando is None or andando < LEJOS_DEL_INICIO:
						# Inalcanzable, o tan cerca del inicio que se recogería nada más empezar.
						continue
					punto = candidato
					break
				if punto is None:
					continue
				puntos_usados.append((planta.id, punto[0], punto[1]))
				dato.update({"planta": planta.id, "x": punto[0], "y": punto[1], "dentro_de": None})
			limpio = normalizar_premio(dato, numero, usados_ids)
			if limpio is not None:
				premios.append(limpio)
	return premios
