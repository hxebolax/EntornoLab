"""Progreso por fases y cancelación de la importación de OpenStreetMap (sin wx y sin red).

Lo que se comprueba es lo que el profesional necesita oír durante una
importación larga: en qué fase está, con cifras reales («Convirtiendo calles:
12 de 30»), los bytes que van llegando y a qué servidor se pide, y que
cancelar corta de verdad, también mientras el servidor prepara los datos.
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from app.importar import comun, osm
from app.importar.comun import ImportacionCancelada

DATOS = Path(__file__).parent / "datos"
OVERPASS = DATOS / "osm_real_valladolid_overpass.json"
LAT, LON = 41.6520609, -4.7285484


class Registro:
	"""Función de progreso con ``por_fases``, como la del diálogo: apunta todo lo que recibe."""

	def __init__(self) -> None:
		self.simples: list[tuple[float, str]] = []
		self.fases: list[dict] = []

	def __call__(self, fraccion: float, texto: str) -> None:
		self.simples.append((fraccion, texto))

	def por_fases(self, fraccion, texto, fase, hecho, total, indeterminado) -> None:
		self.fases.append(
			{"fraccion": fraccion, "texto": texto, "fase": fase, "hecho": hecho, "total": total, "indeterminado": indeterminado}
		)

	def nombres_de_fase(self) -> list[str]:
		vistos: list[str] = []
		for aviso in self.fases:
			if not vistos or vistos[-1] != aviso["fase"]:
				vistos.append(aviso["fase"])
		return vistos


def _plaza() -> dict:
	datos = osm.importar_fichero_osm(OVERPASS)
	datos["recuadro"] = list(osm.recuadro_de(LAT, LON, 150.0))
	datos["centro"] = [LAT, LON]
	return datos


# ── Conversión ───────────────────────────────────────────────────────────────


def test_la_conversion_dice_cada_fase_con_sus_recuentos() -> None:
	registro = Registro()
	resultado = osm.convertir(_plaza(), osm.OpcionesOSM(nombre="Plaza"), registro)
	assert not registro.simples, "con por_fases no se llama además a la forma simple"
	nombres = registro.nombres_de_fase()
	for fase in (
		"Leyendo los datos del mapa",
		"Creando edificios y portales",
		"Convirtiendo calles",
		"Formando los cruces",
		"Creando aceras",
		"Colocando pasos de peatones",
		"Colocando obstáculos y mobiliario",
		"Colocando comercios y servicios",
		"Buscando el punto de inicio",
		"Comprobando el entorno",
	):
		assert fase in nombres, nombres
	# Las cifras son las reales: 16 calles y 133 edificios en la muestra.
	calles = [a for a in registro.fases if a["fase"] == "Convirtiendo calles" and a["total"]]
	assert calles[-1]["hecho"] == calles[-1]["total"] == 16
	assert calles[-1]["texto"] == "Convirtiendo calles: 16 de 16."
	edificios = [a for a in registro.fases if a["fase"] == "Creando edificios y portales" and a["total"]]
	assert edificios[-1]["hecho"] == edificios[-1]["total"] >= 133
	comprobar = next(a for a in registro.fases if a["fase"] == "Comprobando el entorno")
	espacios = len(resultado.entorno.plantas[0].espacios)
	assert comprobar["texto"] == f"Comprobando el entorno: {espacios} espacios."
	fracciones = [a["fraccion"] for a in registro.fases]
	assert fracciones == sorted(fracciones), "la barra nunca va hacia atrás"
	assert registro.fases[-1]["fraccion"] == 1.0
	assert not any(a["indeterminado"] for a in registro.fases), "la conversión siempre sabe cuánto le falta"


def test_la_conversion_con_progreso_simple_recibe_los_mismos_textos() -> None:
	avances: list[tuple[float, str]] = []
	osm.convertir(_plaza(), progreso=lambda fraccion, texto: avances.append((fraccion, texto)))
	textos = [texto for _fraccion, texto in avances]
	assert "Convirtiendo calles: 16 de 16." in textos
	assert textos[-1] == "Importación terminada."


def test_la_conversion_registra_la_duracion_de_cada_fase(caplog: pytest.LogCaptureFixture) -> None:
	with caplog.at_level("INFO", logger="app.importar.osm_conversion"):
		osm.convertir(_plaza())
	lineas = [r.getMessage() for r in caplog.records if "Duración de cada fase" in r.getMessage()]
	assert lineas, [r.getMessage() for r in caplog.records]
	for clave in ("leer", "edificios", "calles", "aceras", "lugares", "inicio", "comprobar"):
		assert f"{clave} " in lineas[0]
	assert any("elementos del mapa convertidos en" in r.getMessage() for r in caplog.records)


@pytest.mark.parametrize("fase_de_corte", ["Creando edificios y portales", "Convirtiendo calles", "Colocando comercios y servicios"])
def test_cancelar_en_mitad_de_una_fase_detiene_la_conversion(fase_de_corte: str, caplog: pytest.LogCaptureFixture) -> None:
	registro = Registro()
	pedido = threading.Event()
	original = registro.por_fases

	def por_fases(fraccion, texto, fase, hecho, total, indeterminado) -> None:
		original(fraccion, texto, fase, hecho, total, indeterminado)
		if fase == fase_de_corte and hecho:
			pedido.set()

	registro.por_fases = por_fases  # type: ignore[method-assign]
	with caplog.at_level("INFO", logger="app.importar.osm_conversion"), pytest.raises(ImportacionCancelada):
		osm.convertir(_plaza(), progreso=registro, cancelado=pedido.is_set)
	nombres = registro.nombres_de_fase()
	assert nombres[-1] == fase_de_corte, "se detiene en la misma fase, sin empezar la siguiente"
	assert any("detenida" in r.getMessage() for r in caplog.records)


# ── Descarga ─────────────────────────────────────────────────────────────────


def test_la_descarga_dice_servidor_bytes_y_reintentos(data_temporal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	from app.core import red

	cuerpo = OVERPASS.read_bytes()
	peticiones: list[str] = []

	class Respuesta:
		headers: dict = {}

		def __init__(self) -> None:
			self._resto = cuerpo

		def read1(self, cantidad: int) -> bytes:
			# Un servidor lento: cada trozo tarda un poco en llegar.
			time.sleep(0.15)
			trozo, self._resto = self._resto[:cantidad], self._resto[cantidad:]
			return trozo

		def __enter__(self) -> Respuesta:
			return self

		def __exit__(self, *_argumentos) -> None:
			return None

	def abrir(url: str, *_argumentos, **_opciones) -> Respuesta:
		peticiones.append(url)
		if len(peticiones) == 1:
			raise red.ErrorRed("El servidor está saturado.", categoria="servidor", reintentar=True, codigo_http=503)
		return Respuesta()

	monkeypatch.setattr(red, "abrir", abrir)
	monkeypatch.setattr(osm, "TROZO_DESCARGA", 64 * 1024)
	monkeypatch.setattr(osm, "PAUSA_REINTENTO", 0.0)
	monkeypatch.setattr(osm, "INTERVALO_AVISO_DESCARGA", 0.0)
	registro = Registro()
	datos = osm.descargar_zona(LAT, LON, 150.0, servidores=("https://overpass.invalid/api",), usar_cache=False, progreso=registro)
	assert len(datos["elements"]) == 2488 and len(peticiones) == 2
	textos = [aviso["texto"] for aviso in registro.fases]
	assert textos[0] == "Pidiendo el mapa de la zona a overpass.invalid (servidor 1 de 1)."
	assert any("se vuelve a intentar (intento 2 de 2)" in texto for texto in textos), textos
	assert "Descargando el mapa de OpenStreetMap desde overpass.invalid (intento 2 de 2)" in registro.nombres_de_fase()
	recibidos = [aviso["hecho"] for aviso in registro.fases if aviso["texto"].startswith("Descargando datos de OpenStreetMap:")]
	assert recibidos and recibidos == sorted(recibidos), "los bytes recibidos solo crecen"
	assert any(t.startswith("Descargando datos de OpenStreetMap: ") and t.endswith(" KB.") for t in textos)
	assert textos[-1] == "Mapa de la zona descargado: 2488 elementos, 369 KB."
	assert all(aviso["indeterminado"] for aviso in registro.fases), "Overpass no dice cuánto ocupa: barra indeterminada"


def test_la_descarga_registra_bytes_y_segundos(data_temporal: Path, caplog: pytest.LogCaptureFixture) -> None:
	with caplog.at_level("INFO", logger="app.importar.osm"):
		osm.descargar_zona(
			LAT,
			LON,
			150.0,
			servidores=("https://overpass.invalid/api",),
			descargar=lambda url, datos=None: OVERPASS.read_bytes(),
			usar_cache=False,
		)
	linea = next(r.getMessage() for r in caplog.records if r.getMessage().startswith("Descarga de Overpass desde"))
	assert "overpass.invalid" in linea and f"{OVERPASS.stat().st_size} bytes" in linea and "2488 elementos" in linea


def test_cancelar_mientras_el_servidor_prepara_los_datos(data_temporal: Path, monkeypatch: pytest.MonkeyPatch) -> None:
	monkeypatch.setattr(osm, "INTERVALO_AVISO_DESCARGA", 0.0)
	soltar = threading.Event()

	def descargar_lento(url: str, datos: bytes | None = None) -> bytes:
		# Overpass pensando: no llega ni un byte hasta que se suelta (o pasan 30 s).
		soltar.wait(30.0)
		return b"{}"

	registro = Registro()
	cancelar = threading.Event()
	threading.Timer(0.5, cancelar.set).start()
	inicio = time.monotonic()
	try:
		with pytest.raises(ImportacionCancelada):
			osm.descargar_zona(
				LAT,
				LON,
				150.0,
				servidores=("https://overpass.invalid/api",),
				descargar=descargar_lento,
				usar_cache=False,
				progreso=registro,
				cancelado=cancelar.is_set,
			)
		assert time.monotonic() - inicio < 3.0, "cancelar no espera a que el servidor conteste"
	finally:
		soltar.set()
	assert any(aviso["texto"].startswith("Esperando a que overpass.invalid prepare los datos") for aviso in registro.fases)


def test_si_un_servidor_falla_dice_que_prueba_con_otro(data_temporal: Path) -> None:
	mapa = json.loads((DATOS / "cruce.osm.json").read_text(encoding="utf-8"))

	def descargar(url: str, datos: bytes | None = None) -> bytes:
		if "primero" in url:
			raise OSError("servidor ocupado")
		return json.dumps({"elements": mapa["elements"]}).encode("utf-8")

	registro = Registro()
	osm.descargar_zona(
		40.0, -3.7, 80, servidores=("https://primero.invalid/api", "https://segundo.invalid/api"), descargar=descargar, progreso=registro
	)
	textos = [aviso["texto"] for aviso in registro.fases]
	assert (
		"primero.invalid no ha dado el mapa; se prueba con otro servidor. Pidiendo el mapa de la zona a segundo.invalid (servidor 2 de 2)."
		in textos
	)


# ── Estimación previa ────────────────────────────────────────────────────────


def test_la_estimacion_crece_con_la_superficie_y_se_dice_con_palabras() -> None:
	pequena, mediana, grande = (osm.estimar_zona(radio) for radio in (150, 300, 400))
	# Calibrada con la muestra real: unos 250 espacios a 150 m y unos 1.000 a 300 m.
	assert 200 <= pequena.espacios <= 300 and 900 <= mediana.espacios <= 1100 and grande.espacios > mediana.espacios
	assert grande.bytes > mediana.bytes > pequena.bytes
	assert grande.descarga_habitual_s > grande.descarga_minima_s
	texto = grande.texto()
	assert "800 por 800 metros" in texto and "unos 1800 espacios" in texto and "MB" in texto and "cancelar" in texto
	assert osm.estimar_zona(5000).lado_m == 800, "no se estima más allá del radio máximo"


def test_textos_de_tamano_y_duracion() -> None:
	assert osm.texto_bytes(380 * 1024) == "380 KB"
	assert osm.texto_bytes(int(2.7 * 1024 * 1024)) == "2,7 MB"
	assert comun.texto_duracion(1) == "1 segundo"
	assert comun.texto_duracion(45) == "45 segundos"
	assert comun.texto_duracion(60) == "1 minuto"
	assert comun.texto_duracion(130) == "2 minutos y 10 segundos"
