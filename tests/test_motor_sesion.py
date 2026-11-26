"""Pruebas de la sesión: ajustes, tiempo y pausa, semilla, ganchos de actividad, baliza, final y rendimiento."""

from __future__ import annotations

import logging
import time

import pytest

from app.dominio import edicion as ed
from app.dominio import ejemplos
from app.dominio.modelo import Abertura, Entorno, Posicion
from app.motor import eventos as ev
from app.motor.sesion import AjustesJuego, Sesion, regla_ayuda
from tests.test_dominio_comun import catalogo_de_prueba
from tests.test_motor_comun import Robot, poner_objeto, registros, sonidos, texto, voces

# ── Ajustes ──────────────────────────────────────────────────────────────────


def test_ajustes_de_serie_y_ida_y_vuelta():
	ajustes = AjustesJuego()
	assert (ajustes.modo_movimiento, ajustes.paso_m, ajustes.giro_grados, ajustes.detalle) == ("pasos", 0.6, 45.0, 2)
	assert (ajustes.formato_direccion, ajustes.unidad, ajustes.estilo, ajustes.radio_m) == ("reloj", "metros", "adulto", 0.25)
	# Una sola fuente de verdad: los valores de serie del motor son los de las preferencias que ve el usuario.
	from app.core.configuracion import VALORES_POR_DEFECTO

	juego = VALORES_POR_DEFECTO["juego"]
	for clave in ("modo_movimiento", "paso_m", "giro_grados", "velocidad_ms", "formato_direccion", "unidad", "estilo"):
		assert getattr(ajustes, clave) == juego[clave], clave
	assert ajustes.detalle == VALORES_POR_DEFECTO["voz"]["detalle"]
	cambiados = AjustesJuego(
		modo_movimiento="continuo", paso_m=0.55, unidad="pasos", detalle=3, ayudas={"sonda": {"permitida": True, "limite": 5}}
	)
	datos = cambiados.a_dict()
	assert datos["ayudas"] == {"sonda": {"permitida": True, "limite": 5}}
	assert AjustesJuego.de_dict(datos) == cambiados


def test_el_paso_de_serie_es_el_mismo_en_lenguaje_e_informes(monkeypatch):
	"""El lenguaje del motor y la narración del recorrido usan el paso de las preferencias, no uno propio."""
	import inspect

	from app.core.configuracion import VALORES_POR_DEFECTO
	from app.motor.lenguaje import Lenguaje
	from app.seguimiento import informes
	from app.ui.seguimiento import presentador_registros as pres

	paso = VALORES_POR_DEFECTO["juego"]["paso_m"]
	assert Lenguaje().paso_m == paso == AjustesJuego().paso_m
	assert inspect.signature(informes.describir_recorrido).parameters["paso_m"].default == paso
	# Un alumno sin paso en su ficha (o sin ficha) se narra con el paso de serie.
	pedidos: list[float] = []
	monkeypatch.setattr(pres.sesiones, "traza", lambda base, id_sesion: {})
	monkeypatch.setattr(pres, "Fichas", lambda base: type("SinFichas", (), {"obtener": lambda self, id_alumno: None})())
	monkeypatch.setattr(pres, "espacios_de", lambda contexto, sesion: [])
	monkeypatch.setattr(pres.informes, "describir_recorrido", lambda traza, **opciones: pedidos.append(opciones["paso_m"]) or [])
	pres.pasos_del_recorrido(None, {"id": "s1", "alumno_id": 1}, unidad="pasos")
	assert pedidos == [paso]


def test_el_motor_no_carga_wx_ni_pygame():
	"""Tomar los valores de serie de app.core.configuracion no arrastra la interfaz al motor."""
	import subprocess
	import sys
	from pathlib import Path

	codigo = "import sys, app.motor.sesion, app.motor.lenguaje; print(sorted(m for m in ('wx', 'pygame') if m in sys.modules))"
	raiz = Path(__file__).resolve().parent.parent
	salida = subprocess.run([sys.executable, "-c", codigo], cwd=raiz, capture_output=True, text=True, timeout=120, check=True)
	assert salida.stdout.strip().splitlines()[-1] == "[]", salida.stdout + salida.stderr


def test_ajustes_tolerantes_y_en_rango():
	ajustes = AjustesJuego.de_dict(
		{
			"modo_movimiento": "volando",
			"paso_m": 9,
			"velocidad_ms": "rápido",
			"giro_grados": -5,
			"detalle": 7,
			"estilo": "infantil",
			"clave_desconocida": 1,
			"ayudas": {"eco": False, "sonda": 3, "pista": {"permitida": True, "limite": "muchas"}, "brujula": True},
		}
	)
	assert ajustes.modo_movimiento == "pasos"
	assert ajustes.paso_m == 1.5 and ajustes.velocidad_ms == 1.2 and ajustes.giro_grados == 0.0
	assert ajustes.detalle == 3 and ajustes.estilo == "infantil"
	assert ajustes.ayudas == {
		"eco": {"permitida": False, "limite": None},
		"sonda": {"permitida": True, "limite": 3},
		"pista": {"permitida": True, "limite": None},
		"brujula": {"permitida": True, "limite": None},
	}
	assert AjustesJuego.de_dict(None) == AjustesJuego()
	assert regla_ayuda("cualquier cosa") == {"permitida": True, "limite": None}


def test_el_estilo_infantil_cambia_el_tono_de_las_frases():
	entorno = ejemplos.vivienda_ejemplo()
	infantil = Robot(entorno, estilo="infantil")
	assert "¡Sitio nuevo! Entrada." in voces(infantil.eventos)
	infantil.girar_a(0.0)
	nuevos = infantil.pulsar("avanzar") + infantil.pulsar("avanzar") + infantil.pulsar("avanzar")
	assert "¡Pum! Pared." in voces(nuevos)
	adulto = Robot(entorno, estilo="adulto")
	assert "Entrada." in voces(adulto.eventos)


# ── Estado, tiempo y pausa ───────────────────────────────────────────────────


def test_estado_oyente_y_muestra():
	entorno = ejemplos.centro_dos_plantas()
	robot = Robot(entorno, inicio=Posicion("pla-2", 5.0, 7.0, 270.0))
	sesion = robot.sesion
	assert sesion.oyente() == (5.0, 7.0, pytest.approx(3.2 + 1.6), 270.0)
	estado = sesion.estado()
	assert estado["planta"] == "pla-2" and estado["planta_nombre"] == "Planta primera"
	assert estado["espacio_nombre"] == "Pasillo de la planta primera"
	assert estado["descripcion"] == "Estás en Pasillo de la planta primera, Planta primera, mirando al oeste."
	assert estado["modo"] == "andando" and estado["suelo"] == "baldosa"
	assert estado["pausado"] is False and estado["terminado"] is False
	assert estado["tiempo_activo"] == pytest.approx(0.1)
	t, planta, x, y, rumbo = sesion.muestra()
	assert (planta, x, y, rumbo) == ("pla-2", 5.0, 7.0, 270.0) and t == pytest.approx(0.1)
	inicio = registros(robot.eventos, "inicio")[0]
	assert inicio["entorno"] == entorno.id and inicio["semilla"] == 7 and inicio["planta"] == "pla-2"


def test_la_pausa_no_cuenta_como_tiempo_activo_ni_atiende_ordenes():
	robot = Robot(ejemplos.vivienda_ejemplo())
	sesion = robot.sesion
	robot.esperar(1.0)
	activo = sesion.tiempo_activo
	posicion = robot.pos
	sesion.pausar(True)
	sesion.orden("avanzar")
	nuevos = robot.esperar(3.0)
	assert sesion.tiempo_activo == activo
	assert sesion.tiempo_pausa == pytest.approx(3.0)
	assert robot.pos == posicion
	assert registros(nuevos, "pausa")[0]["activa"] is True
	assert sonidos(nuevos) == [] and sesion.fuentes() == []
	assert sesion.estado()["pausado"] is True
	sesion.pausar(False)
	nuevos = robot.pulsar("avanzar")
	assert robot.pos != posicion
	assert registros(nuevos, "pausa")[0] == registros(nuevos, "pausa")[0] | {"activa": False, "tiempo_pausa": 3.0}
	assert sesion.tiempo_activo == pytest.approx(activo + 0.1)
	# Una orden mantenida antes de pausar no sigue andando al volver.
	sesion.orden("avanzar")
	robot.tic(1)
	sesion.pausar(True)
	sesion.pausar(False)
	parado = robot.pos
	robot.esperar(2.0)
	assert robot.pos == parado


def test_un_fotograma_largo_no_da_un_salto():
	robot = Robot(ejemplos.vivienda_ejemplo(), modo_movimiento="continuo", velocidad_ms=1.0, inicio=Posicion("pla-1", 0.5, 4.6, 90.0))
	robot.sesion.orden("avanzar")
	robot.tic(1, dt=30.0)
	assert robot.pos[0] <= 0.5 + 0.26


def test_recolocar_y_volver_al_inicio():
	entorno = ejemplos.centro_dos_plantas()
	robot = Robot(entorno)
	robot.sesion.recolocar(Posicion("pla-2", 16.0, 10.0, 180.0))
	nuevos = robot.tic(2)
	assert robot.espacio == "Sala de informática"
	assert registros(nuevos, "recolocar") and registros(nuevos, "entrada_espacio")[0]["nombre"] == "Sala de informática"
	assert "Sala de informática." in voces(nuevos + robot.esperar(3.0))
	nuevos = robot.pulsar("volver_inicio")
	assert robot.sesion.jugador.planta == "pla-1" and robot.pos == (4.0, 1.5)
	assert "Has vuelto al inicio." in voces(nuevos)
	# Recolocar a una planta que no existe no hace nada.
	robot.sesion.recolocar(Posicion("no-existe", 0.0, 0.0, 0.0))
	assert robot.sesion.jugador.planta == "pla-1"


def test_inicio_en_una_planta_que_no_existe_y_entorno_casi_vacio(caplog):
	entorno = ejemplos.vivienda_ejemplo()
	entorno.inicio = Posicion("fantasma", 0.0, 0.0, 0.0)
	with caplog.at_level(logging.WARNING):
		robot = Robot(entorno)
	assert robot.sesion.jugador.planta == "pla-1" and robot.espacio != ""
	vacio = Entorno(id="vacio", nombre="Vacío")
	sesion = Sesion(vacio, None, AjustesJuego(), semilla=1)
	sesion.orden("avanzar")
	sesion.orden("donde_estoy")
	assert isinstance(sesion.avanzar(0.05), list)
	solo_planta = ed.crear_entorno("Solar")
	planta = ed.crear_planta(solo_planta, "Solar")
	ed.fijar_inicio(solo_planta, planta, 0.0, 0.0, 0.0)
	robot = Robot(solo_planta, paso_m=0.7)
	robot.pulsar("avanzar")
	assert robot.pos == pytest.approx((0.0, 0.7))


# ── Semilla ──────────────────────────────────────────────────────────────────


def _guion(robot: Robot) -> list[str]:
	robot.esperar(3.0)
	for accion in ("girar_derecha", "avanzar", "avanzar", "sonda", "avanzar", "alrededor", "avanzar", "eco", "avanzar", "avanzar"):
		robot.pulsar(accion, 6)
	robot.esperar(5.0)
	return [repr(e) for e in robot.eventos] + [repr(f) for f in robot.sesion.fuentes()]


def test_con_la_misma_semilla_todo_es_identico():
	primero = _guion(Robot(ejemplos.barrio_ejemplo(), semilla=99, trafico=True))
	segundo = _guion(Robot(ejemplos.barrio_ejemplo(), semilla=99, trafico=True))
	assert primero == segundo
	assert len(primero) > 30
	otro = _guion(Robot(ejemplos.barrio_ejemplo(), semilla=100, trafico=True))
	assert otro != primero
	# Sin semilla, la sesión elige una y la guarda para poder repetir la partida.
	sesion = Sesion(ejemplos.vivienda_ejemplo(), None, AjustesJuego())
	assert isinstance(sesion.semilla, int) and sesion.semilla > 0
	assert sesion.resumen()["semilla"] == sesion.semilla


# ── Actividad ────────────────────────────────────────────────────────────────


class ActividadDePrueba:
	"""Una actividad mínima: apunta lo que le llega y devuelve eventos."""

	def __init__(self) -> None:
		self.llamadas: list[tuple] = []

	def al_empezar(self, sesion):
		self.llamadas.append(("al_empezar",))
		sesion.anadir_fuente("premio", "premio/cerca", ("pla-1", 1.0, 4.6), radio=6.0, bus="ayudas")
		return [ev.EvVoz("Encuentra la llave.", canal="juego")]

	def tras_mover(self, sesion):
		self.llamadas.append(("tras_mover", round(sesion.jugador.x, 2)))
		if sesion.distancia_a(("pla-1", 1.0, 4.6)) < 0.5 and sesion.quitar_fuente("premio"):
			sesion.registrar("premio", id="llave", nombre="Llave")
			return [ev.EvSonido("premio/recogido", bus="efectos"), ev.EvVoz("¡La llave!")]
		return None

	def al_interactuar(self, sesion, elemento):
		self.llamadas.append(("al_interactuar", elemento))
		if elemento is None:
			return [ev.EvVoz("Aquí no hay nada escondido.")]
		return []

	def tic(self, sesion, dt):
		self.llamadas.append(("tic", dt))
		if sesion.tiempo_activo > 100.0:
			sesion.terminar({"motivo": "tiempo"})

	def al_pedir(self, sesion, accion):
		self.llamadas.append(("al_pedir", accion))
		return [
			ev.EvVoz(
				"Busca la llave en el pasillo." if accion == "objetivo" else "Está cerca de la entrada.", interrumpir=True, canal="ayuda"
			)
		]

	def resultado(self, sesion):
		return {"estrellas": 2}


def test_ganchos_de_la_actividad():
	actividad = ActividadDePrueba()
	robot = Robot(ejemplos.vivienda_ejemplo(), actividad=actividad)
	sesion = robot.sesion
	assert actividad.llamadas[0] == ("al_empezar",)
	assert "Encuentra la llave." in voces(robot.eventos)
	assert "premio" in {f.id for f in sesion.fuentes()}
	assert voces(robot.pulsar("objetivo")) == ["Busca la llave en el pasillo."]
	assert voces(robot.pulsar("pista")) == ["Está cerca de la entrada."]
	assert ("al_pedir", "objetivo") in actividad.llamadas and ("al_pedir", "pista") in actividad.llamadas
	assert sesion.percepcion.usos == {"objetivo": 1, "pista": 1}
	# Nada que usar delante: el gancho recibe None y su respuesta sustituye al «no hay nada que usar».
	assert voces(robot.pulsar("interactuar")) == ["Aquí no hay nada escondido."]
	# Tres pasos hasta el premio: el gancho de movimiento lo recoge.
	nuevos: list = []
	for _i in range(3):
		nuevos += robot.pulsar("avanzar")
	assert "premio/recogido" in sonidos(nuevos) and "¡La llave!" in voces(nuevos)
	assert registros(nuevos, "premio")[0]["id"] == "llave"
	assert "premio" not in {f.id for f in sesion.fuentes()}
	assert len([c for c in actividad.llamadas if c[0] == "tras_mover"]) >= 3
	assert any(c[0] == "tic" and c[1] == pytest.approx(0.05) for c in actividad.llamadas)
	# Al usar una puerta, el gancho recibe el elemento del modelo.
	robot.ir_a(3.0, 4.6)
	robot.girar_a(0.0)
	robot.pulsar("interactuar")
	elemento = next(c[1] for c in reversed(actividad.llamadas) if c[0] == "al_interactuar")
	assert isinstance(elemento, Abertura) and "Dormitorio" in elemento.nombre
	# Terminar: EvFin con el resumen, lo de la actividad y lo que se pase.
	sesion.terminar({"motivo": "prueba"})
	nuevos = robot.tic(1)
	fin = next(e for e in nuevos if isinstance(e, ev.EvFin))
	assert fin.resultado["estrellas"] == 2 and fin.resultado["motivo"] == "prueba"
	assert fin.resultado["ayudas"] == {"objetivo": 1, "pista": 1}
	assert fin.resultado["pasos"] >= 3 and fin.resultado["distancia_m"] > 2.0
	assert len(fin.resultado["espacios_visitados"]) == 2
	assert sesion.terminado and sesion.resultado == fin.resultado
	# Terminada, no pasa nada más.
	sesion.orden("avanzar")
	assert robot.tic(3) == [] and sesion.fuentes() == []


def test_un_fallo_en_la_actividad_no_para_la_partida(caplog):
	class Rota:
		def tras_mover(self, sesion):
			raise RuntimeError("actividad rota")

	robot = Robot(ejemplos.vivienda_ejemplo(), actividad=Rota())
	with caplog.at_level(logging.ERROR, logger="app.motor.sesion"):
		nuevos = robot.pulsar("avanzar")
	assert any(nombre.startswith("pasos/") for nombre in sonidos(nuevos))
	assert "Fallo en el gancho «tras_mover» de la actividad" in caplog.text


def test_el_gancho_al_registrar_recibe_cada_registro(caplog):
	"""La actividad recibe cada ``EvRegistro`` que sale de la sesión: los del motor, los suyos y los de los eventos que devuelve."""

	class Oyente:
		def __init__(self) -> None:
			self.vistos: list[str] = []
			self.dentro = False

		def al_empezar(self, sesion):
			sesion.registrar("mio_al_empezar")

		def al_registrar(self, sesion, registro):
			# Nunca se recibe un registro a medias de atender otro: los que se registran aquí esperan turno.
			assert not self.dentro
			self.dentro = True
			self.vistos.append(registro.tipo)
			if registro.tipo == "choque":
				sesion.registrar("eco_del_choque")
				self.dentro = False
				return [ev.EvRegistro("devuelto", {}), ev.EvSonido("interfaz/elegir")]
			self.dentro = False
			return None

	oyente = Oyente()
	robot = Robot(ejemplos.vivienda_ejemplo(), actividad=oyente, inicio=Posicion("pla-1", 1.0, 1.0, 180.0))
	assert oyente.vistos[:2] == ["inicio", "mio_al_empezar"]
	assert "entrada_espacio" in oyente.vistos
	nuevos = robot.pulsar("avanzar") + robot.pulsar("avanzar")
	assert registros(nuevos, "choque")
	# Tras el choque, por orden: lo que registró al atenderlo y el registro que devolvió (que también sale en los eventos).
	posicion = oyente.vistos.index("choque")
	assert oyente.vistos[posicion + 1 : posicion + 3] == ["eco_del_choque", "devuelto"]
	assert registros(nuevos, "devuelto") and "interfaz/elegir" in sonidos(nuevos)
	# También los de las ayudas y los que se emiten desde fuera (el reproductor reenvía eventos con «emitir»).
	robot.pulsar("donde_estoy")
	robot.sesion.emitir(ev.EvRegistro("de_fuera", {}))
	assert "ayuda" in oyente.vistos and oyente.vistos[-1] == "de_fuera"
	# Todo lo que se ha registrado ha pasado por el gancho, una sola vez.
	emitidos = [e.tipo for e in robot.eventos if isinstance(e, ev.EvRegistro)] + ["de_fuera"]
	assert oyente.vistos == emitidos

	# Una actividad sin el gancho no se entera y no pasa nada; un fallo en él se anota y la partida sigue.
	class Rota:
		def al_registrar(self, sesion, registro):
			raise RuntimeError("al_registrar roto")

	sin_gancho = Robot(ejemplos.vivienda_ejemplo(), actividad=object(), inicio=Posicion("pla-1", 1.0, 1.0, 180.0))
	assert registros(sin_gancho.pulsar("avanzar") + sin_gancho.pulsar("avanzar"), "choque")
	with caplog.at_level(logging.ERROR, logger="app.motor.sesion"):
		rota = Robot(ejemplos.vivienda_ejemplo(), actividad=Rota(), inicio=Posicion("pla-1", 1.0, 1.0, 180.0))
		assert registros(rota.pulsar("avanzar") + rota.pulsar("avanzar"), "choque")
	assert "Fallo en el gancho «al_registrar» de la actividad" in caplog.text


def test_interactuables_cerca():
	entorno = ejemplos.centro_dos_plantas()
	robot = Robot(entorno, inicio=Posicion("pla-1", 11.6, 7.0, 0.0))
	cerca = robot.sesion.interactuables_cerca()
	assert cerca[0]["clase"] == "parada" and cerca[0]["nombre"] == "Ascensor"
	assert cerca[0]["distancia"] == pytest.approx(0.566, abs=0.01)
	robot = Robot(entorno, inicio=Posicion("pla-1", 9.0, 7.6, 0.0))
	clases = [dato["clase"] for dato in robot.sesion.interactuables_cerca()]
	assert "boca" in clases
	dicho = texto(robot.pulsar("interactuar"))
	assert "Escalera principal, sube 18 peldaños." in dicho and "Lleva a Planta primera." in dicho


# ── Baliza ───────────────────────────────────────────────────────────────────


def test_baliza_directa_cambia_segun_la_orientacion_y_avisa_al_llegar():
	# Giros de 90 grados: la prueba mira la baliza de frente y de lado (de serie se gira 45).
	robot = Robot(ejemplos.vivienda_ejemplo(), inicio=Posicion("pla-1", 0.5, 4.6, 90.0), giro_grados=90.0)
	sesion = robot.sesion
	assert sesion.baliza(("pla-1", 7.0, 4.6))
	assert registros(robot.tic(1), "ayuda")[0]["ayuda"] == "baliza"
	pulsos = [e for e in robot.esperar(3.0) if isinstance(e, ev.EvSonido) and e.nombre.startswith("baliza/")]
	# Mirándola de frente suena «alineado», desde el destino.
	assert {e.nombre for e in pulsos} == {"baliza/alineado"}
	assert pulsos[0].pos[:2] == pytest.approx((7.0, 4.6)) and pulsos[0].bus == "ayudas"
	robot.pulsar("media_vuelta")
	assert "baliza/detras" in sonidos(robot.esperar(3.0))
	robot.pulsar("girar_derecha")
	assert "baliza/pulso" in sonidos(robot.esperar(3.0))
	# Más cerca suena más a menudo, y al llegar suena la llegada y se apaga.
	robot.ir_a(4.5, 4.6)
	lejos = len([n for n in sonidos(robot.esperar(4.0)) if n.startswith("baliza/")])
	robot.ir_a(5.5, 4.6)
	cerca = [n for n in sonidos(robot.esperar(4.0)) if n.startswith("baliza/")]
	assert len(cerca) > lejos and set(cerca) == {"baliza/cerca"}
	nuevos = robot.ir_a(6.6, 4.6) + robot.esperar(2.0)
	assert "baliza/llegada" in sonidos(nuevos)
	assert registros(nuevos, "baliza_llegada")
	assert not [n for n in sonidos(robot.esperar(3.0)) if n.startswith("baliza/")]


def test_baliza_por_ruta_guia_por_las_puertas_y_respeta_el_permiso():
	entorno = ejemplos.vivienda_ejemplo()
	robot = Robot(entorno, inicio=Posicion("pla-1", 4.0, 4.6, 90.0))
	sesion = robot.sesion
	cocina = next(e for e in entorno.plantas[0].espacios if e.nombre == "Cocina").centro()
	puerta = next(a for a in entorno.plantas[0].aberturas if "Cocina" in a.nombre and a.tipo == "puerta")
	sesion.baliza(("pla-1", cocina[0], cocina[1]), por_ruta=True)
	pulsos = [e for e in robot.esperar(3.0) if isinstance(e, ev.EvSonido) and e.nombre.startswith("baliza/")]
	# El destino está tras el tabique: suena desde un punto del camino que sí se alcanza en línea recta, junto a la puerta.
	assert pulsos
	x, y = pulsos[0].pos[:2]
	assert abs(x - puerta.centro()[0]) < 0.6 and abs(y - 4.0) < 0.8
	assert robot.sesion.mundo.visible("pla-1", robot.pos, (x, y), "paso")
	# Apagarla, y prohibirla.
	assert sesion.baliza(None) is False
	assert not [n for n in sonidos(robot.esperar(3.0)) if n.startswith("baliza/")]
	sesion.permitir_ayuda("baliza", False)
	assert sesion.baliza(("pla-1", 7.0, 4.6)) is False
	nuevos = robot.tic(2)
	assert registros(nuevos, "ayuda_denegada")[0]["ayuda"] == "baliza"
	assert not [n for n in sonidos(robot.esperar(3.0)) if n.startswith("baliza/")]


# ── Rendimiento ──────────────────────────────────────────────────────────────


def _edificio_grande(tmp_path) -> tuple[Entorno, object]:
	"""Un edificio de 50 espacios: un pasillo de 96 m, 24 cuartos a cada lado y un vestíbulo, con fuentes y muebles."""
	catalogo = catalogo_de_prueba(tmp_path)
	entorno = ed.crear_entorno("Edificio grande")
	planta = ed.crear_planta(entorno, "Planta")
	pasillo = ed.crear_habitacion_rectangular(entorno, planta, "Pasillo", 0, 6, 96, 2, tipo="pasillo")
	vestibulo = ed.crear_habitacion_adosada(entorno, planta, "Vestíbulo", pasillo, "oeste", 5, 2, tipo="vestibulo")
	ed.anadir_puerta_entre(entorno, planta, vestibulo, pasillo, tipo="hueco", ancho=1.6)
	for numero in range(24):
		for lado, y in (("sur", 0.0), ("norte", 8.0)):
			cuarto = ed.crear_habitacion_rectangular(entorno, planta, f"Cuarto {lado} {numero + 1}", numero * 4.0, y, 4.0, 6.0)
			ed.anadir_puerta_entre(entorno, planta, cuarto, pasillo, estado="abierta" if numero % 2 else "cerrada")
			if numero % 3 == 0:
				ed.anadir_fuente(entorno, planta, f"Reloj {lado} {numero + 1}", numero * 4.0 + 2.0, y + 3.0, "reloj", radio=10.0)
			poner_objeto(entorno, planta, catalogo, "prueba/mesa", numero * 4.0 + 2.0, y + 2.0)
			poner_objeto(entorno, planta, catalogo, "prueba/silla", numero * 4.0 + 1.0, y + 4.5)
	ed.fijar_inicio(entorno, planta, 1.0, 7.0, 90.0)
	assert len(planta.espacios) == 50
	return entorno, catalogo


def test_rendimiento_sesenta_fotogramas_por_segundo_en_un_edificio_de_cincuenta_espacios(tmp_path):
	entorno, catalogo = _edificio_grande(tmp_path)
	sesion = Sesion(entorno, catalogo, AjustesJuego(modo_movimiento="continuo", velocidad_ms=1.4, detalle=3), semilla=5)
	sesion.avanzar(1 / 60)
	sesion.orden("avanzar")
	fotogramas = 60 * 30
	peor = 0.0
	inicio = time.perf_counter()
	for numero in range(fotogramas):
		if numero % 240 == 120:
			sesion.orden("sonda")
			sesion.orden("sonda", 0)
		if numero % 600 == 300:
			sesion.orden("alrededor")
		antes = time.perf_counter()
		sesion.avanzar(1 / 60)
		sesion.fuentes()
		sesion.oyente()
		peor = max(peor, time.perf_counter() - antes)
	total = time.perf_counter() - inicio
	medio_ms = total / fotogramas * 1000.0
	# Ha recorrido unos 40 m de pasillo en 30 s de juego, oyendo relojes por las puertas.
	assert sesion.jugador.x > 35.0
	# Un fotograma a 60 por segundo dura 16,7 ms: el motor debe gastar una pequeña parte.
	assert medio_ms < 4.0, f"fotograma medio de {medio_ms:.2f} ms"
	assert peor < 0.1, f"el peor fotograma tardó {peor * 1000:.0f} ms"


def test_rendimiento_de_rutas_y_cercanos_en_el_edificio_grande(tmp_path):
	entorno, catalogo = _edificio_grande(tmp_path)
	sesion = Sesion(entorno, catalogo, AjustesJuego(), semilla=5)
	sesion.avanzar(0.05)
	inicio = time.perf_counter()
	ruta = sesion.nav.ruta(entorno.inicio, ("pla-1", 94.0, 11.0))
	primera = time.perf_counter() - inicio
	assert ruta is not None and 95.0 < ruta.longitud < 110.0
	inicio = time.perf_counter()
	for _i in range(5):
		sesion.nav.ruta(entorno.inicio, ("pla-1", 94.0, 11.0))
	repetida = (time.perf_counter() - inicio) / 5
	inicio = time.perf_counter()
	lista = sesion.percepcion.lista_cercanos()
	cercanos = time.perf_counter() - inicio
	assert lista
	# Son consultas ocasionales (una ruta de 100 m de punta a punta), no de cada fotograma: basta con que no se noten.
	assert primera < 3.0 and repetida < 1.5 and cercanos < 1.5, (primera, repetida, cercanos)
