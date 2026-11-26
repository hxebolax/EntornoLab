"""Catálogo de complementos: los objetos con los que se amuebla un entorno.

Los objetos no están dentro del programa: vienen en complementos, carpetas
``data/plugins/<id>/`` con un ``complemento.json`` y, si hace falta, sonidos,
imágenes y traducciones. Un complemento es SOLO datos; nunca se ejecuta nada
de él, así que instalar el de otra persona no supone un riesgo.

Un objeto no es un dibujo: es una FORMA con medidas reales (su huella en
planta y su altura) que el alumno se encuentra y tiene que esquivar. Por eso
el catálogo sabe calcular la huella exacta de cada objeto colocado y ajustar
sus medidas al hueco disponible sin salirse nunca del rango que declara el
complemento: una mesa no puede quedar más grande que la habitación.

Si un entorno usa un tipo que no está instalado, el objeto se conserva como
una caja con sus medidas: el entorno sigue abriéndose y recorriéndose.
"""

from __future__ import annotations

import functools
import json
import logging
import re
import shutil
import unicodedata
import weakref
import zipfile
from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any

from app.core import i18n, paths
from app.core.i18n import N_, _
from app.dominio import geometria as geo
from app.dominio.formato import (
	EXTENSIONES_IMAGEN,
	EXTENSIONES_SONIDO,
	MAX_BYTES_JSON,
	MAX_BYTES_RECURSO,
	ErrorFormato,
	comprobar_zip,
	leer_entrada,
	leer_json,
)
from app.dominio.geometria import Punto
from app.dominio.modelo import SUELOS, Aviso, Objeto

log = logging.getLogger(__name__)

FORMATO_COMPLEMENTO = 1
NOMBRE_FICHA = "complemento.json"
EXTENSION_COMPLEMENTO = ".elabc"
CARPETA_PLUGINS = "plugins"
TIPO_CAJA = "caja"

FORMAS = ("rectangulo", "circulo", "ele", "poligono")
AMBITOS: dict[str, str] = {"interior": N_("Interior"), "exterior": N_("Exterior")}
COLOCACIONES: dict[str, str] = {
	"suelo": N_("En el suelo"),
	"pared": N_("Contra una pared"),
	"esquina": N_("En una esquina"),
	"acera": N_("En la acera"),
	"calzada": N_("En la calzada"),
}
DIMENSIONES = ("ancho", "fondo", "alto")

# Forma en ele de serie: el brazo largo ocupa todo el ancho por detrás.
PUNTOS_ELE: list[Punto] = [(0.0, 0.0), (1.0, 0.0), (1.0, 0.5), (0.5, 0.5), (0.5, 1.0), (0.0, 1.0)]
# Lados del polígono con el que se aproxima un objeto redondo.
LADOS_CIRCULO = 16
# Medidas de serie cuando un complemento no dice nada: una caja de un metro.
MEDIDA_SERIE: tuple[float, float, float] = (0.1, 1.0, 10.0)

_PATRON_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_PATRON_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")
# Carpeta del complemento donde van sus sonidos; un nombre que empieza por ella es un fichero suyo.
CARPETA_SONIDOS = "sonidos"
# Comportamientos que un objeto puede declarar en «dinamica» (los interpreta el motor).
DINAMICAS = ("semaforo", "temporizador")
# Separador entre un complemento del que se depende y el fichero de sonido que se le pide: «comun:sentarse.flac».
SEPARADOR_DEPENDENCIA = ":"

# ── Taxonomía ────────────────────────────────────────────────────────────────
#
# Con miles de objetos, encontrarlos depende de clasificarlos bien. Los valores
# son CERRADOS (los comprueba ``validar_complemento``) para que un control de
# árbol o una lista de filtros enseñen siempre las mismas opciones, y cada uno
# tiene su nombre visible traducible. Para orientación y movilidad importa
# sobre todo ``OBSTACULOS``: a qué altura queda el objeto y si el bastón lo
# encuentra.

# Para qué sirve el objeto.
FUNCIONES: dict[str, str] = {
	"asiento": N_("Asiento"),
	"mesa": N_("Mesa o superficie de trabajo"),
	"mostrador": N_("Mostrador o barra"),
	"descanso": N_("Cama o descanso"),
	"almacenaje": N_("Almacenaje"),
	"expositor": N_("Expositor o vitrina"),
	"electrodomestico": N_("Electrodoméstico"),
	"maquina": N_("Máquina o aparato"),
	"sanitario": N_("Sanitario o fontanería"),
	"iluminacion": N_("Iluminación"),
	"climatizacion": N_("Climatización"),
	"senalizacion": N_("Señalización e información"),
	"referencia": N_("Referencia en el suelo o táctil"),
	"barrera": N_("Barrera o cierre"),
	"control_acceso": N_("Control de acceso"),
	"estructura": N_("Elemento del edificio o de la vía"),
	"vegetacion": N_("Vegetación"),
	"vehiculo": N_("Vehículo"),
	"juego": N_("Juego o juguete"),
	"deporte": N_("Deporte"),
	"instrumento": N_("Instrumento musical"),
	"ayuda_tecnica": N_("Ayuda técnica o apoyo"),
	"equipo_medico": N_("Equipo sanitario"),
	"residuos": N_("Residuos y limpieza"),
	"decoracion": N_("Decoración"),
	"comunicacion": N_("Comunicación"),
	"pago": N_("Pago y venta automática"),
	"seguridad": N_("Seguridad y emergencia"),
	"herramienta": N_("Herramienta o equipo de trabajo"),
	"carga": N_("Carga y mercancías"),
	"agua": N_("Agua"),
	"animal": N_("Animal o personaje"),
	"trasto": N_("Trasto u obstáculo suelto"),
	"fantasia": N_("Elemento fantástico"),
}

# En qué tipos de lugar es habitual.
LUGARES: dict[str, str] = {
	"vivienda": N_("Vivienda"),
	"comunidad": N_("Edificio de viviendas"),
	"colegio": N_("Colegio o instituto"),
	"guarderia": N_("Guardería o escuela infantil"),
	"universidad": N_("Universidad"),
	"oficina": N_("Oficina"),
	"tienda": N_("Tienda"),
	"supermercado": N_("Supermercado"),
	"centro_comercial": N_("Centro comercial"),
	"bar": N_("Bar o cafetería"),
	"restaurante": N_("Restaurante"),
	"hotel": N_("Hotel"),
	"hospital": N_("Hospital"),
	"centro_salud": N_("Centro de salud o consulta"),
	"farmacia": N_("Farmacia"),
	"residencia": N_("Residencia"),
	"administracion": N_("Administración pública"),
	"banco": N_("Banco"),
	"servicios": N_("Servicios (peluquería, lavandería, correos)"),
	"culto": N_("Lugar de culto o tanatorio"),
	"museo": N_("Museo o sala de exposiciones"),
	"biblioteca": N_("Biblioteca"),
	"cine_teatro": N_("Cine, teatro o auditorio"),
	"ocio": N_("Ocio (bolera, recreativos, centro cívico)"),
	"polideportivo": N_("Polideportivo"),
	"gimnasio": N_("Gimnasio"),
	"piscina": N_("Piscina"),
	"parque": N_("Parque o jardín público"),
	"parque_infantil": N_("Parque infantil"),
	"playa": N_("Playa"),
	"naturaleza": N_("Campo y naturaleza"),
	"jardin": N_("Jardín o huerto"),
	"calle": N_("Calle"),
	"obra": N_("Obra"),
	"aparcamiento": N_("Aparcamiento"),
	"parada": N_("Parada de transporte"),
	"estacion": N_("Estación de tren, metro o autobús"),
	"aeropuerto": N_("Aeropuerto"),
	"puerto": N_("Puerto"),
	"taller": N_("Taller"),
	"almacen": N_("Almacén"),
	"fabrica": N_("Fábrica"),
	"laboratorio": N_("Laboratorio"),
	"fantasia": N_("Mundo de fantasía"),
	"cualquiera": N_("Cualquier lugar"),
}

# En qué estancia o zona de esos lugares suele estar.
ESTANCIAS: dict[str, str] = {
	"salon": N_("Salón"),
	"comedor": N_("Comedor"),
	"cocina": N_("Cocina"),
	"dormitorio": N_("Dormitorio"),
	"habitacion_infantil": N_("Habitación infantil"),
	"bano": N_("Baño o aseo"),
	"aseo_adaptado": N_("Aseo adaptado"),
	"entrada": N_("Entrada o recibidor"),
	"pasillo": N_("Pasillo"),
	"terraza": N_("Terraza o balcón"),
	"lavadero": N_("Lavadero"),
	"trastero": N_("Trastero"),
	"garaje": N_("Garaje"),
	"portal": N_("Portal"),
	"rellano": N_("Escalera y rellano"),
	"patio": N_("Patio"),
	"azotea": N_("Azotea"),
	"cuarto_instalaciones": N_("Cuarto de instalaciones o de basuras"),
	"aula": N_("Aula"),
	"aula_infantil": N_("Aula infantil o sala de cunas"),
	"aula_grada": N_("Aula en grada"),
	"laboratorio": N_("Laboratorio"),
	"patio_recreo": N_("Patio de recreo"),
	"comedor_colectivo": N_("Comedor colectivo"),
	"sala_lectura": N_("Sala de lectura"),
	"despacho": N_("Despacho"),
	"zona_trabajo": N_("Zona de trabajo de oficina"),
	"sala_reuniones": N_("Sala de reuniones"),
	"recepcion": N_("Recepción"),
	"sala_espera": N_("Sala de espera"),
	"ventanilla": N_("Atención al público"),
	"cajeros": N_("Zona de cajeros"),
	"consulta": N_("Consulta médica"),
	"habitacion_hospital": N_("Habitación de hospital"),
	"urgencias": N_("Urgencias"),
	"sala_rehabilitacion": N_("Sala de rehabilitación"),
	"sala_comun": N_("Sala de estar común"),
	"barra": N_("Barra de bar"),
	"sala_restaurante": N_("Sala de restaurante o cafetería"),
	"terraza_bar": N_("Terraza de bar"),
	"cocina_profesional": N_("Cocina profesional"),
	"habitacion_hotel": N_("Habitación de hotel"),
	"vestibulo": N_("Vestíbulo"),
	"sala_ventas": N_("Sala de ventas"),
	"cajas": N_("Línea de cajas"),
	"probador": N_("Probadores"),
	"trastienda": N_("Trastienda"),
	"galeria_comercial": N_("Galería de centro comercial"),
	"sala_exposicion": N_("Sala de exposición"),
	"sala_butacas": N_("Sala de butacas"),
	"escenario": N_("Escenario"),
	"taquilla": N_("Taquillas y venta de entradas"),
	"salon_actos": N_("Salón de actos"),
	"sala_juegos": N_("Sala de juegos"),
	"pista": N_("Pista deportiva"),
	"sala_musculacion": N_("Sala de musculación"),
	"vestuario": N_("Vestuario"),
	"grada": N_("Grada"),
	"vaso_piscina": N_("Vaso y playa de piscina"),
	"zona_juegos": N_("Zona de juegos infantiles"),
	"zona_canina": N_("Zona canina"),
	"merendero": N_("Merendero"),
	"sendero": N_("Sendero o camino"),
	"arena_playa": N_("Arena de playa"),
	"jardin": N_("Jardín"),
	"huerto": N_("Huerto"),
	"acera": N_("Acera"),
	"calzada": N_("Calzada"),
	"cruce": N_("Cruce o paso de peatones"),
	"plaza": N_("Plaza"),
	"parada": N_("Parada"),
	"anden": N_("Andén"),
	"control_seguridad": N_("Control de seguridad"),
	"facturacion": N_("Facturación"),
	"puerta_embarque": N_("Puerta de embarque"),
	"recogida_equipajes": N_("Recogida de equipajes"),
	"plaza_aparcamiento": N_("Plazas de aparcamiento"),
	"nave": N_("Nave de taller o fábrica"),
	"almacen": N_("Almacén"),
	"muelle_carga": N_("Muelle de carga"),
	"zona_obra": N_("Zona de obras"),
	"sala_culto": N_("Sala de culto"),
	"velatorio": N_("Velatorio"),
	"salon_servicio": N_("Local de servicios"),
	"castillo": N_("Castillo"),
	"cueva": N_("Cueva"),
	"bosque": N_("Bosque"),
	"nave_espacial": N_("Nave espacial"),
	"isla": N_("Isla"),
	"interior_vehiculo": N_("Dentro de un autobús, tranvía, metro o tren"),
	"cualquiera": N_("Cualquier estancia"),
}

# A qué altura queda el objeto como obstáculo: lo que el bastón encuentra y lo que no.
OBSTACULOS: dict[str, str] = {
	"ras_suelo": N_("A ras de suelo: se pisa"),
	"bajo": N_("Bajo: por debajo de la rodilla"),
	"medio": N_("A media altura: de la rodilla al pecho"),
	"alto": N_("Alto: de cuerpo entero"),
	"voladizo": N_("En voladizo: el bastón pasa por debajo"),
	"cabeza": N_("A la altura de la cabeza"),
	"aereo": N_("Por encima de la cabeza"),
}

# Riesgos añadidos, además de la altura.
RIESGOS: dict[str, str] = {
	"movil": N_("Se mueve"),
	"temporal": N_("Temporal: cambia de un día a otro"),
	"desnivel": N_("Desnivel o hueco"),
	"caliente": N_("Quema"),
	"transparente": N_("Transparente o difícil de ver"),
	"resbaladizo": N_("Resbala o moja"),
}

# Lo habitual que es, para ordenar los resultados.
FRECUENCIAS: dict[str, str] = {
	"muy_comun": N_("Muy común"),
	"comun": N_("Común"),
	"ocasional": N_("Ocasional"),
}
FRECUENCIA_SERIE = "comun"

# Faceta → tabla de valores cerrados. Las claves son las que usan ``Catalogo.nombre_de`` y ``Catalogo.facetas``.
TAXONOMIAS: dict[str, dict[str, str]] = {
	"funcion": FUNCIONES,
	"lugar": LUGARES,
	"estancia": ESTANCIAS,
	"obstaculo": OBSTACULOS,
	"riesgo": RIESGOS,
	"frecuencia": FRECUENCIAS,
	"ambito": AMBITOS,
	"colocacion": COLOCACIONES,
}

# Alturas (en metros) que separan las clases de obstáculo cuando el complemento no la declara.
ALTURA_RODILLA = 0.5
ALTURA_PECHO = 1.2
ALTURA_VOLADIZO = 0.3
ALTURA_CABEZA = 1.4
ALTURA_LIBRE = 2.2

# Funciones que suelen ir juntas en la misma estancia: una mesa pide asientos, una cama su almacenaje.
FUNCIONES_AFINES: dict[str, tuple[str, ...]] = {
	"mesa": ("asiento", "iluminacion", "almacenaje"),
	"asiento": ("mesa", "mostrador", "iluminacion"),
	"mostrador": ("asiento", "pago", "expositor"),
	"descanso": ("almacenaje", "iluminacion", "asiento", "ayuda_tecnica"),
	"almacenaje": ("mesa", "descanso"),
	"expositor": ("mostrador", "pago", "carga"),
	"electrodomestico": ("almacenaje", "mesa", "sanitario"),
	"sanitario": ("ayuda_tecnica", "almacenaje", "residuos"),
	"equipo_medico": ("descanso", "asiento", "ayuda_tecnica"),
	"ayuda_tecnica": ("sanitario", "descanso", "equipo_medico"),
	"control_acceso": ("pago", "senalizacion", "barrera"),
	"pago": ("control_acceso", "mostrador", "senalizacion"),
	"senalizacion": ("referencia", "control_acceso"),
	"referencia": ("senalizacion", "barrera"),
	"barrera": ("senalizacion", "referencia"),
	"vehiculo": ("barrera", "referencia", "pago"),
	"juego": ("asiento", "fantasia", "animal"),
	"deporte": ("asiento", "almacenaje"),
	"instrumento": ("asiento", "juego"),
	"vegetacion": ("asiento", "agua"),
	"agua": ("vegetacion", "asiento"),
	"residuos": ("sanitario", "almacenaje"),
	"carga": ("almacenaje", "vehiculo", "herramienta"),
	"herramienta": ("mesa", "carga", "almacenaje"),
	"maquina": ("mesa", "asiento", "pago"),
	"fantasia": ("juego", "animal", "instrumento"),
	"animal": ("fantasia", "juego", "vegetacion"),
}


class ErrorComplemento(ErrorFormato):
	"""El complemento no se puede leer o instalar; el mensaje está pensado para la persona."""


def sin_acentos(texto: str) -> str:
	"""Minúsculas y sin tildes, para que «sillon» encuentre «Sillón».

	Se recuerdan los últimos resultados: el árbol del Estudio la pide para
	cada nodo (miles en un barrio importado) y casi siempre con los mismos
	nombres de tipo («acera», «puerta»…).
	"""
	return _sin_acentos(str(texto))


@functools.lru_cache(maxsize=32768)
def _sin_acentos(texto: str) -> str:
	descompuesto = unicodedata.normalize("NFD", texto.lower())
	return "".join(c for c in descompuesto if unicodedata.category(c) != "Mn")


def es_sonido_de_complemento(nombre: str) -> bool:
	"""True si el nombre se refiere a un fichero del complemento y no a un sonido de serie.

	Es un fichero del complemento si lleva extensión de sonido (``campana.flac``)
	o empieza por ``sonidos/``. Todo lo demás (``golpe/metal``,
	``fuente/frigorifico``, ``frigorifico``) es el nombre de un sonido de serie.
	También lo es el fichero de otro complemento del que se depende (``comun:sentarse.flac``).
	"""
	texto = partes_de_sonido(nombre)[1]
	return texto.startswith(CARPETA_SONIDOS + "/") or PurePosixPath(texto).suffix.lower() in EXTENSIONES_SONIDO


def partes_de_sonido(nombre: str) -> tuple[str, str]:
	"""Separa ``comun:sentarse.flac`` en (``comun``, ``sentarse.flac``); sin dependencia, (``""``, nombre).

	Un complemento puede usar los sonidos de otro del que declara depender
	(``depende_de``) en lugar de llevar su propia copia: así un sonido que
	usan veinte complementos ocupa una sola vez en el disco.
	"""
	texto = str(nombre).replace("\\", "/")
	dependencia, separador, resto = texto.partition(SEPARADOR_DEPENDENCIA)
	if separador and _PATRON_ID.match(dependencia) and resto and SEPARADOR_DEPENDENCIA not in resto:
		return dependencia, resto
	return "", texto


def clave_de_sonido(id_complemento: str, nombre: str) -> str:
	"""Nombre con el que el banco de sonidos encuentra un sonido citado por un objeto.

	Un fichero del complemento ``hogar`` citado como ``sonidos/lavadora.flac``
	se pide al banco como ``hogar/lavadora.flac``; un sonido de serie se pide tal cual.
	El de otro complemento (``comun:sentarse.flac``) se pide a ese: ``comun/sentarse.flac``.
	"""
	if not es_sonido_de_complemento(nombre):
		return str(nombre).replace("\\", "/")
	dependencia, texto = partes_de_sonido(nombre)
	if texto.startswith(CARPETA_SONIDOS + "/"):
		texto = texto[len(CARPETA_SONIDOS) + 1 :]
	return f"{dependencia or id_complemento}/{texto}"


# ── Definiciones ─────────────────────────────────────────────────────────────


@dataclass
class Variante:
	"""Un tamaño con nombre de un objeto: mesa de dos, de cuatro o de seis plazas."""

	id: str = ""
	nombre: str = ""
	ancho: float = 1.0
	fondo: float = 1.0
	alto: float = 1.0


def _terna(valor: Any) -> tuple[float, float, float]:
	"""Lee ``[mínimo, defecto, máximo]``; un número suelto es una medida fija."""
	if isinstance(valor, (int, float)) and not isinstance(valor, bool):
		return float(valor), float(valor), float(valor)
	minimo, defecto, maximo = valor
	return float(minimo), float(defecto), float(maximo)


def _textos(valor: Any) -> list[str]:
	return [str(v) for v in valor] if isinstance(valor, list) else []


@dataclass
class DefObjeto:
	"""Ficha de un objeto del catálogo: qué es, cuánto mide y cómo se comporta."""

	id: str = ""
	complemento: str = ""
	nombre: str = ""
	categoria: str = ""
	etiquetas: list[str] = field(default_factory=list)
	descripcion: str = ""
	ambito: list[str] = field(default_factory=lambda: ["interior"])
	forma: dict[str, Any] = field(default_factory=lambda: {"tipo": "rectangulo"})
	medidas: dict[str, tuple[float, float, float]] = field(default_factory=lambda: {d: MEDIDA_SERIE for d in DIMENSIONES})
	variantes: list[Variante] = field(default_factory=list)
	colocacion: list[str] = field(default_factory=lambda: ["suelo"])
	bloquea: bool = True
	altura_base: float = 0.0
	detectable_baston: bool = True
	material: str = "madera"
	sonidos: dict[str, Any] = field(default_factory=dict)
	estados: list[str] = field(default_factory=list)
	acciones: list[dict[str, Any]] = field(default_factory=list)
	contenedor: bool = False
	dinamica: dict[str, Any] = field(default_factory=dict)
	simbolo: dict[str, Any] = field(default_factory=dict)
	imagen: dict[str, Any] = field(default_factory=dict)
	# Suelo que se pisa encima de un objeto que no corta el paso (una alfombra, una tapa de metal); vacío si no cambia.
	suelo: str = ""
	# Frase que se le dice al alumno al pisarlo o al llegar a él (el borde de un andén); vacía si no avisa.
	aviso: str = ""
	# Estados en los que el objeto deja pasar aunque «bloquea» sea cierto (un torno o una puerta abiertos).
	paso_libre: list[str] = field(default_factory=list)
	# ── Clasificación (toda opcional: un complemento antiguo sin ella sigue valiendo) ──
	# Grupo dentro de su categoría («asientos» dentro de «salón»); su nombre visible está en el complemento.
	subcategoria: str = ""
	# Para qué sirve: una clave de ``FUNCIONES``.
	funcion: str = ""
	# Tipos de lugar (``LUGARES``) y estancias (``ESTANCIAS``) donde es habitual.
	lugares: list[str] = field(default_factory=list)
	estancias: list[str] = field(default_factory=list)
	# Clase de obstáculo (``OBSTACULOS``); vacía si no se declara: entonces se deduce de sus medidas.
	obstaculo: str = ""
	# Riesgos añadidos (``RIESGOS``): se mueve, es temporal, es un desnivel…
	riesgos: list[str] = field(default_factory=list)
	# Lo habitual que es (``FRECUENCIAS``), para ordenar los resultados.
	frecuencia: str = FRECUENCIA_SERIE
	# Objetos que suelen ir con él: ids del mismo complemento o tipos completos ``<complemento>/<objeto>``.
	relacionados: list[str] = field(default_factory=list)

	@property
	def tipo(self) -> str:
		"""Identificador completo ``<complemento>/<objeto>``, el que guarda cada ``Objeto``."""
		return f"{self.complemento}/{self.id}"

	@property
	def clase_obstaculo(self) -> str:
		"""Clase de obstáculo: la declarada o, si no hay, la que sale de su altura y de si corta el paso.

		Se deduce para que también los complementos sin clasificar se puedan
		filtrar por lo que más importa en movilidad: qué encuentra el bastón.
		"""
		return self.obstaculo or deducir_obstaculo(self.bloquea, self.altura_base, self.rango("alto")[1])

	@property
	def tiene_sonido_propio(self) -> bool:
		"""True si suena él solo (un frigorífico) o su dinámica lo hace sonar (un semáforo sonoro)."""
		if isinstance(self.sonidos.get("propio"), dict) and self.sonidos["propio"].get("sonido"):
			return True
		return any(isinstance(fase, dict) and fase.get("sonido") for fase in self.dinamica.get("fases") or [])

	@property
	def se_puede_usar(self) -> bool:
		"""True si el alumno puede hacer algo con él (abrir, encender, pulsar…)."""
		return bool(self.acciones)

	def rango(self, dimension: str) -> tuple[float, float, float]:
		"""(mínimo, defecto, máximo) de «ancho», «fondo» o «alto»."""
		return self.medidas.get(dimension, MEDIDA_SERIE)

	def variante(self, id_variante: str) -> Variante | None:
		"""Variante con ese id, o None."""
		for variante in self.variantes:
			if variante.id == id_variante:
				return variante
		return None

	def puntos_forma(self) -> list[Punto]:
		"""La forma en el cuadrado 0..1 (ver ``geometria.forma_a_mundo``)."""
		tipo = self.forma.get("tipo", "rectangulo")
		puntos = self.forma.get("puntos") or []
		if tipo == "circulo":
			return geo.circulo(0.5, 0.5, 0.5, LADOS_CIRCULO)
		if tipo == "ele":
			return list(puntos) if len(puntos) >= 3 else list(PUNTOS_ELE)
		if tipo == "poligono" and len(puntos) >= 3:
			return list(puntos)
		return [(0.0, 0.0), (1.0, 0.0), (1.0, 1.0), (0.0, 1.0)]

	def letra(self) -> str:
		"""Letra de su símbolo en el plano (la inicial del nombre si no declara otra)."""
		letra = str(self.simbolo.get("letra") or "")
		return letra[:2] if letra else (self.nombre[:1].upper() or "?")

	def color(self) -> str:
		"""Color ``#RRGGBB`` de su símbolo en el plano."""
		color = str(self.simbolo.get("color") or "")
		return color if _PATRON_COLOR.match(color) else "#808080"

	@classmethod
	def de_dict(cls, datos: dict[str, Any], complemento: str) -> DefObjeto:
		"""Construye la ficha desde el JSON; lanza ``ValueError`` si es inservible (sin id)."""
		if not isinstance(datos, dict):
			raise ValueError(_("la ficha del objeto no es un diccionario"))
		id_objeto = str(datos.get("id") or "")
		if not _PATRON_ID.match(id_objeto):
			raise ValueError(_("el identificador «{id}» no es válido").format(id=id_objeto))
		definicion = cls(id=id_objeto, complemento=complemento)
		definicion.nombre = str(datos.get("nombre") or id_objeto)
		definicion.categoria = str(datos.get("categoria") or "")
		definicion.etiquetas = _textos(datos.get("etiquetas"))
		definicion.descripcion = str(datos.get("descripcion") or "")
		ambito = [a for a in _textos(datos.get("ambito")) if a in AMBITOS]
		if ambito:
			definicion.ambito = ambito
		colocacion = [c for c in _textos(datos.get("colocacion")) if c in COLOCACIONES]
		if colocacion:
			definicion.colocacion = colocacion
		definicion.forma = _leer_forma(datos.get("forma"))
		medidas = datos.get("medidas") if isinstance(datos.get("medidas"), dict) else {}
		for dimension in DIMENSIONES:
			if dimension not in medidas:
				continue
			try:
				minimo, defecto, maximo = _terna(medidas[dimension])
			except (TypeError, ValueError) as error:
				raise ValueError(_("la medida «{dimension}» no es [mínimo, defecto, máximo]").format(dimension=dimension)) from error
			if not (0 < minimo <= defecto <= maximo):
				raise ValueError(_("la medida «{dimension}» no cumple 0 < mínimo ≤ defecto ≤ máximo").format(dimension=dimension))
			definicion.medidas[dimension] = (minimo, defecto, maximo)
		for bruta in datos.get("variantes") or []:
			if not isinstance(bruta, dict) or not bruta.get("id"):
				continue
			try:
				definicion.variantes.append(
					Variante(
						id=str(bruta["id"]),
						nombre=str(bruta.get("nombre") or bruta["id"]),
						ancho=float(bruta.get("ancho", definicion.rango("ancho")[1])),
						fondo=float(bruta.get("fondo", definicion.rango("fondo")[1])),
						alto=float(bruta.get("alto", definicion.rango("alto")[1])),
					)
				)
			except (TypeError, ValueError) as error:
				raise ValueError(_("la variante «{id}» tiene medidas no válidas").format(id=bruta.get("id"))) from error
		definicion.bloquea = bool(datos.get("bloquea", True))
		definicion.detectable_baston = bool(datos.get("detectable_baston", True))
		definicion.contenedor = bool(datos.get("contenedor", False))
		try:
			definicion.altura_base = float(datos.get("altura_base", 0.0))
		except (TypeError, ValueError) as error:
			raise ValueError(_("«altura_base» no es un número")) from error
		definicion.material = str(datos.get("material") or "madera")
		definicion.sonidos = dict(datos["sonidos"]) if isinstance(datos.get("sonidos"), dict) else {}
		definicion.estados = _textos(datos.get("estados"))
		definicion.acciones = [dict(a) for a in datos.get("acciones") or [] if isinstance(a, dict) and a.get("id")]
		definicion.dinamica = dict(datos["dinamica"]) if isinstance(datos.get("dinamica"), dict) else {}
		definicion.simbolo = dict(datos["simbolo"]) if isinstance(datos.get("simbolo"), dict) else {}
		definicion.imagen = dict(datos["imagen"]) if isinstance(datos.get("imagen"), dict) else {}
		definicion.suelo = str(datos.get("suelo") or "")
		definicion.aviso = str(datos.get("aviso") or "")
		definicion.paso_libre = _textos(datos.get("paso_libre"))
		# Clasificación: lo que no sea un valor conocido se ignora aquí (y lo avisa ``validar_complemento``).
		definicion.subcategoria = str(datos.get("subcategoria") or "")
		funcion = str(datos.get("funcion") or "")
		definicion.funcion = funcion if funcion in FUNCIONES else ""
		definicion.lugares = [valor for valor in _textos(datos.get("lugares")) if valor in LUGARES]
		definicion.estancias = [valor for valor in _textos(datos.get("estancias")) if valor in ESTANCIAS]
		obstaculo = str(datos.get("obstaculo") or "")
		definicion.obstaculo = obstaculo if obstaculo in OBSTACULOS else ""
		definicion.riesgos = [valor for valor in _textos(datos.get("riesgos")) if valor in RIESGOS]
		frecuencia = str(datos.get("frecuencia") or "")
		definicion.frecuencia = frecuencia if frecuencia in FRECUENCIAS else FRECUENCIA_SERIE
		definicion.relacionados = _textos(datos.get("relacionados"))
		return definicion


def deducir_obstaculo(bloquea: bool, altura_base: float, alto: float) -> str:
	"""Clase de obstáculo (clave de ``OBSTACULOS``) que corresponde a unas medidas.

	Lo que no corta el paso y está en el suelo se pisa. Lo que empieza por
	encima del suelo es un voladizo (el bastón pasa por debajo), queda a la
	altura de la cabeza o, a partir de 2,20 m, ya no se toca. Lo apoyado en
	el suelo se reparte por la altura a la que llega: rodilla, pecho o más.
	"""
	if altura_base >= ALTURA_LIBRE:
		return "aereo"
	if altura_base >= ALTURA_CABEZA:
		return "cabeza"
	if altura_base >= ALTURA_VOLADIZO:
		return "voladizo"
	if not bloquea:
		return "ras_suelo"
	techo = altura_base + alto
	if techo < ALTURA_RODILLA:
		return "bajo"
	if techo <= ALTURA_PECHO:
		return "medio"
	return "alto"


def _leer_forma(bruta: Any) -> dict[str, Any]:
	"""Normaliza la forma; lanza ``ValueError`` si no describe una huella válida."""
	if bruta is None:
		return {"tipo": "rectangulo"}
	if isinstance(bruta, str):
		bruta = {"tipo": bruta}
	if not isinstance(bruta, dict):
		raise ValueError(_("la forma no es válida"))
	tipo = str(bruta.get("tipo") or "rectangulo")
	if tipo not in FORMAS:
		raise ValueError(_("la forma «{tipo}» no existe; las admitidas son {formas}").format(tipo=tipo, formas=", ".join(FORMAS)))
	forma: dict[str, Any] = {"tipo": tipo}
	puntos_brutos = bruta.get("puntos")
	if puntos_brutos:
		try:
			puntos = [(float(p[0]), float(p[1])) for p in puntos_brutos]
		except (TypeError, ValueError, IndexError) as error:
			raise ValueError(_("los puntos de la forma no son pares de números")) from error
		if any(not (-1e-9 <= x <= 1 + 1e-9 and -1e-9 <= y <= 1 + 1e-9) for x, y in puntos):
			raise ValueError(_("los puntos de la forma deben estar entre 0 y 1"))
		if len(puntos) < 3 or not geo.es_simple(puntos) or geo.area(puntos) < 1e-6:
			raise ValueError(_("los puntos de la forma no dibujan un polígono válido"))
		forma["puntos"] = puntos
	elif tipo == "poligono":
		raise ValueError(_("una forma «poligono» necesita la lista «puntos»"))
	return forma


@dataclass
class Complemento:
	"""Un complemento cargado: su ficha general y sus objetos."""

	id: str = ""
	nombre: str = ""
	version: str = ""
	autor: str = ""
	licencia: str = ""
	descripcion: str = ""
	carpeta: Path | None = None
	objetos: list[DefObjeto] = field(default_factory=list)
	categorias: dict[str, str] = field(default_factory=dict)
	# Nombre visible de cada estado que usen sus objetos («abierto» → «Abierto»); se traduce.
	estados: dict[str, str] = field(default_factory=dict)
	activo: bool = True
	# Nombre visible de cada subcategoría que usen sus objetos («asientos» → «Asientos»); se traduce.
	subcategorias: dict[str, str] = field(default_factory=dict)
	# Complementos de los que usa sonidos (``comun:sentarse.flac``) y que deben estar instalados.
	depende_de: list[str] = field(default_factory=list)
	# Nombres visibles de los valores de la taxonomía, por faceta, ya en el idioma cargado:
	# ``{"funcion": {"asiento": "Seat"}}``. Así un complemento puede traer traducida la
	# clasificación a un idioma que el programa todavía no tiene.
	taxonomia: dict[str, dict[str, str]] = field(default_factory=dict)

	def objeto(self, id_objeto: str) -> DefObjeto | None:
		"""Ficha del objeto con ese id dentro del complemento.

		Con cientos de objetos por complemento y el motor preguntando por cada
		objeto colocado, se busca en un índice que se rehace si la lista cambia.
		"""
		indice = self.__dict__.get("_indice_por_id")
		if indice is None or indice[0] != len(self.objetos):
			por_id: dict[str, DefObjeto] = {}
			for definicion in self.objetos:
				por_id.setdefault(definicion.id, definicion)
			indice = (len(self.objetos), por_id)
			self.__dict__["_indice_por_id"] = indice
		encontrado = indice[1].get(id_objeto)
		if encontrado is not None and encontrado.id == id_objeto:
			return encontrado
		for definicion in self.objetos:
			if definicion.id == id_objeto:
				return definicion
		return None

	def nombre_subcategoria(self, subcategoria: str) -> str:
		"""Nombre visible de una subcategoría; si el complemento no lo declara, la propia clave puesta en limpio."""
		return self.subcategorias.get(subcategoria) or str(subcategoria).replace("_", " ").capitalize()

	def ruta_recurso(self, nombre: str, catalogo: Catalogo | None = None) -> Path | None:
		"""Ruta de un sonido o imagen del complemento, o None si no existe.

		Solo acepta nombres relativos que se queden dentro de la carpeta. Un
		sonido de otro complemento (``comun:sentarse.flac``) se busca, solo si
		está declarado en ``depende_de``, en ese complemento tal como lo tiene
		cargado el catálogo (``catalogo`` o, si no se da, el catálogo que cargó
		este complemento), esté en la carpeta de serie o en la del usuario; si
		no hay catálogo o no lo tiene, en la carpeta hermana. Así quien pregunte
		por cualquier sonido citado por un objeto obtiene su fichero, venga de
		donde venga.
		"""
		if self.carpeta is None or not nombre:
			return None
		dependencia, fichero = partes_de_sonido(str(nombre))
		if dependencia:
			if dependencia not in self.depende_de:
				return None
			if catalogo is None:
				referencia = self.__dict__.get("_catalogo")
				catalogo = referencia() if referencia is not None else None
			cargado = catalogo.complemento(dependencia) if catalogo is not None else None
			if cargado is not None and cargado.carpeta is not None:
				encontrada = Complemento(id=dependencia, carpeta=cargado.carpeta).ruta_recurso(fichero)
				if encontrada is not None:
					return encontrada
			return Complemento(id=dependencia, carpeta=self.carpeta.parent / dependencia).ruta_recurso(fichero)
		relativa = PurePosixPath(str(nombre).replace("\\", "/"))
		if relativa.is_absolute() or ".." in relativa.parts or ":" in str(nombre):
			return None
		for candidata in (self.carpeta / relativa, self.carpeta / "sonidos" / relativa, self.carpeta / "imagenes" / relativa):
			if candidata.is_file():
				return candidata
		return None

	def nombre_estado(self, estado: str) -> str:
		"""Nombre visible de un estado; si el complemento no lo declara, la propia clave sin guiones bajos."""
		return self.estados.get(estado) or str(estado).replace("_", " ")


# ── Lectura de un complemento ────────────────────────────────────────────────


def _aviso(gravedad: str, codigo: str, mensaje: str, elemento: str = "", sugerencia: str = "") -> Aviso:
	return Aviso(gravedad=gravedad, codigo=codigo, mensaje=mensaje, elemento_id=elemento, sugerencia=sugerencia)


def _leer_ficha(carpeta: Path) -> dict[str, Any]:
	"""Lee ``complemento.json``; lanza ``ErrorComplemento`` si falta o no es JSON."""
	ruta = carpeta / NOMBRE_FICHA
	if not ruta.is_file():
		raise ErrorComplemento(_("En «{carpeta}» falta el fichero «{nombre}».").format(carpeta=carpeta.name, nombre=NOMBRE_FICHA))
	try:
		if ruta.stat().st_size > MAX_BYTES_JSON:
			raise ErrorComplemento(_("«{nombre}» es demasiado grande.").format(nombre=NOMBRE_FICHA))
		datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
	except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
		raise ErrorComplemento(_("No se puede leer «{ruta}»: {detalle}").format(ruta=ruta, detalle=error)) from error
	if not isinstance(datos, dict):
		raise ErrorComplemento(_("«{nombre}» no tiene la estructura esperada.").format(nombre=NOMBRE_FICHA))
	return datos


def _leer_traduccion(carpeta: Path, idioma: str) -> dict[str, Any]:
	"""Traducción del complemento para ``idioma`` (``locales/<idioma>.json``); vacía si no hay."""
	if not idioma or idioma == i18n.IDIOMA_ORIGEN:
		return {}
	for codigo in dict.fromkeys((idioma, idioma.split("_")[0].split("-")[0])):
		ruta = carpeta / "locales" / f"{codigo}.json"
		if not ruta.is_file():
			continue
		try:
			datos = json.loads(ruta.read_text(encoding="utf-8-sig"))
		except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
			log.warning("No se puede leer la traducción %s: %s", ruta, error)
			return {}
		return datos if isinstance(datos, dict) else {}
	return {}


def _leer_taxonomia(bruta: Any) -> dict[str, dict[str, str]]:
	"""Nombres visibles de la taxonomía que trae un complemento: solo facetas y valores que existen."""
	if not isinstance(bruta, dict):
		return {}
	leida: dict[str, dict[str, str]] = {}
	for faceta, nombres in bruta.items():
		if faceta not in TAXONOMIAS or not isinstance(nombres, dict):
			continue
		validos = {
			str(clave): str(nombre)
			for clave, nombre in nombres.items()
			if clave in TAXONOMIAS[faceta] and isinstance(nombre, str) and nombre
		}
		if validos:
			leida[str(faceta)] = validos
	return leida


def _traducir_objeto(definicion: DefObjeto, textos: dict[str, Any]) -> None:
	"""Aplica a una ficha los textos traducidos (nombre, descripción, etiquetas, variantes, acciones)."""
	if isinstance(textos.get("nombre"), str):
		definicion.nombre = textos["nombre"]
	if isinstance(textos.get("descripcion"), str):
		definicion.descripcion = textos["descripcion"]
	# Las etiquetas traducidas se suman: se puede buscar en los dos idiomas.
	for etiqueta in _textos(textos.get("etiquetas")):
		if etiqueta not in definicion.etiquetas:
			definicion.etiquetas.append(etiqueta)
	nombres_variantes = textos.get("variantes") if isinstance(textos.get("variantes"), dict) else {}
	for variante in definicion.variantes:
		if isinstance(nombres_variantes.get(variante.id), str):
			variante.nombre = nombres_variantes[variante.id]
	nombres_acciones = textos.get("acciones") if isinstance(textos.get("acciones"), dict) else {}
	for accion in definicion.acciones:
		if isinstance(nombres_acciones.get(accion.get("id")), str):
			accion["nombre"] = nombres_acciones[accion["id"]]
	if isinstance(textos.get("aviso"), str):
		definicion.aviso = textos["aviso"]
	if isinstance(textos.get("imagen"), str) and definicion.imagen:
		definicion.imagen["descripcion"] = textos["imagen"]


def leer_complemento(carpeta: Path, idioma: str | None = None) -> tuple[Complemento, list[Aviso]]:
	"""Carga un complemento de su carpeta, con los objetos que se puedan leer.

	Un objeto mal definido se salta (con su aviso) sin tirar el resto del
	complemento. Lanza ``ErrorComplemento`` si la ficha general no vale.
	"""
	datos = _leer_ficha(carpeta)
	avisos: list[Aviso] = []
	id_complemento = str(datos.get("id") or "")
	if not _PATRON_ID.match(id_complemento):
		raise ErrorComplemento(
			_("El identificador del complemento «{id}» no es válido: use minúsculas sin tildes, cifras, guiones y guiones bajos.").format(
				id=id_complemento
			)
		)
	try:
		formato = int(datos.get("formato", FORMATO_COMPLEMENTO))
	except (TypeError, ValueError) as error:
		raise ErrorComplemento(_("El número de formato del complemento «{id}» no es válido.").format(id=id_complemento)) from error
	if formato > FORMATO_COMPLEMENTO:
		raise ErrorComplemento(
			_("El complemento «{id}» es de un formato más nuevo ({formato}). Actualice el programa para usarlo.").format(
				id=id_complemento, formato=formato
			)
		)
	complemento = Complemento(
		id=id_complemento,
		nombre=str(datos.get("nombre") or id_complemento),
		version=str(datos.get("version") or ""),
		autor=str(datos.get("autor") or ""),
		licencia=str(datos.get("licencia") or ""),
		descripcion=str(datos.get("descripcion") or ""),
		carpeta=carpeta,
	)
	if isinstance(datos.get("categorias"), dict):
		complemento.categorias = {str(k): str(v) for k, v in datos["categorias"].items()}
	if isinstance(datos.get("estados"), dict):
		complemento.estados = {str(k): str(v) for k, v in datos["estados"].items()}
	if isinstance(datos.get("subcategorias"), dict):
		complemento.subcategorias = {str(k): str(v) for k, v in datos["subcategorias"].items()}
	complemento.depende_de = [d for d in _textos(datos.get("depende_de")) if _PATRON_ID.match(d) and d != id_complemento]
	complemento.taxonomia = _leer_taxonomia(datos.get("taxonomia"))
	objetos = datos.get("objetos")
	if not isinstance(objetos, list):
		objetos = []
		avisos.append(
			_aviso(
				"error",
				"complemento_sin_objetos",
				_("El complemento «{id}» no tiene lista de objetos.").format(id=id_complemento),
				id_complemento,
			)
		)
	vistos: set[str] = set()
	for numero, bruto in enumerate(objetos, start=1):
		try:
			definicion = DefObjeto.de_dict(bruto, id_complemento)
		except ValueError as error:
			nombre = bruto.get("id") if isinstance(bruto, dict) else None
			avisos.append(
				_aviso(
					"error",
					"objeto_no_valido",
					_("El objeto {referencia} del complemento «{id}» no se puede usar: {detalle}.").format(
						referencia=f"«{nombre}»" if nombre else _("número {n}").format(n=numero), id=id_complemento, detalle=error
					),
					f"{id_complemento}/{nombre}" if nombre else id_complemento,
					_("Corrija su ficha en «{fichero}».").format(fichero=NOMBRE_FICHA),
				)
			)
			continue
		if definicion.id in vistos:
			avisos.append(
				_aviso(
					"error",
					"objeto_repetido",
					_("El complemento «{id}» define dos veces el objeto «{objeto}»; se usa el primero.").format(
						id=id_complemento, objeto=definicion.id
					),
					definicion.tipo,
					_("Cambie el identificador de uno de los dos."),
				)
			)
			continue
		vistos.add(definicion.id)
		complemento.objetos.append(definicion)
	traduccion = _leer_traduccion(carpeta, idioma if idioma is not None else i18n.idioma_actual())
	if traduccion:
		if isinstance(traduccion.get("nombre"), str):
			complemento.nombre = traduccion["nombre"]
		if isinstance(traduccion.get("descripcion"), str):
			complemento.descripcion = traduccion["descripcion"]
		if isinstance(traduccion.get("categorias"), dict):
			complemento.categorias.update({str(k): str(v) for k, v in traduccion["categorias"].items()})
		if isinstance(traduccion.get("estados"), dict):
			complemento.estados.update({str(k): str(v) for k, v in traduccion["estados"].items()})
		if isinstance(traduccion.get("subcategorias"), dict):
			complemento.subcategorias.update({str(k): str(v) for k, v in traduccion["subcategorias"].items()})
		for faceta, nombres in _leer_taxonomia(traduccion.get("taxonomia")).items():
			complemento.taxonomia.setdefault(faceta, {}).update(nombres)
		por_objeto = traduccion.get("objetos") if isinstance(traduccion.get("objetos"), dict) else {}
		for definicion in complemento.objetos:
			if isinstance(por_objeto.get(definicion.id), dict):
				_traducir_objeto(definicion, por_objeto[definicion.id])
	return complemento, avisos


# ── Catálogo ─────────────────────────────────────────────────────────────────

# Un filtro admite un valor o varios: con varios basta con que el objeto cumpla uno.
Filtro = str | Iterable[str] | None

# Facetas por las que se puede filtrar y contar, en el orden en que conviene enseñarlas.
FACETAS = (
	"complemento",
	"categoria",
	"subcategoria",
	"funcion",
	"lugar",
	"estancia",
	"obstaculo",
	"riesgo",
	"ambito",
	"colocacion",
	"frecuencia",
	"contenedor",
	"con_sonido",
	"usable",
)
# Las tres últimas son de sí o no; sus valores en ``facetas()`` son estas claves.
FACETAS_SI_NO = ("contenedor", "con_sonido", "usable")
SI, NO = "si", "no"
ORDENES = ("relevancia", "nombre", "frecuencia")
_PUESTO_FRECUENCIA = {clave: puesto for puesto, clave in enumerate(FRECUENCIAS)}


@dataclass
class NodoArbol:
	"""Un nodo de la jerarquía complemento → categoría → subcategoría, con su recuento.

	Pensado para llenar un control de árbol: ``nombre`` es lo que se enseña,
	``total`` cuántos objetos cuelgan de él y ``tipos`` (solo en las hojas y
	si se pide) los objetos, ya ordenados.
	"""

	nivel: str = ""  # complemento | categoria | subcategoria
	clave: str = ""
	nombre: str = ""
	total: int = 0
	hijos: list[NodoArbol] = field(default_factory=list)
	tipos: list[str] = field(default_factory=list)


@dataclass(frozen=True)
class ValorFaceta:
	"""Un valor de una faceta con los objetos que lo cumplen: «Asiento (212)»."""

	clave: str
	nombre: str
	total: int


@dataclass
class _Indizado:
	"""Lo que se precalcula de cada objeto para que buscar entre miles sea inmediato."""

	definicion: DefObjeto
	nombre: str  # sin acentos
	palabras_nombre: frozenset[str]
	etiquetas: tuple[str, ...]  # sin acentos; hacen de sinónimos
	palabras_etiquetas: frozenset[str]
	id_legible: str
	clasificacion: str  # nombres visibles de categoría, subcategoría, función, lugares y estancias
	pajar: str  # todo el texto, para la búsqueda de siempre
	valores: dict[str, frozenset[str]]  # faceta → valores del objeto
	puesto_frecuencia: int


def _conjunto(filtro: Filtro) -> frozenset[str] | None:
	"""Un filtro como conjunto de valores; None si no filtra."""
	if filtro is None or filtro == "":
		return None
	if isinstance(filtro, str):
		return frozenset((filtro,))
	valores = frozenset(str(valor) for valor in filtro if valor)
	return valores or None


def _si_no(valor: bool | None) -> frozenset[str] | None:
	return None if valor is None else frozenset((SI if valor else NO,))


class Catalogo:
	"""Todos los complementos cargados y las operaciones sobre sus objetos."""

	def __init__(self) -> None:
		self._complementos: dict[str, Complemento] = {}
		# Problemas encontrados al cargar: se enseñan al profesional, no se callan.
		self.avisos: list[Aviso] = []
		# Índice de búsqueda en memoria: (huella de lo cargado, objetos indizados). Se rehace solo si algo cambia.
		self._indice: tuple[tuple[Any, ...], list[_Indizado]] | None = None

	@classmethod
	def cargar(
		cls,
		carpetas: Iterable[str | Path] | str | Path | None = None,
		idioma: str | None = None,
		desactivados: Iterable[str] = (),
	) -> Catalogo:
		"""Carga los complementos de una o varias carpetas de complementos.

		Cada carpeta contiene una subcarpeta por complemento. Sin argumentos se
		usa ``data/plugins``. Un complemento que no se puede leer no impide
		cargar los demás: queda anotado en ``avisos``.
		"""
		catalogo = cls()
		if carpetas is None:
			lista = [paths.subcarpeta(CARPETA_PLUGINS)]
		elif isinstance(carpetas, (str, Path)):
			lista = [Path(carpetas)]
		else:
			lista = [Path(carpeta) for carpeta in carpetas]
		apagados = set(desactivados)
		for raiz in lista:
			if not raiz.is_dir():
				log.info("No existe la carpeta de complementos %s", raiz)
				continue
			for carpeta in sorted(p for p in raiz.iterdir() if p.is_dir() and not p.name.startswith(".")):
				try:
					complemento, avisos = leer_complemento(carpeta, idioma)
				except ErrorComplemento as error:
					log.warning("Complemento no cargado (%s): %s", carpeta, error)
					catalogo.avisos.append(
						_aviso(
							"error", "complemento_no_valido", str(error), carpeta.name, _("Revise el complemento o vuelva a instalarlo.")
						)
					)
					continue
				catalogo.avisos.extend(avisos)
				if complemento.id in catalogo._complementos:
					catalogo.avisos.append(
						_aviso(
							"aviso",
							"complemento_repetido",
							_("El complemento «{id}» está en dos carpetas; se usa el primero.").format(id=complemento.id),
							complemento.id,
							_("Borre la copia que sobra."),
						)
					)
					continue
				complemento.activo = complemento.id not in apagados
				catalogo.anadir(complemento)
				log.info("Complemento «%s» cargado con %s objetos", complemento.id, len(complemento.objetos))
		for complemento in list(catalogo._complementos.values()):
			for dependencia in complemento.depende_de:
				if dependencia not in catalogo._complementos:
					catalogo.avisos.append(
						_aviso(
							"aviso",
							"dependencia_ausente",
							_(
								"El complemento «{id}» usa sonidos de «{dependencia}», que no está instalado: esos sonidos no se oirán."
							).format(id=complemento.id, dependencia=dependencia),
							complemento.id,
							_("Instale el complemento «{dependencia}».").format(dependencia=dependencia),
						)
					)
		return catalogo

	# ── Complementos ──

	def anadir(self, complemento: Complemento) -> None:
		"""Añade (o sustituye) un complemento ya construido.

		El complemento recuerda (sin retenerlo) el catálogo que lo tiene, para
		resolver los sonidos de sus dependencias en cualquiera de las carpetas cargadas.
		"""
		self._complementos[complemento.id] = complemento
		complemento.__dict__["_catalogo"] = weakref.ref(self)

	def quitar(self, id_complemento: str) -> bool:
		"""Quita un complemento del catálogo en memoria (no borra su carpeta)."""
		return self._complementos.pop(id_complemento, None) is not None

	def activar(self, id_complemento: str, activo: bool = True) -> bool:
		"""Activa o desactiva un complemento sin reiniciar.

		Desactivado, sus objetos dejan de salir en las búsquedas, pero los ya
		colocados en un entorno conservan su forma y su comportamiento.
		"""
		complemento = self._complementos.get(id_complemento)
		if complemento is None:
			return False
		complemento.activo = activo
		return True

	def complementos(self) -> list[Complemento]:
		"""Complementos cargados, por orden de nombre."""
		return sorted(self._complementos.values(), key=lambda c: sin_acentos(c.nombre))

	def complemento(self, id_complemento: str) -> Complemento | None:
		"""Complemento con ese id, o None."""
		return self._complementos.get(id_complemento)

	@property
	def vacio(self) -> bool:
		"""True si no hay ningún objeto disponible para colocar."""
		return not any(c.activo and c.objetos for c in self._complementos.values())

	# ── Objetos ──

	def objeto(self, tipo: str) -> DefObjeto | None:
		"""Ficha de ``<complemento>/<objeto>``; None si no está instalado."""
		id_complemento, separador, id_objeto = str(tipo).partition("/")
		if not separador:
			return None
		complemento = self._complementos.get(id_complemento)
		return complemento.objeto(id_objeto) if complemento else None

	def definicion_de(self, objeto: Objeto) -> DefObjeto | None:
		"""Ficha del catálogo de un objeto colocado; None si es una caja."""
		return self.objeto(objeto.tipo)

	def objetos(self) -> list[DefObjeto]:
		"""Todos los objetos de los complementos activos."""
		return [d for c in self.complementos() if c.activo for d in c.objetos]

	def categorias(self) -> list[str]:
		"""Categorías con algún objeto disponible, ordenadas."""
		return sorted({d.categoria for d in self.objetos() if d.categoria})

	def nombre_categoria(self, categoria: str) -> str:
		"""Nombre visible de una categoría si algún complemento lo declara; si no, la clave."""
		for complemento in self._complementos.values():
			if categoria in complemento.categorias:
				return complemento.categorias[categoria]
		return categoria

	def nombre_estado(self, tipo: str, estado: str) -> str:
		"""Nombre visible del estado de un objeto ``<complemento>/<objeto>``, en el idioma cargado."""
		complemento = self._complementos.get(str(tipo).partition("/")[0])
		return complemento.nombre_estado(estado) if complemento else str(estado).replace("_", " ")

	def buscar(
		self, texto: str = "", categoria: str | None = None, ambito: str | None = None, colocacion: str | None = None
	) -> list[DefObjeto]:
		"""Objetos que cumplen todos los filtros, ordenados por nombre.

		``texto`` se busca sin distinguir mayúsculas ni tildes en el id, el
		nombre, la categoría, las etiquetas y la descripción; con varias
		palabras tienen que aparecer todas.
		"""
		# Usa el índice ya normalizado (``_indizados``): normalizar dos mil fichas en cada pulsación costaba decenas de milisegundos.
		palabras = sin_acentos(texto).split()
		encontrados: list[_Indizado] = []
		for indizado in self._indizados():
			definicion = indizado.definicion
			if categoria and definicion.categoria != categoria:
				continue
			if ambito and ambito not in definicion.ambito:
				continue
			if colocacion and colocacion not in definicion.colocacion:
				continue
			if palabras and not all(palabra in indizado.pajar for palabra in palabras):
				continue
			encontrados.append(indizado)
		encontrados.sort(key=lambda indizado: indizado.nombre)
		return [indizado.definicion for indizado in encontrados]

	# ── Clasificación: nombres visibles ──

	def nombre_de(self, faceta: str, clave: str) -> str:
		"""Nombre visible de un valor de una faceta, en el idioma cargado.

		``faceta`` es una de ``FACETAS``. Para la taxonomía cerrada se usa
		primero el nombre que traiga algún complemento ya traducido y, si no,
		la traducción del programa. Un valor desconocido se devuelve tal cual.
		"""
		if faceta == "complemento":
			complemento = self._complementos.get(clave)
			return complemento.nombre if complemento else clave
		if faceta == "categoria":
			return self.nombre_categoria(clave)
		if faceta == "subcategoria":
			return self.nombre_subcategoria(clave)
		if faceta in FACETAS_SI_NO:
			return _("Sí") if clave == SI else _("No")
		tabla = TAXONOMIAS.get(faceta)
		if tabla is None or clave not in tabla:
			return clave
		for complemento in self._complementos.values():
			nombre = complemento.taxonomia.get(faceta, {}).get(clave)
			if nombre:
				return nombre
		return _(tabla[clave])

	def nombre_subcategoria(self, subcategoria: str, complemento: str | None = None) -> str:
		"""Nombre visible de una subcategoría; con ``complemento`` se mira primero en ese."""
		propio = self._complementos.get(complemento) if complemento else None
		if propio is not None and subcategoria in propio.subcategorias:
			return propio.subcategorias[subcategoria]
		for otro in self._complementos.values():
			if subcategoria in otro.subcategorias:
				return otro.subcategorias[subcategoria]
		return str(subcategoria).replace("_", " ").capitalize()

	def subcategorias(self, categoria: str | None = None, complemento: str | None = None) -> list[str]:
		"""Subcategorías con algún objeto disponible (de una categoría o de un complemento, si se dan), ordenadas."""
		return sorted(
			{
				d.subcategoria
				for d in self.objetos()
				if d.subcategoria
				and (categoria is None or d.categoria == categoria)
				and (complemento is None or d.complemento == complemento)
			}
		)

	# ── Clasificación: índice ──

	def _indizados(self) -> list[_Indizado]:
		"""Objetos de los complementos activos con sus textos ya normalizados.

		Normalizar el texto de miles de objetos en cada pulsación haría lenta
		la búsqueda mientras se escribe; se hace una vez y se guarda. La huella
		detecta cualquier cambio (activar, instalar, quitar, añadir objetos) sin
		que nadie tenga que acordarse de invalidar nada.
		"""
		huella = tuple((id(c), c.activo, len(c.objetos), c.nombre) for c in self._complementos.values())
		if self._indice is not None and self._indice[0] == huella:
			return self._indice[1]
		indizados: list[_Indizado] = []
		for complemento in self.complementos():
			if not complemento.activo:
				continue
			for definicion in complemento.objetos:
				indizados.append(self._indizar(complemento, definicion))
		self._indice = (huella, indizados)
		return indizados

	def _indizar(self, complemento: Complemento, definicion: DefObjeto) -> _Indizado:
		nombre = sin_acentos(definicion.nombre)
		etiquetas = tuple(sin_acentos(etiqueta) for etiqueta in definicion.etiquetas)
		id_legible = sin_acentos(definicion.id.replace("_", " ").replace("-", " "))
		visibles = [
			complemento.nombre,
			complemento.categorias.get(definicion.categoria, definicion.categoria),
			complemento.nombre_subcategoria(definicion.subcategoria) if definicion.subcategoria else "",
			self.nombre_de("funcion", definicion.funcion) if definicion.funcion else "",
			*(self.nombre_de("lugar", lugar) for lugar in definicion.lugares),
			*(self.nombre_de("estancia", estancia) for estancia in definicion.estancias),
		]
		clasificacion = sin_acentos(" ".join(texto for texto in visibles if texto))
		pajar = sin_acentos(
			" ".join([definicion.id, definicion.nombre, definicion.categoria, definicion.descripcion, *definicion.etiquetas])
		)
		valores = {
			"complemento": frozenset((definicion.complemento,)),
			"categoria": frozenset((definicion.categoria,)) if definicion.categoria else frozenset(),
			"subcategoria": frozenset((definicion.subcategoria,)) if definicion.subcategoria else frozenset(),
			"funcion": frozenset((definicion.funcion,)) if definicion.funcion else frozenset(),
			"lugar": frozenset(definicion.lugares),
			"estancia": frozenset(definicion.estancias),
			"obstaculo": frozenset((definicion.clase_obstaculo,)),
			"riesgo": frozenset(definicion.riesgos),
			"ambito": frozenset(definicion.ambito),
			"colocacion": frozenset(definicion.colocacion),
			"frecuencia": frozenset((definicion.frecuencia,)),
			"contenedor": frozenset((SI if definicion.contenedor else NO,)),
			"con_sonido": frozenset((SI if definicion.tiene_sonido_propio else NO,)),
			"usable": frozenset((SI if definicion.se_puede_usar else NO,)),
		}
		return _Indizado(
			definicion=definicion,
			nombre=nombre,
			palabras_nombre=frozenset(nombre.split()),
			etiquetas=etiquetas,
			palabras_etiquetas=frozenset(palabra for etiqueta in etiquetas for palabra in etiqueta.split()),
			id_legible=id_legible,
			clasificacion=clasificacion,
			pajar=pajar,
			valores=valores,
			puesto_frecuencia=_PUESTO_FRECUENCIA.get(definicion.frecuencia, 1),
		)

	@staticmethod
	def _relevancia(indizado: _Indizado, palabras: list[str], frase: str) -> int:
		"""Puntos de un objeto para un texto buscado; 0 si alguna palabra no aparece.

		Pesa más acertar el nombre que una etiqueta (un sinónimo), y esta más
		que la descripción: quien escribe «mesa» quiere primero las mesas y
		después lo que se pone en una mesa.
		"""
		total = 0
		if frase == indizado.nombre:
			total += 120
		elif frase in indizado.etiquetas:
			total += 70
		elif indizado.nombre.startswith(frase):
			total += 40
		for palabra in palabras:
			if palabra in indizado.palabras_nombre:
				puntos = 50
			elif palabra in indizado.palabras_etiquetas:
				puntos = 30
			elif palabra in indizado.nombre:
				puntos = 24
			elif any(palabra in etiqueta for etiqueta in indizado.etiquetas):
				puntos = 15
			elif palabra in indizado.id_legible:
				puntos = 12
			elif palabra in indizado.clasificacion:
				puntos = 8
			elif palabra in indizado.pajar:
				puntos = 3
			else:
				return 0
			total += puntos
		return total

	@staticmethod
	def _filtros(
		complemento: Filtro,
		categoria: Filtro,
		subcategoria: Filtro,
		funcion: Filtro,
		lugar: Filtro,
		estancia: Filtro,
		obstaculo: Filtro,
		riesgo: Filtro,
		ambito: Filtro,
		colocacion: Filtro,
		frecuencia: Filtro,
		contenedor: bool | None,
		con_sonido: bool | None,
		usable: bool | None,
	) -> dict[str, frozenset[str]]:
		"""Los filtros activos, por faceta."""
		brutos = {
			"complemento": _conjunto(complemento),
			"categoria": _conjunto(categoria),
			"subcategoria": _conjunto(subcategoria),
			"funcion": _conjunto(funcion),
			"lugar": _conjunto(lugar),
			"estancia": _conjunto(estancia),
			"obstaculo": _conjunto(obstaculo),
			"riesgo": _conjunto(riesgo),
			"ambito": _conjunto(ambito),
			"colocacion": _conjunto(colocacion),
			"frecuencia": _conjunto(frecuencia),
			"contenedor": _si_no(contenedor),
			"con_sonido": _si_no(con_sonido),
			"usable": _si_no(usable),
		}
		return {faceta: valores for faceta, valores in brutos.items() if valores is not None}

	# ── Clasificación: búsqueda, árbol, facetas y relacionados ──

	def buscar_avanzado(
		self,
		texto: str = "",
		*,
		complemento: Filtro = None,
		categoria: Filtro = None,
		subcategoria: Filtro = None,
		funcion: Filtro = None,
		lugar: Filtro = None,
		estancia: Filtro = None,
		obstaculo: Filtro = None,
		riesgo: Filtro = None,
		ambito: Filtro = None,
		colocacion: Filtro = None,
		frecuencia: Filtro = None,
		contenedor: bool | None = None,
		con_sonido: bool | None = None,
		usable: bool | None = None,
		orden: str = "relevancia",
		limite: int | None = None,
	) -> list[DefObjeto]:
		"""Objetos que cumplen el texto y todos los filtros, los más útiles primero.

		``texto`` se busca sin mayúsculas ni tildes en el nombre, las etiquetas
		(que hacen de sinónimos), el identificador, la clasificación y la
		descripción; con varias palabras tienen que aparecer todas. Cada filtro
		admite un valor o varios (basta con cumplir uno) y los filtros se
		combinan entre sí: ``funcion="asiento", lugar=("hospital", "centro_salud")``.
		``contenedor``, ``con_sonido`` y ``usable`` son de sí o no.

		``orden``: «relevancia» (lo que mejor casa con el texto y, a igualdad,
		lo más común; sin texto, lo más común), «frecuencia» o «nombre».
		"""
		if orden not in ORDENES:
			raise ValueError(_("No se sabe ordenar por «{orden}». Órdenes: {ordenes}.").format(orden=orden, ordenes=", ".join(ORDENES)))
		filtros = self._filtros(
			complemento,
			categoria,
			subcategoria,
			funcion,
			lugar,
			estancia,
			obstaculo,
			riesgo,
			ambito,
			colocacion,
			frecuencia,
			contenedor,
			con_sonido,
			usable,
		)
		frase = " ".join(sin_acentos(texto).split())
		palabras = frase.split()
		puntuados: list[tuple[int, _Indizado]] = []
		for indizado in self._indizados():
			if any(indizado.valores[faceta].isdisjoint(valores) for faceta, valores in filtros.items()):
				continue
			puntos = self._relevancia(indizado, palabras, frase) if palabras else 1
			if puntos:
				puntuados.append((puntos, indizado))
		if orden == "nombre":
			puntuados.sort(key=lambda par: par[1].nombre)
		elif orden == "frecuencia":
			puntuados.sort(key=lambda par: (par[1].puesto_frecuencia, par[1].nombre))
		else:
			puntuados.sort(key=lambda par: (-par[0], par[1].puesto_frecuencia, par[1].nombre))
		encontrados = [indizado.definicion for _puntos, indizado in puntuados]
		return encontrados[:limite] if limite is not None else encontrados

	def facetas(
		self,
		texto: str = "",
		*,
		complemento: Filtro = None,
		categoria: Filtro = None,
		subcategoria: Filtro = None,
		funcion: Filtro = None,
		lugar: Filtro = None,
		estancia: Filtro = None,
		obstaculo: Filtro = None,
		riesgo: Filtro = None,
		ambito: Filtro = None,
		colocacion: Filtro = None,
		frecuencia: Filtro = None,
		contenedor: bool | None = None,
		con_sonido: bool | None = None,
		usable: bool | None = None,
	) -> dict[str, list[ValorFaceta]]:
		"""Valores disponibles en cada faceta y cuántos objetos hay en cada uno.

		Admite el mismo texto y los mismos filtros que ``buscar_avanzado``. El
		recuento de una faceta se hace con todos los demás filtros puestos pero
		sin el suyo: así, con «función: asiento» elegida, la lista de funciones
		sigue enseñando cuántas mesas habría, que es lo que hace falta para
		cambiar de opción sin borrar antes el filtro.

		Devuelve ``{faceta: [ValorFaceta(clave, nombre, total), …]}`` con los
		valores ordenados de más a menos objetos y, a igualdad, por nombre.
		"""
		filtros = self._filtros(
			complemento,
			categoria,
			subcategoria,
			funcion,
			lugar,
			estancia,
			obstaculo,
			riesgo,
			ambito,
			colocacion,
			frecuencia,
			contenedor,
			con_sonido,
			usable,
		)
		frase = " ".join(sin_acentos(texto).split())
		palabras = frase.split()
		recuentos: dict[str, dict[str, int]] = {faceta: {} for faceta in FACETAS}
		subcategoria_de: dict[str, str] = {}
		for indizado in self._indizados():
			if palabras and not self._relevancia(indizado, palabras, frase):
				continue
			fallan = [faceta for faceta, valores in filtros.items() if indizado.valores[faceta].isdisjoint(valores)]
			if len(fallan) > 1:
				continue
			for faceta in fallan if fallan else FACETAS:
				cuenta = recuentos[faceta]
				for valor in indizado.valores[faceta]:
					cuenta[valor] = cuenta.get(valor, 0) + 1
			if indizado.definicion.subcategoria:
				subcategoria_de.setdefault(indizado.definicion.subcategoria, indizado.definicion.complemento)
		resultado: dict[str, list[ValorFaceta]] = {}
		for faceta in FACETAS:
			valores = [
				ValorFaceta(
					clave,
					self.nombre_subcategoria(clave, subcategoria_de.get(clave))
					if faceta == "subcategoria"
					else self.nombre_de(faceta, clave),
					total,
				)
				for clave, total in recuentos[faceta].items()
			]
			valores.sort(key=lambda valor: (-valor.total, sin_acentos(valor.nombre)))
			resultado[faceta] = valores
		return resultado

	def arbol(
		self,
		texto: str = "",
		*,
		con_objetos: bool = False,
		funcion: Filtro = None,
		lugar: Filtro = None,
		estancia: Filtro = None,
		obstaculo: Filtro = None,
		riesgo: Filtro = None,
		ambito: Filtro = None,
		colocacion: Filtro = None,
		frecuencia: Filtro = None,
		contenedor: bool | None = None,
		con_sonido: bool | None = None,
		usable: bool | None = None,
	) -> list[NodoArbol]:
		"""Jerarquía complemento → categoría → subcategoría con recuentos, para un control de árbol.

		Los complementos van por orden de nombre; las categorías y
		subcategorías, en el orden en que las declara cada complemento. Solo
		salen los nodos con algún objeto que cumpla el texto y los filtros.
		Con ``con_objetos`` cada hoja lleva en ``tipos`` sus objetos, los más
		comunes primero. Un objeto sin subcategoría cuelga de una hoja de clave vacía.
		"""
		encontrados = self.buscar_avanzado(
			texto,
			funcion=funcion,
			lugar=lugar,
			estancia=estancia,
			obstaculo=obstaculo,
			riesgo=riesgo,
			ambito=ambito,
			colocacion=colocacion,
			frecuencia=frecuencia,
			contenedor=contenedor,
			con_sonido=con_sonido,
			usable=usable,
			orden="frecuencia",
		)
		por_complemento: dict[str, dict[str, dict[str, list[str]]]] = {}
		for definicion in encontrados:
			por_complemento.setdefault(definicion.complemento, {}).setdefault(definicion.categoria, {}).setdefault(
				definicion.subcategoria, []
			).append(definicion.tipo)
		raices: list[NodoArbol] = []
		for complemento in self.complementos():
			categorias = por_complemento.get(complemento.id)
			if not categorias:
				continue
			raiz = NodoArbol("complemento", complemento.id, complemento.nombre)
			orden_categorias = {clave: puesto for puesto, clave in enumerate(complemento.categorias)}
			orden_subcategorias = {clave: puesto for puesto, clave in enumerate(complemento.subcategorias)}
			for categoria in sorted(categorias, key=lambda clave: (orden_categorias.get(clave, len(orden_categorias)), clave)):
				rama = NodoArbol("categoria", categoria, complemento.categorias.get(categoria) or categoria or _("Sin categoría"))
				subcategorias = categorias[categoria]
				for subcategoria in sorted(
					subcategorias, key=lambda clave: (orden_subcategorias.get(clave, len(orden_subcategorias)), clave)
				):
					tipos = subcategorias[subcategoria]
					hoja = NodoArbol(
						"subcategoria",
						subcategoria,
						complemento.nombre_subcategoria(subcategoria) if subcategoria else _("Sin clasificar"),
						len(tipos),
						tipos=list(tipos) if con_objetos else [],
					)
					rama.hijos.append(hoja)
					rama.total += hoja.total
				raiz.hijos.append(rama)
				raiz.total += rama.total
			raices.append(raiz)
		return raices

	def relacionados(self, tipo: str, limite: int = 12) -> list[DefObjeto]:
		"""Objetos que suelen ir con ``<complemento>/<objeto>``: con una mesa, sus sillas.

		Primero los que el propio objeto declara en ``relacionados``. Después,
		los de función afín (``FUNCIONES_AFINES``) que comparten estancia con
		él, mejor cuantas más estancias compartan, mejor si son de su mismo
		complemento y mejor cuanto más comunes. Lista vacía si el tipo no existe.
		"""
		definicion = self.objeto(tipo)
		if definicion is None:
			return []
		elegidos: list[DefObjeto] = []
		vistos = {definicion.tipo}
		for referencia in definicion.relacionados:
			otro = self.objeto(referencia if "/" in referencia else f"{definicion.complemento}/{referencia}")
			complemento = self._complementos.get(otro.complemento) if otro else None
			if otro is not None and complemento is not None and complemento.activo and otro.tipo not in vistos:
				elegidos.append(otro)
				vistos.add(otro.tipo)
		afines = FUNCIONES_AFINES.get(definicion.funcion, ())
		estancias = set(definicion.estancias) - {"cualquiera"}
		candidatos: list[tuple[tuple[int, int, int, str], DefObjeto]] = []
		if afines and estancias:
			for indizado in self._indizados():
				otro = indizado.definicion
				if otro.tipo in vistos or otro.funcion not in afines:
					continue
				comunes = len(estancias & indizado.valores["estancia"])
				if not comunes:
					continue
				clave = (0 if otro.complemento == definicion.complemento else 1, -comunes, indizado.puesto_frecuencia, indizado.nombre)
				candidatos.append((clave, otro))
		candidatos.sort(key=lambda par: par[0])
		# Se reparte entre las funciones afines: tras una mesa no deben salir doce sillas y ninguna lámpara.
		por_funcion: dict[str, list[DefObjeto]] = {}
		for _clave, otro in candidatos:
			por_funcion.setdefault(otro.funcion, []).append(otro)
		while len(elegidos) < limite and any(por_funcion.values()):
			for funcion in afines:
				cola = por_funcion.get(funcion)
				if cola and len(elegidos) < limite:
					elegidos.append(cola.pop(0))
		return elegidos[:limite]

	def crear_objeto(self, tipo: str, x: float, y: float, rumbo: float = 0.0, variante: str | None = None) -> Objeto:
		"""Crea un objeto de ese tipo con sus medidas por defecto (o las de una variante).

		Lanza ``KeyError`` si el tipo no está en el catálogo o la variante no existe.
		El objeto sale sin id: se lo pone ``colocacion.colocar`` al añadirlo a una planta.
		"""
		definicion = self.objeto(tipo)
		if definicion is None:
			raise KeyError(tipo)
		objeto = Objeto(
			nombre=definicion.nombre,
			descripcion=definicion.descripcion,
			tipo=definicion.tipo,
			x=float(x),
			y=float(y),
			rumbo=geo.normalizar_rumbo(rumbo),
			ancho=definicion.rango("ancho")[1],
			fondo=definicion.rango("fondo")[1],
			alto=definicion.rango("alto")[1],
			estado=definicion.estados[0] if definicion.estados else "",
		)
		if variante:
			elegida = definicion.variante(variante)
			if elegida is None:
				raise KeyError(f"{tipo}#{variante}")
			objeto.variante = elegida.id
			objeto.ancho, objeto.fondo, objeto.alto = elegida.ancho, elegida.fondo, elegida.alto
		return objeto

	def ajustar_a_hueco(self, defn: DefObjeto, ancho_libre: float, fondo_libre: float) -> tuple[float, float] | None:
		"""Medidas (ancho, fondo) con las que el objeto cabe en un hueco; None si no cabe.

		Por orden: sus medidas por defecto si caben; si no, la variante más
		grande que quepa; si no, se encoge dentro de su rango hasta el hueco.
		Nunca baja del mínimo del complemento: si ni así cabe, no se coloca.
		"""
		elegido = self._ajuste(defn, ancho_libre, fondo_libre)
		return (elegido[0], elegido[1]) if elegido else None

	def _ajuste(self, defn: DefObjeto, ancho_libre: float, fondo_libre: float) -> tuple[float, float, str, float | None] | None:
		"""Como ``ajustar_a_hueco`` pero dice además la variante elegida y su alto."""
		margen = 1e-6
		minimo_a, defecto_a, _max_a = defn.rango("ancho")
		minimo_f, defecto_f, _max_f = defn.rango("fondo")
		if defecto_a <= ancho_libre + margen and defecto_f <= fondo_libre + margen:
			return defecto_a, defecto_f, "", None
		caben = [v for v in defn.variantes if v.ancho <= ancho_libre + margen and v.fondo <= fondo_libre + margen]
		if caben:
			mayor = max(caben, key=lambda v: (v.ancho * v.fondo, v.ancho))
			return mayor.ancho, mayor.fondo, mayor.id, mayor.alto
		ancho = min(defecto_a, ancho_libre)
		fondo = min(defecto_f, fondo_libre)
		if ancho + margen < minimo_a or fondo + margen < minimo_f:
			return None
		return max(ancho, minimo_a), max(fondo, minimo_f), "", None

	def ajustar_objeto(self, objeto: Objeto, ancho_libre: float, fondo_libre: float) -> bool:
		"""Ajusta las medidas de un objeto al hueco; False (sin tocarlo) si no cabe.

		Una caja (tipo no instalado) no tiene rango: cabe con sus medidas o no cabe.
		"""
		definicion = self.definicion_de(objeto)
		if definicion is None:
			return objeto.ancho <= ancho_libre + 1e-6 and objeto.fondo <= fondo_libre + 1e-6
		if objeto.variante:
			# Se pidió una variante concreta: si cabe se respeta.
			actual = definicion.variante(objeto.variante)
			if actual and actual.ancho <= ancho_libre + 1e-6 and actual.fondo <= fondo_libre + 1e-6:
				return True
		elegido = self._ajuste(definicion, ancho_libre, fondo_libre)
		if elegido is None:
			return False
		objeto.ancho, objeto.fondo, objeto.variante = elegido[0], elegido[1], elegido[2]
		if elegido[3] is not None:
			objeto.alto = elegido[3]
		return True

	def huella(self, objeto: Objeto) -> list[Punto]:
		"""Polígono real que ocupa el objeto en el mundo, según su forma, medidas y rumbo."""
		definicion = self.definicion_de(objeto)
		if definicion is None:
			return objeto.huella_caja()
		return geo.forma_a_mundo(definicion.puntos_forma(), objeto.x, objeto.y, objeto.ancho, objeto.fondo, objeto.rumbo)

	def bloquea(self, objeto: Objeto) -> bool:
		"""True si el objeto corta el paso (una caja sin ficha lo corta siempre)."""
		if "bloquea" in objeto.datos:
			return bool(objeto.datos["bloquea"])
		definicion = self.definicion_de(objeto)
		if definicion is None:
			return True
		if objeto.estado and objeto.estado in definicion.paso_libre:
			return False
		return definicion.bloquea

	def material(self, objeto: Objeto) -> str:
		"""Material del objeto (para el sonido del golpe)."""
		if objeto.datos.get("material"):
			return str(objeto.datos["material"])
		definicion = self.definicion_de(objeto)
		return definicion.material if definicion else "madera"

	def es_caja(self, objeto: Objeto) -> bool:
		"""True si el tipo del objeto no está instalado y se trata como una caja."""
		return self.definicion_de(objeto) is None

	def tipos_que_faltan(self, objetos: Iterable[Objeto]) -> list[str]:
		"""Tipos usados por esos objetos que no están en el catálogo (sin contar «caja»)."""
		return sorted({o.tipo for o in objetos if o.tipo != TIPO_CAJA and self.objeto(o.tipo) is None})


# ── Instalación y comprobación ───────────────────────────────────────────────


def _complemento_permitido(nombre: str) -> bool:
	"""True si el nombre (ya sin carpeta envolvente) es de los que admite un complemento."""
	ruta = PurePosixPath(nombre)
	extension = ruta.suffix.lower()
	if len(ruta.parts) == 1:
		return nombre == NOMBRE_FICHA or extension in (".txt", ".md")
	if len(ruta.parts) != 2:
		return False
	carpeta = ruta.parts[0]
	if carpeta == "locales":
		return extension == ".json"
	if carpeta == "sonidos":
		return extension in EXTENSIONES_SONIDO
	if carpeta == "imagenes":
		return extension in EXTENSIONES_IMAGEN
	return False


def _limite_complemento(nombre: str) -> int:
	return MAX_BYTES_JSON if nombre.lower().endswith((".json", ".txt", ".md")) else MAX_BYTES_RECURSO


def instalar_complemento(ruta_zip: str | Path, carpeta_plugins: str | Path | None = None) -> str:
	"""Instala un complemento ``.elabc`` (un ZIP) en la carpeta de complementos y devuelve su id.

	El ZIP puede traer los ficheros sueltos o dentro de una única carpeta.
	Antes de escribir nada se comprueban nombres, tipos y tamaños, y se lee la
	ficha; después se extrae a una carpeta provisional y solo al final
	sustituye a la versión instalada, de modo que un ZIP dañado no deja un
	complemento a medias. Lanza ``ErrorComplemento`` con el motivo.
	"""
	origen = Path(ruta_zip)
	destino_raiz = Path(carpeta_plugins) if carpeta_plugins is not None else paths.subcarpeta(CARPETA_PLUGINS)
	if not origen.is_file():
		raise ErrorComplemento(_("No existe el fichero «{ruta}».").format(ruta=origen))
	try:
		archivo = zipfile.ZipFile(origen)
	except (zipfile.BadZipFile, OSError) as error:
		raise ErrorComplemento(_("«{nombre}» no es un complemento o está dañado.").format(nombre=origen.name)) from error
	with archivo:
		nombres = [e.filename for e in archivo.infolist() if not e.is_dir()]
		prefijo = ""
		if NOMBRE_FICHA not in nombres:
			raices = {nombre.split("/")[0] for nombre in nombres}
			if len(raices) == 1 and f"{next(iter(raices))}/{NOMBRE_FICHA}" in nombres:
				prefijo = next(iter(raices)) + "/"
			else:
				raise ErrorComplemento(_("Al complemento le falta el fichero «{nombre}».").format(nombre=NOMBRE_FICHA))

		def permitido(nombre: str) -> bool:
			return nombre.startswith(prefijo) and _complemento_permitido(nombre[len(prefijo) :])

		try:
			entradas = comprobar_zip(archivo, permitido, limite_de=_limite_complemento)
			ficha = leer_json(leer_entrada(archivo, archivo.getinfo(prefijo + NOMBRE_FICHA), MAX_BYTES_JSON), NOMBRE_FICHA)
		except ErrorComplemento:
			raise
		except ErrorFormato as error:
			raise ErrorComplemento(str(error)) from error
		id_complemento = str(ficha.get("id") or "") if isinstance(ficha, dict) else ""
		if not _PATRON_ID.match(id_complemento):
			raise ErrorComplemento(_("El identificador del complemento «{id}» no es válido.").format(id=id_complemento))
		provisional = destino_raiz / f".{id_complemento}.nuevo"
		definitiva = destino_raiz / id_complemento
		try:
			if provisional.exists():
				shutil.rmtree(provisional)
			provisional.mkdir(parents=True)
			for entrada in entradas:
				relativa = entrada.filename[len(prefijo) :]
				try:
					contenido = leer_entrada(archivo, entrada, _limite_complemento(relativa))
				except ErrorFormato as error:
					raise ErrorComplemento(str(error)) from error
				salida = provisional.joinpath(*relativa.split("/"))
				salida.parent.mkdir(parents=True, exist_ok=True)
				salida.write_bytes(contenido)
			# La ficha tiene que cargarse de verdad antes de dar el complemento por bueno.
			complemento, avisos = leer_complemento(provisional, idioma=i18n.IDIOMA_ORIGEN)
			# Un complemento sin objetos solo vale si es de recursos: sonidos que comparten otros complementos.
			solo_recursos = (
				not avisos and any((provisional / CARPETA_SONIDOS).glob("*")) if (provisional / CARPETA_SONIDOS).is_dir() else False
			)
			if not complemento.objetos and not solo_recursos:
				detalle = avisos[0].mensaje if avisos else _("no define ningún objeto")
				raise ErrorComplemento(
					_("El complemento «{id}» no tiene ningún objeto utilizable: {detalle}").format(id=id_complemento, detalle=detalle)
				)
			if definitiva.exists():
				shutil.rmtree(definitiva)
			provisional.rename(definitiva)
		except OSError as error:
			raise ErrorComplemento(
				_("No se puede instalar el complemento «{id}»: {detalle}").format(id=id_complemento, detalle=error)
			) from error
		finally:
			if provisional.exists():
				shutil.rmtree(provisional, ignore_errors=True)
	log.info("Complemento «%s» instalado en %s", id_complemento, definitiva)
	return id_complemento


def _nombres_sonido(sonidos: dict[str, Any]) -> list[str]:
	"""Nombres de sonido que menciona la ficha de un objeto."""
	nombres: list[str] = []
	for valor in sonidos.values():
		if isinstance(valor, str):
			nombres.append(valor)
		elif isinstance(valor, dict) and isinstance(valor.get("sonido"), str):
			nombres.append(valor["sonido"])
	return nombres


def validar_complemento(carpeta: str | Path) -> list[Aviso]:
	"""Revisa un complemento antes de publicarlo y devuelve lo que hay que corregir.

	Comprueba la ficha general, las medidas (coherentes y con variantes dentro
	de rango), las formas, los estados y acciones, que los sonidos e imágenes
	que vienen dentro del complemento existan y que cada imagen tenga
	descripción en texto. Una lista vacía significa que está listo.
	"""
	raiz = Path(carpeta)
	avisos: list[Aviso] = []
	try:
		datos = _leer_ficha(raiz)
		complemento, avisos_carga = leer_complemento(raiz, idioma=i18n.IDIOMA_ORIGEN)
	except ErrorComplemento as error:
		return [_aviso("error", "complemento_no_valido", str(error), raiz.name, _("Corrija «{fichero}».").format(fichero=NOMBRE_FICHA))]
	avisos.extend(avisos_carga)
	if complemento.id != raiz.name:
		avisos.append(
			_aviso(
				"aviso",
				"carpeta_distinta",
				_("La carpeta se llama «{carpeta}» pero el complemento se identifica como «{id}».").format(
					carpeta=raiz.name, id=complemento.id
				),
				complemento.id,
				_("Llame a la carpeta igual que el identificador."),
			)
		)
	for clave, texto in (("nombre", _("nombre")), ("version", _("versión")), ("autor", _("autor")), ("licencia", _("licencia"))):
		if not str(datos.get(clave) or "").strip():
			avisos.append(
				_aviso(
					"aviso",
					"ficha_incompleta",
					_("A la ficha del complemento le falta: {campo}.").format(campo=texto),
					complemento.id,
					_("Rellene «{clave}» en «{fichero}».").format(clave=clave, fichero=NOMBRE_FICHA),
				)
			)
	brutos = {str(b.get("id")): b for b in datos.get("objetos") or [] if isinstance(b, dict)}
	for definicion in complemento.objetos:
		bruto = brutos.get(definicion.id, {})
		referencia = definicion.tipo
		if not definicion.categoria:
			avisos.append(
				_aviso(
					"aviso",
					"sin_categoria",
					_("El objeto «{id}» no tiene categoría.").format(id=definicion.id),
					referencia,
					_("Póngale una para poder filtrarlo en el catálogo."),
				)
			)
		if not definicion.descripcion.strip():
			avisos.append(
				_aviso(
					"aviso",
					"sin_descripcion",
					_("El objeto «{id}» no tiene descripción hablada.").format(id=definicion.id),
					referencia,
					_("Escriba una frase que explique al alumno qué es."),
				)
			)
		for clave, tabla in (("ambito", AMBITOS), ("colocacion", COLOCACIONES)):
			for valor in _textos(bruto.get(clave)):
				if valor not in tabla:
					avisos.append(
						_aviso(
							"aviso",
							"valor_desconocido",
							_("El objeto «{id}» usa «{valor}» en «{clave}», que no existe.").format(
								id=definicion.id, valor=valor, clave=clave
							),
							referencia,
							_("Valores admitidos: {valores}.").format(valores=", ".join(tabla)),
						)
					)
		# Clasificación: es opcional, pero lo que se declare tiene que ser un valor de la taxonomía.
		for clave, faceta in (("funcion", "funcion"), ("obstaculo", "obstaculo"), ("frecuencia", "frecuencia")):
			valor = bruto.get(clave)
			if valor and valor not in TAXONOMIAS[faceta]:
				avisos.append(
					_aviso(
						"aviso",
						"valor_desconocido",
						_("El objeto «{id}» usa «{valor}» en «{clave}», que no existe.").format(id=definicion.id, valor=valor, clave=clave),
						referencia,
						_("Valores admitidos: {valores}.").format(valores=", ".join(TAXONOMIAS[faceta])),
					)
				)
		for clave, faceta in (("lugares", "lugar"), ("estancias", "estancia"), ("riesgos", "riesgo")):
			for valor in _textos(bruto.get(clave)):
				if valor not in TAXONOMIAS[faceta]:
					avisos.append(
						_aviso(
							"aviso",
							"valor_desconocido",
							_("El objeto «{id}» usa «{valor}» en «{clave}», que no existe.").format(
								id=definicion.id, valor=valor, clave=clave
							),
							referencia,
							_("Valores admitidos: {valores}.").format(valores=", ".join(TAXONOMIAS[faceta])),
						)
					)
		if definicion.subcategoria and definicion.subcategoria not in complemento.subcategorias:
			avisos.append(
				_aviso(
					"aviso",
					"subcategoria_sin_nombre",
					_("El objeto «{id}» usa la subcategoría «{valor}», que no tiene nombre visible.").format(
						id=definicion.id, valor=definicion.subcategoria
					),
					referencia,
					_("Añádala a la tabla «subcategorias» de la ficha del complemento."),
				)
			)
		for relacionado in definicion.relacionados:
			if "/" not in relacionado and complemento.objeto(relacionado) is None:
				avisos.append(
					_aviso(
						"aviso",
						"relacionado_desconocido",
						_("El objeto «{id}» dice ir con «{otro}», que no existe en el complemento.").format(
							id=definicion.id, otro=relacionado
						),
						referencia,
						_("Corrija el identificador o escríbalo completo: complemento/objeto."),
					)
				)
		for dimension in DIMENSIONES:
			if dimension not in (bruto.get("medidas") or {}):
				avisos.append(
					_aviso(
						"aviso",
						"medida_ausente",
						_("El objeto «{id}» no declara la medida «{dimension}»; se usará un metro.").format(
							id=definicion.id, dimension=dimension
						),
						referencia,
						_("Añada «{dimension}»: [mínimo, defecto, máximo] en metros.").format(dimension=dimension),
					)
				)
		for variante in definicion.variantes:
			for dimension in DIMENSIONES:
				minimo, _defecto, maximo = definicion.rango(dimension)
				valor = getattr(variante, dimension)
				if not (minimo - 1e-9 <= valor <= maximo + 1e-9):
					avisos.append(
						_aviso(
							"error",
							"variante_fuera_de_rango",
							_(
								"La variante «{variante}» de «{id}» mide {valor} m de {dimension}, fuera de su rango ({minimo} a {maximo} m)."
							).format(
								variante=variante.id, id=definicion.id, valor=valor, dimension=dimension, minimo=minimo, maximo=maximo
							),
							referencia,
							_("Amplíe el rango o corrija la variante."),
						)
					)
		for accion in definicion.acciones:
			for extremo in ("de", "a"):
				estado = accion.get(extremo)
				if estado and estado not in definicion.estados:
					avisos.append(
						_aviso(
							"error",
							"estado_desconocido",
							_("La acción «{accion}» de «{id}» usa el estado «{estado}», que no está en «estados».").format(
								accion=accion.get("id"), id=definicion.id, estado=estado
							),
							referencia,
							_("Añada el estado a la lista «estados» o corrija la acción."),
						)
					)
		if definicion.suelo and definicion.suelo not in SUELOS:
			avisos.append(
				_aviso(
					"aviso",
					"valor_desconocido",
					_("El objeto «{id}» usa «{valor}» en «{clave}», que no existe.").format(
						id=definicion.id, valor=definicion.suelo, clave="suelo"
					),
					referencia,
					_("Valores admitidos: {valores}.").format(valores=", ".join(SUELOS)),
				)
			)
		tipo_dinamica = definicion.dinamica.get("tipo")
		if definicion.dinamica and tipo_dinamica not in DINAMICAS:
			avisos.append(
				_aviso(
					"aviso",
					"valor_desconocido",
					_("El objeto «{id}» usa «{valor}» en «{clave}», que no existe.").format(
						id=definicion.id, valor=tipo_dinamica, clave="dinamica.tipo"
					),
					referencia,
					_("Valores admitidos: {valores}.").format(valores=", ".join(DINAMICAS)),
				)
			)
		estados_citados = [fase.get("estado") for fase in definicion.dinamica.get("fases") or [] if isinstance(fase, dict)]
		estados_citados += [definicion.dinamica.get(clave) for clave in ("estado", "al_terminar")]
		estados_citados += definicion.paso_libre
		if isinstance(definicion.sonidos.get("propio"), dict):
			estados_citados.append(definicion.sonidos["propio"].get("estado"))
		for estado in estados_citados:
			if estado and estado not in definicion.estados:
				avisos.append(
					_aviso(
						"error",
						"estado_desconocido",
						_(
							"El objeto «{id}» nombra en su dinámica, en «paso_libre» o en su sonido propio el estado «{estado}», que no está en «estados»."
						).format(id=definicion.id, estado=estado),
						referencia,
						_("Añada el estado a la lista «estados» o corríjalo."),
					)
				)
		color = definicion.simbolo.get("color")
		if color and not _PATRON_COLOR.match(str(color)):
			avisos.append(
				_aviso(
					"aviso",
					"color_no_valido",
					_("El color «{color}» del símbolo de «{id}» no tiene la forma #RRGGBB.").format(color=color, id=definicion.id),
					referencia,
					_("Use un color como #8B5A2B."),
				)
			)
		sonidos_objeto = _nombres_sonido(definicion.sonidos) + [
			str(a["sonido"]) for a in definicion.acciones if isinstance(a.get("sonido"), str)
		]
		sonidos_objeto += [
			str(f["sonido"]) for f in definicion.dinamica.get("fases") or [] if isinstance(f, dict) and isinstance(f.get("sonido"), str)
		]
		if isinstance(definicion.dinamica.get("sonido_al_terminar"), str):
			sonidos_objeto.append(definicion.dinamica["sonido_al_terminar"])
		for nombre in sonidos_objeto:
			dependencia, fichero = partes_de_sonido(nombre)
			if dependencia and es_sonido_de_complemento(nombre):
				# Es de otro complemento: tiene que estar declarado en «depende_de» y, si está instalado al lado, tener el fichero.
				if dependencia not in complemento.depende_de:
					avisos.append(
						_aviso(
							"error",
							"dependencia_no_declarada",
							_(
								"El objeto «{id}» usa el sonido «{sonido}» del complemento «{dependencia}», que no está en «depende_de»."
							).format(id=definicion.id, sonido=nombre, dependencia=dependencia),
							referencia,
							_("Añada «{dependencia}» a la lista «depende_de» de la ficha del complemento.").format(dependencia=dependencia),
						)
					)
				vecino = Complemento(id=dependencia, carpeta=raiz.parent / dependencia)
				if (raiz.parent / dependencia).is_dir() and vecino.ruta_recurso(fichero) is None:
					avisos.append(
						_aviso(
							"error",
							"sonido_ausente",
							_("El objeto «{id}» usa el sonido «{sonido}», que no está en el complemento «{dependencia}».").format(
								id=definicion.id, sonido=nombre, dependencia=dependencia
							),
							referencia,
							_("Corrija el nombre o añada el fichero a la carpeta «sonidos» de «{dependencia}».").format(
								dependencia=dependencia
							),
						)
					)
				continue
			# Un nombre con extensión o que empieza por «sonidos/» dice ser un fichero del complemento: tiene que estar.
			if es_sonido_de_complemento(nombre) and complemento.ruta_recurso(nombre) is None:
				avisos.append(
					_aviso(
						"error",
						"sonido_ausente",
						_("El objeto «{id}» usa el sonido «{sonido}», que no está en el complemento.").format(
							id=definicion.id, sonido=nombre
						),
						referencia,
						_("Añada el fichero a la carpeta «sonidos» o use el nombre de un sonido de serie."),
					)
				)
		if definicion.imagen:
			fichero = str(definicion.imagen.get("fichero") or "")
			if not fichero or complemento.ruta_recurso(fichero) is None:
				avisos.append(
					_aviso(
						"error",
						"imagen_ausente",
						_("La imagen «{imagen}» del objeto «{id}» no está en el complemento.").format(imagen=fichero, id=definicion.id),
						referencia,
						_("Añada el fichero a la carpeta «imagenes»."),
					)
				)
			if not str(definicion.imagen.get("descripcion") or "").strip():
				avisos.append(
					_aviso(
						"error",
						"imagen_sin_descripcion",
						_("La imagen del objeto «{id}» no tiene descripción en texto.").format(id=definicion.id),
						referencia,
						_("Describa la imagen para quien no la ve."),
					)
				)
	carpeta_locales = raiz / "locales"
	if carpeta_locales.is_dir():
		for fichero in sorted(carpeta_locales.glob("*.json")):
			try:
				traduccion = json.loads(fichero.read_text(encoding="utf-8-sig"))
			except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
				avisos.append(
					_aviso(
						"error",
						"traduccion_no_valida",
						_("La traducción «{nombre}» no se puede leer: {detalle}").format(nombre=fichero.name, detalle=error),
						complemento.id,
						_("Corrija el JSON."),
					)
				)
				continue
			por_objeto = traduccion.get("objetos") if isinstance(traduccion, dict) and isinstance(traduccion.get("objetos"), dict) else {}
			for id_objeto in por_objeto:
				if complemento.objeto(id_objeto) is None:
					avisos.append(
						_aviso(
							"aviso",
							"traduccion_sobrante",
							_("La traducción «{nombre}» nombra el objeto «{id}», que no existe.").format(nombre=fichero.name, id=id_objeto),
							complemento.id,
							_("Quite esa entrada o corrija el identificador."),
						)
					)
	return avisos


def empaquetar_complemento(carpeta: str | Path, ruta_zip: str | Path) -> Path:
	"""Crea el ``.elabc`` de un complemento para compartirlo (solo los ficheros admitidos)."""
	raiz = Path(carpeta)
	destino = Path(ruta_zip)
	if not (raiz / NOMBRE_FICHA).is_file():
		raise ErrorComplemento(_("En «{carpeta}» falta el fichero «{nombre}».").format(carpeta=raiz.name, nombre=NOMBRE_FICHA))
	try:
		with zipfile.ZipFile(destino, "w", compression=zipfile.ZIP_DEFLATED) as archivo:
			for fichero in sorted(raiz.rglob("*")):
				relativa = fichero.relative_to(raiz).as_posix()
				if fichero.is_file() and _complemento_permitido(relativa):
					archivo.write(fichero, relativa)
	except OSError as error:
		raise ErrorComplemento(_("No se puede crear «{ruta}»: {detalle}").format(ruta=destino, detalle=error)) from error
	return destino
