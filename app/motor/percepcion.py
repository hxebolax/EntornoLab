"""Ayudas de percepción: lo que el alumno puede preguntar y lo que se le avisa solo.

Cada ayuda tiene un NOMBRE estable (``AYUDAS``) con el que la actividad puede
permitirla, prohibirla o limitar cuántas veces se usa
(``AjustesJuego.ayudas``). Cada uso deja un ``EvRegistro`` de tipo «ayuda»,
porque cuántas ayudas necesitó el alumno es uno de los datos del seguimiento.

Aquí vive también el descubrimiento progresivo: el motor recuerda qué
espacios, objetos, puertas y referencias ha percibido ya el alumno (por haber
entrado, por haberlos tocado o por tenerlos a la vista) y cuánto ha recorrido
de cada espacio, para poder decirle «lugares que conoces» sin revelarle nada
que no haya encontrado él.

Los avisos automáticos de proximidad (una referencia, una boca de escalera,
un paso de peatones, un cruce) no se repiten mientras no pase un tiempo o el
alumno no se aleje, y dependen del nivel de detalle (0 a 3).
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from app.core.i18n import _, _n
from app.dominio import geometria as geo
from app.dominio.geometria import Punto
from app.dominio.modelo import Espacio
from app.exportar import fichas
from app.motor import eventos as ev
from app.motor import lenguaje
from app.motor.mundo import TIPOS_CALZADA, Impacto

if TYPE_CHECKING:
	from app.motor.sesion import Sesion

log = logging.getLogger(__name__)

# Nombres de las ayudas (claves de ``AjustesJuego.ayudas``).
AYUDAS: tuple[str, ...] = (
	"donde_estoy",
	"descripcion",
	"mirar",
	"delante",
	"alrededor",
	"sonda",
	"cercanos",
	"descubiertos",
	"brujula",
	"eco",
	"objetivo",
	"pista",
	"baliza",
	"avisos",
)

ALCANCE_MIRAR = 20.0
ALCANCE_ECO = 30.0
RADIO_CERCANOS = 20.0
INTERVALO_SONDA = 0.11
# Un espacio se da por explorado cuando se ha percibido esta parte de él.
FRACCION_EXPLORADO = 0.85
RADIO_PERCEPCION = 2.5
MAX_MUESTRAS = 150
MAX_AVISOS_SEGUIDOS = 2


@dataclass
class Conocido:
	"""Lo que el alumno sabe de un espacio."""

	espacio: Espacio
	planta_id: str
	visitado: bool = False
	muestras: list[Punto] = field(default_factory=list)
	vistas: set[int] = field(default_factory=set)

	@property
	def explorado(self) -> float:
		"""Parte del espacio ya percibida, de 0 a 1."""
		return len(self.vistas) / len(self.muestras) if self.muestras else (1.0 if self.visitado else 0.0)

	@property
	def completo(self) -> bool:
		"""Si se da por explorado del todo."""
		return self.visitado and self.explorado >= FRACCION_EXPLORADO


@dataclass
class Cosa:
	"""Algo que se puede nombrar y situar: un objeto, una puerta, una referencia, una fuente, una escalera."""

	clase: str
	id: str
	nombre: str
	punto: Punto
	distancia: float
	relativo: float
	elemento: Any = None
	camino: float | None = None
	visible: bool = True


def _caja_tramo(a: Punto, b: Punto, margen: float = 0.01) -> tuple[float, float, float, float]:
	"""Caja de un tramo, con un pelo de margen: lo que lo corta tiene que tocarla."""
	return min(a[0], b[0]) - margen, min(a[1], b[1]) - margen, max(a[0], b[0]) + margen, max(a[1], b[1]) + margen


def _muestras_de(espacio: Espacio) -> list[Punto]:
	"""Puntos repartidos por el interior de un espacio, para medir cuánto se ha recorrido."""
	x0, y0, x1, y1 = espacio.caja()
	area = max(1.0, espacio.area())
	paso = max(1.0, math.sqrt(area / MAX_MUESTRAS))
	puntos: list[Punto] = []
	columnas = max(1, int((x1 - x0) / paso))
	filas = max(1, int((y1 - y0) / paso))
	for i in range(columnas):
		for j in range(filas):
			punto = (x0 + (i + 0.5) * (x1 - x0) / columnas, y0 + (j + 0.5) * (y1 - y0) / filas)
			if geo.punto_en_poligono(punto, espacio.contorno):
				puntos.append(punto)
	return puntos or [espacio.centro()]


class Percepcion:
	"""Responde a las preguntas del alumno y da los avisos automáticos."""

	def __init__(self, sesion: Sesion) -> None:
		self.s = sesion
		self.usos: dict[str, int] = {}
		self.conocidos: dict[str, Conocido] = {}
		self.objetos: set[str] = set()
		self.aberturas: set[str] = set()
		self.referencias: set[str] = set()
		self.conectores: set[str] = set()
		self.avisados: dict[tuple, tuple[float, float, float]] = {}
		self.avisos_dados = 0
		self._ultimo_punto: tuple[str, float, float] | None = None
		self._t_donde = -100.0
		self._cercanos: list[Cosa] = []
		self._indice_cercano = -1
		self._cercanos_en: tuple[str, float, float, float, int] | None = None
		self._sonda_mantenida = False
		self._t_sonda = 0.0
		self._mirada: float | None = None
		self._pasos_planta: dict[str, tuple[Any, list[tuple[tuple[float, float, float, float], Espacio]]]] = {}

	# ── Permisos ──

	def permitida(self, ayuda: str) -> bool:
		"""Si la ayuda está permitida y le quedan usos (sin gastar ninguno)."""
		regla = self.s.ajustes.ayudas.get(ayuda)
		if not isinstance(regla, dict):
			return True
		if not regla.get("permitida", True):
			return False
		limite = regla.get("limite")
		return limite is None or self.usos.get(ayuda, 0) < int(limite)

	def restantes(self, ayuda: str) -> int | None:
		"""Usos que quedan de una ayuda limitada; None si no tiene límite."""
		regla = self.s.ajustes.ayudas.get(ayuda)
		if not isinstance(regla, dict) or regla.get("limite") is None:
			return None
		return max(0, int(regla["limite"]) - self.usos.get(ayuda, 0))

	def usar(self, ayuda: str) -> bool:
		"""Gasta un uso de la ayuda y lo registra; si no se puede, lo dice y devuelve False."""
		s = self.s
		regla = s.ajustes.ayudas.get(ayuda)
		if isinstance(regla, dict):
			motivo = ""
			if not regla.get("permitida", True):
				motivo = "prohibida"
			elif regla.get("limite") is not None and self.usos.get(ayuda, 0) >= int(regla["limite"]):
				motivo = "agotada"
			if motivo:
				s.sonar("interfaz/borde", bus="interfaz")
				s.decir(s.leng.tono("ayuda_no" if motivo == "prohibida" else "ayuda_agotada"), canal="ayuda", pedida=True, clave="ayuda")
				s.registrar("ayuda_denegada", ayuda=ayuda, motivo=motivo)
				return False
		self.usos[ayuda] = self.usos.get(ayuda, 0) + 1
		s.registrar("ayuda", ayuda=ayuda, uso=self.usos[ayuda], restantes=self.restantes(ayuda))
		return True

	# ── Órdenes ──

	def orden(self, accion: str, pulsada: bool) -> bool:
		"""Atiende una orden de percepción. Devuelve False si la acción no es suya."""
		if accion == "sonda":
			self._sonda_mantenida = pulsada
			if pulsada:
				self.sonda()
			return True
		if accion not in (
			"donde_estoy",
			"mirar_delante",
			"mirar_izquierda",
			"mirar_detras",
			"mirar_derecha",
			"alrededor",
			"cercano_siguiente",
			"cercano_anterior",
			"descubiertos",
			"brujula",
			"eco",
		):
			return False
		if not pulsada:
			return True
		if accion == "donde_estoy":
			self.donde_estoy()
		elif accion == "mirar_delante":
			self.delante()
		elif accion == "mirar_izquierda":
			self.mirar(-90.0)
		elif accion == "mirar_detras":
			self.mirar(180.0)
		elif accion == "mirar_derecha":
			self.mirar(90.0)
		elif accion == "alrededor":
			self.alrededor()
		elif accion == "cercano_siguiente":
			self.cercano(1)
		elif accion == "cercano_anterior":
			self.cercano(-1)
		elif accion == "descubiertos":
			self.descubiertos()
		elif accion == "brujula":
			self.brujula()
		elif accion == "eco":
			self.eco()
		return True

	def mirada(self, direccion: tuple[float, float] | None) -> None:
		"""Palanca de mirar: al apuntar en una dirección nueva, dice qué hay hacia allí."""
		if direccion is None or math.hypot(direccion[0], direccion[1]) < 0.6:
			if direccion is None or math.hypot(direccion[0], direccion[1]) < 0.3:
				self._mirada = None
			return
		angulo = round(math.degrees(math.atan2(direccion[0], direccion[1])) / 45.0) * 45.0
		angulo = lenguaje.normalizar_relativo(angulo)
		if self._mirada is not None and abs(lenguaje.normalizar_relativo(angulo - self._mirada)) < 1.0:
			return
		self._mirada = angulo
		self.mirar(angulo)

	def tic(self, dt: float) -> None:
		"""Repite la sonda mientras se mantiene pulsada."""
		if self._sonda_mantenida and self.s.t >= self._t_sonda:
			self.sonda(contar=False)

	# ── Dónde estoy ──

	def texto_donde(self) -> str:
		"""Espacio, planta y rumbo. Nunca la ruta: orientarse es cosa del alumno."""
		s = self.s
		jugador = s.jugador
		movimiento = s.movimiento
		planta = s.mundo.planta(jugador.planta)
		nombre_planta = s.leng.planta(planta.planta if planta is not None else None)
		varias = len(s.mundo.entorno.plantas) > 1
		if jugador.modo == "ascensor":
			return _("Estás dentro del ascensor, en {planta}.").format(planta=nombre_planta)
		if jugador.modo == "conector" and movimiento.en_tramo is not None:
			tramo = movimiento.en_tramo
			nombre = s.leng.conector(tramo.conector)
			hechos = round(tramo.progreso if tramo.sentido > 0 else tramo.total - tramo.progreso)
			if tramo.sentido > 0:
				return _("Estás en {escalera}, subiendo. Llevas {n} de {total}.").format(escalera=nombre, n=hechos, total=tramo.total)
			return _("Estás en {escalera}, bajando. Llevas {n} de {total}.").format(escalera=nombre, n=hechos, total=tramo.total)
		espacio = s.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		if espacio is None:
			lugar = _("Estás fuera del entorno")
		elif espacio.datos.get("terreno_base"):
			lugar = _("Estás en una zona que el mapa no detalla")
		else:
			lugar = _("Estás en {espacio}").format(espacio=s.leng.espacio(espacio))
		if varias:
			lugar += ", " + nombre_planta
		return _("{lugar}, mirando {rumbo}.").format(lugar=lugar, rumbo=s.leng.al_cardinal(jugador.rumbo))

	def donde_estoy(self) -> None:
		"""Dice dónde está y hacia dónde mira; pedida dos veces seguidas, añade la descripción del lugar."""
		s = self.s
		if not self.usar("donde_estoy"):
			return
		repetida = s.t - self._t_donde < 4.0
		self._t_donde = s.t
		texto = self.texto_donde()
		if repetida and self.permitida("descripcion"):
			descripcion = self.texto_descripcion()
			if descripcion:
				texto += " " + descripcion
		s.decir(texto, canal="ayuda", pedida=True, clave="donde")

	def texto_descripcion(self) -> str:
		"""Descripción del espacio actual: la que escribió el profesional, su suelo y cuántas salidas tiene."""
		s = self.s
		jugador = s.jugador
		espacio = s.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		if espacio is None:
			return ""
		partes: list[str] = []
		if espacio.descripcion:
			partes.append(lenguaje.frase(espacio.descripcion))
		partes.append(_("Suelo de {suelo}.").format(suelo=s.leng.suelo(espacio.suelo).lower()))
		salidas = len([e for e in s.nav.enlaces(espacio.id) if e.tipo == "abertura"])
		if salidas:
			partes.append(_n("Tiene {n} puerta o paso.", "Tiene {n} puertas o pasos.", salidas).format(n=salidas))
		return " ".join(partes)

	def describir(self) -> None:
		"""Describe el espacio actual a petición."""
		if not self.usar("descripcion"):
			return
		s = self.s
		espacio = s.mundo.espacio_en(s.jugador.planta, s.jugador.x, s.jugador.y)
		texto = self.texto_descripcion() or _("No hay descripción de este lugar.")
		if espacio is not None:
			texto = s.leng.espacio(espacio) + ". " + texto
		s.decir(texto, canal="ayuda", pedida=True, clave="descripcion")

	# ── Mirar ──

	def _hallazgos_en_rayo(self, rumbo: float, tope: float) -> list[tuple[float, str, str]]:
		"""Lo que se cruza antes del obstáculo: aberturas abiertas, cambios de espacio y de suelo, escaleras.

		Devuelve (distancia, clase, texto) por orden de distancia.
		"""
		s = self.s
		jugador = s.jugador
		mundo = s.mundo
		origen = jugador.punto
		fin = geo.punto_a_distancia(origen, rumbo, tope)
		hallazgos: list[tuple[float, str, str]] = []
		espacio_actual = mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		indice = mundo.planta(jugador.planta)
		cruzadas: list[float] = []
		if indice is not None:
			# Solo las aberturas cuya caja toca la del rayo pueden cortarlo (en el mismo orden que la lista entera).
			caja_rayo = _caja_tramo(origen, fin)
			for info in mundo.aberturas_en_caja(jugador.planta, *caja_rayo):
				if info.abertura.tipo == "ventana" or not info.sobre_pared:
					continue
				corte = geo.corte_segmentos(origen, fin, info.abertura.a, info.abertura.b)
				if corte is None:
					continue
				d = geo.distancia(origen, corte)
				if d < 0.05 or not mundo.deja_pasar(info.abertura.id):
					continue
				cruzadas.append(d)
				self.aberturas.add(info.abertura.id)
				mas_alla = geo.punto_a_distancia(origen, rumbo, d + 0.4)
				destino = mundo.espacio_en(jugador.planta, mas_alla[0], mas_alla[1])
				tipo = _("hueco") if info.abertura.tipo == "hueco" else _("puerta abierta")
				if destino is not None and (espacio_actual is None or destino.id != espacio_actual.id):
					texto = _("{puerta} hacia {destino}").format(puerta=tipo, destino=s.leng.espacio(destino))
				else:
					texto = tipo
				hallazgos.append((d, "abertura", texto))
			for boca in indice.bocas:
				a_lo_largo = (boca.x - origen[0]) * math.sin(math.radians(rumbo)) + (boca.y - origen[1]) * math.cos(math.radians(rumbo))
				if a_lo_largo <= 0.2 or a_lo_largo > tope:
					continue
				proyectado = geo.punto_a_distancia(origen, rumbo, a_lo_largo)
				if geo.distancia(proyectado, boca.punto) <= 0.7:
					texto = _("{escalera}, que sube") if boca.sentido > 0 else _("{escalera}, que baja")
					hallazgos.append((a_lo_largo, "boca", texto.format(escalera=s.leng.conector(boca.conector))))
					self.conectores.add(boca.conector.id)
		# Cambios de espacio sin puerta (acera y calzada) y de suelo, tanteando el rayo cada palmo.
		espacio_previo = espacio_actual.id if espacio_actual is not None else ""
		suelo_previo = mundo.suelo_en(jugador.planta, jugador.x, jugador.y)
		cambio_espacio = False
		cambio_suelo = False
		d = 0.25
		while d < tope and not cambio_suelo:
			punto = geo.punto_a_distancia(origen, rumbo, d)
			espacio = mundo.espacio_en(jugador.planta, punto[0], punto[1])
			espacio_id = espacio.id if espacio is not None else ""
			suelo = mundo.suelo_en(jugador.planta, punto[0], punto[1])
			if espacio_id != espacio_previo:
				# Solo se cuenta el primer cambio de espacio; el suelo del nuevo no es noticia aparte.
				if (
					not cambio_espacio
					and espacio is not None
					and not espacio.datos.get("terreno_base")
					and all(abs(d - c) > 0.5 for c in cruzadas)
				):
					hallazgos.append((d, "espacio", s.leng.espacio(espacio)))
				cambio_espacio = True
				espacio_previo = espacio_id
			elif not cambio_suelo and suelo != suelo_previo:
				cambio_suelo = True
				zona = mundo.zona_en(jugador.planta, punto[0], punto[1])
				hallazgos.append((d, "suelo", zona.nombre if zona is not None and zona.nombre else s.leng.suelo(suelo)))
			suelo_previo = suelo
			d += 0.25
		hallazgos.sort(key=lambda dato: dato[0])
		return hallazgos

	def _texto_rayo(self, relativo: float, alcance: float = ALCANCE_MIRAR) -> tuple[str, Impacto | None]:
		"""Frase de lo que hay en una dirección relativa, y el impacto del rayo (para hacerlo sonar)."""
		s = self.s
		jugador = s.jugador
		rumbo = (jugador.rumbo + relativo) % 360.0
		impacto = s.mundo.rayo(jugador.planta, jugador.punto, rumbo, alcance, "paso")
		tope = impacto.distancia if impacto is not None else alcance
		partes = [s.leng.a_distancia(texto, max(0.0, d - jugador.radio)) for d, _clase, texto in self._hallazgos_en_rayo(rumbo, tope)[:3]]
		if impacto is not None:
			nombre = s.movimiento.nombre_obstaculo(impacto.seg)
			partes.append(s.leng.a_distancia(nombre, max(0.0, impacto.distancia - jugador.radio)))
			if impacto.seg.clase == "objeto":
				self.descubrir_objeto(impacto.seg.elemento_id)
			elif impacto.seg.clase == "puerta":
				self.aberturas.add(impacto.seg.elemento_id)
		else:
			partes.append(_("despejado más de {distancia}").format(distancia=s.leng.distancia(alcance)))
		return "; ".join(partes), impacto

	def _sonar_impacto(self, relativo: float, impacto: Impacto | None, alcance: float) -> None:
		s = self.s
		if impacto is None:
			punto = geo.punto_a_distancia(s.jugador.punto, s.jugador.rumbo + relativo, min(alcance, 8.0))
			s.sonar("sonda/libre", pos=s.pos3(punto[0], punto[1], 1.0), bus="ayudas", volumen=0.6)
			return
		s.sonar(self._sonido_sonda(impacto), pos=s.pos3(impacto.punto[0], impacto.punto[1], 1.0), bus="ayudas")

	@staticmethod
	def _sonido_sonda(impacto: Impacto) -> str:
		if impacto.seg.clase == "objeto":
			return "sonda/objeto"
		if impacto.seg.clase == "puerta":
			return "sonda/puerta"
		return "sonda/pared"

	def mirar(self, relativo: float) -> None:
		"""Dice qué hay en una dirección relativa (primer obstáculo, aberturas y cambios) y a qué distancia."""
		s = self.s
		if not self.usar("mirar"):
			return
		texto, impacto = self._texto_rayo(relativo)
		self._sonar_impacto(relativo, impacto, ALCANCE_MIRAR)
		direccion = lenguaje.mayuscula(s.leng.cuadrante(relativo, s.jugador.rumbo))
		s.decir(f"{direccion}: {texto}.", canal="ayuda", pedida=True, clave="mirar")

	def cosas(self, radio: float, solo_visibles: bool = True) -> list[Cosa]:
		"""Lo que hay alrededor del alumno en su planta, hasta ``radio`` metros en línea recta, de cerca a lejos."""
		s = self.s
		jugador = s.jugador
		mundo = s.mundo
		x, y = jugador.x, jugador.y
		lista: list[Cosa] = []

		def anotar(clase: str, ident: str, nombre: str, punto: Punto, distancia: float, elemento: Any) -> None:
			if not nombre:
				return
			visible = mundo.visible(jugador.planta, (x, y), punto, "vista")
			if solo_visibles and not visible:
				return
			absoluto = geo.rumbo_entre((x, y), punto) if geo.distancia((x, y), punto) > 0.05 else jugador.rumbo
			lista.append(
				Cosa(clase, ident, nombre, punto, distancia, geo.diferencia_rumbos(jugador.rumbo, absoluto), elemento, None, visible)
			)

		for d, info in mundo.objetos_cerca(jugador.planta, x, y, radio):
			cercano = min(
				(geo.proyeccion_sobre_segmento((x, y), a, b) for a, b in geo.lados(info.huella)), key=lambda p: geo.distancia((x, y), p)
			)
			# Un palmo hacia el alumno: el borde del objeto está sobre su propio contorno.
			largo = geo.distancia((x, y), cercano)
			if largo > 0.3:
				cercano = (cercano[0] + (x - cercano[0]) / largo * 0.25, cercano[1] + (y - cercano[1]) / largo * 0.25)
			anotar("objeto", info.objeto.id, info.objeto.nombre, cercano, d, info)
		for d, info_abertura in mundo.aberturas_cerca(jugador.planta, x, y, radio):
			nombre = s.leng.abertura(info_abertura.abertura, mundo.estado_abertura(info_abertura.abertura.id))
			anotar("abertura", info_abertura.abertura.id, nombre, info_abertura.centro, d, info_abertura)
		for d, referencia in mundo.referencias_cerca(jugador.planta, x, y, radio):
			anotar("referencia", referencia.id, referencia.nombre, (referencia.x, referencia.y), d, referencia)
		for d, fuente in mundo.fuentes_cerca(jugador.planta, x, y, radio):
			anotar("fuente", fuente.id, fuente.nombre, (fuente.x, fuente.y), d, fuente)
		for d, boca in mundo.bocas_cerca(jugador.planta, x, y, radio):
			texto = _("{escalera}, que sube") if boca.sentido > 0 else _("{escalera}, que baja")
			anotar("boca", f"{boca.conector.id}/{boca.sentido}", texto.format(escalera=s.leng.conector(boca.conector)), boca.punto, d, boca)
		for d, parada in mundo.paradas_cerca(jugador.planta, x, y, radio):
			anotar("parada", parada.conector.id, s.leng.conector(parada.conector), parada.punto, d, parada)
		lista.sort(key=lambda cosa: cosa.distancia)
		return lista

	def delante(self) -> None:
		"""Qué hay delante: lo que encuentra el rayo y, además, lo que queda dentro de un cono."""
		s = self.s
		if not self.usar("delante"):
			return
		texto, impacto = self._texto_rayo(0.0)
		self._sonar_impacto(0.0, impacto, ALCANCE_MIRAR)
		chocado = impacto.seg.elemento_id if impacto is not None else ""
		extras: list[str] = []
		for cosa in self.cosas(8.0):
			if abs(cosa.relativo) > 35.0 or cosa.id == chocado or cosa.distancia < 0.3:
				continue
			if cosa.clase == "abertura" and abs(cosa.relativo) < 8.0:
				continue
			self._descubrir(cosa)
			extras.append(s.leng.a_distancia(cosa.nombre, cosa.distancia, s.leng.direccion(cosa.relativo, s.jugador.rumbo + cosa.relativo)))
			if len(extras) >= 3:
				break
		frase = _("Delante: {texto}.").format(texto=texto)
		if extras:
			frase += " " + _("Cerca: {cosas}.").format(cosas="; ".join(extras))
		s.decir(frase, canal="ayuda", pedida=True, clave="mirar")

	def alrededor(self) -> None:
		"""Describe lo que rodea al alumno por cuadrantes: delante, derecha, detrás e izquierda."""
		s = self.s
		if not self.usar("alrededor"):
			return
		jugador = s.jugador
		cosas = self.cosas(5.0)
		frases: list[str] = []
		for cuadrante in lenguaje.CUADRANTES:
			rumbo = (jugador.rumbo + cuadrante) % 360.0
			impacto = s.mundo.rayo(jugador.planta, jugador.punto, rumbo, ALCANCE_MIRAR, "paso")
			partes: list[str] = []
			chocado = ""
			if impacto is not None:
				chocado = impacto.seg.elemento_id
				partes.append(s.leng.a_distancia(s.movimiento.nombre_obstaculo(impacto.seg), max(0.0, impacto.distancia - jugador.radio)))
				if impacto.seg.clase == "objeto":
					self.descubrir_objeto(chocado)
			else:
				partes.append(_("despejado"))
			dichas = 0
			for cosa in cosas:
				if abs(lenguaje.normalizar_relativo(cosa.relativo - cuadrante)) > 45.0 or cosa.id == chocado or dichas >= 2:
					continue
				self._descubrir(cosa)
				partes.append(s.leng.a_distancia(cosa.nombre, cosa.distancia))
				dichas += 1
			frases.append(f"{lenguaje.mayuscula(s.leng.cuadrante(cuadrante, jugador.rumbo))}: {'; '.join(partes)}.")
		s.decir(" ".join(frases), canal="ayuda", pedida=True, clave="alrededor")

	# ── Sonda ──

	def sonda(self, contar: bool = True) -> None:
		"""Bastón sonoro: un sonido que avanza a ritmo constante y cambia según lo que cruza y con qué choca.

		Hay un pulso por cada paso del alumno, así que contar los pulsos es
		contar los pasos que faltan; además cada pulso suena un poco más flojo
		que el anterior. No encuentra los objetos colgados o en voladizo: el
		bastón pasa por debajo, como en la realidad.
		"""
		s = self.s
		if contar and not self.usar("sonda"):
			self._sonda_mantenida = False
			return
		s.cancelar("sonda")
		jugador = s.jugador
		mundo = s.mundo
		alcance = s.ajustes.alcance_sonda
		paso = s.ajustes.paso_m
		impacto = mundo.rayo(jugador.planta, jugador.punto, jugador.rumbo, alcance, "sonda")
		tope = impacto.distancia if impacto is not None else alcance
		pulsos = int(max(0.0, tope - 1e-6) / paso)
		maximo = max(1, int(alcance / paso))
		previo = jugador.punto
		espacio_previo = mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		indice = mundo.planta(jugador.planta)
		for k in range(1, pulsos + 1):
			punto = geo.punto_a_distancia(jugador.punto, jugador.rumbo, k * paso)
			nombre = "sonda/libre"
			espacio = mundo.espacio_en(jugador.planta, punto[0], punto[1])
			if indice is not None and any(
				mundo.deja_pasar(info.abertura.id) and geo.corte_segmentos(previo, punto, info.abertura.a, info.abertura.b) is not None
				for info in mundo.aberturas_en_caja(jugador.planta, *_caja_tramo(previo, punto))
			):
				nombre = "sonda/puerta"
			elif (
				espacio is not None
				and espacio_previo is not None
				and (espacio.tipo in TIPOS_CALZADA) != (espacio_previo.tipo in TIPOS_CALZADA)
			):
				nombre = "sonda/bordillo"
			elif mundo.bocas_cerca(jugador.planta, punto[0], punto[1], 0.6):
				nombre = "sonda/escalon"
			s.sonar(
				nombre,
				pos=s.pos3(punto[0], punto[1], 0.3),
				bus="ayudas",
				volumen=0.95 - 0.5 * (k / maximo),
				retardo=(k - 1) * INTERVALO_SONDA,
				grupo="sonda",
			)
			previo = punto
			espacio_previo = espacio
		final = pulsos * INTERVALO_SONDA
		if impacto is not None:
			s.sonar(
				self._sonido_sonda(impacto), pos=s.pos3(impacto.punto[0], impacto.punto[1], 0.5), bus="ayudas", retardo=final, grupo="sonda"
			)
			s.vibrar("peldano", retardo=final, grupo="sonda")
			if impacto.seg.clase == "objeto":
				self.descubrir_objeto(impacto.seg.elemento_id)
			if s.ajustes.detalle >= 2:
				texto = s.leng.a_distancia(s.movimiento.nombre_obstaculo(impacto.seg), max(0.0, impacto.distancia - jugador.radio)) + "."
				# Es la respuesta a algo que ha pedido: se dice al acabar el barrido, sin esperar turno.
				s.decir(texto, canal="ayuda", pedida=True, clave="sonda", retardo=final + 0.1, grupo="sonda")
		else:
			punto = geo.punto_a_distancia(jugador.punto, jugador.rumbo, alcance)
			s.sonar("sonda/lejos", pos=s.pos3(punto[0], punto[1], 0.5), bus="ayudas", volumen=0.5, retardo=final, grupo="sonda")
		self._t_sonda = s.t + final + 0.6

	# ── Brújula y eco ──

	def brujula(self) -> None:
		"""Dice el rumbo y hace sonar el norte desde donde está."""
		s = self.s
		if not self.usar("brujula"):
			return
		rumbo = s.jugador.rumbo
		s.sonar("brujula/norte", relativo=(lenguaje.normalizar_relativo(-rumbo), 3.0), bus="ayudas")
		s.decir(s.leng.rumbo(rumbo, con_grados=s.ajustes.detalle >= 3), canal="ayuda", pedida=True, clave="brujula")

	def eco(self) -> None:
		"""Chasquido: su respuesta llega antes y más fuerte cuanto más cerca están las paredes."""
		s = self.s
		if not self.usar("eco"):
			return
		jugador = s.jugador
		s.sonar("eco/chasquido", bus="ayudas")
		distancias: list[tuple[float, float]] = []
		for cuadrante in lenguaje.CUADRANTES:
			impacto = s.mundo.rayo(jugador.planta, jugador.punto, jugador.rumbo + cuadrante, ALCANCE_ECO, "vista")
			if impacto is None:
				continue
			d = impacto.distancia
			distancias.append((d, cuadrante))
			blando = ev.material_sonido(impacto.seg.material) == "tela"
			s.sonar(
				"eco/chasquido",
				pos=s.pos3(impacto.punto[0], impacto.punto[1], 1.2),
				bus="ayudas",
				volumen=max(0.12, 1.0 / (1.0 + 0.35 * d)) * (0.6 if blando else 1.0),
				filtro=0.5 if blando else 0.2,
				retardo=0.08 + d * 0.035,
				grupo="eco",
			)
		if s.ajustes.detalle < 2:
			return
		espacio = s.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		if len(distancias) <= 2 or (espacio is not None and not espacio.cerrado):
			texto = _("Espacio abierto.")
		else:
			area = espacio.area() if espacio is not None else 0.0
			if area < 9.0:
				texto = _("Lugar pequeño.")
			elif area < 30.0:
				texto = _("Lugar mediano.")
			elif area < 100.0:
				texto = _("Lugar grande.")
			else:
				texto = _("Lugar muy grande.")
		if distancias:
			d, cuadrante = min(distancias)
			texto += " " + _("Lo más cercano, {lado}, a {distancia}.").format(
				lado=s.leng.cuadrante(cuadrante, jugador.rumbo), distancia=s.leng.distancia(max(0.0, d - jugador.radio))
			)
		s.decir(texto, canal="ayuda", pedida=True, clave="eco", retardo=0.5, grupo="eco")

	# ── Cercanos ──

	def lista_cercanos(self) -> list[Cosa]:
		"""Lo cercano que el alumno puede conocer, ordenado por lo que hay que ANDAR hasta ello.

		Entran lo que está en su mismo espacio, lo que tiene a la vista y lo
		que ya descubrió; lo demás no, para no revelarle lo que no ha encontrado.
		"""
		s = self.s
		jugador = s.jugador
		espacio = s.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		campo = s.nav.distancias_desde((jugador.planta, jugador.x, jugador.y), RADIO_CERCANOS * 1.5)
		lista: list[Cosa] = []
		for cosa in self.cosas(RADIO_CERCANOS, solo_visibles=False):
			if cosa.clase == "abertura" and cosa.elemento.abertura.tipo == "hueco" and cosa.distancia < 0.3:
				continue
			mismo = False
			if espacio is not None:
				if cosa.clase == "abertura":
					mismo = espacio.id in cosa.elemento.espacios
				else:
					otro = s.mundo.espacio_en(jugador.planta, cosa.punto[0], cosa.punto[1])
					mismo = otro is not None and otro.id == espacio.id
			if not (mismo or cosa.visible or self._conocida(cosa)):
				continue
			camino = s.nav.distancia_en(campo, cosa.punto[0], cosa.punto[1])
			if camino is None:
				if not cosa.visible or cosa.distancia > 3.0:
					continue
				camino = cosa.distancia
			cosa.camino = max(camino, cosa.distancia)
			lista.append(cosa)
		lista.sort(key=lambda cosa: cosa.camino or 0.0)
		return lista

	def cercano(self, salto: int) -> None:
		"""Pasa al siguiente (o al anterior) de la lista de cercanos: suena desde su sitio y se dice distancia y dirección."""
		s = self.s
		if not self.usar("cercanos"):
			return
		jugador = s.jugador
		hecha_en = self._cercanos_en
		if (
			hecha_en is None
			or hecha_en[0] != jugador.planta
			or math.hypot(hecha_en[1] - jugador.x, hecha_en[2] - jugador.y) > 1.0
			or s.t - hecha_en[3] > 20.0
			or hecha_en[4:] != (s.mundo.version,)
		):
			self._cercanos = self.lista_cercanos()
			self._cercanos_en = (jugador.planta, jugador.x, jugador.y, s.t, s.mundo.version)
			self._indice_cercano = -1 if salto > 0 else len(self._cercanos)
		if not self._cercanos:
			s.decir(_("No hay nada cerca."), canal="ayuda", pedida=True, clave="cercanos")
			return
		nuevo = self._indice_cercano + salto
		if nuevo < 0 or nuevo >= len(self._cercanos):
			s.sonar("interfaz/borde", bus="interfaz")
			nuevo = max(0, min(len(self._cercanos) - 1, nuevo))
		self._indice_cercano = nuevo
		cosa = self._cercanos[nuevo]
		self._descubrir(cosa)
		absoluto = geo.rumbo_entre(jugador.punto, cosa.punto) if geo.distancia(jugador.punto, cosa.punto) > 0.05 else jugador.rumbo
		relativo = geo.diferencia_rumbos(jugador.rumbo, absoluto)
		sonido = {"objeto": "sonda/objeto", "abertura": "sonda/puerta", "boca": "sonda/escalon"}.get(cosa.clase, "baliza/pulso")
		s.sonar(sonido, pos=s.pos3(cosa.punto[0], cosa.punto[1], 1.0), bus="ayudas", filtro=0.0 if cosa.visible else 0.6)
		texto = s.leng.a_distancia(
			cosa.nombre, cosa.camino if cosa.camino is not None else cosa.distancia, s.leng.direccion(relativo, absoluto)
		)
		if s.ajustes.detalle >= 2:
			texto += ". " + _("{n} de {total}").format(n=nuevo + 1, total=len(self._cercanos))
		s.decir(texto + ".", canal="ayuda", pedida=True, clave="cercanos")

	# ── Descubrimiento ──

	def _conocido(self, espacio: Espacio, planta_id: str) -> Conocido:
		conocido = self.conocidos.get(espacio.id)
		if conocido is None:
			conocido = Conocido(espacio, planta_id, muestras=_muestras_de(espacio))
			self.conocidos[espacio.id] = conocido
		return conocido

	def _conocida(self, cosa: Cosa) -> bool:
		if cosa.clase == "objeto":
			return cosa.id in self.objetos
		if cosa.clase == "abertura":
			return cosa.id in self.aberturas
		if cosa.clase == "referencia":
			return cosa.id in self.referencias
		if cosa.clase in ("boca", "parada"):
			return cosa.id.split("/")[0] in self.conectores
		return False

	def _descubrir(self, cosa: Cosa) -> None:
		if cosa.clase == "objeto":
			self.descubrir_objeto(cosa.id)
		elif cosa.clase == "abertura":
			self.aberturas.add(cosa.id)
		elif cosa.clase == "referencia":
			self.referencias.add(cosa.id)
		elif cosa.clase in ("boca", "parada"):
			self.conectores.add(cosa.id.split("/")[0])

	def descubrir_objeto(self, objeto_id: str) -> None:
		"""Apunta que el alumno ya ha percibido ese objeto (y lo registra la primera vez)."""
		if objeto_id in self.objetos:
			return
		self.objetos.add(objeto_id)
		info = self.s.mundo.objeto(objeto_id)
		self.s.registrar("descubierto", clase="objeto", elemento=objeto_id, nombre=info.objeto.nombre if info is not None else "")

	def entrar_en_espacio(self, espacio: Espacio, primera: bool) -> None:
		"""El alumno ha entrado en un espacio: pasa a conocerlo."""
		if espacio.datos.get("terreno_base"):
			# El terreno sin detallar de un mapa importado no es un lugar que se «descubra».
			self._ultimo_punto = None
			return
		conocido = self._conocido(espacio, self.s.jugador.planta)
		if not conocido.visitado:
			conocido.visitado = True
			self.s.registrar("descubierto", clase="espacio", elemento=espacio.id, nombre=espacio.nombre)
		self._ultimo_punto = None

	def tras_mover(self) -> None:
		"""Actualiza lo percibido y da los avisos de proximidad, si el alumno se ha movido lo bastante."""
		s = self.s
		jugador = s.jugador
		if jugador.modo != "andando":
			return
		ultimo = self._ultimo_punto
		if ultimo is not None and ultimo[0] == jugador.planta and math.hypot(ultimo[1] - jugador.x, ultimo[2] - jugador.y) < 0.3:
			return
		self._ultimo_punto = (jugador.planta, jugador.x, jugador.y)
		self._percibir()
		self._avisos()

	def _percibir(self) -> None:
		s = self.s
		jugador = s.jugador
		mundo = s.mundo
		x, y = jugador.x, jugador.y
		espacio = mundo.espacio_en(jugador.planta, x, y)
		if espacio is not None and not espacio.datos.get("terreno_base"):
			conocido = self._conocido(espacio, jugador.planta)
			estaba = conocido.completo
			for numero, (mx, my) in enumerate(conocido.muestras):
				if numero in conocido.vistas or abs(mx - x) > RADIO_PERCEPCION or abs(my - y) > RADIO_PERCEPCION:
					continue
				if math.hypot(mx - x, my - y) <= RADIO_PERCEPCION and mundo.visible(jugador.planta, (x, y), (mx, my), "vista"):
					conocido.vistas.add(numero)
			if conocido.completo and not estaba:
				s.registrar("espacio_explorado", espacio=espacio.id, nombre=espacio.nombre)
		for _d, info in mundo.objetos_cerca(jugador.planta, x, y, 0.9):
			self.descubrir_objeto(info.objeto.id)
		for _d, info_abertura in mundo.aberturas_cerca(jugador.planta, x, y, 1.5):
			self.aberturas.add(info_abertura.abertura.id)
			if mundo.deja_pasar(info_abertura.abertura.id) and espacio is not None:
				# Por una puerta abierta se percibe que al otro lado hay otro lugar, aunque no se haya entrado.
				otro_id = info_abertura.otro_lado(espacio.id)
				otro = mundo.elemento(otro_id) if otro_id else None
				if isinstance(otro, Espacio) and not otro.macizo and not otro.datos.get("terreno_base"):
					self._conocido(otro, jugador.planta)
		for _d, referencia in mundo.referencias_cerca(jugador.planta, x, y, 1.5):
			self.referencias.add(referencia.id)
		for _d, boca in mundo.bocas_cerca(jugador.planta, x, y, 2.0):
			self.conectores.add(boca.conector.id)
		for _d, parada in mundo.paradas_cerca(jugador.planta, x, y, 2.0):
			self.conectores.add(parada.conector.id)

	def lugares_conocidos(self) -> list[dict[str, Any]]:
		"""Los espacios que el alumno conoce, en el orden en que los fue conociendo.

		Cada uno: ``id``, ``nombre``, ``planta``, ``visitado``, ``explorado``
		(0 a 1) y ``completo``. Con esto el reproductor monta el menú de lugares conocidos.
		"""
		return [
			{
				"id": c.espacio.id,
				"nombre": self.s.leng.espacio(c.espacio),
				"planta": c.planta_id,
				"visitado": c.visitado,
				"explorado": round(c.explorado, 3),
				"completo": c.completo,
			}
			for c in self.conocidos.values()
		]

	def descubiertos(self) -> None:
		"""Dice los lugares que el alumno ya conoce y cuáles no ha explorado del todo."""
		s = self.s
		if not self.usar("descubiertos"):
			return
		lugares = self.lugares_conocidos()
		if not lugares:
			s.decir(_("Todavía no has descubierto ningún lugar."), canal="ayuda", pedida=True, clave="descubiertos")
			return
		nombres: list[str] = []
		for dato in lugares:
			if not dato["visitado"]:
				nombres.append(_("{lugar}, sin visitar").format(lugar=dato["nombre"]))
			elif not dato["completo"]:
				nombres.append(_("{lugar}, no explorada del todo").format(lugar=dato["nombre"]))
			else:
				nombres.append(dato["nombre"])
		n = len(lugares)
		texto = _n("Conoces {n} lugar: {lista}.", "Conoces {n} lugares: {lista}.", n).format(n=n, lista="; ".join(nombres))
		if len(self.objetos) and s.ajustes.detalle >= 2:
			texto += " " + _n("Has encontrado {n} objeto.", "Has encontrado {n} objetos.", len(self.objetos)).format(n=len(self.objetos))
		s.decir(texto, canal="ayuda", pedida=True, clave="descubiertos")

	# ── Avisos automáticos ──

	def _pasos_y_cruces(self, indice: Any) -> list[tuple[tuple[float, float, float, float], Espacio]]:
		"""(caja, espacio) de los pasos de peatones y los cruces de una planta, en el orden de sus espacios.

		Se calculan una vez por índice de planta: los avisos los miran cada vez
		que el alumno se mueve un poco, y en un barrio importado hay miles de
		espacios y solo unas decenas de pasos y cruces.
		"""
		guardado = self._pasos_planta.get(indice.planta.id)
		if guardado is not None and guardado[0] is indice:
			return guardado[1]
		elegidos = [
			(caja, espacio)
			for caja, espacio in indice.espacios
			if espacio.tipo == "paso_peatones" or (espacio.tipo == "calzada" and espacio.datos.get("cruce"))
		]
		self._pasos_planta[indice.planta.id] = (indice, elegidos)
		return elegidos

	def _ya_avisado(self, clave: tuple, espera: float = 120.0, lejos: float = 6.0) -> bool:
		"""Si eso mismo ya se avisó hace poco y el alumno no se ha alejado desde entonces (no lo apunta)."""
		aviso = self.avisados.get(clave)
		jugador = self.s.jugador
		return aviso is not None and self.s.t - aviso[0] < espera and math.hypot(aviso[1] - jugador.x, aviso[2] - jugador.y) < lejos

	def dar_por_avisado(self, clave: tuple) -> None:
		"""Apunta un aviso como ya dado aquí y ahora (lo que el alumno acaba de usar no hay que anunciárselo)."""
		self._apuntar_aviso(clave)

	def _apuntar_aviso(self, clave: tuple) -> None:
		self.avisados[clave] = (self.s.t, self.s.jugador.x, self.s.jugador.y)
		if len(self.avisados) > 2000:
			for vieja in list(self.avisados)[:500]:
				del self.avisados[vieja]

	def forma_cruce(self, cruce: Espacio) -> tuple[int, list[tuple[float, str]]]:
		"""Ramas de un cruce: cuántas calles salen de él y, de cada una, su rumbo desde el centro y el nombre de su calle."""
		s = self.s
		centro_bruto = cruce.datos.get("centro")
		try:
			centro = (float(centro_bruto[0]), float(centro_bruto[1]))
		except TypeError, ValueError, IndexError:
			centro = cruce.centro()
		ramas: list[tuple[float, str]] = []
		for via_id in cruce.datos.get("vias") or []:
			via = s.mundo.elemento(str(via_id))
			eje = getattr(via, "eje", None)
			if not eje or len(eje) < 2:
				continue
			_cercano, _d, tramo = geo.proyeccion_sobre_linea(centro, eje)
			antes = geo.longitud_linea(eje[: tramo + 1]) + geo.distancia(eje[tramo], centro)
			despues = geo.longitud_linea(eje) - antes
			margen = max(float(getattr(via, "ancho", 6.0)), 3.0)
			rumbo = geo.rumbo_entre(eje[tramo], eje[tramo + 1])
			if despues > margen:
				ramas.append((rumbo, via.nombre))
			if antes > margen:
				ramas.append(((rumbo + 180.0) % 360.0, via.nombre))
		return len(ramas), ramas

	def texto_cruce(self, cruce: Espacio, completo: bool = True) -> str:
		"""Frase de un cruce: su nombre, su forma y qué calle queda a cada lado del alumno."""
		s = self.s
		numero, ramas = self.forma_cruce(cruce)
		nombre = cruce.nombre or _("Cruce")
		texto = nombre + "."
		if not completo:
			return texto
		# La forma que trae el mapa importado manda sobre la que se deduce de las vías.
		formas = {
			"t": _("{cruce}, en forma de te."),
			"y": _("{cruce}, en forma de i griega."),
			"cruz": _("{cruce}, en cruz."),
			"aspa": _("{cruce}, en aspa."),
			"desalineado": _("{cruce}, con las calles desalineadas."),
			"complejo": _("{cruce}, complejo: se juntan varias calles."),
			"rotonda": _("{cruce}: es una rotonda."),
		}
		forma = str(cruce.datos.get("forma") or "")
		if forma in formas:
			texto = formas[forma].format(cruce=nombre)
		elif numero >= 4:
			texto = formas["cruz"].format(cruce=nombre)
		elif numero == 3:
			texto = formas["t"].format(cruce=nombre)
		rumbos = cruce.datos.get("rumbos")
		if not ramas and isinstance(rumbos, list):
			# Sin vías con nombre, al menos hacia dónde sale cada rama.
			lados: list[str] = []
			for rumbo in rumbos:
				if isinstance(rumbo, (int, float)) and not isinstance(rumbo, bool):
					lado = s.leng.cuadrante(round(geo.diferencia_rumbos(s.jugador.rumbo, float(rumbo)) / 90.0) * 90.0, s.jugador.rumbo)
					if lado not in lados:
						lados.append(lado)
			if lados:
				texto += " " + _("Salen calles: {lados}.").format(lados=lenguaje.lista(lados))
		por_calle: dict[str, list[str]] = {}
		for rumbo, nombre in ramas:
			relativo = geo.diferencia_rumbos(s.jugador.rumbo, rumbo)
			por_calle.setdefault(nombre, []).append(s.leng.cuadrante(round(relativo / 90.0) * 90.0, s.jugador.rumbo))
		for nombre, lados in por_calle.items():
			texto += " " + _("{calle}: {lados}.").format(calle=nombre, lados=lenguaje.lista(lados))
		return texto

	def texto_paso(self, paso: Espacio, completo: bool = True) -> str:
		"""Ficha de un paso de peatones: si tiene semáforo y de qué tipo, qué calle cruza y cuánto mide."""
		s = self.s
		datos = paso.datos
		# Tres estados (sí, no, el mapa no lo dice): no es lo mismo «no tiene» que «no se sabe».
		semaforo = fichas.estado_de(datos, "semaforo")
		if semaforo == fichas.SI:
			sonoro = fichas.estado_de(datos, "sonoro")
			if sonoro == fichas.SI:
				tipo = _("Paso de peatones con semáforo sonoro")
			elif sonoro == fichas.NO:
				tipo = _("Paso de peatones con semáforo sin sonido")
			else:
				tipo = _("Paso de peatones con semáforo; el mapa no dice si es sonoro")
		elif semaforo == fichas.NO:
			tipo = _("Paso de peatones sin semáforo")
		else:
			tipo = _("Paso de peatones; el mapa no dice si tiene semáforo")
		if not completo:
			return tipo
		partes = [tipo + "."]
		via = s.mundo.elemento(str(datos.get("via") or ""))
		largo = datos.get("longitud")
		if via is not None and getattr(via, "nombre", ""):
			if isinstance(largo, (int, float)):
				partes.append(_("Cruza {calle}, {distancia}.").format(calle=via.nombre, distancia=s.leng.distancia(float(largo))))
			else:
				partes.append(_("Cruza {calle}.").format(calle=via.nombre))
		if semaforo != fichas.NO:
			pulsador = fichas.estado_de(datos, "pulsador")
			if pulsador == fichas.SI:
				partes.append(_("Tiene pulsador."))
			elif pulsador == fichas.DESCONOCIDO and fichas.viene_de_mapa(datos):
				partes.append(_("El mapa no dice si tiene pulsador."))
		isleta = fichas.estado_de(datos, "isleta")
		if isleta == fichas.SI:
			partes.append(_("Hay una isleta en medio."))
		elif isleta == fichas.DESCONOCIDO and fichas.viene_de_mapa(datos):
			partes.append(_("El mapa no dice si hay isleta."))
		return " ".join(partes)

	def _avisos(self) -> None:
		"""Avisos de proximidad, con antirrepetición y como mucho unos pocos de cada vez."""
		s = self.s
		detalle = s.ajustes.detalle
		if detalle <= 0:
			return
		jugador = s.jugador
		mundo = s.mundo
		x, y = jugador.x, jugador.y
		# Avisos que traen los propios objetos («Borde del andén: detente»): son parte del lugar, como un
		# pavimento táctil, y por eso se dicen aunque la actividad haya quitado los avisos de ayuda.
		for d, info_aviso in mundo.objetos_cerca(jugador.planta, x, y, 1.0):
			if not info_aviso.aviso or (d > 0.0 and not mundo.corta_el_paso(info_aviso)):
				continue
			clave = ("objeto_aviso", info_aviso.objeto.id)
			if not self._ya_avisado(clave, 45.0, 2.5):
				self._apuntar_aviso(clave)
				self.descubrir_objeto(info_aviso.objeto.id)
				s.decir(info_aviso.aviso, canal="aviso", prioridad=3, clave="objeto_aviso")
				s.registrar("aviso", clase="objeto", elemento=info_aviso.objeto.id, texto=info_aviso.aviso)
		if not self.permitida("avisos"):
			return
		espacio = mundo.espacio_en(jugador.planta, x, y)
		en_calzada = espacio is not None and espacio.tipo in TIPOS_CALZADA
		if espacio is not None and espacio.tipo == "paso_peatones":
			# Lo está cruzando: al llegar a la otra acera no hay que anunciárselo otra vez.
			self._apuntar_aviso(("paso", espacio.id))
		candidatos: list[tuple[int, float, tuple, str, float, float]] = []

		def proponer(prioridad: int, distancia: float, clave: tuple, texto: str, espera: float = 120.0, lejos: float = 6.0) -> None:
			if not self._ya_avisado(clave, espera, lejos):
				candidatos.append((prioridad, distancia, clave, texto, espera, lejos))

		def hacia(punto: Punto) -> str:
			return s.leng.direccion_a((x, y), jugador.rumbo, punto)

		for d, boca in mundo.bocas_cerca(jugador.planta, x, y, 2.6):
			if d < 0.3 or not mundo.visible(jugador.planta, (x, y), boca.punto, "vista"):
				continue
			if boca.conector.tipo == "rampa":
				nombre = _("Rampa que sube") if boca.sentido > 0 else _("Rampa que baja")
			else:
				nombre = _("Escalera que sube") if boca.sentido > 0 else _("Escalera que baja")
			proponer(3, d, ("boca", boca.conector.id, boca.sentido), s.leng.a_distancia(nombre, d, hacia(boca.punto)) + ".")
		for d, parada in mundo.paradas_cerca(jugador.planta, x, y, 2.5):
			if mundo.visible(jugador.planta, (x, y), parada.punto, "vista"):
				direccion = hacia(parada.punto) if d > 0.4 else _("aquí")
				proponer(
					2,
					d,
					("parada", parada.conector.id, jugador.planta),
					_("{ascensor}, {direccion}.").format(ascensor=s.leng.conector(parada.conector), direccion=direccion),
				)
		indice = mundo.planta(jugador.planta)
		if indice is not None and indice.planta.exterior and not en_calzada:
			for _caja, otro in self._pasos_y_cruces(indice):
				if otro.tipo == "paso_peatones":
					for extremo in otro.datos.get("extremos") or []:
						try:
							punto = (float(extremo[0]), float(extremo[1]))
						except TypeError, ValueError, IndexError:
							continue
						d = math.hypot(punto[0] - x, punto[1] - y)
						if d <= 3.5:
							texto = self.texto_paso(otro, detalle >= 2)
							proponer(
								3,
								d,
								("paso", otro.id),
								lenguaje.frase(f"{hacia(punto)}, {texto[:1].lower() + texto[1:]}")
								if d > 0.8
								else texto + ("" if texto.endswith(".") else "."),
							)
							break
				elif otro.tipo == "calzada" and otro.datos.get("cruce"):
					x0, y0, x1, y1 = _caja
					if x0 - 7.0 <= x <= x1 + 7.0 and y0 - 7.0 <= y <= y1 + 7.0:
						d = geo.distancia_punto_poligono((x, y), otro.contorno)
						if d <= 6.0:
							proponer(2, d, ("cruce", otro.id), self.texto_cruce(otro, detalle >= 2), 180.0, 12.0)
			if detalle >= 2 and espacio is not None:
				delante = geo.punto_a_distancia((x, y), jugador.rumbo, 1.3)
				otro_delante = mundo.espacio_en(jugador.planta, delante[0], delante[1])
				if (
					otro_delante is not None
					and otro_delante.tipo in TIPOS_CALZADA
					and mundo.visible(jugador.planta, (x, y), delante, "paso")
				):
					proponer(2, 1.3, ("bordillo", otro_delante.id), _("Bordillo delante."), 20.0, 3.0)
		radio = (0.0, 1.5, 2.5, 4.0)[min(3, detalle)]
		for d, referencia in mundo.referencias_cerca(jugador.planta, x, y, radio):
			if referencia.tipo == "semaforo" and detalle < 3:
				continue
			punto = (referencia.x, referencia.y)
			if not mundo.visible(jugador.planta, (x, y), punto, "vista"):
				continue
			if d < 0.5:
				texto = referencia.nombre + "."
			elif detalle >= 3:
				texto = s.leng.a_distancia(referencia.nombre, d, hacia(punto)) + "."
			else:
				texto = _("{nombre}, {direccion}.").format(nombre=referencia.nombre, direccion=hacia(punto))
			proponer(1, d, ("referencia", referencia.id), texto)
		if detalle >= 2:
			for d, info in mundo.aberturas_cerca(jugador.planta, x, y, 1.5):
				if d < jugador.radio + 0.15 or not info.sobre_pared or not mundo.visible(jugador.planta, (x, y), info.centro, "vista"):
					continue
				estado = mundo.estado_abertura(info.abertura.id)
				nombre = s.leng.abertura(info.abertura, estado, con_nombre=detalle >= 3)
				relativo = geo.diferencia_rumbos(jugador.rumbo, geo.rumbo_entre((x, y), info.centro))
				if abs(relativo) > 115.0:
					# Lo que queda a la espalda acaba de pasarse: no hace falta decirlo.
					continue
				proponer(
					1,
					d,
					("abertura", info.abertura.id),
					_("{nombre}, {lado}.").format(nombre=nombre, lado=s.leng.lado(relativo)),
					60.0,
					3.0,
				)
			for d, info_objeto in mundo.objetos_cerca(jugador.planta, x, y, 2.0):
				if info_objeto.sonidos.get("propio") and mundo.visible(
					jugador.planta, (x, y), (info_objeto.objeto.x, info_objeto.objeto.y), "vista"
				):
					punto = (info_objeto.objeto.x, info_objeto.objeto.y)
					proponer(
						1,
						d,
						("objeto", info_objeto.objeto.id),
						_("{nombre}, {direccion}.").format(nombre=info_objeto.objeto.nombre, direccion=hacia(punto)),
					)
		if detalle >= 3:
			impacto = mundo.rayo(jugador.planta, (x, y), jugador.rumbo, 1.6, "paso")
			if impacto is not None and impacto.seg.clase == "objeto":
				proponer(
					2,
					impacto.distancia,
					("delante", impacto.seg.elemento_id),
					_("{nombre} delante.").format(nombre=impacto.seg.nombre or _("Objeto")),
					30.0,
					2.0,
				)
		if not candidatos:
			return
		candidatos.sort(key=lambda c: (-c[0], c[1]))
		for prioridad, _d, clave, texto, _espera, _lejos in candidatos[:MAX_AVISOS_SEGUIDOS]:
			self._apuntar_aviso(clave)
			self.avisos_dados += 1
			s.decir(
				texto, canal="aviso" if prioridad >= 3 else "juego", prioridad=prioridad, clave="/".join(str(c) for c in clave), caduca=6.0
			)
			s.registrar("aviso", clase=str(clave[0]), elemento=str(clave[1]), texto=texto)
