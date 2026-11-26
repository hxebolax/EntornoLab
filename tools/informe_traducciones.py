"""Informe de las cadenas que faltan por traducir en cada idioma.

Uso (desde la raíz del proyecto)::

	python tools/informe_traducciones.py              # resumen de todos los idiomas
	python tools/informe_traducciones.py en           # solo el inglés
	python tools/informe_traducciones.py --detalle    # enumera cada cadena pendiente
	python tools/informe_traducciones.py --estricto   # código 1 si falta algo (para publicar)
	python tools/informe_traducciones.py --salida build/traducciones.txt

Para cada idioma dice cuántas cadenas están traducidas, cuántas son
aproximadas («fuzzy», pendientes de revisar), cuántas están sin traducir y
cuántas tienen errores que impiden usarlas (marcadores cambiados, plurales
incompletos). Con ``--detalle`` enumera cada una con el archivo y la línea
del código donde aparece, en texto plano que se lee bien con un lector de
pantalla.

Si existe la plantilla ``data/locales/<dominio>.pot``, avisa además de los
catálogos que no están al día con ella (hay que pasar ``actualizar_po.py``).

Solo biblioteca estándar.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

try:
	from tools import catalogo_po  # importado como paquete (pruebas)
except ImportError:
	import catalogo_po  # ejecutado como script

RAIZ = Path(__file__).resolve().parent.parent


@dataclass
class InformeIdioma:
	"""Estado de la traducción de un idioma."""

	idioma: str
	archivo: Path
	total: int = 0
	traducidas: int = 0
	aproximadas: list[catalogo_po.Entrada] = field(default_factory=list)
	sin_traducir: list[catalogo_po.Entrada] = field(default_factory=list)
	errores: list[str] = field(default_factory=list)
	# Cadenas de la plantilla que el catálogo todavía no conoce.
	ausentes: int = 0
	fallo_lectura: str = ""

	@property
	def porcentaje(self) -> int:
		"""Porcentaje utilizable (traducidas y sin errores) sobre el total."""
		if self.total == 0:
			return 100
		return int(100 * max(0, self.traducidas - len(self.errores)) / self.total)

	@property
	def completo(self) -> bool:
		"""True si no queda nada pendiente."""
		return not (self.aproximadas or self.sin_traducir or self.errores or self.ausentes or self.fallo_lectura)


def analizar(archivo: Path, pot: catalogo_po.Catalogo | None = None) -> InformeIdioma:
	"""Analiza un ``.po`` y, si se da la plantilla, lo compara con ella."""
	informe = InformeIdioma(idioma=archivo.parent.parent.name, archivo=archivo)
	try:
		catalogo = catalogo_po.leer_po(archivo)
	except (OSError, UnicodeDecodeError, catalogo_po.ErrorPO) as error:
		informe.fallo_lectura = str(error)
		return informe
	activas = [entrada for entrada in catalogo.entradas if not entrada.obsoleta]
	informe.total = len(activas)
	for entrada in activas:
		if entrada.aproximada:
			informe.aproximadas.append(entrada)
		elif entrada.traducida:
			informe.traducidas += 1
		else:
			informe.sin_traducir.append(entrada)
	informe.errores = list(catalogo_po.mensajes_compilables(catalogo).errores)
	if pot is not None:
		conocidas = {entrada.clave for entrada in activas}
		informe.ausentes = sum(1 for entrada in pot.entradas if not entrada.obsoleta and entrada.clave not in conocidas)
	return informe


def _linea_de(entrada: catalogo_po.Entrada) -> str:
	"""Una cadena pendiente en una línea: texto y dónde aparece en el código."""
	texto = catalogo_po.escapar(entrada.msgid)
	donde = ", ".join(entrada.referencias[:3]) or "sin referencia"
	if len(entrada.referencias) > 3:
		donde += f" y {len(entrada.referencias) - 3} más"
	return f"    «{texto}» ({donde})"


def redactar(informes: list[InformeIdioma], detalle: bool) -> list[str]:
	"""Líneas del informe, sin tablas ni adornos."""
	lineas: list[str] = []
	for informe in informes:
		lineas.append(f"Idioma {informe.idioma} ({informe.archivo.as_posix()}):")
		if informe.fallo_lectura:
			lineas.append(f"  No se pudo leer: {informe.fallo_lectura}")
			lineas.append("")
			continue
		lineas.append(
			f"  Utilizable: {informe.porcentaje} %. Total: {informe.total}. Traducidas: {informe.traducidas}. "
			f"Aproximadas: {len(informe.aproximadas)}. Sin traducir: {len(informe.sin_traducir)}. "
			f"Con errores: {len(informe.errores)}."
		)
		if informe.ausentes:
			lineas.append(f"  Faltan {informe.ausentes} cadenas nuevas de la plantilla: ejecute python tools/actualizar_po.py")
		if detalle:
			if informe.sin_traducir:
				lineas.append("  Sin traducir:")
				lineas.extend(_linea_de(entrada) for entrada in informe.sin_traducir)
			if informe.aproximadas:
				lineas.append("  Aproximadas (revisar y quitar la marca «fuzzy»):")
				lineas.extend(_linea_de(entrada) for entrada in informe.aproximadas)
		if informe.errores:
			lineas.append("  Errores (estas traducciones no se usan):")
			lineas.extend(f"    {error}" for error in informe.errores)
		lineas.append("")
	return lineas


def main(argumentos: list[str] | None = None) -> int:
	"""Punto de entrada de línea de órdenes."""
	analizador = argparse.ArgumentParser(description="Informa de las cadenas sin traducir de cada idioma.")
	analizador.add_argument("idiomas", nargs="*", help="Idiomas que revisar (por defecto, todos).")
	analizador.add_argument("--raiz", type=Path, default=RAIZ, help="Raíz del proyecto.")
	analizador.add_argument("--dominio", help="Dominio gettext (por defecto, DOMINIO de app/core/i18n.py).")
	analizador.add_argument("--detalle", action="store_true", help="Enumera cada cadena pendiente.")
	analizador.add_argument("--estricto", action="store_true", help="Código de salida 1 si queda algo pendiente.")
	analizador.add_argument("--salida", type=Path, help="Guarda el informe en un archivo de texto.")
	opciones = analizador.parse_args(argumentos)
	catalogo_po.preparar_consola()
	raiz = opciones.raiz.resolve()
	dominio = opciones.dominio or catalogo_po.dominio_del_proyecto(raiz)
	locales = raiz / "data" / "locales"
	pot: catalogo_po.Catalogo | None = None
	ruta_pot = locales / f"{dominio}.pot"
	if ruta_pot.is_file():
		try:
			pot = catalogo_po.leer_po(ruta_pot)
		except (OSError, UnicodeDecodeError, catalogo_po.ErrorPO) as error:
			print(f"Aviso: no se pudo leer la plantilla {ruta_pot}: {error}")
	archivos = sorted(locales.glob(f"*/LC_MESSAGES/{dominio}.po"))
	if opciones.idiomas:
		pedidos = {idioma.replace("-", "_") for idioma in opciones.idiomas}
		archivos = [archivo for archivo in archivos if archivo.parent.parent.name in pedidos]
	if not archivos:
		print("No hay traducciones que revisar. Cree una con: python tools/actualizar_po.py --nuevo en")
		return 0
	informes = [analizar(archivo, pot) for archivo in archivos]
	lineas = redactar(informes, opciones.detalle)
	texto = "\n".join(lineas)
	if opciones.salida:
		catalogo_po.escribir_texto_atomico(opciones.salida, texto)
		print(f"Informe guardado en {opciones.salida}.")
	else:
		print(texto)
	hay_errores = any(informe.errores or informe.fallo_lectura for informe in informes)
	if hay_errores or (opciones.estricto and not all(informe.completo for informe in informes)):
		return 1
	return 0


if __name__ == "__main__":
	sys.exit(main())
