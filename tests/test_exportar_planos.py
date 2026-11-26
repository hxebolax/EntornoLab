"""Pruebas de las exportaciones gráficas y de intercambio: SVG (visual y táctil), GeoJSON y DXF.

Lo exportado tiene que estar bien formado: el SVG y el GeoJSON se vuelven a
analizar, y el DXF se vuelve a importar (ida y vuelta).
"""

from __future__ import annotations

import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

import pytest

from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio.modelo import hay_errores
from app.dominio.validacion import validar
from app.exportar import braille
from app.exportar import dxf as exportar_dxf
from app.exportar import geojson as exportar_geojson
from app.exportar import svg as exportar_svg
from app.importar import dxf as importar_dxf
from app.importar import osm
from app.importar.plano import OpcionesPlano

DATOS = Path(__file__).parent / "datos"
SVG = "{http://www.w3.org/2000/svg}"


@pytest.fixture(scope="module")
def cruce():
	"""Exterior importado del cruce de prueba (georreferenciado y con atribución)."""
	return osm.convertir(osm.importar_fichero_osm(DATOS / "cruce.osm.json"), osm.OpcionesOSM(nombre="Cruce de prueba")).entorno


@pytest.fixture(scope="module")
def vivienda():
	return ejemplos.vivienda_ejemplo()


def _numeros(texto: str) -> list[float]:
	return [float(n) for n in re.findall(r"-?\d+(?:\.\d+)?", texto)]


# ── SVG ──────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize("variante", exportar_svg.VARIANTES)
def test_svg_bien_formado_a_escala_y_en_milimetros(vivienda, variante: str) -> None:
	plano = exportar_svg.plano_svg(vivienda, vivienda.plantas[0], variante)
	raiz = ET.fromstring(plano.svg.encode("utf-8"))
	assert raiz.tag == f"{SVG}svg"
	# La vivienda mide 10 por 8,7 metros: a 1:75 cabe en un A4 vertical.
	assert plano.escala == 75 and not plano.apaisado and plano.pagina == "A4"
	assert raiz.get("width") == "210.00mm" and raiz.get("height") == "297.00mm"
	assert _numeros(raiz.get("viewBox") or "") == [0.0, 0.0, 210.0, 297.0]
	assert raiz.find(f"{SVG}title") is not None and raiz.find(f"{SVG}desc") is not None
	# Todo el dibujo cae dentro de la hoja.
	for poligono in raiz.iter(f"{SVG}polygon"):
		if poligono.get("transform"):
			continue
		valores = _numeros(poligono.get("points") or "")
		assert all(0.0 <= x <= 210.0 for x in valores[0::2])
		assert all(0.0 <= y <= 297.0 for y in valores[1::2])
	# La vivienda mide 10 metros de oeste a este y 8,7 de sur a norte: sus muros, eso mismo entre 75.
	muros = [
		linea
		for linea in raiz.find(f"{SVG}g[@id='plano']").iter(f"{SVG}line")
		if linea.get("stroke") == "black" and linea.get("stroke-width") == ("1.4" if variante == "tactil" else "0.7")
	]
	equis = [float(linea.get(clave)) for linea in muros for clave in ("x1", "x2")]
	ies = [float(linea.get(clave)) for linea in muros for clave in ("y1", "y2")]
	assert max(equis) - min(equis) == pytest.approx(10000 / 75, abs=0.02)
	assert max(ies) - min(ies) == pytest.approx(8700 / 75, abs=0.02)
	assert "1:75" in plano.leyenda


def test_svg_visual_con_colores_nombres_y_letras(vivienda) -> None:
	entorno = ejemplos.vivienda_ejemplo()
	planta = entorno.plantas[0]
	mesa = ed.Objeto(nombre="Mesa", tipo="caja", x=2.0, y=2.0, ancho=1.2, fondo=0.8, alto=0.75)
	mesa.id = entorno.id_para(mesa)
	planta.objetos.append(mesa)
	plano = exportar_svg.plano_svg(entorno, planta, "visual")
	raiz = ET.fromstring(plano.svg.encode("utf-8"))
	textos = ["".join(t.itertext()) for t in raiz.iter(f"{SVG}text")]
	for nombre in ("Salón", "Cocina", "Dormitorio", "Pasillo"):
		assert nombre in textos
	assert "M" in textos  # la letra del objeto
	assert "N" in textos  # el norte
	rellenos = {p.get("fill") for p in raiz.iter(f"{SVG}polygon")}
	assert len(rellenos) >= 4
	assert any(linea.get("stroke") == "#a0522d" for linea in raiz.iter(f"{SVG}line"))  # puertas
	assert any(linea.get("stroke") == "#3b82c4" for linea in raiz.iter(f"{SVG}line"))  # ventanas
	assert "Letras de los objetos: M: Mesa (1)." in plano.leyenda
	assert "s1: Frigorífico (fuente de sonido)" in plano.leyenda
	assert raiz.find(f"{SVG}g[@id='tinta']") is None


def test_svg_tactil_sin_color_con_tramas_braille_y_leyenda(cruce) -> None:
	planta = cruce.plantas[0]
	plano = exportar_svg.plano_svg(cruce, planta, "tactil")
	raiz = ET.fromstring(plano.svg.encode("utf-8"))
	dibujo = raiz.find(f"{SVG}g[@id='plano']")
	assert dibujo is not None
	# Sin rellenos de color: blanco, negro o una trama.
	for elemento in dibujo.iter():
		relleno = elemento.get("fill")
		assert relleno in (None, "none", "white", "black") or relleno.startswith("url(#t-")
	tramas = {patron.get("id") for patron in raiz.iter(f"{SVG}pattern")}
	assert {"t-calzada", "t-edificio", "t-parque", "t-paso", "t-escalera", "t-tactil"} <= tramas
	# Trazo grueso en las fachadas y puntos braille para las claves.
	grosores = {float(linea.get("stroke-width")) for linea in dibujo.iter(f"{SVG}line")}
	assert max(grosores) >= 1.2
	assert len(list(dibujo.iter(f"{SVG}circle"))) > 20
	# Lo que es solo para quien acompaña va aparte y no en negro.
	tinta = raiz.find(f"{SVG}g[@id='tinta']")
	assert tinta is not None and all(texto.get("fill") != "black" for texto in tinta.iter(f"{SVG}text"))
	assert not list(dibujo.iter(f"{SVG}text"))
	leyenda = plano.leyenda
	assert "Leyenda del plano táctil" in leyenda
	assert "Puntos separados: calzada" in leyenda and "Bandas gruesas: paso de peatones." in leyenda
	assert "un tope a cada lado: una puerta" in leyenda
	assert "Claves:" in leyenda
	assert any(clave == "1" for clave, _nombre in plano.claves)
	assert any("Paso con semáforo de Calle Mayor" in nombre for _clave, nombre in plano.claves)
	# La atribución de OpenStreetMap acompaña a todo lo exportado.
	assert "© colaboradores de OpenStreetMap (ODbL 1.0)" in leyenda
	assert "© colaboradores de OpenStreetMap" in plano.svg
	brf = plano.leyenda_brf()
	assert brf.isascii() and max(len(linea) for linea in brf.splitlines()) <= 40


def test_svg_visual_de_un_exterior_lleva_la_atribucion(cruce) -> None:
	plano = exportar_svg.plano_svg(cruce, cruce.plantas[0], "visual", pagina="A3")
	raiz = ET.fromstring(plano.svg.encode("utf-8"))
	textos = ["".join(t.itertext()) for t in raiz.iter(f"{SVG}text")]
	assert "© colaboradores de OpenStreetMap (ODbL 1.0)" in textos
	assert plano.pagina == "A3" and plano.escala == 750
	assert plano.escala < exportar_svg.plano_svg(cruce, cruce.plantas[0], "visual", pagina="A4").escala


def test_svg_opciones_y_errores(vivienda, tmp_path: Path) -> None:
	planta = vivienda.plantas[0]
	apaisado = exportar_svg.plano_svg(vivienda, planta, "visual", apaisado=True, escala=100)
	assert apaisado.apaisado and apaisado.escala == 100
	assert 'width="297.00mm"' in apaisado.svg
	with pytest.raises(ValueError):
		exportar_svg.plano_svg(vivienda, planta, "acuarela")
	with pytest.raises(ValueError):
		exportar_svg.plano_svg(vivienda, planta, "visual", pagina="A0")
	vacio = ed.crear_entorno("Vacío")
	with pytest.raises(ValueError):
		exportar_svg.plano_svg(vacio, ed.crear_planta(vacio, "Nada"))
	centro = ejemplos.centro_dos_plantas()
	escritos = exportar_svg.guardar_planos(centro, tmp_path / "planos", "tactil")
	assert len(escritos) == 6  # por planta: SVG, leyenda en texto y leyenda en BRF
	assert {ruta.suffix for ruta in escritos} == {".svg", ".txt", ".brf"}
	for ruta in escritos:
		assert ruta.stat().st_size > 0
		if ruta.suffix == ".svg":
			ET.parse(ruta)


def test_braille_numeros_letras_y_brf() -> None:
	assert braille.a_braille("12") == "⠼⠁⠃"
	assert braille.a_braille("baño") == "⠃⠁⠻⠕"
	assert braille.a_brf(braille.a_braille("12 m")) == "#AB M"
	assert braille.ancho_mm(braille.a_braille("1")) == pytest.approx(10.0)
	circulos = braille.puntos_svg(braille.a_braille("c"), 10.0, 20.0)
	assert len(circulos) == 2 and all(c.startswith("<circle") for c in circulos)
	lineas = braille.lineas_brf(["Una leyenda larga que no cabe en una sola línea de una hoja braille normal."], 20)
	assert len(lineas) > 2 and all(len(linea) <= 20 for linea in lineas)


# ── GeoJSON ──────────────────────────────────────────────────────────────────


def test_geojson_en_coordenadas_reales_si_hay_georreferencia(cruce) -> None:
	documento = json.loads(exportar_geojson.texto_geojson(cruce, cruce.plantas[0]))
	assert documento["type"] == "FeatureCollection"
	assert documento["attribution"] == "© colaboradores de OpenStreetMap (ODbL 1.0)"
	assert documento["license"] == "ODbL 1.0"
	assert "crs_local" not in documento
	oeste, sur, este, norte = documento["bbox"]
	assert -3.702 < oeste < este < -3.698 and 39.998 < sur < norte < 40.002
	por_clase: dict[str, list[dict]] = {}
	for feature in documento["features"]:
		assert feature["type"] == "Feature" and feature["properties"]["level"] == "0"
		por_clase.setdefault(feature["properties"]["elab:clase"], []).append(feature)
	assert set(por_clase) >= {"espacio", "zona", "pared", "abertura", "objeto", "referencia", "via"}
	for feature in por_clase["espacio"]:
		anillo = feature["geometry"]["coordinates"][0]
		assert feature["geometry"]["type"] == "Polygon" and anillo[0] == anillo[-1] and len(anillo) >= 4
	propiedades = {f["properties"]["name"]: f["properties"] for f in por_clase["espacio"]}
	con_semaforo = propiedades["Paso con semáforo de Calle Mayor"]
	assert con_semaforo["footway"] == "crossing" and con_semaforo["crossing"] == "traffic_signals"
	assert con_semaforo["traffic_signals:sound"] == "yes" and con_semaforo["button_operated"] == "yes"
	assert con_semaforo["crossing:island"] == "no" and con_semaforo["kerb"] == "lowered"
	# Lo que el mapa no decía no se exporta como si se supiera.
	sin_datos = propiedades["Paso de peatones de Calle del Río"]
	assert "crossing" not in sin_datos and "traffic_signals:sound" not in sin_datos and "tactile_paving" not in sin_datos
	assert sin_datos["elab:segun_mapa"]["semaforo"] == "desconocido"
	assert propiedades["Edificio de viviendas"]["building"] == "yes"
	assert propiedades["Edificio de viviendas"]["feature_type"] == "footprint"
	assert propiedades["Escaleras"]["highway"] == "steps" and propiedades["Escaleras"]["step_count"] == "12"
	acera = next(p for nombre, p in propiedades.items() if nombre.startswith("Acera oeste de Calle del Río"))
	assert acera["footway"] == "sidewalk" and acera["elab:origen"] == "deducida"
	portal = next(f for f in por_clase["abertura"] if f["properties"]["elab:tipo"] == "portal")
	assert portal["geometry"]["type"] == "LineString" and portal["properties"]["entrance"] == "yes"
	assert portal["properties"]["feature_type"] == "opening"
	via = next(f for f in por_clase["via"] if f["properties"]["name"] == "Calle del Río")
	assert via["properties"]["oneway"] == "yes" and via["properties"]["lanes"] == "1"


def test_geojson_local_con_etiquetas_de_interiores(tmp_path: Path) -> None:
	centro = ejemplos.centro_dos_plantas()
	documento = exportar_geojson.a_geojson(centro)
	assert documento["crs_local"]["unidades"] == "metros"
	assert "attribution" not in documento
	assert [nivel["level"] for nivel in documento["elab:niveles"]] == [0, 1]
	clases = {f["properties"]["elab:clase"] for f in documento["features"]}
	assert "conector" in clases
	espacios = [
		f["properties"]
		for f in documento["features"]
		if f["properties"]["elab:clase"] == "espacio" and not f["properties"].get("elab:macizo")
	]
	assert {p["indoor"] for p in espacios} <= {"room", "corridor", "area"}
	assert all(p["feature_type"] == "unit" and p["level_id"] for p in espacios)
	assert {p["level"] for p in espacios} == {"0", "1"}
	puertas = [f["properties"] for f in documento["features"] if f["properties"]["elab:clase"] == "abertura" and "door" in f["properties"]]
	assert puertas and all(p["feature_type"] == "opening" for p in puertas)
	ascensor = [
		f for f in documento["features"] if f["properties"].get("highway") == "elevator" and f["properties"]["elab:clase"] == "conector"
	]
	assert len(ascensor) == 2 and ascensor[0]["properties"]["level"] == "0;1"
	assert len({f["id"] for f in documento["features"]}) == len(documento["features"])
	escritos = exportar_geojson.guardar_geojson(centro, tmp_path / "geo")
	assert len(escritos) == 2
	for ruta in escritos:
		assert json.loads(ruta.read_text(encoding="utf-8"))["features"]


# ── DXF ──────────────────────────────────────────────────────────────────────


def test_dxf_por_capas_y_en_metros(vivienda) -> None:
	texto = exportar_dxf.a_dxf(vivienda, vivienda.plantas[0])
	lineas = texto.splitlines()
	assert len(lineas) % 2 == 0
	assert lineas[0] == "999" and "metros" in lineas[1]
	assert lineas[-2:] == ["0", "EOF"]
	for capa in ("ESPACIOS", "MUROS", "PUERTAS", "VENTANAS", "TEXTOS", "REFERENCIAS"):
		assert capa in lineas
	plano = importar_dxf.leer_dxf(texto.encode("cp1252"))
	assert plano.sugerir_escala()[0] == 1.0
	capas = {capa.nombre: capa for capa in plano.capas()}
	assert capas["ESPACIOS"].cerrados == 6
	assert capas["PUERTAS"].arcos == 5 and capas["VENTANAS"].abiertos == 3
	assert {"Salón", "Baño", "Cocina"} <= {rotulo.texto for rotulo in plano.rotulos}


def test_dxf_ida_y_vuelta(vivienda, tmp_path: Path) -> None:
	rutas = exportar_dxf.guardar_dxf(vivienda, tmp_path / "dxf")
	assert len(rutas) == 1 and rutas[0].suffix == ".dxf"
	vuelta = importar_dxf.importar_dxf(rutas[0], OpcionesPlano(nombre="De vuelta")).entorno
	original = vivienda.plantas[0]
	planta = vuelta.plantas[0]
	# Las mismas salas, con su nombre, su tipo y su tamaño.
	assert sorted(e.nombre for e in planta.espacios) == sorted(e.nombre for e in original.espacios)
	areas = {e.nombre: e.area() for e in original.espacios}
	for espacio in planta.espacios:
		assert espacio.area() == pytest.approx(areas[espacio.nombre], abs=0.01)
	assert next(e for e in planta.espacios if e.nombre == "Pasillo").tipo == "pasillo"
	# Las cinco puertas vuelven por su arco de barrido, con su anchura; el hueco y las ventanas, no.
	puertas_originales = sorted(round(a.ancho, 2) for a in original.aberturas if a.tipo == "puerta")
	assert sorted(round(a.ancho, 2) for a in planta.aberturas) == puertas_originales
	# Los lados de las salas no vuelven duplicados como paredes sueltas.
	assert planta.paredes == []
	assert not hay_errores(validar(vuelta))


def test_dxf_de_un_exterior_importado(cruce) -> None:
	texto = exportar_dxf.a_dxf(cruce, cruce.plantas[0])
	assert "© colaboradores de OpenStreetMap" in texto
	plano = importar_dxf.leer_dxf(texto.encode("cp1252", errors="replace"))
	capas = {capa.nombre: capa for capa in plano.capas()}
	assert capas["EDIFICIOS"].cerrados == 2
	assert capas["EJES_VIAS"].abiertos == 2 and capas["EJES_VIAS"].sugerencia == "ignorar"
	assert capas["MOBILIARIO"].cerrados == 2 and capas["MOBILIARIO"].sugerencia == "ignorar"
	vuelta = importar_dxf.convertir_dxf(plano)
	assert not hay_errores(validar(vuelta.entorno))
	nombres = {e.nombre for e in vuelta.entorno.plantas[0].espacios}
	assert {"Mercado", "Parque del Río", "Paso con semáforo de Calle Mayor"} <= nombres
