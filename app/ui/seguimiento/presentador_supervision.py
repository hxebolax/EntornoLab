"""Lógica de la ventana de supervisión, sin wx: filas, textos, frases y qué se anuncia por voz.

La ventana solo lee la «foto» periódica de la sala y sus sucesos; aquí se
convierten en textos. Nada de esto toca la red ni los controles, así que se
prueba con diccionarios.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from app.core.i18n import N_, _
from app.ui.seguimiento import textos
from app.ui.seguimiento.textos import cardinal, duracion, recortar

log = logging.getLogger(__name__)

CLAVE_ANUNCIAR = "supervision.anunciar_eventos"
CLAVE_TIPOS = "supervision.eventos_anunciados"
CLAVE_SEGUNDA_SALIDA = "supervision.segunda_salida"
# Como mucho, tantos anuncios por refresco: si pasan muchas cosas a la vez se resume.
MAXIMO_ANUNCIOS = 2

AVISO_CORTAFUEGOS = N_(
	"Si un alumno no consigue conectarse desde otro ordenador: compruebe que los dos equipos están en la misma red, "
	"que ha escrito bien la dirección y el código, y que el cortafuegos de Windows deja a EntornoLab aceptar conexiones "
	"en redes privadas. La primera vez que se abre la sala en red, Windows lo pregunta: hay que contestar «Permitir»."
)
EXPLICACION_SEGUNDA_SALIDA = N_(
	"Con el alumno en este mismo ordenador, el reproductor puede enviar su sonido también a una segunda salida de audio "
	"(otros auriculares o los altavoces), para que usted oiga lo mismo que él. La segunda salida se elige en "
	"Preferencias, Sonido, y solo funciona con el motor de sonido clásico."
)


def columnas() -> list[tuple[str, int]]:
	"""Columnas de la lista de alumnos conectados."""
	return [
		(_("Alias"), 110),
		(_("Estado"), 110),
		(_("Entorno"), 130),
		(_("Actividad"), 130),
		(_("Dónde está"), 200),
		(_("Rumbo"), 80),
		(_("Tiempo activo"), 100),
		(_("Choques"), 70),
		(_("Ayudas"), 70),
		(_("Objetivos"), 80),
	]


def estado_alumno(alumno: Mapping[str, Any]) -> str:
	"""«Jugando», «En pausa», «Ha terminado», «Sin conexión» o «Recorriendo»."""
	if not alumno.get("conectado"):
		return _("Ha terminado") if alumno.get("terminado") else _("Sin conexión")
	if alumno.get("terminado"):
		return _("Ha terminado")
	if alumno.get("pausado"):
		return _("En pausa")
	return _("Recorriendo") if alumno.get("recorrido") else _("Jugando")


def contador(alumno: Mapping[str, Any], clave: str, tipo_evento: str = "") -> int:
	"""Un contador del alumno; si el reproductor no lo envía, se cuentan los sucesos de ese tipo que se conservan."""
	contadores = alumno.get("contadores") if isinstance(alumno.get("contadores"), Mapping) else {}
	valor = contadores.get(clave)
	if isinstance(valor, (int, float)) and not isinstance(valor, bool):
		return int(valor)
	if tipo_evento:
		return sum(1 for evento in alumno.get("eventos") or [] if isinstance(evento, Mapping) and evento.get("tipo") == tipo_evento)
	return 0


def fila_alumno(alumno: Mapping[str, Any]) -> list[str]:
	"""Textos de la fila de un alumno conectado."""
	return [
		str(alumno.get("alias") or alumno.get("id") or ""),
		estado_alumno(alumno),
		str(alumno.get("entorno") or ""),
		str(alumno.get("actividad") or ""),
		recortar(str(alumno.get("posicion") or alumno.get("espacio") or _("Sin datos")), 120),
		cardinal(alumno.get("rumbo")).capitalize(),
		duracion(alumno.get("tiempo_activo")),
		str(contador(alumno, "choques", "choque")),
		str(contador(alumno, "ayudas", "ayuda")),
		str(contador(alumno, "objetivos", "objetivo")),
	]


def texto_posicion(alumno: Mapping[str, Any] | None) -> str:
	"""Dónde está el alumno y qué tiene delante, en una línea."""
	if alumno is None:
		return _("Ningún alumno elegido.")
	posicion = str(alumno.get("posicion") or alumno.get("espacio") or "").strip()
	if not posicion:
		return _("Todavía no ha llegado su posición.")
	delante = str(alumno.get("delante") or "").strip()
	if delante:
		return _("{posicion}. Delante: {delante}").format(posicion=posicion.rstrip("."), delante=delante)
	return posicion


def texto_sala(foto: Mapping[str, Any], segunda_salida: bool = False, abriendo: bool = False, error: str = "") -> str:
	"""El estado de la sala, una cosa por línea, para recorrerlo con las flechas y dictarlo."""
	if abriendo:
		return _("Abriendo la sala... La primera vez en red tarda unos segundos, porque crea su certificado.")
	lineas: list[str] = []
	if not foto.get("activa"):
		lineas.append(_("La sala está cerrada. Elija el modo de conexión y pulse «Abrir la sala»."))
		if error:
			lineas.append(_("La última vez no se pudo abrir: {error}").format(error=error))
		return "\n".join(lineas)
	alumnos = foto.get("alumnos") or []
	conectados = sum(1 for alumno in alumnos if alumno.get("conectado"))
	lineas.append(_("Sala abierta. Alumnos conectados: {n}.").format(n=conectados))
	lineas.append(_("Código de emparejamiento: {codigo}.").format(codigo=" ".join(str(foto.get("codigo") or ""))))
	if foto.get("red"):
		lineas.append(_("Modo: red local, con conexión cifrada."))
		direcciones = [str(direccion) for direccion in foto.get("direcciones") or []]
		if direcciones:
			lineas.append(
				_("Dirección de este ordenador para dictarla: {direcciones}, puerto {puerto}.").format(
					direcciones=_(" o ").join(direcciones), puerto=foto.get("puerto")
				)
			)
		else:
			lineas.append(
				_("No se ha podido averiguar la dirección de este ordenador en la red. Puerto {puerto}.").format(puerto=foto.get("puerto"))
			)
		if foto.get("huella_legible"):
			lineas.append(_("Huella para comparar con la que dice el reproductor: {huella}.").format(huella=foto.get("huella_legible")))
		lineas.append(_(AVISO_CORTAFUEGOS))
	else:
		lineas.append(_("Modo: solo este ordenador. Nadie puede conectarse desde la red."))
		lineas.append(_("Puerto local: {puerto}.").format(puerto=foto.get("puerto_local") or foto.get("puerto")))
	bloqueados = foto.get("bloqueados")
	if isinstance(bloqueados, int) and bloqueados > 0:
		lineas.append(_("Direcciones bloqueadas un minuto por probar códigos incorrectos: {n}.").format(n=bloqueados))
	if segunda_salida:
		lineas.append(_("Segunda salida de audio activada: el reproductor de este ordenador la usará si está configurada en Preferencias."))
	return "\n".join(lineas)


# ── Sucesos ──────────────────────────────────────────────────────────────────


def texto_evento(tipo: str, datos: Mapping[str, Any] | None) -> str:
	"""Un ``EvRegistro`` del alumno en una frase breve («Choca con la mesa»)."""
	datos = datos or {}
	if tipo == "choque":
		con = datos.get("con") or datos.get("nombre") or datos.get("material")
		return _("Choca con {con}").format(con=con) if con else _("Choca")
	if tipo == "ayuda":
		ayuda = str(datos.get("ayuda") or datos.get("tipo") or datos.get("nombre") or "")
		return _("Pide la ayuda «{ayuda}»").format(ayuda=textos.nombre(textos.AYUDAS, ayuda) if ayuda else _("sin nombre"))
	if tipo == "ayuda_denegada":
		ayuda = str(datos.get("ayuda") or "")
		return _("Pide «{ayuda}», pero no la tiene permitida").format(ayuda=textos.nombre(textos.AYUDAS, ayuda))
	if tipo == "premio":
		return _("Encuentra el premio «{nombre}»").format(nombre=datos.get("nombre") or datos.get("id") or _("sin nombre"))
	if tipo == "objetivo":
		return _("Cumple el objetivo «{nombre}»").format(
			nombre=datos.get("nombre") or datos.get("texto") or datos.get("id") or _("sin nombre")
		)
	if tipo == "cruce_inseguro":
		return _("Cruce inseguro")
	if tipo == "cruce":
		return _("Cruza la calle con seguridad") if datos.get("seguro", True) else _("Cruza la calle de forma insegura")
	if tipo == "entrada_espacio":
		return _("Entra en {nombre}").format(nombre=datos.get("nombre") or datos.get("espacio") or _("otro espacio"))
	if tipo == "cambio_planta":
		return _("Cambia de planta")
	if tipo == "intervencion":
		return _("Intervención del profesional: {orden}").format(orden=datos.get("orden") or datos.get("tipo") or "")
	if tipo == "inicio":
		return _("Empieza la sesión")
	if tipo == "pausa":
		return _("Pausa") if datos.get("activa", True) else _("Reanuda")
	if tipo == "marca":
		return _("Marca del profesional: {texto}").format(texto=datos.get("texto") or "")
	return str(tipo).replace("_", " ").capitalize()


def fila_evento(evento: Mapping[str, Any]) -> list[str]:
	"""Textos de la fila de un suceso del alumno: instante y qué ha pasado."""
	datos = evento.get("datos") if isinstance(evento.get("datos"), Mapping) else {}
	return [duracion(evento.get("t")), texto_evento(str(evento.get("tipo") or ""), datos)]


def linea_voz(voz: Mapping[str, Any]) -> str:
	"""Una línea del historial de lo oído: el texto, con el canal si no es el del juego."""
	texto = " ".join(str(voz.get("texto") or "").split())
	canal = str(voz.get("canal") or "juego")
	if canal == "profesional":
		return _("[Profesional] {texto}").format(texto=texto)
	return texto


def categoria(suceso: Mapping[str, Any]) -> str | None:
	"""Tipo anunciable al que pertenece un suceso de la sala (clave de ``EVENTOS_ANUNCIABLES``), o None."""
	tipo = suceso.get("tipo")
	if tipo in ("conectado", "reconectado", "desconectado", "proceso_terminado"):
		return "conexion"
	if tipo in ("codigo_incorrecto", "bloqueado"):
		return "codigo"
	if tipo in ("fin", "voz"):
		return str(tipo)
	if tipo == "evento":
		datos = suceso.get("datos") if isinstance(suceso.get("datos"), Mapping) else {}
		interno = str(datos.get("tipo") or "")
		return interno if interno in textos.EVENTOS_ANUNCIABLES else None
	return None


def frase_suceso(suceso: Mapping[str, Any]) -> str:
	"""Frase breve para decir por voz un suceso de la sala («Luna: choca con la mesa.»)."""
	tipo = suceso.get("tipo")
	alias = str(suceso.get("alias") or "")
	datos = suceso.get("datos") if isinstance(suceso.get("datos"), Mapping) else {}
	if tipo == "conectado":
		return _("{alias} se ha conectado.").format(alias=alias)
	if tipo == "reconectado":
		return _("{alias} ha vuelto a conectarse.").format(alias=alias)
	if tipo == "desconectado":
		if datos.get("terminado"):
			return _("{alias} ha cerrado el reproductor.").format(alias=alias)
		return _("{alias} ha perdido la conexión.").format(alias=alias)
	if tipo == "proceso_terminado":
		return frase_proceso_terminado(alias, bool(datos.get("inesperado")))
	if tipo == "fin":
		if datos.get("completada"):
			return _("{alias} ha terminado la actividad.").format(alias=alias)
		return _("{alias} ha terminado sin completar la actividad.").format(alias=alias)
	if tipo == "codigo_incorrecto":
		return _("Alguien ha probado un código de emparejamiento incorrecto.")
	if tipo == "bloqueado":
		return _("Una dirección ha quedado bloqueada un minuto por probar códigos incorrectos.")
	if tipo == "voz":
		return _("{alias} oye: {texto}").format(alias=alias, texto=recortar(str(datos.get("texto") or ""), 200))
	if tipo == "evento":
		interno = datos.get("datos") if isinstance(datos.get("datos"), Mapping) else {}
		texto = texto_evento(str(datos.get("tipo") or ""), interno)
		return _("{alias}: {texto}.").format(alias=alias, texto=texto[:1].lower() + texto[1:])
	return ""


def frase_proceso_terminado(alias: str, inesperado: bool) -> str:
	"""«El reproductor de Luna se ha cerrado», y si fue inesperado, que se puede volver a abrir."""
	if alias:
		if inesperado:
			return _("El reproductor de {alias} se ha cerrado inesperadamente; puede volver a abrirlo.").format(alias=alias)
		return _("El reproductor de {alias} se ha cerrado.").format(alias=alias)
	if inesperado:
		return _("El reproductor se ha cerrado inesperadamente; puede volver a abrirlo.")
	return _("El reproductor se ha cerrado.")


def leer_tipos(configuracion: Any) -> set[str]:
	"""Tipos de suceso que el profesional quiere oír (preferencia ``supervision.eventos_anunciados``)."""
	crudo = textos.EVENTOS_ANUNCIADOS_DE_SERIE
	if configuracion is not None:
		try:
			crudo = str(configuracion.obtener(CLAVE_TIPOS, crudo))
		except KeyError, TypeError, ValueError:
			log.debug("No se ha podido leer %s", CLAVE_TIPOS, exc_info=True)
	return {parte.strip() for parte in crudo.split(",") if parte.strip() in textos.EVENTOS_ANUNCIABLES}


def anuncios_activados(configuracion: Any) -> bool:
	"""Interruptor general ``supervision.anunciar_eventos``."""
	if configuracion is None:
		return True
	try:
		return bool(configuracion.obtener(CLAVE_ANUNCIAR, True))
	except KeyError, TypeError, ValueError:
		log.debug("No se ha podido leer %s; se anuncia como de serie", CLAVE_ANUNCIAR, exc_info=True)
		return True


def guardar_anuncios(configuracion: Any, activados: bool, tipos: Sequence[str]) -> None:
	"""Guarda el interruptor general y los tipos elegidos."""
	if configuracion is None:
		return
	ordenados = ",".join(tipo for tipo in textos.EVENTOS_ANUNCIABLES if tipo in set(tipos))
	configuracion.establecer_varias({CLAVE_ANUNCIAR: bool(activados), CLAVE_TIPOS: ordenados})


def _cierre_inesperado(suceso: Mapping[str, Any]) -> bool:
	datos = suceso.get("datos") if isinstance(suceso.get("datos"), Mapping) else {}
	return suceso.get("tipo") == "proceso_terminado" and bool(datos.get("inesperado"))


def frases_a_anunciar(sucesos: Sequence[Mapping[str, Any]], activados: bool, tipos: set[str]) -> list[str]:
	"""Frases que hay que decir por los sucesos de un refresco, sin saturar.

	Solo los tipos elegidos; si son más de ``MAXIMO_ANUNCIOS`` se dicen los
	primeros y cuántos más ha habido (están todos en las listas de la ventana).
	"""
	if not activados:
		return []
	# Un reproductor que se cierra solo se dice siempre: el profesional tiene que saberlo para volver a abrirlo.
	frases = [
		frase for frase in (frase_suceso(suceso) for suceso in sucesos if categoria(suceso) in tipos or _cierre_inesperado(suceso)) if frase
	]
	if len(frases) <= MAXIMO_ANUNCIOS:
		return frases
	resto = len(frases) - MAXIMO_ANUNCIOS
	return [*frases[:MAXIMO_ANUNCIOS], textos.contar(resto, "Y {n} suceso más.", "Y {n} sucesos más.")]


def resumen_hablado(alumno: Mapping[str, Any] | None) -> str:
	"""Estado del alumno elegido en una frase, para decirlo con una tecla sin mover el foco."""
	if alumno is None:
		return _("No hay ningún alumno elegido.")
	return _("{alias}, {estado}. {posicion}. Tiempo activo {tiempo}, {choques} choques, {ayudas} ayudas.").format(
		alias=alumno.get("alias") or "",
		estado=estado_alumno(alumno).lower(),
		posicion=texto_posicion(alumno).rstrip("."),
		tiempo=duracion(alumno.get("tiempo_activo")),
		choques=contador(alumno, "choques", "choque"),
		ayudas=contador(alumno, "ayudas", "ayuda"),
	)


# ── Sesión en este ordenador ─────────────────────────────────────────────────


def entornos_disponibles(contexto: Any) -> list[tuple[str, Path]]:
	"""Entornos que se pueden jugar en este ordenador: el abierto (si está guardado), los del profesional y los de ejemplo."""
	from app.core import paths
	from app.dominio import formato

	vistos: set[Path] = set()
	lista: list[tuple[str, Path]] = []
	abierto = getattr(contexto, "ruta_paquete", None)
	if abierto is not None and getattr(contexto, "entorno", None) is not None:
		ruta = Path(abierto)
		vistos.add(ruta.resolve())
		lista.append((_("{nombre} (el entorno abierto)").format(nombre=getattr(contexto.entorno, "nombre", "") or ruta.stem), ruta))
	for carpeta in (paths.ruta_entornos(), paths.ruta_ejemplos()):
		for ruta in sorted(carpeta.glob("*.elab")):
			if ruta.resolve() in vistos:
				continue
			vistos.add(ruta.resolve())
			try:
				nombre = str(formato.leer_manifiesto(ruta).get("nombre") or ruta.stem)
			except formato.ErrorFormato:
				log.warning("Entorno ilegible al listar los disponibles: %s", ruta.name)
				continue
			lista.append((nombre, ruta))
	return lista


def actividades_de(contexto: Any, ruta: Path) -> list[dict[str, Any]]:
	"""Actividades del paquete ``ruta`` (las del contexto si es el entorno abierto)."""
	from app.dominio import formato

	abierto = getattr(contexto, "ruta_paquete", None)
	if abierto is not None and Path(abierto).resolve() == Path(ruta).resolve():
		return [actividad for actividad in contexto.actividades if isinstance(actividad, dict)]
	try:
		return list(formato.cargar_paquete(ruta).actividades)
	except formato.ErrorFormato:
		log.warning("No se han podido leer las actividades de %s", Path(ruta).name)
		return []
