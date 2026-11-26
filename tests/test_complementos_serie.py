"""Pruebas de los complementos de objetos de serie (``data/plugins``).

Comprueban lo que se distribuye de verdad: que los veinte complementos (y
``comun``) cargan sin avisos, que todos sus objetos están clasificados con la
taxonomía cerrada, que sus medidas son coherentes y verosímiles para su
función, que no hay casi duplicados, que no falta ni sobra ningún sonido ni
miniatura y que cada sonido está una sola vez en el disco, que la búsqueda,
los filtros, las facetas y el árbol del catálogo dan lo que deben y lo dan al
momento, que el amueblado asistido funciona con ellos sin dejar nunca un
objeto mayor que la habitación, que los entornos de ejemplo se amueblan y
siguen siendo válidos, y que el inglés está completo.

Solo leen ``data/plugins`` y ``data/ejemplos``; lo que escriben va a la
carpeta temporal de cada prueba.
"""

from __future__ import annotations

import hashlib
import importlib
import itertools
import json
import re
import shutil
import struct
import time
from pathlib import Path

import pytest

from app.dominio import colocacion as co
from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio import geometria as geo
from app.dominio.catalogo import (
	ALTURA_VOLADIZO,
	DIMENSIONES,
	DINAMICAS,
	ESTANCIAS,
	FACETAS,
	FRECUENCIAS,
	FUNCIONES,
	LUGARES,
	OBSTACULOS,
	RIESGOS,
	TAXONOMIAS,
	Catalogo,
	DefObjeto,
	empaquetar_complemento,
	es_sonido_de_complemento,
	instalar_complemento,
	partes_de_sonido,
	sin_acentos,
	validar_complemento,
)
from app.dominio.formato import cargar_paquete
from app.dominio.modelo import SUELOS, Entorno, Espacio, Planta
from app.dominio.validacion import validar
from tools import generar_complementos as herramienta

RAIZ = Path(__file__).resolve().parent.parent
PLUGINS = RAIZ / "data" / "plugins"
EJEMPLOS = RAIZ / "data" / "ejemplos"
SERIE = herramienta.COMPLEMENTOS
ORIGINALES = herramienta.ORIGINALES
COMUN = herramienta.ID_COMUN
TODOS = (*SERIE, COMUN)
AUTOR = "Héctor J. Benítez Corredera"

_PATRON_ID = re.compile(r"^[a-z0-9][a-z0-9_-]{0,63}$")
_PATRON_COLOR = re.compile(r"^#[0-9a-fA-F]{6}$")


@pytest.fixture(scope="module")
def catalogo() -> Catalogo:
	"""Los complementos de serie, en español."""
	return Catalogo.cargar(PLUGINS, idioma="es")


@pytest.fixture(scope="module")
def catalogo_ingles() -> Catalogo:
	"""Los complementos de serie, en inglés."""
	return Catalogo.cargar(PLUGINS, idioma="en")


@pytest.fixture(scope="module")
def sonidos_cargados() -> None:
	"""Da de alta los sonidos de todos los ``sonidos_*.py`` (sin esto solo están los de ``sonidos.py``)."""
	herramienta.cargar_sonidos()


def _ficha(id_complemento: str) -> dict:
	return json.loads((PLUGINS / id_complemento / "complemento.json").read_text(encoding="utf-8"))


def _de_serie(catalogo: Catalogo) -> list[DefObjeto]:
	return [d for d in catalogo.objetos() if d.complemento in SERIE]


def _sonidos_de(definicion: DefObjeto) -> list[str]:
	"""Todos los sonidos que cita un objeto: golpe, uso, propio, acciones y dinámica."""
	nombres = []
	for valor in definicion.sonidos.values():
		nombres.append(valor.get("sonido") if isinstance(valor, dict) else valor)
	nombres += [accion.get("sonido") for accion in definicion.acciones]
	nombres += [fase.get("sonido") for fase in definicion.dinamica.get("fases", [])]
	nombres.append(definicion.dinamica.get("sonido_al_terminar"))
	return [nombre for nombre in nombres if nombre]


def _ruta_sonido(id_complemento: str, nombre: str) -> Path:
	"""Fichero de un sonido propio citado por un objeto, en su complemento o en aquel del que depende."""
	dependencia, fichero = partes_de_sonido(nombre)
	return PLUGINS / (dependencia or id_complemento) / "sonidos" / Path(fichero).name


def _copiar_con_dependencias(id_complemento: str, destino: Path) -> None:
	"""Copia a ``destino`` los complementos de los que depende ``id_complemento`` (no el propio)."""
	for dependencia in _ficha(id_complemento).get("depende_de", []):
		shutil.copytree(PLUGINS / dependencia, destino / dependencia)


# ── Carga y ficha ────────────────────────────────────────────────────────────


def test_estan_todos_y_cargan_sin_avisos(catalogo):
	assert catalogo.avisos == []
	assert {c.id for c in catalogo.complementos()} >= set(TODOS)
	for id_complemento in TODOS:
		complemento = catalogo.complemento(id_complemento)
		assert complemento.version == "1.0.0"
		assert complemento.autor == AUTOR
		assert complemento.licencia == "CC BY 4.0"
		assert complemento.descripcion
		leeme = (PLUGINS / id_complemento / "LEEME.md").read_text(encoding="utf-8")
		assert "CC BY 4.0" in leeme and AUTOR in leeme
		if id_complemento == COMUN:
			assert complemento.objetos == []
			continue
		assert 25 <= len(complemento.objetos) <= 200, (id_complemento, len(complemento.objetos))
		for definicion in complemento.objetos:
			assert f"`{definicion.tipo}`" in leeme, definicion.tipo
	# La base de objetos es grande de verdad: más de mil quinientos objetos distintos.
	assert len(_de_serie(catalogo)) >= 1500


@pytest.mark.parametrize("id_complemento", TODOS)
def test_validar_complemento_no_encuentra_nada(id_complemento):
	assert [str(a) for a in validar_complemento(PLUGINS / id_complemento)] == []
	assert herramienta.comprobar(PLUGINS / id_complemento) == []


@pytest.mark.parametrize("id_complemento", TODOS)
def test_la_carpeta_solo_tiene_ficheros_admitidos(id_complemento):
	carpeta = PLUGINS / id_complemento
	for ruta in carpeta.rglob("*"):
		if ruta.is_dir():
			assert ruta.parent == carpeta and ruta.name in ("sonidos", "imagenes", "locales"), ruta
			continue
		relativa = ruta.relative_to(carpeta).as_posix()
		assert relativa in ("complemento.json", "LEEME.md", "locales/en.json") or re.fullmatch(
			r"(sonidos/[a-z0-9_]+\.flac|imagenes/[a-z0-9_]+\.png)", relativa
		), relativa


def test_ids_unicos_y_bien_formados(catalogo):
	for id_complemento in SERIE:
		ids = [objeto["id"] for objeto in _ficha(id_complemento)["objetos"]]
		assert len(ids) == len(set(ids)), [i for i in ids if ids.count(i) > 1]
		assert all(_PATRON_ID.match(i) for i in ids)
		assert len(ids) == len(catalogo.complemento(id_complemento).objetos)
	tipos = [d.tipo for d in _de_serie(catalogo)]
	assert len(tipos) == len(set(tipos))


def test_cada_objeto_rellena_todos_los_campos(catalogo):
	for definicion in _de_serie(catalogo):
		complemento = catalogo.complemento(definicion.complemento)
		tipo = definicion.tipo
		assert definicion.nombre and definicion.nombre != definicion.id, tipo
		assert definicion.categoria in complemento.categorias, tipo
		assert len(definicion.etiquetas) >= 2, tipo
		assert len(definicion.descripcion) >= 25 and definicion.descripcion.endswith("."), tipo
		assert definicion.ambito and definicion.colocacion and definicion.material, tipo
		assert 1 <= len(definicion.simbolo["letra"]) <= 2, tipo
		assert _PATRON_COLOR.match(definicion.simbolo["color"]), tipo
		assert definicion.sonidos.get("golpe"), tipo
		propio = definicion.sonidos.get("propio")
		if propio:
			assert 0 < propio["volumen"] <= 1 and 2 <= propio["radio"] <= 25, tipo
		# Lo que el bastón no detecta es porque empieza en alto (el bastón pasa por debajo);
		# y lo que empieza a medio metro o más no lo detecta nunca.
		if not definicion.detectable_baston:
			assert definicion.altura_base >= ALTURA_VOLADIZO, tipo
		if definicion.altura_base >= 0.5:
			assert not definicion.detectable_baston, tipo
		# Nada pasa de 31 m (la torre de una grúa); nada de interior pasa de 8.
		assert definicion.altura_base + definicion.rango("alto")[1] <= 31.0, tipo
		if definicion.suelo:
			# Lo que se pisa no corta el paso, o lo deja libre en algún estado (una trampilla cerrada, un puente bajado).
			assert definicion.suelo in SUELOS and (not definicion.bloquea or definicion.paso_libre), tipo
		for estado in definicion.estados:
			assert estado in complemento.estados, (tipo, estado)
		for accion in definicion.acciones:
			assert accion["nombre"], tipo
			assert all(
				accion.get(extremo, definicion.estados[0] if definicion.estados else None) in [*definicion.estados, None]
				for extremo in ("de", "a")
			), tipo
		assert set(definicion.paso_libre) <= set(definicion.estados), tipo
		if definicion.paso_libre:
			# Deja pasar solo en algunos estados (un torno abierto, una escalera de buhardilla recogida): en los demás corta el paso.
			assert definicion.bloquea and set(definicion.estados) - set(definicion.paso_libre), tipo
		if definicion.dinamica:
			assert definicion.dinamica["tipo"] in DINAMICAS, tipo


def test_los_semaforos_declaran_su_ciclo(catalogo):
	sonoro = catalogo.objeto("calle/semaforo_peatones")
	assert sonoro.dinamica["tipo"] == "semaforo" and sonoro.dinamica["sonoro"] and sonoro.dinamica["pulsador"]
	assert [fase["estado"] for fase in sonoro.dinamica["fases"]] == ["rojo", "verde", "intermitente"] == sonoro.estados
	assert all(fase["segundos"] > 0 and fase["sonido"].startswith("semaforo/") for fase in sonoro.dinamica["fases"])
	assert sonoro.acciones[0]["id"] == "pulsar"
	mudo = catalogo.objeto("calle/semaforo_peatones_mudo")
	assert not mudo.dinamica["sonoro"] and all("sonido" not in fase for fase in mudo.dinamica["fases"])
	assert [fase["estado"] for fase in catalogo.objeto("calle/semaforo_vehiculos").dinamica["fases"]] == ["verde", "ambar", "rojo"]
	lavadora = catalogo.objeto("hogar/lavadora")
	assert lavadora.dinamica == {"tipo": "temporizador", "estado": "funcionando", "segundos": 90, "al_terminar": "apagado"}
	assert lavadora.sonidos["propio"]["estado"] == "funcionando"


# ── Taxonomía ────────────────────────────────────────────────────────────────


def test_la_taxonomia_cubre_el_cien_por_cien(catalogo):
	"""Cada objeto de serie declara (no deduce) toda su clasificación, y con valores de la taxonomía cerrada."""
	for id_complemento in SERIE:
		subcategorias = _ficha(id_complemento)["subcategorias"]
		for objeto in _ficha(id_complemento)["objetos"]:
			tipo = f"{id_complemento}/{objeto['id']}"
			assert objeto["subcategoria"] in subcategorias, tipo
			assert objeto["funcion"] in FUNCIONES, tipo
			assert objeto["lugares"] and set(objeto["lugares"]) <= set(LUGARES), tipo
			assert objeto["estancias"] and set(objeto["estancias"]) <= set(ESTANCIAS), tipo
			assert objeto["obstaculo"] in OBSTACULOS, tipo
			assert objeto["frecuencia"] in FRECUENCIAS, tipo
			assert set(objeto.get("riesgos", [])) <= set(RIESGOS), tipo
	definiciones = _de_serie(catalogo)
	# Las tablas se usan de verdad: casi todas las funciones y clases de obstáculo tienen objetos.
	assert {d.funcion for d in definiciones} == set(FUNCIONES)
	assert {d.clase_obstaculo for d in definiciones} == set(OBSTACULOS)
	assert {d.frecuencia for d in definiciones} == set(FRECUENCIAS)
	assert len({e for d in definiciones for e in d.estancias}) >= 0.9 * len(ESTANCIAS)
	assert len({lugar for d in definiciones for lugar in d.lugares}) >= 0.9 * len(LUGARES)
	# Y los relacionados que declara cada objeto existen.
	for definicion in definiciones:
		for relacionado in definicion.relacionados:
			referencia = relacionado if "/" in relacionado else f"{definicion.complemento}/{relacionado}"
			assert catalogo.objeto(referencia) is not None, (definicion.tipo, relacionado)


def test_la_clase_de_obstaculo_es_coherente_con_lo_que_encuentra_el_baston(catalogo):
	for definicion in _de_serie(catalogo):
		tipo = definicion.tipo
		if definicion.altura_base >= 0.5:
			# Lo colgado alto nunca se declara como algo que se pisa o que el bastón encuentra en el suelo.
			assert definicion.clase_obstaculo in ("voladizo", "cabeza", "aereo"), tipo
		if definicion.clase_obstaculo == "ras_suelo":
			# Se pisa: es bajo o, si es alto (una escalera, una rampa, un túnel), no corta el paso porque se recorre.
			assert definicion.altura_base == 0 and (definicion.rango("alto")[1] <= 0.25 or not definicion.bloquea), tipo
		if "desnivel" in definicion.riesgos:
			assert definicion.aviso or not definicion.bloquea or definicion.clase_obstaculo != "ras_suelo", tipo


def test_los_nombres_de_la_taxonomia_estan_en_los_dos_idiomas(catalogo, catalogo_ingles):
	comun_es = _ficha(COMUN)["taxonomia"]
	comun_en = json.loads((PLUGINS / COMUN / "locales" / "en.json").read_text(encoding="utf-8"))["taxonomia"]
	distintos = 0
	total = 0
	for faceta, tabla in TAXONOMIAS.items():
		assert set(comun_es[faceta]) == set(tabla) == set(comun_en[faceta]), faceta
		for clave in tabla:
			espanol, ingles = catalogo.nombre_de(faceta, clave), catalogo_ingles.nombre_de(faceta, clave)
			assert espanol and ingles, (faceta, clave)
			total += 1
			distintos += espanol != ingles
	assert distintos >= 0.95 * total
	assert catalogo_ingles.nombre_de("funcion", "asiento") == "Seat"
	assert catalogo.nombre_de("estancia", "sala_espera") == "Sala de espera"


# ── Medidas y formas ─────────────────────────────────────────────────────────


def test_medidas_coherentes_y_verosimiles(catalogo):
	for id_complemento in SERIE:
		for objeto in _ficha(id_complemento)["objetos"]:
			assert set(objeto["medidas"]) == set(DIMENSIONES), objeto["id"]
	for definicion in _de_serie(catalogo):
		tipo = definicion.tipo
		for dimension in DIMENSIONES:
			minimo, defecto, maximo = definicion.rango(dimension)
			assert 0 < minimo <= defecto <= maximo, (tipo, dimension)
			# Un rango desmesurado no protege de nada: el máximo no pasa de diez veces el mínimo (salvo la altura).
			if definicion.bloquea and dimension != "alto":
				assert maximo <= 10 * minimo, (tipo, dimension)
			for variante in definicion.variantes:
				assert minimo - 1e-9 <= getattr(variante, dimension) <= maximo + 1e-9, (tipo, variante.id, dimension)
		ancho, fondo, alto = (definicion.rango(d) for d in DIMENSIONES)
		# Lo más fino (una placa, un pulsador) tiene al menos un centímetro de grueso.
		assert ancho[0] >= 0.01 and fondo[0] >= 0.01, tipo
		if definicion.bloquea:
			assert alto[0] >= 0.05 or definicion.altura_base > 0 or definicion.paso_libre, tipo
			# Nada que corte el paso mide más de treinta metros (un vaso de piscina, una escollera).
			assert max(ancho[2], fondo[2]) <= 30.0, tipo
			if definicion.ambito == ["interior"]:
				# Lo más grande de interior es de una nave (una línea de montaje, una estantería de palés): veinte metros y trece de alto.
				assert max(ancho[2], fondo[2]) <= 20.0, tipo
				assert alto[2] + definicion.altura_base <= 13.0, tipo
		assert len({v.id for v in definicion.variantes}) == len(definicion.variantes), tipo
		assert all(v.nombre for v in definicion.variantes), tipo


# función → (techo mínimo, techo máximo, lado mayor máximo), en metros, con las medidas por defecto.
# El techo es la altura a la que llega el objeto (altura_base + alto).
MEDIDAS_POR_FUNCION: dict[str, tuple[float, float, float]] = {
	"asiento": (0.1, 2.6, 6.5),
	"mesa": (0.3, 2.1, 5.5),
	"mostrador": (0.5, 3.0, 5.0),
	"descanso": (0.05, 2.2, 4.0),
	"electrodomestico": (0.05, 2.3, 5.5),
	"equipo_medico": (0.2, 2.6, 4.0),
	"sanitario": (0.01, 2.7, 4.0),
	"pago": (0.3, 2.6, 3.5),
	"iluminacion": (0.08, 9.5, 2.0),
	"vehiculo": (0.1, 7.0, 15.0),
	"instrumento": (0.2, 5.0, 5.0),
	"juego": (0.003, 5.0, 15.0),
	"vegetacion": (0.03, 20.0, 10.0),
	"senalizacion": (0.1, 7.0, 5.5),
}


def test_medidas_verosimiles_por_funcion(catalogo):
	fuera = []
	for definicion in _de_serie(catalogo):
		if definicion.funcion not in MEDIDAS_POR_FUNCION:
			continue
		techo_minimo, techo_maximo, lado_maximo = MEDIDAS_POR_FUNCION[definicion.funcion]
		techo = definicion.altura_base + definicion.rango("alto")[1]
		lado = max(definicion.rango("ancho")[1], definicion.rango("fondo")[1])
		if not (techo_minimo <= techo <= techo_maximo and lado <= lado_maximo):
			fuera.append((definicion.tipo, round(techo, 2), lado))
	assert fuera == []


@pytest.mark.parametrize(
	("tipo", "dimension", "minimo", "maximo"),
	[
		("hogar/mesa_cocina", "alto", 0.70, 0.80),
		("hogar/encimera", "alto", 0.85, 0.95),
		("hogar/encimera", "fondo", 0.58, 0.65),
		("hogar/inodoro", "ancho", 0.35, 0.42),
		("hogar/frigorifico", "ancho", 0.55, 0.65),
		("hogar/lavadora", "ancho", 0.59, 0.61),
		("hogar/armario", "fondo", 0.55, 0.65),
		("hogar/sofa", "fondo", 0.80, 1.00),
		("hogar/banera", "ancho", 1.50, 1.80),
		("hogar/microondas", "alto", 0.25, 0.35),
		("colegio/pupitre", "ancho", 0.60, 0.70),
		("colegio/mesa_pimpon", "fondo", 2.74, 2.74),
		("colegio/mesa_pimpon", "ancho", 1.525, 1.525),
		("colegio/canasta", "alto", 3.05, 3.05),
		("oficina_y_comercio/mesa_despacho", "alto", 0.72, 0.76),
		("oficina_y_comercio/maquina_expendedora", "alto", 1.70, 1.90),
		("oficina_y_comercio/mostrador_recepcion", "alto", 1.00, 1.15),
		("calle/bolardo", "alto", 0.50, 1.10),
		("calle/contenedor_resto", "ancho", 1.20, 1.40),
		("calle/coche", "fondo", 3.50, 5.00),
		("calle/coche", "ancho", 1.60, 1.95),
		("calle/banco", "alto", 0.75, 0.95),
		("transporte/marquesina", "alto", 2.20, 3.00),
		("transporte/torno", "alto", 0.90, 1.10),
		("juego/cofre", "ancho", 0.50, 1.20),
		("sanidad/cama_hospital", "fondo", 2.00, 2.30),
		("sanidad/cama_hospital", "ancho", 0.90, 1.05),
		("residencia_y_ayudas_tecnicas/inodoro_adaptado_barras", "ancho", 0.70, 0.90),
		("hosteleria/barra_recta", "alto", 1.00, 1.15),
		("deporte/cinta_correr", "fondo", 1.70, 2.20),
		("vehiculos_y_aparcamiento/autocar", "fondo", 10.0, 15.0),
		("estaciones_y_aeropuerto/coche_tren_tramo", "fondo", 2.80, 3.10),
	],
)
def test_medidas_de_referencia(catalogo, tipo, dimension, minimo, maximo):
	"""Medidas por defecto de objetos conocidos, contra las habituales en España."""
	assert minimo - 1e-9 <= catalogo.objeto(tipo).rango(dimension)[1] <= maximo + 1e-9


def test_variantes_con_nombre_de_los_tamanos_habituales(catalogo):
	cama = catalogo.objeto("hogar/cama")
	assert {round(v.ancho, 2) for v in cama.variantes} >= {0.9, 1.35, 1.5}
	assert {v.id for v in catalogo.objeto("hogar/mesa_cocina").variantes} == {"dos_plazas", "cuatro_plazas", "seis_plazas"}
	assert {v.id for v in catalogo.objeto("calle/contenedor_240").variantes} == {"litros_120", "litros_240"}
	assert catalogo.objeto("calle/contenedor_resto").variante("litros_1100").ancho == pytest.approx(1.37)
	assert sum(1 for d in _de_serie(catalogo) if d.variantes) >= 400


def test_las_formas_llenan_su_caja_y_son_variadas(catalogo):
	tipos_de_forma = {"rectangulo": 0, "circulo": 0, "ele": 0, "poligono": 0}
	for definicion in _de_serie(catalogo):
		tipos_de_forma[definicion.forma["tipo"]] += 1
		puntos = definicion.puntos_forma()
		assert len(puntos) >= 3 and geo.es_simple(puntos) and geo.area(puntos) > 0.02, definicion.tipo
		# La huella toca los cuatro lados del cuadrado: el ancho y el fondo declarados son los reales.
		assert geo.caja(puntos) == pytest.approx((0.0, 0.0, 1.0, 1.0), abs=1e-6), definicion.tipo
	assert tipos_de_forma["ele"] >= 15
	assert tipos_de_forma["circulo"] >= 150
	assert tipos_de_forma["poligono"] >= 500
	for tipo in (
		"hogar/sofa_ele",
		"hogar/piano_cola",
		"hogar/banera",
		"hogar/isla",
		"hogar/cama_cabecero",
		"oficina_y_comercio/mostrador_curvo",
		"oficina_y_comercio/mesa_reuniones",
		"oficina_y_comercio/mesa_ele",
		"calle/coche",
		"calle/bancos_rotonda",
		"calle/contenedor_resto",
		"transporte/marquesina",
		"deporte/bici_estatica",
		"trabajo_y_taller/carretilla_elevadora",
	):
		assert catalogo.objeto(tipo).forma["tipo"] in ("ele", "poligono"), tipo
	assert catalogo.objeto("hogar/mesa_redonda").forma["tipo"] == "circulo"
	assert catalogo.objeto("colegio/columna").forma["tipo"] == "circulo"


def test_obstaculos_colgantes_suelo_y_paso_libre(catalogo):
	for tipo in ("hogar/espejo", "hogar/extintor", "calle/toldo_bajo", "calle/buzon_pared", "colegio/pizarra", "calle/andamio_travesano"):
		definicion = catalogo.objeto(tipo)
		assert definicion.altura_base > 0.5 and not definicion.detectable_baston, tipo
	colgados = [d for d in _de_serie(catalogo) if d.altura_base >= 0.5]
	assert len(colgados) >= 150
	assert all(d.clase_obstaculo in ("voladizo", "cabeza", "aereo") for d in colgados)
	alfombra = catalogo.objeto("hogar/alfombra")
	assert not alfombra.bloquea and alfombra.suelo == "alfombra"
	assert catalogo.objeto("calle/tapa_alcantarilla").suelo == "metal"
	assert catalogo.objeto("calle/pavimento_botones").suelo == "tactil_botones"
	borde = catalogo.objeto("transporte/borde_anden")
	assert not borde.bloquea and borde.suelo == "tactil_botones" and "vías" in borde.aviso
	torno = catalogo.crear_objeto("transporte/torno", 0, 0)
	assert torno.estado == "cerrado" and catalogo.bloquea(torno)
	torno.estado = "abierto"
	assert not catalogo.bloquea(torno)
	assert sum(1 for d in _de_serie(catalogo) if d.contenedor) >= 300
	assert catalogo.objeto("juego/cofre").contenedor and catalogo.objeto("juego/cofre").acciones[0]["id"] == "abrir"


# ── Casi duplicados ──────────────────────────────────────────────────────────

# Los objetos que ya tenían los seis complementos originales antes de ampliarlos (sus módulos no se tocan).
LEGADO = frozenset(
	f"{id_complemento}/{definido.ficha['id']}"
	for id_complemento in ORIGINALES
	for definido in importlib.import_module(f"tools.complementos_serie.{id_complemento}").COMPLEMENTO.objetos
)
_PALABRAS_VACIAS = frozenset(("de", "del", "la", "el", "los", "las", "y", "con", "en", "para", "a", "un", "una", "al"))


def _palabras(nombre: str) -> frozenset[str]:
	return frozenset(p for p in re.findall(r"[a-z0-9]+", sin_acentos(nombre)) if p not in _PALABRAS_VACIAS)


def casi_duplicados(definiciones: list[DefObjeto]) -> list[tuple[str, str]]:
	"""Parejas de objetos que son el mismo con otro nombre o solo otro tamaño (eso tiene que ser una variante).

	Lo son si se llaman igual (sin tildes ni mayúsculas) o si tienen la misma
	función, comparten al menos tres cuartas partes de las palabras del nombre
	y sus medidas por defecto no se separan más de un 25 %. No cuentan las
	parejas entre dos objetos que ya existían en los seis complementos
	originales (``LEGADO``): sus ids no se pueden quitar porque hay entornos
	que los usan (cada uno es el mueble propio de su complemento: el extintor
	de casa y el del colegio).
	"""
	# Se compara solo dentro de cada función (y los nombres, por diccionario): con dos mil objetos, todos contra todos tardaría medio minuto.
	puesto = {d.tipo: n for n, d in enumerate(definiciones)}
	parejas: set[tuple[str, str]] = set()
	por_nombre: dict[str, list[DefObjeto]] = {}
	por_funcion: dict[str, list[tuple[DefObjeto, frozenset[str], tuple[float, ...]]]] = {}
	for definicion in definiciones:
		por_nombre.setdefault(sin_acentos(definicion.nombre), []).append(definicion)
		por_funcion.setdefault(definicion.funcion, []).append(
			(definicion, _palabras(definicion.nombre), tuple(definicion.rango(d)[1] for d in DIMENSIONES))
		)
	for iguales in por_nombre.values():
		parejas.update((a.tipo, b.tipo) for a, b in itertools.combinations(iguales, 2))
	for grupo in por_funcion.values():
		for (a, pa, ma), (b, pb, mb) in itertools.combinations(grupo, 2):
			if not pa or not pb or len(pa & pb) / len(pa | pb) < 0.75:
				continue
			if all(abs(x - y) <= 0.25 * max(x, y) for x, y in zip(ma, mb, strict=True)):
				parejas.add((a.tipo, b.tipo))
	return sorted(((a, b) for a, b in parejas if not (a in LEGADO and b in LEGADO)), key=lambda par: (puesto[par[0]], puesto[par[1]]))


def test_no_hay_casi_duplicados(catalogo):
	assert casi_duplicados(_de_serie(catalogo)) == []


def test_el_detector_de_casi_duplicados_los_encuentra(catalogo):
	"""El detector no es un adorno: encuentra el mismo objeto con otro nombre o solo otro tamaño."""
	original = catalogo.objeto("sanidad/cama_hospital")
	copia = DefObjeto.de_dict(
		{
			"id": "cama_hospital_2",
			"nombre": " ".join(reversed(original.nombre.split())),
			"funcion": "descanso",
			"medidas": {d: list(original.rango(d)) for d in DIMENSIONES},
		},
		"otro",
	)
	renombrada = DefObjeto.de_dict({"id": "cama_clinica", "nombre": original.nombre.upper(), "funcion": "asiento"}, "otro")
	assert casi_duplicados([original, copia, renombrada]) == [(original.tipo, copia.tipo), (original.tipo, renombrada.tipo)]


# ── Sonidos y miniaturas ─────────────────────────────────────────────────────


def test_todos_los_sonidos_existen_y_estan_una_sola_vez(catalogo, sonidos_cargados):
	import soundfile as sf

	de_serie = set(json.loads((RAIZ / "data" / "sounds" / "catalogo.json").read_text(encoding="utf-8"))["sonidos"])
	usados: set[Path] = set()
	for id_complemento in SERIE:
		complemento = catalogo.complemento(id_complemento)
		for definicion in complemento.objetos:
			for nombre in _sonidos_de(definicion):
				if es_sonido_de_complemento(nombre):
					dependencia = partes_de_sonido(nombre)[0]
					assert not dependencia or dependencia in complemento.depende_de, (definicion.tipo, nombre)
					ruta = _ruta_sonido(id_complemento, nombre)
					assert ruta.is_file(), (definicion.tipo, nombre)
					usados.add(ruta)
				else:
					assert nombre in de_serie, (definicion.tipo, nombre)
	en_disco = {ruta for id_complemento in TODOS for ruta in (PLUGINS / id_complemento).glob("sonidos/*.flac")}
	# Ni falta ni sobra ninguno.
	assert en_disco == usados, sorted(str(r.relative_to(PLUGINS)) for r in en_disco ^ usados)
	# Y cada sonido está una sola vez en el disco: los compartidos van en «comun» o en su complemento original.
	huellas: dict[str, list[str]] = {}
	for ruta in en_disco:
		huellas.setdefault(hashlib.sha256(ruta.read_bytes()).hexdigest(), []).append(ruta.relative_to(PLUGINS).as_posix())
	assert [rutas for rutas in huellas.values() if len(rutas) > 1] == []
	assert len({ruta.name for ruta in en_disco}) == len(en_disco)
	for ruta in sorted(en_disco):
		info = sf.info(str(ruta))
		assert (info.samplerate, info.channels, info.format) == (44100, 1, "FLAC"), ruta.name
		assert 0.05 <= info.duration <= 8.0, ruta.name
	# Lo que suena solo, en bucle, es un sonido de serie o uno propio declarado como bucle.
	for definicion in _de_serie(catalogo):
		propio = definicion.sonidos.get("propio")
		if propio and es_sonido_de_complemento(propio["sonido"]):
			assert herramienta.sonidos.SONIDOS[Path(partes_de_sonido(propio["sonido"])[1]).stem].bucle, definicion.tipo


def test_los_sonidos_compartidos_no_cambian_de_nombre_en_los_originales(catalogo):
	"""Los sonidos que los seis originales ya llevaban siguen en su sitio: hay entornos y pruebas que los piden así."""
	for clave in ("hogar/puerta_mueble.flac", "transporte/torno.flac", "hogar/lavadora.flac", "hogar/microondas_fin.flac"):
		assert (PLUGINS / clave.split("/")[0] / "sonidos" / clave.split("/")[1]).is_file(), clave
	assert catalogo.objeto("hogar/lavadora").sonidos["propio"]["sonido"] == "sonidos/lavadora.flac"
	# «comun» no tiene objetos y todos los demás dependen de él o de algún original.
	for id_complemento in SERIE:
		assert set(catalogo.complemento(id_complemento).depende_de) <= set(TODOS), id_complemento


def test_tamano_en_disco_razonable():
	total = sum(ruta.stat().st_size for ruta in PLUGINS.rglob("*") if ruta.is_file())
	assert total < 60 * 1024 * 1024


@pytest.mark.lento
def test_los_sonidos_propios_son_prudentes_y_localizables(sonidos_cargados):
	from app.audio import sintesis

	for nombre, definicion in herramienta.sonidos.SONIDOS.items():
		datos = herramienta.sonidos.generar(nombre)
		assert datos.ndim == 1 and datos.dtype.name == "float32", nombre
		assert float(abs(datos).max()) == pytest.approx(definicion.pico, abs=1e-3) and definicion.pico <= 0.6, nombre
		# Sin agudos, el sonido binaural no distingue delante de detrás.
		assert sintesis.fraccion_agudos(datos) > 0.012, nombre
	# Es reproducible: el mismo nombre da siempre las mismas muestras.
	for nombre in ("lavadora", "torno", "semaforo_peatones" if "semaforo_peatones" in herramienta.sonidos.SONIDOS else "cajon"):
		assert (herramienta.sonidos.generar(nombre) == herramienta.sonidos.generar(nombre)).all(), nombre


def test_todas_las_miniaturas_existen(catalogo):
	for definicion in _de_serie(catalogo):
		complemento = catalogo.complemento(definicion.complemento)
		assert definicion.imagen["fichero"] == f"imagenes/{definicion.id}.png", definicion.tipo
		assert len(definicion.imagen["descripcion"]) > 30 and definicion.nombre in definicion.imagen["descripcion"], definicion.tipo
		ruta = complemento.ruta_recurso(definicion.imagen["fichero"])
		assert ruta is not None, definicion.tipo
		cabecera = ruta.read_bytes()[:24]
		assert cabecera[:8] == b"\x89PNG\r\n\x1a\n", definicion.tipo
		assert struct.unpack(">II", cabecera[16:24]) == (128, 128), definicion.tipo
	for id_complemento in SERIE:
		en_disco = {ruta.stem for ruta in (PLUGINS / id_complemento / "imagenes").iterdir()}
		assert en_disco == {d.id for d in catalogo.complemento(id_complemento).objetos}


# ── Búsqueda, filtros, facetas, árbol y relacionados ─────────────────────────


def test_buscar_sin_tildes_en_nombre_etiquetas_y_sinonimos(catalogo):
	assert catalogo.buscar_avanzado("sillon")[0].tipo == "hogar/sillon"
	assert [d.tipo for d in catalogo.buscar_avanzado("SILLÓN")] == [d.tipo for d in catalogo.buscar_avanzado("sillon")]
	# «nevera» es un sinónimo (etiqueta) del frigorífico de casa.
	assert "hogar/frigorifico" in [d.tipo for d in catalogo.buscar_avanzado("nevera", limite=3)]
	# Con varias palabras tienen que estar todas.
	assert catalogo.buscar_avanzado("cama hospital")[0].tipo == "sanidad/cama_hospital"
	assert catalogo.buscar_avanzado("zzzz no existe") == []
	# La firma de siempre sigue igual: ordenado por nombre y con sus tres filtros.
	assert {d.tipo for d in catalogo.buscar("ropero")} >= {"hogar/armario"}
	nombres = [sin_acentos(d.nombre) for d in catalogo.buscar("mesa")]
	assert nombres == sorted(nombres) and len(nombres) >= 50
	assert all(d.categoria == "dormitorio" for d in catalogo.buscar(categoria="dormitorio"))
	assert all("exterior" in d.ambito and "acera" in d.colocacion for d in catalogo.buscar("", ambito="exterior", colocacion="acera"))
	assert "calle/farola" in {d.tipo for d in catalogo.buscar("farola", colocacion="acera")}
	assert len(catalogo.categorias()) >= 100 and len(catalogo.complementos()) == len(TODOS)


def test_filtros_combinables(catalogo):
	espera = catalogo.buscar_avanzado(funcion="asiento", estancia="sala_espera")
	assert "sanidad/bancada_espera" in {d.tipo for d in espera}
	assert all(d.funcion == "asiento" and "sala_espera" in d.estancias for d in espera)
	camas = catalogo.buscar_avanzado(funcion="descanso", lugar=("hospital", "centro_salud"))
	assert "sanidad/cama_hospital" in {d.tipo for d in camas} and "hogar/cama" not in {d.tipo for d in camas}
	cabeza = catalogo.buscar_avanzado(obstaculo="cabeza")
	assert len(cabeza) >= 30 and all(d.clase_obstaculo == "cabeza" for d in cabeza)
	assert all(d.contenedor for d in catalogo.buscar_avanzado(contenedor=True))
	assert all(d.tiene_sonido_propio for d in catalogo.buscar_avanzado(con_sonido=True))
	assert all(not d.acciones for d in catalogo.buscar_avanzado(usable=False))
	juego = catalogo.buscar_avanzado(complemento="juego", categoria="tesoros")
	assert juego and all(d.complemento == "juego" and d.categoria == "tesoros" for d in juego)
	assert all("movil" in d.riesgos for d in catalogo.buscar_avanzado(riesgo="movil"))
	assert all(d.subcategoria == "asientos" for d in catalogo.buscar_avanzado(complemento="hogar", subcategoria="asientos"))
	exteriores = catalogo.buscar_avanzado("banco", ambito="exterior", colocacion="acera")
	assert exteriores and all("exterior" in d.ambito and "acera" in d.colocacion for d in exteriores)
	# Sin texto, lo más común primero.
	puestos = [FRECUENCIAS_ORDEN[d.frecuencia] for d in catalogo.buscar_avanzado(complemento="sanidad")]
	assert puestos == sorted(puestos)
	assert [d.tipo for d in catalogo.buscar_avanzado(complemento="sanidad", orden="nombre")] == [
		d.tipo for d in sorted(catalogo.buscar_avanzado(complemento="sanidad"), key=lambda d: sin_acentos(d.nombre))
	]
	with pytest.raises(ValueError):
		catalogo.buscar_avanzado(orden="al_azar")


FRECUENCIAS_ORDEN = {clave: puesto for puesto, clave in enumerate(FRECUENCIAS)}


def test_facetas_con_recuentos(catalogo):
	facetas = catalogo.facetas()
	assert set(facetas) == set(FACETAS)
	total = len(_de_serie(catalogo))
	assert sum(v.total for v in facetas["complemento"]) == total
	assert sum(v.total for v in facetas["funcion"]) == total
	assert sum(v.total for v in facetas["obstaculo"]) == total
	assert {v.clave: v.total for v in facetas["usable"]}["si"] + {v.clave: v.total for v in facetas["usable"]}["no"] == total
	asientos = next(v for v in facetas["funcion"] if v.clave == "asiento")
	assert asientos.nombre == "Asiento" and asientos.total == len(catalogo.buscar_avanzado(funcion="asiento"))
	# Con un filtro puesto, su propia faceta sigue contando las demás opciones; las otras se acotan.
	con_filtro = catalogo.facetas(funcion="asiento")
	mesas = next(v for v in con_filtro["funcion"] if v.clave == "mesa")
	assert mesas.total == len(catalogo.buscar_avanzado(funcion="mesa"))
	assert sum(v.total for v in con_filtro["complemento"]) == len(catalogo.buscar_avanzado(funcion="asiento"))
	# Y con texto.
	assert sum(v.total for v in catalogo.facetas("banco")["complemento"]) == len(catalogo.buscar_avanzado("banco"))


def test_arbol_complemento_categoria_subcategoria(catalogo):
	arbol = catalogo.arbol()
	assert [nodo.clave for nodo in arbol] == [c.id for c in catalogo.complementos() if c.objetos]
	for nodo in arbol:
		assert nodo.nivel == "complemento" and nodo.total == len(catalogo.complemento(nodo.clave).objetos)
		assert nodo.total == sum(rama.total for rama in nodo.hijos)
		for rama in nodo.hijos:
			assert rama.nivel == "categoria" and rama.nombre and rama.total == sum(hoja.total for hoja in rama.hijos)
			assert all(hoja.nivel == "subcategoria" and hoja.clave and hoja.nombre for hoja in rama.hijos), (nodo.clave, rama.clave)
	hogar = next(nodo for nodo in arbol if nodo.clave == "hogar")
	salon = next(rama for rama in hogar.hijos if rama.clave == "salon")
	assert salon.nombre == "Salón"
	con_objetos = catalogo.arbol(con_objetos=True)
	hojas = [hoja for nodo in con_objetos for rama in nodo.hijos for hoja in rama.hijos]
	assert sum(len(hoja.tipos) for hoja in hojas) == len(_de_serie(catalogo))
	filtrado = catalogo.arbol(funcion="vehiculo")
	assert sum(nodo.total for nodo in filtrado) == len(catalogo.buscar_avanzado(funcion="vehiculo"))


def test_el_arbol_y_las_facetas_tienen_la_forma_que_espera_el_estudio(catalogo):
	"""``app/ui/dialogo_catalogo.py`` lee los nodos por ``clave``, ``nombre``, ``total`` e ``hijos``, y las facetas como ``ValorFaceta``."""
	nodo = catalogo.arbol()[0]
	assert all(hasattr(nodo, atributo) for atributo in ("clave", "nombre", "total", "hijos"))
	for faceta in ("lugar", "estancia", "funcion", "obstaculo"):
		assert all(hasattr(valor, "clave") and hasattr(valor, "total") and hasattr(valor, "nombre") for valor in catalogo.facetas()[faceta])


def test_relacionados(catalogo):
	sofa = catalogo.objeto("hogar/sofa")
	declarados = [r if "/" in r else f"hogar/{r}" for r in sofa.relacionados]
	relacionados = [d.tipo for d in catalogo.relacionados("hogar/sofa")]
	assert declarados and relacionados[: len(declarados)] == declarados
	cama = [d.tipo for d in catalogo.relacionados("sanidad/cama_hospital")]
	assert "sanidad/mesilla_hospitalaria" in cama and "sanidad/cama_hospital" not in cama
	assert len(catalogo.relacionados("hogar/mesa_comedor", limite=5)) == 5
	assert catalogo.relacionados("hogar/no_existe") == []


def test_buscar_es_instantaneo_con_miles_de_objetos():
	"""Cargar, indizar y buscar entre más de dos mil objetos cabe de sobra en lo que tarda una pulsación."""
	inicio = time.perf_counter()
	catalogo = Catalogo.cargar(PLUGINS, idioma="es")
	catalogo.buscar_avanzado("silla")
	assert time.perf_counter() - inicio < 5.0
	consultas = ["silla", "mesa redonda", "cama", "banco de madera", "semaforo", "a", ""]
	inicio = time.perf_counter()
	for texto in consultas * 5:
		catalogo.buscar_avanzado(texto)
		catalogo.buscar(texto)
	assert (time.perf_counter() - inicio) / (len(consultas) * 5) < 0.05
	inicio = time.perf_counter()
	for _vez in range(5):
		catalogo.facetas("silla", funcion="asiento")
		catalogo.arbol()
		catalogo.relacionados("hogar/mesa_comedor")
	assert (time.perf_counter() - inicio) / 5 < 0.15


# ── Amueblado asistido ───────────────────────────────────────────────────────

# uso → (ancho, fondo, objetos mínimos, tipos que tienen que estar, complementos preferidos)
HABITACIONES: dict[str, tuple[float, float, int, tuple[str, ...], tuple[str, ...]]] = {
	"dormitorio": (3.5, 3.2, 4, ("hogar/cama", "hogar/armario", "hogar/mesilla"), ("hogar",)),
	"salon": (4.5, 4.0, 4, ("hogar/sofa", "hogar/mueble_tv", "hogar/mesa_centro"), ("hogar",)),
	"cocina": (3.2, 3.6, 5, ("hogar/frigorifico", "hogar/encimera", "hogar/fregadero"), ("hogar",)),
	"bano": (2.4, 2.2, 3, ("hogar/inodoro", "hogar/lavabo"), ("hogar",)),
	"aula": (7.0, 6.0, 8, ("colegio/pizarra", "colegio/mesa_del_profesor", "colegio/pupitre", "colegio/papelera"), ("colegio",)),
	"oficina": (
		4.0,
		3.5,
		4,
		("oficina_y_comercio/mesa_despacho", "oficina_y_comercio/silla_giratoria", "oficina_y_comercio/archivador"),
		("oficina_y_comercio",),
	),
}

# Usos que se apoyan en la clasificación: uso → (ancho, fondo, objetos mínimos, tipos que tienen que estar).
USOS_NUEVOS: dict[str, tuple[float, float, int, tuple[str, ...]]] = {
	"sala_espera": (6.0, 5.0, 5, ("sanidad/pantalla_turnos",)),
	"consulta": (4.0, 3.5, 5, ("sanidad/mesa_consulta", "sanidad/camilla_exploracion")),
	"habitacion_hospital": (4.5, 4.0, 5, ("sanidad/cama_hospital", "sanidad/mesilla_hospitalaria")),
	"aseo_adaptado": (
		2.4,
		2.4,
		4,
		("residencia_y_ayudas_tecnicas/inodoro_adaptado_barras", "residencia_y_ayudas_tecnicas/lavabo_suspendido_regulable"),
	),
	"bar": (7.0, 6.0, 5, ("hosteleria/barra_recta", "hosteleria/tragaperras")),
	"restaurante": (8.0, 6.0, 5, ("hosteleria/mesa_restaurante_vestida", "hosteleria/aparador_camareros")),
	"habitacion_hotel": (4.5, 4.0, 5, ("hosteleria/cama_hotel_cabecero_corrido", "hosteleria/minibar")),
	"recepcion": (6.0, 5.0, 5, ("oficina_y_comercio/mostrador_recepcion",)),
	"biblioteca": (8.0, 6.0, 5, ("cultura_y_ocio/mostrador_prestamo", "colegio/estanteria_biblioteca")),
	"gimnasio": (8.0, 7.0, 5, ("deporte/cinta_correr", "deporte/bici_estatica")),
	"vestuario": (5.0, 4.0, 4, ("deporte/duchas_colectivas",)),
	"garaje": (6.0, 6.0, 4, ("calle/coche",)),
	"portal": (4.0, 6.0, 4, ("comunidad_y_edificio/casillero_buzones",)),
	"anden": (12.0, 5.0, 5, ("transporte/banco_anden", "transporte/maquina_billetes")),
	"parque_infantil": (14.0, 12.0, 5, ("parque_y_naturaleza/columpio_doble", "parque_y_naturaleza/tobogan_parque")),
}


def _habitacion(uso: str, ancho: float, fondo: float) -> tuple[Entorno, Planta, Espacio]:
	entorno = ed.crear_entorno(f"Prueba de {uso}")
	planta = ed.crear_planta(entorno, "Planta")
	espacio = ed.crear_habitacion_rectangular(entorno, planta, uso.capitalize(), 0.0, 0.0, ancho, fondo)
	ed.anadir_puerta(entorno, planta, espacio, "sur", desplazamiento=0.2, ancho=0.8, es_salida=True)
	# El alumno empieza nada más cruzar la puerta, en la zona que el amueblado deja siempre libre.
	ed.fijar_inicio(entorno, planta, 0.6, 0.35, 0.0)
	return entorno, planta, espacio


def _comprobar_colocados(entorno: Entorno, planta: Planta, espacio: Espacio, catalogo: Catalogo) -> None:
	for objeto in planta.objetos:
		definicion = catalogo.definicion_de(objeto)
		assert definicion is not None and definicion.complemento in SERIE, objeto.tipo
		assert geo.poligono_contiene(espacio.contorno, catalogo.huella(objeto)), (objeto.nombre, objeto.ancho, objeto.fondo)
		for dimension in ("ancho", "fondo"):
			minimo, _defecto, maximo = definicion.rango(dimension)
			assert minimo - 1e-6 <= getattr(objeto, dimension) <= maximo + 1e-6, (objeto.nombre, dimension)
		avisos = co.comprobar(entorno, planta, objeto, catalogo)
		assert not any(a.es_error for a in avisos), (objeto.nombre, [str(a) for a in avisos])
		assert not any(a.codigo == "tapa_abertura" for a in avisos), objeto.nombre


@pytest.mark.parametrize("uso", list(HABITACIONES))
def test_amueblar_una_habitacion_normal(catalogo, uso):
	ancho, fondo, minimo, esperados, preferidos = HABITACIONES[uso]
	entorno, planta, espacio = _habitacion(uso, ancho, fondo)
	colocados = co.amueblar_espacio(entorno, planta, espacio, uso, catalogo, preferidos=preferidos)
	tipos = {objeto.tipo for objeto in colocados}
	assert len(colocados) >= minimo, sorted(tipos)
	assert tipos >= set(esperados), sorted(tipos)
	assert planta.objetos == colocados
	_comprobar_colocados(entorno, planta, espacio, catalogo)
	assert not any(a.es_error for a in validar(entorno, catalogo))


@pytest.mark.parametrize("uso", list(HABITACIONES))
def test_amueblar_sin_preferencias_tambien_coloca_objetos_reales(catalogo, uso):
	ancho, fondo, minimo, _esperados, _preferidos = HABITACIONES[uso]
	entorno, planta, espacio = _habitacion(uso, ancho, fondo)
	colocados = co.amueblar_espacio(entorno, planta, espacio, uso, catalogo)
	assert len(colocados) >= minimo
	_comprobar_colocados(entorno, planta, espacio, catalogo)


@pytest.mark.parametrize("uso", list(USOS_NUEVOS))
def test_amueblar_los_usos_nuevos(catalogo, uso):
	ancho, fondo, minimo, esperados = USOS_NUEVOS[uso]
	assert uso in co.USOS and uso in co.CONTEXTOS and uso in co.NOMBRES_USOS
	entorno, planta, espacio = _habitacion(uso, ancho, fondo)
	colocados = co.amueblar_espacio(entorno, planta, espacio, uso, catalogo)
	tipos = {objeto.tipo for objeto in colocados}
	assert len(colocados) >= minimo, sorted(tipos)
	assert tipos >= set(esperados), sorted(tipos)
	_comprobar_colocados(entorno, planta, espacio, catalogo)
	assert not any(a.es_error for a in validar(entorno, catalogo))
	# Lo que se busca con la clasificación es de su estancia (o, si no hay, se llama exactamente como se pidió).
	estancias = set(co.CONTEXTOS[uso].estancias)
	de_su_estancia = [objeto for objeto in colocados if estancias & set(catalogo.definicion_de(objeto).estancias)]
	assert len(de_su_estancia) >= len(colocados) - 2, sorted(tipos)
	# Con aplicar=False se propone sin tocar la planta.
	entorno, planta, espacio = _habitacion(uso, ancho, fondo)
	propuesta = co.amueblar_espacio(entorno, planta, espacio, uso, catalogo, aplicar=False)
	assert planta.objetos == [] and [o.tipo for o in propuesta] == [o.tipo for o in colocados]


@pytest.mark.parametrize("uso", [*HABITACIONES, *USOS_NUEVOS])
def test_en_una_habitacion_de_dos_por_dos_nada_queda_mas_grande_que_ella(catalogo, uso):
	entorno, planta, espacio = _habitacion(uso, 2.0, 2.0)
	preferidos = HABITACIONES[uso][4] if uso in HABITACIONES else ()
	colocados = co.amueblar_espacio(entorno, planta, espacio, uso, catalogo, preferidos=preferidos)
	_comprobar_colocados(entorno, planta, espacio, catalogo)
	for objeto in colocados:
		assert objeto.ancho <= 2.0 + 1e-6 and objeto.fondo <= 2.0 + 1e-6, objeto.nombre
	# Lo que no cabe ni en su tamaño más pequeño no se coloca.
	tipos = {objeto.tipo for objeto in colocados}
	assert not tipos & {
		"hogar/sofa_ele",
		"sanidad/cama_hospital",
		"calle/coche",
		"parque_y_naturaleza/columpio_doble",
		"hosteleria/cama_hotel_cabecero_corrido",
	}
	superficie = sum(geo.area(catalogo.huella(o)) for o in colocados if catalogo.bloquea(o))
	assert superficie < 4.0


def test_lo_que_no_cabe_no_se_coloca_y_lo_que_cabe_se_ajusta(catalogo):
	entorno, planta, espacio = _habitacion("dormitorio", 2.0, 2.0)
	# Una góndola de supermercado en su tamaño por defecto (4 m) no cabe: se queda en su variante de 1 m.
	gondola = co.colocar_contra_pared(entorno, planta, espacio, "oficina_y_comercio/gondola", catalogo, "norte")
	assert gondola.colocado and gondola.objeto.variante == "un_modulo" and gondola.objeto.ancho == pytest.approx(1.0)
	planta.objetos.clear()
	# Un coche (mínimo 3,5 m de largo) o una marquesina (mínimo 2,6 m) no caben de ninguna manera.
	for tipo in ("calle/coche", "transporte/marquesina", "hogar/sofa_ele", "calle/bancos_rotonda", "vehiculos_y_aparcamiento/autocar"):
		resultado = co.colocar_contra_pared(entorno, planta, espacio, tipo, catalogo, "norte")
		assert not resultado.colocado and resultado.avisos[0].codigo == "no_cabe", tipo
	assert planta.objetos == []
	# La cama de 1,35 no cabe en un hueco de 1,20: se elige la variante de 1,05.
	assert catalogo.ajustar_a_hueco(catalogo.objeto("hogar/cama"), 1.2, 2.0) == pytest.approx((1.05, 1.9))


# ── Entornos de ejemplo ──────────────────────────────────────────────────────


@pytest.mark.parametrize(
	("nombre", "minimo", "complementos", "tipos"),
	[
		("vivienda-de-ejemplo", 18, {"hogar"}, {"hogar/cama", "hogar/sofa", "hogar/frigorifico", "hogar/inodoro"}),
		(
			"centro-de-dos-plantas",
			50,
			{"hogar", "colegio", "oficina_y_comercio"},
			{"colegio/pupitre", "colegio/pizarra", "oficina_y_comercio/mesa_despacho"},
		),
		(
			"barrio-de-ejemplo",
			40,
			{"calle", "transporte", "oficina_y_comercio"},
			{"calle/semaforo_peatones", "calle/farola", "transporte/marquesina", "calle/pavimento_botones"},
		),
	],
)
def test_los_ejemplos_se_amueblan_y_siguen_validando(catalogo, nombre, minimo, complementos, tipos):
	entorno = ejemplos.EJEMPLOS[nombre]()
	colocados = ejemplos.amueblar_ejemplos(entorno, catalogo)
	assert len(colocados) >= minimo
	assert set(entorno.complementos) == complementos
	assert {objeto.tipo for objeto in colocados} >= tipos
	assert sum(len(planta.objetos) for planta in entorno.plantas) == len(colocados)
	assert not any(a.es_error for a in validar(entorno, catalogo)), [str(a) for a in validar(entorno, catalogo) if a.es_error]
	assert len(set(entorno.ids())) == len(entorno.ids())
	for planta in entorno.plantas:
		for objeto in planta.objetos:
			avisos = co.comprobar(entorno, planta, objeto, catalogo)
			assert not any(a.es_error or a.codigo == "tapa_abertura" for a in avisos), (objeto.nombre, [str(a) for a in avisos])
	# El punto de inicio sigue libre.
	inicio = entorno.inicio
	planta_inicio = entorno.planta(inicio.planta)
	assert not any(catalogo.bloquea(o) and geo.punto_en_poligono((inicio.x, inicio.y), catalogo.huella(o)) for o in planta_inicio.objetos)


@pytest.mark.parametrize("nombre", list(ejemplos.EJEMPLOS))
def test_los_ejemplos_distribuidos_estan_amueblados_con_los_de_serie(catalogo, nombre):
	paquete = cargar_paquete(EJEMPLOS / f"{nombre}.elab")
	entorno = paquete.entorno
	objetos = [objeto for planta in entorno.plantas for objeto in planta.objetos]
	assert len(objetos) >= 18
	assert catalogo.tipos_que_faltan(objetos) == []
	assert set(entorno.complementos) <= set(ORIGINALES)
	assert not any(a.es_error for a in validar(entorno, catalogo))
	# El fichero distribuido es el que sale hoy de generar y amueblar el ejemplo.
	nuevo = ejemplos.EJEMPLOS[nombre]()
	ejemplos.amueblar_ejemplos(nuevo, catalogo)
	assert [(o.tipo, o.variante, round(o.x, 3), round(o.y, 3)) for p in nuevo.plantas for o in p.objetos] == [
		(o.tipo, o.variante, round(o.x, 3), round(o.y, 3)) for o in objetos
	]


# ── Inglés ───────────────────────────────────────────────────────────────────


def test_el_ingles_esta_completo(catalogo, catalogo_ingles):
	assert catalogo_ingles.avisos == []
	iguales = []
	for definicion in _de_serie(catalogo):
		traducido = catalogo_ingles.objeto(definicion.tipo)
		textos = json.loads((PLUGINS / definicion.complemento / "locales" / "en.json").read_text(encoding="utf-8"))["objetos"][
			definicion.id
		]
		assert traducido.nombre == textos["nombre"] and traducido.nombre, definicion.tipo
		if traducido.nombre == definicion.nombre:
			iguales.append(definicion.tipo)
		assert traducido.descripcion == textos["descripcion"] != definicion.descripcion, definicion.tipo
		assert len(traducido.descripcion) >= 20, definicion.tipo
		# Las etiquetas inglesas se suman a las españolas: se encuentra en los dos idiomas.
		assert len(textos["etiquetas"]) >= 1 and set(traducido.etiquetas) >= set(definicion.etiquetas) | set(textos["etiquetas"]), (
			definicion.tipo
		)
		for variante, original in zip(traducido.variantes, definicion.variantes, strict=True):
			assert variante.nombre == textos["variantes"][variante.id], (definicion.tipo, variante.id)
			assert (variante.ancho, variante.fondo, variante.alto) == (original.ancho, original.fondo, original.alto)
		for accion in traducido.acciones:
			assert accion["nombre"] == textos["acciones"][accion["id"]], (definicion.tipo, accion["id"])
		assert traducido.imagen["descripcion"] == textos["imagen"] != definicion.imagen["descripcion"], definicion.tipo
		if definicion.aviso:
			assert traducido.aviso == textos["aviso"] != definicion.aviso, definicion.tipo
		for estado in definicion.estados:
			assert catalogo_ingles.nombre_estado(definicion.tipo, estado) != catalogo.nombre_estado(definicion.tipo, estado), (
				definicion.tipo,
				estado,
			)
	# Solo un puñado de nombres se escriben igual en los dos idiomas («Minibar», «Karaoke»…).
	assert len(iguales) <= 0.01 * len(_de_serie(catalogo)), iguales
	for id_complemento in TODOS:
		espanol, ingles = catalogo.complemento(id_complemento), catalogo_ingles.complemento(id_complemento)
		assert ingles.nombre != espanol.nombre and ingles.descripcion != espanol.descripcion
		assert set(ingles.categorias) == set(espanol.categorias)
		assert all(ingles.categorias[clave] != espanol.categorias[clave] for clave in espanol.categorias), id_complemento
		assert set(ingles.subcategorias) == set(espanol.subcategorias)
		assert set(ingles.estados) == set(espanol.estados)


def test_buscar_en_los_dos_idiomas(catalogo, catalogo_ingles):
	assert catalogo_ingles.objeto("hogar/armario").nombre == "Wardrobe"
	assert catalogo_ingles.objeto("hogar/armario").acciones[0]["nombre"] == "Open"
	assert catalogo_ingles.objeto("hogar/cama").variante("ancho_135").nombre == "Double (135 cm)"
	assert catalogo_ingles.nombre_categoria("dormitorio") == "Bedroom"
	assert catalogo_ingles.nombre_estado("calle/semaforo_peatones", "verde") == "Green: you may cross"
	assert catalogo.nombre_estado("calle/semaforo_peatones", "verde") == "Verde: puedes cruzar"
	assert "hogar/armario" in {d.tipo for d in catalogo_ingles.buscar("wardrobe")}
	assert "hogar/armario" in {d.tipo for d in catalogo_ingles.buscar("ropero")}
	assert "calle/farola" in {d.tipo for d in catalogo_ingles.buscar("street lamp", ambito="exterior")}
	assert "sanidad/silla_ruedas_abierta" in {d.tipo for d in catalogo_ingles.buscar_avanzado("wheelchair", limite=10)}
	assert catalogo_ingles.arbol()[0].nombre == catalogo_ingles.complementos()[0].nombre
	# El amueblado asistido funciona igual con el catálogo en inglés: busca por las etiquetas españolas, que se conservan.
	entorno, planta, espacio = _habitacion("dormitorio", 3.5, 3.2)
	colocados = co.amueblar_espacio(entorno, planta, espacio, "dormitorio", catalogo_ingles, preferidos=("hogar",))
	assert "hogar/cama" in {objeto.tipo for objeto in colocados} and colocados[0].nombre == "Bed"
	entorno, planta, espacio = _habitacion("consulta", 4.0, 3.5)
	assert "sanidad/camilla_exploracion" in {o.tipo for o in co.amueblar_espacio(entorno, planta, espacio, "consulta", catalogo_ingles)}


# ── Herramienta y empaquetado ────────────────────────────────────────────────


@pytest.mark.parametrize("id_complemento", SERIE)
def test_los_json_distribuidos_salen_de_las_definiciones(id_complemento):
	"""Si falla, alguien cambió una definición o un JSON sin ejecutar ``tools/generar_complementos.py``."""
	serie = herramienta.definicion(id_complemento)
	ficha = herramienta.ficha_de(serie)
	carpeta = PLUGINS / id_complemento
	assert (carpeta / "complemento.json").read_text(encoding="utf-8") == herramienta.a_json(ficha) + "\n"
	assert (carpeta / "locales" / "en.json").read_text(encoding="utf-8") == herramienta.a_json(
		herramienta.traduccion_de(serie, ficha)
	) + "\n"
	assert json.loads(herramienta.a_json(ficha)) == ficha


def test_los_indices_estan_al_dia():
	assert (PLUGINS / "LEEME.md").read_text(encoding="utf-8") == herramienta.leeme_general(PLUGINS)
	catalogo_md = (PLUGINS / "CATALOGO.md").read_text(encoding="utf-8")
	assert catalogo_md == herramienta.catalogo_md(PLUGINS)
	# Navegable por encabezados: un nivel 2 por complemento y un nivel 3 por categoría con objetos.
	assert len(re.findall(r"^## ", catalogo_md, re.MULTILINE)) == len(SERIE) + 1
	assert len(re.findall(r"^### .+: ", catalogo_md, re.MULTILINE)) == sum(
		len({o["categoria"] for o in _ficha(i)["objetos"]}) for i in SERIE
	)
	assert "### Por función" in catalogo_md and "| Asiento |" in catalogo_md
	informe = herramienta.informe(PLUGINS)
	assert informe.startswith(f"Total: {sum(len(_ficha(i)['objetos']) for i in SERIE)} objetos en {len(SERIE)} complementos.")


@pytest.mark.lento
def test_la_herramienta_es_reproducible(tmp_path):
	_copiar_con_dependencias("transporte", tmp_path)
	assert herramienta.generar("transporte", tmp_path) == []
	original, nuevo = PLUGINS / "transporte", tmp_path / "transporte"
	ficheros = sorted(ruta.relative_to(original).as_posix() for ruta in original.rglob("*") if ruta.is_file())
	assert ficheros == sorted(ruta.relative_to(nuevo).as_posix() for ruta in nuevo.rglob("*") if ruta.is_file())
	for relativa in ficheros:
		assert (
			hashlib.sha256((original / relativa).read_bytes()).hexdigest() == hashlib.sha256((nuevo / relativa).read_bytes()).hexdigest()
		), relativa
	# «--recursos» vuelve a dibujar desde el JSON que haya, sin tocarlo, y quita lo que sobra.
	(nuevo / "imagenes" / "sobra.png").write_bytes(b"x")
	(nuevo / "imagenes" / "torno.png").unlink()
	antes = (nuevo / "complemento.json").read_bytes()
	assert herramienta.generar("transporte", tmp_path, solo_recursos=True) == []
	assert (nuevo / "complemento.json").read_bytes() == antes
	assert (nuevo / "imagenes" / "torno.png").read_bytes() == (original / "imagenes" / "torno.png").read_bytes()
	assert not (nuevo / "imagenes" / "sobra.png").exists()
	assert herramienta.main(["--carpeta", str(tmp_path), "--solo", "transporte", "--comprobar"]) == 0
	(nuevo / "sonidos" / "torno.flac").unlink()
	assert any("torno" in problema for problema in herramienta.comprobar(nuevo))
	assert herramienta.main(["--carpeta", str(tmp_path), "--solo", "transporte", "--comprobar"]) == 1


def test_un_complemento_de_serie_se_empaqueta_y_se_instala(tmp_path):
	paquete = empaquetar_complemento(PLUGINS / "juego", tmp_path / "juego.elabc")
	destino = tmp_path / "plugins"
	destino.mkdir()
	# Se instala donde ya están los complementos de los que depende (los de serie vienen con el programa).
	_copiar_con_dependencias("juego", destino)
	assert instalar_complemento(paquete, destino) == "juego"
	instalado = Catalogo.cargar(destino, idioma="en")
	assert instalado.avisos == []
	assert len(instalado.complemento("juego").objetos) == len(_ficha("juego")["objetos"])
	assert instalado.objeto("juego/cofre").nombre == "Treasure chest"
	assert validar_complemento(destino / "juego") == []
	assert paquete.stat().st_size < 6 * 1024 * 1024
	# Sin sus dependencias se carga igual, pero avisa de que faltan sonidos.
	solo = tmp_path / "solo"
	solo.mkdir()
	instalar_complemento(paquete, solo)
	assert {a.codigo for a in Catalogo.cargar(solo, idioma="es").avisos} == {"dependencia_ausente"}


# ── Documentación ────────────────────────────────────────────────────────────


def test_el_ejemplo_de_la_guia_es_un_complemento_valido(tmp_path):
	guia = (RAIZ / "docs" / "crear-un-complemento.md").read_text(encoding="utf-8")
	bloques = [trozo.split("```")[0] for trozo in guia.split("```json")[1:]]
	# Todo lo que en la guía se presenta como un JSON entero se puede leer.
	enteros = [json.loads(bloque) for bloque in bloques if bloque.lstrip().startswith("{")]
	assert len(enteros) >= 8
	ficha = json.loads(guia.split("<!-- ejemplo-completo -->")[1].split("```json")[1].split("```")[0])
	raiz = tmp_path / "plugins"
	carpeta = raiz / ficha["id"]
	carpeta.mkdir(parents=True)
	(carpeta / "complemento.json").write_text(json.dumps(ficha, ensure_ascii=False, indent="\t"), encoding="utf-8")
	(carpeta / "locales").mkdir()
	traduccion = next(bloque for bloque in enteros if "objetos" in bloque and isinstance(bloque["objetos"], dict))
	(carpeta / "locales" / "en.json").write_text(json.dumps(traduccion, ensure_ascii=False), encoding="utf-8")
	assert [str(a) for a in validar_complemento(carpeta)] == []
	ejemplo = Catalogo.cargar(raiz, idioma="es")
	assert ejemplo.avisos == [] and len(ejemplo.objetos()) == 6
	# Las fichas sueltas que se explican paso a paso son las mismas que las del ejemplo completo.
	sueltas = {bloque["id"]: bloque for bloque in enteros if "medidas" in bloque}
	assert set(sueltas) == {objeto["id"] for objeto in ficha["objetos"]}
	for objeto in ficha["objetos"]:
		assert {clave: valor for clave, valor in objeto.items() if clave in sueltas[objeto["id"]]} == sueltas[objeto["id"]], objeto["id"]
	de_serie = set(json.loads((RAIZ / "data" / "sounds" / "catalogo.json").read_text(encoding="utf-8"))["sonidos"])
	for definicion in ejemplo.objetos():
		assert all(nombre in de_serie for nombre in _sonidos_de(definicion)), definicion.tipo
	assert not ejemplo.objeto("mi-centro/cartel_colgante").detectable_baston
	assert ejemplo.objeto("mi-centro/felpudo").suelo == "moqueta"
	assert Catalogo.cargar(raiz, idioma="en").objeto("mi-centro/banco_espera").nombre == "Waiting bench"
	# El ejemplo de la guía también está clasificado, y su clasificación se puede filtrar.
	assert all(d.funcion and d.lugares and d.estancias for d in ejemplo.objetos())
	assert "mi-centro/banco_espera" in {d.tipo for d in ejemplo.buscar_avanzado(funcion="asiento", estancia="sala_espera")}
	# Y se empaqueta e instala como dice la guía.
	destino = tmp_path / "instalados"
	destino.mkdir()
	assert instalar_complemento(empaquetar_complemento(carpeta, tmp_path / "mi-centro-1.0.0.elabc"), destino) == "mi-centro"
	entorno, planta, espacio = _habitacion("oficina", 5.0, 4.0)
	assert co.colocar_en_esquina(entorno, planta, espacio, "mi-centro/mostrador", ejemplo, "noreste").colocado


def test_la_documentacion_nombra_lo_que_existe(catalogo):
	general = (PLUGINS / "LEEME.md").read_text(encoding="utf-8")
	for id_complemento in SERIE:
		assert f"[`{id_complemento}`]({id_complemento}/LEEME.md)" in general
		assert f"| {len(catalogo.complemento(id_complemento).objetos)} |" in general
	assert f"En total, {len(_de_serie(catalogo))} objetos." in general
	for documento in ("docs/crear-un-complemento.md", "docs/formato-de-complementos.md", "docs/catalogo-de-complementos.md"):
		assert documento in general and (RAIZ / documento).is_file(), documento
	formato = (RAIZ / "docs" / "formato-de-complementos.md").read_text(encoding="utf-8")
	for clave in (
		"`paso_libre`",
		"`suelo`",
		"`aviso`",
		"`estados`",
		"### Dinámica",
		"temporizador",
		"`preferidos",
		"`depende_de`",
		"`subcategorias`",
	):
		assert clave in formato, clave
	# La taxonomía está documentada valor por valor.
	for faceta, tabla in TAXONOMIAS.items():
		if faceta in ("ambito", "colocacion"):
			continue
		for clave in tabla:
			assert f"`{clave}`" in formato, (faceta, clave)
	guia = (RAIZ / "docs" / "crear-un-complemento.md").read_text(encoding="utf-8")
	assert "empaquetar_complemento" in guia and "validar_complemento" in guia and "docs/catalogo-de-complementos.md" in guia
	for clave in ("`funcion`", "`lugares`", "`estancias`", "`subcategoria`", "`frecuencia`", "`obstaculo`"):
		assert clave in guia, clave
