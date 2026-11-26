"""Los juegos: búsqueda, pistas encadenadas, sacar los tesoros, escondite, sigue al guía, explorador y cruces.

Son la parte lúdica y, a la vez, la que mejor respalda la evidencia: quien
aprende un edificio buscando objetos por todo él y sacándolos por la salida
más cercana encuentra después mejor los atajos y las salidas que quien sigue
rutas dictadas (Connors y otros, 2014). Por eso todos obligan a recorrer el
entorno entero y ninguno se gana solo siguiendo una baliza.

Cada clase redefine únicamente su regla; lo común (premios, ayudas, niveles,
resultado, órdenes del profesional) está en ``base.Actividad``.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from app.actividades import puntuacion
from app.actividades.base import Actividad, Premio
from app.actividades.lugares import (
	Lugar,
	abertura_cruzada,
	lugares_de_espacios,
	pista_de_lugar,
	punto_interior_de_abertura,
	punto_libre_en,
	resolver_lugar,
	salidas_ordenadas,
)
from app.core.i18n import _, _n
from app.dominio.modelo import Espacio, Posicion
from app.motor import eventos as ev

log = logging.getLogger(__name__)

RADIO_ENCONTRAR = 1.1
RADIO_LLEGADA_GUIA = 1.8
LARGO_PASO_GUIA = 0.65
INTERVALO_LLAMADA = 4.0


class Busqueda(Actividad):
	"""Búsqueda del tesoro: encontrar todos los premios, en cualquier orden o en el de la lista."""

	ESTRELLAS = ("completar", "pocas_ayudas", "sin_choques", "exploracion")
	PREMIOS_OBLIGATORIOS = True

	def _ordenada(self) -> bool:
		return bool(self.datos.get("orden_obligatorio"))

	def _siguiente(self) -> Premio | None:
		pendientes = self.premios_pendientes()
		return pendientes[0] if pendientes else None

	def _premio_disponible(self, premio: Premio) -> bool:
		if premio.extra or not self._ordenada():
			return True
		return premio is self._siguiente()

	def _preparar(self, sesion: Any) -> None:
		self.total = len(self.premios_pendientes())
		self.fase = "buscar"

	def _tic(self, sesion: Any, dt: float) -> None:
		if self.total == 0:
			# Sin premios en juego no hay nada que buscar: se termina en vez de dejar al alumno dando vueltas.
			self._terminar(sesion, False, "sin_premios")

	def _texto_inicio(self) -> str:
		partes = [self.tx("busqueda_inicio")]
		if self.datos.get("anunciar_premios", True) and self.total:
			if self.estilo == "adulto":
				partes.append(_n("Hay {n} cosa que encontrar.", "Hay {n} cosas que encontrar.", self.total).format(n=self.total))
			else:
				partes.append(_n("Hay {n} premio escondido.", "Hay {n} premios escondidos.", self.total).format(n=self.total))
		return " ".join(partes)

	def texto_objetivo(self) -> str:
		pendientes = self.premios_pendientes()
		if not pendientes:
			return ""
		if self._ordenada():
			return self.tx("busqueda_siguiente", nombre=pendientes[0].nombre)
		if self.datos.get("anunciar_premios", True):
			return self.tx("busqueda_lista", lista=self.tx.lista([p.nombre for p in pendientes]))
		return _n("Queda {n} por encontrar.", "Quedan {n} por encontrar.", len(pendientes)).format(n=len(pendientes))

	def _premio_recogido(self, sesion: Any, premio: Premio) -> None:
		if premio.extra:
			return
		self._logro(sesion, premio.id, premio.nombre, celebrar=False)
		pendientes = self.premios_pendientes()
		if not pendientes:
			self._terminar(sesion, True)
			return
		self._anunciar_resto(sesion, pendientes)

	def _anunciar_resto(self, sesion: Any, pendientes: list[Premio]) -> None:
		if self.es_examen:
			return
		texto = _n("Queda {n}.", "Quedan {n}.", len(pendientes)).format(n=len(pendientes))
		if self._ordenada():
			texto = f"{texto} {self.tx('busqueda_siguiente', nombre=pendientes[0].nombre)}"
		self._decir(sesion, texto, clave="resto")

	def _lugar_actual(self) -> Lugar | None:
		pendientes = [p for p in self.premios_pendientes() if self._premio_disponible(p)]
		if not pendientes:
			return None
		sesion = self._sesion
		if sesion is None or self._ordenada():
			return pendientes[0].lugar()
		return min(pendientes, key=lambda p: (sesion.distancia_a(p.terna), p.id)).lugar()

	def _datos_estrellas(self, sesion: Any) -> dict[str, Any]:
		return {"exploracion": self._exploracion(sesion)}

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		return {"exploracion": self._exploracion(sesion), "premios_encontrados": sum(1 for p in self.premios if p.recogido and not p.extra)}


class Pistas(Busqueda):
	"""Pistas encadenadas: solo suena el premio que toca, y al cogerlo se oye la pista del siguiente."""

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._pista_actual = ""

	def _ordenada(self) -> bool:
		return True

	def _preparar(self, sesion: Any) -> None:
		super()._preparar(sesion)
		self._pista_actual = self._pista_de(sesion, self._siguiente())

	def _pista_de(self, sesion: Any, premio: Premio | None) -> str:
		"""La pista escrita por el profesional o, si falta y se permite, una redactada con el entorno."""
		if premio is None:
			return ""
		if premio.pista:
			return premio.pista
		if not self.datos.get("pistas_automaticas", True):
			return ""
		return pista_de_lugar(self.entorno, sesion.nav, premio.lugar(), 1, premio.dentro_de or "")

	def _texto_inicio(self) -> str:
		return self.tx("pistas_inicio")

	def texto_objetivo(self) -> str:
		siguiente = self._siguiente()
		if siguiente is None:
			return ""
		if not self._pista_actual:
			return self.tx("pista_sin_texto")
		clave = "pista_primera" if self.hechos == 0 else "pista_siguiente"
		return f"{self.tx(clave)} {self._pista_actual}"

	def _anunciar_resto(self, sesion: Any, pendientes: list[Premio]) -> None:
		self._pista_actual = self._pista_de(sesion, pendientes[0])
		if self.es_examen:
			return
		sesion.sonar("logro/pista", bus="ayudas", retardo=0.5)
		self._decir(sesion, self.texto_objetivo(), clave="pista", caduca=30.0)

	def _texto_pista(self, sesion: Any, lugar: Lugar, detalle: int) -> str:
		if detalle <= 1 and self._pista_actual:
			return self._pista_actual
		premio = self._siguiente()
		return pista_de_lugar(self.entorno, sesion.nav, lugar, max(2, detalle), (premio.dentro_de or "") if premio is not None else "")


class SacarTesoros(Actividad):
	"""Sacar los tesoros: recoger de uno en uno y sacarlos por la salida más cercana.

	Es el juego de AbES. Cada tesoro puntúa 3, 2, 1 o 0 según el puesto de la
	salida elegida entre las salidas ordenadas por distancia de camino desde
	donde se cogió. Esa puntuación, calculada durante el juego, es la que en
	el estudio con adolescentes predijo el rendimiento en el edificio real.
	"""

	ESTRELLAS = ("completar", "salida_optima", "pocas_ayudas", "sin_choques")
	PREMIOS_OBLIGATORIOS = True

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._llevando: Premio | None = None
		self._salidas: list[tuple[str, float]] = []
		self._sacados: list[dict[str, Any]] = []
		self._t_cogido = 0.0
		self._t_aviso_llevas = -100.0

	def _preparar(self, sesion: Any) -> None:
		self.total = len(self.premios_pendientes())
		self.puntos_maximos = puntuacion.PUNTOS_SALIDA_MAXIMO * self.total
		self.fase = "buscar"

	def _tic(self, sesion: Any, dt: float) -> None:
		if self.total == 0:
			self._terminar(sesion, False, "sin_premios")

	def _premio_disponible(self, premio: Premio) -> bool:
		# Mientras se lleva un tesoro los demás callan: ahora lo que hay que escuchar es el edificio.
		return self._llevando is None or premio.extra

	def _se_puede_mover(self, premio: Premio) -> bool:
		return premio is not self._llevando

	def _premio_anadido(self, sesion: Any, premio: Premio) -> None:
		self.puntos_maximos += puntuacion.PUNTOS_SALIDA_MAXIMO

	def _puede_recoger(self, sesion: Any, premio: Premio) -> bool:
		if self._llevando is None or premio.extra:
			return True
		if sesion.t - self._t_aviso_llevas > 6.0:
			self._t_aviso_llevas = sesion.t
			self._decir(sesion, self.tx("tesoro_ya_llevas"), prioridad=2, clave="llevas")
		return False

	def _texto_inicio(self) -> str:
		return self.tx("tesoros_inicio")

	def texto_objetivo(self) -> str:
		if self._llevando is not None:
			return self.tx("tesoro_llevar", nombre=self._llevando.nombre)
		pendientes = self.premios_pendientes()
		if not pendientes:
			return ""
		return f"{self.tx('tesoro_buscar')} " + _n("Queda {n}.", "Quedan {n}.", len(pendientes)).format(n=len(pendientes))

	def _premio_recogido(self, sesion: Any, premio: Premio) -> None:
		if premio.extra:
			return
		jugador = sesion.jugador
		self._llevando = premio
		self._t_cogido = sesion.t
		self.fase = "sacar"
		self._salidas = salidas_ordenadas(sesion.nav, (jugador.planta, jugador.x, jugador.y))
		self._abrir_tramo(sesion, None, optimo=self._salidas[0][1] if self._salidas else None)
		self._tramo["destino"] = premio.nombre
		self._guiar(sesion, None)
		self._decir(sesion, self.tx("tesoro_llevar", nombre=premio.nombre), clave="llevar")

	def _tras_mover(self, sesion: Any) -> None:
		info = abertura_cruzada(sesion)
		if info is None:
			return
		premio = self._llevando
		if premio is None or not info.abertura.es_salida:
			self._volver_adentro(sesion, info, self.tx("salir_sin_tesoro" if info.abertura.es_salida else "no_es_salida"))
			return
		puntos = puntuacion.puntos_salida(info.abertura.id, self._salidas, float(self.datos.get("tolerancia_m") or 0.0))
		tramo = self._cerrar_tramo(sesion) or {}
		mejor = self._salidas[0] if self._salidas else ("", None)
		self._llevando = None
		self.fase = "buscar"
		self.puntos += puntos
		dato = {
			"n": len(self._sacados) + 1,
			"id": premio.id,
			"nombre": premio.nombre,
			"salida": info.abertura.id,
			"salida_nombre": info.abertura.nombre,
			"salida_mas_cercana": mejor[0],
			"puntos": puntos,
			"tiempo_s": round(sesion.t - self._t_cogido, 1),
			"camino_m": tramo.get("real_m"),
			"optimo_m": tramo.get("optimo_m"),
			"cociente": tramo.get("cociente"),
		}
		self._sacados.append(dato)
		sesion.registrar("salida_puntuada", **dato)
		if puntos >= puntuacion.PUNTOS_SALIDA_MAXIMO:
			texto = self.tx("tesoro_fuera_mejor")
		else:
			texto = self.tx("tesoro_fuera_peor")
			self._fallo(sesion, "salida")
		texto = f"{texto} " + _n("{n} punto.", "{n} puntos.", puntos).format(n=puntos)
		self._logro(sesion, premio.id, premio.nombre, texto)
		if not self.premios_pendientes():
			self._terminar(sesion, True)
			return
		self._volver_adentro(sesion, info, self.tx("vuelves_a_entrar"))
		self._refrescar_fuentes(sesion)

	def _volver_adentro(self, sesion: Any, info: Any, texto: str) -> None:
		"""Devuelve al alumno al interior, junto a la puerta por la que ha salido y mirando hacia dentro."""
		dentro = punto_interior_de_abertura(sesion.mundo, info)
		if dentro is None:
			return
		(x, y), rumbo = dentro
		if not self.es_examen:
			self._decir(sesion, texto, clave="entrar")
		sesion.recolocar(Posicion(info.planta_id, x, y, rumbo))

	def _lugar_actual(self) -> Lugar | None:
		sesion = self._sesion
		if sesion is None:
			return None
		if self._llevando is not None:
			salida = sesion.nav.salida_mas_cercana((sesion.jugador.planta, sesion.jugador.x, sesion.jugador.y))
			return resolver_lugar(self.entorno, salida.abertura.id) if salida is not None else None
		pendientes = self.premios_pendientes()
		if not pendientes:
			return None
		return min(pendientes, key=lambda p: (sesion.distancia_a(p.terna), p.id)).lugar()

	def _texto_pista(self, sesion: Any, lugar: Lugar, detalle: int) -> str:
		if self._llevando is None:
			return super()._texto_pista(sesion, lugar, detalle)
		# Con el tesoro en la mano la primera pista recuerda qué salidas hay; solo si se insiste se dice cuál es la más cercana.
		if detalle <= 1:
			nombres = [str(getattr(self.entorno.elemento(ident), "nombre", "") or _("una salida")) for ident, _distancia in self._salidas]
			return self.tx("salidas_hay", lista=self.tx.lista(nombres))
		return self.tx("salida_cercana", nombre=lugar.nombre)

	def _puntuaciones(self, sesion: Any) -> dict[str, Any] | None:
		medias = [float(d["puntos"]) for d in self._sacados]
		media = puntuacion.media(medias)
		return {
			"medida": "salida_mas_corta",
			"puntos": self.puntos,
			"puntos_maximos": puntuacion.PUNTOS_SALIDA_MAXIMO * len(self._sacados),
			"media_puntos": round(media, 2) if media is not None else None,
			"tesoros_sacados": len(self._sacados),
			"tesoros_total": self.total,
			"pruebas": list(self._sacados),
		}

	def _datos_estrellas(self, sesion: Any) -> dict[str, Any]:
		return {"media_salida": puntuacion.media([float(d["puntos"]) for d in self._sacados])}

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		return {"salidas": list(self._sacados)}


class Escondite(Actividad):
	"""El escondite: un personaje (o, para un adulto, un teléfono que suena) escondido que se delata de vez en cuando."""

	ESTRELLAS = ("completar", "pocas_ayudas", "atajo", "sin_choques")

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self.personaje = ""
		self._candidatos: list[Lugar] = []
		self._propios = False
		self._escondite: Lugar | None = None
		self._rondas: list[dict[str, Any]] = []

	def _preparar(self, sesion: Any) -> None:
		self.personaje = str(self.datos.get("personaje") or "") or self.tx("personaje")
		self.total = int(self.datos.get("rondas") or 1)
		propios = [self.lugar(objetivo.get("destino")) for objetivo in self.datos["objetivos"]]
		self._candidatos = [lugar for lugar in propios if lugar is not None]
		self._propios = bool(self._candidatos)
		if not self._candidatos:
			self._candidatos = lugares_de_espacios(sesion.mundo, sesion.nav, sesion.inicio)
		self.fase = "buscar"
		self._esconder(sesion)

	def _esconder(self, sesion: Any) -> None:
		"""Elige el siguiente escondite: lejos del alumno, distinto del anterior, y lo pone a sonar."""
		jugador = sesion.jugador
		origen = (jugador.planta, jugador.x, jugador.y)
		aqui = sesion.mundo.espacio_en(*origen)
		previo = self._escondite
		con_distancia: list[tuple[float, Lugar]] = []
		for lugar in self._candidatos:
			if previo is not None and lugar.elemento_id == previo.elemento_id and lugar.punto == previo.punto and len(self._candidatos) > 1:
				continue
			if aqui is not None and lugar.clase == "espacio" and lugar.elemento_id == aqui.id and len(self._candidatos) > 2:
				continue
			distancia = sesion.nav.distancia(origen, lugar.terna)
			if distancia is not None:
				con_distancia.append((distancia, lugar))
		if not con_distancia:
			self._escondite = None
			return
		con_distancia.sort(key=lambda par: (-round(par[0], 1), par[1].elemento_id, par[1].punto))
		# De la mitad más lejana se sortea uno: siempre hay que andar, pero no siempre al mismo sitio.
		mitad = con_distancia[: max(1, (len(con_distancia) + 1) // 2)]
		distancia, elegido = self.azar.choice(mitad)
		x, y = elegido.x, elegido.y
		if not self._propios and elegido.clase == "espacio":
			espacio = self.entorno.elemento(elegido.elemento_id)
			punto = punto_libre_en(sesion.mundo, elegido.planta, espacio, self.azar) if isinstance(espacio, Espacio) else None
			if punto is not None:
				x, y = punto
		self._escondite = Lugar(elegido.planta, x, y, elegido.nombre, "punto", elegido.elemento_id, RADIO_ENCONTRAR)
		sesion.anadir_fuente(
			"escondite",
			str(self.datos.get("sonido") or "premio/aparece"),
			self._escondite.terna,
			volumen=1.0,
			radio=45.0,
			bucle=False,
			intervalo=float(self.datos.get("cada_s") or 4.0),
			bus="efectos",
		)
		self._abrir_tramo(sesion, self._escondite)
		self._guiar(sesion, self._escondite)

	def _tic(self, sesion: Any, dt: float) -> None:
		if self._escondite is None:
			self._terminar(sesion, False, "sin_escondites")

	def _texto_inicio(self) -> str:
		return self.tx("escondite_inicio", personaje=self.personaje)

	def texto_objetivo(self) -> str:
		texto = self.tx("escondite_objetivo", personaje=self.personaje)
		if self.total > 1:
			texto = f"{texto} {self.tx('ronda', n=min(self.total, self.hechos + 1), total=self.total)}"
		return texto

	def _tras_mover(self, sesion: Any) -> None:
		escondite = self._escondite
		if escondite is None or sesion.distancia_a(escondite.terna) > escondite.radio:
			return
		jugador = sesion.jugador
		if not sesion.mundo.visible(jugador.planta, jugador.punto, escondite.punto, "paso"):
			# Al otro lado de un tabique no vale: hay que llegar hasta él.
			return
		sesion.quitar_fuente("escondite")
		tramo = self._cerrar_tramo(sesion) or {}
		self._rondas.append({"n": self.hechos + 1, "lugar": escondite.nombre, "t": round(sesion.t, 1), **tramo})
		self._logro(sesion, f"ronda-{self.hechos + 1}", escondite.nombre, self.tx("escondite_encontrado"))
		if self.hechos >= self.total:
			self._terminar(sesion, True)
			return
		self._decir(sesion, self.tx("escondite_otra"), clave="otra")
		self._esconder(sesion)

	def _lugar_actual(self) -> Lugar | None:
		return self._escondite

	def _al_cerrar(self, sesion: Any) -> None:
		sesion.quitar_fuente("escondite")

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		return {"rondas": list(self._rondas)}


class SigueGuia(Actividad):
	"""Sigue al guía: un guía recorre el camino más corto hasta el destino y se le sigue por el sonido de sus pasos.

	El guía suena con los pasos del suelo que pisa, con la misma oclusión que
	cualquier otra fuente. Se para a esperar si el alumno se queda atrás y,
	ante una escalera o un ascensor, espera a que llegue, dice por dónde hay
	que seguir y aguarda al otro lado.
	"""

	ESTRELLAS = ("completar", "pocas_ayudas", "sin_choques")

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self.guia = ""
		self._destino: Lugar | None = None
		self._puntos: list[tuple[str, float, float]] = []
		self._conectores: list[str] = []
		self._indice = 0
		self._g: tuple[str, float, float] | None = None
		self._resto_paso = 0.0
		self._pie = False
		self._esperando = False
		self._alejado = False
		self._alejamientos = 0
		self._t_llamada = 0.0
		self._t_total = 0.0
		self._t_cerca = 0.0
		self._saltos = 0

	def modo_baliza(self) -> str:
		# El guía es la ayuda: no hay baliza que acompañe.
		return "nunca"

	def _preparar(self, sesion: Any) -> None:
		self.guia = str(self.datos.get("personaje") or "") or self.tx("guia")
		self.total = 1
		self._destino = self.lugar(self.datos.get("destino"))
		if self._destino is None:
			return
		jugador = sesion.jugador
		ruta = sesion.nav.ruta((jugador.planta, jugador.x, jugador.y), self._destino.terna)
		if ruta is None or len(ruta.puntos) < 2:
			self._destino = None
			return
		self._puntos = list(ruta.puntos)
		self._conectores = list(ruta.conectores)
		self._g = self._puntos[0]
		self._indice = 1
		self._abrir_tramo(sesion, self._destino, optimo=ruta.longitud)
		self.fase = "seguir"

	def _texto_inicio(self) -> str:
		return self.tx("guia_inicio", guia=self.guia)

	def texto_objetivo(self) -> str:
		return self.tx("guia_objetivo")

	def _lugar_actual(self) -> Lugar | None:
		if self._g is None:
			return None
		return Lugar(self._g[0], self._g[1], self._g[2], self.guia, "punto", "", RADIO_LLEGADA_GUIA)

	def _distancia_al_guia(self, sesion: Any) -> float:
		return sesion.distancia_a(self._g) if self._g is not None else math.inf

	def _sonar_en_guia(self, sesion: Any, sonido: str, volumen: float = 1.0) -> None:
		"""Un sonido suelto desde donde está el guía, con la oclusión real del motor."""
		if self._g is None:
			return
		sesion.anadir_fuente("guia", sonido, self._g, volumen=volumen, radio=30.0, bucle=False, intervalo=3600.0, altura=0.2, bus="efectos")
		sesion.acustica.disparar("guia")

	def _tic(self, sesion: Any, dt: float) -> None:
		if self._destino is None or self._g is None:
			self._terminar(sesion, False, "sin_ruta")
			return
		distancia = self._distancia_al_guia(sesion)
		espera = float(self.datos.get("distancia_espera") or 4.0)
		self._t_total += dt
		if distancia <= espera:
			self._t_cerca += dt
		if distancia > espera * 2.0 and math.isfinite(distancia):
			if not self._alejado:
				self._alejado = True
				self._alejamientos += 1
				self._decir(sesion, self.tx("guia_lejos"), prioridad=2, clave="guia")
				self._fallo(sesion, "alejado")
		elif distancia <= espera:
			if self._alejado:
				self._avance(sesion)
			self._alejado = False
		if self._indice >= len(self._puntos):
			# El guía ya está en el destino: espera a que el alumno llegue hasta él.
			if distancia <= RADIO_LLEGADA_GUIA:
				self._cerrar_tramo(sesion)
				self._logro(sesion, "destino", self._destino.nombre, self.tx("guia_llegada", lugar=self._destino.nombre))
				self._terminar(sesion, True)
				return
			self._llamar(sesion, dt)
			return
		siguiente = self._puntos[self._indice]
		if siguiente[0] != self._g[0]:
			# Cambio de planta: el guía no sube sin el alumno. Le espera, le dice por dónde y aguarda arriba (o abajo).
			if distancia <= 2.5:
				nombre = self._nombre_conector()
				self._decir(sesion, self.tx("guia_conector", conector=nombre), clave="guia")
				self._g = siguiente
				self._indice += 1
				self._saltos += 1
				self._esperando = False
			else:
				self._llamar(sesion, dt)
			return
		if distancia > espera:
			self._llamar(sesion, dt)
			return
		self._esperando = False
		self._andar(sesion, dt)

	def _nombre_conector(self) -> str:
		ident = self._conectores[self._saltos] if self._saltos < len(self._conectores) else ""
		conector = self.entorno.elemento(ident) if ident else None
		return str(getattr(conector, "nombre", "") or _("hay que cambiar de planta"))

	def _llamar(self, sesion: Any, dt: float) -> None:
		"""El guía está parado esperando: llama de vez en cuando para que se le pueda localizar."""
		if not self._esperando:
			self._esperando = True
			self._t_llamada = 0.0
		self._t_llamada -= dt
		if self._t_llamada > 0.0:
			return
		self._t_llamada = INTERVALO_LLAMADA
		self._sonar_en_guia(sesion, "premio/aparece")
		if math.isfinite(self._distancia_al_guia(sesion)):
			self._decir(sesion, self.tx("guia_espera"), prioridad=1, clave="guia_espera", caduca=3.0)

	def _andar(self, sesion: Any, dt: float) -> None:
		"""Avanza al guía por su camino y hace sonar sus pasos sobre el suelo que pisa."""
		assert self._g is not None
		resto = float(self.datos.get("velocidad_guia") or 0.8) * dt
		planta, x, y = self._g
		while resto > 1e-9 and self._indice < len(self._puntos):
			destino = self._puntos[self._indice]
			if destino[0] != planta:
				break
			tramo = math.hypot(destino[1] - x, destino[2] - y)
			if tramo <= resto:
				x, y = destino[1], destino[2]
				resto -= tramo
				self._resto_paso += tramo
				self._indice += 1
			else:
				x += (destino[1] - x) * resto / tramo
				y += (destino[2] - y) * resto / tramo
				self._resto_paso += resto
				resto = 0.0
		self._g = (planta, x, y)
		if self._resto_paso >= LARGO_PASO_GUIA:
			self._resto_paso = 0.0
			self._pie = not self._pie
			suelo = sesion.mundo.suelo_en(planta, x, y)
			self._sonar_en_guia(sesion, ev.sonido_paso(suelo, self._pie, 1 + self.azar.randrange(3)))

	def _al_cerrar(self, sesion: Any) -> None:
		sesion.quitar_fuente("guia")

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		return {
			"alejamientos": self._alejamientos,
			"tiempo_cerca_del_guia": round(self._t_cerca / self._t_total, 3) if self._t_total > 0.0 else None,
			"destino": self._destino.a_dato() if self._destino is not None else None,
		}


class Explorador(Actividad):
	"""El explorador: descubrir todos los espacios; cada uno nuevo suena a hallazgo."""

	ESTRELLAS = ("completar", "pocas_ayudas", "sin_choques", "exploracion")

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._descubiertos: list[str] = []

	def _preparar(self, sesion: Any) -> None:
		todos = self._espacios_a_explorar(sesion)
		fraccion = float(self.datos.get("fraccion") or 1.0)
		self.total = max(1, math.ceil(len(todos) * fraccion - 1e-9)) if todos else 0
		self.fase = "explorar"

	def _texto_inicio(self) -> str:
		return self.tx("explorador_inicio")

	def texto_objetivo(self) -> str:
		faltan = max(0, self.total - self.hechos)
		return _n("Te queda {n} espacio por descubrir.", "Te quedan {n} espacios por descubrir.", faltan).format(n=faltan)

	def _tic(self, sesion: Any, dt: float) -> None:
		if self.total == 0:
			self._terminar(sesion, False, "sin_espacios")

	def _al_registro(self, sesion: Any, tipo: str, datos: dict[str, Any]) -> None:
		if tipo != "entrada_espacio":
			return
		ident = str(datos.get("espacio") or "")
		if ident in self._descubiertos or ident not in self._espacios_a_explorar(sesion):
			return
		self._descubiertos.append(ident)
		self._logro(sesion, ident, str(datos.get("nombre") or ident), celebrar=False)
		if not self.es_examen:
			sesion.sonar("premio/aparece", bus="efectos")
			sesion.vibrar("objetivo")
			self._decir(sesion, self.tx("descubierto", n=self.hechos, total=self.total), prioridad=2, clave="descubierto", caduca=6.0)
		if self.hechos >= self.total:
			self._terminar(sesion, True)

	def _lugar_actual(self) -> Lugar | None:
		sesion = self._sesion
		if sesion is None:
			return None
		pendientes = [resolver_lugar(self.entorno, ident) for ident in self._espacios_a_explorar(sesion) if ident not in self._descubiertos]
		validos = [lugar for lugar in pendientes if lugar is not None]
		if not validos:
			return None
		return min(validos, key=lambda lugar: (sesion.distancia_a(lugar.terna), lugar.elemento_id))

	def _datos_estrellas(self, sesion: Any) -> dict[str, Any]:
		return {"exploracion": self._exploracion(sesion)}

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		return {"exploracion": self._exploracion(sesion), "espacios_descubiertos": list(self._descubiertos)}


class Cruce(Actividad):
	"""Cruza con el pitido: decidir cuándo cruzar una calzada.

	Usa lo que mide el motor en cada cruce (si fue por el paso, la fase del
	semáforo y si un vehículo tuvo que frenar o pasó al lado). Es una
	práctica de decisión con tráfico simulado: no dice que un cruce real sea
	seguro.
	"""

	ESTRELLAS = ("completar", "pocas_ayudas", "seguridad")

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._cruces: list[dict[str, Any]] = []
		self._incidente = False
		self._destino: Lugar | None = None

	def _retocar_ajustes(self, ajustes: Any) -> None:
		# Sin tráfico no hay nada que decidir; solo se apaga si el profesional lo pide expresamente.
		ajustes.trafico = self.datos.get("trafico", True) is not False

	def _preparar(self, sesion: Any) -> None:
		self.total = int(self.datos.get("cruces") or 1)
		self._destino = self.lugar(self.datos.get("destino"))
		self.fase = "cruzar"

	def _texto_inicio(self) -> str:
		return self.tx("cruce_inicio")

	def texto_objetivo(self) -> str:
		if self.fase == "llegar" and self._destino is not None:
			return self.tx("paso_ir", lugar=self._destino.nombre)
		faltan = max(0, self.total - self.hechos)
		return _n("Te queda {n} cruce.", "Te quedan {n} cruces.", faltan).format(n=faltan)

	def _al_registro(self, sesion: Any, tipo: str, datos: dict[str, Any]) -> None:
		if tipo == "cruce_empieza":
			self._incidente = False
		elif tipo == "cruce_inseguro":
			self._incidente = True
		elif tipo == "cruce":
			self._puntuar_cruce(sesion, datos)

	def _puntuar_cruce(self, sesion: Any, datos: dict[str, Any]) -> None:
		if datos.get("vuelve"):
			# Bajó a la calzada y se volvió a su acera: no ha cruzado. Si hubo incidente, cuenta como tropiezo.
			if self._incidente:
				self._fallo(sesion, "cruce")
			return
		en_rojo = bool(datos.get("en_rojo"))
		por_paso = bool(datos.get("por_paso"))
		incidente = self._incidente or (not datos.get("seguro", True) and not en_rojo)
		puntos = puntuacion.puntos_cruce(incidente, por_paso, en_rojo)
		dato = {
			"n": len(self._cruces) + 1,
			"via": str(datos.get("via") or ""),
			"paso": str(datos.get("paso") or ""),
			"por_paso": por_paso,
			"fase": str(datos.get("fase") or ""),
			"en_rojo": en_rojo,
			"incidente": incidente,
			"puntos": puntos,
			"tiempo_s": datos.get("duracion"),
		}
		self._cruces.append(dato)
		self.puntos += puntos
		self.puntos_maximos += 3
		sesion.registrar("cruce_puntuado", **dato)
		if puntos < 2:
			self._fallo(sesion, "cruce")
		if self.fase != "cruzar":
			return
		self._logro(
			sesion, f"cruce-{dato['n']}", dato["paso"] or dato["via"] or _("cruce"), self.tx(f"cruce_{puntos}"), celebrar=puntos == 3
		)
		if puntos < 3 and not self.es_examen:
			self._decir(sesion, self.tx(f"cruce_{puntos}"), clave="cruce")
		if self.hechos < self.total:
			return
		if self._destino is None:
			self._terminar(sesion, True)
			return
		self.fase = "llegar"
		self._guiar(sesion, self._destino)
		self._decir(sesion, self.tx("cruce_llegar", lugar=self._destino.nombre), clave="llegar")
		if self._destino.alcanzado(sesion):
			self._terminar(sesion, True)

	def _tras_mover(self, sesion: Any) -> None:
		if self.fase == "llegar" and self._destino is not None and self._destino.alcanzado(sesion):
			self._terminar(sesion, True)

	def _lugar_actual(self) -> Lugar | None:
		return self._destino if self.fase == "llegar" else None

	def _dar_pista(self, sesion: Any) -> str:
		if self.fase == "llegar":
			return super()._dar_pista(sesion)
		# La pista de un cruce no es un lugar: es recordar cómo se decide.
		return _(
			"Busca un paso de peatones. Si hay semáforo, espera a oír el verde; si no lo hay, espera a no oír ningún vehículo acercarse."
		)

	def _puntuaciones(self, sesion: Any) -> dict[str, Any] | None:
		media = puntuacion.media([float(c["puntos"]) for c in self._cruces])
		return {
			"medida": "cruces",
			"puntos": self.puntos,
			"puntos_maximos": self.puntos_maximos,
			"media_puntos": round(media, 2) if media is not None else None,
			"cruces": len(self._cruces),
			"cruces_sin_incidente": sum(1 for c in self._cruces if not c["incidente"]),
			"cruces_por_el_paso": sum(1 for c in self._cruces if c["por_paso"]),
			"cruces_en_rojo": sum(1 for c in self._cruces if c["en_rojo"]),
			"pruebas": list(self._cruces),
		}

	def _datos_estrellas(self, sesion: Any) -> dict[str, Any]:
		return {"seguro": bool(self._cruces) and all(c["puntos"] == 3 for c in self._cruces)}

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		return {"cruces": list(self._cruces)}
