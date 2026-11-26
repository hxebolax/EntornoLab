"""Receta del paquete de sonidos «Natural»: qué se le pide al Generador de sonidos para cada sonido.

La usa ``tools/generar_paquete_sonidos.py``. Aquí no se genera nada: solo se describe, con el
formato de especificación del Generador de sonidos (capas, efectos, duración, bucle), cómo se
hace cada uno de los sonidos del catálogo de EntornoLab con su motor procedural (modelos físicos e
instrumentos). **No se usa ninguna capa de inteligencia artificial** (ni ``ia`` ni ``describir``
con ``--ia``) ni las voces de Windows.

Carácter del paquete: frente al de por defecto, que es sintético y limpio (senos, ruido filtrado),
este suena a objetos y a instrumentos acústicos:

- los avisos que **codifican** algo (balizas, bastón sonoro, brújula, plantas del ascensor,
  premios, menús) conservan exactamente sus notas, su número de toques y su ritmo, pero los tocan
  una marimba, un xilófono, un glockenspiel, una celesta, una kalimba o unas trompetas;
- los pasos, golpes, roces, puertas, vehículos, agua y ambientes salen de los modelos físicos.

Lo que hace útil cada sonido se respeta así:

- ``comprobar.notas`` y ``comprobar.golpes`` dicen qué notas (en hercios) y cuántos toques debe
  tener el resultado; la herramienta lo mide y descarta el sonido si no se cumple.
- Lo que se sitúa en el espacio necesita energía por encima de 3 kHz. Los instrumentos de láminas
  casi no la tienen, así que llevan una capa marcada con ``"_aire": True`` (unas maracas: un golpe de
  semillas, ruido de banda ancha), y los ruidos graves, un efecto ``agudos`` marcado con
  ``"_auto": True``. La herramienta sube esa capa o ese efecto, de 4 en 4 dB, solo lo necesario.
- Las claves que empiezan por ``_`` son marcas para la herramienta y no se envían al generador.

Cada receta es un dict: ``{"capas": [...], "efectos": [...], "duracion": s, "bucle": True |
"nativo" | None, "comprobar": {...}}``. Sin ``duracion``, se usa la del sonido de serie.
"""

from __future__ import annotations

ID = "natural"

FICHA = {
	"id": ID,
	"nombre": "Natural",
	"descripcion": (
		"Instrumentos acústicos y objetos con cuerpo: marimba, xilófono y campanas en lugar de tonos electrónicos, y pasos, golpes, puertas y agua "
		"hechos con modelos físicos."
	),
	"autor": "EntornoLab, con el Generador de sonidos de su autor",
	"licencia": "GPL-3.0-or-later, como el programa (sonidos generados por procedimiento; sin grabaciones de terceros)",
	"version": "1.0",
	"igualar": True,
}

# Con cuántos decibelios entra la capa de «aire» antes de que la herramienta la ajuste.
AIRE_INICIAL = -14.0

SUELOS = (
	"baldosa",
	"madera",
	"moqueta",
	"alfombra",
	"hormigon",
	"asfalto",
	"acera",
	"adoquin",
	"tierra",
	"hierba",
	"grava",
	"metal",
	"arena",
	"agua",
	"tactil_botones",
	"tactil_rayas",
)
MATERIALES = ("ladrillo", "madera", "metal", "cristal", "plastico", "tela", "piedra")
# Escala mayor desde do: cada planta del ascensor, una nota más alta (la misma que en la síntesis de serie).
ESCALA_PLANTAS = (0, 2, 4, 5, 7, 9, 11, 12, 14, 16)


# ── Piezas ───────────────────────────────────────────────────────────────────


def son(nombre: str, **opciones: object) -> dict:
	"""Una capa con un generador del catálogo. Las opciones que empiezan por ``c_`` son de la capa; el resto, parámetros."""
	capa: dict = {"tipo": "sonido", "nombre": nombre}
	parametros = {}
	for clave, valor in opciones.items():
		if clave.startswith("c_"):
			capa[clave[2:]] = valor
		else:
			parametros[clave] = valor
	if parametros:
		capa["params"] = parametros
	return capa


def hz(frecuencia: float) -> str:
	"""Una nota escrita en hercios, como la entiende el generador (``440hz``)."""
	return f"{frecuencia:g}hz"


def nota(instrumento: str, frecuencia: float, duracion: float, inicio: float = 0.0, db: float = 0.0, **parametros: object) -> dict:
	"""Una nota suelta de un instrumento, a la frecuencia exacta que se pide."""
	capa: dict = {"tipo": "nota", "instrumento": instrumento, "notas": hz(frecuencia), "duracion": duracion}
	if inicio:
		capa["inicio"] = inicio
	if db:
		capa["volumen_db"] = db
	if parametros:
		capa["params"] = dict(parametros)
	return capa


def frase(
	instrumento: str, pasos: tuple[tuple[float | tuple[float, ...], float], ...], inicio: float = 0.0, db: float = 0.0, **parametros: object
) -> dict:
	"""Varias notas seguidas: cada paso es (frecuencia o acorde, segundos hasta la siguiente)."""
	trozos = []
	for frecuencia, segundos in pasos:
		if isinstance(frecuencia, tuple):
			trozos.append("[" + " ".join(hz(f) for f in frecuencia) + f"]:{segundos:g}")
		else:
			trozos.append(f"{hz(frecuencia)}:{segundos:g}")
	capa: dict = {"tipo": "secuencia", "instrumento": instrumento, "notas": " ".join(trozos)}
	if inicio:
		capa["inicio"] = inicio
	if db:
		capa["volumen_db"] = db
	if parametros:
		capa["params"] = dict(parametros)
	return capa


def aire(inicio: float = 0.0, tipo: str = "maracas", db: float = AIRE_INICIAL, **parametros: object) -> dict:
	"""La capa con agudos que permite situar el sonido: la herramienta ajusta su volumen."""
	capa = son(tipo, **parametros)
	capa["volumen_db"] = db
	if inicio:
		capa["inicio"] = inicio
	capa["_aire"] = True
	return capa


def aires(inicios: tuple[float, ...], **opciones: object) -> list[dict]:
	"""Una capa de aire en cada toque, para que cada uno se pueda situar."""
	return [aire(inicio, **opciones) for inicio in inicios]


def soplo(duracion: float, db: float = AIRE_INICIAL) -> dict:
	"""Aire continuo para un zumbido grave en bucle: el siseo de un ventilador, sin sus graves."""
	capa = son("ventilador", velocidad=0.8, duracion=duracion)
	capa["volumen_db"] = db
	capa["efectos"] = [{"nombre": "paso_alto", "corte": 2500}]
	capa["_aire"] = True
	return capa


def brillo() -> dict:
	"""Efecto final que realza lo que hay por encima de 3 kHz; la herramienta decide cuánto."""
	return {"nombre": "agudos", "frecuencia": 3000, "ganancia": 0.0, "_auto": True}


def receta(
	capas: list[dict],
	efectos: list[dict] | None = None,
	duracion: float | None = None,
	bucle: bool | str | None = None,
	notas: tuple[float, ...] = (),
	golpes: int = 0,
) -> dict:
	"""Arma la ficha de un sonido."""
	ficha: dict = {"capas": capas}
	if efectos:
		ficha["efectos"] = efectos
	if duracion is not None:
		ficha["duracion"] = duracion
	if bucle is not None:
		ficha["bucle"] = bucle
	comprobar: dict = {}
	if notas:
		comprobar["notas"] = list(notas)
	if golpes:
		comprobar["golpes"] = golpes
	if comprobar:
		ficha["comprobar"] = comprobar
	return ficha


# ── Orientación ──────────────────────────────────────────────────────────────


def _orientacion() -> dict[str, dict]:
	r: dict[str, dict] = {}
	# Balizas: marimba y xilófono. «Alineado» es el mismo pulso, más agudo y con maza más dura.
	r["baliza/pulso"] = receta([nota("marimba", 660, 0.3, brillo=0.6), aire()], notas=(660,), golpes=1)
	r["baliza/alineado"] = receta([nota("xilofono", 990, 0.3, brillo=1.0), aire()], notas=(990,), golpes=1)
	r["baliza/detras"] = receta([frase("marimba", ((440, 0.13), (330, 0.24)), brillo=0.5), *aires((0.0, 0.13))], notas=(440, 330), golpes=2)
	r["baliza/cerca"] = receta([frase("xilofono", ((1320, 0.11), (1320, 0.1)), brillo=1.0), *aires((0.0, 0.11))], notas=(1320,), golpes=2)
	r["baliza/llegada"] = receta(
		[
			frase("vibrafono", ((523.25, 0.11), (659.25, 0.11), (783.99, 0.11), (1046.5, 0.5)), motor=0.0, brillo=0.8),
			*aires((0.0, 0.11, 0.22, 0.33)),
		],
		notas=(523.25, 659.25, 783.99, 1046.5),
		golpes=4,
	)
	# Bastón sonoro: cada hallazgo, un objeto distinto.
	r["sonda/pared"] = receta([frase("marimba", (((520, 1040), 0.12),), brillo=0.7, resonador=1.0), aire()], notas=(520,), golpes=1)
	r["sonda/puerta"] = receta(
		[
			son("golpe_madera", golpeador="nudillo", hueco=True, tamano=0.5, c_duracion_max=0.1),
			son("golpe_madera", golpeador="nudillo", hueco=True, tamano=0.5, c_inicio=0.1, c_tono=5, c_duracion_max=0.18),
			*aires((0.0, 0.1), tipo="claves", afinacion=12),
		],
		golpes=2,
	)
	r["sonda/objeto"] = receta([nota("xilofono", 988, 0.16, brillo=0.8), aire()], notas=(988,), golpes=1)
	# Un soplo sin nota: el silbido de algo fino que corta el aire, sin sus graves.
	corte = son("espada_corte_aire", velocidad=0.9, tamano=0.1, duracion=0.25)
	corte["efectos"] = [{"nombre": "paso_alto", "corte": 1200}]
	r["sonda/libre"] = receta([corte], efectos=[brillo()])
	r["sonda/escalon"] = receta(
		[frase("xilofono", ((700, 0.06), (880, 0.06), (1109, 0.12)), brillo=0.9), *aires((0.0, 0.06, 0.12))],
		notas=(700, 880, 1109),
		golpes=3,
	)
	r["sonda/bordillo"] = receta(
		[
			son("tom_grave", fuerza=0.8, afinacion=-5, apagado=0.8, c_duracion_max=0.12),
			son("claves", afinacion=7, c_volumen_db=-12),
			son("claves", afinacion=7, c_inicio=0.09, c_volumen_db=-9),
			*aires((0.0, 0.09)),
		],
		golpes=2,
	)
	# Distancia: el mismo glockenspiel; cambian la nota y cuántas veces suena.
	for clave, frecuencia, veces in (("cerca", 1397.0, 3), ("media", 932.0, 2), ("lejos", 554.0, 1)):
		pasos = tuple((frecuencia, 0.09) for _k in range(veces))
		r[f"sonda/{clave}"] = receta(
			[frase("glockenspiel", pasos, brillo=0.8, liberacion=0.08), *aires(tuple(0.09 * k for k in range(veces)))],
			notas=(frecuencia,),
			golpes=veces,
		)
	# Brújula: celesta. Mismas notas y mismo número de toques que de serie.
	cardinales = {
		"norte": (1568.0,),
		"este": (1174.7, 1174.7),
		"sur": (784.0,),
		"oeste": (987.8, 987.8, 987.8),
		"noreste": (1568.0, 1174.7),
		"sureste": (784.0, 1174.7),
		"suroeste": (784.0, 987.8),
		"noroeste": (1568.0, 987.8),
	}
	for clave, frecuencias in cardinales.items():
		pasos = tuple((f, 0.2 if k == len(frecuencias) - 1 else 0.08) for k, f in enumerate(frecuencias))
		r[f"brujula/{clave}"] = receta(
			[frase("celesta", pasos, brillo=0.9), *aires(tuple(0.08 * k for k in range(len(frecuencias))))],
			notas=tuple(dict.fromkeys(frecuencias)),
			golpes=len(frecuencias),
		)
	r["eco/chasquido"] = receta([son("chasquido_dedos_bateria", fuerza=0.9)], duracion=0.07)
	return r


# ── Pasos ────────────────────────────────────────────────────────────────────

# suelo → (superficie del generador, calzado, peso, capas de más)
_PASOS: dict[str, tuple[str, str, float]] = {
	"baldosa": ("baldosa", "zapato", 0.5),
	"madera": ("madera", "zapato", 0.5),
	"moqueta": ("alfombra", "zapatilla", 0.35),
	"alfombra": ("alfombra", "bota", 0.75),
	"hormigon": ("hormigon", "zapato", 0.5),
	"asfalto": ("hormigon", "zapatilla", 0.55),
	"acera": ("piedra", "zapato", 0.45),
	"adoquin": ("piedra", "bota", 0.55),
	"tierra": ("tierra", "bota", 0.5),
	"hierba": ("hierba", "zapatilla", 0.5),
	"grava": ("grava", "bota", 0.5),
	"metal": ("metal", "bota", 0.5),
	"arena": ("arena", "zapatilla", 0.5),
	"agua": ("agua_charco", "bota", 0.5),
	"tactil_botones": ("baldosa", "zapato", 0.5),
	"tactil_rayas": ("baldosa", "zapato", 0.5),
}
# Segundos de cada paso: algo más que de serie, porque una pisada de verdad tiene talón, planta y punta.
_DURACION_PASO = {
	"baldosa": 0.2,
	"madera": 0.27,
	"moqueta": 0.22,
	"alfombra": 0.24,
	"hormigon": 0.21,
	"asfalto": 0.23,
	"acera": 0.2,
	"adoquin": 0.25,
	"tierra": 0.27,
	"hierba": 0.3,
	"grava": 0.36,
	"metal": 0.4,
	"arena": 0.33,
	"agua": 0.45,
	"tactil_botones": 0.22,
	"tactil_rayas": 0.24,
}


# Retoque del timbre de cada suelo (efectos del generador sobre la pisada), para que no se parezcan entre sí:
# el modelo físico da pisadas muy parecidas en hormigón y en piedra, o en moqueta y en alfombra.
_TIMBRE_PASO: dict[str, list[dict]] = {
	"baldosa": [{"nombre": "agudos", "frecuencia": 2000, "ganancia": 6}],
	"moqueta": [{"nombre": "paso_alto", "corte": 180}, {"nombre": "paso_bajo", "corte": 2200}],
	"alfombra": [{"nombre": "paso_bajo", "corte": 700}, {"nombre": "graves", "frecuencia": 200, "ganancia": 4}],
	"hormigon": [{"nombre": "paso_bajo", "corte": 2500}],
	"asfalto": [{"nombre": "paso_bajo", "corte": 1800}],
	"acera": [{"nombre": "paso_alto", "corte": 300}, {"nombre": "ecualizador", "frecuencia": 2400, "ganancia": 9, "q": 1.2}],
	"adoquin": [{"nombre": "ecualizador", "frecuencia": 1100, "ganancia": 7, "q": 1.5}],
	"tactil_botones": [{"nombre": "agudos", "frecuencia": 2000, "ganancia": 6}],
	"tactil_rayas": [{"nombre": "agudos", "frecuencia": 2000, "ganancia": 6}],
}


def _paso(suelo: str, pie: str) -> dict:
	superficie, calzado, peso = _PASOS[suelo]
	# El pie derecho pisa un pelo más ligero (más agudo): ayuda a notar la alternancia sin que parezcan dos suelos.
	peso = peso + (0.05 if pie == "izq" else -0.05)
	pisada = son("paso", superficie=superficie, calzado=calzado, peso=round(peso, 2), velocidad=0.5, arrastre=0.3, sala="seca")
	if suelo in _TIMBRE_PASO:
		pisada["efectos"] = [dict(efecto) for efecto in _TIMBRE_PASO[suelo]]
	capas = [pisada]
	if suelo == "asfalto":
		# Arenilla suelta sobre el asfalto.
		capas.append(aire(0.0, tipo="paso", db=-5.0, superficie="grava", calzado="zapatilla", peso=0.3, velocidad=0.5))
		return receta(capas, duracion=_DURACION_PASO[suelo])
	elif suelo == "adoquin":
		# Piedra desigual: un segundo apoyo, a destiempo y en otra piedra (más aguda).
		capas.append(son("paso", superficie="piedra", calzado="bota", peso=0.2, velocidad=0.8, c_inicio=0.07, c_volumen_db=-2, c_tono=5))
	elif suelo == "metal":
		# La chapa de la pasarela, que se queda sonando.
		capas.append(son("golpe_metal", tamano=0.35, fuerza=0.4, forma="placa", amortiguado=0.45, duracion=0.35, c_volumen_db=-9))
	elif suelo == "tactil_botones":
		# Los botones del pavimento: un repique doble de madera dura.
		capas.append(son("claves", fuerza=0.5, afinacion=5, c_inicio=0.03, c_volumen_db=-7))
		capas.append(son("claves", fuerza=0.5, afinacion=5, c_inicio=0.06, c_volumen_db=-7))
	elif suelo == "tactil_rayas":
		# Las rayas: la suela raspa un instante.
		capas.append(
			son(
				"arrastrar_pies",
				superficie="hormigon",
				calzado="zapato",
				duracion=0.5,
				velocidad=1.0,
				c_inicio=0.02,
				c_duracion_max=0.15,
				c_volumen_db=1,
			)
		)
	# El roce de la ropa, por encima de 3 kHz, para que el paso se sitúe a tus pies. (En el asfalto ese
	# papel lo hace la arenilla, que ya tiene agudos.)
	capas.append(aire(0.0, tipo="ropa_movimiento", tela="vaqueros", intensidad=0.6, duracion=0.2, movimientos=1, c_duracion_max=0.12))
	return receta(capas, duracion=_DURACION_PASO[suelo])


def _pasos() -> dict[str, dict]:
	r: dict[str, dict] = {}
	for suelo in SUELOS:
		for pie in ("izq", "der"):
			for variante in (1, 2, 3):
				# La misma receta para las tres variantes: las distingue la semilla, que sale del nombre.
				r[f"pasos/{suelo}_{pie}_{variante}"] = _paso(suelo, pie)
	return r


# ── Choques y roces ──────────────────────────────────────────────────────────


def _materiales() -> dict[str, dict]:
	r: dict[str, dict] = {}
	r["golpe/ladrillo"] = receta([son("golpe_piedra", tamano=0.75, fuerza=0.7, arenilla=0.9)], efectos=[brillo()])
	r["golpe/madera"] = receta(
		[son("golpe_madera", tamano=0.5, fuerza=0.8, hueco=True, golpeador="mazo"), aire(tipo="claves", afinacion=12)], golpes=1
	)
	r["golpe/metal"] = receta(
		[son("golpe_metal", tamano=0.5, fuerza=0.8, forma="placa", amortiguado=0.2, duracion=0.7)], efectos=[brillo()]
	)
	r["golpe/cristal"] = receta([son("golpe_vidrio", objeto="ventana", tamano=0.5, fuerza=0.5)], efectos=[brillo()])
	r["golpe/plastico"] = receta(
		[son("impacto", material="plastico", forma="caja", tamano=0.4, fuerza=0.7, duracion=0.3)], efectos=[brillo()]
	)
	r["golpe/tela"] = receta(
		[
			son("golpe_cojin", objeto="cojin", fuerza=0.7),
			aire(0.0, tipo="ropa_movimiento", tela="algodon", intensidad=0.7, duracion=0.25, movimientos=1),
		]
	)
	r["golpe/piedra"] = receta([son("golpe_piedra", tamano=0.4, fuerza=0.9, arenilla=0.05)], efectos=[brillo()])
	roces = {
		"ladrillo": son("arrastrar_objeto", material="piedra", superficie="hormigon", duracion=0.4, peso=0.3, tamano=0.4),
		"madera": son("arrastrar_objeto", material="madera", superficie="madera", duracion=0.4, peso=0.3, tamano=0.4),
		"metal": son("arrastrar_objeto", material="metal", superficie="metal", duracion=0.4, peso=0.3, tamano=0.3),
		"plastico": son("arrastrar_objeto", material="plastico", superficie="madera", duracion=0.4, peso=0.2, tamano=0.3),
		"tela": son("ropa_movimiento", tela="algodon", intensidad=0.6, duracion=0.4, movimientos=1),
		"piedra": son("arrastrar_objeto", material="piedra", superficie="piedra", duracion=0.4, peso=0.5, tamano=0.6),
	}
	for material, capa in roces.items():
		r[f"roce/{material}"] = receta([capa], efectos=[brillo()])
	# El cristal no está entre los materiales que se arrastran: un roce de plástico sobre baldosa, sin sus graves.
	cristal = son("arrastrar_objeto", material="plastico", superficie="baldosa", duracion=0.4, peso=0.1, tamano=0.2)
	cristal["efectos"] = [{"nombre": "paso_alto", "corte": 3000}]
	r["roce/cristal"] = receta([cristal])
	return r


# ── Puertas, escaleras y ascensor ────────────────────────────────────────────


def _puertas() -> dict[str, dict]:
	r: dict[str, dict] = {}
	# Una puerta de verdad tarda más que el aviso de serie: se abre deprisa y se deja en 1,2 segundos.
	r["puerta/abrir"] = receta(
		[son("puerta_madera", accion="abrir", chirrido=0.5, tamano=0.4, fuerza=0.5, velocidad=1.0, espacio="seco")],
		efectos=[brillo()],
		duracion=1.2,
	)
	r["puerta/cerrar"] = receta(
		[son("puerta_madera", accion="cerrar", chirrido=0.4, tamano=0.4, fuerza=0.6, velocidad=1.0, espacio="seco")],
		efectos=[brillo()],
		duracion=1.15,
	)
	# La manilla baja dos veces y la puerta no cede.
	r["puerta/con_llave"] = receta(
		[son("picaporte", fuerza=0.9, desgaste=0.7, material="metal", c_duracion_max=0.3, c_repetir=2, c_cada=0.3)], golpes=0
	)
	motor = son(
		"motor_electrico",
		duracion=2.0,
		velocidad=0.5,
		carga=0.5,
		tamano=0.4,
		c_duracion_max=1.0,
		c_volumen_db=-9,
		c_fundido_entrada=0.08,
		c_fundido_salida=0.15,
	)
	r["puerta/automatica"] = receta(
		[son("ventana", tipo="corredera", accion="abrir", velocidad=1.0, fuerza=0.4), motor], efectos=[brillo()]
	)
	for clave, frecuencias, peso in (("subir", (587.0, 784.0), 0.4), ("bajar", (784.0, 587.0), 0.6)):
		r[f"escalera/{clave}"] = receta(
			[
				son("paso", superficie="madera", calzado="zapato", peso=peso, velocidad=0.6, c_duracion_max=0.2, c_volumen_db=-3),
				frase("marimba", ((frecuencias[0], 0.07), (frecuencias[1], 0.16)), inicio=0.04, brillo=0.7),
				*aires((0.04, 0.11)),
			],
			notas=frecuencias,
		)
	r["escalera/rampa"] = receta(
		[son("arrastrar_pies", superficie="hormigon", calzado="zapato", duracion=0.5, velocidad=1.0, peso=0.4)], efectos=[brillo()]
	)
	r["ascensor/llamada"] = receta(
		[
			son("interruptor_luz", tipo="pulsador", fuerza=0.7),
			nota("glockenspiel", 1175, 0.3, inicio=0.08, brillo=0.7, liberacion=0.2),
			aire(0.08),
		],
		notas=(1175,),
	)
	puerta = son("ventana", tipo="corredera", accion="cerrar", velocidad=0.85, fuerza=0.8)
	puerta["efectos"] = [{"nombre": "graves", "frecuencia": 250, "ganancia": 6}]
	r["ascensor/puerta"] = receta([puerta], efectos=[brillo()])
	# El generador añade el arranque y la parada al viaje: se pide como bucle de la duración exacta.
	r["ascensor/viaje"] = receta([son("ascensor", parte="viaje", duracion=3.25, antiguedad=0.3)], bucle=True)
	r["ascensor/llegada"] = receta(
		[frase("glockenspiel", ((1319, 0.22), (1047, 0.7)), brillo=0.7, liberacion=0.8), *aires((0.0, 0.22))], notas=(1319, 1047), golpes=2
	)
	for planta, semitonos in enumerate(ESCALA_PLANTAS):
		frecuencia = round(523.25 * 2.0 ** (semitonos / 12.0), 2)
		r[f"ascensor/planta_{planta}"] = receta(
			[nota("glockenspiel", frecuencia, 0.42, brillo=0.7, liberacion=0.3), aire()], notas=(frecuencia,), golpes=1
		)
	return r


# ── Premios y logros ─────────────────────────────────────────────────────────


def _premios() -> dict[str, dict]:
	r: dict[str, dict] = {}
	subida = (1568.0, 2093.0, 2637.0, 3136.0, 4186.0)
	r["premio/aparece"] = receta(
		[frase("glockenspiel", tuple((f, 0.07) for f in subida), brillo=0.9, liberacion=0.25), *aires(tuple(0.07 * k for k in range(5)))],
		notas=subida,
		golpes=5,
	)
	centelleo = ((0.0, 2637.0, 0.0), (0.15, 3136.0, -2.0), (0.3, 3951.0, -1.0), (0.6, 3136.0, -3.0), (0.75, 4186.0, -2.0))
	r["premio/cerca"] = receta(
		[nota("glockenspiel", f, 0.15, inicio=inicio, db=db, brillo=0.9, liberacion=0.15) for inicio, f, db in centelleo]
		+ aires(tuple(inicio for inicio, _f, _db in centelleo)),
		bucle=True,
		notas=(2637.0, 3136.0, 3951.0, 4186.0),
	)
	r["premio/recogido"] = receta([son("moneda", tono=0.6, brillo=0.6, estilo="realista", monedas=3)])
	melodia = ((523.25, 0.1), (659.25, 0.1), (783.99, 0.1), (1046.5, 0.1), (783.99, 0.1), (1046.5, 0.1), (1318.5, 0.7))
	r["premio/tesoro"] = receta(
		[
			frase("celesta", melodia, brillo=0.8, pedal=True),
			aire(0.5, tipo="destello", db=-8.0, densidad=0.7, duracion=0.9, tono=0.7),
			aire(),
		],
		notas=(523.25, 659.25, 783.99, 1046.5, 1318.5),
	)
	r["logro/logro"] = receta(
		[frase("vibrafono", ((659.25, 0.09), (783.99, 0.09), (1046.5, 0.45)), motor=0.0, brillo=0.7)], notas=(659.25, 783.99, 1046.5)
	)
	estrellas = (1046.5, 1318.5, 1568.0)
	for cuantas in (1, 2, 3):
		pasos = tuple((f, 0.22 if k < cuantas - 1 else 0.6) for k, f in enumerate(estrellas[:cuantas]))
		r[f"logro/estrella_{cuantas}"] = receta(
			[frase("glockenspiel", pasos, brillo=0.8, liberacion=0.6)], notas=estrellas[:cuantas], golpes=cuantas
		)
	fanfarria = ((392.0, 0.17), (392.0, 0.17), (523.25, 0.24), (659.25, 0.24), ((523.25, 659.25, 783.99, 1046.5), 0.95))
	r["logro/medalla"] = receta(
		[
			frase("trompeta", fanfarria, brillo=0.6, vibrato=0.1),
			son("destello", densidad=0.5, duracion=0.8, tono=0.7, c_inicio=0.85, c_volumen_db=-12),
		],
		notas=(392.0, 523.25, 659.25),
	)
	r["logro/error"] = receta([frase("marimba", ((311.1, 0.13), (233.1, 0.28)), brillo=0.2, resonador=1.0)], notas=(311.1, 233.1), golpes=2)
	r["logro/pista"] = receta([frase("celesta", ((880.0, 0.14), (1318.5, 0.42)), brillo=0.6, pedal=True)], notas=(880.0, 1318.5), golpes=2)
	return r


# ── Interfaz ─────────────────────────────────────────────────────────────────


def _interfaz() -> dict[str, dict]:
	"""Los menús, con kalimba: no se confunde con la marimba de los avisos del juego."""
	r: dict[str, dict] = {}
	r["interfaz/mover"] = receta([son("tick", tono=0.6, brillo=0.5, duracion=0.03, estilo="madera")])
	r["interfaz/ajuste"] = receta([son("tick", tono=0.9, brillo=0.7, duracion=0.03, estilo="madera")])
	r["interfaz/borde"] = receta([nota("marimba", 180, 0.08, brillo=0.3, resonador=1.0)], duracion=0.12, notas=(180,))
	r["interfaz/elegir"] = receta([frase("kalimba", ((880.0, 0.06), (1320.0, 0.15)), brillo=0.7)], notas=(880.0, 1320.0))
	r["interfaz/atras"] = receta([frase("kalimba", ((660.0, 0.06), (440.0, 0.15)), brillo=0.7)], notas=(660.0, 440.0))
	r["interfaz/abrir"] = receta(
		[frase("kalimba", ((523.25, 0.05), (659.25, 0.05), (783.99, 0.16)), brillo=0.7)], notas=(523.25, 659.25, 783.99)
	)
	r["interfaz/cerrar"] = receta(
		[frase("kalimba", ((783.99, 0.05), (659.25, 0.05), (523.25, 0.16)), brillo=0.7)], notas=(783.99, 659.25, 523.25)
	)
	return r


# ── La calle ─────────────────────────────────────────────────────────────────


def _calle() -> dict[str, dict]:
	r: dict[str, dict] = {}
	# El «pío» del semáforo: una ocarina aguda y corta. El ritmo (lo que dice el color) es el de serie.
	r["semaforo/verde"] = receta(
		[nota("ocarina", 3000, 0.08, inicio=0.02 + 0.25 * k, vibrato=0.0, aire=0.2, liberacion=0.04) for k in range(4)],
		bucle=True,
		golpes=4,
	)
	r["semaforo/intermitente"] = receta(
		[nota("ocarina", 3000, 0.05, inicio=0.01 + 0.125 * k, vibrato=0.0, aire=0.2, liberacion=0.03) for k in range(4)],
		bucle=True,
		golpes=4,
	)
	r["semaforo/rojo"] = receta([son("claves", fuerza=0.8, afinacion=3, c_inicio=0.02), aire(0.02)], bucle=True, golpes=1)
	r["semaforo/pulsador"] = receta(
		[
			son("interruptor_luz", tipo="pulsador", fuerza=0.8),
			frase("glockenspiel", ((1480.0, 0.14), (1480.0, 0.16)), inicio=0.12, brillo=0.7, liberacion=0.08),
			*aires((0.12, 0.26)),
		],
		notas=(1480.0,),
	)
	r["trafico/coche"] = receta(
		[son("coche_pasa", velocidad=50.0, distancia_m=5.0, cilindros=4, escape="normal", duracion=3.2)], efectos=[brillo()]
	)
	r["trafico/moto"] = receta([son("moto", tipo="scooter", accion="pasada", duracion=2.6)], efectos=[brillo()])
	r["trafico/autobus"] = receta(
		[
			son("camion_diesel", accion="pasada", carga=0.5, duracion=3.9),
			son("autobus_frenos_aire", accion="frenar", intensidad=0.5, c_inicio=3.3, c_duracion_max=1.2, c_volumen_db=-16),
		],
		# El motor diésel tiene picos muy por encima de su cuerpo: se comprime para que el autobús no suene más flojo que los coches.
		efectos=[{"nombre": "limitador", "techo": -18}, brillo()],
	)
	for clave, densidad, distancia, bocinas in (("leve", 0.12, 0.65, 0.0), ("medio", 0.5, 0.4, 0.0), ("intenso", 0.92, 0.2, 0.1)):
		r[f"trafico/ambiente_{clave}"] = receta(
			[son("trafico", densidad=densidad, distancia=distancia, bocinas=bocinas, duracion=10.0)], bucle="nativo"
		)
	r["exterior/bordillo"] = receta(
		[
			son("arrastrar_pies", superficie="hormigon", calzado="zapato", duracion=0.5, velocidad=1.0, c_duracion_max=0.11),
			son("salto_aterrizaje", superficie="hormigon", calzado="zapato", peso=0.6, altura=0.1, fase="aterrizaje", c_inicio=0.08),
		],
		efectos=[brillo()],
		duracion=0.38,
	)
	return r


# ── Fuentes de los lugares ───────────────────────────────────────────────────


def _fuentes() -> dict[str, dict]:
	r: dict[str, dict] = {}
	r["fuente/frigorifico"] = receta([son("frigorifico", duracion=4.0), soplo(4.0)], bucle=True)
	# El reloj de pie da justo un golpe por segundo: tic, tac (cada golpe es el doble clic del escape, y por eso no se cuentan los toques).
	r["fuente/reloj"] = receta([son("reloj_tic_tac", tipo="pie", duracion=2.0, volumen_caja=0.5)], bucle="nativo")
	r["fuente/grifo"] = receta([son("grifo", caudal=0.4, duracion=3.0)], bucle="nativo")
	r["fuente/ventilador"] = receta([son("ventilador", velocidad=0.5, oscilante=False, duracion=3.0)], bucle="nativo")
	# La tele lejana: un murmullo de pocas voces sin palabras, por un altavoz pequeño. No se usa ninguna voz sintética.
	tele = son("multitud_murmullo", personas=3, animacion=0.45, lugar="sala", duracion=5.0)
	tele["efectos"] = [{"nombre": "telefono"}]
	r["fuente/television"] = receta([tele, soplo(5.0, -20.0)], bucle=True)
	r["fuente/fuente_agua"] = receta([son("fuente", tamano=0.5, duracion=4.0)], bucle="nativo")
	r["fuente/maquina_expendedora"] = receta(
		[
			son("fluorescente_zumbido", red="50", parpadeo=0.0, duracion=4.0, c_volumen_db=-4),
			son("motor_electrico", duracion=4.0, velocidad=0.8, carga=0.2, tamano=0.05, c_volumen_db=-14),
			son("interruptor_luz", tipo="basculante", fuerza=0.5, c_inicio=2.6, c_volumen_db=-8),
			soplo(4.0),
		],
		bucle=True,
	)
	r["fuente/campanas"] = receta(
		[
			nota("campanas_tubulares", 196.0, 1.6, inicio=0.1, brillo=1.0, liberacion=1.2),
			nota("campanas_tubulares", 196.0, 1.6, inicio=1.9, db=-2.0, brillo=1.0, liberacion=1.2),
			# El golpe del badajo: un toque de triángulo apagado, que es lo que tiene agudos.
			*aires((0.1, 1.9), tipo="triangulo", fuerza=0.6, afinacion=-6, apagado=True, duracion=0.3),
		],
		bucle=True,
		notas=(196.0,),
	)
	r["fuente/pajaros"] = receta(
		[
			son("pajaro", especie="gorrion", distancia=0.0, c_inicio=0.3),
			son("pajaro", especie="canario", distancia=0.0, c_inicio=2.1, c_volumen_db=-3),
			son("pajaro", especie="mirlo", distancia=0.0, c_inicio=3.9),
		],
		bucle=True,
	)
	return r


# ── Ambientes ────────────────────────────────────────────────────────────────


def _ambientes() -> dict[str, dict]:
	r: dict[str, dict] = {}
	# El viento de fuera, flojo y sin silbido: el aire de una casa tranquila.
	viento = son("viento", fuerza=0.08, rafagas=0.1, silbido=0.0, duracion=10.0, c_volumen_db=-6)
	r["ambiente/casa"] = receta(
		[
			viento,
			son("crujido_madera", tension=0.4, duracion=0.6, crujidos=1, tamano=0.6, c_inicio=3.1, c_volumen_db=-10, c_pan=-0.4),
			son("crujido_madera", tension=0.5, duracion=0.5, crujidos=1, tamano=0.3, c_inicio=7.4, c_volumen_db=-14, c_pan=0.5),
		],
		bucle=True,
	)
	r["ambiente/oficina"] = receta([son("oficina", densidad=0.4, intensidad=0.4, duracion=10.0)], bucle="nativo")
	pasos = son(
		"secuencia_pasos",
		superficie="baldosa",
		calzado="zapato",
		numero=5,
		velocidad=0.3,
		sala="pasillo",
		c_inicio=2.5,
		c_volumen_db=-8,
		c_pan=0.3,
	)
	pasos["efectos"] = [{"nombre": "distancia", "metros": 12, "entorno": "pasillo"}]
	r["ambiente/pasillo"] = receta(
		[son("aire_acondicionado", unidad="interior", duracion=10.0, c_volumen_db=-6), pasos],
		efectos=[{"nombre": "reverberacion", "espacio": "pasillo", "mezcla": 0.3}],
		bucle=True,
	)
	r["ambiente/calle"] = receta([son("ciudad_dia", densidad=0.5, intensidad=0.5, duracion=10.0)], bucle="nativo")
	aves = (
		("gorrion", 0.6, -0.6, -6),
		("mirlo", 2.4, 0.5, -4),
		("canario", 4.6, -0.2, -8),
		("cantor", 6.3, 0.7, -5),
		("alondra", 8.0, -0.5, -7),
	)
	r["ambiente/parque"] = receta(
		[son("brisa_hojas", intensidad=0.4, hojas=0.7, duracion=10.0, c_volumen_db=-4)]
		+ [son("pajaro", especie=especie, distancia=0.5, c_inicio=inicio, c_pan=pan, c_volumen_db=db) for especie, inicio, pan, db in aves],
		bucle=True,
	)
	r["ambiente/cocina"] = receta(
		[
			son("frigorifico", duracion=10.0, c_volumen_db=-8),
			son("hervir", intensidad=0.4, tapa=False, duracion=10.0, c_volumen_db=-8, c_pan=0.3),
			son("cajon_mueble", accion="abrir", contenido="cubiertos", material="madera", c_inicio=3.4, c_volumen_db=-12, c_pan=-0.4),
			son(
				"golpe_metal",
				tamano=0.2,
				fuerza=0.3,
				forma="cuenco",
				amortiguado=0.6,
				duracion=0.6,
				c_inicio=7.3,
				c_volumen_db=-14,
				c_pan=-0.2,
			),
		],
		bucle=True,
	)
	return r


def recetas() -> dict[str, dict]:
	"""Todas las recetas del paquete: ``{nombre del sonido: receta}``."""
	todas: dict[str, dict] = {}
	for familia in (_orientacion, _pasos, _materiales, _puertas, _premios, _interfaz, _calle, _fuentes, _ambientes):
		todas.update(familia())
	return todas
