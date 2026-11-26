"""Presupuesto de tiempo del reproductor con un barrio de 3.000 espacios y cientos de objetos.

Por qué: el profesional importó un barrio de OpenStreetMap y el programa se
colgó. La regla es «nunca la aplicación tiene que quedarse colgada»: ningún
fotograma ni ninguna acción del alumno puede pasar de una décima de segundo
(un parón mayor se nota y un lector de pantalla lo sufre), salvo la carga,
que va anunciada y en segundo plano (``app.reproductor.carga``).

Se hace lo mismo que el reproductor: preparar la sesión con aviso de progreso
(``Sesion`` + ``Sesion.preparar``), y después cientos de fotogramas a 60 Hz
andando, girando y quieto, con los milisegundos de precálculo de caminos de
cada fotograma (``PantallaJuego._precalcular_caminos``); las preguntas de
percepción, una ruta larga y el sonido.

Límites (medidos en el equipo de desarrollo, con margen para un equipo más
lento o cargado):

- fotograma y acción del alumno: 100 ms, el objetivo del proyecto;
- ruta larga (de un extremo a otro de la parte de la plaza a la que se llega
  andando, cientos de metros con celdas de 40 cm): ``LIMITE_RUTA``. Una ruta
  así recorre decenas de miles de celdas; en este equipo tarda unas décimas,
  y no es un fotograma: la piden las actividades al empezar una prueba;
- carga: ``LIMITE_CARGA``, anunciada y sin bloquear el bucle.
"""

from __future__ import annotations

import math
import time
from pathlib import Path

import pytest

from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.motor.sesion import AjustesJuego, Sesion
from app.reproductor.pantallas.juego import PRESUPUESTO_CAMINOS
from tests._entornos_grandes import amueblar, barrio

PLUGINS = Path(__file__).resolve().parent.parent / "data" / "plugins"
DT = 1.0 / 60.0
LIMITE_FOTOGRAMA = 0.1
LIMITE_ACCION = 0.1
LIMITE_RUTA = 2.0
LIMITE_CARGA = 60.0
ACCIONES_PERCEPCION = (
	"donde_estoy",
	"donde_estoy",
	"alrededor",
	"descubiertos",
	"cercano_siguiente",
	"cercano_siguiente",
	"sonda",
	"mirar_delante",
	"mirar_izquierda",
	"eco",
	"brujula",
)


@pytest.fixture(scope="module")
def preparado() -> tuple[Sesion, list[tuple[str, int, int]], float]:
	"""Un barrio de 3.000 espacios con 800 objetos del catálogo, preparado como lo prepara la pantalla de carga."""
	catalogo = Catalogo.cargar([PLUGINS])
	entorno = barrio(3000)
	amueblar(entorno, catalogo, 800)
	fases: list[tuple[str, int, int]] = []

	def progreso(fase: str, hechos: int, total: int) -> None:
		fases.append((fase, hechos, total))

	inicio = time.perf_counter()
	sesion = Sesion(entorno, catalogo, AjustesJuego(modo_movimiento="pasos"), semilla=7, progreso=progreso)
	sesion.preparar(progreso)
	return sesion, fases, time.perf_counter() - inicio


def _fotograma(sesion: Sesion, ordenes: tuple[str, ...] = ()) -> float:
	"""Un fotograma como el del reproductor: órdenes, avanzar, sonido y precálculo de caminos. Devuelve lo que tardó."""
	inicio = time.perf_counter()
	for orden in ordenes:
		sesion.orden(orden)
	sesion.avanzar(DT)
	sesion.fuentes()
	for orden in ordenes:
		sesion.orden(orden, 0)
	jugador = sesion.jugador
	if jugador.modo == "andando":
		sesion.nav.precalcular((jugador.planta, jugador.x, jugador.y), PRESUPUESTO_CAMINOS)
	return time.perf_counter() - inicio


@pytest.mark.lento
@pytest.mark.rendimiento
def test_la_carga_de_un_barrio_grande_va_por_fases_y_a_tiempo(preparado):
	sesion, fases, duracion = preparado
	assert len(sesion.mundo.plantas()[0].espacios) >= 2900
	assert len(sesion.mundo.plantas()[0].objetos) >= 800
	print(f"\nCarga de 3.000 espacios: {duracion:.2f} s")
	assert duracion < LIMITE_CARGA
	nombres = [fase for fase, _h, _t in fases]
	# Las fases llegan en este orden: el plano (plantas, paredes, puertas, objetos), los caminos y el sonido.
	orden = [nombres.index(fase) for fase in ("plantas", "paredes", "aberturas", "objetos", "caminos", "sonido")]
	assert orden == sorted(orden)
	# Muchos avisos: así cancelar responde enseguida aunque cada fase sea larga.
	assert len(fases) >= 10


@pytest.mark.lento
@pytest.mark.rendimiento
def test_ningun_fotograma_ni_accion_pasa_del_limite(preparado):
	sesion, _fases, _duracion = preparado
	tiempos: list[float] = []
	acciones: dict[str, float] = {}
	for numero in range(720):
		ordenes: tuple[str, ...] = ()
		if numero % 8 == 0:
			ordenes = ("avanzar",)
		elif numero % 45 == 0:
			ordenes = ("girar_derecha",)
		tiempos.append(_fotograma(sesion, ordenes))
		if numero % 60 == 30:
			accion = ACCIONES_PERCEPCION[(numero // 60) % len(ACCIONES_PERCEPCION)]
			acciones[f"{accion} ({numero})"] = _fotograma(sesion, (accion,))
	for accion in ACCIONES_PERCEPCION:
		acciones[accion] = _fotograma(sesion, (accion,))
	medio = sum(tiempos) / len(tiempos)
	print(f"\nFotograma: medio {medio * 1000:.1f} ms, máximo {max(tiempos) * 1000:.1f} ms")
	for nombre, segundos in acciones.items():
		print(f"  {nombre}: {segundos * 1000:.1f} ms")
	assert sesion.movimiento.pasos > 30, "el alumno ha andado por el barrio"
	assert max(tiempos) < LIMITE_FOTOGRAMA
	lento = {nombre: round(segundos * 1000) for nombre, segundos in acciones.items() if segundos >= LIMITE_ACCION}
	assert not lento, f"acciones que pasan de {LIMITE_ACCION * 1000:.0f} ms: {lento}"


@pytest.mark.lento
@pytest.mark.rendimiento
def test_ruta_larga_y_sonido_a_tiempo(preparado):
	sesion, _fases, _duracion = preparado
	jugador = sesion.jugador
	indice = sesion.mundo.plantas()[0]
	origen = (jugador.planta, jugador.x, jugador.y)
	# Los extremos de lo alcanzable: el espacio (con el centro dentro y transitable) más lejano al que hay camino.
	candidatos = [
		espacio
		for _caja, espacio in indice.espacios
		if not espacio.macizo
		and geo.punto_en_poligono(espacio.centro(), espacio.contorno)
		and sesion.mundo.transitable(indice.planta.id, *espacio.centro())
	]
	candidatos.sort(key=lambda e: -math.hypot(e.centro()[0] - jugador.x, e.centro()[1] - jugador.y))
	# Primero unos cuantos de las otras copias de la plaza (sin camino) y después el más lejano del trozo del alumno.
	# Lo que el reproductor termina de calcular poco a poco, fotograma a fotograma, se termina aquí de una vez.
	inicio = time.perf_counter()
	assert sesion.nav.precalcular(origen, 1e9)
	print(f"\nResto del precálculo de caminos (en el reproductor va troceado): {time.perf_counter() - inicio:.2f} s")
	suyo = sesion.nav.componente(origen)
	assert suyo is not None
	sin_camino = [e for e in candidatos if sesion.nav.componente((indice.planta.id, *e.centro())) != suyo][:10]
	con_camino = [e for e in candidatos if sesion.nav.componente((indice.planta.id, *e.centro())) == suyo]
	assert sin_camino and con_camino
	medidas: list[tuple[str, float]] = []
	ruta = None
	for espacio in sin_camino + con_camino[:20]:
		destino = (indice.planta.id, *espacio.centro())
		inicio = time.perf_counter()
		ruta = sesion.nav.ruta(origen, destino)
		segundos = time.perf_counter() - inicio
		medidas.append((espacio.nombre, segundos))
		if ruta is not None:
			break
	assert ruta is not None, "hay algún sitio lejano al que se llega andando"
	print(
		f"\nRuta de {ruta.longitud:.0f} m: {medidas[-1][1] * 1000:.0f} ms; sin camino: {max((s for _n, s in medidas[:-1]), default=0) * 1000:.1f} ms"
	)
	assert ruta.longitud > 100.0
	assert medidas[-1][1] < LIMITE_RUTA
	# Los destinos sin camino se saben al momento: el trozo del alumno ya está entero calculado.
	assert all(segundos < LIMITE_ACCION for _nombre, segundos in medidas[:-1])
	# Recalcular la misma ruta (la baliza lo hace al moverse) tampoco pasa del límite.
	inicio = time.perf_counter()
	assert sesion.nav.ruta(origen, (indice.planta.id, *espacio.centro())) is not None
	assert time.perf_counter() - inicio < LIMITE_RUTA
	inicio = time.perf_counter()
	sesion.acustica._cache_en = None
	sesion.fuentes()
	assert time.perf_counter() - inicio < LIMITE_ACCION
