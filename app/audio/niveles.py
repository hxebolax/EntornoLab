"""Medidas de un sonido y igualado de sonoridad entre paquetes de sonido.

Cada paquete de sonidos viene «a su volumen»: unas grabaciones suenan más fuertes que otras. Para
que al cambiar de paquete no suba ni baje el volumen general, ni un paso tape a una baliza, cada
sonido de un paquete se lleva al nivel del sonido del mismo nombre del paquete por defecto. Es la
misma idea que ``packs.py`` de Puerto Bravo, del mismo autor:

- **Nivel** de un sonido: la media cuadrática de su tramo de 0,3 segundos más intenso. Medir solo
  el tramo más fuerte hace que un golpe con mucha cola, o una grabación con silencio alrededor, no
  salgan perjudicados frente a un sonido compacto.
- **Referencia**: nivel y pico de cada sonido del paquete por defecto, guardados en
  ``data/sounds/por_defecto/niveles.json`` (los escribe ``tools/sintetizar_sonidos.py``).
- **Igualar**: multiplicar por ``referencia / nivel``, sin dejar que el pico pase de un techo
  prudente (nadie debe llevarse un susto con auriculares).

Aquí están también las medidas con las que se vigila que un paquete sirve para orientarse (costura
de los bucles, centro del espectro), que usan ``tools/generar_paquete_sonidos.py`` y las pruebas.
Este módulo solo usa numpy.
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

import numpy as np

log = logging.getLogger(__name__)

FRECUENCIA = 44100
# Tramo sobre el que se mide el nivel, en segundos.
VENTANA_NIVEL = 0.3
# Pico máximo que puede dejar el igualado: por encima recortaría, y un pico a tope asusta.
TECHO_PICO = 0.9
# Por debajo de esto un sonido se considera silencio y no se toca.
SILENCIO = 1e-6
# Lo más que el igualado sube o baja un sonido (20 dB): más que eso es un fichero estropeado.
GANANCIA_MINIMA = 0.1
GANANCIA_MAXIMA = 10.0
# Lo que el usuario puede subir o bajar un sonido concreto desde las preferencias.
AJUSTE_MINIMO = 0.3
AJUSTE_MAXIMO = 2.0
NOMBRE_NIVELES = "niveles.json"
FORMATO_NIVELES = 1


def _mono(datos: np.ndarray) -> np.ndarray:
	x = np.asarray(datos, dtype=np.float64)
	return x.mean(axis=1) if x.ndim == 2 else x


def nivel(datos: np.ndarray, frecuencia: int = FRECUENCIA) -> float:
	"""Lo fuerte que suena: media cuadrática del tramo de 0,3 s más intenso (del sonido entero si es más corto)."""
	x = _mono(datos)
	n = len(x)
	if n == 0:
		return 0.0
	ventana = max(1, int(VENTANA_NIVEL * frecuencia))
	if n <= ventana:
		return float(np.sqrt(np.mean(x * x)))
	acumulado = np.concatenate(([0.0], np.cumsum(x * x)))
	salto = max(1, ventana // 4)
	sumas = acumulado[ventana::salto] - acumulado[:-ventana:salto]
	return float(np.sqrt(max(0.0, float(sumas.max())) / ventana))


def pico(datos: np.ndarray) -> float:
	"""El valor absoluto más alto del sonido (0 si está vacío)."""
	return float(np.max(np.abs(datos))) if len(datos) else 0.0


def ganancia_para_igualar(datos: np.ndarray, referencia: float, frecuencia: int = FRECUENCIA, techo: float = TECHO_PICO) -> float:
	"""Por cuánto hay que multiplicar ``datos`` para que suene al nivel ``referencia`` sin pasar del techo."""
	actual = nivel(datos, frecuencia)
	if actual < SILENCIO or referencia < SILENCIO:
		return 1.0
	ganancia = min(GANANCIA_MAXIMA, max(GANANCIA_MINIMA, referencia / actual))
	maximo = pico(datos) * ganancia
	if maximo > techo:
		ganancia *= techo / maximo
	return float(ganancia)


def igualar(datos: np.ndarray, referencia: float, frecuencia: int = FRECUENCIA, techo: float = TECHO_PICO) -> np.ndarray:
	"""``datos`` llevado al nivel de referencia (float32), sin dejar que sature."""
	ganancia = ganancia_para_igualar(datos, referencia, frecuencia, techo)
	if abs(ganancia - 1.0) < 1e-4:
		return np.ascontiguousarray(datos, dtype=np.float32)
	return np.ascontiguousarray(np.asarray(datos, dtype=np.float32) * np.float32(ganancia))


def ajuste_valido(valor: object) -> float:
	"""El ajuste de volumen de un sonido que de verdad se aplica: 1 si lo guardado no es un número, y siempre dentro de sus límites."""
	if isinstance(valor, bool) or not isinstance(valor, (int, float)):
		return 1.0
	if valor != valor:  # NaN
		return 1.0
	return max(AJUSTE_MINIMO, min(AJUSTE_MAXIMO, float(valor)))


# ── Medidas para comprobar un paquete ────────────────────────────────────────


def costura(datos: np.ndarray) -> float:
	"""Cuánto salta la onda al repetirse un bucle, comparado con sus propios saltos entre muestras.

	Es el salto entre la última muestra y la primera dividido por un salto «grande pero normal»
	dentro del sonido (su percentil 99,9). Hasta 1 es una costura que no se distingue del resto de la
	onda; bastante por encima de 1 se oye un clic en cada vuelta.
	"""
	x = _mono(datos)
	if len(x) < 16:
		return 0.0
	saltos = np.abs(np.diff(x))
	normal = float(np.percentile(saltos, 99.9))
	if normal < 1e-9:
		return 0.0
	return float(abs(x[0] - x[-1]) / normal)


def centroide(datos: np.ndarray, frecuencia: int = FRECUENCIA) -> float:
	"""Centro de gravedad del espectro, en hercios: lo «brillante» que es un sonido."""
	x = _mono(datos)
	if len(x) < 8:
		return 0.0
	energia = np.abs(np.fft.rfft(x)) ** 2
	total = float(energia.sum())
	if total <= 0.0:
		return 0.0
	frecuencias = np.fft.rfftfreq(len(x), 1.0 / frecuencia)
	return float((energia * frecuencias).sum() / total)


def duracion_util(datos: np.ndarray, frecuencia: int = FRECUENCIA, parte: float = 0.99) -> float:
	"""Segundos en los que está el 99 % de la energía: lo que dura el sonido «de verdad», sin su cola."""
	x = _mono(datos)
	if len(x) == 0:
		return 0.0
	acumulada = np.cumsum(x * x)
	if acumulada[-1] <= 0.0:
		return 0.0
	return float(np.searchsorted(acumulada, parte * acumulada[-1]) + 1) / frecuencia


def pico_espectral(datos: np.ndarray, frecuencia: int = FRECUENCIA, minimo: float = 80.0, maximo: float = 8000.0) -> float:
	"""La frecuencia con más energía entre ``minimo`` y ``maximo`` hercios: la nota de un sonido tonal."""
	x = _mono(datos)
	if len(x) < 64:
		return 0.0
	# Con relleno de ceros la rejilla de frecuencias es más fina que la nota más corta.
	largo = max(len(x), frecuencia)
	espectro = np.abs(np.fft.rfft(x * np.hanning(len(x)), largo))
	frecuencias = np.fft.rfftfreq(largo, 1.0 / frecuencia)
	dentro = (frecuencias >= minimo) & (frecuencias <= maximo)
	if not dentro.any():
		return 0.0
	return float(frecuencias[dentro][int(np.argmax(espectro[dentro]))])


def energia_en(datos: np.ndarray, hercios: float, frecuencia: int = FRECUENCIA, margen: float = 0.03) -> float:
	"""Parte de la energía del sonido (0 a 1) que está a menos de un ``margen`` relativo de ``hercios``."""
	x = _mono(datos)
	if len(x) < 64:
		return 0.0
	largo = max(len(x), frecuencia)
	energia = np.abs(np.fft.rfft(x * np.hanning(len(x)), largo)) ** 2
	total = float(energia.sum())
	if total <= 0.0:
		return 0.0
	frecuencias = np.fft.rfftfreq(largo, 1.0 / frecuencia)
	banda = (frecuencias >= hercios * (1.0 - margen)) & (frecuencias <= hercios * (1.0 + margen))
	return float(energia[banda].sum()) / total


def golpes(datos: np.ndarray, frecuencia: int = FRECUENCIA, separacion: float = 0.045, umbral: float = 0.3) -> int:
	"""Cuántos ataques tiene el sonido: las veces que su energía sube de golpe.

	Sirve para comprobar que un aviso que cuenta («tres pitidos: cerca») sigue contando lo mismo. Se
	mira la subida de la envolvente (ventana de 4 ms) de un momento al siguiente; cuenta cada subida
	que llegue al ``umbral`` de la mayor, separadas al menos ``separacion`` segundos.
	"""
	x = _mono(datos)
	ventana = max(1, int(0.004 * frecuencia))
	if len(x) < ventana * 4:
		return 0
	cuadrado = np.concatenate(([0.0], np.cumsum(x * x)))
	envolvente = np.sqrt((cuadrado[ventana:] - cuadrado[:-ventana]) / ventana)
	# Subida respecto de lo que había 8 ms antes; el principio cuenta como subida desde el silencio.
	atras = 2 * ventana
	previo = np.concatenate((np.zeros(atras), envolvente[:-atras]))
	subida = np.maximum(0.0, envolvente - previo)
	mayor = float(subida.max())
	if mayor <= 0.0:
		return 0
	cuenta = 0
	ultimo = -(10**9)
	hueco = int(separacion * frecuencia)
	candidatos = np.flatnonzero(subida >= umbral * mayor)
	for indice in candidatos:
		if indice - ultimo >= hueco:
			cuenta += 1
		ultimo = int(indice)
	return cuenta


def medir(datos: np.ndarray, frecuencia: int = FRECUENCIA) -> dict:
	"""Ficha de medidas de un sonido, para informes y para ``medidas.json`` de un paquete."""
	from app.audio import sintesis

	x = np.asarray(datos)
	return {
		"duracion": round(len(x) / float(frecuencia), 3),
		"canales": 1 if x.ndim == 1 else int(x.shape[1]),
		"pico": round(pico(x), 4),
		"nivel": round(nivel(x, frecuencia), 5),
		"rms": round(float(np.sqrt(np.mean(np.square(_mono(x))))) if len(x) else 0.0, 5),
		"agudos": round(sintesis.fraccion_agudos(x, frecuencia=frecuencia), 4),
		"centroide": round(centroide(x, frecuencia)),
		"costura": round(costura(x), 3),
	}


# ── Fichero de niveles de referencia ─────────────────────────────────────────


def leer_niveles(carpeta: Path) -> dict[str, tuple[float, float]]:
	"""``{nombre: (nivel, pico)}`` de ``carpeta/niveles.json``; vacío si no está o no vale."""
	ruta = Path(carpeta) / NOMBRE_NIVELES
	if not ruta.is_file():
		return {}
	try:
		leido = json.loads(ruta.read_text(encoding="utf-8"))
	except OSError, ValueError:
		log.warning("No se pudo leer %s; los niveles se medirán al cargar cada sonido.", ruta, exc_info=True)
		return {}
	niveles = leido.get("niveles") if isinstance(leido, dict) else None
	if not isinstance(niveles, dict):
		log.warning("%s no tiene el formato esperado; se ignora.", ruta)
		return {}
	resultado: dict[str, tuple[float, float]] = {}
	for nombre, par in niveles.items():
		if (
			isinstance(par, (list, tuple))
			and len(par) >= 2
			and all(isinstance(v, (int, float)) and not isinstance(v, bool) for v in par[:2])
		):
			resultado[str(nombre)] = (float(par[0]), float(par[1]))
	return resultado


def escribir_niveles(carpeta: Path, sonidos: dict[str, np.ndarray]) -> Path:
	"""Mide ``sonidos`` y escribe ``carpeta/niveles.json`` de forma atómica. Devuelve su ruta."""
	carpeta = Path(carpeta)
	carpeta.mkdir(parents=True, exist_ok=True)
	datos = {
		"formato": FORMATO_NIVELES,
		"explicacion": "Nivel (media cuadrática del tramo de 0,3 s más fuerte) y pico de cada sonido. Sirve de referencia para igualar los demás paquetes.",
		"niveles": {nombre: [round(nivel(muestras), 6), round(pico(muestras), 6)] for nombre, muestras in sonidos.items()},
	}
	ruta = carpeta / NOMBRE_NIVELES
	temporal = ruta.with_name(ruta.name + ".tmp")
	temporal.write_text(json.dumps(datos, ensure_ascii=False, indent="\t") + "\n", encoding="utf-8")
	os.replace(temporal, ruta)
	return ruta
