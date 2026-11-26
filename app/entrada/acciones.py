"""Las acciones con nombre que entiende el motor, con su texto y su ayuda.

Una acción es lo que el alumno quiere hacer («avanzar», «dónde estoy»), sin
decir con qué tecla o botón. El teclado y el mando se traducen a estas
acciones, y la sesión del motor las recibe con ``Sesion.orden(accion)``. Así
los mapas se pueden reasignar sin tocar el motor, y la ayuda y las pantallas
de reasignación salen de una única tabla.

Los identificadores son estables (se guardan en los mapas): nunca se
traducen. Lo que se traduce es el nombre visible y la ayuda, marcados aquí
con ``N_`` y traducidos al pedirlos, porque esta tabla se crea al importar el
módulo, antes de elegir el idioma.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.i18n import N_, _

# Contextos en los que vale una acción. «juego»: recorriendo el entorno.
# «menu»: en un menú hablado o en una pantalla de pausa.
JUEGO = "juego"
MENU = "menu"
CONTEXTOS: tuple[str, ...] = (JUEGO, MENU)

# Acción vacía: un botón o una tecla sin nada asignado.
NADA = "nada"


@dataclass(frozen=True)
class Accion:
	"""Una acción con nombre.

	``mantenida`` distingue las que duran mientras se pulsa (andar, girar) de
	las que son un toque (preguntar dónde estoy): la sesión necesita saber
	cuándo se suelta una mantenida, y de un toque solo le interesa el inicio.
	"""

	id: str
	texto: str
	texto_ayuda: str
	contextos: tuple[str, ...] = (JUEGO,)
	mantenida: bool = False

	@property
	def nombre(self) -> str:
		"""Nombre visible, en el idioma activo."""
		return _(self.texto)

	@property
	def ayuda(self) -> str:
		"""Explicación de para qué sirve, en el idioma activo."""
		return _(self.texto_ayuda)


_AMBOS = (JUEGO, MENU)
_SOLO_MENU = (MENU,)

_TABLA: tuple[Accion, ...] = (
	# ── Moverse ──
	Accion("avanzar", N_("Avanzar"), N_("Da un paso hacia delante, o camina mientras se mantiene."), mantenida=True),
	Accion("retroceder", N_("Retroceder"), N_("Da un paso hacia atrás sin girarte."), mantenida=True),
	Accion("girar_izquierda", N_("Girar a la izquierda"), N_("Gira el cuerpo hacia la izquierda."), mantenida=True),
	Accion("girar_derecha", N_("Girar a la derecha"), N_("Gira el cuerpo hacia la derecha."), mantenida=True),
	Accion("paso_izquierda", N_("Paso lateral a la izquierda"), N_("Da un paso de lado hacia la izquierda, sin girarte."), mantenida=True),
	Accion("paso_derecha", N_("Paso lateral a la derecha"), N_("Da un paso de lado hacia la derecha, sin girarte."), mantenida=True),
	Accion("media_vuelta", N_("Media vuelta"), N_("Te giras del todo para mirar hacia donde tenías la espalda.")),
	Accion("interactuar", N_("Interactuar"), N_("Abre una puerta, coge un premio, llama al ascensor o usa lo que tienes delante.")),
	# ── Preguntar ──
	Accion("donde_estoy", N_("Dónde estoy"), N_("Dice en qué lugar estás y hacia dónde miras.")),
	Accion("mirar_delante", N_("Mirar delante"), N_("Dice qué hay delante de ti y a qué distancia.")),
	Accion("mirar_izquierda", N_("Mirar a la izquierda"), N_("Dice qué hay a tu izquierda, sin girarte.")),
	Accion("mirar_detras", N_("Mirar detrás"), N_("Dice qué hay detrás de ti, sin girarte.")),
	Accion("mirar_derecha", N_("Mirar a la derecha"), N_("Dice qué hay a tu derecha, sin girarte.")),
	Accion("alrededor", N_("Alrededor"), N_("Describe lo que te rodea, por partes.")),
	Accion("cercano_siguiente", N_("Cercano siguiente"), N_("Pasa a lo siguiente de la lista de cosas cercanas.")),
	Accion("cercano_anterior", N_("Cercano anterior"), N_("Vuelve a lo anterior de la lista de cosas cercanas.")),
	Accion("descubiertos", N_("Lugares descubiertos"), N_("Dice los lugares que ya has descubierto.")),
	Accion("brujula", N_("Brújula"), N_("Dice hacia qué punto cardinal miras y hace sonar el norte.")),
	Accion("sonda", N_("Bastón sonoro"), N_("Un tono dice lo que hay delante y a qué distancia, como un bastón."), mantenida=True),
	Accion("eco", N_("Eco"), N_("Un chasquido cuyo eco da idea del tamaño del lugar.")),
	Accion("objetivo", N_("Objetivo"), N_("Repite lo que hay que hacer en la actividad.")),
	Accion("pista", N_("Pista"), N_("Pide una ayuda para encontrar el objetivo.")),
	# «Ya he llegado», «es hacia ahí», «esta respuesta»: no depende de lo que haya al alcance de la mano,
	# así un examen no confunde abrir una puerta con dar una respuesta.
	Accion(
		"confirmar",
		N_("Confirmar"),
		N_(
			"En un examen o al localizar un lugar, dice que ya has llegado, que miras hacia ahí o que esa es tu respuesta. Si hay una pregunta, abre sus respuestas."
		),
	),
	# ── Voz ──
	Accion("repetir", N_("Repetir"), N_("Repite el último mensaje."), _AMBOS),
	Accion("historial_anterior", N_("Mensaje anterior"), N_("Repasa el mensaje anterior del historial."), _AMBOS),
	Accion("historial_siguiente", N_("Mensaje siguiente"), N_("Repasa el mensaje siguiente del historial."), _AMBOS),
	Accion("callar", N_("Callar la voz"), N_("Corta lo que se está diciendo."), _AMBOS),
	# ── General ──
	Accion("volver_inicio", N_("Volver al inicio"), N_("Te lleva de nuevo al punto de partida.")),
	Accion("ayuda", N_("Ayuda"), N_("Dice las teclas o los botones que puedes usar ahora."), _AMBOS),
	Accion("pausa", N_("Pausa y menú"), N_("Detiene el juego y abre el menú.")),
	# ── Menús ──
	Accion("menu_arriba", N_("Opción anterior"), N_("Sube a la opción anterior del menú."), _SOLO_MENU),
	Accion("menu_abajo", N_("Opción siguiente"), N_("Baja a la opción siguiente del menú."), _SOLO_MENU),
	Accion("menu_izquierda", N_("Disminuir"), N_("Baja el valor de la opción, o va a la pestaña anterior."), _SOLO_MENU),
	Accion("menu_derecha", N_("Aumentar"), N_("Sube el valor de la opción, o va a la pestaña siguiente."), _SOLO_MENU),
	Accion("menu_aceptar", N_("Aceptar"), N_("Elige la opción del menú."), _SOLO_MENU),
	Accion("menu_atras", N_("Atrás"), N_("Vuelve al menú anterior, o lo cierra."), _SOLO_MENU),
)

# id → acción, en el orden del documento de arquitectura (el de la ayuda).
ACCIONES: dict[str, Accion] = {a.id: a for a in _TABLA}


def existe(accion: str) -> bool:
	"""Si ``accion`` es una acción conocida (``nada`` no lo es)."""
	return accion in ACCIONES


def accion(identificador: str) -> Accion | None:
	"""La acción con ese identificador, o None si no existe."""
	return ACCIONES.get(identificador)


def nombre_accion(identificador: str) -> str:
	"""Nombre visible de una acción; «sin asignar» para ``nada`` o una desconocida."""
	encontrada = ACCIONES.get(identificador)
	return encontrada.nombre if encontrada is not None else _("Sin asignar")


def ayuda_accion(identificador: str) -> str:
	"""Explicación de una acción; cadena vacía si no existe."""
	encontrada = ACCIONES.get(identificador)
	return encontrada.ayuda if encontrada is not None else ""


def acciones_de(contexto: str) -> list[Accion]:
	"""Las acciones que valen en un contexto, en el orden de la ayuda."""
	return [a for a in ACCIONES.values() if contexto in a.contextos]


def vale_en(identificador: str, contexto: str) -> bool:
	"""Si esa acción se puede asignar en ese contexto."""
	encontrada = ACCIONES.get(identificador)
	return encontrada is not None and contexto in encontrada.contextos


def es_mantenida(identificador: str) -> bool:
	"""Si la acción dura mientras se mantiene pulsada."""
	encontrada = ACCIONES.get(identificador)
	return encontrada is not None and encontrada.mantenida
