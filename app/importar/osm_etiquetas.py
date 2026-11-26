"""Tablas que traducen etiquetas de OpenStreetMap a los términos de EntornoLab.

Están separadas del conversor para poder revisarlas y ampliarlas sin tocar
la lógica: qué anchura se supone a cada tipo de vía, qué suelo corresponde a
cada ``surface``, cómo se llama en español cada tipo de lugar y qué medidas
típicas tiene cada obstáculo. Son las mismas ideas del proyecto de ciudades
del autor, reducidas a lo que cabe en un recuadro de unas pocas calles.

Los nombres van marcados con ``N_`` y se traducen al usarlos.
"""

from __future__ import annotations

from app.core.i18n import N_
from app.exportar.fichas import DESCONOCIDO, NO, SI

# ── Vías ─────────────────────────────────────────────────────────────────────

# highway → (nombre, ancho de calzada, tráfico 0-3, velocidad km/h, carriles por defecto).
# Son estimaciones por tipo de vía: se usan solo cuando el mapa no da el dato.
VIAS_RODADAS: dict[str, tuple[str, float, int, float, int]] = {
	"motorway": (N_("autopista"), 14.0, 3, 100.0, 4),
	"trunk": (N_("vía rápida"), 12.0, 3, 80.0, 4),
	"primary": (N_("avenida principal"), 10.0, 3, 50.0, 2),
	"secondary": (N_("calle principal"), 9.0, 2, 50.0, 2),
	"tertiary": (N_("calle de barrio"), 7.5, 2, 30.0, 2),
	"unclassified": (N_("calle"), 6.0, 1, 30.0, 2),
	"residential": (N_("calle residencial"), 6.0, 1, 30.0, 2),
	"living_street": (N_("calle de coexistencia"), 5.0, 1, 20.0, 1),
	"service": (N_("vía de servicio"), 4.0, 1, 20.0, 1),
	"road": (N_("calle"), 6.0, 1, 30.0, 2),
	"busway": (N_("carril de autobuses"), 3.5, 1, 30.0, 1),
}
ANCHO_CARRIL = 3.2

# Tipos de vía en los que, si el mapa no dice nada de aceras, se supone que las hay.
VIAS_CON_ACERA_SUPUESTA = frozenset({"primary", "secondary", "tertiary", "unclassified", "residential", "road"})

# highway → (nombre, anchura, tipo de espacio, suelo). Vías sin calzada para coches.
VIAS_PEATONALES: dict[str, tuple[str, float, str, str]] = {
	"footway": (N_("Camino peatonal"), 2.0, "sendero", "acera"),
	"path": (N_("Sendero"), 1.5, "sendero", "tierra"),
	"pedestrian": (N_("Calle peatonal"), 5.0, "plaza", "adoquin"),
	"steps": (N_("Escaleras"), 2.0, "escalera", "hormigon"),
	"cycleway": (N_("Carril bici"), 2.0, "sendero", "asfalto"),
	"track": (N_("Camino"), 3.0, "sendero", "tierra"),
	"bridleway": (N_("Camino de herradura"), 2.0, "sendero", "tierra"),
	"corridor": (N_("Pasillo"), 2.0, "sendero", "baldosa"),
}

# Vías que no existen todavía o ya no existen: no se importan.
VIAS_DESCARTADAS = frozenset({"proposed", "construction", "abandoned", "disused", "razed", "planned", "dismantled", "no"})

# surface → suelo del modelo.
SUELOS_SUPERFICIE: dict[str, str] = {
	"asphalt": "asfalto",
	"chipseal": "asfalto",
	"concrete": "hormigon",
	"concrete:lanes": "hormigon",
	"paved": "hormigon",
	"concrete:plates": "baldosa",
	"paving_stones": "baldosa",
	"paving_stones:lanes": "baldosa",
	"tiles": "baldosa",
	"marble": "baldosa",
	"brick": "baldosa",
	"bricks": "baldosa",
	"sett": "adoquin",
	"cobblestone": "adoquin",
	"unhewn_cobblestone": "adoquin",
	"stone": "adoquin",
	"rock": "adoquin",
	"pebblestone": "grava",
	"gravel": "grava",
	"fine_gravel": "grava",
	"ground": "tierra",
	"dirt": "tierra",
	"earth": "tierra",
	"compacted": "tierra",
	"unpaved": "tierra",
	"clay": "tierra",
	"mud": "tierra",
	"sand": "arena",
	"grass": "hierba",
	"grass_paver": "hierba",
	"artificial_turf": "hierba",
	"wood": "madera",
	"metal": "metal",
	"metal_grid": "metal",
	"rubber": "moqueta",
	"tartan": "moqueta",
	"carpet": "moqueta",
}

# ── Edificios ────────────────────────────────────────────────────────────────

EDIFICIOS: dict[str, str] = {
	"yes": N_("edificio"),
	"apartments": N_("edificio de viviendas"),
	"residential": N_("edificio de viviendas"),
	"house": N_("casa"),
	"detached": N_("casa"),
	"semidetached_house": N_("casa adosada"),
	"terrace": N_("casas adosadas"),
	"commercial": N_("edificio comercial"),
	"retail": N_("edificio de tiendas"),
	"office": N_("edificio de oficinas"),
	"industrial": N_("nave industrial"),
	"warehouse": N_("almacén"),
	"school": N_("colegio"),
	"university": N_("edificio universitario"),
	"college": N_("centro de estudios"),
	"kindergarten": N_("escuela infantil"),
	"hospital": N_("hospital"),
	"church": N_("iglesia"),
	"cathedral": N_("catedral"),
	"chapel": N_("capilla"),
	"mosque": N_("mezquita"),
	"synagogue": N_("sinagoga"),
	"public": N_("edificio público"),
	"civic": N_("edificio público"),
	"government": N_("edificio oficial"),
	"train_station": N_("estación de tren"),
	"transportation": N_("edificio de transporte"),
	"hotel": N_("hotel"),
	"supermarket": N_("supermercado"),
	"garage": N_("garaje"),
	"garages": N_("garajes"),
	"parking": N_("aparcamiento"),
	"kiosk": N_("quiosco"),
	"shed": N_("caseta"),
	"hut": N_("caseta"),
	"service": N_("caseta de servicios"),
	"sports_centre": N_("polideportivo"),
	"sports_hall": N_("pabellón deportivo"),
}
# Edificios que no son un bloque macizo: tienen techo pero se pasa por debajo.
EDIFICIOS_ABIERTOS = frozenset({"roof", "carport", "canopy", "grandstand"})

ENTRADAS: dict[str, str] = {
	"yes": N_("Entrada"),
	"main": N_("Entrada principal"),
	"secondary": N_("Entrada secundaria"),
	"service": N_("Entrada de servicio"),
	"staircase": N_("Portal"),
	"home": N_("Puerta de la vivienda"),
	"garage": N_("Entrada de garaje"),
	"emergency": N_("Salida de emergencia"),
	"exit": N_("Salida"),
	"shop": N_("Entrada de la tienda"),
}

# ── Áreas ────────────────────────────────────────────────────────────────────

# (clave, valor) → (tipo de espacio, nombre, suelo o "" para el de serie del tipo).
AREAS: dict[tuple[str, str], tuple[str, str, str]] = {
	("place", "square"): ("plaza", N_("Plaza"), ""),
	("highway", "pedestrian"): ("plaza", N_("Zona peatonal"), ""),
	("highway", "footway"): ("plaza", N_("Zona peatonal"), "acera"),
	("leisure", "park"): ("parque", N_("Parque"), ""),
	("leisure", "garden"): ("parque", N_("Jardín"), ""),
	("leisure", "playground"): ("parque", N_("Parque infantil"), "arena"),
	("leisure", "dog_park"): ("parque", N_("Parque para perros"), "tierra"),
	("leisure", "pitch"): ("exterior", N_("Pista deportiva"), "hormigon"),
	("landuse", "grass"): ("parque", N_("Zona de césped"), ""),
	("landuse", "village_green"): ("parque", N_("Zona verde"), ""),
	("landuse", "flowerbed"): ("parque", N_("Parterre"), "tierra"),
	("landuse", "meadow"): ("parque", N_("Prado"), ""),
	("landuse", "forest"): ("parque", N_("Arbolado"), "tierra"),
	("natural", "wood"): ("parque", N_("Arbolado"), "tierra"),
	("natural", "scrub"): ("parque", N_("Matorral"), "tierra"),
	("natural", "water"): ("exterior", N_("Agua"), "agua"),
	("natural", "sand"): ("exterior", N_("Arenal"), "arena"),
	("natural", "beach"): ("exterior", N_("Playa"), "arena"),
	("amenity", "fountain"): ("exterior", N_("Fuente"), "agua"),
	("leisure", "swimming_pool"): ("exterior", N_("Piscina"), "agua"),
	("amenity", "parking"): ("exterior", N_("Aparcamiento"), "asfalto"),
	("public_transport", "platform"): ("exterior", N_("Andén"), "baldosa"),
	("railway", "platform"): ("exterior", N_("Andén"), "baldosa"),
	("highway", "platform"): ("exterior", N_("Andén"), "baldosa"),
}
# Claves en el orden en que se miran (un parque con una fuente dentro es un parque).
CLAVES_AREA = ("place", "highway", "leisure", "amenity", "natural", "landuse", "public_transport", "railway")

# ── Barreras ─────────────────────────────────────────────────────────────────

# barrier (línea) → (nombre, material de pared, altura típica, tapa el sonido).
BARRERAS_LINEA: dict[str, tuple[str, str, float, bool]] = {
	"wall": (N_("Muro"), "piedra", 2.0, True),
	"city_wall": (N_("Muralla"), "piedra", 6.0, True),
	"retaining_wall": (N_("Muro de contención"), "hormigon", 1.5, True),
	"fence": (N_("Valla"), "valla", 1.5, False),
	"railing": (N_("Barandilla"), "valla", 1.0, False),
	"handrail": (N_("Barandilla"), "valla", 1.0, False),
	"guard_rail": (N_("Quitamiedos"), "metal", 0.8, False),
	"hedge": (N_("Seto"), "seto", 1.2, False),
	"jersey_barrier": (N_("Barrera de hormigón"), "hormigon", 0.9, False),
	"chain": (N_("Cadena"), "metal", 0.6, False),
	"yes": (N_("Barrera"), "valla", 1.2, False),
}

# barrier en un nodo que es un paso por una barrera: (nombre, anchura del hueco).
PUERTAS_DE_BARRERA: dict[str, tuple[str, float]] = {
	"gate": (N_("Cancela"), 1.2),
	"lift_gate": (N_("Barrera levadiza"), 3.0),
	"swing_gate": (N_("Barrera giratoria"), 3.0),
	"wicket_gate": (N_("Portillo"), 0.9),
	"kissing_gate": (N_("Paso de portillo"), 0.9),
	"turnstile": (N_("Torniquete"), 0.7),
	"entrance": (N_("Hueco en la barrera"), 1.2),
	"sliding_gate": (N_("Puerta corredera"), 3.0),
}

# (clave, valor) de un nodo → (objeto del complemento «calle», nombre, ancho, fondo, alto).
# El primer dato es el identificador del objeto en el complemento «calle» (o «complemento/objeto»
# si es de otro); si ese objeto no está instalado se usa una caja con las medidas típicas de
# la tabla, que el profesional ajusta si las reales son otras.
OBSTACULOS: dict[tuple[str, str], tuple[str, str, float, float, float]] = {
	("barrier", "bollard"): ("bolardo", N_("Bolardo"), 0.2, 0.2, 0.9),
	("barrier", "block"): ("bloque", N_("Bloque de hormigón"), 0.8, 0.8, 0.6),
	("barrier", "planter"): ("jardinera", N_("Jardinera"), 1.0, 1.0, 0.6),
	("barrier", "cycle_barrier"): ("barrera_bicis", N_("Barrera para bicicletas"), 1.5, 0.3, 1.0),
	("barrier", "stile"): ("paso_valla", N_("Paso sobre la valla"), 1.0, 0.5, 1.0),
	("barrier", "log"): ("tronco", N_("Tronco"), 2.0, 0.4, 0.4),
	("barrier", "debris"): ("escombros", N_("Escombros"), 1.5, 1.5, 0.5),
	("highway", "street_lamp"): ("farola", N_("Farola"), 0.25, 0.25, 6.0),
	("man_made", "utility_pole"): ("poste_luz", N_("Poste"), 0.3, 0.3, 8.0),
	("man_made", "flagpole"): ("mastil", N_("Mástil"), 0.2, 0.2, 8.0),
	("man_made", "street_cabinet"): ("armario_servicios", N_("Armario de registro"), 0.8, 0.4, 1.2),
	("power", "pole"): ("poste_luz", N_("Poste de la luz"), 0.3, 0.3, 8.0),
	("natural", "tree"): ("alcorque", N_("Árbol"), 0.5, 0.5, 6.0),
	("amenity", "bench"): ("banco", N_("Banco"), 1.8, 0.6, 0.45),
	("amenity", "waste_basket"): ("papelera", N_("Papelera"), 0.4, 0.4, 0.9),
	("amenity", "post_box"): ("buzon", N_("Buzón"), 0.5, 0.5, 1.4),
	("amenity", "telephone"): ("cabina", N_("Cabina de teléfono"), 0.9, 0.9, 2.2),
	("amenity", "vending_machine"): ("transporte/vending", N_("Máquina expendedora"), 0.9, 0.8, 1.8),
	("amenity", "recycling"): ("contenedor_envases", N_("Contenedor"), 1.6, 1.2, 1.5),
	("amenity", "waste_disposal"): ("contenedor_resto", N_("Contenedor"), 1.6, 1.2, 1.5),
	("amenity", "bicycle_parking"): ("aparcabicis", N_("Aparcabicicletas"), 2.0, 0.6, 0.8),
	("amenity", "parking_meter"): ("parquimetro", N_("Parquímetro"), 0.4, 0.3, 1.5),
	("advertising", "column"): ("columna_anuncios", N_("Columna de anuncios"), 1.2, 1.2, 3.0),
	("amenity", "drinking_water"): ("fuente_beber", N_("Fuente para beber"), 0.4, 0.4, 1.0),
	("emergency", "fire_hydrant"): ("hidrante", N_("Boca de incendios"), 0.3, 0.3, 0.8),
	("tourism", "information"): ("totem", N_("Panel de información"), 1.0, 0.2, 2.0),
}
COMPLEMENTO_CALLE = "calle"

# ── Lugares (puntos de interés) ──────────────────────────────────────────────

# (clave, valor) → (tipo de referencia, nombre en español).
LUGARES: dict[tuple[str, str], tuple[str, str]] = {
	("amenity", "pharmacy"): ("comercio", N_("farmacia")),
	("amenity", "bank"): ("comercio", N_("banco")),
	("amenity", "atm"): ("punto", N_("cajero automático")),
	("amenity", "cafe"): ("comercio", N_("cafetería")),
	("amenity", "bar"): ("comercio", N_("bar")),
	("amenity", "pub"): ("comercio", N_("bar")),
	("amenity", "restaurant"): ("comercio", N_("restaurante")),
	("amenity", "fast_food"): ("comercio", N_("comida rápida")),
	("amenity", "ice_cream"): ("comercio", N_("heladería")),
	("amenity", "post_office"): ("punto", N_("oficina de correos")),
	("amenity", "police"): ("punto", N_("comisaría")),
	("amenity", "fire_station"): ("punto", N_("parque de bomberos")),
	("amenity", "hospital"): ("punto", N_("hospital")),
	("amenity", "clinic"): ("punto", N_("centro de salud")),
	("amenity", "doctors"): ("punto", N_("consulta médica")),
	("amenity", "dentist"): ("punto", N_("dentista")),
	("amenity", "veterinary"): ("punto", N_("veterinario")),
	("amenity", "school"): ("punto", N_("colegio")),
	("amenity", "kindergarten"): ("punto", N_("escuela infantil")),
	("amenity", "university"): ("punto", N_("universidad")),
	("amenity", "college"): ("punto", N_("centro de estudios")),
	("amenity", "library"): ("punto", N_("biblioteca")),
	("amenity", "townhall"): ("punto", N_("ayuntamiento")),
	("amenity", "community_centre"): ("punto", N_("centro cívico")),
	("amenity", "social_facility"): ("punto", N_("centro de servicios sociales")),
	("amenity", "place_of_worship"): ("punto", N_("lugar de culto")),
	("amenity", "marketplace"): ("comercio", N_("mercado")),
	("amenity", "cinema"): ("punto", N_("cine")),
	("amenity", "theatre"): ("punto", N_("teatro")),
	("amenity", "toilets"): ("punto", N_("aseos públicos")),
	("amenity", "drinking_water"): ("punto", N_("fuente de agua potable")),
	("amenity", "fountain"): ("punto", N_("fuente")),
	("amenity", "fuel"): ("comercio", N_("gasolinera")),
	("amenity", "taxi"): ("parada", N_("parada de taxis")),
	("amenity", "bus_station"): ("parada", N_("estación de autobuses")),
	("amenity", "clock"): ("punto", N_("reloj")),
	("amenity", "shelter"): ("mobiliario", N_("refugio")),
	("tourism", "hotel"): ("comercio", N_("hotel")),
	("tourism", "hostel"): ("comercio", N_("albergue")),
	("tourism", "museum"): ("punto", N_("museo")),
	("tourism", "artwork"): ("punto", N_("obra de arte")),
	("tourism", "attraction"): ("punto", N_("lugar de interés")),
	("leisure", "sports_centre"): ("punto", N_("polideportivo")),
	("leisure", "fitness_centre"): ("comercio", N_("gimnasio")),
	("leisure", "swimming_pool"): ("punto", N_("piscina")),
	("historic", "memorial"): ("punto", N_("monumento conmemorativo")),
	("historic", "monument"): ("punto", N_("monumento")),
	("shop", "supermarket"): ("comercio", N_("supermercado")),
	("shop", "convenience"): ("comercio", N_("tienda de alimentación")),
	("shop", "bakery"): ("comercio", N_("panadería")),
	("shop", "butcher"): ("comercio", N_("carnicería")),
	("shop", "greengrocer"): ("comercio", N_("frutería")),
	("shop", "seafood"): ("comercio", N_("pescadería")),
	("shop", "kiosk"): ("comercio", N_("quiosco")),
	("shop", "newsagent"): ("comercio", N_("quiosco de prensa")),
	("shop", "lottery"): ("comercio", N_("administración de lotería")),
	("shop", "tobacco"): ("comercio", N_("estanco")),
	("shop", "hairdresser"): ("comercio", N_("peluquería")),
	("shop", "clothes"): ("comercio", N_("tienda de ropa")),
	("shop", "shoes"): ("comercio", N_("zapatería")),
	("shop", "optician"): ("comercio", N_("óptica")),
	("shop", "chemist"): ("comercio", N_("droguería")),
	("shop", "hardware"): ("comercio", N_("ferretería")),
	("shop", "books"): ("comercio", N_("librería")),
	("shop", "stationery"): ("comercio", N_("papelería")),
	("shop", "florist"): ("comercio", N_("floristería")),
	("shop", "laundry"): ("comercio", N_("lavandería")),
	("shop", "mall"): ("comercio", N_("centro comercial")),
	("shop", "department_store"): ("comercio", N_("grandes almacenes")),
	("shop", "bicycle"): ("comercio", N_("tienda de bicicletas")),
	("shop", "mobile_phone"): ("comercio", N_("tienda de telefonía")),
	("healthcare", "pharmacy"): ("comercio", N_("farmacia")),
	("healthcare", "hospital"): ("punto", N_("hospital")),
	("healthcare", "clinic"): ("punto", N_("centro de salud")),
	("office", "government"): ("punto", N_("oficina de la administración")),
	("emergency", "defibrillator"): ("punto", N_("desfibrilador")),
	("emergency", "phone"): ("punto", N_("teléfono de emergencia")),
}
# Claves cuyo valor desconocido también cuenta como lugar si tiene nombre: (tipo, plantilla del nombre).
LUGARES_GENERICOS: dict[str, tuple[str, str]] = {
	"shop": ("comercio", N_("tienda")),
	"office": ("punto", N_("oficina")),
	"craft": ("comercio", N_("taller")),
	"healthcare": ("punto", N_("centro sanitario")),
}
# Lugares que se importan aunque no tengan nombre, porque sirven de referencia por sí mismos.
LUGARES_SIN_NOMBRE = frozenset(
	{
		("amenity", "pharmacy"),
		("amenity", "atm"),
		("amenity", "toilets"),
		("amenity", "drinking_water"),
		("amenity", "fountain"),
		("amenity", "taxi"),
		("amenity", "clock"),
		("amenity", "post_office"),
		("emergency", "defibrillator"),
		("emergency", "phone"),
		("shop", "kiosk"),
		("historic", "memorial"),
		("historic", "monument"),
	}
)
CLAVES_LUGAR = ("amenity", "shop", "tourism", "leisure", "healthcare", "office", "craft", "historic", "emergency")

# ── Transporte ───────────────────────────────────────────────────────────────

# (clave, valor) → nombre de la parada.
PARADAS: dict[tuple[str, str], str] = {
	("highway", "bus_stop"): N_("Parada de autobús"),
	("public_transport", "platform"): N_("Parada"),
	("public_transport", "stop_position"): N_("Parada"),
	("public_transport", "station"): N_("Estación"),
	("railway", "tram_stop"): N_("Parada de tranvía"),
	("railway", "station"): N_("Estación de tren"),
	("railway", "halt"): N_("Apeadero"),
	("railway", "subway_entrance"): N_("Boca de metro"),
	("amenity", "taxi"): N_("Parada de taxis"),
	("amenity", "bus_station"): N_("Estación de autobuses"),
}
MEDIOS_DE_PARADA: dict[str, str] = {
	"bus": N_("Parada de autobús"),
	"trolleybus": N_("Parada de trolebús"),
	"tram": N_("Parada de tranvía"),
	"train": N_("Andén de tren"),
	"subway": N_("Andén de metro"),
	"light_rail": N_("Parada de metro ligero"),
}

# ── Pasos de peatones ────────────────────────────────────────────────────────

BORDILLOS: dict[str, str] = {
	"lowered": N_("rebajado"),
	"flush": N_("a nivel, sin escalón"),
	"raised": N_("alto, con escalón"),
	"rolled": N_("redondeado"),
	"no": N_("sin bordillo"),
	"yes": N_("con bordillo"),
}
MARCAS_PASO: dict[str, str] = {
	"zebra": N_("de cebra"),
	"dots": N_("de puntos"),
	"dashes": N_("de líneas discontinuas"),
	"lines": N_("de líneas"),
	"ladder": N_("de escalera"),
	"surface": N_("suelo de otro color"),
	"no": N_("sin marcas"),
}

# Formas de cruce: clave estable → nombre.
FORMAS_CRUCE: dict[str, str] = {
	"t": N_("Cruce en T"),
	"y": N_("Cruce en Y"),
	"cruz": N_("Cruce en cruz"),
	"aspa": N_("Cruce en aspa"),
	"desalineado": N_("Cruce de cuatro calles desalineado"),
	"complejo": N_("Cruce complejo"),
	"rotonda": N_("Rotonda"),
}


def tres_estados(valor: str | None, afirmativos: tuple[str, ...] = ("yes",), negativos: tuple[str, ...] = ("no", "none")) -> str:
	"""«si», «no» o «desconocido» a partir del valor de una etiqueta.

	Es el corazón de la regla «nada inventado»: una etiqueta que falta no
	significa que la cosa no exista, solo que nadie la ha apuntado.
	"""
	if valor is None or valor == "":
		return DESCONOCIDO
	if valor in afirmativos:
		return SI
	if valor in negativos:
		return NO
	return DESCONOCIDO
