"""La distribución lleva los complementos de los que dependen otros (``comun``), y los textos apuntan a lo real."""

from __future__ import annotations

import json
from pathlib import Path

import setup_cx
from tools import verificar_build

from .conftest import RAIZ


def _complemento(plugins: Path, ident: str, depende_de: list[str] | None = None, sonidos: tuple[str, ...] = ()) -> None:
	carpeta = plugins / ident
	carpeta.mkdir(parents=True)
	(carpeta / "complemento.json").write_text(json.dumps({"id": ident, "depende_de": depende_de or []}), encoding="utf-8")
	for nombre in sonidos:
		(carpeta / "sonidos").mkdir(exist_ok=True)
		(carpeta / "sonidos" / nombre).write_bytes(b"x")


def test_plugins_viaja_entero_con_comun():
	assert "plugins" in setup_cx.DATA_DISTRIBUIBLE, "data/plugins (y con ella data/plugins/comun) viaja en la distribución"
	assert (RAIZ / "data" / "plugins" / "comun" / "complemento.json").is_file()
	assert verificar_build._verificar_dependencias_complementos(RAIZ / "data" / "plugins") == []


def test_verificar_build_detecta_que_falta_comun_o_sus_sonidos(tmp_path):
	plugins = tmp_path / "plugins"
	_complemento(plugins, "hogar", ["comun"])
	problemas = verificar_build._verificar_dependencias_complementos(plugins)
	assert len(problemas) == 1 and "data/plugins/comun" in problemas[0] and "hogar" in problemas[0]
	_complemento(plugins, "comun")
	problemas = verificar_build._verificar_dependencias_complementos(plugins)
	assert len(problemas) == 1 and "sonidos" in problemas[0]
	(plugins / "comun" / "sonidos").mkdir()
	(plugins / "comun" / "sonidos" / "sentarse.flac").write_bytes(b"x")
	assert verificar_build._verificar_dependencias_complementos(plugins) == []


def test_los_ejemplos_citados_existen():
	"""entorno.bat y docs/desarrollo.md ponen de ejemplo un entorno que de verdad viene con el programa."""
	for relativo in ("entorno.bat", "docs/desarrollo.md"):
		texto = (RAIZ / relativo).read_text(encoding="utf-8")
		assert "casa.elab" not in texto, relativo
		assert "vivienda-de-ejemplo.elab" in texto, relativo
	assert (RAIZ / "data" / "ejemplos" / "vivienda-de-ejemplo.elab").is_file()
	contenido = (RAIZ / "entorno.bat").read_bytes()
	assert not contenido.startswith(b"\xef\xbb\xbf") and contenido.count(b"\n") == contenido.count(b"\r\n")


def test_los_textos_nombran_las_ordenes_reales():
	"""«Complementos instalados» con «Comprobar» y «Añadir desde fichero»; Ayuda, «Buscar actualizaciones»."""
	for relativo in ("docs/crear-un-complemento.md", "data/plugins/LEEME.md"):
		texto = (RAIZ / relativo).read_text(encoding="utf-8")
		assert "«Comprobar complemento»" not in texto and "«Añadir complemento»" not in texto, relativo
		assert "Complementos instalados" in texto and "Añadir desde fichero" in texto, relativo
	for relativo in ("docs/actualizaciones.md", "app/ui/dialogo_actualizacion.py"):
		texto = (RAIZ / relativo).read_text(encoding="utf-8")
		assert "Ayuda, Actualizaciones" not in texto, relativo
		assert "Buscar actualizaciones" in texto, relativo
