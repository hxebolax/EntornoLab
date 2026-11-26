"""Frases del reproductor según el estilo del alumno: infantil, juvenil o adulto.

El contenido es el mismo para todos; cambia el tono. El estilo adulto es
sobrio a propósito: un adulto que prepara una visita real no debe sentirse
tratado como un niño (apartado 13.4 del informe). Las frases se marcan con
``N_`` porque la tabla se crea al importar, antes de elegir el idioma, y se
traducen al pedirlas.
"""

from __future__ import annotations

import logging

from app.core.i18n import N_, _, _n

log = logging.getLogger(__name__)

ESTILOS: tuple[str, ...] = ("infantil", "juvenil", "adulto")
ESTILO_DE_SERIE = "adulto"

NOMBRES_ESTILO: dict[str, str] = {"infantil": N_("Infantil"), "juvenil": N_("Juvenil"), "adulto": N_("Adulto")}

_FRASES: dict[str, dict[str, str]] = {
	"saludo": {
		"infantil": N_("¡Hola, {alias}! ¡Vamos a jugar!"),
		"juvenil": N_("Hola, {alias}. ¿Preparado para otra misión?"),
		"adulto": N_("Hola, {alias}."),
	},
	"saludo_sin_alias": {
		"infantil": N_("¡Hola! ¡Vamos a jugar!"),
		"juvenil": N_("Hola. ¿Preparado para otra misión?"),
		"adulto": N_("Bienvenido."),
	},
	"empieza_libre": {
		"infantil": N_("¡A explorar! Recorre {entorno} como quieras."),
		"juvenil": N_("Exploración libre de {entorno}. Recórrelo a tu aire."),
		"adulto": N_("Exploración libre de {entorno}."),
	},
	"pausa": {
		"infantil": N_("Juego en pausa. Descansa un poco."),
		"juvenil": N_("Pausa."),
		"adulto": N_("Pausa."),
	},
	"sigue": {
		"infantil": N_("¡Seguimos!"),
		"juvenil": N_("Seguimos."),
		"adulto": N_("Continúa."),
	},
	"completada": {
		"infantil": N_("¡Bravo! ¡Lo has conseguido!"),
		"juvenil": N_("¡Misión cumplida!"),
		"adulto": N_("Actividad completada."),
	},
	"no_completada": {
		"infantil": N_("Hoy no la has terminado, pero has aprendido mucho. ¡Otro día más!"),
		"juvenil": N_("Esta vez no la has terminado. La próxima sale."),
		"adulto": N_("Actividad sin completar."),
	},
	"mejor_marca": {
		"infantil": N_("¡Es tu mejor resultado en esta actividad!"),
		"juvenil": N_("Nueva marca personal."),
		"adulto": N_("Es tu mejor resultado en esta actividad."),
	},
	"sin_premios": {
		"infantil": N_("Todavía no tienes premios. ¡Juega una actividad y gana el primero!"),
		"juvenil": N_("Aún no tienes premios. Completa una actividad para ganar el primero."),
		"adulto": N_("Todavía no hay premios. Se consiguen al completar actividades."),
	},
	"tutorial_fin": {
		"infantil": N_("¡Genial! Ya sabes moverte, preguntar y encontrar premios. ¡A jugar!"),
		"juvenil": N_("Tutorial superado. Ya controlas lo básico."),
		"adulto": N_("Tutorial terminado. Ya conoces los controles básicos."),
	},
	"despedida": {
		"infantil": N_("¡Hasta pronto!"),
		"juvenil": N_("Hasta la próxima."),
		"adulto": N_("Hasta pronto."),
	},
}


def estilo_valido(estilo: str | None) -> str:
	"""El estilo pedido si existe; si no, el adulto (el más neutro)."""
	return estilo if estilo in ESTILOS else ESTILO_DE_SERIE


def nombre_estilo(estilo: str) -> str:
	"""Nombre visible de un estilo."""
	return _(NOMBRES_ESTILO.get(estilo, NOMBRES_ESTILO[ESTILO_DE_SERIE]))


def frase(clave: str, estilo: str | None = None, **datos: object) -> str:
	"""La frase ``clave`` en el tono del estilo, con sus datos puestos. Cadena vacía si la clave no existe."""
	variantes = _FRASES.get(clave)
	if variantes is None:
		log.warning("Frase de estilo desconocida: %s", clave)
		return ""
	texto = _(variantes.get(estilo_valido(estilo), variantes[ESTILO_DE_SERIE]))
	try:
		return texto.format(**datos)
	except KeyError, IndexError:
		log.warning("Faltan datos para la frase de estilo «%s»", clave)
		return texto


def decir_estrellas(estrellas: int, estilo: str | None = None) -> str:
	"""«Tres estrellas» dicho en el tono del estilo."""
	estrellas = max(0, int(estrellas))
	if estrellas == 0:
		return _("Sin estrellas esta vez.")
	base = _n("{n} estrella", "{n} estrellas", estrellas).format(n=estrellas)
	if estilo_valido(estilo) == "infantil":
		return _("¡Has ganado {estrellas}!").format(estrellas=base)
	return _("Has conseguido {estrellas}.").format(estrellas=base)


def duracion(segundos: float) -> str:
	"""Una duración dicha de forma natural: «2 minutos y 5 segundos»."""
	total = max(0, round(float(segundos)))
	minutos, resto = divmod(total, 60)
	texto_segundos = _n("{n} segundo", "{n} segundos", resto).format(n=resto)
	if minutos == 0:
		return texto_segundos
	texto_minutos = _n("{n} minuto", "{n} minutos", minutos).format(n=minutos)
	if resto == 0:
		return texto_minutos
	return _("{minutos} y {segundos}").format(minutos=texto_minutos, segundos=texto_segundos)
