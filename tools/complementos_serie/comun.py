"""Piezas comunes para describir los complementos de serie de forma compacta.

Cada complemento de serie se escribe en su módulo como una lista de llamadas
a ``O(...)``, una por objeto, con los textos en español y en inglés juntos.
``tools/generar_complementos.py`` convierte esas definiciones en el
``complemento.json``, el ``locales/en.json``, las miniaturas y los sonidos de
``data/plugins/<id>/``.

Aquí están también las FORMAS: huellas en planta dentro del cuadrado 0..1
(0,0 = esquina trasera izquierda; 1,1 = delantera derecha; el frente es y = 1)
que luego se estiran al ancho y al fondo reales de cada objeto.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from app.dominio import catalogo as cat

Punto = tuple[float, float]
Medida = float | tuple[float, float, float]


# ── Formas ───────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Forma:
	"""Huella en planta: tipo del formato, puntos (si es un polígono) y cómo se llama en cada idioma."""

	tipo: str
	es: str
	en: str
	puntos: tuple[Punto, ...] = ()

	def a_dict(self) -> dict[str, Any]:
		"""La forma tal como va en ``complemento.json``."""
		datos: dict[str, Any] = {"tipo": self.tipo}
		if self.puntos:
			datos["puntos"] = [[round(x, 3), round(y, 3)] for x, y in self.puntos]
		return datos


def _encajar(puntos: list[Punto]) -> tuple[Punto, ...]:
	"""Estira los puntos para que su caja envolvente sea exactamente el cuadrado 0..1.

	Así el ancho y el fondo declarados son las medidas reales de la huella.
	"""
	xs = [p[0] for p in puntos]
	ys = [p[1] for p in puntos]
	ancho = (max(xs) - min(xs)) or 1.0
	fondo = (max(ys) - min(ys)) or 1.0
	return tuple((min(1.0, max(0.0, (x - min(xs)) / ancho)), min(1.0, max(0.0, (y - min(ys)) / fondo))) for x, y in puntos)


def _poligono(puntos: list[Punto], es: str, en: str) -> Forma:
	return Forma("poligono", es, en, _encajar(puntos))


RECTANGULO = Forma("rectangulo", "un rectángulo", "a rectangle")
CIRCULO = Forma("circulo", "un círculo", "a circle")
ELIPSE = Forma("circulo", "un óvalo", "an oval")


def ele(brazo_ancho: float = 0.5, brazo_fondo: float = 0.5, lado: str = "izquierda") -> Forma:
	"""Ele: el brazo largo ocupa todo el ancho por detrás y el corto sale hacia delante por un lado."""
	if lado == "izquierda":
		puntos = [(0, 0), (1, 0), (1, brazo_fondo), (brazo_ancho, brazo_fondo), (brazo_ancho, 1), (0, 1)]
	else:
		puntos = [(0, 0), (1, 0), (1, 1), (1 - brazo_ancho, 1), (1 - brazo_ancho, brazo_fondo), (0, brazo_fondo)]
	return Forma("ele", "una ele", "an L shape", tuple((float(x), float(y)) for x, y in puntos))


def u_abierta(pared_lado: float = 0.06, pared_fondo: float = 0.3) -> Forma:
	"""U abierta por delante: un fondo grueso y dos paredes laterales finas (una marquesina con su banco)."""
	g, h = pared_lado, pared_fondo
	return _poligono(
		[(0, 0), (1, 0), (1, 1), (1 - g, 1), (1 - g, h), (g, h), (g, 1), (0, 1)], "una U abierta por delante", "a U open at the front"
	)


def te(tallo: float = 0.34, cabeza: float = 0.7) -> Forma:
	"""Te: una barra ancha detrás y un saliente centrado hacia delante."""
	a, b = 0.5 - tallo / 2, 0.5 + tallo / 2
	return _poligono([(0, 0), (1, 0), (1, cabeza), (b, cabeza), (b, 1), (a, 1), (a, cabeza), (0, cabeza)], "una te", "a T shape")


def peine(dientes: int = 4, grosor: float = 0.12, barra: float = 0.2) -> Forma:
	"""Peine: una barra detrás y varios cuerpos hacia delante, con huecos entre ellos (una fila de tornos)."""
	puntos: list[Punto] = [(0.0, 0.0), (1.0, 0.0)]
	paso = (1.0 - grosor) / (dientes - 1)
	for k in reversed(range(dientes)):
		x0 = k * paso
		# Los dientes de los extremos continúan el costado de la barra: ahí no hace falta vértice.
		if k < dientes - 1:
			puntos.append((x0 + grosor, barra))
		puntos += [(x0 + grosor, 1.0), (x0, 1.0)]
		if k > 0:
			puntos.append((x0, barra))
	return _poligono(
		puntos, "un peine: una barra con cuerpos que salen hacia delante", "a comb: a bar with bodies sticking out to the front"
	)


def cruz(grosor: float = 0.34) -> Forma:
	"""Cruz de brazos iguales."""
	a, b = 0.5 - grosor / 2, 0.5 + grosor / 2
	puntos = [(a, 0), (b, 0), (b, a), (1, a), (1, b), (b, b), (b, 1), (a, 1), (a, b), (0, b), (0, a), (a, a)]
	return _poligono(puntos, "una cruz", "a cross")


def chaflan(corte: float = 0.18) -> Forma:
	"""Rectángulo con las cuatro esquinas cortadas."""
	c = corte
	puntos = [(c, 0), (1 - c, 0), (1, c), (1, 1 - c), (1 - c, 1), (c, 1), (0, 1 - c), (0, c)]
	return _poligono(puntos, "un rectángulo con las esquinas cortadas", "a rectangle with cut corners")


def redondeado(exponente: float = 4.0, lados: int = 20) -> Forma:
	"""Rectángulo de esquinas redondeadas (una superelipse): una bañera, una mesa ovalada."""
	puntos = []
	for k in range(lados):
		angulo = 2 * math.pi * k / lados
		c, s = math.cos(angulo), math.sin(angulo)
		puntos.append((0.5 + 0.5 * math.copysign(abs(c) ** (2 / exponente), c), 0.5 + 0.5 * math.copysign(abs(s) ** (2 / exponente), s)))
	return _poligono(puntos, "un rectángulo de esquinas redondeadas", "a rectangle with rounded corners")


def ovalo_alargado(lados_extremo: int = 6) -> Forma:
	"""Óvalo de mesa de reuniones: lados rectos y extremos en semicírculo (proporción 2 a 1)."""
	puntos: list[Punto] = []
	for k in range(lados_extremo + 1):
		angulo = -math.pi / 2 + math.pi * k / lados_extremo
		puntos.append((1.5 + 0.5 * math.cos(angulo), 0.5 + 0.5 * math.sin(angulo)))
	for k in range(lados_extremo + 1):
		angulo = math.pi / 2 + math.pi * k / lados_extremo
		puntos.append((0.5 + 0.5 * math.cos(angulo), 0.5 + 0.5 * math.sin(angulo)))
	return _poligono(
		puntos, "un óvalo alargado, de lados rectos y extremos redondos", "an elongated oval with straight sides and round ends"
	)


def regular(lados: int, giro: float = 0.0, es: str = "", en: str = "") -> Forma:
	"""Polígono regular: hexágono, octógono…"""
	puntos = [
		(math.cos(math.radians(giro) + 2 * math.pi * k / lados), math.sin(math.radians(giro) + 2 * math.pi * k / lados))
		for k in range(lados)
	]
	return _poligono(puntos, es or f"un polígono regular de {lados} lados", en or f"a regular polygon with {lados} sides")


def estrella(puntas: int = 5, interior: float = 0.5) -> Forma:
	"""Estrella de varias puntas, con una punta hacia delante."""
	puntos = []
	for k in range(puntas * 2):
		radio = 1.0 if k % 2 == 0 else interior
		angulo = math.pi / 2 + math.pi * k / puntas
		puntos.append((radio * math.cos(angulo), radio * math.sin(angulo)))
	return _poligono(puntos, f"una estrella de {puntas} puntas", f"a {puntas}-pointed star")


def semicirculo(lados: int = 8) -> Forma:
	"""Media luna: recta por detrás (contra la pared) y redonda por delante."""
	puntos = [(math.cos(math.pi - math.pi * k / lados), math.sin(math.pi * k / lados)) for k in range(lados + 1)]
	return _poligono(
		puntos, "un semicírculo, recto por detrás y redondo por delante", "a semicircle, straight at the back and round at the front"
	)


def cuarto_circulo(lados: int = 6) -> Forma:
	"""Cuarto de círculo con el rincón atrás a la izquierda (un plato de ducha de esquina)."""
	puntos: list[Punto] = [(0.0, 0.0)]
	puntos += [(math.cos(math.pi / 2 * k / lados), math.sin(math.pi / 2 * k / lados)) for k in range(lados + 1)]
	return _poligono(
		puntos, "un cuarto de círculo, con el rincón atrás a la izquierda", "a quarter circle with its corner at the back left"
	)


def arco(abertura: float = 180.0, grosor: float = 0.3, lados: int = 10) -> Forma:
	"""Banda curva que abomba hacia delante (un mostrador curvo)."""
	inicio = math.radians(90.0 + abertura / 2)
	fin = math.radians(90.0 - abertura / 2)
	fuera = [(math.cos(inicio + (fin - inicio) * k / lados), math.sin(inicio + (fin - inicio) * k / lados)) for k in range(lados + 1)]
	dentro = [((1 - grosor) * x, (1 - grosor) * y) for x, y in reversed(fuera)]
	return _poligono(fuera + dentro, "una banda curva que abomba hacia delante", "a curved band bulging towards the front")


def anillo_abierto(hueco: float = 70.0, grosor: float = 0.3, lados: int = 14) -> Forma:
	"""Anillo con una entrada por delante (bancos en rotonda)."""
	inicio = math.radians(90.0 + hueco / 2)
	fin = math.radians(90.0 - hueco / 2 + 360.0)
	fuera = [(math.cos(inicio + (fin - inicio) * k / lados), math.sin(inicio + (fin - inicio) * k / lados)) for k in range(lados + 1)]
	dentro = [((1 - grosor) * x, (1 - grosor) * y) for x, y in reversed(fuera)]
	return _poligono(fuera + dentro, "un anillo con una entrada por delante", "a ring with an opening at the front")


def trapecio(detras: float = 0.6) -> Forma:
	"""Trapecio: más estrecho por detrás que por delante."""
	a, b = (1 - detras) / 2, (1 + detras) / 2
	return _poligono([(a, 0), (b, 0), (1, 1), (0, 1)], "un trapecio, más estrecho por detrás", "a trapezoid, narrower at the back")


def triangulo() -> Forma:
	"""Triángulo con la punta hacia delante."""
	return _poligono([(0, 0), (1, 0), (0.5, 1)], "un triángulo con la punta hacia delante", "a triangle pointing to the front")


def rombo() -> Forma:
	"""Rombo."""
	return _poligono([(0.5, 0), (1, 0.5), (0.5, 1), (0, 0.5)], "un rombo", "a diamond")


def casita() -> Forma:
	"""Pentágono con forma de casa: la punta del tejado hacia atrás."""
	return _poligono([(0, 0.35), (0.5, 0), (1, 0.35), (1, 1), (0, 1)], "un pentágono con forma de casita", "a house-shaped pentagon")


def piano_de_cola() -> Forma:
	"""Piano de cola: teclado recto delante, lado izquierdo largo y cola curva hacia la derecha."""
	puntos = [(0, 1), (0, 0.06), (0.08, 0), (0.34, 0), (0.48, 0.07), (0.6, 0.27), (0.76, 0.42), (0.93, 0.5), (1, 0.6), (1, 1)]
	return _poligono(
		puntos, "la silueta de un piano de cola, con el teclado delante", "the outline of a grand piano, keyboard at the front"
	)


def vehiculo() -> Forma:
	"""Coche o furgoneta: rectángulo con el morro (delante) y la trasera achaflanados."""
	puntos = [(0.12, 0), (0.88, 0), (1, 0.07), (1, 0.85), (0.9, 0.96), (0.72, 1), (0.28, 1), (0.1, 0.96), (0, 0.85), (0, 0.07)]
	return _poligono(puntos, "la silueta de un vehículo, con el morro delante", "the outline of a vehicle, nose at the front")


def cama_con_cabecero() -> Forma:
	"""Cama con cabecero: el cabecero (detrás) sobresale a los lados del colchón."""
	puntos = [(0, 0), (1, 0), (1, 0.05), (0.94, 0.05), (0.94, 1), (0.06, 1), (0.06, 0.05), (0, 0.05)]
	return _poligono(puntos, "un rectángulo con un cabecero más ancho detrás", "a rectangle with a wider headboard at the back")


def gota() -> Forma:
	"""Gota: redonda detrás y en punta delante (un globo, una llama)."""
	puntos = [(0.5 + 0.5 * math.cos(math.pi * k / 8), 0.38 - 0.38 * math.sin(math.pi * k / 8)) for k in range(9)]
	puntos += [(0.08, 0.62), (0.5, 1.0), (0.92, 0.62)]
	return _poligono(puntos, "una gota, redonda detrás y en punta delante", "a teardrop, round at the back and pointed at the front")


def ondulada() -> Forma:
	"""Rectángulo de bordes ondulados (una alfombra voladora)."""
	puntos: list[Punto] = []
	for k in range(9):
		puntos.append((k / 8, 0.08 + 0.08 * math.sin(math.pi * k / 2)))
	for k in range(9):
		puntos.append((1 - k / 8, 0.92 + 0.08 * math.sin(math.pi * k / 2)))
	return _poligono(puntos, "un rectángulo de bordes ondulados", "a rectangle with wavy edges")


# ── Estados y acciones ───────────────────────────────────────────────────────

# estado → (nombre en español, nombre en inglés)
ESTADOS: dict[str, tuple[str, str]] = {
	"cerrado": ("Cerrado", "Closed"),
	"abierto": ("Abierto", "Open"),
	"apagado": ("Apagado", "Off"),
	"encendido": ("Encendido", "On"),
	"funcionando": ("Funcionando", "Running"),
	"libre": ("Libre", "Free"),
	"ocupado": ("Ocupado", "Occupied"),
	"rojo": ("Rojo: no cruces", "Red: do not cross"),
	"verde": ("Verde: puedes cruzar", "Green: you may cross"),
	"intermitente": ("Verde intermitente: se acaba el tiempo", "Flashing green: time is running out"),
	"ambar": ("Ámbar", "Amber"),
	"plegado": ("Plegado", "Folded"),
	"desplegado": ("Desplegado", "Unfolded"),
	"vacio": ("Vacío", "Empty"),
	"lleno": ("Lleno", "Full"),
	"parado": ("Parado", "Stopped"),
	"girando": ("Girando", "Turning"),
	"bloqueado": ("Bloqueado", "Locked"),
	"en_espera": ("En espera", "Waiting"),
	"llamando": ("Llamando", "Calling"),
	"hinchado": ("Hinchado", "Inflated"),
	"explotado": ("Explotado", "Popped"),
}

# acción → (nombre en español, nombre en inglés)
ACCIONES: dict[str, tuple[str, str]] = {
	"abrir": ("Abrir", "Open"),
	"cerrar": ("Cerrar", "Close"),
	"encender": ("Encender", "Switch on"),
	"apagar": ("Apagar", "Switch off"),
	"poner": ("Poner en marcha", "Start"),
	"parar": ("Parar", "Stop"),
	"sentarse": ("Sentarse", "Sit down"),
	"levantarse": ("Levantarse", "Stand up"),
	"tumbarse": ("Tumbarse", "Lie down"),
	"pulsar": ("Pulsar el botón", "Press the button"),
	"tocar": ("Tocar", "Touch"),
	"tocar_nota": ("Tocar una nota", "Play a note"),
	"golpear": ("Golpear", "Strike"),
	"beber": ("Beber", "Drink"),
	"abrir_grifo": ("Abrir el grifo", "Turn the tap on"),
	"cerrar_grifo": ("Cerrar el grifo", "Turn the tap off"),
	"tirar_cadena": ("Tirar de la cadena", "Flush"),
	"tirar_basura": ("Tirar algo dentro", "Throw something in"),
	"validar": ("Validar el billete", "Validate your ticket"),
	"pasar": ("Pasar", "Go through"),
	"comprar": ("Comprar", "Buy"),
	"sacar_billete": ("Sacar un billete", "Buy a ticket"),
	"llamar": ("Llamar", "Call"),
	"colgar": ("Colgar", "Hang up"),
	"escuchar": ("Escuchar la información", "Listen to the information"),
	"leer": ("Leer con los dedos", "Read by touch"),
	"plegar": ("Plegar", "Fold"),
	"desplegar": ("Desplegar", "Unfold"),
	"empujar": ("Empujar", "Push"),
	"coger": ("Coger", "Take"),
	"echar_carta": ("Echar una carta", "Post a letter"),
	"echar_moneda": ("Echar una moneda", "Drop a coin in"),
	"agitar": ("Agitar", "Shake"),
	"explotar": ("Explotar", "Pop"),
	"hinchar": ("Hinchar", "Inflate"),
	"sacar_dinero": ("Sacar dinero", "Withdraw cash"),
	"pagar": ("Pagar", "Pay"),
	"copiar": ("Hacer una copia", "Make a copy"),
	"imprimir": ("Imprimir", "Print"),
	"colgar_ropa": ("Colgar el abrigo", "Hang your coat"),
	"escribir": ("Escribir", "Write"),
	"encestar": ("Lanzar a canasta", "Shoot a basket"),
	"chutar": ("Chutar a puerta", "Shoot at goal"),
	"jugar": ("Jugar", "Play"),
	"subir": ("Subirse", "Climb on"),
	"bajar": ("Bajarse", "Climb down"),
	"pedir_deseo": ("Pedir un deseo", "Make a wish"),
	"recargar": ("Enchufar", "Plug in"),
	"desenchufar": ("Desenchufar", "Unplug"),
	"girar": ("Girar", "Spin"),
	"saludar": ("Saludar", "Wave"),
}

Accion = tuple[str, str | None, str | None, str | None]


def registrar_estados(nuevos: dict[str, tuple[str, str]]) -> None:
	"""Añade estados propios de un complemento a ``ESTADOS`` (nombre en español, nombre en inglés).

	Cada módulo registra aquí los suyos en lugar de tocar este fichero. Si la
	clave ya existe con otro texto se rechaza: el mismo estado no puede
	llamarse de dos maneras según el complemento.
	"""
	_registrar(ESTADOS, nuevos, "estado")


def registrar_acciones(nuevas: dict[str, tuple[str, str]]) -> None:
	"""Añade acciones propias de un complemento a ``ACCIONES`` (nombre en español, nombre en inglés)."""
	_registrar(ACCIONES, nuevas, "acción")


def _registrar(tabla: dict[str, tuple[str, str]], nuevos: dict[str, tuple[str, str]], clase: str) -> None:
	for clave, nombres in nuevos.items():
		if clave in tabla and tabla[clave] != tuple(nombres):
			raise ValueError(
				f"El {clase} «{clave}» ya existe como {tabla[clave]}; use esa clave tal cual o elija otra para {tuple(nombres)}."
			)
		tabla[clave] = (str(nombres[0]), str(nombres[1]))


def abrir(al_abrir: str = "puerta/abrir", al_cerrar: str = "puerta/cerrar") -> list[Accion]:
	"""Se abre y se cierra (empieza cerrado)."""
	return [("abrir", "cerrado", "abierto", al_abrir), ("cerrar", "abierto", "cerrado", al_cerrar)]


def encender(
	sonido: str | None = "sonidos/interruptor.flac", encendido: str = "encendido", verbo: tuple[str, str] = ("encender", "apagar")
) -> list[Accion]:
	"""Se enciende y se apaga (empieza apagado)."""
	return [(verbo[0], "apagado", encendido, sonido), (verbo[1], encendido, "apagado", sonido)]


def sentarse(sonido: str | None = "sonidos/sentarse.flac") -> list[Accion]:
	"""Asiento: sentarse y levantarse."""
	return [("sentarse", "libre", "ocupado", sonido), ("levantarse", "ocupado", "libre", None)]


def gesto(id_accion: str, sonido: str | None = None) -> list[Accion]:
	"""Acción suelta que no cambia el estado: pulsar, tocar, beber."""
	return [(id_accion, None, None, sonido)]


# ── Objetos ──────────────────────────────────────────────────────────────────

# material → sonido de serie del golpe
GOLPES: dict[str, str] = {
	"madera": "golpe/madera",
	"metal": "golpe/metal",
	"cristal": "golpe/cristal",
	"plastico": "golpe/plastico",
	"tela": "golpe/tela",
	"piedra": "golpe/piedra",
	"ladrillo": "golpe/ladrillo",
	"hormigon": "golpe/piedra",
	"ceramica": "golpe/piedra",
	"carton": "golpe/tela",
	"planta": "golpe/tela",
	"goma": "golpe/plastico",
	"papel": "golpe/tela",
	"cuero": "golpe/tela",
	"espuma": "golpe/tela",
	"cuerda": "golpe/tela",
	"red": "golpe/tela",
	"paja": "golpe/tela",
	"arena": "golpe/tela",
	"tierra": "golpe/piedra",
	"marmol": "golpe/piedra",
	"chapa": "golpe/metal",
	"fibra": "golpe/plastico",
	"mimbre": "golpe/madera",
	"corcho": "golpe/madera",
}

AMBITOS = {"i": ["interior"], "e": ["exterior"], "ie": ["interior", "exterior"], "ei": ["exterior", "interior"]}


@dataclass
class DefSerie:
	"""Un objeto de serie: su ficha en español y sus textos en inglés."""

	ficha: dict[str, Any]
	ingles: dict[str, Any]
	forma: Forma


@dataclass
class ComplementoSerie:
	"""Un complemento de serie completo, listo para escribirse en ``data/plugins``."""

	id: str
	nombre: str
	en_nombre: str
	descripcion: str
	en_descripcion: str
	# categoría → (nombre en español, nombre en inglés, color #RRGGBB de sus objetos)
	categorias: dict[str, tuple[str, str, str]]
	objetos: list[DefSerie] = field(default_factory=list)
	# subcategoría → (nombre en español, nombre en inglés). Agrupa los objetos dentro de su categoría.
	subcategorias: dict[str, tuple[str, str]] = field(default_factory=dict)
	# Lugares (claves de ``catalogo.LUGARES`` separadas por espacios) de los objetos que no digan otros.
	lugares: str = ""
	# categoría → estancias (claves de ``catalogo.ESTANCIAS`` separadas por espacios) de sus objetos que no digan otras.
	estancias_de: dict[str, str] = field(default_factory=dict)
	# Clasificación añadida después a objetos ya definidos: id del objeto → ``T(...)`` (la ponen las ampliaciones).
	taxonomia: dict[str, dict[str, Any]] = field(default_factory=dict)


def _terna(medida: Medida) -> list[float] | float:
	return [float(v) for v in medida] if isinstance(medida, tuple) else float(medida)


def _defecto(medida: Medida) -> float:
	return float(medida[1]) if isinstance(medida, tuple) else float(medida)


def _letra(id_objeto: str) -> str:
	partes = [p for p in id_objeto.split("_") if p]
	if len(partes) >= 2:
		return partes[0][0].upper() + partes[1][0].lower()
	return id_objeto[:2].capitalize()


def _lista(texto: str) -> list[str]:
	return [t.strip() for t in texto.split(",") if t.strip()]


def _metros(valor: float, punto: bool = False) -> str:
	texto = f"{valor:.2f}"
	return texto if punto else texto.replace(".", ",")


def O(  # noqa: N802 - nombre corto a propósito: se llama cientos de veces
	id_objeto: str,
	nombre: str,
	en: str,
	categoria: str,
	descripcion: str,
	en_descripcion: str,
	ancho: Medida,
	fondo: Medida,
	alto: Medida,
	*,
	et: str = "",
	en_et: str = "",
	v: tuple[tuple[str, str, str, float, float, float], ...] = (),
	forma: Forma = RECTANGULO,
	amb: str = "i",
	col: str = "suelo",
	mat: str = "madera",
	letra: str = "",
	color: str = "",
	bloquea: bool = True,
	base: float = 0.0,
	baston: bool = True,
	golpe: str | None = None,
	uso: str | None = None,
	propio: tuple | None = None,
	acc: list[Accion] | None = None,
	cont: bool = False,
	din: dict[str, Any] | None = None,
	suelo: str = "",
	aviso: tuple[str, str] | None = None,
	paso_libre: tuple[str, ...] = (),
	sub: str = "",
	fn: str = "",
	lug: str = "",
	est: str = "",
	frec: str = "",
	rg: str = "",
	obs: str = "",
	rel: str = "",
) -> DefSerie:
	"""Define un objeto de serie.

	``ancho``, ``fondo`` y ``alto`` son ``(mínimo, defecto, máximo)`` en metros
	o un número fijo. ``et`` y ``en_et`` son etiquetas separadas por comas.
	``v`` son variantes ``(id, nombre, nombre en inglés, ancho, fondo, alto)``.
	``amb``: «i», «e» o «ie». ``col``: colocaciones separadas por espacios.
	``propio`` es ``(sonido, volumen, radio)`` o ``(sonido, volumen, radio, estado)``.
	``acc`` es una lista de acciones ``(id, de, a, sonido)``; los estados se
	deducen de ellas, por orden de aparición. ``aviso`` es ``(español, inglés)``.

	Clasificación (ver ``T``): ``sub`` subcategoría, ``fn`` función, ``lug``
	lugares, ``est`` estancias, ``frec`` frecuencia, ``rg`` riesgos, ``obs``
	clase de obstáculo (solo si la deducida de las medidas no vale) y ``rel``
	objetos que suelen ir con él. Lo que se deje vacío lo rellena el
	complemento con sus valores por defecto al generar.
	"""
	ficha: dict[str, Any] = {
		"id": id_objeto,
		"nombre": nombre,
		"categoria": categoria,
		"etiquetas": _lista(et),
		"descripcion": descripcion,
		"ambito": AMBITOS[amb],
		"forma": forma.a_dict(),
		"medidas": {"ancho": _terna(ancho), "fondo": _terna(fondo), "alto": _terna(alto)},
	}
	ingles: dict[str, Any] = {"nombre": en, "descripcion": en_descripcion, "etiquetas": _lista(en_et)}
	if v:
		ficha["variantes"] = [{"id": i, "nombre": es, "ancho": a, "fondo": f, "alto": h} for i, es, _en, a, f, h in v]
		ingles["variantes"] = {i: en_v for i, _es, en_v, _a, _f, _h in v}
	ficha["colocacion"] = col.split()
	ficha["bloquea"] = bloquea
	ficha["altura_base"] = base
	ficha["detectable_baston"] = baston
	ficha["material"] = mat
	sonidos: dict[str, Any] = {"golpe": golpe or GOLPES[mat]}
	if uso:
		sonidos["uso"] = uso
	if propio:
		sonidos["propio"] = {"sonido": propio[0], "volumen": propio[1], "radio": propio[2]}
		if len(propio) > 3:
			sonidos["propio"]["estado"] = propio[3]
	ficha["sonidos"] = sonidos
	estados: list[str] = []
	acciones: list[dict[str, Any]] = []
	for id_accion, de, a, sonido in acc or []:
		accion: dict[str, Any] = {"id": id_accion, "nombre": ACCIONES[id_accion][0]}
		for clave, estado in (("de", de), ("a", a)):
			if estado:
				accion[clave] = estado
				if estado not in estados:
					estados.append(estado)
		if sonido:
			accion["sonido"] = sonido
		acciones.append(accion)
	for fase in (din or {}).get("fases", []):
		if fase["estado"] not in estados:
			estados.append(fase["estado"])
	if estados:
		ficha["estados"] = estados
	if acciones:
		ficha["acciones"] = acciones
		ingles["acciones"] = {accion["id"]: ACCIONES[accion["id"]][1] for accion in acciones}
	if paso_libre:
		ficha["paso_libre"] = list(paso_libre)
	ficha["contenedor"] = cont
	if din:
		ficha["dinamica"] = din
	if suelo:
		ficha["suelo"] = suelo
	if aviso:
		ficha["aviso"] = aviso[0]
		ingles["aviso"] = aviso[1]
	ficha["simbolo"] = {"letra": letra or _letra(id_objeto), "color": color}
	a, f = _defecto(ancho), _defecto(fondo)
	colgado_es = f", colgado a {_metros(base)} metros del suelo" if base > 0 else ""
	colgado_en = f", hanging {_metros(base, True)} metres above the floor" if base > 0 else ""
	ficha["imagen"] = {
		"fichero": f"imagenes/{id_objeto}.png",
		"descripcion": f"Huella en planta de «{nombre}»: {forma.es} de {_metros(a)} por {_metros(f)} metros{colgado_es}, con la letra «{ficha['simbolo']['letra']}».",
	}
	ingles["imagen"] = (
		f"Footprint of “{en}”: {forma.en}, {_metros(a, True)} by {_metros(f, True)} metres{colgado_en}, marked with the letters “{ficha['simbolo']['letra']}”."
	)
	try:
		ficha["_taxonomia"] = T(sub, fn, lug, est, frec, rg, obs, rel)
	except ValueError as error:
		raise ValueError(f"Objeto «{id_objeto}»: {error}") from error
	return DefSerie(ficha, ingles, forma)


def T(  # noqa: N802 - nombre corto a propósito
	sub: str = "",
	fn: str = "",
	lug: str = "",
	est: str = "",
	frec: str = "",
	rg: str = "",
	obs: str = "",
	rel: str = "",
) -> dict[str, Any]:
	"""Clasificación de un objeto: la de ``O(...)`` o la que se añade después a un objeto ya definido.

	``sub``: subcategoría (clave de ``ComplementoSerie.subcategorias``).
	``fn``: función (clave de ``catalogo.FUNCIONES``). ``lug`` y ``est``:
	lugares y estancias separados por espacios. ``frec``: «muy_comun»,
	«comun» u «ocasional». ``rg``: riesgos separados por espacios. ``obs``:
	clase de obstáculo, solo para corregir la que se deduce de las medidas.
	``rel``: ids de objetos relacionados separados por espacios.

	Aquí se rechaza cualquier valor que no sea de la taxonomía: un error al
	escribir se ve al generar y no llega al catálogo.
	"""
	datos: dict[str, Any] = {
		"subcategoria": sub,
		"funcion": fn,
		"lugares": lug.split(),
		"estancias": est.split(),
		"frecuencia": frec,
		"riesgos": rg.split(),
		"obstaculo": obs,
		"relacionados": rel.split(),
	}
	for clave, faceta, valores in (
		("fn", "funcion", [fn] if fn else []),
		("lug", "lugar", datos["lugares"]),
		("est", "estancia", datos["estancias"]),
		("frec", "frecuencia", [frec] if frec else []),
		("rg", "riesgo", datos["riesgos"]),
		("obs", "obstaculo", [obs] if obs else []),
	):
		for valor in valores:
			if valor not in cat.TAXONOMIAS[faceta]:
				raise ValueError(f"«{valor}» no es un valor de «{clave}». Valores admitidos: {', '.join(cat.TAXONOMIAS[faceta])}.")
	return datos


# Claves de clasificación de la ficha: la subcategoría va tras la categoría y el resto, antes del símbolo.
_ANTES_DE_SIMBOLO = ("funcion", "lugares", "estancias", "obstaculo", "riesgos", "frecuencia", "relacionados")
_OPCIONALES = ("riesgos", "relacionados")


def clasificar(serie: ComplementoSerie, definido: DefSerie, extra: dict[str, Any] | None = None) -> dict[str, Any]:
	"""La ficha de un objeto con su clasificación completa, lista para ``complemento.json``.

	Junta lo que dijo ``O(...)`` con ``extra`` (la tabla de clasificación de
	un complemento antiguo) y con los valores por defecto del complemento
	(lugares) y de la categoría (estancias). La clase de obstáculo se deduce
	de las medidas salvo que se haya corregido a mano. Lanza ``ValueError``
	si al objeto le queda sin rellenar algo obligatorio.
	"""
	ficha = dict(definido.ficha)
	taxonomia = dict(ficha.pop("_taxonomia", None) or T())
	for clave, valor in (extra or {}).items():
		if valor:
			taxonomia[clave] = valor
	id_objeto = ficha["id"]
	if not taxonomia["lugares"]:
		taxonomia["lugares"] = serie.lugares.split()
	if not taxonomia["estancias"]:
		taxonomia["estancias"] = serie.estancias_de.get(ficha["categoria"], "").split()
	taxonomia["frecuencia"] = taxonomia["frecuencia"] or cat.FRECUENCIA_SERIE
	alto = ficha["medidas"]["alto"]
	alto_defecto = float(alto[1]) if isinstance(alto, list) else float(alto)
	taxonomia["obstaculo"] = taxonomia["obstaculo"] or cat.deducir_obstaculo(ficha["bloquea"], ficha["altura_base"], alto_defecto)
	if taxonomia["subcategoria"] not in serie.subcategorias:
		raise ValueError(
			f"{serie.id}/{id_objeto}: la subcategoría «{taxonomia['subcategoria']}» no está en las subcategorías del complemento."
		)
	for clave in ("funcion", "lugares", "estancias"):
		if not taxonomia[clave]:
			raise ValueError(f"{serie.id}/{id_objeto}: falta «{clave}» en su clasificación.")
	for clave, faceta in (("lugares", "lugar"), ("estancias", "estancia")):
		for valor in taxonomia[clave]:
			if valor not in cat.TAXONOMIAS[faceta]:
				raise ValueError(f"{serie.id}/{id_objeto}: «{valor}» no es un valor de «{clave}».")
	propios = {d.ficha["id"] for d in serie.objetos}
	for relacionado in taxonomia["relacionados"]:
		if "/" not in relacionado and relacionado not in propios:
			raise ValueError(f"{serie.id}/{id_objeto}: su relacionado «{relacionado}» no existe en el complemento.")
	ordenada: dict[str, Any] = {}
	for clave, valor in ficha.items():
		if clave == "simbolo":
			for nueva in _ANTES_DE_SIMBOLO:
				if taxonomia[nueva] or nueva not in _OPCIONALES:
					ordenada[nueva] = taxonomia[nueva]
		ordenada[clave] = valor
		if clave == "categoria":
			ordenada["subcategoria"] = taxonomia["subcategoria"]
	return ordenada


def poligono(puntos: list[Punto], es: str, en: str) -> Forma:
	"""Forma a medida: un polígono cualquiera, que se encaja en el cuadrado 0..1."""
	return _poligono(puntos, es, en)


def S(nombre: str) -> str:  # noqa: N802 - nombre corto a propósito
	"""Ruta de un sonido propio del complemento: ``S("lavadora")`` → ``sonidos/lavadora.flac``."""
	return f"sonidos/{nombre}.flac"


@dataclass
class Ampliacion:
	"""Lo que un módulo ``<id>_ampliacion.py`` añade a un complemento ya publicado.

	Los seis complementos originales no se reescriben (hay entornos que usan
	sus objetos): su módulo se queda como estaba y la ampliación aporta, por
	separado, la clasificación de los objetos que ya existían (``taxonomia``:
	id del objeto → ``T(...)``), los objetos nuevos y las categorías y
	subcategorías que hagan falta.
	"""

	objetos: list[DefSerie] = field(default_factory=list)
	taxonomia: dict[str, dict[str, Any]] = field(default_factory=dict)
	categorias: dict[str, tuple[str, str, str]] = field(default_factory=dict)
	subcategorias: dict[str, tuple[str, str]] = field(default_factory=dict)
	lugares: str = ""
	estancias_de: dict[str, str] = field(default_factory=dict)
