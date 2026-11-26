"""Lo que se mueve o cambia solo: semáforos, tráfico, puertas automáticas y objetos con fases.

- **Semáforos.** Cada paso de peatones con semáforo recorre sus fases (verde
  para peatones, intermitente, rojo) con los tiempos de su ``ciclo``. Si es
  sonoro, sus postes suenan distinto en cada fase; si tiene pulsador, pulsarlo
  acorta la espera.
- **Tráfico.** Por cada vía circulan vehículos (fuentes de sonido móviles)
  con la intensidad de su ``trafico`` y en su sentido. Paran en rojo, ceden
  el paso en los pasos sin semáforo y frenan si el alumno está en la calzada.
- **Cruzar mal no «mata».** Si el alumno cruza con coches pasando, recibe un
  aviso educativo («Has cruzado con coches pasando») y queda registrado; el
  juego sigue. Cada cruce de calzada deja además un registro con si fue
  seguro, para la actividad «cruza con el pitido».
- **Puertas automáticas**: se abren al acercarse y se cierran al alejarse.
- **Objetos con ``dinamica``**: recorren las fases que declara su ficha
  (``{"fases": [{"estado": "encendido", "s": 5, "sonido": "..."}]}``).

Todo usa el generador de azar de la sesión: con la misma semilla, el tráfico
es idéntico.
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.core.i18n import _
from app.dominio import geometria as geo
from app.dominio.geometria import Punto
from app.dominio.modelo import Espacio, Referencia, Via
from app.motor.acustica import Emisor
from app.motor.movimiento import sonido_de_objeto
from app.motor.mundo import TIPOS_CALZADA, InfoAbertura, InfoObjeto

if TYPE_CHECKING:
	from app.motor.sesion import Sesion

log = logging.getLogger(__name__)

FASES_SEMAFORO: tuple[str, ...] = ("verde", "intermitente", "rojo")
CICLO_SERIE: dict[str, float] = {"verde_peatones_s": 25.0, "intermitente_s": 5.0, "rojo_peatones_s": 45.0}
# Segundos entre vehículos de un sentido, de media, para cada nivel de tráfico.
INTERVALO_TRAFICO: tuple[float, ...] = (0.0, 18.0, 9.0, 4.5)
AMBIENTE_TRAFICO: tuple[str, ...] = ("", "trafico/ambiente_leve", "trafico/ambiente_medio", "trafico/ambiente_intenso")
TIPOS_VEHICULO: tuple[tuple[str, float], ...] = (("trafico/coche", 0.75), ("trafico/moto", 0.12), ("trafico/autobus", 0.13))
SEPARACION = 7.0
FRENADA = 3.0
ACELERACION = 2.0
DISTANCIA_PARAR_AUTOMATICA = 2.0
DISTANCIA_CERRAR_AUTOMATICA = 3.2
ESPERA_TRAS_PULSAR = 4.0


@dataclass
class Semaforo:
	"""El semáforo de un paso de peatones."""

	paso: Espacio
	planta_id: str
	duraciones: tuple[float, float, float]
	t: float = 0.0
	postes: list[Punto] = field(default_factory=list)
	sonoro: bool = False
	pulsador: bool = False
	# Hay semáforos puestos como objetos junto al paso que suenan (o se pulsan) por él: sus postes callan.
	suenan_objetos: bool = False
	pulsan_objetos: bool = False

	@property
	def ciclo(self) -> float:
		"""Segundos del ciclo completo."""
		return sum(self.duraciones)

	@property
	def fase(self) -> str:
		"""Fase actual para los peatones: verde, intermitente o rojo."""
		resto = self.t % self.ciclo
		for nombre, duracion in zip(FASES_SEMAFORO, self.duraciones, strict=True):
			if resto < duracion:
				return nombre
			resto -= duracion
		return "rojo"

	@property
	def restante(self) -> float:
		"""Segundos que le quedan a la fase actual."""
		resto = self.t % self.ciclo
		for duracion in self.duraciones:
			if resto < duracion:
				return duracion - resto
			resto -= duracion
		return 0.0

	@property
	def pasan_coches(self) -> bool:
		"""Si los vehículos tienen paso (rojo para los peatones)."""
		return self.fase == "rojo"


@dataclass
class Vehiculo:
	"""Un vehículo que recorre una vía.

	``frena_por_alumno`` se pone cuando el alumno le obliga a frenar de golpe
	o cuando le pasa por al lado en marcha: es lo que hace inseguro un cruce.
	"""

	id: str
	via: Via
	planta_id: str
	sentido: int  # +1 del inicio al fin del eje, -1 al revés
	d: float  # metros recorridos desde su extremo de entrada
	v: float
	v_max: float
	sonido: str
	lateral: float
	x: float = 0.0
	y: float = 0.0
	rumbo: float = 0.0
	frena_por_alumno: bool = False


@dataclass
class _Cruce:
	"""El alumno está cruzando una calzada."""

	t0: float
	via_id: str
	origen: str
	paso_id: str = ""
	fase: str = ""
	inseguro: bool = False


@dataclass
class _Fases:
	"""Un objeto que recorre fases declaradas en su ficha."""

	info: InfoObjeto
	fases: list[dict[str, Any]]
	numero: int = 0
	t: float = 0.0
	# Lo propio de un semáforo declarado como objeto de un complemento.
	para: str = ""
	pulsador: bool = False
	espera_tras_pulsar: float = ESPERA_TRAS_PULSAR
	volumen: float = 0.6
	radio: float = 10.0
	paso_id: str = ""
	maestro: _Fases | None = None
	sigue: Semaforo | None = None

	@property
	def estado(self) -> str:
		"""Estado de la fase actual."""
		return str(self.fases[self.numero].get("estado") or "")

	@property
	def restante(self) -> float:
		"""Segundos que le quedan a la fase actual."""
		return max(0.0, _segundos(self.fases[self.numero]) - self.t)


@dataclass
class _Temporizador:
	"""Un objeto que vuelve solo a otro estado cuando lleva un tiempo en uno (una lavadora que termina)."""

	info: InfoObjeto
	estado: str
	segundos: float
	al_terminar: str
	sonido: str = ""
	t: float = 0.0


@dataclass
class _ViaPlanta:
	"""Lo que no cambia de una vía durante la partida, calculado una vez: su largo y los pasos de peatones que la cruzan.

	``pasos`` son (paso, ancho, línea de parada por sentido +1 y por sentido
	-1, sin el ancho), lo mismo que antes se recalculaba por cada vehículo y
	fotograma.
	"""

	via: Via
	largo: float
	caja: tuple[float, float, float, float] = (0.0, 0.0, 0.0, 0.0)
	pasos: list[tuple[Espacio, float, float, float]] = field(default_factory=list)


@dataclass
class _TraficoPlanta:
	"""El tráfico de una planta preparado (se rehace si la planta se vuelve a indexar)."""

	indice: Any
	vias: list[Via]
	pasos: list[Espacio]
	datos: dict[int, _ViaPlanta]


def _numero(valor: Any, defecto: float) -> float:
	"""Un dato libre de una ficha como número; el valor por defecto si no lo es."""
	try:
		return float(valor)
	except TypeError, ValueError:
		return defecto


def _segundos(fase: dict[str, Any]) -> float:
	for clave in ("s", "segundos", "duracion"):
		if clave in fase:
			try:
				return max(0.2, float(fase[clave]))
			except TypeError, ValueError:
				return 5.0
	return 5.0


class Dinamica:
	"""Semáforos, tráfico, puertas automáticas y objetos con fases."""

	def __init__(self, sesion: Sesion) -> None:
		self.s = sesion
		self.semaforos: dict[str, Semaforo] = {}
		self.vehiculos: list[Vehiculo] = []
		self._numero_vehiculo = 0
		self._esperas: dict[tuple[str, int], float] = {}
		self._automaticas: list[tuple[InfoAbertura, str]] = []
		self._t_automaticas = 0.0
		self._fases: list[_Fases] = []
		self._temporizadores: list[_Temporizador] = []
		self._semaforos_objeto: dict[str, _Fases] = {}
		self._cruce: _Cruce | None = None
		self._planta_trafico = ""
		self._trafico_planta: _TraficoPlanta | None = None
		self._preparar()

	# ── Preparación ──

	def _preparar(self) -> None:
		s = self.s
		for indice in s.mundo.plantas():
			planta = indice.planta
			for _caja, espacio in indice.espacios:
				if espacio.tipo != "paso_peatones" or not espacio.datos.get("semaforo"):
					continue
				ciclo = espacio.datos.get("ciclo") if isinstance(espacio.datos.get("ciclo"), dict) else {}
				duraciones: list[float] = []
				for clave, serie in CICLO_SERIE.items():
					try:
						duraciones.append(max(1.0, float(ciclo.get(clave, serie))))
					except TypeError, ValueError:
						duraciones.append(serie)
				semaforo = Semaforo(
					paso=espacio,
					planta_id=planta.id,
					duraciones=(duraciones[0], duraciones[1], duraciones[2]),
					sonoro=bool(espacio.datos.get("sonoro")),
					pulsador=bool(espacio.datos.get("pulsador")),
				)
				semaforo.t = s.azar.uniform(0.0, semaforo.ciclo)
				semaforo.postes = self._postes(espacio)
				self.semaforos[espacio.id] = semaforo
			for info in indice.aberturas:
				if info.seg is not None and info.abertura.hoja == "automatica" and s.mundo.estado_abertura(info.abertura.id) != "con_llave":
					self._automaticas.append((info, s.mundo.estado_abertura(info.abertura.id)))
			for info_objeto in indice.objetos:
				dinamica = info_objeto.dinamica
				if not dinamica:
					continue
				if dinamica.get("tipo") == "temporizador":
					if dinamica.get("estado") and dinamica.get("al_terminar"):
						self._temporizadores.append(
							_Temporizador(
								info_objeto,
								str(dinamica["estado"]),
								_numero(dinamica.get("segundos"), 60.0),
								str(dinamica["al_terminar"]),
								str(dinamica.get("sonido_al_terminar") or ""),
							)
						)
					continue
				# Semáforo (o cualquier objeto con fases): las recorre en orden y vuelve a empezar.
				fases = dinamica.get("fases") or dinamica.get("ciclo")
				if isinstance(fases, list):
					validas = [f for f in fases if isinstance(f, dict)]
					if validas:
						desfase = s.azar.uniform(0.0, _segundos(validas[0]))
						ciclo = _Fases(
							info_objeto,
							validas,
							0,
							desfase,
							para=str(dinamica.get("para") or ""),
							pulsador=bool(dinamica.get("pulsador")),
							espera_tras_pulsar=_numero(dinamica.get("espera_tras_pulsar_s"), ESPERA_TRAS_PULSAR),
							volumen=max(0.0, min(1.0, _numero(dinamica.get("volumen"), 0.6))),
							radio=max(1.0, _numero(dinamica.get("radio"), 10.0)),
						)
						self._fases.append(ciclo)
						if validas[0].get("estado"):
							s.mundo.poner_estado_objeto(info_objeto.objeto.id, str(validas[0]["estado"]))
						if dinamica.get("tipo") == "semaforo" and ciclo.para != "vehiculos":
							self._enlazar_semaforo(indice, ciclo)

	def _enlazar_semaforo(self, indice: Any, ciclo: _Fases) -> None:
		"""Une un semáforo de peatones puesto como objeto con el paso de peatones que tiene al lado.

		Así manda sobre el tráfico de ese paso igual que un semáforo declarado en
		los datos del paso. Si el paso ya tiene el suyo en sus datos, manda ese.
		Los dos postes de un mismo paso van a la vez: el segundo sigue al primero.
		"""
		objeto = ciclo.info.objeto
		mejor: tuple[float, Espacio] | None = None
		for _caja, espacio in indice.espacios:
			if espacio.tipo != "paso_peatones":
				continue
			d = geo.distancia_punto_poligono((objeto.x, objeto.y), espacio.contorno)
			if d <= 4.0 and (mejor is None or d < mejor[0]):
				mejor = (d, espacio)
		if mejor is None:
			return
		ciclo.paso_id = mejor[1].id
		propio = self.semaforos.get(ciclo.paso_id)
		if propio is not None:
			# El paso ya tiene semáforo en sus datos: el objeto es su poste y va con él (mismas fases, a la vez).
			ciclo.sigue = propio
			propio.suenan_objetos = propio.suenan_objetos or any(f.get("sonido") for f in ciclo.fases)
			propio.pulsan_objetos = propio.pulsan_objetos or ciclo.pulsador
			return
		primero = self._semaforos_objeto.get(ciclo.paso_id)
		if primero is None:
			self._semaforos_objeto[ciclo.paso_id] = ciclo
		elif len(primero.fases) == len(ciclo.fases):
			ciclo.maestro = primero
			ciclo.numero, ciclo.t = primero.numero, primero.t

	def _postes(self, paso: Espacio) -> list[Punto]:
		"""Dónde están los postes del semáforo de un paso: sus referencias, o sus extremos si no las tiene."""
		postes: list[Punto] = []
		for referencia_id in paso.datos.get("referencias") or []:
			referencia = self.s.mundo.elemento(str(referencia_id))
			if isinstance(referencia, Referencia):
				postes.append((referencia.x, referencia.y))
		if postes:
			return postes
		for extremo in paso.datos.get("extremos") or []:
			try:
				postes.append((float(extremo[0]), float(extremo[1])))
			except TypeError, ValueError, IndexError:
				continue
		return postes or [paso.centro()]

	# ── Consultas ──

	def semaforo_de(self, paso_id: str) -> Semaforo | None:
		"""El semáforo de un paso de peatones, o None si no tiene."""
		return self.semaforos.get(paso_id)

	def fase(self, paso_id: str) -> str:
		"""Fase para peatones del semáforo de un paso: verde, intermitente o rojo («» si no tiene semáforo).

		Vale tanto para el semáforo declarado en los datos del paso como para
		uno puesto al lado como objeto de un complemento.
		"""
		semaforo = self.semaforos.get(paso_id)
		if semaforo is not None:
			return semaforo.fase
		objeto = self._semaforos_objeto.get(paso_id)
		if objeto is None:
			return ""
		estado = objeto.estado
		return estado if estado in FASES_SEMAFORO else "rojo"

	def objeto_usado(self, info: InfoObjeto, accion: str, estado: str) -> bool:
		"""El alumno ha accionado un objeto: atiende el pulsador de un semáforo. Devuelve si ya se ha dicho algo."""
		for temporizador in self._temporizadores:
			if temporizador.info is info:
				temporizador.t = 0.0
		if accion != "pulsar":
			return False
		ciclo = next((c for c in self._fases if c.info is info), None)
		if ciclo is None or not ciclo.pulsador:
			return False
		s = self.s
		if ciclo.sigue is not None:
			self._pulsar_semaforo(ciclo.sigue, info.objeto.id)
			return True
		principal = ciclo.maestro or ciclo
		fase = principal.estado
		if fase == "rojo":
			if principal.restante > principal.espera_tras_pulsar:
				principal.t = _segundos(principal.fases[principal.numero]) - principal.espera_tras_pulsar
			s.decir(_("Pulsador. Espera a que se ponga en verde."), canal="juego", pedida=True, clave="pulsador")
		elif fase == "verde":
			s.decir(_("Pulsador. Ya está en verde para peatones."), canal="juego", pedida=True, clave="pulsador")
		else:
			s.decir(_("Pulsador. El verde se está acabando: espera al siguiente."), canal="juego", pedida=True, clave="pulsador")
		s.registrar("pulsador", paso=ciclo.paso_id, objeto=info.objeto.id, fase=fase)
		return True

	def pulsadores_cerca(self, x: float, y: float, radio: float) -> list[dict[str, Any]]:
		"""Pulsadores de semáforo al alcance del alumno, del más cercano al más lejano."""
		planta = self.s.jugador.planta
		cerca: list[dict[str, Any]] = []
		for semaforo in self.semaforos.values():
			if semaforo.planta_id != planta or not semaforo.pulsador or semaforo.pulsan_objetos:
				continue
			for poste in semaforo.postes:
				d = math.hypot(poste[0] - x, poste[1] - y)
				if d <= radio:
					cerca.append({"espacio": semaforo.paso, "distancia": d, "punto": poste, "semaforo": semaforo})
					break
		cerca.sort(key=lambda dato: dato["distancia"])
		return cerca

	def pulsar(self, dato: dict[str, Any]) -> bool:
		"""Pulsa el botón de un semáforo: si está en rojo para peatones, acorta la espera."""
		s = self.s
		semaforo: Semaforo = dato["semaforo"]
		punto: Punto = dato["punto"]
		s.sonar("semaforo/pulsador", pos=s.pos3(punto[0], punto[1], 1.1))
		self._pulsar_semaforo(semaforo)
		return True

	def _pulsar_semaforo(self, semaforo: Semaforo, objeto_id: str = "") -> None:
		s = self.s
		fase = semaforo.fase
		if fase == "rojo":
			if semaforo.restante > ESPERA_TRAS_PULSAR:
				semaforo.t += semaforo.restante - ESPERA_TRAS_PULSAR
			s.decir(_("Pulsador. Espera a que se ponga en verde."), canal="juego", pedida=True, clave="pulsador")
		elif fase == "verde":
			s.decir(_("Pulsador. Ya está en verde para peatones."), canal="juego", pedida=True, clave="pulsador")
		else:
			s.decir(_("Pulsador. El verde se está acabando: espera al siguiente."), canal="juego", pedida=True, clave="pulsador")
		s.registrar("pulsador", paso=semaforo.paso.id, objeto=objeto_id, fase=fase)

	# ── Fotograma ──

	def tic(self, dt: float) -> None:
		"""Avanza semáforos, puertas automáticas, objetos con fases y tráfico."""
		s = self.s
		jugador = s.jugador
		for semaforo in self.semaforos.values():
			antes = semaforo.fase
			semaforo.t += dt
			ahora = semaforo.fase
			if ahora != antes and semaforo.planta_id == jugador.planta and jugador.modo == "andando":
				self._cambio_semaforo(semaforo, ahora)
		self._t_automaticas -= dt
		if self._t_automaticas <= 0.0:
			self._t_automaticas = 0.1
			self._puertas_automaticas()
		for objeto in self._fases:
			if objeto.sigue is not None:
				# Poste de un paso con semáforo propio: se pone en la fase del paso.
				fase_paso = objeto.sigue.fase
				numero = next((i for i, f in enumerate(objeto.fases) if f.get("estado") == fase_paso), objeto.numero)
				if numero != objeto.numero or s.mundo.estado_objeto(objeto.info.objeto.id) != fase_paso:
					objeto.numero = numero
					s.mundo.poner_estado_objeto(objeto.info.objeto.id, objeto.estado)
				continue
			if objeto.maestro is not None:
				# Segundo poste del mismo paso: va con el primero.
				if objeto.numero != objeto.maestro.numero and objeto.maestro.estado:
					s.mundo.poner_estado_objeto(objeto.info.objeto.id, objeto.maestro.estado)
				objeto.numero, objeto.t = objeto.maestro.numero, objeto.maestro.t
				continue
			objeto.t += dt
			while objeto.t >= _segundos(objeto.fases[objeto.numero]):
				objeto.t -= _segundos(objeto.fases[objeto.numero])
				objeto.numero = (objeto.numero + 1) % len(objeto.fases)
				estado = objeto.fases[objeto.numero].get("estado")
				if estado:
					s.mundo.poner_estado_objeto(objeto.info.objeto.id, str(estado))
		for temporizador in self._temporizadores:
			objeto_id = temporizador.info.objeto.id
			if s.mundo.estado_objeto(objeto_id) != temporizador.estado:
				temporizador.t = 0.0
				continue
			temporizador.t += dt
			if temporizador.t >= temporizador.segundos:
				temporizador.t = 0.0
				s.mundo.poner_estado_objeto(objeto_id, temporizador.al_terminar)
				s.registrar("objeto_termina", elemento=objeto_id, nombre=temporizador.info.objeto.nombre, estado=temporizador.al_terminar)
				if temporizador.sonido:
					# Suena en su sitio y con su oclusión, como cualquier otra cosa del lugar.
					lugar = (temporizador.info.planta_id, temporizador.info.objeto.x, temporizador.info.objeto.y)
					s.anadir_fuente(
						f"fin:{objeto_id}",
						sonido_de_objeto(temporizador.info, temporizador.sonido),
						lugar,
						radio=12.0,
						bucle=False,
						intervalo=3600.0,
					)
					s.acustica.disparar(f"fin:{objeto_id}")
		if s.ajustes.trafico:
			self._trafico(dt)
		self._vigilar_cruce()

	def _cambio_semaforo(self, semaforo: Semaforo, fase: str) -> None:
		s = self.s
		jugador = s.jugador
		if s.ajustes.detalle < 2:
			return
		if min(math.hypot(p[0] - jugador.x, p[1] - jugador.y) for p in semaforo.postes) > 8.0:
			return
		textos = {
			"verde": _("Semáforo en verde para peatones."),
			"intermitente": _("El verde se acaba."),
			"rojo": _("Semáforo en rojo para peatones."),
		}
		s.decir(textos[fase], canal="aviso", prioridad=2, clave=f"semaforo/{semaforo.paso.id}", caduca=3.0)

	def _puertas_automaticas(self) -> None:
		s = self.s
		jugador = s.jugador
		for info, original in self._automaticas:
			if info.planta_id != jugador.planta or jugador.modo != "andando":
				continue
			estado = s.mundo.estado_abertura(info.abertura.id)
			d = info.distancia(jugador.x, jugador.y)
			if estado == "cerrada" and d <= DISTANCIA_PARAR_AUTOMATICA:
				s.mundo.poner_abertura(info.abertura.id, "abierta")
				s.sonar("puerta/automatica", pos=s.pos3(info.centro[0], info.centro[1], 1.0))
				if s.ajustes.detalle >= 2:
					s.decir(
						_("{puerta}: se abre sola.").format(puerta=s.leng.abertura(info.abertura)),
						canal="juego",
						clave="puerta",
						caduca=4.0,
					)
				s.registrar("puerta", abertura=info.abertura.id, accion="automatica_abre", nombre=info.abertura.nombre)
			elif estado == "abierta" and original == "cerrada" and d >= DISTANCIA_CERRAR_AUTOMATICA:
				s.mundo.poner_abertura(info.abertura.id, "cerrada")
				s.sonar("puerta/automatica", pos=s.pos3(info.centro[0], info.centro[1], 1.0), volumen=0.8)
				s.registrar("puerta", abertura=info.abertura.id, accion="automatica_cierra", nombre=info.abertura.nombre)

	# ── Tráfico ──

	def _sentidos(self, via: Via) -> tuple[int, ...]:
		if via.sentido == "ida":
			return (1,)
		if via.sentido == "vuelta":
			return (-1,)
		return (1, -1)

	def _preparado(self) -> _TraficoPlanta:
		"""Vías con tráfico, pasos de peatones y datos fijos de cada vía de la planta del alumno.

		Se calculan una vez por planta (y otra si la planta se vuelve a
		indexar): en un barrio grande eran cientos de recorridos de ejes por
		fotograma. Son los mismos valores, calculados igual, así que el
		tráfico es idéntico con la misma semilla.
		"""
		indice = self.s.mundo.planta(self.s.jugador.planta)
		previo = self._trafico_planta
		if previo is not None and previo.indice is indice:
			return previo
		vias: list[Via] = []
		pasos: list[Espacio] = []
		datos: dict[int, _ViaPlanta] = {}
		if indice is not None:
			pasos = [e for _caja, e in indice.espacios if e.tipo == "paso_peatones"]
			if indice.planta.exterior:
				vias = [
					via for via in indice.planta.vias if 1 <= via.trafico <= 3 and len(via.eje) >= 2 and geo.longitud_linea(via.eje) > 5.0
				]
			for via in vias:
				dato = _ViaPlanta(via, geo.longitud_linea(via.eje), geo.caja(via.eje))
				for paso in pasos:
					if paso.datos.get("via") != via.id:
						continue
					ancho = float(paso.datos.get("ancho") or 4.0) if isinstance(paso.datos.get("ancho"), (int, float)) else 4.0
					centro = paso.centro()
					dato.pasos.append((paso, ancho, self._posicion_en_eje(via, centro, 1), self._posicion_en_eje(via, centro, -1)))
				datos[id(via)] = dato
		preparado = _TraficoPlanta(indice, vias, pasos, datos)
		self._trafico_planta = preparado
		return preparado

	def _largo(self, via: Via) -> float:
		"""Largo del eje de una vía (guardado si es de la planta del alumno)."""
		dato = self._trafico_planta.datos.get(id(via)) if self._trafico_planta is not None else None
		if dato is not None and dato.via is via:
			return dato.largo
		return geo.longitud_linea(via.eje)

	def _vias(self) -> list[Via]:
		return list(self._preparado().vias)

	def _nuevo_vehiculo(self, via: Via, sentido: int, d: float) -> Vehiculo:
		s = self.s
		self._numero_vehiculo += 1
		tirada = s.azar.random()
		sonido = TIPOS_VEHICULO[0][0]
		acumulado = 0.0
		for nombre, peso in TIPOS_VEHICULO:
			acumulado += peso
			if tirada <= acumulado:
				sonido = nombre
				break
		v_max = max(2.0, via.velocidad_kmh / 3.6) * s.azar.uniform(0.85, 1.1)
		lateral = via.ancho / 4.0 if via.sentido == "doble" else 0.0
		vehiculo = Vehiculo(f"veh-{self._numero_vehiculo}", via, s.jugador.planta, sentido, d, v_max, v_max, sonido, lateral)
		self._situar(vehiculo)
		return vehiculo

	def _situar(self, vehiculo: Vehiculo) -> None:
		eje = vehiculo.via.eje
		largo = self._largo(vehiculo.via)
		if vehiculo.sentido > 0:
			punto, rumbo = geo.punto_en_linea(eje, vehiculo.d)
		else:
			punto, rumbo = geo.punto_en_linea(eje, largo - vehiculo.d)
			rumbo = (rumbo + 180.0) % 360.0
		# Se circula por la derecha: el carril queda a la derecha del sentido de la marcha.
		vehiculo.x, vehiculo.y = geo.punto_a_distancia(punto, rumbo + 90.0, vehiculo.lateral)
		vehiculo.rumbo = rumbo

	def _poblar(self) -> None:
		"""Al llegar a una planta de calle, reparte vehículos por sus vías como si el tráfico ya llevara un rato."""
		s = self.s
		self.vehiculos.clear()
		self._esperas.clear()
		for via in self._vias():
			largo = geo.longitud_linea(via.eje)
			media = INTERVALO_TRAFICO[via.trafico]
			velocidad = max(2.0, via.velocidad_kmh / 3.6)
			for sentido in self._sentidos(via):
				d = s.azar.uniform(0.0, velocidad * media)
				while d < largo:
					self.vehiculos.append(self._nuevo_vehiculo(via, sentido, d))
					d += max(SEPARACION * 2.0, s.azar.expovariate(1.0 / (velocidad * media)))
				self._esperas[(via.id, sentido)] = s.azar.expovariate(1.0 / media)

	def _posicion_en_eje(self, via: Via, punto: Punto, sentido: int) -> float:
		"""Metros desde el extremo de entrada de ese sentido hasta la altura de un punto."""
		_cercano, _d, tramo = geo.proyeccion_sobre_linea(punto, via.eje)
		cercano = geo.proyeccion_sobre_segmento(punto, via.eje[tramo], via.eje[tramo + 1])
		desde_inicio = geo.longitud_linea(via.eje[: tramo + 1]) + geo.distancia(via.eje[tramo], cercano)
		return desde_inicio if sentido > 0 else geo.longitud_linea(via.eje) - desde_inicio

	def _trafico(self, dt: float) -> None:
		s = self.s
		jugador = s.jugador
		if jugador.planta != self._planta_trafico:
			self._planta_trafico = jugador.planta
			self._poblar()
		vias = self._vias()
		if not vias:
			return
		for via in vias:
			media = INTERVALO_TRAFICO[via.trafico]
			for sentido in self._sentidos(via):
				clave = (via.id, sentido)
				self._esperas[clave] = self._esperas.get(clave, media) - dt
				if self._esperas[clave] <= 0.0:
					self._esperas[clave] = max(2.5, s.azar.expovariate(1.0 / media))
					primero = min((v.d for v in self.vehiculos if v.via is via and v.sentido == sentido), default=math.inf)
					if primero > SEPARACION * 1.5:
						self.vehiculos.append(self._nuevo_vehiculo(via, sentido, 0.0))
		espacio = s.mundo.espacio_en(jugador.planta, jugador.x, jugador.y) if jugador.modo == "andando" else None
		en_calzada = espacio is not None and espacio.tipo in TIPOS_CALZADA
		preparado = self._preparado()
		# Los vehículos de cada vía y sentido juntos: el que va delante se busca solo entre los suyos.
		# Son los mismos objetos, que se van moviendo en este bucle: cada uno ve a los demás como antes.
		grupos: dict[tuple[int, int], list[Vehiculo]] = {}
		for vehiculo in self.vehiculos:
			grupos.setdefault((id(vehiculo.via), vehiculo.sentido), []).append(vehiculo)
		# Dónde queda el alumno a lo largo de cada vía (desde su inicio): no depende del vehículo.
		alumno_en: dict[int, float] = {}
		for vehiculo in self.vehiculos:
			via = vehiculo.via
			# Dónde tiene que parar, si tiene que parar: el obstáculo más cercano por delante.
			hueco = math.inf
			vehiculo.frena_por_alumno = False
			for otro in grupos[(id(via), vehiculo.sentido)]:
				if otro is not vehiculo and otro.d > vehiculo.d:
					hueco = min(hueco, otro.d - vehiculo.d - SEPARACION)
			dato = preparado.datos.get(id(via))
			if dato is not None and dato.via is via:
				pasos_via = dato.pasos
			else:
				pasos_via = self._pasos_de_via(via, preparado.pasos)
			for paso, ancho, linea_ida, linea_vuelta in pasos_via:
				linea = (linea_ida if vehiculo.sentido > 0 else linea_vuelta) - ancho / 2.0 - 1.5
				if linea < vehiculo.d - 0.5:
					continue
				fase_paso = self.fase(paso.id)
				if fase_paso:
					if fase_paso != "rojo":
						hueco = min(hueco, linea - vehiculo.d)
				elif espacio is not None and espacio.id == paso.id:
					# Paso sin semáforo con el alumno cruzando: cede el paso.
					hueco = min(hueco, linea - vehiculo.d)
					if linea - vehiculo.d < vehiculo.v * vehiculo.v / (2.0 * FRENADA) - 1.0:
						vehiculo.frena_por_alumno = True
			if en_calzada:
				desde_inicio = alumno_en.get(id(via))
				if desde_inicio is None:
					desde_inicio = self._posicion_en_eje(via, jugador.punto, 1)
					alumno_en[id(via)] = desde_inicio
				delante = (desde_inicio if vehiculo.sentido > 0 else self._largo(via) - desde_inicio) - vehiculo.d
				dx, dy = geo.vector_rumbo(vehiculo.rumbo)
				de_lado = abs((jugador.x - vehiculo.x) * dy - (jugador.y - vehiculo.y) * dx)
				if abs(delante) < 3.0 and vehiculo.v > 2.0 and de_lado < via.ancho / 2.0 + vehiculo.lateral + 0.5:
					# Le pasa por al lado, en marcha, mientras está en la calzada.
					vehiculo.frena_por_alumno = True
				if 0.0 < delante < 30.0 and de_lado < 2.2:
					if delante - 3.0 < hueco:
						hueco = delante - 3.0
						if (
							vehiculo.v > 2.0
							and delante < 18.0
							and (espacio is None or espacio.tipo != "paso_peatones" or self.fase(espacio.id))
						):
							vehiculo.frena_por_alumno = True
			if hueco <= 0.3:
				deseada = 0.0
			elif hueco < math.inf:
				deseada = min(vehiculo.v_max, math.sqrt(2.0 * FRENADA * hueco))
			else:
				deseada = vehiculo.v_max
			if deseada < vehiculo.v:
				vehiculo.v = max(deseada, vehiculo.v - FRENADA * 2.5 * dt)
			else:
				vehiculo.v = min(deseada, vehiculo.v + ACELERACION * dt)
			vehiculo.d += vehiculo.v * dt
			self._situar(vehiculo)
		self.vehiculos = [v for v in self.vehiculos if v.d <= self._largo(v.via) + 2.0]

	def _pasos_de_via(self, via: Via, pasos: list[Espacio]) -> list[tuple[Espacio, float, float, float]]:
		"""Pasos de peatones de una vía que no es de la planta preparada (no debería pasar; se calcula al momento)."""
		resultado: list[tuple[Espacio, float, float, float]] = []
		for paso in pasos:
			if paso.datos.get("via") != via.id:
				continue
			ancho = float(paso.datos.get("ancho") or 4.0) if isinstance(paso.datos.get("ancho"), (int, float)) else 4.0
			centro = paso.centro()
			resultado.append((paso, ancho, self._posicion_en_eje(via, centro, 1), self._posicion_en_eje(via, centro, -1)))
		return resultado

	def _pasos_de_planta(self) -> list[Espacio]:
		return list(self._preparado().pasos)

	# ── Cruces de calzada ──

	def tras_mover(self) -> None:
		"""Sigue los cruces de calzada del alumno: cuándo empieza a cruzar y cuándo llega a la otra acera."""
		s = self.s
		jugador = s.jugador
		if jugador.modo != "andando":
			return
		espacio = s.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		en_calzada = espacio is not None and espacio.tipo in TIPOS_CALZADA
		cruce = self._cruce
		if en_calzada and espacio is not None:
			if cruce is None:
				via_id = str(espacio.datos.get("via") or "")
				cruce = _Cruce(s.t, via_id, s.movimiento.espacio_anterior)
				self._cruce = cruce
				s.registrar("cruce_empieza", via=via_id, por_paso=espacio.tipo == "paso_peatones")
			if espacio.tipo == "paso_peatones" and not cruce.paso_id:
				cruce.paso_id = espacio.id
				cruce.fase = self.fase(espacio.id)
				if cruce.fase == "rojo" and s.ajustes.detalle >= 2:
					s.decir(_("Estás cruzando en rojo."), canal="aviso", prioridad=3, clave="rojo", caduca=4.0)
		elif cruce is not None:
			self._cruce = None
			destino = espacio.id if espacio is not None else ""
			s.registrar(
				"cruce",
				via=cruce.via_id,
				paso=cruce.paso_id,
				por_paso=bool(cruce.paso_id),
				fase=cruce.fase,
				en_rojo=cruce.fase == "rojo",
				seguro=not cruce.inseguro and cruce.fase != "rojo",
				duracion=round(s.t - cruce.t0, 2),
				vuelve=destino == cruce.origen,
			)

	def _vigilar_cruce(self) -> None:
		"""Mientras el alumno cruza, mira si algún vehículo ha tenido que frenar por él o le pasa rozando."""
		cruce = self._cruce
		if cruce is None or cruce.inseguro:
			return
		s = self.s
		jugador = s.jugador
		for vehiculo in self.vehiculos:
			if vehiculo.frena_por_alumno:
				cerca = math.hypot(vehiculo.x - jugador.x, vehiculo.y - jugador.y)
				cruce.inseguro = True
				s.vibrar("aviso")
				s.decir(s.leng.tono("trafico"), canal="aviso", prioridad=3, clave="trafico", caduca=6.0)
				s.registrar(
					"cruce_inseguro",
					via=cruce.via_id,
					paso=cruce.paso_id,
					fase=cruce.fase,
					distancia=round(cerca, 1),
					vehiculo=vehiculo.sonido,
				)
				return

	# ── Emisores ──

	def emisores(self) -> list[Emisor]:
		"""Lo que suena por la dinámica en la planta del alumno: semáforos, vehículos, rumor de tráfico y objetos con fases."""
		s = self.s
		jugador = s.jugador
		lista: list[Emisor] = []
		for semaforo in self.semaforos.values():
			if not semaforo.sonoro or semaforo.planta_id != jugador.planta or semaforo.suenan_objetos:
				continue
			fase = semaforo.fase
			for numero, poste in enumerate(semaforo.postes):
				lista.append(
					Emisor(
						id=f"sem:{semaforo.paso.id}:{numero}",
						sonido=f"semaforo/{fase}",
						planta_id=semaforo.planta_id,
						x=poste[0],
						y=poste[1],
						altura=2.0,
						volumen=0.35 if fase == "rojo" else 0.8,
						radio=10.0 if fase == "rojo" else 20.0,
						movil=True,
					)
				)
		for objeto in self._fases:
			fase_objeto = objeto.fases[objeto.numero]
			if not fase_objeto.get("sonido") or objeto.info.planta_id != jugador.planta:
				continue
			lista.append(
				Emisor(
					id=f"din:{objeto.info.objeto.id}",
					sonido=sonido_de_objeto(objeto.info, str(fase_objeto["sonido"])),
					planta_id=objeto.info.planta_id,
					x=objeto.info.objeto.x,
					y=objeto.info.objeto.y,
					altura=min(2.0, max(0.3, objeto.info.objeto.alto * 0.8)),
					volumen=objeto.volumen,
					radio=objeto.radio,
					movil=True,
				)
			)
		if not s.ajustes.trafico:
			return lista
		for vehiculo in self.vehiculos:
			if vehiculo.planta_id != jugador.planta or abs(vehiculo.x - jugador.x) > 45.0 or abs(vehiculo.y - jugador.y) > 45.0:
				continue
			marcha = vehiculo.v / vehiculo.v_max if vehiculo.v_max > 0 else 0.0
			lista.append(
				Emisor(
					id=vehiculo.id,
					sonido=vehiculo.sonido,
					planta_id=vehiculo.planta_id,
					x=vehiculo.x,
					y=vehiculo.y,
					altura=0.6,
					volumen=0.45 + 0.45 * marcha,
					radio=45.0,
					tono=0.75 + 0.3 * marcha,
					movil=True,
				)
			)
		preparado = self._preparado()
		for via in preparado.vias:
			dato = preparado.datos.get(id(via))
			if dato is not None:
				# Una vía cuya caja queda a más de 50 m no puede tener ningún punto a 50 m: ni se proyecta.
				x0, y0, x1, y1 = dato.caja
				if jugador.x < x0 - 50.0 or jugador.x > x1 + 50.0 or jugador.y < y0 - 50.0 or jugador.y > y1 + 50.0:
					continue
			cercano, d, _tramo = geo.proyeccion_sobre_linea(jugador.punto, via.eje)
			if d > 50.0:
				continue
			lista.append(
				Emisor(
					id=f"trafico:{via.id}",
					sonido=AMBIENTE_TRAFICO[via.trafico],
					planta_id=jugador.planta,
					x=cercano[0],
					y=cercano[1],
					altura=1.0,
					volumen=0.3,
					radio=50.0,
					movil=True,
				)
			)
		return lista
