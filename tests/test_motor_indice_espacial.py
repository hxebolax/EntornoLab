"""Índices y cachés del motor para entornos grandes: dan EXACTAMENTE lo mismo que la búsqueda exhaustiva.

Por qué: para que un barrio importado de OpenStreetMap no cuelgue el
reproductor, el motor dejó de recorrer todas las listas (espacios, objetos,
aberturas, referencias, fuentes) en cada consulta y guarda cálculos (tráfico,
componentes conexas de los caminos, celdas precalculadas). Estas pruebas
comparan cada atajo con la versión de fuerza bruta (la que había antes, copiada
aquí) sobre la muestra real de la Plaza Mayor de Valladolid, y comprueban que lo
guardado se tira cuando cambia lo que lo invalida (una puerta con llave).
"""

from __future__ import annotations

import math
import random
from pathlib import Path

import pytest

from app.dominio import geometria as geo
from app.dominio import modelo
from app.dominio.catalogo import Catalogo
from app.dominio.formato import cargar_paquete
from app.motor import dinamica as din
from app.motor.indice_espacial import MAX_CELDAS, RejillaCajas
from app.motor.mundo import MARGEN_SALIDA, Mundo
from app.motor.navegacion import Navegador
from tests._entornos_grandes import amueblar, plaza_real
from tests.test_motor_comun import Robot

PLUGINS = Path(__file__).resolve().parent.parent / "data" / "plugins"
VIVIENDA = Path(__file__).resolve().parent.parent / "data" / "ejemplos" / "vivienda-de-ejemplo.elab"


@pytest.fixture(scope="module")
def catalogo() -> Catalogo:
	"""El catálogo real (la carpeta de datos de las pruebas es temporal: se pasa la de complementos explícita)."""
	return Catalogo.cargar([PLUGINS])


@pytest.fixture(scope="module")
def plaza(catalogo: Catalogo) -> tuple[modelo.Entorno, Mundo]:
	"""La plaza real con 150 objetos del catálogo, ya indexada."""
	entorno = plaza_real()
	amueblar(entorno, catalogo, 150)
	return entorno, Mundo(entorno, catalogo)


def _puntos(mundo: Mundo, cuantos: int, semilla: int = 3) -> list[tuple[float, float]]:
	"""Puntos al azar por toda la planta (y un poco fuera), y también los centros de espacios y objetos."""
	indice = mundo.plantas()[0]
	x0, y0, x1, y1 = indice.caja
	azar = random.Random(semilla)
	puntos = [(azar.uniform(x0 - 5, x1 + 5), azar.uniform(y0 - 5, y1 + 5)) for _i in range(cuantos)]
	puntos += [espacio.centro() for _caja, espacio in indice.espacios[:80]]
	puntos += [(info.objeto.x, info.objeto.y) for info in indice.objetos[:80]]
	puntos += [info.centro for info in indice.aberturas[:80]]
	return puntos


# ── La rejilla ──


def test_la_rejilla_da_lo_mismo_que_mirar_todas_las_cajas():
	azar = random.Random(11)
	rejilla = RejillaCajas(4.0)
	cajas = []
	for _i in range(400):
		x, y = azar.uniform(-100, 100), azar.uniform(-100, 100)
		caja = (x, y, x + azar.uniform(0, 12), y + azar.uniform(0, 12))
		cajas.append(caja)
		rejilla.meter(caja)
	# Una enorme (va a la lista que se mira siempre) y una con datos rotos.
	cajas.append((-1e5, -1e5, 1e5, 1e5))
	assert rejilla.meter(cajas[-1]) == 400
	cajas.append((math.nan, 0.0, 1.0, 1.0))
	rejilla.meter(cajas[-1])
	assert len(rejilla) == 402
	for _i in range(300):
		x, y = azar.uniform(-120, 120), azar.uniform(-120, 120)
		lado = azar.choice((0.0, 0.5, 3.0, 20.0, 300.0))
		zona = (x - lado, y - lado, x + lado, y + lado)
		esperado = [
			n
			for n, (a, b, c, d) in enumerate(cajas)
			if not all(math.isfinite(v) for v in (a, b, c, d)) or not (c < zona[0] or a > zona[2] or d < zona[1] or b > zona[3])
		]
		obtenido = rejilla.en_caja(*zona)
		# La rejilla puede dar de más (vecinas de celda), nunca de menos, y siempre ordenado y sin repetir.
		assert set(esperado) <= set(obtenido)
		assert obtenido == sorted(set(obtenido))
		assert set(esperado) <= set(rejilla.en_punto(x, y)) or lado > 0
	assert rejilla.en_punto(math.inf, 0.0) == list(range(402))
	assert MAX_CELDAS > 100


# ── Consultas del mundo ──


def _espacio_exhaustivo(mundo: Mundo, x: float, y: float, macizos: bool) -> modelo.Espacio | None:
	for (x0, y0, x1, y1), espacio in mundo.plantas()[0].espacios:
		if x < x0 - 1e-6 or x > x1 + 1e-6 or y < y0 - 1e-6 or y > y1 + 1e-6:
			continue
		if espacio.macizo and not macizos:
			continue
		if geo.punto_en_poligono((x, y), espacio.contorno):
			return espacio
	return None


def _transitable_exhaustivo(mundo: Mundo, x: float, y: float) -> bool:
	indice = mundo.plantas()[0]
	espacio = _espacio_exhaustivo(mundo, x, y, True)
	if espacio is not None:
		return not espacio.macizo
	return any(info.abertura.tipo != "ventana" and info.sobre_pared and info.distancia(x, y) <= MARGEN_SALIDA for info in indice.aberturas)


def test_espacio_suelo_y_paso_dan_lo_mismo_que_la_busqueda_exhaustiva(plaza):
	_entorno, mundo = plaza
	indice = mundo.plantas()[0]
	planta = indice.planta.id
	for x, y in _puntos(mundo, 1500):
		for macizos in (False, True):
			assert mundo._espacio_en(indice, x, y, macizos) is _espacio_exhaustivo(mundo, x, y, macizos)
		assert mundo.transitable(planta, x, y) == _transitable_exhaustivo(mundo, x, y)
		zona = next(
			(z for (a, b, c, d), z in indice.zonas if a <= x <= c and b <= y <= d and geo.punto_en_poligono((x, y), z.contorno)), None
		)
		assert mundo.zona_en(planta, x, y) is zona
		for fijos in (False, True):
			dentro = next(
				(
					info
					for info in indice.objetos
					if not (fijos and info.paso_libre)
					and info.caja[0] <= x <= info.caja[2]
					and info.caja[1] <= y <= info.caja[3]
					and mundo.corta_el_paso(info)
					and info.altura_base < 1.75
					and geo.punto_en_poligono((x, y), info.huella)
				),
				None,
			)
			assert mundo.dentro_de_objeto(planta, x, y, fijos) is dentro


def test_lo_cercano_da_lo_mismo_y_en_el_mismo_orden(plaza):
	_entorno, mundo = plaza
	indice = mundo.plantas()[0]
	planta = indice.planta.id
	for x, y in _puntos(mundo, 300):
		for radio in (0.9, 1.5, 5.0, 20.0, 60.0):
			objetos = sorted(
				(
					(info.distancia(x, y), info)
					for info in indice.objetos
					if not (x < info.caja[0] - radio or x > info.caja[2] + radio or y < info.caja[1] - radio or y > info.caja[3] + radio)
				),
				key=lambda par: par[0],
			)
			assert mundo.objetos_cerca(planta, x, y, radio) == [par for par in objetos if par[0] <= radio]
			aberturas = sorted(
				(
					(info.distancia(x, y), info)
					for info in indice.aberturas
					if abs(info.centro[0] - x) < radio + 3.0 and abs(info.centro[1] - y) < radio + 3.0
				),
				key=lambda par: par[0],
			)
			assert mundo.aberturas_cerca(planta, x, y, radio) == [par for par in aberturas if par[0] <= radio]
			referencias = sorted(((math.hypot(r.x - x, r.y - y), r) for r in indice.planta.referencias), key=lambda par: par[0])
			assert mundo.referencias_cerca(planta, x, y, radio) == [par for par in referencias if par[0] <= radio]
			fuentes = sorted(((math.hypot(f.x - x, f.y - y), f) for f in indice.planta.fuentes), key=lambda par: par[0])
			assert mundo.fuentes_cerca(planta, x, y, radio) == [par for par in fuentes if par[0] <= radio]
	# Con un radio infinito no hay rejilla que valga: se mira todo.
	assert len(mundo.referencias_cerca(planta, 0.0, 0.0, math.inf)) == len(indice.planta.referencias)


def test_las_aberturas_sobre_pared_son_las_de_la_regla_del_modelo(plaza):
	entorno, mundo = plaza
	planta = entorno.plantas[0]

	def sobre_pared(abertura: modelo.Abertura) -> bool:
		for espacio in planta.espacios:
			if len(espacio.contorno) < 3 or espacio.macizo or not espacio.cerrado:
				continue
			for indice, (a, b) in enumerate(espacio.lados()):
				if indice not in espacio.lados_abiertos and geo.intervalo_sobre_segmento(a, b, abertura.a, abertura.b, 0.05) is not None:
					return True
		return any(geo.intervalo_sobre_segmento(p.a, p.b, abertura.a, abertura.b, 0.05) is not None for p in planta.paredes)

	assert planta.aberturas
	for abertura in planta.aberturas:
		assert mundo.abertura(abertura.id).sobre_pared == sobre_pared(abertura), abertura.id


def test_los_elementos_por_id_son_los_del_entorno(plaza):
	entorno, mundo = plaza
	ids = [planta.id for planta in entorno.plantas] + [elemento.id for _planta, elemento in entorno.elementos()]
	for ident in ids[:: max(1, len(ids) // 400)] + ["no-existe", ""]:
		assert mundo.elemento(ident) is entorno.elemento(ident)


def test_preseleccion_de_aberturas_y_espacios_por_caja(plaza):
	_entorno, mundo = plaza
	indice = mundo.plantas()[0]
	planta = indice.planta.id
	azar = random.Random(5)
	x0, y0, x1, y1 = indice.caja
	for _i in range(200):
		x, y = azar.uniform(x0, x1), azar.uniform(y0, y1)
		zona = (x - 4.0, y - 4.0, x + 4.0, y + 4.0)
		tocan = [
			info
			for info in indice.aberturas
			if not (
				max(info.abertura.a[0], info.abertura.b[0]) < zona[0]
				or min(info.abertura.a[0], info.abertura.b[0]) > zona[2]
				or max(info.abertura.a[1], info.abertura.b[1]) < zona[1]
				or min(info.abertura.a[1], info.abertura.b[1]) > zona[3]
			)
		]
		elegidas = mundo.aberturas_en_caja(planta, *zona)
		assert all(info in elegidas for info in tocan)
		assert elegidas == [info for info in indice.aberturas if info in elegidas], "en el orden de la planta"
		espacios = mundo.espacios_en_caja(planta, *zona)
		assert espacios == [e for _c, e in indice.espacios if e in espacios], "de menor a mayor área"


# ── Caminos: componentes conexas y precálculo ──
#
# Con la vivienda de ejemplo (interior, celdas de 20 cm): un trozo entero se calcula en un momento.
# Con una puerta con llave, un dormitorio queda en otro trozo, sin camino: así hay rutas que no existen.


@pytest.fixture
def vivienda() -> tuple[modelo.Entorno, Catalogo]:
	"""La vivienda de ejemplo, con el catálogo de prueba vacío (sus objetos se ven como cajas)."""
	paquete = cargar_paquete(VIVIENDA)
	return paquete.entorno, Catalogo()


def _lugares(mundo: Mundo, cuantos: int, semilla: int = 9) -> list[tuple[str, float, float]]:
	indice = mundo.plantas()[0]
	azar = random.Random(semilla)
	espacios = [e for _c, e in indice.espacios if not e.macizo and geo.punto_en_poligono(e.centro(), e.contorno)]
	lugares = [(indice.planta.id, *e.centro()) for e in espacios]
	lugares += [
		(indice.planta.id, azar.uniform(indice.caja[0], indice.caja[2]), azar.uniform(indice.caja[1], indice.caja[3]))
		for _i in range(cuantos)
	]
	return lugares


def _comparar_con_uno_nuevo(mundo: Mundo, conocedor: Navegador, origen: tuple[str, float, float]) -> int:
	"""Compara rutas y campos del navegador que ya conoce trozos con los de uno recién hecho. Devuelve cuántas rutas no existen."""
	sin_ruta = 0
	for destino in _lugares(mundo, 12):
		esperada = Navegador(mundo).ruta(origen, destino)
		obtenida = conocedor.ruta(origen, destino)
		assert (esperada is None) == (obtenida is None), destino
		if esperada is None:
			sin_ruta += 1
		else:
			assert obtenida.puntos == esperada.puntos
			assert obtenida.longitud == esperada.longitud
		campo_nuevo = Navegador(mundo).distancias_desde(destino, 6.0)
		campo = conocedor.distancias_desde(destino, 6.0)
		assert (campo is None) == (campo_nuevo is None)
		if campo is not None:
			assert campo.distancias == campo_nuevo.distancias
	return sin_ruta


def test_los_trozos_ya_conocidos_dan_las_mismas_rutas(vivienda):
	entorno, catalogo = vivienda
	mundo = Mundo(entorno, catalogo)
	assert mundo.poner_abertura("abe-13", "con_llave")
	conocedor = Navegador(mundo)
	origen = (entorno.inicio.planta, entorno.inicio.x, entorno.inicio.y)
	# Primero se conoce entero el trozo del origen (es lo que hace el reproductor poco a poco).
	assert conocedor.precalcular(origen, 1e9)
	assert conocedor.componente(origen) is not None
	assert _comparar_con_uno_nuevo(mundo, conocedor, origen) > 0, "con la llave echada hay sitios a los que no se llega"
	# Una búsqueda que no encuentra la meta recorre su trozo entero y también lo apunta.
	otro = Navegador(mundo)
	destino_cerrado = next(d for d in _lugares(mundo, 12) if Navegador(mundo).ruta(origen, d) is None)
	assert otro.ruta(origen, destino_cerrado) is None
	assert otro.componente(origen) is not None


def test_echar_la_llave_tira_los_trozos_conocidos(vivienda):
	entorno, catalogo = vivienda
	mundo = Mundo(entorno, catalogo)
	nav = Navegador(mundo)
	origen = (entorno.inicio.planta, entorno.inicio.x, entorno.inicio.y)
	assert nav.precalcular(origen, 1e9)
	assert nav._componentes
	assert mundo.poner_abertura("abe-13", "con_llave")
	nav._comprobar_firma()
	assert not nav._componentes, "con otra puerta cerrada con llave, los trozos pueden ser otros"
	assert nav.componente(origen) is None
	assert nav.precalcular(origen, 1e9)
	assert _comparar_con_uno_nuevo(mundo, nav, origen) > 0
	# Abrir o cerrar sin llave no cambia por dónde se puede ir: lo conocido sigue valiendo.
	assert mundo.poner_abertura("abe-12", "abierta")
	nav._comprobar_firma()
	assert nav._componentes
	# Quitar la llave sí: se vuelve a calcular y vuelve a haber camino a todas partes.
	assert mundo.poner_abertura("abe-13", "cerrada")
	nav._comprobar_firma()
	assert not nav._componentes
	assert _comparar_con_uno_nuevo(mundo, nav, origen) == 0


def test_precalcular_se_puede_trocear_y_da_lo_mismo(vivienda):
	entorno, catalogo = vivienda
	mundo = Mundo(entorno, catalogo)
	nav = Navegador(mundo)
	origen = (entorno.inicio.planta, entorno.inicio.x, entorno.inicio.y)
	vueltas = 0
	while not nav.precalcular(origen, 0.0):
		vueltas += 1
		assert vueltas < 100000
	assert vueltas > 0, "con presupuesto cero se trabaja a trozos, de fotograma en fotograma"
	entero = Navegador(mundo)
	assert entero.precalcular(origen, 1e9)
	numero = nav.componente(origen)
	numero_entero = entero.componente(origen)
	trozo = {c for c, n in nav._componentes[origen[0]].items() if n == numero}
	assert trozo == {c for c, n in entero._componentes[origen[0]].items() if n == numero_entero}
	# Lo mismo que recorre una búsqueda completa desde ahí.
	campo = Navegador(mundo).distancias_desde(origen)
	assert set(campo.distancias) == trozo
	assert _comparar_con_uno_nuevo(mundo, nav, origen) == 0


# ── Tráfico ──


def _trafico_antiguo(self: din.Dinamica, dt: float) -> None:
	"""El tráfico tal como se calculaba antes de guardar los datos fijos de cada vía (la referencia)."""
	s = self.s
	jugador = s.jugador
	if jugador.planta != self._planta_trafico:
		self._planta_trafico = jugador.planta
		self._poblar()
	vias = self._vias()
	if not vias:
		return
	for via in vias:
		media = din.INTERVALO_TRAFICO[via.trafico]
		for sentido in self._sentidos(via):
			clave = (via.id, sentido)
			self._esperas[clave] = self._esperas.get(clave, media) - dt
			if self._esperas[clave] <= 0.0:
				self._esperas[clave] = max(2.5, s.azar.expovariate(1.0 / media))
				primero = min((v.d for v in self.vehiculos if v.via is via and v.sentido == sentido), default=math.inf)
				if primero > din.SEPARACION * 1.5:
					self.vehiculos.append(self._nuevo_vehiculo(via, sentido, 0.0))
	espacio = s.mundo.espacio_en(jugador.planta, jugador.x, jugador.y) if jugador.modo == "andando" else None
	en_calzada = espacio is not None and espacio.tipo in din.TIPOS_CALZADA
	indice = s.mundo.planta(jugador.planta)
	pasos = [e for _caja, e in indice.espacios if e.tipo == "paso_peatones"]
	for vehiculo in self.vehiculos:
		via = vehiculo.via
		hueco = math.inf
		vehiculo.frena_por_alumno = False
		for otro in self.vehiculos:
			if otro is not vehiculo and otro.via is via and otro.sentido == vehiculo.sentido and otro.d > vehiculo.d:
				hueco = min(hueco, otro.d - vehiculo.d - din.SEPARACION)
		for paso in pasos:
			if paso.datos.get("via") != via.id:
				continue
			ancho = float(paso.datos.get("ancho") or 4.0) if isinstance(paso.datos.get("ancho"), (int, float)) else 4.0
			linea = self._posicion_en_eje(via, paso.centro(), vehiculo.sentido) - ancho / 2.0 - 1.5
			if linea < vehiculo.d - 0.5:
				continue
			fase_paso = self.fase(paso.id)
			if fase_paso:
				if fase_paso != "rojo":
					hueco = min(hueco, linea - vehiculo.d)
			elif espacio is not None and espacio.id == paso.id:
				hueco = min(hueco, linea - vehiculo.d)
				if linea - vehiculo.d < vehiculo.v * vehiculo.v / (2.0 * din.FRENADA) - 1.0:
					vehiculo.frena_por_alumno = True
		if en_calzada:
			delante = self._posicion_en_eje(via, jugador.punto, vehiculo.sentido) - vehiculo.d
			dx, dy = geo.vector_rumbo(vehiculo.rumbo)
			de_lado = abs((jugador.x - vehiculo.x) * dy - (jugador.y - vehiculo.y) * dx)
			if abs(delante) < 3.0 and vehiculo.v > 2.0 and de_lado < via.ancho / 2.0 + vehiculo.lateral + 0.5:
				vehiculo.frena_por_alumno = True
			if 0.0 < delante < 30.0 and de_lado < 2.2:
				if delante - 3.0 < hueco:
					hueco = delante - 3.0
					if (
						vehiculo.v > 2.0
						and delante < 18.0
						and (espacio is None or espacio.tipo != "paso_peatones" or self.fase(espacio.id))
					):
						vehiculo.frena_por_alumno = True
		if hueco <= 0.3:
			deseada = 0.0
		elif hueco < math.inf:
			deseada = min(vehiculo.v_max, math.sqrt(2.0 * din.FRENADA * hueco))
		else:
			deseada = vehiculo.v_max
		if deseada < vehiculo.v:
			vehiculo.v = max(deseada, vehiculo.v - din.FRENADA * 2.5 * dt)
		else:
			vehiculo.v = min(deseada, vehiculo.v + din.ACELERACION * dt)
		vehiculo.d += vehiculo.v * dt
		self._situar(vehiculo)
	self.vehiculos = [v for v in self.vehiculos if v.d <= geo.longitud_linea(v.via.eje) + 2.0]


def _foto_trafico(robot: Robot) -> list[tuple]:
	return [(v.id, v.via.id, v.sentido, v.d, v.v, v.x, v.y, v.frena_por_alumno) for v in robot.sesion.dinamica.vehiculos]


def test_el_trafico_es_identico_al_de_antes(monkeypatch, catalogo):
	"""Con la misma semilla, cada vehículo está en el mismo sitio y a la misma velocidad en cada fotograma."""
	entorno = plaza_real()
	calzada = next(e for e in entorno.plantas[0].espacios if e.tipo == "calzada" and not e.macizo)
	nuevo = Robot(entorno, catalogo, semilla=21, trafico=True)
	antiguo = Robot(entorno, catalogo, semilla=21, trafico=True)
	monkeypatch.setattr(antiguo.sesion.dinamica, "_trafico", _trafico_antiguo.__get__(antiguo.sesion.dinamica))
	assert nuevo.sesion.dinamica._vias(), "la plaza tiene calles con tráfico"
	for numero in range(400):
		if numero == 150:
			# El alumno se pone en medio de la calzada: los coches frenan por él.
			for robot in (nuevo, antiguo):
				robot.sesion.recolocar(modelo.Posicion(entorno.plantas[0].id, *calzada.centro(), 0.0))
		nuevo.tic(1)
		antiguo.tic(1)
		assert _foto_trafico(nuevo) == _foto_trafico(antiguo), f"fotograma {numero}"
	assert _foto_trafico(nuevo)
