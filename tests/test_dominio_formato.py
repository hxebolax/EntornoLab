"""Pruebas del paquete .elab: guardar atómico, cargar con validación de seguridad y migraciones."""

from __future__ import annotations

import json
import zipfile

import pytest

from app.dominio import formato as fo
from app.dominio.formato import ErrorFormato, Paquete, cargar_paquete, guardar_paquete, migrar
from app.dominio.modelo import FORMATO_ACTUAL, Entorno
from tests.test_dominio_comun import piso_minimo

ACTIVIDAD = {
	"formato": 1,
	"id": "buscar-llaves",
	"nombre": "Buscar las llaves",
	"tipo": "busqueda",
	"premios": [{"id": "llaves", "x": 1.5, "y": 2}],
}


def _zip_con(ruta, ficheros: dict[str, bytes | str]) -> None:
	with zipfile.ZipFile(ruta, "w") as archivo:
		for nombre, contenido in ficheros.items():
			archivo.writestr(nombre, contenido)


def _basico(entorno: Entorno | None = None) -> dict[str, str]:
	entorno = entorno or piso_minimo()[0]
	return {
		"manifiesto.json": json.dumps(
			{"formato": 1, "aplicacion": "EntornoLab", "version": "1.0.0", "id": entorno.id, "nombre": entorno.nombre}
		),
		"entorno.json": json.dumps(entorno.a_dict()),
	}


def test_guardar_y_cargar_conserva_todo(tmp_path):
	entorno = piso_minimo()[0]
	ruta = tmp_path / "piso.elab"
	guardar_paquete(ruta, entorno, [ACTIVIDAD], {"sonidos/timbre.ogg": b"OggS-falso", "imagenes/plano.png": b"\x89PNG-falso"})
	paquete = cargar_paquete(ruta)
	assert isinstance(paquete, Paquete)
	assert paquete.entorno == entorno
	assert paquete.actividades == [ACTIVIDAD]
	assert paquete.recurso("sonidos/timbre.ogg") == b"OggS-falso"
	assert paquete.recurso("timbre.ogg") == b"OggS-falso"
	assert paquete.recurso("plano.png").startswith(b"\x89PNG")
	assert paquete.tiene_recurso("timbre.ogg")
	assert not paquete.tiene_recurso("otro.ogg")
	with pytest.raises(KeyError):
		paquete.recurso("otro.ogg")
	assert paquete.nombres_recursos() == ["imagenes/plano.png", "sonidos/timbre.ogg"]
	assert paquete.actividad("buscar-llaves") == ACTIVIDAD
	assert paquete.actividad("no") is None
	assert paquete.manifiesto["aplicacion"] == "EntornoLab"
	assert paquete.manifiesto["formato"] == FORMATO_ACTUAL
	assert paquete.manifiesto["id"] == entorno.id
	assert paquete.ruta == ruta


def test_estructura_interna_del_zip(tmp_path):
	ruta = tmp_path / "piso.elab"
	guardar_paquete(ruta, piso_minimo()[0], [ACTIVIDAD, {"nombre": "Sin id"}, {"id": "buscar-llaves"}])
	with zipfile.ZipFile(ruta) as archivo:
		nombres = archivo.namelist()
		manifiesto = json.loads(archivo.read("manifiesto.json"))
	assert nombres[:2] == ["manifiesto.json", "entorno.json"]
	assert "actividades/buscar-llaves.json" in nombres
	assert "actividades/actividad-2.json" in nombres
	assert "actividades/buscar-llaves-2.json" in nombres
	assert set(manifiesto) == {"formato", "aplicacion", "version", "id", "nombre"}
	assert not (tmp_path / "piso.elab.tmp").exists()


def test_guardar_dos_veces_da_el_mismo_fichero(tmp_path):
	entorno = piso_minimo()[0]
	guardar_paquete(tmp_path / "a.elab", entorno)
	guardar_paquete(tmp_path / "b.elab", entorno)
	assert (tmp_path / "a.elab").read_bytes() == (tmp_path / "b.elab").read_bytes()


def test_guardar_deja_copia_bak_de_la_version_anterior(tmp_path):
	entorno = piso_minimo()[0]
	ruta = tmp_path / "piso.elab"
	guardar_paquete(ruta, entorno)
	assert not (tmp_path / "piso.elab.bak").exists()
	entorno.nombre = "Piso cambiado"
	guardar_paquete(ruta, entorno)
	assert cargar_paquete(ruta).entorno.nombre == "Piso cambiado"
	assert cargar_paquete(tmp_path / "piso.elab.bak").entorno.nombre == "Piso mínimo"
	assert fo.recuperar_copia(ruta).entorno.nombre == "Piso mínimo"


def test_un_fallo_al_escribir_no_toca_el_fichero_bueno(tmp_path, monkeypatch):
	entorno = piso_minimo()[0]
	ruta = tmp_path / "piso.elab"
	guardar_paquete(ruta, entorno)
	original = ruta.read_bytes()

	def falla(*_args, **_kwargs):
		raise OSError("disco lleno")

	monkeypatch.setattr(fo.os, "replace", falla)
	entorno.nombre = "No debería guardarse"
	with pytest.raises(ErrorFormato, match="No se puede guardar"):
		guardar_paquete(ruta, entorno)
	assert ruta.read_bytes() == original
	assert not (tmp_path / "piso.elab.tmp").exists()


def test_guardar_crea_la_carpeta_y_acepta_recursos_por_ruta(tmp_path):
	sonido = tmp_path / "origen.wav"
	sonido.write_bytes(b"RIFF")
	ruta = tmp_path / "nueva" / "carpeta" / "piso.elab"
	guardar_paquete(ruta, piso_minimo()[0], recursos={"sonidos/campana.wav": sonido})
	assert cargar_paquete(ruta).recurso("campana.wav") == b"RIFF"
	with pytest.raises(ErrorFormato, match="No se puede leer el recurso"):
		guardar_paquete(ruta, piso_minimo()[0], recursos={"sonidos/falta.wav": tmp_path / "no-existe.wav"})


@pytest.mark.parametrize(
	"nombre",
	[
		"../fuera.wav",
		"sonidos/../../fuera.wav",
		"/sonidos/a.wav",
		"C:/sonidos/a.wav",
		"sonidos\\a.wav",
		"sonidos/programa.exe",
		"otra/a.wav",
		"entorno.json",
		"sonidos/sub/a.wav",
		"imagenes/dibujo.svg",
	],
)
def test_guardar_rechaza_recursos_con_nombres_o_tipos_no_admitidos(tmp_path, nombre):
	with pytest.raises(ErrorFormato):
		guardar_paquete(tmp_path / "piso.elab", piso_minimo()[0], recursos={nombre: b"x"})
	assert not (tmp_path / "piso.elab").exists()


def test_guardar_rechaza_actividades_que_no_son_diccionarios(tmp_path):
	with pytest.raises(ErrorFormato, match="actividad número 1"):
		guardar_paquete(tmp_path / "piso.elab", piso_minimo()[0], ["no soy un diccionario"])


def test_cargar_fichero_inexistente_o_que_no_es_zip(tmp_path):
	with pytest.raises(ErrorFormato, match="No existe"):
		cargar_paquete(tmp_path / "nada.elab")
	basura = tmp_path / "basura.elab"
	basura.write_bytes(b"esto no es un zip")
	with pytest.raises(ErrorFormato, match="no es un paquete"):
		cargar_paquete(basura)


def test_cargar_exige_manifiesto_y_entorno(tmp_path):
	ruta = tmp_path / "x.elab"
	_zip_con(ruta, {"entorno.json": "{}"})
	with pytest.raises(ErrorFormato, match="manifiesto.json"):
		cargar_paquete(ruta)
	_zip_con(ruta, {"manifiesto.json": '{"formato": 1}'})
	with pytest.raises(ErrorFormato, match="entorno.json"):
		cargar_paquete(ruta)
	_zip_con(ruta, {"manifiesto.json": "[1, 2]", "entorno.json": "{}"})
	with pytest.raises(ErrorFormato, match="estructura"):
		cargar_paquete(ruta)
	_zip_con(ruta, {"manifiesto.json": '{"formato": 1}', "entorno.json": "{roto"})
	with pytest.raises(ErrorFormato, match="JSON válido"):
		cargar_paquete(ruta)
	_zip_con(ruta, {"manifiesto.json": '{"formato": 1}', "entorno.json": "[]"})
	with pytest.raises(ErrorFormato, match="estructura"):
		cargar_paquete(ruta)


@pytest.mark.parametrize(
	"nombre",
	[
		"../fuera.txt",
		"sonidos/../../fuera.wav",
		"/etc/passwd",
		"C:/Windows/system.ini",
		"sonidos\\..\\fuera.wav",
		"sonidos/nul.wav",
		"sonidos/a.wav ",
		"sonidos/programa.exe",
		"sonidos/guion.py",
		"codigo/malo.json",
		"imagenes/dibujo.svg",
		"suelto.txt",
		"actividades/sub/a.json",
		"actividades/a.txt",
	],
)
def test_cargar_rechaza_nombres_peligrosos_y_tipos_no_admitidos(tmp_path, nombre):
	ruta = tmp_path / "malo.elab"
	_zip_con(ruta, {**_basico(), nombre: "x"})
	with pytest.raises(ErrorFormato):
		cargar_paquete(ruta)


def test_cargar_rechaza_ficheros_demasiado_grandes(tmp_path, monkeypatch):
	ruta = tmp_path / "gordo.elab"
	_zip_con(ruta, {**_basico(), "sonidos/largo.wav": b"0" * 5000})
	assert cargar_paquete(ruta).recurso("largo.wav")
	monkeypatch.setattr(fo, "MAX_BYTES_RECURSO", 1000)
	with pytest.raises(ErrorFormato, match="demasiado grande"):
		cargar_paquete(ruta)
	monkeypatch.setattr(fo, "MAX_BYTES_RECURSO", 10**9)
	monkeypatch.setattr(fo, "MAX_BYTES_JSON", 10)
	with pytest.raises(ErrorFormato, match="demasiado grande"):
		cargar_paquete(ruta)


def test_cargar_rechaza_demasiadas_entradas_duplicados_y_total(tmp_path):
	ruta = tmp_path / "muchos.elab"
	_zip_con(ruta, {**_basico(), **{f"sonidos/s{i}.wav": b"x" for i in range(5)}})
	with zipfile.ZipFile(ruta) as archivo:
		with pytest.raises(ErrorFormato, match="demasiados ficheros"):
			fo.comprobar_zip(archivo, lambda _n: True, max_entradas=3)
		with pytest.raises(ErrorFormato, match="demasiado grande"):
			fo.comprobar_zip(archivo, lambda _n: True, max_total=10)
		assert len(fo.comprobar_zip(archivo, lambda _n: True)) == 7
	with pytest.warns(UserWarning), zipfile.ZipFile(ruta, "w") as archivo:
		for nombre, contenido in _basico().items():
			archivo.writestr(nombre, contenido)
		archivo.writestr("sonidos/a.wav", b"1")
		archivo.writestr("sonidos/A.wav", b"2")
		archivo.writestr("sonidos/a.wav", b"3")
	with pytest.raises(ErrorFormato, match="dos veces"):
		cargar_paquete(ruta)


def test_leer_entrada_no_se_fia_del_tamano(tmp_path):
	ruta = tmp_path / "x.zip"
	_zip_con(ruta, {"a.json": "0123456789"})
	with zipfile.ZipFile(ruta) as archivo:
		entrada = archivo.getinfo("a.json")
		assert fo.leer_entrada(archivo, entrada, 100) == b"0123456789"
		with pytest.raises(ErrorFormato, match="más grande"):
			fo.leer_entrada(archivo, entrada, 5)


def test_nombres_internos_seguros():
	assert fo.nombre_interno_seguro("sonidos/timbre.ogg")
	assert fo.nombre_interno_seguro("manifiesto.json")
	for malo in (
		"",
		"..",
		"a/../b",
		"/a",
		"a\\b",
		"c:/a",
		"a//b",
		"a/./b",
		"con.txt",
		"sonidos/COM1.wav",
		"a\x00b",
		"fin.",
		"x" * 300,
		"a?b.wav",
	):
		assert not fo.nombre_interno_seguro(malo), malo
	assert fo.identificador_seguro("Mi Entorno ñ 2!") == "mi-entorno-2"
	assert fo.identificador_seguro("", "reserva") == "reserva"
	assert fo.identificador_seguro("../../x") == "x"


def test_actividades_se_cargan_sin_interpretar(tmp_path):
	ruta = tmp_path / "x.elab"
	rara = {"id": "rara", "tipo": "tipo_que_aun_no_existe", "cualquier": {"cosa": [1, 2, 3]}}
	_zip_con(ruta, {**_basico(), "actividades/rara.json": json.dumps(rara), "actividades/sin-id.json": "{}"})
	paquete = cargar_paquete(ruta)
	assert paquete.actividad("rara") == rara
	# Sin id toma el del nombre del fichero.
	assert paquete.actividad("sin-id") == {"id": "sin-id"}
	_zip_con(ruta, {**_basico(), "actividades/lista.json": "[]"})
	with pytest.raises(ErrorFormato, match="actividad"):
		cargar_paquete(ruta)


def test_migrar_formato_antiguo():
	antiguo = {
		"nombre": "Viejo",
		"inicio": ["p", 1, 2, 90],
		"plantas": [{"id": "p", "habitaciones": [{"id": "h", "nombre": "Sala", "contorno": [[0, 0], [1, 0], [1, 1]]}]}],
	}
	nuevo = migrar(antiguo)
	assert nuevo["formato"] == FORMATO_ACTUAL
	assert "formato" not in antiguo
	entorno = Entorno.de_dict(nuevo)
	assert entorno.plantas[0].espacios[0].nombre == "Sala"
	assert entorno.inicio.planta == "p"
	assert entorno.inicio.rumbo == 90
	# El formato actual pasa sin cambios.
	actual = piso_minimo()[0].a_dict()
	assert migrar(actual) == actual


def test_migrar_rechaza_formatos_mas_nuevos_o_absurdos():
	with pytest.raises(ErrorFormato, match="más nueva"):
		migrar({"formato": FORMATO_ACTUAL + 1})
	with pytest.raises(ErrorFormato, match="no es válido"):
		migrar({"formato": "uno"})
	with pytest.raises(ErrorFormato, match="no es válido"):
		migrar({"formato": -3})
	with pytest.raises(ErrorFormato, match="estructura"):
		migrar([1, 2, 3])


def test_cargar_paquete_de_formato_antiguo_y_de_formato_futuro(tmp_path):
	ruta = tmp_path / "viejo.elab"
	_zip_con(
		ruta,
		{
			"manifiesto.json": json.dumps({"aplicacion": "EntornoLab", "id": "viejo", "nombre": "Entorno viejo"}),
			"entorno.json": json.dumps({"plantas": [{"id": "p", "habitaciones": [{"id": "h", "nombre": "Sala"}]}]}),
		},
	)
	paquete = cargar_paquete(ruta)
	assert paquete.entorno.formato == FORMATO_ACTUAL
	assert paquete.entorno.id == "viejo"
	assert paquete.entorno.nombre == "Entorno viejo"
	assert paquete.entorno.plantas[0].espacios[0].nombre == "Sala"
	_zip_con(ruta, {"manifiesto.json": json.dumps({"formato": 99}), "entorno.json": "{}"})
	with pytest.raises(ErrorFormato, match="más nueva"):
		cargar_paquete(ruta)
	_zip_con(ruta, {"manifiesto.json": json.dumps({"formato": 1}), "entorno.json": json.dumps({"formato": 99})})
	with pytest.raises(ErrorFormato, match="más nueva"):
		cargar_paquete(ruta)


def test_leer_manifiesto_sin_abrir_el_entorno(tmp_path):
	ruta = tmp_path / "piso.elab"
	guardar_paquete(ruta, piso_minimo()[0])
	manifiesto = fo.leer_manifiesto(ruta)
	assert manifiesto["nombre"] == "Piso mínimo"
	assert manifiesto["id"] == "piso-m-nimo"


def test_json_con_marca_de_orden_de_bytes(tmp_path):
	ruta = tmp_path / "bom.elab"
	basico = _basico()
	_zip_con(ruta, {"manifiesto.json": b"\xef\xbb\xbf" + basico["manifiesto.json"].encode(), "entorno.json": basico["entorno.json"]})
	assert cargar_paquete(ruta).entorno.nombre == "Piso mínimo"
