"""Puente con ``app.actividades``: lo único que el reproductor sabe de las actividades.

El reproductor no interpreta las actividades: las crea con
``app.actividades.crear_actividad`` y se las pasa a la ``Sesion``. Este módulo
concentra esas llamadas por dos motivos:

- **Tolerancia.** Si el paquete de actividades falta o falla al importarse
  (una instalación a medias), el reproductor sigue sirviendo para la
  exploración libre y lo dice con claridad, en vez de no arrancar.
- **Un solo sitio que cambiar** si la interfaz de las actividades cambia.

Interfaz que se usa (ver ``docs/actividades.md``): ``crear_actividad(datos,
entorno, catalogo=None, estilo=None, semilla=None, nivel=None)``, ``describir_actividad``,
``recompensas.calcular(resultado, estilo)`` y ``cuestionario.preguntas(estilo)``. De la
actividad creada: ``nombre``, ``tipo``, ``modo``, ``ajustes(base)``,
``inicio()``, ``estado()`` (con ``pregunta``), ``confirmar(sesion)``,
``responder(sesion, opcion)``, ``orden_profesional(sesion, tipo, datos)``,
``valorar(sesion, respuestas)`` y ``resultado(sesion)``. Todo lo que falte se
tolera: un doble de pruebas o una versión antigua puede no tenerlo.
"""

from __future__ import annotations

import importlib
import logging
from collections.abc import Callable
from typing import Any

from app.core.i18n import N_, _

log = logging.getLogger(__name__)

MODOS: tuple[str, ...] = ("juego", "practica", "examen")
_avisados: set[str] = set()

# Preguntas de valoración que se ofrecen si el módulo de cuestionarios no da otras.
# Coinciden con lo que entiende el seguimiento (evento «valoracion»: esfuerzo, confianza, disfrute).
_PREGUNTAS_DE_RESERVA: tuple[tuple[str, str], ...] = (
	("esfuerzo", N_("¿Cuánto te ha costado?")),
	("confianza", N_("¿Sabrías moverte ahora por este lugar?")),
	("disfrute", N_("¿Te ha gustado?")),
)
_ESCALA_DE_RESERVA: tuple[tuple[int, str], ...] = (
	(1, N_("Nada")),
	(2, N_("Poco")),
	(3, N_("Regular")),
	(4, N_("Bastante")),
	(5, N_("Mucho")),
)


class ErrorActividad(Exception):
	"""Una actividad no se puede preparar. El mensaje está pensado para decírselo al alumno."""


def _importar(nombre: str) -> Any | None:
	"""Importa un módulo de actividades; None (y un aviso, una vez) si falta o no se puede cargar."""
	try:
		return importlib.import_module(nombre)
	except Exception:  # noqa: BLE001 - una instalación a medias o un módulo roto no debe impedir la exploración libre
		if nombre not in _avisados:
			_avisados.add(nombre)
			log.warning("El módulo %s no está disponible.", nombre, exc_info=True)
		return None


def modulo() -> Any | None:
	"""El paquete ``app.actividades``, o None si no está o no se puede importar."""
	return _importar("app.actividades")


def disponible() -> bool:
	"""Si se pueden jugar actividades (además de la exploración libre)."""
	return callable(getattr(modulo(), "crear_actividad", None))


def crear(
	datos: dict[str, Any],
	entorno: Any,
	catalogo: Any = None,
	estilo: str | None = None,
	semilla: int | None = None,
	nivel: int | None = None,
) -> Any:
	"""Crea la actividad descrita por ``datos``. Lanza ``ErrorActividad`` con una frase clara si no se puede.

	``semilla`` es la de la partida (un examen usa la suya y la ignora) y
	``nivel``, el nivel de ayudas en que quedó el alumno la vez anterior. El
	nivel solo se pasa si se conoce: así sirve también una fábrica que aún no
	lo acepte.
	"""
	nombre = str(datos.get("nombre") or datos.get("id") or _("sin nombre"))
	fabrica = getattr(modulo(), "crear_actividad", None)
	if not callable(fabrica):
		raise ErrorActividad(_("En esta instalación no se pueden jugar actividades. Puedes hacer la exploración libre."))
	opciones: dict[str, Any] = {"estilo": estilo, "semilla": semilla}
	if nivel is not None:
		opciones["nivel"] = int(nivel)
	try:
		actividad = fabrica(datos, entorno, catalogo, **opciones)
	except Exception as error:  # noqa: BLE001 - una actividad mal definida es un dato de terceros: se dice y se sigue
		log.exception("No se pudo crear la actividad «%s»", datos.get("id"))
		raise ErrorActividad(_("La actividad «{nombre}» no se puede preparar: está mal definida.").format(nombre=nombre)) from error
	if actividad is None:
		raise ErrorActividad(_("La actividad «{nombre}» no se puede preparar.").format(nombre=nombre))
	return actividad


def describir(datos: dict[str, Any], entorno: Any = None) -> str:
	"""Frase que describe una actividad en el menú; si el módulo no la da, su nombre y su descripción."""
	funcion = getattr(modulo(), "describir_actividad", None)
	if callable(funcion):
		try:
			texto = funcion(datos, entorno)
		except Exception:  # noqa: BLE001 - igual que al crearla: datos de terceros
			log.exception("No se pudo describir la actividad «%s»", datos.get("id"))
			texto = ""
		if isinstance(texto, str) and texto.strip():
			return texto.strip()
	descripcion = str(datos.get("descripcion") or "").strip()
	return descripcion or _("Sin descripción.")


def modo_de(actividad: Any) -> str:
	"""«juego», «practica» o «examen» (lo que entiende la grabadora); «juego» si la actividad dice otra cosa."""
	modo = str(getattr(actividad, "modo", "") or "juego")
	return modo if modo in MODOS else "juego"


def estado_de(actividad: Any) -> dict[str, Any]:
	"""``actividad.estado()`` (objetivo, hechos, total, puntos, estrellas, tiempo_restante, nivel), o vacío."""
	funcion = getattr(actividad, "estado", None)
	if not callable(funcion):
		return {}
	try:
		estado = funcion()
	except Exception:  # noqa: BLE001 - la actividad es código ajeno al reproductor; se anota y se sigue
		log.exception("Fallo al pedir el estado a la actividad")
		return {}
	return dict(estado) if isinstance(estado, dict) else {}


def pregunta_de(actividad: Any) -> dict[str, Any] | None:
	"""La pregunta con opciones que la actividad espera que se conteste, o None.

	Sale de ``estado()["pregunta"]`` y no de la orden «objetivo»: consultarla
	así no gasta usos de esa ayuda ni mueve la opción elegida. Devuelve
	``{"texto", "opciones": [str], "elegida": int}`` (−1 si no hay ninguna elegida).
	"""
	pregunta = estado_de(actividad).get("pregunta") if actividad is not None else None
	if not isinstance(pregunta, dict):
		return None
	texto = str(pregunta.get("texto") or "").strip()
	opciones = [str(opcion) for opcion in pregunta.get("opciones") or () if str(opcion).strip()]
	if not texto or not opciones:
		return None
	elegida = pregunta.get("elegida")
	elegida = elegida if isinstance(elegida, int) and not isinstance(elegida, bool) and 0 <= elegida < len(opciones) else -1
	return {"texto": texto, "opciones": opciones, "elegida": elegida}


def _eventos_de(actividad: Any, metodo: str, *argumentos: Any) -> list[Any] | None:
	"""Llama a un método de la actividad que devuelve eventos; None si no lo tiene o falla (se anota)."""
	funcion: Callable[..., Any] | None = getattr(actividad, metodo, None) if actividad is not None else None
	if not callable(funcion):
		return None
	try:
		eventos = funcion(*argumentos)
	except Exception:  # noqa: BLE001 - la actividad es código ajeno al reproductor: se anota y la partida sigue
		log.exception("Fallo de la actividad en «%s»", metodo)
		return None
	return list(eventos) if isinstance(eventos, (list, tuple)) else []


def confirmar(actividad: Any, sesion: Any) -> list[Any] | None:
	"""``actividad.confirmar(sesion)``: «ya he llegado», «es hacia ahí», «esta respuesta». None si no sabe confirmar."""
	return _eventos_de(actividad, "confirmar", sesion)


def responder(actividad: Any, sesion: Any, opcion: int) -> list[Any] | None:
	"""``actividad.responder(sesion, opcion)``: elige una opción de la pregunta en curso (0 es la primera)."""
	return _eventos_de(actividad, "responder", sesion, int(opcion))


def orden(actividad: Any, sesion: Any, tipo: str, datos: dict[str, Any]) -> list[Any] | None:
	"""``actividad.orden_profesional(sesion, tipo, datos)``: los eventos que hay que presentar, o None si no la atiende."""
	return _eventos_de(actividad, "orden_profesional", sesion, tipo, dict(datos))


def termina_a_voluntad(actividad: Any) -> bool:
	"""Si la actividad no tiene final propio y la termina el alumno cuando quiere (la exploración libre).

	Dejarla no es abandonarla: se cierra como terminada y se va a la pantalla de fin.
	"""
	return bool(getattr(actividad, "TERMINA_A_VOLUNTAD", False))


def recompensas(resultado: dict[str, Any], estilo: str | None) -> list[dict[str, Any]]:
	"""Recompensas ganadas con ese resultado; lista vacía si no hay ninguna.

	Si el resultado ya las trae (clave ``recompensas``), son esas; si no, se
	calculan con ``app.actividades.recompensas.calcular(resultado, estilo)``.
	"""
	propias = resultado.get("recompensas")
	if isinstance(propias, (list, tuple)):
		return [dict(r) for r in propias if isinstance(r, dict)]
	calcular = getattr(_importar("app.actividades.recompensas"), "calcular", None)
	if not callable(calcular):
		return []
	try:
		lista = calcular(resultado, estilo)
	except Exception:  # noqa: BLE001 - sin recompensas se puede terminar la actividad igual
		log.exception("No se pudieron calcular las recompensas")
		return []
	return [dict(r) for r in (lista or []) if isinstance(r, dict)]


def _pregunta_normalizada(pregunta: Any) -> dict[str, Any] | None:
	"""Una pregunta en la forma que usa el menú: ``{"id", "texto", "opciones": [(valor, texto), ...]}``."""
	if not isinstance(pregunta, dict):
		pregunta = {clave: getattr(pregunta, clave, None) for clave in ("id", "texto", "opciones")}
	texto = str(pregunta.get("texto") or pregunta.get("pregunta") or "").strip()
	if not texto:
		return None
	opciones: list[tuple[Any, str]] = []
	for opcion in pregunta.get("opciones") or ():
		if isinstance(opcion, dict):
			opciones.append((opcion.get("valor", opcion.get("id")), str(opcion.get("texto") or opcion.get("nombre") or "")))
		elif isinstance(opcion, (tuple, list)) and len(opcion) >= 2:
			opciones.append((opcion[0], str(opcion[1])))
		else:
			opciones.append((opcion, str(opcion)))
	opciones = [(valor, etiqueta) for valor, etiqueta in opciones if etiqueta]
	if not opciones:
		opciones = [(valor, _(etiqueta)) for valor, etiqueta in _ESCALA_DE_RESERVA]
	return {"id": str(pregunta.get("id") or texto[:40]), "texto": texto, "opciones": opciones}


def preguntas(estilo: str | None, resultado: dict[str, Any] | None = None) -> list[dict[str, Any]]:
	"""Preguntas opcionales para después de la actividad, cada una ``{"id", "texto", "opciones": [(valor, texto)]}``.

	Manda la actividad: si su resultado trae la clave ``cuestionario``, esas
	son las preguntas (una lista vacía significa que el profesional no las
	quiere). Si no la trae, salen de ``app.actividades.cuestionario.preguntas(estilo)``
	y, si el módulo no existe, se ofrecen tres de reserva (esfuerzo,
	confianza y disfrute) con una escala de cinco.
	"""
	encontradas: list[dict[str, Any]] = []
	if isinstance(resultado, dict) and isinstance(resultado.get("cuestionario"), (list, tuple)):
		for cruda in resultado["cuestionario"]:
			normal = _pregunta_normalizada(cruda)
			if normal is not None:
				encontradas.append(normal)
		return encontradas
	funcion = getattr(_importar("app.actividades.cuestionario"), "preguntas", None)
	if callable(funcion):
		try:
			crudas = funcion(estilo or "adulto")
		except Exception:  # noqa: BLE001 - el cuestionario es opcional: sin él se usan las preguntas de reserva
			log.exception("No se pudieron obtener las preguntas del cuestionario")
			crudas = None
		for cruda in crudas or ():
			normal = _pregunta_normalizada(cruda)
			if normal is not None:
				encontradas.append(normal)
	if encontradas:
		return encontradas
	return [
		{"id": identificador, "texto": _(texto), "opciones": [(valor, _(etiqueta)) for valor, etiqueta in _ESCALA_DE_RESERVA]}
		for identificador, texto in _PREGUNTAS_DE_RESERVA
	]


def presentacion_preguntas(estilo: str | None) -> str:
	"""Frase con la que se ofrecen las preguntas, dejando claro que son opcionales."""
	funcion = getattr(_importar("app.actividades.cuestionario"), "presentacion", None)
	if callable(funcion):
		try:
			texto = funcion(estilo or "adulto")
		except Exception:  # noqa: BLE001 - es solo una frase de cortesía
			log.exception("No se pudo obtener la presentación del cuestionario")
			texto = ""
		if isinstance(texto, str) and texto.strip():
			return texto.strip()
	return _("Unas preguntas breves y opcionales.")
