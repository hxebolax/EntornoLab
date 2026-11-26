"""Recompensas del alumno: estrellas, medallas y objetos de su colección.

Las recompensas motivan, pero no son una medida: por eso viven en su tabla y
no entran en los informes de rendimiento. Se conservan aunque caduque la
sesión en la que se ganaron (la colección es del alumno).
"""

from __future__ import annotations

import sqlite3
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from app.core.i18n import _
from app.seguimiento.base import TIPOS_RECOMPENSA, BaseSeguimiento, ErrorDatos, ahora_iso


@dataclass(frozen=True)
class Recompensa:
	"""Una recompensa ganada."""

	id: int
	alumno_id: int
	tipo: str
	nombre: str
	fecha: str
	sesion_id: str | None


def registrar(
	base: BaseSeguimiento,
	alumno_id: int,
	tipo: str,
	nombre: str = "",
	*,
	sesion_id: str | None = None,
	fecha: str | None = None,
) -> int:
	"""Apunta una recompensa y devuelve su id."""
	if tipo not in TIPOS_RECOMPENSA:
		raise ErrorDatos(_("Tipo de recompensa desconocido: {tipo}").format(tipo=tipo))
	try:
		return base.insertar(
			"INSERT INTO recompensas (alumno_id, tipo, nombre, fecha, sesion_id) VALUES (?, ?, ?, ?, ?)",
			(alumno_id, tipo, nombre.strip()[:200], fecha or ahora_iso(), sesion_id),
		)
	except sqlite3.IntegrityError as error:
		raise ErrorDatos(_("El alumno o la sesión de la recompensa no existen.")) from error


def registrar_de_sesion(base: BaseSeguimiento, alumno_id: int, sesion_id: str, resumen: Mapping[str, Any], fecha: str | None = None) -> int:
	"""Apunta las recompensas que figuran en el resumen de una sesión. Idempotente.

	Antes borra las que ya hubiera de esa sesión: incorporar dos veces el
	mismo fichero no duplica estrellas.
	"""
	ganadas = resumen.get("recompensas") or []
	with base.transaccion() as tx:
		tx.execute("DELETE FROM recompensas WHERE sesion_id = ?", (sesion_id,))
		cuenta = 0
		for ganada in ganadas:
			if not isinstance(ganada, Mapping) or ganada.get("tipo") not in TIPOS_RECOMPENSA:
				continue
			tx.execute(
				"INSERT INTO recompensas (alumno_id, tipo, nombre, fecha, sesion_id) VALUES (?, ?, ?, ?, ?)",
				(alumno_id, ganada["tipo"], str(ganada.get("nombre", ""))[:200], fecha or ahora_iso(), sesion_id),
			)
			cuenta += 1
	return cuenta


def de_alumno(base: BaseSeguimiento, alumno_id: int, tipo: str | None = None) -> list[Recompensa]:
	"""Recompensas de un alumno, de la más antigua a la más reciente."""
	sql = "SELECT id, alumno_id, tipo, nombre, fecha, sesion_id FROM recompensas WHERE alumno_id = ?"
	parametros: list[Any] = [alumno_id]
	if tipo is not None:
		sql += " AND tipo = ?"
		parametros.append(tipo)
	filas = base.consultar(sql + " ORDER BY fecha, id", parametros)
	return [Recompensa(f["id"], f["alumno_id"], f["tipo"], f["nombre"], f["fecha"], f["sesion_id"]) for f in filas]


def coleccion(base: BaseSeguimiento, alumno_id: int) -> dict[str, Any]:
	"""Lo que el alumno tiene: número de estrellas, medallas y objetos distintos.

	Los objetos repetidos se cuentan (``veces``) en lugar de repetirse en la
	lista: en el menú hablado del alumno se lee «llave dorada, 3 veces».
	"""
	todas = de_alumno(base, alumno_id)
	medallas = [{"nombre": r.nombre, "fecha": r.fecha} for r in todas if r.tipo == "medalla"]
	objetos: dict[str, dict[str, Any]] = {}
	for recompensa in todas:
		if recompensa.tipo != "objeto":
			continue
		ficha = objetos.setdefault(recompensa.nombre, {"nombre": recompensa.nombre, "veces": 0, "primera_fecha": recompensa.fecha})
		ficha["veces"] += 1
	return {
		"estrellas": sum(1 for r in todas if r.tipo == "estrella"),
		"medallas": medallas,
		"objetos": list(objetos.values()),
	}


def borrar(base: BaseSeguimiento, recompensa_id: int) -> bool:
	"""Quita una recompensa apuntada por error."""
	return base.ejecutar("DELETE FROM recompensas WHERE id = ?", (recompensa_id,)) > 0
