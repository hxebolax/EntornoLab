"""Pruebas de proceso real: el Estudio lanza el reproductor DE VERDAD como proceso hijo.

Nada de dobles: ``app.core.procesos.lanzar_reproductor`` arranca
``python main.py --jugar ...`` con los mismos argumentos que usan «Probar
ahora», «Empezar sesión», «Recorrer el entorno» y «Colocar recorriendo». El
hijo hereda el entorno de la prueba:

- ``APP_DATA_DIR``: la carpeta ``data`` temporal de la prueba (sus registros,
  su configuración y sus sesiones quedan ahí);
- ``APP_SIN_VENTANA=1``: sin ventana ni sonido (SDL «dummy», motor nulo y voz
  que solo apunta);
- ``APP_GUION`` y ``APP_GUION_INFORME``: los pasos que da el «alumno» y dónde
  deja el informe con lo dicho y el estado final (``app/reproductor/guion.py``).

El Estudio usa la sala real (``GestorSala`` en 127.0.0.1, puerto libre) y
comprueba lo que llega; el reproductor comprueba con su guion que las órdenes
le han llegado (pausa, mensaje, recolocar). Al final ningún proceso queda vivo.
"""

from __future__ import annotations

import json
import os
import signal
import sys
import time
from pathlib import Path
from typing import Any

import pytest

from app.core import procesos
from app.dominio.formato import cargar_paquete, guardar_paquete
from app.reproductor import guion as modo_guion
from app.seguimiento import grabadora, informes, sesiones
from app.seguimiento.base import abrir_base
from app.supervision.cliente import ClienteSupervision
from app.ui.contexto import ContextoEstudio
from app.ui.recorrido import ErrorRecorrido, Respuesta, SesionRecorrido
from app.ui.seguimiento import presentador_actividades as pres
from app.ui.seguimiento.sala import PROCESO_TERMINADO, GestorSala
from app.ui.seguimiento.servicio import ServicioSeguimiento, cerrar_servicio, poner_servicio
from tests.conftest import RAIZ
from tests.test_core_procesos import _pid_vivo

VIVIENDA = RAIZ / "data" / "ejemplos" / "vivienda-de-ejemplo.elab"
# Lo que tarda como mucho un reproductor en arrancar y conectarse (importar pygame, cargar dos mil objetos...).
ARRANQUE = 90.0


# ── Utilidades ───────────────────────────────────────────────────────────────


def hasta(condicion, plazo: float = ARRANQUE, sondear=None) -> bool:
	"""Espera a que se cumpla la condición, sondeando la sala si se pide (como el temporizador de una ventana)."""
	limite = time.monotonic() + plazo
	while time.monotonic() < limite:
		if sondear is not None:
			sondear()
		if condicion():
			return True
		time.sleep(0.02)
	if sondear is not None:
		sondear()
	return bool(condicion())


def alumno(gestor: GestorSala, ident: str) -> dict[str, Any]:
	"""La ficha de un alumno en la foto de la sala (vacía si no está)."""
	return next((ficha for ficha in gestor.foto()["alumnos"] if ficha["id"] == ident), {})


def poner_guion(monkeypatch: pytest.MonkeyPatch, carpeta: Path, nombre: str, pasos: list[dict[str, Any]], **extra: Any) -> Path:
	"""Escribe el guion y lo deja en el entorno para el próximo reproductor que se lance. Devuelve la ruta del informe."""
	carpeta.mkdir(parents=True, exist_ok=True)
	ruta = carpeta / f"{nombre}.json"
	ruta.write_text(json.dumps({"pasos": pasos, **extra}, ensure_ascii=False), encoding="utf-8")
	informe = carpeta / f"{nombre}.informe.json"
	monkeypatch.setenv(modo_guion.VARIABLE_SIN_VENTANA, "1")
	monkeypatch.setenv(modo_guion.VARIABLE_GUION, str(ruta))
	monkeypatch.setenv(modo_guion.VARIABLE_INFORME, str(informe))
	return informe


def leer_informe(ruta: Path) -> dict[str, Any]:
	assert ruta.is_file(), "el reproductor no ha dejado su informe"
	return json.loads(ruta.read_text(encoding="utf-8"))


def lo_dicho(informe: dict[str, Any]) -> str:
	return " | ".join(linea["texto"] for linea in informe["dicho"])


def paquete_con_actividad(carpeta: Path, en_el_inicio: bool) -> tuple[Path, tuple[str, float, float]]:
	"""La vivienda de ejemplo con una búsqueda corta de un solo premio (en el inicio o lejos de él)."""
	from tests.test_reproductor_comun import puntos_para_premios

	original = cargar_paquete(VIVIENDA)
	inicio = original.entorno.inicio
	punto = (inicio.planta, inicio.x, inicio.y) if en_el_inicio else puntos_para_premios(original, 1)[0]
	actividad = {
		"formato": 1,
		"id": "corta",
		"nombre": "Actividad corta",
		"tipo": "busqueda",
		"modo": "juego",
		"premios": [{"id": "p1", "nombre": "la llave", "planta": punto[0], "x": punto[1], "y": punto[2], "visibilidad": "lejos"}],
	}
	carpeta.mkdir(parents=True, exist_ok=True)
	ruta = carpeta / "corta.elab"
	guardar_paquete(ruta, original.entorno, [actividad], dict(original.recursos))
	return ruta, punto


class Estudio:
	"""Lo mínimo del Estudio sin ventana: contexto real, servicio del seguimiento con su sala y sucesos recogidos."""

	def __init__(self, carpeta: Path, catalogo: Any = None) -> None:
		self.contexto = ContextoEstudio(catalogo=catalogo, lanzador=procesos.lanzar_reproductor)
		self.servicio = ServicioSeguimiento(self.contexto, sala=GestorSala(None, carpeta_config=carpeta / "config_sala"))
		poner_servicio(self.contexto, self.servicio)
		self.sala = self.servicio.sala
		self.sucesos: list[dict[str, Any]] = []
		self.sala.escuchar(self.sucesos.append)

	def sondear(self) -> None:
		self.sala.sondear()

	def de_tipo(self, tipo: str) -> list[dict[str, Any]]:
		return [suceso for suceso in self.sucesos if suceso["tipo"] == tipo]

	def cerrar(self) -> None:
		cerrar_servicio(self.contexto)


@pytest.fixture(autouse=True)
def _sin_huerfanos():
	"""Pase lo que pase, al terminar no queda ningún reproductor vivo."""
	antes = {proceso.pid for proceso in procesos.procesos_vivos()}
	yield
	vivos = [proceso for proceso in procesos.procesos_vivos() if proceso.pid not in antes]
	procesos.terminar_todos(espera=5.0)
	assert not vivos, f"la prueba dejó reproductores vivos: {vivos}"


@pytest.fixture
def estudio(tmp_path):
	instancia = Estudio(tmp_path)
	yield instancia
	instancia.cerrar()


# ── GestorSala.vigilar con dobles (sin procesos) ─────────────────────────────


class ProcesoDoble:
	"""Lo que ``vigilar`` usa de un ``Proceso``."""

	def __init__(self, pid: int) -> None:
		self.pid = pid
		self.codigo: int | None = None
		self.terminado_por_el_estudio = False

	def vivo(self) -> bool:
		return self.codigo is None


def test_vigilar_dice_cuando_termina_y_si_era_esperado(tmp_path):
	gestor = GestorSala(None, carpeta_config=tmp_path)
	recibidos: list[dict[str, Any]] = []
	gestor.escuchar(recibidos.append)
	muere, cerrado, normal, recorrido, esperado = (ProcesoDoble(pid) for pid in (1, 2, 3, 4, 5))
	gestor.vigilar(muere, "Ana")
	gestor.vigilar(cerrado, "Eva")
	gestor.vigilar(normal, "Sol")
	gestor.vigilar(recorrido, cero_es_normal=True)
	gestor.vigilar(esperado)
	gestor.vigilar(muere, "Ana")  # vigilar dos veces el mismo no lo duplica
	gestor.vigilar(None)
	assert gestor.sondear() == [] and len(gestor.vigilados()) == 5
	muere.codigo = 1
	cerrado.codigo, cerrado.terminado_por_el_estudio = 1, True
	normal.codigo = 0  # sale con 0 pero sin «fin»: inesperado
	recorrido.codigo = 0
	gestor.cierre_esperado(esperado)
	esperado.codigo = 0
	sucesos = gestor.sondear()
	assert recibidos == sucesos and gestor.vigilados() == []
	por_pid = {suceso["datos"]["pid"]: suceso for suceso in sucesos}
	assert {pid: suceso["datos"]["inesperado"] for pid, suceso in por_pid.items()} == {1: True, 2: False, 3: True, 4: False, 5: False}
	assert (
		por_pid[1]["tipo"] == PROCESO_TERMINADO
		and por_pid[1]["alumno"] == por_pid[1]["alias"] == "Ana"
		and por_pid[1]["datos"]["codigo"] == 1
	)
	assert isinstance(por_pid[1]["hora"], float)
	assert gestor.sondear() == [], "cada final se avisa una sola vez"


def test_vigilar_sale_con_cero_tras_el_fin_no_es_inesperado(tmp_path):
	gestor = GestorSala(None, carpeta_config=tmp_path)
	gestor.asegurar_local()
	try:
		proceso = ProcesoDoble(7)
		gestor.vigilar(proceso, "Luna")
		cliente = ClienteSupervision("127.0.0.1", gestor.sala.puerto_local, gestor.sala.codigo, "Luna", carpeta_config=tmp_path / "cliente")
		cliente.iniciar()
		try:
			assert hasta(lambda: cliente.conectado, 10)
			cliente.fin(True, {"estrellas": 1})
			sucesos: list[dict[str, Any]] = []
			assert hasta(lambda: any(s["tipo"] == "fin" for s in sucesos), 10, lambda: sucesos.extend(gestor.sondear()))
		finally:
			cliente.detener()
		proceso.codigo = 0
		final = [suceso for suceso in gestor.sondear() if suceso["tipo"] == PROCESO_TERMINADO]
		assert final and final[0]["datos"]["inesperado"] is False
	finally:
		gestor.cerrar()


# ── El guion, sin procesos ───────────────────────────────────────────────────


def test_guion_valida_pasos_y_condiciones(tmp_path):
	guion = modo_guion.leer_guion(
		{"plazo": 5, "pasos": [{"hasta": "conectado"}, {"accion": "avanzar", "fotogramas": 3}, {"tecla": "F4"}, {"salir": True}]}
	)
	assert guion.plazo == 5 and [modo_guion.clase_de(paso) for paso in guion.pasos] == ["hasta", "accion", "tecla", "salir"]
	assert modo_guion.leer_guion([{"nota": "una lista vale como pasos"}]).pasos
	malos = [
		{"pasos": "no"},
		{"pasos": [{"accion": "a", "tecla": "F4"}]},
		{"pasos": [{"hasta": "llover"}]},
		{"pasos": [{"comprobar": "dicho"}]},
		{"pasos": [{"tecla": "no_es_una_tecla"}]},
		{"pasos": [{"fotogramas": 0}]},
		{"motor": "gramofono", "pasos": []},
		{"al_terminar": "dormir", "pasos": []},
	]
	for datos in malos:
		with pytest.raises(modo_guion.ErrorGuion):
			modo_guion.leer_guion(datos)
	roto = tmp_path / "roto.json"
	roto.write_text("{no es json", encoding="utf-8")
	with pytest.raises(modo_guion.ErrorGuion, match="JSON"):
		modo_guion.cargar_guion(roto)


@pytest.mark.lento
def test_guion_no_valido_sale_con_2_y_lo_explica(tmp_path, data_temporal, monkeypatch):
	"""Un guion mal escrito no arranca nada: código 2 y el motivo en el informe."""
	informe = poner_guion(monkeypatch, tmp_path / "guiones", "malo", [{"hasta": "llover"}])
	proceso = procesos.lanzar_reproductor([])
	assert proceso.esperar(ARRANQUE) == modo_guion.CODIGO_GUION_NO_VALIDO
	datos = leer_informe(informe)
	assert datos["correcto"] is False and "llover" in datos["fallos"][0]


@pytest.mark.lento
def test_guion_que_falla_sale_con_4_y_motor_en_memoria(tmp_path, data_temporal, monkeypatch):
	"""Una comprobación que no se cumple da el código 4; el motor pedido se abre en memoria y el informe lo dice."""
	informe = poner_guion(
		monkeypatch,
		tmp_path / "guiones",
		"falla",
		[{"hasta": "partida", "plazo": 60}, {"comprobar": "dicho", "texto": "Esto no lo dice nadie"}, {"comprobar": "sin_fallos"}],
		motor="clasico",
	)
	monkeypatch.delenv("APP_SIN_SONIDO", raising=False)
	proceso = procesos.lanzar_reproductor([str(VIVIENDA), "--actividad", "busqueda-del-tesoro", "--alumno", "Luna"])
	assert proceso.esperar(ARRANQUE) == modo_guion.CODIGO_FALLO
	datos = leer_informe(informe)
	assert datos["codigo"] == modo_guion.CODIGO_FALLO and len(datos["fallos"]) == 1 and "Esto no lo dice nadie" in datos["fallos"][0]
	assert [paso["correcto"] for paso in datos["pasos"]] == [True, False], "se para en la primera comprobación fallida"
	assert datos["sonido"]["motor"] == "clasico" and datos["sonido"]["memoria"] is True
	assert datos["estado_final"]["partida"]["entorno"] == "Vivienda de ejemplo"
	assert datos["complementos"]["faltan"] == [] and datos["complementos"]["objetos"] > 0
	assert any(paquete["defecto"] for paquete in datos["paquetes_sonido"])
	assert datos["estado_final"]["alias"] == "Luna" and "tesoros" in lo_dicho(datos)


# ── Probar ahora y Empezar sesión ────────────────────────────────────────────


@pytest.mark.lento
def test_probar_ahora_ordenes_reales_sesion_e_informe(estudio, tmp_path, data_temporal, monkeypatch):
	"""«Probar ahora»: pausa, reanudar, mensaje y recolocar llegan al reproductor real; termina la actividad,
	escribe su sesión y el Estudio la incorpora y saca el informe."""
	ruta, premio = paquete_con_actividad(tmp_path / "entornos", en_el_inicio=False)
	informe = poner_guion(
		monkeypatch,
		tmp_path / "guiones",
		"probar",
		[
			{"hasta": "conectado", "plazo": ARRANQUE},
			{"hasta": "dicho", "texto": "Tu profesor ha puesto el juego en pausa", "plazo": 60},
			{"comprobar": "pausada"},
			{"hasta": "dicho", "texto": "Tu profesor ha reanudado el juego", "plazo": 60},
			{"hasta": "dicho", "texto": "Sigue por la pared", "plazo": 60},
			{"hasta": "fin", "plazo": 60},
			{"comprobar": "completada"},
			{"comprobar": "dicho", "texto": "Tu profesor te ha llevado a otro sitio"},
			{"comprobar": "sin_fallos"},
			{"salir": True},
		],
	)
	sala = estudio.sala
	sala.asegurar_local()
	# Lo mismo que hace el botón «Probar ahora» de la pestaña Actividades.
	proceso = estudio.servicio.lanzar(pres.argumentos_probar(ruta, "corta", conexion=sala.argumentos_conexion()))
	sala.vigilar(proceso, "invitado")
	assert proceso.atado

	assert hasta(
		lambda: alumno(sala, "invitado").get("conectado") and alumno(sala, "invitado").get("x") is not None, sondear=estudio.sondear
	), "el reproductor real no se conectó ni envió su estado"
	assert alumno(sala, "invitado")["actividad"] == "Actividad corta"
	assert sala.pedir("invitado", "pausa")
	assert hasta(lambda: alumno(sala, "invitado").get("pausado") is True, 30, estudio.sondear), "el estado no dice que está en pausa"
	assert sala.pedir("invitado", "reanudar")
	assert hasta(lambda: alumno(sala, "invitado").get("pausado") is False, 30, estudio.sondear)
	assert sala.pedir("invitado", "mensaje", texto="Sigue por la pared")
	assert hasta(
		lambda: any(voz["texto"] == "Sigue por la pared" for voz in alumno(sala, "invitado").get("voces", [])), 30, estudio.sondear
	), "la voz del reproductor no llegó al Estudio"
	# Recolocar encima del premio: la actividad termina sola, completada.
	assert sala.pedir("invitado", "recolocar", planta=premio[0], x=premio[1], y=premio[2], rumbo=0.0)
	assert hasta(lambda: estudio.de_tipo("fin"), 60, estudio.sondear), "no llegó el fin de la actividad"
	assert estudio.de_tipo("fin")[0]["datos"]["completada"] is True

	assert proceso.esperar(60) == 0
	assert hasta(lambda: estudio.de_tipo(PROCESO_TERMINADO), 10, estudio.sondear)
	terminado = estudio.de_tipo(PROCESO_TERMINADO)[0]
	assert terminado["alias"] == "invitado" and terminado["datos"]["codigo"] == 0 and terminado["datos"]["inesperado"] is False
	assert alumno(sala, "invitado")["terminado"] is True

	datos = leer_informe(informe)
	assert datos["correcto"] is True, datos["fallos"]
	assert ("Sigue por la pared", "profesional") in [(linea["texto"], linea["canal"]) for linea in datos["dicho"]]
	assert datos["estado_final"]["partida"]["completada"] is True
	assert datos["sonido"]["motor"] == "nulo" and datos["sesiones"]

	# El Estudio incorpora la sesión y saca su informe.
	base = abrir_base(tmp_path / "seguimiento.db")
	try:
		resultado = grabadora.incorporar_sesiones(None, base)
		assert resultado.nuevas == 1 and not resultado.erroneas
		guardada = sesiones.listar(base)[0]
		assert guardada["completada"] is True and guardada["actividad_id"] == "corta"
		texto = informes.a_texto(informes.informe_sesion(sesiones.obtener(base, guardada["id"]), alias="invitado"))
		assert "Vivienda de ejemplo" in texto
	finally:
		base.cerrar()


@pytest.mark.lento
def test_empezar_sesion_terminada_en_menos_de_un_segundo_sigue_terminada(estudio, tmp_path, data_temporal, monkeypatch):
	"""«Empezar sesión» y la orden «terminar» con menos de un segundo de juego: la sala la deja terminada.

	Antes, el cliente reenviaba el último estado tras el ``fin`` y la sala,
	al ver un tiempo activo menor de un segundo, creía que empezaba otra
	sesión y la volvía a marcar como no terminada.
	"""
	ruta, _premio = paquete_con_actividad(tmp_path / "entornos", en_el_inicio=False)
	informe = poner_guion(
		monkeypatch,
		tmp_path / "guiones",
		"empezar",
		[
			{"nota": "La pausa para el reloj de la actividad: el tiempo activo se queda por debajo de un segundo."},
			{"accion": "pausa"},
			{"comprobar": "pausada"},
			{"hasta": "conectado", "plazo": ARRANQUE},
			{"hasta": "fin", "plazo": 60},
			{"comprobar": "dicho", "texto": "Tu profesor ha terminado la actividad"},
			{"nota": "Tiempo de sobra para que se reenviara el estado (cinco veces por segundo)."},
			{"segundos": 1.5},
			{"salir": True},
		],
	)
	sala = estudio.sala
	sala.asegurar_local()
	# Lo mismo que el diálogo «Empezar sesión en este ordenador» de la ventana de supervisión.
	proceso = estudio.servicio.lanzar([str(ruta), "--actividad", "corta", "--alumno", "Sol", *sala.argumentos_conexion()])
	sala.vigilar(proceso, "Sol")
	assert hasta(lambda: alumno(sala, "Sol").get("x") is not None, sondear=estudio.sondear)
	assert alumno(sala, "Sol")["tiempo_activo"] < 1.0 and alumno(sala, "Sol")["pausado"] is True
	assert sala.pedir("Sol", "terminar")
	assert hasta(lambda: alumno(sala, "Sol").get("terminado") is True, 60, estudio.sondear)
	assert proceso.esperar(60) == 0
	assert hasta(lambda: estudio.de_tipo(PROCESO_TERMINADO), 10, estudio.sondear)
	assert alumno(sala, "Sol")["terminado"] is True, "el estado reenviado tras el fin volvió a abrir la sesión"
	assert alumno(sala, "Sol")["resultado"].get("terminada_por_profesor") is True
	assert estudio.de_tipo(PROCESO_TERMINADO)[0]["datos"]["inesperado"] is False
	datos = leer_informe(informe)
	assert datos["correcto"] is True, datos["fallos"]
	assert len(list((data_temporal / "sessions").glob("*.json.gz"))) == 1


# ── Recorrer el entorno y Colocar recorriendo ────────────────────────────────


@pytest.fixture
def catalogo_real():
	from app.reproductor import entornos

	return entornos.cargar_catalogo()


@pytest.mark.lento
def test_recorrer_el_entorno_coloca_desde_el_catalogo_del_reproductor(tmp_path, data_temporal, monkeypatch, catalogo_real):
	"""«Recorrer el entorno»: el profesional busca el objeto en el catálogo DEL REPRODUCTOR y el Estudio lo coloca.

	Después, con el mismo reproductor, «Marcar este punto» lo atiende quien
	reutiliza el recorrido (lo que hace «Colocar recorriendo» del editor de
	premios si ya hay uno abierto), y un segundo recorrido no se abre.
	"""
	estudio = Estudio(tmp_path, catalogo_real)
	try:
		contexto = estudio.contexto
		contexto.abrir_documento(cargar_paquete(VIVIENDA).entorno)
		ruta = tmp_path / "entornos" / "vivienda.elab"
		assert contexto.guardar(ruta)
		objetos_antes = sum(len(planta.objetos) for planta in contexto.entorno.plantas)
		informe = poner_guion(
			monkeypatch,
			tmp_path / "guiones",
			"recorrer",
			[
				{"hasta": "conectado", "plazo": ARRANQUE},
				{"tecla": "F4"},
				{"elegir": "Colocar un objeto aquí"},
				{"elegir": "Buscar por nombre"},
				{"escribir": "paraguero", "intro": True},
				{"elegir": "Paragüero,"},
				{"hasta": "dicho", "texto": "Paragüero: colocado.", "plazo": 60},
				{"hasta": "dicho", "texto": "Entorno actualizado.", "plazo": 30},
				{"tecla": "F4"},
				{"elegir": "Marcar este punto"},
				{"tecla": "RETURN", "texto": "\r"},
				{"hasta": "dicho", "texto": "Premio colocado aquí", "plazo": 60},
				{"comprobar": "sin_fallos"},
				{"salir": True},
			],
		)
		sesion = SesionRecorrido(contexto)
		assert sesion.gestor is estudio.sala, "el recorrido usa la sala única del servicio"
		sesion.iniciar()
		assert estudio.sala.recorrido is sesion and sesion.proceso.atado
		with pytest.raises(ErrorRecorrido, match="Ya hay un reproductor"):
			SesionRecorrido(contexto).iniciar()
		frases: list[str] = []
		capturados: list[dict[str, Any]] = []

		def capturar(_alumno: str, datos: dict[str, Any]) -> Respuesta | None:
			if datos.get("accion") != "marcar_punto":
				return None
			capturados.append(datos)
			return Respuesta(True, "Premio colocado aquí: en el salón.")

		def objeto_colocado() -> bool:
			frases.extend(sesion.atender())
			return sum(len(planta.objetos) for planta in contexto.entorno.plantas) > objetos_antes

		assert hasta(objeto_colocado), f"el Estudio no colocó el objeto pedido desde el reproductor: {frases}"
		# Como el editor de premios cuando reutiliza el recorrido abierto.
		sesion.al_pedir = capturar
		nuevo = contexto.seleccion
		assert contexto.entorno.elemento(nuevo).tipo == "hogar/paraguero"
		assert any(objeto.tipo == "hogar/paraguero" for planta in cargar_paquete(ruta).entorno.plantas for objeto in planta.objetos)
		assert hasta(lambda: (frases.extend(sesion.atender()), not sesion.activa)[1]), "el recorrido no terminó al cerrarse el reproductor"
		assert capturados and capturados[0]["planta"]
		assert "Recorrido terminado." in frases and not any("inesperada" in frase for frase in frases)
		assert estudio.sala.recorrido is None and not estudio.sala.activa, "la sala se abrió para el recorrido y se cierra con él"
		datos = leer_informe(informe)
		assert datos["correcto"] is True, datos["fallos"]
		assert datos["estado_final"]["partida"]["recorrido"] is True
	finally:
		estudio.cerrar()


@pytest.mark.lento
def test_colocar_recorriendo_del_editor_de_premios(tmp_path, data_temporal, monkeypatch, app_wx, marco, dialogo_modal):
	"""«Colocar recorriendo» del editor de premios con el reproductor real: la sala del servicio, el premio donde se dice «aquí»."""
	import wx

	from app.ui.seguimiento import editor_premios
	from app.ui.seguimiento.contexto import ContextoDePrueba
	from app.ui.seguimiento.textos import Letras
	from tests.conftest import procesar_eventos

	from app.ui import recorrido as recorrido_ui

	# El reproductor tarda algo más de un segundo en cerrarse con orden (y escribir su informe): aquí se le espera.
	monkeypatch.setattr(recorrido_ui, "ESPERA_TERMINAR", 30.0)
	original = cargar_paquete(VIVIENDA)
	contexto = ContextoDePrueba(entorno=original.entorno, ruta_paquete=tmp_path / "entornos" / "vivienda.elab")
	contexto.ruta_paquete.parent.mkdir(parents=True)
	contexto.lanzar_reproductor = procesos.lanzar_reproductor  # el de verdad, no el doble
	servicio = ServicioSeguimiento(contexto, sala=GestorSala(None, carpeta_config=tmp_path / "config_sala"))
	poner_servicio(contexto, servicio)
	informe = poner_guion(
		monkeypatch,
		tmp_path / "guiones",
		"premio",
		[
			{"hasta": "conectado", "plazo": ARRANQUE},
			{"tecla": "F4"},
			{"elegir": "Marcar este punto"},
			{"tecla": "RETURN", "texto": "\r"},
			{"hasta": "dicho", "texto": "Premio colocado aquí", "plazo": 60},
			{"hasta": "salida", "plazo": 60},
		],
	)
	lanzados: list[Any] = []
	lanzar = servicio.lanzar

	def lanzar_y_apuntar(argumentos):
		proceso = lanzar(argumentos)
		lanzados.append(proceso)
		return proceso

	servicio.lanzar = lanzar_y_apuntar
	try:
		panel = editor_premios.PanelPremios(marco, contexto, servicio, Letras())

		def esperar_aqui(dialogo) -> int:
			assert dialogo.sesion is not None and dialogo.sesion.gestor is servicio.sala
			listo = procesar_eventos(lambda: (dialogo.sondear(), dialogo.aceptado or dialogo.posicion is not None)[1], ARRANQUE)
			assert listo, "no llegó el «aquí» del reproductor"
			procesar_eventos(lambda: dialogo.aceptado, 5.0)
			return wx.ID_OK if dialogo.aceptado else wx.ID_CANCEL

		def nombrar(dialogo) -> int:
			dialogo.nombre.SetValue("Tesoro")
			return wx.ID_OK if dialogo.aceptar() else wx.ID_CANCEL

		dialogo_modal.responder(esperar_aqui, nombrar)
		panel.colocar_recorriendo()
		premio = panel.leer()[0]
		assert premio["nombre"] == "Tesoro" and premio["planta"] == original.entorno.inicio.planta
		proceso = lanzados[0]
		assert proceso.orden[2:4] == ["--jugar", "--recorrido"]
		# Al cerrar el diálogo se cierra el recorrido: el reproductor termina por la orden «terminar», sin quedar huérfano.
		assert hasta(lambda: not proceso.vivo(), 30)
		assert not servicio.sala.activa and servicio.sala.recorrido is None
		datos = leer_informe(informe)
		assert datos["correcto"] is True, datos["fallos"]
	finally:
		cerrar_servicio(contexto)


# ── Cierre del Estudio y reproductores que mueren ────────────────────────────


@pytest.mark.lento
def test_el_estudio_detecta_que_el_reproductor_ha_muerto(estudio, tmp_path, data_temporal, monkeypatch):
	monkeypatch.setenv(modo_guion.VARIABLE_SIN_VENTANA, "1")
	sala = estudio.sala
	sala.asegurar_local()
	proceso = estudio.servicio.lanzar([str(VIVIENDA), "--alumno", "Kim", *sala.argumentos_conexion()])
	sala.vigilar(proceso, "Kim")
	assert hasta(lambda: alumno(sala, "Kim").get("conectado"), sondear=estudio.sondear)
	assert estudio.de_tipo(PROCESO_TERMINADO) == []
	# Lo mata alguien de fuera (el Administrador de tareas): ni el Estudio ni el propio reproductor lo esperaban.
	os.kill(proceso.pid, signal.SIGTERM)
	assert hasta(lambda: estudio.de_tipo(PROCESO_TERMINADO), 30, estudio.sondear), "el Estudio no se enteró de que el reproductor murió"
	suceso = estudio.de_tipo(PROCESO_TERMINADO)[0]
	assert suceso["alumno"] == suceso["alias"] == "Kim" and isinstance(suceso["hora"], float)
	assert suceso["datos"]["inesperado"] is True and suceso["datos"]["codigo"] not in (None, 0)
	assert suceso["datos"]["pid"] == proceso.pid
	assert hasta(lambda: not alumno(sala, "Kim").get("conectado"), 30, estudio.sondear)
	# Una vez avisado, no se repite.
	estudio.sucesos.clear()
	estudio.sondear()
	assert estudio.de_tipo(PROCESO_TERMINADO) == []


@pytest.mark.lento
def test_al_cerrar_el_estudio_no_quedan_reproductores(tmp_path, data_temporal, monkeypatch):
	from app.ui.seguimiento import integracion

	monkeypatch.setenv(modo_guion.VARIABLE_SIN_VENTANA, "1")
	estudio = Estudio(tmp_path)
	sala = estudio.sala
	sala.asegurar_local()
	conectado = estudio.servicio.lanzar([str(VIVIENDA), "--alumno", "Ana", *sala.argumentos_conexion()])
	suelto = estudio.servicio.lanzar(["--alumno", "Eva"])
	sala.vigilar(conectado, "Ana")
	pids = [conectado.pid, suelto.pid]
	assert hasta(lambda: alumno(sala, "Ana").get("conectado"), sondear=estudio.sondear)
	assert all(_pid_vivo(pid) for pid in pids)
	integracion.al_cerrar(estudio.contexto)
	assert hasta(lambda: not any(_pid_vivo(pid) for pid in pids), 30), "quedaron reproductores huérfanos al cerrar el Estudio"
	assert not sala.activa
	assert procesos.procesos_vivos() == []


@pytest.mark.lento
@pytest.mark.skipif(sys.platform != "win32", reason="Los Job Objects son de Windows")
def test_si_el_estudio_muere_de_golpe_el_reproductor_tambien(tmp_path, data_temporal):
	"""Un Estudio que muere sin cerrar nada (sin atexit) no deja el reproductor sin ventana sonando."""
	import subprocess

	padre = tmp_path / "estudio.py"
	padre.write_text(
		"import os, sys, time\n"
		f"sys.path.insert(0, {str(RAIZ)!r})\n"
		"os.environ['APP_SIN_VENTANA'] = '1'\n"
		"from app.core import procesos\n"
		"hijo = procesos.lanzar_reproductor(['--alumno', 'Leo'])\n"
		"print(hijo.pid, hijo.atado, flush=True)\n"
		"time.sleep(1.0)\n"
		"os._exit(0)\n",
		encoding="utf-8",
	)
	resultado = subprocess.run([sys.executable, str(padre)], capture_output=True, text=True, timeout=120, check=False)
	assert resultado.returncode == 0, resultado.stderr
	pid, atado = resultado.stdout.split()
	assert atado == "True"
	assert hasta(lambda: not _pid_vivo(int(pid)), 30), "el reproductor sobrevivió al Estudio"
