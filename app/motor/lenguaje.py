"""Frases de orientación: direcciones, distancias, giros y nombres, en el formato del alumno.

Todo lo que el motor dice sobre «dónde» y «cuánto» sale de aquí, para que
suene igual en cualquier ayuda: si el alumno eligió las horas del reloj y los
pasos, lo oye siempre así. Los formatos son claves estables (``reloj``,
``lados``, ``cardinal``, ``grados``) que nunca se traducen ni se comparan
con textos traducidos; lo traducible son las frases.

Los tres estilos de redacción (infantil, juvenil, adulto) solo cambian el
tono de unas pocas frases de ánimo; los datos de orientación son los mismos y
el modo adulto es sobrio.

Adaptado de ``texto.py`` de Reconocedor de Ciudades, del mismo autor.
"""

from __future__ import annotations

from app.core.configuracion import VALORES_POR_DEFECTO
from app.core.i18n import N_, _, _n
from app.dominio import geometria as geo
from app.dominio import modelo
from app.dominio.modelo import Abertura, Conector, Espacio, Planta

# Longitud del paso de serie: la de las preferencias (app.core.configuracion), única fuente de verdad.
PASO_DE_SERIE_M: float = float(VALORES_POR_DEFECTO["juego"]["paso_m"])

FORMATOS: tuple[str, ...] = ("reloj", "lados", "cardinal", "grados")
UNIDADES: tuple[str, ...] = ("metros", "pasos")
ESTILOS: tuple[str, ...] = ("infantil", "juvenil", "adulto")

# Los cuatro cuadrantes de «alrededor», como ángulos relativos.
CUADRANTES: tuple[float, ...] = (0.0, 90.0, 180.0, -90.0)


def normalizar_relativo(grados: float) -> float:
	"""El mismo ángulo entre -180 y 180 (positivo = a la derecha)."""
	return (grados + 180.0) % 360.0 - 180.0


def hora_reloj(relativo: float) -> str:
	"""Dirección relativa en horas de reloj (las 12 = de frente, las 3 = a la derecha)."""
	hora = round((relativo % 360.0) / 30.0) % 12 or 12
	# Traductores: la dirección como las horas del reloj (las 12 = de frente, las 3 = a la derecha).
	return _n("a la {h}", "a las {h}", hora).format(h=hora)


def lado(relativo: float) -> str:
	"""«delante», «a tu derecha», «detrás a la izquierda»…"""
	r = normalizar_relativo(relativo)
	a = abs(r)
	derecha = r > 0
	if a <= 22.5:
		return _("delante")
	if a >= 157.5:
		return _("detrás")
	if a < 67.5:
		return _("delante a la derecha") if derecha else _("delante a la izquierda")
	if a <= 112.5:
		return _("a tu derecha") if derecha else _("a tu izquierda")
	return _("detrás a la derecha") if derecha else _("detrás a la izquierda")


def grados_relativos(relativo: float) -> str:
	"""«30 grados a la derecha», «de frente»."""
	r = normalizar_relativo(relativo)
	if abs(r) < 5:
		return _("de frente")
	n = abs(round(r))
	if r > 0:
		return _n("{n} grado a la derecha", "{n} grados a la derecha", n).format(n=n)
	return _n("{n} grado a la izquierda", "{n} grados a la izquierda", n).format(n=n)


def giro(angulo: float) -> str:
	"""Instrucción de giro para un cambio de rumbo (positivo = a la derecha)."""
	a = abs(normalizar_relativo(angulo))
	derecha = normalizar_relativo(angulo) > 0
	if a < 20:
		return _("sigue recto")
	if a < 50:
		return _("gira ligeramente a la derecha") if derecha else _("gira ligeramente a la izquierda")
	if a < 135:
		return _("gira a la derecha") if derecha else _("gira a la izquierda")
	if a < 170:
		return _("gira muy cerrado a la derecha") if derecha else _("gira muy cerrado a la izquierda")
	return _("da media vuelta")


def lista(elementos: list[str]) -> str:
	"""«a, b y c», con la conjunción de cada idioma."""
	validos = [e for e in elementos if e]
	if len(validos) <= 1:
		return "".join(validos)
	# Traductores: el final de una lista: «la mesa, la silla y la puerta».
	return _("{lista} y {ultimo}").format(lista=", ".join(validos[:-1]), ultimo=validos[-1])


def mayuscula(texto: str) -> str:
	"""El texto con la primera letra en mayúscula (sin tocar el resto)."""
	return texto[:1].upper() + texto[1:] if texto else texto


def frase(*partes: str) -> str:
	"""Une trozos en una frase: primera letra en mayúscula y punto final."""
	texto = " ".join(p.strip() for p in partes if p and p.strip())
	if not texto:
		return ""
	texto = mayuscula(texto)
	return texto if texto[-1] in ".!?…" else texto + "."


# Textos de tono por estilo: clave estable → (infantil, juvenil, adulto).
_TONO: dict[str, tuple[str, str, str]] = {
	"inicio": (N_("¡Vamos a explorar!"), N_("Empieza la exploración."), N_("Comienza el recorrido.")),
	"espacio_nuevo": (N_("¡Sitio nuevo!"), N_("Lugar nuevo."), ""),
	"choque": (N_("¡Pum!"), "", ""),
	"llegada": (N_("¡Muy bien!"), N_("Hecho."), ""),
	"limite": (N_("Por aquí no se puede seguir."), N_("Fin de la zona."), N_("Aquí termina el entorno.")),
	"nada_que_usar": (N_("Aquí no hay nada que tocar."), N_("No hay nada que usar aquí."), N_("No hay nada que usar aquí.")),
	"ayuda_no": (
		N_("Esa ayuda ahora no se puede usar."),
		N_("Esa ayuda no está disponible en esta actividad."),
		N_("Esa ayuda no está disponible en esta actividad."),
	),
	"ayuda_agotada": (
		N_("Ya has gastado esa ayuda."),
		N_("Ya has usado esa ayuda todas las veces permitidas."),
		N_("Ya no quedan usos de esa ayuda."),
	),
	"trafico": (
		N_("¡Cuidado! Has cruzado con coches pasando."),
		N_("Atención: has cruzado con coches pasando."),
		N_("Has cruzado con coches pasando."),
	),
}


class Lenguaje:
	"""Dice direcciones y distancias en el formato, la unidad y el estilo del alumno."""

	def __init__(self, formato: str = "reloj", unidad: str = "metros", paso_m: float = PASO_DE_SERIE_M, estilo: str = "adulto") -> None:
		self.formato = formato if formato in FORMATOS else "reloj"
		self.unidad = unidad if unidad in UNIDADES else "metros"
		self.paso_m = max(0.25, float(paso_m))
		self.estilo = estilo if estilo in ESTILOS else "adulto"

	# ── Distancias ──

	def distancia(self, metros: float) -> str:
		"""«3 metros» o «4 pasos», según la unidad del alumno (los pasos, de su largo de paso)."""
		metros = max(0.0, float(metros))
		if self.unidad == "pasos":
			n = max(1, round(metros / self.paso_m))
			if n > 20:
				n = round(n / 5) * 5
			return _n("{n} paso", "{n} pasos", n).format(n=n)
		if metros < 0.75:
			return _("medio metro")
		if metros < 100:
			n = max(1, round(metros))
			return _n("{n} metro", "{n} metros", n).format(n=n)
		n = round(metros / 5) * 5
		return _n("{n} metro", "{n} metros", n).format(n=n)

	def pasos(self, metros: float) -> int:
		"""Número de pasos del alumno que caben en esa distancia (al menos uno)."""
		return max(1, round(max(0.0, metros) / self.paso_m))

	# ── Direcciones ──

	def cardinal(self, rumbo: float) -> str:
		"""«noreste», en el idioma elegido."""
		return geo.punto_cardinal(rumbo)

	def al_cardinal(self, rumbo: float) -> str:
		"""«al noreste»."""
		return _("al {punto}").format(punto=geo.punto_cardinal(rumbo))

	def direccion(self, relativo: float, absoluto: float) -> str:
		"""Una dirección en el formato elegido: «a las 2», «a tu derecha», «al este» o «40 grados a la derecha»."""
		if self.formato == "cardinal":
			return self.al_cardinal(absoluto)
		if self.formato == "lados":
			return lado(relativo)
		if self.formato == "grados":
			return grados_relativos(relativo)
		return hora_reloj(relativo)

	def direccion_a(self, origen: tuple[float, float], rumbo: float, destino: tuple[float, float]) -> str:
		"""Dirección hacia ``destino`` vista desde ``origen`` mirando a ``rumbo``."""
		absoluto = geo.rumbo_entre(origen, destino)
		return self.direccion(geo.diferencia_rumbos(rumbo, absoluto), absoluto)

	def lado(self, relativo: float) -> str:
		"""Siempre por lados («a tu izquierda»), para lo que está pegado al alumno."""
		return lado(relativo)

	def cuadrante(self, relativo: float, rumbo: float) -> str:
		"""Nombre de un cuadrante de «alrededor»: por lados, o por cardinales si ese es el formato."""
		if self.formato == "cardinal":
			return self.al_cardinal(rumbo + relativo)
		return lado(relativo)

	def rumbo(self, rumbo: float, con_grados: bool = False) -> str:
		"""«Miras al noreste» (con los grados si se piden)."""
		texto = _("Miras al {punto}").format(punto=geo.punto_cardinal(rumbo))
		if con_grados:
			n = round(rumbo) % 360
			texto += ", " + _n("{n} grado", "{n} grados", n).format(n=n)
		return texto + "."

	def giro(self, angulo: float) -> str:
		"""Instrucción de giro («gira a la derecha»)."""
		return giro(angulo)

	def a_distancia(self, nombre: str, metros: float, direccion: str = "") -> str:
		"""«Mesa, a 3 metros, a las 2»."""
		if direccion:
			return _("{nombre}, a {distancia}, {direccion}").format(nombre=nombre, distancia=self.distancia(metros), direccion=direccion)
		return _("{nombre} a {distancia}").format(nombre=nombre, distancia=self.distancia(metros))

	# ── Nombres ──

	def planta(self, planta: Planta | None) -> str:
		"""Nombre hablado de una planta."""
		if planta is None:
			return ""
		return planta.nombre or _("planta {nivel}").format(nivel=planta.nivel)

	def espacio(self, espacio: Espacio | None) -> str:
		"""Nombre hablado de un espacio (su tipo si no tiene nombre)."""
		if espacio is None:
			return _("zona sin nombre")
		return espacio.nombre or modelo.nombre_visible(modelo.TIPOS_ESPACIO, espacio.tipo)

	def suelo(self, suelo: str) -> str:
		"""Nombre hablado de un suelo."""
		return modelo.nombre_visible(modelo.SUELOS, suelo)

	def abertura(self, abertura: Abertura, estado: str = "", con_nombre: bool = True) -> str:
		"""«Puerta del baño, cerrada»; solo el tipo y el estado si no se quiere el nombre."""
		tipo = modelo.nombre_visible(modelo.TIPOS_ABERTURA, abertura.tipo)
		if abertura.tipo == "hueco":
			tipo = _("Hueco")
		if abertura.tipo in ("hueco", "ventana") or not estado:
			return abertura.nombre if con_nombre and abertura.nombre else tipo
		if not (con_nombre and abertura.nombre):
			# Sin nombre propio basta con el tipo y el estado, de corrido: «Puerta cerrada».
			if estado == "abierta":
				return _("{tipo} abierta").format(tipo=tipo) if abertura.tipo == "puerta" else _("{tipo} abierto").format(tipo=tipo)
			if estado == "con_llave":
				return (
					_("{tipo} cerrada con llave").format(tipo=tipo)
					if abertura.tipo == "puerta"
					else _("{tipo} cerrado con llave").format(tipo=tipo)
				)
			return _("{tipo} cerrada").format(tipo=tipo) if abertura.tipo == "puerta" else _("{tipo} cerrado").format(tipo=tipo)
		nombre = abertura.nombre
		if estado == "abierta":
			return _("{nombre}, abierta").format(nombre=nombre)
		if estado == "con_llave":
			return _("{nombre}, cerrada con llave").format(nombre=nombre)
		return _("{nombre}, cerrada").format(nombre=nombre)

	def conector(self, conector: Conector) -> str:
		"""Nombre hablado de una escalera, rampa o ascensor."""
		return conector.nombre or modelo.nombre_visible(modelo.TIPOS_CONECTOR, conector.tipo)

	def pasamanos(self, conector: Conector, sentido: int) -> str:
		"""Frase del pasamanos, vista por quien sube (``sentido`` 1) o baja (-1); vacía si no hay dato."""
		valor = str(conector.datos.get("pasamanos") or "")
		if valor == "ambos":
			return _("Pasamanos a los dos lados.")
		if valor == "ninguno":
			return _("Sin pasamanos.")
		if valor in ("izquierda", "derecha"):
			# El dato está dado subiendo: al bajar queda al otro lado.
			a_la_izquierda = (valor == "izquierda") == (sentido > 0)
			return _("Pasamanos a tu izquierda.") if a_la_izquierda else _("Pasamanos a tu derecha.")
		return ""

	# ── Tono ──

	def tono(self, clave: str) -> str:
		"""Frase de tono para el estilo del alumno (puede ser vacía: el adulto es sobrio)."""
		textos = _TONO.get(clave)
		if textos is None:
			return ""
		texto = textos[ESTILOS.index(self.estilo)]
		return _(texto) if texto else ""

	def con_tono(self, clave: str, texto: str) -> str:
		"""``texto`` precedido de su frase de tono, si el estilo la tiene."""
		previo = self.tono(clave)
		return f"{previo} {texto}".strip() if previo else texto
