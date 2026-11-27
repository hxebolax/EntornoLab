"""Geometría del plano gráfico, sin wx.

El plano gráfico (``app/ui/plano.py``) solo pinta y recoge el ratón; lo que
hay que calcular vive aquí para poder probarlo sin abrir ninguna ventana:

- ``VistaPlano``: paso de metros del entorno a píxeles de la pantalla y al
  revés, con zoom y desplazamiento;
- ``figuras_de_planta``: la lista ordenada de lo que hay que dibujar;
- ``elemento_en``: qué elemento hay bajo un punto (para el clic);
- el ajuste a la cuadrícula, el desplazamiento de un arrastre y el tramo de
  la regla de escala.

Convenciones: en el entorno la x crece al este y la y al norte; en la
pantalla la y crece hacia abajo. Por eso el norte queda arriba en el plano.
"""

from __future__ import annotations

import dataclasses
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.i18n import _, _n
from app.dominio import geometria as geo
from app.dominio.diferencias import Afectados
from app.dominio.geometria import Punto
from app.dominio.modelo import Entorno, Objeto, Planta
from app.ui.esquemas import texto_numero

log = logging.getLogger(__name__)

ESCALA_MINIMA = 1.0  # píxeles por metro: un barrio entero en pantalla
ESCALA_MAXIMA = 2000.0  # dos píxeles por milímetro: más no enseña nada nuevo
MARGEN_ENCAJE = 0.08  # fracción de la ventana que se deja libre alrededor al encajar

POLIGONO = "poligono"
LINEA = "linea"
PUNTO = "punto"

# Orden de pintado, de abajo arriba. Los elementos pequeños y puntuales van
# encima: son los que se pintan los últimos y los que gana el clic.
ORDEN_ESPACIO = 10.0
ORDEN_ZONA = 20.0
ORDEN_VIA = 25.0
ORDEN_RUTA = 27.0
ORDEN_PARED = 30.0
ORDEN_ABERTURA = 40.0
ORDEN_OBJETO = 50.0
ORDEN_CONECTOR = 60.0
ORDEN_FUENTE = 70.0
ORDEN_REFERENCIA = 72.0
ORDEN_INICIO = 80.0
ORDEN_PREMIO = 90.0


@dataclass
class Figura:
	"""Una cosa que se dibuja en el plano, ya con sus puntos en metros.

	``id`` es el del elemento del entorno (vacío en lo que no se puede
	seleccionar: el punto de inicio, una ruta, un premio). ``clase`` dice qué
	es (espacio, pared, abertura, objeto, fuente, referencia, zona, via,
	conector, inicio, premio, ruta) y ``tipo`` su variedad dentro de la clase
	(puerta, ventana, acera…), que es lo que decide la trama y el símbolo.
	"""

	id: str
	clase: str
	forma: str
	puntos: list[Punto]
	rotulo: str = ""
	letra: str = ""
	color: str = ""
	orden: float = 0.0
	tipo: str = ""
	datos: dict[str, Any] = field(default_factory=dict)
	# Superficie de un espacio (decide el orden de pintado): guardada para no recalcularla al reutilizar la figura.
	area: float = field(default=0.0, compare=False, repr=False)

	@property
	def seleccionable(self) -> bool:
		"""True si corresponde a un elemento del entorno que se puede elegir con un clic."""
		return bool(self.id)

	def caja(self) -> tuple[float, float, float, float]:
		"""Caja envolvente en metros."""
		return geo.caja(self.puntos)

	def centro(self) -> Punto:
		"""Punto donde va su rótulo: el centro de gravedad de un polígono o el medio de sus puntos."""
		if self.forma == POLIGONO and len(self.puntos) >= 3:
			return geo.centroide(self.puntos)
		x0, y0, x1, y1 = self.caja()
		return (x0 + x1) / 2.0, (y0 + y1) / 2.0


# ── Vista ────────────────────────────────────────────────────────────────────


@dataclass
class VistaPlano:
	"""Qué trozo del entorno se ve y a qué escala.

	``escala`` son píxeles por metro; (``origen_x``, ``origen_y``) es el punto
	del entorno que cae en la esquina superior izquierda de la pantalla.
	"""

	escala: float = 40.0
	origen_x: float = 0.0
	origen_y: float = 0.0
	ancho: int = 1
	alto: int = 1

	def a_pantalla(self, x: float, y: float) -> tuple[float, float]:
		"""Metros del entorno → píxeles (la y se invierte: el norte queda arriba)."""
		return (x - self.origen_x) * self.escala, (self.origen_y - y) * self.escala

	def a_mundo(self, px: float, py: float) -> Punto:
		"""Píxeles → metros del entorno."""
		return self.origen_x + px / self.escala, self.origen_y - py / self.escala

	def encajar(self, caja: tuple[float, float, float, float], ancho_px: int, alto_px: int) -> None:
		"""Elige escala y origen para que ``caja`` (x0, y0, x1, y1 en metros) quepa entera y centrada."""
		self.ancho, self.alto = max(1, int(ancho_px)), max(1, int(alto_px))
		x0, y0, x1, y1 = caja
		ancho_m, alto_m = max(x1 - x0, 0.5), max(y1 - y0, 0.5)
		util = 1.0 - 2.0 * MARGEN_ENCAJE
		escala = min(self.ancho * util / ancho_m, self.alto * util / alto_m)
		self.escala = max(ESCALA_MINIMA, min(ESCALA_MAXIMA, escala))
		centro_x, centro_y = (x0 + x1) / 2.0, (y0 + y1) / 2.0
		self.origen_x = centro_x - self.ancho / (2.0 * self.escala)
		self.origen_y = centro_y + self.alto / (2.0 * self.escala)

	def zoom(self, factor: float, px: float, py: float) -> None:
		"""Amplía o reduce dejando quieto el punto que hay bajo (px, py): se acerca «a donde se mira»."""
		x, y = self.a_mundo(px, py)
		self.escala = max(ESCALA_MINIMA, min(ESCALA_MAXIMA, self.escala * factor))
		self.origen_x = x - px / self.escala
		self.origen_y = y + py / self.escala

	def desplazar(self, dx: float, dy: float) -> None:
		"""Arrastra el plano (dx, dy) píxeles: lo que estaba bajo el ratón le sigue."""
		self.origen_x -= dx / self.escala
		self.origen_y += dy / self.escala

	def redimensionar(self, ancho_px: int, alto_px: int) -> None:
		"""Apunta el tamaño nuevo de la ventana sin mover lo que se ve."""
		self.ancho, self.alto = max(1, int(ancho_px)), max(1, int(alto_px))


# ── Figuras ──────────────────────────────────────────────────────────────────


def _actividad_en_planta(dato: Any, planta: Planta) -> bool:
	return isinstance(dato, dict) and dato.get("planta") in (planta.id, None, "")


def _numero(valor: Any) -> float | None:
	try:
		numero = float(valor)
	except TypeError, ValueError:
		return None
	return numero if math.isfinite(numero) else None


def _reutilizables(previas: Sequence[Figura] | None, afectados: Afectados | None) -> dict[tuple[str, str], Figura] | None:
	"""Las figuras de la vez anterior por (clase, id), o None si no se pueden reutilizar (ids repetidos, plantas nuevas)."""
	if previas is None or afectados is None or afectados.estructura:
		return None
	tabla: dict[tuple[str, str], Figura] = {}
	for figura in previas:
		if not figura.id:
			continue
		clave = (figura.clase, figura.id)
		if clave in tabla:
			return None
		tabla[clave] = figura
	return tabla


def figuras_de_planta(
	entorno: Entorno,
	planta: Planta,
	catalogo: Any = None,
	actividad: dict[str, Any] | None = None,
	previas: Sequence[Figura] | None = None,
	afectados: Afectados | None = None,
) -> list[Figura]:
	"""Todo lo que hay que dibujar de una planta, ordenado de abajo arriba.

	Los espacios van del más grande al más pequeño para que un paso de
	peatones se vea (y se pueda pinchar) encima de su calzada. Los objetos
	salen con su HUELLA real del catálogo, su letra y su color; sin catálogo,
	o si falta el complemento, con su caja y la inicial de su nombre.

	Con ``previas`` (las figuras de ESTA planta en el estado de justo antes) y
	``afectados`` (lo que el parche del historial dice que ha cambiado), se
	reutilizan las figuras de lo que no ha cambiado y solo se rehacen las de
	los elementos afectados: con miles de espacios y objetos, calcular cada
	huella del catálogo tras cada edición era la mayor parte del tiempo del
	plano. El resultado es igual al de calcularlo todo.
	"""
	reutilizables = _reutilizables(previas, afectados)
	cambiados = afectados.elementos.get(planta.id, set()) if reutilizables is not None and afectados is not None else set()

	def previa(clase: str, elemento: Any) -> Figura | None:
		if reutilizables is None or elemento.id in cambiados:
			return None
		return reutilizables.get((clase, elemento.id))

	figuras: list[Figura] = []
	espacios: list[tuple[float, Any, Figura | None]] = []
	for espacio in planta.espacios:
		if len(espacio.contorno) >= 3:
			hecha = previa("espacio", espacio)
			espacios.append((hecha.area if hecha is not None else espacio.area(), espacio, hecha))
	espacios.sort(key=lambda trio: trio[0], reverse=True)
	for indice, (area, espacio, hecha) in enumerate(espacios):
		orden = ORDEN_ESPACIO + indice * 0.001
		if hecha is None:
			hecha = Figura(
				espacio.id,
				"espacio",
				POLIGONO,
				list(espacio.contorno),
				rotulo=espacio.nombre,
				orden=orden,
				tipo=espacio.tipo,
				datos={"cerrado": espacio.cerrado, "lados_abiertos": list(espacio.lados_abiertos), "macizo": espacio.macizo},
				area=area,
			)
		elif hecha.orden != orden:
			hecha = dataclasses.replace(hecha, orden=orden)
		figuras.append(hecha)
	for zona in planta.zonas:
		if len(zona.contorno) >= 3:
			hecha = previa("zona", zona)
			figuras.append(
				hecha or Figura(zona.id, "zona", POLIGONO, list(zona.contorno), rotulo=zona.nombre, orden=ORDEN_ZONA, tipo=zona.suelo)
			)
	for via in planta.vias:
		if len(via.eje) >= 2:
			hecha = previa("via", via)
			figuras.append(hecha or Figura(via.id, "via", LINEA, list(via.eje), rotulo=via.nombre, orden=ORDEN_VIA, tipo=via.sentido))
	for ruta in _rutas(entorno, planta):
		figuras.append(ruta)
	for pared in planta.paredes:
		hecha = previa("pared", pared)
		figuras.append(
			hecha
			or Figura(
				pared.id,
				"pared",
				LINEA,
				[pared.a, pared.b],
				rotulo=pared.nombre,
				orden=ORDEN_PARED,
				tipo=pared.material,
				datos={"grosor": pared.grosor},
			)
		)
	for abertura in planta.aberturas:
		hecha = previa("abertura", abertura)
		figuras.append(
			hecha
			or Figura(
				abertura.id,
				"abertura",
				LINEA,
				[abertura.a, abertura.b],
				rotulo=abertura.nombre,
				orden=ORDEN_ABERTURA,
				tipo=abertura.tipo,
				datos={"estado": abertura.estado, "hoja": abertura.hoja},
			)
		)
	for objeto in planta.objetos:
		hecha = previa("objeto", objeto)
		figuras.append(hecha or _figura_objeto(objeto, catalogo))
	for conector in entorno.conectores:
		puntos = [posicion.punto for posicion in conector.posiciones() if posicion.planta == planta.id]
		if puntos:
			letra = {"escalera": "E", "rampa": "R", "ascensor": "A", "escalera_mecanica": "M"}.get(conector.tipo, "C")
			figuras.append(
				Figura(
					conector.id, "conector", PUNTO, puntos, rotulo=conector.nombre, letra=letra, orden=ORDEN_CONECTOR, tipo=conector.tipo
				)
			)
	for fuente in planta.fuentes:
		hecha = previa("fuente", fuente)
		figuras.append(
			hecha
			or Figura(
				fuente.id,
				"fuente",
				PUNTO,
				[(fuente.x, fuente.y)],
				rotulo=fuente.nombre,
				letra="S",
				orden=ORDEN_FUENTE,
				datos={"radio": fuente.radio},
			)
		)
	for referencia in planta.referencias:
		hecha = previa("referencia", referencia)
		figuras.append(
			hecha
			or Figura(
				referencia.id,
				"referencia",
				PUNTO,
				[(referencia.x, referencia.y)],
				rotulo=referencia.nombre,
				letra="R",
				orden=ORDEN_REFERENCIA,
				tipo=referencia.tipo,
			)
		)
	if entorno.inicio.planta == planta.id:
		figuras.append(
			Figura("", "inicio", PUNTO, [entorno.inicio.punto], letra="I", orden=ORDEN_INICIO, datos={"rumbo": entorno.inicio.rumbo})
		)
	figuras.extend(_figuras_de_actividad(actividad, planta, entorno))
	figuras.sort(key=lambda figura: figura.orden)
	return figuras


def _figura_objeto(objeto: Objeto, catalogo: Any) -> Figura:
	"""Un objeto con su huella real; si el catálogo falla o falta, con su caja."""
	huella = objeto.huella_caja()
	letra = (objeto.nombre or objeto.tipo or "?")[:1].upper()
	color = ""
	if catalogo is not None:
		try:
			huella = catalogo.huella(objeto)
			definicion = catalogo.definicion_de(objeto)
			if definicion is not None:
				letra = definicion.letra() or letra
				color = definicion.color()
		except ValueError, KeyError, TypeError, AttributeError:
			log.warning("No se pudo calcular la huella de %s; se dibuja como caja.", objeto.id, exc_info=True)
			huella = objeto.huella_caja()
	return Figura(
		objeto.id, "objeto", POLIGONO, list(huella), rotulo=objeto.nombre, letra=letra, color=color, orden=ORDEN_OBJETO, tipo=objeto.tipo
	)


def _rutas(entorno: Entorno, planta: Planta) -> list[Figura]:
	"""Rutas reales (GPX, GeoJSON) guardadas en la procedencia del entorno. Tolera datos mal formados."""
	rutas = entorno.procedencia.get("rutas") if isinstance(entorno.procedencia, dict) else None
	figuras: list[Figura] = []
	if not isinstance(rutas, list):
		return figuras
	for ruta in rutas:
		if not isinstance(ruta, dict) or ruta.get("planta") not in (planta.id, None):
			continue
		puntos: list[Punto] = []
		for par in ruta.get("puntos") or []:
			try:
				puntos.append((float(par[0]), float(par[1])))
			except TypeError, ValueError, IndexError:
				continue
		if len(puntos) >= 2:
			figuras.append(Figura("", "ruta", LINEA, puntos, rotulo=str(ruta.get("nombre") or ""), orden=ORDEN_RUTA))
	return figuras


def _contenedor_de(premio: dict[str, Any], entorno: Entorno | None) -> tuple[Planta, Objeto] | None:
	"""(planta, objeto) en el que está escondido un premio con ``dentro_de``; None si es suelto o el objeto ya no existe."""
	contenedor = premio.get("dentro_de")
	if not contenedor or entorno is None:
		return None
	encontrado = entorno.buscar(str(contenedor))
	if not encontrado or not isinstance(encontrado[1], Objeto) or encontrado[0] is None:
		return None
	return encontrado[0], encontrado[1]


def _figuras_de_actividad(actividad: dict[str, Any] | None, planta: Planta, entorno: Entorno | None = None) -> list[Figura]:
	"""Premios e inicio de la actividad elegida, para que el profesional vea dónde los ha puesto.

	Un premio escondido DENTRO de un objeto (``dentro_de``) no tiene
	coordenadas propias: se dibuja en el centro de ese objeto, en su planta,
	con ``tipo="dentro"`` para que el plano lo distinga de uno suelto por la
	forma del trazo y no solo por el color.
	"""
	figuras: list[Figura] = []
	if not isinstance(actividad, dict):
		return figuras
	for premio in actividad.get("premios") or []:
		if not isinstance(premio, dict):
			continue
		rotulo = str(premio.get("nombre") or "")
		dentro = _contenedor_de(premio, entorno)
		if dentro is not None:
			planta_objeto, objeto = dentro
			if planta_objeto.id == planta.id:
				figuras.append(
					Figura("", "premio", PUNTO, [(objeto.x, objeto.y)], rotulo=rotulo, letra="*", orden=ORDEN_PREMIO, tipo="dentro")
				)
			continue
		if not _actividad_en_planta(premio, planta):
			continue
		x, y = _numero(premio.get("x")), _numero(premio.get("y"))
		if x is not None and y is not None:
			figuras.append(Figura("", "premio", PUNTO, [(x, y)], rotulo=rotulo, letra="*", orden=ORDEN_PREMIO))
	inicio = actividad.get("inicio")
	if _actividad_en_planta(inicio, planta) and inicio.get("planta") == planta.id:
		x, y = _numero(inicio.get("x")), _numero(inicio.get("y"))
		if x is not None and y is not None:
			figuras.append(
				Figura(
					"",
					"inicio",
					PUNTO,
					[(x, y)],
					letra="I",
					orden=ORDEN_INICIO + 1,
					tipo="actividad",
					datos={"rumbo": _numero(inicio.get("rumbo")) or 0.0},
				)
			)
	return figuras


def _nombre_planta(entorno: Entorno, id_planta: Any) -> str:
	planta = entorno.planta(str(id_planta or ""))
	return (planta.nombre or planta.id) if planta is not None else str(id_planta or "")


def _espacio_en(entorno: Entorno, id_planta: str, x: float, y: float) -> str:
	"""Nombre del espacio más pequeño que contiene el punto (el paso de peatones antes que su calzada), o «»."""
	planta = entorno.planta(id_planta)
	if planta is None:
		return ""
	candidatos = [e for e in planta.espacios if len(e.contorno) >= 3 and geo.punto_en_poligono((x, y), e.contorno)]
	if not candidatos:
		return ""
	espacio = min(candidatos, key=lambda e: e.area())
	return espacio.nombre or espacio.id


def describir_actividad(entorno: Entorno | None, actividad: dict[str, Any] | None) -> str:
	"""Lo que el plano enseña de la actividad elegida, en frases: su inicio y dónde está cada premio.

	El plano es un lienzo que el lector de pantalla no lee. Para que los
	premios no sean «solo visuales», la página «Descripción» añade este texto
	debajo de la del entorno. Vacío si no hay actividad elegida.
	"""
	if entorno is None or not isinstance(actividad, dict):
		return ""
	nombre = str(actividad.get("nombre") or actividad.get("id") or "")
	lineas = [_("Actividad elegida: «{nombre}».").format(nombre=nombre)]
	inicio = actividad.get("inicio")
	if isinstance(inicio, dict):
		x, y = _numero(inicio.get("x")), _numero(inicio.get("y"))
		if x is not None and y is not None:
			id_planta = str(inicio.get("planta") or entorno.inicio.planta)
			lugar = _espacio_en(entorno, id_planta, x, y)
			lineas.append(
				_("Inicio de la actividad: planta {planta}, {lugar}x {x} m, y {y} m.").format(
					planta=_nombre_planta(entorno, id_planta),
					lugar=_("en {espacio}, ").format(espacio=lugar) if lugar else "",
					x=texto_numero(x),
					y=texto_numero(y),
				)
			)
	premios = [premio for premio in actividad.get("premios") or [] if isinstance(premio, dict)]
	if not premios:
		lineas.append(_("No tiene premios."))
		return "\n".join(lineas)
	lineas.append(_n("{n} premio:", "{n} premios:", len(premios)).format(n=len(premios)))
	for premio in premios:
		rotulo = str(premio.get("nombre") or premio.get("id") or "")
		dentro = _contenedor_de(premio, entorno)
		if dentro is not None:
			planta, objeto = dentro
			lineas.append(
				_("Premio «{premio}»: dentro de {objeto}, planta {planta}.").format(
					premio=rotulo, objeto=objeto.nombre or objeto.id, planta=planta.nombre or planta.id
				)
			)
			continue
		if premio.get("dentro_de"):
			lineas.append(_("Premio «{premio}»: dentro de un objeto que ya no existe.").format(premio=rotulo))
			continue
		x, y = _numero(premio.get("x")), _numero(premio.get("y"))
		if x is None or y is None:
			lineas.append(_("Premio «{premio}»: sin lugar en el plano.").format(premio=rotulo))
			continue
		id_planta = str(premio.get("planta") or entorno.inicio.planta)
		lugar = _espacio_en(entorno, id_planta, x, y)
		lineas.append(
			_("Premio «{premio}»: planta {planta}, {lugar}x {x} m, y {y} m.").format(
				premio=rotulo,
				planta=_nombre_planta(entorno, id_planta),
				lugar=_("en {espacio}, ").format(espacio=lugar) if lugar else "",
				x=texto_numero(x),
				y=texto_numero(y),
			)
		)
	return "\n".join(lineas)


# ── Selección ────────────────────────────────────────────────────────────────


def toca(figura: Figura, x: float, y: float, tolerancia: float) -> bool:
	"""True si el punto (x, y) cae sobre la figura, con ``tolerancia`` metros de margen en líneas y puntos."""
	if figura.forma == POLIGONO:
		return len(figura.puntos) >= 3 and geo.punto_en_poligono((x, y), figura.puntos)
	if figura.forma == LINEA:
		return any(geo.distancia_punto_segmento((x, y), a, b) <= tolerancia for a, b in zip(figura.puntos, figura.puntos[1:], strict=False))
	return any(geo.distancia((x, y), punto) <= tolerancia for punto in figura.puntos)


def elemento_en(figuras: Sequence[Figura], x: float, y: float, tolerancia: float = 0.15) -> str:
	"""Id del elemento que hay en el punto (x, y), o cadena vacía si no hay ninguno.

	Gana el que se pinta más arriba: un punto o un objeto antes que el
	espacio en el que está, y el espacio más pequeño antes que el grande.
	"""
	for figura in sorted(figuras, key=lambda f: f.orden, reverse=True):
		if figura.seleccionable and toca(figura, x, y, tolerancia):
			return figura.id
	return ""


def figura_de(figuras: Sequence[Figura], id_elemento: str) -> Figura | None:
	"""La figura de un elemento, o None si no está en esta planta."""
	if not id_elemento:
		return None
	return next((figura for figura in figuras if figura.id == id_elemento), None)


def caja_de_figuras(figuras: Sequence[Figura]) -> tuple[float, float, float, float]:
	"""Caja que envuelve todo lo dibujado; una de 10 por 8 metros si la planta está vacía."""
	puntos = [punto for figura in figuras for punto in figura.puntos]
	if not puntos:
		return (0.0, 0.0, 10.0, 8.0)
	return geo.caja(puntos)


# ── Cuadrícula, arrastre y regla ─────────────────────────────────────────────


def ajustar_a_cuadricula(valor: float, paso: float) -> float:
	"""Redondea una medida al múltiplo más cercano del paso de la cuadrícula (sin paso, no la toca)."""
	if paso <= 0:
		return valor
	return round(round(valor / paso) * paso, 6)


def desplazamiento_de_arrastre(vista: VistaPlano, inicio_px: tuple[float, float], fin_px: tuple[float, float], paso: float = 0.0) -> Punto:
	"""Metros (al este, al norte) que corresponden a arrastrar el ratón de un píxel a otro.

	Con ``paso`` el desplazamiento se redondea a la cuadrícula: así un
	elemento que estaba alineado sigue alineado después de moverlo.
	"""
	x0, y0 = vista.a_mundo(*inicio_px)
	x1, y1 = vista.a_mundo(*fin_px)
	return ajustar_a_cuadricula(x1 - x0, paso), ajustar_a_cuadricula(y1 - y0, paso)


def rectangulo_de_arrastre(
	vista: VistaPlano, inicio_px: tuple[float, float], fin_px: tuple[float, float], paso: float = 0.0
) -> tuple[float, float, float, float]:
	"""(x, y, ancho, fondo) en metros del rectángulo dibujado entre dos píxeles; (x, y) es su esquina suroeste."""
	x0, y0 = vista.a_mundo(*inicio_px)
	x1, y1 = vista.a_mundo(*fin_px)
	x0, y0, x1, y1 = (ajustar_a_cuadricula(v, paso) for v in (x0, y0, x1, y1))
	return min(x0, x1), min(y0, y1), abs(x1 - x0), abs(y1 - y0)


def paso_de_regla(escala: float, ancho_px: float = 120.0) -> float:
	"""Longitud «redonda» (1, 2, 5, 10… metros) de la regla de escala que cabe en ``ancho_px`` píxeles."""
	if escala <= 0:
		return 1.0
	maximo = ancho_px / escala
	if maximo <= 0:
		return 1.0
	potencia = 10.0 ** math.floor(math.log10(maximo))
	for factor in (5.0, 2.0, 1.0):
		if factor * potencia <= maximo:
			return factor * potencia
	return potencia


def paso_visible_de_cuadricula(paso: float, escala: float, minimo_px: float = 8.0) -> float:
	"""Paso con el que se pinta la cuadrícula: el pedido, o un múltiplo si las líneas quedarían pegadas."""
	if paso <= 0 or escala <= 0:
		return 0.0
	visible = paso
	for factor in (1, 2, 5, 10, 20, 50, 100, 200, 500, 1000):
		visible = paso * factor
		if visible * escala >= minimo_px:
			break
	return visible


def arco_de_puerta(a: Punto, b: Punto, tramos: int = 8) -> list[Punto]:
	"""Puntos del barrido de una puerta con bisagra en ``a``: un cuarto de círculo desde ``b``.

	Es el símbolo de puerta de cualquier plano de arquitectura, y lo que la
	distingue de una ventana o de un hueco sin depender del color.
	"""
	radio = geo.distancia(a, b)
	if radio <= 0:
		return [a]
	angulo = math.atan2(b[1] - a[1], b[0] - a[0])
	return [
		(a[0] + radio * math.cos(angulo + math.pi / 2 * i / tramos), a[1] + radio * math.sin(angulo + math.pi / 2 * i / tramos))
		for i in range(tramos + 1)
	]
