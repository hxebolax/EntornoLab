"""Recompensas: de un resultado a estrellas, medallas y objetos de la colección.

Las estrellas premian cosas distintas (completar, usar pocas ayudas, tomar
un atajo o la salida óptima, no chocar, explorarlo todo), para que haya más
de una manera de hacerlo bien y la de «seguir la baliza» no sea ninguna.
Los nombres cambian con el estilo de presentación; lo que se premia, no.

Un examen no da recompensas: mide, no celebra. Y ninguna recompensa dice
nada de la competencia del alumno en el lugar real.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.i18n import N_, _

TIPOS_RECOMPENSA: tuple[str, ...] = ("estrella", "medalla", "objeto")

_INDICE_ESTILO = {"infantil": 0, "juvenil": 1, "adulto": 2}

# Motivo → nombre de la estrella en (infantil, juvenil, adulto).
_ESTRELLAS: dict[str, tuple[str, str, str]] = {
	"completar": (N_("Estrella de ¡lo conseguí!"), N_("Estrella de misión cumplida"), N_("Estrella de actividad completada")),
	"pocas_ayudas": (N_("Estrella de yo solo"), N_("Estrella sin comodines"), N_("Estrella de pocas ayudas")),
	"atajo": (N_("Estrella del atajo"), N_("Estrella del camino más corto"), N_("Estrella de ruta eficiente")),
	"salida_optima": (N_("Estrella de la puerta más cercana"), N_("Estrella de la mejor salida"), N_("Estrella de salida más corta")),
	"sin_choques": (N_("Estrella de pasos suaves"), N_("Estrella sin un solo choque"), N_("Estrella sin choques")),
	"exploracion": (N_("Estrella de gran explorador"), N_("Estrella de mapa completo"), N_("Estrella de exploración completa")),
	"seguridad": (N_("Estrella de cruzar con cuidado"), N_("Estrella de cruces seguros"), N_("Estrella de cruces sin incidentes")),
}

# Clave → nombre de la medalla en (infantil, juvenil, adulto).
_MEDALLAS: dict[str, tuple[str, str, str]] = {
	"pleno": (N_("Medalla de oro"), N_("Medalla de pleno"), N_("Medalla de actividad redonda")),
	"salidas": (N_("Medalla de rey de las salidas"), N_("Medalla de evacuación perfecta"), N_("Medalla de salidas óptimas")),
	"explorador": (N_("Medalla de gran explorador"), N_("Medalla de cartógrafo"), N_("Medalla de entorno recorrido entero")),
	"nivel": (N_("Medalla de subir de nivel"), N_("Medalla de nivel superado"), N_("Medalla de nivel superado")),
}


def _por_estilo(tabla: Mapping[str, tuple[str, str, str]], clave: str, estilo: str) -> str:
	textos = tabla.get(clave)
	if textos is None:
		return clave
	return _(textos[_INDICE_ESTILO.get(estilo, 2)])


def nombre_estrella(motivo: str, estilo: str = "adulto") -> str:
	"""Nombre de la estrella que se gana por un motivo, en el estilo del alumno."""
	return _por_estilo(_ESTRELLAS, motivo, estilo)


def nombre_medalla(clave: str, estilo: str = "adulto") -> str:
	"""Nombre de una medalla, en el estilo del alumno."""
	return _por_estilo(_MEDALLAS, clave, estilo)


def medallas_de(resultado: Mapping[str, Any]) -> list[str]:
	"""Claves de las medallas que merece un resultado (ninguna en un examen o sin completar)."""
	actividad = resultado.get("actividad") or {}
	if actividad.get("modo") == "examen" or not resultado.get("completada"):
		return []
	claves: list[str] = []
	motivos = list(resultado.get("estrellas_motivos") or [])
	posibles = list(resultado.get("estrellas_posibles") or [])
	if posibles and len(posibles) >= 2 and set(posibles) <= set(motivos):
		claves.append("pleno")
	maximos = resultado.get("puntos_maximos") or 0
	if actividad.get("tipo") == "sacar_tesoros" and maximos and resultado.get("puntos") == maximos:
		claves.append("salidas")
	if actividad.get("tipo") == "explorador" and (resultado.get("exploracion") or 0.0) >= 0.999:
		claves.append("explorador")
	if resultado.get("nivel_superado") and resultado.get("nivel_siguiente") != resultado.get("nivel"):
		claves.append("nivel")
	return claves


def desbloqueos_de(resultado: Mapping[str, Any], estrellas_ahora: int) -> list[str]:
	"""Nombres de las recompensas del profesional que se desbloquean con las estrellas de esta sesión.

	Cada regla es ``{"estrellas": 5, "nombre": "la casa del árbol"}``. Se
	desbloquea cuando el total (las de sesiones anteriores, que llegan en
	``estrellas_previas``, más las de ahora) cruza el umbral: una sola vez.
	"""
	try:
		previas = max(0, int(resultado.get("estrellas_previas") or 0))
	except TypeError, ValueError:
		previas = 0
	nombres: list[str] = []
	for regla in resultado.get("desbloqueos") or []:
		if not isinstance(regla, Mapping):
			continue
		nombre = str(regla.get("nombre") or "").strip()
		try:
			umbral = int(regla.get("estrellas") or 0)
		except TypeError, ValueError:
			continue
		if nombre and umbral > 0 and previas < umbral <= previas + estrellas_ahora:
			nombres.append(nombre)
	return nombres


def calcular(resultado: dict, estilo: str) -> list[dict]:
	"""Recompensas de un resultado: ``[{"tipo": "estrella" | "medalla" | "objeto", "nombre": ...}]``.

	``resultado`` es el que devuelve ``Actividad.resultado`` (basta con sus
	claves ``actividad``, ``completada``, ``estrellas_motivos``,
	``estrellas_posibles``, ``coleccion``, ``desbloqueos`` y
	``estrellas_previas``). El orden es estable: estrellas, medallas, objetos
	encontrados y, al final, lo desbloqueado.
	"""
	if not isinstance(resultado, Mapping):
		return []
	actividad = resultado.get("actividad") or {}
	if actividad.get("modo") == "examen":
		return []
	recompensas: list[dict] = []
	motivos = [str(m) for m in resultado.get("estrellas_motivos") or []]
	for motivo in motivos:
		recompensas.append({"tipo": "estrella", "nombre": nombre_estrella(motivo, estilo), "motivo": motivo})
	for clave in medallas_de(resultado):
		recompensas.append({"tipo": "medalla", "nombre": nombre_medalla(clave, estilo), "motivo": clave})
	vistos: set[str] = set()
	for nombre in resultado.get("coleccion") or []:
		texto = str(nombre or "").strip()
		if texto and texto not in vistos:
			vistos.add(texto)
			recompensas.append({"tipo": "objeto", "nombre": texto, "motivo": "encontrado"})
	for nombre in desbloqueos_de(resultado, len(motivos)):
		recompensas.append({"tipo": "objeto", "nombre": nombre, "motivo": "desbloqueo"})
	return recompensas
