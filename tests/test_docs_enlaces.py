"""Comprueba la documentación de usuario y del repositorio.

- Los enlaces relativos del README, de los documentos de ``data/docs`` y de
  los ficheros de comunidad llevan a ficheros que existen.
- Cada orden de los menús del Estudio y cada acción de Jugar aparecen en el
  manual o en la lista de teclas, para que nada quede sin documentar.
- Cada documento tiene un solo encabezado de nivel 1 y no salta niveles,
  como piden las pautas para lectores de pantalla.

Los menús y las acciones se leen con ``ast``, sin importar wx ni pygame.
"""

from __future__ import annotations

import ast
import re
import unicodedata
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
DOCS_USUARIO = RAIZ / "data" / "docs"

# Documentos cuya estructura y enlaces se comprueban.
DOCUMENTOS = sorted(
	[p for p in DOCS_USUARIO.glob("*.md")]
	+ [RAIZ / nombre for nombre in ("README.md", "CONTRIBUTING.md", "CODE_OF_CONDUCT.md", "SECURITY.md")]
	+ [RAIZ / "docs" / "LEEME.md"]
)
DOCUMENTOS = [p for p in DOCUMENTOS if p.is_file()]

_RE_ENLACE = re.compile(r"(?<!!)\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
_RE_ENCABEZADO = re.compile(r"^(#{1,6})\s+\S")


def _sin_codigo(texto: str) -> list[tuple[int, str]]:
	"""Líneas (número, texto) fuera de los bloques de código, sin el código en línea."""
	lineas: list[tuple[int, str]] = []
	en_bloque = False
	for numero, linea in enumerate(texto.splitlines(), start=1):
		if linea.lstrip().startswith("```"):
			en_bloque = not en_bloque
			continue
		if en_bloque:
			continue
		lineas.append((numero, re.sub(r"`[^`]*`", "", linea)))
	return lineas


def _llano(texto: str) -> str:
	"""Minúsculas, sin tildes y con los espacios normalizados."""
	sin_tildes = "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")
	return re.sub(r"\s+", " ", sin_tildes.casefold()).strip()


def _nombre(ruta: Path) -> str:
	return ruta.relative_to(RAIZ).as_posix()


# ── Enlaces ──────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("documento", DOCUMENTOS, ids=_nombre)
def test_enlaces_relativos_llevan_a_ficheros_que_existen(documento: Path):
	rotos = []
	for numero, linea in _sin_codigo(documento.read_text(encoding="utf-8-sig")):
		for destino in _RE_ENLACE.findall(linea):
			if re.match(r"^[a-z][a-z0-9+.-]*:", destino, re.IGNORECASE) or destino.startswith("#"):
				continue
			ruta = destino.split("#", 1)[0]
			if not ruta:
				continue
			if not (documento.parent / ruta).resolve().exists():
				rotos.append(f"línea {numero}: {destino}")
	assert not rotos, f"Enlaces rotos en {_nombre(documento)}: " + "; ".join(rotos)


def test_hay_documentos_que_comprobar():
	nombres = {_nombre(p) for p in DOCUMENTOS}
	for esperado in ("README.md", "data/docs/manual.md", "data/docs/teclas.md", "data/docs/novedades.md"):
		assert esperado in nombres


# ── Encabezados ──────────────────────────────────────────────────────────────


@pytest.mark.parametrize("documento", DOCUMENTOS, ids=_nombre)
def test_un_solo_titulo_y_sin_saltos_de_nivel(documento: Path):
	niveles = []
	for numero, linea in _sin_codigo(documento.read_text(encoding="utf-8-sig")):
		coincidencia = _RE_ENCABEZADO.match(linea)
		if coincidencia:
			niveles.append((numero, len(coincidencia.group(1))))
	assert niveles, f"{_nombre(documento)} no tiene encabezados"
	titulos = [numero for numero, nivel in niveles if nivel == 1]
	assert len(titulos) == 1, f"{_nombre(documento)} debe tener un solo #, tiene {len(titulos)}"
	assert niveles[0][1] == 1, f"{_nombre(documento)} debe empezar por el encabezado de nivel 1"
	anterior = 1
	for numero, nivel in niveles[1:]:
		assert nivel <= anterior + 1, f"{_nombre(documento)}, línea {numero}: salta del nivel {anterior} al {nivel}"
		anterior = nivel


# ── Menús del Estudio y acciones de Jugar ────────────────────────────────────


def _texto_n(nodo: ast.AST) -> str | None:
	"""El texto de una llamada ``N_("...")``; None si no lo es."""
	if (
		isinstance(nodo, ast.Call)
		and getattr(nodo.func, "id", "") == "N_"
		and nodo.args
		and isinstance(nodo.args[0], ast.Constant)
		and isinstance(nodo.args[0].value, str)
	):
		return nodo.args[0].value
	return None


def _etiquetas_de_menu(fichero: Path, variable: str) -> list[str]:
	"""Etiquetas de órdenes y submenús de una tabla de menús con el formato de app/ui/menus.py."""
	arbol = ast.parse(fichero.read_text(encoding="utf-8"))
	valor = None
	for nodo in ast.walk(arbol):
		if isinstance(nodo, (ast.Assign, ast.AnnAssign)):
			objetivos = nodo.targets if isinstance(nodo, ast.Assign) else [nodo.target]
			if any(getattr(o, "id", "") == variable for o in objetivos):
				valor = nodo.value
	assert valor is not None, f"No se encontró {variable} en {fichero}"
	etiquetas = []
	for nodo in ast.walk(valor):
		if not isinstance(nodo, ast.Tuple) or len(nodo.elts) < 2:
			continue
		primero, segundo = nodo.elts[0], nodo.elts[1]
		if isinstance(primero, ast.Constant) and isinstance(primero.value, str) and _texto_n(segundo):
			etiquetas.append(_texto_n(segundo))
		elif len(nodo.elts) == 2 and _texto_n(primero) and isinstance(segundo, (ast.List, ast.Constant)):
			etiquetas.append(_texto_n(primero))
	return etiquetas


def _limpiar_etiqueta(etiqueta: str) -> str:
	texto = etiqueta.split("\t", 1)[0].replace("&&", "\0").replace("&", "").replace("\0", "&")
	texto = texto.replace("{nombre}", "EntornoLab")
	return texto.rstrip(". …").strip()


def _ordenes_del_estudio() -> list[str]:
	etiquetas = _etiquetas_de_menu(RAIZ / "app" / "ui" / "menus.py", "MENUS")
	integracion = RAIZ / "app" / "ui" / "seguimiento" / "integracion.py"
	if integracion.is_file():
		etiquetas += _etiquetas_de_menu(integracion, "MENUS_SEGUIMIENTO")
	return sorted({_limpiar_etiqueta(e) for e in etiquetas})


def _acciones_de_jugar() -> list[str]:
	arbol = ast.parse((RAIZ / "app" / "entrada" / "acciones.py").read_text(encoding="utf-8"))
	nombres = []
	for nodo in ast.walk(arbol):
		if isinstance(nodo, ast.Call) and getattr(nodo.func, "id", "") == "Accion" and len(nodo.args) >= 2:
			texto = _texto_n(nodo.args[1])
			if texto:
				nombres.append(texto)
	return sorted(set(nombres))


def _texto_documentado() -> str:
	partes = [(DOCS_USUARIO / nombre).read_text(encoding="utf-8-sig") for nombre in ("manual.md", "teclas.md")]
	return _llano("\n".join(partes))


def test_se_leen_las_tablas_de_menus_y_acciones():
	ordenes = _ordenes_del_estudio()
	acciones = _acciones_de_jugar()
	assert "Guardar como" in ordenes and "Comprobar el entorno" in ordenes
	assert "Dónde estoy" in acciones and "Bastón sonoro" in acciones


@pytest.mark.parametrize("orden", _ordenes_del_estudio())
def test_cada_orden_del_estudio_esta_documentada(orden: str):
	assert _llano(orden) in _texto_documentado(), f"La orden de menú «{orden}» no aparece en manual.md ni en teclas.md"


@pytest.mark.parametrize("accion", _acciones_de_jugar())
def test_cada_accion_de_jugar_esta_documentada(accion: str):
	assert _llano(accion) in _texto_documentado(), f"La acción «{accion}» no aparece en manual.md ni en teclas.md"
