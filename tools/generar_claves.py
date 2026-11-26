"""Genera el par de claves Ed25519 con el que se firman las versiones y el catálogo.

Se ejecuta UNA sola vez en la vida del proyecto (o al rotar la clave)::

	python tools/generar_claves.py
	python tools/generar_claves.py --carpeta D:\\ClavesSeguras\\EntornoLab

- La clave PRIVADA se guarda FUERA del proyecto: en la carpeta que diga la
  variable de entorno ``ENTORNOLAB_CLAVES`` y, si no está definida, en
  ``.entornolab/claves`` dentro de la carpeta personal del usuario. La
  herramienta se niega a escribirla dentro del proyecto. Con
  ``ENTORNOLAB_FIRMA_CONTRASENA`` definida, se guarda cifrada.
- La clave PÚBLICA se imprime para pegarla en ``CLAVES_PUBLICAS_ED25519`` de
  ``app/services/actualizador.py``. Es pública: va en el código.

Guarde una copia de la privada fuera del equipo (un pendrive en un cajón): sin
ella no se pueden publicar versiones ni catálogos que acepten las
instalaciones ya repartidas, y habría que rotar la clave (ver
``docs/actualizaciones.md``).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import firmar_version  # noqa: E402


def generar(carpeta: Path | str | None = None, forzar: bool = False) -> tuple[Path, str]:
	"""Crea el par de claves y devuelve (ruta de la privada, pública en hexadecimal).

	No sobrescribe una clave existente salvo con ``forzar``: perder la clave
	con la que ya se firmaron versiones obliga a una rotación.
	"""
	from cryptography.hazmat.primitives import serialization
	from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

	destino = Path(carpeta).expanduser() if carpeta else firmar_version.carpeta_claves()
	ruta = destino / firmar_version.NOMBRE_CLAVE
	if firmar_version.esta_dentro_del_proyecto(ruta):
		raise ValueError(f"{ruta} está dentro del proyecto: la clave privada debe guardarse fuera.")
	if ruta.exists() and not forzar:
		raise FileExistsError(f"Ya existe la clave {ruta}. No se sobrescribe (use --forzar solo si sabe lo que hace).")
	destino.mkdir(parents=True, exist_ok=True)
	privada = Ed25519PrivateKey.generate()
	contrasena = firmar_version._contrasena()
	cifrado = serialization.BestAvailableEncryption(contrasena) if contrasena else serialization.NoEncryption()
	ruta.write_bytes(privada.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, cifrado))
	return ruta, firmar_version.clave_publica_hex(privada)


def main(argumentos: list[str] | None = None) -> int:
	"""Interfaz de línea de órdenes."""
	analizador = argparse.ArgumentParser(description="Genera el par de claves de firma de EntornoLab.")
	analizador.add_argument("--carpeta", help="Carpeta donde guardar la clave privada (fuera del proyecto).")
	analizador.add_argument("--forzar", action="store_true", help="Sobrescribe una clave existente (¡peligroso!).")
	analizador.add_argument("--publica", action="store_true", help="Solo muestra la clave pública de la clave ya existente.")
	opciones = analizador.parse_args(argumentos)
	try:
		if opciones.publica:
			ruta = (Path(opciones.carpeta).expanduser() / firmar_version.NOMBRE_CLAVE) if opciones.carpeta else None
			print(firmar_version.clave_publica_hex(firmar_version.cargar_privada(ruta)))
			return 0
		ruta, publica = generar(opciones.carpeta, forzar=opciones.forzar)
	except (OSError, ValueError) as error:
		print(f"ERROR: {error}", file=sys.stderr)
		return 1
	print(f"Clave privada guardada en: {ruta}")
	print("  NO la suba al repositorio ni a GitHub. Guarde una copia fuera del equipo:")
	print("  sin ella no podrá publicar versiones que acepten las instalaciones actuales.")
	print("Clave pública (péguela en CLAVES_PUBLICAS_ED25519 de app/services/actualizador.py):")
	print(f'  CLAVES_PUBLICAS_ED25519 = ("{publica}",)')
	return 0


if __name__ == "__main__":
	sys.exit(main())
