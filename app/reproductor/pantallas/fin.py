"""Fin de actividad: el resultado hablado, la celebración según el estilo, los premios y unas preguntas opcionales.

El resultado se dice entero y en orden fijo (si se ha completado, estrellas,
lo encontrado, tiempo, distancia, choques, ayudas y premios nuevos) para que
el alumno aprenda dónde está cada dato; «Oír otra vez el resultado» lo
repite. La celebración cambia con el estilo: fanfarria y sonido por estrella
en el infantil, un logro breve en el juvenil y un único sonido discreto en el
adulto. Nunca se penalizan las pausas ni los choques: se informan.

La grabación de la sesión sigue abierta mientras esta pantalla está delante,
para poder apuntar en ella las recompensas y las respuestas del cuestionario;
se cierra al salir (repetir, elegir otra o volver al menú).
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from app.core.i18n import _, _n
from app.reproductor import puente_actividades, textos
from app.reproductor.menus import Menu, Opcion

if TYPE_CHECKING:
	from app.reproductor.aplicacion import Aplicacion

log = logging.getLogger(__name__)


def _entero(valor: Any) -> int:
	try:
		return int(valor)
	except TypeError, ValueError:
		return 0


def texto_resultado(app: Aplicacion, partida: Any, recompensas: list[dict[str, Any]], mejora: bool) -> str:
	"""El resultado de la actividad, dicho de corrido y en el tono del estilo."""
	resultado = partida.resultado
	estilo = app.estilo
	frases = [textos.frase("completada" if partida.completada else "no_completada", estilo)]
	mensaje = str(resultado.get("mensaje") or "").strip()
	if mensaje:
		frases.append(mensaje)
	if "estrellas" in resultado:
		frases.append(textos.decir_estrellas(_entero(resultado.get("estrellas")), estilo))
	total = _entero(resultado.get("total", resultado.get("objetivos_total")))
	if total > 0:
		hechos = _entero(resultado.get("hechos", resultado.get("objetivos_hechos")))
		frases.append(_("Has conseguido {hechos} de {total}.").format(hechos=hechos, total=total))
	puntos = _entero(resultado.get("puntos"))
	# Una actividad que no puntúa (máximo cero) no dice «0 puntos».
	if "puntos" in resultado and (puntos or _entero(resultado.get("puntos_maximos", 1))):
		frases.append(_n("{n} punto.", "{n} puntos.", puntos).format(n=puntos))
	frases.append(
		_("Tiempo: {tiempo}. Distancia: {metros} metros.").format(
			tiempo=textos.duracion(float(resultado.get("tiempo_activo") or 0.0)), metros=round(float(resultado.get("distancia_m") or 0.0))
		)
	)
	choques = _entero(resultado.get("choques"))
	ayudas = resultado.get("ayudas")
	usadas = sum(_entero(v) for v in ayudas.values()) if isinstance(ayudas, dict) else _entero(ayudas)
	frases.append(
		_("{choques} y {ayudas}.").format(
			choques=_n("{n} choque", "{n} choques", choques).format(n=choques),
			ayudas=_n("{n} ayuda pedida", "{n} ayudas pedidas", usadas).format(n=usadas),
		)
	)
	nombres = [str(r.get("nombre") or r.get("texto") or "") for r in recompensas]
	nombres = [nombre for nombre in nombres if nombre]
	if nombres:
		frases.append(_n("Premio nuevo: {lista}.", "Premios nuevos: {lista}.", len(nombres)).format(lista=", ".join(nombres)))
	if mejora:
		frases.append(textos.frase("mejor_marca", estilo))
	aviso = str(resultado.get("aviso") or "").strip()
	if aviso and partida.modo == "examen":
		# Lo que la actividad quiere dejar claro tras un examen (que no es un diagnóstico).
		frases.append(aviso)
	return " ".join(frases)


def celebrar(app: Aplicacion, partida: Any, recompensas: list[dict[str, Any]]) -> None:
	"""Los sonidos y la vibración del final, según el estilo y lo conseguido."""
	estilo = app.estilo
	estrellas = max(0, min(3, _entero(partida.resultado.get("estrellas"))))
	if not partida.completada:
		app.sonar("interfaz/cerrar")
		return
	app.haptica.patron("objetivo")
	if estilo == "adulto":
		app.sonar(f"logro/estrella_{estrellas}" if estrellas else "logro/logro", volumen=0.8)
		return
	app.sonar("logro/logro")
	if estrellas:
		app.sonar(f"logro/estrella_{estrellas}")
	if estilo == "infantil":
		app.sonar("premio/tesoro", volumen=0.8)
	if any(str(r.get("tipo")) == "medalla" for r in recompensas):
		app.sonar("logro/medalla")


def abrir_fin(app: Aplicacion, partida: Any) -> Menu:
	"""Calcula y guarda las recompensas, celebra y abre el menú de fin de actividad."""
	from app.reproductor.pantallas import elegir

	resultado = partida.resultado
	recompensas = puente_actividades.recompensas(resultado, app.estilo) if partida.completada else []
	clave = f"{partida.entorno.id}/{partida.id_actividad}"
	mejora = False
	if app.perfil is not None:
		recompensas = app.perfil.anadir_premios(recompensas, partida.entorno.nombre, partida.nombre_actividad) if recompensas else []
		mejora = app.perfil.apuntar_actividad(clave, _entero(resultado.get("estrellas")), partida.completada) and partida.completada
	# Las recompensas que trae el resultado ya las registró la actividad (registro «recompensa»): no se duplican.
	ya_registradas = isinstance(resultado.get("recompensas"), (list, tuple))
	for recompensa in [] if ya_registradas else recompensas:
		datos = {"tipo": recompensa.get("tipo", "objeto"), "nombre": recompensa.get("nombre", "")}
		if partida.grabadora is not None:
			partida.grabadora.evento("recompensa", datos)
		if app.enlace is not None:
			app.enlace.evento("recompensa", datos)
	texto = texto_resultado(app, partida, recompensas, mejora)
	estado = {"preguntado": False}

	def repetir_resultado() -> None:
		app.decir(texto, True)

	def preguntar() -> None:
		estado["preguntado"] = True
		abrir_cuestionario(app, partida, al_terminar=menu.refrescar)

	def repetir_actividad() -> None:
		app.empezar_partida(partida.paquete, partida.datos)

	def otra() -> None:
		paquete = partida.paquete
		app.volver_al_menu()
		elegir.abrir_actividades(app, paquete)

	def lista() -> list[Opcion]:
		opciones = [
			Opcion(
				_("Oír otra vez el resultado"),
				repetir_resultado,
				ayuda=_("Repite las estrellas, el tiempo, los choques y los premios."),
				callado=True,
			)
		]
		if not estado["preguntado"] and partida.grabadora is not None and puente_actividades.preguntas(app.estilo, resultado):
			opciones.append(
				Opcion(_("Responder unas preguntas"), preguntar, ayuda=_("Tres preguntas cortas sobre cómo te ha ido. Son voluntarias."))
			)
		opciones += [
			Opcion(_("Repetir la actividad"), repetir_actividad, ayuda=_("Vuelve a empezar la misma actividad.")),
			Opcion(_("Elegir otra actividad"), otra, ayuda=_("Vuelve a la lista de actividades de este entorno.")),
			Opcion(_("Volver al menú principal"), app.volver_al_menu, ayuda=_("Guarda el resultado y vuelve al menú principal.")),
		]
		return opciones

	menu = Menu(app, _("Fin de {actividad}").format(actividad=partida.nombre_actividad), lista, escapable=False, intro=texto)
	menu.sin_cortar = True
	celebrar(app, partida, recompensas)
	app.abrir(menu)
	if pedido_por_la_actividad(partida) and partida.grabadora is not None:
		# La actividad pide el cuestionario (``cuestionario: true``): se ofrece solo, tras el resultado y sin cortarlo.
		# Cada pregunta se puede saltar, y también todas de una vez.
		estado["preguntado"] = True
		abrir_cuestionario(app, partida, al_terminar=menu.refrescar, sin_cortar=True)
	return menu


def pedido_por_la_actividad(partida: Any) -> bool:
	"""Si el resultado de la actividad trae preguntas finales (``docs/actividades.md``, «Recompensas y cuestionario»)."""
	preguntas = partida.resultado.get("cuestionario") if isinstance(partida.resultado, dict) else None
	return isinstance(preguntas, (list, tuple)) and bool(preguntas)


def abrir_cuestionario(app: Aplicacion, partida: Any, al_terminar: Any = None, sin_cortar: bool = False) -> None:
	"""Hace las preguntas una a una; las respuestas se apuntan en la sesión como un evento «valoracion».

	``sin_cortar``: la primera pregunta espera a que acabe lo que se esté
	diciendo (el resultado), en vez de cortarlo.
	"""
	preguntas = puente_actividades.preguntas(app.estilo, partida.resultado)
	respuestas: dict[str, Any] = {}

	def terminar() -> None:
		if respuestas:
			partida.apuntar_valoracion(respuestas)
			app.decir(_("Gracias. Tus respuestas se han guardado."), True)
		if callable(al_terminar):
			al_terminar(False)

	def preguntar(indice: int) -> None:
		if indice >= len(preguntas):
			terminar()
			return
		pregunta = preguntas[indice]

		def responder(valor: Any) -> Any:
			def hacer() -> None:
				respuestas[str(pregunta["id"])] = valor
				app.cerrar(menu)
				preguntar(indice + 1)

			return hacer

		def saltar() -> None:
			app.cerrar(menu)
			preguntar(indice + 1)

		def dejar() -> None:
			app.cerrar(menu)
			terminar()

		opciones = [Opcion(etiqueta, responder(valor)) for valor, etiqueta in pregunta["opciones"]]
		opciones.append(
			Opcion(_("Prefiero no contestar"), saltar, ayuda=_("Pasa a la pregunta siguiente sin contestar esta."), callado=True)
		)
		if indice + 1 < len(preguntas):
			opciones.append(
				Opcion(
					_("Dejar las preguntas"), dejar, ayuda=_("No contesta ninguna más. Las que ya has contestado se guardan."), callado=True
				)
			)
		titulo = _("Pregunta {n} de {total}. {texto}").format(n=indice + 1, total=len(preguntas), texto=pregunta["texto"])
		menu = Menu(
			app, titulo, opciones, escapable=False, intro=puente_actividades.presentacion_preguntas(app.estilo) if indice == 0 else None
		)
		menu.sin_cortar = sin_cortar and indice == 0
		app.abrir(menu)

	preguntar(0)
