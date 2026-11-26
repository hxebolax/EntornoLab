"""Plano de una planta en SVG, a escala, en dos variantes: visual y táctil.

- **Visual**: para quien ve o tiene resto visual, y para imprimir en tinta.
  Colores por tipo de espacio, nombres escritos donde caben, objetos con su
  letra, puertas en color, norte, escala y título.
- **Táctil**: para lámina en relieve (papel de microcápsulas y horno
  «fuser», o impresora de relieve). Trazo grueso, sin rellenos de color,
  tramas distintas por tipo de superficie, puertas marcadas como huecos con
  dos topes, claves cortas en braille en lugar de nombres y una página de
  leyenda aparte en texto (y en BRF para imprimirla en braille). Sigue las
  costumbres de los mapas táctiles: marco, esquina superior izquierda
  marcada para orientar la hoja, título y norte en braille y barra de escala.

En el papel de microcápsulas todo lo negro sube. Por eso, en la variante
táctil, lo que es solo para quien acompaña (los números en tinta) va en un
grupo aparte, ``id="tinta"``, en azul claro: se puede quitar antes de imprimir.

Las medidas del SVG son milímetros reales de la hoja (A4 o A3): imprimir al
100 %, sin «ajustar a la página», para que la escala indicada sea cierta.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from xml.sax.saxutils import escape

from app.core.i18n import N_, _, separador_decimal
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.formato import identificador_seguro
from app.dominio.geometria import Punto
from app.dominio.modelo import TIPOS_ESPACIO, Entorno, Espacio, Objeto, Planta, nombre_visible, segmentos_solidos
from app.exportar import braille
from app.importar.formas import punto_interior
from app.importar.georef import texto_atribucion

log = logging.getLogger(__name__)

VARIANTES = ("visual", "tactil")
# Tamaños de página en milímetros (ancho, alto) en vertical.
PAGINAS: dict[str, tuple[float, float]] = {"A4": (210.0, 297.0), "A3": (297.0, 420.0)}
ESCALAS = (10, 20, 25, 50, 75, 100, 125, 150, 200, 250, 300, 400, 500, 750, 1000, 1250, 1500, 2000, 2500, 5000, 10000, 25000)
MARGEN = 12.0
CABECERA = 16.0
PIE = 18.0

_COLORES: dict[str, str] = {
	"habitacion": "#fdf6e3",
	"pasillo": "#f1ead2",
	"vestibulo": "#f6efd9",
	"escalera": "#e3d9f0",
	"cabina": "#d9d9e8",
	"exterior": "#eeeeea",
	"acera": "#d9d9d9",
	"calzada": "#9a9a9a",
	"paso_peatones": "#f7f7f7",
	"plaza": "#e8dcc6",
	"parque": "#cfe6c0",
	"sendero": "#e6d8b8",
	"edificio": "#c9bfb2",
}
_COLOR_AGUA = "#b9d8ee"
_COLOR_TACTIL = "#f2c200"

# Tramas de la variante táctil: identificador → (definición SVG, descripción para la leyenda).
_TRAMAS: dict[str, tuple[str, str]] = {
	"t-calzada": (
		'<pattern id="t-calzada" width="4" height="4" patternUnits="userSpaceOnUse"><circle cx="2" cy="2" r="0.55" fill="black"/></pattern>',
		N_("Puntos separados: calzada, por donde pasan los coches."),
	),
	"t-edificio": (
		'<pattern id="t-edificio" width="3" height="3" patternUnits="userSpaceOnUse"><path d="M0,3 L3,0" stroke="black" stroke-width="0.6"/></pattern>',
		N_("Rayas inclinadas muy juntas: edificio macizo, en el que no se entra."),
	),
	"t-parque": (
		'<pattern id="t-parque" width="5" height="5" patternUnits="userSpaceOnUse"><path d="M2.5,0 L2.5,5" stroke="black" stroke-width="0.5"/></pattern>',
		N_("Rayas verticales separadas: parque o zona verde."),
	),
	"t-plaza": (
		'<pattern id="t-plaza" width="7" height="7" patternUnits="userSpaceOnUse"><path d="M0,3.5 L7,3.5 M3.5,0 L3.5,7" stroke="black" stroke-width="0.4"/></pattern>',
		N_("Cuadrícula amplia: plaza o zona peatonal."),
	),
	"t-agua": (
		'<pattern id="t-agua" width="6" height="3" patternUnits="userSpaceOnUse"><path d="M0,1.5 L6,1.5" stroke="black" stroke-width="0.5"/></pattern>',
		N_("Rayas horizontales: agua. No se pisa."),
	),
	"t-paso": (
		'<pattern id="t-paso" width="3.2" height="3.2" patternUnits="userSpaceOnUse"><rect x="0" y="0" width="1.6" height="3.2" fill="black"/></pattern>',
		N_("Bandas gruesas: paso de peatones."),
	),
	"t-escalera": (
		'<pattern id="t-escalera" width="2.2" height="2.2" patternUnits="userSpaceOnUse"><path d="M0,1.1 L2.2,1.1" stroke="black" stroke-width="0.45"/></pattern>',
		N_("Rayas horizontales muy juntas: escalera."),
	),
	"t-tactil": (
		'<pattern id="t-tactil" width="2" height="2" patternUnits="userSpaceOnUse"><circle cx="1" cy="1" r="0.45" fill="black"/></pattern>',
		N_("Puntos muy juntos: pavimento táctil."),
	),
}
_TRAMA_DE_TIPO = {
	"calzada": "t-calzada",
	"paso_peatones": "t-paso",
	"edificio": "t-edificio",
	"parque": "t-parque",
	"plaza": "t-plaza",
	"escalera": "t-escalera",
}


@dataclass
class PlanoSVG:
	"""Un plano generado: el SVG, su página de leyenda en texto y la escala a la que quedó."""

	svg: str
	leyenda: str
	escala: int
	pagina: str
	apaisado: bool
	variante: str
	claves: list[tuple[str, str]] = field(default_factory=list)

	def leyenda_brf(self, celdas_por_linea: int = 32) -> str:
		"""La leyenda en BRF, para imprimirla en braille junto a la lámina."""
		return "\r\n".join(braille.lineas_brf(self.leyenda.splitlines(), celdas_por_linea)) + "\r\n"


def _mm(valor: float) -> str:
	"""Número con dos decimales, como se escriben las medidas en el SVG."""
	return f"{valor:.2f}"


def _letras(numero: int) -> str:
	"""Clave de letras para referencias: a, b … z, aa, ab …"""
	texto = ""
	numero += 1
	while numero > 0:
		numero, resto = divmod(numero - 1, 26)
		texto = chr(ord("a") + resto) + texto
	return texto


class _Dibujo:
	"""Compone el SVG de una planta: calcula la escala, coloca cada elemento y arma la leyenda."""

	def __init__(
		self,
		entorno: Entorno,
		planta: Planta,
		variante: str,
		pagina: str,
		apaisado: bool | None,
		escala: int | None,
		catalogo: Catalogo | None,
	) -> None:
		if variante not in VARIANTES:
			raise ValueError(_("Variante de plano desconocida: «{valor}». Variantes: visual, tactil.").format(valor=variante))
		if pagina not in PAGINAS:
			raise ValueError(_("Tamaño de página desconocido: «{valor}». Tamaños: A4, A3.").format(valor=pagina))
		self.entorno = entorno
		self.planta = planta
		self.tactil = variante == "tactil"
		self.variante = variante
		self.pagina = pagina
		self.catalogo = catalogo
		self.partes: list[str] = []
		self.tinta: list[str] = []
		self.claves: list[tuple[str, str]] = []
		self.notas: list[str] = []
		self.tramas_usadas: list[str] = []
		x0, y0, x1, y1 = planta.caja()
		if x1 - x0 < 0.01 and y1 - y0 < 0.01:
			raise ValueError(_("La planta «{nombre}» está vacía: no hay nada que dibujar.").format(nombre=planta.nombre))
		self.caja = (x0 - 0.5, y0 - 0.5, x1 + 0.5, y1 + 0.5)
		ancho_m, alto_m = self.caja[2] - self.caja[0], self.caja[3] - self.caja[1]
		corto, largo = PAGINAS[pagina]
		opciones = (
			[(False, corto, largo), (True, largo, corto)]
			if apaisado is None
			else [(apaisado, largo, corto) if apaisado else (False, corto, largo)]
		)
		mejor: tuple[int, bool, float, float] | None = None
		for tumbado, ancho_p, alto_p in opciones:
			util_ancho, util_alto = ancho_p - 2 * MARGEN, alto_p - 2 * MARGEN - CABECERA - PIE
			necesario = max(ancho_m * 1000.0 / util_ancho, alto_m * 1000.0 / util_alto)
			elegida = next((e for e in ESCALAS if e >= necesario - 1e-9), ESCALAS[-1])
			if mejor is None or elegida < mejor[0]:
				mejor = (elegida, tumbado, ancho_p, alto_p)
		assert mejor is not None
		self.escala = int(escala) if escala else mejor[0]
		self.apaisado, self.ancho, self.alto = mejor[1], mejor[2], mejor[3]
		self.k = 1000.0 / self.escala
		self.cx = (self.caja[0] + self.caja[2]) / 2.0
		self.cy = (self.caja[1] + self.caja[3]) / 2.0
		self.centro_x = self.ancho / 2.0
		self.centro_y = MARGEN + CABECERA + (self.alto - 2 * MARGEN - CABECERA - PIE) / 2.0

	# ── Geometría ──

	def p(self, punto: Punto) -> tuple[float, float]:
		"""Punto del entorno (metros) → punto de la hoja (milímetros, con la y hacia abajo)."""
		return self.centro_x + (punto[0] - self.cx) * self.k, self.centro_y - (punto[1] - self.cy) * self.k

	def puntos(self, contorno: list[Punto]) -> str:
		"""Un contorno como valor del atributo ``points``."""
		return " ".join(f"{_mm(x)},{_mm(y)}" for x, y in (self.p(p) for p in contorno))

	def linea(self, a: Punto, b: Punto, color: str, grosor: float, extra: str = "") -> str:
		"""Elemento ``line`` entre dos puntos del entorno."""
		(x1, y1), (x2, y2) = self.p(a), self.p(b)
		return f'<line x1="{_mm(x1)}" y1="{_mm(y1)}" x2="{_mm(x2)}" y2="{_mm(y2)}" stroke="{color}" stroke-width="{grosor}" stroke-linecap="round"{extra}/>'

	def texto(self, x: float, y: float, texto: str, tamano: float, ancla: str = "middle", color: str = "black") -> str:
		"""Elemento ``text`` en un punto de la hoja (milímetros), con el texto escapado."""
		return f'<text x="{_mm(x)}" y="{_mm(y)}" font-size="{tamano:.2f}" text-anchor="{ancla}" font-family="Arial, Helvetica, sans-serif" fill="{color}">{escape(texto)}</text>'

	def huella(self, objeto: Objeto) -> list[Punto]:
		"""Forma real del objeto en el entorno: la del catálogo si lo hay, o su caja."""
		return self.catalogo.huella(objeto) if self.catalogo is not None else objeto.huella_caja()

	# ── Capas del dibujo ──

	def _trama(self, espacio: Espacio) -> str:
		trama = "t-agua" if espacio.suelo == "agua" else _TRAMA_DE_TIPO.get(espacio.tipo, "")
		if trama == "t-edificio" and not espacio.macizo:
			trama = ""
		if trama and trama not in self.tramas_usadas:
			self.tramas_usadas.append(trama)
		return trama

	def espacios(self) -> None:
		"""Superficies, de la mayor a la menor para que las pequeñas queden encima."""
		for espacio in sorted(self.planta.espacios, key=lambda e: -e.area()):
			if len(espacio.contorno) < 3:
				continue
			puntos = self.puntos(espacio.contorno)
			if self.tactil:
				if espacio.datos.get("terreno_base"):
					continue
				trama = self._trama(espacio)
				relleno = f"url(#{trama})" if trama else "white"
				borde = "none" if (espacio.cerrado or espacio.macizo) else "black"
				self.partes.append(f'<polygon points="{puntos}" fill="white" stroke="none"/>')
				self.partes.append(f'<polygon points="{puntos}" fill="{relleno}" stroke="{borde}" stroke-width="0.5"/>')
			else:
				color = _COLOR_AGUA if espacio.suelo == "agua" else _COLORES.get(espacio.tipo, "#f4f4f4")
				if espacio.datos.get("terreno_base"):
					color = "#f6f6f2"
				borde = "none" if (espacio.cerrado or espacio.macizo) else "#777777"
				self.partes.append(f'<polygon points="{puntos}" fill="{color}" stroke="{borde}" stroke-width="0.2"/>')
		for zona in self.planta.zonas:
			if len(zona.contorno) < 3:
				continue
			tactil = zona.suelo.startswith("tactil")
			if self.tactil:
				if tactil:
					if "t-tactil" not in self.tramas_usadas:
						self.tramas_usadas.append("t-tactil")
					self.partes.append(f'<polygon points="{self.puntos(zona.contorno)}" fill="white" stroke="none"/>')
					self.partes.append(
						f'<polygon points="{self.puntos(zona.contorno)}" fill="url(#t-tactil)" stroke="black" stroke-width="0.4"/>'
					)
			else:
				self.partes.append(
					f'<polygon points="{self.puntos(zona.contorno)}" fill="{_COLOR_TACTIL if tactil else "#e2e2e2"}" stroke="#666666" stroke-width="0.15"/>'
				)
		if not self.tactil:
			for via in self.planta.vias:
				if len(via.eje) >= 2:
					self.partes.append(
						f'<polyline points="{self.puntos(list(via.eje))}" fill="none" stroke="white" stroke-width="0.35" stroke-dasharray="2,2"/>'
					)

	def paredes(self) -> None:
		"""Muros: los lados de los espacios cerrados, las paredes sueltas y el contorno de los macizos."""
		grosor = 1.4 if self.tactil else 0.7
		for segmento in segmentos_solidos(self.planta, None, incluir_puertas_cerradas=False):
			# Una ventana no deja pasar: al tacto es pared (en visual se le pinta encima su color).
			if segmento.clase in ("pared", "macizo", "ventana"):
				self.partes.append(self.linea(segmento.a, segmento.b, "black", grosor))
		for pared in self.planta.paredes:
			if not pared.bloquea_paso:
				self.partes.append(self.linea(pared.a, pared.b, "black", 0.4, ' stroke-dasharray="1.5,1.5"'))

	def aberturas(self) -> None:
		"""Puertas, portales, huecos y ventanas."""
		for abertura in self.planta.aberturas:
			if geo.distancia(abertura.a, abertura.b) < 0.01:
				continue
			if self.tactil:
				if abertura.tipo == "ventana":
					continue
				# Un hueco en el muro con un tope a cada lado: es como se encuentra una puerta con el dedo.
				self.partes.append(self.linea(abertura.a, abertura.b, "white", 2.2))
				rumbo = geo.rumbo_entre(abertura.a, abertura.b)
				largo = 1.8 / self.k
				for extremo in (abertura.a, abertura.b):
					self.partes.append(
						self.linea(
							geo.punto_a_distancia(extremo, rumbo + 90.0, largo),
							geo.punto_a_distancia(extremo, rumbo - 90.0, largo),
							"black",
							0.8,
						)
					)
				if abertura.tipo in ("puerta", "portal") and abertura.estado != "abierta":
					self.partes.append(self.linea(abertura.a, abertura.b, "black", 0.35))
			elif abertura.tipo == "ventana":
				self.partes.append(self.linea(abertura.a, abertura.b, "#3b82c4", 0.9))
			elif abertura.tipo != "hueco":
				self.partes.append(self.linea(abertura.a, abertura.b, "white", 0.9))
				discontinua = ' stroke-dasharray="1,0.8"' if abertura.estado == "abierta" else ""
				self.partes.append(
					self.linea(abertura.a, abertura.b, "#a0522d" if abertura.tipo == "puerta" else "#c2410c", 0.6, discontinua)
				)

	def objetos(self) -> None:
		"""Objetos con su forma real; en visual, con la letra de su ficha."""
		cuenta: dict[tuple[str, str], int] = {}
		for objeto in self.planta.objetos:
			huella = self.huella(objeto)
			definicion = self.catalogo.definicion_de(objeto) if self.catalogo is not None else None
			letra = (definicion.letra() if definicion is not None else (objeto.nombre[:1] or "?")).upper()
			if self.tactil:
				self.partes.append(f'<polygon points="{self.puntos(huella)}" fill="black" stroke="black" stroke-width="0.3"/>')
			else:
				color = definicion.color() if definicion is not None else "#8b5a2b"
				self.partes.append(
					f'<polygon points="{self.puntos(huella)}" fill="{color}" fill-opacity="0.75" stroke="#333333" stroke-width="0.2"/>'
				)
				lado = min(objeto.ancho, objeto.fondo) * self.k
				if lado >= 2.2:
					x, y = self.p((objeto.x, objeto.y))
					tamano = min(3.0, lado * 0.7)
					self.partes.append(self.texto(x, y + tamano * 0.35, letra, tamano, color="white"))
			nombre = definicion.nombre if definicion is not None else (objeto.nombre or _("Objeto"))
			cuenta[(letra, nombre)] = cuenta.get((letra, nombre), 0) + 1
		if cuenta:
			if self.tactil:
				self.notas.append(_("Formas negras macizas: objetos y obstáculos, con su tamaño real."))
				self.notas.append(
					_("Objetos de esta planta: {lista}.").format(
						lista=", ".join(f"{nombre} ({veces})" for (_letra, nombre), veces in sorted(cuenta.items()))
					)
				)
			else:
				self.notas.append(
					_("Letras de los objetos: {lista}.").format(
						lista=", ".join(f"{letra}: {nombre} ({veces})" for (letra, nombre), veces in sorted(cuenta.items()))
					)
				)

	def _clave_braille(self, x: float, y: float, clave: str) -> None:
		"""Escribe una clave en braille centrada en (x, y) sobre un fondo blanco, y en tinta en su grupo."""
		celdas = braille.a_braille(clave)
		ancho = braille.ancho_mm(celdas)
		self.partes.append(
			f'<rect x="{_mm(x - ancho / 2 - 1)}" y="{_mm(y - braille.ALTO_CELDA / 2 - 1)}" width="{_mm(ancho + 2)}" height="{_mm(braille.ALTO_CELDA + 2)}" fill="white"/>'
		)
		self.partes.extend(braille.puntos_svg(celdas, x - ancho / 2, y - braille.ALTO_CELDA / 2))
		self.tinta.append(self.texto(x, y + braille.ALTO_CELDA / 2 + 3.2, clave, 2.4, color="#7fd0ff"))

	def rotulos(self) -> None:
		"""Nombres de los espacios (visual) o claves numéricas (táctil y espacios pequeños)."""
		numero = 0
		for espacio in sorted(self.planta.espacios, key=lambda e: -e.area()):
			if len(espacio.contorno) < 3 or espacio.datos.get("terreno_base") or not espacio.nombre:
				continue
			if espacio.tipo == "calzada" and not espacio.datos.get("cruce") and self.tactil:
				continue
			x0, y0, x1, y1 = espacio.caja()
			ancho_mm, alto_mm = (x1 - x0) * self.k, (y1 - y0) * self.k
			x, y = self.p(punto_interior(espacio.contorno))
			tipo = nombre_visible(TIPOS_ESPACIO, espacio.tipo).lower()
			if self.tactil:
				numero += 1
				clave = str(numero)
				if ancho_mm >= braille.ancho_mm(braille.a_braille(clave)) + 3.0 and alto_mm >= braille.ALTO_CELDA + 3.0:
					self._clave_braille(x, y, clave)
					self.claves.append((clave, f"{espacio.nombre} ({tipo})"))
				else:
					self.claves.append(
						(
							clave,
							_("{nombre} ({tipo}); demasiado pequeño para llevar la clave en el plano").format(
								nombre=espacio.nombre, tipo=tipo
							),
						)
					)
				continue
			tamano = min(3.2, ancho_mm * 0.9 / max(1.0, len(espacio.nombre) * 0.55), alto_mm * 0.6)
			claro = espacio.tipo == "calzada"
			if tamano >= 1.8:
				self.partes.append(self.texto(x, y + tamano * 0.35, espacio.nombre, tamano, color="white" if claro else "#111111"))
			else:
				numero += 1
				clave = str(numero)
				if min(ancho_mm, alto_mm) >= 2.4:
					self.partes.append(self.texto(x, y + 0.9, clave, 2.4, color="white" if claro else "#111111"))
				self.claves.append((clave, f"{espacio.nombre} ({tipo})"))

	def marcas(self) -> None:
		"""Referencias, fuentes de sonido, bocas de escalera y ascensor, y el punto de inicio."""
		orden = 0
		for referencia in self.planta.referencias:
			x, y = self.p((referencia.x, referencia.y))
			clave = _letras(orden)
			orden += 1
			if self.tactil:
				self.partes.append(f'<circle cx="{_mm(x)}" cy="{_mm(y)}" r="1.6" fill="black"/>')
				self.tinta.append(self.texto(x + 2.4, y + 0.9, clave, 2.4, "start", "#7fd0ff"))
			else:
				self.partes.append(
					f'<polygon points="{_mm(x)},{_mm(y - 1.5)} {_mm(x + 1.5)},{_mm(y)} {_mm(x)},{_mm(y + 1.5)} {_mm(x - 1.5)},{_mm(y)}" fill="#1f8a4c" stroke="white" stroke-width="0.2"/>'
				)
				self.partes.append(self.texto(x + 2.0, y + 0.8, clave, 2.2, "start", "#0f5c30"))
			self.claves.append((clave, referencia.nombre))
		if self.planta.referencias:
			self.notas.append(
				_("Círculos negros macizos: referencias (paradas, semáforos, portales, comercios).")
				if self.tactil
				else _("Rombos verdes con letra: referencias.")
			)
		for numero, fuente in enumerate(self.planta.fuentes, start=1):
			x, y = self.p((fuente.x, fuente.y))
			clave = f"s{numero}"
			if not self.tactil:
				self.partes.append(f'<circle cx="{_mm(x)}" cy="{_mm(y)}" r="1.3" fill="#c0392b" stroke="white" stroke-width="0.2"/>')
				self.partes.append(self.texto(x + 2.0, y + 0.8, clave, 2.2, "start", "#8e2319"))
			self.claves.append((clave, _("{nombre} (fuente de sonido)").format(nombre=fuente.nombre)))
		if self.planta.fuentes and not self.tactil:
			self.notas.append(_("Círculos rojos: fuentes de sonido."))
		for conector in self.entorno.conectores:
			for posicion in conector.posiciones():
				if posicion.planta != self.planta.id:
					continue
				x, y = self.p(posicion.punto)
				self.partes.append(
					f'<rect x="{_mm(x - 1.8)}" y="{_mm(y - 1.8)}" width="3.6" height="3.6" fill="{"black" if self.tactil else "#6b4fa0"}" stroke="white" stroke-width="0.3"/>'
				)
				if not self.tactil:
					self.partes.append(self.texto(x, y + 0.9, (conector.nombre[:1] or "E").upper(), 2.4, color="white"))
				clave = _("Cuadrado: {nombre}").format(nombre=conector.nombre)
				if all(clave != otra for otra, _descripcion in self.claves):
					self.claves.append((clave, _("boca de escalera o de rampa, o parada de ascensor")))
		if self.entorno.inicio.planta == self.planta.id and not self.tactil:
			x, y = self.p(self.entorno.inicio.punto)
			giro = self.entorno.inicio.rumbo
			self.partes.append(
				f'<polygon points="0,-2.4 1.7,1.8 0,0.9 -1.7,1.8" transform="translate({_mm(x)},{_mm(y)}) rotate({giro:.1f})" fill="#d62828" stroke="white" stroke-width="0.25"/>'
			)
			self.notas.append(_("Flecha roja: punto de inicio y hacia dónde se mira."))

	def decoracion(self) -> list[str]:
		"""Marco, título, norte, barra de escala y atribución: lo que rodea al dibujo."""
		partes: list[str] = []
		interior = MARGEN / 2.0
		partes.append(
			f'<rect x="{_mm(interior)}" y="{_mm(interior)}" width="{_mm(self.ancho - MARGEN)}" height="{_mm(self.alto - MARGEN)}" fill="none" stroke="black" stroke-width="{0.6 if self.tactil else 0.3}"/>'
		)
		titulo = f"{self.entorno.nombre} · {self.planta.nombre}" if self.planta.nombre else self.entorno.nombre
		norte_x, norte_y = self.ancho - MARGEN - 7.0, MARGEN + 8.0
		partes.append(
			f'<polygon points="{_mm(norte_x)},{_mm(norte_y - 6)} {_mm(norte_x - 3.5)},{_mm(norte_y + 3)} {_mm(norte_x + 3.5)},{_mm(norte_y + 3)}" fill="black"/>'
		)
		metros_barra = next((m for m in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000) if m * self.k >= 18.0), 1000)
		barra = metros_barra * self.k
		barra_x, barra_y = MARGEN, self.alto - MARGEN - 4.0
		partes.append(
			f'<line x1="{_mm(barra_x)}" y1="{_mm(barra_y)}" x2="{_mm(barra_x + barra)}" y2="{_mm(barra_y)}" stroke="black" stroke-width="{1.6 if self.tactil else 0.8}"/>'
		)
		for extremo in (barra_x, barra_x + barra):
			partes.append(
				f'<line x1="{_mm(extremo)}" y1="{_mm(barra_y - 2.5)}" x2="{_mm(extremo)}" y2="{_mm(barra_y + 2.5)}" stroke="black" stroke-width="{1.2 if self.tactil else 0.6}"/>'
			)
		etiqueta = _("{metros} m").format(metros=metros_barra)
		atribucion = texto_atribucion(self.entorno.procedencia)
		if self.tactil:
			# Esquina superior izquierda rellena: al tacto se sabe cómo va la hoja.
			partes.append(
				f'<polygon points="{_mm(interior)},{_mm(interior)} {_mm(interior + 12)},{_mm(interior)} {_mm(interior)},{_mm(interior + 12)}" fill="black"/>'
			)
			celdas = braille.a_braille(titulo[: int((self.ancho - 2 * MARGEN - 40) / braille.ENTRE_CELDAS)])
			partes.extend(braille.puntos_svg(celdas, interior + 15.0, MARGEN))
			partes.extend(braille.puntos_svg(braille.a_braille("n"), norte_x - 2.0, norte_y + 5.0))
			partes.extend(braille.puntos_svg(braille.a_braille(etiqueta), barra_x, barra_y - 11.0))
			self.tinta.append(
				self.texto(
					self.ancho / 2.0,
					self.alto - MARGEN + 2.0,
					_("{titulo}. Escala 1:{escala}.").format(titulo=titulo, escala=self.escala) + (" " + atribucion if atribucion else ""),
					2.4,
					color="#7fd0ff",
				)
			)
		else:
			partes.append(self.texto(MARGEN, MARGEN + 6.0, titulo, 5.0, "start"))
			partes.append(
				self.texto(
					MARGEN, MARGEN + 11.5, _("Escala 1:{escala}. Imprimir al 100 %.").format(escala=self.escala), 2.8, "start", "#444444"
				)
			)
			partes.append(self.texto(norte_x, norte_y + 7.5, "N", 3.5))
			partes.append(self.texto(barra_x + barra + 2.5, barra_y + 1.2, etiqueta, 3.0, "start"))
			if atribucion:
				partes.append(self.texto(self.ancho - MARGEN, self.alto - MARGEN - 2.0, atribucion, 2.6, "end", "#333333"))
		return partes

	def leyenda(self) -> str:
		"""Página de leyenda en texto: qué es cada cosa y a qué nombre corresponde cada clave."""
		titulo = f"{self.entorno.nombre}, {self.planta.nombre}" if self.planta.nombre else self.entorno.nombre
		centimetro = self.escala / 100.0
		lineas = [
			_("Leyenda del plano táctil de {titulo}.").format(titulo=titulo)
			if self.tactil
			else _("Leyenda del plano de {titulo}.").format(titulo=titulo),
			_("Escala 1:{escala}: un centímetro del plano son {metros} metros. Hoja {pagina} {orientacion}.").format(
				escala=self.escala,
				metros=f"{centimetro:g}".replace(".", separador_decimal()),
				pagina=self.pagina,
				orientacion=_("apaisada") if self.apaisado else _("vertical"),
			),
			_("El norte está arriba. Arriba a la derecha hay una flecha que lo señala."),
		]
		if self.tactil:
			lineas.append(
				_("La esquina de arriba a la izquierda está rellena: sirve para colocar la hoja. A su derecha, el título en braille.")
			)
			lineas.append(_("Abajo a la izquierda, una barra con la escala y su medida en braille."))
			lineas.append(
				_(
					"Líneas gruesas: paredes y fachadas. Un hueco en la pared con un tope a cada lado: una puerta; si lleva una línea fina, está cerrada."
				)
			)
			lineas.append(_("Líneas finas: bordes de zonas sin pared, como aceras y plazas."))
			lineas.extend(_(_TRAMAS[trama][1]) for trama in self.tramas_usadas)
			lineas.append(_("Los números en braille del plano son claves; su significado está más abajo."))
		else:
			lineas.append(
				_("Líneas negras: paredes y fachadas. Tramos marrones: puertas. Tramos naranjas: portales. Tramos azules: ventanas.")
			)
		lineas.extend(self.notas)
		if self.claves:
			lineas.append("")
			lineas.append(_("Claves:"))
			lineas.extend(f"{clave}: {nombre}" if nombre else clave for clave, nombre in self.claves)
		atribucion = texto_atribucion(self.entorno.procedencia)
		if atribucion:
			lineas.append("")
			lineas.append(_("Datos del mapa: {atribucion}.").format(atribucion=atribucion))
		return "\n".join(lineas) + "\n"

	def generar(self) -> PlanoSVG:
		"""Dibuja todo en su orden (de abajo arriba) y devuelve el plano con su leyenda."""
		self.espacios()
		self.paredes()
		self.aberturas()
		self.objetos()
		self.rotulos()
		self.marcas()
		decoracion = self.decoracion()
		titulo = f"{self.entorno.nombre} · {self.planta.nombre}"
		util_x, util_y = MARGEN, MARGEN + CABECERA
		util_ancho, util_alto = self.ancho - 2 * MARGEN, self.alto - 2 * MARGEN - CABECERA - PIE
		documento = [
			'<?xml version="1.0" encoding="UTF-8"?>',
			f'<svg xmlns="http://www.w3.org/2000/svg" width="{_mm(self.ancho)}mm" height="{_mm(self.alto)}mm" viewBox="0 0 {_mm(self.ancho)} {_mm(self.alto)}" role="img" aria-labelledby="titulo descripcion">',
			f'<title id="titulo">{escape(titulo)}</title>',
			f'<desc id="descripcion">{escape(_("Plano {variante} a escala 1:{escala}. La descripción completa está en la leyenda en texto que lo acompaña.").format(variante=_("táctil") if self.tactil else _("visual"), escala=self.escala))}</desc>',
			"<defs>",
			f'<clipPath id="zona"><rect x="{_mm(util_x)}" y="{_mm(util_y)}" width="{_mm(util_ancho)}" height="{_mm(util_alto)}"/></clipPath>',
		]
		documento.extend(_TRAMAS[trama][0] for trama in self.tramas_usadas)
		documento.append("</defs>")
		documento.append(f'<rect x="0" y="0" width="{_mm(self.ancho)}" height="{_mm(self.alto)}" fill="white"/>')
		documento.append('<g id="plano" clip-path="url(#zona)">')
		documento.extend(self.partes)
		documento.append("</g>")
		documento.append('<g id="marco">')
		documento.extend(decoracion)
		documento.append("</g>")
		if self.tinta:
			documento.append('<g id="tinta">')
			documento.extend(self.tinta)
			documento.append("</g>")
		documento.append("</svg>")
		return PlanoSVG(
			"\n".join(documento) + "\n", self.leyenda(), self.escala, self.pagina, self.apaisado, self.variante, list(self.claves)
		)


def plano_svg(
	entorno: Entorno,
	planta: Planta,
	variante: str = "visual",
	pagina: str = "A4",
	apaisado: bool | None = None,
	escala: int | None = None,
	catalogo: Catalogo | None = None,
) -> PlanoSVG:
	"""Plano de una planta en SVG, a escala, con su leyenda en texto.

	Sin ``escala`` se elige la mayor escala normalizada con la que la planta
	cabe en la hoja; sin ``apaisado`` se elige la orientación que da el plano
	más grande. ``variante`` es ``visual`` o ``tactil``.
	"""
	return _Dibujo(entorno, planta, variante, pagina, apaisado, escala, catalogo).generar()


def guardar_planos(
	entorno: Entorno, carpeta: str | os.PathLike[str], variante: str = "visual", pagina: str = "A4", catalogo: Catalogo | None = None
) -> list[Path]:
	"""Escribe el plano de cada planta en ``carpeta``: el SVG, su leyenda ``.txt`` y, en táctil, la leyenda ``.brf``.

	Devuelve los ficheros escritos. Las plantas vacías se saltan.
	"""
	destino = Path(carpeta)
	destino.mkdir(parents=True, exist_ok=True)
	escritos: list[Path] = []
	base = identificador_seguro(entorno.nombre or entorno.id, "entorno")
	for planta in entorno.plantas:
		try:
			plano = plano_svg(entorno, planta, variante, pagina, catalogo=catalogo)
		except ValueError as error:
			log.info("No se dibuja la planta %s: %s", planta.id, error)
			continue
		nombre = f"{base}_{identificador_seguro(planta.nombre or planta.id, 'planta')}_{variante}"
		ruta_svg = destino / f"{nombre}.svg"
		ruta_svg.write_text(plano.svg, encoding="utf-8", newline="\n")
		ruta_leyenda = destino / f"{nombre}_leyenda.txt"
		ruta_leyenda.write_text(plano.leyenda, encoding="utf-8", newline="\n")
		escritos.extend((ruta_svg, ruta_leyenda))
		if variante == "tactil":
			ruta_brf = destino / f"{nombre}_leyenda.brf"
			ruta_brf.write_text(plano.leyenda_brf(), encoding="ascii", errors="replace", newline="")
			escritos.append(ruta_brf)
	return escritos
