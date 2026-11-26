"""Lugares de un entorno dichos en palabras: para elegir y describir puntos sin plano. Sin wx.

Quien no ve el plano no puede «pinchar» dónde esconder un premio. Aquí se
convierte la elección en algo que se hace con listas (planta, espacio,
«dentro del armario», «junto a la mesa», «en la esquina noreste») y, al
revés, cualquier punto guardado se dice en palabras («Dormitorio, dentro de
Armario»).
"""

from __future__ import annotations

import logging
import math
from typing import Any

from app.core.i18n import N_, _
from app.dominio.modelo import Abertura, Entorno, Espacio, Objeto, Planta, Referencia
from app.ui.seguimiento.textos import decimal

log = logging.getLogger(__name__)

CENTRO = "centro"
JUNTO = "junto"
ESQUINA = "esquina"
COORDENADAS = "coordenadas"
DENTRO = "dentro"

MODOS_PUNTO: dict[str, str] = {
	DENTRO: N_("Dentro de un objeto (armario, cajón...)"),
	JUNTO: N_("Junto a un objeto, una puerta o una referencia"),
	CENTRO: N_("En el centro del espacio"),
	ESQUINA: N_("En una esquina del espacio"),
	COORDENADAS: N_("En unas coordenadas concretas"),
}
ESQUINAS: dict[str, str] = {
	"noreste": N_("Noreste"),
	"noroeste": N_("Noroeste"),
	"sureste": N_("Sureste"),
	"suroeste": N_("Suroeste"),
}

# Separación de las paredes y de los objetos al colocar un punto «junto a» algo o en una esquina.
_MARGEN = 0.5


def nombre_de(elemento: Any) -> str:
	"""Nombre para mostrar de un elemento; si no tiene, su identificador."""
	return str(getattr(elemento, "nombre", "") or getattr(elemento, "id", "") or _("sin nombre"))


def nombre_planta(entorno: Entorno | None, planta_id: str) -> str:
	"""Nombre de la planta con ese id (el id si no existe)."""
	planta = entorno.planta(planta_id) if entorno is not None else None
	return nombre_de(planta) if planta is not None else str(planta_id or _("planta sin indicar"))


def plantas(entorno: Entorno | None) -> list[Planta]:
	"""Plantas del entorno, de la más baja a la más alta."""
	if entorno is None:
		return []
	return sorted(entorno.plantas, key=lambda planta: planta.nivel)


def espacios(planta: Planta | None) -> list[Espacio]:
	"""Espacios de la planta en los que se puede estar (los macizos no), por nombre."""
	if planta is None:
		return []
	return sorted((e for e in planta.espacios if not e.macizo and len(e.contorno) >= 3), key=lambda e: nombre_de(e).casefold())


def es_contenedor(objeto: Objeto, catalogo: Any = None) -> bool:
	"""True si dentro del objeto se puede esconder un premio (lo dice el catálogo o el propio objeto)."""
	propio = objeto.datos.get("contenedor") if isinstance(objeto.datos, dict) else None
	if isinstance(propio, bool):
		return propio
	if catalogo is None:
		return False
	try:
		definicion = catalogo.definicion_de(objeto)
	except AttributeError, TypeError, ValueError:
		log.debug("El catálogo no ha podido dar la definición de un objeto", exc_info=True)
		return False
	return bool(getattr(definicion, "contenedor", False))


def objetos_de(planta: Planta | None, espacio: Espacio | None) -> list[Objeto]:
	"""Objetos cuyo centro está dentro del espacio, por nombre."""
	if planta is None or espacio is None:
		return []
	dentro = [objeto for objeto in planta.objetos if espacio.contiene(objeto.x, objeto.y)]
	return sorted(dentro, key=lambda objeto: nombre_de(objeto).casefold())


def contenedores(planta: Planta | None, espacio: Espacio | None, catalogo: Any = None) -> list[Objeto]:
	"""Objetos del espacio dentro de los que se puede esconder algo."""
	return [objeto for objeto in objetos_de(planta, espacio) if es_contenedor(objeto, catalogo)]


def _cerca_de(espacio: Espacio, punto: tuple[float, float], distancia: float = 0.6) -> bool:
	"""True si el punto está dentro del espacio o pegado a su borde (una puerta está en la pared)."""
	if espacio.contiene(punto[0], punto[1]):
		return True
	centro = espacio.centro()
	largo = math.hypot(centro[0] - punto[0], centro[1] - punto[1])
	if largo <= 0.0:
		return True
	hacia = (punto[0] + (centro[0] - punto[0]) * distancia / largo, punto[1] + (centro[1] - punto[1]) * distancia / largo)
	return espacio.contiene(hacia[0], hacia[1])


def aberturas_de(planta: Planta | None, espacio: Espacio | None, solo_salidas: bool = False) -> list[Abertura]:
	"""Puertas, huecos y ventanas que dan al espacio."""
	if planta is None:
		return []
	lista = [a for a in planta.aberturas if (espacio is None or _cerca_de(espacio, a.centro())) and (a.es_salida or not solo_salidas)]
	return sorted(lista, key=lambda abertura: nombre_de(abertura).casefold())


def referencias_de(planta: Planta | None, espacio: Espacio | None) -> list[Referencia]:
	"""Referencias situadas en el espacio."""
	if planta is None:
		return []
	lista = [r for r in planta.referencias if espacio is None or espacio.contiene(r.x, r.y)]
	return sorted(lista, key=lambda referencia: nombre_de(referencia).casefold())


def elementos_de_clase(planta: Planta | None, espacio: Espacio | None, clase: str, catalogo: Any = None) -> list[Any]:
	"""Elementos de una clase (``espacio``, ``abertura``, ``objeto``, ``referencia``, ``salida``, ``contenedor``).

	Con ``espacio`` se limitan a los de ese espacio; para la clase «espacio» se devuelven los de la planta.
	"""
	if planta is None:
		return []
	if clase == "espacio":
		return list(espacios(planta))
	if clase == "abertura":
		return list(aberturas_de(planta, espacio))
	if clase == "salida":
		return list(aberturas_de(planta, espacio, solo_salidas=True))
	if clase == "referencia":
		return list(referencias_de(planta, espacio))
	if clase == "contenedor":
		return (
			list(contenedores(planta, espacio, catalogo))
			if espacio is not None
			else [o for o in planta.objetos if es_contenedor(o, catalogo)]
		)
	if clase == "objeto":
		return list(objetos_de(planta, espacio)) if espacio is not None else sorted(planta.objetos, key=lambda o: nombre_de(o).casefold())
	if clase == "fuente":
		fuentes = [f for f in planta.fuentes if espacio is None or espacio.contiene(f.x, f.y)]
		return sorted(fuentes, key=lambda fuente: nombre_de(fuente).casefold())
	return []


def conectores(entorno: Entorno | None) -> list[Any]:
	"""Escaleras, rampas y ascensores del entorno (no pertenecen a una sola planta)."""
	if entorno is None:
		return []
	return sorted(entorno.conectores, key=lambda conector: nombre_de(conector).casefold())


def vecinos(planta: Planta | None, espacio: Espacio | None) -> list[Any]:
	"""Todo aquello «junto a» lo que se puede poner un punto en el espacio: objetos, puertas y referencias."""
	return [*objetos_de(planta, espacio), *aberturas_de(planta, espacio), *referencias_de(planta, espacio)]


def posicion_de(elemento: Any) -> tuple[float, float] | None:
	"""Punto que representa a un elemento (su centro)."""
	if isinstance(elemento, Espacio):
		return centro_seguro(elemento)
	if isinstance(elemento, Abertura):
		return elemento.centro()
	if hasattr(elemento, "x") and hasattr(elemento, "y"):
		return float(elemento.x), float(elemento.y)
	return None


def centro_seguro(espacio: Espacio) -> tuple[float, float]:
	"""Un punto de dentro del espacio lo más parecido a su centro.

	En un espacio en forma de L el centro de gravedad puede caer fuera: se
	busca entonces el punto interior más cercano en una rejilla.
	"""
	centro = espacio.centro()
	if espacio.contiene(centro[0], centro[1]):
		return centro
	x1, y1, x2, y2 = espacio.caja()
	mejor: tuple[float, float] | None = None
	mejor_distancia = math.inf
	pasos = 12
	for i in range(1, pasos):
		for j in range(1, pasos):
			x = x1 + (x2 - x1) * i / pasos
			y = y1 + (y2 - y1) * j / pasos
			if espacio.contiene(x, y):
				distancia = math.hypot(x - centro[0], y - centro[1])
				if distancia < mejor_distancia:
					mejor, mejor_distancia = (x, y), distancia
	return mejor if mejor is not None else centro


def _hacia(origen: tuple[float, float], destino: tuple[float, float], distancia: float) -> tuple[float, float]:
	largo = math.hypot(destino[0] - origen[0], destino[1] - origen[1])
	if largo <= 1e-6:
		return origen
	avance = min(distancia, largo)
	return origen[0] + (destino[0] - origen[0]) * avance / largo, origen[1] + (destino[1] - origen[1]) * avance / largo


def punto_junto_a(espacio: Espacio, elemento: Any) -> tuple[float, float]:
	"""Punto transitable al lado de un elemento, por el lado que mira al centro del espacio."""
	base = posicion_de(elemento)
	centro = centro_seguro(espacio)
	if base is None:
		return centro
	separacion = _MARGEN
	if isinstance(elemento, Objeto):
		separacion += max(elemento.ancho, elemento.fondo) / 2.0
	punto = _hacia(base, centro, separacion)
	return punto if espacio.contiene(punto[0], punto[1]) else centro


def punto_esquina(espacio: Espacio, esquina: str) -> tuple[float, float]:
	"""Punto cerca de la esquina pedida (``noreste``, ``noroeste``, ``sureste``, ``suroeste``), separado de las paredes."""
	x1, y1, x2, y2 = espacio.caja()
	objetivo = (x2 if "este" in esquina and "oeste" not in esquina else x1, y2 if esquina.startswith("nor") else y1)
	# El vértice del contorno más cercano a la esquina de la caja: en una sala que no es rectangular es la esquina real.
	vertice = min(espacio.contorno, key=lambda punto: math.hypot(punto[0] - objetivo[0], punto[1] - objetivo[1]))
	centro = centro_seguro(espacio)
	for separacion in (_MARGEN * 1.5, _MARGEN, _MARGEN / 2.0):
		punto = _hacia(vertice, centro, separacion)
		if espacio.contiene(punto[0], punto[1]):
			return punto
	return centro


def calcular_punto(espacio: Espacio, modo: str, elemento: Any = None, esquina: str = "noreste") -> tuple[float, float]:
	"""Coordenadas de un punto elegido en palabras dentro de ``espacio``."""
	if modo == DENTRO and elemento is not None:
		posicion = posicion_de(elemento)
		return posicion if posicion is not None else centro_seguro(espacio)
	if modo == JUNTO and elemento is not None:
		return punto_junto_a(espacio, elemento)
	if modo == ESQUINA:
		return punto_esquina(espacio, esquina)
	return centro_seguro(espacio)


def espacio_en(entorno: Entorno | None, planta_id: str, x: Any, y: Any) -> tuple[Planta | None, Espacio | None]:
	"""Planta y espacio en los que cae un punto (el espacio puede ser ``None`` si cae fuera de todos)."""
	if entorno is None:
		return None, None
	planta = entorno.planta(planta_id) or (entorno.plantas[0] if entorno.plantas and not planta_id else None)
	if planta is None or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
		return planta, None
	return planta, planta.espacio_en(float(x), float(y), incluir_macizos=False)


def _mas_cercano(planta: Planta, espacio: Espacio | None, x: float, y: float, maximo: float = 1.6) -> Any | None:
	candidatos = vecinos(planta, espacio) if espacio is not None else [*planta.objetos, *planta.referencias]
	mejor: Any | None = None
	mejor_distancia = maximo
	for candidato in candidatos:
		posicion = posicion_de(candidato)
		if posicion is None:
			continue
		distancia = math.hypot(posicion[0] - x, posicion[1] - y)
		if isinstance(candidato, Objeto):
			distancia -= max(candidato.ancho, candidato.fondo) / 2.0
		if distancia < mejor_distancia:
			mejor, mejor_distancia = candidato, distancia
	return mejor


def describir_punto(entorno: Entorno | None, planta_id: str, x: Any, y: Any, dentro_de: str | None = None) -> str:
	"""Un punto dicho en palabras: «Dormitorio, dentro de Armario», «Cocina, junto a Mesa», «Salón, en el centro».

	Añade la planta si el entorno tiene más de una. Si el punto no cae en
	ningún espacio lo dice, porque casi siempre es un error que hay que ver.
	"""
	if entorno is None:
		return _("sin entorno abierto")
	if not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
		if dentro_de:
			contenedor = entorno.elemento(dentro_de)
			return _("dentro de {objeto}").format(objeto=nombre_de(contenedor) if contenedor is not None else dentro_de)
		return _("lugar sin indicar")
	planta, espacio = espacio_en(entorno, planta_id, x, y)
	if planta is None:
		return _("planta desconocida ({planta})").format(planta=planta_id)
	partes: list[str] = [nombre_de(espacio) if espacio is not None else _("fuera de todos los espacios")]
	if dentro_de:
		contenedor = entorno.elemento(dentro_de)
		if contenedor is not None:
			partes.append(_("dentro de {objeto}").format(objeto=nombre_de(contenedor)))
		else:
			partes.append(_("dentro de un objeto que ya no existe"))
	elif espacio is not None:
		cercano = _mas_cercano(planta, espacio, float(x), float(y))
		centro = centro_seguro(espacio)
		if cercano is not None:
			partes.append(_("junto a {elemento}").format(elemento=nombre_de(cercano)))
		elif math.hypot(centro[0] - float(x), centro[1] - float(y)) <= 0.6:
			partes.append(_("en el centro"))
		else:
			partes.append(_lado(espacio, float(x), float(y)))
	if len(entorno.plantas) > 1:
		partes.append(_("planta {planta}").format(planta=nombre_de(planta)))
	return ", ".join(parte for parte in partes if parte)


def _lado(espacio: Espacio, x: float, y: float) -> str:
	"""«en la parte noreste»: en qué zona del espacio queda un punto que no está junto a nada."""
	x1, y1, x2, y2 = espacio.caja()
	ancho = max(x2 - x1, 1e-6)
	alto = max(y2 - y1, 1e-6)
	u = (x - x1) / ancho
	v = (y - y1) / alto
	vertical = "norte" if v > 0.62 else ("sur" if v < 0.38 else "")
	horizontal = "este" if u > 0.62 else ("oeste" if u < 0.38 else "")
	zonas = {
		("norte", ""): N_("en la parte norte"),
		("sur", ""): N_("en la parte sur"),
		("", "este"): N_("en la parte este"),
		("", "oeste"): N_("en la parte oeste"),
		("norte", "este"): N_("en la parte noreste"),
		("norte", "oeste"): N_("en la parte noroeste"),
		("sur", "este"): N_("en la parte sureste"),
		("sur", "oeste"): N_("en la parte suroeste"),
	}
	return _(zonas.get((vertical, horizontal), N_("hacia el centro")))


def describir_posicion(entorno: Entorno | None, posicion: Any) -> str:
	"""Describe un diccionario de posición (``planta``, ``x``, ``y`` y quizá ``rumbo``), o dice que no hay."""
	if not isinstance(posicion, dict) or "x" not in posicion or "y" not in posicion:
		return _("Sin indicar: se usa el inicio del entorno.")
	from app.ui.seguimiento.textos import cardinal

	texto = describir_punto(entorno, str(posicion.get("planta", "")), posicion.get("x"), posicion.get("y"))
	rumbo = cardinal(posicion.get("rumbo"))
	if rumbo:
		texto = _("{lugar}, mirando al {rumbo}").format(lugar=texto, rumbo=rumbo)
	return texto + " " + _("(x {x}, y {y})").format(x=decimal(float(posicion["x"])), y=decimal(float(posicion["y"])))


def describir_elemento(entorno: Entorno | None, id_elemento: str, catalogo: Any = None) -> str:
	"""Frase que describe el elemento con ese id (la del editor de entornos si está disponible)."""
	if not id_elemento:
		return _("Sin elegir.")
	if entorno is None:
		return str(id_elemento)
	encontrado = entorno.buscar(id_elemento)
	if encontrado is None:
		return _("El elemento «{id}» ya no existe en el entorno.").format(id=id_elemento)
	planta, elemento = encontrado
	try:
		from app.dominio.edicion import describir_elemento as describir

		return describir(entorno, elemento, catalogo)
	except Exception:  # noqa: BLE001 - la descripción es un complemento: si falla se da el nombre y el lugar
		log.warning("No se ha podido describir un elemento con el editor de entornos", exc_info=True)
	posicion = posicion_de(elemento)
	if planta is not None and posicion is not None and not isinstance(elemento, Espacio):
		return _("{nombre}: {lugar}").format(
			nombre=nombre_de(elemento), lugar=describir_punto(entorno, planta.id, posicion[0], posicion[1])
		)
	return nombre_de(elemento)


def espacios_para_informes(entorno: Entorno | None) -> list[dict[str, Any]]:
	"""Espacios del entorno en la forma que piden las medidas y la narración del recorrido."""
	lista: list[dict[str, Any]] = []
	if entorno is None:
		return lista
	for planta in entorno.plantas:
		for espacio in planta.espacios:
			lista.append(
				{
					"id": espacio.id,
					"nombre": espacio.nombre,
					"planta": planta.id,
					"contorno": [[float(x), float(y)] for x, y in espacio.contorno],
					"macizo": bool(espacio.macizo),
				}
			)
	return lista
