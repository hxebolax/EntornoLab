"""Un complemento instalado por el usuario que toma sonidos de «comun», que viaja con el programa.

Los complementos se buscan en varias carpetas (``carpetas_de_serie("plugins")``):
la de datos del usuario y la que está junto al programa. Un sonido citado como
``comun:campana.flac`` tiene que encontrarse aunque «comun» no esté en la carpeta
hermana del complemento que lo cita: el catálogo, el motor y el banco lo
resuelven con todas las carpetas cargadas.
"""

from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest

from app.audio import sintesis
from app.audio.banco import Banco
from app.audio.base import FRECUENCIA, carpetas_de_serie
from app.core import paths
from app.dominio import catalogo as cat
from app.dominio.catalogo import Catalogo, Complemento
from app.motor import movimiento
from app.reproductor import entornos
from tests.test_dominio_comun import FICHA_PRUEBA, _objeto, escribir_complemento


def _tono() -> np.ndarray:
	t = np.arange(int(FRECUENCIA * 0.1)) / FRECUENCIA
	return (np.sin(2 * np.pi * 440 * t) * 0.5).astype(np.float32)


@pytest.fixture
def instalacion(data_temporal: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> tuple[Path, Path]:
	"""«comun» junto al programa (carpeta de serie) y «casa», que depende de él, en la del usuario."""
	base = tmp_path / "programa"
	serie = base / "data" / "plugins"
	monkeypatch.setattr(paths, "ruta_base", lambda: base)
	comun = dict(FICHA_PRUEBA, id="comun", nombre="Común", objetos=[])
	escribir_complemento(serie, comun)
	sintesis.escribir_audio(serie / "comun" / "sonidos" / "campana.flac", _tono(), FRECUENCIA)
	usuario = data_temporal / "plugins"
	casa = dict(
		FICHA_PRUEBA,
		id="casa",
		nombre="Casa",
		depende_de=["comun"],
		objetos=[
			_objeto("reloj", "Reloj", "salon", [0.2, 0.3, 0.4], [0.1, 0.2, 0.3], [0.2, 0.3, 0.4], sonidos={"golpe": "comun:campana.flac"})
		],
	)
	escribir_complemento(usuario, casa)
	assert carpetas_de_serie("plugins") == [usuario, serie]
	return usuario, serie


def test_el_catalogo_resuelve_la_dependencia_en_otra_carpeta(instalacion):
	usuario, serie = instalacion
	catalogo = entornos.cargar_catalogo()
	assert not [a for a in catalogo.avisos if a.codigo == "dependencia_ausente"]
	casa = catalogo.complemento("casa")
	assert casa.carpeta == usuario / "casa"
	esperada = serie / "comun" / "sonidos" / "campana.flac"
	assert casa.ruta_recurso("comun:campana.flac") == esperada
	# También dándole el catálogo explícitamente, o a un complemento suelto que no lo conoce.
	suelto = Complemento(id="casa", carpeta=usuario / "casa", depende_de=["comun"])
	assert suelto.ruta_recurso("comun:campana.flac") is None  # sin catálogo solo mira la carpeta hermana
	assert suelto.ruta_recurso("comun:campana.flac", catalogo) == esperada
	# Lo que no está declarado o no existe sigue sin resolverse.
	assert casa.ruta_recurso("otro:campana.flac") is None
	assert casa.ruta_recurso("comun:no-esta.flac") is None


def test_la_carpeta_hermana_sigue_valiendo_sin_catalogo(tmp_path):
	raiz = tmp_path / "plugins"
	escribir_complemento(raiz, dict(FICHA_PRUEBA, id="comun", objetos=[]))
	sintesis.escribir_audio(raiz / "comun" / "sonidos" / "campana.flac", _tono(), FRECUENCIA)
	suelto = Complemento(id="casa", carpeta=raiz / "casa", depende_de=["comun"])
	assert suelto.ruta_recurso("comun:campana.flac") == raiz / "comun" / "sonidos" / "campana.flac"


def test_el_motor_y_el_banco_dan_el_fichero_de_comun(instalacion):
	usuario, serie = instalacion
	catalogo = Catalogo.cargar(carpetas_de_serie("plugins"))
	definicion = catalogo.objeto("casa/reloj")
	nombre = definicion.sonidos["golpe"]
	clave = movimiento.sonido_de_objeto(SimpleNamespace(definicion=definicion), nombre)
	assert clave == cat.clave_de_sonido("casa", nombre) == "comun/campana.flac"
	banco = Banco()  # con las carpetas de serie, como en el programa
	assert banco.carpetas_complementos == [usuario, serie]
	sonido = banco.sonido(clave)
	assert sonido.origen == "complemento"
	assert sonido.ruta == catalogo.complemento("casa").ruta_recurso(nombre) == serie / "comun" / "sonidos" / "campana.flac"
	assert len(sonido.datos) > 0
