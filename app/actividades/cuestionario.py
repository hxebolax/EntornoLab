"""Preguntas breves y opcionales al terminar: esfuerzo, confianza y disfrute.

Son DATOS: el reproductor las presenta como un menú hablado y apunta las
respuestas con un registro ``valoracion`` (``Actividad.valorar`` lo hace). No
hay respuestas buenas ni malas y cualquiera se puede saltar; sirven para que
el profesional sepa cómo lo ha vivido el alumno, no para puntuarle.

Las tres preguntas son las mismas en los tres estilos; cambia la redacción.
La escala va de 1 a 5 y cada valor tiene su texto, para no obligar a nadie a
traducir números en sensaciones.
"""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.i18n import N_, _

ESCALA_MINIMA = 1
ESCALA_MAXIMA = 5

_INDICE_ESTILO = {"infantil": 0, "juvenil": 1, "adulto": 2}

# id → (pregunta infantil, juvenil, adulto) y textos de la escala de 1 a 5.
_PREGUNTAS: tuple[tuple[str, tuple[str, str, str], tuple[str, str, str, str, str]], ...] = (
	(
		"esfuerzo",
		(N_("¿Te ha costado mucho?"), N_("¿Cuánto esfuerzo te ha pedido?"), N_("¿Cuánto esfuerzo te ha supuesto la actividad?")),
		(N_("Nada"), N_("Poco"), N_("Regular"), N_("Bastante"), N_("Mucho")),
	),
	(
		"confianza",
		(
			N_("¿Sabrías ir tú solo por este sitio?"),
			N_("¿Te ves capaz de moverte por este lugar de verdad?"),
			N_("¿Qué confianza tienes en orientarte en este lugar real?"),
		),
		(N_("Ninguna"), N_("Poca"), N_("Regular"), N_("Bastante"), N_("Mucha")),
	),
	(
		"disfrute",
		(N_("¿Te lo has pasado bien?"), N_("¿Te ha gustado?"), N_("¿Te ha resultado agradable la actividad?")),
		(N_("Nada"), N_("Poco"), N_("Regular"), N_("Bastante"), N_("Mucho")),
	),
)

IDS_PREGUNTAS: tuple[str, ...] = tuple(pregunta[0] for pregunta in _PREGUNTAS)


def preguntas(estilo: str = "adulto") -> list[dict[str, Any]]:
	"""Las preguntas, redactadas para un estilo: ``[{"id", "texto", "opciones": [{"valor", "texto"}], "opcional": True}]``."""
	indice = _INDICE_ESTILO.get(estilo, 2)
	lista: list[dict[str, Any]] = []
	for ident, textos, escala in _PREGUNTAS:
		lista.append(
			{
				"id": ident,
				"texto": _(textos[indice]),
				"opciones": [{"valor": valor, "texto": _(nombre)} for valor, nombre in enumerate(escala, start=ESCALA_MINIMA)],
				"opcional": True,
			}
		)
	return lista


def presentacion(estilo: str = "adulto") -> str:
	"""Frase con la que se ofrecen las preguntas, dejando claro que son opcionales."""
	textos = (
		N_("Tres preguntas cortitas, si quieres."),
		N_("Tres preguntas rápidas; puedes saltarte las que quieras."),
		N_("Para terminar, tres preguntas breves y opcionales."),
	)
	return _(textos[_INDICE_ESTILO.get(estilo, 2)])


def normalizar_respuestas(respuestas: Any) -> dict[str, int | None]:
	"""Deja las respuestas en ``{"esfuerzo": 1..5 | None, "confianza": …, "disfrute": …}``.

	Lo que falta, lo que no es un número o lo que se sale de la escala queda
	como None (pregunta saltada): unas respuestas mal formadas no deben
	estropear el guardado de la sesión.
	"""
	limpias: dict[str, int | None] = dict.fromkeys(IDS_PREGUNTAS)
	if not isinstance(respuestas, Mapping):
		return limpias
	for ident in IDS_PREGUNTAS:
		valor = respuestas.get(ident)
		if isinstance(valor, bool) or not isinstance(valor, (int, float)):
			continue
		if ESCALA_MINIMA <= int(valor) <= ESCALA_MAXIMA:
			limpias[ident] = int(valor)
	return limpias
