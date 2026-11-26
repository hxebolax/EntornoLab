"""Crear un complemento propio sin programar: la lógica, sin wx.

El asistente del Estudio (``app/ui/asistente_complemento.py``) solo pregunta;
lo que hace con las respuestas está aquí para poder probarlo sin ventanas:

- pasar los valores de un formulario a la ficha de un objeto (y al revés,
  para volver a editarlo);
- componer el ``complemento.json`` entero;
- dibujar la miniatura de cada objeto: su HUELLA en planta, con su letra y
  su color, como PNG escrito con la biblioteca estándar (sin wx ni PIL);
- guardar el complemento en ``data/plugins/<id>`` y empaquetarlo en un
  ``.elabc`` para compartirlo.

Un complemento es solo datos: nada de lo que se escribe aquí se ejecuta.
"""

from __future__ import annotations

import json
import logging
import os
import struct
import wave
import zlib
from collections.abc import Sequence
from pathlib import Path
from typing import Any

from app.core import paths
from app.core.i18n import N_, _
from app.dominio import geometria as geo
from app.dominio.catalogo import (
	AMBITOS,
	COLOCACIONES,
	FORMATO_COMPLEMENTO,
	NOMBRE_FICHA,
	DefObjeto,
	empaquetar_complemento,
	sin_acentos,
	validar_complemento,
)
from app.dominio.formato import identificador_seguro
from app.dominio.modelo import Aviso
from app.ui.esquemas import Campo, ErrorCampo, c, leer_numero, opciones_de, texto_numero

log = logging.getLogger(__name__)

Punto = tuple[float, float]

FORMAS: dict[str, str] = {
	"rectangulo": N_("Rectángulo"),
	"circulo": N_("Círculo o elipse"),
	"ele": N_("En ele"),
	"poligono": N_("Polígono por puntos"),
}

MATERIALES: dict[str, str] = {
	"madera": N_("Madera"),
	"metal": N_("Metal"),
	"cristal": N_("Cristal"),
	"plastico": N_("Plástico"),
	"tela": N_("Tela"),
	"piedra": N_("Piedra"),
	"ladrillo": N_("Ladrillo"),
}

#: Colores con NOMBRE para el símbolo: quien no ve el color lo elige igual.
COLORES: dict[str, str] = {
	"#8B5A2B": N_("Marrón"),
	"#808080": N_("Gris"),
	"#1F4E9C": N_("Azul"),
	"#2E7D32": N_("Verde"),
	"#C62828": N_("Rojo"),
	"#EF6C00": N_("Naranja"),
	"#F9A825": N_("Amarillo"),
	"#6A1B9A": N_("Morado"),
	"#00838F": N_("Turquesa"),
	"#AD1457": N_("Rosa"),
	"#212121": N_("Negro"),
}

SIN_SONIDO = ""
LICENCIAS = ("CC BY 4.0", "CC BY-SA 4.0", "CC0 1.0", "GPL-3.0-or-later")


# ── Sonidos de serie ─────────────────────────────────────────────────────────


def sonidos_de_serie() -> list[tuple[str, str]]:
	"""(clave, nombre visible) de los sonidos que trae el programa, para elegirlos en una lista.

	Si el catálogo de sonidos no se puede leer se devuelve una lista vacía:
	el asistente sigue sirviendo, solo que sin sonidos que elegir.
	"""
	try:
		from app.audio.banco import catalogo_sonidos

		sonidos = catalogo_sonidos().get("sonidos", {})
	except Exception:  # noqa: BLE001 - sin catálogo de sonidos el asistente funciona igual
		log.warning("No se pudo leer el catálogo de sonidos de serie", exc_info=True)
		return []
	lista = [(clave, f"{ficha.get('nombre') or clave} ({clave})") for clave, ficha in sonidos.items() if isinstance(ficha, dict)]
	return sorted(lista, key=lambda par: par[0])


def opciones_sonido(familia: str = "") -> list[tuple[str, str]]:
	"""Opciones de un campo de sonido: «Ninguno» y los de serie (los de ``familia`` primero)."""
	todos = sonidos_de_serie()
	if familia:
		todos = [par for par in todos if par[0].startswith(familia + "/")] + [par for par in todos if not par[0].startswith(familia + "/")]
	return [(SIN_SONIDO, _("Ninguno"))] + todos


def sonido_a_wav(nombre: str, destino: str | os.PathLike[str] | None = None, segundos: float = 4.0) -> Path | None:
	"""Escribe un sonido de serie como WAV de 16 bits para poder escucharlo desde el Estudio.

	Devuelve la ruta, o ``None`` si no se pudo (sin bibliotecas de sonido, nombre
	desconocido…): escuchar es una comodidad y nunca debe romper el asistente.
	"""
	if not nombre:
		return None
	try:
		import numpy as np

		from app.audio.banco import Banco

		datos, frecuencia = Banco(carpetas_complementos=[]).datos(nombre)
		muestras = np.asarray(datos, dtype=np.float32)
		if muestras.ndim == 2:
			muestras = muestras.mean(axis=1)
		muestras = muestras[: int(frecuencia * segundos)]
		enteros = (np.clip(muestras, -1.0, 1.0) * 32767.0).astype("<i2")
		ruta = Path(destino) if destino else paths.ruta_temporales() / "escuchar.wav"
		ruta.parent.mkdir(parents=True, exist_ok=True)
		with wave.open(str(ruta), "wb") as salida:
			salida.setnchannels(1)
			salida.setsampwidth(2)
			salida.setframerate(int(frecuencia))
			salida.writeframes(enteros.tobytes())
		return ruta
	except Exception:  # noqa: BLE001 - cualquier fallo de sonido se registra y se sigue sin sonar
		log.warning("No se pudo preparar el sonido «%s» para escucharlo", nombre, exc_info=True)
		return None


# ── Textos ↔ listas ──────────────────────────────────────────────────────────


def id_de(nombre: str, reserva: str = "objeto") -> str:
	"""Identificador válido (minúsculas sin tilde, cifras, guion y guion bajo) derivado de un nombre."""
	limpio = identificador_seguro(sin_acentos(nombre).replace(" ", "_"), reserva).lower().strip("-_")
	return (limpio or reserva)[:64]


def leer_puntos(texto: str, clave: str = "puntos") -> list[list[float]]:
	"""«0,0; 1,0; 0,1» → [[0, 0], [1, 0], [0, 1]]. Cada punto, dos números entre 0 y 1.

	Los puntos se separan con punto y coma o con saltos de línea. Dentro de
	cada punto los dos números se separan con coma y espacio («0.5, 1») o solo
	con un espacio, y entonces los decimales pueden ir también con coma («0,5 1»).
	"""
	puntos: list[list[float]] = []
	for trozo in texto.replace("\n", ";").split(";"):
		trozo = trozo.strip().strip("()[]")
		if not trozo:
			continue
		# «0, 1» y «0,5 1» se separan por el espacio; «0,1» (sin espacio), por la coma.
		partes = trozo.replace(", ", " ").split()
		if len(partes) == 1 and partes[0].count(",") == 1:
			partes = partes[0].split(",")
		try:
			if len(partes) != 2:
				raise ValueError(trozo)
			x, y = (float(leer_numero(parte) or 0.0) for parte in partes)
		except ValueError:
			raise ErrorCampo(
				clave, _("No se entiende el punto «{punto}». Escriba dos números entre 0 y 1, como «0.5, 1».").format(punto=trozo)
			) from None
		if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
			raise ErrorCampo(clave, _("El punto «{punto}» se sale del cuadrado: los dos números van de 0 a 1.").format(punto=trozo))
		puntos.append([x, y])
	if puntos and len(puntos) < 3:
		raise ErrorCampo(clave, _("Un polígono necesita al menos tres puntos."))
	return puntos


def texto_puntos(puntos: Sequence[Sequence[float]]) -> str:
	"""Lo contrario de ``leer_puntos``: «0, 0; 1, 0; 0, 1»."""
	return "; ".join(f"{float(p[0]):g}, {float(p[1]):g}" for p in puntos)


def leer_variantes(texto: str, clave: str = "variantes") -> list[dict[str, Any]]:
	"""Una variante por línea: «De dos plazas: 1,5 x 0,9 x 0,85» (ancho, fondo y alto en metros)."""
	variantes: list[dict[str, Any]] = []
	usados: set[str] = set()
	for linea in texto.splitlines():
		linea = linea.strip()
		if not linea:
			continue
		nombre, separador, medidas = linea.rpartition(":")
		partes = [parte.strip() for parte in medidas.lower().replace("×", "x").replace(" por ", "x").split("x")]
		try:
			if not separador or not nombre.strip() or len(partes) != 3:
				raise ValueError(linea)
			ancho, fondo, alto = (float(leer_numero(parte) or 0.0) for parte in partes)
			if min(ancho, fondo, alto) <= 0:
				raise ValueError(linea)
		except ValueError:
			raise ErrorCampo(
				clave, _("No se entiende la variante «{linea}». Escríbala así: «De dos plazas: 1,5 x 0,9 x 0,85».").format(linea=linea)
			) from None
		identificador = id_de(nombre, "variante")
		while identificador in usados:
			identificador += "_2"
		usados.add(identificador)
		variantes.append({"id": identificador, "nombre": nombre.strip(), "ancho": ancho, "fondo": fondo, "alto": alto})
	return variantes


def texto_variantes(variantes: Sequence[Any]) -> str:
	"""Lo contrario de ``leer_variantes`` (admite diccionarios y ``Variante``)."""
	lineas = []
	for variante in variantes:
		dato = variante if isinstance(variante, dict) else {k: getattr(variante, k) for k in ("nombre", "ancho", "fondo", "alto")}
		lineas.append(f"{dato['nombre']}: {texto_numero(dato['ancho'])} x {texto_numero(dato['fondo'])} x {texto_numero(dato['alto'])}")
	return "\n".join(lineas)


def leer_lista(texto: str) -> list[str]:
	"""Palabras separadas por comas o saltos de línea, sin vacías ni repetidas."""
	vistas: list[str] = []
	for trozo in texto.replace("\n", ",").split(","):
		trozo = trozo.strip()
		if trozo and trozo not in vistas:
			vistas.append(trozo)
	return vistas


def leer_acciones(texto: str, estados: Sequence[str], clave: str = "acciones") -> list[dict[str, Any]]:
	"""Una acción por línea: «Abrir: cerrado > abierto»; sin estados («Pulsar») es un gesto suelto."""
	acciones: list[dict[str, Any]] = []
	for linea in texto.splitlines():
		linea = linea.strip()
		if not linea:
			continue
		nombre, separador, paso = linea.partition(":")
		accion: dict[str, Any] = {"id": id_de(nombre, "accion"), "nombre": nombre.strip()}
		if separador and paso.strip():
			de, flecha, a = paso.replace("→", ">").replace("->", ">").partition(">")
			de, a = id_de(de, ""), id_de(a, "")
			if not flecha or de not in estados or a not in estados:
				raise ErrorCampo(
					clave,
					_(
						"No se entiende la acción «{linea}». Escríbala así: «Abrir: cerrado > abierto», con estados de la lista de estados."
					).format(linea=linea),
				)
			accion.update({"de": de, "a": a})
		acciones.append(accion)
	return acciones


def texto_acciones(acciones: Sequence[dict[str, Any]]) -> str:
	"""Lo contrario de ``leer_acciones``."""
	lineas = []
	for accion in acciones:
		nombre = accion.get("nombre") or accion.get("id") or ""
		lineas.append(f"{nombre}: {accion['de']} > {accion['a']}" if accion.get("de") and accion.get("a") else str(nombre))
	return "\n".join(lineas)


# ── Esquemas de los formularios ──────────────────────────────────────────────

ESQUEMA_FICHA: list[Campo] = [
	c("nombre", N_("Nombre del complemento"), obligatorio=True, ayuda=N_("Como se verá en la lista de complementos.")),
	c(
		"id",
		N_("Identificador"),
		ayuda=N_("Nombre de su carpeta: minúsculas sin tilde, cifras, guion y guion bajo. Vacío: se saca del nombre."),
	),
	c("version", N_("Versión"), defecto="1.0", obligatorio=True),
	c("autor", N_("Autor"), ayuda=N_("Quien hace el complemento.")),
	c("licencia", N_("Licencia"), defecto=LICENCIAS[0], ayuda=N_("Con qué condiciones se comparte; por ejemplo, CC BY 4.0.")),
	c("descripcion", N_("Descripción"), "largo", ayuda=N_("Qué objetos contiene.")),
]

G_GENERAL = N_("Qué es")
G_FORMA = N_("Forma y medidas")
G_USO = N_("Colocación")
G_SONIDO = N_("Sonidos y acciones")
G_SIMBOLO = N_("Símbolo")
G_CLASE = N_("Clasificación")

#: Campos de clasificación: clave del formulario → (faceta de la taxonomía del dominio, clave en el JSON, admite varios).
CLASIFICACION: dict[str, tuple[str, str, bool]] = {
	"funcion": ("funcion", "funcion", False),
	"lugares": ("lugar", "lugares", True),
	"estancias": ("estancia", "estancias", True),
	"obstaculo": ("obstaculo", "obstaculo", False),
	"riesgos": ("riesgo", "riesgos", True),
	"frecuencia": ("frecuencia", "frecuencia", False),
}
SIN_INDICAR = ""


def tabla_taxonomia(faceta: str) -> dict[str, str] | None:
	"""Valores admitidos de una faceta (clave → nombre), si el dominio los declara; None si aún no existen.

	El dominio comprueba estos valores en ``validar_complemento``: por eso,
	cuando hay tabla, el asistente los ofrece en una lista cerrada en vez de
	dejar escribir cualquier cosa.
	"""
	from app.dominio import catalogo as modulo

	taxonomias = getattr(modulo, "TAXONOMIAS", None)
	tabla = taxonomias.get(faceta) if isinstance(taxonomias, dict) else None
	return dict(tabla) if isinstance(tabla, dict) and tabla else None


def _campo_clasificacion(clave: str, etiqueta: str, ayuda: str, vacio: str = "") -> Campo:
	"""Campo de una faceta: lista cerrada (o casillas) con los valores del dominio, o texto libre si no los hay."""
	faceta, _json, varios = CLASIFICACION[clave]
	tabla = tabla_taxonomia(faceta)
	if tabla is None:
		# Sin tabla en el dominio: texto libre (varios valores, separados por comas).
		return c(clave, etiqueta, grupo=G_CLASE, ayuda=ayuda)
	opciones = [(valor, _(nombre)) for valor, nombre in tabla.items()]
	if varios:
		return c(clave, etiqueta, "casillas", opciones=opciones, defecto=[], grupo=G_CLASE, ayuda=ayuda)
	return c(
		clave,
		etiqueta,
		"opcion",
		opciones=[(SIN_INDICAR, _(vacio or N_("Sin indicar"))), *opciones],
		defecto=SIN_INDICAR,
		grupo=G_CLASE,
		ayuda=ayuda,
	)


def campos_clasificacion() -> list[Campo]:
	"""Los campos de la pestaña «Clasificación»: con ellos el objeto se encuentra entre miles."""
	return [
		c(
			"subcategoria",
			N_("Subcategoría"),
			grupo=G_CLASE,
			ayuda=N_("Grupo dentro de su categoría: «Asientos» dentro de «Salón». Texto libre; puede dejarse vacío."),
		),
		_campo_clasificacion("funcion", N_("Función"), N_("Para qué sirve el objeto.")),
		_campo_clasificacion("lugares", N_("Lugares donde es habitual"), N_("Tipos de lugar en los que suele encontrarse.")),
		_campo_clasificacion(
			"estancias", N_("Estancias donde es habitual"), N_("Estancias o zonas de esos lugares en las que suele estar.")
		),
		_campo_clasificacion(
			"obstaculo",
			N_("Tipo de obstáculo"),
			N_("A qué altura queda como obstáculo y si el bastón lo encuentra. Sin indicar, el programa lo deduce de sus medidas."),
			N_("Deducirlo de las medidas"),
		),
		_campo_clasificacion("riesgos", N_("Riesgos añadidos"), N_("Además de la altura: si se mueve, si es temporal, si quema…")),
		_campo_clasificacion(
			"frecuencia", N_("Lo habitual que es"), N_("Sirve para poner primero en las búsquedas los objetos más comunes."), N_("Normal")
		),
	]


def _medida(dimension: str, etiqueta: str, cual: str, defecto: float) -> Campo:
	return c(f"{dimension}_{cual}", etiqueta, "metros", minimo=0.01, maximo=100.0, defecto=defecto, obligatorio=True, grupo=G_FORMA)


def esquema_objeto() -> list[Campo]:
	"""Campos del formulario de un objeto (se construye al pedirlo porque lee los sonidos de serie)."""
	return [
		c("nombre", N_("Nombre"), obligatorio=True, grupo=G_GENERAL, ayuda=N_("Como lo dirá el programa: «Mesa de comedor».")),
		c("categoria", N_("Categoría"), grupo=G_GENERAL, ayuda=N_("Para filtrar el catálogo: dormitorio, cocina, calle…")),
		c("etiquetas", N_("Palabras para buscarlo"), grupo=G_GENERAL, ayuda=N_("Separadas por comas.")),
		c("descripcion", N_("Descripción hablada"), "largo", grupo=G_GENERAL, ayuda=N_("Lo que se le dice al alumno de este objeto.")),
		c(
			"forma",
			N_("Forma de su planta"),
			"opcion",
			opciones=opciones_de(FORMAS),
			defecto="rectangulo",
			recarga=True,
			grupo=G_FORMA,
			ayuda=N_("La huella del objeto vista desde arriba."),
		),
		c(
			"puntos",
			N_("Puntos de la forma"),
			"largo",
			grupo=G_FORMA,
			si=lambda v: v.get("forma") in ("poligono", "ele"),
			ayuda=N_(
				"Esquinas de la huella en un cuadrado de 0 a 1, separadas con punto y coma: «0, 0; 1, 0; 0, 1». "
				"El primer número va de izquierda a derecha y el segundo de atrás al frente. En una ele puede dejarse vacío."
			),
		),
		_medida("ancho", N_("Ancho mínimo"), "min", 0.5),
		_medida("ancho", N_("Ancho normal"), "normal", 1.0),
		_medida("ancho", N_("Ancho máximo"), "max", 2.0),
		_medida("fondo", N_("Fondo mínimo"), "min", 0.5),
		_medida("fondo", N_("Fondo normal"), "normal", 1.0),
		_medida("fondo", N_("Fondo máximo"), "max", 2.0),
		_medida("alto", N_("Alto mínimo"), "min", 0.5),
		_medida("alto", N_("Alto normal"), "normal", 1.0),
		_medida("alto", N_("Alto máximo"), "max", 2.0),
		c(
			"variantes",
			N_("Variantes"),
			"largo",
			grupo=G_FORMA,
			ayuda=N_("Tamaños con nombre, uno por línea: «De dos plazas: 1,5 x 0,9 x 0,85» (ancho, fondo y alto en metros)."),
		),
		c("colocacion", N_("Dónde se coloca"), "casillas", opciones=opciones_de(COLOCACIONES), defecto=["suelo"], grupo=G_USO),
		c("ambito", N_("Ámbito"), "casillas", opciones=opciones_de(AMBITOS), defecto=["interior"], grupo=G_USO),
		c(
			"bloquea",
			N_("Corta el paso"),
			"si_no",
			defecto=True,
			grupo=G_USO,
			ayuda=N_("Desmarcado en una alfombra o una marca en el suelo."),
		),
		c(
			"altura_base",
			N_("Altura de su base"),
			"metros",
			minimo=0.0,
			maximo=10.0,
			defecto=0.0,
			grupo=G_USO,
			ayuda=N_("Metros del suelo a su parte más baja. Mayor que cero en un objeto colgado."),
		),
		c("detectable_baston", N_("Se detecta con el bastón"), "si_no", defecto=True, grupo=G_USO),
		c("contenedor", N_("Puede esconder un premio"), "si_no", defecto=False, grupo=G_USO),
		c("material", N_("Material"), "opcion", opciones=opciones_de(MATERIALES), defecto="madera", grupo=G_SONIDO),
		c(
			"sonido_golpe",
			N_("Sonido al golpearlo"),
			"opcion",
			opciones=lambda _v: opciones_sonido("golpe"),
			defecto=SIN_SONIDO,
			grupo=G_SONIDO,
		),
		c(
			"sonido_uso",
			N_("Sonido al usarlo"),
			"opcion",
			opciones=lambda _v: opciones_sonido("puerta"),
			defecto=SIN_SONIDO,
			grupo=G_SONIDO,
		),
		c(
			"sonido_propio",
			N_("Sonido propio"),
			"opcion",
			opciones=lambda _v: opciones_sonido("fuente"),
			defecto=SIN_SONIDO,
			grupo=G_SONIDO,
			ayuda=N_("Sonido que emite él solo: un frigorífico que zumba."),
		),
		c("estados", N_("Estados"), grupo=G_SONIDO, ayuda=N_("Separados por comas; el primero es el inicial: «cerrado, abierto».")),
		c(
			"acciones",
			N_("Acciones"),
			"largo",
			grupo=G_SONIDO,
			ayuda=N_("Una por línea: «Abrir: cerrado > abierto». Sin estados es un gesto suelto: «Pulsar»."),
		),
		*campos_clasificacion(),
		c(
			"letra",
			N_("Letra del símbolo"),
			grupo=G_SIMBOLO,
			ayuda=N_("Una o dos letras que se dibujan en su huella. Vacío: la inicial del nombre."),
		),
		c("color", N_("Color del símbolo"), "opcion", opciones=opciones_de(COLORES), defecto="#8B5A2B", grupo=G_SIMBOLO),
	]


CAMPOS_SONIDO = ("sonido_golpe", "sonido_uso", "sonido_propio")


# ── Valores de formulario ↔ ficha de objeto ──────────────────────────────────


def objeto_a_dict(valores: dict[str, Any], id_objeto: str = "") -> dict[str, Any]:
	"""Ficha JSON de un objeto a partir de los valores del formulario; lanza ``ErrorCampo`` si algo no cuadra."""
	nombre = str(valores.get("nombre") or "").strip()
	if not nombre:
		raise ErrorCampo("nombre", _("Falta el nombre del objeto."))
	medidas: dict[str, list[float]] = {}
	for dimension, visible in (("ancho", _("ancho")), ("fondo", _("fondo")), ("alto", _("alto"))):
		minimo, normal, maximo = (float(valores.get(f"{dimension}_{cual}") or 0.0) for cual in ("min", "normal", "max"))
		if not 0 < minimo <= normal:
			raise ErrorCampo(
				f"{dimension}_min", _("El {medida} mínimo tiene que ser mayor que cero y no pasar del normal.").format(medida=visible)
			)
		if normal > maximo:
			raise ErrorCampo(f"{dimension}_max", _("El {medida} máximo no puede ser menor que el normal.").format(medida=visible))
		medidas[dimension] = [minimo, normal, maximo]
	tipo_forma = valores.get("forma") or "rectangulo"
	forma: dict[str, Any] = {"tipo": tipo_forma}
	if tipo_forma in ("poligono", "ele"):
		puntos = leer_puntos(str(valores.get("puntos") or ""))
		if tipo_forma == "poligono" and not puntos:
			raise ErrorCampo("puntos", _("Un polígono necesita sus puntos: al menos tres."))
		if puntos:
			forma["puntos"] = puntos
	variantes = leer_variantes(str(valores.get("variantes") or ""))
	for variante in variantes:
		for dimension in ("ancho", "fondo", "alto"):
			if not medidas[dimension][0] - 1e-9 <= variante[dimension] <= medidas[dimension][2] + 1e-9:
				raise ErrorCampo(
					"variantes",
					_("La variante «{nombre}» se sale de las medidas mínima y máxima del objeto.").format(nombre=variante["nombre"]),
				)
	estados = [id_de(estado, "estado") for estado in leer_lista(str(valores.get("estados") or ""))]
	acciones = leer_acciones(str(valores.get("acciones") or ""), estados)
	colocacion = list(valores.get("colocacion") or [])
	if not colocacion:
		raise ErrorCampo("colocacion", _("Marque al menos un sitio donde se pueda colocar el objeto."))
	ambito = list(valores.get("ambito") or [])
	if not ambito:
		raise ErrorCampo("ambito", _("Marque si el objeto es de interior, de exterior o de los dos."))
	sonidos: dict[str, Any] = {}
	if valores.get("sonido_golpe"):
		sonidos["golpe"] = valores["sonido_golpe"]
	if valores.get("sonido_uso"):
		sonidos["uso"] = valores["sonido_uso"]
	if valores.get("sonido_propio"):
		sonidos["propio"] = {"sonido": valores["sonido_propio"], "volumen": 0.5, "radio": 8}
	letra = str(valores.get("letra") or "").strip()[:2] or nombre[0].upper()
	ficha: dict[str, Any] = {
		"id": id_objeto or id_de(nombre),
		"nombre": nombre,
		"categoria": id_de(str(valores.get("categoria") or ""), "") if valores.get("categoria") else "",
		"etiquetas": leer_lista(str(valores.get("etiquetas") or "")),
		"descripcion": str(valores.get("descripcion") or "").strip(),
		"ambito": ambito,
		"forma": forma,
		"medidas": medidas,
		"variantes": variantes,
		"colocacion": colocacion,
		"bloquea": bool(valores.get("bloquea", True)),
		"altura_base": float(valores.get("altura_base") or 0.0),
		"detectable_baston": bool(valores.get("detectable_baston", True)),
		"material": valores.get("material") or "madera",
		"sonidos": sonidos,
		"estados": estados,
		"acciones": acciones,
		"contenedor": bool(valores.get("contenedor", False)),
		"simbolo": {"letra": letra, "color": valores.get("color") or "#808080"},
	}
	if valores.get("categoria"):
		ficha["_nombre_categoria"] = str(valores["categoria"]).strip()
	# La clasificación es opcional: solo se escribe lo que se haya rellenado.
	subcategoria = str(valores.get("subcategoria") or "").strip()
	if subcategoria:
		ficha["subcategoria"] = id_de(subcategoria, "grupo")
		ficha["_nombre_subcategoria"] = subcategoria
	for clave, (faceta, clave_json, varios) in CLASIFICACION.items():
		valor = valores.get(clave)
		if varios:
			elegidos = leer_lista(valor) if isinstance(valor, str) else [str(v) for v in (valor or [])]
			if tabla_taxonomia(faceta) is None:
				elegidos = [id_de(v, "") for v in elegidos if id_de(v, "")]
			if elegidos:
				ficha[clave_json] = elegidos
		elif valor not in (None, "", SIN_INDICAR):
			ficha[clave_json] = str(valor) if tabla_taxonomia(faceta) is not None else id_de(str(valor), "")
	return ficha


def dict_a_valores(ficha: dict[str, Any]) -> dict[str, Any]:
	"""Valores de formulario de una ficha de objeto, para volver a editarla."""
	valores: dict[str, Any] = {
		"nombre": ficha.get("nombre", ""),
		"categoria": ficha.get("_nombre_categoria") or ficha.get("categoria", ""),
		"etiquetas": ", ".join(ficha.get("etiquetas") or []),
		"descripcion": ficha.get("descripcion", ""),
		"forma": (ficha.get("forma") or {}).get("tipo", "rectangulo"),
		"puntos": texto_puntos((ficha.get("forma") or {}).get("puntos") or []),
		"variantes": texto_variantes(ficha.get("variantes") or []),
		"colocacion": list(ficha.get("colocacion") or ["suelo"]),
		"ambito": list(ficha.get("ambito") or ["interior"]),
		"bloquea": ficha.get("bloquea", True),
		"altura_base": ficha.get("altura_base", 0.0),
		"detectable_baston": ficha.get("detectable_baston", True),
		"contenedor": ficha.get("contenedor", False),
		"material": ficha.get("material", "madera"),
		"estados": ", ".join(ficha.get("estados") or []),
		"acciones": texto_acciones(ficha.get("acciones") or []),
		"letra": (ficha.get("simbolo") or {}).get("letra", ""),
		"color": (ficha.get("simbolo") or {}).get("color", "#808080"),
	}
	valores["subcategoria"] = ficha.get("_nombre_subcategoria") or str(ficha.get("subcategoria") or "").replace("_", " ")
	for clave, (faceta, clave_json, varios) in CLASIFICACION.items():
		guardado = ficha.get(clave_json)
		if varios:
			lista = [str(v) for v in (guardado or [])]
			valores[clave] = lista if tabla_taxonomia(faceta) is not None else ", ".join(lista)
		else:
			valores[clave] = str(guardado or SIN_INDICAR)
	sonidos = ficha.get("sonidos") or {}
	propio = sonidos.get("propio")
	valores["sonido_golpe"] = sonidos.get("golpe", SIN_SONIDO)
	valores["sonido_uso"] = sonidos.get("uso", SIN_SONIDO)
	valores["sonido_propio"] = (propio.get("sonido") if isinstance(propio, dict) else propio) or SIN_SONIDO
	for dimension in ("ancho", "fondo", "alto"):
		medida = (ficha.get("medidas") or {}).get(dimension, [0.5, 1.0, 2.0])
		if isinstance(medida, (int, float)):
			medida = [medida, medida, medida]
		valores[f"{dimension}_min"], valores[f"{dimension}_normal"], valores[f"{dimension}_max"] = medida
	return valores


def resumen_objeto(ficha: dict[str, Any]) -> tuple[str, str, str, str]:
	"""(nombre, categoría, forma, medidas) de una ficha, para la lista de objetos del asistente."""
	medidas = ficha.get("medidas") or {}
	texto = " × ".join(texto_numero(medidas.get(d, [0, 1, 0])[1]) for d in ("ancho", "fondo", "alto"))
	forma = _(FORMAS.get((ficha.get("forma") or {}).get("tipo", "rectangulo"), "Rectángulo"))
	return (
		str(ficha.get("nombre", "")),
		str(ficha.get("_nombre_categoria") or ficha.get("categoria") or ""),
		forma,
		_("{medidas} m").format(medidas=texto),
	)


def construir_complemento(ficha: dict[str, Any], objetos: Sequence[dict[str, Any]]) -> dict[str, Any]:
	"""El ``complemento.json`` completo; lanza ``ErrorCampo`` si la ficha general no vale o no hay objetos."""
	nombre = str(ficha.get("nombre") or "").strip()
	if not nombre:
		raise ErrorCampo("nombre", _("Falta el nombre del complemento."))
	identificador = id_de(str(ficha.get("id") or "") or nombre, "complemento")
	if not objetos:
		raise ErrorCampo("objetos", _("El complemento no tiene ningún objeto: añada al menos uno."))
	categorias: dict[str, str] = {}
	subcategorias: dict[str, str] = {}
	estados: dict[str, str] = {}
	limpios: list[dict[str, Any]] = []
	usados: set[str] = set()
	for objeto in objetos:
		copia = {clave: valor for clave, valor in objeto.items() if not clave.startswith("_")}
		base = copia["id"]
		numero = 2
		while copia["id"] in usados:
			copia["id"] = f"{base}_{numero}"[:64]
			numero += 1
		usados.add(copia["id"])
		if copia.get("categoria"):
			categorias.setdefault(copia["categoria"], objeto.get("_nombre_categoria") or copia["categoria"])
		if copia.get("subcategoria"):
			subcategorias.setdefault(
				copia["subcategoria"], objeto.get("_nombre_subcategoria") or copia["subcategoria"].replace("_", " ").capitalize()
			)
		for estado in copia.get("estados") or []:
			estados.setdefault(estado, estado.replace("_", " ").capitalize())
		limpios.append(copia)
	datos: dict[str, Any] = {
		"formato": FORMATO_COMPLEMENTO,
		"id": identificador,
		"nombre": nombre,
		"version": str(ficha.get("version") or "1.0").strip(),
		"autor": str(ficha.get("autor") or "").strip(),
		"licencia": str(ficha.get("licencia") or "").strip(),
		"descripcion": str(ficha.get("descripcion") or "").strip(),
		"categorias": categorias,
		"estados": estados,
		"objetos": limpios,
	}
	if subcategorias:
		# Solo si algún objeto la usa: un complemento sin clasificar queda como antes.
		datos["subcategorias"] = subcategorias
	return datos


# ── Miniaturas: la huella como PNG ───────────────────────────────────────────

# Letras de 5 × 7 puntos: lo justo para escribir el símbolo sin depender de wx ni de fuentes.
_GLIFOS: dict[str, tuple[str, ...]] = {
	"A": ("01110", "10001", "10001", "11111", "10001", "10001", "10001"),
	"B": ("11110", "10001", "10001", "11110", "10001", "10001", "11110"),
	"C": ("01110", "10001", "10000", "10000", "10000", "10001", "01110"),
	"D": ("11110", "10001", "10001", "10001", "10001", "10001", "11110"),
	"E": ("11111", "10000", "10000", "11110", "10000", "10000", "11111"),
	"F": ("11111", "10000", "10000", "11110", "10000", "10000", "10000"),
	"G": ("01110", "10001", "10000", "10111", "10001", "10001", "01111"),
	"H": ("10001", "10001", "10001", "11111", "10001", "10001", "10001"),
	"I": ("01110", "00100", "00100", "00100", "00100", "00100", "01110"),
	"J": ("00111", "00010", "00010", "00010", "00010", "10010", "01100"),
	"K": ("10001", "10010", "10100", "11000", "10100", "10010", "10001"),
	"L": ("10000", "10000", "10000", "10000", "10000", "10000", "11111"),
	"M": ("10001", "11011", "10101", "10101", "10001", "10001", "10001"),
	"N": ("10001", "11001", "10101", "10011", "10001", "10001", "10001"),
	"O": ("01110", "10001", "10001", "10001", "10001", "10001", "01110"),
	"P": ("11110", "10001", "10001", "11110", "10000", "10000", "10000"),
	"Q": ("01110", "10001", "10001", "10001", "10101", "10010", "01101"),
	"R": ("11110", "10001", "10001", "11110", "10100", "10010", "10001"),
	"S": ("01111", "10000", "10000", "01110", "00001", "00001", "11110"),
	"T": ("11111", "00100", "00100", "00100", "00100", "00100", "00100"),
	"U": ("10001", "10001", "10001", "10001", "10001", "10001", "01110"),
	"V": ("10001", "10001", "10001", "10001", "10001", "01010", "00100"),
	"W": ("10001", "10001", "10001", "10101", "10101", "11011", "10001"),
	"X": ("10001", "10001", "01010", "00100", "01010", "10001", "10001"),
	"Y": ("10001", "10001", "01010", "00100", "00100", "00100", "00100"),
	"Z": ("11111", "00001", "00010", "00100", "01000", "10000", "11111"),
	"0": ("01110", "10001", "10011", "10101", "11001", "10001", "01110"),
	"1": ("00100", "01100", "00100", "00100", "00100", "00100", "01110"),
	"2": ("01110", "10001", "00001", "00010", "00100", "01000", "11111"),
	"3": ("11110", "00001", "00001", "01110", "00001", "00001", "11110"),
	"4": ("00010", "00110", "01010", "10010", "11111", "00010", "00010"),
	"5": ("11111", "10000", "11110", "00001", "00001", "10001", "01110"),
	"6": ("01110", "10000", "10000", "11110", "10001", "10001", "01110"),
	"7": ("11111", "00001", "00010", "00100", "01000", "01000", "01000"),
	"8": ("01110", "10001", "10001", "01110", "10001", "10001", "01110"),
	"9": ("01110", "10001", "10001", "01111", "00001", "00001", "01110"),
}


def _color_rgb(color: str) -> tuple[int, int, int]:
	limpio = color.strip().lstrip("#")
	try:
		if len(limpio) != 6:
			raise ValueError(color)
		return int(limpio[0:2], 16), int(limpio[2:4], 16), int(limpio[4:6], 16)
	except ValueError:
		return 128, 128, 128


def puntos_de_forma(forma: dict[str, Any] | DefObjeto) -> list[Punto]:
	"""La huella en el cuadrado 0..1 de una forma declarada (o de una ficha del catálogo)."""
	if isinstance(forma, DefObjeto):
		return [(float(x), float(y)) for x, y in forma.puntos_forma()]
	return [(float(x), float(y)) for x, y in DefObjeto(forma=dict(forma)).puntos_forma()]


def _png(ancho: int, alto: int, filas: list[bytearray]) -> bytes:
	"""PNG RGB de 8 bits con la biblioteca estándar."""

	def trozo(tipo: bytes, datos: bytes) -> bytes:
		return struct.pack(">I", len(datos)) + tipo + datos + struct.pack(">I", zlib.crc32(tipo + datos) & 0xFFFFFFFF)

	crudo = b"".join(b"\x00" + bytes(fila) for fila in filas)
	return (
		b"\x89PNG\r\n\x1a\n"
		+ trozo(b"IHDR", struct.pack(">IIBBBBB", ancho, alto, 8, 2, 0, 0, 0))
		+ trozo(b"IDAT", zlib.compress(crudo, 9))
		+ trozo(b"IEND", b"")
	)


def generar_miniatura(
	forma: dict[str, Any] | DefObjeto,
	ruta: str | os.PathLike[str],
	lado: int = 128,
	letra: str = "",
	color: str = "#808080",
	ancho: float = 1.0,
	fondo: float = 1.0,
) -> Path:
	"""Dibuja la huella en planta de un objeto como PNG cuadrado de ``lado`` píxeles y devuelve su ruta.

	La huella se pinta a escala (``ancho`` por ``fondo``, en metros), rellena
	del color del símbolo, con borde oscuro y con la letra en el centro. La
	parte de atrás del objeto (la que se arrima a la pared) queda arriba. Si se
	pasa una ficha del catálogo, la letra, el color y las medidas salen de ella.
	"""
	if isinstance(forma, DefObjeto):
		letra = letra or forma.letra()
		color = forma.color() if color == "#808080" else color
		ancho, fondo = forma.rango("ancho")[1], forma.rango("fondo")[1]
	lado = max(16, int(lado))
	puntos = puntos_de_forma(forma)
	margen = max(2, lado // 12)
	util = lado - 2 * margen
	mayor = max(ancho, fondo, 1e-6)
	# Una huella muy alargada no se reduce a una raya: se le garantiza un grosor visible.
	ancho_px = max(util * ancho / mayor, util * 0.12)
	fondo_px = max(util * fondo / mayor, util * 0.12)
	x0, y0 = (lado - ancho_px) / 2.0, (lado - fondo_px) / 2.0
	poligono = [(x0 + x * ancho_px, y0 + y * fondo_px) for x, y in puntos]
	relleno = _color_rgb(color)
	borde = (20, 20, 20)
	blanco = (255, 255, 255)
	grosor = max(1.0, lado / 64.0)
	lados = list(zip(poligono, poligono[1:] + poligono[:1], strict=True))
	filas = [bytearray(blanco * lado) for _fila in range(lado)]
	for fila in range(lado):
		for columna in range(lado):
			centro = (columna + 0.5, fila + 0.5)
			pixel: tuple[int, int, int] | None = None
			if any(geo.distancia_punto_segmento(centro, a, b) <= grosor for a, b in lados):
				pixel = borde
			elif geo.punto_en_poligono(centro, poligono):
				pixel = relleno
			if pixel is not None:
				filas[fila][columna * 3 : columna * 3 + 3] = bytes(pixel)
	texto = [caracter for caracter in sin_acentos(letra).upper() if caracter in _GLIFOS][:2]
	if texto:
		luminancia = 0.299 * relleno[0] + 0.587 * relleno[1] + 0.114 * relleno[2]
		tinta = (0, 0, 0) if luminancia > 140 else blanco
		escala = max(1, lado // 32)
		ancho_texto = (len(texto) * 6 - 1) * escala
		centro_x, centro_y = geo.centroide(poligono) if len(poligono) >= 3 else (lado / 2, lado / 2)
		inicio_x = int(min(max(centro_x - ancho_texto / 2, 0), lado - ancho_texto))
		inicio_y = int(min(max(centro_y - 3.5 * escala, 0), lado - 7 * escala))
		for indice, caracter in enumerate(texto):
			for fila_glifo, linea in enumerate(_GLIFOS[caracter]):
				for columna_glifo, punto in enumerate(linea):
					if punto != "1":
						continue
					for dy in range(escala):
						for dx in range(escala):
							x = inicio_x + (indice * 6 + columna_glifo) * escala + dx
							y = inicio_y + fila_glifo * escala + dy
							if 0 <= x < lado and 0 <= y < lado:
								filas[y][x * 3 : x * 3 + 3] = bytes(tinta)
	destino = Path(ruta)
	destino.parent.mkdir(parents=True, exist_ok=True)
	destino.write_bytes(_png(lado, lado, filas))
	return destino


def descripcion_miniatura(ficha: dict[str, Any]) -> str:
	"""Descripción en texto de la miniatura: obligatoria, porque la imagen sola no le sirve a quien no ve."""
	medidas = ficha.get("medidas") or {}
	nombres = {"rectangulo": _("un rectángulo"), "circulo": _("un círculo o elipse"), "ele": _("una ele"), "poligono": _("un polígono")}
	return _("Huella en planta de «{nombre}»: {forma} de {ancho} por {fondo} metros, con la letra «{letra}».").format(
		nombre=ficha.get("nombre", ""),
		forma=nombres.get((ficha.get("forma") or {}).get("tipo", "rectangulo"), _("un rectángulo")),
		ancho=texto_numero(medidas.get("ancho", [0, 1, 0])[1]),
		fondo=texto_numero(medidas.get("fondo", [0, 1, 0])[1]),
		letra=(ficha.get("simbolo") or {}).get("letra", ""),
	)


# ── Guardar, comprobar y exportar ────────────────────────────────────────────


def guardar_complemento(datos: dict[str, Any], carpeta_plugins: str | os.PathLike[str] | None = None, miniaturas: bool = True) -> Path:
	"""Escribe el complemento en ``<plugins>/<id>`` (con la miniatura de cada objeto) y devuelve su carpeta.

	El JSON se escribe en un fichero provisional y después sustituye al
	anterior: un corte a mitad no deja una ficha a medias. Si la carpeta ya
	existía (se está corrigiendo un complemento propio) se conservan sus
	sonidos y lo demás que tuviera.
	"""
	raiz = Path(carpeta_plugins) if carpeta_plugins else paths.ruta_complementos()
	carpeta = raiz / str(datos["id"])
	carpeta.mkdir(parents=True, exist_ok=True)
	datos = json.loads(json.dumps(datos))  # copia: no se toca lo que tenga en la mano quien llama
	if miniaturas:
		for objeto in datos.get("objetos", []):
			medidas = objeto.get("medidas") or {}
			simbolo = objeto.get("simbolo") or {}
			nombre = f"imagenes/{objeto['id']}.png"
			generar_miniatura(
				objeto.get("forma") or {"tipo": "rectangulo"},
				carpeta / nombre,
				letra=str(simbolo.get("letra", "")),
				color=str(simbolo.get("color", "#808080")),
				ancho=float(medidas.get("ancho", [0, 1, 0])[1]),
				fondo=float(medidas.get("fondo", [0, 1, 0])[1]),
			)
			objeto["imagen"] = {"fichero": nombre, "descripcion": descripcion_miniatura(objeto)}
	provisional = carpeta / (NOMBRE_FICHA + ".tmp")
	provisional.write_text(json.dumps(datos, ensure_ascii=False, indent="\t"), encoding="utf-8")
	os.replace(provisional, carpeta / NOMBRE_FICHA)
	log.info("Complemento propio «%s» guardado en %s", datos["id"], carpeta)
	return carpeta


def comprobar(carpeta: str | os.PathLike[str]) -> list[Aviso]:
	"""Lo que hay que corregir antes de compartir el complemento (lista vacía: listo)."""
	return validar_complemento(carpeta)


def exportar(carpeta: str | os.PathLike[str], ruta_zip: str | os.PathLike[str]) -> Path:
	"""Crea el ``.elabc`` del complemento para compartirlo."""
	return empaquetar_complemento(carpeta, ruta_zip)


def texto_avisos(avisos: Sequence[Aviso]) -> str:
	"""Los avisos en texto llano, uno por línea, con los errores marcados con palabras (no solo con color)."""
	if not avisos:
		return _("Sin problemas: el complemento está listo.")
	return "\n".join((_("Error: {texto}") if aviso.es_error else _("Aviso: {texto}")).format(texto=str(aviso)) for aviso in avisos)
