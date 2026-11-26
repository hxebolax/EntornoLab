"""Pruebas del empaquetado SIN compilar: verificador, lista de data, .bat y .gitignore.

``tools/verificar_build.py`` se prueba contra un árbol de compilación falso
creado en una carpeta temporal.
"""

from __future__ import annotations

import importlib.util
import shutil
from pathlib import Path

import pytest

from app.core.version import EJECUTABLE_ESTUDIO, EJECUTABLE_REPRODUCTOR
from tools import verificar_build

from .conftest import RAIZ

ORDENES_DEL_BAT = [
	"crear",
	"instalar",
	"actualizar",
	"ejecutar",
	"depurar",
	"jugar",
	"pruebas",
	"comprobar",
	"sonidos",
	"ejemplos",
	"idiomas",
	"compilar",
	"compilar-debug",
	"empaquetar",
	"limpiar",
	"datos",
	"registros",
	"diagnostico",
	"congelar",
]


def _tocar(ruta: Path, contenido: bytes = b"x") -> None:
	ruta.parent.mkdir(parents=True, exist_ok=True)
	ruta.write_bytes(contenido)


@pytest.fixture
def compilacion(tmp_path) -> Path:
	"""Árbol mínimo de una compilación correcta y limpia."""
	destino = tmp_path / "entornolab"
	for nombre in (EJECUTABLE_ESTUDIO, EJECUTABLE_REPRODUCTOR, *verificar_build.RUNTIMES_VC, *verificar_build.ARCHIVOS_RAIZ):
		_tocar(destino / nombre)
	for paquete in verificar_build.PAQUETES_OBLIGATORIOS:
		_tocar(destino / "lib" / paquete / "__init__.pyc")
	for paquete, recursos in verificar_build.RECURSOS_DE_PAQUETES.items():
		_tocar(destino / "lib" / paquete / "__init__.pyc")
		for recurso in recursos:
			_tocar(destino / "lib" / recurso)
	for paquete in verificar_build.PAQUETES_APP:
		_tocar(destino / "lib" / paquete / "__init__.pyc")
	for relativo in verificar_build.DATA_OBLIGATORIO:
		_tocar(destino / "data" / relativo)
	_tocar(destino / "data" / "bin" / "openal" / "hrtf" / "ku100.mhr")
	_tocar(destino / "data" / "sounds" / "pasos" / "baldosa_1.flac")
	_tocar(destino / "data" / "sounds" / "pasos" / "pack.json")
	_tocar(destino / "data" / "plugins" / "hogar" / "mesa" / "complemento.json")
	_tocar(destino / "data" / "locales" / "en" / "LC_MESSAGES" / "entornolab.po")
	_tocar(destino / "data" / "locales" / "en" / "LC_MESSAGES" / "entornolab.mo")
	_tocar(destino / "data" / "ejemplos" / "casa.elab")
	return destino


def test_compilacion_correcta_no_tiene_problemas(compilacion):
	assert verificar_build.verificar(compilacion) == []
	assert verificar_build.main([str(compilacion)]) == 0
	assert verificar_build.ejecutables_por_defecto() == (EJECUTABLE_ESTUDIO, EJECUTABLE_REPRODUCTOR)


@pytest.mark.parametrize(
	("relativo", "pista"),
	[
		(EJECUTABLE_ESTUDIO, EJECUTABLE_ESTUDIO),
		(EJECUTABLE_REPRODUCTOR, EJECUTABLE_REPRODUCTOR),
		("vcruntime140_1.dll", "Visual C++"),
		("lib/wx/locale/es/LC_MESSAGES/wxstd.mo", "wxstd.mo"),
		("lib/accessible_output2/lib/nvdaControllerClient64.dll", "nvdaControllerClient64.dll"),
		("lib/pygame/SDL2.dll", "SDL2.dll"),
		("lib/basskit/data/dlls/x64/bass.dll", "bass.dll"),
		("LICENSE.txt", "LICENSE.txt"),
		("data/docs/licencias/BASS.txt", "BASS.txt"),
		("data/bin/openal/soft_oal.dll", "soft_oal.dll"),
		("data/docs/manual.md", "manual.md"),
		("data/sounds/pasos/baldosa_1.flac", "ningún sonido"),
		("data/locales/en/LC_MESSAGES/entornolab.mo", "catálogo compilado"),
		("lib/certifi/cacert.pem", "cacert.pem"),
		("lib/markdown/extensions", "lib/markdown/extensions"),
		("lib/app/reproductor/pantallas", "lib/app/reproductor/pantallas"),
		("lib/app/actividades", "lib/app/actividades"),
		("data/bin/openal/hrtf/ku100.mhr", "HRTF"),
		("data/bin/openal/alsoft.ini", "alsoft.ini"),
		("data/sounds/catalogo.json", "catalogo.json"),
		("data/sounds/pasos/pack.json", "pack.json"),
		("data/plugins/hogar/mesa/complemento.json", "complemento"),
		("data/ejemplos/casa.elab", "ejemplo"),
	],
)
def test_detecta_lo_que_falta(compilacion, relativo, pista):
	objetivo = compilacion / relativo
	if objetivo.is_dir():
		shutil.rmtree(objetivo)
	else:
		objetivo.unlink()
	problemas = verificar_build.verificar(compilacion)
	assert len(problemas) == 1 and pista in problemas[0], problemas
	assert verificar_build.main([str(compilacion)]) == 1


@pytest.mark.parametrize(
	"relativo",
	[
		"data/config/config.json",
		"data/logs/sesion_20260101_000000.log",
		"data/db/entornolab.db",
		"data/sessions/abc.json.gz",
		"data/entornos/mi_centro.elab",
		"data/cache/x.bin",
		"data/temp/buzon.txt",
		"data/backups/copia.zip",
	],
)
def test_detecta_datos_personales_en_la_distribucion(compilacion, relativo):
	_tocar(compilacion / relativo)
	problemas = verificar_build.verificar(compilacion)
	assert any("NO debe distribuirse" in problema for problema in problemas), problemas


def test_detecta_archivos_sospechosos_caches_y_herramientas(compilacion):
	_tocar(compilacion / "data" / "docs" / "notas.log")
	_tocar(compilacion / "data" / "plugins" / "mobiliario" / "__pycache__" / "x.pyc")
	_tocar(compilacion / "lib" / "pytest" / "__init__.pyc")
	problemas = "\n".join(verificar_build.verificar(compilacion))
	assert "Archivo sospechoso" in problemas and "notas.log" in problemas
	assert "Caché de Python" in problemas
	assert "lib/pytest" in problemas


def test_carpeta_inexistente(tmp_path):
	problemas = verificar_build.verificar(tmp_path / "no_existe")
	assert len(problemas) == 1 and "No existe" in problemas[0]


def _cargar_setup_cx():
	"""Importa setup_cx.py sin lanzar la compilación (solo se ejecuta bajo ``__main__``)."""
	especificacion = importlib.util.spec_from_file_location("setup_cx_en_pruebas", RAIZ / "setup_cx.py")
	modulo = importlib.util.module_from_spec(especificacion)
	especificacion.loader.exec_module(modulo)
	return modulo


def test_setup_cx_no_empaqueta_nada_personal_ni_basura():
	setup_cx = _cargar_setup_cx()
	assert setup_cx.DATA_PROHIBIDO == verificar_build.DATA_PROHIBIDO, "el compilador y el verificador aplican la misma lista"
	destinos = [destino for _origen, destino in setup_cx.archivos_de_data()]
	assert destinos, "data/ debe aportar archivos a la distribución"
	for destino in destinos:
		partes = Path(destino).parts
		assert partes[0] == "data" and partes[1] in setup_cx.DATA_DISTRIBUIBLE
		assert partes[1] not in setup_cx.DATA_PROHIBIDO
		assert not destino.endswith((".gitkeep", ".pyc", ".log", ".db", ".bak", ".tmp"))
	assert "data/docs/manual.md" in destinos
	# Las traducciones viajan compiladas: el .mo sí, el .po y la plantilla .pot no.
	assert not [destino for destino in destinos if destino.endswith((".po", ".pot"))]
	# Los .mo no se versionan: los genera tools/antes_de_compilar.py al compilar. En un
	# clon recién descargado todavía no existen; si existen, tienen que viajar.
	for po in (RAIZ / "data" / "locales").glob("*/LC_MESSAGES/*.po"):
		mo = po.with_suffix(".mo")
		if mo.is_file():
			assert mo.relative_to(RAIZ).as_posix() in destinos
	assert "compilar_traducciones" in (RAIZ / "tools" / "antes_de_compilar.py").read_text(encoding="utf-8")
	assert "data/sounds/catalogo.json" in destinos
	assert any(destino.startswith("data/bin/openal/hrtf/") for destino in destinos)
	assert setup_cx.leer_version() == _cargar_version()


@pytest.mark.lento
def test_comprobar_motores_falla_sin_compilacion(tmp_path):
	"""``--motores`` lanza un Python aislado; sin compilación termina con error, no con éxito."""
	assert verificar_build.main([verificar_build.ORDEN_MOTORES, str(tmp_path / "no_existe")]) != 0


def test_entorno_bat_prueba_la_compilacion_con_su_data_y_sus_motores():
	texto = (RAIZ / "entorno.bat").read_bytes().decode("utf-8")
	bloque = texto.split("\r\n:COMPROBAR_BUILD\r\n", 1)[1].split("\r\n:", 1)[0]
	assert "robocopy" in bloque and "comprobacion_data" in bloque
	assert "--comprobar-arranque" in bloque and "verificar_build.py --motores" in bloque


def test_detecta_avisos_de_licencia_enlazados_que_no_viajan(compilacion):
	(compilacion / "data" / "docs" / "licencias" / "LEEME.md").write_text("- [BASS](BASS.txt)\n- [Otra](otra.txt)\n", encoding="utf-8")
	problemas = verificar_build.verificar(compilacion)
	assert len(problemas) == 1 and "otra.txt" in problemas[0], problemas


def _cargar_version() -> str:
	from app.core.version import APP_VERSION

	return APP_VERSION


def test_setup_cx_incluye_los_paquetes_con_dll_fuera_del_zip():
	setup_cx = _cargar_setup_cx()
	paquetes, includes = setup_cx.paquetes_finales()
	for necesario in ("wx", "app", "pygame", "numpy", "accessible_output2", "cryptography", "basskit", "certifi", "markdown"):
		assert necesario in paquetes, f"{necesario} debe ir completo en la compilación"
	# Cada paquete propio que el verificador exige se compila nombrado (y existe en el código).
	for paquete in verificar_build.PAQUETES_APP:
		assert paquete.replace("/", ".") in paquetes, f"{paquete} debe compilarse"
	assert {"sounddevice", "soundfile"} <= set(includes)
	texto = (RAIZ / "setup_cx.py").read_text(encoding="utf-8")
	assert '"zip_exclude_packages": ["*"]' in texto and '"zip_include_packages": []' in texto
	assert texto.count("Executable(") == 2, "dos ejecutables: el Estudio y el reproductor"
	assert "pytest" in setup_cx.EXCLUDES and "cx_Freeze" in setup_cx.EXCLUDES


def test_entorno_bat_tiene_todas_las_ordenes():
	texto = (RAIZ / "entorno.bat").read_bytes().decode("utf-8")
	assert texto.startswith("@echo off\r\n")
	assert "chcp 65001" in texto
	for orden in ORDENES_DEL_BAT:
		assert f'if /i "%ORDEN%"=="{orden}" call :' in texto, f"falta la orden {orden}"
	assert f'set "EXE={EJECUTABLE_ESTUDIO}"' in texto
	assert f'set "EXE_JUGAR={EJECUTABLE_REPRODUCTOR}"' in texto
	# Cada etiqueta llamada existe (un «call :X» sin etiqueta rompe el .bat al usar esa opción).
	import re

	etiquetas = set(re.findall(r"^:([A-Z_]+)\s*$", texto.replace("\r", ""), re.MULTILINE))
	llamadas = set(re.findall(r"call :([A-Z_]+)", texto)) | set(re.findall(r"goto ([A-Z_]+)", texto))
	assert llamadas <= etiquetas, f"etiquetas inexistentes: {llamadas - etiquetas}"


def test_gitignore_protege_lo_personal_sin_ocultar_los_recursos():
	lineas = {linea.strip() for linea in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()}
	for personal in ("config", "logs", "db", "sessions", "entornos", "cache", "temp", "backups"):
		assert f"data/{personal}/" in lineas, f"data/{personal} no debe versionarse"
	for recurso in ("ejemplos", "plugins", "sounds", "bin", "locales", "docs", "icons"):
		assert f"data/{recurso}/" not in lineas and f"data/{recurso}" not in lineas, f"data/{recurso} sí se versiona"
	assert "data/" not in lineas and "data/*" not in lineas


def test_bass_viaja_con_el_codigo_y_con_la_compilacion():
	"""La rueda de basskit está en __pip__, se instala con requirements.txt, no se ignora y se empaqueta."""
	ruedas = sorted((RAIZ / "__pip__").glob("basskit-*.whl"))
	assert len(ruedas) == 1, "debe haber una (y solo una) rueda de basskit en __pip__"
	requisitos = (RAIZ / "requirements.txt").read_text(encoding="utf-8").splitlines()
	assert f"__pip__/{ruedas[0].name}" in [linea.strip() for linea in requisitos], "requirements.txt instala la rueda de __pip__"
	assert ruedas[0].name.encode() in (RAIZ / "entorno.bat").read_bytes(), "entorno.bat comprueba esa misma rueda"
	ignorados = {linea.strip() for linea in (RAIZ / ".gitignore").read_text(encoding="utf-8").splitlines()}
	assert not ignorados & {"__pip__", "__pip__/", "__pip__/*", "*.whl", "__pip__/*.whl"}, "la rueda se versiona"
	setup_cx = _cargar_setup_cx()
	assert "basskit" in setup_cx.PAQUETES, "obligatorio: sin basskit no se compila"
	assert ("LICENSE", "LICENSE.txt") in setup_cx.ARCHIVOS_EXTRA
	assert "basskit" in verificar_build.PAQUETES_OBLIGATORIOS
	assert "basskit/data/dlls/x64/bass.dll" in verificar_build.RECURSOS_DE_PAQUETES["basskit"]


def test_la_compilacion_rechaza_el_basskit_completo(compilacion):
	_tocar(compilacion / "lib" / "basskit" / "data" / "dlls" / "x64" / "bass_fx.dll")
	_tocar(compilacion / "lib" / "basskit" / "data" / "ffmpeg" / "avcodec-62.dll")
	problemas = "\n".join(verificar_build.verificar(compilacion))
	assert "bass_fx.dll" in problemas and "avcodec-62.dll" in problemas
	# La DLL que sí viaja no se confunde con un complemento.
	assert "x64/bass.dll" not in problemas


def test_licencia_gpl_con_permiso_para_bass_y_avisos_de_terceros():
	licencia = (RAIZ / "LICENSE").read_text(encoding="utf-8")
	assert "EntornoLab" in licencia and "Copyright (C) 2026 Héctor J. Benítez Corredera" in licencia
	assert "PERMISO ADICIONAL PARA BASS" in licencia and "sección 7" in licencia
	assert "GNU GENERAL PUBLIC LICENSE" in licencia and "Version 3, 29 June 2007" in licencia
	assert "END OF TERMS AND CONDITIONS" in licencia
	carpeta = RAIZ / "data" / "docs" / "licencias"
	lista = (carpeta / "LEEME.md").read_text(encoding="utf-8")
	for fichero in (
		"BASS.txt",
		"basskit.txt",
		"OpenAL-Soft-LGPL.txt",
		"HRTF.txt",
		"pygame-ce.txt",
		"LGPL-2.1.txt",
		"wxPython.txt",
		"numpy.txt",
		"sounddevice-PortAudio.txt",
		"soundfile-libsndfile.txt",
		"accessible_output2.txt",
		"cryptography.txt",
		"markdown.txt",
	):
		assert (carpeta / fichero).is_file(), f"falta data/docs/licencias/{fichero}"
		assert f"({fichero})" in lista, f"LEEME.md no enlaza {fichero}"
	assert "uso no comercial" in lista
	assert "free for non-commercial use" in (carpeta / "BASS.txt").read_text(encoding="utf-8", errors="replace")
	# Viajan en la distribución: data/docs está en la lista blanca.
	destinos = [destino for _origen, destino in _cargar_setup_cx().archivos_de_data()]
	assert "data/docs/licencias/BASS.txt" in destinos and "data/docs/licencias/LEEME.md" in destinos


def test_paths_conoce_todas_las_carpetas_del_documento(data_temporal):
	from app.core import paths

	esperadas = {
		"plugins": paths.ruta_complementos,
		"sounds": paths.ruta_sonidos,
		"ejemplos": paths.ruta_ejemplos,
		"entornos": paths.ruta_entornos,
		"sessions": paths.ruta_sesiones,
		"db": paths.ruta_base_datos,
		"bin": paths.ruta_binarios,
		"locales": paths.ruta_traducciones,
		"docs": paths.ruta_documentacion,
		"config": paths.ruta_configuracion,
		"logs": paths.ruta_registros,
	}
	for nombre, funcion in esperadas.items():
		ruta = funcion()
		assert ruta == data_temporal / nombre and ruta.is_dir()
	assert paths.ruta_plugins is paths.ruta_complementos and paths.ruta_sessions is paths.ruta_sesiones
