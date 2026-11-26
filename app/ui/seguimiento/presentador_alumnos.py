"""Lógica de la ventana de alumnos, sin wx: filas de la lista, ajustes de juego, paso, lista de trabajo."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from app.core.configuracion import VALORES_POR_DEFECTO
from app.core.i18n import _, _n
from app.seguimiento import grabadora, recompensas
from app.seguimiento.alumnos import Alumno, Fichas
from app.seguimiento.base import BaseSeguimiento, ahora_iso
from app.supervision import protocolo
from app.ui.seguimiento import textos
from app.ui.seguimiento.textos import contar, fecha_legible, leer_numero

log = logging.getLogger(__name__)

# Rangos de los ajustes de juego (los de ``AjustesJuego`` del motor).
PASO_MINIMO, PASO_MAXIMO = 0.25, 1.5
GIRO_MINIMO, GIRO_MAXIMO = 0.0, 180.0
VELOCIDAD_MINIMA, VELOCIDAD_MAXIMA = 0.3, 3.0

# Los de serie son los de las preferencias (``app.core.configuracion``): una sola fuente de verdad.
AJUSTES_DE_SERIE: dict[str, Any] = {
	**{
		clave: VALORES_POR_DEFECTO["juego"][clave]
		for clave in ("modo_movimiento", "paso_m", "giro_grados", "velocidad_ms", "formato_direccion", "unidad")
	},
	"detalle": VALORES_POR_DEFECTO["voz"]["detalle"],
}
CLAVE_LISTA_TRABAJO = "lista_trabajo"
# Nivel de ayudas alcanzado en cada actividad: {"<entorno_id>/<actividad_id>": nivel}. Lo pone al día la incorporación de sesiones.
CLAVE_NIVELES = grabadora.CLAVE_NIVELES


def columnas() -> list[tuple[str, int]]:
	"""Columnas de la lista de alumnos."""
	return [
		(_("Alias"), 170),
		(_("Perfil"), 110),
		(_("Estilo"), 90),
		(_("Última sesión"), 140),
		(_("Sesiones"), 80),
		(_("Estado"), 100),
	]


def fila_de(alumno: Alumno, sesiones: int, ultima: str | None) -> list[str]:
	"""Textos de la fila de un alumno."""
	return [
		alumno.alias,
		textos.nombre(textos.PERFILES, alumno.perfil),
		textos.nombre(textos.ESTILOS, alumno.estilo),
		fecha_legible(ultima) if ultima else _("Ninguna"),
		str(sesiones),
		_("Archivado") if alumno.archivado else _("Activo"),
	]


def filas_alumnos(base: BaseSeguimiento, texto: str = "", incluir_archivados: bool = False) -> list[tuple[Alumno, list[str]]]:
	"""Alumnos que cumplen la búsqueda, con los textos de su fila."""
	cuentas = {
		fila["alumno_id"]: (int(fila["cuantas"]), fila["ultima"])
		for fila in base.consultar("SELECT alumno_id, COUNT(*) AS cuantas, MAX(inicio) AS ultima FROM sesiones GROUP BY alumno_id")
	}
	resultado: list[tuple[Alumno, list[str]]] = []
	for alumno in Fichas(base).buscar(texto, incluir_archivados=incluir_archivados):
		cuantas, ultima = cuentas.get(alumno.id, (0, None))
		resultado.append((alumno, fila_de(alumno, cuantas, ultima)))
	return resultado


def ajustes_completos(ajustes: dict[str, Any] | None, configuracion: Any = None) -> dict[str, Any]:
	"""Ajustes de juego de un alumno con todo lo que falte tomado de las preferencias generales."""
	completos = dict(AJUSTES_DE_SERIE)
	if configuracion is not None:
		for clave in ("modo_movimiento", "paso_m", "giro_grados", "velocidad_ms", "formato_direccion", "unidad"):
			try:
				valor = configuracion.obtener(f"juego.{clave}", None)
			except KeyError, TypeError, ValueError:
				log.debug("No se ha podido leer juego.%s", clave, exc_info=True)
				valor = None
			if valor is not None:
				completos[clave] = valor
		try:
			detalle = configuracion.obtener("voz.detalle", None)
		except KeyError, TypeError, ValueError:
			log.debug("No se ha podido leer voz.detalle", exc_info=True)
			detalle = None
		if isinstance(detalle, int) and not isinstance(detalle, bool):
			completos["detalle"] = detalle
	completos.update({clave: valor for clave, valor in (ajustes or {}).items() if valor is not None})
	return completos


def calcular_paso(metros_texto: str, pasos_texto: str) -> float:
	"""Longitud del paso a partir de «camina N metros y cuenta los pasos».

	Lanza ``ValueError`` con un mensaje para mostrar si los datos no valen o
	el resultado no es un paso humano creíble.
	"""
	try:
		metros = leer_numero(metros_texto)
		pasos = leer_numero(pasos_texto, entero=True)
	except ValueError:
		raise ValueError(_("Escriba los metros y los pasos con números. Los pasos, sin decimales.")) from None
	if metros is None or pasos is None:
		raise ValueError(_("Escriba cuántos metros ha caminado y cuántos pasos ha contado."))
	if metros <= 0 or pasos <= 0:
		raise ValueError(_("Los metros y los pasos deben ser mayores que cero."))
	paso = float(metros) / float(pasos)
	if not PASO_MINIMO <= paso <= PASO_MAXIMO:
		raise ValueError(
			_("Sale un paso de {paso} metros, fuera de lo normal (entre {minimo} y {maximo}). Revise los números.").format(
				paso=textos.decimal(paso, 2), minimo=textos.decimal(PASO_MINIMO, 2), maximo=textos.decimal(PASO_MAXIMO, 2)
			)
		)
	return round(paso, 2)


@dataclass
class DatosFicha:
	"""Lo escrito en el formulario de la ficha, ya convertido."""

	alias: str
	nombre_real: str
	notas: str
	ano_nacimiento: int | None
	perfil: str
	estilo: str
	ajustes: dict[str, Any]


def leer_en_rango(texto: str, minimo: float, maximo: float, nombre: str, entero: bool = False, vacio: bool = False) -> float | int | None:
	"""Número escrito por el usuario dentro de un rango; ``ValueError`` con mensaje concreto si no vale."""
	try:
		valor = leer_numero(texto, entero=entero)
	except ValueError:
		raise ValueError(_("«{nombre}» debe ser un número.").format(nombre=nombre)) from None
	if valor is None:
		if vacio:
			return None
		raise ValueError(_("Escriba un valor en «{nombre}».").format(nombre=nombre))
	if not minimo <= valor <= maximo:
		raise ValueError(
			_("«{nombre}» debe estar entre {minimo} y {maximo}.").format(
				nombre=nombre, minimo=textos.texto_numero(minimo), maximo=textos.texto_numero(maximo)
			)
		)
	return valor


def ano_actual() -> int:
	"""El año en curso (límite superior del año de nacimiento)."""
	return datetime.now().year


def texto_coleccion(base: BaseSeguimiento, alumno_id: int) -> str:
	"""La colección de recompensas del alumno, en frases, para un campo de solo lectura."""
	coleccion = recompensas.coleccion(base, alumno_id)
	lineas = [contar(int(coleccion["estrellas"]), "{n} estrella.", "{n} estrellas.")]
	medallas = coleccion["medallas"]
	lineas.append(contar(len(medallas), "{n} medalla.", "{n} medallas."))
	for medalla in medallas:
		lineas.append(
			_("Medalla: {nombre}, el {fecha}.").format(
				nombre=medalla["nombre"] or _("sin nombre"), fecha=fecha_legible(medalla["fecha"], con_hora=False)
			)
		)
	objetos = coleccion["objetos"]
	lineas.append(contar(len(objetos), "{n} objeto distinto en la colección.", "{n} objetos distintos en la colección."))
	for objeto in objetos:
		veces = int(objeto["veces"])
		lineas.append(_n("{nombre}, {n} vez.", "{nombre}, {n} veces.", veces).format(nombre=objeto["nombre"] or _("sin nombre"), n=veces))
	return "\n".join(lineas)


def resumen_de_borrado(base: BaseSeguimiento, alumno: Alumno) -> str:
	"""Qué se va a borrar con el alumno, para la confirmación fuerte."""
	sesiones = int(base.valor("SELECT COUNT(*) FROM sesiones WHERE alumno_id = ?", (alumno.id,), 0))
	evaluaciones = int(base.valor("SELECT COUNT(*) FROM evaluaciones_reales WHERE alumno_id = ?", (alumno.id,), 0))
	premios = int(base.valor("SELECT COUNT(*) FROM recompensas WHERE alumno_id = ?", (alumno.id,), 0))
	copias = len(base.copias())
	return "\n".join(
		[
			_("Va a borrar por completo al alumno «{alias}» y todo lo suyo:").format(alias=alumno.alias),
			_("- Su ficha, con el nombre real y las notas."),
			contar(
				sesiones,
				"- {n} sesión, con su recorrido, sus notas y sus marcas.",
				"- {n} sesiones, con sus recorridos, sus notas y sus marcas.",
			),
			contar(evaluaciones, "- {n} evaluación en el lugar real.", "- {n} evaluaciones en el lugar real."),
			contar(premios, "- {n} recompensa.", "- {n} recompensas."),
			_("- Sus ficheros de sesión que aún no se hayan incorporado."),
			"",
			contar(
				copias,
				"Además se eliminará {n} copia de seguridad de la base de datos, porque también lo contiene; después se hará una copia nueva sin él.",
				"Además se eliminarán las {n} copias de seguridad de la base de datos, porque también lo contienen; después se hará una copia nueva sin él.",
			),
			"",
			_("ESTO NO SE PUEDE DESHACER. Si quiere conservar algo, cancele y use antes «Exportar datos»."),
		]
	)


def alias_coincide(escrito: str, alias: str) -> bool:
	"""True si lo escrito para confirmar es el alias (sin distinguir mayúsculas ni espacios de más)."""
	return " ".join(escrito.split()).casefold() == " ".join(alias.split()).casefold()


# ── Lista de trabajo ─────────────────────────────────────────────────────────


def lista_de_trabajo(alumno: Alumno) -> list[dict[str, Any]]:
	"""Actividades asignadas al alumno (se guardan en sus ajustes, sin datos personales)."""
	lista = alumno.ajustes.get(CLAVE_LISTA_TRABAJO)
	return [dict(entrada) for entrada in lista if isinstance(entrada, dict)] if isinstance(lista, list) else []


def _misma(entrada: dict[str, Any], entorno_id: str, actividad_id: str) -> bool:
	return entrada.get("entorno_id") == entorno_id and entrada.get("actividad_id") == actividad_id


def tiene_asignada(alumno: Alumno, entorno_id: str, actividad_id: str) -> bool:
	"""True si esa actividad de ese entorno ya está en la lista de trabajo del alumno."""
	return any(_misma(entrada, entorno_id, actividad_id) for entrada in lista_de_trabajo(alumno))


def asignar(fichas: Fichas, alumno: Alumno, entorno: Any, actividad: dict[str, Any], paquete: str = "", asignada: bool = True) -> Alumno:
	"""Pone o quita una actividad en la lista de trabajo de un alumno y guarda la ficha."""
	entorno_id = str(getattr(entorno, "id", "") or "")
	actividad_id = str(actividad.get("id", ""))
	lista = [entrada for entrada in lista_de_trabajo(alumno) if not _misma(entrada, entorno_id, actividad_id)]
	if asignada:
		lista.append(
			{
				"entorno_id": entorno_id,
				"entorno_nombre": str(getattr(entorno, "nombre", "") or ""),
				"paquete": paquete,
				"actividad_id": actividad_id,
				"actividad_nombre": str(actividad.get("nombre", "") or actividad_id),
				"asignada": ahora_iso(),
			}
		)
	ajustes = dict(alumno.ajustes)
	ajustes[CLAVE_LISTA_TRABAJO] = lista
	return fichas.editar(alumno.id, ajustes=ajustes)


def quitar_de_lista(fichas: Fichas, alumno: Alumno, indice: int) -> Alumno:
	"""Quita de la lista de trabajo la entrada de esa posición."""
	lista = lista_de_trabajo(alumno)
	if 0 <= indice < len(lista):
		del lista[indice]
	ajustes = dict(alumno.ajustes)
	ajustes[CLAVE_LISTA_TRABAJO] = lista
	return fichas.editar(alumno.id, ajustes=ajustes)


# ── Niveles y lo que viaja al reproductor ────────────────────────────────────


def clave_nivel(entorno_id: str, actividad_id: str) -> str:
	"""Clave del nivel de una actividad en la ficha: «entorno/actividad» (la misma que usa el reproductor)."""
	return f"{entorno_id}/{actividad_id}"


def niveles_de(alumno: Alumno) -> dict[str, int]:
	"""Nivel de ayudas alcanzado en cada actividad, según la ficha."""
	crudos = alumno.ajustes.get(CLAVE_NIVELES)
	if not isinstance(crudos, dict):
		return {}
	return {
		str(clave): int(nivel) for clave, nivel in crudos.items() if isinstance(nivel, int) and not isinstance(nivel, bool) and nivel >= 0
	}


def datos_para_reproductor(alumno: Alumno) -> dict[str, Any]:
	"""Lo que la orden ``alumno`` de la sala lleva al reproductor: ajustes de juego, lista de trabajo y niveles.

	NUNCA el nombre real, las notas, el año ni el perfil de movilidad: solo lo
	que hace falta para jugar. Se descartan los valores fuera de rango (una
	ficha antigua o tocada a mano no debe impedir enviar el resto) y lo que
	no cabría en un mensaje.
	"""
	ajustes: dict[str, Any] = {}
	for campo, regla in protocolo.AJUSTES_ALUMNO.items():
		valor = alumno.estilo if campo == "estilo" else alumno.ajustes.get(campo)
		if valor is None:
			continue
		clase, primero, segundo = regla
		if clase == "opcion":
			valido = isinstance(valor, str) and valor in primero
		elif clase == "entero":
			valido = isinstance(valor, int) and not isinstance(valor, bool) and primero <= valor <= segundo
		else:
			valido = isinstance(valor, (int, float)) and not isinstance(valor, bool) and primero <= float(valor) <= segundo
			valor = float(valor) if valido else valor
		if valido:
			ajustes[campo] = valor
		else:
			log.warning("Ajuste de juego de una ficha fuera de rango (%s); no se envía al reproductor", campo)
	lista: list[dict[str, str]] = []
	for entrada in lista_de_trabajo(alumno)[: protocolo.LISTA_MAXIMA]:
		limpia = {campo: str(entrada.get(campo) or "")[:maximo] for campo, maximo in protocolo.CAMPOS_LISTA.items()}
		if limpia["actividad_id"]:
			lista.append(limpia)
	niveles = {
		clave: min(nivel, protocolo.NIVEL_MAXIMO) for clave, nivel in niveles_de(alumno).items() if "/" in clave and len(clave) <= 64
	}
	return {"ajustes": ajustes, "lista": lista, "niveles": dict(list(niveles.items())[: protocolo.NIVELES_MAXIMOS])}


def fila_trabajo(entrada: dict[str, Any]) -> list[str]:
	"""Textos de una entrada de la lista de trabajo."""
	return [
		str(entrada.get("actividad_nombre", "")),
		str(entrada.get("entorno_nombre", "")),
		fecha_legible(entrada.get("asignada"), con_hora=False),
	]
