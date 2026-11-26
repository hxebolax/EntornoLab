"""Tabla declarativa de las preferencias del Estudio, sin wx.

Cada preferencia es un ``Campo`` cuya ``clave`` es la clave de configuración
(«seccion.clave») y cuyo ``grupo`` es la pestaña en que aparece. El diálogo
(``app/ui/preferencias.py``) se genera entero a partir de esta tabla: añadir
una preferencia es añadir una línea aquí (y su valor por defecto y su regla
en ``app/core/configuracion.py``).

Lo que el formulario enseña no siempre es lo que se guarda:

- un volumen se guarda de 0 a 1 y se enseña en un deslizador de 0 a 100
  (``extra={"escala": 100}``);
- los canales de voz se guardan como diccionario canal → activado y se
  enseñan como lista de casillas (``extra={"mapa": True}``);
- las claves que empiezan por ``_restablecer.`` no son de configuración: son
  casillas que, marcadas, devuelven a su valor de fábrica la clave que sigue
  (los mapas de teclas y de botones, la lista de recientes).

``a_formulario`` y ``a_configuracion`` hacen esas conversiones.

Los límites de los números (mínimo y máximo) no se repiten aquí: se toman de
las ``REGLAS`` de la configuración con ``campos_preferencias``.

Las listas que dependen del equipo (idiomas, salidas de sonido, perfiles de
cabeza, paquetes de sonidos, voces) se piden a funciones de este módulo en
el momento de abrir el diálogo. Ninguna abre un dispositivo de sonido.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Any

from app.core.i18n import N_, _
from app.ui.esquemas import Campo, c

log = logging.getLogger(__name__)

PREFIJO_RESTABLECER = "_restablecer."
#: Campo de solo lectura con la descripción del paquete de sonidos elegido (no es una clave de configuración).
NOTA_PAQUETE = "_nota.paquete"

G_GENERAL = N_("General")
G_SONIDO = N_("Sonido")
G_VOLUMENES = N_("Volúmenes")
G_VOZ = N_("Voz")
G_JUEGO = N_("Juego")
G_MANDOS = N_("Teclado y mando")
G_EDITOR = N_("Editor")
G_SUPERVISION = N_("Supervisión y privacidad")
G_ACCESIBILIDAD = N_("Accesibilidad")
G_RED = N_("Red y registro")

#: Claves de configuración que no se editan en Preferencias, y por qué.
CLAVES_INTERNAS: dict[str, str] = {
	"ventana.": "geometría de la ventana: se guarda sola",
	"actualizaciones.ultima_comprobacion": "la apunta el actualizador",
	"actualizaciones.preguntado": "la apunta el actualizador",
	"actualizaciones.version_saltada": "se decide en el diálogo de actualizaciones",
	"editor.recientes": "la lista se llena sola; aquí solo se puede vaciar",
	"importar.aviso_privacidad_visto": "se apunta al aceptar el aviso",
	"complementos.desactivados": "se decide en «Complementos instalados»",
	"teclado.mapa": "se reasigna desde el reproductor; aquí solo se restablece",
	"mando.mapa": "se reasigna desde el reproductor; aquí solo se restablece",
	"sonido.volumen_sonidos": "se ajusta sonido a sonido desde el reproductor",
	"juego.alias": "lo recuerda el reproductor; nunca es un nombre real",
	"supervision.ultima_sala": "la recuerda el reproductor",
	"supervision.eventos_anunciados": "se elige en la ventana de supervisión",
}


# ── Listas que dependen del equipo ───────────────────────────────────────────


def idiomas() -> list[tuple[str, str]]:
	"""«auto» y los idiomas con catálogo, cada uno con su nombre escrito en ese idioma."""
	from app.core import i18n

	return [("auto", _("El de Windows")), *[(codigo, i18n.nombre_idioma(codigo)) for codigo in i18n.idiomas_disponibles()]]


def motores() -> list[tuple[str, str]]:
	"""Los motores de sonido, diciendo cuáles no se pueden usar en este equipo."""
	try:
		from app.audio import fabrica

		lista = fabrica.motores_disponibles()
	except Exception:  # noqa: BLE001 - sin las bibliotecas de sonido se enseñan los identificadores
		log.info("No se pudieron consultar los motores de sonido.", exc_info=True)
		return [(nombre, nombre) for nombre in ("openal", "clasico", "estereo", "bass", "nulo")]
	return [
		(
			motor["id"],
			motor["nombre"] if motor["disponible"] else _("{nombre} (no disponible en este equipo)").format(nombre=motor["nombre"]),
		)
		for motor in lista
	]


def dispositivos() -> list[tuple[str, str]]:
	"""«» (el predeterminado de Windows) y las salidas de sonido conectadas ahora."""
	try:
		from app.audio import salidas

		nombres = salidas.disponibles()
	except Exception:  # noqa: BLE001 - sin la lista se puede seguir eligiendo la salida predeterminada
		log.info("No se pudieron enumerar las salidas de sonido.", exc_info=True)
		nombres = []
	return [("", _("La predeterminada de Windows")), *[(nombre, nombre) for nombre in nombres]]


def segundas_salidas() -> list[tuple[str, str]]:
	"""«» (ninguna) y las salidas de sonido conectadas ahora."""
	return [("", _("Ninguna")), *dispositivos()[1:]]


def perfiles_hrtf() -> list[tuple[str, str]]:
	"""Perfiles de cabeza de OpenAL Soft que hay en el disco."""
	try:
		from app.audio import motor_openal

		return [(cabeza, motor_openal.nombre_cabeza(cabeza).capitalize()) for cabeza in motor_openal.cabezas_disponibles()]
	except Exception:  # noqa: BLE001 - sin OpenAL solo queda el perfil integrado
		log.info("No se pudieron listar los perfiles de cabeza.", exc_info=True)
		return [("", _("La integrada"))]


def lista_paquetes() -> list[dict]:
	"""Los paquetes de sonidos instalados, como los da ``app.audio.paquetes.listar`` (lista vacía si no se puede)."""
	try:
		from app.audio import paquetes

		return list(paquetes.listar())
	except Exception:  # noqa: BLE001 - sin la lista se deja el paquete de serie
		log.info("No se pudieron listar los paquetes de sonidos.", exc_info=True)
		return []


def paquetes_sonido() -> list[tuple[str, str]]:
	"""Paquetes de sonidos instalados en ``data/sounds``: (identificador, nombre)."""
	lista = lista_paquetes()
	if not lista:
		return [("por_defecto", _("De serie"))]
	return [(paquete["id"], str(paquete.get("nombre") or paquete["id"])) for paquete in lista]


def descripcion_paquete(identificador: str) -> str:
	"""Frase que describe un paquete (qué es y cuántos sonidos trae), o una explicación si no está instalado."""
	for paquete in lista_paquetes():
		if paquete.get("id") == identificador:
			try:
				from app.audio import paquetes

				return paquetes.describir(paquete)
			except Exception:  # noqa: BLE001 - sin la descripción queda al menos el nombre
				log.info("No se pudo describir el paquete de sonidos %s.", identificador, exc_info=True)
				return str(paquete.get("nombre") or identificador)
	return _("Este paquete no está instalado: sonarán los sonidos de serie.")


def voces_sapi() -> list[tuple[str, str]]:
	"""«» (la predeterminada) y las voces SAPI instaladas en Windows."""
	# Desde el hilo de voz: un objeto COM de SAPI creado en el hilo de wx da RPC_E_CANTCALLOUT_ININPUTSYNCCALL al abrir diálogos.
	from app.core import voz

	nombres = voz.voces_sapi()
	return [("", _("La predeterminada de Windows")), *[(nombre, nombre) for nombre in nombres]]


# ── Tabla ────────────────────────────────────────────────────────────────────

_VOLUMEN = {"escala": 100, "unidad": N_("por ciento"), "paso": 5, "paso_pagina": 10}


def _volumen(clave: str, etiqueta: str, ayuda: str) -> Campo:
	return c(clave, etiqueta, "deslizador", ayuda, minimo=0, maximo=100, grupo=G_VOLUMENES, extra=dict(_VOLUMEN))


CAMPOS: list[Campo] = [
	# ── General ──
	c(
		"general.idioma",
		N_("Idioma"),
		"opcion",
		N_("Idioma de la aplicación. Los textos cambian al aceptar; los menús ya abiertos y los botones estándar, al reiniciar."),
		opciones=lambda _v: idiomas(),
		grupo=G_GENERAL,
	),
	c(
		"general.comprobar_novedades",
		N_("Enseñar las novedades tras actualizar"),
		"si_no",
		N_("Muestra una vez los cambios de la versión nueva."),
		grupo=G_GENERAL,
	),
	c(
		"general.estilo_visual",
		N_("Colores"),
		"opcion",
		N_("Colores del Estudio: los de Windows, claros u oscuros."),
		opciones=[("sistema", N_("Los de Windows")), ("claro", N_("Claros")), ("oscuro", N_("Oscuros"))],
		grupo=G_GENERAL,
	),
	c(
		"general.tamano_texto",
		N_("Tamaño del texto, en porcentaje"),
		"entero",
		N_("Tamaño del texto del Estudio y del plano. 100 es el normal."),
		obligatorio=True,
		grupo=G_GENERAL,
	),
	c(
		"general.alto_contraste",
		N_("Alto contraste en el plano y en el reproductor"),
		"si_no",
		N_("Usa solo colores de mucho contraste al dibujar."),
		grupo=G_GENERAL,
	),
	c(
		"general.anunciar_arranque",
		N_("Decir «Iniciando» al arrancar"),
		"si_no",
		N_("Avisa por voz mientras la aplicación se abre."),
		grupo=G_GENERAL,
	),
	c(
		"general.minimizar_a_bandeja",
		N_("Minimizar a la bandeja del sistema"),
		"si_no",
		N_("Al minimizar, la ventana se oculta y queda un icono en la bandeja. Si su bandeja oculta los iconos, no lo active."),
		grupo=G_GENERAL,
	),
	c(
		"general.cerrar_a_bandeja",
		N_("Ocultar en la bandeja al cerrar"),
		"si_no",
		N_("Alt+F4 oculta la ventana en vez de salir. Archivo, Salir sale siempre."),
		grupo=G_GENERAL,
	),
	c(
		"general.iniciar_en_bandeja",
		N_("Empezar oculta en la bandeja"),
		"si_no",
		N_("La aplicación arranca sin enseñar la ventana."),
		grupo=G_GENERAL,
	),
	# ── Sonido ──
	c(
		"sonido.motor",
		N_("Motor de sonido"),
		"opcion",
		N_("Cómo se produce el sonido 3D del reproductor. Si el elegido falla se usa el siguiente."),
		opciones=lambda _v: motores(),
		grupo=G_SONIDO,
	),
	c(
		"sonido.perfil_hrtf",
		N_("Perfil de cabeza"),
		"opcion",
		N_("Forma de cabeza y de oreja que usa el sonido binaural. Pruebe cuál sitúa mejor los sonidos para cada alumno."),
		opciones=lambda _v: perfiles_hrtf(),
		grupo=G_SONIDO,
	),
	c(
		"sonido.paquete",
		N_("Paquete de sonidos"),
		"opcion",
		N_("Colección de sonidos del reproductor: pasos, golpes, puertas, ambientes."),
		opciones=lambda _v: paquetes_sonido(),
		grupo=G_SONIDO,
	),
	c(
		NOTA_PAQUETE,
		N_("Descripción del paquete elegido"),
		"solo_lectura",
		N_("Qué es el paquete de sonidos elegido y cuántos sonidos trae. Cambia al elegir otro paquete."),
		grupo=G_SONIDO,
	),
	c(
		"sonido.igualar_paquetes",
		N_("Igualar el volumen de los paquetes"),
		"si_no",
		N_("Lleva los sonidos de los demás paquetes al nivel de los de serie."),
		grupo=G_SONIDO,
	),
	c(
		"sonido.dispositivo",
		N_("Salida de sonido"),
		"opcion",
		N_("Por dónde suena el reproductor: normalmente, los auriculares del alumno."),
		opciones=lambda _v: dispositivos(),
		grupo=G_SONIDO,
	),
	c(
		"sonido.segunda_salida",
		N_("Segunda salida, para el profesional"),
		"opcion",
		N_("Salida donde el profesional oye lo mismo que el alumno. Solo con el motor clásico."),
		opciones=lambda _v: segundas_salidas(),
		grupo=G_SONIDO,
	),
	c(
		"sonido.modo_salida",
		N_("Tipo de salida"),
		"opcion",
		N_("Con auriculares se usa sonido binaural; con altavoces, panorama."),
		opciones=[("auriculares", N_("Auriculares")), ("altavoces", N_("Altavoces"))],
		grupo=G_SONIDO,
	),
	c(
		"sonido.proteccion_auditiva",
		N_("Protección auditiva"),
		"si_no",
		N_("Pone techo al volumen y hace graduales las subidas, para proteger el oído con auriculares."),
		grupo=G_SONIDO,
	),
	c(
		"sonido.refuerzo_detras",
		N_("Reforzar lo que suena detrás"),
		"si_no",
		N_("Apaga un poco el sonido que llega por detrás, para distinguirlo del de delante."),
		grupo=G_SONIDO,
	),
	c(
		"sonido.seguimiento_cabeza",
		N_("Seguimiento de cabeza con OpenTrack"),
		"si_no",
		N_("El giro de la cabeza se suma al rumbo del oyente."),
		grupo=G_SONIDO,
	),
	c(
		"sonido.seguimiento_cabeza_puerto",
		N_("Puerto de OpenTrack"),
		"entero",
		N_("Puerto UDP en el que OpenTrack envía la posición de la cabeza."),
		obligatorio=True,
		grupo=G_SONIDO,
	),
	# ── Volúmenes ──
	_volumen("sonido.volumen_maestro", N_("General"), N_("Volumen de todo el sonido del reproductor.")),
	_volumen("sonido.volumen_efectos", N_("Efectos"), N_("Golpes, puertas y sonidos de los objetos.")),
	_volumen("sonido.volumen_pasos", N_("Pasos"), N_("Sonido de los pasos del alumno.")),
	_volumen("sonido.volumen_ambiente", N_("Ambiente"), N_("Sonidos de fondo y fuentes de sonido del entorno.")),
	_volumen("sonido.volumen_ayudas", N_("Sonidos de ayuda"), N_("Balizas, sonda y brújula.")),
	_volumen("sonido.volumen_interfaz", N_("Interfaz"), N_("Sonidos de los menús.")),
	_volumen("sonido.volumen_musica", N_("Música de fondo"), N_("Música de los juegos.")),
	_volumen("sonido.volumen_voz", N_("Voz"), N_("Volumen de la voz respecto al resto.")),
	# ── Voz ──
	c(
		"voz.salida",
		N_("Salida de voz"),
		"opcion",
		N_(
			"Quién habla en el Estudio y en el reproductor. Automática: el lector de pantalla y, si no hay ninguno, la voz de Windows. "
			"Solo el lector de pantalla: sin lector no se habla y nunca se usa la voz de Windows. "
			"Siempre la voz de Windows: aunque haya lector. "
			"Sin voz: no se habla nunca; los mensajes siguen en el historial, en la barra de estado, en la pantalla del reproductor "
			"y, si hay lector, en la línea braille."
		),
		opciones=[
			("automatica", N_("Automática: el lector de pantalla y, si no hay, la voz de Windows")),
			("lector", N_("Solo el lector de pantalla, nunca la voz de Windows")),
			("sapi", N_("Siempre la voz de Windows (SAPI)")),
			("ninguna", N_("Sin voz: no hablar nunca")),
		],
		grupo=G_VOZ,
	),
	c(
		"voz.voz_sapi",
		N_("Voz de Windows"),
		"opcion",
		N_("Voz SAPI que se usa con la salida automática cuando no hay lector de pantalla, o siempre con «Siempre la voz de Windows»."),
		opciones=lambda _v: voces_sapi(),
		grupo=G_VOZ,
	),
	c(
		"voz.velocidad",
		N_("Rapidez de la voz de Windows"),
		"deslizador",
		N_("De 0 (muy lenta) a 100 (muy rápida)."),
		minimo=0,
		maximo=100,
		grupo=G_VOZ,
		extra={"paso": 5},
	),
	c(
		"voz.volumen",
		N_("Fuerza de la voz de Windows"),
		"deslizador",
		N_("Volumen de la voz SAPI, de 0 a 100."),
		minimo=0,
		maximo=100,
		grupo=G_VOZ,
		extra={"paso": 5},
	),
	c(
		"voz.braille",
		N_("Enviar los mensajes a la línea braille"),
		"si_no",
		N_("Lo que se dice se escribe también en la línea braille."),
		grupo=G_VOZ,
	),
	c(
		"voz.interrumpir",
		N_("Un mensaje nuevo corta el anterior"),
		"si_no",
		N_("Si se desmarca, los mensajes se dicen uno detrás de otro."),
		grupo=G_VOZ,
	),
	c(
		"voz.historial",
		N_("Mensajes que se guardan para repasar"),
		"entero",
		N_("Cuántos mensajes se pueden repasar con «anterior» y «siguiente»."),
		obligatorio=True,
		grupo=G_VOZ,
	),
	c(
		"voz.detalle",
		N_("Detalle de las descripciones"),
		"opcion",
		N_("Cuánto cuenta el juego al describir lo que hay."),
		opciones=[(0, N_("Mínimo")), (1, N_("Breve")), (2, N_("Normal")), (3, N_("Máximo"))],
		grupo=G_VOZ,
	),
	c(
		"voz.canales",
		N_("Canales de voz activados"),
		"casillas",
		N_("Qué clases de mensaje se dicen. Los de un canal desactivado quedan en el historial."),
		opciones=[
			("juego", N_("Juego")),
			("ayuda", N_("Ayudas")),
			("aviso", N_("Avisos")),
			("profesional", N_("Mensajes del profesional")),
		],
		grupo=G_VOZ,
		extra={"mapa": True},
	),
	# ── Juego ──
	c(
		"juego.modo_movimiento",
		N_("Forma de moverse"),
		"opcion",
		N_(
			"Cómo avanza el alumno de serie. Cada ficha de alumno puede tener la suya, y la de la ficha manda: le llega al reproductor "
			"al conectarse a la sala y se queda guardada en su perfil."
		),
		opciones=[
			("pasos", N_("Por pasos")),
			("continuo", N_("Continuo")),
			("brujula", N_("Por rumbos de brújula")),
			("salas", N_("De sala en sala")),
			("aceras", N_("Por aceras, de novedad en novedad")),
		],
		grupo=G_JUEGO,
	),
	c("juego.paso_m", N_("Longitud del paso"), "metros", N_("Cuánto se avanza con cada pulsación."), obligatorio=True, grupo=G_JUEGO),
	c(
		"juego.giro_grados",
		N_("Giro por pulsación, en grados"),
		"decimal",
		N_("Cuánto gira el alumno con cada pulsación."),
		obligatorio=True,
		grupo=G_JUEGO,
	),
	c(
		"juego.velocidad_ms",
		N_("Velocidad en modo continuo, en metros por segundo"),
		"decimal",
		N_("Velocidad al andar en el modo continuo."),
		obligatorio=True,
		grupo=G_JUEGO,
	),
	c(
		"juego.formato_direccion",
		N_("Forma de decir las direcciones"),
		"opcion",
		N_("Cómo se dicen las direcciones: por horas del reloj, por lados, por puntos cardinales o en grados."),
		opciones=[
			("reloj", N_("Horas del reloj")),
			("lados", N_("Izquierda y derecha")),
			("cardinal", N_("Puntos cardinales")),
			("grados", N_("Grados")),
		],
		grupo=G_JUEGO,
	),
	c(
		"juego.unidad",
		N_("Unidad de las distancias"),
		"opcion",
		N_("En qué se dicen las distancias."),
		opciones=[("metros", N_("Metros")), ("pasos", N_("Pasos"))],
		grupo=G_JUEGO,
	),
	c(
		"juego.estilo",
		N_("Estilo de los mensajes"),
		"opcion",
		N_("Tono de los mensajes del juego según la edad."),
		opciones=[("infantil", N_("Infantil")), ("juvenil", N_("Juvenil")), ("adulto", N_("Adulto"))],
		grupo=G_JUEGO,
	),
	c(
		"juego.ver_plano",
		N_("Dibujar el plano en el reproductor"),
		"si_no",
		N_("El reproductor dibuja la planta, para baja visión y acompañantes."),
		grupo=G_JUEGO,
	),
	c(
		"juego.pantalla_negra",
		N_("Pantalla en negro en el reproductor"),
		"si_no",
		N_("El reproductor no dibuja nada: para quien no usa la pantalla o no quiere pistas visuales."),
		grupo=G_JUEGO,
	),
	c(
		"juego.posicion_menu",
		N_("Decir la posición en los menús del reproductor"),
		"si_no",
		N_("Al recorrer un menú se dice «3 de 9»."),
		grupo=G_JUEGO,
	),
	# ── Teclado y mando ──
	c(
		"_nota.mandos",
		N_("Cómo se cambian las teclas"),
		"solo_lectura",
		N_("Explicación de dónde se reasignan las teclas y los botones."),
		defecto=N_(
			"Las teclas y los botones del mando se reasignan desde el reproductor, en su menú de opciones, pulsando la tecla o el botón nuevo. Aquí puede devolverlos a los de serie."
		),
		grupo=G_MANDOS,
	),
	c(
		PREFIJO_RESTABLECER + "teclado.mapa",
		N_("Restablecer el mapa de teclas de serie al aceptar"),
		"si_no",
		N_("Olvida las teclas reasignadas."),
		grupo=G_MANDOS,
	),
	c(
		PREFIJO_RESTABLECER + "mando.mapa",
		N_("Restablecer los botones del mando de serie al aceptar"),
		"si_no",
		N_("Olvida los botones reasignados."),
		grupo=G_MANDOS,
	),
	c(
		"mando.zona_muerta",
		N_("Zona muerta de las palancas"),
		"decimal",
		N_("Recorrido de la palanca que se ignora, de 0 a 0,9. Súbalo si el personaje se mueve solo."),
		obligatorio=True,
		grupo=G_MANDOS,
	),
	c("mando.vibracion", N_("Vibración del mando"), "si_no", N_("El mando vibra al chocar y en los avisos."), grupo=G_MANDOS),
	c(
		"mando.fuerza_vibracion",
		N_("Fuerza de la vibración"),
		"deslizador",
		N_("De 0 a 100."),
		minimo=0,
		maximo=100,
		grupo=G_MANDOS,
		extra={"escala": 100, "unidad": N_("por ciento"), "paso": 5, "paso_pagina": 10},
	),
	# ── Editor ──
	c("editor.plano_visible", N_("Enseñar el plano gráfico"), "si_no", N_("Muestra el plano junto al árbol y la lista."), grupo=G_EDITOR),
	c(
		"editor.cuadricula",
		N_("Ajustar a la cuadrícula al dibujar y mover"),
		"si_no",
		N_("Las posiciones se redondean al paso de la cuadrícula."),
		grupo=G_EDITOR,
	),
	c(
		"editor.paso_cuadricula",
		N_("Separación de la cuadrícula"),
		"metros",
		N_("Distancia entre las líneas de la cuadrícula y paso de las flechas en el plano."),
		obligatorio=True,
		grupo=G_EDITOR,
	),
	c(
		"editor.paso_minimo_m",
		N_("Desplazamiento fino"),
		"metros",
		N_("El paso más pequeño al mover con el teclado."),
		obligatorio=True,
		grupo=G_EDITOR,
	),
	c(
		"editor.paso_libre_m",
		N_("Paso libre mínimo"),
		"metros",
		N_("Hueco que debe quedar para pasar al colocar un objeto. Por debajo, se avisa de «paso estrecho»."),
		obligatorio=True,
		grupo=G_EDITOR,
	),
	c(
		"editor.deshacer_niveles",
		N_("Operaciones que se pueden deshacer"),
		"entero",
		N_("Cuántas operaciones recuerda Deshacer. Vale para el próximo entorno que se abra."),
		obligatorio=True,
		grupo=G_EDITOR,
	),
	c(
		"editor.autoguardado_min",
		N_("Minutos entre autoguardados"),
		"entero",
		N_("Cada cuánto se guarda una copia de recuperación. 0 lo desactiva."),
		obligatorio=True,
		grupo=G_EDITOR,
	),
	c(
		"editor.carpeta_entornos",
		N_("Carpeta de los entornos"),
		"ruta_carpeta",
		N_("Dónde se guardan los entornos de serie. Vacío: la carpeta entornos de los datos de la aplicación."),
		grupo=G_EDITOR,
	),
	c(
		"editor.max_recientes",
		N_("Entornos recientes que se recuerdan"),
		"entero",
		N_("Cuántos entornos aparecen en Archivo, Recientes."),
		obligatorio=True,
		grupo=G_EDITOR,
	),
	c(
		PREFIJO_RESTABLECER + "editor.recientes",
		N_("Olvidar los entornos recientes al aceptar"),
		"si_no",
		N_("Vacía la lista de Archivo, Recientes."),
		grupo=G_EDITOR,
	),
	# ── Supervisión y privacidad ──
	c(
		"supervision.puerto",
		N_("Puerto de la sala de supervisión"),
		"entero",
		N_("Puerto TCP en el que el Estudio espera a los reproductores."),
		obligatorio=True,
		grupo=G_SUPERVISION,
	),
	c(
		"supervision.anunciar_eventos",
		N_("Decir lo que le ocurre al alumno"),
		"si_no",
		N_("Anuncia por voz al profesional los choques, las ayudas y los logros del alumno."),
		grupo=G_SUPERVISION,
	),
	c(
		"supervision.segunda_salida",
		N_("Oír al alumno por la segunda salida"),
		"si_no",
		N_("Envía el sonido del alumno también a la segunda salida de sonido."),
		grupo=G_SUPERVISION,
	),
	c(
		"privacidad.cifrar_fichas",
		N_("Cifrar los datos personales de las fichas"),
		"si_no",
		N_("Los datos personales de los alumnos se guardan cifrados con la contraseña del profesional."),
		grupo=G_SUPERVISION,
	),
	c(
		"privacidad.caducidad_dias",
		N_("Días que se conservan las sesiones"),
		"entero",
		N_("Pasados esos días, las sesiones se borran. 0: no caducan."),
		obligatorio=True,
		grupo=G_SUPERVISION,
	),
	# ── Accesibilidad ──
	c(
		"accesibilidad.leer_columnas",
		N_("Columnas que se leen en las listas"),
		"opcion",
		N_("Qué se lee al recorrer las columnas de una lista con izquierda y derecha."),
		opciones=[("todas", N_("Todas las columnas")), ("primera", N_("Solo la primera"))],
		grupo=G_ACCESIBILIDAD,
	),
	c(
		"accesibilidad.leer_cabeceras",
		N_("Decir el nombre de la columna"),
		"si_no",
		N_("Antes del valor de una celda se dice de qué columna es."),
		grupo=G_ACCESIBILIDAD,
	),
	c(
		"accesibilidad.anunciar_progreso",
		N_("Anunciar el avance de las tareas largas"),
		"si_no",
		N_("Dice por voz el progreso de importar, exportar y descargar."),
		grupo=G_ACCESIBILIDAD,
	),
	c(
		"accesibilidad.progreso_cada",
		N_("Puntos de porcentaje entre anuncios"),
		"entero",
		N_("Con 25 se anuncia al 25, 50 y 75 por ciento."),
		obligatorio=True,
		grupo=G_ACCESIBILIDAD,
	),
	c(
		"accesibilidad.sonidos_interfaz",
		N_("Sonidos de la interfaz del Estudio"),
		"si_no",
		N_("Sonidos breves al abrir, guardar y fallar."),
		grupo=G_ACCESIBILIDAD,
	),
	# ── Red y registro ──
	c(
		"actualizaciones.comprobar_al_arrancar",
		N_("Buscar actualizaciones al arrancar"),
		"si_no",
		N_("Como mucho una vez al día. Sin marcar, la aplicación no se conecta a Internet por su cuenta."),
		grupo=G_RED,
	),
	c(
		"actualizaciones.canal",
		N_("Versiones que se ofrecen"),
		"opcion",
		N_("Solo las versiones estables, o también las preliminares de pruebas."),
		opciones=[("estable", N_("Estables")), ("pruebas", N_("También las de pruebas"))],
		grupo=G_RED,
	),
	c(
		"complementos.comprobar_actualizaciones",
		N_("Mirar también el catálogo de complementos"),
		"si_no",
		N_("Al buscar actualizaciones, mira si hay complementos nuevos."),
		grupo=G_RED,
	),
	c(
		"complementos.url_catalogo",
		N_("Dirección del catálogo de complementos"),
		"texto",
		N_("Vacío: el catálogo oficial. Solo direcciones https."),
		grupo=G_RED,
	),
	c(
		"importar.overpass_url",
		N_("Servidor Overpass propio"),
		"texto",
		N_("Para descargar de OpenStreetMap. Vacío: los servidores públicos."),
		grupo=G_RED,
	),
	c(
		"importar.nominatim_url",
		N_("Servidor Nominatim propio"),
		"texto",
		N_("Para buscar lugares. Vacío: el servidor público."),
		grupo=G_RED,
	),
	c(
		"importar.radio_m",
		N_("Radio que se propone al importar de OpenStreetMap, en metros"),
		"entero",
		N_("Tamaño de la zona que se propone descargar."),
		obligatorio=True,
		grupo=G_RED,
	),
	c(
		"registro.nivel",
		N_("Detalle del registro"),
		"opcion",
		N_("Cuánto se escribe en los ficheros de registro. «Depuración» solo para buscar un fallo."),
		opciones=[
			("DEBUG", N_("Depuración")),
			("INFO", N_("Normal")),
			("WARNING", N_("Solo avisos y errores")),
			("ERROR", N_("Solo errores")),
		],
		grupo=G_RED,
	),
]


def es_clave_de_configuracion(clave: str) -> bool:
	"""False para las casillas de restablecer y las notas, que no se guardan como tales."""
	return not clave.startswith("_")


def es_interna(clave: str) -> bool:
	"""True si esa clave de configuración no se edita en Preferencias a propósito."""
	return any(clave == interna or (interna.endswith(".") and clave.startswith(interna)) for interna in CLAVES_INTERNAS)


def _traducir_opciones(campo: Campo) -> Campo:
	"""Las opciones de la tabla llevan sus textos marcados con ``N_``: se traducen al abrir el diálogo."""
	if callable(campo.opciones) or not campo.opciones:
		return campo
	return dataclasses.replace(campo, opciones=[(valor, _(texto)) for valor, texto in campo.opciones])


def campos_preferencias(configuracion: Any) -> list[Campo]:
	"""La tabla lista para el formulario: opciones traducidas y límites tomados de las reglas."""
	resultado: list[Campo] = []
	for campo in CAMPOS:
		campo = _traducir_opciones(campo)
		if campo.tipo == "solo_lectura" and isinstance(campo.defecto, str):
			campo = dataclasses.replace(campo, defecto=_(campo.defecto))
		if es_clave_de_configuracion(campo.clave) and campo.tipo in ("entero", "decimal", "metros"):
			regla = configuracion.regla(campo.clave) if configuracion is not None else None
			if regla is not None:
				campo = dataclasses.replace(campo, minimo=regla.minimo, maximo=regla.maximo)
		resultado.append(campo)
	return resultado


def a_formulario(campo: Campo, valor: Any) -> Any:
	"""Valor de la configuración → valor que enseña el formulario."""
	if campo.extra.get("escala"):
		return int(round(float(valor or 0) * campo.extra["escala"]))
	if campo.extra.get("mapa"):
		return [clave for clave, activo in (valor or {}).items() if activo]
	return valor


def a_configuracion(campo: Campo, valor: Any) -> Any:
	"""Valor del formulario → valor que se guarda en la configuración."""
	if campo.extra.get("escala"):
		return float(valor) / campo.extra["escala"]
	if campo.extra.get("mapa"):
		marcadas = set(valor or [])
		return {clave: clave in marcadas for clave, _texto in campo.lista_opciones({})}
	if valor is None and campo.tipo in ("texto", "ruta_carpeta", "ruta_fichero"):
		return ""
	return valor


def valores_de_formulario(configuracion: Any, de_fabrica: bool = False) -> dict[str, Any]:
	"""Todos los valores del formulario a partir de la configuración (o de sus valores de fábrica)."""
	valores: dict[str, Any] = {}
	for campo in CAMPOS:
		if campo.clave.startswith(PREFIJO_RESTABLECER):
			valores[campo.clave] = False
		elif es_clave_de_configuracion(campo.clave):
			crudo = configuracion.valor_por_defecto(campo.clave) if de_fabrica else configuracion.obtener(campo.clave)
			valores[campo.clave] = a_formulario(campo, crudo)
	if "sonido.paquete" in valores:
		valores[NOTA_PAQUETE] = descripcion_paquete(str(valores["sonido.paquete"] or ""))
	return valores
