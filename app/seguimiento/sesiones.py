"""Sesiones guardadas en la base: alta desde el documento de sesión, consulta, notas y marcas.

El documento de sesión es el contenido de ``data/sessions/<id>.json.gz`` que
escribe la grabadora (ver ``grabadora.py``). Aquí se valida —llega de otro
proceso y quizá de otro ordenador, así que no se confía en él— y se reparte
en la tabla ``sesiones`` (resumen en JSON, traza comprimida) y en ``marcas``
(las notas del profesional, cifradas y fuera de la traza).
"""

from __future__ import annotations

import json
import logging
import re
import sqlite3
import zlib
from collections.abc import Mapping
from typing import Any

from app.core.i18n import _
from app.seguimiento.base import MODOS, BaseSeguimiento, ErrorDatos

log = logging.getLogger(__name__)

FORMATO_SESION = 1
PATRON_ID = re.compile(r"^[0-9a-f]{32}$")
# Una traza descomprimida mayor que esto no es una sesión real (8 horas a 4 Hz son unos 6 MB).
TRAZA_MAXIMA = 64 * 1024 * 1024

_COLUMNAS = (
	"id, alumno_id, entorno_id, entorno_nombre, actividad_id, actividad_nombre, actividad_tipo, modo, "
	"inicio, fin, tiempo_activo, tiempo_pausa, completada, parcial, resumen, notas"
)


def _texto(valor: Any, maximo: int = 200) -> str:
	return str(valor)[:maximo] if isinstance(valor, (str, int, float)) and not isinstance(valor, bool) else ""


def validar_documento(documento: Any) -> dict[str, Any]:
	"""Comprueba la forma de un documento de sesión y devuelve sus partes normalizadas.

	Lanza ``ErrorDatos`` con un motivo legible. Tolera campos de más (otra
	versión del reproductor) pero no tipos equivocados en los que se usan.
	"""
	if not isinstance(documento, Mapping):
		raise ErrorDatos(_("El fichero de sesión no tiene el formato esperado."))
	manifiesto = documento.get("manifiesto")
	if not isinstance(manifiesto, Mapping):
		raise ErrorDatos(_("Al fichero de sesión le falta el manifiesto."))
	formato = manifiesto.get("formato")
	if not isinstance(formato, int) or isinstance(formato, bool) or formato < 1:
		raise ErrorDatos(_("El fichero de sesión no indica su formato."))
	if formato > FORMATO_SESION:
		raise ErrorDatos(_("La sesión se grabó con una versión más nueva de EntornoLab."))
	ident = manifiesto.get("id")
	if not isinstance(ident, str) or not PATRON_ID.match(ident):
		raise ErrorDatos(_("El identificador de la sesión no es válido."))
	alias = manifiesto.get("alias")
	if not isinstance(alias, str) or not alias.strip():
		raise ErrorDatos(_("La sesión no indica el alias del alumno."))
	modo = manifiesto.get("modo", "juego")
	if modo not in MODOS:
		raise ErrorDatos(_("El modo de la sesión no es válido."))
	inicio = manifiesto.get("inicio")
	fin = manifiesto.get("fin")
	if not isinstance(inicio, str) or not isinstance(fin, str) or not inicio or not fin:
		raise ErrorDatos(_("La sesión no indica cuándo empezó y terminó."))
	entorno = manifiesto.get("entorno") if isinstance(manifiesto.get("entorno"), Mapping) else {}
	actividad = manifiesto.get("actividad") if isinstance(manifiesto.get("actividad"), Mapping) else {}
	resumen = documento.get("resumen")
	if not isinstance(resumen, Mapping):
		raise ErrorDatos(_("Al fichero de sesión le falta el resumen."))
	traza = documento.get("traza")
	if not isinstance(traza, Mapping):
		raise ErrorDatos(_("Al fichero de sesión le falta la traza."))
	for clave in ("muestras", "eventos"):
		if not isinstance(traza.get(clave, []), list):
			raise ErrorDatos(_("La traza de la sesión no es válida."))

	def numero(valor: Any) -> float:
		return float(valor) if isinstance(valor, (int, float)) and not isinstance(valor, bool) else 0.0

	return {
		"id": ident,
		"alias": alias.strip(),
		"entorno_id": _texto(entorno.get("id", "")),
		"entorno_nombre": _texto(entorno.get("nombre", "")),
		"actividad_id": _texto(actividad.get("id", "")),
		"actividad_nombre": _texto(actividad.get("nombre", "")),
		"actividad_tipo": _texto(actividad.get("tipo", "")),
		"modo": modo,
		"inicio": inicio[:40],
		"fin": fin[:40],
		"tiempo_activo": numero(resumen.get("tiempo_activo_s")),
		"tiempo_pausa": numero(resumen.get("tiempo_pausa_s")),
		"completada": bool(manifiesto.get("completada", False)),
		"parcial": bool(manifiesto.get("parcial", False)),
		"resumen": dict(resumen),
		"traza": dict(traza),
	}


def _separar_marcas(traza: dict[str, Any]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
	"""Saca de la traza el texto de las marcas del profesional.

	El texto de una marca es una observación sobre el alumno: se guarda
	cifrado en su tabla y en la traza solo queda el instante y el lugar.
	"""
	marcas: list[dict[str, Any]] = []
	sin_texto: list[dict[str, Any]] = []
	for marca in traza.get("marcas") or []:
		if not isinstance(marca, Mapping):
			continue
		ficha = {
			"t": float(marca["t"]) if isinstance(marca.get("t"), (int, float)) else 0.0,
			"planta": _texto(marca.get("planta", "")),
			"x": float(marca["x"]) if isinstance(marca.get("x"), (int, float)) else None,
			"y": float(marca["y"]) if isinstance(marca.get("y"), (int, float)) else None,
			"texto": _texto(marca.get("texto", ""), 2000),
		}
		marcas.append(ficha)
		sin_texto.append({clave: valor for clave, valor in ficha.items() if clave != "texto"})
	limpia = dict(traza)
	limpia["marcas"] = sin_texto
	return limpia, marcas


def guardar_sesion(base: BaseSeguimiento, alumno_id: int, documento: Any) -> str:
	"""Guarda en la base un documento de sesión. Idempotente.

	Devuelve ``"nueva"``, ``"repetida"`` (ya estaba: no se toca, para no
	pisar las notas del profesional) o ``"actualizada"`` (lo que había era un
	guardado parcial y ahora llega la sesión terminada).
	"""
	partes = validar_documento(documento)
	traza, marcas = _separar_marcas(partes["traza"])
	comprimida = zlib.compress(json.dumps(traza, ensure_ascii=False, separators=(",", ":")).encode("utf-8"), 9)
	resumen = json.dumps(partes["resumen"], ensure_ascii=False, separators=(",", ":"))
	valores = (
		alumno_id,
		partes["entorno_id"],
		partes["entorno_nombre"],
		partes["actividad_id"],
		partes["actividad_nombre"],
		partes["actividad_tipo"],
		partes["modo"],
		partes["inicio"],
		partes["fin"],
		partes["tiempo_activo"],
		partes["tiempo_pausa"],
		int(partes["completada"]),
		int(partes["parcial"]),
		resumen,
		comprimida,
	)
	with base.transaccion() as tx:
		anterior = tx.execute("SELECT parcial FROM sesiones WHERE id = ?", (partes["id"],)).fetchone()
		if anterior is not None and (not anterior["parcial"] or partes["parcial"]):
			return "repetida"
		if anterior is not None:
			tx.execute(
				"UPDATE sesiones SET alumno_id = ?, entorno_id = ?, entorno_nombre = ?, actividad_id = ?, actividad_nombre = ?, "
				"actividad_tipo = ?, modo = ?, inicio = ?, fin = ?, tiempo_activo = ?, tiempo_pausa = ?, completada = ?, "
				"parcial = ?, resumen = ?, traza = ? WHERE id = ?",
				(*valores, partes["id"]),
			)
			tx.execute("DELETE FROM marcas WHERE sesion_id = ?", (partes["id"],))
			estado = "actualizada"
		else:
			try:
				tx.execute(
					"INSERT INTO sesiones (alumno_id, entorno_id, entorno_nombre, actividad_id, actividad_nombre, actividad_tipo, "
					"modo, inicio, fin, tiempo_activo, tiempo_pausa, completada, parcial, resumen, traza, id) "
					"VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
					(*valores, partes["id"]),
				)
			except sqlite3.IntegrityError as error:
				raise ErrorDatos(_("El alumno de la sesión no existe.")) from error
			estado = "nueva"
		for marca in marcas:
			tx.execute(
				"INSERT INTO marcas (sesion_id, t, planta, x, y, texto) VALUES (?, ?, ?, ?, ?, ?)",
				(partes["id"], marca["t"], marca["planta"], marca["x"], marca["y"], base.cifrar_texto(marca["texto"])),
			)
	return estado


def _a_dict(base: BaseSeguimiento, fila: sqlite3.Row) -> dict[str, Any]:
	try:
		resumen = json.loads(fila["resumen"])
	except ValueError:
		log.error("El resumen de una sesión guardada no es JSON válido")
		resumen = {}
	return {
		"id": fila["id"],
		"alumno_id": fila["alumno_id"],
		"entorno_id": fila["entorno_id"],
		"entorno_nombre": fila["entorno_nombre"],
		"actividad_id": fila["actividad_id"],
		"actividad_nombre": fila["actividad_nombre"],
		"actividad_tipo": fila["actividad_tipo"],
		"modo": fila["modo"],
		"inicio": fila["inicio"],
		"fin": fila["fin"],
		"tiempo_activo": fila["tiempo_activo"],
		"tiempo_pausa": fila["tiempo_pausa"],
		"completada": bool(fila["completada"]),
		"parcial": bool(fila["parcial"]),
		"resumen": resumen if isinstance(resumen, dict) else {},
		"notas": base.descifrar_texto(fila["notas"]) or "",
	}


def obtener(base: BaseSeguimiento, sesion_id: str, con_traza: bool = False) -> dict[str, Any] | None:
	"""Una sesión como diccionario (es lo que reciben los informes), o ``None``.

	Con ``con_traza`` añade ``"traza"`` (descomprimida) y ``"marcas"``.
	"""
	fila = base.consultar_uno(f"SELECT {_COLUMNAS} FROM sesiones WHERE id = ?", (sesion_id,))
	if fila is None:
		return None
	sesion = _a_dict(base, fila)
	if con_traza:
		sesion["traza"] = traza(base, sesion_id)
		sesion["marcas"] = marcas(base, sesion_id)
	return sesion


def listar(
	base: BaseSeguimiento,
	alumno_id: int | None = None,
	*,
	entorno_id: str | None = None,
	actividad_id: str | None = None,
	modo: str | None = None,
	desde: str | None = None,
	hasta: str | None = None,
	incluir_parciales: bool = True,
) -> list[dict[str, Any]]:
	"""Sesiones que cumplen los filtros, de la más antigua a la más reciente (sin traza)."""
	condiciones: list[str] = []
	parametros: list[Any] = []
	for columna, valor in (("alumno_id", alumno_id), ("entorno_id", entorno_id), ("actividad_id", actividad_id), ("modo", modo)):
		if valor is not None:
			condiciones.append(f"{columna} = ?")
			parametros.append(valor)
	if desde is not None:
		condiciones.append("inicio >= ?")
		parametros.append(desde)
	if hasta is not None:
		condiciones.append("inicio <= ?")
		parametros.append(hasta)
	if not incluir_parciales:
		condiciones.append("parcial = 0")
	donde = (" WHERE " + " AND ".join(condiciones)) if condiciones else ""
	filas = base.consultar(f"SELECT {_COLUMNAS} FROM sesiones{donde} ORDER BY inicio, id", parametros)
	return [_a_dict(base, fila) for fila in filas]


def traza(base: BaseSeguimiento, sesion_id: str) -> dict[str, Any]:
	"""Traza descomprimida de una sesión: ``{"muestras", "eventos", "pausas", "marcas"}``."""
	valor = base.valor("SELECT traza FROM sesiones WHERE id = ?", (sesion_id,))
	if valor is None:
		return {"muestras": [], "eventos": [], "pausas": [], "marcas": []}
	descompresor = zlib.decompressobj()
	try:
		datos = descompresor.decompress(bytes(valor), TRAZA_MAXIMA)
		if descompresor.unconsumed_tail:
			raise ErrorDatos(_("La traza de la sesión es demasiado grande."))
		contenido = json.loads(datos.decode("utf-8"))
	except (zlib.error, ValueError) as error:
		raise ErrorDatos(_("La traza de la sesión está dañada.")) from error
	return contenido if isinstance(contenido, dict) else {"muestras": [], "eventos": [], "pausas": [], "marcas": []}


def anotar(base: BaseSeguimiento, sesion_id: str, notas: str) -> bool:
	"""Guarda (cifradas) las notas del profesional sobre la sesión."""
	return base.ejecutar("UPDATE sesiones SET notas = ? WHERE id = ?", (base.cifrar_texto(notas), sesion_id)) > 0


def borrar(base: BaseSeguimiento, sesion_id: str) -> bool:
	"""Borra una sesión con sus marcas. Las recompensas ganadas en ella se conservan sin sesión."""
	return base.ejecutar("DELETE FROM sesiones WHERE id = ?", (sesion_id,)) > 0


def marcas(base: BaseSeguimiento, sesion_id: str) -> list[dict[str, Any]]:
	"""Marcas del profesional durante la sesión, por orden de tiempo."""
	filas = base.consultar("SELECT id, t, planta, x, y, texto FROM marcas WHERE sesion_id = ? ORDER BY t, id", (sesion_id,))
	return [
		{"id": f["id"], "t": f["t"], "planta": f["planta"], "x": f["x"], "y": f["y"], "texto": base.descifrar_texto(f["texto"]) or ""}
		for f in filas
	]


def anadir_marca(
	base: BaseSeguimiento,
	sesion_id: str,
	t: float,
	texto: str,
	*,
	planta: str = "",
	x: float | None = None,
	y: float | None = None,
) -> int:
	"""Añade una marca a una sesión ya guardada (el profesional la anota al repasarla)."""
	try:
		return base.insertar(
			"INSERT INTO marcas (sesion_id, t, planta, x, y, texto) VALUES (?, ?, ?, ?, ?, ?)",
			(sesion_id, float(t), planta, x, y, base.cifrar_texto(texto)),
		)
	except sqlite3.IntegrityError as error:
		raise ErrorDatos(_("La sesión no existe.")) from error
