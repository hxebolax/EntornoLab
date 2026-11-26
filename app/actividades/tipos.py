"""Catálogo de tipos de actividad y esquema declarativo de sus campos.

Una actividad es un diccionario JSON; aquí está lo que el Estudio necesita
para ofrecerla y editarla sin conocer cada tipo: ``TIPOS`` dice qué tipos hay
y a qué grupo pertenecen (juego, práctica o examen) y ``campos_de`` describe
el formulario de cada uno. Así añadir un tipo no obliga a tocar el editor.

Las claves de los campos pueden llevar un punto (``mensajes.inicio``,
``travieso.activo``): nombran un valor dentro de un diccionario anidado y se
leen y se escriben con ``leer_campo`` y ``poner_campo``.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any

from app.core.i18n import N_, _

FORMATO_ACTIVIDAD = 1

GRUPOS: tuple[str, ...] = ("juego", "practica", "examen")
MODOS: tuple[str, ...] = ("juego", "practica", "examen")
ESTILOS: tuple[str, ...] = ("infantil", "juvenil", "adulto")
ESTILO_DEL_ALUMNO = "del_alumno"
VISIBILIDADES: tuple[str, ...] = ("lejos", "cerca", "oculto")
MODOS_BALIZA: tuple[str, ...] = ("nunca", "al_pedir", "siempre")
TIPOS_CAMPO: tuple[str, ...] = (
	"texto",
	"texto_largo",
	"entero",
	"decimal",
	"si_no",
	"opcion",
	"posicion",
	"elemento",
	"lista_premios",
	"lista_objetivos",
	"ayudas",
	"sonido",
)
# Clases de elemento que puede pedir un campo de tipo «elemento».
CLASES_ELEMENTO: tuple[str, ...] = ("espacio", "abertura", "objeto", "referencia", "salida", "conector", "fuente")
CARDINALES: tuple[str, ...] = ("norte", "este", "sur", "oeste")


@dataclass(frozen=True)
class InfoTipo:
	"""Un tipo de actividad tal como lo ve quien elige qué crear.

	``nombre`` y ``descripcion`` se guardan en español (idioma de origen) y se
	traducen al leerlos con ``nombre_visible`` y ``descripcion_visible``: el
	catálogo se construye una vez, antes de que se conozca el idioma.
	"""

	id: str
	nombre: str
	descripcion: str
	modo_por_defecto: str
	grupo: str

	@property
	def nombre_visible(self) -> str:
		"""Nombre en el idioma de la interfaz."""
		return _(self.nombre)

	@property
	def descripcion_visible(self) -> str:
		"""Descripción en el idioma de la interfaz."""
		return _(self.descripcion)


@dataclass
class Campo:
	"""Un campo del formulario de una actividad.

	``opciones`` depende del tipo: en ``opcion`` es una lista de pares
	(valor, etiqueta); en ``elemento``, la lista de clases de elemento que
	valen (espacio, abertura, objeto, referencia, salida, conector).
	``depende_de`` es la clave de un campo «sí o no» que debe estar activado
	para que este tenga sentido (el editor puede atenuarlo si no lo está).
	"""

	clave: str
	etiqueta: str
	tipo: str
	ayuda: str
	opciones: list[Any] | None = None
	defecto: Any = None
	minimo: float | None = None
	maximo: float | None = None
	grupo: str = "general"
	depende_de: str | None = None


def _tipo(ident: str, nombre: str, descripcion: str, modo: str, grupo: str) -> InfoTipo:
	return InfoTipo(ident, nombre, descripcion, modo, grupo)


TIPOS: dict[str, InfoTipo] = {
	info.id: info
	for info in (
		# ── Juegos ──
		_tipo("busqueda", N_("Búsqueda del tesoro"), N_("Encontrar todos los premios escondidos por el entorno."), "juego", "juego"),
		_tipo(
			"recadero",
			N_("El recadero"),
			N_("Coger algo en un sitio y llevarlo a otro; los encargos se pueden encadenar."),
			"juego",
			"juego",
		),
		_tipo(
			"sacar_tesoros",
			N_("Sacar los tesoros"),
			N_(
				"Recoger los tesoros de uno en uno y sacarlos por la salida más cercana. Cada tesoro puntúa 3, 2, 1 o 0 según la salida elegida."
			),
			"juego",
			"juego",
		),
		_tipo("escondite", N_("El escondite"), N_("Encontrar a un personaje escondido que hace ruido de vez en cuando."), "juego", "juego"),
		_tipo("sigue_guia", N_("Sigue al guía"), N_("Seguir a un guía por el sonido de sus pasos, sin alejarse de él."), "juego", "juego"),
		_tipo(
			"explorador",
			N_("El explorador"),
			N_("Descubrir todos los espacios del entorno; cada uno nuevo suena a hallazgo."),
			"juego",
			"juego",
		),
		_tipo(
			"pistas",
			N_("Pistas encadenadas"),
			N_(
				"Cada premio da la pista del siguiente, redactada con las relaciones espaciales reales del entorno o escrita por el profesional."
			),
			"juego",
			"juego",
		),
		_tipo(
			"cruce",
			N_("Cruza con el pitido"),
			N_("En la calle: decidir cuándo cruzar, por el paso y con el semáforo a favor."),
			"juego",
			"juego",
		),
		# ── Prácticas ──
		_tipo(
			"exploracion",
			N_("Exploración libre"),
			N_("Recorrer el entorno con libertad, sin objetivo ni puntuación."),
			"practica",
			"practica",
		),
		_tipo(
			"visita_guiada",
			N_("Visita guiada"),
			N_("Recorrer el entorno oyendo textos preparados en cada zona, o la narración en vivo del profesional."),
			"practica",
			"practica",
		),
		_tipo("ruta", N_("Ruta"), N_("Ir de un punto a otro, con paradas intermedias si se quiere."), "practica", "practica"),
		_tipo("ruta_inversa", N_("Ruta inversa"), N_("Ir a un lugar y volver por donde se vino."), "practica", "practica"),
		_tipo(
			"volver_origen",
			N_("Volver al origen"),
			N_("Pasar por varios lugares y regresar al punto de partida por el camino más corto."),
			"practica",
			"practica",
		),
		_tipo(
			"ruta_alternativa",
			N_("Ruta alternativa"),
			N_("Llegar al destino con una puerta o una escalera cortadas: hay que encontrar otro camino."),
			"practica",
			"practica",
		),
		_tipo(
			"localizar",
			N_("Localizar un espacio"),
			N_("Encontrar una habitación o un lugar sabiendo solo su nombre."),
			"practica",
			"practica",
		),
		_tipo(
			"perimetro",
			N_("Familiarización de sala"),
			N_("Conocer una sala como en orientación y movilidad: primero el perímetro, después el interior."),
			"practica",
			"practica",
		),
		_tipo(
			"linea_guia",
			N_("Seguir una línea guía"),
			N_("Seguir una pared o un bordillo de un extremo a otro sin separarse."),
			"practica",
			"practica",
		),
		# ── Exámenes ──
		_tipo(
			"examen_rutas",
			N_("Examen de rutas"),
			N_("Serie de rutas no entrenadas de dificultad comparable, con límite de tiempo. Se registra el acierto y el tiempo."),
			"examen",
			"examen",
		),
		_tipo(
			"examen_salida",
			N_("Examen de salida más corta"),
			N_("Desde varios puntos de partida, salir por la salida más cercana. Cada salida puntúa 3, 2, 1 o 0."),
			"examen",
			"examen",
		),
		_tipo(
			"examen_senalar",
			N_("Examen de señalar"),
			N_("Girarse hacia un lugar que no se percibe y confirmar. Se mide el error en grados."),
			"examen",
			"examen",
		),
		_tipo(
			"examen_distancias",
			N_("Examen de distancias"),
			N_("Decidir cuál de dos lugares queda más cerca, andando o en línea recta."),
			"examen",
			"examen",
		),
		_tipo(
			"examen_reconstruccion",
			N_("Examen de reconstrucción"),
			N_("Colocar las habitaciones en su posición relativa respondiendo a preguntas como «¿qué hay al norte del salón?»."),
			"examen",
			"examen",
		),
	)
}

# Ayudas del motor (las mismas claves que ``app.motor.percepcion.AYUDAS``) con su nombre para el formulario.
NOMBRES_AYUDAS: dict[str, str] = {
	"donde_estoy": N_("Dónde estoy"),
	"descripcion": N_("Descripción del lugar"),
	"mirar": N_("Mirar a los lados y atrás"),
	"delante": N_("Qué hay delante"),
	"alrededor": N_("Qué hay alrededor"),
	"sonda": N_("Bastón sonoro"),
	"cercanos": N_("Lista de cosas cercanas"),
	"descubiertos": N_("Lugares descubiertos"),
	"brujula": N_("Brújula"),
	"eco": N_("Eco"),
	"objetivo": N_("Repetir el objetivo"),
	"pista": N_("Pedir una pista"),
	"baliza": N_("Baliza sonora"),
	"avisos": N_("Avisos automáticos de proximidad"),
}

# Ayudas que en un examen quedan prohibidas si el profesional no dice otra cosa: darían la respuesta.
AYUDAS_PROHIBIDAS_EN_EXAMEN: tuple[str, ...] = ("pista", "baliza", "donde_estoy", "descripcion", "cercanos", "descubiertos")

# Retirada progresiva de ayudas: cada nivel quita algo al anterior.
NIVELES_SERIE: list[dict[str, Any]] = [
	{"nombre": N_("Con baliza"), "baliza": "siempre", "ayudas": {}},
	{"nombre": N_("Baliza solo al pedirla"), "baliza": "al_pedir", "ayudas": {}},
	{"nombre": N_("Sin baliza"), "baliza": "nunca", "ayudas": {"baliza": False}},
	{
		"nombre": N_("Sin baliza y sin «dónde estoy»"),
		"baliza": "nunca",
		"ayudas": {"baliza": False, "donde_estoy": False, "descripcion": False},
	},
]

_ELEMENTOS_LUGAR = ["espacio", "referencia", "objeto", "abertura"]


def _opciones_estilo() -> list[tuple[str, str]]:
	return [
		(ESTILO_DEL_ALUMNO, _("El de la ficha del alumno")),
		("infantil", _("Infantil")),
		("juvenil", _("Juvenil")),
		("adulto", _("Adulto")),
	]


def _comunes(info: InfoTipo) -> list[Campo]:
	"""Campos que comparten todas las actividades."""
	campos = [
		Campo(
			"nombre",
			_("Nombre"),
			"texto",
			_("Nombre con el que el alumno y el profesional verán la actividad."),
			defecto=info.nombre_visible,
		),
		Campo("descripcion", _("Descripción"), "texto_largo", _("Para qué sirve esta actividad; solo la lee el profesional."), defecto=""),
		Campo(
			"estilo",
			_("Estilo de presentación"),
			"opcion",
			_("Cómo se le habla al alumno. El contenido de aprendizaje es el mismo en los tres estilos."),
			opciones=_opciones_estilo(),
			defecto=ESTILO_DEL_ALUMNO,
		),
		Campo(
			"inicio",
			_("Punto de inicio"),
			"posicion",
			_("Dónde empieza el alumno y hacia dónde mira. Vacío: el inicio del entorno."),
			defecto=None,
		),
		Campo(
			"mensajes.inicio",
			_("Mensaje de inicio"),
			"texto_largo",
			_("Se dice al empezar. Vacío: el mensaje de serie del estilo."),
			defecto="",
			grupo="mensajes",
		),
		Campo(
			"mensajes.logro",
			_("Mensaje de logro"),
			"texto_largo",
			_("Se dice al conseguir cada objetivo. Vacío: el de serie."),
			defecto="",
			grupo="mensajes",
		),
		Campo(
			"mensajes.final", _("Mensaje final"), "texto_largo", _("Se dice al terminar. Vacío: el de serie."), defecto="", grupo="mensajes"
		),
		Campo(
			"ayudas",
			_("Ayudas permitidas"),
			"ayudas",
			_("Qué ayudas puede usar el alumno y cuántas veces. Lo que no se indique queda como en la ficha del alumno."),
			defecto={},
			grupo="ayudas",
		),
		Campo(
			"cuestionario",
			_("Preguntar al terminar"),
			"si_no",
			_("Al acabar, tres preguntas breves y opcionales sobre esfuerzo, confianza y disfrute."),
			defecto=False,
			grupo="final",
		),
	]
	if info.grupo == "examen":
		return campos
	campos.extend(
		[
			Campo(
				"tiempo_limite_s",
				_("Contrarreloj (segundos)"),
				"entero",
				_("Tiempo máximo de juego, sin contar las pausas. Cero: sin límite. Las prisas son siempre opcionales."),
				defecto=0,
				minimo=0,
				maximo=7200,
			),
			Campo(
				"baliza",
				_("Baliza sonora hacia el objetivo"),
				"opcion",
				_(
					"«Siempre» guía en todo momento; «al pedirla» solo suena un rato cuando el alumno pide una pista. Si hay niveles, mandan ellos."
				),
				opciones=[("nunca", _("Nunca")), ("al_pedir", _("Al pedir una pista")), ("siempre", _("Siempre"))],
				defecto="al_pedir",
				grupo="ayudas",
			),
			Campo(
				"usar_niveles",
				_("Retirar las ayudas por niveles"),
				"si_no",
				_(
					"Cuatro niveles: con baliza, baliza solo al pedirla, sin baliza y sin «dónde estoy». Se sube al superar el anterior sin ayuda."
				),
				defecto=False,
				grupo="ayudas",
			),
			Campo(
				"nivel",
				_("Nivel de partida"),
				"entero",
				_("Nivel en el que empieza el alumno (0 es el más fácil)."),
				defecto=0,
				minimo=0,
				maximo=9,
				grupo="ayudas",
				depende_de="usar_niveles",
			),
			Campo(
				"fallos_para_ayuda",
				_("Fallos seguidos antes de ofrecer ayuda"),
				"entero",
				_("Tras tantos tropiezos seguidos el juego ofrece una pista en lugar de insistir. Cero: no ofrecerla nunca."),
				defecto=3,
				minimo=0,
				maximo=20,
				grupo="ayudas",
			),
			Campo(
				"con_acompanante",
				_("Con personaje acompañante"),
				"si_no",
				_("Solo en el estilo infantil: un personaje que se presenta al empezar y anima durante el juego."),
				defecto=True,
				grupo="mensajes",
			),
			Campo(
				"acompanante",
				_("Nombre del acompañante"),
				"texto",
				_("Cómo se llama el personaje. Vacío: el de serie."),
				defecto="",
				grupo="mensajes",
				depende_de="con_acompanante",
			),
			Campo(
				"recompensas.desbloqueo_nombre",
				_("Recompensa que se desbloquea"),
				"texto",
				_("Algo que el alumno gana al juntar estrellas, por ejemplo «la casa del árbol». Vacío: ninguna."),
				defecto="",
				grupo="final",
			),
			Campo(
				"recompensas.desbloqueo_estrellas",
				_("Estrellas necesarias para desbloquearla"),
				"entero",
				_("Cuántas estrellas, sumando las de sesiones anteriores, hacen falta."),
				defecto=5,
				minimo=1,
				maximo=500,
				grupo="final",
			),
		]
	)
	if info.id == "sigue_guia":
		# El guía ES la ayuda: no hay baliza ni niveles que retirar.
		campos = [campo for campo in campos if campo.clave not in ("baliza", "usar_niveles", "nivel")]
	return campos


def _premios(obligatorios: bool = True) -> list[Campo]:
	ayuda = _("Cada premio tiene nombre, lugar, sonido, visibilidad (lejos, cerca u oculto), objeto que lo esconde y mensaje.")
	if not obligatorios:
		ayuda = _("Premios de regalo por el camino; no hacen falta para terminar.")
	return [Campo("premios", _("Premios"), "lista_premios", ayuda, defecto=[], grupo="premios")]


def _travieso() -> list[Campo]:
	return [
		Campo(
			"travieso.activo",
			_("Con el travieso"),
			"si_no",
			_("Un personaje que de vez en cuando cambia de sitio un premio sin recoger, para obligar a volver a recorrer."),
			defecto=False,
			grupo="premios",
		),
		Campo(
			"travieso.cada_s",
			_("Segundos entre travesuras"),
			"entero",
			_("Cada cuánto tiempo de juego mueve un premio."),
			defecto=90,
			minimo=20,
			maximo=1200,
			grupo="premios",
			depende_de="travieso.activo",
		),
		Campo(
			"travieso.veces",
			_("Travesuras como mucho"),
			"entero",
			_("Cuántas veces puede mover premios en una partida."),
			defecto=2,
			minimo=1,
			maximo=20,
			grupo="premios",
			depende_de="travieso.activo",
		),
	]


def _examen(tiempo: int, con_tiempo: bool = True) -> list[Campo]:
	campos = [
		Campo(
			"numero_pruebas",
			_("Número de pruebas"),
			"entero",
			_("Cuántas pruebas se generan si no se definen a mano."),
			defecto=5,
			minimo=1,
			maximo=30,
			grupo="examen",
		),
		Campo(
			"pruebas",
			_("Pruebas definidas a mano"),
			"lista_objetivos",
			_("Vacío: el programa las genera con la semilla, siempre las mismas para la misma semilla."),
			defecto=[],
			grupo="examen",
		),
		Campo(
			"semilla",
			_("Semilla"),
			"entero",
			_("Número que fija las pruebas generadas: con la misma semilla el examen se repite idéntico otro día."),
			defecto=1,
			minimo=0,
			maximo=2**31 - 1,
			grupo="examen",
		),
		Campo(
			"regla_parada.activa",
			_("Regla de parada"),
			"si_no",
			_("Termina el examen antes de tiempo si el alumno falla demasiado al principio, para evitar la frustración."),
			defecto=True,
			grupo="examen",
		),
		Campo(
			"regla_parada.de",
			_("Se miran las primeras"),
			"entero",
			_("Número de pruebas iniciales que se tienen en cuenta."),
			defecto=5,
			minimo=1,
			maximo=30,
			grupo="examen",
			depende_de="regla_parada.activa",
		),
		Campo(
			"regla_parada.minimo",
			_("Aciertos mínimos para seguir"),
			"entero",
			_("Si en esas primeras pruebas ya no se puede llegar a este número de aciertos, el examen termina."),
			defecto=3,
			minimo=1,
			maximo=30,
			grupo="examen",
			depende_de="regla_parada.activa",
		),
		Campo(
			"decir_resultado",
			_("Decir el resultado al final"),
			"si_no",
			_("Durante el examen nunca se dice si se acierta. Con esto activado, al terminar se dice el total."),
			defecto=False,
			grupo="examen",
		),
	]
	if con_tiempo:
		campos.insert(
			2,
			Campo(
				"tiempo_por_prueba_s",
				_("Límite de tiempo por prueba (segundos)"),
				"entero",
				_("Tiempo de juego para cada prueba; el tiempo en pausa no cuenta. Cero: sin límite."),
				defecto=tiempo,
				minimo=0,
				maximo=3600,
				grupo="examen",
			),
		)
	return campos


def _propios(tipo: str) -> list[Campo]:
	"""Campos que solo tiene ese tipo de actividad."""
	if tipo == "busqueda":
		return [
			*_premios(),
			Campo(
				"orden_obligatorio",
				_("En orden"),
				"si_no",
				_("Los premios hay que encontrarlos en el orden de la lista."),
				defecto=False,
				grupo="premios",
			),
			Campo(
				"anunciar_premios",
				_("Decir cuántos hay"),
				"si_no",
				_("Al empezar se dice cuántos premios hay escondidos."),
				defecto=True,
				grupo="premios",
			),
			*_travieso(),
		]
	if tipo == "pistas":
		return [
			*_premios(),
			Campo(
				"pistas_automaticas",
				_("Redactar las pistas que falten"),
				"si_no",
				_("Si un premio no trae pista escrita, se redacta con las relaciones reales del entorno («al norte de la cocina»)."),
				defecto=True,
				grupo="premios",
			),
		]
	if tipo == "sacar_tesoros":
		return [
			*_premios(),
			Campo(
				"tolerancia_m",
				_("Empate entre salidas (metros)"),
				"decimal",
				_("Dos salidas cuya distancia difiere menos que esto cuentan como igual de cercanas."),
				defecto=1.0,
				minimo=0.0,
				maximo=10.0,
				grupo="puntuacion",
			),
			*_travieso(),
		]
	if tipo == "recadero":
		return [
			Campo(
				"objetivos",
				_("Encargos"),
				"lista_objetivos",
				_("Pares «recoger» y «entregar», en orden: qué se coge, dónde y adónde se lleva."),
				defecto=[],
				grupo="objetivos",
			),
			*_premios(False),
		]
	if tipo == "escondite":
		return [
			Campo("personaje", _("Quién se esconde"), "texto", _("Nombre del personaje escondido."), defecto="", grupo="objetivos"),
			Campo(
				"sonido",
				_("Sonido que hace"),
				"sonido",
				_("Sonido con el que se delata de vez en cuando."),
				defecto="premio/aparece",
				grupo="objetivos",
			),
			Campo(
				"cada_s",
				_("Segundos entre ruidos"),
				"decimal",
				_("Cada cuánto hace ruido."),
				defecto=4.0,
				minimo=1.0,
				maximo=60.0,
				grupo="objetivos",
			),
			Campo("rondas", _("Rondas"), "entero", _("Cuántas veces se esconde."), defecto=3, minimo=1, maximo=20, grupo="objetivos"),
			Campo(
				"objetivos",
				_("Escondites"),
				"lista_objetivos",
				_("Lugares donde puede esconderse. Vacío: los elige el programa, lejos del alumno."),
				defecto=[],
				grupo="objetivos",
			),
		]
	if tipo == "sigue_guia":
		return [
			Campo(
				"destino", _("Adónde lleva el guía"), "elemento", _("Lugar al que conduce."), opciones=_ELEMENTOS_LUGAR, grupo="objetivos"
			),
			Campo("personaje", _("Nombre del guía"), "texto", _("Cómo se llama el guía."), defecto="", grupo="objetivos"),
			Campo(
				"velocidad_guia",
				_("Velocidad del guía (m/s)"),
				"decimal",
				_("A qué paso anda; se para a esperar si el alumno se queda atrás."),
				defecto=0.8,
				minimo=0.2,
				maximo=2.0,
				grupo="objetivos",
			),
			Campo(
				"distancia_espera",
				_("Distancia a la que espera (metros)"),
				"decimal",
				_("Si el alumno queda más lejos, el guía se para y le llama."),
				defecto=4.0,
				minimo=1.5,
				maximo=15.0,
				grupo="objetivos",
			),
		]
	if tipo == "explorador":
		return [
			Campo(
				"fraccion",
				_("Parte que hay que descubrir"),
				"decimal",
				_("De 0,5 (la mitad de los espacios) a 1 (todos)."),
				defecto=1.0,
				minimo=0.5,
				maximo=1.0,
				grupo="objetivos",
			),
			*_premios(False),
		]
	if tipo == "cruce":
		return [
			Campo(
				"cruces",
				_("Cruces que hay que hacer"),
				"entero",
				_("Número de veces que hay que cruzar una calzada."),
				defecto=3,
				minimo=1,
				maximo=20,
				grupo="objetivos",
			),
			Campo(
				"destino",
				_("Lugar al que llegar"),
				"elemento",
				_("Opcional: si se indica, además hay que llegar a ese lugar del otro lado."),
				opciones=_ELEMENTOS_LUGAR,
				grupo="objetivos",
			),
		]
	if tipo == "visita_guiada":
		return [
			Campo(
				"objetivos",
				_("Zonas de la visita"),
				"lista_objetivos",
				_("Cada zona es un lugar y el texto que se dice al llegar. Vacío: todos los espacios, con su descripción."),
				defecto=[],
				grupo="objetivos",
			),
			Campo(
				"orden_obligatorio",
				_("En orden"),
				"si_no",
				_("Las zonas se visitan en el orden de la lista."),
				defecto=False,
				grupo="objetivos",
			),
			Campo(
				"narrada_en_vivo",
				_("Narrada en vivo por el profesional"),
				"si_no",
				_("No se leen textos preparados: el profesional narra desde la supervisión con sus mensajes."),
				defecto=False,
				grupo="objetivos",
			),
		]
	if tipo == "ruta":
		return [
			Campo("destino", _("Destino"), "elemento", _("Lugar al que hay que llegar."), opciones=_ELEMENTOS_LUGAR, grupo="objetivos"),
			Campo(
				"objetivos",
				_("Paradas intermedias"),
				"lista_objetivos",
				_("Lugares por los que hay que pasar antes, en orden. Opcional."),
				defecto=[],
				grupo="objetivos",
			),
			*_premios(False),
		]
	if tipo == "ruta_inversa":
		return [
			Campo(
				"destino", _("Lugar de ida"), "elemento", _("Adónde se va antes de volver."), opciones=_ELEMENTOS_LUGAR, grupo="objetivos"
			),
			Campo(
				"ida_guiada",
				_("Ida con baliza"),
				"si_no",
				_("La ida se hace siguiendo una baliza; la vuelta, que es lo que se mide, sin ella."),
				defecto=True,
				grupo="objetivos",
			),
		]
	if tipo == "volver_origen":
		return [
			Campo(
				"objetivos",
				_("Lugares por los que pasar"),
				"lista_objetivos",
				_("Se visitan en orden y después se vuelve al punto de partida."),
				defecto=[],
				grupo="objetivos",
			),
			Campo(
				"ida_guiada",
				_("Ida con baliza"),
				"si_no",
				_("La ida se hace siguiendo una baliza; la vuelta, sin ella."),
				defecto=True,
				grupo="objetivos",
			),
		]
	if tipo == "ruta_alternativa":
		return [
			Campo("destino", _("Destino"), "elemento", _("Lugar al que hay que llegar."), opciones=_ELEMENTOS_LUGAR, grupo="objetivos"),
			Campo(
				"corte",
				_("Paso cortado"),
				"elemento",
				_("Puerta, hueco, escalera o ascensor por el que hoy no se puede pasar."),
				opciones=["abertura", "conector"],
				grupo="objetivos",
			),
		]
	if tipo == "localizar":
		return [
			Campo(
				"destino",
				_("Espacio que hay que encontrar"),
				"elemento",
				_("Solo se le dice el nombre al alumno."),
				opciones=["espacio"],
				grupo="objetivos",
			),
			Campo(
				"confirmar",
				_("Confirmar la llegada"),
				"si_no",
				_("El alumno tiene que confirmar que cree haber llegado (con la orden de usar); si no, se detecta solo."),
				defecto=False,
				grupo="objetivos",
			),
		]
	if tipo == "perimetro":
		return [
			Campo("espacio", _("Sala"), "elemento", _("Sala que se va a conocer."), opciones=["espacio"], grupo="objetivos"),
			Campo(
				"distancia_pared",
				_("Distancia a la pared (metros)"),
				"decimal",
				_("Hasta dónde se considera que se va siguiendo la pared."),
				defecto=1.0,
				minimo=0.4,
				maximo=2.0,
				grupo="objetivos",
			),
			Campo(
				"fraccion_perimetro",
				_("Parte del perímetro"),
				"decimal",
				_("Parte del contorno que hay que recorrer antes de pasar al interior."),
				defecto=0.8,
				minimo=0.3,
				maximo=1.0,
				grupo="objetivos",
			),
			Campo(
				"fraccion_interior",
				_("Parte del interior"),
				"decimal",
				_("Parte del interior que hay que pisar para dar la sala por conocida."),
				defecto=0.5,
				minimo=0.1,
				maximo=1.0,
				grupo="objetivos",
			),
		]
	if tipo == "linea_guia":
		return [
			Campo(
				"espacio",
				_("Espacio"),
				"elemento",
				_("Habitación o acera cuya pared o bordillo se sigue."),
				opciones=["espacio"],
				grupo="objetivos",
			),
			Campo(
				"lado",
				_("Lado"),
				"opcion",
				_("Qué lado del espacio hace de línea guía."),
				opciones=[
					("mas_largo", _("El más largo")),
					("norte", _("Norte")),
					("este", _("Este")),
					("sur", _("Sur")),
					("oeste", _("Oeste")),
				],
				defecto="mas_largo",
				grupo="objetivos",
			),
			Campo(
				"distancia_maxima",
				_("Separación máxima (metros)"),
				"decimal",
				_("Más lejos que esto cuenta como haberse separado de la línea."),
				defecto=1.0,
				minimo=0.4,
				maximo=3.0,
				grupo="objetivos",
			),
		]
	if tipo == "examen_rutas":
		return [
			*_examen(360),
			Campo(
				"variante",
				_("Variante"),
				"opcion",
				_(
					"«Rutas» va de un punto a otro; «inversa» enseña la ida y mide la vuelta; «atajo» enseña dos tramos y mide el regreso directo."
				),
				opciones=[("normal", _("Rutas")), ("inversa", _("Ruta inversa")), ("atajo", _("Atajos"))],
				defecto="normal",
				grupo="examen",
			),
		]
	if tipo == "examen_salida":
		return [
			*_examen(180),
			Campo(
				"acierto_minimo",
				_("Puntos que cuentan como acierto"),
				"entero",
				_("Para la regla de parada: una salida con estos puntos o más es un acierto."),
				defecto=2,
				minimo=1,
				maximo=3,
				grupo="examen",
			),
			Campo(
				"tolerancia_m",
				_("Empate entre salidas (metros)"),
				"decimal",
				_("Dos salidas cuya distancia difiere menos que esto cuentan como igual de cercanas."),
				defecto=1.0,
				minimo=0.0,
				maximo=10.0,
				grupo="examen",
			),
		]
	if tipo == "examen_senalar":
		return [
			*_examen(60),
			Campo(
				"tolerancia_grados",
				_("Error que cuenta como acierto (grados)"),
				"entero",
				_("Para la regla de parada: un error igual o menor es un acierto."),
				defecto=30,
				minimo=5,
				maximo=90,
				grupo="examen",
			),
			Campo(
				"giro_grados",
				_("Giro por pulsación (grados)"),
				"entero",
				_("Durante este examen cada pulsación gira estos grados, para poder afinar."),
				defecto=15,
				minimo=5,
				maximo=45,
				grupo="examen",
			),
		]
	if tipo == "examen_distancias":
		return [
			*_examen(60),
			Campo(
				"criterio",
				_("Qué distancia se compara"),
				"opcion",
				_("La que hay que andar o la distancia en línea recta."),
				opciones=[("camino", _("Andando")), ("recta", _("En línea recta"))],
				defecto="camino",
				grupo="examen",
			),
		]
	if tipo == "examen_reconstruccion":
		return _examen(60)
	return _premios(False) if tipo == "exploracion" else []


def campos_de(tipo: str) -> list[Campo]:
	"""Campos del formulario de un tipo de actividad, en el orden en que conviene mostrarlos.

	Un tipo desconocido lanza ``KeyError``: el editor solo debe ofrecer los de ``TIPOS``.
	"""
	info = TIPOS[tipo]
	comunes = _comunes(info)
	propios = _propios(tipo)
	# Primero la identidad, después lo propio del tipo y al final ayudas, mensajes y cierre.
	cabeza = [campo for campo in comunes if campo.grupo == "general"]
	cola = [campo for campo in comunes if campo.grupo != "general"]
	return cabeza + propios + cola


def leer_campo(datos: dict[str, Any], clave: str, defecto: Any = None) -> Any:
	"""Valor de un campo; ``clave`` puede llevar puntos para entrar en diccionarios anidados."""
	actual: Any = datos
	for parte in clave.split("."):
		if not isinstance(actual, dict) or parte not in actual:
			return defecto
		actual = actual[parte]
	return actual


def poner_campo(datos: dict[str, Any], clave: str, valor: Any) -> None:
	"""Escribe un campo, creando los diccionarios anidados que hagan falta."""
	partes = clave.split(".")
	actual = datos
	for parte in partes[:-1]:
		siguiente = actual.get(parte)
		if not isinstance(siguiente, dict):
			siguiente = {}
			actual[parte] = siguiente
		actual = siguiente
	actual[partes[-1]] = valor


def valores_por_defecto(tipo: str) -> dict[str, Any]:
	"""Diccionario con el valor de serie de cada campo del tipo (copias: se puede modificar)."""
	datos: dict[str, Any] = {}
	for campo in campos_de(tipo):
		poner_campo(datos, campo.clave, copy.deepcopy(campo.defecto))
	return datos
