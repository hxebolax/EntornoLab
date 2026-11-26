"""El JSON de una actividad: lectura tolerante y valores de serie.

Una actividad llega del paquete ``.elab`` (escrita por el Estudio, por otra
versión del programa o a mano). ``normalizar`` la deja siempre completa y con
los tipos correctos, sin lanzar excepciones: lo que falta toma su valor de
serie y lo que no se entiende se descarta. Los errores de contenido (un
premio en un sitio imposible, un id que no existe) no se arreglan aquí: los
cuenta ``validar_actividad`` para que el profesional los vea.

Nunca se ejecuta nada de lo que trae una actividad: son solo datos.
"""

from __future__ import annotations

import copy
import logging
import math
from typing import Any

from app.actividades.tipos import (
	ESTILO_DEL_ALUMNO,
	ESTILOS,
	FORMATO_ACTIVIDAD,
	MODOS,
	MODOS_BALIZA,
	NIVELES_SERIE,
	TIPOS,
	VISIBILIDADES,
	valores_por_defecto,
)

log = logging.getLogger(__name__)

TIPOS_OBJETIVO: tuple[str, ...] = ("ir_a", "recoger", "entregar", "salir", "localizar", "senalar")
SONIDO_PREMIO = "premio/cerca"
SONIDO_PREMIO_LEJOS = "premio/aparece"
MAX_TEXTO = 2000
MAX_LISTA = 200


def _texto(valor: Any, maximo: int = MAX_TEXTO) -> str:
	return str(valor).strip()[:maximo] if isinstance(valor, (str, int, float)) and not isinstance(valor, bool) else ""


def _numero(valor: Any, defecto: float | None, minimo: float | None = None, maximo: float | None = None) -> float | None:
	if isinstance(valor, bool) or not isinstance(valor, (int, float, str)):
		return defecto
	try:
		numero = float(valor)
	except ValueError:
		return defecto
	if not math.isfinite(numero):
		return defecto
	if minimo is not None:
		numero = max(minimo, numero)
	if maximo is not None:
		numero = min(maximo, numero)
	return numero


def _entero(valor: Any, defecto: int, minimo: int | None = None, maximo: int | None = None) -> int:
	numero = _numero(valor, float(defecto), minimo, maximo)
	return int(numero) if numero is not None else defecto


def _posicion(valor: Any) -> dict[str, Any] | None:
	"""Una posición ``{"planta", "x", "y", "rumbo"}`` bien formada, o None."""
	if hasattr(valor, "planta") and hasattr(valor, "x"):
		valor = {"planta": valor.planta, "x": valor.x, "y": valor.y, "rumbo": getattr(valor, "rumbo", 0.0)}
	if not isinstance(valor, dict):
		return None
	x, y = _numero(valor.get("x"), None), _numero(valor.get("y"), None)
	planta = _texto(valor.get("planta"), 100)
	if x is None or y is None or not planta:
		return None
	posicion: dict[str, Any] = {
		"planta": planta,
		"x": round(x, 3),
		"y": round(y, 3),
		"rumbo": round((_numero(valor.get("rumbo"), 0.0) or 0.0) % 360.0, 1),
	}
	if _texto(valor.get("nombre")):
		posicion["nombre"] = _texto(valor.get("nombre"), 200)
	return posicion


def normalizar_lugar(valor: Any) -> Any:
	"""Un lugar tal como se guarda: el id de un elemento (texto) o una posición; None si no vale."""
	if isinstance(valor, str):
		return valor.strip()[:100] or None
	if isinstance(valor, (list, tuple)) and len(valor) >= 3:
		return _posicion({"planta": valor[0], "x": valor[1], "y": valor[2]})
	if isinstance(valor, dict) and valor.get("id") and "x" not in valor:
		return _texto(valor.get("id"), 100) or None
	return _posicion(valor)


def normalizar_premio(valor: Any, numero: int, usados: set[str]) -> dict[str, Any] | None:
	"""Un premio completo; None si no es un diccionario."""
	if not isinstance(valor, dict):
		return None
	ident = _texto(valor.get("id"), 100) or f"premio-{numero}"
	base = ident
	sufijo = 2
	while ident in usados:
		ident = f"{base}-{sufijo}"
		sufijo += 1
	usados.add(ident)
	visibilidad = valor.get("visibilidad") if valor.get("visibilidad") in VISIBILIDADES else "cerca"
	x, y = _numero(valor.get("x"), None), _numero(valor.get("y"), None)
	return {
		"id": ident,
		"nombre": _texto(valor.get("nombre"), 200) or ident,
		"planta": _texto(valor.get("planta"), 100),
		"x": round(x, 3) if x is not None else None,
		"y": round(y, 3) if y is not None else None,
		"sonido": _texto(valor.get("sonido"), 200),
		"visibilidad": visibilidad,
		"dentro_de": _texto(valor.get("dentro_de"), 100) or None,
		"mensaje": _texto(valor.get("mensaje")),
		"audio": _texto(valor.get("audio"), 200) or None,
		"vibrar": bool(valor.get("vibrar", True)),
		"pista": _texto(valor.get("pista")),
	}


def normalizar_objetivo(valor: Any, numero: int) -> dict[str, Any] | None:
	"""Un objetivo o una prueba de examen: se conservan sus claves, con los lugares ya normalizados."""
	if isinstance(valor, str):
		valor = {"destino": valor}
	if not isinstance(valor, dict):
		return None
	objetivo: dict[str, Any] = {}
	for clave, dato in valor.items():
		clave = str(clave)[:64]
		if clave in ("destino", "origen", "a", "b", "referencia", "correcta", "via", "recoger", "entregar"):
			objetivo[clave] = normalizar_lugar(dato)
		elif clave == "opciones" and isinstance(dato, list):
			objetivo[clave] = [str(opcion)[:100] for opcion in dato[:12] if isinstance(opcion, str)]
		elif isinstance(dato, (str, int, float, bool)) or dato is None:
			objetivo[clave] = dato[:MAX_TEXTO] if isinstance(dato, str) else dato
	objetivo["id"] = _texto(objetivo.get("id"), 100) or f"objetivo-{numero}"
	tipo = objetivo.get("tipo")
	objetivo["tipo"] = tipo if tipo in TIPOS_OBJETIVO else "ir_a"
	objetivo["texto"] = _texto(objetivo.get("texto"))
	return objetivo


def _lista(valor: Any) -> list[Any]:
	return list(valor)[:MAX_LISTA] if isinstance(valor, (list, tuple)) else []


def _ayudas(valor: Any) -> dict[str, dict[str, Any]]:
	"""Reglas de ayudas completas; admite ``False``, ``True`` o un número como abreviatura (igual que el motor)."""
	from app.motor.sesion import regla_ayuda

	if not isinstance(valor, dict):
		return {}
	return {str(nombre)[:40]: regla_ayuda(regla) for nombre, regla in valor.items()}


def _niveles(valor: Any, usar: bool) -> list[dict[str, Any]]:
	niveles: list[dict[str, Any]] = []
	for nivel in _lista(valor):
		if not isinstance(nivel, dict):
			continue
		baliza = nivel.get("baliza") if nivel.get("baliza") in MODOS_BALIZA else "nunca"
		niveles.append({"nombre": _texto(nivel.get("nombre"), 200), "baliza": baliza, "ayudas": _ayudas(nivel.get("ayudas"))})
	if not niveles and usar:
		niveles = [{"nombre": n["nombre"], "baliza": n["baliza"], "ayudas": _ayudas(n["ayudas"])} for n in NIVELES_SERIE]
	return niveles


def normalizar(datos: Any) -> dict[str, Any]:
	"""Copia completa y bien tipada de una actividad. No lanza excepciones.

	Un tipo desconocido se conserva tal cual (lo señalará la validación) y la
	actividad se trata como una exploración libre: es preferible que el alumno
	pueda entrar al entorno a que no pueda abrir el paquete.
	"""
	bruto = copy.deepcopy(datos) if isinstance(datos, dict) else {}
	tipo = bruto.get("tipo") if isinstance(bruto.get("tipo"), str) else "exploracion"
	info = TIPOS.get(tipo)
	serie = valores_por_defecto(tipo) if info is not None else valores_por_defecto("exploracion")
	limpio: dict[str, Any] = dict(serie)
	# Lo que el formulario no conoce (campos propios del profesional, claves de versiones futuras) se conserva.
	for clave, valor in bruto.items():
		limpio[str(clave)] = valor
	limpio["formato"] = _entero(bruto.get("formato"), FORMATO_ACTIVIDAD, 1)
	limpio["tipo"] = tipo
	limpio["id"] = _texto(bruto.get("id"), 100) or tipo
	limpio["nombre"] = _texto(bruto.get("nombre"), 200) or (info.nombre_visible if info is not None else tipo)
	limpio["descripcion"] = _texto(bruto.get("descripcion"))
	modo = bruto.get("modo")
	limpio["modo"] = modo if modo in MODOS else (info.modo_por_defecto if info is not None else "practica")
	if info is not None and info.grupo == "examen":
		# Un examen es siempre un examen: no se le pueden poner pistas cambiándole el modo.
		limpio["modo"] = "examen"
	estilo = bruto.get("estilo")
	limpio["estilo"] = estilo if estilo in ESTILOS else ESTILO_DEL_ALUMNO
	limpio["inicio"] = _posicion(bruto.get("inicio"))
	usados: set[str] = set()
	premios = [normalizar_premio(premio, numero, usados) for numero, premio in enumerate(_lista(bruto.get("premios")), start=1)]
	limpio["premios"] = [premio for premio in premios if premio is not None]
	objetivos = [normalizar_objetivo(objetivo, numero) for numero, objetivo in enumerate(_lista(bruto.get("objetivos")), start=1)]
	limpio["objetivos"] = [objetivo for objetivo in objetivos if objetivo is not None]
	pruebas = [normalizar_objetivo(prueba, numero) for numero, prueba in enumerate(_lista(bruto.get("pruebas")), start=1)]
	limpio["pruebas"] = [prueba for prueba in pruebas if prueba is not None]
	limpio["orden_obligatorio"] = bool(limpio.get("orden_obligatorio", False))
	limpio["ayudas"] = _ayudas(bruto.get("ayudas"))
	limpio["usar_niveles"] = bool(bruto.get("usar_niveles", False)) or bool(_lista(bruto.get("niveles")))
	limpio["niveles"] = _niveles(bruto.get("niveles"), limpio["usar_niveles"]) if limpio["modo"] != "examen" else []
	limpio["nivel"] = _entero(bruto.get("nivel"), 0, 0, max(0, len(limpio["niveles"]) - 1))
	limpio["baliza"] = bruto.get("baliza") if bruto.get("baliza") in MODOS_BALIZA else str(serie.get("baliza") or "nunca")
	limite = _numero(bruto.get("tiempo_limite_s"), 0.0, 0.0, 86400.0) or 0.0
	limpio["tiempo_limite_s"] = limite if limite > 0.0 else None
	regla = bruto.get("regla_parada")
	if isinstance(regla, dict):
		de = _entero(regla.get("de"), 5, 1, 100)
		limpio["regla_parada"] = {"activa": bool(regla.get("activa", True)), "de": de, "minimo": _entero(regla.get("minimo"), 3, 1, de)}
	elif limpio["modo"] == "examen" and "regla_parada" not in bruto:
		limpio["regla_parada"] = {"activa": True, "de": 5, "minimo": 3}
	else:
		limpio["regla_parada"] = None
	travieso = bruto.get("travieso") if isinstance(bruto.get("travieso"), dict) else {}
	limpio["travieso"] = {
		"activo": bool(travieso.get("activo", False)) and limpio["modo"] != "examen",
		"cada_s": _numero(travieso.get("cada_s"), 90.0, 5.0, 3600.0),
		"veces": _entero(travieso.get("veces"), 2, 1, 50),
	}
	mensajes = bruto.get("mensajes") if isinstance(bruto.get("mensajes"), dict) else {}
	limpio["mensajes"] = {clave: _texto(mensajes.get(clave)) for clave in ("inicio", "logro", "final")}
	recompensas = bruto.get("recompensas") if isinstance(bruto.get("recompensas"), dict) else {}
	desbloqueos = [
		{"estrellas": _entero(regla.get("estrellas"), 5, 1, 10000), "nombre": _texto(regla.get("nombre"), 200)}
		for regla in _lista(recompensas.get("desbloqueos"))
		if isinstance(regla, dict) and _texto(regla.get("nombre"))
	]
	nombre_unico = _texto(recompensas.get("desbloqueo_nombre"), 200)
	if nombre_unico and not any(regla["nombre"] == nombre_unico for regla in desbloqueos):
		desbloqueos.append({"estrellas": _entero(recompensas.get("desbloqueo_estrellas"), 5, 1, 10000), "nombre": nombre_unico})
	limpio["recompensas"] = {
		"desbloqueo_nombre": nombre_unico,
		"desbloqueo_estrellas": _entero(recompensas.get("desbloqueo_estrellas"), 5, 1, 10000),
		"desbloqueos": desbloqueos,
		"estrellas_previas": _entero(recompensas.get("estrellas_previas"), 0, 0),
	}
	limpio["cuestionario"] = bool(bruto.get("cuestionario", False))
	limpio["fallos_para_ayuda"] = _entero(bruto.get("fallos_para_ayuda"), 3, 0, 100)
	semilla = bruto.get("semilla")
	limpio["semilla"] = (
		_entero(semilla, 1, 0) if semilla is not None and not isinstance(semilla, bool) else (1 if limpio["modo"] == "examen" else None)
	)
	for clave in ("destino", "espacio", "corte"):
		if clave in limpio:
			limpio[clave] = normalizar_lugar(limpio.get(clave))
	# El formulario edita un solo paso cortado («corte»); a mano se pueden dar varios en «cortes».
	# Si los dos están y no casan, manda el del formulario: es lo último que tocó el profesional.
	cortes = [corte for corte in (normalizar_lugar(corte) for corte in _lista(bruto.get("cortes"))) if isinstance(corte, str)]
	corte = limpio.get("corte") if isinstance(limpio.get("corte"), str) else None
	if corte is not None and corte not in cortes:
		cortes = [corte]
	limpio["cortes"] = cortes
	if tipo == "ruta_alternativa":
		limpio["corte"] = corte if corte is not None else (cortes[0] if cortes else None)
	# Los números propios de cada tipo se acotan con los límites que declara su formulario.
	if info is not None:
		from app.actividades.tipos import campos_de, leer_campo, poner_campo

		for campo in campos_de(tipo):
			if (
				campo.tipo not in ("entero", "decimal")
				or "." in campo.clave
				or campo.clave in ("tiempo_limite_s", "nivel", "semilla", "fallos_para_ayuda")
			):
				continue
			valor = _numero(leer_campo(limpio, campo.clave), campo.defecto, campo.minimo, campo.maximo)
			if valor is not None and campo.tipo == "entero":
				valor = int(valor)
			poner_campo(limpio, campo.clave, valor)
	return limpio
