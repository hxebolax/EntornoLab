"""Escribe los entornos de ejemplo como paquetes ``.elab`` en ``data/ejemplos``.

Uso (desde la raíz del proyecto, con el entorno virtual activado)::

	python tools/generar_ejemplos.py [--destino CARPETA] [--amueblar]

Cada ejemplo se construye con ``app.dominio.ejemplos``, se valida, se guarda
con sus actividades de ejemplo (``app.actividades.plantillas``: búsquedas,
rutas, exámenes…) y se vuelve a abrir para comprobar que el fichero escrito
es legible. Si el entorno o alguna de sus actividades tiene errores de
validación el programa lo dice y termina con código 1, para que un ejemplo
roto no llegue a distribuirse.

Con ``--amueblar`` los ejemplos salen con objetos de los complementos de
serie (``data/plugins``): hogar en la vivienda, colegio y oficina en el
centro, calle y transporte en el barrio. Así es como se generan los que se
distribuyen. Los complementos se regeneran con ``tools/generar_complementos.py``.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
	sys.path.insert(0, str(RAIZ))

from app.actividades import plantillas_de, validar_actividad  # noqa: E402
from app.core import paths  # noqa: E402
from app.dominio import ejemplos  # noqa: E402
from app.dominio.catalogo import Catalogo  # noqa: E402
from app.dominio.formato import EXTENSION_PAQUETE, cargar_paquete, guardar_paquete  # noqa: E402
from app.dominio.validacion import resumen, validar  # noqa: E402

log = logging.getLogger("generar_ejemplos")


def generar(destino: Path, amueblar: bool = False) -> int:
	"""Genera los ejemplos en ``destino``; devuelve cuántos tienen errores."""
	destino.mkdir(parents=True, exist_ok=True)
	# Los complementos de serie viajan con el programa: se buscan también junto al código, aunque ``data`` esté redirigida.
	catalogo = Catalogo.cargar([paths.subcarpeta("plugins"), paths.ruta_base() / "data" / "plugins"]) if amueblar else None
	con_errores = 0
	for nombre, construir in ejemplos.EJEMPLOS.items():
		entorno = construir()
		if catalogo is not None:
			colocados = ejemplos.amueblar_ejemplos(entorno, catalogo)
			log.info("%s: %s objetos colocados", nombre, len(colocados))
		avisos = validar(entorno, catalogo)
		errores = [aviso for aviso in avisos if aviso.es_error]
		# Las actividades se montan sobre el entorno ya amueblado: así los premios pueden ir dentro de los muebles.
		actividades = plantillas_de(nombre, entorno, catalogo)
		avisos_actividades = [(datos["id"], aviso) for datos in actividades for aviso in validar_actividad(datos, entorno, catalogo)]
		errores += [aviso for _id, aviso in avisos_actividades if aviso.es_error]
		ruta = destino / f"{nombre}{EXTENSION_PAQUETE}"
		guardar_paquete(ruta, entorno, actividades)
		paquete = cargar_paquete(ruta)
		if paquete.entorno.a_dict() != entorno.a_dict():
			log.error("%s: el fichero escrito no coincide con el entorno generado", nombre)
			con_errores += 1
		if sorted(a["id"] for a in paquete.actividades) != sorted(a["id"] for a in actividades):
			log.error("%s: las actividades escritas no coinciden con las generadas", nombre)
			con_errores += 1
		print(f"{ruta}: {resumen(avisos)} Actividades: {len(actividades)}.")
		for aviso in avisos:
			print(f"  [{aviso.gravedad}] {aviso.codigo}: {aviso.mensaje} {aviso.sugerencia}")
		for id_actividad, aviso in avisos_actividades:
			print(f"  [{aviso.gravedad}] actividad {id_actividad}, {aviso.codigo}: {aviso.mensaje} {aviso.sugerencia}")
		if errores:
			con_errores += 1
	return con_errores


def main() -> int:
	"""Punto de entrada de la herramienta."""
	logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
	analizador = argparse.ArgumentParser(description="Genera los entornos de ejemplo de EntornoLab.")
	analizador.add_argument("--destino", type=Path, default=None, help="carpeta de salida (por defecto, data/ejemplos)")
	analizador.add_argument("--amueblar", action="store_true", help="amuebla los ejemplos con los complementos instalados")
	argumentos = analizador.parse_args()
	destino = argumentos.destino if argumentos.destino is not None else paths.subcarpeta("ejemplos")
	con_errores = generar(destino, argumentos.amueblar)
	if con_errores:
		print(f"Hay {con_errores} ejemplos con errores.")
		return 1
	print("Ejemplos generados sin errores.")
	return 0


if __name__ == "__main__":
	sys.exit(main())
