"""Pruebas de la grabadora de sesiones y de su incorporación a la base."""

from __future__ import annotations

import gzip
import json
import time
from types import SimpleNamespace

import pytest

from app.seguimiento import recompensas, sesiones
from app.seguimiento.alumnos import Fichas
from app.seguimiento.base import BaseSeguimiento, ErrorDatos
from app.seguimiento.grabadora import (
	Grabadora,
	borrar_ficheros_de_alias,
	caducar_ficheros,
	carpeta_sesiones,
	escribir_sesion,
	incorporar_sesiones,
	leer_sesion,
)
from tests._seguimiento_util import ESPACIOS, documento_sesion


class RelojFalso:
	"""Reloj monótono que solo avanza cuando la prueba lo dice."""

	def __init__(self) -> None:
		self.t = 100.0

	def __call__(self) -> float:
		return self.t


def _esperar(condicion, segundos: float = 5.0) -> bool:
	limite = time.monotonic() + segundos
	while time.monotonic() < limite:
		if condicion():
			return True
		time.sleep(0.01)
	return condicion()


def _grabar(tmp_path, **opciones):
	reloj = RelojFalso()
	grabadora = Grabadora(
		"Luna",
		"casa",
		"Casa de ejemplo",
		"buscar",
		"Buscar la llave",
		"busqueda",
		"practica",
		espacios=ESPACIOS,
		camino_optimo_m=4.0,
		carpeta=tmp_path / "sessions",
		reloj=reloj,
		**opciones,
	)
	return grabadora, reloj


def test_graba_a_cuatro_muestras_por_segundo(tmp_path):
	grabadora, _reloj = _grabar(tmp_path)
	guardadas = 0
	# El juego la llama 60 veces por segundo durante 2 segundos.
	for fotograma in range(121):
		t = fotograma / 60.0
		if grabadora.muestra(t, "p0", 1.0 + t, 1.0, 90.0):
			guardadas += 1
	assert guardadas == 9  # t = 0, 0.25, ..., 2.0
	ruta = grabadora.terminar(completada=True)
	traza = leer_sesion(ruta)["traza"]
	tiempos = [m[0] for m in traza["muestras"]]
	assert tiempos == pytest.approx([i * 0.25 for i in range(9)], abs=0.02)


def test_fichero_de_sesion_completo(tmp_path):
	grabadora, reloj = _grabar(tmp_path)
	for i in range(41):
		grabadora.muestra(i * 0.25, "p0", 1.0 + i * 0.2, 1.0, 90.0)
		if i == 8:
			grabadora.evento("choque", {"con": "mesa"})
		if i == 12:
			grabadora.registrar(SimpleNamespace(tipo="ayuda", datos={"ayuda": "donde_estoy"}))
		if i == 20:
			grabadora.pausar(True)
			assert grabadora.en_pausa
			assert not grabadora.muestra(99.0, "p0", 50.0, 50.0, 0.0)  # en pausa no se graba
			reloj.t += 30.0
			grabadora.pausar(False)
			grabadora.marca("Se orienta por el sonido de la nevera")
			grabadora.intervencion("mensaje", {"texto": "Texto que no debe guardarse", "canal": "profesional"})
		if i == 30:
			grabadora.evento("premio", {"id": "llave", "nombre": "Llave dorada"})
			grabadora.evento("recompensa", {"tipo": "estrella", "nombre": "Primera estrella"})
	grabadora.puntuaciones({"puntos": 2})
	ruta = grabadora.terminar(completada=True, resultado={"estrellas": 2})
	assert ruta == tmp_path / "sessions" / f"{grabadora.id}.json.gz"
	with gzip.open(ruta, "rb") as entrada:
		crudo = entrada.read().decode("utf-8")
	documento = json.loads(crudo)
	manifiesto = documento["manifiesto"]
	assert manifiesto["alias"] == "Luna"
	assert manifiesto["entorno"] == {"id": "casa", "nombre": "Casa de ejemplo"}
	assert manifiesto["actividad"]["tipo"] == "busqueda"
	assert manifiesto["modo"] == "practica"
	assert manifiesto["completada"] is True
	assert manifiesto["parcial"] is False
	assert manifiesto["frecuencia_hz"] == 4
	resumen = documento["resumen"]
	assert resumen["tiempo_activo_s"] == pytest.approx(10.0)
	assert resumen["tiempo_pausa_s"] == pytest.approx(30.0)
	assert resumen["pausas"]["lista"] == [[5.0, 30.0]]
	assert resumen["distancia_m"] == pytest.approx(8.0, abs=0.05)
	assert resumen["cociente_camino"] == pytest.approx(2.0, abs=0.02)
	assert resumen["choques"]["lugares"][0]["espacio"] == "sala"
	assert resumen["choques"]["lugares"][0]["x"] == pytest.approx(2.6)
	assert resumen["ayudas"]["por_tipo"] == {"donde_estoy": 1}
	assert resumen["premios"][0]["nombre"] == "Llave dorada"
	assert resumen["intervenciones"]["por_tipo"] == {"mensaje": 1}
	assert resumen["examen"] == {"puntos": 2}
	assert resumen["resultado"] == {"estrellas": 2}
	assert documento["traza"]["marcas"][0]["texto"] == "Se orienta por el sonido de la nevera"
	assert documento["traza"]["marcas"][0]["x"] == pytest.approx(5.0)
	assert "Texto que no debe guardarse" not in crudo
	# Terminar dos veces no cambia nada, y después ya no se graba.
	assert grabadora.terminar() == ruta
	assert not grabadora.muestra(200.0, "p0", 0, 0, 0)


def test_por_defecto_escribe_en_data_sessions(datos_temporales):
	grabadora = Grabadora("", autoguardado_s=0)
	grabadora.muestra(0.0, "p0", 0, 0, 0)
	ruta = grabadora.terminar()
	assert ruta.parent == carpeta_sesiones() == datos_temporales.resolve() / "sessions"
	assert leer_sesion(ruta)["manifiesto"]["alias"] == "invitado"


def test_guardado_parcial_automatico(tmp_path):
	grabadora, _reloj = _grabar(tmp_path, autoguardado_s=2.0)
	for i in range(13):
		grabadora.muestra(i * 0.25, "p0", 1.0 + i * 0.1, 1.0, 90.0)
	assert _esperar(grabadora.ruta.exists)
	parcial = leer_sesion(grabadora.ruta)
	assert parcial["manifiesto"]["parcial"] is True
	assert parcial["manifiesto"]["completada"] is False
	grabadora.terminar(completada=True)
	assert leer_sesion(grabadora.ruta)["manifiesto"]["parcial"] is False
	assert [r.name for r in grabadora.ruta.parent.iterdir()] == [grabadora.ruta.name]


def test_modo_o_identificador_no_validos(tmp_path):
	with pytest.raises(ErrorDatos):
		Grabadora("Luna", modo="trampa", carpeta=tmp_path)
	with pytest.raises(ErrorDatos):
		Grabadora("Luna", id_sesion="../fuera", carpeta=tmp_path)


def test_incorporar_es_idempotente(tmp_path):
	carpeta = tmp_path / "sessions"
	escribir_sesion(carpeta / f"{'1' * 32}.json.gz", documento_sesion("1" * 32, alias="Luna"))
	escribir_sesion(carpeta / f"{'2' * 32}.json.gz", documento_sesion("2" * 32, alias="luna"))
	escribir_sesion(carpeta / f"{'3' * 32}.json.gz", documento_sesion("3" * 32, alias="Sol"))
	(carpeta / "roto.json.gz").write_bytes(b"esto no es gzip")
	with gzip.open(carpeta / "sin_manifiesto.json.gz", "wb") as salida:
		salida.write(b'{"resumen": {}}')
	with BaseSeguimiento(tmp_path / "p.db") as base:
		Fichas(base).alta("Luna", nombre_real="Ana")
		primero = incorporar_sesiones(carpeta, base)
		assert (primero.nuevas, primero.repetidas, primero.alumnos_creados) == (3, 0, 1)
		assert sorted(nombre for nombre, _motivo in primero.erroneas) == ["roto.json.gz", "sin_manifiesto.json.gz"]
		segundo = incorporar_sesiones(carpeta, base)
		assert (segundo.nuevas, segundo.repetidas, segundo.alumnos_creados) == (0, 3, 0)
		luna = Fichas(base).por_alias("Luna")
		assert len(sesiones.listar(base, luna.id)) == 2
		assert base.valor("SELECT COUNT(*) FROM sesiones") == 3
		# Las recompensas del resumen se apuntan una sola vez.
		assert recompensas.coleccion(base, luna.id)["estrellas"] == 2
		assert incorporar_sesiones(tmp_path / "no_existe", base).nuevas == 0


def test_incorporar_sin_crear_alumnos_y_borrando_ficheros(tmp_path):
	carpeta = tmp_path / "sessions"
	escribir_sesion(carpeta / f"{'1' * 32}.json.gz", documento_sesion("1" * 32, alias="Luna"))
	escribir_sesion(carpeta / f"{'2' * 32}.json.gz", documento_sesion("2" * 32, alias="Desconocido"))
	with BaseSeguimiento(tmp_path / "p.db") as base:
		Fichas(base).alta("Luna")
		resultado = incorporar_sesiones(carpeta, base, crear_alumnos=False, borrar_incorporadas=True)
		assert (resultado.nuevas, resultado.sin_alumno, resultado.alumnos_creados) == (1, 1, 0)
		assert [ruta.name for ruta in carpeta.iterdir()] == [f"{'2' * 32}.json.gz"]
		assert Fichas(base).por_alias("Desconocido") is None


def test_sesion_grabada_de_verdad_llega_a_la_base(tmp_path):
	grabadora, _reloj = _grabar(tmp_path)
	for i in range(21):
		grabadora.muestra(i * 0.25, "p0", 1.0 + i * 0.2, 1.0, 90.0)
	grabadora.marca("nota de la marca")
	grabadora.terminar(completada=True)
	with BaseSeguimiento(tmp_path / "p.db") as base:
		assert incorporar_sesiones(tmp_path / "sessions", base).nuevas == 1
		guardada = sesiones.obtener(base, grabadora.id, con_traza=True)
		assert guardada["actividad_nombre"] == "Buscar la llave"
		assert guardada["modo"] == "practica"
		assert guardada["completada"]
		assert guardada["tiempo_activo"] == pytest.approx(5.0)
		assert len(guardada["traza"]["muestras"]) == 21
		assert guardada["marcas"][0]["texto"] == "nota de la marca"


def test_borrar_y_caducar_ficheros(tmp_path):
	carpeta = tmp_path / "sessions"
	escribir_sesion(carpeta / f"{'1' * 32}.json.gz", documento_sesion("1" * 32, alias="Luna"))
	escribir_sesion(carpeta / f"{'2' * 32}.json.gz", documento_sesion("2" * 32, alias="Sol"))
	assert borrar_ficheros_de_alias(carpeta, "LUNA") == 1
	assert caducar_ficheros(carpeta, 30) == 0
	assert caducar_ficheros(carpeta, 30, ahora=time.time() + 31 * 86400) == 1
	assert list(carpeta.iterdir()) == []
	with pytest.raises(ErrorDatos):
		caducar_ficheros(carpeta, 0)


def test_leer_un_fichero_desmesurado(tmp_path, monkeypatch):
	from app.seguimiento import grabadora as modulo

	ruta = tmp_path / "grande.json.gz"
	with gzip.open(ruta, "wb") as salida:
		salida.write(b'{"relleno": "' + b"x" * 5000 + b'"}')
	monkeypatch.setattr(modulo, "TAMANO_MAXIMO", 1000)
	with pytest.raises(ErrorDatos):
		leer_sesion(ruta)
