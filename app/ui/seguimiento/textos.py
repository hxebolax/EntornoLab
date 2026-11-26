"""Textos, tablas de nombres y formatos comunes del seguimiento. Sin wx.

Los valores cerrados (perfil, estilo, modo...) se guardan con su identificador
y se muestran con su nombre traducido: nunca se compara un texto traducido.
"""

from __future__ import annotations

import math
import unicodedata
from collections.abc import Iterable, Mapping
from datetime import datetime
from typing import Any

from app.core.i18n import N_, _, _n, separador_decimal

PERFILES: dict[str, str] = {
	"baston": N_("Bastón"),
	"perro_guia": N_("Perro guía"),
	"baja_vision": N_("Baja visión"),
	"otro": N_("Otro"),
}
ESTILOS: dict[str, str] = {"infantil": N_("Infantil"), "juvenil": N_("Juvenil"), "adulto": N_("Adulto")}
ESTILOS_ACTIVIDAD: dict[str, str] = {**ESTILOS, "del_alumno": N_("El del alumno")}
MODOS: dict[str, str] = {"juego": N_("Juego"), "practica": N_("Práctica"), "examen": N_("Examen")}
GRUPOS_TIPO: dict[str, str] = {"juego": N_("Juegos"), "practica": N_("Prácticas"), "examen": N_("Exámenes")}
MODOS_MOVIMIENTO: dict[str, str] = {
	"pasos": N_("Por pasos: cada pulsación es un paso"),
	"continuo": N_("Continuo: se anda mientras se mantiene la tecla"),
	"brujula": N_("Brújula: las flechas son norte, sur, este y oeste"),
	"salas": N_("Por salas: se elige una salida y se cruza"),
	"aceras": N_("Por aceras: se anda recto hasta la siguiente novedad"),
}
FORMATOS_DIRECCION: dict[str, str] = {
	"reloj": N_("Horas del reloj: «a las dos»"),
	"lados": N_("Lados: «delante a la derecha»"),
	"cardinal": N_("Puntos cardinales: «al nordeste»"),
	"grados": N_("Grados"),
}
UNIDADES: dict[str, str] = {"metros": N_("Metros"), "pasos": N_("Pasos del alumno")}
DETALLES: dict[int, str] = {
	0: N_("0: solo sonidos"),
	1: N_("1: lo imprescindible"),
	2: N_("2: normal"),
	3: N_("3: todo"),
}
VISIBILIDADES: dict[str, str] = {
	"lejos": N_("Se oye de lejos"),
	"cerca": N_("Solo se oye de cerca"),
	"oculto": N_("Oculto hasta abrir o usar algo"),
}
AYUDAS: dict[str, str] = {
	"donde_estoy": N_("Dónde estoy"),
	"descripcion": N_("Descripción del lugar"),
	"mirar": N_("Mirar a los lados y detrás"),
	"delante": N_("Qué hay delante"),
	"alrededor": N_("Qué hay alrededor"),
	"sonda": N_("Bastón sonoro"),
	"cercanos": N_("Lista de lo cercano"),
	"descubiertos": N_("Lugares descubiertos"),
	"brujula": N_("Brújula"),
	"eco": N_("Eco"),
	"objetivo": N_("Recordar el objetivo"),
	"pista": N_("Pista"),
	"baliza": N_("Baliza sonora"),
	"avisos": N_("Avisos automáticos"),
}
TIPOS_OBJETIVO: dict[str, str] = {
	"ir_a": N_("Ir a un lugar"),
	"recoger": N_("Recoger algo"),
	"entregar": N_("Entregar algo"),
	"salir": N_("Salir del edificio"),
	"senalar": N_("Señalar hacia un lugar"),
	"usar": N_("Usar o abrir algo"),
	"cruzar": N_("Cruzar una calle"),
}
CLASES_ELEMENTO: dict[str, str] = {
	"espacio": N_("Espacios"),
	"abertura": N_("Puertas y huecos"),
	"objeto": N_("Objetos"),
	"referencia": N_("Referencias"),
	"salida": N_("Salidas"),
}
# Tipos de suceso que se pueden anunciar por voz en la supervisión, con su nombre.
EVENTOS_ANUNCIABLES: dict[str, str] = {
	"conexion": N_("Un alumno se conecta o se desconecta"),
	"choque": N_("Choques"),
	"ayuda": N_("Ayudas pedidas"),
	"premio": N_("Premios encontrados"),
	"objetivo": N_("Objetivos cumplidos"),
	"cruce_inseguro": N_("Cruces inseguros"),
	"entrada_espacio": N_("Cambios de espacio"),
	"fin": N_("Final de la sesión"),
	"codigo": N_("Códigos de emparejamiento incorrectos"),
	"voz": N_("Todo lo que oye el alumno (muy hablador)"),
}
EVENTOS_ANUNCIADOS_DE_SERIE = "conexion,choque,ayuda,premio,objetivo,cruce_inseguro,fin,codigo"

_CARDINALES = (N_("norte"), N_("nordeste"), N_("este"), N_("sureste"), N_("sur"), N_("suroeste"), N_("oeste"), N_("noroeste"))
RUMBOS: tuple[tuple[float, str], ...] = tuple((indice * 45.0, nombre) for indice, nombre in enumerate(_CARDINALES))


def nombre(tabla: Mapping[Any, str], clave: Any) -> str:
	"""Nombre traducido de ``clave``; si no está en la tabla, la propia clave (dato de otra versión)."""
	texto = tabla.get(clave)
	return _(texto) if texto else str(clave if clave is not None else "")


def cardinal(rumbo: Any) -> str:
	"""«este» para 90 grados; cadena vacía si no hay rumbo."""
	if not isinstance(rumbo, (int, float)) or isinstance(rumbo, bool) or math.isnan(rumbo):
		return ""
	return _(_CARDINALES[int(((float(rumbo) % 360.0) + 22.5) // 45.0) % 8])


def decimal(valor: float, decimales: int = 1) -> str:
	"""Número con coma decimal, como se escribe en español."""
	return f"{valor:.{decimales}f}".replace(".", separador_decimal())


def texto_numero(valor: Any) -> str:
	"""Un número para un campo de texto: vacío si no hay, coma decimal, sin ceros de más."""
	if valor is None or valor == "" or isinstance(valor, bool):
		return ""
	if isinstance(valor, float):
		if valor == int(valor):
			return str(int(valor))
		return f"{valor:.3f}".rstrip("0").rstrip(".").replace(".", separador_decimal())
	return str(valor)


def leer_numero(texto: str, entero: bool = False) -> float | int | None:
	"""Convierte lo escrito en un número aceptando coma o punto. ``None`` si está vacío.

	Lanza ``ValueError`` si no es un número (o no es entero cuando se pide).
	"""
	limpio = str(texto).strip().replace(",", ".")
	if not limpio:
		return None
	valor = float(limpio)
	if math.isnan(valor) or math.isinf(valor):
		raise ValueError(texto)
	if entero:
		if valor != int(valor):
			raise ValueError(texto)
		return int(valor)
	return valor


def duracion(segundos: Any) -> str:
	"""«3 min 05 s», «45 s» o «1 h 02 min»."""
	if not isinstance(segundos, (int, float)) or isinstance(segundos, bool):
		return _("sin dato")
	total = int(max(0.0, float(segundos)) + 0.5)
	horas, resto = divmod(total, 3600)
	minutos, seg = divmod(resto, 60)
	if horas:
		return _("{h} h {m:02d} min").format(h=horas, m=minutos)
	if minutos:
		return _("{m} min {s:02d} s").format(m=minutos, s=seg)
	return _("{s} s").format(s=seg)


def fecha_legible(iso: Any, con_hora: bool = True) -> str:
	"""«20/11/2026 11:00» a partir de una fecha ISO (se pasa a la hora local)."""
	if not isinstance(iso, str) or not iso:
		return _("sin dato")
	try:
		momento = datetime.fromisoformat(iso)
	except ValueError:
		# No es una fecha ISO (dato de otra versión): se enseña tal cual en vez de ocultarlo.
		return iso
	if momento.tzinfo is not None:
		momento = momento.astimezone()
	return momento.strftime("%d/%m/%Y %H:%M" if con_hora else "%d/%m/%Y")


def si_no(valor: Any) -> str:
	"""«Sí» o «No»."""
	return _("Sí") if valor else _("No")


def contar(n: int, uno: str, varios: str) -> str:
	"""Atajo de ``_n(...).format(n=n)`` para frases con un número."""
	return _n(uno, varios, n).format(n=n)


def recortar(texto: str, maximo: int = 120) -> str:
	"""Texto de una línea y de longitud acotada para una celda de lista."""
	limpio = " ".join(str(texto or "").split())
	return limpio if len(limpio) <= maximo else limpio[: maximo - 1].rstrip() + "…"


# ── Letras de acceso ─────────────────────────────────────────────────────────

_LETRAS_VALIDAS = set("abcdefghijklmnopqrstuvwxyzñ")


def letra_de(etiqueta: str) -> str:
	"""Letra de acceso de una etiqueta con «&» («A&plicar» da «p»), o cadena vacía."""
	posicion = 0
	while True:
		posicion = etiqueta.find("&", posicion)
		if posicion < 0 or posicion + 1 >= len(etiqueta):
			return ""
		if etiqueta[posicion + 1] == "&":
			posicion += 2
			continue
		return etiqueta[posicion + 1].lower()


def sin_marca(etiqueta: str) -> str:
	"""La etiqueta sin su «&» de acceso."""
	return etiqueta.replace("&&", "\0").replace("&", "").replace("\0", "&&")


class Letras:
	"""Reparte letras de acceso sin repetir dentro de lo que se ve a la vez.

	Las etiquetas de los formularios generados no se conocen al escribir el
	código (vienen del esquema de cada tipo de actividad, y cambian al
	traducir), así que la letra no puede elegirse a mano: se toma la primera
	letra libre de cada etiqueta, por orden. ``reservadas`` son las que ya
	usan los botones fijos (Aceptar, Cancelar) y los menús de la ventana.
	"""

	def __init__(self, reservadas: Iterable[str] = ()) -> None:
		self.usadas: set[str] = {letra.lower() for letra in reservadas if letra}

	def copia(self) -> Letras:
		"""Otro repartidor con las mismas letras ocupadas (una pestaña distinta puede repetir las de otra)."""
		return Letras(self.usadas)

	def reservar(self, *etiquetas: str) -> None:
		"""Ocupa las letras de etiquetas que ya llevan su «&»."""
		for etiqueta in etiquetas:
			letra = letra_de(etiqueta)
			if letra:
				self.usadas.add(letra)

	def poner(self, etiqueta: str) -> str:
		"""Devuelve la etiqueta con «&» delante de su primera letra libre.

		Si ya trae una letra y está libre, se respeta. Las vocales con tilde
		no se usan: con el teclado español no se pulsan con Alt.
		"""
		propia = letra_de(etiqueta)
		if propia and propia in _LETRAS_VALIDAS and propia not in self.usadas:
			self.usadas.add(propia)
			return etiqueta
		limpia = sin_marca(etiqueta)
		for posicion, caracter in enumerate(limpia):
			letra = caracter.lower()
			if letra in _LETRAS_VALIDAS and letra not in self.usadas and unicodedata.category(caracter).startswith("L"):
				self.usadas.add(letra)
				return limpia[:posicion] + "&" + limpia[posicion:]
		# Sin letras libres (formulario muy largo): un número entre paréntesis, que también se pulsa con Alt.
		for cifra in "123456789":
			if cifra not in self.usadas:
				self.usadas.add(cifra)
				cuerpo = limpia.rstrip()
				final = ":" if cuerpo.endswith(":") else ""
				return f"{cuerpo.rstrip(':')} (&{cifra}){final}"
		return limpia
