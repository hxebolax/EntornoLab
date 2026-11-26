"""Pruebas de la lógica sin wx del Estudio: árbol, filas, propiedades, plantillas, menús y archivos."""

from __future__ import annotations

import pytest

from app.core.config import Configuracion
from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio.edicion import ErrorEdicion
from app.dominio.formato import cargar_paquete
from app.dominio.modelo import hay_errores
from app.dominio.validacion import validar
from app.ui import archivos, menus, operaciones
from app.ui.contexto import ContextoEstudio
from app.ui.esquemas import letra_de
from app.ui.esquemas_elementos import ORDENES, esquema_de
from tests.test_dominio_comun import piso_minimo


@pytest.fixture
def contexto():
	ctx = ContextoEstudio(None, Configuracion())
	ctx.abrir_documento(piso_minimo()[0])
	return ctx


def test_arbol_plantas_espacios_y_contenido():
	entorno, planta, salon, cocina = piso_minimo()
	ed.anadir_fuente(entorno, planta, "Frigorífico", 6.5, 3.5, "fuente/frigorifico")
	ed.anadir_referencia(entorno, planta, "Ventana del salón", 1.0, 3.9)
	ed.anadir_pared(entorno, planta, (20, 0), (24, 0), "Valla")
	arbol = operaciones.arbol_de(entorno)
	assert arbol.clave == operaciones.CLAVE_ENTORNO and "Piso mínimo" in arbol.texto
	nodo_planta = arbol.buscar(planta.id)
	nodo_salon = arbol.buscar(salon.id)
	nodo_cocina = arbol.buscar(cocina.id)
	assert nodo_planta is not None and nodo_salon in nodo_planta.hijos
	puerta = planta.aberturas[0]
	assert [h.id for h in nodo_salon.hijos if h.id == puerta.id], "la puerta sale bajo el salón"
	assert [h.id for h in nodo_cocina.hijos if h.id == puerta.id], "y también bajo la cocina, con otra clave"
	claves = [nodo.clave for nodo in arbol.recorrer()]
	assert len(claves) == len(set(claves)), "las claves del árbol no se repiten"
	assert any("Frigorífico" in h.texto for h in nodo_cocina.hijos)
	assert any("Paredes sueltas" in h.texto for h in nodo_planta.hijos)
	assert arbol.buscar_id(puerta.id) is not None


def test_filas_de_cada_nodo():
	entorno, planta, salon, cocina = piso_minimo()
	fuente = ed.anadir_fuente(entorno, planta, "Frigorífico", 6.5, 3.5, "fuente/frigorifico")
	raiz = operaciones.filas_de_nodo(entorno, operaciones.CLAVE_ENTORNO)
	assert [fila.id for fila in raiz] == [planta.id]
	de_planta = operaciones.filas_de_nodo(entorno, planta.id)
	assert {salon.id, cocina.id} <= {fila.id for fila in de_planta}
	de_cocina = operaciones.filas_de_nodo(entorno, cocina.id)
	assert "Frigorífico" in [fila.nombre for fila in de_cocina]
	fila_salon = next(fila for fila in de_planta if fila.id == salon.id)
	assert fila_salon.celdas() == ("Salón", "Habitación", "5 × 4 m", "x 2,5, y 2")
	hoja = f"{cocina.id}/{fuente.id}"
	assert [f.id for f in operaciones.filas_de_nodo(entorno, hoja)] == [f.id for f in de_cocina], "una hoja enseña a sus hermanos"


def test_aplicar_valores_usa_las_funciones_de_edicion():
	entorno, planta, salon, _cocina = piso_minimo()
	valores = operaciones.valores_de(entorno, salon)
	assert valores["ancho"] == 5 and valores["x"] == 0
	assert operaciones.aplicar_valores(entorno, salon.id, dict(valores)) == [], "sin cambios no se toca nada"
	puerta = planta.aberturas[0]
	antes = puerta.centro()
	cambiadas = operaciones.aplicar_valores(entorno, salon.id, {**valores, "nombre": "Sala", "y": 2.0, "suelo": "madera"})
	assert cambiadas == ["nombre", "suelo", "y"]
	assert salon.nombre == "Sala" and salon.suelo == "madera"
	assert puerta.centro()[1] == pytest.approx(antes[1] + 2.0), "al mover la habitación se mueve su puerta"
	with pytest.raises(ErrorEdicion):
		operaciones.aplicar_valores(entorno, salon.id, {**operaciones.valores_de(entorno, salon), "nombre": "  "})
	fuente = ed.anadir_fuente(entorno, planta, "Reloj", 1, 3, "fuente/reloj")
	operaciones.aplicar_valores(entorno, fuente.id, {**operaciones.valores_de(entorno, fuente), "volumen": 50, "x": 2.0})
	assert fuente.volumen == pytest.approx(0.5) and fuente.x == 2.0
	operaciones.aplicar_valores(
		entorno, operaciones.CLAVE_ENTORNO, {**operaciones.valores_de(entorno, entorno), "autor": "Ana", "inicio_x": 1.0}
	)
	assert entorno.autor == "Ana" and entorno.inicio.x == 1.0


def test_cada_clase_de_elemento_tiene_esquema_y_valores():
	for entorno in ejemplos.todos().values():
		vistos = [(None, entorno)] + [(p, p) for p in entorno.plantas] + list(entorno.elementos())
		for _planta, elemento in vistos:
			campos = esquema_de(elemento, entorno)
			assert campos, type(elemento).__name__
			valores = operaciones.valores_de(entorno, elemento)
			for campo in campos:
				assert campo.clave in valores, f"{type(elemento).__name__}.{campo.clave} no tiene valor"


def test_puntos_escritos():
	assert operaciones.puntos_de_texto("0 0; 4 0; 4 3,5") == [(0.0, 0.0), (4.0, 0.0), (4.0, 3.5)]
	assert operaciones.texto_de_puntos([(0, 0), (4, 3.5)]) == "0 0; 4 3,5"
	with pytest.raises(ErrorEdicion) as error:
		operaciones.puntos_de_texto("0 0; 4")
	assert "punto 2" in str(error.value)
	with pytest.raises(ErrorEdicion):
		operaciones.puntos_de_texto("0 0", minimo=3)


def test_buscar_y_posicion_junto_a():
	entorno, planta, _salon, cocina = piso_minimo()
	assert [i for i, _r in operaciones.buscar_elementos(entorno, "cocina habitacion")] == [cocina.id]
	assert len(operaciones.buscar_elementos(entorno, "")) >= 4
	posicion = operaciones.posicion_junto_a(entorno, cocina.id)
	assert posicion is not None and posicion.planta == planta.id and cocina.contiene(posicion.x, posicion.y)
	assert operaciones.posicion_junto_a(entorno, operaciones.CLAVE_ENTORNO) is None


@pytest.mark.parametrize("clave", list(operaciones.PLANTILLAS))
def test_plantillas_dan_entornos_validos(clave):
	entorno = operaciones.crear_de_plantilla(clave, "Prueba", "Ana")
	assert entorno.nombre == "Prueba" and entorno.autor == "Ana" and entorno.plantas
	if clave not in ("en_blanco", "exterior"):
		# Las dos plantillas en blanco no tienen todavía ningún espacio: eso sí es un error hasta que se cree el primero.
		assert not hay_errores(validar(entorno)), [str(a) for a in validar(entorno) if a.es_error]
	with pytest.raises(ErrorEdicion):
		operaciones.crear_de_plantilla(clave, "  ")


def test_tabla_de_menus_bien_formada():
	from app.ui.ventana_principal import VentanaPrincipal

	def revisar(titulo, entradas):
		letras = []
		for entrada in entradas:
			if entrada is None:
				continue
			if menus.es_submenu(entrada):
				letras.append(letra_de(entrada[0]))
				if isinstance(entrada[1], list):
					revisar(entrada[0], entrada[1])
				continue
			nombre, etiqueta, ayuda, _tipo = menus.normalizar_entrada(entrada)
			assert ayuda, f"{nombre} no tiene texto de ayuda"
			assert letra_de(etiqueta), f"{etiqueta} no tiene letra de acceso"
			letras.append(letra_de(etiqueta))
			assert hasattr(VentanaPrincipal, f"_al_{nombre}") or nombre in ORDENES, f"la orden {nombre} no tiene quien la atienda"
		assert len(letras) == len(set(letras)), f"letras repetidas en {titulo}: {sorted(letras)}"

	titulos = [letra_de(titulo) for titulo, _e in menus.MENUS]
	assert len(titulos) == len(set(titulos))
	for titulo, entradas in menus.MENUS:
		revisar(titulo, entradas)
	atajos = [etiqueta.split("\t")[1] for _n, etiqueta, _a, _t in menus.ordenes(menus.MENUS) if "\t" in etiqueta]
	assert len(atajos) == len(set(atajos)), "ningún atajo se repite"
	assert "Esc" not in atajos and "Escape" not in atajos


def test_normalizar_entradas_de_otra_mano():
	canonica = ("mostrar_alumnos", "&Fichas...\tCtrl+L", "Abre las fichas.", "normal")
	assert menus.normalizar_entrada(("mostrar_alumnos", "&Fichas...\tCtrl+L", "Abre las fichas.")) == canonica
	assert menus.normalizar_entrada(("&Fichas...", "Ctrl+L", "Abre las fichas.", "mostrar_alumnos")) == canonica
	assert menus.normalizar_entrada({"nombre": "x", "etiqueta": "&X", "atajo": "F7", "ayuda": "a"}) == ("x", "&X\tF7", "a", "normal")
	assert menus.normalizar_entrada(("solo",)) is None


def test_contexto_ejecutar_deshacer_y_eventos(contexto, voz_simulada):
	vistos = []
	contexto.suscribir("entorno_cambiado", lambda: vistos.append("cambio"))
	contexto.suscribir("documento_cambiado", lambda ctx: vistos.append(ctx.modificado))
	contexto.ejecutar(
		"crear Baño",
		lambda: ed.crear_habitacion_rectangular(contexto.entorno, contexto.entorno.plantas[0], "Baño", 20, 0, 2, 2),
		anuncio="Hecho",
	)
	assert contexto.modificado and "cambio" in vistos and True in vistos and voz_simulada.contiene("Hecho")
	assert len(contexto.entorno.plantas[0].espacios) == 3
	with pytest.raises(ErrorEdicion):
		contexto.ejecutar(
			"pisar", lambda: ed.crear_habitacion_rectangular(contexto.entorno, contexto.entorno.plantas[0], "Encima", 0, 0, 2, 2)
		)
	assert contexto.historial.operaciones() == ["crear Baño"], "una operación que falla no entra en el historial"
	assert contexto.deshacer() == "crear Baño" and len(contexto.entorno.plantas[0].espacios) == 2
	assert contexto.rehacer() == "crear Baño" and len(contexto.entorno.plantas[0].espacios) == 3
	assert contexto.deshacer() and contexto.deshacer() is None
	with pytest.raises(ValueError):
		contexto.suscribir("no_existe", print)


def test_contexto_guardar_y_marcar_modificado(contexto, tmp_path):
	avisos = []
	contexto.suscribir("actividades_cambiadas", lambda: avisos.append(1))
	assert contexto.guardar() is False, "sin ruta ni ventana no se puede guardar"
	contexto.actividades.append({"formato": 1, "id": "act-1", "nombre": "Buscar", "tipo": "exploracion"})
	contexto.marcar_modificado("añadir actividad")
	assert contexto.modificado and avisos
	ruta = tmp_path / "piso.elab"
	assert contexto.guardar(ruta) is True and not contexto.modificado and contexto.ruta_paquete == ruta
	paquete = cargar_paquete(ruta)
	assert paquete.entorno.a_dict() == contexto.entorno.a_dict()
	assert [a["id"] for a in paquete.actividades] == ["act-1"]


def test_recientes_y_copia_de_recuperacion(contexto, tmp_path):
	config = contexto.configuracion
	uno, dos = tmp_path / "uno.elab", tmp_path / "dos.elab"
	for ruta in (uno, dos):
		assert contexto.guardar(ruta)
		archivos.anotar_reciente(config, ruta)
	archivos.anotar_reciente(config, uno)
	assert [r.name for r in archivos.recientes(config)] == ["uno.elab", "dos.elab"]
	dos.unlink()
	assert [r.name for r in archivos.recientes(config)] == ["uno.elab"], "un reciente borrado del disco no se ofrece"
	assert archivos.guardar_recuperacion(contexto) is None, "sin cambios no hay copia"
	contexto.ejecutar("renombrar", lambda: ed.renombrar(contexto.entorno, contexto.entorno.plantas[0].espacios[0], "Sala"))
	copia = archivos.guardar_recuperacion(contexto)
	assert copia is not None and copia.is_file() and contexto.modificado and contexto.ruta_paquete == dos
	recuperaciones = archivos.recuperaciones()
	assert len(recuperaciones) == 1 and recuperaciones[0].nombre == "Piso mínimo" and recuperaciones[0].ruta_original == dos
	assert cargar_paquete(recuperaciones[0].ruta).entorno.plantas[0].espacios[0].nombre == "Sala"
	archivos.borrar_recuperacion(contexto.entorno.id)
	assert archivos.recuperaciones() == []
	assert archivos.nombre_de_fichero("Casa de Ana") == "casa-de-ana.elab"
	assert archivos.con_extension(tmp_path / "x").name == "x.elab"
