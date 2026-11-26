"""Puerta única a ``app.actividades`` desde el editor de actividades. Sin wx.

El editor no conoce ningún tipo de actividad: pregunta aquí qué tipos hay,
qué campos tiene cada uno y cómo se crea, comprueba y describe una actividad.
Cada función se busca en ``app.actividades``; la que falte (el paquete se
escribe por separado y puede no estar completo) se toma del esquema de
reserva, de modo que el panel nunca deja de abrirse por eso.
"""

from __future__ import annotations

import copy
import importlib
import logging
from collections.abc import Sequence
from typing import Any

from app.core.i18n import _
from app.ui.seguimiento import reserva_actividades as reserva

log = logging.getLogger(__name__)

NOMBRES = ("TIPOS", "campos_de", "nueva_actividad", "validar_actividad", "repartir_premios", "describir_actividad")
_avisados: set[str] = set()


def _real(nombre: str) -> Any | None:
	"""El objeto ``nombre`` de ``app.actividades`` (o de ``app.actividades.tipos``), o None si no está."""
	for modulo in ("app.actividades", "app.actividades.tipos"):
		try:
			paquete = importlib.import_module(modulo)
		except ImportError:
			continue
		except Exception:  # noqa: BLE001 - un paquete a medio escribir puede fallar de cualquier forma al importarse
			if modulo not in _avisados:
				_avisados.add(modulo)
				log.exception("No se ha podido importar %s; se usa el esquema de reserva", modulo)
			continue
		objeto = getattr(paquete, nombre, None)
		if objeto is not None:
			return objeto
	return None


def obtener(nombre: str) -> Any:
	"""``nombre`` de la API real si existe; si no, el del esquema de reserva."""
	objeto = _real(nombre)
	if objeto is None:
		if nombre not in _avisados:
			_avisados.add(nombre)
			log.warning("app.actividades no ofrece «%s»; se usa el esquema de reserva", nombre)
		return getattr(reserva, nombre)
	return objeto


def es_real(nombre: str | None = None) -> bool:
	"""True si esa función (o todas, sin argumento) viene de ``app.actividades`` y no de la reserva."""
	nombres = (nombre,) if nombre else NOMBRES
	return all(_real(uno) is not None for uno in nombres)


def tipos() -> dict[str, Any]:
	"""Tipos de actividad disponibles: id → InfoTipo."""
	return dict(obtener("TIPOS"))


def nombre_tipo(tipo: str) -> str:
	"""Nombre visible de un tipo (el id si no se conoce)."""
	info = tipos().get(tipo)
	if info is None:
		return str(tipo or _("sin tipo"))
	visible = getattr(info, "nombre_visible", None)
	return str(visible) if visible else _(info.nombre)


def descripcion_tipo(tipo: str) -> str:
	"""Descripción visible de un tipo."""
	info = tipos().get(tipo)
	if info is None:
		return ""
	visible = getattr(info, "descripcion_visible", None)
	return str(visible) if visible else _(info.descripcion)


def campos_de(tipo: str) -> list[Any]:
	"""Campos del formulario de un tipo; lista vacía si el tipo no se conoce."""
	try:
		return list(obtener("campos_de")(tipo))
	except KeyError:
		log.warning("Tipo de actividad desconocido al pedir sus campos")
		return []


def nueva_actividad(tipo: str, entorno: Any, catalogo: Any = None, **opciones: Any) -> dict[str, Any]:
	"""Actividad nueva de ese tipo.

	Si ``app.actividades`` no ofrece la función, se construye con los valores
	de serie de los campos del tipo (que sí pueden venir del paquete real).
	"""
	funcion = _real("nueva_actividad")
	if funcion is not None:
		return dict(funcion(tipo, entorno, catalogo, **opciones))
	info = tipos().get(tipo)
	datos: dict[str, Any] = {"formato": 1, "id": tipo, "tipo": tipo, "modo": getattr(info, "modo_por_defecto", "practica")}
	for campo in campos_de(tipo):
		poner_campo(datos, campo.clave, copy.deepcopy(campo.defecto))
	datos.update(opciones)
	return datos


def validar_actividad(datos: dict[str, Any], entorno: Any, catalogo: Any = None, recursos: Any = None) -> list[Any]:
	"""Avisos de la actividad (``gravedad``, ``codigo``, ``mensaje``, ``elemento_id``, ``sugerencia``).

	``recursos`` son los del paquete abierto (``contexto.recursos``): con ellos
	se comprueba también que el audio grabado de cada premio está en el
	paquete. Sin ellos (None) no se comprueba, como antes.
	"""
	funcion = obtener("validar_actividad")
	if recursos is None:
		return list(funcion(datos, entorno, catalogo))
	return list(funcion(datos, entorno, catalogo, recursos=recursos))


def repartir_premios(
	entorno: Any,
	cantidad: int,
	catalogo: Any = None,
	semilla: int | None = None,
	plantas: Sequence[str] | None = None,
	visibilidad: str = "cerca",
	dentro_de_objetos: bool = True,
) -> list[dict[str, Any]]:
	"""Premios repartidos automáticamente por el entorno."""
	return [
		dict(premio)
		for premio in obtener("repartir_premios")(
			entorno,
			cantidad,
			catalogo,
			semilla=semilla,
			plantas=list(plantas) if plantas else None,
			visibilidad=visibilidad,
			dentro_de_objetos=dentro_de_objetos,
		)
	]


def describir_actividad(datos: dict[str, Any], entorno: Any) -> str:
	"""Resumen de una actividad en una frase. Nunca lanza: una actividad rara no debe vaciar la lista."""
	try:
		return str(obtener("describir_actividad")(datos, entorno))
	except Exception:  # noqa: BLE001 - el resumen es informativo; con datos a medias puede fallar de muchas formas
		log.warning("No se ha podido describir una actividad", exc_info=True)
		return ""


def leer_campo(datos: dict[str, Any], clave: str, defecto: Any = None) -> Any:
	"""Valor de un campo; la clave puede llevar puntos («mensajes.inicio»)."""
	actual: Any = datos
	for parte in clave.split("."):
		if not isinstance(actual, dict) or parte not in actual:
			return defecto
		actual = actual[parte]
	return actual


def poner_campo(datos: dict[str, Any], clave: str, valor: Any) -> None:
	"""Escribe un campo creando los diccionarios anidados que hagan falta."""
	partes = clave.split(".")
	actual = datos
	for parte in partes[:-1]:
		siguiente = actual.get(parte)
		if not isinstance(siguiente, dict):
			siguiente = {}
			actual[parte] = siguiente
		actual = siguiente
	actual[partes[-1]] = valor
