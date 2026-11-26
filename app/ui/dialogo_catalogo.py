"""«Insertar objeto»: buscar en el catálogo de complementos y colocar a escala.

Dos pasos, los dos accesibles con teclado y lector de pantalla:

1. ``DialogoCatalogo``: pensado para un catálogo de más de mil objetos. Un
   árbol de clasificación (complemento, categoría, subcategoría, favoritos y
   usados recientemente), búsqueda por texto ordenada por relevancia y
   filtros que se combinan acotan una lista virtual de columnas; la
   miniatura de la huella (solo la de la fila enfocada) acompaña a una
   descripción en texto que dice lo mismo, y se elige la variante.
2. Un formulario de colocación por RELACIÓN, que es como trabaja quien no ve
   el plano: contra una pared, en una esquina, junto a otro elemento o en un
   punto por coordenadas.

Reglas de escala, que son la razón de ser de este módulo: todo se mide en
metros reales, así que antes de tocar el entorno la colocación se ENSAYA
sobre una copia. Si el objeto no cabe ni en su variante menor ni encogido
hasta su mínimo, se explica y no se coloca nada (ni queda nada que deshacer).
Si cabe pero tapa una puerta o deja un paso estrecho, se pregunta con
botones que dicen la acción. Solo entonces se hace el cambio de verdad con
``contexto.ejecutar``, que lo apunta en el historial con su nombre.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import wx

from app.core import paths
from app.core.i18n import N_, _, _n
from app.dominio import colocacion, edicion
from app.dominio.catalogo import AMBITOS, COLOCACIONES, Catalogo, DefObjeto, sin_acentos
from app.dominio.modelo import Abertura, Aviso, Entorno, Objeto, Planta
from app.ui import complemento_propio
from app.ui.accesibilidad.dialogos import crear_botonera, elegir_opcion, mostrar_error, mostrar_mensaje, preparar_dialogo
from app.ui.accesibilidad.lista import ListaAccesible
from app.ui.accesibilidad.nombres import crear_campo
from app.ui.esquemas import Campo, c, texto_numero
from app.ui.formulario import pedir_formulario

log = logging.getLogger(__name__)

TODOS = "*"
RETARDO_BUSQUEDA_MS = 350
# Espera antes de cargar la miniatura de la fila enfocada: al recorrer la lista deprisa no se carga ninguna.
RETARDO_MINIATURA_MS = 250
LADO_MINIATURA = 128

MODOS: dict[str, str] = {
	"pared": N_("Contra una pared"),
	"esquina": N_("En una esquina"),
	"junto": N_("Junto a otro elemento"),
	"punto": N_("En un punto, por coordenadas"),
}
LADOS: dict[str, str] = {"norte": N_("Norte"), "este": N_("Este"), "sur": N_("Sur"), "oeste": N_("Oeste")}
ESQUINAS: dict[str, str] = {
	"noreste": N_("Noreste"),
	"noroeste": N_("Noroeste"),
	"sureste": N_("Sureste"),
	"suroeste": N_("Suroeste"),
}
ALINEACIONES: dict[str, str] = {
	"centro": N_("Centrado"),
	"inicio": N_("En el extremo oeste o sur de la pared"),
	"fin": N_("En el extremo este o norte de la pared"),
	"distancia": N_("A una distancia del extremo oeste o sur"),
}


# ── Textos del catálogo (sin ventanas) ───────────────────────────────────────


def texto_medidas(definicion: DefObjeto) -> str:
	"""«2 × 0,9 × 0,85 m»: ancho, fondo y alto normales."""
	return _("{ancho} × {fondo} × {alto} m").format(
		ancho=texto_numero(definicion.rango("ancho")[1]),
		fondo=texto_numero(definicion.rango("fondo")[1]),
		alto=texto_numero(definicion.rango("alto")[1]),
	)


def fila_de(catalogo: Catalogo, definicion: DefObjeto) -> tuple[str, str, str, str]:
	"""Celdas de un objeto en la lista: nombre, categoría, medidas y complemento."""
	complemento = catalogo.complemento(definicion.complemento)
	return (
		definicion.nombre,
		catalogo.nombre_categoria(definicion.categoria) if definicion.categoria else "",
		texto_medidas(definicion),
		complemento.nombre if complemento is not None else definicion.complemento,
	)


def texto_descripcion(catalogo: Catalogo, definicion: DefObjeto) -> str:
	"""Todo lo que la miniatura enseña, y más, en frases: es lo que lee quien no ve la imagen."""
	lineas = [definicion.nombre + "."]
	if definicion.descripcion:
		lineas.append(definicion.descripcion)
	for dimension, nombre in (("ancho", _("Ancho")), ("fondo", _("Fondo")), ("alto", _("Alto"))):
		minimo, normal, maximo = definicion.rango(dimension)
		if abs(maximo - minimo) < 0.005:
			lineas.append(_("{medida}: {normal} metros, fijo.").format(medida=nombre, normal=texto_numero(normal)))
		else:
			lineas.append(
				_("{medida}: {normal} metros (de {minimo} a {maximo}).").format(
					medida=nombre, normal=texto_numero(normal), minimo=texto_numero(minimo), maximo=texto_numero(maximo)
				)
			)
	forma = complemento_propio.FORMAS.get(definicion.forma.get("tipo", "rectangulo"), complemento_propio.FORMAS["rectangulo"])
	lineas.append(_("Forma de su planta: {forma}.").format(forma=_(forma).lower()))
	if definicion.variantes:
		lineas.append(
			_("Variantes: {lista}.").format(
				lista="; ".join(
					_("{nombre}, {ancho} por {fondo} metros").format(
						nombre=v.nombre, ancho=texto_numero(v.ancho), fondo=texto_numero(v.fondo)
					)
					for v in definicion.variantes
				)
			)
		)
	if definicion.colocacion:
		lineas.append(_("Se coloca: {lista}.").format(lista=", ".join(_(COLOCACIONES.get(k, k)).lower() for k in definicion.colocacion)))
	if definicion.ambito:
		lineas.append(_("Ámbito: {lista}.").format(lista=", ".join(_(AMBITOS.get(k, k)).lower() for k in definicion.ambito)))
	lineas.append(_("Corta el paso.") if definicion.bloquea else _("No corta el paso: se puede pisar o atravesar."))
	if definicion.altura_base > 0:
		lineas.append(_("Su base queda a {metros} metros del suelo.").format(metros=texto_numero(definicion.altura_base)))
	if not definicion.detectable_baston:
		lineas.append(_("No se detecta con el bastón."))
	if definicion.contenedor:
		lineas.append(_("Puede esconder un premio."))
	subcategoria = str(getattr(definicion, "subcategoria", "") or "")
	if definicion.categoria:
		clasificacion = catalogo.nombre_categoria(definicion.categoria)
		if subcategoria:
			nombre_sub = getattr(catalogo.complemento(definicion.complemento), "nombre_subcategoria", None)
			clasificacion += ", " + (str(nombre_sub(subcategoria)) if callable(nombre_sub) else subcategoria.replace("_", " ")).lower()
		lineas.append(_("Clasificación: {valor}.").format(valor=clasificacion))
	for faceta, nombre_faceta in (
		("lugar", _("Lugares")),
		("estancia", _("Estancias")),
		("funcion", _("Función")),
		("obstaculo", _("Tipo de obstáculo")),
	):
		valores = valores_de(definicion, faceta)
		if valores:
			lineas.append(
				_("{faceta}: {lista}.").format(faceta=nombre_faceta, lista=", ".join(nombre_valor(faceta, v).lower() for v in valores))
			)
	riesgos = [str(riesgo) for riesgo in getattr(definicion, "riesgos", None) or []]
	if riesgos:
		lineas.append(_("Riesgos: {lista}.").format(lista=", ".join(nombre_valor("riesgo", r).lower() for r in riesgos)))
	if tiene_sonido_propio(definicion):
		lineas.append(_("Tiene sonido propio."))
	if definicion.estados:
		lineas.append(
			_("Estados: {lista}.").format(lista=", ".join(catalogo.nombre_estado(definicion.tipo, e) for e in definicion.estados))
		)
	lineas.append(_("Símbolo en el plano: letra «{letra}».").format(letra=definicion.letra()))
	descripcion_imagen = str(definicion.imagen.get("descripcion") or "")
	if descripcion_imagen:
		lineas.append(_("Imagen: {descripcion}").format(descripcion=descripcion_imagen))
	return "\n".join(lineas)


def ruta_miniatura(catalogo: Catalogo, definicion: DefObjeto) -> Path | None:
	"""PNG de la huella: el del complemento si lo trae; si no, uno generado en la caché. None si no se pudo."""
	complemento = catalogo.complemento(definicion.complemento)
	fichero = str(definicion.imagen.get("fichero") or "")
	if complemento is not None and fichero:
		ruta = complemento.ruta_recurso(fichero)
		if ruta is not None and ruta.is_file():
			return ruta
	try:
		destino = paths.ruta_cache() / "miniaturas" / f"{definicion.complemento}_{definicion.id}.png"
		if not destino.is_file():
			complemento_propio.generar_miniatura(definicion, destino, lado=LADO_MINIATURA)
		return destino
	except OSError, ValueError:
		log.warning("No se pudo generar la miniatura de %s", definicion.tipo, exc_info=True)
		return None


# ── Clasificación, facetas y relevancia (sin ventanas) ───────────────────────
#
# El dominio está ampliando la ficha de los objetos (subcategoría, lugares,
# estancias, función, tipo de obstáculo, frecuencia) y el catálogo (``arbol``,
# ``facetas``, ``relacionados``). Todo lo de aquí funciona tanto si eso ya
# existe como si no: se pregunta con ``getattr`` y, a falta de ello, se deduce
# de lo que hay (complementos, categorías y los campos de siempre).

#: Facetas que se filtran con una lista: clave interna → (etiqueta con letra, atributos posibles, tablas posibles del dominio).
FACETAS: dict[str, tuple[str, tuple[str, ...], tuple[str, ...]]] = {
	"lugar": (N_("&Lugar:"), ("lugares", "lugar"), ("LUGARES",)),
	"estancia": (N_("&Estancia:"), ("estancias", "estancia"), ("ESTANCIAS",)),
	"funcion": (N_("F&unción:"), ("funcion", "funciones"), ("FUNCIONES",)),
	# ``clase_obstaculo`` va primero: es la declarada o, si no la hay, la que el dominio deduce de las medidas.
	"obstaculo": (
		N_("Tipo de ob&stáculo:"),
		("clase_obstaculo", "obstaculo", "tipo_obstaculo", "obstaculos"),
		("OBSTACULOS", "TIPOS_OBSTACULO", "TIPOS_DE_OBSTACULO"),
	),
	# «Ries&go»: la R ya es de «Objetos relacionados».
	"riesgo": (N_("Ries&go:"), ("riesgos", "riesgo"), ("RIESGOS",)),
}
_FRECUENCIAS = {"muy_comun": 3.0, "comun": 2.0, "ocasional": 1.0, "muy_alta": 3.0, "alta": 3.0, "media": 2.0, "baja": 1.0, "rara": 1.0}
MAX_RECIENTES = 30
FICHERO_USO = "catalogo_uso.json"

# Nodos del árbol de clasificación.
NODO_TODOS = ("todos",)
NODO_FAVORITOS = ("favoritos",)
NODO_RECIENTES = ("recientes",)


def valores_de(definicion: Any, faceta: str) -> list[str]:
	"""Valores de una faceta en una ficha (lista vacía si la ficha no tiene ese campo todavía)."""
	for atributo in FACETAS[faceta][1]:
		valor = getattr(definicion, atributo, None)
		if valor in (None, "", [], ()):
			continue
		if isinstance(valor, str):
			return [valor]
		if isinstance(valor, (list, tuple, set, frozenset)):
			return [str(v) for v in valor if v not in (None, "")]
		return [str(valor)]
	return []


def subcategoria_de(definicion: Any) -> str:
	"""Subcategoría de una ficha, o cadena vacía."""
	return str(getattr(definicion, "subcategoria", "") or "")


def frecuencia_de(definicion: Any) -> float:
	"""Lo habitual que es un objeto, como número para ordenar (0 si la ficha no lo dice)."""
	valor = getattr(definicion, "frecuencia", None)
	if isinstance(valor, bool) or valor in (None, ""):
		return 0.0
	if isinstance(valor, (int, float)):
		return float(valor)
	return _FRECUENCIAS.get(str(valor).strip().lower(), 0.0)


def tiene_sonido_propio(definicion: Any) -> bool:
	"""True si el objeto suena él solo (un frigorífico, un semáforo). Usa lo que diga el dominio si ya lo sabe."""
	propio = getattr(definicion, "tiene_sonido_propio", None)
	if isinstance(propio, bool):
		return propio
	sonidos = getattr(definicion, "sonidos", None) or {}
	if sonidos.get("propio"):
		return True
	dinamica = getattr(definicion, "dinamica", None) or {}
	return bool(dinamica.get("sonoro"))


def nombre_valor(faceta: str, valor: str) -> str:
	"""Nombre visible de un valor de faceta: el que declare el dominio o, si no, la clave puesta en limpio."""
	from app.dominio import catalogo as modulo

	taxonomias = getattr(modulo, "TAXONOMIAS", None)
	if isinstance(taxonomias, dict) and valor in (taxonomias.get(faceta) or {}):
		return _(str(taxonomias[faceta][valor]))
	for nombre_tabla in FACETAS.get(faceta, ("", (), ()))[2]:
		tabla = getattr(modulo, nombre_tabla, None)
		if isinstance(tabla, dict) and valor in tabla:
			return _(str(tabla[valor]))
	return valor.replace("_", " ").capitalize()


def facetas_de(definiciones: Sequence[Any]) -> dict[str, list[tuple[str, int]]]:
	"""Valores de cada faceta que tienen algún objeto, con su recuento, ordenados por nombre."""
	resultado: dict[str, list[tuple[str, int]]] = {}
	for faceta in FACETAS:
		cuenta: dict[str, int] = {}
		for definicion in definiciones:
			for valor in valores_de(definicion, faceta):
				cuenta[valor] = cuenta.get(valor, 0) + 1
		resultado[faceta] = sorted(cuenta.items(), key=lambda par: sin_acentos(nombre_valor(faceta, par[0])))
	return resultado


@dataclass
class NodoArbol:
	"""Un nodo de la clasificación: su clave, su texto (sin recuento), cuántos objetos tiene y sus hijos."""

	clave: tuple[str, ...]
	nombre: str
	recuento: int = 0
	hijos: list[NodoArbol] = field(default_factory=list)

	def texto(self) -> str:
		"""«Cocina (34)»: el recuento va en el texto para que el lector lo diga al pasar por el nodo."""
		return _("{nombre} ({n})").format(nombre=self.nombre, n=self.recuento)


def construir_arbol(catalogo: Any) -> list[NodoArbol]:
	"""Complemento → categoría → subcategoría, con recuentos, a partir de las fichas de los complementos activos.

	Se construye siempre de las fichas (y no de un posible ``catalogo.arbol()``)
	para que los recuentos coincidan exactamente con lo que después enseña la
	lista; ``arbol_del_dominio`` da el del dominio cuando existe, y el diálogo
	lo prefiere si tiene la forma esperada.
	"""
	nodos: list[NodoArbol] = []
	for complemento in catalogo.complementos():
		if not getattr(complemento, "activo", True) or not complemento.objetos:
			continue
		nodo = NodoArbol(("comp", complemento.id), complemento.nombre or complemento.id, len(complemento.objetos))
		por_categoria: dict[str, list[Any]] = {}
		for definicion in complemento.objetos:
			por_categoria.setdefault(definicion.categoria or "", []).append(definicion)
		for categoria in sorted(por_categoria, key=lambda c: sin_acentos(catalogo.nombre_categoria(c) if c else "~")):
			fichas = por_categoria[categoria]
			nombre = catalogo.nombre_categoria(categoria) if categoria else _("Sin categoría")
			hijo = NodoArbol(("cat", complemento.id, categoria), nombre, len(fichas))
			subcategorias: dict[str, int] = {}
			for definicion in fichas:
				sub = subcategoria_de(definicion)
				if sub:
					subcategorias[sub] = subcategorias.get(sub, 0) + 1
			nombre_sub = getattr(complemento, "nombre_subcategoria", None) or getattr(catalogo, "nombre_subcategoria", None)
			for sub in sorted(subcategorias, key=sin_acentos):
				visible = str(nombre_sub(sub)) if callable(nombre_sub) else sub.replace("_", " ")
				visible = visible[:1].upper() + visible[1:]
				hijo.hijos.append(NodoArbol(("sub", complemento.id, categoria, sub), visible, subcategorias[sub]))
			nodo.hijos.append(hijo)
		nodos.append(nodo)
	return nodos


def arbol_del_dominio(catalogo: Any) -> list[NodoArbol] | None:
	"""El árbol que dé ``catalogo.arbol()`` si existe y se entiende; None en cualquier otro caso.

	Se admiten nodos como diccionarios u objetos con ``id``, ``nombre``, un
	recuento (``recuento``, ``total`` o ``n``) e hijos (``hijos``,
	``categorias`` o ``subcategorias``). Si algo no cuadra se devuelve None y
	el diálogo usa el árbol construido de las fichas.
	"""
	funcion = getattr(catalogo, "arbol", None)
	if not callable(funcion):
		return None

	def leer(dato: Any, nombres: tuple[str, ...]) -> Any:
		for nombre in nombres:
			valor = dato.get(nombre) if isinstance(dato, dict) else getattr(dato, nombre, None)
			if valor is not None:
				return valor
		return None

	def convertir(bruto: Any, ruta: tuple[str, ...]) -> NodoArbol:
		identificador = leer(bruto, ("id", "clave"))
		if identificador is None:
			raise ValueError("nodo sin id")
		ruta_nueva = (*ruta, str(identificador))
		clave = (("comp", "cat", "sub")[len(ruta_nueva) - 1], *ruta_nueva)
		nodo = NodoArbol(
			clave, str(leer(bruto, ("nombre", "titulo")) or identificador), int(leer(bruto, ("recuento", "total", "n", "objetos")) or 0)
		)
		hijos = leer(bruto, ("hijos", "categorias", "subcategorias")) or []
		if isinstance(hijos, dict):
			hijos = list(hijos.values())
		if len(ruta_nueva) < 3:
			nodo.hijos = [convertir(hijo, ruta_nueva) for hijo in hijos]
		if len(ruta_nueva) == 2 and len(nodo.hijos) == 1 and nodo.hijos[0].clave[-1] == "":
			# Una categoría cuya única hoja es «sin clasificar» no gana nada con ese nivel de más.
			nodo.hijos = []
		return nodo

	try:
		bruto = funcion()
		if isinstance(bruto, dict):
			bruto = list(bruto.values())
		return [convertir(nodo, ()) for nodo in bruto]
	except Exception:  # noqa: BLE001 - el dominio aún puede cambiar la forma del árbol: se usa el propio
		log.info("catalogo.arbol() no tiene la forma esperada; se usa el árbol construido de las fichas.", exc_info=True)
		return None


@dataclass
class Filtros:
	"""Todo lo que acota la lista. Se combinan: un objeto sale si cumple todos."""

	texto: str = ""
	nodo: tuple[str, ...] = NODO_TODOS
	categoria: str | None = None
	ambito: str | None = None
	facetas: dict[str, str] = field(default_factory=dict)
	contenedor: bool = False
	sonido_propio: bool = False
	tipos: frozenset[str] | None = None  # «objetos relacionados»: solo estos tipos


class Indice:
	"""Las fichas activas con sus textos ya normalizados, para filtrar miles de objetos sin que se note.

	Si el catálogo ofrece ``buscar_avanzado`` (el del dominio), el diálogo
	busca con él (``filtrar_con_dominio``): su índice ya está hecho, su
	relevancia es la misma que en el resto del programa y conoce todas las
	facetas. La búsqueda propia (``filtrar``) queda para un catálogo que no la
	tenga, y sus textos normalizados se preparan solo la primera vez que hacen falta.
	"""

	def __init__(self, catalogo: Any) -> None:
		self.catalogo = catalogo
		self.definiciones: list[Any] = list(catalogo.objetos())
		self._textos_preparados: dict[str, tuple[str, str, str]] | None = None

	@property
	def _textos(self) -> dict[str, tuple[str, str, str]]:
		"""Nombre, etiquetas y resto de cada ficha sin tildes ni mayúsculas (se calculan una vez)."""
		if self._textos_preparados is None:
			self._textos_preparados = self._preparar_textos()
		return self._textos_preparados

	def _preparar_textos(self) -> dict[str, tuple[str, str, str]]:
		catalogo = self.catalogo
		textos: dict[str, tuple[str, str, str]] = {}
		for definicion in self.definiciones:
			nombre = sin_acentos(definicion.nombre)
			etiquetas = sin_acentos(" ".join([definicion.id, *definicion.etiquetas]))
			resto = sin_acentos(
				" ".join(
					[
						definicion.categoria,
						catalogo.nombre_categoria(definicion.categoria) if definicion.categoria else "",
						subcategoria_de(definicion),
						definicion.descripcion,
						*(valor for faceta in FACETAS for valor in valores_de(definicion, faceta)),
					]
				)
			)
			textos[definicion.tipo] = (nombre, etiquetas, resto)
		return textos

	def filtrar_con_dominio(self, filtros: Filtros, favoritos: Sequence[str] = (), recientes: Sequence[str] = ()) -> list[Any] | None:
		"""Las fichas que cumplen los filtros según ``catalogo.buscar_avanzado``; None si el catálogo no sabe buscar así.

		Al dominio se le pasan el texto, el complemento del nodo, la categoría,
		el ámbito, las facetas y las casillas; lo que solo sabe el diálogo
		(favoritos, recientes, relacionados y la hoja «sin clasificar») se
		filtra después sobre lo que devuelve, que ya viene ordenado por relevancia.
		"""
		buscar = getattr(self.catalogo, "buscar_avanzado", None)
		if not callable(buscar):
			return None
		nodo = filtros.nodo
		argumentos: dict[str, Any] = {}
		if nodo[0] in ("comp", "cat", "sub"):
			argumentos["complemento"] = nodo[1]
		if nodo[0] in ("cat", "sub") and nodo[2]:
			argumentos["categoria"] = nodo[2]
		if nodo[0] == "sub" and nodo[3]:
			argumentos["subcategoria"] = nodo[3]
		if filtros.ambito is not None:
			argumentos["ambito"] = filtros.ambito
		argumentos.update(filtros.facetas)
		if filtros.contenedor:
			argumentos["contenedor"] = True
		if filtros.sonido_propio:
			argumentos["con_sonido"] = True
		try:
			encontrados = list(buscar(filtros.texto, **argumentos))
		except Exception:  # noqa: BLE001 - si el dominio falla con estos filtros, el diálogo busca por su cuenta
			log.warning("catalogo.buscar_avanzado falló; se usa la búsqueda propia del diálogo.", exc_info=True)
			return None
		conjunto: set[str] | None = None
		if nodo == NODO_FAVORITOS:
			conjunto = set(favoritos)
		elif nodo == NODO_RECIENTES:
			conjunto = set(recientes)
		elegidos = []
		for definicion in encontrados:
			if conjunto is not None and definicion.tipo not in conjunto:
				continue
			if filtros.tipos is not None and definicion.tipo not in filtros.tipos:
				continue
			# Una categoría o subcategoría de clave vacía («sin clasificar») el dominio no la filtra: se hace aquí.
			if nodo[0] in ("cat", "sub") and (definicion.categoria or "") != nodo[2]:
				continue
			if nodo[0] == "sub" and subcategoria_de(definicion) != nodo[3]:
				continue
			if filtros.categoria is not None and definicion.categoria != filtros.categoria:
				continue
			elegidos.append(definicion)
		if nodo == NODO_RECIENTES and not filtros.texto.split():
			orden = {tipo: posicion for posicion, tipo in enumerate(recientes)}
			elegidos.sort(key=lambda definicion: orden.get(definicion.tipo, len(orden)))
		return elegidos

	def buscar(self, filtros: Filtros, favoritos: Sequence[str] = (), recientes: Sequence[str] = ()) -> list[Any]:
		"""Lo que enseña el diálogo: con el buscador del dominio si lo hay; si no, con el propio."""
		encontrados = self.filtrar_con_dominio(filtros, favoritos, recientes)
		if encontrados is None:
			encontrados = self.filtrar(filtros, favoritos, recientes)
		return encontrados

	def relevancia(self, definicion: Any, palabras: Sequence[str]) -> int | None:
		"""Puntos de una ficha para una búsqueda; None si alguna palabra no aparece en ningún sitio.

		Pesa más coincidir en el nombre (y más aún si empieza por la palabra)
		que en las etiquetas, y estas más que en la descripción o la categoría.
		"""
		nombre, etiquetas, resto = self._textos[definicion.tipo]
		puntos = 0
		for palabra in palabras:
			if nombre.startswith(palabra):
				puntos += 100
			elif any(trozo.startswith(palabra) for trozo in nombre.split()):
				puntos += 80
			elif palabra in nombre:
				puntos += 60
			elif palabra in etiquetas:
				puntos += 30
			elif palabra in resto:
				puntos += 10
			else:
				return None
		return puntos

	def filtrar(self, filtros: Filtros, favoritos: Sequence[str] = (), recientes: Sequence[str] = ()) -> list[Any]:
		"""Las fichas que cumplen todos los filtros, por relevancia, frecuencia y nombre."""
		palabras = sin_acentos(filtros.texto).split()
		nodo = filtros.nodo
		conjunto: set[str] | None = None
		if nodo == NODO_FAVORITOS:
			conjunto = set(favoritos)
		elif nodo == NODO_RECIENTES:
			conjunto = set(recientes)
		elegidos: list[tuple[int, Any]] = []
		for definicion in self.definiciones:
			if conjunto is not None and definicion.tipo not in conjunto:
				continue
			if filtros.tipos is not None and definicion.tipo not in filtros.tipos:
				continue
			if nodo[0] in ("comp", "cat", "sub") and definicion.complemento != nodo[1]:
				continue
			if nodo[0] in ("cat", "sub") and (definicion.categoria or "") != nodo[2]:
				continue
			if nodo[0] == "sub" and subcategoria_de(definicion) != nodo[3]:
				continue
			if filtros.categoria is not None and definicion.categoria != filtros.categoria:
				continue
			if filtros.ambito is not None and filtros.ambito not in definicion.ambito:
				continue
			if filtros.contenedor and not definicion.contenedor:
				continue
			if filtros.sonido_propio and not tiene_sonido_propio(definicion):
				continue
			if any(valor not in valores_de(definicion, faceta) for faceta, valor in filtros.facetas.items()):
				continue
			puntos = self.relevancia(definicion, palabras) if palabras else 0
			if puntos is None:
				continue
			elegidos.append((puntos, definicion))
		if nodo == NODO_RECIENTES and not palabras:
			orden = {tipo: posicion for posicion, tipo in enumerate(recientes)}
			elegidos.sort(key=lambda par: orden.get(par[1].tipo, len(orden)))
		else:
			elegidos.sort(key=lambda par: (-par[0], -frecuencia_de(par[1]), sin_acentos(par[1].nombre)))
		return [definicion for _puntos, definicion in elegidos]


# ── Favoritos y usados recientemente ─────────────────────────────────────────


def ruta_uso() -> Path:
	"""``data/config/catalogo_uso.json``: favoritos y objetos usados hace poco. Es del profesional."""
	return paths.ruta_configuracion() / FICHERO_USO


def leer_uso() -> dict[str, list[str]]:
	"""Favoritos y recientes guardados; listas vacías si el fichero falta o está dañado."""
	try:
		datos = json.loads(ruta_uso().read_text(encoding="utf-8"))
	except FileNotFoundError:
		datos = {}
	except OSError, ValueError:
		log.warning("No se pudo leer %s; se empieza sin favoritos ni recientes.", ruta_uso(), exc_info=True)
		datos = {}
	if not isinstance(datos, dict):
		datos = {}
	return {
		clave: [str(tipo) for tipo in datos.get(clave, []) if isinstance(tipo, str)] if isinstance(datos.get(clave), list) else []
		for clave in ("favoritos", "recientes")
	}


def guardar_uso(uso: dict[str, list[str]]) -> bool:
	"""Escribe favoritos y recientes de forma atómica. False (sin lanzar) si el disco no deja."""
	ruta = ruta_uso()
	try:
		ruta.parent.mkdir(parents=True, exist_ok=True)
		provisional = ruta.with_name(ruta.name + ".tmp")
		provisional.write_text(json.dumps(uso, ensure_ascii=False, indent="\t"), encoding="utf-8")
		os.replace(provisional, ruta)
		return True
	except OSError:
		log.warning("No se pudo guardar %s", ruta, exc_info=True)
		return False


def alternar_favorito(tipo: str) -> bool:
	"""Marca o desmarca un objeto como favorito y lo guarda. Devuelve True si ha quedado marcado."""
	uso = leer_uso()
	if tipo in uso["favoritos"]:
		uso["favoritos"].remove(tipo)
		marcado = False
	else:
		uso["favoritos"].append(tipo)
		marcado = True
	guardar_uso(uso)
	return marcado


def apuntar_reciente(tipo: str) -> None:
	"""Pone un objeto el primero de los usados recientemente (se llama al colocarlo)."""
	uso = leer_uso()
	uso["recientes"] = [tipo, *(otro for otro in uso["recientes"] if otro != tipo)][:MAX_RECIENTES]
	guardar_uso(uso)


def tipos_relacionados(catalogo: Any, definicion: Any) -> frozenset[str]:
	"""Tipos de los objetos que suelen ir con uno: lo que diga ``catalogo.relacionados`` o, si no existe, su ficha."""
	funcion = getattr(catalogo, "relacionados", None)
	if callable(funcion):
		try:
			return frozenset(str(getattr(otro, "tipo", otro)) for otro in funcion(definicion.tipo))
		except Exception:  # noqa: BLE001 - un fallo del catálogo al buscar relacionados no debe cerrar el diálogo
			log.warning("No se pudieron buscar los relacionados de %s", definicion.tipo, exc_info=True)
			return frozenset()
	declarados = getattr(definicion, "relacionados", None) or []
	tipos = (str(otro) if "/" in str(otro) else f"{definicion.complemento}/{otro}" for otro in declarados)
	return frozenset(tipo for tipo in tipos if catalogo.objeto(tipo) is not None)


def hay_relacionados(catalogo: Any, definiciones: Sequence[Any]) -> bool:
	"""True si tiene sentido ofrecer «Objetos relacionados»: el catálogo sabe buscarlos o alguna ficha los declara."""
	return callable(getattr(catalogo, "relacionados", None)) or any(getattr(d, "relacionados", None) for d in definiciones)


def texto_recuento(cantidad: int) -> str:
	"""«34 objetos», «1 objeto», «Ningún objeto»."""
	if cantidad == 0:
		return _("Ningún objeto")
	return _n("{n} objeto", "{n} objetos", cantidad).format(n=cantidad)


# ── Paso 1: elegir el objeto ─────────────────────────────────────────────────


class DialogoCatalogo(wx.Dialog):
	"""Busca un objeto entre los de los complementos activos (pueden ser más de mil) y elige su variante.

	Pensado para un catálogo grande: un árbol de clasificación para acotar,
	búsqueda por texto ordenada por relevancia, filtros que se combinan, una
	lista virtual (solo se pintan las filas visibles) y la miniatura de la
	fila enfocada cargada con un pequeño retardo, nunca todas al abrir.
	"""

	def __init__(self, padre: wx.Window | None, catalogo: Catalogo, ambito: str | None = None, contexto: Any = None) -> None:
		"""Crea el diálogo.

		:param ambito: ``"interior"`` o ``"exterior"`` para empezar filtrando por
			el de la planta en la que se va a colocar; ``None`` enseña todo.
		:param contexto: si se pasa, el recuento tras cada filtrado se anuncia con ``contexto.anunciar``.
		"""
		titulo = _("Insertar objeto del catálogo")
		super().__init__(padre, title=titulo, style=wx.DEFAULT_DIALOG_STYLE | wx.RESIZE_BORDER, name=titulo)
		self._catalogo = catalogo
		self._contexto = contexto
		self._indice = Indice(catalogo)
		self._definiciones: list[DefObjeto] = []
		self._variantes: list[str | None] = [None]
		self._filtros = Filtros(ambito=ambito if ambito in AMBITOS else None)
		self._uso = leer_uso()
		self._nodos: dict[tuple[str, ...], wx.TreeItemId] = {}
		self._nombres_valor: dict[tuple[str, str], str] = {}
		self._silencio_arbol = False
		self._tipo_mostrado: str | None = None
		self._tipo_miniatura: str | None = None
		# Se guarda el id: en wxPython 4.3 ``evento.GetEventObject()`` de EVT_WINDOW_DESTROY no es ``self``.
		self._id_propio = self.GetId()
		self._temporizador = wx.Timer(self)
		self._temporizador_miniatura = wx.Timer(self)
		self.resultado: tuple[str, str | None] | None = None
		self.ultimo_error = ""
		self.ultimo_anuncio = ""
		#: Cuántas miniaturas se han cargado (las pruebas comprueban que abrir no carga ninguna).
		self.miniaturas_cargadas = 0

		principal = wx.BoxSizer(wx.HORIZONTAL)

		# Columna izquierda: la clasificación. Es el primer control del diálogo.
		izquierda = wx.BoxSizer(wx.VERTICAL)
		etiqueta_arbol = wx.StaticText(self, label=_("Clasi&ficación:"))
		self.arbol = wx.TreeCtrl(
			self, style=wx.TR_HAS_BUTTONS | wx.TR_LINES_AT_ROOT | wx.TR_HIDE_ROOT | wx.TR_SINGLE, name=_("Clasificación")
		)
		self.arbol.SetMinSize(self.FromDIP(wx.Size(240, 320)))
		self.arbol.SetHelpText(
			_(
				"Clasificación del catálogo: todos, favoritos, usados recientemente y cada complemento con sus categorías y subcategorías. "
				"El número entre paréntesis dice cuántos objetos hay. Al elegir un nodo la lista enseña solo sus objetos."
			)
		)
		izquierda.Add(etiqueta_arbol, 0, wx.LEFT | wx.RIGHT | wx.TOP, 8)
		izquierda.Add(self.arbol, 1, wx.EXPAND | wx.ALL, 8)
		principal.Add(izquierda, 0, wx.EXPAND)

		derecha = wx.BoxSizer(wx.VERTICAL)
		_e, self.campo_buscar = crear_campo(
			self,
			_("&Buscar:"),
			wx.TextCtrl,
			style=wx.TE_PROCESS_ENTER,
			ayuda=_(
				"Escriba parte del nombre, de las etiquetas o de la descripción; la lista se filtra sola y pone primero lo que coincide en el nombre. "
				"Intro la filtra al momento."
			),
			sizer=derecha,
		)

		# Filtros en listas. Las de clasificación solo se crean si algún objeto declara ese dato.
		filtros = wx.WrapSizer(wx.HORIZONTAL)
		self._claves_ambito: list[str | None] = [None, *AMBITOS]
		columna = wx.BoxSizer(wx.VERTICAL)
		_e, self.eleccion_ambito = crear_campo(
			self,
			_("Ámbi&to:"),
			wx.Choice,
			choices=[_("Todos")] + [_(nombre) for nombre in AMBITOS.values()],
			ayuda=_("Enseña solo los objetos de interior o solo los de exterior."),
			sizer=columna,
		)
		self.eleccion_ambito.SetSelection(self._claves_ambito.index(self._filtros.ambito))
		filtros.Add(columna, 0)
		self.elecciones_faceta: dict[str, wx.Choice] = {}
		self._claves_faceta: dict[str, list[str | None]] = {}
		for faceta, valores in self._facetas().items():
			if not valores:
				continue
			columna = wx.BoxSizer(wx.VERTICAL)
			_e, eleccion = crear_campo(
				self,
				_(FACETAS[faceta][0]),
				wx.Choice,
				choices=[_("Todos")]
				+ [_("{nombre} ({n})").format(nombre=self.nombre_de_valor(faceta, valor), n=cuenta) for valor, cuenta in valores],
				ayuda=_("Enseña solo los objetos con ese valor. Se combina con los demás filtros."),
				sizer=columna,
			)
			eleccion.SetSelection(0)
			self.elecciones_faceta[faceta] = eleccion
			self._claves_faceta[faceta] = [None, *(valor for valor, _cuenta in valores)]
			filtros.Add(columna, 0)
		derecha.Add(filtros, 0, wx.EXPAND)
		casillas = wx.BoxSizer(wx.HORIZONTAL)
		self.casilla_premio = wx.CheckBox(self, label=_("Puede esconder un &premio"))
		self.casilla_premio.SetHelpText(_("Enseña solo los objetos que pueden esconder un premio dentro o debajo."))
		self.casilla_sonido = wx.CheckBox(self, label=_("Tiene sonido prop&io"))
		self.casilla_sonido.SetHelpText(_("Enseña solo los objetos que suenan ellos solos, como un frigorífico o un semáforo."))
		casillas.Add(self.casilla_premio, 0, wx.ALL, 5)
		casillas.Add(self.casilla_sonido, 0, wx.ALL, 5)
		derecha.Add(casillas, 0)

		etiqueta_lista = wx.StaticText(self, label=_("&Objetos:"))
		self.lista = ListaAccesible(
			self,
			_("Objetos"),
			[
				(_("Nombre"), self.FromDIP(200)),
				(_("Categoría"), self.FromDIP(130)),
				(_("Medidas"), self.FromDIP(150)),
				(_("Complemento"), self.FromDIP(140)),
			],
			virtual=True,
		)
		self.lista.SetMinSize(self.FromDIP(wx.Size(620, 190)))
		self.lista.SetHelpText(
			_(
				"Objetos que cumplen los filtros, los más parecidos a lo buscado primero. Izquierda y derecha leen las columnas; "
				"Intro elige el objeto y pasa a colocarlo; Control+D lo marca o lo desmarca como favorito."
			)
		)
		derecha.Add(etiqueta_lista, 0, wx.LEFT | wx.RIGHT | wx.TOP, 5)
		derecha.Add(self.lista, 1, wx.EXPAND | wx.ALL, 5)
		# El recuento también se ve (y se puede leer con el cursor de revisión): la voz es solo un complemento.
		self.texto_recuento = wx.StaticText(self, label="", name=_("Recuento"))
		derecha.Add(self.texto_recuento, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 5)

		acciones = wx.BoxSizer(wx.HORIZONTAL)
		self.boton_favorito = wx.Button(self, label=_("Marcar como fa&vorito"))
		self.boton_favorito.SetHelpText(
			_("Marca o desmarca el objeto elegido como favorito (también con Control+D). Los favoritos tienen su nodo en la clasificación.")
		)
		acciones.Add(self.boton_favorito, 0, wx.ALL, 4)
		self.boton_relacionados: wx.Button | None = None
		if hay_relacionados(catalogo, self._indice.definiciones):
			self.boton_relacionados = wx.Button(self, label=_("Objetos &relacionados"))
			self.boton_relacionados.SetHelpText(
				_("Enseña en la lista los objetos que suelen ir con el elegido. Para volver, elija otro nodo de la clasificación.")
			)
			acciones.Add(self.boton_relacionados, 0, wx.ALL, 4)
		derecha.Add(acciones, 0)

		detalle = wx.BoxSizer(wx.HORIZONTAL)
		self.miniatura = wx.StaticBitmap(self, size=self.FromDIP(wx.Size(LADO_MINIATURA, LADO_MINIATURA)), name=_("Miniatura de la huella"))
		detalle.Add(self.miniatura, 0, wx.ALL, 5)
		columna = wx.BoxSizer(wx.VERTICAL)
		_e, self.campo_descripcion = crear_campo(
			self,
			_("&Descripción:"),
			wx.TextCtrl,
			style=wx.TE_MULTILINE | wx.TE_READONLY,
			size=self.FromDIP(wx.Size(420, 110)),
			ayuda=_(
				"Descripción del objeto elegido: medidas, forma, variantes, clasificación y cómo se comporta. Dice en texto lo mismo que la miniatura."
			),
			sizer=columna,
		)
		_e, self.eleccion_variante = crear_campo(
			self,
			_("Varia&nte:"),
			wx.Choice,
			choices=[_("Medidas normales")],
			ayuda=_("Tamaño con nombre del objeto elegido."),
			sizer=columna,
		)
		self.eleccion_variante.SetSelection(0)
		detalle.Add(columna, 1, wx.EXPAND)
		derecha.Add(detalle, 0, wx.EXPAND)
		derecha.Add(crear_botonera(self, wx.OK | wx.CANCEL), 0, wx.ALIGN_RIGHT | wx.ALL, 10)
		principal.Add(derecha, 1, wx.EXPAND | wx.ALL, 3)
		self.SetSizerAndFit(principal)

		self.campo_buscar.Bind(wx.EVT_TEXT, self._al_escribir)
		self.campo_buscar.Bind(wx.EVT_TEXT_ENTER, lambda _e: self.filtrar())
		self.eleccion_ambito.Bind(wx.EVT_CHOICE, lambda _e: self.filtrar())
		for eleccion in self.elecciones_faceta.values():
			eleccion.Bind(wx.EVT_CHOICE, lambda _e: self.filtrar())
		self.casilla_premio.Bind(wx.EVT_CHECKBOX, lambda _e: self.filtrar())
		self.casilla_sonido.Bind(wx.EVT_CHECKBOX, lambda _e: self.filtrar())
		self.arbol.Bind(wx.EVT_TREE_SEL_CHANGED, self._al_elegir_nodo)
		self.lista.Bind(wx.EVT_LIST_ITEM_FOCUSED, self._al_cambiar_fila)
		self.lista.Bind(wx.EVT_LIST_ITEM_SELECTED, self._al_cambiar_fila)
		self.lista.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self._al_aceptar)
		self.boton_favorito.Bind(wx.EVT_BUTTON, lambda _e: self.alternar_favorito())
		if self.boton_relacionados is not None:
			self.boton_relacionados.Bind(wx.EVT_BUTTON, lambda _e: self.mostrar_relacionados())
		self.Bind(wx.EVT_TIMER, lambda _e: self.filtrar(), self._temporizador)
		self.Bind(wx.EVT_TIMER, lambda _e: self.cargar_miniatura_ahora(), self._temporizador_miniatura)
		self.Bind(wx.EVT_BUTTON, self._al_aceptar, id=wx.ID_OK)
		self.Bind(wx.EVT_WINDOW_DESTROY, self._al_destruir)
		preparar_dialogo(self, foco_inicial=self.campo_buscar)
		self.Bind(wx.EVT_CHAR_HOOK, self._al_pulsar)
		self._poblar_arbol()
		self.filtrar(anunciar=False)
		self.CentreOnParent()

	def _parar_temporizadores(self) -> None:
		"""Para los dos temporizadores: uno vivo tras liberar su dueño cierra el proceso en el siguiente Dispatch."""
		for temporizador in (self._temporizador, self._temporizador_miniatura):
			if temporizador.IsRunning():
				temporizador.Stop()

	def Destroy(self) -> bool:  # noqa: N802 - sobrescribe el método de wx
		"""Para los temporizadores antes de destruir, sin depender de que llegue EVT_WINDOW_DESTROY."""
		self._parar_temporizadores()
		return super().Destroy()

	def _al_destruir(self, evento: wx.WindowDestroyEvent) -> None:
		# El evento de un hijo también sube hasta aquí: se compara el id, porque GetEventObject() no es self (wxPython 4.3).
		if evento.GetId() == self._id_propio:
			self._parar_temporizadores()
		evento.Skip()

	def _al_pulsar(self, evento: wx.KeyEvent) -> None:
		"""Control+D marca o desmarca el favorito desde cualquier control; lo demás sigue su camino."""
		# atajo: Ctrl+D
		if evento.GetModifiers() == wx.MOD_CONTROL and evento.GetKeyCode() == ord("D"):
			self.alternar_favorito()
			return
		evento.Skip()

	# ── Clasificación ────────────────────────────────────────────────────────

	def _facetas(self) -> dict[str, list[tuple[str, int]]]:
		"""Valores de cada faceta con su recuento: los de ``catalogo.facetas()`` si existe y se entiende; si no, los calculados."""
		calculadas = facetas_de(self._indice.definiciones)
		funcion = getattr(self._catalogo, "facetas", None)
		if not callable(funcion):
			return calculadas
		try:
			brutas = funcion()
			for faceta, (_etiqueta, atributos, _tablas) in FACETAS.items():
				valores = next((brutas[nombre] for nombre in (faceta, *atributos) if nombre in brutas), None)
				if valores is None:
					continue
				pares: list[tuple[str, int]] = []
				for valor in valores.items() if isinstance(valores, dict) else valores:
					if isinstance(valor, (tuple, list)):
						pares.append((str(valor[0]), int(valor[1])))
					else:
						# ``ValorFaceta(clave, nombre, total)`` del dominio: su nombre ya viene en el idioma cargado.
						pares.append((str(valor.clave), int(valor.total)))
						self._nombres_valor[(faceta, str(valor.clave))] = str(valor.nombre)
				calculadas[faceta] = sorted(pares, key=lambda par: sin_acentos(self.nombre_de_valor(faceta, par[0])))
		except Exception:  # noqa: BLE001 - el dominio aún puede cambiar la forma de las facetas: valen las calculadas
			log.info("catalogo.facetas() no tiene la forma esperada; se calculan de las fichas.", exc_info=True)
			return facetas_de(self._indice.definiciones)
		return calculadas

	def nombre_de_valor(self, faceta: str, valor: str) -> str:
		"""Nombre visible de un valor de faceta: el que dio el catálogo o, si no, el de las tablas del programa."""
		return self._nombres_valor.get((faceta, valor)) or nombre_valor(faceta, valor)

	def nodos_especiales(self) -> list[NodoArbol]:
		"""«Todos», «Favoritos» y «Usados recientemente», con sus recuentos."""
		tipos = {definicion.tipo for definicion in self._indice.definiciones}
		return [
			NodoArbol(NODO_TODOS, _("Todos"), len(tipos)),
			NodoArbol(NODO_FAVORITOS, _("Favoritos"), sum(1 for tipo in self._uso["favoritos"] if tipo in tipos)),
			NodoArbol(NODO_RECIENTES, _("Usados recientemente"), sum(1 for tipo in self._uso["recientes"] if tipo in tipos)),
		]

	def nodos_de_clasificacion(self) -> list[NodoArbol]:
		"""Los nodos del árbol: los especiales y después los complementos."""
		return self.nodos_especiales() + (arbol_del_dominio(self._catalogo) or construir_arbol(self._catalogo))

	def _poblar_arbol(self) -> None:
		"""Rellena el árbol. Los complementos quedan plegados: con veinte, desplegarlos todos sería un muro."""
		self._silencio_arbol = True
		try:
			self.arbol.DeleteAllItems()
			self._nodos = {}
			raiz = self.arbol.AddRoot(_("Catálogo"))

			def anadir(padre: wx.TreeItemId, nodo: NodoArbol) -> None:
				elemento = self.arbol.AppendItem(padre, nodo.texto())
				self.arbol.SetItemData(elemento, nodo.clave)
				self._nodos[nodo.clave] = elemento
				for hijo in nodo.hijos:
					anadir(elemento, hijo)

			for nodo in self.nodos_de_clasificacion():
				anadir(raiz, nodo)
			destino = self._nodos.get(self._filtros.nodo) or self._nodos[NODO_TODOS]
			self.arbol.SelectItem(destino)
			self.arbol.EnsureVisible(destino)
		finally:
			self._silencio_arbol = False

	def _actualizar_nodos_de_uso(self) -> None:
		"""Pone al día el recuento de «Favoritos» y «Usados recientemente» sin reconstruir el árbol (no mueve al usuario)."""
		# Solo los especiales: recalcular el árbol de miles de objetos para dos recuentos sería tirar el tiempo.
		for nodo in self.nodos_especiales()[1:3]:
			elemento = self._nodos.get(nodo.clave)
			if elemento is not None and self.arbol.GetItemText(elemento) != nodo.texto():
				self.arbol.SetItemText(elemento, nodo.texto())

	def _al_elegir_nodo(self, evento: wx.TreeEvent) -> None:
		evento.Skip()
		# Al destruirse, el árbol aún avisa de cambios de selección: entonces ya no hay nada que filtrar.
		if self._silencio_arbol or not self or not self.arbol or self.IsBeingDeleted() or not evento.GetItem().IsOk():
			return
		clave = self.arbol.GetItemData(evento.GetItem())
		if clave and tuple(clave) != self._filtros.nodo:
			self._filtros.nodo = tuple(clave)
			self._filtros.tipos = None
			self._filtros.categoria = None
			self.filtrar()

	def elegir_nodo(self, *clave: str) -> bool:
		"""Elige un nodo de la clasificación por su clave (``"favoritos"``; ``"comp", id``; ``"cat", id, categoría``…). False si no existe."""
		elemento = self._nodos.get(tuple(clave))
		if elemento is None:
			return False
		self._silencio_arbol = True
		try:
			self.arbol.SelectItem(elemento)
			self.arbol.EnsureVisible(elemento)
		finally:
			self._silencio_arbol = False
		self._filtros.nodo = tuple(clave)
		self._filtros.tipos = None
		self._filtros.categoria = None
		self.filtrar()
		return True

	# ── Filtros ──────────────────────────────────────────────────────────────

	def _al_escribir(self, evento: wx.CommandEvent) -> None:
		"""Filtra un momento después de dejar de escribir: filtrar a cada tecla haría hablar al lector sin parar."""
		self._temporizador.StartOnce(RETARDO_BUSQUEDA_MS)
		evento.Skip()

	def _decir(self, texto: str) -> None:
		"""Un anuncio breve: por el contexto del Estudio si lo hay; si no, por la voz del proyecto."""
		self.ultimo_anuncio = texto
		if self._contexto is not None:
			self._contexto.anunciar(texto)
			return
		from app.core import voz

		voz.hablar(texto, False)

	def filtrar(
		self,
		texto: str | None = None,
		complemento: str | None = None,
		categoria: str | None = None,
		ambito: str | None = None,
		anunciar: bool = True,
		**facetas: str | bool | None,
	) -> int:
		"""Aplica los filtros y devuelve cuántos objetos quedan.

		Sin argumentos lee los controles. Los que se pasen se ponen antes en
		sus controles: ``TODOS`` quita ese filtro; ``complemento`` elige su nodo
		en la clasificación; ``lugar``, ``estancia``, ``funcion``,
		``obstaculo`` y ``riesgo`` eligen un valor; ``contenedor`` y ``sonido_propio`` marcan
		las casillas. El recuento se anuncia UNA vez por filtrado y queda escrito
		bajo la lista.
		"""
		if texto is not None:
			self.campo_buscar.ChangeValue(texto)
		if complemento is not None:
			clave = NODO_TODOS if complemento == TODOS else ("comp", complemento)
			if clave in self._nodos:
				self._silencio_arbol = True
				try:
					self.arbol.SelectItem(self._nodos[clave])
				finally:
					self._silencio_arbol = False
				self._filtros.nodo = clave
				self._filtros.tipos = None
		if categoria is not None:
			self._filtros.categoria = None if categoria == TODOS else categoria
		if ambito is not None:
			clave_ambito = None if ambito == TODOS else ambito
			if clave_ambito in self._claves_ambito:
				self.eleccion_ambito.SetSelection(self._claves_ambito.index(clave_ambito))
		for nombre, valor in facetas.items():
			if nombre == "contenedor":
				self.casilla_premio.SetValue(bool(valor))
			elif nombre == "sonido_propio":
				self.casilla_sonido.SetValue(bool(valor))
			elif nombre in self.elecciones_faceta:
				clave_faceta = None if valor in (None, TODOS) else valor
				if clave_faceta in self._claves_faceta[nombre]:
					self.elecciones_faceta[nombre].SetSelection(self._claves_faceta[nombre].index(clave_faceta))
		self._temporizador.Stop()

		elegido_antes = self.definicion_actual()
		self._filtros.texto = self.campo_buscar.GetValue()
		self._filtros.ambito = self._claves_ambito[max(self.eleccion_ambito.GetSelection(), 0)]
		self._filtros.facetas = {}
		for faceta, eleccion in self.elecciones_faceta.items():
			valor_faceta = self._claves_faceta[faceta][max(eleccion.GetSelection(), 0)]
			if valor_faceta is not None:
				self._filtros.facetas[faceta] = valor_faceta
		self._filtros.contenedor = self.casilla_premio.GetValue()
		self._filtros.sonido_propio = self.casilla_sonido.GetValue()
		encontrados = self._indice.buscar(self._filtros, self._uso["favoritos"], self._uso["recientes"])
		self._definiciones = encontrados
		self.lista.reemplazar_filas([fila_de(self._catalogo, d) for d in encontrados], conservar_foco=False)
		if encontrados:
			fila = 0
			if elegido_antes is not None and not self._filtros.texto.strip():
				# Sin búsqueda se conserva el objeto en el que se estaba; con búsqueda manda el más parecido.
				fila = next((i for i, d in enumerate(encontrados) if d.tipo == elegido_antes.tipo), 0)
			self.lista.enfocar_fila(fila, anunciar=False)
		recuento = texto_recuento(len(encontrados))
		self.texto_recuento.SetLabel(recuento)
		self._mostrar_detalle()
		if anunciar:
			self._decir(recuento)
		return len(encontrados)

	# ── Objeto elegido ───────────────────────────────────────────────────────

	def definicion_actual(self) -> DefObjeto | None:
		"""La ficha de la fila enfocada, o None si la lista está vacía."""
		fila = self.lista.fila_actual() if self._definiciones else -1
		return self._definiciones[fila] if 0 <= fila < len(self._definiciones) else None

	def _al_cambiar_fila(self, evento: wx.ListEvent) -> None:
		evento.Skip()
		self._mostrar_detalle()

	def _mostrar_detalle(self) -> None:
		"""Pone la descripción y las variantes del objeto enfocado, y deja su miniatura para dentro de un momento."""
		definicion = self.definicion_actual()
		tipo = definicion.tipo if definicion is not None else ""
		self._actualizar_boton_favorito(definicion)
		if tipo == self._tipo_mostrado:
			return
		self._tipo_mostrado = tipo
		self.eleccion_variante.Clear()
		self._variantes = [None]
		self.eleccion_variante.Append(_("Medidas normales"))
		self.eleccion_variante.SetSelection(0)
		self._temporizador_miniatura.Stop()
		if self._tipo_miniatura != tipo:
			self._tipo_miniatura = None
			self.miniatura.SetBitmap(wx.BitmapBundle())
		if definicion is None:
			self.campo_descripcion.ChangeValue(_("No hay ningún objeto que cumpla los filtros."))
			return
		for variante in definicion.variantes:
			self._variantes.append(variante.id)
			self.eleccion_variante.Append(
				_("{nombre} ({ancho} × {fondo} m)").format(
					nombre=variante.nombre, ancho=texto_numero(variante.ancho), fondo=texto_numero(variante.fondo)
				)
			)
		self.campo_descripcion.ChangeValue(texto_descripcion(self._catalogo, definicion))
		# La miniatura, con retardo: al recorrer la lista deprisa no se carga (ni se genera) la de cada fila.
		self._temporizador_miniatura.StartOnce(RETARDO_MINIATURA_MS)

	def cargar_miniatura_ahora(self) -> bool:
		"""Carga la miniatura del objeto enfocado (la llama el temporizador). True si quedó puesta."""
		self._temporizador_miniatura.Stop()
		definicion = self.definicion_actual()
		if definicion is None:
			return False
		if self._tipo_miniatura == definicion.tipo:
			return True
		mapa = self._bitmap_de(definicion)
		self.miniatura.SetBitmap(mapa)
		self._tipo_miniatura = definicion.tipo
		self.miniaturas_cargadas += 1
		return mapa.IsOk()

	def _bitmap_de(self, definicion: DefObjeto) -> wx.BitmapBundle:
		ruta = ruta_miniatura(self._catalogo, definicion)
		if ruta is None:
			return wx.BitmapBundle()
		registro_silenciado = wx.LogNull()  # un PNG dañado no debe abrir un cuadro de error de wx
		try:
			imagen = wx.Image(str(ruta), wx.BITMAP_TYPE_ANY)
		finally:
			del registro_silenciado
		if not imagen.IsOk():
			return wx.BitmapBundle()
		lado = self.FromDIP(LADO_MINIATURA)
		escala = min(lado / max(imagen.GetWidth(), 1), lado / max(imagen.GetHeight(), 1))
		imagen = imagen.Scale(max(1, int(imagen.GetWidth() * escala)), max(1, int(imagen.GetHeight() * escala)), wx.IMAGE_QUALITY_HIGH)
		return wx.BitmapBundle(wx.Bitmap(imagen))

	def elegir(self, tipo: str, variante: str | None = None) -> bool:
		"""Enfoca el objeto ``tipo`` (quitando los filtros si lo esconden) y elige su variante. False si no existe."""
		if tipo not in [d.tipo for d in self._definiciones]:
			self._filtros.nodo = NODO_TODOS
			self._filtros.tipos = None
			self._filtros.categoria = None
			libres = {faceta: TODOS for faceta in self.elecciones_faceta}
			self.filtrar("", TODOS, TODOS, TODOS, anunciar=False, contenedor=False, sonido_propio=False, **libres)
		tipos = [d.tipo for d in self._definiciones]
		if tipo not in tipos:
			return False
		self.lista.enfocar_fila(tipos.index(tipo), anunciar=False)
		self._mostrar_detalle()
		if variante in self._variantes:
			self.eleccion_variante.SetSelection(self._variantes.index(variante))
		return True

	def seleccion(self) -> tuple[str, str | None] | None:
		"""(tipo, variante) elegidos ahora; variante None son las medidas normales."""
		definicion = self.definicion_actual()
		if definicion is None:
			return None
		indice = self.eleccion_variante.GetSelection()
		return definicion.tipo, self._variantes[indice] if 0 <= indice < len(self._variantes) else None

	# ── Favoritos y relacionados ─────────────────────────────────────────────

	def _actualizar_boton_favorito(self, definicion: DefObjeto | None) -> None:
		"""El botón dice lo que hará: marcar o quitar. La letra de acceso es la misma en los dos casos."""
		es_favorito = definicion is not None and definicion.tipo in self._uso["favoritos"]
		etiqueta = _("Quitar de fa&voritos") if es_favorito else _("Marcar como fa&vorito")
		if self.boton_favorito.GetLabel() != etiqueta:
			self.boton_favorito.SetLabel(etiqueta)
		self.boton_favorito.Enable(definicion is not None)
		if self.boton_relacionados is not None:
			self.boton_relacionados.Enable(definicion is not None)

	def alternar_favorito(self) -> bool | None:
		"""Marca o desmarca como favorito el objeto enfocado y lo guarda. Devuelve cómo quedó (None si no hay objeto)."""
		definicion = self.definicion_actual()
		if definicion is None:
			return None
		marcado = alternar_favorito(definicion.tipo)
		self._uso = leer_uso()
		self._actualizar_nodos_de_uso()
		self._actualizar_boton_favorito(definicion)
		self._decir(
			(_("{nombre}, marcado como favorito.") if marcado else _("{nombre}, quitado de favoritos.")).format(nombre=definicion.nombre)
		)
		if self._filtros.nodo == NODO_FAVORITOS and not marcado:
			self.filtrar(anunciar=False)
		return marcado

	def mostrar_relacionados(self) -> int:
		"""Enseña en la lista los objetos relacionados con el enfocado (si el catálogo sabe decirlos). Devuelve cuántos."""
		definicion = self.definicion_actual()
		if definicion is None:
			return 0
		tipos = tipos_relacionados(self._catalogo, definicion)
		if not tipos:
			self._decir(_("«{nombre}» no tiene objetos relacionados.").format(nombre=definicion.nombre))
			return 0
		self._filtros.tipos = tipos
		self._filtros.nodo = NODO_TODOS
		self._filtros.categoria = None
		self._silencio_arbol = True
		try:
			self.arbol.SelectItem(self._nodos[NODO_TODOS])
		finally:
			self._silencio_arbol = False
		libres = {faceta: TODOS for faceta in self.elecciones_faceta}
		cantidad = self.filtrar("", ambito=TODOS, anunciar=False, contenedor=False, sonido_propio=False, **libres)
		self._decir(
			_("Relacionados con «{nombre}»: {recuento}.").format(nombre=definicion.nombre, recuento=texto_recuento(cantidad).lower())
		)
		self.lista.SetFocus()
		return cantidad

	# ── Aceptar ──────────────────────────────────────────────────────────────

	def aceptar(self) -> bool:
		"""Guarda la elección en ``resultado``. False si no hay ningún objeto elegido."""
		elegido = self.seleccion()
		if elegido is None:
			self.ultimo_error = _("Elija un objeto de la lista. Si está vacía, cambie la búsqueda o los filtros.")
			mostrar_error(self, self.ultimo_error, _("Insertar objeto"))
			self.campo_buscar.SetFocus()
			return False
		self.ultimo_error = ""
		self.resultado = elegido
		return True

	def _al_aceptar(self, _evento: wx.Event) -> None:
		if self.aceptar():
			self.EndModal(wx.ID_OK)


def elegir_objeto(contexto: Any, padre: wx.Window | None = None, ambito: str | None = None) -> tuple[str, str | None] | None:
	"""Abre el catálogo y devuelve ``(tipo, variante)`` del objeto elegido, sin colocar nada. None si se cancela."""
	padre = padre if padre is not None else getattr(contexto, "ventana", None)
	catalogo = contexto.catalogo
	if catalogo is None or catalogo.vacio:
		mostrar_mensaje(
			padre,
			_("No hay ningún objeto disponible. Instale o active algún complemento en Herramientas, Complementos instalados."),
			_("Insertar objeto"),
		)
		return None
	dialogo = DialogoCatalogo(padre, catalogo, ambito, contexto)
	foco_previo = wx.Window.FindFocus()
	try:
		if dialogo.ShowModal() != wx.ID_OK:
			return None
		if dialogo.resultado is None and not dialogo.aceptar():
			return None
		return dialogo.resultado
	finally:
		dialogo.Destroy()
		if foco_previo:
			foco_previo.SetFocus()


# ── Paso 2: dónde y cómo se coloca ───────────────────────────────────────────


def _plantas(entorno: Entorno) -> list[tuple[str, str]]:
	return [(planta.id, planta.nombre or planta.id) for planta in entorno.plantas]


def _espacios(entorno: Entorno, id_planta: str) -> list[tuple[str, str]]:
	planta = entorno.planta(id_planta)
	if planta is None:
		return []
	return [(espacio.id, espacio.nombre or espacio.id) for espacio in planta.espacios if not espacio.macizo]


def _referencias(entorno: Entorno, id_planta: str, catalogo: Catalogo | None) -> list[tuple[str, str]]:
	"""Elementos de la planta junto a los que se puede colocar: objetos, puertas, referencias y sonidos."""
	planta = entorno.planta(id_planta)
	if planta is None:
		return []
	elementos = [*planta.objetos, *planta.aberturas, *planta.referencias, *planta.fuentes]
	return [(elemento.id, elemento.nombre or elemento.id) for elemento in elementos]


def esquema_colocacion(contexto: Any) -> list[Campo]:
	"""Campos del formulario «dónde se coloca». Las listas dependen de la planta elegida."""
	entorno: Entorno = contexto.entorno
	catalogo = contexto.catalogo

	def es(modo: str):
		return lambda valores: valores.get("modo") == modo

	return [
		c("planta", N_("Planta"), "opcion", opciones=_plantas(entorno), recarga=True, ayuda=N_("Planta en la que se coloca el objeto.")),
		c(
			"modo",
			N_("Forma de colocarlo"),
			"opcion",
			opciones=[(k, _(v)) for k, v in MODOS.items()],
			recarga=True,
			defecto="pared",
			ayuda=N_("Cómo se dice dónde va: por una pared, una esquina, otro elemento o unas coordenadas."),
		),
		c(
			"espacio",
			N_("Espacio"),
			"opcion",
			opciones=lambda v: _espacios(entorno, v.get("planta", "")),
			si=lambda v: v.get("modo") in ("pared", "esquina"),
			ayuda=N_("Habitación o zona en la que se coloca."),
		),
		c(
			"lado",
			N_("Pared"),
			"opcion",
			opciones=[(k, _(v)) for k, v in LADOS.items()],
			defecto="norte",
			si=es("pared"),
			ayuda=N_("Pared contra la que queda la espalda del objeto."),
		),
		c(
			"alineacion",
			N_("Sitio a lo largo de la pared"),
			"opcion",
			opciones=[(k, _(v)) for k, v in ALINEACIONES.items()],
			defecto="centro",
			recarga=True,
			si=es("pared"),
		),
		c(
			"desplazamiento",
			N_("Distancia al extremo oeste o sur"),
			"metros",
			minimo=0.0,
			maximo=1000.0,
			defecto=0.0,
			si=lambda v: v.get("modo") == "pared" and v.get("alineacion") == "distancia",
			ayuda=N_("Metros desde el extremo oeste o sur de la pared hasta el borde más cercano del objeto."),
		),
		c(
			"separacion",
			N_("Separación de la pared"),
			"metros",
			minimo=0.0,
			maximo=100.0,
			defecto=0.0,
			si=es("pared"),
			ayuda=N_("Cero para dejarlo pegado a la pared."),
		),
		c("esquina", N_("Esquina"), "opcion", opciones=[(k, _(v)) for k, v in ESQUINAS.items()], defecto="noreste", si=es("esquina")),
		c(
			"referencia",
			N_("Elemento de referencia"),
			"opcion",
			opciones=lambda v: _referencias(entorno, v.get("planta", ""), catalogo),
			si=es("junto"),
			ayuda=N_("El objeto, la puerta, la referencia o el sonido junto al que se coloca."),
		),
		c(
			"lado_junto",
			N_("A qué lado del elemento"),
			"opcion",
			opciones=[(k, _(v)) for k, v in LADOS.items()],
			defecto="este",
			si=es("junto"),
		),
		c("separacion_junto", N_("Separación del elemento"), "metros", minimo=0.0, maximo=100.0, defecto=0.0, si=es("junto")),
		c(
			"x",
			N_("Metros hacia el este (X)"),
			"metros",
			minimo=-100000.0,
			maximo=100000.0,
			defecto=0.0,
			obligatorio=True,
			si=es("punto"),
			ayuda=N_("Coordenada X del centro del objeto."),
		),
		c(
			"y",
			N_("Metros hacia el norte (Y)"),
			"metros",
			minimo=-100000.0,
			maximo=100000.0,
			defecto=0.0,
			obligatorio=True,
			si=es("punto"),
			ayuda=N_("Coordenada Y del centro del objeto."),
		),
		c(
			"rumbo",
			N_("Rumbo del frente, en grados"),
			"decimal",
			minimo=0.0,
			maximo=360.0,
			defecto=0.0,
			si=es("punto"),
			ayuda=N_("Hacia dónde mira el frente del objeto: 0 es norte, 90 este, 180 sur y 270 oeste."),
		),
		c("nombre", N_("Nombre propio"), ayuda=N_("Opcional. Vacío: el nombre del objeto en el catálogo.")),
	]


class ErrorColocacion(ValueError):
	"""Lo pedido en el formulario de colocación no se puede intentar siquiera (falta el espacio, la referencia…)."""


def aplicar_colocacion(
	entorno: Entorno, catalogo: Catalogo, tipo: str, variante: str | None, datos: dict[str, Any], paso_minimo: float
) -> colocacion.Colocacion:
	"""Coloca el objeto en ``entorno`` según ``datos`` (los del formulario) y devuelve el resultado.

	Se usa dos veces con los mismos datos: primero sobre una copia, para
	saber qué va a pasar sin tocar nada, y después sobre el entorno abierto.
	Todo se resuelve por id aquí dentro: no se guardan referencias de un
	entorno para usarlas en otro.
	"""
	planta = entorno.planta(str(datos.get("planta") or ""))
	if planta is None:
		raise ErrorColocacion(_("Elija la planta en la que se coloca el objeto."))
	modo = datos.get("modo") or "pared"
	nombre = str(datos.get("nombre") or "")
	if modo == "punto":
		return colocacion.colocar_en_punto(
			entorno,
			planta,
			tipo,
			catalogo,
			float(datos.get("x") or 0.0),
			float(datos.get("y") or 0.0),
			float(datos.get("rumbo") or 0.0),
			variante=variante,
			nombre=nombre,
			paso_minimo=paso_minimo,
		)
	if modo == "junto":
		encontrado = entorno.buscar(str(datos.get("referencia") or ""))
		if encontrado is None or encontrado[0] is not planta:
			raise ErrorColocacion(
				_("Elija el elemento junto al que se coloca el objeto. Si la lista está vacía, coloque antes otro elemento.")
			)
		return colocacion.colocar_junto_a(
			entorno,
			planta,
			encontrado[1],
			tipo,
			catalogo,
			str(datos.get("lado_junto") or "este"),
			separacion=float(datos.get("separacion_junto") or 0.0),
			variante=variante,
			nombre=nombre,
			paso_minimo=paso_minimo,
		)
	espacio = planta.espacio(str(datos.get("espacio") or ""))
	if espacio is None:
		raise ErrorColocacion(_("Elija el espacio en el que se coloca el objeto. Si la lista está vacía, cree antes una habitación."))
	if modo == "esquina":
		return colocacion.colocar_en_esquina(
			entorno,
			planta,
			espacio,
			tipo,
			catalogo,
			str(datos.get("esquina") or "noreste"),
			variante=variante,
			nombre=nombre,
			paso_minimo=paso_minimo,
		)
	alineacion = str(datos.get("alineacion") or "centro")
	return colocacion.colocar_contra_pared(
		entorno,
		planta,
		espacio,
		tipo,
		catalogo,
		str(datos.get("lado") or "norte"),
		alineacion="centro" if alineacion == "distancia" else alineacion,
		desplazamiento=float(datos.get("desplazamiento") or 0.0) if alineacion == "distancia" else None,
		separacion=float(datos.get("separacion") or 0.0),
		variante=variante,
		nombre=nombre,
		paso_minimo=paso_minimo,
	)


@dataclass
class Ensayo:
	"""Lo que pasaría al colocar: si cabe, con qué avisos y con qué medidas quedaría."""

	colocado: bool
	avisos: list[Aviso] = field(default_factory=list)
	objeto: Objeto | None = None
	ajuste: str = ""

	def texto_avisos(self) -> str:
		"""Los avisos en frases, una por línea."""
		return "\n".join(str(aviso) for aviso in self.avisos)


def texto_ajuste(catalogo: Catalogo, tipo: str, variante: str | None, objeto: Objeto) -> str:
	"""Frase que cuenta que el objeto no ha quedado con las medidas pedidas; vacía si quedó como se pidió."""
	definicion = catalogo.objeto(tipo)
	if definicion is None:
		return ""
	pedida = definicion.variante(variante) if variante else None
	ancho = pedida.ancho if pedida is not None else definicion.rango("ancho")[1]
	fondo = pedida.fondo if pedida is not None else definicion.rango("fondo")[1]
	if abs(objeto.ancho - ancho) < 0.005 and abs(objeto.fondo - fondo) < 0.005:
		return ""
	quedo = definicion.variante(objeto.variante) if objeto.variante else None
	if quedo is not None and objeto.variante != (variante or ""):
		return _("Se ha colocado la variante «{variante}» ({ancho} por {fondo} metros) porque con las medidas pedidas no cabía.").format(
			variante=quedo.nombre, ancho=texto_numero(objeto.ancho), fondo=texto_numero(objeto.fondo)
		)
	return _("Se ha ajustado a {ancho} por {fondo} metros porque con las medidas pedidas no cabía.").format(
		ancho=texto_numero(objeto.ancho), fondo=texto_numero(objeto.fondo)
	)


def ensayar(contexto: Any, tipo: str, variante: str | None, datos: dict[str, Any]) -> Ensayo:
	"""Prueba la colocación sobre una COPIA del entorno: el abierto no se toca."""
	copia = Entorno.de_dict(contexto.entorno.a_dict())
	resultado = aplicar_colocacion(copia, contexto.catalogo, tipo, variante, datos, contexto.paso_libre())
	ajuste = texto_ajuste(contexto.catalogo, tipo, variante, resultado.objeto) if resultado.objeto is not None else ""
	return Ensayo(resultado.colocado, list(resultado.avisos), resultado.objeto, ajuste)


def colocar_objeto(contexto: Any, tipo: str, variante: str | None, datos: dict[str, Any], preguntar: bool = True) -> str | None:
	"""Coloca un objeto con las reglas de escala y devuelve su id; None si no cabe o la persona decide no dejarlo.

	- No cabe: se explica y no cambia nada (ni el entorno ni el historial).
	- Cabe con avisos (tapa una puerta, paso estrecho): se enseñan y se
	  pregunta «Dejarlo así» o «Quitarlo»; con «Quitarlo» tampoco cambia nada.
	- Cabe: se hace con ``contexto.ejecutar`` (se puede deshacer), se
	  selecciona y se anuncia en una frase, diciendo si hubo que ajustarlo.
	"""
	padre = getattr(contexto, "ventana", None)
	definicion = contexto.catalogo.objeto(tipo)
	nombre = str(datos.get("nombre") or "") or (definicion.nombre if definicion is not None else tipo)
	try:
		ensayo = ensayar(contexto, tipo, variante, datos)
	except ErrorColocacion as error:
		mostrar_error(padre, str(error), _("Insertar objeto"))
		return None
	if not ensayo.colocado:
		mensaje = _("«{nombre}» no se ha colocado.").format(nombre=nombre)
		if ensayo.avisos:
			mensaje += "\n" + ensayo.texto_avisos()
		mostrar_error(padre, mensaje, _("No cabe"))
		contexto.anunciar(_("«{nombre}» no se ha colocado: no cabe.").format(nombre=nombre))
		return None
	if ensayo.avisos and preguntar:
		pregunta = _("«{nombre}» cabe, pero conviene revisarlo:").format(nombre=nombre) + "\n" + ensayo.texto_avisos()
		if ensayo.ajuste:
			pregunta += "\n" + ensayo.ajuste
		pregunta += "\n" + _("¿Qué quiere hacer?")
		if elegir_opcion(padre, pregunta, _("Insertar objeto"), [_("&Dejarlo así"), _("&Quitarlo")]) != 0:
			contexto.anunciar(_("«{nombre}» no se ha colocado.").format(nombre=nombre))
			return None

	def operacion() -> str:
		resultado = aplicar_colocacion(contexto.entorno, contexto.catalogo, tipo, variante, datos, contexto.paso_libre())
		if resultado.objeto is None:
			# No debería ocurrir (el ensayo dijo que cabía); se trata como «no cabe» y ejecutar no apunta nada.
			raise ErrorColocacion("\n".join(str(aviso) for aviso in resultado.avisos) or _("El objeto no cabe."))
		return resultado.objeto.id

	try:
		id_objeto = contexto.ejecutar(_("colocar {nombre}").format(nombre=nombre), operacion)
	except ErrorColocacion as error:
		mostrar_error(padre, str(error), _("No cabe"))
		return None
	apuntar_reciente(tipo)
	contexto.seleccionar(id_objeto)
	frase = describir_elemento_seguro(contexto, id_objeto)
	if ensayo.ajuste:
		frase = (ensayo.ajuste + " " + frase).strip()
	contexto.anunciar(frase or _("«{nombre}» colocado.").format(nombre=nombre))
	return id_objeto


def describir_elemento_seguro(contexto: Any, id_elemento: str) -> str:
	"""Frase de un elemento por id, o cadena vacía si ya no existe."""
	encontrado = contexto.entorno.buscar(id_elemento) if contexto.entorno is not None else None
	return edicion.describir_elemento(contexto.entorno, encontrado[1], contexto.catalogo) if encontrado else ""


def _valores_iniciales(contexto: Any, planta_id: str | None, espacio_id: str | None) -> dict[str, Any]:
	"""Planta, espacio y referencia de partida: lo pedido o, si no, lo que haya seleccionado."""
	entorno: Entorno = contexto.entorno
	planta: Planta | None = entorno.planta(planta_id or "") or contexto.planta_actual()
	valores: dict[str, Any] = {"modo": "pared"}
	seleccion = contexto.elemento_seleccionado()
	if seleccion is not None and seleccion[0] is not None and planta_id is None:
		planta = seleccion[0]
	if planta is None:
		return valores
	valores["planta"] = planta.id
	espacio = planta.espacio(espacio_id or "")
	if espacio is None and seleccion is not None and seleccion[0] is planta:
		elemento = seleccion[1]
		if elemento in planta.espacios:
			espacio = elemento
		elif isinstance(elemento, (Objeto, Abertura)) or elemento in planta.referencias or elemento in planta.fuentes:
			valores["referencia"] = elemento.id
			x, y = edicion.centro_de(elemento)
			espacio = planta.espacio_en(x, y, incluir_macizos=False)
	if espacio is not None and not espacio.macizo:
		valores["espacio"] = espacio.id
	return valores


def insertar_objeto(
	contexto: Any,
	planta_id: str | None = None,
	espacio_id: str | None = None,
	punto: tuple[float, float] | None = None,
	rumbo: float = 0.0,
) -> str | None:
	"""Abre «Insertar objeto», coloca y devuelve el id del objeto colocado (None si se cancela o no cabe).

	Con ``punto`` (clic en el plano o «colocar aquí» del recorrido) coloca
	centrado en ese punto con ``colocacion.colocar_en_punto``; sin él, tras
	elegir el objeto se pregunta la planta, el espacio y la forma de
	colocarlo: contra una pared, en una esquina, junto a otro elemento o en
	un punto por coordenadas.
	"""
	padre = getattr(contexto, "ventana", None)
	entorno: Entorno | None = contexto.entorno
	if entorno is None or not entorno.plantas:
		mostrar_mensaje(padre, _("Para colocar un objeto hace falta un entorno abierto con al menos una planta."), _("Insertar objeto"))
		return None
	planta = entorno.planta(planta_id or "") or contexto.planta_actual()
	ambito = ("exterior" if planta.exterior else "interior") if planta is not None else None
	elegido = elegir_objeto(contexto, padre, ambito)
	if elegido is None:
		return None
	tipo, variante = elegido
	if punto is not None:
		if planta is None:
			return None
		datos: dict[str, Any] = {"planta": planta.id, "modo": "punto", "x": float(punto[0]), "y": float(punto[1]), "rumbo": float(rumbo)}
		return colocar_objeto(contexto, tipo, variante, datos)
	definicion = contexto.catalogo.objeto(tipo)
	titulo = _("Colocar «{nombre}»").format(nombre=definicion.nombre if definicion is not None else tipo)
	datos_formulario = pedir_formulario(
		padre,
		titulo,
		esquema_colocacion(contexto),
		_valores_iniciales(contexto, planta_id, espacio_id),
		introduccion=_(
			"Diga dónde va el objeto. Si no cabe con sus medidas se probará una variante menor o se encogerá dentro de su rango."
		),
	)
	if datos_formulario is None:
		return None
	datos_formulario.pop("_producto", None)
	return colocar_objeto(contexto, tipo, variante, datos_formulario)
