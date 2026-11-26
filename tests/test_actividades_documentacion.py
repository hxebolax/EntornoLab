"""``docs/actividades.md`` dice la verdad: sus ejemplos JSON son válidos en los entornos distribuidos y sus listas están completas."""

from __future__ import annotations

import functools
import json
import re

from app.actividades import TIPOS, crear_actividad, normalizar, validar_actividad
from app.dominio.formato import Paquete, cargar_paquete
from tests.test_actividades_comun import RAIZ, Jugador, catalogo_real

DOCUMENTO = RAIZ / "docs" / "actividades.md"
BLOQUE = re.compile(r"<!-- entorno: ([a-z0-9-]+) -->\n```json\n(.*?)\n```", re.DOTALL)


@functools.cache
def paquete(nombre: str) -> Paquete:
	return cargar_paquete(RAIZ / "data" / "ejemplos" / f"{nombre}.elab")


def ejemplos_del_documento() -> list[tuple[str, dict]]:
	texto = DOCUMENTO.read_text(encoding="utf-8")
	return [(nombre, json.loads(cuerpo)) for nombre, cuerpo in BLOQUE.findall(texto)]


def test_hay_un_ejemplo_json_de_cada_tipo():
	ejemplos = ejemplos_del_documento()
	assert {datos["tipo"] for _nombre, datos in ejemplos} == set(TIPOS)
	texto = DOCUMENTO.read_text(encoding="utf-8")
	assert "@@" not in texto, "quedan marcadores sin rellenar"
	for tipo in TIPOS:
		assert f"### `{tipo}`" in texto, tipo


def test_los_ejemplos_del_documento_son_validos_y_se_pueden_jugar():
	for nombre, datos in ejemplos_del_documento():
		entorno = paquete(nombre).entorno
		avisos = validar_actividad(datos, entorno, catalogo_real())
		assert not [a for a in avisos if a.es_error], (datos["id"], [str(a) for a in avisos])
		actividad = crear_actividad(datos, entorno, catalogo_real())
		assert actividad.tipo == datos["tipo"] and actividad.nombre == datos["nombre"]
		# Lo que el documento omite son los valores de serie: completarlo no cambia lo que dice.
		completo = normalizar(datos)
		for clave, valor in datos.items():
			if not isinstance(valor, (list, dict)):
				assert completo[clave] == valor, (datos["id"], clave)
		jugador = Jugador(entorno, datos)
		jugador.tic(5)
		assert not jugador.sesion.terminado, datos["id"]
		assert jugador.actividad.estado()["objetivo"], datos["id"]
		assert jugador.actividad.estado()["total"] >= 1, datos["id"]


def test_los_ejemplos_que_son_plantillas_coinciden_con_los_paquetes_distribuidos():
	"""Los ejemplos tomados de ``data/ejemplos`` no se han quedado viejos: tienen los mismos premios y objetivos."""
	comprobados = 0
	for nombre, datos in ejemplos_del_documento():
		distribuida = paquete(nombre).actividad(datos["id"])
		if distribuida is None:
			continue
		comprobados += 1
		completo = normalizar(datos)
		for clave in ("tipo", "nombre", "estilo", "premios", "objetivos", "pruebas", "destino", "espacio"):
			assert completo.get(clave) == distribuida.get(clave), (datos["id"], clave)
	assert comprobados >= 10


def test_el_documento_lista_todos_los_codigos_de_validacion_y_las_claves_del_resultado():
	texto = DOCUMENTO.read_text(encoding="utf-8")
	fuente = (RAIZ / "app" / "actividades" / "validacion.py").read_text(encoding="utf-8")
	codigos = set(re.findall(r"""(?:ctx|self)\.(?:error|aviso)\(\s*"([a-z_]+)\"""", fuente)) | {"formato"}
	assert len(codigos) > 30
	for codigo in sorted(codigos):
		assert f"`{codigo}`" in texto, codigo
	entorno = paquete("vivienda-de-ejemplo").entorno
	jugador = Jugador(entorno, paquete("vivienda-de-ejemplo").actividad("visita-a-la-casa"))
	jugador.sesion.terminar()
	jugador.tic(1)
	propias = set(jugador.fin)
	# La actividad no pisa las cifras de la sesión: «pasos» sigue siendo el número de pasos andados.
	assert isinstance(jugador.fin["pasos"], int) and isinstance(jugador.fin["pasos_actividad"], list)
	for clave in sorted(propias):
		assert f"`{clave}`" in texto, clave
	for clave in jugador.actividad.estado():
		assert f"`{clave}`" in texto or clave in ("id", "tipo", "modo"), clave
	# Y no promete lo que el programa no hace.
	for frase in ("no equivale a competencia en el lugar real", "No hay diagnósticos", "No dice que un cruce real sea seguro"):
		assert frase in texto, frase
