"""Pruebas de la importación de planos: DXF, SVG, imagen de fondo, GPX y GeoJSON.

Los planos de ``tests/datos`` son ficticios. Incluyen un SVG malicioso (con
entidades externas) que tiene que rechazarse sin leer nada, y se fabrica al
vuelo un SVG enorme para comprobar los límites.
"""

from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from app.dominio import edicion as ed
from app.dominio.formato import cargar_paquete, guardar_paquete
from app.dominio.modelo import hay_errores
from app.dominio.validacion import validar
from app.importar import dxf, gpx, imagen, osm, svg
from app.importar.comun import ErrorImportacion, ImportacionCancelada, analizar_xml_seguro
from app.importar.plano import OpcionesPlano

DATOS = Path(__file__).parent / "datos"


# ── DXF ──────────────────────────────────────────────────────────────────────


def test_dxf_lee_capas_entidades_y_unidades() -> None:
	plano = dxf.leer_dxf(DATOS / "planta.dxf")
	capas = {capa.nombre: capa for capa in plano.capas()}
	assert set(capas) == {"MUROS", "PUERTAS", "TEXTOS", "MOBILIARIO"}
	# Dos salas (LWPOLYLINE y POLYLINE) y la columna del bloque insertado; una línea suelta.
	assert capas["MUROS"].cerrados == 3 and capas["MUROS"].abiertos == 1
	assert capas["MUROS"].sugerencia == "paredes"
	assert capas["PUERTAS"].arcos == 1 and capas["PUERTAS"].sugerencia == "puertas"
	assert capas["TEXTOS"].rotulos == 2 and capas["TEXTOS"].sugerencia == "textos"
	assert capas["MOBILIARIO"].sugerencia == "ignorar"
	assert "MUROS" in capas["MUROS"].descripcion()
	assert sorted(rotulo.texto for rotulo in plano.rotulos) == ["Cocina", "Salon comedor"]
	# El bloque insertado en (9000, 1000) queda en su sitio.
	columna = next(t for t in plano.trazos if t.cerrado and min(p[0] for p in t.puntos) == pytest.approx(9000))
	assert max(p[1] for p in columna.puntos) == pytest.approx(1300)
	escala, explicacion = plano.sugerir_escala()
	assert escala == pytest.approx(0.001)
	assert "milímetros" in explicacion
	# Lo que no se entiende se cuenta y se dice; la lámina del espacio papel se ignora.
	assert any("HATCH" in aviso for aviso in plano.avisos)
	assert not any(t.capa == "COTAS" for t in plano.trazos)


def test_dxf_se_convierte_en_salas_paredes_y_puerta() -> None:
	resultado = dxf.importar_dxf(DATOS / "planta.dxf", OpcionesPlano(nombre="Piso de prueba"))
	entorno = resultado.entorno
	planta = entorno.plantas[0]
	salas = {e.nombre: e for e in planta.espacios}
	assert set(salas) == {"Cocina", "Salon comedor"}
	assert salas["Cocina"].caja() == pytest.approx((0.0, 0.0, 4.0, 3.0))
	assert salas["Cocina"].datos["uso"] == "cocina"
	assert salas["Salon comedor"].caja() == pytest.approx((4.0, 0.0, 8.0, 3.0))
	assert all(e.cerrado for e in planta.espacios)
	# El muro suelto y la columna; los lados de las salas no se repiten como paredes.
	assert len(planta.paredes) == 2
	assert max(pared.b[0] for pared in planta.paredes) == pytest.approx(10.0)
	# La puerta sale del arco de barrido: en la pared común, de 0,9 metros.
	assert len(planta.aberturas) == 1
	puerta = planta.aberturas[0]
	assert puerta.tipo == "puerta" and puerta.ancho == pytest.approx(0.9)
	assert puerta.a[0] == pytest.approx(4.0) and puerta.b[0] == pytest.approx(4.0)
	assert "Cocina" in puerta.nombre and "Salon comedor" in puerta.nombre
	assert not hay_errores(validar(entorno)), [str(a) for a in validar(entorno) if a.es_error]
	assert planta.espacio_en(entorno.inicio.x, entorno.inicio.y) is not None
	informe = resultado.informe
	assert informe.cuentas == {"espacios": 2, "paredes": 2, "puertas": 1}
	assert any("Escala tomada del fichero" in frase for frase in informe.deducido)
	assert any("arcos de barrido" in frase for frase in informe.deducido)
	assert "DXF" in entorno.procedencia["fuente"]


def test_dxf_escala_origen_y_capas_elegidas() -> None:
	plano = dxf.leer_dxf((DATOS / "planta.dxf").read_bytes())
	resultado = dxf.convertir_dxf(
		plano, OpcionesPlano(metros_por_unidad=0.002, origen=(4000.0, 0.0), capas_paredes=[], capas_puertas=[], capas_espacios=["MUROS"])
	)
	planta = resultado.entorno.plantas[0]
	cocina = next(e for e in planta.espacios if e.nombre == "Cocina")
	assert cocina.caja() == pytest.approx((-8.0, 0.0, 0.0, 6.0))
	assert planta.aberturas == []
	assert len(planta.paredes) == 1  # solo la columna, que es un contorno fino de la capa de espacios
	assert any("puertas" in frase for frase in resultado.informe.falta)
	with pytest.raises(ErrorImportacion):
		dxf.convertir_dxf(plano, OpcionesPlano(metros_por_unidad=0.0))
	with pytest.raises(ErrorImportacion) as error:
		dxf.convertir_dxf(plano, OpcionesPlano(metros_por_unidad=5.0))
	assert "escala" in str(error.value).lower()


def test_dxf_sin_unidades_pregunta_la_escala() -> None:
	# Una sala de 4 por 3 unidades, sin $INSUNITS: no se puede saber si son metros.
	texto = "0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\nSALAS\n90\n4\n70\n1\n10\n0\n20\n0\n10\n4\n20\n0\n10\n4\n20\n3\n10\n0\n20\n3\n0\nENDSEC\n0\nEOF\n"
	plano = dxf.leer_dxf(texto.encode("ascii"))
	escala, explicacion = plano.sugerir_escala()
	assert escala is None and "unidades" in explicacion
	with pytest.raises(ErrorImportacion) as error:
		dxf.convertir_dxf(plano)
	assert "cuántos metros" in str(error.value)
	sala = dxf.convertir_dxf(plano, OpcionesPlano(metros_por_unidad=1.0)).entorno.plantas[0].espacios[0]
	assert sala.area() == pytest.approx(12.0)
	assert "el plano no lo dice" in sala.descripcion


def test_dxf_rechaza_lo_que_no_es_dxf(tmp_path: Path) -> None:
	with pytest.raises(ErrorImportacion):
		dxf.leer_dxf(b"esto no es un plano\nni nada parecido\n")
	with pytest.raises(ErrorImportacion) as error:
		dxf.leer_dxf(b"AutoCAD Binary DXF\r\n\x1a\x00resto")
	assert "binario" in str(error.value)
	with pytest.raises(ErrorImportacion):
		dxf.leer_dxf(tmp_path / "no_existe.dxf")
	with pytest.raises(ErrorImportacion):
		dxf.leer_dxf(b"0\nSECTION\n2\nHEADER\n0\nENDSEC\n0\nEOF\n")


def test_dxf_polilinea_con_tramo_curvo() -> None:
	# Un semicírculo: de (0,0) a (2,0) con «bulge» 1, cerrado por la cuerda.
	texto = "0\nSECTION\n2\nENTITIES\n0\nLWPOLYLINE\n8\nSALAS\n90\n2\n70\n1\n10\n0\n20\n0\n42\n1\n10\n2\n20\n0\n0\nENDSEC\n0\nEOF\n"
	plano = dxf.leer_dxf(texto.encode("ascii"))
	puntos = plano.trazos[0].puntos
	assert len(puntos) > 6
	assert all(math.hypot(x - 1.0, y) == pytest.approx(1.0, abs=1e-6) for x, y in puntos)
	assert min(y for _x, y in puntos) == pytest.approx(-1.0, abs=0.05)


# ── SVG ──────────────────────────────────────────────────────────────────────


def test_svg_lee_formas_capas_y_transformaciones() -> None:
	plano = svg.leer_svg(DATOS / "planta.svg")
	capas = {capa.nombre: capa for capa in plano.capas()}
	assert capas["salas"].cerrados == 3
	assert capas["muros"].abiertos == 2
	assert capas["rotulos"].rotulos == 3
	# La y del SVG crece hacia abajo; en el plano, hacia el norte.
	assert all(y <= 0 for trazo in plano.trazos for _x, y in trazo.puntos)
	# El grupo de muros lleva translate(10, 0).
	linea = next(t for t in plano.trazos if t.origen == "line")
	assert linea.puntos[0][0] == pytest.approx(90.0)
	assert sorted(r.texto for r in plano.rotulos) == ["Cocina", "Pasillo", "Salón"]
	# Ni el script, ni la imagen remota, ni el «use» entran; lo de <defs> tampoco.
	assert len(plano.trazos) == 5
	assert any("image" in aviso and "use" in aviso for aviso in plano.avisos)


def test_svg_se_convierte_con_la_escala_indicada() -> None:
	plano = svg.leer_svg(DATOS / "planta.svg")
	with pytest.raises(ErrorImportacion) as error:
		svg.convertir_svg(plano)
	assert "escala" in str(error.value)
	resultado = svg.importar_svg(DATOS / "planta.svg", 0.1, OpcionesPlano(nombre="Piso SVG"))
	planta = resultado.entorno.plantas[0]
	salas = {e.nombre: e for e in planta.espacios}
	assert set(salas) == {"Cocina", "Salón", "Pasillo"}
	assert salas["Pasillo"].tipo == "pasillo"
	assert salas["Cocina"].area() == pytest.approx(12.0)
	assert salas["Pasillo"].caja() == pytest.approx((0.0, 0.0, 8.0, 2.0))
	assert salas["Cocina"].caja() == pytest.approx((0.0, 2.0, 4.0, 5.0))
	assert len(planta.paredes) == 2
	assert not hay_errores(validar(resultado.entorno))
	assert any("puertas" in frase for frase in resultado.informe.falta)


def test_svg_path_con_ordenes_relativas_y_curvas() -> None:
	contenido = b'<svg xmlns="http://www.w3.org/2000/svg"><path d="m 10,10 l 20,0 0,10 -20,0 z M 50 50 C 60 40 70 40 80 50 L 80 70"/></svg>'
	plano = svg.leer_svg(contenido)
	assert len(plano.trazos) == 2
	cerrado, abierto = plano.trazos
	assert cerrado.cerrado and len(cerrado.puntos) == 4
	assert cerrado.puntos[2] == pytest.approx((30.0, -20.0))
	assert not abierto.cerrado
	assert [coordenada for punto in abierto.puntos for coordenada in punto] == pytest.approx([50.0, -50.0, 80.0, -50.0, 80.0, -70.0])
	assert any("curvas" in aviso for aviso in plano.avisos)


def test_svg_malicioso_con_entidades_externas_se_rechaza() -> None:
	with pytest.raises(ErrorImportacion) as error:
		svg.leer_svg(DATOS / "malicioso.svg")
	assert "seguridad" in str(error.value)
	bomba = (
		b'<?xml version="1.0"?><!DOCTYPE svg [<!ENTITY a "aaaaaaaaaa"><!ENTITY b "&a;&a;&a;&a;&a;&a;&a;&a;&a;&a;">'
		b'<!ENTITY c "&b;&b;&b;&b;&b;&b;&b;&b;&b;&b;">]><svg xmlns="http://www.w3.org/2000/svg"><text>&c;</text></svg>'
	)
	with pytest.raises(ErrorImportacion):
		svg.leer_svg(bomba)
	with pytest.raises(ErrorImportacion):
		analizar_xml_seguro(b'<!DOCTYPE x SYSTEM "http://example.invalid/x.dtd"><x/>', 1000, 10)


def test_svg_enorme_se_rechaza_pronto() -> None:
	muchos = (
		b'<svg xmlns="http://www.w3.org/2000/svg">' + b'<rect x="0" y="0" width="1" height="1"/>' * (svg.MAX_ELEMENTOS_SVG + 10) + b"</svg>"
	)
	with pytest.raises(ErrorImportacion) as error:
		svg.leer_svg(muchos)
	assert "demasiado grande" in str(error.value)
	pesado = b'<svg xmlns="http://www.w3.org/2000/svg"><!--' + b"x" * (svg.MAX_BYTES_SVG + 1) + b"--></svg>"
	with pytest.raises(ErrorImportacion):
		svg.leer_svg(pesado)
	hondo = b"<svg>" + b"<g>" * 500 + b"</g>" * 500 + b"</svg>"
	with pytest.raises(ErrorImportacion):
		svg.leer_svg(hondo)
	with pytest.raises(ErrorImportacion):
		svg.leer_svg(b"<html><body>no es un svg</body></html>")
	with pytest.raises(ErrorImportacion):
		svg.leer_svg(b"<svg><rect")


def test_plano_como_planta_nueva_de_un_entorno_y_cancelacion() -> None:
	entorno = ed.crear_entorno("Edificio")
	baja = ed.crear_planta(entorno, "Planta baja")
	ed.crear_habitacion_rectangular(entorno, baja, "Portal", 0, 0, 4, 3)
	ed.fijar_inicio(entorno, baja, 2, 1.5)
	plano = dxf.leer_dxf(DATOS / "planta.dxf")
	resultado = dxf.convertir_dxf(plano, OpcionesPlano(entorno=entorno, nivel=1, nombre_planta="Primera"))
	assert resultado.entorno is entorno
	assert [p.nombre for p in entorno.plantas] == ["Planta baja", "Primera"]
	assert entorno.inicio.planta == baja.id  # el inicio que ya había no se toca
	assert len(set(entorno.ids())) == len(entorno.ids())
	with pytest.raises(ErrorImportacion):
		dxf.convertir_dxf(plano, OpcionesPlano(entorno=entorno, nivel=1))
	with pytest.raises(ImportacionCancelada):
		dxf.convertir_dxf(plano, cancelado=lambda: True)


# ── Imagen de fondo ──────────────────────────────────────────────────────────


def test_imagen_de_fondo_con_dos_puntos_de_calibracion(tmp_path: Path) -> None:
	entorno = ed.crear_entorno("Con fondo")
	planta = ed.crear_planta(entorno, "Baja")
	ed.crear_habitacion_rectangular(entorno, planta, "Sala", 0, 0, 10, 5)
	ed.fijar_inicio(entorno, planta, 5, 2.5)
	# Imagen de 1000 por 500 píxeles que cubre la sala: 1 píxel = 1 centímetro, sin giro.
	fondo = imagen.definir_fondo(entorno, planta, "imagenes/plano.png", (0, 500), (0, 0), (1000, 0), (10, 5), opacidad=0.4)
	escala, giro, x0, y0 = imagen.transformacion(fondo)
	assert escala == pytest.approx(0.01)
	assert giro == pytest.approx(0.0, abs=1e-9)
	assert (x0, y0) == pytest.approx((0.0, 5.0))
	assert imagen.imagen_a_mundo(fondo, 500, 250) == pytest.approx((5.0, 2.5))
	assert imagen.mundo_a_imagen(fondo, 5.0, 2.5) == pytest.approx((500.0, 250.0))
	assert imagen.fondos_de(entorno, planta.id) == [fondo]
	# Sobrevive a guardar y abrir el paquete, con la imagen dentro.
	ruta_imagen = tmp_path / "Plano Escaneado.png"
	ruta_imagen.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 32)
	nombre, datos = imagen.preparar_recurso(ruta_imagen)
	assert nombre == "imagenes/plano-escaneado.png"
	guardar_paquete(tmp_path / "con_fondo.elab", entorno, recursos={nombre: datos})
	paquete = cargar_paquete(tmp_path / "con_fondo.elab")
	recargado = imagen.fondos_de(paquete.entorno)[0]
	assert imagen.transformacion(recargado)[0] == pytest.approx(0.01)
	assert paquete.tiene_recurso(nombre)
	# Un fondo nuevo sustituye al anterior; quitarlo limpia la procedencia.
	imagen.definir_fondo(entorno, planta, "imagenes/otro.png", (0, 0), (0, 0), (0, 100), (2, 0))
	assert len(imagen.fondos_de(entorno)) == 1
	girado = imagen.fondos_de(entorno)[0]
	assert imagen.transformacion(girado)[1] == pytest.approx(90.0)
	assert imagen.imagen_a_mundo(girado, 0, 50) == pytest.approx((1.0, 0.0))
	assert imagen.quitar_fondo(entorno, planta.id)
	assert "fondos" not in entorno.procedencia


def test_imagen_de_fondo_valida_lo_que_recibe(tmp_path: Path) -> None:
	entorno = ed.crear_entorno("Con fondo")
	planta = ed.crear_planta(entorno, "Baja")
	with pytest.raises(ErrorImportacion):
		imagen.definir_fondo(entorno, planta, "imagenes/p.png", (10, 10), (0, 0), (11, 10), (5, 0))
	with pytest.raises(ErrorImportacion):
		imagen.definir_fondo(entorno, planta, "imagenes/p.png", (0, 0), (1, 1), (500, 0), (1.05, 1))
	with pytest.raises(ErrorImportacion):
		imagen.definir_fondo(entorno, planta, "imagenes/p.png", (0, "x"), (0, 0), (500, 0), (5, 0))
	programa = tmp_path / "plano.exe"
	programa.write_bytes(b"MZ")
	with pytest.raises(ErrorImportacion):
		imagen.preparar_recurso(programa)
	with pytest.raises(ErrorImportacion):
		imagen.transformacion({"puntos": []})


# ── GPX y GeoJSON ────────────────────────────────────────────────────────────


@pytest.fixture
def exterior():
	"""Entorno georreferenciado recién importado del cruce de prueba."""
	return osm.convertir(osm.importar_fichero_osm(DATOS / "cruce.osm.json")).entorno


def test_gpx_puntos_y_ruta_sobre_un_exterior(exterior) -> None:
	trazado = gpx.leer_gpx(DATOS / "ruta.gpx")
	assert [p.nombre for p in trazado.puntos] == ["Casa", "Muy lejos"]
	assert trazado.rutas[0].nombre == "Ruta al parque" and len(trazado.rutas[0].puntos) == 5
	planta = exterior.plantas[0]
	antes = len(planta.referencias)
	informe = gpx.anadir_trazado(exterior, planta, trazado)
	assert informe.cuentas == {"puntos": 1, "rutas": 1}
	casa = next(r for r in planta.referencias if r.nombre == "Casa")
	assert (casa.x, casa.y) == pytest.approx((-60.0, 4.2), abs=0.05)
	assert not any(r.nombre == "Muy lejos" for r in planta.referencias)
	assert any("fuera de la zona" in frase for frase in informe.avisos)
	rutas = gpx.rutas_de(exterior, planta.id)
	assert len(rutas) == 1
	assert rutas[0]["longitud_m"] == pytest.approx(40 + 8.4 + 14 + 35.8, abs=0.5)
	assert rutas[0]["puntos"][0] == pytest.approx([-60.0, 4.2], abs=0.05)
	marcas = [r for r in planta.referencias if r.nombre.startswith("Ruta al parque")]
	assert len(marcas) == 5
	assert marcas[0].nombre.endswith("salida") and marcas[-1].nombre.endswith("llegada")
	assert all(not marca.permanente for marca in marcas)
	assert len(planta.referencias) == antes + 6
	assert not hay_errores(validar(exterior))
	assert json.dumps(exterior.a_dict())


def test_geojson_puntos_y_lineas(exterior) -> None:
	planta = exterior.plantas[0]
	informe = gpx.importar_geojson(exterior, planta, DATOS / "ruta.geojson", referencias_de_ruta=False)
	assert informe.cuentas == {"puntos": 1, "rutas": 1}
	punto = next(r for r in planta.referencias if r.nombre == "Punto de encuentro")
	assert punto.descripcion == "Junto al banco."
	assert (punto.x, punto.y) == pytest.approx((-10.0, 3.8), abs=0.05)
	assert not any(r.nombre.startswith("Ruta al mercado") for r in planta.referencias)
	assert gpx.rutas_de(exterior)[0]["nombre"] == "Ruta al mercado"
	poligono = json.dumps({"type": "Polygon", "coordinates": [[[-3.7, 40.0], [-3.6999, 40.0], [-3.6999, 40.0001], [-3.7, 40.0]]]}).encode(
		"utf-8"
	)
	assert len(gpx.leer_geojson(poligono).rutas[0].puntos) == 4


def test_rutas_exigen_georreferencia_y_ficheros_validos(exterior, tmp_path: Path) -> None:
	interior = ed.crear_entorno("Sin georreferencia")
	planta = ed.crear_planta(interior, "Baja")
	ed.crear_habitacion_rectangular(interior, planta, "Sala", 0, 0, 4, 3)
	with pytest.raises(ErrorImportacion) as error:
		gpx.importar_gpx(interior, planta, DATOS / "ruta.gpx")
	assert "georreferenciado" in str(error.value)
	with pytest.raises(ErrorImportacion):
		gpx.leer_gpx(b"<kml></kml>")
	with pytest.raises(ErrorImportacion):
		gpx.leer_gpx(b'<gpx version="1.1"></gpx>')
	with pytest.raises(ErrorImportacion):
		gpx.leer_gpx(b'<!DOCTYPE gpx [<!ENTITY x SYSTEM "file:///etc/passwd">]><gpx><wpt lat="1" lon="1"><name>&x;</name></wpt></gpx>')
	with pytest.raises(ErrorImportacion):
		gpx.leer_geojson(b"no es json")
	with pytest.raises(ErrorImportacion):
		gpx.leer_geojson(b'{"type": "FeatureCollection", "features": []}')
	lejos = json.dumps({"type": "Point", "coordinates": [2.17, 41.38]}).encode("utf-8")
	with pytest.raises(ErrorImportacion):
		gpx.importar_geojson(exterior, exterior.plantas[0], lejos)
