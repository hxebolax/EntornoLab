"""Diálogos de las órdenes de «Insertar» y «Editar» de la ventana principal.

Casi todos son el mismo diálogo: un formulario generado del esquema de la
orden (``app/ui/esquemas_elementos.ORDENES``). Al aceptar, el cambio se hace
con ``contexto.ejecutar``, que lo apunta en el historial con su nombre; si
lo pedido no se puede hacer (``ErrorEdicion``: «no cabe», «pisa a otra
habitación»), el mensaje se enseña y el formulario sigue abierto para
corregirlo, con el entorno intacto.

Cada función devuelve el id del elemento creado o cambiado (o ``None`` si
se canceló), lo deja seleccionado y lo anuncia en una frase.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.i18n import N_, _, _n
from app.dominio import edicion
from app.dominio.edicion import ErrorEdicion
from app.dominio.modelo import Entorno, Planta
from app.ui import operaciones
from app.ui.accesibilidad.dialogos import elegir_opcion, mostrar_error, mostrar_mensaje, pedir_texto
from app.ui.esquemas import c
from app.ui.esquemas_elementos import ORDENES, esquema_de
from app.ui.formulario import pedir_formulario

log = logging.getLogger(__name__)


def _sin_entorno(contexto: Any) -> bool:
	"""Avisa si no hay entorno abierto. True si no se puede seguir."""
	if contexto.entorno is not None:
		return False
	mostrar_mensaje(
		contexto.ventana,
		_("No hay ningún entorno abierto. Cree uno con Archivo, Nuevo entorno, o abra uno con Archivo, Abrir."),
		_("Sin entorno"),
	)
	return True


def describir(contexto: Any, elemento: Any) -> str:
	"""Frase que describe un elemento; si no se puede componer, su nombre (nunca falla)."""
	try:
		if isinstance(elemento, Entorno):
			return _("Entorno {nombre}.").format(nombre=elemento.nombre)
		return edicion.describir_elemento(contexto.entorno, elemento, contexto.catalogo)
	except Exception:  # noqa: BLE001 - una descripción que falla no debe impedir trabajar con el elemento
		log.exception("No se pudo describir el elemento %r", getattr(elemento, "id", elemento))
		return operaciones.nombre_de(elemento)


def _nombre_seleccion(contexto: Any) -> str:
	elegido = contexto.elemento_seleccionado()
	return operaciones.nombre_de(elegido[1]) if elegido is not None else ""


def ejecutar_orden(contexto: Any, clave: str, iniciales: dict[str, Any] | None = None) -> str | None:
	"""Abre el formulario de una orden de ``ORDENES`` y la hace. Devuelve el id del elemento, o None.

	:param iniciales: valores que sustituyen a los de partida (la posición
		dibujada en el plano, por ejemplo).
	"""
	if _sin_entorno(contexto):
		return None
	orden = ORDENES[clave]
	impedimento = orden.requisito(contexto)
	if impedimento:
		mostrar_mensaje(contexto.ventana, impedimento, _(orden.titulo))
		return None
	valores = orden.valores(contexto)
	valores.update(iniciales or {})
	seleccionado = _nombre_seleccion(contexto)

	def validar(v: dict[str, Any]) -> Any:
		nombre = " ".join(orden.nombre({**v, "_nombre": seleccionado}).split())
		return contexto.ejecutar(nombre, lambda: orden.hacer(contexto, v))

	resultado = pedir_formulario(
		contexto.ventana, _(orden.titulo), orden.campos(contexto), valores, validar, _(orden.introduccion) if orden.introduccion else ""
	)
	if resultado is None:
		return None
	elemento = resultado["_producto"]
	id_elemento = getattr(elemento, "id", "") or ""
	if id_elemento:
		contexto.seleccionar(id_elemento)
	contexto.anunciar(describir(contexto, elemento))
	return id_elemento or None


def editar_propiedades(contexto: Any, id_elemento: str | None = None) -> bool:
	"""Abre el formulario de propiedades de un elemento (el seleccionado si no se dice otro). True si cambió algo."""
	if _sin_entorno(contexto):
		return False
	objetivo = id_elemento if id_elemento is not None else contexto.seleccion
	try:
		_planta, elemento = operaciones.resolver(contexto.entorno, objetivo or operaciones.CLAVE_ENTORNO)
	except ErrorEdicion as error:
		mostrar_error(contexto.ventana, str(error), _("Propiedades"))
		return False
	campos = esquema_de(elemento, contexto.entorno, contexto.catalogo)
	if not campos:
		mostrar_mensaje(contexto.ventana, _("Este elemento no tiene propiedades que cambiar."), _("Propiedades"))
		return False
	nombre = operaciones.nombre_de(elemento)
	clave = objetivo or operaciones.CLAVE_ENTORNO
	return aplicar_propiedades_con_dialogo(contexto, clave, campos, nombre)


def aplicar_propiedades(contexto: Any, clave: str, valores: dict[str, Any]) -> list[str]:
	"""Aplica al elemento ``clave`` los valores de su formulario; devuelve las claves cambiadas.

	Lo usan el diálogo de propiedades y el panel de propiedades de la ventana.
	Si nada cambió no se apunta nada en el historial.
	"""
	if not operaciones.valores_cambiados(contexto.entorno, clave, valores, contexto.catalogo):
		return []
	_planta, elemento = operaciones.resolver(contexto.entorno, clave)
	nombre = _("cambiar {nombre}").format(nombre=operaciones.nombre_de(elemento))
	return contexto.ejecutar(nombre, lambda: operaciones.aplicar_valores(contexto.entorno, clave, valores, contexto.catalogo))


def aplicar_propiedades_con_dialogo(contexto: Any, clave: str, campos: list[Any], nombre: str) -> bool:
	"""Formulario modal de propiedades; al aceptar aplica los cambios y los anuncia."""
	_planta, elemento = operaciones.resolver(contexto.entorno, clave)
	valores = operaciones.valores_de(contexto.entorno, elemento, contexto.catalogo)
	resultado = pedir_formulario(
		contexto.ventana,
		_("Propiedades de {nombre}").format(nombre=nombre),
		campos,
		valores,
		lambda v: aplicar_propiedades(contexto, clave, v),
	)
	if resultado is None:
		return False
	cambiadas = resultado["_producto"] or []
	if not cambiadas:
		contexto.anunciar(_("Sin cambios."))
		return False
	_planta, elemento = operaciones.resolver(contexto.entorno, clave)
	contexto.anunciar(describir(contexto, elemento))
	return True


def renombrar(contexto: Any) -> bool:
	"""Pide el nombre nuevo del elemento seleccionado y lo cambia."""
	if _sin_entorno(contexto):
		return False
	elegido = contexto.elemento_seleccionado()
	if elegido is None:
		mostrar_mensaje(contexto.ventana, _("Seleccione antes un elemento en el árbol, en la lista o en el plano."), _("Renombrar"))
		return False
	id_elemento = contexto.seleccion
	anterior = operaciones.nombre_de(elegido[1])
	nuevo = pedir_texto(contexto.ventana, _("&Nombre:"), _("Renombrar"), anterior, max_caracteres=200)
	if nuevo is None or not nuevo.strip() or nuevo.strip() == anterior:
		return False
	nuevo = nuevo.strip()

	def operacion() -> None:
		_planta, actual = operaciones.resolver(contexto.entorno, id_elemento)
		edicion.renombrar(contexto.entorno, actual, nuevo)

	try:
		contexto.ejecutar(_("renombrar {anterior} como {nuevo}").format(anterior=anterior, nuevo=nuevo), operacion)
	except ValueError as error:
		mostrar_error(contexto.ventana, str(error), _("Renombrar"))
		return False
	contexto.anunciar(_("Ahora se llama {nombre}.").format(nombre=nuevo))
	return True


def duplicar(contexto: Any) -> str | None:
	"""Duplica el elemento seleccionado medio metro al este y selecciona la copia."""
	if _sin_entorno(contexto):
		return None
	elegido = contexto.elemento_seleccionado()
	if elegido is None:
		mostrar_mensaje(contexto.ventana, _("Seleccione antes un elemento en el árbol, en la lista o en el plano."), _("Duplicar"))
		return None
	id_elemento = contexto.seleccion
	nombre = operaciones.nombre_de(elegido[1])

	def operacion() -> Any:
		_planta, original = operaciones.resolver(contexto.entorno, id_elemento)
		return edicion.duplicar(contexto.entorno, original)

	try:
		copia = contexto.ejecutar(_("duplicar {nombre}").format(nombre=nombre), operacion)
	except ValueError as error:
		mostrar_error(contexto.ventana, str(error), _("Duplicar"))
		return None
	contexto.seleccionar(copia.id)
	contexto.anunciar(_("Copia creada: {descripcion}").format(descripcion=describir(contexto, copia)))
	return copia.id


def borrar(contexto: Any) -> bool:
	"""Borra el elemento seleccionado tras confirmarlo con botones que dicen la acción."""
	if _sin_entorno(contexto):
		return False
	elegido = contexto.elemento_seleccionado()
	if elegido is None:
		mostrar_mensaje(contexto.ventana, _("Seleccione antes un elemento en el árbol, en la lista o en el plano."), _("Borrar"))
		return False
	planta, elemento = elegido
	id_elemento = contexto.seleccion
	nombre = operaciones.nombre_de(elemento)
	if isinstance(elemento, Planta):
		pregunta = _("¿Borrar la planta «{nombre}» con todo lo que contiene? Se podrá deshacer.").format(nombre=nombre)
	else:
		pregunta = _(
			"¿Borrar «{nombre}»? Si otras cosas dependen de él (las puertas de una habitación, las aceras de una calle), se borran también. Se podrá deshacer."
		).format(nombre=nombre)
	# «Cancelar» va primero para que sea el botón de Intro: un Intro de más no debe borrar nada.
	elegida = elegir_opcion(contexto.ventana, pregunta, _("Borrar"), [_("&Cancelar"), _("&Borrar")])
	if elegida != 1:
		return False

	def operacion() -> list[str]:
		_planta, actual = operaciones.resolver(contexto.entorno, id_elemento)
		return edicion.borrar(contexto.entorno, actual)

	try:
		borrados = contexto.ejecutar(_("borrar {nombre}").format(nombre=nombre), operacion)
	except ValueError as error:
		mostrar_error(contexto.ventana, str(error), _("Borrar"))
		return False
	# La selección pasa a la planta: el foco no puede quedarse en algo que ya no existe.
	contexto.seleccion = ""
	destino = planta.id if planta is not None and planta is not elemento and contexto.entorno.planta(planta.id) is not None else ""
	contexto.seleccionar(destino)
	if not destino:
		contexto.emitir("seleccion_cambiada")
	otros = max(0, len(borrados) - 1)
	if otros:
		contexto.anunciar(
			_n(
				"Borrado {nombre} y {n} elemento que dependía de él.", "Borrado {nombre} y {n} elementos que dependían de él.", otros
			).format(nombre=nombre, n=otros)
		)
	else:
		contexto.anunciar(_("Borrado {nombre}.").format(nombre=nombre))
	return True


def fijar_inicio(contexto: Any) -> bool:
	"""Pone el punto de inicio del entorno junto al elemento seleccionado."""
	if _sin_entorno(contexto):
		return False
	posicion = operaciones.posicion_junto_a(contexto.entorno, contexto.seleccion) if contexto.seleccion else None
	if posicion is None:
		mostrar_mensaje(
			contexto.ventana, _("Seleccione antes el espacio o el elemento junto al que debe empezar el recorrido."), _("Poner el inicio")
		)
		return False

	def operacion() -> Any:
		planta = contexto.entorno.planta(posicion.planta)
		if planta is None:
			raise ErrorEdicion(_("La planta ya no existe."))
		return edicion.fijar_inicio(contexto.entorno, planta, posicion.x, posicion.y, posicion.rumbo)

	try:
		contexto.ejecutar(_("poner el inicio junto a {nombre}").format(nombre=_nombre_seleccion(contexto)), operacion)
	except ValueError as error:
		mostrar_error(contexto.ventana, str(error), _("Poner el inicio"))
		return False
	contexto.anunciar(_("Inicio puesto junto a {nombre}.").format(nombre=_nombre_seleccion(contexto)))
	return True


def nuevo_entorno(contexto: Any) -> Entorno | None:
	"""Asistente «Nuevo entorno»: nombre, plantilla y autor. Devuelve el entorno creado (sin abrirlo) o None."""
	plantillas = [
		(clave, _("{nombre}: {explicacion}").format(nombre=_(nombre), explicacion=_(explicacion)))
		for clave, (nombre, explicacion, _f) in operaciones.PLANTILLAS.items()
	]
	campos = [
		c("nombre", N_("Nombre del entorno"), obligatorio=True, ayuda=N_("Por ejemplo «Casa de Ana» o «Colegio, planta baja».")),
		c(
			"plantilla",
			N_("Punto de partida"),
			"opcion",
			N_("Empiece en blanco o con una plantilla que después podrá cambiar."),
			opciones=plantillas,
		),
		c(
			"amueblar",
			N_("Amueblar con los complementos instalados"),
			"si_no",
			N_("En las plantillas con habitaciones, coloca el mobiliario habitual."),
		),
		c("autor", N_("Autor")),
		c("descripcion", N_("Descripción"), "largo"),
	]

	def crear(v: dict[str, Any]) -> Entorno:
		entorno = operaciones.crear_de_plantilla(
			str(v.get("plantilla") or "en_blanco"), str(v.get("nombre") or ""), str(v.get("autor") or "")
		)
		entorno.descripcion = str(v.get("descripcion") or "")
		if v.get("amueblar") and contexto.catalogo is not None:
			from app.dominio import ejemplos

			ejemplos.amueblar_ejemplos(entorno, contexto.catalogo)
		return entorno

	resultado = pedir_formulario(
		contexto.ventana,
		_("Nuevo entorno"),
		campos,
		{"plantilla": "en_blanco", "amueblar": False},
		crear,
		_("Dé un nombre al entorno y elija de dónde partir. Todo se puede cambiar después."),
	)
	return resultado["_producto"] if resultado is not None else None
