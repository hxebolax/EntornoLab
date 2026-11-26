"""Protocolo de supervisión: una línea JSON por mensaje, con validación estricta.

Sobre de todos los mensajes::

	{"v": 1, "tipo": "estado", "seq": 42, "t": 12.5, "datos": {...}}

- ``v``: versión del protocolo (``VERSION``).
- ``tipo``: uno de los tipos conocidos para el sentido en que viaja.
- ``seq``: contador del emisor, empieza en 0 en cada conexión.
- ``t``: segundos desde que el emisor abrió la conexión (su reloj monótono).
- ``datos``: campos propios del tipo.

Por qué validar tanto: lo que llega por la red no es de fiar aunque venga
de un reproductor legítimo (otra versión, un fallo, alguien curioseando en
la red del centro). Un mensaje mal formado se RECHAZA con ``ErrorProtocolo``
y quien lo recibe decide; nunca tumba la conexión por sí solo ni llega a la
interfaz con tipos inesperados. Los campos desconocidos de ``datos`` se
descartan (compatibilidad hacia delante dentro de la misma versión); los
conocidos deben tener el tipo y el tamaño exactos.

Este módulo no abre conexiones: solo codifica, decodifica y trocea líneas.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from typing import Any

VERSION = 1
PUERTO_SALA = 47900
PUERTO_DESCUBRIMIENTO = 47901

# Tamaño máximo de una línea, con su salto. Un estado ocupa menos de 1 KiB.
MAX_LINEA = 32 * 1024

# Sentidos en que viaja un mensaje.
A_ESTUDIO = "a_estudio"
A_JUGAR = "a_jugar"

# Órdenes que el Estudio puede enviar a un reproductor con ``Sala.pedir``.
ORDENES: tuple[str, ...] = (
	"pausa",
	"reanudar",
	"recolocar",
	"mensaje",
	"pista",
	"ayudas",
	"premio",
	"marca",
	"reiniciar",
	"terminar",
	"alumno",
	"releer_configuracion",
)

# Orden «alumno»: lo que la ficha del Estudio dice del alumno, sin datos personales.
# Claves de ``ajustes`` y su regla: (clase, mínimo, máximo) o (clase, valores admitidos).
# Los rangos son los de ``AjustesJuego`` del motor (los que acepta la ficha).
AJUSTES_ALUMNO: dict[str, tuple[str, Any, Any]] = {
	"modo_movimiento": ("opcion", ("pasos", "continuo", "brujula", "salas", "aceras"), None),
	"paso_m": ("numero", 0.25, 1.5),
	"giro_grados": ("numero", 0.0, 180.0),
	"velocidad_ms": ("numero", 0.3, 3.0),
	"formato_direccion": ("opcion", ("reloj", "lados", "cardinal", "grados"), None),
	"unidad": ("opcion", ("metros", "pasos"), None),
	"estilo": ("opcion", ("infantil", "juvenil", "adulto"), None),
	"detalle": ("entero", 0, 3),
}
# Campos de cada entrada de la lista de trabajo (todos texto) y sus longitudes máximas.
CAMPOS_LISTA: dict[str, int] = {"entorno_id": 100, "entorno_nombre": 200, "actividad_id": 100, "actividad_nombre": 200, "paquete": 200}
LISTA_MAXIMA = 60
NIVELES_MAXIMOS = 200
NIVEL_MAXIMO = 99

# Peticiones del modo recorrido (reproductor -> Estudio).
ACCIONES_PETICION: tuple[str, ...] = ("colocar_aqui", "marcar_punto", "medir_desde_aqui")

# Motivos de ``rechazo``.
MOTIVOS_RECHAZO: tuple[str, ...] = ("codigo", "bloqueado", "version", "lleno", "protocolo", "expulsado", "cierre")

# Límites de los diccionarios libres (contadores, datos de un evento...).
_PROFUNDIDAD_MAXIMA = 4
_NODOS_MAXIMOS = 300
_TEXTO_LIBRE_MAXIMO = 2000
_CLAVE_MAXIMA = 64
_COORDENADA_MAXIMA = 1.0e7


class ErrorProtocolo(ValueError):
	"""Mensaje que no cumple el protocolo.

	``codigo`` es estable y no contiene datos del mensaje (se puede
	registrar): ``tamano``, ``json``, ``sobre``, ``version``, ``tipo``, ``campo``.
	"""

	def __init__(self, codigo: str, detalle: str = "") -> None:
		super().__init__(f"{codigo}: {detalle}" if detalle else codigo)
		self.codigo = codigo
		self.detalle = detalle


@dataclass(frozen=True)
class Mensaje:
	"""Un mensaje ya validado."""

	tipo: str
	datos: dict[str, Any]
	seq: int = 0
	t: float = 0.0
	v: int = VERSION


@dataclass(frozen=True)
class Campo:
	"""Regla de un campo de ``datos``.

	:param clase: ``"texto"``, ``"numero"``, ``"entero"``, ``"logico"``, ``"dic"`` o ``"lista"`` (de valores libres acotados).
	:param obligatorio: si falta, el mensaje se rechaza.
	:param maximo: longitud máxima (texto) o valor absoluto máximo (números).
	:param valores: lista cerrada de valores admitidos (texto).
	:param nulo: admite ``null``.
	"""

	clase: str
	obligatorio: bool = False
	maximo: float | None = None
	valores: tuple[str, ...] | None = None
	nulo: bool = False


def _texto(maximo: int, obligatorio: bool = False) -> Campo:
	return Campo("texto", obligatorio, maximo)


_NUMERO = Campo("numero", maximo=_COORDENADA_MAXIMA)
_LOGICO = Campo("logico")
_DIC = Campo("dic")

# Esquema de cada tipo de mensaje, por sentido.
ESQUEMAS: dict[str, dict[str, dict[str, Campo]]] = {
	A_ESTUDIO: {
		"hola": {
			"alias": _texto(60, True),
			"instancia": _texto(64),
			"nonce": _texto(64, True),
			"prueba": _texto(128, True),
			"entorno": _texto(200),
			"actividad": _texto(200),
			"modo": _texto(20),
			"recorrido": _LOGICO,
			"version_app": _texto(40),
		},
		"estado": {
			"planta": _texto(100),
			"x": _NUMERO,
			"y": _NUMERO,
			"rumbo": _NUMERO,
			"espacio": _texto(200),
			"descripcion": _texto(500),
			"delante": _texto(500),
			"pausado": _LOGICO,
			"tiempo_activo": _NUMERO,
			"contadores": _DIC,
			"entorno": _texto(200),
			"actividad": _texto(200),
			"modo": _texto(20),
		},
		"evento": {"tipo": _texto(40, True), "datos": _DIC},
		"voz": {"texto": _texto(2000, True), "canal": _texto(20)},
		"fin": {"completada": _LOGICO, "resultado": _DIC},
		"latido": {},
		"peticion": {
			"id": Campo("entero", True, 2**31),
			"accion": Campo("texto", True, 40, ACCIONES_PETICION),
			"planta": _texto(100),
			"x": _NUMERO,
			"y": _NUMERO,
			"rumbo": _NUMERO,
			"datos": _DIC,
		},
	},
	A_JUGAR: {
		"reto": {"nonce": _texto(64, True), "nombre": _texto(100)},
		"bienvenida": {"prueba": _texto(128, True), "alumno": _texto(80), "nombre": _texto(100), "latido_s": Campo("numero", maximo=3600)},
		"rechazo": {"motivo": Campo("texto", True, 20, MOTIVOS_RECHAZO), "espera_s": Campo("numero", maximo=86400)},
		"pausa": {},
		"reanudar": {},
		"recolocar": {
			"planta": _texto(100, True),
			"x": Campo("numero", True, _COORDENADA_MAXIMA),
			"y": Campo("numero", True, _COORDENADA_MAXIMA),
			"rumbo": Campo("numero", maximo=_COORDENADA_MAXIMA, nulo=True),
		},
		"mensaje": {"texto": _texto(1000, True)},
		"pista": {"texto": _texto(1000), "baliza_s": Campo("numero", maximo=600), "destino": _texto(200)},
		"ayudas": {"ayudas": Campo("dic", True)},
		"premio": {
			"id": _texto(100),
			"nombre": _texto(200, True),
			"planta": _texto(100),
			"x": _NUMERO,
			"y": _NUMERO,
			"sonido": _texto(200),
			"mensaje": _texto(1000),
			"visibilidad": _texto(20),
		},
		"marca": {"texto": _texto(2000)},
		"reiniciar": {},
		"terminar": {},
		# La ficha del alumno (ajustes de juego, lista de trabajo y niveles); se revisa a fondo en ``_validar_alumno``.
		"alumno": {"ajustes": _DIC, "lista": Campo("lista"), "niveles": _DIC},
		# El Estudio ha cambiado preferencias que el reproductor comparte (config.json): que las vuelva a leer.
		"releer_configuracion": {},
		"respuesta": {"id": Campo("entero", True, 2**31), "aceptada": Campo("logico", True), "texto": _texto(1000), "datos": _DIC},
		# «visto»: seq del último mensaje del reproductor que la sala ha tratado (acuse de recibo).
		"latido": {"visto": Campo("entero", maximo=2**53)},
	},
}


def _es_numero(valor: Any) -> bool:
	return isinstance(valor, (int, float)) and not isinstance(valor, bool) and math.isfinite(valor)


def _validar_libre(valor: Any, profundidad: int, cuenta: list[int]) -> None:
	"""Comprueba un valor JSON libre: profundidad, número de nodos y tamaño de textos acotados."""
	cuenta[0] += 1
	if cuenta[0] > _NODOS_MAXIMOS:
		raise ErrorProtocolo("campo", "demasiados elementos")
	if valor is None or isinstance(valor, bool):
		return
	if isinstance(valor, (int, float)):
		if not math.isfinite(valor) or abs(valor) > 1.0e15:
			raise ErrorProtocolo("campo", "número fuera de rango")
		return
	if isinstance(valor, str):
		if len(valor) > _TEXTO_LIBRE_MAXIMO:
			raise ErrorProtocolo("campo", "texto demasiado largo")
		return
	if profundidad >= _PROFUNDIDAD_MAXIMA:
		raise ErrorProtocolo("campo", "demasiados niveles")
	if isinstance(valor, list):
		for elemento in valor:
			_validar_libre(elemento, profundidad + 1, cuenta)
		return
	if isinstance(valor, dict):
		for clave, elemento in valor.items():
			if not isinstance(clave, str) or len(clave) > _CLAVE_MAXIMA:
				raise ErrorProtocolo("campo", "clave no válida")
			_validar_libre(elemento, profundidad + 1, cuenta)
		return
	raise ErrorProtocolo("campo", "tipo de dato no admitido")


def _validar_campo(nombre: str, valor: Any, regla: Campo) -> Any:
	if valor is None:
		if regla.nulo:
			return None
		raise ErrorProtocolo("campo", f"{nombre} no puede ser nulo")
	if regla.clase == "texto":
		if not isinstance(valor, str):
			raise ErrorProtocolo("campo", f"{nombre} debe ser texto")
		if regla.maximo is not None and len(valor) > regla.maximo:
			raise ErrorProtocolo("campo", f"{nombre} es demasiado largo")
		if regla.valores is not None and valor not in regla.valores:
			raise ErrorProtocolo("campo", f"{nombre} tiene un valor desconocido")
		return valor
	if regla.clase == "logico":
		if not isinstance(valor, bool):
			raise ErrorProtocolo("campo", f"{nombre} debe ser verdadero o falso")
		return valor
	if regla.clase == "entero":
		if isinstance(valor, bool) or not isinstance(valor, int):
			raise ErrorProtocolo("campo", f"{nombre} debe ser un entero")
		if valor < 0 or (regla.maximo is not None and valor > regla.maximo):
			raise ErrorProtocolo("campo", f"{nombre} está fuera de rango")
		return valor
	if regla.clase == "numero":
		if not _es_numero(valor):
			raise ErrorProtocolo("campo", f"{nombre} debe ser un número")
		if regla.maximo is not None and abs(valor) > regla.maximo:
			raise ErrorProtocolo("campo", f"{nombre} está fuera de rango")
		return valor
	if regla.clase == "dic":
		if not isinstance(valor, dict):
			raise ErrorProtocolo("campo", f"{nombre} debe ser un diccionario")
		_validar_libre(valor, 0, [0])
		return valor
	if regla.clase == "lista":
		if not isinstance(valor, list):
			raise ErrorProtocolo("campo", f"{nombre} debe ser una lista")
		# Una lista puede llevar muchas entradas pequeñas: cada una se acota por separado, y el total por la línea.
		if len(valor) > _NODOS_MAXIMOS:
			raise ErrorProtocolo("campo", f"{nombre} tiene demasiados elementos")
		for elemento in valor:
			_validar_libre(elemento, 1, [0])
		return valor
	raise ErrorProtocolo("campo", f"regla desconocida para {nombre}")


def _validar_alumno(datos: dict[str, Any]) -> dict[str, Any]:
	"""Revisa a fondo la orden ``alumno``: tipos y rangos de cada ajuste, forma de la lista y de los niveles.

	Lo que llega aquí acaba en las preferencias de juego del alumno y en su
	perfil: un valor fuera de rango no se «arregla» en silencio, se rechaza
	el mensaje entero (es un fallo del emisor y debe verse). Las claves de
	``ajustes`` que no se conocen se descartan (compatibilidad hacia delante).
	"""
	limpio: dict[str, Any] = {}
	if "ajustes" in datos:
		ajustes: dict[str, Any] = {}
		for clave, valor in datos["ajustes"].items():
			regla = AJUSTES_ALUMNO.get(clave)
			if regla is None:
				continue
			clase, primero, segundo = regla
			if clase == "opcion":
				if not isinstance(valor, str) or valor not in primero:
					raise ErrorProtocolo("campo", f"ajustes.{clave} tiene un valor desconocido")
			elif clase == "entero":
				if isinstance(valor, bool) or not isinstance(valor, int) or not primero <= valor <= segundo:
					raise ErrorProtocolo("campo", f"ajustes.{clave} está fuera de rango")
			elif not _es_numero(valor) or not primero <= valor <= segundo:
				raise ErrorProtocolo("campo", f"ajustes.{clave} está fuera de rango")
			ajustes[clave] = valor
		limpio["ajustes"] = ajustes
	if "lista" in datos:
		lista = datos["lista"]
		if len(lista) > LISTA_MAXIMA:
			raise ErrorProtocolo("campo", "la lista de trabajo es demasiado larga")
		entradas: list[dict[str, str]] = []
		for entrada in lista:
			if not isinstance(entrada, dict):
				raise ErrorProtocolo("campo", "una entrada de la lista de trabajo no es un diccionario")
			limpia: dict[str, str] = {}
			for campo, maximo in CAMPOS_LISTA.items():
				valor = entrada.get(campo, "")
				if not isinstance(valor, str) or len(valor) > maximo:
					raise ErrorProtocolo("campo", f"lista.{campo} no es válido")
				limpia[campo] = valor
			if not limpia["actividad_id"]:
				raise ErrorProtocolo("campo", "falta lista.actividad_id")
			entradas.append(limpia)
		limpio["lista"] = entradas
	if "niveles" in datos:
		niveles = datos["niveles"]
		if len(niveles) > NIVELES_MAXIMOS:
			raise ErrorProtocolo("campo", "demasiados niveles")
		for clave, nivel in niveles.items():
			if "/" not in clave or isinstance(nivel, bool) or not isinstance(nivel, int) or not 0 <= nivel <= NIVEL_MAXIMO:
				raise ErrorProtocolo("campo", "niveles no es válido")
		limpio["niveles"] = dict(niveles)
	return limpio


# Revisión extra de algunos mensajes, después de la de sus campos.
_REVISIONES: dict[tuple[str, str], Any] = {(A_JUGAR, "alumno"): _validar_alumno}


def validar(tipo: str, datos: Any, sentido: str) -> dict[str, Any]:
	"""Valida los datos de un tipo de mensaje y devuelve solo los campos conocidos."""
	esquemas = ESQUEMAS.get(sentido)
	if esquemas is None:
		raise ValueError(f"sentido desconocido: {sentido}")
	if not isinstance(tipo, str) or tipo not in esquemas:
		raise ErrorProtocolo("tipo", "tipo de mensaje desconocido")
	if not isinstance(datos, dict):
		raise ErrorProtocolo("sobre", "datos debe ser un diccionario")
	limpio: dict[str, Any] = {}
	for nombre, regla in esquemas[tipo].items():
		if nombre not in datos:
			if regla.obligatorio:
				raise ErrorProtocolo("campo", f"falta {nombre}")
			continue
		limpio[nombre] = _validar_campo(nombre, datos[nombre], regla)
	revision = _REVISIONES.get((sentido, tipo))
	if revision is not None:
		limpio = revision(limpio)
	return limpio


def filtrar(tipo: str, datos: dict[str, Any], sentido: str) -> tuple[dict[str, Any], list[str]]:
	"""Se queda con los campos válidos de ``datos`` y dice cuáles ha descartado por no serlo.

	Para el ``estado`` del reproductor: llega del motor cinco veces por
	segundo y un campo con un tipo inesperado (un ``None``, por ejemplo) no
	debe dejar al profesional sin el resto del estado.
	"""
	reglas = ESQUEMAS[sentido][tipo]
	limpio: dict[str, Any] = {}
	descartados: list[str] = []
	for nombre, regla in reglas.items():
		if nombre not in datos:
			continue
		try:
			limpio[nombre] = _validar_campo(nombre, datos[nombre], regla)
		except ErrorProtocolo:
			descartados.append(nombre)
	return limpio, descartados


def codificar(tipo: str, datos: dict[str, Any] | None = None, *, sentido: str, seq: int = 0, t: float = 0.0) -> bytes:
	"""Devuelve la línea (con su salto) de un mensaje, validándolo antes de enviarlo.

	Validar también lo que sale evita que un fallo propio llegue al otro
	lado como «mensaje mal formado» difícil de rastrear.
	"""
	limpio = validar(tipo, datos or {}, sentido)
	sobre = {"v": VERSION, "tipo": tipo, "seq": int(seq), "t": round(float(t), 3), "datos": limpio}
	try:
		linea = json.dumps(sobre, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8") + b"\n"
	except (TypeError, ValueError) as error:
		raise ErrorProtocolo("campo", "datos no serializables") from error
	if len(linea) > MAX_LINEA:
		raise ErrorProtocolo("tamano", "mensaje demasiado grande")
	return linea


def _constante_prohibida(nombre: str) -> float:
	raise ValueError(f"constante no admitida: {nombre}")


def decodificar(linea: bytes | str, sentido: str) -> Mensaje:
	"""Convierte una línea recibida en un ``Mensaje`` validado, o lanza ``ErrorProtocolo``."""
	if isinstance(linea, str):
		linea = linea.encode("utf-8")
	if len(linea) > MAX_LINEA:
		raise ErrorProtocolo("tamano", "línea demasiado larga")
	try:
		sobre = json.loads(linea.decode("utf-8"), parse_constant=_constante_prohibida)
	except (ValueError, RecursionError) as error:
		raise ErrorProtocolo("json", "no es JSON válido") from error
	if not isinstance(sobre, dict):
		raise ErrorProtocolo("sobre", "el mensaje no es un objeto")
	version = sobre.get("v")
	if isinstance(version, bool) or not isinstance(version, int):
		raise ErrorProtocolo("sobre", "falta la versión")
	if version != VERSION:
		raise ErrorProtocolo("version", "versión de protocolo distinta")
	seq = sobre.get("seq", 0)
	if isinstance(seq, bool) or not isinstance(seq, int) or seq < 0 or seq > 2**53:
		raise ErrorProtocolo("sobre", "seq no válido")
	t = sobre.get("t", 0.0)
	if not _es_numero(t) or abs(t) > 1.0e9:
		raise ErrorProtocolo("sobre", "t no válido")
	tipo = sobre.get("tipo")
	datos = validar(tipo, sobre.get("datos", {}), sentido)
	return Mensaje(tipo=tipo, datos=datos, seq=seq, t=float(t), v=version)


class LectorLineas:
	"""Trocea en líneas lo que llega por la conexión, con tamaño acotado.

	Si una línea supera ``MAX_LINEA`` se descarta ENTERA (hasta su salto) y
	se entrega ``None`` en su lugar: quien lee cuenta un error y sigue con la
	siguiente línea, sin cortar la conexión ni guardar megas en memoria.
	"""

	def __init__(self, maximo: int = MAX_LINEA) -> None:
		self._maximo = maximo
		self._resto = bytearray()
		self._descartando = False

	def alimentar(self, datos: bytes) -> list[bytes | None]:
		"""Añade octetos recibidos y devuelve las líneas completas (sin el salto)."""
		lineas: list[bytes | None] = []
		self._resto.extend(datos)
		while True:
			corte = self._resto.find(b"\n")
			if corte < 0:
				if len(self._resto) > self._maximo:
					# Línea desmesurada sin terminar: se tira lo recibido y se espera a su salto.
					self._resto.clear()
					if not self._descartando:
						self._descartando = True
						lineas.append(None)
				return lineas
			linea = bytes(self._resto[:corte])
			del self._resto[: corte + 1]
			if self._descartando:
				# Fin de la línea desmesurada: ya se avisó al empezar a descartarla.
				self._descartando = False
				continue
			if len(linea) + 1 > self._maximo:
				lineas.append(None)
				continue
			if linea.strip():
				lineas.append(linea)
