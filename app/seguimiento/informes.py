"""Informes del seguimiento en texto plano, HTML accesible y CSV.

Los informes son DESCRIPTIVOS: recogen tiempos, distancias, choques y ayudas.
Nunca diagnostican, nunca recomiendan, nunca dicen que un cruce real sea
seguro, y todos llevan el aviso de que el rendimiento en el simulador no
equivale a competencia en el lugar real. Esa regla condiciona la redacción:
se escribe «el tiempo pasó de 5 a 3 minutos», no «el alumno ha mejorado».

Diseño: cada función ``informe_*`` construye un ``Informe`` (título,
secciones, tablas) sin formato; ``a_texto``, ``a_html`` y ``a_csv`` lo
convierten. Así los tres formatos dicen exactamente lo mismo.

Accesibilidad del HTML: un solo ``h1``, secciones con ``h2``, tablas
pequeñas con ``caption`` y cabeceras ``th`` con ``scope``, idioma declarado,
nada que dependa del color ni de la posición, sin scripts ni recursos externos.

Las sesiones llegan como diccionarios, tal como los da ``sesiones.obtener``.
"""

from __future__ import annotations

import csv
import html
import io
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from app.core.configuracion import VALORES_POR_DEFECTO
from app.core.i18n import N_, _, _n, idioma_actual
from app.seguimiento import cuaderno, medidas

# Paso de serie para narrar en pasos: el de las preferencias (app.core.configuracion).
PASO_DE_SERIE_M: float = float(VALORES_POR_DEFECTO["juego"]["paso_m"])

AVISO = N_(
	"Este informe es descriptivo: recoge tiempos, distancias, choques y ayudas pedidas. "
	"El rendimiento en el simulador no equivale a competencia en el lugar real. "
	"EntornoLab es una herramienta educativa y de entrenamiento: no diagnostica, no trata "
	"y no sustituye al aprendizaje real con un profesional."
)

LIMITES_ESTRATEGIA = N_(
	"La forma de explorar se deduce de la geometría del recorrido con una regla sencilla. "
	"Es una descripción aproximada, no una valoración: no indica si la estrategia era adecuada."
)

NOMBRES_ESTRATEGIA: dict[str, str] = {
	"perimetro": N_("Por el perímetro"),
	"cuadricula": N_("En cuadrícula"),
	"objeto_a_objeto": N_("De objeto en objeto"),
	"sin_patron": N_("Sin patrón reconocible"),
	"insuficiente": N_("Recorrido demasiado corto para describirlo"),
}
NOMBRES_CONFIANZA: dict[str, str] = {"alta": N_("alta"), "media": N_("media"), "baja": N_("baja")}
NOMBRES_MODO: dict[str, str] = {"juego": N_("Juego"), "practica": N_("Práctica"), "examen": N_("Examen")}

# Nombres legibles de los campos habituales de las puntuaciones de examen.
_CAMPOS_EXAMEN: dict[str, str] = {
	"t": N_("Instante"),
	"prueba": N_("Prueba"),
	"ruta": N_("Ruta"),
	"nombre": N_("Nombre"),
	"acierto": N_("Acierto"),
	"conseguida": N_("Conseguida"),
	"tiempo_s": N_("Tiempo"),
	"puntos": N_("Puntos"),
	"error_grados": N_("Error al señalar (grados)"),
	"cociente": N_("Camino real / óptimo"),
	"distancia_m": N_("Distancia"),
}

_CARDINALES = (N_("norte"), N_("nordeste"), N_("este"), N_("sureste"), N_("sur"), N_("suroeste"), N_("oeste"), N_("noroeste"))


# ── Estructura neutra ────────────────────────────────────────────────────────


@dataclass
class Tabla:
	"""Tabla pequeña con título y cabeceras; la primera columna identifica la fila."""

	titulo: str
	cabeceras: list[str]
	filas: list[list[str]] = field(default_factory=list)


@dataclass
class Seccion:
	"""Sección con título y bloques en orden: párrafo (str), lista (list[str]) o ``Tabla``."""

	titulo: str
	bloques: list[str | list[str] | Tabla] = field(default_factory=list)


@dataclass
class Informe:
	"""Informe sin formato. ``aviso`` se escribe siempre al final."""

	titulo: str
	secciones: list[Seccion] = field(default_factory=list)
	aviso: str = ""


# ── Formato de valores ───────────────────────────────────────────────────────


def _decimal(valor: float, decimales: int = 1) -> str:
	texto = f"{valor:.{decimales}f}"
	return texto.replace(".", ",") if idioma_actual() == "es" else texto


def _duracion(segundos: Any) -> str:
	"""«3 min 20 s»: se lee bien con voz y no se confunde con una hora."""
	if not isinstance(segundos, (int, float)) or isinstance(segundos, bool) or not math.isfinite(segundos):
		return _("sin dato")
	total = int(round(segundos))
	horas, resto = divmod(total, 3600)
	minutos, segs = divmod(resto, 60)
	if horas:
		return _("{h} h {m} min {s} s").format(h=horas, m=minutos, s=segs)
	if minutos:
		return _("{m} min {s} s").format(m=minutos, s=segs)
	return _("{s} s").format(s=segs)


def _metros(valor: Any) -> str:
	if not isinstance(valor, (int, float)) or isinstance(valor, bool):
		return _("sin dato")
	return _("{valor} m").format(valor=_decimal(float(valor)))


def _numero(valor: Any, decimales: int = 2) -> str:
	if isinstance(valor, bool):
		return _("sí") if valor else _("no")
	if isinstance(valor, int):
		return str(valor)
	if isinstance(valor, float):
		return _decimal(valor, decimales)
	if valor is None:
		return _("sin dato")
	return str(valor)


def _fecha(iso: Any) -> str:
	"""Fecha y hora locales legibles; si no se entiende, el texto tal cual."""
	if not isinstance(iso, str) or not iso:
		return _("sin dato")
	try:
		momento = datetime.fromisoformat(iso)
	except ValueError:
		return iso
	if momento.tzinfo is not None:
		momento = momento.astimezone()
	return momento.strftime("%d/%m/%Y %H:%M")


def _si_no(valor: Any) -> str:
	return _("sí") if valor else _("no")


def _nombre_espacio(ident: str, nombres: Mapping[str, str]) -> str:
	if not ident:
		return _("lugar sin identificar")
	return nombres.get(ident) or ident


def _nombres_de(resumen: Mapping[str, Any], espacios: Sequence[Mapping[str, Any]] = ()) -> dict[str, str]:
	nombres = {str(e.get("id", "")): str(e.get("nombre", "")) for e in espacios if e.get("nombre")}
	datos = resumen.get("espacios") or {}
	for clave in ("visitados", "no_visitados"):
		for espacio in datos.get(clave) or []:
			if isinstance(espacio, Mapping) and espacio.get("nombre"):
				nombres.setdefault(str(espacio.get("id", "")), str(espacio["nombre"]))
	return nombres


def _total(resumen: Mapping[str, Any], clave: str) -> Any:
	valor = resumen.get(clave)
	return valor.get("total") if isinstance(valor, Mapping) else None


# ── Informe de una sesión ────────────────────────────────────────────────────


def _seccion_datos(sesion: Mapping[str, Any], alias: str) -> Seccion:
	filas = []
	if alias:
		filas.append([_("Alumno (alias)"), alias])
	filas += [
		[_("Entorno"), sesion.get("entorno_nombre") or _("sin dato")],
		[_("Actividad"), sesion.get("actividad_nombre") or _("sin actividad")],
		[_("Modo"), _(NOMBRES_MODO.get(str(sesion.get("modo")), str(sesion.get("modo", ""))))],
		[_("Inicio"), _fecha(sesion.get("inicio"))],
		[_("Fin"), _fecha(sesion.get("fin"))],
		[_("Actividad completada"), _si_no(sesion.get("completada"))],
	]
	seccion = Seccion(_("Datos de la sesión"), [Tabla(_("Datos de la sesión"), [_("Dato"), _("Valor")], filas)])
	if sesion.get("parcial"):
		seccion.bloques.append(_("La sesión no terminó con normalidad: estos datos proceden de un guardado automático."))
	return seccion


def _seccion_recorrido(resumen: Mapping[str, Any]) -> Seccion:
	giros = resumen.get("giros") or {}
	pausas = resumen.get("pausas") or {}
	filas = [
		[_("Tiempo activo"), _duracion(resumen.get("tiempo_activo_s"))],
		[_("Tiempo en pausa"), _duracion(resumen.get("tiempo_pausa_s"))],
		[_("Número de pausas"), _numero(pausas.get("numero", 0))],
		[_("Tiempo en movimiento"), _duracion(resumen.get("tiempo_en_movimiento_s"))],
		[_("Distancia recorrida"), _metros(resumen.get("distancia_m"))],
	]
	if resumen.get("velocidad_media_ms") is not None:
		filas.append([_("Velocidad media"), _("{valor} m/s").format(valor=_decimal(float(resumen["velocidad_media_ms"]), 2))])
	if resumen.get("camino_optimo_m") is not None:
		filas.append([_("Longitud del camino más corto"), _metros(resumen.get("camino_optimo_m"))])
	if resumen.get("cociente_camino") is not None:
		filas.append([_("Camino real dividido entre camino más corto"), _numero(float(resumen["cociente_camino"]))])
	filas += [
		[_("Giros"), _numero(giros.get("numero", 0))],
		[_("Giros a la izquierda"), _numero(giros.get("izquierda", 0))],
		[_("Giros a la derecha"), _numero(giros.get("derecha", 0))],
		[_("Medias vueltas"), _numero(giros.get("medias_vueltas", 0))],
	]
	seccion = Seccion(_("Tiempos y recorrido"), [Tabla(_("Tiempos y recorrido"), [_("Medida"), _("Valor")], filas)])
	if resumen.get("cociente_camino") is not None:
		seccion.bloques.append(_("Un cociente de 1 significa que el recorrido midió lo mismo que el camino más corto; 2, el doble."))
	if resumen.get("saltos"):
		seccion.bloques.append(
			_n(
				"Hubo {n} recolocación (no cuenta como distancia andada).",
				"Hubo {n} recolocaciones (no cuentan como distancia andada).",
				int(resumen["saltos"]),
			).format(n=int(resumen["saltos"]))
		)
	return seccion


def _seccion_choques(resumen: Mapping[str, Any], nombres: Mapping[str, str]) -> Seccion:
	choques = resumen.get("choques") or {}
	total = int(choques.get("total", 0) or 0)
	seccion = Seccion(_("Choques"), [_n("{n} choque.", "{n} choques.", total).format(n=total)])
	por_espacio = choques.get("por_espacio") or {}
	if por_espacio:
		filas = [
			[_nombre_espacio(str(ident), nombres), str(cuenta)] for ident, cuenta in sorted(por_espacio.items(), key=lambda par: -par[1])
		]
		seccion.bloques.append(Tabla(_("Choques por espacio"), [_("Espacio"), _("Choques")], filas))
	lugares = choques.get("lugares") or []
	if lugares:
		filas = []
		for choque in lugares[:40]:
			filas.append(
				[
					_duracion(choque.get("t")),
					_nombre_espacio(str(choque.get("espacio", "")), nombres),
					str(choque.get("con") or _("sin dato")),
				]
			)
		seccion.bloques.append(Tabla(_("Choques por orden"), [_("Instante"), _("Espacio"), _("Con qué")], filas))
		if len(lugares) > 40:
			seccion.bloques.append(_("Se muestran los 40 primeros; el resto está en la exportación completa."))
	return seccion


def _seccion_ayudas(resumen: Mapping[str, Any]) -> Seccion:
	ayudas = resumen.get("ayudas") or {}
	total = int(ayudas.get("total", 0) or 0)
	seccion = Seccion(_("Ayudas pedidas"), [_n("{n} ayuda pedida.", "{n} ayudas pedidas.", total).format(n=total)])
	por_tipo = ayudas.get("por_tipo") or {}
	if por_tipo:
		filas = [[str(tipo), str(cuenta)] for tipo, cuenta in sorted(por_tipo.items(), key=lambda par: -par[1])]
		seccion.bloques.append(Tabla(_("Ayudas por tipo"), [_("Ayuda"), _("Veces")], filas))
	return seccion


def _seccion_logros(resumen: Mapping[str, Any]) -> Seccion | None:
	logros: list[tuple[float, str, str]] = []
	for clase, clave in ((_("Objetivo"), "objetivos"), (_("Premio"), "premios")):
		for logro in resumen.get(clave) or []:
			instante = logro.get("t") if isinstance(logro.get("t"), (int, float)) else 0.0
			logros.append((float(instante), clase, str(logro.get("nombre") or logro.get("id") or _("sin nombre"))))
	if not logros:
		return None
	logros.sort(key=lambda logro: logro[0])
	filas = [[_duracion(instante), clase, nombre] for instante, clase, nombre in logros]
	return Seccion(
		_("Objetivos y premios"), [Tabla(_("Objetivos y premios, con su instante"), [_("Instante"), _("Clase"), _("Nombre")], filas)]
	)


def _seccion_espacios(resumen: Mapping[str, Any], nombres: Mapping[str, str]) -> Seccion | None:
	datos = resumen.get("espacios") or {}
	visitados = datos.get("visitados") or []
	no_visitados = datos.get("no_visitados") or []
	if not visitados and not no_visitados:
		return None
	seccion = Seccion(_("Espacios visitados y sin visitar"))
	seccion.bloques.append(_("Visitados: {v} de {t}.").format(v=len(visitados), t=len(visitados) + len(no_visitados)))
	if visitados:
		filas = [
			[
				_nombre_espacio(str(e.get("id", "")), nombres) if not e.get("nombre") else str(e["nombre"]),
				_duracion(e.get("primera_vez_s")),
				str(e.get("entradas", 0)),
				_duracion(e.get("tiempo_s")),
			]
			for e in visitados
		]
		seccion.bloques.append(
			Tabla(_("Espacios visitados"), [_("Espacio"), _("Primera entrada"), _("Entradas"), _("Tiempo dentro")], filas)
		)
	if no_visitados:
		seccion.bloques.append(_("Espacios sin visitar:"))
		seccion.bloques.append([str(e.get("nombre") or e.get("id") or "") for e in no_visitados])
	return seccion


def _seccion_estrategia(resumen: Mapping[str, Any]) -> Seccion:
	estrategia = resumen.get("estrategia") or {}
	tipo = str(estrategia.get("tipo", "insuficiente"))
	seccion = Seccion(_("Forma de explorar"))
	seccion.bloques.append(
		_("{nombre}. Confianza de la clasificación: {confianza}.").format(
			nombre=_(NOMBRES_ESTRATEGIA.get(tipo, tipo)),
			confianza=_(NOMBRES_CONFIANZA.get(str(estrategia.get("confianza", "baja")), "baja")),
		)
	)
	if estrategia.get("aproximada"):
		seccion.bloques.append(_("No había contornos de los espacios: se ha usado una aproximación."))
	seccion.bloques.append(_(LIMITES_ESTRATEGIA))
	return seccion


def _seccion_profesional(sesion: Mapping[str, Any], marcas: Sequence[Mapping[str, Any]]) -> Seccion | None:
	resumen = sesion.get("resumen") or {}
	intervenciones = resumen.get("intervenciones") or {}
	notas = str(sesion.get("notas") or "")
	if not intervenciones.get("total") and not marcas and not notas:
		return None
	seccion = Seccion(_("Intervenciones y notas del profesional"))
	por_tipo = intervenciones.get("por_tipo") or {}
	if por_tipo:
		seccion.bloques.append(
			Tabla(_("Intervenciones durante la sesión"), [_("Intervención"), _("Veces")], [[str(t), str(n)] for t, n in por_tipo.items()])
		)
	if marcas:
		filas = [[_duracion(m.get("t")), str(m.get("texto") or _("marca sin nota"))] for m in marcas]
		seccion.bloques.append(Tabla(_("Marcas del profesional"), [_("Instante"), _("Nota")], filas))
	if notas:
		seccion.bloques.append(_("Notas: {notas}").format(notas=notas))
	return seccion


def _seccion_examen(resumen: Mapping[str, Any]) -> Seccion | None:
	examen = resumen.get("examen")
	if not isinstance(examen, Mapping) or not examen:
		return None
	seccion = Seccion(_("Puntuaciones del examen"))
	sueltos = [[_(_CAMPOS_EXAMEN.get(str(k), str(k))), _numero(v)] for k, v in examen.items() if not isinstance(v, (list, dict))]
	if sueltos:
		seccion.bloques.append(Tabla(_("Resultado del examen"), [_("Dato"), _("Valor")], sueltos))
	for clave, valor in examen.items():
		if not isinstance(valor, list) or not valor or not all(isinstance(fila, Mapping) for fila in valor):
			continue
		columnas: list[str] = []
		for fila in valor:
			for campo in fila:
				if str(campo) not in columnas and not isinstance(fila[campo], (list, dict)):
					columnas.append(str(campo))
		filas = []
		for fila in valor:
			celdas = []
			for campo in columnas:
				dato = fila.get(campo)
				celdas.append(_duracion(dato) if campo in ("t", "tiempo_s") else _numero(dato))
			filas.append(celdas)
		titulo = _("Pruebas del examen") if clave == "pruebas" else str(clave)
		seccion.bloques.append(Tabla(titulo, [_(_CAMPOS_EXAMEN.get(c, c)) for c in columnas], filas))
	seccion.bloques.append(
		_("El tiempo en pausa no cuenta en el examen. Las puntuaciones son las que calculó el programa, sin interpretar.")
	)
	return seccion


def informe_sesion(
	sesion: Mapping[str, Any],
	*,
	alias: str = "",
	espacios: Sequence[Mapping[str, Any]] = (),
	marcas: Sequence[Mapping[str, Any]] | None = None,
) -> Informe:
	"""Informe de una sesión: datos, tiempos, choques, ayudas, logros, espacios y forma de explorar."""
	resumen = sesion.get("resumen") or {}
	nombres = _nombres_de(resumen, espacios)
	lista_marcas = list(marcas if marcas is not None else sesion.get("marcas") or [])
	titulo = _("Informe de sesión: {entorno}").format(entorno=sesion.get("entorno_nombre") or _("entorno sin nombre"))
	informe = Informe(titulo, aviso=_(AVISO))
	candidatas = [
		_seccion_datos(sesion, alias),
		_seccion_recorrido(resumen),
		_seccion_choques(resumen, nombres),
		_seccion_ayudas(resumen),
		_seccion_logros(resumen),
		_seccion_espacios(resumen, nombres),
		_seccion_estrategia(resumen),
		_seccion_examen(resumen),
		_seccion_profesional(sesion, lista_marcas),
	]
	informe.secciones = [seccion for seccion in candidatas if seccion is not None]
	return informe


def informe_examen(sesion: Mapping[str, Any], *, alias: str = "") -> Informe:
	"""Informe de un examen: puntuaciones primero, y después tiempos, choques y ayudas."""
	resumen = sesion.get("resumen") or {}
	titulo = _("Informe de examen: {actividad}").format(actividad=sesion.get("actividad_nombre") or _("examen sin nombre"))
	informe = Informe(titulo, aviso=_(AVISO))
	examen = _seccion_examen(resumen)
	if examen is None:
		examen = Seccion(_("Puntuaciones del examen"), [_("Esta sesión no tiene puntuaciones de examen.")])
	informe.secciones = [
		_seccion_datos(sesion, alias),
		examen,
		_seccion_recorrido(resumen),
		_seccion_choques(resumen, _nombres_de(resumen)),
		_seccion_ayudas(resumen),
	]
	return informe


# ── Comparación y evolución ──────────────────────────────────────────────────

_CABECERAS_SERIE = (
	N_("Fecha"),
	N_("Completada"),
	N_("Tiempo activo"),
	N_("Distancia"),
	N_("Choques"),
	N_("Ayudas"),
	N_("Camino real / más corto"),
)


def _fila_serie(sesion: Mapping[str, Any]) -> list[str]:
	resumen = sesion.get("resumen") or {}
	cociente = resumen.get("cociente_camino")
	return [
		_fecha(sesion.get("inicio")),
		_si_no(sesion.get("completada")),
		_duracion(resumen.get("tiempo_activo_s", sesion.get("tiempo_activo"))),
		_metros(resumen.get("distancia_m")),
		_numero(_total(resumen, "choques") or 0),
		_numero(_total(resumen, "ayudas") or 0),
		_numero(float(cociente)) if isinstance(cociente, (int, float)) else _("sin dato"),
	]


def _ordenadas(lista: Sequence[Mapping[str, Any]]) -> list[Mapping[str, Any]]:
	return sorted(lista, key=lambda s: str(s.get("inicio", "")))


def _frase_cambio(nombre: str, antes: str, despues: str) -> str:
	if antes == despues:
		return _("{nombre}: {valor} en las dos.").format(nombre=nombre, valor=antes)
	return _("{nombre}: de {antes} a {despues}.").format(nombre=nombre, antes=antes, despues=despues)


def comparar_sesiones(lista: Sequence[Mapping[str, Any]], *, alias: str = "") -> Informe:
	"""Compara varias sesiones del mismo alumno (y, normalmente, del mismo entorno y actividad).

	Describe las diferencias entre la primera y la última sin calificarlas.
	"""
	if len({s.get("alumno_id") for s in lista}) > 1:
		raise ValueError("comparar_sesiones solo compara sesiones de un mismo alumno")
	ordenadas = _ordenadas(lista)
	informe = Informe(_("Comparación de sesiones"), aviso=_(AVISO))
	if not ordenadas:
		informe.secciones.append(Seccion(_("Sesiones comparadas"), [_("No hay sesiones que comparar.")]))
		return informe
	seccion = Seccion(_("Sesiones comparadas"))
	if alias:
		seccion.bloques.append(_("Alumno (alias): {alias}.").format(alias=alias))
	entornos = {str(s.get("entorno_nombre") or s.get("entorno_id") or "") for s in ordenadas}
	actividades = {str(s.get("actividad_nombre") or s.get("actividad_id") or "") for s in ordenadas}
	if len(entornos) == 1:
		seccion.bloques.append(_("Entorno: {nombre}.").format(nombre=next(iter(entornos)) or _("sin dato")))
	else:
		seccion.bloques.append(_("Atención: las sesiones son de entornos distintos; las medidas no son comparables entre sí."))
	if len(actividades) > 1:
		seccion.bloques.append(_("Atención: las sesiones son de actividades distintas."))
	seccion.bloques.append(
		Tabla(
			_("Medidas de cada sesión, de la más antigua a la más reciente"),
			[_(c) for c in _CABECERAS_SERIE],
			[_fila_serie(s) for s in ordenadas],
		)
	)
	informe.secciones.append(seccion)
	if len(ordenadas) >= 2:
		primera = _fila_serie(ordenadas[0])
		ultima = _fila_serie(ordenadas[-1])
		cambios = [_frase_cambio(_(_CABECERAS_SERIE[i]), primera[i], ultima[i]) for i in range(2, len(_CABECERAS_SERIE))]
		informe.secciones.append(Seccion(_("De la primera a la última sesión"), [cambios]))
	return informe


def evolucion(lista: Sequence[Mapping[str, Any]], *, alias: str = "") -> Informe:
	"""Evolución en el tiempo de un alumno: resumen por entorno y serie de cada actividad."""
	ordenadas = _ordenadas(lista)
	informe = Informe(_("Evolución en el tiempo"), aviso=_(AVISO))
	general = Seccion(_("Resumen"))
	if alias:
		general.bloques.append(_("Alumno (alias): {alias}.").format(alias=alias))
	if not ordenadas:
		general.bloques.append(_("No hay sesiones guardadas."))
		informe.secciones.append(general)
		return informe
	total_activo = sum(float((s.get("resumen") or {}).get("tiempo_activo_s") or s.get("tiempo_activo") or 0.0) for s in ordenadas)
	general.bloques.append(
		_n("{n} sesión entre el {a} y el {b}.", "{n} sesiones entre el {a} y el {b}.", len(ordenadas)).format(
			n=len(ordenadas), a=_fecha(ordenadas[0].get("inicio")), b=_fecha(ordenadas[-1].get("inicio"))
		)
	)
	general.bloques.append(_("Tiempo activo total: {t}.").format(t=_duracion(total_activo)))
	por_entorno: dict[str, list[Mapping[str, Any]]] = {}
	for sesion in ordenadas:
		por_entorno.setdefault(str(sesion.get("entorno_nombre") or sesion.get("entorno_id") or _("entorno sin nombre")), []).append(sesion)
	filas = []
	for nombre, grupo in por_entorno.items():
		filas.append(
			[
				nombre,
				str(len(grupo)),
				_fecha(grupo[0].get("inicio")),
				_fecha(grupo[-1].get("inicio")),
				str(sum(1 for s in grupo if s.get("completada"))),
			]
		)
	general.bloques.append(
		Tabla(_("Sesiones por entorno"), [_("Entorno"), _("Sesiones"), _("Primera"), _("Última"), _("Completadas")], filas)
	)
	informe.secciones.append(general)
	grupos: dict[tuple[str, str], list[Mapping[str, Any]]] = {}
	for sesion in ordenadas:
		clave = (
			str(sesion.get("entorno_nombre") or sesion.get("entorno_id") or _("entorno sin nombre")),
			str(sesion.get("actividad_nombre") or sesion.get("actividad_id") or _("sin actividad")),
		)
		grupos.setdefault(clave, []).append(sesion)
	for (entorno, actividad), grupo in grupos.items():
		titulo = _("{entorno}: {actividad}").format(entorno=entorno, actividad=actividad)
		informe.secciones.append(Seccion(titulo, [Tabla(titulo, [_(c) for c in _CABECERAS_SERIE], [_fila_serie(s) for s in grupo])]))
	return informe


def informe_real_frente_virtual(
	evaluaciones: Sequence[Any],
	lista: Sequence[Mapping[str, Any]],
	*,
	alias: str = "",
) -> Informe:
	"""Pone juntas las evaluaciones en el lugar real y las sesiones del simulador del mismo entorno.

	Solo las coloca una junto a otra: no calcula correlaciones ni saca
	conclusiones. Las evaluaciones son ``cuaderno.EvaluacionReal``.
	"""
	informe = Informe(_("Evaluación real frente a sesiones en el simulador"), aviso=_(AVISO))
	if alias:
		informe.secciones.append(Seccion(_("Alumno"), [_("Alumno (alias): {alias}.").format(alias=alias)]))
	if not evaluaciones:
		informe.secciones.append(Seccion(_("Evaluaciones reales"), [_("No hay evaluaciones reales anotadas.")]))
		return informe
	for evaluacion in sorted(evaluaciones, key=lambda e: e.fecha):
		titulo = _("Evaluación real del {fecha}: {lugar}").format(
			fecha=_fecha_corta(evaluacion.fecha), lugar=evaluacion.lugar or evaluacion.entorno_nombre or _("lugar sin indicar")
		)
		seccion = Seccion(titulo)
		filas = [
			[_("Fecha"), _fecha_corta(evaluacion.fecha)],
			[_("Lugar"), evaluacion.lugar or _("sin dato")],
			[_("Entorno del simulador"), evaluacion.entorno_nombre or _("sin dato")],
			[_("Nivel de ayuda"), _(cuaderno.NIVELES_AYUDA.get(evaluacion.nivel_ayuda, evaluacion.nivel_ayuda))],
			[_("Tipo de recorrido"), _(cuaderno.TIPOS_RECORRIDO.get(evaluacion.tipo_recorrido, evaluacion.tipo_recorrido))],
			[_("Ayudas de movilidad usadas"), ", ".join(evaluacion.ayudas_movilidad) or _("sin dato")],
			[
				_("Días desde el último entrenamiento en el simulador"),
				_numero(evaluacion.dias_desde_entrenamiento) if evaluacion.dias_desde_entrenamiento is not None else _("sin dato"),
			],
		]
		seccion.bloques.append(Tabla(_("En el lugar real"), [_("Dato"), _("Valor")], filas))
		if evaluacion.rutas:
			rutas = [
				[
					str(r.get("nombre", "")),
					_(cuaderno.RESULTADOS_RUTA.get(str(r.get("resultado", "")), str(r.get("resultado", "")))),
					str(r.get("notas", "")),
				]
				for r in evaluacion.rutas
			]
			seccion.bloques.append(Tabla(_("Rutas realizadas en el lugar real"), [_("Ruta"), _("Resultado"), _("Notas")], rutas))
		if evaluacion.observaciones:
			seccion.bloques.append(_("Observaciones del profesional: {texto}").format(texto=evaluacion.observaciones))
		previas = [
			s
			for s in _ordenadas(lista)
			if str(s.get("inicio", ""))[:10] <= evaluacion.fecha
			and (not evaluacion.entorno_id or s.get("entorno_id") == evaluacion.entorno_id)
		]
		if previas:
			seccion.bloques.append(
				_n(
					"{n} sesión en el simulador antes de esta evaluación.",
					"{n} sesiones en el simulador antes de esta evaluación.",
					len(previas),
				).format(n=len(previas))
			)
			seccion.bloques.append(
				Tabla(
					_("En el simulador (últimas sesiones anteriores)"),
					[_(c) for c in _CABECERAS_SERIE],
					[_fila_serie(s) for s in previas[-5:]],
				)
			)
		else:
			seccion.bloques.append(_("No hay sesiones en el simulador de este entorno anteriores a la evaluación."))
		informe.secciones.append(seccion)
	return informe


def _fecha_corta(texto: str) -> str:
	try:
		return date.fromisoformat(texto).strftime("%d/%m/%Y")
	except TypeError, ValueError:
		return str(texto)


# ── Salidas ──────────────────────────────────────────────────────────────────


def a_texto(informe: Informe) -> str:
	"""Texto plano: se lee de corrido con un lector de pantalla, sin dibujos de tabla.

	Cada fila de tabla se escribe como «cabecera: valor; cabecera: valor».
	"""
	lineas = [informe.titulo, ""]
	for seccion in informe.secciones:
		lineas.append(seccion.titulo.upper())
		lineas.append("")
		for bloque in seccion.bloques:
			if isinstance(bloque, Tabla):
				if bloque.titulo != seccion.titulo:
					lineas.append(bloque.titulo + ":")
				for fila in bloque.filas:
					if len(bloque.cabeceras) == 2:
						lineas.append(f"- {fila[0]}: {fila[1]}")
					else:
						lineas.append(
							"- " + "; ".join(f"{cabecera}: {celda}" for cabecera, celda in zip(bloque.cabeceras, fila, strict=False))
						)
				lineas.append("")
			elif isinstance(bloque, list):
				lineas.extend(f"- {elemento}" for elemento in bloque)
				lineas.append("")
			else:
				lineas.append(bloque)
				lineas.append("")
	if informe.aviso:
		lineas.append(_("AVISO"))
		lineas.append("")
		lineas.append(informe.aviso)
		lineas.append("")
	return "\n".join(lineas)


_ESTILO_HTML = (
	"body{font-family:sans-serif;font-size:1.1rem;line-height:1.5;max-width:60rem;margin:1rem auto;padding:0 1rem}"
	"table{border-collapse:collapse;margin:0.5rem 0 1.5rem}"
	"caption{text-align:left;font-weight:bold;padding:0.3rem 0}"
	"th,td{border:1px solid;padding:0.3rem 0.6rem;text-align:left;vertical-align:top}"
	"footer{border-top:2px solid;margin-top:2rem;padding-top:0.5rem}"
)


def a_html(informe: Informe) -> str:
	"""HTML accesible y autónomo (sin scripts ni recursos externos).

	Un solo ``h1``; cada sección es un ``section`` con su ``h2``; las tablas
	llevan ``caption`` y ``th`` con ``scope``; el aviso va en ``footer`` con
	su propio ``h2``. Los colores son los del sistema (alto contraste incluido).
	"""
	e = html.escape
	partes = [
		"<!DOCTYPE html>",
		f'<html lang="{e(idioma_actual())}">',
		"<head>",
		'<meta charset="utf-8">',
		'<meta name="viewport" content="width=device-width, initial-scale=1">',
		f"<title>{e(informe.titulo)}</title>",
		f"<style>{_ESTILO_HTML}</style>",
		"</head>",
		"<body>",
		"<main>",
		f"<h1>{e(informe.titulo)}</h1>",
	]
	for seccion in informe.secciones:
		partes.append("<section>")
		partes.append(f"<h2>{e(seccion.titulo)}</h2>")
		for bloque in seccion.bloques:
			if isinstance(bloque, Tabla):
				partes.append("<table>")
				partes.append(f"<caption>{e(bloque.titulo)}</caption>")
				partes.append("<thead><tr>" + "".join(f'<th scope="col">{e(c)}</th>' for c in bloque.cabeceras) + "</tr></thead>")
				partes.append("<tbody>")
				for fila in bloque.filas:
					celdas = f'<th scope="row">{e(str(fila[0]))}</th>' + "".join(f"<td>{e(str(celda))}</td>" for celda in fila[1:])
					partes.append(f"<tr>{celdas}</tr>")
				partes.append("</tbody>")
				partes.append("</table>")
			elif isinstance(bloque, list):
				partes.append("<ul>" + "".join(f"<li>{e(str(elemento))}</li>" for elemento in bloque) + "</ul>")
			else:
				partes.append(f"<p>{e(bloque)}</p>")
		partes.append("</section>")
	partes.append("</main>")
	if informe.aviso:
		partes.append(f"<footer><h2>{e(_('Aviso'))}</h2><p>{e(informe.aviso)}</p></footer>")
	partes.append("</body>")
	partes.append("</html>")
	return "\n".join(partes) + "\n"


def _celda_csv(valor: Any) -> str:
	"""Evita que una hoja de cálculo ejecute como fórmula un texto que empieza por =, +, - o @."""
	texto = str(valor)
	if texto[:1] in ("=", "+", "@") or (texto[:1] == "-" and not texto[1:2].isdigit()):
		return "'" + texto
	return texto


def a_csv(informe: Informe) -> str:
	"""CSV con punto y coma: una tabla tras otra, cada una con su título y sus cabeceras.

	Formato de cada bloque: una fila con la sección y el título de la tabla,
	la fila de cabeceras, las filas de datos y una fila vacía. Cada párrafo
	va en una fila «sección; texto», para que el CSV diga lo mismo que los
	otros formatos (incluido el aviso final).
	"""
	salida = io.StringIO()
	escritor = csv.writer(salida, delimiter=";", lineterminator="\r\n")
	escritor.writerow([_celda_csv(informe.titulo)])
	escritor.writerow([])
	for seccion in informe.secciones:
		for bloque in seccion.bloques:
			if isinstance(bloque, Tabla):
				escritor.writerow([_celda_csv(seccion.titulo), _celda_csv(bloque.titulo)])
				escritor.writerow([_celda_csv(c) for c in bloque.cabeceras])
				for fila in bloque.filas:
					escritor.writerow([_celda_csv(celda) for celda in fila])
				escritor.writerow([])
			elif isinstance(bloque, list):
				escritor.writerow([_celda_csv(seccion.titulo)])
				for elemento in bloque:
					escritor.writerow([_celda_csv(elemento)])
				escritor.writerow([])
			else:
				escritor.writerow([_celda_csv(seccion.titulo), _celda_csv(bloque)])
				escritor.writerow([])
	if informe.aviso:
		escritor.writerow([_celda_csv(_("Aviso")), _celda_csv(informe.aviso)])
	return salida.getvalue()


FORMATOS: tuple[str, ...] = ("texto", "html", "csv")


def generar(informe: Informe, formato: str) -> str:
	"""Devuelve el informe en ``"texto"``, ``"html"`` o ``"csv"``."""
	if formato == "texto":
		return a_texto(informe)
	if formato == "html":
		return a_html(informe)
	if formato == "csv":
		return a_csv(informe)
	raise ValueError(f"formato de informe desconocido: {formato}")


def guardar(informe: Informe, ruta: Path | str, formato: str | None = None) -> Path:
	"""Escribe el informe en un fichero; el formato se deduce de la extensión si no se da.

	El CSV se guarda con BOM para que la hoja de cálculo reconozca UTF-8.
	"""
	ruta = Path(ruta)
	if formato is None:
		formato = {".txt": "texto", ".html": "html", ".htm": "html", ".csv": "csv"}.get(ruta.suffix.lower(), "texto")
	contenido = generar(informe, formato)
	ruta.parent.mkdir(parents=True, exist_ok=True)
	codificacion = "utf-8-sig" if formato == "csv" else "utf-8"
	with open(ruta, "w", encoding=codificacion, newline="") as salida:
		salida.write(contenido)
	return ruta


# ── Narración de un recorrido ────────────────────────────────────────────────


def _cardinal(rumbo: float) -> str:
	return _(_CARDINALES[int(((rumbo % 360.0) + 22.5) // 45.0) % 8])


def _frase_giro(grados: float) -> str:
	redondeo = int(round(abs(grados) / 15.0) * 15)
	if redondeo >= 165:
		return _("Da media vuelta.")
	if grados < 0:
		return _("Gira a la izquierda, unos {g} grados.").format(g=redondeo)
	return _("Gira a la derecha, unos {g} grados.").format(g=redondeo)


def _frase_avance(clase: str, metros: float, unidad: str, paso_m: float) -> str:
	if unidad == "pasos" and paso_m > 0:
		pasos = max(1, int(round(metros / paso_m)))
		cantidad = _n("{n} paso", "{n} pasos", pasos).format(n=pasos)
	else:
		cantidad = _("{m} metros").format(m=_decimal(metros)) if abs(metros - 1.0) >= 0.05 else _("1 metro")
	if clase == "atras":
		return _("Retrocede {cantidad}.").format(cantidad=cantidad)
	if clase == "izquierda":
		return _("Se desplaza de lado a la izquierda {cantidad}.").format(cantidad=cantidad)
	if clase == "derecha":
		return _("Se desplaza de lado a la derecha {cantidad}.").format(cantidad=cantidad)
	return _("Avanza {cantidad}.").format(cantidad=cantidad)


def _frase_evento(evento: Mapping[str, Any], nombres: Mapping[str, str]) -> str | None:
	tipo = evento.get("tipo")
	datos = evento.get("datos") or {}
	if tipo == "choque":
		con = datos.get("con") or datos.get("objeto") or datos.get("nombre") or datos.get("material")
		return _("Choca con {con}.").format(con=con) if con else _("Choca.")
	if tipo == "entrada_espacio":
		ident = str(datos.get("espacio") or datos.get("espacio_id") or datos.get("id") or "")
		nombre = datos.get("nombre") or nombres.get(ident) or ident
		return _("Entra en {nombre}.").format(nombre=nombre) if nombre else None
	if tipo == "ayuda":
		return _("Pide la ayuda «{ayuda}».").format(ayuda=datos.get("ayuda") or datos.get("tipo") or datos.get("nombre") or _("sin nombre"))
	if tipo == "objetivo":
		return _("Cumple el objetivo «{nombre}».").format(
			nombre=datos.get("nombre") or datos.get("texto") or datos.get("id") or _("sin nombre")
		)
	if tipo == "premio":
		return _("Encuentra el premio «{nombre}».").format(nombre=datos.get("nombre") or datos.get("id") or _("sin nombre"))
	if tipo == "intervencion":
		return _("Interviene el profesional ({tipo}).").format(tipo=datos.get("tipo") or _("sin dato"))
	return None


def describir_recorrido(
	traza: Mapping[str, Any],
	*,
	espacios: Sequence[Mapping[str, Any]] = (),
	unidad: str = "metros",
	paso_m: float = PASO_DE_SERIE_M,
	con_tiempos: bool = False,
) -> list[str]:
	"""Narra un recorrido paso a paso, para repetirlo «de oído» con un lector de pantalla.

	Devuelve una frase por paso («Avanza 4 metros.», «Gira a la derecha, unos
	90 grados.», «Choca con la mesa.»). Los movimientos seguidos del mismo
	tipo se juntan en una sola frase; los giros de menos de 15 grados y los
	desplazamientos de menos de 30 centímetros se omiten por ser ruido.

	:param traza: ``{"muestras", "eventos", "pausas"}`` como en el fichero de sesión.
	:param espacios: para nombrar el espacio de salida y las entradas.
	:param unidad: ``"metros"`` o ``"pasos"`` (de ``paso_m`` metros).
	:param con_tiempos: antepone a cada frase el instante («1 min 5 s. Avanza...»).
	"""
	muestras = medidas._limpiar_muestras(traza.get("muestras") or [])
	nombres = {str(e.get("id", "")): str(e.get("nombre", "")) for e in espacios}
	sucesos: list[tuple[float, int, str]] = []
	for evento in traza.get("eventos") or []:
		if not isinstance(evento, Mapping):
			continue
		frase = _frase_evento(evento, nombres)
		if frase is not None and isinstance(evento.get("t"), (int, float)):
			sucesos.append((float(evento["t"]), 1, frase))
	for pausa in traza.get("pausas") or []:
		if (
			isinstance(pausa, (list, tuple))
			and len(pausa) >= 2
			and isinstance(pausa[0], (int, float))
			and isinstance(pausa[1], (int, float))
		):
			sucesos.append((float(pausa[0]), 0, _("Pausa de {duracion}.").format(duracion=_duracion(pausa[1]))))
	sucesos.sort(key=lambda suceso: (suceso[0], suceso[1]))

	pasos: list[str] = []

	def decir(t: float, frase: str) -> None:
		pasos.append(f"{_duracion(t)}. {frase}" if con_tiempos else frase)

	if not muestras:
		for t, _orden, frase in sucesos:
			decir(t, frase)
		return pasos or [_("No hay recorrido grabado.")]

	primera = muestras[0]
	inicio = medidas.espacio_en(primera[1], primera[2], primera[3], espacios)
	if inicio and nombres.get(inicio):
		decir(primera[0], _("Empieza en {espacio}, mirando al {cardinal}.").format(espacio=nombres[inicio], cardinal=_cardinal(primera[4])))
	else:
		decir(primera[0], _("Empieza mirando al {cardinal}.").format(cardinal=_cardinal(primera[4])))

	clase_actual: str | None = None
	acumulado = 0.0
	# Giro hecho mientras se anda (movimiento continuo): no corta el avance, se cuenta al cerrarlo.
	deriva = 0.0
	t_accion = primera[0]

	def cerrar() -> None:
		nonlocal clase_actual, acumulado, deriva
		if clase_actual == "giro" and abs(acumulado) >= 15.0:
			decir(t_accion, _frase_giro(acumulado))
		elif clase_actual not in (None, "giro") and acumulado >= 0.3:
			decir(t_accion, _frase_avance(str(clase_actual), acumulado, unidad, paso_m))
			if abs(deriva) >= 30.0:
				lado = _("la izquierda") if deriva < 0 else _("la derecha")
				decir(
					t_accion,
					_("Mientras tanto, va girando hacia {lado}, unos {g} grados.").format(lado=lado, g=int(round(abs(deriva) / 15.0) * 15)),
				)
		clase_actual = None
		acumulado = 0.0
		deriva = 0.0

	def acumular(clase: str, cantidad: float, t: float) -> None:
		nonlocal clase_actual, acumulado, deriva, t_accion
		cambia = clase != clase_actual or (clase == "giro" and acumulado and (cantidad > 0) != (acumulado > 0))
		if cambia:
			cerrar()
			clase_actual = clase
			t_accion = t
		acumulado += cantidad

	pendiente = 0
	for anterior, actual in zip(muestras, muestras[1:], strict=False):
		while pendiente < len(sucesos) and sucesos[pendiente][0] <= anterior[0]:
			cerrar()
			decir(sucesos[pendiente][0], sucesos[pendiente][2])
			pendiente += 1
		dx = actual[2] - anterior[2]
		dy = actual[3] - anterior[3]
		tramo = math.hypot(dx, dy)
		if anterior[1] != actual[1]:
			cerrar()
			decir(actual[0], _("Cambia a la planta {planta}.").format(planta=actual[1]))
			continue
		if tramo > max(medidas.SALTO_MINIMO_M, medidas.VELOCIDAD_MAXIMA_MS * max(actual[0] - anterior[0], 0.0)):
			cerrar()
			decir(actual[0], _("Es recolocado en otro punto."))
			continue
		giro = medidas._diferencia_rumbo(anterior[4], actual[4])
		if 1.0 <= abs(giro) < 20.0 and tramo >= 0.02 and clase_actual not in (None, "giro"):
			# Giro suave mientras se anda: es una curva, no un giro en el sitio.
			deriva += giro
		elif abs(giro) >= 1.0:
			acumular("giro", giro, anterior[0])
		if tramo >= 0.02:
			relativo = medidas._diferencia_rumbo(actual[4], medidas._rumbo_de(dx, dy))
			if abs(relativo) <= 45.0:
				clase = "delante"
			elif abs(relativo) >= 135.0:
				clase = "atras"
			elif relativo < 0:
				clase = "izquierda"
			else:
				clase = "derecha"
			acumular(clase, tramo, anterior[0])
	cerrar()
	for t, _orden, frase in sucesos[pendiente:]:
		decir(t, frase)
	final = muestras[-1]
	destino = medidas.espacio_en(final[1], final[2], final[3], espacios)
	if destino and nombres.get(destino):
		decir(final[0], _("Termina en {espacio}.").format(espacio=nombres[destino]))
	else:
		decir(final[0], _("Fin del recorrido."))
	return pasos
