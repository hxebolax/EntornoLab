"""Pruebas de la importación de OpenStreetMap: red simulada, lectura de ficheros y conversión.

Los datos de ``tests/datos`` son FICTICIOS, escritos para estas pruebas: un
cruce de dos calles (una con aceras en el mapa y otra sin ese dato), un paso
con semáforo sonoro y otro sin ningún dato, un edificio con portal y número,
una parada, dos escaleras, una valla con cancela, un parque y un sendero.
Ninguna prueba sale a la red: las descargas se sustituyen por funciones falsas.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.dominio.catalogo import Catalogo
from app.dominio.formato import cargar_paquete, guardar_paquete
from app.dominio.modelo import hay_errores
from app.dominio.validacion import validar
from app.importar import osm
from app.importar.comun import ErrorImportacion, ImportacionCancelada
from app.importar.osm_conversion import forma_de_cruce, numero
from app.importar.osm_interiores import niveles_de

DATOS = Path(__file__).parent / "datos"


@pytest.fixture(scope="module")
def cruce():
	"""El cruce de prueba ya convertido (se convierte una vez para todo el módulo)."""
	return osm.convertir(osm.importar_fichero_osm(DATOS / "cruce.osm.json"), osm.OpcionesOSM(nombre="Cruce de prueba"))


def _espacios(resultado, tipo: str) -> list:
	return [e for e in resultado.entorno.plantas[0].espacios if e.tipo == tipo]


# ── Búsqueda y descarga, sin red ─────────────────────────────────────────────


def test_proyeccion_ida_y_vuelta() -> None:
	proyeccion = osm.Proyeccion(40.0, -3.7)
	x, y = proyeccion.a_xy(40.001, -3.699)
	assert x == pytest.approx(85.18, abs=0.05)
	assert y == pytest.approx(111.19, abs=0.05)
	lat, lon = proyeccion.a_latlon(x, y)
	assert (lat, lon) == pytest.approx((40.001, -3.699))


def test_recuadro_rechaza_zona_demasiado_grande() -> None:
	with pytest.raises(ErrorImportacion) as error:
		osm.recuadro_de(40.0, -3.7, osm.RADIO_MAXIMO_M + 1)
	assert "400" in str(error.value)
	with pytest.raises(ErrorImportacion):
		osm.recuadro_de(95.0, 0.0, 100)
	sur, oeste, norte, este = osm.recuadro_de(40.0, -3.7, 100)
	assert sur < 40.0 < norte and oeste < -3.7 < este


def test_consulta_overpass_pide_json_y_el_recuadro() -> None:
	consulta = osm.consulta_overpass((39.999, -3.701, 40.001, -3.699))
	assert consulta.startswith("[out:json]")
	assert "39.999000,-3.701000,40.001000,-3.699000" in consulta
	assert "multipolygon" in consulta


def test_buscar_lugar_usa_la_descarga_inyectada_y_la_cache(data_temporal: Path) -> None:
	llamadas: list[tuple[str, bytes | None]] = []
	respuesta = [
		{
			"lat": "40.0",
			"lon": "-3.7",
			"name": "Calle Mayor",
			"display_name": "Calle Mayor, Villaprueba, España",
			"type": "tertiary",
			"boundingbox": ["39.9", "40.1", "-3.8", "-3.6"],
			"osm_type": "way",
			"osm_id": 100,
		},
		{"display_name": "Sin coordenadas"},
	]

	def descargar(url: str, datos: bytes | None = None) -> bytes:
		llamadas.append((url, datos))
		return json.dumps(respuesta).encode("utf-8")

	osm._limitador_nominatim.intervalo = 0.0
	try:
		candidatos = osm.buscar_lugar("  Calle   Mayor ", descargar=descargar)
		otra_vez = osm.buscar_lugar("calle mayor", descargar=descargar)
	finally:
		osm._limitador_nominatim.intervalo = osm.INTERVALO_NOMINATIM
	assert len(candidatos) == 1
	assert candidatos[0].nombre == "Calle Mayor"
	assert (candidatos[0].lat, candidatos[0].lon) == (40.0, -3.7)
	assert candidatos[0].recuadro == (39.9, -3.8, 40.1, -3.6)
	assert len(otra_vez) == 1
	# La segunda búsqueda sale de la caché: una sola petición al servidor.
	assert len(llamadas) == 1
	assert llamadas[0][0] == osm.NOMINATIM
	assert b"q=Calle+Mayor" in (llamadas[0][1] or b"")
	assert list((data_temporal / "cache" / "osm").glob("nominatim-*.json"))


def test_buscar_lugar_exige_texto_y_traduce_los_fallos(data_temporal: Path) -> None:
	with pytest.raises(ErrorImportacion):
		osm.buscar_lugar("ab")

	def descargar(url: str, datos: bytes | None = None) -> bytes:
		raise OSError("sin conexión")

	osm._limitador_nominatim.intervalo = 0.0
	try:
		with pytest.raises(ErrorImportacion) as error:
			osm.buscar_lugar("plaza inexistente", descargar=descargar)
	finally:
		osm._limitador_nominatim.intervalo = osm.INTERVALO_NOMINATIM
	assert "sin conexión" in str(error.value)


def test_limitador_respeta_un_segundo_entre_peticiones() -> None:
	ahora = [100.0]
	dormido: list[float] = []

	def dormir(segundos: float) -> None:
		dormido.append(segundos)
		ahora[0] += segundos

	limitador = osm.LimitadorRitmo(1.0, reloj=lambda: ahora[0], dormir=dormir)
	limitador.esperar()
	assert dormido == []
	limitador.esperar()
	assert sum(dormido) == pytest.approx(1.0)
	ahora[0] += 5.0
	limitador.esperar()
	assert sum(dormido) == pytest.approx(1.0)


def test_descargar_zona_prueba_otro_servidor_y_guarda_cache(data_temporal: Path) -> None:
	mapa = json.loads((DATOS / "cruce.osm.json").read_text(encoding="utf-8"))
	llamadas: list[str] = []

	def descargar(url: str, datos: bytes | None = None) -> bytes:
		llamadas.append(url)
		assert datos is not None and datos.startswith(b"data=")
		if "primero" in url:
			raise OSError("servidor ocupado")
		if "segundo" in url:
			return b"<html>Too many requests</html>"
		return json.dumps({"elements": mapa["elements"]}).encode("utf-8")

	servidores = ("https://primero.invalid/api", "https://segundo.invalid/api", "https://tercero.invalid/api")
	avances: list[float] = []
	datos = osm.descargar_zona(
		40.0, -3.7, 80, servidores=servidores, descargar=descargar, progreso=lambda fraccion, texto: avances.append(fraccion)
	)
	assert len(llamadas) == 3
	assert len(datos["elements"]) == len(mapa["elements"])
	assert datos["centro"] == [40.0, -3.7]
	assert len(datos["recuadro"]) == 4
	assert avances[-1] == 1.0
	assert list((data_temporal / "cache" / "osm").glob("overpass-*.json"))
	# La segunda vez no se llama a ningún servidor.
	de_cache = osm.descargar_zona(40.0, -3.7, 80, servidores=servidores, descargar=descargar)
	assert len(llamadas) == 3
	assert len(de_cache["elements"]) == len(mapa["elements"])


def test_descargar_zona_explica_el_fallo_de_todos_los_servidores(data_temporal: Path) -> None:
	def descargar(url: str, datos: bytes | None = None) -> bytes:
		return json.dumps({"elements": [], "remark": "runtime error: Query timed out in query at line 1"}).encode("utf-8")

	with pytest.raises(ErrorImportacion) as error:
		osm.descargar_zona(40.0, -3.7, 80, servidores=("https://uno.invalid/api",), descargar=descargar, usar_cache=False)
	assert "uno.invalid" in str(error.value)
	with pytest.raises(ErrorImportacion):
		osm.descargar_zona(40.0, -3.7, 5000, descargar=descargar)


def test_descargar_zona_se_puede_cancelar(data_temporal: Path) -> None:
	def descargar(url: str, datos: bytes | None = None) -> bytes:
		raise AssertionError("no debe llegar a descargar")

	with pytest.raises(ImportacionCancelada):
		osm.descargar_zona(
			40.0, -3.7, 80, servidores=("https://uno.invalid/api",), descargar=descargar, usar_cache=False, cancelado=lambda: True
		)


# ── Lectura de ficheros ──────────────────────────────────────────────────────


def test_importar_fichero_xml_y_json_dan_lo_mismo() -> None:
	de_json = osm.importar_fichero_osm(DATOS / "cruce.osm.json")
	de_xml = osm.importar_fichero_osm(DATOS / "cruce.osm")
	assert len(de_xml["elements"]) == len(de_json["elements"])
	assert de_xml["recuadro"] == pytest.approx(de_json["recuadro"])
	uno = osm.convertir(de_json).entorno.plantas[0]
	otro = osm.convertir(de_xml).entorno.plantas[0]
	assert [e.nombre for e in uno.espacios] == [e.nombre for e in otro.espacios]
	assert len(uno.referencias) == len(otro.referencias)


def test_importar_fichero_rechaza_lo_que_no_es_osm(tmp_path: Path) -> None:
	texto = tmp_path / "notas.txt"
	texto.write_text("esto no es un mapa", encoding="utf-8")
	with pytest.raises(ErrorImportacion):
		osm.importar_fichero_osm(texto)
	otro = tmp_path / "otro.json"
	otro.write_text('{"cosas": []}', encoding="utf-8")
	with pytest.raises(ErrorImportacion):
		osm.importar_fichero_osm(otro)
	with pytest.raises(ErrorImportacion):
		osm.importar_fichero_osm(tmp_path / "no_existe.osm")
	malo = tmp_path / "malo.osm"
	malo.write_text(
		'<?xml version="1.0"?><!DOCTYPE osm [<!ENTITY x SYSTEM "file:///c:/windows/win.ini">]><osm><node id="1" lat="0" lon="0"/></osm>',
		encoding="utf-8",
	)
	with pytest.raises(ErrorImportacion):
		osm.importar_fichero_osm(malo)


# ── Conversión ───────────────────────────────────────────────────────────────


def test_utilidades_de_etiquetas() -> None:
	assert numero("3,5 m") == 3.5
	assert numero("30 mph") == 30.0
	assert numero("-8%") == -8.0
	assert numero("ancho") is None
	assert numero(None) is None
	assert niveles_de("0;1") == [0, 1]
	assert niveles_de("-1-1") == [-1, 0, 1]
	assert niveles_de("0.5") == [0]
	assert niveles_de("") == []
	assert forma_de_cruce([0, 90, 180, 270]) == "cruz"
	assert forma_de_cruce([0, 90, 180]) == "t"
	assert forma_de_cruce([0, 120, 240]) == "y"
	assert forma_de_cruce([0, 45, 180, 225]) == "aspa"
	assert forma_de_cruce([0, 72, 144, 216, 288]) == "complejo"


def test_calles_con_nombre_carriles_sentido_y_trafico(cruce) -> None:
	vias = {via.nombre: via for via in cruce.entorno.plantas[0].vias}
	assert set(vias) == {"Calle Mayor", "Calle del Río"}
	mayor, rio = vias["Calle Mayor"], vias["Calle del Río"]
	assert (mayor.carriles, mayor.sentido, mayor.trafico, mayor.velocidad_kmh) == (2, "doble", 2, 30.0)
	assert mayor.ancho == pytest.approx(6.4)
	assert "según el mapa" in mayor.descripcion
	assert (rio.carriles, rio.sentido, rio.trafico) == (1, "ida", 1)
	# Lo que el mapa no da se dice que es estimado.
	assert "estimado" in rio.descripcion
	assert "el mapa no lo dice" in rio.descripcion
	calzadas = [e for e in _espacios(cruce, "calzada") if not e.datos.get("cruce")]
	assert {e.datos["via"] for e in calzadas} == {mayor.id, rio.id}
	assert all(e.suelo == "asfalto" for e in calzadas)


def test_aceras_del_mapa_y_aceras_deducidas(cruce) -> None:
	aceras = _espacios(cruce, "acera")
	vias = {via.id: via.nombre for via in cruce.entorno.plantas[0].vias}
	del_mapa = [a for a in aceras if a.datos["origen"] == "mapa"]
	deducidas = [a for a in aceras if a.datos["origen"] == "deducida"]
	# Cada calle tiene dos aceras y el cruce las parte: cuatro tramos por calle.
	assert len(del_mapa) == 4
	assert len(deducidas) == 4
	assert {vias[a.datos["via"]] for a in del_mapa} == {"Calle Mayor"}
	assert {vias[a.datos["via"]] for a in deducidas} == {"Calle del Río"}
	assert {a.datos["lado"] for a in deducidas} == {"izquierda", "derecha"}
	assert all("deducida" in a.descripcion.lower() for a in deducidas)
	assert all(not a.cerrado and not a.macizo and a.datos["ancho"] > 0.5 for a in aceras)
	# Las aceras no invaden la calzada de la otra calle: ninguna cruza el centro del cruce.
	assert not any(a.contiene(0.0, 0.0) for a in aceras)
	assert any("DEDUCIDAS" in frase and "Calle del Río" in frase for frase in cruce.informe.deducido)
	assert cruce.informe.cuentas["aceras_mapa"] == 4


def test_cruce_con_su_forma(cruce) -> None:
	cruces = [e for e in _espacios(cruce, "calzada") if e.datos.get("cruce")]
	assert len(cruces) == 1
	assert cruces[0].datos["forma"] == "cruz"
	assert cruces[0].datos["ramas"] == 4
	assert len(cruces[0].datos["vias"]) == 2
	assert "Calle Mayor" in cruces[0].nombre and "Calle del Río" in cruces[0].nombre
	assert cruces[0].contiene(0.0, 0.0)


def test_paso_con_semaforo_sonoro(cruce) -> None:
	paso = next(e for e in _espacios(cruce, "paso_peatones") if "Calle Mayor" in e.nombre)
	datos = paso.datos
	assert datos["semaforo"] is True and datos["sonoro"] is True and datos["pulsador"] is True
	assert datos["vibracion"] is True and datos["isleta"] is False and datos["tactil"] is True
	assert datos["bordillo"] == "lowered"
	assert datos["segun_mapa"] == {
		"semaforo": "si",
		"sonoro": "si",
		"vibracion": "si",
		"pulsador": "si",
		"isleta": "no",
		"tactil": "si",
		"bordillo": "si",
	}
	assert "Con señal sonora." in paso.descripcion
	assert "Sin isleta." in paso.descripcion
	assert "el mapa no lo dice" in paso.descripcion  # los tiempos del semáforo
	assert datos["ciclo_estimado"] is True
	assert len(datos["zonas"]) == 2 and len(datos["referencias"]) == 2
	assert datos["longitud"] == pytest.approx(6.4)


def test_paso_sin_datos_dice_que_el_mapa_no_lo_dice(cruce) -> None:
	paso = next(e for e in _espacios(cruce, "paso_peatones") if "Calle del Río" in e.nombre)
	datos = paso.datos
	# Para el motor, lo desconocido es «no»; para la persona, «el mapa no lo dice».
	assert datos["semaforo"] is False and datos["sonoro"] is False and datos["pulsador"] is False
	assert set(datos["segun_mapa"].values()) == {"desconocido"}
	assert paso.descripcion.count("el mapa no lo dice") >= 7
	assert "Sin semáforo" not in paso.descripcion
	assert datos["zonas"] == []  # no se inventa pavimento táctil
	assert "ciclo" not in datos
	assert any(paso.nombre in frase and "semáforo" in frase for frase in cruce.informe.falta)


def test_edificio_macizo_con_portal_y_numero(cruce) -> None:
	planta = cruce.entorno.plantas[0]
	edificios = _espacios(cruce, "edificio")
	assert {e.nombre for e in edificios} == {"Edificio de viviendas", "Mercado"}
	assert all(e.macizo and e.cerrado for e in edificios)
	viviendas = next(e for e in edificios if e.nombre == "Edificio de viviendas")
	assert "4 plantas" in viviendas.descripcion
	portales = [a for a in planta.aberturas if a.tipo == "portal"]
	assert len(portales) == 1
	assert "número 12" in portales[0].nombre
	assert portales[0].ancho == pytest.approx(1.2)
	# El portal cae sobre la fachada sur del edificio, donde el mapa pone la entrada.
	assert portales[0].centro() == pytest.approx((20.0, 12.0), abs=0.05)
	assert "Calle Mayor" in portales[0].descripcion
	mercado = next(e for e in edificios if e.nombre == "Mercado")
	assert "mercado" in mercado.descripcion


def test_parada_escaleras_y_referencias(cruce) -> None:
	planta = cruce.entorno.plantas[0]
	paradas = [r for r in planta.referencias if r.tipo == "parada"]
	assert len(paradas) == 1
	assert paradas[0].nombre == "Parada de autobús Calle Mayor"
	assert "3, 7" in paradas[0].descripcion
	assert "Con marquesina." in paradas[0].descripcion and "Sin banco." in paradas[0].descripcion
	assert "Pavimento táctil: el mapa no lo dice." in paradas[0].descripcion
	escaleras = {e.nombre: e for e in _espacios(cruce, "escalera")}
	assert set(escaleras) == {"Escaleras", "Escaleras 2"}
	con_datos, sin_datos = escaleras["Escaleras"], escaleras["Escaleras 2"]
	assert con_datos.datos["peldanos"] == 12 and con_datos.datos["pasamanos"] == "ambos"
	assert con_datos.datos["sube_hacia"] == pytest.approx(180.0, abs=1.0)
	assert "12 peldaños." in con_datos.descripcion
	assert sin_datos.datos["peldanos"] is None
	assert "Número de peldaños: el mapa no lo dice." in sin_datos.descripcion
	assert not con_datos.cerrado
	comercios = {r.nombre: r for r in planta.referencias if r.tipo == "comercio"}
	assert comercios["Panadería La Espiga"].descripcion.startswith("Panadería.")
	assert "Farmacia" in comercios


def test_barreras_obstaculos_zonas_y_superficies(cruce) -> None:
	planta = cruce.entorno.plantas[0]
	assert len(planta.paredes) == 1
	valla = planta.paredes[0]
	assert valla.material == "valla" and valla.bloquea_paso and not valla.bloquea_sonido
	cancelas = [a for a in planta.aberturas if a.tipo == "puerta"]
	assert len(cancelas) == 1 and cancelas[0].nombre == "Cancela"
	assert "El mapa no dice" in cancelas[0].descripcion
	objetos = {o.nombre: o for o in planta.objetos}
	assert set(objetos) == {"Bolardo", "Banco"}
	# Sin catálogo quedan como cajas con nombre y medidas típicas, y recuerdan qué objeto serían.
	assert objetos["Bolardo"].tipo == "caja"
	assert objetos["Bolardo"].datos["tipo_previsto"] == "calle/bolardo"
	assert (objetos["Bolardo"].ancho, objetos["Bolardo"].alto) == (0.2, 0.9)
	# El árbol del mapa cae dentro del edificio: no cabe como obstáculo y queda como referencia.
	assert any(r.nombre == "Árbol" and r.tipo == "mobiliario" for r in planta.referencias)
	parque = next(e for e in planta.espacios if e.tipo == "parque")
	assert parque.nombre == "Parque del Río" and parque.suelo == "hierba"
	sendero = next(e for e in planta.espacios if e.tipo == "sendero")
	assert sendero.suelo == "grava"
	# Nada inventado: el mapa no habla de sonidos, así que no hay fuentes de sonido.
	assert planta.fuentes == []


def test_georreferencia_y_procedencia(cruce) -> None:
	entorno = cruce.entorno
	assert entorno.georef is not None
	assert entorno.georef["lat0"] == pytest.approx(40.0, abs=1e-5)
	assert entorno.georef["lon0"] == pytest.approx(-3.7, abs=1e-5)
	assert len(entorno.georef["recuadro"]) == 4
	procedencia = entorno.procedencia
	assert procedencia["fuente"] == "OpenStreetMap"
	assert procedencia["licencia"] == "ODbL 1.0"
	assert procedencia["atribucion"] == "© colaboradores de OpenStreetMap"
	assert procedencia["fecha_datos"] == "2026-11-01T00:00:00Z"
	assert len(procedencia["fecha"]) == 10
	assert len(procedencia["recuadro"]) == 4
	assert entorno.plantas[0].exterior


def test_informe_en_espanol_con_sus_apartados(cruce) -> None:
	informe = cruce.informe
	texto = informe.a_texto()
	assert texto.startswith("Informe de la importación de OpenStreetMap")
	for apartado in ("Importado:", "Deducido por el programa", "Lo que la fuente no dice:", "Conviene revisar in situ:"):
		assert apartado in texto
	assert "© colaboradores de OpenStreetMap" in informe.importado[0]
	assert informe.cuentas["vias"] == 2 and informe.cuentas["pasos"] == 2 and informe.cuentas["edificios"] == 2
	assert informe.cuentas["cruces"] == 1 and informe.cuentas["paradas"] == 1 and informe.cuentas["escaleras"] == 2
	assert any("sonidos" in frase for frase in informe.falta)
	assert any("borrador" in frase for frase in informe.revisar)
	assert json.dumps(informe.a_dict())  # se puede guardar


def test_el_entorno_importado_no_tiene_errores_y_empieza_en_un_sitio_valido(cruce) -> None:
	entorno = cruce.entorno
	avisos = validar(entorno)
	assert not hay_errores(avisos), [str(a) for a in avisos if a.es_error]
	planta = entorno.plantas[0]
	donde = planta.espacio_en(entorno.inicio.x, entorno.inicio.y)
	assert donde is not None and donde.tipo == "acera"
	assert len(set(entorno.ids())) == len(entorno.ids())


def test_se_guarda_y_se_recarga_igual(cruce, tmp_path: Path) -> None:
	ruta = tmp_path / "cruce.elab"
	guardar_paquete(ruta, cruce.entorno)
	recargado = cargar_paquete(ruta).entorno
	assert recargado.a_dict() == cruce.entorno.a_dict()
	assert recargado.procedencia["atribucion"] == "© colaboradores de OpenStreetMap"
	assert not hay_errores(validar(recargado))
	paso = next(e for e in recargado.plantas[0].espacios if e.tipo == "paso_peatones" and "Río" in e.nombre)
	assert paso.datos["segun_mapa"]["semaforo"] == "desconocido"


def test_progreso_y_cancelacion() -> None:
	datos = osm.importar_fichero_osm(DATOS / "cruce.osm.json")
	avances: list[tuple[float, str]] = []
	osm.convertir(datos, progreso=lambda fraccion, texto: avances.append((fraccion, texto)))
	fracciones = [fraccion for fraccion, _texto in avances]
	assert fracciones == sorted(fracciones)
	assert fracciones[-1] == 1.0 and len(avances) >= 8
	assert all(texto for _fraccion, texto in avances)
	llamadas = [0]

	def cancelado() -> bool:
		llamadas[0] += 1
		return llamadas[0] > 3

	with pytest.raises(ImportacionCancelada):
		osm.convertir(datos, cancelado=cancelado)


def test_opciones_recortar_por_radio_y_quitar_cosas() -> None:
	datos = osm.importar_fichero_osm(DATOS / "cruce.osm.json")
	recortado = osm.convertir(
		datos, osm.OpcionesOSM(centro=(40.0, -3.7), radio_m=25.0, edificios=False, obstaculos=False, lugares=False, deducir_aceras=False)
	)
	planta = recortado.entorno.plantas[0]
	x0, y0, x1, y1 = planta.caja()
	assert x1 - x0 == pytest.approx(50.0, abs=0.5) and y1 - y0 == pytest.approx(50.0, abs=0.5)
	assert not any(e.tipo == "edificio" for e in planta.espacios)
	assert planta.objetos == []
	assert all(a.datos["origen"] == "mapa" for a in planta.espacios if a.tipo == "acera")
	assert any("Calle del Río" in frase for frase in recortado.informe.falta)
	assert not hay_errores(validar(recortado.entorno))


def test_datos_que_no_sirven_dan_un_mensaje_claro() -> None:
	with pytest.raises(ErrorImportacion):
		osm.convertir({"elements": []})
	with pytest.raises(ErrorImportacion):
		osm.convertir({"cosa": 1})
	lejos = {"elements": [{"type": "node", "id": 1, "lat": 40.0, "lon": -3.7}, {"type": "node", "id": 2, "lat": 40.5, "lon": -3.2}]}
	with pytest.raises(ErrorImportacion) as error:
		osm.convertir(lejos)
	assert "radio" in str(error.value)


def test_con_el_complemento_calle_usa_sus_objetos(tmp_path: Path) -> None:
	carpeta = tmp_path / "plugins" / "calle"
	carpeta.mkdir(parents=True)
	ficha = {
		"formato": 1,
		"id": "calle",
		"nombre": "Calle de prueba",
		"version": "1.0",
		"objetos": [
			{
				"id": "bolardo",
				"nombre": "Bolardo",
				"ambito": ["exterior"],
				"forma": {"tipo": "circulo"},
				"medidas": {"ancho": [0.1, 0.15, 0.3], "fondo": [0.1, 0.15, 0.3], "alto": [0.5, 0.8, 1.1]},
			}
		],
	}
	(carpeta / "complemento.json").write_text(json.dumps(ficha), encoding="utf-8")
	catalogo = Catalogo.cargar(tmp_path / "plugins")
	resultado = osm.convertir(osm.importar_fichero_osm(DATOS / "cruce.osm.json"), osm.OpcionesOSM(catalogo=catalogo))
	objetos = {o.nombre: o for o in resultado.entorno.plantas[0].objetos}
	assert objetos["Bolardo"].tipo == "calle/bolardo"
	assert objetos["Bolardo"].ancho == pytest.approx(0.15)
	assert objetos["Banco"].tipo == "caja"  # ese objeto no está en este complemento de prueba
	assert resultado.entorno.complementos == ["calle"]
	assert not hay_errores(validar(resultado.entorno, catalogo))


def test_interiores_opcionales() -> None:
	datos = osm.importar_fichero_osm(DATOS / "interior.osm.json")
	sin = osm.convertir(datos)
	assert len(sin.entorno.plantas) == 1
	assert any(e.macizo and e.nombre == "Centro cívico" for e in sin.entorno.plantas[0].espacios)
	assert any("interiores" in frase for frase in sin.informe.revisar)
	con = osm.convertir(datos, osm.OpcionesOSM(interiores=True))
	entorno = con.entorno
	assert [p.nivel for p in entorno.plantas] == [0, 1]
	calle, primera = entorno.plantas
	nombres = {e.nombre: e for e in calle.espacios}
	assert nombres["Pasillo de entrada"].tipo == "pasillo" and nombres["Pasillo de entrada"].cerrado
	assert nombres["Sala de lectura"].tipo == "habitacion"
	assert "Sala" in nombres  # la sala sin nombre en el mapa
	assert "el mapa no lo dice" in nombres["Sala"].descripcion
	# El edificio con salas en la planta baja ya no es un bloque macizo.
	assert not any(e.macizo for e in calle.espacios)
	tipos = sorted(a.tipo for a in calle.aberturas)
	assert tipos == ["hueco", "portal", "puerta"]
	portal = next(a for a in calle.aberturas if a.tipo == "portal")
	assert portal.es_salida and portal.hoja == "automatica"
	assert [e.nombre for e in primera.espacios] == ["Aula"]
	assert len(entorno.conectores) == 1 and entorno.conectores[0].tipo == "ascensor"
	assert entorno.conectores[0].plantas() == [calle.id, primera.id]
	assert con.informe.cuentas["salas"] == 4
	assert not hay_errores(validar(entorno)), [str(a) for a in validar(entorno) if a.es_error]
