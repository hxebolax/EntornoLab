"""Genera los complementos de objetos de serie en ``data/plugins`` (herramienta de DESARROLLO).

Uso (desde la raíz del proyecto)::

	.venv\\Scripts\\python.exe tools\\generar_complementos.py
	.venv\\Scripts\\python.exe tools\\generar_complementos.py --solo hogar --solo calle
	.venv\\Scripts\\python.exe tools\\generar_complementos.py --comprobar
	.venv\\Scripts\\python.exe tools\\generar_complementos.py --recursos
	.venv\\Scripts\\python.exe tools\\generar_complementos.py --informe
	.venv\\Scripts\\python.exe tools\\generar_complementos.py --solo sanidad --aislado --carpeta C:\\tmp\\prueba

Los objetos de serie se describen en ``tools/complementos_serie/<id>.py``. Los
seis complementos originales tienen además ``<id>_ampliacion.py``, que les
añade objetos y clasifica los que ya tenían sin tocar su módulo. Los sonidos
se sintetizan en ``sonidos.py`` y en los ``sonidos_*.py`` que haya.
De ahí salen, para cada complemento:

- ``complemento.json`` (la ficha, en español) y ``locales/en.json`` (su traducción);
- ``imagenes/<objeto>.png``: la miniatura para el profesional, que es la
  HUELLA en planta del objeto con sus proporciones reales, su color, su letra,
  una marca en el frente y una barra de escala;
- ``sonidos/<nombre>.flac``: los sonidos propios que citan sus objetos,
  sintetizados con numpy (``tools/complementos_serie/sonidos.py``);
- ``LEEME.md``: licencia y lista de objetos.

Cada fichero de sonido está UNA sola vez en el disco. Un sonido que usan dos
o más complementos no se copia en cada uno: va al complemento ``comun`` (que
no tiene objetos) y los demás lo citan como ``comun:<nombre>.flac`` y declaran
``"depende_de": ["comun"]``. La excepción son los sonidos que los seis
complementos originales ya llevaban dentro: esos se quedan en su original
(el primero de ``DUENOS`` si eran de varios), porque hay entornos y pruebas
que los piden por su nombre de siempre, y los demás los toman de allí
(``hogar:sentarse.flac``, con ``hogar`` en ``depende_de``). ``comun`` lleva
también los nombres visibles de la clasificación (funciones, lugares,
estancias…) en español y en inglés.

Y, en la raíz de la carpeta de complementos, un ``LEEME.md`` general que
explica qué son los complementos, cuáles vienen de serie y cómo añadir uno, y
un ``CATALOGO.md`` con el índice completo: complemento, categoría,
subcategoría y cada objeto con sus medidas. Al terminar se escribe en pantalla
el informe de recuentos por complemento, categoría y función.

Es reproducible: volver a ejecutarla sin cambiar las definiciones deja
exactamente los mismos ficheros. Al terminar valida cada complemento
(``validar_complemento``, sonidos de serie citados, inglés completo) y
termina con código 1 si algo falla.

``--comprobar`` no escribe nada: solo valida lo que hay en disco.
``--recursos`` no toca los JSON: regenera miniaturas y sonidos a partir del
``complemento.json`` que haya (útil tras retocar una ficha a mano).
``--informe`` no escribe nada: solo enseña los recuentos de lo que hay en disco.
``--aislado`` (para probar un módulo mientras se escribe, siempre con
``--carpeta`` y ``--solo``) genera el complemento sin mirar los demás: todos
sus sonidos quedan dentro de él y no se escribe ``comun`` ni los índices.

Escribe en la carpeta ``data/plugins`` que está junto al código, no en la
``data`` redirigida por ``APP_DATA_DIR``: son recursos que viajan con el programa.
"""

from __future__ import annotations

import argparse
import copy
import dataclasses
import importlib
import importlib.util
import json
import logging
import os
import pkgutil
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
	sys.path.insert(0, str(RAIZ))

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import pygame  # noqa: E402 - necesita SDL_VIDEODRIVER puesto antes

from app.audio import sintesis  # noqa: E402 - necesita la raíz del proyecto en sys.path
from app.core import paths  # noqa: E402
from app.dominio import geometria as geo  # noqa: E402
from app.dominio import catalogo as cat  # noqa: E402
from app.dominio.catalogo import (  # noqa: E402
	NOMBRE_FICHA,
	DefObjeto,
	es_sonido_de_complemento,
	leer_complemento,
	partes_de_sonido,
	validar_complemento,
)
from tools.complementos_serie import comun, sonidos, taxonomia_en  # noqa: E402
from tools.complementos_serie.comun import ComplementoSerie  # noqa: E402

log = logging.getLogger("generar_complementos")

# Los seis complementos originales: sus objetos y los sonidos que ya llevaban dentro no cambian de sitio.
ORIGINALES = ("hogar", "colegio", "oficina_y_comercio", "calle", "transporte", "juego")
# En este orden se generan (y se listan en la documentación).
COMPLEMENTOS = (
	*ORIGINALES,
	"sanidad",
	"residencia_y_ayudas_tecnicas",
	"hosteleria",
	"comunidad_y_edificio",
	"vehiculos_y_aparcamiento",
	"cultura_y_ocio",
	"deporte",
	"parque_y_naturaleza",
	"administracion_y_servicios",
	"tiendas",
	"trabajo_y_taller",
	"educacion_superior_e_infantil",
	"obstaculos_temporales",
	"estaciones_y_aeropuerto",
)
# Si varios originales llevaban dentro el mismo sonido, se queda en el primero de esta lista (las pruebas
# del motor piden ``hogar/puerta_mueble.flac`` y ``transporte/torno.flac``).
DUENOS = ("hogar", "transporte", "calle", "colegio", "oficina_y_comercio", "juego")
# Complemento sin objetos con los sonidos que comparten los demás y los nombres de la clasificación.
ID_COMUN = "comun"
SUFIJO_AMPLIACION = "_ampliacion"
VERSION = "1.0.0"
AUTOR = "Héctor J. Benítez Corredera"
LICENCIA = "CC BY 4.0"
IDIOMA_TRADUCCION = "en"

LADO_MINIATURA = 128
# Se dibuja a cuatro veces el tamaño y se reduce: así los bordes salen suaves.
SOBREMUESTREO = 4
FONDO_MINIATURA = (246, 246, 244)


def carpeta_de_serie() -> Path:
	"""La carpeta de complementos que se distribuye con el programa."""
	return paths.ruta_base() / "data" / "plugins"


_DEFINICIONES: dict[str, ComplementoSerie] = {}
# Sonidos que cada complemento original llevaba ya dentro: se quedan en él aunque otros los usen.
_SONIDOS_FIJOS: dict[str, frozenset[str]] = {}
_USOS: dict[str, set[str]] | None = None
_SONIDOS_CARGADOS = False


def definicion(id_complemento: str) -> ComplementoSerie:
	"""Carga la definición de un complemento de serie de ``tools/complementos_serie``.

	Si existe ``<id>_ampliacion.py`` se le suma: sus objetos van detrás de los
	del módulo original y su tabla de clasificación se aplica a los que ya había.
	"""
	if id_complemento in _DEFINICIONES:
		return _DEFINICIONES[id_complemento]
	paquete = "tools.complementos_serie"
	base: ComplementoSerie = importlib.import_module(f"{paquete}.{id_complemento}").COMPLEMENTO
	_SONIDOS_FIJOS[id_complemento] = (
		frozenset(
			Path(nombre).stem
			for nombre in sonidos_citados({"objetos": [d.ficha for d in base.objetos]})
			if es_sonido_de_complemento(nombre)
		)
		if id_complemento in ORIGINALES
		else frozenset()
	)
	serie = base
	if importlib.util.find_spec(f"{paquete}.{id_complemento}{SUFIJO_AMPLIACION}") is not None:
		ampliacion: comun.Ampliacion = importlib.import_module(f"{paquete}.{id_complemento}{SUFIJO_AMPLIACION}").AMPLIACION
		serie = dataclasses.replace(
			base,
			categorias={**base.categorias, **ampliacion.categorias},
			objetos=[*base.objetos, *ampliacion.objetos],
			subcategorias={**base.subcategorias, **ampliacion.subcategorias},
			lugares=ampliacion.lugares or base.lugares,
			estancias_de={**base.estancias_de, **ampliacion.estancias_de},
			taxonomia={**base.taxonomia, **ampliacion.taxonomia},
		)
	_DEFINICIONES[id_complemento] = serie
	return serie


def cargar_sonidos(tolerante: bool = False) -> None:
	"""Importa los ``sonidos_*.py`` del paquete: cada uno da de alta sus sonidos en ``sonidos.SONIDOS``.

	Con ``tolerante`` (pruebas de un módulo suelto), uno que no se pueda
	importar se anota y se sigue con los demás; sin ello, el fallo se propaga.
	"""
	global _SONIDOS_CARGADOS
	if _SONIDOS_CARGADOS:
		return
	paquete = importlib.import_module("tools.complementos_serie")
	for modulo in sorted(info.name for info in pkgutil.iter_modules(paquete.__path__) if info.name.startswith("sonidos_")):
		try:
			importlib.import_module(f"tools.complementos_serie.{modulo}")
		except Exception:  # noqa: BLE001 - un módulo de sonidos a medio escribir no debe impedir probar los demás
			if not tolerante:
				raise
			log.exception("No se pudo importar tools/complementos_serie/%s.py; sus sonidos no estarán disponibles.", modulo)
	_SONIDOS_CARGADOS = True


def usos_de_sonidos() -> dict[str, set[str]]:
	"""Sonido propio → complementos de serie que lo citan (mirando todas las definiciones)."""
	global _USOS
	if _USOS is None:
		usos: dict[str, set[str]] = {}
		for id_complemento in COMPLEMENTOS:
			serie = definicion(id_complemento)
			for nombre in sonidos_citados({"objetos": [d.ficha for d in serie.objetos]}):
				if es_sonido_de_complemento(nombre):
					usos.setdefault(Path(nombre).stem, set()).add(id_complemento)
		_USOS = usos
	return _USOS


def dueno_de_sonido(nombre: str) -> str:
	"""Complemento original que ya llevaba dentro ese sonido antes de existir ``comun``; cadena vacía si ninguno.

	Si lo llevaban varios, manda el primero de ``DUENOS``. Ese conserva el
	fichero con su nombre de siempre (``hogar/puerta_mueble.flac``: hay entornos
	y pruebas que lo piden así) y todos los demás lo toman de él.
	"""
	usos_de_sonidos()
	return next((original for original in DUENOS if nombre in _SONIDOS_FIJOS.get(original, frozenset())), "")


def procedencia_de_sonidos(id_complemento: str) -> dict[str, str]:
	"""Sonido propio → complemento del que ese complemento lo toma en lugar de llevar su copia.

	Cada fichero está UNA sola vez en el disco: en el original que ya lo
	llevaba (ver ``dueno_de_sonido``) o, si no lo llevaba ninguno y lo citan
	dos o más complementos, en ``comun``. Los sonidos que solo usa este
	complemento, o de los que es el dueño, no salen aquí: se quedan dentro.
	"""
	definicion(id_complemento)
	procedencia: dict[str, str] = {}
	for nombre, quienes in usos_de_sonidos().items():
		if id_complemento not in quienes:
			continue
		dueno = dueno_de_sonido(nombre)
		if dueno and dueno != id_complemento:
			procedencia[nombre] = dueno
		elif not dueno and len(quienes) >= 2:
			procedencia[nombre] = ID_COMUN
	return procedencia


def sonidos_comunes_de(id_complemento: str) -> frozenset[str]:
	"""Sonidos que ese complemento toma de ``comun`` en lugar de llevar su copia."""
	return frozenset(nombre for nombre, origen in procedencia_de_sonidos(id_complemento).items() if origen == ID_COMUN)


def todos_los_comunes() -> list[str]:
	"""Los sonidos que tiene que llevar el complemento ``comun``, ordenados."""
	return sorted({nombre for id_complemento in COMPLEMENTOS for nombre in sonidos_comunes_de(id_complemento)})


def _de_otro(nombre: Any, procedencia: dict[str, str]) -> Any:
	"""``sonidos/x.flac`` → ``<complemento>:x.flac`` si ese sonido se toma de otro complemento."""
	if (
		isinstance(nombre, str)
		and es_sonido_de_complemento(nombre)
		and not partes_de_sonido(nombre)[0]
		and Path(nombre).stem in procedencia
	):
		return f"{procedencia[Path(nombre).stem]}{cat.SEPARADOR_DEPENDENCIA}{Path(nombre).name}"
	return nombre


def _repartir_sonidos(ficha: dict[str, Any], procedencia: dict[str, str]) -> None:
	"""Cambia en una ficha de objeto (ya copiada) los sonidos que se toman de otro complemento por su nombre allí."""
	for clave, valor in list((ficha.get("sonidos") or {}).items()):
		if isinstance(valor, dict):
			valor["sonido"] = _de_otro(valor.get("sonido"), procedencia)
		else:
			ficha["sonidos"][clave] = _de_otro(valor, procedencia)
	for accion in ficha.get("acciones") or []:
		if "sonido" in accion:
			accion["sonido"] = _de_otro(accion["sonido"], procedencia)
	dinamica = ficha.get("dinamica") or {}
	for fase in dinamica.get("fases") or []:
		if "sonido" in fase:
			fase["sonido"] = _de_otro(fase["sonido"], procedencia)
	if "sonido_al_terminar" in dinamica:
		dinamica["sonido_al_terminar"] = _de_otro(dinamica["sonido_al_terminar"], procedencia)


# ── JSON legible ─────────────────────────────────────────────────────────────


def _es_simple(valor: Any) -> bool:
	"""True si el valor cabe en una línea: un dato suelto o una lista corta de datos sueltos."""
	if isinstance(valor, (str, int, float, bool)) or valor is None:
		return True
	if isinstance(valor, list):
		return all(
			isinstance(v, (str, int, float, bool)) or (isinstance(v, list) and all(isinstance(n, (int, float)) for n in v)) for v in valor
		)
	return False


def a_json(valor: Any, nivel: int = 0) -> str:
	"""JSON con tabuladores en el que las listas de datos sueltos (medidas, etiquetas, puntos) van en una línea."""
	sangria = "\t" * nivel
	if isinstance(valor, dict):
		if not valor:
			return "{}"
		lineas = [f"{sangria}\t{json.dumps(str(clave), ensure_ascii=False)}: {a_json(dato, nivel + 1)}" for clave, dato in valor.items()]
		return "{\n" + ",\n".join(lineas) + f"\n{sangria}}}"
	if isinstance(valor, list) and not _es_simple(valor):
		lineas = [f"{sangria}\t{a_json(dato, nivel + 1)}" for dato in valor]
		return "[\n" + ",\n".join(lineas) + f"\n{sangria}]"
	return json.dumps(valor, ensure_ascii=False)


def _escribir_texto(ruta: Path, texto: str) -> None:
	ruta.parent.mkdir(parents=True, exist_ok=True)
	ruta.write_bytes(texto.encode("utf-8"))


# ── Ficha, traducción y LEEME ────────────────────────────────────────────────


def ficha_de(serie: ComplementoSerie, aislado: bool = False) -> dict[str, Any]:
	"""El ``complemento.json`` de un complemento de serie.

	Con ``aislado`` no se miran los demás complementos: todos los sonidos se
	quedan dentro de este (sirve para probar un módulo suelto).
	"""
	procedencia: dict[str, str] = {} if aislado else procedencia_de_sonidos(serie.id)
	objetos = []
	estados: list[str] = []
	usadas: set[str] = set()
	for definido in serie.objetos:
		ficha = copy.deepcopy(comun.clasificar(serie, definido, serie.taxonomia.get(definido.ficha["id"])))
		ficha["simbolo"]["color"] = ficha["simbolo"]["color"] or serie.categorias[ficha["categoria"]][2]
		_repartir_sonidos(ficha, procedencia)
		objetos.append(ficha)
		usadas.add(ficha["subcategoria"])
		for estado in ficha.get("estados", []):
			if estado not in estados:
				estados.append(estado)
	sobran = sorted(set(serie.taxonomia) - {objeto["id"] for objeto in objetos})
	if sobran:
		raise ValueError(f"{serie.id}: la tabla de clasificación nombra objetos que no existen: {', '.join(sobran)}.")
	ficha_general: dict[str, Any] = {
		"formato": 1,
		"id": serie.id,
		"nombre": serie.nombre,
		"version": VERSION,
		"autor": AUTOR,
		"licencia": LICENCIA,
		"descripcion": serie.descripcion,
	}
	dependencias = {partes_de_sonido(nombre)[0] for nombre in sonidos_citados({"objetos": objetos})} - {""}
	if dependencias:
		# «comun» primero y luego los originales, en el orden de generación: así el JSON no cambia de una vez a otra.
		ficha_general["depende_de"] = sorted(
			dependencias, key=lambda otro: (otro != ID_COMUN, COMPLEMENTOS.index(otro) if otro in COMPLEMENTOS else 0)
		)
	ficha_general["categorias"] = {clave: nombres[0] for clave, nombres in serie.categorias.items()}
	ficha_general["subcategorias"] = {clave: nombres[0] for clave, nombres in serie.subcategorias.items() if clave in usadas}
	ficha_general["estados"] = {estado: comun.ESTADOS[estado][0] for estado in estados}
	ficha_general["objetos"] = objetos
	return ficha_general


def ficha_comun() -> dict[str, Any]:
	"""El ``complemento.json`` de ``comun``: sin objetos, con los nombres en español de la clasificación."""
	return {
		"formato": 1,
		"id": ID_COMUN,
		"nombre": "Común",
		"version": VERSION,
		"autor": AUTOR,
		"licencia": LICENCIA,
		"descripcion": "Sonidos que comparten varios complementos de serie y nombres visibles de la clasificación de objetos. "
		"No tiene objetos: los demás complementos de serie dependen de él.",
		"taxonomia": {faceta: dict(tabla) for faceta, tabla in cat.TAXONOMIAS.items()},
		"objetos": [],
	}


def traduccion_comun() -> dict[str, Any]:
	"""El ``locales/en.json`` de ``comun``: la clasificación en inglés."""
	faltan = [
		f"{faceta}.{clave}"
		for faceta, tabla in cat.TAXONOMIAS.items()
		for clave in tabla
		if not taxonomia_en.TAXONOMIA.get(faceta, {}).get(clave)
	]
	if faltan:
		raise ValueError(f"Falta el nombre en inglés de: {', '.join(faltan)} (tools/complementos_serie/taxonomia_en.py).")
	return {
		"nombre": "Common",
		"descripcion": "Sounds shared by several built-in add-ons and the visible names of the object classification. "
		"It has no objects: the other built-in add-ons depend on it.",
		"taxonomia": {
			faceta: {clave: taxonomia_en.TAXONOMIA[faceta][clave] for clave in tabla} for faceta, tabla in cat.TAXONOMIAS.items()
		},
	}


def traduccion_de(serie: ComplementoSerie, ficha: dict[str, Any]) -> dict[str, Any]:
	"""El ``locales/en.json`` de un complemento de serie."""
	return {
		"nombre": serie.en_nombre,
		"descripcion": serie.en_descripcion,
		"categorias": {clave: nombres[1] for clave, nombres in serie.categorias.items()},
		"subcategorias": {clave: serie.subcategorias[clave][1] for clave in ficha["subcategorias"]},
		"estados": {estado: comun.ESTADOS[estado][1] for estado in ficha["estados"]},
		"objetos": {definido.ficha["id"]: definido.ingles for definido in serie.objetos},
	}


def _medida(valor: Any) -> float:
	return float(valor[1]) if isinstance(valor, list) else float(valor)


def _metros(valor: float) -> str:
	return f"{valor:.2f}".replace(".", ",")


def leeme_de(ficha: dict[str, Any], nombres_sonidos: list[str]) -> str:
	"""El ``LEEME.md`` de un complemento: qué es, licencia y lista de objetos."""
	lineas = [
		f"# {ficha['nombre']}",
		"",
		ficha["descripcion"],
		"",
		f"- Identificador: `{ficha['id']}`",
		f"- Versión: {ficha['version']}",
		f"- Autor: {ficha['autor']}",
		f"- Licencia: {ficha['licencia']} (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)",
		"",
		"Es un complemento de objetos de EntornoLab: solo datos. Los objetos no son dibujos, sino formas con su huella en planta y sus medidas reales en metros, "
		"que el alumno se encuentra y tiene que rodear. El formato se explica en `docs/formato-de-complementos.md`.",
		"",
		"## Licencia",
		"",
		f"Los datos de este complemento (fichas de objetos, traducciones, miniaturas y sonidos) se publican con licencia {ficha['licencia']}: "
		f"se pueden copiar, modificar y redistribuir, también con fines comerciales, citando a su autor ({ficha['autor']}). "
		"Los sonidos están sintetizados por ordenador y las miniaturas se dibujan a partir de las medidas: no hay material de terceros.",
		"",
		"## Cómo se regenera",
		"",
		f"Los ficheros de esta carpeta se generan con `tools/generar_complementos.py --solo {ficha['id']}` a partir de `tools/complementos_serie/{ficha['id']}.py`. "
		"Si se retoca `complemento.json` a mano, `tools/generar_complementos.py --recursos` vuelve a dibujar las miniaturas sin tocar los JSON.",
		"",
		f"## Objetos ({len(ficha['objetos'])})",
		"",
		"Medidas por defecto: ancho × fondo × alto, en metros.",
	]
	for categoria, nombre_categoria in ficha["categorias"].items():
		de_categoria = [o for o in ficha["objetos"] if o["categoria"] == categoria]
		if not de_categoria:
			continue
		lineas += ["", f"### {nombre_categoria} ({len(de_categoria)})"]
		for subcategoria, nombre_subcategoria in ficha.get("subcategorias", {}).items():
			de_subcategoria = [o for o in de_categoria if o.get("subcategoria") == subcategoria]
			if not de_subcategoria:
				continue
			lineas += ["", f"#### {nombre_subcategoria}", ""]
			lineas += [_linea_de_objeto(ficha["id"], objeto) for objeto in de_subcategoria]
	if nombres_sonidos:
		lineas += ["", f"## Sonidos propios ({len(nombres_sonidos)})", "", ", ".join(f"`{nombre}`" for nombre in nombres_sonidos) + "."]
	for dependencia in ficha.get("depende_de", []):
		tomados = sorted(
			{Path(partes_de_sonido(nombre)[1]).stem for nombre in sonidos_citados(ficha) if partes_de_sonido(nombre)[0] == dependencia}
		)
		if not tomados:
			continue
		lineas += [
			"",
			f"## Sonidos que toma del complemento `{dependencia}` ({len(tomados)})",
			"",
			f"Este complemento depende de `{dependencia}`, que viene con el programa: cada sonido que comparten varios complementos está una sola vez en el disco.",
			"",
			", ".join(f"`{nombre}`" for nombre in tomados) + ".",
		]
	return "\n".join(lineas) + "\n"


def _linea_de_objeto(id_complemento: str, objeto: dict[str, Any], con_descripcion: bool = False) -> str:
	"""Una línea de lista con el nombre, el tipo, las medidas por defecto y lo más señalado de un objeto."""
	medidas = objeto["medidas"]
	texto = " × ".join(_metros(_medida(medidas[d])) for d in ("ancho", "fondo", "alto"))
	extras = []
	if objeto.get("variantes"):
		extras.append(f"{len(objeto['variantes'])} variantes")
	if not objeto.get("bloquea", True):
		extras.append("no corta el paso")
	if objeto.get("altura_base", 0) > 0:
		extras.append(f"colgado a {_metros(objeto['altura_base'])} m")
	if objeto.get("contenedor"):
		extras.append("puede esconder un premio")
	detalle = f" ({'; '.join(extras)})" if extras else ""
	linea = f"- **{objeto['nombre']}** (`{id_complemento}/{objeto['id']}`): {texto}{detalle}."
	if con_descripcion:
		clasificacion = [cat.FUNCIONES.get(objeto.get("funcion", ""), ""), cat.OBSTACULOS.get(objeto.get("obstaculo", ""), "")]
		clasificacion += [cat.RIESGOS[riesgo] for riesgo in objeto.get("riesgos", []) if riesgo in cat.RIESGOS]
		linea += f" {_primera_frase(objeto.get('descripcion', ''))} _{'; '.join(c for c in clasificacion if c)}._"
	return linea


def _primera_frase(texto: str) -> str:
	"""La primera frase de una descripción, para que el índice quepa en una línea por objeto."""
	corte = texto.find(". ")
	return texto if corte < 0 else texto[: corte + 1]


def leeme_comun(nombres_sonidos: list[str]) -> str:
	"""El ``LEEME.md`` del complemento ``comun``."""
	usos = usos_de_sonidos()
	lineas = [
		"# Común",
		"",
		"Complemento sin objetos. Lleva dos cosas que comparten los demás complementos de serie:",
		"",
		"- Los **sonidos** que usan dos o más complementos. En lugar de copiar el mismo fichero en cada uno, lo citan como "
		f'`{ID_COMUN}:<nombre>.flac` y declaran `"depende_de": ["{ID_COMUN}"]` en su ficha.',
		"- Los **nombres visibles de la clasificación** de objetos (funciones, lugares, estancias, clases de obstáculo, riesgos y frecuencias), "
		"en español en `complemento.json` y en inglés en `locales/en.json`. Para traducirlos a otro idioma basta añadir `locales/<idioma>.json`.",
		"",
		f"- Identificador: `{ID_COMUN}`",
		f"- Versión: {VERSION}",
		f"- Autor: {AUTOR}",
		f"- Licencia: {LICENCIA} (Creative Commons Atribución 4.0 Internacional, <https://creativecommons.org/licenses/by/4.0/deed.es>)",
		"",
		"No lo desinstale: los complementos que dependen de él seguirían funcionando, pero sin esos sonidos. "
		"Se genera con `tools/generar_complementos.py`; los sonidos están sintetizados por ordenador (`tools/complementos_serie/sonidos*.py`).",
		"",
		f"## Sonidos compartidos ({len(nombres_sonidos)})",
		"",
	]
	for nombre in nombres_sonidos:
		quienes = sorted(q for q in usos.get(nombre, ()) if nombre in sonidos_comunes_de(q))
		lineas.append(f"- `{nombre}`: {', '.join(quienes)}.")
	return "\n".join(lineas) + "\n"


def leeme_general(raiz: Path) -> str:
	"""El ``LEEME.md`` de la carpeta de complementos: qué son, cuáles vienen de serie y cómo añadir uno."""
	lineas = [
		"# Complementos de objetos",
		"",
		"En esta carpeta están los complementos de EntornoLab: los objetos con los que el profesional amuebla los entornos que construye "
		"(viviendas, colegios, hospitales, tiendas, calles, parques, estaciones) para acercarlos al lugar real.",
		"",
		"## Qué es un complemento",
		"",
		"- Una carpeta con un fichero `complemento.json` y, si hacen falta, sonidos (`sonidos/`), imágenes (`imagenes/`) y traducciones (`locales/<idioma>.json`).",
		"- Solo datos. No lleva código y el programa no ejecuta nada de él: instalar el de otra persona no supone un riesgo.",
		"- Sus objetos no son dibujos. Cada uno es una forma (rectángulo, círculo, ele o polígono) con su huella en planta y sus medidas reales en metros, "
		"su altura, su material y su comportamiento. El alumno, al recorrer el entorno como un audiojuego, se los encuentra: chocan, hay que rodearlos, "
		"suenan al golpearlos según su material, algunos tienen sonido propio y otros se pueden abrir, encender, pulsar o esconder un premio.",
		"- Cada objeto declara un tamaño mínimo, uno por defecto y uno máximo, y variantes con nombre (cama de 90, de 135, de 150). "
		"Con eso el programa ajusta el objeto al hueco y nunca lo deja más grande que la habitación.",
		"",
		"- Cada objeto está clasificado: categoría y subcategoría dentro de su complemento, función (asiento, mesa, barrera…), "
		"lugares y estancias donde es habitual, clase de obstáculo (a ras de suelo, bajo, a media altura, alto, en voladizo, a la altura de la cabeza), "
		"riesgos (se mueve, es temporal, es un desnivel…) y frecuencia. Con eso se busca y se filtra en el catálogo del Estudio.",
		"",
		"## Complementos de serie",
		"",
		"| Complemento | Objetos | Sonidos propios | Contenido |",
		"| --- | --- | --- | --- |",
	]
	total_objetos = 0
	for id_complemento in COMPLEMENTOS:
		ruta = raiz / id_complemento / NOMBRE_FICHA
		if not ruta.is_file():
			continue
		ficha = json.loads(ruta.read_text(encoding="utf-8"))
		propios = {
			Path(nombre).stem for nombre in sonidos_citados(ficha) if es_sonido_de_complemento(nombre) and not partes_de_sonido(nombre)[0]
		}
		categorias = ", ".join(nombre[0].lower() + nombre[1:] for nombre in ficha["categorias"].values())
		total_objetos += len(ficha["objetos"])
		lineas.append(
			f"| [`{id_complemento}`]({id_complemento}/LEEME.md) · {ficha['nombre']} | {len(ficha['objetos'])} | {len(propios)} | {categorias[0].upper() + categorias[1:]}. |"
		)
	en_comun = sorted(ruta.stem for ruta in (raiz / ID_COMUN / "sonidos").glob("*.flac")) if (raiz / ID_COMUN / "sonidos").is_dir() else []
	lineas += [
		"",
		f"En total, {total_objetos} objetos. Cada carpeta tiene su `LEEME.md` con la lista completa y las medidas por defecto, "
		"y [`CATALOGO.md`](CATALOGO.md) es el índice de todos: complemento, categoría, subcategoría y cada objeto con sus medidas y una línea de descripción.",
		"",
		f"Además está [`{ID_COMUN}`]({ID_COMUN}/LEEME.md), un complemento sin objetos con los {len(en_comun)} sonidos que comparten varios complementos "
		"(así cada sonido ocupa una sola vez) y con los nombres visibles de la clasificación en español y en inglés. Los demás dependen de él.",
		"",
		f"Autor: {AUTOR}. Licencia de los datos (fichas, traducciones, miniaturas y sonidos): {LICENCIA}, "
		"Creative Commons Atribución 4.0 Internacional (<https://creativecommons.org/licenses/by/4.0/deed.es>). "
		"Se pueden copiar, adaptar y redistribuir citando al autor.",
		"",
		"Las miniaturas de `imagenes/` son la huella en planta de cada objeto, con sus proporciones reales, su color, su letra, "
		"un triángulo que marca el frente y una barra de escala. Un objeto traslúcido no corta el paso; uno con doble contorno está colgado.",
		"",
		"Los complementos de serie se generan con `tools/generar_complementos.py` a partir de `tools/complementos_serie/`: no los edite aquí si quiere que el cambio dure. "
		"Para hacer el suyo, cree una carpeta nueva.",
		"",
		"## Cómo añadir un complemento",
		"",
		"Hay tres maneras:",
		"",
		"1. **Copiar su carpeta aquí**, dentro de `data/plugins`, con el mismo nombre que su identificador, y reiniciar el Estudio.",
		"2. **Instalar un fichero `.elabc`** (un ZIP con el complemento) desde el Estudio, en Herramientas, «Complementos instalados», con el botón «Añadir desde fichero».",
		"3. **Desde el catálogo en línea**, en Herramientas, Catálogo en línea de complementos (ver `docs/catalogo-de-complementos.md`).",
		"",
		"Un complemento se puede desactivar sin borrarlo: sus objetos dejan de salir en el catálogo, pero los ya colocados siguen funcionando. "
		"Si un entorno usa un complemento que no está instalado, se abre igual: sus objetos se conservan como cajas con sus medidas.",
		"",
		"## Cómo crear uno",
		"",
		"- Guía paso a paso, sin programar, con un ejemplo completo: `docs/crear-un-complemento.md`.",
		"- Referencia del formato, clave por clave: `docs/formato-de-complementos.md`.",
		"- Cómo publicarlo en el catálogo en línea: `docs/catalogo-de-complementos.md`.",
	]
	return "\n".join(lineas) + "\n"


# ── Sonidos ──────────────────────────────────────────────────────────────────


def sonidos_citados(ficha: dict[str, Any]) -> list[str]:
	"""Todos los nombres de sonido que citan los objetos de una ficha, sin repetir y en orden."""
	nombres: list[str] = []
	for objeto in ficha.get("objetos", []):
		citados = []
		for valor in (objeto.get("sonidos") or {}).values():
			citados.append(valor.get("sonido") if isinstance(valor, dict) else valor)
		citados += [accion.get("sonido") for accion in objeto.get("acciones") or []]
		dinamica = objeto.get("dinamica") or {}
		citados += [fase.get("sonido") for fase in dinamica.get("fases") or []]
		citados.append(dinamica.get("sonido_al_terminar"))
		for nombre in citados:
			if isinstance(nombre, str) and nombre and nombre not in nombres:
				nombres.append(nombre)
	return nombres


def sonidos_de_serie() -> set[str]:
	"""Claves de los sonidos de serie del programa (``data/sounds/catalogo.json``)."""
	ruta = paths.ruta_base() / "data" / "sounds" / "catalogo.json"
	try:
		return set(json.loads(ruta.read_text(encoding="utf-8"))["sonidos"])
	except OSError, ValueError, KeyError:
		return set(sintesis.nombres())


def escribir_sonidos(carpeta: Path, ficha: dict[str, Any]) -> list[str]:
	"""Sintetiza en ``carpeta/sonidos`` los sonidos propios que cita la ficha; devuelve sus nombres.

	Los que la ficha toma de otro complemento (``comun:x.flac``) no se escriben aquí.
	"""
	propios = sorted(
		{Path(nombre).stem for nombre in sonidos_citados(ficha) if es_sonido_de_complemento(nombre) and not partes_de_sonido(nombre)[0]}
	)
	return _sintetizar(carpeta, propios, ficha["id"])


def _sintetizar(carpeta: Path, propios: list[str], id_complemento: str) -> list[str]:
	"""Escribe en ``carpeta/sonidos`` esos sonidos y quita los que sobren."""
	cargar_sonidos()
	destino = carpeta / "sonidos"
	ficha = {"id": id_complemento}
	for nombre in propios:
		if nombre not in sonidos.SONIDOS:
			raise KeyError(f"El complemento «{ficha['id']}» cita el sonido «{nombre}», que no está en tools/complementos_serie/sonidos.py")
		sintesis.escribir_audio(destino / f"{nombre}.flac", sonidos.generar(nombre))
	_quitar_sobrantes(destino, {f"{nombre}.flac" for nombre in propios}, ".flac")
	return propios


def _quitar_sobrantes(carpeta: Path, vigentes: set[str], extension: str) -> None:
	"""Borra de una carpeta generada los ficheros de ese tipo que ya no corresponden a nada."""
	if not carpeta.is_dir():
		return
	for ruta in carpeta.iterdir():
		if ruta.suffix.lower() == extension and ruta.name not in vigentes:
			log.info("Se quita %s, que ya no se usa.", ruta)
			ruta.unlink()
	if not any(carpeta.iterdir()):
		carpeta.rmdir()


# ── Miniaturas ───────────────────────────────────────────────────────────────


def _rgb(color: str) -> tuple[int, int, int]:
	return int(color[1:3], 16), int(color[3:5], 16), int(color[5:7], 16)


def _centro_visible(puntos: list[tuple[float, float]]) -> tuple[float, float]:
	"""Un punto de dentro del polígono donde poner la letra: su centroide o, si cae fuera (una ele), el mejor de una rejilla."""
	centroide = geo.centroide(puntos)
	if geo.punto_en_poligono(centroide, puntos, borde=False):
		return centroide
	x0, y0, x1, y1 = geo.caja(puntos)
	mejor, holgura = centroide, -1.0
	for i in range(1, 12):
		for j in range(1, 12):
			candidato = (x0 + (x1 - x0) * i / 12, y0 + (y1 - y0) * j / 12)
			if not geo.punto_en_poligono(candidato, puntos, borde=False):
				continue
			distancia = min(geo.distancia_punto_segmento(candidato, puntos[k], puntos[(k + 1) % len(puntos)]) for k in range(len(puntos)))
			if distancia > holgura:
				mejor, holgura = candidato, distancia
	return mejor


def dibujar_miniatura(definicion_objeto: DefObjeto) -> pygame.Surface:
	"""Miniatura de un objeto: su huella en planta con sus proporciones reales.

	La parte de atrás queda arriba y el frente abajo, marcado con un
	triángulo. Un objeto que no corta el paso se dibuja traslúcido; uno
	colgado, con un segundo contorno por dentro. La barra de abajo a la
	izquierda mide lo que dice su rótulo.
	"""
	lado = LADO_MINIATURA * SOBREMUESTREO
	margen = 18 * SOBREMUESTREO
	lienzo = pygame.Surface((lado, lado), pygame.SRCALPHA)
	lienzo.fill((*FONDO_MINIATURA, 255))
	ancho = definicion_objeto.rango("ancho")[1]
	fondo = definicion_objeto.rango("fondo")[1]
	escala = (lado - 2 * margen) / max(ancho, fondo)
	centro = lado / 2
	unidad = definicion_objeto.puntos_forma()
	puntos = [(centro + (x - 0.5) * ancho * escala, centro - 4 * SOBREMUESTREO + (y - 0.5) * fondo * escala) for x, y in unidad]
	color = _rgb(definicion_objeto.color())
	oscuro = tuple(int(canal * 0.55) for canal in color)
	capa = pygame.Surface((lado, lado), pygame.SRCALPHA)
	pygame.draw.polygon(capa, (*color, 255 if definicion_objeto.bloquea else 105), puntos)
	lienzo.blit(capa, (0, 0))
	pygame.draw.polygon(lienzo, oscuro, puntos, width=2 * SOBREMUESTREO)
	if definicion_objeto.altura_base > 0:
		cx, cy = geo.centroide(puntos)
		interior = [(cx + (x - cx) * 0.72, cy + (y - cy) * 0.72) for x, y in puntos]
		pygame.draw.polygon(lienzo, (255, 255, 255), interior, width=SOBREMUESTREO)
	# El frente: un triángulo bajo la huella, apuntando hacia fuera.
	base_y = max(y for _x, y in puntos) + 3 * SOBREMUESTREO
	pygame.draw.polygon(
		lienzo,
		(60, 60, 60),
		[(centro - 5 * SOBREMUESTREO, base_y), (centro + 5 * SOBREMUESTREO, base_y), (centro, base_y + 6 * SOBREMUESTREO)],
	)
	# La letra, en blanco o en negro según contraste mejor con el color.
	claro = (0.299 * color[0] + 0.587 * color[1] + 0.114 * color[2]) > 150 or not definicion_objeto.bloquea
	fuente = pygame.font.Font(None, 30 * SOBREMUESTREO)
	letra = fuente.render(definicion_objeto.letra(), True, (20, 20, 20) if claro else (255, 255, 255))
	lienzo.blit(letra, letra.get_rect(center=_centro_visible(puntos)))
	# Barra de escala.
	mayor = max(ancho, fondo)
	metros = next((m for m in (2.0, 1.0, 0.5, 0.2, 0.1, 0.05) if m <= mayor * 0.6), 0.05)
	largo = metros * escala
	x0, y0 = 5 * SOBREMUESTREO, lado - 6 * SOBREMUESTREO
	pygame.draw.line(lienzo, (40, 40, 40), (x0, y0), (x0 + largo, y0), width=2 * SOBREMUESTREO)
	for x in (x0, x0 + largo):
		pygame.draw.line(lienzo, (40, 40, 40), (x, y0 - 3 * SOBREMUESTREO), (x, y0 + 2 * SOBREMUESTREO), width=SOBREMUESTREO)
	rotulo = f"{metros:g} m".replace(".", ",") if metros >= 1 else f"{round(metros * 100)} cm"
	etiqueta = pygame.font.Font(None, 13 * SOBREMUESTREO).render(rotulo, True, (40, 40, 40))
	lienzo.blit(etiqueta, (x0 + largo + 3 * SOBREMUESTREO, y0 - etiqueta.get_height() / 2))
	return pygame.transform.smoothscale(lienzo, (LADO_MINIATURA, LADO_MINIATURA))


def escribir_miniaturas(carpeta: Path) -> int:
	"""Dibuja en ``carpeta/imagenes`` la miniatura de cada objeto del ``complemento.json`` que haya; devuelve cuántas."""
	pygame.font.init()
	complemento, _avisos = leer_complemento(carpeta, idioma="es")
	destino = carpeta / "imagenes"
	destino.mkdir(parents=True, exist_ok=True)
	vigentes: set[str] = set()
	for definicion_objeto in complemento.objetos:
		nombre = Path(str(definicion_objeto.imagen.get("fichero") or f"imagenes/{definicion_objeto.id}.png")).name
		pygame.image.save(dibujar_miniatura(definicion_objeto), str(destino / nombre))
		vigentes.add(nombre)
	_quitar_sobrantes(destino, vigentes, ".png")
	return len(vigentes)


# ── Comprobación ─────────────────────────────────────────────────────────────


def comprobar(carpeta: Path) -> list[str]:
	"""Problemas de un complemento de serie ya escrito; lista vacía si está listo para distribuirse."""
	problemas = [f"[{aviso.gravedad}] {aviso.codigo}: {aviso.mensaje} {aviso.sugerencia}" for aviso in validar_complemento(carpeta)]
	if not (carpeta / NOMBRE_FICHA).is_file():
		return problemas
	ficha = json.loads((carpeta / NOMBRE_FICHA).read_text(encoding="utf-8"))
	de_serie = sonidos_de_serie()
	if ficha.get("id") == ID_COMUN:
		return problemas + _comprobar_comun(carpeta, ficha)
	for nombre in sonidos_citados(ficha):
		if es_sonido_de_complemento(nombre):
			dependencia, fichero = partes_de_sonido(nombre)
			if dependencia and dependencia not in ficha.get("depende_de", []):
				problemas.append(f"El sonido «{nombre}» es de «{dependencia}», que no está en «depende_de».")
			if not ((carpeta.parent / dependencia if dependencia else carpeta) / "sonidos" / Path(fichero).name).is_file():
				problemas.append(f"Falta el sonido propio «{nombre}».")
		elif nombre not in de_serie:
			problemas.append(f"El sonido de serie «{nombre}» no existe en data/sounds/catalogo.json.")
	ruta_ingles = carpeta / "locales" / f"{IDIOMA_TRADUCCION}.json"
	if not ruta_ingles.is_file():
		return [*problemas, f"Falta la traducción locales/{IDIOMA_TRADUCCION}.json."]
	ingles = json.loads(ruta_ingles.read_text(encoding="utf-8"))
	for clave in ("nombre", "descripcion"):
		if not ingles.get(clave):
			problemas.append(f"A la traducción le falta «{clave}».")
	for tabla in ("categorias", "subcategorias", "estados"):
		for clave in ficha.get(tabla, {}):
			if not ingles.get(tabla, {}).get(clave):
				problemas.append(f"A la traducción le falta «{tabla}.{clave}».")
	for objeto in ficha.get("objetos", []):
		# La clasificación es obligatoria en los complementos de serie, aunque el formato la deje opcional.
		sin_clasificar = [
			clave for clave in ("subcategoria", "funcion", "lugares", "estancias", "obstaculo", "frecuencia") if not objeto.get(clave)
		]
		if objeto.get("subcategoria") and objeto["subcategoria"] not in ficha.get("subcategorias", {}):
			sin_clasificar.append("subcategorias." + objeto["subcategoria"])
		if sin_clasificar:
			problemas.append(f"Al objeto «{objeto['id']}» le falta clasificar: {', '.join(sin_clasificar)}.")
		textos = ingles.get("objetos", {}).get(objeto["id"], {})
		faltan = [clave for clave in ("nombre", "descripcion", "etiquetas", "imagen") if not textos.get(clave)]
		faltan += [f"variantes.{v['id']}" for v in objeto.get("variantes", []) if not textos.get("variantes", {}).get(v["id"])]
		faltan += [f"acciones.{a['id']}" for a in objeto.get("acciones", []) if not textos.get("acciones", {}).get(a["id"])]
		if objeto.get("aviso") and not textos.get("aviso"):
			faltan.append("aviso")
		if faltan:
			problemas.append(f"Al objeto «{objeto['id']}» le falta traducir: {', '.join(faltan)}.")
	_avisos, objetos_ingles = _cargar_solo(carpeta, IDIOMA_TRADUCCION)
	problemas += [f"[{aviso.gravedad}] {aviso.codigo}: {aviso.mensaje}" for aviso in _avisos]
	if objetos_ingles != len(ficha.get("objetos", [])):
		problemas.append(f"En inglés se cargan {objetos_ingles} objetos de {len(ficha.get('objetos', []))}.")
	return problemas


def _cargar_solo(carpeta: Path, idioma: str) -> tuple[list[Any], int]:
	"""Avisos de cargar ese complemento en un idioma y cuántos objetos salen (sin cargar los demás: con veinte sería lento)."""
	complemento, avisos = leer_complemento(carpeta, idioma)
	for dependencia in complemento.depende_de:
		if not (carpeta.parent / dependencia / NOMBRE_FICHA).is_file():
			avisos.append(
				cat.Aviso(
					gravedad="aviso",
					codigo="dependencia_ausente",
					mensaje=f"Falta el complemento «{dependencia}», del que depende «{complemento.id}».",
				)
			)
	return avisos, len(complemento.objetos)


def _comprobar_comun(carpeta: Path, ficha: dict[str, Any]) -> list[str]:
	"""Problemas propios del complemento ``comun``: su clasificación completa en los dos idiomas."""
	problemas: list[str] = []
	ruta_ingles = carpeta / "locales" / f"{IDIOMA_TRADUCCION}.json"
	if not ruta_ingles.is_file():
		return [f"Falta la traducción locales/{IDIOMA_TRADUCCION}.json."]
	ingles = json.loads(ruta_ingles.read_text(encoding="utf-8"))
	for clave in ("nombre", "descripcion"):
		if not ingles.get(clave):
			problemas.append(f"A la traducción le falta «{clave}».")
	for faceta, tabla in cat.TAXONOMIAS.items():
		for clave in tabla:
			for idioma, nombres in (("español", ficha.get("taxonomia", {})), ("inglés", ingles.get("taxonomia", {}))):
				if not nombres.get(faceta, {}).get(clave):
					problemas.append(f"Falta el nombre en {idioma} de «{faceta}.{clave}».")
	if not (carpeta / "sonidos").is_dir() and ficha.get("objetos") == []:
		log.info("%s no tiene sonidos compartidos.", ID_COMUN)
	return problemas


# ── Generación ───────────────────────────────────────────────────────────────


def generar_comun(raiz: Path) -> list[str]:
	"""Escribe el complemento ``comun`` en ``raiz`` y devuelve los problemas encontrados al comprobarlo."""
	carpeta = raiz / ID_COMUN
	_escribir_texto(carpeta / NOMBRE_FICHA, a_json(ficha_comun()) + "\n")
	_escribir_texto(carpeta / "locales" / f"{IDIOMA_TRADUCCION}.json", a_json(traduccion_comun()) + "\n")
	propios = _sintetizar(carpeta, todos_los_comunes(), ID_COMUN)
	_escribir_texto(carpeta / "LEEME.md", leeme_comun(propios))
	peso = sum(ruta.stat().st_size for ruta in carpeta.rglob("*") if ruta.is_file())
	log.info("%s: %s sonidos compartidos, %.2f MB.", ID_COMUN, len(propios), peso / 1048576.0)
	return comprobar(carpeta)


def _comun_al_dia(raiz: Path) -> bool:
	"""True si ``raiz/comun`` ya tiene la ficha y los sonidos que tocan (para no sintetizarlos otra vez)."""
	carpeta = raiz / ID_COMUN
	ruta = carpeta / NOMBRE_FICHA
	if not ruta.is_file() or ruta.read_text(encoding="utf-8") != a_json(ficha_comun()) + "\n":
		return False
	en_disco = {r.stem for r in (carpeta / "sonidos").glob("*.flac")} if (carpeta / "sonidos").is_dir() else set()
	return en_disco == set(todos_los_comunes()) and (carpeta / "locales" / f"{IDIOMA_TRADUCCION}.json").is_file()


def generar(id_complemento: str, raiz: Path, solo_recursos: bool = False, aislado: bool = False) -> list[str]:
	"""Escribe un complemento de serie en ``raiz/<id>`` y devuelve los problemas encontrados al comprobarlo.

	Salvo con ``aislado``, se asegura antes de que ``raiz/comun`` exista: el
	complemento puede citar sonidos de allí.
	"""
	if id_complemento == ID_COMUN:
		return generar_comun(raiz)
	carpeta = raiz / id_complemento
	if not aislado and not solo_recursos and not _comun_al_dia(raiz):
		problemas_comun = generar_comun(raiz)
		if problemas_comun:
			return [f"{ID_COMUN}: {problema}" for problema in problemas_comun]
	if solo_recursos:
		ficha = json.loads((carpeta / NOMBRE_FICHA).read_text(encoding="utf-8"))
	else:
		serie = definicion(id_complemento)
		ficha = ficha_de(serie, aislado)
		_escribir_texto(carpeta / NOMBRE_FICHA, a_json(ficha) + "\n")
		_escribir_texto(carpeta / "locales" / f"{IDIOMA_TRADUCCION}.json", a_json(traduccion_de(serie, ficha)) + "\n")
	propios = escribir_sonidos(carpeta, ficha)
	miniaturas = escribir_miniaturas(carpeta)
	if not solo_recursos:
		_escribir_texto(carpeta / "LEEME.md", leeme_de(ficha, propios))
	peso = sum(ruta.stat().st_size for ruta in carpeta.rglob("*") if ruta.is_file())
	log.info(
		"%s: %s objetos, %s sonidos propios, %s miniaturas, %.2f MB.",
		id_complemento,
		len(ficha["objetos"]),
		len(propios),
		miniaturas,
		peso / 1048576.0,
	)
	return comprobar(carpeta)


# ── Índice e informe ─────────────────────────────────────────────────────────


def fichas_en_disco(raiz: Path) -> list[dict[str, Any]]:
	"""Las fichas de los complementos de serie con objetos que hay en ``raiz``, en su orden."""
	fichas = []
	for id_complemento in COMPLEMENTOS:
		ruta = raiz / id_complemento / NOMBRE_FICHA
		if ruta.is_file():
			fichas.append(json.loads(ruta.read_text(encoding="utf-8")))
	return fichas


def _tabla(cabeceras: tuple[str, ...], filas: list[tuple[Any, ...]]) -> list[str]:
	lineas = ["| " + " | ".join(cabeceras) + " |", "| " + " | ".join("---" for _ in cabeceras) + " |"]
	lineas += ["| " + " | ".join(str(celda) for celda in fila) + " |" for fila in filas]
	return lineas


def _recuento(fichas: list[dict[str, Any]], clave: str, tabla: dict[str, str]) -> list[tuple[str, int]]:
	"""Cuántos objetos hay en cada valor de una clave de clasificación (de valor único o lista), de más a menos."""
	cuenta: dict[str, int] = {}
	for ficha in fichas:
		for objeto in ficha["objetos"]:
			valores = objeto.get(clave) or []
			for valor in valores if isinstance(valores, list) else [valores]:
				cuenta[valor] = cuenta.get(valor, 0) + 1
	return sorted(((tabla.get(valor, valor), total) for valor, total in cuenta.items()), key=lambda par: (-par[1], par[0]))


def informe(raiz: Path) -> str:
	"""Recuentos de lo que hay en disco, en Markdown: por complemento, por categoría, por función y por el resto de la clasificación."""
	fichas = fichas_en_disco(raiz)
	total = sum(len(ficha["objetos"]) for ficha in fichas)
	lineas = [f"Total: {total} objetos en {len(fichas)} complementos.", "", "### Por complemento", ""]
	filas = []
	for ficha in fichas:
		carpeta = raiz / ficha["id"]
		propios = len(list((carpeta / "sonidos").glob("*.flac"))) if (carpeta / "sonidos").is_dir() else 0
		peso = sum(ruta.stat().st_size for ruta in carpeta.rglob("*") if ruta.is_file()) / 1048576.0
		usadas = {objeto["categoria"] for objeto in ficha["objetos"]}
		subcategorias = {objeto.get("subcategoria") for objeto in ficha["objetos"]}
		filas.append(
			(
				f"`{ficha['id']}`",
				ficha["nombre"],
				len(ficha["objetos"]),
				len(usadas),
				len(subcategorias),
				propios,
				f"{peso:.2f}".replace(".", ","),
			)
		)
	lineas += _tabla(("Complemento", "Nombre", "Objetos", "Categorías", "Subcategorías", "Sonidos propios", "MB"), filas)
	carpeta_comun = raiz / ID_COMUN
	if carpeta_comun.is_dir():
		peso = sum(ruta.stat().st_size for ruta in carpeta_comun.rglob("*") if ruta.is_file()) / 1048576.0
		lineas += [
			"",
			f"`{ID_COMUN}`: {len(list((carpeta_comun / 'sonidos').glob('*.flac')))} sonidos compartidos, {f'{peso:.2f}'.replace('.', ',')} MB.",
		]
	lineas += ["", "### Por categoría", ""]
	filas = []
	for ficha in fichas:
		for categoria, nombre in ficha["categorias"].items():
			cuantos = sum(1 for objeto in ficha["objetos"] if objeto["categoria"] == categoria)
			if cuantos:
				filas.append((ficha["nombre"], nombre, cuantos))
	lineas += _tabla(("Complemento", "Categoría", "Objetos"), filas)
	for titulo, clave, tabla in (
		("Por función", "funcion", cat.FUNCIONES),
		("Por clase de obstáculo", "obstaculo", cat.OBSTACULOS),
		("Por riesgo", "riesgos", cat.RIESGOS),
		("Por frecuencia", "frecuencia", cat.FRECUENCIAS),
		("Por lugar", "lugares", cat.LUGARES),
		("Por estancia", "estancias", cat.ESTANCIAS),
	):
		lineas += ["", f"### {titulo}", ""]
		lineas += _tabla((titulo[4:].capitalize(), "Objetos"), _recuento(fichas, clave, tabla))
	return "\n".join(lineas) + "\n"


def catalogo_md(raiz: Path) -> str:
	"""El ``CATALOGO.md``: índice completo, navegable por encabezados, de todos los objetos de serie."""
	fichas = fichas_en_disco(raiz)
	lineas = [
		"# Catálogo de objetos de serie",
		"",
		"Índice de todos los objetos de los complementos de serie de EntornoLab. Se navega por encabezados: "
		"complemento (nivel 2), categoría (nivel 3), subcategoría (nivel 4). Cada objeto lleva su identificador, "
		"sus medidas por defecto (ancho × fondo × alto, en metros), la primera frase de su descripción y, en cursiva, su función y su clase de obstáculo.",
		"",
		"Este fichero lo escribe `tools/generar_complementos.py`: no lo edite a mano.",
		"",
		"## Resumen",
		"",
		*informe(raiz).splitlines(),
	]
	for ficha in fichas:
		lineas += ["", f"## {ficha['nombre']} ({len(ficha['objetos'])})", "", ficha["descripcion"], "", f"Identificador: `{ficha['id']}`."]
		for categoria, nombre_categoria in ficha["categorias"].items():
			de_categoria = [o for o in ficha["objetos"] if o["categoria"] == categoria]
			if not de_categoria:
				continue
			lineas += ["", f"### {ficha['nombre']}: {nombre_categoria} ({len(de_categoria)})"]
			for subcategoria, nombre_subcategoria in ficha.get("subcategorias", {}).items():
				de_subcategoria = [o for o in de_categoria if o.get("subcategoria") == subcategoria]
				if not de_subcategoria:
					continue
				lineas += ["", f"#### {nombre_subcategoria} ({len(de_subcategoria)})", ""]
				lineas += [_linea_de_objeto(ficha["id"], objeto, con_descripcion=True) for objeto in de_subcategoria]
	return "\n".join(lineas) + "\n"


def main(argv: list[str] | None = None) -> int:
	"""Genera (o solo comprueba) los complementos de serie. Devuelve el código de salida del proceso."""
	logging.basicConfig(level=logging.INFO, format="%(message)s")
	analizador = argparse.ArgumentParser(description="Genera los complementos de objetos de serie de EntornoLab.")
	analizador.add_argument(
		"--carpeta", type=Path, default=None, help="carpeta de complementos de destino (por defecto, data/plugins del programa)"
	)
	analizador.add_argument(
		"--solo", action="append", choices=(*COMPLEMENTOS, ID_COMUN), help="genera solo ese complemento (se puede repetir)"
	)
	analizador.add_argument("--comprobar", action="store_true", help="no escribe nada: solo valida los complementos que hay en disco")
	analizador.add_argument(
		"--recursos", action="store_true", help="no toca los JSON: regenera miniaturas y sonidos desde el complemento.json que haya"
	)
	analizador.add_argument(
		"--informe",
		action="store_true",
		help="no escribe nada: enseña los recuentos por complemento, categoría y función de lo que hay en disco",
	)
	analizador.add_argument(
		"--aislado",
		action="store_true",
		help="para probar un módulo suelto (con --solo y --carpeta): no mira los demás complementos ni escribe comun ni los índices",
	)
	argumentos = analizador.parse_args(argv)
	raiz = (argumentos.carpeta or carpeta_de_serie()).resolve()
	if argumentos.informe:
		log.info("%s", informe(raiz))
		return 0
	if argumentos.aislado and (not argumentos.solo or argumentos.carpeta is None or raiz == carpeta_de_serie().resolve()):
		log.error("--aislado es solo para pruebas: úselo con --solo y con --carpeta apuntando a una carpeta temporal.")
		return 1
	cargar_sonidos(tolerante=argumentos.aislado)
	con_problemas = 0
	# «comun» va el primero: los demás citan sus sonidos.
	pedidos = list(argumentos.solo or COMPLEMENTOS)
	if not argumentos.aislado and not argumentos.recursos:
		pedidos.insert(0, ID_COMUN)
	for id_complemento in pedidos:
		try:
			problemas = (
				comprobar(raiz / id_complemento)
				if argumentos.comprobar
				else generar(id_complemento, raiz, argumentos.recursos, argumentos.aislado)
			)
		except OSError, ValueError, KeyError:
			log.exception("No se pudo generar el complemento «%s».", id_complemento)
			con_problemas += 1
			continue
		for problema in problemas:
			log.error("%s: %s", id_complemento, problema)
		con_problemas += bool(problemas)
	if argumentos.comprobar and not argumentos.solo:
		for nombre, texto in (("LEEME.md", leeme_general(raiz)), ("CATALOGO.md", catalogo_md(raiz))):
			if not (raiz / nombre).is_file() or (raiz / nombre).read_text(encoding="utf-8") != texto:
				log.error("%s no está al día: vuelva a generar.", nombre)
				con_problemas += 1
	if not argumentos.comprobar and not argumentos.aislado:
		_escribir_texto(raiz / "LEEME.md", leeme_general(raiz))
		_escribir_texto(raiz / "CATALOGO.md", catalogo_md(raiz))
		log.info("%s", informe(raiz))
	if con_problemas:
		log.error("Hay %s complementos con problemas.", con_problemas)
		return 1
	log.info("Complementos de serie correctos en %s.", raiz)
	return 0


if __name__ == "__main__":
	sys.exit(main())
