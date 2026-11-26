"""Modelo de datos de un entorno: plantas, espacios, aberturas, conectores y objetos.

Es el documento que edita el profesional y que recorre el alumno. Solo son
datos: cada clase sabe convertirse a un diccionario (``a_dict``) y
reconstruirse desde él (``de_dict``) de forma tolerante, porque un entorno
puede venir de una versión más antigua o más nueva del programa, o haber sido
retocado a mano: una clave que falta toma su valor de serie, una clave
desconocida se ignora y un valor del tipo equivocado no rompe la carga.

Convenciones: metros; x hacia el este, y hacia el norte; rumbo 0 = norte y
en el sentido del reloj. Las paredes de un espacio «cerrado» NO se guardan:
se derivan de su contorno (ver ``segmentos_solidos``), de modo que dos
habitaciones adosadas comparten pared sin duplicarla.
"""

from __future__ import annotations

import dataclasses
import logging
import math
import operator
from collections.abc import Callable, Iterator
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, ClassVar, NamedTuple, Self

from app.core.i18n import N_, _
from app.dominio import geometria as geo
from app.dominio.geometria import Punto

if TYPE_CHECKING:
	from app.dominio.catalogo import Catalogo

log = logging.getLogger(__name__)

# Versión del formato del documento. Al cambiarla hay que añadir una migración en formato.py.
FORMATO_ACTUAL = 1

# ── Listas de valores válidos (clave estable → nombre visible traducible) ────

TIPOS_ESPACIO: dict[str, str] = {
	"habitacion": N_("Habitación"),
	"pasillo": N_("Pasillo"),
	"vestibulo": N_("Vestíbulo"),
	"escalera": N_("Hueco de escalera"),
	"cabina": N_("Cabina de ascensor"),
	"exterior": N_("Zona exterior"),
	"acera": N_("Acera"),
	"calzada": N_("Calzada"),
	"paso_peatones": N_("Paso de peatones"),
	"plaza": N_("Plaza"),
	"parque": N_("Parque"),
	"sendero": N_("Sendero"),
	"edificio": N_("Edificio"),
}

SUELOS: dict[str, str] = {
	"baldosa": N_("Baldosa"),
	"madera": N_("Madera"),
	"moqueta": N_("Moqueta"),
	"alfombra": N_("Alfombra"),
	"hormigon": N_("Hormigón"),
	"asfalto": N_("Asfalto"),
	"acera": N_("Acera"),
	"adoquin": N_("Adoquín"),
	"tierra": N_("Tierra"),
	"hierba": N_("Hierba"),
	"grava": N_("Grava"),
	"metal": N_("Metal"),
	"arena": N_("Arena"),
	"agua": N_("Agua"),
	"tactil_botones": N_("Pavimento táctil de botones"),
	"tactil_rayas": N_("Pavimento táctil de rayas"),
}

ACUSTICAS: dict[str, str] = {
	"seca": N_("Seca"),
	"habitacion": N_("Habitación"),
	"sala_grande": N_("Sala grande"),
	"pasillo": N_("Pasillo"),
	"bano": N_("Baño"),
	"escalera": N_("Escalera"),
	"nave": N_("Nave"),
	"exterior": N_("Exterior"),
	"calle": N_("Calle"),
	"parque": N_("Parque"),
}

MATERIALES_PARED: dict[str, str] = {
	"ladrillo": N_("Ladrillo"),
	"hormigon": N_("Hormigón"),
	"yeso": N_("Yeso"),
	"madera": N_("Madera"),
	"cristal": N_("Cristal"),
	"metal": N_("Metal"),
	"piedra": N_("Piedra"),
	"valla": N_("Valla"),
	"seto": N_("Seto"),
}

TIPOS_ABERTURA: dict[str, str] = {
	"puerta": N_("Puerta"),
	"hueco": N_("Hueco sin puerta"),
	"ventana": N_("Ventana"),
	"portal": N_("Portal"),
}

ESTADOS_ABERTURA: dict[str, str] = {
	"abierta": N_("Abierta"),
	"cerrada": N_("Cerrada"),
	"con_llave": N_("Cerrada con llave"),
}

HOJAS: dict[str, str] = {
	"batiente": N_("Batiente"),
	"corredera": N_("Corredera"),
	"automatica": N_("Automática"),
	"ninguna": N_("Sin hoja"),
}

TIPOS_CONECTOR: dict[str, str] = {
	"escalera": N_("Escalera"),
	"rampa": N_("Rampa"),
	"ascensor": N_("Ascensor"),
	"escalera_mecanica": N_("Escalera mecánica"),
}

PASAMANOS: dict[str, str] = {
	"izquierda": N_("A la izquierda"),
	"derecha": N_("A la derecha"),
	"ambos": N_("A los dos lados"),
	"ninguno": N_("Sin pasamanos"),
}

TIPOS_REFERENCIA: dict[str, str] = {
	"punto": N_("Punto de interés"),
	"sonora": N_("Referencia sonora"),
	"tactil": N_("Referencia táctil"),
	"olor": N_("Referencia de olor"),
	"parada": N_("Parada de transporte"),
	"semaforo": N_("Semáforo"),
	"portal": N_("Portal"),
	"comercio": N_("Comercio"),
	"mobiliario": N_("Mobiliario urbano"),
}

SENTIDOS_VIA: dict[str, str] = {
	"doble": N_("Doble sentido"),
	"ida": N_("Sentido único, de inicio a fin"),
	"vuelta": N_("Sentido único, de fin a inicio"),
}

NIVELES_TRAFICO: dict[int, str] = {
	0: N_("Sin tráfico"),
	1: N_("Tráfico escaso"),
	2: N_("Tráfico moderado"),
	3: N_("Tráfico intenso"),
}

# Tipos de espacio que por naturaleza son de calle (zonas, no habitaciones con paredes).
TIPOS_EXTERIORES = frozenset({"exterior", "acera", "calzada", "paso_peatones", "plaza", "parque", "sendero"})

# Suelo y acústica de serie según el tipo de espacio, para no pedirlos siempre.
SUELO_POR_TIPO: dict[str, str] = {
	"acera": "acera",
	"calzada": "asfalto",
	"paso_peatones": "asfalto",
	"plaza": "adoquin",
	"parque": "hierba",
	"sendero": "tierra",
	"exterior": "hormigon",
	"cabina": "metal",
}
ACUSTICA_POR_TIPO: dict[str, str] = {
	"habitacion": "habitacion",
	"pasillo": "pasillo",
	"vestibulo": "sala_grande",
	"escalera": "escalera",
	"cabina": "seca",
	"exterior": "exterior",
	"acera": "calle",
	"calzada": "calle",
	"paso_peatones": "calle",
	"plaza": "exterior",
	"parque": "parque",
	"sendero": "parque",
	"edificio": "seca",
}

# Tolerancia (metros) para considerar que una abertura está sobre una pared.
TOLERANCIA_PARED = 0.05


def nombre_visible(tabla: dict[Any, str], clave: Any) -> str:
	"""Nombre traducido de una clave de las tablas anteriores; la propia clave si no está."""
	texto = tabla.get(clave)
	return _(texto) if texto else str(clave)


# ── Conversión tolerante ─────────────────────────────────────────────────────


def a_punto(valor: Any) -> Punto:
	"""Convierte ``[x, y]`` (o cualquier par) en un punto; lanza ValueError si no lo es."""
	x, y = valor
	x, y = float(x), float(y)
	if not (math.isfinite(x) and math.isfinite(y)):
		raise ValueError("coordenada no finita")
	return x, y


def a_puntos(valor: Any) -> list[Punto]:
	"""Convierte una lista de pares en lista de puntos."""
	return [a_punto(par) for par in valor]


def _a_basico(valor: Any) -> Any:
	"""Convierte recursivamente a tipos que JSON sabe escribir.

	Se mira primero el TIPO exacto de los valores más frecuentes (números,
	textos, puntos): preguntar ``hasattr(valor, "a_dict")`` a cada número
	lanzaba y capturaba una excepción por dentro, y guardar o anotar para
	deshacer un barrio de miles de espacios tardaba más de medio segundo.
	El resultado es el mismo que antes.
	"""
	tipo = type(valor)
	if tipo is float:
		# Redondeo a décimas de milímetro: ficheros estables y sin 0.30000000000000004.
		return round(valor, 4)
	if tipo is str or tipo is int or tipo is bool or valor is None:
		return valor
	if tipo is tuple and len(valor) == 2:
		x, y = valor
		if type(x) is float and type(y) is float:
			return [round(x, 4), round(y, 4)]
	if hasattr(valor, "a_dict"):
		return valor.a_dict()
	if isinstance(valor, (list, tuple)):
		return [_a_basico(v) for v in valor]
	if isinstance(valor, dict):
		return {str(k): _a_basico(v) for k, v in valor.items()}
	if isinstance(valor, float):
		return round(valor, 4)
	return valor


def _convertir_por_tipo(valor: Any, modelo: Any) -> Any:
	"""Ajusta ``valor`` al tipo del valor de serie ``modelo``; lanza si no se puede."""
	if isinstance(modelo, bool):
		if isinstance(valor, (bool, int)):
			return bool(valor)
		raise ValueError("se esperaba verdadero o falso")
	if isinstance(modelo, int):
		return int(valor)
	if isinstance(modelo, float):
		numero = float(valor)
		if not math.isfinite(numero):
			raise ValueError("número no finito")
		return numero
	if isinstance(modelo, str):
		if isinstance(valor, (dict, list)):
			raise ValueError("se esperaba un texto")
		return "" if valor is None else str(valor)
	if isinstance(modelo, dict):
		if not isinstance(valor, dict):
			raise ValueError("se esperaba un diccionario")
		return dict(valor)
	if isinstance(modelo, list):
		if not isinstance(valor, list):
			raise ValueError("se esperaba una lista")
		return list(valor)
	return valor


_CAMPOS_POR_CLASE: dict[type, tuple[str, ...]] = {}


def _nombres_de_campos(clase: type) -> tuple[str, ...]:
	"""Nombres de los campos de una dataclass del modelo, calculados una vez por clase (``a_dict`` los pide miles de veces)."""
	nombres = _CAMPOS_POR_CLASE.get(clase)
	if nombres is None:
		nombres = tuple(campo.name for campo in dataclasses.fields(clase))  # type: ignore[arg-type]
		_CAMPOS_POR_CLASE[clase] = nombres
	return nombres


class Serializable:
	"""Base de las dataclasses del modelo: ``a_dict`` y ``de_dict`` tolerantes.

	``_CONVERSORES`` indica cómo reconstruir los campos que no son tipos
	simples (puntos, listas de elementos). El resto se ajusta al tipo de su
	valor de serie. Un campo que no se puede leer se sustituye por su valor
	de serie y se anota en el registro, en lugar de impedir abrir el entorno.
	"""

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {}

	def a_dict(self) -> dict[str, Any]:
		"""Diccionario con tipos básicos, listo para JSON."""
		datos = self.__dict__
		return {nombre: _a_basico(datos[nombre]) for nombre in _nombres_de_campos(type(self))}

	@classmethod
	def de_dict(cls, datos: Any) -> Self:
		"""Reconstruye el elemento; nunca lanza por claves que faltan, sobran o están mal."""
		objeto = cls()
		if not isinstance(datos, dict):
			log.warning("Se esperaba un diccionario para %s y llegó %s; se usan los valores de serie", cls.__name__, type(datos).__name__)
			return objeto
		conversores = cls._CONVERSORES
		for nombre in _nombres_de_campos(cls):
			if nombre not in datos:
				continue
			valor = datos[nombre]
			try:
				conversor = conversores.get(nombre)
				if conversor is not None:
					nuevo = conversor(valor)
				else:
					modelo = getattr(objeto, nombre)
					# Atajo para lo más frecuente (un número o un texto que ya es del tipo de serie): mismo resultado, sin pasar por la conversión general.
					if type(valor) is type(modelo) and (type(valor) is str or (type(valor) is float and math.isfinite(valor))):
						nuevo = valor
					else:
						nuevo = _convertir_por_tipo(valor, modelo)
			except (TypeError, ValueError) as error:
				log.warning("Valor no válido en %s.%s (%s); se usa el valor de serie", cls.__name__, nombre, error)
				continue
			setattr(objeto, nombre, nuevo)
		return objeto

	def copia(self) -> Self:
		"""Copia independiente (pasando por el diccionario, como al guardar y abrir)."""
		return type(self).de_dict(self.a_dict())


def _lista_de(clase: type[Serializable]) -> Callable[[Any], list[Any]]:
	"""Conversor para una lista de elementos de ``clase``; descarta lo que no sea diccionario."""

	def convertir(valor: Any) -> list[Any]:
		if not isinstance(valor, list):
			raise ValueError("se esperaba una lista")
		return [clase.de_dict(elemento) for elemento in valor if isinstance(elemento, dict)]

	return convertir


def _lista_textos(valor: Any) -> list[str]:
	if not isinstance(valor, list):
		raise ValueError("se esperaba una lista")
	return [str(v) for v in valor]


def _lista_enteros(valor: Any) -> list[int]:
	if not isinstance(valor, list):
		raise ValueError("se esperaba una lista")
	return [int(v) for v in valor]


def _dict_o_nada(valor: Any) -> dict[str, Any] | None:
	if valor is None:
		return None
	if not isinstance(valor, dict):
		raise ValueError("se esperaba un diccionario o nada")
	return dict(valor)


# ── Avisos (los usan colocación, catálogo y validación) ──────────────────────


@dataclass
class Aviso:
	"""Un problema encontrado, con dónde está y cómo arreglarlo.

	``gravedad`` es "error" (impide usar el entorno con garantías) o "aviso"
	(conviene revisarlo). ``codigo`` es estable y es lo que se compara en el
	código; ``mensaje`` y ``sugerencia`` son textos ya traducidos para la persona.
	"""

	gravedad: str = "aviso"
	codigo: str = ""
	mensaje: str = ""
	elemento_id: str = ""
	planta_id: str = ""
	sugerencia: str = ""

	@property
	def es_error(self) -> bool:
		"""True si el aviso es de gravedad «error»."""
		return self.gravedad == "error"

	def __str__(self) -> str:
		return f"{self.mensaje} {self.sugerencia}".strip()


def hay_errores(avisos: list[Aviso]) -> bool:
	"""True si alguno de los avisos es un error."""
	return any(aviso.es_error for aviso in avisos)


# ── Elementos ────────────────────────────────────────────────────────────────


@dataclass
class Posicion(Serializable):
	"""Un punto en una planta y hacia dónde se mira."""

	planta: str = ""
	x: float = 0.0
	y: float = 0.0
	rumbo: float = 0.0

	@property
	def punto(self) -> Punto:
		"""El punto (x, y)."""
		return self.x, self.y


def _posicion(valor: Any) -> Posicion:
	if not isinstance(valor, dict):
		raise ValueError("se esperaba una posición")
	return Posicion.de_dict(valor)


@dataclass
class Espacio(Serializable):
	"""Zona transitable con nombre: habitación, pasillo, acera, calzada, plaza…"""

	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	tipo: str = "habitacion"
	contorno: list[Punto] = field(default_factory=list)
	cerrado: bool = True
	lados_abiertos: list[int] = field(default_factory=list)
	suelo: str = "baldosa"
	acustica: str = "habitacion"
	pared_material: str = "ladrillo"
	macizo: bool = False
	datos: dict[str, Any] = field(default_factory=dict)

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {"contorno": a_puntos, "lados_abiertos": _lista_enteros}

	def lados(self) -> list[tuple[Punto, Punto]]:
		"""Lados del contorno; el lado ``i`` va del vértice ``i`` al siguiente."""
		return geo.lados(self.contorno) if len(self.contorno) >= 2 else []

	def caja(self) -> tuple[float, float, float, float]:
		"""Caja envolvente (x mín, y mín, x máx, y máx)."""
		return geo.caja(self.contorno)

	def centro(self) -> Punto:
		"""Centro de gravedad del contorno."""
		return geo.centroide(self.contorno)

	def area(self) -> float:
		"""Superficie en metros cuadrados."""
		return geo.area(self.contorno)

	def contiene(self, x: float, y: float) -> bool:
		"""True si el punto está dentro del espacio (el borde cuenta)."""
		return geo.punto_en_poligono((x, y), self.contorno)

	def __setattr__(self, nombre: str, valor: Any) -> None:
		"""Al sustituir el contorno de un espacio ya indizado, los índices espaciales dejan de valer.

		Es la única forma de que el índice de ``Planta.espacios_en`` se entere
		de que un espacio se ha movido o cambiado de forma sin que cada consulta
		tenga que revisar todos los contornos. Regla: el contorno se SUSTITUYE
		(``espacio.contorno = [...]``), como hacen todas las funciones de
		edición; si alguien lo cambia en el sitio, debe llamar a
		``invalidar_indices()``.
		"""
		if nombre == "contorno" and self.__dict__.get("_indizado"):
			invalidar_indices()
		object.__setattr__(self, nombre, valor)


# Generación de la geometría de los espacios: cambia cada vez que se sustituye
# el contorno de un espacio que algún índice tiene apuntado.
_generacion_geometria = 0


class ListaEspacios(list):
	"""La lista de espacios de una planta, que cuenta sus cambios en ``version``.

	Es una lista de verdad (``isinstance``, JSON, igualdad con otra lista): solo
	se añade el contador.

	Así el índice espacial sabe en tiempo constante si la lista ha cambiado
	(añadir, quitar, reordenar o sustituir un espacio) sin compararla entera en
	cada consulta: con miles de espacios esa comparación costaba más que la
	propia búsqueda. Para todo lo demás es una lista normal.
	"""

	version: int = 0

	def _cambio(self) -> None:
		self.version += 1

	def append(self, valor: Any) -> None:
		self._cambio()
		super().append(valor)

	def extend(self, valores: Any) -> None:
		self._cambio()
		super().extend(valores)

	def insert(self, posicion: Any, valor: Any) -> None:
		self._cambio()
		super().insert(posicion, valor)

	def remove(self, valor: Any) -> None:
		self._cambio()
		super().remove(valor)

	def pop(self, *posicion: Any) -> Any:
		self._cambio()
		return super().pop(*posicion)

	def clear(self) -> None:
		self._cambio()
		super().clear()

	def sort(self, *args: Any, **kwargs: Any) -> None:
		self._cambio()
		super().sort(*args, **kwargs)

	def reverse(self) -> None:
		self._cambio()
		super().reverse()

	def __setitem__(self, clave: Any, valor: Any) -> None:
		self._cambio()
		super().__setitem__(clave, valor)

	def __delitem__(self, clave: Any) -> None:
		self._cambio()
		super().__delitem__(clave)

	def __iadd__(self, valores: Any) -> Self:
		self._cambio()
		return super().__iadd__(valores)

	def __imul__(self, veces: Any) -> Self:
		self._cambio()
		return super().__imul__(veces)


def _lista_espacios(valor: Any) -> ListaEspacios:
	"""Conversor de ``Planta.espacios``: los espacios leídos, en una ``ListaEspacios``."""
	return ListaEspacios(_lista_de(Espacio)(valor))


_CONTORNO = operator.attrgetter("contorno")


def invalidar_indices() -> None:
	"""Da por caducados todos los índices espaciales de espacios (se rehacen en la próxima consulta)."""
	global _generacion_geometria
	_generacion_geometria += 1


class IndiceEspacios:
	"""Índice espacial de los espacios de una planta: qué espacios contienen un punto, sin mirarlos todos.

	Por qué existe: el Estudio pregunta «¿en qué espacio está esto?» por cada
	puerta, objeto y referencia al construir el árbol, al describir y al
	comprobar; con 350 espacios importados de OpenStreetMap cada clic tardaba
	diez segundos porque cada pregunta recorría todos los espacios con el punto
	en polígono. Aquí se guardan una vez la caja y la superficie de cada
	espacio y una rejilla de cajas; una consulta solo prueba los espacios cuya
	caja toca el punto. El resultado es IDÉNTICO al de la búsqueda exhaustiva
	(mismo orden: del más pequeño al más grande y, a igualdad, el orden de la lista).

	Caduca (``vigente`` devuelve False) si cambia la lista de espacios de la
	planta o se sustituye el contorno de alguno.
	"""

	# Por debajo de este número de espacios no compensa la rejilla: se miran las cajas una a una.
	MINIMO_REJILLA = 24
	# Holgura de las cajas: la tolerancia del borde de ``punto_en_poligono`` y un margen de redondeo.
	HOLGURA = 1e-5

	def __init__(self, espacios: list[Espacio]) -> None:
		from app.dominio.indice_espacial import RejillaCajas

		self.generacion = _generacion_geometria
		# La lista de la planta y su versión: si es una ``ListaEspacios`` que no ha cambiado, el índice vale sin más comprobaciones.
		self._lista = espacios
		self._version = getattr(espacios, "version", None)
		self._espacios = list(espacios)
		self._longitudes = list(map(len, map(_CONTORNO, espacios)))
		self._utiles: list[int] = []
		self._cajas: list[tuple[float, float, float, float]] = []
		self._areas: list[float] = []
		for numero, espacio in enumerate(espacios):
			object.__setattr__(espacio, "_indizado", True)
			if len(espacio.contorno) >= 3:
				self._utiles.append(numero)
				self._cajas.append(geo.caja(espacio.contorno))
				self._areas.append(espacio.area())
			else:
				self._cajas.append((0.0, 0.0, 0.0, 0.0))
				self._areas.append(0.0)
		#: Espacios de dos puntos: no tienen caja útil y no van a la rejilla, pero hay búsquedas (las aberturas) que sí los miran.
		self.lineales = [espacio for espacio in espacios if len(espacio.contorno) == 2]
		self._rejilla: RejillaCajas | None = None
		if len(self._utiles) >= self.MINIMO_REJILLA:
			x0 = min(self._cajas[i][0] for i in self._utiles)
			y0 = min(self._cajas[i][1] for i in self._utiles)
			x1 = max(self._cajas[i][2] for i in self._utiles)
			y1 = max(self._cajas[i][3] for i in self._utiles)
			# Celdas del tamaño de un espacio típico: pocas cajas por celda y pocas celdas por caja.
			celda = max(2.0, math.sqrt(max(1.0, (x1 - x0) * (y1 - y0)) / len(self._utiles)))
			self._rejilla = RejillaCajas(celda)
			for numero in self._utiles:
				self._rejilla.meter(self._cajas[numero], self.HOLGURA)
		# La rejilla numera por orden de llegada: se traduce al número de la lista de espacios.
		self._numero_de = self._utiles

	def vigente(self, espacios: list[Espacio]) -> bool:
		"""True si el índice sigue valiendo para esa lista de espacios.

		Se compara la IDENTIDAD de cada espacio (``operator.is_`` en C, unos
		microsegundos con miles de espacios): dos espacios iguales pero
		distintos, como los de un entorno recuperado al deshacer, no valen,
		porque el índice devolvería los antiguos. Las longitudes de los
		contornos descubren además un punto añadido o quitado en el sitio.
		"""
		if self.generacion != _generacion_geometria:
			return False
		if espacios is self._lista and self._version is not None and getattr(espacios, "version", None) == self._version:
			return True
		vale = (
			len(espacios) == len(self._espacios)
			and all(map(operator.is_, espacios, self._espacios, strict=True))
			and list(map(len, map(_CONTORNO, espacios))) == self._longitudes
		)
		if vale:
			self._lista = espacios
			self._version = getattr(espacios, "version", None)
		return vale

	def _candidatos(self, x: float, y: float) -> list[int]:
		"""Números (en la lista de espacios, de menor a mayor) de los espacios cuya caja toca el punto."""
		holgura = self.HOLGURA
		if self._rejilla is None:
			numeros: list[int] = self._utiles
		else:
			numeros = [self._numero_de[orden] for orden in self._rejilla.en_punto(x, y)]
		cajas = self._cajas
		return [
			numero
			for numero in numeros
			if cajas[numero][0] - holgura <= x <= cajas[numero][2] + holgura
			and cajas[numero][1] - holgura <= y <= cajas[numero][3] + holgura
		]

	def espacios_en(self, x: float, y: float) -> list[Espacio]:
		"""Espacios que contienen el punto, del más pequeño al más grande (como ``Planta.espacios_en``)."""
		espacios = self._espacios
		punto = (x, y)
		# La caja ya se ha mirado en ``_candidatos`` (con más holgura que la del borde): se salta esa parte.
		dentro = [numero for numero in self._candidatos(x, y) if geo.punto_en_poligono_sin_caja(punto, espacios[numero].contorno)]
		areas = self._areas
		dentro.sort(key=lambda numero: areas[numero])
		return [espacios[numero] for numero in dentro]

	def en_caja(self, x0: float, y0: float, x1: float, y1: float, margen: float = 0.0) -> list[Espacio]:
		"""Espacios cuya caja toca la zona ampliada en ``margen``, en el orden de la lista (solo preselecciona)."""
		ax0, ay0, ax1, ay1 = x0 - margen, y0 - margen, x1 + margen, y1 + margen
		if self._rejilla is None:
			numeros: list[int] = self._utiles
		else:
			numeros = [self._numero_de[orden] for orden in self._rejilla.en_caja(ax0, ay0, ax1, ay1)]
		cajas = self._cajas
		return [
			self._espacios[numero]
			for numero in numeros
			if cajas[numero][0] <= ax1 and ax0 <= cajas[numero][2] and cajas[numero][1] <= ay1 and ay0 <= cajas[numero][3]
		]

	def caja_de(self, espacio: Espacio) -> tuple[float, float, float, float] | None:
		"""Caja guardada de un espacio de la planta (por identidad), o None si no está o no tiene contorno."""
		for numero, candidato in enumerate(self._espacios):
			if candidato is espacio:
				return self._cajas[numero] if self._longitudes[numero] >= 3 else None
		return None


@dataclass
class Pared(Serializable):
	"""Tabique, valla o muro suelto (las paredes de las habitaciones salen de su contorno)."""

	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	a: Punto = (0.0, 0.0)
	b: Punto = (0.0, 0.0)
	grosor: float = 0.1
	material: str = "ladrillo"
	bloquea_paso: bool = True
	bloquea_sonido: bool = True
	altura: float = 2.5

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {"a": a_punto, "b": a_punto}


@dataclass
class Abertura(Serializable):
	"""Puerta, hueco, ventana o portal: el tramo que ocupa sobre una pared."""

	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	tipo: str = "puerta"
	a: Punto = (0.0, 0.0)
	b: Punto = (0.0, 0.0)
	estado: str = "cerrada"
	hoja: str = "batiente"
	material: str = "madera"
	es_salida: bool = False

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {"a": a_punto, "b": a_punto}

	@property
	def ancho(self) -> float:
		"""Anchura del hueco en metros."""
		return geo.distancia(self.a, self.b)

	def centro(self) -> Punto:
		"""Punto medio del hueco."""
		return geo.punto_medio(self.a, self.b)

	def deja_pasar(self, contar_cerradas: bool = False) -> bool:
		"""True si una persona puede cruzarla ahora.

		Con ``contar_cerradas`` una puerta cerrada también cuenta (el alumno
		puede abrirla); una puerta con llave y una ventana no cuentan nunca.
		"""
		if self.tipo == "ventana":
			return False
		if self.tipo == "hueco":
			return True
		if self.estado == "abierta":
			return True
		return contar_cerradas and self.estado == "cerrada"


@dataclass
class Tramo(Serializable):
	"""Un tramo de escalera o rampa entre dos plantas."""

	desde: Posicion = field(default_factory=Posicion)
	hasta: Posicion = field(default_factory=Posicion)
	longitud_m: float = 0.0
	peldanos: int = 0

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {"desde": _posicion, "hasta": _posicion}


@dataclass
class Parada(Serializable):
	"""Una parada de ascensor: la planta y el punto delante de su puerta."""

	planta: str = ""
	puerta: Posicion = field(default_factory=Posicion)

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {"puerta": _posicion}


@dataclass
class Conector(Serializable):
	"""Une plantas: escalera, rampa, ascensor o escalera mecánica."""

	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	tipo: str = "escalera"
	tramos: list[Tramo] = field(default_factory=list)
	paradas: list[Parada] = field(default_factory=list)
	datos: dict[str, Any] = field(default_factory=dict)

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {"tramos": _lista_de(Tramo), "paradas": _lista_de(Parada)}

	def posiciones(self) -> list[Posicion]:
		"""Todas las bocas y puertas del conector."""
		lista: list[Posicion] = []
		for tramo in self.tramos:
			lista.append(tramo.desde)
			lista.append(tramo.hasta)
		lista.extend(parada.puerta for parada in self.paradas)
		return lista

	def plantas(self) -> list[str]:
		"""Ids de las plantas que une, sin repetir y en orden de aparición."""
		vistas: list[str] = []
		for posicion in self.posiciones():
			if posicion.planta and posicion.planta not in vistas:
				vistas.append(posicion.planta)
		return vistas


@dataclass
class Objeto(Serializable):
	"""Un objeto colocado: una FORMA con medidas reales que el alumno se encuentra y esquiva."""

	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	tipo: str = "caja"
	x: float = 0.0
	y: float = 0.0
	rumbo: float = 0.0
	ancho: float = 1.0
	fondo: float = 1.0
	alto: float = 1.0
	variante: str = ""
	estado: str = ""
	datos: dict[str, Any] = field(default_factory=dict)

	def huella_caja(self) -> list[Punto]:
		"""Huella rectangular con sus medidas: la que vale cuando no hay catálogo."""
		return geo.rectangulo_girado(self.x, self.y, self.ancho, self.fondo, self.rumbo)


@dataclass
class FuenteSonido(Serializable):
	"""Sonido fijo que sirve de referencia: un frigorífico, un reloj, una fuente."""

	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	x: float = 0.0
	y: float = 0.0
	sonido: str = ""
	volumen: float = 1.0
	radio: float = 12.0
	bucle: bool = True
	intervalo: float = 0.0
	altura: float = 1.0


@dataclass
class ZonaSuelo(Serializable):
	"""Trozo de suelo distinto del resto del espacio: una alfombra, pavimento táctil."""

	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	contorno: list[Punto] = field(default_factory=list)
	suelo: str = "alfombra"

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {"contorno": a_puntos}


@dataclass
class Referencia(Serializable):
	"""Punto de interés o de referencia; ``permanente`` distingue las fijas de las pasajeras."""

	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	x: float = 0.0
	y: float = 0.0
	tipo: str = "punto"
	permanente: bool = True


@dataclass
class Via(Serializable):
	"""Eje de una calle por el que circula el tráfico (solo en plantas exteriores)."""

	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	eje: list[Punto] = field(default_factory=list)
	ancho: float = 6.0
	carriles: int = 2
	sentido: str = "doble"
	trafico: int = 1
	velocidad_kmh: float = 30.0

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {"eje": a_puntos}


# Cualquier elemento que vive dentro de una planta o del entorno.
Elemento = Espacio | Pared | Abertura | Objeto | FuenteSonido | ZonaSuelo | Referencia | Via | Conector

# Nombre de la lista de la planta que guarda cada clase, y prefijo de sus ids.
LISTA_DE_CLASE: dict[type, str] = {
	Espacio: "espacios",
	Pared: "paredes",
	Abertura: "aberturas",
	Objeto: "objetos",
	FuenteSonido: "fuentes",
	ZonaSuelo: "zonas",
	Referencia: "referencias",
	Via: "vias",
}
PREFIJO_DE_CLASE: dict[type, str] = {
	Espacio: "esp",
	Pared: "par",
	Abertura: "abe",
	Objeto: "obj",
	FuenteSonido: "fue",
	ZonaSuelo: "zon",
	Referencia: "ref",
	Via: "via",
	Conector: "con",
}


@dataclass
class Planta(Serializable):
	"""Un nivel del entorno: una planta de edificio o un plano de calle."""

	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	nivel: int = 0
	altura_m: float = 0.0
	exterior: bool = False
	espacios: list[Espacio] = field(default_factory=ListaEspacios)
	paredes: list[Pared] = field(default_factory=list)
	aberturas: list[Abertura] = field(default_factory=list)
	objetos: list[Objeto] = field(default_factory=list)
	fuentes: list[FuenteSonido] = field(default_factory=list)
	zonas: list[ZonaSuelo] = field(default_factory=list)
	referencias: list[Referencia] = field(default_factory=list)
	vias: list[Via] = field(default_factory=list)

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {
		"espacios": _lista_espacios,
		"paredes": _lista_de(Pared),
		"aberturas": _lista_de(Abertura),
		"objetos": _lista_de(Objeto),
		"fuentes": _lista_de(FuenteSonido),
		"zonas": _lista_de(ZonaSuelo),
		"referencias": _lista_de(Referencia),
		"vias": _lista_de(Via),
	}

	def elementos(self) -> Iterator[Elemento]:
		"""Todos los elementos de la planta, lista por lista."""
		for nombre in LISTA_DE_CLASE.values():
			yield from getattr(self, nombre)

	def lista_de(self, elemento: Any) -> list[Any] | None:
		"""La lista de esta planta donde vive (o viviría) un elemento de esa clase."""
		nombre = LISTA_DE_CLASE.get(type(elemento))
		return getattr(self, nombre) if nombre else None

	def espacio(self, id_espacio: str) -> Espacio | None:
		"""Espacio con ese id, o None."""
		for espacio in self.espacios:
			if espacio.id == id_espacio:
				return espacio
		return None

	def indice_espacios(self) -> IndiceEspacios:
		"""El índice espacial de los espacios de la planta, rehecho si ha caducado.

		Se guarda en la propia planta (fuera de los campos: no se guarda en el
		fichero ni cuenta al comparar plantas). Rehacerlo cuesta lo que una sola
		búsqueda exhaustiva; con él, cada consulta mira solo unos pocos espacios.
		"""
		indice: IndiceEspacios | None = self.__dict__.get("_indice_espacios")
		if indice is None or not indice.vigente(self.espacios):
			indice = IndiceEspacios(self.espacios)
			self.__dict__["_indice_espacios"] = indice
		return indice

	def espacios_en(self, x: float, y: float) -> list[Espacio]:
		"""Espacios que contienen el punto, del más pequeño al más grande (con el índice espacial)."""
		return self.indice_espacios().espacios_en(x, y)

	def espacios_en_exhaustivo(self, x: float, y: float) -> list[Espacio]:
		"""Lo mismo que ``espacios_en`` mirando todos los espacios: la referencia con la que las pruebas comparan el índice."""
		dentro = [espacio for espacio in self.espacios if len(espacio.contorno) >= 3 and espacio.contiene(x, y)]
		dentro.sort(key=lambda espacio: espacio.area())
		return dentro

	def espacio_en(self, x: float, y: float, incluir_macizos: bool = True) -> Espacio | None:
		"""Espacio en el que cae un punto.

		Si varios lo contienen (un paso de peatones sobre la calzada) gana el
		más pequeño, que es el más concreto y el que debe nombrarse al alumno.
		"""
		for espacio in self.espacios_en(x, y):
			if incluir_macizos or not espacio.macizo:
				return espacio
		return None

	def caja(self) -> tuple[float, float, float, float]:
		"""Caja envolvente de todos los espacios y paredes de la planta."""
		puntos: list[Punto] = []
		for espacio in self.espacios:
			puntos.extend(espacio.contorno)
		for pared in self.paredes:
			puntos.extend((pared.a, pared.b))
		for via in self.vias:
			puntos.extend(via.eje)
		return geo.caja(puntos)


@dataclass
class Entorno(Serializable):
	"""El documento completo: plantas, conectores entre ellas y punto de inicio."""

	formato: int = FORMATO_ACTUAL
	id: str = ""
	nombre: str = ""
	descripcion: str = ""
	autor: str = ""
	procedencia: dict[str, Any] = field(default_factory=dict)
	georef: dict[str, Any] | None = None
	inicio: Posicion = field(default_factory=Posicion)
	plantas: list[Planta] = field(default_factory=list)
	conectores: list[Conector] = field(default_factory=list)
	complementos: list[str] = field(default_factory=list)
	# Último número usado al generar ids: así un id borrado no se reutiliza nunca
	# y las actividades que lo nombraban no acaban apuntando a otro elemento.
	contador_ids: int = 0

	_CONVERSORES: ClassVar[dict[str, Callable[[Any], Any]]] = {
		"georef": _dict_o_nada,
		"inicio": _posicion,
		"plantas": _lista_de(Planta),
		"conectores": _lista_de(Conector),
		"complementos": _lista_textos,
	}

	# ── Búsquedas ──

	def planta(self, id_planta: str) -> Planta | None:
		"""Planta con ese id, o None."""
		for planta in self.plantas:
			if planta.id == id_planta:
				return planta
		return None

	def planta_de_nivel(self, nivel: int) -> Planta | None:
		"""Primera planta con ese nivel, o None."""
		for planta in self.plantas:
			if planta.nivel == nivel:
				return planta
		return None

	def elementos(self) -> Iterator[tuple[Planta | None, Elemento]]:
		"""Pares (planta, elemento) de todo el entorno; los conectores van con planta None."""
		for planta in self.plantas:
			for elemento in planta.elementos():
				yield planta, elemento
		for conector in self.conectores:
			yield None, conector

	def buscar(self, id_elemento: str) -> tuple[Planta | None, Any] | None:
		"""(planta, elemento) del elemento con ese id; None si no existe.

		Para una planta devuelve (planta, planta); para un conector, (None, conector).
		"""
		if not id_elemento:
			return None
		for planta in self.plantas:
			if planta.id == id_elemento:
				return planta, planta
		for planta, elemento in self.elementos():
			if elemento.id == id_elemento:
				return planta, elemento
		return None

	def elemento(self, id_elemento: str) -> Any | None:
		"""Solo el elemento con ese id, o None."""
		encontrado = self.buscar(id_elemento)
		return encontrado[1] if encontrado else None

	def planta_de(self, elemento: Any) -> Planta | None:
		"""Planta que contiene ese elemento (por identidad), o None."""
		for planta in self.plantas:
			if elemento is planta:
				return planta
			lista = planta.lista_de(elemento)
			if lista is not None and any(candidato is elemento for candidato in lista):
				return planta
		return None

	def ids(self) -> list[str]:
		"""Todos los ids en uso (plantas y elementos), con repeticiones si las hay."""
		lista = [planta.id for planta in self.plantas]
		lista.extend(elemento.id for _planta, elemento in self.elementos())
		return lista

	# ── Ids ──

	def nuevo_id(self, prefijo: str) -> str:
		"""Genera un id único y estable del tipo ``esp-12``.

		El número sale de un contador que se guarda con el entorno y solo
		crece: los ids son cortos y legibles, y no se repiten aunque se borren
		elementos o se abran entornos hechos a mano con ids parecidos.
		"""
		en_uso = set(self.ids())
		# Lo mismo que buscar «-(\d+)$» en cada id, sin expresión regular: con un barrio de miles de
		# elementos se llama en cada inserción y la expresión era lo que más tardaba.
		for existente in en_uso:
			_cabeza, guion, cola = existente.rpartition("-")
			if guion and cola.isascii() and cola.isdigit():
				numero = int(cola)
				if numero > self.contador_ids:
					self.contador_ids = numero
		while True:
			self.contador_ids += 1
			candidato = f"{prefijo}-{self.contador_ids}"
			if candidato not in en_uso:
				return candidato

	def id_para(self, elemento: Any) -> str:
		"""Id nuevo con el prefijo que corresponde a la clase del elemento."""
		if isinstance(elemento, Planta):
			return self.nuevo_id("pla")
		return self.nuevo_id(PREFIJO_DE_CLASE.get(type(elemento), "ele"))


# ── Paredes derivadas ────────────────────────────────────────────────────────


class Segmento(NamedTuple):
	"""Un tramo que corta el paso o el sonido, con de dónde sale.

	``clase``: pared (lado de una habitación o pared suelta), puerta, ventana,
	macizo (contorno de un edificio) u objeto. ``atenuacion`` va de 0 (no
	quita nada de sonido) a 1 (lo tapa del todo).
	"""

	a: Punto
	b: Punto
	elemento_id: str
	clase: str
	material: str
	atenuacion: float = 1.0


# Cuánto sonido quitan una puerta cerrada y una ventana (el resto de paredes, todo).
ATENUACION_PUERTA = 0.6
ATENUACION_VENTANA = 0.5


def aberturas_sobre(planta: Planta, a: Punto, b: Punto, candidatas: list[Abertura] | None = None) -> list[tuple[Abertura, float, float]]:
	"""Aberturas que caen sobre el segmento ab, con el tramo (metros desde ``a``) que ocupan.

	``candidatas`` (en el orden de ``planta.aberturas``) evita mirar todas: la
	preselección de una rejilla. Sin ella se miran todas las de la planta.
	"""
	resultado: list[tuple[Abertura, float, float]] = []
	for abertura in planta.aberturas if candidatas is None else candidatas:
		intervalo = geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, TOLERANCIA_PARED)
		if intervalo is not None:
			resultado.append((abertura, intervalo[0], intervalo[1]))
	return resultado


class _RejillaAberturas:
	"""Preselección de las aberturas cercanas a un segmento (para no cruzar cada lado con todas las puertas).

	Una abertura solo puede estar sobre un lado si alguno de sus puntos queda a
	menos de ``TOLERANCIA_PARED`` del lado: basta con que las cajas, ampliadas
	en esa tolerancia, se toquen. Devuelve las candidatas en el orden de la
	planta, así que el resultado de ``aberturas_sobre`` no cambia.
	"""

	def __init__(self, aberturas: list[Abertura]) -> None:
		from app.dominio.indice_espacial import RejillaCajas

		self._aberturas = aberturas
		self._rejilla = RejillaCajas(4.0)
		for abertura in aberturas:
			self._rejilla.meter(geo.caja((abertura.a, abertura.b)), TOLERANCIA_PARED + 1e-6)

	def cerca(self, a: Punto, b: Punto) -> list[Abertura]:
		"""Aberturas cuya caja ampliada toca la del segmento ab, en el orden de la planta."""
		x0, y0, x1, y1 = geo.caja((a, b))
		return [self._aberturas[numero] for numero in self._rejilla.en_caja(x0, y0, x1, y1)]


def _clave_segmento(a: Punto, b: Punto) -> tuple[Punto, Punto]:
	"""Clave que iguala un segmento con su inverso y absorbe el ruido de redondeo."""
	p = (round(a[0], 3), round(a[1], 3))
	q = (round(b[0], 3), round(b[1], 3))
	return (p, q) if p <= q else (q, p)


def _paredes_derivadas(planta: Planta) -> list[tuple[Punto, Punto, str, str, bool, bool]]:
	"""Lados que hacen de pared, ya sin los huecos de las aberturas.

	Cada uno es (a, b, id de origen, material, tapa el sonido, corta el paso).
	Los lados compartidos por dos habitaciones adosadas salen una sola vez.
	"""
	brutos: list[tuple[Punto, Punto, str, str, bool, bool]] = []
	for espacio in planta.espacios:
		if len(espacio.contorno) < 3 or espacio.macizo or not espacio.cerrado:
			continue
		for indice, (a, b) in enumerate(espacio.lados()):
			if indice not in espacio.lados_abiertos:
				brutos.append((a, b, espacio.id, espacio.pared_material, True, True))
	for pared in planta.paredes:
		brutos.append((pared.a, pared.b, pared.id, pared.material, pared.bloquea_sonido, pared.bloquea_paso))
	resultado: list[tuple[Punto, Punto, str, str, bool, bool]] = []
	vistos: set[tuple[Punto, Punto]] = set()
	rejilla = _RejillaAberturas(planta.aberturas)
	for a, b, id_origen, material, tapa_sonido, tapa_paso in brutos:
		huecos = [(inicio, fin) for _abertura, inicio, fin in aberturas_sobre(planta, a, b, rejilla.cerca(a, b))]
		for p, q in geo.recortar_segmento(a, b, huecos):
			clave = _clave_segmento(p, q)
			if clave in vistos:
				continue
			vistos.add(clave)
			resultado.append((p, q, id_origen, material, tapa_sonido, tapa_paso))
	return resultado


def _abertura_sobre_alguna_pared(planta: Planta, abertura: Abertura, indice: IndiceEspacios | None = None) -> bool:
	"""True si la abertura está sobre un lado con pared de un espacio cerrado o sobre una pared suelta.

	Solo se miran los espacios cuya caja toca la de la abertura (con la
	tolerancia de pared): una abertura lejos de un espacio no puede estar
	sobre ninguno de sus lados. Antes se cruzaba cada abertura con todos los
	lados de la planta, y con miles de espacios eran segundos.
	"""
	x0, y0, x1, y1 = geo.caja((abertura.a, abertura.b))
	cercanos = (indice or planta.indice_espacios()).en_caja(x0, y0, x1, y1, TOLERANCIA_PARED + 1e-6)
	for espacio in cercanos:
		if len(espacio.contorno) < 3 or espacio.macizo or not espacio.cerrado:
			continue
		for indice, (a, b) in enumerate(espacio.lados()):
			if indice in espacio.lados_abiertos:
				continue
			if geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, TOLERANCIA_PARED) is not None:
				return True
	for pared in planta.paredes:
		if geo.intervalo_sobre_segmento(pared.a, pared.b, abertura.a, abertura.b, TOLERANCIA_PARED) is not None:
			return True
	return False


def segmentos_solidos(planta: Planta, catalogo: Catalogo | None = None, incluir_puertas_cerradas: bool = True) -> list[Segmento]:
	"""Segmentos que cortan el paso en una planta.

	Salen de: los lados de los espacios cerrados (menos los ``lados_abiertos``
	y menos los tramos de sus aberturas), las paredes sueltas que bloquean el
	paso, las ventanas, las puertas cerradas (si ``incluir_puertas_cerradas``;
	las que tienen llave, siempre) y el contorno de los espacios macizos, que
	no se recorta: el portal de un edificio macizo es una referencia, no una entrada.

	Con ``catalogo`` se añaden además las huellas de los objetos que cortan
	el paso. Sin él los objetos no se incluyen (el motor los trata aparte).
	"""
	segmentos: list[Segmento] = []
	for a, b, id_origen, material, _tapa_sonido, tapa_paso in _paredes_derivadas(planta):
		if not tapa_paso:
			continue
		segmentos.append(Segmento(a, b, id_origen, "pared", material, 1.0))
	indice = planta.indice_espacios()
	for abertura in planta.aberturas:
		if not _abertura_sobre_alguna_pared(planta, abertura, indice):
			continue
		if abertura.tipo == "ventana":
			segmentos.append(Segmento(abertura.a, abertura.b, abertura.id, "ventana", abertura.material, ATENUACION_VENTANA))
		elif abertura.tipo != "hueco" and (abertura.estado == "con_llave" or (abertura.estado == "cerrada" and incluir_puertas_cerradas)):
			segmentos.append(Segmento(abertura.a, abertura.b, abertura.id, "puerta", abertura.material, ATENUACION_PUERTA))
	for espacio in planta.espacios:
		if espacio.macizo and len(espacio.contorno) >= 3:
			for a, b in espacio.lados():
				segmentos.append(Segmento(a, b, espacio.id, "macizo", espacio.pared_material, 1.0))
	if catalogo is not None:
		for objeto in planta.objetos:
			if not catalogo.bloquea(objeto):
				continue
			for a, b in geo.lados(catalogo.huella(objeto)):
				segmentos.append(Segmento(a, b, objeto.id, "objeto", catalogo.material(objeto), 0.0))
	return segmentos


def segmentos_opacos(planta: Planta) -> list[Segmento]:
	"""Segmentos que tapan el sonido en una planta.

	Como los sólidos, pero pensando en el oído: las paredes sueltas con
	``bloquea_sonido`` falso (una valla, un cristal bajo) no cuentan, una
	puerta cerrada y una ventana dejan pasar parte (ver ``atenuacion``) y una
	puerta abierta o un hueco no tapan nada.
	"""
	segmentos: list[Segmento] = []
	for a, b, id_origen, material, tapa_sonido, _tapa_paso in _paredes_derivadas(planta):
		if tapa_sonido:
			segmentos.append(Segmento(a, b, id_origen, "pared", material, 1.0))
	indice = planta.indice_espacios()
	for abertura in planta.aberturas:
		if not _abertura_sobre_alguna_pared(planta, abertura, indice):
			continue
		if abertura.tipo == "ventana":
			segmentos.append(Segmento(abertura.a, abertura.b, abertura.id, "ventana", abertura.material, ATENUACION_VENTANA))
		elif abertura.tipo != "hueco" and abertura.estado != "abierta":
			segmentos.append(Segmento(abertura.a, abertura.b, abertura.id, "puerta", abertura.material, ATENUACION_PUERTA))
	for espacio in planta.espacios:
		if espacio.macizo and len(espacio.contorno) >= 3:
			for a, b in espacio.lados():
				segmentos.append(Segmento(a, b, espacio.id, "macizo", espacio.pared_material, 1.0))
	return segmentos
