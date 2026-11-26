"""Conversión de un plano vectorial (DXF o SVG) en una planta interior editable.

Los lectores de ``dxf.py`` y ``svg.py`` dejan el dibujo en una forma común,
el ``Plano``: trazos por capas, rótulos y arcos. Aquí está lo que comparten:

- enseñar las capas con una sugerencia de para qué sirve cada una, para que
  el profesional elija cuáles son paredes;
- pasar de las unidades del dibujo a metros (1 unidad = X metros) y llevar
  el origen a la esquina del plano;
- convertir polilíneas cerradas en espacios, líneas en paredes, rótulos en
  nombres de los espacios en que caen y arcos de puerta en puertas.

Un plano no dice casi nunca dónde están las puertas ni cómo se llama cada
sala: lo que falta se anota en el informe en lugar de inventarlo. El plano
no sale del equipo en ningún momento.
"""

from __future__ import annotations

import datetime
import logging
import math
from collections.abc import Sequence
from dataclasses import dataclass, field

from app.core.i18n import _, separador_decimal
from app.dominio import edicion as ed
from app.dominio import geometria as geo
from app.dominio.geometria import Punto
from app.dominio.modelo import ACUSTICA_POR_TIPO, Abertura, Entorno, Espacio, Planta
from app.importar import formas
from app.importar.comun import (
	Cancelado,
	ErrorImportacion,
	Informe,
	Progreso,
	ResultadoImportacion,
	avisar,
	candidatos_en_rejilla,
	comprobar_cancelacion,
	fijar_inicio_valido,
	frase_cuenta,
)

log = logging.getLogger(__name__)

# Usos que se pueden sugerir para una capa.
USO_PAREDES = "paredes"
USO_ESPACIOS = "espacios"
USO_PUERTAS = "puertas"
USO_TEXTOS = "textos"
USO_IGNORAR = "ignorar"

_PALABRAS: dict[str, tuple[str, ...]] = {
	USO_PAREDES: ("muro", "pared", "wall", "tabique", "mur", "estructura", "cerramiento"),
	USO_PUERTAS: ("puerta", "door", "carpint", "hueco"),
	USO_TEXTOS: ("texto", "text", "nombre", "rotul", "rótul", "label", "anot", "annot"),
	USO_ESPACIOS: ("espacio", "sala", "room", "area", "área", "superficie", "habitac", "recinto", "zona", "estancia"),
	USO_IGNORAR: (
		"ventan",
		"window",
		"cota",
		"dim",
		"mobil",
		"furn",
		"eje",
		"axis",
		"hatch",
		"sombre",
		"trama",
		"defpoints",
		"vegeta",
		"sanit",
		"instal",
		"elec",
	),
}

# Límites para que un plano equivocado no deje el programa colgado.
MAX_PAREDES = 20_000
MAX_ESPACIOS = 3_000
LADO_MAXIMO_M = 3_000.0
# Un contorno cerrado más fino que esto es el cuerpo de un muro, no una sala.
GROSOR_MURO_MAXIMO = 0.45

_TIPOS_POR_NOMBRE: tuple[tuple[tuple[str, ...], str], ...] = (
	(("pasillo", "corredor", "distribuidor", "corridor"), "pasillo"),
	(("vestíbulo", "vestibulo", "hall", "recibidor", "entrada", "zaguán"), "vestibulo"),
	(("escalera", "stair"), "escalera"),
	(("ascensor", "elevator", "lift"), "cabina"),
)
_USOS_POR_NOMBRE: tuple[tuple[tuple[str, ...], str], ...] = (
	(("dormitorio", "habitación", "habitacion", "bedroom"), "dormitorio"),
	(("salón", "salon", "estar", "comedor", "living"), "salon"),
	(("cocina", "kitchen"), "cocina"),
	(("baño", "bano", "aseo", "wc", "bath"), "bano"),
	(("aula", "clase", "classroom"), "aula"),
	(("oficina", "despacho", "office"), "oficina"),
)


@dataclass
class Trazo:
	"""Una línea quebrada del dibujo, en las unidades del fichero y con la y hacia arriba."""

	capa: str
	puntos: list[Punto]
	cerrado: bool = False
	origen: str = ""


@dataclass
class Rotulo:
	"""Un texto del dibujo con el punto donde está escrito."""

	capa: str
	texto: str
	x: float
	y: float
	alto: float = 0.0


@dataclass
class Arco:
	"""Un arco del dibujo: en un plano de arquitectura suele ser el barrido de una puerta."""

	capa: str
	centro: Punto
	radio: float
	inicio: float
	fin: float


@dataclass
class CapaPlano:
	"""Resumen de una capa para que el profesional decida qué hacer con ella."""

	nombre: str
	abiertos: int = 0
	cerrados: int = 0
	rotulos: int = 0
	arcos: int = 0
	longitud: float = 0.0
	sugerencia: str = USO_IGNORAR

	def descripcion(self) -> str:
		"""Frase para la lista de capas: qué contiene y para qué parece servir."""
		partes = []
		if self.cerrados:
			partes.append(frase_cuenta(self.cerrados, "{n} contorno cerrado", "{n} contornos cerrados"))
		if self.abiertos:
			partes.append(frase_cuenta(self.abiertos, "{n} línea", "{n} líneas"))
		if self.arcos:
			partes.append(frase_cuenta(self.arcos, "{n} arco", "{n} arcos"))
		if self.rotulos:
			partes.append(frase_cuenta(self.rotulos, "{n} texto", "{n} textos"))
		return _("{nombre}: {contenido}. Sugerencia: {uso}.").format(
			nombre=self.nombre, contenido=", ".join(partes) or _("vacía"), uso=_(self.sugerencia)
		)


@dataclass
class Plano:
	"""Un dibujo leído de un DXF o un SVG, todavía sin convertir."""

	formato: str = ""
	nombre: str = ""
	trazos: list[Trazo] = field(default_factory=list)
	rotulos: list[Rotulo] = field(default_factory=list)
	arcos: list[Arco] = field(default_factory=list)
	# Metros por unidad que declara el propio fichero (None si no lo dice).
	metros_por_unidad: float | None = None
	nota_unidades: str = ""
	avisos: list[str] = field(default_factory=list)

	def capas(self) -> list[CapaPlano]:
		"""Las capas del dibujo con lo que contiene cada una y una sugerencia de uso."""
		tabla: dict[str, CapaPlano] = {}
		for trazo in self.trazos:
			capa = tabla.setdefault(trazo.capa, CapaPlano(trazo.capa))
			if trazo.cerrado:
				capa.cerrados += 1
			else:
				capa.abiertos += 1
			capa.longitud += geo.longitud_linea(trazo.puntos)
		for rotulo in self.rotulos:
			tabla.setdefault(rotulo.capa, CapaPlano(rotulo.capa)).rotulos += 1
		for arco in self.arcos:
			tabla.setdefault(arco.capa, CapaPlano(arco.capa)).arcos += 1
		for capa in tabla.values():
			capa.sugerencia = _sugerir_uso(capa)
		return sorted(tabla.values(), key=lambda c: c.nombre.lower())

	def caja(self) -> tuple[float, float, float, float]:
		"""Caja envolvente del dibujo, en las unidades del fichero."""
		puntos = [p for trazo in self.trazos for p in trazo.puntos]
		puntos.extend((rotulo.x, rotulo.y) for rotulo in self.rotulos)
		if not puntos:
			return 0.0, 0.0, 0.0, 0.0
		return geo.caja(puntos)

	def sugerir_escala(self) -> tuple[float | None, str]:
		"""(metros por unidad, explicación) que se puede proponer al profesional; None si hay que preguntar.

		Si el fichero declara sus unidades, esas mandan. Si no, un dibujo de
		varios miles de unidades de lado solo puede estar en milímetros.
		"""
		if self.metros_por_unidad:
			return self.metros_por_unidad, self.nota_unidades
		x0, y0, x1, y1 = self.caja()
		lado = max(x1 - x0, y1 - y0)
		if lado >= 3000.0:
			return 0.001, _("El fichero no dice sus unidades; por el tamaño del dibujo parecen milímetros.")
		return None, _(
			"El fichero no dice sus unidades: el dibujo mide {ancho} por {alto} unidades. Indique cuántos metros es una unidad."
		).format(ancho=round(x1 - x0, 2), alto=round(y1 - y0, 2))


def _sugerir_uso(capa: CapaPlano) -> str:
	nombre = capa.nombre.lower()
	for uso in (USO_IGNORAR, USO_PUERTAS, USO_PAREDES, USO_TEXTOS, USO_ESPACIOS):
		if any(palabra in nombre for palabra in _PALABRAS[uso]):
			return uso
	if capa.cerrados and capa.cerrados >= capa.abiertos:
		return USO_ESPACIOS
	if capa.abiertos:
		return USO_PAREDES
	if capa.rotulos:
		return USO_TEXTOS
	if capa.arcos:
		return USO_PUERTAS
	return USO_IGNORAR


@dataclass
class OpcionesPlano:
	"""Decisiones del profesional al convertir un plano.

	Las listas de capas a None dejan que el programa use sus sugerencias.
	``origen`` es el punto del dibujo (en sus unidades) que será el (0, 0);
	sin él, la esquina inferior izquierda. Con ``entorno`` el plano se añade
	como una planta más a un entorno que ya existe.
	"""

	nombre: str = ""
	metros_por_unidad: float | None = None
	capas_paredes: list[str] | None = None
	capas_espacios: list[str] | None = None
	capas_puertas: list[str] | None = None
	capas_textos: list[str] | None = None
	origen: Punto | None = None
	nivel: int | None = None
	nombre_planta: str = ""
	rotulos_sueltos: bool = True
	entorno: Entorno | None = None


def _capas_elegidas(elegidas: list[str] | None, capas: Sequence[CapaPlano], usos: tuple[str, ...]) -> set[str]:
	if elegidas is not None:
		return set(elegidas)
	return {capa.nombre for capa in capas if capa.sugerencia in usos}


def _grosor(contorno: Sequence[Punto]) -> float:
	"""Grosor medio de un contorno: pequeño si es una tira larga y fina (el cuerpo de un muro)."""
	perimetro = geo.perimetro(contorno)
	return 2.0 * geo.area(contorno) / perimetro if perimetro > 0 else 0.0


def _tipo_y_uso(nombre: str) -> tuple[str, str]:
	"""(tipo de espacio, uso) que se deduce del nombre escrito en el plano."""
	bajo = nombre.lower()
	tipo = "habitacion"
	for palabras, candidato in _TIPOS_POR_NOMBRE:
		if any(palabra in bajo for palabra in palabras):
			tipo = candidato
			break
	for palabras, uso in _USOS_POR_NOMBRE:
		if any(palabra in bajo for palabra in palabras):
			return tipo, uso
	return tipo, ""


class _ConversorPlano:
	"""Estado de una conversión de plano: escala, planta que se va formando e informe."""

	def __init__(self, plano: Plano, opciones: OpcionesPlano, progreso: Progreso | None, cancelado: Cancelado | None) -> None:
		self.plano = plano
		self.op = opciones
		self.progreso = progreso
		self.cancelado = cancelado
		self.informe = Informe()
		self.escala = 1.0
		self.origen: Punto = (0.0, 0.0)
		self.entorno = opciones.entorno or Entorno()
		self.planta = Planta()
		self.espacios: list[Espacio] = []

	def punto(self, p: Punto) -> Punto:
		"""Punto del dibujo → metros del entorno."""
		return round((p[0] - self.origen[0]) * self.escala, 4), round((p[1] - self.origen[1]) * self.escala, 4)

	def _fijar_escala(self) -> None:
		sugerida, explicacion = self.plano.sugerir_escala()
		if self.op.metros_por_unidad is not None:
			escala = float(self.op.metros_por_unidad)
			if not math.isfinite(escala) or escala <= 0:
				raise ErrorImportacion(_("La escala tiene que ser un número mayor que cero (metros que mide una unidad del plano)."))
			self.informe.anotar_importado(
				_("Escala indicada: 1 unidad del plano son {metros} metros.").format(metros=f"{escala:g}".replace(".", separador_decimal()))
			)
		elif sugerida is not None:
			escala = sugerida
			self.informe.anotar_deducido(
				_(
					"Escala tomada del fichero: 1 unidad son {metros} metros. {explicacion} Mida una pared conocida para comprobarlo."
				).format(metros=f"{escala:g}".replace(".", separador_decimal()), explicacion=explicacion)
			)
		else:
			raise ErrorImportacion(explicacion)
		x0, y0, x1, y1 = self.plano.caja()
		lado = max(x1 - x0, y1 - y0) * escala
		if lado > LADO_MAXIMO_M:
			raise ErrorImportacion(
				_(
					"Con esa escala el plano mediría {metros} metros de lado, que no es creíble. Revise cuántos metros es una unidad."
				).format(metros=round(lado))
			)
		if lado < 0.5:
			raise ErrorImportacion(
				_("Con esa escala el plano mediría {centimetros} centímetros de lado. Revise cuántos metros es una unidad.").format(
					centimetros=round(lado * 100.0, 1)
				)
			)
		self.escala = escala
		self.origen = (float(self.op.origen[0]), float(self.op.origen[1])) if self.op.origen is not None else (x0, y0)

	def _crear_planta(self) -> None:
		nombre = self.op.nombre.strip() or self.plano.nombre or _("Plano importado")
		if self.op.entorno is None:
			self.entorno = ed.crear_entorno(
				nombre, _("Borrador importado de un plano. Revíselo y complételo antes de usarlo con un alumno.")
			)
		try:
			self.planta = ed.crear_planta(self.entorno, self.op.nombre_planta, nivel=self.op.nivel)
		except ed.ErrorEdicion as error:
			raise ErrorImportacion(str(error)) from error

	def _espacios(self, capas: set[str]) -> list[list[Punto]]:
		"""Crea un espacio por cada contorno cerrado; devuelve los contornos finos, que son muros."""
		contornos: list[list[Punto]] = []
		muros: list[list[Punto]] = []
		for trazo in self.plano.trazos:
			if not trazo.cerrado or trazo.capa not in capas:
				continue
			contorno = formas.limpiar_poligono([self.punto(p) for p in trazo.puntos], 0.01)
			if not formas.poligono_valido(contorno, 0.02):
				continue
			if _grosor(contorno) <= GROSOR_MURO_MAXIMO or geo.area(contorno) < 0.5:
				muros.append(contorno)
			else:
				contornos.append(geo.orientar_antihorario(contorno))
		if len(contornos) > MAX_ESPACIOS:
			raise ErrorImportacion(_("El plano tiene más de {n} contornos cerrados: elija menos capas.").format(n=MAX_ESPACIOS))
		contornos.sort(key=geo.area)
		envolventes = 0
		for indice, contorno in enumerate(contornos):
			contenidos = [otro for otro in contornos[:indice] if geo.punto_en_poligono(formas.punto_interior(otro), contorno)]
			if len(contenidos) >= 2 and sum(geo.area(otro) for otro in contenidos) >= 0.6 * geo.area(contorno):
				# Es el contorno del edificio, que envuelve a las salas: sus lados son muros, no una sala más.
				muros.append(contorno)
				envolventes += 1
				continue
			try:
				espacio = ed.crear_espacio_poligonal(self.entorno, self.planta, "", contorno, tipo="habitacion", permitir_solape=True)
			except ed.ErrorEdicion as error:
				log.info("Contorno del plano descartado: %s", error)
				continue
			self.espacios.append(espacio)
		if envolventes:
			self.informe.anotar_deducido(
				_(
					"Un contorno que envuelve a varias salas se ha tomado como el perímetro del edificio: sus lados se han puesto como paredes."
				)
			)
		return muros

	def _nombres(self, capas: set[str]) -> None:
		"""Pone a cada espacio el rótulo que cae dentro; los rótulos que quedan fuera pasan a ser referencias."""
		por_espacio: dict[str, list[Rotulo]] = {}
		sueltos: list[tuple[Rotulo, Punto]] = []
		for rotulo in self.plano.rotulos:
			if rotulo.capa not in capas or not rotulo.texto.strip():
				continue
			x, y = self.punto((rotulo.x, rotulo.y))
			espacio = self.planta.espacio_en(x, y)
			if espacio is None:
				sueltos.append((rotulo, (x, y)))
			else:
				por_espacio.setdefault(espacio.id, []).append(rotulo)
		sin_nombre = 0
		for numero, espacio in enumerate(self.espacios, start=1):
			rotulos = sorted(por_espacio.get(espacio.id, []), key=lambda r: -r.alto)
			if rotulos:
				espacio.nombre = " ".join(rotulos[0].texto.split())[:80]
				resto = [" ".join(r.texto.split()) for r in rotulos[1:]]
				if resto:
					espacio.descripcion = _("Otros textos del plano en esta sala: {textos}.").format(textos="; ".join(resto)[:300])
				tipo, uso = _tipo_y_uso(espacio.nombre)
				espacio.tipo = tipo
				espacio.acustica = ACUSTICA_POR_TIPO.get(tipo, espacio.acustica)
				if uso:
					espacio.datos["uso"] = uso
			else:
				sin_nombre += 1
				espacio.nombre = _("Espacio {n}").format(n=numero)
				espacio.descripcion = _("Nombre: el plano no lo dice.")
		if sin_nombre:
			self.informe.anotar_falta(
				_("{espacios} sin nombre en el plano: se han numerado.").format(
					espacios=frase_cuenta(sin_nombre, "{n} espacio", "{n} espacios")
				)
			)
		if self.op.rotulos_sueltos:
			for rotulo, (x, y) in sueltos[:300]:
				ed.anadir_referencia(
					self.entorno,
					self.planta,
					" ".join(rotulo.texto.split())[:80],
					x,
					y,
					tipo="punto",
					descripcion=_("Texto del plano que no cae dentro de ningún espacio."),
				)
			if sueltos:
				self.informe.anotar_importado(
					_("{textos} fuera de todo espacio, como referencias.").format(
						textos=frase_cuenta(min(len(sueltos), 300), "{n} texto", "{n} textos")
					)
				)

	def _sobre_espacio(self, a: Punto, b: Punto) -> bool:
		"""True si el segmento coincide con un lado de un espacio ya creado (sería una pared repetida)."""
		largo = geo.distancia(a, b)
		caja_tramo = geo.caja((a, b))
		for espacio in self.espacios:
			if not geo.cajas_se_tocan(caja_tramo, espacio.caja(), 0.1):
				continue
			for c, d in espacio.lados():
				intervalo = geo.intervalo_sobre_segmento(c, d, a, b, 0.03)
				if intervalo is not None and intervalo[1] - intervalo[0] >= largo * 0.95:
					return True
		return False

	def _paredes(self, capas: set[str], muros: list[list[Punto]]) -> int:
		"""Convierte las líneas de las capas de paredes en paredes sueltas."""
		segmentos: list[tuple[Punto, Punto, float]] = []
		for trazo in self.plano.trazos:
			if trazo.cerrado or trazo.capa not in capas:
				continue
			puntos = formas.sin_puntos_repetidos([self.punto(p) for p in trazo.puntos], 0.01)
			segmentos.extend((a, b, 0.1) for a, b in zip(puntos, puntos[1:], strict=False))
		for contorno in muros:
			if len(contorno) == 4 and _grosor(contorno) <= GROSOR_MURO_MAXIMO:
				lados = geo.lados(contorno)
				cortos = sorted(range(4), key=lambda i: geo.distancia(*lados[i]))[:2]
				a, b = geo.punto_medio(*lados[cortos[0]]), geo.punto_medio(*lados[cortos[1]])
				segmentos.append((a, b, max(0.05, geo.distancia(*lados[cortos[0]]))))
			else:
				segmentos.extend((a, b, 0.1) for a, b in geo.lados(contorno))
		creadas = 0
		for a, b, grosor in segmentos:
			if geo.distancia(a, b) < 0.05 or self._sobre_espacio(a, b):
				continue
			creadas += 1
			if creadas > MAX_PAREDES:
				raise ErrorImportacion(
					_("El plano tiene más de {n} tramos de pared: elija menos capas o simplifique el dibujo.").format(n=MAX_PAREDES)
				)
			if creadas % 500 == 0:
				comprobar_cancelacion(self.cancelado)
			ed.anadir_pared(self.entorno, self.planta, a, b, nombre=_("Pared"), grosor=grosor)
		return creadas

	def _puertas(self, capas: set[str]) -> int:
		"""Deduce puertas de los arcos de barrido: el centro es la bisagra y el radio, el ancho de la hoja."""
		creadas = 0
		for arco in self.plano.arcos:
			if arco.capa not in capas:
				continue
			radio = arco.radio * self.escala
			barrido = (arco.fin - arco.inicio) % 360.0
			if not (0.55 <= radio <= 1.4) or not (45.0 <= barrido <= 135.0):
				continue
			bisagra = self.punto(arco.centro)
			extremos = [
				self.punto(
					(
						arco.centro[0] + arco.radio * math.cos(math.radians(angulo)),
						arco.centro[1] + arco.radio * math.sin(math.radians(angulo)),
					)
				)
				for angulo in (arco.inicio, arco.fin)
			]
			mejor: tuple[float, Punto, Punto] | None = None
			candidatos = [lado for espacio in self.espacios for lado in espacio.lados()] + [
				(pared.a, pared.b) for pared in self.planta.paredes
			]
			for a, b in candidatos:
				if geo.distancia_punto_segmento(bisagra, a, b) > 0.25:
					continue
				for extremo in extremos:
					distancia = geo.distancia_punto_segmento(extremo, a, b)
					if distancia <= 0.25 and (mejor is None or distancia < mejor[0]):
						mejor = (distancia, geo.proyeccion_sobre_segmento(bisagra, a, b), geo.proyeccion_sobre_segmento(extremo, a, b))
			if mejor is None or geo.distancia(mejor[1], mejor[2]) < 0.5:
				continue
			abertura = Abertura(tipo="puerta", a=mejor[1], b=mejor[2], estado="cerrada", hoja="batiente")
			if any(
				(intervalo := geo.intervalo_sobre_segmento(abertura.a, abertura.b, otra.a, otra.b)) is not None
				and intervalo[1] - intervalo[0] > 0.01
				for otra in self.planta.aberturas
			):
				continue
			unidos = ed.espacios_de_abertura(self.planta, abertura)
			if len(unidos) >= 2:
				abertura.nombre = _("Puerta entre {a} y {b}").format(a=unidos[0].nombre, b=unidos[1].nombre)
			elif unidos:
				abertura.nombre = _("Puerta de {a}").format(a=unidos[0].nombre)
			else:
				abertura.nombre = _("Puerta")
			abertura.descripcion = _("Deducida del arco de barrido dibujado en el plano.")
			abertura.id = self.entorno.id_para(abertura)
			self.planta.aberturas.append(abertura)
			creadas += 1
		return creadas

	def ejecutar(self) -> ResultadoImportacion:
		"""Convierte el plano entero y devuelve el entorno con su informe."""
		avisar(self.progreso, 0.05, _("Preparando el plano."))
		if not self.plano.trazos:
			raise ErrorImportacion(_("El plano no tiene ninguna línea que se pueda importar."))
		capas = self.plano.capas()
		self._fijar_escala()
		self._crear_planta()
		for aviso in self.plano.avisos:
			self.informe.anotar_aviso(aviso)
		capas_paredes = _capas_elegidas(self.op.capas_paredes, capas, (USO_PAREDES,))
		capas_espacios = _capas_elegidas(self.op.capas_espacios, capas, (USO_ESPACIOS, USO_PAREDES))
		capas_puertas = _capas_elegidas(self.op.capas_puertas, capas, (USO_PUERTAS, USO_PAREDES))
		capas_textos = _capas_elegidas(self.op.capas_textos, capas, (USO_TEXTOS, USO_ESPACIOS, USO_PAREDES, USO_PUERTAS))
		if self.op.capas_paredes is None and not capas_paredes:
			capas_paredes = {capa.nombre for capa in capas if capa.abiertos and capa.sugerencia not in (USO_IGNORAR, USO_TEXTOS)}
		comprobar_cancelacion(self.cancelado)
		avisar(self.progreso, 0.25, _("Espacios."))
		muros = self._espacios(capas_espacios | capas_paredes)
		self._nombres(capas_textos)
		comprobar_cancelacion(self.cancelado)
		avisar(self.progreso, 0.55, _("Paredes."))
		paredes = self._paredes(capas_paredes, muros)
		comprobar_cancelacion(self.cancelado)
		avisar(self.progreso, 0.8, _("Puertas."))
		puertas = self._puertas(capas_puertas)
		self._terminar(paredes, puertas, sorted(capas_paredes))
		avisar(self.progreso, 1.0, _("Importación terminada."))
		return ResultadoImportacion(self.entorno, self.informe)

	def _terminar(self, paredes: int, puertas: int, capas_paredes: list[str]) -> None:
		informe = self.informe
		informe.titulo = _("Informe de la importación del plano «{nombre}»").format(nombre=self.entorno.nombre)
		informe.contar("espacios", len(self.espacios))
		informe.contar("paredes", paredes)
		informe.contar("puertas", puertas)
		informe.importado.insert(
			0,
			_("{espacios} y {paredes}. Capas usadas como paredes: {capas}.").format(
				espacios=frase_cuenta(len(self.espacios), "{n} espacio", "{n} espacios"),
				paredes=frase_cuenta(paredes, "{n} tramo de pared suelta", "{n} tramos de pared suelta"),
				capas=", ".join(capas_paredes) or _("ninguna"),
			),
		)
		if puertas:
			informe.anotar_deducido(
				_("{puertas} deducidas de los arcos de barrido del plano. Compruebe que están donde deben y hacia dónde abren.").format(
					puertas=frase_cuenta(puertas, "{n} puerta", "{n} puertas")
				)
			)
		else:
			informe.anotar_falta(
				_("El plano no dice dónde están las puertas: los espacios se han importado cerrados. Añada las puertas a mano.")
			)
		if not self.espacios:
			x0, y0, x1, y1 = self.planta.caja()
			zona = ed.crear_espacio_poligonal(
				self.entorno,
				self.planta,
				_("Planta completa"),
				geo.rectangulo(x0 - 1.0, y0 - 1.0, x1 - x0 + 2.0, y1 - y0 + 2.0),
				tipo="vestibulo",
				cerrado=False,
				descripcion=_("El plano solo tiene líneas sueltas, sin salas cerradas: esta zona cubre todo para que se pueda recorrer."),
			)
			self.espacios.append(zona)
			informe.anotar_deducido(
				_(
					"El plano no tiene contornos cerrados: se ha puesto una zona que cubre toda la planta. Dibuje las salas sobre las paredes importadas."
				)
			)
		informe.anotar_falta(
			_("Un plano no dice de qué es el suelo, cómo suena cada sala ni qué muebles hay: todo eso queda con los valores de serie.")
		)
		informe.anotar_revisar(_("Mida in situ una pared larga y compárela con el entorno, para confirmar la escala."))
		informe.anotar_revisar(
			_("Compruebe que cada sala tiene sus puertas y que las paredes sueltas no cortan pasos que en realidad están abiertos.")
		)
		candidatos = [(formas.punto_interior(e.contorno), 0.0) for e in sorted(self.espacios, key=lambda e: -e.area())]
		candidatos.extend(candidatos_en_rejilla(self.planta.caja(), 0.5))
		if self.op.entorno is None or not self.entorno.planta(self.entorno.inicio.planta) or self.entorno.inicio.planta == self.planta.id:
			if not fijar_inicio_valido(self.entorno, self.planta, candidatos):
				informe.anotar_aviso(_("No se ha encontrado un punto libre para el inicio: fíjelo a mano."))
		if self.op.entorno is None:
			self.entorno.procedencia = {
				"fuente": _("Plano {formato}: {nombre}").format(formato=self.plano.formato, nombre=self.plano.nombre or _("sin nombre")),
				"fecha": datetime.date.today().isoformat(),
				"escala": _("1 unidad del plano = {metros} m").format(metros=f"{self.escala:g}"),
				"licencia": "",
				"notas": _(
					"Borrador importado de un plano. El plano no ha salido del equipo. Las puertas, los suelos y los nombres que falten hay que añadirlos."
				),
			}


def convertir_plano(
	plano: Plano, opciones: OpcionesPlano | None = None, progreso: Progreso | None = None, cancelado: Cancelado | None = None
) -> ResultadoImportacion:
	"""Convierte un plano leído (DXF o SVG) en un entorno con una planta interior y su informe.

	Lanza ``ErrorImportacion`` si falta la escala y el fichero no la dice: el
	mensaje incluye las medidas del dibujo para poder preguntarla.
	"""
	return _ConversorPlano(plano, opciones or OpcionesPlano(), progreso, cancelado).ejecutar()
