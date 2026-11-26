"""Que nunca se vean rutas ni datos del equipo de DESARROLLO.

El autor no quiere que el repositorio, la compilación ni lo que se envía para
soporte lleven su carpeta de usuario, la de sus proyectos, la de su Python o su
entorno virtual, ni su nombre de usuario. Estas pruebas no escriben ninguna de
esas cadenas: las calculan al vuelo (``os.path.expanduser("~")``, el nombre de
usuario actual, la carpeta que contiene el proyecto y ``sys.base_prefix``), así
que sirven igual en cualquier equipo y en la integración continua.
"""

from __future__ import annotations

import getpass
import io
import logging
import os
import shutil
import sys
import traceback
import zipfile
from pathlib import Path

import pytest

from app.core import diagnostico, paths, registro

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ / "tools") not in sys.path:
	sys.path.insert(0, str(RAIZ / "tools"))

import comprobar_rutas  # noqa: E402 - necesita tools en sys.path

CASA = os.path.expanduser("~")
USUARIO = getpass.getuser()


def _hay_git() -> bool:
	return shutil.which("git") is not None and (RAIZ / ".git").exists()


# ── El repositorio ──────────────────────────────────────────────────────────


@pytest.mark.skipif(not _hay_git(), reason="hace falta git para saber qué ficheros se suben")
def test_el_repositorio_no_lleva_rutas_del_equipo():
	"""Lo que subiría git (versionado y nuevo no ignorado) está limpio: texto, binarios y dentro de los ZIP."""
	hallazgos = comprobar_rutas.comprobar_repositorio(RAIZ)
	assert not hallazgos, "Rutas o datos del equipo de desarrollo en el repositorio:\n" + "\n".join(map(str, hallazgos))


def test_se_buscan_las_cadenas_de_este_equipo():
	"""La lista sale del equipo, no del código: carpeta de usuario, Python, entorno y carpeta de los proyectos."""
	cadenas = {cadena.lower() for _que, cadena in comprobar_rutas.cadenas_del_equipo(RAIZ)}
	assert CASA.lower() in cadenas
	assert sys.base_prefix.lower().rstrip("\\/") in cadenas
	assert sys.prefix.lower().rstrip("\\/") in cadenas
	assert str(RAIZ.parent).lower().rstrip("\\/") in cadenas
	if len(USUARIO) >= 4 and USUARIO.lower() not in comprobar_rutas.NOMBRES_GENERICOS:
		assert USUARIO.lower() in cadenas


def test_ningun_codigo_ni_prueba_escribe_la_ruta_del_equipo():
	"""Ni las herramientas ni las pruebas llevan escrita la carpeta de usuario o la de los proyectos (deben leerla de un argumento)."""
	prohibidas = [CASA, str(RAIZ.parent)]
	culpables = []
	for carpeta in ("app", "tools", "tests"):
		for fichero in (RAIZ / carpeta).rglob("*.py"):
			if "__pycache__" in fichero.parts:
				continue
			texto = fichero.read_text(encoding="utf-8", errors="replace").lower()
			for ruta in prohibidas:
				for variante in (ruta, ruta.replace("\\", "/"), ruta.replace("\\", "\\\\")):
					if variante.lower() in texto:
						culpables.append(f"{fichero.relative_to(RAIZ).as_posix()}: {variante}")
	assert not culpables, culpables


# ── La herramienta ──────────────────────────────────────────────────────────


def test_la_herramienta_encuentra_rutas_en_texto_zip_y_binarios(tmp_path):
	carpeta = tmp_path / "revisar"
	carpeta.mkdir()
	(carpeta / "receta.json").write_text('{"carpeta": "' + CASA.replace("\\", "\\\\") + '\\\\fuentes"}\n', encoding="utf-8")
	(carpeta / "nota.md").write_text(f"Ver {RAIZ.parent}{os.sep}OtroProyecto\n", encoding="utf-8")
	# Una cuenta ficticia cualquiera también delata (es la ruta de alguien).
	(carpeta / "prueba.txt").write_text("C:" + "\\Users\\Fulanito\\x.txt\n", encoding="utf-8")
	with zipfile.ZipFile(carpeta / "entorno.elab", "w") as zip_:
		zip_.writestr("entorno.json", '{"origen": "' + sys.base_prefix.replace("\\", "/") + '/Lib"}')
	(carpeta / "biblioteca.dll").write_bytes(b"\x00MZ" + f"{CASA}\\depuracion.pdb".encode("utf-16-le") + b"\x00")
	hallazgos = comprobar_rutas.comprobar_carpeta(carpeta)
	ficheros = {hallazgo.fichero.split("!")[0] for hallazgo in hallazgos}
	assert {"receta.json", "nota.md", "prueba.txt", "entorno.elab", "biblioteca.dll"} <= ficheros, hallazgos
	assert comprobar_rutas.main(["--carpeta", str(carpeta)]) == 1


def test_la_herramienta_respeta_marcadores_y_lo_que_no_es_una_ruta(tmp_path):
	carpeta = tmp_path / "limpia"
	carpeta.mkdir()
	(carpeta / "manual.md").write_text(
		"Los datos van en %USERPROFILE%\\EntornoLab o en C:\\Users\\<usuario>\\Documentos.\n"
		"La carpeta pública es C:\\Users\\Public.\n"
		# El nombre de usuario dentro de una palabra más larga no es el nombre de usuario.
		f"https://github.com/x{USUARIO}x/proyecto\n"
		"Ejemplo justificado C:\\Users\\Mengano\\x  # comprobar_rutas: permitido\n",
		encoding="utf-8",
	)
	# Los binarios de terceros traen la ruta de depuración de QUIEN los compiló: no es del autor.
	(carpeta / "tercero.dll").write_bytes(b"\x00RSDS C:" + b"\\Users\\programador\\proyecto\\x.pdb\x00")
	assert comprobar_rutas.comprobar_carpeta(carpeta) == []
	assert comprobar_rutas.main(["--carpeta", str(carpeta)]) == 0


# ── El registro y el paquete de diagnóstico ─────────────────────────────────


def _traza_con_rutas_del_equipo() -> str:
	"""Una traza como la que daría el programa ejecutado desde el código fuente."""
	marcos = traceback.StackSummary.from_list(
		[
			(str(RAIZ / "app" / "ui" / "ventana.py"), 10, "al_guardar", "guardar()"),
			(str(Path(sys.prefix) / "Lib" / "site-packages" / "wx" / "core.py"), 20, "Bind", "x"),
			(str(Path(sys.base_prefix) / "Lib" / "json" / "decoder.py"), 30, "decode", "y"),
		]
	)
	return "Traceback (most recent call last):\n" + "".join(marcos.format()) + "ValueError: mal\n"


def test_las_trazas_solo_llevan_rutas_relativas():
	texto = registro.acortar_rutas_de_traza(_traza_con_rutas_del_equipo())
	assert 'File "app/ui/ventana.py", line 10' in texto
	assert 'File "wx/core.py", line 20' in texto
	assert 'File "json/decoder.py", line 30' in texto
	for ruta in (str(RAIZ), sys.prefix, sys.base_prefix, CASA):
		assert ruta.lower() not in texto.lower()


def test_el_registro_escribe_las_trazas_sin_rutas_del_equipo(tmp_path, monkeypatch):
	monkeypatch.delenv(registro.VARIABLE_DEPURACION, raising=False)
	logs = tmp_path / "logs"
	ganchos = (sys.excepthook, sys.unraisablehook)
	registro.configurar_registro("Prueba", "9.9.9", nivel="DEBUG", carpeta=logs)
	try:
		try:
			{}["no_existe"]
		except KeyError:
			logging.getLogger("app.prueba").exception("Falló a propósito")
		registro.detener_registro()
		texto = "\n".join(archivo.read_text(encoding="utf-8") for archivo in logs.glob("sesion_*.log"))
	finally:
		registro.detener_registro(cerrar_fallo_nativo=True)
		sys.excepthook, sys.unraisablehook = ganchos
		logging.captureWarnings(False)
	assert "Falló a propósito" in texto and "KeyError" in texto
	assert 'File "tests/test_sin_rutas_locales.py"' in texto
	assert f'File "{RAIZ}'.lower() not in texto.lower()


def test_anonimizar_sustituye_las_carpetas_del_equipo(data_temporal):
	"""Lo que se envía: carpeta del usuario → %USERPROFILE%, del programa → <carpeta del programa>, cuentas → <usuario>."""
	programa = paths.ruta_base()
	texto = "\n".join(
		[
			f"No se pudo abrir {CASA}\\Documentos\\casa.elab",
			f"Abierto {CASA.replace(chr(92), '/')}/Escritorio/plano.png",
			'{"ruta": "' + str(programa).replace("\\", "\\\\") + '\\\\data\\\\x.json"}',
			"Otra cuenta: C:" + "\\Users\\Fulanito\\Descargas\\x.zip",
			f"Sesión de {USUARIO} en {os.environ.get('COMPUTERNAME', 'equipo')}",
		]
	)
	anonimo = diagnostico.anonimizar(texto)
	assert "%USERPROFILE%\\Documentos\\casa.elab" in anonimo
	assert "%USERPROFILE%/Escritorio/plano.png" in anonimo
	assert "<carpeta del programa>" in anonimo
	assert "C:\\Users\\<usuario>\\Descargas" in anonimo and "Fulanito" not in anonimo
	assert CASA.lower() not in anonimo.lower() and str(programa).lower() not in anonimo.lower()
	if len(USUARIO) >= 3:
		assert USUARIO.lower() not in anonimo.lower(), anonimo


def test_el_paquete_de_diagnostico_no_lleva_rutas_ni_usuario(data_temporal, monkeypatch):
	"""Una ruta con el nombre de usuario en un registro no llega al paquete que se envía."""
	carpeta = paths.ruta_registros()
	carpeta.mkdir(parents=True, exist_ok=True)
	monkeypatch.setattr(registro, "carpeta_registros", lambda: carpeta)
	(carpeta / "sesion_20260101_000000.log").write_text(
		f"Abierto {CASA}{os.sep}Documents{os.sep}{USUARIO}_casa.elab\n"
		f"Datos en {paths.ruta_datos()} · programa en {paths.ruta_base()}\n" + _traza_con_rutas_del_equipo(),
		encoding="utf-8",
	)
	(carpeta / "incidencias.log").write_text(f"ERROR al guardar en {CASA}\\x.elab\n", encoding="utf-8")
	ruta = diagnostico.generar_paquete("Prueba", "9.9.9")
	with zipfile.ZipFile(ruta) as zip_:
		contenido = "\n".join(zip_.read(nombre).decode("utf-8") for nombre in zip_.namelist())
	for prohibida in (CASA, str(paths.ruta_base()), str(paths.ruta_datos()), sys.prefix, sys.base_prefix, str(RAIZ.parent)):
		assert prohibida.lower() not in contenido.lower(), prohibida
	if len(USUARIO) >= 3:
		assert USUARIO.lower() not in contenido.lower()
	assert "%USERPROFILE%" in contenido and "<carpeta de datos>" in contenido


# ── La compilación ──────────────────────────────────────────────────────────


def test_setup_cx_reemplaza_todas_las_rutas_y_relativiza_las_dll():
	import setup_cx

	reemplazos = setup_cx.rutas_a_reemplazar()
	assert reemplazos[0] == ("*", ""), "primero la regla general de cx_Freeze"
	buscadas = {Path(origen).resolve() for origen, _destino in reemplazos[1:]}
	assert Path(sys.prefix, "Lib", "site-packages").resolve() in buscadas
	assert Path(sys.base_prefix, "Lib").resolve() in buscadas and RAIZ in buscadas
	assert all(destino == "" for _origen, destino in reemplazos)
	sitio = Path(sys.prefix, "Lib", "site-packages").resolve()
	valor = os.pathsep.join(
		[str(sitio / "_sounddevice_data" / "portaudio-binaries"), str(sitio / "_sounddevice_data" / "portaudio-binaries"), "ya/relativa"]
	)
	assert setup_cx._libs_relativas(valor) == os.pathsep.join(["_sounddevice_data/portaudio-binaries", "ya/relativa"])
	assert "direct_url.json" in setup_cx.METADATOS_RETIRADOS and "RECORD" in setup_cx.METADATOS_RETIRADOS
	assert "METADATA" not in setup_cx.METADATOS_RETIRADOS, "importlib.metadata y el paquete de diagnóstico leen la versión"


def test_la_herramienta_mira_dentro_de_library_zip(tmp_path):
	"""Un dist-info con direct_url.json y un .pyc con co_filename absoluto, dentro de library.zip, se detectan."""
	lib = tmp_path / "compilacion" / "lib"
	lib.mkdir(parents=True)
	codigo = compile("x = 1", str(RAIZ / "app" / "modulo.py"), "exec")
	import marshal

	contenido = io.BytesIO()
	with zipfile.ZipFile(contenido, "w") as zip_:
		zip_.writestr("app/modulo.pyc", b"\x00" * 16 + marshal.dumps(codigo))
		zip_.writestr("paquete-1.0.dist-info/direct_url.json", '{"url": "file:///' + str(RAIZ).replace("\\", "/") + '/__pip__/x.whl"}')
	(lib / "library.zip").write_bytes(contenido.getvalue())
	hallazgos = comprobar_rutas.comprobar_carpeta(tmp_path / "compilacion")
	nombres = {hallazgo.fichero for hallazgo in hallazgos}
	assert "lib/library.zip!app/modulo.pyc" in nombres and "lib/library.zip!paquete-1.0.dist-info/direct_url.json" in nombres, nombres
