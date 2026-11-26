"""Braille español de grado 1 para los planos táctiles y sus leyendas.

Un plano en relieve no puede llevar los nombres escritos en tinta: lleva
claves cortas en braille (un número por sala) y una leyenda aparte. Este
módulo, adaptado del proyecto de ciudades del mismo autor, da lo necesario:

- ``a_braille``: texto → braille Unicode, con el signo de número;
- ``a_brf``: braille Unicode → BRF, el ASCII braille que entienden las
  impresoras braille y muchas líneas braille;
- ``puntos_svg``: los puntos de un texto como círculos de un SVG, con las
  medidas habituales del braille en papel, para papel de microcápsulas
  (horno «fuser») o impresión en relieve.
"""

from __future__ import annotations

_LETRAS: dict[str, int] = {
	"a": 1,
	"b": 12,
	"c": 14,
	"d": 145,
	"e": 15,
	"f": 124,
	"g": 1245,
	"h": 125,
	"i": 24,
	"j": 245,
	"k": 13,
	"l": 123,
	"m": 134,
	"n": 1345,
	"o": 135,
	"p": 1234,
	"q": 12345,
	"r": 1235,
	"s": 234,
	"t": 2345,
	"u": 136,
	"v": 1236,
	"w": 2456,
	"x": 1346,
	"y": 13456,
	"z": 1356,
	"ñ": 12456,
	"á": 12356,
	"é": 2346,
	"í": 34,
	"ó": 346,
	"ú": 23456,
	"ü": 1256,
	"ç": 12346,
	"à": 12356,
	"è": 2346,
	"ò": 346,
	"ï": 34,
	",": 2,
	";": 23,
	":": 25,
	".": 3,
	"-": 36,
	"?": 26,
	"!": 235,
	"'": 3,
	"(": 126,
	")": 345,
	"/": 6,
	"º": 356,
	"«": 236,
	"»": 236,
	'"': 236,
	" ": 0,
}
_DIGITOS = {"1": "a", "2": "b", "3": "c", "4": "d", "5": "e", "6": "f", "7": "g", "8": "h", "9": "i", "0": "j"}
SIGNO_NUMERO = 3456
SIGNO_MAYUSCULA = 46

# Medidas del braille en papel, en milímetros.
PUNTO = 1.5
ENTRE_PUNTOS = 2.5
ENTRE_CELDAS = 6.0
ENTRE_LINEAS = 10.0
ALTO_CELDA = 2 * ENTRE_PUNTOS + PUNTO

# Tabla del ASCII braille norteamericano para las 64 celdas de seis puntos.
_BRF = " A1B'K2L@CIF/MSP\"E3H9O6R^DJG>NTQ,*5<-U8V.%[$+X!&;:4\\0Z7(_?W]#Y)="


def celda(puntos: int) -> str:
	"""«145» → ⠙: la celda braille con esos puntos, escritos como cifras."""
	valor = 0
	for cifra in str(puntos) if puntos else "":
		valor |= 1 << (int(cifra) - 1)
	return chr(0x2800 + valor)


def a_braille(texto: str, mayusculas: bool = False) -> str:
	"""Texto en braille Unicode. Los caracteres sin signo braille conocido se omiten."""
	salida: list[str] = []
	en_numero = False
	for caracter in texto:
		if caracter.isdigit() and caracter in _DIGITOS:
			if not en_numero:
				salida.append(celda(SIGNO_NUMERO))
				en_numero = True
			salida.append(celda(_LETRAS[_DIGITOS[caracter]]))
			continue
		if en_numero and caracter in ",.":
			# 1.000 o 2,5: el número sigue.
			salida.append(celda(_LETRAS[caracter]))
			continue
		en_numero = False
		minuscula = caracter.lower()
		if minuscula not in _LETRAS:
			continue
		if mayusculas and caracter != minuscula:
			salida.append(celda(SIGNO_MAYUSCULA))
		salida.append(celda(_LETRAS[minuscula]))
	return "".join(salida)


def a_brf(braille: str) -> str:
	"""Braille Unicode → BRF (ASCII braille)."""
	return "".join(_BRF[(ord(c) - 0x2800) & 0x3F] if 0x2800 <= ord(c) <= 0x28FF else c for c in braille)


def ancho_mm(braille: str) -> float:
	"""Anchura en milímetros de un texto braille en papel."""
	return max(0, len(braille) - 1) * ENTRE_CELDAS + ENTRE_PUNTOS + PUNTO


def puntos_svg(braille: str, x: float, y: float) -> list[str]:
	"""Círculos SVG de un texto braille con su esquina superior izquierda en (x, y), en milímetros."""
	salida: list[str] = []
	for numero, caracter in enumerate(braille):
		valor = ord(caracter) - 0x2800
		cx = x + numero * ENTRE_CELDAS + PUNTO / 2.0
		for punto in range(6):
			if valor & (1 << punto):
				columna, fila = (0, punto) if punto < 3 else (1, punto - 3)
				salida.append(
					f'<circle cx="{cx + columna * ENTRE_PUNTOS:.2f}" cy="{y + PUNTO / 2.0 + fila * ENTRE_PUNTOS:.2f}" r="{PUNTO / 2.0}" fill="black"/>'
				)
	return salida


def lineas_brf(parrafos: list[str], celdas_por_linea: int = 32) -> list[str]:
	"""Parte unos párrafos en líneas BRF que caben en una hoja braille (por palabras)."""
	lineas: list[str] = []
	for parrafo in parrafos:
		actual = ""
		for palabra in parrafo.split():
			candidato = f"{actual} {palabra}".strip()
			if actual and len(a_braille(candidato)) > celdas_por_linea:
				lineas.append(a_brf(a_braille(actual)))
				actual = palabra
			else:
				actual = candidato
		lineas.append(a_brf(a_braille(actual)))
	return lineas
