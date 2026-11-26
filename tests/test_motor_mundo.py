"""Pruebas del índice del mundo: segmentos, espacios, suelo, rayos y estado dinámico."""

from __future__ import annotations

import pytest

from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.motor.mundo import Mundo
from tests.test_motor_comun import sala_de_pruebas


def test_espacio_y_suelo_en_un_punto():
	mundo = Mundo(ejemplos.vivienda_ejemplo())
	assert mundo.espacio_en("pla-1", 2.0, 2.0).nombre == "Salón"
	assert mundo.espacio_en("pla-1", 6.0, 7.0).nombre == "Baño"
	assert mundo.espacio_en("pla-1", 20.0, 20.0) is None
	assert mundo.espacio_en("no-existe", 0.0, 0.0) is None
	assert mundo.suelo_en("pla-1", 0.5, 0.5) == "madera"
	# La alfombra es una zona de suelo dentro del salón.
	assert mundo.suelo_en("pla-1", 2.0, 2.0) == "alfombra"
	assert mundo.zona_en("pla-1", 2.0, 2.0).nombre == "Alfombra del salón"
	assert mundo.suelo_en("pla-1", 6.0, 2.0) == "baldosa"


def test_el_paso_de_peatones_gana_a_la_calzada_y_los_macizos_no_son_transitables():
	mundo = Mundo(ejemplos.barrio_ejemplo())
	assert mundo.espacio_en("pla-1", -8.0, 0.0).tipo == "paso_peatones"
	assert mundo.espacio_en("pla-1", -15.0, 0.0).tipo == "calzada"
	assert mundo.suelo_en("pla-1", -8.0, 3.8) == "tactil_botones"
	# Dentro del mercado (macizo) no hay espacio transitable, pero se puede preguntar por él.
	assert mundo.espacio_en("pla-1", -15.0, 12.0) is None
	assert mundo.espacio_en("pla-1", -15.0, 12.0, macizos=True).nombre == "Mercado"
	assert not mundo.transitable("pla-1", -15.0, 12.0)
	assert mundo.transitable("pla-1", -20.0, 4.5)
	# Más allá de las aceras no hay nada: no se puede estar.
	assert not mundo.transitable("pla-1", 35.0, 15.0)


def test_rayo_y_linea_de_vision():
	mundo = Mundo(ejemplos.vivienda_ejemplo())
	# Desde el centro del pasillo hacia el este: la pared del fondo, a 4 m.
	impacto = mundo.rayo("pla-1", (4.0, 4.6), 90.0, 20.0)
	assert impacto.distancia == pytest.approx(4.0)
	assert impacto.punto == pytest.approx((8.0, 4.6))
	assert impacto.seg.clase == "pared" and impacto.seg.material == "ladrillo"
	assert mundo.rayo("pla-1", (4.0, 4.6), 90.0, 3.0) is None
	# Del pasillo al salón se ve por la puerta abierta, pero no a través del tabique.
	assert mundo.visible("pla-1", (1.95, 4.6), (1.95, 2.0))
	assert not mundo.visible("pla-1", (4.0, 4.6), (4.0, 2.0))
	assert mundo.corta("pla-1", (4.0, 4.6), (4.0, 2.0)).clase == "pared"
	# Mirar hacia el centro de una puerta, que está sobre la pared, no cuenta como cortado por ella.
	puerta = next(a for a in mundo.entorno.plantas[0].aberturas if "Dormitorio" in a.nombre and a.tipo == "puerta")
	assert mundo.visible("pla-1", (3.0, 4.6), puerta.centro())


def test_las_puertas_cambian_sin_reconstruir_y_sin_tocar_el_modelo():
	entorno = ejemplos.vivienda_ejemplo()
	mundo = Mundo(entorno)
	puerta = next(a for a in entorno.plantas[0].aberturas if "Dormitorio" in a.nombre and a.tipo == "puerta")
	dentro, fuera = (puerta.centro()[0], 6.0), (puerta.centro()[0], 4.6)
	segmentos = len(mundo.planta("pla-1").segs)
	version = mundo.version
	assert mundo.estado_abertura(puerta.id) == "cerrada"
	assert mundo.corta("pla-1", fuera, dentro).clase == "puerta"
	assert mundo.atenuacion("pla-1", fuera, dentro) == (0, pytest.approx(0.4))
	assert not mundo.deja_pasar(puerta.id) and mundo.deja_pasar(puerta.id, contar_cerradas=True)
	assert mundo.poner_abertura(puerta.id, "abierta")
	assert not mundo.poner_abertura(puerta.id, "abierta")
	assert mundo.version == version + 1
	assert mundo.corta("pla-1", fuera, dentro) is None
	assert mundo.atenuacion("pla-1", fuera, dentro) == (0, 1.0)
	assert len(mundo.planta("pla-1").segs) == segmentos
	assert puerta.estado == "cerrada"
	mundo.poner_abertura(puerta.id, "con_llave")
	assert not mundo.deja_pasar(puerta.id, contar_cerradas=True)
	# Una ventana y un hueco no tienen hoja que mover.
	ventana = next(a for a in entorno.plantas[0].aberturas if a.tipo == "ventana")
	assert not mundo.poner_abertura(ventana.id, "abierta")
	assert not mundo.deja_pasar(ventana.id, contar_cerradas=True)


def test_atenuacion_del_sonido():
	mundo = Mundo(ejemplos.vivienda_ejemplo())
	# Un tabique tapa del todo; dos, dos veces; una ventana, en parte.
	assert mundo.atenuacion("pla-1", (2.0, 4.6), (2.0, 4.8)) == (0, 1.0)
	assert mundo.atenuacion("pla-1", (4.0, 4.6), (4.0, 2.0))[0] == 1
	assert mundo.atenuacion("pla-1", (4.0, 2.0), (4.0, 7.0))[0] == 2
	totales, transmision = mundo.atenuacion("pla-1", (2.25, 1.0), (2.25, -1.0))
	assert totales == 0 and transmision == pytest.approx(0.5)
	# Un edificio macizo cuenta una vez aunque el sonido cruce dos de sus fachadas.
	barrio = Mundo(ejemplos.barrio_ejemplo())
	assert barrio.atenuacion("pla-1", (-15.0, 4.5), (-15.0, 25.0))[0] == 1


def test_objetos_del_catalogo_con_su_huella_real(tmp_path):
	entorno, _planta, catalogo, objetos = sala_de_pruebas(tmp_path)
	mundo = Mundo(entorno, catalogo)
	mesa = mundo.objeto(objetos["mesa"].id)
	assert mesa.bloquea and mesa.detectable and mesa.caja == pytest.approx((3.4, 2.6, 4.6, 3.4))
	# El rayo da en el borde real de la mesa, no en su centro.
	impacto = mundo.rayo("pla-1", (1.0, 3.0), 90.0, 20.0)
	assert impacto.distancia == pytest.approx(2.4) and impacto.seg.clase == "objeto" and impacto.seg.nombre == "Mesa"
	# La vista no la corta un mueble; el paso, sí.
	assert mundo.visible("pla-1", (1.0, 3.0), (7.0, 3.0), "vista")
	assert not mundo.visible("pla-1", (1.0, 3.0), (7.0, 3.0), "paso")
	# Pizarra en voladizo: para al alumno pero el bastón pasa por debajo.
	pizarra = mundo.objeto(objetos["pizarra"].id)
	assert pizarra.altura_base == pytest.approx(0.9) and not pizarra.detectable
	assert mundo.rayo("pla-1", (2.0, 4.0), 0.0, 5.0, "paso").seg.nombre == "Pizarra"
	assert mundo.rayo("pla-1", (2.0, 4.0), 0.0, 5.0, "sonda").seg.clase == "pared"
	# Lámpara a 1,90: ni para ni la encuentra el bastón; la alfombra no corta el paso.
	assert mundo.rayo("pla-1", (2.0, 2.5), 180.0, 5.0, "paso").seg.clase == "pared"
	assert mundo.rayo("pla-1", (5.0, 1.5), 90.0, 2.0, "paso") is None
	assert mundo.dentro_de_objeto("pla-1", 4.0, 3.0) is mesa
	assert mundo.dentro_de_objeto("pla-1", 6.5, 1.5) is None
	cerca = mundo.objetos_cerca("pla-1", 1.0, 3.0, 2.5)
	assert [info.objeto.nombre for _d, info in cerca][-1] == "Mesa"
	assert cerca[-1][0] == pytest.approx(2.4)


def test_objeto_circular_y_objeto_sin_ficha(tmp_path):
	entorno, planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	from app.dominio.modelo import Objeto
	from tests.test_motor_comun import poner_objeto

	redonda = poner_objeto(entorno, planta, catalogo, "prueba/mesa_redonda", 6.0, 4.0)
	planta.objetos.append(
		Objeto(id="obj-caja", nombre="Caja de mudanza", tipo="otro/desconocido", x=1.0, y=1.0, ancho=0.6, fondo=0.6, alto=0.5)
	)
	mundo = Mundo(entorno, catalogo)
	# Mesa redonda de 1 m: en diagonal, el rayo la encuentra a medio metro de su centro, no en la esquina de su caja.
	impacto = mundo.rayo("pla-1", (7.0, 5.0), 225.0, 5.0)
	assert impacto.seg.elemento_id == redonda.id
	assert impacto.distancia == pytest.approx(1.414 - 0.5, abs=0.03)
	# Un tipo que no está instalado se conserva como una caja con sus medidas, que corta el paso.
	caja = mundo.objeto("obj-caja")
	assert caja.definicion is None and caja.bloquea
	assert mundo.rayo("pla-1", (1.0, 3.0), 180.0, 5.0).seg.nombre == "Caja de mudanza"


def test_bocas_y_paradas_por_planta():
	mundo = Mundo(ejemplos.centro_dos_plantas())
	baja, primera = mundo.planta("pla-1"), mundo.planta("pla-2")
	assert [(b.sentido, b.punto, b.rumbo, b.destino) for b in baja.bocas] == [(1, (8.8, 8.6), 0.0, "pla-2")]
	# Arriba se entra al tramo de espaldas a como se sale de él.
	assert [(b.sentido, b.punto, b.rumbo, b.destino) for b in primera.bocas] == [(-1, (10.2, 8.6), 0.0, "pla-1")]
	assert len(baja.paradas) == 1 and len(primera.paradas) == 1
	assert mundo.altura("pla-2") == pytest.approx(3.2)
	assert mundo.paradas_cerca("pla-1", 12.0, 7.0, 1.0)[0][0] == pytest.approx(0.4)
	assert mundo.bocas_cerca("pla-1", 0.0, 0.0, 2.0) == []


def test_una_valla_corta_el_paso_pero_no_el_sonido_ni_la_percepcion():
	entorno = ed.crear_entorno("Patio")
	planta = ed.crear_planta(entorno, "Patio", exterior=True)
	ed.crear_espacio_poligonal(entorno, planta, "Patio", [(0, 0), (10, 0), (10, 10), (0, 10)], tipo="plaza", cerrado=False)
	ed.anadir_pared(entorno, planta, (0.0, 5.0), (10.0, 5.0), material="valla", bloquea_sonido=False, nombre="Valla del patio")
	mundo = Mundo(entorno)
	assert mundo.corta(planta.id, (5.0, 4.0), (5.0, 6.0), "paso").nombre == "Valla del patio"
	assert mundo.visible(planta.id, (5.0, 4.0), (5.0, 6.0), "vista")
	assert mundo.atenuacion(planta.id, (5.0, 4.0), (5.0, 6.0)) == (0, 1.0)


def test_reindexar_tras_editar_conserva_el_estado(tmp_path):
	entorno, planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	from tests.test_motor_comun import poner_objeto

	mundo = Mundo(entorno, catalogo)
	puerta = planta.aberturas[0]
	mundo.poner_abertura(puerta.id, "abierta")
	silla = poner_objeto(entorno, planta, catalogo, "prueba/silla", 1.0, 1.0)
	assert mundo.objeto(silla.id) is None
	mundo.reindexar(planta.id)
	assert mundo.objeto(silla.id) is not None
	assert mundo.estado_abertura(puerta.id) == "abierta"
	assert mundo.rayo(planta.id, (1.0, 3.0), 180.0, 5.0).seg.nombre == "Silla"
