"""Esquemas declarativos de formulario: la descripción de cada campo, sin wx.

Todo formulario del Estudio (propiedades de un elemento, «Insertar
habitación», preferencias…) se genera a partir de una lista de ``Campo``. Así
añadir un dato a un elemento es añadir una línea aquí, y ese dato aparece a la
vez en el panel de propiedades, en su diálogo, en la validación y en la ayuda
de Control+H, siempre con su etiqueta delante y su letra de acceso.

Este módulo no importa wx a propósito: los números, las letras de acceso y la
validación se prueban sin abrir ninguna ventana. Quien dibuja los controles
es ``app/ui/formulario.py``.

Tipos de campo:

- ``texto``: una línea.
- ``largo``: varias líneas.
- ``metros`` y ``decimal``: número con coma o punto decimal, en un campo de
  texto validado (nunca ``wx.SpinCtrlDouble``: el lector no lee su etiqueta).
- ``entero``: número sin decimales.
- ``si_no``: casilla.
- ``opcion``: lista cerrada ``[(valor, texto), …]``.
- ``solo_lectura``: texto que se lee y no se cambia.
- ``ruta_fichero`` y ``ruta_carpeta``: campo con botón «Examinar».
- ``deslizador``: entero entre ``minimo`` y ``maximo`` con ``SliderAccesible``.
- ``casillas``: varias opciones a la vez; el valor es la lista de las marcadas.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

from app.core.i18n import _, separador_decimal

TIPOS_NUMERICOS = ("metros", "decimal", "entero", "deslizador")
TIPOS_TEXTO = ("texto", "largo", "ruta_fichero", "ruta_carpeta")
#: Letras que se pueden pulsar con Alt en un teclado español sin combinaciones raras.
LETRAS_DE_ACCESO = "abcdefghijklmnopqrstuvwxyzñ0123456789"

Opciones = Sequence[tuple[Any, str]]


@dataclass(frozen=True)
class Campo:
	"""Un dato de un formulario.

	``etiqueta`` va SIN ``&``: la letra de acceso se reparte al construir el
	formulario, porque depende de qué más hay en pantalla (los menús de la
	barra, los botones, los otros campos de la pestaña). ``opciones`` puede
	ser una función de los valores actuales, para listas que dependen de
	otro campo. ``si`` decide si el campo se enseña.
	"""

	clave: str
	etiqueta: str
	tipo: str = "texto"
	ayuda: str = ""
	opciones: Opciones | Callable[[dict[str, Any]], Opciones] = ()
	minimo: float | None = None
	maximo: float | None = None
	obligatorio: bool = False
	grupo: str = ""
	si: Callable[[dict[str, Any]], bool] | None = None
	recarga: bool = False
	defecto: Any = None
	comodin: str = ""
	extra: dict[str, Any] = field(default_factory=dict)

	def visible(self, valores: dict[str, Any]) -> bool:
		"""True si el campo procede con los valores actuales."""
		return self.si is None or bool(self.si(valores))

	def lista_opciones(self, valores: dict[str, Any]) -> list[tuple[Any, str]]:
		"""Las opciones ya resueltas (valor, texto visible)."""
		opciones = self.opciones(valores) if callable(self.opciones) else self.opciones
		return [(valor, texto) for valor, texto in opciones]


def c(clave: str, etiqueta: str, tipo: str = "texto", ayuda: str = "", **opciones: Any) -> Campo:
	"""Forma corta de declarar un campo en una tabla de esquema."""
	return Campo(clave=clave, etiqueta=etiqueta, tipo=tipo, ayuda=ayuda, **opciones)


def opciones_de(tabla: dict[Any, str]) -> list[tuple[Any, str]]:
	"""Una tabla del modelo (``SUELOS``, ``TIPOS_ABERTURA``…) como opciones traducidas."""
	return [(clave, _(texto)) for clave, texto in tabla.items()]


# ── Números ──────────────────────────────────────────────────────────────────


def leer_numero(texto: str, decimal: bool = True) -> float | int | None:
	"""Convierte lo escrito en un número; admite coma o punto decimal.

	Devuelve ``None`` si el campo está vacío y lanza ``ValueError`` si lo
	escrito no es un número (o tiene decimales donde no se admiten). Tolera
	que la persona escriba la unidad detrás («3,5 m», «2 metros»).
	"""
	limpio = texto.strip().lower()
	for sufijo in ("metros", "metro", "m"):
		if limpio.endswith(sufijo) and limpio[: -len(sufijo)].strip()[-1:].isdigit():
			limpio = limpio[: -len(sufijo)].strip()
			break
	if not limpio:
		return None
	limpio = limpio.replace(" ", "")
	if "," in limpio and "." in limpio:
		# «1.250,5»: el punto separa miles y la coma decimales.
		limpio = limpio.replace(".", "")
	valor = float(limpio.replace(",", "."))
	if not math.isfinite(valor):
		raise ValueError(texto)
	if not decimal:
		if valor != int(valor):
			raise ValueError(texto)
		return int(valor)
	return valor


def texto_numero(valor: Any, decimales: int = 2) -> str:
	"""Un número como se escribe en español: «3», «3,5», «0,82». Vacío si no hay valor."""
	if valor is None or valor == "":
		return ""
	if isinstance(valor, bool):
		return str(int(valor))
	if isinstance(valor, int):
		return str(valor)
	if isinstance(valor, str):
		# Ya es un texto (lo que la persona escribió): se deja tal cual.
		return valor
	texto = f"{float(valor):.{decimales}f}".rstrip("0").rstrip(".")
	if texto in ("", "-0"):
		texto = "0"
	return texto.replace(".", separador_decimal())


def texto_metros(valor: float) -> str:
	"""«3,5 m»: una medida corta para columnas de lista."""
	return _("{n} m").format(n=texto_numero(valor))


# ── Letras de acceso ─────────────────────────────────────────────────────────


def letra_de(etiqueta: str) -> str:
	"""La letra de acceso de una etiqueta con ``&``: «&Aceptar» da «a». Vacío si no tiene."""
	limpia = etiqueta.replace("&&", "")
	posicion = limpia.find("&")
	return limpia[posicion + 1].lower() if 0 <= posicion < len(limpia) - 1 else ""


def letras_de(etiquetas: Iterable[str]) -> set[str]:
	"""Letras de acceso de varias etiquetas (las de una botonera o una barra de menús)."""
	return {letra for letra in (letra_de(etiqueta) for etiqueta in etiquetas) if letra}


def con_letra(etiqueta: str, usadas: set[str]) -> str:
	"""Pone ``&`` delante de la primera letra libre de la etiqueta y la apunta en ``usadas``.

	Prefiere la inicial de cada palabra (es la que se recuerda) y después
	cualquier otra letra. Si la etiqueta ya trae su ``&`` se respeta. Si no
	queda ninguna letra libre se devuelve sin letra de acceso: el campo sigue
	alcanzándose con el tabulador (antes se prueba a darle una cifra).
	"""
	propia = letra_de(etiqueta)
	if propia:
		usadas.add(propia)
		return etiqueta
	iniciales = [i for i, caracter in enumerate(etiqueta) if i == 0 or etiqueta[i - 1] in " («/-"]
	resto = [i for i in range(len(etiqueta)) if i not in iniciales]
	for posicion in iniciales + resto:
		letra = etiqueta[posicion].lower()
		if letra in LETRAS_DE_ACCESO and letra not in usadas:
			usadas.add(letra)
			return etiqueta[:posicion] + "&" + etiqueta[posicion:]
	# Todas las letras de la etiqueta están ya ocupadas en esta pantalla: se le da un número, que
	# se dice al final («Procedencia, 1») y deja el campo alcanzable con Alt+1.
	for cifra in "1234567890":
		if cifra not in usadas:
			usadas.add(cifra)
			return f"{etiqueta} (&{cifra})"
	return etiqueta


# ── Validación ───────────────────────────────────────────────────────────────


class ErrorCampo(ValueError):
	"""Un campo del formulario no vale. Lleva la clave para poner el foco en él."""

	def __init__(self, clave: str, mensaje: str) -> None:
		super().__init__(mensaje)
		self.clave = clave
		self.mensaje = mensaje


def nombre_campo(campo: Campo) -> str:
	"""La etiqueta traducida y sin ``&``, para nombrar el campo en un mensaje."""
	return _(campo.etiqueta).replace("&", "").rstrip(":")


def convertir_valor(campo: Campo, crudo: Any) -> Any:
	"""Pasa lo que hay en el control al tipo del campo; lanza ``ErrorCampo`` si no vale.

	``crudo`` es un texto para los campos escritos y el valor ya tipado para
	casillas, listas y deslizadores.
	"""
	nombre = nombre_campo(campo)
	if campo.tipo in ("metros", "decimal", "entero") and isinstance(crudo, str):
		try:
			valor = leer_numero(crudo, decimal=campo.tipo != "entero")
		except ValueError:
			if campo.tipo == "entero":
				raise ErrorCampo(campo.clave, _("«{campo}» tiene que ser un número entero.").format(campo=nombre)) from None
			raise ErrorCampo(
				campo.clave, _("«{campo}» tiene que ser un número. Puede escribir los decimales con coma o con punto.").format(campo=nombre)
			) from None
	elif campo.tipo in TIPOS_TEXTO and isinstance(crudo, str):
		valor = crudo.strip()
	else:
		valor = crudo
	if valor is None or valor == "":
		if campo.obligatorio:
			raise ErrorCampo(campo.clave, _("Falta «{campo}».").format(campo=nombre))
		return None if campo.tipo in TIPOS_NUMERICOS else valor
	if isinstance(valor, (int, float)) and not isinstance(valor, bool):
		if campo.minimo is not None and valor < campo.minimo:
			raise ErrorCampo(
				campo.clave, _("«{campo}» no puede ser menor que {limite}.").format(campo=nombre, limite=texto_numero(campo.minimo))
			)
		if campo.maximo is not None and valor > campo.maximo:
			raise ErrorCampo(
				campo.clave, _("«{campo}» no puede ser mayor que {limite}.").format(campo=nombre, limite=texto_numero(campo.maximo))
			)
	return valor


def valores_por_defecto(campos: Sequence[Campo]) -> dict[str, Any]:
	"""Los valores de partida de un formulario nuevo."""
	return {campo.clave: campo.defecto for campo in campos if campo.defecto is not None}


def grupos_de(campos: Sequence[Campo]) -> list[str]:
	"""Nombres de grupo (pestañas) en el orden en que aparecen."""
	vistos: list[str] = []
	for campo in campos:
		if campo.grupo not in vistos:
			vistos.append(campo.grupo)
	return vistos
