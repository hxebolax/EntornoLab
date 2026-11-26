"""Pruebas de la búsqueda de salas por UDP y de la dirección escrita a mano."""

from __future__ import annotations

import json
import socket
import time

import pytest

from app.supervision.descubrimiento import Anunciador, analizar_direccion, buscar_salas, direcciones_locales
from app.supervision.sala import Sala


@pytest.fixture
def anunciador():
	creado = Anunciador("Aula 3", 47900, tls=True, huella="ab" * 32, puerto=0, host="127.0.0.1")
	assert creado.iniciar()
	yield creado
	creado.detener()


def test_buscar_encuentra_la_sala_anunciada(anunciador):
	salas = buscar_salas(1.0, puerto=anunciador.puerto, destinos=["127.0.0.1"])
	assert len(salas) == 1
	sala = salas[0]
	assert (sala.nombre, sala.host, sala.puerto, sala.tls, sala.huella) == ("Aula 3", "127.0.0.1", 47900, True, "ab" * 32)


def test_buscar_sin_salas_devuelve_lista_vacia_y_no_tarda_mas_de_lo_pedido():
	libre = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	libre.bind(("127.0.0.1", 0))
	puerto = libre.getsockname()[1]
	libre.close()
	inicio = time.perf_counter()
	assert buscar_salas(0.3, puerto=puerto, destinos=["127.0.0.1"]) == []
	assert time.perf_counter() - inicio < 1.5


def test_el_anunciador_ignora_lo_que_no_es_una_busqueda(anunciador):
	enchufe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	enchufe.settimeout(0.3)
	try:
		for basura in (
			b"hola",
			b"\xff\xfe",
			b"x" * 5000,
			json.dumps({"v": 1, "app": "OtraCosa", "tipo": "buscar"}).encode(),
			json.dumps({"v": 99, "app": "EntornoLab", "tipo": "buscar"}).encode(),
			json.dumps({"v": 1, "app": "EntornoLab", "tipo": "sala", "nombre": "falsa"}).encode(),
			json.dumps([1, 2]).encode(),
		):
			try:
				enchufe.sendto(basura, ("127.0.0.1", anunciador.puerto))
			except OSError:
				continue  # el datagrama enorme puede no caber: tampoco debe responderse
		with pytest.raises((TimeoutError, OSError)):
			enchufe.recvfrom(2048)
		# Y sigue vivo: una búsqueda de verdad obtiene respuesta.
		enchufe.sendto(json.dumps({"v": 1, "app": "EntornoLab", "tipo": "buscar"}).encode(), ("127.0.0.1", anunciador.puerto))
		enchufe.settimeout(2.0)
		datos, _origen = enchufe.recvfrom(2048)
		respuesta = json.loads(datos)
		assert respuesta["tipo"] == "sala"
		assert "codigo" not in respuesta
	finally:
		enchufe.close()


def test_el_anunciador_limita_las_respuestas_por_direccion(anunciador):
	enchufe = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	enchufe.settimeout(0.3)
	pregunta = json.dumps({"v": 1, "app": "EntornoLab", "tipo": "buscar"}).encode()
	try:
		for _vuelta in range(30):
			enchufe.sendto(pregunta, ("127.0.0.1", anunciador.puerto))
		respuestas = 0
		try:
			while True:
				enchufe.recvfrom(2048)
				respuestas += 1
		except TimeoutError:
			pass
		assert 1 <= respuestas <= 5
	finally:
		enchufe.close()


def test_buscar_descarta_respuestas_falsas():
	"""Un programa que responde con datos absurdos no cuela una sala en la lista."""
	falso = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	falso.bind(("127.0.0.1", 0))
	falso.settimeout(2.0)
	puerto = falso.getsockname()[1]
	import threading

	def responder() -> None:
		_datos, origen = falso.recvfrom(2048)
		for respuesta in (
			b"basura",
			json.dumps({"v": 1, "app": "EntornoLab", "tipo": "sala", "nombre": "Mala", "puerto": 99999}).encode(),
			json.dumps({"v": 1, "app": "EntornoLab", "tipo": "sala", "nombre": "Mala", "puerto": "47900"}).encode(),
			json.dumps({"v": 1, "app": "Otro", "tipo": "sala", "nombre": "Mala", "puerto": 47900}).encode(),
			json.dumps({"v": 1, "app": "EntornoLab", "tipo": "sala", "nombre": ["x"], "puerto": 47955, "huella": 7}).encode(),
		):
			falso.sendto(respuesta, origen)

	hilo = threading.Thread(target=responder, daemon=True)
	hilo.start()
	salas = buscar_salas(0.6, puerto=puerto, destinos=["127.0.0.1"])
	hilo.join(timeout=3)
	falso.close()
	assert [(s.nombre, s.puerto, s.huella) for s in salas] == [("", 47955, "")]


def test_detener_dos_veces_y_puerto_ocupado(anunciador):
	otro = Anunciador("Otra", 47900, tls=True, puerto=anunciador.puerto, host="127.0.0.1")
	# En Windows SO_REUSEADDR permite compartir el puerto UDP; en cualquier caso no debe lanzar.
	assert otro.iniciar() in (True, False)
	otro.detener()
	otro.detener()


def test_la_sala_en_red_se_anuncia_y_sin_red_no(tmp_path):
	libre = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
	libre.bind(("127.0.0.1", 0))
	puerto_udp = libre.getsockname()[1]
	libre.close()
	sala = Sala(nombre="Gimnasio", carpeta_config=tmp_path)
	sala.iniciar(0, "123456", red=True, host="127.0.0.1", puerto_descubrimiento=puerto_udp)
	try:
		salas = buscar_salas(1.0, puerto=puerto_udp, destinos=["127.0.0.1"])
		assert [(s.nombre, s.puerto, s.tls, s.huella) for s in salas] == [("Gimnasio", sala.puerto, True, sala.huella)]
	finally:
		sala.detener()
	assert buscar_salas(0.3, puerto=puerto_udp, destinos=["127.0.0.1"]) == []
	local = Sala(nombre="Solo aquí")
	local.iniciar(0, "123456", puerto_descubrimiento=puerto_udp)
	try:
		assert buscar_salas(0.3, puerto=puerto_udp, destinos=["127.0.0.1"]) == []
	finally:
		local.detener()


@pytest.mark.parametrize(
	("texto", "esperado"),
	[
		("192.168.1.20", ("192.168.1.20", 47900)),
		("  192.168.1.20:5000 ", ("192.168.1.20", 5000)),
		("equipo-profe", ("equipo-profe", 47900)),
		("equipo-profe:47901", ("equipo-profe", 47901)),
		("[::1]:47900", ("::1", 47900)),
		("[fe80::1]", ("fe80::1", 47900)),
		("fe80::1", ("fe80::1", 47900)),
	],
)
def test_analizar_direccion_valida(texto, esperado):
	assert analizar_direccion(texto) == esperado


@pytest.mark.parametrize(
	"texto",
	["", "   ", "192.168.1.20:", "192.168.1.20:abc", "192.168.1.20:0", "192.168.1.20:70000", ":47900", "[::1", "[::1]x", "dos palabras"],
)
def test_analizar_direccion_no_valida(texto):
	with pytest.raises(ValueError):
		analizar_direccion(texto)


def test_direcciones_locales_no_incluye_la_de_bucle():
	direcciones = direcciones_locales()
	assert isinstance(direcciones, list)
	assert all(not direccion.startswith("127.") for direccion in direcciones)
