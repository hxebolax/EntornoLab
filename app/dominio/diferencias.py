"""Diferencias entre dos estados de un entorno: lo que guarda el historial para deshacer y rehacer.

Por qué existe: el historial guardaba una copia ENTERA del entorno antes de
cada operación. Con un barrio importado de 3.000 espacios eran unos 9 MB y
30 ms por operación al guardarla, 25 ms más al recuperarla, y el entorno
recuperado era otro objeto que el Estudio tenía que volver a enseñar desde
cero (árbol, lista y plano). Con cien niveles de deshacer, casi un gigabyte.
Ahora cada operación guarda solo lo que ha cambiado (un ``Parche``) y
deshacer lo aplica sobre el MISMO entorno.

Cómo se calcula, sin que la operación tenga que decir nada:

1. ``tomar_foto(entorno)`` ANTES de la operación apunta, de cada elemento de
   cada planta, el objeto y una huella: los valores de sus campos en
   ``marshal`` (en C: unos 9 ms para diez mil elementos). También los campos
   del entorno, los de cada planta y los conectores.
2. ``comparar(foto, entorno)`` DESPUÉS vuelve a sacar las huellas y empareja
   los elementos por IDENTIDAD (el mismo objeto antes y después). Los que
   faltan se han quitado, los nuevos se han puesto y los que tienen otra
   huella se han cambiado. De esos pocos se guarda su forma serializada
   (``a_dict``): entera si se ha puesto o quitado, solo los campos que
   cambian si se ha cambiado; y la posición en su lista, para volver a
   dejarlos donde estaban.
3. ``aplicar(entorno, parche, hacia_atras)`` deja el entorno como estaba antes
   (deshacer) o después (rehacer), en el sitio: cambia los campos de los
   objetos que siguen (así no cambia su identidad), quita los puestos y
   vuelve a poner los quitados en su posición.

Así es imposible que un cambio se quede fuera del parche: no depende de que
cada operación declare lo que toca, se compara todo. Lo único que se exige es
lo que ya exigía el índice espacial: un contorno se SUSTITUYE, no se cambia
en el sitio (la huella lo vería igual, pero el índice no).
"""

from __future__ import annotations

import itertools
import logging
import marshal
import operator
from collections.abc import Iterable
from dataclasses import dataclass, field
from typing import Any

from app.dominio.modelo import LISTA_DE_CLASE, Conector, Entorno, Planta, Serializable, _a_basico, _nombres_de_campos

log = logging.getLogger(__name__)

# Versión 2 de marshal: sin referencias compartidas. La 3 marca los objetos que
# se repiten, y dos estados iguales podrían dar huellas distintas.
VERSION_MARSHAL = 2

#: Las listas de elementos de una planta, en su orden.
LISTAS_PLANTA: tuple[str, ...] = tuple(LISTA_DE_CLASE.values())
#: Clase de los elementos de cada lista de una planta.
CLASE_DE_LISTA: dict[str, type[Serializable]] = {nombre: clase for clase, nombre in LISTA_DE_CLASE.items()}
#: Campos propios de una planta (los que no son listas de elementos).
CAMPOS_PLANTA: tuple[str, ...] = tuple(campo for campo in _nombres_de_campos(Planta) if campo not in LISTAS_PLANTA)
#: Campos propios del entorno (todo menos las plantas y los conectores).
CAMPOS_ENTORNO: tuple[str, ...] = tuple(campo for campo in _nombres_de_campos(Entorno) if campo not in ("plantas", "conectores"))

_LECTORES: dict[type, operator.attrgetter[Any]] = {}
_FALTA = object()


class ErrorParche(RuntimeError):
	"""El entorno no está como el parche espera: algo lo cambió sin pasar por el historial."""


# ── Huellas ──────────────────────────────────────────────────────────────────


def _lector(clase: type) -> operator.attrgetter[Any]:
	"""Función (en C) que da la tupla de los valores de los campos de un elemento de esa clase."""
	lector = _LECTORES.get(clase)
	if lector is None:
		lector = operator.attrgetter(*_nombres_de_campos(clase))
		_LECTORES[clase] = lector
	return lector


def _huella(elemento: Any) -> bytes:
	"""Huella de un elemento: sus valores en ``marshal``; si alguno no se deja (un objeto dentro), su ``a_dict``."""
	try:
		return marshal.dumps(_lector(type(elemento))(elemento), VERSION_MARSHAL)
	except ValueError, TypeError, AttributeError:
		return marshal.dumps(elemento.a_dict(), VERSION_MARSHAL)


def _huellas(elementos: list[Any]) -> list[bytes]:
	"""Huellas de todos los elementos de una lista.

	Con todos de la misma clase y con valores simples (lo normal en una
	planta), se hace entero en C: ``attrgetter`` saca los valores y
	``marshal`` los convierte, sin un bucle de Python por elemento.
	"""
	if not elementos:
		return []
	clase = type(elementos[0])
	if all(map(operator.is_, map(type, elementos), itertools.repeat(clase))):
		try:
			return list(map(marshal.dumps, map(_lector(clase), elementos), itertools.repeat(VERSION_MARSHAL)))
		except ValueError, TypeError, AttributeError:
			log.debug("Lista de %s con valores que marshal no admite: huellas una a una", clase.__name__)
	# Un conector (sus tramos son objetos), una lista mezclada o datos raros: uno a uno, con su a_dict si hace falta.
	return [_huella(elemento) for elemento in elementos]


def _desde_huella(huella: bytes, clase: type) -> dict[str, Any]:
	"""El ``a_dict`` del elemento tal como estaba cuando se sacó la huella."""
	valores = marshal.loads(huella)
	if isinstance(valores, dict):
		return valores
	return {campo: _a_basico(valor) for campo, valor in zip(_nombres_de_campos(clase), valores, strict=True)}


def _campos(objeto: Any, campos: tuple[str, ...]) -> dict[str, Any]:
	"""Los campos propios (sin listas de elementos) de un entorno o una planta, serializados."""
	return {campo: _a_basico(getattr(objeto, campo)) for campo in campos}


@dataclass(slots=True)
class _FotoLista:
	"""Una lista de elementos tal como estaba: los objetos (por identidad) y la huella de cada uno."""

	objetos: list[Any]
	huellas: list[bytes]


def _foto_lista(elementos: list[Any]) -> _FotoLista:
	return _FotoLista(list(elementos), _huellas(elementos))


@dataclass(slots=True)
class _FotoPlanta:
	planta: Planta
	campos: dict[str, Any]
	listas: dict[str, _FotoLista]


@dataclass(slots=True)
class Foto:
	"""El estado de un entorno antes de una operación, en huellas: lo que ``comparar`` necesita.

	Solo vive mientras dura la operación (el historial la tira al cerrarla):
	no hay una por nivel de deshacer.
	"""

	entorno: Entorno
	campos: dict[str, Any]
	plantas: list[_FotoPlanta]
	conectores: _FotoLista


def tomar_foto(entorno: Entorno) -> Foto:
	"""Apunta el estado del entorno ANTES de una operación (unos milisegundos incluso con miles de espacios)."""
	plantas = [
		_FotoPlanta(planta, _campos(planta, CAMPOS_PLANTA), {nombre: _foto_lista(getattr(planta, nombre)) for nombre in LISTAS_PLANTA})
		for planta in entorno.plantas
	]
	return Foto(entorno, _campos(entorno, CAMPOS_ENTORNO), plantas, _foto_lista(entorno.conectores))


# ── Parches ──────────────────────────────────────────────────────────────────


@dataclass(slots=True)
class Modificacion:
	"""Un elemento que sigue en su lista pero ha cambiado: sus posiciones y SOLO los campos que cambian."""

	posicion_antes: int
	posicion_despues: int
	id_antes: str
	id_despues: str
	antes: dict[str, Any]
	despues: dict[str, Any]


@dataclass(slots=True)
class CambioLista:
	"""Lo que cambia en una lista de elementos (los de una lista de una planta, los conectores o las plantas).

	``quitados``: (posición en la lista de ANTES, elemento entero), de menor a
	mayor. ``puestos``: (posición en la lista de DESPUÉS, elemento entero), de
	menor a mayor. Con las posiciones se vuelve a dejar cada elemento donde
	estaba: el orden de las listas importa (decide, por ejemplo, los empates
	del índice espacial y el orden del árbol).
	"""

	quitados: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
	puestos: list[tuple[int, dict[str, Any]]] = field(default_factory=list)
	cambiados: list[Modificacion] = field(default_factory=list)

	@property
	def vacio(self) -> bool:
		"""True si la lista no cambia."""
		return not (self.quitados or self.puestos or self.cambiados)

	def ids(self) -> set[str]:
		"""Ids de los elementos que se quitan, se ponen o cambian (antes y después)."""
		ids = {str(datos.get("id", "")) for _posicion, datos in (*self.quitados, *self.puestos)}
		for modificacion in self.cambiados:
			ids.add(modificacion.id_antes)
			ids.add(modificacion.id_despues)
		ids.discard("")
		return ids


@dataclass(slots=True)
class CambioPlanta:
	"""Lo que cambia en una planta que está antes y después: sus campos propios y sus listas."""

	id: str
	posicion_antes: int
	posicion_despues: int
	antes: dict[str, Any] = field(default_factory=dict)
	despues: dict[str, Any] = field(default_factory=dict)
	listas: dict[str, CambioLista] = field(default_factory=dict)


@dataclass
class Afectados:
	"""Qué toca un parche, dicho para quien tiene que enseñarlo (el árbol, la lista, el plano).

	``elementos``: id de planta → ids de los elementos de esa planta que se
	ponen, se quitan o cambian. ``plantas``: plantas cuyos campos propios
	cambian (nombre, nivel…). ``estructura``: se añaden o se quitan plantas.
	``conectores``: ids de los conectores que cambian. ``entorno``: campos del
	propio entorno que cambian (nombre, inicio, contador de ids…).
	"""

	elementos: dict[str, set[str]] = field(default_factory=dict)
	plantas: set[str] = field(default_factory=set)
	estructura: bool = False
	conectores: set[str] = field(default_factory=set)
	entorno: set[str] = field(default_factory=set)

	def ids(self) -> set[str]:
		"""Todos los ids que cambian: elementos, plantas y conectores."""
		todos = set(self.plantas) | self.conectores
		for ids in self.elementos.values():
			todos |= ids
		return todos


@dataclass
class Parche:
	"""Lo que una operación ha cambiado en el entorno, con el «antes» y el «después» de cada cosa."""

	entorno_antes: dict[str, Any] = field(default_factory=dict)
	entorno_despues: dict[str, Any] = field(default_factory=dict)
	#: Plantas que se añaden o se quitan ENTERAS (``cambiados`` no se usa: lo de dentro va en ``en_plantas``).
	plantas: CambioLista = field(default_factory=CambioLista)
	en_plantas: list[CambioPlanta] = field(default_factory=list)
	conectores: CambioLista = field(default_factory=CambioLista)
	_afectados: Afectados | None = field(default=None, repr=False, compare=False)

	@property
	def vacio(self) -> bool:
		"""True si la operación no cambió nada."""
		return not (self.entorno_antes or self.entorno_despues or self.en_plantas) and self.plantas.vacio and self.conectores.vacio

	def afectados(self) -> Afectados:
		"""Qué elementos, plantas y conectores toca (se calcula una vez)."""
		if self._afectados is None:
			afectados = Afectados(
				estructura=not self.plantas.vacio,
				conectores=self.conectores.ids(),
				entorno=set(self.entorno_antes) | set(self.entorno_despues),
			)
			for cambio in self.en_plantas:
				if cambio.antes or cambio.despues:
					afectados.plantas.add(cambio.id)
				ids: set[str] = set()
				for lista in cambio.listas.values():
					ids |= lista.ids()
				if ids:
					afectados.elementos[cambio.id] = ids
			afectados.plantas |= self.plantas.ids()
			self._afectados = afectados
		return self._afectados

	def foco(self, hacia_atras: bool) -> str:
		"""Id del elemento al que debe ir la selección tras deshacer (``hacia_atras``) o rehacer; «» si no hay.

		Primero un elemento que cambia; si no, uno que vuelve a aparecer (lo
		borrado, al deshacer; lo creado, al rehacer); si no, la planta tocada.
		Siempre algo que EXISTE después de aplicar el parche.
		"""
		for cambio in self.en_plantas:
			for nombre in LISTAS_PLANTA:
				lista = cambio.listas.get(nombre)
				if lista is not None and lista.cambiados:
					modificacion = lista.cambiados[0]
					return modificacion.id_antes if hacia_atras else modificacion.id_despues
		for cambio in self.en_plantas:
			for nombre in LISTAS_PLANTA:
				lista = cambio.listas.get(nombre)
				vuelven = (lista.quitados if hacia_atras else lista.puestos) if lista is not None else []
				if vuelven:
					return str(vuelven[0][1].get("id", ""))
		conectores = self.conectores
		if conectores.cambiados:
			return conectores.cambiados[0].id_antes if hacia_atras else conectores.cambiados[0].id_despues
		vuelven = conectores.quitados if hacia_atras else conectores.puestos
		if vuelven:
			return str(vuelven[0][1].get("id", ""))
		plantas = self.plantas.quitados if hacia_atras else self.plantas.puestos
		if plantas:
			return str(plantas[0][1].get("id", ""))
		return self.en_plantas[0].id if self.en_plantas else ""

	def tamano(self) -> int:
		"""Bytes que ocupa lo guardado, aproximadamente (lo que mide cuánto crece el historial)."""
		partes: list[Any] = [self.entorno_antes, self.entorno_despues]
		for lista in self._listas():
			partes.extend(datos for _posicion, datos in (*lista.quitados, *lista.puestos))
			partes.extend((m.antes, m.despues) for m in lista.cambiados)
		partes.extend((cambio.antes, cambio.despues) for cambio in self.en_plantas)
		return len(marshal.dumps(partes, VERSION_MARSHAL))

	def _listas(self) -> Iterable[CambioLista]:
		yield self.plantas
		yield self.conectores
		for cambio in self.en_plantas:
			yield from cambio.listas.values()


# ── Comparar ─────────────────────────────────────────────────────────────────


def _parcial(antes: dict[str, Any], despues: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
	"""Solo las claves que cambian, con su valor antes y después."""
	claves = [clave for clave, valor in despues.items() if antes.get(clave, _FALTA) != valor]
	claves.extend(clave for clave in antes if clave not in despues)
	return {c: antes[c] for c in claves if c in antes}, {c: despues[c] for c in claves if c in despues}


def _emparejar(antes: list[Any], despues: list[Any]) -> tuple[list[int], list[int], list[tuple[int, int]]]:
	"""(posiciones quitadas, posiciones puestas, pares de posiciones del mismo objeto) entre dos listas.

	Si los objetos que siguen han cambiado de ORDEN entre sí (o un objeto
	está dos veces), no se puede describir con quitar y poner: se da la lista
	entera por quitada y puesta, que también es correcto.
	"""
	todos = (list(range(len(antes))), list(range(len(despues))), [])
	posiciones: dict[int, int] = {}
	for numero, objeto in enumerate(antes):
		if id(objeto) in posiciones:
			return todos
		posiciones[id(objeto)] = numero
	vistos: set[int] = set()
	puestos: list[int] = []
	pares: list[tuple[int, int]] = []
	ultimo = -1
	for numero, objeto in enumerate(despues):
		previo = posiciones.get(id(objeto))
		if previo is None or id(objeto) in vistos:
			puestos.append(numero)
			continue
		if previo < ultimo:
			return todos
		ultimo = previo
		vistos.add(id(objeto))
		pares.append((previo, numero))
	quitados = [numero for numero, objeto in enumerate(antes) if id(objeto) not in vistos]
	return quitados, puestos, pares


def _comparar_lista(foto: _FotoLista, actuales: list[Any], despues: list[_FotoLista] | None = None) -> CambioLista:
	"""Lo que ha cambiado en una lista desde su foto (y, en ``despues``, la foto de la lista tal como está ahora)."""
	huellas = _huellas(actuales)
	if despues is not None:
		despues.append(_FotoLista(list(actuales), huellas))
	antes = foto.objetos
	if len(antes) == len(actuales) and all(map(operator.is_, antes, actuales, strict=True)):
		# Lo más frecuente (mover, cambiar una propiedad): los mismos objetos; solo se buscan las huellas distintas, en C.
		distintas = itertools.compress(range(len(huellas)), map(operator.ne, foto.huellas, huellas, strict=True))
		pares: Iterable[tuple[int, int]] = ((numero, numero) for numero in distintas)
		quitados: list[int] = []
		puestos: list[int] = []
	else:
		quitados, puestos, todos_los_pares = _emparejar(antes, actuales)
		pares = ((a, d) for a, d in todos_los_pares if foto.huellas[a] != huellas[d])
	cambio = CambioLista(
		quitados=[(numero, _desde_huella(foto.huellas[numero], type(antes[numero]))) for numero in quitados],
		puestos=[(numero, actuales[numero].a_dict()) for numero in puestos],
	)
	for posicion_antes, posicion_despues in pares:
		objeto = actuales[posicion_despues]
		completo_antes = _desde_huella(foto.huellas[posicion_antes], type(objeto))
		completo_despues = objeto.a_dict()
		parcial_antes, parcial_despues = _parcial(completo_antes, completo_despues)
		if not parcial_antes and not parcial_despues:
			# Cambió por debajo del redondeo con que se guarda (décimas de milímetro): no es un cambio.
			continue
		cambio.cambiados.append(
			Modificacion(
				posicion_antes,
				posicion_despues,
				str(completo_antes.get("id", "")),
				str(completo_despues.get("id", "")),
				parcial_antes,
				parcial_despues,
			)
		)
	return cambio


def _planta_desde_foto(foto: _FotoPlanta) -> dict[str, Any]:
	"""El ``a_dict`` completo de una planta tal como estaba en la foto."""
	datos = dict(foto.campos)
	for nombre in LISTAS_PLANTA:
		lista = foto.listas[nombre]
		datos[nombre] = [_desde_huella(huella, type(objeto)) for objeto, huella in zip(lista.objetos, lista.huellas, strict=True)]
	# El mismo orden de claves que ``Planta.a_dict``.
	return {campo: datos[campo] for campo in _nombres_de_campos(Planta)}


def comparar(foto: Foto, entorno: Entorno) -> Parche:
	"""El parche que lleva de la foto (antes de la operación) al entorno tal como está ahora."""
	return comparar_y_fotografiar(foto, entorno)[0]


def comparar_y_fotografiar(foto: Foto, entorno: Entorno) -> tuple[Parche, Foto]:
	"""El parche desde la foto y, de paso, la foto del entorno tal como está ahora.

	La foto de después sale casi gratis (las huellas ya se han sacado para
	comparar) y vale como foto de ANTES de la operación siguiente si nadie toca
	el entorno entre medias: el historial se ahorra así sacarla otra vez.
	"""
	campos_ahora = _campos(entorno, CAMPOS_ENTORNO)
	entorno_antes, entorno_despues = _parcial(foto.campos, campos_ahora)
	parche = Parche(entorno_antes=entorno_antes, entorno_despues=entorno_despues)
	conectores_ahora: list[_FotoLista] = []
	parche.conectores = _comparar_lista(foto.conectores, entorno.conectores, conectores_ahora)
	quitadas, puestas, pares = _emparejar([f.planta for f in foto.plantas], entorno.plantas)
	parche.plantas = CambioLista(
		quitados=[(numero, _planta_desde_foto(foto.plantas[numero])) for numero in quitadas],
		puestos=[(numero, entorno.plantas[numero].a_dict()) for numero in puestas],
	)
	fotos_plantas: dict[int, _FotoPlanta] = {}
	for posicion_antes, posicion_despues in pares:
		foto_planta = foto.plantas[posicion_antes]
		planta = entorno.plantas[posicion_despues]
		campos_planta = _campos(planta, CAMPOS_PLANTA)
		antes, despues = _parcial(foto_planta.campos, campos_planta)
		listas = {}
		listas_ahora: dict[str, _FotoLista] = {}
		for nombre in LISTAS_PLANTA:
			ahora: list[_FotoLista] = []
			cambio_lista = _comparar_lista(foto_planta.listas[nombre], getattr(planta, nombre), ahora)
			listas_ahora[nombre] = ahora[0]
			if not cambio_lista.vacio:
				listas[nombre] = cambio_lista
		fotos_plantas[posicion_despues] = _FotoPlanta(planta, campos_planta, listas_ahora)
		if antes or despues or listas:
			parche.en_plantas.append(CambioPlanta(planta.id, posicion_antes, posicion_despues, antes, despues, listas))
	despues_foto = Foto(
		entorno,
		campos_ahora,
		[
			fotos_plantas[numero]
			if numero in fotos_plantas
			else _FotoPlanta(planta, _campos(planta, CAMPOS_PLANTA), {n: _foto_lista(getattr(planta, n)) for n in LISTAS_PLANTA})
			for numero, planta in enumerate(entorno.plantas)
		],
		conectores_ahora[0],
	)
	return parche, despues_foto


# ── Aplicar ──────────────────────────────────────────────────────────────────


def _copia(datos: dict[str, Any]) -> dict[str, Any]:
	"""Copia honda (en C) de lo guardado en un parche.

	``de_dict`` solo copia el primer nivel de diccionarios y listas: sin esto,
	una lista dentro de ``datos`` quedaría compartida entre el entorno y el
	parche, y un cambio posterior en el sitio estropearía el historial.
	"""
	return marshal.loads(marshal.dumps(datos, VERSION_MARSHAL))


def _poner_campos(objeto: Any, parcial: dict[str, Any]) -> None:
	"""Pone en el objeto (sin sustituirlo) los campos guardados, convertidos como al abrir un fichero."""
	if not parcial:
		return
	nuevo = type(objeto).de_dict(_copia(parcial))
	campos = _nombres_de_campos(type(objeto))
	for campo in parcial:
		if campo in campos:
			# ``setattr`` y no el diccionario: un contorno nuevo caduca así el índice espacial de su planta.
			setattr(objeto, campo, getattr(nuevo, campo))


def _id_en(lista: list[Any], posicion: int) -> str | None:
	return str(getattr(lista[posicion], "id", "")) if 0 <= posicion < len(lista) else None


def _comprobar_lista(lista: list[Any], cambio: CambioLista, hacia_atras: bool, donde: str) -> None:
	"""Lanza ``ErrorParche`` si la lista no está como el parche espera, ANTES de tocar nada."""
	presentes = cambio.puestos if hacia_atras else cambio.quitados
	for modificacion in cambio.cambiados:
		posicion = modificacion.posicion_despues if hacia_atras else modificacion.posicion_antes
		esperado = modificacion.id_despues if hacia_atras else modificacion.id_antes
		if _id_en(lista, posicion) != esperado:
			raise ErrorParche(f"{donde}: en la posición {posicion} se esperaba «{esperado}» y hay «{_id_en(lista, posicion)}»")
	for posicion, datos in presentes:
		esperado = str(datos.get("id", ""))
		if _id_en(lista, posicion) != esperado:
			raise ErrorParche(f"{donde}: en la posición {posicion} se esperaba «{esperado}» y hay «{_id_en(lista, posicion)}»")
	ausentes = cambio.quitados if hacia_atras else cambio.puestos
	final = len(lista) - len(presentes) + len(ausentes)
	if any(posicion > final for posicion, _datos in ausentes):
		raise ErrorParche(f"{donde}: la lista tiene {len(lista)} elementos y el parche no cabe")


def _aplicar_lista(lista: list[Any], cambio: CambioLista, clase: type[Serializable], hacia_atras: bool) -> None:
	"""Aplica a una lista los cambios de un parche: campos de los que siguen, quitar los sobrantes y poner los que faltan."""
	for modificacion in cambio.cambiados:
		if hacia_atras:
			_poner_campos(lista[modificacion.posicion_despues], modificacion.antes)
		else:
			_poner_campos(lista[modificacion.posicion_antes], modificacion.despues)
	sobran = cambio.puestos if hacia_atras else cambio.quitados
	faltan = cambio.quitados if hacia_atras else cambio.puestos
	# De atrás adelante para que las posiciones que quedan sigan valiendo; luego de delante atrás al poner.
	for posicion, _datos in reversed(sobran):
		del lista[posicion]
	for posicion, datos in faltan:
		lista.insert(posicion, clase.de_dict(_copia(datos)))


def comprobar(entorno: Entorno, parche: Parche, hacia_atras: bool) -> None:
	"""Lanza ``ErrorParche`` si el parche no se puede aplicar al entorno tal como está (sin cambiar nada)."""
	_comprobar_lista(entorno.conectores, parche.conectores, hacia_atras, "conectores")
	for cambio in parche.en_plantas:
		posicion = cambio.posicion_despues if hacia_atras else cambio.posicion_antes
		if _id_en(entorno.plantas, posicion) != cambio.id:
			raise ErrorParche(f"plantas: en la posición {posicion} se esperaba «{cambio.id}»")
		planta = entorno.plantas[posicion]
		for nombre, cambio_lista in cambio.listas.items():
			_comprobar_lista(getattr(planta, nombre), cambio_lista, hacia_atras, f"{cambio.id}.{nombre}")
	_comprobar_lista(entorno.plantas, parche.plantas, hacia_atras, "plantas")


def aplicar(entorno: Entorno, parche: Parche, hacia_atras: bool) -> None:
	"""Deja el entorno, EN EL SITIO, como estaba antes del parche (``hacia_atras``) o como quedó después.

	Comprueba primero que el entorno está como el parche espera (si no, lanza
	``ErrorParche`` sin haber tocado nada). Solo caduca el índice espacial de
	las plantas cuyos espacios cambian.
	"""
	comprobar(entorno, parche, hacia_atras)
	_aplicar_lista(entorno.conectores, parche.conectores, Conector, hacia_atras)
	# Lo de dentro de las plantas primero: sus posiciones son las de la lista de plantas sin tocar.
	for cambio in parche.en_plantas:
		planta = entorno.plantas[cambio.posicion_despues if hacia_atras else cambio.posicion_antes]
		_poner_campos(planta, cambio.antes if hacia_atras else cambio.despues)
		for nombre, cambio_lista in cambio.listas.items():
			_aplicar_lista(getattr(planta, nombre), cambio_lista, CLASE_DE_LISTA[nombre], hacia_atras)
		if "espacios" in cambio.listas:
			planta.caducar_indice()
	_aplicar_lista(entorno.plantas, parche.plantas, Planta, hacia_atras)
	_poner_campos(entorno, parche.entorno_antes if hacia_atras else parche.entorno_despues)
