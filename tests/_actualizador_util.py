"""Utilidades comunes de las pruebas del actualizador y del catálogo en línea.

- Carga de las herramientas de ``tools/`` (que no es un paquete).
- Un par de claves de PRUEBA por sesión, en una carpeta temporal: las pruebas
  nunca usan (ni ven) la clave privada real del autor.
- Construcción de versiones publicadas (ZIP + ``version.json`` firmado) y de
  catálogos de complementos firmados, como los que generan las herramientas.
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import sys
import zipfile
from pathlib import Path
from types import ModuleType

RAIZ = Path(__file__).resolve().parents[1]


def cargar_herramienta(nombre: str) -> ModuleType:
	"""Importa ``tools/<nombre>.py`` como módulo (una sola vez por sesión)."""
	clave = f"_herramienta_{nombre}"
	if clave in sys.modules:
		return sys.modules[clave]
	carpeta = str(RAIZ / "tools")
	if carpeta not in sys.path:
		sys.path.insert(0, carpeta)
	especificacion = importlib.util.spec_from_file_location(clave, RAIZ / "tools" / f"{nombre}.py")
	modulo = importlib.util.module_from_spec(especificacion)
	sys.modules[clave] = modulo
	especificacion.loader.exec_module(modulo)
	return modulo


class Claves:
	"""Par de claves de prueba: ``privada`` (ruta) y ``publica`` (hexadecimal)."""

	def __init__(self, carpeta: Path) -> None:
		generador = cargar_herramienta("generar_claves")
		self.privada, self.publica = generador.generar(carpeta)
		self.firmador = cargar_herramienta("firmar_version")

	def firmar(self, manifiesto: dict) -> dict:
		return self.firmador.firmar_datos(manifiesto, self.privada)


def crear_zip(ruta: Path, archivos: dict[str, bytes], carpeta_raiz: str | None = "EntornoLab") -> Path:
	"""Crea un ZIP como el de una versión (todo bajo una carpeta raíz)."""
	ruta.parent.mkdir(parents=True, exist_ok=True)
	with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as paquete:
		for nombre, contenido in archivos.items():
			paquete.writestr(f"{carpeta_raiz}/{nombre}" if carpeta_raiz else nombre, contenido)
	return ruta


def publicar_version(
	carpeta: Path,
	version: str,
	archivos: dict[str, bytes],
	claves: Claves | None,
	*,
	canal: str = "estable",
	novedades: str = "",
	extra: dict | None = None,
	nombre_json: str = "version.json",
) -> dict:
	"""Deja en ``carpeta`` el ZIP y su ``version.json`` (firmado si hay claves) y devuelve el manifiesto."""
	zip_ = crear_zip(carpeta / f"EntornoLab_v{version}.zip", archivos)
	datos = zip_.read_bytes()
	manifiesto = {
		"app": "EntornoLab",
		"version": version,
		"canal": canal,
		"file": zip_.name,
		"sha256": hashlib.sha256(datos).hexdigest(),
		"size": len(datos),
		"date": "2026-11-26",
		"novedades": novedades,
	}
	manifiesto.update(extra or {})
	if claves is not None:
		manifiesto = claves.firmar(manifiesto)
	escribir_json(carpeta / nombre_json, manifiesto)
	return manifiesto


def escribir_json(ruta: Path, datos: dict) -> None:
	ruta.parent.mkdir(parents=True, exist_ok=True)
	ruta.write_text(json.dumps(datos, indent="\t", ensure_ascii=False), encoding="utf-8")


def crear_elabc(ruta: Path, ficha: dict, extra: dict[str, bytes] | None = None, prefijo: str = "") -> Path:
	"""Crea un paquete de complemento con su ficha y los ficheros extra indicados."""
	ruta.parent.mkdir(parents=True, exist_ok=True)
	with zipfile.ZipFile(ruta, "w", zipfile.ZIP_DEFLATED) as archivo:
		archivo.writestr(prefijo + "complemento.json", json.dumps(ficha, ensure_ascii=False))
		for nombre, contenido in (extra or {}).items():
			archivo.writestr(prefijo + nombre, contenido)
	return ruta


def entrada_catalogo(ruta_elabc: Path, ficha: dict, **cambios) -> dict:
	"""Entrada del índice para un paquete ya creado (con su tamaño y SHA-256 reales)."""
	datos = ruta_elabc.read_bytes()
	entrada = {
		"id": ficha["id"],
		"nombre": ficha.get("nombre", ficha["id"]),
		"descripcion": ficha.get("descripcion", ""),
		"autor": ficha.get("autor", ""),
		"licencia": ficha.get("licencia", ""),
		"version": ficha.get("version", "1.0"),
		"version_minima_app": "0.1.0",
		"categorias": sorted({objeto.get("categoria", "") for objeto in ficha.get("objetos", []) if objeto.get("categoria")}),
		"objetos": len(ficha.get("objetos", [])),
		"tamano": len(datos),
		"url": f"paquetes/{ruta_elabc.name}",
		"sha256": hashlib.sha256(datos).hexdigest(),
		"fecha": "2026-11-26",
	}
	entrada.update(cambios)
	return entrada


def publicar_catalogo(carpeta: Path, entradas: list[dict], claves: Claves | None, *, serie: int = 1, extra: dict | None = None) -> dict:
	"""Escribe ``catalogo.json`` (firmado si hay claves) en ``carpeta`` y lo devuelve."""
	indice = {
		"formato": 1,
		"tipo": "catalogo-complementos",
		"app": "EntornoLab",
		"serie": serie,
		"generado": "2026-11-26T10:00:00+00:00",
		"complementos": entradas,
	}
	indice.update(extra or {})
	if claves is not None:
		indice = claves.firmar(indice)
	escribir_json(carpeta / "catalogo.json", indice)
	return indice
