"""Propiedad fundamental del historial por diferencias: deshacer y rehacer dejan el entorno IDÉNTICO.

Por qué existe: el historial ya no guarda una copia del entorno entero, sino
lo que cambia cada operación (``app.dominio.diferencias``), y lo aplica sobre
el mismo entorno. Si a un parche se le escapara algo, deshacer dejaría el
entorno «casi» como estaba, y eso no se ve hasta que el alumno se choca con
una pared que no debería estar. Aquí se hace una secuencia larga y variada de
operaciones de edición y colocación (todas las de ``edicion`` y
``colocacion``, también las que fallan a medias) en los entornos de ejemplo y
en un barrio grande, y se comprueba:

- deshacer todo devuelve un entorno cuyo ``a_dict`` es idéntico al inicial, y
  cada paso intermedio idéntico al que había; rehacer todo, igual hasta el final;
- deshacer y rehacer alternados al azar (con semilla fija), lo mismo;
- tras cada paso, el índice espacial de cada planta da lo mismo que la
  búsqueda exhaustiva (``espacios_en_exhaustivo``), y el contenido de cada
  espacio (lo que el árbol del Estudio calcula por partes) lo mismo que
  calculado desde cero;
- una operación que falla a medias no deja rastro;
- el historial no crece sin medida (cien movimientos en un barrio de 3.000
  espacios ocupan kilobytes, no cientos de megas).
"""

from __future__ import annotations

import marshal
import random
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from app.dominio import colocacion as co
from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.diferencias import ErrorParche, comparar, tomar_foto
from app.dominio.edicion import ErrorEdicion, Historial
from app.dominio.modelo import Entorno, Espacio, Objeto, Planta, invalidar_indices
from app.ui import operaciones
from tests import _entornos_grandes as eg

PLUGINS = Path(__file__).resolve().parent.parent / "data" / "plugins"


@pytest.fixture(scope="module")
def catalogo() -> Catalogo:
	return Catalogo.cargar([PLUGINS])


# ── Operaciones al azar ──────────────────────────────────────────────────────


def _planta(entorno: Entorno, azar: random.Random) -> Planta:
	if not entorno.plantas:
		raise ErrorEdicion("sin plantas")
	return azar.choice(entorno.plantas)


def _espacio(planta: Planta, azar: random.Random, minimo: int = 3) -> Espacio:
	candidatos = [e for e in planta.espacios if len(e.contorno) >= minimo]
	if not candidatos:
		raise ErrorEdicion("sin espacios")
	return azar.choice(candidatos)


def _elemento(entorno: Entorno, azar: random.Random) -> Any:
	todos = [elemento for _planta, elemento in entorno.elementos()] + list(entorno.plantas)
	if not todos:
		raise ErrorEdicion("vacío")
	return azar.choice(todos)


def _lejos(planta: Planta, azar: random.Random) -> tuple[float, float]:
	"""Un punto libre a un lado de la planta (para crear sin pisar nada)."""
	x0, y0, x1, y1 = planta.caja() if planta.espacios or planta.paredes or planta.vias else (0.0, 0.0, 0.0, 0.0)
	return x1 + 5.0 + azar.uniform(0.0, 30.0), y0 + azar.uniform(0.0, max(1.0, y1 - y0))


def _punto_en(espacio: Espacio, azar: random.Random) -> tuple[float, float]:
	x, y = espacio.centro()
	return x + azar.uniform(-0.3, 0.3), y + azar.uniform(-0.3, 0.3)


def op_crear_planta(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	ed.crear_planta(e, exterior=azar.random() < 0.3)


def op_habitacion(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	x, y = _lejos(planta, azar)
	ed.crear_habitacion_rectangular(e, planta, f"Cuarto {azar.randint(1, 999)}", x, y, azar.uniform(2, 6), azar.uniform(2, 5))


def op_adosada(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	junto = _espacio(planta, azar)
	ed.crear_habitacion_adosada(e, planta, "Adosada", junto, azar.choice(["norte", "sur", "este", "oeste"]), 3, 3, "centro")


def op_poligonal(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	x, y = _lejos(planta, azar)
	ed.crear_espacio_poligonal(
		e, planta, "Plaza", [(x, y), (x + 8, y), (x + 4, y + 6)], tipo=azar.choice(["plaza", "habitacion", "parque"])
	)


def op_puerta(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	ed.anadir_puerta(e, planta, _espacio(planta, azar), azar.choice(["norte", "sur", "este", "oeste"]), ancho=0.8)


def op_puerta_entre(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	espacio = _espacio(planta, azar)
	vecinos = ed.vecinos(planta, espacio)
	if not vecinos:
		raise ErrorEdicion("sin vecinos")
	ed.anadir_puerta_entre(e, planta, espacio, azar.choice(vecinos)[0], ancho=0.7)


def op_portal(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	ed.anadir_portal(e, planta, _espacio(planta, azar), azar.choice(["norte", "sur", "este", "oeste"]))


def op_pared(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	x, y = _lejos(planta, azar)
	ed.anadir_pared(e, planta, (x, y), (x + azar.uniform(1, 5), y + azar.uniform(-2, 2)), material=azar.choice(["ladrillo", "valla"]))


def op_fuente(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	ed.anadir_fuente(e, planta, "Reloj", *_punto_en(_espacio(planta, azar), azar), sonido=azar.choice(["reloj", ""]))


def op_referencia(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	ed.anadir_referencia(e, planta, "Banco", *_punto_en(_espacio(planta, azar), azar), tipo="mobiliario")


def op_parada(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	ed.crear_parada(e, planta, "Parada", *_lejos(planta, azar))


def op_zona(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	x, y = _punto_en(_espacio(planta, azar), azar)
	ed.anadir_zona_suelo(e, planta, "Alfombra", geo.rectangulo(x - 0.4, y - 0.3, 0.8, 0.6), azar.choice(["alfombra", "tactil_rayas"]))


def _dos_plantas(e: Entorno) -> tuple[Planta, Planta]:
	if len(e.plantas) < 2:
		raise ErrorEdicion("una planta")
	plantas = sorted(e.plantas, key=lambda p: p.altura_m)
	return plantas[0], plantas[-1]


def op_escalera(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	abajo, arriba = _dos_plantas(e)
	ed.crear_escalera(e, abajo, arriba, _lejos(abajo, azar), azar.uniform(0, 360), 4.0, 14)


def op_rampa(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	abajo, arriba = _dos_plantas(e)
	ed.crear_rampa(e, abajo, arriba, _lejos(abajo, azar), 90.0, azar.choice([6.0, -1.0]))


def op_ascensor(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	ed.crear_ascensor(e, list(e.plantas), _lejos(e.plantas[0], azar) if e.plantas else (0, 0), 0.0)


def op_calle(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	x, y = _lejos(planta, azar)
	calle = ed.crear_calle(e, planta, f"Calle {azar.randint(1, 99)}", [(x, y), (x + 40, y)])
	if azar.random() < 0.5:
		otra = ed.crear_calle(e, planta, "Travesía", [(x + 20, y - 20), (x + 20, y + 20)])
		ed.crear_cruce(e, planta, calle, otra)
	ed.crear_paso_peatones(e, planta, calle, (x + 8, y), semaforo=True, sonoro=True, isleta=azar.random() < 0.5)


def op_edificio(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	x, y = _lejos(planta, azar)
	ed.crear_edificio(e, planta, "Edificio", x, y, 10, 8, portal_lado=azar.choice(["sur", None]))


def op_manzana(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	x, y = _lejos(planta, azar)
	ed.crear_manzana(e, planta, "Manzana", [(x, y), (x + 20, y), (x + 20, y + 15), (x, y + 15)])


def op_inicio(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	ed.fijar_inicio(e, planta, *_punto_en(_espacio(planta, azar), azar), azar.uniform(0, 360))


def op_mover(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	ed.mover(e, _elemento(e, azar), azar.uniform(-3, 3), azar.uniform(-3, 3), con_contenido=azar.random() < 0.8)


def op_mover_espacio(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	planta = _planta(e, azar)
	ed.mover(e, _espacio(planta, azar), azar.uniform(-2, 2), azar.uniform(-2, 2))


def op_mover_a(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	ed.mover_a(e, _elemento(e, azar), azar.uniform(-20, 20), azar.uniform(-20, 20))


def op_girar(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	ed.girar(e, _elemento(e, azar), azar.choice([90.0, -45.0, 30.0]))


def op_redimensionar(e: Entorno, azar: random.Random, cat: Catalogo) -> None:
	ed.redimensionar(e, _elemento(e, azar), ancho=azar.uniform(0.5, 6), fondo=azar.uniform(0.5, 6), alto=azar.uniform(0.5, 3), catalogo=cat)


def op_renombrar(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	ed.renombrar(e, _elemento(e, azar), azar.choice(["Nuevo nombre", "", "Otro"]))


def op_duplicar(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	ed.duplicar(e, _elemento(e, azar), azar.uniform(0, 2), azar.uniform(0, 2))


def op_borrar(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	ed.borrar(e, _elemento(e, azar))


def op_borrar_conector(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	if not e.conectores:
		raise ErrorEdicion("sin conectores")
	ed.borrar(e, azar.choice(e.conectores))


def op_colocar_pared(e: Entorno, azar: random.Random, cat: Catalogo) -> None:
	planta = _planta(e, azar)
	definicion = azar.choice([d for d in cat.objetos() if d.se_puede_usar])
	resultado = co.colocar_contra_pared(e, planta, _espacio(planta, azar), definicion.tipo, cat, azar.choice(["norte", "sur", "este"]))
	if not resultado.colocado:
		raise ErrorEdicion("no cabe")


def op_colocar_esquina(e: Entorno, azar: random.Random, cat: Catalogo) -> None:
	planta = _planta(e, azar)
	definicion = azar.choice([d for d in cat.objetos() if d.se_puede_usar])
	co.colocar_en_esquina(e, planta, _espacio(planta, azar), definicion.tipo, cat, azar.choice(["noreste", "suroeste"]), forzar=True)


def op_colocar_junto(e: Entorno, azar: random.Random, cat: Catalogo) -> None:
	planta = _planta(e, azar)
	if not planta.objetos:
		raise ErrorEdicion("sin objetos")
	definicion = azar.choice([d for d in cat.objetos() if d.se_puede_usar])
	co.colocar_junto_a(e, planta, azar.choice(planta.objetos), definicion.tipo, cat, "este", forzar=True)


def op_colocar_punto(e: Entorno, azar: random.Random, cat: Catalogo) -> None:
	planta = _planta(e, azar)
	definicion = azar.choice([d for d in cat.objetos() if d.se_puede_usar])
	co.colocar_en_punto(e, planta, definicion.tipo, cat, *_punto_en(_espacio(planta, azar), azar), forzar=True)


def op_colocar(e: Entorno, azar: random.Random, cat: Catalogo) -> None:
	planta = _planta(e, azar)
	definicion = azar.choice([d for d in cat.objetos() if d.se_puede_usar])
	objeto = cat.crear_objeto(definicion.tipo, *_punto_en(_espacio(planta, azar), azar))
	co.colocar(e, planta, objeto, cat, forzar=True)


def op_amueblar(e: Entorno, azar: random.Random, cat: Catalogo) -> None:
	planta = _planta(e, azar)
	co.amueblar_espacio(e, planta, _espacio(planta, azar), azar.choice(sorted(co.USOS)), cat)


def op_a_mano(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	"""Cambios que no pasan por ninguna función de edición: también tienen que quedar en el parche."""
	planta = _planta(e, azar)
	opcion = azar.randrange(9)
	if opcion == 7 and planta.espacios:
		# En el sitio, dentro de una lista anidada: lo que vuelve al deshacer no puede compartirla con el historial.
		azar.choice(planta.espacios).datos.setdefault("marcas", []).append(azar.randint(0, 9))
		return
	if opcion == 8:
		e.procedencia.setdefault("rutas", []).append({"nombre": "Paseo", "puntos": [[0, 0], [2, 2]]})
		return
	if opcion == 0:
		planta.nombre = f"Planta {azar.randint(1, 99)}"
		planta.altura_m += 0.5
	elif opcion == 1 and planta.espacios:
		espacio = azar.choice(planta.espacios)
		espacio.datos["nota"] = [azar.randint(0, 9), {"anidado": "sí"}]
		espacio.lados_abiertos = [0]
	elif opcion == 2:
		e.nombre = f"Entorno {azar.randint(1, 99)}"
		e.procedencia = {"rutas": [{"nombre": "GPX", "puntos": [[0, 0], [1, 1]]}]}
		e.complementos.append("prueba")
	elif opcion == 3 and len(e.plantas) > 1:
		e.plantas.reverse()
	elif opcion == 4 and len(planta.objetos) > 2:
		planta.objetos.reverse()
	elif opcion == 5 and len(planta.referencias) > 1:
		# Quitar uno y poner otro (el mismo objeto dos veces en la lista: el parche la da entera por cambiada).
		del planta.referencias[azar.randrange(len(planta.referencias))]
		planta.referencias.insert(0, planta.referencias[-1])
	else:
		planta.objetos.append(Objeto(id=e.nuevo_id("obj"), nombre="Caja suelta", x=1.0, y=1.0, datos={"t": (1, 2, 3)}))


def op_falla_a_medias(e: Entorno, azar: random.Random, _cat: Catalogo) -> None:
	"""Cambia algo y LUEGO falla: el historial tiene que dejarlo como estaba."""
	op_mover(e, azar, _cat)
	op_referencia(e, azar, _cat)
	raise ErrorEdicion("falla después de cambiar")


OPERACIONES: tuple[Callable[[Entorno, random.Random, Catalogo], None], ...] = (
	op_crear_planta,
	op_habitacion,
	op_adosada,
	op_poligonal,
	op_puerta,
	op_puerta_entre,
	op_portal,
	op_pared,
	op_fuente,
	op_referencia,
	op_parada,
	op_zona,
	op_escalera,
	op_rampa,
	op_ascensor,
	op_calle,
	op_edificio,
	op_manzana,
	op_inicio,
	op_mover,
	op_mover_espacio,
	op_mover_espacio,
	op_mover_a,
	op_girar,
	op_redimensionar,
	op_renombrar,
	op_duplicar,
	op_borrar,
	op_borrar_conector,
	op_colocar_pared,
	op_colocar_esquina,
	op_colocar_junto,
	op_colocar_punto,
	op_colocar,
	op_amueblar,
	op_a_mano,
	op_falla_a_medias,
)


# ── Comprobaciones ───────────────────────────────────────────────────────────


def _comprobar_indices(entorno: Entorno, azar: random.Random, muestras: int = 12) -> None:
	"""El índice espacial de cada planta (sin rehacerlo a mano) da lo mismo que mirar todos los espacios."""
	for planta in entorno.plantas:
		utiles = [e for e in planta.espacios if len(e.contorno) >= 3]
		if not utiles:
			continue
		puntos = [azar.choice(utiles).centro() for _vez in range(muestras)]
		x0, y0, x1, y1 = planta.caja()
		puntos.extend((azar.uniform(x0, x1), azar.uniform(y0, y1)) for _vez in range(muestras))
		for x, y in puntos:
			assert [id(e) for e in planta.espacios_en(x, y)] == [id(e) for e in planta.espacios_en_exhaustivo(x, y)], (planta.id, x, y)


def _comprobar_contenido(entorno: Entorno, completo: bool) -> None:
	"""El contenido de cada espacio, que el árbol calcula por partes, es el mismo que calculado desde cero."""
	for planta in entorno.plantas:
		por_partes = operaciones.contenido_de_planta(planta)
		guardado = planta.__dict__.pop("_cache_contenido", None)
		desde_cero = operaciones.contenido_de_planta(planta)
		if guardado is not None:
			planta.__dict__["_cache_contenido"] = guardado
		for espacio in planta.espacios:
			assert [id(e) for e in por_partes[id(espacio)]] == [id(e) for e in desde_cero[id(espacio)]], espacio.id
			if completo:
				assert [id(e) for e in por_partes[id(espacio)]] == [id(e) for e in operaciones.contenido_de_espacio(planta, espacio)], (
					espacio.id
				)


class _Arbol:
	"""El árbol del Estudio puesto al día por partes, como hace la ventana, comparado con el hecho desde cero."""

	def __init__(self, entorno: Entorno, catalogo: Catalogo) -> None:
		self.entorno = entorno
		self.catalogo = catalogo
		self.arbol = operaciones.arbol_de(entorno, catalogo)

	def al_dia(self, historial: Historial) -> None:
		parche = historial.ultimo_parche
		assert parche is not None
		nuevo = operaciones.arbol_de(self.entorno, self.catalogo, anterior=self.arbol, afectados=parche.afectados())
		assert nuevo == operaciones.arbol_de(self.entorno, self.catalogo), "el árbol por partes no es el de desde cero"
		self.arbol = nuevo


def _hacer(
	entorno: Entorno, historial: Historial, catalogo: Catalogo, azar: random.Random, pasos: int, completo: bool, arbol: _Arbol
) -> list[dict]:
	"""Hace ``pasos`` operaciones al azar con el historial y devuelve el a_dict tras cada una (el primero, el inicial)."""
	estados = [entorno.a_dict()]
	for numero in range(pasos):
		operacion = azar.choice(OPERACIONES)
		historial.anotar(entorno, f"{numero} {operacion.__name__}")
		try:
			operacion(entorno, azar, catalogo)
		except ErrorEdicion, ValueError:
			parche = historial.cancelar(entorno)
			assert parche is not None
			assert entorno.a_dict() == estados[-1], f"{operacion.__name__} falló y dejó rastro"
			arbol.al_dia(historial)
			continue
		historial.cerrar(entorno)
		estados.append(entorno.a_dict())
		_comprobar_indices(entorno, azar)
		_comprobar_contenido(entorno, completo)
		arbol.al_dia(historial)
	return estados


def _ida_y_vuelta(entorno: Entorno, catalogo: Catalogo, semilla: int, pasos: int, completo: bool = True) -> None:
	azar = random.Random(semilla)
	historial = Historial(limite=pasos + 1)
	arbol = _Arbol(entorno, catalogo)
	estados = _hacer(entorno, historial, catalogo, azar, pasos, completo, arbol)
	assert len(estados) > pasos // 3, "casi todas las operaciones fallaron: la prueba no prueba nada"
	assert len(historial.operaciones()) == len(estados) - 1
	# Deshacer todo, comprobando cada estado intermedio.
	for esperado in reversed(estados[:-1]):
		assert historial.deshacer(entorno) is entorno
		assert entorno.a_dict() == esperado
		_comprobar_indices(entorno, azar, 4)
		arbol.al_dia(historial)
	assert entorno.a_dict() == estados[0]
	assert not historial.puede_deshacer
	_comprobar_contenido(entorno, completo)
	# Rehacer todo.
	for esperado in estados[1:]:
		assert historial.rehacer(entorno) is entorno
		assert entorno.a_dict() == esperado
		_comprobar_indices(entorno, azar, 4)
		arbol.al_dia(historial)
	assert not historial.puede_rehacer
	_comprobar_contenido(entorno, completo)
	# Alternados al azar.
	posicion = len(estados) - 1
	for _vez in range(3 * pasos):
		if azar.random() < 0.5 and historial.puede_deshacer:
			historial.deshacer(entorno)
			posicion -= 1
		elif historial.puede_rehacer:
			historial.rehacer(entorno)
			posicion += 1
		else:
			continue
		assert entorno.a_dict() == estados[posicion]
		_comprobar_indices(entorno, azar, 3)
		arbol.al_dia(historial)
	_comprobar_contenido(entorno, completo)
	# Operaciones nuevas tras deshacer (otra rama): se pierde lo que se podía rehacer y se deshacen bien.
	rama = _hacer(entorno, historial, catalogo, azar, max(5, pasos // 4), completo, arbol)
	assert rama[0] == estados[posicion]
	assert not historial.puede_rehacer or len(rama) == 1
	for esperado in reversed(rama[:-1]):
		historial.deshacer(entorno)
		assert entorno.a_dict() == esperado
		arbol.al_dia(historial)
	assert entorno.a_dict() == estados[posicion]


@pytest.mark.parametrize("nombre", sorted(ejemplos.todos()))
@pytest.mark.parametrize("semilla", [1, 2, 3])
def test_deshacer_y_rehacer_todo_deja_el_entorno_identico(nombre: str, semilla: int, catalogo: Catalogo) -> None:
	_ida_y_vuelta(ejemplos.todos()[nombre], catalogo, semilla, pasos=70)


def test_deshacer_y_rehacer_en_un_barrio_grande(catalogo: Catalogo) -> None:
	entorno = eg.barrio(1000)
	eg.amueblar(entorno, catalogo, 300)
	_ida_y_vuelta(entorno, catalogo, 11, pasos=40, completo=False)


@pytest.mark.parametrize("semilla", [4, 5])
def test_operar_justo_despues_de_deshacer_no_arrastra_lo_deshecho(semilla: int, catalogo: Catalogo) -> None:
	# Hacer, deshacer y hacer otra cosa: la operación nueva solo puede llevarse lo suyo (la foto de
	# después de la primera ya no vale tras deshacerla).
	entorno = ejemplos.vivienda_ejemplo()
	azar = random.Random(semilla)
	historial = Historial()
	for _vez in range(25):
		antes = entorno.a_dict()
		historial.anotar(entorno, "una")
		op_mover_espacio(entorno, azar, catalogo)
		historial.cerrar(entorno)
		historial.deshacer(entorno)
		assert entorno.a_dict() == antes
		historial.anotar(entorno, "otra")
		op_referencia(entorno, azar, catalogo)
		historial.cerrar(entorno)
		historial.deshacer(entorno)
		assert entorno.a_dict() == antes, "deshacer la segunda operación no puede rehacer ni deshacer la primera"
		historial.rehacer(entorno)


def test_deshacer_conserva_la_identidad_de_lo_que_no_cambia() -> None:
	entorno = ejemplos.vivienda_ejemplo()
	planta = entorno.plantas[0]
	historial = Historial()
	primero, movido = planta.espacios[0], planta.espacios[1]
	historial.anotar(entorno, "mover")
	ed.mover(entorno, movido, 1.0, 0.0)
	parche = historial.cerrar(entorno)
	assert parche is not None and not parche.vacio
	afectados = parche.afectados()
	assert movido.id in afectados.elementos[planta.id] and primero.id not in afectados.elementos[planta.id]
	historial.deshacer(entorno)
	assert planta.espacios[0] is primero and planta.espacios[1] is movido, "deshacer no sustituye los objetos"
	assert historial.ultimo_parche is parche and parche.foco(hacia_atras=True) == movido.id


def test_el_parche_guarda_solo_los_campos_que_cambian() -> None:
	entorno = ejemplos.vivienda_ejemplo()
	espacio = entorno.plantas[0].espacios[0]
	foto = tomar_foto(entorno)
	ed.renombrar(entorno, espacio, "Sala grande")
	parche = comparar(foto, entorno)
	(cambio,) = parche.en_plantas
	(modificacion,) = cambio.listas["espacios"].cambiados
	assert set(modificacion.antes) == {"nombre"} and modificacion.despues == {"nombre": "Sala grande"}
	assert not parche.entorno_antes and not parche.plantas.quitados


def test_una_operacion_que_falla_no_borra_lo_que_se_podia_rehacer() -> None:
	entorno = ejemplos.vivienda_ejemplo()
	planta = entorno.plantas[0]
	historial = Historial()
	historial.anotar(entorno, "renombrar")
	ed.renombrar(entorno, planta.espacios[0], "Uno")
	historial.cerrar(entorno)
	historial.deshacer(entorno)
	assert historial.puede_rehacer
	historial.anotar(entorno, "fallida")
	ed.renombrar(entorno, planta.espacios[0], "A medias")
	historial.cancelar(entorno)
	assert planta.espacios[0].nombre != "A medias"
	assert historial.puede_rehacer and historial.texto_rehacer() == "Rehacer: renombrar"
	assert historial.operaciones() == []


def test_deshacer_sobre_un_entorno_cambiado_por_fuera_no_toca_nada() -> None:
	entorno = ejemplos.vivienda_ejemplo()
	planta = entorno.plantas[0]
	historial = Historial()
	historial.anotar(entorno, "crear")
	ed.crear_habitacion_rectangular(entorno, planta, "Trastero", 100, 100, 2, 2)
	historial.cerrar(entorno)
	# Alguien borra el trastero sin pasar por el historial: el parche ya no encaja.
	del planta.espacios[-1]
	antes = entorno.a_dict()
	with pytest.raises(ErrorParche):
		historial.deshacer(entorno)
	assert entorno.a_dict() == antes
	assert historial.puede_deshacer, "el historial sigue como estaba"


def test_mover_un_espacio_caduca_solo_el_indice_de_su_planta() -> None:
	entorno = ejemplos.centro_dos_plantas()
	baja, alta = entorno.plantas[0], entorno.plantas[1]
	indice_alta = alta.indice_espacios()
	indice_baja = baja.indice_espacios()
	ed.mover(entorno, baja.espacios[0], 1.0, 0.0)
	assert alta.indice_espacios() is indice_alta, "la otra planta no rehace su índice"
	assert baja.indice_espacios() is not indice_baja
	cajas = baja.indice_espacios().cambios_desde(indice_baja)
	assert cajas is not None and len(cajas) == 2
	invalidar_indices()
	assert alta.indice_espacios() is not indice_alta, "invalidar a mano los caduca todos"


@pytest.mark.lento
def test_el_historial_de_un_barrio_grande_no_crece_sin_medida(catalogo: Catalogo) -> None:
	entorno = eg.barrio(3000)
	eg.amueblar(entorno, catalogo, 800)
	planta = entorno.plantas[0]
	historial = Historial(limite=100)
	espacios = [e for e in planta.espacios if len(e.contorno) >= 3]
	for numero in range(100):
		historial.anotar(entorno, f"mover {numero}")
		elemento = espacios[numero * 7 % len(espacios)] if numero % 2 else planta.objetos[numero]
		ed.mover(entorno, elemento, 0.5, 0.0)
		historial.cerrar(entorno)
	ocupado = historial.memoria()
	entero = len(marshal.dumps(entorno.a_dict(), 2))
	# Antes: cien copias enteras (unos 900 MB en memoria). Ahora: lo que cambia en cada movimiento.
	assert ocupado < entero / 2, f"{ocupado} bytes para 100 niveles; una sola copia entera son {entero}"
