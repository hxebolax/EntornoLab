"""Importación de OpenStreetMap con datos REALES guardados: la Plaza Mayor de Valladolid.

Las pruebas de ``test_importar_osm.py`` usan datos ficticios. Estas usan una
respuesta real de Nominatim y otra de Overpass (150 metros alrededor de la
plaza), descargadas una sola vez con el cliente de la aplicación y guardadas
en ``tests/datos/osm_real_valladolid_*``; la atribución y la consulta están en
``osm_real_valladolid_ATRIBUCION.txt``. Ninguna prueba sale a la red: las
descargas se sustituyen por funciones que devuelven esos ficheros.

Datos: © colaboradores de OpenStreetMap, licencia ODbL.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.dominio import geometria as geo
from app.dominio.modelo import hay_errores
from app.dominio.validacion import validar
from app.importar import formas, osm
from app.importar.osm_conversion import nombre_de_obstaculo
from tests.test_motor_comun import Robot, registros, texto, voces

DATOS = Path(__file__).parent / "datos"
NOMINATIM = DATOS / "osm_real_valladolid_nominatim.json"
OVERPASS = DATOS / "osm_real_valladolid_overpass.json"
ATRIBUCION = DATOS / "osm_real_valladolid_ATRIBUCION.txt"
# El primer resultado de Nominatim para «Plaza Mayor, Valladolid» (way/24432960).
LAT, LON = 41.6520609, -4.7285484
RADIO = 150.0


def _datos_como_descargados() -> dict:
	"""La respuesta guardada de Overpass con lo que le añade ``descargar_zona`` (recuadro y centro)."""
	datos = osm.importar_fichero_osm(OVERPASS)
	datos["recuadro"] = list(osm.recuadro_de(LAT, LON, RADIO))
	datos["centro"] = [LAT, LON]
	return datos


@pytest.fixture(scope="module")
def plaza():
	"""La zona real ya convertida (una vez para todo el módulo)."""
	return osm.convertir(_datos_como_descargados(), osm.OpcionesOSM(nombre="Plaza Mayor de Valladolid"))


def _espacios(resultado, tipo: str) -> list:
	return [e for e in resultado.entorno.plantas[0].espacios if e.tipo == tipo]


# ── La muestra y el camino de red, sin red ───────────────────────────────────


def test_la_muestra_lleva_su_atribucion() -> None:
	texto_atribucion = ATRIBUCION.read_text(encoding="utf-8")
	assert (
		"© colaboradores de OpenStreetMap, datos disponibles bajo la licencia ODbL (https://www.openstreetmap.org/copyright)"
		in texto_atribucion
	)
	assert "Fecha de descarga: 2026-11-26" in texto_atribucion
	assert osm.consulta_overpass(osm.recuadro_de(LAT, LON, RADIO)) in texto_atribucion
	crudo = json.loads(OVERPASS.read_text(encoding="utf-8"))
	assert "ODbL" in crudo["osm3s"]["copyright"]


def test_busqueda_real_sin_red(data_temporal: Path) -> None:
	peticiones: list[str] = []

	def descargar(url: str, datos: bytes | None = None) -> bytes:
		peticiones.append(url)
		return NOMINATIM.read_bytes()

	osm._limitador_nominatim.intervalo = 0.0
	try:
		candidatos = osm.buscar_lugar("Plaza Mayor, Valladolid", 5, descargar=descargar)
	finally:
		osm._limitador_nominatim.intervalo = osm.INTERVALO_NOMINATIM
	assert peticiones == [osm.NOMINATIM]
	assert len(candidatos) == 5
	primero = candidatos[0]
	assert (primero.nombre, primero.osm, primero.tipo) == ("Plaza Mayor", "way/24432960", "square")
	assert (primero.lat, primero.lon) == (LAT, LON)
	assert primero.descripcion.startswith("Plaza Mayor, Valladolid")


def test_descarga_real_sin_red(data_temporal: Path) -> None:
	def descargar(url: str, datos: bytes | None = None) -> bytes:
		assert datos is not None and datos.startswith(b"data=")
		return OVERPASS.read_bytes()

	datos = osm.descargar_zona(LAT, LON, RADIO, servidores=("https://overpass.invalid/api",), descargar=descargar, usar_cache=False)
	assert len(datos["elements"]) == 2488
	assert datos["centro"] == [LAT, LON]
	assert datos["recuadro"] == pytest.approx(list(osm.recuadro_de(LAT, LON, RADIO)))
	assert datos["osm3s"]["timestamp_osm_base"] == "2026-11-26T16:43:51Z"


# ── Conversión ───────────────────────────────────────────────────────────────


def test_conversion_con_calles_reales(plaza) -> None:
	planta = plaza.entorno.plantas[0]
	nombres = {via.nombre for via in planta.vias}
	for calle in (
		"Calle de la Cebadería",
		"Calle de Quiñones",
		"Calle del Duque de la Victoria",
		"Calle de la Lonja",
		"Calle de la Especería",
		"Calle de Correos",
	):
		assert calle in nombres
	cuentas = plaza.informe.cuentas
	assert cuentas["vias"] == 16 and cuentas["cruces"] == 5 and cuentas["pasos"] == 7
	assert cuentas["edificios"] == 133 and cuentas["portales"] >= 150
	assert len(_espacios(plaza, "acera")) >= 20
	assert len(_espacios(plaza, "paso_peatones")) == 7
	procedencia = plaza.entorno.procedencia
	assert procedencia["atribucion"] == "© colaboradores de OpenStreetMap"
	assert procedencia["fecha_datos"] == "2026-11-26T16:43:51Z"


def test_la_plaza_mayor_es_una_sola_zona(plaza) -> None:
	# Es una vía peatonal cerrada con place=square: tiene que salir como zona, no también como franja de borde.
	desde_la_plaza = [e for e in plaza.entorno.plantas[0].espacios if e.datos.get("osm") in ("way/24432960", ["way/24432960"])]
	assert len(desde_la_plaza) == 1
	assert desde_la_plaza[0].tipo == "plaza" and desde_la_plaza[0].suelo == "baldosa"
	assert geo.area(desde_la_plaza[0].contorno) > 9000.0
	assert desde_la_plaza[0].contiene(0.0, 0.0)


def test_no_entra_el_borde_de_una_plaza_de_fuera(plaza) -> None:
	# La Plaza de la Fuente Dorada queda fuera del recuadro salvo una tira de 3,7 metros cuadrados.
	assert not [e for e in plaza.entorno.plantas[0].espacios if "Fuente Dorada" in e.nombre]


def test_los_paneles_no_se_llaman_como_lo_que_explican(plaza) -> None:
	nombres = {o.nombre for o in plaza.entorno.plantas[0].objetos}
	assert "Panel de información «Iglesia de Santiago»" in nombres
	assert "Iglesia de Santiago" not in nombres
	assert nombre_de_obstaculo("Fuente para beber", "Fuente de la plaza") == "Fuente de la plaza"
	assert nombre_de_obstaculo("Banco", "") == "Banco"


def test_validacion_sin_errores_ni_medianeras_solapadas(plaza) -> None:
	avisos = validar(plaza.entorno)
	assert not hay_errores(avisos), [str(a) for a in avisos if a.es_error]
	# Sin el ajuste de medianeras salían 17 parejas de edificios que se pisaban de 1 a 9 centímetros cuadrados.
	assert not [a for a in avisos if a.codigo == "espacios_solapados"]
	assert len(avisos) <= 12


def test_ajustar_medianeras_quita_el_solape_de_unos_centimetros() -> None:
	uno = [(0.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0)]
	otro = [(9.9, 2.0), (20.0, 2.0), (20.0, 8.0), (9.95, 8.0)]
	assert geo.area_interseccion(uno, otro) > 0.01
	a, b = formas.ajustar_medianeras([uno, otro])
	assert geo.area_interseccion(a, b) < 0.01
	assert a == uno
	# Un solape grande no es una medianera mal dibujada: no se toca.
	lejos = [(5.0, 2.0), (20.0, 2.0), (20.0, 8.0), (5.0, 8.0)]
	assert formas.ajustar_medianeras([uno, lejos])[1] == lejos


# ── Recorrido con el motor ───────────────────────────────────────────────────


def _paso(plaza, nombre: str):
	paso = next(e for e in _espacios(plaza, "paso_peatones") if e.nombre == nombre)
	(a, b), rumbo = paso.datos["extremos"], paso.datos["rumbo_cruce"]
	ux, uy = geo.vector_rumbo(rumbo)
	return paso, (a[0] - ux * 1.5, a[1] - uy * 1.5), (b[0] + ux * 1.5, b[1] + uy * 1.5), rumbo


def _cruzar(robot: Robot, paso, hasta, rumbo: float) -> list:
	robot.girar_a(rumbo)
	nuevos: list = []
	for _i in range(20):
		nuevos += robot.pulsar("avanzar")
		if robot.espacio != paso.nombre and geo.distancia(robot.pos, hasta) < 1.0:
			break
	return nuevos


def test_el_alumno_anda_por_la_acera_y_sabe_en_que_calle_esta(plaza) -> None:
	robot = Robot(plaza.entorno)
	assert robot.espacio == "Acera sur de Calle de la Cebadería"
	dicho = voces(robot.pulsar("donde_estoy"))
	assert len(dicho) == 1 and dicho[0].startswith("Estás en Acera sur de Calle de la Cebadería, mirando al ")
	# Empieza mirando a lo largo de la calle (antes miraba al este, hacia la calzada):
	# anda por la acera sin salirse ni chocar.
	for _i in range(8):
		robot.pulsar("avanzar")
		assert robot.espacio == "Acera sur de Calle de la Cebadería"
	assert not registros(robot.eventos, "choque")


@pytest.mark.lento
def test_el_alumno_llega_a_un_paso_y_cruza_la_calle(plaza) -> None:
	planta = plaza.entorno.plantas[0]
	paso, desde, hasta, rumbo = _paso(plaza, "Paso sin semáforo de Calle de Quiñones")
	robot = Robot(plaza.entorno)
	assert robot.recorrer((planta.id, desde[0], desde[1]), cerca=0.6)
	assert robot.espacio == "Acera oeste de Calle de Quiñones"
	assert not registros(robot.eventos, "choque")
	assert "Calle de Quiñones" in voces(robot.pulsar("donde_estoy"))[0]
	nuevos = _cruzar(robot, paso, hasta, rumbo)
	assert robot.espacio == "Acera este de Calle de Quiñones"
	assert registros(nuevos, "cruce_empieza")[0]["por_paso"] is True
	cruce = registros(nuevos, "cruce")[0]
	assert cruce["paso"] == paso.id and cruce["por_paso"] is True and cruce["seguro"] is True
	dicho = texto(nuevos)
	assert "Paso sin semáforo de Calle de Quiñones." in dicho and "Bordillo a nivel, sin escalón." in dicho
	assert "Acera este de Calle de Quiñones" in voces(robot.pulsar("donde_estoy"))[0]


@pytest.mark.lento
def test_el_alumno_espera_el_verde_y_cruza(plaza) -> None:
	planta = plaza.entorno.plantas[0]
	paso, desde, hasta, rumbo = _paso(plaza, "Paso con semáforo de Calle del Duque de la Victoria")
	robot = Robot(plaza.entorno)
	assert robot.recorrer((planta.id, desde[0], desde[1]), cerca=0.6)
	assert robot.espacio == "Acera oeste de Calle del Duque de la Victoria"
	# El paso tiene semáforo sonoro en el mapa, con los tiempos de serie: se espera al verde.
	assert robot.esperar_hasta(lambda: robot.sesion.dinamica.fase(paso.id) == "verde", 80.0)
	nuevos = _cruzar(robot, paso, hasta, rumbo)
	assert robot.espacio == "Acera este de Calle del Duque de la Victoria"
	cruce = registros(nuevos, "cruce")[0]
	assert cruce["fase"] == "verde" and cruce["seguro"] is True and cruce["en_rojo"] is False
	assert "Con señal sonora." in texto(nuevos)
