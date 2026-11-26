"""Pruebas de la base del seguimiento: esquema, migraciones, transacciones y cifrado de campos."""

from __future__ import annotations

import sqlite3

import pytest

from app.seguimiento.alumnos import Fichas
from app.seguimiento.base import (
	MIGRACIONES,
	BaseSeguimiento,
	Cifrador,
	ErrorClave,
	ErrorMigracion,
	ErrorVersionFutura,
	Migracion,
	abrir_base,
	normalizar_busqueda,
	ruta_por_defecto,
)
from tests._seguimiento_util import cifrador_de_prueba


def test_crea_el_esquema_y_la_version(tmp_path):
	with BaseSeguimiento(tmp_path / "db" / "prueba.db") as base:
		assert base.version() == len(MIGRACIONES)
		tablas = {fila["name"] for fila in base.consultar("SELECT name FROM sqlite_master WHERE type = 'table'")}
		assert {"alumnos", "sesiones", "evaluaciones_reales", "recompensas", "marcas", "meta"} <= tablas
		assert base.valor("PRAGMA foreign_keys") == 1
		assert base.valor("PRAGMA secure_delete") == 1


def test_la_ruta_por_defecto_esta_en_data_db(datos_temporales):
	ruta = ruta_por_defecto()
	assert ruta.parent == datos_temporales.resolve() / "db"
	assert ruta.name == "entornolab.db"


def test_transaccion_deshace_todo_si_falla(tmp_path):
	with BaseSeguimiento(tmp_path / "p.db") as base:
		with pytest.raises(RuntimeError):
			with base.transaccion() as tx:
				tx.execute("INSERT INTO alumnos (alias, alias_busqueda, alta) VALUES ('Uno', 'uno', '2026')")
				raise RuntimeError("fallo a propósito")
		assert base.valor("SELECT COUNT(*) FROM alumnos") == 0


def test_transaccion_anidada_solo_deshace_lo_interior(tmp_path):
	with BaseSeguimiento(tmp_path / "p.db") as base:
		with base.transaccion() as tx:
			tx.execute("INSERT INTO alumnos (alias, alias_busqueda, alta) VALUES ('Uno', 'uno', '2026')")
			with pytest.raises(sqlite3.IntegrityError):
				with base.transaccion() as interior:
					interior.execute("INSERT INTO alumnos (alias, alias_busqueda, alta) VALUES ('Dos', 'dos', '2026')")
					interior.execute("INSERT INTO alumnos (alias, alias_busqueda, alta) VALUES ('uno', 'uno', '2026')")
		assert [fila["alias"] for fila in base.consultar("SELECT alias FROM alumnos")] == ["Uno"]


def test_el_esquema_rechaza_valores_fuera_de_lista(tmp_path):
	with BaseSeguimiento(tmp_path / "p.db") as base:
		with pytest.raises(sqlite3.IntegrityError):
			base.ejecutar("INSERT INTO alumnos (alias, alias_busqueda, alta, perfil) VALUES ('A', 'a', '2026', 'volador')")
		with pytest.raises(sqlite3.IntegrityError):
			base.ejecutar("INSERT INTO alumnos (alias, alias_busqueda, alta) VALUES ('  ', '', '2026')")


def test_migracion_nueva_hace_copia_y_sube_la_version(tmp_path):
	ruta = tmp_path / "p.db"
	with BaseSeguimiento(ruta) as base:
		Fichas(base).alta("Luna")
	ampliadas = (*MIGRACIONES, Migracion("Columna de prueba", sql="ALTER TABLE alumnos ADD COLUMN prueba TEXT"))
	with BaseSeguimiento(ruta, migraciones=ampliadas) as base:
		assert base.version() == len(MIGRACIONES) + 1
		assert len(base.copias()) == 1
		assert Fichas(base).por_alias("luna") is not None


def test_migracion_que_falla_deja_la_version_anterior(tmp_path):
	ruta = tmp_path / "p.db"
	BaseSeguimiento(ruta).cerrar()
	rotas = (*MIGRACIONES, Migracion("Rota", sql="ALTER TABLE no_existe ADD COLUMN x TEXT"))
	with pytest.raises(ErrorMigracion):
		BaseSeguimiento(ruta, migraciones=rotas)
	with BaseSeguimiento(ruta) as base:
		assert base.version() == len(MIGRACIONES)


def test_rechaza_una_base_de_version_futura(tmp_path):
	ruta = tmp_path / "p.db"
	with BaseSeguimiento(ruta) as base:
		base.ejecutar(f"PRAGMA user_version = {len(MIGRACIONES) + 5}")
	with pytest.raises(ErrorVersionFutura):
		BaseSeguimiento(ruta)


def test_los_campos_sensibles_no_estan_en_claro_en_el_fichero(tmp_path):
	ruta = tmp_path / "p.db"
	with BaseSeguimiento(ruta, cifrador=cifrador_de_prueba(b"clave-secreta")) as base:
		ficha = Fichas(base).alta("Luna", nombre_real="Nombre Verdadero Unico", notas="Nota muy privada")
		assert Fichas(base).obtener(ficha.id).nombre_real == "Nombre Verdadero Unico"
	contenido = ruta.read_bytes()
	assert b"Nombre Verdadero Unico" not in contenido
	assert b"Nota muy privada" not in contenido
	assert b"Luna" in contenido  # el alias no se cifra: es el identificador


def test_sin_cifrar_los_campos_se_leen_igual(tmp_path):
	with BaseSeguimiento(tmp_path / "p.db", cifrador=Cifrador.sin_cifrar()) as base:
		ficha = Fichas(base).alta("Luna", nombre_real="Ana")
		assert Fichas(base).obtener(ficha.id).nombre_real == "Ana"


def test_clave_equivocada_o_ausente_se_detecta_al_abrir(tmp_path):
	ruta = tmp_path / "p.db"
	with BaseSeguimiento(ruta, cifrador=cifrador_de_prueba(b"buena")) as base:
		Fichas(base).alta("Luna", nombre_real="Ana")
	with pytest.raises(ErrorClave):
		BaseSeguimiento(ruta, cifrador=cifrador_de_prueba(b"mala"))
	with pytest.raises(ErrorClave):
		BaseSeguimiento(ruta)
	with BaseSeguimiento(ruta, cifrador=cifrador_de_prueba(b"buena")) as base:
		assert Fichas(base).por_alias("Luna").nombre_real == "Ana"


def test_una_base_sin_cifrar_se_cifra_al_abrirla_con_clave(tmp_path):
	ruta = tmp_path / "p.db"
	with BaseSeguimiento(ruta) as base:
		Fichas(base).alta("Luna", nombre_real="Nombre En Claro")
	assert b"Nombre En Claro" in ruta.read_bytes()
	with BaseSeguimiento(ruta, cifrador=cifrador_de_prueba(b"nueva")) as base:
		assert Fichas(base).por_alias("Luna").nombre_real == "Nombre En Claro"
		valor = bytes(base.valor("SELECT nombre_real FROM alumnos"))
		assert b"Nombre En Claro" not in valor
	with pytest.raises(ErrorClave):
		BaseSeguimiento(ruta)


def test_cambiar_cifrador_recifra_todo(tmp_path):
	ruta = tmp_path / "p.db"
	with BaseSeguimiento(ruta, cifrador=cifrador_de_prueba(b"vieja")) as base:
		Fichas(base).alta("Luna", nombre_real="Ana", notas="nota")
		base.cambiar_cifrador(cifrador_de_prueba(b"nueva"))
		assert Fichas(base).por_alias("Luna").notas == "nota"
	with pytest.raises(ErrorClave):
		BaseSeguimiento(ruta, cifrador=cifrador_de_prueba(b"vieja"))
	with BaseSeguimiento(ruta, cifrador=cifrador_de_prueba(b"nueva")) as base:
		assert Fichas(base).por_alias("Luna").nombre_real == "Ana"


def test_abrir_base_con_funciones_inyectadas(tmp_path):
	def cifrar(datos: bytes, clave: bytes) -> bytes:
		return bytes(reversed(datos)) + clave

	def descifrar(datos: bytes, clave: bytes) -> bytes:
		assert datos.endswith(clave)
		return bytes(reversed(datos[: -len(clave)]))

	with abrir_base(tmp_path / "p.db", clave=b"k1", cifrar=cifrar, descifrar=descifrar) as base:
		Fichas(base).alta("Sol", nombre_real="Marta")
		assert Fichas(base).por_alias("sol").nombre_real == "Marta"
	with pytest.raises(ValueError):
		abrir_base(tmp_path / "q.db", cifrar=cifrar)
	with pytest.raises(ValueError):
		Cifrador(cifrar=lambda datos: datos)


def test_copia_de_seguridad_y_rotacion(tmp_path):
	with BaseSeguimiento(tmp_path / "p.db", copias_conservadas=2) as base:
		for _vuelta in range(3):
			base.copia_seguridad()
		assert len(base.copias()) == 2
		assert base.purgar_copias() == 2
		assert base.copias() == []


def test_normalizar_busqueda_quita_acentos_y_mayusculas():
	assert normalizar_busqueda("  María JOSÉ ") == "maria jose"
