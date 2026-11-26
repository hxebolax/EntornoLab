"""Los exámenes: rutas, salida más corta, señalar, comparar distancias y reconstrucción.

Un examen mide; no enseña ni anima. Por eso aquí no hay pistas ni baliza
(salvo en la fase de aprendizaje de las variantes «inversa» y «atajo», que no
puntúa), no hay celebraciones intermedias y nunca se dice si se ha acertado:
tras cada prueba solo se oye «Anotado».

Reglas comunes:

- Las pruebas se generan con una semilla: con la misma semilla y el mismo
  entorno, el examen es idéntico otro día.
- El tiempo de cada prueba es tiempo de juego: en pausa no corre.
- La regla de parada termina el examen cuando ya no se puede alcanzar el
  mínimo de aciertos en las primeras pruebas, para no frustrar.
- Cada prueba deja un registro ``examen`` y el resultado lleva todas en
  ``examen["pruebas"]``.

Qué mide cada uno y en qué estudio se apoya está en ``docs/actividades.md``.
"""

from __future__ import annotations

import logging
import math
from typing import Any

from app.actividades import puntuacion
from app.actividades.base import Actividad
from app.actividades.lugares import (
	Lugar,
	RutaCandidata,
	abertura_cruzada,
	elegir_comparables,
	lugares_de_espacios,
	punto_interior_de_abertura,
	relaciones_cardinales,
	rutas_candidatas,
	salidas_ordenadas,
)
from app.core.i18n import _
from app.dominio import geometria as geo
from app.dominio.modelo import Abertura, Conector, Posicion
from app.motor import eventos as ev
from app.motor.eventos import Evento

log = logging.getLogger(__name__)

MAX_LUGARES = 14
MARGEN_DISTANCIAS = 0.2


class Examen(Actividad):
	"""Lo común de los exámenes: serie de pruebas, tiempo por prueba, confirmación, regla de parada y registro."""

	ESTRELLAS = ()
	MEDIDA = "examen"

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._pruebas: list[dict[str, Any]] = []
		self._hechas: list[dict[str, Any]] = []
		self._n = -1
		self._t_prueba = 0.0
		self._d_prueba = 0.0
		self._c_prueba = 0
		self._en_prueba = False
		self._con_ayuda = False
		self._parada = False
		self._instruccion = ""
		# La pregunta sola, sin «cambia de opción con…»: es lo que lee el menú de respuestas del reproductor.
		self._enunciado = ""
		self._opciones: list[str] = []
		self._elegida = -1
		self._baliza_examen = False

	# ── Lo que redefine cada examen ──

	def _generar(self, sesion: Any) -> list[dict[str, Any]]:
		"""Pruebas del examen: las definidas por el profesional o, si no hay, las generadas con la semilla."""
		return []

	def _empezar_prueba(self, sesion: Any, prueba: dict[str, Any]) -> str:
		"""Prepara una prueba (coloca al alumno) y devuelve la instrucción que se le dice."""
		return ""

	def _confirmar(self, sesion: Any, prueba: dict[str, Any]) -> None:
		"""El alumno confirma: se anota la prueba."""

	def _resumen(self) -> dict[str, Any]:
		"""Cifras propias del examen para el resultado."""
		return {}

	# ── Ciclo de pruebas ──

	def _preparar(self, sesion: Any) -> None:
		self._pruebas = self._generar(sesion)
		self.total = len(self._pruebas)
		self.fase = "examen"

	def _texto_inicio(self) -> str:
		return self.tx("examen_inicio")

	def texto_objetivo(self) -> str:
		return self._instruccion

	def _prueba(self) -> dict[str, Any] | None:
		return self._pruebas[self._n] if 0 <= self._n < len(self._pruebas) and self._en_prueba else None

	def _colocar(self, sesion: Any, lugar: Lugar, rumbo: float | None = None) -> None:
		"""Lleva al alumno al punto de partida de una prueba, mirando a un rumbo sorteado (no se le da el rumbo como pista)."""
		if rumbo is None:
			rumbo = float(self.azar.choice((0, 90, 180, 270)))
		sesion.recolocar(Posicion(lugar.planta, lugar.x, lugar.y, rumbo))

	def _siguiente(self, sesion: Any) -> None:
		self._n += 1
		if self._n >= len(self._pruebas):
			self._en_prueba = False
			self._terminar(sesion, True, "completada")
			return
		prueba = self._pruebas[self._n]
		# Mientras se coloca al alumno la prueba aún no cuenta: recolocarle no debe tomarse por un movimiento suyo.
		self._en_prueba = False
		self._con_ayuda = False
		self._opciones = []
		self._enunciado = ""
		self._elegida = -1
		texto = self._empezar_prueba(sesion, prueba)
		self._en_prueba = True
		self._marcar_inicio(sesion)
		self._decir_instruccion(sesion, texto, con_numero=True)

	def _marcar_inicio(self, sesion: Any) -> None:
		"""Empieza a contar el tiempo, el camino y los choques de la prueba."""
		self._t_prueba = sesion.t
		self._d_prueba = sesion.movimiento.distancia
		self._c_prueba = sesion.movimiento.choques

	def _decir_instruccion(self, sesion: Any, texto: str, con_numero: bool = False) -> None:
		self._instruccion = texto
		partes: list[str] = []
		if con_numero:
			partes.append(self.tx("examen_prueba", n=self._n + 1, total=self.total))
		partes.append(texto)
		limite = self._limite()
		if limite and con_numero and self._n == 0:
			partes.append(self.tx("examen_tiempo_limite", tiempo=self.tx.duracion(limite)))
		self._decir(sesion, " ".join(p for p in partes if p), clave="examen", caduca=60.0)

	def _limite(self) -> float:
		return float(self.datos.get("tiempo_por_prueba_s") or 0.0)

	def tiempo_restante(self) -> float | None:
		limite = self._limite()
		if not limite or not self._en_prueba:
			return None
		return max(0.0, round(limite - (self._t - self._t_prueba), 1))

	def _tic(self, sesion: Any, dt: float) -> None:
		if self._n < 0:
			if not self._pruebas:
				self._terminar(sesion, False, "sin_pruebas")
				return
			self._siguiente(sesion)
			return
		limite = self._limite()
		if self._en_prueba and limite and sesion.t - self._t_prueba >= limite:
			self._tiempo_agotado(sesion)

	def _tiempo_agotado(self, sesion: Any) -> None:
		self._cerrar_prueba(sesion, False, "tiempo")

	def _cerrar_prueba(self, sesion: Any, acierto: bool, motivo: str, **datos: Any) -> None:
		"""Anota la prueba en curso, sin decir si se ha acertado, y pasa a la siguiente o para el examen."""
		if not self._en_prueba:
			return
		self._en_prueba = False
		self._apagar_baliza_examen(sesion)
		registro: dict[str, Any] = {
			"n": self._n + 1,
			"acierto": bool(acierto),
			"motivo": motivo,
			"tiempo_s": round(sesion.t - self._t_prueba, 1),
			"camino_m": round(sesion.movimiento.distancia - self._d_prueba, 2),
			"choques": sesion.movimiento.choques - self._c_prueba,
			"con_ayuda_profesional": self._con_ayuda,
		}
		registro.update(datos)
		self._hechas.append(registro)
		self.hechos = len(self._hechas)
		self._puntuar(registro)
		sesion.registrar(
			"examen", actividad=self.id, medida=self.MEDIDA, **{k: v for k, v in registro.items() if not isinstance(v, (list, dict))}
		)
		sesion.sonar("interfaz/elegir", bus="interfaz")
		self._decir(sesion, self.tx("examen_tiempo" if motivo == "tiempo" else "examen_anotado"), clave="anotado")
		if puntuacion.debe_parar([bool(r["acierto"]) for r in self._hechas], self.datos.get("regla_parada")):
			self._parada = True
			self._decir(sesion, self.tx("examen_parada"), clave="parada")
			self._terminar(sesion, True, "regla_parada")
			return
		self._siguiente(sesion)

	def _puntuar(self, registro: dict[str, Any]) -> None:
		"""Suma al marcador; por defecto un punto por acierto."""
		self.puntos += 1 if registro["acierto"] else 0
		self.puntos_maximos += 1

	# ── Confirmar y responder ──

	def _al_interactuar(self, sesion: Any, elemento: Any) -> list[Evento]:
		# Abrir una puerta o llamar al ascensor no es confirmar: hacen falta para moverse.
		if isinstance(elemento, (Abertura, Conector)):
			return []
		return self.confirmar(sesion)

	def confirmar(self, sesion: Any) -> list[Evento]:
		"""El alumno confirma («ya he llegado», «es hacia ahí», «esta respuesta»). No se le dice si acierta."""
		prueba = self._prueba()
		if prueba is None or self._cerrada:
			return []
		self._confirmar(sesion, prueba)
		return [ev.EvSonido("interfaz/mover", bus="interfaz")]

	def pregunta(self) -> dict[str, Any] | None:
		if not self._opciones or not self._en_prueba:
			return None
		return {"texto": self._enunciado or self._instruccion, "opciones": list(self._opciones), "elegida": self._elegida}

	def _texto_opcion(self) -> str:
		return self.tx("examen_opcion", n=self._elegida + 1, total=len(self._opciones), texto=self._opciones[self._elegida])

	def _al_pedir_objetivo(self, sesion: Any) -> str:
		"""En un examen de preguntas, la orden de objetivo pasa a la opción siguiente; en los demás repite la instrucción."""
		if not self._opciones or not self._en_prueba:
			return self._instruccion
		self._elegida = (self._elegida + 1) % len(self._opciones)
		texto = self._texto_opcion()
		if self._elegida == 0:
			texto = f"{self._instruccion} {texto}"
		return texto

	def responder(self, sesion: Any, opcion: int) -> list[Evento]:
		"""Elige una opción por su número (0 es la primera). Queda elegida; falta confirmar."""
		if not self._opciones or not self._en_prueba or not 0 <= int(opcion) < len(self._opciones):
			return []
		self._elegida = int(opcion)
		return [ev.EvVoz(self._texto_opcion(), True, "ayuda")]

	# ── Baliza de la fase de aprendizaje (no puntúa) ──

	def _encender_baliza_examen(self, sesion: Any, lugar: Lugar) -> None:
		sesion.permitir_ayuda("baliza", True, None)
		if sesion.baliza(lugar.terna, por_ruta=True):
			self._ayudas_no_contadas += 1
		self._baliza_examen = True

	def _apagar_baliza_examen(self, sesion: Any) -> None:
		if not self._baliza_examen:
			return
		self._baliza_examen = False
		sesion.baliza(None)
		sesion.permitir_ayuda("baliza", False, None)

	def _pista_dada_por_profesional(self, sesion: Any) -> None:
		self._con_ayuda = True

	def _al_cerrar(self, sesion: Any) -> None:
		# Si el examen se deja a medias en una fase de aprendizaje, la baliza no se queda encendida ni permitida.
		self._apagar_baliza_examen(sesion)

	# ── Resultado ──

	def _puntuaciones(self, sesion: Any) -> dict[str, Any] | None:
		datos: dict[str, Any] = {"medida": self.MEDIDA}
		datos.update(puntuacion.resumen_examen(self._hechas))
		datos.update(
			{
				"pruebas_total": self.total,
				"puntos": self.puntos,
				"puntos_maximos": self.puntos_maximos,
				"parada": self._parada,
				"con_ayuda_profesional": sum(1 for r in self._hechas if r.get("con_ayuda_profesional")),
				"semilla": self.semilla,
			}
		)
		datos.update(self._resumen())
		datos["pruebas"] = list(self._hechas)
		return datos

	def _detalle(self, sesion: Any) -> dict[str, Any]:
		return {"regla_parada": self.datos.get("regla_parada"), "parada": self._parada}

	def _lugares(self, sesion: Any) -> list[Lugar]:
		"""Lugares entre los que se generan pruebas: un punto por espacio alcanzable, como mucho catorce (sorteados con la semilla)."""
		lugares = lugares_de_espacios(sesion.mundo, sesion.nav, sesion.inicio)
		if len(lugares) > MAX_LUGARES:
			elegidos = set(self.azar.sample(range(len(lugares)), MAX_LUGARES))
			lugares = [lugar for indice, lugar in enumerate(lugares) if indice in elegidos]
		return lugares


class ExamenRutas(Examen):
	"""Rutas no entrenadas, de longitud y giros comparables, con límite de tiempo.

	Variantes: ``normal`` (de un punto a otro), ``inversa`` (se enseña la ida
	con baliza y se mide la vuelta) y ``atajo`` (se enseñan dos tramos, A a B
	y B a C, y se mide ir de C a A por un camino no practicado).
	"""

	MEDIDA = "rutas"

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._guia: list[Lugar] = []
		# En las variantes con fase de aprendizaje, el lugar desde el que empieza lo que se mide.
		self._desde = ""
		self._objetivo: Lugar | None = None
		self._optimo: float | None = None

	def _variante(self) -> str:
		variante = str(self.datos.get("variante") or "normal")
		return variante if variante in ("normal", "inversa", "atajo") else "normal"

	def _generar(self, sesion: Any) -> list[dict[str, Any]]:
		pruebas: list[dict[str, Any]] = []
		for dato in self.datos["pruebas"]:
			origen, destino = self.lugar(dato.get("origen")), self.lugar(dato.get("destino"))
			if origen is None or destino is None:
				continue
			pruebas.append({"origen": origen, "destino": destino, "via": self.lugar(dato.get("via"))})
		if pruebas:
			return pruebas
		lugares = self._lugares(sesion)
		candidatas = rutas_candidatas(sesion.nav, lugares)
		entrenadas = {
			frozenset(str(x) for x in par) for par in self.datos.get("entrenadas") or [] if isinstance(par, (list, tuple)) and len(par) == 2
		}
		candidatas = [c for c in candidatas if frozenset((c.origen.elemento_id, c.destino.elemento_id)) not in entrenadas]
		elegidas: list[RutaCandidata] = elegir_comparables(candidatas, int(self.datos.get("numero_pruebas") or 5), self.azar)
		for candidata in elegidas:
			via = None
			if self._variante() == "atajo":
				otros = [
					lugar for lugar in lugares if lugar.elemento_id not in (candidata.origen.elemento_id, candidata.destino.elemento_id)
				]
				via = self.azar.choice(otros) if otros else None
			pruebas.append(
				{
					"origen": candidata.origen,
					"destino": candidata.destino,
					"via": via,
					"longitud": round(candidata.longitud, 1),
					"giros": candidata.giros,
				}
			)
		return pruebas

	def _empezar_prueba(self, sesion: Any, prueba: dict[str, Any]) -> str:
		origen: Lugar = prueba["origen"]
		destino: Lugar = prueba["destino"]
		variante = self._variante()
		self._desde = ""
		self._colocar(sesion, origen)
		aqui = self.tx("examen_estas_en", lugar=origen.nombre)
		if variante == "normal":
			self.fase = "ruta"
			self._objetivo = destino
			self._optimo = sesion.nav.distancia(origen.terna, destino.terna)
			return f"{aqui} {self.tx('examen_ruta', destino=destino.nombre)}"
		# Fase de aprendizaje: se sigue la baliza. No puntúa; lo que se mide viene después.
		self.fase = "ida"
		self._guia = [destino]
		if variante == "atajo" and prueba.get("via") is not None:
			self._guia.append(prueba["via"])
		self._objetivo = origen
		self._encender_baliza_examen(sesion, self._guia[0])
		return f"{aqui} {self.tx('examen_ida', destino=self._guia[0].nombre)}"

	def _tras_mover(self, sesion: Any) -> None:
		if self.fase != "ida" or not self._en_prueba or not self._guia:
			return
		if not self._guia[0].alcanzado(sesion):
			return
		self._desde = self._guia.pop(0).nombre
		sesion.sonar("baliza/llegada", bus="ayudas")
		if self._guia:
			self._encender_baliza_examen(sesion, self._guia[0])
			self._decir_instruccion(sesion, self.tx("examen_ida_2", destino=self._guia[0].nombre))
			return
		# Empieza lo que se mide: sin baliza, y el reloj de la prueba arranca aquí.
		self._apagar_baliza_examen(sesion)
		self.fase = "ruta"
		objetivo = self._objetivo
		jugador = sesion.jugador
		self._optimo = sesion.nav.distancia((jugador.planta, jugador.x, jugador.y), objetivo.terna) if objetivo is not None else None
		self._marcar_inicio(sesion)
		clave = "examen_atajo" if self._variante() == "atajo" else "examen_vuelve"
		self._decir_instruccion(sesion, self.tx(clave, destino=objetivo.nombre if objetivo is not None else ""))

	def _tiempo_agotado(self, sesion: Any) -> None:
		prueba = self._prueba() or {}
		self._cerrar_prueba(sesion, False, "tiempo_aprendizaje" if self.fase == "ida" else "tiempo", **self._datos_ruta(sesion, prueba))

	def _datos_ruta(self, sesion: Any, prueba: dict[str, Any]) -> dict[str, Any]:
		objetivo = self._objetivo
		real = sesion.movimiento.distancia - self._d_prueba
		recta = sesion.distancia_a(objetivo.terna) if objetivo is not None else math.inf
		return {
			"origen": self._desde or (prueba["origen"].nombre if prueba.get("origen") is not None else ""),
			"destino": objetivo.nombre if objetivo is not None else "",
			"variante": self._variante(),
			"optimo_m": round(self._optimo, 2) if self._optimo is not None else None,
			"cociente": puntuacion.cociente_camino(real, self._optimo) if self.fase == "ruta" else None,
			"distancia_al_destino_m": round(recta, 1) if math.isfinite(recta) else None,
		}

	def _confirmar(self, sesion: Any, prueba: dict[str, Any]) -> None:
		if self.fase != "ruta" or self._objetivo is None:
			# En la fase de aprendizaje no hay nada que confirmar: la llegada se detecta sola.
			return
		acierto = self._objetivo.alcanzado(sesion)
		self._cerrar_prueba(sesion, acierto, "confirmada", **self._datos_ruta(sesion, prueba))

	def _resumen(self) -> dict[str, Any]:
		cocientes = [float(r["cociente"]) for r in self._hechas if r.get("acierto") and isinstance(r.get("cociente"), (int, float))]
		media = puntuacion.media(cocientes)
		return {"variante": self._variante(), "cociente_medio_aciertos": round(media, 2) if media is not None else None}

	def _texto_resultado_examen(self, resultado: dict[str, Any]) -> str:
		examen = resultado.get("examen") or {}
		return _("Rutas conseguidas: {aciertos} de {total}.").format(
			aciertos=examen.get("aciertos", 0), total=examen.get("pruebas_hechas", 0)
		)


class ExamenSalida(Examen):
	"""Salida más corta: desde cada punto de partida, salir por la salida más cercana. Puntúa 3, 2, 1 o 0."""

	MEDIDA = "salida_mas_corta"

	def __init__(self, *argumentos: Any, **opciones: Any) -> None:
		super().__init__(*argumentos, **opciones)
		self._salidas: list[tuple[str, float]] = []

	def _tolerancia(self) -> float:
		return float(self.datos.get("tolerancia_m") or 0.0)

	def _generar(self, sesion: Any) -> list[dict[str, Any]]:
		pruebas: list[dict[str, Any]] = []
		for dato in self.datos["pruebas"]:
			origen = self.lugar(dato.get("origen") if dato.get("origen") is not None else dato.get("destino"))
			if origen is not None:
				pruebas.append({"origen": origen})
		if pruebas:
			return pruebas
		claros: list[Lugar] = []
		dudosos: list[Lugar] = []
		for lugar in self._lugares(sesion):
			salidas = salidas_ordenadas(sesion.nav, lugar.terna)
			if not salidas:
				continue
			# Se prefieren los puntos donde elegir importa: la mejor salida queda claramente más cerca que la segunda.
			if len(salidas) >= 2 and salidas[1][1] - salidas[0][1] > self._tolerancia() + 1.0:
				claros.append(lugar)
			else:
				dudosos.append(lugar)
		numero = int(self.datos.get("numero_pruebas") or 5)
		self.azar.shuffle(claros)
		self.azar.shuffle(dudosos)
		return [{"origen": lugar} for lugar in (claros + dudosos)[:numero]]

	def _empezar_prueba(self, sesion: Any, prueba: dict[str, Any]) -> str:
		origen: Lugar = prueba["origen"]
		self._colocar(sesion, origen)
		self._salidas = salidas_ordenadas(sesion.nav, origen.terna)
		self.fase = "salir"
		return f"{self.tx('examen_estas_en', lugar=origen.nombre)} {self.tx('examen_salida')}"

	def _datos_salida(self, sesion: Any, prueba: dict[str, Any], elegida: str, nombre: str, puntos: int) -> dict[str, Any]:
		optimo = self._salidas[0][1] if self._salidas else None
		real = sesion.movimiento.distancia - self._d_prueba
		return {
			"origen": prueba["origen"].nombre,
			"salida": elegida,
			"salida_nombre": nombre,
			"salida_mas_cercana": self._salidas[0][0] if self._salidas else "",
			"puntos": puntos,
			"optimo_m": round(optimo, 2) if optimo is not None else None,
			"cociente": puntuacion.cociente_camino(real, optimo) if elegida else None,
		}

	def _tras_mover(self, sesion: Any) -> None:
		prueba = self._prueba()
		if prueba is None:
			return
		info = abertura_cruzada(sesion)
		if info is None:
			return
		if not info.abertura.es_salida:
			# Ha cruzado algo que no es una salida del edificio: vuelve adentro sin comentario.
			dentro = punto_interior_de_abertura(sesion.mundo, info)
			if dentro is not None:
				sesion.recolocar(Posicion(info.planta_id, dentro[0][0], dentro[0][1], dentro[1]))
			return
		puntos = puntuacion.puntos_salida(info.abertura.id, self._salidas, self._tolerancia())
		acierto = puntos >= int(self.datos.get("acierto_minimo") or 2)
		self._cerrar_prueba(sesion, acierto, "salida", **self._datos_salida(sesion, prueba, info.abertura.id, info.abertura.nombre, puntos))

	def _tiempo_agotado(self, sesion: Any) -> None:
		prueba = self._prueba() or {}
		self._cerrar_prueba(sesion, False, "tiempo", **self._datos_salida(sesion, prueba, "", "", 0))

	def _confirmar(self, sesion: Any, prueba: dict[str, Any]) -> None:
		"""En este examen no se confirma: salir es la respuesta."""

	def _puntuar(self, registro: dict[str, Any]) -> None:
		self.puntos += int(registro.get("puntos") or 0)
		self.puntos_maximos += puntuacion.PUNTOS_SALIDA_MAXIMO

	def _resumen(self) -> dict[str, Any]:
		media = puntuacion.media([float(r.get("puntos") or 0) for r in self._hechas])
		return {
			"media_puntos": round(media, 2) if media is not None else None,
			"salidas_optimas": sum(1 for r in self._hechas if r.get("puntos") == 3),
		}

	def _texto_resultado_examen(self, resultado: dict[str, Any]) -> str:
		examen = resultado.get("examen") or {}
		return _("Puntos de salida: {puntos} de {maximo}.").format(puntos=examen.get("puntos", 0), maximo=examen.get("puntos_maximos", 0))


class ExamenSenalar(Examen):
	"""Señalar: girarse hacia un lugar que no se percibe y confirmar. Se mide el error en grados."""

	MEDIDA = "senalar"

	def _retocar_ajustes(self, ajustes: Any) -> None:
		# Con giros de 90 grados no se puede señalar con precisión: en este examen cada pulsación gira menos.
		fino = float(self.datos.get("giro_grados") or 15)
		if ajustes.giro_grados > fino:
			ajustes.giro_grados = fino

	def _generar(self, sesion: Any) -> list[dict[str, Any]]:
		pruebas: list[dict[str, Any]] = []
		for dato in self.datos["pruebas"]:
			origen, destino = self.lugar(dato.get("origen")), self.lugar(dato.get("destino"))
			if origen is not None and destino is not None and origen.planta == destino.planta:
				pruebas.append({"origen": origen, "destino": destino})
		if pruebas:
			return pruebas
		lugares = self._lugares(sesion)
		pares: list[tuple[Lugar, Lugar]] = []
		for origen in lugares:
			for destino in lugares:
				if origen is destino or origen.planta != destino.planta or geo.distancia(origen.punto, destino.punto) < 3.0:
					continue
				if sesion.mundo.visible(origen.planta, origen.punto, destino.punto, "vista"):
					continue
				pares.append((origen, destino))
		numero = min(len(pares), int(self.datos.get("numero_pruebas") or 5))
		elegidos = self.azar.sample(pares, numero) if numero else []
		return [{"origen": origen, "destino": destino} for origen, destino in elegidos]

	def _empezar_prueba(self, sesion: Any, prueba: dict[str, Any]) -> str:
		paso = max(5, int(self.datos.get("giro_grados") or 15))
		self._colocar(sesion, prueba["origen"], float(self.azar.randrange(0, 360, paso)))
		self.fase = "senalar"
		return f"{self.tx('examen_estas_en', lugar=prueba['origen'].nombre)} {self.tx('examen_senalar', destino=prueba['destino'].nombre)}"

	def _confirmar(self, sesion: Any, prueba: dict[str, Any]) -> None:
		jugador = sesion.jugador
		destino: Lugar = prueba["destino"]
		origen: Lugar = prueba["origen"]
		if jugador.planta != destino.planta or geo.distancia(jugador.punto, destino.punto) < 0.05:
			self._cerrar_prueba(sesion, False, "fuera_de_sitio", origen=origen.nombre, destino=destino.nombre, error_grados=None)
			return
		real = geo.rumbo_entre(jugador.punto, destino.punto)
		error = puntuacion.error_angular(jugador.rumbo, real)
		self._cerrar_prueba(
			sesion,
			error <= float(self.datos.get("tolerancia_grados") or 30),
			"confirmada",
			origen=origen.nombre,
			destino=destino.nombre,
			error_grados=round(error, 1),
			rumbo_alumno=round(jugador.rumbo % 360.0, 1),
			rumbo_real=round(real % 360.0, 1),
			desplazado_m=round(geo.distancia(jugador.punto, origen.punto), 1),
		)

	def _resumen(self) -> dict[str, Any]:
		errores = [float(r["error_grados"]) for r in self._hechas if isinstance(r.get("error_grados"), (int, float))]
		media, mediana = puntuacion.media(errores), puntuacion.mediana(errores)
		return {
			"error_medio_grados": round(media, 1) if media is not None else None,
			"error_mediano_grados": round(mediana, 1) if mediana is not None else None,
			"tolerancia_grados": float(self.datos.get("tolerancia_grados") or 30),
		}

	def _texto_resultado_examen(self, resultado: dict[str, Any]) -> str:
		error = (resultado.get("examen") or {}).get("error_medio_grados")
		if error is None:
			return ""
		return _("Error medio al señalar: {n} grados.").format(n=round(error))


class ExamenDistancias(Examen):
	"""Comparar distancias: ¿qué queda más cerca, A o B? Andando o en línea recta, según se configure."""

	MEDIDA = "distancias"

	def _criterio(self) -> str:
		return "recta" if self.datos.get("criterio") == "recta" else "camino"

	def _distancia(self, sesion: Any, origen: Lugar, destino: Lugar) -> float | None:
		if self._criterio() == "recta":
			return geo.distancia(origen.punto, destino.punto) if origen.planta == destino.planta else None
		return sesion.nav.distancia(origen.terna, destino.terna)

	def _prueba_de(self, sesion: Any, origen: Lugar, a: Lugar, b: Lugar, exigir_margen: bool) -> dict[str, Any] | None:
		d_a, d_b = self._distancia(sesion, origen, a), self._distancia(sesion, origen, b)
		if d_a is None or d_b is None or max(d_a, d_b) < 1e-6:
			return None
		if exigir_margen and (min(d_a, d_b) < 2.0 or abs(d_a - d_b) / max(d_a, d_b) < MARGEN_DISTANCIAS):
			return None
		return {"origen": origen, "a": a, "b": b, "d_a": round(d_a, 1), "d_b": round(d_b, 1), "correcta": 0 if d_a <= d_b else 1}

	def _generar(self, sesion: Any) -> list[dict[str, Any]]:
		pruebas: list[dict[str, Any]] = []
		for dato in self.datos["pruebas"]:
			origen, a, b = self.lugar(dato.get("origen")), self.lugar(dato.get("a")), self.lugar(dato.get("b"))
			if origen is None or a is None or b is None:
				continue
			prueba = self._prueba_de(sesion, origen, a, b, exigir_margen=False)
			if prueba is not None:
				pruebas.append(prueba)
		if pruebas:
			return pruebas
		lugares = self._lugares(sesion)
		numero = int(self.datos.get("numero_pruebas") or 5)
		if len(lugares) < 3:
			return []
		vistas: set[tuple[str, frozenset[str]]] = set()
		for _intento in range(numero * 40):
			if len(pruebas) >= numero:
				break
			origen, a, b = self.azar.sample(lugares, 3)
			clave = (origen.elemento_id, frozenset((a.elemento_id, b.elemento_id)))
			if clave in vistas:
				continue
			vistas.add(clave)
			prueba = self._prueba_de(sesion, origen, a, b, exigir_margen=True)
			if prueba is not None:
				pruebas.append(prueba)
		return pruebas

	def _empezar_prueba(self, sesion: Any, prueba: dict[str, Any]) -> str:
		self._colocar(sesion, prueba["origen"])
		self._opciones = [prueba["a"].nombre, prueba["b"].nombre]
		self.fase = "pregunta"
		pregunta = self.tx(f"examen_distancias_{self._criterio()}", a=prueba["a"].nombre, b=prueba["b"].nombre)
		self._enunciado = f"{self.tx('examen_estas_en', lugar=prueba['origen'].nombre)} {pregunta}"
		return f"{self._enunciado} {self.tx('examen_elige')}"

	def _confirmar(self, sesion: Any, prueba: dict[str, Any]) -> None:
		if self._elegida < 0:
			# Sin opción elegida no hay respuesta que anotar: se repite la pregunta.
			self._decir(sesion, self._instruccion, clave="examen")
			return
		self._cerrar_prueba(
			sesion,
			self._elegida == prueba["correcta"],
			"respondida",
			origen=prueba["origen"].nombre,
			a=prueba["a"].nombre,
			b=prueba["b"].nombre,
			d_a=prueba["d_a"],
			d_b=prueba["d_b"],
			respuesta=self._opciones[self._elegida],
			correcta=self._opciones[prueba["correcta"]],
			criterio=self._criterio(),
		)

	def _resumen(self) -> dict[str, Any]:
		return {"criterio": self._criterio()}


class ExamenReconstruccion(Examen):
	"""Reconstrucción: colocar las habitaciones en su posición relativa con preguntas como «¿qué hay al norte del salón?».

	Solo se pregunta por relaciones claras (espacios contiguos y bien
	alineados con un punto cardinal) y las opciones falsas son espacios que
	no están en esa dirección, de modo que cada pregunta tiene una única
	respuesta correcta.
	"""

	MEDIDA = "reconstruccion"

	def _generar(self, sesion: Any) -> list[dict[str, Any]]:
		pruebas: list[dict[str, Any]] = []
		for dato in self.datos["pruebas"]:
			referencia = self.entorno.elemento(str(dato.get("referencia") or ""))
			correcta = self.entorno.elemento(str(dato.get("correcta") or ""))
			lado = str(dato.get("direccion") or dato.get("lado") or "")
			if referencia is None or correcta is None or lado not in ("norte", "este", "sur", "oeste"):
				continue
			nombres = [str(getattr(self.entorno.elemento(ident), "nombre", "") or "") for ident in dato.get("opciones") or []]
			opciones = [nombre for nombre in nombres if nombre and nombre != correcta.nombre]
			opciones.append(correcta.nombre)
			self.azar.shuffle(opciones)
			pruebas.append({"referencia": referencia.nombre, "lado": lado, "correcta": correcta.nombre, "opciones": opciones})
		if pruebas:
			return pruebas
		alcanzables = sesion.nav.espacios_alcanzables(sesion.inicio)
		ternas = [t for t in relaciones_cardinales(self.entorno) if not alcanzables or (t[0].id in alcanzables and t[2].id in alcanzables)]
		en_direccion: dict[tuple[str, str], set[str]] = {}
		for referencia, lado, otro in ternas:
			en_direccion.setdefault((referencia.id, lado), set()).add(otro.id)
		self.azar.shuffle(ternas)
		numero = int(self.datos.get("numero_pruebas") or 5)
		usadas: set[tuple[str, str]] = set()
		for referencia, lado, otro in ternas:
			if len(pruebas) >= numero:
				break
			if (referencia.id, lado) in usadas:
				continue
			planta = self.entorno.planta_de(referencia)
			falsos = [
				e.nombre
				for e in (planta.espacios if planta is not None else [])
				if e.nombre
				and not e.macizo
				and e.id != referencia.id
				and e.id not in en_direccion[(referencia.id, lado)]
				and e.nombre != otro.nombre
			]
			falsos = sorted(set(falsos))
			if not falsos:
				continue
			usadas.add((referencia.id, lado))
			opciones = self.azar.sample(falsos, min(3, len(falsos))) + [otro.nombre]
			self.azar.shuffle(opciones)
			pruebas.append({"referencia": referencia.nombre, "lado": lado, "correcta": otro.nombre, "opciones": opciones})
		return pruebas

	def _empezar_prueba(self, sesion: Any, prueba: dict[str, Any]) -> str:
		self._opciones = list(prueba["opciones"])
		self.fase = "pregunta"
		self._enunciado = self.tx("examen_reconstruccion", lado=self.tx.lado(prueba["lado"]), referencia=prueba["referencia"])
		return f"{self._enunciado} {self.tx('examen_elige')}"

	def _confirmar(self, sesion: Any, prueba: dict[str, Any]) -> None:
		if self._elegida < 0:
			self._decir(sesion, self._instruccion, clave="examen")
			return
		respuesta = self._opciones[self._elegida]
		self._cerrar_prueba(
			sesion,
			respuesta == prueba["correcta"],
			"respondida",
			referencia=prueba["referencia"],
			lado=prueba["lado"],
			respuesta=respuesta,
			correcta=prueba["correcta"],
		)

	def _resumen(self) -> dict[str, Any]:
		return {"relaciones_acertadas": [f"{r['correcta']} / {r['lado']} / {r['referencia']}" for r in self._hechas if r.get("acierto")]}
