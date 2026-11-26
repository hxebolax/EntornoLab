"""Cuaderno de evaluación real: lo que el profesional anota en el lugar físico.

Es la otra mitad de la comparación «simulador frente a realidad»: rutas
hechas con su resultado, nivel de ayuda, tipo de recorrido, ayudas de
movilidad y observaciones. El programa solo guarda y muestra lo anotado; no
puntúa ni interpreta la evaluación.
"""

from __future__ import annotations

import json
import logging
import sqlite3
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.core.i18n import N_, _
from app.seguimiento.base import BaseSeguimiento, ErrorDatos

log = logging.getLogger(__name__)

# Valores cerrados con su texto (se traduce con _() al mostrarlo).
RESULTADOS_RUTA: dict[str, str] = {
	"conseguida": N_("Conseguida sin ayuda"),
	"con_ayuda": N_("Conseguida con ayuda"),
	"no_conseguida": N_("No conseguida"),
	"no_intentada": N_("No intentada"),
}
NIVELES_AYUDA: dict[str, str] = {
	"": N_("Sin indicar"),
	"independiente": N_("Independiente"),
	"supervision": N_("Con supervisión"),
	"indicacion_verbal": N_("Con indicaciones verbales"),
	"ayuda_fisica": N_("Con ayuda física"),
}
TIPOS_RECORRIDO: dict[str, str] = {
	"": N_("Sin indicar"),
	"entrenado": N_("Recorrido entrenado en el simulador"),
	"no_entrenado": N_("Recorrido no entrenado"),
	"inverso": N_("Recorrido inverso"),
	"alternativo": N_("Recorrido alternativo"),
	"otro": N_("Otro"),
}


@dataclass
class EvaluacionReal:
	"""Una evaluación en el lugar real."""

	id: int
	alumno_id: int
	fecha: str
	lugar: str = ""
	entorno_id: str = ""
	entorno_nombre: str = ""
	rutas: list[dict[str, str]] = field(default_factory=list)
	nivel_ayuda: str = ""
	tipo_recorrido: str = ""
	ayudas_movilidad: list[str] = field(default_factory=list)
	observaciones: str = ""
	dias_desde_entrenamiento: int | None = None


def _validar_fecha(fecha: str) -> str:
	try:
		return date.fromisoformat(fecha).isoformat()
	except (TypeError, ValueError) as error:
		raise ErrorDatos(_("La fecha debe tener la forma AAAA-MM-DD.")) from error


def _validar_rutas(rutas: Sequence[Mapping[str, Any]]) -> list[dict[str, str]]:
	limpias: list[dict[str, str]] = []
	for ruta in rutas:
		nombre = str(ruta.get("nombre", "")).strip()
		resultado = str(ruta.get("resultado", ""))
		if not nombre:
			raise ErrorDatos(_("Cada ruta necesita un nombre."))
		if resultado not in RESULTADOS_RUTA:
			raise ErrorDatos(_("Resultado de ruta desconocido: {resultado}").format(resultado=resultado))
		limpias.append({"nombre": nombre[:200], "resultado": resultado, "notas": str(ruta.get("notas", ""))[:500]})
	return limpias


def dias_desde_ultima_sesion(base: BaseSeguimiento, alumno_id: int, fecha: str, entorno_id: str = "") -> int | None:
	"""Días entre la última sesión en el simulador (de ese entorno, si se indica) y ``fecha``.

	Sirve para anotar si lo aprendido se mantiene semanas después. ``None``
	si no hay ninguna sesión anterior.
	"""
	sql = "SELECT MAX(inicio) FROM sesiones WHERE alumno_id = ? AND substr(inicio, 1, 10) <= ?"
	parametros: list[Any] = [alumno_id, fecha]
	if entorno_id:
		sql += " AND entorno_id = ?"
		parametros.append(entorno_id)
	ultima = base.valor(sql, parametros)
	if not ultima:
		return None
	try:
		return (date.fromisoformat(fecha) - date.fromisoformat(str(ultima)[:10])).days
	except ValueError:
		log.warning("Fecha de sesión con formato inesperado en la base")
		return None


def anotar(
	base: BaseSeguimiento,
	alumno_id: int,
	*,
	fecha: str,
	lugar: str = "",
	entorno_id: str = "",
	entorno_nombre: str = "",
	rutas: Sequence[Mapping[str, Any]] = (),
	nivel_ayuda: str = "",
	tipo_recorrido: str = "",
	ayudas_movilidad: Sequence[str] = (),
	observaciones: str = "",
	dias_desde_entrenamiento: int | None = None,
) -> int:
	"""Guarda una evaluación real y devuelve su id.

	Si no se indican los días desde el último entrenamiento, se calculan con
	las sesiones guardadas del alumno en ese entorno.
	"""
	fecha = _validar_fecha(fecha)
	if nivel_ayuda not in NIVELES_AYUDA:
		raise ErrorDatos(_("Nivel de ayuda desconocido: {valor}").format(valor=nivel_ayuda))
	if tipo_recorrido not in TIPOS_RECORRIDO:
		raise ErrorDatos(_("Tipo de recorrido desconocido: {valor}").format(valor=tipo_recorrido))
	if dias_desde_entrenamiento is None:
		dias_desde_entrenamiento = dias_desde_ultima_sesion(base, alumno_id, fecha, entorno_id)
	try:
		return base.insertar(
			"INSERT INTO evaluaciones_reales (alumno_id, entorno_id, entorno_nombre, fecha, lugar, rutas, nivel_ayuda, "
			"tipo_recorrido, ayudas_movilidad, observaciones, dias_desde_entrenamiento) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
			(
				alumno_id,
				entorno_id,
				entorno_nombre,
				fecha,
				lugar.strip()[:200],
				json.dumps(_validar_rutas(rutas), ensure_ascii=False),
				nivel_ayuda,
				tipo_recorrido,
				json.dumps([str(a).strip()[:100] for a in ayudas_movilidad if str(a).strip()], ensure_ascii=False),
				base.cifrar_texto(observaciones),
				dias_desde_entrenamiento,
			),
		)
	except sqlite3.IntegrityError as error:
		raise ErrorDatos(_("El alumno de la evaluación no existe.")) from error


def _de_fila(base: BaseSeguimiento, fila: sqlite3.Row) -> EvaluacionReal:
	def lista(texto: str) -> list[Any]:
		try:
			valor = json.loads(texto)
		except ValueError:
			log.error("Una evaluación real guardada tiene un JSON no válido")
			return []
		return valor if isinstance(valor, list) else []

	return EvaluacionReal(
		id=fila["id"],
		alumno_id=fila["alumno_id"],
		fecha=fila["fecha"],
		lugar=fila["lugar"],
		entorno_id=fila["entorno_id"],
		entorno_nombre=fila["entorno_nombre"],
		rutas=lista(fila["rutas"]),
		nivel_ayuda=fila["nivel_ayuda"],
		tipo_recorrido=fila["tipo_recorrido"],
		ayudas_movilidad=lista(fila["ayudas_movilidad"]),
		observaciones=base.descifrar_texto(fila["observaciones"]) or "",
		dias_desde_entrenamiento=fila["dias_desde_entrenamiento"],
	)


def listar(base: BaseSeguimiento, alumno_id: int, entorno_id: str | None = None) -> list[EvaluacionReal]:
	"""Evaluaciones reales de un alumno, por fecha."""
	sql = "SELECT * FROM evaluaciones_reales WHERE alumno_id = ?"
	parametros: list[Any] = [alumno_id]
	if entorno_id is not None:
		sql += " AND entorno_id = ?"
		parametros.append(entorno_id)
	return [_de_fila(base, fila) for fila in base.consultar(sql + " ORDER BY fecha, id", parametros)]


def obtener(base: BaseSeguimiento, evaluacion_id: int) -> EvaluacionReal | None:
	"""Una evaluación por su id."""
	fila = base.consultar_uno("SELECT * FROM evaluaciones_reales WHERE id = ?", (evaluacion_id,))
	return None if fila is None else _de_fila(base, fila)


def borrar(base: BaseSeguimiento, evaluacion_id: int) -> bool:
	"""Borra una evaluación real."""
	return base.ejecutar("DELETE FROM evaluaciones_reales WHERE id = ?", (evaluacion_id,)) > 0
