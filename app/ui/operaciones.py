"""Lo que las órdenes del Estudio hacen sobre el entorno, sin wx.

La ventana principal solo enseña y pregunta; lo que se calcula está aquí
para poder probarlo sin abrir ventanas:

- el ÁRBOL del entorno (plantas → espacios → lo que hay en cada espacio);
- las FILAS de la lista de elementos (nombre, tipo, medidas, posición);
- leer y APLICAR las propiedades de un elemento, usando las funciones de
  ``app.dominio.edicion`` siempre que existen (renombrar, mover, girar,
  redimensionar) para que cada cambio arrastre lo que depende de él;
- las PLANTILLAS del asistente «Nuevo entorno»;
- buscar elementos y calcular el punto de partida de un recorrido.

Ninguna función guarda referencias entre llamadas: todas reciben el entorno
vigente, porque al deshacer el entorno se sustituye por otro.
"""

from __future__ import annotations

import logging
import math
import operator
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any, overload

from app.core.i18n import N_, _, _n
from app.dominio import edicion, ejemplos
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo, sin_acentos
from app.dominio.diferencias import Afectados
from app.dominio.edicion import ErrorEdicion
from app.dominio.geometria import Punto
from app.dominio.modelo import (
	TIPOS_ABERTURA,
	TIPOS_CONECTOR,
	TIPOS_ESPACIO,
	TIPOS_REFERENCIA,
	TOLERANCIA_PARED,
	Abertura,
	Conector,
	Entorno,
	Espacio,
	FuenteSonido,
	Objeto,
	Pared,
	Planta,
	Posicion,
	Referencia,
	Via,
	ZonaSuelo,
	nombre_visible,
)
from app.ui.esquemas import leer_numero, texto_numero

log = logging.getLogger(__name__)

# Claves de los nodos del árbol que no son un elemento.
CLAVE_ENTORNO = "@entorno"
CLAVE_CONECTORES = "@conectores"
PREFIJO_GRUPO = "@grupo:"

# ── Nombres ──────────────────────────────────────────────────────────────────


def nombre_de(elemento: Any) -> str:
	"""Nombre con el que se enseña un elemento; si no tiene, su id."""
	return getattr(elemento, "nombre", "") or getattr(elemento, "id", "") or _("(sin nombre)")


def nombre_tipo(elemento: Any, catalogo: Catalogo | None = None) -> str:
	"""Qué es un elemento, en palabras: «Habitación», «Puerta», «Mesa de comedor», «Fuente de sonido»."""
	if isinstance(elemento, Entorno):
		return _("Entorno")
	if isinstance(elemento, Planta):
		return _("Plano de calle") if elemento.exterior else _("Planta")
	if isinstance(elemento, Espacio):
		return nombre_visible(TIPOS_ESPACIO, elemento.tipo)
	if isinstance(elemento, Abertura):
		return nombre_visible(TIPOS_ABERTURA, elemento.tipo)
	if isinstance(elemento, Pared):
		return _("Pared suelta")
	if isinstance(elemento, Objeto):
		definicion = catalogo.definicion_de(elemento) if catalogo is not None else None
		return definicion.nombre if definicion is not None else _("Objeto")
	if isinstance(elemento, FuenteSonido):
		return _("Fuente de sonido")
	if isinstance(elemento, Referencia):
		return nombre_visible(TIPOS_REFERENCIA, elemento.tipo)
	if isinstance(elemento, ZonaSuelo):
		return _("Zona de suelo")
	if isinstance(elemento, Via):
		return _("Calle")
	if isinstance(elemento, Conector):
		return nombre_visible(TIPOS_CONECTOR, elemento.tipo)
	return ""


def texto_medidas(elemento: Any) -> str:
	"""Medidas de un elemento para la columna de la lista: «4 × 3 m», «0,82 m de ancho»."""
	if isinstance(elemento, (Espacio, ZonaSuelo)) and len(elemento.contorno) >= 3:
		x0, y0, x1, y1 = geo.caja(elemento.contorno)
		return _("{ancho} × {fondo} m").format(ancho=texto_numero(x1 - x0), fondo=texto_numero(y1 - y0))
	if isinstance(elemento, Objeto):
		return _("{ancho} × {fondo} × {alto} m").format(
			ancho=texto_numero(elemento.ancho), fondo=texto_numero(elemento.fondo), alto=texto_numero(elemento.alto)
		)
	if isinstance(elemento, Abertura):
		return _("{ancho} m de ancho").format(ancho=texto_numero(elemento.ancho))
	if isinstance(elemento, Pared):
		return _("{largo} m de largo").format(largo=texto_numero(geo.distancia(elemento.a, elemento.b)))
	if isinstance(elemento, Via):
		largo = sum(geo.distancia(a, b) for a, b in zip(elemento.eje, elemento.eje[1:], strict=False))
		return _("{largo} m de largo, {ancho} m de calzada").format(largo=texto_numero(largo), ancho=texto_numero(elemento.ancho))
	if isinstance(elemento, FuenteSonido):
		return _("se oye a {radio} m").format(radio=texto_numero(elemento.radio))
	if isinstance(elemento, Conector) and elemento.tramos:
		tramo = elemento.tramos[0]
		if tramo.peldanos:
			return _("{largo} m, {n} peldaños").format(largo=texto_numero(tramo.longitud_m), n=tramo.peldanos)
		return _("{largo} m").format(largo=texto_numero(tramo.longitud_m))
	if isinstance(elemento, Planta):
		return _("nivel {nivel}, a {altura} m").format(nivel=elemento.nivel, altura=texto_numero(elemento.altura_m))
	return ""


def texto_posicion(elemento: Any) -> str:
	"""Dónde está un elemento, para la columna de la lista: «x 2,5, y 1» (metros al este y al norte)."""
	if isinstance(elemento, (Planta, Entorno)):
		return ""
	if isinstance(elemento, Conector):
		posiciones = elemento.posiciones()
		if not posiciones:
			return ""
		x, y = posiciones[0].x, posiciones[0].y
	else:
		try:
			x, y = edicion.centro_de(elemento)
		except ValueError, TypeError, ZeroDivisionError:
			log.debug("Elemento sin posición calculable: %r", elemento)
			return ""
	return _("x {x}, y {y}").format(x=texto_numero(x), y=texto_numero(y))


# ── Árbol ────────────────────────────────────────────────────────────────────


@dataclass
class Nodo:
	"""Un nodo del árbol del entorno.

	``clave`` es única en el árbol; ``id`` es el del elemento (vacío en los
	grupos). Una puerta sale debajo de cada uno de los dos espacios que une,
	así que dos nodos pueden compartir ``id`` con distinta ``clave``.
	"""

	clave: str
	texto: str
	id: str = ""
	hijos: list[Nodo] = field(default_factory=list)
	# Índices de búsqueda (clave → nodo y padre; id → primer nodo), hechos la primera vez que se buscan.
	# El árbol no se modifica después de construirlo: buscar en un barrio de miles de nodos es un acceso a diccionario.
	_por_clave: dict[str, tuple[Nodo, Nodo | None]] | None = field(default=None, repr=False, compare=False)
	_por_id: dict[str, Nodo] | None = field(default=None, repr=False, compare=False)

	def recorrer(self) -> Iterable[Nodo]:
		"""Este nodo y todos sus descendientes, en el orden en que se leen (sin recursión: el árbol puede ser enorme)."""
		pendientes: list[Nodo] = [self]
		while pendientes:
			nodo = pendientes.pop()
			yield nodo
			pendientes.extend(reversed(nodo.hijos))

	def _indizar(self) -> None:
		"""Los dos índices en UNA pasada en orden de lectura (el árbol cambia tras cada edición y se vuelve a indizar)."""
		por_clave: dict[str, tuple[Nodo, Nodo | None]] = {self.clave: (self, None)}
		por_id: dict[str, Nodo] = {}
		pendientes: list[Nodo] = [self]
		while pendientes:
			nodo = pendientes.pop()
			if nodo.id:
				por_id.setdefault(nodo.id, nodo)
			hijos = nodo.hijos
			if hijos:
				for hijo in hijos:
					por_clave.setdefault(hijo.clave, (hijo, nodo))
				pendientes.extend(reversed(hijos))
		self._por_clave = por_clave
		self._por_id = por_id

	def buscar(self, clave: str) -> Nodo | None:
		"""Nodo con esa clave, o None."""
		if self._por_clave is None:
			self._indizar()
		encontrado = self._por_clave.get(clave) if self._por_clave is not None else None
		return encontrado[0] if encontrado is not None else None

	def padre_de(self, clave: str) -> Nodo | None:
		"""Nodo padre del de esa clave (None si es la raíz o no existe)."""
		if self._por_clave is None:
			self._indizar()
		encontrado = self._por_clave.get(clave) if self._por_clave is not None else None
		return encontrado[1] if encontrado is not None else None

	def buscar_id(self, id_elemento: str) -> Nodo | None:
		"""Primer nodo de ese elemento, o None."""
		if not id_elemento:
			return None
		if self._por_id is None:
			self._indizar()
		return self._por_id.get(id_elemento) if self._por_id is not None else None


def _texto_nodo(elemento: Any, catalogo: Catalogo | None) -> str:
	"""«Cocina (habitación)»: nombre y tipo, que es lo que el lector dice al pasar por el árbol."""
	tipo = nombre_tipo(elemento, catalogo)
	nombre = nombre_de(elemento)
	if not tipo or sin_acentos(tipo) in sin_acentos(nombre):
		return nombre
	return _("{nombre} ({tipo})").format(nombre=nombre, tipo=tipo.lower())


def contenido_de_espacio(planta: Planta, espacio: Espacio) -> list[Any]:
	"""Lo que hay en un espacio: sus puertas y los objetos, sonidos, referencias y zonas que caen dentro.

	Un elemento pertenece al espacio MÁS PEQUEÑO que lo contiene (el paso de
	peatones antes que la calzada), que es el que se nombra al alumno.
	"""
	dentro: list[Any] = list(edicion.aberturas_de(planta, espacio))
	for elemento in [*planta.objetos, *planta.fuentes, *planta.referencias, *planta.zonas]:
		if _espacio_de(planta, elemento) is espacio:
			dentro.append(elemento)
	return dentro


def contenido_de_planta(planta: Planta) -> dict[int, list[Any]]:
	"""``contenido_de_espacio`` de TODOS los espacios de la planta de una vez: ``id(espacio)`` → su contenido.

	Por qué: el árbol necesita el contenido de cada espacio, y pedirlo espacio
	por espacio preguntaba por cada elemento tantas veces como espacios hay
	(con 350 espacios importados, diez segundos por clic). Aquí cada elemento
	se sitúa UNA vez con el índice espacial de la planta. Mismo resultado y
	mismo orden que ``contenido_de_espacio``.
	"""
	indice = planta.indice_espacios()
	# Lo calculado la última vez para esta planta: al mover un mueble solo se vuelve a situar ese mueble,
	# no los miles de elementos. Si desde entonces han cambiado espacios (otro índice), se olvida solo lo
	# que cae cerca de los espacios cambiados: lo demás no puede haber cambiado de espacio.
	cache = planta.__dict__.get("_cache_contenido")
	if cache is None:
		cache = (indice, {}, {})
	elif cache[0] is not indice:
		cajas = indice.cambios_desde(cache[0])
		if cajas is None or len(cajas) > MAX_CAJAS_CAMBIADAS:
			cache = (indice, {}, {})
		else:
			cache = (indice, *_olvidar_cerca(cache[1], cache[2], cajas))
	planta.__dict__["_cache_contenido"] = cache
	_indice, de_aberturas, de_elementos = cache
	contenido: dict[int, list[Any]] = {id(espacio): [] for espacio in planta.espacios}
	vistas: set[int] = set()
	for abertura in planta.aberturas:
		vistas.add(id(abertura))
		clave = (abertura.a, abertura.b)
		guardado = de_aberturas.get(id(abertura))
		if guardado is None or guardado[0] is not abertura or guardado[1] != clave:
			guardado = (abertura, clave, edicion.espacios_bajo_abertura(planta, abertura, indice))
			de_aberturas[id(abertura)] = guardado
		for espacio in guardado[2]:
			if id(espacio) in contenido:
				contenido[id(espacio)].append(abertura)
	for elemento in [*planta.objetos, *planta.fuentes, *planta.referencias, *planta.zonas]:
		vistas.add(id(elemento))
		try:
			centro = edicion.centro_de(elemento)
		except ValueError, TypeError, ZeroDivisionError:
			continue
		guardado = de_elementos.get(id(elemento))
		if guardado is None or guardado[0] is not elemento or guardado[1] != centro:
			guardado = (elemento, centro, planta.espacio_en(*centro))
			de_elementos[id(elemento)] = guardado
		espacio = guardado[2]
		if espacio is not None and id(espacio) in contenido:
			contenido[id(espacio)].append(elemento)
	# Se olvida lo de los elementos que ya no están (borrados): no se guardan referencias a ellos.
	for guardados in (de_aberturas, de_elementos):
		for sobrante in [clave for clave in guardados if clave not in vistas]:
			del guardados[sobrante]
	return contenido


#: Más espacios cambiados que esto (importar una planta, duplicar medio barrio) y se sitúa todo de nuevo:
#: mirar cada elemento contra cientos de cajas costaría más que volver a empezar.
MAX_CAJAS_CAMBIADAS = 64
# Holguras con que el índice espacial preselecciona: una abertura o un punto más lejos de la caja de un
# espacio que esto no puede haber cambiado de espacio porque ese espacio cambie.
_HOLGURA_ABERTURA = TOLERANCIA_PARED + 2e-5
_HOLGURA_PUNTO = 4e-5


def _toca(caja: tuple[float, float, float, float], cajas: list[tuple[float, float, float, float]], holgura: float) -> bool:
	x0, y0, x1, y1 = caja
	return any(x0 - holgura <= c[2] and c[0] <= x1 + holgura and y0 - holgura <= c[3] and c[1] <= y1 + holgura for c in cajas)


def _olvidar_cerca(
	de_aberturas: dict[int, Any], de_elementos: dict[int, Any], cajas: list[tuple[float, float, float, float]]
) -> tuple[dict[int, Any], dict[int, Any]]:
	"""Lo ya situado, sin lo que cae cerca de alguna caja cambiada (eso se vuelve a situar).

	Primero se mira la caja que envuelve a todas las cambiadas, con
	comparaciones sueltas: casi todo queda lejos y se descarta sin más.
	"""
	if not cajas:
		return de_aberturas, de_elementos
	holgura = max(_HOLGURA_ABERTURA, _HOLGURA_PUNTO)
	ux0 = min(c[0] for c in cajas) - holgura
	uy0 = min(c[1] for c in cajas) - holgura
	ux1 = max(c[2] for c in cajas) + holgura
	uy1 = max(c[3] for c in cajas) + holgura
	aberturas: dict[int, Any] = {}
	for clave, guardado in de_aberturas.items():
		(ax, ay), (bx, by) = guardado[1]
		if (ax < ux0 and bx < ux0) or (ax > ux1 and bx > ux1) or (ay < uy0 and by < uy0) or (ay > uy1 and by > uy1):
			aberturas[clave] = guardado
		elif not _toca(geo.caja(guardado[1]), cajas, _HOLGURA_ABERTURA):
			aberturas[clave] = guardado
	elementos: dict[int, Any] = {}
	for clave, guardado in de_elementos.items():
		x, y = guardado[1]
		if x < ux0 or x > ux1 or y < uy0 or y > uy1 or not _toca((x, y, x, y), cajas, _HOLGURA_PUNTO):
			elementos[clave] = guardado
	return aberturas, elementos


def _espacio_de(planta: Planta, elemento: Any) -> Espacio | None:
	"""Espacio al que pertenece un elemento con posición (None si está fuera de todos)."""
	try:
		x, y = edicion.centro_de(elemento)
	except ValueError, TypeError, ZeroDivisionError:
		return None
	return planta.espacio_en(x, y)


def _mismos_hijos(previo: Nodo, elementos: list[Any], cambiados: set[str]) -> bool:
	"""True si el nodo ya enseña esos elementos, en ese orden, y ninguno ha cambiado (su texto sigue valiendo)."""
	hijos = previo.hijos
	if len(hijos) != len(elementos):
		return False
	for nodo, elemento in zip(hijos, elementos, strict=True):
		if nodo.id != elemento.id or elemento.id in cambiados:
			return False
	return True


def _nodo_planta(planta: Planta, catalogo: Catalogo | None, previo: Nodo | None, cambiados: set[str] | None) -> Nodo:
	"""El nodo de una planta. Con ``previo`` y ``cambiados``, reutiliza los nodos de lo que no ha cambiado.

	Un espacio cuyo id no está en ``cambiados`` y cuyo contenido (calculado por
	partes con ``contenido_de_planta``) sigue siendo el mismo conserva su nodo
	tal cual: la ventana lo reconoce por identidad y no toca su nodo nativo.
	"""
	nodo_planta = Nodo(planta.id, _texto_nodo(planta, catalogo), planta.id)
	previos = {hijo.clave: hijo for hijo in previo.hijos} if previo is not None and cambiados is not None else {}
	cambiados = cambiados if cambiados is not None else set()
	colocados: set[str] = set()
	contenido = contenido_de_planta(planta)
	for espacio in planta.espacios:
		dentro = contenido[id(espacio)]
		anterior = previos.get(espacio.id)
		if anterior is not None and espacio.id not in cambiados and _mismos_hijos(anterior, dentro, cambiados):
			nodo_espacio = anterior
		else:
			nodo_espacio = Nodo(espacio.id, _texto_nodo(espacio, catalogo), espacio.id)
			nodo_espacio.hijos = [Nodo(f"{espacio.id}/{hijo.id}", _texto_nodo(hijo, catalogo), hijo.id) for hijo in dentro]
		colocados.update(hijo.id for hijo in dentro)
		nodo_planta.hijos.append(nodo_espacio)
	grupos: list[tuple[str, str, list[Any]]] = [
		("paredes", _("Paredes sueltas"), list(planta.paredes)),
		("vias", _("Calles"), list(planta.vias)),
		(
			"sueltos",
			_("Fuera de todo espacio"),
			[e for e in [*planta.aberturas, *planta.objetos, *planta.fuentes, *planta.referencias, *planta.zonas] if e.id not in colocados],
		),
	]
	for clave, titulo, elementos in grupos:
		if not elementos:
			continue
		clave_grupo = f"{PREFIJO_GRUPO}{planta.id}:{clave}"
		texto = _("{titulo}: {n}").format(titulo=titulo, n=len(elementos))
		anterior = previos.get(clave_grupo)
		if anterior is not None and anterior.texto == texto and _mismos_hijos(anterior, elementos, cambiados):
			nodo_planta.hijos.append(anterior)
			continue
		grupo = Nodo(clave_grupo, texto)
		grupo.hijos = [Nodo(f"{clave_grupo}/{e.id}", _texto_nodo(e, catalogo), e.id) for e in elementos]
		nodo_planta.hijos.append(grupo)
	if (
		previo is not None
		and previo.texto == nodo_planta.texto
		and len(previo.hijos) == len(nodo_planta.hijos)
		and all(map(operator.is_, previo.hijos, nodo_planta.hijos, strict=True))
	):
		return previo
	return nodo_planta


def arbol_de(entorno: Entorno, catalogo: Catalogo | None = None, anterior: Nodo | None = None, afectados: Afectados | None = None) -> Nodo:
	"""El árbol del entorno: entorno → plantas → espacios → lo de cada espacio; paredes, vías y conectores.

	Con ``anterior`` (el árbol del estado de justo antes) y ``afectados`` (lo
	que dice el parche del historial que ha cambiado), el árbol nuevo
	COMPARTE con el anterior los nodos de lo que no ha cambiado: las plantas no
	tocadas son el mismo objeto y, en la planta tocada, también los espacios
	cuyo contenido sigue igual. Así la ventana solo reescribe los nodos
	nativos afectados (con 3.000 espacios, rehacer el árbol entero tras cada
	edición era la mitad de lo que tardaba). El resultado es IGUAL (``==``) al
	del árbol hecho desde cero. Si se añaden o quitan plantas, se hace entero.
	"""
	parcial = anterior is not None and afectados is not None and not afectados.estructura
	previas = {hijo.clave: hijo for hijo in anterior.hijos} if parcial and anterior is not None else {}
	raiz = Nodo(CLAVE_ENTORNO, _("{nombre} (entorno)").format(nombre=entorno.nombre or _("Entorno sin nombre")))
	for planta in sorted(entorno.plantas, key=lambda p: p.nivel):
		previa = previas.get(planta.id)
		if previa is not None and afectados is not None and planta.id not in afectados.elementos and planta.id not in afectados.plantas:
			# Nada de esta planta ha cambiado: el mismo nodo.
			raiz.hijos.append(previa)
			continue
		cambiados = afectados.elementos.get(planta.id, set()) if previa is not None and afectados is not None else None
		raiz.hijos.append(_nodo_planta(planta, catalogo, previa, cambiados))
	if entorno.conectores:
		grupo = Nodo(CLAVE_CONECTORES, _("Escaleras, rampas y ascensores: {n}").format(n=len(entorno.conectores)))
		grupo.hijos = [Nodo(conector.id, _texto_nodo(conector, catalogo), conector.id) for conector in entorno.conectores]
		raiz.hijos.append(grupo)
	return raiz


# ── Lista ────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Fila:
	"""Una fila de la lista de elementos."""

	id: str
	nombre: str
	tipo: str
	medidas: str
	posicion: str

	def celdas(self) -> tuple[str, str, str, str]:
		"""Los textos de las cuatro columnas."""
		return self.nombre, self.tipo, self.medidas, self.posicion


def fila_de(elemento: Any, catalogo: Catalogo | None = None) -> Fila:
	"""La fila de un elemento."""
	return Fila(elemento.id, nombre_de(elemento), nombre_tipo(elemento, catalogo), texto_medidas(elemento), texto_posicion(elemento))


def _elementos_por_id(entorno: Entorno, planta: Planta | None = None) -> dict[str, Any]:
	"""Id → elemento de todo el entorno, o solo de ``planta`` (el primero si un id se repitiera, como ``Entorno.elemento``)."""
	por_id: dict[str, Any] = {}
	if planta is not None:
		por_id[planta.id] = planta
		for elemento in planta.elementos():
			por_id.setdefault(elemento.id, elemento)
		return por_id
	for planta_entorno in entorno.plantas:
		por_id.setdefault(planta_entorno.id, planta_entorno)
	for _planta, elemento in entorno.elementos():
		por_id.setdefault(elemento.id, elemento)
	return por_id


def _planta_del_nodo(entorno: Entorno, arbol: Nodo, clave: str) -> Planta | None:
	"""La planta bajo la que cuelga un nodo del árbol (None si cuelga del entorno, como los conectores)."""
	nodo = arbol.padre_de(clave)
	while nodo is not None:
		planta = entorno.planta(nodo.id) if nodo.id else None
		if planta is not None:
			return planta
		nodo = arbol.padre_de(nodo.clave)
	return None


class FilasPerezosas(Sequence[Fila]):
	"""Las filas de una lista de elementos, compuestas la primera vez que se piden.

	Componer una fila (medidas, posición, tipo) cuesta poco, pero una planta de
	un barrio importado tiene miles de elementos y la lista virtual solo pide
	las que se ven. Se comporta como una lista de ``Fila`` de solo lectura.
	"""

	def __init__(self, elementos: list[Any], catalogo: Catalogo | None) -> None:
		self._elementos = elementos
		self._catalogo = catalogo
		self._hechas: dict[int, Fila] = {}

	def __len__(self) -> int:
		return len(self._elementos)

	@property
	def elementos(self) -> list[Any]:
		"""Los elementos de las filas, en su orden (para saber si la lista sigue enseñando lo mismo)."""
		return self._elementos

	def olvidar(self, indice: int) -> None:
		"""Olvida la fila ya compuesta de ``indice`` (su elemento ha cambiado): se compone otra vez al pedirla."""
		self._hechas.pop(indice, None)

	@overload
	def __getitem__(self, indice: int) -> Fila: ...

	@overload
	def __getitem__(self, indice: slice) -> list[Fila]: ...

	def __getitem__(self, indice: int | slice) -> Fila | list[Fila]:
		if isinstance(indice, slice):
			return [self[i] for i in range(*indice.indices(len(self)))]
		if indice < 0:
			indice += len(self._elementos)
		if not 0 <= indice < len(self._elementos):
			raise IndexError(indice)
		fila = self._hechas.get(indice)
		if fila is None:
			fila = fila_de(self._elementos[indice], self._catalogo)
			self._hechas[indice] = fila
		return fila


def elementos_de_nodo(entorno: Entorno, clave: str, arbol: Nodo | None = None) -> list[Any]:
	"""Los elementos que la lista enseña cuando en el árbol está elegido el nodo ``clave``.

	El entorno enseña sus plantas y conectores; una planta, todo lo suyo; un
	espacio, lo que contiene; un grupo, sus miembros; y un elemento suelto,
	los de su mismo contenedor (así la lista no se queda con una sola fila
	y se puede pasar al vecino).

	``arbol`` es el árbol ya construido del mismo entorno (el que enseña la
	ventana): pasarlo evita reconstruirlo en cada clic, que con un barrio de
	miles de espacios era lo que dejaba el Estudio colgado.
	"""
	if clave in ("", CLAVE_ENTORNO):
		return [*sorted(entorno.plantas, key=lambda p: p.nivel), *entorno.conectores]
	if clave == CLAVE_CONECTORES:
		return list(entorno.conectores)
	if arbol is None:
		arbol = arbol_de(entorno)
	nodo = arbol.buscar(clave)
	if nodo is None:
		return []
	planta = entorno.planta(nodo.id) if nodo.id else None
	if planta is not None:
		return list(planta.elementos())
	if nodo.hijos or clave.startswith(PREFIJO_GRUPO) and "/" not in clave:
		# Solo los elementos de su planta: buscarlos en todo un barrio era lo que más tardaba la lista tras editar.
		por_id = _elementos_por_id(entorno, _planta_del_nodo(entorno, arbol, clave))
		return [elemento for elemento in (por_id.get(hijo.id) for hijo in nodo.hijos) if elemento is not None]
	encontrado = entorno.buscar(nodo.id) if nodo.id else None
	if encontrado is None:
		return []
	planta_del, elemento = encontrado
	if isinstance(elemento, Espacio) and planta_del is not None:
		# Los hijos de un espacio en el árbol son su contenido (``arbol_de`` los saca de ``contenido_de_planta``):
		# si no tiene, no hay nada dentro, y no hace falta situar otra vez todos los elementos de la planta.
		return []
	if isinstance(elemento, Conector):
		return list(entorno.conectores)
	if "/" in clave:
		padre = arbol.buscar(clave.rsplit("/", 1)[0])
		if padre is not None:
			por_id = _elementos_por_id(entorno, _planta_del_nodo(entorno, arbol, clave))
			return [e for e in (por_id.get(hijo.id) for hijo in padre.hijos) if e is not None]
	return [elemento]


def filas_de_nodo(entorno: Entorno, clave: str, catalogo: Catalogo | None = None, arbol: Nodo | None = None) -> list[Fila]:
	"""Las filas de la lista para el nodo elegido en el árbol (``arbol``: el ya construido, para no rehacerlo)."""
	return [fila_de(elemento, catalogo) for elemento in elementos_de_nodo(entorno, clave, arbol)]


# ── Propiedades ──────────────────────────────────────────────────────────────


def resolver(entorno: Entorno, id_elemento: str) -> tuple[Planta | None, Any]:
	"""(planta, elemento) de un id de elemento, de planta o la clave del entorno."""
	if id_elemento in ("", CLAVE_ENTORNO):
		return None, entorno
	planta = entorno.planta(id_elemento)
	if planta is not None:
		return planta, planta
	return edicion.resolver(entorno, id_elemento)


def valores_de(entorno: Entorno, elemento: Any, catalogo: Catalogo | None = None) -> dict[str, Any]:
	"""Los valores de un elemento con las claves de su esquema de propiedades."""
	valores: dict[str, Any] = {"nombre": getattr(elemento, "nombre", ""), "descripcion": getattr(elemento, "descripcion", "")}
	if isinstance(elemento, Entorno):
		valores.update(
			autor=elemento.autor,
			inicio_planta=elemento.inicio.planta,
			inicio_x=elemento.inicio.x,
			inicio_y=elemento.inicio.y,
			inicio_rumbo=elemento.inicio.rumbo,
			procedencia=_texto_procedencia(elemento),
		)
	elif isinstance(elemento, Planta):
		valores.update(nivel=elemento.nivel, altura_m=elemento.altura_m, exterior=elemento.exterior)
	elif isinstance(elemento, Espacio):
		x0, y0, x1, y1 = geo.caja(elemento.contorno) if elemento.contorno else (0.0, 0.0, 0.0, 0.0)
		valores.update(
			tipo=elemento.tipo,
			x=x0,
			y=y0,
			ancho=x1 - x0,
			fondo=y1 - y0,
			suelo=elemento.suelo,
			acustica=elemento.acustica,
			pared_material=elemento.pared_material,
			cerrado=elemento.cerrado,
			macizo=elemento.macizo,
			contorno=texto_de_puntos(elemento.contorno),
		)
		for clave in ("semaforo", "sonoro", "pulsador", "isleta"):
			valores[clave] = bool(elemento.datos.get(clave, False))
	elif isinstance(elemento, Pared):
		valores.update(
			ax=elemento.a[0],
			ay=elemento.a[1],
			bx=elemento.b[0],
			by=elemento.b[1],
			grosor=elemento.grosor,
			altura=elemento.altura,
			material=elemento.material,
			bloquea_paso=elemento.bloquea_paso,
			bloquea_sonido=elemento.bloquea_sonido,
		)
	elif isinstance(elemento, Abertura):
		valores.update(
			tipo=elemento.tipo,
			ancho=elemento.ancho,
			estado=elemento.estado,
			hoja=elemento.hoja,
			material=elemento.material,
			es_salida=elemento.es_salida,
		)
	elif isinstance(elemento, Objeto):
		definicion = catalogo.definicion_de(elemento) if catalogo is not None else None
		valores.update(
			tipo_objeto=definicion.nombre
			if definicion is not None
			else _("{tipo} (complemento no instalado: se trata como una caja)").format(tipo=elemento.tipo),
			variante=elemento.variante,
			x=elemento.x,
			y=elemento.y,
			rumbo=elemento.rumbo,
			ancho=elemento.ancho,
			fondo=elemento.fondo,
			alto=elemento.alto,
			estado=elemento.estado,
		)
	elif isinstance(elemento, FuenteSonido):
		valores.update(
			x=elemento.x,
			y=elemento.y,
			sonido=elemento.sonido,
			volumen=int(round(elemento.volumen * 100)),
			radio=elemento.radio,
			bucle=elemento.bucle,
			intervalo=elemento.intervalo,
			altura=elemento.altura,
		)
	elif isinstance(elemento, ZonaSuelo):
		x0, y0, x1, y1 = geo.caja(elemento.contorno) if elemento.contorno else (0.0, 0.0, 0.0, 0.0)
		valores.update(x=x0, y=y0, ancho=x1 - x0, fondo=y1 - y0, suelo=elemento.suelo)
	elif isinstance(elemento, Referencia):
		valores.update(x=elemento.x, y=elemento.y, tipo=elemento.tipo, permanente=elemento.permanente)
	elif isinstance(elemento, Via):
		valores.update(
			ancho=elemento.ancho,
			carriles=elemento.carriles,
			sentido=elemento.sentido,
			trafico=elemento.trafico,
			velocidad_kmh=elemento.velocidad_kmh,
		)
	elif isinstance(elemento, Conector):
		valores.update(
			tipo_conector=nombre_visible(TIPOS_CONECTOR, elemento.tipo),
			pasamanos=elemento.datos.get("pasamanos", "ninguno"),
			anchura=elemento.datos.get("anchura", 1.0),
			aviso_hablado=bool(elemento.datos.get("aviso_hablado", False)),
		)
	return valores


def _texto_procedencia(entorno: Entorno) -> str:
	"""De dónde viene el entorno, en una frase; vacío si se hizo a mano."""
	procedencia = entorno.procedencia or {}
	partes = [str(procedencia[clave]) for clave in ("fuente", "fecha", "licencia") if procedencia.get(clave)]
	return ", ".join(partes)


def _distinto(a: Any, b: Any) -> bool:
	"""True si dos valores difieren de verdad (los números, con una tolerancia de medio milímetro)."""
	if isinstance(a, (int, float)) and isinstance(b, (int, float)) and not isinstance(a, bool) and not isinstance(b, bool):
		return abs(float(a) - float(b)) > 0.0005
	return a != b


def valores_cambiados(entorno: Entorno, id_elemento: str, nuevos: dict[str, Any], catalogo: Catalogo | None = None) -> dict[str, Any]:
	"""Los valores de ``nuevos`` que difieren de los que tiene el elemento (para no apuntar en el historial un «cambio» que no cambia nada)."""
	_planta, elemento = resolver(entorno, id_elemento)
	actuales = valores_de(entorno, elemento, catalogo)
	# Un texto vacío y la falta de valor son lo mismo para la persona.
	return {
		clave: valor
		for clave, valor in nuevos.items()
		if clave in actuales and _distinto(actuales[clave], valor) and (actuales[clave] or valor)
	}


def aplicar_valores(entorno: Entorno, id_elemento: str, nuevos: dict[str, Any], catalogo: Catalogo | None = None) -> list[str]:
	"""Aplica al elemento los valores que hayan cambiado y devuelve las claves cambiadas.

	Se llama DENTRO de ``contexto.ejecutar``. Usa las funciones de edición
	cuando existen, para que el cambio arrastre lo que depende de él: al
	mover una habitación se mueven sus puertas y sus muebles, al cambiar sus
	medidas se reescala, al girar un objeto gira su huella. El resto de
	propiedades (suelo, material, estado…) son datos del propio elemento.
	Lanza ``ErrorEdicion`` si un valor no se puede aplicar.
	"""
	_planta, elemento = resolver(entorno, id_elemento)
	actuales = valores_de(entorno, elemento, catalogo)
	cambios = valores_cambiados(entorno, id_elemento, nuevos, catalogo)
	if not cambios:
		return []
	if "nombre" in cambios:
		if not str(cambios["nombre"]).strip():
			raise ErrorEdicion(_("El nombre no puede quedar vacío."))
		if isinstance(elemento, Entorno):
			elemento.nombre = str(cambios["nombre"]).strip()
		else:
			edicion.renombrar(entorno, elemento, str(cambios["nombre"]).strip())
	if "descripcion" in cambios:
		elemento.descripcion = str(cambios["descripcion"] or "")

	def nuevo(clave: str) -> Any:
		return cambios.get(clave, actuales.get(clave))

	if isinstance(elemento, Entorno):
		if "autor" in cambios:
			elemento.autor = str(cambios["autor"] or "")
		if any(clave.startswith("inicio_") for clave in cambios):
			planta_inicio = entorno.planta(str(nuevo("inicio_planta")))
			if planta_inicio is None:
				raise ErrorEdicion(_("Elija la planta del punto de inicio."))
			edicion.fijar_inicio(
				entorno,
				planta_inicio,
				float(nuevo("inicio_x") or 0.0),
				float(nuevo("inicio_y") or 0.0),
				float(nuevo("inicio_rumbo") or 0.0),
			)
	elif isinstance(elemento, Planta):
		if "nivel" in cambios:
			nivel = int(cambios["nivel"])
			if any(otra is not elemento and otra.nivel == nivel for otra in entorno.plantas):
				raise ErrorEdicion(_("Ya hay otra planta en el nivel {nivel}.").format(nivel=nivel))
			elemento.nivel = nivel
		if "altura_m" in cambios:
			elemento.altura_m = float(cambios["altura_m"])
		if "exterior" in cambios:
			elemento.exterior = bool(cambios["exterior"])
	elif isinstance(elemento, (Espacio, ZonaSuelo)):
		if "ancho" in cambios or "fondo" in cambios:
			edicion.redimensionar(entorno, elemento, ancho=float(nuevo("ancho")), fondo=float(nuevo("fondo")), catalogo=catalogo)
		if "x" in cambios or "y" in cambios:
			edicion.mover(entorno, elemento, float(nuevo("x")) - float(actuales["x"]), float(nuevo("y")) - float(actuales["y"]))
		for clave in ("tipo", "suelo", "acustica", "pared_material", "cerrado", "macizo"):
			if clave in cambios and hasattr(elemento, clave):
				setattr(elemento, clave, cambios[clave])
		if isinstance(elemento, Espacio):
			for clave in ("semaforo", "sonoro", "pulsador", "isleta"):
				if clave in cambios:
					elemento.datos[clave] = bool(cambios[clave])
	elif isinstance(elemento, Pared):
		if any(clave in cambios for clave in ("ax", "ay", "bx", "by")):
			a = (float(nuevo("ax")), float(nuevo("ay")))
			b = (float(nuevo("bx")), float(nuevo("by")))
			if geo.distancia(a, b) < 0.05:
				raise ErrorEdicion(_("Los dos extremos de la pared no pueden estar en el mismo punto."))
			elemento.a, elemento.b = a, b
		for clave in ("grosor", "altura"):
			if clave in cambios:
				if float(cambios[clave]) <= 0:
					raise ErrorEdicion(_("El grosor y la altura tienen que ser mayores que cero."))
				setattr(elemento, clave, float(cambios[clave]))
		for clave in ("material", "bloquea_paso", "bloquea_sonido"):
			if clave in cambios:
				setattr(elemento, clave, cambios[clave])
	elif isinstance(elemento, Abertura):
		if "ancho" in cambios:
			edicion.redimensionar(entorno, elemento, ancho=float(cambios["ancho"]))
		for clave in ("tipo", "estado", "hoja", "material", "es_salida"):
			if clave in cambios:
				setattr(elemento, clave, cambios[clave])
	elif isinstance(elemento, Objeto):
		if "variante" in cambios:
			definicion = catalogo.definicion_de(elemento) if catalogo is not None else None
			variante = definicion.variante(str(cambios["variante"])) if definicion is not None and cambios["variante"] else None
			elemento.variante = str(cambios["variante"] or "")
			if variante is not None and not any(clave in cambios for clave in ("ancho", "fondo", "alto")):
				edicion.redimensionar(entorno, elemento, ancho=variante.ancho, fondo=variante.fondo, alto=variante.alto, catalogo=catalogo)
		if any(clave in cambios for clave in ("ancho", "fondo", "alto")):
			edicion.redimensionar(
				entorno, elemento, ancho=float(nuevo("ancho")), fondo=float(nuevo("fondo")), alto=float(nuevo("alto")), catalogo=catalogo
			)
		if "x" in cambios or "y" in cambios:
			edicion.mover_a(entorno, elemento, float(nuevo("x")), float(nuevo("y")))
		if "rumbo" in cambios:
			edicion.girar(entorno, elemento, float(cambios["rumbo"]) - float(actuales["rumbo"]))
		if "estado" in cambios:
			elemento.estado = str(cambios["estado"] or "")
	elif isinstance(elemento, FuenteSonido):
		if "x" in cambios or "y" in cambios:
			edicion.mover_a(entorno, elemento, float(nuevo("x")), float(nuevo("y")))
		if "volumen" in cambios:
			elemento.volumen = max(0.0, min(1.0, float(cambios["volumen"]) / 100.0))
		for clave in ("radio", "intervalo", "altura"):
			if clave in cambios:
				setattr(elemento, clave, float(cambios[clave] or 0.0))
		if "sonido" in cambios:
			elemento.sonido = str(cambios["sonido"] or "")
		if "bucle" in cambios:
			elemento.bucle = bool(cambios["bucle"])
	elif isinstance(elemento, Referencia):
		if "x" in cambios or "y" in cambios:
			edicion.mover_a(entorno, elemento, float(nuevo("x")), float(nuevo("y")))
		for clave in ("tipo", "permanente"):
			if clave in cambios:
				setattr(elemento, clave, cambios[clave])
	elif isinstance(elemento, Via):
		if "ancho" in cambios:
			edicion.redimensionar(entorno, elemento, ancho=float(cambios["ancho"]))
		for clave, tipo in (("carriles", int), ("sentido", str), ("trafico", int), ("velocidad_kmh", float)):
			if clave in cambios:
				setattr(elemento, clave, tipo(cambios[clave]))
	elif isinstance(elemento, Conector):
		for clave in ("pasamanos", "anchura", "aviso_hablado"):
			if clave in cambios:
				elemento.datos[clave] = cambios[clave]
	return sorted(cambios)


# ── Puntos escritos ──────────────────────────────────────────────────────────


def texto_de_puntos(puntos: Iterable[Punto]) -> str:
	"""Una lista de puntos como se escribe en un formulario: «0 0; 4 0; 4 3»."""
	return "; ".join(f"{texto_numero(x, 3)} {texto_numero(y, 3)}" for x, y in puntos)


def puntos_de_texto(texto: str, minimo: int = 2) -> list[Punto]:
	"""Lee puntos escritos como «0 0; 4 0; 4 3» (x e y separadas por un espacio; los puntos, por punto y coma).

	La coma queda libre para los decimales, que es como se escriben en
	español. Lanza ``ErrorEdicion`` con una frase que dice qué punto está mal.
	"""
	puntos: list[Punto] = []
	for numero, trozo in enumerate((t.strip() for t in texto.replace("\n", ";").split(";")), start=1):
		if not trozo:
			continue
		partes = trozo.split()
		if len(partes) != 2:
			raise ErrorEdicion(
				_(
					"El punto {n} («{texto}») no se entiende. Escriba la x y la y separadas por un espacio, y los puntos separados por punto y coma."
				).format(n=numero, texto=trozo)
			)
		try:
			x, y = leer_numero(partes[0]), leer_numero(partes[1])
		except ValueError as error:
			raise ErrorEdicion(_("El punto {n} («{texto}») no tiene dos números.").format(n=numero, texto=trozo)) from error
		puntos.append((float(x or 0.0), float(y or 0.0)))
	if len(puntos) < minimo:
		raise ErrorEdicion(_("Hacen falta al menos {n} puntos.").format(n=minimo))
	return puntos


# ── Búsqueda y posiciones ────────────────────────────────────────────────────


def buscar_elementos(entorno: Entorno, texto: str, catalogo: Catalogo | None = None) -> list[tuple[str, str]]:
	"""Elementos cuyo nombre, tipo o id contiene todas las palabras de ``texto``: [(id, «nombre (tipo), planta»)]."""
	palabras = sin_acentos(texto).split()
	encontrados: list[tuple[str, str]] = []
	candidatos: list[tuple[Planta | None, Any]] = [(planta, planta) for planta in entorno.plantas]
	candidatos.extend(entorno.elementos())
	for planta, elemento in candidatos:
		donde = sin_acentos(" ".join((nombre_de(elemento), nombre_tipo(elemento, catalogo), elemento.id)))
		if all(palabra in donde for palabra in palabras):
			rotulo = _texto_nodo(elemento, catalogo)
			if planta is not None and planta is not elemento:
				rotulo = _("{elemento}, en {planta}").format(elemento=rotulo, planta=nombre_de(planta))
			encontrados.append((elemento.id, rotulo))
	return encontrados


def posicion_junto_a(entorno: Entorno, id_elemento: str) -> Posicion | None:
	"""Punto desde el que empezar a recorrer «junto a» un elemento: su centro, o el del espacio si es un mueble que corta el paso.

	Devuelve None si el elemento no tiene sitio (el entorno entero, un grupo).
	"""
	try:
		planta, elemento = resolver(entorno, id_elemento)
	except ErrorEdicion:
		return None
	if isinstance(elemento, Entorno):
		return None
	if isinstance(elemento, Planta):
		if not elemento.espacios:
			return None
		x, y = elemento.espacios[0].centro()
		return Posicion(elemento.id, x, y, 0.0)
	if isinstance(elemento, Conector):
		posiciones = elemento.posiciones()
		return posiciones[0].copia() if posiciones else None
	if planta is None:
		return None
	x, y = edicion.centro_de(elemento)
	rumbo = 0.0
	if isinstance(elemento, Objeto):
		# Delante del objeto, a medio metro de su frente, mirándolo: dentro de él no se puede empezar.
		separacion = elemento.fondo / 2.0 + 0.5
		frente = geo.punto_a_distancia((x, y), elemento.rumbo, separacion)
		espacio = planta.espacio_en(*frente, incluir_macizos=False)
		if espacio is not None:
			return Posicion(planta.id, frente[0], frente[1], (elemento.rumbo + 180.0) % 360.0)
		espacio = planta.espacio_en(x, y, incluir_macizos=False)
		if espacio is not None:
			x, y = espacio.centro()
	return Posicion(planta.id, x, y, rumbo)


def rumbo_cardinal(rumbo: float) -> str:
	"""«norte», «noreste»… de un rumbo en grados."""
	return geo.punto_cardinal(rumbo)


# ── Plantillas del asistente «Nuevo entorno» ─────────────────────────────────


def _plantilla_en_blanco(nombre: str, autor: str) -> Entorno:
	entorno = edicion.crear_entorno(nombre, autor=autor)
	edicion.crear_planta(entorno, _("Planta baja"))
	return entorno


def _plantilla_exterior(nombre: str, autor: str) -> Entorno:
	entorno = edicion.crear_entorno(nombre, autor=autor)
	edicion.crear_planta(entorno, _("Calle"), exterior=True)
	return entorno


def _plantilla_vivienda(nombre: str, autor: str) -> Entorno:
	entorno = ejemplos.vivienda_ejemplo()
	entorno.nombre = nombre
	entorno.autor = autor
	entorno.id = edicion.crear_entorno(nombre).id
	entorno.procedencia = {}
	return entorno


def _plantilla_aula(nombre: str, autor: str) -> Entorno:
	entorno = edicion.crear_entorno(nombre, autor=autor)
	planta = edicion.crear_planta(entorno, _("Planta baja"))
	pasillo = edicion.crear_habitacion_rectangular(entorno, planta, _("Pasillo"), 0.0, 0.0, 9.0, 2.0, tipo="pasillo")
	aula = edicion.crear_habitacion_adosada(entorno, planta, _("Aula"), pasillo, "norte", 9.0, 7.0)
	aula.datos["uso"] = "aula"
	edicion.anadir_puerta_entre(entorno, planta, pasillo, aula, desplazamiento=1.0)
	edicion.anadir_puerta(entorno, planta, pasillo, "oeste", nombre=_("Entrada"), es_salida=True)
	edicion.fijar_inicio(entorno, planta, 1.0, 1.0, 90.0)
	return entorno


def _plantilla_oficinas(nombre: str, autor: str) -> Entorno:
	entorno = edicion.crear_entorno(nombre, autor=autor)
	planta = edicion.crear_planta(entorno, _("Planta baja"))
	pasillo = edicion.crear_habitacion_rectangular(entorno, planta, _("Pasillo"), 0.0, 0.0, 12.0, 2.0, tipo="pasillo")
	for numero in range(3):
		despacho = edicion.crear_habitacion_adosada(
			entorno, planta, _("Despacho {n}").format(n=numero + 1), pasillo, "norte", 4.0, 4.0, desplazamiento=4.0 * numero
		)
		despacho.datos["uso"] = "oficina"
		edicion.anadir_puerta_entre(entorno, planta, pasillo, despacho)
	sala = edicion.crear_habitacion_adosada(entorno, planta, _("Sala de reuniones"), pasillo, "sur", 6.0, 4.0)
	edicion.anadir_puerta_entre(entorno, planta, pasillo, sala)
	edicion.anadir_puerta(entorno, planta, pasillo, "oeste", nombre=_("Entrada"), es_salida=True)
	edicion.fijar_inicio(entorno, planta, 1.0, 1.0, 90.0)
	return entorno


def _plantilla_cruce(nombre: str, autor: str) -> Entorno:
	entorno = edicion.crear_entorno(nombre, autor=autor)
	planta = edicion.crear_planta(entorno, _("Calle"), exterior=True)
	mayor = edicion.crear_calle(entorno, planta, _("Calle Mayor"), [(-40.0, 0.0), (40.0, 0.0)])
	rio = edicion.crear_calle(entorno, planta, _("Calle del Río"), [(0.0, -40.0), (0.0, 40.0)])
	edicion.crear_cruce(entorno, planta, mayor, rio)
	edicion.crear_paso_peatones(entorno, planta, mayor, (-8.0, 0.0), semaforo=True, sonoro=True)
	edicion.crear_paso_peatones(entorno, planta, rio, (0.0, 8.0))
	edicion.fijar_inicio(entorno, planta, -20.0, 4.0, 90.0)
	return entorno


def _plantilla_parada(nombre: str, autor: str) -> Entorno:
	entorno = edicion.crear_entorno(nombre, autor=autor)
	planta = edicion.crear_planta(entorno, _("Calle"), exterior=True)
	calle = edicion.crear_calle(entorno, planta, _("Avenida"), [(-30.0, 0.0), (30.0, 0.0)])
	edicion.crear_paso_peatones(entorno, planta, calle, (10.0, 0.0), semaforo=True, sonoro=True, pulsador=True)
	edicion.crear_parada(entorno, planta, _("Parada de autobús"), -5.0, 4.0)
	edicion.fijar_inicio(entorno, planta, -20.0, 4.0, 90.0)
	return entorno


#: Plantillas del asistente: clave → (nombre visible, explicación, función que la construye).
PLANTILLAS: dict[str, tuple[str, str, Callable[[str, str], Entorno]]] = {
	"en_blanco": (N_("Interior en blanco"), N_("Un entorno con una planta baja vacía."), _plantilla_en_blanco),
	"exterior": (N_("Exterior en blanco"), N_("Un entorno con un plano de calle vacío."), _plantilla_exterior),
	"vivienda": (N_("Vivienda tipo"), N_("Entrada, pasillo, salón, cocina, dormitorio y baño, con sus puertas."), _plantilla_vivienda),
	"aula": (N_("Aula"), N_("Un aula de 9 por 7 metros con su pasillo y su entrada."), _plantilla_aula),
	"oficinas": (N_("Planta de oficinas"), N_("Un pasillo con tres despachos y una sala de reuniones."), _plantilla_oficinas),
	"cruce": (
		N_("Tramo de calle con cruce"),
		N_("Dos calles con aceras que se cruzan y dos pasos de peatones, uno con semáforo sonoro."),
		_plantilla_cruce,
	),
	"parada": (N_("Parada de autobús"), N_("Una avenida con aceras, un paso con semáforo y una parada de autobús."), _plantilla_parada),
}


def crear_de_plantilla(clave: str, nombre: str, autor: str = "") -> Entorno:
	"""Construye un entorno nuevo a partir de una plantilla del asistente."""
	if clave not in PLANTILLAS:
		raise ErrorEdicion(_("No existe la plantilla «{clave}».").format(clave=clave))
	nombre = nombre.strip()
	if not nombre:
		raise ErrorEdicion(_("Escriba un nombre para el entorno."))
	return PLANTILLAS[clave][2](nombre, autor.strip())


def esquinas_rectangulo(x: float, y: float, ancho: float, fondo: float) -> list[Punto]:
	"""Las cuatro esquinas de un rectángulo con su esquina suroeste en (x, y)."""
	return geo.rectangulo(float(x), float(y), float(ancho), float(fondo))


def finito(valor: Any) -> bool:
	"""True si el valor es un número utilizable."""
	return isinstance(valor, (int, float)) and math.isfinite(valor)


# ── Complementos que faltan ──────────────────────────────────────────────────


def complementos_que_faltan(entorno: Entorno | None, catalogo: Catalogo | None) -> dict[str, int]:
	"""Complementos que usa el entorno y no están instalados: id del complemento → cuántos objetos suyos hay.

	Un objeto cuyo ``tipo`` (``complemento/objeto``) no está en el catálogo
	se conserva con sus medidas y se dibuja como una caja; esto solo cuenta
	cuáles faltan para avisar UNA vez al abrir. Sin catálogo (no se pudo
	cargar) no se dice nada: faltarían todos, y ese fallo ya está en el registro.
	"""
	if entorno is None or catalogo is None:
		return {}
	objetos = [objeto for planta in entorno.plantas for objeto in planta.objetos]
	tipos = set(catalogo.tipos_que_faltan(objetos))
	cuentas: dict[str, int] = {}
	for objeto in objetos:
		if objeto.tipo in tipos:
			complemento = objeto.tipo.split("/", 1)[0]
			cuentas[complemento] = cuentas.get(complemento, 0) + 1
	return dict(sorted(cuentas.items()))


def texto_complementos_que_faltan(faltan: dict[str, int]) -> str:
	"""El aviso que se enseña al abrir un entorno con complementos que no están instalados; «» si no falta ninguno."""
	if not faltan:
		return ""
	lista = ", ".join(faltan)
	objetos = sum(faltan.values())
	return " ".join(
		(
			_n(
				"Este entorno usa el complemento {lista}, que no está instalado.",
				"Este entorno usa los complementos {lista}, que no están instalados.",
				len(faltan),
			).format(lista=lista),
			_n(
				"Su objeto se conserva y se ve como una caja con sus medidas.",
				"Sus {n} objetos se conservan y se ven como cajas con sus medidas.",
				objetos,
			).format(n=objetos),
			_("¿Buscar en el catálogo en línea?"),
		)
	)
