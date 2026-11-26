"""Prepara y publica una versión de EntornoLab en GitHub para el actualizador.

Uso (desde la raíz del proyecto, con la versión ya compilada en ``build/entornolab``)::

	python tools/publicar_version.py                    canal estable; prepara y EXPLICA cómo subirla
	python tools/publicar_version.py --canal pruebas    versión preliminar (publicación fija «pruebas»)
	python tools/publicar_version.py --subir            además la sube con «gh» (GitHub CLI)
	python tools/publicar_version.py --simular          no escribe nada en build/ ni llama a gh: solo dice qué haría

Qué hace:

1. Comprueba que la compilación está limpia (``verificar_build.py``): nunca se
   publica una versión con datos personales dentro.
2. Extrae las notas de la versión de ``data/docs/novedades.md``.
3. Crea ``EntornoLab_v<versión>.zip`` (todo bajo ``EntornoLab/``) y añade dentro
   ``data/plugins/de_serie.json``: la lista de complementos que viajan con la
   aplicación, para que el catálogo en línea distinga los de serie de los del usuario.
4. Escribe ``version.json`` (aplicación, versión, canal, fichero, SHA-256,
   tamaño, fecha, dirección de descarga y novedades) y lo FIRMA con la clave
   privada, que está fuera del proyecto (``tools/generar_claves.py``).
5. Verifica la firma con las claves públicas que lleva la aplicación: si no
   coincide, las instalaciones rechazarían la versión, así que se detiene.
6. Explica (o ejecuta, con ``--subir``) la publicación con ``gh release``.

De dónde lee la aplicación (``app/services/actualizador.py``):

- estable: ``https://github.com/hxebolax/EntornoLab/releases/latest/download/version.json``
  («latest» es la última publicación que no está marcada como preliminar);
- pruebas: ``https://github.com/hxebolax/EntornoLab/releases/download/pruebas/version.json``.

Detalles y lista de comprobación: ``docs/actualizaciones.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import tempfile
import zipfile
from datetime import date
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for _ruta in (str(RAIZ), str(RAIZ / "tools")):
	if _ruta not in sys.path:
		sys.path.insert(0, _ruta)

import firmar_version  # noqa: E402

from app.core import documentacion  # noqa: E402
from app.core.version import APP_VERSION, EJECUTABLE_ESTUDIO, EJECUTABLE_REPRODUCTOR, NOMBRE_APLICACION  # noqa: E402
from app.services import actualizador  # noqa: E402

ORIGEN = RAIZ / "build" / "entornolab"
SALIDA = RAIZ / "build" / "publicar"
CANALES = actualizador.CANALES


class ErrorPublicacion(Exception):
	"""Algo impide publicar; el mensaje dice qué hay que arreglar."""


def etiqueta_de(version: str, canal: str) -> str:
	"""Etiqueta de la publicación de GitHub: ``v<versión>`` o la fija de pruebas."""
	return actualizador.ETIQUETA_PRUEBAS if canal == "pruebas" else f"v{version}"


def url_de_descarga(version: str, canal: str, nombre_zip: str) -> str:
	"""Dirección permanente del ZIP dentro de su publicación (va firmada en version.json)."""
	return f"https://github.com/{actualizador.REPOSITORIO}/releases/download/{etiqueta_de(version, canal)}/{nombre_zip}"


def complementos_de_serie(origen: Path) -> dict[str, str]:
	"""Identificador y versión de cada complemento que viaja en la compilación."""
	resultado: dict[str, str] = {}
	plugins = origen / "data" / actualizador.CARPETA_COMPLEMENTOS
	if not plugins.is_dir():
		return resultado
	for carpeta in sorted(p for p in plugins.iterdir() if p.is_dir() and not p.name.startswith(".")):
		try:
			ficha = json.loads((carpeta / actualizador.FICHA_COMPLEMENTO).read_text(encoding="utf-8-sig"))
		except (OSError, ValueError) as error:
			raise ErrorPublicacion(f"El complemento de serie {carpeta.name} no se puede leer: {error}") from error
		resultado[str(ficha.get("id") or carpeta.name)] = str(ficha.get("version") or "")
	return resultado


def notas_de(version: str, raiz: Path = RAIZ) -> str:
	"""Notas de la versión, del registro de cambios de usuario. Sin notas no se publica."""
	ruta = raiz / "data" / "docs" / documentacion.CHANGELOG
	try:
		entrada = documentacion.notas_de_version(ruta.read_text(encoding="utf-8-sig"), version)
	except OSError as error:
		raise ErrorPublicacion(f"No se pudo leer {ruta}: {error}") from error
	if entrada is None or not entrada.texto.strip():
		raise ErrorPublicacion(f"La versión {version} no tiene notas en {ruta}. Añada «## Versión {version} - AAAA-MM-DD».")
	return entrada.texto.strip()


def comprimir(origen: Path, destino: Path, de_serie: dict[str, str]) -> int:
	"""Crea el ZIP de la versión (bajo ``EntornoLab/``) con la lista de complementos de serie dentro."""
	lista = f"{NOMBRE_APLICACION}/data/{actualizador.CARPETA_COMPLEMENTOS}/{actualizador.FICHERO_DE_SERIE}"
	total = 0
	with zipfile.ZipFile(destino, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as paquete:
		for fichero in sorted(origen.rglob("*")):
			if not fichero.is_file():
				continue
			interno = f"{NOMBRE_APLICACION}/{fichero.relative_to(origen).as_posix()}"
			if interno == lista:
				continue  # se escribe siempre la calculada ahora
			paquete.write(fichero, interno)
			total += 1
		paquete.writestr(lista, json.dumps({"de_serie": de_serie}, indent="\t", ensure_ascii=False))
	return total + 1


def sha256_de(ruta: Path) -> str:
	"""SHA-256 de un fichero leyendo por bloques de 1 MB."""
	resumen = hashlib.sha256()
	with ruta.open("rb") as archivo:
		for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
			resumen.update(bloque)
	return resumen.hexdigest()


def preparar(
	origen: Path = ORIGEN,
	salida: Path = SALIDA,
	canal: str = "estable",
	version: str = APP_VERSION,
	clave: Path | None = None,
	claves_publicas: tuple[str, ...] | None = None,
	notas: str | None = None,
	verificar_compilacion: bool = True,
) -> dict:
	"""Genera en ``salida`` el ZIP, ``version.json`` firmado y ``notas_version.md``.

	:return: ``{"zip": Path, "json": Path, "notas": Path, "manifiesto": dict}``.
	:raises ErrorPublicacion: con lo que hay que arreglar.
	"""
	if canal not in CANALES:
		raise ErrorPublicacion(f"Canal no válido: {canal}. Use uno de: {', '.join(CANALES)}.")
	try:
		actualizador.clave_version(version)
	except actualizador.VersionInvalida as error:
		raise ErrorPublicacion(str(error)) from error
	if canal == "estable" and actualizador.clave_version(version)[1][0] != 1:
		raise ErrorPublicacion(f"«{version}» es una versión preliminar: publíquela con --canal pruebas.")
	for ejecutable in (EJECUTABLE_ESTUDIO, EJECUTABLE_REPRODUCTOR):
		if not (origen / ejecutable).is_file():
			raise ErrorPublicacion(f"No existe {origen / ejecutable}. Compile primero (entorno.bat compilar).")
	if verificar_compilacion:
		from verificar_build import verificar

		problemas = verificar(origen)
		if problemas:
			raise ErrorPublicacion("La compilación no está limpia:\n  - " + "\n  - ".join(problemas))
	clave = clave or firmar_version.ruta_clave_privada()
	if not clave.is_file():
		raise ErrorPublicacion(f"No se encuentra la clave privada de firma ({clave}). Créela con tools/generar_claves.py.")
	notas = notas_de(version) if notas is None else notas.strip()
	de_serie = complementos_de_serie(origen)

	salida.mkdir(parents=True, exist_ok=True)
	ruta_zip = salida / f"{NOMBRE_APLICACION}_v{version}.zip"
	ruta_zip.unlink(missing_ok=True)
	ficheros = comprimir(origen, ruta_zip, de_serie)
	manifiesto = {
		"app": NOMBRE_APLICACION,
		"version": version,
		"canal": canal,
		"file": ruta_zip.name,
		"sha256": sha256_de(ruta_zip),
		"size": ruta_zip.stat().st_size,
		"date": date.today().isoformat(),
		"url": url_de_descarga(version, canal, ruta_zip.name),
		"novedades": notas,
	}
	manifiesto = firmar_version.firmar_datos(manifiesto, clave)
	publicas = actualizador.CLAVES_PUBLICAS_ED25519 if claves_publicas is None else claves_publicas
	if not firmar_version.firma_valida(manifiesto, list(publicas)):
		ruta_zip.unlink(missing_ok=True)
		raise ErrorPublicacion(
			"La clave con la que se ha firmado NO es ninguna de las que acepta la aplicación "
			"(CLAVES_PUBLICAS_ED25519 de app/services/actualizador.py): las instalaciones rechazarían esta versión."
		)
	ruta_json = salida / "version.json"
	ruta_json.write_text(json.dumps(manifiesto, indent="\t", ensure_ascii=False) + "\n", encoding="utf-8")
	ruta_notas = salida / "notas_version.md"
	ruta_notas.write_text(f"# {NOMBRE_APLICACION} {version}\n\n{notas}\n", encoding="utf-8")
	print(f"Paquete: {ruta_zip.name} ({ficheros} ficheros, {manifiesto['size'] / 1_048_576:.1f} MB)")
	print(f"Complementos de serie: {', '.join(f'{clave_} {valor}' for clave_, valor in de_serie.items()) or 'ninguno'}")
	print(f"version.json firmado y verificado (canal {canal}).")
	return {"zip": ruta_zip, "json": ruta_json, "notas": ruta_notas, "manifiesto": manifiesto}


def ordenes_gh(preparado: dict, existe_pruebas: bool = False) -> list[list[str]]:
	"""Órdenes de GitHub CLI que publican lo preparado (no las ejecuta).

	- estable: una publicación nueva con la etiqueta ``v<versión>``. GitHub la
	  marca como la última («latest») y de ahí la leen las instalaciones.
	- pruebas: una única publicación preliminar, de etiqueta ``pruebas``, cuyos
	  recursos se sustituyen. Al ser preliminar nunca es «latest».
	"""
	manifiesto = preparado["manifiesto"]
	version, canal = manifiesto["version"], manifiesto["canal"]
	repositorio = ["--repo", actualizador.REPOSITORIO]
	rutas = [str(preparado["zip"]), str(preparado["json"])]
	if canal == "estable":
		return [
			[
				"gh", "release", "create", etiqueta_de(version, canal), *rutas, *repositorio,
				"--title", f"{NOMBRE_APLICACION} {version}", "--notes-file", str(preparado["notas"]), "--latest",
			]
		]  # fmt: skip
	if existe_pruebas:
		return [
			["gh", "release", "upload", actualizador.ETIQUETA_PRUEBAS, *rutas, *repositorio, "--clobber"],
			["gh", "release", "edit", actualizador.ETIQUETA_PRUEBAS, *repositorio, "--notes-file", str(preparado["notas"])],
		]
	return [
		[
			"gh", "release", "create", actualizador.ETIQUETA_PRUEBAS, *rutas, *repositorio, "--prerelease",
			"--title", f"{NOMBRE_APLICACION} (versiones de pruebas)", "--notes-file", str(preparado["notas"]),
		]
	]  # fmt: skip


def _texto_orden(orden: list[str]) -> str:
	return " ".join(f'"{parte}"' if " " in parte else parte for parte in orden)


def _existe_publicacion(etiqueta: str) -> bool:
	"""Pregunta a GitHub si ya existe la publicación (solo se usa con ``--subir``)."""
	resultado = subprocess.run(
		["gh", "release", "view", etiqueta, "--repo", actualizador.REPOSITORIO], capture_output=True, text=True, check=False
	)
	return resultado.returncode == 0


def publicar(preparado: dict, subir: bool = False) -> int:
	"""Explica cómo subir lo preparado o, con ``subir``, lo sube con ``gh``."""
	canal = preparado["manifiesto"]["canal"]
	if not subir:
		print("\nPara publicarla, con GitHub CLI (https://cli.github.com) ya identificado («gh auth login»):")
		for orden in ordenes_gh(preparado, existe_pruebas=False):
			print("  " + _texto_orden(orden))
		if canal == "pruebas":
			print("  Si la publicación «pruebas» ya existe, en su lugar:")
			for orden in ordenes_gh(preparado, existe_pruebas=True):
				print("  " + _texto_orden(orden))
		print("O a mano: en GitHub, Releases, «Draft a new release», con esa etiqueta, y adjunte los dos ficheros.")
		print("Después compruebe la publicación con una copia instalada de la versión anterior (docs/actualizaciones.md).")
		return 0
	if shutil.which("gh") is None:
		print("ERROR: no se encuentra GitHub CLI (gh). Instálelo o publique a mano.", file=sys.stderr)
		return 1
	existe = canal == "pruebas" and _existe_publicacion(actualizador.ETIQUETA_PRUEBAS)
	for orden in ordenes_gh(preparado, existe_pruebas=existe):
		print("> " + _texto_orden(orden))
		if subprocess.run(orden, check=False).returncode != 0:
			print("ERROR: GitHub CLI ha fallado; la versión NO está publicada.", file=sys.stderr)
			return 1
	print("Versión publicada.")
	return 0


def main(argumentos: list[str] | None = None) -> int:
	"""Interfaz de línea de órdenes."""
	analizador = argparse.ArgumentParser(description="Prepara y publica una versión de EntornoLab en GitHub.")
	analizador.add_argument("--canal", choices=CANALES, default="estable")
	analizador.add_argument("--origen", type=Path, default=ORIGEN, help="Carpeta de la compilación (build/entornolab).")
	analizador.add_argument("--salida", type=Path, default=SALIDA, help="Dónde dejar el ZIP, version.json y las notas.")
	analizador.add_argument("--clave", type=Path, help="Clave privada (por defecto, la de ENTORNOLAB_CLAVES).")
	analizador.add_argument("--subir", action="store_true", help="Sube la versión con GitHub CLI (gh).")
	analizador.add_argument("--simular", action="store_true", help="No deja nada en la salida ni llama a gh: solo dice qué haría.")
	analizador.add_argument(
		"--sin-verificar", action="store_true", help="No pasa verificar_build.py (solo para pruebas de la herramienta)."
	)
	opciones = analizador.parse_args(argumentos)
	for flujo in (sys.stdout, sys.stderr):
		if hasattr(flujo, "reconfigure"):
			flujo.reconfigure(errors="replace")
	temporal = tempfile.TemporaryDirectory(prefix="entornolab_publicar_") if opciones.simular else None
	try:
		salida = Path(temporal.name) if temporal else opciones.salida
		if temporal:
			print("SIMULACIÓN: se genera todo en una carpeta temporal y no se sube nada.")
		preparado = preparar(
			opciones.origen, salida, opciones.canal, clave=opciones.clave, verificar_compilacion=not opciones.sin_verificar
		)
		return publicar(preparado, subir=opciones.subir and not opciones.simular)
	except ErrorPublicacion as error:
		print(f"ERROR: {error}", file=sys.stderr)
		return 1
	finally:
		if temporal:
			temporal.cleanup()


if __name__ == "__main__":
	sys.exit(main())
