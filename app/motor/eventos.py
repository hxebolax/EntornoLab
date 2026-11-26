"""Eventos que devuelve el motor y fuentes continuas que declara.

El motor no suena ni habla: cada llamada a ``Sesion.avanzar`` devuelve una
lista de estos eventos y otra capa los presenta. La capa de sonido los
reconoce por el NOMBRE de su clase (``EvSonido``, ``EvVoz``, ``EvVibrar``,
``EvAcustica``), así que esos nombres son parte del contrato. ``EvRegistro``
y ``EvFin`` son para el seguimiento y para el reproductor.

Aquí vive también la correspondencia entre los nombres de sonido cortos que
escriben los entornos y los complementos («frigorifico», «golpe_metal») y los
sonidos de serie («fuente/frigorifico», «golpe/metal»): el motor siempre emite
el nombre completo, de modo que el banco de sonidos no tenga que adivinar.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

Posicion3 = tuple[float, float, float]

# Canales de voz que entiende la capa de voz.
CANALES_VOZ: tuple[str, ...] = ("juego", "ayuda", "aviso", "profesional")


@dataclass(slots=True)
class EvSonido:
	"""Un sonido de un solo disparo.

	``pos`` es (x, y, z) en el mundo; ``relativo`` es (ángulo en grados,
	distancia) respecto del oyente (0 delante, 90 a la derecha); sin ninguno
	de los dos el sonido no tiene posición (interfaz).
	"""

	nombre: str
	pos: Posicion3 | None = None
	volumen: float = 1.0
	tono: float = 1.0
	bus: str = "efectos"
	filtro: float = 0.0
	relativo: tuple[float, float] | None = None


@dataclass(slots=True)
class EvVoz:
	"""Una frase para la voz. ``interrumpir`` corta lo que se estuviera diciendo."""

	texto: str
	interrumpir: bool = False
	canal: str = "juego"


@dataclass(slots=True)
class EvVibrar:
	"""Vibración del mando: motores de 0 a 1 y milisegundos, o un ``patron`` con nombre.

	Los patrones son los de ``app.audio.haptica`` (choque, pared_izquierda,
	pared_derecha, objetivo, peldano, premio_cerca, aviso): un vocabulario
	pequeño y constante que el alumno aprende como aprende los sonidos.
	"""

	grave: float = 0.0
	agudo: float = 0.0
	ms: int = 0
	patron: str | None = None
	intensidad: float = 1.0


@dataclass(slots=True)
class EvAcustica:
	"""El eco del lugar ha cambiado (se entra en otro espacio)."""

	preset: str


@dataclass(slots=True)
class EvRegistro:
	"""Algo que interesa al seguimiento: un choque, una ayuda usada, una entrada en un espacio…

	``datos`` lleva siempre ``planta``, ``x``, ``y`` y ``espacio`` (los pone la
	sesión) además de lo propio de cada tipo. Ver la lista en ``docs/motor.md``.
	"""

	tipo: str
	datos: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvFin:
	"""La sesión ha terminado; ``resultado`` lo rellenan la sesión y la actividad."""

	resultado: dict[str, Any] = field(default_factory=dict)


Evento = EvSonido | EvVoz | EvVibrar | EvAcustica | EvRegistro | EvFin


@dataclass(slots=True)
class FuenteActiva:
	"""Una fuente continua que se oye ahora.

	``volumen`` y ``filtro`` llevan SOLO la oclusión y el camino por puertas:
	la atenuación por distancia la pone la capa de sonido a partir de ``pos``.
	"""

	id: str
	sonido: str
	pos: Posicion3
	volumen: float = 1.0
	tono: float = 1.0
	filtro: float = 0.0
	bucle: bool = True
	eco: bool = True
	bus: str = "ambiente"


# ── Nombres de sonido ────────────────────────────────────────────────────────

MATERIALES_GOLPE: tuple[str, ...] = ("ladrillo", "madera", "metal", "cristal", "plastico", "tela", "piedra")
SUELOS_PASOS: tuple[str, ...] = (
	"baldosa",
	"madera",
	"moqueta",
	"alfombra",
	"hormigon",
	"asfalto",
	"acera",
	"adoquin",
	"tierra",
	"hierba",
	"grava",
	"metal",
	"arena",
	"agua",
	"tactil_botones",
	"tactil_rayas",
)

# Material de pared o de objeto → material de los sonidos de golpe y de roce.
_MATERIAL_A_GOLPE: dict[str, str] = {
	"hormigon": "piedra",
	"yeso": "ladrillo",
	"valla": "metal",
	"seto": "tela",
	"vidrio": "cristal",
	"tejido": "tela",
	"moqueta": "tela",
	"hierro": "metal",
	"acero": "metal",
	"aluminio": "metal",
	"ceramica": "piedra",
	"marmol": "piedra",
	"carton": "plastico",
}

# Familias de sonidos de serie: un nombre corto «familia_resto» equivale a «familia/resto».
_FAMILIAS: tuple[str, ...] = (
	"ambiente",
	"golpe",
	"roce",
	"puerta",
	"semaforo",
	"trafico",
	"escalera",
	"ascensor",
	"baliza",
	"sonda",
	"brujula",
	"premio",
	"logro",
	"interfaz",
	"pasos",
	"fuente",
	"eco",
	"exterior",
)
# Sonidos de la familia «fuente», que los entornos nombran sin familia («reloj»).
_FUENTES_SERIE: frozenset[str] = frozenset(
	{"frigorifico", "reloj", "grifo", "ventilador", "television", "fuente_agua", "maquina_expendedora", "campanas", "pajaros"}
)


def material_sonido(material: str) -> str:
	"""Material de los sonidos de golpe y roce que corresponde a un material del modelo."""
	clave = str(material or "").strip().lower()
	if clave in MATERIALES_GOLPE:
		return clave
	return _MATERIAL_A_GOLPE.get(clave, "ladrillo")


def sonido_de_serie(nombre: str) -> str:
	"""Nombre completo de un sonido a partir del que escribe un entorno o un complemento.

	«frigorifico» → «fuente/frigorifico»; «golpe_metal» → «golpe/metal»;
	«ambiente_calle» → «ambiente/calle». Un nombre con carpeta o con extensión
	(un fichero del paquete o del complemento) se deja como está, y uno que no
	se reconoce también: el banco de sonidos sabrá si existe.
	"""
	texto = str(nombre or "").strip().replace("\\", "/")
	if not texto or "/" in texto or "." in texto:
		return texto
	if texto in _FUENTES_SERIE:
		return f"fuente/{texto}"
	familia, separador, resto = texto.partition("_")
	if separador and resto and familia in _FAMILIAS:
		return f"{familia}/{resto}"
	return texto


def sonido_golpe(material: str) -> str:
	"""Sonido de chocar con algo de ese material."""
	return f"golpe/{material_sonido(material)}"


def sonido_roce(material: str) -> str:
	"""Sonido de rozar algo de ese material."""
	return f"roce/{material_sonido(material)}"


def sonido_paso(suelo: str, pie_izquierdo: bool, variante: int = 1) -> str:
	"""Sonido de un paso sobre ese suelo, con el pie y la variante (1 a 3) indicados."""
	base = suelo if suelo in SUELOS_PASOS else "baldosa"
	return f"pasos/{base}_{'izq' if pie_izquierdo else 'der'}_{max(1, min(3, int(variante)))}"
