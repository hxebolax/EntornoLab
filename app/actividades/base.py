"""La clase ``Actividad``: lo que comparten todos los juegos, prácticas y exámenes.

Una actividad se cuelga de la ``Sesion`` del motor y recibe sus ganchos
(``al_empezar``, ``tras_mover``, ``al_interactuar``, ``tic``, ``al_pedir``,
``al_registrar`` y ``resultado``). Esta clase pone lo común y deja a cada tipo solo su regla de
juego:

- **Premios**: fuentes de sonido de la sesión que se recogen al llegar o al
  usar el objeto que los esconde.
- **Ayudas y niveles**: qué se permite, la baliza según el nivel y la
  retirada progresiva de ayudas.
- **Reglas para que jugar no estropee el aprendizaje**: el tiempo que cuenta
  es el de juego (las pausas no penalizan), chocar informa pero no elimina,
  tras varios tropiezos seguidos se ofrece ayuda en lugar de insistir y
  ganar nunca depende solo de seguir una baliza.
- **Modo examen**: sin pistas, sin celebraciones y sin decir si se acierta.
- **Órdenes del profesional** desde la supervisión.
- **Resultado** con todo lo que el seguimiento espera.

La actividad no guarda nada del alumno entre sesiones: lo que haga falta
recordar (el nivel alcanzado, las estrellas acumuladas) sale en el resultado
y vuelve en los datos la próxima vez.
"""

from __future__ import annotations

import logging
import math
import random
from dataclasses import dataclass
from typing import Any

from app.actividades import cuestionario, puntuacion, recompensas
from app.actividades.formato import SONIDO_PREMIO, SONIDO_PREMIO_LEJOS, normalizar, normalizar_premio
from app.actividades.lugares import Lugar, espacios_jugables, pista_de_lugar, punto_de_acceso, punto_libre_en, resolver_lugar
from app.actividades.textos import Textos
from app.actividades.tipos import AYUDAS_PROHIBIDAS_EN_EXAMEN, ESTILOS, TIPOS
from app.core.i18n import N_, _, _n
from app.dominio.catalogo import Catalogo
from app.dominio.modelo import Entorno, Objeto, Posicion
from app.motor import eventos as ev
from app.motor.eventos import Evento
from app.motor.sesion import AjustesJuego, regla_ayuda

log = logging.getLogger(__name__)

RADIO_RECOGER = 0.9
RADIO_RECOGER_A_MANO = 1.6
RADIO_VIBRAR = 2.5
INTERVALO_VIBRAR = 1.3
SEGUNDOS_BALIZA = 20.0
# Choques en poco tiempo que se toman como señal de que el alumno está atascado.
CHOQUES_SEGUIDOS = 4
VENTANA_CHOQUES = 20.0
SEGUNDOS_SIN_AVANCE = 150.0
AVISO_TIEMPO = 60.0
# Registros del motor que interesan a las actividades.
REGISTROS_DEL_MOTOR = frozenset(
	{"choque", "salida", "cruce", "cruce_inseguro", "cruce_empieza", "cambio_planta", "baliza_llegada", "entrada_espacio"}
)

AVISO_RESULTADO = N_(
	"Las puntuaciones describen lo ocurrido en el simulador. No equivalen a competencia en el lugar real ni son un diagnóstico."
)


@dataclass
class Premio:
	"""Un premio en juego: dónde está, cómo suena y si ya se ha recogido."""

	id: str
	nombre: str
	planta: str = ""
	x: float = 0.0
	y: float = 0.0
	sonido: str = ""
	visibilidad: str = "cerca"
	dentro_de: str | None = None
	mensaje: str = ""
	audio: str | None = None
	vibrar: bool = True
	pista: str = ""
	extra: bool = False
	colocado: bool = False
	recogido: bool = False
	t_recogido: float | None = None
	sonando: bool = False
	t_vibrar: float = 0.0
	# Punto libre desde el que se usa el objeto que lo esconde: adonde llevan la baliza y las pistas.
	acceso: tuple[float, float] | None = None

	@property
	def terna(self) -> tuple[str, float, float]:
		"""(planta, x, y)."""
		return self.planta, self.x, self.y

	@property
	def fuente(self) -> str:
		"""Id de su fuente de sonido en la sesión."""
		return f"premio:{self.id}"

	def lugar(self) -> Lugar:
		"""El premio como lugar al que ir (si está dentro de un objeto, el punto desde el que se usa)."""
		x, y = self.acceso if self.acceso is not None else (self.x, self.y)
		return Lugar(self.planta, x, y, self.nombre, "premio", self.id, RADIO_RECOGER)


class Actividad:
	"""Una actividad en marcha. Las subclases definen la regla de cada tipo."""

	# Motivos de estrella que se pueden ganar en este tipo de actividad.
	ESTRELLAS: tuple[str, ...] = ("completar", "pocas_ayudas", "sin_choques")
	# Si los premios de la lista son parte del objetivo (búsqueda) o un regalo por el camino.
	PREMIOS_OBLIGATORIOS = False

	def __init__(
		self,
		datos: dict[str, Any],
		entorno: Entorno,
		catalogo: Catalogo | None = None,
		estilo: str | None = None,
		semilla: int | None = None,
		nivel: int | None = None,
	) -> None:
		"""``estilo`` es el de la ficha del alumno (lo usa la actividad si no fija uno propio); ``semilla`` hace reproducible lo que se genera, salvo que la actividad traiga la suya."""
		self.datos = normalizar(datos)
		self.entorno = entorno
		self.catalogo = catalogo
		self.id: str = self.datos["id"]
		self.nombre: str = self.datos["nombre"]
		self.tipo: str = self.datos["tipo"]
		self.modo: str = self.datos["modo"]
		self.es_examen = self.modo == "examen"
		self._estilo_fijo = self.datos["estilo"] in ESTILOS
		self.estilo: str = self.datos["estilo"] if self._estilo_fijo else (estilo if estilo in ESTILOS else "adulto")
		self._estilo_dado = self._estilo_fijo or estilo in ESTILOS
		self.tx = Textos(self.estilo)
		# Si la actividad fija su semilla (un examen la fija siempre) manda esa: así el examen es el mismo
		# otro día aunque el reproductor pase la semilla de cada partida. La que llega solo vale si no hay otra.
		propia = self.datos.get("semilla")
		self.semilla: int | None = propia if propia is not None else semilla
		self.azar = random.Random(self.semilla)
		self.niveles: list[dict[str, Any]] = self.datos["niveles"]
		tope = max(0, len(self.niveles) - 1)
		self.nivel: int = max(0, min(tope, int(nivel if nivel is not None else self.datos["nivel"])))
		self.premios: list[Premio] = [self._premio_de(dato) for dato in self.datos["premios"]]
		self.coleccion: list[str] = []
		# Marcador.
		self.hechos = 0
		self.total = 0
		self.puntos = 0
		self.puntos_maximos = 0
		self.fase = ""
		self.completada = False
		self.motivo = ""
		# Estado de la partida.
		self._sesion: Any = None
		self._empezada = False
		self._cerrada = False
		self._resultado: dict[str, Any] | None = None
		self._t = 0.0
		self._avisado_tiempo = False
		# Registros del motor que han llegado por «al_registrar» y esperan al siguiente «tic».
		self._registros_pendientes: list[tuple[str, dict[str, Any]]] = []
		self._fallos = 0
		self._fallos_seguidos = 0
		self._ayudas_ofrecidas = 0
		self._ayuda_ofrecida = False
		self._t_progreso = 0.0
		self._t_choques: list[float] = []
		self._pistas_dadas: dict[str, int] = {}
		self._baliza_hasta: float | None = None
		self._baliza_regla_previa: dict[str, Any] | None = None
		self._baliza_continua = False
		self._destino_guia: Lugar | None = None
		self._intervenciones: dict[str, int] = {}
		self._tramos: list[dict[str, Any]] = []
		self._tramo: dict[str, Any] | None = None
		self._logros: list[dict[str, Any]] = []
		self._travesuras = 0
		self._t_travieso = 0.0
		self._valoracion: dict[str, Any] | None = None
		self._usos_inicio: dict[str, int] = {}
		self._choques_inicio = 0
		self._distancia_inicio = 0.0
		self._explorables: list[str] | None = None
		# Balizas que pone la propia actividad para enseñar un tramo (la ida de una ruta inversa): no son ayudas pedidas.
		self._ayudas_no_contadas = 0

	# ── Datos ──

	@staticmethod
	def _premio_de(dato: dict[str, Any], extra: bool = False) -> Premio:
		return Premio(
			id=dato["id"],
			nombre=dato["nombre"],
			planta=dato.get("planta") or "",
			x=float(dato["x"]) if dato.get("x") is not None else math.nan,
			y=float(dato["y"]) if dato.get("y") is not None else math.nan,
			sonido=dato.get("sonido") or "",
			visibilidad=dato.get("visibilidad") or "cerca",
			dentro_de=dato.get("dentro_de"),
			mensaje=dato.get("mensaje") or "",
			audio=dato.get("audio"),
			vibrar=bool(dato.get("vibrar", True)),
			pista=dato.get("pista") or "",
			extra=extra,
		)

	def inicio(self) -> Posicion | None:
		"""Punto de inicio propio de la actividad, o None si vale el del entorno."""
		dato = self.datos.get("inicio")
		if not isinstance(dato, dict) or self.entorno.planta(str(dato.get("planta"))) is None:
			return None
		return Posicion(str(dato["planta"]), float(dato["x"]), float(dato["y"]), float(dato.get("rumbo", 0.0)))

	def lugar(self, valor: Any, radio: float | None = None) -> Lugar | None:
		"""Resuelve un lugar de los datos (id o posición) en este entorno.

		Un objeto se convierte en el punto libre desde el que se le puede
		usar (su centro no se puede pisar), si la partida ya ha empezado.
		"""
		lugar = resolver_lugar(self.entorno, valor) if radio is None else resolver_lugar(self.entorno, valor, radio)
		if lugar is not None and lugar.clase == "objeto" and self._sesion is not None:
			acceso = punto_de_acceso(self._sesion.mundo, lugar.elemento_id)
			if acceso is not None:
				lugar.x, lugar.y = acceso
		return lugar

	# ── Ayudas, niveles y ajustes ──

	def modo_baliza(self) -> str:
		"""Cómo se usa la baliza ahora: ``nunca``, ``al_pedir`` o ``siempre`` (según el nivel, si hay niveles)."""
		if self.es_examen:
			return "nunca"
		if self.niveles:
			return str(self.niveles[self.nivel].get("baliza") or "nunca")
		return str(self.datos.get("baliza") or "nunca")

	def reglas_ayudas(self) -> dict[str, dict[str, Any]]:
		"""Reglas de ayudas que impone la actividad: las del examen, las que marcó el profesional y las del nivel."""
		reglas: dict[str, dict[str, Any]] = {}
		if self.es_examen:
			for ayuda in AYUDAS_PROHIBIDAS_EN_EXAMEN:
				reglas[ayuda] = {"permitida": False, "limite": None}
		for ayuda, regla in self.datos["ayudas"].items():
			reglas[ayuda] = regla_ayuda(regla)
		if self.niveles:
			for ayuda, regla in self.niveles[self.nivel].get("ayudas", {}).items():
				reglas[ayuda] = regla_ayuda(regla)
		if self.es_examen:
			# En un examen no hay pistas ni baliza, lo diga quien lo diga: darían la respuesta.
			reglas["pista"] = {"permitida": False, "limite": None}
			reglas["baliza"] = {"permitida": False, "limite": None}
		return reglas

	def ajustes(self, base: AjustesJuego) -> AjustesJuego:
		"""Ajustes de juego del alumno retocados por la actividad: ayudas permitidas y límites, y estilo.

		Devuelve una copia: los ajustes de la ficha no se tocan.
		"""
		nuevos = AjustesJuego.de_dict(base.a_dict())
		if self._estilo_dado:
			nuevos.estilo = self.estilo
		for ayuda, regla in self.reglas_ayudas().items():
			nuevos.ayudas[ayuda] = dict(regla)
		self._retocar_ajustes(nuevos)
		return nuevos

	def _retocar_ajustes(self, ajustes: AjustesJuego) -> None:
		"""Cambios de ajustes propios de un tipo (el giro fino del examen de señalar)."""

	def _aplicar_reglas(self, sesion: Any) -> None:
		"""Pone en la sesión las reglas de ayudas de la actividad, por si quien la creó no pasó por ``ajustes``."""
		for ayuda, regla in self.reglas_ayudas().items():
			actual = sesion.ajustes.ayudas.get(ayuda)
			if actual != regla:
				sesion.permitir_ayuda(ayuda, regla["permitida"], regla["limite"])

	# ── Ganchos del motor ──

	def al_empezar(self, sesion: Any) -> list[Evento]:
		"""Prepara la partida: reglas, premios y mensaje de inicio."""
		self._sesion = sesion
		self._empezada = True
		if self.semilla is None:
			self.semilla = sesion.semilla
			self.azar = random.Random(self.semilla)
		if not self._estilo_dado:
			self.estilo = sesion.ajustes.estilo if sesion.ajustes.estilo in ESTILOS else "adulto"
			self.tx = Textos(self.estilo)
		elif sesion.ajustes.estilo != self.estilo:
			sesion.ajustes.estilo = self.estilo
			sesion.leng.estilo = self.estilo
		self._aplicar_reglas(sesion)
		self._retocar_ajustes(sesion.ajustes)
		self._t = sesion.t
		self._t_progreso = sesion.t
		self._t_travieso = sesion.t
		self._usos_inicio = dict(sesion.percepcion.usos)
		self._choques_inicio = sesion.movimiento.choques
		self._distancia_inicio = sesion.movimiento.distancia
		for premio in self.premios:
			self._situar_premio(sesion, premio)
		self._preparar(sesion)
		self._refrescar_fuentes(sesion)
		self._saludar(sesion)
		return []

	def tras_mover(self, sesion: Any) -> list[Evento]:
		"""Tras cada desplazamiento: premios al alcance y la regla del tipo."""
		if self._cerrada or not self._empezada:
			return []
		self._comprobar_premios(sesion)
		if not self._cerrada:
			self._tras_mover(sesion)
		return []

	def al_interactuar(self, sesion: Any, elemento: Any) -> list[Evento]:
		"""Tras usar algo: premios escondidos dentro de un objeto y la regla del tipo.

		Devuelve eventos solo cuando la actividad ha hecho algo con esa
		pulsación; así el motor no añade «no hay nada que usar aquí».
		"""
		if self._cerrada or not self._empezada:
			return []
		eventos: list[Evento] = []
		if isinstance(elemento, Objeto):
			dentro = [
				p for p in self.premios if not p.recogido and p.colocado and p.dentro_de == elemento.id and self._premio_disponible(p)
			]
			for premio in dentro:
				self._recoger(sesion, premio, dentro=True)
			if not dentro and not self.es_examen and self._es_contenedor(elemento) and self._quedan_escondidos():
				self._decir(sesion, self.tx("contenedor_vacio"), prioridad=2, clave="vacio")
		if elemento is None and not self._cerrada:
			a_mano = self._premio_a_mano(sesion)
			if a_mano is not None:
				self._recoger(sesion, a_mano)
				# Con esto el motor sabe que la pulsación ha servido y no dice «no hay nada que usar aquí».
				eventos.append(ev.EvSonido("interfaz/elegir", bus="interfaz"))
		if not self._cerrada:
			eventos.extend(self._al_interactuar(sesion, elemento) or [])
		return eventos

	def tic(self, sesion: Any, dt: float) -> list[Evento]:
		"""Cada fotograma de juego: tiempo, registros del motor, vibración de premio cercano, travieso y atascos."""
		if self._cerrada or not self._empezada:
			return []
		self._t = sesion.t
		for tipo, datos in self._registros_nuevos(sesion):
			if tipo == "choque":
				self._al_chocar(sesion)
			self._al_registro(sesion, tipo, datos)
			if self._cerrada:
				return []
		limite = self.datos.get("tiempo_limite_s")
		if limite and not self.es_examen:
			resto = limite - (sesion.t - self._t0())
			if resto <= 0.0:
				self._terminar(sesion, False, "tiempo")
				return []
			if resto <= AVISO_TIEMPO < limite and not self._avisado_tiempo:
				self._avisado_tiempo = True
				self._decir(sesion, self.tx("queda_un_minuto"), prioridad=2, clave="tiempo")
		if self._baliza_hasta is not None and sesion.t >= self._baliza_hasta:
			self._apagar_baliza_temporal(sesion)
		self._vibrar_cerca(sesion, dt)
		self._tic_travieso(sesion)
		if (
			not self.es_examen
			and self.datos["fallos_para_ayuda"] > 0
			and self._avance_esperado()
			and sesion.t - self._t_progreso > SEGUNDOS_SIN_AVANCE
		):
			self._t_progreso = sesion.t
			self._ofrecer_ayuda(sesion, "sin_avance")
		self._tic(sesion, dt)
		return []

	def al_pedir(self, sesion: Any, accion: str) -> list[Evento]:
		"""El alumno pide el objetivo o una pista (el motor ya lo ha contado como ayuda)."""
		if self._cerrada or not self._empezada:
			return []
		if accion == "objetivo":
			texto = self._al_pedir_objetivo(sesion)
			return [ev.EvVoz(texto, True, "ayuda")] if texto else []
		if accion == "pista":
			if self.es_examen:
				return [ev.EvVoz(self.tx("sin_pistas_examen"), True, "ayuda")]
			texto = self._dar_pista(sesion)
			if not texto:
				return [ev.EvVoz(self.tx("sin_pista"), True, "ayuda")]
			return [ev.EvSonido("logro/pista", bus="ayudas"), ev.EvVoz(texto, True, "ayuda")]
		return []

	def resultado(self, sesion: Any) -> dict[str, Any]:
		"""Resultado de la actividad, que el motor mezcla en ``EvFin``.

		Si la sesión termina sin que la actividad haya acabado (el alumno lo
		deja, el profesional la corta), se cierra aquí como no completada.
		"""
		if not self._cerrada:
			self._cerrar(sesion, False, "abandonada")
		return dict(self._resultado or {})

	# ── Lo que redefine cada tipo ──

	def _preparar(self, sesion: Any) -> None:
		"""Monta el estado propio del tipo al empezar."""

	def _tras_mover(self, sesion: Any) -> None:
		"""Regla del tipo tras cada desplazamiento."""

	def _al_interactuar(self, sesion: Any, elemento: Any) -> list[Evento]:
		"""Regla del tipo tras usar algo. Devuelve eventos si ha atendido la pulsación."""
		return []

	def _tic(self, sesion: Any, dt: float) -> None:
		"""Regla del tipo cada fotograma."""

	def _al_registro(self, sesion: Any, tipo: str, datos: dict[str, Any]) -> None:
		"""Un registro del motor que interesa a las actividades (choque, salida, cruce, cambio de planta…)."""

	def _premio_recogido(self, sesion: Any, premio: Premio) -> None:
		"""Se ha recogido un premio."""

	def _premio_disponible(self, premio: Premio) -> bool:
		"""Si ese premio está en juego ahora (en una búsqueda por orden, solo el siguiente)."""
		return True

	def _premio_anadido(self, sesion: Any, premio: Premio) -> None:
		"""El profesional ha añadido en caliente un premio que cuenta para el objetivo."""

	def _avance_esperado(self) -> bool:
		"""Si la actividad tiene un objetivo en el que se puede estar atascado (una exploración libre, no)."""
		return True

	def texto_objetivo(self) -> str:
		"""Qué tiene que hacer el alumno ahora, en una frase."""
		return self.tx("objetivo_libre")

	def _lugar_actual(self) -> Lugar | None:
		"""Lugar al que hay que ir ahora, para las pistas y la baliza; None si no lo hay."""
		return self._destino_guia

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		"""Claves propias del tipo para el resultado."""
		return {}

	def _puntuaciones(self, sesion: Any) -> dict[str, Any] | None:
		"""Puntuaciones medidas (las de un examen, o las de un juego que puntúa como él); None si no las hay."""
		return None

	def _datos_estrellas(self, sesion: Any) -> dict[str, Any]:
		"""Datos propios del tipo para calcular las estrellas (media de salida, exploración, seguridad)."""
		return {}

	def _texto_inicio(self) -> str:
		"""Mensaje de inicio de serie del tipo."""
		return self.tx("inicio")

	# ── Hablar ──

	def _decir(
		self, sesion: Any, texto: str, prioridad: int = 3, clave: str = "actividad", caduca: float = 15.0, canal: str = "juego"
	) -> None:
		if texto:
			sesion.decir(texto, canal=canal, prioridad=prioridad, clave=clave, caduca=caduca)

	def _celebrar(self, sesion: Any, texto: str = "", sonido: str = "logro/logro") -> None:
		"""Celebración intermedia: sonido, vibración y frase. En examen no hay ninguna."""
		if self.es_examen:
			return
		sesion.sonar(sonido, bus="efectos")
		sesion.vibrar("objetivo")
		self._decir(sesion, texto, clave="logro")

	def acompanante(self) -> str:
		"""Nombre del personaje que acompaña al alumno; vacío si no lo hay (solo existe en el estilo infantil y fuera de examen)."""
		if self.estilo != "infantil" or self.es_examen or not self.datos.get("con_acompanante", True):
			return ""
		return str(self.datos.get("acompanante") or "") or self.tx("amigo")

	def _saludar(self, sesion: Any) -> None:
		partes = [self.datos["mensajes"]["inicio"] or self._texto_inicio()]
		amigo = self.acompanante()
		if amigo and not self.datos["mensajes"]["inicio"]:
			partes.insert(0, self.tx("acompanante", amigo=amigo))
		limite = self.datos.get("tiempo_limite_s")
		if limite and not self.es_examen:
			partes.append(self.tx("con_tiempo", tiempo=self.tx.duracion(limite)))
		objetivo = self.texto_objetivo()
		if objetivo and objetivo not in partes[0]:
			partes.append(objetivo)
		self._decir(sesion, " ".join(p for p in partes if p), clave="inicio", caduca=30.0)

	def _al_pedir_objetivo(self, sesion: Any) -> str:
		"""Texto con el que se contesta a «¿qué tengo que hacer?»."""
		return self.texto_objetivo()

	# ── Tiempo ──

	def _t0(self) -> float:
		"""Instante de juego en que empezó a contar el tiempo de la actividad."""
		return 0.0

	def tiempo_restante(self) -> float | None:
		"""Segundos de juego que quedan, o None si no hay límite."""
		limite = self.datos.get("tiempo_limite_s")
		if not limite or self.es_examen:
			return None
		return max(0.0, round(limite - (self._t - self._t0()), 1))

	# ── Registros del motor ──

	def al_registrar(self, sesion: Any, registro: Any) -> list[Evento]:
		"""Gancho del motor: la sesión pasa aquí cada ``EvRegistro`` que emite (un choque, un cruce, una salida…).

		Solo se apuntan los que interesan a las actividades; se atienden en el
		siguiente ``tic`` y no aquí, porque el motor puede registrar a mitad
		de un paso (un choque, una salida) y la regla del tipo puede mover al
		alumno o terminar la partida: hacerlo entonces dejaría el movimiento a
		medias. El ``tic`` llega en el mismo fotograma, así que no se pierde nada.
		"""
		if self._cerrada or not self._empezada:
			return []
		tipo = getattr(registro, "tipo", "")
		if tipo in REGISTROS_DEL_MOTOR:
			datos = getattr(registro, "datos", None)
			self._registros_pendientes.append((tipo, dict(datos) if isinstance(datos, dict) else {}))
		return []

	def _registros_nuevos(self, sesion: Any) -> list[tuple[str, dict[str, Any]]]:
		"""Registros del motor recibidos por ``al_registrar`` que la actividad aún no ha atendido."""
		nuevos, self._registros_pendientes = self._registros_pendientes, []
		return nuevos

	# ── Premios ──

	def _situar_premio(self, sesion: Any, premio: Premio) -> None:
		"""Decide dónde está el premio: en el objeto que lo esconde o en su punto. Sin sitio válido, queda fuera de juego."""
		if premio.dentro_de:
			info = sesion.mundo.objeto(premio.dentro_de)
			if info is not None:
				premio.planta, premio.x, premio.y = info.planta_id, info.objeto.x, info.objeto.y
				premio.acceso = punto_de_acceso(sesion.mundo, premio.dentro_de)
				premio.colocado = True
				return
			log.warning("El premio %s dice estar dentro de un objeto que no existe; se deja suelto", premio.id)
			premio.dentro_de = None
		if sesion.mundo.planta(premio.planta) is None or not (math.isfinite(premio.x) and math.isfinite(premio.y)):
			log.warning("El premio %s no tiene un lugar válido y no entra en juego", premio.id)
			premio.colocado = False
			return
		premio.colocado = True

	def premios_pendientes(self, con_extras: bool = False) -> list[Premio]:
		"""Premios en juego que faltan por recoger."""
		return [p for p in self.premios if p.colocado and not p.recogido and (con_extras or not p.extra)]

	def _quedan_escondidos(self) -> bool:
		return any(p.dentro_de for p in self.premios_pendientes(True))

	def _es_contenedor(self, objeto: Objeto) -> bool:
		definicion = self.catalogo.definicion_de(objeto) if self.catalogo is not None else None
		return bool(definicion is not None and definicion.contenedor)

	def _refrescar_fuentes(self, sesion: Any) -> None:
		"""Pone a sonar los premios en juego y calla los demás."""
		for premio in self.premios:
			debe = premio.colocado and not premio.recogido and premio.visibilidad != "oculto" and self._premio_disponible(premio)
			if debe and not premio.sonando:
				lejos = premio.visibilidad == "lejos"
				if premio.sonido:
					sesion.anadir_fuente(
						premio.fuente,
						premio.sonido,
						premio.terna,
						volumen=1.0 if lejos else 0.8,
						radio=30.0 if lejos else 5.0,
						bucle=False,
						intervalo=2.5 if lejos else 2.0,
						bus="efectos",
					)
				elif lejos:
					sesion.anadir_fuente(
						premio.fuente, SONIDO_PREMIO_LEJOS, premio.terna, volumen=1.0, radio=30.0, bucle=False, intervalo=2.5, bus="efectos"
					)
				else:
					sesion.anadir_fuente(premio.fuente, SONIDO_PREMIO, premio.terna, volumen=0.8, radio=5.0, bucle=True, bus="efectos")
				premio.sonando = True
			elif not debe and premio.sonando:
				sesion.quitar_fuente(premio.fuente)
				premio.sonando = False

	def _comprobar_premios(self, sesion: Any) -> None:
		"""Recoge los premios sueltos a los que el alumno ha llegado."""
		for premio in list(self.premios):
			if premio.recogido or not premio.colocado or premio.dentro_de or not self._premio_disponible(premio):
				continue
			if sesion.distancia_a(premio.terna) <= RADIO_RECOGER:
				self._recoger(sesion, premio)
				if self._cerrada:
					return

	def _premio_a_mano(self, sesion: Any) -> Premio | None:
		"""Premio suelto que queda al alcance de la mano (se coge con la orden de usar aunque no se haya pisado)."""
		candidatos = [
			(sesion.distancia_a(p.terna), p)
			for p in self.premios
			if p.colocado and not p.recogido and not p.dentro_de and self._premio_disponible(p)
		]
		candidatos = [par for par in candidatos if par[0] <= RADIO_RECOGER_A_MANO]
		return min(candidatos, key=lambda par: par[0])[1] if candidatos else None

	def _puede_recoger(self, sesion: Any, premio: Premio) -> bool:
		"""Si ahora se puede coger ese premio (en «sacar los tesoros», no mientras se lleva otro)."""
		return True

	def _recoger(self, sesion: Any, premio: Premio, dentro: bool = False) -> None:
		if premio.recogido or not self._puede_recoger(sesion, premio):
			return
		premio.recogido = True
		premio.t_recogido = round(sesion.t, 2)
		if premio.sonando:
			sesion.quitar_fuente(premio.fuente)
			premio.sonando = False
		self.coleccion.append(premio.nombre)
		altura = sesion.mundo.altura(premio.planta) + 1.0
		ultimo = self.PREMIOS_OBLIGATORIOS and not self.premios_pendientes()
		sesion.sonar("premio/tesoro" if ultimo else "premio/recogido", pos=(premio.x, premio.y, altura))
		sesion.vibrar("objetivo")
		sesion.registrar("premio", id=premio.id, nombre=premio.nombre, dentro_de=premio.dentro_de or "", extra=premio.extra)
		self._avance(sesion)
		partes = [self.tx("premio_dentro" if dentro else "premio_cogido", nombre=premio.nombre)]
		if premio.mensaje:
			partes.append(premio.mensaje)
		self._decir(sesion, " ".join(partes), clave=f"premio:{premio.id}")
		if premio.audio:
			# Mensaje grabado por el profesional o la familia: un recurso del paquete, que el banco de sonidos sabe encontrar.
			sesion.sonar(premio.audio, bus="voz", retardo=0.8)
		self._premio_recogido(sesion, premio)
		if not self._cerrada:
			self._refrescar_fuentes(sesion)

	def _vibrar_cerca(self, sesion: Any, dt: float) -> None:
		"""Aviso por vibración al estar cerca de un premio que lo pide (los ocultos no se delatan)."""
		for premio in self.premios:
			if (
				premio.recogido
				or not premio.colocado
				or not premio.vibrar
				or premio.visibilidad == "oculto"
				or not self._premio_disponible(premio)
			):
				continue
			premio.t_vibrar -= dt
			if premio.t_vibrar <= 0.0 and sesion.distancia_a(premio.terna) <= RADIO_VIBRAR:
				sesion.vibrar("premio_cerca")
				premio.t_vibrar = INTERVALO_VIBRAR

	def _anadir_premio(self, sesion: Any, dato: dict[str, Any], extra: bool = True) -> Premio | None:
		"""Añade un premio en caliente. Devuelve None si no tiene un sitio válido."""
		usados = {p.id for p in self.premios}
		limpio = normalizar_premio(dato, len(self.premios) + 1, usados)
		if limpio is None:
			return None
		premio = self._premio_de(limpio, extra=extra)
		self._situar_premio(sesion, premio)
		if not premio.colocado:
			return None
		self.premios.append(premio)
		self._refrescar_fuentes(sesion)
		return premio

	# ── El travieso ──

	def _tic_travieso(self, sesion: Any) -> None:
		"""De vez en cuando cambia de sitio un premio sin recoger, para que haya que volver a recorrer."""
		travieso = self.datos["travieso"]
		if not travieso["activo"] or self.es_examen or self._travesuras >= travieso["veces"]:
			return
		if sesion.t - self._t_travieso < travieso["cada_s"]:
			return
		self._t_travieso = sesion.t
		candidatos = [p for p in self.premios_pendientes() if self._premio_disponible(p) and self._se_puede_mover(p)]
		if not candidatos:
			return
		premio = self.azar.choice(candidatos)
		destino = self._sitio_nuevo(sesion, premio)
		if destino is None:
			return
		premio.planta, premio.x, premio.y = destino
		premio.dentro_de = None
		premio.acceso = None
		if premio.sonando:
			sesion.quitar_fuente(premio.fuente)
			premio.sonando = False
		self._travesuras += 1
		self._pistas_dadas.pop(premio.id, None)
		self._refrescar_fuentes(sesion)
		sesion.registrar("travieso", id=premio.id, nombre=premio.nombre, a=[destino[0], round(destino[1], 2), round(destino[2], 2)])
		sesion.sonar("logro/error", bus="efectos")
		self._decir(sesion, self.tx("travieso"), clave="travieso")

	def _se_puede_mover(self, premio: Premio) -> bool:
		"""Si el travieso puede llevarse ese premio."""
		return True

	def _sitio_nuevo(self, sesion: Any, premio: Premio) -> tuple[str, float, float] | None:
		"""Un punto libre en otro espacio al que se pueda llegar, lejos del alumno."""
		jugador = sesion.jugador
		alcanzables = sesion.nav.espacios_alcanzables((jugador.planta, jugador.x, jugador.y))
		actual = sesion.mundo.espacio_en(premio.planta, premio.x, premio.y)
		donde_alumno = sesion.movimiento.espacio_id or ""
		candidatos = [
			(planta, espacio)
			for planta, espacio in espacios_jugables(self.entorno)
			if espacio.id in alcanzables and espacio.id != donde_alumno and (actual is None or espacio.id != actual.id)
		]
		self.azar.shuffle(candidatos)
		for planta, espacio in candidatos:
			punto = punto_libre_en(sesion.mundo, planta.id, espacio, self.azar)
			if punto is not None:
				return planta.id, punto[0], punto[1]
		return None

	# ── Exploración ──

	def _espacios_a_explorar(self, sesion: Any) -> list[str]:
		"""Ids de los espacios jugables a los que se puede llegar desde el inicio de la sesión (se calcula una vez)."""
		if self._explorables is None:
			alcanzables = sesion.nav.espacios_alcanzables(sesion.inicio)
			self._explorables = [
				espacio.id for _planta, espacio in espacios_jugables(self.entorno) if not alcanzables or espacio.id in alcanzables
			]
		return self._explorables

	def _exploracion(self, sesion: Any) -> float:
		"""Parte (0 a 1) de los espacios alcanzables en la que ya se ha entrado."""
		todos = self._espacios_a_explorar(sesion)
		if not todos:
			return 1.0
		visitados = sesion.movimiento.visitados
		return round(sum(1 for ident in todos if ident in visitados) / len(todos), 3)

	# ── Avance, tropiezos y ayuda ofrecida ──

	def _avance(self, sesion: Any) -> None:
		"""Algo ha salido bien: se olvida la racha de tropiezos."""
		self._t_progreso = sesion.t
		self._fallos_seguidos = 0
		self._t_choques.clear()

	def _logro(self, sesion: Any, ident: str, nombre: str, texto: str | None = None, celebrar: bool = True) -> None:
		"""Un objetivo conseguido: se registra para el seguimiento y, fuera de examen, se celebra."""
		self.hechos += 1
		self._logros.append({"id": ident, "nombre": nombre, "t": round(sesion.t, 2)})
		sesion.registrar("objetivo", id=ident, nombre=nombre)
		self._avance(sesion)
		if celebrar:
			self._celebrar(sesion, texto if texto is not None else (self.datos["mensajes"]["logro"] or self.tx("logro")))

	def _al_chocar(self, sesion: Any) -> None:
		"""Chocar informa (lo hace el motor) y no elimina; muchos choques seguidos son señal de atasco."""
		self._t_choques = [t for t in self._t_choques if sesion.t - t <= VENTANA_CHOQUES]
		self._t_choques.append(sesion.t)
		if len(self._t_choques) >= CHOQUES_SEGUIDOS:
			self._t_choques.clear()
			self._fallo(sesion, "choques")

	def _fallo(self, sesion: Any, motivo: str) -> None:
		"""Un tropiezo. Tras varios seguidos se ofrece ayuda en vez de insistir (nunca en examen)."""
		self._fallos += 1
		self._fallos_seguidos += 1
		umbral = self.datos["fallos_para_ayuda"]
		if not self.es_examen and umbral > 0 and self._fallos_seguidos >= umbral:
			self._fallos_seguidos = 0
			self._ofrecer_ayuda(sesion, motivo)

	def _ofrecer_ayuda(self, sesion: Any, motivo: str) -> None:
		if self.es_examen:
			return
		self._ayuda_ofrecida = True
		self._ayudas_ofrecidas += 1
		regla = sesion.ajustes.ayudas.get("pista")
		if isinstance(regla, dict) and not sesion.percepcion.permitida("pista"):
			# La ayuda que se ofrece tiene que poder usarse: se levanta el límite de pistas.
			sesion.permitir_ayuda("pista", True, None)
		sesion.registrar("ayuda_ofrecida", motivo=motivo)
		sesion.sonar("logro/pista", bus="ayudas")
		amigo = self.acompanante()
		animo = f"{self.tx('acompanante_anima', amigo=amigo)} " if amigo else ""
		self._decir(sesion, f"{animo}{self.tx('ofrecer_ayuda')}", clave="ofrecer")

	# ── Pistas y baliza ──

	def _dar_pista(self, sesion: Any) -> str:
		"""Texto de la pista para el objetivo actual; cada vez que se pide dice un poco más."""
		lugar = self._lugar_actual()
		if lugar is None:
			return ""
		clave = lugar.elemento_id or f"{lugar.planta}:{lugar.x:.1f}:{lugar.y:.1f}"
		veces = self._pistas_dadas.get(clave, 0) + 1
		self._pistas_dadas[clave] = veces
		detalle = min(3, veces + (1 if self._ayuda_ofrecida else 0))
		texto = self._texto_pista(sesion, lugar, detalle)
		if self.modo_baliza() in ("al_pedir", "siempre") or self._ayuda_ofrecida:
			if self._encender_baliza_temporal(sesion, lugar, SEGUNDOS_BALIZA, forzar=self._ayuda_ofrecida):
				texto = f"{texto} {self.tx('baliza_un_rato')}".strip()
		self._ayuda_ofrecida = False
		return texto

	def _texto_pista(self, sesion: Any, lugar: Lugar, detalle: int) -> str:
		premio = next((p for p in self.premios if p.id == lugar.elemento_id and lugar.clase == "premio"), None)
		if premio is not None and premio.pista and detalle == 1:
			return premio.pista
		return pista_de_lugar(self.entorno, sesion.nav, lugar, detalle, premio.dentro_de or "" if premio is not None else "")

	def _guiar(self, sesion: Any, lugar: Lugar | None) -> None:
		"""Fija el destino actual. Con la baliza «siempre» (primer nivel) la enciende paso a paso hacia él."""
		self._destino_guia = lugar
		if self._baliza_hasta is not None:
			self._apagar_baliza_temporal(sesion)
		if lugar is None:
			sesion.baliza(None)
			return
		if self.modo_baliza() == "siempre" and sesion.percepcion.permitida("baliza"):
			if sesion.baliza(lugar.terna, por_ruta=True):
				self._baliza_continua = True
		else:
			sesion.baliza(None)

	def _encender_baliza_temporal(self, sesion: Any, lugar: Lugar, segundos: float, forzar: bool = False) -> bool:
		"""Enciende la baliza hacia un lugar durante un rato. ``forzar`` la permite aunque el nivel la haya retirado."""
		if self.modo_baliza() == "siempre" and self._baliza_continua and not forzar:
			return False
		if not sesion.percepcion.permitida("baliza"):
			if not forzar:
				return False
			if self._baliza_regla_previa is None:
				self._baliza_regla_previa = dict(sesion.ajustes.ayudas.get("baliza") or {"permitida": True, "limite": None})
			sesion.permitir_ayuda("baliza", True, None)
		if not sesion.baliza(lugar.terna):
			return False
		self._baliza_hasta = sesion.t + max(1.0, segundos)
		return True

	def _apagar_baliza_temporal(self, sesion: Any) -> None:
		self._baliza_hasta = None
		previa = self._baliza_regla_previa
		self._baliza_regla_previa = None
		if previa is not None:
			sesion.permitir_ayuda("baliza", bool(previa.get("permitida", True)), previa.get("limite"))
		destino = self._destino_guia
		if destino is not None and self.modo_baliza() == "siempre" and sesion.percepcion.permitida("baliza"):
			sesion.baliza(destino.terna, por_ruta=True)
		else:
			sesion.baliza(None)

	# ── Camino real frente al más corto ──

	def _abrir_tramo(self, sesion: Any, destino: Lugar | None, evitar: tuple[str, ...] = (), optimo: float | None = None) -> None:
		"""Empieza a medir un tramo: lo que se ande desde aquí se comparará con el camino más corto hasta ``destino``."""
		self._cerrar_tramo(sesion)
		jugador = sesion.jugador
		if optimo is None and destino is not None:
			optimo = sesion.nav.distancia((jugador.planta, jugador.x, jugador.y), destino.terna, evitar)
		self._tramo = {"optimo": optimo, "desde": sesion.movimiento.distancia, "destino": destino.nombre if destino is not None else ""}

	def _cerrar_tramo(self, sesion: Any, cuenta: bool = True) -> dict[str, Any] | None:
		"""Termina el tramo en curso y devuelve lo medido (real, óptimo y cociente)."""
		tramo = self._tramo
		self._tramo = None
		if tramo is None:
			return None
		real = max(0.0, sesion.movimiento.distancia - tramo["desde"])
		medido = {
			"destino": tramo["destino"],
			"real_m": round(real, 2),
			"optimo_m": round(tramo["optimo"], 2) if tramo["optimo"] is not None else None,
			"cociente": puntuacion.cociente_camino(real, tramo["optimo"]),
		}
		if cuenta:
			self._tramos.append(medido)
		return medido

	def _camino(self) -> tuple[float | None, float | None, float | None]:
		"""(real, óptimo, cociente) sumando los tramos medidos que tienen óptimo."""
		con_optimo = [t for t in self._tramos if t["optimo_m"]]
		if not con_optimo:
			return None, None, None
		real = sum(t["real_m"] for t in con_optimo)
		optimo = sum(t["optimo_m"] for t in con_optimo)
		return round(real, 2), round(optimo, 2), puntuacion.cociente_camino(real, optimo)

	# ── Final ──

	def _terminar(self, sesion: Any, completada: bool, motivo: str = "") -> None:
		"""Cierra la actividad y termina la sesión."""
		if self._cerrada:
			return
		self._cerrar(sesion, completada, motivo or ("completada" if completada else "sin_completar"))
		sesion.terminar()

	def _ayudas_usadas(self, sesion: Any) -> dict[str, int]:
		usos = sesion.percepcion.usos
		return {ayuda: n - self._usos_inicio.get(ayuda, 0) for ayuda, n in usos.items() if n - self._usos_inicio.get(ayuda, 0) > 0}

	def _nivel_superado(self, sesion: Any, completada: bool) -> bool:
		"""Se supera el nivel completando la actividad sin pedir pistas, sin ayuda ofrecida y sin pistas del profesional."""
		if not self.niveles or not completada:
			return False
		usos = self._ayudas_usadas(sesion)
		return usos.get("pista", 0) == 0 and self._ayudas_ofrecidas == 0 and self._intervenciones.get("pista", 0) == 0

	def _cerrar(self, sesion: Any, completada: bool, motivo: str) -> None:
		"""Calcula el resultado, apunta las recompensas y dice el mensaje final."""
		self._cerrada = True
		self.completada = completada
		self.motivo = motivo
		self._cerrar_tramo(sesion)
		if self._baliza_hasta is not None:
			self._apagar_baliza_temporal(sesion)
		sesion.baliza(None)
		for premio in self.premios:
			if premio.sonando:
				sesion.quitar_fuente(premio.fuente)
				premio.sonando = False
		self._al_cerrar(sesion)
		usos = self._ayudas_usadas(sesion)
		ayudas = max(0, puntuacion.ayudas_contadas(usos) - self._ayudas_no_contadas) + self._intervenciones.get("pista", 0)
		choques = sesion.movimiento.choques - self._choques_inicio
		real, optimo, cociente = self._camino()
		propios = self._datos_estrellas(sesion)
		motivos = (
			[]
			if self.es_examen
			else puntuacion.estrellas(
				completada,
				self.ESTRELLAS,
				ayudas=ayudas,
				cociente=cociente,
				media_salida=propios.get("media_salida"),
				choques=choques,
				exploracion=propios.get("exploracion"),
				seguro=propios.get("seguro"),
				con_baliza_continua=self._baliza_continua,
			)
		)
		superado = self._nivel_superado(sesion, completada)
		siguiente = min(self.nivel + 1, max(0, len(self.niveles) - 1)) if superado else self.nivel
		puntuaciones = self._puntuaciones(sesion)
		examen = puntuaciones if self.es_examen else None
		resultado: dict[str, Any] = {
			"actividad": {"id": self.id, "nombre": self.nombre, "tipo": self.tipo, "modo": self.modo, "estilo": self.estilo},
			"completada": completada,
			"motivo": motivo,
			"objetivos_hechos": self.hechos,
			"objetivos_total": self.total,
			"objetivos": list(self._logros),
			"puntos": self.puntos,
			"puntos_maximos": self.puntos_maximos,
			"estrellas": len(motivos),
			"estrellas_motivos": motivos,
			"estrellas_posibles": [] if self.es_examen else list(self.ESTRELLAS),
			"estrellas_previas": self.datos["recompensas"]["estrellas_previas"],
			"desbloqueos": list(self.datos["recompensas"]["desbloqueos"]),
			"coleccion": list(self.coleccion),
			"premios": [
				{"id": p.id, "nombre": p.nombre, "recogido": p.recogido, "t": p.t_recogido, "extra": p.extra} for p in self.premios
			],
			"camino_real_m": real,
			"camino_optimo_m": optimo,
			"cociente_camino": cociente,
			"tramos": list(self._tramos),
			"tiempo_juego_s": round(sesion.t - self._t0(), 2),
			"tiempo_limite_s": self.datos.get("tiempo_limite_s"),
			"fuera_de_tiempo": motivo == "tiempo",
			"choques_actividad": choques,
			"ayudas_usadas": usos,
			"ayudas_contadas": ayudas,
			"ayudas_ofrecidas": self._ayudas_ofrecidas,
			"fallos": self._fallos,
			"travesuras": self._travesuras,
			"intervenciones_profesional": dict(self._intervenciones),
			"nivel": self.nivel,
			"nivel_nombre": self.nombre_nivel(self.nivel),
			"nivel_superado": superado,
			"nivel_siguiente": siguiente,
			"baliza_continua": self._baliza_continua,
			"examen": examen,
			"puntuaciones": puntuaciones,
			"valoracion": None,
			"cuestionario": cuestionario.preguntas(self.estilo) if self.datos["cuestionario"] else [],
			"semilla_actividad": self.semilla,
			"aviso": _(AVISO_RESULTADO),
		}
		resultado.update(self._detalle(sesion))
		resultado["recompensas"] = recompensas.calcular(resultado, self.estilo)
		resultado["medallas"] = [r["nombre"] for r in resultado["recompensas"] if r["tipo"] == "medalla"]
		self._resultado = resultado
		for recompensa in resultado["recompensas"]:
			sesion.registrar("recompensa", tipo=recompensa["tipo"], nombre=recompensa["nombre"], motivo=recompensa.get("motivo", ""))
		if puntuaciones is not None:
			sueltos = {clave: valor for clave, valor in puntuaciones.items() if not isinstance(valor, (list, dict))}
			sesion.registrar("puntuacion", actividad=self.id, tipo_actividad=self.tipo, **sueltos)
		self._despedir(sesion, resultado)

	def _al_cerrar(self, sesion: Any) -> None:
		"""Último retoque del tipo antes de calcular el resultado (cerrar la prueba en curso de un examen)."""

	def _despedir(self, sesion: Any, resultado: dict[str, Any]) -> None:
		"""Mensaje y sonidos finales. Un examen se despide sin valorar; el resto celebra lo conseguido."""
		if self.es_examen:
			partes = [self.datos["mensajes"]["final"] or self.tx("examen_fin")]
			if self.datos.get("decir_resultado"):
				partes.append(self._texto_resultado_examen(resultado))
			self._decir(sesion, " ".join(p for p in partes if p), clave="final", caduca=60.0)
			return
		estrellas = resultado["estrellas"]
		if resultado["completada"]:
			texto = self.datos["mensajes"]["final"] or self.tx("final_bien")
		elif resultado["motivo"] == "tiempo":
			texto = self.tx("final_tiempo")
		elif resultado["motivo"] == "abandonada":
			texto = ""
		else:
			texto = self.tx("final_incompleto")
		partes = [texto]
		if estrellas:
			sesion.sonar(f"logro/estrella_{min(3, estrellas)}", bus="efectos")
			partes.append(_n("Has ganado {n} estrella.", "Has ganado {n} estrellas.", estrellas).format(n=estrellas))
		for medalla in resultado["medallas"]:
			partes.append(_("Y una medalla: {nombre}.").format(nombre=medalla))
		if resultado["medallas"]:
			sesion.sonar("logro/medalla", bus="efectos", retardo=1.4)
		desbloqueados = [r["nombre"] for r in resultado["recompensas"] if r.get("motivo") == "desbloqueo"]
		for nombre in desbloqueados:
			partes.append(self.tx("desbloqueo", nombre=nombre))
		if resultado["nivel_superado"] and resultado["nivel_siguiente"] != resultado["nivel"]:
			partes.append(self.tx("nivel_sube", nivel=self.nombre_nivel(resultado["nivel_siguiente"])))
		if self.estilo == "juvenil" and resultado["completada"]:
			partes.append(self.tx("marca", tiempo=self.tx.duracion(resultado["tiempo_juego_s"])))
		self._decir(sesion, " ".join(p for p in partes if p), clave="final", caduca=60.0)

	def _texto_resultado_examen(self, resultado: dict[str, Any]) -> str:
		examen = resultado.get("examen") or {}
		return _("Aciertos: {aciertos} de {total}.").format(aciertos=examen.get("aciertos", 0), total=examen.get("pruebas_hechas", 0))

	def nombre_nivel(self, nivel: int) -> str:
		"""Nombre hablado de un nivel de ayudas; vacío si la actividad no tiene niveles."""
		if not self.niveles or not 0 <= nivel < len(self.niveles):
			return ""
		nombre = self.niveles[nivel].get("nombre") or ""
		return _(nombre) if nombre else _("nivel {n}").format(n=nivel + 1)

	# ── Valoración subjetiva ──

	def valorar(self, sesion: Any, respuestas: Any) -> dict[str, Any]:
		"""Apunta las respuestas del cuestionario final (esfuerzo, confianza, disfrute) con un registro ``valoracion``.

		Se puede llamar después de terminada la sesión: el registro sale en
		el siguiente ``avanzar``. Devuelve las respuestas ya normalizadas.
		"""
		limpias = cuestionario.normalizar_respuestas(respuestas)
		self._valoracion = dict(limpias)
		if self._resultado is not None:
			self._resultado["valoracion"] = dict(limpias)
		if isinstance(getattr(sesion, "resultado", None), dict) and sesion.resultado:
			sesion.resultado["valoracion"] = dict(limpias)
		sesion.registrar("valoracion", actividad=self.id, **limpias)
		return limpias

	# ── Estado ──

	def estado(self) -> dict[str, Any]:
		"""Foto de la actividad para el reproductor y la supervisión."""
		resultado = self._resultado or {}
		return {
			"id": self.id,
			"tipo": self.tipo,
			"modo": self.modo,
			"objetivo": self.texto_objetivo() if not self._cerrada else "",
			"hechos": self.hechos,
			"total": self.total,
			"puntos": self.puntos,
			"puntos_maximos": self.puntos_maximos,
			"estrellas": int(resultado.get("estrellas", 0)),
			"tiempo_restante": self.tiempo_restante(),
			"nivel": self.nivel,
			"nivel_nombre": self.nombre_nivel(self.nivel),
			"fase": self.fase,
			"premios_pendientes": len(self.premios_pendientes(True)),
			"pregunta": self.pregunta(),
			"terminada": self._cerrada,
			"completada": self.completada,
		}

	def pregunta(self) -> dict[str, Any] | None:
		"""Pregunta con opciones que espera respuesta (solo en los exámenes de preguntas); None si no hay."""
		return None

	def confirmar(self, sesion: Any) -> list[Evento]:
		"""El alumno confirma («ya he llegado», «es hacia ahí», «esta respuesta»). Por defecto no hay nada que confirmar."""
		return []

	def responder(self, sesion: Any, opcion: int) -> list[Evento]:
		"""Elige una opción de la pregunta en curso (los exámenes de preguntas lo redefinen)."""
		return []

	# ── Órdenes del profesional ──

	def orden_profesional(self, sesion: Any, tipo: str, datos: dict[str, Any] | None) -> list[Evento]:
		"""Atiende una orden de la supervisión: ``pista``, ``premio``, ``ayudas`` o ``mensaje``.

		Devuelve los eventos que hay que presentar al alumno (voz por el
		canal «profesional», un sonido). NO se han emitido en la sesión: quien
		llama los presenta o se los pasa a ``sesion.emitir``. Los cambios de
		estado (un premio nuevo, una baliza, un permiso) sí quedan hechos.
		"""
		datos = datos if isinstance(datos, dict) else {}
		self._intervenciones[tipo] = self._intervenciones.get(tipo, 0) + 1
		eventos: list[Evento] = []
		if tipo == "mensaje":
			texto = str(datos.get("texto") or "").strip()
			if texto:
				eventos.append(ev.EvVoz(texto, False, "profesional"))
		elif tipo == "ayudas":
			reglas = datos.get("ayudas") if isinstance(datos.get("ayudas"), dict) else {}
			for ayuda, regla in reglas.items():
				completa = regla_ayuda(regla)
				sesion.permitir_ayuda(str(ayuda), completa["permitida"], completa["limite"])
			if reglas:
				eventos.append(ev.EvSonido("interfaz/ajuste", bus="interfaz"))
		elif tipo == "pista":
			eventos.extend(self._pista_profesional(sesion, datos))
		elif tipo == "premio":
			eventos.extend(self._premio_profesional(sesion, datos))
		else:
			log.warning("Orden del profesional que la actividad no atiende: %s", tipo)
			self._intervenciones[tipo] -= 1
		return eventos

	def _pista_profesional(self, sesion: Any, datos: dict[str, Any]) -> list[Evento]:
		destino = self.lugar(datos.get("destino")) if datos.get("destino") else self._lugar_actual()
		texto = str(datos.get("texto") or "").strip()
		if not texto and destino is not None:
			texto = pista_de_lugar(self.entorno, sesion.nav, destino, 2)
		eventos: list[Evento] = [ev.EvSonido("logro/pista", bus="ayudas")]
		if texto:
			eventos.append(ev.EvVoz(texto, False, "profesional"))
		try:
			segundos = float(datos.get("baliza_s") or 0.0)
		except TypeError, ValueError:
			segundos = 0.0
		if segundos > 0.0 and destino is not None:
			# El profesional manda: la baliza se enciende aunque el nivel o el examen la tengan retirada, y queda anotado.
			self._encender_baliza_temporal(sesion, destino, min(600.0, segundos), forzar=True)
		sesion.registrar("pista_profesional", baliza_s=round(segundos, 1), con_texto=bool(texto))
		self._pista_dada_por_profesional(sesion)
		return eventos

	def _pista_dada_por_profesional(self, sesion: Any) -> None:
		"""Para que un examen marque la prueba en curso como hecha con ayuda."""

	def _premio_profesional(self, sesion: Any, datos: dict[str, Any]) -> list[Evento]:
		dato = dict(datos)
		if dato.get("x") is None or dato.get("y") is None or not dato.get("planta"):
			# Sin lugar: se deja en un punto libre del espacio donde está el alumno, a unos pasos.
			jugador = sesion.jugador
			espacio = sesion.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
			punto = punto_libre_en(sesion.mundo, jugador.planta, espacio, self.azar) if espacio is not None else None
			if punto is None:
				return [ev.EvSonido("logro/error", bus="interfaz")]
			dato.update({"planta": jugador.planta, "x": punto[0], "y": punto[1]})
		dato.setdefault("visibilidad", "lejos")
		premio = self._anadir_premio(sesion, dato, extra=not self.PREMIOS_OBLIGATORIOS)
		if premio is None:
			return [ev.EvSonido("logro/error", bus="interfaz")]
		if self.PREMIOS_OBLIGATORIOS:
			self.total += 1
			self._premio_anadido(sesion, premio)
		sesion.registrar("premio_nuevo", id=premio.id, nombre=premio.nombre)
		eventos: list[Evento] = [ev.EvSonido("premio/aparece", pos=(premio.x, premio.y, sesion.mundo.altura(premio.planta) + 1.0))]
		if not self.es_examen:
			eventos.append(ev.EvVoz(self.tx("premio_nuevo", nombre=premio.nombre), False, "profesional"))
		return eventos


def info_de(actividad: Actividad) -> Any:
	"""Ficha del tipo de una actividad (``InfoTipo``), o None si el tipo no se conoce."""
	return TIPOS.get(actividad.tipo)
