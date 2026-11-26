"""Frases de las actividades en los tres estilos de presentación.

El contenido de aprendizaje es el mismo para un niño, un joven y un adulto;
cambia cómo se dice. El estilo **infantil** usa frases cortas y celebra
mucho; el **juvenil** habla de misiones y retos; el **adulto** es sobrio y
práctico, sin tono infantil. Cada frase tiene una clave estable y sus tres
redacciones (o una sola, si vale para todos); nunca se comparan textos
traducidos.

Las frases de examen son neutras a propósito: no animan, no valoran y no
dicen si se ha acertado.
"""

from __future__ import annotations

import logging
from typing import Any

from app.core.i18n import N_, _, _n

log = logging.getLogger(__name__)

_INDICE = {"infantil": 0, "juvenil": 1, "adulto": 2}

# Clave → una frase para todos, o (infantil, juvenil, adulto).
FRASES: dict[str, str | tuple[str, str, str]] = {
	# ── Comunes ──
	"inicio": (N_("¡Vamos a jugar!"), N_("Empieza la misión."), N_("Comienza la actividad.")),
	"objetivo_libre": (N_("Explora por donde quieras."), N_("Explora con libertad."), N_("Recorre el lugar con libertad.")),
	"con_tiempo": N_("Tienes {tiempo}."),
	"queda_un_minuto": (N_("¡Queda un minuto!"), N_("Queda un minuto."), N_("Queda un minuto.")),
	"logro": (N_("¡Muy bien!"), N_("Hecho."), N_("Conseguido.")),
	"final_bien": (N_("¡Lo has conseguido! ¡Bravo!"), N_("Misión cumplida."), N_("Actividad completada.")),
	"final_incompleto": (
		N_("Lo dejamos aquí. ¡Otro día seguimos!"),
		N_("Misión sin terminar. Puedes repetirla cuando quieras."),
		N_("Actividad terminada sin completar."),
	),
	"final_tiempo": (
		N_("¡Se acabó el tiempo! Otro día lo intentamos otra vez."),
		N_("Tiempo agotado. Puedes repetirla."),
		N_("Se ha agotado el tiempo."),
	),
	"desbloqueo": (N_("¡Has desbloqueado {nombre}!"), N_("Desbloqueado: {nombre}."), N_("Has desbloqueado: {nombre}.")),
	"nivel_sube": (
		N_("¡Subes de nivel! El próximo día: {nivel}."),
		N_("Nivel superado. Siguiente nivel: {nivel}."),
		N_("Nivel superado. La próxima vez: {nivel}."),
	),
	"marca": N_("Tu marca: {tiempo}."),
	"ofrecer_ayuda": (
		N_("¿Te echo una mano? Pide una pista cuando quieras."),
		N_("¿Atascado? Puedes pedir una pista."),
		N_("Si lo necesitas, puedes pedir una pista."),
	),
	"sin_pista": N_("Ahora no hay ninguna pista."),
	"sin_pistas_examen": N_("En el examen no hay pistas."),
	"baliza_un_rato": (
		N_("Escucha: va a sonar un ratito desde allí."),
		N_("La baliza suena unos segundos desde allí."),
		N_("Una baliza sonará unos segundos desde allí."),
	),
	"contenedor_vacio": (N_("Aquí no hay nada."), N_("Vacío."), N_("Aquí no está.")),
	"premio_cogido": (N_("¡Has encontrado {nombre}!"), N_("Conseguido: {nombre}."), N_("Encontrado: {nombre}.")),
	"premio_dentro": (N_("¡Sorpresa! Dentro estaba {nombre}."), N_("Dentro estaba {nombre}. Conseguido."), N_("Dentro estaba {nombre}.")),
	"premio_nuevo": (
		N_("¡Ha aparecido un premio nuevo: {nombre}!"),
		N_("Nuevo premio en juego: {nombre}."),
		N_("Hay una cosa más que encontrar: {nombre}."),
	),
	"travieso": (
		N_("¡Oh, no! El travieso ha cambiado un premio de sitio."),
		N_("Aviso: alguien ha movido uno de los premios."),
		N_("Una de las cosas ha cambiado de sitio."),
	),
	"amigo": N_("Tiko"),
	"acompanante": N_("Soy {amigo} y voy contigo."),
	"acompanante_anima": N_("{amigo} dice: ¡tú puedes!"),
	# ── Búsqueda y pistas ──
	"busqueda_inicio": (
		N_("¡A buscar tesoros!"),
		N_("Misión: encontrar los premios escondidos."),
		N_("Prepara la visita: hay cosas que encontrar."),
	),
	"busqueda_lista": (N_("Busca {lista}."), N_("Encuentra {lista}."), N_("Encuentra {lista}.")),
	"busqueda_siguiente": (N_("Ahora busca {nombre}."), N_("Siguiente: {nombre}."), N_("Siguiente: {nombre}.")),
	"pistas_inicio": (
		N_("¡Sigue las pistas! Cada premio te dice dónde está el siguiente."),
		N_("Misión: seguir la cadena de pistas."),
		N_("Cada cosa que encuentres te dirá dónde está la siguiente."),
	),
	"pista_primera": N_("Primera pista:"),
	"pista_siguiente": N_("Pista del siguiente:"),
	"pista_sin_texto": (N_("¡A buscar el siguiente!"), N_("Busca el siguiente."), N_("Busca el siguiente.")),
	# ── Sacar los tesoros ──
	"tesoros_inicio": (
		N_("¡Hay que salvar los tesoros! Coge uno y sácalo por la puerta que esté más cerca."),
		N_("Misión: saca los tesoros de uno en uno por la salida más cercana."),
		N_("Recoge cada objeto y sácalo por la salida más cercana, de uno en uno."),
	),
	"tesoro_buscar": (N_("Busca un tesoro."), N_("Busca un tesoro."), N_("Busca uno de los objetos.")),
	"tesoro_llevar": N_("Llevas {nombre}. Sácalo por la salida más cercana."),
	"tesoro_ya_llevas": N_("Ya llevas uno. Sácalo antes de coger otro."),
	"tesoro_fuera_mejor": (
		N_("¡Tesoro a salvo por la mejor puerta!"),
		N_("A salvo por la salida más corta."),
		N_("Fuera por la salida más cercana."),
	),
	"tesoro_fuera_peor": (
		N_("Tesoro a salvo. Había una puerta más cerca."),
		N_("A salvo, pero había una salida más cerca."),
		N_("Fuera. Había una salida más cercana."),
	),
	"vuelves_a_entrar": N_("Vuelves a entrar por la misma puerta."),
	"salir_sin_tesoro": N_("Has salido sin llevar nada. Vuelves a entrar."),
	"no_es_salida": N_("Por aquí no se sale del edificio. Vuelves a entrar."),
	"salidas_hay": N_("Las salidas son: {lista}."),
	"salida_cercana": N_("La salida más cercana desde aquí es {nombre}."),
	# ── Recados y rutas ──
	"recadero_inicio": (N_("¡Hoy eres el recadero!"), N_("Misión de reparto."), N_("Hay encargos que hacer.")),
	"paso_recoger": (N_("Ve a {lugar} y coge {nombre}."), N_("Ve a {lugar} y recoge {nombre}."), N_("Ve a {lugar} y recoge {nombre}.")),
	"paso_entregar": N_("Lleva {nombre} a {lugar}."),
	"paso_ir": N_("Ve a {lugar}."),
	"paso_localizar": (N_("Encuentra {lugar}."), N_("Localiza {lugar}."), N_("Localiza {lugar}.")),
	"paso_volver": (
		N_("Ahora vuelve al sitio donde empezaste."),
		N_("Ahora vuelve al punto de partida."),
		N_("Ahora vuelve al punto de partida."),
	),
	"paso_volver_mismo": N_("Ahora vuelve por donde has venido hasta el punto de partida."),
	"paso_confirmar": N_("Cuando creas que has llegado, confírmalo con la orden de usar."),
	"recogido": (N_("¡Ya tienes {nombre}!"), N_("Recogido: {nombre}."), N_("Recogido: {nombre}.")),
	"entregado": (N_("¡Entregado! Muy bien."), N_("Entregado."), N_("Entregado.")),
	"llegada": (N_("¡Has llegado a {lugar}!"), N_("Has llegado: {lugar}."), N_("Has llegado a {lugar}.")),
	"aun_no": N_("Todavía no has llegado."),
	"ruta_inicio": (N_("¡Vamos de paseo!"), N_("Empieza la ruta."), N_("Comienza la ruta.")),
	"corte_aviso": (
		N_("¡Ojo! Hoy no se puede pasar por {paso}. Busca otro camino."),
		N_("Hoy {paso} está cortado. Busca una ruta alternativa."),
		N_("Hoy no se puede pasar por {paso}. Busca otro camino."),
	),
	"corte_usado": N_("Ese paso estaba cortado. La próxima vez busca otro camino."),
	"visita_inicio": (N_("¡Vamos de visita! Te voy contando cosas."), N_("Empieza la visita."), N_("Comienza la visita guiada.")),
	"visita_en_vivo": N_("El profesional te irá contando lo que hay."),
	# ── Escondite ──
	"personaje": (N_("la rana Rita"), N_("el escurridizo"), N_("el teléfono")),
	"escondite_inicio": (
		N_("{personaje} se ha escondido. ¡Escucha y encuéntralo!"),
		N_("Reto: {personaje} se ha escondido. Localízalo por el sonido."),
		N_("Suena {personaje} en algún lugar. Localízalo por el sonido."),
	),
	"escondite_objetivo": (N_("Encuentra a {personaje}."), N_("Localiza a {personaje}."), N_("Localiza {personaje}.")),
	"escondite_encontrado": (N_("¡Lo has encontrado!"), N_("Localizado."), N_("Localizado.")),
	"escondite_otra": (N_("¡Se ha vuelto a esconder!"), N_("Se esconde otra vez."), N_("Ha cambiado de sitio. Localízalo de nuevo.")),
	"ronda": N_("Ronda {n} de {total}."),
	# ── Sigue al guía ──
	"guia": (N_("Lupa"), N_("tu guía"), N_("el guía")),
	"guia_inicio": (
		N_("Soy {guia}. ¡Sígueme! Escucha mis pasos."),
		N_("Te lleva {guia}. Sigue el sonido de sus pasos."),
		N_("Sigue al guía por el sonido de sus pasos."),
	),
	"guia_objetivo": N_("Sigue los pasos del guía sin alejarte."),
	"guia_espera": (N_("¡Por aquí! Te espero."), N_("Por aquí."), N_("Por aquí.")),
	"guia_lejos": (
		N_("¡Te has alejado! Ven hacia mis pasos."),
		N_("Te has alejado. Vuelve hacia los pasos."),
		N_("Te has alejado del guía."),
	),
	"guia_conector": N_("Ahora, {conector}. Te espero al otro lado."),
	"guia_llegada": (N_("¡Hemos llegado a {lugar}!"), N_("Destino alcanzado: {lugar}."), N_("Hemos llegado a {lugar}.")),
	# ── Explorador ──
	"explorador_inicio": (
		N_("¡Eres un explorador! Descubre todos los sitios."),
		N_("Misión: descubrir todo el mapa."),
		N_("Recorre todos los espacios del lugar."),
	),
	"descubierto": N_("{n} de {total}."),
	# ── Cruces ──
	"cruce_inicio": (
		N_("Vamos a cruzar la calle con mucho cuidado. Escucha bien antes de cruzar."),
		N_("Reto: cruzar por los pasos de peatones y con el semáforo a favor."),
		N_("Práctica de cruces: decide cuándo cruzar. Es un simulador: no dice si un cruce real es seguro."),
	),
	"cruce_3": (N_("¡Muy bien cruzado!"), N_("Cruce perfecto."), N_("Cruce correcto: por el paso y sin tráfico.")),
	"cruce_2": N_("Has cruzado sin peligro, pero fuera del paso de peatones."),
	"cruce_1": N_("Has cruzado con el semáforo en rojo. Espera al verde la próxima vez."),
	"cruce_0": (
		N_("¡Cuidado! Venía un coche. Espera a que no se oiga ninguno."),
		N_("Cruce con peligro: venía un vehículo."),
		N_("Cruce inseguro: había un vehículo cerca."),
	),
	"cruce_llegar": N_("Después, ve a {lugar}."),
	# ── Prácticas ──
	"exploracion_inicio": (N_("¡A explorar!"), N_("Exploración libre."), N_("Exploración libre: recorre el lugar a tu ritmo.")),
	"perimetro_inicio": (
		N_("Vamos a conocer esta sala. Primero, da la vuelta siguiendo la pared."),
		N_("Vas a conocer la sala: primero el perímetro, después el interior."),
		N_("Familiarización de sala: primero el perímetro, después el interior."),
	),
	"perimetro_objetivo": N_("Recorre el perímetro de {sala} siguiendo la pared."),
	"interior_objetivo": N_("Ahora recorre el interior de {sala}, cruzándola de lado a lado."),
	"perimetro_progreso": N_("Llevas {porcentaje} por ciento del perímetro."),
	"perimetro_hecho": (
		N_("¡Ya conoces las paredes! Ahora cruza por el medio."),
		N_("Perímetro hecho. Ahora, el interior."),
		N_("Perímetro completado. Ahora recorre el interior."),
	),
	"perimetro_fuera": N_("Has salido de la sala. Vuelve a entrar."),
	"linea_inicio": (
		N_("Vamos a seguir la pared sin soltarnos."),
		N_("Reto: seguir la línea guía sin separarte."),
		N_("Sigue la línea guía de un extremo a otro sin separarte."),
	),
	"linea_objetivo": N_("Sigue {linea} hasta el final."),
	"linea_pared": N_("la pared {lado} de {espacio}"),
	"linea_bordillo": N_("el borde {lado} de {espacio}"),
	"linea_separado": (
		N_("¡Te has soltado! Vuelve a la pared."),
		N_("Te has separado. Vuelve a la línea."),
		N_("Te has separado de la línea guía."),
	),
	"linea_mitad": N_("Vas por la mitad."),
	# ── Exámenes: neutros en los tres estilos ──
	"examen_inicio": (
		N_("Vamos a hacer unas pruebas. No hay pistas y no te diré si aciertas. Hazlo sin prisa."),
		N_("Empieza el examen. No hay pistas y no se dice si aciertas. Hazlo a tu ritmo."),
		N_("Empieza el examen. No hay pistas y no se dice si aciertas. Hazlo a tu ritmo."),
	),
	"examen_fin": N_("El examen ha terminado. Gracias."),
	"examen_prueba": N_("Prueba {n} de {total}."),
	"examen_estas_en": N_("Estás en {lugar}."),
	"examen_ruta": N_("Ve a {destino}. Cuando creas que has llegado, confírmalo con la orden de usar."),
	"examen_tiempo_limite": N_("Tienes {tiempo}."),
	"examen_anotado": N_("Anotado."),
	"examen_tiempo": N_("Se acabó el tiempo de esta prueba."),
	"examen_parada": N_("Lo dejamos aquí por hoy."),
	"examen_salida": N_("Sal del edificio por la salida más cercana."),
	"examen_senalar": N_("Sin moverte del sitio, gírate hacia {destino} y confírmalo con la orden de usar."),
	"examen_distancias_camino": N_("Andando desde aquí, ¿qué queda más cerca: {a} o {b}?"),
	"examen_distancias_recta": N_("En línea recta desde aquí, ¿qué queda más cerca: {a} o {b}?"),
	"examen_reconstruccion": N_("¿Qué hay al {lado} de {referencia}?"),
	"examen_opcion": N_("Opción {n} de {total}: {texto}."),
	"examen_elige": N_("Cambia de opción con la orden de objetivo y confirma con la orden de usar."),
	"examen_ida": N_("Primero sigue la baliza hasta {destino}."),
	"examen_ida_2": N_("Ahora sigue la baliza hasta {destino}."),
	"examen_vuelve": N_("Ahora vuelve a {destino} sin ayuda. Cuando creas que has llegado, confírmalo con la orden de usar."),
	"examen_atajo": N_(
		"Ahora ve a {destino} por el camino más corto que sepas. Cuando creas que has llegado, confírmalo con la orden de usar."
	),
}

LADOS: dict[str, str] = {"norte": N_("norte"), "este": N_("este"), "sur": N_("sur"), "oeste": N_("oeste")}


class Textos:
	"""Frases de un estilo: ``tx("clave", dato=valor)`` devuelve la frase traducida y rellena."""

	def __init__(self, estilo: str = "adulto") -> None:
		self.estilo = estilo if estilo in _INDICE else "adulto"

	def __call__(self, clave: str, **datos: Any) -> str:
		frase = FRASES.get(clave)
		if frase is None:
			log.warning("Falta la frase «%s» de las actividades", clave)
			return ""
		origen = frase if isinstance(frase, str) else frase[_INDICE[self.estilo]]
		if not origen:
			return ""
		texto = _(origen)
		try:
			return texto.format(**datos) if datos else texto
		except KeyError, IndexError, ValueError:
			# Una traducción con una llave mal puesta no debe dejar mudo el juego.
			log.warning("La frase «%s» no admite los datos que se le pasan", clave)
			return texto

	@staticmethod
	def lado(lado: str) -> str:
		"""Nombre traducido de un lado cardinal (norte, este, sur, oeste)."""
		return _(LADOS[lado]) if lado in LADOS else lado

	@staticmethod
	def duracion(segundos: float) -> str:
		"""«2 minutos», «45 segundos» o «1 minuto y 30 segundos»."""
		total = max(0, round(float(segundos)))
		minutos, resto = divmod(total, 60)
		partes: list[str] = []
		if minutos:
			partes.append(_n("{n} minuto", "{n} minutos", minutos).format(n=minutos))
		if resto or not minutos:
			partes.append(_n("{n} segundo", "{n} segundos", resto).format(n=resto))
		return _("{a} y {b}").format(a=partes[0], b=partes[1]) if len(partes) == 2 else partes[0]

	@staticmethod
	def lista(elementos: list[str]) -> str:
		"""«a, b y c»."""
		validos = [e for e in elementos if e]
		if len(validos) <= 1:
			return "".join(validos)
		return _("{lista} y {ultimo}").format(lista=", ".join(validos[:-1]), ultimo=validos[-1])
