"""Lógica del editor de actividades, sin wx: filas, copias, condiciones, premios, objetivos, ayudas y paquetes."""

from __future__ import annotations

import copy
import logging
import re
from collections.abc import Iterable, Sequence
from pathlib import Path
from typing import Any

from app.core.i18n import N_, _
from app.dominio import formato
from app.ui.seguimiento import actividades_api as api
from app.ui.seguimiento import lugares, textos
from app.ui.seguimiento.textos import recortar

log = logging.getLogger(__name__)

TITULOS_GRUPO: dict[str, str] = {
	"general": N_("General"),
	"premios": N_("Premios"),
	"objetivos": N_("Objetivos"),
	"examen": N_("Examen"),
	"puntuacion": N_("Puntuación"),
	"ayudas": N_("Ayudas"),
	"mensajes": N_("Mensajes"),
	"final": N_("Final"),
}
EXTENSIONES_AUDIO = (".wav", ".ogg", ".flac")
MODOS_BALIZA: dict[str, str] = {"nunca": N_("Nunca"), "al_pedir": N_("Al pedir una pista"), "siempre": N_("Siempre")}
# Estados de una ayuda en la tabla: sin indicar (manda la ficha del alumno), permitida o prohibida.
SIN_INDICAR = "sin_indicar"
PERMITIDA = "permitida"
PROHIBIDA = "prohibida"
ESTADOS_AYUDA: dict[str, str] = {
	SIN_INDICAR: N_("Como en la ficha del alumno"),
	PERMITIDA: N_("Permitida"),
	PROHIBIDA: N_("Prohibida"),
}
TIPOS_OBJETIVO: dict[str, str] = {
	"ir_a": N_("Ir a un lugar"),
	"recoger": N_("Recoger algo en un lugar"),
	"entregar": N_("Entregar lo recogido en un lugar"),
	"salir": N_("Salir por una salida"),
	"localizar": N_("Localizar un espacio por su nombre"),
	"senalar": N_("Señalar hacia un lugar"),
}
NIVELES_DE_SERIE: list[dict[str, Any]] = [
	{"nombre": N_("Con baliza"), "baliza": "siempre", "ayudas": {}},
	{"nombre": N_("Baliza solo al pedirla"), "baliza": "al_pedir", "ayudas": {}},
	{"nombre": N_("Sin baliza"), "baliza": "nunca", "ayudas": {"baliza": {"permitida": False, "limite": None}}},
	{
		"nombre": N_("Sin baliza y sin «dónde estoy»"),
		"baliza": "nunca",
		"ayudas": {
			"baliza": {"permitida": False, "limite": None},
			"donde_estoy": {"permitida": False, "limite": None},
			"descripcion": {"permitida": False, "limite": None},
		},
	},
]


# ── Lista de actividades ─────────────────────────────────────────────────────


def columnas() -> list[tuple[str, int]]:
	"""Columnas de la lista de actividades."""
	return [(_("Nombre"), 220), (_("Tipo"), 170), (_("Modo"), 90), (_("Resumen"), 380)]


def fila_actividad(datos: dict[str, Any], entorno: Any) -> list[str]:
	"""Textos de la fila de una actividad."""
	return [
		str(datos.get("nombre") or datos.get("id") or _("Sin nombre")),
		api.nombre_tipo(str(datos.get("tipo") or "")),
		textos.nombre(textos.MODOS, datos.get("modo") or ""),
		recortar(api.describir_actividad(datos, entorno), 240),
	]


def id_unico(actividades: Iterable[dict[str, Any]], propuesto: str) -> str:
	"""Identificador de actividad que no repite ninguno de la lista."""
	base = formato.identificador_seguro(propuesto, "actividad")
	usados = {str(actividad.get("id", "")) for actividad in actividades}
	if base not in usados:
		return base
	raiz = re.sub(r"-\d+$", "", base)
	numero = 2
	while f"{raiz}-{numero}" in usados:
		numero += 1
	return f"{raiz}-{numero}"


def duplicar(actividad: dict[str, Any], actividades: Iterable[dict[str, Any]]) -> dict[str, Any]:
	"""Copia independiente de una actividad, con otro id y «Copia de» en el nombre."""
	copia = copy.deepcopy(actividad)
	copia["id"] = id_unico(actividades, str(actividad.get("id") or "actividad"))
	copia["nombre"] = _("Copia de {nombre}").format(nombre=actividad.get("nombre") or actividad.get("id") or _("actividad"))
	return copia


def mover(lista: list[Any], indice: int, delta: int) -> int:
	"""Mueve un elemento de la lista un puesto. Devuelve su posición nueva (la misma si no se puede)."""
	destino = indice + delta
	if not (0 <= indice < len(lista) and 0 <= destino < len(lista)):
		return indice
	lista[indice], lista[destino] = lista[destino], lista[indice]
	return destino


# ── Esquema ──────────────────────────────────────────────────────────────────


def titulo_grupo(grupo: str) -> str:
	"""Título de la pestaña de un grupo de campos."""
	conocido = TITULOS_GRUPO.get(str(grupo))
	if conocido:
		return _(conocido)
	return str(grupo or _("General")).replace("_", " ").capitalize()


def grupos_en_orden(campos: Sequence[Any]) -> list[str]:
	"""Grupos de los campos, en el orden en que aparecen (así lo decide el esquema)."""
	orden: list[str] = []
	for campo in campos:
		grupo = str(getattr(campo, "grupo", "") or "general")
		if grupo not in orden:
			orden.append(grupo)
	return orden


def condicion_cumplida(depende_de: Any, datos: dict[str, Any]) -> bool:
	"""True si el campo del que depende otro está activado.

	El esquema real usa la clave de un campo «sí o no». Se admiten además
	formas más ricas por si el esquema las incorpora: ``"clave=valor"``,
	``"clave!=valor"``, ``(clave, valor o lista de valores)`` y ``{clave: valor}``.
	"""
	if not depende_de:
		return True
	if isinstance(depende_de, dict):
		return all(condicion_cumplida((clave, valor), datos) for clave, valor in depende_de.items())
	if isinstance(depende_de, (list, tuple)) and len(depende_de) == 2:
		actual = api.leer_campo(datos, str(depende_de[0]))
		esperado = depende_de[1]
		if isinstance(esperado, (list, tuple, set, frozenset)):
			return actual in esperado
		return actual == esperado
	texto = str(depende_de)
	if "!=" in texto:
		clave, _sep, valor = texto.partition("!=")
		return str(api.leer_campo(datos, clave.strip(), "")) != valor.strip()
	if "=" in texto:
		clave, _sep, valor = texto.partition("=")
		return str(api.leer_campo(datos, clave.strip(), "")) == valor.strip()
	return bool(api.leer_campo(datos, texto))


def clave_de_dependencia(depende_de: Any) -> str:
	"""Clave del campo del que depende otro (para saber a qué control hay que escuchar)."""
	if isinstance(depende_de, dict) and depende_de:
		return str(next(iter(depende_de)))
	if isinstance(depende_de, (list, tuple)) and depende_de:
		return str(depende_de[0])
	return re.split(r"!?=", str(depende_de or ""))[0].strip()


def opciones_normalizadas(opciones: Any) -> list[tuple[Any, str]]:
	"""Opciones de un campo «opcion» como pares (valor, etiqueta), vengan como vengan."""
	if isinstance(opciones, dict):
		return [(valor, str(etiqueta)) for valor, etiqueta in opciones.items()]
	pares: list[tuple[Any, str]] = []
	for opcion in opciones or []:
		if isinstance(opcion, (list, tuple)) and len(opcion) >= 2:
			pares.append((opcion[0], str(opcion[1])))
		else:
			pares.append((opcion, str(opcion)))
	return pares


def clases_de(opciones: Any) -> list[str]:
	"""Clases de elemento que admite un campo «elemento» (todas las habituales si no lo dice)."""
	if isinstance(opciones, str):
		return [opciones]
	clases = [str(clase) for clase in (opciones or []) if isinstance(clase, str)]
	return clases or ["espacio", "objeto", "abertura", "referencia"]


# Palabras del código de un aviso que señalan a un campo aunque no se llamen igual que él.
_ALIAS_DE_CAMPO: tuple[tuple[str, tuple[str, ...]], ...] = (
	("contenedor", ("premios",)),
	("examen", ("pruebas", "numero_pruebas")),
	("prueba", ("pruebas", "numero_pruebas")),
	("guia", ("destino",)),
	("salida", ("premios", "pruebas")),
	("ayuda", ("ayudas",)),
)


def campo_de_aviso(aviso: Any, claves: Sequence[str], datos: dict[str, Any] | None = None) -> str | None:
	"""Clave del campo al que se refiere un aviso de la validación, si se puede deducir.

	La validación no dice qué campo falla: da un código («sin_premios»,
	«objetivo_sin_destino») y, a veces, el id del premio, del objetivo o del
	elemento afectado. Se mira, por este orden: si el id es el de un premio o
	un objetivo de la actividad; si es el valor de algún campo (el destino);
	si el id o el código son directamente una clave; y si el nombre de algún
	campo aparece dentro del código.
	"""
	elemento = str(getattr(aviso, "elemento_id", "") or "")
	codigo = str(getattr(aviso, "codigo", "") or "")
	if elemento and datos is not None:
		for clave in ("premios", "objetivos", "pruebas"):
			lista = datos.get(clave)
			if clave in claves and isinstance(lista, list) and any(isinstance(uno, dict) and uno.get("id") == elemento for uno in lista):
				return clave
		for clave in claves:
			if api.leer_campo(datos, clave) == elemento:
				return clave
	for candidato in (elemento, codigo):
		if candidato in claves:
			return candidato
	mejor: str | None = None
	for clave in claves:
		raiz = clave.split(".")[-1]
		singular = raiz[:-1] if raiz.endswith("s") and len(raiz) > 3 else raiz
		if len(singular) > 2 and singular in codigo:
			if mejor is None or len(clave) > len(mejor):
				mejor = clave
	if mejor is not None:
		return mejor
	for palabra, candidatas in _ALIAS_DE_CAMPO:
		if palabra in codigo:
			for clave in candidatas:
				if clave in claves:
					return clave
	return None


def indice_de_aviso(aviso: Any, lista: Sequence[Any]) -> int:
	"""Posición, en una lista de premios u objetivos, del que señala el aviso; -1 si no señala a ninguno."""
	elemento = str(getattr(aviso, "elemento_id", "") or "")
	for indice, uno in enumerate(lista):
		if elemento and isinstance(uno, dict) and uno.get("id") == elemento:
			return indice
	return -1


def texto_avisos(avisos: Sequence[Any]) -> str:
	"""Los avisos de una comprobación, uno por línea, con los errores primero."""
	if not avisos:
		return _("No se ha encontrado ningún problema.")
	errores = [aviso for aviso in avisos if getattr(aviso, "gravedad", "") == "error"]
	otros = [aviso for aviso in avisos if getattr(aviso, "gravedad", "") != "error"]
	lineas = [
		_("{errores} errores y {avisos} avisos.").format(errores=len(errores), avisos=len(otros)),
		"",
	]
	for aviso in errores:
		lineas.append(_("Error: {texto}").format(texto=_texto_aviso(aviso)))
	for aviso in otros:
		lineas.append(_("Aviso: {texto}").format(texto=_texto_aviso(aviso)))
	return "\n".join(lineas)


def _texto_aviso(aviso: Any) -> str:
	return " ".join(
		parte for parte in (str(getattr(aviso, "mensaje", "") or aviso), str(getattr(aviso, "sugerencia", "") or "")) if parte
	).strip()


def hay_errores(avisos: Sequence[Any]) -> bool:
	"""True si algún aviso es de gravedad «error»."""
	return any(getattr(aviso, "gravedad", "") == "error" for aviso in avisos)


# ── Premios ──────────────────────────────────────────────────────────────────


def columnas_premios() -> list[tuple[str, int]]:
	"""Columnas de la lista de premios."""
	return [(_("Premio"), 150), (_("Dónde está"), 260), (_("Visibilidad"), 150), (_("Sonido"), 120), (_("Mensaje"), 200)]


def fila_premio(premio: dict[str, Any], entorno: Any, nombres_sonido: dict[str, str] | None = None) -> list[str]:
	"""Textos de la fila de un premio: el lugar va en palabras, nunca en coordenadas."""
	sonido = str(premio.get("sonido") or "")
	mensaje = recortar(str(premio.get("mensaje") or ""), 80)
	if premio.get("audio"):
		mensaje = (mensaje + " " if mensaje else "") + _("(con audio grabado)")
	return [
		str(premio.get("nombre") or premio.get("id") or _("Premio")),
		lugares.describir_punto(entorno, str(premio.get("planta") or ""), premio.get("x"), premio.get("y"), premio.get("dentro_de")),
		textos.nombre(textos.VISIBILIDADES, premio.get("visibilidad") or "cerca"),
		(nombres_sonido or {}).get(sonido, sonido) or _("El de serie"),
		mensaje,
	]


def id_premio_unico(premios: Iterable[dict[str, Any]], propuesto: str = "premio") -> str:
	"""Identificador de premio que no repite ninguno de la lista."""
	usados = {str(premio.get("id", "")) for premio in premios}
	raiz = re.sub(r"-\d+$", "", formato.identificador_seguro(propuesto, "premio"))
	numero = 1
	while f"{raiz}-{numero}" in usados:
		numero += 1
	return f"{raiz}-{numero}"


def renumerar_premios(nuevos: list[dict[str, Any]], existentes: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
	"""Da a los premios nuevos ids que no choquen con los que ya hay."""
	todos = list(existentes)
	resultado: list[dict[str, Any]] = []
	for premio in nuevos:
		copia = dict(premio)
		copia["id"] = id_premio_unico(todos, str(copia.get("id") or "premio"))
		todos.append(copia)
		resultado.append(copia)
	return resultado


def nombre_recurso_audio(ruta: Path, existentes: Iterable[str]) -> str:
	"""Nombre interno (``sonidos/<nombre>.<ext>``) para un audio que se añade al paquete."""
	extension = ruta.suffix.lower()
	raiz = formato.identificador_seguro(ruta.stem, "audio")
	usados = set(existentes)
	nombre = f"{formato.CARPETA_SONIDOS}/{raiz}{extension}"
	numero = 2
	while nombre in usados:
		nombre = f"{formato.CARPETA_SONIDOS}/{raiz}-{numero}{extension}"
		numero += 1
	return nombre


def leer_audio(ruta: Path) -> bytes:
	"""Bytes de un audio grabado. ``ValueError`` con mensaje para mostrar si no vale."""
	if ruta.suffix.lower() not in EXTENSIONES_AUDIO:
		raise ValueError(_("El audio debe ser un fichero WAV, OGG o FLAC."))
	try:
		datos = ruta.read_bytes()
	except OSError as error:
		raise ValueError(_("No se puede leer el fichero de audio: {error}").format(error=error)) from error
	if not datos:
		raise ValueError(_("El fichero de audio está vacío."))
	if len(datos) > formato.MAX_BYTES_RECURSO:
		raise ValueError(_("El fichero de audio es demasiado grande para guardarlo en el paquete."))
	return datos


# ── Objetivos ────────────────────────────────────────────────────────────────


def describir_lugar(entorno: Any, lugar: Any, premios: Sequence[dict[str, Any]] = ()) -> str:
	"""Un destino dicho en palabras: el nombre de un elemento, un premio de la actividad o un punto."""
	if not lugar:
		return _("Sin indicar")
	if isinstance(lugar, str):
		for premio in premios:
			if premio.get("id") == lugar:
				return _("Premio «{nombre}»").format(nombre=premio.get("nombre") or lugar)
		elemento = entorno.elemento(lugar) if entorno is not None else None
		if elemento is None and entorno is not None and entorno.planta(lugar) is not None:
			return lugares.nombre_planta(entorno, lugar)
		return lugares.nombre_de(elemento) if elemento is not None else _("«{id}» (ya no existe)").format(id=lugar)
	if isinstance(lugar, dict):
		return lugares.describir_punto(entorno, str(lugar.get("planta") or ""), lugar.get("x"), lugar.get("y"))
	return str(lugar)


def fila_objetivo(objetivo: dict[str, Any], entorno: Any, premios: Sequence[dict[str, Any]] = ()) -> list[str]:
	"""Textos de la fila de un objetivo."""
	return [
		textos.nombre(TIPOS_OBJETIVO, objetivo.get("tipo") or "ir_a"),
		describir_lugar(entorno, objetivo.get("destino"), premios),
		recortar(str(objetivo.get("texto") or ""), 120),
	]


def id_objetivo_unico(objetivos: Iterable[dict[str, Any]]) -> str:
	"""Identificador de objetivo que no repite ninguno de la lista."""
	usados = {str(objetivo.get("id", "")) for objetivo in objetivos}
	numero = 1
	while f"objetivo-{numero}" in usados:
		numero += 1
	return f"objetivo-{numero}"


# ── Ayudas ───────────────────────────────────────────────────────────────────


def regla_completa(regla: Any) -> dict[str, Any] | None:
	"""Regla de una ayuda como ``{"permitida", "limite"}``; admite las abreviaturas del motor (True, False o un número)."""
	if isinstance(regla, bool):
		return {"permitida": regla, "limite": None}
	if isinstance(regla, (int, float)):
		return {"permitida": True, "limite": max(0, int(regla))}
	if isinstance(regla, dict):
		limite = regla.get("limite")
		limite = int(limite) if isinstance(limite, (int, float)) and not isinstance(limite, bool) and limite >= 0 else None
		return {"permitida": bool(regla.get("permitida", True)), "limite": limite}
	return None


def estado_ayuda(regla: Any) -> str:
	"""``sin_indicar``, ``permitida`` o ``prohibida``."""
	completa = regla_completa(regla)
	if completa is None:
		return SIN_INDICAR
	return PERMITIDA if completa["permitida"] else PROHIBIDA


def fila_ayuda(clave: str, regla: Any) -> list[str]:
	"""Textos de la fila de una ayuda: nombre, estado y límite de usos."""
	completa = regla_completa(regla)
	estado = estado_ayuda(regla)
	if estado != PERMITIDA:
		limite = ""
	elif completa is not None and completa["limite"] is not None:
		limite = str(completa["limite"])
	else:
		limite = _("Sin límite")
	return [textos.nombre(textos.AYUDAS, clave), textos.nombre(ESTADOS_AYUDA, estado), limite]


def claves_ayudas(reglas: dict[str, Any] | None = None) -> list[str]:
	"""Las ayudas conocidas más las que traiga la actividad y no se conozcan (de otra versión)."""
	claves = list(textos.AYUDAS)
	claves.extend(clave for clave in (reglas or {}) if clave not in claves)
	return claves


def cambiar_ayuda(reglas: dict[str, Any], clave: str, estado: str, limite: int | None = None) -> None:
	"""Pone una ayuda en un estado (y con un límite de usos si está permitida)."""
	if estado == SIN_INDICAR:
		reglas.pop(clave, None)
	elif estado == PROHIBIDA:
		reglas[clave] = {"permitida": False, "limite": None}
	else:
		reglas[clave] = {"permitida": True, "limite": limite}


def resumen_nivel(nivel: dict[str, Any]) -> list[str]:
	"""Textos de la fila de un nivel de retirada: nombre, baliza y ayudas que quita."""
	reglas = nivel.get("ayudas") if isinstance(nivel.get("ayudas"), dict) else {}
	quitadas = [textos.nombre(textos.AYUDAS, clave) for clave, regla in reglas.items() if estado_ayuda(regla) == PROHIBIDA]
	limitadas = [
		_("{ayuda} ({n} usos)").format(ayuda=textos.nombre(textos.AYUDAS, clave), n=regla_completa(regla)["limite"])
		for clave, regla in reglas.items()
		if estado_ayuda(regla) == PERMITIDA and regla_completa(regla)["limite"] is not None
	]
	nombre = str(nivel.get("nombre") or "")
	return [
		_(nombre) if nombre else _("Nivel sin nombre"),
		textos.nombre(MODOS_BALIZA, nivel.get("baliza") or "nunca"),
		", ".join(quitadas + limitadas) or _("No quita ninguna"),
	]


def niveles_de_serie() -> list[dict[str, Any]]:
	"""Los cuatro niveles habituales, con el nombre ya en el idioma de la interfaz."""
	niveles = copy.deepcopy(NIVELES_DE_SERIE)
	for nivel in niveles:
		nivel["nombre"] = _(nivel["nombre"])
	return niveles


# ── Paquetes y pruebas ───────────────────────────────────────────────────────


def recursos_del_paquete(contexto: Any) -> dict[str, Any]:
	"""Recursos (sonidos e imágenes) del paquete abierto: los del contexto y, si no los da, los del fichero."""
	recursos: dict[str, Any] = {}
	ruta = getattr(contexto, "ruta_paquete", None)
	propios = getattr(contexto, "recursos", None)
	if isinstance(propios, dict) and propios:
		recursos.update(propios)
	elif ruta is not None and Path(ruta).is_file():
		try:
			recursos.update(formato.cargar_paquete(ruta).recursos)
		except formato.ErrorFormato:
			log.warning("No se han podido leer los recursos del paquete abierto", exc_info=True)
		if isinstance(propios, dict):
			recursos.update(propios)
	return recursos


def exportar_paquete_alumno(contexto: Any, ids: Sequence[str], destino: Path) -> int:
	"""Escribe un ``.elab`` con el entorno abierto y solo las actividades elegidas. Devuelve cuántas lleva.

	Lleva únicamente los recursos que esas actividades usan (el audio grabado
	de sus premios) y los demás sonidos e imágenes del entorno; no lleva
	ningún dato de alumnos.
	"""
	entorno = getattr(contexto, "entorno", None)
	if entorno is None:
		raise ValueError(_("No hay ningún entorno abierto."))
	elegidas = [copy.deepcopy(actividad) for actividad in contexto.actividades if str(actividad.get("id", "")) in set(ids)]
	if not elegidas:
		raise ValueError(_("Elija al menos una actividad."))
	recursos = recursos_del_paquete(contexto)
	audios_de_otras = {
		str(premio.get("audio"))
		for actividad in contexto.actividades
		if str(actividad.get("id", "")) not in set(ids)
		for premio in (actividad.get("premios") or [])
		if isinstance(premio, dict) and premio.get("audio")
	}
	audios_propios = {
		str(premio.get("audio"))
		for actividad in elegidas
		for premio in (actividad.get("premios") or [])
		if isinstance(premio, dict) and premio.get("audio")
	}
	sobran = audios_de_otras - audios_propios
	recursos = {nombre: datos for nombre, datos in recursos.items() if nombre not in sobran}
	formato.guardar_paquete(destino, entorno, elegidas, recursos or None)
	return len(elegidas)


def argumentos_probar(ruta_paquete: Path | str, actividad_id: str, alumno: str = "", conexion: Sequence[str] = ()) -> list[str]:
	"""Argumentos del reproductor para jugar una actividad de un paquete."""
	argumentos = [str(ruta_paquete), "--actividad", str(actividad_id)]
	if alumno:
		argumentos += ["--alumno", alumno]
	argumentos += list(conexion)
	return argumentos
