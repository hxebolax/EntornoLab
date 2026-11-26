"""Pasos previos a la compilación (los ejecuta ``entorno.bat compilar``).

1. Compila las traducciones: la versión distribuida lee los ``.mo`` y una
   traducción con errores debe parar la compilación, no descubrirse después.
2. Comprueba que la versión que se va a publicar tiene notas en
   ``data/docs/novedades.md``.
3. Comprueba con ``tools/comprobar_rutas.py`` que lo que se sube al
   repositorio no lleva rutas ni datos del equipo de desarrollo (los datos
   de ``data/`` que viajan en la compilación salen de ahí).
4. Avisa (sin parar) de lo que falta en ``data/`` para que el resultado sea
   completo: OpenAL Soft, sonidos de serie, complementos y ejemplos.

Código de salida 1 si hay que detener la compilación.

Solo biblioteca estándar.
"""

from __future__ import annotations

import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
	sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tools") not in sys.path:
	sys.path.insert(0, str(RAIZ / "tools"))

# Lo que debería existir en data/ antes de compilar y cómo conseguirlo.
RECOMENDADOS = [
	("data/bin/openal/soft_oal.dll", "sin él no hay sonido 3D con OpenAL (se usará el motor clásico)"),
	("data/sounds/catalogo.json", "ejecute: entorno.bat sonidos"),
	("data/docs/manual.md", "falta el manual de usuario"),
]
CARPETAS_CON_CONTENIDO = [
	("data/plugins", "no hay complementos de objetos"),
	("data/ejemplos", "no hay entornos de ejemplo (ejecute: entorno.bat ejemplos)"),
]


def main() -> int:
	"""Ejecuta los pasos y devuelve el código de salida."""
	import compilar_traducciones
	import notas_version

	print("Compilando las traducciones...")
	if compilar_traducciones.main([]) != 0:
		print("ERROR: hay traducciones con errores. Corríjalas (entorno.bat idiomas) antes de compilar.")
		return 1
	print("Comprobando las notas de la versión...")
	salida = RAIZ / "build" / "notas_version.md"
	if notas_version.main(["--salida", str(salida)]) != 0:
		print("ERROR: la versión no tiene notas en data/docs/novedades.md.")
		return 1
	import comprobar_rutas

	print("Comprobando que el repositorio no lleva rutas del equipo de desarrollo...")
	codigo_rutas = comprobar_rutas.main([])
	if codigo_rutas == 1:
		print("ERROR: hay rutas o datos del equipo de desarrollo en el repositorio. Quítelos antes de compilar.")
		return 1
	if codigo_rutas != 0:
		# Sin git no se sabe qué se subiría; la compilación se comprueba igual después (verificar_build.py).
		print("Aviso: no se pudo comprobar el repositorio; la compilación se comprobará al terminar.")
	for relativo, consejo in RECOMENDADOS:
		if not (RAIZ / relativo).is_file():
			print(f"Aviso: falta {relativo}; {consejo}.")
	for relativo, consejo in CARPETAS_CON_CONTENIDO:
		carpeta = RAIZ / relativo
		if not carpeta.is_dir() or not any(archivo.name != ".gitkeep" for archivo in carpeta.iterdir()):
			print(f"Aviso: {relativo} está vacía; {consejo}.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
