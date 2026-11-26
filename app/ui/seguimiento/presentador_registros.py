"""Lógica de las ventanas de sesiones, informes y cuaderno de evaluación real. Sin wx."""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from datetime import date
from pathlib import Path
from typing import Any

from app.core import paths
from app.core.configuracion import VALORES_POR_DEFECTO
from app.core.i18n import N_, _
from app.seguimiento import cuaderno, informes, sesiones
from app.seguimiento.alumnos import Alumno, Fichas
from app.seguimiento.base import MODOS, BaseSeguimiento
from app.ui.seguimiento import lugares, textos
from app.ui.seguimiento.textos import duracion, fecha_legible, recortar, si_no

log = logging.getLogger(__name__)

# Paso del alumno si su ficha no lo dice: el de serie de las preferencias (app.core.configuracion).
PASO_DE_SERIE_M: float = float(VALORES_POR_DEFECTO["juego"]["paso_m"])

TIPOS_INFORME: dict[str, str] = {
	"sesion": N_("Informe de una sesión"),
	"comparacion": N_("Comparación de varias sesiones"),
	"evolucion": N_("Evolución de un alumno en el tiempo"),
	"examen": N_("Informe de un examen"),
	"real_virtual": N_("Evaluación real frente a sesiones en el simulador"),
}
EXTENSIONES: dict[str, str] = {"texto": ".txt", "html": ".html", "csv": ".csv"}
COMODINES: dict[str, str] = {
	"texto": N_("Texto (*.txt)|*.txt"),
	"html": N_("Página web (*.html)|*.html"),
	"csv": N_("Hoja de cálculo CSV (*.csv)|*.csv"),
}
AYUDA_INFORMES = N_(
	"Los informes son descriptivos: recogen tiempos, distancias, choques y ayudas. No diagnostican ni recomiendan, y el "
	"rendimiento en el simulador no equivale a competencia en el lugar real. Todos terminan con ese aviso."
)


# ── Sesiones ─────────────────────────────────────────────────────────────────


def columnas_sesiones() -> list[tuple[str, int]]:
	"""Columnas de la lista de sesiones."""
	return [
		(_("Fecha"), 130),
		(_("Alumno"), 110),
		(_("Entorno"), 150),
		(_("Actividad"), 150),
		(_("Modo"), 80),
		(_("Tiempo activo"), 100),
		(_("Completada"), 90),
	]


def alias_por_id(base: BaseSeguimiento) -> dict[int, str]:
	"""Alias de cada alumno (también de los archivados), por su id."""
	return {alumno.id: alumno.alias for alumno in Fichas(base).buscar(incluir_archivados=True)}


def fila_sesion(sesion: dict[str, Any], alias: str) -> list[str]:
	"""Textos de la fila de una sesión."""
	estado = si_no(sesion.get("completada"))
	if sesion.get("parcial"):
		estado = _("Sin terminar")
	return [
		fecha_legible(sesion.get("inicio")),
		alias,
		str(sesion.get("entorno_nombre") or sesion.get("entorno_id") or ""),
		str(sesion.get("actividad_nombre") or sesion.get("actividad_id") or _("Sin actividad")),
		textos.nombre(textos.MODOS, sesion.get("modo") or ""),
		duracion(sesion.get("tiempo_activo")),
		estado,
	]


def leer_fecha(texto: str, nombre: str) -> str | None:
	"""Fecha escrita por el usuario como AAAA-MM-DD o DD/MM/AAAA, en ISO. ``None`` si está vacía.

	Lanza ``ValueError`` con un mensaje concreto si no es una fecha.
	"""
	limpio = texto.strip()
	if not limpio:
		return None
	coincide = re.fullmatch(r"(\d{1,2})[/.-](\d{1,2})[/.-](\d{4})", limpio)
	if coincide:
		limpio = f"{coincide.group(3)}-{int(coincide.group(2)):02d}-{int(coincide.group(1)):02d}"
	try:
		return date.fromisoformat(limpio).isoformat()
	except ValueError:
		raise ValueError(_("«{nombre}» debe ser una fecha como 2026-11-20 o 20/11/2026.").format(nombre=nombre)) from None


def valores_de_filtro(base: BaseSeguimiento) -> tuple[list[tuple[str, str]], list[tuple[str, str]]]:
	"""Entornos y actividades que aparecen en las sesiones guardadas, como pares (id, nombre)."""
	entornos = [
		(str(fila["entorno_id"]), str(fila["nombre"] or fila["entorno_id"]))
		for fila in base.consultar("SELECT entorno_id, MAX(entorno_nombre) AS nombre FROM sesiones GROUP BY entorno_id ORDER BY nombre")
	]
	actividades = [
		(str(fila["actividad_id"]), str(fila["nombre"] or fila["actividad_id"] or _("Sin actividad")))
		for fila in base.consultar(
			"SELECT actividad_id, MAX(actividad_nombre) AS nombre FROM sesiones GROUP BY actividad_id ORDER BY nombre"
		)
	]
	return entornos, actividades


def buscar_sesiones(
	base: BaseSeguimiento,
	alumno_id: int | None = None,
	entorno_id: str | None = None,
	actividad_id: str | None = None,
	modo: str | None = None,
	desde: str | None = None,
	hasta: str | None = None,
) -> list[dict[str, Any]]:
	"""Sesiones que cumplen los filtros, de la más reciente a la más antigua."""
	lista = sesiones.listar(
		base,
		alumno_id,
		entorno_id=entorno_id,
		actividad_id=actividad_id,
		modo=modo if modo in MODOS else None,
		desde=desde,
		# «inicio» lleva la hora: para incluir todo el día final se compara con el final de ese día.
		hasta=(hasta + "T99") if hasta else None,
	)
	lista.reverse()
	return lista


def espacios_de(contexto: Any, sesion: dict[str, Any]) -> list[dict[str, Any]]:
	"""Espacios del entorno abierto si es el de la sesión (dan nombre a los lugares del informe)."""
	entorno = getattr(contexto, "entorno", None)
	if entorno is None or str(getattr(entorno, "id", "")) != str(sesion.get("entorno_id") or ""):
		return []
	return lugares.espacios_para_informes(entorno)


def texto_sesion(base: BaseSeguimiento, sesion_id: str, contexto: Any = None) -> str:
	"""Resumen completo y legible de una sesión (el informe de sesión en texto)."""
	sesion = sesiones.obtener(base, sesion_id, con_traza=True)
	if sesion is None:
		return _("La sesión ya no existe.")
	alias = alias_por_id(base).get(sesion["alumno_id"], "")
	informe = informes.informe_sesion(sesion, alias=alias, espacios=espacios_de(contexto, sesion), marcas=sesion.get("marcas"))
	return informes.a_texto(informe)


def fila_marca(marca: dict[str, Any], contexto: Any = None) -> list[str]:
	"""Textos de la fila de una marca del profesional: instante, lugar y nota."""
	entorno = getattr(contexto, "entorno", None)
	lugar = ""
	if entorno is not None and marca.get("planta") and marca.get("x") is not None:
		lugar = lugares.describir_punto(entorno, str(marca["planta"]), marca["x"], marca["y"])
	return [duracion(marca.get("t")), lugar, recortar(str(marca.get("texto") or ""), 200)]


def pasos_del_recorrido(
	base: BaseSeguimiento, sesion: dict[str, Any], contexto: Any = None, unidad: str = "metros", con_tiempos: bool = False
) -> list[str]:
	"""El recorrido de la sesión narrado paso a paso, para repasarlo con las flechas."""
	traza = sesiones.traza(base, sesion["id"])
	alumno = Fichas(base).obtener(sesion["alumno_id"])
	paso = float((alumno.ajustes if alumno else {}).get("paso_m") or PASO_DE_SERIE_M)
	return informes.describir_recorrido(traza, espacios=espacios_de(contexto, sesion), unidad=unidad, paso_m=paso, con_tiempos=con_tiempos)


def puntos_del_recorrido(base: BaseSeguimiento, sesion_id: str) -> tuple[str, list[tuple[float, float]]]:
	"""Planta en la que más se anduvo y los puntos del recorrido en ella (para el plano)."""
	muestras = sesiones.traza(base, sesion_id).get("muestras") or []
	por_planta: dict[str, list[tuple[float, float]]] = {}
	for muestra in muestras:
		if (
			isinstance(muestra, (list, tuple))
			and len(muestra) >= 4
			and isinstance(muestra[2], (int, float))
			and isinstance(muestra[3], (int, float))
		):
			por_planta.setdefault(str(muestra[1]), []).append((float(muestra[2]), float(muestra[3])))
	if not por_planta:
		return "", []
	planta = max(por_planta, key=lambda clave: len(por_planta[clave]))
	return planta, por_planta[planta]


# ── Informes ─────────────────────────────────────────────────────────────────


def construir_informe(
	base: BaseSeguimiento, tipo: str, alumno: Alumno | None, ids: Sequence[str], contexto: Any = None
) -> informes.Informe:
	"""Construye el informe pedido. Lanza ``ValueError`` con un mensaje para mostrar si faltan datos."""
	if alumno is None:
		raise ValueError(_("Elija un alumno."))
	if tipo == "evolucion":
		return informes.evolucion(sesiones.listar(base, alumno.id, incluir_parciales=False), alias=alumno.alias)
	if tipo == "real_virtual":
		return informes.informe_real_frente_virtual(
			cuaderno.listar(base, alumno.id), sesiones.listar(base, alumno.id, incluir_parciales=False), alias=alumno.alias
		)
	elegidas = [sesion for sesion in (sesiones.obtener(base, ident, con_traza=(tipo == "sesion")) for ident in ids) if sesion is not None]
	if tipo == "comparacion":
		if len(elegidas) < 2:
			raise ValueError(_("Marque dos sesiones o más para compararlas."))
		return informes.comparar_sesiones(elegidas, alias=alumno.alias)
	if not elegidas:
		raise ValueError(_("Elija una sesión en la lista."))
	sesion = elegidas[0]
	if tipo == "examen":
		return informes.informe_examen(sesion, alias=alumno.alias)
	return informes.informe_sesion(sesion, alias=alumno.alias, espacios=espacios_de(contexto, sesion), marcas=sesion.get("marcas"))


def nombre_de_fichero(informe: informes.Informe, alias: str, formato: str) -> str:
	"""Nombre propuesto para guardar un informe (sin caracteres que Windows no admite)."""
	base = f"{informe.titulo} - {alias}" if alias else informe.titulo
	limpio = re.sub(r'[\\/:*?"<>|]+', " ", base)
	return " ".join(limpio.split())[:120] + EXTENSIONES.get(formato, ".txt")


def guardar_informe(informe: informes.Informe, ruta: Path, formato: str) -> Path:
	"""Guarda el informe en ``ruta`` con el formato pedido (se le pone la extensión si falta)."""
	extension = EXTENSIONES[formato]
	if ruta.suffix.lower() not in (extension, ".htm" if formato == "html" else extension):
		ruta = ruta.with_name(ruta.name + extension)
	return informes.guardar(informe, ruta, formato)


def html_temporal(informe: informes.Informe) -> Path:
	"""Escribe el informe en HTML en la carpeta temporal para abrirlo en el navegador. Quien llama lo borra al cerrar."""
	carpeta = paths.ruta_temporales() / "informes"
	carpeta.mkdir(parents=True, exist_ok=True)
	numero = 1
	while (carpeta / f"informe-{numero}.html").exists():
		numero += 1
	return informes.guardar(informe, carpeta / f"informe-{numero}.html", "html")


# ── Cuaderno de evaluación real ──────────────────────────────────────────────


def columnas_evaluaciones() -> list[tuple[str, int]]:
	"""Columnas de la lista de evaluaciones reales."""
	return [
		(_("Fecha"), 100),
		(_("Lugar"), 180),
		(_("Entorno del simulador"), 160),
		(_("Rutas"), 220),
		(_("Nivel de ayuda"), 160),
		(_("Días desde el entrenamiento"), 150),
	]


def resumen_rutas(rutas: Sequence[dict[str, Any]]) -> str:
	"""«2 de 3 conseguidas sin ayuda» y, si las hay, cuántas con ayuda."""
	if not rutas:
		return _("Sin rutas anotadas")
	solas = sum(1 for ruta in rutas if ruta.get("resultado") == "conseguida")
	ayudadas = sum(1 for ruta in rutas if ruta.get("resultado") == "con_ayuda")
	texto = _("{solas} de {total} conseguidas sin ayuda").format(solas=solas, total=len(rutas))
	if ayudadas:
		texto += _(", {n} con ayuda").format(n=ayudadas)
	return texto


def fila_evaluacion(evaluacion: cuaderno.EvaluacionReal) -> list[str]:
	"""Textos de la fila de una evaluación real."""
	dias = evaluacion.dias_desde_entrenamiento
	return [
		fecha_legible(evaluacion.fecha, con_hora=False),
		evaluacion.lugar,
		evaluacion.entorno_nombre,
		resumen_rutas(evaluacion.rutas),
		_(cuaderno.NIVELES_AYUDA.get(evaluacion.nivel_ayuda, evaluacion.nivel_ayuda)),
		str(dias) if dias is not None else _("Sin sesiones anteriores"),
	]


def fila_ruta(ruta: dict[str, Any]) -> list[str]:
	"""Textos de la fila de una ruta de la evaluación."""
	return [
		str(ruta.get("nombre", "")),
		_(cuaderno.RESULTADOS_RUTA.get(str(ruta.get("resultado", "")), str(ruta.get("resultado", "")))),
		str(ruta.get("notas", "")),
	]


def texto_dias(base: BaseSeguimiento, alumno_id: int, fecha: str | None, entorno_id: str) -> str:
	"""Frase con los días desde el último entrenamiento en el simulador (se calcula, no se escribe)."""
	if not fecha:
		return _("Escriba la fecha para calcularlo.")
	dias = cuaderno.dias_desde_ultima_sesion(base, alumno_id, fecha, entorno_id)
	if dias is None:
		return _("No hay sesiones anteriores en el simulador{en}.").format(en=_(" en ese entorno") if entorno_id else "")
	return textos.contar(dias, "{n} día desde la última sesión en el simulador.", "{n} días desde la última sesión en el simulador.")


def texto_evaluacion(evaluacion: cuaderno.EvaluacionReal, alias: str) -> str:
	"""Una evaluación real completa, en texto, para leerla con calma."""
	lineas = [
		_("Evaluación en el lugar real de {alias}").format(alias=alias),
		"",
		_("Fecha: {fecha}.").format(fecha=fecha_legible(evaluacion.fecha, con_hora=False)),
		_("Lugar: {lugar}.").format(lugar=evaluacion.lugar or _("sin indicar")),
		_("Entorno del simulador relacionado: {entorno}.").format(entorno=evaluacion.entorno_nombre or _("ninguno")),
		_("Nivel de ayuda: {nivel}.").format(nivel=_(cuaderno.NIVELES_AYUDA.get(evaluacion.nivel_ayuda, evaluacion.nivel_ayuda))),
		_("Tipo de recorrido: {tipo}.").format(tipo=_(cuaderno.TIPOS_RECORRIDO.get(evaluacion.tipo_recorrido, evaluacion.tipo_recorrido))),
		_("Ayudas de movilidad usadas: {ayudas}.").format(ayudas=", ".join(evaluacion.ayudas_movilidad) or _("sin indicar")),
	]
	dias = evaluacion.dias_desde_entrenamiento
	lineas.append(
		textos.contar(
			dias, "Días desde el último entrenamiento en el simulador: {n}.", "Días desde el último entrenamiento en el simulador: {n}."
		)
		if dias is not None
		else _("No había sesiones anteriores en el simulador.")
	)
	lineas.append("")
	lineas.append(_("Rutas: {resumen}.").format(resumen=resumen_rutas(evaluacion.rutas)))
	for ruta in evaluacion.rutas:
		fila = fila_ruta(ruta)
		lineas.append(_("- {nombre}: {resultado}. {notas}").format(nombre=fila[0], resultado=fila[1], notas=fila[2]).rstrip())
	if evaluacion.observaciones:
		lineas.extend(["", _("Observaciones: {texto}").format(texto=evaluacion.observaciones)])
	lineas.extend(["", _(informes.AVISO)])
	return "\n".join(lineas)


def entornos_para_evaluar(base: BaseSeguimiento, contexto: Any = None) -> list[tuple[str, str]]:
	"""Entornos con los que se puede relacionar una evaluación: el abierto y los de las sesiones guardadas."""
	pares, _actividades = valores_de_filtro(base)
	entorno = getattr(contexto, "entorno", None)
	if entorno is not None and str(entorno.id) not in [ident for ident, _nombre in pares]:
		pares.insert(0, (str(entorno.id), str(entorno.nombre or entorno.id)))
	return pares


def separar_ayudas(texto: str) -> list[str]:
	"""«bastón largo, perro guía» → lista de ayudas de movilidad."""
	return [parte.strip() for parte in re.split(r"[,;\n]+", texto) if parte.strip()]
