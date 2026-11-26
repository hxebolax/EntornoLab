"""Firma Ed25519 de los manifiestos que publica EntornoLab.

Sirve para los dos ficheros que la aplicación descarga y en los que confía:
``version.json`` (la versión nueva) y ``catalogo.json`` (el índice del
catálogo en línea de complementos).

Por qué firmar además del SHA-256: el SHA-256 solo demuestra que el fichero no
se corrompió por el camino. Quien entrase en la cuenta de GitHub cambiaría el
ZIP Y su SHA-256 a la vez. Con la firma necesitaría además la clave PRIVADA,
que no está en GitHub ni en el repositorio: vive en una carpeta del autor,
fuera del proyecto (ver ``tools/generar_claves.py``).

Uso (desde la raíz del proyecto)::

	python tools/firmar_version.py firmar build/version.json [--novedades notas.md]
		Añade (opcionalmente) las novedades y el campo «firma_ed25519». Se firma
		el fichero COMPLETO con una serialización canónica: cambiar cualquier
		campo (versión, sha256, tamaño, url, novedades) invalida la firma.

	python tools/firmar_version.py verificar build/version.json [--publica HEX ...]
		Comprueba la firma (con la clave pública indicada o la derivada de la
		privada) y, si el ZIP está junto al manifiesto, su tamaño y su SHA-256.

Dónde está la clave privada: en la carpeta que diga la variable de entorno
``ENTORNOLAB_CLAVES`` y, si no está definida, en ``.entornolab/claves`` dentro
de la carpeta personal del usuario. Nunca dentro del proyecto. Si la variable
``ENTORNOLAB_FIRMA_CONTRASENA`` está definida, la clave se guarda cifrada con
ella y se descifra al usarla.

``firmar(ruta_clave, ruta_json)`` es la función que llama ``tools/empaquetar.py``.

Procede de la plantilla del agente «actualizador».
"""

from __future__ import annotations

import argparse
import base64
import binascii
import hashlib
import hmac
import json
import os
import sys
from pathlib import Path
from typing import Any

RAIZ = Path(__file__).resolve().parent.parent
VARIABLE_CLAVES = "ENTORNOLAB_CLAVES"
VARIABLE_CONTRASENA = "ENTORNOLAB_FIRMA_CONTRASENA"
NOMBRE_CLAVE = "firma_ed25519.key"
CAMPO_FIRMA = "firma_ed25519"
CAMPOS_VERSION = ("version", "file", "sha256", "size")


def carpeta_claves() -> Path:
	"""Carpeta de la clave privada: la de ``ENTORNOLAB_CLAVES`` o ``~/.entornolab/claves``.

	Siempre FUERA del proyecto: así no puede acabar en el repositorio por un
	``git add`` descuidado ni en el ZIP de una versión.
	"""
	indicada = os.environ.get(VARIABLE_CLAVES, "").strip()
	return Path(indicada).expanduser() if indicada else Path.home() / ".entornolab" / "claves"


def ruta_clave_privada() -> Path:
	"""Ruta por defecto de la clave privada de firma."""
	return carpeta_claves() / NOMBRE_CLAVE


def esta_dentro_del_proyecto(ruta: Path) -> bool:
	"""True si ``ruta`` cae dentro de la carpeta del proyecto (donde una clave no debe estar)."""
	try:
		return Path(ruta).resolve().is_relative_to(RAIZ)
	except OSError:
		return False


def serializar_canonico(manifiesto: dict) -> bytes:
	"""Bytes que se firman: JSON ordenado, separadores fijos y sin el campo de firma.

	Debe ser IDÉNTICA a ``serializar_canonico`` de ``app/services/actualizador.py``
	(una prueba lo comprueba).
	"""
	datos = {clave: valor for clave, valor in manifiesto.items() if clave != CAMPO_FIRMA}
	return json.dumps(datos, sort_keys=True, separators=(",", ":"), ensure_ascii=False, allow_nan=False).encode("utf-8")


def _contrasena() -> bytes | None:
	valor = os.environ.get(VARIABLE_CONTRASENA, "")
	return valor.encode("utf-8") if valor else None


def cargar_privada(ruta_privada: Path | str | None = None) -> Any:
	"""Carga la clave privada (PEM, cifrada o no)."""
	from cryptography.hazmat.primitives import serialization
	from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

	ruta = Path(ruta_privada) if ruta_privada else ruta_clave_privada()
	clave = serialization.load_pem_private_key(ruta.read_bytes(), password=_contrasena())
	if not isinstance(clave, Ed25519PrivateKey):
		raise ValueError("La clave no es Ed25519.")
	return clave


def clave_publica_hex(privada: Any) -> str:
	"""Clave pública en hexadecimal (64 caracteres), como la espera la aplicación."""
	from cryptography.hazmat.primitives import serialization

	return privada.public_key().public_bytes(serialization.Encoding.Raw, serialization.PublicFormat.Raw).hex()


def firmar_datos(manifiesto: dict, ruta_privada: Path | str | None = None) -> dict:
	"""Devuelve una copia del manifiesto con el campo de firma puesto."""
	firmado = {clave: valor for clave, valor in manifiesto.items() if clave != CAMPO_FIRMA}
	privada = cargar_privada(ruta_privada)
	firmado[CAMPO_FIRMA] = base64.b64encode(privada.sign(serializar_canonico(firmado))).decode("ascii")
	return firmado


def firmar(ruta_privada: Path | str | None, ruta_json: Path | str, novedades: Path | str | None = None) -> str:
	"""Firma un manifiesto en su sitio y devuelve la firma en base64.

	Si es un ``version.json`` (tiene ``version``), exige sus campos mínimos:
	firmar un manifiesto incompleto publicaría una versión que nadie puede instalar.
	"""
	ruta = Path(ruta_json)
	manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
	if not isinstance(manifiesto, dict):
		raise ValueError("El fichero no contiene un objeto JSON.")
	if "version" in manifiesto:
		faltan = [campo for campo in CAMPOS_VERSION if not manifiesto.get(campo)]
		if faltan:
			raise ValueError(f"Al manifiesto le faltan campos: {', '.join(faltan)}.")
	if novedades:
		manifiesto["novedades"] = Path(novedades).read_text(encoding="utf-8").strip()
	firmado = firmar_datos(manifiesto, ruta_privada)
	ruta.write_text(json.dumps(firmado, indent="\t", ensure_ascii=False) + "\n", encoding="utf-8")
	return firmado[CAMPO_FIRMA]


def firma_valida(manifiesto: dict, claves_publicas: list[str]) -> bool:
	"""True si la firma del manifiesto corresponde a alguna de las claves públicas."""
	from cryptography.exceptions import InvalidSignature
	from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

	try:
		firma = base64.b64decode(str(manifiesto.get(CAMPO_FIRMA) or ""), validate=True)
	except binascii.Error, ValueError:
		return False
	if not firma:
		return False
	mensaje = serializar_canonico(manifiesto)
	for clave_hex in claves_publicas:
		try:
			Ed25519PublicKey.from_public_bytes(bytes.fromhex(clave_hex)).verify(firma, mensaje)
		except InvalidSignature, ValueError:
			continue
		return True
	return False


def verificar(ruta_json: Path | str, claves_publicas: list[str], comprobar_zip: bool = True) -> list[str]:
	"""Devuelve los problemas encontrados (lista vacía si todo está bien)."""
	ruta = Path(ruta_json)
	problemas: list[str] = []
	manifiesto = json.loads(ruta.read_text(encoding="utf-8"))
	if not manifiesto.get(CAMPO_FIRMA):
		return ["El manifiesto no está firmado."]
	if not firma_valida(manifiesto, claves_publicas):
		problemas.append("La firma NO es válida con ninguna de las claves públicas indicadas.")
	if not comprobar_zip or "file" not in manifiesto:
		return problemas
	zip_ = ruta.parent / str(manifiesto.get("file", ""))
	if not zip_.is_file():
		problemas.append(f"Aviso: no se encuentra {zip_.name} junto al manifiesto; no se ha comprobado su SHA-256.")
		return problemas
	if zip_.stat().st_size != manifiesto.get("size"):
		problemas.append(f"El tamaño de {zip_.name} no coincide con el manifiesto.")
	resumen = hashlib.sha256()
	with zip_.open("rb") as archivo:
		for bloque in iter(lambda: archivo.read(1024 * 1024), b""):
			resumen.update(bloque)
	if not hmac.compare_digest(resumen.hexdigest(), str(manifiesto.get("sha256", "")).lower()):
		problemas.append(f"El SHA-256 de {zip_.name} no coincide con el manifiesto.")
	return problemas


def main(argumentos: list[str] | None = None) -> int:
	"""Interfaz de línea de órdenes: firmar y verificar."""
	analizador = argparse.ArgumentParser(description="Firma Ed25519 de version.json y catalogo.json.")
	ordenes = analizador.add_subparsers(dest="orden", required=True)
	o_firmar = ordenes.add_parser("firmar", help="Firma un manifiesto.")
	o_firmar.add_argument("manifiesto")
	o_firmar.add_argument("--clave", help="Clave privada (por defecto, la de ENTORNOLAB_CLAVES).")
	o_firmar.add_argument("--novedades", help="Fichero de texto con las novedades de esta versión.")
	o_verificar = ordenes.add_parser("verificar", help="Comprueba la firma y, si está, el ZIP.")
	o_verificar.add_argument("manifiesto")
	o_verificar.add_argument("--publica", action="append", default=[], help="Clave pública en hexadecimal (repetible).")
	o_verificar.add_argument("--clave", help="Clave privada de la que derivar la pública.")
	opciones = analizador.parse_args(argumentos)
	try:
		if opciones.orden == "firmar":
			firmar(opciones.clave, opciones.manifiesto, opciones.novedades)
			print(f"Firmado: {opciones.manifiesto}")
			return 0
		publicas = list(opciones.publica) or [clave_publica_hex(cargar_privada(opciones.clave))]
		problemas = verificar(opciones.manifiesto, publicas)
		for problema in problemas:
			print(problema)
		graves = [problema for problema in problemas if not problema.startswith("Aviso:")]
		if not graves:
			print("Firma válida.")
		return 1 if graves else 0
	except (OSError, ValueError, TypeError) as error:
		print(f"ERROR: {error}", file=sys.stderr)
		return 1


if __name__ == "__main__":
	sys.exit(main())
