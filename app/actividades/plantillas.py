"""Actividades de ejemplo para los tres entornos de ``app.dominio.ejemplos``.

Sirven de muestra al profesional (se abren, se juegan y se copian) y de
prueba de que el formato basta para hacer actividades completas. Se
construyen sobre el entorno ya amueblado, buscando los sitios por su posición
en el plano y no por su id: los ids de los objetos dependen de qué
complementos haya instalados, y los nombres, del idioma.

``tools/generar_ejemplos.py`` las guarda dentro de cada ``.elab`` de
``data/ejemplos``.
"""

from __future__ import annotations

import logging
import random
from collections.abc import Callable
from typing import Any

from app.actividades.formato import normalizar
from app.actividades.lugares import puntos_libres
from app.actividades.reparto import contenedores_de, repartir_premios
from app.core.i18n import _
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Entorno, Espacio, Planta, Referencia
from app.motor.mundo import Mundo

log = logging.getLogger(__name__)

SEMILLA_EJEMPLOS = 2026


class _Constructor:
	"""Ayudas para situar cosas en un entorno de ejemplo por sus coordenadas."""

	def __init__(self, entorno: Entorno, catalogo: Catalogo | None) -> None:
		self.entorno = entorno
		self.catalogo = catalogo
		self.mundo = Mundo(entorno, catalogo)
		self.azar = random.Random(SEMILLA_EJEMPLOS)
		self._objetos_usados: set[str] = set()

	def planta(self, indice: int = 0) -> Planta:
		return self.entorno.plantas[indice]

	def espacio(self, x: float, y: float, planta: int = 0) -> Espacio | None:
		return self.planta(planta).espacio_en(x, y, incluir_macizos=False)

	def referencia(self, x: float, y: float, planta: int = 0) -> Referencia | None:
		referencias = self.planta(planta).referencias
		if not referencias:
			return None
		return min(referencias, key=lambda r: (round(geo.distancia((r.x, r.y), (x, y)), 2), r.id))

	def premio(
		self,
		ident: str,
		nombre: str,
		x: float,
		y: float,
		planta: int = 0,
		visibilidad: str = "cerca",
		mensaje: str = "",
		pista: str = "",
		palabras: tuple[str, ...] = (),
		suelto: bool = False,
	) -> dict[str, Any] | None:
		"""Un premio en el espacio que contiene (x, y): dentro de un contenedor si lo hay, o en el punto libre más cercano a (x, y).

		``palabras`` son trozos de id de tipo de objeto por los que se
		prefiere el contenedor («armario», «cama»); ``suelto`` lo deja fuera
		de todo objeto aunque haya contenedores.
		"""
		lugar = self.planta(planta)
		espacio = self.espacio(x, y, planta)
		if espacio is None:
			log.warning("No hay espacio en (%s, %s) para el premio de ejemplo %s", x, y, ident)
			return None
		dato: dict[str, Any] = {"id": ident, "nombre": nombre, "visibilidad": visibilidad, "mensaje": mensaje, "pista": pista}
		contenedores = (
			[] if suelto else [o for o in contenedores_de(self.mundo, lugar, espacio, self.catalogo) if o.id not in self._objetos_usados]
		)
		if contenedores:
			preferidos = [o for o in contenedores if any(palabra in o.tipo for palabra in palabras)]
			elegido = preferidos[0] if preferidos else min(contenedores, key=lambda o: (round(geo.distancia((o.x, o.y), (x, y)), 2), o.id))
			self._objetos_usados.add(elegido.id)
			dato.update({"planta": lugar.id, "x": elegido.x, "y": elegido.y, "dentro_de": elegido.id})
			return dato
		libres = puntos_libres(self.mundo, lugar.id, espacio)
		if not libres:
			return None
		punto = min(libres, key=lambda p: (round(geo.distancia(p, (x, y)), 2), p))
		dato.update({"planta": lugar.id, "x": punto[0], "y": punto[1], "dentro_de": None})
		return dato

	def posicion(self, x: float, y: float, rumbo: float, planta: int = 0) -> dict[str, Any]:
		return {"planta": self.planta(planta).id, "x": x, "y": y, "rumbo": rumbo}


def _renombrar(premios: list[dict[str, Any]], nombres: list[str]) -> list[dict[str, Any]]:
	"""Pone nombres propios a los premios de un reparto asistido."""
	for premio, nombre in zip(premios, nombres, strict=False):
		premio["nombre"] = nombre
	return premios


def _vivienda(c: _Constructor) -> list[dict[str, Any]]:
	"""Vivienda: búsqueda del tesoro infantil, «prepara la visita» adulta, pistas, familiarización del salón y visita guiada."""
	tesoros = [
		c.premio("moneda", _("la moneda de oro"), 2.2, 7.0, palabras=("cama",), mensaje=_("Estaba debajo de la cama.")),
		c.premio("dinosaurio", _("el dinosaurio"), 2.2, 2.0, palabras=("sofa",)),
		c.premio("galleta", _("la galleta gigante"), 6.2, 2.0, palabras=("frigorifico",), mensaje=_("¡Qué fresquita!")),
		c.premio("patito", _("el patito de goma"), 5.7, 7.0, suelto=True),
		c.premio("estrella", _("la estrella brillante"), 7.0, 4.6, visibilidad="lejos", suelto=True),
	]
	visita = [
		c.premio("llaves", _("las llaves"), 2.2, 2.0, palabras=("mueble_tv", "estanteria"), visibilidad="oculto"),
		c.premio("abrigo", _("el abrigo"), 2.2, 7.0, palabras=("armario",), visibilidad="oculto"),
		c.premio("paraguas", _("el paraguas"), 7.2, 4.6, suelto=True, mensaje=_("Estaba secándose junto al radiador del pasillo.")),
	]
	pistas = [
		c.premio("sobre-1", _("el primer sobre"), 6.2, 2.0, palabras=("encimera", "lavavajillas"), visibilidad="cerca"),
		c.premio("sobre-2", _("el segundo sobre"), 5.7, 7.0, suelto=True),
		c.premio("sobre-3", _("el tercer sobre"), 2.2, 2.0, palabras=("estanteria",)),
		c.premio("sobre-4", _("el sobre final"), 2.2, 7.0, palabras=("escritorio", "mesilla")),
	]
	salon = c.espacio(2.2, 2.0)
	return [
		{
			"id": "busqueda-del-tesoro",
			"tipo": "busqueda",
			"nombre": _("Búsqueda del tesoro en casa"),
			"descripcion": _("Cinco tesoros escondidos por toda la casa: hay que entrar en todas las habitaciones y abrir cosas."),
			"estilo": "infantil",
			"premios": [p for p in tesoros if p is not None],
			"anunciar_premios": True,
			"baliza": "al_pedir",
			"mensajes": {
				"inicio": _("¡Hola! Tiko ha escondido cinco tesoros por la casa. ¡Vamos a buscarlos!"),
				"final": _("¡Has encontrado todos los tesoros de la casa!"),
			},
			"recompensas": {"desbloqueos": [{"estrellas": 5, "nombre": _("la casa del árbol")}]},
			"cuestionario": True,
		},
		{
			"id": "prepara-la-visita",
			"tipo": "busqueda",
			"nombre": _("Prepara la visita"),
			"descripcion": _(
				"Antes de salir de casa: localizar las llaves, el abrigo y el paraguas. Sobrio y práctico, pensado para adultos."
			),
			"estilo": "adulto",
			"premios": [p for p in visita if p is not None],
			"anunciar_premios": True,
			"baliza": "nunca",
			"mensajes": {
				"inicio": _("Prepara la visita: encuentra las llaves, el abrigo y el paraguas."),
				"final": _("Ya lo tienes todo para salir."),
			},
		},
		{
			"id": "pistas-por-la-casa",
			"tipo": "pistas",
			"nombre": _("Pistas por la casa"),
			"descripcion": _(
				"Cuatro sobres encadenados: cada uno dice dónde está el siguiente, con relaciones reales entre las habitaciones."
			),
			"estilo": "juvenil",
			"premios": [p for p in pistas if p is not None],
			"pistas_automaticas": True,
			"usar_niveles": True,
			"nivel": 1,
		},
		{
			"id": "conoce-el-salon",
			"tipo": "perimetro",
			"nombre": _("Conoce el salón"),
			"descripcion": _("Familiarización de sala: primero el perímetro siguiendo la pared y después el interior."),
			"inicio": c.posicion(1.95, 3.3, 180.0),
			"espacio": salon.id if salon is not None else None,
			"baliza": "nunca",
		},
		{
			"id": "visita-a-la-casa",
			"tipo": "visita_guiada",
			"nombre": _("Visita a la casa"),
			"descripcion": _("Un paseo por todas las estancias oyendo la descripción de cada una."),
		},
	]


def _centro(c: _Constructor) -> list[dict[str, Any]]:
	"""Centro de dos plantas: sacar los tesoros, exámenes de rutas, de salida y de señalar, sigue al guía y una ruta por niveles."""
	tesoros = _renombrar(
		repartir_premios(c.entorno, 5, c.catalogo, semilla=SEMILLA_EJEMPLOS, visibilidad="cerca", dentro_de_objetos=False),
		[_("el trofeo"), _("el mapa antiguo"), _("la llave maestra"), _("el globo terráqueo"), _("el reloj de arena")],
	)
	biblioteca = c.espacio(16.0, 10.0, 0)
	informatica = c.espacio(16.0, 10.0, 1)
	return [
		{
			"id": "sacar-los-tesoros",
			"tipo": "sacar_tesoros",
			"nombre": _("Sacar los tesoros del centro"),
			"descripcion": _(
				"Cinco tesoros por las dos plantas. Se sacan de uno en uno por la salida más cercana: 3, 2, 1 o 0 puntos según la salida."
			),
			"estilo": "juvenil",
			"premios": tesoros,
			"baliza": "nunca",
			"cuestionario": True,
		},
		{
			"id": "examen-de-rutas",
			"tipo": "examen_rutas",
			"nombre": _("Examen de rutas del centro"),
			"descripcion": _("Cinco rutas no entrenadas de longitud parecida, con seis minutos para cada una."),
			"numero_pruebas": 5,
			"tiempo_por_prueba_s": 360,
			"semilla": SEMILLA_EJEMPLOS,
			"regla_parada": {"activa": True, "de": 5, "minimo": 3},
		},
		{
			"id": "examen-de-salida",
			"tipo": "examen_salida",
			"nombre": _("Examen de salida más corta"),
			"descripcion": _("Desde cinco puntos del centro, salir por la salida más cercana."),
			"numero_pruebas": 5,
			"tiempo_por_prueba_s": 180,
			"semilla": SEMILLA_EJEMPLOS,
			"regla_parada": None,
		},
		{
			"id": "examen-de-senalar",
			"tipo": "examen_senalar",
			"nombre": _("Examen de señalar"),
			"descripcion": _("Girarse hacia cinco lugares del centro que no se perciben desde donde se está."),
			"numero_pruebas": 5,
			"semilla": SEMILLA_EJEMPLOS,
			"regla_parada": None,
		},
		{
			"id": "sigue-al-guia",
			"tipo": "sigue_guia",
			"nombre": _("Sigue al guía hasta la biblioteca"),
			"descripcion": _("Un guía lleva al alumno del vestíbulo a la biblioteca; se le sigue por el sonido de sus pasos."),
			"destino": biblioteca.id if biblioteca is not None else None,
		},
		{
			"id": "ruta-a-informatica",
			"tipo": "ruta",
			"nombre": _("Del vestíbulo a la sala de informática"),
			"descripcion": _(
				"Ruta con cambio de planta. Las ayudas se retiran por niveles: con baliza, baliza al pedirla, sin baliza y sin «dónde estoy»."
			),
			"destino": informatica.id if informatica is not None else None,
			"usar_niveles": True,
			"nivel": 0,
		},
	]


def _barrio(c: _Constructor) -> list[dict[str, Any]]:
	"""Barrio: recadero hasta la parada, práctica de cruce y localizar el centro cívico."""
	buzon = c.referencia(-4.5, -12.0)
	parada = c.referencia(15.0, 4.0)
	vestibulo = c.espacio(8.0, -9.0)
	return [
		{
			"id": "recado-a-la-parada",
			"tipo": "recadero",
			"nombre": _("Un recado hasta la parada"),
			"descripcion": _("Recoger una carta junto al buzón de correos y llevarla a la parada de autobús, cruzando las dos calles."),
			"estilo": "adulto",
			"objetivos": [
				{
					"id": "carta",
					"nombre": _("la carta"),
					"recoger": buzon.id if buzon is not None else None,
					"entregar": parada.id if parada is not None else None,
				}
			],
			"baliza": "al_pedir",
		},
		{
			"id": "practica-de-cruce",
			"tipo": "cruce",
			"nombre": _("Práctica de cruce"),
			"descripcion": _(
				"Cruzar dos veces: por el paso con semáforo sonoro y por el paso sin semáforo. Es un simulador: no dice si un cruce real es seguro."
			),
			"cruces": 2,
		},
		{
			"id": "encuentra-el-centro-civico",
			"tipo": "localizar",
			"nombre": _("Encuentra el centro cívico"),
			"descripcion": _("Llegar al vestíbulo del centro cívico sabiendo solo su nombre."),
			"destino": vestibulo.id if vestibulo is not None else None,
			"confirmar": True,
			"baliza": "nunca",
		},
	]


# Nombre del ejemplo (el de ``app.dominio.ejemplos.EJEMPLOS``) → función que construye sus actividades.
PLANTILLAS: dict[str, Callable[[_Constructor], list[dict[str, Any]]]] = {
	"vivienda-de-ejemplo": _vivienda,
	"centro-de-dos-plantas": _centro,
	"barrio-de-ejemplo": _barrio,
}


def plantillas_de(nombre: str, entorno: Entorno, catalogo: Catalogo | None = None) -> list[dict[str, Any]]:
	"""Actividades de ejemplo de uno de los entornos de ejemplo, ya normalizadas; lista vacía si no las tiene.

	``entorno`` es el ejemplo ya construido (y amueblado, si se quiere que
	los premios se escondan dentro de los muebles).
	"""
	construir = PLANTILLAS.get(nombre)
	if construir is None:
		return []
	return [normalizar(datos) for datos in construir(_Constructor(entorno, catalogo))]
