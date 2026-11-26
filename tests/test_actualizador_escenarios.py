"""Todos los escenarios del actualizador, sobre instalaciones falsas con la forma de la compilación.

Dos grupos:

- Rápidos (solo Python): versiones y canales, paquetes rechazados (firma, SHA,
  ZIP dañado o con rutas peligrosas), descarga cortada y sin red, y las
  comprobaciones previas que paran ANTES de tocar nada: permisos de escritura
  (con una denegación real de icacls), disco lleno, rutas largas, restos
  bloqueados de un intento anterior, limpieza de lo que no se deja borrar,
  recuperación tras un corte y el mensaje que ve el usuario.
- Lentos (marcados ``lento``): ejecutan el .bat de verdad con bloqueos REALES
  puestos por otros procesos (fichero abierto sin compartir, DLL cargada,
  carpeta con un fichero en uso, solo lectura, permiso denegado), fallo forzado
  a mitad, corte de luz simulado matando el script, reproductor y segundo
  Estudio abiertos y rutas de más de 260 caracteres.

En todos se comparan las huellas SHA-256 de los datos del usuario antes y
después, y se comprueba con ``--comprobar-arranque`` que la versión que queda
(la nueva o la anterior tras volver atrás) está ENTERA y arranca.

La instalación vive en «Mis cosas\\EntornoLab (copia) & 100% ñ'».
"""

from __future__ import annotations

import errno
import hashlib
import os
import subprocess
import sys
import time
from pathlib import Path

import pytest

from app.core import red
from app.services import actualizador
from tests._actualizador_util import Claves, crear_zip, escribir_json, publicar_version
from tests._instalacion_falsa import (
	CEBO_DATOS_USUARIO,
	NOMBRE_INSTALACION,
	PYTHON_SIN_VENTANA,
	archivos_version,
	bloquear,
	comprobar_arranque,
	crear_instalacion,
	denegar,
	esperar,
	huellas,
	huellas_esperadas,
	quitar_denegaciones,
	terminar_restos,
)
from tests.servidor_http_prueba import ServidorPrueba

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="El actualizador sustituye una instalación de Windows")

# Carpeta honda para la prueba de rutas largas: con la instalación y data\temp\version_anterior\programa
# delante, pasa de sobra de 260 caracteres.
HONDO = "/".join(["carpeta con nombre largo de una biblioteca"] * 5)


@pytest.fixture(scope="module")
def claves(tmp_path_factory) -> Claves:
	return Claves(tmp_path_factory.mktemp("claves"))


@pytest.fixture
def entorno(tmp_path, monkeypatch, claves):
	monkeypatch.setattr(red, "ESPERA_INICIAL", 0.01)
	monkeypatch.setattr(red, "TIEMPO_ESPERA", 5.0)
	servidor = ServidorPrueba(tmp_path / "servidor")
	instalacion = tmp_path.joinpath(*NOMBRE_INSTALACION)
	datos = {"claves": claves, "servidor": servidor, "instalacion": instalacion, "procesos": [], "denegados": []}
	yield datos
	servidor.cerrar()
	for proceso in datos["procesos"]:
		if proceso.poll() is None:
			proceso.kill()
			proceso.wait(timeout=30)
	for ruta in datos["denegados"]:
		quitar_denegaciones(ruta)
	terminar_restos(instalacion)


def _publicar(entorno, version: str = "1.1.0", comportamiento: str = "sana", hondo: str = "", **opciones) -> dict:
	"""Publica una versión firmada; su ZIP trae además datos «del usuario» que nunca deben llegar."""
	return publicar_version(
		entorno["servidor"].carpeta,
		version,
		{**archivos_version(version, comportamiento, hondo), **CEBO_DATOS_USUARIO},
		entorno["claves"],
		**opciones,
	)


def _config(entorno, **cambios) -> actualizador.Configuracion:
	instalacion: Path = entorno["instalacion"]
	opciones = {
		"version_actual": "1.0.0",
		"carpeta_app": instalacion,
		"url_estable": entorno["servidor"].url("version.json"),
		"url_pruebas": entorno["servidor"].url("pruebas/version.json"),
		"claves_publicas": (entorno["claves"].publica,),
		"comando": [PYTHON_SIN_VENTANA, str(instalacion / "app_falsa.py")],
		"permitir_desde_codigo": True,
		"espera_salud": 20,
		"espera_cierre": 20,
		"reintentos_bloqueo": 3,
	}
	opciones.update(cambios)
	return actualizador.Configuracion(**opciones)


def _registro(config: actualizador.Configuracion) -> str:
	if config.registro_script.is_file():
		return config.registro_script.read_text(encoding="utf-8", errors="replace")
	return "(sin registro)"


def _leer_resultado(config: actualizador.Configuracion) -> dict[str, str]:
	return actualizador.leer_resultado(config) or {}


def _proceso_de_la_app(entorno, segundos: float) -> subprocess.Popen:
	"""Hace de «Estudio en ejecución», el proceso que el script espera que se cierre."""
	proceso = subprocess.Popen([PYTHON_SIN_VENTANA, "-c", f"import time; time.sleep({segundos})"])
	entorno["procesos"].append(proceso)
	return proceso


def _ejecutar(entorno, comportamiento: str = "sana", *, preparar=None, vida_app: float = 2, esperar_fin: bool = True, **cambios):
	"""Publica la 1.1.0, comprueba, descarga, prepara y lanza el .bat de verdad.

	:param preparar: función que recibe la configuración y pone los bloqueos
		justo antes de lanzar el script.
	"""
	_publicar(entorno, comportamiento=comportamiento, hondo=cambios.pop("hondo", ""))
	app = _proceso_de_la_app(entorno, vida_app)
	config = _config(entorno, pid_a_esperar=app.pid, **cambios)
	info = actualizador.comprobar(config)
	assert info is not None and info.version == "1.1.0"
	ruta_bat = actualizador.descargar_y_preparar(config, info)
	if preparar is not None:
		preparar(config)
	script = actualizador.lanzar_sustitucion(ruta_bat)
	entorno["procesos"].append(script)
	if esperar_fin:
		script.wait(timeout=config.espera_cierre * 3 + config.espera_salud + 180)
	return config, script


def _assert_version_entera(instalacion: Path, version: str, hondo: str = "") -> None:
	"""El programa es EXACTAMENTE el de ``version`` y arranca."""
	assert huellas(instalacion, programa=True) == huellas_esperadas(version, hondo)
	codigo, salida = comprobar_arranque(instalacion)
	assert (codigo, salida) == (0, f"VERSION {version} ok")


def _assert_anterior_intacta(instalacion: Path, programa_antes: dict[str, str]) -> None:
	"""Tras volver atrás, el programa es byte a byte el que había y arranca."""
	assert huellas(instalacion, programa=True) == programa_antes
	codigo, salida = comprobar_arranque(instalacion)
	assert (codigo, salida) == (0, "VERSION 1.0.0 ok")


def _arranques(instalacion: Path) -> str:
	ruta = instalacion / "data" / "logs" / "arranques.txt"
	return ruta.read_text(encoding="utf-8") if ruta.is_file() else ""


# ════════════════════════════════════════════════════════════════════════════
# Rápidos: qué se ofrece y qué se rechaza
# ════════════════════════════════════════════════════════════════════════════


@pytest.mark.parametrize(("publicada", "saltada", "respetar", "ofrece"), [
	("1.1.0", "", False, True),
	("1.0.0", "", False, False),
	("0.9.0", "", False, False),
	("1.1.0", "1.1.0", True, False),
	("1.1.0", "1.1.0", False, True),
])  # fmt: skip
def test_que_version_se_ofrece(entorno, publicada, saltada, respetar, ofrece):
	"""Nueva, igual, más antigua y saltada (la automática respeta el salto; la manual no)."""
	crear_instalacion(entorno["instalacion"])
	_publicar(entorno, publicada)
	if saltada:
		actualizador.saltar_version(saltada)
	info = actualizador.comprobar(_config(entorno), respetar_saltada=respetar)
	assert (info is not None) == ofrece


def test_canal_estable_y_de_pruebas(entorno):
	crear_instalacion(entorno["instalacion"])
	_publicar(entorno, "1.1.0")
	_publicar(entorno, "1.2.0-beta.1", canal="pruebas", nombre_json="pruebas/version.json")
	assert actualizador.comprobar(_config(entorno, canal="estable")).version == "1.1.0"
	assert actualizador.comprobar(_config(entorno, canal="pruebas")).version == "1.2.0-beta.1"


def _instalacion_sin_tocar(entorno, programa_antes, usuario_antes) -> None:
	instalacion = entorno["instalacion"]
	assert huellas(instalacion, programa=True) == programa_antes
	assert huellas(instalacion, programa=False) == usuario_antes
	assert not (instalacion / "data" / "temp" / "actualizacion" / "actualizar.bat").exists()


def test_firma_mala_se_rechaza_sin_tocar_nada(entorno, tmp_path):
	crear_instalacion(entorno["instalacion"])
	otras = Claves(tmp_path / "otras")
	publicar_version(entorno["servidor"].carpeta, "1.1.0", archivos_version("1.1.0"), otras)
	with pytest.raises(actualizador.ErrorFirma):
		actualizador.comprobar(_config(entorno))


def _refirmar(entorno, manifiesto: dict, zip_: Path) -> None:
	"""Firma de nuevo el manifiesto con la huella y el tamaño del ZIP tal como ha quedado."""
	datos = zip_.read_bytes()
	nuevo = {clave: valor for clave, valor in manifiesto.items() if clave != "firma_ed25519"}
	nuevo.update(sha256=hashlib.sha256(datos).hexdigest(), size=len(datos))
	escribir_json(entorno["servidor"].carpeta / "version.json", entorno["claves"].firmar(nuevo))


@pytest.mark.parametrize("defecto", ["sha", "zip_corrupto", "ruta_peligrosa"])
def test_paquete_malo_se_rechaza_sin_tocar_nada(entorno, defecto):
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	programa_antes, usuario_antes = huellas(instalacion, programa=True), huellas(instalacion, programa=False)
	carpeta = entorno["servidor"].carpeta
	manifiesto = _publicar(entorno)
	zip_ = carpeta / manifiesto["file"]
	if defecto == "sha":
		datos = bytearray(zip_.read_bytes())
		datos[len(datos) // 2] ^= 0xFF
		zip_.write_bytes(bytes(datos))
		esperado = actualizador.ErrorVerificacion
	else:
		if defecto == "zip_corrupto":
			zip_.write_bytes(b"esto no es un zip" * 50)
		else:
			crear_zip(zip_, {**archivos_version("1.1.0"), "../../fuera.txt": b"malo"})
		# Se vuelve a firmar con la huella del paquete malo: la firma es buena, el contenido no.
		_refirmar(entorno, manifiesto, zip_)
		esperado = actualizador.ErrorPaquete
	config = _config(entorno)
	info = actualizador.comprobar(config)
	with pytest.raises(esperado):
		actualizador.descargar_y_preparar(config, info)
	_instalacion_sin_tocar(entorno, programa_antes, usuario_antes)
	assert not (entorno["instalacion"].parent.parent / "fuera.txt").exists()


def test_descarga_cortada_y_reanudada(entorno):
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	manifiesto = _publicar(entorno)
	servidor = entorno["servidor"]
	servidor.cortar(manifiesto["file"], manifiesto["size"] // 3)
	config = _config(entorno)
	info = actualizador.comprobar(config)
	with pytest.raises(actualizador.ErrorConexion) as error:
		actualizador.descargar_y_preparar(config, info)
	assert error.value.reintentar  # el diálogo ofrece «Reintentar»
	ruta_bat = actualizador.descargar_y_preparar(config, info)
	assert ruta_bat.is_file()
	cabeceras = servidor.cabeceras_de(manifiesto["file"])
	assert len(cabeceras) >= 2 and any("Range" in c for c in cabeceras[1:])


def test_sin_red(entorno):
	crear_instalacion(entorno["instalacion"])
	config = _config(entorno)
	entorno["servidor"].cerrar()
	entorno["servidor"] = ServidorPrueba(entorno["instalacion"].parent.parent / "otro")  # el de antes ya no responde
	with pytest.raises(actualizador.ErrorConexion) as error:
		actualizador.comprobar(config)
	assert error.value.reintentar


# ════════════════════════════════════════════════════════════════════════════
# Rápidos: comprobaciones previas (paran ANTES de cerrar el Estudio)
# ════════════════════════════════════════════════════════════════════════════


def test_sin_permiso_de_escritura_no_se_descarga_nada(entorno):
	"""Como en Archivos de programa sin ser administrador: denegación REAL con icacls."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	manifiesto = _publicar(entorno)
	denegar(instalacion, "(WD,AD)")
	entorno["denegados"].append(instalacion)
	with pytest.raises(PermissionError):
		(instalacion / "prueba.txt").write_bytes(b"x")
	config = _config(entorno)
	info = actualizador.comprobar(config)
	with pytest.raises(actualizador.ErrorPermisos) as error:
		actualizador.descargar_y_preparar(config, info)
	assert "Archivos de programa" in str(error.value)
	assert entorno["servidor"].veces(manifiesto["file"]) == 0  # ni siquiera se descargó


def test_disco_lleno_antes_de_descargar(entorno, monkeypatch):
	crear_instalacion(entorno["instalacion"])
	manifiesto = _publicar(entorno)
	config = _config(entorno)
	info = actualizador.comprobar(config)
	monkeypatch.setattr(actualizador.shutil, "disk_usage", lambda _ruta: type("Uso", (), {"free": 1024})())
	with pytest.raises(actualizador.ErrorEspacio) as error:
		actualizador.descargar_y_preparar(config, info)
	assert "MB" in str(error.value)
	assert entorno["servidor"].veces(manifiesto["file"]) == 0


def test_disco_lleno_al_descomprimir(entorno, monkeypatch):
	"""Simulado: el disco se llena a mitad de la extracción. Nada queda a medias."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	programa_antes, usuario_antes = huellas(instalacion, programa=True), huellas(instalacion, programa=False)
	_publicar(entorno)
	config = _config(entorno)
	info = actualizador.comprobar(config)
	abiertos: list[str] = []

	def abrir(ruta, modo="r", *argumentos, **opciones):
		if "w" in modo and "nueva" in str(ruta):
			abiertos.append(str(ruta))
			if len(abiertos) > 3:
				raise OSError(errno.ENOSPC, "No queda espacio en el disco")
		return open(ruta, modo, *argumentos, **opciones)

	monkeypatch.setattr(actualizador, "open", abrir, raising=False)
	with pytest.raises(actualizador.ErrorEspacio):
		actualizador.descargar_y_preparar(config, info)
	assert not (config.carpeta_trabajo / "nueva").exists()
	_instalacion_sin_tocar(entorno, programa_antes, usuario_antes)


def test_ruta_demasiado_larga_sin_rutas_largas(entorno, monkeypatch):
	"""Sin la opción de rutas largas de Windows, una versión nueva que no podría arrancar se rechaza."""
	crear_instalacion(entorno["instalacion"])
	_publicar(entorno, hondo=HONDO)
	monkeypatch.setattr(actualizador, "rutas_largas_activadas", lambda: False)
	config = _config(entorno)
	info = actualizador.comprobar(config)
	with pytest.raises(actualizador.ErrorRutaLarga) as error:
		actualizador.descargar_y_preparar(config, info)
	assert "ruta más corta" in str(error.value)
	assert not (config.carpeta_trabajo / "actualizar.bat").exists()


def test_una_sustitucion_a_medias_impide_otra(entorno):
	crear_instalacion(entorno["instalacion"])
	_publicar(entorno)
	config = _config(entorno)
	info = actualizador.comprobar(config)
	config.carpeta_trabajo.mkdir(parents=True, exist_ok=True)
	config.diario.write_text("estado=aplicando\nversion=1.1.0\nanterior=1.0.0\n", encoding="utf-8")
	with pytest.raises(actualizador.ErrorEnCurso):
		actualizador.descargar_y_preparar(config, info)


# ── Restos que no se dejan borrar ────────────────────────────────────────────


def _solo_lectura(carpeta: Path) -> None:
	"""Lo que Windows devuelve como «Acceso denegado» al borrar una carpeta (WinError 5)."""
	carpeta.mkdir(parents=True, exist_ok=True)
	(carpeta / "ayuda.py").write_bytes(b"x")
	(carpeta / "ayuda.py").chmod(0o444)
	carpeta.chmod(0o555)


def test_restos_de_solo_lectura_de_un_intento_anterior(entorno):
	crear_instalacion(entorno["instalacion"])
	_publicar(entorno)
	config = _config(entorno)
	_solo_lectura(config.carpeta_trabajo / "nueva" / "programa" / "copia_vieja" / "ui")
	info = actualizador.comprobar(config)
	actualizador.descargar_y_preparar(config, info)
	assert not (config.carpeta_trabajo / "nueva" / "programa" / "copia_vieja").exists()
	assert (config.carpeta_trabajo / "nueva" / "programa" / "EntornoLab.exe").read_bytes() == b"ESTUDIO 1.1.0"


def test_restos_en_uso_de_un_intento_anterior_se_apartan(entorno):
	"""Un fichero de la extracción anterior abierto por otro proceso: se aparta y se sigue."""
	crear_instalacion(entorno["instalacion"])
	_publicar(entorno)
	config = _config(entorno)
	# Una DLL cargada no se deja borrar, pero su carpeta sí se deja apartar.
	viejo = config.carpeta_trabajo / "nueva" / "programa" / "lib" / "viejo.dll"
	viejo.parent.mkdir(parents=True)
	viejo.write_bytes((entorno["instalacion"] / "lib" / "prueba.dll").read_bytes())
	bloqueo = bloquear(viejo, "dll")
	entorno["procesos"].append(bloqueo)
	info = actualizador.comprobar(config)
	actualizador.descargar_y_preparar(config, info)
	assert not (config.carpeta_trabajo / "nueva" / "programa" / "lib" / "viejo.dll").exists()
	apartados = list(config.carpeta_por_borrar.iterdir())
	assert len(apartados) == 1
	bloqueo.kill()
	bloqueo.wait()
	actualizador.limpiar_trabajo(config)
	assert not config.carpeta_por_borrar.exists()


def test_restos_que_ni_se_borran_ni_se_apartan_dan_un_mensaje_claro(entorno, monkeypatch):
	crear_instalacion(entorno["instalacion"])
	config = _config(entorno)
	nueva = config.carpeta_trabajo / "nueva"
	nueva.mkdir(parents=True)
	monkeypatch.setattr(actualizador, "borrar_carpeta", lambda ruta, intentos=4: False)
	monkeypatch.setattr(actualizador, "_apartar", lambda ruta, destino: None)
	with pytest.raises(actualizador.ErrorActualizacion) as error:
		actualizador.extraer_seguro(crear_zip(entorno["instalacion"].parent / "v.zip", archivos_version("1.1.0")), nueva, config)
	assert "data\\temp\\actualizacion" in str(error.value)


def test_limpiar_con_una_dll_cargada_por_otro_proceso(entorno, monkeypatch):
	"""Una DLL de la versión anterior que otro proceso tiene cargada: no se borra hasta que la suelta."""
	crear_instalacion(entorno["instalacion"])
	config = _config(entorno)
	resto = config.carpeta_por_borrar / "version_anterior-1" / "lib"
	resto.mkdir(parents=True)
	(resto / "prueba.dll").write_bytes((entorno["instalacion"] / "lib" / "prueba.dll").read_bytes())
	bloqueo = bloquear(resto / "prueba.dll", "dll")
	entorno["procesos"].append(bloqueo)
	programados: list[Path] = []
	monkeypatch.setattr(actualizador, "programar_borrado_al_reiniciar", lambda ruta: programados.append(ruta) or False)
	actualizador.limpiar_trabajo(config)
	assert (resto / "prueba.dll").exists() and programados == [config.carpeta_por_borrar]
	bloqueo.kill()
	bloqueo.wait()
	assert esperar(lambda: (actualizador.limpiar_trabajo(config), not config.carpeta_por_borrar.exists())[1], 10)


def test_borrado_al_reiniciar_sin_permisos_de_administrador(tmp_path):
	"""MoveFileEx con MOVEFILE_DELAY_UNTIL_REBOOT exige ser administrador; sin serlo, se informa y se sigue."""
	import ctypes

	if ctypes.windll.shell32.IsUserAnAdmin():
		pytest.skip("Con permisos de administrador se programaría un borrado REAL en el registro de este equipo")
	resto = tmp_path / "resto"
	resto.mkdir()
	(resto / "a.txt").write_bytes(b"x")
	assert actualizador.programar_borrado_al_reiniciar(resto) is False


# ── Recuperación al arrancar ─────────────────────────────────────────────────


def _diario(config: actualizador.Configuracion, estado: str = "aplicando") -> None:
	config.carpeta_trabajo.mkdir(parents=True, exist_ok=True)
	config.diario.write_text(f"estado={estado}\nversion=1.1.0\nanterior=1.0.0\n", encoding="utf-8")


def test_recuperacion_al_arrancar_lanza_recuperar_bat(entorno):
	crear_instalacion(entorno["instalacion"])
	config = _config(entorno)
	assert actualizador.recuperar_si_interrumpida(config, lambda ruta, argumentos: pytest.fail("sin diario no se lanza")) is False
	_diario(config)
	# El script dejó su PID al empezar y murió con el corte: ese PID ya no es un cmd.exe vivo.
	config.pid_script.write_text("4", encoding="utf-8")  # el proceso System: nunca es un cmd.exe
	lanzados: list[tuple[Path, list[str]]] = []
	assert actualizador.recuperar_si_interrumpida(config, lambda ruta, argumentos: lanzados.append((ruta, argumentos))) is True
	assert lanzados == [(config.script_recuperar, [str(os.getpid())])]
	texto = config.script_recuperar.read_text(encoding="utf-8")
	assert 'set "MODO=recuperar"' in texto and 'set "VERSION_NUEVA=1.1.0"' in texto
	assert config.motor.is_file()
	# Mientras hay una sustitución a medias no se limpia nada: hace falta para recuperarla.
	actualizador.limpiar_trabajo(config)
	assert config.diario.is_file() and config.script_recuperar.is_file()


def test_no_se_interviene_si_el_script_sigue_en_marcha(entorno):
	crear_instalacion(entorno["instalacion"])
	config = _config(entorno)
	_diario(config)
	cmd = subprocess.Popen(["cmd.exe", "/d", "/c", "ping -n 30 127.0.0.1 >nul"], creationflags=0x08000000)
	entorno["procesos"].append(cmd)
	time.sleep(0.5)
	config.pid_script.write_text(str(cmd.pid), encoding="utf-8")
	assert actualizador.script_en_marcha(config)
	assert actualizador.recuperar_si_interrumpida(config, lambda ruta, argumentos: pytest.fail("no se lanza")) is False
	cmd.kill()
	cmd.wait()
	assert not actualizador.script_en_marcha(config)  # tras un corte el PID ya no está vivo


def test_no_se_relanza_una_recuperacion_que_ya_fallo(entorno):
	crear_instalacion(entorno["instalacion"])
	config = _config(entorno)
	_diario(config, "restaurando")
	config.archivo_resultado.write_text("estado=rota\nmotivo=restauracion_incompleta\nversion=1.1.0\nanterior=1.0.0\n", encoding="utf-8")
	assert actualizador.recuperar_si_interrumpida(config, lambda ruta, argumentos: pytest.fail("no se relanza")) is False
	mensaje = actualizador.leer_resultado_anterior(config)
	assert "recuperar.bat" in mensaje and "1.0.0" in mensaje


# ── El mensaje que ve el usuario al volver a abrir ───────────────────────────


@pytest.mark.parametrize(("estado", "motivo", "archivo", "fragmentos", "saltada"), [
	("correcta", "ninguno", "", None, ""),
	("revertida", "se_cerro_sin_confirmar", "", ["no arrancó correctamente", "1.0.0"], "1.1.0"),
	("revertida", "fichero_bloqueado", "lib\\modulo.txt", ["lib\\modulo.txt", "antivirus", "Sigue en la versión 1.0.0"], ""),
	("no_aplicada", "fichero_bloqueado", "", ["un archivo de EntornoLab", "Sigue en la versión 1.0.0"], ""),
	("no_aplicada", "sin_permiso", "lib", ["Archivos de programa", "Sigue en la versión 1.0.0"], ""),
	("revertida", "sin_espacio", "", ["disco se ha llenado", "Sigue en la versión 1.0.0"], ""),
	("no_aplicada", "ruta_larga", "", ["ruta más corta", "Sigue en la versión 1.0.0"], ""),
	("revertida", "interrumpida", "", ["corte de luz", "Sigue en la versión 1.0.0"], ""),
	("revertida", "fallo_copia", "lib", ["No se pudo terminar", "1.0.0"], ""),
	("no_aplicada", "la_aplicacion_no_se_cerro", "", ["seguían abiertos"], ""),
	("rota", "restauracion_incompleta", "lib\\x", ["recuperar.bat", "1.0.0"], ""),
])  # fmt: skip
def test_mensaje_al_volver_a_abrir(entorno, estado, motivo, archivo, fragmentos, saltada):
	crear_instalacion(entorno["instalacion"])
	config = _config(entorno)
	config.carpeta_trabajo.mkdir(parents=True, exist_ok=True)
	config.archivo_resultado.write_text(
		f"estado={estado}\nmotivo={motivo}\nversion=1.1.0\nanterior=1.0.0\narchivo={archivo}\n", encoding="utf-8"
	)
	mensaje = actualizador.leer_resultado_anterior(config)
	if fragmentos is None:
		assert mensaje is None
	else:
		assert "1.1.0" in mensaje, mensaje
		for fragmento in fragmentos:
			assert fragmento in mensaje, mensaje
	# Solo se salta la versión cuando no arrancó: un fallo pasajero se puede reintentar.
	assert actualizador.version_saltada() == saltada


# ════════════════════════════════════════════════════════════════════════════
# Lentos: el .bat de verdad
# ════════════════════════════════════════════════════════════════════════════

lento = pytest.mark.lento


@lento
def test_actualizacion_correcta(entorno):
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	usuario_antes = huellas(instalacion, programa=False)
	config, _script = _ejecutar(entorno)
	resultado = _leer_resultado(config)
	assert resultado.get("estado") == "correcta", _registro(config)
	_assert_version_entera(instalacion, "1.1.0")
	assert huellas(instalacion, programa=False) == usuario_antes
	assert (instalacion / "data" / "sounds" / "aviso.wav").read_bytes() == b"sonido 1.1.0"
	assert "1.1.0|--tras-actualizar|ok" in _arranques(instalacion)
	assert not config.carpeta_respaldo.exists() and not config.diario.exists()
	assert esperar(lambda: not (config.carpeta_trabajo / "actualizar.bat").exists(), 10)
	assert actualizador.leer_resultado_anterior(config) is None


@lento
def test_la_version_nueva_no_arranca_y_se_vuelve_atras(entorno):
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	programa_antes, usuario_antes = huellas(instalacion, programa=True), huellas(instalacion, programa=False)
	config, _script = _ejecutar(entorno, "falla")
	resultado = _leer_resultado(config)
	assert (resultado.get("estado"), resultado.get("motivo")) == ("revertida", "se_cerro_sin_confirmar"), _registro(config)
	_assert_anterior_intacta(instalacion, programa_antes)
	assert huellas(instalacion, programa=False) == usuario_antes
	assert esperar(lambda: "1.0.0||ok" in _arranques(instalacion), 20), _arranques(instalacion) + _registro(config)
	assert "comprobada" in _registro(config)
	mensaje = actualizador.leer_resultado_anterior(config)
	assert "no arrancó" in mensaje and "1.0.0" in mensaje


@lento
def test_solo_lectura_y_restos_de_otra_vez(entorno):
	"""Ficheros y carpetas de solo lectura en el programa, una copia de seguridad vieja y restos en «nueva»."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	for relativa in ("EntornoLab.exe", "lib/modulo.txt", "lib/prueba.dll", "lib/paquete/data/interno.txt"):
		(instalacion / relativa).chmod(0o444)
	(instalacion / "lib" / "paquete").chmod(0o555)
	vieja = instalacion / "data" / "temp" / "version_anterior" / "programa"
	vieja.mkdir(parents=True)
	(vieja / "EntornoLab.exe").write_bytes(b"ESTUDIO 0.5.0")  # nunca debe volver a su sitio
	(vieja / "EntornoLab.exe").chmod(0o444)
	_solo_lectura(instalacion / "data" / "temp" / "actualizacion" / "nueva" / "programa" / "copia_vieja")
	usuario_antes = huellas(instalacion, programa=False)
	config, _script = _ejecutar(entorno)
	assert _leer_resultado(config).get("estado") == "correcta", _registro(config)
	_assert_version_entera(instalacion, "1.1.0")
	assert huellas(instalacion, programa=False) == usuario_antes
	assert not config.carpeta_respaldo.exists()


@lento
def test_fichero_en_uso_sin_compartir_no_toca_nada(entorno):
	"""Otro proceso tiene abierto lib\\modulo.txt sin compartir y no lo suelta: no se aplica."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	programa_antes, usuario_antes = huellas(instalacion, programa=True), huellas(instalacion, programa=False)

	bloqueos: list[subprocess.Popen] = []

	def poner(_config):
		bloqueos.append(bloquear(instalacion / "lib" / "modulo.txt", "exclusivo"))
		entorno["procesos"].append(bloqueos[0])

	config, _script = _ejecutar(entorno, preparar=poner)
	resultado = _leer_resultado(config)
	assert (resultado.get("estado"), resultado.get("motivo")) == ("no_aplicada", "fichero_bloqueado"), _registro(config)
	assert resultado.get("archivo") == "lib\\modulo.txt"
	assert "se reintenta con espera creciente" in _registro(config)
	# La que había se vuelve a abrir enseguida (aún con el fichero bloqueado).
	assert esperar(lambda: "1.0.0||" in _arranques(instalacion), 20)
	bloqueos[0].kill()
	bloqueos[0].wait()
	assert huellas(instalacion, programa=True) == programa_antes
	assert huellas(instalacion, programa=False) == usuario_antes
	assert not config.diario.exists()
	mensaje = actualizador.leer_resultado_anterior(config)
	assert "lib\\modulo.txt" in mensaje and "Sigue en la versión 1.0.0" in mensaje
	assert actualizador.version_saltada() == ""  # se puede reintentar


@lento
def test_fichero_en_uso_un_momento_se_reintenta(entorno):
	"""El antivirus o el indexador lo sueltan enseguida: con la espera creciente, se actualiza."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)

	def poner(_config):
		entorno["procesos"].append(bloquear(instalacion / "lib" / "modulo.txt", "exclusivo", segundos=8))

	config, _script = _ejecutar(entorno, preparar=poner, reintentos_bloqueo=7)
	assert _leer_resultado(config).get("estado") == "correcta", _registro(config)
	assert "Hecho tras" in _registro(config)
	_assert_version_entera(instalacion, "1.1.0")


@lento
def test_dll_cargada_por_otro_proceso(entorno):
	"""Una DLL de lib cargada por otro programa: no se puede sobrescribir ni borrar, pero sí renombrar."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	usuario_antes = huellas(instalacion, programa=False)
	cargada: list[subprocess.Popen] = []

	def poner(_config):
		cargada.append(bloquear(instalacion / "lib" / "prueba.dll", "dll"))
		entorno["procesos"].append(cargada[0])

	config, _script = _ejecutar(entorno, preparar=poner)
	assert _leer_resultado(config).get("estado") == "correcta", _registro(config)
	_assert_version_entera(instalacion, "1.1.0")
	assert huellas(instalacion, programa=False) == usuario_antes
	# La DLL vieja sigue cargada: queda apartada y se borra cuando el otro proceso la suelta.
	restos = [ruta for ruta in (config.carpeta_respaldo, config.carpeta_por_borrar) if ruta.exists()]
	assert restos, _registro(config)
	cargada[0].kill()
	cargada[0].wait()
	assert esperar(lambda: (actualizador.limpiar_trabajo(config), not any(ruta.exists() for ruta in restos))[1], 15)


@lento
def test_carpeta_con_un_fichero_en_uso(entorno):
	"""lib tiene abierto un fichero que la versión nueva ya no trae: la carpeta se sustituye fichero a fichero."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)

	def poner(_config):
		entorno["procesos"].append(bloquear(instalacion / "lib" / "solo_1.0.0.txt", "compartido"))

	config, _script = _ejecutar(entorno, preparar=poner)
	assert _leer_resultado(config).get("estado") == "correcta", _registro(config)
	registro = _registro(config)
	assert "fichero a fichero" in registro and "se deja donde esta" in registro
	esperadas = huellas_esperadas("1.1.0")
	actuales = huellas(instalacion, programa=True)
	assert actuales.pop("lib/solo_1.0.0.txt")  # el resto en uso se queda (no estorba)
	assert actuales == esperadas
	assert comprobar_arranque(instalacion) == (0, "VERSION 1.1.0 ok")


@lento
def test_sin_permiso_para_mover_un_fichero(entorno):
	"""Permiso de borrar denegado (icacls) en un fichero del programa: no se aplica y no se toca nada."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	programa_antes = huellas(instalacion, programa=True)

	def poner(_config):
		# Borrar (y por tanto renombrar) un fichero se permite si lo permite el fichero O su carpeta:
		# se niega en los dos.
		for ruta, permisos in ((instalacion / "lib" / "modulo.txt", "(DE)"), (instalacion / "lib", "(DC)")):
			denegar(ruta, permisos)
			entorno["denegados"].append(ruta)

	config, _script = _ejecutar(entorno, preparar=poner, reintentos_bloqueo=1)
	resultado = _leer_resultado(config)
	assert (resultado.get("estado"), resultado.get("motivo")) == ("no_aplicada", "sin_permiso"), _registro(config)
	assert huellas(instalacion, programa=True) == programa_antes
	assert "Archivos de programa" in actualizador.leer_resultado_anterior(config)


@lento
def test_fallo_a_mitad_de_la_sustitucion_vuelve_atras(entorno):
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	programa_antes, usuario_antes = huellas(instalacion, programa=True), huellas(instalacion, programa=False)
	config, _script = _ejecutar(entorno, punto_de_fallo="aplicar")
	resultado = _leer_resultado(config)
	assert (resultado.get("estado"), resultado.get("motivo")) == ("revertida", "fallo_copia"), _registro(config)
	assert "PRUEBA: fallo forzado" in _registro(config)
	_assert_anterior_intacta(instalacion, programa_antes)
	assert huellas(instalacion, programa=False) == usuario_antes
	assert esperar(lambda: "1.0.0||ok" in _arranques(instalacion), 20), _arranques(instalacion) + _registro(config)
	assert "No se pudo terminar" in actualizador.leer_resultado_anterior(config)


@lento
def test_corte_de_luz_a_mitad_y_recuperacion_al_arrancar(entorno):
	"""Se mata el script a mitad (como un corte de luz); al arrancar, la aplicación lo deshace."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	programa_antes, usuario_antes = huellas(instalacion, programa=True), huellas(instalacion, programa=False)
	config, script = _ejecutar(entorno, punto_de_fallo="pausa", esperar_fin=False)
	assert esperar(lambda: "PRUEBA: pausa" in _registro(config), 90), _registro(config)
	subprocess.run(["taskkill", "/F", "/T", "/PID", str(script.pid)], capture_output=True, check=False)
	script.wait(timeout=30)
	# Instalación a medias: la versión que hay no está entera.
	assert config.diario.is_file()
	codigo, salida = comprobar_arranque(instalacion)
	assert codigo == 1 and "MEZCLA" in salida, salida
	assert not actualizador.script_en_marcha(config)
	# «Siguiente arranque»: la aplicación ve el diario y lanza recuperar.bat, que espera a que se cierre.
	app = _proceso_de_la_app(entorno, 2)
	recuperacion: list[subprocess.Popen] = []

	def lanzar(ruta, _argumentos):
		recuperacion.append(actualizador.lanzar_sustitucion(ruta, [str(app.pid)]))
		entorno["procesos"].append(recuperacion[0])

	assert actualizador.recuperar_si_interrumpida(_config(entorno), lanzar)
	recuperacion[0].wait(timeout=180)
	resultado = _leer_resultado(config)
	assert (resultado.get("estado"), resultado.get("motivo")) == ("revertida", "interrumpida"), _registro(config)
	_assert_anterior_intacta(instalacion, programa_antes)
	assert huellas(instalacion, programa=False) == usuario_antes
	assert not config.diario.exists()
	assert esperar(lambda: "1.0.0||ok" in _arranques(instalacion), 20), _arranques(instalacion) + _registro(config)
	mensaje = actualizador.leer_resultado_anterior(config)
	assert "corte de luz" in mensaje and "Sigue en la versión 1.0.0" in mensaje


@lento
def test_recuperar_bat_a_mano_sin_la_aplicacion(entorno):
	"""Si la aplicación no llegara a arrancar, recuperar.bat con doble clic deshace la sustitución."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	programa_antes = huellas(instalacion, programa=True)
	config, script = _ejecutar(entorno, punto_de_fallo="pausa", esperar_fin=False)
	assert esperar(lambda: "PRUEBA: pausa" in _registro(config), 90), _registro(config)
	subprocess.run(["taskkill", "/F", "/T", "/PID", str(script.pid)], capture_output=True, check=False)
	script.wait(timeout=30)
	assert config.script_recuperar.is_file()
	a_mano = subprocess.Popen(
		["cmd.exe", "/d", "/c", ".\\" + config.script_recuperar.name], cwd=config.carpeta_trabajo, creationflags=0x08000000
	)
	entorno["procesos"].append(a_mano)
	a_mano.wait(timeout=180)
	assert _leer_resultado(config).get("estado") == "revertida", _registro(config)
	_assert_anterior_intacta(instalacion, programa_antes)


@lento
def test_reproductor_abierto_que_se_cierra_durante_la_espera(entorno):
	"""Un reproductor (o el que lanzó la sala) sigue abierto: el script espera, sin matarlo, y luego actualiza."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	reproductor = subprocess.Popen([PYTHON_SIN_VENTANA, "-c", "import time; time.sleep(6)", str(instalacion / "EntornoLabJugar.exe")])
	entorno["procesos"].append(reproductor)
	config, _script = _ejecutar(entorno)
	assert _leer_resultado(config).get("estado") == "correcta", _registro(config)
	assert "se espera a que se cierre" in _registro(config)
	assert reproductor.wait(timeout=10) == 0  # terminó solo: nadie lo mató
	_assert_version_entera(instalacion, "1.1.0")


@lento
def test_reproductor_que_no_se_cierra_cancela_sin_tocar_nada(entorno):
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	programa_antes = huellas(instalacion, programa=True)
	reproductor = subprocess.Popen([PYTHON_SIN_VENTANA, "-c", "import time; time.sleep(120)", str(instalacion / "EntornoLabJugar.exe")])
	entorno["procesos"].append(reproductor)
	config, _script = _ejecutar(entorno, espera_cierre=4)
	resultado = _leer_resultado(config)
	assert (resultado.get("estado"), resultado.get("motivo")) == ("no_aplicada", "la_aplicacion_no_se_cerro"), _registro(config)
	assert reproductor.poll() is None, "el script nunca mata al reproductor"
	assert huellas(instalacion, programa=True) == programa_antes


@lento
def test_segundo_estudio_abierto(entorno):
	"""Otro Estudio de la misma carpeta abierto unos segundos más: se espera a que se cierre."""
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion)
	otro = subprocess.Popen([PYTHON_SIN_VENTANA, "-c", "import time; time.sleep(5)", str(instalacion / "EntornoLab.exe")])
	entorno["procesos"].append(otro)
	config, _script = _ejecutar(entorno, vida_app=1)
	assert _leer_resultado(config).get("estado") == "correcta", _registro(config)
	_assert_version_entera(instalacion, "1.1.0")


@lento
def test_rutas_de_mas_de_260_caracteres(entorno):
	if not actualizador.rutas_largas_activadas():
		pytest.skip("Windows no tiene activadas las rutas largas (LongPathsEnabled): no se puede crear la instalación de prueba")
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion, hondo=HONDO)
	assert max(len(str(ruta)) for ruta in instalacion.rglob("*")) > 260
	usuario_antes = huellas(instalacion, programa=False)
	config, _script = _ejecutar(entorno, hondo=HONDO)
	assert _leer_resultado(config).get("estado") == "correcta", _registro(config)
	assert huellas(instalacion, programa=True) == huellas_esperadas("1.1.0", HONDO)
	assert huellas(instalacion, programa=False) == usuario_antes


@lento
def test_rutas_largas_y_vuelta_atras(entorno):
	if not actualizador.rutas_largas_activadas():
		pytest.skip("Windows no tiene activadas las rutas largas (LongPathsEnabled)")
	instalacion = entorno["instalacion"]
	crear_instalacion(instalacion, hondo=HONDO)
	programa_antes = huellas(instalacion, programa=True)
	config, _script = _ejecutar(entorno, "falla", hondo=HONDO)
	assert _leer_resultado(config).get("estado") == "revertida", _registro(config)
	assert huellas(instalacion, programa=True) == programa_antes
