"""Sonidos citados como ``dueño:fichero`` (``comun:sentarse.flac``) en el reproductor real.

Un complemento puede usar los sonidos de otro del que depende (``depende_de``)
sin llevar copia. El motor los pide al banco como ``dueño/fichero`` y el banco
tiene que encontrarlos en la carpeta de ese complemento, no sintetizar uno de
reserva. Aquí se comprueba con el catálogo real de ``data/plugins`` (solo se lee).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.dominio import catalogo as cat
from app.dominio import colocacion
from app.dominio.formato import cargar_paquete, guardar_paquete
from app.reproductor import entornos

from .conftest import RAIZ
from .test_reproductor_comun import VIVIENDA, crear_app, instalar_actividades_dobles, puntos_para_premios, sin_navegador  # noqa: F401 - fixture

pytestmark = pytest.mark.lento

PLUGINS = RAIZ / "data" / "plugins"


def _sonidos_de(definicion: cat.DefObjeto) -> list[str]:
	"""Todos los sonidos que cita un objeto: los de su ficha y los de sus acciones."""
	nombres = cat._nombres_sonido(definicion.sonidos)
	nombres += [str(accion["sonido"]) for accion in definicion.acciones if isinstance(accion.get("sonido"), str)]
	return nombres


def _propio_de_comun(catalogo: cat.Catalogo) -> cat.DefObjeto:
	"""Un objeto con sonido propio, sin estado, que lo toma del complemento «comun»."""
	for definicion in catalogo.objetos():
		propio = definicion.sonidos.get("propio")
		if isinstance(propio, dict) and str(propio.get("sonido", "")).startswith("comun:") and not propio.get("estado"):
			return definicion
	pytest.skip("ningún objeto del catálogo real toma su sonido propio de «comun»")


@pytest.fixture
def app(data_temporal: Path, sin_navegador: list[str], monkeypatch: pytest.MonkeyPatch):  # noqa: F811 - fixture importada
	if not (PLUGINS / "comun" / "sonidos").is_dir():
		pytest.skip("no está el complemento «comun» en data/plugins")
	instalar_actividades_dobles(monkeypatch)
	aplicacion = crear_app("--alumno", "Luna")
	yield aplicacion
	aplicacion.cerrar_todo()


def test_el_banco_del_reproductor_encuentra_los_sonidos_de_otro_complemento(app):
	"""Cada sonido ``dueño:fichero`` del catálogo real sale de su complemento, no de la reserva."""
	catalogo = app.catalogo
	citados = 0
	for definicion in catalogo.objetos():
		for nombre in _sonidos_de(definicion):
			if cat.partes_de_sonido(nombre)[0]:
				clave = cat.clave_de_sonido(definicion.complemento, nombre)
				assert app.banco.origen(clave) == "complemento", (definicion.tipo, nombre, clave)
				citados += 1
	assert citados > 0, "el catálogo real ya no usa sonidos de otros complementos: revise la prueba"
	# Y lo que el banco entrega son muestras de verdad, leídas del fichero de «comun».
	definicion = _propio_de_comun(catalogo)
	clave = cat.clave_de_sonido(definicion.complemento, definicion.sonidos["propio"]["sonido"])
	sonido = app.banco.sonido(clave)
	assert sonido.origen == "complemento" and sonido.ruta is not None and sonido.ruta.parent.parent.name == "comun"
	assert len(sonido.datos) > 0


def test_en_partida_suena_el_sonido_propio_tomado_de_comun(app, data_temporal: Path):
	"""Un objeto con sonido propio de «comun» junto al alumno: el motor lo pide y el banco lo da del fichero."""
	catalogo = app.catalogo
	definicion = _propio_de_comun(catalogo)
	original = cargar_paquete(VIVIENDA)
	entorno = original.entorno
	planta = (
		next(p for p in entorno.plantas if p.id == entorno.inicio.planta) if getattr(entorno.inicio, "planta", "") else entorno.plantas[0]
	)
	x, y = float(entorno.inicio.x), float(entorno.inicio.y)
	colocado = None
	# Se busca un hueco cerca del punto de inicio, dentro del radio en que se oye.
	for dx, dy in ((1.0, 0.0), (-1.0, 0.0), (0.0, 1.0), (0.0, -1.0), (1.5, 1.5), (-1.5, -1.5), (0.0, 0.0)):
		resultado = colocacion.colocar_en_punto(entorno, planta, definicion.tipo, catalogo, x + dx, y + dy, forzar=True)
		if resultado.colocado:
			colocado = resultado.objeto
			break
	assert colocado is not None, "no se pudo colocar el objeto junto al inicio"
	puntos = puntos_para_premios(original, 1)
	actividad = {
		"formato": 1,
		"id": "busca",
		"nombre": "Busca",
		"tipo": "busqueda",
		"modo": "juego",
		"premios": [
			{"id": "p1", "nombre": "la moneda", "planta": puntos[0][0], "x": puntos[0][1], "y": puntos[0][2], "sonido": "premio/cerca"}
		],
	}
	carpeta = data_temporal / "entornos"
	carpeta.mkdir(parents=True, exist_ok=True)
	ruta = carpeta / "con-sonido-de-comun.elab"
	guardar_paquete(ruta, entorno, [actividad], dict(original.recursos))
	paquete = entornos.abrir(ruta)
	assert app.empezar_partida(paquete, paquete.actividad("busca"))
	clave = cat.clave_de_sonido(definicion.complemento, definicion.sonidos["propio"]["sonido"])
	assert clave.startswith("comun/")
	pedidos: list[str] = []
	for _fotograma in range(240):
		app.avanzar(1, 1.0 / 60.0)
		pedidos = [str(llamada.get("nombre")) for metodo in ("reproducir", "cargar") for llamada in app.motor.de(metodo)]
		if clave in pedidos:
			break
	assert clave in pedidos, f"el motor no pidió {clave}; pidió {sorted(set(pedidos))[:20]}"
	assert app.banco.origen(clave) == "complemento"
	assert app.fallos == 0
