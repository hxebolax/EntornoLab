"""Pruebas de ``tools/publicar_complemento.py``: lo que publica la herramienta lo acepta la aplicación."""

from __future__ import annotations

import json

import pytest

from app.core import paths, red
from app.services import actualizador
from app.services import complementos_en_linea as cel
from tests._actualizador_util import Claves, cargar_herramienta, escribir_json
from tests.servidor_http_prueba import servidor  # noqa: F401 - fixture
from tests.test_complementos_en_linea_servicio import ficha


@pytest.fixture(scope="module")
def claves(tmp_path_factory) -> Claves:
	return Claves(tmp_path_factory.mktemp("claves"))


@pytest.fixture
def herramienta(claves, monkeypatch):
	monkeypatch.setattr(actualizador, "CLAVES_PUBLICAS_ED25519", (claves.publica,))
	monkeypatch.setattr(red, "ESPERA_INICIAL", 0.01)
	return cargar_herramienta("publicar_complemento")


def _fuente(tmp_path, identificador: str, version: str, extra: dict[str, bytes] | None = None):
	carpeta = tmp_path / "fuentes" / identificador
	carpeta.mkdir(parents=True, exist_ok=True)
	escribir_json(carpeta / "complemento.json", ficha(identificador, version))
	for nombre, contenido in (extra or {}).items():
		ruta = carpeta / nombre
		ruta.parent.mkdir(parents=True, exist_ok=True)
		ruta.write_bytes(contenido)
	return carpeta


def test_publicar_y_que_la_aplicacion_lo_instale(herramienta, claves, tmp_path, servidor):  # noqa: F811
	catalogo = servidor.carpeta  # la carpeta del repositorio del catálogo, servida tal cual
	hogar = _fuente(tmp_path, "hogar", "1.0", {"LEEME.md": b"# Hogar", "instalar.exe": b"MZ no debe viajar", "notas.docx": b"tampoco"})
	(entrada,) = herramienta.publicar([str(hogar)], catalogo, clave=claves.privada)
	assert entrada["id"] == "hogar" and entrada["version"] == "1.0" and entrada["url"] == "paquetes/hogar-1.0.elabc"
	assert entrada["objetos"] == len(ficha()["objetos"]) and entrada["version_minima_app"] == "0.1.0"
	assert {"Dormitorio", "Salón"} <= set(entrada["categorias"]) and "salon" not in entrada[
		"categorias"
	]  # nombres visibles, no identificadores
	assert set(entrada) == {
		"id", "nombre", "descripcion", "autor", "licencia", "version", "version_minima_app",
		"categorias", "objetos", "tamano", "url", "sha256", "fecha",
	}  # fmt: skip
	paquete = catalogo / "paquetes" / "hogar-1.0.elabc"
	assert entrada["tamano"] == paquete.stat().st_size and entrada["sha256"] == actualizador.sha256_de(paquete)
	import zipfile

	with zipfile.ZipFile(paquete) as archivo:
		assert sorted(archivo.namelist()) == ["LEEME.md", "complemento.json"]  # ni el .exe ni el .docx viajan
	indice = json.loads((catalogo / "catalogo.json").read_text(encoding="utf-8"))
	assert (indice["formato"], indice["tipo"], indice["app"], indice["serie"]) == (1, "catalogo-complementos", "EntornoLab", 1)
	assert indice["firma_ed25519"] and indice["generado"]
	# La aplicación lo descarga, verifica la firma y lo instala.
	recibido = cel.descargar_catalogo(servidor.url("catalogo.json"))
	assert list(recibido.complementos) == ["hogar"] and recibido.serie == 1
	assert cel.instalar(recibido.complementos["hogar"]).correcto
	assert (paths.ruta_complementos() / "hogar" / "LEEME.md").is_file()


def test_actualizar_quitar_y_listar(herramienta, claves, tmp_path, capsys):
	catalogo = tmp_path / "repositorio"
	catalogo.mkdir()
	herramienta.publicar([str(_fuente(tmp_path, "hogar", "1.0")), str(_fuente(tmp_path, "ciudad", "1.0"))], catalogo, clave=claves.privada)
	with pytest.raises(herramienta.ErrorPublicacion, match="ya está publicado"):
		herramienta.publicar([str(_fuente(tmp_path, "hogar", "1.0"))], catalogo, clave=claves.privada)
	herramienta.publicar([str(_fuente(tmp_path, "hogar", "1.1"))], catalogo, version_minima="0.2.0", clave=claves.privada)
	indice = herramienta.leer_indice(catalogo)
	assert {entrada["id"]: (entrada["version"], entrada["version_minima_app"]) for entrada in indice["complementos"]} == {
		"ciudad": ("1.0", "0.1.0"),
		"hogar": ("1.1", "0.2.0"),
	}
	assert indice["serie"] == 2
	assert sorted(p.name for p in (catalogo / "paquetes").iterdir()) == ["ciudad-1.0.elabc", "hogar-1.1.elabc"]  # el viejo se retira
	cel.interpretar_indice(indice, "https://ejemplo.invalid/catalogo.json", (claves.publica,))
	assert herramienta.main(["--listar", "--catalogo", str(catalogo)]) == 0
	assert "hogar 1.1" in capsys.readouterr().out
	herramienta.quitar("ciudad", catalogo, clave=claves.privada)
	indice = herramienta.leer_indice(catalogo)
	assert [entrada["id"] for entrada in indice["complementos"]] == ["hogar"] and indice["serie"] == 3
	assert not (catalogo / "paquetes" / "ciudad-1.0.elabc").exists()
	with pytest.raises(herramienta.ErrorPublicacion, match="no está en el catálogo"):
		herramienta.quitar("ciudad", catalogo, clave=claves.privada)


def test_simular_no_escribe_nada(herramienta, claves, tmp_path, capsys):
	catalogo = tmp_path / "repositorio"
	catalogo.mkdir()
	codigo = herramienta.main(
		[str(_fuente(tmp_path, "hogar", "1.0")), "--catalogo", str(catalogo), "--simular", "--clave", str(claves.privada)]
	)
	salida = capsys.readouterr().out
	assert codigo == 0 and "SIMULACIÓN" in salida and "hogar 1.0" in salida
	assert list(catalogo.iterdir()) == []


def test_lo_que_impide_publicar_un_complemento(herramienta, claves, tmp_path, capsys, monkeypatch):
	catalogo = tmp_path / "repositorio"
	catalogo.mkdir()
	error = herramienta.ErrorPublicacion
	with pytest.raises(error, match="No se encuentra el complemento"):
		herramienta.publicar(["no-existe-este-complemento"], catalogo, clave=claves.privada)
	roto = tmp_path / "fuentes" / "roto"
	roto.mkdir(parents=True)
	(roto / "complemento.json").write_text("{esto no es json", encoding="utf-8")
	with pytest.raises(error, match="no es válido"):
		herramienta.publicar([str(roto)], catalogo, clave=claves.privada)
	with pytest.raises(error, match="versiones como"):
		herramienta.publicar([str(_fuente(tmp_path, "raro", "la primera"))], catalogo, clave=claves.privada)
	with pytest.raises(error, match="clave privada"):
		herramienta.publicar([str(_fuente(tmp_path, "hogar", "1.0"))], catalogo, clave=tmp_path / "no.key")
	otra = Claves(tmp_path / "otra")
	with pytest.raises(error, match="NO es ninguna"):
		herramienta.publicar([str(_fuente(tmp_path, "hogar", "1.0"))], catalogo, clave=otra.privada)
	assert not (catalogo / "catalogo.json").exists()
	monkeypatch.delenv(herramienta.VARIABLE_CATALOGO, raising=False)
	assert herramienta.main(["hogar"]) == 1  # sin --catalogo ni variable: error claro, sin tocar nada
	assert herramienta.main([str(roto), "--catalogo", str(tmp_path / "no-existe")]) == 1
	assert "ERROR" in capsys.readouterr().err
