"""Pruebas de la síntesis de los sonidos de serie (``app/audio/sintesis.py``).

Vigilan lo que no se puede comprobar a oído en cada cambio: que no falte
ningún sonido de los que el juego da por hechos, que nada recorte ni haga
clic, que lo que hay que localizar sea mono y tenga agudos, y que el
catálogo distribuido corresponda al código.
"""

from __future__ import annotations

import json

import numpy as np
import pytest

from app.audio import sintesis
from app.core import paths

# Parte mínima de la energía por encima de 3 kHz en un sonido que hay que situar.
MINIMO_AGUDOS = 0.02


def _obligatorios() -> list[str]:
	"""Los nombres que el resto del programa da por hechos (convención del encargo)."""
	nombres = [
		f"pasos/{suelo}_{pie}_{variante}"
		for suelo in (
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
		for pie in ("izq", "der")
		for variante in (1, 2)
	]
	for material in ("ladrillo", "madera", "metal", "cristal", "plastico", "tela", "piedra"):
		nombres += [f"golpe/{material}", f"roce/{material}"]
	familias = {
		"puerta": ("abrir", "cerrar", "con_llave", "automatica"),
		"escalera": ("subir", "bajar", "rampa"),
		"ascensor": ("llamada", "puerta", "viaje", "llegada", *(f"planta_{n}" for n in range(10))),
		"baliza": ("pulso", "alineado", "detras", "cerca", "llegada"),
		"sonda": ("pared", "puerta", "objeto", "libre", "escalon", "bordillo", "cerca", "media", "lejos"),
		"premio": ("aparece", "cerca", "recogido", "tesoro"),
		"logro": ("logro", "estrella_1", "estrella_2", "estrella_3", "medalla", "error", "pista"),
		"interfaz": ("mover", "elegir", "atras", "borde", "abrir", "cerrar", "ajuste"),
		"brujula": ("norte", "este", "sur", "oeste"),
		"eco": ("chasquido",),
		"semaforo": ("verde", "intermitente", "rojo", "pulsador"),
		"trafico": ("coche", "moto", "autobus", "ambiente_leve", "ambiente_medio", "ambiente_intenso"),
		"exterior": ("bordillo",),
		"ambiente": ("casa", "oficina", "pasillo", "calle", "parque", "cocina"),
		"fuente": (
			"frigorifico",
			"reloj",
			"grifo",
			"ventilador",
			"television",
			"fuente_agua",
			"maquina_expendedora",
			"campanas",
			"pajaros",
		),
	}
	for familia, claves in familias.items():
		nombres += [f"{familia}/{clave}" for clave in claves]
	return nombres


@pytest.fixture(scope="module")
def todos() -> dict[str, np.ndarray]:
	"""Todos los sonidos, sintetizados una sola vez para el módulo (los ambientes son largos)."""
	return sintesis.generar_todos()


def test_estan_todos_los_sonidos_obligatorios():
	faltan = [nombre for nombre in _obligatorios() if nombre not in sintesis.CATALOGO]
	assert not faltan, f"Faltan en el catálogo: {faltan}"


def test_los_nombres_siguen_la_convencion():
	for nombre in sintesis.nombres():
		assert nombre == nombre.lower()
		assert nombre.isascii(), nombre
		assert nombre.count("/") == 1 and " " not in nombre, nombre


def test_el_catalogo_esta_completo_y_sus_textos_se_rellenan():
	grupos = {identificador for identificador, _nombre in sintesis.GRUPOS}
	assert len(grupos) == len(sintesis.GRUPOS)
	usados = set()
	for nombre, definicion in sintesis.CATALOGO.items():
		assert definicion.clave == nombre
		assert definicion.grupo in grupos, nombre
		usados.add(definicion.grupo)
		for texto in (definicion.nombre_visible(), definicion.explicacion_visible()):
			assert texto.strip(), nombre
			assert "{" not in texto and "}" not in texto, f"{nombre}: quedó un hueco sin rellenar en «{texto}»"
		assert 0.0 < definicion.pico <= 0.8, nombre
	assert usados == grupos, "Hay grupos sin ningún sonido"
	visibles = [definicion.nombre_visible() for definicion in sintesis.CATALOGO.values()]
	assert len(set(visibles)) == len(visibles), "Dos sonidos se llaman igual en voz alta"


def test_generar_es_determinista():
	for nombre in ("baliza/pulso", "pasos/grava_izq_2", "golpe/metal", "fuente/pajaros", "premio/tesoro"):
		assert np.array_equal(sintesis.generar(nombre), sintesis.generar(nombre)), nombre


def test_las_variantes_de_un_paso_son_distintas():
	uno = sintesis.generar("pasos/baldosa_izq_1")
	dos = sintesis.generar("pasos/baldosa_izq_2")
	assert uno.shape != dos.shape or not np.array_equal(uno, dos)


def test_un_nombre_desconocido_no_se_genera():
	with pytest.raises(KeyError):
		sintesis.generar("no/existe")


def test_nada_recorta_ni_es_silencio(todos):
	assert list(todos) == sintesis.nombres()
	for nombre, datos in todos.items():
		definicion = sintesis.CATALOGO[nombre]
		assert datos.dtype == np.float32, nombre
		assert datos.ndim in (1, 2) and len(datos) > 100, nombre
		assert np.isfinite(datos).all(), nombre
		pico = float(np.max(np.abs(datos)))
		assert pico <= 0.8 + 1e-6, f"{nombre}: pico {pico:.3f}"
		assert pico == pytest.approx(definicion.pico, abs=1e-4), nombre
		assert float(np.sqrt(np.mean(np.square(datos)))) > 0.005, f"{nombre} es casi silencio"
		assert abs(float(np.mean(datos))) < 0.01, f"{nombre} tiene componente continua"


def test_los_ambientes_suenan_mas_bajo_que_los_avisos(todos):
	for nombre, datos in todos.items():
		if nombre.startswith("ambiente/"):
			assert float(np.max(np.abs(datos))) <= 0.35, nombre


def test_los_posicionables_son_mono_y_tienen_agudos(todos):
	pocos = {}
	for nombre, datos in todos.items():
		if not sintesis.CATALOGO[nombre].posicionable:
			continue
		assert datos.ndim == 1, f"{nombre} se sitúa en el espacio y no es mono"
		fraccion = sintesis.fraccion_agudos(datos)
		if fraccion < MINIMO_AGUDOS:
			pocos[nombre] = round(fraccion, 4)
	assert not pocos, f"Sin agudos por encima de 3 kHz no se distinguen delante y detrás: {pocos}"


def test_solo_los_fondos_son_estereo(todos):
	for nombre, datos in todos.items():
		if datos.ndim == 2:
			assert datos.shape[1] == 2, nombre
			assert sintesis.CATALOGO[nombre].bucle and not sintesis.CATALOGO[nombre].posicionable, nombre


def test_los_bucles_no_tienen_salto_en_la_costura(todos):
	bucles = [nombre for nombre, definicion in sintesis.CATALOGO.items() if definicion.bucle]
	assert bucles
	for nombre in bucles:
		datos = todos[nombre]
		assert len(datos) >= sintesis.FRECUENCIA // 2, f"{nombre} es demasiado corto para un bucle"
		# El paso del final al principio no debe ser mayor que los pasos normales entre muestras vecinas.
		salto = float(np.max(np.abs(datos[0] - datos[-1])))
		normal = float(np.percentile(np.abs(np.diff(datos, axis=0)), 99.9))
		assert salto <= max(2.0 * normal, 1e-3), f"{nombre}: salto de {salto:.4f} en la costura (lo normal es {normal:.4f})"


def test_los_que_no_son_bucle_empiezan_y_acaban_en_silencio(todos):
	for nombre, datos in todos.items():
		if not sintesis.CATALOGO[nombre].bucle:
			assert abs(float(datos[0])) < 0.01 and abs(float(datos[-1])) < 0.01, nombre


def test_sonido_reserva():
	neutro = sintesis.sonido_reserva("complemento/sonido_que_no_existe")
	assert neutro.ndim == 1 and neutro.dtype == np.float32
	assert 0.03 < len(neutro) / sintesis.FRECUENCIA < 0.5
	assert 0.1 < float(np.max(np.abs(neutro))) <= 0.8
	assert sintesis.fraccion_agudos(neutro) >= MINIMO_AGUDOS
	# De una familia conocida suena algo de esa familia; un paso conserva su suelo y su pie.
	assert np.array_equal(sintesis.sonido_reserva("pasos/metal_der_7"), sintesis.generar("pasos/metal_der_1"))
	assert np.array_equal(sintesis.sonido_reserva("pasos/lava_izq_1"), sintesis.generar("pasos/acera_izq_1"))
	assert np.array_equal(sintesis.sonido_reserva("golpe/goma"), sintesis.generar("golpe/madera"))
	assert np.array_equal(sintesis.sonido_reserva("baliza/pulso"), sintesis.generar("baliza/pulso"))
	assert not np.array_equal(neutro[:100], sintesis.generar("interfaz/mover")[:100])


@pytest.mark.parametrize("extension", [".flac", ".wav", ".ogg"])
def test_escribir_y_leer_ida_y_vuelta(tmp_path, extension):
	original = sintesis.generar("baliza/pulso")
	ruta = tmp_path / "sub" / f"prueba{extension}"
	sintesis.escribir_audio(ruta, original)
	assert ruta.is_file() and not list(ruta.parent.glob("*.tmp"))
	leido, frecuencia = sintesis.leer_audio(ruta)
	assert frecuencia == sintesis.FRECUENCIA
	assert leido.dtype == np.float32 and leido.shape == original.shape
	if extension == ".ogg":  # con pérdida: basta con que se parezca
		assert float(np.max(np.abs(leido))) == pytest.approx(float(np.max(np.abs(original))), abs=0.15)
	else:
		assert np.max(np.abs(leido - original)) < 1.0 / 16000.0


def test_leer_estereo_y_pasarlo_a_mono(tmp_path):
	t = np.arange(4410) / sintesis.FRECUENCIA
	estereo = np.stack([0.5 * np.sin(2 * np.pi * 440 * t), 0.4 * np.sin(2 * np.pi * 440 * t)], axis=1).astype(np.float32)
	ruta = tmp_path / "estereo.flac"
	sintesis.escribir_audio(ruta, estereo, 22050)
	leido, frecuencia = sintesis.leer_audio(ruta)
	assert frecuencia == 22050 and leido.shape == (4410, 2)
	mono, _frecuencia = sintesis.leer_audio(ruta, mono=True)
	assert mono.shape == (4410,)
	assert float(np.max(np.abs(mono))) == pytest.approx(0.45, abs=0.01)


def test_leer_y_escribir_fallan_con_mensaje_claro(tmp_path):
	with pytest.raises(OSError, match="No existe"):
		sintesis.leer_audio(tmp_path / "nada.flac")
	roto = tmp_path / "roto.flac"
	roto.write_bytes(b"esto no es audio")
	with pytest.raises(ValueError, match="No se pudo leer"):
		sintesis.leer_audio(roto)
	with pytest.raises(ValueError, match="no admitido"):
		sintesis.escribir_audio(tmp_path / "sonido.mp3", np.zeros(100, np.float32))


def test_remuestrear_conserva_duracion_y_tono():
	t = np.arange(22050) / 22050
	tono = np.sin(2 * np.pi * 1000 * t).astype(np.float32)
	subido = sintesis.remuestrear(tono, 22050, 44100)
	assert len(subido) == 44100 and subido.dtype == np.float32
	espectro = np.abs(np.fft.rfft(subido))
	assert int(np.argmax(espectro)) == pytest.approx(1000, abs=2)
	assert sintesis.remuestrear(tono, 44100, 44100) is tono or np.array_equal(sintesis.remuestrear(tono, 44100, 44100), tono)
	estereo = np.stack([tono, tono], axis=1)
	assert sintesis.remuestrear(estereo, 22050, 44100).shape == (44100, 2)
	# Un sonido largo va por tramos y debe dar la misma duración.
	largo = np.tile(tono, 12)
	assert len(sintesis.remuestrear(largo, 22050, 44100)) == len(largo) * 2
	with pytest.raises(ValueError):
		sintesis.remuestrear(tono, 0, 44100)


def test_apagar_quita_agudos_y_deja_graves():
	ruido = np.random.default_rng(1).standard_normal(8192).astype(np.float32)
	apagado = sintesis.apagar(ruido)
	assert apagado.shape == ruido.shape and apagado.dtype == np.float32
	assert sintesis.fraccion_agudos(apagado) < 0.2 * sintesis.fraccion_agudos(ruido)
	t = np.arange(8192) / sintesis.FRECUENCIA
	grave = np.sin(2 * np.pi * 100 * t).astype(np.float32)
	assert float(np.sqrt(np.mean(sintesis.apagar(grave) ** 2))) > 0.9 * float(np.sqrt(np.mean(grave**2)))
	assert sintesis.apagar(np.zeros((8192, 2), np.float32)).shape == (8192, 2)


def test_el_catalogo_va_fuera_de_la_carpeta_del_paquete(tmp_path):
	"""El catálogo se escribe en la carpeta de sonidos y mide los ficheros del paquete por defecto."""
	paquete = tmp_path / "por_defecto"
	sintesis.escribir_todos(paquete, "wav", solo="interfaz/mover")
	ruta = sintesis.escribir_catalogo(tmp_path, "flac", carpeta_sonidos=paquete)
	assert ruta == tmp_path / "catalogo.json"
	datos = json.loads(ruta.read_text(encoding="utf-8"))
	assert datos["sonidos"]["interfaz/mover"]["fichero"] == "interfaz/mover.wav"  # el que hay escrito
	assert datos["sonidos"]["baliza/pulso"]["fichero"] == "baliza/pulso.flac"  # el que se escribiría
	assert list(datos["sonidos"]) == sintesis.nombres()


def test_escribir_todos_con_patron_y_catalogo(tmp_path):
	escritos = sintesis.escribir_todos(tmp_path, "flac", solo="interfaz/*")
	assert sorted(ruta.relative_to(tmp_path).as_posix() for ruta in escritos) == sorted(
		f"{nombre}.flac" for nombre in sintesis.nombres() if nombre.startswith("interfaz/")
	)
	assert sintesis.fichero_de(tmp_path, "interfaz/mover") == tmp_path / "interfaz" / "mover.flac"
	assert sintesis.fichero_de(tmp_path, "baliza/pulso") is None
	with pytest.raises(ValueError):
		sintesis.escribir_todos(tmp_path, "mp3")


def test_datos_del_catalogo(todos):
	datos = sintesis.datos_catalogo()
	assert datos["formato"] == sintesis.FORMATO_CATALOGO
	assert [grupo["id"] for grupo in datos["grupos"]] == [identificador for identificador, _nombre in sintesis.GRUPOS]
	assert list(datos["sonidos"]) == sintesis.nombres()
	for nombre, ficha in datos["sonidos"].items():
		assert set(ficha) == {"nombre", "explicacion", "grupo", "bucle", "posicionable", "fichero", "duracion"}
		assert ficha["fichero"] == f"{nombre}.flac"
		assert ficha["duracion"] == pytest.approx(len(todos[nombre]) / sintesis.FRECUENCIA, abs=0.002)
	json.dumps(datos)  # todo es serializable


def test_el_catalogo_distribuido_corresponde_al_codigo():
	"""``data/sounds`` del repositorio (no el ``data`` temporal de las pruebas) está al día con la síntesis.

	El catálogo es común a todos los paquetes de sonidos; los ficheros que describe son los del paquete por defecto.
	"""
	ruta = paths.ruta_base() / "data" / "sounds" / "catalogo.json"
	carpeta = ruta.parent / "por_defecto"
	if not ruta.is_file():
		pytest.skip("No se han generado los sonidos: ejecute tools/sintetizar_sonidos.py")
	datos = json.loads(ruta.read_text(encoding="utf-8"))
	assert datos["formato"] == sintesis.FORMATO_CATALOGO
	assert [(grupo["id"], grupo["nombre"]) for grupo in datos["grupos"]] == sintesis.GRUPOS
	assert list(datos["sonidos"]) == sintesis.nombres(), "El catálogo distribuido no tiene los mismos sonidos que el código"
	for nombre, ficha in datos["sonidos"].items():
		definicion = sintesis.CATALOGO[nombre]
		assert ficha["nombre"] == definicion.nombre_origen(), nombre
		assert ficha["explicacion"] == definicion.explicacion_origen(), nombre
		assert (ficha["grupo"], ficha["bucle"], ficha["posicionable"]) == (definicion.grupo, definicion.bucle, definicion.posicionable)
		assert (carpeta / ficha["fichero"]).is_file(), f"Falta el fichero de {nombre}"
	# Una muestra: lo escrito en disco es lo que sintetiza el código de ahora.
	for nombre in ("baliza/pulso", "pasos/baldosa_izq_1", "fuente/reloj"):
		leido, frecuencia = sintesis.leer_audio(carpeta / datos["sonidos"][nombre]["fichero"])
		assert frecuencia == sintesis.FRECUENCIA
		if datos["sonidos"][nombre]["fichero"].endswith(".flac"):
			assert np.max(np.abs(leido - sintesis.generar(nombre))) < 1.0 / 16000.0, f"{nombre} está desfasado: regenere los sonidos"
