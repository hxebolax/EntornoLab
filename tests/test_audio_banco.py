"""Banco de sonidos: orden de búsqueda, caché, nombres peligrosos, reserva y catálogo."""

from __future__ import annotations

import io
import random

import numpy as np
import pytest
import soundfile

from app.audio import banco as modulo
from app.audio import sintesis
from app.audio.banco import Banco, catalogo_sonidos, nombre_seguro
from app.audio.base import FRECUENCIA
from app.audio.motor_nulo import MotorNulo
from app.core import paths


def _tono(frecuencia: float, segundos: float = 0.1, nivel: float = 0.5) -> np.ndarray:
	t = np.arange(int(FRECUENCIA * segundos)) / FRECUENCIA
	return (np.sin(2 * np.pi * frecuencia * t) * nivel).astype(np.float32)


def _escribir(ruta, datos: np.ndarray, frecuencia: int = FRECUENCIA) -> None:
	ruta.parent.mkdir(parents=True, exist_ok=True)
	sintesis.escribir_audio(ruta, datos, frecuencia)


def _en_bytes(datos: np.ndarray, formato: str = "OGG") -> bytes:
	memoria = io.BytesIO()
	soundfile.write(memoria, datos, FRECUENCIA, format=formato)
	return memoria.getvalue()


@pytest.fixture
def carpetas(tmp_path):
	sonidos = tmp_path / "sounds"
	complementos = tmp_path / "plugins"
	# ``sounds`` contiene los paquetes; los sonidos de serie están en el paquete por defecto.
	_escribir(sonidos / "por_defecto" / "puerta" / "abrir.flac", _tono(440))
	_escribir(sonidos / "por_defecto" / "suelto.wav", _tono(550))
	_escribir(complementos / "cocina" / "sonidos" / "microondas.ogg", _tono(660, 0.3))
	return sonidos, complementos


def test_nombre_seguro():
	assert nombre_seguro("puerta/abrir") == "puerta/abrir"
	assert nombre_seguro("puerta\\abrir") == "puerta/abrir"
	assert nombre_seguro("../secreto") is None
	assert nombre_seguro("a/../../b") is None
	assert nombre_seguro("/etc/passwd") is None
	assert nombre_seguro("C:/Windows/media/tada.wav") is None
	assert nombre_seguro("") is None


def test_de_serie_y_cache(carpetas):
	sonidos, complementos = carpetas
	banco = Banco(carpetas_sonidos=[sonidos], carpetas_complementos=[complementos])
	encontrado = banco.sonido("puerta/abrir")
	assert encontrado.origen == "serie"
	assert encontrado.ruta == sonidos / "por_defecto" / "puerta" / "abrir.flac"
	assert encontrado.paquete == "por_defecto"
	assert encontrado.frecuencia == FRECUENCIA
	assert len(encontrado.datos) == int(FRECUENCIA * 0.1)
	assert banco.sonido("puerta/abrir") is encontrado  # caché
	assert banco.sonido("suelto").origen == "serie"
	assert banco.sonido("suelto.wav").origen == "serie"  # con extensión también
	datos, frecuencia = banco.datos("puerta/abrir")
	assert datos is encontrado.datos and frecuencia == FRECUENCIA


def test_complemento(carpetas):
	sonidos, complementos = carpetas
	banco = Banco(carpetas_sonidos=[sonidos], carpetas_complementos=[complementos])
	assert banco.origen("cocina/microondas") == "complemento"
	assert banco.origen("cocina/sonidos/microondas.ogg") == "complemento"
	assert banco.existe("cocina/microondas")
	assert not banco.existe("cocina/tostadora")


def test_el_entorno_manda_sobre_lo_de_serie(carpetas):
	sonidos, complementos = carpetas
	propios = {"sonidos/puerta/abrir.ogg": _en_bytes(_tono(880, 0.2)), "sonidos/timbre.wav": _en_bytes(_tono(990, 0.4), "WAV")}
	pedidos: list[str] = []

	def recurso(nombre: str) -> bytes:
		pedidos.append(nombre)
		return propios[nombre]  # KeyError si no está, como haría un paquete

	banco = Banco(recurso, carpetas_sonidos=[sonidos], carpetas_complementos=[complementos])
	propio = banco.sonido("puerta/abrir")
	assert propio.origen == "entorno"
	assert len(propio.datos) == pytest.approx(FRECUENCIA * 0.2, abs=64)
	assert banco.origen("sonidos/timbre.wav") == "entorno"
	assert banco.origen("timbre") == "entorno"
	assert banco.origen("suelto") == "serie"  # lo que el entorno no trae sigue saliendo de serie
	# Al cambiar de entorno, lo propio deja de valer.
	banco.poner_entorno(None)
	assert banco.origen("puerta/abrir") == "serie"
	assert all(nombre.startswith("sonidos/") for nombre in pedidos)


def test_un_paquete_que_falla_no_tumba_el_sonido(carpetas):
	sonidos, complementos = carpetas

	class ErrorDelPaquete(Exception):
		pass

	def recurso(nombre: str) -> bytes:
		if nombre.endswith(".ogg"):
			raise ErrorDelPaquete("formato no admitido")
		if nombre.endswith(".flac"):
			return b"esto no es un sonido"
		return b""

	banco = Banco(recurso, carpetas_sonidos=[sonidos], carpetas_complementos=[complementos])
	assert banco.origen("puerta/abrir") == "serie"


def test_reserva_y_sintetizado_cuando_falta_el_fichero(tmp_path, caplog):
	banco = Banco(carpetas_sonidos=[tmp_path / "vacia"], carpetas_complementos=[])
	with caplog.at_level("WARNING"):
		de_serie = banco.sonido("puerta/abrir")
		inventado = banco.sonido("no/existe/en/ningun/sitio")
		banco.sonido("no/existe/en/ningun/sitio")
	assert de_serie.origen == "sintetizado"
	assert np.array_equal(de_serie.datos, sintesis.generar("puerta/abrir"))
	assert inventado.origen == "reserva"
	assert len(inventado.datos) > 100 and np.abs(inventado.datos).max() > 0.01
	assert not banco.existe("no/existe/en/ningun/sitio")
	assert caplog.text.count("no/existe/en/ningun/sitio") == 1  # se avisa una sola vez


def test_nombre_peligroso_da_reserva_sin_leer_nada(tmp_path):
	secreto = tmp_path / "secreto.wav"
	_escribir(secreto, _tono(100))
	(tmp_path / "sounds").mkdir()
	banco = Banco(carpetas_sonidos=[tmp_path / "sounds"], carpetas_complementos=[tmp_path])
	assert banco.sonido("../secreto").origen == "reserva"
	assert banco.sonido(str(secreto)).origen == "reserva"
	assert not banco.existe("../secreto")


def test_nombre_generico_elige_una_variante(tmp_path):
	banco = Banco(carpetas_sonidos=[tmp_path], carpetas_complementos=[], azar=random.Random(4))
	variantes = {name for name in sintesis.nombres() if name.startswith("pasos/baldosa_")}
	assert len(variantes) >= 4
	oidos = set()
	for _i in range(40):
		paso = banco.sonido("pasos/baldosa")
		assert paso.origen == "sintetizado"
		oidos.add(paso.datos.tobytes())
	assert len(oidos) >= 3  # van cambiando
	izquierdos = {banco.sonido("pasos/baldosa_izq").datos.tobytes() for _i in range(30)}
	assert 2 <= len(izquierdos) <= 3


def test_sonido_larguisimo_se_recorta(tmp_path, monkeypatch):
	monkeypatch.setattr(modulo, "MUESTRAS_MAXIMAS", 1000)
	# Suelto en la carpeta de sonidos, como en las instalaciones anteriores a los paquetes: sigue valiendo.
	_escribir(tmp_path / "largo.wav", _tono(300, 0.5))
	banco = Banco(carpetas_sonidos=[tmp_path], carpetas_complementos=[])
	assert len(banco.sonido("largo").datos) == 1000


def test_los_sonidos_de_serie_del_programa_se_encuentran():
	"""Con ``data`` redirigida (las pruebas), los sonidos de serie siguen saliendo de la carpeta del programa."""
	if not (paths.ruta_base() / "data" / "sounds" / "catalogo.json").is_file():
		pytest.skip("los sonidos de serie no están generados (tools/sintetizar_sonidos.py)")
	banco = Banco()
	for nombre in ("baliza/pulso", "pasos/madera_izq_1", "puerta/abrir", "interfaz/mover", "ambiente/calle"):
		encontrado = banco.sonido(nombre)
		assert encontrado.origen == "serie", nombre
		assert encontrado.frecuencia == FRECUENCIA
	assert banco.sonido("ambiente/calle").datos.ndim == 2


def test_precargar_y_resolver_en_un_motor(carpetas):
	sonidos, complementos = carpetas
	banco = Banco(carpetas_sonidos=[sonidos], carpetas_complementos=[complementos])
	motor = MotorNulo()
	motor.iniciar(None, {})
	motor.resolver = banco.datos
	assert banco.precargar(motor, ["puerta/abrir", "cocina/microondas"]) == 2
	assert motor.duracion("cocina/microondas") == pytest.approx(0.3, abs=0.02)
	assert motor.reproducir("suelto") > 0  # sin precargar: lo trae el banco al pedirlo
	assert motor.duracion("suelto") == pytest.approx(0.1, abs=0.01)


def test_catalogo_sonidos():
	catalogo = catalogo_sonidos()
	assert catalogo["formato"] == 1
	grupos = [g["id"] for g in catalogo["grupos"]]
	assert grupos == [identificador for identificador, _nombre in sintesis.GRUPOS]
	assert set(catalogo["sonidos"]) == set(sintesis.nombres())
	for clave, ficha in catalogo["sonidos"].items():
		assert ficha["nombre"] and ficha["explicacion"], clave
		assert ficha["grupo"] in grupos, clave
		assert isinstance(ficha["bucle"], bool) and isinstance(ficha["posicionable"], bool)
