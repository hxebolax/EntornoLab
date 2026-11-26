"""Puntuación de actividades y exámenes: funciones puras, fáciles de comprobar a mano.

Cada medida sigue a un estudio o a una práctica de orientación y movilidad
(ver ``docs/actividades.md``):

- **Salida más corta, 3-2-1-0**: la medida de AbES (Connors y otros, 2014).
  Se puntúa la salida ELEGIDA según su puesto entre las salidas ordenadas por
  distancia de camino desde el punto de partida.
- **Error angular al señalar**: grados entre hacia donde mira el alumno y la
  dirección real en línea recta (tareas de señalamiento, Lahav y otros, 2015).
- **Cociente camino real / camino óptimo**: 1 es el camino más corto.
- **Regla de parada**: se deja el examen cuando ya no se puede alcanzar el
  mínimo de aciertos en las primeras pruebas, para no frustrar.

Ninguna de estas cifras es un diagnóstico ni equivale a competencia en el
lugar real: describen lo ocurrido en el simulador.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from typing import Any

from app.dominio import geometria as geo

# Motivos por los que se gana una estrella. Cada uno premia una cosa distinta.
MOTIVOS_ESTRELLA: tuple[str, ...] = ("completar", "pocas_ayudas", "atajo", "salida_optima", "sin_choques", "exploracion", "seguridad")

# Ayudas que «dan la respuesta» y por eso cuentan para la estrella de pocas ayudas. Percibir (bastón, mirar, eco) no cuenta.
AYUDAS_QUE_CUENTAN: tuple[str, ...] = ("pista", "baliza", "donde_estoy", "descripcion", "cercanos", "descubiertos")

LIMITE_POCAS_AYUDAS = 2
UMBRAL_ATAJO = 1.35
UMBRAL_SALIDA_OPTIMA = 2.5
LIMITE_SIN_CHOQUES = 0
UMBRAL_EXPLORACION = 0.999
PUNTOS_SALIDA_MAXIMO = 3


def puntos_salida(elegida: str, ordenadas: Sequence[tuple[str, float]], tolerancia_m: float = 1.0) -> int:
	"""Puntos (3, 2, 1 o 0) por salir por ``elegida``.

	``ordenadas`` son las salidas alcanzables con su distancia de camino
	desde el punto de partida. Vale 3 la más cercana, 2 la segunda, 1 la
	tercera y 0 cualquier otra. Dos salidas que distan menos de
	``tolerancia_m`` entre sí comparten puesto: no se castiga elegir entre
	dos puertas que quedan igual de cerca.
	"""
	distancias = {str(ident): float(distancia) for ident, distancia in ordenadas}
	if elegida not in distancias:
		return 0
	propia = distancias[elegida]
	mejores = sum(1 for ident, distancia in distancias.items() if ident != elegida and distancia < propia - max(0.0, tolerancia_m))
	return max(0, PUNTOS_SALIDA_MAXIMO - mejores)


def error_angular(rumbo_alumno: float, rumbo_real: float) -> float:
	"""Grados (0 a 180) entre hacia donde mira el alumno y la dirección real."""
	return abs(geo.diferencia_rumbos(rumbo_alumno, rumbo_real))


def cociente_camino(real_m: float | None, optimo_m: float | None) -> float | None:
	"""Camino andado entre camino más corto; None si no hay óptimo con el que comparar."""
	if real_m is None or optimo_m is None or optimo_m <= 0.05 or not math.isfinite(optimo_m):
		return None
	return round(max(0.0, real_m) / optimo_m, 3)


def puntos_cruce(incidente: bool, por_paso: bool, en_rojo: bool) -> int:
	"""Puntos de un cruce de calzada.

	3 por el paso de peatones y sin incidentes, 2 sin incidentes pero fuera
	del paso, 1 si se cruzó con el semáforo en rojo aunque no pasara nada y 0
	si un vehículo tuvo que frenar o pasó al lado (``incidente``).
	"""
	if incidente:
		return 0
	if en_rojo:
		return 1
	return 3 if por_paso else 2


def debe_parar(aciertos: Sequence[bool], regla: Mapping[str, Any] | None) -> bool:
	"""Si la regla de parada manda terminar ya el examen.

	``regla`` es ``{"de": 5, "minimo": 3}``: hacen falta 3 aciertos en las 5
	primeras pruebas para seguir. Se para en cuanto es imposible llegar al
	mínimo (con tres fallos de cinco ya no se llega a tres aciertos), sin
	hacer pasar al alumno por las pruebas que faltan.
	"""
	if not regla or regla.get("activa") is False:
		return False
	try:
		de = max(1, int(regla.get("de", 5)))
		minimo = max(1, int(regla.get("minimo", 3)))
	except TypeError, ValueError:
		return False
	minimo = min(minimo, de)
	primeras = list(aciertos)[:de]
	fallos = sum(1 for acierto in primeras if not acierto)
	return fallos > de - minimo


def mediana(valores: Sequence[float]) -> float | None:
	"""Mediana de una lista de números; None si está vacía."""
	ordenados = sorted(float(v) for v in valores)
	if not ordenados:
		return None
	mitad = len(ordenados) // 2
	if len(ordenados) % 2:
		return ordenados[mitad]
	return (ordenados[mitad - 1] + ordenados[mitad]) / 2.0


def media(valores: Sequence[float]) -> float | None:
	"""Media de una lista de números; None si está vacía."""
	lista = [float(v) for v in valores]
	return sum(lista) / len(lista) if lista else None


def ayudas_contadas(usos: Mapping[str, int]) -> int:
	"""Número de ayudas «de respuesta» usadas (pistas, baliza, dónde estoy…)."""
	return sum(int(usos.get(ayuda, 0)) for ayuda in AYUDAS_QUE_CUENTAN)


def estrellas(
	completada: bool,
	posibles: Sequence[str],
	ayudas: int = 0,
	cociente: float | None = None,
	media_salida: float | None = None,
	choques: int = 0,
	exploracion: float | None = None,
	seguro: bool | None = None,
	con_baliza_continua: bool = False,
) -> list[str]:
	"""Motivos de estrella ganados, en el orden de ``MOTIVOS_ESTRELLA``.

	Sin completar la actividad no hay estrellas, salvo la de exploración
	(que premia haberlo recorrido todo aunque no se encontrara todo). La de
	pocas ayudas no se gana con la baliza sonando todo el rato: ganar nunca
	depende solo de seguir una baliza.
	"""
	ganadas: list[str] = []
	for motivo in MOTIVOS_ESTRELLA:
		if motivo not in posibles:
			continue
		if motivo == "exploracion":
			if exploracion is not None and exploracion >= UMBRAL_EXPLORACION:
				ganadas.append(motivo)
			continue
		if not completada:
			continue
		if motivo == "completar":
			ganadas.append(motivo)
		elif motivo == "pocas_ayudas" and ayudas <= LIMITE_POCAS_AYUDAS and not con_baliza_continua:
			ganadas.append(motivo)
		elif motivo == "atajo" and cociente is not None and cociente <= UMBRAL_ATAJO:
			ganadas.append(motivo)
		elif motivo == "salida_optima" and media_salida is not None and media_salida >= UMBRAL_SALIDA_OPTIMA:
			ganadas.append(motivo)
		elif motivo == "sin_choques" and choques <= LIMITE_SIN_CHOQUES:
			ganadas.append(motivo)
		elif motivo == "seguridad" and seguro:
			ganadas.append(motivo)
	return ganadas


def resumen_examen(pruebas: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
	"""Cifras comunes de un examen: pruebas hechas, aciertos, porcentaje y tiempos (solo tiempo de juego, sin pausas)."""
	hechas = [p for p in pruebas if p.get("hecha", True)]
	aciertos = sum(1 for p in hechas if p.get("acierto"))
	tiempos = [float(p["tiempo_s"]) for p in hechas if isinstance(p.get("tiempo_s"), (int, float))]
	tiempos_acierto = [float(p["tiempo_s"]) for p in hechas if p.get("acierto") and isinstance(p.get("tiempo_s"), (int, float))]
	tiempo_medio = media(tiempos)
	tiempo_medio_acierto = media(tiempos_acierto)
	return {
		"pruebas_hechas": len(hechas),
		"aciertos": aciertos,
		"porcentaje_aciertos": round(100.0 * aciertos / len(hechas), 1) if hechas else 0.0,
		"tiempo_total_s": round(sum(tiempos), 1),
		"tiempo_medio_s": round(tiempo_medio, 1) if tiempo_medio is not None else None,
		"tiempo_medio_aciertos_s": round(tiempo_medio_acierto, 1) if tiempo_medio_acierto is not None else None,
	}
