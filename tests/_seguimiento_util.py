"""Utilidades compartidas por las pruebas del seguimiento (no es un fichero de pruebas)."""

from __future__ import annotations

import hashlib
import math
from typing import Any

from app.seguimiento.base import Cifrador

SALA = {"id": "sala", "nombre": "Sala de estar", "planta": "p0", "contorno": [[0, 0], [10, 0], [10, 8], [0, 8]]}
COCINA = {"id": "cocina", "nombre": "Cocina", "planta": "p0", "contorno": [[10, 0], [16, 0], [16, 8], [10, 8]]}
BANO = {"id": "bano", "nombre": "Baño", "planta": "p0", "contorno": [[0, 8], [4, 8], [4, 11], [0, 11]]}
ESPACIOS = [SALA, COCINA, BANO]


def cifrador_de_prueba(clave: bytes) -> Cifrador:
	"""Cifrado de juguete (XOR con la clave y una suma de comprobación) que detecta una clave equivocada."""

	def mezclar(datos: bytes, llave: bytes) -> bytes:
		return bytes(octeto ^ llave[i % len(llave)] for i, octeto in enumerate(datos))

	def cifrar(datos: bytes, llave: bytes) -> bytes:
		return hashlib.sha256(llave + datos).digest()[:8] + mezclar(datos, llave)

	def descifrar(datos: bytes, llave: bytes) -> bytes:
		claro = mezclar(datos[8:], llave)
		if hashlib.sha256(llave + claro).digest()[:8] != datos[:8]:
			raise ValueError("clave incorrecta")
		return claro

	return Cifrador.con_clave(clave, cifrar, descifrar)


def andar(
	puntos: list[tuple[float, float]], *, planta: str = "p0", velocidad: float = 1.0, t0: float = 0.0, hz: float = 4.0
) -> list[list[Any]]:
	"""Muestras a ``hz`` por segundo recorriendo una línea quebrada a velocidad constante, mirando hacia donde se anda."""
	muestras: list[list[Any]] = []
	t = t0
	paso = velocidad / hz
	for (x1, y1), (x2, y2) in zip(puntos, puntos[1:], strict=False):
		largo = math.hypot(x2 - x1, y2 - y1)
		rumbo = math.degrees(math.atan2(x2 - x1, y2 - y1)) % 360.0
		partes = max(1, round(largo / paso))
		for i in range(partes):
			u = i / partes
			muestras.append([round(t, 3), planta, x1 + (x2 - x1) * u, y1 + (y2 - y1) * u, rumbo])
			t += 1.0 / hz
	ultimo = puntos[-1]
	rumbo_final = muestras[-1][4] if muestras else 0.0
	muestras.append([round(t, 3), planta, ultimo[0], ultimo[1], rumbo_final])
	return muestras


def documento_sesion(
	ident: str,
	alias: str = "Luna",
	*,
	inicio: str = "2026-11-20T10:00:00+00:00",
	fin: str = "2026-11-20T10:05:00+00:00",
	entorno: str = "casa",
	actividad: str = "buscar",
	modo: str = "juego",
	completada: bool = True,
	parcial: bool = False,
	resumen: dict[str, Any] | None = None,
	marcas: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
	"""Documento de sesión mínimo y válido, como el que escribe la grabadora."""
	from app.seguimiento import medidas

	muestras = andar([(1, 1), (5, 1), (5, 5)])
	eventos = [
		{"t": 2.0, "tipo": "choque", "datos": {"con": "mesa"}, "pos": ["p0", 3.0, 1.0]},
		{"t": 3.0, "tipo": "ayuda", "datos": {"ayuda": "donde_estoy"}, "pos": ["p0", 4.0, 1.0]},
		{"t": 6.0, "tipo": "premio", "datos": {"id": "llave", "nombre": "Llave dorada"}, "pos": ["p0", 5.0, 3.0]},
		{"t": 6.5, "tipo": "recompensa", "datos": {"tipo": "estrella", "nombre": "Primera estrella"}},
	]
	calculado = medidas.calcular_resumen(muestras, eventos, espacios=ESPACIOS, camino_optimo_m=6.0, pausas=[[4.0, 12.0]])
	if resumen:
		calculado.update(resumen)
	return {
		"manifiesto": {
			"formato": 1,
			"aplicacion": "EntornoLab",
			"version": "1.0.0",
			"id": ident,
			"alias": alias,
			"entorno": {"id": entorno, "nombre": "Casa de ejemplo"},
			"actividad": {"id": actividad, "nombre": "Buscar la llave", "tipo": "busqueda"},
			"modo": modo,
			"inicio": inicio,
			"fin": fin,
			"completada": completada,
			"parcial": parcial,
			"frecuencia_hz": 4,
		},
		"resumen": calculado,
		"traza": {"muestras": muestras, "eventos": eventos, "pausas": [[4.0, 12.0]], "marcas": marcas or []},
	}
