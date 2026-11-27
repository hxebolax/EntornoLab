"""Pruebas de las operaciones de edición por medidas y relaciones, las descripciones y el historial."""

from __future__ import annotations

import pytest

from app.dominio import colocacion as co
from app.dominio import edicion as ed
from app.dominio import geometria as geo
from app.dominio.edicion import ErrorEdicion, Historial
from app.dominio.modelo import Abertura, Entorno, Objeto, segmentos_solidos
from tests.test_dominio_comun import catalogo_de_prueba, piso_minimo

# ── Entorno, plantas y espacios ──────────────────────────────────────────────


def test_crear_entorno_y_plantas():
	entorno = ed.crear_entorno("Mi Casa", "Descripción", "Ana")
	assert (entorno.id, entorno.nombre, entorno.autor) == ("mi-casa", "Mi Casa", "Ana")
	baja = ed.crear_planta(entorno)
	primera = ed.crear_planta(entorno)
	sotano = ed.crear_planta(entorno, nivel=-1)
	calle = ed.crear_planta(entorno, nivel=5, exterior=True, altura_m=0.0)
	assert (baja.nombre, baja.nivel, baja.altura_m) == ("Planta baja", 0, 0.0)
	assert (primera.nombre, primera.nivel, primera.altura_m) == ("Planta 1", 1, 3.0)
	assert (sotano.nombre, sotano.altura_m) == ("Sótano 1", -3.0)
	assert (calle.nombre, calle.exterior) == ("Calle", True)
	assert [p.nivel for p in entorno.plantas] == [-1, 0, 1, 5]
	assert entorno.inicio.planta == baja.id
	assert len({p.id for p in entorno.plantas}) == 4
	with pytest.raises(ErrorEdicion, match="nivel 1"):
		ed.crear_planta(entorno, nivel=1)


def test_habitacion_rectangular_por_medidas():
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	cocina = ed.crear_habitacion_rectangular(entorno, planta, "Cocina", 1, 2, 3, 4, suelo="baldosa", descripcion="Con ventana")
	assert cocina.contorno == [(1, 2), (4, 2), (4, 6), (1, 6)]
	assert (cocina.tipo, cocina.cerrado, cocina.suelo, cocina.acustica) == ("habitacion", True, "baldosa", "habitacion")
	assert cocina.id.startswith("esp-")
	assert planta.espacios == [cocina]
	assert cocina.descripcion == "Con ventana"
	pasillo = ed.crear_habitacion_rectangular(entorno, planta, "Pasillo", 10, 0, 8, 1.2, tipo="pasillo")
	assert pasillo.acustica == "pasillo"
	for ancho, fondo in ((0, 3), (3, -1), ("x", 3), (float("nan"), 3)):
		with pytest.raises(ErrorEdicion):
			ed.crear_habitacion_rectangular(entorno, planta, "Mala", 20, 0, ancho, fondo)
	with pytest.raises(ErrorEdicion, match="suelo"):
		ed.crear_habitacion_rectangular(entorno, planta, "Mala", 20, 0, 2, 2, suelo="lava")
	with pytest.raises(ErrorEdicion, match="acústica"):
		ed.crear_habitacion_rectangular(entorno, planta, "Mala", 20, 0, 2, 2, acustica="catedral")
	with pytest.raises(ErrorEdicion, match="tipo de espacio"):
		ed.crear_habitacion_rectangular(entorno, planta, "Mala", 20, 0, 2, 2, tipo="mazmorra")
	assert len(planta.espacios) == 2


def test_no_deja_pisar_otra_habitacion():
	entorno, planta, _salon, _cocina = piso_minimo()
	with pytest.raises(ErrorEdicion, match="Salón"):
		ed.crear_habitacion_rectangular(entorno, planta, "Encima", 4, 3, 2, 2)
	assert len(planta.espacios) == 2
	# Una zona sin paredes sí puede solaparse (una alfombra de juegos, una plaza).
	zona = ed.crear_espacio_poligonal(entorno, planta, "Zona", [(1, 1), (2, 1), (2, 2), (1, 2)], tipo="exterior")
	assert not zona.cerrado
	dentro = ed.crear_habitacion_rectangular(entorno, planta, "Cabina", 1, 1, 1, 1, permitir_solape=True)
	assert planta.espacio_en(1.5, 1.5) is zona or planta.espacio_en(1.5, 1.5) is dentro


@pytest.mark.parametrize(
	("lado", "alineacion", "desplazamiento", "caja"),
	[
		("este", "inicio", None, (5, 0, 7, 3)),
		("este", "fin", None, (5, 1, 7, 4)),
		("este", "centro", None, (5, 0.5, 7, 3.5)),
		("este", "inicio", 0.5, (5, 0.5, 7, 3.5)),
		("oeste", "inicio", None, (-2, 0, 0, 3)),
		("norte", "inicio", None, (0, 4, 2, 7)),
		("norte", "fin", None, (3, 4, 5, 7)),
		("norte", "centro", None, (1.5, 4, 3.5, 7)),
		("sur", "inicio", 1.0, (1, -3, 3, 0)),
	],
)
def test_habitacion_adosada_comparte_pared(lado, alineacion, desplazamiento, caja):
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	salon = ed.crear_habitacion_rectangular(entorno, planta, "Salón", 0, 0, 5, 4)
	nueva = ed.crear_habitacion_adosada(entorno, planta, "Nueva", salon, lado, 2, 3, alineacion=alineacion, desplazamiento=desplazamiento)
	assert nueva.caja() == pytest.approx(caja)
	tramo = ed.pared_compartida(salon, nueva)
	assert tramo is not None
	assert geo.distancia(*tramo) == pytest.approx(2 if lado in ("norte", "sur") else 3)
	assert ed.vecinos(planta, salon) == [(nueva, lado)]
	opuesto = {"norte": "sur", "sur": "norte", "este": "oeste", "oeste": "este"}[lado]
	assert ed.vecinos(planta, nueva) == [(salon, opuesto)]


def test_habitacion_adosada_argumentos_no_validos():
	entorno, planta, salon, _cocina = piso_minimo()
	with pytest.raises(ErrorEdicion, match="lado"):
		ed.crear_habitacion_adosada(entorno, planta, "X", salon, "arriba", 2, 2)
	with pytest.raises(ErrorEdicion, match="alineación"):
		ed.crear_habitacion_adosada(entorno, planta, "X", salon, "norte", 2, 2, alineacion="torcida")
	with pytest.raises(ErrorEdicion, match="Cocina"):
		ed.crear_habitacion_adosada(entorno, planta, "X", salon, "este", 2, 2)


def test_espacio_poligonal_se_orienta_y_se_valida():
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	horario = [(0, 0), (0, 4), (2, 4), (2, 2), (4, 2), (4, 0)]
	ele = ed.crear_espacio_poligonal(entorno, planta, "Ele", horario)
	assert geo.es_antihorario(ele.contorno)
	assert ele.area() == pytest.approx(12)
	with pytest.raises(ErrorEdicion, match="tres vértices"):
		ed.crear_espacio_poligonal(entorno, planta, "Línea", [(0, 0), (1, 1)])
	with pytest.raises(ErrorEdicion, match="se corta"):
		ed.crear_espacio_poligonal(entorno, planta, "Lazo", [(10, 0), (12, 2), (12, 0), (10, 2)])
	with pytest.raises(ErrorEdicion, match="lista de puntos"):
		ed.crear_espacio_poligonal(entorno, planta, "Basura", [1, 2, 3])
	parque = ed.crear_espacio_poligonal(entorno, planta, "Parque", [(20, 0), (30, 0), (25, 8)], tipo="parque")
	assert (parque.cerrado, parque.suelo, parque.acustica) == (False, "hierba", "parque")


# ── Puertas y paredes ────────────────────────────────────────────────────────


def test_anadir_puerta_por_lado_y_desplazamiento():
	entorno, planta, salon, _cocina = piso_minimo()
	puerta = ed.anadir_puerta(entorno, planta, salon, "norte", 1.2)
	assert puerta.a == pytest.approx((1.2, 4))
	assert puerta.b == pytest.approx((2.02, 4))
	assert (puerta.tipo, puerta.estado, puerta.hoja) == ("puerta", "cerrada", "batiente")
	assert puerta.nombre == "Puerta de Salón"
	assert puerta.id.startswith("abe-")
	# En las paredes este y oeste el desplazamiento se mide desde el sur.
	oeste = ed.anadir_puerta(entorno, planta, salon, "oeste", 0.5, ancho=1.0, tipo="hueco")
	assert (oeste.a, oeste.b) == ((0, 0.5), (0, 1.5))
	assert (oeste.estado, oeste.hoja) == ("abierta", "ninguna")
	assert oeste.nombre == "Hueco de Salón"
	centrada = ed.anadir_puerta(entorno, planta, salon, "sur", nombre="Entrada", es_salida=True, estado="con_llave", hoja="corredera")
	assert centrada.centro() == pytest.approx((2.5, 0))
	assert (centrada.nombre, centrada.es_salida, centrada.estado, centrada.hoja) == ("Entrada", True, "con_llave", "corredera")


def test_anadir_puerta_detecta_el_vecino():
	entorno, planta, salon, cocina = piso_minimo()
	assert planta.aberturas[0].nombre == "Puerta entre Salón y Cocina"
	despensa = ed.crear_habitacion_adosada(entorno, planta, "Despensa", cocina, "norte", 3, 2)
	puerta = ed.anadir_puerta(entorno, planta, cocina, "norte", 1.0)
	assert puerta.nombre == "Puerta entre Cocina y Despensa"
	assert {e.nombre for e in ed.espacios_de_abertura(planta, puerta)} == {"Cocina", "Despensa"}
	assert ed.aberturas_de(planta, despensa) == [puerta]
	assert len(ed.aberturas_de(planta, cocina)) == 2
	assert ed.aberturas_de(planta, salon) == [planta.aberturas[0]]


def test_anadir_puerta_errores():
	entorno, planta, salon, _cocina = piso_minimo()
	with pytest.raises(ErrorEdicion, match="no cabe"):
		ed.anadir_puerta(entorno, planta, salon, "norte", 4.5)
	with pytest.raises(ErrorEdicion, match="no cabe"):
		ed.anadir_puerta(entorno, planta, salon, "norte", -1)
	with pytest.raises(ErrorEdicion, match="no cabe"):
		ed.anadir_puerta(entorno, planta, salon, "oeste", ancho=6)
	with pytest.raises(ErrorEdicion, match="no tiene pared"):
		ed.anadir_puerta(entorno, planta, salon, "noreste")
	with pytest.raises(ErrorEdicion, match="tipo de abertura"):
		ed.anadir_puerta(entorno, planta, salon, "norte", tipo="trampilla")
	with pytest.raises(ErrorEdicion, match="estado"):
		ed.anadir_puerta(entorno, planta, salon, "norte", estado="rota")
	with pytest.raises(ErrorEdicion, match="hoja"):
		ed.anadir_puerta(entorno, planta, salon, "norte", hoja="giratoria")
	# Ya hay una puerta en mitad de la pared este.
	with pytest.raises(ErrorEdicion, match="ya está"):
		ed.anadir_puerta(entorno, planta, salon, "este", 1.8)
	assert len(planta.aberturas) == 1


def test_anadir_puerta_entre_dos_espacios():
	entorno = ed.crear_entorno("x")
	planta = ed.crear_planta(entorno)
	salon = ed.crear_habitacion_rectangular(entorno, planta, "Salón", 0, 0, 5, 4)
	cocina = ed.crear_habitacion_adosada(entorno, planta, "Cocina", salon, "este", 3, 2, alineacion="fin")
	lejos = ed.crear_habitacion_rectangular(entorno, planta, "Lejos", 20, 20, 2, 2)
	# La pared común va de (5, 2) a (5, 4).
	assert ed.pared_compartida(salon, cocina) == ((5, 2), (5, 4))
	centrada = ed.anadir_puerta_entre(entorno, planta, salon, cocina)
	assert centrada.centro() == pytest.approx((5, 3))
	assert centrada.ancho == pytest.approx(0.82)
	planta.aberturas.clear()
	medida = ed.anadir_puerta_entre(entorno, planta, cocina, salon, desplazamiento=0.2, ancho=0.7, tipo="hueco")
	assert medida.a == pytest.approx((5, 2.2))
	assert medida.b == pytest.approx((5, 2.9))
	assert medida.nombre == "Hueco entre Cocina y Salón" or medida.nombre == "Hueco entre Salón y Cocina"
	with pytest.raises(ErrorEdicion, match="no comparten"):
		ed.anadir_puerta_entre(entorno, planta, salon, lejos)
	with pytest.raises(ErrorEdicion, match="no cabe"):
		ed.anadir_puerta_entre(entorno, planta, salon, cocina, ancho=2.5)
	assert ed.pared_compartida(salon, lejos) is None


def test_la_puerta_abre_la_pared_de_las_dos_habitaciones():
	_entorno, planta, _salon, _cocina = piso_minimo()
	# De centro a centro solo se pasa por el hueco de la puerta abierta.
	solidos = [(s.a, s.b) for s in segmentos_solidos(planta)]
	assert geo.rayo_contra_segmentos((2.5, 2.0), 90, solidos)[0] == pytest.approx(5.5)
	assert geo.rayo_contra_segmentos((2.5, 1.0), 90, solidos)[0] == pytest.approx(2.5)


def test_anadir_pared_portal_fuente_referencia_y_zona():
	entorno, planta, salon, _cocina = piso_minimo()
	pared = ed.anadir_pared(entorno, planta, (1, 1), (1, 3), nombre="Biombo", material="madera", bloquea_sonido=False, altura=1.8)
	assert (pared.id[:4], pared.a, pared.b, pared.altura) == ("par-", (1, 1), (1, 3), 1.8)
	with pytest.raises(ErrorEdicion, match="mismo punto"):
		ed.anadir_pared(entorno, planta, (1, 1), (1, 1))
	portal = ed.anadir_portal(entorno, planta, salon, "sur", 1.0, nombre="Portal 3", es_salida=True)
	assert (portal.tipo, portal.ancho, portal.es_salida) == ("portal", pytest.approx(1.2), True)
	fuente = ed.anadir_fuente(entorno, planta, "Reloj", 0.2, 2, "reloj", volumen=0.4, radio=5, bucle=False, intervalo=1.0)
	assert (fuente.id[:4], fuente.sonido, fuente.radio, fuente.bucle) == ("fue-", "reloj", 5.0, False)
	with pytest.raises(ErrorEdicion, match="sonido"):
		ed.anadir_fuente(entorno, planta, "Muda", 1, 1, "  ")
	referencia = ed.anadir_referencia(entorno, planta, "Felpudo", 2.5, 0.3, tipo="tactil", permanente=False)
	assert (referencia.id[:4], referencia.tipo, referencia.permanente) == ("ref-", "tactil", False)
	zona = ed.anadir_zona_suelo(entorno, planta, "Alfombra", [(1, 1), (1, 2), (3, 2), (3, 1)], "alfombra")
	assert geo.es_antihorario(zona.contorno)
	with pytest.raises(ErrorEdicion, match="suelo"):
		ed.anadir_zona_suelo(entorno, planta, "Rara", [(1, 1), (1, 2), (3, 2)], "lava")
	with pytest.raises(ErrorEdicion, match="superficie"):
		ed.anadir_zona_suelo(entorno, planta, "Plana", [(1, 1), (2, 1), (3, 1)], "alfombra")
	parada = ed.crear_parada(entorno, planta, "Parada", 1, 1)
	assert parada.tipo == "parada"
	inicio = ed.fijar_inicio(entorno, planta, 1, 2, -90)
	assert (inicio.x, inicio.y, inicio.rumbo) == (1, 2, 270)
	assert len(set(entorno.ids())) == len(entorno.ids())


# ── Conectores ───────────────────────────────────────────────────────────────


def _dos_plantas() -> tuple[Entorno, object, object]:
	entorno = ed.crear_entorno("x")
	baja = ed.crear_planta(entorno)
	alta = ed.crear_planta(entorno)
	ed.crear_habitacion_rectangular(entorno, baja, "Rellano bajo", 0, 0, 4, 6, tipo="escalera")
	ed.crear_habitacion_rectangular(entorno, alta, "Rellano alto", 0, 0, 4, 6, tipo="escalera")
	return entorno, baja, alta


def test_crear_escalera():
	entorno, baja, alta = _dos_plantas()
	escalera = ed.crear_escalera(entorno, baja, alta, (1, 1), 0, 4.0, 16, nombre="Escalera principal", pasamanos="derecha")
	tramo = escalera.tramos[0]
	assert (escalera.tipo, escalera.id[:4]) == ("escalera", "con-")
	assert (tramo.desde.planta, tramo.desde.punto, tramo.desde.rumbo) == (baja.id, (1, 1), 0)
	assert (tramo.hasta.planta, tramo.hasta.rumbo) == (alta.id, 0)
	assert tramo.hasta.punto == pytest.approx((1, 5))
	assert (tramo.longitud_m, tramo.peldanos) == (4.0, 16)
	assert escalera.datos == {"pasamanos": "derecha", "anchura": 1.0}
	assert entorno.conectores == [escalera]
	vuelta = ed.crear_escalera(entorno, baja, alta, (3, 1), 0, 6.0, 18, boca_arriba=(2, 1), rumbo_arriba=180, tipo="escalera_mecanica")
	assert (vuelta.tramos[0].hasta.punto, vuelta.tramos[0].hasta.rumbo) == ((2, 1), 180)
	assert vuelta.nombre == "Escalera mecánica"
	for argumentos, texto in (
		((baja, baja, (1, 1), 0, 4, 16), "distintas"),
		((alta, baja, (1, 1), 0, 4, 16), "orden contrario"),
		((baja, alta, (1, 1), 0, 0, 16), "longitud"),
		((baja, alta, (1, 1), 0, 4, 0), "peldaño"),
	):
		with pytest.raises(ErrorEdicion, match=texto):
			ed.crear_escalera(entorno, *argumentos)
	with pytest.raises(ErrorEdicion, match="pasamanos"):
		ed.crear_escalera(entorno, baja, alta, (1, 1), 0, 4, 16, pasamanos="arriba")
	with pytest.raises(ErrorEdicion, match="tipo de escalera"):
		ed.crear_escalera(entorno, baja, alta, (1, 1), 0, 4, 16, tipo="rampa")
	assert len(entorno.conectores) == 2


def test_crear_rampa_y_ascensor():
	entorno, baja, alta = _dos_plantas()
	rampa = ed.crear_rampa(entorno, baja, alta, (2, 0.5), 0, 5.0)
	assert (rampa.tipo, rampa.tramos[0].peldanos, rampa.nombre) == ("rampa", 0, "Rampa")
	assert rampa.datos["pendiente_pct"] == pytest.approx(60.0)
	assert rampa.tramos[0].hasta.punto == pytest.approx((2, 5.5))
	ascensor = ed.crear_ascensor(entorno, [alta, baja, baja], (3.5, 3), 90, nombre="Ascensor A")
	assert ascensor.tipo == "ascensor"
	assert [p.planta for p in ascensor.paradas] == [baja.id, alta.id]
	assert all(p.puerta.punto == (3.5, 3) and p.puerta.rumbo == 90 and p.puerta.planta == p.planta for p in ascensor.paradas)
	assert ascensor.datos["aviso_hablado"] is True
	assert ascensor.plantas() == [baja.id, alta.id]
	with pytest.raises(ErrorEdicion, match="dos plantas"):
		ed.crear_ascensor(entorno, [baja], (1, 1), 0)


# ── Exteriores ───────────────────────────────────────────────────────────────


def _calle() -> tuple[Entorno, object]:
	entorno = ed.crear_entorno("Barrio")
	return entorno, ed.crear_planta(entorno, exterior=True)


def test_crear_calle_genera_via_calzada_y_dos_aceras():
	entorno, planta = _calle()
	calle = ed.crear_calle(
		entorno, planta, "Calle Mayor", [(0, 0), (50, 0)], ancho_calzada=7, ancho_acera=2.5, carriles=2, trafico=2, velocidad_kmh=40
	)
	via = calle.via
	assert planta.vias == [via]
	assert (via.id[:4], via.nombre, via.ancho, via.carriles, via.sentido, via.trafico, via.velocidad_kmh) == (
		"via-",
		"Calle Mayor",
		7,
		2,
		"doble",
		2,
		40,
	)
	assert calle.calzada.caja() == pytest.approx((0, -3.5, 50, 3.5))
	assert (calle.calzada.tipo, calle.calzada.cerrado, calle.calzada.suelo, calle.calzada.acustica) == (
		"calzada",
		False,
		"asfalto",
		"calle",
	)
	# Eje hacia el este: la acera izquierda es la norte.
	assert calle.acera_izquierda.nombre == "Acera norte de Calle Mayor"
	assert calle.acera_izquierda.caja() == pytest.approx((0, 3.5, 50, 6))
	assert calle.acera_derecha.nombre == "Acera sur de Calle Mayor"
	assert calle.acera_derecha.caja() == pytest.approx((0, -6, 50, -3.5))
	assert all(a.tipo == "acera" and a.suelo == "acera" and not a.cerrado for a in calle.aceras)
	assert all(e.datos["via"] == via.id for e in planta.espacios)
	assert all(geo.es_antihorario(e.contorno) for e in planta.espacios)
	assert planta.espacio_en(10, 0) is calle.calzada
	assert planta.espacio_en(10, 5) is calle.acera_izquierda
	# En una zona de calle no hay paredes.
	assert segmentos_solidos(planta) == []
	reunida = ed.calle_de(planta, via)
	assert reunida.calzada is calle.calzada
	assert reunida.aceras == calle.aceras


def test_crear_calle_en_otras_direcciones_con_curva_y_sin_aceras():
	entorno, planta = _calle()
	sur = ed.crear_calle(entorno, planta, "Calle Sur", [(0, 30), (0, 0)], ancho_calzada=6, ancho_acera=2)
	assert sur.acera_izquierda.nombre == "Acera este de Calle Sur"
	assert sur.acera_derecha.nombre == "Acera oeste de Calle Sur"
	curva = ed.crear_calle(entorno, planta, "Calle Curva", [(100, 0), (140, 0), (140, 40)], ancho_calzada=6, ancho_acera=2)
	assert curva.calzada.area() == pytest.approx(6 * 80, rel=0.02)
	assert geo.es_simple(curva.calzada.contorno)
	assert planta.espacio_en(140, 20) is curva.calzada
	assert planta.espacio_en(144, 20) is curva.acera_derecha
	camino = ed.crear_calle(entorno, planta, "Camino", [(200, 0), (200, 20)], ancho_calzada=3, ancho_acera=0)
	assert camino.aceras == []
	assert camino.acera_izquierda is None
	for argumentos in (
		dict(eje=[(0, 0)]),
		dict(eje=[(0, 0), (0, 0.1)]),
		dict(ancho_calzada=0),
		dict(ancho_acera=-1),
		dict(sentido="circular"),
		dict(trafico=7),
	):
		parametros = {"eje": [(300, 0), (300, 50)], **argumentos}
		with pytest.raises(ErrorEdicion):
			ed.crear_calle(entorno, planta, "Mala", **parametros)


def test_crear_cruce_parte_las_aceras_y_crea_el_espacio_comun():
	entorno, planta = _calle()
	mayor = ed.crear_calle(entorno, planta, "Calle Mayor", [(-40, 0), (40, 0)], ancho_calzada=7, ancho_acera=2.5)
	rio = ed.crear_calle(entorno, planta, "Calle del Río", [(0, -30), (0, 30)], ancho_calzada=6, ancho_acera=2)
	cruce = ed.crear_cruce(entorno, planta, mayor, rio.via)
	assert cruce.nombre == "Cruce de Calle Mayor con Calle del Río"
	assert cruce.caja() == pytest.approx((-3, -3.5, 3, 3.5))
	assert (cruce.tipo, cruce.datos["cruce"], cruce.datos["vias"]) == ("calzada", True, [mayor.via.id, rio.via.id])
	assert planta.espacio_en(0, 0) is cruce
	aceras = [e for e in planta.espacios if e.tipo == "acera"]
	assert len(aceras) == 8
	assert len({a.id for a in aceras}) == 8
	nombres = sorted(a.nombre for a in aceras)
	assert "Acera norte de Calle Mayor, tramo oeste" in nombres
	assert "Acera norte de Calle Mayor, tramo este" in nombres
	assert "Acera este de Calle del Río, tramo sur" in nombres
	# Ninguna acera pisa ya la calzada de la otra calle.
	for acera in aceras:
		for calzada in (mayor.calzada, rio.calzada):
			assert geo.area_interseccion(acera.contorno, calzada.contorno) < 0.01, acera.nombre
	noroeste = next(a for a in aceras if a.nombre == "Acera norte de Calle Mayor, tramo oeste")
	assert noroeste.caja() == pytest.approx((-40, 3.5, -3, 6))
	# En mitad de la calzada del Río, a la altura de la acera de Mayor, ya no hay acera.
	assert planta.espacio_en(0, 5) is rio.calzada
	assert planta.espacio_en(-4, 5).tipo == "acera"
	assert len(ed.calle_de(planta, mayor).aceras) == 4


def test_crear_cruce_errores_y_cruce_en_t():
	entorno, planta = _calle()
	mayor = ed.crear_calle(entorno, planta, "Mayor", [(-40, 0), (40, 0)], ancho_calzada=6, ancho_acera=2)
	paralela = ed.crear_calle(entorno, planta, "Paralela", [(-40, 50), (40, 50)])
	with pytest.raises(ErrorEdicion, match="no se cruzan"):
		ed.crear_cruce(entorno, planta, mayor, paralela)
	with pytest.raises(ErrorEdicion, match="distintas"):
		ed.crear_cruce(entorno, planta, mayor, mayor.via)
	# Una calle que acaba en otra (cruce en T): solo se parte la acera del lado por el que llega.
	lateral = ed.crear_calle(entorno, planta, "Lateral", [(0, -30), (0, 0)], ancho_calzada=6, ancho_acera=2)
	ed.crear_cruce(entorno, planta, mayor, lateral)
	aceras_mayor = ed.calle_de(planta, mayor).aceras
	assert sorted(a.nombre for a in aceras_mayor) == [
		"Acera norte de Mayor",
		"Acera sur de Mayor, tramo este",
		"Acera sur de Mayor, tramo oeste",
	]


def test_crear_paso_de_peatones_con_semaforo():
	entorno, planta = _calle()
	mayor = ed.crear_calle(entorno, planta, "Calle Mayor", [(-40, 0), (40, 0)], ancho_calzada=7, ancho_acera=2.5)
	paso = ed.crear_paso_peatones(entorno, planta, mayor.via, (-8, 1.3), semaforo=True, sonoro=True, pulsador=True, isleta=True, ancho=4)
	assert paso.tipo == "paso_peatones"
	assert paso.nombre == "Paso de peatones de Calle Mayor"
	# Se ajusta al eje aunque el punto no esté justo encima.
	assert paso.caja() == pytest.approx((-10, -3.5, -6, 3.5))
	datos = paso.datos
	assert (datos["semaforo"], datos["sonoro"], datos["pulsador"], datos["isleta"]) == (True, True, True, True)
	assert (datos["via"], datos["longitud"], datos["ancho"]) == (mayor.via.id, 7, 4)
	assert sorted(datos["extremos"]) == [[-8.0, -3.5], [-8.0, 3.5]]
	assert set(datos["ciclo"]) == {"verde_peatones_s", "intermitente_s", "rojo_peatones_s"}
	assert planta.espacio_en(-8, 0) is paso
	tactiles = [z for z in planta.zonas if z.suelo == "tactil_botones"]
	assert len(tactiles) == 2
	assert sorted(geo.caja(z.contorno) for z in tactiles) == [pytest.approx((-10, -4.1, -6, -3.5)), pytest.approx((-10, 3.5, -6, 4.1))]
	assert {z.nombre for z in tactiles} == {
		"Pavimento táctil norte de Paso de peatones de Calle Mayor",
		"Pavimento táctil sur de Paso de peatones de Calle Mayor",
	}
	semaforos = [r for r in planta.referencias if r.tipo == "semaforo"]
	assert len(semaforos) == 2
	assert all("sonora" in r.descripcion and "pulsador" in r.descripcion for r in semaforos)
	assert len(datos["zonas"]) == 3
	assert len(datos["referencias"]) == 2
	assert any(z.nombre.startswith("Isleta") and z.suelo == "acera" for z in planta.zonas)


def test_crear_paso_de_peatones_sin_semaforo_y_errores():
	entorno, planta = _calle()
	rio = ed.crear_calle(entorno, planta, "Calle del Río", [(0, -30), (0, 30)], ancho_calzada=6, ancho_acera=2)
	paso = ed.crear_paso_peatones(entorno, planta, rio, (0, 9), nombre="Paso del colegio", ciclo=None, tactil=False)
	assert paso.caja() == pytest.approx((-3, 7, 3, 11))
	assert (paso.datos["semaforo"], paso.datos["sonoro"], paso.datos["pulsador"]) == (False, False, False)
	assert "ciclo" not in paso.datos
	assert planta.zonas == []
	assert planta.referencias == []
	propio = ed.crear_paso_peatones(entorno, planta, rio, (0, -9), semaforo=True, ciclo={"verde_peatones_s": 15, "rojo_peatones_s": 30})
	assert propio.datos["ciclo"] == {"verde_peatones_s": 15, "rojo_peatones_s": 30}
	with pytest.raises(ErrorEdicion, match="sin semáforo"):
		ed.crear_paso_peatones(entorno, planta, rio, (0, 20), sonoro=True)
	with pytest.raises(ErrorEdicion, match="ancho"):
		ed.crear_paso_peatones(entorno, planta, rio, (0, 20), ancho=0)


def test_manzana_y_edificio_macizo_con_portal():
	entorno, planta = _calle()
	manzana = ed.crear_manzana(entorno, planta, "Manzana", [(0, 0), (10, 0), (10, 10), (0, 10)])
	assert (manzana.tipo, manzana.macizo, manzana.cerrado) == ("edificio", True, True)
	edificio, portal = ed.crear_edificio(
		entorno, planta, "Bloque", 20, 0, 12, 8, portal_lado="sur", portal_desplazamiento=4, portal_nombre="Portal 12"
	)
	assert edificio.macizo
	assert (portal.tipo, portal.nombre, portal.estado) == ("portal", "Portal 12", "cerrada")
	assert portal.a == pytest.approx((24, 0))
	assert portal.b == pytest.approx((25.2, 0))
	sin_portal, nada = ed.crear_edificio(entorno, planta, "Nave", 40, 0, 5, 5)
	assert nada is None
	_e, por_defecto = ed.crear_edificio(entorno, planta, "Tienda", 50, 0, 5, 5, portal_lado="norte")
	assert por_defecto.nombre == "Portal de Tienda"
	with pytest.raises(ErrorEdicion, match="solaparía"):
		ed.crear_edificio(entorno, planta, "Encima", 5, 5, 10, 10)
	assert sin_portal.id != edificio.id


# ── Mover, girar, redimensionar, duplicar, borrar, renombrar ─────────────────


def test_mover_cada_clase_de_elemento(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, salon, _cocina = piso_minimo()
	mesa = co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 2, 2).objeto
	ed.mover(entorno, mesa, 1, -0.5)
	assert (mesa.x, mesa.y) == (3, 1.5)
	ed.mover_a(entorno, mesa.id, 1.5, 3)
	assert (mesa.x, mesa.y) == (1.5, 3)
	pared = ed.anadir_pared(entorno, planta, (1, 1), (2, 1))
	ed.mover(entorno, pared, 0, 1)
	assert (pared.a, pared.b) == ((1, 2), (2, 2))
	fuente = ed.anadir_fuente(entorno, planta, "Reloj", 1, 1, "reloj")
	ed.mover(entorno, fuente, 2, 2)
	assert (fuente.x, fuente.y) == (3, 3)
	zona = ed.anadir_zona_suelo(entorno, planta, "Alfombra", [(1, 1), (2, 1), (2, 2), (1, 2)], "alfombra")
	ed.mover_a(entorno, zona, 3.5, 0.5)
	assert geo.caja(zona.contorno) == pytest.approx((3, 0, 4, 1))
	with pytest.raises(ErrorEdicion, match="No existe"):
		ed.mover(entorno, "no-existe", 1, 1)
	assert salon.caja() == (0, 0, 5, 4)


def test_mover_una_habitacion_se_lleva_su_contenido(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, salon, cocina = piso_minimo()
	puerta = planta.aberturas[0]
	ventana = ed.anadir_puerta(entorno, planta, cocina, "este", tipo="ventana")
	nevera = co.colocar_en_esquina(entorno, planta, cocina, "prueba/frigorifico", catalogo, "noreste").objeto
	sofa = co.colocar_contra_pared(entorno, planta, salon, "prueba/sofa", catalogo, "oeste").objeto
	reloj = ed.anadir_fuente(entorno, planta, "Reloj", 7, 2, "reloj")
	felpudo = ed.anadir_referencia(entorno, planta, "Felpudo", 6, 1)
	ed.fijar_inicio(entorno, planta, 6.5, 2, 0)
	antes = (nevera.x, nevera.y)
	ed.mover(entorno, cocina, 10, 1)
	assert cocina.caja() == (15, 1, 18, 5)
	assert (nevera.x, nevera.y) == pytest.approx((antes[0] + 10, antes[1] + 1))
	assert (reloj.x, reloj.y) == (17, 3)
	assert (felpudo.x, felpudo.y) == (16, 2)
	assert ventana.centro() == pytest.approx((18, 3))
	assert puerta.centro() == pytest.approx((15, 3))
	assert (entorno.inicio.x, entorno.inicio.y) == (16.5, 3)
	# Lo del salón no se mueve.
	assert sofa.x == pytest.approx(0.45)
	assert salon.caja() == (0, 0, 5, 4)
	ed.mover(entorno, cocina, -10, -1, con_contenido=False)
	assert cocina.caja() == (5, 0, 8, 4)
	assert (reloj.x, reloj.y) == (17, 3)


def test_girar(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, salon, _cocina = piso_minimo()
	mesa = co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 2, 2).objeto
	ed.girar(entorno, mesa, 90)
	assert (mesa.x, mesa.y, mesa.rumbo) == (2, 2, 90)
	ed.girar(entorno, mesa, 300)
	assert mesa.rumbo == pytest.approx(30)
	ed.girar(entorno, mesa, 90, centro=(0, 0))
	assert (mesa.x, mesa.y) == pytest.approx((2, -2))
	pared = ed.anadir_pared(entorno, planta, (0, 10), (2, 10))
	ed.girar(entorno, pared, 90)
	assert pared.a == pytest.approx((1, 11))
	assert pared.b == pytest.approx((1, 9))
	aislada = ed.crear_habitacion_rectangular(entorno, planta, "Aislada", 20, 0, 4, 2)
	puerta = ed.anadir_puerta(entorno, planta, aislada, "sur", 0.5)
	ed.girar(entorno, aislada, 90)
	assert aislada.caja() == pytest.approx((21, -1, 23, 3))
	assert aislada.area() == pytest.approx(8)
	# La puerta sigue en la pared, que ahora es la oeste.
	assert ed.aberturas_de(planta, aislada) == [puerta]
	assert puerta.a[0] == pytest.approx(21)
	assert salon.caja() == (0, 0, 5, 4)


def test_redimensionar(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, salon, _cocina = piso_minimo()
	mesa = co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 2, 2).objeto
	ed.redimensionar(entorno, mesa, ancho=2.0, fondo=1.0, alto=0.8, catalogo=catalogo)
	assert (mesa.ancho, mesa.fondo, mesa.alto) == (2.0, 1.0, 0.8)
	with pytest.raises(ErrorEdicion, match="de 0,8 a 2,4"):
		ed.redimensionar(entorno, mesa, ancho=5.0, catalogo=catalogo)
	assert mesa.ancho == 2.0
	# Sin catálogo no hay rango que respetar.
	ed.redimensionar(entorno, mesa, ancho=5.0)
	assert mesa.ancho == 5.0
	with pytest.raises(ErrorEdicion):
		ed.redimensionar(entorno, mesa, ancho=0)
	ed.redimensionar(entorno, salon, ancho=6, fondo=3)
	assert salon.caja() == pytest.approx((0, 0, 6, 3))
	ed.redimensionar(entorno, salon, fondo=4)
	assert salon.caja() == pytest.approx((0, 0, 6, 4))
	puerta = planta.aberturas[0]
	ed.redimensionar(entorno, puerta, ancho=1.2)
	assert puerta.ancho == pytest.approx(1.2)
	assert puerta.centro() == pytest.approx((5, 2))
	with pytest.raises(ErrorEdicion, match="ancho"):
		ed.redimensionar(entorno, puerta, alto=2)
	pared = ed.anadir_pared(entorno, planta, (1, 1), (2, 1))
	ed.redimensionar(entorno, pared, ancho=3, alto=1.0, fondo=0.2)
	assert (pared.a, pared.b, pared.altura, pared.grosor) == ((1, 1), pytest.approx((4, 1)), 1.0, 0.2)
	fuente = ed.anadir_fuente(entorno, planta, "Reloj", 1, 1, "reloj")
	with pytest.raises(ErrorEdicion, match="no tiene medidas"):
		ed.redimensionar(entorno, fuente, ancho=1)


def test_renombrar():
	entorno, planta, salon, _cocina = piso_minimo()
	ed.renombrar(entorno, salon, "  Sala de estar ")
	assert salon.nombre == "Sala de estar"
	ed.renombrar(entorno, planta.id, "Bajo")
	assert planta.nombre == "Bajo"
	with pytest.raises(ErrorEdicion, match="vacío"):
		ed.renombrar(entorno, salon, "   ")


def test_duplicar_elementos(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, salon, _cocina = piso_minimo()
	silla = co.colocar_en_punto(entorno, planta, "prueba/silla", catalogo, 1, 1).objeto
	copia = ed.duplicar(entorno, silla, dx=1.0)
	assert copia is not silla
	assert copia.id != silla.id
	assert (copia.x, copia.y, copia.tipo) == (2, 1, silla.tipo)
	assert copia.nombre == "Silla (copia)"
	assert copia in planta.objetos
	otra = ed.duplicar(entorno, silla.id, dx=0, dy=1, nombre="Silla del rincón")
	assert (otra.nombre, otra.y) == ("Silla del rincón", 2)
	sala = ed.duplicar(entorno, salon, dx=0, dy=10)
	assert sala.caja() == (0, 10, 5, 14)
	assert len(planta.espacios) == 3
	assert len(set(entorno.ids())) == len(entorno.ids())


def test_duplicar_una_planta_entera():
	entorno, planta, _salon, _cocina = piso_minimo()
	ed.anadir_fuente(entorno, planta, "Reloj", 1, 1, "reloj")
	copia = ed.duplicar(entorno, planta, nombre="Planta primera")
	assert copia in entorno.plantas
	assert (copia.nombre, copia.nivel, copia.altura_m) == ("Planta primera", 1, 3.0)
	assert [e.nombre for e in copia.espacios] == ["Salón", "Cocina"]
	assert len(copia.aberturas) == 1
	assert len(copia.fuentes) == 1
	assert len(set(entorno.ids())) == len(entorno.ids())
	copia.espacios[0].nombre = "Otro"
	assert planta.espacios[0].nombre == "Salón"


def test_borrar_elementos_y_lo_que_depende_de_ellos(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, salon, cocina = piso_minimo()
	puerta = planta.aberturas[0]
	ventana = ed.anadir_puerta(entorno, planta, cocina, "este", tipo="ventana")
	silla = co.colocar_en_punto(entorno, planta, "prueba/silla", catalogo, 1, 1).objeto
	assert ed.borrar(entorno, silla) == [silla.id]
	assert planta.objetos == []
	borrados = ed.borrar(entorno, cocina.id)
	# La ventana se queda sin pared y desaparece; la puerta sigue en la pared del salón.
	assert set(borrados) == {cocina.id, ventana.id}
	assert planta.aberturas == [puerta]
	assert planta.espacios == [salon]
	tabique = ed.anadir_pared(entorno, planta, (1, 1), (4, 1))
	planta.aberturas.append(Abertura(id="abe-suelta", nombre="Paso", tipo="hueco", a=(2, 1), b=(3, 1)))
	assert set(ed.borrar(entorno, tabique)) == {tabique.id, "abe-suelta"}
	with pytest.raises(ErrorEdicion, match="No existe"):
		ed.borrar(entorno, silla.id)
	with pytest.raises(ErrorEdicion):
		ed.borrar(entorno, Objeto(id="fantasma"))


def test_borrar_via_paso_y_planta():
	entorno, planta = _calle()
	mayor = ed.crear_calle(entorno, planta, "Mayor", [(-40, 0), (40, 0)])
	rio = ed.crear_calle(entorno, planta, "Río", [(0, -30), (0, 30)])
	ed.crear_cruce(entorno, planta, mayor, rio)
	paso = ed.crear_paso_peatones(entorno, planta, mayor, (-10, 0), semaforo=True)
	otro = ed.crear_paso_peatones(entorno, planta, rio, (0, 12))
	assert len(planta.zonas) == 4
	ed.borrar(entorno, otro)
	assert len(planta.zonas) == 2
	assert len(planta.referencias) == 2
	ed.borrar(entorno, mayor.via)
	assert paso not in planta.espacios
	assert planta.zonas == []
	assert planta.referencias == []
	assert planta.vias == [rio.via]
	assert all(e.datos.get("via") == rio.via.id for e in planta.espacios)
	interior = ed.crear_planta(entorno, "Sótano", nivel=-1)
	ed.crear_habitacion_rectangular(entorno, interior, "Garaje", 100, 100, 5, 5)
	arriba = ed.crear_planta(entorno, "Azotea", nivel=1)
	ed.crear_habitacion_rectangular(entorno, arriba, "Terraza", 100, 100, 5, 5)
	ed.crear_ascensor(entorno, [interior, planta, arriba], (102, 102), 0)
	ed.crear_rampa(entorno, interior, planta, (101, 101), 0, 3)
	ed.fijar_inicio(entorno, interior, 102, 102)
	borrados = ed.borrar(entorno, interior)
	assert interior.id in borrados
	assert interior not in entorno.plantas
	# El ascensor conserva las otras dos paradas; la rampa se queda sin destino y desaparece.
	assert [c.tipo for c in entorno.conectores] == ["ascensor"]
	assert len(entorno.conectores[0].paradas) == 2
	assert entorno.inicio.planta == entorno.plantas[0].id
	assert ed.borrar(entorno, entorno.conectores[0]) != []
	assert entorno.conectores == []


# ── Medir ────────────────────────────────────────────────────────────────────


def test_medir_distancia_rumbo_y_separacion(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, salon, cocina = piso_minimo()
	silla = co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 1, 1).objeto
	mesa = co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 4, 1).objeto
	medida = ed.medir(entorno, silla, mesa.id, catalogo)
	assert medida.distancia == pytest.approx(3)
	assert medida.rumbo == pytest.approx(90)
	assert medida.separacion == pytest.approx(3 - 0.6 - 0.6)
	assert medida.misma_planta
	assert medida.texto() == "3 metros hacia el este (separación libre: 1,8 metros)"
	assert ed.medir(entorno, mesa, silla).rumbo == pytest.approx(270)
	entre_salas = ed.medir(entorno, salon, cocina)
	assert entre_salas.distancia == pytest.approx(4)
	assert entre_salas.separacion == 0
	reloj = ed.anadir_fuente(entorno, planta, "Reloj", 1, 3, "reloj")
	a_la_puerta = ed.medir(entorno, reloj, planta.aberturas[0])
	assert a_la_puerta.distancia == pytest.approx((16 + 1) ** 0.5)
	assert ed.medir(entorno, reloj, reloj).distancia == 0
	assert ed.medir(entorno, reloj, silla).texto() == "2 metros hacia el sur (separación libre: 1,6 metros)"


def test_medir_entre_plantas():
	entorno, baja, alta = _dos_plantas()
	abajo = ed.anadir_referencia(entorno, baja, "Abajo", 1, 1)
	arriba = ed.anadir_referencia(entorno, alta, "Arriba", 1, 2)
	medida = ed.medir(entorno, abajo, arriba)
	assert not medida.misma_planta
	assert medida.desnivel == pytest.approx(3.0)
	assert medida.texto() == "1 metro hacia el norte, en otra planta, 3 metros más arriba"
	assert "más abajo" in ed.medir(entorno, arriba, abajo).texto()
	assert ed.centro_de(baja) == pytest.approx((2, 3))
	assert len(ed.puntos_de(baja)) == 4


# ── Descripciones ────────────────────────────────────────────────────────────


def test_describir_elemento_de_cada_clase(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, salon, cocina = piso_minimo()
	assert (
		ed.describir_elemento(entorno, salon)
		== "Salón: habitación de 5 por 4 metros (20 metros cuadrados), suelo de baldosa, 1 puerta o hueco."
	)
	puerta = planta.aberturas[0]
	assert ed.describir_elemento(entorno, puerta) == (
		"Puerta entre Salón y Cocina: puerta de 0,82 metros, abierta, en la pared este de Salón, a 1,59 metros de la esquina sur, da a Cocina."
	)
	entrada = ed.anadir_puerta(entorno, planta, salon, "sur", 1.2, nombre="Entrada", es_salida=True, hoja="corredera")
	assert ed.describir_elemento(entorno, entrada.id) == (
		"Entrada: puerta de 0,82 metros, cerrada, corredera, en la pared sur de Salón, a 1,2 metros de la esquina oeste, es una salida."
	)
	mesa = co.colocar_en_punto(entorno, planta, "prueba/mesa", catalogo, 2, 3, 90).objeto
	assert ed.describir_elemento(entorno, mesa, catalogo) == (
		"Mesa: mesa de 1,2 de ancho por 0,8 de fondo y 0,75 metros de alto en Salón, a 2 metros de su lado oeste y 3 metros de su lado sur, "
		"mirando al este. Mesa de prueba."
	)
	armario = co.colocar_contra_pared(entorno, planta, cocina, "prueba/armario", catalogo, "norte").objeto
	assert "estado: cerrado" in ed.describir_elemento(entorno, armario, catalogo)
	caja = Objeto(nombre="Vitrina", tipo="museo/vitrina", x=1, y=1, ancho=1, fondo=0.5, alto=2)
	co.colocar(entorno, planta, caja, catalogo, forzar=True)
	assert ed.describir_elemento(entorno, caja, catalogo).startswith(
		"Vitrina: caja de 1 de ancho por 0,5 de fondo y 2 metros de alto en Salón"
	)
	reloj = ed.anadir_fuente(entorno, planta, "Reloj", 0.5, 2, "reloj", radio=5, descripcion="Hace tictac.")
	assert ed.describir_elemento(entorno, reloj) == (
		"Reloj: fuente de sonido «reloj» en Salón, a 0,5 metros de su lado oeste y 2 metros de su lado sur, se oye hasta 5 metros. Hace tictac."
	)
	felpudo = ed.anadir_referencia(entorno, planta, "Felpudo", 2.5, 0.3, tipo="tactil", permanente=False)
	assert ed.describir_elemento(entorno, felpudo).startswith("Felpudo: referencia táctil en Salón")
	assert ed.describir_elemento(entorno, felpudo).endswith(", pasajera.")
	alfombra = ed.anadir_zona_suelo(entorno, planta, "Alfombra", [(1, 1), (3, 1), (3, 2), (1, 2)], "alfombra")
	assert ed.describir_elemento(entorno, alfombra) == "Alfombra: zona de suelo de alfombra, de unos 2 por 1 metros."
	valla = ed.anadir_pared(entorno, planta, (10, 0), (13, 0), nombre="Valla", material="valla", bloquea_sonido=False)
	assert ed.describir_elemento(entorno, valla) == "Valla: pared de valla de 3 metros, de (10; 0) a (13; 0), deja pasar el sonido."
	assert ed.describir_elemento(entorno, planta) == "Planta baja: planta interior, nivel 0, a 0 metros de altura, con 2 espacios."
	with pytest.raises(ErrorEdicion):
		ed.describir_elemento(entorno, "no-existe")


def test_describir_exteriores_y_conectores():
	entorno, planta = _calle()
	mayor = ed.crear_calle(
		entorno, planta, "Calle Mayor", [(-40, 0), (40, 0)], ancho_calzada=7, ancho_acera=2.5, trafico=3, velocidad_kmh=50
	)
	assert ed.describir_elemento(entorno, mayor.via) == (
		"Calle Mayor: vía de 80 metros de largo y 7 metros de calzada, 2 carriles, doble sentido, tráfico intenso, a 50 kilómetros por hora."
	)
	paso = ed.crear_paso_peatones(entorno, planta, mayor, (0, 0), semaforo=True, sonoro=True, pulsador=True, isleta=True)
	texto = ed.describir_elemento(entorno, paso)
	assert texto.startswith("Paso de peatones de Calle Mayor: paso de peatones de ")
	assert "con semáforo sonoro y pulsador" in texto
	assert "con isleta" in texto
	sin = ed.crear_paso_peatones(entorno, planta, mayor, (20, 0))
	assert "sin semáforo" in ed.describir_elemento(entorno, sin)
	edificio, portal = ed.crear_edificio(entorno, planta, "Bloque", -20, 6, 10, 8, portal_lado="sur", portal_desplazamiento=2)
	assert "macizo, no se puede entrar" in ed.describir_elemento(entorno, edificio)
	assert "en la pared sur de Bloque, a 2 metros de la esquina oeste" in ed.describir_elemento(entorno, portal)
	ele = ed.crear_espacio_poligonal(entorno, planta, "Plaza", [(50, 10), (60, 10), (60, 15), (55, 15), (55, 20), (50, 20)], tipo="plaza")
	assert "de 6 lados, unos 10 por 10 metros (75 metros cuadrados)" in ed.describir_elemento(entorno, ele)
	entorno2, baja, alta = _dos_plantas()
	escalera = ed.crear_escalera(entorno2, baja, alta, (1, 1), 0, 4, 16, nombre="Escalera principal", pasamanos="derecha")
	assert ed.describir_elemento(entorno2, escalera) == (
		"Escalera principal: escalera, une Planta baja y Planta 1, 16 peldaños, 4 metros de recorrido, se sube hacia el norte, pasamanos: a la derecha."
	)
	rampa = ed.crear_rampa(entorno2, baja, alta, (2, 1), 0, 30)
	assert "pendiente del 10 por ciento" in ed.describir_elemento(entorno2, rampa)
	ascensor = ed.crear_ascensor(entorno2, [baja, alta], (3, 3), 90)
	assert ed.describir_elemento(entorno2, ascensor.id) == "Ascensor: ascensor, une Planta baja y Planta 1, 2 paradas."


def test_describir_entorno_completo(tmp_path):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno, planta, salon, cocina = piso_minimo()
	entorno.descripcion = "Un piso para las pruebas."
	entorno.autor = "Ana"
	co.colocar_contra_pared(entorno, planta, salon, "prueba/sofa", catalogo, "oeste")
	ed.anadir_fuente(entorno, planta, "Frigorífico", 7.5, 0.5, "frigorifico")
	ed.anadir_referencia(entorno, planta, "Buzón", 50, 50)
	alta = ed.crear_planta(entorno, "Planta primera")
	ed.crear_habitacion_rectangular(entorno, alta, "Dormitorio", 0, 0, 5, 4)
	ed.crear_escalera(entorno, planta, alta, (4, 3), 180, 2, 12)
	texto = ed.describir_entorno(entorno, catalogo)
	lineas = texto.splitlines()
	assert lineas[0] == "Piso mínimo"
	assert lineas[1] == "Un piso para las pruebas."
	assert "Autor: Ana." in lineas
	assert "Tiene 2 plantas y 1 conector entre plantas." in lineas
	assert "Inicio: en Salón, planta Planta baja, mirando al norte." in lineas
	assert "  Vecinos: Cocina al este." in lineas
	assert "  Vecinos: Salón al oeste." in lineas
	assert any(
		linea.startswith("  Puerta entre Salón y Cocina: puerta de 0,82 metros, abierta, en la pared este de Salón") for linea in lineas
	)
	assert any(linea.startswith("  Puerta entre Salón y Cocina:") and "en la pared oeste de Cocina" in linea for linea in lineas)
	assert any(linea.startswith("  Sofá: sofá de 2 de ancho") for linea in lineas)
	assert any(linea.startswith("  Frigorífico: fuente de sonido") and "en Cocina" in linea for linea in lineas)
	# Lo que queda fuera de todo espacio también se cuenta, sin sangría.
	assert any(linea.startswith("Buzón: punto de interés") for linea in lineas)
	assert "Conectores entre plantas:" in lineas
	assert lineas[-1].startswith("  Escalera: escalera, une Planta baja y Planta primera, 12 peldaños")
	assert texto.index("Salón:") < texto.index("Cocina:") < texto.index("Dormitorio:")
	assert ed.describir_entorno(ed.crear_entorno("")).startswith("Entorno sin nombre")


# ── Historial ────────────────────────────────────────────────────────────────


def test_historial_deshacer_y_rehacer_con_nombre():
	entorno, planta, salon, _cocina = piso_minimo()
	historial = Historial()
	assert not historial.puede_deshacer
	assert historial.texto_deshacer() == "Deshacer"
	assert historial.deshacer(entorno) is None
	assert historial.rehacer(entorno) is None

	historial.anotar(entorno, "crear habitación Baño")
	ed.crear_habitacion_adosada(entorno, planta, "Baño", salon, "norte", 2, 2)
	historial.anotar(entorno, "renombrar Salón")
	ed.renombrar(entorno, salon, "Sala")
	assert historial.texto_deshacer() == "Deshacer: renombrar Salón"
	assert historial.operaciones() == ["crear habitación Baño", "renombrar Salón"]

	anterior = historial.deshacer(entorno)
	# Por diferencias: se deshace EN EL SITIO y devuelve el mismo entorno.
	assert anterior is entorno
	assert [e.nombre for e in anterior.plantas[0].espacios] == ["Salón", "Cocina", "Baño"]
	assert historial.texto_deshacer() == "Deshacer: crear habitación Baño"
	assert historial.texto_rehacer() == "Rehacer: renombrar Salón"

	primero = historial.deshacer(anterior)
	assert [e.nombre for e in primero.plantas[0].espacios] == ["Salón", "Cocina"]
	assert not historial.puede_deshacer
	assert historial.puede_rehacer

	rehecho = historial.rehacer(primero)
	assert [e.nombre for e in rehecho.plantas[0].espacios] == ["Salón", "Cocina", "Baño"]
	final = historial.rehacer(rehecho)
	assert final.plantas[0].espacios[0].nombre == "Sala"
	assert final == entorno
	assert not historial.puede_rehacer
	assert historial.texto_rehacer() == "Rehacer"


def test_historial_una_operacion_nueva_borra_lo_rehacible_y_hay_limite():
	entorno, _planta, salon, _cocina = piso_minimo()
	historial = Historial(limite=3)
	for numero in range(5):
		historial.anotar(entorno, f"cambio {numero}")
		ed.renombrar(entorno, salon, f"Salón {numero}")
	assert historial.operaciones() == ["cambio 2", "cambio 3", "cambio 4"]
	atras = historial.deshacer(entorno)
	assert atras.plantas[0].espacios[0].nombre == "Salón 3"
	assert historial.puede_rehacer
	historial.anotar(atras, "otra cosa")
	assert not historial.puede_rehacer
	assert historial.operaciones() == ["cambio 2", "cambio 3", "otra cosa"]
	historial.limpiar()
	assert not historial.puede_deshacer
	assert Historial(limite=0).limite == 1


def test_el_estado_recuperado_conserva_el_contador_de_ids():
	entorno, planta, salon, _cocina = piso_minimo()
	historial = Historial()
	historial.anotar(entorno, "crear Baño")
	bano = ed.crear_habitacion_adosada(entorno, planta, "Baño", salon, "norte", 2, 2)
	anterior = historial.deshacer(entorno)
	nueva = ed.crear_habitacion_adosada(anterior, anterior.plantas[0], "Aseo", anterior.plantas[0].espacios[0], "norte", 2, 2)
	assert len(set(anterior.ids())) == len(anterior.ids())
	assert nueva.id == bano.id or nueva.id.startswith("esp-")
