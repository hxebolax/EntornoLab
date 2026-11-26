"""Pruebas de las herramientas de publicación de versiones (en modo simulación: nunca se llama a GitHub)."""

from __future__ import annotations

import json
import subprocess
import zipfile

import pytest

from app.core.version import APP_VERSION
from app.services import actualizador
from tests._actualizador_util import Claves, cargar_herramienta, escribir_json
from tests.servidor_http_prueba import servidor  # noqa: F401 - fixture


@pytest.fixture(scope="module")
def claves(tmp_path_factory) -> Claves:
	return Claves(tmp_path_factory.mktemp("claves"))


@pytest.fixture
def herramienta(claves, monkeypatch):
	"""``tools/publicar_version.py`` con la clave de prueba como la única que acepta la aplicación."""
	monkeypatch.setattr(actualizador, "CLAVES_PUBLICAS_ED25519", (claves.publica,))

	def prohibido(*args, **kwargs):
		raise AssertionError(f"Las pruebas no deben ejecutar órdenes externas: {args}")

	monkeypatch.setattr(subprocess, "run", prohibido)
	return cargar_herramienta("publicar_version")


@pytest.fixture
def compilacion(tmp_path):
	"""Una «compilación» mínima: los dos ejecutables, una biblioteca y dos complementos de serie."""
	origen = tmp_path / "build" / "entornolab"
	ficheros = {
		"EntornoLab.exe": b"ESTUDIO",
		"EntornoLabJugar.exe": b"REPRODUCTOR",
		"lib/modulo.pyd": b"biblioteca",
		"data/docs/manual.md": b"# Manual",
		"data/plugins/hogar/complemento.json": json.dumps({"formato": 1, "id": "hogar", "version": "1.2", "objetos": []}).encode(),
		"data/plugins/ciudad/complemento.json": json.dumps({"formato": 1, "id": "ciudad", "version": "2.0", "objetos": []}).encode(),
		"data/plugins/de_serie.json": b'{"de_serie": {"viejo": "0.1"}}',
	}
	for nombre, contenido in ficheros.items():
		ruta = origen / nombre
		ruta.parent.mkdir(parents=True, exist_ok=True)
		ruta.write_bytes(contenido)
	return origen


def test_preparar_una_version_estable(herramienta, compilacion, claves, tmp_path, servidor):  # noqa: F811
	preparado = herramienta.preparar(
		compilacion,
		tmp_path / "salida",
		"estable",
		version="1.1.0",
		clave=claves.privada,
		notas="- Catálogo en línea.",
		verificar_compilacion=False,
	)
	manifiesto = json.loads(preparado["json"].read_text(encoding="utf-8"))
	assert manifiesto == preparado["manifiesto"]
	assert manifiesto["app"] == "EntornoLab" and manifiesto["canal"] == "estable" and manifiesto["version"] == "1.1.0"
	assert manifiesto["file"] == "EntornoLab_v1.1.0.zip" and manifiesto["size"] == preparado["zip"].stat().st_size
	assert manifiesto["sha256"] == actualizador.sha256_de(preparado["zip"])
	assert manifiesto["url"] == "https://github.com/hxebolax/EntornoLab/releases/download/v1.1.0/EntornoLab_v1.1.0.zip"
	assert manifiesto["novedades"] == "- Catálogo en línea."
	assert "Catálogo en línea" in preparado["notas"].read_text(encoding="utf-8")
	with zipfile.ZipFile(preparado["zip"]) as paquete:
		nombres = paquete.namelist()
		assert all(nombre.startswith("EntornoLab/") for nombre in nombres)
		assert nombres.count("EntornoLab/data/plugins/de_serie.json") == 1
		assert json.loads(paquete.read("EntornoLab/data/plugins/de_serie.json")) == {"de_serie": {"ciudad": "2.0", "hogar": "1.2"}}
	# La aplicación acepta lo que genera la herramienta: firma, campos y contenido.
	escribir_json(servidor.carpeta / "version.json", manifiesto)
	(tmp_path / "instalada" / "data").mkdir(parents=True)
	config = actualizador.Configuracion(
		version_actual="1.0.0",
		carpeta_app=tmp_path / "instalada",
		url_estable=servidor.url("version.json"),
		claves_publicas=(claves.publica,),
		comando=["x"],
	)
	info = actualizador.comprobar(config)
	assert info.version == "1.1.0" and info.url_zip == manifiesto["url"]
	actualizador.verificar_paquete(preparado["zip"], info)
	destino = actualizador.extraer_seguro(preparado["zip"], tmp_path / "extraido", config)
	assert (destino / "programa" / "EntornoLabJugar.exe").read_bytes() == b"REPRODUCTOR"
	assert (destino / "recursos" / "plugins" / "hogar" / "complemento.json").is_file()
	assert herramienta.firmar_version.verificar(preparado["json"], [claves.publica]) == []


def test_ordenes_de_github(herramienta, compilacion, claves, tmp_path):
	estable = herramienta.preparar(
		compilacion, tmp_path / "e", "estable", version="1.1.0", clave=claves.privada, notas="x", verificar_compilacion=False
	)
	(orden,) = herramienta.ordenes_gh(estable)
	assert orden[:4] == ["gh", "release", "create", "v1.1.0"]
	assert str(estable["zip"]) in orden and str(estable["json"]) in orden
	assert orden[orden.index("--repo") + 1] == "hxebolax/EntornoLab" and "--latest" in orden and "--prerelease" not in orden
	pruebas = herramienta.preparar(
		compilacion, tmp_path / "p", "pruebas", version="1.2.0-beta.1", clave=claves.privada, notas="x", verificar_compilacion=False
	)
	assert pruebas["manifiesto"]["canal"] == "pruebas"
	assert pruebas["manifiesto"]["url"] == "https://github.com/hxebolax/EntornoLab/releases/download/pruebas/EntornoLab_v1.2.0-beta.1.zip"
	(crear,) = herramienta.ordenes_gh(pruebas, existe_pruebas=False)
	assert crear[:4] == ["gh", "release", "create", "pruebas"] and "--prerelease" in crear and "--latest" not in crear
	subir, editar = herramienta.ordenes_gh(pruebas, existe_pruebas=True)
	assert subir[:4] == ["gh", "release", "upload", "pruebas"] and "--clobber" in subir
	assert editar[:4] == ["gh", "release", "edit", "pruebas"]
	# Sin --subir solo se explica: no se ejecuta nada (subprocess.run está prohibido en esta prueba).
	assert herramienta.publicar(estable, subir=False) == 0


def test_lo_que_impide_publicar(herramienta, compilacion, claves, tmp_path):
	error = herramienta.ErrorPublicacion
	opciones = {"clave": claves.privada, "notas": "x", "verificar_compilacion": False}
	with pytest.raises(error, match="preliminar"):
		herramienta.preparar(compilacion, tmp_path / "s", "estable", version="1.2.0-beta.1", **opciones)
	with pytest.raises(error, match="Canal"):
		herramienta.preparar(compilacion, tmp_path / "s", "nocturno", version="1.1.0", **opciones)
	with pytest.raises(error, match="clave privada"):
		herramienta.preparar(
			compilacion, tmp_path / "s", version="1.1.0", clave=tmp_path / "no-existe.key", notas="x", verificar_compilacion=False
		)
	with pytest.raises(error, match="no tiene notas"):
		herramienta.preparar(compilacion, tmp_path / "s", version="99.99.99", clave=claves.privada, verificar_compilacion=False)
	# Firmado con una clave que la aplicación no lleva: las instalaciones lo rechazarían.
	otra = Claves(tmp_path / "otra")
	with pytest.raises(error, match="NO es ninguna"):
		herramienta.preparar(compilacion, tmp_path / "s", version="1.1.0", clave=otra.privada, notas="x", verificar_compilacion=False)
	assert not list((tmp_path / "s").glob("*.zip"))
	(compilacion / "EntornoLabJugar.exe").unlink()
	with pytest.raises(error, match="EntornoLabJugar"):
		herramienta.preparar(compilacion, tmp_path / "s", version="1.1.0", **opciones)


def test_modo_simulacion_no_deja_nada_ni_llama_a_github(herramienta, compilacion, claves, tmp_path, capsys):
	salida = tmp_path / "publicar"
	codigo = herramienta.main(
		["--simular", "--subir", "--sin-verificar", "--origen", str(compilacion), "--salida", str(salida), "--clave", str(claves.privada)]
	)
	texto = capsys.readouterr()
	assert codigo == 0, texto.err
	assert "SIMULACIÓN" in texto.out
	assert f"gh release create v{APP_VERSION}" in texto.out and "--repo hxebolax/EntornoLab" in texto.out
	assert not salida.exists()


def test_firmar_y_verificar_por_linea_de_ordenes(claves, tmp_path, capsys):
	firmador = cargar_herramienta("firmar_version")
	(tmp_path / "EntornoLab_v1.1.0.zip").write_bytes(b"contenido del paquete")
	import hashlib

	escribir_json(
		tmp_path / "version.json",
		{"version": "1.1.0", "file": "EntornoLab_v1.1.0.zip", "sha256": hashlib.sha256(b"contenido del paquete").hexdigest(), "size": 21},
	)
	(tmp_path / "notas.md").write_text("- Novedad.", encoding="utf-8")
	assert (
		firmador.main(["firmar", str(tmp_path / "version.json"), "--clave", str(claves.privada), "--novedades", str(tmp_path / "notas.md")])
		== 0
	)
	manifiesto = json.loads((tmp_path / "version.json").read_text(encoding="utf-8"))
	assert manifiesto["novedades"] == "- Novedad."
	actualizador.verificar_firma(manifiesto, (claves.publica,))
	assert firmador.main(["verificar", str(tmp_path / "version.json"), "--publica", claves.publica]) == 0
	assert firmador.main(["verificar", str(tmp_path / "version.json"), "--clave", str(claves.privada)]) == 0
	(tmp_path / "EntornoLab_v1.1.0.zip").write_bytes(b"contenido cambiado!!!")
	assert firmador.main(["verificar", str(tmp_path / "version.json"), "--publica", claves.publica]) == 1
	assert "SHA-256" in capsys.readouterr().out
	escribir_json(tmp_path / "incompleto.json", {"version": "1.1.0"})
	assert firmador.main(["firmar", str(tmp_path / "incompleto.json"), "--clave", str(claves.privada)]) == 1


def test_la_clave_privada_se_busca_fuera_del_proyecto(monkeypatch, tmp_path):
	firmador = cargar_herramienta("firmar_version")
	monkeypatch.setenv(firmador.VARIABLE_CLAVES, str(tmp_path / "mis claves"))
	assert firmador.ruta_clave_privada() == tmp_path / "mis claves" / "firma_ed25519.key"
	monkeypatch.delenv(firmador.VARIABLE_CLAVES)
	assert ".entornolab" in firmador.ruta_clave_privada().parts
	assert not firmador.esta_dentro_del_proyecto(firmador.ruta_clave_privada())
