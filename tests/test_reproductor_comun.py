"""Material común de las pruebas del reproductor: el ``Robot`` y unas actividades dobles.

El reproductor se prueba como lo usaría un alumno, pero sin ventana real, sin
sonido y sin voz: ``Aplicacion(pruebas=True)`` usa los controladores «dummy»
de SDL, el motor de sonido nulo y ``VozFalsa``. El ``Robot`` lo maneja con
acciones, teclas (por el camino real: pantalla, mapa de teclado y acciones) y
fotogramas, y lee lo que se habría dicho.

Las actividades se sustituyen por un doble pequeño (``instalar_actividades_dobles``)
para que estas pruebas comprueben el REPRODUCTOR y no dependan de las reglas
de cada tipo de actividad, que tienen sus propias pruebas. Una prueba aparte
usa el paquete real si está disponible.
"""

from __future__ import annotations

import math
import sys
import types
from pathlib import Path
from typing import Any

import pygame
import pytest

from app.dominio import geometria as geo
from app.dominio.formato import cargar_paquete, guardar_paquete
from app.motor import eventos as ev
from app.reproductor import puente_actividades
from app.reproductor.aplicacion import Aplicacion
from app.reproductor.arranque import analizar_argumentos
from app.reproductor.menus import Menu

from .conftest import RAIZ

VIVIENDA = RAIZ / "data" / "ejemplos" / "vivienda-de-ejemplo.elab"
DT = 1.0 / 60.0


# ── Actividades dobles ───────────────────────────────────────────────────────


class ActividadDoble:
	"""Una búsqueda de premios mínima con la interfaz que el reproductor espera de una actividad."""

	def __init__(self, datos: dict, entorno: Any, catalogo: Any = None, estilo: str | None = None, semilla: int | None = None) -> None:
		self.datos = datos
		self.id = str(datos.get("id") or "doble")
		self.nombre = str(datos.get("nombre") or "Actividad doble")
		self.tipo = str(datos.get("tipo") or "busqueda")
		self.modo = str(datos.get("modo") or "juego")
		self.estilo = estilo
		self.premios = [dict(p) for p in datos.get("premios") or []]
		self.recogidos: list[str] = []
		self.ordenes: list[tuple[str, dict]] = []
		self.valoracion: dict | None = None

	def ajustes(self, base: Any) -> Any:
		for ayuda, regla in (self.datos.get("ayudas") or {}).items():
			base.ayudas[ayuda] = dict(regla)
		return base

	def inicio(self) -> None:
		return None

	def estado(self) -> dict:
		return {
			"objetivo": "Encuentra todos los premios",
			"hechos": len(self.recogidos),
			"total": len(self.premios),
			"puntos": 10 * len(self.recogidos),
			"estrellas": 0,
			"tiempo_restante": None,
			"nivel": 0,
		}

	def al_empezar(self, sesion: Any) -> list:
		for premio in self.premios:
			sesion.anadir_fuente(f"premio_{premio['id']}", "premio/cerca", (premio["planta"], premio["x"], premio["y"]), bus="ayudas")
		return [ev.EvVoz(str((self.datos.get("mensajes") or {}).get("inicio") or "Busca los premios."), False, "juego")]

	def tras_mover(self, sesion: Any) -> None:
		for premio in self.premios:
			if premio["id"] in self.recogidos or sesion.distancia_a((premio["planta"], premio["x"], premio["y"])) > 0.9:
				continue
			self.recogidos.append(premio["id"])
			sesion.quitar_fuente(f"premio_{premio['id']}")
			sesion.sonar("premio/recogido")
			sesion.registrar("premio", id=premio["id"], nombre=premio["nombre"])
			sesion.decir(f"Has encontrado {premio['nombre']}.", prioridad=3)
		if self.premios and len(self.recogidos) == len(self.premios):
			sesion.terminar()

	def al_pedir(self, sesion: Any, accion: str) -> list:
		return [ev.EvVoz("Encuentra todos los premios." if accion == "objetivo" else "Sigue el sonido.", True, "ayuda")]

	def orden_profesional(self, sesion: Any, tipo: str, datos: dict | None) -> list:
		self.ordenes.append((tipo, dict(datos or {})))
		if tipo == "pista":
			return [ev.EvVoz(str((datos or {}).get("texto") or "Pista."), False, "profesional")]
		if tipo == "ayudas":
			for ayuda, regla in ((datos or {}).get("ayudas") or {}).items():
				sesion.permitir_ayuda(ayuda, bool(regla.get("permitida", True)), regla.get("limite"))
			return [ev.EvSonido("interfaz/ajuste", bus="interfaz")]
		if tipo == "premio":
			return [ev.EvVoz(f"Premio nuevo: {(datos or {}).get('nombre')}.", False, "profesional")]
		return []

	def valorar(self, sesion: Any, respuestas: dict) -> dict:
		self.valoracion = dict(respuestas)
		sesion.registrar("valoracion", actividad=self.id, **respuestas)
		return self.valoracion

	def resultado(self, sesion: Any) -> dict:
		completa = bool(self.premios) and len(self.recogidos) == len(self.premios)
		return {
			"actividad": {"id": self.id, "nombre": self.nombre, "tipo": self.tipo, "modo": self.modo},
			"completada": completa,
			"hechos": len(self.recogidos),
			"total": len(self.premios),
			"puntos": 10 * len(self.recogidos),
			"estrellas": 3 if completa else 0,
		}


def _recompensas_dobles(resultado: dict, estilo: str) -> list[dict]:
	if not resultado.get("completada"):
		return []
	lista = [{"tipo": "estrella", "nombre": f"Estrella {n + 1}"} for n in range(int(resultado.get("estrellas", 0)))]
	lista.append({"tipo": "medalla", "nombre": "Medalla de explorador"})
	return lista


def _preguntas_dobles(estilo: str = "adulto") -> list[dict]:
	return [
		{
			"id": clave,
			"texto": texto,
			"opciones": [{"valor": valor, "texto": nombre} for valor, nombre in enumerate(("Nada", "Regular", "Mucho"), start=1)],
		}
		for clave, texto in (("esfuerzo", "¿Te ha costado?"), ("disfrute", "¿Te ha gustado?"))
	]


def instalar_actividades_dobles(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
	"""Pone un ``app.actividades`` de mentira (y sus módulos de recompensas y cuestionario) mientras dure la prueba."""
	paquete = types.ModuleType("app.actividades")
	paquete.__path__ = []  # type: ignore[attr-defined] - para que se pueda importar «app.actividades.x»
	paquete.creadas = []  # type: ignore[attr-defined]

	def crear_actividad(
		datos: dict, entorno: Any, catalogo: Any = None, estilo: str | None = None, semilla: int | None = None
	) -> ActividadDoble:
		if datos.get("tipo") == "rota":
			raise ValueError("actividad mal definida")
		actividad = ActividadDoble(datos, entorno, catalogo, estilo, semilla)
		paquete.creadas.append(actividad)  # type: ignore[attr-defined]
		return actividad

	paquete.crear_actividad = crear_actividad  # type: ignore[attr-defined]
	paquete.describir_actividad = lambda datos, entorno=None: f"Doble: {datos.get('descripcion') or 'sin descripción'}"  # type: ignore[attr-defined]
	paquete.TIPOS = {"busqueda": object()}  # type: ignore[attr-defined]
	recompensas = types.ModuleType("app.actividades.recompensas")
	recompensas.calcular = _recompensas_dobles  # type: ignore[attr-defined]
	cuestionario = types.ModuleType("app.actividades.cuestionario")
	cuestionario.preguntas = _preguntas_dobles  # type: ignore[attr-defined]
	cuestionario.presentacion = lambda estilo="adulto": "Dos preguntas, si quieres."  # type: ignore[attr-defined]
	monkeypatch.setitem(sys.modules, "app.actividades", paquete)
	monkeypatch.setitem(sys.modules, "app.actividades.recompensas", recompensas)
	monkeypatch.setitem(sys.modules, "app.actividades.cuestionario", cuestionario)
	monkeypatch.setattr(puente_actividades, "_avisados", set())
	return paquete


# ── Paquetes de prueba ───────────────────────────────────────────────────────


def puntos_para_premios(paquete: Any, cuantos: int = 2) -> list[tuple[str, float, float]]:
	"""Puntos del entorno a los que se llega andando desde el inicio, uno por lugar, lejos del inicio."""
	from app.dominio.catalogo import Catalogo
	from app.audio.base import carpetas_de_serie
	from app.motor.mundo import Mundo
	from app.motor.navegacion import Navegador

	entorno = paquete.entorno
	mundo = Mundo(entorno, Catalogo.cargar(carpetas_de_serie("plugins")))
	nav = Navegador(mundo)
	inicio = (entorno.inicio.planta, entorno.inicio.x, entorno.inicio.y)
	puntos: list[tuple[str, float, float]] = []
	for planta in entorno.plantas:
		for espacio in planta.espacios:
			if espacio.macizo or len(puntos) >= cuantos:
				continue
			x0, y0, x1, y1 = espacio.caja()
			candidatos = [espacio.centro(), (x0 + 0.7, y0 + 0.7), (x1 - 0.7, y1 - 0.7), (x0 + 0.7, y1 - 0.7), (x1 - 0.7, y0 + 0.7)]
			for x, y in candidatos:
				if mundo.espacio_en(planta.id, x, y) is not espacio or mundo.dentro_de_objeto(planta.id, x, y) is not None:
					continue
				if mundo.distancia_libre(planta.id, x, y, 0.5) < 0.3:
					continue
				ruta = nav.ruta(inicio, (planta.id, x, y))
				if ruta is not None and ruta.longitud > 2.0:
					puntos.append((planta.id, round(x, 2), round(y, 2)))
					break
	assert len(puntos) >= cuantos, "el entorno de ejemplo no tiene bastantes puntos libres"
	return puntos


def paquete_con_busqueda(carpeta: Path, premios: int = 2, nombre: str = "vivienda-con-juego.elab", **extra: Any) -> Path:
	"""Copia la vivienda de ejemplo a ``carpeta`` añadiéndole una búsqueda de premios. Devuelve la ruta del paquete."""
	original = cargar_paquete(VIVIENDA)
	puntos = puntos_para_premios(original, premios)
	actividad = {
		"formato": 1,
		"id": "busca",
		"nombre": "Busca los premios",
		"descripcion": "Encuentra los premios escondidos por la casa.",
		"tipo": "busqueda",
		"modo": "juego",
		"estilo": "del_alumno",
		"premios": [
			{
				"id": f"p{n + 1}",
				"nombre": f"la moneda {n + 1}",
				"planta": planta,
				"x": x,
				"y": y,
				"sonido": "premio/cerca",
				"visibilidad": "lejos",
			}
			for n, (planta, x, y) in enumerate(puntos)
		],
		"mensajes": {"inicio": "Hay monedas escondidas. ¡Búscalas!"},
		**extra,
	}
	carpeta.mkdir(parents=True, exist_ok=True)
	ruta = carpeta / nombre
	guardar_paquete(ruta, original.entorno, [actividad], dict(original.recursos))
	return ruta


# ── El robot ─────────────────────────────────────────────────────────────────


class Robot:
	"""Maneja el reproductor como una persona: acciones, teclas y fotogramas; y escucha lo que se dice."""

	def __init__(self, app: Aplicacion) -> None:
		self.app = app

	# ── Estado ──

	@property
	def cima(self) -> Any:
		return self.app.cima

	@property
	def partida(self) -> Any:
		return self.app.partida

	@property
	def sesion(self) -> Any:
		return self.app.partida.sesion

	@property
	def jugador(self) -> Any:
		return self.sesion.jugador

	def pantallas(self) -> list[str]:
		"""Nombres de las clases de la pila, de abajo arriba."""
		return [type(pantalla).__name__ for pantalla in self.app.pila]

	def opciones(self) -> list[str]:
		"""Textos de las opciones del menú de arriba."""
		assert isinstance(self.cima, Menu), f"arriba no hay un menú, sino {type(self.cima).__name__}"
		return [opcion.texto for opcion in self.cima.opciones]

	# ── Entrada ──

	def esperar(self, fotogramas: int = 1) -> None:
		self.app.avanzar(fotogramas, DT)

	def segundos(self, segundos: float) -> None:
		self.app.avanzar(max(1, round(segundos / DT)), DT)

	def accion(self, accion: str, fotogramas: int = 1) -> None:
		"""Pulsa y suelta una acción y deja pasar fotogramas."""
		self.app.inyectar(accion)
		self.esperar(fotogramas)

	def tecla(self, codigo: int, mod: int = 0, unicode: str = "", fotogramas: int = 1) -> None:
		"""Una tecla por el camino real."""
		self.app.tecla(codigo, mod, unicode)
		self.esperar(fotogramas)

	def escribir(self, texto: str) -> None:
		"""Escribe un texto letra a letra en una entrada de texto y acepta con Intro."""
		for letra in texto:
			self.app.tecla(pygame.K_a if letra.isalpha() else pygame.K_0, 0, letra)
		self.tecla(pygame.K_RETURN, unicode="\r")

	def elegir(self, texto: str, fotogramas: int = 2) -> None:
		"""En el menú de arriba, va a la opción que empieza por ``texto`` y la acepta."""
		assert isinstance(self.cima, Menu), f"arriba no hay un menú, sino {type(self.cima).__name__}"
		assert self.cima.elegir(texto), f"no hay ninguna opción «{texto}» en {self.opciones()}"
		self.accion("menu_aceptar", fotogramas)

	def ajustar(self, texto: str, delta: int = 1) -> str:
		"""En el menú de arriba, cambia el valor de la opción que empieza por ``texto``. Devuelve su texto nuevo."""
		assert isinstance(self.cima, Menu)
		assert self.cima.elegir(texto), f"no hay ninguna opción «{texto}» en {self.opciones()}"
		self.accion("menu_derecha" if delta > 0 else "menu_izquierda")
		return self.cima.opciones[self.cima.i].texto

	def atras(self, veces: int = 1) -> None:
		for _i in range(veces):
			self.accion("menu_atras")

	# ── Lo dicho ──

	def marca(self) -> int:
		"""Posición actual en el registro de la voz, para leer después solo lo nuevo."""
		return len(self.app.voz.registro)

	def dicho(self, desde: int = 0) -> str:
		"""Todo lo dicho desde una marca, en una sola cadena."""
		return " | ".join(texto for texto, _canal, _interrumpir in self.app.voz.registro[desde:])

	def canales(self, desde: int = 0) -> list[tuple[str, str]]:
		"""(texto, canal) de lo dicho desde una marca."""
		return [(texto, canal) for texto, canal, _interrumpir in self.app.voz.registro[desde:]]

	def ultimo(self) -> str:
		return self.app.voz.registro[-1][0] if self.app.voz.registro else ""

	def sonidos(self) -> list[str]:
		"""Nombres de los sonidos pedidos al motor nulo."""
		return [str(llamada.get("nombre")) for llamada in self.app.motor.de("reproducir")] if hasattr(self.app.motor, "de") else []

	# ── Moverse por el entorno (por los mismos medios que el alumno) ──

	def girar_a(self, rumbo: float) -> None:
		"""Se gira hasta mirar a ``rumbo`` con una sola orden de giro, del ángulo que haga falta."""
		ajustes = self.sesion.ajustes
		diferencia = geo.diferencia_rumbos(self.jugador.rumbo, rumbo)
		if abs(diferencia) < 1e-6:
			return
		previo = ajustes.giro_grados
		ajustes.giro_grados = abs(diferencia)
		self.accion("girar_derecha" if diferencia > 0 else "girar_izquierda")
		ajustes.giro_grados = previo

	def andar(self, pasos: int = 1) -> None:
		for _i in range(pasos):
			self.accion("avanzar")

	def ir_a(self, x: float, y: float, abrir: bool = True) -> None:
		"""Va en línea recta a un punto: se gira hacia él y da los pasos justos; abre la puerta si le para."""
		for _intento in range(3):
			jugador = self.jugador
			ajustes = self.sesion.ajustes
			distancia = math.hypot(x - jugador.x, y - jugador.y)
			if distancia < 0.05 or self.partida.terminado:
				return
			self.girar_a(geo.rumbo_entre((jugador.x, jugador.y), (x, y)))
			pasos = max(1, math.ceil(distancia / 0.7))
			previo = ajustes.paso_m
			ajustes.paso_m = distancia / pasos
			bloqueado = False
			for _i in range(pasos):
				antes = (jugador.x, jugador.y)
				self.accion("avanzar")
				if self.partida is None or self.partida.terminado:
					break
				if math.hypot(jugador.x - antes[0], jugador.y - antes[1]) < ajustes.paso_m * 0.5:
					bloqueado = True
					break
			ajustes.paso_m = previo
			if self.partida is None or self.partida.terminado or not bloqueado or not abrir:
				return
			self.accion("interactuar")

	def seguir(self, destino: tuple[str, float, float]) -> None:
		"""Va a un lugar por el camino que da el navegador, punto a punto."""
		jugador = self.jugador
		ruta = self.sesion.nav.ruta((jugador.planta, jugador.x, jugador.y), destino)
		assert ruta is not None, f"no hay camino a {destino}"
		for planta, x, y in ruta.puntos[1:]:
			if self.partida is None or self.partida.terminado or planta != self.jugador.planta:
				break
			self.ir_a(x, y)


# ── Fixtures ─────────────────────────────────────────────────────────────────


def crear_app(*argumentos: str) -> Aplicacion:
	"""Un reproductor en modo de pruebas con esos argumentos de línea de órdenes."""
	return Aplicacion(analizar_argumentos(list(argumentos)), pruebas=True)


@pytest.fixture
def sin_navegador(monkeypatch: pytest.MonkeyPatch) -> list[str]:
	"""Las pruebas no abren el navegador: apunta los enlaces que se habrían abierto."""
	abiertos: list[str] = []
	import webbrowser

	monkeypatch.setattr(webbrowser, "open", lambda enlace, *a, **k: abiertos.append(enlace) or True)
	return abiertos


@pytest.fixture
def actividades(monkeypatch: pytest.MonkeyPatch) -> types.ModuleType:
	"""Actividades dobles instaladas (ver el docstring del módulo)."""
	return instalar_actividades_dobles(monkeypatch)


@pytest.fixture
def app(data_temporal: Path, sin_navegador: list[str]) -> Any:
	"""El reproductor en el menú principal, con el alias «Luna»."""
	aplicacion = crear_app("--alumno", "Luna")
	yield aplicacion
	aplicacion.cerrar_todo()


@pytest.fixture
def robot(app: Aplicacion) -> Robot:
	return Robot(app)


def test_el_robot_arranca_en_el_menu_principal(robot: Robot):
	assert robot.pantallas() == ["Menu"]
	assert "Menú principal" in robot.dicho() and "Hola, Luna" in robot.dicho()
	assert robot.opciones()[0].startswith("Continuar") and robot.opciones()[-1] == "Salir"
	robot.esperar(10)
	assert robot.app.fallos == 0
