"""Medidas de una sesión, calculadas a partir de la traza y de los eventos.

Todo son funciones puras: reciben listas y devuelven un diccionario que se
puede guardar como JSON. No se importa el modelo del entorno: lo que hace
falta de él (la lista de espacios con su contorno y la longitud del camino
óptimo) llega como dato, para que este módulo se pruebe solo y para que el
resumen se pueda recalcular años después sin abrir el paquete del entorno.

Formato de entrada:

- ``muestras``: lista de ``(t, planta, x, y, rumbo)``; ``t`` es el segundo de
  tiempo ACTIVO de la sesión (el reloj no corre en pausa).
- ``eventos``: lista de ``{"t": segundos, "tipo": str, "datos": dict}`` (los
  ``EvRegistro`` del motor). Lugar del evento: ``datos["x"]``, ``datos["y"]``
  y ``datos["planta"]`` si vienen; si no, ``evento["pos"] = [planta, x, y]``,
  que añade la grabadora con la última posición conocida.
- ``espacios``: lista de ``{"id", "nombre", "planta", "contorno": [[x, y], ...]}``;
  el contorno es opcional (sin él no se puede medir el tiempo por espacio a
  partir de la traza ni valorar el recorrido por el perímetro con precisión).

Las medidas son DESCRIPTIVAS. La clasificación de la estrategia de
exploración es una heurística con límites claros (ver ``clasificar_estrategia``):
nunca debe presentarse como un juicio sobre el alumno.
"""

from __future__ import annotations

import math
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

FORMATO_RESUMEN = 1

# ── Umbrales (documentados en docs/seguimiento.md) ───────────────────────────

# Un desplazamiento mayor entre dos muestras no es andar: es una recolocación.
SALTO_MINIMO_M = 3.0
VELOCIDAD_MAXIMA_MS = 6.0
# Por debajo de esta velocidad se considera que el alumno está parado.
VELOCIDAD_PARADO_MS = 0.05
# Giro: rotación acumulada en un mismo sentido de al menos estos grados.
GIRO_MINIMO_GRADOS = 30.0
GIRO_PAUSA_S = 1.0
MEDIA_VUELTA_GRADOS = 150.0
# Estrategia de exploración.
ESTRATEGIA_DISTANCIA_MINIMA_M = 8.0
ESTRATEGIA_MUESTRAS_MINIMAS = 40
PARED_CERCA_M = 1.0
PERIMETRO_CERCA = 0.6
PERIMETRO_COBERTURA = 0.5
ESPACIO_ANCHO_MINIMO_M = 3.0
TRAMO_MINIMO_M = 1.5
TRAMO_TOLERANCIA_GRADOS = 20.0
CUADRICULA_EJE = 0.6
CUADRICULA_PASADAS = 4
CUADRICULA_DESPLAZAMIENTO_M = 0.5
CONTACTO_RADIO_M = 1.0
OBJETOS_RECTITUD = 0.7
OBJETOS_TRAMOS = 3
OBJETOS_PROPORCION = 0.5

# Tipos de evento que cuentan como «tocar algo» para la estrategia objeto a objeto.
TIPOS_CONTACTO: frozenset[str] = frozenset({"choque", "contacto", "interaccion", "premio", "objeto"})

ESTRATEGIAS: tuple[str, ...] = ("perimetro", "cuadricula", "objeto_a_objeto", "sin_patron", "insuficiente")

Muestra = Sequence[Any]
Evento = Mapping[str, Any]
Punto = tuple[float, float]


# ── Geometría mínima (propia, para no depender de app.dominio) ───────────────


def _distancia_a_segmento(p: Punto, a: Punto, b: Punto) -> float:
	dx = b[0] - a[0]
	dy = b[1] - a[1]
	largo2 = dx * dx + dy * dy
	if largo2 <= 0.0:
		return math.hypot(p[0] - a[0], p[1] - a[1])
	u = ((p[0] - a[0]) * dx + (p[1] - a[1]) * dy) / largo2
	u = max(0.0, min(1.0, u))
	return math.hypot(p[0] - (a[0] + u * dx), p[1] - (a[1] + u * dy))


def _dentro(p: Punto, contorno: Sequence[Punto]) -> bool:
	"""Punto en polígono por cruce de rayos."""
	dentro = False
	total = len(contorno)
	for i in range(total):
		x1, y1 = contorno[i]
		x2, y2 = contorno[(i + 1) % total]
		if (y1 > p[1]) != (y2 > p[1]):
			corte = x1 + (p[1] - y1) * (x2 - x1) / (y2 - y1)
			if p[0] < corte:
				dentro = not dentro
	return dentro


def _contorno(espacio: Mapping[str, Any]) -> list[Punto]:
	puntos: list[Punto] = []
	for punto in espacio.get("contorno") or ():
		try:
			puntos.append((float(punto[0]), float(punto[1])))
		except TypeError, ValueError, IndexError:
			return []
	return puntos if len(puntos) >= 3 else []


def _diferencia_rumbo(a: float, b: float) -> float:
	"""Giro de ``a`` a ``b`` en grados, entre -180 y 180 (positivo: a la derecha)."""
	return (b - a + 180.0) % 360.0 - 180.0


def _rumbo_de(dx: float, dy: float) -> float:
	"""Rumbo del desplazamiento: 0 = norte (+Y), 90 = este (+X)."""
	return math.degrees(math.atan2(dx, dy)) % 360.0


# ── Normalización de la entrada ──────────────────────────────────────────────


def _limpiar_muestras(muestras: Iterable[Muestra]) -> list[tuple[float, str, float, float, float]]:
	"""Descarta las muestras mal formadas y ordena por tiempo.

	Un fichero de sesión puede venir de otra versión o estar truncado: una
	muestra rota no debe impedir el informe del resto.
	"""
	limpias: list[tuple[float, str, float, float, float]] = []
	for muestra in muestras:
		try:
			t = float(muestra[0])
			planta = str(muestra[1])
			x = float(muestra[2])
			y = float(muestra[3])
			rumbo = float(muestra[4])
		except TypeError, ValueError, IndexError:
			continue
		if not all(math.isfinite(valor) for valor in (t, x, y, rumbo)):
			continue
		limpias.append((t, planta, x, y, rumbo))
	limpias.sort(key=lambda m: m[0])
	return limpias


def _limpiar_eventos(eventos: Iterable[Evento]) -> list[dict[str, Any]]:
	limpios: list[dict[str, Any]] = []
	for evento in eventos:
		if not isinstance(evento, Mapping):
			continue
		tipo = evento.get("tipo")
		if not isinstance(tipo, str) or not tipo:
			continue
		try:
			t = float(evento.get("t", 0.0))
		except TypeError, ValueError:
			t = 0.0
		datos = evento.get("datos")
		limpios.append({"t": t, "tipo": tipo, "datos": dict(datos) if isinstance(datos, Mapping) else {}, "pos": evento.get("pos")})
	limpios.sort(key=lambda e: e["t"])
	return limpios


def lugar_de(evento: Evento) -> tuple[str, float, float] | None:
	"""``(planta, x, y)`` de un evento, o ``None`` si no se sabe dónde ocurrió."""
	datos = evento.get("datos") or {}
	try:
		if "x" in datos and "y" in datos:
			return (str(datos.get("planta", "")), float(datos["x"]), float(datos["y"]))
		pos = evento.get("pos")
		if pos is not None and len(pos) >= 3:
			return (str(pos[0]), float(pos[1]), float(pos[2]))
	except TypeError, ValueError:
		return None
	return None


def espacio_en(planta: str, x: float, y: float, espacios: Sequence[Mapping[str, Any]]) -> str | None:
	"""Id del espacio que contiene el punto, o ``None`` (sin contornos o fuera de todos)."""
	for espacio in espacios:
		if str(espacio.get("planta", "")) not in ("", planta):
			continue
		contorno = _contorno(espacio)
		if contorno and _dentro((x, y), contorno):
			return str(espacio.get("id", ""))
	return None


def _primero(datos: Mapping[str, Any], *claves: str) -> str:
	"""Primer valor no vacío entre varias claves posibles.

	El motor y las actividades se escriben a la vez que este módulo: se
	aceptan los nombres de campo razonables en lugar de exigir uno solo.
	"""
	for clave in claves:
		valor = datos.get(clave)
		if valor not in (None, ""):
			return str(valor)
	return ""


# ── Medidas sueltas ──────────────────────────────────────────────────────────


def medir_distancia(muestras: Sequence[Muestra]) -> dict[str, Any]:
	"""Distancia andada, tiempo en movimiento y saltos.

	Se suman los tramos entre muestras consecutivas de la misma planta. Un
	tramo de más de 3 m (o de más de 6 m/s) no es andar sino una recolocación
	(del profesional, «volver al inicio», un ascensor): se cuenta como salto y
	no suma distancia.
	"""
	limpias = _limpiar_muestras(muestras)
	distancia = 0.0
	en_movimiento = 0.0
	saltos = 0
	for anterior, actual in zip(limpias, limpias[1:], strict=False):
		dt = actual[0] - anterior[0]
		if anterior[1] != actual[1]:
			continue
		tramo = math.hypot(actual[2] - anterior[2], actual[3] - anterior[3])
		if tramo > max(SALTO_MINIMO_M, VELOCIDAD_MAXIMA_MS * max(dt, 0.0)):
			saltos += 1
			continue
		distancia += tramo
		if dt > 0 and tramo / dt >= VELOCIDAD_PARADO_MS:
			en_movimiento += dt
	return {"distancia_m": distancia, "tiempo_en_movimiento_s": en_movimiento, "saltos": saltos}


def medir_giros(muestras: Sequence[Muestra]) -> dict[str, Any]:
	"""Cuenta los giros a partir del rumbo.

	Un giro es una rotación seguida en el mismo sentido que suma al menos 30
	grados; termina al cambiar de sentido o al pasar un segundo sin rotar. Así
	un giro de 90 grados hecho en seis pulsaciones cuenta como uno, no como seis.
	"""
	limpias = _limpiar_muestras(muestras)
	giros = 0
	izquierda = 0
	derecha = 0
	medias_vueltas = 0
	grados = 0.0
	acumulado = 0.0
	ultimo_giro_t = 0.0

	def cerrar(valor: float) -> None:
		nonlocal giros, izquierda, derecha, medias_vueltas
		if abs(valor) < GIRO_MINIMO_GRADOS:
			return
		giros += 1
		if valor < 0:
			izquierda += 1
		else:
			derecha += 1
		if abs(valor) >= MEDIA_VUELTA_GRADOS:
			medias_vueltas += 1

	for anterior, actual in zip(limpias, limpias[1:], strict=False):
		cambio = _diferencia_rumbo(anterior[4], actual[4])
		if abs(cambio) < 1.0:
			if acumulado and actual[0] - ultimo_giro_t >= GIRO_PAUSA_S:
				cerrar(acumulado)
				acumulado = 0.0
			continue
		grados += abs(cambio)
		if acumulado and (cambio > 0) != (acumulado > 0):
			cerrar(acumulado)
			acumulado = 0.0
		acumulado += cambio
		ultimo_giro_t = actual[0]
	cerrar(acumulado)
	return {
		"numero": giros,
		"izquierda": izquierda,
		"derecha": derecha,
		"medias_vueltas": medias_vueltas,
		"grados_totales": grados,
	}


def medir_espacios(
	muestras: Sequence[Muestra],
	eventos: Sequence[Evento],
	espacios: Sequence[Mapping[str, Any]],
) -> dict[str, Any]:
	"""Espacios visitados y no visitados, con entradas, primera vez y tiempo.

	Dos fuentes, por este orden de preferencia:

	1. Los contornos de los espacios y la traza (punto en polígono): da además
	   el tiempo pasado en cada uno.
	2. Los eventos ``entrada_espacio`` del motor, cuando no hay contornos.
	"""
	limpias = _limpiar_muestras(muestras)
	nombres = {str(e.get("id", "")): str(e.get("nombre", "")) for e in espacios}
	hay_contornos = any(_contorno(e) for e in espacios)
	visitas: dict[str, dict[str, Any]] = {}
	fuente = "ninguna"

	def anotar(ident: str, nombre: str, t: float) -> None:
		ficha = visitas.setdefault(
			ident, {"id": ident, "nombre": nombre or nombres.get(ident, ""), "primera_vez_s": t, "entradas": 0, "tiempo_s": 0.0}
		)
		ficha["entradas"] += 1

	if hay_contornos and limpias:
		fuente = "traza"
		actual: str | None = None
		for i, muestra in enumerate(limpias):
			ident = espacio_en(muestra[1], muestra[2], muestra[3], espacios)
			if ident is not None and ident != actual:
				anotar(ident, "", muestra[0])
			actual = ident if ident is not None else actual
			if ident is not None and i + 1 < len(limpias):
				visitas[ident]["tiempo_s"] += max(0.0, limpias[i + 1][0] - muestra[0])
	else:
		entradas = [e for e in _limpiar_eventos(eventos) if e["tipo"] == "entrada_espacio"]
		if entradas:
			fuente = "eventos"
		fin = limpias[-1][0] if limpias else (entradas[-1]["t"] if entradas else 0.0)
		for i, evento in enumerate(entradas):
			ident = _primero(evento["datos"], "espacio", "espacio_id", "id")
			if not ident:
				continue
			anotar(ident, _primero(evento["datos"], "nombre", "espacio_nombre"), evento["t"])
			siguiente = entradas[i + 1]["t"] if i + 1 < len(entradas) else fin
			visitas[ident]["tiempo_s"] += max(0.0, siguiente - evento["t"])

	visitados = sorted(visitas.values(), key=lambda v: v["primera_vez_s"])
	no_visitados = [
		{"id": str(e.get("id", "")), "nombre": str(e.get("nombre", ""))}
		for e in espacios
		if str(e.get("id", "")) not in visitas and not e.get("macizo")
	]
	total = len(visitados) + len(no_visitados)
	return {
		"fuente": fuente,
		"visitados": visitados,
		"no_visitados": no_visitados,
		"total": total,
		"proporcion_visitada": (len(visitados) / total) if total else None,
	}


# ── Estrategia de exploración ────────────────────────────────────────────────


def _tramos_rectos(limpias: Sequence[tuple[float, str, float, float, float]]) -> list[dict[str, Any]]:
	"""Trocea el recorrido en tramos rectos (misma dirección de avance, con tolerancia)."""
	tramos: list[dict[str, Any]] = []
	actual: dict[str, Any] | None = None

	def cerrar() -> None:
		nonlocal actual
		if actual is not None and actual["largo"] >= TRAMO_MINIMO_M:
			tramos.append(actual)
		actual = None

	for anterior, muestra in zip(limpias, limpias[1:], strict=False):
		dx = muestra[2] - anterior[2]
		dy = muestra[3] - anterior[3]
		paso = math.hypot(dx, dy)
		if anterior[1] != muestra[1] or paso > SALTO_MINIMO_M:
			cerrar()
			continue
		if paso < 0.02:
			continue
		direccion = _rumbo_de(dx, dy)
		if actual is not None and abs(_diferencia_rumbo(actual["direccion"], direccion)) > TRAMO_TOLERANCIA_GRADOS:
			cerrar()
		if actual is None:
			actual = {"direccion": direccion, "largo": 0.0, "inicio": (anterior[2], anterior[3]), "fin": (muestra[2], muestra[3])}
		actual["largo"] += paso
		actual["fin"] = (muestra[2], muestra[3])
	cerrar()
	return tramos


def _indicadores_cuadricula(tramos: Sequence[Mapping[str, Any]]) -> tuple[float, int]:
	"""(proporción de la longitud en el eje dominante, número de pasadas alternas y desplazadas)."""
	total = sum(t["largo"] for t in tramos)
	if total <= 0:
		return 0.0, 0
	mejor_eje = 0.0
	mejor_largo = 0.0
	for candidato in range(0, 180, 10):
		largo = sum(t["largo"] for t in tramos if _desvio_eje(t["direccion"], candidato) <= TRAMO_TOLERANCIA_GRADOS)
		if largo > mejor_largo:
			mejor_largo = largo
			mejor_eje = float(candidato)
	del_eje = [t for t in tramos if _desvio_eje(t["direccion"], mejor_eje) <= TRAMO_TOLERANCIA_GRADOS]
	# Vector normal al eje: mide cuánto se desplaza cada pasada respecto a la anterior.
	normal = (math.cos(math.radians(mejor_eje)), -math.sin(math.radians(mejor_eje)))
	pasadas = 1 if del_eje else 0
	for anterior, tramo in zip(del_eje, del_eje[1:], strict=False):
		sentido_contrario = abs(_diferencia_rumbo(anterior["direccion"], tramo["direccion"])) > 90.0
		lateral_anterior = anterior["inicio"][0] * normal[0] + anterior["inicio"][1] * normal[1]
		lateral = tramo["inicio"][0] * normal[0] + tramo["inicio"][1] * normal[1]
		if sentido_contrario and abs(lateral - lateral_anterior) >= CUADRICULA_DESPLAZAMIENTO_M:
			pasadas += 1
	return mejor_largo / total, pasadas


def _desvio_eje(direccion: float, eje: float) -> float:
	"""Ángulo entre una dirección y un eje (sin sentido), de 0 a 90 grados."""
	desvio = abs(_diferencia_rumbo(eje, direccion))
	return min(desvio, 180.0 - desvio)


def _espacio_principal(
	limpias: Sequence[tuple[float, str, float, float, float]],
	espacios: Sequence[Mapping[str, Any]],
) -> tuple[list[Punto], str, bool]:
	"""Contorno del espacio donde hay más muestras; si no hay contornos, la caja de la traza.

	Devuelve (contorno, planta, aproximado).
	"""
	cuenta: dict[str, int] = {}
	for muestra in limpias:
		ident = espacio_en(muestra[1], muestra[2], muestra[3], espacios)
		if ident is not None:
			cuenta[ident] = cuenta.get(ident, 0) + 1
	if cuenta:
		principal = max(cuenta, key=lambda ident: cuenta[ident])
		for espacio in espacios:
			if str(espacio.get("id", "")) == principal:
				return _contorno(espacio), str(espacio.get("planta", "")), False
	plantas: dict[str, int] = {}
	for muestra in limpias:
		plantas[muestra[1]] = plantas.get(muestra[1], 0) + 1
	planta = max(plantas, key=lambda p: plantas[p])
	xs = [m[2] for m in limpias if m[1] == planta]
	ys = [m[3] for m in limpias if m[1] == planta]
	caja = [(min(xs), min(ys)), (max(xs), min(ys)), (max(xs), max(ys)), (min(xs), max(ys))]
	return caja, planta, True


def _indicadores_perimetro(
	limpias: Sequence[tuple[float, str, float, float, float]],
	contorno: Sequence[Punto],
	planta: str,
) -> tuple[float, float] | None:
	"""(proporción de la distancia hecha cerca de la pared, proporción del perímetro recorrida).

	``None`` si el espacio es demasiado estrecho para que «ir por el
	perímetro» signifique algo (en un pasillo de 2 m todo está junto a la pared).
	"""
	xs = [p[0] for p in contorno]
	ys = [p[1] for p in contorno]
	if min(max(xs) - min(xs), max(ys) - min(ys)) < ESPACIO_ANCHO_MINIMO_M:
		return None
	lados = [(contorno[i], contorno[(i + 1) % len(contorno)]) for i in range(len(contorno))]
	# El perímetro se parte en trozos de un metro para medir cuánto se ha cubierto.
	trozos: list[Punto] = []
	for a, b in lados:
		largo = math.hypot(b[0] - a[0], b[1] - a[1])
		partes = max(1, round(largo))
		for i in range(partes):
			u = (i + 0.5) / partes
			trozos.append((a[0] + (b[0] - a[0]) * u, a[1] + (b[1] - a[1]) * u))
	cubiertos = [False] * len(trozos)
	total = 0.0
	cerca = 0.0
	for anterior, muestra in zip(limpias, limpias[1:], strict=False):
		if muestra[1] != anterior[1] or (planta and muestra[1] != planta):
			continue
		paso = math.hypot(muestra[2] - anterior[2], muestra[3] - anterior[3])
		if paso > SALTO_MINIMO_M or paso < 0.02:
			continue
		punto = (muestra[2], muestra[3])
		if not _dentro(punto, contorno) and min(_distancia_a_segmento(punto, a, b) for a, b in lados) > PARED_CERCA_M:
			continue
		total += paso
		if min(_distancia_a_segmento(punto, a, b) for a, b in lados) <= PARED_CERCA_M:
			cerca += paso
			for i, trozo in enumerate(trozos):
				if not cubiertos[i] and math.hypot(trozo[0] - punto[0], trozo[1] - punto[1]) <= PARED_CERCA_M + 0.5:
					cubiertos[i] = True
	if total <= 0:
		return 0.0, 0.0
	return cerca / total, sum(cubiertos) / len(cubiertos)


def _indicadores_objetos(
	limpias: Sequence[tuple[float, str, float, float, float]],
	eventos: Sequence[Mapping[str, Any]],
	distancia_total: float,
) -> tuple[int, float]:
	"""(tramos rectos entre contactos distintos, proporción de la distancia hecha en ellos)."""
	contactos: list[tuple[float, float, float]] = []
	for evento in eventos:
		if evento["tipo"] not in TIPOS_CONTACTO:
			continue
		lugar = lugar_de(evento)
		if lugar is None:
			continue
		if contactos and math.hypot(lugar[1] - contactos[-1][1], lugar[2] - contactos[-1][2]) <= CONTACTO_RADIO_M:
			continue
		contactos.append((evento["t"], lugar[1], lugar[2]))
	rectos = 0
	distancia_recta = 0.0
	for a, b in zip(contactos, contactos[1:], strict=False):
		tramo = [m for m in limpias if a[0] <= m[0] <= b[0]]
		camino = sum(math.hypot(m2[2] - m1[2], m2[3] - m1[3]) for m1, m2 in zip(tramo, tramo[1:], strict=False))
		directo = math.hypot(b[1] - a[1], b[2] - a[2])
		if camino > 0 and directo / camino >= OBJETOS_RECTITUD:
			rectos += 1
			distancia_recta += camino
	return rectos, (distancia_recta / distancia_total) if distancia_total > 0 else 0.0


def clasificar_estrategia(
	muestras: Sequence[Muestra],
	eventos: Sequence[Evento] = (),
	espacios: Sequence[Mapping[str, Any]] = (),
) -> dict[str, Any]:
	"""Clasifica la forma de explorar: perímetro, cuadrícula, objeto a objeto o sin patrón.

	HEURÍSTICA (por orden; gana la primera que se cumple):

	1. **Perímetro.** En el espacio donde el alumno pasó más tiempo, al menos
	   el 60 % de la distancia se hizo a un metro o menos de sus paredes, y se
	   recorrió al menos la mitad de la longitud del perímetro.
	2. **Cuadrícula.** El recorrido se trocea en tramos rectos de 1,5 m o más;
	   al menos el 60 % de su longitud sigue un mismo eje (±20 grados) y hay
	   cuatro o más pasadas en sentidos alternos, cada una desplazada medio
	   metro o más de la anterior.
	3. **Objeto a objeto.** Hay al menos tres tramos entre contactos distintos
	   (choques, objetos usados, premios) casi rectos (distancia directa /
	   distancia andada de 0,7 o más) y suman la mitad o más de la distancia.
	4. **Sin patrón** en otro caso. **Insuficiente** si se anduvo menos de 8 m
	   o hay menos de 10 segundos de traza.

	LÍMITES (se repiten en el informe):

	- Es una descripción geométrica del recorrido, no una valoración: no dice
	  si la estrategia era adecuada ni si el alumno la eligió a propósito.
	- En espacios de menos de 3 m de ancho no se valora el perímetro. Sin
	  contornos se usa la caja que encierra la traza, y la confianza es baja.
	- Solo se mira el espacio principal; una sesión que mezcla estrategias, o
	  una actividad de ruta (donde no se explora), sale «sin patrón».
	- En el modo de movimiento por pasos, los tramos son rectos por
	  construcción, lo que favorece «cuadrícula» y «objeto a objeto».
	- Los umbrales son convenciones de este programa, no valores validados.
	"""
	limpias = _limpiar_muestras(muestras)
	sucesos = _limpiar_eventos(eventos)
	distancia = medir_distancia(limpias)["distancia_m"]
	indicadores: dict[str, Any] = {}
	if distancia < ESTRATEGIA_DISTANCIA_MINIMA_M or len(limpias) < ESTRATEGIA_MUESTRAS_MINIMAS:
		return {"tipo": "insuficiente", "confianza": "baja", "indicadores": indicadores, "aproximada": False}

	contorno, planta, aproximado = _espacio_principal(limpias, espacios)
	perimetro = _indicadores_perimetro(limpias, contorno, planta) if contorno else None
	if perimetro is not None:
		indicadores["cerca_de_pared"] = round(perimetro[0], 3)
		indicadores["cobertura_perimetro"] = round(perimetro[1], 3)
	tramos = _tramos_rectos(limpias)
	eje, pasadas = _indicadores_cuadricula(tramos)
	indicadores["eje_dominante"] = round(eje, 3)
	indicadores["pasadas"] = pasadas
	rectos, proporcion = _indicadores_objetos(limpias, sucesos, distancia)
	indicadores["tramos_entre_contactos"] = rectos
	indicadores["distancia_entre_contactos"] = round(proporcion, 3)

	tipo = "sin_patron"
	holgura = 0.0
	if perimetro is not None and perimetro[0] >= PERIMETRO_CERCA and perimetro[1] >= PERIMETRO_COBERTURA:
		tipo = "perimetro"
		holgura = min(perimetro[0] / PERIMETRO_CERCA, perimetro[1] / PERIMETRO_COBERTURA)
	elif eje >= CUADRICULA_EJE and pasadas >= CUADRICULA_PASADAS:
		tipo = "cuadricula"
		holgura = min(eje / CUADRICULA_EJE, pasadas / CUADRICULA_PASADAS)
	elif rectos >= OBJETOS_TRAMOS and proporcion >= OBJETOS_PROPORCION:
		tipo = "objeto_a_objeto"
		holgura = min(rectos / OBJETOS_TRAMOS, proporcion / OBJETOS_PROPORCION)
	if tipo == "sin_patron" or (aproximado and tipo == "perimetro"):
		confianza = "baja"
	elif holgura >= 1.25:
		confianza = "alta"
	else:
		confianza = "media"
	return {"tipo": tipo, "confianza": confianza, "indicadores": indicadores, "aproximada": aproximado}


# ── Resumen completo ─────────────────────────────────────────────────────────


def calcular_resumen(
	muestras: Sequence[Muestra],
	eventos: Sequence[Evento] = (),
	*,
	espacios: Sequence[Mapping[str, Any]] = (),
	camino_optimo_m: float | None = None,
	pausas: Sequence[Sequence[float]] = (),
	tiempo_activo_s: float | None = None,
	tiempo_pausa_s: float | None = None,
	puntuaciones: Mapping[str, Any] | None = None,
	resultado: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
	"""Resumen de una sesión con todas las medidas (serializable como JSON).

	:param espacios: espacios del entorno (id, nombre, planta y contorno opcional).
	:param camino_optimo_m: longitud del camino más corto, calculada por el
		motor (``navegacion``); sin ella no hay cociente.
	:param pausas: lista de ``(t, duracion)``: segundo de tiempo activo en que
		empezó cada pausa y cuánto duró.
	:param tiempo_activo_s: si no se da, el instante de la última muestra o evento.
	:param puntuaciones: puntuaciones de examen tal como las da el motor; se
		guardan sin interpretar.
	:param resultado: el diccionario de ``EvFin``; se guarda tal cual.
	"""
	limpias = _limpiar_muestras(muestras)
	sucesos = _limpiar_eventos(eventos)
	ultimo = max([m[0] for m in limpias[-1:]] + [e["t"] for e in sucesos[-1:]] + [0.0])
	activo = float(tiempo_activo_s) if tiempo_activo_s is not None else ultimo
	lista_pausas = [[float(p[0]), float(p[1])] for p in pausas if len(p) >= 2]
	en_pausa = float(tiempo_pausa_s) if tiempo_pausa_s is not None else sum(p[1] for p in lista_pausas)

	recorrido = medir_distancia(limpias)
	distancia = recorrido["distancia_m"]

	def con_lugar(evento: Mapping[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
		ficha: dict[str, Any] = {"t": evento["t"]}
		lugar = lugar_de(evento)
		if lugar is not None:
			ficha["planta"] = lugar[0]
			ficha["x"] = round(lugar[1], 2)
			ficha["y"] = round(lugar[2], 2)
			ident = _primero(evento["datos"], "espacio", "espacio_id") or espacio_en(lugar[0], lugar[1], lugar[2], espacios) or ""
			ficha["espacio"] = ident
		else:
			ficha["espacio"] = _primero(evento["datos"], "espacio", "espacio_id")
		ficha.update(extra)
		return ficha

	choques = [con_lugar(e, {"con": _primero(e["datos"], "con", "objeto", "nombre", "material")}) for e in sucesos if e["tipo"] == "choque"]
	choques_por_espacio: dict[str, int] = {}
	for choque in choques:
		clave = choque.get("espacio") or ""
		choques_por_espacio[clave] = choques_por_espacio.get(clave, 0) + 1

	ayudas = [con_lugar(e, {"tipo": _primero(e["datos"], "ayuda", "tipo", "nombre") or "otra"}) for e in sucesos if e["tipo"] == "ayuda"]
	ayudas_por_tipo: dict[str, int] = {}
	for ayuda in ayudas:
		ayudas_por_tipo[ayuda["tipo"]] = ayudas_por_tipo.get(ayuda["tipo"], 0) + 1

	objetivos = [
		{"t": e["t"], "id": _primero(e["datos"], "id", "objetivo"), "nombre": _primero(e["datos"], "nombre", "texto")}
		for e in sucesos
		if e["tipo"] == "objetivo"
	]
	premios = [
		{"t": e["t"], "id": _primero(e["datos"], "id", "premio"), "nombre": _primero(e["datos"], "nombre")}
		for e in sucesos
		if e["tipo"] == "premio"
	]
	recompensas = [
		{"tipo": _primero(e["datos"], "tipo") or "estrella", "nombre": _primero(e["datos"], "nombre"), "t": e["t"]}
		for e in sucesos
		if e["tipo"] == "recompensa"
	]
	intervenciones: dict[str, int] = {}
	for evento in sucesos:
		if evento["tipo"] == "intervencion":
			clase = _primero(evento["datos"], "tipo", "orden") or "otra"
			intervenciones[clase] = intervenciones.get(clase, 0) + 1
	por_tipo: dict[str, int] = {}
	for evento in sucesos:
		por_tipo[evento["tipo"]] = por_tipo.get(evento["tipo"], 0) + 1

	examen: dict[str, Any] | None = None
	if puntuaciones:
		examen = dict(puntuaciones)
	else:
		for evento in sucesos:
			if evento["tipo"] in ("examen", "puntuacion"):
				examen = examen or {}
				examen.setdefault("pruebas", []).append({"t": evento["t"], **evento["datos"]})
	valoracion = next((e["datos"] for e in reversed(sucesos) if e["tipo"] == "valoracion"), None)

	cociente = None
	if camino_optimo_m is not None and camino_optimo_m > 0:
		cociente = distancia / camino_optimo_m

	return {
		"formato": FORMATO_RESUMEN,
		"distancia_m": round(distancia, 2),
		"tiempo_activo_s": round(activo, 2),
		"tiempo_pausa_s": round(en_pausa, 2),
		"tiempo_en_movimiento_s": round(recorrido["tiempo_en_movimiento_s"], 2),
		"tiempo_parado_s": round(max(0.0, activo - recorrido["tiempo_en_movimiento_s"]), 2),
		"velocidad_media_ms": round(distancia / activo, 3) if activo > 0 else None,
		"velocidad_en_movimiento_ms": (
			round(distancia / recorrido["tiempo_en_movimiento_s"], 3) if recorrido["tiempo_en_movimiento_s"] > 0 else None
		),
		"saltos": recorrido["saltos"],
		"pausas": {"numero": len(lista_pausas), "lista": lista_pausas},
		"choques": {"total": len(choques), "lugares": choques, "por_espacio": choques_por_espacio},
		"ayudas": {"total": len(ayudas), "por_tipo": ayudas_por_tipo, "lista": ayudas},
		"objetivos": objetivos,
		"premios": premios,
		"recompensas": recompensas,
		"espacios": medir_espacios(limpias, sucesos, espacios),
		"camino_optimo_m": round(camino_optimo_m, 2) if camino_optimo_m is not None else None,
		"cociente_camino": round(cociente, 3) if cociente is not None else None,
		"giros": medir_giros(limpias),
		"estrategia": clasificar_estrategia(limpias, sucesos, espacios),
		"intervenciones": {"total": sum(intervenciones.values()), "por_tipo": intervenciones},
		"examen": examen,
		"valoracion": dict(valoracion) if valoracion else None,
		"eventos_por_tipo": por_tipo,
		"resultado": dict(resultado) if resultado else None,
		"muestras": len(limpias),
	}
