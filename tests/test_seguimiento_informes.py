"""Pruebas de los informes en texto, HTML accesible y CSV, y de la narración del recorrido."""

from __future__ import annotations

import csv
import io
import re
from html.parser import HTMLParser

import pytest

from app.seguimiento import cuaderno, informes, sesiones
from app.seguimiento.alumnos import Fichas
from app.seguimiento.base import BaseSeguimiento
from tests._seguimiento_util import ESPACIOS, andar, documento_sesion

ID1 = "1" * 32
ID2 = "2" * 32
ID3 = "3" * 32

# Palabras que un informe descriptivo no debe contener (salvo en el aviso, que las niega).
PROHIBIDAS = ("diagnóstico", "recomienda", "recomendación", "debería", "mejorado", "empeorado", "seguro cruzar", "apto", "competente")


class Estructura(HTMLParser):
	"""Recoge lo que hace falta para comprobar la accesibilidad del HTML."""

	def __init__(self) -> None:
		super().__init__()
		self.encabezados: list[str] = []
		self.tablas = 0
		self.captions = 0
		self.th_sin_scope = 0
		self.th = 0
		self.lang = ""
		self.etiquetas: set[str] = set()
		self.atributos: set[str] = set()

	def handle_starttag(self, tag, attrs):
		datos = dict(attrs)
		self.etiquetas.add(tag)
		self.atributos.update(datos)
		if tag in ("h1", "h2", "h3", "h4"):
			self.encabezados.append(tag)
		elif tag == "table":
			self.tablas += 1
		elif tag == "caption":
			self.captions += 1
		elif tag == "th":
			self.th += 1
			if datos.get("scope") not in ("col", "row"):
				self.th_sin_scope += 1
		elif tag == "html":
			self.lang = datos.get("lang", "")


@pytest.fixture
def datos(tmp_path):
	with BaseSeguimiento(tmp_path / "p.db") as base:
		luna = Fichas(base).alta("Luna", nombre_real="Nombre Real Secreto")
		examen = {
			"examen": {
				"puntos": 5,
				"pruebas": [
					{"ruta": "A", "acierto": True, "tiempo_s": 42.0, "puntos": 3},
					{"ruta": "B", "acierto": False, "tiempo_s": 90.0, "puntos": 0},
				],
			}
		}
		sesiones.guardar_sesion(
			base,
			luna.id,
			documento_sesion(
				ID1, inicio="2026-11-10T10:00:00+00:00", fin="2026-11-10T10:06:00+00:00", marcas=[{"t": 3.0, "texto": "Duda <aquí> & allí"}]
			),
		)
		sesiones.guardar_sesion(
			base,
			luna.id,
			documento_sesion(ID2, inicio="2026-11-17T10:00:00+00:00", fin="2026-11-17T10:04:00+00:00", resumen={"tiempo_activo_s": 4.0}),
		)
		sesiones.guardar_sesion(
			base,
			luna.id,
			documento_sesion(
				ID3, inicio="2026-11-20T10:00:00+00:00", fin="2026-11-20T10:09:00+00:00", actividad="examen1", modo="examen", resumen=examen
			),
		)
		sesiones.anotar(base, ID1, "Nota del profesional")
		cuaderno.anotar(
			base,
			luna.id,
			fecha="2026-11-24",
			lugar="Casa real",
			entorno_id="casa",
			entorno_nombre="Casa de ejemplo",
			rutas=[{"nombre": "Entrada a cocina", "resultado": "conseguida"}, {"nombre": "Cocina a baño", "resultado": "con_ayuda"}],
			nivel_ayuda="indicacion_verbal",
			tipo_recorrido="entrenado",
			ayudas_movilidad=["bastón largo"],
			observaciones="Observación de campo",
		)
		yield {
			"base": base,
			"alumno": luna,
			"lista": sesiones.listar(base, luna.id),
			"una": sesiones.obtener(base, ID1, con_traza=True),
			"examen": sesiones.obtener(base, ID3),
			"evaluaciones": cuaderno.listar(base, luna.id),
		}


def _todos(datos):
	return {
		"sesion": informes.informe_sesion(datos["una"], alias="Luna", espacios=ESPACIOS),
		"comparacion": informes.comparar_sesiones(datos["lista"][:2], alias="Luna"),
		"evolucion": informes.evolucion(datos["lista"], alias="Luna"),
		"examen": informes.informe_examen(datos["examen"], alias="Luna"),
		"real": informes.informe_real_frente_virtual(datos["evaluaciones"], datos["lista"], alias="Luna"),
	}


def test_los_cinco_informes_en_los_tres_formatos(datos):
	for nombre, informe in _todos(datos).items():
		for formato in informes.FORMATOS:
			salida = informes.generar(informe, formato)
			assert salida.strip(), (nombre, formato)
			assert "no equivale a competencia en el lugar real" in salida, (nombre, formato)
			assert "Nombre Real Secreto" not in salida, (nombre, formato)
			assert "Luna" in salida, (nombre, formato)


def test_informe_de_sesion_en_texto(datos):
	texto = informes.a_texto(informes.informe_sesion(datos["una"], alias="Luna", espacios=ESPACIOS))
	assert texto.startswith("Informe de sesión: Casa de ejemplo")
	assert "- Distancia recorrida: 8,0 m" in texto
	assert "- Tiempo en pausa: 12 s" in texto
	assert "1 choque." in texto
	assert "1 ayuda pedida." in texto
	assert "donde_estoy" in texto
	assert "Llave dorada" in texto
	assert "Sala de estar" in texto
	assert "- Baño" in texto  # espacio sin visitar
	assert "- Cocina" in texto
	assert "FORMA DE EXPLORAR" in texto
	assert "no una valoración" in texto
	assert "Duda <aquí> & allí" in texto
	assert "Notas: Nota del profesional" in texto
	assert "|" not in texto and "+--" not in texto  # sin dibujos de tabla


def test_los_informes_son_descriptivos(datos):
	for nombre, informe in _todos(datos).items():
		texto = informes.a_texto(informe)
		cuerpo = texto.split("AVISO")[0].lower()
		for palabra in PROHIBIDAS:
			assert palabra not in cuerpo, (nombre, palabra)


def test_html_accesible(datos):
	for nombre, informe in _todos(datos).items():
		pagina = informes.a_html(informe)
		estructura = Estructura()
		estructura.feed(pagina)
		assert pagina.startswith("<!DOCTYPE html>"), nombre
		assert estructura.lang == "es", nombre
		assert estructura.encabezados.count("h1") == 1, nombre
		assert estructura.encabezados[0] == "h1", nombre
		# Jerarquía sin saltos: después del h1 solo hay h2 (ningún h3 colgando de un h1).
		assert set(estructura.encabezados[1:]) == {"h2"}, nombre
		assert estructura.tablas >= 1, nombre
		assert estructura.captions == estructura.tablas, nombre
		assert estructura.th > 0 and estructura.th_sin_scope == 0, nombre
		assert not {"script", "img", "link", "iframe", "font"} & estructura.etiquetas, nombre
		assert not {"bgcolor", "color", "onclick"} & estructura.atributos, nombre
		assert "color:" not in pagina and "background" not in pagina, nombre
		assert '<meta charset="utf-8">' in pagina, nombre


def test_html_escapa_el_texto_del_profesional(datos):
	pagina = informes.a_html(informes.informe_sesion(datos["una"], alias="<b>Luna</b>"))
	assert "Duda &lt;aquí&gt; &amp; allí" in pagina
	assert "&lt;b&gt;Luna&lt;/b&gt;" in pagina
	assert "<b>" not in pagina


def test_csv_se_puede_leer_y_no_contiene_formulas(datos):
	informe = informes.informe_sesion(datos["una"], alias='=HIPERVINCULO("x")')
	filas = list(csv.reader(io.StringIO(informes.a_csv(informe)), delimiter=";"))
	assert filas[0] == ["Informe de sesión: Casa de ejemplo"]
	assert ["Medida", "Valor"] in filas
	assert ["Distancia recorrida", "8,0 m"] in filas
	assert ["Alumno (alias)", '\'=HIPERVINCULO("x")'] in filas
	assert filas[-1][0] == "Aviso"
	for fila in filas:
		for celda in fila:
			assert not re.match(r"^[=+@]", celda)


def test_guardar_deduce_el_formato(datos, tmp_path):
	informe = informes.informe_sesion(datos["una"])
	assert informes.guardar(informe, tmp_path / "a" / "informe.html").read_text(encoding="utf-8").startswith("<!DOCTYPE html>")
	assert informes.guardar(informe, tmp_path / "informe.csv").read_bytes().startswith(b"\xef\xbb\xbf")
	assert informes.guardar(informe, tmp_path / "informe.txt").read_text(encoding="utf-8").startswith("Informe de sesión")
	with pytest.raises(ValueError):
		informes.generar(informe, "pdf")


def test_comparacion_describe_el_cambio_sin_calificarlo(datos):
	texto = informes.a_texto(informes.comparar_sesiones(datos["lista"][:2], alias="Luna"))
	assert "Entorno: Casa de ejemplo." in texto
	assert "10/11/2026" in texto and "17/11/2026" in texto
	assert "- Tiempo activo: de 8 s a 4 s." in texto
	assert "- Choques: 1 en las dos." in texto
	mezcla = [dict(datos["lista"][0]), dict(datos["lista"][1], entorno_nombre="Otro sitio")]
	assert "entornos distintos" in informes.a_texto(informes.comparar_sesiones(mezcla))
	with pytest.raises(ValueError):
		informes.comparar_sesiones([dict(datos["lista"][0]), dict(datos["lista"][1], alumno_id=99)])
	assert "No hay sesiones" in informes.a_texto(informes.comparar_sesiones([]))


def test_evolucion_agrupa_por_entorno_y_actividad(datos):
	informe = informes.evolucion(datos["lista"], alias="Luna")
	titulos = [seccion.titulo for seccion in informe.secciones]
	assert titulos == ["Resumen", "Casa de ejemplo: Buscar la llave"]
	texto = informes.a_texto(informe)
	assert "3 sesiones entre el" in texto
	assert "No hay sesiones guardadas." in informes.a_texto(informes.evolucion([]))


def test_informe_de_examen(datos):
	texto = informes.a_texto(informes.informe_examen(datos["examen"], alias="Luna"))
	assert "PUNTUACIONES DEL EXAMEN" in texto
	assert "- Puntos: 5" in texto
	assert "Ruta: A; Acierto: sí; Tiempo: 42 s; Puntos: 3" in texto
	assert "Ruta: B; Acierto: no; Tiempo: 1 min 30 s; Puntos: 0" in texto
	assert "El tiempo en pausa no cuenta" in texto
	sin_puntos = informes.a_texto(informes.informe_examen(datos["una"]))
	assert "no tiene puntuaciones de examen" in sin_puntos


def test_informe_real_frente_a_virtual(datos):
	texto = informes.a_texto(informes.informe_real_frente_virtual(datos["evaluaciones"], datos["lista"], alias="Luna"))
	assert "EVALUACIÓN REAL DEL 24/11/2026: CASA REAL" in texto
	assert "- Nivel de ayuda: Con indicaciones verbales" in texto
	assert "- Días desde el último entrenamiento en el simulador: 4" in texto
	assert "Ruta: Cocina a baño; Resultado: Conseguida con ayuda" in texto
	assert "Observaciones del profesional: Observación de campo" in texto
	assert "3 sesiones en el simulador antes de esta evaluación." in texto
	vacio = informes.a_texto(informes.informe_real_frente_virtual([], datos["lista"]))
	assert "No hay evaluaciones reales anotadas." in vacio


def test_describir_recorrido_paso_a_paso():
	traza = {
		"muestras": andar([(1, 1), (5, 1), (5, 4), (12, 4)]),
		"eventos": [
			{"t": 2.0, "tipo": "choque", "datos": {"con": "la mesa"}},
			{"t": 9.0, "tipo": "entrada_espacio", "datos": {"espacio": "cocina"}},
			{"t": 13.0, "tipo": "premio", "datos": {"nombre": "Llave"}},
		],
		"pausas": [[4.0, 75.0]],
	}
	pasos = informes.describir_recorrido(traza, espacios=ESPACIOS)
	assert pasos[0] == "Empieza en Sala de estar, mirando al este."
	assert pasos[1] == "Avanza 2,0 metros."
	assert pasos[2] == "Choca con la mesa."
	assert "Pausa de 1 min 15 s." in pasos
	assert "Gira a la izquierda, unos 90 grados." in pasos
	assert "Gira a la derecha, unos 90 grados." in pasos
	assert "Entra en Cocina." in pasos
	assert "Encuentra el premio «Llave»." in pasos
	assert pasos[-1] == "Termina en Cocina."
	# El orden es el del recorrido: el giro a la izquierda va antes que el de la derecha.
	assert pasos.index("Gira a la izquierda, unos 90 grados.") < pasos.index("Gira a la derecha, unos 90 grados.")
	metros = sum(float(re.search(r"([\d,]+) metro", p).group(1).replace(",", ".")) for p in pasos if p.startswith("Avanza"))
	assert metros == pytest.approx(14.0, abs=0.6)


def test_describir_recorrido_en_pasos_con_tiempos_y_casos_limite():
	traza = {"muestras": andar([(1, 1), (1, 4.5)]), "eventos": []}
	pasos = informes.describir_recorrido(traza, unidad="pasos", paso_m=0.7, con_tiempos=True)
	assert pasos[0] == "0 s. Empieza mirando al norte."
	assert pasos[1] == "0 s. Avanza 5 pasos."
	assert pasos[-1].endswith("Fin del recorrido.")
	assert informes.describir_recorrido({}) == ["No hay recorrido grabado."]
	salto = {"muestras": andar([(1, 1), (2, 1)]) + andar([(9, 7), (9, 6)], t0=1.25) + andar([(9, 6), (9, 5)], planta="p1", t0=2.5)}
	narrado = informes.describir_recorrido(salto)
	assert "Es recolocado en otro punto." in narrado
	assert "Cambia a la planta p1." in narrado
	media_vuelta = {
		"muestras": [
			[0, "p0", 0, 0, 0],
			[0.25, "p0", 0, 0, 90],
			[0.5, "p0", 0, 0, 180],
			[0.75, "p0", 0, 0.5, 180],
			[1.0, "p0", 0, 1.0, 180],
		]
	}
	narrado = informes.describir_recorrido(media_vuelta)
	assert "Da media vuelta." in narrado
	assert "Retrocede 1 metro." in narrado
