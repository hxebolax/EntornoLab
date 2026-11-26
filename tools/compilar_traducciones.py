"""Compila los catálogos .po a .mo (formato binario de GNU gettext) sin dependencias.

Uso (desde la raíz del proyecto)::

	python tools/compilar_traducciones.py            # todos los .po de data/locales
	python tools/compilar_traducciones.py ruta.po    # uno concreto

Qué hace además de compilar:

- Omite las entradas «fuzzy» (aproximadas) y las que están sin traducir: la
  aplicación mostrará el texto original en español, que es mejor que una
  traducción dudosa.
- Comprueba que cada traducción conserva los marcadores del original
  (``{nombre}``, ``{}``, ``%s``, ``%(n)d``). Una traducción con un marcador
  que no existe haría fallar ``.format()`` en tiempo de ejecución; por eso
  esa entrada NO se compila y se informa como error.
- Avisa si cambia el número de aceleradores ``&`` o el atajo que sigue al
  tabulador de un menú (``&Guardar\\tCtrl+S``).
- Comprueba que ``Plural-Forms`` existe y es válido si hay plurales, y que
  cada plural tiene tantas formas como ``nplurals``.

Formato del .mo: manual de GNU gettext, «The Format of GNU MO Files»
(https://www.gnu.org/software/gettext/manual/html_node/MO-Files.html).

Código de salida 1 si hay errores (el .mo se genera igualmente sin las
entradas erróneas, para no bloquear el resto del trabajo).

La validación y el generador del .mo están en ``app/core/catalogo_po.py``
(la aplicación aplica las mismas reglas al leer un .po sin compilar).

Solo biblioteca estándar. Procede de la plantilla del agente «traducciones».
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
	from tools import catalogo_po  # importado como paquete (pruebas)
except ImportError:
	import catalogo_po  # ejecutado como script

log = logging.getLogger(__name__)

RAIZ = Path(__file__).resolve().parent.parent


@dataclass
class Informe:
	"""Resultado de compilar un .po."""

	origen: Path
	destino: Path | None = None
	compiladas: int = 0
	aproximadas: int = 0
	sin_traducir: int = 0
	errores: list[str] = field(default_factory=list)
	avisos: list[str] = field(default_factory=list)


def compilar(origen: Path, destino: Path | None = None) -> Informe:
	"""Compila un .po. El .mo se escribe junto al .po si no se indica destino."""
	informe = Informe(origen=origen)
	try:
		catalogo = catalogo_po.leer_po(origen)
	except (OSError, UnicodeDecodeError, catalogo_po.ErrorPO) as error:
		informe.errores.append(f"No se pudo leer: {error}")
		return informe
	resultado = catalogo_po.mensajes_compilables(catalogo)
	informe.compiladas = resultado.compiladas
	informe.aproximadas = resultado.aproximadas
	informe.sin_traducir = resultado.sin_traducir
	informe.errores.extend(resultado.errores)
	informe.avisos.extend(resultado.avisos)
	destino = destino or origen.with_suffix(".mo")
	temporal = destino.with_name(destino.name + ".tmp")
	try:
		temporal.write_bytes(catalogo_po.generar_mo(resultado.mensajes))
		temporal.replace(destino)
	except OSError as error:
		# Típico en Windows: el .mo está abierto por la aplicación en marcha.
		temporal.unlink(missing_ok=True)
		informe.errores.append(f"No se pudo escribir {destino}: {error}")
		return informe
	informe.destino = destino
	return informe


def buscar_po(raiz: Path) -> list[Path]:
	return sorted((raiz / "data" / "locales").glob("*/LC_MESSAGES/*.po"))


def main(argumentos: list[str] | None = None) -> int:
	analizador = argparse.ArgumentParser(description="Compila los catálogos .po a .mo.")
	analizador.add_argument("archivos", nargs="*", type=Path, help="Archivos .po (por defecto, todos los de data/locales).")
	analizador.add_argument("--raiz", type=Path, default=RAIZ, help="Raíz del proyecto.")
	opciones = analizador.parse_args(argumentos)
	catalogo_po.preparar_consola()
	archivos = opciones.archivos or buscar_po(opciones.raiz.resolve())
	if not archivos:
		print("No hay archivos .po en data/locales/<idioma>/LC_MESSAGES/.")
		return 0
	hay_errores = False
	for archivo in archivos:
		informe = compilar(archivo)
		print(f"{archivo}:")
		if informe.destino:
			print(
				f"  Compilado en {informe.destino}. Traducidas: {informe.compiladas}. "
				f"Aproximadas (omitidas): {informe.aproximadas}. Sin traducir: {informe.sin_traducir}."
			)
		for error in informe.errores:
			print(f"  Error: {error}")
		for aviso in informe.avisos:
			print(f"  Aviso: {aviso}")
		hay_errores = hay_errores or bool(informe.errores)
	return 1 if hay_errores else 0


if __name__ == "__main__":
	sys.exit(main())
