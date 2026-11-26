"""Pruebas de la descripción en texto, Markdown y HTML, y de las indicaciones de ruta."""

from __future__ import annotations

import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import pytest

from app.dominio import ejemplos
from app.dominio.modelo import Espacio, Posicion
from app.exportar import indicaciones, texto
from app.exportar.fichas import estado_de, ficha_escalera, ficha_paso
from app.importar import osm

DATOS = Path(__file__).parent / "datos"


@pytest.fixture(scope="module")
def cruce():
	return osm.convertir(osm.importar_fichero_osm(DATOS / "cruce.osm.json"), osm.OpcionesOSM(nombre="Cruce de prueba")).entorno


class _Esquema(HTMLParser):
	"""Recoge los encabezados y comprueba que las etiquetas se abren y se cierran en orden."""

	def __init__(self) -> None:
		super().__init__()
		self.pila: list[str] = []
		self.encabezados: list[tuple[int, str]] = []
		self.elementos_de_lista = 0
		self.idioma = ""
		self._actual: int | None = None

	def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
		if tag == "meta":
			return
		if tag == "html":
			self.idioma = dict(attrs).get("lang") or ""
		if tag == "li":
			self.elementos_de_lista += 1
			assert self.pila[-1] == "ul"
		if len(tag) == 2 and tag[0] == "h" and tag[1].isdigit():
			self._actual = int(tag[1])
			self.encabezados.append((self._actual, ""))
		self.pila.append(tag)

	def handle_endtag(self, tag: str) -> None:
		assert self.pila and self.pila[-1] == tag, f"se cierra <{tag}> con {self.pila[-3:]} abiertas"
		self.pila.pop()
		if tag.startswith("h") and len(tag) == 2:
			self._actual = None

	def handle_data(self, data: str) -> None:
		if self._actual is not None:
			nivel, hasta_ahora = self.encabezados[-1]
			self.encabezados[-1] = (nivel, hasta_ahora + data)


# ── Fichas ───────────────────────────────────────────────────────────────────


def test_ficha_de_un_paso_hecho_a_mano_no_habla_del_mapa() -> None:
	paso = Espacio(
		tipo="paso_peatones",
		datos={"semaforo": True, "sonoro": False, "pulsador": True, "isleta": True, "longitud": 7.0, "rumbo_cruce": 180.0},
	)
	lineas = ficha_paso(paso)
	assert lineas[:3] == ["Con semáforo.", "Sin señal sonora.", "Con pulsador."]
	assert "Con isleta en medio: se cruza en dos tiempos." in lineas
	assert any("7 metros de calzada" in linea and "sur" in linea for linea in lineas)
	assert not any("el mapa no lo dice" in linea for linea in lineas)
	assert estado_de(paso.datos, "vibracion") == "desconocido"
	sin_semaforo = Espacio(tipo="paso_peatones", datos={"semaforo": False})
	assert ficha_paso(sin_semaforo) == ["Sin semáforo: hay que escuchar el tráfico para cruzar."]


def test_ficha_de_un_paso_importado_distingue_no_tiene_de_no_se_sabe() -> None:
	datos = {
		"semaforo": False,
		"isleta": False,
		"segun_mapa": {"semaforo": "desconocido", "sonoro": "desconocido", "isleta": "no", "tactil": "si", "bordillo": "desconocido"},
	}
	lineas = ficha_paso(Espacio(tipo="paso_peatones", datos=datos))
	assert "Semáforo: el mapa no lo dice." in lineas
	assert "Sin isleta." in lineas
	assert "Con pavimento táctil." in lineas
	assert "Bordillo: el mapa no lo dice." in lineas
	escalera = Espacio(
		tipo="escalera",
		datos={"peldanos": None, "pasamanos": "", "pasamanos_lado_desconocido": True, "sube_hacia": 90.0, "segun_mapa": {"tactil": "no"}},
	)
	assert ficha_escalera(escalera) == [
		"Número de peldaños: el mapa no lo dice.",
		"Con pasamanos; en qué lado, el mapa no lo dice.",
		"Se sube hacia el este.",
		"Sin pavimento táctil de aviso.",
	]


# ── Descripción ──────────────────────────────────────────────────────────────


def test_descripcion_de_un_interior_por_plantas_y_espacios() -> None:
	centro = ejemplos.centro_dos_plantas()
	documento = texto.a_texto(centro)
	lineas = documento.splitlines()
	assert lineas[0] == centro.nombre.upper()
	assert "PLANTA: PLANTA BAJA" in lineas and "PLANTA: PLANTA PRIMERA" in lineas
	assert "ESCALERAS, RAMPAS Y ASCENSORES ENTRE PLANTAS" in lineas
	for espacio in centro.plantas[0].espacios:
		assert espacio.nombre in lineas  # cada espacio tiene su encabezado
	assert any(linea.strip().startswith("Vecinos:") for linea in lineas)
	assert any("puerta de" in linea and "en la pared" in linea for linea in lineas)
	assert any("peldaños" in linea for linea in lineas)
	assert "Datos del mapa" not in documento  # un entorno propio no cita a OpenStreetMap
	# Cada línea con contenido es una frase completa.
	assert all(
		linea.rstrip().endswith((".", ":")) or linea.isupper() or linea in {e.nombre for p in centro.plantas for e in p.espacios}
		for linea in lineas
		if linea.strip()
	)


def test_descripcion_de_un_exterior_importado(cruce) -> None:
	documento = texto.a_texto(cruce)
	for encabezado in (
		"PROCEDENCIA",
		"Calles",
		"Cruces",
		"Pasos de peatones",
		"Paradas de transporte",
		"Edificios y portales",
		"Obstáculos y mobiliario",
	):
		assert f"\n{encabezado}\n" in documento
	assert "Atribución obligatoria: © colaboradores de OpenStreetMap." in documento
	assert "Datos del mapa: © colaboradores de OpenStreetMap (ODbL 1.0)." in documento
	assert "DEDUCIDA: el mapa no dice si existe" in documento
	assert "figura en el mapa, pero su anchura no" in documento
	assert "Semáforo: el mapa no lo dice." in documento
	assert "Con señal sonora." in documento
	assert "cruce en cruz" in documento
	assert "Portal número 12 de Edificio de viviendas" in documento
	assert "Líneas, según el mapa: 3, 7." in documento
	assert "Número de peldaños: el mapa no lo dice." in documento
	assert "latitud 40,0" in documento
	# La ficha de cada paso no se repite con su descripción automática.
	assert documento.count("Con vibración en el poste.") == 1


def test_markdown_con_encabezados_en_orden(cruce) -> None:
	documento = texto.a_markdown(cruce)
	encabezados = [linea for linea in documento.splitlines() if linea.startswith("#")]
	assert encabezados[0] == "# Cruce de prueba"
	assert "## Procedencia" in encabezados and "### Calles" in encabezados
	assert "#### Paso con semáforo de Calle Mayor" in encabezados
	niveles = [len(linea.split(" ")[0]) for linea in encabezados]
	assert all(siguiente - anterior <= 1 for anterior, siguiente in zip(niveles, niveles[1:], strict=False))
	assert "- Con semáforo." in documento
	assert "  - Acera norte de Calle Mayor, tramo 1" in documento


def test_html_accesible_y_bien_formado(cruce) -> None:
	documento = texto.a_html(cruce)
	assert documento.startswith("<!DOCTYPE html>")
	esquema = _Esquema()
	esquema.feed(documento)
	esquema.close()
	assert esquema.pila == []
	assert esquema.idioma == "es"
	assert esquema.encabezados[0] == (1, "Cruce de prueba")
	assert [nivel for nivel, _titulo in esquema.encabezados].count(1) == 1
	niveles = [nivel for nivel, _titulo in esquema.encabezados]
	assert all(siguiente - anterior <= 1 for anterior, siguiente in zip(niveles, niveles[1:], strict=False))
	assert esquema.elementos_de_lista > 30
	assert "<script" not in documento and "<style" not in documento
	# Sin el DOCTYPE es XML bien formado: se puede volver a analizar.
	raiz = ET.fromstring(
		documento.split("\n", 1)[1]
		.replace('<meta charset="utf-8">', "")
		.replace('<meta name="viewport" content="width=device-width, initial-scale=1">', "")
	)
	assert raiz.find("body/main/h1").text == "Cruce de prueba"
	peligroso = ejemplos.vivienda_ejemplo()
	peligroso.nombre = "<script>alert(1)</script> & compañía"
	escapado = texto.a_html(peligroso)
	assert "<script>" not in escapado and "&lt;script&gt;" in escapado and "&amp; compañía" in escapado


def test_guardar_descripcion_por_extension(tmp_path: Path) -> None:
	vivienda = ejemplos.vivienda_ejemplo()
	assert texto.guardar_descripcion(vivienda, tmp_path / "casa.md").read_text(encoding="utf-8").startswith("# Vivienda de ejemplo")
	assert texto.guardar_descripcion(vivienda, tmp_path / "casa.html").read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
	assert texto.guardar_descripcion(vivienda, tmp_path / "casa.txt").read_text(encoding="utf-8").startswith("VIVIENDA DE EJEMPLO")
	assert texto.describir(vivienda, "txt") == texto.a_texto(vivienda)
	with pytest.raises(ValueError):
		texto.describir(vivienda, "pdf")
	assert len(texto.estructura(vivienda)) >= 8


# ── Indicaciones ─────────────────────────────────────────────────────────────


def test_indicaciones_en_un_interior_con_puertas() -> None:
	vivienda = ejemplos.vivienda_ejemplo()
	planta = vivienda.plantas[0]
	# De la entrada al salón: por el hueco al pasillo y por la puerta del salón (x entre 1,5 y 2,4).
	ruta = [(planta.id, -1.0, 4.6), (planta.id, 1.95, 4.6), (planta.id, 1.95, 2.0)]
	resultado = indicaciones.redactar(vivienda, ruta)
	textos = [paso.texto for paso in resultado.pasos]
	assert textos[0] == "Empiezas en Entrada, planta Vivienda. Ponte mirando al este."
	assert "Cruza «Hueco entre Entrada y Pasillo» y entra en Pasillo." in textos[1]
	assert textos[1].startswith("Avanza 1 metro.")
	assert "Gira a la derecha" in textos[2] and "quedas mirando al sur" in textos[2]
	assert "Cruza «Puerta entre Salón y Pasillo» y entra en Salón." in " ".join(textos)
	assert "has llegado: estás en Salón" in textos[-1]
	assert resultado.total_m == pytest.approx(2.95 + 2.6)
	assert resultado.resumen == "Ruta de 5,5 metros, 1 giro."
	assert resultado.pasos[0].tipo == "salida" and resultado.pasos[-1].tipo == "llegada"
	assert resultado.a_texto().splitlines()[2].startswith("1. Empiezas")
	assert resultado.a_markdown().startswith("# Ruta de")


def test_indicaciones_en_la_calle_con_paso_y_calzada(cruce) -> None:
	planta = cruce.plantas[0]
	ruta = [
		(planta.id, -30.0, 4.2),
		(planta.id, -20.0, 4.2),
		(planta.id, -20.0, -4.2),
		(planta.id, -6.0, -4.2),
		(planta.id, 2.9, -6.0),
		(planta.id, 2.9, -30.0),
	]
	resultado = indicaciones.redactar(cruce, ruta)
	completo = resultado.a_texto()
	assert "Cruza por «Paso con semáforo de Calle Mayor»" in completo
	assert "tiene semáforo con señal sonora, con pulsador" in completo
	assert "a la altura de «Semáforo norte de Paso con semáforo de Calle Mayor»" in completo
	assert "Atención: bajas a la calzada («Calzada de Calle del Río») sin paso de peatones." in completo
	assert "2 cruces de calzada" in resultado.resumen and "3 giros" in resultado.resumen
	assert "© colaboradores de OpenStreetMap" in resultado.nota
	assert [paso.tipo for paso in resultado.pasos].count("cruce") == 2
	# Por el paso sin datos, la indicación no inventa un semáforo ni su ausencia.
	otra = indicaciones.redactar(cruce, [(planta.id, -2.9, -15.0), (planta.id, 2.9, -15.0)])
	assert "el mapa no dice si tiene semáforo" in otra.a_texto()


def test_indicaciones_en_pasos_y_por_horas_del_reloj(cruce) -> None:
	planta = cruce.plantas[0]
	ruta = [Posicion(planta.id, -30.0, 4.2), Posicion(planta.id, -20.0, 4.2), Posicion(planta.id, -20.0, -4.2)]
	opciones = indicaciones.OpcionesIndicaciones(unidad="pasos", paso_m=0.5, giros="reloj", referencias=False)
	resultado = indicaciones.redactar(cruce, ruta, opciones)
	completo = resultado.a_texto()
	assert "Avanza 20 pasos. Gira hacia las 3: quedas mirando al sur." in completo
	assert "a la altura de" not in completo
	assert resultado.resumen.startswith("Ruta de 37 pasos")


def test_indicaciones_con_cambio_de_planta() -> None:
	centro = ejemplos.centro_dos_plantas()
	escalera = next(c for c in centro.conectores if c.tipo == "escalera")
	tramo = escalera.tramos[0]
	ascensor = next(c for c in centro.conectores if c.tipo == "ascensor")
	abajo, arriba = centro.plantas
	ruta = [
		{"planta": tramo.desde.planta, "puntos": [[tramo.desde.x - 2.0, tramo.desde.y], [tramo.desde.x, tramo.desde.y]]},
		(tramo.hasta.planta, [(tramo.hasta.x, tramo.hasta.y), (tramo.hasta.x - 1.5, tramo.hasta.y)]),
	]
	resultado = indicaciones.redactar(centro, ruta)
	cambio = next(paso for paso in resultado.pasos if paso.tipo == "planta")
	assert cambio.texto.startswith(f"Sube por «{escalera.nombre}» hasta la planta {arriba.nombre}")
	assert "peldaños" in cambio.texto and "pasamanos" in cambio.texto
	assert "1 cambio de planta" in resultado.resumen
	parada_abajo = next(p.puerta for p in ascensor.paradas if p.planta == abajo.id)
	parada_arriba = next(p.puerta for p in ascensor.paradas if p.planta == arriba.id)
	bajando = indicaciones.redactar(centro, [(arriba.id, parada_arriba.x, parada_arriba.y), (abajo.id, parada_abajo.x, parada_abajo.y)])
	assert any(paso.texto.startswith(f"Toma «{ascensor.nombre}» hasta la planta {abajo.nombre}") for paso in bajando.pasos)


def test_indicaciones_rechazan_rutas_que_no_sirven() -> None:
	vivienda = ejemplos.vivienda_ejemplo()
	with pytest.raises(ValueError):
		indicaciones.redactar(vivienda, [])
	with pytest.raises(ValueError):
		indicaciones.redactar(vivienda, [("planta-que-no-existe", 0.0, 0.0), ("planta-que-no-existe", 1.0, 0.0)])
	with pytest.raises(ValueError):
		indicaciones.redactar(vivienda, ["esto no es un punto"])
	with pytest.raises(ValueError):
		indicaciones.normalizar_ruta([("pla-1", "x", 2.0)])
	planta = vivienda.plantas[0]
	assert indicaciones.normalizar_ruta([(planta.id, 1, 1), (planta.id, 1.0, 1.01), {"planta": planta.id, "x": 2, "y": 1}]) == [
		(planta.id, 1.0, 1.0),
		(planta.id, 2.0, 1.0),
	]
	un_punto = indicaciones.redactar(vivienda, [(planta.id, 2.0, 2.0)])
	assert un_punto.pasos[0].texto == "Empiezas en Salón, planta Vivienda."
	assert un_punto.total_m == 0.0
