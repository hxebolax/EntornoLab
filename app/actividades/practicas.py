"""Prácticas que no son una lista de pasos: exploración libre, familiarización de sala y línea guía.

- **Exploración libre**: sin objetivo ni final; solo anota por dónde se ha pasado.
- **Familiarización de sala**: la técnica habitual de orientación y
  movilidad para conocer una sala, primero el perímetro siguiendo la pared y
  después el interior. Se mide cuánto perímetro y cuánto interior se han recorrido.
- **Línea guía**: seguir una pared o un bordillo de un extremo a otro sin separarse.

Las rutas, los recados y la visita guiada están en ``secuencia``.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from app.actividades.base import Actividad
from app.actividades.lugares import Lugar
from app.core.i18n import _
from app.dominio import geometria as geo
from app.dominio.colocacion import lado_de_espacio
from app.dominio.geometria import Punto
from app.dominio.modelo import Espacio

log = logging.getLogger(__name__)

TROZO = 1.0
RADIO_CELDA = 0.8
SEGUNDOS_SEPARADO = 2.0
FRACCION_LINEA = 0.9


def _trocear(a: Punto, b: Punto, largo: float = TROZO) -> list[tuple[Punto, Punto]]:
	"""Divide un segmento en trozos de un metro más o menos."""
	total = geo.distancia(a, b)
	if total < 1e-6:
		return []
	n = max(1, round(total / largo))
	puntos = [(a[0] + (b[0] - a[0]) * i / n, a[1] + (b[1] - a[1]) * i / n) for i in range(n + 1)]
	return list(zip(puntos[:-1], puntos[1:], strict=True))


def _distancia_al_borde(punto: Punto, contorno: list[Punto]) -> float:
	"""Distancia de un punto al borde de un polígono (``distancia_punto_poligono`` vale cero para los puntos de dentro)."""
	return min(geo.distancia_punto_segmento(punto, a, b) for a, b in geo.lados(contorno))


class Exploracion(Actividad):
	"""Exploración libre: recorrer el entorno sin objetivo. Termina cuando el alumno quiere."""

	ESTRELLAS = ("exploracion",)
	# No tiene final propio: el reproductor ofrece «terminar» (que la cierra como terminada) en vez de «abandonar».
	TERMINA_A_VOLUNTAD = True

	def _avance_esperado(self) -> bool:
		return False

	def _preparar(self, sesion: Any) -> None:
		self.total = len(self._espacios_a_explorar(sesion))
		self.fase = "libre"

	def _texto_inicio(self) -> str:
		return self.tx("exploracion_inicio")

	def texto_objetivo(self) -> str:
		return self.tx("objetivo_libre")

	def _al_registro(self, sesion: Any, tipo: str, datos: dict[str, Any]) -> None:
		if tipo == "entrada_espacio":
			visitados = sesion.movimiento.visitados
			self.hechos = sum(1 for ident in self._espacios_a_explorar(sesion) if ident in visitados)

	def _cerrar(self, sesion: Any, completada: bool, motivo: str) -> None:
		# Una exploración libre no se «falla»: dejarla, o que se acabe el tiempo, es terminarla.
		libre = motivo in ("abandonada", "tiempo", "sin_completar")
		super()._cerrar(sesion, True if libre else completada, "terminada" if libre else motivo)

	def _datos_estrellas(self, sesion: Any) -> dict[str, Any]:
		return {"exploracion": self._exploracion(sesion)}

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		return {"exploracion": self._exploracion(sesion)}


class Perimetro(Actividad):
	"""Familiarización de sala: primero el perímetro, después el interior."""

	ESTRELLAS = ("completar", "pocas_ayudas", "sin_choques")

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._espacio: Espacio | None = None
		self._planta = ""
		self._trozos: list[tuple[Punto, Punto]] = []
		self._cubiertos: set[int] = set()
		self._celdas: list[Punto] = []
		self._pisadas: set[int] = set()
		self._anunciado = 0
		self._fuera = False
		self._alcance = 1.1

	def _preparar(self, sesion: Any) -> None:
		jugador = sesion.jugador
		elemento = self.entorno.elemento(str(self.datos.get("espacio") or "")) if self.datos.get("espacio") else None
		if not isinstance(elemento, Espacio):
			elemento = sesion.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		if not isinstance(elemento, Espacio) or len(elemento.contorno) < 3:
			return
		planta = self.entorno.planta_de(elemento)
		self._espacio = elemento
		self._planta = planta.id if planta is not None else jugador.planta
		for a, b in elemento.lados():
			self._trozos.extend(_trocear(a, b))
		x0, y0, x1, y1 = elemento.caja()
		# En una sala pequeña «junto a la pared» tiene que ser más cerca, o desde el centro se tocarían todas a la vez.
		self._alcance = min(float(self.datos.get("distancia_pared") or 1.0) + 0.1, max(0.45, 0.3 * min(x1 - x0, y1 - y0)))
		margen = self._alcance + 0.1
		x = x0 + 0.5
		while x < x1:
			y = y0 + 0.5
			while y < y1:
				if (
					geo.punto_en_poligono((x, y), elemento.contorno, borde=False)
					and _distancia_al_borde((x, y), elemento.contorno) >= margen
				):
					if sesion.mundo.dentro_de_objeto(self._planta, x, y) is None:
						self._celdas.append((x, y))
				y += 1.0
			x += 1.0
		self.total = 2 if self._celdas else 1
		self.fase = "perimetro"

	def _tic(self, sesion: Any, dt: float) -> None:
		if self._espacio is None:
			self._terminar(sesion, False, "sin_sala")

	def _nombre_sala(self) -> str:
		return (self._espacio.nombre if self._espacio is not None else "") or _("la sala")

	def _texto_inicio(self) -> str:
		return self.tx("perimetro_inicio")

	def texto_objetivo(self) -> str:
		return self.tx("interior_objetivo" if self.fase == "interior" else "perimetro_objetivo", sala=self._nombre_sala())

	def perimetro_recorrido(self) -> float:
		"""Parte del perímetro (0 a 1) junto a la que ya se ha pasado."""
		return round(len(self._cubiertos) / len(self._trozos), 3) if self._trozos else 0.0

	def interior_recorrido(self) -> float:
		"""Parte del interior (0 a 1) que ya se ha pisado."""
		return round(len(self._pisadas) / len(self._celdas), 3) if self._celdas else 1.0

	def _tras_mover(self, sesion: Any) -> None:
		espacio = self._espacio
		if espacio is None:
			return
		jugador = sesion.jugador
		dentro = jugador.planta == self._planta and (sesion.movimiento.espacio_id or "") == espacio.id
		if not dentro:
			if not self._fuera and self._cubiertos:
				self._fuera = True
				self._decir(sesion, self.tx("perimetro_fuera"), prioridad=2, clave="fuera")
			return
		self._fuera = False
		punto = jugador.punto
		if self.fase == "perimetro":
			alcance = self._alcance
			antes = len(self._cubiertos)
			for indice, (a, b) in enumerate(self._trozos):
				if indice not in self._cubiertos and geo.distancia_punto_segmento(punto, a, b) <= alcance:
					self._cubiertos.add(indice)
			if len(self._cubiertos) > antes:
				self._avance(sesion)
				self._progreso_perimetro(sesion)
		elif self.fase == "interior":
			antes = len(self._pisadas)
			for indice, celda in enumerate(self._celdas):
				if indice not in self._pisadas and geo.distancia(punto, celda) <= RADIO_CELDA:
					self._pisadas.add(indice)
			if len(self._pisadas) > antes:
				self._avance(sesion)
			if self.interior_recorrido() >= float(self.datos.get("fraccion_interior") or 0.5):
				self._logro(sesion, "interior", self._nombre_sala(), "")
				self._terminar(sesion, True)

	def _progreso_perimetro(self, sesion: Any) -> None:
		recorrido = self.perimetro_recorrido()
		if recorrido >= float(self.datos.get("fraccion_perimetro") or 0.8):
			if not self._celdas:
				self._logro(sesion, "perimetro", self._nombre_sala(), "")
				self._terminar(sesion, True)
				return
			self.fase = "interior"
			self._logro(sesion, "perimetro", self._nombre_sala(), self.tx("perimetro_hecho"))
			return
		cuarto = int(recorrido * 4)
		if cuarto > self._anunciado and 1 <= cuarto <= 3 and not self.es_examen:
			self._anunciado = cuarto
			self._decir(sesion, self.tx("perimetro_progreso", porcentaje=cuarto * 25), prioridad=2, clave="progreso", caduca=10.0)

	def _lugar_actual(self) -> Lugar | None:
		sesion = self._sesion
		if sesion is None or self._espacio is None:
			return None
		punto = sesion.jugador.punto
		if self.fase == "interior":
			pendientes = [celda for indice, celda in enumerate(self._celdas) if indice not in self._pisadas]
		else:
			pendientes = [geo.punto_medio(a, b) for indice, (a, b) in enumerate(self._trozos) if indice not in self._cubiertos]
		if not pendientes:
			return None
		cerca = min(pendientes, key=lambda p: (round(geo.distancia(p, punto), 2), p))
		return Lugar(self._planta, cerca[0], cerca[1], self._nombre_sala(), "punto", "", 1.0)

	def _texto_pista(self, sesion: Any, lugar: Lugar, detalle: int) -> str:
		if self.fase == "perimetro" and detalle <= 1:
			return _("Busca una pared y síguela sin soltarla. Las esquinas te dicen cuándo cambias de pared.")
		donde = geo.punto_cardinal(geo.rumbo_entre(sesion.jugador.punto, lugar.punto))
		return _("Te falta una parte que queda al {punto} de donde estás.").format(punto=donde)

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		return {
			"sala": self._espacio.id if self._espacio is not None else "",
			"perimetro_recorrido": self.perimetro_recorrido(),
			"interior_recorrido": self.interior_recorrido(),
			"perimetro_m": round(geo.perimetro(self._espacio.contorno), 1) if self._espacio is not None else 0.0,
		}


class LineaGuia(Actividad):
	"""Seguir una línea guía (una pared, un bordillo) de un extremo a otro sin separarse de ella."""

	ESTRELLAS = ("completar", "pocas_ayudas", "sin_choques")

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._espacio: Espacio | None = None
		self._planta = ""
		self._a: Punto = (0.0, 0.0)
		self._b: Punto = (0.0, 0.0)
		self._lado = ""
		self._trozos: list[tuple[Punto, Punto]] = []
		self._cubiertos: set[int] = set()
		self._t_lejos = 0.0
		self._separado = False
		self._separaciones = 0
		self._mitad_dicha = False

	def _preparar(self, sesion: Any) -> None:
		jugador = sesion.jugador
		elemento = self.entorno.elemento(str(self.datos.get("espacio") or "")) if self.datos.get("espacio") else None
		if not isinstance(elemento, Espacio):
			elemento = sesion.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		if not isinstance(elemento, Espacio) or len(elemento.contorno) < 3:
			return
		lado = str(self.datos.get("lado") or "mas_largo")
		tramo: tuple[Punto, Punto] | None = None
		if lado != "mas_largo":
			encontrado = lado_de_espacio(elemento, lado)
			if encontrado is not None:
				tramo = (encontrado[1], encontrado[2])
		if tramo is None:
			tramo = max(elemento.lados(), key=lambda par: (round(geo.distancia(par[0], par[1]), 3), par))
		planta = self.entorno.planta_de(elemento)
		self._espacio = elemento
		self._planta = planta.id if planta is not None else jugador.planta
		self._a, self._b = tramo
		self._lado = geo.lado_cardinal(geo.rumbo_entre(elemento.centro(), geo.punto_medio(self._a, self._b)))
		self._trozos = _trocear(self._a, self._b)
		self.total = 1
		self.fase = "seguir"
		self._guiar(sesion, self._lugar_actual())

	def _tic(self, sesion: Any, dt: float) -> None:
		if self._espacio is None or not self._trozos:
			self._terminar(sesion, False, "sin_linea")
			return
		if not self._cubiertos:
			return
		if self._distancia(sesion) > self._maxima():
			self._t_lejos += dt
			if self._t_lejos >= SEGUNDOS_SEPARADO and not self._separado:
				self._separado = True
				self._separaciones += 1
				self._decir(sesion, self.tx("linea_separado"), prioridad=2, clave="linea")
				self._fallo(sesion, "separado")
		else:
			self._t_lejos = 0.0
			self._separado = False

	def _maxima(self) -> float:
		"""Separación máxima de la línea; en un espacio estrecho se reduce, o no habría forma de separarse."""
		maxima = float(self.datos.get("distancia_maxima") or 1.0)
		if self._espacio is None:
			return maxima
		x0, y0, x1, y1 = self._espacio.caja()
		return min(maxima, max(0.45, 0.3 * min(x1 - x0, y1 - y0)))

	def _distancia(self, sesion: Any) -> float:
		jugador = sesion.jugador
		if jugador.planta != self._planta:
			return math.inf
		return geo.distancia_punto_segmento(jugador.punto, self._a, self._b)

	def linea_recorrida(self) -> float:
		"""Parte de la línea (0 a 1) junto a la que ya se ha pasado."""
		return round(len(self._cubiertos) / len(self._trozos), 3) if self._trozos else 0.0

	def _nombre_linea(self) -> str:
		espacio = self._espacio
		nombre = (espacio.nombre if espacio is not None else "") or _("este lugar")
		clave = "linea_pared" if espacio is not None and espacio.cerrado else "linea_bordillo"
		return self.tx(clave, lado=self.tx.lado(self._lado), espacio=nombre)

	def _texto_inicio(self) -> str:
		return self.tx("linea_inicio")

	def texto_objetivo(self) -> str:
		return self.tx("linea_objetivo", linea=self._nombre_linea())

	def _tras_mover(self, sesion: Any) -> None:
		if not self._trozos or self._distancia(sesion) > self._maxima():
			return
		punto = sesion.jugador.punto
		alcance = self._maxima() + 0.1
		antes = len(self._cubiertos)
		for indice, (a, b) in enumerate(self._trozos):
			if indice not in self._cubiertos and geo.distancia_punto_segmento(punto, a, b) <= alcance:
				self._cubiertos.add(indice)
		if len(self._cubiertos) == antes:
			return
		self._avance(sesion)
		recorrida = self.linea_recorrida()
		if recorrida >= FRACCION_LINEA:
			self._logro(sesion, "linea", self._nombre_linea(), "")
			self._terminar(sesion, True)
			return
		if recorrida >= 0.5 and not self._mitad_dicha and not self.es_examen:
			self._mitad_dicha = True
			self._decir(sesion, self.tx("linea_mitad"), prioridad=2, clave="progreso", caduca=10.0)

	def _lugar_actual(self) -> Lugar | None:
		"""El extremo de la línea que queda más lejos de lo ya recorrido (hacia allí hay que seguir)."""
		if not self._trozos or self._espacio is None:
			return None
		pendientes = [indice for indice in range(len(self._trozos)) if indice not in self._cubiertos]
		if not pendientes:
			return None
		# Se apunta al trozo pendiente más alejado del centro de lo recorrido: el final de la línea.
		if self._cubiertos:
			centro = sum(self._cubiertos) / len(self._cubiertos)
			indice = max(pendientes, key=lambda i: (abs(i - centro), i))
		else:
			indice = pendientes[-1]
		a, b = self._trozos[indice]
		medio = geo.punto_medio(a, b)
		hacia = self._espacio.centro()
		largo = geo.distancia(medio, hacia)
		separacion = min(0.5, largo)
		x = medio[0] + (hacia[0] - medio[0]) * separacion / largo if largo > 1e-6 else medio[0]
		y = medio[1] + (hacia[1] - medio[1]) * separacion / largo if largo > 1e-6 else medio[1]
		return Lugar(self._planta, x, y, self._nombre_linea(), "punto", "", 1.0)

	def _texto_pista(self, sesion: Any, lugar: Lugar, detalle: int) -> str:
		donde = geo.punto_cardinal(geo.rumbo_entre(sesion.jugador.punto, lugar.punto))
		return _("La línea sigue hacia el {punto}. Mantén el contacto y no la sueltes.").format(punto=donde)

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		return {
			"espacio": self._espacio.id if self._espacio is not None else "",
			"lado": self._lado,
			"linea_m": round(geo.distancia(self._a, self._b), 1),
			"linea_recorrida": self.linea_recorrida(),
			"separaciones": self._separaciones,
		}
