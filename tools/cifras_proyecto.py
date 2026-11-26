"""Cuenta lo que trae EntornoLab y lo imprime como tabla Markdown.

Las cifras del README (complementos, objetos, sonidos, paquetes, tipos de
actividad, entornos de ejemplo, pruebas e idiomas) cambian a menudo. En vez de
escribirlas a mano, se cuentan aquí a partir de los datos reales del proyecto.

Uso (desde la raíz del proyecto)::

	python tools/cifras_proyecto.py                    # tabla en pantalla
	python tools/cifras_proyecto.py --pytest           # cuenta las pruebas con pytest (más lento, exacto)
	python tools/cifras_proyecto.py --escribir README.md

Con ``--escribir``, la tabla sustituye lo que haya en el fichero entre las
marcas ``<!-- cifras:inicio -->`` y ``<!-- cifras:fin -->``. Si faltan las
marcas, no se toca el fichero y se termina con código 1.

Solo necesita la biblioteca estándar. Si puede importar ``app`` usa los
mismos lectores que la aplicación (así cuenta igual que el catálogo); si no,
lee los JSON directamente.
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
	sys.path.insert(0, str(RAIZ))

MARCA_INICIO = "<!-- cifras:inicio -->"
MARCA_FIN = "<!-- cifras:fin -->"
EXTENSIONES_SONIDO = {".ogg", ".wav", ".flac"}


@dataclass
class Cifra:
	"""Una fila de la tabla: qué se cuenta, cuántos hay y una nota opcional."""

	nombre: str
	valor: int | None
	nota: str = ""

	def texto_valor(self) -> str:
		return "sin datos" if self.valor is None else f"{self.valor:,}".replace(",", ".")


def _leer_json(ruta: Path) -> object | None:
	try:
		return json.loads(ruta.read_text(encoding="utf-8-sig"))
	except OSError, ValueError:
		log.warning("No se pudo leer %s", ruta, exc_info=True)
		return None


# ── Complementos y objetos ───────────────────────────────────────────────────


def carpetas_de_complementos(raiz: Path) -> list[Path]:
	"""Carpetas de ``data/plugins`` (a cualquier profundidad) que tienen ``complemento.json``."""
	plugins = raiz / "data" / "plugins"
	if not plugins.is_dir():
		return []
	return sorted(ficha.parent for ficha in plugins.rglob("complemento.json"))


def objetos_de_complemento(carpeta: Path) -> int:
	"""Objetos de un complemento: con el lector de la aplicación si se puede; si no, del JSON."""
	try:
		from app.dominio import catalogo

		complemento, _avisos = catalogo.leer_complemento(carpeta)
		objetos = getattr(complemento, "objetos", None)
		if objetos is not None:
			return len(objetos)
	except Exception:  # Límite: cualquier fallo del lector se sustituye por la lectura directa.
		log.debug("Lector de la aplicación no disponible para %s", carpeta, exc_info=True)
	datos = _leer_json(carpeta / "complemento.json")
	if isinstance(datos, dict) and isinstance(datos.get("objetos"), list):
		return len(datos["objetos"])
	return 0


# ── Sonidos ──────────────────────────────────────────────────────────────────


def sonidos_del_catalogo(raiz: Path) -> int | None:
	datos = _leer_json(raiz / "data" / "sounds" / "catalogo.json")
	if isinstance(datos, dict) and isinstance(datos.get("sonidos"), dict):
		return len(datos["sonidos"])
	return None


def paquetes_de_sonido(raiz: Path) -> list[Path]:
	carpeta = raiz / "data" / "sounds"
	if not carpeta.is_dir():
		return []
	return sorted(p for p in carpeta.iterdir() if p.is_dir() and not p.name.startswith((".", "_")))


def ficheros_de_sonido(carpeta: Path) -> int:
	return sum(1 for f in carpeta.rglob("*") if f.suffix.lower() in EXTENSIONES_SONIDO)


# ── Actividades, ejemplos, idiomas y pruebas ─────────────────────────────────


def tipos_de_actividad(raiz: Path) -> int | None:
	try:
		from app.actividades import tipos

		return len(tipos.TIPOS)
	except Exception:  # Límite: si no se puede importar, se cuenta en el texto.
		log.debug("No se pudo importar app.actividades.tipos", exc_info=True)
	try:
		texto = (raiz / "app" / "actividades" / "tipos.py").read_text(encoding="utf-8")
	except OSError:
		return None
	return len(re.findall(r"^\s*_tipo\(", texto, re.MULTILINE)) or None


def entornos_de_ejemplo(raiz: Path) -> int:
	carpeta = raiz / "data" / "ejemplos"
	return len(list(carpeta.glob("*.elab"))) if carpeta.is_dir() else 0


def idiomas(raiz: Path) -> int:
	"""Español (el del código) más cada catálogo de ``data/locales``."""
	carpeta = raiz / "data" / "locales"
	extra = [p for p in carpeta.iterdir() if (p / "LC_MESSAGES").is_dir()] if carpeta.is_dir() else []
	return 1 + len(extra)


def pruebas_estaticas(raiz: Path) -> tuple[int, int]:
	"""(ficheros de prueba, funciones ``test_``) contados en el texto, sin ejecutar nada."""
	carpeta = raiz / "tests"
	if not carpeta.is_dir():
		return 0, 0
	ficheros = sorted(carpeta.rglob("test_*.py"))
	funciones = 0
	for fichero in ficheros:
		try:
			funciones += len(re.findall(r"^\s*(?:async\s+)?def test_", fichero.read_text(encoding="utf-8"), re.MULTILINE))
		except OSError, UnicodeDecodeError:
			log.warning("No se pudo leer %s", fichero, exc_info=True)
	return len(ficheros), funciones


def pruebas_con_pytest(raiz: Path) -> int | None:
	"""Pruebas que recoge pytest (con las parametrizadas) con las marcas de serie."""
	try:
		resultado = subprocess.run(
			[sys.executable, "-m", "pytest", "--collect-only", "-q", "tests"],
			cwd=raiz,
			capture_output=True,
			text=True,
			encoding="utf-8",
			errors="replace",
			timeout=600,
			check=False,
		)
	except OSError, subprocess.TimeoutExpired:
		log.warning("No se pudo ejecutar pytest", exc_info=True)
		return None
	coincidencia = re.search(r"(\d+)(?:/\d+)? tests? (?:collected|selected)", resultado.stdout)
	if coincidencia:
		return int(coincidencia.group(1))
	lineas = [linea for linea in resultado.stdout.splitlines() if "::" in linea]
	return len(lineas) or None


# ── Tabla ────────────────────────────────────────────────────────────────────


def cifras(raiz: Path, con_pytest: bool = False) -> list[Cifra]:
	complementos = carpetas_de_complementos(raiz)
	objetos = sum(objetos_de_complemento(c) for c in complementos)
	paquetes = paquetes_de_sonido(raiz)
	nombres_paquetes = ", ".join(p.name for p in paquetes)
	ficheros_prueba, funciones = pruebas_estaticas(raiz)
	filas = [
		Cifra("Complementos de objetos de serie", len(complementos)),
		Cifra("Objetos en esos complementos", objetos),
		Cifra("Sonidos distintos del catálogo de sonidos", sonidos_del_catalogo(raiz)),
		Cifra("Paquetes de sonidos", len(paquetes), nombres_paquetes),
		Cifra("Tipos de actividad", tipos_de_actividad(raiz)),
		Cifra("Entornos de ejemplo", entornos_de_ejemplo(raiz)),
		Cifra("Idiomas de la interfaz (con catálogo, aunque esté incompleto)", idiomas(raiz)),
		Cifra("Ficheros de pruebas automáticas", ficheros_prueba),
	]
	if con_pytest:
		filas.append(Cifra("Pruebas automáticas que recoge pytest", pruebas_con_pytest(raiz)))
	else:
		filas.append(Cifra("Funciones de prueba (sin contar las parametrizadas)", funciones))
	return filas


def tabla_markdown(filas: list[Cifra]) -> str:
	lineas = ["| Qué | Cuántos |", "|---|---|"]
	for fila in filas:
		valor = fila.texto_valor()
		if fila.nota:
			valor = f"{valor} ({fila.nota})"
		lineas.append(f"| {fila.nombre} | {valor} |")
	return "\n".join(lineas)


def escribir_en(fichero: Path, tabla: str) -> bool:
	"""Sustituye lo que haya entre las marcas. False si faltan."""
	texto = fichero.read_text(encoding="utf-8")
	inicio = texto.find(MARCA_INICIO)
	fin = texto.find(MARCA_FIN)
	if inicio < 0 or fin < inicio:
		return False
	nuevo = texto[: inicio + len(MARCA_INICIO)] + "\n\n" + tabla + "\n\n" + texto[fin:]
	if nuevo != texto:
		fichero.write_text(nuevo, encoding="utf-8", newline="\n")
	return True


def main(argumentos: list[str] | None = None) -> int:
	analizador = argparse.ArgumentParser(description="Cuenta complementos, objetos, sonidos, actividades, ejemplos y pruebas.")
	analizador.add_argument("--raiz", type=Path, default=RAIZ, help="Raíz del proyecto.")
	analizador.add_argument("--pytest", action="store_true", help="Cuenta las pruebas con pytest --collect-only.")
	analizador.add_argument("--escribir", type=Path, metavar="FICHERO", help="Escribe la tabla entre las marcas de cifras de ese fichero.")
	opciones = analizador.parse_args(argumentos)
	for flujo in (sys.stdout, sys.stderr):
		if hasattr(flujo, "reconfigure"):
			flujo.reconfigure(encoding="utf-8", errors="replace")
	logging.basicConfig(level=logging.WARNING, format="%(levelname)s: %(message)s")
	raiz = opciones.raiz.resolve()
	tabla = tabla_markdown(cifras(raiz, opciones.pytest))
	print(tabla)
	if opciones.escribir:
		fichero = opciones.escribir if opciones.escribir.is_absolute() else raiz / opciones.escribir
		if not escribir_en(fichero, tabla):
			print(f"No se encontraron las marcas {MARCA_INICIO} y {MARCA_FIN} en {fichero}.")
			return 1
		print(f"Tabla escrita en {fichero}.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
