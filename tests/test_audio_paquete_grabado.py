"""El paquete de sonidos «Grabado» (grabaciones reales de uso libre) y la herramienta que lo monta.

Nada suena: se miden los ficheros de ``data/sounds/grabado`` (esas pruebas se saltan si el paquete no
está montado) y la herramienta se prueba con «grabaciones» sintéticas escritas en carpetas
temporales, sin tocar los originales del autor.
"""

from __future__ import annotations

import json
import sys
import types

import numpy as np
import pytest

from app.audio import niveles, paquetes, sintesis
from app.audio.banco import NOMBRE_FICHA, PAQUETE_POR_DEFECTO, Banco, leer_ficha
from app.audio.base import FRECUENCIA
from app.audio.motor_nulo import MotorNulo
from app.audio.presentador import Presentador
from app.core import paths
from app.core.configuracion import Configuracion
from tools import montar_paquete_grabado as herramienta
from tools import receta_grabado

SONIDOS_DE_SERIE = paths.ruta_base() / "data" / "sounds"
GRABADO = SONIDOS_DE_SERIE / "grabado"
# Lo único que puede haber en la carpeta del paquete además de los sonidos.
TEXTOS = {NOMBRE_FICHA, "CREDITOS.txt", "receta.json", "medidas.json"}


def _ruido(segundos: float, frecuencia: int = FRECUENCIA, semilla: int = 1, nivel: float = 0.2) -> np.ndarray:
	"""Ruido blanco: una «grabación» con agudos de sobra."""
	return (np.random.default_rng(semilla).standard_normal(int(segundos * frecuencia)) * nivel).astype(np.float32)


def _tono(hercios: float, segundos: float, frecuencia: int = FRECUENCIA, nivel: float = 0.3) -> np.ndarray:
	t = np.arange(int(segundos * frecuencia)) / frecuencia
	return (np.sin(2 * np.pi * hercios * t) * nivel).astype(np.float32)


# ── La tabla ─────────────────────────────────────────────────────────────────


def test_la_receta_reparte_todo_el_catalogo_sin_solapes():
	"""Cada sonido del catálogo sale de una grabación, o se hereda por ser un código, o está pendiente con lo que hay que buscar."""
	grabados = set(receta_grabado.recetas())
	funcionales = set(receta_grabado.FUNCIONALES)
	pendientes = receta_grabado.pendientes()
	assert grabados | funcionales | set(pendientes) == set(sintesis.nombres())
	assert not grabados & funcionales and not grabados & set(pendientes) and not funcionales & set(pendientes)
	assert receta_grabado.FICHA["id"] == receta_grabado.ID == "grabado"
	for nombre, pendiente in pendientes.items():
		assert len(pendiente["motivo"]) > 10 and len(pendiente["buscar"]) > 30, nombre
		assert "mono" in pendiente["buscar"] or "estéreo" in pendiente["buscar"], f"{nombre}: falta decir si se busca mono o estéreo"
	assert "3 kHz" in receta_grabado.que_buscar("golpe/madera") and "bucle" in receta_grabado.que_buscar("fuente/reloj")


def test_la_receta_solo_usa_colecciones_con_licencia_admitida():
	for clave, coleccion in receta_grabado.COLECCIONES.items():
		assert coleccion["licencia"] in herramienta.LICENCIAS_ADMITIDAS, clave
		for campo in ("carpeta", "nombre", "autor", "origen", "constancia"):
			assert coleccion[campo], f"A la colección {clave} le falta «{campo}»"
		assert coleccion["origen"].startswith("https://"), clave
	for nombre, receta in receta_grabado.recetas().items():
		assert receta["coleccion"] in receta_grabado.COLECCIONES, nombre
		assert receta["fichero"] and ".." not in receta["fichero"], nombre
		coleccion = receta_grabado.COLECCIONES[receta["coleccion"]]
		assert coleccion.get("raiz", herramienta.RAIZ_ORIGINALES) in (herramienta.RAIZ_ORIGINALES, herramienta.RAIZ_DESCARGADAS), nombre
		if coleccion.get("raiz") == herramienta.RAIZ_DESCARGADAS:
			# Lo descargado para el paquete lleva el autor y la página de cada grabación, no solo los de la colección.
			autor, fichero = receta["fichero"].split("/", 1)
			assert receta["autor"] == autor and receta["titulo"], nombre
			assert receta["origen"] == f"https://freesound.org/people/{autor}/sounds/{fichero.split('_', 1)[0]}/", nombre
		definicion = sintesis.CATALOGO[nombre]
		if definicion.bucle:
			assert "duracion" not in receta, f"{nombre}: un bucle dura lo que el de serie"


def test_la_receta_no_sustituye_los_avisos_que_codifican_informacion():
	grabados = set(receta_grabado.recetas())
	for nombre in sintesis.nombres():
		if nombre.startswith(("baliza/", "sonda/", "brujula/", "ascensor/planta_", "pasos/tactil_")) or nombre in (
			"semaforo/verde",
			"semaforo/intermitente",
			"semaforo/rojo",
			"escalera/subir",
			"escalera/bajar",
		):
			assert nombre not in grabados and nombre in receta_grabado.FUNCIONALES, nombre


def test_la_receta_trae_los_suelos_enteros():
	"""Un suelo entra con sus seis pasos o no entra: mezclar pasos grabados y sintetizados en un mismo suelo despistaría."""
	grabados = set(receta_grabado.recetas())
	for suelo in sintesis.SUELOS:
		pasos = [f"pasos/{suelo}_{pie}_{variante}" for pie in sintesis.PIES for variante in range(1, sintesis.VARIANTES_PASO + 1)]
		cuantos = sum(nombre in grabados for nombre in pasos)
		assert cuantos in (0, len(pasos)), f"El suelo {suelo} tiene {cuantos} pasos grabados de {len(pasos)}"
		assert (cuantos > 0) == (suelo in receta_grabado.SUELOS_GRABADOS)


# ── El tratamiento ───────────────────────────────────────────────────────────


def test_tratar_recorta_pasa_a_mono_y_remuestrea():
	estereo = np.stack([_ruido(1.0, 48000, 1), _ruido(1.0, 48000, 2)], axis=1)
	estereo[: int(0.2 * 48000)] = 0.0  # la grabación empieza con dos décimas de silencio
	datos, hecho = herramienta.tratar(estereo, 48000, {"duracion": 0.3}, 1, False, 0.25)
	assert datos.ndim == 1 and datos.dtype == np.float32
	assert len(datos) == pytest.approx(0.3 * FRECUENCIA, abs=2)
	assert datos[0] == 0.0 and datos[-1] == 0.0  # fundidos: empieza y acaba en cero
	assert hecho["inicio"] == pytest.approx(0.2, abs=0.01)  # se salta el silencio hasta el ataque
	assert hecho["remuestreado_de"] == 48000 and hecho["canales_del_original"] == 2
	assert sintesis.fraccion_agudos(datos) > 0.5  # el remuestreo no se come los agudos
	# Sin buscar el ataque, el tramo empieza donde dice la receta.
	_datos, fijo = herramienta.tratar(estereo, 48000, {"duracion": 0.3, "inicio": 0.5, "ataque": False}, 1, False, 0.25)
	assert fijo["inicio"] == 0.5
	# Sin duración en la receta, la del sonido de serie.
	corto, _hecho = herramienta.tratar(_ruido(1.0), FRECUENCIA, {"ataque": False}, 1, False, 0.25)
	assert len(corto) == int(0.25 * FRECUENCIA)


def test_tratar_hace_bucles_sin_costura_y_de_la_duracion_exacta():
	ambiente = np.stack([_ruido(6.0, 48000, 3), _ruido(6.0, 48000, 4)], axis=1) + 0.05  # con componente continua
	bucle, hecho = herramienta.tratar(ambiente, 48000, {"inicio": 1.0, "cruce": 0.4}, 2, True, 3.0)
	assert bucle.shape == (3 * FRECUENCIA, 2)
	assert hecho["cruce"] == 0.4 and hecho["duracion"] == 3.0
	assert abs(float(bucle.mean())) < 0.005  # sin componente continua
	# El cruce a potencia constante no deja un bache de volumen al principio.
	principio = float(np.sqrt(np.mean(bucle[: int(0.4 * FRECUENCIA)] ** 2)))
	resto = float(np.sqrt(np.mean(bucle[int(0.4 * FRECUENCIA) :] ** 2)))
	assert principio == pytest.approx(resto, rel=0.1)
	# Un zumbido estable, cortado a destiempo, saltaría en la costura; con el cruce, no.
	zumbido = _tono(100.25, 6.0)
	sin_cruce = zumbido[FRECUENCIA : 4 * FRECUENCIA]
	con_cruce, _hecho = herramienta.tratar(zumbido, FRECUENCIA, {"inicio": 1.0, "cruce": 0.3}, 1, True, 3.0)
	assert niveles.costura(sin_cruce) > 3.0 and niveles.costura(con_cruce) < 2.0
	assert len(con_cruce) == 3 * FRECUENCIA


def test_tratar_dice_claro_lo_que_no_se_puede():
	with pytest.raises(herramienta.ErrorMontaje, match="mono"):
		herramienta.tratar(_ruido(12.0), FRECUENCIA, {}, 2, True, 10.0)  # un ambiente no se hace con una grabación mono
	with pytest.raises(herramienta.ErrorMontaje, match="bucle"):
		herramienta.tratar(_ruido(2.0), FRECUENCIA, {}, 1, True, 3.0)  # no da para la vuelta entera
	with pytest.raises(herramienta.ErrorMontaje, match="empieza"):
		herramienta.tratar(_ruido(1.0), FRECUENCIA, {"inicio": 5.0}, 1, False, 0.3)
	with pytest.raises(herramienta.ErrorMontaje, match="No se encuentra"):
		herramienta.buscar_fuentes(paths.ruta_base() / "no_existe")


def test_igualar_sube_una_grabacion_baja_sin_recortar():
	lejana = _ruido(1.0, nivel=0.002)  # un parque a lo lejos: pico de 0,01
	igualada, ganancia = herramienta.igualar(lejana, 0.1)
	assert ganancia > 20.0  # más de lo que sube el igualado de serie, que se queda en 10
	assert niveles.nivel(igualada) == pytest.approx(0.1, rel=0.05)
	assert niveles.pico(igualada) <= herramienta.TECHO_PICO + 1e-3
	# Un sonido muy picudo se queda en el techo aunque no llegue al nivel pedido.
	picudo = np.zeros(FRECUENCIA, dtype=np.float32)
	picudo[::4410] = 0.1
	assert niveles.pico(herramienta.igualar(picudo, 0.3)[0]) == pytest.approx(herramienta.TECHO_PICO, abs=1e-3)
	assert herramienta.igualar(np.zeros(100, np.float32), 0.3)[1] == 1.0  # el silencio no se toca


def test_la_separacion_distingue_suelos_distintos_y_delata_los_iguales():
	def suelo(nombre: str, grave: float, agudo: float) -> dict[str, np.ndarray]:
		pasos = {}
		for indice, (pie, variante) in enumerate((pie, variante) for pie in sintesis.PIES for variante in (1, 2, 3)):
			pasos[f"pasos/{nombre}_{pie}_{variante}"] = _tono(grave, 0.2, nivel=0.3) + _ruido(0.2, semilla=indice, nivel=agudo)
		return pasos

	distintos = {**suelo("madera", 120.0, 0.001), **suelo("grava", 120.0, 0.2)}
	medida = herramienta.separacion(distintos)
	assert medida["suelos"] == ["grava", "madera"]
	assert medida["pasos"]["entre_minima_db"] > 3 * medida["pasos"]["dentro_db"] and medida["pasos"]["margen"] > 3
	iguales = {**suelo("madera", 120.0, 0.05), **suelo("grava", 120.0, 0.05)}
	assert herramienta.separacion(iguales)["pasos"]["margen"] < 1.0
	# Un suelo al que le falta un paso no cuenta; y los golpes se comparan de dos en dos.
	del distintos["pasos/grava_der_3"]
	golpes = {"golpe/madera": _tono(200.0, 0.3), "golpe/cristal": _ruido(0.3)}
	incompleto = herramienta.separacion({**distintos, **golpes})
	assert incompleto["suelos"] == ["madera"] and "pasos" not in incompleto
	assert incompleto["golpe"]["par_mas_parecido"] == "cristal-madera" and incompleto["golpe"]["entre_minima_db"] > 5


# ── La herramienta entera, con originales de mentira ─────────────────────────


@pytest.fixture
def receta_de_prueba(tmp_path, monkeypatch):
	"""Una carpeta de «originales», una tabla pequeña y una carpeta de sonidos de destino."""
	fuentes = tmp_path / "originales"
	sintesis.escribir_audio(fuentes / "libres" / "golpe.wav", np.concatenate([np.zeros(4800, np.float32), _ruido(0.6, 48000)]), 48000)
	sintesis.escribir_audio(fuentes / "libres" / "zumbido.wav", _ruido(6.0, 48000, 7, nivel=0.01), 48000)
	sintesis.escribir_audio(fuentes / "libres" / "sin_agudos.wav", _tono(180.0, 1.0, 48000), 48000)
	sintesis.escribir_audio(fuentes / "libres" / "calle.wav", np.stack([_ruido(12.0, 48000, 8), _ruido(12.0, 48000, 9)], axis=1), 48000)
	modulo = types.ModuleType("receta_de_prueba")
	modulo.ID = "de_prueba"
	modulo.FICHA = {
		"id": "de_prueba",
		"nombre": "De prueba",
		"descripcion": "Para las pruebas",
		"autor": "Pruebas",
		"licencia": "CC0 1.0",
		"version": "1",
	}
	modulo.COLECCIONES = {
		"libres": {
			"carpeta": "libres",
			"nombre": "Sonidos libres de prueba",
			"autor": "Alguien",
			"licencia": "CC0 1.0",
			"origen": "https://example.org/libres",
			"constancia": "LICENSE.txt",
		}
	}
	tabla = {
		"golpe/madera": {"coleccion": "libres", "fichero": "golpe.wav", "duracion": 0.3},
		"fuente/frigorifico": {
			"coleccion": "libres",
			"fichero": "zumbido.wav",
			"inicio": 0.5,
			"titulo": "Zumbido",
			"autor": "Otra persona",
		},
		"golpe/metal": {"coleccion": "libres", "fichero": "sin_agudos.wav", "duracion": 0.7},
		"golpe/piedra": {"coleccion": "libres", "fichero": "no_esta.wav"},
		"ambiente/calle": {"coleccion": "libres", "fichero": "calle.wav", "inicio": 1.0, "nota": "Una nota"},
	}
	modulo.recetas = lambda: {nombre: dict(receta) for nombre, receta in tabla.items()}
	modulo.FUNCIONALES = {"baliza/pulso": "codifica el rumbo"}
	modulo.pendientes = lambda: {"golpe/tela": {"motivo": "no hay ninguna", "buscar": "un golpe blando; mono, de 0,2 s"}}
	modulo.que_buscar = receta_grabado.que_buscar
	monkeypatch.setitem(sys.modules, "receta_de_prueba", modulo)
	destino = tmp_path / "sounds"
	(destino / PAQUETE_POR_DEFECTO).mkdir(parents=True)
	return fuentes, destino, modulo


def test_la_herramienta_monta_el_paquete_sin_copiar_los_originales(receta_de_prueba):
	fuentes, destino, _modulo = receta_de_prueba
	assert herramienta.main(["--fuentes", str(fuentes), "--carpeta", str(destino), "--receta", "receta_de_prueba"]) == 0
	paquete = destino / "de_prueba"
	escritos = sorted(ruta.relative_to(paquete).as_posix() for ruta in paquete.rglob("*") if ruta.is_file())
	assert escritos == [
		"CREDITOS.txt",
		"ambiente/calle.flac",
		"fuente/frigorifico.flac",
		"golpe/madera.flac",
		"medidas.json",
		"pack.json",
		"receta.json",
	]
	# Lo escrito tiene la forma del sonido de serie: mono y recortado el golpe, bucle exacto el zumbido, estéreo el ambiente.
	golpe, frecuencia = sintesis.leer_audio(paquete / "golpe" / "madera.flac")
	assert frecuencia == FRECUENCIA and golpe.ndim == 1 and len(golpe) == pytest.approx(0.3 * FRECUENCIA, abs=2)
	assert niveles.pico(golpe) <= herramienta.TECHO_PICO + 1e-3 and abs(golpe[0]) < 0.01 and abs(golpe[-1]) < 0.01
	zumbido = sintesis.leer_audio(paquete / "fuente" / "frigorifico.flac")[0]
	assert len(zumbido) == len(sintesis.generar("fuente/frigorifico")) and niveles.costura(zumbido) < 2.0
	assert niveles.pico(zumbido) > 0.3  # venía con un pico de 0,04: se ha subido
	assert sintesis.leer_audio(paquete / "ambiente" / "calle.flac")[0].shape == (10 * FRECUENCIA, 2)
	# Ficha, créditos, receta y medidas dicen lo mismo.
	ficha = leer_ficha(paquete)
	assert ficha["sonidos"] == 3 and "golpe/metal" in ficha["heredados"] and "golpe/madera" not in ficha["heredados"]
	assert len(ficha["heredados"]) == len(sintesis.nombres()) - 3
	receta = json.loads((paquete / "receta.json").read_text(encoding="utf-8"))
	assert set(receta["sonidos"]) == {"golpe/madera", "fuente/frigorifico", "ambiente/calle"}
	apunte = receta["sonidos"]["golpe/madera"]
	assert (
		apunte["inicio"] == pytest.approx(0.1, abs=0.01)
		and apunte["duracion"] == pytest.approx(0.3, abs=0.001)
		and apunte["licencia"] == "CC0 1.0"
	)
	assert receta["sonidos"]["fuente/frigorifico"]["autor"] == "Otra persona" and receta["sonidos"]["fuente/frigorifico"]["cruce"] > 0
	assert receta["funcionales"] == {"baliza/pulso": "codifica el rumbo"}
	# Lo que no pasa las medidas o no está queda pendiente con su motivo y con lo que hay que buscar.
	assert "3 kHz" in receta["pendientes"]["golpe/metal"]["motivo"] and "3 kHz" in receta["pendientes"]["golpe/metal"]["buscar"]
	assert "no se encuentra el original" in receta["pendientes"]["golpe/piedra"]["motivo"]
	assert receta["pendientes"]["golpe/tela"]["buscar"].startswith("un golpe blando")
	medidas = json.loads((paquete / "medidas.json").read_text(encoding="utf-8"))
	assert medidas["sonidos"]["golpe/madera"]["en_el_paquete"] and not medidas["sonidos"]["golpe/metal"]["en_el_paquete"]
	assert "de_prueba" in medidas["separacion"]
	creditos = (paquete / "CREDITOS.txt").read_text(encoding="utf-8")
	assert (
		"  golpe/madera: golpe.wav, de la colección «Sonidos libres de prueba». Autor: Alguien. Licencia: CC0 1.0. Origen: https://example.org/libres."
		in creditos
	)
	assert "«Zumbido», de la colección" in creditos and "Nota: Una nota" in creditos and "creativecommons.org/publicdomain/zero" in creditos
	# El banco lo ve como un paquete parcial y hereda el resto.
	banco = Banco(carpetas_sonidos=[destino], carpetas_complementos=[], paquete="de_prueba")
	assert banco.sonido("golpe/madera").origen == "paquete" and banco.sonido("golpe/metal").origen == "sintetizado"


def test_la_herramienta_rehace_solo_lo_pedido_y_rechaza_licencias_no_admitidas(receta_de_prueba, caplog):
	fuentes, destino, modulo = receta_de_prueba
	orden = ["--fuentes", str(fuentes), "--carpeta", str(destino), "--receta", "receta_de_prueba"]
	assert herramienta.main(orden) == 0
	paquete = destino / "de_prueba"
	antes = (paquete / "ambiente" / "calle.flac").stat().st_mtime_ns
	assert herramienta.main([*orden, "--solo", "golpe/*"]) == 0
	assert (paquete / "ambiente" / "calle.flac").stat().st_mtime_ns == antes
	receta = json.loads((paquete / "receta.json").read_text(encoding="utf-8"))
	assert set(receta["sonidos"]) == {"golpe/madera", "fuente/frigorifico", "ambiente/calle"}  # se conserva lo ya apuntado
	assert herramienta.main([*orden, "--solo", "no/existe"]) == 1
	# Una grabación «solo para uso no comercial» no entra en un programa que cualquiera descarga.
	modulo.COLECCIONES["libres"]["licencia"] = "CC BY-NC 4.0"
	with caplog.at_level("ERROR"):
		assert herramienta.main(orden) == 1
	assert "no se admite" in caplog.text
	modulo.COLECCIONES["libres"]["licencia"] = "CC0 1.0"
	# Sin la carpeta de los originales lo dice claro y no toca el paquete.
	assert herramienta.main(["--fuentes", str(destino / "no_esta"), "--carpeta", str(destino), "--receta", "receta_de_prueba"]) == 1
	assert (paquete / "golpe" / "madera.flac").is_file()


def test_la_herramienta_lee_tambien_la_carpeta_de_lo_descargado(receta_de_prueba, tmp_path, monkeypatch):
	"""Las colecciones con ``"raiz": "descargadas"`` salen de la segunda carpeta (argumento o variable de entorno); si falta, se heredan con su motivo."""
	fuentes, destino, modulo = receta_de_prueba
	descargadas = tmp_path / "descargadas"
	sintesis.escribir_audio(
		descargadas / "freesound" / "alguien" / "1_golpe.wav", np.concatenate([np.zeros(2400, np.float32), _ruido(0.5, 48000, 5)]), 48000
	)
	modulo.COLECCIONES["bajadas"] = {
		"raiz": "descargadas",
		"carpeta": "freesound",
		"nombre": "Descargado para el paquete",
		"autor": "varios",
		"licencia": "CC0 1.0",
		"origen": "https://example.org/descargas",
		"constancia": "inventario.json",
	}
	tabla = modulo.recetas()
	tabla["golpe/ladrillo"] = {
		"coleccion": "bajadas",
		"fichero": "alguien/1_golpe.wav",
		"duracion": 0.3,
		"autor": "alguien",
		"origen": "https://example.org/1/",
	}
	monkeypatch.setattr(modulo, "recetas", lambda: {nombre: dict(receta) for nombre, receta in tabla.items()})
	base = ["--fuentes", str(fuentes), "--carpeta", str(destino), "--receta", "receta_de_prueba"]
	assert herramienta.main([*base, "--descargadas", str(descargadas)]) == 0
	paquete = destino / "de_prueba"
	assert (paquete / "golpe" / "ladrillo.flac").is_file()
	apunte = json.loads((paquete / "receta.json").read_text(encoding="utf-8"))["sonidos"]["golpe/ladrillo"]
	assert (
		apunte["autor"] == "alguien"
		and apunte["origen"] == "https://example.org/1/"
		and apunte["coleccion_nombre"] == "Descargado para el paquete"
	)
	# Con la variable de entorno también la encuentra.
	monkeypatch.setenv(herramienta.VARIABLE_DESCARGADAS, str(descargadas))
	assert herramienta.buscar_descargadas(None) == descargadas
	# Sin esa carpeta, lo que sale de ella se hereda y queda pendiente con su motivo; lo demás se monta igual.
	assert herramienta.main([*base, "--descargadas", str(tmp_path / "no_esta")]) == 0
	receta = json.loads((paquete / "receta.json").read_text(encoding="utf-8"))
	assert "golpe/ladrillo" not in receta["sonidos"] and "golpe/madera" in receta["sonidos"]
	assert "carpeta de lo descargado" in receta["pendientes"]["golpe/ladrillo"]["motivo"]
	assert not (paquete / "golpe" / "ladrillo.flac").exists()
	# Una colección que dice salir de una carpeta que no existe es un error de la receta.
	with pytest.raises(herramienta.ErrorMontaje, match="ninguna de las dos"):
		herramienta.carpeta_de_coleccion({"raiz": "otra", "carpeta": "x"}, fuentes, descargadas)


# ── El paquete que viaja con el programa ─────────────────────────────────────


@pytest.fixture(scope="module")
def grabado():
	"""Los sonidos del paquete Grabado tal como están en disco (sin igualar): nombre → muestras."""
	if not (GRABADO / NOMBRE_FICHA).is_file():
		pytest.skip("el paquete Grabado no está montado (tools/montar_paquete_grabado.py)")
	leidos = {}
	for nombre in sintesis.nombres():
		ruta = sintesis.fichero_de(GRABADO, nombre)
		if ruta is not None:
			datos, frecuencia = sintesis.leer_audio(ruta)
			assert frecuencia == FRECUENCIA, nombre
			leidos[nombre] = datos
	return leidos


def test_grabado_tiene_la_estructura_de_un_paquete(grabado):
	ficha = leer_ficha(GRABADO)
	for clave in ("id", "nombre", "descripcion", "autor", "licencia", "version", "generado"):
		assert ficha.get(clave), f"A la ficha le falta «{clave}»"
	assert ficha["id"] == "grabado" and ficha["igualar"] is True and "CC0" in ficha["licencia"]
	heredados = set(ficha["heredados"])
	assert set(grabado) | heredados == set(sintesis.nombres()) and not set(grabado) & heredados
	assert ficha["sonidos"] == len(grabado) >= 40
	# No choca con los otros paquetes y aparece en la lista como parcial.
	lista = {paquete["id"]: paquete for paquete in paquetes.listar(Banco(carpetas_sonidos=[SONIDOS_DE_SERIE], carpetas_complementos=[]))}
	assert lista["grabado"]["parcial"] and lista["grabado"]["sonidos"] == len(grabado)
	assert len({paquete["nombre"] for paquete in lista.values()}) == len(lista)
	# En la carpeta solo hay FLAC finales y los cuatro textos: los originales no viajan.
	for ruta in GRABADO.rglob("*"):
		if ruta.is_file():
			assert ruta.suffix == ".flac" or (ruta.parent == GRABADO and ruta.name in TEXTOS), f"{ruta} no debería estar en el paquete"
	assert {ruta.name for ruta in GRABADO.iterdir() if ruta.is_file()} == TEXTOS
	en_disco = {ruta.relative_to(GRABADO).with_suffix("").as_posix() for ruta in GRABADO.rglob("*.flac")}
	assert en_disco == set(grabado), "hay ficheros de sonido que no son del catálogo"


def test_grabado_cada_sonido_tiene_su_credito_con_licencia_admitida(grabado):
	creditos = (GRABADO / "CREDITOS.txt").read_text(encoding="utf-8")
	lineas = {linea.strip().split(": ", 1)[0]: linea for linea in creditos.splitlines() if linea.startswith("  ") and ": " in linea}
	receta = json.loads((GRABADO / "receta.json").read_text(encoding="utf-8"))
	assert set(receta["sonidos"]) == set(grabado)
	for nombre in grabado:
		apunte = receta["sonidos"][nombre]
		assert apunte["licencia"] in herramienta.LICENCIAS_ADMITIDAS, nombre
		assert apunte["origen"].startswith("https://") and apunte["autor"] and apunte["fichero"] and apunte["coleccion_nombre"], nombre
		assert apunte["duracion"] > 0 and apunte["inicio"] >= 0, nombre
		linea = lineas.get(nombre)
		assert linea, f"{nombre} no tiene su línea en CREDITOS.txt"
		assert linea == herramienta.linea_credito(nombre, apunte), nombre
		for dato in (apunte["fichero"], apunte["coleccion_nombre"], apunte["autor"], f"Licencia: {apunte['licencia']}", apunte["origen"]):
			assert dato in linea, f"{nombre}: falta «{dato}» en su crédito"
	# Las colecciones usadas, con su constancia; y el texto que explica la licencia.
	for coleccion in receta["colecciones"].values():
		assert coleccion["licencia"] in herramienta.LICENCIAS_ADMITIDAS
		assert f"«{coleccion['nombre']}»" in creditos and coleccion["origen"] in creditos and coleccion["constancia"] in creditos
	assert "creativecommons.org/publicdomain/zero/1.0" in creditos and "no viajan" in creditos
	for palabra in ("NonCommercial", "no comercial", "BY-NC", "NoDerivatives", "uso personal"):
		assert palabra not in creditos
	# Lo que se hereda está explicado: por ser un código o por faltar grabación, y qué habría que buscar.
	ficha = leer_ficha(GRABADO)
	assert set(receta["funcionales"]) | set(receta["pendientes"]) == set(ficha["heredados"])
	assert not set(receta["funcionales"]) & set(receta["pendientes"])
	for nombre, pendiente in receta["pendientes"].items():
		assert pendiente["motivo"] and pendiente["buscar"], nombre
		assert f"  {nombre}: " in creditos, f"{nombre} no está en la lista de pendientes de CREDITOS.txt"
	assert (paths.ruta_base() / "data" / "docs" / "licencias" / "sonidos-grabado.txt").is_file()


def test_grabado_tiene_la_misma_forma_que_el_de_serie(grabado):
	"""Canales, duración aproximada, picos prudentes, silencio en los bordes y bucles sin costura: las varas del paquete Natural."""
	defecto = SONIDOS_DE_SERIE / PAQUETE_POR_DEFECTO
	medidas = json.loads((GRABADO / "medidas.json").read_text(encoding="utf-8"))["sonidos"]
	for nombre, datos in grabado.items():
		definicion = sintesis.CATALOGO[nombre]
		de_serie, _frecuencia = sintesis.leer_audio(sintesis.fichero_de(defecto, nombre))
		assert datos.ndim == de_serie.ndim, f"{nombre}: canales distintos de los de serie"
		assert np.isfinite(datos).all() and len(datos) > 100, nombre
		proporcion = len(datos) / len(de_serie)
		assert 0.5 <= proporcion <= 1.75, f"{nombre} dura {proporcion:.2f} veces lo que el de serie"
		assert niveles.pico(datos) <= 0.8 + 1e-3, f"{nombre}: pico demasiado alto"
		assert float(np.sqrt(np.mean(np.square(datos)))) > 0.005, f"{nombre} es casi silencio"
		assert abs(float(np.mean(datos))) < 0.01, f"{nombre} tiene componente continua"
		if definicion.bucle:
			assert len(datos) == pytest.approx(len(de_serie), abs=0.01 * FRECUENCIA), f"{nombre}: el bucle no dura lo mismo"
			assert niveles.costura(datos) <= 2.0, f"{nombre}: salto en la costura del bucle"
		else:
			assert float(np.max(np.abs(datos[0]))) < 0.01 and float(np.max(np.abs(datos[-1]))) < 0.01, (
				f"{nombre} no empieza o no acaba en silencio"
			)
		assert medidas[nombre]["en_el_paquete"], nombre
	# Los pasos y los golpes, cortos: ninguno pasa de medio segundo (ni de 0,8 s el metal y el cristal, que resuenan).
	for nombre, datos in grabado.items():
		if nombre.startswith("pasos/"):
			assert len(datos) / FRECUENCIA <= 0.5, nombre
		if nombre.startswith("golpe/"):
			assert len(datos) / FRECUENCIA <= 0.8, nombre


def test_grabado_lo_que_se_situa_es_mono_y_tiene_agudos(grabado):
	pocos = {}
	for nombre, datos in grabado.items():
		if not sintesis.CATALOGO[nombre].posicionable:
			continue
		assert datos.ndim == 1, f"{nombre} se sitúa en el espacio y no es mono"
		fraccion = sintesis.fraccion_agudos(datos)
		if fraccion < herramienta.MINIMO_AGUDOS:
			pocos[nombre] = round(fraccion, 4)
	assert not pocos, f"Sin agudos por encima de 3 kHz no se distinguen delante y detrás: {pocos}"
	# Los ambientes, en estéreo.
	for nombre in (
		"ambiente/calle",
		"ambiente/parque",
		"ambiente/casa",
		"ambiente/oficina",
		"ambiente/pasillo",
		"ambiente/cocina",
		"trafico/ambiente_leve",
	):
		if nombre in grabado:
			assert grabado[nombre].ndim == 2 and grabado[nombre].shape[1] == 2, nombre


def test_grabado_esta_igualado_con_el_de_serie(grabado):
	"""Al cargarlo, el banco apenas corrige nada, y ningún sonido queda más de 6 dB por debajo del de serie."""
	banco = Banco(carpetas_sonidos=[SONIDOS_DE_SERIE], carpetas_complementos=[], paquete="grabado")
	referencias = niveles.leer_niveles(SONIDOS_DE_SERIE / PAQUETE_POR_DEFECTO)
	for nombre in grabado:
		encontrado = banco.sonido(nombre)
		assert (encontrado.origen, encontrado.paquete) == ("paquete", "grabado"), nombre
		assert 0.7 <= encontrado.ganancia <= 1.3, f"{nombre}: el igualado lo cambia {encontrado.ganancia:.2f} veces"
		assert herramienta.NIVEL_MINIMO * referencias[nombre][0] <= niveles.nivel(encontrado.datos) <= 1.05 * referencias[nombre][0], nombre


def test_grabado_hereda_lo_que_no_trae(grabado):
	"""Los avisos que codifican algo y lo que no tiene grabación suenan con el paquete por defecto, idénticos."""
	banco = Banco(carpetas_sonidos=[SONIDOS_DE_SERIE], carpetas_complementos=[], paquete="grabado")
	de_serie = Banco(carpetas_sonidos=[SONIDOS_DE_SERIE], carpetas_complementos=[])
	for nombre in sintesis.nombres():
		encontrado = banco.sonido(nombre)
		if nombre in grabado:
			assert encontrado.origen == "paquete", nombre
		else:
			assert (encontrado.origen, encontrado.paquete) == ("serie", PAQUETE_POR_DEFECTO), nombre
			assert np.array_equal(encontrado.datos, de_serie.sonido(nombre).datos), f"{nombre} no es el de serie"
	for nombre in (
		"baliza/pulso",
		"sonda/cerca",
		"brujula/norte",
		"ascensor/planta_7",
		"semaforo/verde",
		"escalera/subir",
		"pasos/tactil_botones_izq_1",
	):
		assert nombre not in grabado, f"{nombre} codifica información: no debe sustituirse por una grabación"
	# Un nombre genérico de un suelo grabado da siempre un paso del paquete; el de uno pendiente, uno de serie.
	if "pasos/arena_izq_1" in grabado:
		assert {banco.sonido("pasos/arena").origen for _i in range(12)} == {"paquete"}
	assert {banco.sonido("pasos/tactil_rayas").origen for _i in range(12)} == {"serie"}


def test_grabado_los_pasos_y_los_golpes_se_distinguen(grabado):
	"""Cada suelo grabado está entero y se separa de los demás más de lo que varían sus propios pasos; los golpes, más de 2 dB."""
	medida = herramienta.separacion(grabado)
	assert set(medida["suelos"]) == {suelo for suelo in sintesis.SUELOS if f"pasos/{suelo}_izq_1" in grabado}
	assert len(medida["suelos"]) >= 3
	assert medida["pasos"]["entre_minima_db"] > medida["pasos"]["dentro_db"], f"Los pasos se parecen demasiado: {medida['pasos']}"
	for familia in ("golpe", "roce"):
		if familia in medida:
			assert medida[familia]["entre_minima_db"] > 2.0, f"{familia}: {medida[familia]}"
	# Lo apuntado en medidas.json es lo que se mide ahora.
	apuntada = json.loads((GRABADO / "medidas.json").read_text(encoding="utf-8"))["separacion"]
	assert apuntada["grabado"] == medida
	assert {"por_defecto", "natural"} & set(apuntada), "falta la comparación con los otros paquetes"


def test_grabado_los_avisos_con_ritmo_lo_conservan(grabado):
	"""Lo poco que lleva un dibujo reconocible lo mantiene: un tic por segundo y dos campanadas por vuelta."""
	if "fuente/reloj" in grabado:
		assert niveles.golpes(grabado["fuente/reloj"], separacion=0.3, umbral=0.5) == 2  # dos segundos, dos golpes
	if "fuente/campanas" in grabado:
		assert niveles.golpes(grabado["fuente/campanas"], separacion=0.3, umbral=0.5) == 2
	if {"interfaz/borde", "interfaz/mover", "interfaz/ajuste"} <= set(grabado):
		# El borde es el toque grave y el ajuste el agudo, como dice el catálogo.
		assert (
			niveles.centroide(grabado["interfaz/borde"])
			< niveles.centroide(grabado["interfaz/mover"])
			< niveles.centroide(grabado["interfaz/ajuste"])
		)


def test_grabado_no_es_una_copia_de_los_otros_paquetes(grabado):
	for otro in (PAQUETE_POR_DEFECTO, "natural"):
		for nombre, datos in grabado.items():
			ruta = sintesis.fichero_de(SONIDOS_DE_SERIE / otro, nombre)
			if ruta is None:
				continue
			ajeno = sintesis.leer_audio(ruta)[0]
			assert datos.shape != ajeno.shape or not np.allclose(datos, ajeno, atol=1e-3), f"{nombre} es igual que el de {otro}"


# ── Cambio en caliente a este paquete ────────────────────────────────────────


def test_cambio_en_caliente_al_paquete_grabado(grabado, tmp_path):
	"""Elegirlo en la configuración recarga en el motor solo lo que el paquete trae, y los bucles siguen por su canal."""
	suyos = [nombre for nombre in ("fuente/frigorifico", "pasos/arena_izq_1", "golpe/madera") if nombre in grabado]
	heredados = ["baliza/pulso", "sonda/cerca", "brujula/norte"]
	assert suyos, "el paquete no trae ninguno de los sonidos de la prueba"
	config = Configuracion(tmp_path / "config.json")
	banco = Banco(carpetas_sonidos=[SONIDOS_DE_SERIE], carpetas_complementos=[])
	motor = MotorNulo()
	motor.iniciar(None, {})
	motor.resolver = banco.datos
	presentador = Presentador(motor, banco=banco)
	cancelar = paquetes.conectar(banco, config)
	try:
		assert banco.paquete_actual() == PAQUETE_POR_DEFECTO
		assert banco.precargar(motor, suyos + heredados) == len(suyos) + len(heredados)
		de_serie = {nombre: motor._sonidos[nombre].copy() for nombre in suyos + heredados}
		bucle = "fuente/frigorifico" if "fuente/frigorifico" in grabado else None
		canal = motor.reproducir(bucle, bus="ambiente", bucle=True, pos=(2.0, 3.0, 1.0)) if bucle else 0
		presentador.aplicar([], None, 0.05)
		motor.vaciar()

		assert paquetes.elegir("grabado", config, banco) is True
		assert config.obtener("sonido.paquete") == "grabado" and banco.paquete_actual() == "grabado"
		presentador.aplicar([], None, 0.05)  # la recarga se hace aquí, en el hilo del juego
		assert sorted(llamada["nombre"] for llamada in motor.de("cargar")) == sorted(suyos)
		for nombre in suyos:
			nuevo = motor._sonidos[nombre]
			assert nuevo.shape != de_serie[nombre].shape or not np.allclose(nuevo, de_serie[nombre], atol=1e-3), f"{nombre} no ha cambiado"
		for nombre in heredados:
			assert np.array_equal(motor._sonidos[nombre], de_serie[nombre]), f"{nombre} se hereda: no debía recargarse"
		if bucle:
			# El frigorífico pasa a la grabación con un fundido y el juego lo sigue manejando por el mismo número de canal.
			assert motor.suena(canal)
			del_bucle = [activo for activo in motor.canales_activos() if activo.nombre == bucle]
			assert len(del_bucle) == 2 and sum(activo.parando for activo in del_bucle) == 1
			for _i in range(12):
				presentador.aplicar([], None, 0.05)
			assert motor.suena(canal) and len([activo for activo in motor.canales_activos() if activo.nombre == bucle]) == 1
		assert banco.recargar_en(motor) == 0  # ya está al día

		# De vuelta al de por defecto, y de ahí al Natural si está: siempre lo mismo que se recarga.
		motor.vaciar()
		assert paquetes.elegir(PAQUETE_POR_DEFECTO, config, banco) is True
		presentador.aplicar([], None, 0.05)
		assert sorted(llamada["nombre"] for llamada in motor.de("cargar")) == sorted(suyos)
		for nombre in suyos:
			assert np.allclose(motor._sonidos[nombre], de_serie[nombre], atol=1e-4), nombre
		if bucle:
			motor.parar(canal)
		# Y guardado: otro arranque lo encuentra elegido.
		paquetes.elegir("grabado", config, banco)
		assert Configuracion(tmp_path / "config.json").obtener("sonido.paquete") == "grabado"
		assert [paquete["id"] for paquete in paquetes.listar(banco) if paquete["actual"]] == ["grabado"]
	finally:
		cancelar()
		presentador.cerrar()


def test_la_muestra_del_paquete_grabado_no_cambia_de_paquete(grabado):
	banco = Banco(carpetas_sonidos=[SONIDOS_DE_SERIE], carpetas_complementos=[])
	nombres = tuple(nombre for nombre in ("pasos/arena_izq_1", "golpe/madera", "puerta/abrir") if nombre in grabado)
	suya, frecuencia = paquetes.muestra("grabado", banco, nombres)
	de_serie, _frecuencia = paquetes.muestra(PAQUETE_POR_DEFECTO, banco, nombres)
	assert frecuencia == FRECUENCIA and len(suya) > FRECUENCIA // 4
	assert suya.shape != de_serie.shape or not np.allclose(suya, de_serie, atol=1e-3)
	assert banco.paquete_actual() == PAQUETE_POR_DEFECTO
