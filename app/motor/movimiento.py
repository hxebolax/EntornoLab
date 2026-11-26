"""Movimiento del alumno: pasos, giros, choques con deslizamiento, puertas, escaleras y ascensor.

El alumno es un círculo (25 cm de radio por defecto) que se mueve por la
planta. Al avanzar se le empuja fuera de lo que toca, de modo que resbala a lo
largo de una pared o rodea la esquina de una mesa en vez de quedarse clavado;
si va de frente, choca: suena el material de lo que ha tocado, EN el punto de
contacto, vibra el mando y, según el nivel de detalle, se dice qué es.

Modos (``AjustesJuego.modo_movimiento``):

- ``pasos``: cada orden es un paso del largo del alumno. Un paso virtual = un paso real.
- ``continuo``: se anda mientras se mantiene la orden o se inclina la palanca, a velocidad de paseo.
- ``brujula``: cada dirección es un punto cardinal (avanzar = norte, girar a la derecha = este…).
- ``salas``: se salta de espacio en espacio por sus aberturas; para una primera toma de contacto.
- ``aceras``: cada orden de avanzar camina recto hasta la siguiente novedad (un cruce, un cambio
  de suelo, un obstáculo, una referencia); pensado para exteriores.

Escaleras y rampas: al pasar por la boca en el rumbo del tramo se entra en él
y se recorre peldaño a peldaño, con un sonido por peldaño cuyo tono sube al
subir y baja al bajar. El ascensor no es un espacio que se recorra: es un
estado del alumno (llamar, entrar, elegir planta, viajar, salir).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from app.core.i18n import _, _n
from app.dominio import catalogo
from app.dominio import geometria as geo
from app.dominio.geometria import Punto
from app.dominio.modelo import Conector, Espacio, Tramo
from app.exportar import fichas
from app.motor import eventos as ev
from app.motor.mundo import TIPOS_CALZADA, Boca, InfoAbertura, InfoObjeto, InfoParada, Mundo, Seg
from app.motor.navegacion import Enlace

if TYPE_CHECKING:
	from app.motor.sesion import Sesion

log = logging.getLogger(__name__)

MODOS: tuple[str, ...] = ("pasos", "continuo", "brujula", "salas", "aceras")

# Segundos que hay que mantener una orden para que empiece a repetirse.
RETARDO_REPETICION = 0.45
RETARDO_GIRO = 0.4
# Grados por segundo del giro libre (palanca, o giro_grados = 0).
VELOCIDAD_GIRO = 90.0
ZONA_MUERTA = 0.15
# Un paso lateral es más corto que uno de frente.
FACTOR_LATERAL = 0.6
# Distancia a la boca de una escalera a la que se entra en ella, y tolerancia de rumbo.
RADIO_BOCA = 0.9
ANGULO_BOCA = 50.0
# Distancia a la parada del ascensor para llamarlo o entrar.
RADIO_PARADA = 1.4
ALCANCE_MANO = 1.3
VELOCIDAD_MECANICA = 0.5
ESPERA_VOZ_CHOQUE = 3.0
ESPERA_ROCE = 0.6
# En el modo «aceras», pasos como mucho por cada orden.
MAX_PASOS_ACERA = 80
# Empujón lateral al dar de frente contra el canto de una pared, para rodearlo.
EMPUJE_CANTO = 0.03

RUMBOS_BRUJULA: dict[str, float] = {"avanzar": 0.0, "girar_derecha": 90.0, "retroceder": 180.0, "girar_izquierda": 270.0}
ACCIONES_PASO: dict[str, float] = {"avanzar": 0.0, "retroceder": 180.0, "paso_izquierda": -90.0, "paso_derecha": 90.0}


@dataclass
class Jugador:
	"""Dónde está el alumno y cómo."""

	planta: str = ""
	x: float = 0.0
	y: float = 0.0
	rumbo: float = 0.0
	radio: float = 0.25
	modo: str = "andando"  # andando | conector | ascensor
	z_extra: float = 0.0  # altura sobre el suelo de su planta (a media escalera)
	pie_izquierdo: bool = True

	@property
	def punto(self) -> Punto:
		"""El punto (x, y)."""
		return self.x, self.y


@dataclass
class ResultadoMovimiento:
	"""Lo que pasó al intentar mover el círculo."""

	x: float
	y: float
	contacto: Seg | None = None
	punto: Punto | None = None
	limite: bool = False


@dataclass
class EnTramo:
	"""El alumno en una escalera o rampa: cuánto lleva recorrido desde abajo y hacia dónde va."""

	conector: Conector
	tramo: Tramo
	sentido: int  # +1 sube, -1 baja
	progreso: float  # 0 = boca de abajo, total = boca de arriba
	total: int
	planta_origen: str


@dataclass
class EstadoAscensor:
	"""Dónde está la cabina de un ascensor y qué hace."""

	conector: Conector
	en_parada: int = 0
	estado: str = "reposo"  # reposo | viniendo | abierto | viajando
	t: float = 0.0
	destino: int = 0
	seleccion: int = 0
	mirando_fuera: bool = False


def mover_circulo(mundo: Mundo, planta_id: str, x: float, y: float, dx: float, dy: float, radio: float) -> ResultadoMovimiento:
	"""Mueve un círculo (dx, dy) resbalando por lo que toca.

	Se avanza en tramos cortos (medio radio) para no atravesar nada fino; en
	cada uno se saca al círculo de lo que pisa, empujándolo en perpendicular:
	eso es el deslizamiento. ``contacto`` es lo primero que tocó.
	"""
	distancia = math.hypot(dx, dy)
	resultado = ResultadoMovimiento(x, y)
	if distancia < 1e-9:
		return resultado
	tramos = max(1, math.ceil(distancia / (radio * 0.5)))
	sx, sy = dx / tramos, dy / tramos
	largo = distancia / tramos
	for _i in range(tramos):
		nx, ny = resultado.x + sx, resultado.y + sy
		libre = False
		for _vuelta in range(5):
			contactos = mundo.contactos(planta_id, nx, ny, radio, "paso")
			if not contactos:
				libre = True
				break
			d, (px, py), seg = contactos[0]
			if resultado.contacto is None:
				resultado.contacto = seg
				resultado.punto = (px, py)
			if d > 1e-6:
				ux, uy = (nx - px) / d, (ny - py) / d
			else:
				ux, uy = -sx / largo, -sy / largo
			empuje = radio - d + 1e-4
			nx += ux * empuje
			ny += uy * empuje
			if (ux * sx + uy * sy) / largo < -0.999:
				# De frente contra el canto de una pared (la jamba de una puerta): un empujón de lado,
				# hacia donde la pared se acaba, para rodearlo en vez de quedarse clavado en él.
				if math.hypot(px - seg.ax, py - seg.ay) < 1e-6:
					lx, ly = seg.ax - seg.bx, seg.ay - seg.by
				elif math.hypot(px - seg.bx, py - seg.by) < 1e-6:
					lx, ly = seg.bx - seg.ax, seg.by - seg.ay
				else:
					lx = ly = 0.0
				norma = math.hypot(lx, ly)
				if norma > 1e-9:
					nx += lx / norma * EMPUJE_CANTO
					ny += ly / norma * EMPUJE_CANTO
		if not libre and mundo.contactos(planta_id, nx, ny, radio, "paso"):
			break
		if mundo.corta(planta_id, (resultado.x, resultado.y), (nx, ny), "paso") is not None:
			break
		if not mundo.transitable(planta_id, nx, ny):
			resultado.limite = True
			break
		resultado.x, resultado.y = nx, ny
	return resultado


class Movimiento:
	"""Lleva al alumno por el mundo y cuenta lo que le pasa."""

	def __init__(self, sesion: Sesion) -> None:
		self.s = sesion
		self.mantenidas: dict[str, float] = {}
		self.eje_avance = 0.0
		self.eje_lateral = 0.0
		self.eje_giro = 0.0
		self._t_eje = 0.0
		self._resto_paso = 0.0
		self._rumbo_dicho = 0.0
		self._giro_libre = False
		self.espacio_id: str | None = None
		self.espacio_anterior: str = ""
		self.suelo = ""
		self.acustica = ""
		self.visitados: set[str] = set()
		self._ultimo_choque: tuple[str, float] = ("", -100.0)
		self._t_roce = -100.0
		self._t_limite = -100.0
		self._t_voz_limite = -100.0
		self._rumbo_marcha = sesion.jugador.rumbo
		self.en_tramo: EnTramo | None = None
		self.cabina: EstadoAscensor | None = None
		self.ascensores: dict[str, EstadoAscensor] = {
			c.id: EstadoAscensor(c) for c in sesion.mundo.entorno.conectores if c.tipo == "ascensor" and c.paradas
		}
		self._enlace_elegido: Enlace | None = None
		self._pasos_mudos = False
		self.novedad = False
		self.distancia = 0.0
		self.pasos = 0
		self.choques = 0

	# ── Entrada ──

	def orden(self, accion: str, pulsada: bool) -> bool:
		"""Atiende una orden de movimiento. Devuelve False si la acción no es de movimiento."""
		if accion not in ACCIONES_PASO and accion not in ("girar_izquierda", "girar_derecha", "media_vuelta", "interactuar"):
			return False
		if not pulsada:
			self.mantenidas.pop(accion, None)
			return True
		jugador = self.s.jugador
		if jugador.modo == "ascensor":
			self._orden_cabina(accion)
			return True
		if jugador.modo == "conector":
			self._orden_tramo(accion)
			return True
		modo = self.s.ajustes.modo_movimiento
		if accion == "interactuar":
			self.interactuar()
		elif accion == "media_vuelta":
			self.girar(180.0)
		elif modo == "brujula" and accion in RUMBOS_BRUJULA:
			jugador.rumbo = RUMBOS_BRUJULA[accion]
			self._rumbo_dicho = jugador.rumbo
			self.paso(0.0)
			self.mantenidas[accion] = RETARDO_REPETICION
		elif modo == "salas" and accion in ("avanzar", "retroceder", "girar_izquierda", "girar_derecha"):
			self._orden_salas(accion)
		elif accion in ("girar_izquierda", "girar_derecha"):
			signo = -1.0 if accion == "girar_izquierda" else 1.0
			if self.s.ajustes.giro_grados > 0:
				self.girar(signo * self.s.ajustes.giro_grados)
				self.mantenidas[accion] = RETARDO_GIRO
			else:
				self.mantenidas[accion] = 0.0
		elif modo == "aceras" and accion == "avanzar":
			self._avanzar_hasta_novedad()
		elif modo == "continuo":
			self.mantenidas[accion] = 0.0
		else:
			self.paso(ACCIONES_PASO[accion])
			self.mantenidas[accion] = RETARDO_REPETICION
		return True

	def analogico(self, avance: float, lateral: float, giro: float) -> None:
		"""Guarda la posición de las palancas (-1 a 1); se aplican en ``tic``."""
		self.eje_avance = max(-1.0, min(1.0, float(avance)))
		self.eje_lateral = max(-1.0, min(1.0, float(lateral)))
		self.eje_giro = max(-1.0, min(1.0, float(giro)))

	def soltar_todo(self) -> None:
		"""Olvida lo que se estuviera manteniendo (al pausar o recolocar)."""
		self.mantenidas.clear()
		self.eje_avance = self.eje_lateral = self.eje_giro = 0.0

	# ── Fotograma ──

	def tic(self, dt: float) -> None:
		"""Avanza lo que depende del tiempo: órdenes mantenidas, palancas, escaleras y ascensores."""
		self._tic_ascensores(dt)
		jugador = self.s.jugador
		if jugador.modo == "ascensor":
			return
		if jugador.modo == "conector":
			self._tic_tramo(dt)
			return
		ajustes = self.s.ajustes
		# Giro libre: palanca, o teclas de giro con giro_grados = 0.
		giro = self.eje_giro if abs(self.eje_giro) > ZONA_MUERTA else 0.0
		if ajustes.giro_grados <= 0:
			giro += (1.0 if "girar_derecha" in self.mantenidas else 0.0) - (1.0 if "girar_izquierda" in self.mantenidas else 0.0)
		if giro:
			jugador.rumbo = (jugador.rumbo + giro * VELOCIDAD_GIRO * dt) % 360.0
			self._giro_libre = True
		elif self._giro_libre:
			self._giro_libre = False
			if abs(geo.diferencia_rumbos(self._rumbo_dicho, jugador.rumbo)) >= 10.0:
				self._decir_rumbo()
		if ajustes.giro_grados > 0:
			for accion, signo in (("girar_izquierda", -1.0), ("girar_derecha", 1.0)):
				if accion in self.mantenidas and ajustes.modo_movimiento not in ("brujula", "salas"):
					self.mantenidas[accion] -= dt
					if self.mantenidas[accion] <= 0.0:
						self.girar(signo * ajustes.giro_grados)
						self.mantenidas[accion] = RETARDO_GIRO
		if ajustes.modo_movimiento == "continuo":
			self._tic_continuo(dt)
			return
		cadencia = max(0.25, ajustes.paso_m / max(0.2, ajustes.velocidad_ms))
		for accion in [a for a in self.mantenidas if a in ACCIONES_PASO]:
			if ajustes.modo_movimiento in ("salas", "aceras") and accion == "avanzar":
				continue
			self.mantenidas[accion] -= dt
			if self.mantenidas[accion] <= 0.0:
				self.mantenidas[accion] = cadencia
				if ajustes.modo_movimiento == "brujula" and accion in RUMBOS_BRUJULA:
					self.paso(0.0)
				else:
					self.paso(ACCIONES_PASO[accion])
				if jugador.modo != "andando":
					return
		# La palanca en un modo por pasos da pasos al ritmo de paseo mientras se inclina.
		if ajustes.modo_movimiento in ("pasos", "aceras") and (abs(self.eje_avance) > 0.5 or abs(self.eje_lateral) > 0.5):
			self._t_eje -= dt
			if self._t_eje <= 0.0:
				self._t_eje = cadencia
				if abs(self.eje_avance) >= abs(self.eje_lateral):
					self.paso(0.0 if self.eje_avance > 0 else 180.0)
				else:
					self.paso(90.0 if self.eje_lateral > 0 else -90.0)
		else:
			self._t_eje = 0.0

	def _tic_continuo(self, dt: float) -> None:
		ajustes = self.s.ajustes
		avance = (1.0 if "avanzar" in self.mantenidas else 0.0) - (0.6 if "retroceder" in self.mantenidas else 0.0)
		lateral = (FACTOR_LATERAL if "paso_derecha" in self.mantenidas else 0.0) - (
			FACTOR_LATERAL if "paso_izquierda" in self.mantenidas else 0.0
		)
		if abs(self.eje_avance) > ZONA_MUERTA:
			avance += self.eje_avance if self.eje_avance > 0 else self.eje_avance * 0.6
		if abs(self.eje_lateral) > ZONA_MUERTA:
			lateral += self.eje_lateral * FACTOR_LATERAL
		avance = max(-1.0, min(1.0, avance))
		lateral = max(-1.0, min(1.0, lateral))
		if not avance and not lateral:
			self._resto_paso = min(self._resto_paso, ajustes.paso_m * 0.5)
			return
		relativo = math.degrees(math.atan2(lateral, avance))
		fuerza = min(1.0, math.hypot(avance, lateral))
		self.desplazar(self.s.jugador.rumbo + relativo, ajustes.velocidad_ms * fuerza * dt, continuo=True)

	# ── Giros ──

	def girar(self, grados: float) -> None:
		"""Gira el cuerpo ``grados`` (positivo a la derecha) y, según el detalle, dice hacia dónde se mira."""
		jugador = self.s.jugador
		jugador.rumbo = (jugador.rumbo + grados) % 360.0
		self.s.sonar("interfaz/mover", bus="interfaz", volumen=0.5)
		self._decir_rumbo()

	def _decir_rumbo(self) -> None:
		self._rumbo_dicho = self.s.jugador.rumbo
		if self.s.ajustes.detalle >= 1:
			self.s.decir(geo.punto_cardinal(self.s.jugador.rumbo).capitalize() + ".", canal="juego", pedida=True, clave="rumbo")

	# ── Pasos ──

	def paso(self, relativo: float) -> float:
		"""Da un paso en una dirección relativa al cuerpo (0 delante, 180 atrás, ±90 de lado). Devuelve lo avanzado."""
		ajustes = self.s.ajustes
		largo = ajustes.paso_m * (FACTOR_LATERAL if abs(geo.diferencia_rumbos(0.0, relativo)) == 90.0 else 1.0)
		return self.desplazar(self.s.jugador.rumbo + relativo, largo)

	def desplazar(self, rumbo: float, metros: float, continuo: bool = False) -> float:
		"""Mueve al alumno ``metros`` hacia ``rumbo`` con colisión, y cuenta lo que pasa. Devuelve lo avanzado."""
		s = self.s
		jugador = s.jugador
		if jugador.modo != "andando" or metros <= 0.0:
			return 0.0
		rumbo %= 360.0
		self._rumbo_marcha = rumbo
		if self._entrar_en_ascensor(rumbo):
			return 0.0
		dx, dy = geo.vector_rumbo(rumbo)
		viejo = jugador.punto
		resultado = mover_circulo(s.mundo, jugador.planta, jugador.x, jugador.y, dx * metros, dy * metros, jugador.radio)
		jugador.x, jugador.y = resultado.x, resultado.y
		avanzado = math.hypot(jugador.x - viejo[0], jugador.y - viejo[1])
		progreso = (jugador.x - viejo[0]) * dx + (jugador.y - viejo[1]) * dy
		self.distancia += avanzado
		if continuo:
			self._resto_paso += avanzado
			if self._resto_paso >= s.ajustes.paso_m:
				self._resto_paso -= s.ajustes.paso_m
				self._sonar_paso()
		elif avanzado > 0.08:
			self._sonar_paso()
		if resultado.contacto is not None and resultado.punto is not None:
			self._contacto(resultado, rumbo, dx, dy, progreso, metros, continuo)
		elif resultado.limite and progreso < metros * 0.5:
			self._limite()
		if avanzado > 1e-4:
			self.tras_mover(rumbo)
		return avanzado

	def _sonar_paso(self) -> None:
		s = self.s
		jugador = s.jugador
		suelo = s.mundo.suelo_en(jugador.planta, jugador.x, jugador.y)
		nombre = ev.sonido_paso(suelo, jugador.pie_izquierdo, s.azar.randint(1, 3))
		escalera = self.escalera_de_calle()
		if escalera is not None:
			# Escaleras dibujadas como zona de la calle (mapas importados): cada paso es un peldaño.
			if escalera.datos.get("rampa"):
				peldano = "escalera/rampa"
			else:
				sube = escalera.datos.get("sube_hacia")
				bajando = isinstance(sube, (int, float)) and abs(geo.diferencia_rumbos(float(sube), self._rumbo_marcha)) > 90.0
				peldano = "escalera/bajar" if bajando else "escalera/subir"
			if not self._pasos_mudos:
				s.sonar(peldano, relativo=(0.0, 0.4), bus="pasos")
				s.vibrar("peldano")
		elif not self._pasos_mudos:
			s.sonar(nombre, relativo=(-60.0 if jugador.pie_izquierdo else 60.0, 0.3), bus="pasos", volumen=0.9)
		jugador.pie_izquierdo = not jugador.pie_izquierdo
		self.pasos += 1

	def escalera_de_calle(self, espacio: Espacio | None = None) -> Espacio | None:
		"""El espacio de tipo escalera de una planta exterior en el que está el alumno (o el dado, si lo es), o None.

		En los mapas importados unas escaleras de calle no unen dos plantas: son
		una zona más de la calle, con su ficha en ``datos``.
		"""
		s = self.s
		indice = s.mundo.planta(s.jugador.planta)
		if indice is None or not indice.planta.exterior:
			return None
		if espacio is None:
			espacio = s.mundo.espacio_en(s.jugador.planta, s.jugador.x, s.jugador.y)
		return espacio if espacio is not None and espacio.tipo == "escalera" else None

	def _frase_escalera_de_calle(self, escalera: Espacio) -> str:
		"""«Escaleras, 12 peldaños», o que el mapa no dice cuántos; con detalle, el resto de su ficha."""
		s = self.s
		datos = escalera.datos
		peldanos = datos.get("peldanos")
		if datos.get("rampa"):
			texto = _("Rampa.")
		elif isinstance(peldanos, int) and not isinstance(peldanos, bool) and peldanos > 0:
			texto = _n("Escaleras, {n} peldaño.", "Escaleras, {n} peldaños.", peldanos).format(n=peldanos)
		elif fichas.viene_de_mapa(datos):
			texto = _("Escaleras. El mapa no dice cuántos peldaños.")
		else:
			texto = _("Escaleras.")
		sube = datos.get("sube_hacia")
		if isinstance(sube, (int, float)):
			texto += " " + (_("Suben.") if abs(geo.diferencia_rumbos(float(sube), self._rumbo_marcha)) <= 90.0 else _("Bajan."))
		if s.ajustes.detalle >= 2:
			# El resto de la ficha (pasamanos, pendiente), que ya distingue «no tiene» de «el mapa no lo dice».
			resto = [linea for linea in fichas.ficha_escalera(escalera) if "peldaño" not in linea and "sube" not in linea.lower()]
			texto += " " + " ".join(resto) if resto else ""
		return texto

	def _contacto(
		self, resultado: ResultadoMovimiento, rumbo: float, dx: float, dy: float, progreso: float, metros: float, continuo: bool
	) -> None:
		"""Decide si lo tocado es un choque (de frente) o un roce (resbalando) y lo cuenta."""
		s = self.s
		jugador = s.jugador
		seg = resultado.contacto
		punto = resultado.punto
		if seg is None or punto is None:
			return
		nx, ny = jugador.x - punto[0], jugador.y - punto[1]
		norma = math.hypot(nx, ny) or 1.0
		incidencia = -(dx * nx + dy * ny) / norma
		# De frente: casi perpendicular a lo que toca, o sin haber podido avanzar apenas. Lo demás es resbalar.
		de_frente = incidencia > 0.9 or progreso < metros * 0.35
		if not de_frente:
			if s.t - self._t_roce >= ESPERA_ROCE:
				self._t_roce = s.t
				s.sonar(ev.sonido_roce(seg.material), pos=s.pos3(punto[0], punto[1], 1.0), volumen=0.7)
				lado = geo.diferencia_rumbos(jugador.rumbo, geo.rumbo_entre(jugador.punto, punto))
				s.vibrar("pared_izquierda" if lado < 0 else "pared_derecha")
			return
		if continuo and seg.elemento_id == self._ultimo_choque[0] and s.t - self._ultimo_choque[1] < 0.7:
			# Andando seguido contra lo mismo no se repite el golpe en cada fotograma.
			return
		self.choques += 1
		self.novedad = True
		golpe = ev.sonido_golpe(seg.material)
		info = s.mundo.objeto(seg.elemento_id) if seg.clase == "objeto" else None
		if info is not None and info.sonidos.get("golpe"):
			golpe = sonido_de_objeto(info, str(info.sonidos["golpe"]))
		s.sonar(golpe, pos=s.pos3(punto[0], punto[1], 1.0))
		s.vibrar("choque")
		nombre = self.nombre_obstaculo(seg)
		repetido = seg.elemento_id == self._ultimo_choque[0] and s.t - self._ultimo_choque[1] < ESPERA_VOZ_CHOQUE
		self._ultimo_choque = (seg.elemento_id, s.t)
		if s.ajustes.detalle >= 1 and not repetido:
			s.decir(s.leng.con_tono("choque", nombre + "."), canal="juego", pedida=True, clave="choque")
		if seg.clase == "objeto":
			s.percepcion.descubrir_objeto(seg.elemento_id)
		s.registrar(
			"choque",
			con=nombre,
			clase=seg.clase,
			material=seg.material,
			elemento=seg.elemento_id,
			punto=[round(punto[0], 2), round(punto[1], 2)],
		)

	def nombre_obstaculo(self, seg: Seg) -> str:
		"""Nombre breve de lo que corta el paso: «Pared», «Mesa», «Puerta cerrada»."""
		if seg.clase == "objeto":
			return seg.nombre or _("Objeto")
		if seg.clase == "puerta":
			estado = self.s.mundo.estado_abertura(seg.elemento_id)
			if self.s.ajustes.detalle >= 2 and seg.abertura is not None:
				return self.s.leng.abertura(seg.abertura, estado)
			return _("Puerta cerrada con llave") if estado == "con_llave" else _("Puerta cerrada")
		if seg.clase == "ventana":
			return seg.nombre if self.s.ajustes.detalle >= 2 and seg.nombre else _("Ventana")
		if seg.clase == "macizo":
			return seg.nombre or _("Edificio")
		return seg.nombre or _("Pared")

	def _limite(self) -> None:
		s = self.s
		self.novedad = True
		if s.t - self._t_limite < 0.3:
			return
		s.sonar("interfaz/borde", bus="interfaz")
		if s.t - self._t_voz_limite >= ESPERA_VOZ_CHOQUE:
			self._t_voz_limite = s.t
			s.decir(s.leng.tono("limite"), canal="juego", pedida=True, clave="limite")
			s.registrar("limite")
		self._t_limite = s.t

	# ── Después de moverse ──

	def tras_mover(self, rumbo: float | None = None, forzar: bool = False) -> None:
		"""Mira qué ha cambiado tras moverse: boca de escalera, espacio, suelo, avisos y descubrimientos."""
		s = self.s
		jugador = s.jugador
		if rumbo is not None and jugador.modo == "andando" and self._entrar_en_tramo(rumbo):
			return
		self._comprobar_espacio(forzar)
		s.dinamica.tras_mover()
		s.percepcion.tras_mover()
		s.gancho("tras_mover")

	def _comprobar_espacio(self, forzar: bool = False) -> None:
		s = self.s
		jugador = s.jugador
		mundo = s.mundo
		espacio = mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		nuevo_id = espacio.id if espacio is not None else ""
		suelo = mundo.suelo_en(jugador.planta, jugador.x, jugador.y)
		cambio_espacio = forzar or nuevo_id != self.espacio_id
		detalle = s.ajustes.detalle
		if cambio_espacio:
			anterior = mundo.elemento(self.espacio_id) if self.espacio_id else None
			if self.espacio_id:
				self.espacio_anterior = self.espacio_id
			self.espacio_id = nuevo_id
			self._enlace_elegido = None
			self.novedad = True
			if espacio is None:
				self._salida()
			else:
				primera = nuevo_id not in self.visitados
				self.visitados.add(nuevo_id)
				if espacio.acustica != self.acustica:
					self.acustica = espacio.acustica
					s.emitir(ev.EvAcustica(espacio.acustica))
				partes: list[str] = []
				# Entre acera y calzada (o paso de peatones) hay un bordillo; entre paso y calzada, no.
				bordillo = isinstance(anterior, Espacio) and (anterior.tipo in TIPOS_CALZADA) != (espacio.tipo in TIPOS_CALZADA)
				if bordillo:
					s.sonar("exterior/bordillo", relativo=(0.0, 0.3), bus="pasos")
					s.vibrar("peldano")
					if detalle >= 1:
						partes.append(_("Bordillo."))
				escalera = self.escalera_de_calle(espacio)
				sale_de_escalera = isinstance(anterior, Espacio) and self.escalera_de_calle(anterior) is not None and escalera is None
				if sale_de_escalera and detalle >= 1:
					partes.append(_("Fin de la rampa.") if anterior.datos.get("rampa") else _("Fin de las escaleras."))
				if escalera is not None:
					s.vibrar("peldano")
					if detalle >= 1:
						partes.append(self._frase_escalera_de_calle(escalera))
				elif espacio.datos.get("terreno_base"):
					# El «terreno sin detallar» que queda debajo de todo en un mapa importado no es un lugar: no se anuncia.
					pass
				elif detalle >= 1:
					partes.append(
						s.leng.con_tono("espacio_nuevo", s.leng.espacio(espacio) + ".") if primera else s.leng.espacio(espacio) + "."
					)
					if primera and detalle >= 2 and espacio.descripcion:
						partes.append(espacio.descripcion)
					if primera and detalle >= 2 and espacio.tipo == "acera" and espacio.datos.get("origen") == "deducida":
						partes.append(_("Esta acera no está en el mapa: se ha supuesto."))
				if detalle >= 3 and suelo != self.suelo:
					partes.append(_("Suelo de {suelo}.").format(suelo=s.leng.suelo(suelo).lower()))
				if partes:
					# Bajar a la calzada o empezar unas escaleras es cosa de seguridad: se dice ya, sin esperar turno.
					urgente = bordillo or escalera is not None or sale_de_escalera
					s.decir(
						" ".join(partes), canal="aviso" if urgente else "juego", prioridad=3 if urgente else 2, clave="espacio", caduca=8.0
					)
				s.percepcion.entrar_en_espacio(espacio, primera)
				s.registrar("entrada_espacio", espacio=nuevo_id, nombre=espacio.nombre, primera=primera, tipo=espacio.tipo)
		elif suelo != self.suelo and self.suelo:
			self.novedad = True
			if detalle >= 1:
				zona = mundo.zona_en(jugador.planta, jugador.x, jugador.y)
				sobre = mundo.objeto_de_suelo_en(jugador.planta, jugador.x, jugador.y)
				if sobre is not None and detalle >= 2:
					# Lo que cambia el suelo es un objeto (una alfombra, una tapa): se dice cuál.
					nombre = sobre.objeto.nombre or s.leng.suelo(suelo)
					s.percepcion.descubrir_objeto(sobre.objeto.id)
				else:
					nombre = zona.nombre if zona is not None and zona.nombre and detalle >= 2 else s.leng.suelo(suelo)
				s.decir(nombre + ".", canal="juego", clave="suelo", caduca=3.0)
			s.registrar("cambio_suelo", suelo=suelo, anterior=self.suelo)
		self.suelo = suelo

	def _salida(self) -> None:
		"""El alumno ha cruzado una abertura hacia fuera del entorno."""
		s = self.s
		jugador = s.jugador
		cercanas = s.mundo.aberturas_cerca(jugador.planta, jugador.x, jugador.y, 1.5)
		info = cercanas[0][1] if cercanas else None
		if self.acustica != "exterior":
			self.acustica = "exterior"
			s.emitir(ev.EvAcustica("exterior"))
		if info is not None:
			nombre = info.abertura.nombre or s.leng.abertura(info.abertura)
			s.decir(_("Has salido por {puerta}.").format(puerta=nombre), canal="juego", prioridad=3, clave="salida", caduca=8.0)
			s.registrar("salida", abertura=info.abertura.id, nombre=info.abertura.nombre, es_salida=info.abertura.es_salida)
		else:
			s.registrar("salida", abertura="", nombre="", es_salida=False)

	# ── Interactuar ──

	def interactuables(self) -> list[dict[str, Any]]:
		"""Lo que el alumno tiene al alcance de la mano, de lo más a lo menos a mano.

		Cada elemento es un diccionario con ``clase`` (abertura, parada,
		pulsador, objeto, boca), ``elemento`` (el del modelo), ``id``,
		``nombre``, ``distancia`` y ``relativo`` (grados respecto del cuerpo).
		"""
		s = self.s
		jugador = s.jugador
		mundo = s.mundo
		x, y = jugador.x, jugador.y
		lista: list[dict[str, Any]] = []

		def anotar(clase: str, elemento: Any, ident: str, nombre: str, distancia: float, punto: Punto, extra: Any = None) -> None:
			relativo = geo.diferencia_rumbos(jugador.rumbo, geo.rumbo_entre((x, y), punto)) if geo.distancia((x, y), punto) > 0.05 else 0.0
			if abs(relativo) > 100.0 and distancia > 0.6:
				# A la espalda solo cuenta lo que se está tocando: se usa lo que se tiene delante.
				return
			# Lo que queda de frente gana a lo que queda de lado aunque esté un poco más lejos.
			orden = distancia + (0.0 if abs(relativo) <= 60.0 else 0.6)
			lista.append(
				{
					"clase": clase,
					"elemento": elemento,
					"id": ident,
					"nombre": nombre,
					"distancia": distancia,
					"relativo": relativo,
					"orden": orden,
					"info": extra,
				}
			)

		for d, info in mundo.aberturas_cerca(jugador.planta, x, y, ALCANCE_MANO):
			if info.seg is not None and mundo.visible(
				jugador.planta, (x, y), geo.proyeccion_sobre_segmento((x, y), info.abertura.a, info.abertura.b), "vista"
			):
				cercano = geo.proyeccion_sobre_segmento((x, y), info.abertura.a, info.abertura.b)
				anotar("abertura", info.abertura, info.abertura.id, info.abertura.nombre, d, cercano, info)
		for d, parada in mundo.paradas_cerca(jugador.planta, x, y, RADIO_PARADA):
			anotar("parada", parada.conector, parada.conector.id, parada.conector.nombre, d, parada.punto, parada)
		for paso in s.dinamica.pulsadores_cerca(x, y, 2.0):
			anotar("pulsador", paso["espacio"], paso["espacio"].id, paso["espacio"].nombre, paso["distancia"], paso["punto"], paso)
		for d, info_objeto in mundo.objetos_cerca(jugador.planta, x, y, ALCANCE_MANO - jugador.radio + 0.2):
			cercano = min(
				(geo.proyeccion_sobre_segmento((x, y), a, b) for a, b in geo.lados(info_objeto.huella)),
				key=lambda p: geo.distancia((x, y), p),
			)
			if any(seg.clase != "objeto" for _t, seg in mundo.cortes(jugador.planta, (x, y), cercano, "paso")):
				# Queda al otro lado de una pared o de una puerta cerrada: con la mano no se llega (por encima de otro mueble, sí).
				continue
			anotar("objeto", info_objeto.objeto, info_objeto.objeto.id, info_objeto.objeto.nombre, d, cercano, info_objeto)
		for d, boca in mundo.bocas_cerca(jugador.planta, x, y, 1.6):
			anotar("boca", boca.conector, boca.conector.id, boca.conector.nombre, d, boca.punto, boca)
		lista.sort(key=lambda dato: dato["orden"])
		return lista

	def interactuar(self) -> None:
		"""Usa lo que el alumno tiene delante: abre o cierra, llama al ascensor, pulsa, acciona un objeto."""
		s = self.s
		candidatos = self.interactuables()
		elegido = candidatos[0] if candidatos else None
		hecho = False
		elemento: Any = None
		if elegido is not None:
			elemento = elegido["elemento"]
			clase = elegido["clase"]
			if clase == "abertura":
				hecho = self.usar_abertura(elegido["info"])
			elif clase == "parada":
				hecho = self._llamar_ascensor(elegido["info"])
			elif clase == "pulsador":
				hecho = s.dinamica.pulsar(elegido["info"])
			elif clase == "objeto":
				hecho = self._usar_objeto(elegido["info"])
			elif clase == "boca":
				hecho = self._describir_boca(elegido["info"])
		producidos = s.gancho("al_interactuar", elemento)
		if not hecho and not producidos:
			s.decir(s.leng.tono("nada_que_usar"), canal="juego", pedida=True, clave="interactuar")

	def usar_abertura(self, info: InfoAbertura) -> bool:
		"""Abre una puerta cerrada o cierra una abierta, con su sonido. Devuelve si había algo que hacer."""
		s = self.s
		abertura = info.abertura
		estado = s.mundo.estado_abertura(abertura.id)
		pos = s.pos3(info.centro[0], info.centro[1], 1.0)
		nombre = (abertura.nombre if s.ajustes.detalle >= 2 and abertura.nombre else "") or s.leng.abertura(abertura, "", con_nombre=False)
		if estado == "con_llave":
			s.sonar("puerta/con_llave", pos=pos)
			s.decir(_("{puerta}: cerrada con llave.").format(puerta=nombre), canal="juego", pedida=True, clave="puerta")
			s.registrar("puerta", abertura=abertura.id, accion="con_llave", nombre=abertura.nombre)
			return True
		if estado == "cerrada":
			s.mundo.poner_abertura(abertura.id, "abierta")
			s.sonar("puerta/automatica" if abertura.hoja == "automatica" else "puerta/abrir", pos=pos)
			s.decir(_("{puerta}: abierta.").format(puerta=nombre), canal="juego", pedida=True, clave="puerta")
			s.registrar("puerta", abertura=abertura.id, accion="abrir", nombre=abertura.nombre)
			return True
		jugador = s.jugador
		if info.distancia(jugador.x, jugador.y) < jugador.radio + 0.05:
			s.decir(_("Estás en medio de la puerta: apártate para cerrarla."), canal="juego", pedida=True, clave="puerta")
			return True
		s.mundo.poner_abertura(abertura.id, "cerrada")
		s.sonar("puerta/automatica" if abertura.hoja == "automatica" else "puerta/cerrar", pos=pos)
		s.decir(_("{puerta}: cerrada.").format(puerta=nombre), canal="juego", pedida=True, clave="puerta")
		s.registrar("puerta", abertura=abertura.id, accion="cerrar", nombre=abertura.nombre)
		return True

	def _usar_objeto(self, info: InfoObjeto) -> bool:
		s = self.s
		objeto = info.objeto
		estado = s.mundo.estado_objeto(objeto.id)
		s.percepcion.descubrir_objeto(objeto.id)
		# Primero lo que cambia su estado desde el actual; si no hay, un gesto suelto (pulsar un botón, tocar un piano).
		accion = next((a for a in info.acciones if a.get("de") and str(a.get("de")) == estado), None)
		if accion is None:
			accion = next((a for a in info.acciones if not a.get("de") and not a.get("a")), None)
		pos = s.pos3(objeto.x, objeto.y, min(1.2, max(0.3, objeto.alto * 0.6)))
		if accion is None:
			partes = [objeto.nombre + "."]
			if estado:
				partes[0] = _("{objeto}, {estado}.").format(objeto=objeto.nombre, estado=s.catalogo.nombre_estado(objeto.tipo, estado))
			if s.ajustes.detalle >= 2 and objeto.descripcion:
				partes.append(objeto.descripcion)
			if info.sonidos.get("uso"):
				s.sonar(sonido_de_objeto(info, str(info.sonidos["uso"])), pos=pos)
			s.decir(" ".join(partes), canal="juego", pedida=True, clave="objeto")
			s.registrar("interaccion", elemento=objeto.id, clase="objeto", nombre=objeto.nombre, accion="tocar", estado=estado)
			return True
		nuevo = str(accion.get("a") or estado)
		if (
			estado in info.paso_libre
			and nuevo not in info.paso_libre
			and info.bloquea
			and info.distancia(s.jugador.x, s.jugador.y) < s.jugador.radio
		):
			# Está dentro del torno o bajo la mampara: no se le cierra encima.
			s.decir(_("Estás en medio: apártate primero."), canal="juego", pedida=True, clave="objeto")
			return True
		s.mundo.poner_estado_objeto(objeto.id, nuevo)
		sonido = accion.get("sonido") or info.sonidos.get("uso")
		if sonido:
			s.sonar(sonido_de_objeto(info, str(sonido)), pos=pos)
		s.registrar("interaccion", elemento=objeto.id, clase="objeto", nombre=objeto.nombre, accion=str(accion.get("id")), estado=nuevo)
		if not s.dinamica.objeto_usado(info, str(accion.get("id")), nuevo):
			s.decir(
				_("{accion}: {objeto}.").format(accion=str(accion.get("nombre") or accion.get("id")), objeto=objeto.nombre),
				canal="juego",
				pedida=True,
				clave="objeto",
			)
		return True

	def _describir_boca(self, boca: Boca) -> bool:
		s = self.s
		s.decir(self._frase_tramo(boca.conector, boca.tramo, boca.sentido, completa=True), canal="juego", pedida=True, clave="boca")
		return True

	# ── Escaleras y rampas ──

	def _total_tramo(self, tramo: Tramo) -> int:
		if tramo.peldanos > 0:
			return tramo.peldanos
		return max(1, round(max(0.5, tramo.longitud_m) / self.s.ajustes.paso_m))

	def _frase_tramo(self, conector: Conector, tramo: Tramo, sentido: int, completa: bool = False) -> str:
		s = self.s
		nombre = (
			s.leng.conector(conector) if s.ajustes.detalle >= 2 or completa else (_("Rampa") if conector.tipo == "rampa" else _("Escalera"))
		)
		if tramo.peldanos > 0:
			n = tramo.peldanos
			if sentido > 0:
				cuerpo = _n("sube {n} peldaño", "sube {n} peldaños", n).format(n=n)
			else:
				cuerpo = _n("baja {n} peldaño", "baja {n} peldaños", n).format(n=n)
		else:
			cuerpo = (_("sube {distancia}") if sentido > 0 else _("baja {distancia}")).format(distancia=s.leng.distancia(tramo.longitud_m))
		texto = _("{nombre}, {cuerpo}.").format(nombre=nombre, cuerpo=cuerpo)
		pasamanos = s.leng.pasamanos(conector, sentido)
		if pasamanos:
			texto += " " + pasamanos
		if completa:
			destino = s.mundo.planta(tramo.hasta.planta if sentido > 0 else tramo.desde.planta)
			if destino is not None:
				texto += " " + _("Lleva a {planta}.").format(planta=s.leng.planta(destino.planta))
		return texto

	def _entrar_en_tramo(self, rumbo: float) -> bool:
		s = self.s
		jugador = s.jugador
		for d, boca in s.mundo.bocas_cerca(jugador.planta, jugador.x, jugador.y, RADIO_BOCA):
			radio = max(0.6, min(RADIO_BOCA, _numero(boca.conector.datos.get("anchura"), 1.0) * 0.75))
			if d > radio or abs(geo.diferencia_rumbos(rumbo, boca.rumbo)) > ANGULO_BOCA:
				continue
			conector = boca.conector
			if conector.tipo == "escalera_mecanica":
				baja = str(conector.datos.get("sentido") or "") == "baja"
				if (boca.sentido > 0) == baja:
					s.decir(
						_("Esta escalera mecánica viene hacia ti: no se puede entrar por aquí."),
						canal="aviso",
						prioridad=3,
						clave="mecanica",
						caduca=6.0,
					)
					return False
			total = self._total_tramo(boca.tramo)
			self.en_tramo = EnTramo(conector, boca.tramo, boca.sentido, 0.0 if boca.sentido > 0 else float(total), total, jugador.planta)
			jugador.modo = "conector"
			jugador.x, jugador.y = boca.x, boca.y
			jugador.rumbo = boca.rumbo
			self.mantenidas.pop("avanzar", None)
			self.novedad = True
			if "escalera" != self.acustica and conector.tipo != "rampa":
				self.acustica = "escalera"
				s.emitir(ev.EvAcustica("escalera"))
			s.decir(self._frase_tramo(conector, boca.tramo, boca.sentido), canal="juego", prioridad=3, clave="tramo", caduca=10.0)
			s.registrar(
				"conector", conector=conector.id, accion="entrar", sentido="sube" if boca.sentido > 0 else "baja", tipo=conector.tipo
			)
			return True
		return False

	def _orden_tramo(self, accion: str) -> None:
		estado = self.en_tramo
		if estado is None:
			return
		s = self.s
		mecanica = estado.conector.tipo == "escalera_mecanica"
		if accion == "avanzar":
			self._mover_en_tramo(1.0)
			self.mantenidas[accion] = RETARDO_REPETICION
		elif accion == "retroceder" and not mecanica:
			self._mover_en_tramo(-1.0)
			self.mantenidas[accion] = RETARDO_REPETICION
		elif accion == "media_vuelta" and not mecanica:
			estado.sentido = -estado.sentido
			s.jugador.rumbo = (s.jugador.rumbo + 180.0) % 360.0
			s.decir(
				_("Media vuelta. Ahora subes.") if estado.sentido > 0 else _("Media vuelta. Ahora bajas."),
				canal="juego",
				pedida=True,
				clave="tramo",
			)
		elif accion == "interactuar":
			hechos = round(estado.progreso if estado.sentido > 0 else estado.total - estado.progreso)
			s.decir(_("Llevas {n} de {total}.").format(n=hechos, total=estado.total), canal="juego", pedida=True, clave="tramo")
		else:
			s.sonar("interfaz/borde", bus="interfaz")

	def _tic_tramo(self, dt: float) -> None:
		estado = self.en_tramo
		if estado is None:
			return
		ajustes = self.s.ajustes
		largo_unidad = max(0.1, estado.tramo.longitud_m / estado.total) if estado.tramo.longitud_m > 0 else ajustes.paso_m
		if estado.conector.tipo == "escalera_mecanica":
			self._mover_en_tramo(VELOCIDAD_MECANICA * dt / largo_unidad)
			if self.en_tramo is None:
				return
		for accion, signo in (("avanzar", 1.0), ("retroceder", -1.0)):
			if accion not in self.mantenidas or self.en_tramo is None:
				continue
			if ajustes.modo_movimiento == "continuo":
				self._mover_en_tramo(signo * ajustes.velocidad_ms * 0.6 * dt / largo_unidad)
			else:
				self.mantenidas[accion] -= dt
				if self.mantenidas[accion] <= 0.0:
					self.mantenidas[accion] = max(0.3, 0.5 / max(0.2, ajustes.velocidad_ms) * 1.2)
					self._mover_en_tramo(signo)
		if self.en_tramo is not None and abs(self.eje_avance) > 0.5:
			self._mover_en_tramo((1.0 if self.eje_avance > 0 else -1.0) * ajustes.velocidad_ms * 0.6 * dt / largo_unidad)

	def _mover_en_tramo(self, unidades: float) -> None:
		"""Avanza ``unidades`` peldaños en el sentido de la marcha (negativo: hacia atrás)."""
		estado = self.en_tramo
		if estado is None:
			return
		s = self.s
		antes = estado.progreso
		estado.progreso = max(0.0, min(float(estado.total), antes + unidades * estado.sentido))
		sube = estado.progreso > antes
		# Un sonido por cada peldaño completo que se pisa.
		if sube:
			pisados = range(math.floor(antes + 1e-9) + 1, math.floor(estado.progreso + 1e-9) + 1)
		else:
			pisados = range(math.ceil(antes - 1e-9) - 1, math.ceil(estado.progreso - 1e-9) - 1, -1)
		largo_unidad = estado.tramo.longitud_m / estado.total if estado.total else 0.0
		self.distancia += abs(estado.progreso - antes) * largo_unidad
		for peldano in pisados:
			fraccion = peldano / estado.total
			if estado.conector.tipo == "escalera":
				nombre = "escalera/subir" if sube else "escalera/bajar"
			else:
				nombre = "escalera/rampa"
			s.sonar(nombre, relativo=(0.0, 0.4), bus="pasos", tono=0.8 + 0.6 * fraccion)
			s.vibrar("peldano")
			self.pasos += 1
		self._situar_en_tramo()
		if estado.progreso >= estado.total - 1e-9 and estado.sentido > 0:
			self._salir_de_tramo(arriba=True)
		elif estado.progreso <= 1e-9 and estado.sentido < 0:
			self._salir_de_tramo(arriba=False)
		elif estado.progreso <= 1e-9 and unidades < 0:
			# Ha desandado hasta la boca de abajo andando hacia atrás.
			self._salir_de_tramo(arriba=False, de_espaldas=True)
		elif estado.progreso >= estado.total - 1e-9 and unidades < 0:
			self._salir_de_tramo(arriba=True, de_espaldas=True)

	def _situar_en_tramo(self) -> None:
		estado = self.en_tramo
		if estado is None:
			return
		s = self.s
		jugador = s.jugador
		tramo = estado.tramo
		fraccion = estado.progreso / estado.total if estado.total else 0.0
		jugador.x = tramo.desde.x + (tramo.hasta.x - tramo.desde.x) * fraccion
		jugador.y = tramo.desde.y + (tramo.hasta.y - tramo.desde.y) * fraccion
		abajo, arriba = s.mundo.altura(tramo.desde.planta), s.mundo.altura(tramo.hasta.planta)
		cota = abajo + (arriba - abajo) * fraccion
		jugador.planta = tramo.desde.planta if fraccion < 0.5 else tramo.hasta.planta
		jugador.z_extra = cota - s.mundo.altura(jugador.planta)
		base = tramo.desde.rumbo if fraccion < 0.5 else tramo.hasta.rumbo
		jugador.rumbo = base % 360.0 if estado.sentido > 0 else (base + 180.0) % 360.0

	def _salir_de_tramo(self, arriba: bool, de_espaldas: bool = False) -> None:
		estado = self.en_tramo
		if estado is None:
			return
		s = self.s
		jugador = s.jugador
		tramo = estado.tramo
		destino = tramo.hasta if arriba else tramo.desde
		jugador.planta = destino.planta
		jugador.x, jugador.y = destino.x, destino.y
		jugador.z_extra = 0.0
		jugador.rumbo = destino.rumbo % 360.0 if arriba else (destino.rumbo + 180.0) % 360.0
		if de_espaldas:
			jugador.rumbo = (jugador.rumbo + 180.0) % 360.0
		jugador.modo = "andando"
		self.en_tramo = None
		self.mantenidas.pop("avanzar", None)
		self.mantenidas.pop("retroceder", None)
		self.novedad = True
		planta = s.mundo.planta(destino.planta)
		nombre = s.leng.planta(planta.planta if planta is not None else None)
		if destino.planta != estado.planta_origen:
			texto = _("Has llegado a {planta}.").format(planta=nombre)
			s.registrar("cambio_planta", de=estado.planta_origen, a=destino.planta, conector=estado.conector.id, tipo=estado.conector.tipo)
		else:
			texto = _("Has vuelto a {planta}.").format(planta=nombre)
		s.decir(s.leng.con_tono("llegada", texto), canal="juego", prioridad=3, clave="tramo", caduca=10.0)
		s.registrar("conector", conector=estado.conector.id, accion="salir", tipo=estado.conector.tipo)
		# Acaba de usarla: no hace falta avisarle de que tiene una escalera al lado.
		s.percepcion.dar_por_avisado(("boca", estado.conector.id, 1))
		s.percepcion.dar_por_avisado(("boca", estado.conector.id, -1))
		self.espacio_id = None
		self.tras_mover(None, forzar=True)

	# ── Ascensor ──

	def _parada_actual(self, estado: EstadoAscensor) -> InfoParada | None:
		for indice in self.s.mundo.plantas():
			for parada in indice.paradas:
				if parada.conector is estado.conector and parada.indice == estado.en_parada:
					return parada
		return None

	def _nivel_parada(self, conector: Conector, numero: int) -> int:
		planta = self.s.mundo.planta(conector.paradas[numero].planta)
		return planta.planta.nivel if planta is not None else numero

	def _nombre_parada(self, conector: Conector, numero: int) -> str:
		planta = self.s.mundo.planta(conector.paradas[numero].planta)
		return self.s.leng.planta(planta.planta if planta is not None else None)

	def _sonar_en_parada(self, estado: EstadoAscensor, nombre: str) -> None:
		"""Hace sonar algo en la puerta del ascensor, si el alumno está en esa planta para oírlo."""
		s = self.s
		parada = self._parada_actual(estado)
		if parada is not None and parada.parada.planta == s.jugador.planta:
			s.sonar(nombre, pos=s.pos3(parada.parada.puerta.x, parada.parada.puerta.y, 1.2))

	def _llamar_ascensor(self, parada: InfoParada) -> bool:
		s = self.s
		estado = self.ascensores.get(parada.conector.id)
		if estado is None:
			return False
		nombre = s.leng.conector(parada.conector)
		if estado.estado == "abierto" and estado.en_parada == parada.indice:
			s.decir(
				_("{ascensor}: la puerta está abierta. Avanza hacia ella para entrar.").format(ascensor=nombre),
				canal="juego",
				pedida=True,
				clave="ascensor",
			)
			return True
		if estado.estado == "viniendo":
			s.decir(_("{ascensor}: ya viene.").format(ascensor=nombre), canal="juego", pedida=True, clave="ascensor")
			return True
		s.sonar("ascensor/llamada", pos=s.pos3(parada.parada.puerta.x, parada.parada.puerta.y, 1.2))
		niveles = abs(self._nivel_parada(parada.conector, estado.en_parada) - self._nivel_parada(parada.conector, parada.indice))
		estado.estado = "viniendo"
		estado.destino = parada.indice
		estado.t = 1.0 + 1.5 * niveles
		s.decir(_("{ascensor} llamado. Espera.").format(ascensor=nombre), canal="juego", pedida=True, clave="ascensor")
		s.registrar("ascensor", conector=parada.conector.id, accion="llamar", espera=round(estado.t, 1))
		return True

	def _tic_ascensores(self, dt: float) -> None:
		s = self.s
		for estado in self.ascensores.values():
			if estado.estado == "reposo":
				continue
			estado.t -= dt
			if estado.t > 0.0:
				continue
			if estado.estado == "viniendo":
				estado.en_parada = estado.destino
				estado.estado = "abierto"
				estado.t = 15.0
				self._sonar_en_parada(estado, "ascensor/llegada")
				self._sonar_en_parada(estado, "ascensor/puerta")
				parada = self._parada_actual(estado)
				if parada is not None and parada.parada.planta == s.jugador.planta:
					s.decir(
						_("El ascensor ha llegado. Avanza hacia la puerta para entrar."),
						canal="juego",
						prioridad=3,
						clave="ascensor",
						caduca=12.0,
					)
			elif estado.estado == "abierto":
				if self.cabina is estado:
					estado.t = 1.0
					continue
				estado.estado = "reposo"
				self._sonar_en_parada(estado, "ascensor/puerta")
				parada = self._parada_actual(estado)
				if s.ajustes.detalle >= 2 and parada is not None and parada.parada.planta == s.jugador.planta:
					if math.hypot(parada.punto[0] - s.jugador.x, parada.punto[1] - s.jugador.y) < 4.0:
						s.decir(_("Se cierra la puerta del ascensor."), canal="juego", clave="ascensor", caduca=4.0)
			elif estado.estado == "viajando":
				self._llegar_en_ascensor(estado)

	def _entrar_en_ascensor(self, rumbo: float) -> bool:
		s = self.s
		jugador = s.jugador
		for _d, parada in s.mundo.paradas_cerca(jugador.planta, jugador.x, jugador.y, RADIO_PARADA):
			estado = self.ascensores.get(parada.conector.id)
			if estado is None or estado.estado != "abierto" or estado.en_parada != parada.indice:
				continue
			if abs(geo.diferencia_rumbos(rumbo, parada.parada.puerta.rumbo)) > 60.0:
				continue
			self.cabina = estado
			estado.seleccion = estado.en_parada
			estado.mirando_fuera = False
			jugador.modo = "ascensor"
			jugador.x, jugador.y = parada.punto
			jugador.rumbo = parada.parada.puerta.rumbo % 360.0
			self.mantenidas.clear()
			self.novedad = True
			self._sonar_paso()
			if self.acustica != "seca":
				self.acustica = "seca"
				s.emitir(ev.EvAcustica("seca"))
			s.decir(
				_(
					"Estás dentro del ascensor. Elige planta con girar a la izquierda o a la derecha y acepta con interactuar. {planta}."
				).format(planta=self._nombre_parada(estado.conector, estado.seleccion)),
				canal="juego",
				prioridad=3,
				clave="ascensor",
				caduca=12.0,
			)
			s.registrar("ascensor", conector=estado.conector.id, accion="entrar")
			return True
		return False

	def _orden_cabina(self, accion: str) -> None:
		s = self.s
		estado = self.cabina
		if estado is None:
			return
		if estado.estado == "viajando":
			if accion == "interactuar":
				s.decir(_("El ascensor está en marcha."), canal="juego", pedida=True, clave="ascensor")
			return
		paradas = estado.conector.paradas
		if accion in ("girar_izquierda", "girar_derecha"):
			nueva = estado.seleccion + (1 if accion == "girar_derecha" else -1)
			if nueva < 0 or nueva >= len(paradas):
				s.sonar("interfaz/borde", bus="interfaz")
				return
			estado.seleccion = nueva
			s.sonar("interfaz/mover", bus="interfaz")
			s.decir(self._nombre_parada(estado.conector, nueva) + ".", canal="juego", pedida=True, clave="ascensor")
		elif accion == "interactuar":
			if estado.seleccion == estado.en_parada:
				s.decir(
					_("Ya estás en {planta}. Avanza para salir.").format(planta=self._nombre_parada(estado.conector, estado.en_parada)),
					canal="juego",
					pedida=True,
					clave="ascensor",
				)
				estado.mirando_fuera = True
				s.jugador.rumbo = (paradas[estado.en_parada].puerta.rumbo + 180.0) % 360.0
				return
			niveles = abs(self._nivel_parada(estado.conector, estado.en_parada) - self._nivel_parada(estado.conector, estado.seleccion))
			estado.estado = "viajando"
			estado.destino = estado.seleccion
			estado.t = 2.0 + 2.5 * niveles
			s.sonar("ascensor/puerta", relativo=(0.0, 1.0))
			s.decir(
				_("Vas a {planta}.").format(planta=self._nombre_parada(estado.conector, estado.seleccion)),
				canal="juego",
				pedida=True,
				clave="ascensor",
			)
			s.registrar(
				"ascensor",
				conector=estado.conector.id,
				accion="viajar",
				de=paradas[estado.en_parada].planta,
				a=paradas[estado.destino].planta,
				duracion=round(estado.t, 1),
			)
		elif accion == "media_vuelta":
			estado.mirando_fuera = not estado.mirando_fuera
			s.jugador.rumbo = (s.jugador.rumbo + 180.0) % 360.0
			s.decir(
				_("Miras a la puerta.") if estado.mirando_fuera else _("Miras al fondo de la cabina."),
				canal="juego",
				pedida=True,
				clave="ascensor",
			)
		elif (accion == "avanzar" and estado.mirando_fuera) or (accion == "retroceder" and not estado.mirando_fuera):
			self._salir_del_ascensor(estado)
		elif accion in ("avanzar", "retroceder"):
			s.sonar(ev.sonido_golpe("metal"), relativo=(0.0 if accion == "avanzar" else 180.0, 0.5), volumen=0.6)
			s.decir(
				_("Pared de la cabina. La puerta está detrás de ti.")
				if accion == "avanzar"
				else _("Pared de la cabina. La puerta está delante."),
				canal="juego",
				pedida=True,
				clave="ascensor",
			)

	def _llegar_en_ascensor(self, estado: EstadoAscensor) -> None:
		s = self.s
		jugador = s.jugador
		conector = estado.conector
		origen = conector.paradas[estado.en_parada].planta
		estado.en_parada = estado.destino
		estado.estado = "abierto"
		estado.t = 15.0
		if self.cabina is not estado:
			return
		parada = conector.paradas[estado.en_parada]
		jugador.planta = parada.planta
		jugador.x, jugador.y = parada.puerta.x, parada.puerta.y
		jugador.rumbo = (parada.puerta.rumbo + 180.0) % 360.0
		estado.mirando_fuera = True
		s.sonar("ascensor/llegada", relativo=(0.0, 1.0))
		nivel = self._nivel_parada(conector, estado.en_parada)
		nombre = self._nombre_parada(conector, estado.en_parada)
		if conector.datos.get("aviso_hablado") and 0 <= nivel <= 9:
			s.sonar(f"ascensor/planta_{nivel}", relativo=(0.0, 1.0), retardo=0.5)
		s.sonar("ascensor/puerta", relativo=(0.0, 1.0), retardo=1.0)
		if conector.datos.get("aviso_hablado"):
			texto = _("{planta}. Puerta abierta. Avanza para salir.").format(planta=nombre)
		else:
			texto = _("El ascensor se ha parado. Puerta abierta. Avanza para salir.")
		s.decir(texto, canal="juego", prioridad=3, clave="ascensor", caduca=15.0)
		s.registrar("cambio_planta", de=origen, a=parada.planta, conector=conector.id, tipo="ascensor")

	def _salir_del_ascensor(self, estado: EstadoAscensor) -> None:
		s = self.s
		jugador = s.jugador
		parada = estado.conector.paradas[estado.en_parada]
		jugador.modo = "andando"
		jugador.planta = parada.planta
		jugador.x, jugador.y = parada.puerta.x, parada.puerta.y
		jugador.rumbo = (parada.puerta.rumbo + 180.0) % 360.0
		self.cabina = None
		estado.t = 6.0
		self.mantenidas.clear()
		self._sonar_paso()
		s.registrar("ascensor", conector=estado.conector.id, accion="salir")
		s.percepcion.dar_por_avisado(("parada", estado.conector.id, jugador.planta))
		self.espacio_id = None
		self.tras_mover(None, forzar=True)

	def fuentes(self) -> list[ev.FuenteActiva]:
		"""Sonidos continuos del propio movimiento: el ascensor en marcha, o viniendo tras llamarlo."""
		s = self.s
		estado = self.cabina
		if estado is not None:
			if estado.estado != "viajando":
				return []
			x, y, z, _rumbo = s.oyente()
			return [ev.FuenteActiva("ascensor-viaje", "ascensor/viaje", (x, y, z), volumen=0.8, bucle=True, eco=False, bus="efectos")]
		lista: list[ev.FuenteActiva] = []
		for ascensor in self.ascensores.values():
			if ascensor.estado != "viniendo":
				continue
			parada = ascensor.conector.paradas[ascensor.destino]
			if parada.planta == s.jugador.planta and math.hypot(parada.puerta.x - s.jugador.x, parada.puerta.y - s.jugador.y) < 8.0:
				# Mientras se espera se oye la maquinaria tras la puerta: así se sabe que la llamada ha funcionado.
				lista.append(
					ev.FuenteActiva(
						f"ascensor-viene:{ascensor.conector.id}",
						"ascensor/viaje",
						s.pos3(parada.puerta.x, parada.puerta.y, 1.2),
						volumen=0.45,
						filtro=0.6,
						bus="efectos",
					)
				)
		return lista

	# ── Modo por salas ──

	def _enlaces_actuales(self) -> list[Enlace]:
		s = self.s
		jugador = s.jugador
		if not self.espacio_id:
			return []
		enlaces = [e for e in s.nav.enlaces(self.espacio_id) if e.punto[0] == jugador.planta]
		# En el orden de las agujas del reloj, empezando por lo que queda delante.
		enlaces.sort(key=lambda e: geo.diferencia_rumbos(jugador.rumbo, geo.rumbo_entre(jugador.punto, e.punto[1:])) % 360.0)
		return enlaces

	def _nombre_enlace(self, enlace: Enlace) -> str:
		s = self.s
		destino = s.mundo.elemento(enlace.destino) if enlace.destino else None
		nombre_destino = s.leng.espacio(destino) if isinstance(destino, Espacio) else _("fuera")
		if enlace.tipo == "abertura":
			info = s.mundo.abertura(enlace.id)
			if info is not None:
				tipo = s.leng.abertura(info.abertura, s.mundo.estado_abertura(enlace.id), con_nombre=False)
				return _("{puerta}, hacia {destino}").format(puerta=tipo, destino=nombre_destino)
		if enlace.tipo == "conector":
			return _("{conector}, hacia {destino}").format(conector=enlace.nombre or _("Conector"), destino=nombre_destino)
		return nombre_destino

	def _orden_salas(self, accion: str) -> None:
		s = self.s
		jugador = s.jugador
		enlaces = self._enlaces_actuales()
		if not enlaces:
			s.decir(_("Desde aquí no se puede pasar a ningún otro sitio."), canal="juego", pedida=True, clave="salas")
			return
		if accion in ("girar_izquierda", "girar_derecha"):
			actual = self._enlace_elegido
			posicion = next(
				(i for i, e in enumerate(enlaces) if actual is not None and e.id == actual.id and e.destino == actual.destino), -1
			)
			if posicion < 0:
				posicion = 0 if accion == "girar_derecha" else len(enlaces) - 1
			else:
				posicion = (posicion + (1 if accion == "girar_derecha" else -1)) % len(enlaces)
			elegido = enlaces[posicion]
			self._enlace_elegido = elegido
			jugador.rumbo = (
				geo.rumbo_entre(jugador.punto, elegido.punto[1:])
				if geo.distancia(jugador.punto, elegido.punto[1:]) > 0.05
				else jugador.rumbo
			)
			s.sonar("interfaz/mover", bus="interfaz")
			s.decir(
				_("{salida}, {direccion}.").format(salida=self._nombre_enlace(elegido), direccion=s.leng.al_cardinal(jugador.rumbo)),
				canal="juego",
				pedida=True,
				clave="salas",
			)
			return
		if accion == "retroceder":
			elegido = next((e for e in enlaces if e.destino == self.espacio_anterior), None)
			if elegido is None:
				s.sonar("interfaz/borde", bus="interfaz")
				return
		else:
			elegido = self._enlace_elegido
			if elegido is None or all(e.id != elegido.id or e.destino != elegido.destino for e in enlaces):
				delante = [
					e for e in enlaces if abs(geo.diferencia_rumbos(jugador.rumbo, geo.rumbo_entre(jugador.punto, e.punto[1:]))) <= 60.0
				]
				if not delante:
					s.decir(
						_("Elige primero una salida con girar a la izquierda o a la derecha."), canal="juego", pedida=True, clave="salas"
					)
					return
				elegido = delante[0]
		self._cruzar_enlace(elegido)

	def _cruzar_enlace(self, enlace: Enlace) -> None:
		s = self.s
		jugador = s.jugador
		if enlace.tipo == "abertura":
			info = s.mundo.abertura(enlace.id)
			if info is not None and info.seg is not None:
				estado = s.mundo.estado_abertura(enlace.id)
				if estado != "abierta":
					self.usar_abertura(info)
					if estado == "con_llave":
						return
		origen = jugador.punto
		if enlace.tipo == "conector":
			conector = s.mundo.elemento(enlace.id)
			sube = s.mundo.altura(enlace.punto_destino[0]) > s.mundo.altura(jugador.planta)
			s.sonar(
				"ascensor/viaje"
				if isinstance(conector, Conector) and conector.tipo == "ascensor"
				else ("escalera/subir" if sube else "escalera/bajar"),
				relativo=(0.0, 0.5),
				bus="pasos",
			)
			s.registrar(
				"cambio_planta",
				de=jugador.planta,
				a=enlace.punto_destino[0],
				conector=enlace.id,
				tipo=conector.tipo if isinstance(conector, Conector) else "",
			)
			if isinstance(conector, Conector) and conector.tramos:
				self.distancia += conector.tramos[0].longitud_m
		else:
			jugador.rumbo = geo.rumbo_entre(enlace.punto[1:], enlace.punto_destino[1:])
			self.distancia += geo.distancia(origen, enlace.punto_destino[1:])
		jugador.planta, jugador.x, jugador.y = enlace.punto_destino
		self._sonar_paso()
		self._enlace_elegido = None
		self.tras_mover(None)

	# ── Modo por aceras ──

	def _avanzar_hasta_novedad(self) -> None:
		"""Camina recto hasta que pase algo que merezca pararse (o hasta un tope de pasos)."""
		s = self.s
		inicio = self.distancia
		for numero in range(MAX_PASOS_ACERA):
			self.novedad = False
			avisos_antes = s.percepcion.avisos_dados
			# Solo suenan los primeros pasos: ochenta pasos de golpe serían ruido.
			self._pasos_mudos = numero >= 3
			avanzado = self.paso(0.0)
			if (
				avanzado < s.ajustes.paso_m * 0.3
				or self.novedad
				or s.percepcion.avisos_dados != avisos_antes
				or s.jugador.modo != "andando"
			):
				break
		self._pasos_mudos = False
		recorrido = self.distancia - inicio
		if recorrido >= s.ajustes.paso_m * 1.5:
			s.decir(
				_("Has avanzado {distancia}.").format(distancia=s.leng.distancia(recorrido)), canal="juego", prioridad=3, clave="avance"
			)


def _numero(valor: Any, defecto: float) -> float:
	"""Un dato libre del modelo como número; el valor por defecto si no lo es."""
	try:
		return float(valor)
	except TypeError, ValueError:
		return defecto


def sonido_de_objeto(info: InfoObjeto, nombre: str) -> str:
	"""Nombre con el que el banco de sonidos encuentra un sonido declarado por un objeto.

	Un fichero del complemento (lleva extensión o empieza por ``sonidos/``) se
	pide como ``<complemento>/<fichero>``; cualquier otro nombre es de serie.
	"""
	if info.definicion is not None and catalogo.es_sonido_de_complemento(nombre):
		return catalogo.clave_de_sonido(info.definicion.complemento, nombre)
	return ev.sonido_de_serie(nombre)
