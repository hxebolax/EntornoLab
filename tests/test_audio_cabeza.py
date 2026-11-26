"""Pruebas del seguimiento de cabeza (OpenTrack por UDP)."""

from __future__ import annotations

import socket
import struct
import time

import pytest

from app.audio import cabeza as modulo
from app.audio.cabeza import Cabeza, leer_paquete


def test_leer_paquete() -> None:
	datos = struct.pack("<6d", 1.0, 2.0, 3.0, 30.0, -5.0, 0.5)
	assert leer_paquete(datos) == (1.0, 2.0, 3.0, 30.0, -5.0, 0.5)
	assert leer_paquete(b"corto") is None


def test_giro_centrado_e_invertido() -> None:
	c = Cabeza()
	assert c.giro() == 0.0 and not c.recibiendo
	c.poner(20.0, 4.0)
	assert c.recibiendo
	assert c.giro() == pytest.approx(20.0)
	assert c.cabeceo() == pytest.approx(4.0)
	c.centrar()
	assert c.giro() == pytest.approx(0.0)
	c.poner(50.0, 4.0)
	assert c.giro() == pytest.approx(30.0)
	assert c.cabeceo() == pytest.approx(0.0)
	inv = Cabeza(invertir=True)
	inv.poner(15.0)
	assert inv.giro() == pytest.approx(-15.0)


def test_normaliza_por_el_camino_corto() -> None:
	c = Cabeza()
	c.poner(170.0)
	c.centrar()
	c.poner(-170.0)
	assert c.giro() == pytest.approx(20.0)


def test_suavizado() -> None:
	c = Cabeza(suavizado=0.5)
	c.poner(0.0)
	c.poner(10.0)
	assert c.giro() == pytest.approx(5.0)
	c.poner(178.0)
	c.poner(178.0)
	c.suavizado = 0.0
	c.poner(178.0)
	c.suavizado = 0.5
	c.poner(-178.0)  # cruza por 180, no por 0: queda en 180
	assert abs(c.giro()) == pytest.approx(180.0)


def test_caduca(monkeypatch) -> None:
	c = Cabeza()
	c.poner(40.0)
	monkeypatch.setattr(modulo, "CADUCA", 0.0)
	assert c.giro() == 0.0
	c.centrar()
	monkeypatch.setattr(modulo, "CADUCA", 1.0)
	c.poner(10.0)
	assert c.giro() == pytest.approx(10.0)


def test_udp_real_en_localhost() -> None:
	c = Cabeza(puerto=0)
	assert c.iniciar()
	try:
		assert c.puerto != 0
		assert c.iniciar()  # ya iniciada: no abre otro
		with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
			limite = time.monotonic() + 3.0
			while not c.recibiendo and time.monotonic() < limite:
				s.sendto(b"basura", ("127.0.0.1", c.puerto))
				s.sendto(struct.pack("<6d", 0, 0, 0, -25.0, 7.0, 0), ("127.0.0.1", c.puerto))
				time.sleep(0.02)
		assert c.giro() == pytest.approx(-25.0)
		assert c.cabeceo() == pytest.approx(7.0)
	finally:
		c.parar()


def test_puerto_ocupado() -> None:
	a = Cabeza(puerto=0)
	assert a.iniciar()
	try:
		b = Cabeza(puerto=a.puerto)
		assert b.iniciar() is False
	finally:
		a.parar()
