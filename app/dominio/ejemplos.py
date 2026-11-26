"""Entornos de ejemplo: una vivienda, un centro de dos plantas y un barrio.

Son lugares FICTICIOS, construidos con las mismas operaciones de ``edicion``
que usa el profesional, de modo que sirven a la vez de muestra para quien
empieza y de prueba de que esas operaciones bastan para hacer un entorno
completo. No llevan objetos de complementos (los complementos van aparte):
``amueblar_ejemplos`` los amuebla si el catálogo tiene con qué.

Cada espacio lleva en ``datos["uso"]`` para qué se usa (dormitorio, cocina,
aula…), que es lo que lee el amueblado asistido. Los espacios de la calle,
donde no hay receta que valga, llevan en ``datos["mobiliario"]`` una lista de
sugerencias (qué objeto, dónde y mirando hacia dónde) que ``amueblar_ejemplos``
coloca si algún complemento instalado tiene ese objeto.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Sequence

from app.core.i18n import _
from app.dominio import edicion as ed
from app.dominio.catalogo import Catalogo, DefObjeto, sin_acentos
from app.dominio.colocacion import USOS, amueblar_espacio, colocar_en_punto
from app.dominio.modelo import Entorno, Espacio, Objeto, Planta

log = logging.getLogger(__name__)

AUTOR_EJEMPLOS = "EntornoLab"

# Complementos de serie que se prefieren al amueblar cada uso, por orden. Solo
# deciden cuando varios complementos instalados ofrecen el mismo mueble.
PREFERIDOS_POR_USO: dict[str, tuple[str, ...]] = {
	"aula": ("colegio", "oficina_y_comercio", "hogar"),
	"oficina": ("oficina_y_comercio", "colegio", "hogar"),
}
PREFERIDOS_INTERIOR: tuple[str, ...] = ("hogar", "oficina_y_comercio", "colegio")
PREFERIDOS_EXTERIOR: tuple[str, ...] = ("calle", "transporte")


def _procedencia(entorno: Entorno) -> None:
	"""Deja claro en el propio fichero que el lugar es inventado."""
	entorno.procedencia = {
		"fuente": _("Entorno ficticio de ejemplo"),
		"fecha": "2026",
		"escala": "1:1",
		"licencia": "CC0",
		"notas": _("No representa ningún lugar real. Puede copiarse y modificarse libremente."),
	}


def _habitacion(
	entorno: Entorno, planta: Planta, nombre: str, x: float, y: float, ancho: float, fondo: float, uso: str = "", **opciones
) -> Espacio:
	"""Habitación rectangular que anota su uso para el amueblado asistido."""
	espacio = ed.crear_habitacion_rectangular(entorno, planta, nombre, x, y, ancho, fondo, **opciones)
	if uso:
		espacio.datos["uso"] = uso
	return espacio


def _sugerir(planta: Planta, x: float, y: float, rumbo: float, *palabras: str, ambito: str = "exterior") -> None:
	"""Anota en el espacio que hay en (x, y) que ahí iría bien un objeto.

	``palabras`` son los nombres por los que buscarlo en el catálogo, por orden
	de preferencia («semaforo peatones», «semaforo»). No coloca nada: lo hace
	``amueblar_ejemplos`` si hay un complemento que lo tenga.
	"""
	espacio = planta.espacio_en(x, y, incluir_macizos=False)
	if espacio is None:
		return
	espacio.datos.setdefault("mobiliario", []).append({"palabras": list(palabras), "x": x, "y": y, "rumbo": rumbo, "ambito": ambito})


# ── 1. Vivienda ──────────────────────────────────────────────────────────────


def vivienda_ejemplo() -> Entorno:
	"""Vivienda de una planta: entrada, pasillo, salón, cocina, dormitorio y baño.

	Un pasillo de este a oeste reparte la casa: al sur quedan el salón y la
	cocina, al norte el dormitorio y el baño, y en su extremo oeste la entrada.
	"""
	entorno = ed.crear_entorno(
		_("Vivienda de ejemplo"), _("Un piso pequeño para aprender a moverse por una casa: seis estancias en una planta."), AUTOR_EJEMPLOS
	)
	_procedencia(entorno)
	planta = ed.crear_planta(entorno, _("Vivienda"))

	pasillo = _habitacion(entorno, planta, _("Pasillo"), 0.0, 4.0, 8.0, 1.2, tipo="pasillo", suelo="madera")
	entrada = ed.crear_habitacion_adosada(
		entorno,
		planta,
		_("Entrada"),
		pasillo,
		"oeste",
		2.0,
		2.2,
		alineacion="centro",
		tipo="vestibulo",
		suelo="baldosa",
		acustica="habitacion",
	)
	salon = _habitacion(entorno, planta, _("Salón"), 0.0, 0.0, 4.5, 4.0, uso="salon", suelo="madera")
	cocina = _habitacion(entorno, planta, _("Cocina"), 4.5, 0.0, 3.5, 4.0, uso="cocina", suelo="baldosa")
	dormitorio = _habitacion(entorno, planta, _("Dormitorio"), 0.0, 5.2, 4.5, 3.5, uso="dormitorio", suelo="madera")
	bano = _habitacion(entorno, planta, _("Baño"), 4.5, 5.2, 2.5, 3.5, uso="bano", suelo="baldosa", acustica="bano")

	ed.anadir_puerta(
		entorno,
		planta,
		entrada,
		"oeste",
		ancho=0.9,
		nombre=_("Puerta de la calle"),
		estado="cerrada",
		material="madera",
		es_salida=True,
		descripcion=_("Es la puerta de la casa; da al rellano."),
	)
	ed.anadir_puerta_entre(entorno, planta, entrada, pasillo, ancho=1.0, tipo="hueco")
	ed.anadir_puerta_entre(entorno, planta, salon, pasillo, desplazamiento=1.5, ancho=0.9, estado="abierta")
	ed.anadir_puerta_entre(entorno, planta, cocina, pasillo, desplazamiento=1.0, estado="abierta")
	ed.anadir_puerta_entre(entorno, planta, dormitorio, pasillo, desplazamiento=2.5, estado="cerrada")
	ed.anadir_puerta_entre(entorno, planta, bano, pasillo, desplazamiento=0.8, ancho=0.72, estado="cerrada", hoja="corredera")
	ed.anadir_puerta(
		entorno, planta, salon, "sur", desplazamiento=1.5, ancho=1.5, tipo="ventana", nombre=_("Ventana del salón"), material="cristal"
	)
	ed.anadir_puerta(
		entorno, planta, cocina, "sur", desplazamiento=1.0, ancho=1.2, tipo="ventana", nombre=_("Ventana de la cocina"), material="cristal"
	)
	ed.anadir_puerta(
		entorno,
		planta,
		dormitorio,
		"norte",
		desplazamiento=1.5,
		ancho=1.5,
		tipo="ventana",
		nombre=_("Ventana del dormitorio"),
		material="cristal",
	)

	ed.anadir_fuente(
		entorno,
		planta,
		_("Frigorífico"),
		7.6,
		0.5,
		"frigorifico",
		volumen=0.5,
		radio=6.0,
		descripcion=_("Zumba todo el rato en la esquina sureste de la cocina."),
	)
	ed.anadir_fuente(
		entorno,
		planta,
		_("Reloj de pared"),
		0.3,
		2.0,
		"reloj",
		volumen=0.4,
		radio=5.0,
		altura=1.8,
		descripcion=_("Hace tictac en la pared oeste del salón."),
	)
	ed.anadir_fuente(
		entorno,
		planta,
		_("Calle por la ventana"),
		2.25,
		0.2,
		"ambiente_calle",
		volumen=0.3,
		radio=7.0,
		altura=1.2,
		descripcion=_("El ruido de la calle entra por la ventana del salón."),
	)
	ed.anadir_referencia(entorno, planta, _("Felpudo"), -1.5, 4.6, tipo="tactil", descripcion=_("Se nota bajo los pies nada más entrar."))
	ed.anadir_referencia(entorno, planta, _("Perchero"), -1.0, 5.5, tipo="punto", descripcion=_("Colgado en la pared norte de la entrada."))
	ed.anadir_referencia(
		entorno, planta, _("Radiador del pasillo"), 7.5, 5.1, tipo="tactil", descripcion=_("Bajo, pegado a la pared norte del pasillo.")
	)
	ed.anadir_zona_suelo(entorno, planta, _("Alfombra del salón"), [(1.2, 1.0), (3.4, 1.0), (3.4, 2.6), (1.2, 2.6)], "alfombra")
	ed.fijar_inicio(entorno, planta, -1.0, 4.6, 90.0)
	return entorno


# ── 2. Centro de dos plantas ─────────────────────────────────────────────────


def _planta_centro(entorno: Entorno, planta: Planta, baja: bool) -> dict[str, Espacio]:
	"""Lo que las dos plantas del centro tienen en común: pasillo, escalera, aseos y hueco del ascensor."""
	espacios: dict[str, Espacio] = {}
	sufijo = _(" de la planta baja") if baja else _(" de la planta primera")
	espacios["pasillo"] = _habitacion(entorno, planta, _("Pasillo") + sufijo, 0.0, 6.0, 20.0, 2.0, tipo="pasillo", suelo="baldosa")
	espacios["aseos"] = _habitacion(entorno, planta, _("Aseos") + sufijo, 4.0, 8.0, 4.0, 4.0, uso="bano", acustica="bano")
	espacios["escalera"] = _habitacion(entorno, planta, _("Escalera") + sufijo, 8.0, 8.0, 3.0, 4.0, tipo="escalera", suelo="hormigon")
	espacios["ascensor"] = ed.crear_espacio_poligonal(
		entorno,
		planta,
		_("Hueco del ascensor") + sufijo,
		[(11.0, 8.0), (13.0, 8.0), (13.0, 12.0), (11.0, 12.0)],
		tipo="cabina",
		macizo=True,
		descripcion=_("La cabina queda detrás de la puerta; no se recorre andando."),
	)
	ed.anadir_puerta_entre(entorno, planta, espacios["aseos"], espacios["pasillo"], desplazamiento=1.5, estado="cerrada")
	ed.anadir_puerta_entre(entorno, planta, espacios["escalera"], espacios["pasillo"], ancho=1.4, tipo="hueco")
	ed.anadir_referencia(
		entorno,
		planta,
		_("Puerta del ascensor") + sufijo,
		12.0,
		7.8,
		tipo="punto",
		descripcion=_("En la pared norte del pasillo, junto a la escalera. El botón está a la derecha."),
	)
	return espacios


def centro_dos_plantas() -> Entorno:
	"""Centro de dos plantas: vestíbulo, pasillos, aulas, despachos, aseos, escalera y ascensor.

	Tiene tres salidas marcadas (la principal y dos de emergencia en los
	extremos del pasillo de la planta baja), para practicar evacuaciones.
	"""
	entorno = ed.crear_entorno(
		_("Centro de dos plantas"),
		_("Un centro pequeño con aulas y despachos en dos plantas, unidas por una escalera y un ascensor. Tiene tres salidas."),
		AUTOR_EJEMPLOS,
	)
	_procedencia(entorno)
	baja = ed.crear_planta(entorno, _("Planta baja"), nivel=0, altura_m=0.0)
	primera = ed.crear_planta(entorno, _("Planta primera"), nivel=1, altura_m=3.2)

	# Planta baja.
	comunes = _planta_centro(entorno, baja, baja=True)
	pasillo = comunes["pasillo"]
	vestibulo = _habitacion(entorno, baja, _("Vestíbulo"), 0.0, 0.0, 8.0, 6.0, tipo="vestibulo", suelo="baldosa")
	aula_1 = _habitacion(entorno, baja, _("Aula 1"), 8.0, 0.0, 6.0, 6.0, uso="aula")
	aula_2 = _habitacion(entorno, baja, _("Aula 2"), 14.0, 0.0, 6.0, 6.0, uso="aula")
	conserjeria = _habitacion(entorno, baja, _("Conserjería"), 0.0, 8.0, 4.0, 4.0, uso="oficina")
	biblioteca = _habitacion(entorno, baja, _("Biblioteca"), 13.0, 8.0, 7.0, 4.0, uso="oficina", suelo="moqueta", acustica="seca")

	ed.anadir_puerta(
		entorno,
		baja,
		vestibulo,
		"sur",
		ancho=1.6,
		nombre=_("Puerta principal"),
		estado="cerrada",
		hoja="automatica",
		material="cristal",
		es_salida=True,
		descripcion=_("Puerta doble de cristal que se abre sola. Da a la calle."),
	)
	ed.anadir_puerta_entre(entorno, baja, vestibulo, pasillo, ancho=2.4, tipo="hueco")
	ed.anadir_puerta_entre(entorno, baja, aula_1, pasillo, desplazamiento=0.6, estado="cerrada")
	ed.anadir_puerta_entre(entorno, baja, aula_2, pasillo, desplazamiento=0.6, estado="cerrada")
	ed.anadir_puerta_entre(entorno, baja, conserjeria, pasillo, desplazamiento=2.4, estado="abierta")
	ed.anadir_puerta_entre(entorno, baja, biblioteca, pasillo, desplazamiento=1.0, ancho=0.9, estado="cerrada")
	ed.anadir_puerta(
		entorno,
		baja,
		pasillo,
		"este",
		ancho=1.0,
		nombre=_("Salida de emergencia este"),
		estado="cerrada",
		material="metal",
		es_salida=True,
		descripcion=_("Puerta con barra antipánico al final del pasillo."),
	)
	ed.anadir_puerta(
		entorno,
		baja,
		pasillo,
		"oeste",
		ancho=1.0,
		nombre=_("Salida de emergencia oeste"),
		estado="cerrada",
		material="metal",
		es_salida=True,
		descripcion=_("Puerta con barra antipánico al principio del pasillo, junto a la conserjería."),
	)
	ed.anadir_fuente(
		entorno,
		baja,
		_("Máquina de bebidas"),
		7.5,
		3.0,
		"maquina_expendedora",
		volumen=0.5,
		radio=8.0,
		descripcion=_("Zumba en la pared este del vestíbulo."),
	)
	ed.anadir_fuente(
		entorno,
		baja,
		_("Reloj del vestíbulo"),
		0.3,
		3.0,
		"reloj",
		volumen=0.4,
		radio=6.0,
		altura=2.0,
		descripcion=_("En la pared oeste del vestíbulo."),
	)
	ed.anadir_fuente(
		entorno,
		baja,
		_("Fuente de agua"),
		17.0,
		7.7,
		"fuente_agua",
		volumen=0.4,
		radio=6.0,
		descripcion=_("Gotea junto a la puerta de la biblioteca."),
	)
	ed.anadir_referencia(
		entorno, baja, _("Felpudo de la entrada"), 4.0, 0.6, tipo="tactil", descripcion=_("Ancho, justo detrás de la puerta principal.")
	)
	ed.anadir_referencia(entorno, baja, _("Mostrador de información"), 2.0, 4.5, tipo="punto", descripcion=_("A la izquierda al entrar."))
	ed.anadir_zona_suelo(entorno, baja, _("Franja guía del vestíbulo"), [(3.7, 1.0), (4.3, 1.0), (4.3, 6.0), (3.7, 6.0)], "tactil_rayas")

	# Planta primera.
	arriba = _planta_centro(entorno, primera, baja=False)
	pasillo_1 = arriba["pasillo"]
	aula_3 = _habitacion(entorno, primera, _("Aula 3"), 0.0, 0.0, 7.0, 6.0, uso="aula")
	aula_4 = _habitacion(entorno, primera, _("Aula 4"), 7.0, 0.0, 7.0, 6.0, uso="aula")
	aula_5 = _habitacion(entorno, primera, _("Aula 5"), 14.0, 0.0, 6.0, 6.0, uso="aula")
	direccion = _habitacion(entorno, primera, _("Despacho de dirección"), 0.0, 8.0, 4.0, 4.0, uso="oficina", suelo="madera")
	informatica = _habitacion(entorno, primera, _("Sala de informática"), 13.0, 8.0, 7.0, 4.0, uso="aula")
	for aula in (aula_3, aula_4, aula_5):
		ed.anadir_puerta_entre(entorno, primera, aula, pasillo_1, desplazamiento=0.6, estado="cerrada")
	ed.anadir_puerta_entre(entorno, primera, direccion, pasillo_1, desplazamiento=2.4, estado="cerrada")
	ed.anadir_puerta_entre(entorno, primera, informatica, pasillo_1, desplazamiento=1.0, ancho=0.9, estado="cerrada")
	ed.anadir_puerta(
		entorno,
		primera,
		pasillo_1,
		"este",
		desplazamiento=0.4,
		ancho=1.2,
		tipo="ventana",
		nombre=_("Ventana del fondo del pasillo"),
		material="cristal",
	)
	ed.anadir_fuente(
		entorno,
		primera,
		_("Ordenadores"),
		16.5,
		10.0,
		"ventilador",
		volumen=0.4,
		radio=7.0,
		descripcion=_("El zumbido de los ordenadores de la sala de informática."),
	)
	ed.anadir_fuente(
		entorno,
		primera,
		_("Reloj del pasillo"),
		0.3,
		7.0,
		"reloj",
		volumen=0.4,
		radio=6.0,
		altura=2.0,
		descripcion=_("En el extremo oeste del pasillo de arriba."),
	)

	ed.crear_escalera(
		entorno,
		baja,
		primera,
		(8.8, 8.6),
		0.0,
		6.0,
		18,
		nombre=_("Escalera principal"),
		ancho=1.2,
		pasamanos="ambos",
		boca_arriba=(10.2, 8.6),
		rumbo_arriba=180.0,
		descripcion=_(
			"Dos tramos de nueve peldaños con un rellano en medio. Se sube por la izquierda y arriba se sale mirando al pasillo."
		),
	)
	ed.crear_ascensor(
		entorno,
		[baja, primera],
		(12.0, 7.4),
		0.0,
		nombre=_("Ascensor"),
		descripcion=_("Avisa de la planta con voz. La puerta está en la pared norte del pasillo."),
	)
	ed.fijar_inicio(entorno, baja, 4.0, 1.5, 0.0)
	return entorno


# ── 3. Barrio ────────────────────────────────────────────────────────────────


def barrio_ejemplo() -> Entorno:
	"""Barrio exterior: dos calles que se cruzan, pasos de peatones, parada y edificios.

	La Calle Mayor va de oeste a este y la Calle del Río de sur a norte. Hay
	un paso con semáforo sonoro y otro sin semáforo, una parada de autobús,
	tres edificios macizos con portal y un centro cívico con un vestíbulo
	al que se entra andando desde la acera.
	"""
	entorno = ed.crear_entorno(
		_("Barrio de ejemplo"),
		_("Un cruce de dos calles con sus aceras, dos pasos de peatones, una parada de autobús y varios edificios."),
		AUTOR_EJEMPLOS,
	)
	_procedencia(entorno)
	calle = ed.crear_planta(entorno, _("Calle"), nivel=0, exterior=True)

	mayor = ed.crear_calle(
		entorno,
		calle,
		_("Calle Mayor"),
		[(-40.0, 0.0), (40.0, 0.0)],
		ancho_calzada=7.0,
		ancho_acera=2.5,
		carriles=2,
		sentido="doble",
		trafico=2,
		velocidad_kmh=30.0,
		descripcion=_("Calle principal, con bastante tráfico en los dos sentidos."),
	)
	rio = ed.crear_calle(
		entorno,
		calle,
		_("Calle del Río"),
		[(0.0, -30.0), (0.0, 30.0)],
		ancho_calzada=6.0,
		ancho_acera=2.0,
		carriles=1,
		sentido="ida",
		trafico=1,
		velocidad_kmh=20.0,
		descripcion=_("Calle tranquila de un solo sentido, hacia el norte."),
	)
	ed.crear_cruce(entorno, calle, mayor, rio)
	ed.crear_paso_peatones(
		entorno,
		calle,
		mayor,
		(-8.0, 0.0),
		semaforo=True,
		sonoro=True,
		pulsador=True,
		ancho=4.0,
		nombre=_("Paso con semáforo de Calle Mayor"),
		descripcion=_("Cruza la Calle Mayor al oeste del cruce. El semáforo pita cuando está verde para los peatones."),
	)
	ed.crear_paso_peatones(
		entorno,
		calle,
		rio,
		(0.0, 9.0),
		ancho=4.0,
		nombre=_("Paso sin semáforo de Calle del Río"),
		descripcion=_("Cruza la Calle del Río al norte del cruce. No tiene semáforo: hay que escuchar el tráfico."),
	)
	ed.crear_parada(
		entorno,
		calle,
		_("Parada de autobús Calle Mayor"),
		15.0,
		4.0,
		descripcion=_("Marquesina en la acera norte, con banco. Paran las líneas 3 y 7."),
	)

	ed.crear_edificio(
		entorno,
		calle,
		_("Edificio de viviendas"),
		5.0,
		6.0,
		20.0,
		14.0,
		portal_lado="sur",
		portal_desplazamiento=4.0,
		portal_nombre=_("Portal número 12"),
		descripcion=_("Bloque de pisos en la esquina noreste."),
	)
	ed.crear_edificio(
		entorno,
		calle,
		_("Mercado"),
		-25.0,
		6.0,
		20.0,
		14.0,
		portal_lado="sur",
		portal_desplazamiento=9.0,
		portal_ancho=2.0,
		portal_nombre=_("Puerta del mercado"),
		descripcion=_("Mercado cubierto en la esquina noroeste."),
	)
	ed.crear_edificio(
		entorno,
		calle,
		_("Oficina de correos"),
		-25.0,
		-20.0,
		20.0,
		14.0,
		portal_lado="este",
		portal_desplazamiento=8.0,
		portal_nombre=_("Puerta de correos"),
		descripcion=_("En la esquina suroeste; su puerta da a la Calle del Río."),
	)

	vestibulo = ed.crear_habitacion_rectangular(
		entorno,
		calle,
		_("Vestíbulo del centro cívico"),
		5.0,
		-12.0,
		6.0,
		6.0,
		tipo="vestibulo",
		suelo="baldosa",
		descripcion=_("Sala amplia a la que se entra desde la acera sur de la Calle Mayor."),
	)
	ed.crear_manzana(
		entorno,
		calle,
		_("Centro cívico"),
		[(5.0, -20.0), (25.0, -20.0), (25.0, -6.0), (11.0, -6.0), (11.0, -12.0), (5.0, -12.0)],
		descripcion=_("El resto del edificio del centro cívico, en la esquina sureste."),
	)
	ed.anadir_puerta(
		entorno,
		calle,
		vestibulo,
		"norte",
		desplazamiento=2.0,
		ancho=1.6,
		tipo="portal",
		estado="abierta",
		hoja="automatica",
		material="cristal",
		es_salida=True,
		nombre=_("Portal del centro cívico"),
		descripcion=_("Une la acera con el vestíbulo. Al cruzarlo cambia el sonido de calle a interior."),
	)
	ed.anadir_fuente(
		entorno,
		calle,
		_("Reloj del centro cívico"),
		10.7,
		-9.0,
		"reloj",
		volumen=0.4,
		radio=6.0,
		altura=2.0,
		descripcion=_("En la pared este del vestíbulo."),
	)
	ed.anadir_referencia(
		entorno,
		calle,
		_("Mostrador del centro cívico"),
		8.0,
		-10.5,
		tipo="punto",
		descripcion=_("Al fondo del vestíbulo, frente al portal."),
	)

	ed.anadir_fuente(
		entorno,
		calle,
		_("Terraza de la cafetería"),
		12.0,
		5.5,
		"cafeteria",
		volumen=0.5,
		radio=12.0,
		descripcion=_("Voces y tazas en la acera norte, pegada al edificio de viviendas."),
	)
	ed.anadir_fuente(
		entorno,
		calle,
		_("Fuente de la esquina"),
		-4.0,
		-5.0,
		"fuente_agua",
		volumen=0.5,
		radio=10.0,
		descripcion=_("Una fuente de beber en la esquina suroeste del cruce."),
	)
	ed.anadir_referencia(
		entorno,
		calle,
		_("Buzón de correos"),
		-4.5,
		-12.0,
		tipo="mobiliario",
		descripcion=_("En la acera oeste de la Calle del Río, junto a la puerta de correos."),
	)
	ed.anadir_referencia(
		entorno, calle, _("Quiosco"), -18.0, 5.2, tipo="comercio", descripcion=_("En la acera norte de la Calle Mayor, pegado al mercado.")
	)
	_mobiliario_del_barrio(calle)
	ed.fijar_inicio(entorno, calle, -20.0, 4.5, 90.0)
	return entorno


def _mobiliario_del_barrio(calle: Planta) -> None:
	"""Sugerencias de mobiliario urbano del barrio: lo que suele haber en una calle así.

	El bordillo de la Calle Mayor está en y = ±3,5 y las fachadas en y = ±6;
	lo que va junto al bordillo deja libre el lado de la fachada, que es por
	donde se camina siguiendo la pared.
	"""
	norte, sur, este, oeste = 0.0, 180.0, 90.0, 270.0
	# Paso de peatones con semáforo (x de -10 a -6): franja de botones en cada boca y el poste al lado.
	_sugerir(calle, -8.0, 3.8, sur, "pavimento botones", "pavimento tactil de botones")
	_sugerir(calle, -8.0, -3.8, norte, "pavimento botones", "pavimento tactil de botones")
	_sugerir(calle, -5.6, 3.75, sur, "semaforo peatones", "semaforo")
	_sugerir(calle, -5.6, -3.75, norte, "semaforo peatones", "semaforo")
	# Paso sin semáforo de la Calle del Río (y de 7 a 11).
	_sugerir(calle, 3.3, 9.0, oeste, "pavimento botones", "pavimento tactil de botones")
	_sugerir(calle, -3.3, 9.0, este, "pavimento botones", "pavimento tactil de botones")
	# Farolas y árboles junto al bordillo de la Calle Mayor.
	for x in (-34.0, -22.0, -12.0, 9.0, 21.0, 33.0):
		_sugerir(calle, x, 3.75, sur, "farola")
		_sugerir(calle, x + 3.0, -3.75, norte, "farola")
	for x in (-28.0, -17.5, 30.5):
		_sugerir(calle, x, 3.9, sur, "alcorque", "arbol")
	for x, y in ((3.3, 3.8), (-3.3, 3.8), (3.3, -3.8), (-3.3, -3.8)):
		_sugerir(calle, x, y, norte, "bolardo")
	# Parada de autobús: marquesina contra la fachada, poste y panel junto al bordillo.
	_sugerir(calle, 15.0, 5.2, sur, "marquesina", "banco")
	_sugerir(calle, 17.9, 3.75, sur, "poste parada")
	_sugerir(calle, 12.2, 3.75, sur, "panel sonoro")
	_sugerir(calle, 19.5, 5.8, sur, "papelera")
	_sugerir(calle, 22.9, 5.675, sur, "banco")
	# Terraza de la cafetería y obstáculos de todos los días en la acera norte.
	_sugerir(calle, 11.3, 5.65, sur, "mesa alta")
	_sugerir(calle, 6.5, 3.95, este, "moto")
	_sugerir(calle, -11.5, 5.42, sur, "patinetes")
	_sugerir(calle, -22.0, 5.4, sur, "toldo bajo")
	_sugerir(calle, -31.0, 5.75, sur, "jardinera")
	# Contenedores en la calzada, pegados al bordillo norte, y vehículos aparcados en el sur.
	_sugerir(calle, 25.5, 2.9, norte, "contenedor resto", "contenedor")
	_sugerir(calle, 27.135, 2.7, norte, "contenedor envases")
	_sugerir(calle, 28.885, 2.6, norte, "contenedor vidrio")
	_sugerir(calle, -15.0, -2.5, este, "coche")
	_sugerir(calle, -27.5, -2.4, este, "furgoneta")
	# Acera sur: obra, tapa de alcantarilla y un cubo que alguien ha sacado.
	_sugerir(calle, 33.0, -4.3, norte, "valla obra")
	_sugerir(calle, 30.8, -4.2, norte, "cono")
	_sugerir(calle, 14.0, -4.6, norte, "tapa alcantarilla")
	_sugerir(calle, -30.0, -5.6, norte, "contenedor 240")
	_sugerir(calle, -36.0, -3.75, norte, "poste taxi")
	# Calle del Río: el buzón y la fuente que ya se anuncian como referencias.
	_sugerir(calle, -4.75, -13.6, este, "buzon")
	_sugerir(calle, -4.4, -5.0, este, "fuente beber", "fuente")
	# Vestíbulo del centro cívico.
	_sugerir(calle, 8.0, -10.8, norte, "mostrador recepcion", "mostrador", ambito="interior")
	_sugerir(calle, 10.7, -9.0, oeste, "sillas espera", "banco", ambito="interior")
	_sugerir(calle, 5.225, -11.775, norte, "planta de interior", "planta", ambito="interior")


# ── Conjunto ─────────────────────────────────────────────────────────────────

# Nombre de fichero (sin extensión) → función que construye el entorno.
EJEMPLOS: dict[str, Callable[[], Entorno]] = {
	"vivienda-de-ejemplo": vivienda_ejemplo,
	"centro-de-dos-plantas": centro_dos_plantas,
	"barrio-de-ejemplo": barrio_ejemplo,
}


def todos() -> dict[str, Entorno]:
	"""Construye los tres ejemplos: nombre de fichero → entorno."""
	return {nombre: construir() for nombre, construir in EJEMPLOS.items()}


def _buscar_exacto(catalogo: Catalogo, palabras: Sequence[str], ambito: str, preferidos: Sequence[str]) -> DefObjeto | None:
	"""Objeto cuyo id, nombre o alguna etiqueta coincide con una de las palabras (sin tildes ni mayúsculas)."""
	orden = {id_complemento: puesto for puesto, id_complemento in enumerate(preferidos)}
	for palabra in palabras:
		clave = sin_acentos(palabra)
		candidatos = catalogo.buscar(palabra, ambito=ambito)
		candidatos.sort(key=lambda definicion: orden.get(definicion.complemento, len(orden)))
		for definicion in candidatos:
			nombres = {sin_acentos(definicion.id.replace("_", " ").replace("-", " ")), sin_acentos(definicion.nombre)}
			nombres.update(sin_acentos(etiqueta) for etiqueta in definicion.etiquetas)
			if clave in nombres:
				return definicion
	return None


def amueblar_mobiliario(entorno: Entorno, planta: Planta, espacio: Espacio, catalogo: Catalogo) -> list[Objeto]:
	"""Coloca el mobiliario sugerido en ``datos["mobiliario"]`` de un espacio.

	Cada sugerencia se coloca solo si el catálogo tiene el objeto, cabe en su
	sitio sin errores y no tapa una puerta; si no, se deja pasar sin más.
	"""
	colocados: list[Objeto] = []
	for sugerencia in espacio.datos.get("mobiliario") or []:
		if not isinstance(sugerencia, dict):
			continue
		ambito = str(sugerencia.get("ambito") or "exterior")
		preferidos = PREFERIDOS_INTERIOR if ambito == "interior" else PREFERIDOS_EXTERIOR
		definicion = _buscar_exacto(catalogo, [str(p) for p in sugerencia.get("palabras") or []], ambito, preferidos)
		if definicion is None:
			continue
		try:
			x, y, rumbo = float(sugerencia["x"]), float(sugerencia["y"]), float(sugerencia.get("rumbo", 0.0))
		except KeyError, TypeError, ValueError:
			continue
		resultado = colocar_en_punto(entorno, planta, definicion.tipo, catalogo, x, y, rumbo)
		if not resultado.colocado or resultado.objeto is None:
			continue
		if any(aviso.codigo == "tapa_abertura" for aviso in resultado.avisos):
			planta.objetos.remove(resultado.objeto)
			continue
		colocados.append(resultado.objeto)
	return colocados


def amueblar_ejemplos(entorno: Entorno, catalogo: Catalogo) -> list[Objeto]:
	"""Amuebla los espacios que declaran su uso o su mobiliario, con lo que haya en el catálogo.

	Los interiores con ``datos["uso"]`` se amueblan con el amueblado asistido
	(prefiriendo el complemento propio de cada uso: el de colegio en un aula,
	el de oficina en un despacho, el de hogar en lo demás) y los espacios con
	``datos["mobiliario"]``, con sus sugerencias.

	Devuelve los objetos colocados (lista vacía si no hay complementos instalados).
	"""
	colocados: list[Objeto] = []
	if catalogo.vacio:
		return colocados
	for planta in entorno.plantas:
		for espacio in list(planta.espacios):
			if espacio.macizo:
				continue
			uso = espacio.datos.get("uso")
			if uso in USOS:
				preferidos = PREFERIDOS_POR_USO.get(uso, PREFERIDOS_INTERIOR)
				colocados.extend(amueblar_espacio(entorno, planta, espacio, uso, catalogo, preferidos=preferidos))
			if espacio.datos.get("mobiliario"):
				colocados.extend(amueblar_mobiliario(entorno, planta, espacio, catalogo))
	log.info("Entorno «%s» amueblado con %s objetos", entorno.nombre, len(colocados))
	return colocados
