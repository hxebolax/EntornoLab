"""Pruebas de las fichas de alumnos, el cuaderno real, las recompensas, exportar, borrar y caducar."""

from __future__ import annotations

import io
import json
import zipfile
from datetime import UTC, datetime

import pytest

from app.seguimiento import cuaderno, recompensas, sesiones
from app.seguimiento.alumnos import Fichas
from app.seguimiento.base import BaseSeguimiento, ErrorDatos
from app.seguimiento.grabadora import escribir_sesion
from tests._seguimiento_util import cifrador_de_prueba, documento_sesion

ID1 = "1" * 32
ID2 = "2" * 32
ID3 = "3" * 32


@pytest.fixture
def base(tmp_path):
	with BaseSeguimiento(tmp_path / "db" / "p.db", cifrador=cifrador_de_prueba(b"clave")) as abierta:
		yield abierta


def test_alta_y_lectura(base):
	fichas = Fichas(base)
	ficha = fichas.alta(
		"  Luna   Azul ",
		nombre_real="Ana",
		notas="usa bastón largo",
		ano_nacimiento=2015,
		perfil="baston",
		estilo="infantil",
		ajustes={"paso_m": 0.5},
	)
	assert ficha.alias == "Luna Azul"
	assert ficha.perfil == "baston"
	assert ficha.ajustes == {"paso_m": 0.5}
	assert ficha.alta
	assert not ficha.archivado
	assert fichas.por_alias("luna azul").id == ficha.id


def test_alias_obligatorio_y_unico(base):
	fichas = Fichas(base)
	fichas.alta("María")
	with pytest.raises(ErrorDatos):
		fichas.alta("   ")
	with pytest.raises(ErrorDatos):
		fichas.alta("maria")
	with pytest.raises(ErrorDatos):
		fichas.alta("x" * 61)


def test_valores_no_validos(base):
	fichas = Fichas(base)
	with pytest.raises(ErrorDatos):
		fichas.alta("A", perfil="volador")
	with pytest.raises(ErrorDatos):
		fichas.alta("A", estilo="anciano")
	with pytest.raises(ErrorDatos):
		fichas.alta("A", ano_nacimiento=1800)


def test_editar_archivar_y_buscar(base):
	fichas = Fichas(base)
	luna = fichas.alta("Luna")
	sol = fichas.alta("Sol")
	fichas.alta("100%_raro")
	editada = fichas.editar(luna.id, alias="Lúa", perfil="perro_guia", notas="cambio")
	assert editada.alias == "Lúa"
	assert editada.notas == "cambio"
	with pytest.raises(ErrorDatos):
		fichas.editar(luna.id, alias="sol")
	with pytest.raises(ErrorDatos):
		fichas.editar(luna.id, id=7)
	assert [a.alias for a in fichas.buscar("lua")] == ["Lúa"]
	assert [a.alias for a in fichas.buscar("%")] == ["100%_raro"]
	assert fichas.archivar(sol.id)
	assert "Sol" not in [a.alias for a in fichas.buscar()]
	assert "Sol" in [a.alias for a in fichas.buscar(incluir_archivados=True)]
	assert fichas.archivar(sol.id, False)
	assert len(fichas.buscar()) == 3


def test_sesiones_guardar_es_idempotente_y_separa_las_marcas(base):
	luna = Fichas(base).alta("Luna")
	marca = {"t": 5.0, "planta": "p0", "x": 5.0, "y": 2.0, "texto": "Duda en la puerta secreta"}
	documento = documento_sesion(ID1, marcas=[marca])
	assert sesiones.guardar_sesion(base, luna.id, documento) == "nueva"
	assert sesiones.guardar_sesion(base, luna.id, documento) == "repetida"
	assert base.valor("SELECT COUNT(*) FROM sesiones") == 1
	guardada = sesiones.obtener(base, ID1, con_traza=True)
	assert guardada["resumen"]["choques"]["total"] == 1
	assert len(guardada["traza"]["muestras"]) == len(documento["traza"]["muestras"])
	assert guardada["marcas"][0]["texto"] == "Duda en la puerta secreta"
	assert "texto" not in guardada["traza"]["marcas"][0]
	assert b"puerta secreta" not in bytes(base.valor("SELECT texto FROM marcas"))
	assert sesiones.anotar(base, ID1, "Buena sesión, repetir el jueves")
	assert sesiones.obtener(base, ID1)["notas"] == "Buena sesión, repetir el jueves"
	sesiones.anadir_marca(base, ID1, 9.0, "otra")
	assert [m["t"] for m in sesiones.marcas(base, ID1)] == [5.0, 9.0]


def test_sesion_parcial_se_sustituye_por_la_definitiva(base):
	luna = Fichas(base).alta("Luna")
	assert sesiones.guardar_sesion(base, luna.id, documento_sesion(ID1, parcial=True, completada=False)) == "nueva"
	assert sesiones.obtener(base, ID1)["parcial"]
	assert sesiones.guardar_sesion(base, luna.id, documento_sesion(ID1)) == "actualizada"
	assert not sesiones.obtener(base, ID1)["parcial"]
	assert sesiones.guardar_sesion(base, luna.id, documento_sesion(ID1, parcial=True)) == "repetida"


@pytest.mark.parametrize(
	"estropear",
	[
		lambda d: d.pop("manifiesto"),
		lambda d: d["manifiesto"].update(id="../../malo"),
		lambda d: d["manifiesto"].update(alias="  "),
		lambda d: d["manifiesto"].update(modo="trampa"),
		lambda d: d["manifiesto"].update(formato=99),
		lambda d: d.update(traza=[1, 2]),
		lambda d: d["traza"].update(muestras="no"),
	],
)
def test_documento_de_sesion_mal_formado_se_rechaza(base, estropear):
	luna = Fichas(base).alta("Luna")
	documento = documento_sesion(ID1)
	estropear(documento)
	with pytest.raises(ErrorDatos):
		sesiones.guardar_sesion(base, luna.id, documento)
	assert base.valor("SELECT COUNT(*) FROM sesiones") == 0


def test_listar_sesiones_con_filtros(base):
	luna = Fichas(base).alta("Luna")
	sol = Fichas(base).alta("Sol")
	sesiones.guardar_sesion(base, luna.id, documento_sesion(ID1, inicio="2026-10-01T10:00:00+00:00", fin="2026-10-01T10:05:00+00:00"))
	sesiones.guardar_sesion(base, luna.id, documento_sesion(ID2, entorno="cole", modo="examen"))
	sesiones.guardar_sesion(base, sol.id, documento_sesion(ID3, alias="Sol"))
	assert [s["id"] for s in sesiones.listar(base, luna.id)] == [ID1, ID2]
	assert [s["id"] for s in sesiones.listar(base, luna.id, entorno_id="cole")] == [ID2]
	assert [s["id"] for s in sesiones.listar(base, modo="examen")] == [ID2]
	assert [s["id"] for s in sesiones.listar(base, luna.id, desde="2026-11-01")] == [ID2]


def test_cuaderno_de_evaluacion_real(base):
	luna = Fichas(base).alta("Luna")
	sesiones.guardar_sesion(base, luna.id, documento_sesion(ID1))  # 2026-11-20
	ident = cuaderno.anotar(
		base,
		luna.id,
		fecha="2026-11-27",
		lugar="Centro cívico",
		entorno_id="casa",
		entorno_nombre="Casa de ejemplo",
		rutas=[
			{"nombre": "Entrada a cocina", "resultado": "conseguida"},
			{"nombre": "Cocina a baño", "resultado": "con_ayuda", "notas": "duda"},
		],
		nivel_ayuda="supervision",
		tipo_recorrido="entrenado",
		ayudas_movilidad=["bastón largo", " "],
		observaciones="Observación reservada",
	)
	evaluacion = cuaderno.obtener(base, ident)
	assert evaluacion.dias_desde_entrenamiento == 7
	assert evaluacion.ayudas_movilidad == ["bastón largo"]
	assert evaluacion.rutas[1]["resultado"] == "con_ayuda"
	assert evaluacion.observaciones == "Observación reservada"
	assert b"reservada" not in bytes(base.valor("SELECT observaciones FROM evaluaciones_reales"))
	assert len(cuaderno.listar(base, luna.id, entorno_id="casa")) == 1
	with pytest.raises(ErrorDatos):
		cuaderno.anotar(base, luna.id, fecha="27/11/2026")
	with pytest.raises(ErrorDatos):
		cuaderno.anotar(base, luna.id, fecha="2026-11-27", rutas=[{"nombre": "x", "resultado": "regular"}])
	with pytest.raises(ErrorDatos):
		cuaderno.anotar(base, 999, fecha="2026-11-27")
	assert cuaderno.borrar(base, ident)


def test_recompensas_y_coleccion(base):
	luna = Fichas(base).alta("Luna")
	sesiones.guardar_sesion(base, luna.id, documento_sesion(ID1))
	recompensas.registrar(base, luna.id, "estrella", "Primera", sesion_id=ID1)
	recompensas.registrar(base, luna.id, "estrella")
	recompensas.registrar(base, luna.id, "medalla", "Exploradora")
	recompensas.registrar(base, luna.id, "objeto", "Llave dorada")
	recompensas.registrar(base, luna.id, "objeto", "Llave dorada")
	with pytest.raises(ErrorDatos):
		recompensas.registrar(base, luna.id, "trofeo")
	with pytest.raises(ErrorDatos):
		recompensas.registrar(base, 999, "estrella")
	coleccion = recompensas.coleccion(base, luna.id)
	assert coleccion["estrellas"] == 2
	assert [m["nombre"] for m in coleccion["medallas"]] == ["Exploradora"]
	assert coleccion["objetos"] == [{"nombre": "Llave dorada", "veces": 2, "primera_fecha": coleccion["objetos"][0]["primera_fecha"]}]
	assert len(recompensas.de_alumno(base, luna.id, "estrella")) == 2
	# Registrar las de una sesión dos veces no duplica.
	resumen = {"recompensas": [{"tipo": "estrella", "nombre": "a"}, {"tipo": "medalla", "nombre": "b"}, {"tipo": "raro"}]}
	assert recompensas.registrar_de_sesion(base, luna.id, ID1, resumen) == 2
	assert recompensas.registrar_de_sesion(base, luna.id, ID1, resumen) == 2
	assert len([r for r in recompensas.de_alumno(base, luna.id) if r.sesion_id == ID1]) == 2


def _poblar(base, tmp_path):
	fichas = Fichas(base)
	luna = fichas.alta("Luna", nombre_real="Ana Real", notas="notas de Luna", ano_nacimiento=2014, perfil="baston", estilo="infantil")
	sol = fichas.alta("Sol", nombre_real="Marta Real")
	sesiones.guardar_sesion(base, luna.id, documento_sesion(ID1, marcas=[{"t": 1.0, "texto": "marca de Luna"}]))
	sesiones.guardar_sesion(base, luna.id, documento_sesion(ID2))
	sesiones.guardar_sesion(base, sol.id, documento_sesion(ID3, alias="Sol"))
	sesiones.anotar(base, ID1, "nota de sesión")
	cuaderno.anotar(
		base, luna.id, fecha="2026-11-27", lugar="=Centro", rutas=[{"nombre": "A", "resultado": "conseguida"}], observaciones="obs"
	)
	cuaderno.anotar(base, sol.id, fecha="2026-11-27")
	recompensas.registrar(base, luna.id, "medalla", "Exploradora", sesion_id=ID1)
	recompensas.registrar(base, sol.id, "estrella")
	carpeta = tmp_path / "sessions"
	escribir_sesion(carpeta / f"{'a' * 32}.json.gz", documento_sesion("a" * 32, alias="LUNA"))
	escribir_sesion(carpeta / f"{'b' * 32}.json.gz", documento_sesion("b" * 32, alias="Sol"))
	return luna, sol, carpeta


def test_exportar_todos_los_datos_de_un_alumno(base, tmp_path):
	luna, _sol, _carpeta = _poblar(base, tmp_path)
	destino = Fichas(base).exportar(luna.id, tmp_path / "salida" / "luna.zip")
	with zipfile.ZipFile(destino) as paquete:
		nombres = set(paquete.namelist())
		assert {
			"LEEME.txt",
			"alumno.json",
			"sesiones.csv",
			"evaluaciones_reales.json",
			"evaluaciones_reales.csv",
			"recompensas.csv",
		} <= nombres
		assert {f"sesiones/{ID1}.json", f"sesiones/{ID2}.json"} <= nombres
		assert f"sesiones/{ID3}.json" not in nombres
		ficha = json.loads(paquete.read("alumno.json"))
		assert ficha["nombre_real"] == "Ana Real"
		assert ficha["notas"] == "notas de Luna"
		sesion = json.loads(paquete.read(f"sesiones/{ID1}.json"))
		assert sesion["notas"] == "nota de sesión"
		assert sesion["marcas"][0]["texto"] == "marca de Luna"
		assert len(sesion["traza"]["muestras"]) > 10
		tabla = paquete.read("sesiones.csv").decode("utf-8-sig")
		lineas = tabla.strip().splitlines()
		assert len(lineas) == 3
		assert lineas[0].startswith("Sesión;Inicio;Fin;Entorno")
		evaluaciones = paquete.read("evaluaciones_reales.csv").decode("utf-8-sig")
		assert "'=Centro" in evaluaciones  # no se deja una fórmula en el CSV
		assert "Marta" not in io.BytesIO(paquete.read("alumno.json")).read().decode("utf-8")
		assert "no está cifrado".upper() in paquete.read("LEEME.txt").decode("utf-8-sig").upper()
	with pytest.raises(ErrorDatos):
		Fichas(base).exportar(999, tmp_path / "nada.zip")


def test_borrado_completo_e_irreversible(base, tmp_path):
	luna, sol, carpeta = _poblar(base, tmp_path)
	base.copia_seguridad()
	cuenta = Fichas(base).borrar(luna.id, carpeta_sesiones=carpeta)
	assert cuenta["sesiones"] == 2
	assert cuenta["marcas"] == 1
	assert cuenta["evaluaciones"] == 1
	assert cuenta["recompensas"] == 1
	assert cuenta["ficheros"] == 1
	assert cuenta["copias"] == 1
	fichas = Fichas(base)
	assert fichas.obtener(luna.id) is None
	assert fichas.por_alias("Luna") is None
	for tabla, esperado in (("sesiones", 1), ("marcas", 0), ("evaluaciones_reales", 1), ("recompensas", 1), ("alumnos", 1)):
		assert base.valor(f"SELECT COUNT(*) FROM {tabla}") == esperado, tabla
	# Lo de Sol sigue intacto, también su fichero sin incorporar.
	assert fichas.obtener(sol.id).nombre_real == "Marta Real"
	assert sorted(ruta.name for ruta in carpeta.iterdir()) == [f"{'b' * 32}.json.gz"]
	# Ni la base ni la copia nueva contienen ya el alias ni el id de sus sesiones.
	copias = base.copias()
	assert len(copias) == 1
	assert "tras-borrar-alumno" in copias[0].name
	ruta_base = base.ruta
	base.cerrar()
	for fichero in (ruta_base, copias[0]):
		contenido = fichero.read_bytes()
		assert b"Luna" not in contenido
		assert ID1.encode() not in contenido
	assert not ruta_base.with_name(ruta_base.name + "-wal").exists() or ruta_base.with_name(ruta_base.name + "-wal").stat().st_size == 0


def test_borrar_un_alumno_que_no_existe(base):
	with pytest.raises(ErrorDatos):
		Fichas(base).borrar(12345)


def test_caducidad_de_sesiones(base):
	fichas = Fichas(base)
	luna = fichas.alta("Luna")
	sesiones.guardar_sesion(
		base,
		luna.id,
		documento_sesion(ID1, inicio="2026-01-10T10:00:00+00:00", fin="2026-01-10T10:05:00+00:00", marcas=[{"t": 1, "texto": "vieja"}]),
	)
	sesiones.guardar_sesion(base, luna.id, documento_sesion(ID2, inicio="2026-11-20T10:00:00+00:00", fin="2026-11-20T10:05:00+00:00"))
	recompensas.registrar(base, luna.id, "estrella", sesion_id=ID1)
	ahora = datetime(2026, 11, 26, tzinfo=UTC)
	assert fichas.caducar_sesiones(365, ahora=ahora) == 0
	assert fichas.caducar_sesiones(90, ahora=ahora) == 1
	assert [s["id"] for s in sesiones.listar(base, luna.id)] == [ID2]
	assert base.valor("SELECT COUNT(*) FROM marcas") == 0
	# La recompensa se conserva, ya sin sesión.
	assert recompensas.de_alumno(base, luna.id)[0].sesion_id is None
	with pytest.raises(ErrorDatos):
		fichas.caducar_sesiones(0)
