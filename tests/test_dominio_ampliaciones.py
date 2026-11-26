"""Pruebas de las ampliaciones del formato de complementos y del amueblado asistido.

Son añadidos compatibles: ``suelo``, ``aviso``, ``paso_libre``, nombres de
estado traducibles, dinámica validada, nombres de sonido de serie con barra
(``golpe/metal``), complementos preferidos al amueblar y mobiliario sugerido
en los espacios de los ejemplos.
"""

from __future__ import annotations

import copy

from app.dominio import colocacion as co
from app.dominio import ejemplos
from app.dominio.catalogo import Catalogo, clave_de_sonido, es_sonido_de_complemento, validar_complemento
from app.dominio.validacion import validar
from tests.test_dominio_comun import FICHA_PRUEBA, catalogo_de_prueba, escribir_complemento


def _objeto(ficha: dict, id_objeto: str) -> dict:
	return next(objeto for objeto in ficha["objetos"] if objeto["id"] == id_objeto)


def _ficha_ampliada() -> dict:
	ficha = copy.deepcopy(FICHA_PRUEBA)
	ficha["estados"] = {"cerrado": "Cerrado", "abierto": "Abierto de par en par"}
	alfombra = _objeto(ficha, "alfombra")
	alfombra["suelo"] = "alfombra"
	alfombra["aviso"] = "Estás sobre la alfombra."
	armario = _objeto(ficha, "armario")
	armario["paso_libre"] = ["abierto"]
	armario["sonidos"] = {"golpe": "golpe/madera", "propio": {"sonido": "fuente/reloj", "volumen": 0.3, "radio": 4, "estado": "abierto"}}
	armario["dinamica"] = {"tipo": "temporizador", "estado": "abierto", "segundos": 5, "al_terminar": "cerrado"}
	return ficha


def test_sonido_del_complemento_o_de_serie():
	assert es_sonido_de_complemento("sonidos/lavadora.flac")
	assert es_sonido_de_complemento("lavadora.ogg")
	assert es_sonido_de_complemento("sonidos/lavadora")
	assert es_sonido_de_complemento("sonidos\\lavadora.wav")
	# Los sonidos de serie se llaman «familia/nombre»: la barra sola no los convierte en ficheros del complemento.
	assert not es_sonido_de_complemento("golpe/metal")
	assert not es_sonido_de_complemento("fuente/frigorifico")
	assert not es_sonido_de_complemento("frigorifico")
	assert clave_de_sonido("hogar", "sonidos/lavadora.flac") == "hogar/lavadora.flac"
	assert clave_de_sonido("hogar", "lavadora.flac") == "hogar/lavadora.flac"
	assert clave_de_sonido("hogar", "golpe/metal") == "golpe/metal"
	assert clave_de_sonido("hogar", "frigorifico") == "frigorifico"


def test_suelo_aviso_paso_libre_y_nombres_de_estado(tmp_path):
	ingles = {
		"estados": {"abierto": "Wide open"},
		"objetos": {"alfombra": {"aviso": "You are on the rug.", "imagen": "No se usa: el objeto no tiene imagen."}},
	}
	carpeta = escribir_complemento(tmp_path, _ficha_ampliada(), traducciones={"en": ingles})
	assert validar_complemento(carpeta) == []
	catalogo = Catalogo.cargar(tmp_path, idioma="es")
	alfombra = catalogo.objeto("prueba/alfombra")
	assert (alfombra.suelo, alfombra.aviso) == ("alfombra", "Estás sobre la alfombra.")
	assert (
		catalogo.objeto("prueba/cama").suelo == ""
		and catalogo.objeto("prueba/cama").aviso == ""
		and catalogo.objeto("prueba/cama").paso_libre == []
	)
	# Un objeto con «paso_libre» corta el paso salvo en esos estados.
	armario = catalogo.crear_objeto("prueba/armario", 0, 0)
	assert armario.estado == "cerrado" and catalogo.bloquea(armario)
	armario.estado = "abierto"
	assert not catalogo.bloquea(armario)
	armario.datos["bloquea"] = True
	assert catalogo.bloquea(armario)
	# Nombres visibles de los estados, con su traducción y con un valor de serie legible.
	assert catalogo.nombre_estado("prueba/armario", "abierto") == "Abierto de par en par"
	assert catalogo.nombre_estado("prueba/armario", "medio_abierto") == "medio abierto"
	assert catalogo.nombre_estado("no-instalado/cosa", "en_marcha") == "en marcha"
	traducido = Catalogo.cargar(tmp_path, idioma="en")
	assert traducido.nombre_estado("prueba/armario", "abierto") == "Wide open"
	assert traducido.nombre_estado("prueba/armario", "cerrado") == "Cerrado"
	assert traducido.objeto("prueba/alfombra").aviso == "You are on the rug."
	assert traducido.objeto("prueba/alfombra").imagen == {}


def test_la_descripcion_de_la_imagen_se_traduce(tmp_path):
	ficha = _ficha_ampliada()
	_objeto(ficha, "cama")["imagen"] = {"fichero": "imagenes/cama.png", "descripcion": "Huella de la cama."}
	carpeta = escribir_complemento(tmp_path, ficha, traducciones={"en": {"objetos": {"cama": {"imagen": "Footprint of the bed."}}}})
	(carpeta / "imagenes").mkdir()
	(carpeta / "imagenes" / "cama.png").write_bytes(b"PNG")
	assert validar_complemento(carpeta) == []
	assert Catalogo.cargar(tmp_path, idioma="es").objeto("prueba/cama").imagen["descripcion"] == "Huella de la cama."
	assert Catalogo.cargar(tmp_path, idioma="en").objeto("prueba/cama").imagen == {
		"fichero": "imagenes/cama.png",
		"descripcion": "Footprint of the bed.",
	}


def test_validar_las_ampliaciones(tmp_path):
	ficha = _ficha_ampliada()
	_objeto(ficha, "alfombra")["suelo"] = "lava"
	armario = _objeto(ficha, "armario")
	armario["paso_libre"] = ["entornado"]
	armario["sonidos"]["propio"]["estado"] = "roto"
	armario["dinamica"] = {
		"tipo": "semaforo",
		"fases": [
			{"estado": "verde", "segundos": 5, "sonido": "sonidos/no-esta.ogg"},
			{"estado": "cerrado", "segundos": 5, "sonido": "semaforo/rojo"},
		],
	}
	_objeto(ficha, "cama")["dinamica"] = {"tipo": "teletransporte"}
	avisos = validar_complemento(escribir_complemento(tmp_path, ficha))
	assert sorted(a.codigo for a in avisos) == [
		"estado_desconocido",
		"estado_desconocido",
		"estado_desconocido",
		"sonido_ausente",
		"valor_desconocido",
		"valor_desconocido",
	]
	desconocidos = sorted(a.mensaje for a in avisos if a.codigo == "estado_desconocido")
	assert ["«entornado»" in m or "«roto»" in m or "«verde»" in m for m in desconocidos] == [True, True, True]
	assert {a.elemento_id for a in avisos if a.codigo == "valor_desconocido"} == {"prueba/alfombra", "prueba/cama"}
	assert all(a.gravedad == ("aviso" if a.codigo == "valor_desconocido" else "error") and a.sugerencia for a in avisos)


def test_amueblar_prefiere_el_complemento_indicado(tmp_path):
	escribir_complemento(tmp_path)
	otra = copy.deepcopy(FICHA_PRUEBA)
	otra["id"] = "zeta"
	otra["objetos"] = [objeto for objeto in otra["objetos"] if objeto["id"] in ("escritorio", "papelera", "silla")]
	escribir_complemento(tmp_path, otra)
	catalogo = Catalogo.cargar(tmp_path)
	assert co._buscar_mueble(catalogo, ("escritorio",)).tipo == "prueba/escritorio"
	assert co._buscar_mueble(catalogo, ("escritorio",), ("zeta",)).tipo == "zeta/escritorio"
	assert co._buscar_mueble(catalogo, ("escritorio",), ("no-instalado", "zeta", "prueba")).tipo == "zeta/escritorio"
	# Lo que el preferido no tiene se sigue tomando de los demás.
	assert co._buscar_mueble(catalogo, ("archivador", "estanteria"), ("zeta",)).tipo == "prueba/estanteria"
	from tests.test_dominio_comun import piso_minimo

	entorno, planta, salon, _cocina = piso_minimo()
	colocados = co.amueblar_espacio(entorno, planta, salon, "oficina", catalogo, preferidos=("zeta",))
	tipos = {objeto.tipo for objeto in colocados}
	assert {"zeta/escritorio", "zeta/silla", "zeta/papelera", "prueba/estanteria"} <= tipos
	assert "prueba/escritorio" not in tipos
	assert sorted(entorno.complementos) == ["prueba", "zeta"]


def test_mobiliario_sugerido_del_barrio(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno = ejemplos.barrio_ejemplo()
	calle = entorno.plantas[0]
	sugerencias = [s for espacio in calle.espacios for s in espacio.datos.get("mobiliario", [])]
	assert len(sugerencias) >= 40
	assert all(set(s) == {"palabras", "x", "y", "rumbo", "ambito"} and s["palabras"] for s in sugerencias)
	# Cada sugerencia está anotada en el espacio en el que cae.
	for espacio in calle.espacios:
		for sugerencia in espacio.datos.get("mobiliario", []):
			assert calle.espacio_en(sugerencia["x"], sugerencia["y"], incluir_macizos=False) is espacio
	# Sin amueblar no hay objetos y el entorno valida limpio; las sugerencias se guardan con él.
	assert calle.objetos == [] and validar(entorno) == []
	assert type(entorno).de_dict(entorno.a_dict()).a_dict() == entorno.a_dict()
	# El complemento de prueba solo tiene dos objetos de exterior: un banco y una jardinera.
	colocados = ejemplos.amueblar_ejemplos(entorno, catalogo)
	assert sorted(objeto.tipo for objeto in colocados) == ["prueba/banco", "prueba/banco", "prueba/jardinera"]
	assert all(calle.espacio_en(o.x, o.y).tipo == "acera" for o in colocados)
	assert not any(a.es_error for a in validar(entorno, catalogo))
	# Una sugerencia mal escrita o que no cabe se deja pasar sin romper nada.
	acera = next(e for e in calle.espacios if e.tipo == "acera")
	acera.datos["mobiliario"] = [
		"no es un diccionario",
		{"palabras": ["banco"]},
		{"palabras": ["banco"], "x": 500.0, "y": 500.0},
		{"palabras": ["dragon"], "x": 0, "y": 0},
	]
	assert ejemplos.amueblar_mobiliario(entorno, calle, acera, catalogo) == []
