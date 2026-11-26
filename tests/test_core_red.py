"""Pruebas de ``app.core.red`` y ``app.core.descargas`` contra un servidor local (sin Internet)."""

from __future__ import annotations

import hashlib
import ssl
import threading

import pytest

from app.core import descargas, red
from app.core.version import APP_VERSION
from tests.servidor_http_prueba import servidor  # noqa: F401 - fixture

CONTENIDO = bytes(range(256)) * 1200  # 300 KB deterministas
SHA = hashlib.sha256(CONTENIDO).hexdigest()


@pytest.fixture(autouse=True)
def _esperas_cortas(monkeypatch):
	monkeypatch.setattr(red, "TIEMPO_ESPERA", 5.0)
	monkeypatch.setattr(red, "ESPERA_INICIAL", 0.01)


@pytest.fixture
def web(servidor):  # noqa: F811
	(servidor.carpeta / "archivo.bin").write_bytes(CONTENIDO)
	(servidor.carpeta / "dato.json").write_text('{"a": 1}', encoding="utf-8")
	return servidor


# ── Direcciones y privacidad ─────────────────────────────────────────────────


@pytest.mark.parametrize("url", ["https://github.com/x", "http://127.0.0.1:8000/x", "http://localhost/x", "http://[::1]:9/x"])
def test_direcciones_admitidas(url):
	red.comprobar_url(url)


@pytest.mark.parametrize("url", ["http://github.com/x", "ftp://github.com/x", "file:///C:/Windows/win.ini", "", "github.com", "https://"])
def test_direcciones_rechazadas(url):
	with pytest.raises(red.ErrorRed) as error:
		red.comprobar_url(url)
	assert error.value.categoria == "seguridad"


def test_user_agent_generico_sin_identificadores(web):
	assert red.user_agent() == f"EntornoLab/{APP_VERSION}"
	red.leer_bytes(web.url("dato.json"), 1000)
	cabeceras = {nombre.lower(): valor for nombre, valor in web.cabeceras_de("dato.json")[0].items()}
	assert cabeceras["user-agent"] == f"EntornoLab/{APP_VERSION}"
	# Nada que identifique al equipo o a la persona: ni galletas, ni procedencia, ni autorización.
	assert not {"cookie", "referer", "authorization", "from", "x-forwarded-for"} & set(cabeceras)
	assert set(cabeceras) <= {"user-agent", "accept", "accept-encoding", "cache-control", "host", "connection"}


def test_el_contexto_tls_verifica_certificado_y_nombre():
	contexto = red.contexto_tls()
	assert contexto.verify_mode == ssl.CERT_REQUIRED
	assert contexto.check_hostname is True
	assert contexto.minimum_version >= ssl.TLSVersion.TLSv1_2


def test_no_hay_conexiones_fuera_de_la_maquina(sin_red):
	"""La red de seguridad de las pruebas funciona: una petición a GitHub no sale del equipo."""
	from tests.conftest import ConexionBloqueada

	with pytest.raises(ConexionBloqueada):
		red.leer_bytes("https://github.com/hxebolax/EntornoLab", 1000, intentos=1)
	assert sin_red.intentos == ["github.com"]


# ── Peticiones ───────────────────────────────────────────────────────────────


def test_leer_json(web):
	assert red.leer_json(web.url("dato.json"), 1000) == {"a": 1}


def test_json_danado(web):
	(web.carpeta / "roto.json").write_text("{esto no es json", encoding="utf-8")
	(web.carpeta / "lista.json").write_text("[1, 2]", encoding="utf-8")
	for nombre in ("roto.json", "lista.json"):
		with pytest.raises(red.ErrorRed) as error:
			red.leer_json(web.url(nombre), 1000)
		assert error.value.categoria == "servidor"


def test_respuesta_demasiado_grande(web):
	with pytest.raises(red.ErrorRed):
		red.leer_bytes(web.url("archivo.bin"), 1000)


def test_reintenta_los_fallos_pasajeros(web):
	web.fallos["dato.json"] = [(503, {}), (429, {"Retry-After": "0"})]
	assert red.leer_json(web.url("dato.json"), 1000) == {"a": 1}
	assert web.veces("dato.json") == 3


def test_503_persistente_acaba_en_error_reintentable(web):
	web.fallos["dato.json"] = [(503, {})] * 5
	with pytest.raises(red.ErrorRed) as error:
		red.leer_bytes(web.url("dato.json"), 1000)
	assert error.value.codigo_http == 503
	assert error.value.reintentar
	assert error.value.transitorio
	assert web.veces("dato.json") == red.INTENTOS


def test_retry_after_largo_falla_enseguida(web):
	web.fallos["dato.json"] = [(429, {"Retry-After": "3600"})]
	with pytest.raises(red.ErrorRed) as error:
		red.abrir(web.url("dato.json"))
	assert error.value.codigo_http == 429
	assert web.veces("dato.json") == 1


def test_404_no_se_reintenta(web):
	with pytest.raises(red.ErrorRed) as error:
		red.leer_bytes(web.url("no-existe"), 1000)
	assert error.value.codigo_http == 404
	assert not error.value.reintentar
	assert web.veces("no-existe") == 1
	assert "404" in error.value.mensaje_usuario


def test_redireccion_a_http_externo_se_rechaza(web):
	web.redirecciones["salto"] = "http://ejemplo.invalid/archivo.bin"
	with pytest.raises(red.ErrorRed) as error:
		red.leer_bytes(web.url("salto"), 1000)
	assert error.value.categoria == "seguridad"


def test_redireccion_local_se_sigue(web):
	web.redirecciones["salto"] = web.url("dato.json")
	assert red.leer_json(web.url("salto"), 1000) == {"a": 1}


def test_servidor_apagado_da_mensaje_claro(tmp_path):
	from tests.servidor_http_prueba import ServidorPrueba

	apagado = ServidorPrueba(tmp_path / "w")
	url = apagado.url("x")
	apagado.cerrar()
	with pytest.raises(red.ErrorRed) as error:
		red.leer_bytes(url, 10, intentos=1)
	assert error.value.categoria == "red"
	assert "conectar" in error.value.mensaje_usuario


def test_clasificar_errores_locales():
	assert red.clasificar_error(PermissionError("no")).categoria == "local"
	assert red.clasificar_error(TimeoutError()).reintentar
	assert red.clasificar_error(ValueError("x")).categoria == "desconocido"
	assert red.clasificar_error(ssl.SSLCertVerificationError("mal")).categoria == "seguridad"


# ── Descargas ────────────────────────────────────────────────────────────────


def test_descarga_completa_y_verificada(web, tmp_path):
	avances: list[tuple[int, int | None]] = []
	resultado = descargas.descargar(
		web.url("archivo.bin"),
		tmp_path / "d" / "archivo.bin",
		sha256=SHA,
		tamano=len(CONTENIDO),
		al_progresar=lambda h, t: avances.append((h, t)),
	)
	assert resultado.ruta.read_bytes() == CONTENIDO
	assert resultado.sha256 == SHA
	assert not resultado.reanudada
	assert avances[-1] == (len(CONTENIDO), len(CONTENIDO))
	assert sorted(p.name for p in resultado.ruta.parent.iterdir()) == ["archivo.bin"]


def test_sha_incorrecto_borra_lo_descargado(web, tmp_path):
	destino = tmp_path / "archivo.bin"
	with pytest.raises(descargas.ErrorIntegridad):
		descargas.descargar(web.url("archivo.bin"), destino, sha256="0" * 64)
	assert list(tmp_path.glob("archivo.bin*")) == []


def test_fichero_mayor_de_lo_anunciado_se_descarta(web, tmp_path):
	destino = tmp_path / "archivo.bin"
	with pytest.raises(descargas.ErrorDescarga):
		descargas.descargar(web.url("archivo.bin"), destino, tamano=1000)
	assert not destino.exists()
	with pytest.raises(descargas.ErrorDescarga):
		descargas.descargar(web.url("archivo.bin"), destino, tamano_maximo=1000)
	assert not destino.exists()


def test_descarga_cortada_y_reanudada(web, tmp_path):
	destino = tmp_path / "archivo.bin"
	web.cortar("archivo.bin", 100_000)
	with pytest.raises(descargas.ErrorDescarga) as error:
		descargas.descargar(web.url("archivo.bin"), destino, sha256=SHA, tamano=len(CONTENIDO))
	assert error.value.reintentar
	assert not destino.exists()
	parcial = destino.with_name("archivo.bin.parcial")
	assert 0 < parcial.stat().st_size < len(CONTENIDO)
	a_medias = parcial.stat().st_size

	resultado = descargas.descargar(web.url("archivo.bin"), destino, sha256=SHA, tamano=len(CONTENIDO))
	assert resultado.reanudada
	assert destino.read_bytes() == CONTENIDO
	cabeceras = {nombre.lower(): valor for nombre, valor in web.cabeceras_de("archivo.bin")[-1].items()}
	assert cabeceras["range"] == f"bytes={a_medias}-"
	assert "if-range" in cabeceras
	assert not parcial.exists()


def test_reanudar_sin_rangos_empieza_de_cero(web, tmp_path):
	destino = tmp_path / "archivo.bin"
	destino.with_name("archivo.bin.parcial").write_bytes(b"basura que no es del fichero")
	web.admite_rangos = False
	resultado = descargas.descargar(web.url("archivo.bin"), destino, sha256=SHA, tamano=len(CONTENIDO))
	assert not resultado.reanudada
	assert destino.read_bytes() == CONTENIDO


def test_parcial_de_otra_version_no_se_mezcla(web, tmp_path):
	"""Si el fichero cambió en el servidor (otro ETag), If-Range hace que llegue entero."""
	destino = tmp_path / "archivo.bin"
	destino.with_name("archivo.bin.parcial").write_bytes(b"x" * 5000)
	destino.with_name("archivo.bin.parcial.json").write_text('{"etag": "\\"otro\\""}', encoding="utf-8")
	resultado = descargas.descargar(web.url("archivo.bin"), destino, sha256=SHA)
	assert not resultado.reanudada
	assert destino.read_bytes() == CONTENIDO


def test_parcial_ya_completo_no_vuelve_a_descargar(web, tmp_path):
	destino = tmp_path / "archivo.bin"
	destino.with_name("archivo.bin.parcial").write_bytes(CONTENIDO)
	resultado = descargas.descargar(web.url("archivo.bin"), destino, sha256=SHA, tamano=len(CONTENIDO))
	assert resultado.reanudada
	assert web.veces("archivo.bin") == 0
	assert destino.read_bytes() == CONTENIDO


def test_cancelar_conserva_el_parcial(web, tmp_path):
	destino = tmp_path / "archivo.bin"
	cancelar = threading.Event()

	def progreso(hecho, _total):
		if hecho >= 64 * 1024:
			cancelar.set()

	with pytest.raises(descargas.DescargaCancelada) as error:
		descargas.descargar(web.url("archivo.bin"), destino, al_progresar=progreso, cancelacion=cancelar, progresos_por_segundo=0)
	assert error.value.parcial_conservado
	assert destino.with_name("archivo.bin.parcial").stat().st_size >= 64 * 1024
	assert not destino.exists()
	assert red.clasificar_error(error.value).categoria == "cancelado"


def test_descarga_sustituye_el_destino(web, tmp_path):
	destino = tmp_path / "archivo.bin"
	destino.write_bytes(b"viejo")
	descargas.descargar(web.url("archivo.bin"), destino, sha256=SHA)
	assert destino.read_bytes() == CONTENIDO


@pytest.mark.parametrize(
	("entrada", "esperado"),
	[
		("..\\..\\Windows\\win.ini", "win.ini"),
		("/etc/passwd", "passwd"),
		("CON.txt", "_CON.txt"),
		("nul", "_nul"),
		('a<b>:c"d|e?.zip', "a_b__c_d_e_.zip"),
		("", "descarga"),
		("...", "descarga"),
		("nombre. ", "nombre"),
	],
)
def test_nombre_seguro(entrada, esperado):
	assert descargas.nombre_seguro(entrada) == esperado
