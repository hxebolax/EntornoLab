"""Genera un paquete de sonidos con el «Generador de sonidos» del autor (herramienta de DESARROLLO).

Uso (desde la raíz del proyecto)::

	.venv\\Scripts\\python.exe tools\\generar_paquete_sonidos.py
	.venv\\Scripts\\python.exe tools\\generar_paquete_sonidos.py --solo "pasos/*" --conservar
	.venv\\Scripts\\python.exe tools\\generar_paquete_sonidos.py --exe D:\\ruta\\sonido.exe
	.venv\\Scripts\\python.exe tools\\generar_paquete_sonidos.py --desde-receta data\\sounds\\natural\\receta.json

Deja en ``data/sounds/<id>`` un paquete con los mismos nombres que el paquete por defecto (o los que
se puedan), listo para elegirlo en las preferencias. De serie genera el paquete «Natural», cuya
receta está en ``tools/receta_natural.py``.

Qué hace, paso a paso:

1. **Arma una especificación por sonido** (el formato JSON del Generador de sonidos: capas, efectos,
   duración, bucle, mono o estéreo, 44,1 kHz) a partir de la receta y de lo que el catálogo dice de
   cada sonido (si es un bucle, si se sitúa en el espacio, cuánto dura, cuántos canales tiene).
2. **Llama a** ``sonido.exe renderizar lote.json --json`` (la línea de órdenes compilada del
   generador), que escribe un WAV por sonido en una carpeta de trabajo. Solo se usa el motor
   procedural del generador: ninguna capa de inteligencia artificial ni las voces de Windows. La
   ruta del ejecutable se da con ``--exe`` o con la variable ``GENERADOR_SONIDOS_EXE``. Los datos
   del generador se redirigen (``APP_DATA_DIR``) a la carpeta de trabajo: no se escribe nada en su
   carpeta.
3. **Ajusta los agudos**: lo que hay que situar necesita energía por encima de 3 kHz. Si un sonido
   se queda corto, se sube 4 dB la capa o el efecto que la receta marca para eso y se vuelve a
   pedir, hasta seis veces. Lo decide la medida, no el oído.
4. **Comprueba cada sonido midiendo** (no se reproduce nada): duración, canales, pico, silencio en los
   bordes, costura de los bucles, agudos, y que los avisos que codifican algo conservan sus notas y
   su número de toques. **Lo que no cumple no entra en el paquete**: se heredará del de por defecto,
   y queda apuntado con su motivo.
5. **Iguala** cada sonido al nivel del de serie del mismo nombre (``por_defecto/niveles.json``) y lo
   escribe en FLAC de 16 bits. Es lo único que esta herramienta le hace al audio: una ganancia.
6. Escribe ``pack.json``, ``CREDITOS.txt``, ``receta.json`` (las especificaciones exactas enviadas,
   para regenerar el paquete) y ``medidas.json`` (lo medido de cada sonido).

Es reproducible: cada sonido usa una semilla derivada de su nombre.
"""

from __future__ import annotations

import argparse
import copy
import fnmatch
import importlib
import json
import logging
import os
import shutil
import subprocess
import sys
import tempfile
import time
import zlib
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
	sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tools") not in sys.path:
	sys.path.insert(0, str(RAIZ / "tools"))

import numpy as np  # noqa: E402 - necesita la raíz del proyecto en sys.path

from app.audio import niveles, sintesis  # noqa: E402
from app.audio.banco import NOMBRE_FICHA, PAQUETE_POR_DEFECTO  # noqa: E402
from app.core import paths  # noqa: E402

log = logging.getLogger("generar_paquete_sonidos")

# Dónde está ``sonido.exe``: siempre lo dice quien ejecuta la herramienta (``--exe`` o esta variable).
# No hay ruta por defecto escrita aquí: sería la del equipo del autor y acabaría en el repositorio.
VARIABLE_EXE = "GENERADOR_SONIDOS_EXE"
RECETA_POR_DEFECTO = "receta_natural"
FORMATO_RECETA = 1

# Parte mínima de la energía por encima de 3 kHz en un sonido que hay que situar (la misma de las pruebas de la síntesis).
MINIMO_AGUDOS = 0.02
# A lo que se apunta al ajustar, con margen sobre el mínimo.
OBJETIVO_AGUDOS = 0.035
PASO_AGUDOS = 4.0
VUELTAS_AGUDOS = 6
# Pico máximo de un sonido del paquete: el mismo techo que tienen los de serie.
TECHO_PICO = 0.8
# Un sonido puede durar entre la mitad y algo menos del doble que el de serie.
DURACION_MINIMA = 0.5
DURACION_MAXIMA = 1.75
# Hasta aquí la costura de un bucle no se distingue del resto de la onda (la misma vara que en las pruebas).
COSTURA_MAXIMA = 2.0
# Parte de la energía que debe haber alrededor de cada nota que el sonido codifica.
ENERGIA_NOTA = 0.012
SEGUNDOS_POR_SONIDO = 60


class ErrorGenerador(RuntimeError):
	"""El Generador de sonidos no está o no ha podido hacer lo que se le pidió."""


def carpeta_de_serie() -> Path:
	"""La carpeta de sonidos que se distribuye con el programa (la que contiene los paquetes)."""
	return paths.ruta_base() / "data" / "sounds"


# ── Especificaciones ─────────────────────────────────────────────────────────


def _limpiar(objeto: object) -> object:
	"""Copia sin las marcas de la receta (claves que empiezan por «_»): el generador rechaza claves desconocidas."""
	if isinstance(objeto, dict):
		return {clave: _limpiar(valor) for clave, valor in objeto.items() if not str(clave).startswith("_")}
	if isinstance(objeto, list):
		return [_limpiar(valor) for valor in objeto]
	return objeto


def _semilla(nombre: str) -> int:
	"""Semilla propia de cada sonido: estable entre ejecuciones y distinta para cada variante."""
	return zlib.crc32(nombre.encode("utf-8")) % 1000000


def tiene_ajuste(receta: dict) -> bool:
	"""Si la receta marca alguna capa o efecto con los que subir los agudos."""
	return any(capa.get("_aire") for capa in receta.get("capas", [])) or any(efecto.get("_auto") for efecto in receta.get("efectos", []))


def especificacion(
	nombre: str, receta: dict, definicion: sintesis.DefSonido, canales: int, duracion_serie: float, subida: float = 0.0
) -> dict:
	"""La especificación del Generador de sonidos para ``nombre``. ``subida`` son los dB de más en lo marcado para agudos."""
	capas = copy.deepcopy(receta["capas"])
	efectos = copy.deepcopy(receta.get("efectos", []))
	for capa in capas:
		if capa.get("_aire"):
			capa["volumen_db"] = round(float(capa.get("volumen_db", 0.0)) + subida, 1)
	for efecto in efectos:
		if efecto.get("_auto"):
			efecto["ganancia"] = round(float(efecto.get("ganancia", 0.0)) + subida, 1)
	# Un efecto de agudos a 0 dB no hace nada: se quita para no tocar el sonido sin necesidad.
	efectos = [efecto for efecto in efectos if not (efecto.get("_auto") and abs(float(efecto.get("ganancia", 0.0))) < 0.05)]
	duracion = float(receta.get("duracion") or duracion_serie)
	bucle = receta.get("bucle", True if definicion.bucle else None)
	datos: dict = {
		"salida": f"{nombre}.wav",
		"titulo": nombre,
		"semilla": _semilla(nombre),
		"sr_salida": sintesis.FRECUENCIA,
		"bits": 24,
		"normalizar": -3,
		"capas": _limpiar(capas),
	}
	datos["mono" if canales == 1 else "estereo"] = True
	if bucle == "nativo" and not efectos:
		# El generador ya entrega un bucle perfecto de la duración pedida en sus parámetros.
		datos["bucle"] = "nativo"
	elif bucle:
		datos["bucle"] = True
		datos["duracion"] = round(duracion, 4)
	else:
		datos["duracion"] = round(duracion, 4)
		# Entrada y salida sin clic, también cuando la duración corta la cola del sonido.
		efectos.append({"nombre": "fundido", "entrada": 0.002, "salida": round(min(0.03, duracion / 4.0), 4)})
	if efectos:
		datos["efectos"] = _limpiar(efectos)
	return datos


# ── El generador ─────────────────────────────────────────────────────────────


def buscar_exe(indicado: Path | None) -> Path:
	"""El ``sonido.exe`` que se va a usar: el indicado con ``--exe`` o el de la variable de entorno.

	Sin ninguno de los dos se para con un mensaje que dice cómo indicarlo, en lugar de
	probar una ruta fija del equipo de alguien.
	"""
	variable = os.environ.get(VARIABLE_EXE, "").strip()
	candidato = indicado or (Path(variable).expanduser() if variable else None)
	if candidato is None:
		raise ErrorGenerador(
			f"Falta la ruta del Generador de sonidos (sonido.exe). Indíquela con --exe <ruta de sonido.exe> o con la variable de entorno {VARIABLE_EXE}."
		)
	if not candidato.is_file():
		raise ErrorGenerador(
			f"No se encuentra el Generador de sonidos en {candidato}. Indique su ruta con --exe o con la variable {VARIABLE_EXE}."
		)
	return candidato


def _orden(exe: Path, argumentos: list[str], trabajo: Path, espera: float) -> subprocess.CompletedProcess:
	entorno = dict(os.environ)
	# Los datos del generador (caché, registros) van a la carpeta de trabajo: no se toca su instalación.
	entorno["APP_DATA_DIR"] = str(trabajo / "_datos_generador")
	entorno["PYTHONUTF8"] = "1"
	return subprocess.run(  # noqa: S603 - se ejecuta la herramienta del propio autor, con argumentos fijos
		[str(exe), *argumentos], cwd=str(trabajo), env=entorno, capture_output=True, timeout=espera, check=False
	)


def version_generador(exe: Path, trabajo: Path) -> str:
	"""Lo que dice ``sonido.exe diagnostico`` de sí mismo (la primera línea), para los créditos."""
	try:
		resultado = _orden(exe, ["diagnostico"], trabajo, 120)
	except OSError, subprocess.SubprocessError:
		log.warning("No se pudo preguntar su versión al Generador de sonidos.", exc_info=True)
		return "Generador de sonidos"
	lineas = resultado.stdout.decode("utf-8", errors="replace").strip().splitlines()
	return lineas[0].strip().rstrip(".") if lineas else "Generador de sonidos"


def _error_de(resultado: subprocess.CompletedProcess) -> str:
	texto = (resultado.stderr or b"").decode("utf-8", errors="replace").strip() or (resultado.stdout or b"").decode(
		"utf-8", errors="replace"
	).strip()
	return texto.splitlines()[-1][:400] if texto else f"código de salida {resultado.returncode}"


def renderizar(exe: Path, lote: dict[str, dict], trabajo: Path) -> dict[str, str]:
	"""Pide al generador los sonidos de ``lote`` (nombre → especificación). Devuelve ``{nombre: error}`` de los que fallan.

	Primero todos de una vez, que es mucho más rápido; lo que no haya salido se pide de uno en uno
	para saber exactamente cuál falla y por qué.
	"""
	errores: dict[str, str] = {}
	if not lote:
		return errores
	for nombre in lote:
		(trabajo / f"{nombre}.wav").parent.mkdir(parents=True, exist_ok=True)
		(trabajo / f"{nombre}.wav").unlink(missing_ok=True)
	fichero = trabajo / "_lote.json"
	fichero.write_text(json.dumps(list(lote.values()), ensure_ascii=False, indent="\t"), encoding="utf-8")
	try:
		resultado = _orden(exe, ["renderizar", fichero.name, "--json"], trabajo, SEGUNDOS_POR_SONIDO * len(lote) + 300)
		if resultado.returncode != 0:
			log.warning("El lote no se completó (%s); se pide lo que falta de uno en uno.", _error_de(resultado))
	except subprocess.TimeoutExpired:
		log.warning("El generador tardó demasiado con el lote; se pide lo que falta de uno en uno.")
	except OSError as error:
		raise ErrorGenerador(f"No se pudo ejecutar {exe}: {error}") from error
	for nombre, datos in lote.items():
		if (trabajo / f"{nombre}.wav").is_file():
			continue
		uno = trabajo / "_uno.json"
		uno.write_text(json.dumps(datos, ensure_ascii=False), encoding="utf-8")
		try:
			resultado = _orden(exe, ["renderizar", uno.name, "--json"], trabajo, SEGUNDOS_POR_SONIDO + 120)
		except subprocess.TimeoutExpired:
			errores[nombre] = "el generador no terminó a tiempo"
			continue
		except OSError as error:
			raise ErrorGenerador(f"No se pudo ejecutar {exe}: {error}") from error
		if resultado.returncode != 0 or not (trabajo / f"{nombre}.wav").is_file():
			errores[nombre] = "el generador dio error: " + _error_de(resultado)
	return errores


# ── Comprobaciones ───────────────────────────────────────────────────────────


def energia_nota(datos: np.ndarray, hercios: float, frecuencia: int) -> float:
	"""Parte de la energía del sonido que está en esa nota: en su fundamental y en sus tres primeros armónicos.

	Se cuentan los armónicos porque hay instrumentos cuya nota se oye sin que su fundamental suene
	apenas: en una trompeta mandan los armónicos, y unas campanas tubulares solo tienen los parciales
	2, 3 y 4 (el oído reconstruye la nota que falta). Pero sin fundamental se exigen al menos dos
	armónicos: uno solo es, sencillamente, otra nota (la octava o la quinta de arriba).
	"""
	partes = [niveles.energia_en(datos, hercios * armonico, frecuencia) for armonico in (1, 2, 3, 4)]
	if partes[0] >= ENERGIA_NOTA:
		return float(sum(partes))
	presentes = [parte for parte in partes[1:] if parte >= ENERGIA_NOTA / 2.0]
	return float(sum(partes)) if len(presentes) >= 2 else float(partes[0])


def comprobar(
	nombre: str,
	datos: np.ndarray,
	frecuencia: int,
	receta: dict,
	definicion: sintesis.DefSonido,
	canales: int,
	duracion_serie: float,
	objetivo: float,
) -> list[str]:
	"""Los motivos por los que ``datos`` (ya igualado) no puede entrar en el paquete. Lista vacía si vale."""
	problemas: list[str] = []
	if frecuencia != sintesis.FRECUENCIA:
		problemas.append(f"frecuencia de muestreo {frecuencia} en vez de {sintesis.FRECUENCIA}")
	tiene = 1 if datos.ndim == 1 else int(datos.shape[1])
	if tiene != canales:
		problemas.append(f"{tiene} canales en vez de {canales}")
	if len(datos) < 100 or not np.isfinite(datos).all():
		return [*problemas, "vacío o con valores no válidos"]
	duracion = len(datos) / float(frecuencia)
	if definicion.bucle:
		if abs(duracion - objetivo) > 0.01:
			problemas.append(f"el bucle dura {duracion:.3f} s y debía durar {objetivo:.3f} s")
		if duracion < 0.5:
			problemas.append("demasiado corto para un bucle")
		costura = niveles.costura(datos)
		if costura > COSTURA_MAXIMA:
			problemas.append(f"salto en la costura del bucle ({costura:.1f} veces lo normal)")
	else:
		if duracion > objetivo + 0.02:
			problemas.append(f"dura {duracion:.3f} s, más de los {objetivo:.3f} s pedidos")
		bordes = max(float(np.max(np.abs(datos[0]))), float(np.max(np.abs(datos[-1]))))
		if bordes >= 0.01:
			problemas.append(f"no empieza o no acaba en silencio ({bordes:.3f})")
	proporcion = duracion / duracion_serie if duracion_serie > 0 else 1.0
	if not DURACION_MINIMA <= proporcion <= DURACION_MAXIMA:
		problemas.append(f"dura {proporcion:.2f} veces lo que el de serie ({duracion:.2f} s frente a {duracion_serie:.2f} s)")
	pico = niveles.pico(datos)
	if pico > TECHO_PICO + 1e-3:
		problemas.append(f"pico {pico:.3f} por encima de {TECHO_PICO}")
	if float(np.sqrt(np.mean(np.square(datos.astype(np.float64))))) <= 0.005:
		problemas.append("es casi silencio")
	if abs(float(np.mean(datos))) >= 0.01:
		problemas.append("tiene componente continua")
	if definicion.posicionable:
		agudos = sintesis.fraccion_agudos(datos, frecuencia=frecuencia)
		if agudos < MINIMO_AGUDOS:
			problemas.append(f"solo un {agudos * 100:.1f} % de su energía por encima de 3 kHz: no se podría situar delante o detrás")
	pedido = receta.get("comprobar", {})
	for hercios in pedido.get("notas", []):
		parte = energia_nota(datos, float(hercios), frecuencia)
		if parte < ENERGIA_NOTA:
			problemas.append(f"no se encuentra la nota de {hercios:g} Hz que codifica (solo un {parte * 100:.1f} % de la energía)")
	if pedido.get("golpes"):
		cuenta = niveles.golpes(datos, frecuencia)
		if cuenta != int(pedido["golpes"]):
			problemas.append(f"se cuentan {cuenta} toques y deben ser {pedido['golpes']}")
	return problemas


# ── Textos del paquete ───────────────────────────────────────────────────────


def _creditos(ficha: dict, generador: str, hechos: int, total: int, heredados: dict[str, str], orden: str) -> str:
	lineas = [
		f"PAQUETE DE SONIDOS «{str(ficha.get('nombre', '')).upper()}» DE ENTORNOLAB",
		"",
		str(ficha.get("descripcion", "")),
		"",
		f"Trae {hechos} de los {total} sonidos del catálogo. Lo que no trae suena con el paquete por defecto.",
		"",
		"CÓMO SE HIZO",
		f"  Con el {generador}, la herramienta del propio autor de EntornoLab, usando solo su motor",
		"  procedural (modelos físicos, instrumentos y efectos) por la línea de órdenes compilada:",
		"      sonido.exe renderizar lote.json --json",
		"  No se ha usado ninguno de sus motores de inteligencia artificial, ni grabaciones, ni las voces",
		"  de Windows. Después, cada sonido se ha llevado al nivel del sonido de serie del mismo nombre",
		"  (una ganancia) y se ha guardado en FLAC de 16 bits a 44,1 kHz.",
		"",
		"  La receta completa (las especificaciones enviadas al generador, con sus semillas) está en",
		"  receta.json, y lo que se midió de cada sonido, en medidas.json. Para regenerarlo:",
		f"      {orden}",
		"",
		"QUÉ SE CONSERVA DEL PAQUETE POR DEFECTO",
		"  Los nombres, las duraciones aproximadas, los bucles sin costura y el contenido por encima de",
		"  3 kHz de todo lo que se sitúa en el espacio. Los avisos que codifican algo (balizas, bastón",
		"  sonoro, brújula, plantas del ascensor, premios, menús, semáforos) conservan sus notas exactas,",
		"  su número de toques y su ritmo: solo cambia el instrumento que los toca.",
		"",
		"LICENCIA",
		f"  {ficha.get('licencia', '')}",
		"  Son sonidos generados por procedimiento con una herramienta del autor: no tienen derechos de terceros.",
		"",
	]
	if heredados:
		lineas.append("SONIDOS QUE NO ESTÁN EN ESTE PAQUETE (suenan con el de por defecto) Y POR QUÉ")
		for nombre, motivo in heredados.items():
			lineas.append(f"  {nombre}: {motivo}")
		lineas.append("")
	return "\n".join(lineas)


def _escribir_texto(ruta: Path, texto: str) -> None:
	"""Escribe un fichero de texto de forma atómica (temporal al lado y renombrado)."""
	ruta.parent.mkdir(parents=True, exist_ok=True)
	temporal = ruta.with_name(ruta.name + ".tmp")
	temporal.write_text(texto, encoding="utf-8", newline="\n")
	os.replace(temporal, ruta)


# ── Programa ─────────────────────────────────────────────────────────────────


def _argumentos(argv: list[str] | None) -> argparse.Namespace:
	analizador = argparse.ArgumentParser(
		description="Genera un paquete de sonidos de EntornoLab con el Generador de sonidos (sin inteligencia artificial)."
	)
	analizador.add_argument(
		"--exe",
		type=Path,
		default=None,
		help=f"ruta de sonido.exe (por defecto, la de la variable de entorno {VARIABLE_EXE}; una de las dos es obligatoria)",
	)
	analizador.add_argument("--receta", default=RECETA_POR_DEFECTO, help="módulo de tools con la receta (por defecto, receta_natural)")
	analizador.add_argument(
		"--desde-receta", type=Path, default=None, help="regenerar a partir de un receta.json ya escrito, sin volver a ajustar nada"
	)
	analizador.add_argument(
		"--carpeta", type=Path, default=None, help="carpeta de sonidos de destino (por defecto, data/sounds del programa)"
	)
	analizador.add_argument(
		"--solo", default=None, help="patrón de nombres que regenerar, por ejemplo «pasos/*» (el resto del paquete no se toca)"
	)
	analizador.add_argument(
		"--trabajo", type=Path, default=None, help="carpeta de trabajo para los WAV intermedios (por defecto, una temporal)"
	)
	analizador.add_argument("--conservar", action="store_true", help="no borrar la carpeta de trabajo al terminar")
	return analizador.parse_args(argv)


def _de_serie(paquete: Path) -> dict[str, tuple[int, float]]:
	"""(canales, duración) de cada sonido del paquete por defecto: el molde del paquete nuevo."""
	import soundfile

	molde: dict[str, tuple[int, float]] = {}
	for nombre in sintesis.nombres():
		ruta = sintesis.fichero_de(paquete, nombre)
		if ruta is not None:
			info = soundfile.info(str(ruta))
			molde[nombre] = (int(info.channels), info.frames / float(info.samplerate))
		else:
			datos = sintesis.generar(nombre)
			molde[nombre] = (1 if datos.ndim == 1 else int(datos.shape[1]), len(datos) / float(sintesis.FRECUENCIA))
	return molde


def generar(argumentos: argparse.Namespace) -> int:
	"""Hace el paquete. Devuelve el código de salida del proceso."""
	exe = buscar_exe(argumentos.exe)
	carpeta = (argumentos.carpeta or carpeta_de_serie()).resolve()
	referencias = niveles.leer_niveles(carpeta / PAQUETE_POR_DEFECTO)
	molde = _de_serie(carpeta / PAQUETE_POR_DEFECTO)
	guardada: dict = {}
	if argumentos.desde_receta is not None:
		guardada = json.loads(argumentos.desde_receta.read_text(encoding="utf-8"))
		ficha = dict(guardada["ficha"])
		# De la receta guardada solo hace falta lo que hay que comprobar: la especificación se envía tal cual.
		recetas = {
			nombre: ({"comprobar": datos["comprobar"]} if datos.get("comprobar") else {}) for nombre, datos in guardada["sonidos"].items()
		}
		identificador = str(ficha["id"])
	else:
		modulo = importlib.import_module(argumentos.receta)
		ficha = dict(modulo.FICHA)
		recetas = modulo.recetas()
		identificador = str(modulo.ID)
	desconocidos = sorted(set(recetas) - set(sintesis.CATALOGO))
	if desconocidos:
		log.warning("La receta trae sonidos que no están en el catálogo y se ignoran: %s", ", ".join(desconocidos))
	elegidos = [
		nombre
		for nombre in sintesis.nombres()
		if nombre in recetas and (not argumentos.solo or fnmatch.fnmatchcase(nombre, argumentos.solo))
	]
	if not elegidos:
		log.error("No hay ningún sonido que generar (patrón «%s»).", argumentos.solo)
		return 1
	destino = carpeta / identificador
	trabajo = (argumentos.trabajo or Path(tempfile.mkdtemp(prefix="entornolab_paquete_"))).resolve()
	trabajo.mkdir(parents=True, exist_ok=True)
	inicio = time.perf_counter()
	generador = version_generador(exe, trabajo)
	log.info("%s. Ejecutable: %s", generador, exe)
	log.info("Carpeta de trabajo: %s", trabajo)

	# 1 y 2. Especificaciones y primera pasada.
	subidas: dict[str, float] = dict.fromkeys(elegidos, 0.0)
	enviadas: dict[str, dict] = {}
	errores: dict[str, str] = {}

	def pedir(nombres: list[str]) -> None:
		lote = {}
		for nombre in nombres:
			if guardada:
				lote[nombre] = guardada["sonidos"][nombre]["especificacion"]
			else:
				canales, duracion = molde[nombre]
				lote[nombre] = especificacion(nombre, recetas[nombre], sintesis.CATALOGO[nombre], canales, duracion, subidas[nombre])
		enviadas.update(lote)
		for nombre in nombres:
			errores.pop(nombre, None)
		errores.update(renderizar(exe, lote, trabajo))

	pedir(elegidos)

	# 3. Agudos: se sube lo marcado en la receta hasta llegar al objetivo.
	if not guardada:
		for vuelta in range(1, VUELTAS_AGUDOS + 1):
			cortos = []
			for nombre in elegidos:
				if nombre in errores or not sintesis.CATALOGO[nombre].posicionable or not tiene_ajuste(recetas[nombre]):
					continue
				datos, frecuencia = sintesis.leer_audio(trabajo / f"{nombre}.wav")
				if sintesis.fraccion_agudos(datos, frecuencia=frecuencia) < OBJETIVO_AGUDOS:
					subidas[nombre] += PASO_AGUDOS
					cortos.append(nombre)
			if not cortos:
				break
			log.info("Vuelta %s de agudos: %s sonidos suben %s dB.", vuelta, len(cortos), PASO_AGUDOS)
			pedir(cortos)

	# 4 y 5. Comprobar, igualar y escribir.
	medidas: dict[str, dict] = {}
	heredados: dict[str, str] = {}
	escritos = 0
	for nombre in elegidos:
		for extension in sintesis.FORMATOS_AUDIO:
			(destino / f"{nombre}{extension}").unlink(missing_ok=True)
		if nombre in errores:
			heredados[nombre] = errores[nombre]
			continue
		definicion = sintesis.CATALOGO[nombre]
		canales, duracion_serie = molde[nombre]
		datos, frecuencia = sintesis.leer_audio(trabajo / f"{nombre}.wav")
		referencia = referencias.get(nombre)
		if referencia is not None:
			datos = niveles.igualar(datos, referencia[0], frecuencia, techo=TECHO_PICO)
		elif niveles.pico(datos) > TECHO_PICO:
			datos = (datos * np.float32(TECHO_PICO / niveles.pico(datos))).astype(np.float32)
		receta = recetas[nombre]
		objetivo = float(enviadas[nombre].get("duracion") or receta.get("duracion") or duracion_serie)
		problemas = comprobar(nombre, datos, frecuencia, receta, definicion, canales, duracion_serie, objetivo)
		ficha_medida = niveles.medir(datos, frecuencia)
		ficha_medida["duracion_serie"] = round(duracion_serie, 3)
		ficha_medida["nivel_serie"] = round(referencia[0], 5) if referencia is not None else None
		ficha_medida["subida_agudos_db"] = subidas.get(nombre, 0.0)
		if receta.get("comprobar", {}).get("golpes"):
			ficha_medida["toques"] = niveles.golpes(datos, frecuencia)
		if receta.get("comprobar", {}).get("notas"):
			ficha_medida["notas"] = {
				f"{hercios:g}": round(energia_nota(datos, float(hercios), frecuencia), 3) for hercios in receta["comprobar"]["notas"]
			}
		ficha_medida["en_el_paquete"] = not problemas
		if problemas:
			ficha_medida["motivo"] = "; ".join(problemas)
			heredados[nombre] = "; ".join(problemas)
		else:
			sintesis.escribir_audio(destino / f"{nombre}.flac", datos, frecuencia)
			escritos += 1
		medidas[nombre] = ficha_medida

	# 6. Ficha, créditos, receta y medidas. Con --solo se conserva lo ya apuntado de los demás sonidos.
	anteriores_medidas: dict = {}
	anterior_receta: dict = {}
	if argumentos.solo:
		for ruta, cubo in ((destino / "medidas.json", anteriores_medidas), (destino / "receta.json", anterior_receta)):
			if ruta.is_file():
				try:
					cubo.update(json.loads(ruta.read_text(encoding="utf-8")))
				except OSError, ValueError:
					log.warning("No se pudo leer %s; se reescribe solo con lo de ahora.", ruta, exc_info=True)
	todas_medidas = dict(anteriores_medidas.get("sonidos", {}))
	todas_medidas.update(medidas)
	todas_recetas = dict(anterior_receta.get("sonidos", {}))
	for nombre in elegidos:
		entrada: dict = {"especificacion": enviadas[nombre]}
		if recetas[nombre].get("comprobar"):
			entrada["comprobar"] = recetas[nombre]["comprobar"]
		todas_recetas[nombre] = entrada
	catalogo = sintesis.nombres()
	presentes = [nombre for nombre in catalogo if sintesis.fichero_de(destino, nombre) is not None]
	todos_heredados = {
		nombre: str(todas_medidas.get(nombre, {}).get("motivo") or heredados.get(nombre) or "no está en la receta")
		for nombre in catalogo
		if nombre not in presentes
	}
	orden = f".venv\\Scripts\\python.exe tools\\generar_paquete_sonidos.py --desde-receta data\\sounds\\{identificador}\\receta.json"
	ficha["generado"] = (
		f"{generador}, solo con su motor procedural (sonido.exe renderizar), sin inteligencia artificial. "
		f"Receta en receta.json; herramienta: tools/generar_paquete_sonidos.py."
	)
	ficha["sonidos"] = len(presentes)
	ficha["heredados"] = sorted(todos_heredados)
	_escribir_texto(destino / NOMBRE_FICHA, json.dumps(ficha, ensure_ascii=False, indent="\t") + "\n")
	_escribir_texto(destino / "CREDITOS.txt", _creditos(ficha, generador, len(presentes), len(catalogo), todos_heredados, orden))
	receta_final = {
		"formato": FORMATO_RECETA,
		"explicacion": (
			"Especificaciones enviadas a «sonido.exe renderizar» del Generador de sonidos, una por sonido (la salida es relativa a la carpeta de trabajo). "
			"Después solo se iguala el nivel de cada sonido al de serie y se guarda en FLAC."
		),
		"generador": generador,
		"ficha": {clave: valor for clave, valor in ficha.items() if clave not in ("sonidos", "heredados", "generado")},
		"sonidos": {nombre: todas_recetas[nombre] for nombre in catalogo if nombre in todas_recetas},
	}
	_escribir_texto(destino / "receta.json", json.dumps(receta_final, ensure_ascii=False, indent="\t") + "\n")
	medidas_final = {
		"formato": 1,
		"explicacion": (
			"Lo medido de cada sonido tras igualarlo: duración (s), canales, pico, nivel (media cuadrática del tramo de 0,3 s más fuerte), rms, "
			"agudos (parte de la energía por encima de 3 kHz), centroide del espectro (Hz) y costura (salto del bucle respecto de lo normal)."
		),
		"sonidos": {nombre: todas_medidas[nombre] for nombre in catalogo if nombre in todas_medidas},
	}
	_escribir_texto(destino / "medidas.json", json.dumps(medidas_final, ensure_ascii=False, indent="\t") + "\n")

	log.info("")
	log.info(
		"%s sonidos escritos en %s en %.0f s. El paquete tiene %s de %s.",
		escritos,
		destino,
		time.perf_counter() - inicio,
		len(presentes),
		len(catalogo),
	)
	for nombre, motivo in heredados.items():
		log.warning("NO entra en el paquete (se hereda del de por defecto): %s: %s", nombre, motivo)
	if argumentos.conservar or argumentos.trabajo is not None:
		log.info("Los WAV intermedios quedan en %s.", trabajo)
	else:
		shutil.rmtree(trabajo, ignore_errors=True)
	return 0 if escritos else 1


def main(argv: list[str] | None = None) -> int:
	"""Punto de entrada. Devuelve el código de salida del proceso."""
	logging.basicConfig(level=logging.INFO, format="%(message)s")
	try:
		return generar(_argumentos(argv))
	except ErrorGenerador as error:
		log.error("%s", error)
		return 1
	except OSError, ValueError, KeyError:
		log.exception("No se pudo generar el paquete de sonidos.")
		return 1


if __name__ == "__main__":
	sys.exit(main())
