"""Pruebas del modelo del entorno: conversión a diccionario, ids, búsquedas y paredes derivadas."""

from __future__ import annotations

import json

import pytest

from app.dominio import edicion as ed
from app.dominio import modelo as mo
from app.dominio.modelo import (
	Abertura,
	Aviso,
	Conector,
	Entorno,
	Espacio,
	FuenteSonido,
	Objeto,
	Parada,
	Pared,
	Planta,
	Posicion,
	Referencia,
	Tramo,
	Via,
	ZonaSuelo,
	segmentos_opacos,
	segmentos_solidos,
)
from tests.test_dominio_comun import catalogo_de_prueba, piso_minimo


def entorno_completo() -> Entorno:
	"""Un entorno con un elemento de cada clase, escrito a mano."""
	planta = Planta(
		id="pla-1",
		nombre="Baja",
		espacios=[Espacio(id="esp-1", nombre="Sala", contorno=[(0, 0), (4, 0), (4, 3), (0, 3)], datos={"uso": "salon"})],
		paredes=[Pared(id="par-1", nombre="Tabique", a=(1, 1), b=(2, 1))],
		aberturas=[Abertura(id="abe-1", nombre="Puerta", a=(1, 0), b=(1.82, 0), estado="abierta", es_salida=True)],
		objetos=[
			Objeto(id="obj-1", nombre="Mesa", tipo="hogar/mesa", x=2, y=2, rumbo=90, ancho=1.2, fondo=0.8, alto=0.75, datos={"k": [1, 2]})
		],
		fuentes=[FuenteSonido(id="fue-1", nombre="Reloj", x=0.2, y=1.5, sonido="reloj", bucle=False, intervalo=1.0)],
		zonas=[ZonaSuelo(id="zon-1", nombre="Alfombra", contorno=[(1, 1), (2, 1), (2, 2)], suelo="alfombra")],
		referencias=[Referencia(id="ref-1", nombre="Felpudo", x=1.4, y=0.3, tipo="tactil", permanente=False)],
		vias=[Via(id="via-1", nombre="Calle", eje=[(0, -5), (10, -5)], ancho=7, carriles=2, sentido="ida", trafico=3, velocidad_kmh=50)],
	)
	arriba = Planta(id="pla-2", nombre="Primera", nivel=1, altura_m=3.0)
	escalera = Conector(
		id="con-1",
		nombre="Escalera",
		tipo="escalera",
		tramos=[Tramo(desde=Posicion("pla-1", 3, 1, 0), hasta=Posicion("pla-2", 3, 2.5, 180), longitud_m=4.0, peldanos=16)],
		datos={"pasamanos": "ambos"},
	)
	ascensor = Conector(
		id="con-2",
		nombre="Ascensor",
		tipo="ascensor",
		paradas=[Parada("pla-1", Posicion("pla-1", 0.5, 2.5, 270)), Parada("pla-2", Posicion("pla-2", 0.5, 2.5, 270))],
	)
	return Entorno(
		id="prueba",
		nombre="Prueba",
		descripcion="Para las pruebas",
		autor="Yo",
		procedencia={"fuente": "inventado"},
		georef={"lat0": 40.0, "lon0": -3.0},
		inicio=Posicion("pla-1", 2, 1.5, 45),
		plantas=[planta, arriba],
		conectores=[escalera, ascensor],
		complementos=["hogar"],
	)


def test_ida_y_vuelta_por_diccionario_y_json():
	entorno = entorno_completo()
	datos = entorno.a_dict()
	# Tiene que poder escribirse como JSON sin ayuda.
	texto = json.dumps(datos, ensure_ascii=False)
	reconstruido = Entorno.de_dict(json.loads(texto))
	assert reconstruido == entorno
	assert reconstruido.a_dict() == datos
	assert isinstance(reconstruido.plantas[0].espacios[0].contorno[0], tuple)
	assert reconstruido.plantas[0].aberturas[0].a == (1.0, 0.0)
	assert reconstruido.conectores[0].tramos[0].hasta.rumbo == 180
	assert reconstruido.georef == {"lat0": 40.0, "lon0": -3.0}


def test_de_dict_tolera_claves_que_faltan_y_que_sobran():
	espacio = Espacio.de_dict({"id": "e", "nombre": "Sala", "inventada": 123})
	assert espacio.id == "e"
	assert espacio.tipo == "habitacion"
	assert espacio.cerrado is True
	assert espacio.contorno == []
	assert Entorno.de_dict({}).formato == mo.FORMATO_ACTUAL
	assert Entorno.de_dict({"plantas": [{"id": "p"}]}).plantas[0].espacios == []


def test_de_dict_tolera_valores_del_tipo_equivocado(caplog):
	objeto = Objeto.de_dict({"id": "o", "x": "tres", "ancho": "1.5", "datos": "no es un diccionario", "nombre": None})
	assert objeto.x == 0.0
	assert objeto.ancho == 1.5
	assert objeto.datos == {}
	assert objeto.nombre == ""
	assert "Valor no válido" in caplog.text
	espacio = Espacio.de_dict({"contorno": [[0, 0], [1]], "cerrado": "quizá", "lados_abiertos": "x"})
	assert espacio.contorno == []
	assert espacio.cerrado is True
	assert Espacio.de_dict({"contorno": [[0, 0], [1, "nan"]]}).contorno == []
	assert Entorno.de_dict("esto no es un diccionario").plantas == []
	planta = Planta.de_dict({"espacios": [{"id": "a"}, "basura", 7], "nivel": "2"})
	assert [e.id for e in planta.espacios] == ["a"]
	assert planta.nivel == 2
	assert Entorno.de_dict({"inicio": [1, 2]}).inicio == Posicion()
	assert Entorno.de_dict({"georef": None}).georef is None


def test_a_dict_redondea_y_no_comparte_listas():
	espacio = Espacio(contorno=[(0.1 + 0.2, 0.0)])
	datos = espacio.a_dict()
	assert datos["contorno"] == [[0.3, 0.0]]
	datos["lados_abiertos"].append(3)
	assert espacio.lados_abiertos == []
	copia = espacio.copia()
	copia.contorno.append((9.0, 9.0))
	assert len(espacio.contorno) == 1


def test_listas_de_valores_con_nombre_visible():
	for tabla in (
		mo.TIPOS_ESPACIO,
		mo.SUELOS,
		mo.ACUSTICAS,
		mo.TIPOS_ABERTURA,
		mo.ESTADOS_ABERTURA,
		mo.HOJAS,
		mo.TIPOS_CONECTOR,
		mo.TIPOS_REFERENCIA,
	):
		assert tabla
		assert all(isinstance(nombre, str) and nombre for nombre in tabla.values())
	assert set(mo.SUELOS) >= {"baldosa", "asfalto", "tactil_botones", "tactil_rayas"}
	assert set(mo.ACUSTICAS) == {"seca", "habitacion", "sala_grande", "pasillo", "bano", "escalera", "nave", "exterior", "calle", "parque"}
	assert len(mo.TIPOS_ESPACIO) == 13
	assert mo.nombre_visible(mo.SUELOS, "hormigon") == "Hormigón"
	assert mo.nombre_visible(mo.SUELOS, "inventado") == "inventado"
	assert mo.nombre_visible(mo.NIVELES_TRAFICO, 3) == "Tráfico intenso"


def test_ids_unicos_estables_y_que_no_se_reutilizan():
	entorno = Entorno()
	primero = entorno.nuevo_id("esp")
	segundo = entorno.nuevo_id("esp")
	assert primero != segundo
	assert primero == "esp-1"
	# El contador viaja con el entorno: tras abrirlo de nuevo no repite.
	reabierto = Entorno.de_dict(entorno.a_dict())
	assert reabierto.nuevo_id("obj") == "obj-3"
	# Un entorno hecho a mano con ids altos no provoca choques.
	a_mano = entorno_completo()
	a_mano.plantas[0].espacios[0].id = "esp-40"
	assert a_mano.nuevo_id("esp") == "esp-41"
	assert a_mano.id_para(Objeto()).startswith("obj-")
	assert a_mano.id_para(Planta()).startswith("pla-")
	assert a_mano.id_para(Conector()).startswith("con-")


def test_busquedas():
	entorno = entorno_completo()
	planta = entorno.planta("pla-1")
	assert planta is entorno.plantas[0]
	assert entorno.planta("no-existe") is None
	assert entorno.planta_de_nivel(1).id == "pla-2"
	encontrada = entorno.buscar("obj-1")
	assert encontrada == (planta, planta.objetos[0])
	assert entorno.buscar("con-2") == (None, entorno.conectores[1])
	assert entorno.buscar("pla-2") == (entorno.plantas[1], entorno.plantas[1])
	assert entorno.buscar("nada") is None
	assert entorno.buscar("") is None
	assert entorno.elemento("ref-1").nombre == "Felpudo"
	assert entorno.planta_de(planta.aberturas[0]) is planta
	assert entorno.planta_de(Objeto()) is None
	elementos = list(entorno.elementos())
	assert len(elementos) == 10
	assert {type(e).__name__ for _p, e in elementos} == {
		"Espacio",
		"Pared",
		"Abertura",
		"Objeto",
		"FuenteSonido",
		"ZonaSuelo",
		"Referencia",
		"Via",
		"Conector",
	}
	assert sorted(entorno.ids())[:2] == ["abe-1", "con-1"]
	assert entorno.conectores[0].plantas() == ["pla-1", "pla-2"]
	assert len(entorno.conectores[1].posiciones()) == 2


def test_espacio_en_un_punto_elige_el_mas_concreto():
	planta = Planta(
		espacios=[
			Espacio(id="grande", contorno=[(0, 0), (10, 0), (10, 10), (0, 10)], cerrado=False),
			Espacio(id="chico", contorno=[(4, 4), (6, 4), (6, 6), (4, 6)], cerrado=False, macizo=True),
		]
	)
	assert planta.espacio_en(5, 5).id == "chico"
	assert planta.espacio_en(5, 5, incluir_macizos=False).id == "grande"
	assert planta.espacio_en(1, 1).id == "grande"
	assert planta.espacio_en(20, 20) is None
	assert [e.id for e in planta.espacios_en(5, 5)] == ["chico", "grande"]
	assert planta.caja() == (0, 0, 10, 10)
	assert planta.espacio("chico").area() == pytest.approx(4)
	assert planta.espacios[0].centro() == pytest.approx((5, 5))


def test_abertura_deja_pasar_segun_tipo_y_estado():
	assert Abertura(tipo="hueco", estado="cerrada").deja_pasar()
	assert Abertura(tipo="puerta", estado="abierta").deja_pasar()
	assert not Abertura(tipo="puerta", estado="cerrada").deja_pasar()
	assert Abertura(tipo="puerta", estado="cerrada").deja_pasar(contar_cerradas=True)
	assert not Abertura(tipo="puerta", estado="con_llave").deja_pasar(contar_cerradas=True)
	assert not Abertura(tipo="ventana", estado="abierta").deja_pasar(contar_cerradas=True)
	assert Abertura(a=(0, 0), b=(0.82, 0)).ancho == pytest.approx(0.82)


def test_aviso():
	aviso = Aviso("error", "codigo", "Mensaje.", "e", "p", "Sugerencia.")
	assert aviso.es_error
	assert str(aviso) == "Mensaje. Sugerencia."
	assert mo.hay_errores([Aviso(), aviso])
	assert not mo.hay_errores([Aviso()])


# ── Paredes derivadas ────────────────────────────────────────────────────────


def _largo(segmentos) -> float:
	return sum(((s.a[0] - s.b[0]) ** 2 + (s.a[1] - s.b[1]) ** 2) ** 0.5 for s in segmentos)


def test_solidos_de_dos_habitaciones_adosadas_comparten_pared():
	_entorno, planta, _salon, _cocina = piso_minimo()
	solidos = segmentos_solidos(planta)
	# Perímetros: 18 + 14 = 32; la pared común (4 m) cuenta una vez y pierde la puerta abierta (0,82).
	assert _largo(solidos) == pytest.approx(32 - 4 - 0.82)
	assert all(s.clase == "pared" for s in solidos)
	# Nadie puede cruzar de (4, 1) a (6, 1) salvo por la puerta, centrada en y = 2.
	assert any(s.a[0] == pytest.approx(5) and s.b[0] == pytest.approx(5) for s in solidos)


def test_puerta_cerrada_es_solida_y_se_puede_ignorar():
	_entorno, planta, _salon, _cocina = piso_minimo()
	puerta = planta.aberturas[0]
	puerta.estado = "cerrada"
	con_puerta = segmentos_solidos(planta)
	assert [s.clase for s in con_puerta].count("puerta") == 1
	assert next(s for s in con_puerta if s.clase == "puerta").elemento_id == puerta.id
	assert _largo(con_puerta) == pytest.approx(28)
	sin_puerta = segmentos_solidos(planta, incluir_puertas_cerradas=False)
	assert all(s.clase != "puerta" for s in sin_puerta)
	assert _largo(sin_puerta) == pytest.approx(28 - 0.82)
	# Con llave no se quita nunca.
	puerta.estado = "con_llave"
	assert any(s.clase == "puerta" for s in segmentos_solidos(planta, incluir_puertas_cerradas=False))


def test_ventana_corta_el_paso_pero_deja_pasar_parte_del_sonido():
	entorno, planta, salon, _cocina = piso_minimo()
	ed.anadir_puerta(entorno, planta, salon, "sur", tipo="ventana", ancho=1.0)
	ventanas = [s for s in segmentos_solidos(planta) if s.clase == "ventana"]
	assert len(ventanas) == 1
	assert _largo(segmentos_solidos(planta)) == pytest.approx(32 - 4 - 0.82)
	opacas = [s for s in segmentos_opacos(planta) if s.clase == "ventana"]
	assert opacas[0].atenuacion == mo.ATENUACION_VENTANA < 1


def test_lados_abiertos_macizos_y_zonas_sin_pared():
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	sala = ed.crear_habitacion_rectangular(entorno, planta, "Sala", 0, 0, 4, 4, lados_abiertos=[1])
	assert _largo(segmentos_solidos(planta)) == pytest.approx(12)
	plaza = ed.crear_espacio_poligonal(entorno, planta, "Plaza", [(10, 0), (20, 0), (20, 10), (10, 10)], tipo="plaza")
	assert not plaza.cerrado
	assert _largo(segmentos_solidos(planta)) == pytest.approx(12)
	edificio, portal = ed.crear_edificio(entorno, planta, "Bloque", 30, 0, 5, 5, portal_lado="sur")
	macizos = [s for s in segmentos_solidos(planta) if s.clase == "macizo"]
	# El portal de un macizo no abre hueco: el contorno entero sigue siendo sólido.
	assert _largo(macizos) == pytest.approx(20)
	assert all(s.elemento_id == edificio.id for s in macizos)
	assert portal is not None
	assert sala.lados_abiertos == [1]


def test_paredes_sueltas_paso_y_sonido():
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	ed.crear_espacio_poligonal(entorno, planta, "Patio", [(0, 0), (10, 0), (10, 10), (0, 10)], tipo="exterior")
	muro = ed.anadir_pared(entorno, planta, (2, 2), (6, 2), nombre="Muro")
	valla = ed.anadir_pared(entorno, planta, (2, 5), (6, 5), nombre="Valla", material="valla", bloquea_sonido=False)
	cinta = ed.anadir_pared(entorno, planta, (2, 8), (6, 8), nombre="Cortina", bloquea_paso=False)
	solidos = {s.elemento_id for s in segmentos_solidos(planta)}
	opacos = {s.elemento_id for s in segmentos_opacos(planta)}
	assert solidos == {muro.id, valla.id}
	assert opacos == {muro.id, cinta.id}


def test_puertas_y_sonido():
	_entorno, planta, _salon, _cocina = piso_minimo()
	puerta = planta.aberturas[0]
	assert all(s.clase == "pared" for s in segmentos_opacos(planta))
	puerta.estado = "cerrada"
	atenuadas = [s for s in segmentos_opacos(planta) if s.clase == "puerta"]
	assert len(atenuadas) == 1
	assert atenuadas[0].atenuacion == mo.ATENUACION_PUERTA
	puerta.tipo = "hueco"
	assert all(s.clase == "pared" for s in segmentos_opacos(planta))


def test_solidos_con_catalogo_incluyen_los_objetos_que_bloquean(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	_entorno, planta, _salon, _cocina = piso_minimo()
	mesa = catalogo.crear_objeto("prueba/mesa", 2, 2, 0)
	mesa.id = "obj-mesa"
	alfombra = catalogo.crear_objeto("prueba/alfombra", 3, 1, 0)
	alfombra.id = "obj-alfombra"
	caja = Objeto(id="obj-caja", tipo="falta/algo", x=1, y=3, ancho=0.5, fondo=0.5)
	planta.objetos.extend([mesa, alfombra, caja])
	sin_objetos = segmentos_solidos(planta)
	con_objetos = segmentos_solidos(planta, catalogo)
	de_objetos = [s for s in con_objetos if s.clase == "objeto"]
	assert len(con_objetos) == len(sin_objetos) + 8
	assert {s.elemento_id for s in de_objetos} == {"obj-mesa", "obj-caja"}
	assert _largo([s for s in de_objetos if s.elemento_id == "obj-mesa"]) == pytest.approx(2 * (1.2 + 0.8))


def test_abertura_fuera_de_toda_pared_no_cuenta():
	_entorno, planta, _salon, _cocina = piso_minimo()
	planta.aberturas.append(Abertura(id="suelta", tipo="puerta", a=(1, 1), b=(2, 1), estado="cerrada"))
	assert all(s.elemento_id != "suelta" for s in segmentos_solidos(planta))
	assert mo.aberturas_sobre(planta, (5, 0), (5, 4))[0][0] is planta.aberturas[0]
