"""Pruebas del catálogo en línea de complementos contra un servidor local (sin Internet)."""

from __future__ import annotations

import copy
import json
import stat
import threading
import zipfile
from dataclasses import dataclass

import pytest

from app.core import paths, red
from app.core.configuracion import obtener_configuracion
from app.services import actualizador
from app.services import complementos_en_linea as cel
from tests._actualizador_util import Claves, crear_elabc, entrada_catalogo, escribir_json, publicar_catalogo
from tests.servidor_http_prueba import servidor  # noqa: F401 - fixture
from tests.test_dominio_comun import FICHA_PRUEBA


@dataclass
class AvisoFalso:
	gravedad: str
	mensaje: str


def ficha(identificador: str = "prueba", version: str = "1.0", **cambios) -> dict:
	datos = copy.deepcopy(FICHA_PRUEBA)
	datos.update({"id": identificador, "version": version, "nombre": f"Complemento {identificador}"})
	datos.update(cambios)
	return datos


@pytest.fixture(scope="module")
def claves(tmp_path_factory) -> Claves:
	return Claves(tmp_path_factory.mktemp("claves"))


@pytest.fixture(autouse=True)
def _entorno(monkeypatch, claves):
	monkeypatch.setattr(red, "TIEMPO_ESPERA", 5.0)
	monkeypatch.setattr(red, "ESPERA_INICIAL", 0.01)
	# La aplicación solo se fía de su clave: en las pruebas, la de prueba.
	monkeypatch.setattr(actualizador, "CLAVES_PUBLICAS_ED25519", (claves.publica,))


class Tienda:
	"""Un catálogo publicado en el servidor de pruebas."""

	def __init__(self, servidor, claves: Claves) -> None:  # noqa: F811
		self.servidor = servidor
		self.claves = claves
		self.entradas: dict[str, dict] = {}
		self.serie = 0

	@property
	def url(self) -> str:
		return self.servidor.url("catalogo.json")

	def publicar(self, datos: dict, extra: dict[str, bytes] | None = None, **cambios) -> dict:
		paquete = crear_elabc(self.servidor.carpeta / "paquetes" / f"{datos['id']}-{datos['version']}.elabc", datos, extra)
		self.entradas[datos["id"]] = entrada_catalogo(paquete, datos, **cambios)
		return self.firmar()

	def firmar(self, claves: Claves | None = None, sin_firma: bool = False, extra: dict | None = None) -> dict:
		self.serie += 1
		return publicar_catalogo(
			self.servidor.carpeta,
			list(self.entradas.values()),
			None if sin_firma else (claves or self.claves),
			serie=self.serie,
			extra=extra,
		)

	def indice(self) -> cel.Indice:
		return cel.descargar_catalogo(self.url)


@pytest.fixture
def tienda(servidor, claves) -> Tienda:  # noqa: F811
	return Tienda(servidor, claves)


def _version_instalada(identificador: str) -> str:
	return json.loads((paths.ruta_complementos() / identificador / "complemento.json").read_text(encoding="utf-8"))["version"]


def _estados(indice) -> dict[str, str]:
	return {fila.id: fila.estado for fila in cel.comparar(indice)}


# ── Índice ───────────────────────────────────────────────────────────────────


def test_direccion_oficial_y_personalizada():
	assert cel.url_catalogo() == "https://raw.githubusercontent.com/hxebolax/EntornoLab-complementos/main/catalogo.json"
	red.comprobar_url(cel.URL_CATALOGO)
	obtener_configuracion().establecer("complementos.url_catalogo", "https://espejo.invalid/catalogo.json")
	assert cel.url_catalogo() == "https://espejo.invalid/catalogo.json"
	assert cel.comprobar_con_la_aplicacion() is True


def test_descargar_catalogo(tienda):
	tienda.publicar(ficha("mobiliario", "1.2"))
	indice = tienda.indice()
	assert list(indice.complementos) == ["mobiliario"]
	complemento = indice.complementos["mobiliario"]
	assert complemento.version == "1.2"
	assert complemento.nombre == "Complemento mobiliario"
	assert complemento.autor == "Pruebas" and complemento.licencia == "CC0"
	assert complemento.objetos == len(FICHA_PRUEBA["objetos"])
	assert set(complemento.categorias) >= {"dormitorio", "salon"}
	assert complemento.url == tienda.servidor.url("paquetes/mobiliario-1.2.elabc")  # relativa al índice
	assert complemento.tamano > 0 and len(complemento.sha256) == 64
	assert complemento.fecha == "2026-11-26"
	assert indice.serie == 1


def test_catalogo_sin_firma_con_firma_mala_o_de_otra_clave(tienda, tmp_path):
	tienda.publicar(ficha())
	tienda.firmar(sin_firma=True)
	with pytest.raises(cel.ErrorCatalogo):
		tienda.indice()
	tienda.firmar(claves=Claves(tmp_path / "intruso"))
	with pytest.raises(cel.ErrorCatalogo):
		tienda.indice()
	# Firmado y después manipulado: alguien cambia la dirección de descarga.
	indice = tienda.firmar()
	indice["complementos"][0]["url"] = "https://malo.invalid/prueba.elabc"
	escribir_json(tienda.servidor.carpeta / "catalogo.json", indice)
	with pytest.raises(cel.ErrorCatalogo):
		tienda.indice()


def test_un_version_json_firmado_no_vale_como_catalogo(tienda, claves):
	escribir_json(
		tienda.servidor.carpeta / "catalogo.json",
		claves.firmar({"app": "EntornoLab", "version": "9.9", "file": "a.zip", "sha256": "0" * 64, "size": 1, "complementos": []}),
	)
	with pytest.raises(cel.ErrorCatalogo):
		tienda.indice()
	tienda.firmar(extra={"formato": 99})
	with pytest.raises(cel.ErrorCatalogo, match="formato"):
		tienda.indice()


def test_catalogo_no_disponible(tienda):
	with pytest.raises(cel.ErrorCatalogo) as error:
		tienda.indice()
	assert "404" in str(error.value)
	tienda.publicar(ficha())
	tienda.servidor.fallos["catalogo.json"] = [(503, {})] * 5
	with pytest.raises(cel.ErrorCatalogo) as error:
		tienda.indice()
	assert error.value.reintentar


def test_una_entrada_mal_formada_no_tira_el_catalogo(tienda):
	tienda.publicar(ficha("bueno"))
	for identificador, cambios in (
		("malo-sha", {"sha256": "xyz"}),
		("malo-url", {"url": "http://ejemplo.invalid/a.elabc"}),
		("malo-tamano", {"tamano": -1}),
		("malo-version", {"version": "la última"}),
		("MALO ID", {}),
	):
		tienda.entradas[identificador] = {**tienda.entradas["bueno"], "id": identificador, **cambios}
	tienda.firmar()
	assert list(tienda.indice().complementos) == ["bueno"]


def test_no_se_acepta_un_catalogo_mas_antiguo_que_el_ya_visto(tienda):
	tienda.publicar(ficha("a"))
	viejo = (tienda.servidor.carpeta / "catalogo.json").read_bytes()
	tienda.publicar(ficha("b"))
	assert tienda.indice().serie == 2
	(tienda.servidor.carpeta / "catalogo.json").write_bytes(viejo)  # firma válida, pero retirado
	with pytest.raises(cel.ErrorCatalogo, match="antiguo"):
		tienda.indice()


# ── Estados ──────────────────────────────────────────────────────────────────


def test_estados_del_catalogo_frente_a_lo_instalado(tienda):
	for identificador, version in (("al-dia", "1.0"), ("viejo", "1.0"), ("solo-local", "1.0"), ("adelantado", "3.0")):
		carpeta = paths.ruta_complementos() / identificador
		carpeta.mkdir(parents=True)
		escribir_json(carpeta / "complemento.json", ficha(identificador, version))
	tienda.publicar(ficha("al-dia", "1.0"))
	tienda.publicar(ficha("viejo", "1.1"))
	tienda.publicar(ficha("adelantado", "2.0"))
	tienda.publicar(ficha("nuevo", "1.0"))
	tienda.publicar(ficha("futuro", "1.0"), version_minima_app="99.0")
	indice = tienda.indice()
	assert _estados(indice) == {
		"al-dia": cel.AL_DIA,
		"viejo": cel.ACTUALIZABLE,
		"solo-local": cel.SOLO_LOCAL,
		"adelantado": cel.AL_DIA,
		"nuevo": cel.NUEVO,
		"futuro": cel.REQUIERE_APP,
	}
	filas = {fila.id: fila for fila in cel.comparar(indice)}
	assert (filas["viejo"].version_instalada, filas["viejo"].version_disponible) == ("1.0", "1.1")
	assert filas["nuevo"].instalable and not filas["nuevo"].actualizable and not filas["nuevo"].desinstalable
	assert filas["viejo"].actualizable and filas["viejo"].tamano > 0
	assert filas["solo-local"].version_disponible == "" and filas["solo-local"].tamano == 0
	assert [c.id for c in cel.actualizables(filas.values())] == ["viejo"]
	assert all(cel.nombre_estado(fila.estado) for fila in filas.values())
	# Sin conexión (sin índice) se sigue viendo lo instalado.
	assert set(_estados(None).values()) == {cel.SOLO_LOCAL}


def test_de_serie_y_del_usuario(tienda):
	for identificador in ("mobiliario", "ciudad", "manual"):
		carpeta = paths.ruta_complementos() / identificador
		carpeta.mkdir(parents=True)
		escribir_json(carpeta / "complemento.json", ficha(identificador, "1.0"))
	# Sin lista (desde el código fuente): es de serie lo que no instaló el usuario.
	assert {c.id: c.origen for c in cel.instalados().values()} == {"mobiliario": "serie", "ciudad": "serie", "manual": "serie"}
	# Con la lista que viaja en el ZIP de la versión, lo que no está en ella es del usuario.
	escribir_json(paths.ruta_complementos() / "de_serie.json", {"de_serie": {"mobiliario": "1.0", "ciudad": "1.0"}})
	locales = cel.instalados()
	assert {c.id: (c.origen, c.de_serie) for c in locales.values()} == {
		"mobiliario": ("serie", True),
		"ciudad": ("serie", True),
		"manual": ("manual", False),
	}
	with pytest.raises(cel.ErrorComplementoEnLinea, match="viene con la aplicación"):
		cel.desinstalar("mobiliario")
	cel.desinstalar("manual")
	assert "manual" not in cel.instalados()
	with pytest.raises(cel.ErrorComplementoEnLinea, match="no está instalado"):
		cel.desinstalar("manual")
	with pytest.raises(cel.ErrorComplementoEnLinea):
		cel.desinstalar("../config")


# ── Instalar y actualizar (con el instalador y el validador reales) ──────────


def test_instalar_un_complemento_nuevo(tienda):
	tienda.publicar(ficha("mobiliario", "1.0"), {"sonidos/golpe.wav": b"RIFF....WAVE", "LEEME.txt": b"hola"})
	indice = tienda.indice()
	avances: list[tuple[int, int]] = []
	resultado = cel.instalar(indice.complementos["mobiliario"], al_progresar=lambda hecho, total: avances.append((hecho, total)))
	assert resultado.correcto and (resultado.id, resultado.version, resultado.version_anterior) == ("mobiliario", "1.0", "")
	carpeta = paths.ruta_complementos() / "mobiliario"
	assert (carpeta / "sonidos" / "golpe.wav").read_bytes() == b"RIFF....WAVE"
	assert avances and avances[-1][0] == avances[-1][1] == indice.complementos["mobiliario"].tamano
	assert _estados(indice) == {"mobiliario": cel.AL_DIA}
	local = cel.instalados()["mobiliario"]
	assert (local.origen, local.de_serie, local.version) == ("catalogo", False, "1.0")
	registro = cel.leer_registro()["instalados"]["mobiliario"]
	assert registro["version"] == "1.0" and registro["origen"] == "catalogo"
	assert not list((paths.ruta_temporales() / "complementos").iterdir())  # el paquete descargado se borra
	assert not cel.hay_anterior("mobiliario")
	# El catálogo de la aplicación lo carga de verdad.
	from app.dominio.catalogo import Catalogo

	assert Catalogo.cargar().objeto("mobiliario/cama") is not None


def test_actualizar_y_volver_a_la_version_anterior(tienda):
	tienda.publicar(ficha("mobiliario", "1.0"), {"sonidos/viejo.wav": b"v1"})
	cel.instalar(tienda.indice().complementos["mobiliario"])
	tienda.publicar(ficha("mobiliario", "1.1"), {"sonidos/nuevo.wav": b"v2"})
	indice = tienda.indice()
	assert _estados(indice) == {"mobiliario": cel.ACTUALIZABLE}
	resultado = cel.instalar(indice.complementos["mobiliario"])
	assert (resultado.version, resultado.version_anterior) == ("1.1", "1.0")
	carpeta = paths.ruta_complementos() / "mobiliario"
	assert _version_instalada("mobiliario") == "1.1"
	assert (carpeta / "sonidos" / "nuevo.wav").is_file() and not (carpeta / "sonidos" / "viejo.wav").exists()
	fila = cel.comparar(indice)[0]
	assert fila.estado == cel.AL_DIA and fila.hay_anterior
	assert cel.volver_a_anterior("mobiliario") == "1.0"
	assert _version_instalada("mobiliario") == "1.0"
	assert (carpeta / "sonidos" / "viejo.wav").read_bytes() == b"v1"
	assert not cel.hay_anterior("mobiliario")
	assert cel.leer_registro()["instalados"]["mobiliario"]["version"] == "1.0"
	assert _estados(indice) == {"mobiliario": cel.ACTUALIZABLE}  # se puede volver a actualizar
	with pytest.raises(cel.ErrorComplementoEnLinea, match="ninguna versión anterior"):
		cel.volver_a_anterior("mobiliario")


def test_un_complemento_de_serie_se_actualiza_por_el_catalogo_y_vuelve_a_como_vino(tienda):
	carpeta = paths.ruta_complementos() / "mobiliario"
	carpeta.mkdir(parents=True)
	escribir_json(carpeta / "complemento.json", ficha("mobiliario", "1.0"))
	escribir_json(paths.ruta_complementos() / "de_serie.json", {"de_serie": {"mobiliario": "1.0"}})
	tienda.publicar(ficha("mobiliario", "2.0"))
	cel.instalar(tienda.indice().complementos["mobiliario"])
	local = cel.instalados()["mobiliario"]
	assert (local.version, local.de_serie, local.origen) == ("2.0", True, "catalogo")
	# Al actualizar la aplicación, el actualizador lo trata como del usuario y no lo pisa con uno más viejo.
	assert actualizador.complementos_del_usuario(paths.ruta_datos()) == {"mobiliario"}
	with pytest.raises(cel.ErrorComplementoEnLinea, match="viene con la aplicación"):
		cel.desinstalar("mobiliario")
	assert cel.volver_a_anterior("mobiliario") == "1.0"
	assert cel.leer_registro()["instalados"] == {}  # vuelve a ser «tal como vino»
	assert cel.instalados()["mobiliario"].origen == "serie"


def test_desinstalar_un_complemento_del_usuario(tienda):
	tienda.publicar(ficha("extra", "1.0"))
	tienda.publicar(ficha("extra", "1.1"))
	escribir_json(paths.ruta_complementos() / "de_serie.json", {"de_serie": {}})
	cel.instalar(cel.ComplementoEnLinea(**{**tienda.indice().complementos["extra"].__dict__}))
	assert cel.comparar(tienda.indice())[0].desinstalable
	cel.desinstalar("extra")
	assert not (paths.ruta_complementos() / "extra").exists()
	assert cel.leer_registro()["instalados"] == {}
	assert _estados(tienda.indice()) == {"extra": cel.NUEVO}


def test_version_minima_de_la_aplicacion(tienda):
	tienda.publicar(ficha("futuro", "1.0"), version_minima_app="2.0.0")
	complemento = tienda.indice().complementos["futuro"]
	with pytest.raises(cel.ErrorComplementoEnLinea, match=r"2\.0\.0"):
		cel.instalar(complemento, version_app="1.5.0")
	assert tienda.servidor.veces("paquetes/futuro-1.0.elabc") == 0
	assert cel.instalar(complemento, version_app="2.0.0").correcto


# ── Verificación y paquetes maliciosos ───────────────────────────────────────


def test_sha_malo_no_se_instala(tienda):
	tienda.publicar(ficha("mobiliario", "1.0"))
	indice = tienda.indice()
	# El paquete del servidor cambia después de firmarse el índice.
	crear_elabc(tienda.servidor.carpeta / "paquetes" / "mobiliario-1.0.elabc", ficha("mobiliario", "1.0", descripcion="Otro contenido"))
	with pytest.raises(cel.ErrorPaqueteComplemento, match="no coincide"):
		cel.instalar(indice.complementos["mobiliario"])
	assert not (paths.ruta_complementos() / "mobiliario").exists()
	assert cel.leer_registro()["instalados"] == {}


@pytest.mark.parametrize(
	("extra", "fragmento"),
	[
		({"instalar.exe": b"MZ\x90\x00"}, "programa o un guion"),
		({"sonidos/ayuda.dll": b"MZ"}, "programa o un guion"),
		({"guion.py": b"import os"}, "programa o un guion"),
		({"arranque.bat": b"@echo off"}, "programa o un guion"),
		({"macro.ps1": b"Remove-Item"}, "programa o un guion"),
		({"imagenes/dibujo.svg": b"<svg onload='x()'/>"}, "programa o un guion"),
		({"imagenes/foto.png": b"MZ\x90\x00\x03 esto es un .exe renombrado"}, "disfrazado"),
		({"sonidos/paso.wav": b"#!/bin/sh\nrm -rf /"}, "disfrazado"),
		({"datos.bin": b"\x00\x01"}, "tipo de fichero"),
		({"sin_extension": b"hola"}, "tipo de fichero"),
		({"../fuera.json": b"{}"}, "fuera de su carpeta"),
		({"sonidos/../../fuera.wav": b"RIFF"}, "fuera de su carpeta"),
		({"/absoluta.json": b"{}"}, "ruta absoluta"),
		({"C:/Windows/x.json": b"{}"}, "ruta absoluta"),
		({"sonidos/CON.wav": b"RIFF"}, "reservado"),
	],
)
def test_paquete_malicioso_se_rechaza(tienda, extra, fragmento):
	tienda.publicar(ficha("mobiliario", "1.0"), extra)
	with pytest.raises(cel.ErrorPaqueteComplemento, match=fragmento):
		cel.instalar(tienda.indice().complementos["mobiliario"])
	assert not (paths.ruta_complementos() / "mobiliario").exists()
	assert not (paths.ruta_datos().parent / "fuera.json").exists()
	assert cel.leer_registro()["instalados"] == {}
	assert not list((paths.ruta_temporales() / "complementos").iterdir())


def test_paquete_con_enlace_o_cifrado_se_rechaza(tmp_path):
	ruta = tmp_path / "enlace.elabc"
	with zipfile.ZipFile(ruta, "w") as archivo:
		archivo.writestr("complemento.json", json.dumps(ficha()))
		enlace = zipfile.ZipInfo("sonidos/enlace.wav")
		enlace.external_attr = (stat.S_IFLNK | 0o777) << 16
		archivo.writestr(enlace, "C:/Windows/System32")
	with pytest.raises(cel.ErrorPaqueteComplemento, match="enlaces"):
		cel.revisar_paquete(ruta)
	(tmp_path / "roto.elabc").write_bytes(b"esto no es un zip")
	with pytest.raises(cel.ErrorPaqueteComplemento, match="dañado"):
		cel.revisar_paquete(tmp_path / "roto.elabc")


def test_paquete_de_otro_complemento_o_sin_ficha_se_rechaza(tienda, tmp_path):
	"""El índice dice «mobiliario», pero el paquete instalaría (y pisaría) «ciudad»."""
	tienda.publicar(ficha("mobiliario", "1.0"))
	crear_elabc(tienda.servidor.carpeta / "paquetes" / "mobiliario-1.0.elabc", ficha("ciudad", "9.0"))
	paquete = tienda.servidor.carpeta / "paquetes" / "mobiliario-1.0.elabc"
	tienda.entradas["mobiliario"] = entrada_catalogo(paquete, ficha("mobiliario", "1.0"))
	tienda.firmar()
	with pytest.raises(cel.ErrorPaqueteComplemento, match="ciudad"):
		cel.instalar(tienda.indice().complementos["mobiliario"])
	assert not (paths.ruta_complementos() / "ciudad").exists()
	with zipfile.ZipFile(tmp_path / "sin_ficha.elabc", "w") as archivo:
		archivo.writestr("LEEME.txt", "nada")
	with pytest.raises(cel.ErrorPaqueteComplemento, match="ficha"):
		cel.revisar_paquete(tmp_path / "sin_ficha.elabc")
	assert cel.revisar_paquete(crear_elabc(tmp_path / "bueno.elabc", ficha("bueno"), prefijo="bueno/")) == "bueno"


# ── Vuelta atrás ─────────────────────────────────────────────────────────────


def test_si_la_version_nueva_no_valida_se_vuelve_a_la_anterior(tienda):
	tienda.publicar(ficha("mobiliario", "1.0"), {"sonidos/viejo.wav": b"v1"})
	cel.instalar(tienda.indice().complementos["mobiliario"])
	tienda.publicar(ficha("mobiliario", "2.0"), {"sonidos/nuevo.wav": b"v2"})
	indice = tienda.indice()

	def validador(carpeta):
		assert json.loads((carpeta / "complemento.json").read_text(encoding="utf-8"))["version"] == "2.0"
		return [AvisoFalso("aviso", "le falta una descripción"), AvisoFalso("error", "la medida del armario es imposible")]

	with pytest.raises(cel.ErrorValidacionComplemento) as error:
		cel.instalar(indice.complementos["mobiliario"], validador=validador)
	assert "se ha vuelto a la 1.0" in str(error.value) and "armario" in str(error.value)
	assert [aviso.gravedad for aviso in error.value.avisos] == ["error"]
	carpeta = paths.ruta_complementos() / "mobiliario"
	assert _version_instalada("mobiliario") == "1.0"
	assert (carpeta / "sonidos" / "viejo.wav").read_bytes() == b"v1" and not (carpeta / "sonidos" / "nuevo.wav").exists()
	assert cel.leer_registro()["instalados"]["mobiliario"]["version"] == "1.0"
	assert not cel.hay_anterior("mobiliario")  # no queda una «anterior» igual a la instalada
	assert _estados(indice) == {"mobiliario": cel.ACTUALIZABLE}


def test_un_complemento_nuevo_que_no_valida_no_queda_instalado(tienda):
	tienda.publicar(ficha("raro", "1.0"))
	with pytest.raises(cel.ErrorValidacionComplemento, match="no se ha instalado"):
		cel.instalar(tienda.indice().complementos["raro"], validador=lambda carpeta: [AvisoFalso("error", "no vale")])
	assert not (paths.ruta_complementos() / "raro").exists()
	assert cel.leer_registro()["instalados"] == {}


def test_los_avisos_que_no_son_errores_no_impiden_instalar(tienda):
	tienda.publicar(ficha("mobiliario", "1.0"))
	resultado = cel.instalar(tienda.indice().complementos["mobiliario"], validador=lambda carpeta: [AvisoFalso("aviso", "mejorable")])
	assert resultado.correcto and len(resultado.avisos) == 1


def test_si_el_instalador_falla_queda_la_version_anterior(tienda):
	tienda.publicar(ficha("mobiliario", "1.0"))
	cel.instalar(tienda.indice().complementos["mobiliario"])
	tienda.publicar(ficha("mobiliario", "2.0"))

	def instalador_roto(ruta_zip):
		# Estropea la carpeta a medias y falla, como un disco lleno.
		(paths.ruta_complementos() / "mobiliario" / "complemento.json").write_text("{a medias", encoding="utf-8")
		raise OSError("disco lleno")

	with pytest.raises(cel.ErrorComplementoEnLinea, match="disco lleno"):
		cel.instalar(tienda.indice().complementos["mobiliario"], instalador=instalador_roto)
	assert _version_instalada("mobiliario") == "1.0"
	with pytest.raises(cel.ErrorPaqueteComplemento, match="no corresponde"):
		cel.instalar(tienda.indice().complementos["mobiliario"], instalador=lambda ruta_zip: "otro")
	assert _version_instalada("mobiliario") == "1.0"


def test_el_instalador_recibe_el_paquete_verificado(tienda):
	tienda.publicar(ficha("mobiliario", "1.0"))
	complemento = tienda.indice().complementos["mobiliario"]
	recibidos: list[str] = []

	def instalador(ruta_zip):
		recibidos.append(actualizador.sha256_de(ruta_zip))
		from app.dominio.catalogo import instalar_complemento

		return instalar_complemento(ruta_zip)

	cel.instalar(complemento, instalador=instalador, validador=lambda carpeta: [])
	assert recibidos == [complemento.sha256]


# ── Red ──────────────────────────────────────────────────────────────────────


def test_descarga_cortada_y_reanudada(tienda):
	tienda.publicar(ficha("grande", "1.0"), {"sonidos/largo.wav": b"RIFF" + bytes(range(256)) * 3000})
	complemento = tienda.indice().complementos["grande"]
	nombre = "paquetes/grande-1.0.elabc"
	tienda.servidor.cortar(nombre, 2000)
	with pytest.raises(cel.ErrorCatalogo) as error:
		cel.instalar(complemento)
	assert error.value.reintentar
	assert not (paths.ruta_complementos() / "grande").exists()
	assert cel.instalar(complemento).correcto
	cabeceras = {clave.lower(): valor for clave, valor in tienda.servidor.cabeceras_de(nombre)[-1].items()}
	assert cabeceras["range"].startswith("bytes=") and cabeceras["range"] != "bytes=0-"
	assert _version_instalada("grande") == "1.0"


def test_cancelar(tienda):
	tienda.publicar(ficha("a", "1.0"))
	tienda.publicar(ficha("b", "1.0"))
	indice = tienda.indice()
	cancelar = threading.Event()
	cancelar.set()
	with pytest.raises(cel.OperacionCancelada):
		cel.instalar(indice.complementos["a"], cancelacion=cancelar)
	resultados = cel.instalar_varios(indice.complementos.values(), cancelacion=cancelar)
	assert [resultado.cancelado for resultado in resultados] == [True, True]
	assert cel.instalados() == {}


def test_instalar_varios_sigue_aunque_uno_falle(tienda):
	for identificador in ("a", "b", "c"):
		carpeta = paths.ruta_complementos() / identificador
		carpeta.mkdir(parents=True)
		escribir_json(carpeta / "complemento.json", ficha(identificador, "1.0"))
		tienda.publicar(ficha(identificador, "1.1"))
	indice = tienda.indice()
	crear_elabc(tienda.servidor.carpeta / "paquetes" / "b-1.1.elabc", ficha("b", "1.1", descripcion="manipulado"))
	pasos: list[tuple[int, int, str]] = []
	resultados = cel.instalar_varios(
		cel.actualizables(cel.comparar(indice)), al_progresar=lambda i, n, c, hecho, total: pasos.append((i, n, c.id))
	)
	assert [(r.id, r.correcto) for r in resultados] == [("a", True), ("b", False), ("c", True)]
	assert "no coincide" in resultados[1].error
	assert {identificador: _version_instalada(identificador) for identificador in "abc"} == {"a": "1.1", "b": "1.0", "c": "1.1"}
	assert {paso[:2] for paso in pasos} >= {(1, 3), (3, 3)}
	assert _estados(indice) == {"a": cel.AL_DIA, "b": cel.ACTUALIZABLE, "c": cel.AL_DIA}


def test_las_peticiones_no_llevan_ningun_dato_del_usuario(tienda):
	tienda.publicar(ficha("mobiliario", "1.0"))
	cel.instalar(tienda.indice().complementos["mobiliario"])
	for nombre, cabeceras in tienda.servidor.peticiones:
		claves_enviadas = {clave.lower() for clave in cabeceras}
		assert claves_enviadas <= {"user-agent", "accept", "accept-encoding", "cache-control", "host", "connection", "range", "if-range"}, (
			nombre
		)
		assert cabeceras.get("User-Agent", "").startswith("EntornoLab/")
		assert "?" not in nombre
