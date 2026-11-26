"""Exportación de una planta a DXF por capas, con un escritor mínimo propio.

Sirve para llevar el plano a un programa de CAD: al arquitecto que va a
reformar el edificio, o a quien prepara una lámina en relieve con otra
herramienta. Se escribe DXF de texto en su variante más antigua y compatible
(R12): solo LINE, POLYLINE, ARC, TEXT y POINT, que abre cualquier programa.

Capas:

	ESPACIOS     contorno cerrado de cada espacio (salas, aceras, plazas)
	EDIFICIOS    contorno de los edificios macizos
	MUROS        tramos de pared: los de las salas y las paredes sueltas
	PUERTAS      puertas, portales y huecos, con el arco de barrido de las puertas
	VENTANAS     ventanas
	MOBILIARIO   huella de cada objeto
	TEXTOS       nombre de cada espacio
	REFERENCIAS  referencias y fuentes de sonido, con su nombre
	EJES_VIAS    eje de cada calle

Las unidades son metros. Como R12 no tiene dónde decirlo, el fichero empieza
con un comentario que el importador de EntornoLab reconoce: un DXF exportado
se puede volver a importar sin preguntar la escala. El texto se escribe en
Windows-1252, que es lo que esperan los programas de CAD para R12.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.formato import identificador_seguro
from app.dominio.geometria import Punto
from app.dominio.modelo import Entorno, Planta, segmentos_solidos
from app.importar.dxf import MARCA_METROS
from app.importar.formas import punto_interior
from app.importar.georef import texto_atribucion

log = logging.getLogger(__name__)

CODIFICACION = "cp1252"
# Capa → color de AutoCAD (índice): solo para que se distingan al abrir el fichero.
CAPAS: dict[str, int] = {
	"ESPACIOS": 8,
	"EDIFICIOS": 9,
	"MUROS": 7,
	"PUERTAS": 30,
	"VENTANAS": 5,
	"MOBILIARIO": 3,
	"TEXTOS": 2,
	"REFERENCIAS": 6,
	"EJES_VIAS": 1,
}
ALTO_TEXTO_ESPACIO = 0.3
ALTO_TEXTO_REFERENCIA = 0.15


def _numero(valor: float) -> str:
	texto = f"{valor:.4f}".rstrip("0").rstrip(".")
	return texto if texto not in ("", "-0") else "0"


def _texto_seguro(texto: str) -> str:
	"""Texto en una sola línea, que es lo único que admite un valor de DXF."""
	return " ".join(str(texto).split())[:250]


class _Escritor:
	"""Acumula las parejas código-valor de las entidades."""

	def __init__(self) -> None:
		self.lineas: list[str] = []
		self.caja: list[Punto] = []

	def par(self, codigo: int, valor: str | float | int) -> None:
		"""Añade una pareja código-valor: la unidad mínima de un DXF."""
		self.lineas.append(str(codigo))
		self.lineas.append(_numero(valor) if isinstance(valor, float) else str(valor))

	def _punto(self, punto: Punto, indice: int = 0) -> None:
		self.caja.append(punto)
		self.par(10 + indice, float(punto[0]))
		self.par(20 + indice, float(punto[1]))
		self.par(30 + indice, 0.0)

	def linea(self, capa: str, a: Punto, b: Punto) -> None:
		"""Entidad LINE entre dos puntos."""
		self.par(0, "LINE")
		self.par(8, capa)
		self._punto(a)
		self._punto(b, 1)

	def polilinea(self, capa: str, puntos: list[Punto], cerrada: bool) -> None:
		"""Entidad POLYLINE con sus VERTEX (la forma de R12, que abre cualquier programa)."""
		if len(puntos) < 2:
			return
		self.par(0, "POLYLINE")
		self.par(8, capa)
		self.par(66, 1)
		self.par(70, 1 if cerrada else 0)
		for punto in puntos:
			self.par(0, "VERTEX")
			self.par(8, capa)
			self._punto(punto)
		self.par(0, "SEQEND")
		self.par(8, capa)

	def arco(self, capa: str, centro: Punto, radio: float, inicio: float, fin: float) -> None:
		"""Entidad ARC, en sentido antihorario de ``inicio`` a ``fin`` grados."""
		self.par(0, "ARC")
		self.par(8, capa)
		self._punto(centro)
		self.par(40, float(radio))
		self.par(50, float(inicio % 360.0))
		self.par(51, float(fin % 360.0))

	def texto(self, capa: str, punto: Punto, alto: float, texto: str) -> None:
		"""Entidad TEXT de una línea; un texto vacío no se escribe."""
		contenido = _texto_seguro(texto)
		if not contenido:
			return
		self.par(0, "TEXT")
		self.par(8, capa)
		self._punto(punto)
		self.par(40, float(alto))
		self.par(1, contenido)

	def punto(self, capa: str, punto: Punto) -> None:
		"""Entidad POINT."""
		self.par(0, "POINT")
		self.par(8, capa)
		self._punto(punto)


def _arco_de_puerta(escritor: _Escritor, planta: Planta, a: Punto, b: Punto) -> None:
	"""Dibuja el barrido de una puerta con la bisagra en ``a``: es como se reconoce una puerta en un plano."""
	radio = geo.distancia(a, b)
	if not 0.5 <= radio <= 1.4:
		return
	rumbo = geo.rumbo_entre(a, b)
	# Ángulo matemático (antihorario desde el este) del tramo de la puerta.
	angulo = (90.0 - rumbo) % 360.0
	# El barrido va hacia el lado en que hay un espacio en el que se pueda estar.
	hacia_izquierda = geo.punto_a_distancia(geo.punto_medio(a, b), rumbo - 90.0, radio / 2.0)
	if planta.espacio_en(hacia_izquierda[0], hacia_izquierda[1], incluir_macizos=False) is not None:
		escritor.arco("PUERTAS", a, radio, angulo, angulo + 90.0)
	else:
		escritor.arco("PUERTAS", a, radio, angulo - 90.0, angulo)


def a_dxf(entorno: Entorno, planta: Planta, catalogo: Catalogo | None = None) -> str:
	"""El plano de una planta como texto DXF (R12), en metros y por capas."""
	escritor = _Escritor()
	for espacio in planta.espacios:
		if len(espacio.contorno) < 3 or espacio.datos.get("terreno_base"):
			continue
		escritor.polilinea("EDIFICIOS" if espacio.macizo else "ESPACIOS", list(espacio.contorno), True)
		if espacio.nombre:
			escritor.texto("TEXTOS", punto_interior(espacio.contorno), ALTO_TEXTO_ESPACIO, espacio.nombre)
	for segmento in segmentos_solidos(planta, None, incluir_puertas_cerradas=False):
		if segmento.clase == "pared":
			escritor.linea("MUROS", segmento.a, segmento.b)
	for pared in planta.paredes:
		if not pared.bloquea_paso:
			escritor.linea("MUROS", pared.a, pared.b)
	for abertura in planta.aberturas:
		if abertura.ancho < 0.01:
			continue
		if abertura.tipo == "ventana":
			escritor.linea("VENTANAS", abertura.a, abertura.b)
			continue
		escritor.linea("PUERTAS", abertura.a, abertura.b)
		if abertura.tipo in ("puerta", "portal"):
			_arco_de_puerta(escritor, planta, abertura.a, abertura.b)
	for objeto in planta.objetos:
		escritor.polilinea("MOBILIARIO", catalogo.huella(objeto) if catalogo is not None else objeto.huella_caja(), True)
		escritor.texto("MOBILIARIO", (objeto.x, objeto.y), ALTO_TEXTO_REFERENCIA, objeto.nombre)
	for elemento in list(planta.referencias) + list(planta.fuentes):
		escritor.punto("REFERENCIAS", (elemento.x, elemento.y))
		escritor.texto("REFERENCIAS", (elemento.x + 0.2, elemento.y + 0.2), ALTO_TEXTO_REFERENCIA, elemento.nombre)
	for via in planta.vias:
		escritor.polilinea("EJES_VIAS", list(via.eje), False)
	x0, y0, x1, y1 = geo.caja(escritor.caja) if escritor.caja else (0.0, 0.0, 0.0, 0.0)
	cabecera = _Escritor()
	cabecera.par(999, MARCA_METROS)
	cabecera.par(999, _texto_seguro(f"{entorno.nombre} - {planta.nombre}"))
	atribucion = texto_atribucion(entorno.procedencia)
	if atribucion:
		cabecera.par(999, _texto_seguro(atribucion))
	cabecera.par(0, "SECTION")
	cabecera.par(2, "HEADER")
	cabecera.par(9, "$ACADVER")
	cabecera.par(1, "AC1009")
	cabecera.par(9, "$DWGCODEPAGE")
	cabecera.par(3, "ANSI_1252")
	cabecera.par(9, "$EXTMIN")
	cabecera.par(10, float(x0))
	cabecera.par(20, float(y0))
	cabecera.par(9, "$EXTMAX")
	cabecera.par(10, float(x1))
	cabecera.par(20, float(y1))
	cabecera.par(0, "ENDSEC")
	cabecera.par(0, "SECTION")
	cabecera.par(2, "TABLES")
	cabecera.par(0, "TABLE")
	cabecera.par(2, "LTYPE")
	cabecera.par(70, 1)
	cabecera.par(0, "LTYPE")
	cabecera.par(2, "CONTINUOUS")
	cabecera.par(70, 0)
	cabecera.par(3, "Solid line")
	cabecera.par(72, 65)
	cabecera.par(73, 0)
	cabecera.par(40, 0.0)
	cabecera.par(0, "ENDTAB")
	cabecera.par(0, "TABLE")
	cabecera.par(2, "LAYER")
	cabecera.par(70, len(CAPAS))
	for capa, color in CAPAS.items():
		cabecera.par(0, "LAYER")
		cabecera.par(2, capa)
		cabecera.par(70, 0)
		cabecera.par(62, color)
		cabecera.par(6, "CONTINUOUS")
	cabecera.par(0, "ENDTAB")
	cabecera.par(0, "ENDSEC")
	cabecera.par(0, "SECTION")
	cabecera.par(2, "ENTITIES")
	final = _Escritor()
	final.par(0, "ENDSEC")
	final.par(0, "EOF")
	return "\n".join(cabecera.lineas + escritor.lineas + final.lineas) + "\n"


def guardar_dxf(entorno: Entorno, carpeta: str | os.PathLike[str], catalogo: Catalogo | None = None) -> list[Path]:
	"""Escribe un ``.dxf`` por planta en ``carpeta`` y devuelve sus rutas."""
	destino = Path(carpeta)
	destino.mkdir(parents=True, exist_ok=True)
	base = identificador_seguro(entorno.nombre or entorno.id, "entorno")
	escritos: list[Path] = []
	for planta in entorno.plantas:
		ruta = destino / f"{base}_{identificador_seguro(planta.nombre or planta.id, 'planta')}.dxf"
		ruta.write_bytes(a_dxf(entorno, planta, catalogo).replace("\n", "\r\n").encode(CODIFICACION, errors="replace"))
		escritos.append(ruta)
	log.info("DXF de «%s»: %s ficheros", entorno.nombre, len(escritos))
	return escritos
