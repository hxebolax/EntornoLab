"""Esquema de actividades de reserva, con la misma forma que ``app.actividades``. Sin wx.

Sirve para dos cosas:

- que el panel de actividades siga funcionando (con cuatro tipos básicos) si
  el paquete ``app.actividades`` no está o le falta alguna función, en vez de
  dejar al profesional sin poder abrir una actividad;
- como esquema de prueba del formulario generado: entre sus cuatro tipos usa
  todos los tipos de campo.

No sustituye al motor de actividades: solo describe, crea y comprueba datos.
"""

from __future__ import annotations

import copy
import random
from dataclasses import dataclass
from typing import Any

from app.core.i18n import N_, _
from app.dominio.modelo import Aviso
from app.ui.seguimiento import lugares

FORMATO_ACTIVIDAD = 1


@dataclass(frozen=True)
class InfoTipo:
	"""Un tipo de actividad: identificador, nombre, descripción, modo de serie y grupo."""

	id: str
	nombre: str
	descripcion: str
	modo_por_defecto: str
	grupo: str


@dataclass
class Campo:
	"""Un campo del formulario de una actividad (misma forma que ``app.actividades.tipos.Campo``)."""

	clave: str
	etiqueta: str
	tipo: str
	ayuda: str
	opciones: list[Any] | None = None
	defecto: Any = None
	minimo: float | None = None
	maximo: float | None = None
	grupo: str = "general"
	depende_de: str | None = None


TIPOS: dict[str, InfoTipo] = {
	info.id: info
	for info in (
		InfoTipo("busqueda", N_("Búsqueda del tesoro"), N_("Encontrar todos los premios escondidos por el entorno."), "juego", "juego"),
		InfoTipo(
			"exploracion",
			N_("Exploración libre"),
			N_("Recorrer el entorno con libertad, sin objetivo ni puntuación."),
			"practica",
			"practica",
		),
		InfoTipo("ruta", N_("Ruta"), N_("Ir de un punto a otro, con paradas intermedias si se quiere."), "practica", "practica"),
		InfoTipo(
			"examen_salida",
			N_("Examen de salida más corta"),
			N_("Desde varios puntos, salir por la salida más cercana."),
			"examen",
			"examen",
		),
	)
}


def campos_de(tipo: str) -> list[Campo]:
	"""Campos del formulario de un tipo. ``KeyError`` si el tipo no existe."""
	info = TIPOS[tipo]
	campos = [
		Campo(
			"nombre", _("Nombre"), "texto", _("Nombre con el que el alumno y el profesional verán la actividad."), defecto=_(info.nombre)
		),
		Campo("descripcion", _("Descripción"), "texto_largo", _("Para qué sirve esta actividad; solo la lee el profesional."), defecto=""),
		Campo(
			"estilo",
			_("Estilo de presentación"),
			"opcion",
			_("Cómo se le habla al alumno."),
			opciones=[
				("del_alumno", _("El de la ficha del alumno")),
				("infantil", _("Infantil")),
				("juvenil", _("Juvenil")),
				("adulto", _("Adulto")),
			],
			defecto="del_alumno",
		),
		Campo(
			"inicio",
			_("Punto de inicio"),
			"posicion",
			_("Dónde empieza el alumno y hacia dónde mira. Vacío: el inicio del entorno."),
			defecto=None,
		),
	]
	if tipo in ("busqueda", "exploracion"):
		campos.append(
			Campo(
				"premios",
				_("Premios"),
				"lista_premios",
				_("Premios escondidos para que el alumno los encuentre."),
				defecto=[],
				grupo="premios",
			)
		)
	if tipo == "busqueda":
		campos.append(
			Campo(
				"orden_obligatorio",
				_("En orden"),
				"si_no",
				_("Los premios hay que encontrarlos en el orden de la lista."),
				defecto=False,
				grupo="premios",
			)
		)
		campos.append(
			Campo(
				"sonido_logro",
				_("Sonido al encontrar un premio"),
				"sonido",
				_("Sonido de celebración."),
				defecto="premio/recogido",
				grupo="premios",
			)
		)
	if tipo == "ruta":
		campos.append(
			Campo(
				"destino",
				_("Destino"),
				"elemento",
				_("Lugar al que hay que llegar."),
				opciones=["espacio", "referencia", "objeto", "abertura"],
				grupo="objetivos",
			)
		)
		campos.append(
			Campo(
				"objetivos",
				_("Paradas intermedias"),
				"lista_objetivos",
				_("Lugares por los que hay que pasar antes, en orden."),
				defecto=[],
				grupo="objetivos",
			)
		)
		campos.append(
			Campo(
				"orden_obligatorio",
				_("En orden"),
				"si_no",
				_("Las paradas se hacen en el orden de la lista."),
				defecto=True,
				grupo="objetivos",
			)
		)
	if tipo == "examen_salida":
		campos.append(
			Campo(
				"numero_pruebas",
				_("Número de pruebas"),
				"entero",
				_("Cuántas pruebas tiene el examen."),
				defecto=5,
				minimo=1,
				maximo=30,
				grupo="examen",
			)
		)
		campos.append(
			Campo(
				"tolerancia_m",
				_("Empate entre salidas (metros)"),
				"decimal",
				_("Diferencia que cuenta como empate."),
				defecto=1.0,
				minimo=0.0,
				maximo=10.0,
				grupo="examen",
			)
		)
	else:
		campos.append(
			Campo(
				"tiempo_limite_s",
				_("Contrarreloj (segundos)"),
				"entero",
				_("Tiempo máximo de juego. Cero: sin límite."),
				defecto=0,
				minimo=0,
				maximo=7200,
			)
		)
		campos.append(
			Campo(
				"usar_niveles",
				_("Retirar las ayudas por niveles"),
				"si_no",
				_("Cada nivel quita alguna ayuda al anterior."),
				defecto=False,
				grupo="ayudas",
			)
		)
		campos.append(
			Campo(
				"nivel",
				_("Nivel de partida"),
				"entero",
				_("Nivel en el que empieza el alumno."),
				defecto=0,
				minimo=0,
				maximo=9,
				grupo="ayudas",
				depende_de="usar_niveles",
			)
		)
	campos.append(
		Campo("ayudas", _("Ayudas permitidas"), "ayudas", _("Qué ayudas puede usar el alumno y cuántas veces."), defecto={}, grupo="ayudas")
	)
	campos.append(Campo("mensajes.inicio", _("Mensaje de inicio"), "texto_largo", _("Se dice al empezar."), defecto="", grupo="mensajes"))
	campos.append(Campo("mensajes.final", _("Mensaje final"), "texto_largo", _("Se dice al terminar."), defecto="", grupo="mensajes"))
	return campos


def _poner(datos: dict[str, Any], clave: str, valor: Any) -> None:
	partes = clave.split(".")
	actual = datos
	for parte in partes[:-1]:
		actual = actual.setdefault(parte, {})
	actual[partes[-1]] = valor


def nueva_actividad(tipo: str, entorno: Any, catalogo: Any = None, **opciones: Any) -> dict[str, Any]:
	"""Actividad nueva de ese tipo con los valores de serie."""
	info = TIPOS[tipo]
	datos: dict[str, Any] = {"formato": FORMATO_ACTIVIDAD, "id": tipo, "tipo": tipo, "modo": info.modo_por_defecto}
	for campo in campos_de(tipo):
		_poner(datos, campo.clave, copy.deepcopy(campo.defecto))
	datos.update(opciones)
	return datos


def validar_actividad(datos: dict[str, Any], entorno: Any, catalogo: Any = None, recursos: Any = None) -> list[Aviso]:
	"""Comprobaciones básicas: nombre, premios en su sitio y destinos que existen.

	``recursos`` se acepta por tener la misma forma que la API real, pero la
	reserva no comprueba los audios del paquete.
	"""
	avisos: list[Aviso] = []
	if not str(datos.get("nombre") or "").strip():
		avisos.append(Aviso("error", "nombre_vacio", _("La actividad no tiene nombre."), "nombre", "", _("Escriba un nombre.")))
	premios = datos.get("premios") or []
	if datos.get("tipo") == "busqueda" and not premios:
		avisos.append(
			Aviso(
				"error",
				"premios_sin_premios",
				_("Una búsqueda del tesoro necesita al menos un premio."),
				"premios",
				"",
				_("Añada un premio o repártalos automáticamente."),
			)
		)
	for premio in premios:
		if not isinstance(premio, dict):
			continue
		_planta, espacio = lugares.espacio_en(entorno, str(premio.get("planta", "")), premio.get("x"), premio.get("y"))
		if espacio is None and not premio.get("dentro_de"):
			avisos.append(
				Aviso(
					"aviso",
					"premio_fuera",
					_("El premio «{nombre}» no está dentro de ningún espacio.").format(nombre=premio.get("nombre", "")),
					"premios",
				)
			)
		contenedor = premio.get("dentro_de")
		if contenedor and (entorno is None or entorno.elemento(contenedor) is None):
			avisos.append(
				Aviso(
					"error",
					"premio_contenedor",
					_("El objeto que esconde el premio «{nombre}» ya no existe.").format(nombre=premio.get("nombre", "")),
					"premios",
				)
			)
	destino = datos.get("destino")
	if datos.get("tipo") == "ruta":
		if not destino:
			avisos.append(
				Aviso("error", "destino_vacio", _("La ruta no tiene destino."), "destino", "", _("Elija el lugar al que hay que llegar."))
			)
		elif isinstance(destino, str) and (entorno is None or entorno.buscar(destino) is None):
			avisos.append(Aviso("error", "destino_inexistente", _("El destino de la ruta ya no existe en el entorno."), "destino"))
	return avisos


def repartir_premios(
	entorno: Any,
	cantidad: int,
	catalogo: Any = None,
	semilla: int | None = None,
	plantas: list[str] | None = None,
	visibilidad: str = "cerca",
	dentro_de_objetos: bool = True,
) -> list[dict[str, Any]]:
	"""Reparte premios por espacios distintos, de modo que haya que recorrerlos todos."""
	azar = random.Random(semilla)
	sitios: list[tuple[Any, Any]] = []
	for planta in lugares.plantas(entorno):
		if plantas and planta.id not in plantas:
			continue
		sitios.extend((planta, espacio) for espacio in lugares.espacios(planta))
	azar.shuffle(sitios)
	premios: list[dict[str, Any]] = []
	if not sitios:
		return premios
	for numero in range(max(0, int(cantidad))):
		planta, espacio = sitios[numero % len(sitios)]
		contenedores = lugares.contenedores(planta, espacio, catalogo) if dentro_de_objetos else []
		dentro = azar.choice(contenedores) if contenedores and azar.random() < 0.5 else None
		if dentro is not None:
			x, y = dentro.x, dentro.y
		else:
			modo = azar.choice([lugares.CENTRO, lugares.ESQUINA])
			x, y = lugares.calcular_punto(espacio, modo, esquina=azar.choice(list(lugares.ESQUINAS)))
		premios.append(
			{
				"id": f"premio-{numero + 1}",
				"nombre": _("Premio {n}").format(n=numero + 1),
				"planta": planta.id,
				"x": round(float(x), 2),
				"y": round(float(y), 2),
				"sonido": "premio/cerca",
				"visibilidad": "oculto" if dentro is not None else visibilidad,
				"dentro_de": dentro.id if dentro is not None else None,
				"mensaje": "",
				"audio": None,
			}
		)
	return premios


def describir_actividad(datos: dict[str, Any], entorno: Any) -> str:
	"""Resumen de una línea: cuántos premios y objetivos tiene."""
	partes: list[str] = []
	premios = datos.get("premios") or []
	objetivos = datos.get("objetivos") or []
	if premios:
		partes.append(_("{n} premios").format(n=len(premios)) if len(premios) != 1 else _("1 premio"))
	if objetivos:
		partes.append(_("{n} objetivos").format(n=len(objetivos)) if len(objetivos) != 1 else _("1 objetivo"))
	if datos.get("destino"):
		partes.append(_("con destino"))
	return ", ".join(partes) or _("sin premios ni objetivos")
