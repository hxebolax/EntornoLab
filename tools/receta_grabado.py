"""Tabla del paquete de sonidos «Grabado»: de qué grabación sale cada sonido y qué tramo se toma.

La usa ``tools/montar_paquete_grabado.py``. Aquí no se toca ningún audio: solo se dice, para cada
sonido del catálogo de EntornoLab, una de estas tres cosas:

- ``SONIDOS``: sale de una grabación. Se indica la colección, el fichero original, el tramo (``inicio``
  y ``duracion`` en segundos) y, si hace falta, los fundidos (``entrada``, ``salida``) o el fundido
  cruzado del bucle (``cruce``). Sin ``duracion`` se usa la del sonido de serie (obligado en los
  bucles, que deben durar exactamente lo mismo).
- ``FUNCIONALES``: **codifica información** (número de toques, notas que suben o bajan, ritmo) y una
  grabación no conserva ese código. No se sustituye: se hereda del paquete por defecto, a propósito.
- ``PENDIENTES``: no hay, entre lo descargado, una grabación de licencia clara que sirva. Se hereda del
  paquete por defecto y se apunta **qué habría que buscar** para completarlo.

Criterio de licencia. Solo entran colecciones cuya licencia consta y permite redistribuir en un
programa GPL que cualquiera descarga. Todas las usadas son **CC0 1.0** (dominio público). En
``constancia`` se dice dónde figura la licencia de cada una:

1. un fichero de licencia dentro de la propia colección, o un inventario del autor que da título,
   autor, licencia y página de cada grabación (BigSoundBank, las primeras de Freesound);
2. la página de OpenGameArt de la colección, leída el 26 de noviembre de 2026: «License(s): CC0» y su
   autor (los pasos de Fantozzi y las colecciones de rubberduck);
3. lo **descargado expresamente para este paquete** (colección ``freesound_2026``, ``"raiz":
   "descargadas"``): la página de Freesound de cada grabación dice «Creative Commons 0», y el
   ``inventario.json`` de ``adjuntos/fuentes_sonido`` (que no se sube al repositorio) guarda la página,
   el enlace de descarga, el autor, la licencia y el SHA-256 de cada fichero. Son las vistas previas de
   alta calidad (OGG), lo único que Freesound deja bajar sin iniciar sesión.

Lo descargado que **no** se usa por licencia: lo que no trae licencia ni está en ese inventario
(«MoreSounds», «SoundPack01», «all-in-one», «beeps», «Cardsounds», «GUI Sound Effects by Lokif» y las
páginas de OpenGameArt de ``oga2`` que no cita ``crear_packs.py``), y lo que es CC BY sin autor
identificable («Well Done»). «Footsteps on different surfaces» (OpenGameArt) es CC BY 3.0 y mezcla
grabaciones de varios autores de Freesound: no se usó.

Criterio de medida. Lo que se sitúa en el espacio necesita energía por encima de 3 kHz. Los pasos e
impactos de Kenney («Impact Sounds», «RPG Audio») no llegan (son golpes graves, casi sin agudos), así
que no se usan para eso aunque su licencia sea impecable: no se arregla una grabación añadiéndole
ruido ni ecualizándola. Tampoco se usa una grabación que contradiga la explicación que el catálogo
da del sonido (el menú «Aprender los sonidos» es común a todos los paquetes).
"""

from __future__ import annotations

ID = "grabado"

FICHA = {
	"id": ID,
	"nombre": "Grabado",
	"descripcion": (
		"Grabaciones reales de uso libre: pasos sobre doce suelos, golpes, roces, puertas, ascensor, agua, tráfico, "
		"máquinas y ambientes de calle, parque, casa, oficina, pasillo y cocina. "
		"Paquete parcial: los avisos que codifican información y lo que aún no tiene grabación suenan con el paquete por defecto."
	),
	"autor": (
		"Montado para EntornoLab con grabaciones CC0 de Fantozzi, Corsica_S, Kenney, rubberduck, BigSoundBank.com y de varios autores "
		"de Freesound (detalle en CREDITOS.txt)"
	),
	"licencia": "CC0 1.0 (dominio público) todas las grabaciones; origen y autor de cada una en CREDITOS.txt",
	"version": "1.1",
	"igualar": True,
}

_OGA = "https://opengameart.org/content/"
_ANOTADA = "anotada como CC0 por el autor de EntornoLab en herramientas/crear_packs.py de Puerto Bravo"
_RUBBERDUCK = "rubberduck"
_COMPROBADA = "comprobado en su página de OpenGameArt el 26 de noviembre de 2026"
_PAGINA_RUBBERDUCK = (
	f"su página de OpenGameArt dice «Author: rubberduck» y «License(s): CC0» ({_COMPROBADA}); el título también declara CC0"
)
_SIN_AUTOR = "no indicado en el inventario descargado (figura en la página de origen)"

# clave → carpeta dentro de la carpeta de los originales, nombre, autor, licencia, página de origen y dónde consta la licencia.
COLECCIONES: dict[str, dict[str, str]] = {
	"fantozzi": {
		"carpeta": "fuentes/Fantozzi-footsteps/Fantozzi-footsteps/flac",
		"nombre": "Fantozzi's Footsteps (Grass/Sand & Stone)",
		"autor": "Fantozzi",
		"licencia": "CC0 1.0",
		"origen": _OGA + "fantozzis-footsteps-grasssand-stone",
		"constancia": (
			"su página de OpenGameArt dice «Author: Fantozzi (Submitted by qubodup)» y «License(s): CC0», y que las tomas salen de un paquete "
			f"que Fantozzi publicó en Freesound con CC0 ({_COMPROBADA}); la colección no trae fichero de licencia"
		),
	},
	"corsica": {
		"carpeta": "fuentes/oga2/42-snow-and-gravel-footsteps/corsica_s-walking_in_snow/Corsica_S-Walking_in_Snow",
		"nombre": "42 snow and gravel footsteps",
		"autor": "Corsica_S (grabación), recortadas por Iwan Gabovitch (qubodup)",
		"licencia": "CC0 1.0",
		"origen": _OGA + "42-snow-and-gravel-footsteps",
		"constancia": "readme.txt de la colección: el autor dio permiso para publicarlas con CC0",
	},
	"kenney_rpg": {
		"carpeta": "fuentes/RPGsounds_Kenney/OGG",
		"nombre": "50 RPG sound effects (RPG Audio)",
		"autor": "Kenney Vleugels (www.kenney.nl)",
		"licencia": "CC0 1.0",
		"origen": _OGA + "50-rpg-sound-effects",
		"constancia": "license.txt de la colección",
	},
	"kenney_ui": {
		"carpeta": "fuentes/UI_SFX_Set",
		"nombre": "51 UI sound effects (UI Audio)",
		"autor": "Kenney Vleugels (www.kenney.nl)",
		"licencia": "CC0 1.0",
		"origen": _OGA + "51-ui-sound-effects-buttons-switches-and-clicks",
		"constancia": f"readme.txt de la colección (uso libre, personal y comercial, sin obligación de citar) y {_ANOTADA}",
	},
	"rd_v2": {
		"carpeta": "fuentes/sfx_100_v2",
		"nombre": "100 CC0 SFX #2",
		"autor": _RUBBERDUCK,
		"licencia": "CC0 1.0",
		"origen": _OGA + "100-cc0-sfx-2",
		"constancia": _PAGINA_RUBBERDUCK,
	},
	"rd_rpg": {
		"carpeta": "fuentes/80-CC0-RPG-SFX_0",
		"nombre": "80 CC0 RPG SFX",
		"autor": _RUBBERDUCK,
		"licencia": "CC0 1.0",
		"origen": _OGA + "80-cc0-rpg-sfx",
		"constancia": _PAGINA_RUBBERDUCK,
	},
	"rd_madera": {
		"carpeta": "fuentes/oga2/100-cc0-metal-and-wood-sfx/100-CC0-wood-metal-SFX",
		"nombre": "100 CC0 metal and wood SFX",
		"autor": _RUBBERDUCK,
		"licencia": "CC0 1.0",
		"origen": _OGA + "100-cc0-metal-and-wood-sfx",
		"constancia": _PAGINA_RUBBERDUCK,
	},
	"rd_agua": {
		"carpeta": "fuentes/water-splash-slime-sfx",
		"nombre": "40 CC0 water, splash, slime SFX",
		"autor": _RUBBERDUCK,
		"licencia": "CC0 1.0",
		"origen": _OGA + "40-cc0-water-splash-slime-sfx",
		"constancia": _PAGINA_RUBBERDUCK,
	},
	"reloj": {
		"carpeta": "fuentes/oga2/ticking-clock-0/ticking_clock",
		"nombre": "Ticking clock",
		"autor": "no indicado en la colección (figura en su página de OpenGameArt)",
		"licencia": "CC0 1.0",
		"origen": _OGA + "ticking-clock-0",
		"constancia": "LICENSE.txt de la colección (texto legal de CC0 1.0 Universal)",
	},
	"bsb": {
		"carpeta": "fuentes/bigsoundbank",
		"nombre": "BigSoundBank.com",
		"autor": "Joseph SARDIN y colaboradores de BigSoundBank.com",
		"licencia": "CC0 1.0",
		"origen": "https://bigsoundbank.com",
		"constancia": "LEEME.txt del autor junto a los originales: título y página de cada grabación, todas «CC0 (dominio público)»",
	},
	"bsb_171": {
		"carpeta": "fuentes/bigsoundbank_171",
		"nombre": "BigSoundBank.com (descargas de noviembre de 2026)",
		"autor": "Joseph SARDIN y colaboradores de BigSoundBank.com",
		"licencia": "CC0 1.0",
		"origen": "https://bigsoundbank.com",
		"constancia": "LEEME.txt del autor junto a los originales: en la página de cada una figura «License: CC0 (public domain)», leído el 18 de noviembre de 2026",
	},
	"freesound": {
		"carpeta": "packs/fuentes_envolvente",
		"nombre": "Freesound (vistas previas de alta calidad)",
		"autor": "varios; el de cada grabación va en su línea",
		"licencia": "CC0 1.0",
		"origen": "https://freesound.org",
		"constancia": "fuentes.json del autor junto a los originales: título, autor, licencia «CC0 1.0 (Creative Commons 0)» y página de cada grabación",
	},
	"freesound_2026": {
		"raiz": "descargadas",
		"carpeta": "freesound",
		"nombre": "Freesound (vistas previas de alta calidad descargadas para este paquete)",
		"autor": "varios; el de cada grabación va en su línea",
		"licencia": "CC0 1.0",
		"origen": "https://freesound.org",
		"constancia": (
			"en la página de Freesound de cada grabación figura «Creative Commons 0» (comprobado al descargarla y otra vez el 26 de noviembre "
			"de 2026); inventario.json de adjuntos/fuentes_sonido: página, enlace de descarga, autor, licencia y SHA-256 de cada fichero"
		),
	},
}

_FS = "https://freesound.org/people/"


def _fs(fichero: str, titulo: str, **resto) -> dict:
	"""Receta de una grabación de Freesound descargada para el paquete: ``fichero`` es ``<autor>/<id>_<título>.ogg``."""
	autor, nombre = fichero.split("/", 1)
	ident = nombre.split("_", 1)[0]
	return {
		"coleccion": "freesound_2026",
		"fichero": fichero,
		"titulo": titulo,
		"autor": autor,
		"origen": f"{_FS}{autor}/sounds/{ident}/",
		**resto,
	}


SUELOS_GRABADOS = ("acera", "grava", "arena", "agua", "baldosa", "madera", "alfombra", "hormigon", "asfalto", "tierra", "hierba", "metal")

# suelo → (fichero, título en Freesound, duración de cada pisada, los seis inicios elegidos, nota).
# Las seis pisadas de cada suelo son, de entre las que tienen más de un 3 % de energía por encima de
# 3 kHz, las seis más parecidas a la mediana de su perfil: así varían poco entre sí y se separan de
# los demás suelos (lo mide ``montar_paquete_grabado.py --comparar``). Pie izquierdo y derecho, alternos.
_PASOS_FREESOUND: dict[str, tuple[str, str, float, tuple[float, ...], str]] = {
	"baldosa": (
		"SpliceSound/170500_Footsteps_Tile_Male_Tennis_Shoes_Medium_Pace.ogg",
		"Footsteps, Tile, Male Tennis Shoes, Medium Pace.wav",
		0.24,
		(2.085, 3.584, 6.142, 14.975, 15.504, 16.523),
		"Zapatillas de tenis sobre baldosa.",
	),
	"madera": (
		"vicleb/712874_High_heels_on_wood.ogg",
		"High heels on wood",
		0.33,
		(7.338, 8.714, 9.208, 12.048, 14.172, 14.519),
		"Tacones sobre suelo de madera: las pisadas con zapato plano que se encontraron no tienen agudos.",
	),
	"alfombra": (
		"SpliceSound/260115_01-25_Footsteps__Rug__Slippers__Medium_Pace.ogg",
		"01-25 Footsteps, Rug, Slippers, Medium Pace.wav",
		0.35,
		(0.626, 9.201, 11.435, 12.018, 15.378, 15.895),
		"Zapatillas de casa sobre una alfombra.",
	),
	"hormigon": (
		"florianreichelt/459964_Footsteps_on_concrete.ogg",
		"Footsteps on concrete",
		0.26,
		(3.294, 3.656, 7.867, 11.765, 12.682, 19.192),
		"",
	),
	"asfalto": (
		"Rimmer/648336_Walking_asphalt.ogg",
		"Walking asphalt.wav",
		0.27,
		(0.528, 2.089, 3.335, 4.336, 9.988, 11.607),
		"La grabación es de dos personas que caminan casi al paso; se toman pisadas sueltas.",
	),
	"tierra": (
		"kyles/637550_footsteps_shoes_dirt_walk.ogg",
		"footsteps shoes dirt walk.flac",
		0.33,
		(4.175, 5.373, 5.959, 14.19, 15.255, 18.436),
		"",
	),
	"hierba": (
		"Nox_Sound/556042_Footsteps_Mountain_Boots_Grass_Mono.ogg",
		"Footsteps_Mountain_Boots_Grass_Mono.wav",
		0.38,
		(18.864, 21.321, 25.273, 26.573, 30.03, 39.579),
		"Botas de montaña sobre hierba.",
	),
	"metal": (
		"SoftDistortionFX/398937_Metal_Footsteps.ogg",
		"Metal Footsteps",
		0.47,
		(19.073, 22.05, 39.474, 45.539, 61.742, 82.731),
		"Zapatos de suela dura sobre una rejilla metálica.",
	),
	"agua": (
		"patchytherat/531566_puddle_footsteps.ogg",
		"puddle footsteps.wav",
		0.4,
		(1.885, 2.68, 4.873, 5.452, 6.246, 8.027),
		"Seis pisadas distintas en un charco (antes, tres tomas repetidas en los dos pies).",
	),
}


def _pasos() -> dict[str, dict]:
	"""Los pasos: seis por suelo (tres por pie), de colecciones grabadas pisando ese suelo."""
	tabla: dict[str, dict] = {}
	# Fantozzi grabó cada pie por separado: la toma L va al pie izquierdo y la R al derecho.
	for suelo, material, duracion, nota in (
		("arena", "Sand", 0.42, None),
		("acera", "Stone", 0.24, "Pisada sobre losa de piedra; se corta a 0,24 s (la de serie dura 0,14) con un fundido final de 40 ms."),
	):
		for pie, letra in (("izq", "L"), ("der", "R")):
			for variante in (1, 2, 3):
				entrada: dict = {
					"coleccion": "fantozzi",
					"fichero": f"Fantozzi-{material}{letra}{variante}.flac",
					"duracion": duracion,
					"salida": 0.04,
				}
				if nota:
					entrada["nota"] = nota
				tabla[f"pasos/{suelo}_{pie}_{variante}"] = entrada
	# De las 42 tomas de Corsica_S se usan las seis con más agudos (grava con hielo: las piedrecillas crujen más).
	tomas_grava = {"izq": ("17", "18", "20"), "der": ("05", "04", "21")}
	for pie, tomas in tomas_grava.items():
		for variante, toma in enumerate(tomas, start=1):
			tabla[f"pasos/grava_{pie}_{variante}"] = {
				"coleccion": "corsica",
				"fichero": f"Corsica_S-Walking_on_snow_covered_gravel_and_ice_{toma}.flac",
				"duracion": 0.46,
				"salida": 0.08,
				"nota": "Grava cubierta de nieve y hielo: cruje como la grava suelta, algo más amortiguada. Se corta a 0,46 s.",
			}
	# Los demás suelos, de grabaciones de Freesound (CC0): seis pisadas de una misma grabación.
	for suelo, (fichero, titulo, duracion, inicios, nota) in _PASOS_FREESOUND.items():
		for orden, inicio in enumerate(inicios):
			pie = "izq" if orden % 2 == 0 else "der"
			extra = {"nota": nota} if nota else {}
			tabla[f"pasos/{suelo}_{pie}_{orden // 2 + 1}"] = _fs(fichero, titulo, inicio=inicio, duracion=duracion, **extra)
	return tabla


SONIDOS: dict[str, dict] = {
	**_pasos(),
	# Golpes: un impacto por material, recortado a lo que dura el de serie.
	"golpe/madera": {"coleccion": "rd_madera", "fichero": "wood_hit_03.ogg", "duracion": 0.4},
	"golpe/metal": {"coleccion": "rd_v2", "fichero": "sfx100v2_metal_hit_01.ogg", "duracion": 0.8, "salida": 0.1},
	"golpe/cristal": {"coleccion": "rd_v2", "fichero": "sfx100v2_glass_02.ogg", "duracion": 0.62, "salida": 0.08},
	"golpe/piedra": {"coleccion": "rd_v2", "fichero": "sfx100v2_stones_02.ogg", "duracion": 0.5, "salida": 0.06},
	"golpe/ladrillo": _fs("Alexbuk/391765_BRICK_taps_and_hits.ogg", "BRICK taps and hits.wav", inicio=1.1, duracion=0.3, salida=0.05),
	"roce/tela": {"coleccion": "kenney_rpg", "fichero": "cloth4.ogg", "duracion": 0.38, "ataque": False, "entrada": 0.01, "salida": 0.05},
	# Roces: un tramo del arrastre, con fundidos suaves porque no empiezan con un golpe.
	"roce/ladrillo": _fs("Alexbuk/391764_Brick_scrapes.ogg", "Brick scrapes.wav", inicio=4.7, duracion=0.45, entrada=0.02, salida=0.06),
	"roce/madera": _fs(
		"dvandevorst/568914_rubbed_wood_on_wood.ogg",
		"rubbed wood on wood.wav",
		inicio=1.9,
		duracion=0.45,
		entrada=0.02,
		salida=0.06,
		nota="Un trozo de madera frotado contra otro.",
	),
	"roce/metal": _fs(
		"ocramrudiger/832547_Hitting_and_rubbing_a_metallic_railing.ogg",
		"Hitting and rubbing a metallic railing",
		inicio=2.4,
		duracion=0.45,
		ataque=False,
		entrada=0.02,
		salida=0.06,
		nota="Tramo del frotado de una barandilla (la grabación empieza con golpes), grabado con micrófono de contacto.",
	),
	"roce/cristal": _fs(
		"trexlasso/630007_SLIDING_ON_GLASS.ogg", "SLIDING ON GLASS.wav", inicio=0.25, duracion=0.45, entrada=0.02, salida=0.06
	),
	"roce/plastico": _fs(
		"newagesoup/369121_VSH-53-plastic-hand-rub-squeak-short.ogg",
		"VSH-53-plastic-hand-rub-squeak-short.wav",
		inicio=0.55,
		duracion=0.45,
		entrada=0.02,
		salida=0.06,
		nota="Mano frotando un objeto de plástico; el autor dice haberle aplicado ecualización y compresión.",
	),
	"eco/chasquido": _fs("fleurescence/573148_tongue_click.ogg", "tongue click", duracion=0.06, salida=0.015),
	# Puertas.
	"puerta/abrir": {"coleccion": "kenney_rpg", "fichero": "doorOpen_1.ogg", "duracion": 0.9, "salida": 0.06},
	"puerta/cerrar": {"coleccion": "kenney_rpg", "fichero": "doorClose_1.ogg", "duracion": 0.66, "salida": 0.06},
	"puerta/con_llave": _fs(
		"CastIronCarousel/216871_Locked_doorknob_rattle_1.ogg",
		"Locked doorknob rattle 1.wav",
		duracion=0.9,
		salida=0.08,
		nota="La manilla de una puerta cerrada con llave que se prueba y no cede.",
	),
	"puerta/automatica": _fs(
		"Stroms/369500_Automatic_Door.ogg",
		"Automatic Door.wav",
		duracion=1.05,
		salida=0.15,
		nota="Puerta corredera de cristal que se abre sola.",
	),
	"ascensor/puerta": _fs(
		"Rshai/202604_Opening_an_elevator_door_sample.ogg", "Opening an elevator door sample.wav", duracion=2.2, salida=0.1
	),
	"ascensor/viaje": _fs(
		"JoanCalsina/867597_Subtle_quiet_elevator_ride.ogg",
		"Subtle quiet elevator ride",
		inicio=11.0,
		cruce=0.5,
		nota="Tramo del viaje, lejos del timbre y de la puerta del final.",
	),
	# Premios.
	"premio/recogido": _fs("LamaMakesMusic/403573_Coins_Table_Short.ogg", "Coins_Table_Short.ogg", duracion=0.55, salida=0.08),
	# Menús: clics de verdad, sin notas. El borde, el más grave; el ajuste, el más agudo.
	"interfaz/mover": {
		"coleccion": "kenney_ui",
		"fichero": "click5.wav",
		"duracion": 0.03,
		"ataque": False,
		"entrada": 0.001,
		"salida": 0.008,
	},
	"interfaz/borde": {
		"coleccion": "kenney_ui",
		"fichero": "click2.wav",
		"duracion": 0.06,
		"ataque": False,
		"entrada": 0.001,
		"salida": 0.015,
	},
	"interfaz/ajuste": {
		"coleccion": "kenney_ui",
		"fichero": "switch13.wav",
		"duracion": 0.03,
		"ataque": False,
		"entrada": 0.001,
		"salida": 0.008,
	},
	# Tráfico.
	"trafico/autobus": {
		"coleccion": "bsb",
		"fichero": "motor_camion_1442.wav",
		"titulo": "Moteur de camion #1",
		"autor": _SIN_AUTOR,
		"origen": "https://bigsoundbank.com/moteur-de-camion-1-s1442.html",
		"inicio": 3.0,
		"duracion": 4.5,
		"ataque": False,
		"entrada": 0.9,
		"salida": 1.3,
		"nota": "Es el motor diésel de un camión, no un autobús, y no trae el soplido de frenos del final. La entrada y la salida largas hacen de «llega y se va».",
	},
	"trafico/coche": _fs(
		"Breviceps/462862_Passing_Car__Wet_road.ogg",
		"Passing Car (Wet road)",
		inicio=0.3,
		duracion=4.5,
		ataque=False,
		entrada=0.6,
		salida=1.0,
		nota="Un coche que pasa a unos 100 km/h por una calzada mojada.",
	),
	"trafico/moto": _fs(
		"kyles/450698_scooter_pass_by_medium_speed_echo_off_building.ogg",
		"scooter pass by medium speed echo off building.flac",
		inicio=4.6,
		duracion=4.5,
		ataque=False,
		entrada=0.9,
		salida=1.2,
		nota="Un ciclomotor que llega y pasa; se corta cuando se aleja.",
	),
	"trafico/ambiente_leve": {
		"coleccion": "bsb",
		"fichero": "calle_1713.wav",
		"titulo": "Petite rue parisienne",
		"autor": _SIN_AUTOR,
		"origen": "https://bigsoundbank.com/petite-rue-parisienne-s1713.html",
		"inicio": 3.0,
		"cruce": 0.6,
	},
	"trafico/ambiente_medio": {
		"coleccion": "freesound",
		"fichero": "amb_ciudad.ogg",
		"titulo": "Day Traffic - City Life",
		"autor": "Liljendal",
		"origen": "https://freesound.org/people/Liljendal/sounds/442636/",
		"inicio": 18.0,
		"cruce": 0.6,
		"nota": "Se parte de la vista previa de alta calidad de Freesound (OGG, con pérdida), no del original.",
	},
	"trafico/ambiente_intenso": {
		"coleccion": "rd_v2",
		"fichero": "sfx100v2_loop_highway.ogg",
		"inicio": 3.5,
		"cruce": 0.6,
		"nota": "El original tiene dos canales iguales: es estéreo de formato, sin anchura.",
	},
	# Cosas que suenan en los lugares (bucles mono que se sitúan).
	"fuente/frigorifico": {
		"coleccion": "bsb_171",
		"fichero": "nevera/nevera_motor_0034.wav",
		"titulo": "Refrigerator",
		"autor": _SIN_AUTOR,
		"origen": "https://bigsoundbank.com/refrigerator-s0034.html",
		"inicio": 0.5,
		"cruce": 0.5,
	},
	"fuente/reloj": {
		"coleccion": "reloj",
		"fichero": "clock-1.wav",
		"inicio": 0.05,
		"cruce": 0.1,
		"nota": "Dos segundos de un reloj que da un golpe por segundo; el cruce cae en el silencio entre dos golpes.",
	},
	"fuente/maquina_expendedora": _fs(
		"Filmscore/825404_Vending_Machines_in_Hotel.ogg",
		"Vending Machines in Hotel",
		inicio=24.0,
		cruce=0.5,
		nota="El zumbido de unas máquinas expendedoras en la zona de un hotel.",
	),
	"fuente/grifo": {"coleccion": "rd_agua", "fichero": "loop_water_01.ogg", "inicio": 0.04, "cruce": 0.3},
	"fuente/fuente_agua": {"coleccion": "rd_v2", "fichero": "sfx100v2_loop_water_02.ogg", "inicio": 3.0, "cruce": 0.5},
	"fuente/campanas": {
		"coleccion": "bsb_171",
		"fichero": "barrio_perdido/campana_0135.wav",
		"titulo": "Church Bell",
		"autor": "Joseph SARDIN",
		"origen": "https://bigsoundbank.com/church-bell-s0135.html",
		"inicio": 7.72,
		"cruce": 0.25,
		"nota": "Dos campanadas seguidas de la grabación (a dos segundos una de otra) y la cola de la segunda: dos campanadas en cada vuelta de cinco segundos, como describe el catálogo.",
	},
	"fuente/pajaros": {
		"coleccion": "freesound",
		"fichero": "amb_residencial.ogg",
		"titulo": "Nõmme_Morning_June.wav",
		"autor": "Islabonita",
		"origen": "https://freesound.org/people/Islabonita/sounds/471070/",
		"inicio": 18.0,
		"cruce": 0.5,
		"nota": "Pájaros de un barrio al amanecer, pasados a mono. Vista previa de alta calidad de Freesound (OGG, con pérdida).",
	},
	# Ambientes (bucles estéreo de diez segundos).
	"ambiente/calle": {
		"coleccion": "bsb",
		"fichero": "pueblo_1347.wav",
		"titulo": "Village centre ville #2",
		"autor": _SIN_AUTOR,
		"origen": "https://bigsoundbank.com/village-centre-ville-2-s1347.html",
		"inicio": 4.5,
		"cruce": 0.6,
	},
	"ambiente/parque": {
		"coleccion": "freesound",
		"fichero": "amb_parque.ogg",
		"titulo": "St_Stephen's_Green_Ambiance_Dublin_04",
		"autor": "SignatureSoundsOrg",
		"origen": "https://freesound.org/people/SignatureSoundsOrg/sounds/869037/",
		"inicio": 5.5,
		"cruce": 0.6,
		"nota": "Vista previa de alta calidad de Freesound (OGG, con pérdida), no el original.",
	},
	"ambiente/casa": _fs(
		"leonelmail/329569_Roomtone_Bedroom_Yew.ogg",
		"Roomtone Bedroom Yew",
		inicio=5.0,
		cruce=0.6,
		nota="Tono de sala de un dormitorio tranquilo.",
	),
	"ambiente/oficina": _fs(
		"Chelly01/541117_Office_ambience.ogg",
		"Office ambience.wav",
		inicio=88.0,
		cruce=0.6,
		nota="Murmullo, papeles, máquinas y aire acondicionado de una oficina, en estéreo (X/Y).",
	),
	"ambiente/pasillo": _fs(
		"Sheyvan/570015_Ambience_Empty_Office_Hallway__Stereo.ogg", "Ambience Empty Office Hallway (Stereo)", inicio=10.0, cruce=0.6
	),
	"ambiente/cocina": _fs(
		"brunoboselli/512511_Kitchen_Ambience.ogg",
		"Kitchen Ambience",
		inicio=15.0,
		cruce=0.6,
		nota="Cubiertos, vasos y cacharros oídos desde media distancia; sin frigorífico de fondo.",
	),
}


def _funcionales() -> dict[str, str]:
	tabla: dict[str, str] = {}
	for clave in ("pulso", "alineado", "detras", "cerca", "llegada"):
		tabla[f"baliza/{clave}"] = "baliza de destino: su nota y su número de pulsos dicen si vas bien, si queda detrás o si has llegado"
	for clave in ("pared", "puerta", "objeto", "libre", "escalon", "bordillo"):
		tabla[f"sonda/{clave}"] = "bastón sonoro: cada hallazgo tiene su propio timbre y su propio dibujo de toques"
	for clave in ("cerca", "media", "lejos"):
		tabla[f"sonda/{clave}"] = "bastón sonoro: tres, dos y un pitido, cada vez más grave, dan la distancia"
	for clave in ("norte", "noreste", "este", "sureste", "sur", "suroeste", "oeste", "noroeste"):
		tabla[f"brujula/{clave}"] = "brújula: el rumbo va en el número de notas y en su altura"
	for planta in range(10):
		tabla[f"ascensor/planta_{planta}"] = "las diez plantas forman una escala: cada una, una nota más aguda que la anterior"
	tabla["ascensor/llamada"] = "un clic y un pitido: el pitido confirma la llamada"
	tabla["ascensor/llegada"] = "dos campanadas, la segunda más grave: es la señal de llegada"
	for clave in ("verde", "intermitente", "rojo"):
		tabla[f"semaforo/{clave}"] = "fases del semáforo sonoro: se distinguen por el ritmo de los píos"
	tabla["semaforo/pulsador"] = "un clic y dos pitidos que confirman la petición de verde"
	tabla["escalera/subir"] = "una pisada y dos notas que suben, cada peldaño un poco más agudo"
	tabla["escalera/bajar"] = "una pisada y dos notas que bajan, cada peldaño un poco más grave"
	tabla["escalera/rampa"] = "deslizamiento que el juego sube o baja de tono según subas o bajes"
	tabla["exterior/bordillo"] = "aviso de seguridad con forma fija: un raspado y un golpe grave"
	for patron, motivo in (
		("tactil_botones", "repique doble que avisa de un peligro"),
		("tactil_rayas", "raspado corto que marca un camino"),
	):
		for pie in ("izq", "der"):
			for variante in (1, 2, 3):
				tabla[f"pasos/{patron}_{pie}_{variante}"] = f"pavimento táctil: {motivo}; es un código, no el ruido de un suelo"
	for clave, motivo in (
		("elegir", "dos notas que suben"),
		("atras", "dos notas que bajan"),
		("abrir", "tres notas que suben"),
		("cerrar", "tres notas que bajan"),
	):
		tabla[f"interfaz/{clave}"] = f"menús: {motivo}"
	tabla["premio/aparece"] = "cinco tintineos que suben"
	tabla["premio/cerca"] = "centelleo que se repite desde el premio para ir hacia él"
	tabla["premio/tesoro"] = "una melodía que sube"
	tabla["logro/logro"] = "tres notas que suben"
	for estrellas in (1, 2, 3):
		tabla[f"logro/estrella_{estrellas}"] = "tantas notas como estrellas"
	tabla["logro/medalla"] = "fanfarria: una melodía"
	tabla["logro/error"] = "dos notas graves que bajan"
	tabla["logro/pista"] = "dos campanillas que suben"
	return tabla


FUNCIONALES: dict[str, str] = _funcionales()

_SIN_AGUDOS_FS = (
	"las grabaciones CC0 de Freesound que se descargaron y midieron ({}) no llegan al 2 % de energía por encima de 3 kHz "
	"en ninguna pisada: no se podrían situar"
)

# suelo → (motivo, cómo debe ser la pisada que hay que buscar, duración máxima en segundos)
_PASOS_PENDIENTES: dict[str, tuple[str, str, float]] = {
	"moqueta": (
		_SIN_AGUDOS_FS.format("alec_mackay, izzylikesnoise, hannagreen, theshuggie y LewisEmmott5; también las de Kenney"),
		"pisadas sobre moqueta: muy apagadas y cortas, pero con el roce de la suela audible",
		0.31,
	),
	"adoquin": (
		"no se encontró en Freesound ni en OpenGameArt una grabación CC0 de pisadas sobre adoquín; las de losa de piedra descargadas "
		"(kyles, xkeril, Fission9, niamhd00145229, SecureSubset) no tienen agudos en más de una pisada",
		"pisadas sobre adoquín o empedrado irregular: dos toques desiguales por paso",
		0.29,
	),
}

_OTROS_PENDIENTES: dict[str, tuple[str, str]] = {
	"golpe/plastico": (
		"lo descargado con licencia en regla no es un golpe: «Plastic» de Pipelenisf es una botella frotada y el golpe en un barreño de "
		"Sadiquecat no tiene nada por encima de 3 kHz",
		"un golpe contra un objeto hueco de plástico (un cubo, una caja): clac hueco y ligero; mono, de 0,15 a 0,5 s",
	),
	"golpe/tela": (
		"los golpes en almohada descargados (KoimeMatsuchiya, saturdaysoundguy) y los de Kenney no llegan al 2 % por encima de 3 kHz",
		"un golpe contra un cojín, un sofá o una cortina gruesa, con el roce de la tela audible; mono, de 0,15 a 0,5 s",
	),
	"roce/piedra": (
		"los raspados de piedra descargados (alegemaate, dslrguide) no llegan al 2 % por encima de 3 kHz",
		"una mano o un bastón rozando un muro de piedra: raspado duro y granulado; mono, de 0,2 a 0,7 s",
	),
	"fuente/ventilador": (
		"los ventiladores descargados (RealSquink, unfa, NorTEEN_X) son un zumbido sin agudos (menos del 1 % por encima de 3 kHz)",
		"un ventilador de techo o de pie en marcha, de cerca: soplo continuo con el batir de las aspas; mono, al menos 4 s para un bucle de 3 s",
	),
	"fuente/television": (
		"la televisión oída tras una pared que se descargó (milcahrawr) no tiene nada por encima de 3 kHz: lo que llega amortiguado no se podría situar",
		"una televisión o una radio oída desde otra habitación: voces apagadas que no se entienden, sin música reconocible; mono, al menos 6 s para un bucle de 5 s",
	),
}


def pendientes() -> dict[str, dict[str, str]]:
	"""Los sonidos sin grabación válida: nombre → ``{"motivo", "buscar"}``, con la descripción precisa de lo que hace falta."""
	tabla: dict[str, dict[str, str]] = {}
	for suelo, (motivo, descripcion, maximo) in _PASOS_PENDIENTES.items():
		limite = f"{maximo:.2f}".replace(".", ",")
		buscar = (
			f"seis {descripcion} (tres de cada pie, o seis tomas sueltas del mismo calzado y el mismo suelo), grabadas de cerca; "
			f"mono, cada una de menos de {limite} s, con contenido por encima de 3 kHz"
		)
		for pie in ("izq", "der"):
			for variante in (1, 2, 3):
				tabla[f"pasos/{suelo}_{pie}_{variante}"] = {"motivo": motivo, "buscar": buscar}
	for nombre, (motivo, buscar) in _OTROS_PENDIENTES.items():
		tabla[nombre] = {"motivo": motivo, "buscar": buscar}
	return tabla


def que_buscar(nombre: str) -> str:
	"""Qué grabación haría falta para ``nombre`` cuando la elegida en ``SONIDOS`` no pasa las medidas."""
	from app.audio import sintesis

	definicion = sintesis.CATALOGO[nombre]
	forma = "bucle sin costura" if definicion.bucle else "sonido suelto"
	lugar = "mono y con contenido por encima de 3 kHz" if definicion.posicionable else "sin requisito de agudos"
	return f"otra grabación de «{definicion.nombre_origen()}» ({definicion.explicacion_origen()}); {forma}, {lugar}"


def recetas() -> dict[str, dict]:
	"""La tabla de sonidos que salen de una grabación: nombre → receta."""
	return {nombre: dict(receta) for nombre, receta in SONIDOS.items()}
