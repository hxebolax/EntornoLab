"""Piezas que comparten todos los importadores: errores, informe, progreso, lectura segura y punto de inicio.

Están juntas para que cada importador (OpenStreetMap, DXF, SVG, GPX) hable
igual con la interfaz: la misma forma de avisar del avance, de cancelar, de
fallar con un mensaje legible y de contar al profesional qué se ha hecho.
"""

from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from xml.parsers import expat

from app.core.i18n import _, _n
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.geometria import Punto
from app.dominio.modelo import Entorno, Planta, Posicion, segmentos_solidos

log = logging.getLogger(__name__)

# Una función de progreso recibe la fracción hecha (0 a 1) y una frase corta.
Progreso = Callable[[float, str], None]
# Una función de cancelación devuelve True cuando el profesional ha pedido parar.
Cancelado = Callable[[], bool]

# Separación mínima entre el punto de inicio y cualquier muro (la validación exige 0,2).
MARGEN_INICIO = 0.35

MAX_PROFUNDIDAD_XML = 200


class ErrorImportacion(Exception):
	"""La importación no se puede hacer; el mensaje está pensado para leerlo tal cual a la persona."""


class ImportacionCancelada(ErrorImportacion):
	"""El profesional canceló la importación a medias."""


def sin_progreso(fraccion: float, texto: str) -> None:
	"""Progreso que solo deja rastro en el registro: para llamadas sin interfaz."""
	log.debug("Importación al %s %%: %s", round(fraccion * 100), texto)


def avisar(progreso: Progreso | None, fraccion: float, texto: str) -> None:
	"""Llama a la función de progreso si la hay, con la fracción acotada entre 0 y 1."""
	(progreso or sin_progreso)(max(0.0, min(1.0, fraccion)), texto)


def avisar_fase(
	progreso: Progreso | None,
	fraccion: float,
	fase: str,
	texto: str = "",
	hecho: int | None = None,
	total: int | None = None,
	indeterminado: bool = False,
) -> None:
	"""Avisa del avance diciendo además en qué FASE está y, si se sabe, cuánto lleva de cuánto.

	Por qué: el profesional que espera una importación larga con lector de
	pantalla necesita oír «Convirtiendo calles: 12 de 30», no un porcentaje
	suelto, para saber que la aplicación sigue viva y qué está haciendo.

	Es compatible con cualquier función ``progreso(fraccion, texto)``: esa
	recibe la fracción y el texto completo. Si además tiene un método
	``por_fases(fraccion, texto, fase, hecho, total, indeterminado)`` (lo
	tiene la de ``app.ui.dialogo_progreso.progreso_de_tarea``), se llama a
	ese en su lugar, para que el diálogo pueda anunciar los cambios de fase y
	poner la barra indeterminada cuando no se sabe el total (una descarga
	cuyo tamaño no dice el servidor). Se llama desde el hilo de trabajo: la
	función de progreso NUNCA debe tocar controles wx directamente.
	"""
	texto = texto or fase
	por_fases = getattr(progreso, "por_fases", None)
	if callable(por_fases):
		por_fases(max(0.0, min(1.0, fraccion)), texto, fase, hecho, total, indeterminado)
		return
	avisar(progreso, fraccion, texto)


def texto_duracion(segundos: float) -> str:
	"""«10 segundos», «1 minuto», «2 minutos y 10 segundos»: una duración aproximada, dicha con palabras."""
	total = max(1, round(segundos))
	minutos, resto = divmod(total, 60)
	if not minutos:
		return _n("{n} segundo", "{n} segundos", resto).format(n=resto)
	texto_minutos = _n("{n} minuto", "{n} minutos", minutos).format(n=minutos)
	if not resto:
		return texto_minutos
	return _("{minutos} y {segundos}").format(minutos=texto_minutos, segundos=_n("{n} segundo", "{n} segundos", resto).format(n=resto))


def comprobar_cancelacion(cancelado: Cancelado | None) -> None:
	"""Lanza ``ImportacionCancelada`` si se ha pedido parar.

	Se llama entre fases: así una importación larga se corta pronto sin
	dejar nada a medias (el entorno a medio hacer se descarta entero).
	"""
	if cancelado is not None and cancelado():
		raise ImportacionCancelada(_("Importación cancelada."))


# ── Informe ──────────────────────────────────────────────────────────────────


@dataclass
class Informe:
	"""Lo que el profesional tiene que saber del borrador recién importado.

	Cuatro listas, porque son cuatro grados de confianza distintos:
	``importado`` (lo dice la fuente), ``deducido`` (lo ha calculado el
	programa y puede no ser así), ``falta`` (la fuente no lo dice) y
	``revisar`` (hay que comprobarlo en el sitio). ``avisos`` recoge lo que
	no se pudo convertir.
	"""

	titulo: str = ""
	importado: list[str] = field(default_factory=list)
	deducido: list[str] = field(default_factory=list)
	falta: list[str] = field(default_factory=list)
	revisar: list[str] = field(default_factory=list)
	avisos: list[str] = field(default_factory=list)
	cuentas: dict[str, int] = field(default_factory=dict)

	def contar(self, clave: str, cantidad: int = 1) -> None:
		"""Suma al recuento de una clase de elemento (para pruebas y resúmenes)."""
		self.cuentas[clave] = self.cuentas.get(clave, 0) + cantidad

	def _anadir(self, lista: list[str], frase: str) -> None:
		if frase and frase not in lista:
			lista.append(frase)

	def anotar_importado(self, frase: str) -> None:
		"""Algo que la fuente dice y se ha traído tal cual."""
		self._anadir(self.importado, frase)

	def anotar_deducido(self, frase: str) -> None:
		"""Algo que el programa ha calculado porque la fuente no lo daba."""
		self._anadir(self.deducido, frase)

	def anotar_falta(self, frase: str) -> None:
		"""Algo que la fuente no dice."""
		self._anadir(self.falta, frase)

	def anotar_revisar(self, frase: str) -> None:
		"""Algo que conviene comprobar en el sitio."""
		self._anadir(self.revisar, frase)

	def anotar_aviso(self, frase: str) -> None:
		"""Algo que no se ha podido convertir."""
		self._anadir(self.avisos, frase)

	def secciones(self) -> list[tuple[str, list[str]]]:
		"""(título, frases) de cada apartado que tiene contenido, en el orden en que se lee."""
		todas = [
			(_("Importado"), self.importado),
			(_("Deducido por el programa (puede no ser así)"), self.deducido),
			(_("Lo que la fuente no dice"), self.falta),
			(_("Conviene revisar in situ"), self.revisar),
			(_("No se ha podido convertir"), self.avisos),
		]
		return [(titulo, frases) for titulo, frases in todas if frases]

	def a_texto(self) -> str:
		"""El informe entero en texto llano: una frase por línea, apto para lector de pantalla."""
		lineas: list[str] = []
		if self.titulo:
			lineas.append(self.titulo)
		for titulo, frases in self.secciones():
			if lineas:
				lineas.append("")
			lineas.append(titulo + ":")
			lineas.extend("- " + frase for frase in frases)
		return "\n".join(lineas)

	def a_dict(self) -> dict[str, Any]:
		"""El informe como diccionario, para guardarlo junto al entorno si se quiere."""
		return {
			"titulo": self.titulo,
			"importado": list(self.importado),
			"deducido": list(self.deducido),
			"falta": list(self.falta),
			"revisar": list(self.revisar),
			"avisos": list(self.avisos),
			"cuentas": dict(self.cuentas),
		}


@dataclass
class ResultadoImportacion:
	"""Lo que devuelve cualquier importador: el borrador y su informe."""

	entorno: Entorno
	informe: Informe


def frase_cuenta(cantidad: int, uno: str, varios: str) -> str:
	"""«1 edificio», «3 edificios»: recuento con su plural."""
	return _n(uno, varios, cantidad).format(n=cantidad)


# ── Lectura segura de ficheros ───────────────────────────────────────────────


def leer_fichero(ruta: str | os.PathLike[str], max_bytes: int) -> bytes:
	"""Lee un fichero entero comprobando antes que no pasa de ``max_bytes``.

	El límite evita que un fichero equivocado (un vídeo, una copia de
	seguridad) deje el programa sin memoria.
	"""
	camino = Path(ruta)
	try:
		tamano = camino.stat().st_size
	except OSError as error:
		raise ErrorImportacion(_("No se puede leer «{ruta}»: {motivo}").format(ruta=camino.name, motivo=error.strerror or error)) from error
	if tamano > max_bytes:
		raise ErrorImportacion(
			_("«{ruta}» ocupa {megas} MB y el máximo que se puede importar son {maximo} MB.").format(
				ruta=camino.name, megas=round(tamano / 1048576, 1), maximo=round(max_bytes / 1048576, 1)
			)
		)
	try:
		return camino.read_bytes()
	except OSError as error:
		raise ErrorImportacion(_("No se puede leer «{ruta}»: {motivo}").format(ruta=camino.name, motivo=error.strerror or error)) from error


def decodificar_texto(datos: bytes) -> str:
	"""Texto de un fichero que debería ser UTF-8 pero puede venir de un programa antiguo de Windows."""
	try:
		return datos.decode("utf-8-sig")
	except UnicodeDecodeError:
		log.info("El fichero no es UTF-8; se lee como Windows-1252.")
		return datos.decode("cp1252", errors="replace")


def nombre_local(nombre: str) -> str:
	"""Nombre de etiqueta o atributo XML sin su prefijo de espacio de nombres (``svg:rect`` → ``rect``)."""
	return nombre.rsplit(":", 1)[-1]


def analizar_xml_seguro(datos: bytes, max_bytes: int, max_elementos: int) -> ET.Element:
	"""Analiza un XML que viene de fuera sin fiarse de él.

	Un XML puede declarar entidades que al expandirse ocupan gigas, o que
	apuntan a ficheros del equipo o a direcciones de Internet. Aquí se
	rechaza cualquier declaración DOCTYPE o de entidad antes de expandir
	nada, se limita el tamaño, el número de elementos y la profundidad, y no
	se resuelve ninguna referencia externa. Los nombres salen sin prefijo.
	"""
	if len(datos) > max_bytes:
		raise ErrorImportacion(
			_("El fichero ocupa {megas} MB y el máximo que se puede importar son {maximo} MB.").format(
				megas=round(len(datos) / 1048576, 1), maximo=round(max_bytes / 1048576, 1)
			)
		)
	constructor = ET.TreeBuilder()
	estado = {"elementos": 0, "profundidad": 0}

	def al_abrir(nombre: str, atributos: dict[str, str]) -> None:
		estado["elementos"] += 1
		estado["profundidad"] += 1
		if estado["elementos"] > max_elementos:
			raise ErrorImportacion(
				_("El fichero tiene más de {n} elementos: es demasiado grande para importarlo. Simplifíquelo o divídalo.").format(
					n=max_elementos
				)
			)
		if estado["profundidad"] > MAX_PROFUNDIDAD_XML:
			raise ErrorImportacion(_("El fichero tiene demasiados niveles anidados; no parece un plano normal."))
		constructor.start(nombre_local(nombre), {nombre_local(clave): valor for clave, valor in atributos.items()})

	def al_cerrar(nombre: str) -> None:
		estado["profundidad"] -= 1
		constructor.end(nombre_local(nombre))

	def prohibido(*_argumentos: Any) -> None:
		raise ErrorImportacion(
			_("El fichero declara entidades o un DOCTYPE. Por seguridad no se importa: guárdelo de nuevo sin esas declaraciones.")
		)

	analizador = expat.ParserCreate()
	analizador.buffer_text = True
	analizador.StartElementHandler = al_abrir
	analizador.EndElementHandler = al_cerrar
	analizador.CharacterDataHandler = constructor.data
	analizador.StartDoctypeDeclHandler = prohibido
	analizador.EntityDeclHandler = prohibido
	analizador.UnparsedEntityDeclHandler = prohibido
	analizador.ExternalEntityRefHandler = prohibido
	analizador.SetParamEntityParsing(expat.XML_PARAM_ENTITY_PARSING_NEVER)
	try:
		analizador.Parse(datos, True)
		return constructor.close()
	except expat.ExpatError as error:
		raise ErrorImportacion(_("El fichero no es un XML válido (línea {linea}).").format(linea=error.lineno)) from error
	except AssertionError as error:
		# TreeBuilder se queja así de un documento vacío o mal cerrado.
		raise ErrorImportacion(_("El fichero XML está vacío o incompleto.")) from error


# ── Punto de inicio ──────────────────────────────────────────────────────────


def punto_valido_de_inicio(planta: Planta, punto: Punto, catalogo: Catalogo | None = None) -> bool:
	"""True si un alumno puede empezar ahí: dentro de un espacio, fuera de macizos, muros y objetos."""
	espacios = planta.espacios_en(punto[0], punto[1])
	if not espacios or any(espacio.macizo for espacio in espacios):
		return False
	for segmento in segmentos_solidos(planta):
		if geo.distancia_punto_segmento(punto, segmento.a, segmento.b) < MARGEN_INICIO:
			return False
	for objeto in planta.objetos:
		huella = catalogo.huella(objeto) if catalogo is not None else objeto.huella_caja()
		if geo.distancia_punto_poligono(punto, huella) < MARGEN_INICIO:
			return False
	return True


def fijar_inicio_valido(
	entorno: Entorno, planta: Planta, candidatos: Iterable[tuple[Punto, float]], catalogo: Catalogo | None = None
) -> bool:
	"""Pone el inicio en el primer candidato (punto, rumbo) que sirve; False si ninguno sirve.

	Un borrador importado tiene que poder recorrerse nada más crearlo: por
	eso el inicio no se deja en el (0, 0), que puede caer dentro de un muro.
	"""
	for punto, rumbo in candidatos:
		if punto_valido_de_inicio(planta, punto, catalogo):
			entorno.inicio = Posicion(planta=planta.id, x=round(punto[0], 2), y=round(punto[1], 2), rumbo=geo.normalizar_rumbo(rumbo))
			return True
	return False


def candidatos_en_rejilla(caja: tuple[float, float, float, float], paso: float = 1.0, maximo: int = 4000) -> list[tuple[Punto, float]]:
	"""Puntos de una rejilla sobre la caja, del centro hacia fuera: último recurso para encontrar inicio."""
	x0, y0, x1, y1 = caja
	centro = ((x0 + x1) / 2.0, (y0 + y1) / 2.0)
	columnas = max(1, int((x1 - x0) / paso))
	filas = max(1, int((y1 - y0) / paso))
	while columnas * filas > maximo:
		paso *= 1.5
		columnas = max(1, int((x1 - x0) / paso))
		filas = max(1, int((y1 - y0) / paso))
	puntos = [(x0 + (i + 0.5) * paso, y0 + (j + 0.5) * paso) for i in range(columnas) for j in range(filas)]
	puntos.sort(key=lambda p: geo.distancia(p, centro))
	return [(p, 0.0) for p in puntos]
