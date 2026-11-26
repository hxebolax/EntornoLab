"""Sintetiza el paquete de sonidos por defecto en ``data/sounds/por_defecto`` (herramienta de DESARROLLO).

Uso (desde la raíz del proyecto)::

	.venv\\Scripts\\python.exe tools\\sintetizar_sonidos.py
	.venv\\Scripts\\python.exe tools\\sintetizar_sonidos.py --solo "pasos/*"
	.venv\\Scripts\\python.exe tools\\sintetizar_sonidos.py --carpeta otra\\carpeta --formato ogg

Escribe, dentro de la carpeta de sonidos (``data/sounds``):

- ``por_defecto/``: todos los sonidos del catálogo de ``app/audio/sintesis.py``, con su ``pack.json``,
  su ``CREDITOS.txt`` y ``niveles.json`` (lo fuerte que suena cada uno: la referencia con la que
  se igualan los demás paquetes de sonidos);
- ``catalogo.json``: nombre hablado, explicación y grupo de cada sonido, para el menú «Aprender los
  sonidos». Es común a todos los paquetes y por eso queda fuera de ``por_defecto``.

El resultado se distribuye con el programa: la aplicación no sintetiza nada al arrancar. Los demás
paquetes de sonidos (por ejemplo ``natural``, que se genera con ``tools/generar_paquete_sonidos.py``)
no se tocan.

Escribe en la carpeta de sonidos de serie del programa (junto al código), no
en la carpeta ``data`` redirigida por ``APP_DATA_DIR``: son recursos que viajan
con la distribución, no datos del usuario.

Es determinista: volver a ejecutarla sin cambiar la síntesis deja exactamente
los mismos ficheros. Con ``--solo`` se regenera una parte, pero el catálogo y los niveles se
reescriben siempre enteros.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
	sys.path.insert(0, str(RAIZ))

from app.audio import niveles, sintesis  # noqa: E402 - necesita la raíz del proyecto en sys.path
from app.audio.banco import NOMBRE_FICHA, PAQUETE_POR_DEFECTO  # noqa: E402
from app.core import paths  # noqa: E402

log = logging.getLogger("sintetizar_sonidos")

FICHA = {
	"id": PAQUETE_POR_DEFECTO,
	"nombre": "Sintético (por defecto)",
	"descripcion": "Los sonidos de serie de EntornoLab: limpios, cortos y muy distintos entre sí, sintetizados uno a uno.",
	"autor": "EntornoLab",
	"licencia": "GPL-3.0-or-later, como el programa",
	"version": "1.0",
	"generado": "Síntesis con numpy (app/audio/sintesis.py), con tools/sintetizar_sonidos.py. Sin grabaciones ni inteligencia artificial.",
}

CREDITOS = """PAQUETE DE SONIDOS «SINTÉTICO (POR DEFECTO)» DE ENTORNOLAB

Los sonidos de serie de EntornoLab: limpios, cortos y muy distintos entre sí.

Trae todos los sonidos del catálogo ({total}). Son la referencia de los demás paquetes: lo que
otro paquete no trae suena con el sonido de aquí, y el nivel de cada sonido de aquí (niveles.json)
es al que se igualan los de los demás.

CÓMO SE HIZO
  Todos se sintetizan con numpy en app/audio/sintesis.py; no hay grabaciones ni se ha usado
  inteligencia artificial. Para regenerarlos:
      .venv\\Scripts\\python.exe tools\\sintetizar_sonidos.py
  Es determinista: cada sonido usa una semilla derivada de su nombre.

LICENCIA
  Son parte de EntornoLab y van con su misma licencia (GPL-3.0-or-later). No tienen derechos de
  terceros.

SUSTITUIR UN SONIDO
  No hace falta tocar esta carpeta: cree un paquete propio (vea LEEME.md, en la carpeta de sonidos)
  con solo los sonidos que quiera cambiar.
"""


def carpeta_de_serie() -> Path:
	"""La carpeta de sonidos que se distribuye con el programa (la que contiene los paquetes)."""
	return paths.ruta_base() / "data" / "sounds"


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
	analizador = argparse.ArgumentParser(description="Sintetiza el paquete de sonidos por defecto de EntornoLab.")
	analizador.add_argument(
		"--carpeta",
		type=Path,
		default=None,
		help="carpeta de sonidos de destino (por defecto, data/sounds del programa); el paquete va en su subcarpeta por_defecto",
	)
	analizador.add_argument("--formato", choices=("flac", "ogg", "wav"), default="flac", help="formato de los ficheros (por defecto, flac)")
	analizador.add_argument("--solo", default=None, help="patrón de nombres que regenerar, por ejemplo «pasos/*»")
	return analizador.parse_args(argv)


def _sobrantes(carpeta: Path) -> list[Path]:
	"""Ficheros de audio de la carpeta que ya no corresponden a ningún sonido del catálogo."""
	conocidos = set(sintesis.nombres())
	sobran = []
	for ruta in sorted(carpeta.rglob("*")):
		if ruta.suffix.lower() in sintesis.FORMATOS_AUDIO and ruta.relative_to(carpeta).with_suffix("").as_posix() not in conocidos:
			sobran.append(ruta)
	return sobran


def _escribir_texto(ruta: Path, texto: str) -> None:
	"""Escribe un fichero de texto de forma atómica (temporal al lado y renombrado)."""
	temporal = ruta.with_name(ruta.name + ".tmp")
	temporal.write_text(texto, encoding="utf-8", newline="\n")
	os.replace(temporal, ruta)


def escribir_paquete(carpeta: Path, formato: str = "flac", solo: str | None = None) -> list[Path]:
	"""Escribe en ``carpeta`` (la de sonidos) el paquete por defecto y el catálogo. Devuelve los sonidos escritos."""
	paquete = carpeta / PAQUETE_POR_DEFECTO
	escritos = sintesis.escribir_todos(paquete, formato, solo)
	sintesis.escribir_catalogo(carpeta, formato, carpeta_sonidos=paquete)
	# Los niveles se miden sobre lo que hay escrito: es lo que de verdad va a sonar.
	medidos = {}
	for nombre in sintesis.nombres():
		ruta = sintesis.fichero_de(paquete, nombre)
		medidos[nombre] = sintesis.leer_audio(ruta)[0] if ruta is not None else sintesis.generar(nombre)
	niveles.escribir_niveles(paquete, medidos)
	_escribir_texto(paquete / NOMBRE_FICHA, json.dumps(FICHA, ensure_ascii=False, indent="\t") + "\n")
	_escribir_texto(paquete / "CREDITOS.txt", CREDITOS.format(total=len(sintesis.nombres())))
	return escritos


def main(argv: list[str] | None = None) -> int:
	"""Genera los sonidos, el catálogo y los niveles. Devuelve el código de salida del proceso."""
	logging.basicConfig(level=logging.INFO, format="%(message)s")
	argumentos = _argumentos(argv)
	carpeta = (argumentos.carpeta or carpeta_de_serie()).resolve()
	inicio = time.perf_counter()
	try:
		escritos = escribir_paquete(carpeta, argumentos.formato, argumentos.solo)
	except OSError, ValueError:
		log.exception("No se pudieron escribir los sonidos en %s.", carpeta)
		return 1
	if not escritos:
		log.warning("Ningún sonido coincide con el patrón «%s».", argumentos.solo)
	total = sum(ruta.stat().st_size for ruta in escritos)
	log.info(
		"%s sonidos escritos en %s (%.1f MB) en %.1f s. Catálogo: %s.",
		len(escritos),
		carpeta / PAQUETE_POR_DEFECTO,
		total / 1048576.0,
		time.perf_counter() - inicio,
		carpeta / "catalogo.json",
	)
	for ruta in _sobrantes(carpeta / PAQUETE_POR_DEFECTO):
		# No se borra nada: puede ser una grabación que alguien ha dejado a propósito.
		log.warning("Hay un fichero que no está en el catálogo: %s", ruta.relative_to(carpeta).as_posix())
	return 0


if __name__ == "__main__":
	sys.exit(main())
