"""Pruebas de los entornos de ejemplo y de la herramienta que los escribe en disco."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from app.dominio import colocacion as co
from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.formato import cargar_paquete, guardar_paquete
from app.dominio.modelo import Entorno, segmentos_solidos
from app.dominio.validacion import validar
from tests.test_dominio_comun import catalogo_de_prueba

RAIZ = Path(__file__).resolve().parent.parent


def _por_nombre(entorno: Entorno) -> dict[str, object]:
	return {elemento.nombre: elemento for _planta, elemento in entorno.elementos()}


def _alcanzables(entorno: Entorno) -> set[str]:
	"""Ids de los espacios a los que se llega desde el inicio cruzando aberturas (no ventanas) y conectores."""
	vecinos: dict[str, set[str]] = {}

	def unir(a: str, b: str) -> None:
		vecinos.setdefault(a, set()).add(b)
		vecinos.setdefault(b, set()).add(a)

	for planta in entorno.plantas:
		transitables = [e for e in planta.espacios if not e.macizo]
		for abertura in planta.aberturas:
			if abertura.tipo == "ventana":
				continue
			unidos = [e for e in ed.espacios_de_abertura(planta, abertura) if not e.macizo]
			for i, uno in enumerate(unidos):
				for otro in unidos[i + 1 :]:
					unir(uno.id, otro.id)
		# Las zonas sin paredes se comunican con las que tocan o pisan.
		for i, uno in enumerate(transitables):
			for otro in transitables[i + 1 :]:
				if uno.cerrado or otro.cerrado:
					continue
				if geo.distancia_entre_poligonos(uno.contorno, otro.contorno) < 0.01:
					unir(uno.id, otro.id)
	for conector in entorno.conectores:
		espacios = []
		for posicion in conector.posiciones():
			planta = entorno.planta(posicion.planta)
			espacio = planta.espacio_en(posicion.x, posicion.y, incluir_macizos=False)
			assert espacio is not None, conector.nombre
			espacios.append(espacio.id)
		for otro in espacios[1:]:
			unir(espacios[0], otro)
	planta_inicio = entorno.planta(entorno.inicio.planta)
	origen = planta_inicio.espacio_en(entorno.inicio.x, entorno.inicio.y, incluir_macizos=False)
	vistos = {origen.id}
	pendientes = [origen.id]
	while pendientes:
		actual = pendientes.pop()
		for siguiente in vecinos.get(actual, ()):
			if siguiente not in vistos:
				vistos.add(siguiente)
				pendientes.append(siguiente)
	return vistos


@pytest.mark.parametrize("nombre", list(ejemplos.EJEMPLOS))
def test_cada_ejemplo_es_valido_completo_y_recorrible(nombre):
	entorno = ejemplos.EJEMPLOS[nombre]()
	assert validar(entorno) == []
	assert validar(entorno, Catalogo()) == []
	assert entorno.nombre
	assert entorno.descripcion
	assert entorno.autor == "EntornoLab"
	assert entorno.procedencia["licencia"] == "CC0"
	assert entorno.complementos == []
	assert all(not planta.objetos for planta in entorno.plantas)
	ids = entorno.ids()
	assert len(ids) == len(set(ids))
	assert all(ids)
	# Todo tiene nombre: es lo que oye quien lo recorre.
	assert all(elemento.nombre for _planta, elemento in entorno.elementos())
	# Desde el inicio se llega a todos los espacios en los que se puede entrar.
	transitables = {e.id for planta in entorno.plantas for e in planta.espacios if not e.macizo}
	assert _alcanzables(entorno) == transitables
	# Hay sonidos fijos y referencias para orientarse.
	assert sum(len(planta.fuentes) for planta in entorno.plantas) >= 3
	assert sum(len(planta.referencias) for planta in entorno.plantas) >= 2
	assert all(fuente.sonido for planta in entorno.plantas for fuente in planta.fuentes)
	texto = ed.describir_entorno(entorno)
	assert texto.startswith(entorno.nombre)
	assert len(texto.splitlines()) > 15


@pytest.mark.parametrize("nombre", list(ejemplos.EJEMPLOS))
def test_cada_ejemplo_sobrevive_a_guardar_y_abrir(tmp_path, nombre):
	entorno = ejemplos.EJEMPLOS[nombre]()
	ruta = tmp_path / f"{nombre}.elab"
	guardar_paquete(ruta, entorno)
	paquete = cargar_paquete(ruta)
	assert paquete.entorno.a_dict() == entorno.a_dict()
	assert validar(paquete.entorno) == []
	# Construirlo dos veces da exactamente lo mismo: los ficheros distribuidos son reproducibles.
	assert ejemplos.EJEMPLOS[nombre]().a_dict() == entorno.a_dict()


def test_vivienda_de_ejemplo():
	entorno = ejemplos.vivienda_ejemplo()
	assert entorno.nombre == "Vivienda de ejemplo"
	assert len(entorno.plantas) == 1
	planta = entorno.plantas[0]
	assert sorted(e.nombre for e in planta.espacios) == ["Baño", "Cocina", "Dormitorio", "Entrada", "Pasillo", "Salón"]
	assert {e.nombre: e.datos.get("uso") for e in planta.espacios if e.datos.get("uso")} == {
		"Salón": "salon",
		"Cocina": "cocina",
		"Dormitorio": "dormitorio",
		"Baño": "bano",
	}
	nombres = _por_nombre(entorno)
	assert {"Frigorífico", "Reloj de pared"} <= set(nombres)
	assert planta.espacio_en(nombres["Frigorífico"].x, nombres["Frigorífico"].y).nombre == "Cocina"
	assert planta.espacio_en(nombres["Reloj de pared"].x, nombres["Reloj de pared"].y).nombre == "Salón"
	salidas = [a for a in planta.aberturas if a.es_salida]
	assert [a.nombre for a in salidas] == ["Puerta de la calle"]
	assert len([a for a in planta.aberturas if a.tipo == "ventana"]) == 3
	# Todas las estancias dan al pasillo.
	pasillo = nombres["Pasillo"]
	assert sorted(e.nombre for e, _lado in ed.vecinos(planta, pasillo)) == ["Baño", "Cocina", "Dormitorio", "Entrada", "Salón"]
	assert planta.espacio_en(entorno.inicio.x, entorno.inicio.y).nombre == "Entrada"
	assert len(planta.zonas) == 1
	assert entorno.conectores == []


def test_centro_de_dos_plantas():
	entorno = ejemplos.centro_dos_plantas()
	assert [p.nombre for p in entorno.plantas] == ["Planta baja", "Planta primera"]
	baja, primera = entorno.plantas
	assert primera.altura_m == pytest.approx(3.2)
	nombres_baja = {e.nombre for e in baja.espacios}
	assert {"Vestíbulo", "Aula 1", "Aula 2", "Conserjería", "Biblioteca"} <= nombres_baja
	assert any(nombre.startswith("Pasillo") for nombre in nombres_baja)
	assert any(nombre.startswith("Aseos") for nombre in nombres_baja)
	assert {"Aula 3", "Aula 4", "Aula 5", "Despacho de dirección", "Sala de informática"} <= {e.nombre for e in primera.espacios}
	salidas = [a for planta in entorno.plantas for a in planta.aberturas if a.es_salida]
	assert sorted(a.nombre for a in salidas) == ["Puerta principal", "Salida de emergencia este", "Salida de emergencia oeste"]
	assert all(a in baja.aberturas for a in salidas)
	assert sorted(c.tipo for c in entorno.conectores) == ["ascensor", "escalera"]
	escalera = next(c for c in entorno.conectores if c.tipo == "escalera")
	assert escalera.plantas() == [baja.id, primera.id]
	assert escalera.tramos[0].peldanos == 18
	assert baja.espacio_en(*escalera.tramos[0].desde.punto).tipo == "escalera"
	assert primera.espacio_en(*escalera.tramos[0].hasta.punto).tipo == "escalera"
	ascensor = next(c for c in entorno.conectores if c.tipo == "ascensor")
	assert [p.planta for p in ascensor.paradas] == [baja.id, primera.id]
	assert all(entorno.planta(p.planta).espacio_en(p.puerta.x, p.puerta.y).tipo == "pasillo" for p in ascensor.paradas)
	# El hueco del ascensor es macizo en las dos plantas: la cabina no se recorre andando.
	assert sum(1 for planta in entorno.plantas for e in planta.espacios if e.macizo) == 2
	assert baja.espacio_en(entorno.inicio.x, entorno.inicio.y).nombre == "Vestíbulo"
	# Las dos plantas ocupan la misma huella.
	assert baja.caja() == pytest.approx(primera.caja())


def test_barrio_de_ejemplo():
	entorno = ejemplos.barrio_ejemplo()
	assert len(entorno.plantas) == 1
	calle = entorno.plantas[0]
	assert calle.exterior
	assert sorted(v.nombre for v in calle.vias) == ["Calle Mayor", "Calle del Río"]
	tipos = [e.tipo for e in calle.espacios]
	assert tipos.count("acera") == 8
	assert tipos.count("paso_peatones") == 2
	assert tipos.count("calzada") == 3
	assert tipos.count("edificio") == 4
	assert tipos.count("vestibulo") == 1
	pasos = {e.datos["semaforo"]: e for e in calle.espacios if e.tipo == "paso_peatones"}
	assert pasos[True].datos["sonoro"] is True
	assert pasos[True].datos["pulsador"] is True
	assert pasos[False].datos["sonoro"] is False
	assert len([z for z in calle.zonas if z.suelo == "tactil_botones"]) == 4
	assert len([r for r in calle.referencias if r.tipo == "semaforo"]) == 2
	paradas = [r for r in calle.referencias if r.tipo == "parada"]
	assert len(paradas) == 1
	assert calle.espacio_en(paradas[0].x, paradas[0].y).tipo == "acera"
	portales = [a for a in calle.aberturas if a.tipo == "portal"]
	assert len(portales) == 4
	# Solo uno da paso de verdad: el del vestíbulo del centro cívico.
	pasables = [a for a in portales if {e.tipo for e in ed.espacios_de_abertura(calle, a)} == {"vestibulo", "acera"}]
	assert [a.nombre for a in pasables] == ["Portal del centro cívico"]
	assert pasables[0].es_salida
	assert pasables[0].deja_pasar()
	assert calle.espacio_en(entorno.inicio.x, entorno.inicio.y).tipo == "acera"
	assert calle.espacio_en(0, 0).nombre.startswith("Cruce")
	# Los edificios macizos son sólidos enteros y el portal del vestíbulo abre su pared.
	solidos = segmentos_solidos(calle)
	assert {s.clase for s in solidos} == {"pared", "macizo"}
	centro = pasables[0].centro()
	tramos = [(s.a, s.b) for s in solidos]
	assert geo.rayo_contra_segmentos((centro[0], centro[1] + 1.0), 180, tramos)[0] == pytest.approx(7.0)


def test_todos_devuelve_los_tres():
	conjunto = ejemplos.todos()
	assert list(conjunto) == ["vivienda-de-ejemplo", "centro-de-dos-plantas", "barrio-de-ejemplo"]
	assert [e.nombre for e in conjunto.values()] == ["Vivienda de ejemplo", "Centro de dos plantas", "Barrio de ejemplo"]
	assert len({e.id for e in conjunto.values()}) == 3


def test_amueblar_ejemplos_sin_complementos_no_hace_nada():
	entorno = ejemplos.vivienda_ejemplo()
	assert ejemplos.amueblar_ejemplos(entorno, Catalogo()) == []
	assert all(not planta.objetos for planta in entorno.plantas)


@pytest.mark.parametrize("nombre", ["vivienda-de-ejemplo", "centro-de-dos-plantas"])
def test_amueblar_ejemplos_con_catalogo(tmp_path, nombre):
	catalogo = catalogo_de_prueba(tmp_path)
	entorno = ejemplos.EJEMPLOS[nombre]()
	colocados = ejemplos.amueblar_ejemplos(entorno, catalogo)
	assert len(colocados) >= 10
	assert entorno.complementos == ["prueba"]
	assert sum(len(planta.objetos) for planta in entorno.plantas) == len(colocados)
	for planta in entorno.plantas:
		usados = {planta.espacio_en(o.x, o.y).nombre for o in planta.objetos}
		assert all(planta.espacio_en(o.x, o.y).datos.get("uso") for o in planta.objetos), usados
		for objeto in planta.objetos:
			avisos = co.comprobar(entorno, planta, objeto, catalogo)
			assert not any(a.es_error for a in avisos), (objeto.nombre, [str(a) for a in avisos])
			assert not any(a.codigo == "tapa_abertura" for a in avisos), objeto.nombre
	# Amueblado, sigue sin errores (puede haber avisos de paso estrecho que el profesional revisa).
	assert not any(a.es_error for a in validar(entorno, catalogo))
	assert len(set(entorno.ids())) == len(entorno.ids())


def test_herramienta_generar_ejemplos(tmp_path, capsys):
	especificacion = importlib.util.spec_from_file_location("generar_ejemplos", RAIZ / "tools" / "generar_ejemplos.py")
	modulo = importlib.util.module_from_spec(especificacion)
	especificacion.loader.exec_module(modulo)
	destino = tmp_path / "ejemplos"
	assert modulo.generar(destino) == 0
	ficheros = sorted(p.name for p in destino.iterdir())
	assert ficheros == ["barrio-de-ejemplo.elab", "centro-de-dos-plantas.elab", "vivienda-de-ejemplo.elab"]
	for fichero in destino.iterdir():
		paquete = cargar_paquete(fichero)
		assert validar(paquete.entorno) == []
		assert paquete.manifiesto["aplicacion"] == "EntornoLab"
	assert capsys.readouterr().out.count("Sin problemas.") == 3
	# Volver a generar deja copia .bak y no falla.
	assert modulo.generar(destino) == 0
	assert (destino / "vivienda-de-ejemplo.elab.bak").is_file()


def test_herramienta_por_defecto_escribe_en_data_ejemplos(datos_temporales, monkeypatch, capsys):
	especificacion = importlib.util.spec_from_file_location("generar_ejemplos", RAIZ / "tools" / "generar_ejemplos.py")
	modulo = importlib.util.module_from_spec(especificacion)
	especificacion.loader.exec_module(modulo)
	monkeypatch.setattr("sys.argv", ["generar_ejemplos.py"])
	assert modulo.main() == 0
	assert len(list((datos_temporales / "ejemplos").glob("*.elab"))) == 3
	assert "sin errores" in capsys.readouterr().out
