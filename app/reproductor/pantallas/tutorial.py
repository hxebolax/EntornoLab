"""Tutorial jugable: un entorno mínimo, hecho por código, que enseña los controles uno a uno.

Dos habitaciones unidas por una puerta cerrada, una mesa en medio de la
primera y un premio que suena en la segunda. El alumno aprende, en este
orden y sin poder perderse: avanzar, chocar (chocar informa, no castiga),
girar, rodear un objeto, preguntar dónde está, mirar alrededor, usar el
bastón sonoro, abrir una puerta y encontrar un premio por su sonido.

El tutorial es una **actividad** como las demás para el motor (un objeto con
los ganchos ``al_empezar``, ``tic`` y ``al_pedir``): no hay un modo especial
ni en la sesión ni en la pantalla de juego. Cada paso se da por hecho mirando
lo que el motor ya cuenta (pasos, choques, ayudas usadas, estado de la
puerta), y sus instrucciones nombran la tecla o el botón que el alumno tiene
de verdad, con el mando conectado si lo hay. La acción «objetivo» repite el
paso y «pista» dice hacia dónde queda lo que se busca.

No se graba como sesión: no es una actividad del profesional.
"""

from __future__ import annotations

import logging
import math
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.i18n import _
from app.dominio import edicion as ed
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.formato import Paquete
from app.dominio.modelo import Entorno, Objeto
from app.entrada import acciones
from app.motor import eventos as ev
from app.motor.sesion import AjustesJuego

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)

# Medidas del entorno (metros). La sala va de (0, 0) a (6, 4) y el cuarto del premio queda al este.
ANCHO_SALA = 6.0
FONDO_SALA = 4.0
ANCHO_CUARTO = 3.0
INICIO = (1.0, 2.0, 90.0)
MESA = (3.5, 2.0)
PREMIO = (7.6, 2.0)
TIPO_MESA = "hogar/mesa_comedor"
DISTANCIA_PREMIO = 0.9


def crear_entorno_tutorial(catalogo: Catalogo) -> tuple[Entorno, dict[str, Any]]:
	"""El entorno del tutorial y sus piezas (planta, mesa y puerta) para la actividad."""
	entorno = ed.crear_entorno(_("Sala del tutorial"), _("Dos habitaciones para aprender los controles."))
	entorno.id = "tutorial"
	planta = ed.crear_planta(entorno, _("Planta baja"))
	sala = ed.crear_habitacion_rectangular(
		entorno,
		planta,
		_("Sala grande"),
		0.0,
		0.0,
		ANCHO_SALA,
		FONDO_SALA,
		descripcion=_("Una sala con una mesa en el centro y una puerta al este."),
	)
	cuarto = ed.crear_habitacion_adosada(entorno, planta, _("Cuarto del premio"), sala, "este", ANCHO_CUARTO, FONDO_SALA)
	puerta = ed.anadir_puerta_entre(entorno, planta, sala, cuarto, ancho=0.9, estado="cerrada", nombre=_("Puerta del cuarto"))
	if catalogo.objeto(TIPO_MESA) is not None:
		mesa = catalogo.crear_objeto(TIPO_MESA, MESA[0], MESA[1], 90.0)
	else:
		# Sin el complemento del hogar, la mesa es una caja con sus medidas: el tutorial funciona igual.
		mesa = Objeto(tipo="caja", x=MESA[0], y=MESA[1], ancho=0.9, fondo=1.4, alto=0.75)
	mesa.nombre = _("Mesa")
	mesa.id = entorno.nuevo_id("obj")
	planta.objetos.append(mesa)
	ed.fijar_inicio(entorno, planta, *INICIO)
	return entorno, {"planta": planta.id, "mesa": mesa, "puerta": puerta}


@dataclass
class Paso:
	"""Un paso del tutorial: qué se pide, cuándo se da por hecho y hacia dónde apunta la pista."""

	clave: str
	texto: Callable[[], str]
	hecho: Callable[[Any, dict[str, Any]], bool]
	destino: tuple[float, float] | None = None
	nombre_destino: str = ""


class ActividadTutorial:
	"""La actividad del tutorial (ver el docstring del módulo)."""

	tipo = "tutorial"
	modo = "practica"

	def __init__(self, control_de: Callable[[str], str], piezas: dict[str, Any]) -> None:
		"""``control_de(accion)`` devuelve la tecla o el botón de una acción, dicho en una frase."""
		self.nombre = _("Tutorial")
		self.control_de = control_de
		self.piezas = piezas
		self.indice = 0
		self.terminada = False
		self._marca: dict[str, Any] = {}
		mesa: Objeto = piezas["mesa"]
		puerta = piezas["puerta"]
		centro_puerta = ((puerta.a[0] + puerta.b[0]) / 2.0, (puerta.a[1] + puerta.b[1]) / 2.0)
		lado_este = mesa.x + max(mesa.ancho, mesa.fondo) / 2.0 + 0.45
		c = control_de
		self.pasos: list[Paso] = [
			Paso(
				"avanzar",
				lambda: _("Vamos a andar. Pulsa {tecla} dos veces para dar dos pasos hacia delante.").format(tecla=c("avanzar")),
				lambda s, m: s.movimiento.pasos >= m["pasos"] + 2,
			),
			Paso(
				"chocar",
				lambda: _(
					"Muy bien. Delante tienes una mesa. Sigue avanzando hasta chocar con ella. Chocar no es malo: te dice dónde están las cosas."
				),
				lambda s, m: s.movimiento.choques > m["choques"],
				destino=(mesa.x, mesa.y),
				nombre_destino=_("La mesa"),
			),
			Paso(
				"girar",
				lambda: _(
					"Eso era la mesa. Para rodearla hay que girar. Pulsa {izquierda} para girar a la izquierda, o {derecha} para girar a la derecha."
				).format(izquierda=c("girar_izquierda"), derecha=c("girar_derecha")),
				lambda s, m: abs(geo.diferencia_rumbos(m["rumbo"], s.jugador.rumbo)) >= 40.0,
			),
			Paso(
				"rodear",
				lambda: _(
					"Ahora rodea la mesa y pasa al otro lado, hacia el este. Avanza un par de pasos, gira otra vez y sigue. "
					"Si te pierdes, pide una pista con {pista}."
				).format(pista=c("pista")),
				lambda s, m: s.jugador.x >= lado_este,
				destino=(lado_este + 0.4, mesa.y + 1.2),
				nombre_destino=_("El otro lado de la mesa"),
			),
			Paso(
				"donde_estoy",
				lambda: _("Has rodeado la mesa. Cuando no sepas dónde estás, pregúntalo: pulsa {tecla}.").format(tecla=c("donde_estoy")),
				lambda s, m: s.percepcion.usos.get("donde_estoy", 0) > m["usos"].get("donde_estoy", 0),
			),
			Paso(
				"alrededor",
				lambda: _("También puedes preguntar qué te rodea, sin moverte. Pulsa {tecla}.").format(tecla=c("alrededor")),
				lambda s, m: any(s.percepcion.usos.get(a, 0) > m["usos"].get(a, 0) for a in ("alrededor", "mirar", "delante")),
			),
			Paso(
				"sonda",
				lambda: _("El bastón sonoro te dice con un tono lo que hay delante y a qué distancia. Pruébalo: pulsa {tecla}.").format(
					tecla=c("sonda")
				),
				lambda s, m: s.percepcion.usos.get("sonda", 0) > m["usos"].get("sonda", 0),
			),
			Paso(
				"puerta",
				lambda: _(
					"En la pared del este hay una puerta cerrada. Ve hasta ella y ábrela con {tecla}. Recuerda: {pista} te da una pista."
				).format(tecla=c("interactuar"), pista=c("pista")),
				lambda s, m: s.mundo.estado_abertura(puerta.id) == "abierta",
				destino=(centro_puerta[0] - 0.6, centro_puerta[1]),
				nombre_destino=_("La puerta"),
			),
			Paso(
				"premio",
				lambda: _("Puerta abierta. Al otro lado suena un premio. Camina hacia el sonido hasta llegar a él."),
				lambda s, m: s.distancia_a((piezas["planta"], PREMIO[0], PREMIO[1])) <= DISTANCIA_PREMIO,
				destino=PREMIO,
				nombre_destino=_("El premio"),
			),
		]

	# ── Lo que consulta el reproductor ──

	def ajustes(self, base: AjustesJuego) -> AjustesJuego:
		"""El tutorial se juega por pasos, con giros de un cuarto de vuelta y todas las ayudas."""
		base.modo_movimiento = "pasos"
		base.giro_grados = 90.0
		base.detalle = max(1, base.detalle)
		base.ayudas = {}
		return base

	def inicio(self) -> None:
		"""Se empieza en el inicio del entorno."""
		return None

	def estado(self) -> dict[str, Any]:
		"""Objetivo actual y pasos hechos."""
		objetivo = self.pasos[self.indice].texto() if not self.terminada else _("Tutorial terminado.")
		return {"objetivo": objetivo, "hechos": self.indice, "total": len(self.pasos)}

	def resultado(self, sesion: Any) -> dict[str, Any]:
		"""Lo que se añade al resultado de la sesión."""
		return {"tutorial": True, "hechos": self.indice, "total": len(self.pasos), "completada": self.terminada}

	# ── Ganchos del motor ──

	def _marcar(self, sesion: Any) -> None:
		"""Apunta cómo están los contadores al empezar un paso, para ver después lo que cambia."""
		self._marca = {
			"pasos": sesion.movimiento.pasos,
			"choques": sesion.movimiento.choques,
			"rumbo": sesion.jugador.rumbo,
			"usos": dict(sesion.percepcion.usos),
		}

	def _decir_paso(self, sesion: Any, antes: str = "") -> None:
		texto = self.pasos[self.indice].texto()
		# No interrumpe: espera a que termine lo que el alumno acaba de pedir (su «dónde estoy», su choque).
		sesion.decir(f"{antes} {texto}".strip(), canal="ayuda", prioridad=2, clave="tutorial", caduca=120.0)

	def al_empezar(self, sesion: Any) -> None:
		"""Da la bienvenida y el primer paso."""
		self._marcar(sesion)
		bienvenida = _("Tutorial. Estás en una sala. Para oír otra vez lo que hay que hacer, pulsa {objetivo}.").format(
			objetivo=self.control_de("objetivo")
		)
		sesion.decir(f"{bienvenida} {self.pasos[0].texto()}", canal="ayuda", prioridad=3)

	def tic(self, sesion: Any, dt: float) -> None:
		"""Comprueba el paso actual y, si está hecho, pasa al siguiente."""
		if self.terminada:
			return
		paso = self.pasos[self.indice]
		if not paso.hecho(sesion, self._marca):
			return
		sesion.registrar("objetivo", id=paso.clave, nombre=paso.clave)
		if self.indice + 1 >= len(self.pasos):
			self.indice = len(self.pasos)
			self._terminar(sesion)
			return
		self.indice += 1
		self._marcar(sesion)
		sesion.sonar("logro/pista", bus="interfaz", volumen=0.7)
		if self.pasos[self.indice].clave == "premio":
			sesion.anadir_fuente("premio_tutorial", "premio/cerca", (self.piezas["planta"], PREMIO[0], PREMIO[1]), radio=14.0, bus="ayudas")
		self._decir_paso(sesion)

	def _terminar(self, sesion: Any) -> None:
		self.terminada = True
		sesion.quitar_fuente("premio_tutorial")
		sesion.sonar("premio/recogido", bus="interfaz")
		sesion.vibrar("objetivo")
		sesion.registrar("premio", id="tutorial", nombre=_("Premio del tutorial"))
		sesion.terminar({"completada": True})

	def al_pedir(self, sesion: Any, accion: str) -> list[Any]:
		"""«Objetivo» repite el paso; «pista» dice hacia dónde queda lo que se busca."""
		if self.terminada:
			return []
		paso = self.pasos[self.indice]
		if accion == "pista" and paso.destino is not None:
			jugador = sesion.jugador
			distancia = math.hypot(paso.destino[0] - jugador.x, paso.destino[1] - jugador.y)
			direccion = sesion.leng.direccion_a(jugador.punto, jugador.rumbo, paso.destino)
			texto = _("{lugar} está {direccion}, a {distancia}.").format(
				lugar=paso.nombre_destino, direccion=direccion, distancia=sesion.leng.distancia(distancia)
			)
		else:
			texto = paso.texto()
		# Se devuelve el evento (y no se llama a ``sesion.decir``): así el motor sabe que la petición está atendida.
		return [ev.EvVoz(texto, True, "ayuda")]


def empezar_tutorial(app: Aplicacion) -> bool:
	"""Crea el entorno y la actividad del tutorial y empieza a jugarlo."""
	entorno, piezas = crear_entorno_tutorial(app.catalogo)
	actividad = ActividadTutorial(lambda accion: app.entrada.control_de(accion, acciones.JUEGO), piezas)
	paquete = Paquete(entorno=entorno)
	return app.empezar_partida(paquete, None, tutorial=True, actividad=actividad)
