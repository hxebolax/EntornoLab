"""Coherencia del proyecto: versión única, data limpia, rutas portables y .bat correcto."""

from __future__ import annotations

import ast
import re

from app.core import paths
from app.core.version import APP_VERSION, EJECUTABLE_ESTUDIO, EJECUTABLE_REPRODUCTOR, ID_APLICACION

from .conftest import RAIZ


def _constantes_de(archivo):
	arbol = ast.parse(archivo.read_text(encoding="utf-8"))
	valores = {}
	for nodo in arbol.body:
		if isinstance(nodo, ast.Assign) and len(nodo.targets) == 1 and isinstance(nodo.targets[0], ast.Name):
			try:
				valores[nodo.targets[0].id] = ast.literal_eval(nodo.value)
			except ValueError:
				continue
	return valores


def test_version_unica():
	texto = (RAIZ / "pyproject.toml").read_text(encoding="utf-8")
	coincidencia = re.search(r'^version\s*=\s*"([^"]+)"', texto, re.MULTILINE)
	assert coincidencia and coincidencia.group(1) == APP_VERSION


def test_setup_cx_coherente_y_limpio():
	setup = RAIZ / "setup_cx.py"
	constantes = _constantes_de(setup)
	assert constantes["NOMBRE_APP"] == ID_APLICACION
	# Dos ejecutables: el Estudio y el reproductor, con los nombres de version.py.
	assert constantes["EJECUTABLE"] == EJECUTABLE_ESTUDIO
	assert constantes["EJECUTABLE_JUGAR"] == EJECUTABLE_REPRODUCTOR
	assert not set(constantes["DATA_DISTRIBUIBLE"]) & constantes["DATA_PROHIBIDO"]
	# Lo personal nunca viaja: configuración, registros, fichas, sesiones y entornos del profesional.
	assert {"config", "logs", "db", "sessions", "entornos", "cache", "temp", "backups"} <= constantes["DATA_PROHIBIDO"]
	assert {"bin", "sounds", "locales", "docs", "icons", "plugins", "ejemplos"} <= set(constantes["DATA_DISTRIBUIBLE"])
	assert '"include_msvcr": True' in setup.read_text(encoding="utf-8")


def test_data_del_proyecto_solo_tiene_lo_distribuible():
	distribuible = set(_constantes_de(RAIZ / "setup_cx.py")["DATA_DISTRIBUIBLE"])
	carpetas = {p.name for p in (RAIZ / "data").iterdir() if p.is_dir()}
	assert carpetas <= distribuible, f"data/ contiene carpetas personales: {carpetas - distribuible}"


def test_rutas_portables(datos_temporales):
	assert paths.ruta_base() == RAIZ
	assert paths.ruta_datos() == datos_temporales
	assert paths.ruta_registros() == datos_temporales / "logs"


def test_bat_crlf_sin_bom():
	datos = (RAIZ / "entorno.bat").read_bytes()
	assert not datos.startswith(b"\xef\xbb\xbf")
	assert b"\n" not in datos.replace(b"\r\n", b"")
	assert f'set "NOMBRE_APP={ID_APLICACION}"'.encode() in datos
