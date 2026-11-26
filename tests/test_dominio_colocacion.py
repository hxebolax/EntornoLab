"""Pruebas de la colocación de objetos a escala y de las ayudas para colocar sin ver."""

from __future__ import annotations

import pytest

from app.dominio import colocacion as co
from app.dominio import edicion as ed
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Objeto
from tests.test_dominio_comun import catalogo_de_prueba, piso_minimo


@pytest.fixture
def catalogo(tmp_path):
	return catalogo_de_prueba(tmp_path)


def _codigos(avisos) -> list[str]:
	return sorted(a.codigo for a in avisos)


def _dentro(catalogo, espacio, objeto) -> bool:
	return geo.poligono_contiene(espacio.contorno, catalogo.huella(objeto))


# ── colocar y comprobar ──────────────────────────────────────────────────────


def test_colocar_en_sitio_libre_anade_el_objeto_y_le_da_id(catalogo):
	entorno, planta, _salon, _cocina = piso_minimo()
	mesa = catalogo.crear_objeto("prueba/mesa", 2.0, 2.0)
	avisos = co.colocar(entorno, planta, mesa, catalogo)
	assert avisos == []
	assert planta.objetos == [mesa]
	assert mesa.id.startswith("obj-")
	assert entorno.complementos == ["prueba"]
	# Volver a colocar el mismo objeto no lo duplica.
	co.colocar(entorno, planta, mesa, catalogo)
	assert len(planta.objetos) == 1
	assert entorno.complementos == ["prueba"]


def test_no_coloca_fuera_de_todo_espacio(catalogo):
	entorno, planta, _salon, _cocina = piso_minimo()
	mesa = catalogo.crear_objeto("prueba/mesa", 50, 50)
	avisos = co.colocar(entorno, planta, mesa, catalogo)
	assert _codigos(avisos) == ["fuera_de_espacio"]
	assert avisos[0].es_error
	assert avisos[0].planta_id == planta.id
	assert avisos[0].sugerencia
	assert planta.objetos == []
	assert mesa.id == ""


def test_no_coloca_atravesando_una_pared(catalogo):
	entorno, planta, _salon, _cocina = piso_minimo()
	mesa = catalogo.crear_objeto("prueba/mesa", 0.3, 2.0)
	avisos = co.colocar(entorno, planta, mesa, catalogo)
	assert "no_cabe" in _codigos(avisos)
	assert "Salón" in next(a.mensaje for a in avisos if a.codigo == "no_cabe")
	assert planta.objetos == []
	# Forzando se coloca igualmente, con sus avisos.
	assert "no_cabe" in _codigos(co.colocar(entorno, planta, mesa, catalogo, forzar=True))
	assert planta.objetos == [mesa]


def test_pegado_a_la_pared_cabe(catalogo):
	entorno, planta, salon, _cocina = piso_minimo()
	armario = catalogo.crear_objeto("prueba/armario", 2.0, 0.3, 0)
	assert co.colocar(entorno, planta, armario, catalogo) == []
	assert _dentro(catalogo, salon, armario)


def test_no_coloca_solapando_otro_objeto(catalogo):
	entorno, planta, _salon, _cocina = piso_minimo()
	co.colocar(entorno, planta, catalogo.crear_objeto("prueba/mesa", 2.0, 2.0), catalogo)
	silla = catalogo.crear_objeto("prueba/silla", 2.2, 2.1)
	avisos = co.colocar(entorno, planta, silla, catalogo)
	assert _codigos(avisos) == ["solapa_objeto"]
	assert "Mesa" in avisos[0].mensaje
	assert len(planta.objetos) == 1


def test_dos_objetos_adosados_no_se_solapan(catalogo):
	entorno, planta, _salon, _cocina = piso_minimo()
	co.colocar(entorno, planta, catalogo.crear_objeto("prueba/mesa", 2.0, 2.0), catalogo)
	otra = catalogo.crear_objeto("prueba/mesa", 3.2, 2.0)
	assert co.colocar(entorno, planta, otra, catalogo) == []


def test_alfombra_y_lampara_no_chocan_con_los_muebles(catalogo):
	entorno, planta, _salon, _cocina = piso_minimo()
	co.colocar(entorno, planta, catalogo.crear_objeto("prueba/mesa", 2.0, 2.0), catalogo)
	alfombra = catalogo.crear_objeto("prueba/alfombra", 2.0, 2.0)
	assert co.colocar(entorno, planta, alfombra, catalogo) == []
	# La lámpara cuelga a 1,90: por debajo cabe la mesa.
	lampara = catalogo.crear_objeto("prueba/lampara", 2.0, 2.0)
	assert co.colocar(entorno, planta, lampara, catalogo) == []
	# Pero el armario mide 2 metros de alto y sí choca con ella.
	armario = catalogo.crear_objeto("prueba/armario", 2.0, 0.3)
	armario.x, armario.y = 2.0, 2.9
	lampara.y = 2.9
	assert "solapa_objeto" in _codigos(co.comprobar(entorno, planta, armario, catalogo))


def test_avisa_si_tapa_una_puerta_pero_lo_coloca(catalogo):
	entorno, planta, _salon, _cocina = piso_minimo()
	# La puerta entre salón y cocina está en x = 5, de y = 1,59 a 2,41.
	armario = catalogo.crear_objeto("prueba/armario", 4.7, 2.0, 270)
	avisos = co.colocar(entorno, planta, armario, catalogo)
	assert "tapa_abertura" in _codigos(avisos)
	assert not next(a for a in avisos if a.codigo == "tapa_abertura").es_error
	assert planta.objetos == [armario]
	# Una ventana no cuenta: delante se puede poner un mueble.
	entorno2, planta2, salon2, _c = piso_minimo()
	ed.anadir_puerta(entorno2, planta2, salon2, "sur", desplazamiento=1.0, ancho=1.5, tipo="ventana")
	bajo = catalogo.crear_objeto("prueba/estanteria", 1.75, 0.15, 0)
	assert co.colocar(entorno2, planta2, bajo, catalogo) == []
	# Y junto al marco, sin invadir el paso, tampoco avisa.
	al_lado = catalogo.crear_objeto("prueba/estanteria", 4.85, 0.9, 270)
	assert "tapa_abertura" not in _codigos(co.comprobar(entorno, planta, al_lado, catalogo))


def test_zona_de_paso_de_una_abertura():
	_entorno, planta, _salon, _cocina = piso_minimo()
	zona = co.zona_de_paso(planta.aberturas[0])
	assert geo.caja(zona) == pytest.approx((5 - 0.6, 2 - 0.36, 5 + 0.6, 2 + 0.36))


def test_paso_minimo_configurable_entre_objetos_y_con_la_pared(catalogo):
	entorno, planta, _salon, _cocina = piso_minimo()
	co.colocar(entorno, planta, catalogo.crear_objeto("prueba/mesa", 2.0, 2.0), catalogo)
	# A 0,5 m de la mesa (borde de la mesa en x = 2,6).
	silla = catalogo.crear_objeto("prueba/silla", 3.325, 2.0)
	avisos = co.comprobar(entorno, planta, silla, catalogo)
	assert _codigos(avisos) == ["paso_estrecho"]
	assert "0,50" in avisos[0].mensaje
	assert "0,80" in avisos[0].mensaje
	assert not avisos[0].es_error
	assert co.comprobar(entorno, planta, silla, catalogo, paso_minimo=0.5) == []
	assert _codigos(co.comprobar(entorno, planta, silla, catalogo, paso_minimo=1.2)) == ["paso_estrecho"]
	# A 0,3 m de la pared sur: hueco que no sirve para pasar.
	cerca = catalogo.crear_objeto("prueba/silla", 1.0, 0.525)
	avisos = co.comprobar(entorno, planta, cerca, catalogo)
	assert _codigos(avisos) == ["paso_estrecho"]
	assert "pared" in avisos[0].mensaje
	# Un objeto que no corta el paso no estrecha nada.
	alfombra = catalogo.crear_objeto("prueba/alfombra", 2.0, 0.9)
	assert co.comprobar(entorno, planta, alfombra, catalogo) == []


def test_paredes_sueltas_macizos_y_zonas_exteriores(catalogo):
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno, exterior=True)
	acera = ed.crear_espacio_poligonal(entorno, planta, "Acera", [(0, 0), (20, 0), (20, 2), (0, 2)], tipo="acera")
	ed.crear_edificio(entorno, planta, "Bloque", 0, 2, 20, 10)
	ed.anadir_pared(entorno, planta, (10, 0), (10, 1.5), nombre="Valla de obra")
	banco = catalogo.crear_objeto("prueba/banco", 5, 1.7, 180)
	assert co.comprobar(entorno, planta, banco, catalogo) == []
	banco.y = 2.2
	assert "solapa_macizo" in _codigos(co.comprobar(entorno, planta, banco, catalogo))
	banco.x, banco.y = 10, 1.0
	assert "solapa_pared" in _codigos(co.comprobar(entorno, planta, banco, catalogo))
	# En una zona sin paredes, sobresalir es un aviso y no un error.
	banco.x, banco.y = 15, 0.1
	avisos = co.comprobar(entorno, planta, banco, catalogo)
	assert _codigos(avisos) == ["sobresale"]
	assert not avisos[0].es_error
	assert acera.cerrado is False
	dentro = catalogo.crear_objeto("prueba/banco", 5, 6)
	assert _codigos(co.comprobar(entorno, planta, dentro, catalogo)) == ["solapa_macizo"]


def test_medidas_no_validas_y_cajas_sin_catalogo():
	entorno, planta, _salon, _cocina = piso_minimo()
	raro = Objeto(nombre="Raro", ancho=0, fondo=1, x=2, y=2)
	assert _codigos(co.comprobar(entorno, planta, raro, None)) == ["medidas_no_validas"]
	caja = Objeto(nombre="Vitrina", tipo="museo/vitrina", ancho=1.0, fondo=0.5, x=2, y=2)
	assert co.colocar(entorno, planta, caja, None) == []
	assert entorno.complementos == ["museo"]
	suelta = Objeto(nombre="Caja", tipo="caja", ancho=0.5, fondo=0.5, x=3.9, y=2.0)
	assert co.colocar(entorno, planta, suelta, Catalogo()) == []
	assert entorno.complementos == ["museo"]


# ── Lados de un espacio ──────────────────────────────────────────────────────


def test_lado_de_espacio_rectangular():
	_entorno, _planta, salon, _cocina = piso_minimo()
	assert co.lado_de_espacio(salon, "sur") == (0, (0.0, 0.0), (5.0, 0.0))
	assert co.lado_de_espacio(salon, "este") == (1, (5.0, 0.0), (5.0, 4.0))
	# El inicio es siempre el extremo oeste o sur, aunque el contorno gire al revés.
	assert co.lado_de_espacio(salon, "norte") == (2, (0.0, 4.0), (5.0, 4.0))
	assert co.lado_de_espacio(salon, "oeste") == (3, (0.0, 0.0), (0.0, 4.0))
	assert co.lado_de_espacio(salon, "arriba") is None


def test_lado_de_espacio_en_ele_y_contorno_horario():
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	ele = ed.crear_espacio_poligonal(entorno, planta, "Ele", [(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)])
	# Hay dos lados que miran al norte: gana el más al norte.
	assert co.lado_de_espacio(ele, "norte")[1:] == ((0.0, 4.0), (2.0, 4.0))
	assert co.lado_de_espacio(ele, "este")[1:] == ((4.0, 0.0), (4.0, 2.0))
	ele.contorno.reverse()
	assert co.lado_de_espacio(ele, "norte")[1:] == ((0.0, 4.0), (2.0, 4.0))
	assert co.lado_de_espacio(ele, "sur")[1:] == ((0.0, 0.0), (4.0, 0.0))


# ── Colocar sin ver ──────────────────────────────────────────────────────────


@pytest.mark.parametrize(
	("lado", "x", "y", "rumbo"),
	[("norte", 2.5, 3.7, 180), ("sur", 2.5, 0.3, 0), ("este", 4.7, 2.0, 270), ("oeste", 0.3, 2.0, 90)],
)
def test_contra_pared_centrado_mira_hacia_dentro(catalogo, lado, x, y, rumbo):
	entorno, planta, salon, _cocina = piso_minimo()
	# La puerta está en la pared este: se comprueba la geometría, no los avisos.
	resultado = co.colocar_contra_pared(entorno, planta, salon, "prueba/armario", catalogo, lado)
	assert resultado.colocado
	armario = resultado.objeto
	assert (armario.x, armario.y) == pytest.approx((x, y))
	assert armario.rumbo == pytest.approx(rumbo)
	assert _dentro(catalogo, salon, armario)
	assert armario in planta.objetos


def test_contra_pared_con_alineacion_y_desplazamiento(catalogo):
	entorno, planta, salon, _cocina = piso_minimo()
	inicio = co.colocar_contra_pared(entorno, planta, salon, "prueba/armario", catalogo, "norte", "inicio").objeto
	assert geo.caja(catalogo.huella(inicio)) == pytest.approx((0, 3.4, 1.2, 4))
	fin = co.colocar_contra_pared(entorno, planta, salon, "prueba/estanteria", catalogo, "norte", "fin").objeto
	assert geo.caja(catalogo.huella(fin)) == pytest.approx((4.1, 3.7, 5, 4))
	# «A 1,20 del inicio» en la pared oeste: desde la esquina sur.
	medido = co.colocar_contra_pared(entorno, planta, salon, "prueba/estanteria", catalogo, "oeste", desplazamiento=1.2).objeto
	assert geo.caja(catalogo.huella(medido)) == pytest.approx((0, 1.2, 0.3, 2.1))
	separado = co.colocar_contra_pared(
		entorno, planta, salon, "prueba/silla", catalogo, "sur", separacion=0.5, nombre="Silla suelta"
	).objeto
	assert geo.caja(catalogo.huella(separado))[1] == pytest.approx(0.5)
	assert separado.nombre == "Silla suelta"


def test_contra_pared_ajusta_la_escala_y_nunca_supera_la_habitacion(catalogo):
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	cuarto = ed.crear_habitacion_rectangular(entorno, planta, "Cuarto", 0, 0, 1.2, 2.5)
	# La cama de 1,50 no cabe en 1,20 de ancho: se elige la variante individual.
	resultado = co.colocar_contra_pared(entorno, planta, cuarto, "prueba/cama", catalogo, "norte")
	assert resultado.colocado
	assert (resultado.objeto.ancho, resultado.objeto.fondo, resultado.objeto.variante) == (0.9, 1.9, "individual")
	assert _dentro(catalogo, cuarto, resultado.objeto)
	# En un trastero de 0,85 × 1,85 se escala al hueco.
	trastero = ed.crear_habitacion_rectangular(entorno, planta, "Trastero", 5, 0, 0.85, 1.85)
	resultado = co.colocar_contra_pared(entorno, planta, trastero, "prueba/cama", catalogo, "sur")
	assert resultado.colocado
	assert (resultado.objeto.ancho, resultado.objeto.fondo) == pytest.approx((0.85, 1.85))
	assert _dentro(catalogo, trastero, resultado.objeto)
	# En un armario empotrado de 0,6 × 0,6 no cabe ni al mínimo: no se coloca.
	hueco = ed.crear_habitacion_rectangular(entorno, planta, "Hueco", 10, 0, 0.6, 0.6)
	resultado = co.colocar_contra_pared(entorno, planta, hueco, "prueba/cama", catalogo, "norte")
	assert not resultado.colocado
	assert _codigos(resultado.avisos) == ["no_cabe"]
	assert "Hueco" in resultado.avisos[0].mensaje
	assert len(planta.objetos) == 2


def test_contra_pared_errores_claros(catalogo):
	entorno, planta, salon, _cocina = piso_minimo()
	assert _codigos(co.colocar_contra_pared(entorno, planta, salon, "prueba/no-existe", catalogo, "norte").avisos) == ["tipo_desconocido"]
	assert _codigos(co.colocar_contra_pared(entorno, planta, salon, "prueba/cama", catalogo, "arriba").avisos) == ["sin_lado"]
	assert _codigos(co.colocar_en_esquina(entorno, planta, salon, "prueba/cama", catalogo, "centro").avisos) == ["sin_lado"]
	assert planta.objetos == []
	# Una caja hecha a mano también se puede colocar con las ayudas.
	caja = Objeto(nombre="Baúl", tipo="caja", ancho=1.0, fondo=0.5, alto=0.5)
	resultado = co.colocar_contra_pared(entorno, planta, salon, caja, catalogo, "sur", "inicio")
	assert resultado.objeto is caja
	assert geo.caja(caja.huella_caja()) == pytest.approx((0, 0, 1.0, 0.5))


@pytest.mark.parametrize(
	("esquina", "caja"),
	[
		("noreste", (4.4, 3.35, 5.0, 4.0)),
		("noroeste", (0.0, 3.35, 0.6, 4.0)),
		("sureste", (4.4, 0.0, 5.0, 0.65)),
		("suroeste", (0.0, 0.0, 0.6, 0.65)),
	],
)
def test_colocar_en_esquina(catalogo, esquina, caja):
	entorno, planta, salon, _cocina = piso_minimo()
	resultado = co.colocar_en_esquina(entorno, planta, salon, "prueba/frigorifico", catalogo, esquina)
	assert resultado.colocado
	assert geo.caja(catalogo.huella(resultado.objeto)) == pytest.approx(caja)


def test_contra_pared_en_habitacion_girada(catalogo):
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	rombo = ed.crear_espacio_poligonal(entorno, planta, "Girada", geo.rectangulo_girado(0, 0, 5, 4, 30))
	for lado in co.LADOS:
		resultado = co.colocar_contra_pared(entorno, planta, rombo, "prueba/estanteria", catalogo, lado)
		assert resultado.colocado, lado
		assert _dentro(catalogo, rombo, resultado.objeto)


def test_colocar_junto_a_otro_objeto(catalogo):
	entorno, planta, salon, _cocina = piso_minimo()
	cama = co.colocar_contra_pared(entorno, planta, salon, "prueba/cama", catalogo, "norte").objeto
	# Cama: de x = 1,75 a 3,25 y de y = 2 a 4, mirando al sur.
	mesilla = co.colocar_junto_a(entorno, planta, cama, "prueba/mesilla", catalogo, "este").objeto
	assert geo.caja(catalogo.huella(mesilla)) == pytest.approx((3.25, 2.8, 3.7, 3.2))
	assert mesilla.rumbo == cama.rumbo
	otra = co.colocar_junto_a(entorno, planta, cama.id, "prueba/mesilla", catalogo, "oeste", separacion=0.1, rumbo=0).objeto
	assert geo.caja(catalogo.huella(otra)) == pytest.approx((1.2, 2.8, 1.65, 3.2))
	silla = co.colocar_junto_a(entorno, planta, cama, "prueba/silla", catalogo, "sur", separacion=0.9).objeto
	assert geo.caja(catalogo.huella(silla)) == pytest.approx((2.275, 0.65, 2.725, 1.1))
	# Al norte de la cama está la pared: no hay sitio.
	resultado = co.colocar_junto_a(entorno, planta, cama, "prueba/silla", catalogo, "norte")
	assert not resultado.colocado
	assert _codigos(resultado.avisos) == ["no_cabe"]
	assert _codigos(co.colocar_junto_a(entorno, planta, "no-existe", "prueba/silla", catalogo, "sur").avisos) == ["sin_lado"]
	assert _codigos(co.colocar_junto_a(entorno, planta, cama, "prueba/silla", catalogo, "abajo").avisos) == ["sin_lado"]


def test_colocar_junto_a_una_puerta_y_ajustando_tamano(catalogo):
	entorno, planta, salon, _cocina = piso_minimo()
	puerta = planta.aberturas[0]
	# «Al oeste de la puerta, a 1 metro».
	resultado = co.colocar_junto_a(entorno, planta, puerta, "prueba/silla", catalogo, "oeste", separacion=1.0)
	assert resultado.colocado
	assert geo.caja(catalogo.huella(resultado.objeto)) == pytest.approx((3.55, 1.775, 4.0, 2.225))
	# Entre un mueble y la pared solo quedan 0,9 m: el sofá de 2 m no cabe y la mesa se encoge.
	estante = co.colocar_contra_pared(entorno, planta, salon, "prueba/estanteria", catalogo, "sur", desplazamiento=3.2).objeto
	assert geo.caja(catalogo.huella(estante))[2] == pytest.approx(4.1)
	sofa = co.colocar_junto_a(entorno, planta, estante, "prueba/sofa", catalogo, "este", rumbo=0)
	assert not sofa.colocado
	assert _codigos(sofa.avisos) == ["no_cabe"]
	mesa = co.colocar_junto_a(entorno, planta, estante, "prueba/mesa", catalogo, "este", rumbo=0)
	assert mesa.colocado
	assert mesa.objeto.ancho == pytest.approx(0.9)
	assert _dentro(catalogo, salon, mesa.objeto)


def test_colocar_en_punto(catalogo):
	entorno, planta, salon, _cocina = piso_minimo()
	resultado = co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 2.5, 2.0, 90)
	assert resultado.colocado
	assert resultado.avisos == []
	assert geo.caja(catalogo.huella(resultado.objeto)) == pytest.approx((2.1, 1.4, 2.9, 2.6))
	# Cerca de la esquina no cabe con su tamaño: se encoge a lo que dejan las paredes.
	ajustada = co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 0.45, 3.6, 0)
	assert ajustada.colocado
	assert (ajustada.objeto.ancho, ajustada.objeto.fondo) == pytest.approx((0.9, 0.8))
	assert _dentro(catalogo, salon, ajustada.objeto)
	# Demasiado pegado: ni al mínimo.
	imposible = co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 0.2, 0.2, 0)
	assert not imposible.colocado
	assert _codigos(imposible.avisos) == ["no_cabe"]
	fuera = co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 99, 99)
	assert not fuera.colocado
	assert _codigos(fuera.avisos) == ["fuera_de_espacio"]
	assert _codigos(co.colocar_en_punto(entorno, planta, "nada/nada", catalogo, 1, 1).avisos) == ["tipo_desconocido"]


def test_caja_de_cualquier_elemento(catalogo):
	entorno, planta, salon, _cocina = piso_minimo()
	assert co.caja_de(salon) == (0, 0, 5, 4)
	assert co.caja_de(planta.aberturas[0]) == pytest.approx((5, 1.59, 5, 2.41))
	fuente = ed.anadir_fuente(entorno, planta, "Reloj", 1, 2, "reloj")
	assert co.caja_de(fuente) == (1, 2, 1, 2)
	redonda = catalogo.crear_objeto("prueba/mesa_redonda", 2, 2)
	assert co.caja_de(redonda, catalogo) == pytest.approx((1.5, 1.5, 2.5, 2.5))
	with pytest.raises(TypeError):
		co.caja_de(entorno)


# ── Amueblado asistido ───────────────────────────────────────────────────────


def _sin_errores_ni_puertas_tapadas(entorno, planta, catalogo) -> None:
	for objeto in planta.objetos:
		avisos = co.comprobar(entorno, planta, objeto, catalogo)
		assert not any(a.es_error for a in avisos), (objeto.nombre, [str(a) for a in avisos])
		assert "tapa_abertura" not in _codigos(avisos), objeto.nombre


@pytest.mark.parametrize(
	("uso", "ancho", "fondo", "esperados"),
	[
		("dormitorio", 4.0, 3.5, {"cama", "mesilla", "armario"}),
		("salon", 5.0, 4.0, {"sofa", "mesa", "estanteria"}),
		("cocina", 3.5, 4.0, {"frigorifico", "encimera", "mesa"}),
		("bano", 2.5, 2.5, {"inodoro", "lavabo"}),
		("aula", 7.0, 6.0, {"pizarra", "pupitre", "escritorio"}),
		("oficina", 4.0, 4.0, {"escritorio", "silla", "estanteria", "papelera"}),
	],
)
def test_amueblar_espacio_segun_su_uso(catalogo, uso, ancho, fondo, esperados):
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	sala = ed.crear_habitacion_rectangular(entorno, planta, "Sala", 0, 0, ancho, fondo)
	pasillo = ed.crear_habitacion_adosada(entorno, planta, "Pasillo", sala, "sur", ancho, 1.2, tipo="pasillo")
	ed.anadir_puerta_entre(entorno, planta, sala, pasillo)
	colocados = co.amueblar_espacio(entorno, planta, sala, uso, catalogo)
	tipos = {o.tipo.split("/")[1] for o in colocados}
	assert esperados <= tipos, tipos
	assert planta.objetos == colocados
	assert len({o.id for o in colocados}) == len(colocados)
	assert all(_dentro(catalogo, sala, o) for o in colocados)
	_sin_errores_ni_puertas_tapadas(entorno, planta, catalogo)


def test_amueblar_aula_reparte_pupitres_en_filas(catalogo):
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	aula = ed.crear_habitacion_rectangular(entorno, planta, "Aula", 0, 0, 8, 7)
	colocados = co.amueblar_espacio(entorno, planta, aula, "aula", catalogo)
	pupitres = [o for o in colocados if o.tipo == "prueba/pupitre"]
	assert 6 <= len(pupitres) <= 12
	assert len({round(o.y, 2) for o in pupitres}) >= 2
	# Entre pupitres queda siempre el paso mínimo.
	for i, uno in enumerate(pupitres):
		for otro in pupitres[i + 1 :]:
			assert geo.distancia_entre_poligonos(catalogo.huella(uno), catalogo.huella(otro)) >= co.PASO_MINIMO - 1e-6


def test_amueblar_sin_complementos_o_sin_sitio(catalogo):
	entorno, planta, salon, _cocina = piso_minimo()
	assert co.amueblar_espacio(entorno, planta, salon, "salon", Catalogo()) == []
	assert planta.objetos == []
	with pytest.raises(ValueError, match="submarino"):
		co.amueblar_espacio(entorno, planta, salon, "submarino", catalogo)
	cuartucho = ed.crear_habitacion_rectangular(entorno, planta, "Cuartucho", 20, 0, 0.25, 0.25)
	assert co.amueblar_espacio(entorno, planta, cuartucho, "dormitorio", catalogo) == []
	# Los seis usos de siempre siguen ahí y se buscan como siempre; los nuevos se apoyan en la clasificación.
	assert {"dormitorio", "salon", "cocina", "bano", "aula", "oficina"} <= set(co.USOS)
	assert set(co.USOS) == set(co.NOMBRES_USOS) and set(co.CONTEXTOS) == set(co.USOS) - {
		"dormitorio",
		"salon",
		"cocina",
		"bano",
		"aula",
		"oficina",
	}


def test_amueblar_como_propuesta_no_toca_la_planta(catalogo):
	entorno, planta, salon, _cocina = piso_minimo()
	propuesta = co.amueblar_espacio(entorno, planta, salon, "salon", catalogo, aplicar=False)
	assert propuesta
	assert planta.objetos == []
	# Aceptar la propuesta es colocar sus objetos.
	for objeto in propuesta:
		assert not any(a.es_error for a in co.colocar(entorno, planta, objeto, catalogo))
	assert len(planta.objetos) == len(propuesta)


def test_amueblar_respeta_lo_que_ya_habia(catalogo):
	entorno, planta, salon, _cocina = piso_minimo()
	piano = Objeto(nombre="Piano", tipo="caja", x=2.5, y=3.65, ancho=1.5, fondo=0.7, alto=1.2)
	assert co.colocar(entorno, planta, piano, catalogo) == []
	co.amueblar_espacio(entorno, planta, salon, "salon", catalogo)
	assert planta.objetos[0] is piano
	assert len(planta.objetos) > 1
	_sin_errores_ni_puertas_tapadas(entorno, planta, catalogo)
