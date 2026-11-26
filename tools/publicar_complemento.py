"""Publica un complemento en el catálogo en línea de EntornoLab.

El catálogo vive en un repositorio aparte, ``hxebolax/EntornoLab-complementos``,
clonado en una carpeta de su equipo. Esta herramienta empaqueta un
complemento, lo deja en ``paquetes/`` de ese repositorio y actualiza y FIRMA
su índice ``catalogo.json``. No toca Git: al final dice qué hay que confirmar
y subir.

Uso (desde la raíz del proyecto)::

	python tools/publicar_complemento.py hogar --catalogo D:\\Repos\\EntornoLab-complementos
	python tools/publicar_complemento.py D:\\Recibidos\\parque --catalogo ...     (una carpeta cualquiera)
	python tools/publicar_complemento.py hogar ciudad --catalogo ... --version-minima 0.2.0
	python tools/publicar_complemento.py --quitar parque --catalogo ...
	python tools/publicar_complemento.py --listar --catalogo ...
	python tools/publicar_complemento.py hogar --catalogo ... --simular           (no escribe nada)

Un nombre sin ruta se busca en ``data/plugins/<id>``. La carpeta del catálogo
también puede venir en la variable de entorno ``ENTORNOLAB_CATALOGO``.

Qué hace con cada complemento:

1. Lo valida (``validar_complemento``): con errores no se publica.
2. Lo empaqueta como ``<id>-<versión>.elabc`` solo con los ficheros admitidos.
3. Pasa el paquete por la MISMA revisión que hará la aplicación al instalarlo
   (solo datos: ni ejecutables ni guiones ni rutas raras).
4. Calcula tamaño y SHA-256 y sustituye su entrada en el índice. Se niega a
   publicar una versión que no sea mayor que la ya publicada (``--forzar``).
5. Sube el número de serie del índice, lo firma y lo verifica con las claves
   públicas que lleva la aplicación.

Formato del índice y revisión de complementos de terceros:
``docs/catalogo-de-complementos.md``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import date, datetime, timezone
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
for _ruta in (str(RAIZ), str(RAIZ / "tools")):
	if _ruta not in sys.path:
		sys.path.insert(0, _ruta)

import firmar_version  # noqa: E402

from app.dominio import catalogo as dominio  # noqa: E402
from app.services import actualizador  # noqa: E402
from app.services import complementos_en_linea as servicio  # noqa: E402

VARIABLE_CATALOGO = "ENTORNOLAB_CATALOGO"
NOMBRE_INDICE = "catalogo.json"
CARPETA_PAQUETES = "paquetes"


class ErrorPublicacion(Exception):
	"""Algo impide publicar; el mensaje dice qué hay que arreglar."""


def carpeta_de(nombre: str) -> Path:
	"""Carpeta del complemento: una ruta, o el identificador de uno de ``data/plugins``."""
	directa = Path(nombre)
	if directa.is_dir():
		return directa.resolve()
	en_proyecto = RAIZ / "data" / "plugins" / nombre
	if en_proyecto.is_dir():
		return en_proyecto
	raise ErrorPublicacion(f"No se encuentra el complemento «{nombre}» (ni como carpeta ni en data/plugins).")


def leer_indice(carpeta_catalogo: Path) -> dict:
	"""Lee el índice del repositorio del catálogo; si no existe, empieza uno vacío."""
	ruta = carpeta_catalogo / NOMBRE_INDICE
	if not ruta.is_file():
		return {"formato": servicio.FORMATO_INDICE, "tipo": servicio.TIPO_INDICE, "app": "EntornoLab", "serie": 0, "complementos": []}
	try:
		indice = json.loads(ruta.read_text(encoding="utf-8"))
	except (OSError, ValueError) as error:
		raise ErrorPublicacion(f"No se puede leer {ruta}: {error}") from error
	if not isinstance(indice, dict) or not isinstance(indice.get("complementos"), list):
		raise ErrorPublicacion(f"{ruta} no tiene la estructura de un catálogo.")
	return indice


def guardar_indice(carpeta_catalogo: Path, indice: dict, clave: Path | None, claves_publicas: tuple[str, ...] | None = None) -> dict:
	"""Sube la serie, ordena, firma, verifica y escribe el índice. Devuelve el índice firmado."""
	indice = {clave_: valor for clave_, valor in indice.items() if clave_ != firmar_version.CAMPO_FIRMA}
	indice["formato"] = servicio.FORMATO_INDICE
	indice["tipo"] = servicio.TIPO_INDICE
	indice["app"] = "EntornoLab"
	indice["serie"] = int(indice.get("serie") or 0) + 1
	indice["generado"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
	indice["complementos"] = sorted(indice["complementos"], key=lambda entrada: str(entrada.get("id")))
	ruta_clave = clave or firmar_version.ruta_clave_privada()
	if not ruta_clave.is_file():
		raise ErrorPublicacion(f"No se encuentra la clave privada de firma ({ruta_clave}). Créela con tools/generar_claves.py.")
	firmado = firmar_version.firmar_datos(indice, ruta_clave)
	publicas = actualizador.CLAVES_PUBLICAS_ED25519 if claves_publicas is None else claves_publicas
	if not firmar_version.firma_valida(firmado, list(publicas)):
		raise ErrorPublicacion(
			"La clave con la que se ha firmado NO es ninguna de las que acepta la aplicación: las instalaciones rechazarían el catálogo."
		)
	(carpeta_catalogo / NOMBRE_INDICE).write_text(json.dumps(firmado, indent="\t", ensure_ascii=False) + "\n", encoding="utf-8")
	return firmado


def entrada_de(carpeta: Path, paquete: Path, version_minima: str) -> dict:
	"""Entrada del índice para un complemento ya empaquetado."""
	ficha = json.loads((carpeta / dominio.NOMBRE_FICHA).read_text(encoding="utf-8-sig"))
	objetos = ficha.get("objetos") if isinstance(ficha.get("objetos"), list) else []
	nombres = ficha.get("categorias") if isinstance(ficha.get("categorias"), dict) else {}
	categorias = sorted(
		{str(nombres.get(o.get("categoria"), o.get("categoria"))) for o in objetos if isinstance(o, dict) and o.get("categoria")}
	)
	datos = paquete.read_bytes()
	return {
		"id": str(ficha["id"]),
		"nombre": str(ficha.get("nombre") or ficha["id"]),
		"descripcion": str(ficha.get("descripcion") or ""),
		"autor": str(ficha.get("autor") or ""),
		"licencia": str(ficha.get("licencia") or ""),
		"version": str(ficha.get("version") or ""),
		"version_minima_app": version_minima,
		"categorias": categorias,
		"objetos": len(objetos),
		"tamano": len(datos),
		"url": f"{CARPETA_PAQUETES}/{paquete.name}",
		"sha256": hashlib.sha256(datos).hexdigest(),
		"fecha": date.today().isoformat(),
	}


def preparar_complemento(carpeta: Path, destino: Path, indice: dict, version_minima: str, forzar: bool = False) -> tuple[dict, Path]:
	"""Valida, empaqueta y revisa un complemento. Devuelve (entrada del índice, paquete).

	:param destino: carpeta ``paquetes`` donde dejar el ``.elabc``.
	:raises ErrorPublicacion: si no es válido, trae algo que no son datos o la versión no sube.
	"""
	errores = [aviso for aviso in dominio.validar_complemento(carpeta) if aviso.gravedad == "error"]
	if errores:
		raise ErrorPublicacion(f"«{carpeta.name}» no es válido:\n  - " + "\n  - ".join(aviso.mensaje for aviso in errores))
	ficha = json.loads((carpeta / dominio.NOMBRE_FICHA).read_text(encoding="utf-8-sig"))
	identificador, version = str(ficha.get("id") or ""), str(ficha.get("version") or "")
	try:
		actualizador.clave_version(version)
		actualizador.clave_version(version_minima)
	except actualizador.VersionInvalida as error:
		raise ErrorPublicacion(f"«{identificador}»: {error}. Use versiones como 1.0 o 1.2.3.") from error
	publicada = next((entrada for entrada in indice["complementos"] if entrada.get("id") == identificador), None)
	if publicada and not forzar and not actualizador.es_mas_nueva(version, str(publicada.get("version") or "0")):
		raise ErrorPublicacion(
			f"«{identificador}» ya está publicado en la versión {publicada.get('version')}; suba «version» en su "
			f"complemento.json (ahora {version}) o use --forzar."
		)
	destino.mkdir(parents=True, exist_ok=True)
	paquete = destino / f"{identificador}-{version}{dominio.EXTENSION_COMPLEMENTO}"
	try:
		dominio.empaquetar_complemento(carpeta, paquete)
		servicio.revisar_paquete(paquete, identificador)
	except (dominio.ErrorComplemento, servicio.ErrorPaqueteComplemento) as error:
		paquete.unlink(missing_ok=True)
		raise ErrorPublicacion(f"«{identificador}»: {error}") from error
	if paquete.stat().st_size > servicio.MAX_PAQUETE:
		paquete.unlink(missing_ok=True)
		raise ErrorPublicacion(f"«{identificador}» ocupa más de {servicio.MAX_PAQUETE // 1_048_576} MB: la aplicación no lo aceptaría.")
	return entrada_de(carpeta, paquete, version_minima), paquete


def publicar(
	nombres: list[str],
	carpeta_catalogo: Path,
	version_minima: str = "0.1.0",
	clave: Path | None = None,
	forzar: bool = False,
	simular: bool = False,
	claves_publicas: tuple[str, ...] | None = None,
) -> list[dict]:
	"""Empaqueta los complementos indicados y actualiza y firma el índice. Devuelve sus entradas."""
	if not carpeta_catalogo.is_dir():
		raise ErrorPublicacion(f"No existe la carpeta del catálogo: {carpeta_catalogo}")
	indice = leer_indice(carpeta_catalogo)
	destino = carpeta_catalogo / CARPETA_PAQUETES
	if simular:
		import tempfile

		with tempfile.TemporaryDirectory(prefix="entornolab_complemento_") as temporal:
			entradas = [preparar_complemento(carpeta_de(nombre), Path(temporal), indice, version_minima, forzar)[0] for nombre in nombres]
		for entrada in entradas:
			print(
				f"SIMULACIÓN: se publicaría {entrada['id']} {entrada['version']} ({entrada['tamano']} bytes, {entrada['objetos']} objetos)."
			)
		print(f"SIMULACIÓN: el índice pasaría a la serie {int(indice.get('serie') or 0) + 1}. No se ha escrito nada.")
		return entradas
	entradas = []
	for nombre in nombres:
		entrada, paquete = preparar_complemento(carpeta_de(nombre), destino, indice, version_minima, forzar)
		anterior = next((vieja for vieja in indice["complementos"] if vieja.get("id") == entrada["id"]), None)
		if anterior is not None:
			viejo = carpeta_catalogo / str(anterior.get("url") or "")
			if viejo.is_file() and viejo.resolve() != paquete.resolve() and viejo.resolve().is_relative_to(destino.resolve()):
				viejo.unlink()  # el índice ya no lo nombra; el historial de Git lo conserva
		indice["complementos"] = [vieja for vieja in indice["complementos"] if vieja.get("id") != entrada["id"]] + [entrada]
		entradas.append(entrada)
		print(f"Empaquetado {paquete.name}: {entrada['tamano']} bytes, {entrada['objetos']} objetos, SHA-256 {entrada['sha256'][:16]}…")
	firmado = guardar_indice(carpeta_catalogo, indice, clave, claves_publicas)
	print(f"Índice firmado y verificado: {len(firmado['complementos'])} complementos, serie {firmado['serie']}.")
	return entradas


def quitar(identificador: str, carpeta_catalogo: Path, clave: Path | None = None, claves_publicas: tuple[str, ...] | None = None) -> None:
	"""Retira un complemento del catálogo (las copias ya instaladas no se tocan)."""
	indice = leer_indice(carpeta_catalogo)
	entrada = next((vieja for vieja in indice["complementos"] if vieja.get("id") == identificador), None)
	if entrada is None:
		raise ErrorPublicacion(f"«{identificador}» no está en el catálogo.")
	paquete = carpeta_catalogo / str(entrada.get("url") or "")
	if paquete.is_file() and paquete.resolve().is_relative_to((carpeta_catalogo / CARPETA_PAQUETES).resolve()):
		paquete.unlink()
	indice["complementos"] = [vieja for vieja in indice["complementos"] if vieja.get("id") != identificador]
	firmado = guardar_indice(carpeta_catalogo, indice, clave, claves_publicas)
	print(f"«{identificador}» retirado. Índice firmado: serie {firmado['serie']}.")


def main(argumentos: list[str] | None = None) -> int:
	"""Interfaz de línea de órdenes."""
	analizador = argparse.ArgumentParser(description="Publica complementos en el catálogo en línea de EntornoLab.")
	analizador.add_argument("complementos", nargs="*", help="Identificadores de data/plugins o carpetas de complementos.")
	analizador.add_argument("--catalogo", type=Path, help=f"Carpeta del repositorio del catálogo (o la variable {VARIABLE_CATALOGO}).")
	analizador.add_argument("--version-minima", default="0.1.0", help="Versión mínima de la aplicación que necesita (por defecto 0.1.0).")
	analizador.add_argument("--clave", type=Path, help="Clave privada (por defecto, la de ENTORNOLAB_CLAVES).")
	analizador.add_argument("--forzar", action="store_true", help="Publica aunque la versión no sea mayor que la ya publicada.")
	analizador.add_argument("--simular", action="store_true", help="Valida y empaqueta en una carpeta temporal; no escribe en el catálogo.")
	analizador.add_argument("--quitar", metavar="ID", help="Retira un complemento del catálogo.")
	analizador.add_argument("--listar", action="store_true", help="Muestra lo publicado.")
	opciones = analizador.parse_args(argumentos)
	for flujo in (sys.stdout, sys.stderr):
		if hasattr(flujo, "reconfigure"):
			flujo.reconfigure(errors="replace")
	carpeta = opciones.catalogo or (Path(os.environ[VARIABLE_CATALOGO]) if os.environ.get(VARIABLE_CATALOGO) else None)
	if carpeta is None:
		print(f"ERROR: indique la carpeta del catálogo con --catalogo o con la variable {VARIABLE_CATALOGO}.", file=sys.stderr)
		return 1
	try:
		if opciones.listar:
			indice = leer_indice(carpeta)
			print(f"Serie {indice.get('serie', 0)}, {len(indice['complementos'])} complementos:")
			for entrada in indice["complementos"]:
				print(f"  {entrada.get('id')} {entrada.get('version')} ({entrada.get('objetos')} objetos, {entrada.get('tamano')} bytes)")
			return 0
		if opciones.quitar:
			quitar(opciones.quitar, carpeta, opciones.clave)
		elif opciones.complementos:
			publicar(opciones.complementos, carpeta, opciones.version_minima, opciones.clave, opciones.forzar, opciones.simular)
		else:
			analizador.error("indique al menos un complemento, --quitar o --listar")
	except ErrorPublicacion as error:
		print(f"ERROR: {error}", file=sys.stderr)
		return 1
	if not opciones.simular:
		print("\nPara que llegue a los usuarios, confirme y suba los cambios del repositorio del catálogo:")
		print(f'  git -C "{carpeta}" add {NOMBRE_INDICE} {CARPETA_PAQUETES}')
		print(f'  git -C "{carpeta}" commit -m "Catálogo: actualización de complementos"')
		print(f'  git -C "{carpeta}" push')
	return 0


if __name__ == "__main__":
	sys.exit(main())
