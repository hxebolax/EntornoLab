"""De los datos a la actividad: crear una en marcha, proponer una nueva y describirla.

``crear_actividad`` elige la clase por el ``tipo`` de los datos (un tipo
desconocido se juega como exploración libre: los datos nunca traen código que
ejecutar). ``nueva_actividad`` da una actividad con valores razonables para el
entorno, lista para jugar o para que el profesional la retoque, y
``describir_actividad`` la resume en una frase tras otra para leerla con un
lector de pantalla.
"""

from __future__ import annotations

import logging
from typing import Any

from app.actividades import examenes, juegos, practicas, secuencia
from app.actividades.base import Actividad
from app.actividades.formato import normalizar
from app.actividades.lugares import Lugar, espacios_jugables, lugar_de_espacio, punto_esta_libre, resolver_lugar
from app.actividades.reparto import repartir_premios
from app.actividades.tipos import ESTILOS, NOMBRES_AYUDAS, TIPOS, poner_campo
from app.core.i18n import _, _n
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Entorno, Objeto
from app.motor.mundo import Mundo
from app.motor.navegacion import Navegador

log = logging.getLogger(__name__)

CLASES: dict[str, type[Actividad]] = {
	"busqueda": juegos.Busqueda,
	"pistas": juegos.Pistas,
	"sacar_tesoros": juegos.SacarTesoros,
	"escondite": juegos.Escondite,
	"sigue_guia": juegos.SigueGuia,
	"explorador": juegos.Explorador,
	"cruce": juegos.Cruce,
	"recadero": secuencia.Recadero,
	"ruta": secuencia.Ruta,
	"ruta_inversa": secuencia.RutaInversa,
	"volver_origen": secuencia.VolverOrigen,
	"ruta_alternativa": secuencia.RutaAlternativa,
	"localizar": secuencia.Localizar,
	"visita_guiada": secuencia.VisitaGuiada,
	"exploracion": practicas.Exploracion,
	"perimetro": practicas.Perimetro,
	"linea_guia": practicas.LineaGuia,
	"examen_rutas": examenes.ExamenRutas,
	"examen_salida": examenes.ExamenSalida,
	"examen_senalar": examenes.ExamenSenalar,
	"examen_distancias": examenes.ExamenDistancias,
	"examen_reconstruccion": examenes.ExamenReconstruccion,
}


def crear_actividad(
	datos: dict,
	entorno: Entorno,
	catalogo: Catalogo | None = None,
	estilo: str | None = None,
	semilla: int | None = None,
	nivel: int | None = None,
) -> Actividad:
	"""Crea la actividad lista para colgarla de una ``Sesion``.

	``estilo`` es el de la ficha del alumno y solo se usa si la actividad no
	fija el suyo. ``semilla`` (normalmente la de la partida) hace reproducible
	lo que la actividad sortea, pero solo si sus datos no traen ``semilla``:
	un examen la trae siempre, y por eso se repite idéntico otro día; para
	otro examen equivalente se cambia la semilla en los datos. ``nivel`` es
	el nivel de ayudas en el que está el alumno (el ``nivel_siguiente`` del
	resultado de su sesión anterior).
	"""
	tipo = datos.get("tipo") if isinstance(datos, dict) else None
	clase = CLASES.get(str(tipo))
	if clase is None:
		log.warning("Tipo de actividad desconocido (%s): se juega como exploración libre", tipo)
		clase = practicas.Exploracion
	return clase(datos, entorno, catalogo, estilo=estilo, semilla=semilla, nivel=nivel)


# ── Actividad nueva ──────────────────────────────────────────────────────────


def _lugares_por_lejania(entorno: Entorno, mundo: Mundo, nav: Navegador) -> list[tuple[float, Lugar]]:
	"""Un lugar por espacio jugable alcanzable desde el inicio, con su distancia de camino, del más lejano al más cercano."""
	alcanzables = nav.espacios_alcanzables(entorno.inicio)
	con_distancia: list[tuple[float, Lugar]] = []
	for planta, espacio in espacios_jugables(entorno):
		if alcanzables and espacio.id not in alcanzables:
			continue
		lugar = lugar_de_espacio(mundo, planta, espacio)
		distancia = nav.distancia(entorno.inicio, lugar.terna)
		if distancia is not None and distancia > 1.5:
			con_distancia.append((distancia, lugar))
	con_distancia.sort(key=lambda par: (-round(par[0], 2), par[1].elemento_id))
	return con_distancia


def _corte_con_alternativa(entorno: Entorno, nav: Navegador, destino: Lugar) -> str | None:
	"""Un paso del camino más corto al destino que se pueda cortar dejando otro camino; None si no lo hay.

	Primero se prueban los conectores (cortar la escalera deja el ascensor) y
	después las puertas y huecos que cruza el camino.
	"""
	ruta = nav.ruta(entorno.inicio, destino.terna)
	if ruta is None:
		return None
	for conector_id in ruta.conectores:
		if nav.ruta(entorno.inicio, destino.terna, evitar=[conector_id]) is not None:
			return conector_id
	for (planta_a, xa, ya), (planta_b, xb, yb) in zip(ruta.puntos[:-1], ruta.puntos[1:], strict=True):
		if planta_a != planta_b:
			continue
		planta = entorno.planta(planta_a)
		if planta is None:
			continue
		for abertura in planta.aberturas:
			if abertura.tipo == "ventana" or geo.corte_segmentos((xa, ya), (xb, yb), abertura.a, abertura.b) is None:
				continue
			if nav.ruta(entorno.inicio, destino.terna, evitar=[abertura.id]) is not None:
				return abertura.id
	return None


def nueva_actividad(tipo: str, entorno: Entorno, catalogo: Catalogo | None = None, **opciones: Any) -> dict:
	"""Actividad de ese tipo con valores razonables para el entorno, lista para editar o jugar.

	Las ``opciones`` sustituyen a lo propuesto; sus claves son las de los
	campos (con puntos para lo anidado se usa un diccionario, o
	``**{"travieso.activo": True}``). Además: ``cantidad`` (premios que
	repartir), ``visibilidad`` y ``dentro_de_objetos`` para el reparto.

	Lanza ``KeyError`` si el tipo no existe.
	"""
	info = TIPOS[tipo]
	cantidad = opciones.pop("cantidad", None)
	visibilidad = str(opciones.pop("visibilidad", "cerca"))
	dentro = bool(opciones.pop("dentro_de_objetos", True))
	semilla = opciones.get("semilla", 1)
	datos: dict[str, Any] = normalizar({"tipo": tipo, "id": tipo, "nombre": info.nombre_visible, "descripcion": info.descripcion_visible})
	mundo = Mundo(entorno, catalogo)
	nav = Navegador(mundo)
	lejanos = _lugares_por_lejania(entorno, mundo, nav) if tipo not in ("exploracion", "explorador", "visita_guiada", "cruce") else []
	lejano = lejanos[0][1] if lejanos else None
	if tipo in ("busqueda", "pistas", "sacar_tesoros") and "premios" not in opciones:
		por_defecto = min(6, max(3, len(espacios_jugables(entorno)) - 1))
		datos["premios"] = repartir_premios(
			entorno,
			int(cantidad if cantidad is not None else por_defecto),
			catalogo,
			semilla=semilla,
			visibilidad=visibilidad,
			dentro_de_objetos=dentro,
		)
	if tipo in ("sigue_guia", "ruta", "ruta_alternativa", "localizar") and lejano is not None:
		datos["destino"] = lejano.elemento_id
	if tipo == "ruta_inversa" and lejanos:
		# Para la ida y vuelta, un destino a media distancia: lo bastante lejos para tener giros, no tanto como para cansar.
		datos["destino"] = lejanos[len(lejanos) // 2][1].elemento_id
	if tipo == "ruta_alternativa" and lejanos and "corte" not in opciones and "cortes" not in opciones:
		# Solo se prueban los destinos más lejanos: buscar un corte para cada espacio de un edificio grande tardaría.
		candidatos = [lugar for _distancia, lugar in lejanos[:4]]
		pedido = resolver_lugar(entorno, opciones.get("destino")) if opciones.get("destino") is not None else None
		if pedido is not None:
			candidatos = [pedido]
		for lugar in candidatos:
			corte = _corte_con_alternativa(entorno, nav, lugar)
			if corte is not None:
				if pedido is None:
					datos["destino"] = lugar.elemento_id
				datos["corte"] = corte
				datos["cortes"] = [corte]
				break
	if tipo == "localizar":
		datos["baliza"] = "nunca"
	if tipo == "recadero" and len(lejanos) >= 2:
		datos["objetivos"] = [
			{"id": "encargo-1", "nombre": _("el paquete"), "recoger": lejanos[0][1].elemento_id, "entregar": lejanos[-1][1].elemento_id},
		]
	if tipo == "volver_origen" and lejanos:
		paradas = [lejanos[len(lejanos) // 2][1]]
		if len(lejanos) >= 3:
			paradas.append(lejanos[0][1])
		datos["objetivos"] = [
			{"id": f"parada-{n}", "tipo": "ir_a", "destino": lugar.elemento_id} for n, lugar in enumerate(paradas, start=1)
		]
	if tipo == "linea_guia" and "espacio" not in opciones:
		# El lado más largo de todos los espacios a los que se llega (un pasillo, una acera), empezando junto a uno de sus extremos.
		alcanzables = nav.espacios_alcanzables(entorno.inicio)
		mejor: tuple[float, str, Any, Any, Any, Any] | None = None
		for planta, espacio in espacios_jugables(entorno):
			if alcanzables and espacio.id not in alcanzables:
				continue
			for a, b in espacio.lados():
				largo = round(geo.distancia(a, b), 2)
				if mejor is None or (largo, espacio.id) > (mejor[0], mejor[1]):
					mejor = (largo, espacio.id, planta, espacio, a, b)
		if mejor is not None:
			largo, _id, planta, espacio, a, b = mejor
			datos["espacio"] = espacio.id
			datos["lado"] = "mas_largo"
			centro = espacio.centro()
			medio = geo.punto_medio(a, b)
			hacia = geo.distancia(medio, centro)
			if largo > 2.0 and hacia > 1e-6:
				# Un punto a 70 cm del extremo y a medio metro de la línea, hacia dentro del espacio.
				base = (a[0] + (b[0] - a[0]) * 0.7 / largo, a[1] + (b[1] - a[1]) * 0.7 / largo)
				separacion = min(0.5, hacia * 0.5)
				punto = (base[0] + (centro[0] - medio[0]) * separacion / hacia, base[1] + (centro[1] - medio[1]) * separacion / hacia)
				if punto_esta_libre(mundo, planta.id, punto[0], punto[1], 0.3):
					datos["inicio"] = {
						"planta": planta.id,
						"x": round(punto[0], 2),
						"y": round(punto[1], 2),
						"rumbo": round(geo.rumbo_entre(a, b), 1),
					}
	if tipo == "perimetro" and "espacio" not in opciones:
		# La sala más grande a la que se llega (no un pasillo), y se empieza dentro de ella.
		alcanzables = nav.espacios_alcanzables(entorno.inicio)
		salas = [
			(planta, espacio)
			for planta, espacio in espacios_jugables(entorno)
			if espacio.tipo in ("habitacion", "vestibulo") and espacio.cerrado and (not alcanzables or espacio.id in alcanzables)
		]
		if salas:
			planta, sala = max(salas, key=lambda par: (round(par[1].area(), 2), par[1].id))
			lugar = lugar_de_espacio(mundo, planta, sala)
			datos["espacio"] = sala.id
			datos["inicio"] = {"planta": planta.id, "x": lugar.x, "y": lugar.y, "rumbo": 0.0}
	for clave, valor in opciones.items():
		poner_campo(datos, str(clave), valor)
	return normalizar(datos)


# ── Descripción ──────────────────────────────────────────────────────────────


def _nombre_lugar(entorno: Entorno, valor: Any) -> str:
	lugar = resolver_lugar(entorno, valor)
	return lugar.nombre if lugar is not None else _("un lugar que no existe")


def _describir_premio(entorno: Entorno, premio: dict[str, Any]) -> str:
	partes = [premio["nombre"]]
	contenedor = entorno.elemento(premio["dentro_de"]) if premio.get("dentro_de") else None
	if isinstance(contenedor, Objeto):
		partes.append(_("dentro de {objeto}").format(objeto=contenedor.nombre or contenedor.id))
		planta = entorno.planta_de(contenedor)
		espacio = planta.espacio_en(contenedor.x, contenedor.y, incluir_macizos=False) if planta is not None else None
	else:
		planta = entorno.planta(premio.get("planta") or "")
		tiene_punto = premio.get("x") is not None and premio.get("y") is not None
		espacio = planta.espacio_en(premio["x"], premio["y"], incluir_macizos=False) if planta is not None and tiene_punto else None
	if espacio is not None and espacio.nombre:
		partes.append(_("en {espacio}").format(espacio=espacio.nombre))
	visibilidad = {"lejos": _("se oye desde lejos"), "cerca": _("se oye solo de cerca"), "oculto": _("no suena")}.get(
		premio.get("visibilidad"), ""
	)
	if visibilidad:
		partes.append(visibilidad)
	if premio.get("mensaje") or premio.get("audio"):
		partes.append(_("con mensaje"))
	return ", ".join(partes)


def describir_actividad(datos: dict, entorno: Entorno) -> str:
	"""Resumen en frases cortas de una actividad, para leerlo con un lector de pantalla.

	Dice qué es, para quién, dónde empieza, qué hay que hacer, con qué ayudas
	y cómo acaba. No valida: lo que no exista en el entorno se nombra como tal.
	"""
	limpio = normalizar(datos)
	tipo = limpio["tipo"]
	info = TIPOS.get(tipo)
	frases: list[str] = []
	nombre_tipo = info.nombre_visible if info is not None else _("Actividad de tipo desconocido ({tipo})").format(tipo=tipo)
	frases.append(_("{nombre}: {tipo}.").format(nombre=limpio["nombre"], tipo=nombre_tipo))
	modo = {"juego": _("Es un juego"), "practica": _("Es una práctica"), "examen": _("Es un examen")}[limpio["modo"]]
	estilo = {"infantil": _("estilo infantil"), "juvenil": _("estilo juvenil"), "adulto": _("estilo adulto")}.get(
		limpio["estilo"], _("con el estilo de la ficha del alumno")
	)
	frases.append(_("{modo}, {estilo}.").format(modo=modo, estilo=estilo))
	if limpio["descripcion"]:
		frases.append(limpio["descripcion"] if limpio["descripcion"].endswith(".") else limpio["descripcion"] + ".")
	inicio = limpio.get("inicio")
	if inicio:
		frases.append(_("Empieza en {lugar}.").format(lugar=_nombre_lugar(entorno, inicio)))
	else:
		frases.append(_("Empieza en el inicio del entorno."))
	premios = limpio["premios"]
	if premios:
		frases.append(
			_n("Tiene {n} premio:", "Tiene {n} premios:", len(premios)).format(n=len(premios))
			+ " "
			+ "; ".join(_describir_premio(entorno, p) for p in premios)
			+ "."
		)
	if limpio.get("destino"):
		frases.append(_("Destino: {lugar}.").format(lugar=_nombre_lugar(entorno, limpio["destino"])))
	if limpio.get("espacio"):
		frases.append(_("Espacio: {lugar}.").format(lugar=_nombre_lugar(entorno, limpio["espacio"])))
	if limpio.get("cortes"):
		nombres = [str(getattr(entorno.elemento(c), "nombre", "") or c) for c in limpio["cortes"]]
		frases.append(_("Paso cortado: {lista}.").format(lista=", ".join(nombres)))
	objetivos = limpio["objetivos"]
	if objetivos:
		textos: list[str] = []
		for objetivo in objetivos:
			if objetivo.get("recoger") is not None or objetivo.get("entregar") is not None:
				textos.append(
					_("recoger {nombre} en {origen} y llevarlo a {destino}").format(
						nombre=objetivo.get("nombre") or _("el encargo"),
						origen=_nombre_lugar(entorno, objetivo.get("recoger")),
						destino=_nombre_lugar(entorno, objetivo.get("entregar")),
					)
				)
			elif objetivo.get("destino") is not None:
				textos.append(_nombre_lugar(entorno, objetivo.get("destino")))
		if textos:
			frases.append(
				_n("{n} objetivo: {lista}.", "{n} objetivos: {lista}.", len(textos)).format(n=len(textos), lista="; ".join(textos))
			)
	if limpio["modo"] == "examen":
		if limpio["pruebas"]:
			frases.append(
				_n("{n} prueba definida a mano.", "{n} pruebas definidas a mano.", len(limpio["pruebas"])).format(n=len(limpio["pruebas"]))
			)
		else:
			frases.append(
				_("{n} pruebas generadas con la semilla {semilla}: con la misma semilla el examen se repite idéntico.").format(
					n=limpio.get("numero_pruebas"), semilla=limpio.get("semilla")
				)
			)
		limite = limpio.get("tiempo_por_prueba_s")
		if limite:
			frases.append(_("Límite de {n} segundos por prueba; el tiempo en pausa no cuenta.").format(n=int(limite)))
		regla = limpio.get("regla_parada")
		if regla and regla.get("activa", True):
			frases.append(
				_("Regla de parada: hacen falta {minimo} aciertos en las {de} primeras pruebas para seguir.").format(
					minimo=regla["minimo"], de=regla["de"]
				)
			)
		frases.append(_("Sin pistas, sin celebraciones y sin decir si se acierta."))
	else:
		if limpio.get("tiempo_limite_s"):
			frases.append(_("Contrarreloj: {n} segundos de juego.").format(n=int(limpio["tiempo_limite_s"])))
		else:
			frases.append(_("Sin límite de tiempo."))
		if limpio["niveles"]:
			frases.append(
				_("Las ayudas se retiran en {n} niveles; empieza en el {nivel}.").format(
					n=len(limpio["niveles"]), nivel=limpio["nivel"] + 1
				)
			)
		elif "baliza" in limpio and tipo != "sigue_guia":
			baliza = {"nunca": _("sin baliza"), "al_pedir": _("baliza solo al pedir una pista"), "siempre": _("con baliza todo el rato")}[
				limpio["baliza"]
			]
			frases.append(_("Baliza: {modo}.").format(modo=baliza))
		if limpio["travieso"]["activo"]:
			frases.append(_("Con el travieso, que cambia premios de sitio."))
	prohibidas = [_(NOMBRES_AYUDAS.get(ayuda, ayuda)) for ayuda, regla in limpio["ayudas"].items() if not regla.get("permitida", True)]
	limitadas = [
		_("{ayuda} ({n} veces)").format(ayuda=_(NOMBRES_AYUDAS.get(ayuda, ayuda)), n=regla["limite"])
		for ayuda, regla in limpio["ayudas"].items()
		if regla.get("permitida", True) and regla.get("limite") is not None
	]
	if prohibidas:
		frases.append(_("Ayudas prohibidas: {lista}.").format(lista=", ".join(prohibidas)))
	if limitadas:
		frases.append(_("Ayudas limitadas: {lista}.").format(lista=", ".join(limitadas)))
	if limpio["cuestionario"]:
		frases.append(_("Al terminar se hacen tres preguntas opcionales sobre esfuerzo, confianza y disfrute."))
	desbloqueos = limpio["recompensas"]["desbloqueos"]
	if desbloqueos and limpio["modo"] != "examen":
		for regla in desbloqueos:
			frases.append(_("Al juntar {n} estrellas se desbloquea {nombre}.").format(n=regla["estrellas"], nombre=regla["nombre"]))
	return " ".join(frases)


def estilos_disponibles() -> tuple[str, ...]:
	"""Estilos de presentación que entiende el paquete."""
	return ESTILOS
