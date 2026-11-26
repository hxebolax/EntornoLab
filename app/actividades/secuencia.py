"""Actividades hechas de pasos: ir a un sitio, recoger, entregar, volver.

El recadero, las rutas (directa, inversa, alternativa, volver al origen),
localizar un espacio y la visita guiada son la misma cosa por dentro: una
lista de pasos, cada uno con un lugar al que llegar. Aquí está ese motor de
pasos (heredero del de misiones declarativas de Puerto Bravo, del mismo
autor: pasos, puntos de control y conteo de fallos) y las actividades que lo
usan.

Cada paso medido compara lo andado con el camino más corto que da el
navegador, y de ahí sale el cociente camino real / camino óptimo.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from app.actividades.base import Actividad
from app.actividades.lugares import Lugar, abertura_cruzada, espacios_jugables, lugar_de_espacio
from app.core.i18n import _, _n
from app.dominio.modelo import Abertura, Conector, Espacio
from app.motor import eventos as ev
from app.motor.eventos import Evento

log = logging.getLogger(__name__)

RADIO_ORIGEN = 1.5


@dataclass
class Paso:
	"""Un paso de una actividad: adónde hay que ir y qué pasa al llegar."""

	id: str
	tipo: str  # ir_a | recoger | entregar | volver | localizar | salir
	lugar: Lugar
	nombre: str = ""  # lo que se recoge o se entrega
	texto: str = ""  # frase propia del profesional (sustituye a la de serie)
	narracion: str = ""  # lo que se dice al llegar (visita guiada)
	guiado: bool = False  # con baliza paso a paso aunque el nivel no la dé (la ida de una ruta inversa)
	sin_baliza: bool = False  # sin baliza aunque el nivel la dé (la vuelta, que es lo que se mide)
	medido: bool = True  # cuenta para el cociente camino real / óptimo
	confirmar: bool = False  # hay que confirmar la llegada con la orden de usar
	evitar: tuple[str, ...] = ()
	hecho: bool = False


class Secuencia(Actividad):
	"""Actividad de pasos, en orden o en el orden que el alumno quiera."""

	ESTRELLAS = ("completar", "pocas_ayudas", "atajo", "sin_choques")
	EN_ORDEN = True

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._pasos: list[Paso] = []
		self._origen: Lugar | None = None
		self._intentos_fallidos = 0

	# ── Construcción ──

	def _construir_pasos(self, sesion: Any) -> list[Paso]:
		"""Pasos de la actividad; lo redefine cada tipo."""
		return []

	def _en_orden(self) -> bool:
		return self.EN_ORDEN

	def _paso_de_objetivo(self, objetivo: dict[str, Any], tipo: str | None = None, **opciones: Any) -> Paso | None:
		lugar = self.lugar(objetivo.get("destino"))
		if lugar is None:
			log.warning("El objetivo %s de la actividad %s no tiene un destino válido y se omite", objetivo.get("id"), self.id)
			return None
		return Paso(
			id=str(objetivo.get("id") or ""),
			tipo=tipo or str(objetivo.get("tipo") or "ir_a"),
			lugar=lugar,
			nombre=str(objetivo.get("nombre") or ""),
			texto=str(objetivo.get("texto") or ""),
			**opciones,
		)

	def _preparar(self, sesion: Any) -> None:
		jugador = sesion.jugador
		espacio = sesion.mundo.espacio_en(jugador.planta, jugador.x, jugador.y)
		nombre = espacio.nombre if espacio is not None and espacio.nombre else _("el punto de partida")
		self._origen = Lugar(jugador.planta, jugador.x, jugador.y, nombre, "punto", "", RADIO_ORIGEN)
		self._pasos = self._construir_pasos(sesion)
		self.total = len(self._pasos)
		self.fase = "pasos"
		self._empezar_paso(sesion, anunciar=False)

	def _tic(self, sesion: Any, dt: float) -> None:
		if not self._pasos:
			self._terminar(sesion, False, "sin_objetivos")

	# ── Paso actual ──

	def _pendientes(self) -> list[Paso]:
		return [paso for paso in self._pasos if not paso.hecho]

	def _paso(self) -> Paso | None:
		"""El paso que toca (en orden) o el pendiente más cercano (orden libre)."""
		pendientes = self._pendientes()
		if not pendientes:
			return None
		sesion = self._sesion
		if self._en_orden() or sesion is None:
			return pendientes[0]
		return min(pendientes, key=lambda paso: (sesion.distancia_a(paso.lugar.terna), paso.id))

	def _empezar_paso(self, sesion: Any, anunciar: bool = True) -> None:
		paso = self._paso()
		if paso is None:
			return
		if self._en_orden():
			if paso.medido:
				self._abrir_tramo(sesion, paso.lugar, paso.evitar)
			if paso.guiado and sesion.percepcion.permitida("baliza"):
				self._destino_guia = paso.lugar
				if sesion.baliza(paso.lugar.terna, por_ruta=True):
					# La ida guiada no cuenta como ayuda pedida: lo que se mide es la vuelta.
					self._ayudas_no_contadas += 1
			elif paso.sin_baliza:
				self._destino_guia = paso.lugar
				sesion.baliza(None)
			else:
				self._guiar(sesion, paso.lugar)
		if anunciar and not self.es_examen:
			self._decir(sesion, self.texto_objetivo(), clave="objetivo", caduca=20.0)

	def _texto_paso(self, paso: Paso) -> str:
		if paso.texto:
			return paso.texto
		if paso.tipo == "recoger":
			texto = self.tx("paso_recoger", lugar=paso.lugar.nombre, nombre=paso.nombre or _("el encargo"))
		elif paso.tipo == "entregar":
			texto = self.tx("paso_entregar", lugar=paso.lugar.nombre, nombre=paso.nombre or _("el encargo"))
		elif paso.tipo == "volver":
			texto = self.tx("paso_volver")
		elif paso.tipo == "localizar":
			texto = self.tx("paso_localizar", lugar=paso.lugar.nombre)
		else:
			texto = self.tx("paso_ir", lugar=paso.lugar.nombre)
		if paso.confirmar:
			texto = f"{texto} {self.tx('paso_confirmar')}"
		return texto

	def texto_objetivo(self) -> str:
		pendientes = self._pendientes()
		if not pendientes:
			return ""
		if self._en_orden():
			return self._texto_paso(pendientes[0])
		nombres = self.tx.lista([paso.lugar.nombre for paso in pendientes[:6]])
		return _n("Te queda {n} lugar por visitar: {lista}.", "Te quedan {n} lugares por visitar: {lista}.", len(pendientes)).format(
			n=len(pendientes), lista=nombres
		)

	def _lugar_actual(self) -> Lugar | None:
		paso = self._paso()
		return paso.lugar if paso is not None else None

	# ── Llegadas ──

	def _llegado(self, sesion: Any, paso: Paso) -> bool:
		if paso.tipo == "salir":
			info = abertura_cruzada(sesion)
			return (
				info is not None and info.abertura.es_salida and (not paso.lugar.elemento_id or info.abertura.id == paso.lugar.elemento_id)
			)
		return paso.lugar.alcanzado(sesion)

	def _tras_mover(self, sesion: Any) -> None:
		if self._en_orden():
			paso = self._paso()
			if paso is not None and not paso.confirmar and self._llegado(sesion, paso):
				self._paso_hecho(sesion, paso)
			return
		for paso in self._pendientes():
			if not paso.confirmar and self._llegado(sesion, paso):
				self._paso_hecho(sesion, paso)
				if self._cerrada:
					return

	def _al_interactuar(self, sesion: Any, elemento: Any) -> list[Evento]:
		paso = self._paso()
		if paso is None or not paso.confirmar or isinstance(elemento, (Abertura, Conector)):
			return []
		return self.confirmar(sesion)

	def confirmar(self, sesion: Any) -> list[Evento]:
		"""El alumno dice que ha llegado: se comprueba y, en una práctica, se le dice si es así."""
		paso = self._paso()
		# Un paso que se da por hecho al llegar no tiene nada que confirmar: la tecla de confirmar no debe contar como tropiezo.
		if paso is None or self._cerrada or not paso.confirmar:
			return []
		if self._llegado(sesion, paso):
			self._paso_hecho(sesion, paso)
		else:
			self._intentos_fallidos += 1
			self._decir(sesion, self.tx("aun_no"), clave="aun_no")
			self._fallo(sesion, "confirmacion")
		return [ev.EvSonido("interfaz/elegir", bus="interfaz")]

	def _texto_llegada(self, paso: Paso) -> str:
		if paso.narracion:
			return paso.narracion
		if paso.tipo == "recoger":
			return self.tx("recogido", nombre=paso.nombre or _("el encargo"))
		if paso.tipo == "entregar":
			return self.tx("entregado")
		return self.datos["mensajes"]["logro"] or self.tx("llegada", lugar=paso.lugar.nombre)

	def _paso_hecho(self, sesion: Any, paso: Paso) -> None:
		paso.hecho = True
		if self._en_orden() and paso.medido:
			self._cerrar_tramo(sesion)
		self._logro(sesion, paso.id or paso.lugar.elemento_id or paso.tipo, paso.nombre or paso.lugar.nombre, self._texto_llegada(paso))
		self._al_hacer_paso(sesion, paso)
		if self._cerrada:
			return
		if not self._pendientes():
			self._terminar(sesion, True)
			return
		self._empezar_paso(sesion)

	def _al_hacer_paso(self, sesion: Any, paso: Paso) -> None:
		"""Para lo que un tipo quiera hacer al completar un paso."""

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		# «pasos» a secas es, en el resumen de la sesión, el número de pasos andados: aquí se llaman de otro modo para no pisarlo.
		return {
			"pasos_actividad": [{"id": p.id, "tipo": p.tipo, "lugar": p.lugar.nombre, "hecho": p.hecho} for p in self._pasos],
			"confirmaciones_fallidas": self._intentos_fallidos,
		}


class Recadero(Secuencia):
	"""El recadero: coger algo en un sitio y llevarlo a otro. Los encargos se encadenan."""

	def _construir_pasos(self, sesion: Any) -> list[Paso]:
		pasos: list[Paso] = []
		for numero, objetivo in enumerate(self.datos["objetivos"], start=1):
			if objetivo.get("recoger") is not None or objetivo.get("entregar") is not None:
				# Forma abreviada: un encargo entero en un solo objetivo.
				nombre = str(objetivo.get("nombre") or "")
				for tipo in ("recoger", "entregar"):
					lugar = self.lugar(objetivo.get(tipo))
					if lugar is not None:
						pasos.append(Paso(f"{objetivo['id']}-{tipo}", tipo, lugar, nombre, str(objetivo.get(f"texto_{tipo}") or "")))
				continue
			paso = self._paso_de_objetivo(objetivo)
			if paso is not None:
				if not paso.id:
					paso.id = f"paso-{numero}"
				pasos.append(paso)
		return pasos

	def _texto_inicio(self) -> str:
		return self.tx("recadero_inicio")


class Ruta(Secuencia):
	"""Ruta de un punto a otro, con paradas intermedias opcionales."""

	def _construir_pasos(self, sesion: Any) -> list[Paso]:
		pasos = [paso for paso in (self._paso_de_objetivo(objetivo, "ir_a") for objetivo in self.datos["objetivos"]) if paso is not None]
		destino = self.lugar(self.datos.get("destino"))
		if destino is not None:
			pasos.append(Paso("destino", "ir_a", destino))
		return pasos

	def _texto_inicio(self) -> str:
		return self.tx("ruta_inicio")


class RutaInversa(Secuencia):
	"""Ruta inversa: se va a un lugar (con baliza, si se quiere) y se vuelve por donde se vino, que es lo que se mide."""

	def _construir_pasos(self, sesion: Any) -> list[Paso]:
		destino = self.lugar(self.datos.get("destino"))
		if destino is None or self._origen is None:
			return []
		guiada = bool(self.datos.get("ida_guiada", True))
		return [
			Paso("ida", "ir_a", destino, guiado=guiada, medido=False),
			Paso("vuelta", "volver", self._origen, texto=self.tx("paso_volver_mismo"), sin_baliza=True),
		]

	def _texto_inicio(self) -> str:
		return self.tx("ruta_inicio")


class VolverOrigen(Secuencia):
	"""Volver al origen: se pasa por varios lugares y se regresa al punto de partida por el camino más corto."""

	def _construir_pasos(self, sesion: Any) -> list[Paso]:
		if self._origen is None:
			return []
		guiada = bool(self.datos.get("ida_guiada", True))
		pasos = [
			paso
			for paso in (self._paso_de_objetivo(objetivo, "ir_a", guiado=guiada, medido=False) for objetivo in self.datos["objetivos"])
			if paso is not None
		]
		if not pasos:
			return []
		pasos.append(Paso("vuelta", "volver", self._origen, sin_baliza=True))
		return pasos

	def _texto_inicio(self) -> str:
		return self.tx("ruta_inicio")


class RutaAlternativa(Secuencia):
	"""Ruta alternativa: el paso habitual está cortado y hay que encontrar otro camino.

	Una puerta o un hueco cortados se cierran con llave en la partida (el
	entorno no se toca); un conector cortado no se puede cerrar, así que se
	avisa y se anota si el alumno lo usa de todos modos.
	"""

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._cortes: tuple[str, ...] = ()
		self._corte_usado = False

	def _construir_pasos(self, sesion: Any) -> list[Paso]:
		destino = self.lugar(self.datos.get("destino"))
		if destino is None:
			return []
		validos: list[str] = []
		for ident in self.datos["cortes"]:
			elemento = self.entorno.elemento(ident)
			if isinstance(elemento, Abertura):
				sesion.mundo.poner_abertura(ident, "con_llave")
				validos.append(ident)
			elif isinstance(elemento, Conector):
				validos.append(ident)
		self._cortes = tuple(validos)
		return [Paso("destino", "ir_a", destino, evitar=self._cortes)]

	def _nombres_cortes(self) -> str:
		nombres = [str(getattr(self.entorno.elemento(ident), "nombre", "") or _("un paso")) for ident in self._cortes]
		return self.tx.lista(nombres)

	def _texto_inicio(self) -> str:
		return self.tx("ruta_inicio")

	def texto_objetivo(self) -> str:
		texto = super().texto_objetivo()
		if texto and self._cortes:
			texto = f"{texto} {self.tx('corte_aviso', paso=self._nombres_cortes())}"
		return texto

	def _al_registro(self, sesion: Any, tipo: str, datos: dict[str, Any]) -> None:
		if tipo == "cambio_planta" and str(datos.get("conector") or "") in self._cortes and not self._corte_usado:
			self._corte_usado = True
			self._decir(sesion, self.tx("corte_usado"), clave="corte")
			self._fallo(sesion, "paso_cortado")

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		detalle = super()._detalle(sesion)
		detalle.update({"cortes": list(self._cortes), "paso_cortado_usado": self._corte_usado})
		return detalle


class Localizar(Secuencia):
	"""Localizar un espacio sabiendo solo su nombre."""

	def _construir_pasos(self, sesion: Any) -> list[Paso]:
		destino = self.lugar(self.datos.get("destino"))
		if destino is None:
			return []
		return [Paso("destino", "localizar", destino, confirmar=bool(self.datos.get("confirmar")))]

	def _texto_inicio(self) -> str:
		return self.tx("inicio")


class VisitaGuiada(Secuencia):
	"""Visita guiada: en cada zona se oye un texto preparado, o narra en vivo el profesional.

	Sin zonas definidas se visitan todos los espacios y se lee la descripción
	de cada uno. No puntúa el camino: es para conocer, no para medir.
	"""

	ESTRELLAS = ("completar", "exploracion")

	def _en_orden(self) -> bool:
		return bool(self.datos.get("orden_obligatorio"))

	def _construir_pasos(self, sesion: Any) -> list[Paso]:
		en_vivo = bool(self.datos.get("narrada_en_vivo"))
		pasos: list[Paso] = []
		for objetivo in self.datos["objetivos"]:
			paso = self._paso_de_objetivo(objetivo, "ir_a", medido=False)
			if paso is None:
				continue
			# En la visita el «texto» del objetivo es lo que se cuenta al llegar, no la orden de ir.
			narracion = paso.texto
			paso.texto = ""
			elemento = self.entorno.elemento(paso.lugar.elemento_id) if paso.lugar.elemento_id else None
			if not narracion and isinstance(elemento, Espacio):
				narracion = elemento.descripcion
			paso.narracion = "" if en_vivo else self._narracion(paso.lugar.nombre, narracion)
			pasos.append(paso)
		if pasos:
			return pasos
		alcanzables = sesion.nav.espacios_alcanzables(sesion.inicio)
		for planta, espacio in espacios_jugables(self.entorno):
			if alcanzables and espacio.id not in alcanzables:
				continue
			lugar = lugar_de_espacio(sesion.mundo, planta, espacio)
			pasos.append(
				Paso(
					espacio.id, "ir_a", lugar, medido=False, narracion="" if en_vivo else self._narracion(lugar.nombre, espacio.descripcion)
				)
			)
		return pasos

	@staticmethod
	def _narracion(nombre: str, texto: str) -> str:
		texto = (texto or "").strip()
		return f"{nombre}. {texto}" if texto else f"{nombre}."

	def _texto_inicio(self) -> str:
		texto = self.tx("visita_inicio")
		if self.datos.get("narrada_en_vivo"):
			texto = f"{texto} {self.tx('visita_en_vivo')}"
		return texto

	def _texto_llegada(self, paso: Paso) -> str:
		return paso.narracion

	def _datos_estrellas(self, sesion: Any) -> dict[str, Any]:
		return {"exploracion": self._exploracion(sesion)}

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		detalle = super()._detalle(sesion)
		detalle["exploracion"] = self._exploracion(sesion)
		detalle["mensajes_del_profesional"] = self._intervenciones.get("mensaje", 0)
		return detalle
