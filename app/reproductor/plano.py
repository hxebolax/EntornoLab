"""Parte visual del juego: plano cenital de la planta actual, a escala.

Es un añadido para quien tiene baja visión y para el acompañante que mira la
pantalla; quien juega de oído no pierde nada si no la ve (nunca hay
información solo visual). Reglas que sigue el dibujo:

- **A escala**, con una barra de medida, y el norte arriba (como los planos
  del Estudio).
- **Nada depende solo del color**: las paredes son trazos gruesos, las
  puertas cerradas un trazo doble, las ventanas un trazo fino discontinuo,
  los objetos su huella real con la letra de su complemento, los premios un
  rombo y el alumno una flecha que apunta a donde mira.
- **Sin destellos ni animaciones**: lo único que se mueve es el alumno.
- **Alto contraste** opcional (blanco y amarillo sobre negro), y el objetivo
  en texto grande arriba.

Se dibuja a partir del índice del motor (``Mundo``), no del modelo: así se ve
exactamente lo que hay en la partida (una puerta que se ha abierto deja de
dibujarse cerrada).
"""

from __future__ import annotations

import logging
import math
from typing import TYPE_CHECKING, Any

import pygame

from app.core.i18n import _, separador_decimal
from app.dominio import geometria as geo

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)

MARGEN = 20
ALTO_CABECERA = 74
ALTO_PIE = 104
# Barras de escala posibles, en metros: se elige la mayor que quepa en un cuarto del ancho.
_BARRAS = (0.5, 1.0, 2.0, 5.0, 10.0, 20.0, 50.0, 100.0)


class _Vista:
	"""Conversión de metros del mundo a píxeles del lienzo (norte arriba)."""

	def __init__(self, caja: tuple[float, float, float, float], zona: pygame.Rect) -> None:
		x0, y0, x1, y1 = caja
		ancho = max(1.0, x1 - x0)
		alto = max(1.0, y1 - y0)
		self.escala = min(zona.width / ancho, zona.height / alto)
		self.x0 = x0
		self.y1 = y1
		self.dx = zona.left + (zona.width - ancho * self.escala) / 2.0
		self.dy = zona.top + (zona.height - alto * self.escala) / 2.0

	def punto(self, x: float, y: float) -> tuple[int, int]:
		"""Un punto del mundo en píxeles."""
		return round(self.dx + (x - self.x0) * self.escala), round(self.dy + (self.y1 - y) * self.escala)

	def puntos(self, poligono: Any) -> list[tuple[int, int]]:
		"""Un polígono del mundo en píxeles."""
		return [self.punto(x, y) for x, y in poligono]


def _color(texto: str, reserva: tuple[int, int, int]) -> tuple[int, int, int]:
	try:
		color = pygame.Color(texto)
	except ValueError:
		return reserva
	return color.r, color.g, color.b


def _trazo_discontinuo(
	lienzo: pygame.Surface, color: tuple[int, int, int], a: tuple[int, int], b: tuple[int, int], grosor: int = 1
) -> None:
	largo = math.hypot(b[0] - a[0], b[1] - a[1])
	if largo < 1.0:
		return
	tramos = max(1, int(largo // 8))
	for numero in range(0, tramos, 2):
		inicio = numero / tramos
		final = min(1.0, (numero + 1) / tramos)
		pygame.draw.line(
			lienzo,
			color,
			(round(a[0] + (b[0] - a[0]) * inicio), round(a[1] + (b[1] - a[1]) * inicio)),
			(round(a[0] + (b[0] - a[0]) * final), round(a[1] + (b[1] - a[1]) * final)),
			grosor,
		)


def premios_visibles(partida: Any) -> list[tuple[str, float, float]]:
	"""(planta, x, y) de los premios de la actividad que se pueden enseñar y aún no se han cogido."""
	datos = partida.datos if isinstance(partida.datos, dict) else {}
	visibles: list[tuple[str, float, float]] = []
	for premio in datos.get("premios") or ():
		if not isinstance(premio, dict) or str(premio.get("visibilidad") or "lejos") == "oculto" or premio.get("dentro_de"):
			continue
		if str(premio.get("id") or "") in partida.premios_recogidos:
			continue
		try:
			visibles.append((str(premio.get("planta") or ""), float(premio["x"]), float(premio["y"])))
		except KeyError, TypeError, ValueError:
			continue
	return visibles


def _capa_fija(app: Aplicacion, tamano: tuple[int, int], indice: Any, vista: _Vista) -> pygame.Surface:
	"""Lo que no cambia durante la partida, dibujado una vez: suelo y nombre de cada lugar, objetos, paredes y ventanas.

	Por qué: en un barrio importado son miles de polígonos y decenas de miles
	de trazos; dibujarlos en cada fotograma llevaba más de 60 ms. Se dibuja
	igual que antes y en el mismo orden; las puertas (que se abren y se
	cierran), los premios y el alumno se dibujan encima en cada fotograma.
	"""
	fondo, color, _destacado, tenue = app.paleta
	contraste = bool(app.config.obtener("general.alto_contraste", False))
	capa = pygame.Surface(tamano)
	capa.fill(fondo)

	# Suelo de cada lugar y su nombre.
	relleno = (28, 28, 28) if contraste else (34, 42, 56)
	for _caja, espacio in sorted(indice.espacios, key=lambda par: -par[1].area()):
		if len(espacio.contorno) < 3:
			continue
		puntos = vista.puntos(espacio.contorno)
		pygame.draw.polygon(capa, tenue if espacio.macizo else relleno, puntos)
		if not espacio.cerrado:
			pygame.draw.polygon(capa, tenue, puntos, 1)
		if espacio.nombre and vista.escala * math.sqrt(max(espacio.area(), 0.0)) > 60:
			centro = vista.punto(*espacio.centro())
			rotulo = app.texto(espacio.nombre[:24], 14, tenue if not espacio.macizo else fondo)
			capa.blit(rotulo, (centro[0] - rotulo.get_width() // 2, centro[1] - rotulo.get_height() // 2))

	# Objetos: su huella real, con la letra de su complemento.
	for info in indice.objetos:
		if len(info.huella) < 3:
			continue
		puntos = vista.puntos(info.huella)
		definicion = info.definicion
		color_objeto = (0, 0, 0) if contraste else _color(definicion.color() if definicion is not None else "#808080", (128, 128, 128))
		pygame.draw.polygon(capa, color_objeto, puntos)
		pygame.draw.polygon(capa, color, puntos, 2 if info.bloquea else 1)
		letra = definicion.letra() if definicion is not None else "?"
		centro = vista.punto(*geo.centroide(info.huella))
		rotulo = app.texto(letra, 13, color)
		if rotulo.get_width() + 4 <= max(p[0] for p in puntos) - min(p[0] for p in puntos) + 14:
			capa.blit(rotulo, (centro[0] - rotulo.get_width() // 2, centro[1] - rotulo.get_height() // 2))

	# Paredes y ventanas (en la lista van antes que las puertas: el orden de dibujo es el mismo de siempre).
	for seg in indice.segs:
		if seg.clase in ("pared", "macizo"):
			if seg.paso:
				pygame.draw.line(capa, color, vista.punto(seg.ax, seg.ay), vista.punto(seg.bx, seg.by), 4)
		elif seg.clase == "ventana":
			_trazo_discontinuo(capa, color, vista.punto(seg.ax, seg.ay), vista.punto(seg.bx, seg.by), 2)
	return capa


# Capa fija ya dibujada: [lo que la determina, la capa, el índice de planta, sus puertas]. Una sola: la de la planta que se ve.
_cache_capa: list[Any] = [None, None, None, []]


def dibujar(app: Aplicacion, lienzo: pygame.Surface, partida: Any) -> None:
	"""Dibuja el objetivo, el plano de la planta en la que está el alumno y la barra de escala."""
	fondo, color, destacado, tenue = app.paleta
	contraste = bool(app.config.obtener("general.alto_contraste", False))
	ancho, alto = lienzo.get_size()
	sesion = partida.sesion
	jugador = sesion.jugador
	indice = sesion.mundo.planta(jugador.planta)
	zona = pygame.Rect(MARGEN, ALTO_CABECERA, ancho - 2 * MARGEN, alto - ALTO_CABECERA - ALTO_PIE)
	vista = _Vista(indice.caja, zona) if indice is not None else None

	if indice is not None and vista is not None:
		# La capa fija vale mientras sean la misma planta indexada, el mismo tamaño, los mismos colores y el mismo texto.
		clave = (len(indice.segs), lienzo.get_size(), app.paleta, contraste, app.config.obtener("general.tamano_texto", 100))
		if _cache_capa[2] is not indice or _cache_capa[0] != clave or _cache_capa[1] is None:
			_cache_capa[:] = [
				clave,
				_capa_fija(app, lienzo.get_size(), indice, vista),
				indice,
				[s for s in indice.segs if s.clase == "puerta"],
			]
		lienzo.blit(_cache_capa[1], (0, 0))

	# Cabecera: el objetivo en texto grande (también se puede oír con la tecla de objetivo).
	y = 10
	for linea in app.partir(partida.texto_objetivo(), 26, ancho - 2 * MARGEN)[:2]:
		lienzo.blit(app.texto(linea, 26, destacado), (MARGEN, y))
		y += app.fuente(26).get_linesize()
	if indice is None or vista is None:
		return

	# Puertas cerradas, tal como están en la partida: trazo doble, más fino que la pared.
	for seg in _cache_capa[3]:
		if seg.activo:
			a = vista.punto(seg.ax, seg.ay)
			b = vista.punto(seg.bx, seg.by)
			pygame.draw.line(lienzo, destacado, a, b, 5)
			pygame.draw.line(lienzo, fondo, a, b, 1)

	# Premios que se pueden ver: un rombo.
	for planta, x, y_mundo in premios_visibles(partida):
		if planta and planta != jugador.planta:
			continue
		cx, cy = vista.punto(x, y_mundo)
		rombo = [(cx, cy - 9), (cx + 7, cy), (cx, cy + 9), (cx - 7, cy)]
		pygame.draw.polygon(lienzo, destacado, rombo)
		pygame.draw.polygon(lienzo, color, rombo, 1)

	# El alumno: un círculo de su tamaño real (con un mínimo) y una flecha hacia donde mira.
	cx, cy = vista.punto(jugador.x, jugador.y)
	radio = max(7, round(jugador.radio * vista.escala))
	dx, dy = geo.vector_rumbo(jugador.rumbo)
	punta = (cx + round(dx * (radio + 12)), cy - round(dy * (radio + 12)))
	izquierda = (cx + round(-dy * radio * 0.8), cy - round(dx * radio * 0.8))
	derecha = (cx + round(dy * radio * 0.8), cy - round(-dx * radio * 0.8))
	pygame.draw.polygon(lienzo, destacado, [punta, izquierda, derecha])
	pygame.draw.circle(lienzo, destacado, (cx, cy), radio)
	pygame.draw.circle(lienzo, fondo, (cx, cy), radio, 2)

	# Barra de escala y nombre de la planta.
	metros = next((m for m in reversed(_BARRAS) if m * vista.escala <= zona.width / 4), _BARRAS[0])
	largo = round(metros * vista.escala)
	base = zona.bottom + 10
	pygame.draw.line(lienzo, color, (MARGEN, base), (MARGEN + largo, base), 2)
	pygame.draw.line(lienzo, color, (MARGEN, base - 4), (MARGEN, base + 4), 2)
	pygame.draw.line(lienzo, color, (MARGEN + largo, base - 4), (MARGEN + largo, base + 4), 2)
	texto_metros = str(int(metros)) if float(metros).is_integer() else str(metros).replace(".", separador_decimal())
	rotulo = _("{metros} m. {planta}. Norte arriba.").format(metros=texto_metros, planta=indice.planta.nombre or indice.planta.id)
	lienzo.blit(app.texto(rotulo, 14, tenue), (MARGEN + largo + 10, base - 9))
