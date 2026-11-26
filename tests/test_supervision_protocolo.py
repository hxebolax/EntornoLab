"""Pruebas del protocolo de supervisión: codificar, decodificar y trocear líneas."""

from __future__ import annotations

import json

import pytest

from app.supervision import protocolo
from app.supervision.protocolo import A_ESTUDIO, A_JUGAR, MAX_LINEA, ErrorProtocolo, LectorLineas


def _linea(sobre: dict) -> bytes:
	return json.dumps(sobre).encode("utf-8")


def test_ida_y_vuelta_de_un_estado():
	datos = {
		"planta": "p0",
		"x": 3.5,
		"y": -2,
		"rumbo": 90.0,
		"espacio": "Cocina",
		"descripcion": "Cocina, planta baja",
		"pausado": False,
		"tiempo_activo": 12.25,
		"contadores": {"choques": 2, "ayudas": {"baliza": 1}},
	}
	linea = protocolo.codificar("estado", datos, sentido=A_ESTUDIO, seq=7, t=1.23456)
	assert linea.endswith(b"\n")
	assert linea.count(b"\n") == 1
	sobre = json.loads(linea)
	assert sobre == {"v": 1, "tipo": "estado", "seq": 7, "t": 1.235, "datos": datos}
	mensaje = protocolo.decodificar(linea, A_ESTUDIO)
	assert (mensaje.tipo, mensaje.seq, mensaje.t, mensaje.v) == ("estado", 7, 1.235, 1)
	assert mensaje.datos == datos


def test_todos_los_tipos_del_documento_existen():
	assert {"hola", "estado", "evento", "voz", "fin", "latido", "peticion"} == set(protocolo.ESQUEMAS[A_ESTUDIO])
	assert {
		"bienvenida",
		"pausa",
		"reanudar",
		"recolocar",
		"mensaje",
		"pista",
		"ayudas",
		"premio",
		"reiniciar",
		"terminar",
		"latido",
	} <= set(protocolo.ESQUEMAS[A_JUGAR])
	for orden in protocolo.ORDENES:
		assert orden in protocolo.ESQUEMAS[A_JUGAR]


def test_los_tipos_dependen_del_sentido():
	linea = protocolo.codificar("pausa", {}, sentido=A_JUGAR)
	assert protocolo.decodificar(linea, A_JUGAR).tipo == "pausa"
	with pytest.raises(ErrorProtocolo) as error:
		protocolo.decodificar(linea, A_ESTUDIO)
	assert error.value.codigo == "tipo"


def test_los_campos_desconocidos_se_descartan():
	linea = _linea({"v": 1, "tipo": "voz", "seq": 0, "t": 0, "datos": {"texto": "hola", "futuro": [1, 2, 3]}, "extra": True})
	assert protocolo.decodificar(linea, A_ESTUDIO).datos == {"texto": "hola"}


@pytest.mark.parametrize(
	("linea", "codigo"),
	[
		(b"esto no es json", "json"),
		(b"\xff\xfe\x00", "json"),
		(b"[1, 2, 3]", "sobre"),
		(b'"texto"', "sobre"),
		(_linea({"tipo": "latido", "datos": {}}), "sobre"),
		(_linea({"v": "1", "tipo": "latido", "datos": {}}), "sobre"),
		(_linea({"v": True, "tipo": "latido", "datos": {}}), "sobre"),
		(_linea({"v": 2, "tipo": "latido", "datos": {}}), "version"),
		(_linea({"v": 1, "tipo": "borrar_todo", "datos": {}}), "tipo"),
		(_linea({"v": 1, "tipo": 7, "datos": {}}), "tipo"),
		(_linea({"v": 1, "tipo": ["voz"], "datos": {}}), "tipo"),
		(_linea({"v": 1, "tipo": "voz", "datos": []}), "sobre"),
		(_linea({"v": 1, "tipo": "voz", "seq": -1, "datos": {"texto": "a"}}), "sobre"),
		(_linea({"v": 1, "tipo": "voz", "seq": 1.5, "datos": {"texto": "a"}}), "sobre"),
		(_linea({"v": 1, "tipo": "voz", "t": "ahora", "datos": {"texto": "a"}}), "sobre"),
		(_linea({"v": 1, "tipo": "voz", "datos": {}}), "campo"),
		(_linea({"v": 1, "tipo": "voz", "datos": {"texto": 5}}), "campo"),
		(_linea({"v": 1, "tipo": "voz", "datos": {"texto": None}}), "campo"),
		(_linea({"v": 1, "tipo": "voz", "datos": {"texto": "x" * 2001}}), "campo"),
		(_linea({"v": 1, "tipo": "estado", "datos": {"x": "3"}}), "campo"),
		(_linea({"v": 1, "tipo": "estado", "datos": {"x": True}}), "campo"),
		(_linea({"v": 1, "tipo": "estado", "datos": {"x": 1e300}}), "campo"),
		(_linea({"v": 1, "tipo": "estado", "datos": {"pausado": 1}}), "campo"),
		(_linea({"v": 1, "tipo": "estado", "datos": {"contadores": [1]}}), "campo"),
		(_linea({"v": 1, "tipo": "estado", "datos": {"contadores": {"a": {"b": {"c": {"d": {"e": 1}}}}}}}), "campo"),
		(_linea({"v": 1, "tipo": "estado", "datos": {"contadores": {str(i): i for i in range(400)}}}), "campo"),
		(_linea({"v": 1, "tipo": "peticion", "datos": {"id": 1, "accion": "formatear"}}), "campo"),
		(_linea({"v": 1, "tipo": "peticion", "datos": {"id": 1.0, "accion": "colocar_aqui"}}), "campo"),
		(b'{"v": 1, "tipo": "estado", "datos": {"x": NaN}}', "json"),
		(b'{"v": 1, "tipo": "estado", "datos": {"x": Infinity}}', "json"),
		(b'{"v": 1, "tipo": "estado", "datos": {"x": 1e999}}', "campo"),
		(b"[" * 100000 + b"]" * 100000, "tamano"),
		(b'{"v": 1, "tipo": "voz", "datos": {"texto": "' + b"a" * MAX_LINEA + b'"}}', "tamano"),
	],
)
def test_mensajes_mal_formados_se_rechazan_con_su_codigo(linea, codigo):
	with pytest.raises(ErrorProtocolo) as error:
		protocolo.decodificar(linea, A_ESTUDIO)
	assert error.value.codigo == codigo
	# El texto del error no repite el contenido del mensaje: se puede registrar.
	assert len(str(error.value)) < 80


def test_codificar_valida_lo_que_sale():
	with pytest.raises(ErrorProtocolo):
		protocolo.codificar("recolocar", {"planta": "p0", "x": "tres", "y": 1}, sentido=A_JUGAR)
	with pytest.raises(ErrorProtocolo):
		protocolo.codificar("recolocar", {"planta": "p0"}, sentido=A_JUGAR)
	with pytest.raises(ErrorProtocolo):
		protocolo.codificar("inventado", {}, sentido=A_JUGAR)
	with pytest.raises(ErrorProtocolo):
		protocolo.codificar("rechazo", {"motivo": "porque_si"}, sentido=A_JUGAR)
	with pytest.raises(ErrorProtocolo) as error:
		protocolo.codificar("evento", {"tipo": "x", "datos": {str(i): "y" * 1900 for i in range(40)}}, sentido=A_ESTUDIO)
	assert error.value.codigo == "tamano"
	with pytest.raises(ValueError):
		protocolo.validar("pausa", {}, "a_marte")
	assert protocolo.codificar("recolocar", {"planta": "p0", "x": 1, "y": 2, "rumbo": None}, sentido=A_JUGAR)


def test_filtrar_se_queda_con_lo_valido():
	limpio, descartados = protocolo.filtrar("estado", {"x": 1.0, "espacio": None, "pausado": "no", "inventado": 3, "rumbo": 90}, A_ESTUDIO)
	assert limpio == {"x": 1.0, "rumbo": 90}
	assert sorted(descartados) == ["espacio", "pausado"]


def test_lector_trocea_lineas_partidas():
	lector = LectorLineas()
	assert lector.alimentar(b'{"a":') == []
	assert lector.alimentar(b' 1}\n{"b": 2}\n\n{"c"') == [b'{"a": 1}', b'{"b": 2}']
	assert lector.alimentar(b": 3}\r\n") == [b'{"c": 3}\r']


def test_lector_descarta_una_linea_enorme_y_sigue():
	lector = LectorLineas(maximo=100)
	salida = []
	# Medio megabyte sin salto de línea, a trozos: no se acumula y solo se avisa una vez.
	for _trozo in range(500):
		salida += lector.alimentar(b"x" * 1000)
		assert len(lector._resto) <= 1100
	assert salida == [None]
	assert lector.alimentar(b'xxxx\n{"ok": 1}\n') == [b'{"ok": 1}']
	# Una línea demasiado larga que llega entera con su salto también se descarta.
	assert lector.alimentar(b"y" * 150 + b'\n{"ok": 2}\n') == [None, b'{"ok": 2}']


def test_json_muy_anidado_no_tumba_el_decodificador():
	# Según la versión de Python, el analizador lo rechaza por profundidad o lo acepta como lista:
	# en los dos casos debe salir un ErrorProtocolo y nunca un RecursionError.
	with pytest.raises(ErrorProtocolo) as error:
		protocolo.decodificar(b"[" * 10000 + b"]" * 10000, A_ESTUDIO)
	assert error.value.codigo in ("json", "sobre")


# ── Ficha del alumno y releer la configuración ───────────────────────────────


def test_orden_alumno_de_ida_y_vuelta():
	datos = {
		"ajustes": {
			"modo_movimiento": "continuo",
			"paso_m": 0.8,
			"giro_grados": 30,
			"velocidad_ms": 1.4,
			"formato_direccion": "lados",
			"unidad": "pasos",
			"estilo": "juvenil",
			"detalle": 3,
			"futuro": "x",
		},
		"lista": [
			{"entorno_id": "casa", "entorno_nombre": "Casa", "actividad_id": "busca", "actividad_nombre": "Busca", "paquete": "casa.elab"}
		],
		"niveles": {"casa/busca": 2},
	}
	mensaje = protocolo.decodificar(protocolo.codificar("alumno", datos, sentido=A_JUGAR), A_JUGAR)
	assert "futuro" not in mensaje.datos["ajustes"], "las claves desconocidas se descartan"
	assert (
		mensaje.datos["ajustes"]["detalle"] == 3
		and mensaje.datos["lista"] == datos["lista"]
		and mensaje.datos["niveles"] == {"casa/busca": 2}
	)
	# Las entradas de la lista quedan con todos sus campos, aunque falten (vacíos).
	solo_id = protocolo.validar("alumno", {"lista": [{"actividad_id": "busca"}]}, A_JUGAR)
	assert solo_id["lista"] == [{"entorno_id": "", "entorno_nombre": "", "actividad_id": "busca", "actividad_nombre": "", "paquete": ""}]
	assert protocolo.validar("releer_configuracion", {"lo_que_sea": 1}, A_JUGAR) == {}
	assert {"alumno", "releer_configuracion"} <= set(protocolo.ORDENES)


@pytest.mark.parametrize(
	"datos",
	[
		{"ajustes": {"paso_m": 9}},
		{"ajustes": {"paso_m": "0.8"}},
		{"ajustes": {"giro_grados": float("nan")}},
		{"ajustes": {"detalle": 2.5}},
		{"ajustes": {"detalle": True}},
		{"ajustes": {"unidad": "leguas"}},
		{"ajustes": "rápido"},
		{"lista": {"actividad_id": "busca"}},
		{"lista": ["busca"]},
		{"lista": [{"actividad_id": ""}]},
		{"lista": [{"actividad_id": "busca", "paquete": 3}]},
		{"lista": [{"actividad_id": "a"}] * (protocolo.LISTA_MAXIMA + 1)},
		{"niveles": {"sin_barra": 1}},
		{"niveles": {"casa/busca": -1}},
		{"niveles": {"casa/busca": protocolo.NIVEL_MAXIMO + 1}},
		{"niveles": {"casa/busca": "2"}},
	],
)
def test_orden_alumno_rechaza_tipos_y_rangos_incorrectos(datos):
	with pytest.raises(ErrorProtocolo) as error:
		protocolo.validar("alumno", datos, A_JUGAR)
	assert error.value.codigo == "campo"
