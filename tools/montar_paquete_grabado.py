"""Monta un paquete de sonidos con grabaciones reales de uso libre (herramienta de DESARROLLO).

Uso (desde la raíz del proyecto)::

	.venv\\Scripts\\python.exe tools\\montar_paquete_grabado.py
	.venv\\Scripts\\python.exe tools\\montar_paquete_grabado.py --fuentes D:\\ruta\\a\\los\\originales --descargadas D:\\ruta\\a\\lo\\descargado
	.venv\\Scripts\\python.exe tools\\montar_paquete_grabado.py --solo "pasos/*"
	.venv\\Scripts\\python.exe tools\\montar_paquete_grabado.py --comparar

Deja en ``data/sounds/<id>`` un paquete parcial con los mismos nombres que el paquete por defecto,
hecho con grabaciones cuya licencia consta y permite redistribuirlas. De serie monta el paquete
«Grabado», cuya tabla está en ``tools/receta_grabado.py``: de qué fichero original sale cada sonido,
qué tramo se toma y con qué fundidos.

**Los originales no se copian al repositorio.** Se leen de dos carpetas y en el paquete solo quedan
los FLAC finales, ya recortados. Quien no tenga los originales no puede regenerar el paquete, pero sí
usarlo: es lo que viaja.

- La de los originales que el autor ya tenía (``--fuentes``, la variable ``ENTORNOLAB_FUENTES_SONIDO``
  ; una de las dos es obligatoria: el autor la tiene en la carpeta ``adjuntos`` de Puerto Bravo).
- La de lo **descargado para este paquete** (``--descargadas``, la variable
  ``ENTORNOLAB_FUENTES_DESCARGADAS`` o, por defecto, ``adjuntos/fuentes_sonido`` de este proyecto, que
  no se sube al repositorio). De ahí salen las colecciones que en la receta llevan
  ``"raiz": "descargadas"``. Su ``inventario.json`` dice página, autor, licencia y SHA-256 de cada
  fichero. Si la carpeta falta, esos sonidos no entran y quedan apuntados con su motivo.

Qué se le hace a cada grabación, y nada más:

1. **Canales**: a mono lo que se sitúa en el espacio (y todo lo que es mono de serie); los ambientes
   se quedan en estéreo, y si la grabación es mono no sirve para un ambiente.
2. **Remuestreo** a 44,1 kHz.
3. **Tramo**: desde ``inicio`` (afinado al primer ataque si la receta lo pide) y con la ``duracion``
   de la receta. Los pasos y los golpes se recortan: no pueden durar mucho más que los de serie.
4. **Fundidos** de entrada y de salida para que no haya clic; en los bucles, **fundido cruzado** del
   final con el principio, para que la costura no se oiga.
5. **Ganancia** para llevarlo al nivel del sonido de serie del mismo nombre (``niveles.igualar``),
   sin pasar de un pico prudente.

No se filtra, no se ecualiza y no se añade nada: si una grabación no tiene agudos por encima de
3 kHz y hay que situarla, **no entra** (no se «arregla» con ruido).

Después **se comprueba midiendo**, con las mismas varas que el paquete «Natural»
(``generar_paquete_sonidos.comprobar``): frecuencia, canales, duración entre 0,5 y 1,75 veces la de
serie (exacta en los bucles), pico, bordes en silencio, costura, componente continua y agudos; y
una más, propia de las grabaciones: que el igualado no lo deje más de 6 dB por debajo del de serie. Lo que
no cumple no se escribe: se hereda del paquete por defecto y queda apuntado con su motivo. También se
mide lo que más importa para orientarse: cuánto se separan unos suelos de otros y unos materiales de
otros, comparado con los otros paquetes.

No reproduce nada por los altavoces.
"""

from __future__ import annotations

import argparse
import fnmatch
import importlib
import json
import logging
import os
import sys
import time
from pathlib import Path

RAIZ = Path(__file__).resolve().parent.parent
if str(RAIZ) not in sys.path:
	sys.path.insert(0, str(RAIZ))
if str(RAIZ / "tools") not in sys.path:
	sys.path.insert(0, str(RAIZ / "tools"))

import numpy as np  # noqa: E402 - necesita la raíz del proyecto en sys.path

import generar_paquete_sonidos as molde_natural  # noqa: E402 - las mismas comprobaciones que el paquete «Natural»

from app.audio import niveles, sintesis  # noqa: E402
from app.audio.banco import NOMBRE_FICHA, PAQUETE_POR_DEFECTO  # noqa: E402

log = logging.getLogger("montar_paquete_grabado")

# Carpeta de los originales que el autor ya tenía: siempre la dice quien ejecuta la herramienta
# (``--fuentes`` o esta variable). Una ruta por defecto escrita aquí sería la del equipo del autor.
VARIABLE_FUENTES = "ENTORNOLAB_FUENTES_SONIDO"
# Segunda carpeta de originales: lo descargado expresamente para el paquete (no se sube al repositorio).
DESCARGADAS_POR_DEFECTO = RAIZ / "adjuntos" / "fuentes_sonido"
VARIABLE_DESCARGADAS = "ENTORNOLAB_FUENTES_DESCARGADAS"
RAIZ_ORIGINALES = "originales"
RAIZ_DESCARGADAS = "descargadas"
RECETA_POR_DEFECTO = "receta_grabado"
FORMATO_RECETA = 1
FRECUENCIA = sintesis.FRECUENCIA
# Las mismas varas que el paquete «Natural».
TECHO_PICO = molde_natural.TECHO_PICO
MINIMO_AGUDOS = molde_natural.MINIMO_AGUDOS
# Lo más que un sonido puede quedar por debajo del de serie (6 dB) cuando su pico no deja subirlo más.
NIVEL_MINIMO = 0.5
# Fundidos de serie de un sonido que no es bucle, en segundos.
ENTRADA = 0.002
SALIDA = 0.03
# Lo que se retrocede desde el primer ataque para no comerse su arranque.
ANTES_DEL_ATAQUE = 0.003
# El ataque empieza donde la onda pasa de esta parte de su pico.
UMBRAL_ATAQUE = 0.05
# Licencias con las que una grabación puede entrar en un programa GPL que cualquiera descarga.
LICENCIAS_ADMITIDAS = ("CC0 1.0", "Dominio público")
# Bandas (Hz) con las que se compara el timbre de dos pasos o de dos golpes: las mismas de las pruebas.
CORTES_BANDAS = (0, 150, 300, 600, 1200, 2400, 4800, 9600, 22051)


class ErrorMontaje(ValueError):
	"""Una grabación no sirve para el sonido que se le pide, o no está donde se esperaba."""


# ── Tratamiento ──────────────────────────────────────────────────────────────


def buscar_fuentes(indicada: Path | None) -> Path:
	"""La carpeta de los originales: la indicada con ``--fuentes`` o la de la variable de entorno.

	Sin ninguna de las dos se para con un mensaje que dice cómo indicarla, en lugar de
	probar una ruta fija del equipo de alguien.
	"""
	variable = os.environ.get(VARIABLE_FUENTES, "").strip()
	carpeta = indicada or (Path(variable).expanduser() if variable else None)
	if carpeta is None:
		raise ErrorMontaje(
			f"Falta la carpeta de los originales. Indíquela con --fuentes <carpeta con los originales> o con la variable de entorno {VARIABLE_FUENTES}."
		)
	if not carpeta.is_dir():
		raise ErrorMontaje(
			f"No se encuentra la carpeta de los originales en {carpeta}. Indíquela con --fuentes o con la variable {VARIABLE_FUENTES}."
		)
	return carpeta


def buscar_descargadas(indicada: Path | None) -> Path:
	"""La carpeta de lo descargado para el paquete: la indicada, la de la variable de entorno o ``adjuntos/fuentes_sonido``.

	No tiene por qué existir: quien no la tenga monta solo lo que sale de la otra carpeta.
	"""
	return indicada or (Path(os.environ[VARIABLE_DESCARGADAS]) if os.environ.get(VARIABLE_DESCARGADAS) else DESCARGADAS_POR_DEFECTO)


def carpeta_de_coleccion(coleccion: dict, fuentes: Path, descargadas: Path | None) -> Path:
	"""La carpeta donde están los originales de una colección, según de cuál de las dos carpetas de fuentes salga."""
	raiz = coleccion.get("raiz", RAIZ_ORIGINALES)
	if raiz == RAIZ_DESCARGADAS:
		if descargadas is None or not descargadas.is_dir():
			raise ErrorMontaje(
				f"no se encuentra la carpeta de lo descargado ({descargadas}): indíquela con --descargadas o con la variable {VARIABLE_DESCARGADAS}"
			)
		return descargadas / coleccion["carpeta"]
	if raiz != RAIZ_ORIGINALES:
		raise ErrorMontaje(f"la colección dice salir de «{raiz}», que no es ninguna de las dos carpetas de fuentes")
	return fuentes / coleccion["carpeta"]


def _a_canales(datos: np.ndarray, canales: int) -> np.ndarray:
	"""Deja la grabación con los canales del sonido de serie. Una grabación mono no se convierte en un falso estéreo."""
	if canales == 1:
		return np.ascontiguousarray(sintesis.a_mono(datos), dtype=np.float32)
	if datos.ndim == 1:
		raise ErrorMontaje("la grabación es mono y este sonido es un ambiente estéreo")
	return np.ascontiguousarray(datos[:, :2], dtype=np.float32)


def _ataque(datos: np.ndarray, desde: int, alcance: int) -> int:
	"""La muestra donde empieza de verdad el sonido a partir de ``desde``: un poco antes de su primer ataque."""
	tramo = np.abs(datos[desde : desde + alcance])
	if tramo.ndim == 2:
		tramo = tramo.max(axis=1)
	if len(tramo) == 0:
		return desde
	mayor = float(tramo.max())
	if mayor <= 0.0:
		return desde
	primero = int(np.argmax(tramo >= UMBRAL_ATAQUE * mayor))
	return desde + max(0, primero - int(ANTES_DEL_ATAQUE * FRECUENCIA))


def _por_canal(curva: np.ndarray, datos: np.ndarray) -> np.ndarray:
	return curva[:, None] if datos.ndim == 2 else curva


def _fundir(datos: np.ndarray, entrada: float, salida: float) -> np.ndarray:
	"""Fundidos lineales de entrada y de salida: el sonido empieza y acaba exactamente en cero."""
	x = datos.copy()
	a = min(len(x) // 2, max(1, int(entrada * FRECUENCIA)))
	b = min(len(x) // 2, max(1, int(salida * FRECUENCIA)))
	x[:a] *= _por_canal(np.linspace(0.0, 1.0, a, dtype=np.float32), x)
	x[-b:] *= _por_canal(np.linspace(1.0, 0.0, b, dtype=np.float32), x)
	return x


def _cruzar(tramo: np.ndarray, muestras: int, cruce: int) -> np.ndarray:
	"""Bucle de ``muestras`` hecho con ``tramo`` (que trae ``cruce`` muestras de más): el final se funde con el principio.

	Lo que sigue al último instante del bucle se mezcla sobre su principio, de modo que al dar la
	vuelta la onda continúa por donde iba. Si los dos trozos que se mezclan no se parecen (ruido,
	ambiente) se cruzan a potencia constante, para que el volumen no baje en mitad del cruce; si se
	parecen (un zumbido estable), en línea recta, para que no suba.
	"""
	cuerpo = tramo[:muestras].copy()
	cola = tramo[muestras : muestras + cruce]
	cabeza = cuerpo[:cruce]
	a = cabeza.reshape(len(cabeza), -1).mean(axis=1).astype(np.float64)
	b = cola.reshape(len(cola), -1).mean(axis=1).astype(np.float64)
	norma = float(np.sqrt(np.sum(a * a) * np.sum(b * b)))
	parecido = float(np.sum(a * b) / norma) if norma > 0.0 else 0.0
	avance = np.linspace(0.0, 1.0, cruce, dtype=np.float64)
	if parecido > 0.5:
		sube, baja = avance, 1.0 - avance
	else:
		sube, baja = np.sin(avance * np.pi / 2.0), np.cos(avance * np.pi / 2.0)
	cuerpo[:cruce] = cabeza * _por_canal(sube.astype(np.float32), cuerpo) + cola * _por_canal(baja.astype(np.float32), cuerpo)
	return cuerpo


def tratar(datos: np.ndarray, frecuencia: int, receta: dict, canales: int, bucle: bool, duracion_serie: float) -> tuple[np.ndarray, dict]:
	"""Convierte una grabación en el sonido del paquete. Devuelve ``(muestras, lo que se hizo)``.

	``lo que se hizo`` lleva el tramo exacto que se tomó (inicio y duración en segundos del original
	ya remuestreado) y los fundidos, para apuntarlo en ``receta.json``. Lanza ``ErrorMontaje`` si la
	grabación no da para lo que se pide.
	"""
	x = _a_canales(np.asarray(datos, dtype=np.float32), canales)
	if int(frecuencia) != FRECUENCIA:
		x = sintesis.remuestrear(x, int(frecuencia), FRECUENCIA)
	duracion = float(receta.get("duracion") or duracion_serie)
	muestras = int(round(duracion * FRECUENCIA))
	inicio = int(round(float(receta.get("inicio", 0.0)) * FRECUENCIA))
	if inicio >= len(x):
		raise ErrorMontaje(f"el tramo empieza en el segundo {inicio / FRECUENCIA:.2f} y la grabación dura {len(x) / FRECUENCIA:.2f} s")
	hecho: dict = {"remuestreado_de": int(frecuencia), "canales_del_original": 1 if np.ndim(datos) == 1 else int(np.shape(datos)[1])}
	if bucle:
		cruce = int(round(float(receta.get("cruce") or min(0.5, duracion / 4.0)) * FRECUENCIA))
		tramo = x[inicio : inicio + muestras + cruce]
		if len(tramo) < muestras + cruce:
			raise ErrorMontaje(
				f"la grabación no da para un bucle de {duracion:.2f} s con {cruce / FRECUENCIA:.2f} s de cruce desde el segundo {inicio / FRECUENCIA:.2f}"
			)
		# Sin componente continua, que en un bucle se nota como un escalón al empezar a sonar.
		tramo = tramo - tramo.mean(axis=0, dtype=np.float64).astype(np.float32)
		resultado = _cruzar(tramo, muestras, cruce)
		hecho.update(inicio=round(inicio / FRECUENCIA, 4), duracion=round(muestras / FRECUENCIA, 4), cruce=round(cruce / FRECUENCIA, 4))
	else:
		if receta.get("ataque", True):
			inicio = _ataque(x, inicio, muestras + int(0.5 * FRECUENCIA))
		tramo = x[inicio : inicio + muestras]
		if len(tramo) < 64:
			raise ErrorMontaje("no queda sonido en el tramo pedido")
		tramo = tramo - tramo.mean(axis=0, dtype=np.float64).astype(np.float32)
		entrada = float(receta.get("entrada") or ENTRADA)
		salida = float(receta.get("salida") or min(SALIDA, len(tramo) / FRECUENCIA / 4.0))
		resultado = _fundir(tramo, entrada, salida)
		hecho.update(
			inicio=round(inicio / FRECUENCIA, 4),
			duracion=round(len(tramo) / FRECUENCIA, 4),
			entrada=round(entrada, 4),
			salida=round(salida, 4),
		)
	return np.ascontiguousarray(resultado, dtype=np.float32), hecho


def igualar(datos: np.ndarray, referencia: float | None) -> tuple[np.ndarray, float]:
	"""Lleva el sonido al nivel del de serie sin pasar del pico prudente. Devuelve ``(muestras, ganancia aplicada)``.

	Muchas grabaciones vienen muy bajas (un parque a lo lejos tiene un pico de 0,03) y el igualado de
	``niveles`` no sube más de 20 dB: primero se lleva el pico al techo y después se iguala, que ya
	solo puede bajar.
	"""
	pico = niveles.pico(datos)
	if pico < niveles.SILENCIO:
		return datos, 1.0
	ganancia = TECHO_PICO / pico
	normalizado = (datos * np.float32(ganancia)).astype(np.float32)
	if referencia is None:
		return normalizado, float(ganancia)
	ganancia *= niveles.ganancia_para_igualar(normalizado, referencia, FRECUENCIA, techo=TECHO_PICO)
	return niveles.igualar(normalizado, referencia, FRECUENCIA, techo=TECHO_PICO), float(ganancia)


# ── Separación entre suelos y entre materiales ───────────────────────────────


def bandas(datos: np.ndarray) -> np.ndarray:
	"""Reparto de la energía de un sonido en ocho bandas, en decibelios respecto del total (la misma medida de las pruebas)."""
	x = sintesis.a_mono(np.asarray(datos, dtype=np.float32))
	largo = max(8192, len(x))
	energia = np.abs(np.fft.rfft(x, largo)) ** 2
	frecuencias = np.fft.rfftfreq(largo, 1.0 / FRECUENCIA)
	partes = (
		np.array(
			[energia[(frecuencias >= a) & (frecuencias < b)].sum() for a, b in zip(CORTES_BANDAS[:-1], CORTES_BANDAS[1:], strict=True)]
		)
		+ 1e-12
	)
	return np.clip(10.0 * np.log10(partes / partes.sum()), -40.0, 0.0)


def separacion(sonidos: dict[str, np.ndarray], suelos: tuple[str, ...] | None = None, materiales: tuple[str, ...] | None = None) -> dict:
	"""Cuánto se distinguen los pasos de un suelo de los de otro, y los golpes de un material de los de otro.

	Es la medida con la que se examinó el paquete «Natural»: cada sonido es su perfil de ocho bandas.
	De los pasos se da la variación **dentro** de un mismo suelo (lo que cambian sus seis variantes)
	y la distancia **entre** las medias de dos suelos; se distinguen si la segunda supera a la
	primera. ``margen`` es la menor distancia entre dos suelos dividida por la variación de dentro:
	cuanto mayor, mejor. De los golpes y los roces, la menor distancia entre dos materiales.
	Solo cuentan los suelos con sus seis variantes y los materiales presentes (o los que se indiquen).
	"""
	perfiles: dict[str, np.ndarray] = {}
	for suelo in suelos or sintesis.SUELOS:
		nombres = [f"pasos/{suelo}_{pie}_{variante}" for pie in sintesis.PIES for variante in range(1, sintesis.VARIANTES_PASO + 1)]
		if all(nombre in sonidos for nombre in nombres):
			perfiles[suelo] = np.array([bandas(sonidos[nombre]) for nombre in nombres])
	resultado: dict = {"suelos": sorted(perfiles)}
	if len(perfiles) >= 2:
		dentro = float(np.mean([perfil.std(axis=0).mean() for perfil in perfiles.values()]))
		pares = {}
		claves = sorted(perfiles)
		for i, uno in enumerate(claves):
			for otro in claves[i + 1 :]:
				pares[f"{uno}-{otro}"] = float(np.abs(perfiles[uno].mean(axis=0) - perfiles[otro].mean(axis=0)).mean())
		peor = min(pares, key=pares.get)
		resultado["pasos"] = {
			"dentro_db": round(dentro, 2),
			"entre_minima_db": round(pares[peor], 2),
			"entre_media_db": round(float(np.mean(list(pares.values()))), 2),
			"par_mas_parecido": peor,
			"margen": round(pares[peor] / dentro, 2) if dentro > 0.0 else None,
		}
	for familia in ("golpe", "roce"):
		presentes = {
			material: bandas(sonidos[f"{familia}/{material}"])
			for material in (materiales or sintesis.MATERIALES)
			if f"{familia}/{material}" in sonidos
		}
		pares = {}
		claves = sorted(presentes)
		for i, uno in enumerate(claves):
			for otro in claves[i + 1 :]:
				pares[f"{uno}-{otro}"] = float(np.abs(presentes[uno] - presentes[otro]).mean())
		if pares:
			peor = min(pares, key=pares.get)
			resultado[familia] = {
				"materiales": claves,
				"entre_minima_db": round(pares[peor], 2),
				"entre_media_db": round(float(np.mean(list(pares.values()))), 2),
				"par_mas_parecido": peor,
			}
	return resultado


def leer_paquete(carpeta: Path) -> dict[str, np.ndarray]:
	"""Los sonidos del catálogo que hay en la carpeta de un paquete: nombre → muestras."""
	leidos: dict[str, np.ndarray] = {}
	for nombre in sintesis.nombres():
		ruta = sintesis.fichero_de(carpeta, nombre)
		if ruta is not None:
			leidos[nombre] = sintesis.leer_audio(ruta)[0]
	return leidos


def comparar_separacion(carpeta_sonidos: Path, identificador: str) -> dict:
	"""La separación del paquete ``identificador`` y, con sus mismos suelos y materiales, la de los demás paquetes instalados."""
	propio = leer_paquete(carpeta_sonidos / identificador)
	medida = separacion(propio)
	suelos = tuple(medida.get("suelos", ()))
	golpes = tuple(medida.get("golpe", {}).get("materiales", ()))
	comparacion: dict = {identificador: medida}
	for otro in sorted(
		ruta.name for ruta in carpeta_sonidos.iterdir() if ruta.is_dir() and ruta.name != identificador and (ruta / NOMBRE_FICHA).is_file()
	):
		sonidos = leer_paquete(carpeta_sonidos / otro)
		comparacion[otro] = {
			"mismos_suelos_y_materiales": separacion(sonidos, suelos or None, golpes or None),
			"todo_lo_suyo": separacion(sonidos),
		}
	return comparacion


# ── Textos del paquete ───────────────────────────────────────────────────────


def _segundos(valor: float) -> str:
	return f"{valor:.2f}".replace(".", ",")


def linea_credito(nombre: str, entrada: dict) -> str:
	"""La línea de ``CREDITOS.txt`` de un sonido: fichero original, colección, autor, licencia, origen y tramo."""
	titulo = f"«{entrada['titulo']}», " if entrada.get("titulo") else ""
	tramo = (
		f"del segundo {_segundos(entrada['inicio'])} al {_segundos(entrada['inicio'] + entrada['duracion'] + entrada.get('cruce', 0.0))}"
	)
	como = f"bucle con {_segundos(entrada['cruce'])} s de fundido cruzado" if "cruce" in entrada else "con fundidos de entrada y de salida"
	return (
		f"  {nombre}: {entrada['fichero']}, {titulo}de la colección «{entrada['coleccion_nombre']}». Autor: {entrada['autor']}. "
		f"Licencia: {entrada['licencia']}. Origen: {entrada['origen']}. Tramo: {tramo}, {como}."
	)


def _creditos(ficha: dict, receta: dict, total: int, orden: str) -> str:
	sonidos: dict[str, dict] = receta["sonidos"]
	colecciones: dict[str, dict] = receta["colecciones"]
	usadas = {clave: sum(1 for entrada in sonidos.values() if entrada["coleccion"] == clave) for clave in colecciones}
	lineas = [
		f"PAQUETE DE SONIDOS «{str(ficha.get('nombre', '')).upper()}» DE ENTORNOLAB",
		"",
		str(ficha.get("descripcion", "")),
		"",
		f"Trae {len(sonidos)} de los {total} sonidos del catálogo. Lo que no trae suena con el paquete por defecto.",
		"",
		"CÓMO SE HIZO",
		"  Con grabaciones de colecciones de sonidos libres, recortadas y niveladas con tools/montar_paquete_grabado.py",
		"  a partir de la tabla de tools/receta_grabado.py. A cada grabación solo se le ha hecho esto: paso a mono",
		"  (los ambientes siguen en estéreo), remuestreo a 44,1 kHz, recorte del tramo que se indica, fundidos de",
		"  entrada y de salida (o fundido cruzado, en los bucles) y una ganancia para igualarla al sonido de serie",
		"  del mismo nombre. No se ha filtrado, ecualizado ni mezclado nada, y no se ha usado inteligencia artificial.",
		"  Los ficheros originales no viajan con el programa: aquí solo están los FLAC ya recortados.",
		"  El tramo exacto de cada uno está en receta.json y lo que se midió, en medidas.json. Para rehacerlo:",
		f"      {orden}",
		"",
		"LICENCIAS",
		"  Todas las grabaciones de este paquete están dedicadas al dominio público con Creative Commons Zero",
		"  (CC0 1.0 Universal): https://creativecommons.org/publicdomain/zero/1.0/deed.es",
		"  CC0 permite copiar, modificar y redistribuir la obra, también con fines comerciales, sin pedir permiso y",
		"  sin obligación de citar al autor. Aun así, aquí se cita a cada uno: es de justicia y permite comprobarlo.",
		"  Los recortes de este paquete se publican con la misma dedicación (CC0 1.0); el resto del programa, con la suya.",
		"  En «Constancia» se dice dónde figura la licencia de cada colección. Las marcadas como «anotada por el autor",
		"  de EntornoLab» no traen fichero de licencia propio: conviene volver a comprobar su página antes de publicar.",
		"  Las grabaciones de Freesound descargadas para este paquete son las vistas previas de alta calidad (OGG): en la",
		"  página de cada una, que va en su línea, figura «Creative Commons 0». No hay ninguna con licencia CC BY, así que",
		"  no hace falta texto de atribución obligatorio; si alguna vez se añade, su línea llevará la atribución exacta.",
		"",
		"COLECCIONES USADAS",
	]
	for clave, coleccion in colecciones.items():
		if not usadas.get(clave):
			continue
		cuantos = "1 sonido" if usadas[clave] == 1 else f"{usadas[clave]} sonidos"
		lineas.append(f"  «{coleccion['nombre']}». Autor: {coleccion['autor']}. Licencia: {coleccion['licencia']}. {cuantos}.")
		lineas.append(f"      Origen: {coleccion['origen']}")
		lineas.append(f"      Constancia: {coleccion['constancia']}")
	lineas += ["", "QUÉ SONIDO SALE DE DÓNDE"]
	for nombre, entrada in sonidos.items():
		lineas.append(linea_credito(nombre, entrada))
		if entrada.get("nota"):
			lineas.append(f"      Nota: {entrada['nota']}")
	lineas += [
		"",
		"SONIDOS QUE CODIFICAN INFORMACIÓN Y SE DEJAN A PROPÓSITO CON EL PAQUETE POR DEFECTO",
		"  Una grabación no conserva su código (número de toques, orden de las notas, ritmo), así que no se sustituyen.",
	]
	for nombre, motivo in receta["funcionales"].items():
		lineas.append(f"  {nombre}: {motivo}")
	lineas += ["", "SONIDOS PARA LOS QUE NO HABÍA UNA GRABACIÓN VÁLIDA (suenan con el paquete por defecto) Y QUÉ HABRÍA QUE BUSCAR"]
	for nombre, pendiente in receta["pendientes"].items():
		lineas.append(f"  {nombre}: {pendiente['motivo']}")
		lineas.append(f"      Buscar: {pendiente['buscar']}")
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
	analizador = argparse.ArgumentParser(description="Monta un paquete de sonidos de EntornoLab con grabaciones reales de uso libre.")
	analizador.add_argument(
		"--fuentes",
		type=Path,
		default=None,
		help=f"carpeta con los originales descargados (por defecto, la de la variable de entorno {VARIABLE_FUENTES}; una de las dos es obligatoria)",
	)
	analizador.add_argument(
		"--descargadas",
		type=Path,
		default=None,
		help=f"carpeta con lo descargado para el paquete (por defecto, la variable {VARIABLE_DESCARGADAS} o {DESCARGADAS_POR_DEFECTO})",
	)
	analizador.add_argument("--receta", default=RECETA_POR_DEFECTO, help="módulo de tools con la tabla (por defecto, receta_grabado)")
	analizador.add_argument(
		"--carpeta", type=Path, default=None, help="carpeta de sonidos de destino (por defecto, data/sounds del programa)"
	)
	analizador.add_argument(
		"--solo", default=None, help="patrón de nombres que montar, por ejemplo «pasos/*» (el resto del paquete no se toca)"
	)
	analizador.add_argument(
		"--comparar",
		action="store_true",
		help="no montar nada: solo medir la separación entre suelos y materiales de los paquetes instalados",
	)
	return analizador.parse_args(argv)


def forma_de_serie(paquete: Path, nombres: list[str]) -> dict[str, tuple[int, float]]:
	"""(canales, duración) de cada sonido pedido en el paquete por defecto: el molde del sonido nuevo.

	Si el fichero de serie no está, se mide el sonido sintetizado, que es lo que sonaría en su lugar.
	"""
	import soundfile

	molde: dict[str, tuple[int, float]] = {}
	for nombre in nombres:
		ruta = sintesis.fichero_de(paquete, nombre)
		if ruta is not None:
			info = soundfile.info(str(ruta))
			molde[nombre] = (int(info.channels), info.frames / float(info.samplerate))
		else:
			datos = sintesis.generar(nombre)
			molde[nombre] = (1 if datos.ndim == 1 else int(datos.shape[1]), len(datos) / float(FRECUENCIA))
	return molde


def montar_sonido(
	nombre: str,
	receta: dict,
	coleccion: dict,
	fuentes: Path,
	canales: int,
	duracion_serie: float,
	referencia: float | None,
	descargadas: Path | None = None,
) -> tuple[np.ndarray, dict, list[str]]:
	"""Lee el original de ``nombre``, lo trata, lo iguala y lo comprueba. Devuelve ``(muestras, lo que se hizo, problemas)``."""
	definicion = sintesis.CATALOGO[nombre]
	carpeta = carpeta_de_coleccion(coleccion, fuentes, descargadas)
	ruta = carpeta / receta["fichero"]
	if carpeta.resolve() not in ruta.resolve().parents:
		raise ErrorMontaje(f"el original {receta['fichero']} se sale de la carpeta de su colección")
	if not ruta.is_file():
		raise ErrorMontaje(f"no se encuentra el original {coleccion['carpeta']}/{receta['fichero']}")
	try:
		datos, frecuencia = sintesis.leer_audio(ruta)
	except (OSError, ValueError) as error:
		raise ErrorMontaje(f"no se pudo leer el original: {error}") from error
	tratado, hecho = tratar(datos, frecuencia, receta, canales, definicion.bucle, duracion_serie)
	tratado, ganancia = igualar(tratado, referencia)
	hecho["ganancia"] = round(ganancia, 4)
	objetivo = duracion_serie if definicion.bucle else len(tratado) / float(FRECUENCIA)
	problemas = molde_natural.comprobar(nombre, tratado, FRECUENCIA, {}, definicion, canales, duracion_serie, objetivo)
	if referencia and niveles.nivel(tratado, FRECUENCIA) < NIVEL_MINIMO * referencia:
		# Una grabación muy picuda (unas monedas) no se puede subir hasta el nivel de serie sin recortarla: se oiría mucho menos que las demás.
		decibelios = 20.0 * float(np.log10(max(niveles.nivel(tratado, FRECUENCIA), niveles.SILENCIO) / referencia))
		problemas.append(f"queda {-decibelios:.1f} dB por debajo del sonido de serie y no se puede subir más sin recortar sus picos")
	return tratado, hecho, problemas


def montar(argumentos: argparse.Namespace) -> int:
	"""Hace el paquete. Devuelve el código de salida del proceso."""
	carpeta = (argumentos.carpeta or molde_natural.carpeta_de_serie()).resolve()
	modulo = importlib.import_module(argumentos.receta)
	identificador = str(modulo.ID)
	if argumentos.comparar:
		log.info("%s", json.dumps(comparar_separacion(carpeta, identificador), ensure_ascii=False, indent="\t"))
		return 0
	fuentes = buscar_fuentes(argumentos.fuentes)
	descargadas = buscar_descargadas(getattr(argumentos, "descargadas", None))
	ficha = dict(modulo.FICHA)
	colecciones: dict[str, dict] = modulo.COLECCIONES
	recetas: dict[str, dict] = modulo.recetas()
	catalogo = sintesis.nombres()
	desconocidos = sorted((set(recetas) | set(modulo.FUNCIONALES) | set(modulo.pendientes())) - set(catalogo))
	if desconocidos:
		raise ErrorMontaje(f"La receta nombra sonidos que no están en el catálogo: {', '.join(desconocidos)}")
	for clave, coleccion in colecciones.items():
		if coleccion["licencia"] not in LICENCIAS_ADMITIDAS:
			raise ErrorMontaje(f"La colección «{clave}» tiene una licencia que no se admite: {coleccion['licencia']}")
	referencias = niveles.leer_niveles(carpeta / PAQUETE_POR_DEFECTO)
	elegidos = [
		nombre for nombre in catalogo if nombre in recetas and (not argumentos.solo or fnmatch.fnmatchcase(nombre, argumentos.solo))
	]
	if not elegidos:
		log.error("No hay ningún sonido que montar (patrón «%s»).", argumentos.solo)
		return 1
	molde = forma_de_serie(carpeta / PAQUETE_POR_DEFECTO, elegidos)
	destino = carpeta / identificador
	inicio = time.perf_counter()
	log.info("Originales: %s", fuentes)
	log.info("Descargadas: %s%s", descargadas, "" if descargadas.is_dir() else " (no está: lo que salga de ahí no entra)")

	medidas: dict[str, dict] = {}
	apuntes: dict[str, dict] = {}
	descartados: dict[str, str] = {}
	escritos = 0
	for nombre in elegidos:
		for extension in sintesis.FORMATOS_AUDIO:
			(destino / f"{nombre}{extension}").unlink(missing_ok=True)
		receta = recetas[nombre]
		coleccion = colecciones[receta["coleccion"]]
		canales, duracion_serie = molde[nombre]
		referencia = referencias.get(nombre)
		try:
			datos, hecho, problemas = montar_sonido(
				nombre, receta, coleccion, fuentes, canales, duracion_serie, referencia[0] if referencia else None, descargadas
			)
		except ErrorMontaje as error:
			descartados[nombre] = str(error)
			medidas[nombre] = {"en_el_paquete": False, "motivo": str(error)}
			continue
		ficha_medida = niveles.medir(datos, FRECUENCIA)
		ficha_medida["duracion_serie"] = round(duracion_serie, 3)
		ficha_medida["nivel_serie"] = round(referencia[0], 5) if referencia else None
		ficha_medida["en_el_paquete"] = not problemas
		if problemas:
			ficha_medida["motivo"] = "; ".join(problemas)
			descartados[nombre] = "; ".join(problemas)
		else:
			sintesis.escribir_audio(destino / f"{nombre}.flac", datos, FRECUENCIA)
			escritos += 1
			apuntes[nombre] = {
				"coleccion": receta["coleccion"],
				"coleccion_nombre": coleccion["nombre"],
				"fichero": receta["fichero"],
				**({"titulo": receta["titulo"]} if receta.get("titulo") else {}),
				"autor": receta.get("autor") or coleccion["autor"],
				"licencia": coleccion["licencia"],
				"origen": receta.get("origen") or coleccion["origen"],
				"canales": canales,
				"bucle": sintesis.CATALOGO[nombre].bucle,
				**hecho,
				**({"nota": receta["nota"]} if receta.get("nota") else {}),
			}
		medidas[nombre] = ficha_medida

	# Con --solo se conserva lo ya apuntado de los demás sonidos.
	anteriores: dict[str, dict] = {"medidas": {}, "receta": {}}
	if argumentos.solo:
		for clave, ruta in (("medidas", destino / "medidas.json"), ("receta", destino / "receta.json")):
			if ruta.is_file():
				try:
					anteriores[clave] = json.loads(ruta.read_text(encoding="utf-8")).get("sonidos", {})
				except OSError, ValueError:
					log.warning("No se pudo leer %s; se reescribe solo con lo de ahora.", ruta, exc_info=True)
	todas_medidas = {**anteriores["medidas"], **medidas}
	todos_apuntes = {nombre: entrada for nombre, entrada in anteriores["receta"].items() if nombre not in elegidos}
	todos_apuntes.update(apuntes)
	# Una subcarpeta que se ha quedado sin sonidos (todo lo suyo se descartó) no debe viajar vacía.
	for subcarpeta in sorted(ruta for ruta in destino.iterdir() if ruta.is_dir()):
		if not any(subcarpeta.iterdir()):
			subcarpeta.rmdir()
	presentes = [nombre for nombre in catalogo if sintesis.fichero_de(destino, nombre) is not None]
	todos_apuntes = {nombre: todos_apuntes[nombre] for nombre in presentes if nombre in todos_apuntes}
	sin_apunte = sorted(set(presentes) - set(todos_apuntes))
	if sin_apunte:
		raise ErrorMontaje(f"Hay sonidos en {destino} que no vienen de la receta (bórrelos o móntelo entero): {', '.join(sin_apunte)}")

	funcionales = {nombre: motivo for nombre, motivo in modulo.FUNCIONALES.items() if nombre not in presentes}
	pendientes = {nombre: dict(dato) for nombre, dato in modulo.pendientes().items() if nombre not in presentes}
	for nombre in catalogo:
		if nombre in presentes or nombre in funcionales or nombre in pendientes:
			continue
		motivo = str(todas_medidas.get(nombre, {}).get("motivo") or descartados.get(nombre) or "no está en la receta")
		recetado = recetas.get(nombre, {})
		pendientes[nombre] = {
			"motivo": f"la grabación elegida ({recetado.get('fichero', 'ninguna')}) no pasó las medidas: {motivo}",
			"buscar": modulo.que_buscar(nombre),
		}
	pendientes = {nombre: pendientes[nombre] for nombre in catalogo if nombre in pendientes}
	funcionales = {nombre: funcionales[nombre] for nombre in catalogo if nombre in funcionales}

	orden = ".venv\\Scripts\\python.exe tools\\montar_paquete_grabado.py --fuentes <carpeta con los originales> --descargadas <carpeta con lo descargado>"
	ficha["generado"] = (
		"Grabaciones de colecciones CC0 recortadas, pasadas a 44,1 kHz e igualadas al paquete por defecto con tools/montar_paquete_grabado.py. "
		"Tabla en tools/receta_grabado.py; tramo exacto de cada sonido en receta.json; origen y licencia de cada uno en CREDITOS.txt."
	)
	ficha["sonidos"] = len(presentes)
	ficha["heredados"] = sorted(set(catalogo) - set(presentes))
	receta_final = {
		"formato": FORMATO_RECETA,
		"explicacion": (
			"De qué grabación sale cada sonido y qué se le hizo: fichero original (relativo a la carpeta de su colección dentro de la carpeta de los "
			"originales), tramo tomado (inicio y duración en segundos, ya a 44,1 kHz), fundidos o fundido cruzado y ganancia. Los originales no viajan."
		),
		"ficha": {clave: valor for clave, valor in ficha.items() if clave not in ("sonidos", "heredados", "generado")},
		"colecciones": {
			clave: colecciones[clave] for clave in colecciones if any(entrada["coleccion"] == clave for entrada in todos_apuntes.values())
		},
		"sonidos": todos_apuntes,
		"funcionales": funcionales,
		"pendientes": pendientes,
	}
	_escribir_texto(destino / NOMBRE_FICHA, json.dumps(ficha, ensure_ascii=False, indent="\t") + "\n")
	_escribir_texto(destino / "CREDITOS.txt", _creditos(ficha, receta_final, len(catalogo), orden))
	_escribir_texto(destino / "receta.json", json.dumps(receta_final, ensure_ascii=False, indent="\t") + "\n")
	medidas_final = {
		"formato": 1,
		"explicacion": (
			"Lo medido de cada sonido tras igualarlo: duración (s), canales, pico, nivel (media cuadrática del tramo de 0,3 s más fuerte), rms, "
			"agudos (parte de la energía por encima de 3 kHz), centroide del espectro (Hz) y costura (salto del bucle respecto de lo normal). "
			"En «separacion», cuánto se distinguen los suelos y los materiales (perfil de ocho bandas, en dB), aquí y en los otros paquetes."
		),
		"separacion": comparar_separacion(carpeta, identificador),
		"sonidos": {nombre: todas_medidas[nombre] for nombre in catalogo if nombre in todas_medidas},
	}
	_escribir_texto(destino / "medidas.json", json.dumps(medidas_final, ensure_ascii=False, indent="\t") + "\n")

	log.info(
		"%s sonidos escritos en %s en %.0f s. El paquete tiene %s de %s.",
		escritos,
		destino,
		time.perf_counter() - inicio,
		len(presentes),
		len(catalogo),
	)
	log.info("Se heredan %s por codificar información y %s por no tener grabación válida.", len(funcionales), len(pendientes))
	for nombre, motivo in descartados.items():
		log.warning("NO entra en el paquete (se hereda del de por defecto): %s: %s", nombre, motivo)
	return 0 if escritos else 1


def main(argv: list[str] | None = None) -> int:
	"""Punto de entrada. Devuelve el código de salida del proceso."""
	logging.basicConfig(level=logging.INFO, format="%(message)s")
	try:
		return montar(_argumentos(argv))
	except ErrorMontaje as error:
		log.error("%s", error)
		return 1
	except OSError, KeyError:
		log.exception("No se pudo montar el paquete de sonidos.")
		return 1


if __name__ == "__main__":
	sys.exit(main())
