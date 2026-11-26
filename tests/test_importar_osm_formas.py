"""Pruebas de la conversión de OpenStreetMap con trazados difíciles.

Los mapas reales no son cruces de manual: hay rotondas, calles que se salen
del recuadro, curvas cerradas, calles en T, edificios con patio dibujados
como multipolígono, aceras dibujadas como vías aparte y pasos de peatones
dibujados solo como una línea. Aquí se fabrica una zona ficticia con todo eso
y se comprueba que la importación no falla y deja un entorno sin errores.
"""

from __future__ import annotations

import math

import pytest

from app.dominio.modelo import hay_errores
from app.dominio.validacion import validar
from app.importar import osm

LAT0, LON0 = 41.5, 2.1
M_GRADO = math.pi * 6371008.8 / 180.0
KX = M_GRADO * math.cos(math.radians(LAT0))


class _Mapa:
	"""Construye datos de OpenStreetMap ficticios a partir de coordenadas en metros."""

	def __init__(self) -> None:
		self.elementos: list[dict] = []
		self._siguiente = 1

	def nodo(self, x: float, y: float, **etiquetas: str) -> int:
		identificador = self._siguiente
		self._siguiente += 1
		elemento: dict = {"type": "node", "id": identificador, "lat": LAT0 + y / M_GRADO, "lon": LON0 + x / KX}
		if etiquetas:
			elemento["tags"] = {clave.replace("__", ":"): valor for clave, valor in etiquetas.items()}
		self.elementos.append(elemento)
		return identificador

	def etiquetar(self, nodo: int, **etiquetas: str) -> None:
		elemento = next(e for e in self.elementos if e["type"] == "node" and e["id"] == nodo)
		elemento["tags"] = dict(etiquetas)

	def via(self, nodos: list[int], **etiquetas: str) -> int:
		identificador = self._siguiente
		self._siguiente += 1
		self.elementos.append(
			{
				"type": "way",
				"id": identificador,
				"nodes": nodos,
				"tags": {clave.replace("__", ":"): valor for clave, valor in etiquetas.items()},
			}
		)
		return identificador

	def linea(self, puntos: list[tuple[float, float]], **etiquetas: str) -> list[int]:
		nodos = [self.nodo(x, y) for x, y in puntos]
		self.via(nodos, **etiquetas)
		return nodos

	def area(self, puntos: list[tuple[float, float]], **etiquetas: str) -> list[int]:
		nodos = [self.nodo(x, y) for x, y in puntos]
		self.via(nodos + [nodos[0]], **etiquetas)
		return nodos

	def relacion(self, miembros: list[tuple[int, str]], **etiquetas: str) -> None:
		self.elementos.append(
			{
				"type": "relation",
				"id": self._siguiente,
				"members": [{"type": "way", "ref": via, "role": papel} for via, papel in miembros],
				"tags": dict(etiquetas),
			}
		)
		self._siguiente += 1

	def datos(self, medio_lado: float) -> dict:
		return {
			"elements": self.elementos,
			"centro": [LAT0, LON0],
			"recuadro": [LAT0 - medio_lado / M_GRADO, LON0 - medio_lado / KX, LAT0 + medio_lado / M_GRADO, LON0 + medio_lado / KX],
		}


@pytest.fixture(scope="module")
def zona():
	"""Zona ficticia de 300 por 300 metros con un poco de todo, ya convertida."""
	mapa = _Mapa()
	# Rotonda de 12 metros de radio con tres calles que llegan a ella.
	anillo = [mapa.nodo(12 * math.cos(math.radians(a)), 12 * math.sin(math.radians(a))) for a in range(0, 360, 30)]
	mapa.via(anillo + [anillo[0]], highway="tertiary", junction="roundabout", name="Glorieta de la Fuente")
	este = [anillo[0], mapa.nodo(60, 0), mapa.nodo(400, 0)]  # se sale del recuadro
	mapa.via(este, highway="secondary", name="Avenida del Este", lanes="2", sidewalk="both", maxspeed="50")
	norte_1 = [anillo[3], mapa.nodo(0, 50, highway="crossing", crossing="uncontrolled", tactile_paving="no", kerb="raised")]
	norte_2 = [norte_1[-1], mapa.nodo(0, 90), mapa.nodo(5, 130)]
	# La misma calle partida en dos vías del mapa: tiene que quedar como una sola.
	mapa.via(norte_1, highway="residential", name="Calle del Norte", sidewalk="right")
	mapa.via(norte_2, highway="residential", name="Calle del Norte", sidewalk="right")
	oeste = [anillo[6], mapa.nodo(-50, 0), mapa.nodo(-80, 5), mapa.nodo(-82, 40), mapa.nodo(-60, 45), mapa.nodo(-58, 20)]  # curvas cerradas
	mapa.via(oeste, highway="residential", name="Calle Revuelta", oneway="-1", surface="sett")
	# Calle en T contra la avenida, sin nombre, y un callejón de servicio.
	cruce_dibujado = mapa.nodo(60, -40)
	mapa.via([este[1], cruce_dibujado, mapa.nodo(60, -70)], highway="residential")
	mapa.linea([(100, 0.0), (100, 40)], highway="service", access="private")
	# Acera dibujada como vía aparte junto a la calle en T, y un paso dibujado solo como línea
	# (su nodo central es de la calle, pero no lleva la etiqueta de paso).
	mapa.linea([(65, -10), (65, -65)], highway="footway", footway="sidewalk", surface="paving_stones")
	mapa.via(
		[mapa.nodo(55, -40), cruce_dibujado, mapa.nodo(65, -40)],
		highway="footway",
		footway="crossing",
		crossing="traffic_signals",
		traffic_signals__sound="no",
	)
	# Edificio con patio (multipolígono), edificio sin paredes, y uno que se corta a sí mismo.
	exterior = mapa.area([(20, 20), (50, 20), (50, 45), (20, 45)])
	via_exterior = mapa._siguiente - 1
	mapa.area([(30, 28), (40, 28), (40, 38), (30, 38)])
	via_interior = mapa._siguiente - 1
	mapa.relacion([(via_exterior, "outer"), (via_interior, "inner")], type="multipolygon", building="yes", name="Mercado central")
	assert exterior
	mapa.area([(-40, -40), (-20, -40), (-20, -25), (-40, -25)], building="roof")
	mapa.area([(-120, -120), (-100, -100), (-100, -120), (-120, -100)], building="yes")
	# Plaza peatonal, estanque, andén y fila de bolardos.
	mapa.area(
		[(-45, 60), (-15, 60), (-15, 100), (-45, 100)], highway="pedestrian", area="yes", name="Plaza del Reloj", surface="paving_stones"
	)
	mapa.area([(-38, 75), (-28, 75), (-28, 85), (-38, 85)], natural="water")
	mapa.linea([(20, -12), (45, -12)], public_transport="platform", bus="yes", name="Glorieta")
	mapa.linea([(-44, 59), (-30, 59), (-16, 59)], barrier="bollard")
	# Muro con hueco, rampa, sendero y una farola, un banco y una fuente.
	muro = mapa.linea([(-140, 20), (-110, 20), (-110, 60)], barrier="wall", height="2.5")
	mapa.etiquetar(muro[1], barrier="entrance")
	mapa.linea([(70, 30), (95, 55)], highway="footway", incline="8%", handrail="yes")
	mapa.linea([(-140, -60), (-90, -80), (-60, -130)], highway="path")
	mapa.nodo(30, 6, highway="street_lamp")
	mapa.nodo(-30, 70, amenity="bench")
	mapa.nodo(-20, 95, amenity="drinking_water")
	mapa.nodo(35, 15, amenity="pharmacy", name="Farmacia Central", addr__street="Avenida del Este", addr__housenumber="3")
	mapa.nodo(15, 8, railway="subway_entrance", name="Glorieta")
	return osm.convertir(mapa.datos(150.0), osm.OpcionesOSM(nombre="Zona enrevesada"))


def test_la_zona_dificil_se_importa_sin_errores(zona) -> None:
	entorno = zona.entorno
	avisos = validar(entorno)
	assert not hay_errores(avisos), [str(a) for a in avisos if a.es_error]
	planta = entorno.plantas[0]
	assert planta.espacio_en(entorno.inicio.x, entorno.inicio.y) is not None
	# Todo queda dentro del recuadro pedido, aunque la avenida siga 250 metros más.
	x0, y0, x1, y1 = planta.caja()
	assert x0 >= -150.5 and x1 <= 150.5 and y0 >= -150.5 and y1 <= 150.5
	assert zona.informe.a_texto()


def test_rotonda_y_calles_que_llegan_a_ella(zona) -> None:
	planta = zona.entorno.plantas[0]
	rotonda = next(e for e in planta.espacios if e.datos.get("forma") == "rotonda")
	assert rotonda.nombre == "Rotonda de Glorieta de la Fuente" and rotonda.tipo == "calzada"
	# El anillo del mapa (12 metros de radio, dibujado con 12 lados) más media calzada de un solo sentido.
	assert rotonda.area() == pytest.approx(3.0 * (12.0 + 4.875 / 2.0) ** 2, rel=0.01)
	vias = {via.nombre: via for via in planta.vias}
	assert vias["Glorieta de la Fuente"].sentido == "ida"
	assert vias["Avenida del Este"].velocidad_kmh == 50.0 and vias["Avenida del Este"].trafico == 2
	# Las dos vías del mapa con el mismo nombre son una sola calle.
	assert [via.nombre for via in planta.vias].count("Calle del Norte") == 1
	assert len(vias["Calle del Norte"].eje) >= 3
	assert vias["Calle Revuelta"].sentido == "vuelta"
	# Las aceras de la avenida no se meten en la rotonda.
	aceras = [e for e in planta.espacios if e.tipo == "acera" and e.datos.get("via") == vias["Avenida del Este"].id]
	assert aceras and all(min(x for x, _y in a.contorno) >= 12.0 for a in aceras)
	assert any("rotondas" in frase for frase in zona.informe.revisar)


def test_aceras_segun_lo_que_dice_el_mapa(zona) -> None:
	planta = zona.entorno.plantas[0]
	vias = {via.nombre: via.id for via in planta.vias}
	del_norte = [e for e in planta.espacios if e.tipo == "acera" and e.datos.get("via") == vias["Calle del Norte"]]
	# sidewalk=right: solo hay acera a la derecha del sentido del dibujo (al este de una calle que sube al norte).
	assert del_norte and {a.datos["lado"] for a in del_norte} == {"derecha"}
	assert all(a.centro()[0] > 0 for a in del_norte)
	assert any("Calle del Norte" in frase and "Sin acera" in frase for frase in zona.informe.importado)
	# La calle sin nombre tiene la acera dibujada aparte: no se le deducen otras encima.
	dibujadas = [e for e in planta.espacios if e.tipo == "acera" and e.suelo == "baldosa"]
	assert len(dibujadas) == 1 and dibujadas[0].datos["origen"] == "mapa"
	sin_nombre = next(via for via in planta.vias if via.nombre.startswith("Calle residencial sin nombre"))
	assert dibujadas[0].datos["via"] == sin_nombre.id
	assert not any(e.datos.get("origen") == "deducida" and e.datos.get("via") == sin_nombre.id for e in planta.espacios)
	# La calle de curvas cerradas tiene aceras deducidas, y adoquín en la calzada.
	revuelta = [e for e in planta.espacios if e.datos.get("via") == vias["Calle Revuelta"]]
	assert any(e.tipo == "acera" and e.datos["origen"] == "deducida" for e in revuelta)
	assert next(e for e in revuelta if e.tipo == "calzada").suelo == "adoquin"
	assert any("Calle residencial sin nombre" in frase or "calle no tiene nombre" in frase for frase in zona.informe.falta)


def test_pasos_cruces_y_trafico_cerrado(zona) -> None:
	planta = zona.entorno.plantas[0]
	pasos = {e.nombre: e for e in planta.espacios if e.tipo == "paso_peatones"}
	sin_semaforo = pasos["Paso sin semáforo de Calle del Norte"]
	assert sin_semaforo.datos["segun_mapa"]["semaforo"] == "no"
	# Sin semáforo no puede haber señal sonora: eso se sabe, no hace falta que el mapa lo diga.
	assert sin_semaforo.datos["segun_mapa"]["sonoro"] == "no"
	assert "Sin pavimento táctil." in sin_semaforo.descripcion and "Bordillo alto" in sin_semaforo.descripcion
	assert sin_semaforo.datos["zonas"] == []
	# El paso dibujado solo como línea se reconoce por el nodo que comparte con la calzada.
	con_semaforo = next(e for nombre, e in pasos.items() if nombre.startswith("Paso con semáforo"))
	assert con_semaforo.datos["semaforo"] is True and con_semaforo.datos["sonoro"] is False
	assert con_semaforo.datos["segun_mapa"]["sonoro"] == "no" and con_semaforo.datos["segun_mapa"]["pulsador"] == "desconocido"
	cruces = [e for e in planta.espacios if e.datos.get("cruce") and e.datos.get("forma") != "rotonda"]
	assert [e.datos["forma"] for e in cruces] == ["t"]
	servicio = next(via for via in planta.vias if via.nombre.startswith("Vía de servicio"))
	assert servicio.trafico == 0 and "Cerrada al tráfico" in servicio.descripcion


def test_edificios_zonas_y_mobiliario(zona) -> None:
	planta = zona.entorno.plantas[0]
	espacios = {e.nombre: e for e in planta.espacios}
	assert espacios["Mercado central"].macizo and espacios["Mercado central"].area() == pytest.approx(750.0, rel=0.01)
	assert any("patio" in frase for frase in zona.informe.revisar)
	assert not espacios["Zona cubierta"].macizo and espacios["Zona cubierta"].datos["cubierta"]
	assert any("se corta a sí mismo" in frase for frase in zona.informe.avisos)
	assert espacios["Plaza del Reloj"].tipo == "plaza" and espacios["Plaza del Reloj"].suelo == "baldosa"
	assert espacios["Agua"].suelo == "agua"
	assert espacios["Rampa"].datos["rampa"] and espacios["Rampa"].datos["pendiente_pct"] == 8.0
	assert "peldanos" not in espacios["Rampa"].datos
	assert "Con pasamanos; en qué lado, el mapa no lo dice." in espacios["Rampa"].descripcion
	assert espacios["Sendero"].suelo == "tierra"
	nombres = sorted(o.nombre for o in planta.objetos)
	assert nombres.count("Bolardo") == 3 and "Farola" in nombres and "Banco" in nombres and "Fuente para beber" in nombres
	assert len([p for p in planta.paredes if p.nombre == "Muro"]) == 2
	hueco = next(a for a in planta.aberturas if a.tipo == "hueco")
	assert hueco.estado == "abierta" and hueco.centro() == pytest.approx((-110.0, 20.6), abs=0.7)
	paradas = sorted(r.nombre for r in planta.referencias if r.tipo == "parada")
	assert paradas == ["Boca de metro Glorieta", "Parada de autobús Glorieta"]
	farmacia = next(r for r in planta.referencias if r.nombre == "Farmacia Central")
	assert "Avenida del Este 3" in farmacia.descripcion
	# La fuente de beber es un obstáculo, no un sonido: no se inventan fuentes de sonido.
	assert planta.fuentes == []
