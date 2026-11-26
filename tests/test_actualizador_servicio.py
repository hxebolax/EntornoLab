"""Pruebas del actualizador: versiones, firma, comprobación, descarga y extracción segura.

Todo contra un servidor HTTP local y con claves de prueba; ninguna petición
sale del equipo y nunca se usa la clave privada real.
"""

from __future__ import annotations

import json
import stat
import threading
import zipfile
from datetime import datetime, timedelta, timezone

import pytest

from app.core import red
from app.core.configuracion import obtener_configuracion
from app.services import actualizador
from tests._actualizador_util import Claves, cargar_herramienta, crear_zip, escribir_json, publicar_version
from tests.servidor_http_prueba import servidor  # noqa: F401 - fixture

ARCHIVOS = {
	"EntornoLab.exe": b"EXE estudio 1.1.0",
	"EntornoLabJugar.exe": b"EXE reproductor 1.1.0",
	"lib/modulo.txt": b"modulo 1.1.0" * 2000,
	"data/sounds/paso.wav": b"sonido nuevo",
}


@pytest.fixture(scope="module")
def claves(tmp_path_factory) -> Claves:
	return Claves(tmp_path_factory.mktemp("claves"))


@pytest.fixture(autouse=True)
def _esperas_cortas(monkeypatch):
	monkeypatch.setattr(red, "TIEMPO_ESPERA", 5.0)
	monkeypatch.setattr(red, "ESPERA_INICIAL", 0.01)


@pytest.fixture
def config(tmp_path, servidor, claves):  # noqa: F811
	instalacion = tmp_path / "instalación de prueba"
	(instalacion / "data").mkdir(parents=True)
	(instalacion / "EntornoLab.exe").write_bytes(b"EXE estudio 1.0.0")
	return actualizador.Configuracion(
		version_actual="1.0.0",
		carpeta_app=instalacion,
		url_estable=servidor.url("version.json"),
		url_pruebas=servidor.url("pruebas/version.json"),
		claves_publicas=(claves.publica,),
		comando=["no-se-lanza"],
		permitir_desde_codigo=True,
	)


# ── Versiones ────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
	("a", "b", "esperado"),
	[
		("1.0.0", "1.0", 0),
		("1.0.1", "1.0.0", 1),
		("1.10.0", "1.9.9", 1),
		("v2.0", "1.99", 1),
		("1.0.0-beta.1", "1.0.0", -1),
		("1.0rc1", "1.0b3", 1),
		("1.0.dev1", "1.0a1", -1),
		("0.9", "1.0", -1),
	],
)
def test_comparar_versiones(a, b, esperado):
	assert actualizador.comparar_versiones(a, b) == esperado


@pytest.mark.parametrize("texto", ["", "abc", "1..2", "1.0 final", None])
def test_version_no_valida(texto):
	with pytest.raises(actualizador.VersionInvalida):
		actualizador.clave_version(texto)


# ── Firma ────────────────────────────────────────────────────────────────────


def test_la_serializacion_canonica_coincide_con_la_herramienta():
	firmador = cargar_herramienta("firmar_version")
	manifiesto = {"version": "1.0", "ñ": "áé", "size": 3, "lista": [1, {"b": 2, "a": 1}], "firma_ed25519": "x"}
	assert actualizador.serializar_canonico(manifiesto) == firmador.serializar_canonico(manifiesto)
	assert firmador.CAMPO_FIRMA == actualizador.CAMPO_FIRMA
	assert b"firma" not in actualizador.serializar_canonico(manifiesto)


def test_firma_valida_y_manipulada(claves):
	manifiesto = claves.firmar({"version": "1.1.0", "file": "a.zip", "sha256": "0" * 64, "size": 10})
	actualizador.verificar_firma(manifiesto, (claves.publica,))
	for cambio in ({"version": "9.9.9"}, {"size": 11}, {"url": "https://malo.invalid/a.zip"}, {"novedades": "x"}):
		with pytest.raises(actualizador.ErrorFirma):
			actualizador.verificar_firma({**manifiesto, **cambio}, (claves.publica,))


def test_firma_rechazada_sin_firma_sin_claves_o_con_otra_clave(claves, tmp_path):
	otra = Claves(tmp_path / "otras")
	manifiesto = claves.firmar({"version": "1.1.0"})
	sin_firma = {clave: valor for clave, valor in manifiesto.items() if clave != actualizador.CAMPO_FIRMA}
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.verificar_firma(sin_firma, (claves.publica,))
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.verificar_firma(manifiesto, ())
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.verificar_firma(manifiesto, (otra.publica,))
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.verificar_firma({**manifiesto, actualizador.CAMPO_FIRMA: "esto no es base64 !!"}, (claves.publica,))
	# Con varias claves aceptadas (rotación) basta con que una corresponda.
	actualizador.verificar_firma(manifiesto, ("zz", otra.publica, claves.publica))


def test_la_clave_publica_del_codigo_es_valida_y_la_privada_no_esta_en_el_proyecto():
	from tests._actualizador_util import RAIZ

	assert actualizador.CLAVES_PUBLICAS_ED25519
	for clave in actualizador.CLAVES_PUBLICAS_ED25519:
		assert len(bytes.fromhex(clave)) == 32
	firmador = cargar_herramienta("firmar_version")
	assert not firmador.esta_dentro_del_proyecto(firmador.ruta_clave_privada())
	assert not list((RAIZ / "tools").rglob("*.key"))
	assert "tools/claves/" in (RAIZ / ".gitignore").read_text(encoding="utf-8")


def test_generar_claves_se_niega_dentro_del_proyecto(tmp_path):
	from tests._actualizador_util import RAIZ

	generador = cargar_herramienta("generar_claves")
	with pytest.raises(ValueError, match="dentro del proyecto"):
		generador.generar(RAIZ / "tools" / "claves")
	ruta, _publica = generador.generar(tmp_path / "c")
	with pytest.raises(FileExistsError):
		generador.generar(tmp_path / "c")
	assert ruta.read_bytes().startswith(b"-----BEGIN PRIVATE KEY-----")


# ── Direcciones de GitHub ────────────────────────────────────────────────────


def test_direcciones_por_defecto_son_de_github_y_https():
	assert actualizador.URL_ESTABLE == "https://github.com/hxebolax/EntornoLab/releases/latest/download/version.json"
	assert actualizador.URL_PRUEBAS == "https://github.com/hxebolax/EntornoLab/releases/download/pruebas/version.json"
	red.comprobar_url(actualizador.URL_ESTABLE)
	red.comprobar_url(actualizador.URL_PRUEBAS)
	por_defecto = actualizador.configuracion_por_defecto()
	assert por_defecto.canal == "estable"
	assert actualizador.fuentes(por_defecto) == [("estable", actualizador.URL_ESTABLE)]
	assert not actualizador.puede_instalar(por_defecto)  # desde el código fuente nunca se sustituye


# ── Comprobación ─────────────────────────────────────────────────────────────


def test_version_nueva(config, servidor, claves):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves, novedades="- Catálogo en línea.\n- Correcciones.")
	info = actualizador.comprobar(config)
	assert info is not None
	assert (info.version, info.canal, info.archivo) == ("1.1.0", "estable", "EntornoLab_v1.1.0.zip")
	assert info.url_zip == servidor.url("EntornoLab_v1.1.0.zip")
	assert "Catálogo en línea" in info.novedades
	assert obtener_configuracion().obtener("actualizaciones.ultima_comprobacion")


@pytest.mark.parametrize("publicada", ["1.0.0", "0.9.5", "1.0"])
def test_version_igual_o_mas_antigua_no_se_ofrece(config, servidor, claves, publicada):  # noqa: F811
	publicar_version(servidor.carpeta, publicada, ARCHIVOS, claves)
	assert actualizador.comprobar(config) is None


def test_firma_mala_se_rechaza(config, servidor, claves, tmp_path):  # noqa: F811
	manifiesto = publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	# Alguien cambia la versión y la huella sin poder volver a firmar.
	escribir_json(servidor.carpeta / "version.json", {**manifiesto, "sha256": "f" * 64})
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.comprobar(config)
	# Firmado con una clave que la aplicación no conoce.
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, Claves(tmp_path / "intruso"))
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.comprobar(config)
	# Sin firmar.
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, None)
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.comprobar(config)
	assert not obtener_configuracion().obtener("actualizaciones.ultima_comprobacion")


@pytest.mark.parametrize(
	"extra",
	[
		{"app": "OtraAplicacion"},
		{"file": "../fuera.zip"},
		{"file": "paquete.exe"},
		{"sha256": "abc"},
		{"size": 0},
		{"size": -5},
		{"size": True},
		{"version": "no es una versión"},
		{"url": "http://ejemplo.invalid/EntornoLab.zip"},
		{"canal": "nocturno"},
	],
)
def test_manifiesto_firmado_pero_inadmisible(config, servidor, claves, extra):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves, extra=extra)
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.comprobar(config)


def test_sin_publicaciones_da_un_error_de_conexion_claro(config):
	with pytest.raises(actualizador.ErrorConexion) as error:
		actualizador.comprobar(config)
	assert "404" in str(error.value)


def test_proteccion_contra_retrocesos(config, servidor, claves):  # noqa: F811
	actualizador.confirmar_version(config, "1.5.0")
	actualizador.confirmar_version(config, "1.2.0")  # nunca baja
	assert actualizador.leer_estado(config)["version_confirmada"] == "1.5.0"
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	with pytest.raises(actualizador.ErrorRetroceso):
		actualizador.comprobar(config)
	publicar_version(servidor.carpeta, "1.5.1", ARCHIVOS, claves)
	assert actualizador.comprobar(config).version == "1.5.1"


def test_saltar_una_version(config, servidor, claves):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	actualizador.saltar_version("1.1.0")
	assert actualizador.version_saltada() == "1.1.0"
	assert actualizador.comprobar(config, respetar_saltada=True) is None
	assert actualizador.comprobar(config).version == "1.1.0"  # la manual siempre informa
	publicar_version(servidor.carpeta, "1.2.0", ARCHIVOS, claves)
	assert actualizador.comprobar(config, respetar_saltada=True).version == "1.2.0"


def test_canal_de_pruebas(config, servidor, claves):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	publicar_version(servidor.carpeta / "pruebas", "1.2.0-beta.1", ARCHIVOS, claves, canal="pruebas")
	assert actualizador.comprobar(config).version == "1.1.0"
	assert servidor.veces("pruebas/version.json") == 0  # el canal estable ni lo mira
	config.canal = "pruebas"
	info = actualizador.comprobar(config)
	assert (info.version, info.canal) == ("1.2.0-beta.1", "pruebas")
	assert info.url_zip == servidor.url("pruebas/EntornoLab_v1.2.0-beta.1.zip")
	# Cuando la estable adelanta a la de pruebas, gana la estable.
	publicar_version(servidor.carpeta, "1.2.0", ARCHIVOS, claves)
	assert actualizador.comprobar(config).version == "1.2.0"


def test_canal_de_pruebas_sin_publicacion_de_pruebas_usa_la_estable(config, servidor, claves):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	config.canal = "pruebas"
	assert actualizador.comprobar(config).version == "1.1.0"


def test_el_canal_estable_no_acepta_un_manifiesto_de_pruebas(config, servidor, claves):  # noqa: F811
	"""Aunque la firma sea buena: nadie puede colocar una versión preliminar en el canal estable."""
	publicar_version(servidor.carpeta, "1.2.0-beta.1", ARCHIVOS, claves, canal="pruebas")
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.comprobar(config)


def test_un_catalogo_firmado_no_vale_como_version(config, servidor, claves):  # noqa: F811
	escribir_json(servidor.carpeta / "version.json", claves.firmar({"tipo": "catalogo-complementos", "complementos": []}))
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.comprobar(config)


# ── Preferencias ─────────────────────────────────────────────────────────────


def test_de_fabrica_no_se_comprueba_al_arrancar_y_se_pregunta_una_vez():
	assert actualizador.debe_preguntar()
	assert not actualizador.comprobacion_al_arrancar()
	assert not actualizador.toca_comprobar()
	actualizador.establecer_comprobacion_al_arrancar(False)
	assert not actualizador.debe_preguntar()
	assert not actualizador.toca_comprobar()
	actualizador.establecer_comprobacion_al_arrancar(True)
	assert not actualizador.debe_preguntar()
	assert actualizador.toca_comprobar()


def test_toca_comprobar_una_vez_al_dia():
	actualizador.establecer_comprobacion_al_arrancar(True)
	ahora = datetime.now(timezone.utc)
	config = obtener_configuracion()
	config.establecer("actualizaciones.ultima_comprobacion", (ahora - timedelta(hours=2)).isoformat(timespec="seconds"))
	assert not actualizador.toca_comprobar(ahora)
	config.establecer("actualizaciones.ultima_comprobacion", (ahora - timedelta(hours=25)).isoformat(timespec="seconds"))
	assert actualizador.toca_comprobar(ahora)
	config.establecer("actualizaciones.ultima_comprobacion", "ayer por la tarde")
	assert actualizador.toca_comprobar(ahora)


def test_canal_en_preferencias():
	assert actualizador.canal_elegido() == "estable"
	actualizador.establecer_canal("pruebas")
	assert actualizador.canal_elegido() == "pruebas"
	assert actualizador.configuracion_por_defecto().canal == "pruebas"
	with pytest.raises(ValueError):
		actualizador.establecer_canal("nocturno")


# ── Descarga ─────────────────────────────────────────────────────────────────


def test_descarga_y_verificacion(config, servidor, claves):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	info = actualizador.comprobar(config)
	fases: list[str] = []
	ruta = actualizador.descargar(config, info, progreso=lambda fase, _h, _t: fases.append(fase))
	assert ruta == config.carpeta_trabajo / "descarga" / "EntornoLab_v1.1.0.zip"
	actualizador.verificar_paquete(ruta, info)
	assert set(fases) == {"descarga"}


def test_sha_malo_se_rechaza_y_se_borra(config, servidor, claves):  # noqa: F811
	"""El ZIP del servidor no es el que se firmó (lo cambiaron después de publicar)."""
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	info = actualizador.comprobar(config)
	original = (servidor.carpeta / info.archivo).read_bytes()
	(servidor.carpeta / info.archivo).write_bytes(original[:-1] + bytes([original[-1] ^ 0xFF]))
	with pytest.raises(actualizador.ErrorVerificacion):
		actualizador.descargar(config, info)
	assert list((config.carpeta_trabajo / "descarga").iterdir()) == []


def test_zip_mayor_de_lo_firmado_se_rechaza(config, servidor, claves):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	info = actualizador.comprobar(config)
	with (servidor.carpeta / info.archivo).open("ab") as archivo:
		archivo.write(b"relleno" * 1000)
	with pytest.raises(actualizador.ErrorVerificacion):
		actualizador.descargar(config, info)


def test_descarga_cortada_y_reanudada(config, servidor, claves):  # noqa: F811
	grandes = {**ARCHIVOS, "lib/grande.bin": bytes(range(256)) * 2000}
	with zipfile.ZipFile(servidor.carpeta / "medida.zip", "w", zipfile.ZIP_STORED) as paquete:
		for nombre, contenido in grandes.items():
			paquete.writestr(f"EntornoLab/{nombre}", contenido)
	datos = (servidor.carpeta / "medida.zip").read_bytes()
	(servidor.carpeta / "EntornoLab_v1.1.0.zip").write_bytes(datos)
	import hashlib

	manifiesto = claves.firmar(
		{
			"app": "EntornoLab",
			"version": "1.1.0",
			"file": "EntornoLab_v1.1.0.zip",
			"sha256": hashlib.sha256(datos).hexdigest(),
			"size": len(datos),
		}
	)
	escribir_json(servidor.carpeta / "version.json", manifiesto)
	info = actualizador.comprobar(config)
	servidor.cortar(info.archivo, 150_000)
	with pytest.raises(actualizador.ErrorConexion) as error:
		actualizador.descargar(config, info)
	assert error.value.reintentar
	parcial = config.carpeta_trabajo / "descarga" / (info.archivo + ".parcial")
	a_medias = parcial.stat().st_size
	assert 0 < a_medias < info.tamano
	ruta = actualizador.descargar(config, info)
	actualizador.verificar_paquete(ruta, info)
	cabeceras = {nombre.lower(): valor for nombre, valor in servidor.cabeceras_de(info.archivo)[-1].items()}
	assert cabeceras["range"] == f"bytes={a_medias}-"


def test_cancelar_la_descarga(config, servidor, claves):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	info = actualizador.comprobar(config)
	cancelar = threading.Event()
	cancelar.set()
	with pytest.raises(actualizador.ErrorCancelado):
		actualizador.descargar(config, info, cancelacion=cancelar)


def test_desde_el_codigo_fuente_no_se_instala(config, servidor, claves):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	info = actualizador.comprobar(config)
	config.permitir_desde_codigo = False
	with pytest.raises(actualizador.ErrorActualizacion, match="código fuente"):
		actualizador.descargar_y_preparar(config, info)
	assert servidor.veces(info.archivo) == 0


# ── Extracción segura ────────────────────────────────────────────────────────


def _zip_con(ruta, entradas: dict[str, bytes]):
	with zipfile.ZipFile(ruta, "w") as paquete:
		for nombre, contenido in entradas.items():
			paquete.writestr(nombre, contenido)
	return ruta


@pytest.mark.parametrize(
	"nombre",
	[
		"EntornoLab/../../fuera.txt",
		"../fuera.txt",
		"/absoluta.txt",
		"C:/Windows/System32/malo.dll",
		"EntornoLab\\..\\..\\fuera.txt",
		"EntornoLab/lib/CON.txt",
		"EntornoLab/lib/nul",
		"EntornoLab/lib/archivo.txt:flujo",
		"EntornoLab/lib/acaba en punto.",
	],
)
def test_zip_malicioso_se_rechaza_entero(config, tmp_path, nombre):
	paquete = _zip_con(tmp_path / "malo.zip", {"EntornoLab/EntornoLab.exe": b"EXE", nombre: b"malo"})
	destino = tmp_path / "extraido"
	with pytest.raises(actualizador.ErrorPaquete):
		actualizador.extraer_seguro(paquete, destino, config)
	assert not destino.exists()
	assert not (tmp_path / "fuera.txt").exists()
	assert not (tmp_path.parent / "fuera.txt").exists()


def test_zip_con_enlace_simbolico_o_repetido_se_rechaza(config, tmp_path):
	ruta = tmp_path / "enlace.zip"
	with zipfile.ZipFile(ruta, "w") as paquete:
		paquete.writestr("EntornoLab/EntornoLab.exe", b"EXE")
		enlace = zipfile.ZipInfo("EntornoLab/enlace")
		enlace.external_attr = (stat.S_IFLNK | 0o777) << 16
		paquete.writestr(enlace, "C:/Windows")
	with pytest.raises(actualizador.ErrorPaquete, match="enlaces"):
		actualizador.extraer_seguro(ruta, tmp_path / "e1", config)
	repetido = _zip_con(
		tmp_path / "repetido.zip", {"EntornoLab/EntornoLab.exe": b"EXE", "EntornoLab/Lib/a.txt": b"1", "EntornoLab/lib/A.TXT": b"2"}
	)
	with pytest.raises(actualizador.ErrorPaquete, match="repite"):
		actualizador.extraer_seguro(repetido, tmp_path / "e2", config)


def test_zip_que_no_es_la_aplicacion_o_esta_danado(config, tmp_path):
	otro = _zip_con(tmp_path / "otro.zip", {"Otra/Otra.exe": b"EXE"})
	with pytest.raises(actualizador.ErrorPaquete, match="no parece"):
		actualizador.extraer_seguro(otro, tmp_path / "e1", config)
	(tmp_path / "roto.zip").write_bytes(b"PK esto no es un zip")
	with pytest.raises(actualizador.ErrorPaquete, match="dañado"):
		actualizador.extraer_seguro(tmp_path / "roto.zip", tmp_path / "e2", config)


def test_bomba_zip_se_rechaza(config, tmp_path):
	config.max_expandido = 100_000
	with zipfile.ZipFile(tmp_path / "bomba.zip", "w", zipfile.ZIP_DEFLATED) as paquete:
		paquete.writestr("EntornoLab/EntornoLab.exe", b"EXE")
		paquete.writestr("EntornoLab/lib/ceros.bin", b"\0" * 5_000_000)
	with pytest.raises(actualizador.ErrorPaquete, match="demasiado"):
		actualizador.extraer_seguro(tmp_path / "bomba.zip", tmp_path / "e", config)


def test_los_datos_del_usuario_que_traiga_el_zip_se_descartan(config, tmp_path):
	paquete = crear_zip(
		tmp_path / "v.zip",
		{
			**ARCHIVOS,
			"lib/paquete/data/interno.txt": b"esto es del programa, no la data del usuario",
			"data/config/config.json": b'{"pisado": true}',
			"data/db/entornolab.db": b"base de datos ajena",
			"data/sessions/s.json.gz": b"sesion ajena",
			"data/entornos/casa.elab": b"entorno ajeno",
			"data/logs/x.log": b"registro",
			"data/suelto.txt": b"fichero suelto en data",
			"data/docs/manual.md": b"# Manual nuevo",
			"data/ejemplos/piso.elab": b"ejemplo nuevo",
		},
	)
	destino = actualizador.extraer_seguro(paquete, tmp_path / "extraido", config)
	recursos = sorted(p.relative_to(destino / "recursos").as_posix() for p in (destino / "recursos").rglob("*") if p.is_file())
	assert recursos == ["docs/manual.md", "ejemplos/piso.elab", "sounds/paso.wav"]
	assert (destino / "programa" / "EntornoLab.exe").read_bytes() == b"EXE estudio 1.1.0"
	assert (destino / "programa" / "EntornoLabJugar.exe").is_file()
	assert (destino / "programa" / "lib" / "paquete" / "data" / "interno.txt").is_file()


def _ficha(identificador: str, version: str) -> bytes:
	return json.dumps({"formato": 1, "id": identificador, "version": version, "objetos": []}).encode("utf-8")


def test_complementos_al_actualizar_la_aplicacion(config, tmp_path):
	"""La versión nueva trae sus complementos de serie sin pisar los del usuario ni los más nuevos."""
	plugins = config.carpeta_complementos
	for identificador, version in (("mobiliario", "1.0"), ("ciudad", "3.0"), ("propio", "1.0"), ("igual", "2.0")):
		(plugins / identificador).mkdir(parents=True)
		(plugins / identificador / "complemento.json").write_bytes(_ficha(identificador, version))
		(plugins / identificador / "marca.txt").write_text("instalado", encoding="utf-8")
	# «ciudad» lo actualizó el usuario desde el catálogo; «propio» lo instaló él.
	escribir_json(
		config.carpeta_datos / "config" / "complementos.json", {"instalados": {"ciudad": {"version": "3.0"}, "propio": {"version": "1.0"}}}
	)
	entradas = {**ARCHIVOS, "data/plugins/de_serie.json": b'{"de_serie": {}}'}
	for identificador, version in (("mobiliario", "2.0"), ("ciudad", "2.5"), ("propio", "1.0"), ("igual", "2.0"), ("nuevo", "1.0")):
		entradas[f"data/plugins/{identificador}/complemento.json"] = _ficha(identificador, version)
		entradas[f"data/plugins/{identificador}/sonidos/a.wav"] = b"del zip"
	destino = actualizador.extraer_seguro(crear_zip(tmp_path / "v.zip", entradas), tmp_path / "extraido", config)
	copiados = sorted(p.name for p in (destino / "recursos" / "plugins").iterdir())
	# mobiliario: el ZIP es más nuevo. igual: misma versión y de serie (se repara). nuevo: no estaba.
	# ciudad: el instalado es más nuevo. propio: misma versión, pero es del usuario.
	assert copiados == ["de_serie.json", "igual", "mobiliario", "nuevo"]
	assert actualizador.complementos_del_usuario(config.carpeta_datos) == {"ciudad", "propio"}


def test_preparar_el_script(config, servidor, claves):  # noqa: F811
	publicar_version(servidor.carpeta, "1.1.0", ARCHIVOS, claves)
	info = actualizador.comprobar(config)
	fases: list[str] = []
	ruta_bat = actualizador.descargar_y_preparar(config, info, progreso=lambda fase, _h, _t: fases.append(fase))
	assert [fase for indice, fase in enumerate(fases) if indice == 0 or fases[indice - 1] != fase] == [
		"descarga",
		"verificacion",
		"extraccion",
		"preparacion",
	]
	texto = ruta_bat.read_bytes().decode("utf-8")
	assert "\r\n" in texto and "{" not in texto.split("powershell")[0].replace("{ ", "")
	assert "esperar_reproductores" in texto
	assert "/MIR" not in texto.upper().replace("NUNCA USA /MIR", "")
	assert (config.carpeta_trabajo / "nueva" / "programa" / "EntornoLab.exe").is_file()
	assert not (config.carpeta_trabajo / "descarga" / info.archivo).exists()


# ── Reproductores y arranque ─────────────────────────────────────────────────


def test_reproductores_abiertos(config, monkeypatch):
	from app.core import procesos

	class Falso:
		pid = 4242

	monkeypatch.setattr(procesos, "procesos_vivos", lambda: [Falso()])
	monkeypatch.setattr(actualizador, "_procesos_con_imagen", lambda ruta: [77] if ruta.name == "EntornoLabJugar.exe" else [])
	assert actualizador.reproductores_abiertos(config) == [77, 4242]
	cerrados: list[float] = []
	monkeypatch.setattr(procesos, "terminar_todos", lambda espera=2.0: cerrados.append(espera))
	monkeypatch.setattr(procesos, "procesos_vivos", lambda: [])
	assert actualizador.cerrar_reproductores(config) == [77]  # el que abrió otra persona no se toca
	assert cerrados


def test_buscar_procesos_por_ruta_no_falla(config):
	assert actualizador._procesos_con_imagen(config.carpeta_app / "EntornoLabJugar.exe") == []


def test_confirmar_arranque_y_marcador(config):
	actualizador.confirmar_arranque(config, tras_actualizar=False)
	assert actualizador.leer_estado(config)["version_confirmada"] == "1.0.0"
	assert not config.marcador_salud.exists()
	config.carpeta_trabajo.mkdir(parents=True, exist_ok=True)
	config.aviso_espera_salud.write_text("1.0.0\n", encoding="utf-8")
	actualizador.confirmar_arranque(config, tras_actualizar=False)
	assert config.marcador_salud.read_text(encoding="utf-8").strip() == "ok 1.0.0"


@pytest.mark.parametrize(
	("estado", "motivo", "fragmento"),
	[
		("correcta", "ninguno", None),
		("revertida", "sin_marcador_de_salud", "se ha vuelto a la versión 1.0.0"),
		("no_aplicada", "la_aplicacion_no_se_cerro", "seguían abiertos"),
		("no_aplicada", "fallo_copia_de_seguridad", "no se ha tocado"),
		("rota", "x", "recuperar.bat"),
	],
)
def test_resultado_de_la_actualizacion_anterior(config, estado, motivo, fragmento):
	config.carpeta_trabajo.mkdir(parents=True, exist_ok=True)
	(config.carpeta_trabajo / "nueva").mkdir()
	config.archivo_resultado.write_text(f"estado={estado}\nmotivo={motivo}\nversion=1.1.0\nanterior=1.0.0\n", encoding="utf-8")
	mensaje = actualizador.leer_resultado_anterior(config)
	if fragmento is None:
		assert mensaje is None
	else:
		assert fragmento in mensaje and "1.1.0" in mensaje
	assert not config.archivo_resultado.exists()
	assert not (config.carpeta_trabajo / "nueva").exists()
	assert actualizador.version_saltada() == ("1.1.0" if estado == "revertida" else "")
	assert actualizador.leer_resultado_anterior(config) is None
