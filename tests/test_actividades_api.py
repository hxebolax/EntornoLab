"""La API pública de ``app.actividades``: tipos, campos, actividades nuevas, validación, reparto, descripción y recompensas.

Es el contrato con el reproductor y con el editor del Estudio: si algo de
aquí cambia de nombre o de forma, se rompen ellos.
"""

from __future__ import annotations

import copy
import dataclasses
import importlib.util
import inspect
import json
import re
from pathlib import Path

import pytest

import app.actividades as actividades
from app.actividades import (
	TIPOS,
	Actividad,
	Campo,
	InfoTipo,
	campos_de,
	crear_actividad,
	cuestionario,
	describir_actividad,
	leer_campo,
	normalizar,
	nueva_actividad,
	plantillas_de,
	poner_campo,
	puntuacion,
	recompensas,
	repartir_premios,
	validar_actividad,
)
from app.actividades.lugares import pista_de_lugar, punto_de_acceso, resolver_lugar
from app.actividades.textos import FRASES
from app.actividades.tipos import TIPOS_CAMPO
from app.dominio import edicion as ed
from app.dominio.formato import cargar_paquete, guardar_paquete
from app.dominio.modelo import Aviso, Objeto, Posicion
from app.motor.mundo import Mundo
from app.motor.navegacion import Navegador
from app.motor.percepcion import AYUDAS
from app.motor.sesion import AjustesJuego
from tests.test_actividades_comun import RAIZ, Jugador, barrio, catalogo_real, centro, ejemplo, espacio_en, vivienda

TIPOS_DE_ARQUITECTURA = (
	"exploracion busqueda recadero sacar_tesoros escondite sigue_guia explorador pistas ruta ruta_inversa volver_origen ruta_alternativa "
	"localizar perimetro linea_guia cruce visita_guiada examen_rutas examen_salida examen_senalar examen_distancias examen_reconstruccion"
).split()


def casa_vacia():
	return ejemplo("vivienda-de-ejemplo", False)


def codigos(avisos: list[Aviso], gravedad: str | None = None) -> set[str]:
	return {a.codigo for a in avisos if gravedad is None or a.gravedad == gravedad}


# ── Tipos y campos ───────────────────────────────────────────────────────────


def test_estan_todos_los_tipos_del_documento_de_arquitectura():
	assert set(TIPOS) == set(TIPOS_DE_ARQUITECTURA)
	assert set(actividades.CLASES) == set(TIPOS)
	for ident, info in TIPOS.items():
		assert isinstance(info, InfoTipo) and info.id == ident
		assert [c.name for c in dataclasses.fields(info)] == ["id", "nombre", "descripcion", "modo_por_defecto", "grupo"]
		assert info.grupo in ("juego", "practica", "examen") and info.modo_por_defecto in ("juego", "practica", "examen")
		assert info.nombre and info.descripcion and info.nombre_visible and info.descripcion_visible
		assert (info.grupo == "examen") == ident.startswith("examen_")
	assert sum(1 for i in TIPOS.values() if i.grupo == "examen") == 5


def test_campos_de_cada_tipo_sirven_para_generar_un_formulario():
	firma = [c.name for c in dataclasses.fields(Campo)]
	assert firma == ["clave", "etiqueta", "tipo", "ayuda", "opciones", "defecto", "minimo", "maximo", "grupo", "depende_de"]
	for tipo in TIPOS:
		campos = campos_de(tipo)
		claves = [c.clave for c in campos]
		assert len(claves) == len(set(claves)), tipo
		assert {"nombre", "estilo", "inicio", "ayudas", "mensajes.inicio"} <= set(claves)
		por_clave = {c.clave: c for c in campos}
		for campo in campos:
			assert campo.tipo in TIPOS_CAMPO, (tipo, campo.clave)
			assert campo.etiqueta and campo.ayuda, (tipo, campo.clave)
			if campo.tipo == "opcion":
				assert campo.opciones and all(len(par) == 2 for par in campo.opciones)
				assert campo.defecto in [valor for valor, _etiqueta in campo.opciones]
			if campo.tipo == "elemento":
				assert campo.opciones and set(campo.opciones) <= {"espacio", "abertura", "objeto", "referencia", "salida", "conector"}
			if campo.tipo in ("entero", "decimal") and campo.defecto is not None:
				assert campo.minimo <= campo.defecto <= campo.maximo, (tipo, campo.clave)
			if campo.depende_de:
				assert por_clave[campo.depende_de].tipo == "si_no"
		if TIPOS[tipo].grupo == "examen":
			assert {"numero_pruebas", "pruebas", "semilla", "regla_parada.de", "regla_parada.minimo"} <= set(claves)
			assert "tiempo_limite_s" not in claves and "baliza" not in claves
		else:
			assert {"tiempo_limite_s", "fallos_para_ayuda"} <= set(claves)
	assert por_campo("busqueda", "premios").tipo == "lista_premios"
	assert por_campo("recadero", "objetivos").tipo == "lista_objetivos"
	assert por_campo("examen_rutas", "tiempo_por_prueba_s").defecto == 360
	assert por_campo("escondite", "sonido").tipo == "sonido"
	assert por_campo("ruta", "inicio").tipo == "posicion"
	with pytest.raises(KeyError):
		campos_de("no_existe")


def por_campo(tipo: str, clave: str) -> Campo:
	return next(c for c in campos_de(tipo) if c.clave == clave)


def test_leer_y_poner_campos_anidados():
	datos: dict = {}
	poner_campo(datos, "travieso.activo", True)
	poner_campo(datos, "nombre", "Prueba")
	assert datos == {"travieso": {"activo": True}, "nombre": "Prueba"}
	assert leer_campo(datos, "travieso.activo") is True
	assert leer_campo(datos, "travieso.cada_s", 90) == 90 and leer_campo(datos, "mensajes.inicio") is None
	# Lo que escribe el formulario sobrevive a la normalización.
	limpio = normalizar(dict(datos, tipo="busqueda"))
	for campo in campos_de("busqueda"):
		assert leer_campo(limpio, campo.clave, "falta") != "falta", campo.clave
	assert limpio["travieso"]["activo"] is True


def test_firmas_de_la_api_obligatoria():
	def parametros(funcion) -> list[str]:
		return list(inspect.signature(funcion).parameters)

	assert parametros(nueva_actividad)[:3] == ["tipo", "entorno", "catalogo"]
	# ``recursos`` es opcional y va al final: quien llama con tres argumentos sigue igual.
	assert parametros(validar_actividad) == ["datos", "entorno", "catalogo", "recursos"]
	assert inspect.signature(validar_actividad).parameters["recursos"].default is None
	assert parametros(crear_actividad)[:5] == ["datos", "entorno", "catalogo", "estilo", "semilla"]
	assert parametros(repartir_premios) == ["entorno", "cantidad", "catalogo", "semilla", "plantas", "visibilidad", "dentro_de_objetos"]
	assert parametros(describir_actividad) == ["datos", "entorno"]
	assert parametros(recompensas.calcular) == ["resultado", "estilo"]
	firma = inspect.signature(repartir_premios)
	assert firma.parameters["visibilidad"].default == "cerca" and firma.parameters["dentro_de_objetos"].default is True
	for nombre in (
		"al_empezar",
		"tras_mover",
		"al_interactuar",
		"tic",
		"al_pedir",
		"resultado",
		"ajustes",
		"inicio",
		"estado",
		"orden_profesional",
	):
		assert callable(getattr(Actividad, nombre)), nombre
	assert parametros(Actividad.orden_profesional) == ["self", "sesion", "tipo", "datos"]
	for nombre in actividades.__all__:
		assert hasattr(actividades, nombre), nombre


def test_el_paquete_no_importa_interfaz_ni_sonido():
	"""Nada de wx, pygame ni sonido: se prueba sin ventana ni altavoces."""
	prohibidos = re.compile(r"^\s*(import|from)\s+(wx|pygame|sounddevice|numpy|app\.audio|app\.ui|app\.reproductor)\b", re.MULTILINE)
	for ruta in sorted((RAIZ / "app" / "actividades").glob("*.py")):
		texto = ruta.read_text(encoding="utf-8")
		assert not prohibidos.search(texto), ruta.name
		assert "from __future__ import annotations" in texto, ruta.name
		assert not re.search(r"^    +\S", texto, re.MULTILINE), f"{ruta.name}: se indenta con tabulaciones"


def test_todas_las_frases_que_se_usan_existen():
	"""Cada clave que el código pide a ``self.tx(...)`` está en la tabla de frases, con sus tres estilos si los tiene."""
	usadas: set[str] = set()
	for ruta in (RAIZ / "app" / "actividades").glob("*.py"):
		if ruta.name == "textos.py":
			continue
		texto = ruta.read_text(encoding="utf-8")
		usadas.update(re.findall(r"""\btx\(\s*["']([a-z_0-9]+)["']""", texto))
	assert len(usadas) > 60
	assert usadas <= set(FRASES), sorted(usadas - set(FRASES))
	for clave, frase in FRASES.items():
		assert isinstance(frase, str) or len(frase) == 3, clave
	# Las que se montan con una f-string.
	assert {"cruce_0", "cruce_1", "cruce_2", "cruce_3", "examen_distancias_camino", "examen_distancias_recta"} <= set(FRASES)


# ── Actividad nueva, estado y descripción ────────────────────────────────────


@pytest.mark.parametrize("nombre", ["vivienda-de-ejemplo", "centro-de-dos-plantas", "barrio-de-ejemplo"])
def test_nueva_actividad_de_cada_tipo_es_jugable(nombre):
	"""Cada tipo, recién creado en cada entorno de ejemplo, es JSON puro, se describe y no tiene errores (salvo los que el entorno no admite)."""
	entorno = ejemplo(nombre)
	catalogo = catalogo_real()
	esperados = {
		("vivienda-de-ejemplo", "cruce"): {"sin_calzada"},
		("centro-de-dos-plantas", "cruce"): {"sin_calzada"},
	}
	for tipo in TIPOS:
		datos = nueva_actividad(tipo, entorno, catalogo)
		assert datos["tipo"] == tipo and datos["formato"] == 1 and datos["modo"] == TIPOS[tipo].modo_por_defecto
		assert json.loads(json.dumps(datos)) == datos, tipo
		assert normalizar(datos) == datos, f"{tipo}: normalizar no es estable"
		descripcion = describir_actividad(datos, entorno)
		assert descripcion.startswith(datos["nombre"]) and descripcion.endswith(".")
		errores = codigos(validar_actividad(datos, entorno, catalogo), "error")
		assert errores == esperados.get((nombre, tipo), set()), (tipo, errores)
		actividad = crear_actividad(datos, entorno, catalogo)
		assert isinstance(actividad, actividades.CLASES[tipo])
		assert (actividad.id, actividad.nombre, actividad.tipo, actividad.modo, actividad.datos) == (
			datos["id"],
			datos["nombre"],
			tipo,
			datos["modo"],
			datos,
		)
		estado = actividad.estado()
		assert {"objetivo", "hechos", "total", "puntos", "estrellas", "tiempo_restante", "nivel"} <= set(estado)
		assert (actividad.inicio() is None) == (tipo not in ("perimetro", "linea_guia")), tipo
		assert isinstance(actividad.ajustes(AjustesJuego()), AjustesJuego)


def test_cada_tipo_arranca_y_dice_su_objetivo():
	"""Todos los tipos empiezan en la vivienda sin fallos en los ganchos y con un objetivo que decir."""
	entorno = vivienda()
	for tipo in TIPOS:
		if tipo == "cruce":
			continue
		jugador = Jugador(entorno, nueva_actividad(tipo, entorno, catalogo_real()))
		jugador.tic(5)
		estado = jugador.actividad.estado()
		assert not jugador.sesion.terminado, tipo
		assert estado["objetivo"], tipo
		assert estado["total"] >= 1, tipo
		assert jugador.dicho(), tipo
		jugador.pulsar("objetivo")
		jugador.sesion.terminar()
		jugador.tic(1)
		resultado = jugador.fin
		assert resultado["actividad"]["tipo"] == tipo
		for clave in (
			"completada",
			"examen",
			"valoracion",
			"recompensas",
			"puntuaciones",
			"estrellas",
			"cociente_camino",
			"nivel_siguiente",
			"aviso",
		):
			assert clave in resultado, (tipo, clave)
		assert json.loads(json.dumps(resultado)) == resultado, f"{tipo}: el resultado no es JSON puro"


def test_inicio_propio_y_opciones_de_nueva_actividad():
	entorno = casa_vacia()
	datos = nueva_actividad(
		"exploracion", entorno, inicio=Posicion("pla-1", 6.0, 2.0, 180.0), nombre="Desde la cocina", **{"mensajes.inicio": "Hola."}
	)
	actividad = crear_actividad(datos, entorno)
	assert actividad.inicio() == Posicion("pla-1", 6.0, 2.0, 180.0) and actividad.nombre == "Desde la cocina"
	jugador = Jugador(entorno, datos)
	assert jugador.espacio == "Cocina" and "Hola." in jugador.dicho()
	with pytest.raises(KeyError):
		nueva_actividad("no_existe", entorno)


def test_tipo_desconocido_se_juega_como_exploracion():
	"""Los datos nunca traen código: un tipo que no se conoce no rompe nada, y la validación lo dice."""
	entorno = casa_vacia()
	datos = {"tipo": "__import__('os').system('x')", "nombre": "Rara", "id": "rara"}
	assert codigos(validar_actividad(datos, entorno)) == {"tipo_desconocido"}
	jugador = Jugador(entorno, datos)
	jugador.tic(3)
	assert type(jugador.actividad).__name__ == "Exploracion" and not jugador.sesion.terminado


def test_normalizar_es_tolerante():
	limpio = normalizar(
		{
			"tipo": "busqueda",
			"premios": [{"nombre": "a", "x": "3", "y": 4.6, "planta": "pla-1", "visibilidad": "rara"}, "basura", {"id": "premio-1"}],
			"tiempo_limite_s": "nada",
			"ayudas": {"sonda": False, "pista": 2},
			"travieso": "sí",
			"nivel": 99,
			"estilo": "barroco",
			"regla_parada": 7,
		}
	)
	assert [p["id"] for p in limpio["premios"]] == ["premio-1", "premio-1-2"]
	assert limpio["premios"][0]["x"] == 3.0 and limpio["premios"][0]["visibilidad"] == "cerca"
	assert limpio["tiempo_limite_s"] is None and limpio["travieso"]["activo"] is False
	assert limpio["ayudas"] == {"sonda": {"permitida": False, "limite": None}, "pista": {"permitida": True, "limite": 2}}
	assert limpio["nivel"] == 0 and limpio["estilo"] == "del_alumno" and limpio["regla_parada"] is None
	assert normalizar(None)["tipo"] == "exploracion" and normalizar([1, 2])["modo"] == "practica"
	# Un examen no deja de serlo porque se le cambie el modo, ni admite travieso.
	examen = normalizar({"tipo": "examen_rutas", "modo": "juego", "travieso": {"activo": True}, "usar_niveles": True})
	assert examen["modo"] == "examen" and examen["travieso"]["activo"] is False and examen["niveles"] == []
	assert examen["regla_parada"] == {"activa": True, "de": 5, "minimo": 3} and examen["semilla"] == 1


def test_describir_actividad_para_lector_de_pantalla():
	entorno = vivienda()
	plantillas = plantillas_de("vivienda-de-ejemplo", entorno, catalogo_real())
	texto = describir_actividad(plantillas[0], entorno)
	assert "Búsqueda del tesoro en casa: Búsqueda del tesoro." in texto and "Es un juego, estilo infantil." in texto
	assert "Tiene 5 premios:" in texto and "dentro de" in texto and "se oye desde lejos" in texto
	assert "Al juntar 5 estrellas se desbloquea la casa del árbol." in texto
	assert "preguntas opcionales" in texto
	# Sin símbolos ni tablas: frases.
	assert not re.search(r"[|*#_\[\]{}]", texto)
	examen = describir_actividad(nueva_actividad("examen_rutas", entorno, semilla=42), entorno)
	assert "Es un examen" in examen and "semilla 42" in examen and "el tiempo en pausa no cuenta" in examen
	assert "Regla de parada: hacen falta 3 aciertos en las 5 primeras pruebas" in examen
	assert "Sin pistas, sin celebraciones y sin decir si se acierta." in examen
	rota = describir_actividad({"tipo": "ruta", "destino": "no-existe"}, entorno)
	assert "un lugar que no existe" in rota


# ── Lugares y pistas ─────────────────────────────────────────────────────────


def test_resolver_lugares_y_pistas_con_relaciones_reales():
	entorno = vivienda()
	planta = entorno.plantas[0]
	cocina = espacio_en(entorno, 6.0, 2.0)
	lugar = resolver_lugar(entorno, cocina.id)
	assert lugar.clase == "espacio" and lugar.nombre == "Cocina" and cocina.contiene(lugar.x, lugar.y)
	assert resolver_lugar(entorno, {"planta": planta.id, "x": 3.0, "y": 4.6}).nombre == "Pasillo"
	assert resolver_lugar(entorno, (planta.id, 3.0, 4.6)).clase == "punto"
	assert resolver_lugar(entorno, "no-existe") is None and resolver_lugar(entorno, None) is None
	assert resolver_lugar(entorno, {"planta": "no", "x": 1, "y": 1}) is None
	referencia = planta.referencias[0]
	assert resolver_lugar(entorno, referencia.id).clase == "referencia"
	nav = Navegador(Mundo(entorno, catalogo_real()))
	assert pista_de_lugar(entorno, nav, lugar, 1) == "Está en la habitación que queda al este de Salón."
	assert pista_de_lugar(entorno, nav, lugar, 2) == "Está en Cocina."
	assert pista_de_lugar(entorno, nav, lugar, 3).startswith("Está en Cocina, ")
	dormitorio = resolver_lugar(entorno, espacio_en(entorno, 2.0, 7.0).id)
	assert pista_de_lugar(entorno, nav, dormitorio, 1) == "Está en la habitación que queda al oeste de Baño."


def test_punto_de_acceso_a_un_mueble_pegado_a_la_pared():
	"""El sitio desde el que se usa un armario está en su habitación, no al otro lado del tabique."""
	entorno = vivienda()
	catalogo = catalogo_real()
	mundo = Mundo(entorno, catalogo)
	planta = entorno.plantas[0]
	contenedores = [o for o in planta.objetos if catalogo.definicion_de(o) is not None and catalogo.definicion_de(o).contenedor]
	assert contenedores
	for objeto in contenedores:
		acceso = punto_de_acceso(mundo, objeto.id)
		assert acceso is not None, objeto.nombre
		assert planta.espacio_en(*acceso) is planta.espacio_en(objeto.x, objeto.y), objeto.nombre
		assert mundo.dentro_de_objeto(planta.id, *acceso) is None


# ── Validación ───────────────────────────────────────────────────────────────


def test_validar_premios_imposibles():
	entorno = vivienda()
	catalogo = catalogo_real()
	planta = entorno.plantas[0]
	sofa = next(o for o in planta.objetos if "sofa" in o.tipo)
	silla = next(
		o
		for o in planta.objetos
		if catalogo.definicion_de(o) is not None and not catalogo.definicion_de(o).contenedor and catalogo.bloquea(o)
	)
	base = {"planta": planta.id, "visibilidad": "cerca"}
	datos = nueva_actividad(
		"busqueda",
		entorno,
		catalogo,
		premios=[
			dict(base, id="bien", nombre="bien", x=3.0, y=4.6),
			dict(base, id="muro", nombre="en el muro", x=-5.0, y=20.0),
			dict(base, id="planta", nombre="otra planta", x=1.0, y=1.0, planta="sotano"),
			dict(base, id="fantasma", nombre="dentro de nada", dentro_de="obj-999"),
			dict(base, id="sin", nombre="sin lugar", x=None, y=None),
			dict(base, id="mueble", nombre="tapado", x=sofa.x, y=sofa.y),
			dict(base, id="rara", nombre="en una silla", dentro_de=silla.id),
			dict(base, id="inicio", nombre="en el inicio", x=-1.0, y=4.9),
		],
	)
	avisos = validar_actividad(datos, entorno, catalogo)
	por_premio = {a.elemento_id: a for a in avisos}
	assert "bien" not in por_premio
	assert (por_premio["muro"].codigo, por_premio["muro"].gravedad) == ("fuera_de_espacio", "error")
	assert por_premio["planta"].codigo == "planta_no_existe" and por_premio["fantasma"].codigo == "contenedor_no_existe"
	assert por_premio["sin"].codigo == "premio_sin_lugar"
	assert (por_premio["mueble"].codigo, por_premio["mueble"].gravedad) == ("dentro_de_mueble", "aviso")
	assert (por_premio["rara"].codigo, por_premio["rara"].gravedad) == ("no_es_contenedor", "aviso")
	assert (por_premio["inicio"].codigo, por_premio["inicio"].gravedad) == ("premio_en_el_inicio", "aviso")
	# Los errores van primero y todos traen mensaje y sugerencia para la persona.
	gravedades = [a.gravedad for a in avisos]
	assert gravedades == sorted(gravedades, key=lambda g: 0 if g == "error" else 1)
	assert all(a.mensaje and a.sugerencia for a in avisos)
	# Un edificio macizo de la calle tampoco vale.
	calle = barrio()
	macizo = next(e for e in calle.plantas[0].espacios if e.macizo)
	centro_macizo = macizo.centro()
	datos = nueva_actividad(
		"busqueda", calle, premios=[{"id": "m", "nombre": "m", "planta": calle.plantas[0].id, "x": centro_macizo[0], "y": centro_macizo[1]}]
	)
	assert "dentro_de_macizo" in codigos(validar_actividad(datos, calle), "error")
	assert "sin_premios" in codigos(validar_actividad(nueva_actividad("busqueda", calle, premios=[]), calle), "error")


def test_validar_audio_de_los_premios_con_los_recursos_del_paquete():
	"""Con los recursos del paquete se avisa del audio que no viaja en él; sin ellos no se comprueba (compatibilidad)."""
	entorno = vivienda()
	planta = entorno.plantas[0]
	base = {"planta": planta.id, "visibilidad": "cerca", "x": 3.0, "y": 4.6}
	datos = nueva_actividad(
		"busqueda",
		entorno,
		premios=[
			dict(base, id="con", nombre="con audio", audio="sonidos/llaves.wav"),
			dict(base, id="corto", nombre="sin carpeta", audio="timbre.ogg"),
			dict(base, id="perdido", nombre="audio perdido", audio="sonidos/perdido.wav"),
			dict(base, id="mudo", nombre="sin audio"),
		],
	)
	sin_recursos = validar_actividad(datos, entorno)
	assert "audio_no_existe" not in codigos(sin_recursos), "sin recursos no se puede saber: no se comprueba"
	recursos = {"sonidos/llaves.wav": b"RIFF", "sonidos/timbre.ogg": b"OggS"}
	for como in (recursos, list(recursos), iter(list(recursos))):
		avisos = validar_actividad(datos, entorno, None, como)
		audios = [a for a in avisos if a.codigo == "audio_no_existe"]
		assert [(a.elemento_id, a.gravedad) for a in audios] == [("perdido", "aviso")], (
			"el nombre sin carpeta se busca en sonidos/, como Paquete.recurso"
		)
		assert "perdido.wav" in audios[0].mensaje and audios[0].sugerencia
		assert [a.codigo for a in avisos if a.codigo != "audio_no_existe"] == [a.codigo for a in sin_recursos]
	# Con un paquete real: lo que se guarda con el audio no avisa; sin él, sí.
	paquete_bien = validar_actividad(datos, entorno, recursos=["sonidos/llaves.wav", "sonidos/timbre.ogg", "sonidos/perdido.wav"])
	assert "audio_no_existe" not in codigos(paquete_bien)
	assert "audio_no_existe" in codigos(validar_actividad(datos, entorno, recursos=[]))


def test_validar_distingue_lo_imposible_de_lo_bloqueado_a_proposito():
	"""Un premio tras una puerta con llave es un aviso (puede ser a propósito); uno en una sala sin puerta, un error."""
	entorno = copy.deepcopy(casa_vacia())
	planta = entorno.plantas[0]
	bano = espacio_en(entorno, 5.5, 7.0)
	puerta_bano = next(a for a in planta.aberturas if a.hoja == "corredera")
	puerta_bano.estado = "con_llave"
	trastero = ed.crear_habitacion_rectangular(entorno, planta, "Trastero", 20.0, 20.0, 3.0, 3.0)
	datos = nueva_actividad(
		"busqueda",
		entorno,
		premios=[
			{"id": "cerrado", "nombre": "el del baño", "planta": planta.id, "x": 5.7, "y": 7.0},
			{"id": "aislado", "nombre": "el del trastero", "planta": planta.id, "x": 21.5, "y": 21.5},
		],
	)
	por_premio = {a.elemento_id: a for a in validar_actividad(datos, entorno)}
	assert (por_premio["cerrado"].codigo, por_premio["cerrado"].gravedad) == ("bloqueado", "aviso")
	assert "a propósito" in por_premio["cerrado"].sugerencia
	assert (por_premio["aislado"].codigo, por_premio["aislado"].gravedad) == ("inalcanzable", "error")
	# Lo mismo con el destino de una ruta.
	assert codigos(validar_actividad(nueva_actividad("ruta", entorno, destino=bano.id), entorno)) == {"bloqueado"}
	assert codigos(validar_actividad(nueva_actividad("ruta", entorno, destino=trastero.id), entorno), "error") == {"inalcanzable"}
	# Y el guía no sabe abrir con llave: para él es un error.
	assert "guia_sin_camino" in codigos(validar_actividad(nueva_actividad("sigue_guia", entorno, destino=bano.id), entorno), "error")


def test_validar_ids_inexistentes_e_inicio():
	entorno = casa_vacia()
	cocina = espacio_en(entorno, 6.0, 2.0)
	assert codigos(validar_actividad(nueva_actividad("ruta", entorno, destino="esp-999"), entorno), "error") == {"no_existe"}
	assert codigos(validar_actividad(dict(nueva_actividad("ruta", entorno), destino=None), entorno), "error") == {"sin_destino"}
	recado = nueva_actividad("recadero", entorno, objetivos=[{"recoger": cocina.id, "entregar": "ref-999"}, {"tipo": "ir_a"}])
	assert codigos(validar_actividad(recado, entorno), "error") == {"no_existe", "objetivo_sin_destino"}
	assert codigos(validar_actividad(nueva_actividad("recadero", entorno, objetivos=[]), entorno), "error") == {"sin_objetivos"}
	assert codigos(validar_actividad(nueva_actividad("perimetro", entorno, espacio="esp-999"), entorno), "error") == {"espacio_no_existe"}
	fuera = nueva_actividad("exploracion", entorno, inicio={"planta": "pla-1", "x": 50.0, "y": 50.0, "rumbo": 0})
	assert codigos(validar_actividad(fuera, entorno), "error") == {"inicio_fuera"}
	otra_planta = nueva_actividad("exploracion", entorno, inicio={"planta": "atico", "x": 1.0, "y": 1.0})
	assert codigos(validar_actividad(otra_planta, entorno), "error") == {"inicio_sin_planta"}
	assert codigos(validar_actividad("no soy un diccionario", entorno)) == {"formato"}
	assert codigos(validar_actividad(nueva_actividad("exploracion", entorno, ayudas={"telepatia": True}), entorno)) == {"ayuda_desconocida"}
	assert set(AYUDAS) >= set(actividades.NOMBRES_AYUDAS)
	# Validar no toca ni los datos ni el entorno.
	datos = nueva_actividad("busqueda", entorno, cantidad=3)
	copia, antes = copy.deepcopy(datos), entorno.a_dict()
	validar_actividad(datos, entorno)
	assert datos == copia and entorno.a_dict() == antes


def test_validar_salidas_cortes_y_examenes():
	casa = casa_vacia()
	# La vivienda solo tiene una salida: elegir la más cercana no mide nada.
	assert "una_sola_salida" in codigos(validar_actividad(nueva_actividad("sacar_tesoros", casa), casa), "aviso")
	assert "una_sola_salida" in codigos(validar_actividad(nueva_actividad("examen_salida", casa), casa), "aviso")
	sin_salidas = copy.deepcopy(casa)
	for abertura in sin_salidas.plantas[0].aberturas:
		abertura.es_salida = False
	assert "sin_salidas" in codigos(validar_actividad(nueva_actividad("examen_salida", sin_salidas), sin_salidas), "error")
	# Ruta alternativa: en la vivienda cada habitación tiene una sola puerta; cortarla deja sin camino.
	cocina = espacio_en(casa, 6.0, 2.0)
	puerta = next(a for a in casa.plantas[0].aberturas if a.tipo == "puerta" and abs(a.centro()[1] - 4.0) < 0.01 and a.centro()[0] > 4.5)
	assert "corte_sin_alternativa" in codigos(
		validar_actividad(nueva_actividad("ruta_alternativa", casa, destino=cocina.id, corte=puerta.id), casa), "error"
	)
	assert "sin_corte" in codigos(
		validar_actividad(nueva_actividad("ruta_alternativa", casa, destino=cocina.id, corte=None), casa), "aviso"
	)
	assert "corte_no_existe" in codigos(
		validar_actividad(nueva_actividad("ruta_alternativa", casa, destino=cocina.id, corte="abe-999"), casa), "error"
	)
	puerta_dormitorio = next(
		a for a in casa.plantas[0].aberturas if a.tipo == "puerta" and abs(a.centro()[1] - 5.2) < 0.01 and a.centro()[0] < 4.5
	)
	fuera = validar_actividad(nueva_actividad("ruta_alternativa", casa, destino=cocina.id, corte=puerta_dormitorio.id), casa)
	assert codigos(fuera) == {"corte_fuera_del_camino"}
	# Exámenes sin pruebas suficientes: una sola habitación no da para rutas.
	unico = ed.crear_entorno("Una sala")
	planta = ed.crear_planta(unico, "Planta")
	ed.crear_habitacion_rectangular(unico, planta, "Sala", 0, 0, 5, 4)
	ed.fijar_inicio(unico, planta, 1.0, 1.0, 0.0)
	for tipo in ("examen_rutas", "examen_senalar", "examen_distancias", "examen_reconstruccion"):
		assert "examen_sin_pruebas" in codigos(validar_actividad(nueva_actividad(tipo, unico), unico), "error"), tipo
	# Pedir más rutas de las que dan los espacios es un aviso, y la regla de parada más larga que el examen, otro.
	muchas = validar_actividad(nueva_actividad("examen_reconstruccion", casa, numero_pruebas=30), casa)
	assert codigos(muchas) == {"pruebas_insuficientes"}
	corta = validar_actividad(nueva_actividad("examen_rutas", casa, numero_pruebas=3, regla_parada={"de": 5, "minimo": 3}), casa)
	assert codigos(corta) == {"regla_parada_larga"}
	rotas = validar_actividad(
		nueva_actividad(
			"examen_rutas", casa, pruebas=[{"origen": cocina.id, "destino": "esp-999"}, {"origen": cocina.id, "destino": puerta.id}]
		),
		casa,
	)
	assert "pruebas_no_validas" in codigos(rotas, "error")
	vacio = ed.crear_entorno("Vacío")
	assert codigos(validar_actividad(nueva_actividad("exploracion", vacio), vacio)) == {"entorno_vacio"}


# ── Reparto asistido ─────────────────────────────────────────────────────────


def test_repartir_premios_obliga_a_pasar_por_todos_los_espacios():
	entorno = vivienda()
	catalogo = catalogo_real()
	planta = entorno.plantas[0]
	premios = repartir_premios(entorno, 6, catalogo, semilla=1)
	assert len(premios) == 6 and len({p["id"] for p in premios}) == 6
	espacios = set()
	for premio in premios:
		if premio["dentro_de"]:
			objeto = entorno.elemento(premio["dentro_de"])
			assert isinstance(objeto, Objeto) and catalogo.definicion_de(objeto).contenedor
			assert (premio["x"], premio["y"]) == (round(objeto.x, 3), round(objeto.y, 3))
		espacios.add(planta.espacio_en(premio["x"], premio["y"]).nombre)
	# Todos menos la entrada, que es donde se empieza (es tan pequeña que un premio allí se recogería nada más empezar).
	assert espacios == {"Pasillo", "Salón", "Cocina", "Dormitorio", "Baño"}
	# Donde hay contenedores del catálogo se usan; donde no, un punto libre.
	dentro = {planta.espacio_en(p["x"], p["y"]).nombre for p in premios if p["dentro_de"]}
	assert dentro == {"Salón", "Cocina", "Dormitorio"}
	assert codigos(validar_actividad(nueva_actividad("busqueda", entorno, catalogo, premios=premios), entorno, catalogo)) == set()
	# Misma semilla, mismo reparto; otra semilla, otro.
	assert repartir_premios(entorno, 6, catalogo, semilla=1) == premios
	assert any(repartir_premios(entorno, 6, catalogo, semilla=s) != premios for s in (2, 3, 4))
	# Con pocos premios se va a los extremos, nunca al espacio donde se empieza.
	pocos = repartir_premios(entorno, 2, catalogo, semilla=1)
	assert "Entrada" not in {planta.espacio_en(p["x"], p["y"]).nombre for p in pocos}
	# Sin objetos, con otra visibilidad, y más premios que espacios.
	sueltos = repartir_premios(entorno, 8, catalogo, semilla=1, visibilidad="lejos", dentro_de_objetos=False)
	assert len(sueltos) == 8 and all(p["dentro_de"] is None and p["visibilidad"] == "lejos" for p in sueltos)
	mundo = Mundo(entorno, catalogo)
	assert all(mundo.dentro_de_objeto(planta.id, p["x"], p["y"]) is None for p in sueltos)
	assert repartir_premios(entorno, 0) == [] and len(repartir_premios(entorno, 3)) == 3


def test_repartir_premios_por_plantas():
	entorno = centro()
	baja, primera = entorno.plantas
	solo_arriba = repartir_premios(entorno, 4, catalogo_real(), semilla=2, plantas=[primera.id])
	assert len(solo_arriba) == 4 and {p["planta"] for p in solo_arriba} == {primera.id}
	todos = repartir_premios(entorno, 12, catalogo_real(), semilla=2)
	assert {p["planta"] for p in todos} == {baja.id, primera.id}


# ── Puntuación, recompensas y cuestionario ───────────────────────────────────


def test_puntos_de_salida_3_2_1_0():
	salidas = [("este", 4.0), ("principal", 12.0), ("oeste", 20.0), ("garaje", 31.0)]
	assert [puntuacion.puntos_salida(s, salidas, 1.0) for s in ("este", "principal", "oeste", "garaje", "no-es-salida")] == [3, 2, 1, 0, 0]
	# Dos salidas que quedan igual de cerca (menos que la tolerancia) comparten puesto.
	empate = [("a", 5.0), ("b", 5.6), ("c", 15.0)]
	assert [puntuacion.puntos_salida(s, empate, 1.0) for s in ("a", "b", "c")] == [3, 3, 1]
	assert [puntuacion.puntos_salida(s, empate, 0.0) for s in ("a", "b", "c")] == [3, 2, 1]
	assert puntuacion.puntos_salida("a", [], 1.0) == 0


def test_error_angular_cociente_cruces_y_regla_de_parada():
	assert puntuacion.error_angular(350.0, 10.0) == 20.0 and puntuacion.error_angular(90.0, 270.0) == 180.0
	assert (
		puntuacion.cociente_camino(15.0, 10.0) == 1.5
		and puntuacion.cociente_camino(15.0, None) is None
		and puntuacion.cociente_camino(3.0, 0.0) is None
	)
	assert [
		puntuacion.puntos_cruce(*caso) for caso in ((False, True, False), (False, False, False), (False, True, True), (True, True, False))
	] == [3, 2, 1, 0]
	regla = {"de": 5, "minimo": 3}
	assert puntuacion.debe_parar([False, False], regla) is False
	assert puntuacion.debe_parar([False, True, False, False], regla) is True
	assert puntuacion.debe_parar([True, True, False, False], regla) is False
	assert puntuacion.debe_parar([True, True, True, False, False, False, False], regla) is False
	assert (
		puntuacion.debe_parar([False] * 5, None) is False
		and puntuacion.debe_parar([False] * 5, {"activa": False, "de": 5, "minimo": 3}) is False
	)
	assert puntuacion.mediana([3, 1, 2]) == 2 and puntuacion.mediana([1, 2, 3, 4]) == 2.5 and puntuacion.mediana([]) is None
	resumen = puntuacion.resumen_examen([{"acierto": True, "tiempo_s": 10}, {"acierto": False, "tiempo_s": 30}])
	assert (
		resumen["aciertos"] == 1
		and resumen["porcentaje_aciertos"] == 50.0
		and resumen["tiempo_medio_s"] == 20.0
		and resumen["tiempo_medio_aciertos_s"] == 10.0
	)


def test_estrellas_por_motivos_distintos():
	todas = puntuacion.MOTIVOS_ESTRELLA
	assert puntuacion.estrellas(True, todas, ayudas=0, cociente=1.1, media_salida=3.0, choques=0, exploracion=1.0, seguro=True) == list(
		todas
	)
	assert puntuacion.estrellas(True, todas, ayudas=5, cociente=2.0, media_salida=1.0, choques=3, exploracion=0.5, seguro=False) == [
		"completar"
	]
	# Sin completar no hay estrellas, salvo la de haberlo explorado todo.
	assert puntuacion.estrellas(False, todas, exploracion=1.0) == ["exploracion"]
	# Ganar nunca depende solo de seguir una baliza.
	assert "pocas_ayudas" not in puntuacion.estrellas(True, todas, ayudas=0, con_baliza_continua=True)
	assert puntuacion.estrellas(True, ("completar", "atajo"), cociente=1.2, choques=0) == ["completar", "atajo"]
	assert puntuacion.ayudas_contadas({"pista": 2, "sonda": 9, "donde_estoy": 1}) == 3


def test_recompensas_calcular():
	resultado = {
		"actividad": {"tipo": "sacar_tesoros", "modo": "juego"},
		"completada": True,
		"estrellas_motivos": ["completar", "salida_optima"],
		"estrellas_posibles": ["completar", "salida_optima"],
		"puntos": 6,
		"puntos_maximos": 6,
		"coleccion": ["el trofeo", "el trofeo", "el mapa"],
		"desbloqueos": [{"estrellas": 5, "nombre": "la casa del árbol"}, {"estrellas": 50, "nombre": "el castillo"}],
		"estrellas_previas": 3,
	}
	ganadas = recompensas.calcular(resultado, "infantil")
	assert all(set(r) >= {"tipo", "nombre"} and r["tipo"] in ("estrella", "medalla", "objeto") for r in ganadas)
	assert [r["tipo"] for r in ganadas] == ["estrella", "estrella", "medalla", "medalla", "objeto", "objeto", "objeto"]
	assert [r["nombre"] for r in ganadas if r["tipo"] == "objeto"] == ["el trofeo", "el mapa", "la casa del árbol"]
	# Tres estrellas previas más dos de hoy cruzan el umbral de cinco; con cinco previas ya estaba desbloqueada.
	assert "la casa del árbol" not in [r["nombre"] for r in recompensas.calcular(dict(resultado, estrellas_previas=5), "infantil")]
	# El estilo cambia los nombres, no lo que se gana.
	adulto = recompensas.calcular(resultado, "adulto")
	assert [r["tipo"] for r in adulto] == [r["tipo"] for r in ganadas] and adulto[0]["nombre"] != ganadas[0]["nombre"]
	assert "¡" not in " ".join(r["nombre"] for r in adulto)
	# Un examen mide, no premia. Y sin completar no hay medallas.
	assert recompensas.calcular(dict(resultado, actividad={"tipo": "examen_salida", "modo": "examen"}), "juvenil") == []
	a_medias = recompensas.calcular(dict(resultado, completada=False, estrellas_motivos=[]), "juvenil")
	assert [r["tipo"] for r in a_medias] == ["objeto", "objeto"]
	assert recompensas.calcular({}, "adulto") == [] and recompensas.calcular(None, "adulto") == []


def test_las_recompensas_del_resultado_las_entiende_el_seguimiento():
	"""Los registros ``recompensa`` del juego acaban en el resumen de la sesión tal como los espera ``app.seguimiento``."""
	from app.seguimiento.medidas import calcular_resumen
	from app.seguimiento.recompensas import TIPOS_RECOMPENSA

	entorno = casa_vacia()
	datos = nueva_actividad(
		"busqueda", entorno, premios=[{"id": "a", "nombre": "la pelota", "planta": "pla-1", "x": 3.0, "y": 4.6}], cuestionario=True
	)
	jugador = Jugador(entorno, datos)
	jugador.ir(("pla-1", 3.0, 4.6), cerca=0.3)
	jugador.actividad.valorar(jugador.sesion, {"esfuerzo": 1, "confianza": 4, "disfrute": 5})
	jugador.tic(1)
	resultado = jugador.fin
	from app.motor import eventos as ev

	sucesos = [{"t": e.datos.get("t", 0.0), "tipo": e.tipo, "datos": e.datos} for e in jugador.eventos if isinstance(e, ev.EvRegistro)]
	resumen = calcular_resumen([], sucesos, puntuaciones=resultado["puntuaciones"], resultado=resultado)
	assert [r["nombre"] for r in resumen["recompensas"]] == [r["nombre"] for r in resultado["recompensas"]]
	assert {r["tipo"] for r in resumen["recompensas"]} <= set(TIPOS_RECOMPENSA)
	assert [p["id"] for p in resumen["premios"]] == ["a"] and [o["id"] for o in resumen["objetivos"]] == ["a"]
	assert resumen["valoracion"]["disfrute"] == 5 and resumen["resultado"]["completada"] is True


def test_cuestionario_como_datos():
	for estilo in ("infantil", "juvenil", "adulto"):
		preguntas = cuestionario.preguntas(estilo)
		assert [p["id"] for p in preguntas] == ["esfuerzo", "confianza", "disfrute"]
		for pregunta in preguntas:
			assert pregunta["texto"].endswith("?") and pregunta["opcional"] is True
			assert [o["valor"] for o in pregunta["opciones"]] == [1, 2, 3, 4, 5] and all(o["texto"] for o in pregunta["opciones"])
		assert cuestionario.presentacion(estilo)
	textos = {estilo: [p["texto"] for p in cuestionario.preguntas(estilo)] for estilo in ("infantil", "juvenil", "adulto")}
	assert textos["infantil"] != textos["adulto"] != textos["juvenil"]
	assert json.loads(json.dumps(cuestionario.preguntas("adulto"))) == cuestionario.preguntas("adulto")
	assert cuestionario.normalizar_respuestas({"esfuerzo": 3, "confianza": "mucha", "disfrute": 0, "otra": 5}) == {
		"esfuerzo": 3,
		"confianza": None,
		"disfrute": None,
	}
	assert cuestionario.normalizar_respuestas(None) == {"esfuerzo": None, "confianza": None, "disfrute": None}


# ── Plantillas y paquetes de ejemplo ─────────────────────────────────────────


@pytest.mark.parametrize("nombre", ["vivienda-de-ejemplo", "centro-de-dos-plantas", "barrio-de-ejemplo"])
def test_las_plantillas_de_los_ejemplos_son_validas(nombre):
	entorno = ejemplo(nombre)
	catalogo = catalogo_real()
	plantillas = plantillas_de(nombre, entorno, catalogo)
	assert len({p["id"] for p in plantillas}) == len(plantillas) >= 3
	for datos in plantillas:
		avisos = validar_actividad(datos, entorno, catalogo)
		assert not [a for a in avisos if a.es_error], (datos["id"], [str(a) for a in avisos])
		assert datos["descripcion"] and normalizar(datos) == datos
	tipos = {p["tipo"] for p in plantillas}
	if nombre == "vivienda-de-ejemplo":
		assert tipos >= {"busqueda", "pistas", "perimetro"}
		infantil, adulta = plantillas[0], plantillas[1]
		assert infantil["estilo"] == "infantil" and adulta["estilo"] == "adulto" and adulta["nombre"] == "Prepara la visita"
		assert [p["nombre"] for p in adulta["premios"]] == ["las llaves", "el abrigo", "el paraguas"]
	elif nombre == "centro-de-dos-plantas":
		assert tipos >= {"sacar_tesoros", "examen_rutas", "examen_salida"}
		tesoros = next(p for p in plantillas if p["tipo"] == "sacar_tesoros")
		assert len(tesoros["premios"]) == 5 and len({p["planta"] for p in tesoros["premios"]}) == 2
	else:
		assert tipos >= {"recadero", "cruce"}
	assert plantillas_de("no-es-un-ejemplo", entorno) == []
	# También sin catálogo (los premios quedan sueltos) siguen siendo válidas.
	sin_muebles = ejemplo(nombre, False)
	for datos in plantillas_de(nombre, sin_muebles):
		assert not [a for a in validar_actividad(datos, sin_muebles) if a.es_error], datos["id"]


def test_generar_ejemplos_guarda_las_actividades_en_el_paquete(tmp_path):
	"""``tools/generar_ejemplos.py`` escribe los .elab con sus actividades, y se leen de vuelta tal cual."""
	especificacion = importlib.util.spec_from_file_location("generar_ejemplos", RAIZ / "tools" / "generar_ejemplos.py")
	modulo = importlib.util.module_from_spec(especificacion)
	especificacion.loader.exec_module(modulo)
	assert modulo.generar(tmp_path, amueblar=False) == 0
	for nombre in ("vivienda-de-ejemplo", "centro-de-dos-plantas", "barrio-de-ejemplo"):
		paquete = cargar_paquete(tmp_path / f"{nombre}.elab")
		esperadas = plantillas_de(nombre, paquete.entorno)
		assert [a["id"] for a in paquete.actividades] == sorted(a["id"] for a in esperadas)
		for datos in paquete.actividades:
			assert not [a for a in validar_actividad(datos, paquete.entorno) if a.es_error], datos["id"]
			assert paquete.actividad(datos["id"]) == datos
	# Una de ellas se juega entera desde el paquete recién leído.
	paquete = cargar_paquete(tmp_path / "vivienda-de-ejemplo.elab")
	datos = paquete.actividad("prepara-la-visita")
	jugador = Jugador(paquete.entorno, datos)
	for premio in datos["premios"]:
		jugador.ir((premio["planta"], premio["x"], premio["y"]), cerca=0.3)
	assert jugador.fin["completada"] is True


def test_los_ejemplos_distribuidos_traen_sus_actividades():
	"""Los .elab de ``data/ejemplos`` (los que se distribuyen) llevan las actividades de ejemplo y son válidas con el catálogo real."""
	carpeta = RAIZ / "data" / "ejemplos"
	for nombre, minimo in (("vivienda-de-ejemplo", 5), ("centro-de-dos-plantas", 6), ("barrio-de-ejemplo", 3)):
		paquete = cargar_paquete(carpeta / f"{nombre}.elab")
		assert len(paquete.actividades) >= minimo, nombre
		assert any(planta.objetos for planta in paquete.entorno.plantas), f"{nombre}: debería estar amueblado"
		for datos in paquete.actividades:
			avisos = validar_actividad(datos, paquete.entorno, catalogo_real())
			assert not [a for a in avisos if a.es_error], (nombre, datos["id"], [str(a) for a in avisos])
	vivienda_distribuida = cargar_paquete(carpeta / "vivienda-de-ejemplo.elab")
	infantil = vivienda_distribuida.actividad("busqueda-del-tesoro")
	assert infantil["estilo"] == "infantil" and sum(1 for p in infantil["premios"] if p["dentro_de"]) >= 3


def test_guardar_y_cargar_una_actividad_en_un_paquete(tmp_path: Path):
	entorno = casa_vacia()
	datos = nueva_actividad("busqueda", entorno, cantidad=3, id="mi-busqueda")
	ruta = tmp_path / "casa.elab"
	guardar_paquete(ruta, entorno, [datos])
	leida = cargar_paquete(ruta).actividad("mi-busqueda")
	assert leida == datos and normalizar(leida) == datos
