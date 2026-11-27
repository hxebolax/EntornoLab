"""Operaciones de edición de alto nivel: construir un entorno por medidas y por relaciones.

Es lo que usa el editor del Estudio. Está pensado para trabajar SIN VER el
plano: en lugar de arrastrar líneas se dice «habitación de 4 por 3 metros»,
«al este del salón, compartiendo pared», «puerta en la pared norte a 1,20 de
la esquina oeste». Cada función calcula las coordenadas, comprueba lo que
pide y, si no se puede hacer, lanza ``ErrorEdicion`` con un mensaje que se
puede leer tal cual a la persona.

También están aquí las descripciones en texto (``describir_elemento`` y
``describir_entorno``), que son la manera de «mirar» el entorno con un lector
de pantalla, y el ``Historial`` para deshacer y rehacer.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.i18n import _, _n, separador_decimal
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.colocacion import LADOS, lado_de_espacio
from app.dominio.diferencias import Foto, Parche, aplicar, comparar, comparar_y_fotografiar, tomar_foto
from app.dominio.formato import identificador_seguro
from app.dominio.geometria import Punto
from app.dominio.modelo import (
	ACUSTICA_POR_TIPO,
	ACUSTICAS,
	ESTADOS_ABERTURA,
	HOJAS,
	NIVELES_TRAFICO,
	PASAMANOS,
	SENTIDOS_VIA,
	SUELO_POR_TIPO,
	SUELOS,
	TIPOS_ABERTURA,
	TIPOS_CONECTOR,
	TIPOS_ESPACIO,
	TIPOS_EXTERIORES,
	TIPOS_REFERENCIA,
	TOLERANCIA_PARED,
	Abertura,
	Conector,
	Entorno,
	Espacio,
	FuenteSonido,
	IndiceEspacios,
	Objeto,
	Parada,
	Pared,
	Planta,
	Posicion,
	Referencia,
	Tramo,
	Via,
	ZonaSuelo,
	nombre_visible,
)

log = logging.getLogger(__name__)

ANCHO_PUERTA = 0.82
ANCHO_PORTAL = 1.2
ALTURA_ENTRE_PLANTAS = 3.0
# Fondo de la banda de pavimento táctil que se pone a cada lado de un paso de peatones.
FONDO_TACTIL = 0.6


class ErrorEdicion(ValueError):
	"""La operación pedida no se puede hacer; el mensaje está pensado para la persona."""


# ── Utilidades ───────────────────────────────────────────────────────────────


def _m(valor: float) -> str:
	"""Una medida como se dice en español: «3», «3,5», «0,82»."""
	texto = f"{valor:.2f}".rstrip("0").rstrip(".")
	if texto in ("", "-0"):
		texto = "0"
	return texto.replace(".", separador_decimal())


def _metros(valor: float) -> str:
	"""«1 metro», «3,5 metros»."""
	return _n("{n} metro", "{n} metros", 1 if abs(valor - 1.0) < 0.005 else 2).format(n=_m(valor))


def _lado_visible(lado: str) -> str:
	"""Nombre traducido de un lado (norte, sur…)."""
	return _(lado)


def resolver(entorno: Entorno, elemento: Any) -> tuple[Planta | None, Any]:
	"""(planta, elemento) a partir de un elemento o de su id; lanza ``ErrorEdicion`` si no existe."""
	if isinstance(elemento, str):
		encontrado = entorno.buscar(elemento)
		if encontrado is None:
			raise ErrorEdicion(_("No existe ningún elemento con el identificador «{id}».").format(id=elemento))
		return encontrado
	if isinstance(elemento, Planta):
		return elemento, elemento
	if isinstance(elemento, Conector):
		return None, elemento
	return entorno.planta_de(elemento), elemento


def _positivo(valor: float, nombre: str) -> float:
	try:
		numero = float(valor)
	except (TypeError, ValueError) as error:
		raise ErrorEdicion(_("«{nombre}» tiene que ser un número.").format(nombre=nombre)) from error
	if not math.isfinite(numero) or numero <= 0:
		raise ErrorEdicion(_("«{nombre}» tiene que ser mayor que cero.").format(nombre=nombre))
	return numero


def _registrar(entorno: Entorno, planta: Planta, elemento: Any) -> Any:
	"""Da id al elemento y lo guarda en la lista de la planta que le toca."""
	if not elemento.id:
		elemento.id = entorno.id_para(elemento)
	lista = planta.lista_de(elemento)
	if lista is None:
		raise ErrorEdicion(_("Ese elemento no se puede guardar en una planta."))
	lista.append(elemento)
	return elemento


# ── Entorno y plantas ────────────────────────────────────────────────────────


def crear_entorno(nombre: str, descripcion: str = "", autor: str = "") -> Entorno:
	"""Entorno vacío con su id derivado del nombre."""
	return Entorno(id=identificador_seguro(nombre, "entorno"), nombre=nombre, descripcion=descripcion, autor=autor)


def crear_planta(
	entorno: Entorno,
	nombre: str = "",
	nivel: int | None = None,
	altura_m: float | None = None,
	exterior: bool = False,
	descripcion: str = "",
) -> Planta:
	"""Añade una planta. Sin ``nivel`` se pone encima de la más alta; sin ``altura_m``, a 3 m por nivel.

	La primera planta que se crea pasa a ser la del punto de inicio.
	"""
	if nivel is None:
		nivel = max((planta.nivel for planta in entorno.plantas), default=-1) + 1
	if any(planta.nivel == nivel for planta in entorno.plantas):
		raise ErrorEdicion(_("Ya hay una planta en el nivel {nivel}.").format(nivel=nivel))
	if not nombre:
		if exterior:
			nombre = _("Calle")
		elif nivel == 0:
			nombre = _("Planta baja")
		elif nivel > 0:
			nombre = _("Planta {n}").format(n=nivel)
		else:
			nombre = _("Sótano {n}").format(n=-nivel)
	planta = Planta(
		id=entorno.nuevo_id("pla"),
		nombre=nombre,
		descripcion=descripcion,
		nivel=int(nivel),
		altura_m=float(nivel * ALTURA_ENTRE_PLANTAS if altura_m is None else altura_m),
		exterior=exterior,
	)
	entorno.plantas.append(planta)
	entorno.plantas.sort(key=lambda p: p.nivel)
	if not entorno.inicio.planta:
		entorno.inicio.planta = planta.id
	return planta


def fijar_inicio(entorno: Entorno, planta: Planta, x: float, y: float, rumbo: float = 0.0) -> Posicion:
	"""Fija el punto y el rumbo de inicio por defecto del entorno."""
	entorno.inicio = Posicion(planta=planta.id, x=float(x), y=float(y), rumbo=geo.normalizar_rumbo(rumbo))
	return entorno.inicio


# ── Espacios ─────────────────────────────────────────────────────────────────


def crear_espacio_poligonal(
	entorno: Entorno,
	planta: Planta,
	nombre: str,
	contorno: Sequence[Punto],
	tipo: str = "habitacion",
	cerrado: bool | None = None,
	suelo: str | None = None,
	acustica: str | None = None,
	pared_material: str = "ladrillo",
	macizo: bool = False,
	descripcion: str = "",
	datos: dict[str, Any] | None = None,
	lados_abiertos: Iterable[int] = (),
	permitir_solape: bool = False,
) -> Espacio:
	"""Crea un espacio con cualquier contorno (se ordena solo en sentido antihorario).

	Sin ``cerrado`` se deduce del tipo: los interiores tienen paredes, las
	zonas de calle no. Dos espacios con paredes no pueden pisarse (salvo
	``permitir_solape``): sería una habitación dentro de otra sin puerta.
	"""
	if tipo not in TIPOS_ESPACIO:
		raise ErrorEdicion(_("«{tipo}» no es un tipo de espacio. Tipos: {tipos}.").format(tipo=tipo, tipos=", ".join(TIPOS_ESPACIO)))
	try:
		puntos = geo.orientar_antihorario([(float(p[0]), float(p[1])) for p in contorno])
	except (TypeError, ValueError, IndexError) as error:
		raise ErrorEdicion(_("El contorno tiene que ser una lista de puntos (x, y).")) from error
	if len(puntos) < 3:
		raise ErrorEdicion(_("Un espacio necesita al menos tres vértices."))
	if not geo.es_simple(puntos) or geo.area(puntos) < 0.01:
		raise ErrorEdicion(_("El contorno de «{nombre}» se corta a sí mismo o no encierra superficie.").format(nombre=nombre))
	if cerrado is None:
		cerrado = tipo not in TIPOS_EXTERIORES
	if suelo is not None and suelo not in SUELOS:
		raise ErrorEdicion(_("«{suelo}» no es un suelo conocido. Suelos: {suelos}.").format(suelo=suelo, suelos=", ".join(SUELOS)))
	if acustica is not None and acustica not in ACUSTICAS:
		raise ErrorEdicion(
			_("«{acustica}» no es una acústica conocida. Acústicas: {lista}.").format(acustica=acustica, lista=", ".join(ACUSTICAS))
		)
	if (cerrado or macizo) and not permitir_solape:
		for otro in planta.espacios:
			if (otro.cerrado or otro.macizo) and len(otro.contorno) >= 3 and geo.area_interseccion(puntos, otro.contorno) > 0.01:
				raise ErrorEdicion(
					_("«{nombre}» se solaparía con «{otro}». Cambie la posición o las medidas.").format(nombre=nombre, otro=otro.nombre)
				)
	espacio = Espacio(
		nombre=nombre,
		descripcion=descripcion,
		tipo=tipo,
		contorno=puntos,
		cerrado=bool(cerrado),
		lados_abiertos=sorted({int(i) for i in lados_abiertos}),
		suelo=suelo or SUELO_POR_TIPO.get(tipo, "baldosa"),
		acustica=acustica or ACUSTICA_POR_TIPO.get(tipo, "habitacion"),
		pared_material=pared_material,
		macizo=macizo,
		datos=dict(datos or {}),
	)
	return _registrar(entorno, planta, espacio)


def crear_habitacion_rectangular(
	entorno: Entorno,
	planta: Planta,
	nombre: str,
	x: float,
	y: float,
	ancho: float,
	fondo: float,
	tipo: str = "habitacion",
	**opciones: Any,
) -> Espacio:
	"""Habitación rectangular: (x, y) es su esquina suroeste, ``ancho`` va al este y ``fondo`` al norte.

	Sus lados quedan siempre en este orden: 0 sur, 1 este, 2 norte, 3 oeste.
	``opciones`` son las de ``crear_espacio_poligonal`` (suelo, acustica, descripcion…).
	"""
	ancho = _positivo(ancho, _("ancho"))
	fondo = _positivo(fondo, _("fondo"))
	return crear_espacio_poligonal(entorno, planta, nombre, geo.rectangulo(float(x), float(y), ancho, fondo), tipo=tipo, **opciones)


def crear_habitacion_adosada(
	entorno: Entorno,
	planta: Planta,
	nombre: str,
	junto_a: Espacio,
	lado: str,
	ancho: float,
	fondo: float,
	alineacion: str = "inicio",
	desplazamiento: float | None = None,
	tipo: str = "habitacion",
	**opciones: Any,
) -> Espacio:
	"""Habitación rectangular pegada a otra por uno de sus lados, compartiendo pared.

	``lado`` es el lado de ``junto_a`` al que se adosa. ``ancho`` va siempre
	de oeste a este y ``fondo`` de sur a norte. A lo largo de la pared común,
	``alineacion`` vale inicio (extremos oeste o sur igualados), centro o fin;
	``desplazamiento`` (metros desde el inicio de ``junto_a``) manda sobre ella.
	"""
	if lado not in LADOS:
		raise ErrorEdicion(_("«{lado}» no es un lado. Lados: norte, sur, este, oeste.").format(lado=lado))
	if alineacion not in ("inicio", "centro", "fin"):
		raise ErrorEdicion(_("«{valor}» no es una alineación. Alineaciones: inicio, centro, fin.").format(valor=alineacion))
	ancho = _positivo(ancho, _("ancho"))
	fondo = _positivo(fondo, _("fondo"))
	x0, y0, x1, y1 = junto_a.caja()

	def a_lo_largo(inicio: float, fin: float, medida: float) -> float:
		if desplazamiento is not None:
			return inicio + float(desplazamiento)
		if alineacion == "fin":
			return fin - medida
		if alineacion == "centro":
			return (inicio + fin) / 2.0 - medida / 2.0
		return inicio

	if lado == "este":
		x, y = x1, a_lo_largo(y0, y1, fondo)
	elif lado == "oeste":
		x, y = x0 - ancho, a_lo_largo(y0, y1, fondo)
	elif lado == "norte":
		x, y = a_lo_largo(x0, x1, ancho), y1
	else:
		x, y = a_lo_largo(x0, x1, ancho), y0 - fondo
	return crear_habitacion_rectangular(entorno, planta, nombre, x, y, ancho, fondo, tipo=tipo, **opciones)


def pared_compartida(espacio_a: Espacio, espacio_b: Espacio) -> tuple[Punto, Punto] | None:
	"""Tramo de pared que comparten dos espacios (el más largo si hay varios), o None."""
	mejor: tuple[float, Punto, Punto] | None = None
	for a, b in espacio_a.lados():
		largo = geo.distancia(a, b)
		if largo < 1e-6:
			continue
		for c, d in espacio_b.lados():
			intervalo = geo.intervalo_sobre_segmento(a, b, c, d, TOLERANCIA_PARED)
			if intervalo is None:
				continue
			ux, uy = (b[0] - a[0]) / largo, (b[1] - a[1]) / largo
			p = (a[0] + ux * intervalo[0], a[1] + uy * intervalo[0])
			q = (a[0] + ux * intervalo[1], a[1] + uy * intervalo[1])
			if mejor is None or intervalo[1] - intervalo[0] > mejor[0]:
				mejor = (intervalo[1] - intervalo[0], p, q)
	if mejor is None or mejor[0] < 0.05:
		return None
	return _ordenar_tramo(mejor[1], mejor[2])


def _ordenar_tramo(p: Punto, q: Punto) -> tuple[Punto, Punto]:
	"""Pone primero el extremo oeste (tramos horizontales) o sur (verticales)."""
	eje = 0 if abs(q[0] - p[0]) >= abs(q[1] - p[1]) else 1
	return (p, q) if p[eje] <= q[eje] else (q, p)


def vecinos(planta: Planta, espacio: Espacio) -> list[tuple[Espacio, str]]:
	"""Espacios que comparten pared con uno dado, con el lado (norte, este…) por el que están."""
	resultado: list[tuple[Espacio, str]] = []
	x0, y0, x1, y1 = espacio.caja()
	centro = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
	# Solo pueden compartir pared los espacios cuya caja toca esta (con la tolerancia de pared):
	# el índice de la planta los da en el orden de la lista, sin cruzar lados con todo el barrio.
	for otro in planta.indice_espacios().en_caja(x0, y0, x1, y1, TOLERANCIA_PARED + 1e-6):
		if otro is espacio or len(otro.contorno) < 3:
			continue
		tramo = pared_compartida(espacio, otro)
		if tramo is None:
			continue
		resultado.append((otro, _lado_del_tramo(espacio, tramo, centro)))
	return resultado


def _lado_del_tramo(espacio: Espacio, tramo: tuple[Punto, Punto], centro: Punto | None = None) -> str:
	"""Lado (norte, este, sur, oeste) del espacio en el que está un tramo de su contorno."""
	medio = geo.punto_medio(*tramo)
	base = geo.rumbo_entre(*tramo)
	for candidato in (base + 90.0, base - 90.0):
		fuera = geo.punto_a_distancia(medio, candidato, 0.05)
		if not geo.punto_en_poligono(fuera, espacio.contorno):
			return geo.lado_cardinal(candidato)
	return geo.lado_cardinal(geo.rumbo_entre(centro or espacio.centro(), medio))


# ── Aberturas y paredes ──────────────────────────────────────────────────────


def aberturas_de(planta: Planta, espacio: Espacio) -> list[Abertura]:
	"""Aberturas que están sobre algún lado del espacio.

	Antes de cruzar la abertura con cada lado se mira si su caja toca la del
	espacio (con la tolerancia de pared): casi ninguna lo hace, y así describir
	o construir el árbol de un barrio con miles de puertas no tarda segundos.
	"""
	resultado: list[Abertura] = []
	if len(espacio.contorno) < 2:
		return resultado
	margen = TOLERANCIA_PARED + 1e-6
	ex0, ey0, ex1, ey1 = geo.caja(espacio.contorno)
	lados = espacio.lados()
	for abertura in planta.aberturas:
		(ax, ay), (bx, by) = abertura.a, abertura.b
		if min(ax, bx) > ex1 + margen or max(ax, bx) < ex0 - margen or min(ay, by) > ey1 + margen or max(ay, by) < ey0 - margen:
			continue
		for a, b in lados:
			if geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, TOLERANCIA_PARED) is not None:
				resultado.append(abertura)
				break
	return resultado


def aberturas_por_espacio(planta: Planta) -> dict[int, list[Abertura]]:
	"""Las aberturas de TODOS los espacios de una planta de una vez: ``id(espacio)`` → lo que daría ``aberturas_de``.

	Para el árbol del Estudio y la descripción del entorno, que piden las
	aberturas de cada espacio: llamar a ``aberturas_de`` espacio por espacio
	cruza cada puerta con cada espacio. Aquí cada abertura solo se prueba con
	los espacios cuya caja toca la suya (índice espacial de la planta). Cada
	lista sale en el orden de ``planta.aberturas``, como en ``aberturas_de``.
	"""
	resultado: dict[int, list[Abertura]] = {id(espacio): [] for espacio in planta.espacios}
	indice = planta.indice_espacios()
	for abertura in planta.aberturas:
		for espacio in espacios_bajo_abertura(planta, abertura, indice):
			resultado[id(espacio)].append(abertura)
	return resultado


def espacios_bajo_abertura(planta: Planta, abertura: Abertura, indice: IndiceEspacios | None = None) -> list[Espacio]:
	"""Espacios (en el orden de la planta) en cuyos lados está la abertura: aquellos para los que ``aberturas_de`` la daría."""
	indice = indice if indice is not None else planta.indice_espacios()
	x0, y0, x1, y1 = geo.caja((abertura.a, abertura.b))
	candidatos = indice.en_caja(x0, y0, x1, y1, TOLERANCIA_PARED + 1e-6)
	# Los espacios de dos puntos no van al índice (no tienen superficie), pero ``aberturas_de`` sí los mira.
	lineales = indice.lineales
	if lineales:
		elegidos = {id(espacio) for espacio in (*candidatos, *lineales)}
		candidatos = [espacio for espacio in planta.espacios if id(espacio) in elegidos]
	encontrados: list[Espacio] = []
	for espacio in candidatos:
		for a, b in espacio.lados():
			if geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, TOLERANCIA_PARED) is not None:
				encontrados.append(espacio)
				break
	return encontrados


def espacios_de_abertura(planta: Planta, abertura: Abertura) -> list[Espacio]:
	"""Espacios que une una abertura: los que hay a un lado y a otro de ella."""
	medio = abertura.centro()
	base = geo.rumbo_entre(abertura.a, abertura.b)
	encontrados: list[Espacio] = []
	for candidato in (base + 90.0, base - 90.0):
		punto = geo.punto_a_distancia(medio, candidato, 0.15)
		espacio = planta.espacio_en(punto[0], punto[1])
		if espacio is not None and not any(espacio is e for e in encontrados):
			encontrados.append(espacio)
	return encontrados


def _situacion_en_lado(espacio: Espacio, abertura: Abertura) -> tuple[str, float] | None:
	"""(lado, metros desde el inicio del lado) de una abertura sobre el contorno de un espacio."""
	for a, b in espacio.lados():
		if geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, TOLERANCIA_PARED) is None:
			continue
		lado = _lado_del_tramo(espacio, (a, b))
		inicio, _fin = _ordenar_tramo(a, b)
		return lado, min(geo.distancia(inicio, abertura.a), geo.distancia(inicio, abertura.b))
	return None


def _crear_abertura(
	entorno: Entorno,
	planta: Planta,
	inicio: Punto,
	fin: Punto,
	desplazamiento: float | None,
	ancho: float,
	tipo: str,
	estado: str | None,
	hoja: str | None,
	nombre: str,
	descripcion: str,
	material: str,
	es_salida: bool,
	donde: str,
	primero: Espacio | None = None,
) -> Abertura:
	"""Crea una abertura de ``ancho`` metros sobre el tramo inicio→fin; centrada si no hay desplazamiento.

	``primero`` es el espacio desde el que se pidió: se nombra antes en «Puerta entre A y B».
	"""
	if tipo not in TIPOS_ABERTURA:
		raise ErrorEdicion(_("«{tipo}» no es un tipo de abertura. Tipos: {tipos}.").format(tipo=tipo, tipos=", ".join(TIPOS_ABERTURA)))
	ancho = _positivo(ancho, _("ancho"))
	largo = geo.distancia(inicio, fin)
	if desplazamiento is None:
		desplazamiento = (largo - ancho) / 2.0
	if desplazamiento < -1e-6 or desplazamiento + ancho > largo + 1e-6:
		raise ErrorEdicion(
			_("Una abertura de {ancho} a {desplazamiento} del inicio no cabe en {donde}, que mide {largo}.").format(
				ancho=_metros(ancho), desplazamiento=_metros(max(desplazamiento, 0.0)), donde=donde, largo=_metros(largo)
			)
		)
	ux, uy = (fin[0] - inicio[0]) / largo, (fin[1] - inicio[1]) / largo
	a = (inicio[0] + ux * desplazamiento, inicio[1] + uy * desplazamiento)
	b = (inicio[0] + ux * (desplazamiento + ancho), inicio[1] + uy * (desplazamiento + ancho))
	for otra in planta.aberturas:
		intervalo = geo.intervalo_sobre_segmento(a, b, otra.a, otra.b, TOLERANCIA_PARED)
		if intervalo is not None and intervalo[1] - intervalo[0] > 0.01:
			raise ErrorEdicion(_("En ese tramo ya está «{otra}». Elija otro desplazamiento.").format(otra=otra.nombre or otra.id))
	if estado is None:
		estado = "abierta" if tipo == "hueco" else "cerrada"
	if estado not in ESTADOS_ABERTURA:
		raise ErrorEdicion(_("«{estado}» no es un estado. Estados: abierta, cerrada, con_llave.").format(estado=estado))
	if hoja is None:
		hoja = "ninguna" if tipo == "hueco" else "batiente"
	if hoja not in HOJAS:
		raise ErrorEdicion(_("«{hoja}» no es un tipo de hoja. Hojas: {hojas}.").format(hoja=hoja, hojas=", ".join(HOJAS)))
	abertura = Abertura(
		nombre=nombre, descripcion=descripcion, tipo=tipo, a=a, b=b, estado=estado, hoja=hoja, material=material, es_salida=es_salida
	)
	if not abertura.nombre:
		unidos = espacios_de_abertura(planta, abertura)
		unidos.sort(key=lambda espacio: 0 if espacio is primero else 1)
		visible = nombre_visible(TIPOS_ABERTURA, tipo)
		if tipo == "hueco":
			visible = _("Hueco")
		if len(unidos) >= 2:
			abertura.nombre = _("{tipo} entre {a} y {b}").format(tipo=visible, a=unidos[0].nombre, b=unidos[1].nombre)
		elif unidos:
			abertura.nombre = _("{tipo} de {a}").format(tipo=visible, a=unidos[0].nombre)
		else:
			abertura.nombre = visible
	return _registrar(entorno, planta, abertura)


def anadir_puerta(
	entorno: Entorno,
	planta: Planta,
	espacio: Espacio,
	lado: str,
	desplazamiento: float | None = None,
	ancho: float = ANCHO_PUERTA,
	tipo: str = "puerta",
	estado: str | None = None,
	hoja: str | None = None,
	nombre: str = "",
	descripcion: str = "",
	material: str = "madera",
	es_salida: bool = False,
) -> Abertura:
	"""Abre una puerta (o hueco, ventana o portal) en un lado de un espacio.

	``desplazamiento`` son los metros desde el inicio del lado (su extremo
	oeste o sur) hasta el borde de la puerta; sin él queda centrada. Si no se
	da nombre se compone con los espacios que une («Puerta entre Cocina y
	Pasillo»), detectando sola cuál es el vecino al otro lado de la pared.
	"""
	encontrado = lado_de_espacio(espacio, lado)
	if encontrado is None:
		raise ErrorEdicion(_("«{espacio}» no tiene pared en el lado «{lado}».").format(espacio=espacio.nombre, lado=lado))
	_indice, inicio, fin = encontrado
	donde = _("la pared {lado} de «{espacio}»").format(lado=_lado_visible(lado), espacio=espacio.nombre)
	return _crear_abertura(
		entorno, planta, inicio, fin, desplazamiento, ancho, tipo, estado, hoja, nombre, descripcion, material, es_salida, donde, espacio
	)


def anadir_puerta_entre(
	entorno: Entorno,
	planta: Planta,
	espacio_a: Espacio,
	espacio_b: Espacio,
	desplazamiento: float | None = None,
	ancho: float = ANCHO_PUERTA,
	tipo: str = "puerta",
	estado: str | None = None,
	hoja: str | None = None,
	nombre: str = "",
	descripcion: str = "",
	material: str = "madera",
	es_salida: bool = False,
) -> Abertura:
	"""Abre una puerta en la pared que comparten dos espacios (centrada si no se dice otra cosa).

	``desplazamiento`` se mide desde el extremo oeste o sur del tramo compartido.
	"""
	tramo = pared_compartida(espacio_a, espacio_b)
	if tramo is None:
		raise ErrorEdicion(_("«{a}» y «{b}» no comparten ninguna pared.").format(a=espacio_a.nombre, b=espacio_b.nombre))
	donde = _("la pared entre «{a}» y «{b}»").format(a=espacio_a.nombre, b=espacio_b.nombre)
	return _crear_abertura(
		entorno,
		planta,
		tramo[0],
		tramo[1],
		desplazamiento,
		ancho,
		tipo,
		estado,
		hoja,
		nombre,
		descripcion,
		material,
		es_salida,
		donde,
		espacio_a,
	)


def anadir_portal(
	entorno: Entorno,
	planta: Planta,
	espacio: Espacio,
	lado: str,
	desplazamiento: float | None = None,
	ancho: float = ANCHO_PORTAL,
	nombre: str = "",
	estado: str = "cerrada",
	es_salida: bool = False,
	descripcion: str = "",
) -> Abertura:
	"""Portal en la fachada de un edificio: pertenece a la vez al edificio y a la calle."""
	return anadir_puerta(
		entorno,
		planta,
		espacio,
		lado,
		desplazamiento,
		ancho,
		tipo="portal",
		estado=estado,
		nombre=nombre,
		descripcion=descripcion,
		material="metal",
		es_salida=es_salida,
	)


def anadir_pared(
	entorno: Entorno,
	planta: Planta,
	a: Punto,
	b: Punto,
	nombre: str = "",
	grosor: float = 0.1,
	material: str = "ladrillo",
	bloquea_paso: bool = True,
	bloquea_sonido: bool = True,
	altura: float = 2.5,
	descripcion: str = "",
) -> Pared:
	"""Añade un tabique, valla o muro suelto entre dos puntos."""
	a, b = (float(a[0]), float(a[1])), (float(b[0]), float(b[1]))
	if geo.distancia(a, b) < 0.01:
		raise ErrorEdicion(_("Los dos extremos de la pared están en el mismo punto."))
	pared = Pared(
		nombre=nombre or _("Pared"),
		descripcion=descripcion,
		a=a,
		b=b,
		grosor=_positivo(grosor, _("grosor")),
		material=material,
		bloquea_paso=bloquea_paso,
		bloquea_sonido=bloquea_sonido,
		altura=_positivo(altura, _("altura")),
	)
	return _registrar(entorno, planta, pared)


# ── Sonidos, referencias y suelos ────────────────────────────────────────────


def anadir_fuente(
	entorno: Entorno,
	planta: Planta,
	nombre: str,
	x: float,
	y: float,
	sonido: str,
	volumen: float = 1.0,
	radio: float = 12.0,
	bucle: bool = True,
	intervalo: float = 0.0,
	altura: float = 1.0,
	descripcion: str = "",
) -> FuenteSonido:
	"""Añade una fuente de sonido fija (un frigorífico, un reloj, una fuente)."""
	if not str(sonido).strip():
		raise ErrorEdicion(_("Hay que indicar qué sonido emite «{nombre}».").format(nombre=nombre))
	fuente = FuenteSonido(
		nombre=nombre,
		descripcion=descripcion,
		x=float(x),
		y=float(y),
		sonido=str(sonido),
		volumen=float(volumen),
		radio=_positivo(radio, _("radio")),
		bucle=bucle,
		intervalo=float(intervalo),
		altura=float(altura),
	)
	return _registrar(entorno, planta, fuente)


def anadir_referencia(
	entorno: Entorno, planta: Planta, nombre: str, x: float, y: float, tipo: str = "punto", descripcion: str = "", permanente: bool = True
) -> Referencia:
	"""Añade un punto de interés o de referencia."""
	referencia = Referencia(nombre=nombre, descripcion=descripcion, x=float(x), y=float(y), tipo=tipo, permanente=permanente)
	return _registrar(entorno, planta, referencia)


def anadir_zona_suelo(
	entorno: Entorno, planta: Planta, nombre: str, contorno: Sequence[Punto], suelo: str, descripcion: str = ""
) -> ZonaSuelo:
	"""Añade un trozo de suelo distinto (una alfombra, una banda de pavimento táctil)."""
	if suelo not in SUELOS:
		raise ErrorEdicion(_("«{suelo}» no es un suelo conocido. Suelos: {suelos}.").format(suelo=suelo, suelos=", ".join(SUELOS)))
	puntos = geo.orientar_antihorario(contorno)
	if len(puntos) < 3 or geo.area(puntos) < 1e-4:
		raise ErrorEdicion(_("La zona de suelo «{nombre}» no encierra superficie.").format(nombre=nombre))
	return _registrar(entorno, planta, ZonaSuelo(nombre=nombre, descripcion=descripcion, contorno=puntos, suelo=suelo))


def crear_parada(entorno: Entorno, planta: Planta, nombre: str, x: float, y: float, descripcion: str = "") -> Referencia:
	"""Marca una parada de transporte (autobús, tranvía, taxi) como referencia permanente."""
	return anadir_referencia(entorno, planta, nombre, x, y, tipo="parada", descripcion=descripcion)


# ── Conectores entre plantas ─────────────────────────────────────────────────


def _dos_plantas(planta_abajo: Planta, planta_arriba: Planta) -> None:
	if planta_abajo is planta_arriba or planta_abajo.id == planta_arriba.id:
		raise ErrorEdicion(_("Una escalera o rampa tiene que unir dos plantas distintas."))
	if planta_abajo.altura_m > planta_arriba.altura_m:
		raise ErrorEdicion(
			_("«{abajo}» está más alta que «{arriba}»: páselas en el orden contrario.").format(
				abajo=planta_abajo.nombre, arriba=planta_arriba.nombre
			)
		)


def crear_escalera(
	entorno: Entorno,
	planta_abajo: Planta,
	planta_arriba: Planta,
	boca: Punto,
	rumbo: float,
	longitud: float,
	peldanos: int,
	nombre: str = "",
	ancho: float = 1.0,
	pasamanos: str = "ambos",
	boca_arriba: Punto | None = None,
	rumbo_arriba: float | None = None,
	tipo: str = "escalera",
	descripcion: str = "",
) -> Conector:
	"""Escalera de un tramo entre dos plantas.

	``boca`` es el punto de abajo donde se empieza a subir y ``rumbo`` hacia
	dónde se sube. Arriba se sale, si no se dice otra cosa, ``longitud``
	metros más allá en la misma dirección (una escalera recta vista en planta).
	"""
	_dos_plantas(planta_abajo, planta_arriba)
	if tipo not in ("escalera", "escalera_mecanica"):
		raise ErrorEdicion(_("«{tipo}» no es un tipo de escalera.").format(tipo=tipo))
	if pasamanos not in PASAMANOS:
		raise ErrorEdicion(
			_("«{valor}» no es una opción de pasamanos. Opciones: izquierda, derecha, ambos, ninguno.").format(valor=pasamanos)
		)
	longitud = _positivo(longitud, _("longitud"))
	if int(peldanos) < 1:
		raise ErrorEdicion(_("Una escalera necesita al menos un peldaño."))
	rumbo = geo.normalizar_rumbo(rumbo)
	arriba = boca_arriba if boca_arriba is not None else geo.punto_a_distancia(boca, rumbo, longitud)
	tramo = Tramo(
		desde=Posicion(planta_abajo.id, float(boca[0]), float(boca[1]), rumbo),
		hasta=Posicion(
			planta_arriba.id, float(arriba[0]), float(arriba[1]), geo.normalizar_rumbo(rumbo if rumbo_arriba is None else rumbo_arriba)
		),
		longitud_m=longitud,
		peldanos=int(peldanos),
	)
	conector = Conector(
		id=entorno.nuevo_id("con"),
		nombre=nombre or nombre_visible(TIPOS_CONECTOR, tipo),
		descripcion=descripcion,
		tipo=tipo,
		tramos=[tramo],
		datos={"pasamanos": pasamanos, "anchura": _positivo(ancho, _("ancho"))},
	)
	entorno.conectores.append(conector)
	return conector


def crear_rampa(
	entorno: Entorno,
	planta_abajo: Planta,
	planta_arriba: Planta,
	boca: Punto,
	rumbo: float,
	longitud: float,
	nombre: str = "",
	ancho: float = 1.2,
	pasamanos: str = "ambos",
	boca_arriba: Punto | None = None,
	rumbo_arriba: float | None = None,
	descripcion: str = "",
) -> Conector:
	"""Rampa entre dos plantas; anota su pendiente en tanto por ciento."""
	_dos_plantas(planta_abajo, planta_arriba)
	if pasamanos not in PASAMANOS:
		raise ErrorEdicion(
			_("«{valor}» no es una opción de pasamanos. Opciones: izquierda, derecha, ambos, ninguno.").format(valor=pasamanos)
		)
	longitud = _positivo(longitud, _("longitud"))
	rumbo = geo.normalizar_rumbo(rumbo)
	arriba = boca_arriba if boca_arriba is not None else geo.punto_a_distancia(boca, rumbo, longitud)
	tramo = Tramo(
		desde=Posicion(planta_abajo.id, float(boca[0]), float(boca[1]), rumbo),
		hasta=Posicion(
			planta_arriba.id, float(arriba[0]), float(arriba[1]), geo.normalizar_rumbo(rumbo if rumbo_arriba is None else rumbo_arriba)
		),
		longitud_m=longitud,
		peldanos=0,
	)
	desnivel = planta_arriba.altura_m - planta_abajo.altura_m
	conector = Conector(
		id=entorno.nuevo_id("con"),
		nombre=nombre or _("Rampa"),
		descripcion=descripcion,
		tipo="rampa",
		tramos=[tramo],
		datos={"pasamanos": pasamanos, "anchura": _positivo(ancho, _("ancho")), "pendiente_pct": round(desnivel / longitud * 100.0, 1)},
	)
	entorno.conectores.append(conector)
	return conector


def crear_ascensor(
	entorno: Entorno,
	plantas: Sequence[Planta],
	punto: Punto,
	rumbo: float,
	nombre: str = "",
	aviso_hablado: bool = True,
	descripcion: str = "",
) -> Conector:
	"""Ascensor con una parada en cada planta indicada.

	``punto`` es el sitio delante de la puerta (el mismo en todas las plantas,
	porque el hueco es vertical) y ``rumbo`` hacia dónde se mira para entrar en la cabina.
	"""
	unicas: list[Planta] = []
	for planta in plantas:
		if not any(planta is otra for otra in unicas):
			unicas.append(planta)
	if len(unicas) < 2:
		raise ErrorEdicion(_("Un ascensor tiene que parar al menos en dos plantas."))
	unicas.sort(key=lambda p: p.nivel)
	rumbo = geo.normalizar_rumbo(rumbo)
	conector = Conector(
		id=entorno.nuevo_id("con"),
		nombre=nombre or _("Ascensor"),
		descripcion=descripcion,
		tipo="ascensor",
		paradas=[Parada(planta=p.id, puerta=Posicion(p.id, float(punto[0]), float(punto[1]), rumbo)) for p in unicas],
		datos={"aviso_hablado": aviso_hablado, "puerta": "automatica"},
	)
	entorno.conectores.append(conector)
	return conector


# ── Exteriores ───────────────────────────────────────────────────────────────


@dataclass
class Calle:
	"""Lo que genera ``crear_calle``: la vía y los espacios que la dibujan."""

	via: Via
	calzada: Espacio | None = None
	aceras: list[Espacio] = field(default_factory=list)

	def _acera(self, lado: str) -> Espacio | None:
		for acera in self.aceras:
			if acera.datos.get("lado") == lado:
				return acera
		return None

	@property
	def acera_izquierda(self) -> Espacio | None:
		"""Acera a la izquierda del sentido del eje (su primer tramo si un cruce la partió)."""
		return self._acera("izquierda")

	@property
	def acera_derecha(self) -> Espacio | None:
		"""Acera a la derecha del sentido del eje (su primer tramo si un cruce la partió)."""
		return self._acera("derecha")


def calle_de(planta: Planta, via: Via | Calle) -> Calle:
	"""Reúne la vía con su calzada y sus aceras tal como están ahora en la planta."""
	if isinstance(via, Calle):
		via = via.via
	calle = Calle(via=via)
	for espacio in planta.espacios:
		if espacio.datos.get("via") != via.id:
			continue
		if espacio.tipo == "acera":
			calle.aceras.append(espacio)
		elif espacio.tipo == "calzada" and not espacio.datos.get("cruce") and calle.calzada is None:
			calle.calzada = espacio
	return calle


def crear_calle(
	entorno: Entorno,
	planta: Planta,
	nombre: str,
	eje: Sequence[Punto],
	ancho_calzada: float = 6.0,
	ancho_acera: float = 2.0,
	carriles: int = 2,
	sentido: str = "doble",
	trafico: int = 1,
	velocidad_kmh: float = 30.0,
	descripcion: str = "",
) -> Calle:
	"""Crea una calle a partir de su eje: la vía (para el tráfico), la calzada y dos aceras.

	Las aceras se nombran por el lado hacia el que quedan («Acera norte de
	Calle Mayor»). Con ``ancho_acera`` 0 no se crean aceras.
	"""
	puntos = [(float(p[0]), float(p[1])) for p in eje]
	if len(puntos) < 2 or geo.longitud_linea(puntos) < 1.0:
		raise ErrorEdicion(_("El eje de una calle necesita al menos dos puntos separados."))
	ancho_calzada = _positivo(ancho_calzada, _("ancho de la calzada"))
	if ancho_acera < 0:
		raise ErrorEdicion(_("El ancho de la acera no puede ser negativo."))
	if sentido not in SENTIDOS_VIA:
		raise ErrorEdicion(_("«{sentido}» no es un sentido. Sentidos: doble, ida, vuelta.").format(sentido=sentido))
	if int(trafico) not in NIVELES_TRAFICO:
		raise ErrorEdicion(_("El tráfico va de 0 (ninguno) a 3 (intenso)."))
	via = Via(
		nombre=nombre,
		descripcion=descripcion,
		eje=puntos,
		ancho=ancho_calzada,
		carriles=max(1, int(carriles)),
		sentido=sentido,
		trafico=int(trafico),
		velocidad_kmh=float(velocidad_kmh),
	)
	_registrar(entorno, planta, via)
	mitad = ancho_calzada / 2.0
	borde_derecho = geo.desplazar_linea(puntos, mitad)
	borde_izquierdo = geo.desplazar_linea(puntos, -mitad)
	calle = Calle(via=via)
	calle.calzada = crear_espacio_poligonal(
		entorno,
		planta,
		_("Calzada de {calle}").format(calle=nombre),
		borde_derecho + borde_izquierdo[::-1],
		tipo="calzada",
		datos={"via": via.id},
	)
	if ancho_acera > 0:
		rumbo_general = geo.rumbo_entre(puntos[0], puntos[-1])
		for lado, signo, borde in (("izquierda", -1.0, borde_izquierdo), ("derecha", 1.0, borde_derecho)):
			exterior = geo.desplazar_linea(puntos, signo * (mitad + ancho_acera))
			cardinal = geo.lado_cardinal(rumbo_general + signo * 90.0)
			acera = crear_espacio_poligonal(
				entorno,
				planta,
				_("Acera {lado} de {calle}").format(lado=_lado_visible(cardinal), calle=nombre),
				borde + exterior[::-1],
				tipo="acera",
				datos={"via": via.id, "lado": lado, "ancho": float(ancho_acera)},
			)
			calle.aceras.append(acera)
	return calle


def _tramo_en_cruce(via: Via, punto: Punto) -> tuple[Punto, Punto]:
	"""Tramo del eje de la vía más cercano a un punto."""
	_cercano, _distancia, indice = geo.proyeccion_sobre_linea(punto, via.eje)
	return via.eje[indice], via.eje[indice + 1]


def _bordes_de_calzada(via: Via, punto: Punto) -> tuple[tuple[Punto, Punto], tuple[Punto, Punto]]:
	"""Rectas (izquierda, derecha) que limitan la calzada de una vía a la altura de un punto."""
	c, d = _tramo_en_cruce(via, punto)
	izquierda = geo.desplazar_linea([c, d], -via.ancho / 2.0)
	derecha = geo.desplazar_linea([c, d], via.ancho / 2.0)
	return (izquierda[0], izquierda[1]), (derecha[0], derecha[1])


def crear_cruce(entorno: Entorno, planta: Planta, calle_a: Via | Calle, calle_b: Via | Calle, nombre: str = "") -> Espacio:
	"""Resuelve el cruce de dos calles que ya existen y devuelve el espacio del cruce.

	Al cruzarse, las aceras de cada calle pisarían la calzada de la otra. Esta
	función les recorta ese trozo (cada acera queda partida en un tramo a cada
	lado, nombrados por su posición: «…, tramo oeste») y crea un espacio
	«Cruce de A con B» con la superficie común de las dos calzadas.
	"""
	a, b = calle_de(planta, calle_a), calle_de(planta, calle_b)
	if a.via is b.via:
		raise ErrorEdicion(_("Un cruce necesita dos calles distintas."))
	punto: Punto | None = None
	for i in range(len(a.via.eje) - 1):
		for j in range(len(b.via.eje) - 1):
			punto = geo.corte_segmentos(a.via.eje[i], a.via.eje[i + 1], b.via.eje[j], b.via.eje[j + 1])
			if punto is not None:
				break
		if punto is not None:
			break
	if punto is None:
		raise ErrorEdicion(_("«{a}» y «{b}» no se cruzan.").format(a=a.via.nombre, b=b.via.nombre))
	if a.calzada is None or b.calzada is None:
		raise ErrorEdicion(_("A una de las calles le falta la calzada; créelas con «crear calle»."))

	for propia, otra in ((a, b), (b, a)):
		izquierda, derecha = _bordes_de_calzada(otra.via, punto)
		for acera in list(propia.aceras):
			if otra.calzada is None or not geo.poligonos_se_solapan(acera.contorno, otra.calzada.contorno, 0.01):
				continue
			# Lo que queda a la izquierda del borde izquierdo y a la derecha del derecho.
			trozos = [
				geo.recortar_por_semiplano(acera.contorno, izquierda[0], izquierda[1]),
				geo.recortar_por_semiplano(acera.contorno, derecha[1], derecha[0]),
			]
			trozos = [geo.orientar_antihorario(t) for t in trozos if len(t) >= 3 and geo.area(t) > 0.01]
			if not trozos:
				planta.espacios.remove(acera)
				continue
			base = acera.nombre
			for numero, trozo in enumerate(trozos):
				tramo = geo.lado_cardinal(geo.rumbo_entre(punto, geo.centroide(trozo)))
				if numero == 0:
					destino = acera
				else:
					destino = acera.copia()
					destino.id = entorno.nuevo_id("esp")
					planta.espacios.append(destino)
				destino.contorno = trozo
				destino.nombre = _("{acera}, tramo {tramo}").format(acera=base, tramo=_lado_visible(tramo))
				destino.datos["tramo"] = tramo

	izquierda, derecha = _bordes_de_calzada(b.via, punto)
	comun = geo.recortar_por_semiplano(a.calzada.contorno, izquierda[1], izquierda[0])
	comun = geo.recortar_por_semiplano(comun, derecha[0], derecha[1])
	if len(comun) < 3 or geo.area(comun) < 0.01:
		raise ErrorEdicion(_("Las calzadas de «{a}» y «{b}» no llegan a tocarse.").format(a=a.via.nombre, b=b.via.nombre))
	return crear_espacio_poligonal(
		entorno,
		planta,
		nombre or _("Cruce de {a} con {b}").format(a=a.via.nombre, b=b.via.nombre),
		comun,
		tipo="calzada",
		datos={"cruce": True, "vias": [a.via.id, b.via.id], "centro": [round(punto[0], 3), round(punto[1], 3)]},
	)


def crear_paso_peatones(
	entorno: Entorno,
	planta: Planta,
	via: Via | Calle,
	punto: Punto,
	semaforo: bool = False,
	sonoro: bool = False,
	pulsador: bool = False,
	isleta: bool = False,
	ancho: float = 4.0,
	nombre: str = "",
	ciclo: dict[str, Any] | None = None,
	tactil: bool = True,
	descripcion: str = "",
) -> Espacio:
	"""Paso de peatones que cruza una vía a la altura de ``punto`` (se ajusta al eje).

	Crea el espacio del paso (de bordillo a bordillo), una banda de pavimento
	táctil a cada lado y, si hay semáforo, una referencia en cada extremo.
	En ``datos`` quedan semaforo, sonoro, pulsador, isleta, el ciclo en
	segundos, la longitud del cruce y los dos extremos.
	"""
	if isinstance(via, Calle):
		via = via.via
	ancho = _positivo(ancho, _("ancho"))
	if (sonoro or pulsador) and not semaforo:
		raise ErrorEdicion(_("Un paso sin semáforo no puede tener señal sonora ni pulsador."))
	centro, _distancia, indice = geo.proyeccion_sobre_linea((float(punto[0]), float(punto[1])), via.eje)
	rumbo_eje = geo.rumbo_entre(via.eje[indice], via.eje[indice + 1])
	if not nombre:
		nombre = _("Paso de peatones de {calle}").format(calle=via.nombre)
	extremos = [
		geo.punto_a_distancia(centro, rumbo_eje - 90.0, via.ancho / 2.0),
		geo.punto_a_distancia(centro, rumbo_eje + 90.0, via.ancho / 2.0),
	]
	datos: dict[str, Any] = {
		"via": via.id,
		"semaforo": bool(semaforo),
		"sonoro": bool(sonoro),
		"pulsador": bool(pulsador),
		"isleta": bool(isleta),
		"longitud": round(via.ancho, 3),
		"ancho": ancho,
		"rumbo_cruce": round(geo.normalizar_rumbo(rumbo_eje + 90.0), 2),
		"extremos": [[round(p[0], 3), round(p[1], 3)] for p in extremos],
		"zonas": [],
		"referencias": [],
	}
	if semaforo:
		datos["ciclo"] = dict(ciclo) if ciclo else {"verde_peatones_s": 25, "intermitente_s": 5, "rojo_peatones_s": 45}
	paso = crear_espacio_poligonal(
		entorno,
		planta,
		nombre,
		geo.rectangulo_girado(centro[0], centro[1], via.ancho, ancho, rumbo_eje),
		tipo="paso_peatones",
		descripcion=descripcion,
		datos=datos,
	)
	for extremo, giro in zip(extremos, (-90.0, 90.0), strict=True):
		hacia_fuera = rumbo_eje + giro
		cardinal = _lado_visible(geo.lado_cardinal(hacia_fuera))
		if tactil:
			medio = geo.punto_a_distancia(extremo, hacia_fuera, FONDO_TACTIL / 2.0)
			zona = anadir_zona_suelo(
				entorno,
				planta,
				_("Pavimento táctil {lado} de {paso}").format(lado=cardinal, paso=nombre),
				geo.rectangulo_girado(medio[0], medio[1], FONDO_TACTIL, ancho, rumbo_eje),
				"tactil_botones",
			)
			datos["zonas"].append(zona.id)
		if semaforo:
			poste = geo.punto_a_distancia(extremo, hacia_fuera, FONDO_TACTIL / 2.0)
			detalle = []
			if sonoro:
				detalle.append(_("con señal sonora"))
			if pulsador:
				detalle.append(_("con pulsador"))
			referencia = anadir_referencia(
				entorno,
				planta,
				_("Semáforo {lado} de {paso}").format(lado=cardinal, paso=nombre),
				poste[0],
				poste[1],
				tipo="semaforo",
				descripcion=", ".join(detalle),
			)
			datos["referencias"].append(referencia.id)
	if isleta:
		zona = anadir_zona_suelo(
			entorno,
			planta,
			_("Isleta de {paso}").format(paso=nombre),
			geo.rectangulo_girado(centro[0], centro[1], 1.5, ancho, rumbo_eje),
			"acera",
		)
		datos["zonas"].append(zona.id)
	return paso


def crear_manzana(entorno: Entorno, planta: Planta, nombre: str, contorno: Sequence[Punto], descripcion: str = "") -> Espacio:
	"""Manzana o edificio macizo: se ve desde la calle pero no se puede entrar."""
	return crear_espacio_poligonal(entorno, planta, nombre, contorno, tipo="edificio", cerrado=True, macizo=True, descripcion=descripcion)


def crear_edificio(
	entorno: Entorno,
	planta: Planta,
	nombre: str,
	x: float,
	y: float,
	ancho: float,
	fondo: float,
	portal_lado: str | None = None,
	portal_desplazamiento: float | None = None,
	portal_ancho: float = ANCHO_PORTAL,
	portal_nombre: str = "",
	descripcion: str = "",
) -> tuple[Espacio, Abertura | None]:
	"""Edificio macizo rectangular con su portal en una fachada.

	El portal de un edificio macizo es una referencia para orientarse (con su
	número o su nombre): no da paso, porque dentro no hay nada modelado.
	"""
	edificio = crear_manzana(
		entorno, planta, nombre, geo.rectangulo(float(x), float(y), _positivo(ancho, _("ancho")), _positivo(fondo, _("fondo"))), descripcion
	)
	portal = None
	if portal_lado:
		portal = anadir_portal(
			entorno,
			planta,
			edificio,
			portal_lado,
			portal_desplazamiento,
			portal_ancho,
			nombre=portal_nombre or _("Portal de {edificio}").format(edificio=nombre),
		)
	return edificio, portal


# ── Operaciones genéricas ────────────────────────────────────────────────────


def puntos_de(elemento: Any) -> list[Punto]:
	"""Puntos que definen la geometría de cualquier elemento."""
	if isinstance(elemento, (Espacio, ZonaSuelo)):
		return list(elemento.contorno)
	if isinstance(elemento, (Pared, Abertura)):
		return [elemento.a, elemento.b]
	if isinstance(elemento, Objeto):
		return elemento.huella_caja()
	if isinstance(elemento, Via):
		return list(elemento.eje)
	if isinstance(elemento, Conector):
		return [posicion.punto for posicion in elemento.posiciones()]
	if isinstance(elemento, Planta):
		x0, y0, x1, y1 = elemento.caja()
		return [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
	if hasattr(elemento, "x") and hasattr(elemento, "y"):
		return [(elemento.x, elemento.y)]
	raise ErrorEdicion(_("Ese elemento no tiene posición."))


def centro_de(elemento: Any) -> Punto:
	"""Punto que representa a un elemento: su centro."""
	if isinstance(elemento, (Objeto, FuenteSonido, Referencia, Posicion)):
		return elemento.x, elemento.y
	if isinstance(elemento, (Espacio, ZonaSuelo)) and len(elemento.contorno) >= 3:
		return geo.centroide(elemento.contorno)
	puntos = puntos_de(elemento)
	if not puntos:
		raise ErrorEdicion(_("Ese elemento no tiene posición."))
	x0, y0, x1, y1 = geo.caja(puntos)
	return (x0 + x1) / 2.0, (y0 + y1) / 2.0


def _contenido_de(entorno: Entorno, planta: Planta, espacio: Espacio) -> list[Any]:
	"""Lo que «va con» un espacio al moverlo: sus aberturas y lo que tiene dentro.

	Solo se pregunta en qué espacio está a lo que cae dentro de la caja del
	espacio (con la holgura del índice espacial): lo de fuera no puede estar
	en él. Con un barrio de miles de objetos y referencias, preguntarlo de
	todos costaba 35 ms en cada movimiento. El resultado es el mismo.
	"""
	contenido: list[Any] = list(aberturas_de(planta, espacio))
	if len(espacio.contorno) < 3:
		return contenido
	holgura = IndiceEspacios.HOLGURA * 2
	x0, y0, x1, y1 = geo.caja(espacio.contorno)
	x0, y0, x1, y1 = x0 - holgura, y0 - holgura, x1 + holgura, y1 + holgura

	def dentro(x: float, y: float) -> bool:
		return x0 <= x <= x1 and y0 <= y <= y1 and planta.espacio_en(x, y) is espacio

	for lista in (planta.objetos, planta.fuentes, planta.referencias):
		contenido.extend(e for e in lista if dentro(e.x, e.y))
	for zona in planta.zonas:
		if len(zona.contorno) >= 3 and dentro(*geo.centroide(zona.contorno)):
			contenido.append(zona)
	for conector in entorno.conectores:
		for posicion in conector.posiciones():
			if posicion.planta == planta.id and dentro(posicion.x, posicion.y):
				contenido.append(posicion)
	if entorno.inicio.planta == planta.id and dentro(entorno.inicio.x, entorno.inicio.y):
		contenido.append(entorno.inicio)
	return contenido


def _aplicar(elemento: Any, f: Callable[[Punto], Punto], giro: float) -> None:
	"""Aplica una transformación de puntos (y un giro de rumbo) a un elemento."""
	if isinstance(elemento, (Espacio, ZonaSuelo)):
		elemento.contorno = [f(p) for p in elemento.contorno]
	elif isinstance(elemento, (Pared, Abertura)):
		elemento.a, elemento.b = f(elemento.a), f(elemento.b)
	elif isinstance(elemento, Via):
		elemento.eje = [f(p) for p in elemento.eje]
	elif isinstance(elemento, Conector):
		for posicion in elemento.posiciones():
			_aplicar(posicion, f, giro)
	elif isinstance(elemento, (Objeto, Posicion)):
		elemento.x, elemento.y = f((elemento.x, elemento.y))
		elemento.rumbo = geo.normalizar_rumbo(elemento.rumbo + giro)
	elif isinstance(elemento, (FuenteSonido, Referencia)):
		elemento.x, elemento.y = f((elemento.x, elemento.y))
	else:
		raise ErrorEdicion(_("Ese elemento no se puede mover."))


def _transformar(entorno: Entorno, elemento: Any, f: Callable[[Punto], Punto], giro: float, con_contenido: bool) -> None:
	planta, elemento = resolver(entorno, elemento)
	if isinstance(elemento, Planta):
		for hijo in list(elemento.elementos()):
			_aplicar(hijo, f, giro)
		for conector in entorno.conectores:
			for posicion in conector.posiciones():
				if posicion.planta == elemento.id:
					_aplicar(posicion, f, giro)
		if entorno.inicio.planta == elemento.id:
			_aplicar(entorno.inicio, f, giro)
		return
	afectados: list[Any] = [elemento]
	if planta is not None and con_contenido:
		if isinstance(elemento, Espacio):
			afectados.extend(_contenido_de(entorno, planta, elemento))
		elif isinstance(elemento, Via):
			for espacio in planta.espacios:
				if espacio.datos.get("via") == elemento.id or elemento.id in (espacio.datos.get("vias") or []):
					afectados.append(espacio)
					for clave in ("zonas", "referencias"):
						for id_hijo in espacio.datos.get(clave) or []:
							hijo = entorno.elemento(id_hijo)
							if hijo is not None:
								afectados.append(hijo)
	vistos: list[Any] = []
	for afectado in afectados:
		if any(afectado is v for v in vistos):
			continue
		vistos.append(afectado)
		_aplicar(afectado, f, giro)
	for afectado in vistos:
		if isinstance(afectado, Espacio) and "extremos" in afectado.datos:
			afectado.datos["extremos"] = [[round(c, 3) for c in f((float(p[0]), float(p[1])))] for p in afectado.datos["extremos"]]


def mover(entorno: Entorno, elemento: Any, dx: float, dy: float, con_contenido: bool = True) -> None:
	"""Desplaza un elemento (dx al este, dy al norte).

	Una habitación se lleva consigo sus puertas, sus objetos, sus sonidos y
	sus referencias (``con_contenido``); una calle, su calzada y sus aceras;
	una planta, todo lo que contiene.
	"""
	dx, dy = float(dx), float(dy)
	_transformar(entorno, elemento, lambda p: (p[0] + dx, p[1] + dy), 0.0, con_contenido)


def mover_a(entorno: Entorno, elemento: Any, x: float, y: float, con_contenido: bool = True) -> None:
	"""Lleva el centro de un elemento al punto (x, y)."""
	_planta, real = resolver(entorno, elemento)
	centro = centro_de(real)
	mover(entorno, real, float(x) - centro[0], float(y) - centro[1], con_contenido)


def girar(entorno: Entorno, elemento: Any, grados: float, centro: Punto | None = None, con_contenido: bool = True) -> None:
	"""Gira un elemento en el sentido del reloj, alrededor de su centro o del punto dado."""
	_planta, real = resolver(entorno, elemento)
	eje = centro if centro is not None else centro_de(real)
	grados = float(grados)
	_transformar(entorno, real, lambda p: geo.girar_punto(p, eje, grados), grados, con_contenido)


def redimensionar(
	entorno: Entorno,
	elemento: Any,
	ancho: float | None = None,
	fondo: float | None = None,
	alto: float | None = None,
	catalogo: Catalogo | None = None,
) -> None:
	"""Cambia las medidas de un elemento.

	Objeto: ancho, fondo y alto (dentro del rango de su ficha si se pasa el
	catálogo). Espacio o zona de suelo: se escala desde su esquina suroeste
	hasta que su caja mida ``ancho`` por ``fondo``. Abertura: ``ancho``, desde
	su centro. Pared: ``ancho`` es su longitud (desde su primer extremo) y
	``alto`` su altura. Vía: ``ancho`` de la calzada (no rehace las aceras).
	"""
	_planta, real = resolver(entorno, elemento)
	ancho = None if ancho is None else _positivo(ancho, _("ancho"))
	fondo = None if fondo is None else _positivo(fondo, _("fondo"))
	alto = None if alto is None else _positivo(alto, _("alto"))
	if isinstance(real, Objeto):
		definicion = catalogo.definicion_de(real) if catalogo else None
		for dimension, valor in (("ancho", ancho), ("fondo", fondo), ("alto", alto)):
			if valor is None:
				continue
			if definicion is not None:
				minimo, _defecto, maximo = definicion.rango(dimension)
				if not (minimo - 1e-9 <= valor <= maximo + 1e-9):
					raise ErrorEdicion(
						_("«{nombre}» admite un {dimension} de {minimo} a {maximo} metros.").format(
							nombre=real.nombre, dimension=_(dimension), minimo=_m(minimo), maximo=_m(maximo)
						)
					)
			setattr(real, dimension, valor)
		real.variante = ""
	elif isinstance(real, (Espacio, ZonaSuelo)):
		x0, y0, x1, y1 = geo.caja(real.contorno)
		factor_x = 1.0 if ancho is None or x1 - x0 < 1e-9 else ancho / (x1 - x0)
		factor_y = 1.0 if fondo is None or y1 - y0 < 1e-9 else fondo / (y1 - y0)
		real.contorno = [(x0 + (p[0] - x0) * factor_x, y0 + (p[1] - y0) * factor_y) for p in real.contorno]
	elif isinstance(real, Abertura):
		if ancho is None:
			raise ErrorEdicion(_("Para una abertura hay que indicar el ancho."))
		centro = real.centro()
		direccion = geo.rumbo_entre(real.a, real.b)
		real.a = geo.punto_a_distancia(centro, direccion + 180.0, ancho / 2.0)
		real.b = geo.punto_a_distancia(centro, direccion, ancho / 2.0)
	elif isinstance(real, Pared):
		if ancho is not None:
			real.b = geo.punto_a_distancia(real.a, geo.rumbo_entre(real.a, real.b), ancho)
		if alto is not None:
			real.altura = alto
		if fondo is not None:
			real.grosor = fondo
	elif isinstance(real, Via):
		if ancho is None:
			raise ErrorEdicion(_("Para una vía hay que indicar el ancho de la calzada."))
		real.ancho = ancho
	else:
		raise ErrorEdicion(_("Ese elemento no tiene medidas que cambiar."))


def renombrar(entorno: Entorno, elemento: Any, nombre: str) -> None:
	"""Cambia el nombre de un elemento, de una planta o de un conector."""
	_planta, real = resolver(entorno, elemento)
	if not str(nombre).strip():
		raise ErrorEdicion(_("El nombre no puede quedar vacío."))
	real.nombre = str(nombre).strip()


def duplicar(entorno: Entorno, elemento: Any, dx: float = 0.5, dy: float = 0.0, nombre: str = "") -> Any:
	"""Crea una copia de un elemento con id nuevo, desplazada (dx, dy), y la devuelve.

	Una planta se duplica entera, con todos sus elementos, un nivel por encima de la más alta.
	"""
	planta, real = resolver(entorno, elemento)
	if isinstance(real, Planta):
		copia = real.copia()
		copia.id = entorno.nuevo_id("pla")
		copia.nivel = max(p.nivel for p in entorno.plantas) + 1
		copia.altura_m = real.altura_m + (copia.nivel - real.nivel) * ALTURA_ENTRE_PLANTAS
		copia.nombre = nombre or _("{nombre} (copia)").format(nombre=real.nombre)
		entorno.plantas.append(copia)
		cambios: dict[str, str] = {}
		for hijo in copia.elementos():
			nuevo = entorno.id_para(hijo)
			cambios[hijo.id] = nuevo
			hijo.id = nuevo
		for espacio in copia.espacios:
			for clave in ("via", "vias", "zonas", "referencias"):
				valor = espacio.datos.get(clave)
				if isinstance(valor, str):
					espacio.datos[clave] = cambios.get(valor, valor)
				elif isinstance(valor, list):
					espacio.datos[clave] = [cambios.get(v, v) for v in valor]
		return copia
	copia = real.copia()
	copia.nombre = nombre or _("{nombre} (copia)").format(nombre=real.nombre)
	if isinstance(real, Conector):
		copia.id = entorno.nuevo_id("con")
		entorno.conectores.append(copia)
	else:
		if planta is None:
			raise ErrorEdicion(_("Ese elemento no está en ninguna planta."))
		copia.id = entorno.id_para(copia)
		lista = planta.lista_de(copia)
		if lista is None:
			raise ErrorEdicion(_("Ese elemento no se puede duplicar."))
		lista.append(copia)
	if dx or dy:
		mover(entorno, copia, dx, dy, con_contenido=False)
	return copia


def _sobre_algun_contorno(planta: Planta, abertura: Abertura) -> bool:
	for espacio in planta.espacios:
		if not (espacio.cerrado or espacio.macizo):
			continue
		for a, b in espacio.lados():
			if geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, TOLERANCIA_PARED) is not None:
				return True
	return any(geo.intervalo_sobre_segmento(p.a, p.b, abertura.a, abertura.b, TOLERANCIA_PARED) is not None for p in planta.paredes)


def borrar(entorno: Entorno, elemento: Any) -> list[str]:
	"""Borra un elemento y lo que depende de él; devuelve los ids borrados.

	- Un espacio o una pared se llevan las puertas que se quedarían sin pared.
	- Una vía se lleva su calzada, sus aceras y sus pasos de peatones.
	- Un paso de peatones, su pavimento táctil y sus semáforos.
	- Una planta, sus elementos y los tramos y paradas de conectores que llegaban a ella
	  (un conector que se queda sin dos plantas desaparece).
	"""
	planta, real = resolver(entorno, elemento)
	borrados: list[str] = []
	if isinstance(real, Planta):
		borrados.extend(hijo.id for hijo in real.elementos())
		borrados.append(real.id)
		entorno.plantas = [p for p in entorno.plantas if p is not real]
		for conector in list(entorno.conectores):
			conector.tramos = [t for t in conector.tramos if real.id not in (t.desde.planta, t.hasta.planta)]
			conector.paradas = [p for p in conector.paradas if p.planta != real.id]
			if len(conector.plantas()) < 2:
				entorno.conectores.remove(conector)
				borrados.append(conector.id)
		if entorno.inicio.planta == real.id:
			entorno.inicio = Posicion(planta=entorno.plantas[0].id if entorno.plantas else "")
		return borrados
	if isinstance(real, Conector):
		entorno.conectores = [c for c in entorno.conectores if c is not real]
		return [real.id]
	if planta is None:
		raise ErrorEdicion(_("Ese elemento no está en ninguna planta."))

	def quitar(hijo: Any) -> None:
		lista = planta.lista_de(hijo)
		if lista is not None and any(hijo is e for e in lista):
			lista[:] = [e for e in lista if e is not hijo]
			borrados.append(hijo.id)

	if isinstance(real, Via):
		for espacio in list(planta.espacios):
			if espacio.datos.get("via") == real.id or real.id in (espacio.datos.get("vias") or []):
				for clave in ("zonas", "referencias"):
					for id_hijo in espacio.datos.get(clave) or []:
						hijo = entorno.elemento(id_hijo)
						if hijo is not None:
							quitar(hijo)
				quitar(espacio)
	if isinstance(real, Espacio):
		for clave in ("zonas", "referencias"):
			for id_hijo in real.datos.get(clave) or []:
				hijo = entorno.elemento(id_hijo)
				if hijo is not None:
					quitar(hijo)
	propias = aberturas_de(planta, real) if isinstance(real, Espacio) else []
	if isinstance(real, Pared):
		propias = [a for a in planta.aberturas if geo.intervalo_sobre_segmento(real.a, real.b, a.a, a.b, TOLERANCIA_PARED) is not None]
	quitar(real)
	for abertura in propias:
		if not _sobre_algun_contorno(planta, abertura):
			quitar(abertura)
	return borrados


# ── Medir ────────────────────────────────────────────────────────────────────


@dataclass
class Medida:
	"""Resultado de ``medir``: cómo está un elemento respecto de otro."""

	distancia: float  # entre centros, en metros
	rumbo: float  # del primero hacia el segundo
	separacion: float  # hueco libre entre sus contornos (0 si se tocan)
	misma_planta: bool = True
	desnivel: float = 0.0  # metros que hay que subir (negativo: bajar)

	def texto(self) -> str:
		"""Frase para decir la medida: «3,2 metros hacia el noreste (separación libre: 1,5 metros)»."""
		frase = _("{distancia} hacia el {punto}").format(distancia=_metros(self.distancia), punto=geo.punto_cardinal(self.rumbo))
		if abs(self.separacion - self.distancia) > 0.005:
			frase += _(" (separación libre: {metros})").format(metros=_metros(self.separacion))
		if not self.misma_planta:
			if self.desnivel > 0:
				frase += _(", en otra planta, {metros} más arriba").format(metros=_metros(self.desnivel))
			elif self.desnivel < 0:
				frase += _(", en otra planta, {metros} más abajo").format(metros=_metros(-self.desnivel))
			else:
				frase += _(", en otra planta")
		return frase


def _poligono_de(elemento: Any, catalogo: Catalogo | None) -> list[Punto]:
	if isinstance(elemento, Objeto) and catalogo is not None:
		return catalogo.huella(elemento)
	return puntos_de(elemento)


def medir(entorno: Entorno, elemento_a: Any, elemento_b: Any, catalogo: Catalogo | None = None) -> Medida:
	"""Distancia y rumbo de un elemento a otro (de centro a centro) y hueco libre entre ellos."""
	planta_a, a = resolver(entorno, elemento_a)
	planta_b, b = resolver(entorno, elemento_b)
	centro_a, centro_b = centro_de(a), centro_de(b)
	puntos_a, puntos_b = _poligono_de(a, catalogo), _poligono_de(b, catalogo)

	def como_poligono(puntos: list[Punto]) -> list[Punto]:
		# Un punto o un segmento también valen como «polígono» degenerado para medir huecos.
		return puntos if len(puntos) >= 2 else [puntos[0], puntos[0]]

	separacion = geo.distancia_entre_poligonos(como_poligono(puntos_a), como_poligono(puntos_b))
	misma = planta_a is planta_b or planta_a is None or planta_b is None
	desnivel = 0.0 if misma or planta_a is None or planta_b is None else planta_b.altura_m - planta_a.altura_m
	return Medida(
		distancia=geo.distancia(centro_a, centro_b),
		rumbo=geo.rumbo_entre(centro_a, centro_b) if geo.distancia(centro_a, centro_b) > 1e-9 else 0.0,
		separacion=separacion,
		misma_planta=misma,
		desnivel=desnivel,
	)


# ── Descripciones para lector de pantalla ────────────────────────────────────


def _medidas_espacio(espacio: Espacio) -> str:
	x0, y0, x1, y1 = espacio.caja()
	superficie = espacio.area()
	rectangular = len(espacio.contorno) == 4 and abs(superficie - (x1 - x0) * (y1 - y0)) < 0.01
	if rectangular:
		return _("de {ancho} por {fondo} metros ({area} metros cuadrados)").format(
			ancho=_m(x1 - x0), fondo=_m(y1 - y0), area=_m(round(superficie, 1))
		)
	return _("de {lados} lados, unos {ancho} por {fondo} metros ({area} metros cuadrados)").format(
		lados=len(espacio.contorno), ancho=_m(x1 - x0), fondo=_m(y1 - y0), area=_m(round(superficie, 1))
	)


def _describir_abertura(planta: Planta | None, abertura: Abertura, desde: Espacio | None = None) -> str:
	partes = [nombre_visible(TIPOS_ABERTURA, abertura.tipo).lower() + " " + _("de {ancho}").format(ancho=_metros(abertura.ancho))]
	if abertura.tipo in ("puerta", "portal"):
		partes.append(nombre_visible(ESTADOS_ABERTURA, abertura.estado).lower())
		if abertura.hoja not in ("batiente", "ninguna"):
			partes.append(nombre_visible(HOJAS, abertura.hoja).lower())
	if planta is not None:
		referencia = desde
		unidos = espacios_de_abertura(planta, abertura)
		if referencia is None:
			# Mejor el espacio con paredes que la tiene en un lado (el edificio antes que la acera).
			for espacio in planta.espacios:
				if (espacio.cerrado or espacio.macizo) and _situacion_en_lado(espacio, abertura) is not None:
					referencia = espacio
					break
		if referencia is None and unidos:
			referencia = unidos[0]
		if referencia is not None:
			situacion = _situacion_en_lado(referencia, abertura)
			if situacion is not None:
				lado, metros = situacion
				esquina = _lado_visible("oeste" if lado in ("norte", "sur") else "sur")
				partes.append(
					_("en la pared {lado} de {espacio}, a {metros} de la esquina {esquina}").format(
						lado=_lado_visible(lado), espacio=referencia.nombre, metros=_metros(metros), esquina=esquina
					)
				)
			otros = [e.nombre for e in unidos if e is not referencia]
			if otros:
				partes.append(_("da a {espacio}").format(espacio=otros[0]))
	if abertura.es_salida:
		partes.append(_("es una salida"))
	return f"{abertura.nombre}: " + ", ".join(partes) + "."


def _describir_conector(entorno: Entorno, conector: Conector) -> str:
	nombres = [p.nombre for p in (entorno.planta(i) for i in conector.plantas()) if p is not None]
	une = _("une {plantas}").format(plantas=_(" y ").join(nombres)) if nombres else _("no une ninguna planta")
	partes = [nombre_visible(TIPOS_CONECTOR, conector.tipo).lower(), une]
	for tramo in conector.tramos:
		if tramo.peldanos:
			partes.append(_n("{n} peldaño", "{n} peldaños", tramo.peldanos).format(n=tramo.peldanos))
		partes.append(_("{metros} de recorrido").format(metros=_metros(tramo.longitud_m)))
		partes.append(_("se sube hacia el {punto}").format(punto=geo.punto_cardinal(tramo.desde.rumbo)))
	if conector.datos.get("pasamanos"):
		partes.append(_("pasamanos: {valor}").format(valor=nombre_visible(PASAMANOS, conector.datos["pasamanos"]).lower()))
	if conector.datos.get("pendiente_pct") is not None:
		partes.append(_("pendiente del {valor} por ciento").format(valor=_m(float(conector.datos["pendiente_pct"]))))
	if conector.tipo == "ascensor":
		partes.append(_n("{n} parada", "{n} paradas", len(conector.paradas)).format(n=len(conector.paradas)))
	return f"{conector.nombre}: " + ", ".join(partes) + "."


def describir_elemento(entorno: Entorno, elemento: Any, catalogo: Catalogo | None = None) -> str:
	"""Una frase que describe un elemento, para leerla con el lector de pantalla.

	Dice qué es, cuánto mide y dónde está en relación con lo que tiene cerca
	(en qué espacio, en qué pared, a qué distancia de la esquina).
	"""
	planta, real = resolver(entorno, elemento)
	if isinstance(real, Planta):
		clase = _("exterior") if real.exterior else _("interior")
		return _("{nombre}: planta {clase}, nivel {nivel}, a {altura} de altura, con {espacios}.").format(
			nombre=real.nombre,
			clase=clase,
			nivel=real.nivel,
			altura=_metros(real.altura_m),
			espacios=_n("{n} espacio", "{n} espacios", len(real.espacios)).format(n=len(real.espacios)),
		)
	if isinstance(real, Conector):
		return _describir_conector(entorno, real)
	if isinstance(real, Espacio):
		partes = [nombre_visible(TIPOS_ESPACIO, real.tipo).lower() + " " + _medidas_espacio(real)]
		if real.macizo:
			partes.append(_("macizo, no se puede entrar"))
		else:
			partes.append(_("suelo de {suelo}").format(suelo=nombre_visible(SUELOS, real.suelo).lower()))
		if real.tipo == "paso_peatones":
			if real.datos.get("semaforo"):
				detalle = _("con semáforo")
				if real.datos.get("sonoro"):
					detalle += _(" sonoro")
				if real.datos.get("pulsador"):
					detalle += _(" y pulsador")
				partes.append(detalle)
			else:
				partes.append(_("sin semáforo"))
			if real.datos.get("isleta"):
				partes.append(_("con isleta"))
		if planta is not None and not real.macizo:
			puertas = [a for a in aberturas_de(planta, real) if a.tipo != "ventana"]
			if real.cerrado:
				partes.append(_n("{n} puerta o hueco", "{n} puertas o huecos", len(puertas)).format(n=len(puertas)))
		frase = f"{real.nombre}: " + ", ".join(partes) + "."
		if real.descripcion:
			frase += " " + real.descripcion
		return frase
	if isinstance(real, Abertura):
		frase = _describir_abertura(planta, real)
		return frase + (" " + real.descripcion if real.descripcion else "")
	if isinstance(real, Pared):
		frase = _("{nombre}: pared de {material} de {largo}, de {a} a {b}").format(
			nombre=real.nombre or _("Pared"),
			material=real.material,
			largo=_metros(geo.distancia(real.a, real.b)),
			a=_punto(real.a),
			b=_punto(real.b),
		)
		if not real.bloquea_paso:
			frase += _(", no corta el paso")
		if not real.bloquea_sonido:
			frase += _(", deja pasar el sonido")
		return frase + "."
	donde = ""
	if planta is not None and hasattr(real, "x"):
		espacio = planta.espacio_en(real.x, real.y)
		if espacio is not None:
			x0, y0, _x1, _y1 = espacio.caja()
			donde = _(" en {espacio}, a {este} de su lado oeste y {norte} de su lado sur").format(
				espacio=espacio.nombre, este=_metros(real.x - x0), norte=_metros(real.y - y0)
			)
	if isinstance(real, Objeto):
		definicion = catalogo.definicion_de(real) if catalogo else None
		clase = definicion.nombre if definicion else (_("caja") if catalogo is not None or real.tipo == "caja" else real.tipo)
		frase = _("{nombre}: {clase} de {ancho} de ancho por {fondo} de fondo y {alto} de alto{donde}, mirando al {punto}").format(
			nombre=real.nombre or clase,
			clase=clase.lower(),
			ancho=_m(real.ancho),
			fondo=_m(real.fondo),
			alto=_metros(real.alto),
			donde=donde,
			punto=geo.punto_cardinal(real.rumbo),
		)
		if real.estado:
			frase += _(", estado: {estado}").format(estado=real.estado)
		return frase + "." + (" " + real.descripcion if real.descripcion else "")
	if isinstance(real, FuenteSonido):
		return _("{nombre}: fuente de sonido «{sonido}»{donde}, se oye hasta {radio}.").format(
			nombre=real.nombre, sonido=real.sonido, donde=donde, radio=_metros(real.radio)
		) + (" " + real.descripcion if real.descripcion else "")
	if isinstance(real, Referencia):
		frase = _("{nombre}: {tipo}{donde}").format(
			nombre=real.nombre, tipo=nombre_visible(TIPOS_REFERENCIA, real.tipo).lower(), donde=donde
		)
		if not real.permanente:
			frase += _(", pasajera")
		return frase + "." + (" " + real.descripcion if real.descripcion else "")
	if isinstance(real, ZonaSuelo):
		x0, y0, x1, y1 = geo.caja(real.contorno)
		return _("{nombre}: zona de suelo de {suelo}, de unos {ancho} por {fondo} metros.").format(
			nombre=real.nombre, suelo=nombre_visible(SUELOS, real.suelo).lower(), ancho=_m(x1 - x0), fondo=_m(y1 - y0)
		)
	if isinstance(real, Via):
		return _(
			"{nombre}: vía de {largo} de largo y {ancho} de calzada, {carriles}, {sentido}, {trafico}, a {velocidad} kilómetros por hora."
		).format(
			nombre=real.nombre,
			largo=_metros(geo.longitud_linea(real.eje)),
			ancho=_metros(real.ancho),
			carriles=_n("{n} carril", "{n} carriles", real.carriles).format(n=real.carriles),
			sentido=nombre_visible(SENTIDOS_VIA, real.sentido).lower(),
			trafico=nombre_visible(NIVELES_TRAFICO, real.trafico).lower(),
			velocidad=_m(real.velocidad_kmh),
		)
	raise ErrorEdicion(_("No se sabe describir ese elemento."))


def _punto(p: Punto) -> str:
	return f"({_m(p[0])}; {_m(p[1])})"


def describir_entorno(entorno: Entorno, catalogo: Catalogo | None = None) -> str:
	"""Texto completo y estructurado del entorno: plantas, espacios, vecinos, puertas y objetos.

	Es la «vista general» para quien no ve el plano, y también lo que se
	exporta como descripción en texto. Cada línea es una frase completa.
	"""
	lineas: list[str] = [entorno.nombre or _("Entorno sin nombre")]
	if entorno.descripcion:
		lineas.append(entorno.descripcion)
	if entorno.autor:
		lineas.append(_("Autor: {autor}.").format(autor=entorno.autor))
	lineas.append(
		_n("Tiene {n} planta", "Tiene {n} plantas", len(entorno.plantas)).format(n=len(entorno.plantas))
		+ _n(" y {n} conector entre plantas.", " y {n} conectores entre plantas.", len(entorno.conectores)).format(
			n=len(entorno.conectores)
		)
	)
	planta_inicio = entorno.planta(entorno.inicio.planta)
	if planta_inicio is not None:
		espacio_inicio = planta_inicio.espacio_en(entorno.inicio.x, entorno.inicio.y)
		lineas.append(
			_("Inicio: en {donde}, planta {planta}, mirando al {punto}.").format(
				donde=espacio_inicio.nombre if espacio_inicio else _("un punto fuera de todo espacio"),
				planta=planta_inicio.nombre,
				punto=geo.punto_cardinal(entorno.inicio.rumbo),
			)
		)
	for planta in entorno.plantas:
		lineas.append("")
		lineas.append(describir_elemento(entorno, planta))
		# Una sola pasada por planta: qué aberturas tiene cada espacio y en qué espacio cae
		# cada objeto, sonido y referencia. Antes se preguntaba por cada pareja espacio-elemento.
		aberturas_de_cada = aberturas_por_espacio(planta)
		hijos_de: dict[int, list[Any]] = {id(espacio): [] for espacio in planta.espacios}
		sueltos: list[Any] = []
		for nombre_lista in ("objetos", "fuentes", "referencias"):
			for hijo in getattr(planta, nombre_lista):
				donde = planta.espacio_en(hijo.x, hijo.y)
				if donde is None:
					sueltos.append(hijo)
				elif id(donde) in hijos_de:
					hijos_de[id(donde)].append(hijo)
		# Los sueltos van en el orden de antes: objetos, luego sonidos, luego referencias.
		for espacio in planta.espacios:
			lineas.append("")
			lineas.append(describir_elemento(entorno, espacio, catalogo))
			if espacio.macizo:
				for abertura in aberturas_de_cada[id(espacio)]:
					lineas.append("  " + _describir_abertura(planta, abertura, espacio))
				continue
			cercanos = vecinos(planta, espacio)
			if cercanos:
				lineas.append(
					"  "
					+ _("Vecinos: {lista}.").format(
						lista=", ".join(_("{nombre} al {lado}").format(nombre=o.nombre, lado=_lado_visible(lado)) for o, lado in cercanos)
					)
				)
			if espacio.cerrado:
				for abertura in aberturas_de_cada[id(espacio)]:
					lineas.append("  " + _describir_abertura(planta, abertura, espacio))
			for hijo in hijos_de[id(espacio)]:
				lineas.append("  " + describir_elemento(entorno, hijo, catalogo))
		if sueltos or planta.paredes or planta.vias:
			lineas.append("")
		for pared in planta.paredes:
			lineas.append(describir_elemento(entorno, pared))
		for via in planta.vias:
			lineas.append(describir_elemento(entorno, via))
		for hijo in sueltos:
			lineas.append(describir_elemento(entorno, hijo, catalogo))
	if entorno.conectores:
		lineas.append("")
		lineas.append(_("Conectores entre plantas:"))
		for conector in entorno.conectores:
			lineas.append("  " + _describir_conector(entorno, conector))
	return "\n".join(lineas)


# ── Deshacer y rehacer ───────────────────────────────────────────────────────


@dataclass(slots=True)
class _Entrada:
	"""Una operación del historial: su nombre y lo que cambió (el parche)."""

	nombre: str
	parche: Parche


class Historial:
	"""Deshacer y rehacer POR DIFERENCIAS, con el nombre de cada operación.

	Antes de cada cambio el editor llama a ``anotar(entorno, "crear habitación
	Cocina")``: se saca una foto en huellas del entorno (ver
	``app.dominio.diferencias``). La operación queda ABIERTA hasta que se
	llama a ``cerrar(entorno)`` (lo hace ``ContextoEstudio.ejecutar`` al
	terminar) o hasta la siguiente llamada a ``anotar``, ``deshacer`` o
	``rehacer``, que la cierran solas: entonces se compara con el entorno y se
	guarda solo lo que cambió. Una operación que falla se descarta con
	``cancelar(entorno)``, que además deja el entorno como estaba.

	``deshacer`` y ``rehacer`` modifican el entorno EN EL SITIO y devuelven el
	MISMO objeto (antes devolvían un ``Entorno`` nuevo que el editor ponía en
	lugar del suyo): así los objetos que no cambian conservan su identidad,
	el índice espacial de las plantas no tocadas sigue valiendo y el Estudio
	solo tiene que poner al día lo que dice el parche (``ultimo_parche``).
	Si el entorno no está como el parche espera (alguien lo cambió sin pasar
	por el historial) lanzan ``ErrorParche`` sin tocar nada.

	Por qué: con un barrio de 3.000 espacios cada instantánea completa ocupaba
	unos 9 MB y tardaba 30 ms en guardarse y 25 ms en recuperarse; cien
	niveles eran casi un gigabyte. Un parche de mover una habitación ocupa
	unos pocos kilobytes.
	"""

	def __init__(self, limite: int = 50) -> None:
		self.limite = max(1, int(limite))
		self._deshacer: list[_Entrada] = []
		self._rehacer: list[_Entrada] = []
		# La operación en curso: su nombre y la foto del entorno antes de empezarla.
		self._abierta: tuple[str, Foto] | None = None
		# La foto del entorno tal como lo dejó la última operación cerrada: es la de ANTES de la
		# siguiente si nadie lo toca entre medias (todo cambio pasa por el historial). Ahorra sacarla.
		self._foto_vigente: Foto | None = None
		#: El parche de lo último que se hizo, deshizo o rehízo: dice qué elementos hay que volver a enseñar.
		self.ultimo_parche: Parche | None = None

	def anotar(self, entorno: Entorno, nombre: str) -> None:
		"""Abre una operación que se podrá deshacer: hay que llamarlo ANTES de cambiar el entorno.

		Si había otra abierta, se cierra antes con el entorno tal como está.
		Si la anterior se cerró sobre este mismo entorno, su foto de después
		sirve de foto de antes (la regla de siempre: el entorno solo se cambia
		dentro de una operación anotada). Aunque alguien lo cambiara por fuera,
		el resultado sería coherente: ese cambio quedaría dentro de esta operación.
		"""
		self.cerrar(entorno)
		vigente = self._foto_vigente
		self._foto_vigente = None
		self._abierta = (nombre, vigente if vigente is not None and vigente.entorno is entorno else tomar_foto(entorno))

	def cerrar(self, entorno: Entorno | None = None) -> Parche | None:
		"""Cierra la operación abierta: guarda lo que ha cambiado desde ``anotar`` y lo devuelve. None si no había ninguna.

		Una operación nueva borra lo que se podía rehacer, como en cualquier editor.
		"""
		if self._abierta is None:
			return None
		nombre, foto = self._abierta
		self._abierta = None
		parche, self._foto_vigente = comparar_y_fotografiar(foto, entorno if entorno is not None else foto.entorno)
		self._deshacer.append(_Entrada(nombre, parche))
		if len(self._deshacer) > self.limite:
			del self._deshacer[: len(self._deshacer) - self.limite]
		self._rehacer.clear()
		self.ultimo_parche = parche
		return parche

	def cancelar(self, entorno: Entorno | None = None) -> Parche | None:
		"""Descarta la operación abierta (falló) y deja el entorno como estaba al anotarla.

		No entra en el historial ni borra lo que se podía rehacer. Devuelve lo
		que se ha devuelto a su estado (vacío si la operación no llegó a tocar
		nada), o None si no había ninguna abierta.
		"""
		if self._abierta is None:
			return None
		_nombre, foto = self._abierta
		self._abierta = None
		self._foto_vigente = None
		destino = entorno if entorno is not None else foto.entorno
		parche = comparar(foto, destino)
		if not parche.vacio:
			aplicar(destino, parche, hacia_atras=True)
		self.ultimo_parche = parche
		return parche

	def _nombres(self) -> list[str]:
		nombres = [entrada.nombre for entrada in self._deshacer]
		if self._abierta is not None:
			nombres.append(self._abierta[0])
		return nombres[-self.limite :]

	@property
	def puede_deshacer(self) -> bool:
		"""True si hay algo que deshacer (también la operación abierta)."""
		return bool(self._deshacer) or self._abierta is not None

	@property
	def puede_rehacer(self) -> bool:
		"""True si hay algo que rehacer (con una operación abierta, no: al cerrarla se pierde)."""
		return bool(self._rehacer) and self._abierta is None

	def texto_deshacer(self) -> str:
		"""«Deshacer: crear habitación Cocina», o «Deshacer» si no hay nada."""
		nombres = self._nombres()
		return _("Deshacer: {operacion}").format(operacion=nombres[-1]) if nombres else _("Deshacer")

	def texto_rehacer(self) -> str:
		"""«Rehacer: crear habitación Cocina», o «Rehacer» si no hay nada."""
		return _("Rehacer: {operacion}").format(operacion=self._rehacer[-1].nombre) if self.puede_rehacer else _("Rehacer")

	def operaciones(self) -> list[str]:
		"""Nombres de las operaciones que se pueden deshacer, de la más antigua a la más reciente."""
		return self._nombres()

	def deshacer(self, entorno: Entorno) -> Entorno | None:
		"""Deja el entorno como estaba antes de la última operación, EN EL SITIO, y lo devuelve; None si no hay nada.

		Devuelve el mismo ``entorno`` que recibe (no uno nuevo). Lo cambiado
		está en ``ultimo_parche``. Lanza ``ErrorParche`` (sin tocar nada) si el
		entorno no está como lo dejó esa operación.
		"""
		self.cerrar(entorno)
		if not self._deshacer:
			return None
		entrada = self._deshacer[-1]
		# La foto de después de la última operación ya no es el estado del entorno.
		self._foto_vigente = None
		aplicar(entorno, entrada.parche, hacia_atras=True)
		self._rehacer.append(self._deshacer.pop())
		self.ultimo_parche = entrada.parche
		return entorno

	def rehacer(self, entorno: Entorno) -> Entorno | None:
		"""Vuelve a aplicar la última operación deshecha, EN EL SITIO, y devuelve el mismo entorno; None si no hay nada."""
		if not self.puede_rehacer:
			return None
		entrada = self._rehacer[-1]
		self._foto_vigente = None
		aplicar(entorno, entrada.parche, hacia_atras=False)
		self._deshacer.append(self._rehacer.pop())
		self.ultimo_parche = entrada.parche
		return entorno

	def memoria(self) -> int:
		"""Bytes que ocupan, aproximadamente, todos los parches guardados (para medir que no crece sin medida)."""
		return sum(entrada.parche.tamano() for entrada in (*self._deshacer, *self._rehacer))

	def limpiar(self) -> None:
		"""Olvida todo (al abrir otro entorno)."""
		self._deshacer.clear()
		self._rehacer.clear()
		self._abierta = None
		self._foto_vigente = None
		self.ultimo_parche = None
