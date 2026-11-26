"""Pruebas del catálogo de complementos: carga, búsqueda, huellas, ajuste a escala, instalación y comprobación."""

from __future__ import annotations

import copy
import json
import zipfile

import pytest

from app.core import i18n
from app.dominio import catalogo as ca
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo, ErrorComplemento, instalar_complemento, validar_complemento
from app.dominio.formato import ErrorFormato
from app.dominio.modelo import Objeto
from tests.test_dominio_comun import FICHA_PRUEBA, catalogo_de_prueba, escribir_complemento


def _ficha(**cambios) -> dict:
	ficha = copy.deepcopy(FICHA_PRUEBA)
	ficha.update(cambios)
	return ficha


def _elabc(ruta, ficha: dict, extra: dict[str, bytes] | None = None, prefijo: str = "") -> None:
	with zipfile.ZipFile(ruta, "w") as archivo:
		archivo.writestr(prefijo + "complemento.json", json.dumps(ficha, ensure_ascii=False))
		for nombre, contenido in (extra or {}).items():
			archivo.writestr(prefijo + nombre, contenido)


def test_cargar_catalogo_de_una_carpeta(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	assert [c.id for c in catalogo.complementos()] == ["prueba"]
	complemento = catalogo.complemento("prueba")
	assert complemento.nombre == "Complemento de prueba"
	assert complemento.version == "1.0"
	assert complemento.licencia == "CC0"
	assert complemento.carpeta == tmp_path / "plugins" / "prueba"
	assert not catalogo.vacio
	assert catalogo.avisos == []
	cama = catalogo.objeto("prueba/cama")
	assert cama.tipo == "prueba/cama"
	assert cama.rango("ancho") == (0.8, 1.5, 2.0)
	assert [v.id for v in cama.variantes] == ["individual", "matrimonio"]
	assert cama.variante("individual").ancho == 0.9
	assert cama.contenedor
	assert cama.letra() == "C"
	assert cama.color() == "#8B5A2B"
	assert catalogo.objeto("prueba/no-existe") is None
	assert catalogo.objeto("otro/cama") is None
	assert catalogo.objeto("caja") is None
	assert catalogo.nombre_categoria("salon") == "Salón"
	assert catalogo.nombre_categoria("otra") == "otra"


def test_cargar_sin_carpeta_usa_data_plugins_y_puede_estar_vacio(datos_temporales):
	catalogo = Catalogo.cargar()
	assert catalogo.vacio
	assert catalogo.complementos() == []
	assert (datos_temporales / "plugins").is_dir()
	escribir_complemento(datos_temporales / "plugins")
	assert not Catalogo.cargar().vacio
	assert Catalogo.cargar(datos_temporales / "no-existe").vacio


def test_varias_carpetas_y_complementos_repetidos_o_rotos(tmp_path):
	escribir_complemento(tmp_path / "a")
	escribir_complemento(tmp_path / "b")
	escribir_complemento(tmp_path / "b", _ficha(id="otro", nombre="Otro"))
	rota = tmp_path / "b" / "rota"
	rota.mkdir()
	(rota / "complemento.json").write_text("{esto no es json", encoding="utf-8")
	(tmp_path / "b" / "vacia").mkdir()
	catalogo = Catalogo.cargar([tmp_path / "a", tmp_path / "b"])
	assert sorted(c.id for c in catalogo.complementos()) == ["otro", "prueba"]
	codigos = sorted(a.codigo for a in catalogo.avisos)
	assert codigos == ["complemento_no_valido", "complemento_no_valido", "complemento_repetido"]
	assert all(a.mensaje and a.sugerencia for a in catalogo.avisos)


def test_objeto_mal_definido_no_tira_el_complemento(tmp_path):
	ficha = _ficha()
	ficha["objetos"] = ficha["objetos"][:2] + [
		{"id": "Mal Id", "nombre": "x"},
		{"id": "medidas_raras", "medidas": {"ancho": [2, 1, 3]}},
		{"id": "forma_rara", "forma": {"tipo": "hexagono"}},
		{"id": "poligono_vacio", "forma": {"tipo": "poligono"}},
		{"id": "puntos_fuera", "forma": {"tipo": "poligono", "puntos": [[0, 0], [2, 0], [0, 1]]}},
		{"id": "cama", "nombre": "Cama repetida"},
		"no soy un objeto",
	]
	escribir_complemento(tmp_path, ficha)
	catalogo = Catalogo.cargar(tmp_path)
	assert [d.id for d in catalogo.objetos()] == ["cama", "mesilla"]
	assert [a.codigo for a in catalogo.avisos].count("objeto_no_valido") == 6
	assert [a.codigo for a in catalogo.avisos].count("objeto_repetido") == 1
	assert all(a.es_error for a in catalogo.avisos)


def test_ficha_general_no_valida(tmp_path):
	for ficha, texto in (
		(_ficha(id="Con Espacios"), "identificador"),
		(_ficha(formato=99), "más nuevo"),
		(_ficha(formato="x"), "formato"),
	):
		carpeta = tmp_path / "caso"
		carpeta.mkdir(exist_ok=True)
		(carpeta / "complemento.json").write_text(json.dumps(ficha), encoding="utf-8")
		with pytest.raises(ErrorComplemento, match=texto):
			ca.leer_complemento(carpeta)
	with pytest.raises(ErrorComplemento, match="falta"):
		ca.leer_complemento(tmp_path / "no-existe")
	(tmp_path / "caso" / "complemento.json").write_text("[]", encoding="utf-8")
	with pytest.raises(ErrorComplemento, match="estructura"):
		ca.leer_complemento(tmp_path / "caso")
	assert issubclass(ErrorComplemento, ErrorFormato)


def test_buscar_por_texto_categoria_ambito_y_colocacion(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	assert [d.id for d in catalogo.buscar("sofa")] == ["sofa", "rinconera"]
	assert [d.id for d in catalogo.buscar("SOFÁ rinconera")] == ["rinconera"]
	assert [d.id for d in catalogo.buscar("nevera")] == ["frigorifico"]
	assert [d.id for d in catalogo.buscar("frigorífico")] == ["frigorifico"]
	assert catalogo.buscar("unicornio") == []
	assert {d.id for d in catalogo.buscar(categoria="bano")} == {"inodoro", "lavabo"}
	assert {d.id for d in catalogo.buscar(ambito="exterior")} == {"banco", "jardinera"}
	assert {d.id for d in catalogo.buscar(colocacion="esquina")} == {"rinconera"}
	assert [d.id for d in catalogo.buscar("mesa", categoria="salon", colocacion="pared")] == ["mesa_redonda"]
	assert len(catalogo.buscar()) == len(FICHA_PRUEBA["objetos"])
	nombres = [d.nombre for d in catalogo.buscar()]
	assert nombres == sorted(nombres, key=ca.sin_acentos)
	assert catalogo.categorias() == ["aula", "bano", "calle", "cocina", "dormitorio", "oficina", "salon"]


def test_activar_y_desactivar_sin_perder_los_objetos_colocados(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	cama = catalogo.crear_objeto("prueba/cama", 0, 0)
	assert catalogo.activar("prueba", False)
	assert catalogo.buscar("cama") == []
	assert catalogo.vacio
	# Lo ya colocado sigue teniendo su forma y sus reglas.
	assert catalogo.definicion_de(cama) is not None
	assert catalogo.activar("prueba")
	assert catalogo.buscar("cama")
	assert not catalogo.activar("no-existe")
	assert Catalogo.cargar(tmp_path / "plugins", desactivados=["prueba"]).vacio
	assert catalogo.quitar("prueba")
	assert not catalogo.quitar("prueba")
	assert catalogo.objeto("prueba/cama") is None


def test_crear_objeto_con_medidas_por_defecto_y_variantes(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	cama = catalogo.crear_objeto("prueba/cama", 2, 3, 450)
	assert (cama.tipo, cama.nombre, cama.x, cama.y, cama.rumbo) == ("prueba/cama", "Cama", 2.0, 3.0, 90.0)
	assert (cama.ancho, cama.fondo, cama.alto) == (1.5, 2.0, 0.5)
	assert cama.id == ""
	assert cama.variante == ""
	individual = catalogo.crear_objeto("prueba/cama", 0, 0, variante="individual")
	assert (individual.ancho, individual.fondo, individual.variante) == (0.9, 1.9, "individual")
	assert catalogo.crear_objeto("prueba/armario", 0, 0).estado == "cerrado"
	with pytest.raises(KeyError):
		catalogo.crear_objeto("prueba/no-existe", 0, 0)
	with pytest.raises(KeyError):
		catalogo.crear_objeto("prueba/cama", 0, 0, variante="gigante")


def test_ajustar_a_hueco_elige_defecto_variante_o_escala(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	cama = catalogo.objeto("prueba/cama")
	# Cabe con sus medidas por defecto.
	assert catalogo.ajustar_a_hueco(cama, 3.0, 3.0) == (1.5, 2.0)
	# No cabe la de defecto: la variante MAYOR que quepa (la individual).
	assert catalogo.ajustar_a_hueco(cama, 1.2, 2.5) == (0.9, 1.9)
	# Ninguna variante cabe: se escala dentro del rango.
	assert catalogo.ajustar_a_hueco(cama, 0.85, 1.85) == (0.85, 1.85)
	assert catalogo.ajustar_a_hueco(cama, 1.4, 1.85) == (1.4, 1.85)
	# Ni al mínimo: no se coloca.
	assert catalogo.ajustar_a_hueco(cama, 0.7, 3.0) is None
	assert catalogo.ajustar_a_hueco(cama, 3.0, 1.7) is None
	mesa = catalogo.objeto("prueba/mesa")
	assert catalogo.ajustar_a_hueco(mesa, 1.0, 5.0) == (1.0, 0.8)
	assert catalogo.ajustar_a_hueco(mesa, 0.8, 0.6) == (0.8, 0.6)
	assert catalogo.ajustar_a_hueco(mesa, 0.79, 0.6) is None


def test_ajustar_a_hueco_nunca_supera_el_hueco_ni_sale_del_rango(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	for definicion in catalogo.objetos():
		for ancho_libre in (0.2, 0.5, 0.9, 1.3, 2.2, 5.0):
			for fondo_libre in (0.2, 0.5, 0.9, 1.3, 2.2, 5.0):
				ajuste = catalogo.ajustar_a_hueco(definicion, ancho_libre, fondo_libre)
				if ajuste is None:
					continue
				assert ajuste[0] <= ancho_libre + 1e-6
				assert ajuste[1] <= fondo_libre + 1e-6
				assert definicion.rango("ancho")[0] - 1e-6 <= ajuste[0] <= definicion.rango("ancho")[2] + 1e-6
				assert definicion.rango("fondo")[0] - 1e-6 <= ajuste[1] <= definicion.rango("fondo")[2] + 1e-6


def test_ajustar_objeto_cambia_medidas_y_variante(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	cama = catalogo.crear_objeto("prueba/cama", 0, 0)
	assert catalogo.ajustar_objeto(cama, 1.2, 2.5)
	assert (cama.ancho, cama.fondo, cama.variante) == (0.9, 1.9, "individual")
	intacta = catalogo.crear_objeto("prueba/cama", 0, 0)
	assert not catalogo.ajustar_objeto(intacta, 0.5, 0.5)
	assert (intacta.ancho, intacta.fondo) == (1.5, 2.0)
	pedida = catalogo.crear_objeto("prueba/cama", 0, 0, variante="individual")
	assert catalogo.ajustar_objeto(pedida, 5, 5)
	assert pedida.variante == "individual"
	caja = Objeto(tipo="falta/x", ancho=1.0, fondo=1.0)
	assert catalogo.ajustar_objeto(caja, 1.0, 2.0)
	assert not catalogo.ajustar_objeto(caja, 0.9, 2.0)


def test_huella_rectangular_con_rumbo(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	cama = catalogo.crear_objeto("prueba/cama", 10, 10, 0)
	assert geo.caja(catalogo.huella(cama)) == pytest.approx((9.25, 9.0, 10.75, 11.0))
	cama.rumbo = 90
	assert geo.caja(catalogo.huella(cama)) == pytest.approx((9.0, 9.25, 11.0, 10.75))
	cama.rumbo = 45
	assert geo.area(catalogo.huella(cama)) == pytest.approx(3.0)
	assert geo.es_antihorario(catalogo.huella(cama))


def test_huella_de_circulo_ele_y_poligono(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	redonda = catalogo.crear_objeto("prueba/mesa_redonda", 0, 0)
	huella = catalogo.huella(redonda)
	assert len(huella) == ca.LADOS_CIRCULO
	assert geo.area(huella) == pytest.approx(3.14159 * 0.25, rel=0.03)
	assert all(geo.distancia(p, (0, 0)) == pytest.approx(0.5) for p in huella)
	rinconera = catalogo.crear_objeto("prueba/rinconera", 0, 0)
	ele = catalogo.huella(rinconera)
	assert len(ele) == 6
	assert geo.area(ele) == pytest.approx(2.4 * 2.0 * 0.75)
	assert geo.caja(ele) == pytest.approx((-1.2, -1.0, 1.2, 1.0))
	# La esquina delantera derecha de la ele está vacía.
	assert not geo.punto_en_poligono((0.9, 0.8), ele)
	assert geo.punto_en_poligono((-0.9, 0.8), ele)
	jardinera = catalogo.crear_objeto("prueba/jardinera", 5, 5, 180)
	triangulo = catalogo.huella(jardinera)
	assert len(triangulo) == 3
	assert geo.area(triangulo) == pytest.approx(0.5)
	# Girada media vuelta, el ángulo recto pasa de la esquina suroeste a la noreste.
	assert any(p == pytest.approx((5.5, 5.5)) for p in triangulo)


def test_tipo_desconocido_se_conserva_como_caja(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	perdido = Objeto(id="o", nombre="Vitrina", tipo="museo/vitrina", x=1, y=1, rumbo=90, ancho=2.0, fondo=0.5, alto=1.5)
	assert catalogo.es_caja(perdido)
	assert catalogo.definicion_de(perdido) is None
	assert geo.caja(catalogo.huella(perdido)) == pytest.approx((0.75, 0, 1.25, 2))
	assert catalogo.bloquea(perdido)
	assert catalogo.material(perdido) == "madera"
	assert catalogo.tipos_que_faltan([perdido, Objeto(tipo="caja"), catalogo.crear_objeto("prueba/cama", 0, 0)]) == ["museo/vitrina"]
	assert Catalogo().huella(perdido) == perdido.huella_caja()


def test_bloquea_y_material_con_sobrescrituras(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	alfombra = catalogo.crear_objeto("prueba/alfombra", 0, 0)
	mesa = catalogo.crear_objeto("prueba/mesa", 0, 0)
	assert not catalogo.bloquea(alfombra)
	assert catalogo.bloquea(mesa)
	mesa.datos["bloquea"] = False
	mesa.datos["material"] = "cristal"
	assert not catalogo.bloquea(mesa)
	assert catalogo.material(mesa) == "cristal"
	assert catalogo.objeto("prueba/lampara").altura_base == 1.9
	assert not catalogo.objeto("prueba/lampara").detectable_baston
	assert catalogo.objeto("prueba/frigorifico").sonidos["propio"]["sonido"] == "frigorifico"
	assert catalogo.objeto("prueba/armario").acciones[0]["a"] == "abierto"


def test_traducciones_del_complemento(tmp_path):
	ingles = {
		"nombre": "Test add-on",
		"descripcion": "Furniture for tests.",
		"categorias": {"salon": "Living room"},
		"objetos": {
			"cama": {"nombre": "Bed", "descripcion": "A test bed.", "etiquetas": ["bed"], "variantes": {"individual": "Single"}},
			"armario": {"nombre": "Wardrobe", "acciones": {"abrir": "Open"}},
		},
	}
	escribir_complemento(tmp_path, traducciones={"en": ingles})
	espanol = Catalogo.cargar(tmp_path, idioma="es")
	assert espanol.objeto("prueba/cama").nombre == "Cama"
	traducido = Catalogo.cargar(tmp_path, idioma="en")
	cama = traducido.objeto("prueba/cama")
	assert cama.nombre == "Bed"
	assert cama.descripcion == "A test bed."
	assert cama.variante("individual").nombre == "Single"
	assert cama.variante("matrimonio").nombre == "De matrimonio"
	assert traducido.objeto("prueba/armario").acciones[0]["nombre"] == "Open"
	assert traducido.complemento("prueba").nombre == "Test add-on"
	assert traducido.nombre_categoria("salon") == "Living room"
	# Se puede buscar en los dos idiomas.
	assert [d.id for d in traducido.buscar("bed")] == ["cama"]
	assert [d.id for d in traducido.buscar("cama")] == ["cama"]
	# Una variante regional cae en el idioma base; un idioma sin fichero deja el español.
	assert Catalogo.cargar(tmp_path, idioma="en_GB").objeto("prueba/cama").nombre == "Bed"
	assert Catalogo.cargar(tmp_path, idioma="fr").objeto("prueba/cama").nombre == "Cama"
	# Por defecto usa el idioma activo de la aplicación.
	assert i18n.idioma_actual() == "es"
	assert Catalogo.cargar(tmp_path).objeto("prueba/cama").nombre == "Cama"


def test_instalar_complemento_desde_zip(tmp_path, datos_temporales):
	paquete = tmp_path / "prueba.elabc"
	_elabc(
		paquete, FICHA_PRUEBA, {"sonidos/zumbido.ogg": b"Ogg", "imagenes/cama.png": b"PNG", "locales/en.json": b"{}", "LEEME.txt": b"hola"}
	)
	assert instalar_complemento(paquete) == "prueba"
	instalado = datos_temporales / "plugins" / "prueba"
	assert (instalado / "complemento.json").is_file()
	assert (instalado / "sonidos" / "zumbido.ogg").read_bytes() == b"Ogg"
	assert (instalado / "LEEME.txt").is_file()
	assert not (datos_temporales / "plugins" / ".prueba.nuevo").exists()
	catalogo = Catalogo.cargar()
	assert catalogo.objeto("prueba/cama") is not None
	assert catalogo.complemento("prueba").ruta_recurso("zumbido.ogg") == instalado / "sonidos" / "zumbido.ogg"
	assert catalogo.complemento("prueba").ruta_recurso("imagenes/cama.png") is not None
	assert catalogo.complemento("prueba").ruta_recurso("../../config/config.json") is None
	assert catalogo.complemento("prueba").ruta_recurso("no.ogg") is None


def test_instalar_con_carpeta_envolvente_y_sustituir_version(tmp_path):
	destino = tmp_path / "plugins"
	paquete = tmp_path / "v1.elabc"
	_elabc(paquete, FICHA_PRUEBA, {"sonidos/viejo.ogg": b"1"}, prefijo="prueba-1.0/")
	assert instalar_complemento(paquete, destino) == "prueba"
	assert (destino / "prueba" / "sonidos" / "viejo.ogg").is_file()
	nueva = _ficha(version="2.0")
	_elabc(paquete, nueva)
	assert instalar_complemento(paquete, destino) == "prueba"
	assert Catalogo.cargar(destino).complemento("prueba").version == "2.0"
	# La versión anterior desaparece entera: no quedan ficheros huérfanos.
	assert not (destino / "prueba" / "sonidos").exists()


@pytest.mark.parametrize(
	"extra",
	[
		{"../fuera.txt": b"x"},
		{"sonidos/../../fuera.ogg": b"x"},
		{"programa.exe": b"MZ"},
		{"sonidos/guion.py": b"print(1)"},
		{"otra/carpeta.json": b"{}"},
		{"imagenes/dibujo.svg": b"<svg/>"},
		{"sonidos/sub/a.ogg": b"x"},
	],
)
def test_instalar_rechaza_contenido_peligroso_sin_dejar_restos(tmp_path, extra):
	destino = tmp_path / "plugins"
	paquete = tmp_path / "malo.elabc"
	_elabc(paquete, FICHA_PRUEBA, extra)
	with pytest.raises(ErrorComplemento):
		instalar_complemento(paquete, destino)
	assert not (destino / "prueba").exists()
	assert not (tmp_path / "fuera.txt").exists()
	assert not (tmp_path / "fuera.ogg").exists()


def test_instalar_rechaza_zips_que_no_son_complementos(tmp_path):
	destino = tmp_path / "plugins"
	with pytest.raises(ErrorComplemento, match="No existe"):
		instalar_complemento(tmp_path / "nada.elabc", destino)
	basura = tmp_path / "basura.elabc"
	basura.write_bytes(b"no soy un zip")
	with pytest.raises(ErrorComplemento, match="no es un complemento"):
		instalar_complemento(basura, destino)
	with zipfile.ZipFile(basura, "w") as archivo:
		archivo.writestr("otra-cosa.txt", "x")
	with pytest.raises(ErrorComplemento, match="falta"):
		instalar_complemento(basura, destino)
	_elabc(basura, _ficha(id="../../malo"))
	with pytest.raises(ErrorComplemento, match="identificador"):
		instalar_complemento(basura, destino)
	_elabc(basura, _ficha(objetos=[]))
	with pytest.raises(ErrorComplemento, match="ningún objeto"):
		instalar_complemento(basura, destino)
	with zipfile.ZipFile(basura, "w") as archivo:
		archivo.writestr("complemento.json", "{roto")
	with pytest.raises(ErrorComplemento, match="JSON"):
		instalar_complemento(basura, destino)
	assert not destino.exists() or list(destino.iterdir()) == []


def test_instalar_no_destruye_la_version_instalada_si_la_nueva_es_mala(tmp_path):
	destino = tmp_path / "plugins"
	escribir_complemento(destino)
	malo = tmp_path / "malo.elabc"
	_elabc(malo, _ficha(objetos=[{"id": "Mal Id"}]))
	with pytest.raises(ErrorComplemento):
		instalar_complemento(malo, destino)
	assert Catalogo.cargar(destino).objeto("prueba/cama") is not None


def test_empaquetar_e_instalar_de_vuelta(tmp_path):
	carpeta = escribir_complemento(tmp_path / "origen")
	(carpeta / "sonidos").mkdir()
	(carpeta / "sonidos" / "a.wav").write_bytes(b"RIFF")
	(carpeta / "notas.docx").write_bytes(b"no debe viajar")
	paquete = ca.empaquetar_complemento(carpeta, tmp_path / "prueba.elabc")
	with zipfile.ZipFile(paquete) as archivo:
		assert sorted(archivo.namelist()) == ["complemento.json", "sonidos/a.wav"]
	assert instalar_complemento(paquete, tmp_path / "destino") == "prueba"
	with pytest.raises(ErrorComplemento):
		ca.empaquetar_complemento(tmp_path / "no-existe", tmp_path / "x.elabc")


def test_validar_complemento_correcto(tmp_path):
	carpeta = escribir_complemento(tmp_path)
	assert validar_complemento(carpeta) == []


def test_validar_complemento_detecta_problemas(tmp_path):
	ficha = _ficha(autor="", licencia="")
	objetos = ficha["objetos"]
	objetos[0]["variantes"].append({"id": "enorme", "nombre": "Enorme", "ancho": 5.0, "fondo": 2.0, "alto": 0.5})
	objetos[1]["categoria"] = ""
	objetos[1]["descripcion"] = ""
	objetos[2]["acciones"].append({"id": "romper", "nombre": "Romper", "de": "cerrado", "a": "roto"})
	objetos[3]["sonidos"] = {"golpe": "sonidos/no-esta.ogg", "uso": "nombre_de_serie"}
	objetos[4]["imagen"] = {"fichero": "imagenes/falta.png", "descripcion": ""}
	objetos[5]["simbolo"] = {"letra": "S", "color": "rojo"}
	objetos[6]["ambito"] = ["interior", "submarino"]
	del objetos[7]["medidas"]["alto"]
	carpeta = escribir_complemento(tmp_path / "otra-carpeta", ficha, traducciones={"en": {"objetos": {"fantasma": {"nombre": "Ghost"}}}})
	(carpeta / "locales" / "fr.json").write_text("{roto", encoding="utf-8")
	destino = tmp_path / "otra-carpeta" / "renombrada"
	carpeta.rename(destino)
	avisos = validar_complemento(destino)
	codigos = {a.codigo for a in avisos}
	assert codigos == {
		"carpeta_distinta",
		"ficha_incompleta",
		"variante_fuera_de_rango",
		"sin_categoria",
		"sin_descripcion",
		"estado_desconocido",
		"sonido_ausente",
		"imagen_ausente",
		"imagen_sin_descripcion",
		"color_no_valido",
		"valor_desconocido",
		"medida_ausente",
		"traduccion_sobrante",
		"traduccion_no_valida",
	}
	assert [a.codigo for a in avisos].count("ficha_incompleta") == 2
	assert [a.codigo for a in avisos].count("sonido_ausente") == 1
	assert all(a.mensaje and a.sugerencia and a.gravedad in ("error", "aviso") for a in avisos)
	assert next(a for a in avisos if a.codigo == "variante_fuera_de_rango").elemento_id == "prueba/cama"


def test_validar_complemento_ilegible(tmp_path):
	avisos = validar_complemento(tmp_path / "no-existe")
	assert [a.codigo for a in avisos] == ["complemento_no_valido"]
	assert avisos[0].es_error
	carpeta = tmp_path / "vacio"
	carpeta.mkdir()
	(carpeta / "complemento.json").write_text(json.dumps({"id": "vacio", "nombre": "Vacío"}), encoding="utf-8")
	assert "complemento_sin_objetos" in {a.codigo for a in validar_complemento(carpeta)}


def test_medidas_fijas_y_valores_de_serie(tmp_path):
	ficha = _ficha(objetos=[{"id": "poste", "medidas": {"ancho": 0.2, "fondo": 0.2, "alto": 3}}, {"id": "minimo"}])
	escribir_complemento(tmp_path, ficha)
	catalogo = Catalogo.cargar(tmp_path)
	poste = catalogo.objeto("prueba/poste")
	assert poste.rango("ancho") == (0.2, 0.2, 0.2)
	assert catalogo.ajustar_a_hueco(poste, 0.19, 1) is None
	minimo = catalogo.objeto("prueba/minimo")
	assert minimo.nombre == "minimo"
	assert minimo.forma == {"tipo": "rectangulo"}
	assert minimo.ambito == ["interior"]
	assert minimo.bloquea
	assert minimo.letra() == "M"
	assert minimo.color() == "#808080"
	creado = catalogo.crear_objeto("prueba/minimo", 0, 0)
	assert (creado.ancho, creado.fondo, creado.alto) == (1.0, 1.0, 1.0)
