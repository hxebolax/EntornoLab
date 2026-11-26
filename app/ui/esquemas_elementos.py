"""Esquemas de las propiedades de cada clase de elemento y de las órdenes de «Insertar» y «Editar», sin wx.

Dos tablas:

- ``esquema_de(elemento, …)`` da los campos del formulario de PROPIEDADES de
  un elemento según su clase. Las claves coinciden con las de
  ``operaciones.valores_de`` y ``operaciones.aplicar_valores``.
- ``ORDENES`` describe cada orden que crea o cambia algo con un formulario:
  su título, sus campos, sus valores de partida, el nombre con que queda en
  el historial y la función que la hace con ``app.dominio.edicion``.

Para añadir un tipo de elemento o una orden nueva basta añadir aquí su
esquema: el diálogo, la validación, la ayuda de Control+H y las letras de
acceso salen solos (ver docs/estudio.md).

Las tres formas de colocar están en estos formularios: por MEDIDAS (ancho,
fondo, coordenadas en metros) y por RELACIÓN («adosada al este del salón»,
«en la pared norte, a 1,20 m de la esquina oeste»). La tercera, recorriendo,
está en ``app/ui/recorrido.py``.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from app.core.i18n import N_, _
from app.dominio import edicion
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.edicion import ErrorEdicion
from app.dominio.modelo import (
	ACUSTICAS,
	ESTADOS_ABERTURA,
	HOJAS,
	MATERIALES_PARED,
	NIVELES_TRAFICO,
	PASAMANOS,
	SENTIDOS_VIA,
	SUELOS,
	TIPOS_ABERTURA,
	TIPOS_ESPACIO,
	TIPOS_REFERENCIA,
	Abertura,
	Conector,
	Entorno,
	Espacio,
	FuenteSonido,
	Objeto,
	Pared,
	Planta,
	Referencia,
	Via,
	ZonaSuelo,
)
from app.ui import operaciones
from app.ui.esquemas import Campo, c, opciones_de

LADOS = [("norte", N_("Norte")), ("este", N_("Este")), ("sur", N_("Sur")), ("oeste", N_("Oeste"))]
ALINEACIONES = [
	("inicio", N_("Igualada por el extremo oeste o sur")),
	("centro", N_("Centrada")),
	("fin", N_("Igualada por el extremo este o norte")),
]
RUMBOS = [
	(0.0, N_("Norte")),
	(45.0, N_("Noreste")),
	(90.0, N_("Este")),
	(135.0, N_("Sureste")),
	(180.0, N_("Sur")),
	(225.0, N_("Suroeste")),
	(270.0, N_("Oeste")),
	(315.0, N_("Noroeste")),
]
SIN_VALOR = ""


def _traducidas(opciones: list[tuple[Any, str]]) -> list[tuple[Any, str]]:
	return [(valor, _(texto)) for valor, texto in opciones]


def _con_habitual(tabla: dict[Any, str], texto: str) -> list[tuple[Any, str]]:
	"""Opciones de una tabla del modelo precedidas de «el habitual», que deja decidir al programa."""
	return [(SIN_VALOR, _(texto))] + opciones_de(tabla)


# ── Opciones que salen del entorno ───────────────────────────────────────────


def plantas(entorno: Entorno, exteriores: bool | None = None) -> list[tuple[str, str]]:
	"""Plantas como opciones; con ``exteriores`` se filtran los planos de calle (True) o los interiores (False)."""
	return [
		(planta.id, operaciones.nombre_de(planta))
		for planta in sorted(entorno.plantas, key=lambda p: p.nivel)
		if exteriores is None or planta.exterior == exteriores
	]


def espacios(entorno: Entorno, id_planta: Any, macizos: bool = True) -> list[tuple[str, str]]:
	"""Espacios de una planta como opciones."""
	planta = entorno.planta(str(id_planta or ""))
	if planta is None:
		return []
	return [(espacio.id, operaciones.nombre_de(espacio)) for espacio in planta.espacios if macizos or not espacio.macizo]


def vias(entorno: Entorno, id_planta: Any) -> list[tuple[str, str]]:
	"""Calles de una planta como opciones."""
	planta = entorno.planta(str(id_planta or ""))
	return [(via.id, operaciones.nombre_de(via)) for via in planta.vias] if planta is not None else []


def sonidos() -> list[tuple[str, str]]:
	"""Sonidos de serie como opciones para una fuente de sonido (lista vacía si no hay catálogo de sonidos)."""
	from app.ui.complemento_propio import sonidos_de_serie

	lista = sonidos_de_serie()
	fuentes = [par for par in lista if par[0].startswith(("fuente/", "ambiente/"))]
	return fuentes + [par for par in lista if par not in fuentes]


# ── Propiedades de cada clase de elemento ────────────────────────────────────

_NOMBRE = c("nombre", N_("Nombre"), obligatorio=True, ayuda=N_("Como lo nombrará el programa al alumno y en las listas."))
_DESCRIPCION = c("descripcion", N_("Descripción"), "largo", N_("Lo que se le dice al alumno cuando pregunta por este elemento."))
_X = c("x", N_("Posición al este, x (metros)"), "metros", N_("Metros hacia el este desde el origen del plano."), obligatorio=True)
_Y = c("y", N_("Posición al norte, y (metros)"), "metros", N_("Metros hacia el norte desde el origen del plano."), obligatorio=True)


def _esquema_entorno(entorno: Entorno) -> list[Campo]:
	inicio = N_("Punto de inicio")
	return [
		c("nombre", N_("Nombre del entorno"), obligatorio=True),
		c("descripcion", N_("Descripción"), "largo", N_("Qué lugar es y para qué se ha preparado.")),
		c("autor", N_("Autor")),
		c("procedencia", N_("Procedencia"), "solo_lectura", N_("De dónde viene el entorno, si se importó.")),
		c(
			"inicio_planta",
			N_("Planta del punto de inicio"),
			"opcion",
			N_("Dónde empieza el alumno si la actividad no dice otra cosa."),
			opciones=plantas(entorno),
			grupo=inicio,
		),
		c("inicio_x", N_("Inicio al este, x (metros)"), "metros", grupo=inicio),
		c("inicio_y", N_("Inicio al norte, y (metros)"), "metros", grupo=inicio),
		c("inicio_rumbo", N_("Hacia dónde mira al empezar"), "opcion", opciones=_traducidas(RUMBOS), grupo=inicio),
	]


def _esquema_planta() -> list[Campo]:
	return [
		_NOMBRE,
		_DESCRIPCION,
		c(
			"nivel",
			N_("Nivel"),
			"entero",
			N_("0 es la planta baja; 1, la primera; -1, el sótano."),
			obligatorio=True,
			minimo=-20,
			maximo=200,
		),
		c(
			"altura_m",
			N_("Altura del suelo (metros)"),
			"metros",
			N_("Cota del suelo de la planta respecto de la planta baja."),
			obligatorio=True,
		),
		c("exterior", N_("Es un plano de calle"), "si_no", N_("Las plantas de calle admiten calles, aceras, cruces y pasos de peatones.")),
	]


def _es_paso(valores: dict[str, Any]) -> bool:
	return valores.get("tipo") == "paso_peatones"


def _esquema_espacio() -> list[Campo]:
	# En tres pestañas: son muchos campos para una sola página (no quedarían letras de acceso para todos).
	materiales = N_("Suelo y paredes")
	forma = N_("Forma")
	return [
		_NOMBRE,
		_DESCRIPCION,
		c("tipo", N_("Tipo de espacio"), "opcion", opciones=opciones_de(TIPOS_ESPACIO), recarga=True),
		c("ancho", N_("Ancho, de oeste a este (metros)"), "metros", obligatorio=True, minimo=0.2, maximo=2000),
		c("fondo", N_("Fondo, de sur a norte (metros)"), "metros", obligatorio=True, minimo=0.2, maximo=2000),
		c("semaforo", N_("Tiene semáforo"), "si_no", si=_es_paso),
		c("sonoro", N_("El semáforo es sonoro"), "si_no", si=_es_paso),
		c("pulsador", N_("Tiene pulsador"), "si_no", si=_es_paso),
		c("isleta", N_("Tiene isleta en medio"), "si_no", si=_es_paso),
		c("suelo", N_("Suelo"), "opcion", N_("Decide el sonido de los pasos."), opciones=opciones_de(SUELOS), grupo=materiales),
		c("acustica", N_("Acústica"), "opcion", N_("El eco que se oye dentro."), opciones=opciones_de(ACUSTICAS), grupo=materiales),
		c("pared_material", N_("Material de las paredes"), "opcion", opciones=opciones_de(MATERIALES_PARED), grupo=materiales),
		c("cerrado", N_("Tiene paredes"), "si_no", N_("Sin marcar es solo una zona, como una acera o una plaza."), grupo=materiales),
		c("macizo", N_("Es macizo: no se puede entrar"), "si_no", N_("Un edificio visto desde la calle."), grupo=materiales),
		c(
			"x",
			N_("Esquina suroeste al este, x (metros)"),
			"metros",
			N_("Al cambiarla, el espacio se mueve con todo lo que contiene."),
			obligatorio=True,
			grupo=forma,
		),
		c(
			"y",
			N_("Esquina suroeste al norte, y (metros)"),
			"metros",
			N_("Al cambiarla, el espacio se mueve con todo lo que contiene."),
			obligatorio=True,
			grupo=forma,
		),
		c("contorno", N_("Esquinas"), "solo_lectura", N_("Las esquinas del contorno, x e y en metros."), grupo=forma),
	]


def _esquema_pared() -> list[Campo]:
	return [
		c("nombre", N_("Nombre")),
		_DESCRIPCION,
		c("ax", N_("Primer extremo al este, x (metros)"), "metros", obligatorio=True),
		c("ay", N_("Primer extremo al norte, y (metros)"), "metros", obligatorio=True),
		c("bx", N_("Segundo extremo al este, x (metros)"), "metros", obligatorio=True),
		c("by", N_("Segundo extremo al norte, y (metros)"), "metros", obligatorio=True),
		c("grosor", N_("Grosor (metros)"), "metros", obligatorio=True, minimo=0.01, maximo=5),
		c("altura", N_("Altura (metros)"), "metros", obligatorio=True, minimo=0.1, maximo=50),
		c("material", N_("Material"), "opcion", opciones=opciones_de(MATERIALES_PARED)),
		c("bloquea_paso", N_("Corta el paso"), "si_no"),
		c("bloquea_sonido", N_("Corta el sonido"), "si_no", N_("Desmárquelo en una valla o un cristal.")),
	]


def _esquema_abertura() -> list[Campo]:
	return [
		c("nombre", N_("Nombre")),
		_DESCRIPCION,
		c("tipo", N_("Tipo"), "opcion", opciones=opciones_de(TIPOS_ABERTURA)),
		c(
			"ancho",
			N_("Ancho del hueco (metros)"),
			"metros",
			N_("Se cambia desde el centro de la puerta."),
			obligatorio=True,
			minimo=0.3,
			maximo=20,
		),
		c("estado", N_("Estado"), "opcion", opciones=opciones_de(ESTADOS_ABERTURA)),
		c("hoja", N_("Hoja"), "opcion", opciones=opciones_de(HOJAS)),
		c("material", N_("Material")),
		c("es_salida", N_("Cuenta como salida del edificio"), "si_no", N_("Para los juegos y exámenes de salir del edificio.")),
	]


def _esquema_objeto(objeto: Objeto, catalogo: Catalogo | None) -> list[Campo]:
	definicion = catalogo.definicion_de(objeto) if catalogo is not None else None
	variantes = [(SIN_VALOR, _("Medidas propias"))]
	estados: list[tuple[str, str]] = [(SIN_VALOR, _("Sin estado"))]
	if definicion is not None:
		variantes += [(variante.id, variante.nombre) for variante in definicion.variantes]
		estados += [(estado, catalogo.nombre_estado(objeto.tipo, estado)) for estado in definicion.estados]  # type: ignore[union-attr]
	return [
		_NOMBRE,
		_DESCRIPCION,
		c("tipo_objeto", N_("Objeto del catálogo"), "solo_lectura"),
		c("variante", N_("Variante"), "opcion", N_("Al elegir una variante se ponen sus medidas."), opciones=variantes),
		c("ancho", N_("Ancho (metros)"), "metros", obligatorio=True, minimo=0.01, maximo=100),
		c("fondo", N_("Fondo (metros)"), "metros", obligatorio=True, minimo=0.01, maximo=100),
		c("alto", N_("Alto (metros)"), "metros", obligatorio=True, minimo=0.01, maximo=100),
		c("x", N_("Centro al este, x (metros)"), "metros", obligatorio=True),
		c("y", N_("Centro al norte, y (metros)"), "metros", obligatorio=True),
		c(
			"rumbo",
			N_("Hacia dónde mira (grados)"),
			"decimal",
			N_("0 es el norte y 90 el este, en el sentido del reloj."),
			obligatorio=True,
			minimo=0,
			maximo=360,
		),
		c("estado", N_("Estado"), "opcion", opciones=estados),
	]


def _campo_sonido_de_fuente() -> Campo:
	"""Como ``_campo_sonido``; se resuelve al pedir el esquema porque esa función se define más abajo."""
	return _campo_sonido()


def _esquema_fuente() -> list[Campo]:
	return [
		_NOMBRE,
		_DESCRIPCION,
		_campo_sonido_de_fuente(),
		_X,
		_Y,
		c("volumen", N_("Volumen"), "deslizador", minimo=0, maximo=100, extra={"unidad": N_("por ciento"), "paso": 5}),
		c("radio", N_("Distancia a la que se oye (metros)"), "metros", obligatorio=True, minimo=0.5, maximo=500),
		c("bucle", N_("Suena sin parar"), "si_no"),
		c(
			"intervalo",
			N_("Segundos entre repeticiones"),
			"decimal",
			N_("Si no suena sin parar, cada cuánto se repite."),
			minimo=0,
			maximo=3600,
		),
		c("altura", N_("Altura sobre el suelo (metros)"), "metros", minimo=0, maximo=50),
	]


def _esquema_zona() -> list[Campo]:
	return [
		_NOMBRE,
		_DESCRIPCION,
		c("suelo", N_("Suelo"), "opcion", opciones=opciones_de(SUELOS)),
		c("ancho", N_("Ancho, de oeste a este (metros)"), "metros", obligatorio=True, minimo=0.05, maximo=2000),
		c("fondo", N_("Fondo, de sur a norte (metros)"), "metros", obligatorio=True, minimo=0.05, maximo=2000),
		c("x", N_("Esquina suroeste al este, x (metros)"), "metros", obligatorio=True),
		c("y", N_("Esquina suroeste al norte, y (metros)"), "metros", obligatorio=True),
	]


def _esquema_referencia() -> list[Campo]:
	return [
		_NOMBRE,
		_DESCRIPCION,
		c("tipo", N_("Tipo de referencia"), "opcion", opciones=opciones_de(TIPOS_REFERENCIA)),
		_X,
		_Y,
		c("permanente", N_("Es permanente"), "si_no", N_("Desmárquelo en lo que hoy está y mañana puede no estar.")),
	]


def _esquema_via() -> list[Campo]:
	return [
		_NOMBRE,
		_DESCRIPCION,
		c("ancho", N_("Ancho de la calzada (metros)"), "metros", N_("No rehace las aceras."), obligatorio=True, minimo=1, maximo=100),
		c("carriles", N_("Carriles"), "entero", obligatorio=True, minimo=1, maximo=12),
		c("sentido", N_("Sentido"), "opcion", opciones=opciones_de(SENTIDOS_VIA)),
		c("trafico", N_("Tráfico"), "opcion", opciones=opciones_de(NIVELES_TRAFICO)),
		c("velocidad_kmh", N_("Velocidad de los coches (kilómetros por hora)"), "decimal", obligatorio=True, minimo=5, maximo=130),
	]


def _esquema_conector(conector: Conector) -> list[Campo]:
	campos = [_NOMBRE, _DESCRIPCION, c("tipo_conector", N_("Tipo"), "solo_lectura")]
	if conector.tipo == "ascensor":
		campos.append(c("aviso_hablado", N_("Dice la planta al llegar"), "si_no"))
	else:
		campos.append(c("pasamanos", N_("Pasamanos"), "opcion", opciones=opciones_de(PASAMANOS)))
		campos.append(c("anchura", N_("Anchura (metros)"), "metros", minimo=0.4, maximo=20))
	return campos


def esquema_de(elemento: Any, entorno: Entorno, catalogo: Catalogo | None = None) -> list[Campo]:
	"""Campos del formulario de propiedades de un elemento, según su clase. Lista vacía si no tiene."""
	if isinstance(elemento, Entorno):
		return _esquema_entorno(entorno)
	if isinstance(elemento, Planta):
		return _esquema_planta()
	if isinstance(elemento, Espacio):
		return _esquema_espacio()
	if isinstance(elemento, Pared):
		return _esquema_pared()
	if isinstance(elemento, Abertura):
		return _esquema_abertura()
	if isinstance(elemento, Objeto):
		return _esquema_objeto(elemento, catalogo)
	if isinstance(elemento, FuenteSonido):
		return _esquema_fuente()
	if isinstance(elemento, ZonaSuelo):
		return _esquema_zona()
	if isinstance(elemento, Referencia):
		return _esquema_referencia()
	if isinstance(elemento, Via):
		return _esquema_via()
	if isinstance(elemento, Conector):
		return _esquema_conector(elemento)
	return []


# ── Órdenes con formulario ───────────────────────────────────────────────────


@dataclass(frozen=True)
class Orden:
	"""Una orden que se hace rellenando un formulario.

	``campos(contexto)`` da el esquema, ``valores(contexto)`` los valores de
	partida, ``nombre(valores)`` el texto que queda en el historial («crear la
	habitación Cocina») y ``hacer(contexto, valores)`` hace el cambio y
	devuelve el elemento creado o cambiado. ``requisito(contexto)`` devuelve
	una frase si la orden no se puede usar ahora (y entonces no se abre).
	"""

	titulo: str
	campos: Callable[[Any], list[Campo]]
	hacer: Callable[[Any, dict[str, Any]], Any]
	nombre: Callable[[dict[str, Any]], str]
	valores: Callable[[Any], dict[str, Any]] = lambda _contexto: {}
	requisito: Callable[[Any], str | None] = lambda _contexto: None
	introduccion: str = ""


def _planta(contexto: Any, valores: dict[str, Any], clave: str = "planta") -> Planta:
	planta = contexto.entorno.planta(str(valores.get(clave) or ""))
	if planta is None:
		raise ErrorEdicion(_("Elija una planta."))
	return planta


def _espacio(contexto: Any, valores: dict[str, Any], clave: str = "espacio") -> tuple[Planta, Espacio]:
	planta = _planta(contexto, valores)
	espacio = planta.espacio(str(valores.get(clave) or ""))
	if espacio is None:
		raise ErrorEdicion(_("Elija un espacio de la planta «{planta}».").format(planta=operaciones.nombre_de(planta)))
	return planta, espacio


def _via(contexto: Any, valores: dict[str, Any], clave: str = "via") -> tuple[Planta, Via]:
	planta = _planta(contexto, valores)
	via = next((v for v in planta.vias if v.id == valores.get(clave)), None)
	if via is None:
		raise ErrorEdicion(_("Elija una calle de la planta «{planta}».").format(planta=operaciones.nombre_de(planta)))
	return planta, via


def _espacio_actual(contexto: Any) -> tuple[str, str]:
	"""(id de planta, id de espacio) del sitio donde está trabajando la persona, según la selección."""
	planta = contexto.planta_actual()
	if planta is None:
		return "", ""
	elegido = contexto.elemento_seleccionado()
	espacio: Espacio | None = None
	if elegido is not None and elegido[0] is planta:
		elemento = elegido[1]
		if isinstance(elemento, Espacio):
			espacio = elemento
		elif not isinstance(elemento, (Planta, Via, Pared)):
			try:
				espacio = planta.espacio_en(*edicion.centro_de(elemento))
			except ValueError, TypeError, ZeroDivisionError:
				espacio = None
	if espacio is None and planta.espacios:
		espacio = planta.espacios[0]
	return planta.id, espacio.id if espacio is not None else ""


def _punto_actual(contexto: Any) -> tuple[float, float]:
	"""Punto que se propone para algo nuevo: el centro del espacio en el que se está trabajando."""
	planta = contexto.planta_actual()
	_id_planta, id_espacio = _espacio_actual(contexto)
	espacio = planta.espacio(id_espacio) if planta is not None else None
	if espacio is None:
		return 0.0, 0.0
	x, y = espacio.centro()
	return round(x, 2), round(y, 2)


def _sitio_libre(contexto: Any) -> tuple[float, float]:
	"""Esquina suroeste que se propone para una habitación nueva: al este de lo que ya hay, para no pisarlo."""
	planta = contexto.planta_actual()
	if planta is None or not planta.espacios:
		return 0.0, 0.0
	_x0, y0, x1, _y1 = planta.caja()
	return round(x1 + 1.0, 2), round(y0, 2)


def _campo_planta(contexto: Any, exteriores: bool | None = None, etiqueta: str = N_("Planta")) -> Campo:
	return c("planta", etiqueta, "opcion", opciones=plantas(contexto.entorno, exteriores), obligatorio=True, recarga=True)


def _campo_espacio(contexto: Any, clave: str = "espacio", etiqueta: str = N_("Espacio"), ayuda: str = "") -> Campo:
	entorno = contexto.entorno
	return c(clave, etiqueta, "opcion", ayuda, opciones=lambda v: espacios(entorno, v.get("planta")), obligatorio=True)


def _sin_planta(contexto: Any) -> str | None:
	if not contexto.entorno.plantas:
		return _("Primero añada una planta con Insertar, Planta.")
	return None


def _sin_espacios(contexto: Any) -> str | None:
	if not any(planta.espacios for planta in contexto.entorno.plantas):
		return _("Primero cree un espacio: Insertar, Habitación por medidas.")
	return None


def _sin_exterior(contexto: Any) -> str | None:
	if not plantas(contexto.entorno, True):
		return _("Hace falta un plano de calle. Añádalo con Insertar, Planta, marcando «Es un plano de calle».")
	return None


def _planta_exterior(contexto: Any) -> str:
	actual = contexto.planta_actual()
	if actual is not None and actual.exterior:
		return actual.id
	opciones = plantas(contexto.entorno, True)
	return opciones[0][0] if opciones else ""


def _opcional(valores: dict[str, Any], *claves: str) -> dict[str, Any]:
	"""Los valores no vacíos de esas claves, para pasarlos como argumentos opcionales."""
	return {clave: valores[clave] for clave in claves if valores.get(clave) not in (None, "")}


# Planta ----------------------------------------------------------------------


def _campos_planta(_contexto: Any) -> list[Campo]:
	return [
		c("nombre", N_("Nombre"), ayuda=N_("Por ejemplo «Planta baja» o «Calle». Vacío: el programa le pone uno.")),
		c("exterior", N_("Es un plano de calle"), "si_no", N_("Márquelo para calles, aceras, cruces y pasos de peatones.")),
		c("nivel", N_("Nivel"), "entero", N_("0 es la planta baja. Vacío: encima de la más alta."), minimo=-20, maximo=200),
		c("altura_m", N_("Altura del suelo (metros)"), "metros", N_("Vacío: 3 metros por nivel.")),
		c("descripcion", N_("Descripción"), "largo"),
	]


def _hacer_planta(contexto: Any, v: dict[str, Any]) -> Any:
	return edicion.crear_planta(
		contexto.entorno, v.get("nombre") or "", v.get("nivel"), v.get("altura_m"), bool(v.get("exterior")), v.get("descripcion") or ""
	)


# Habitaciones ----------------------------------------------------------------


def _campos_habitacion(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto),
		c("nombre", N_("Nombre"), obligatorio=True, ayuda=N_("Por ejemplo «Cocina».")),
		c("tipo", N_("Tipo de espacio"), "opcion", opciones=opciones_de(TIPOS_ESPACIO)),
		c("ancho", N_("Ancho, de oeste a este (metros)"), "metros", obligatorio=True, minimo=0.3, maximo=2000),
		c("fondo", N_("Fondo, de sur a norte (metros)"), "metros", obligatorio=True, minimo=0.3, maximo=2000),
		c(
			"x",
			N_("Esquina suroeste al este, x (metros)"),
			"metros",
			N_("Se propone un sitio libre al este de lo que ya hay."),
			obligatorio=True,
		),
		c("y", N_("Esquina suroeste al norte, y (metros)"), "metros", obligatorio=True),
		c("suelo", N_("Suelo"), "opcion", opciones=_con_habitual(SUELOS, N_("El habitual de ese tipo de espacio"))),
		c("descripcion", N_("Descripción"), "largo"),
	]


def _valores_habitacion(contexto: Any) -> dict[str, Any]:
	x, y = _sitio_libre(contexto)
	return {"planta": contexto.planta_id, "tipo": "habitacion", "ancho": 4.0, "fondo": 3.0, "x": x, "y": y, "suelo": SIN_VALOR}


def _hacer_habitacion(contexto: Any, v: dict[str, Any]) -> Any:
	return edicion.crear_habitacion_rectangular(
		contexto.entorno,
		_planta(contexto, v),
		v["nombre"],
		v["x"],
		v["y"],
		v["ancho"],
		v["fondo"],
		v.get("tipo") or "habitacion",
		**_opcional(v, "suelo", "descripcion"),
	)


def _campos_adosada(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto),
		_campo_espacio(contexto, "junto_a", N_("Junto a"), N_("El espacio al que se pega la habitación nueva.")),
		c(
			"lado",
			N_("Lado de ese espacio"),
			"opcion",
			N_("Por qué lado se adosa: quedarán compartiendo esa pared."),
			opciones=_traducidas(LADOS),
		),
		c("nombre", N_("Nombre de la habitación nueva"), obligatorio=True),
		c("tipo", N_("Tipo de espacio"), "opcion", opciones=opciones_de(TIPOS_ESPACIO)),
		c("ancho", N_("Ancho, de oeste a este (metros)"), "metros", obligatorio=True, minimo=0.3, maximo=2000),
		c("fondo", N_("Fondo, de sur a norte (metros)"), "metros", obligatorio=True, minimo=0.3, maximo=2000),
		c("alineacion", N_("Colocación a lo largo de la pared"), "opcion", opciones=_traducidas(ALINEACIONES)),
		c(
			"desplazamiento",
			N_("O distancia desde el extremo oeste o sur (metros)"),
			"metros",
			N_("Si se escribe, manda sobre la colocación anterior: metros desde el extremo oeste o sur del otro espacio."),
		),
		c("con_puerta", N_("Abrir una puerta en la pared compartida"), "si_no"),
		c("descripcion", N_("Descripción"), "largo"),
	]


def _valores_adosada(contexto: Any) -> dict[str, Any]:
	id_planta, id_espacio = _espacio_actual(contexto)
	return {
		"planta": id_planta,
		"junto_a": id_espacio,
		"lado": "este",
		"tipo": "habitacion",
		"ancho": 4.0,
		"fondo": 3.0,
		"alineacion": "inicio",
		"con_puerta": True,
	}


def _hacer_adosada(contexto: Any, v: dict[str, Any]) -> Any:
	planta, junto_a = _espacio(contexto, v, "junto_a")
	nueva = edicion.crear_habitacion_adosada(
		contexto.entorno,
		planta,
		v["nombre"],
		junto_a,
		v["lado"],
		v["ancho"],
		v["fondo"],
		v.get("alineacion") or "inicio",
		v.get("desplazamiento"),
		v.get("tipo") or "habitacion",
		**_opcional(v, "descripcion"),
	)
	if v.get("con_puerta"):
		edicion.anadir_puerta_entre(contexto.entorno, planta, junto_a, nueva)
	return nueva


_AYUDA_PUNTOS = N_(
	"Escriba cada punto con su x y su y, en metros, separadas por un espacio, y separe los puntos con punto y coma. Por ejemplo: 0 0; 4 0; 4 3; 0 3."
)


def _campos_poligonal(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto),
		c("nombre", N_("Nombre"), obligatorio=True),
		c("tipo", N_("Tipo de espacio"), "opcion", opciones=opciones_de(TIPOS_ESPACIO)),
		c("contorno", N_("Esquinas"), "largo", _AYUDA_PUNTOS, obligatorio=True),
		c("descripcion", N_("Descripción"), "largo"),
	]


def _hacer_poligonal(contexto: Any, v: dict[str, Any]) -> Any:
	contorno = operaciones.puntos_de_texto(v["contorno"], minimo=3)
	return edicion.crear_espacio_poligonal(
		contexto.entorno, _planta(contexto, v), v["nombre"], contorno, v.get("tipo") or "habitacion", **_opcional(v, "descripcion")
	)


# Aberturas y paredes ---------------------------------------------------------


def _campos_abertura(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto),
		_campo_espacio(contexto, ayuda=N_("El espacio en una de cuyas paredes se abre.")),
		c("lado", N_("Pared"), "opcion", N_("En qué pared del espacio."), opciones=_traducidas(LADOS)),
		c("tipo", N_("Qué se abre"), "opcion", opciones=opciones_de(TIPOS_ABERTURA), recarga=True),
		c("ancho", N_("Ancho (metros)"), "metros", obligatorio=True, minimo=0.3, maximo=20),
		c("centrada", N_("Centrada en la pared"), "si_no", recarga=True),
		c(
			"desplazamiento",
			N_("Distancia desde la esquina oeste o sur (metros)"),
			"metros",
			N_("Metros desde el extremo oeste (paredes norte y sur) o sur (paredes este y oeste) hasta el borde de la puerta."),
			obligatorio=True,
			minimo=0,
			si=lambda v: not v.get("centrada"),
		),
		c("estado", N_("Estado"), "opcion", opciones=opciones_de(ESTADOS_ABERTURA), si=lambda v: v.get("tipo") in ("puerta", "portal")),
		c("hoja", N_("Hoja"), "opcion", opciones=opciones_de(HOJAS), si=lambda v: v.get("tipo") in ("puerta", "portal")),
		c("nombre", N_("Nombre"), ayuda=N_("Vacío: se compone con los espacios que une, como «Puerta entre Cocina y Pasillo».")),
		c("es_salida", N_("Cuenta como salida del edificio"), "si_no"),
	]


def _valores_abertura(contexto: Any) -> dict[str, Any]:
	id_planta, id_espacio = _espacio_actual(contexto)
	return {
		"planta": id_planta,
		"espacio": id_espacio,
		"lado": "norte",
		"tipo": "puerta",
		"ancho": edicion.ANCHO_PUERTA,
		"centrada": True,
		"estado": "cerrada",
		"hoja": "batiente",
	}


def _hacer_abertura(contexto: Any, v: dict[str, Any]) -> Any:
	planta, espacio = _espacio(contexto, v)
	return edicion.anadir_puerta(
		contexto.entorno,
		planta,
		espacio,
		v["lado"],
		None if v.get("centrada") else v.get("desplazamiento"),
		v["ancho"],
		v.get("tipo") or "puerta",
		v.get("estado") or None,
		v.get("hoja") or None,
		v.get("nombre") or "",
		es_salida=bool(v.get("es_salida")),
	)


def _campos_pared(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto),
		c("nombre", N_("Nombre"), ayuda=N_("Por ejemplo «Valla del patio».")),
		c("ax", N_("Primer extremo al este, x (metros)"), "metros", obligatorio=True),
		c("ay", N_("Primer extremo al norte, y (metros)"), "metros", obligatorio=True),
		c("bx", N_("Segundo extremo al este, x (metros)"), "metros", obligatorio=True),
		c("by", N_("Segundo extremo al norte, y (metros)"), "metros", obligatorio=True),
		c("grosor", N_("Grosor (metros)"), "metros", obligatorio=True, minimo=0.01, maximo=5),
		c("altura", N_("Altura (metros)"), "metros", obligatorio=True, minimo=0.1, maximo=50),
		c("material", N_("Material"), "opcion", opciones=opciones_de(MATERIALES_PARED)),
		c("bloquea_paso", N_("Corta el paso"), "si_no"),
		c("bloquea_sonido", N_("Corta el sonido"), "si_no", N_("Desmárquelo en una valla o un cristal.")),
	]


def _hacer_pared(contexto: Any, v: dict[str, Any]) -> Any:
	return edicion.anadir_pared(
		contexto.entorno,
		_planta(contexto, v),
		(v["ax"], v["ay"]),
		(v["bx"], v["by"]),
		v.get("nombre") or "",
		v["grosor"],
		v.get("material") or "ladrillo",
		bool(v.get("bloquea_paso")),
		bool(v.get("bloquea_sonido")),
		v["altura"],
	)


# Conectores ------------------------------------------------------------------


def _dos_plantas(contexto: Any) -> str | None:
	if len(contexto.entorno.plantas) < 2:
		return _("Hacen falta al menos dos plantas. Añada otra con Insertar, Planta.")
	return None


def _campos_escalera(contexto: Any, rampa: bool = False) -> list[Campo]:
	todas = plantas(contexto.entorno)
	campos = [
		c("planta_abajo", N_("Planta de abajo"), "opcion", opciones=todas, obligatorio=True),
		c("planta_arriba", N_("Planta de arriba"), "opcion", opciones=todas, obligatorio=True),
		c(
			"x",
			N_("Boca de abajo al este, x (metros)"),
			"metros",
			N_("El punto de la planta de abajo donde se empieza a subir."),
			obligatorio=True,
		),
		c("y", N_("Boca de abajo al norte, y (metros)"), "metros", obligatorio=True),
		c("rumbo", N_("Hacia dónde se sube"), "opcion", opciones=_traducidas(RUMBOS)),
		c(
			"longitud",
			N_("Longitud en planta (metros)"),
			"metros",
			N_("Arriba se sale esos metros más allá, en la misma dirección."),
			obligatorio=True,
			minimo=0.5,
			maximo=200,
		),
	]
	if not rampa:
		campos.append(c("peldanos", N_("Peldaños"), "entero", obligatorio=True, minimo=1, maximo=500))
	campos += [
		c("ancho", N_("Anchura (metros)"), "metros", obligatorio=True, minimo=0.4, maximo=20),
		c("pasamanos", N_("Pasamanos"), "opcion", opciones=opciones_de(PASAMANOS)),
		c("nombre", N_("Nombre")),
	]
	return campos


def _valores_escalera(contexto: Any) -> dict[str, Any]:
	ordenadas = sorted(contexto.entorno.plantas, key=lambda p: p.nivel)
	actual = contexto.planta_actual() or ordenadas[0]
	indice = min(ordenadas.index(actual), len(ordenadas) - 2) if actual in ordenadas and len(ordenadas) >= 2 else 0
	x, y = _punto_actual(contexto)
	return {
		"planta_abajo": ordenadas[indice].id,
		"planta_arriba": ordenadas[min(indice + 1, len(ordenadas) - 1)].id,
		"x": x,
		"y": y,
		"rumbo": 0.0,
		"longitud": 4.0,
		"peldanos": 16,
		"ancho": 1.0,
		"pasamanos": "ambos",
	}


def _hacer_escalera(contexto: Any, v: dict[str, Any]) -> Any:
	return edicion.crear_escalera(
		contexto.entorno,
		_planta(contexto, v, "planta_abajo"),
		_planta(contexto, v, "planta_arriba"),
		(v["x"], v["y"]),
		float(v.get("rumbo") or 0.0),
		v["longitud"],
		int(v["peldanos"]),
		v.get("nombre") or "",
		v["ancho"],
		v.get("pasamanos") or "ambos",
	)


def _hacer_rampa(contexto: Any, v: dict[str, Any]) -> Any:
	return edicion.crear_rampa(
		contexto.entorno,
		_planta(contexto, v, "planta_abajo"),
		_planta(contexto, v, "planta_arriba"),
		(v["x"], v["y"]),
		float(v.get("rumbo") or 0.0),
		v["longitud"],
		v.get("nombre") or "",
		v["ancho"],
		v.get("pasamanos") or "ambos",
	)


def _campos_ascensor(contexto: Any) -> list[Campo]:
	return [
		c("plantas", N_("Plantas en las que para"), "casillas", opciones=plantas(contexto.entorno)),
		c(
			"x",
			N_("Delante de la puerta al este, x (metros)"),
			"metros",
			N_("El mismo punto en todas las plantas: el hueco es vertical."),
			obligatorio=True,
		),
		c("y", N_("Delante de la puerta al norte, y (metros)"), "metros", obligatorio=True),
		c("rumbo", N_("Hacia dónde se mira para entrar"), "opcion", opciones=_traducidas(RUMBOS)),
		c("aviso_hablado", N_("Dice la planta al llegar"), "si_no"),
		c("nombre", N_("Nombre")),
	]


def _valores_ascensor(contexto: Any) -> dict[str, Any]:
	x, y = _punto_actual(contexto)
	return {
		"plantas": [planta.id for planta in contexto.entorno.plantas if not planta.exterior],
		"x": x,
		"y": y,
		"rumbo": 0.0,
		"aviso_hablado": True,
	}


def _hacer_ascensor(contexto: Any, v: dict[str, Any]) -> Any:
	elegidas = [planta for planta in contexto.entorno.plantas if planta.id in (v.get("plantas") or [])]
	if len(elegidas) < 2:
		raise ErrorEdicion(_("Marque al menos dos plantas."))
	return edicion.crear_ascensor(
		contexto.entorno, elegidas, (v["x"], v["y"]), float(v.get("rumbo") or 0.0), v.get("nombre") or "", bool(v.get("aviso_hablado"))
	)


# Sonidos, referencias y zonas ------------------------------------------------


def _valores_en_punto(contexto: Any) -> dict[str, Any]:
	x, y = _punto_actual(contexto)
	return {"planta": contexto.planta_id, "x": x, "y": y}


def _campo_sonido() -> Campo:
	"""El sonido de una fuente: una lista con los de serie o, si no hay catálogo de sonidos, su nombre escrito."""
	lista = sonidos()
	if lista:
		return c("sonido", N_("Sonido"), "opcion", N_("El sonido que emite."), opciones=lista, obligatorio=True)
	return c("sonido", N_("Sonido"), ayuda=N_("Nombre del sonido, por ejemplo «fuente/frigorifico»."), obligatorio=True)


def _campos_fuente(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto),
		c("nombre", N_("Nombre"), obligatorio=True, ayuda=N_("Por ejemplo «Frigorífico» o «Reloj de pared».")),
		_campo_sonido(),
		c(
			"x",
			N_("Posición al este, x (metros)"),
			"metros",
			N_("Se propone el centro del espacio en el que está trabajando."),
			obligatorio=True,
		),
		c("y", N_("Posición al norte, y (metros)"), "metros", obligatorio=True),
		c("volumen", N_("Volumen"), "deslizador", minimo=0, maximo=100, extra={"unidad": N_("por ciento"), "paso": 5}),
		c("radio", N_("Distancia a la que se oye (metros)"), "metros", obligatorio=True, minimo=0.5, maximo=500),
		c("bucle", N_("Suena sin parar"), "si_no"),
		c("descripcion", N_("Descripción"), "largo"),
	]


def _valores_fuente(contexto: Any) -> dict[str, Any]:
	valores = _valores_en_punto(contexto)
	lista = sonidos()
	valores.update(volumen=100, radio=12.0, bucle=True, sonido=lista[0][0] if lista else "")
	return valores


def _hacer_fuente(contexto: Any, v: dict[str, Any]) -> Any:
	return edicion.anadir_fuente(
		contexto.entorno,
		_planta(contexto, v),
		v["nombre"],
		v["x"],
		v["y"],
		str(v.get("sonido") or ""),
		float(v.get("volumen", 100)) / 100.0,
		v["radio"],
		bool(v.get("bucle")),
		descripcion=v.get("descripcion") or "",
	)


def _campos_referencia(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto),
		c("nombre", N_("Nombre"), obligatorio=True),
		c("tipo", N_("Tipo de referencia"), "opcion", opciones=opciones_de(TIPOS_REFERENCIA)),
		c("x", N_("Posición al este, x (metros)"), "metros", obligatorio=True),
		c("y", N_("Posición al norte, y (metros)"), "metros", obligatorio=True),
		c("permanente", N_("Es permanente"), "si_no"),
		c("descripcion", N_("Descripción"), "largo"),
	]


def _hacer_referencia(contexto: Any, v: dict[str, Any]) -> Any:
	return edicion.anadir_referencia(
		contexto.entorno,
		_planta(contexto, v),
		v["nombre"],
		v["x"],
		v["y"],
		v.get("tipo") or "punto",
		v.get("descripcion") or "",
		bool(v.get("permanente")),
	)


def _campos_zona(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto),
		c("nombre", N_("Nombre"), obligatorio=True, ayuda=N_("Por ejemplo «Alfombra del salón».")),
		c("suelo", N_("Suelo"), "opcion", opciones=opciones_de(SUELOS)),
		c("x", N_("Esquina suroeste al este, x (metros)"), "metros", obligatorio=True),
		c("y", N_("Esquina suroeste al norte, y (metros)"), "metros", obligatorio=True),
		c("ancho", N_("Ancho, de oeste a este (metros)"), "metros", obligatorio=True, minimo=0.05, maximo=2000),
		c("fondo", N_("Fondo, de sur a norte (metros)"), "metros", obligatorio=True, minimo=0.05, maximo=2000),
	]


def _hacer_zona(contexto: Any, v: dict[str, Any]) -> Any:
	contorno = geo.rectangulo(float(v["x"]), float(v["y"]), float(v["ancho"]), float(v["fondo"]))
	return edicion.anadir_zona_suelo(contexto.entorno, _planta(contexto, v), v["nombre"], contorno, v.get("suelo") or "alfombra")


# Exteriores ------------------------------------------------------------------


def _campos_calle(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto, True, N_("Plano de calle")),
		c("nombre", N_("Nombre"), obligatorio=True, ayuda=N_("Por ejemplo «Calle Mayor».")),
		c("eje", N_("Puntos del eje"), "largo", _AYUDA_PUNTOS, obligatorio=True),
		c("ancho_calzada", N_("Ancho de la calzada (metros)"), "metros", obligatorio=True, minimo=1, maximo=100),
		c(
			"ancho_acera",
			N_("Ancho de cada acera (metros)"),
			"metros",
			N_("Con 0 no se crean aceras."),
			obligatorio=True,
			minimo=0,
			maximo=50,
		),
		c("carriles", N_("Carriles"), "entero", obligatorio=True, minimo=1, maximo=12),
		c("sentido", N_("Sentido"), "opcion", opciones=opciones_de(SENTIDOS_VIA)),
		c("trafico", N_("Tráfico"), "opcion", opciones=opciones_de(NIVELES_TRAFICO)),
		c("velocidad_kmh", N_("Velocidad de los coches (kilómetros por hora)"), "decimal", obligatorio=True, minimo=5, maximo=130),
	]


def _valores_calle(contexto: Any) -> dict[str, Any]:
	return {
		"planta": _planta_exterior(contexto),
		"eje": "-30 0; 30 0",
		"ancho_calzada": 6.0,
		"ancho_acera": 2.0,
		"carriles": 2,
		"sentido": "doble",
		"trafico": 1,
		"velocidad_kmh": 30.0,
	}


def _hacer_calle(contexto: Any, v: dict[str, Any]) -> Any:
	calle = edicion.crear_calle(
		contexto.entorno,
		_planta(contexto, v),
		v["nombre"],
		operaciones.puntos_de_texto(v["eje"]),
		v["ancho_calzada"],
		v["ancho_acera"],
		int(v["carriles"]),
		v.get("sentido") or "doble",
		int(v.get("trafico") or 0),
		v["velocidad_kmh"],
	)
	return calle.via


def _dos_calles(contexto: Any) -> str | None:
	if not any(len(planta.vias) >= 2 for planta in contexto.entorno.plantas):
		return _("Hacen falta dos calles en el mismo plano. Créelas con Insertar, Exteriores, Calle con aceras.")
	return None


def _una_calle(contexto: Any) -> str | None:
	if not any(planta.vias for planta in contexto.entorno.plantas):
		return _("Primero cree una calle con Insertar, Exteriores, Calle con aceras.")
	return None


def _planta_con_vias(contexto: Any, minimo: int = 1) -> str:
	actual = contexto.planta_actual()
	if actual is not None and len(actual.vias) >= minimo:
		return actual.id
	return next((planta.id for planta in contexto.entorno.plantas if len(planta.vias) >= minimo), "")


def _campos_cruce(contexto: Any) -> list[Campo]:
	entorno = contexto.entorno
	return [
		_campo_planta(contexto, True, N_("Plano de calle")),
		c("calle_a", N_("Primera calle"), "opcion", opciones=lambda v: vias(entorno, v.get("planta")), obligatorio=True),
		c("calle_b", N_("Segunda calle"), "opcion", opciones=lambda v: vias(entorno, v.get("planta")), obligatorio=True),
		c("nombre", N_("Nombre"), ayuda=N_("Vacío: «Cruce de» las dos calles.")),
	]


def _valores_cruce(contexto: Any) -> dict[str, Any]:
	id_planta = _planta_con_vias(contexto, 2)
	lista = vias(contexto.entorno, id_planta)
	return {"planta": id_planta, "calle_a": lista[0][0] if lista else "", "calle_b": lista[1][0] if len(lista) > 1 else ""}


def _hacer_cruce(contexto: Any, v: dict[str, Any]) -> Any:
	planta, calle_a = _via(contexto, v, "calle_a")
	_planta_b, calle_b = _via(contexto, v, "calle_b")
	if calle_a is calle_b:
		raise ErrorEdicion(_("Elija dos calles distintas."))
	return edicion.crear_cruce(contexto.entorno, planta, calle_a, calle_b, v.get("nombre") or "")


def _campos_paso(contexto: Any) -> list[Campo]:
	entorno = contexto.entorno
	return [
		_campo_planta(contexto, True, N_("Plano de calle")),
		c("via", N_("Calle que cruza"), "opcion", opciones=lambda v: vias(entorno, v.get("planta")), obligatorio=True),
		c(
			"x",
			N_("Punto del cruce al este, x (metros)"),
			"metros",
			N_("Un punto cercano: el paso se ajusta solo al eje de la calle."),
			obligatorio=True,
		),
		c("y", N_("Punto del cruce al norte, y (metros)"), "metros", obligatorio=True),
		c("ancho", N_("Ancho del paso (metros)"), "metros", obligatorio=True, minimo=1, maximo=30),
		c("semaforo", N_("Tiene semáforo"), "si_no", recarga=True),
		c("sonoro", N_("El semáforo es sonoro"), "si_no", si=lambda v: bool(v.get("semaforo"))),
		c("pulsador", N_("Tiene pulsador"), "si_no", si=lambda v: bool(v.get("semaforo"))),
		c("isleta", N_("Tiene isleta en medio"), "si_no"),
		c("tactil", N_("Poner pavimento táctil a cada lado"), "si_no"),
		c("nombre", N_("Nombre")),
	]


def _valores_paso(contexto: Any) -> dict[str, Any]:
	id_planta = _planta_con_vias(contexto)
	lista = vias(contexto.entorno, id_planta)
	return {"planta": id_planta, "via": lista[0][0] if lista else "", "x": 0.0, "y": 0.0, "ancho": 4.0, "tactil": True}


def _hacer_paso(contexto: Any, v: dict[str, Any]) -> Any:
	planta, via = _via(contexto, v)
	semaforo = bool(v.get("semaforo"))
	return edicion.crear_paso_peatones(
		contexto.entorno,
		planta,
		via,
		(v["x"], v["y"]),
		semaforo,
		semaforo and bool(v.get("sonoro")),
		semaforo and bool(v.get("pulsador")),
		bool(v.get("isleta")),
		v["ancho"],
		v.get("nombre") or "",
		tactil=bool(v.get("tactil")),
	)


def _campos_edificio(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto, True, N_("Plano de calle")),
		c("nombre", N_("Nombre"), obligatorio=True, ayuda=N_("Por ejemplo «Farmacia» o «Número 12».")),
		c("x", N_("Esquina suroeste al este, x (metros)"), "metros", obligatorio=True),
		c("y", N_("Esquina suroeste al norte, y (metros)"), "metros", obligatorio=True),
		c("ancho", N_("Ancho, de oeste a este (metros)"), "metros", obligatorio=True, minimo=1, maximo=2000),
		c("fondo", N_("Fondo, de sur a norte (metros)"), "metros", obligatorio=True, minimo=1, maximo=2000),
		c("portal_lado", N_("Fachada del portal"), "opcion", opciones=[(SIN_VALOR, _("Sin portal"))] + _traducidas(LADOS)),
		c(
			"portal_desplazamiento",
			N_("Portal: distancia desde la esquina oeste o sur (metros)"),
			"metros",
			N_("Vacío: centrado en la fachada."),
			minimo=0,
		),
		c("portal_nombre", N_("Nombre del portal")),
		c("descripcion", N_("Descripción"), "largo"),
	]


def _hacer_edificio(contexto: Any, v: dict[str, Any]) -> Any:
	edificio, _portal = edicion.crear_edificio(
		contexto.entorno,
		_planta(contexto, v),
		v["nombre"],
		v["x"],
		v["y"],
		v["ancho"],
		v["fondo"],
		v.get("portal_lado") or None,
		v.get("portal_desplazamiento"),
		portal_nombre=v.get("portal_nombre") or "",
		descripcion=v.get("descripcion") or "",
	)
	return edificio


def _campos_manzana(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto, True, N_("Plano de calle")),
		c("nombre", N_("Nombre"), obligatorio=True),
		c("contorno", N_("Esquinas"), "largo", _AYUDA_PUNTOS, obligatorio=True),
		c("descripcion", N_("Descripción"), "largo"),
	]


def _hacer_manzana(contexto: Any, v: dict[str, Any]) -> Any:
	return edicion.crear_manzana(
		contexto.entorno,
		_planta(contexto, v),
		v["nombre"],
		operaciones.puntos_de_texto(v["contorno"], minimo=3),
		v.get("descripcion") or "",
	)


def _campos_parada(contexto: Any) -> list[Campo]:
	return [
		_campo_planta(contexto, True, N_("Plano de calle")),
		c("nombre", N_("Nombre"), obligatorio=True, ayuda=N_("Por ejemplo «Parada de la línea 3».")),
		c("x", N_("Posición al este, x (metros)"), "metros", obligatorio=True),
		c("y", N_("Posición al norte, y (metros)"), "metros", obligatorio=True),
		c("descripcion", N_("Descripción"), "largo"),
	]


def _hacer_parada(contexto: Any, v: dict[str, Any]) -> Any:
	return edicion.crear_parada(contexto.entorno, _planta(contexto, v), v["nombre"], v["x"], v["y"], v.get("descripcion") or "")


def _valores_exterior(contexto: Any) -> dict[str, Any]:
	return {"planta": _planta_exterior(contexto), "x": 0.0, "y": 0.0, "ancho": 12.0, "fondo": 10.0, "portal_lado": "sur"}


# Editar: mover, girar y cambiar medidas -------------------------------------


def _seleccion(contexto: Any) -> Any:
	elegido = contexto.elemento_seleccionado()
	if elegido is None:
		raise ErrorEdicion(_("No hay ningún elemento seleccionado."))
	return elegido[1]


def _sin_seleccion(contexto: Any) -> str | None:
	if contexto.elemento_seleccionado() is None:
		return _("Seleccione antes un elemento en el árbol, en la lista o en el plano.")
	return None


def _campos_mover(_contexto: Any) -> list[Campo]:
	return [
		c(
			"modo",
			N_("Cómo moverlo"),
			"opcion",
			opciones=[("desplazar", _("Desplazarlo unos metros")), ("llevar", _("Llevar su centro a un punto"))],
			recarga=True,
		),
		c(
			"dx",
			N_("Metros hacia el este"),
			"metros",
			N_("Negativo: hacia el oeste."),
			obligatorio=True,
			si=lambda v: v.get("modo") != "llevar",
		),
		c(
			"dy",
			N_("Metros hacia el norte"),
			"metros",
			N_("Negativo: hacia el sur."),
			obligatorio=True,
			si=lambda v: v.get("modo") != "llevar",
		),
		c("x", N_("Centro al este, x (metros)"), "metros", obligatorio=True, si=lambda v: v.get("modo") == "llevar"),
		c("y", N_("Centro al norte, y (metros)"), "metros", obligatorio=True, si=lambda v: v.get("modo") == "llevar"),
		c("con_contenido", N_("Llevarse lo que contiene"), "si_no", N_("Una habitación se lleva sus puertas, sus objetos y sus sonidos.")),
	]


def _valores_mover(contexto: Any) -> dict[str, Any]:
	elemento = _seleccion(contexto)
	try:
		x, y = edicion.centro_de(elemento)
	except ValueError, TypeError, ZeroDivisionError:
		x, y = 0.0, 0.0
	return {"modo": "desplazar", "dx": 0.0, "dy": 0.0, "x": round(x, 2), "y": round(y, 2), "con_contenido": True}


def _hacer_mover(contexto: Any, v: dict[str, Any]) -> Any:
	elemento = _seleccion(contexto)
	if v.get("modo") == "llevar":
		edicion.mover_a(contexto.entorno, elemento, v["x"], v["y"], bool(v.get("con_contenido")))
	else:
		edicion.mover(contexto.entorno, elemento, v["dx"], v["dy"], bool(v.get("con_contenido")))
	return elemento


def _campos_girar(_contexto: Any) -> list[Campo]:
	return [
		c(
			"grados",
			N_("Grados, en el sentido del reloj"),
			"decimal",
			N_("90 es un cuarto de vuelta a la derecha; -90, a la izquierda."),
			obligatorio=True,
			minimo=-360,
			maximo=360,
		),
		c("con_contenido", N_("Girar también lo que contiene"), "si_no"),
	]


def _hacer_girar(contexto: Any, v: dict[str, Any]) -> Any:
	elemento = _seleccion(contexto)
	edicion.girar(contexto.entorno, elemento, v["grados"], con_contenido=bool(v.get("con_contenido")))
	return elemento


def _campos_medidas(contexto: Any) -> list[Campo]:
	elemento = _seleccion(contexto)
	campos: list[Campo] = []
	if isinstance(elemento, Pared):
		campos.append(c("ancho", N_("Longitud (metros)"), "metros", obligatorio=True, minimo=0.05, maximo=2000))
		campos.append(c("alto", N_("Altura (metros)"), "metros", obligatorio=True, minimo=0.1, maximo=50))
	elif isinstance(elemento, (Abertura, Via)):
		campos.append(c("ancho", N_("Ancho (metros)"), "metros", obligatorio=True, minimo=0.3, maximo=100))
	else:
		campos.append(c("ancho", N_("Ancho, de oeste a este (metros)"), "metros", obligatorio=True, minimo=0.01, maximo=2000))
		campos.append(c("fondo", N_("Fondo, de sur a norte (metros)"), "metros", obligatorio=True, minimo=0.01, maximo=2000))
		if isinstance(elemento, Objeto):
			campos.append(c("alto", N_("Alto (metros)"), "metros", obligatorio=True, minimo=0.01, maximo=100))
	return campos


def _valores_medidas(contexto: Any) -> dict[str, Any]:
	elemento = _seleccion(contexto)
	if isinstance(elemento, Pared):
		return {"ancho": round(geo.distancia(elemento.a, elemento.b), 3), "alto": elemento.altura}
	if isinstance(elemento, (Abertura, Via)):
		return {"ancho": round(elemento.ancho, 3)}
	if isinstance(elemento, Objeto):
		return {"ancho": elemento.ancho, "fondo": elemento.fondo, "alto": elemento.alto}
	x0, y0, x1, y1 = geo.caja(elemento.contorno)
	return {"ancho": round(x1 - x0, 3), "fondo": round(y1 - y0, 3)}


def _con_medidas(contexto: Any) -> str | None:
	falta = _sin_seleccion(contexto)
	if falta:
		return falta
	elemento = _seleccion(contexto)
	if not isinstance(elemento, (Espacio, ZonaSuelo, Objeto, Abertura, Pared, Via)):
		return _("A este elemento no se le pueden cambiar las medidas.")
	return None


def _movible(contexto: Any) -> str | None:
	falta = _sin_seleccion(contexto)
	if falta:
		return falta
	if isinstance(_seleccion(contexto), Conector):
		return _("Una escalera, una rampa o un ascensor no se mueven: bórrelo y créelo en su sitio nuevo.")
	return None


def _hacer_medidas(contexto: Any, v: dict[str, Any]) -> Any:
	elemento = _seleccion(contexto)
	edicion.redimensionar(contexto.entorno, elemento, v.get("ancho"), v.get("fondo"), v.get("alto"), contexto.catalogo)
	return elemento


def _nombre_seleccion(contexto_o_valores: Any) -> str:
	return str(contexto_o_valores.get("_nombre", "")) if isinstance(contexto_o_valores, dict) else ""


ORDENES: dict[str, Orden] = {
	"insertar_planta": Orden(
		N_("Insertar una planta"),
		_campos_planta,
		_hacer_planta,
		lambda v: _("crear la planta {nombre}").format(nombre=v.get("nombre") or "").strip(),
	),
	"insertar_habitacion": Orden(
		N_("Insertar una habitación por medidas"),
		_campos_habitacion,
		_hacer_habitacion,
		lambda v: _("crear {nombre}").format(nombre=v["nombre"]),
		_valores_habitacion,
		_sin_planta,
	),
	"insertar_adosada": Orden(
		N_("Insertar una habitación adosada a otra"),
		_campos_adosada,
		_hacer_adosada,
		lambda v: _("crear {nombre}").format(nombre=v["nombre"]),
		_valores_adosada,
		_sin_espacios,
	),
	"insertar_poligonal": Orden(
		N_("Insertar un espacio poligonal"),
		_campos_poligonal,
		_hacer_poligonal,
		lambda v: _("crear {nombre}").format(nombre=v["nombre"]),
		lambda contexto: {"planta": contexto.planta_id, "tipo": "habitacion"},
		_sin_planta,
	),
	"insertar_abertura": Orden(
		N_("Insertar una puerta, un hueco, una ventana o un portal"),
		_campos_abertura,
		_hacer_abertura,
		lambda v: _("abrir {nombre}").format(nombre=v.get("nombre") or _("una puerta")),
		_valores_abertura,
		_sin_espacios,
	),
	"insertar_pared": Orden(
		N_("Insertar una pared suelta"),
		_campos_pared,
		_hacer_pared,
		lambda v: _("añadir la pared {nombre}").format(nombre=v.get("nombre") or "").strip(),
		lambda contexto: {
			"planta": contexto.planta_id,
			"grosor": 0.1,
			"altura": 2.5,
			"material": "ladrillo",
			"bloquea_paso": True,
			"bloquea_sonido": True,
		},
		_sin_planta,
	),
	"insertar_escalera": Orden(
		N_("Insertar una escalera"),
		_campos_escalera,
		_hacer_escalera,
		lambda v: _("crear la escalera {nombre}").format(nombre=v.get("nombre") or "").strip(),
		_valores_escalera,
		_dos_plantas,
	),
	"insertar_rampa": Orden(
		N_("Insertar una rampa"),
		lambda contexto: _campos_escalera(contexto, rampa=True),
		_hacer_rampa,
		lambda v: _("crear la rampa {nombre}").format(nombre=v.get("nombre") or "").strip(),
		lambda contexto: {**_valores_escalera(contexto), "longitud": 8.0, "ancho": 1.2},
		_dos_plantas,
	),
	"insertar_ascensor": Orden(
		N_("Insertar un ascensor"),
		_campos_ascensor,
		_hacer_ascensor,
		lambda v: _("crear el ascensor {nombre}").format(nombre=v.get("nombre") or "").strip(),
		_valores_ascensor,
		_dos_plantas,
	),
	"insertar_fuente": Orden(
		N_("Insertar una fuente de sonido"),
		_campos_fuente,
		_hacer_fuente,
		lambda v: _("añadir el sonido {nombre}").format(nombre=v["nombre"]),
		_valores_fuente,
		_sin_planta,
	),
	"insertar_referencia": Orden(
		N_("Insertar una referencia"),
		_campos_referencia,
		_hacer_referencia,
		lambda v: _("añadir la referencia {nombre}").format(nombre=v["nombre"]),
		lambda contexto: {**_valores_en_punto(contexto), "tipo": "punto", "permanente": True},
		_sin_planta,
	),
	"insertar_zona": Orden(
		N_("Insertar una zona de suelo"),
		_campos_zona,
		_hacer_zona,
		lambda v: _("añadir la zona {nombre}").format(nombre=v["nombre"]),
		lambda contexto: {**_valores_en_punto(contexto), "suelo": "alfombra", "ancho": 2.0, "fondo": 1.5},
		_sin_planta,
	),
	"insertar_calle": Orden(
		N_("Insertar una calle con aceras"),
		_campos_calle,
		_hacer_calle,
		lambda v: _("crear {nombre}").format(nombre=v["nombre"]),
		_valores_calle,
		_sin_exterior,
	),
	"insertar_cruce": Orden(
		N_("Insertar un cruce"),
		_campos_cruce,
		_hacer_cruce,
		lambda v: _("crear el cruce {nombre}").format(nombre=v.get("nombre") or "").strip(),
		_valores_cruce,
		_dos_calles,
	),
	"insertar_paso": Orden(
		N_("Insertar un paso de peatones"),
		_campos_paso,
		_hacer_paso,
		lambda v: _("crear el paso de peatones {nombre}").format(nombre=v.get("nombre") or "").strip(),
		_valores_paso,
		_una_calle,
	),
	"insertar_edificio": Orden(
		N_("Insertar un edificio con portal"),
		_campos_edificio,
		_hacer_edificio,
		lambda v: _("crear el edificio {nombre}").format(nombre=v["nombre"]),
		_valores_exterior,
		_sin_exterior,
	),
	"insertar_manzana": Orden(
		N_("Insertar una manzana"),
		_campos_manzana,
		_hacer_manzana,
		lambda v: _("crear la manzana {nombre}").format(nombre=v["nombre"]),
		lambda contexto: {"planta": _planta_exterior(contexto)},
		_sin_exterior,
	),
	"insertar_parada": Orden(
		N_("Insertar una parada"),
		_campos_parada,
		_hacer_parada,
		lambda v: _("marcar la parada {nombre}").format(nombre=v["nombre"]),
		lambda contexto: {"planta": _planta_exterior(contexto), "x": 0.0, "y": 0.0},
		_sin_exterior,
	),
	"mover": Orden(
		N_("Mover"),
		_campos_mover,
		_hacer_mover,
		lambda v: _("mover {nombre}").format(nombre=_nombre_seleccion(v)),
		_valores_mover,
		_movible,
	),
	"girar": Orden(
		N_("Girar"),
		_campos_girar,
		_hacer_girar,
		lambda v: _("girar {nombre}").format(nombre=_nombre_seleccion(v)),
		lambda _contexto: {"grados": 90.0, "con_contenido": True},
		_movible,
	),
	"medidas": Orden(
		N_("Cambiar medidas"),
		_campos_medidas,
		_hacer_medidas,
		lambda v: _("cambiar las medidas de {nombre}").format(nombre=_nombre_seleccion(v)),
		_valores_medidas,
		_con_medidas,
	),
}
