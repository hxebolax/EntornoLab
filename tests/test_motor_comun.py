"""Material común de las pruebas del motor: un «robot» que da órdenes y mira los eventos.

El motor no tiene interfaz ni sonido, así que se prueba entero como lo usaría
el reproductor: ``orden``, ``avanzar`` y a ver qué eventos salen. El robot
junta esas tres cosas y añade atajos para moverse a un punto por los mismos
medios que el alumno (girar y dar pasos), sin teletransportes.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from app.dominio import edicion as ed
from app.dominio import geometria as geo
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Entorno, Objeto, Planta, Posicion
from app.motor import eventos as ev
from app.motor.sesion import AjustesJuego, Sesion
from tests.test_dominio_comun import catalogo_de_prueba

DT = 0.05


class Robot:
	"""Un alumno automático: da órdenes a una sesión y guarda todo lo que devuelve."""

	def __init__(
		self,
		entorno: Entorno,
		catalogo: Catalogo | None = None,
		inicio: Posicion | None = None,
		semilla: int = 7,
		actividad: Any = None,
		**ajustes: Any,
	) -> None:
		ajustes.setdefault("trafico", False)
		# Las pruebas del motor se escribieron con paso de 0,7 m y giro de 90°;
		# los valores de serie (los de la configuración) son otros, más finos.
		ajustes.setdefault("paso_m", 0.7)
		ajustes.setdefault("giro_grados", 90.0)
		self.sesion = Sesion(entorno, catalogo, AjustesJuego(**ajustes), actividad=actividad, semilla=semilla, inicio=inicio)
		self.eventos: list[Any] = []
		self.tic(2)

	# ── Órdenes ──

	def tic(self, n: int = 1, dt: float = DT) -> list[Any]:
		"""Deja pasar ``n`` fotogramas y devuelve lo ocurrido."""
		nuevos: list[Any] = []
		for _i in range(n):
			nuevos.extend(self.sesion.avanzar(dt))
		self.eventos.extend(nuevos)
		return nuevos

	def esperar(self, segundos: float) -> list[Any]:
		"""Deja pasar ese tiempo de juego."""
		return self.tic(max(1, round(segundos / DT)))

	def pulsar(self, accion: str, n: int = 2) -> list[Any]:
		"""Pulsa y suelta una acción, y deja pasar ``n`` fotogramas."""
		self.sesion.orden(accion)
		self.sesion.orden(accion, 0)
		return self.tic(n)

	def girar_a(self, rumbo: float) -> None:
		"""Se gira hasta mirar a ``rumbo`` con una sola orden de giro (del ángulo que haga falta)."""
		ajustes = self.sesion.ajustes
		diferencia = geo.diferencia_rumbos(self.sesion.jugador.rumbo, rumbo)
		if abs(diferencia) < 1e-6:
			return
		previo = ajustes.giro_grados
		ajustes.giro_grados = abs(diferencia)
		self.pulsar("girar_derecha" if diferencia > 0 else "girar_izquierda", 1)
		ajustes.giro_grados = previo

	def ir_a(self, x: float, y: float, abrir: bool = True) -> list[Any]:
		"""Va andando en línea recta a un punto: se gira hacia él y da los pasos justos. Abre la puerta si le para."""
		jugador = self.sesion.jugador
		ajustes = self.sesion.ajustes
		nuevos: list[Any] = []
		for _intento in range(3):
			distancia = math.hypot(x - jugador.x, y - jugador.y)
			if distancia < 0.05:
				break
			self.girar_a(geo.rumbo_entre((jugador.x, jugador.y), (x, y)))
			pasos = max(1, math.ceil(distancia / 0.7))
			previo = ajustes.paso_m
			ajustes.paso_m = distancia / pasos
			bloqueado = False
			for _i in range(pasos):
				antes = (jugador.planta, jugador.x, jugador.y)
				nuevos.extend(self.pulsar("avanzar", 1))
				if jugador.modo != "andando" or jugador.planta != antes[0]:
					break
				if math.hypot(jugador.x - antes[1], jugador.y - antes[2]) < ajustes.paso_m * 0.5:
					bloqueado = True
					break
			ajustes.paso_m = previo
			if jugador.modo != "andando" or not bloqueado or not abrir:
				break
			nuevos.extend(self.pulsar("interactuar", 1))
		return nuevos

	def seguir(self, destino: tuple[str, float, float]) -> list[Any]:
		"""Va a un lugar por el camino que da el navegador, punto a punto (solo dentro de la planta actual)."""
		jugador = self.sesion.jugador
		ruta = self.sesion.nav.ruta((jugador.planta, jugador.x, jugador.y), destino)
		assert ruta is not None, f"no hay camino a {destino}"
		nuevos: list[Any] = []
		for planta, x, y in ruta.puntos[1:]:
			if planta != jugador.planta:
				break
			nuevos.extend(self.ir_a(x, y))
		return nuevos

	# ── Recorrer el entorno entero, también entre plantas ──

	def esperar_hasta(self, condicion: Any, plazo: float, dt: float = DT) -> bool:
		"""Deja pasar el tiempo hasta que se cumpla ``condicion()`` o pasen ``plazo`` segundos de juego. Devuelve si se cumplió."""
		pasado = 0.0
		while not condicion():
			if pasado >= plazo or self.sesion.terminado:
				return bool(condicion())
			self.tic(1, dt)
			pasado += dt
		return True

	def recorrer(self, destino: Any, cerca: float = 0.5, evitar: Any = (), intentos: int = 10) -> bool:
		"""Va a un lugar ``(planta, x, y)`` de cualquier planta por el camino del navegador, como lo haría el alumno.

		Anda con ``ir_a`` (abre las puertas que le paran) y, donde la ruta
		cambia de planta, usa el conector con las órdenes de verdad: en una
		escalera o una rampa se pone de cara a la boca y avanza peldaño a
		peldaño; en un ascensor lo llama, espera a que llegue, entra, elige la
		planta girando, acepta y sale al llegar. Tras cada tramo vuelve a pedir
		la ruta desde donde ha quedado. Devuelve si ha llegado.
		"""
		planta, x, y = str(destino[0]), float(destino[1]), float(destino[2])
		jugador = self.sesion.jugador
		for _intento in range(intentos):
			if self.sesion.terminado:
				return False
			self._acabar_conector()
			if jugador.planta == planta and math.hypot(jugador.x - x, jugador.y - y) <= cerca:
				return True
			ruta = self.sesion.nav.ruta((jugador.planta, jugador.x, jugador.y), (planta, x, y), evitar)
			if ruta is None:
				return False
			for numero, (planta_punto, px, py) in enumerate(ruta.puntos[1:], start=1):
				if self.sesion.terminado or jugador.modo != "andando":
					break
				if planta_punto != jugador.planta:
					# Primer cambio de planta de esta ruta (se vuelve a pedir tras cada uno): su conector es el primero.
					# El punto anterior es la boca de la escalera o la puerta del ascensor.
					self.usar_conector(ruta.conectores[0] if ruta.conectores else "", ruta.puntos[numero - 1], planta_punto)
					break
				self.ir_a(px, py)
		jugador = self.sesion.jugador
		return jugador.planta == planta and math.hypot(jugador.x - x, jugador.y - y) <= cerca + 0.6

	def usar_conector(self, conector_id: str, boca: tuple[str, float, float], planta_destino: str) -> bool:
		"""Usa un conector desde su boca (o su parada) para ir a ``planta_destino``. Devuelve si ha llegado a esa planta."""
		conector = self.sesion.entorno.elemento(conector_id)
		if conector is None:
			return False
		if conector.tipo == "ascensor":
			return self.usar_ascensor(conector_id, planta_destino)
		jugador = self.sesion.jugador
		mundo = self.sesion.mundo
		for _intento in range(4):
			if jugador.modo == "conector":
				break
			bocas = [b for _d, b in mundo.bocas_cerca(jugador.planta, boca[1], boca[2], 1.0) if b.conector.id == conector_id]
			if not bocas:
				return False
			elegida = bocas[0]
			# Un poco antes de la boca, en la línea del tramo, y de cara a él: el paso siguiente entra.
			atras = geo.vector_rumbo(elegida.rumbo)
			self.ir_a(elegida.x - atras[0] * 0.5, elegida.y - atras[1] * 0.5)
			if jugador.modo == "conector":
				break
			self.girar_a(elegida.rumbo)
			self.pulsar("avanzar", 1)
		self._acabar_conector()
		return jugador.planta == planta_destino and jugador.modo == "andando"

	def _acabar_conector(self) -> None:
		"""Si está en una escalera o una rampa, sigue avanzando hasta salir; si está en una cabina, sale en la planta en que esté."""
		jugador = self.sesion.jugador
		for _paso in range(200):
			if jugador.modo != "conector" or self.sesion.terminado:
				break
			tramo = self.sesion.movimiento.en_tramo
			if tramo is not None and tramo.conector.tipo == "escalera_mecanica":
				self.tic(4)
			else:
				self.pulsar("avanzar", 1)
		if jugador.modo == "ascensor":
			cabina = self.sesion.movimiento.cabina
			if cabina is not None:
				self.esperar_hasta(lambda: cabina.estado != "viajando", 30.0)
				cabina.seleccion = cabina.en_parada
				self.pulsar("interactuar", 1)
				self.pulsar("avanzar", 2)

	def usar_ascensor(self, conector_id: str, planta_destino: str) -> bool:
		"""Llama al ascensor desde su puerta, entra, elige la planta con los giros, acepta y sale al llegar."""
		movimiento = self.sesion.movimiento
		jugador = self.sesion.jugador
		conector = self.sesion.entorno.elemento(conector_id)
		estado = movimiento.ascensores.get(conector_id)
		if conector is None or estado is None:
			return False
		aqui = next((i for i, parada in enumerate(conector.paradas) if parada.planta == jugador.planta), None)
		alla = next((i for i, parada in enumerate(conector.paradas) if parada.planta == planta_destino), None)
		if aqui is None or alla is None:
			return False
		puerta = conector.paradas[aqui].puerta
		# Delante de la puerta y de cara a ella.
		self.ir_a(puerta.x, puerta.y, abrir=False)
		self.girar_a(puerta.rumbo)
		if not (estado.estado == "abierto" and estado.en_parada == aqui):
			self.pulsar("interactuar", 1)
			if not self.esperar_hasta(lambda: estado.estado == "abierto" and estado.en_parada == aqui, 30.0):
				return False
		self.pulsar("avanzar", 1)
		if jugador.modo != "ascensor":
			return False
		for _giro in range(len(conector.paradas)):
			if estado.seleccion == alla:
				break
			self.pulsar("girar_derecha" if alla > estado.seleccion else "girar_izquierda", 1)
		self.pulsar("interactuar", 1)
		if not self.esperar_hasta(lambda: estado.estado == "abierto" and estado.en_parada == alla, 60.0):
			return False
		self.pulsar("avanzar", 2)
		return jugador.modo == "andando" and jugador.planta == planta_destino

	# ── Lo ocurrido ──

	@property
	def pos(self) -> tuple[float, float]:
		"""Posición actual."""
		return self.sesion.jugador.x, self.sesion.jugador.y

	@property
	def espacio(self) -> str:
		"""Nombre del espacio en el que está."""
		jugador = self.sesion.jugador
		espacio = self.sesion.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		return espacio.nombre if espacio is not None else ""


def voces(eventos: list[Any]) -> list[str]:
	"""Textos de los eventos de voz."""
	return [e.texto for e in eventos if isinstance(e, ev.EvVoz)]


def texto(eventos: list[Any]) -> str:
	"""Todo lo dicho, en una sola cadena."""
	return " | ".join(voces(eventos))


def sonidos(eventos: list[Any]) -> list[str]:
	"""Nombres de los sonidos emitidos."""
	return [e.nombre for e in eventos if isinstance(e, ev.EvSonido)]


def registros(eventos: list[Any], tipo: str) -> list[dict[str, Any]]:
	"""Datos de los ``EvRegistro`` de un tipo."""
	return [e.datos for e in eventos if isinstance(e, ev.EvRegistro) and e.tipo == tipo]


def vibraciones(eventos: list[Any]) -> list[str]:
	"""Patrones de vibración emitidos."""
	return [e.patron for e in eventos if isinstance(e, ev.EvVibrar)]


def poner_objeto(
	entorno: Entorno, planta: Planta, catalogo: Catalogo, tipo: str, x: float, y: float, rumbo: float = 0.0, **cambios: Any
) -> Objeto:
	"""Coloca un objeto del catálogo de prueba en una planta, sin pasar por la colocación asistida."""
	objeto = catalogo.crear_objeto(tipo, x, y, rumbo)
	objeto.id = entorno.nuevo_id("obj")
	for clave, valor in cambios.items():
		setattr(objeto, clave, valor)
	planta.objetos.append(objeto)
	return objeto


def sala_de_pruebas(tmp_path: Path) -> tuple[Entorno, Planta, Catalogo, dict[str, Objeto]]:
	"""Una sala de 8 × 6 con una antesala al oeste y varios objetos del catálogo de prueba.

	En la sala: una mesa en el centro, una pizarra en voladizo (no la encuentra
	el bastón), una lámpara alta (no toca a nadie), una alfombra (no corta el
	paso), un frigorífico que zumba y un armario que se abre.
	"""
	catalogo = catalogo_de_prueba(tmp_path)
	entorno = ed.crear_entorno("Sala de pruebas")
	planta = ed.crear_planta(entorno, "Planta baja")
	sala = ed.crear_habitacion_rectangular(entorno, planta, "Sala", 0, 0, 8, 6, descripcion="Una sala amplia con una mesa en el centro.")
	antesala = ed.crear_habitacion_adosada(entorno, planta, "Antesala", sala, "oeste", 3, 6)
	ed.anadir_puerta_entre(entorno, planta, antesala, sala, ancho=0.9, estado="cerrada")
	objetos = {
		"mesa": poner_objeto(entorno, planta, catalogo, "prueba/mesa", 4.0, 3.0),
		"pizarra": poner_objeto(entorno, planta, catalogo, "prueba/pizarra", 2.0, 5.0),
		"lampara": poner_objeto(entorno, planta, catalogo, "prueba/lampara", 2.0, 1.0),
		"alfombra": poner_objeto(entorno, planta, catalogo, "prueba/alfombra", 6.5, 1.5),
		"frigorifico": poner_objeto(entorno, planta, catalogo, "prueba/frigorifico", 7.6, 5.6),
		"armario": poner_objeto(entorno, planta, catalogo, "prueba/armario", 7.6, 0.6, 270.0),
	}
	ed.fijar_inicio(entorno, planta, 1.0, 3.0, 90.0)
	return entorno, planta, catalogo, objetos


def test_eventos_que_reconoce_la_capa_de_sonido():
	"""El presentador reconoce los eventos por el nombre de su clase: son parte del contrato."""
	from app.audio.presentador import tipo_evento

	assert tipo_evento(ev.EvSonido("golpe/madera")) == "sonido"
	assert tipo_evento(ev.EvVoz("hola")) == "voz"
	assert tipo_evento(ev.EvVibrar(patron="choque")) == "vibrar"
	assert tipo_evento(ev.EvAcustica("pasillo")) == "acustica"
	assert tipo_evento(ev.EvRegistro("choque", {})) == ""
	assert tipo_evento(ev.EvFin({})) == ""


def test_nombres_de_sonido():
	assert ev.sonido_de_serie("frigorifico") == "fuente/frigorifico"
	assert ev.sonido_de_serie("golpe_metal") == "golpe/metal"
	assert ev.sonido_de_serie("ambiente_calle") == "ambiente/calle"
	assert ev.sonido_de_serie("sonidos/timbre.ogg") == "sonidos/timbre.ogg"
	assert ev.sonido_de_serie("cafeteria") == "cafeteria"
	assert ev.sonido_golpe("hormigon") == "golpe/piedra"
	assert ev.sonido_roce("valla") == "roce/metal"
	assert ev.sonido_paso("tactil_botones", True, 2) == "pasos/tactil_botones_izq_2"
	assert ev.sonido_paso("lava", False, 9) == "pasos/baldosa_der_3"


def test_el_robot_anda_y_gira(tmp_path):
	entorno, _planta, catalogo, _objetos = sala_de_pruebas(tmp_path)
	robot = Robot(entorno, catalogo)
	assert robot.espacio == "Sala"
	robot.girar_a(0.0)
	assert robot.sesion.jugador.rumbo == 0.0
	antes = robot.pos
	robot.pulsar("avanzar")
	assert robot.pos[1] == antes[1] + 0.7
